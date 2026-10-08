"""Delivery latency (PRE_BETA_SCOPE_DECISION_V1 §2 A «measured alert latency, candle close → delivery»;
backlog A4). Read from stored rows only: no new clock, no new table.

Each delivered message has a source time, the moment the fact it reports existed:

- level / price / move / push: the close of the candle that carried the fact (a level or
  personal-alert touch: the 1m or 5m bar that touched; a sharp move: the 5m bar that completed
  it; a detector push: the 5m bucket it was decided on);
- event: the moment the calendar pre-alert became due (the event time minus the lead);
- brief / weekly: the scheduled time.

Latency is delivery (`finished_at` of the SENT row) minus the source time, split into detection
(source → decision) and sending (decision → delivery). A row whose source time is unknown (an
alert recorded before A4) is counted apart, never guessed. Messages that expired undelivered are
counted per class: they are the latency tail that never arrived.

The push carries the measured value as a field (`latency_field`); the line itself is drawn by
the template (track B, F1)."""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Optional

logger = logging.getLogger(__name__)

WINDOW = timedelta(days=7)
CANDLE, EVENT_DUE, SCHEDULE = "candle_close", "event_due", "schedule"
SOURCE = {"level": CANDLE, "price": CANDLE, "approach": CANDLE, "move": CANDLE, "push": CANDLE,
          "event": EVENT_DUE, "brief": SCHEDULE, "weekly": SCHEDULE}
CLASSES = tuple(SOURCE)


def percentile(values, q: float) -> Optional[float]:
    """Nearest-rank percentile (no interpolation: every reported value was observed)."""
    xs = sorted(values)
    if not xs:
        return None
    return float(xs[max(0, math.ceil(q / 100.0 * len(xs)) - 1)])


def _when(v) -> Optional[datetime]:
    if v is None or isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v))


def row_class(row: Mapping[str, Any]) -> str:
    return row["alert_kind"] if row["kind"] == "alert" else row["kind"]


def row_source(row: Mapping[str, Any]) -> Optional[datetime]:
    if row["kind"] == "alert":
        return _when(row.get("source_at"))
    return row["decision_ts"]


def alert_source_at(payload: Mapping[str, Any]) -> Optional[datetime]:
    return _when((payload or {}).get("source_at"))


_MESSAGE_ID = {"alert": "alert_pk", "weekly": "weekly_pk", "brief": "view_pk", "push": "decision_id"}


def message_key(row: Mapping[str, Any]):
    """One message, however many participants received it (review of #375: one alert to 20 people is one
    measurement of the pipeline, not 20). A row without its id counts alone."""
    ref = row.get(_MESSAGE_ID.get(row["kind"], ""))
    return (row["kind"], ref) if ref is not None else ("row", id(row))


def summarize(rows: Iterable[Mapping[str, Any]]) -> dict:
    """{class: {n, messages, p50_s, p95_s, max_s, detect_p50_s, detect_p95_s, send_p50_s, send_p95_s,
    expired, no_source}} over SENT rows (latency) and EXPIRED_UNDELIVERED rows (counted). `n` counts
    delivery rows, `messages` the distinct messages among them."""
    acc: dict = {}
    for r in rows:
        cls = row_class(r)
        a = acc.setdefault(cls, {"total": [], "detect": [], "send": [], "expired": 0, "no_source": 0,
                                 "messages": set()})
        if r["state"] == "EXPIRED_UNDELIVERED":
            a["expired"] += 1
            continue
        src, done = row_source(r), r["finished_at"]
        if done is None:
            continue
        a["send"].append((done - r["decision_ts"]).total_seconds())
        if src is None:
            a["no_source"] += 1
            continue
        a["total"].append((done - src).total_seconds())
        a["messages"].add(message_key(r))
        a["detect"].append((r["decision_ts"] - src).total_seconds())
    out = {}
    for cls, a in acc.items():
        out[cls] = {"source": SOURCE.get(cls), "n": len(a["total"]), "messages": len(a["messages"]),
                    "p50_s": percentile(a["total"], 50), "p95_s": percentile(a["total"], 95),
                    "max_s": max(a["total"]) if a["total"] else None,
                    "detect_p50_s": percentile(a["detect"], 50), "detect_p95_s": percentile(a["detect"], 95),
                    "send_p50_s": percentile(a["send"], 50), "send_p95_s": percentile(a["send"], 95),
                    "expired": a["expired"], "no_source": a["no_source"]}
    return out


async def class_summary(conn, now: datetime) -> dict:
    """`summarize` over the last `WINDOW`; {} when it cannot be read (the delay field then has
    no class percentiles, and a send never waits on or fails for it)."""
    try:
        return summarize(await conn.delivery_latency_rows(since=now - WINDOW))
    except Exception as exc:  # noqa: BLE001 - a measurement never blocks a delivery
        logger.warning("delivery latency summary unavailable: %s", type(exc).__name__)
        return {}


def latency_field(cls: str, source_at: Optional[datetime], now: datetime,
                  summary: Optional[Mapping[str, Any]], *, window_days: int = WINDOW.days) -> Optional[dict]:
    """The push's latency field: this message's own lag at render (source → now) beside the
    class's measured P50/P95 with its N. None without a source time."""
    if source_at is None:
        return None
    s = (summary or {}).get(cls) or {}
    return {"class": cls, "source": SOURCE.get(cls), "source_at": source_at.isoformat(),
            "lag_s": max(0, int(round((now - source_at).total_seconds()))),
            "p50_s": s.get("p50_s"), "p95_s": s.get("p95_s"), "n": int(s.get("n") or 0),
            "messages": int(s.get("messages") or 0),
            "window_days": window_days}


def _s(v) -> str:
    return "—" if v is None else f"{v:.0f}s"


def format_report(summary: Mapping[str, Any], *, days: int) -> str:
    """Owner text (/admin_latency): one line per class, every percentile with its N."""
    lines = [f"Delivery latency, last {days} d (source → delivered; nearest-rank)"]
    if not summary:
        return lines[0] + "\nno delivered or expired messages in the window"
    for cls in [c for c in CLASSES if c in summary] + sorted(set(summary) - set(CLASSES)):
        s = summary[cls]
        lines.append(f"{cls} ({s['source'] or '?'}): N={s['n']} P50 {_s(s['p50_s'])} P95 {_s(s['p95_s'])} "
                     f"max {_s(s['max_s'])} · detect P50 {_s(s['detect_p50_s'])} P95 {_s(s['detect_p95_s'])} "
                     f"· send P50 {_s(s['send_p50_s'])} P95 {_s(s['send_p95_s'])}"
                     + (f" · expired {s['expired']}" if s["expired"] else "")
                     + (f" · no source {s['no_source']}" if s["no_source"] else ""))
    return "\n".join(lines)
