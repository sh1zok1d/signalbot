"""PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0 — pure pilot logic. No I/O.

Pilot-only kill-test, not confirmatory, no trading claim. Every constant below
is frozen in ``docs/research/price_oi_incremental_information_pilot_v0.json``;
``check_protocol`` refuses to run when they differ.

Event A is the current ``semantic_rule`` exactly. Control B is the same rule
with only the OI component changed: the price side is the current
``semantic_rule`` evaluated with the OI rank neutralised, and the real OI
percentile must be valid, mature and at or above the median. Both go through
the current ``step_episode`` lifecycle. Control eligibility never looks past
the control anchor.
"""
from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Sequence

from beta.config import PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP, BetaConfig
from beta.detector import BucketContext, step_episode
from beta.models import NOT_EVALUABLE, NOT_QUALIFIES, QUALIFIES
from beta.outcomes import compute_outcome
from beta.rules import MATURE, _pct
from beta.state_tape import metric_key
from beta.models import OUTCOME_COMPLETE
from scripts.audit.live_archive_replay_preflight import price_oi_semantic_replay as semantic

UTC = timezone.utc
BUCKET = timedelta(minutes=5)
PILOT_ID = "PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0"
PROTOCOL_PATH = (Path(__file__).resolve().parents[3] / "docs" / "research"
                 / "price_oi_incremental_information_pilot_v0.json")
FAMILIES = (PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP)
OI_KEY = metric_key(None, "oi_change_pct_median")

# ---- frozen protocol constants ---------------------------------------------------
OI_CONTROL_RANK_MIN = 0.5
CALIPER = 0.75
K_MAX = 3
MIN_ELIGIBLE_CONTROLS = 10
MIN_MATCHED_EVENTS = 10
MIN_MATCHED_EVENT_DATES = 5
MIN_DISTINCT_CONTROLS_USED = 5
MIN_PLACEBO_MATCHED = 10
MATCHED_SMD_MAX = 0.25
TIME_SMD_MAX = 0.5
MATERIALITY_RATIO = 1.25
MATERIALITY_LOG_RATIO = math.log(MATERIALITY_RATIO)
CLUSTER_GAP = timedelta(hours=4)
PRIMARY, SECONDARY = "4h", "1h"
KLINE_READ_END = datetime(2026, 9, 29, 4, 0, tzinfo=UTC)
EXPECTED_AUTHORIZED_BUCKETS = 12434
EXPECTED_TRIGGERED = {PRICE_OI_CONTRACTION_DOWN: 25, PRICE_OI_CONTRACTION_UP: 19}
P4_ELIGIBLE = {PRICE_OI_CONTRACTION_DOWN: 22, PRICE_OI_CONTRACTION_UP: 17}
MATCHED_COVARIATES = ("log_abs_trigger_price_move", "log_prior_range_15m",
                      "log_prior_range_1h", "log_prior_range_4h")
TIME_COVARIATES = ("hour_sin", "hour_cos", "weekend")
PRIOR_WINDOWS = {"log_prior_range_15m": ("15m", timedelta(minutes=15)),
                 "log_prior_range_1h": ("1h", timedelta(hours=1)),
                 "log_prior_range_4h": ("4h", timedelta(hours=4)),
                 "log_prior_range_24h": ("24h", timedelta(hours=24))}

# ---- verdicts --------------------------------------------------------------------
NULL_LIKE = "OI_ABLATION_NULL_LIKE"
SURVIVES = "OI_INCREMENTAL_SIGNAL_PILOT_SURVIVES"
INSUFFICIENT = "PILOT_INSUFFICIENT_CONTROL_SUPPORT"
BALANCE_FAILED = "PILOT_BALANCE_FAILED"
DATA_BLOCKED = "PILOT_DATA_BLOCKED"
VERDICTS = (NULL_LIKE, SURVIVES, INSUFFICIENT, BALANCE_FAILED, DATA_BLOCKED)
FORBIDDEN_OUTPUTS = ("VALIDATED_EDGE", "PREDICTIVE", "PROFITABLE", "SIGNIFICANT_ALPHA")

