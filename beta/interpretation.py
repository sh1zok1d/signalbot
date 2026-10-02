"""Product interpretation of one 1h or 4h context window (PRODUCT_FIRST_DECISION_V1 §3.1).

Pure and deterministic. Input: one `context_1h(..., horizon=...)` reading from the
context projection, plus the liquidation-stress detector episodes the projection
already holds. Output: a language-neutral result; `interpretation_text` renders it.

This is product evidence, not a research claim. A label describes what the window
looked like. It never says what comes next. Every inferred label reads "похоже на";
when the observations conflict or are missing, the result is a factual fallback
without a causal label. 24h has no interpretation label.

Cut points are the existing context labels: "up" = rank >= label_elevated (0.80),
"down" = rank <= tail_display_max (0.20), otherwise "flat"; the same bands for
price, OI change and taker delta. Only mature ranks are read.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

from .config import LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT, BetaConfig
from .i18n import assert_descriptive, t
from .state_tape import BUCKET

INTERPRETATION_VERSION = "BETA_INTERPRETATION_V1"
INTERPRETED_HORIZONS = ("1h", "4h")
MATURE = "mature"

# kinds
INTERPRETED = "INTERPRETED"            # an inferred "похоже на" label (or a confirmed "вынос")
FACTUAL = "FACTUAL"                    # observations conflict or are incomplete: no causal label
COMPRESSION = "COMPRESSION"
NORMAL = "NORMAL"
VENUES_DIVERGE = "VENUES_DIVERGE"      # price agreement below min_venue_coverage
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
DATA_MISSING = "DATA_MISSING"

# inferred rows: (price, oi, taker) -> label; conflict fallback is the factual pair
_ROWS = {
    ("up", "down"): ("short_exit", "up", "up_oi_down"),
    ("up", "up"): ("long_build", "up", "up_oi_up"),
    ("down", "up"): ("short_build", "down", "down_oi_up"),
    ("down", "down"): ("long_exit", "down", "down_oi_down"),
}
# escalation: inferred label -> (confirming liquidation-stress type, escalated label)
_FLUSH = {"short_exit": (LIQUIDATION_STRESS_SHORT, "short_flush"),
          "long_exit": (LIQUIDATION_STRESS_LONG, "long_flush")}

LABEL_KEYS = {
    "short_exit": "interp_short_exit", "long_build": "interp_long_build",
    "short_build": "interp_short_build", "long_exit": "interp_long_exit",
    "short_flush": "interp_short_flush", "long_flush": "interp_long_flush",
    "compression": "interp_compression", "compression_oi_na": "interp_compression_oi_na",
    "normal": "interp_normal",
    "up_oi_down": "fact_up_oi_down", "up_oi_up": "fact_up_oi_up",
    "down_oi_up": "fact_down_oi_up", "down_oi_down": "fact_down_oi_down",
    "up_oi_na": "fact_up_oi_na", "down_oi_na": "fact_down_oi_na",
    "up": "fact_up", "down": "fact_down",
    "venues_diverge": "interp_venues_diverge", "insufficient": "interp_insufficient",
    "missing": "interp_missing",
}


def definition(cfg: BetaConfig) -> dict:
    c = cfg.section("context")
    return {"version": INTERPRETATION_VERSION, "horizons": list(INTERPRETED_HORIZONS),
            "up_rank_min": float(c["label_elevated"]), "down_rank_max": float(c["tail_display_max"]),
            "compression_range_rank_max": float(c["tail_display_max"]),
            "requires": ["price", "oi", "taker"], "min_price_venue_agreement": cfg.min_venues,
            "flush_requires": "a LIQUIDATION_STRESS episode of the matching side overlapping the window",
            "never": "future direction"}


def _band(cfg: BetaConfig, ctx: Mapping[str, Any], metric: str) -> tuple:
    """(band, status): band in up/down/flat, or None with status MISSING / IMMATURE."""
    value = ctx.get(metric)
    p = (ctx.get("percentiles") or {}).get(metric) or {}
    if value is None or p.get("rank") is None:
        return None, "MISSING"
    if p.get("tier") != MATURE:
        return None, "IMMATURE"
    c = cfg.section("context")
    rank = float(p["rank"])
    if rank >= float(c["label_elevated"]):
        return "up", "OK"
    if rank <= float(c["tail_display_max"]):
        return "down", "OK"
    return "flat", "OK"


def price_agreement(ctx: Mapping[str, Any]) -> tuple:
    """(venues agreeing with the sign of the median move, venues with a move)."""
    by = ctx.get("price_move_pct_by_venue") or {}
    med = ctx.get("price_move_pct_median")
    if med is None or not by:
        return 0, len(by)
    sign = (med > 0) - (med < 0)
    return sum(1 for v in by.values() if ((v > 0) - (v < 0)) == sign), len(by)


def liquidation_episodes(state: Optional[Mapping[str, Any]]) -> list:
    """The projection's open and most recently ended LIQUIDATION_STRESS episodes."""
    if not state:
        return []
    out = []
    for group in ("open", "last_ended"):
        for et, ep in (state.get(group) or {}).items():
            if et in (LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT):
                out.append(ep)
    return out


