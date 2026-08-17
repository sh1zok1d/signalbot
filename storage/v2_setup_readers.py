"""
V2 setup-detector historical-window storage readers (Stage 5 — Setup
Detectors, PR 1 of ~4, docs/FORECASTING_ROADMAP.md §I stage 5).

`storage/v2_alignment_readers.py` (Stage 3) answers "given an
already-selected EXACT legal bucket, how do I read exactly that one
Stage 2 row?" The three Stage 5 detector families (`TREND_PULLBACK`,
`COMPRESSION_BREAKOUT`, `CONFIRMED_BREAKOUT`) additionally need
deterministic HISTORICAL WINDOWS — many consecutive closed buckets, not
one — so this is a SEPARATE module rather than an expansion of Stage 3's
single-bucket semantic scope:

  - `read_v2_consensus_feature_window` — every `consensus_feature_vectors`
    row inside a caller-supplied INCLUSIVE `[bucket_start, bucket_end]`
    bucket-START interval, for one exact
    `(symbol, market_type, timeframe, calculation_version)` identity.
    Reuses the full explicit `ConsensusFeatureVector` column surface
    `storage/v2_alignment_readers.py::_CONSENSUS_FEATURE_SQL` already
    selects — future detectors need `range_width_pct_median`,
    `price_move_pct_median`, `price_direction_agreement`,
    `taker_delta_notional_usd_sum`, and coverage/confidence fields from
    the SAME row shape, so this avoids inventing a second, narrower
    consensus pseudo-model.
  - `read_v2_consensus_percentile_window` — every consensus-scope
    `percentile_snapshots` row for one exact `(symbol, market_type,
    metric, timeframe, percentile_window, calculation_version)` identity,
    inside the same inclusive bucket-START interval. `scope='consensus'`/
    `exchange=''` are pinned at SQL level, same as Stage 3's percentile
    reader.
  - `read_v2_reference_feature_window` — every `exchange_feature_vectors`
    row for one exact `(exchange, symbol, market_type, timeframe,
    calculation_version)` identity, inside the same inclusive interval.
    Generic about `exchange`; pinning it to the canonical V2 reference
    exchange (`"binance"`, §11) remains an ANALYTICS decision, never made
    here — same posture as Stage 3's `read_v2_reference_feature`.
  - `read_v2_instrument` — the ONE `exchange_instruments` row for one
    exact `(exchange, symbol, market_type)` identity (not bucket-scoped —
    instrument metadata is not time-bucketed). Exists so
    `protection_buffer()`'s `tick_size` input has a narrowly-scoped,
    read-only, schema-grounded source; reuses
    `storage/stage2_readers.py::INSTRUMENT_SQL`'s exact column set rather
    than inventing a second one, but as its OWN standalone single-row
    read (that existing reader is bundled inside a heavier six-table
    per-bucket `ExchangeFeatureRawBundle` fetch that is not a good fit
    for a bucket-independent metadata lookup).

Raw `klines_1m` history reuses Stage 3's existing
`read_v2_reference_klines`/`Database.fetch_v2_reference_klines`
UNCHANGED — that reader already supports an arbitrary explicit half-open
`[bucket_start, bucket_end)` interval, so this module does not duplicate
it.

**Inclusive bucket-START interval, deliberately different from Stage 3's
half-open kline convention.** `bucket_start`/`bucket_end` here are both
INCLUSIVE bucket-START identities (`bucket_ts >= bucket_start AND
bucket_ts <= bucket_end`) — matching how `RANGE_PROXY_pct`
(`analytics/forecasting_v2/setup_common.py`) and the lookback windows in
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §7 are framed ("the N most
recent closed buckets with bucket_ts in `[B-(N-1)*tf, B]`" — an inclusive
range of bucket STARTS, not a half-open range of raw timestamps like
`klines_1m`'s continuous `ts` column).

**No detector assembler here.** This module gives future detector code
deterministic historical ROWS. It does not decide which N buckets a
specific detector needs, does not compute `RANGE_PROXY_pct`/
`compression_score`/anything derived, and does not assemble a
detector-specific input bundle (`V2TrendPullbackInputs` etc.) — those are
each detector PR's own job (PR 2/~4 onward).

Read only. No writes — no `INSERT`/`UPDATE`/`DELETE`/`UPSERT`/
`ON CONFLICT` appears anywhere in this module's SQL. No wall clock
(`datetime.now()`/`utcnow()`/`time.time()`), no `now()`/
`CURRENT_TIMESTAMP` in SQL, no `computed_at` cutoff, no "latest" fallback,
no `LIMIT N` used as a semantic substitute for an explicit boundary — the
caller supplies the exact interval. No `random`/`uuid`, no imports from
`runtime`/`main`/`notifications`, and no imports from `analytics` of any
kind (mirrors `storage/v2_alignment_readers.py`'s own layering: `timeframe`
here is validated only as a non-empty string, never re-checked against
`analytics.forecasting_v2.alignment.TIMEFRAME_MINUTES` — that enumeration
remains the analytics layer's job).

Missing historical buckets are NOT a storage error — a request covering
14 expected bucket starts where only 13 rows physically exist returns
exactly those 13 rows; this module never fabricates the 14th, substitutes
an older bucket, or refuses merely because the window is incomplete.
Deciding whether an incomplete window is usable (e.g. `range_proxy_pct`'s
exact-14 requirement) is the ANALYTICS layer's job
(`analytics/forecasting_v2/setup_common.py`), kept deliberately separate
from this module's storage-selection concern.

Fail-closed validation happens TWICE, mirroring
`storage/v2_alignment_readers.py`'s own posture: each public `read_v2_*`
function enforces its full argument contract itself, before
`conn.fetch()`, and each `storage.db.Database.fetch_v2_*` wrapper
additionally validates before `pool.acquire()`.

Pure storage layer: static, trusted, explicit-column SQL only (no
`SELECT *`, no dynamic identifiers, no query-builder abstraction); every
returned row is detached (a plain, deeply-immutable `Mapping`,
`MappingProxyType`, JSONB parsed and frozen) so nothing here retains the
connection or a mutable reference into a DB-returned object.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping as _AbcMapping
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, Mapping, Optional

__all__ = [
    "V2SetupReaderError",
    "read_v2_consensus_feature_window",
    "read_v2_consensus_percentile_window",
    "read_v2_reference_feature_window",
    "read_v2_instrument",
]


class V2SetupReaderError(ValueError):
    """Invalid reader argument (raised before any DB access), or a
    returned DB row that fails to match the identity/interval that was
    explicitly requested (a fake/test connection misbehaving, or — for a
    real connection — a bug elsewhere; either way, never silently
    trusted)."""


# ---- static, trusted SQL (no SELECT *, no dynamic identifiers) --------------
# Identical explicit column set to v2_alignment_readers.py's
# _CONSENSUS_FEATURE_SQL, widened from an exact bucket_ts match to an
# inclusive bucket-START interval. INCLUSIVE on both ends (bucket_ts
# BETWEEN, expressed explicitly rather than via BETWEEN for readability).
_CONSENSUS_FEATURE_WINDOW_SQL = """
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
  AND calculation_version = $4
  AND bucket_ts >= $5 AND bucket_ts <= $6