# ---- exclusion reasons -------------------------------------------------------------
REFERENCE_UNAVAILABLE = "REFERENCE_UNAVAILABLE"
OUTCOME_NOT_COMPLETE = "OUTCOME_NOT_COMPLETE"
OUTCOME_NONPOSITIVE = "OUTCOME_NONPOSITIVE"
COVARIATE_UNAVAILABLE = "COVARIATE_UNAVAILABLE"


class ProtocolMismatch(RuntimeError):
    pass


def check_protocol(path: Path = PROTOCOL_PATH) -> dict:
    """The module constants must equal the frozen JSON protocol."""
    doc = json.loads(Path(path).read_text())
    expected = {
        ("pilot_id",): PILOT_ID,
        ("status",): "FROZEN_BEFORE_OUTCOMES",
        ("control_group_b", "oi_control_rank_min"): OI_CONTROL_RANK_MIN,
        ("matching", "caliper"): CALIPER,
        ("matching", "k_max"): K_MAX,
        ("matching", "replacement"): True,
        ("support_gate", "min_eligible_controls"): MIN_ELIGIBLE_CONTROLS,
        ("support_gate", "min_matched_events"): MIN_MATCHED_EVENTS,
        ("support_gate", "min_matched_event_dates"): MIN_MATCHED_EVENT_DATES,
        ("support_gate", "min_distinct_controls_used"): MIN_DISTINCT_CONTROLS_USED,
        ("support_gate", "min_placebo_matched"): MIN_PLACEBO_MATCHED,
        ("balance_gate", "matched_covariate_abs_smd_max"): MATCHED_SMD_MAX,
        ("balance_gate", "time_covariate_abs_smd_max"): TIME_SMD_MAX,
        ("materiality_ratio",): MATERIALITY_RATIO,
        ("materiality_log_ratio",): MATERIALITY_LOG_RATIO,
        ("outcome", "primary_horizon"): PRIMARY,
        ("outcome", "secondary_horizon"): SECONDARY,
        ("data_scope", "authorized_buckets"): EXPECTED_AUTHORIZED_BUCKETS,
        ("data_scope", "kline_read_end_exclusive"): _iso(KLINE_READ_END),
        ("data_gate", "triggered_episodes_must_equal"): dict(EXPECTED_TRIGGERED),
        ("data_gate", "p4_eligible_reference_not_blocking"): dict(P4_ELIGIBLE),
        ("families",): list(FAMILIES),
        ("confirmatory",): False,
    }
    for keys, want in expected.items():
        got = doc
        for key in keys:
            got = got[key]
        if got != want:
            raise ProtocolMismatch(f"protocol {'.'.join(keys)} = {got!r}, code has {want!r}")
    intervals = [[_iso(a), _iso(b)] for a, b in semantic.INTERVALS]
    if doc["data_scope"]["rule_evaluation_intervals"] != intervals:
        raise ProtocolMismatch("protocol intervals differ from the frozen Phase A grid")
    return doc


# ---- predicates (current code) -----------------------------------------------------
Predicate = Callable[[BetaConfig, str, "semantic.PreparedBucket"], str]


def event_status(cfg: BetaConfig, family: str, item) -> str:
    """Group A: the current semantic rule, unchanged."""
    return semantic.semantic_rule(cfg, family, item)[0]


def price_side_status(cfg: BetaConfig, family: str, item) -> str:
    """The current semantic rule with ONLY the OI rank neutralised to a mature 0.0.

    The OI rank then always satisfies the event's OI check, so the result is
    decided by the real family usability, the real price percentile and the
    current price threshold. Nothing about price is restated here.
    """
    neutral = replace(item, oi_rank=0.0, oi_tier=MATURE)
    return semantic.semantic_rule(cfg, family, neutral)[0]


def oi_valid_rank(cfg: BetaConfig, item) -> Optional[float]:
    """Real OI rank when present, valued and mature (current ``_pct``); else None."""
    rank, why = _pct(semantic._projection(cfg, item), OI_KEY)
    return None if why else rank


