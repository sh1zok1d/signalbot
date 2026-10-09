"""Shared market view builder (PRODUCT_FIRST_DECISION_V1 §3 row 1).

One assembly path for `/btc`, `/catchup` and the morning briefing:

    collect_status → context projection state → btc_view → horizons (1h/4h/24h)
    → D7 line (when enabled) → [catchup / brief: window summary + 1h/4h interpretation]
    → decision support (corridor, levels, events, «после похожих»; PRODUCT_DECISION_V2)

`/btc` keeps the payload it had before, plus the decision and derivatives blocks
(each left out or marked unavailable on a failure). `/catchup` and the briefing add a
`market` block. Rendering lives in `beta.formatter`; nothing here
writes text, and nothing here reads anything after the latest closed bucket.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

from .config import BetaConfig
from .state_tape import BUCKET, iso

logger = logging.getLogger("beta.market_view")

VIEW_KINDS = ("btc", "catchup", "brief")
CATCHUP_DEFAULT_HOURS = 8
CATCHUP_MIN_HOURS = 1
CATCHUP_MAX_HOURS = 24
BRIEF_WINDOW_HOURS = CATCHUP_DEFAULT_HOURS
MARKET_VIEW_VERSION = "BETA_MARKET_VIEW_V1"
_FAIL = ("DATA STALE", "DATA DEGRADED")
_EVENT_HISTORY_LIMIT = 50


def maturity_days(cfg: BetaConfig) -> float:
    """The percentile core's maturity span (Stage-2 confidence tiers), not a UI constant."""
    from common.stage2_config import Stage2Config
    tiers = Stage2Config.load().resolve(cfg.symbol)["percentiles"]["confidence_tiers"]
    return float(tiers["building_below_days"])


def parse_catchup_hours(args: Optional[str]) -> Optional[int]:
    """`/catchup` → default; `/catchup N` → N in [1, 24]; anything else → None."""
    text = (args or "").strip().lower().rstrip("hч")
    if not text:
        return CATCHUP_DEFAULT_HOURS
    if not text.isdigit():
        return None
    n = int(text)
    return n if CATCHUP_MIN_HOURS <= n <= CATCHUP_MAX_HOURS else None


async def build_view(conn, cfg: BetaConfig, *, now: datetime, kind: str = "btc",
                     window_hours: Optional[int] = None, maturity_days: float,
                     d7_enabled: bool = False, decision: bool = True) -> dict:
    """The one view object every user surface renders. `decision` adds the decision-support
    block (corridor, levels, events, «после похожих»; PRODUCT_DECISION_V2) by value."""
    if kind not in VIEW_KINDS:
        raise ValueError(f"unknown view kind {kind!r}")
    from .admin import collect_status
    from .context import btc_view, episodization_digest
    from .readiness import readiness
    st = await collect_status(conn, cfg, now)
    ctx = await conn.fetch_latest_context_state(symbol=cfg.symbol, episodization_digest=episodization_digest(cfg))
    rd = readiness(cfg, st["latest"], maturity_days=maturity_days)
    view = btc_view(cfg, product=st["status"], state=ctx["state"] if ctx else None,
                    state_digest_value=ctx["state_digest"] if ctx else None, now=now, readiness=rd,
                    detector_open_ids=[e.public_id for e in st["open_episodes"]])
    hours = window_hours if kind != "btc" else None
    tape = await _tape_and_oi(conn, cfg, view, window_hours=hours)
    view["horizons"] = _horizons(cfg, view, tape)
    view["derivatives"] = await _derivatives(conn, view, tape, now=now)
    if d7_enabled:
        from .regime_d7 import regime_for_status
        view["regime"] = await regime_for_status(conn, now=now, product_status=view.get("product_status") or "")
    if kind != "btc":
        hours = hours or CATCHUP_DEFAULT_HOURS
        qualified = []
        if tape is not None:
            from .horizons import data_through
            end = data_through(tape["as_of"])
            qualified = await conn.fetch_qualified_hours(symbol=cfg.symbol, start=end - timedelta(hours=hours), end=end)
        view["kind"] = kind
        view["market"] = market_block(cfg, view, ctx["state"] if ctx else None, tape,
                                      window_hours=hours, qualified=qualified)
    if decision:
        from .decision import build_decision
        view["decision"] = await build_decision(conn, cfg, now=now, market=view.get("market"),
                                                regime=view.get("regime"))
    return view


