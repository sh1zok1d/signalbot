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
from typing import Any, Mapping, Optional, Sequence

from .config import BetaConfig
from .hist_series import BAR_MS, Bars, from_ms, to_ms
from .detector import in_quiet_hours, own_budget_spent
from .models import D_EXPIRED, D_FAILED, D_PENDING, D_SUPPRESSED, DELIVERY_TOO_OLD, PUSH_DISABLED, USER_INACTIVE

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


def first_touch_bar(series, level: float, side: int) -> Optional[tuple]:
    """(open time, minutes) of the first closed bar that touched `level`; its close is the
    alert's source time (backlog A4: latency is measured from that candle close)."""
    for ts, hi, lo, _c, m in series:
        if (side > 0 and hi >= level) or (side < 0 and lo <= level):
            return ts, m
    return None


def first_touch(series, level: float, side: int) -> Optional[datetime]:
    hit = first_touch_bar(series, level, side)
    return None if hit is None else hit[0]


def _period_open(b: Bars, closed_1m, start: datetime) -> Optional[float]:
    i = (to_ms(start) - b.t0) // BAR_MS
    if 0 <= i < b.n and math.isfinite(b.open[i]):
        return float(b.open[i])
    for r in closed_1m or ():
        if r["ts"] == start:
            return float(r["open"])
    return None


def _corridor_track(block: Mapping[str, Any], h: str) -> Optional[dict]:
    """What an alert needs to print horizon h's corridor record at send time: the designed share, the live
    30-day record and the held-out record of that horizon (decision_format.corridor_record)."""
    c = block.get("corridor") or {}
    if c.get("coverage") is None:
        return None
    return {"coverage": c["coverage"], "live": {h: (c.get("live") or {}).get(h)},
            "holdout": {h: {k: ((c.get("holdout") or {}).get(h) or {}).get(k) for k in ("coverage_realized", "n_days")}}}


def _next_brief(block: Mapping[str, Any], z: Optional[Mapping[str, Any]]) -> Optional[dict]:
    """The next level of a level alert with its 24h chance's wording by the /btc rule (claims.touch_wording),
    decided now: the alert is rendered later, at send time, from this payload."""
    out = _zone_brief(z)
    if out is None:
        return None
    from .decision_format import touch_wording
    w = touch_wording(block, "24h", (out.get("touch") or {}).get("24h"))
    out["touch_24h_wording"] = {k: w[k] for k in ("mode", "source", "bin", "predicted", "realized", "n_eff") if k in w}
    return out


def _zone_brief(z: Optional[Mapping[str, Any]]) -> Optional[dict]:
    if not z:
        return None
    return {k: z.get(k) for k in ("low", "high", "edge", "distance_pct", "members", "kinds", "touch")}


def detect_level_touches(block: Mapping[str, Any], b: Bars, closed_1m, *, now: datetime, max_age: timedelta,
                         stats: Optional[Mapping[str, Any]]) -> list:
    from .levels import PUSH_LEVELS, history_view
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
        hit = first_touch_bar(_series_since(b, closed_1m, start), lv["price"], side)
        if hit is None or now - hit[0] > max_age:
            continue
        touched, source_at = hit[0], hit[0] + timedelta(minutes=hit[1])
        nxt_list = (block.get("levels") or {}).get("above" if side > 0 else "below") or []
        nxt = next((z for z in nxt_list if side * (z["edge"] - lv["price"]) > lv["price"] * 0.001), None)
        rec = lstats.get(kind)
        out.append({"kind": "level", "key": f"level:{kind}:{start.date().isoformat()}",
                    "payload": {"at": touched.isoformat(), "source_at": source_at.isoformat(),
                                "level_kind": kind, "level": lv["price"],
                                "side": side, "period": pname, "price": block["price"],
                                "price_ts": block.get("price_ts"),
                                "history": history_view(rec) if rec else None,
                                "next": _next_brief(block, nxt), "corridor_4h": corridor_4h,
                                "corridor_4h_track": _corridor_track(block, "4h") if corridor_4h else None,
                                "event_zone": block.get("event_zone") or {}}})
    return _one_per_price(out)