def control_status(cfg: BetaConfig, family: str, item) -> str:
    """Group B: same price side, OI valid and at or above the median."""
    price = price_side_status(cfg, family, item)
    rank = oi_valid_rank(cfg, item)
    if price == NOT_EVALUABLE or rank is None:
        return NOT_EVALUABLE
    return QUALIFIES if price == QUALIFIES and rank >= OI_CONTROL_RANK_MIN else NOT_QUALIFIES


# ---- lifecycle (current step_episode) ----------------------------------------------
def triggered_anchors(cfg: BetaConfig, family: str, prepared: Sequence, predicate: Predicate) -> list:
    """Anchors (triggered_at) of every episode the current lifecycle triggers.

    Same streak carry as ``replay_series``: a non-contiguous bucket restarts
    the streak, and ``step_episode`` terminates an open episode on the gap.
    Only buckets up to and including the triggering bucket are read.
    """
    anchors = []
    open_ep = None
    previous_bucket, previous_streak = None, 0
    for item in prepared:
        bucket = item.reconstruction.bucket_ts
        contiguous = previous_bucket is not None and bucket == previous_bucket + BUCKET
        status = predicate(cfg, family, item)
        streak = ((previous_streak if contiguous else 0) + 1) if status == QUALIFIES else 0
        ctx = BucketContext(
            bucket_ts=bucket, decision_ts=bucket + BUCKET,
            snapshot_digest=semantic._digest(item, family, status, streak),
            calculation_version=item.reconstruction.calculation_version or "UNMATERIALIZED",
            reference={"status": "NOT_A_HISTORICAL_REFERENCE"}, code_version=PILOT_ID)
        step = step_episode(cfg, family, open_ep, {"status": status, "streak": streak}, ctx)
        if step.terminated is not None:
            open_ep = None
        if step.updated is not None:
            open_ep = step.updated
        if step.opened is not None:
            open_ep = step.opened
        if step.triggered is not None:
            anchors.append(ctx.decision_ts)
        previous_bucket, previous_streak = bucket, streak
    return anchors


# ---- observations ----------------------------------------------------------------
@dataclass(frozen=True)
class Observation:
    family: str
    group: str                                   # "A" event | "B" control
    anchor: datetime
    covariates: Mapping[str, Optional[float]] = field(default_factory=dict)
    ranges: Mapping[str, Optional[float]] = field(default_factory=dict)
    exclusion: Optional[str] = None

    @property
    def eligible(self) -> bool:
        return self.exclusion is None


class KlineIndex:
    """1m composite-input rows keyed by minute, for window slicing."""

    def __init__(self, rows: Iterable[Mapping]):
        self._by_minute: dict = {}
        for row in rows:
            self._by_minute.setdefault(row["ts"], []).append(row)

    def window(self, start: datetime, end: datetime) -> list:
        out, cursor = [], start
        while cursor < end:
            out.extend(self._by_minute.get(cursor, ()))
            cursor += timedelta(minutes=1)
        return out


