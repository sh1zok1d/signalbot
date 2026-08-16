"""
V2 aligned-input storage readers (Stage 3 — Multi-timeframe Alignment,
PR 2 of ~3, docs/FORECASTING_ROADMAP.md §I stage 3).

PR 1 (`analytics/forecasting_v2/alignment.py`) answered "which closed
bucket timestamp is legal?" This module answers the next, and only the
next, question: "given an already-selected legal timestamp/cutoff, how do
I read EXACTLY the corresponding Stage 2 data row(s)?" It does not decide
what those rows mean.

Three read primitives, each scoped to an explicit, caller-supplied
identity — never a wall-clock "latest":

  - `read_v2_consensus_feature` — the ONE `consensus_feature_vectors` row
    at an EXACT `bucket_ts` (never `<=`, never `ORDER BY bucket_ts DESC
    LIMIT 1`). Missing means `None`; there is no older-bucket fallback.
  - `read_v2_consensus_percentiles` — every `percentile_snapshots` row at
    an EXACT `bucket_ts`, pinned to `scope='consensus'`/`exchange=''`
    (exchange-scoped percentiles are out of scope for this PR). Missing
    means `()`; there is no older-bucket fallback.
  - `read_v2_data_health_at_cutoff` — for each requested `(exchange,
    metric)` pair, the LATEST `data_health_snapshots` row whose
    `snapshot_ts <= cutoff_ts` (an explicit, caller-supplied historical
    cutoff — never `now()`/`CURRENT_TIMESTAMP`). A row exactly at the
    cutoff is eligible; a row after it is never returned. This is
    "bounded latest," not "latest now," and it is the one place in this
    module where a `<=` comparison against a caller-supplied timestamp is
    legitimate (`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §2's own
    per-family table: health's no-lookahead mechanism IS a cutoff-bounded
    read, unlike consensus/percentiles' exact-bucket-identity mechanism).

Every read requires an explicit `calculation_version` — never inferred,
never the newest available, never omitted. `computed_at` (Stage 2's
DB-owned write-time metadata) is NEVER used to decide whether a row is
historically legal — Stage 2 corrections upsert rows in place under the
same `calculation_version` (§2.1), so a row's `computed_at` says nothing
about what the *feature value itself* logically represents; only the
row's own `bucket_ts`/`snapshot_ts` identity does. This module reads
CURRENT Stage 2 research truth — it does not, and cannot, reconstruct
what a table contained at some past wall-clock instant.

Layering decision — `timeframe` — deliberately documented, not left
implicit: this module requires `timeframe` to be a non-empty string and
nothing more. It does NOT import `analytics.forecasting_v2.alignment` to
re-validate against `TIMEFRAME_MINUTES`'s four V2 semantic timeframes,
because `storage -> analytics` is the wrong dependency direction (this
module is a lower layer that `analytics` code calls INTO, not the other
way around) — and this module's own SQL identity (matching
`consensus_feature_vectors`/`percentile_snapshots`' real `timeframe`
column) is timeframe-value-agnostic in any case. Strict V2 semantic
timeframe enumeration remains `analytics.forecasting_v2.alignment`'s job;
a caller here is trusted to have already picked a legal value there.

Pure storage layer: static, trusted, explicit-column SQL only (no
`SELECT *`, no dynamic identifiers, no query-builder abstraction); every
argument is validated BEFORE a connection is touched; every returned row
is detached (a plain, deeply-immutable `Mapping`, MappingProxyType/tuple
throughout, JSONB parsed and frozen) so nothing here retains the
connection or a mutable reference into a DB-returned object. No writes —
no `INSERT`/`UPDATE`/`DELETE`/`UPSERT`/`ON CONFLICT` appears in this
module's SQL. No wall clock (`datetime.now()`/`utcnow()`/`time.time()`),
no `random`/`uuid`, no imports from `runtime`/`main`/`notifications`, and
no imports from `analytics` of any kind.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping as _AbcMapping
from collections.abc import Sequence as _AbcSequence
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

__all__ = [
    "V2AlignmentReaderError",
    "read_v2_consensus_feature",
    "read_v2_consensus_percentiles",
    "read_v2_data_health_at_cutoff",
]


class V2AlignmentReaderError(ValueError):
    """Invalid reader argument, or a returned DB row that fails to match
    the identity that was explicitly requested (a fake/test connection
    misbehaving, or — for a real connection — a bug elsewhere; either way,
    never silently trusted). Raised before any DB access for argument
    errors; raised after fetch for row-identity/shape violations."""


# ---- static, trusted SQL (no SELECT *, no dynamic identifiers) --------------
# Column order matches analytics/feature_engine/consensus_models.py's
# ConsensusFeatureVector field order exactly (identity/version, per-family
# JSON maps, rolled-up reporting, direction agreement, robust aggregates,
# additive notional sums, liquidation provenance, dispersion/outliers,
# confidence), plus computed_at (metadata only — see module docstring) and
# provenance. EXACT bucket_ts match, never <=, never ORDER BY ... DESC LIMIT 1.
_CONSENSUS_FEATURE_SQL = """
SELECT symbol, market_type, timeframe, bucket_ts, feature_schema_version,
       calculation_version,
       coverage_by_metric, provenance_by_metric, data_confidence_by_metric,
       exchanges_expected_max, min_coverage_ratio, data_confidence_overall,
       price_direction_agreement, flow_direction_agreement, oi_direction_agreement,
       price_move_pct_median, range_width_pct_median, oi_change_pct_median,
       funding_rate_median, funding_rate_mad,
       volume_notional_usd_sum, taker_buy_notional_usd_sum,
       taker_sell_notional_usd_sum, taker_delta_notional_usd_sum,
       cvd_delta_notional_usd_sum,
       observed_long_liquidation_notional_sum, observed_short_liquidation_notional_sum,
       observed_liquidation_event_count_sum, liquidation_feed_quality_by_exchange,
       price_move_pct_mad, oi_change_pct_mad, outlier_exchanges,
       consensus_confidence, is_partial_consensus,
       computed_at, config_hash, config_version, code_version