def detect_structural_touches(block: Mapping[str, Any], b: Bars, *, now: datetime, max_age: timedelta,
                              table: Optional[Mapping[str, Any]]) -> list:
    """The level-touch push as the forecast layer's event (FORECAST_LAYER_DECISION_V1 §3, architect's P2 = A):
    the #352 structural first touch (the price entered the ±0.15 % zone of a previous day / week / month
    high or low; confluent levels are one zone, a level born inside an active zone is absorbed), decided at
    the touch bar's 5m close. It carries the T0 race line (LR_PUSH_HIST_V1) in place of the hold history."""
    from .level_race_live import push_view
    from .levels import structural_first_touches
    now_ms = to_ms(now)
    corridor_4h = ((block.get("corridor") or {}).get("horizons") or {}).get("4h")
    out = []
    for ev in structural_first_touches(b):
        if not (ev["t0_ms"] <= now_ms and now_ms - ev["t0_ms"] <= max_age.total_seconds() * 1000):
            continue
        side = int(ev["side"]) if ev["side"] in (1, -1) else int(ev["struct_side"])
        nxt_list = (block.get("levels") or {}).get("above" if side > 0 else "below") or []
        edge = ev["zone_high"] if side > 0 else ev["zone_low"]
        nxt = next((z for z in nxt_list if side * (z["edge"] - edge) > edge * 0.001), None)
        out.append({"kind": "level", "key": f"level:{ev['event_id']}",
                    "payload": {"at": from_ms(ev["touch_open_ms"]).isoformat(), "source_at": from_ms(ev["t0_ms"]).isoformat(),
                                "trigger": "structural", "event_id": ev["event_id"], "level_kind": ev["kind"],
                                "also_kinds": [k for k in ev["member_kinds"] if k != ev["kind"]],
                                "level": ev["anchor_price"], "zone_low": ev["zone_low"], "zone_high": ev["zone_high"],
                                "side": side, "period": _period(ev["kind"]), "price": block["price"],
                                "price_ts": block.get("price_ts"), "history": None,
                                # no race line inside the 4h CPI / FOMC event zone (cells not event-conditioned)
                                "race": None if (block.get("event_zone") or {}).get("4h") else push_view(b, ev, table),
                                "next": _next_brief(block, nxt), "corridor_4h": corridor_4h,
                                "corridor_4h_track": _corridor_track(block, "4h") if corridor_4h else None,
                                "event_zone": block.get("event_zone") or {}}})
    return out