def observe(family: str, group: str, anchor: datetime, *, price_move: Optional[float],
            reference: Mapping, klines: KlineIndex) -> Observation:
    """Pre-anchor covariates and forward ranges for one anchor.

    Covariates read only bars in [anchor - window, anchor). Forward ranges use
    the unchanged ``compute_outcome`` from the anchor.
    """
    base = dict(family=family, group=group, anchor=anchor)
    if reference.get("status") != "OK" or reference.get("price") is None:
        return Observation(**base, exclusion=REFERENCE_UNAVAILABLE)
    price, exchanges = float(reference["price"]), list(reference["exchanges"])
    ranges = {}
    for horizon, length in (("1h", timedelta(hours=1)), ("4h", timedelta(hours=4))):
        out = compute_outcome(anchor=anchor, horizon=horizon, reference_price=price,
                              exchanges=exchanges, klines=klines.window(anchor, anchor + length))
        ranges[horizon] = out["realized_range_pct"] if out["status"] == OUTCOME_COMPLETE else None
    covariates = {name: prior_log_range(anchor, horizon, length, price, exchanges, klines)
                  for name, (horizon, length) in PRIOR_WINDOWS.items()}
    covariates["log_abs_trigger_price_move"] = _log_pos(None if price_move is None else abs(price_move))
    covariates.update(time_covariates(anchor))
    if any(ranges[h] is None for h in ranges):
        return Observation(**base, covariates=covariates, ranges=ranges, exclusion=OUTCOME_NOT_COMPLETE)
    if any(not (ranges[h] > 0 and math.isfinite(ranges[h])) for h in ranges):
        return Observation(**base, covariates=covariates, ranges=ranges, exclusion=OUTCOME_NONPOSITIVE)
    if any(covariates[name] is None for name in MATCHED_COVARIATES):
        return Observation(**base, covariates=covariates, ranges=ranges, exclusion=COVARIATE_UNAVAILABLE)
    return Observation(**base, covariates=covariates, ranges=ranges)


def prior_log_range(anchor, horizon, length, price, exchanges, klines: KlineIndex) -> Optional[float]:
    start = anchor - length
    bars = [row for row in klines.window(start, anchor) if row["ts"] < anchor]
    out = compute_outcome(anchor=start, horizon=horizon, reference_price=price,
                          exchanges=exchanges, klines=bars)
    return _log_pos(out["realized_range_pct"]) if out["status"] == OUTCOME_COMPLETE else None


def time_covariates(anchor: datetime) -> dict:
    bucket = anchor - BUCKET                      # the triggering bucket start
    angle = 2.0 * math.pi * (bucket.hour + bucket.minute / 60.0) / 24.0
    return {"hour_sin": math.sin(angle), "hour_cos": math.cos(angle),
            "weekend": 1.0 if bucket.weekday() >= 5 else 0.0}


def _log_pos(value: Optional[float]) -> Optional[float]:
    if value is None or not math.isfinite(value) or value <= 0:
        return None
    return math.log(value)


# ---- matching ----------------------------------------------------------------------
def scales(pool: Sequence[Observation], names: Sequence[str] = MATCHED_COVARIATES) -> dict:
    return {name: statistics.pstdev([o.covariates[name] for o in pool]) if len(pool) else 0.0
            for name in names}


def distance(event: Observation, control: Observation, scale: Mapping[str, float]) -> float:
    total = 0.0
    for name in MATCHED_COVARIATES:
        diff = event.covariates[name] - control.covariates[name]
        if scale[name] == 0:
            if diff != 0:
                return math.inf
            continue
        total += (diff / scale[name]) ** 2
    return math.sqrt(total / len(MATCHED_COVARIATES))


def match(events: Sequence[Observation], controls: Sequence[Observation],
          scale: Mapping[str, float], *, exclude_self: bool = False) -> dict:
    """anchor -> [(distance, control)], nearest first, with replacement.

    Selection uses only pre-anchor covariates. No temporal exclusion.
    """
    out = {}
    for event in events:
        found = []
        for control in controls:
            if exclude_self and control.anchor == event.anchor:
                continue
            d = distance(event, control, scale)
            if d <= CALIPER:
                found.append((d, control.anchor, control))
        found.sort(key=lambda item: (item[0], item[1]))
        if found:
            out[event.anchor] = [(d, c) for d, _a, c in found[:K_MAX]]
    return out