ORDER BY bucket_ts ASC
"""

_CONSENSUS_JSON_COLUMNS = (
    "coverage_by_metric", "provenance_by_metric", "data_confidence_by_metric",
    "liquidation_feed_quality_by_exchange", "outlier_exchanges",
)
_CONSENSUS_REQUIRED_JSON_COLUMNS = frozenset(
    {"coverage_by_metric", "provenance_by_metric", "data_confidence_by_metric"})

# The FULL explicit column set _CONSENSUS_FEATURE_WINDOW_SQL selects — a
# required-row-shape check, not merely the identity subset this module
# directly indexes: _detach_consensus_row() blindly iterates `rec.keys()`,
# so a row silently MISSING a key (not SQL NULL, an absent key entirely)
# would otherwise produce a silently-incomplete detached row rather than
# a domain error.
_CONSENSUS_FEATURE_REQUIRED_FIELDS = (
    "symbol", "market_type", "timeframe", "bucket_ts", "feature_schema_version",
    "calculation_version",
    "coverage_by_metric", "provenance_by_metric", "data_confidence_by_metric",
    "exchanges_expected_max", "min_coverage_ratio", "data_confidence_overall",
    "price_direction_agreement", "flow_direction_agreement", "oi_direction_agreement",
    "price_move_pct_median", "range_width_pct_median", "oi_change_pct_median",
    "funding_rate_median", "funding_rate_mad",
    "volume_notional_usd_sum", "taker_buy_notional_usd_sum",
    "taker_sell_notional_usd_sum", "taker_delta_notional_usd_sum",
    "cvd_delta_notional_usd_sum",
    "observed_long_liquidation_notional_sum", "observed_short_liquidation_notional_sum",
    "observed_liquidation_event_count_sum", "liquidation_feed_quality_by_exchange",
    "price_move_pct_mad", "oi_change_pct_mad", "outlier_exchanges",
    "consensus_confidence", "is_partial_consensus",
    "computed_at", "config_hash", "config_version", "code_version",
)

# scope/exchange pinned at SQL level, same as Stage 3's percentile reader.
# EXACT metric/timeframe/percentile_window, inclusive bucket-START interval.
_CONSENSUS_PERCENTILE_WINDOW_SQL = """
SELECT scope, exchange, symbol, market_type, metric, timeframe, percentile_window,
       bucket_ts, value, percentile_rank, sample_size,
       sample_window_start, sample_window_end, confidence_tier,
       computed_at, config_hash, config_version, code_version,
       feature_schema_version, calculation_version
