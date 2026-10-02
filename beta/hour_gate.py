"""Product-level unusual-hour gate (PRODUCT_FIRST_DECISION_V1 §3 row 7, §3.1b).

Pure and deterministic. It reads ONE rolling-1h context reading of the projection
(`BETA_CONTEXT_1H_V2`) plus the liquidation-stress episodes the detector already
holds, and says whether the hour around a `TRIGGERED` detector episode is unusual
enough to push. It is not a detector: it never opens, closes or ranks episodes, and
it is evaluated inside the existing push policy only.

The rule, with no key of its own (the cut point is `context.label_high`):
- at least two of the three ranked 1h metrics are extreme:
  range rank >= label_high, volume rank >= label_high, and the SIGNED price move in
  either tail (rank >= label_high, or rank <= 1 - label_high);
- at least `min_venue_coverage` venues agree on the sign of the 1h price move;
- only mature ranks count.

The result is stored by value with the push decision (`beta_push_decisions.gate`):
what was known at the decision bucket, including the interpretation of the hour,
so the push text and the «Необычные часы» block of /catchup render the same facts.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from .config import LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT, BetaConfig
from .interpretation import interpret, price_agreement

GATE_VERSION = "BETA_HOUR_GATE_V1"
MIN_EXTREME_METRICS = 2            # fixed by the decision; not a config key
MATURE = "mature"

# statuses
QUALIFIED = "QUALIFIED"
CONTEXT_UNAVAILABLE = "CONTEXT_UNAVAILABLE"
IMMATURE = "IMMATURE"
NOT_UNUSUAL = "NOT_UNUSUAL"
VENUES_DISAGREE = "VENUES_DISAGREE"


def _rank(ctx: Mapping[str, Any], metric: str):
    p = (ctx.get("percentiles") or {}).get(metric) or {}
    if p.get("rank") is None or p.get("tier") != MATURE:
        return None
    return float(p["rank"])


def _liquidation_votes(snapshot: Optional[Mapping[str, Any]], event_type: str) -> Optional[dict]:
    """The per-venue liquidation votes of the decision bucket's own rule evaluation
    (the existing LIQUIDATION_STRESS evidence); None when it is not available."""
    ev = ((snapshot or {}).get("rule_evaluations") or {}).get(event_type) or {}
    detail = ev.get("detail") if isinstance(ev.get("detail"), Mapping) else ev
    voting = detail.get("voting") if isinstance(detail, Mapping) else None
    eligible = detail.get("eligible") if isinstance(detail, Mapping) else None
    if voting is None and eligible is None:
        return None
    return {"voting": list(voting or ()), "eligible": list(eligible or ())}


def evaluate_hour(cfg: BetaConfig, ctx: Optional[Mapping[str, Any]], *,
                  liquidation_episodes: Iterable[Mapping[str, Any]] = (),
                  snapshot: Optional[Mapping[str, Any]] = None) -> dict:
    """The gate for one rolling-1h reading. Never reads anything after the window."""
    out: dict = {"version": GATE_VERSION, "qualified": False, "status": CONTEXT_UNAVAILABLE,
                 "window_start": None, "window_end": None, "passed": {}, "venues_agree": None,
                 "venues": None, "values": {}, "interpretation": None, "liquidation": None}
    if not ctx:
        return out
    out["window_start"], out["window_end"] = ctx.get("window_start"), ctx.get("window_end")
    high = float(cfg.section("context")["label_high"])
    ranks = {m: _rank(ctx, m) for m in ("range_width_pct_median", "volume_notional_usd_sum",
                                         "price_move_pct_median")}
    out["values"] = {
        "price_move_pct": ctx.get("price_move_pct_median"),
        "range_width_pct": ctx.get("range_width_pct_median"),
        "volume_notional_usd": ctx.get("volume_notional_usd_sum"),
        "taker_delta_notional_usd": ctx.get("taker_delta_notional_usd_sum"),
        "oi_change_pct": ctx.get("oi_change_pct_median"),
        "oi_venues": list(ctx.get("oi_venues") or ()),
        "open": ctx.get("open_median"), "close": ctx.get("close_median"),
        "price_move_pct_by_venue": dict(ctx.get("price_move_pct_by_venue") or {}),
        "ranks": ranks,
    }
    agree, venues = price_agreement(ctx)
    out["venues_agree"], out["venues"] = agree, venues
    if any(r is None for r in ranks.values()):
        out["status"] = IMMATURE
        return out
    price_rank = ranks["price_move_pct_median"]
    passed = {
        "range": ranks["range_width_pct_median"] >= high,
        "volume": ranks["volume_notional_usd_sum"] >= high,
        "price": "up" if price_rank >= high else ("down" if price_rank <= 1.0 - high else None),
    }
    out["passed"] = passed
    extreme = int(passed["range"]) + int(passed["volume"]) + int(passed["price"] is not None)
    if extreme < MIN_EXTREME_METRICS:
        out["status"] = NOT_UNUSUAL
        return out
    if agree < cfg.min_venues:
        out["status"] = VENUES_DISAGREE
        return out
    out["status"], out["qualified"] = QUALIFIED, True
    res = interpret(cfg, ctx, horizon="1h", liquidation_episodes=liquidation_episodes)
    out["interpretation"] = {k: res[k] for k in ("kind", "key", "label", "liquidation_episode", "inputs")}
    if res.get("liquidation_episode") is not None:
        et = LIQUIDATION_STRESS_SHORT if res["key"] == "short_flush" else LIQUIDATION_STRESS_LONG
        out["liquidation"] = {"side": "short" if et == LIQUIDATION_STRESS_SHORT else "long",
                              "episode_id": res["liquidation_episode"],
                              **(_liquidation_votes(snapshot, et) or {})}
    return out


def is_qualified(gate: Optional[Mapping[str, Any]]) -> bool:
    return bool(gate and gate.get("qualified"))
