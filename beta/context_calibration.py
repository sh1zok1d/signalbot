"""EXPERIMENTAL, UNFROZEN hysteresis — offline calibration tooling only.

Identity: EXPERIMENTAL_TAKER_HYSTERESIS_UNFROZEN. NOT an active episodization:
no runtime module imports this file (enforced by tests), nothing here is
persisted, rendered, delivered or used for push decisions, detector episodes,
episode identity or outcomes. The active episodization is
`beta.context.STRICT_QUALIFICATION_V1` (the detector's own boundaries).

Scope follows the outcome-blind audit: only TAKER_FLOW_EXTREME_BUY/SELL have a
single-observable intensity series (signed taker delta). Conjunction families
(price+OI contraction, build-up/compression) and per-venue liquidation voting
have no defensible single primary observable and are deliberately unsupported.

`structure_stats` reports condition-series STRUCTURE only (episode count,
reactivations, lengths) per candidate parameter set. It never reads forward
prices or outcomes, so a later freeze can be chosen without outcome tuning.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional, Sequence

from .config import TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL, BetaConfig
from .detector import lifecycle
from .models import QUALIFIES
from .state_tape import BUCKET

EXPERIMENTAL_IDENTITY = "EXPERIMENTAL_TAKER_HYSTERESIS_UNFROZEN"
SUPPORTED = {TAKER_FLOW_EXTREME_BUY: +1, TAKER_FLOW_EXTREME_SELL: -1}
PRIMARY = "c:taker_delta_notional_usd_sum"


@dataclass(frozen=True)
class HysteresisParams:
    """Candidate parameters — UNFROZEN placeholders, never defaults for any live path."""
    cooling_buckets_to_end: int
    max_episode_duration_min: int
    exit_rank_buy: float            # ACTIVE persists while rank >= this (entry 0.95)
    exit_rank_sell: float           # ACTIVE persists while rank <= this (entry 0.05)


def _rank(snapshot) -> Optional[float]:
    p = ((snapshot or {}).get("percentiles") or {}).get(PRIMARY) or {}
    return float(p["rank"]) if p.get("rank") is not None and p.get("tier") == "mature" else None


def _fresh(snapshot) -> bool:
    return bool(snapshot and snapshot.get("materialized") and snapshot.get("evaluation_fresh")
                and not snapshot.get("stale_barrier")
                and ((snapshot.get("families") or {}).get("taker_flow") or {}).get("usable"))


def simulate(cfg: BetaConfig, rows_by_bucket: Mapping[datetime, Optional[Mapping[str, Any]]], *,
             params: HysteresisParams, start_bucket: datetime, end_bucket: datetime) -> list:
    """Offline hysteresis episodes for the taker families (ACTIVE/COOLING/ENDED)."""
    ttl = timedelta(minutes=params.max_episode_duration_min)
    exit_thr = {TAKER_FLOW_EXTREME_BUY: params.exit_rank_buy, TAKER_FLOW_EXTREME_SELL: params.exit_rank_sell}
    open_, done = {}, []
    b = start_bucket
    while b <= end_bucket:
        snap = (rows_by_bucket.get(b) or {}).get("snapshot")
        evals = (snap or {}).get("rule_evaluations") or {}
        for et, direction in SUPPORTED.items():
            ep = open_.get(et)
            ev = evals.get(et) or {}
            qualifies = _fresh(snap) and ev.get("status") == QUALIFIES
            if ep is not None:
                if b - ep["start"] >= ttl:
                    done.append({**ep, "end": b, "reason": "MAX_DURATION"})
                    open_.pop(et)
                    ep = None
                else:
                    r = _rank(snap) if _fresh(snap) else None
                    beyond = r is not None and (r >= exit_thr[et] if direction > 0 else r <= exit_thr[et])
                    if qualifies:
                        ep["reactivations"] += ep["phase"] == "COOLING"
                        ep.update(phase="ACTIVE", below=0)
                    elif beyond:
                        ep["below"] = 0
                    else:
                        ep.update(phase="COOLING", below=ep["below"] + 1)
                        if ep["below"] >= params.cooling_buckets_to_end:
                            done.append({**ep, "end": b, "reason": "COOLED_DOWN"})
                            open_.pop(et)
                    continue
            if ep is None and qualifies and int(ev.get("streak") or 0) == lifecycle(cfg, et).entry_streak:
                open_[et] = {"event_type": et, "start": b, "phase": "ACTIVE", "below": 0, "reactivations": 0}
        b += BUCKET
    return done + list(open_.values())


def structure_stats(cfg: BetaConfig, rows_by_bucket, *, start_bucket: datetime, end_bucket: datetime,
                    candidates: Sequence[HysteresisParams]) -> list:
    """Per candidate: episodes ended / still open, reactivations, mean length (buckets)."""
    out = []
    for p in candidates:
        eps = simulate(cfg, rows_by_bucket, params=p, start_bucket=start_bucket, end_bucket=end_bucket)
        ended = [e for e in eps if "end" in e]
        lengths = [int((e["end"] - e["start"]) / BUCKET) for e in ended]
        out.append({"identity": EXPERIMENTAL_IDENTITY, "params": p.__dict__, "episodes_ended": len(ended),
                    "open_at_end": len(eps) - len(ended),
                    "reactivations": sum(e["reactivations"] for e in eps),
                    "mean_length_buckets": (sum(lengths) / len(lengths)) if lengths else None})
    return out