FROM percentile_snapshots
WHERE scope = 'consensus' AND exchange = ''
  AND symbol = $1 AND market_type = $2 AND metric = $3 AND timeframe = $4
  AND percentile_window = $5 AND calculation_version = $6
  AND bucket_ts >= $7 AND bucket_ts <= $8
ORDER BY bucket_ts ASC
"""

# The FULL explicit column set _CONSENSUS_PERCENTILE_WINDOW_SQL selects.
_CONSENSUS_PERCENTILE_REQUIRED_FIELDS = (
    "scope", "exchange", "symbol", "market_type", "metric", "timeframe", "percentile_window",
    "bucket_ts", "value", "percentile_rank", "sample_size",
    "sample_window_start", "sample_window_end", "confidence_tier",
    "computed_at", "config_hash", "config_version", "code_version",
    "feature_schema_version", "calculation_version",
)

# Identical explicit column set to v2_alignment_readers.py's
# _REFERENCE_FEATURE_SQL, widened to an inclusive bucket-START interval.
_REFERENCE_FEATURE_WINDOW_SQL = """
SELECT exchange, symbol, market_type, timeframe, bucket_ts, feature_schema_version,
       calculation_version,
       price_move_pct, range_width_pct, close_price,
       volume_raw, volume_raw_unit, volume_notional_usd, taker_buy_notional_usd,
       taker_sell_notional_usd, taker_delta_notional_usd, cvd_delta_notional_usd,
       oi_change_pct, oi_unit, funding_rate,
       long_liquidation_notional, short_liquidation_notional, liquidation_event_count,
       liquidation_feed_quality, is_snapshot_feed,
       bars_expected, bars_present, has_gap, is_usable,
       computed_at, config_hash, config_version, code_version
FROM exchange_feature_vectors
WHERE exchange = $1 AND symbol = $2 AND market_type = $3 AND timeframe = $4
  AND calculation_version = $5
  AND bucket_ts >= $6 AND bucket_ts <= $7
