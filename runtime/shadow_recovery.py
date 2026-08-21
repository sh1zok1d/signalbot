"""
Bounded automatic shadow recovery + outcome maturation.

This is the RUNTIME orchestration layer that turns one automatic
`--shadow-once` invocation into a single bounded recovery pass:

  1. acquire one non-blocking cross-process PostgreSQL advisory lock;
  2. bootstrap/verify Stage 2 prerequisites once;
  3. plan a bounded, oldest-first sequence of missing closed 5m prediction buckets;
  4. process them with the existing `process_shadow_cycle` (one bucket each);
  5. advance a durable, monotonic prediction watermark only after each success;
  6. discover bounded DUE forecast outcomes missing from `forecast_outcomes`;
  7. evaluate them sequentially with the existing outcome pipeline;
  8. emit one deterministic aggregate report;
  9. release the advisory lock on every exit path.

There is no background worker, no sleep, and no loop over invocations — one CLI
call is bounded and then exits.

Layer discipline: the PURE functions here (lock-key derivation, bucket planning,
snapshot/prediction hydration, dueness) touch no DB, clock, environment,
subprocess, or logging. `execute_shadow_recovery` is the only impure part; it
receives an already-connected `db`, the wall-clock `now`, and the configs.
Analytics primitives (`process_shadow_cycle`, `process_forecast_outcome_horizon`)
are used unchanged; forecast/consensus/outcome formulas are never duplicated.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from common.versioning import resolve_code_version
from symbols.registry import (
    ACTIVE_EXCHANGES, symbol_exchange_capability_seed_rows, symbol_seed_rows,
)

from analytics.feature_engine.consensus_models import (
    ConsensusFeatureVector, CoverageEntry, OutlierEntry, ProvenanceEntry,
)
from analytics.forecasting.outcome_pipeline import process_forecast_outcome_horizon
from analytics.forecasting.outcomes import (
    DEFAULT_OUTCOME_VERSION, EVALUATION_PRICE_SOURCE, OUTCOME_HORIZON_MINUTES,
    OUTCOME_HORIZONS,
)
from analytics.forecasting.persistence import ForecastPrediction
from analytics.forecasting.shadow_cycle import (
    DueOutcomeJob, PREDICTION_DUPLICATE, PREDICTION_INSERTED,
    PREDICTION_SKIPPED_NO_CONSENSUS, PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE,
    process_shadow_cycle,
)

from runtime.shadow_cli import (
    BUCKET_EXPLICIT, SHADOW_ONCE, ShadowExecutionReport, _BUCKET_MINUTES,
    _MARKET_TYPE, _TIMEFRAME, _bootstrap_instrument_metadata,
    _bootstrap_stage2_schema_and_revision, _iso_utc,
    _resolve_shadow_scope, execute_shadow_once, execution_report_to_jsonable,
    parse_shadow_bucket_ts, render_shadow_execution_report,
    select_latest_closed_5m_bucket,
)

# ---- stable constants ------------------------------------------------------
RUNNER_NAME = "shadow_forecast_v1"          # explicit, stable automatic-runner id
SHADOW_RECOVERY = "SHADOW_RECOVERY"

LOCK_ACQUIRED = "ACQUIRED"
LOCK_HELD_SKIPPED = "LOCK_HELD_SKIPPED"

# Bounded catch-up defaults + hard validation ceilings (operational only; these
# NEVER enter config_hash / calculation_version).
DEFAULT_MAX_CATCHUP_BUCKETS = 12
DEFAULT_MAX_OUTCOME_JOBS = 100
MAX_CATCHUP_BUCKETS_LIMIT = 288             # <= 24h of 5m buckets per invocation
MAX_OUTCOME_JOBS_LIMIT = 1000

# Hard bounded recovery lookback so a fresh/stale runner never replays months.
RECOVERY_LOOKBACK_BUCKETS = 288             # 24h of 5m buckets
OUTCOME_LOOKBACK_BUCKETS = 288              # recent predictions considered for outcomes
OUTCOME_CANDIDATE_ROW_LIMIT = 2000          # hard cap on candidate rows fetched

_REFERENCE_SUFFIX = "_close_5m"
_STEP = timedelta(minutes=_BUCKET_MINUTES)


class ShadowRecoveryError(RuntimeError):
    """A recovery-layer failure: malformed operational input, a hydration/identity
    failure that must fail closed, or an impossible orchestration state."""


# ============================================================================
# Pure helpers
# ============================================================================
def shadow_recovery_lock_key(runner_name: str, symbol: str, market_type: str,
                             timeframe: str) -> int:
    """Deterministic signed 64-bit advisory-lock key from the runner identity.
    Uses sha256 (NOT Python's randomized built-in hash) so the same runner/scope
    always maps to the same PostgreSQL advisory-lock id across processes/runs."""
    for name, value in (("runner_name", runner_name), ("symbol", symbol),
                        ("market_type", market_type), ("timeframe", timeframe)):
        if not isinstance(value, str) or not value.strip():
            raise ShadowRecoveryError(f"{name} must be a non-empty string")
    payload = "\x1f".join((runner_name, symbol, market_type, timeframe)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=True)


def _require_utc_5m(dt, name: str) -> datetime:
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ShadowRecoveryError(f"{name} must be a timezone-aware UTC datetime")
    if dt.second != 0 or dt.microsecond != 0 or dt.minute % _BUCKET_MINUTES != 0:
        raise ShadowRecoveryError(f"{name} must be a whole-minute 5m-aligned UTC timestamp")
    return dt


def validate_operational_cap(value, name: str, upper: int) -> int:
    """A validated operational cap: an exact int in [1, upper]; bool/zero/negative/
    non-int/too-large rejected. Operational only — never enters config identity."""
    if type(value) is not int:
        raise ShadowRecoveryError(f"{name} must be an int (bool rejected)")
    if not (1 <= value <= upper):
        raise ShadowRecoveryError(f"{name} must be in [1, {upper}], got {value}")
    return value


@dataclass(frozen=True)
class PredictionPlan:
    buckets: tuple                      # oldest-first, aligned closed 5m buckets
    truncated_by_lookback: bool
    truncated_by_cap: bool


def plan_prediction_buckets(*, watermark: Optional[datetime],
                            newest_prediction_bucket: Optional[datetime],
                            latest_closed: datetime, max_buckets: int,
                            lookback_buckets: int) -> PredictionPlan:
    """Pure catch-up planning (no I/O). Oldest-first aligned buckets from the next
    bucket after the watermark (or, on a fresh runner, from the newest persisted
    prediction; or, with neither, ONLY the current latest closed bucket) through
    latest_closed, floored by the hard lookback and capped at max_buckets (keeping
    the OLDEST ones so the watermark advances and the next run continues)."""
    _require_utc_5m(latest_closed, "latest_closed")
    if watermark is not None:
        _require_utc_5m(watermark, "watermark")
    if newest_prediction_bucket is not None:
        _require_utc_5m(newest_prediction_bucket, "newest_prediction_bucket")
    validate_operational_cap(max_buckets, "max_buckets", MAX_CATCHUP_BUCKETS_LIMIT)
    validate_operational_cap(lookback_buckets, "lookback_buckets", 100000)

    if watermark is not None:
        start = watermark + _STEP
    elif newest_prediction_bucket is not None:
        start = newest_prediction_bucket + _STEP
    else:
        start = latest_closed          # fresh runner: only the current latest bucket

    if start > latest_closed:
        return PredictionPlan((), False, False)

    earliest = latest_closed - lookback_buckets * _STEP
    truncated_by_lookback = False
    if start < earliest:
        start = earliest
        truncated_by_lookback = True

    n = round((latest_closed - start) / _STEP) + 1
    buckets = [start + i * _STEP for i in range(n)]

    truncated_by_cap = False
    if len(buckets) > max_buckets:
        buckets = buckets[:max_buckets]     # keep the OLDEST max_buckets
        truncated_by_cap = True
    return PredictionPlan(tuple(buckets), truncated_by_lookback, truncated_by_cap)


def derive_evaluation_exchange(reference_price_source: str) -> str:
    """V0 rule: `<exchange>_close_5m` -> `<exchange>` (must be an active exchange).
    Malformed/unsupported sources fail closed."""
    if not isinstance(reference_price_source, str) or not reference_price_source.endswith(_REFERENCE_SUFFIX):
        raise ShadowRecoveryError(
            f"unsupported reference_price_source {reference_price_source!r}")
    exchange = reference_price_source[:-len(_REFERENCE_SUFFIX)]
    if exchange not in ACTIVE_EXCHANGES:
        raise ShadowRecoveryError(
            f"reference exchange {exchange!r} (from {reference_price_source!r}) is not active")
    return exchange


def due_horizons(prediction: ForecastPrediction, now: datetime, soft_grace_s: int
                 ) -> tuple:
    """Horizons of `prediction` whose evaluation window has ENDED by `now` (minus
    soft grace), in canonical OUTCOME_HORIZONS order. evaluation_end =
    bucket_ts + 5m + horizon_minutes."""
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ShadowRecoveryError("now must be a timezone-aware UTC datetime")
    if type(soft_grace_s) is not int or soft_grace_s < 0:
        raise ShadowRecoveryError("soft_grace_s must be an int >= 0")
    cutoff = now - timedelta(seconds=soft_grace_s)
    out = []
    for horizon in OUTCOME_HORIZONS:
        if horizon in prediction.horizon_set:
            end = prediction.bucket_ts + timedelta(
                minutes=_BUCKET_MINUTES + OUTCOME_HORIZON_MINUTES[horizon])
            if end <= cutoff:
                out.append(horizon)
    return tuple(out)


# ============================================================================
# Strict hydration (pure): DB row -> exact immutable ForecastPrediction
# ============================================================================
def _parse_iso_utc(value) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value[:-1] + "+00:00" if value.endswith("Z") else value
        dt = datetime.fromisoformat(text)
    else:
        raise ShadowRecoveryError(f"expected an ISO datetime, got {type(value).__name__}")
    if dt.tzinfo is None:
        raise ShadowRecoveryError("snapshot datetime must be timezone-aware")
    return dt.astimezone(timezone.utc)


def hydrate_consensus_snapshot(snap: Mapping) -> ConsensusFeatureVector:
    """Strictly reconstruct the nested ConsensusFeatureVector from the stored
    consensus_snapshot JSON. Fails closed on missing keys / wrong shapes."""
    if not isinstance(snap, Mapping):
        raise ShadowRecoveryError("consensus_snapshot must be a JSON object")
    try:
        coverage = MappingProxyType({
            str(m): CoverageEntry(available=e["available"], expected=e["expected"],
                                  ratio=e["ratio"])
            for m, e in snap["coverage_by_metric"].items()})
        provenance = MappingProxyType({
            str(m): ProvenanceEntry(
                contributing=tuple(e["contributing"]),
                excluded=tuple(tuple(pair) for pair in e["excluded"]))
            for m, e in snap["provenance_by_metric"].items()})
        outliers = MappingProxyType({
            str(m): MappingProxyType({
                str(ex): OutlierEntry(robust_z=o["robust_z"], reason=o["reason"])
                for ex, o in inner.items()})
            for m, inner in snap["outlier_exchanges"].items()})
        return ConsensusFeatureVector(
            symbol=snap["symbol"], market_type=snap["market_type"],
            timeframe=snap["timeframe"], bucket_ts=_parse_iso_utc(snap["bucket_ts"]),
            feature_schema_version=snap["feature_schema_version"],
            calculation_version=snap["calculation_version"],
            coverage_by_metric=coverage, provenance_by_metric=provenance,
            data_confidence_by_metric=MappingProxyType(dict(snap["data_confidence_by_metric"])),
            exchanges_expected_max=snap["exchanges_expected_max"],
            min_coverage_ratio=snap["min_coverage_ratio"],
            data_confidence_overall=snap["data_confidence_overall"],
            price_direction_agreement=snap["price_direction_agreement"],
            flow_direction_agreement=snap["flow_direction_agreement"],
            oi_direction_agreement=snap["oi_direction_agreement"],
            price_move_pct_median=snap["price_move_pct_median"],
            range_width_pct_median=snap["range_width_pct_median"],
            oi_change_pct_median=snap["oi_change_pct_median"],
            funding_rate_median=snap["funding_rate_median"],
            funding_rate_mad=snap["funding_rate_mad"],
            volume_notional_usd_sum=snap["volume_notional_usd_sum"],
            taker_buy_notional_usd_sum=snap["taker_buy_notional_usd_sum"],
            taker_sell_notional_usd_sum=snap["taker_sell_notional_usd_sum"],
            taker_delta_notional_usd_sum=snap["taker_delta_notional_usd_sum"],
            cvd_delta_notional_usd_sum=snap["cvd_delta_notional_usd_sum"],
            observed_long_liquidation_notional_sum=snap["observed_long_liquidation_notional_sum"],
            observed_short_liquidation_notional_sum=snap["observed_short_liquidation_notional_sum"],
            observed_liquidation_event_count_sum=snap["observed_liquidation_event_count_sum"],
            liquidation_feed_quality_by_exchange=MappingProxyType(
                dict(snap["liquidation_feed_quality_by_exchange"])),
            price_move_pct_mad=snap["price_move_pct_mad"],
            oi_change_pct_mad=snap["oi_change_pct_mad"],
            outlier_exchanges=outliers,
            consensus_confidence=snap["consensus_confidence"],
            is_partial_consensus=snap["is_partial_consensus"],
            config_hash=snap["config_hash"], config_version=snap["config_version"],
            code_version=snap["code_version"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ShadowRecoveryError(f"malformed consensus_snapshot: {exc}") from exc


def hydrate_forecast_prediction(row: Mapping) -> ForecastPrediction:
    """Reconstruct the exact immutable ForecastPrediction from a stored row,
    including its nested ConsensusFeatureVector. The model's own __post_init__
    revalidates every field and enforces the prediction<->snapshot identity match,
    so malformed JSON / missing keys / identity mismatch / bad horizons / bad
    reference source all fail closed. Uses ONLY the versions stored on the row —
    never the current config — so historical identity is preserved."""
    if not isinstance(row, Mapping):
        raise ShadowRecoveryError("prediction row must be a mapping")
    try:
        snapshot = hydrate_consensus_snapshot(row["consensus_snapshot"])
        return ForecastPrediction(
            symbol=row["symbol"], market_type=row["market_type"], timeframe=row["timeframe"],
            bucket_ts=row["bucket_ts"], feature_schema_version=row["feature_schema_version"],
            calculation_version=row["calculation_version"], rule_version=row["rule_version"],
            direction=row["direction"], confidence=row["confidence"],
            horizon_set=tuple(row["horizon_set"]), reasons=tuple(row["reasons"]),
            component_scores=dict(row["component_scores"]), final_score=row["final_score"],
            reference_price=row["reference_price"], reference_price_source=row["reference_price_source"],
            exchanges_expected_max=row["exchanges_expected_max"],
            min_coverage_ratio=row["min_coverage_ratio"],
            data_confidence_overall=row["data_confidence_overall"],
            consensus_confidence=row["consensus_confidence"],
            is_partial_consensus=row["is_partial_consensus"], consensus_snapshot=snapshot,
            config_hash=row["config_hash"], config_version=row["config_version"],
            code_version=row["code_version"])
    except ShadowRecoveryError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise ShadowRecoveryError(f"malformed prediction row: {exc}") from exc


# ============================================================================
# Aggregate report
# ============================================================================
@dataclass(frozen=True)
class ShadowRecoveryReport:
    lock_status: str
    latest_closed_bucket: datetime
    recovery_lookback_buckets: int
    catchup_truncated_by_lookback: bool
    catchup_truncated_by_cap: bool
    watermark_before: Optional[datetime]
    watermark_after: Optional[datetime]
    prediction_buckets_planned: int
    prediction_buckets_attempted: int
    per_bucket_status: tuple            # ((bucket_ts, status), ...)
    outcome_jobs_discovered: int
    outcome_jobs_attempted: int
    outcome_evaluations_complete: int
    outcome_evaluations_incomplete: int
    horizons_represented: tuple
    writes_enabled: bool
    stage2_global_enabled: bool
    reference_exchange: str
    code_version: str

    def _count(self, wanted: str) -> int:
        return sum(1 for _b, status in self.per_bucket_status if status == wanted)


def _report_to_jsonable(report: ShadowRecoveryReport) -> dict:
    return {
        "command": SHADOW_RECOVERY,
        "lock_status": report.lock_status,
        "latest_closed_bucket": _iso_utc(report.latest_closed_bucket),
        "recovery_lookback_buckets": report.recovery_lookback_buckets,
        "catchup_truncated_by_lookback": report.catchup_truncated_by_lookback,
        "catchup_truncated_by_cap": report.catchup_truncated_by_cap,
        "watermark_before": _iso_utc(report.watermark_before) if report.watermark_before else None,
        "watermark_after": _iso_utc(report.watermark_after) if report.watermark_after else None,
        "prediction_buckets_planned": report.prediction_buckets_planned,
        "prediction_buckets_attempted": report.prediction_buckets_attempted,
        "per_bucket_prediction_status": [
            {"bucket_ts": _iso_utc(b), "status": s} for b, s in report.per_bucket_status],
        "prediction_inserted": report._count(PREDICTION_INSERTED),
        "prediction_duplicate": report._count(PREDICTION_DUPLICATE),
        "prediction_skipped_no_consensus": report._count(PREDICTION_SKIPPED_NO_CONSENSUS),
        "prediction_skipped_reference_unavailable": report._count(
            PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE),
        "outcome_jobs_discovered": report.outcome_jobs_discovered,
        "outcome_jobs_attempted": report.outcome_jobs_attempted,
        "outcome_evaluations_complete": report.outcome_evaluations_complete,
        "outcome_evaluations_incomplete": report.outcome_evaluations_incomplete,
        "horizons_represented": list(report.horizons_represented),
        "writes_enabled": report.writes_enabled,
        "stage2_global_enabled": report.stage2_global_enabled,
        "reference_exchange": report.reference_exchange,
        "code_version": report.code_version,
    }


def render_shadow_recovery_report_json(report: ShadowRecoveryReport) -> str:
    import json
    return json.dumps(_report_to_jsonable(report), sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def render_shadow_recovery_report(report: ShadowRecoveryReport) -> str:
    j = _report_to_jsonable(report)
    lines = [
        "=== SHADOW RECOVERY ===",
        f"lock:             {j['lock_status']}",
        f"latest_closed:    {j['latest_closed_bucket']}",
        f"stage2_enabled:   {j['stage2_global_enabled']}",
        f"writes_enabled:   {'yes' if j['writes_enabled'] else 'no'}",
        f"reference:        {j['reference_exchange']}",
        f"code_version:     {j['code_version']}",
        f"watermark:        {j['watermark_before']} -> {j['watermark_after']}",
        f"lookback_buckets: {j['recovery_lookback_buckets']} "
        f"(trunc lookback={j['catchup_truncated_by_lookback']} cap={j['catchup_truncated_by_cap']})",
        f"prediction buckets: planned={j['prediction_buckets_planned']} "
        f"attempted={j['prediction_buckets_attempted']} "
        f"inserted={j['prediction_inserted']} dup={j['prediction_duplicate']} "
        f"no_consensus={j['prediction_skipped_no_consensus']} "
        f"ref_unavailable={j['prediction_skipped_reference_unavailable']}",
        f"outcomes: discovered={j['outcome_jobs_discovered']} "
        f"attempted={j['outcome_jobs_attempted']} "
        f"complete={j['outcome_evaluations_complete']} "
        f"incomplete={j['outcome_evaluations_incomplete']} "
        f"horizons={','.join(j['horizons_represented']) or '(none)'}",
    ]
    return "\n".join(lines)


# ============================================================================
# Orchestration
# ============================================================================
def _lock_held_report(latest_closed, reference_exchange, code_version,
                      stage2_config) -> ShadowRecoveryReport:
    return ShadowRecoveryReport(
        lock_status=LOCK_HELD_SKIPPED, latest_closed_bucket=latest_closed,
        recovery_lookback_buckets=RECOVERY_LOOKBACK_BUCKETS,
        catchup_truncated_by_lookback=False, catchup_truncated_by_cap=False,
        watermark_before=None, watermark_after=None,
        prediction_buckets_planned=0, prediction_buckets_attempted=0,
        per_bucket_status=(), outcome_jobs_discovered=0, outcome_jobs_attempted=0,
        outcome_evaluations_complete=0, outcome_evaluations_incomplete=0,
        horizons_represented=(), writes_enabled=False,
        stage2_global_enabled=stage2_config.enabled,
        reference_exchange=reference_exchange, code_version=code_version)


async def execute_shadow_recovery(
    db,
    stage1_config,
    stage2_config,
    *,
    now: datetime,
    reference_exchange: str,
    explicit_code_version: Optional[str],
    metadata_fetch_json=None,
    max_catchup_buckets: int = DEFAULT_MAX_CATCHUP_BUCKETS,
    max_outcome_jobs: int = DEFAULT_MAX_OUTCOME_JOBS,
) -> ShadowRecoveryReport:
    """One bounded automatic recovery pass. See module docstring. All validation
    happens before the advisory lock; the lock is released on every exit path."""
    symbol, exchanges, resolved = _resolve_shadow_scope(
        stage1_config, stage2_config, reference_exchange=reference_exchange)
    validate_operational_cap(max_catchup_buckets, "max_catchup_buckets", MAX_CATCHUP_BUCKETS_LIMIT)
    validate_operational_cap(max_outcome_jobs, "max_outcome_jobs", MAX_OUTCOME_JOBS_LIMIT)
    soft_grace_s = resolved["bucket_close"]["soft_grace_s"]
    latest_closed = select_latest_closed_5m_bucket(now, soft_grace_s=soft_grace_s)
    code_version = resolve_code_version(explicit=explicit_code_version)
    lock_key = shadow_recovery_lock_key(RUNNER_NAME, symbol, _MARKET_TYPE, _TIMEFRAME)

    async with db.shadow_recovery_lock(lock_key) as acquired:
        if not acquired:
            # Another runner holds the lock: exit cleanly, zero writes.
            return _lock_held_report(latest_closed, reference_exchange, code_version, stage2_config)

        # --- bootstrap once (tech-lead review 4992495660: the SAME shared
        # helper execute_shadow_once uses -- never duplicated separately) ---
        await _bootstrap_stage2_schema_and_revision(db, stage2_config, symbol)
        await db.seed_symbols(symbol_seed_rows())
        await db.seed_symbol_exchange_capabilities(symbol_exchange_capability_seed_rows())
        await _bootstrap_instrument_metadata(
            db, exchanges, symbol, metadata_fetch_json=metadata_fetch_json)

        # --- prediction catch-up ---
        watermark_before = await db.fetch_shadow_watermark(
            runner_name=RUNNER_NAME, symbol=symbol, market_type=_MARKET_TYPE, timeframe=_TIMEFRAME)
        newest_prediction = None
        if watermark_before is None:
            newest_prediction = await db.fetch_newest_prediction_bucket(
                symbol=symbol, market_type=_MARKET_TYPE, timeframe=_TIMEFRAME)
        plan = plan_prediction_buckets(
            watermark=watermark_before, newest_prediction_bucket=newest_prediction,
            latest_closed=latest_closed, max_buckets=max_catchup_buckets,
            lookback_buckets=RECOVERY_LOOKBACK_BUCKETS)

        availability = await db.fetch_shadow_liquidation_availability(
            exchanges=exchanges, symbol=symbol, market_type=_MARKET_TYPE)

        per_bucket: list = []
        watermark_after = watermark_before
        for bucket_ts in plan.buckets:      # oldest-first
            result = await process_shadow_cycle(
                db, db, stage2_config, exchanges=exchanges, symbol=symbol,
                market_type=_MARKET_TYPE, timeframe=_TIMEFRAME, bucket_ts=bucket_ts,
                code_version=code_version,
                liquidation_feed_available_by_exchange=availability,
                reference_exchange=reference_exchange, due_outcome_jobs=())
            # advance the watermark ONLY after the bucket returned successfully
            await db.advance_shadow_watermark(
                runner_name=RUNNER_NAME, symbol=symbol, market_type=_MARKET_TYPE,
                timeframe=_TIMEFRAME, bucket_ts=bucket_ts)
            watermark_after = bucket_ts
            per_bucket.append((bucket_ts, result.prediction_status))

        # --- outcome maturation ---
        lookback_start = latest_closed - OUTCOME_LOOKBACK_BUCKETS * _STEP
        candidate_rows = await db.fetch_recovery_prediction_candidates(
            symbol=symbol, market_type=_MARKET_TYPE, timeframe=_TIMEFRAME,
            lookback_start=lookback_start, limit=OUTCOME_CANDIDATE_ROW_LIMIT)
        due_candidates: list = []           # (prediction, horizon, evaluation_exchange, outcome_version)
        for row in candidate_rows:
            prediction = hydrate_forecast_prediction(row)
            evaluation_exchange = derive_evaluation_exchange(prediction.reference_price_source)
            for horizon in due_horizons(prediction, now, soft_grace_s):
                due_candidates.append(
                    (prediction, horizon, evaluation_exchange, DEFAULT_OUTCOME_VERSION))

        antijoin_input = [
            (p.bucket_ts, p.calculation_version, p.rule_version, h, ex, ov)
            for (p, h, ex, ov) in due_candidates]
        missing_rows = await db.fetch_missing_outcome_identities(
            symbol=symbol, market_type=_MARKET_TYPE, timeframe=_TIMEFRAME,
            candidates=antijoin_input, evaluation_price_source=EVALUATION_PRICE_SOURCE)
        missing_keys = {
            (r["bucket_ts"], r["calculation_version"], r["rule_version"],
             r["horizon"], r["evaluation_exchange"], r["outcome_version"])
            for r in missing_rows}

        discovered = [
            cand for cand in due_candidates
            if (cand[0].bucket_ts, cand[0].calculation_version, cand[0].rule_version,
                cand[1], cand[2], cand[3]) in missing_keys]
        jobs = [DueOutcomeJob(p, h, ex, ov) for (p, h, ex, ov) in discovered[:max_outcome_jobs]]

        complete = incomplete = 0
        horizons_seen: set = set()
        for job in jobs:
            evaluation = await process_forecast_outcome_horizon(
                db, db, job.prediction, horizon=job.horizon,
                evaluation_exchange=job.evaluation_exchange, outcome_version=job.outcome_version)
            horizons_seen.add(job.horizon)
            if evaluation.status == "COMPLETE":
                complete += 1
            else:
                incomplete += 1

        horizons_represented = tuple(h for h in OUTCOME_HORIZONS if h in horizons_seen)

        return ShadowRecoveryReport(
            lock_status=LOCK_ACQUIRED, latest_closed_bucket=latest_closed,
            recovery_lookback_buckets=RECOVERY_LOOKBACK_BUCKETS,
            catchup_truncated_by_lookback=plan.truncated_by_lookback,
            catchup_truncated_by_cap=plan.truncated_by_cap,
            watermark_before=watermark_before, watermark_after=watermark_after,
            prediction_buckets_planned=len(plan.buckets),
            prediction_buckets_attempted=len(per_bucket),
            per_bucket_status=tuple(per_bucket),
            outcome_jobs_discovered=len(discovered),
            outcome_jobs_attempted=len(jobs),
            outcome_evaluations_complete=complete,
            outcome_evaluations_incomplete=incomplete,
            horizons_represented=horizons_represented, writes_enabled=True,
            stage2_global_enabled=stage2_config.enabled,
            reference_exchange=reference_exchange, code_version=code_version)


# ============================================================================
# Explicit --shadow-bucket-ts, under the SAME advisory lock as automatic
# recovery. A manual write run and the timer must never run concurrently: both
# invocations derive the identical deterministic lock key
# (shadow_recovery_lock_key(RUNNER_NAME, symbol, market_type, timeframe)) — there
# is exactly one lock namespace for every write-capable --shadow-once path.
# ============================================================================
@dataclass(frozen=True)
class LockedOnceReport:
    lock_status: str
    execution: Optional[ShadowExecutionReport]
    bucket_ts: datetime
    reference_exchange: str
    code_version: str
    stage2_global_enabled: bool

    def __post_init__(self) -> None:
        if self.lock_status not in (LOCK_ACQUIRED, LOCK_HELD_SKIPPED):
            raise ShadowRecoveryError(f"invalid lock_status {self.lock_status!r}")
        if self.lock_status == LOCK_ACQUIRED:
            if type(self.execution) is not ShadowExecutionReport:
                raise ShadowRecoveryError("ACQUIRED requires an exact ShadowExecutionReport")
        elif self.execution is not None:
            raise ShadowRecoveryError("LOCK_HELD_SKIPPED must have execution=None")


async def execute_shadow_once_locked(
    db,
    stage1_config,
    stage2_config,
    *,
    now: datetime,
    explicit_bucket_ts: str,
    reference_exchange: str,
    explicit_code_version: Optional[str],
    metadata_fetch_json=None,
) -> LockedOnceReport:
    """Explicit one-bucket `--shadow-once --shadow-bucket-ts ...` run, guarded by
    the SAME deterministic advisory lock as automatic recovery (never a second
    lock namespace). Processes exactly the one selected bucket via the existing
    `execute_shadow_once` — it does NOT read or advance the recovery watermark,
    perform catch-up, or discover/process broad outcomes. If another runner
    (the timer, or a concurrent manual run) holds the lock, this exits cleanly
    with zero schema/seed/metadata/feature/consensus/prediction writes."""
    if not isinstance(explicit_bucket_ts, str) or not explicit_bucket_ts.strip():
        raise ShadowRecoveryError(
            "execute_shadow_once_locked requires a non-empty explicit bucket timestamp")
    # All CLI/config/time validation happens BEFORE the lock is even requested.
    symbol, exchanges, resolved = _resolve_shadow_scope(
        stage1_config, stage2_config, reference_exchange=reference_exchange)
    bucket_ts = parse_shadow_bucket_ts(explicit_bucket_ts, now=now)
    code_version = resolve_code_version(explicit=explicit_code_version)
    lock_key = shadow_recovery_lock_key(RUNNER_NAME, symbol, _MARKET_TYPE, _TIMEFRAME)

    async with db.shadow_recovery_lock(lock_key) as acquired:
        if not acquired:
            return LockedOnceReport(
                lock_status=LOCK_HELD_SKIPPED, execution=None, bucket_ts=bucket_ts,
                reference_exchange=reference_exchange, code_version=code_version,
                stage2_global_enabled=stage2_config.enabled)
        execution = await execute_shadow_once(
            db, stage1_config, stage2_config, now=now,
            explicit_bucket_ts=explicit_bucket_ts, reference_exchange=reference_exchange,
            explicit_code_version=explicit_code_version, metadata_fetch_json=metadata_fetch_json)
        return LockedOnceReport(
            lock_status=LOCK_ACQUIRED, execution=execution, bucket_ts=bucket_ts,
            reference_exchange=reference_exchange, code_version=code_version,
            stage2_global_enabled=stage2_config.enabled)


def _locked_once_to_jsonable(report: LockedOnceReport) -> dict:
    """Preserve the existing one-bucket JSON fields exactly (via
    execution_report_to_jsonable) when the lock was acquired, plus the new
    `lock_status` field. On LOCK_HELD_SKIPPED (no execution ran) report the
    minimal equivalent shape with writes_enabled=False."""
    if report.execution is not None:
        body = execution_report_to_jsonable(report.execution)
    else:
        body = {
            "command": SHADOW_ONCE,
            "bucket_selection": BUCKET_EXPLICIT,
            "bucket_ts": _iso_utc(report.bucket_ts),
            "stage2_global_enabled": report.stage2_global_enabled,
            "writes_enabled": False,
            "reference_exchange": report.reference_exchange,
            "code_version": report.code_version,
        }
    body["lock_status"] = report.lock_status
    return body


def render_locked_once_report_json(report: LockedOnceReport) -> str:
    import json
    return json.dumps(_locked_once_to_jsonable(report), sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def render_locked_once_report(report: LockedOnceReport) -> str:
    """When the lock was acquired, the body is EXACTLY the existing one-bucket
    human report (preserved as-is), with a leading lock-status line. When the
    lock was held, render the minimal equivalent (zero writes performed)."""
    if report.execution is not None:
        return f"lock:             {report.lock_status}\n" + render_shadow_execution_report(report.execution)
    return "\n".join([
        "=== SHADOW ONCE ===",
        f"lock:             {report.lock_status}",
        f"bucket_ts:        {_iso_utc(report.bucket_ts)} ({BUCKET_EXPLICIT})",
        f"stage2_enabled:   {report.stage2_global_enabled}",
        "writes_enabled:   no",
        f"reference:        {report.reference_exchange}",
        f"code_version:     {report.code_version}",
    ])