# ---- gates -------------------------------------------------------------------------
def smd_table(events: Sequence[Observation], matches: Mapping, pool_a: Sequence[Observation],
              pool_b: Sequence[Observation]) -> dict:
    matched = [e for e in events if e.anchor in matches]
    table = {}
    for name in MATCHED_COVARIATES + TIME_COVARIATES:
        a = [e.covariates[name] for e in matched]
        c = [statistics.fmean(ctrl.covariates[name] for _d, ctrl in matches[e.anchor]) for e in matched]
        diff = statistics.fmean(a) - statistics.fmean(c) if matched else 0.0
        var_a = statistics.pvariance([o.covariates[name] for o in pool_a]) if pool_a else 0.0
        var_b = statistics.pvariance([o.covariates[name] for o in pool_b]) if pool_b else 0.0
        scale = math.sqrt((var_a + var_b) / 2.0)
        limit = MATCHED_SMD_MAX if name in MATCHED_COVARIATES else TIME_SMD_MAX
        if scale == 0:
            smd, ok = (0.0 if diff == 0 else math.inf), diff == 0
        else:
            smd = diff / scale
            ok = abs(smd) <= limit
        table[name] = {"smd": smd, "limit": limit, "pass": ok, "mean_event": _mean(a),
                       "mean_matched_control": _mean(c)}
    return table


def log_ratio(event: Observation, controls: Sequence[Observation], horizon: str) -> float:
    return math.log(event.ranges[horizon]) - statistics.fmean(
        math.log(c.ranges[horizon]) for c in controls)


def placebo_statistic(pool_b: Sequence[Observation], placebo_matches: Mapping) -> dict:
    """B-vs-B pseudo-events; reads control outcomes only. Deterministic."""
    values = [log_ratio(p, [c for _d, c in placebo_matches[p.anchor]], PRIMARY)
              for p in pool_b if p.anchor in placebo_matches]
    med = statistics.median(values) if values else None
    return {"design": "B_VS_B", "pseudo_events": len(values), "median_log_ratio_4h": med,
            "pass": med is not None and abs(med) < MATERIALITY_LOG_RATIO}


def clusters(anchors: Sequence[datetime]) -> list:
    groups: list = []
    for anchor in sorted(anchors):
        if groups and anchor - groups[-1][-1] <= CLUSTER_GAP:
            groups[-1].append(anchor)
        else:
            groups.append([anchor])
    return groups