ORDER BY bucket_ts ASC
"""

# The FULL explicit column set _REFERENCE_FEATURE_WINDOW_SQL selects.
_REFERENCE_FEATURE_REQUIRED_FIELDS = (
    "exchange", "symbol", "market_type", "timeframe", "bucket_ts", "feature_schema_version",
    "calculation_version",
    "price_move_pct", "range_width_pct", "close_price",
    "volume_raw", "volume_raw_unit", "volume_notional_usd", "taker_buy_notional_usd",
    "taker_sell_notional_usd", "taker_delta_notional_usd", "cvd_delta_notional_usd",
    "oi_change_pct", "oi_unit", "funding_rate",
    "long_liquidation_notional", "short_liquidation_notional", "liquidation_event_count",
    "liquidation_feed_quality", "is_snapshot_feed",
    "bars_expected", "bars_present", "has_gap", "is_usable",
    "computed_at", "config_hash", "config_version", "code_version",
)

# Single-row instrument metadata lookup — NOT bucket-scoped (instrument
# metadata is not time-bucketed). Same explicit column set as
# storage/stage2_readers.py::INSTRUMENT_SQL, as its own standalone read.
_INSTRUMENT_SQL = """
SELECT exchange, symbol, market_type, exchange_instrument_id, quantity_unit,
       contract_multiplier, tick_size, price_precision, quantity_precision,
       metadata_source, fetched_at, is_stale, note, updated_at
