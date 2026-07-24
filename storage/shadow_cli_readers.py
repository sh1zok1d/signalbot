"""
Read-only storage helpers for the operational shadow CLI (one-shot / dry-run /
status). Pure storage layer: static/trusted SQL and immutable detached results
only. Imports NO analytics, runtime, or main module, and NO network client. No
writes, no clock, no schema creation.

Two concerns live here:
  1. Liquidation availability — the `liquidation_feed_available_by_exchange`
     mapping that process_shadow_cycle requires, derived from the seeded
     symbol_exchange_capabilities rows (never from WS client classes).
  2. Read-only status — schema presence (to_regclass), per-exchange
     prerequisites, the latest stored prediction, and its recorded outcomes.
     Status is NOT recovery: it reads only the single latest prediction and the
     outcomes already recorded for it; it never scans for predictions missing
     outcomes and never decides an outcome is "due".
"""
from __future__ import annotations

import json
from types import MappingProxyType
from typing import Mapping, Sequence


class ShadowCliReaderError(ValueError):
    """Invalid shadow-CLI reader argument or an unexpected/malformed DB row
    (request args are validated before any DB access)."""


# The Stage 2 tables the status state-machine reasons about, in a stable order.
SHADOW_STATUS_TABLES = (
    "symbols",
    "exchange_instruments",
    "symbol_exchange_capabilities",
    "exchange_feature_vectors",
    "consensus_feature_vectors",
    "forecast_predictions",
    "forecast_outcomes",
)

# The subset that must exist before per-exchange prerequisites can be read.
_PREREQUISITE_TABLES = ("exchange_instruments", "symbol_exchange_capabilities")


# ---- static, trusted SQL (no SELECT *, no dynamic identifiers) --------------
SHADOW_LIQUIDATION_AVAILABILITY_SQL = """
SELECT exchange, live_supported, enabled, coverage_type
FROM symbol_exchange_capabilities
WHERE exchange = ANY($1::text[])
  AND symbol = $2
  AND market_type = $3
  AND metric = 'liquidations'
"""

SHADOW_SCHEMA_STATE_SQL = """
SELECT
    to_regclass('public.symbols')::text                       AS symbols,
    to_regclass('public.exchange_instruments')::text          AS exchange_instruments,
    to_regclass('public.symbol_exchange_capabilities')::text  AS symbol_exchange_capabilities,
    to_regclass('public.exchange_feature_vectors')::text      AS exchange_feature_vectors,
    to_regclass('public.consensus_feature_vectors')::text     AS consensus_feature_vectors,
    to_regclass('public.forecast_predictions')::text          AS forecast_predictions,
    to_regclass('public.forecast_outcomes')::text             AS forecast_outcomes
"""

SHADOW_PREREQUISITES_SQL = """
SELECT
    req.exchange                        AS exchange,
    (ei.exchange IS NOT NULL)           AS instrument_present,
    ei.is_stale                         AS instrument_is_stale,
    (cap.exchange IS NOT NULL)          AS liquidation_capability_present,
    cap.live_supported                  AS liquidation_live_supported,
    cap.enabled                         AS liquidation_enabled,
    cap.coverage_type                   AS liquidation_coverage_type
FROM unnest($1::text[]) WITH ORDINALITY AS req(exchange, ord)
LEFT JOIN exchange_instruments ei
    ON ei.exchange = req.exchange AND ei.symbol = $2 AND ei.market_type = $3
LEFT JOIN symbol_exchange_capabilities cap
    ON cap.exchange = req.exchange AND cap.symbol = $2 AND cap.market_type = $3
   AND cap.metric = 'liquidations'
ORDER BY req.ord ASC
"""

LATEST_SHADOW_PREDICTION_SQL = """
SELECT
    symbol, market_type, timeframe, bucket_ts, calculation_version, rule_version,
    direction, confidence, final_score, reference_price, reference_price_source,
    horizon_set, reasons, exchanges_expected_max, min_coverage_ratio,
    data_confidence_overall, consensus_confidence, is_partial_consensus,
    config_version, code_version, created_at
FROM forecast_predictions
WHERE symbol = $1 AND market_type = $2 AND timeframe = $3
ORDER BY bucket_ts DESC, created_at DESC, calculation_version DESC, rule_version DESC
LIMIT 1
"""

