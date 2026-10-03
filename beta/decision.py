"""Live decision-support block for every user surface (PRODUCT_DECISION_V2 §2).

One function, `build_decision`, assembles what /btc, /catchup, the morning briefing, /levels,
/risk and /events render:

- the corridor for 1h / 4h / 24h and the typical move (range model, newest statistics row);
- the nearest level zones above and below with their distance and the chance to reach them
  within 4h / 24h, and the history of the first touch for level types that have it;
- the scheduled events of the next 24h with how big such hours / days were;
- «что было после похожих» for the current 1h / 4h labels;
- where the corridor's own track record stands (live accuracy is read separately).

Inputs: Binance history (`beta_hist_bars_5m`) up to yesterday, the Stage-1 Binance 1m klines
for the tail (read-only), Stage-1 liquidations of the last 24h (read-only), the calendar file
and the newest `beta_hist_stats` row. Bars are used only after they closed. When the live tail
is stale nothing forward-looking is shown (fail closed). The block is language-neutral and
JSON-safe; it is stored by value with the view.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from .config import BetaConfig
from .hist_series import (BAR_MS, aggregate_1m, bars_from_rows, floor_bar, from_ms, merge_rows, to_ms)

logger = logging.getLogger("beta.decision")

DECISION_VERSION = "BETA_DECISION_V1"
LIVE_EXCHANGE = "binance"
LOOKBACK_DAYS = 70
LIVE_TAIL_DAYS = 35
STALE_AFTER = timedelta(minutes=10)
STATS_RELOAD_S = 300
EVENTS_AHEAD_H = 24
SHOWN_EVENT_KINDS = ("CPI", "FOMC", "EXPIRY_MONTHLY", "EXPIRY_QUARTERLY")

_cache: dict = {"pk": None, "payload": None, "checked": None}


async def latest_stats(conn, *, now: datetime) -> Optional[dict]:
    """The newest statistics row, cached per process; reloaded when a newer row exists."""
    checked = _cache.get("checked")
    if checked is not None and (now - checked).total_seconds() < STATS_RELOAD_S and _cache["payload"] is not None:
        return _cache["payload"]
    meta = await conn.fetch_latest_hist_stats_meta()
    _cache["checked"] = now
    if meta is None:
        _cache.update(pk=None, payload=None)
        return None
    if meta["stats_pk"] != _cache.get("pk"):
        row = await conn.fetch_latest_hist_stats()
        _cache["pk"] = row["stats_pk"]
        _cache["payload"] = {**row["payload"], "_stats_pk": row["stats_pk"],
                             "_built_at": row["built_at"].isoformat()}
    return _cache["payload"]


def reset_cache() -> None:
    _cache.update(pk=None, payload=None, checked=None)


async def load_live_bars(conn, cfg: BetaConfig, *, now: datetime, days: int = LOOKBACK_DAYS,
                         capture: Optional[dict] = None):
    """(5m grid of closed bars, last 1m close, its open time). History up to its end, then the
    Stage-1 Binance 1m tail aggregated to complete 5m bars."""
    start = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    hist = await conn.fetch_hist_bars(start=start, end=now)
    tail_start = start
    if hist:
        tail_start = max(start, from_ms(int(hist[-1]["open_time_ms"]) + BAR_MS))
    tail_start = max(tail_start, now - timedelta(days=LIVE_TAIL_DAYS))
    live = await conn.fetch_live_klines_1m(exchange=LIVE_EXCHANGE, symbol=cfg.symbol, start=tail_start, end=now)
    from .history_data import in_protected_window
    live = [r for r in live if not in_protected_window(to_ms(r["ts"]))]
    price, price_ts = None, None
    closed_1m = [r for r in live if r["ts"] + timedelta(minutes=1) <= now]
    if closed_1m:
        price, price_ts = float(closed_1m[-1]["close"]), closed_1m[-1]["ts"]
    end_ms = floor_bar(to_ms(now))                     # the current 5m bar is still open
    five = [r for r in aggregate_1m(closed_1m) if r["open_time_ms"] + BAR_MS <= end_ms]
    rows = merge_rows(hist, five)
    b = bars_from_rows(rows, start_ms=to_ms(start), end_ms=end_ms)
    if capture is not None:
        capture["closed_1m"] = closed_1m
    return b, price, price_ts


def _round(x, nd=6):
    return None if x is None else round(float(x), nd)


def _zone_out(z: Mapping[str, Any], *, model, fc, levels_stats, price: float, side: int) -> dict:
    from .levels import stat_type_for
    from .rangecast import touch_probability
    dist = abs(z["distance_pct"])
    touch = {}
    for h in ("4h", "24h"):
        hz = (fc or {}).get("horizons", {}).get(h)
        if model is not None and hz:
            touch[h] = touch_probability(model, h, hz["scale_pct"], dist)
    hist = None
    for m in z["members"]:
        st = stat_type_for(m["kind"], side)
        rec = ((levels_stats or {}).get("types") or {}).get(st) if st else None
        if rec and rec.get("real", {}).get("n"):
            hist = {"type": st, "kind": m["kind"], **{k: rec[k] for k in ("real", "control", "verdicts")}}
            break
    members = [{"kind": m["kind"], "price": _round(m["price"], 2),
                **({"notional_usd": _round(m.get("notional_usd"), 0)} if m.get("notional_usd") else {}),
                **({"major": True} if m.get("major") else {})} for m in z["members"]]
    return {"low": _round(z["low"], 2), "high": _round(z["high"], 2), "edge": _round(z["edge"], 2),
            "distance_pct": _round(z["distance_pct"], 4), "kinds": list(z["kinds"]), "members": members,
            "touch": {h: _round(p, 4) for h, p in touch.items()}, "history": hist}


async def build_decision(conn, cfg: BetaConfig, *, now: datetime,
                         market: Optional[Mapping[str, Any]] = None,
                         capture: Optional[dict] = None) -> dict:
    """Never raises: any failure yields an unavailable block with the error type. `capture`
    (market alerts, forecast tracking) receives the bars, the closed 1m tail, the model and
    the calendar the block was built from."""
    from .history_stats import json_safe
    try:
        block = await _build(conn, cfg, now=now, market=market, capture=capture)
    except Exception as exc:  # noqa: BLE001 - decision support must never break a view
        logger.warning("decision block failed: %s", type(exc).__name__)
        block = {"version": DECISION_VERSION, "available": False, "reason": "ERROR",
                 "error_type": type(exc).__name__}
    return json_safe(block)


async def _build(conn, cfg: BetaConfig, *, now: datetime, market: Optional[Mapping[str, Any]],
                 capture: Optional[dict] = None) -> dict:
    from .analogues import lookup
    from .calendar_events import event_times_ms, load_calendar, upcoming
    from .levels import compute_levels, merge_zones, nearest_zones
    from .rangecast import forecast
    block: dict = {"version": DECISION_VERSION, "available": False, "reason": None, "venue": LIVE_EXCHANGE,
                   "as_of": now.isoformat()}
    stats = await latest_stats(conn, now=now)
    model = (stats or {}).get("range_model")
    if stats is not None:
        block["stats"] = {"stats_pk": stats.get("_stats_pk"), "built_at": stats.get("_built_at"),
                          "data_from_ms": (stats.get("data") or {}).get("from_ms"),
                          "data_to_ms": (stats.get("data") or {}).get("to_ms")}
    b, price, price_ts = await load_live_bars(conn, cfg, now=now, capture=capture)
    if capture is not None:
        capture.update(bars=b, stats=stats, model=model)
    if price is None or price_ts is None or now - price_ts > STALE_AFTER:
        block["reason"] = "DATA_STALE"
        block["price_ts"] = price_ts.isoformat() if price_ts else None
        return block
    block["price"] = price
    block["price_ts"] = price_ts.isoformat()
    cal = load_calendar()
    events = event_times_ms(cal)
    fc = forecast(model, b, price=price, events=events) if model else None
    if capture is not None:
        capture.update(calendar=cal, events=events, forecast=fc)
    if fc is not None:
        block["corridor"] = {"coverage": fc["coverage"], "anchor_close_ms": fc["anchor_close_ms"],
                             "horizons": fc["horizons"]}
        cal_rep = model.get("calibration") or {}
        block["corridor"]["holdout"] = {h: {"coverage_realized": c.get("coverage_realized"),
                                            "n_days": c.get("n_days"), "from_ms": c.get("holdout_from_ms"),
                                            "to_ms": c.get("holdout_to_ms")} for h, c in cal_rep.items()}
    liq = await conn.fetch_liquidations(symbol=cfg.symbol, exchanges=cfg.exchanges,
                                        start=now - timedelta(hours=24), end=now)
    now_ms = to_ms(now)
    lv = compute_levels(b, now_ms=now_ms, price=price, liquidations=liq)
    reach = ((fc or {}).get("horizons", {}).get("24h") or {}).get("half_width_pct")
    near = nearest_zones(merge_zones(lv, price=price), price=price, reach_pct=reach)
    lstats = (stats or {}).get("levels")
    block["levels"] = {
        "above": [_zone_out(z, model=model, fc=fc, levels_stats=lstats, price=price, side=+1) for z in near["above"]],
        "below": [_zone_out(z, model=model, fc=fc, levels_stats=lstats, price=price, side=-1) for z in near["below"]],
        "at": _zone_out(near["at"], model=model, fc=fc, levels_stats=lstats, price=price,
                        side=+1 if near["at"]["mid"] >= price else -1) if near["at"] else None,
        "all": [{"kind": x["kind"], "price": _round(x["price"], 2)} for x in lv],
    }
    ev_stats = ((stats or {}).get("events") or {}).get("kinds") or {}
    block["events"] = [{"kind": e["kind"], "at": e["at"].isoformat(), "stats": ev_stats.get(e["kind"])}
                       for e in upcoming(cal, now=now, hours=EVENTS_AHEAD_H) if e["kind"] in SHOWN_EVENT_KINDS]
    interp = (market or {}).get("interpretation") or {}
    ana = (stats or {}).get("analogues")
    block["analogues"] = {}
    for w in ("1h", "4h"):
        res = interp.get(w) or {}
        card = lookup(ana, w, res.get("key"))
        if card is not None:
            block["analogues"][w] = card
    block["available"] = True
    return block


def corridor_for_record(block: Mapping[str, Any]) -> list:
    """(horizon, lower, upper, anchor price, coverage) of a block, for forecast tracking."""
    c = block.get("corridor") or {}
    out = []
    for h, hz in (c.get("horizons") or {}).items():
        out.append({"horizon": h, "lower": hz["lower"], "upper": hz["upper"], "price": block.get("price"),
                    "coverage": c.get("coverage")})
    return out