FROM consensus_feature_vectors
WHERE symbol = $1 AND market_type = $2 AND timeframe = $3
  AND bucket_ts = $4 AND calculation_version = $5
"""

_CONSENSUS_JSON_COLUMNS = (
    "coverage_by_metric", "provenance_by_metric", "data_confidence_by_metric",
    "liquidation_feed_quality_by_exchange", "outlier_exchanges",
)
# NOT NULL in the schema; a NULL arriving here would itself be a bug.
_CONSENSUS_REQUIRED_JSON_COLUMNS = frozenset(
    {"coverage_by_metric", "provenance_by_metric", "data_confidence_by_metric"})

# EXACT bucket_ts match, pinned to scope='consensus'/exchange='' (§5:
# exchange-scoped percentiles are out of scope for this PR). Deterministic
# ordering — metric ASC, percentile_window ASC — since deciding which
# metric/window matters is NOT this reader's job.
_CONSENSUS_PERCENTILES_SQL = """
SELECT scope, exchange, symbol, market_type, metric, timeframe, percentile_window,
       bucket_ts, value, percentile_rank, sample_size,
       sample_window_start, sample_window_end, confidence_tier,
       computed_at, config_hash, config_version, code_version,
       feature_schema_version, calculation_version
FROM percentile_snapshots
WHERE scope = 'consensus' AND exchange = ''
  AND symbol = $1 AND market_type = $2 AND timeframe = $3
  AND bucket_ts = $4 AND calculation_version = $5