LATEST_SHADOW_OUTCOMES_SQL = """
SELECT
    horizon, outcome_version, evaluation_exchange, evaluation_price_source,
    target_close_price, market_return_pct, directional_return_pct, mfe_pct,
    mae_pct, computed_at
FROM forecast_outcomes
WHERE symbol = $1 AND market_type = $2 AND timeframe = $3
  AND bucket_ts = $4 AND calculation_version = $5 AND rule_version = $6
ORDER BY
    CASE horizon WHEN '15m' THEN 0 WHEN '1h' THEN 1 WHEN '4h' THEN 2 ELSE 3 END ASC,
    evaluation_exchange ASC,
    outcome_version ASC
"""


# ---- argument validation (before any DB access) ----------------------------
def _validate_exchanges(exchanges) -> tuple[str, ...]:
    if isinstance(exchanges, (str, bytes, bytearray)) or not isinstance(exchanges, Sequence):
        raise ShadowCliReaderError(
            f"exchanges must be a Sequence (list/tuple), got {type(exchanges).__name__}")
    values = tuple(exchanges)
    if not values:
        raise ShadowCliReaderError("exchanges must be non-empty")
    seen: set[str] = set()
    for ex in values:
        if not isinstance(ex, str) or not ex.strip():
            raise ShadowCliReaderError(f"exchange must be a non-empty string, got {ex!r}")
        if ex in seen:
            raise ShadowCliReaderError(f"duplicate exchange {ex!r}")
        seen.add(ex)
    return values