async def persist_view(conn, view: Mapping[str, Any], *, now: datetime, text: str, lang: str,
                       kind: str = "btc") -> int:
    import hashlib
    from .state_tape import sha256_json
    return await conn.insert_btc_view(
        requested_at=now,
        as_of_bucket=datetime.fromisoformat(view["as_of_bucket"]) if view.get("as_of_bucket") else None,
        context_state_digest=view["context_state_digest"], episodization_version=view["episodization_version"],
        episodization_digest=view["episodization_digest"], payload=view, payload_digest=sha256_json(view),
        rendered_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(), rendered_html=text, lang=lang,
        kind=kind)


async def _tape_and_oi(conn, cfg: BetaConfig, view: Mapping[str, Any], *,
                       window_hours: Optional[int]) -> Optional[dict]:
    """One tape-history read and one OI as-of read for every horizon of the view.

    Tape history covers the 24h window plus 30 prior days, each of which needs its
    own 24h lookback, so the fetch starts 31 days and 24h before data-through."""
    from .horizons import data_through, oi_boundaries
    if view.get("product_status") in _FAIL or not view.get("as_of_bucket"):
        return None
    as_of = datetime.fromisoformat(view["as_of_bucket"])
    latest = await conn.fetch_latest_live_tape(symbol=cfg.symbol)
    calc = (((latest or {}).get("snapshot") or {}).get("identity") or {}).get("calculation_version")
    if not calc:
        return None
    hist = await conn.fetch_tape_history(
        symbol=cfg.symbol, market_type=cfg.market_type, timeframe=cfg.timeframe,
        calculation_version=calc, state_schema_versions=(cfg.state_schema_version,),
        start=as_of - timedelta(days=31, hours=24), end=as_of + BUCKET)
    bounds = list(oi_boundaries(as_of))
    if window_hours:
        start = data_through(as_of) - timedelta(hours=window_hours)
        if start not in bounds:
            bounds.append(start)
    oi = await conn.fetch_open_interest_asof(symbol=cfg.symbol, exchanges=cfg.exchanges, boundaries=bounds)
    # each venue's newest live funding with its time: the age bound of «Funding сейчас» (D3, R3)
    ff = getattr(conn, "fetch_funding_latest", None)
    from .horizons import FUNDING_MAX_AGE
    through = data_through(as_of)
    funding = None if ff is None else await ff(symbol=cfg.symbol, exchanges=cfg.exchanges, at=through,
                                               since=through - FUNDING_MAX_AGE)
    from .liq_mapping import okx_liq_shown, without_okx_liq
    metrics = {b: m for b, m in hist}
    if not okx_liq_shown((latest.get("snapshot") or {}).get("percentiles"), enabled=cfg.okx_liquidations_enabled):
        metrics = {b: without_okx_liq(m) for b, m in metrics.items()}
    return {"as_of": as_of, "metrics": metrics, "oi": oi, "funding": funding}


def _horizons(cfg: BetaConfig, view: Mapping[str, Any], tape: Optional[Mapping[str, Any]]) -> dict:
    from .horizons import build_horizons, empty_horizons
    if tape is None:
        return empty_horizons()
    from .liq_mapping import mark_okx_lower_bound
    return mark_okx_lower_bound(build_horizons(cfg, as_of_bucket=tape["as_of"], metrics_by_bucket=tape["metrics"],
                                               oi_by_boundary=tape["oi"], funding_latest=tape.get("funding")))


async def _derivatives(conn, view: Mapping[str, Any], tape: Optional[Mapping[str, Any]], *,
                       now: datetime) -> Optional[dict]:
    """OI change, funding and long/short beside their «обычно» (backlog G2; beta/derivatives.py). Like the
    decision block it never breaks a view: any failure leaves the block out and the 24h lines as before."""
    from .decision import fresh_stats
    from .derivatives import derivatives_block, funding_typical
    from .horizons import data_through
    if tape is None:
        return None
    try:
        stats = await fresh_stats(conn, now=now)            # the OI «обычно» never from stale statistics (A2)
        return derivatives_block(horizons=view["horizons"], funding=funding_typical(tape["metrics"], tape["as_of"]),
                                 oi_stats=((stats or {}).get("derivatives") or {}).get("oi_24h"),
                                 long_short=await conn.long_short_summary(as_of=data_through(tape["as_of"])))
    except Exception as exc:  # noqa: BLE001 - context lines must never break a view
        logger.warning("derivatives block failed: %s", type(exc).__name__)
        return None


UNUSUAL_HOURS_MAX = 3
_UNUSUAL_MERGE = timedelta(minutes=60)        # one entry per hour, as one push per hour