def _confirming(episodes: Iterable[Mapping[str, Any]], event_type: str, start: datetime,
                end: datetime) -> Optional[str]:
    """Id of a triggered episode of `event_type` whose qualifying buckets
    [opened_bucket, last_bucket + 5m) intersect the window [start, end)."""
    for ep in episodes:
        if ep.get("event_type") != event_type or not ep.get("triggered_at") or not ep.get("opened_bucket"):
            continue
        first = datetime.fromisoformat(ep["opened_bucket"])
        last = datetime.fromisoformat(ep.get("last_bucket") or ep["opened_bucket"])
        if first < end and last + BUCKET > start:
            return ep.get("episode_id")
    return None


def interpret(cfg: BetaConfig, ctx: Optional[Mapping[str, Any]], *, horizon: str,
              liquidation_episodes: Iterable[Mapping[str, Any]] = ()) -> dict:
    """One window's interpretation. `ctx` is the projection's context reading for
    `horizon`. Never reads anything after the window's end."""
    if horizon not in INTERPRETED_HORIZONS:
        raise ValueError(f"no interpretation label for horizon {horizon!r}")
    base = {"version": INTERPRETATION_VERSION, "horizon": horizon, "label": None, "kind": DATA_MISSING,
            "key": "missing", "liquidation_episode": None, "inputs": {}}
    if not ctx:
        return base
    price, price_st = _band(cfg, ctx, "price_move_pct_median")
    oi, oi_st = _band(cfg, ctx, "oi_change_pct_median")
    taker, taker_st = _band(cfg, ctx, "taker_delta_notional_usd_sum")
    rng, rng_st = _band(cfg, ctx, "range_width_pct_median")
    agree, venues = price_agreement(ctx)
    base["inputs"] = {"price": price or price_st, "oi": oi or oi_st, "taker": taker or taker_st,
                      "range": rng or rng_st, "price_venues_agree": agree, "price_venues": venues,
                      "window_start": ctx.get("window_start"), "window_end": ctx.get("window_end")}

    def done(kind, key, label=None, episode=None):
        return {**base, "kind": kind, "key": key, "label": label, "liquidation_episode": episode}

    if price_st == "MISSING":
        return done(DATA_MISSING, "missing")
    if agree < cfg.min_venues:
        return done(VENUES_DIVERGE, "venues_diverge")
    if price_st == "IMMATURE":
        return done(INSUFFICIENT_HISTORY, "insufficient")

    if price in ("up", "down"):
        if oi is None:                                     # OI missing, immature or < 2 venues
            return done(FACTUAL, f"{price}_oi_na")
        row = _ROWS.get((price, oi))
        if row is None:                                    # OI flat: the price fact only
            return done(FACTUAL, price)
        label, need, fallback = row
        if taker != need:                                  # taker missing, flat or opposite
            return done(FACTUAL, fallback)
        if label in _FLUSH:
            et, flush = _FLUSH[label]
            start, end = ctx.get("window_start"), ctx.get("window_end")
            ep_id = None if not (start and end) else _confirming(
                liquidation_episodes, et, datetime.fromisoformat(start), datetime.fromisoformat(end))
            if ep_id is not None:
                return done(INTERPRETED, flush, flush, ep_id)
        return done(INTERPRETED, label, label)

    # price flat
    if rng_st == "MISSING":
        return done(DATA_MISSING, "missing")
    if rng_st == "IMMATURE":
        return done(INSUFFICIENT_HISTORY, "insufficient")
    if rng == "down":
        if oi_st != "OK":
            return done(COMPRESSION, "compression_oi_na", "compression")
        if oi != "down":
            return done(COMPRESSION, "compression", "compression")
    return done(NORMAL, "normal", "normal")


def interpretation_text(result: Mapping[str, Any], lang: str = "ru") -> str:
    return assert_descriptive(t(lang, LABEL_KEYS[result["key"]]), lang)
