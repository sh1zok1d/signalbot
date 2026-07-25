"""
Storage-layer SQL + validation for the bounded automatic shadow recovery pass.

Pure storage: static/trusted SQL and immutable detached results only. Imports NO
analytics, runtime, or main module and NO network client. It makes no analytics
decision (no dueness/clock logic, no hydration into analytics models) — it only
reads/writes rows and returns detached mappings/scalars. The watermark upsert is
monotonic; the outcome discovery is a real anti-join (LEFT JOIN ... IS NULL).

The PostgreSQL advisory-lock helpers deliberately keep the SQL here while the
Database layer owns the dedicated connection for the session-scoped lock.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Mapping, Optional, Sequence


class ShadowRecoveryReaderError(ValueError):
    """Invalid shadow-recovery reader/writer argument (validated before DB access)."""


# ---- advisory lock (session-scoped; connection ownership lives in db.py) ----
ADVISORY_TRY_LOCK_SQL = "SELECT pg_try_advisory_lock($1)"
ADVISORY_UNLOCK_SQL = "SELECT pg_advisory_unlock($1)"


# ---- watermark --------------------------------------------------------------
SHADOW_WATERMARK_SELECT_SQL = """
SELECT last_completed_bucket_ts
FROM shadow_recovery_watermarks
WHERE runner_name = $1 AND symbol = $2 AND market_type = $3 AND timeframe = $4
"""

# Monotonic upsert: the stored watermark can only ever move FORWARD (GREATEST).
SHADOW_WATERMARK_UPSERT_SQL = """
INSERT INTO shadow_recovery_watermarks
    (runner_name, symbol, market_type, timeframe, last_completed_bucket_ts, updated_at)
VALUES ($1, $2, $3, $4, $5, now())
ON CONFLICT (runner_name, symbol, market_type, timeframe) DO UPDATE SET
    last_completed_bucket_ts =
        GREATEST(shadow_recovery_watermarks.last_completed_bucket_ts, EXCLUDED.last_completed_bucket_ts),
    updated_at = now()
"""


# ---- prediction discovery ---------------------------------------------------
NEWEST_PREDICTION_BUCKET_SQL = """
SELECT bucket_ts
FROM forecast_predictions
WHERE symbol = $1 AND market_type = $2 AND timeframe = $3
ORDER BY bucket_ts DESC
LIMIT 1
"""

# Bounded candidate predictions (within the recovery lookback) whose horizons may
# now be due for outcome evaluation. Explicit columns (no SELECT *), deterministic
# order, and a hard LIMIT so neither the query nor the caller list is unbounded.
RECOVERY_PREDICTION_CANDIDATES_SQL = """
SELECT
    symbol, market_type, timeframe, bucket_ts, feature_schema_version,
    calculation_version, rule_version, direction, confidence, horizon_set, reasons,
    component_scores, final_score, reference_price, reference_price_source,
    exchanges_expected_max, min_coverage_ratio, data_confidence_overall,
    consensus_confidence, is_partial_consensus, consensus_snapshot,
    config_hash, config_version, code_version
FROM forecast_predictions
WHERE symbol = $1 AND market_type = $2 AND timeframe = $3 AND bucket_ts >= $4
ORDER BY bucket_ts ASC, calculation_version ASC, rule_version ASC
LIMIT $5
"""

# Real anti-join: of the caller-supplied candidate outcome identities (zipped
# parallel arrays), return exactly those NOT already present in forecast_outcomes,
# in caller order. evaluation_price_source is a constant ($8) for the whole batch.
DUE_OUTCOME_ANTIJOIN_SQL = """
SELECT
    cand.bucket_ts, cand.calculation_version, cand.rule_version,
    cand.horizon, cand.evaluation_exchange, cand.outcome_version
FROM unnest($4::timestamptz[], $5::text[], $6::text[], $7::text[], $8::text[], $9::text[])
     WITH ORDINALITY AS cand(bucket_ts, calculation_version, rule_version,
                             horizon, evaluation_exchange, outcome_version, ord)
LEFT JOIN forecast_outcomes fo
    ON  fo.symbol = $1 AND fo.market_type = $2 AND fo.timeframe = $3
    AND fo.bucket_ts = cand.bucket_ts
    AND fo.calculation_version = cand.calculation_version
    AND fo.rule_version = cand.rule_version
    AND fo.horizon = cand.horizon
    AND fo.evaluation_exchange = cand.evaluation_exchange
    AND fo.evaluation_price_source = $10
    AND fo.outcome_version = cand.outcome_version
