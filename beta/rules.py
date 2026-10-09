"""BETA_EVENT_RULES_V1 — pure, deterministic, descriptive per-bucket rule evaluation.

These are descriptive operational rules, NOT validated market hypotheses and not
trading signals. Input: one by-value tape snapshot (+ the previous contiguous
bucket's evaluations for streaks). Output: per event type one RuleEvaluation with
status QUALIFIES / NOT_QUALIFIES / NOT_EVALUABLE. NOT_EVALUABLE is an evaluation
result, never an episode lifecycle state. Every threshold comes from BetaConfig.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

from .config import (
    BetaConfig, EVENT_TYPES, LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT,
    POSITION_BUILDUP_COMPRESSION, PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP,
    TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL)
from .models import NOT_EVALUABLE, NOT_QUALIFIES, QUALIFIES, RuleEvaluation
from .state_tape import metric_key

MATURE = "mature"


def _pct(snapshot: Mapping[str, Any], key: str):
    """(rank, reason) — rank only when the percentile is present AND mature."""
    p = (snapshot.get("percentiles") or {}).get(key)
    if p is None:
        return None, f"PERCENTILE_MISSING:{key}"
    if p.get("value") is None or p.get("rank") is None:
        return None, f"VALUE_UNAVAILABLE:{key}"
    if p.get("tier") != MATURE:
        return None, f"PERCENTILE_NOT_MATURE:{key}:{p.get('tier')}"
    return float(p["rank"]), None


def _families_usable(snapshot, families) -> Optional[str]:
    fams = snapshot.get("families") or {}
    for f in families:
        if not (fams.get(f) or {}).get("usable"):
            return f"FAMILY_UNUSABLE:{f}"
    return None


def _base_gate(snapshot) -> Optional[str]:
    if not snapshot.get("materialized"):
        return "NOT_MATERIALIZED"
    if snapshot.get("stale_barrier"):
        return "STALE_BARRIER"
    if not snapshot.get("evaluation_fresh"):
        return "EVALUATION_NOT_FRESH"
    return None


def _threshold_rule(snapshot, families, checks):
    """checks: [(metric, op, threshold)] with op in {'<=','>='}."""
    reason = _base_gate(snapshot) or _families_usable(snapshot, families)
    if reason:
        return NOT_EVALUABLE, reason, {}
    ranks = {}
    for metric, _op, _thr in checks:
        rank, why = _pct(snapshot, metric_key(None, metric))
        if why:
            return NOT_EVALUABLE, why, {}
        ranks[metric] = rank
    ok = all((ranks[m] <= t) if op == "<=" else (ranks[m] >= t) for m, op, t in checks)
    return (QUALIFIES if ok else NOT_QUALIFIES), ("CONDITION_MET" if ok else "CONDITION_NOT_MET"), \
        {"ranks": ranks}


def _liquidation_rule(snapshot, cfg: BetaConfig, side_field: str):
    r = cfg.rule("LIQUIDATION_STRESS")
    if not r["enabled"]:
        return NOT_EVALUABLE, "RULE_DISABLED", {}
    reason = _base_gate(snapshot)
    if reason:
        return NOT_EVALUABLE, reason, {}
    venues = snapshot.get("venues") or {}
    eligible, votes, why_not = [], [], {}
    for ex in cfg.exchanges:
        v = venues.get(ex) or {}
        if ex == "okx" and not cfg.okx_liquidations_enabled:
            why_not[ex] = "OKX_LIQUIDATIONS_EXCLUDED"       # decision (d): never a vote, whatever its maturity
            continue
        if not v.get("declared_available"):
            why_not[ex] = "FEED_NOT_DECLARED_AVAILABLE"
            continue
        if not v.get("heartbeat_healthy"):
            why_not[ex] = "HEARTBEAT_UNHEALTHY"
            continue
        rank, why = _pct(snapshot, metric_key(ex, side_field))
        if why:
            why_not[ex] = why
            continue
        eligible.append(ex)
        if rank >= r["venue_percentile_min"]:
            votes.append(ex)
    detail = {"eligible": eligible, "voting": votes, "ineligible": why_not}
    if len(eligible) < r["min_eligible_venues"]:
        return NOT_EVALUABLE, "INSUFFICIENT_ELIGIBLE_VENUES", detail
    ok = len(votes) >= r["min_eligible_venues"]
    return (QUALIFIES if ok else NOT_QUALIFIES), ("CONDITION_MET" if ok else "CONDITION_NOT_MET"), detail


def evaluate_bucket(cfg: BetaConfig, snapshot: Mapping[str, Any],
                    previous: Optional[Mapping[str, Mapping[str, Any]]]) -> dict:
    """Evaluate every V0.2 event type for one bucket. `previous` = the rule
    evaluations of the immediately preceding 5m LIVE tape row under the SAME rules
    digest (None if absent/non-contiguous => streaks restart)."""
    down, up = cfg.rule("PRICE_OI_CONTRACTION_DOWN"), cfg.rule("PRICE_OI_CONTRACTION_UP")
    bu, tk = cfg.rule("POSITION_BUILDUP_COMPRESSION"), cfg.rule("TAKER_FLOW_EXTREME")
    results = {
        PRICE_OI_CONTRACTION_DOWN: _threshold_rule(snapshot, ("price_structure", "oi"), [
            ("price_move_pct_median", "<=", down["price_move_pct_median_max"]),
            ("oi_change_pct_median", "<=", down["oi_change_pct_median_max"])]),
        PRICE_OI_CONTRACTION_UP: _threshold_rule(snapshot, ("price_structure", "oi"), [
            ("price_move_pct_median", ">=", up["price_move_pct_median_min"]),
            ("oi_change_pct_median", "<=", up["oi_change_pct_median_max"])]),
        POSITION_BUILDUP_COMPRESSION: _threshold_rule(snapshot, ("price_structure", "oi", "volume"), [
            ("range_width_pct_median", "<=", bu["range_width_pct_median_max"]),
            ("oi_change_pct_median", ">=", bu["oi_change_pct_median_min"]),
            ("volume_notional_usd_sum", ">=", bu["volume_notional_usd_sum_min"])]),
        LIQUIDATION_STRESS_LONG: _liquidation_rule(snapshot, cfg, "long_liquidation_notional"),
        LIQUIDATION_STRESS_SHORT: _liquidation_rule(snapshot, cfg, "short_liquidation_notional"),
    }
    if tk["enabled"]:
        results[TAKER_FLOW_EXTREME_BUY] = _threshold_rule(snapshot, ("taker_flow",), [
            ("taker_delta_notional_usd_sum", ">=", tk["buy_percentile_min"])])
        results[TAKER_FLOW_EXTREME_SELL] = _threshold_rule(snapshot, ("taker_flow",), [
            ("taker_delta_notional_usd_sum", "<=", tk["sell_percentile_max"])])
    else:
        results[TAKER_FLOW_EXTREME_BUY] = (NOT_EVALUABLE, "RULE_DISABLED", {})
        results[TAKER_FLOW_EXTREME_SELL] = (NOT_EVALUABLE, "RULE_DISABLED", {})

    out = {}
    for et in EVENT_TYPES:
        status, reason, detail = results[et]
        prev_streak = int(((previous or {}).get(et) or {}).get("streak", 0))
        streak = prev_streak + 1 if status == QUALIFIES else 0
        out[et] = {"status": status, "streak": streak, "reason": reason, "detail": detail}
    return out


def as_rule_evaluation(event_type: str, ev: Mapping[str, Any]) -> RuleEvaluation:
    return RuleEvaluation(event_type=event_type, status=ev["status"], streak=ev["streak"],
                          reason=ev["reason"], detail=ev.get("detail") or {})