def _nonblank(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ShadowCliReaderError(f"{name} must be a non-empty string")
    return value


def validate_liquidation_availability_args(*, exchanges, symbol, market_type) -> tuple[str, ...]:
    values = _validate_exchanges(exchanges)
    _nonblank(symbol, "symbol")
    _nonblank(market_type, "market_type")
    return values


def validate_shadow_status_args(*, exchanges, symbol, market_type, timeframe) -> tuple[str, ...]:
    values = _validate_exchanges(exchanges)
    _nonblank(symbol, "symbol")
    _nonblank(market_type, "market_type")
    _nonblank(timeframe, "timeframe")
    return values


def _require_bool(value, name: str) -> bool:
    if not isinstance(value, bool):
        raise ShadowCliReaderError(f"{name} must be a bool, got {type(value).__name__}")
    return value


# ---- liquidation availability ----------------------------------------------
async def read_shadow_liquidation_availability(
    conn,
    *,
    exchanges: Sequence[str],
    symbol: str,
    market_type: str,
) -> Mapping[str, bool]:
    """One fetch on `conn`; return an immutable MappingProxyType {exchange: bool}
    in caller exchange order. Requires exactly one liquidation-capability row per
    requested exchange (missing/duplicate/unexpected rows are rejected — a missing
    exchange is never silently filled with False). Availability =
    live_supported is True AND enabled is True AND coverage_type != 'unavailable'.
    Args are NOT re-validated here (the Database method validates first)."""
    requested = tuple(exchanges)
    records = await conn.fetch(
        SHADOW_LIQUIDATION_AVAILABILITY_SQL, list(requested), symbol, market_type)
    by_exchange: dict[str, dict] = {}
    requested_set = set(requested)
    for rec in records:
        ex = rec["exchange"]
        if ex not in requested_set:
            raise ShadowCliReaderError(f"unexpected exchange row {ex!r}")
        if ex in by_exchange:
            raise ShadowCliReaderError(f"duplicate capability row for {ex!r}")
        by_exchange[ex] = dict(rec)
    availability: dict[str, bool] = {}
    for ex in requested:
        if ex not in by_exchange:
            raise ShadowCliReaderError(
                f"no liquidations capability row for {ex!r} (not filling with False)")
        row = by_exchange[ex]
        live = _require_bool(row["live_supported"], f"{ex}.live_supported")
        enabled = _require_bool(row["enabled"], f"{ex}.enabled")
        coverage_type = row["coverage_type"]
        if not isinstance(coverage_type, str) or not coverage_type:
            raise ShadowCliReaderError(f"{ex}.coverage_type must be a non-empty string")
        availability[ex] = bool(live and enabled and coverage_type != "unavailable")
    return MappingProxyType(availability)


# ---- read-only status ------------------------------------------------------
def _schema_presence(schema_row) -> "dict[str, bool]":
    return {t: schema_row[t] is not None for t in SHADOW_STATUS_TABLES}


async def read_shadow_status(
    conn,
    *,
    exchanges: Sequence[str],
    symbol: str,
    market_type: str,
    timeframe: str,
) -> Mapping:
    """Run the fixed read-only status queries on `conn` and return a detached,
    immutable snapshot. Reads only tables that exist (to_regclass-gated), so a
    fresh DB yields NOT_INITIALIZED instead of raising UndefinedTable. Args are
    NOT re-validated here (the Database method validates first)."""
    requested = tuple(exchanges)
    schema_row = await conn.fetchrow(SHADOW_SCHEMA_STATE_SQL)
    present = _schema_presence(schema_row)
    all_present = all(present.values())
    none_present = not any(present.values())

    prerequisites: tuple = ()
    latest_prediction = None
    outcomes: tuple = ()

    if none_present:
        state = "NOT_INITIALIZED"
    elif not all_present:
        state = "PARTIAL_SCHEMA"
    else:
        # All required tables exist: safe to read prerequisites, the latest
        # prediction, and (only if a prediction exists) its recorded outcomes.
        prereq_records = await conn.fetch(
            SHADOW_PREREQUISITES_SQL, list(requested), symbol, market_type)
        prerequisites = tuple(_detach_prerequisite(rec) for rec in prereq_records)

        pred_row = await conn.fetchrow(
            LATEST_SHADOW_PREDICTION_SQL, symbol, market_type, timeframe)
        if pred_row is None:
            state = "EMPTY"
        else:
            latest_prediction = _detach_prediction(pred_row)
            outcome_records = await conn.fetch(
                LATEST_SHADOW_OUTCOMES_SQL, symbol, market_type, timeframe,
                pred_row["bucket_ts"], pred_row["calculation_version"],
                pred_row["rule_version"])
            outcomes = tuple(_detach_outcome(rec) for rec in outcome_records)
            state = "READY"

    return MappingProxyType({
        "state": state,
        "schema_present": MappingProxyType(dict(present)),
        "prerequisites": prerequisites,
        "latest_prediction": latest_prediction,
        "outcomes": outcomes,
    })


def _detach_prerequisite(rec) -> Mapping:
    return MappingProxyType({
        "exchange": rec["exchange"],
        "instrument_present": bool(rec["instrument_present"]),
        "instrument_is_stale": rec["instrument_is_stale"],
        "liquidation_capability_present": bool(rec["liquidation_capability_present"]),
        "liquidation_live_supported": rec["liquidation_live_supported"],
        "liquidation_enabled": rec["liquidation_enabled"],
        "liquidation_coverage_type": rec["liquidation_coverage_type"],
    })


def _parse_json_array(value, name: str) -> tuple:
    """forecast_predictions.horizon_set / reasons are JSONB; asyncpg returns them
    as JSON text. Parse to a detached tuple of strings."""
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    if isinstance(value, str):
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise ShadowCliReaderError(f"{name} must be a JSON array")
        return tuple(parsed)
    raise ShadowCliReaderError(f"{name} has unexpected type {type(value).__name__}")


def _detach_prediction(rec) -> Mapping:
    return MappingProxyType({
        "symbol": rec["symbol"],
        "market_type": rec["market_type"],
        "timeframe": rec["timeframe"],
        "bucket_ts": rec["bucket_ts"],
        "calculation_version": rec["calculation_version"],
        "rule_version": rec["rule_version"],
        "direction": rec["direction"],
        "confidence": rec["confidence"],
        "final_score": rec["final_score"],
        "reference_price": rec["reference_price"],
        "reference_price_source": rec["reference_price_source"],
        "horizon_set": _parse_json_array(rec["horizon_set"], "horizon_set"),
        "reasons": _parse_json_array(rec["reasons"], "reasons"),
        "exchanges_expected_max": rec["exchanges_expected_max"],
        "min_coverage_ratio": rec["min_coverage_ratio"],
        "data_confidence_overall": rec["data_confidence_overall"],
        "consensus_confidence": rec["consensus_confidence"],
        "is_partial_consensus": rec["is_partial_consensus"],
        "config_version": rec["config_version"],
        "code_version": rec["code_version"],
        "created_at": rec["created_at"],
    })


def _detach_outcome(rec) -> Mapping:
    return MappingProxyType({
        "horizon": rec["horizon"],
        "outcome_version": rec["outcome_version"],
        "evaluation_exchange": rec["evaluation_exchange"],
        "evaluation_price_source": rec["evaluation_price_source"],
        "target_close_price": rec["target_close_price"],
        "market_return_pct": rec["market_return_pct"],
        "directional_return_pct": rec["directional_return_pct"],
        "mfe_pct": rec["mfe_pct"],
        "mae_pct": rec["mae_pct"],
        "computed_at": rec["computed_at"],
    })