def unusual_hours(qualified, *, start: datetime, end: datetime) -> list:
    """The «Необычные часы» entries of a window from the push decisions whose gate
    passed (decision §3.1b.3): chronological, one per hour (decisions inside 60 minutes
    of the kept one describe the same hour), at most UNUSUAL_HOURS_MAX. Delivery-side
    suppression is carried as a fact, never as a filter."""
    out, last = [], None
    for row in sorted(qualified or (), key=lambda r: r["decision_ts"]):
        ts = row["decision_ts"]
        gate = row.get("gate") or {}
        ws = gate.get("window_start")
        wstart = datetime.fromisoformat(ws) if ws else ts - timedelta(hours=1)
        if wstart < start - _UNUSUAL_MERGE or ts > end:
            continue
        if last is not None and ts - last < _UNUSUAL_MERGE:
            continue
        out.append({"decision_ts": iso(ts), "decision": row.get("decision"), "decision_id": row.get("decision_id"),
                    "suppression_reason": row.get("suppression_reason"), "gate": gate})
        last = ts
    return out[:UNUSUAL_HOURS_MAX]


def market_block(cfg: BetaConfig, view: Mapping[str, Any], state: Optional[Mapping[str, Any]],
                 tape: Optional[Mapping[str, Any]], *, window_hours: int, qualified=()) -> dict:
    """Window summary, the unusual hours of the window and the 1h / 4h interpretation
    with the values that stand beside it.

    Language-neutral; the interpretation is computed from the projection's own
    1h / 4h context readings at the same as-of bucket."""
    from .context import level_label
    from .horizons import _oi_for, data_through, rolling_24h_values, span_min_present
    from .interpretation import interpret, liquidation_episodes
    block: dict = {"version": MARKET_VIEW_VERSION, "window_hours": window_hours, "window": None,
                   "unusual_hours": [], "interpretation": {}, "levels": {}, "values": {},
                   "history_days": None, "ranks_immature": False, "complete": tape is not None}
    if tape is None:
        return block
    as_of = tape["as_of"]
    end = data_through(as_of)
    n = window_hours * 12
    span = rolling_24h_values(cfg, tape["metrics"], as_of, n=n, min_present=span_min_present(n))
    oi = _oi_for(cfg, end - timedelta(hours=window_hours), end, tape["oi"])
    block["window"] = {
        "window_start": iso(span["buckets"][0]), "window_end": iso(end),
        "price_complete": span["price_complete"],
        "price_move_pct": span["price_move_pct"] if span["price_complete"] else None,
        "range_width_pct": span["range_width_pct"] if span["price_complete"] else None,
        "high": span["high"] if span["price_complete"] else None,
        "low": span["low"] if span["price_complete"] else None,
        "open": span["open"] if span["price_complete"] else None,
        "close": span["close"] if span["price_complete"] else None,
        "volume_notional_usd": span["volume_notional_usd"] if span["volume_complete"] else None,
        "oi_change_pct": oi["oi_change_pct"],
    }
    start = end - timedelta(hours=window_hours)
    block["unusual_hours"] = unusual_hours(qualified, start=start, end=end)
    liq = liquidation_episodes(state)
    for h in ("1h", "4h"):
        ctx = (state or {}).get(f"context_{h}")
        if ctx is not None and ctx.get("window_end") != iso(end):
            ctx = None                     # never interpret a reading of another bucket
        block["interpretation"][h] = interpret(cfg, ctx, horizon=h, liquidation_episodes=liq)
        pct = (ctx or {}).get("percentiles") or {}
        block["levels"][h] = {m: level_label(cfg, (pct.get(m) or {}).get("rank"), (pct.get(m) or {}).get("tier"))
                              for m in ("range_width_pct_median", "volume_notional_usd_sum")}
        block["values"][h] = {
            "price_move_pct": (ctx or {}).get("price_move_pct_median"),
            "oi_change_pct": (ctx or {}).get("oi_change_pct_median"),
            "taker_delta_notional_usd": (ctx or {}).get("taker_delta_notional_usd_sum"),
            "range_width_pct": (ctx or {}).get("range_width_pct_median"),
            "oi_venues": list((ctx or {}).get("oi_venues") or ()),
            "price_move_pct_by_venue": dict((ctx or {}).get("price_move_pct_by_venue") or {}),
        }
        if h == "1h":
            p = pct.get("price_move_pct_median") or {}
            if p.get("sample_size") is not None:
                block["history_days"] = int(p["sample_size"]) // 288
            block["ranks_immature"] = ctx is not None and p.get("tier") != "mature"
    return block