FROM exchange_instruments
WHERE exchange = $1 AND symbol = $2 AND market_type = $3
"""

# The FULL explicit column set _INSTRUMENT_SQL selects.
_INSTRUMENT_REQUIRED_FIELDS = (
    "exchange", "symbol", "market_type", "exchange_instrument_id", "quantity_unit",
    "contract_multiplier", "tick_size", "price_precision", "quantity_precision",
    "metadata_source", "fetched_at", "is_stale", "note", "updated_at",
)


# ---- JSONB detachment (identical posture to v2_alignment_readers.py) -------
def _freeze_json_value(value: Any, name: str) -> Any:
    if isinstance(value, _AbcMapping):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise V2SetupReaderError(
                    f"{name}: JSON object keys must be str, got {type(k).__name__}: {k!r}")
            out[k] = _freeze_json_value(v, f"{name}.{k}")
        return MappingProxyType(out)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_value(v, f"{name}[]") for v in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise V2SetupReaderError(f"{name}: unsupported JSON value of type {type(value).__name__}")


def _parse_json_column(value: Any, name: str) -> Any:
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError) as exc:
            raise V2SetupReaderError(f"{name}: malformed JSON: {exc}") from exc
        return _freeze_json_value(decoded, name)
    return _freeze_json_value(value, name)


def _parse_required_json_column(value: Any, name: str) -> Any:
    if value is None:
        raise V2SetupReaderError(f"{name} must not be NULL")
    return _parse_json_column(value, name)


def _parse_nullable_json_column(value: Any, name: str) -> Optional[Any]:
    if value is None:
        return None
    return _parse_json_column(value, name)


# ---- returned-row shape hardening (load-bearing, pre-merge amendment) -----
# A broken/fake connection (or a genuinely corrupted real one) can return
# something that is not row-shaped at all ({}, a partial dict, a bare
# string, None). Without this check, the post-fetch identity/detachment
# code below would leak a bare KeyError/AttributeError/TypeError instead
# of this module's own documented V2SetupReaderError. This checks ONLY
# that the row supports the exact Mapping/asyncpg.Record-like access
# pattern already used elsewhere in this module (`.keys()` + indexing)
# and that every REQUIRED column is PRESENT as a key — never that a
# present column's VALUE is non-NULL (SQL NULL is a legitimate value for
# a nullable column; a missing key is a structurally different failure,
# and this check never conflates the two).
def _require_row_fields(rec: Any, required_fields: "tuple[str, ...]", family: str) -> None:
    if not hasattr(rec, "keys") or not hasattr(rec, "__getitem__"):
        raise V2SetupReaderError(
            f"{family} row must be Mapping/Record-like (support .keys()/indexing), "
            f"got {type(rec).__name__}: {rec!r}")
    try:
        present = set(rec.keys())
    except TypeError as exc:
        raise V2SetupReaderError(f"{family} row .keys() failed: {exc}") from exc
    missing = [col for col in required_fields if col not in present]
    if missing:
        raise V2SetupReaderError(
            f"{family} row is missing required field(s) {missing!r}")


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


def _detach_row(rec) -> Mapping:
    return MappingProxyType(dict(rec))


# ---- argument validation (BEFORE any connection is acquired) ---------------
_HEX16 = re.compile(r"[0-9a-f]{16}")


def _nonblank(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise V2SetupReaderError(f"{name} must be a non-empty string")
    return value


def _validate_calculation_version(value: Any) -> str:
    if not isinstance(value, str) or not _HEX16.fullmatch(value):
        raise V2SetupReaderError("calculation_version must be exactly 16 lowercase hex chars")
    return value


def _validate_whole_minute_utc(value: Any, name: str) -> datetime:
    if type(value) is not datetime:
        raise V2SetupReaderError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2SetupReaderError(f"{name} must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise V2SetupReaderError(f"{name} must be UTC (offset 0), got {value.utcoffset()}")
    if value.second != 0 or value.microsecond != 0:
        raise V2SetupReaderError(f"{name} must be a whole minute (no seconds/microseconds)")
    return value


def _validate_window_bounds(bucket_start: Any, bucket_end: Any) -> "tuple[datetime, datetime]":
    start = _validate_whole_minute_utc(bucket_start, "bucket_start")
    end = _validate_whole_minute_utc(bucket_end, "bucket_end")
    if not (start <= end):
        raise V2SetupReaderError(
            f"bucket_start ({start.isoformat()}) must be <= bucket_end ({end.isoformat()})")
    return start, end


def validate_consensus_feature_window_args(
    *, symbol: str, market_type: str, timeframe: str,
    bucket_start: datetime, bucket_end: datetime, calculation_version: str,
) -> None:
    """Validate every argument for `read_v2_consensus_feature_window`.
    Raises `V2SetupReaderError`; performs no I/O."""
    _nonblank(symbol, "symbol")
    _nonblank(market_type, "market_type")
    _nonblank(timeframe, "timeframe")
    _validate_window_bounds(bucket_start, bucket_end)
    _validate_calculation_version(calculation_version)


def validate_consensus_percentile_window_args(
    *, symbol: str, market_type: str, metric: str, timeframe: str, percentile_window: str,
    bucket_start: datetime, bucket_end: datetime, calculation_version: str,
) -> None:
    """Validate every argument for `read_v2_consensus_percentile_window`.
    Raises `V2SetupReaderError`; performs no I/O."""
    _nonblank(symbol, "symbol")
    _nonblank(market_type, "market_type")
    _nonblank(metric, "metric")
    _nonblank(timeframe, "timeframe")
    _nonblank(percentile_window, "percentile_window")
    _validate_window_bounds(bucket_start, bucket_end)
    _validate_calculation_version(calculation_version)


def validate_reference_feature_window_args(
    *, exchange: str, symbol: str, market_type: str, timeframe: str,
    bucket_start: datetime, bucket_end: datetime, calculation_version: str,
) -> None:
    """Validate every argument for `read_v2_reference_feature_window`.
    Raises `V2SetupReaderError`; performs no I/O."""
    _nonblank(exchange, "exchange")
    _nonblank(symbol, "symbol")
    _nonblank(market_type, "market_type")
    _nonblank(timeframe, "timeframe")
    _validate_window_bounds(bucket_start, bucket_end)
    _validate_calculation_version(calculation_version)


def validate_instrument_args(*, exchange: str, symbol: str, market_type: str) -> None:
    """Validate every argument for `read_v2_instrument`. Raises
    `V2SetupReaderError`; performs no I/O."""
    _nonblank(exchange, "exchange")
    _nonblank(symbol, "symbol")
    _nonblank(market_type, "market_type")


# ---- the four read primitives (run on a single caller-supplied connection) -
async def read_v2_consensus_feature_window(
    conn, *, symbol: str, market_type: str, timeframe: str,
    bucket_start: datetime, bucket_end: datetime, calculation_version: str,
) -> "tuple[Mapping, ...]":
    """Every `consensus_feature_vectors` row for one exact `(symbol,
    market_type, timeframe, calculation_version)` identity whose
    `bucket_ts` falls inside the INCLUSIVE `[bucket_start, bucket_end]`
    interval, ordered ascending by `bucket_ts`. Only physically present
    rows are returned — a caller requesting 14 expected bucket starts
    where only 13 rows exist gets exactly those 13; this function never
    fabricates the missing one, substitutes an older bucket, or refuses
    for incompleteness (deciding whether an incomplete window is USABLE
    is the analytics layer's job, `setup_common.py::range_proxy_pct`).

    Enforces its own public contract BEFORE any DB access, via
    `validate_consensus_feature_window_args`. Every returned row is
    re-validated: exact requested identity, `bucket_ts` inside the
    requested inclusive interval, no duplicate `bucket_ts`, and
    non-descending order (a broken/fake connection returning an
    unsorted/inconsistent set fails loudly rather than being silently
    accepted)."""
    validate_consensus_feature_window_args(
        symbol=symbol, market_type=market_type, timeframe=timeframe,
        bucket_start=bucket_start, bucket_end=bucket_end,
        calculation_version=calculation_version)
    rows = await conn.fetch(
        _CONSENSUS_FEATURE_WINDOW_SQL, symbol, market_type, timeframe,
        calculation_version, bucket_start, bucket_end)

    detached = []
    seen_bucket_ts: set = set()
    prev_ts: Optional[datetime] = None
    for rec in rows:
        _require_row_fields(rec, _CONSENSUS_FEATURE_REQUIRED_FIELDS, "consensus_feature_vectors")
        if (rec["symbol"], rec["market_type"], rec["timeframe"], rec["calculation_version"]) != (
                symbol, market_type, timeframe, calculation_version):
            raise V2SetupReaderError(
                "consensus_feature_vectors row identity does not match the requested identity")
        ts = _validate_whole_minute_utc(rec["bucket_ts"], "bucket_ts")
        if not (bucket_start <= ts <= bucket_end):
            raise V2SetupReaderError(
                f"consensus_feature_vectors row bucket_ts {ts.isoformat()} is outside the "
                f"requested inclusive interval [{bucket_start.isoformat()}, "
                f"{bucket_end.isoformat()}]")
        if ts in seen_bucket_ts:
            raise V2SetupReaderError(f"duplicate consensus_feature_vectors row for bucket_ts "
                                     f"{ts.isoformat()}")
        if prev_ts is not None and ts < prev_ts:
            raise V2SetupReaderError(
                "consensus_feature_vectors rows must be non-descending in bucket_ts "
                "(broken/fake connection)")
        seen_bucket_ts.add(ts)
        prev_ts = ts
        detached.append(_detach_consensus_row(rec))
    return tuple(detached)


async def read_v2_consensus_percentile_window(
    conn, *, symbol: str, market_type: str, metric: str, timeframe: str,
    percentile_window: str, bucket_start: datetime, bucket_end: datetime,
    calculation_version: str,
) -> "tuple[Mapping, ...]":
    """Every consensus-scope `percentile_snapshots` row for one exact
    `(symbol, market_type, metric, timeframe, percentile_window,
    calculation_version)` identity whose `bucket_ts` falls inside the
    INCLUSIVE `[bucket_start, bucket_end]` interval, ordered ascending by
    `bucket_ts`. `scope='consensus'`/`exchange=''` pinned at SQL level —
    no exchange-scoped row is ever reachable here. No cross-metric,
    cross-timeframe, or cross-window fallback of any kind. Only
    physically present rows are returned; no fabrication of missing ones.

    Enforces its own public contract BEFORE any DB access, via
    `validate_consensus_percentile_window_args`. Every returned row is
    re-validated: exact requested identity (including the pinned
    `scope`/`exchange`), `bucket_ts` inside the requested inclusive
    interval, the already-established no-lookahead invariant
    (`sample_window_end < bucket_ts` when `sample_window_end` is
    present — equality is not allowed, same posture as Stage 3/PR 1's
    `find_consensus_percentile`), no duplicate `bucket_ts`, and
    non-descending order."""
    validate_consensus_percentile_window_args(
        symbol=symbol, market_type=market_type, metric=metric, timeframe=timeframe,
        percentile_window=percentile_window, bucket_start=bucket_start, bucket_end=bucket_end,
        calculation_version=calculation_version)
    rows = await conn.fetch(
        _CONSENSUS_PERCENTILE_WINDOW_SQL, symbol, market_type, metric, timeframe,
        percentile_window, calculation_version, bucket_start, bucket_end)

    detached = []
    seen_bucket_ts: set = set()
    prev_ts: Optional[datetime] = None
    for rec in rows:
        _require_row_fields(rec, _CONSENSUS_PERCENTILE_REQUIRED_FIELDS, "percentile_snapshots")
        if (rec["scope"], rec["exchange"], rec["symbol"], rec["market_type"], rec["metric"],
                rec["timeframe"], rec["percentile_window"], rec["calculation_version"]) != (
                "consensus", "", symbol, market_type, metric, timeframe, percentile_window,
                calculation_version):
            raise V2SetupReaderError(
                "percentile_snapshots row identity does not match the requested identity")
        ts = _validate_whole_minute_utc(rec["bucket_ts"], "bucket_ts")
        if not (bucket_start <= ts <= bucket_end):
            raise V2SetupReaderError(
                f"percentile_snapshots row bucket_ts {ts.isoformat()} is outside the requested "
                f"inclusive interval [{bucket_start.isoformat()}, {bucket_end.isoformat()}]")
        sample_window_end = rec["sample_window_end"]
        if sample_window_end is not None:
            swe = _validate_whole_minute_utc(sample_window_end, "sample_window_end")
            if not (swe < ts):
                raise V2SetupReaderError(
                    "percentile_snapshots row sample_window_end must be strictly before "
                    "bucket_ts (no-lookahead defense) — equality is not allowed")
        if ts in seen_bucket_ts:
            raise V2SetupReaderError(
                f"duplicate percentile_snapshots row for bucket_ts {ts.isoformat()}")
        if prev_ts is not None and ts < prev_ts:
            raise V2SetupReaderError(
                "percentile_snapshots rows must be non-descending in bucket_ts "
                "(broken/fake connection)")
        seen_bucket_ts.add(ts)
        prev_ts = ts
        detached.append(_detach_row(rec))
    return tuple(detached)


async def read_v2_reference_feature_window(
    conn, *, exchange: str, symbol: str, market_type: str, timeframe: str,
    bucket_start: datetime, bucket_end: datetime, calculation_version: str,
) -> "tuple[Mapping, ...]":
    """Every `exchange_feature_vectors` row for one exact `(exchange,
    symbol, market_type, timeframe, calculation_version)` identity whose
    `bucket_ts` falls inside the INCLUSIVE `[bucket_start, bucket_end]`
    interval, ordered ascending by `bucket_ts`. Generic about `exchange`
    — pinning it to the canonical V2 reference exchange (`"binance"`,
    §11) remains the analytics layer's job, never made here. Only
    physically present rows are returned; no fabrication of missing ones.

    Enforces its own public contract BEFORE any DB access, via
    `validate_reference_feature_window_args`. Every returned row is
    re-validated: exact requested identity, `bucket_ts` inside the
    requested inclusive interval, no duplicate `bucket_ts`, and
    non-descending order."""
    validate_reference_feature_window_args(
        exchange=exchange, symbol=symbol, market_type=market_type, timeframe=timeframe,
        bucket_start=bucket_start, bucket_end=bucket_end,
        calculation_version=calculation_version)
    rows = await conn.fetch(
        _REFERENCE_FEATURE_WINDOW_SQL, exchange, symbol, market_type, timeframe,
        calculation_version, bucket_start, bucket_end)

    detached = []
    seen_bucket_ts: set = set()
    prev_ts: Optional[datetime] = None
    for rec in rows:
        _require_row_fields(rec, _REFERENCE_FEATURE_REQUIRED_FIELDS, "exchange_feature_vectors")
        if (rec["exchange"], rec["symbol"], rec["market_type"], rec["timeframe"],
                rec["calculation_version"]) != (
                exchange, symbol, market_type, timeframe, calculation_version):
            raise V2SetupReaderError(
                "exchange_feature_vectors row identity does not match the requested identity")
        ts = _validate_whole_minute_utc(rec["bucket_ts"], "bucket_ts")
        if not (bucket_start <= ts <= bucket_end):
            raise V2SetupReaderError(
                f"exchange_feature_vectors row bucket_ts {ts.isoformat()} is outside the "
                f"requested inclusive interval [{bucket_start.isoformat()}, "
                f"{bucket_end.isoformat()}]")
        if ts in seen_bucket_ts:
            raise V2SetupReaderError(
                f"duplicate exchange_feature_vectors row for bucket_ts {ts.isoformat()}")
        if prev_ts is not None and ts < prev_ts:
            raise V2SetupReaderError(
                "exchange_feature_vectors rows must be non-descending in bucket_ts "
                "(broken/fake connection)")
        seen_bucket_ts.add(ts)
        prev_ts = ts
        detached.append(_detach_row(rec))
    return tuple(detached)


async def read_v2_instrument(
    conn, *, exchange: str, symbol: str, market_type: str,
) -> Optional[Mapping]:
    """The ONE `exchange_instruments` row at the EXACT `(exchange, symbol,
    market_type)` identity — instrument metadata is not time-bucketed, so
    there is no `bucket_ts`/`calculation_version` dimension here. `None`
    if no such row exists; no fallback to a different exchange/symbol.
    Exists to give `protection_buffer()`'s `tick_size` input
    (`analytics/forecasting_v2/setup_common.py`) a narrowly-scoped,
    read-only, schema-grounded source — this module has no opinion about
    which exchange is canonical (that remains the analytics layer's job,
    §11).

    Enforces its own public contract BEFORE any DB access, via
    `validate_instrument_args`. The single returned row (if any) is
    re-validated against the exact requested identity."""
    validate_instrument_args(exchange=exchange, symbol=symbol, market_type=market_type)
    rows = await conn.fetch(_INSTRUMENT_SQL, exchange, symbol, market_type)
    if not rows:
        return None
    if len(rows) > 1:
        raise V2SetupReaderError(
            f"expected at most one exchange_instruments row for ({exchange!r}, {symbol!r}, "
            f"{market_type!r}), got {len(rows)}")
    rec = rows[0]
    _require_row_fields(rec, _INSTRUMENT_REQUIRED_FIELDS, "exchange_instruments")
    if (rec["exchange"], rec["symbol"], rec["market_type"]) != (exchange, symbol, market_type):
        raise V2SetupReaderError(
            "exchange_instruments row identity does not match the requested identity")
    return _detach_row(rec)