ORDER BY metric ASC, percentile_window ASC
"""

# Bounded-latest per (exchange, metric): DISTINCT ON picks the greatest
# snapshot_ts <= the caller-supplied cutoff_ts — never a row after it, and
# never "latest now" (no now()/CURRENT_TIMESTAMP anywhere in this query).
_DATA_HEALTH_AT_CUTOFF_SQL = """
SELECT DISTINCT ON (exchange, metric)
       symbol, exchange, market_type, metric, snapshot_ts, last_event_at,
       expected_interval_s, lateness_ms, gap_count, largest_gap_s, backfill_status,
       coverage_window_start, coverage_window_end, is_stale, is_usable,
       computed_at, config_hash, config_version, code_version,
       feature_schema_version, calculation_version
FROM data_health_snapshots
WHERE symbol = $1 AND market_type = $2 AND calculation_version = $3
  AND exchange = ANY($4::text[]) AND metric = ANY($5::text[])
  AND snapshot_ts <= $6
ORDER BY exchange, metric, snapshot_ts DESC
"""


# ---- JSONB detachment --------------------------------------------------------
def _freeze_json_value(value: Any, name: str) -> Any:
    """Recursively detach an already-decoded JSON value into a deeply
    immutable structure: Mapping -> MappingProxyType, list/tuple -> tuple,
    scalars pass through unchanged. Rejects a non-str mapping key and any
    unsupported nested type loudly, never silently drops/replaces it."""
    if isinstance(value, _AbcMapping):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise V2AlignmentReaderError(
                    f"{name}: JSON object keys must be str, got {type(k).__name__}: {k!r}")
            out[k] = _freeze_json_value(v, f"{name}.{k}")
        return MappingProxyType(out)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_value(v, f"{name}[]") for v in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise V2AlignmentReaderError(
        f"{name}: unsupported JSON value of type {type(value).__name__}")


def _parse_json_column(value: Any, name: str) -> Any:
    """Parse+detach one JSONB column value. asyncpg returns JSONB as JSON
    TEXT by default (no custom codec is registered anywhere in this
    codebase — see storage/shadow_cli_readers.py's identical note for
    forecast_predictions), but a test fake or a codec-configured connection
    may hand back an already-decoded dict/list directly; both are handled.
    Malformed JSON text raises loudly rather than being silently replaced
    with an empty object/array."""
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError) as exc:
            raise V2AlignmentReaderError(f"{name}: malformed JSON: {exc}") from exc
        return _freeze_json_value(decoded, name)
    return _freeze_json_value(value, name)


def _parse_required_json_column(value: Any, name: str) -> Any:
    if value is None:
        raise V2AlignmentReaderError(f"{name} must not be NULL")
    return _parse_json_column(value, name)


def _parse_nullable_json_column(value: Any, name: str) -> Optional[Any]:
    if value is None:
        return None
    return _parse_json_column(value, name)


def _detach_consensus_row(rec) -> Mapping:
    out = {}
    for col in rec.keys():
        value = rec[col]
        if col in _CONSENSUS_JSON_COLUMNS:
            value = (_parse_required_json_column(value, col)
                     if col in _CONSENSUS_REQUIRED_JSON_COLUMNS
                     else _parse_nullable_json_column(value, col))
        out[col] = value
    return MappingProxyType(out)


def _detach_percentile_row(rec) -> Mapping:
    return MappingProxyType(dict(rec))


def _detach_health_row(rec) -> Mapping:
    return MappingProxyType(dict(rec))


# ---- argument validation (BEFORE any connection is acquired) ---------------
_HEX16 = re.compile(r"[0-9a-f]{16}")


def _nonblank(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise V2AlignmentReaderError(f"{name} must be a non-empty string")
    return value


def _validate_calculation_version(value: Any) -> str:
    if not isinstance(value, str) or not _HEX16.fullmatch(value):
        raise V2AlignmentReaderError(
            "calculation_version must be exactly 16 lowercase hex chars")
    return value


def _validate_whole_minute_utc(value: Any, name: str) -> datetime:
    # Exact type check (not isinstance) so a datetime subclass or a bool is
    # never silently accepted — matches analytics/forecasting_v2/
    # alignment.py's own validation posture for the same reason.
    if type(value) is not datetime:
        raise V2AlignmentReaderError(
            f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2AlignmentReaderError(f"{name} must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise V2AlignmentReaderError(f"{name} must be UTC (offset 0), got {value.utcoffset()}")
    if value.second != 0 or value.microsecond != 0:
        raise V2AlignmentReaderError(f"{name} must be a whole minute (no seconds/microseconds)")
    return value


def _validate_identifier_sequence(values: Any, name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, _AbcSequence):
        raise V2AlignmentReaderError(f"{name} must be a Sequence (not a str/bytes)")
    items = tuple(values)
    if not items:
        raise V2AlignmentReaderError(f"{name} must be non-empty")
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise V2AlignmentReaderError(f"{name} entries must be non-empty strings")
        if item in seen:
            raise V2AlignmentReaderError(f"{name} must not contain duplicates, got {item!r} twice")
        seen.add(item)
    return items


def validate_consensus_feature_args(*, symbol: str, market_type: str, timeframe: str,
                                    bucket_ts: datetime, calculation_version: str) -> None:
    """Validate every argument for `read_v2_consensus_feature` /
    `read_v2_consensus_percentiles` (the two share an identical identity
    shape). Raises `V2AlignmentReaderError`; performs no I/O."""
    _nonblank(symbol, "symbol")
    _nonblank(market_type, "market_type")
    _nonblank(timeframe, "timeframe")
    _validate_whole_minute_utc(bucket_ts, "bucket_ts")
    _validate_calculation_version(calculation_version)


def validate_data_health_args(*, symbol: str, market_type: str, exchanges: Sequence[str],
                              metrics: Sequence[str], cutoff_ts: datetime,
                              calculation_version: str) -> None:
    """Validate every argument for `read_v2_data_health_at_cutoff`. Raises
    `V2AlignmentReaderError`; performs no I/O."""
    _nonblank(symbol, "symbol")
    _nonblank(market_type, "market_type")
    _validate_identifier_sequence(exchanges, "exchanges")
    _validate_identifier_sequence(metrics, "metrics")
    _validate_whole_minute_utc(cutoff_ts, "cutoff_ts")
    _validate_calculation_version(calculation_version)


# ---- the three read primitives (run on a single caller-supplied connection) -
async def read_v2_consensus_feature(
    conn, *, symbol: str, market_type: str, timeframe: str,
    bucket_ts: datetime, calculation_version: str,
) -> Optional[Mapping]:
    """The ONE `consensus_feature_vectors` row at the EXACT
    `(symbol, market_type, timeframe, bucket_ts, calculation_version)`
    identity — never an older bucket, never a different
    `calculation_version`. `None` if no such row exists; this absence is
    itself meaningful information for a future decision layer, never
    silently papered over with a fallback. Arguments must already be
    validated (`validate_consensus_feature_args`)."""
    rows = await conn.fetch(
        _CONSENSUS_FEATURE_SQL, symbol, market_type, timeframe, bucket_ts, calculation_version)
    if not rows:
        return None
    if len(rows) > 1:
        raise V2AlignmentReaderError(
            f"expected at most one consensus_feature_vectors row for "
            f"({symbol!r}, {market_type!r}, {timeframe!r}, {bucket_ts.isoformat()!r}, "
            f"{calculation_version!r}), got {len(rows)}")
    rec = rows[0]
    if (rec["symbol"], rec["market_type"], rec["timeframe"], rec["bucket_ts"],
            rec["calculation_version"]) != (symbol, market_type, timeframe, bucket_ts,
                                            calculation_version):
        raise V2AlignmentReaderError(
            "consensus_feature_vectors row identity does not match the requested identity")
    return _detach_consensus_row(rec)


async def read_v2_consensus_percentiles(
    conn, *, symbol: str, market_type: str, timeframe: str,
    bucket_ts: datetime, calculation_version: str,
) -> tuple[Mapping, ...]:
    """Every `percentile_snapshots` row (one per `(metric,
    percentile_window)`) at the EXACT `(symbol, market_type, timeframe,
    bucket_ts, calculation_version)` identity, pinned to
    `scope='consensus'`/`exchange=''` — exchange-scoped percentiles are
    never read here. `()` if no such rows exist; no older-bucket fallback.
    Deterministically ordered by `(metric, percentile_window)`. Which
    metric/window matters is NOT decided here. Arguments must already be
    validated (`validate_consensus_feature_args`)."""
    rows = await conn.fetch(
        _CONSENSUS_PERCENTILES_SQL, symbol, market_type, timeframe, bucket_ts,
        calculation_version)
    seen_identity: set[tuple] = set()
    detached = []
    for rec in rows:
        if (rec["scope"], rec["exchange"], rec["symbol"], rec["market_type"],
                rec["timeframe"], rec["bucket_ts"], rec["calculation_version"]) != (
                "consensus", "", symbol, market_type, timeframe, bucket_ts,
                calculation_version):
            raise V2AlignmentReaderError(
                "percentile_snapshots row identity does not match the requested identity")
        logical_key = (rec["metric"], rec["percentile_window"])
        if logical_key in seen_identity:
            raise V2AlignmentReaderError(
                f"duplicate percentile_snapshots row for (metric, percentile_window)="
                f"{logical_key!r} despite the table's primary key")
        seen_identity.add(logical_key)
        detached.append(_detach_percentile_row(rec))
    return tuple(detached)


async def read_v2_data_health_at_cutoff(
    conn, *, symbol: str, market_type: str, exchanges: Sequence[str],
    metrics: Sequence[str], cutoff_ts: datetime, calculation_version: str,
) -> Mapping:
    """For every requested `(exchange, metric)` pair (the full
    `exchanges x metrics` cross product, in caller order), the LATEST
    `data_health_snapshots` row whose `snapshot_ts <= cutoff_ts` — a row
    exactly at the cutoff is eligible, a row after it is never returned
    (§2's health no-lookahead mechanism). A pair with no eligible row maps
    to `None`, explicitly present in the result — never silently omitted,
    and never backfilled with a fabricated healthy default
    (`is_stale=False`/`is_usable=True`/`gap_count=0`). Arguments must
    already be validated (`validate_data_health_args`)."""
    exchanges = tuple(exchanges)
    metrics = tuple(metrics)
    rows = await conn.fetch(
        _DATA_HEALTH_AT_CUTOFF_SQL, symbol, market_type, calculation_version,
        list(exchanges), list(metrics), cutoff_ts)

    by_pair: dict[tuple[str, str], Mapping] = {}
    for rec in rows:
        pair = (rec["exchange"], rec["metric"])
        if rec["exchange"] not in exchanges or rec["metric"] not in metrics:
            raise V2AlignmentReaderError(
                f"data_health_snapshots returned unrequested pair {pair!r}")
        if rec["symbol"] != symbol or rec["market_type"] != market_type:
            raise V2AlignmentReaderError(
                "data_health_snapshots row identity does not match the requested "
                "symbol/market_type")
        if rec["calculation_version"] != calculation_version:
            raise V2AlignmentReaderError(
                "data_health_snapshots row has an unrequested calculation_version")
        if rec["snapshot_ts"] > cutoff_ts:
            raise V2AlignmentReaderError(
                f"data_health_snapshots row for {pair!r} has snapshot_ts "
                f"{rec['snapshot_ts'].isoformat()} after cutoff_ts {cutoff_ts.isoformat()}")
        if pair in by_pair:
            raise V2AlignmentReaderError(
                f"duplicate data_health_snapshots row for (exchange, metric)={pair!r}")
        by_pair[pair] = _detach_health_row(rec)

    result: dict[tuple[str, str], Optional[Mapping]] = {}
    for exchange in exchanges:
        for metric in metrics:
            result[(exchange, metric)] = by_pair.get((exchange, metric))
    return MappingProxyType(result)