def evaluate_family(family: str, events: Sequence[Observation], controls: Sequence[Observation],
                    *, data_blocked_reason: Optional[str] = None) -> dict:
    """Frozen gate order: data, support, balance (+placebo), then the endpoint."""
    report = {"family": family, "events_total": len(events), "controls_total": len(controls),
              "event_exclusions": _reasons(events), "control_exclusions": _reasons(controls)}
    if data_blocked_reason is not None:
        return _finish(report, DATA_BLOCKED, data_blocked_reason)
    pool_a = [o for o in events if o.eligible]
    pool_b = [o for o in controls if o.eligible]
    report.update({"events_eligible": len(pool_a), "controls_eligible": len(pool_b),
                   "event_eligible_dates": _dates(o.anchor for o in pool_a)})
    if len(pool_b) < MIN_ELIGIBLE_CONTROLS or not pool_a:
        return _finish(report, INSUFFICIENT, "TOO_FEW_ELIGIBLE_CONTROLS" if pool_a else "NO_ELIGIBLE_EVENTS")
    scale = scales(pool_a + pool_b)
    matches = match(pool_a, pool_b, scale)
    matched = [e for e in pool_a if e.anchor in matches]
    used = {c.anchor for pairs in matches.values() for _d, c in pairs}
    placebo_matches = match(pool_b, pool_b, scale, exclude_self=True)
    report["support"] = {
        "candidate_controls": len(pool_b),
        "matched_events": len(matched),
        "unmatched_events": len(pool_a) - len(matched),
        "matched_event_dates": _dates(e.anchor for e in matched),
        "distinct_controls_used": len(used),
        "controls_per_event": {"1": 0, "2": 0, "3": 0} | _count_sizes(matches),
        "placebo_matched": len(placebo_matches),
        "scales": scale,
    }
    s = report["support"]
    if (len(matched) < MIN_MATCHED_EVENTS or s["matched_event_dates"] < MIN_MATCHED_EVENT_DATES
            or len(used) < MIN_DISTINCT_CONTROLS_USED or len(placebo_matches) < MIN_PLACEBO_MATCHED):
        return _finish(report, INSUFFICIENT, "SUPPORT_GATE_FAILED")
    balance = smd_table(pool_a, matches, pool_a, pool_b)
    report["balance"] = balance
    if not all(row["pass"] for row in balance.values()):
        return _finish(report, BALANCE_FAILED, "SMD_GATE_FAILED")
    report["placebo"] = placebo_statistic(pool_b, placebo_matches)
    if not report["placebo"]["pass"]:
        return _finish(report, BALANCE_FAILED, "PLACEBO_FAILED")
    # Endpoint (only now are event outcomes read).
    endpoint = {}
    for horizon in (PRIMARY, SECONDARY):
        d = [log_ratio(e, [c for _d, c in matches[e.anchor]], horizon) for e in matched]
        med = statistics.median(d)
        endpoint[horizon] = {"median_log_ratio": med, "median_range_ratio": math.exp(med),
                             "events_with_positive_log_ratio": sum(1 for v in d if v > 0),
                             "events": len(d)}
    groups = clusters([e.anchor for e in matched])
    by_anchor = {e.anchor: e for e in matched}
    first = [log_ratio(by_anchor[g[0]], [c for _d, c in matches[g[0]]], PRIMARY) for g in groups]
    pairs = [(e.anchor, c.anchor) for e in matched for _d, c in matches[e.anchor]]
    overlap = sum(1 for a, c in pairs if abs(a - c) < timedelta(hours=4))
    report["endpoint"] = endpoint
    report["declustering"] = {
        "matched_events": len(matched), "distinct_utc_dates": s["matched_event_dates"],
        "clusters_4h": len(groups), "first_per_cluster_median_log_ratio_4h": statistics.median(first),
        "first_per_cluster_median_range_ratio_4h": math.exp(statistics.median(first)),
    }
    report["diagnostics"] = {"pairs": len(pairs), "pair_forward_4h_overlap": overlap,
                             "pair_forward_4h_overlap_share": overlap / len(pairs)}
    survives = (endpoint[PRIMARY]["median_log_ratio"] >= MATERIALITY_LOG_RATIO
                and report["declustering"]["first_per_cluster_median_log_ratio_4h"] >= MATERIALITY_LOG_RATIO)
    return _finish(report, SURVIVES if survives else NULL_LIKE,
                   "MATERIAL_AND_DECLUSTERED" if survives else "NOT_MATERIAL_AFTER_ABLATION")


def final_classification(results: Mapping[str, str]) -> str:
    verdicts = list(results.values())
    if any(v == DATA_BLOCKED for v in verdicts):
        return DATA_BLOCKED
    if any(v == SURVIVES for v in verdicts):
        return SURVIVES
    if verdicts and all(v == NULL_LIKE for v in verdicts):
        return NULL_LIKE
    if any(v == INSUFFICIENT for v in verdicts):
        return INSUFFICIENT
    return BALANCE_FAILED


def assert_allowed_wording(text: str) -> str:
    for word in FORBIDDEN_OUTPUTS:
        if word in text:
            raise ValueError(f"forbidden output {word!r}")
    return text


# ---- helpers -----------------------------------------------------------------------
def _finish(report: dict, verdict: str, reason: str) -> dict:
    report["verdict"] = verdict
    report["verdict_reason"] = reason
    return report


def _reasons(items: Sequence[Observation]) -> dict:
    out: dict = {}
    for item in items:
        if item.exclusion is not None:
            out[item.exclusion] = out.get(item.exclusion, 0) + 1
    return dict(sorted(out.items()))


def _count_sizes(matches: Mapping) -> dict:
    out: dict = {}
    for pairs in matches.values():
        out[str(len(pairs))] = out.get(str(len(pairs)), 0) + 1
    return out


def _dates(anchors: Iterable[datetime]) -> int:
    return len({(a - BUCKET).astimezone(UTC).date() for a in anchors})


def _mean(values: Sequence[float]) -> Optional[float]:
    return statistics.fmean(values) if values else None


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
