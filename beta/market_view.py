"""Shared market view builder (PRODUCT_FIRST_DECISION_V1 §3 row 1).

One assembly path for `/btc`, `/catchup` and the morning briefing:

    collect_status → context projection state → btc_view → horizons (1h/4h/24h)
    → D7 line (when enabled) → [catchup / brief: window summary + 1h/4h interpretation]

`/btc` gets exactly the payload it had before (same keys). `/catchup` and the
briefing add a `market` block. Rendering lives in `beta.formatter`; nothing here
writes text, and nothing here reads anything after the latest closed bucket.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

from .config import BetaConfig
from .state_tape import BUCKET, iso

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
                     d7_enabled: bool = False) -> dict:
    """The one view object every user surface renders."""
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
    if d7_enabled:
        from .regime_d7 import regime_for_status
        view["regime"] = await regime_for_status(conn, now=now, product_status=view.get("product_status") or "")
    if kind != "btc":
        events = await conn.fetch_episode_history(symbol=cfg.symbol, limit=_EVENT_HISTORY_LIMIT)
        view["kind"] = kind
        view["market"] = market_block(cfg, view, ctx["state"] if ctx else None, tape,
                                      window_hours=hours or CATCHUP_DEFAULT_HOURS, episodes=events)
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
    return {"as_of": as_of, "metrics": {b: m for b, m in hist}, "oi": oi}


def _horizons(cfg: BetaConfig, view: Mapping[str, Any], tape: Optional[Mapping[str, Any]]) -> dict:
    from .horizons import build_horizons, empty_horizons
    if tape is None:
        return empty_horizons()
    return build_horizons(cfg, as_of_bucket=tape["as_of"], metrics_by_bucket=tape["metrics"],
                          oi_by_boundary=tape["oi"])


def market_block(cfg: BetaConfig, view: Mapping[str, Any], state: Optional[Mapping[str, Any]],
                 tape: Optional[Mapping[str, Any]], *, window_hours: int, episodes) -> dict:
    """Window summary, events in the window and the 1h / 4h interpretation.

    Language-neutral; the interpretation is computed from the projection's own
    1h / 4h context readings at the same as-of bucket."""
    from .context import level_label
    from .horizons import _oi_for, data_through, rolling_24h_values, span_min_present
    from .interpretation import interpret, liquidation_episodes
    block: dict = {"version": MARKET_VIEW_VERSION, "window_hours": window_hours, "window": None,
                   "events": [], "interpretation": {}, "levels": {}, "complete": tape is not None}
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
        "volume_notional_usd": span["volume_notional_usd"] if span["volume_complete"] else None,
        "oi_change_pct": oi["oi_change_pct"],
    }
    start = end - timedelta(hours=window_hours)
    for row in episodes or ():
        trig = row.get("triggered_at")
        if trig is None or not (start <= trig <= end):
            continue
        block["events"].append({"event_type": row["event_type"], "opened_bucket": iso(row["opened_bucket"]),
                                "last_bucket": iso(row["last_bucket"]), "triggered_at": iso(trig),
                                "terminal_at": iso(row.get("terminal_at"))})
    block["events"].sort(key=lambda e: e["triggered_at"])
    liq = liquidation_episodes(state)
    for h in ("1h", "4h"):
        ctx = (state or {}).get(f"context_{h}")
        if ctx is not None and ctx.get("window_end") != iso(end):
            ctx = None                     # never interpret a reading of another bucket
        block["interpretation"][h] = interpret(cfg, ctx, horizon=h, liquidation_episodes=liq)
        pct = (ctx or {}).get("percentiles") or {}
        block["levels"][h] = {m: level_label(cfg, (pct.get(m) or {}).get("rank"), (pct.get(m) or {}).get("tier"))
                              for m in ("range_width_pct_median", "volume_notional_usd_sum")}
    return block
