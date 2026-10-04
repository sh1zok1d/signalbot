"""Market alerts and forecast tracking inside the existing notifier cycle (PRODUCT_DECISION_V2 §2).

Four alert kinds, each with a unique identity (`alert_key`) so one market fact alerts once:

- `level`: the first touch in its period of yesterday's / last week's / last month's high or low
  (the period must have opened on the approach side), with the history of such touches;
- `event`: CPI or FOMC within `event_lead_min`, with how big such hours were;
- `move`: a 15-minute move larger than the historical threshold (about one episode in three
  days), relative to the 1h scale known before the move, without the CPI/FOMC term;
- `price`: a participant's own /alert level.

Policy (market side, recorded on the alert row): the global push switch; quiet hours (Kyiv) and
a daily cap for `level` + `move`; one `move` per cooldown. A personal alert ignores quiet hours
and the cap. Recipients: push on and the kind's preference on (personal: its participant).
Delivery reuses the outbox rules: at most one send attempt, never older than the delivery TTL.

Forecast tracking: in the first minutes of every hour the current 1h / 4h / 24h corridors are
recorded once; matured ones are scored INSIDE / OUTSIDE (NO_DATA when bars are missing).

Market alerts never read or change the detector's push decisions.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from .config import BetaConfig
from .hist_series import BAR_MS, Bars, from_ms, to_ms
from .models import D_EXPIRED, D_FAILED, D_PENDING, D_SENDING, D_SENT, D_SUPPRESSED, D_UNKNOWN, \
    DELIVERY_TOO_OLD, PUSH_DISABLED, USER_INACTIVE

logger = logging.getLogger("beta.market_alerts")

MARKET_ALERTS_VERSION = "BETA_MARKET_ALERTS_V1"
CAPPED_KINDS = ("level", "move")
QUIET_KINDS = ("level", "move", "event")
RECORD_WINDOW_MIN = 10
SCORE_SETTLE = timedelta(minutes=3)     # the window's last 1m bars have closed and been collected
SAME_PRICE_FRAC = 0.0005                # push levels this close are one touch (zones merge at levels.ZONE_TOL_PCT)
DAY_MS = 86_400_000


def _period(kind: str) -> str:
    return {"D": "day", "W": "week", "M": "month"}[kind[1]]


def _period_start(name: str, now: datetime) -> datetime:
    d = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    if name == "day":
        return d
    if name == "week":
        return d - timedelta(days=d.weekday())
    return d.replace(day=1)


def _series_since(b: Bars, closed_1m, start: datetime, end: Optional[datetime] = None):
    """[(open time, high, low, close, minutes)] of the closed bars lying wholly inside [start, end),
    in time order: 5m grid bars where a whole 5m bar fits, 1m bars of the Stage-1 tail for the
    rest (the partial 5m bars at either edge and the minutes after the grid's last bar). A bar
    that only partly overlaps the window is never counted whole."""
    s_ms = to_ms(start)
    e_ms = to_ms(end) if end is not None else None
    out, used5 = [], set()
    a = max(0, -(-(s_ms - b.t0) // BAR_MS))               # first 5m bar opening at or after start
    for i in range(int(a), b.n):
        t = b.t0 + i * BAR_MS
        if e_ms is not None and t + BAR_MS > e_ms:
            break
        if math.isfinite(b.close[i]):
            out.append((from_ms(t), float(b.high[i]), float(b.low[i]), float(b.close[i]), 5))
            used5.add(t)
    for r in closed_1m or ():
        t = to_ms(r["ts"])
        if t < s_ms or (e_ms is not None and t + 60_000 > e_ms) or (t - t % BAR_MS) in used5:
            continue
        out.append((r["ts"], float(r["high"]), float(r["low"]), float(r["close"]), 1))
    out.sort(key=lambda x: x[0])
    return out


def first_touch(series, level: float, side: int) -> Optional[datetime]:
    for ts, hi, lo, _c, _m in series:
        if (side > 0 and hi >= level) or (side < 0 and lo <= level):
            return ts
    return None


def _period_open(b: Bars, closed_1m, start: datetime) -> Optional[float]:
    i = (to_ms(start) - b.t0) // BAR_MS
    if 0 <= i < b.n and math.isfinite(b.open[i]):
        return float(b.open[i])
    for r in closed_1m or ():
        if r["ts"] == start:
            return float(r["open"])
    return None


def _zone_brief(z: Optional[Mapping[str, Any]]) -> Optional[dict]:
    if not z:
        return None
    return {k: z.get(k) for k in ("low", "high", "edge", "distance_pct", "members", "kinds", "touch")}


def detect_level_touches(block: Mapping[str, Any], b: Bars, closed_1m, *, now: datetime, max_age: timedelta,
                         stats: Optional[Mapping[str, Any]]) -> list:
    from .levels import PUSH_LEVELS
    out = []
    lstats = ((stats or {}).get("levels") or {}).get("types") or {}
    corridor_4h = ((block.get("corridor") or {}).get("horizons") or {}).get("4h")
    for lv in (block.get("levels") or {}).get("all") or ():
        kind = lv["kind"]
        if kind not in PUSH_LEVELS:
            continue
        side = +1 if kind.endswith("H") else -1
        pname = _period(kind)
        start = _period_start(pname, now)
        popen = _period_open(b, closed_1m, start)
        if popen is None or side * (lv["price"] - popen) <= 0:
            continue
        touched = first_touch(_series_since(b, closed_1m, start), lv["price"], side)
        if touched is None or now - touched > max_age:
            continue
        nxt_list = (block.get("levels") or {}).get("above" if side > 0 else "below") or []
        nxt = next((z for z in nxt_list if side * (z["edge"] - lv["price"]) > lv["price"] * 0.001), None)
        rec = lstats.get(kind)
        out.append({"kind": "level", "key": f"level:{kind}:{start.date().isoformat()}",
                    "payload": {"at": touched.isoformat(), "level_kind": kind, "level": lv["price"],
                                "side": side, "period": pname, "price": block["price"],
                                "history": {k: rec[k] for k in ("real", "control", "verdicts")} if rec else None,
                                "next": _zone_brief(nxt), "corridor_4h": corridor_4h,
                                "event_zone": block.get("event_zone") or {}}})
    return _one_per_price(out)


_PUSH_RANK = {"M": 0, "W": 1, "D": 2}                     # month > week > day


def _one_per_price(cands: list) -> list:
    """A week high that is also the day high is one market fact: keep the most important kind
    and name the others in it, so one touch sends one message and uses one daily slot."""
    cands = sorted(cands, key=lambda c: (_PUSH_RANK[c["payload"]["level_kind"][1]], c["key"]))
    kept: list = []
    for c in cands:
        p = c["payload"]
        same = next((k for k in kept if k["payload"]["side"] == p["side"]
                     and abs(k["payload"]["level"] - p["level"]) <= SAME_PRICE_FRAC * p["level"]), None)
        if same is None:
            kept.append(c)
        else:
            same["payload"].setdefault("also_kinds", []).append(p["level_kind"])
    return kept


def detect_events(block: Mapping[str, Any], cal, *, now: datetime, lead: timedelta,
                  stats: Optional[Mapping[str, Any]]) -> list:
    from .calendar_events import PUSH_KINDS
    out = []
    ev_stats = ((stats or {}).get("events") or {}).get("kinds") or {}
    for e in cal["events"]:
        if e["kind"] not in PUSH_KINDS or not (now < e["at"] <= now + lead):
            continue
        mins = max(1, int(round((e["at"] - now).total_seconds() / 60)))
        out.append({"kind": "event", "key": f"event:{e['kind']}:{e['at'].isoformat()}",
                    "payload": {"at": now.isoformat(), "event_kind": e["kind"], "event_at": e["at"].isoformat(),
                                "minutes": mins, "price": block["price"], "stats": ev_stats.get(e["kind"]),
                                "event_zone": block.get("event_zone") or {}}})
    return out


def detect_move(block: Mapping[str, Any], b: Bars, closed_1m, *, now: datetime, model) -> list:
    """A sharp 15-minute move on the closed 5m grid: |close[i] / close[i-3] - 1| over the 1h scale
    known before the move began, with the CPI/FOMC term at 0 (SHARP_MOVE_EVENT_CONDITIONING =
    DISABLED_PENDING_VALIDATION). It is `rangecast.move_ratio`, the statistic the threshold was
    calibrated on, so «примерно раз в N дней» holds; a threshold built on another statistic is
    never used. It is checked once per closed 5m bar (a sliding 1m window would fire more often
    than the calibration says)."""
    from .rangecast import MOVE_STATISTIC, MOVE_WINDOW_BARS, move_ratio_at
    thr = ((model or {}).get("move") or {})
    if not model or not thr.get("threshold") or thr.get("statistic") != MOVE_STATISTIC or b.n <= MOVE_WINDOW_BARS:
        return []
    if to_ms(now) - b.end_ms >= BAR_MS:                  # the grid's last bar is not the latest closed one
        return []
    i = b.n - 1
    j = i - MOVE_WINDOW_BARS                              # last 5m bar closed before the move began
    o, c = float(b.close[j]), float(b.close[i])
    if not (math.isfinite(o) and math.isfinite(c)) or o <= 0:
        return []
    move = (c - o) / o * 100.0
    ratio = move_ratio_at(model, b, i)
    if ratio is None or ratio < float(thr["threshold"]):
        return []
    lv = block.get("levels") or {}
    near = [z for z in ((lv.get("above") or [])[:1] + (lv.get("below") or [])[:1]) if z]
    eps = thr.get("episodes_per_day")
    return [{"kind": "move", "key": f"move:{b.end_ms // BAR_MS}",
             "payload": {"at": from_ms(b.end_ms).isoformat(), "start": from_ms(b.t0 + (j + 1) * BAR_MS).isoformat(),
                         "open": o, "close": c, "move_pct": move, "ratio": ratio,
                         "every_days": (1.0 / eps) if eps else None,
                         "corridor_1h": ((block.get("corridor") or {}).get("horizons") or {}).get("1h"),
                         "near": [_zone_brief(z) for z in near], "event_zone": block.get("event_zone") or {}}}]


def detect_price_alerts(active, b: Bars, closed_1m, *, block: Mapping[str, Any], now: Optional[datetime] = None,
                        max_age: Optional[timedelta] = None) -> list:
    """A personal alert fires on the first touch after it was set. A touch older than `max_age`
    (the participant was stopped, or pushes were paused) is still reported, marked `late`, so
    the message names the day and time instead of looking current."""
    out = []
    corridor_4h = ((block.get("corridor") or {}).get("horizons") or {}).get("4h")
    for a in active:
        side = +1 if a["direction"] == "above" else -1
        touched = first_touch(_series_since(b, closed_1m, a["created_at"]), float(a["price"]), side)
        if touched is None:
            continue
        at = max(touched, a["created_at"])
        late = bool(now is not None and max_age is not None and now - at > max_age)
        out.append({"kind": "price", "key": f"price:{a['price_alert_pk']}", "price_alert_pk": a["price_alert_pk"],
                    "target_user_pk": a["user_pk"],
                    "payload": {"at": at.isoformat(), "level": float(a["price"]), "late": late,
                                "price": block["price"], "corridor_4h": corridor_4h,
                                "event_zone": block.get("event_zone") or {}}})
    return out


def _in_quiet_hours(cfg: BetaConfig, ts: datetime) -> bool:
    from .detector import in_quiet_hours
    return in_quiet_hours(cfg, ts)


async def _decide_and_record(conn, cfg: BetaConfig, cand: Mapping[str, Any], *, now: datetime, push_on: bool) -> str:
    m = cfg.section("decision")["market_alerts"]
    kind = cand["kind"]
    reason = None
    if not push_on:
        reason = "PUSH_DISABLED"
    elif kind != "price" and kind in QUIET_KINDS and _in_quiet_hours(cfg, now):
        reason = "QUIET_HOURS"
    elif kind in CAPPED_KINDS and await conn.count_market_pushes(utc_day=now.astimezone(timezone.utc).date(),
                                                                 kinds=CAPPED_KINDS) >= int(m["max_per_utc_day"]):
        reason = "DAILY_CAP"
    async with conn.transaction():          # a price alert is recorded and consumed together
        pk = await conn.insert_market_alert(kind=kind, alert_key=cand["key"], decision_ts=now,
                                            decision="PUSH" if reason is None else "SUPPRESSED",
                                            suppression_reason=reason, payload=cand["payload"],
                                            target_user_pk=cand.get("target_user_pk"))
        if kind == "price":
            await conn.mark_price_alert_triggered(cand["price_alert_pk"], at=now)
    if pk is None:
        return "DUPLICATE"
    return "PUSH" if reason is None else reason


async def record_forecasts(conn, block: Mapping[str, Any], *, now: datetime) -> int:
    c = block.get("corridor") or {}
    if not block.get("available") or not c.get("horizons"):
        return 0
    hour = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    if now - hour > timedelta(minutes=RECORD_WINDOW_MIN):
        return 0
    from .rangecast import HORIZON_MS
    n = 0
    stats_pk = (block.get("stats") or {}).get("stats_pk")
    for h, x in c["horizons"].items():
        if await conn.forecast_issued_since(horizon=h, since=hour):
            continue
        ok = await conn.insert_forecast(horizon=h, issued_at=now, horizon_end=now + timedelta(milliseconds=HORIZON_MS[h]),
                                        anchor_price=float(block["price"]), lower=float(x["lower"]),
                                        upper=float(x["upper"]), coverage=float(c["coverage"]),
                                        model_version=str((block.get("version") or "")), stats_pk=stats_pk)
        n += int(ok)
    return n


async def score_forecasts(conn, b: Bars, closed_1m, *, now: datetime) -> dict:
    out = {"scored": 0, "no_data": 0}
    for f in await conn.fetch_matured_forecasts(now=now - SCORE_SETTLE):
        series = _series_since(b, closed_1m, f["issued_at"], f["horizon_end"])
        minutes = (f["horizon_end"] - f["issued_at"]).total_seconds() / 60
        covered = sum(x[4] for x in series)
        if not series or covered < 0.9 * minutes:
            if now - f["horizon_end"] > timedelta(hours=6):
                await conn.set_forecast_outcome(f["forecast_pk"], outcome="NO_DATA", high=None, low=None, now=now)
                out["no_data"] += 1
            continue
        hi = max(x[1] for x in series)
        lo = min(x[2] for x in series)
        inside = lo >= f["lower"] and hi <= f["upper"]
        await conn.set_forecast_outcome(f["forecast_pk"], outcome="INSIDE" if inside else "OUTSIDE",
                                        high=hi, low=lo, now=now)
        out["scored"] += 1
    return out


async def _regime(conn, cfg: BetaConfig, *, now: datetime) -> Optional[dict]:
    """The D7 hour state for research evidence, only where the D7 line itself may show."""
    from .config import effective_d7_enabled
    getter = getattr(conn, "get_admin_d7_enabled", None)
    from .regime_d7 import regime_for_status
    tx = getattr(conn, "transaction", None)
    try:
        if tx is None:
            if getter is None or not effective_d7_enabled(cfg, await getter()):
                return None
            return await regime_for_status(conn, now=now, product_status="")
        async with tx():                    # a savepoint: a failed read never aborts the caller's transaction
            if getter is None or not effective_d7_enabled(cfg, await getter()):
                return None
            return await regime_for_status(conn, now=now, product_status="")
    except Exception:  # noqa: BLE001 - research context never blocks alerts
        return None


def attach_evidence(cand: dict, block: Mapping[str, Any], cap: Mapping[str, Any]) -> None:
    """Record the research evidence that describes a level touch or a sharp move with the alert
    (beta/research_evidence.py). It is part of the rendered text's by-value input; it never takes
    part in detection, the push decision or the alert identity."""
    from .research_evidence import for_level_touch, for_move
    ev = block.get("evidence")
    if not ev or ev.get("error_type") or cand["kind"] not in ("level", "move"):
        return
    try:
        if cand["kind"] == "level":
            b = cap.get("bars")
            now_ms = int(datetime.fromisoformat(block["as_of"]).timestamp() * 1000)
            found = for_level_touch(ev, b, cand["payload"], levels=(block.get("levels") or {}).get("all") or (),
                                    now_ms=now_ms)
        else:
            found = for_move(ev, cand["payload"])
    except Exception as exc:  # noqa: BLE001 - research context never blocks alerts
        logger.warning("alert evidence failed: %s", type(exc).__name__)
        return
    from .history_stats import json_safe
    cand["payload"]["evidence"] = json_safe(found)


async def run_market_alerts(conn, cfg: BetaConfig, *, sender, clock, push_on: bool) -> dict:
    """Detect, decide, materialize and send market alerts; record and score corridors."""
    from .decision import build_decision
    from .decision_format import format_alert
    from .delivery import DeliveryRejected
    d = cfg.section("decision")
    m = d["market_alerts"]
    rep = {"detected": 0, "pushed": 0, "suppressed": 0, "materialized": 0, "sent": 0, "failed": 0,
           "unknown": 0, "expired": 0, "forecasts_recorded": 0, "forecasts_scored": 0}
    now = clock()
    cap: dict = {}
    block = await build_decision(conn, cfg, now=now, capture=cap, regime=await _regime(conn, cfg, now=now))
    b, closed = cap.get("bars"), cap.get("closed_1m") or []
    if block.get("available") and b is not None:
        cands = []
        if m["enabled"]:
            cands += detect_level_touches(block, b, closed, now=now,
                                          max_age=timedelta(minutes=int(m["touch_max_age_min"])),
                                          stats=cap.get("stats"))
            cands += detect_events(block, cap["calendar"], now=now,
                                   lead=timedelta(minutes=int(m["event_lead_min"])), stats=cap.get("stats"))
            last_move = await conn.last_market_push_ts(kind="move")
            if last_move is None or now - last_move >= timedelta(minutes=int(m["move_cooldown_min"])):
                cands += detect_move(block, b, closed, now=now, model=cap.get("model"))
            if push_on:
                cands += detect_price_alerts(await conn.fetch_active_price_alerts(), b, closed, block=block, now=now,
                                             max_age=timedelta(minutes=int(m["touch_max_age_min"])))
        known = await conn.market_alert_keys([c["key"] for c in cands]) if cands else set()
        for c in cands:
            if c["key"] in known:
                continue
            rep["detected"] += 1
            attach_evidence(c, block, cap)        # text context only: the decision below never reads it
            res = await _decide_and_record(conn, cfg, c, now=now, push_on=push_on)
            if res == "PUSH":
                rep["pushed"] += 1
            elif res != "DUPLICATE":
                rep["suppressed"] += 1
        if d["forecast_tracking"]:
            rep["forecasts_recorded"] = await record_forecasts(conn, block, now=now)
            rep["forecasts_scored"] = (await score_forecasts(conn, b, closed, now=now))["scored"]
    ttl = cfg.delivery_ttl
    for a in await conn.fetch_undispatched_market_alerts(cfg["notifications"]["max_deliveries_per_run"]):
        rep["materialized"] += await conn.materialize_alert_deliveries(
            alert_pk=a["alert_pk"], kind=a["kind"], decision_ts=a["decision_ts"],
            target_user_pk=a["target_user_pk"], expired=(now - a["decision_ts"] > ttl), now=now)
    for row in await conn.fetch_pending_alert_deliveries(cfg["notifications"]["max_deliveries_per_run"]):
        now = clock()
        did = row["delivery_id"]
        if now - row["decision_ts"] > ttl:
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_EXPIRED, now=now,
                                           suppression_reason=DELIVERY_TOO_OLD)
            rep["expired"] += 1
            continue
        if not push_on:             # paused after the row was made: never sent late
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SUPPRESSED, now=now,
                                           suppression_reason=PUSH_DISABLED)
            rep["suppressed"] += 1
            continue
        if row["user_status"] != "ACTIVE":
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SUPPRESSED, now=now,
                                           suppression_reason=USER_INACTIVE)
            continue
        if sender is None:
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_FAILED, now=now,
                                           error_summary="sender unavailable (no bot token)")
            rep["failed"] += 1
            continue
        lang = row.get("user_lang") or "ru"
        text = format_alert(row["kind"], row["payload"], lang)
        if not await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SENDING, now=now):
            continue
        try:
            from .formatter import push_action_row
            from .i18n import t
            message_id = await sender.send(chat_id=row["chat_id"], html=text,
                                           buttons=[push_action_row(lang),
                                                    [(t(lang, "btn_levels"), "L:levels"),
                                                     (t(lang, "btn_risk"), "L:risk")]])
        except DeliveryRejected as exc:
            await conn.transition_delivery(did, from_state=D_SENDING, to_state=D_FAILED, now=clock(),
                                           error_summary=str(exc)[:300])
            rep["failed"] += 1
            continue
        except Exception as exc:  # noqa: BLE001 - ambiguous: never resend
            await conn.transition_delivery(did, from_state=D_SENDING, to_state=D_UNKNOWN, now=clock(),
                                           error_summary=type(exc).__name__)
            rep["unknown"] += 1
            continue
        sent_at = clock()
        await conn.transition_delivery(did, from_state=D_SENDING, to_state=D_SENT, now=sent_at,
                                       message_id=int(message_id))
        if row.get("user_pk") is not None:
            # detail = the alert kind (level / event / move / price): the measurement contract
            # keeps market alerts and personal /alert deliveries apart
            await conn.record_activity(user_pk=row["user_pk"], action="alert_delivered", lang=lang, at=sent_at,
                                       detail=row["kind"])
        rep["sent"] += 1
    return rep