def level_touch_candidates(cfg: BetaConfig, block: Mapping[str, Any], b: Bars, closed_1m, *, now: datetime,
                           max_age: timedelta, stats: Optional[Mapping[str, Any]]) -> list:
    """The one place the level-touch trigger is chosen (`level_race.push_trigger`)."""
    from .level_race_live import push_trigger, setting
    if push_trigger(cfg) != "structural":
        return detect_level_touches(block, b, closed_1m, now=now, max_age=max_age, stats=stats)
    table = None                       # one display flag for every surface: without it, no race line
    if setting(cfg, "display_enabled"):
        try:
            from .level_race import load_hist_table
            table = load_hist_table()
        except Exception as exc:  # noqa: BLE001 - no verified table: the push goes out without a race line (OFF)
            logger.warning("level race table unavailable: %s", type(exc).__name__)
    return detect_structural_touches(block, b, now=now, max_age=max_age, table=table)


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
                    "payload": {"at": now.isoformat(), "source_at": (e["at"] - lead).isoformat(),
                                "event_kind": e["kind"], "event_at": e["at"].isoformat(),
                                "minutes": mins, "price": block["price"], "price_ts": block.get("price_ts"),
                                "stats": ev_stats.get(e["kind"]),
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
             "payload": {"at": from_ms(b.end_ms).isoformat(), "source_at": from_ms(b.end_ms).isoformat(),
                         "start": from_ms(b.t0 + (j + 1) * BAR_MS).isoformat(),
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
        hit = first_touch_bar(_series_since(b, closed_1m, a["created_at"]), float(a["price"]), side)
        if hit is None:
            continue
        touched = hit[0]
        at = max(touched, a["created_at"])
        late = bool(now is not None and max_age is not None and now - at > max_age)
        out.append({"kind": "price", "key": f"price:{a['price_alert_pk']}", "price_alert_pk": a["price_alert_pk"],
                    "target_user_pk": a["user_pk"],
                    "payload": {"at": at.isoformat(), "source_at": (touched + timedelta(minutes=hit[1])).isoformat(),
                                "level": float(a["price"]), "late": late,
                                "price": block["price"], "price_ts": block.get("price_ts"), "corridor_4h": corridor_4h,
                                "corridor_4h_track": _corridor_track(block, "4h") if corridor_4h else None,
                                "event_zone": block.get("event_zone") or {}}})
    return out


def detect_price_approaches(active, *, block: Mapping[str, Any], now: datetime) -> list:
    """«Мои уровни» (backlog E1): one message when the price first comes within the hour's typical move
    of a personal level that was set farther away than that; never after the touch. No typical move (the
    1h horizon inside its event zone, no statistics): no approach message, the touch still fires."""
    from .decision_format import price_clock
    x = ((block.get("corridor") or {}).get("horizons") or {}).get("1h")
    if not block.get("available") or not x or block.get("price") is None:
        return []
    typ, price = float(x["typical_move_pct"]), float(block["price"])
    out = []
    for a in active:
        if a.get("approached_at") is not None:
            continue
        level = float(a["price"])
        dist = abs(level / price - 1) * 100.0
        set_from = abs(level / float(a["created_price"]) - 1) * 100.0
        side = +1 if a["direction"] == "above" else -1
        if set_from <= typ or dist > typ or side * (level - price) <= 0:
            continue                                   # set already close, still far, or already through
        out.append({"kind": "approach", "key": f"approach:{a['price_alert_pk']}", "price_alert_pk": a["price_alert_pk"],
                    "target_user_pk": a["user_pk"],
                    # the latency source is the close of the price's 1m bar (price_ts is its open)
                    "payload": {"at": now.isoformat(),
                                "source_at": (price_clock(block.get("price_ts")) or now).isoformat(),
                                "level": level, "price": price, "price_ts": block.get("price_ts"),
                                "distance_pct": dist, "typical_1h_pct": typ}})
    return out


_KIND_PREF = {"level": "push_levels", "event": "push_events", "move": "push_moves"}


async def _quiet_for_all(conn, cfg: BetaConfig, kind: str, ts: datetime) -> bool:
    """Quiet hours for an alert of this kind: every participant who could receive it is in their own
    night (backlog C5); the others' deliveries are checked one by one at send time."""
    from .detector import _recipient_tzs, quiet_for_all
    return quiet_for_all(cfg, ts, await _recipient_tzs(conn, _KIND_PREF[kind]))


async def _decide_and_record(conn, cfg: BetaConfig, cand: Mapping[str, Any], *, now: datetime, push_on: bool) -> str:
    m = cfg.section("decision")["market_alerts"]
    kind = cand["kind"]
    reason = None
    if not push_on:
        reason = "PUSH_DISABLED"
    elif kind in QUIET_KINDS:
        # each recipient's own night and own daily budget (review of #373); the UTC-day count of all
        # decisions is only a higher fuse
        from .detector import _recipients, recipient_gate
        recips = await _recipients(conn, _KIND_PREF[kind], now, outbox_kind="alert",
                                   alert_kinds=CAPPED_KINDS if kind in CAPPED_KINDS else ())
        if recips:
            reason = recipient_gate(cfg, now, recips, int(m["max_per_utc_day"]) if kind in CAPPED_KINDS else None)
        elif await _quiet_for_all(conn, cfg, kind, now):
            reason = "QUIET_HOURS"
        if reason is None and kind in CAPPED_KINDS:
            fuse = int(m["decisions_fuse_per_utc_day"]) if recips else int(m["max_per_utc_day"])
            if await conn.count_market_pushes(utc_day=now.astimezone(timezone.utc).date(), kinds=CAPPED_KINDS) >= fuse:
                reason = "DAILY_FUSE" if recips else "DAILY_CAP"    # the fuse is never anyone's own budget
    async with conn.transaction():          # a price alert is recorded and consumed together
        pk = await conn.insert_market_alert(kind=kind, alert_key=cand["key"], decision_ts=now,
                                            decision="PUSH" if reason is None else "SUPPRESSED",
                                            suppression_reason=reason, payload=cand["payload"],
                                            target_user_pk=cand.get("target_user_pk"))
        if kind == "price":
            await conn.mark_price_alert_triggered(cand["price_alert_pk"], at=now)
        elif kind == "approach":
            await conn.mark_price_alert_approached(cand["price_alert_pk"], at=now)
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
    part in detection, the push decision or the alert identity. Matching runs whatever the main-surface
    switch (decision §6.1: collection and matching unchanged): the alert prints it only with research on
    the main surfaces (`evidence_main`), and the «🔬 Исследования» tab of later views lists it."""
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
    cand["payload"]["evidence_main"] = bool(ev.get("main_surfaces"))


def alert_buttons(kind: str, payload: Mapping[str, Any], lang: str, alert_pk: Optional[int] = None) -> list:
    """«📊 BTC сейчас», Levels / Risk, and «🎯 Проверить» with the next level filled in (a level alert's
    next level, a sharp move's nearest level; PRE_BETA_SCOPE_DECISION_V1 §5)."""
    from .check import check_button
    from .formatter import push_action_row
    from .i18n import t
    rows = [push_action_row(lang), [(t(lang, "btn_levels"), "L:levels"), (t(lang, "btn_risk"), "L:risk")]]
    target = None
    if kind == "level" and payload.get("next"):
        target = payload["next"].get("edge")
    elif kind == "approach":                    # the chance to reach the participant's own level now
        target = payload.get("level")
    elif kind == "move" and payload.get("near") and payload.get("close") is not None:
        # the nearest level in the move's direction: above after a rise, below after a fall (none: no button)
        up, close = float(payload.get("move_pct") or 0.0) >= 0, float(payload["close"])
        ahead = [z for z in payload["near"] if z and z.get("edge") is not None and (float(z["edge"]) > close) == up]
        if ahead:
            target = min(ahead, key=lambda z: abs(float(z["edge"]) - close))["edge"]
    if target:
        rows.append([check_button(float(target), lang)])
    from .formatter import mute_row, vote_row
    if alert_pk is not None:                    # «Полезно / Шум» on every alert type (backlog F6)
        rows.append(vote_row(kind, alert_pk, lang))
    mute = {"level": "levels", "event": "events", "move": "moves"}.get(kind)
    if mute:                                    # a personal /alert is the participant's own: no mute
        rows.append(mute_row(mute, lang))
    return rows


async def _journal_level_touch(conn, cand: Mapping[str, Any], decision: str, *, now: datetime) -> None:
    """The level-touch claims of an evaluated candidate (PUSH or SUPPRESSED) and, for a push, the link
    to the alert that shows them. The journal never changes the decision and never stops the run."""
    from .claims import record_displays, record_level_hold, shown_keys
    try:
        await record_level_hold(conn, cand, now=now)
        if decision == "PUSH":
            alert_pk = await conn.market_alert_pk(cand["key"])
            keys = shown_keys("alert", None, alert=cand)
            # the hold line belongs to the touch (its slot is the touch time); the next level's
            # chance to the hour's grid
            await record_displays(conn, surface="alert", shown=[k for k in keys if k[0].startswith("L2_")], now=now,
                                  slot=datetime.fromisoformat(cand["payload"]["at"]), alert_pk=alert_pk)
            await record_displays(conn, surface="alert", shown=[k for k in keys if k[0].startswith("L3_")], now=now,
                                  alert_pk=alert_pk)
    except Exception as exc:  # noqa: BLE001 - internal tracking never blocks an alert
        logger.warning("claim journal (level touch) failed: %s", type(exc).__name__)


async def _race_lines_journaled_only(conn, cands: list) -> None:
    """Fail closed: a structural push carries its T0 race line only when the T0 journal record exists (the
    journal write may have failed, or the landmark may lie outside its write window); otherwise the push goes
    out without the line, as /levels does (decision._journaled_only)."""
    fetch = getattr(conn, "fetch_slot_claims", None)
    for c in cands:
        race = (c.get("payload") or {}).get("race")
        if c.get("kind") != "level" or not race:
            continue
        have = []
        if fetch is not None:
            try:
                have = await fetch(issue_slot=from_ms(int(race["landmark_ms"])), classes=[race["class"]])
            except Exception as exc:  # noqa: BLE001 - no proof of the record: no line
                logger.warning("level race record check failed: %s", type(exc).__name__)
        if not any(x["subject_key"] == f"{race['event_id']}:{race['landmark']}" for x in have):
            c["payload"]["race"] = None
            c["payload"]["race_not_journaled"] = True


async def _journal_race(conn, cfg: BetaConfig, cap: Mapping[str, Any], *, now: datetime) -> dict:
    from .claims import record_level_race
    try:
        return await record_level_race(conn, cfg, now=now, capture=cap)
    except Exception as exc:  # noqa: BLE001 - internal tracking never blocks the alert run
        logger.warning("level race journal failed: %s", type(exc).__name__)
        return {"error": type(exc).__name__}


async def _journal_hour(conn, cfg: BetaConfig, block: Mapping[str, Any], cap: Mapping[str, Any], *,
                        now: datetime) -> dict:
    from .claims import record_claims, score_claims
    try:
        rep = await record_claims(conn, cfg, block, now=now, capture=cap)
        rep.update(await score_claims(conn, cap.get("bars"), cap.get("closed_1m") or [], now=now))
        from .claims import refresh_touch_calibration
        rep["touch_calibration_refreshed"] = await refresh_touch_calibration(conn, now=now) is not None
        return rep
    except Exception as exc:  # noqa: BLE001 - internal tracking never blocks the alert run
        logger.warning("claim journal failed: %s", type(exc).__name__)
        return {"error": type(exc).__name__}


async def run_market_alerts(conn, cfg: BetaConfig, *, sender, clock, push_on: bool, pacer=None) -> dict:
    """Detect, decide, materialize and send market alerts; record and score corridors."""
    from .decision import build_decision
    from .decision_format import format_alert
    from .delivery import SENT, SendPacer, count_outcome, send_one
    from .latency import alert_source_at, class_summary, latency_field
    d = cfg.section("decision")
    m = d["market_alerts"]
    rep = {"detected": 0, "pushed": 0, "suppressed": 0, "materialized": 0, "sent": 0, "failed": 0,
           "unknown": 0, "throttled": 0, "expired": 0, "forecasts_recorded": 0, "forecasts_scored": 0}
    pacer = pacer if pacer is not None else SendPacer().set_preview(cfg, None)   # preview on: fail closed
    now = clock()
    cap: dict = {}
    block = await build_decision(conn, cfg, now=now, capture=cap, regime=await _regime(conn, cfg, now=now))
    b, closed = cap.get("bars"), cap.get("closed_1m") or []
    available = bool(block.get("available"))
    # a fresh tape, also when the history statistics are stale: personal price alerts and the release
    # alerts need only the price and the calendar, and past forecasts and claims are still scored
    if b is not None and block.get("price") is not None:
        cands = []
        if m["enabled"]:
            if available:
                cands += level_touch_candidates(cfg, block, b, closed, now=now,
                                                max_age=timedelta(minutes=int(m["touch_max_age_min"])),
                                                stats=cap.get("stats"))
            cands += detect_events(block, cap["calendar"], now=now,
                                   lead=timedelta(minutes=int(m["event_lead_min"])), stats=cap.get("stats"))
            last_move = await conn.last_market_push_ts(kind="move") if available else None
            if available and (last_move is None or now - last_move >= timedelta(minutes=int(m["move_cooldown_min"]))):
                cands += detect_move(block, b, closed, now=now, model=cap.get("model"))
            if push_on:
                active = await conn.fetch_active_price_alerts()
                touched = detect_price_alerts(active, b, closed, block=block, now=now,
                                              max_age=timedelta(minutes=int(m["touch_max_age_min"])))
                hit = {c["price_alert_pk"] for c in touched}       # a touch says it all: no approach after it
                cands += touched + detect_price_approaches([a for a in active if a["price_alert_pk"] not in hit],
                                                           block=block, now=now)
        if d["claim_journal"]:
            # the race landmarks first: a structural push links its T0 line to that record below
            rep["level_race"] = await _journal_race(conn, cfg, cap, now=now)
        await _race_lines_journaled_only(conn, cands)
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
            if d["claim_journal"] and c["kind"] == "level" and res != "DUPLICATE":
                await _journal_level_touch(conn, c, res, now=now)
        if d["forecast_tracking"]:
            rep["forecasts_recorded"] = await record_forecasts(conn, block, now=now)
            rep["forecasts_scored"] = (await score_forecasts(conn, b, closed, now=now))["scored"]
        if d["claim_journal"]:
            rep["claims"] = await _journal_hour(conn, cfg, block, cap, now=now)
    if d["signature_index"]:
        # owner-only research tooling (PRE_BETA_SCOPE_DECISION_V1 §7): reads stored states, never decides
        try:
            from .signatures import record_signatures
            rep["signatures"] = await record_signatures(conn, cfg, now=now, evidence=block.get("evidence"))
        except Exception as exc:  # noqa: BLE001 - the index never stops alerts or deliveries
            rep["signatures_error"] = type(exc).__name__
    ttl = cfg.delivery_ttl
    for a in await conn.fetch_undispatched_market_alerts(cfg["notifications"]["max_deliveries_per_run"]):
        rep["materialized"] += await conn.materialize_alert_deliveries(
            alert_pk=a["alert_pk"], kind=a["kind"], decision_ts=a["decision_ts"],
            target_user_pk=a["target_user_pk"], expired=(now - a["decision_ts"] > ttl), now=now)
    lat_summary = None
    for row in await conn.fetch_pending_alert_deliveries(cfg["notifications"]["max_deliveries_per_run"],
                                                         now=clock()):
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
        if row["kind"] in QUIET_KINDS and in_quiet_hours(cfg, row["decision_ts"], row.get("user_tz")):
            # sent to the participants who are awake; this one's own night (backlog C5)
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SUPPRESSED, now=now,
                                           suppression_reason="QUIET_HOURS")
            continue
        if row["kind"] in CAPPED_KINDS and await own_budget_spent(conn, row, cap=int(m["max_per_utc_day"]),
                                                                   outbox_kind="alert", alert_kinds=CAPPED_KINDS):
            # this participant already had their day's level and move alerts (their own date, review of #373)
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SUPPRESSED, now=now,
                                           suppression_reason="DAILY_CAP")
            continue
        if sender is None:
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_FAILED, now=now,
                                           error_summary="sender unavailable (no bot token)")
            rep["failed"] += 1
            continue
        if not pacer.may_send(row["chat_id"]):          # nothing is rendered for a row that waits
            pacer.deferred += 1
            continue
        lang = row.get("user_lang") or "ru"
        if lat_summary is None:
            lat_summary = await class_summary(conn, now)
        # the measured delay field for the push's delay line (backlog A4; the line is drawn by F1)
        lat = latency_field(row["kind"], alert_source_at(row["payload"]), now, lat_summary)
        from .i18n import render_tz
        with render_tz(row.get("user_tz")):            # the recipient's clock (C5)
            text = format_alert(row["kind"], {**row["payload"], "latency": lat}, lang)
            buttons = alert_buttons(row["kind"], row["payload"], lang, alert_pk=row["alert_pk"])
        outcome, _mid, sent_at = await send_one(conn, sender, pacer, did, chat_id=row["chat_id"], html=text,
                                                buttons=buttons, clock=clock)
        if outcome != SENT:
            count_outcome(rep, outcome)
            continue
        if row.get("user_pk") is not None:
            # detail = the alert kind (level / event / move / price): the measurement contract
            # keeps market alerts and personal /alert deliveries apart
            await conn.record_activity(user_pk=row["user_pk"], action="alert_delivered", lang=lang, at=sent_at,
                                       detail=row["kind"])
        rep["sent"] += 1
    return rep