WHERE fo.bucket_ts IS NULL
ORDER BY cand.ord ASC
"""


# ---- validation -------------------------------------------------------------
def _nonblank(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ShadowRecoveryReaderError(f"{name} must be a non-empty string")
    return value


def _utc_5m(dt, name: str) -> datetime:
    if not isinstance(dt, datetime):
        raise ShadowRecoveryReaderError(f"{name} must be a datetime, got {type(dt).__name__}")
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ShadowRecoveryReaderError(f"{name} must be timezone-aware UTC")
    if dt.second != 0 or dt.microsecond != 0 or dt.minute % 5 != 0:
        raise ShadowRecoveryReaderError(f"{name} must be a whole-minute 5m-aligned UTC timestamp")
    return dt


def _pos_int(value, name: str, upper: int) -> int:
    if type(value) is not int:
        raise ShadowRecoveryReaderError(f"{name} must be an int")
    if not (1 <= value <= upper):
        raise ShadowRecoveryReaderError(f"{name} must be in [1, {upper}]")
    return value


def validate_scope(*, symbol, market_type, timeframe) -> None:
    _nonblank(symbol, "symbol")
    _nonblank(market_type, "market_type")
    _nonblank(timeframe, "timeframe")


def validate_runner_scope(*, runner_name, symbol, market_type, timeframe) -> None:
    _nonblank(runner_name, "runner_name")
    validate_scope(symbol=symbol, market_type=market_type, timeframe=timeframe)


# ---- watermark reads/writes -------------------------------------------------
async def read_shadow_watermark(conn, *, runner_name, symbol, market_type, timeframe
                                ) -> Optional[datetime]:
    validate_runner_scope(runner_name=runner_name, symbol=symbol,
                          market_type=market_type, timeframe=timeframe)
    return await conn.fetchval(
        SHADOW_WATERMARK_SELECT_SQL, runner_name, symbol, market_type, timeframe)


async def advance_shadow_watermark(conn, *, runner_name, symbol, market_type,
                                   timeframe, bucket_ts) -> None:
    validate_runner_scope(runner_name=runner_name, symbol=symbol,
                          market_type=market_type, timeframe=timeframe)
    _utc_5m(bucket_ts, "bucket_ts")
    await conn.execute(SHADOW_WATERMARK_UPSERT_SQL, runner_name, symbol,
                       market_type, timeframe, bucket_ts)


async def read_newest_prediction_bucket(conn, *, symbol, market_type, timeframe
                                        ) -> Optional[datetime]:
    validate_scope(symbol=symbol, market_type=market_type, timeframe=timeframe)
    return await conn.fetchval(NEWEST_PREDICTION_BUCKET_SQL, symbol, market_type, timeframe)


# ---- prediction candidates (detached rows; JSONB parsed to plain Python) ----
_JSONB_COLUMNS = ("horizon_set", "reasons", "component_scores", "consensus_snapshot")


def _parse_jsonb(value):
    if value is None or isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        return json.loads(value)
    raise ShadowRecoveryReaderError(f"unexpected JSONB python type {type(value).__name__}")


def _detach_prediction_row(rec) -> Mapping:
    out = {}
    for key in rec.keys():
        out[key] = _parse_jsonb(rec[key]) if key in _JSONB_COLUMNS else rec[key]
    return MappingProxyType(out)


async def read_recovery_prediction_candidates(conn, *, symbol, market_type, timeframe,
                                              lookback_start, limit) -> tuple:
    validate_scope(symbol=symbol, market_type=market_type, timeframe=timeframe)
    _utc_5m(lookback_start, "lookback_start")
    _pos_int(limit, "limit", 100000)
    records = await conn.fetch(
        RECOVERY_PREDICTION_CANDIDATES_SQL, symbol, market_type, timeframe,
        lookback_start, limit)
    return tuple(_detach_prediction_row(r) for r in records)


# ---- due-outcome anti-join --------------------------------------------------
async def read_missing_outcome_identities(conn, *, symbol, market_type, timeframe,
                                          candidates, evaluation_price_source) -> tuple:
    """`candidates` is a Sequence of (bucket_ts, calculation_version, rule_version,
    horizon, evaluation_exchange, outcome_version). Returns the subset NOT present
    in forecast_outcomes (real LEFT JOIN anti-join), as detached MappingProxyType
    rows in caller order."""
    validate_scope(symbol=symbol, market_type=market_type, timeframe=timeframe)
    _nonblank(evaluation_price_source, "evaluation_price_source")
    if isinstance(candidates, (str, bytes, bytearray)) or not isinstance(candidates, Sequence):
        raise ShadowRecoveryReaderError("candidates must be a Sequence")
    if not candidates:
        return ()
    bucket_ts, calc, rule, horizon, ex, ov = [], [], [], [], [], []
    for i, cand in enumerate(candidates):
        if len(cand) != 6:
            raise ShadowRecoveryReaderError(f"candidate {i} must be a 6-tuple")
        b, cv, rv, h, e, o = cand
        _utc_5m(b, f"candidate[{i}].bucket_ts")
        bucket_ts.append(b)
        calc.append(_nonblank(cv, f"candidate[{i}].calculation_version"))
        rule.append(_nonblank(rv, f"candidate[{i}].rule_version"))
        horizon.append(_nonblank(h, f"candidate[{i}].horizon"))
        ex.append(_nonblank(e, f"candidate[{i}].evaluation_exchange"))
        ov.append(_nonblank(o, f"candidate[{i}].outcome_version"))
    records = await conn.fetch(
        DUE_OUTCOME_ANTIJOIN_SQL, symbol, market_type, timeframe,
        bucket_ts, calc, rule, horizon, ex, ov, evaluation_price_source)
    return tuple(
        MappingProxyType({
            "bucket_ts": r["bucket_ts"],
            "calculation_version": r["calculation_version"],
            "rule_version": r["rule_version"],
            "horizon": r["horizon"],
            "evaluation_exchange": r["evaluation_exchange"],
            "outcome_version": r["outcome_version"],
        })
        for r in records)
