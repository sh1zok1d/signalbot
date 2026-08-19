"""
V2 aligned-input snapshot assembly (Stage 3 — Multi-timeframe Alignment,
PR 3 of ~3, FINAL Stage 3 PR, docs/FORECASTING_ROADMAP.md §I stage 3).

Completes the Stage 3 chain:

    PR 1 (`alignment.py`):    explicit now -> logical T -> legal bucket_ts
    PR 2 (`v2_alignment_readers.py`): exact bucket_ts/cutoff -> exact rows
    PR 3 (this module):       T + exact rows + canonical reference OHLC
                               -> ONE immutable, deterministic aligned
                                  input snapshot

`load_v2_aligned_inputs()` is the ONE place that composes PR 1's clock,
PR 2's readers, and the canonical Binance reference path into a single
`V2AlignedInputs` object. Future Stage 4 Context Engines consume this
boundary instead of each independently re-deriving `selected_bucket()`,
health cutoffs, exact-row lookups, reference-exchange selection,
reference-vector completeness gates, or raw-1m structural-OHLC membership.

This module implements ALIGNMENT / DATA PREPARATION ONLY. It makes ZERO
LONG/SHORT, regime, bias, setup, confidence, or episode decisions — no
`normalized_evidence`, `compression_score`, 4h regime, 1h bias, OI
confirmation, directional-context gate, setup detector, `structural_anchor`,
episode identity, state machine, entry zone, invalidation, confidence, or
outcome logic exists anywhere in this module. Stage 4 starts only after
this PR merges.

**Canonical reference exchange (§11): exactly `"binance"`, no failover.**
Cross-exchange evidence remains consensus-based; only the exact tradable
price levels / structural OHLC come from this one canonical exchange. If
Binance's reference vector for a bucket fails the frozen §11 gate
(`is_usable is True`, `has_gap is False`, `bars_present == bars_expected`,
`close_price is not None`), this module fails closed for anything that
needs it — it never silently substitutes Bybit, OKX, or a consensus
median close. `V2_REFERENCE_EXCHANGE` is the single, non-overridable
public constant naming this; there is no `reference_exchange=...` runtime
parameter anywhere in this module's public API.

**§7.0a structural high/low, per-bucket only.** `derive_reference_extrema`
computes `HTF_high`/`HTF_low` for exactly ONE closed bucket from its
constituent raw 1m bars, gated by the same §11 reference-vector
completeness signal. It does NOT compare extrema across a lookback of
buckets (that is §7.0c tie-breaking / Stage 5's job, not this PR's) and
does NOT compute `resistance_level`/`support_level`/`trend_leg_extreme`/
`compression range`/`structural_anchor` — only the deterministic per-bucket
extrema a later stage can compare.

**Missingness vs. corruption (§21).** Legitimately absent Stage 2 data
(no exact-bucket consensus row, no percentile rows, no eligible health
snapshot, no reference vector) is preserved as `None`/`()`/an explicit
per-pair `None` — never a fallback, never a fabricated healthy default,
never a failure of the whole snapshot. An internally INCONSISTENT result
(a fake/broken reader returning the wrong bucket, the wrong
`calculation_version`, a percentile violating its own no-lookahead
constraint, a health row after its cutoff, a reference vector that claims
full coverage but whose raw bar set is incomplete/misaligned) is a
`V2AlignedInputError` — this module never trusts a reader's returned rows
blindly, mirroring `storage/v2_alignment_readers.py`'s own posture at the
storage boundary.

**Deep immutability.** `V2AlignedInputs`/`V2TimeframeInputs` are frozen
dataclasses, but a frozen dataclass only stops a caller from REASSIGNING
one of its own fields — it does nothing about a nested dict/list a field
happens to point at. Because `V2AlignedInputReader` is a structural
`Protocol`, a conforming reader may legitimately hand back a plain
mutable dict/list it still owns elsewhere (every test double in this
codebase does exactly that). `_deep_freeze` recursively detaches every
family (consensus/percentiles/health/reference_feature/reference_klines)
into a brand-new, deeply immutable structure (`MappingProxyType`/`tuple`,
never `MappingProxyType(original)`) immediately before it is stored, so
the returned snapshot never retains a live reference the reader (or its
caller) can mutate afterward.

**Determinism.** `load_v2_aligned_inputs()` performs I/O only through the
`V2AlignedInputReader` port. It never reads `datetime.now()`/`utcnow()`/
`time.time()`, the environment, a config file, or generates a random/uuid
value — its only logical time input is `request.T`. The same reader data
+ the same request always produce the same aligned snapshot. This module
does NOT claim to reconstruct "what the DB physically contained at `T`" —
Stage 2 rows remain correction-friendly research truth (§2.1); historical
user-visible truth is preserved elsewhere, by value, in immutable
`V2EpisodeEvent` rows.
"""
from __future__ import annotations

from collections.abc import Mapping as _AbcMapping
from collections.abc import Sequence as _AbcSequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from analytics.forecasting_v2._validation import (
    validate_calculation_version, validate_feature_schema_version,
    validate_market_type, validate_symbol,
)
from analytics.forecasting_v2.alignment import (
    TIMEFRAME_MINUTES, V2AlignmentError, selected_bucket,
)
from analytics.forecasting_v2.ports import V2AlignedInputReader

__all__ = [
    "V2AlignedInputError",
    "V2_REFERENCE_EXCHANGE",
    "ALIGNED_TIMEFRAMES",
    "STRUCTURAL_OHLC_TIMEFRAMES",
    "V2AlignedInputRequest",
    "V2ReferenceExtrema",
    "V2TimeframeInputs",
    "V2AlignedInputs",
    "derive_reference_extrema",
    "load_v2_aligned_inputs",
]


class V2AlignedInputError(ValueError):
    """Malformed request/argument, or a reader result that is internally
    INCONSISTENT with what was requested (wrong bucket, wrong
    `calculation_version`, wrong `feature_schema_version`, a percentile
    violating its own no-lookahead constraint, a health row after its
    cutoff, a reference vector claiming full coverage with an
    incomplete/misaligned raw bar set). Never raised for legitimately
    MISSING data — that is preserved as `None`/`()`, never an error."""


# Canonical V2 reference exchange (§11) — reused unchanged from V1's own
# operational default (`runtime/shadow_cli.py`: `reference_exchange = ...
# or "binance"`). Not a parameter anywhere in this module's public API —
# there is no caller-selectable override and no fallback exchange list.
V2_REFERENCE_EXCHANGE = "binance"

# Exactly the four V2 semantic timeframes (analytics/forecasting_v2/
# alignment.py's own TIMEFRAME_MINUTES keys, reused not re-derived).
ALIGNED_TIMEFRAMES = ("5m", "15m", "1h", "4h")

# Raw structural OHLC (§7.0a) is only required by the CURRENT frozen
# detectors for these two timeframes (15m for COMPRESSION_BREAKOUT, 1h for
# CONFIRMED_BREAKOUT). Loading raw 1m bars for 5m (already exact via the
# reference ExchangeFeatureVector's own close_price) or 4h (240 bars per
# 5m tick, no current frozen consumer needs them; 4h context is
# consensus-based) would add unnecessary runtime cost with no frozen
# requirement backing it.
STRUCTURAL_OHLC_TIMEFRAMES = ("15m", "1h")


# ---- request-side sequence validation (local, not shared/exported) --------
def _validate_identifier_sequence(values: Any, name: str) -> tuple:
    """Mirrors storage/v2_alignment_readers.py's own
    `_validate_identifier_sequence` — kept as a small local, private copy
    (not a cross-module import of that storage-private helper, and not
    promoted into the shared `_validation.py`, which only holds checks
    needed by MULTIPLE V2 value objects; this one is needed by exactly
    one, `V2AlignedInputRequest`). Detaches to a tuple, preserving caller
    order; rejects str/bytes, empty, non-str/blank members, and
    duplicates."""
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, _AbcSequence):
        raise V2AlignedInputError(f"{name} must be a Sequence (not a str/bytes)")
    items = tuple(values)
    if not items:
        raise V2AlignedInputError(f"{name} must be non-empty")
    seen: set = set()
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise V2AlignedInputError(f"{name} entries must be non-empty strings")
        if item in seen:
            raise V2AlignedInputError(f"{name} must not contain duplicates, got {item!r} twice")
        seen.add(item)
    return items


@dataclass(frozen=True)
class V2AlignedInputRequest:
    """Fully immutable request for one `load_v2_aligned_inputs()` call.
    Every field is validated — and every sequence field DETACHED to a
    tuple — in `__post_init__`, before the loader's first `await`. This
    closes the same TOCTOU class of bug PR 2's `Database.
    fetch_v2_data_health_at_cutoff` hardening closed: a caller cannot
    mutate a list it passed in and retroactively change what was actually
    validated/requested.

    `T` is validated as a legal V2 decision boundary by calling PR 1's own
    `selected_bucket("5m", T)` (discarding the result) rather than
    re-implementing its grid-alignment algorithm a second time — a
    malformed `T` therefore fails with the exact same rules PR 1 already
    freezes, wrapped as `V2AlignedInputError`."""
    T: datetime
    symbol: str
    market_type: str
    calculation_version: str
    feature_schema_version: int
    health_exchanges: tuple
    health_metrics: tuple

    def __post_init__(self) -> None:
        validate_symbol(self.symbol, V2AlignedInputError)
        validate_market_type(self.market_type, V2AlignedInputError)
        validate_calculation_version(self.calculation_version, V2AlignedInputError)
        validate_feature_schema_version(self.feature_schema_version, V2AlignedInputError)
        object.__setattr__(
            self, "health_exchanges",
            _validate_identifier_sequence(self.health_exchanges, "health_exchanges"))
        object.__setattr__(
            self, "health_metrics",
            _validate_identifier_sequence(self.health_metrics, "health_metrics"))
        try:
            selected_bucket("5m", self.T)
        except V2AlignmentError as exc:
            raise V2AlignedInputError(
                f"T must be a legal V2 decision boundary: {exc}") from exc


@dataclass(frozen=True)
class V2ReferenceExtrema:
    """`HTF_high`/`HTF_low` (§7.0a) for exactly one closed bucket, computed
    from the reference exchange's own constituent raw 1m bars. Full stored
    precision — no rounding."""
    high: float
    low: float


@dataclass(frozen=True)
class V2TimeframeInputs:
    """Everything read for ONE timeframe at its own `selected_bucket`
    identity. `reference_klines`/`reference_extrema` are populated only
    for `STRUCTURAL_OHLC_TIMEFRAMES` (`15m`/`1h`) — always `None` for
    `5m`/`4h`, by design (see module docstring)."""
    timeframe: str
    bucket_ts: datetime
    bucket_end: datetime
    consensus: Optional[Mapping]
    percentiles: "tuple[Mapping, ...]"
    health: Mapping
    reference_feature: Optional[Mapping]
    reference_klines: "Optional[tuple[Mapping, ...]]"
    reference_extrema: Optional[V2ReferenceExtrema]


@dataclass(frozen=True)
class V2AlignedInputs:
    """The final immutable, deterministic aligned-input snapshot for one
    `T`. `by_timeframe` is a `MappingProxyType` keyed by exactly
    `ALIGNED_TIMEFRAMES`."""
    T: datetime
    symbol: str
    market_type: str
    calculation_version: str
    feature_schema_version: int
    reference_exchange: str
    by_timeframe: Mapping[str, V2TimeframeInputs]


# ---- §7.0a structural high/low (pure) ---------------------------------------
def _reference_feature_gate_passes(reference_feature: Mapping) -> bool:
    """The exact §11 reference-vector gate, reused unchanged for §7.0a's
    own "same gate" requirement: `is_usable is True`, `has_gap is False`,
    `bars_present == bars_expected`, `close_price is not None`."""
    return (
        reference_feature.get("is_usable") is True
        and reference_feature.get("has_gap") is False
        and reference_feature.get("bars_present") == reference_feature.get("bars_expected")
        and reference_feature.get("close_price") is not None
    )


def _validate_finite_price(value: Any, name: str, *, ts) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2AlignedInputError(
            f"bar at {ts.isoformat()} has non-numeric {name}: {value!r}")
    if not _is_finite(value):
        raise V2AlignedInputError(
            f"bar at {ts.isoformat()} has non-finite {name}: {value!r}")
    return float(value)


def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))  # NaN != NaN


def derive_reference_extrema(
    *, timeframe: str, bucket_ts: datetime,
    reference_feature: Optional[Mapping],
    reference_klines: Sequence[Mapping],
) -> Optional[V2ReferenceExtrema]:
    """§7.0a: `HTF_high`/`HTF_low` for exactly one closed `[bucket_ts,
    bucket_ts + timeframe)` bucket, from the reference exchange's own
    constituent raw 1m bars. Pure — no I/O; `reference_klines` must already
    be fetched (the caller decides whether fetching was even necessary,
    see `load_v2_aligned_inputs`).

    Returns `None` (legitimately unavailable, never an error) if:
      - `reference_feature` is missing;
      - the §11 gate fails (`is_usable`/`has_gap`/`bars_present==
        bars_expected`/`close_price` — `_reference_feature_gate_passes`).

    Raises `V2AlignedInputError` (internal inconsistency, never silently
    downgraded to "unavailable") if the reference feature CLAIMS full,
    usable coverage but the supplied raw bar set does not actually match
    the required exact 1-minute constituent grid: wrong count, a
    duplicate minute, a gap, a bar outside `[bucket_ts, bucket_end)`, a
    malformed `ts` (not an aware, UTC, whole-minute `datetime` —
    `_validate_bar_ts`, defensive against a structurally-conforming but
    broken/fake `V2AlignedInputReader` bypassing storage's own `ts`
    validation), or a non-finite/impossible (`high < low`) price. No
    partial-window extreme is ever computed from an incomplete set."""
    if timeframe not in STRUCTURAL_OHLC_TIMEFRAMES:
        raise V2AlignedInputError(
            f"structural extrema are only defined for {STRUCTURAL_OHLC_TIMEFRAMES}, "
            f"got {timeframe!r}")
    if reference_feature is None:
        return None
    if not _reference_feature_gate_passes(reference_feature):
        return None

    expected_minutes = TIMEFRAME_MINUTES[timeframe]
    bars_expected = reference_feature.get("bars_expected")
    if bars_expected != expected_minutes:
        raise V2AlignedInputError(
            f"reference_feature.bars_expected ({bars_expected!r}) does not match the "
            f"{timeframe} timeframe's full 1m bar count ({expected_minutes}) despite "
            "claiming usable/full coverage")

    klines = list(reference_klines)
    if len(klines) != expected_minutes:
        raise V2AlignedInputError(
            f"expected exactly {expected_minutes} constituent 1m bars for {timeframe} "
            f"bucket {bucket_ts.isoformat()}, got {len(klines)}, despite reference_feature "
            "claiming usable/full coverage")

    expected_grid = {bucket_ts + timedelta(minutes=i) for i in range(expected_minutes)}
    seen_ts: set = set()
    highs: list = []
    lows: list = []
    for bar in klines:
        ts = _validate_bar_ts(bar["ts"], timeframe=timeframe, bucket_ts=bucket_ts)
        if ts in seen_ts:
            raise V2AlignedInputError(
                f"duplicate constituent bar ts {ts.isoformat()} for {timeframe} bucket "
                f"{bucket_ts.isoformat()}")
        if ts not in expected_grid:
            raise V2AlignedInputError(
                f"constituent bar ts {ts.isoformat()} is not on the exact {timeframe} "
                f"minute grid for bucket {bucket_ts.isoformat()}")
        seen_ts.add(ts)
        high = _validate_finite_price(bar["high"], "high", ts=ts)
        low = _validate_finite_price(bar["low"], "low", ts=ts)
        if high < low:
            raise V2AlignedInputError(
                f"bar at {ts.isoformat()} has high < low ({high} < {low})")
        highs.append(high)
        lows.append(low)

    if seen_ts != expected_grid:
        missing = sorted(expected_grid - seen_ts)
        raise V2AlignedInputError(
            f"missing constituent bar(s) for {timeframe} bucket {bucket_ts.isoformat()}: "
            f"{[m.isoformat() for m in missing]}")

    return V2ReferenceExtrema(high=max(highs), low=min(lows))


# ---- deep immutability (never store a reader-owned mutable reference) -----
# A frozen dataclass (V2TimeframeInputs/V2AlignedInputs) only prevents
# REASSIGNING its own fields — it does nothing to stop a caller from
# mutating a nested dict/list one of those fields happens to point at.
# `V2AlignedInputReader` is a structural Protocol: a conforming reader (as
# every test double in this codebase does) may hand back a plain mutable
# dict/list it still owns elsewhere. `_deep_freeze` is applied to every
# family (consensus/percentiles/health/reference_feature/reference_klines)
# immediately before it is stored in `V2TimeframeInputs`, so the final
# snapshot never retains a live reference into anything the reader (or ITS
# caller) still owns and could mutate after `load_v2_aligned_inputs`
# returns.
_IMMUTABLE_SCALAR_TYPES = (str, int, float, bool, bytes, type(None))


def _deep_freeze(value: Any) -> Any:
    """Recursively detach `value` into a deeply immutable structure.

    `Mapping` -> a NEW `dict` is built first (never `MappingProxyType
    (original)`, which would still let mutating `original` mutate the
    visible proxy), then wrapped as `MappingProxyType`, with every VALUE
    recursively frozen. Keys are passed through unchanged — health-map
    keys are `(exchange, metric)` tuples, not `str`, so this layer does
    not assume every mapping key is a string; nested JSON objects inside
    a Stage 2 row normally use `str` keys already (and, via a real
    `storage.db.Database`, arrive here already frozen by
    `storage/v2_alignment_readers.py`'s own JSON detachment — re-freezing
    an already-frozen `MappingProxyType` here is idempotent, not harmful).

    `list`/`tuple` -> a NEW `tuple`, each item recursively frozen.

    `datetime` and plain immutable scalars (`str`/`int`/`float`/`bool`/
    `bytes`/`None`) are returned as-is — already immutable, nothing to do.

    Anything else (an unrecognized, potentially-mutable type) raises
    `V2AlignedInputError` rather than being silently stored by reference —
    this module has no general way to guarantee an unknown type's
    immutability, and silently trusting it would reopen exactly the hole
    this helper exists to close."""
    if isinstance(value, _AbcMapping):
        return MappingProxyType({key: _deep_freeze(v) for key, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(v) for v in value)
    if isinstance(value, datetime) or isinstance(value, _IMMUTABLE_SCALAR_TYPES):
        return value
    raise V2AlignedInputError(
        f"cannot freeze a value of unrecognized type {type(value).__name__} into the "
        f"immutable aligned-input snapshot: {value!r}")


def _validate_bar_ts(value: Any, *, timeframe: str, bucket_ts: datetime) -> datetime:
    """Defensive UTC-whole-minute `datetime` check for one raw kline bar's
    `ts`, applied BEFORE any comparison/`.isoformat()` use in
    `derive_reference_extrema`. `storage/v2_alignment_readers.py` already
    enforces this at the real storage boundary — this is a SEPARATE,
    analytics-owned re-check, because `V2AlignedInputReader` is a
    structural Protocol: a conforming-but-broken/fake reader can bypass
    storage validation entirely, and without this check a malformed
    `ts` (a string, a naive datetime, ...) would otherwise leak a bare
    `TypeError`/`AttributeError` out of this module instead of the
    documented `V2AlignedInputError`. Mirrors
    `storage/v2_alignment_readers.py::_validate_whole_minute_utc`'s exact
    rules (exact `datetime` type, timezone-aware, UTC offset zero, whole
    minute) without importing it — `storage -> analytics` reads are fine,
    but this module is not `storage/v2_alignment_readers.py` and raises
    its own `V2AlignedInputError`, never `V2AlignmentReaderError`."""
    label = f"{timeframe} bucket {bucket_ts.isoformat()}: constituent bar ts"
    if type(value) is not datetime:
        raise V2AlignedInputError(f"{label} must be a datetime, got {type(value).__name__}: {value!r}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2AlignedInputError(f"{label} must be timezone-aware, got {value!r}")
    if value.utcoffset() != timedelta(0):
        raise V2AlignedInputError(f"{label} must be UTC (offset 0), got offset {value.utcoffset()}")
    if value.second != 0 or value.microsecond != 0:
        raise V2AlignedInputError(
            f"{label} must be a whole minute (no seconds/microseconds), got {value!r}")
    return value


def _validate_utc_instant(value: Any, *, label: str) -> datetime:
    """(V2-H2d, §2.1c) Defensive UTC `datetime` check for a PRESENT
    timestamp FIELD (`health.snapshot_ts`, `percentile.sample_window_end`)
    that this module is about to compare against another datetime. Shares
    `_validate_bar_ts`'s exact type/timezone-awareness/UTC-offset rules but
    deliberately OMITS its whole-minute requirement — these two fields are
    sub-minute-precision provenance timestamps (when a snapshot/percentile
    window was actually computed), not grid-aligned bucket boundaries, so
    requiring `:00.000000` here would reject legitimate values.

    Without this check, a naive `datetime` (passes a bare `isinstance`
    check but is not timezone-comparable) or any other malformed-but-
    PRESENT value reaching a direct `>`/`<` comparison downstream raises a
    raw `TypeError` — corruption that must fail as the documented
    `V2AlignedInputError`, never leak a bare Python exception past this
    module's boundary. Legitimately MISSING data (the field is simply
    absent/`None`) is a completely separate, already-solved case — callers
    check for `None` themselves BEFORE calling this, exactly the
    missingness-vs-corruption precedence this module's docstring already
    freezes elsewhere."""
    if type(value) is not datetime:
        raise V2AlignedInputError(
            f"{label} must be a datetime, got {type(value).__name__}: {value!r}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2AlignedInputError(f"{label} must be timezone-aware, got {value!r}")
    if value.utcoffset() != timedelta(0):
        raise V2AlignedInputError(f"{label} must be UTC (offset 0), got offset {value.utcoffset()}")
    return value


# ---- cross-family provenance / identity defense (never trust a reader) -----
def _check_provenance(row: Optional[Mapping], *, request: V2AlignedInputRequest,
                      label: str) -> None:
    if row is None:
        return
    if row.get("calculation_version") != request.calculation_version:
        raise V2AlignedInputError(f"{label}: calculation_version does not match the request")
    if row.get("feature_schema_version") != request.feature_schema_version:
        raise V2AlignedInputError(f"{label}: feature_schema_version does not match the request")


def _validate_consensus_row(row: Optional[Mapping], *, timeframe: str, bucket_ts: datetime,
                            request: V2AlignedInputRequest) -> None:
    if row is None:
        return
    _check_provenance(row, request=request, label="consensus")
    if row.get("bucket_ts") != bucket_ts:
        raise V2AlignedInputError("consensus: bucket_ts does not match the selected bucket")
    if row.get("timeframe") != timeframe:
        raise V2AlignedInputError("consensus: timeframe does not match the request")
    if row.get("symbol") != request.symbol or row.get("market_type") != request.market_type:
        raise V2AlignedInputError("consensus: symbol/market_type does not match the request")


def _validate_percentile_rows(rows: "tuple[Mapping, ...]", *, timeframe: str,
                              bucket_ts: datetime, request: V2AlignedInputRequest) -> None:
    """Re-validate every percentile row's own identity — NOT its metric
    values (this module never interprets what a metric means, only
    whether the row it arrived in legitimately belongs where it was
    requested). `storage/v2_alignment_readers.py`'s real reader already
    protects this at the DB boundary; this recheck exists because
    `V2AlignedInputReader` is a structural Protocol Stage 4 can hand a
    DIFFERENT, non-`Database` implementation to — the aligned snapshot
    must be trustworthy on its own, without a caller re-deriving these
    storage-layer identity checks itself."""
    seen_logical_keys: set = set()
    for row in rows:
        _check_provenance(row, request=request, label="percentile")
        if row.get("scope") != "consensus":
            raise V2AlignedInputError(
                f"percentile: scope must be 'consensus', got {row.get('scope')!r}")
        if row.get("exchange") != "":
            raise V2AlignedInputError(
                f"percentile: exchange must be '' for consensus-scope rows, got "
                f"{row.get('exchange')!r}")
        if row.get("symbol") != request.symbol or row.get("market_type") != request.market_type:
            raise V2AlignedInputError("percentile: symbol/market_type does not match the request")
        if row.get("bucket_ts") != bucket_ts:
            raise V2AlignedInputError("percentile: bucket_ts does not match the selected bucket")
        if row.get("timeframe") != timeframe:
            raise V2AlignedInputError("percentile: timeframe does not match the request")
        sample_window_end = row.get("sample_window_end")
        if sample_window_end is not None:
            sample_window_end = _validate_utc_instant(
                sample_window_end, label="percentile: sample_window_end")
            if not (sample_window_end < row.get("bucket_ts")):
                raise V2AlignedInputError(
                    "percentile: sample_window_end must be strictly before bucket_ts "
                    "(no-lookahead defense) — equality is not allowed")
        logical_key = (row.get("metric"), row.get("percentile_window"))
        if logical_key in seen_logical_keys:
            raise V2AlignedInputError(
                f"percentile: duplicate (metric, percentile_window)={logical_key!r} row "
                f"for {timeframe} bucket {bucket_ts.isoformat()}")
        seen_logical_keys.add(logical_key)


def _validate_health_map(health: Mapping, *, bucket_end: datetime,
                         request: V2AlignedInputRequest) -> None:
    """PR #34 froze the health-missingness contract: the result mapping
    MUST contain every requested `(exchange, metric)` key, mapped to
    `None` when no eligible snapshot exists — never a silently omitted
    pair. Enforce that here too (the real `Database` reader already
    guarantees it; a different structural `V2AlignedInputReader` might
    not): the actual key set must equal exactly the requested
    `health_exchanges x health_metrics` cross product — a reader silently
    dropping a requested pair, or inventing an unrequested one, is
    reader-side corruption, not legitimate missingness, and fails loudly
    rather than being silently patched up here."""
    expected_keys = {
        (exchange, metric)
        for exchange in request.health_exchanges
        for metric in request.health_metrics
    }
    actual_keys = set(health.keys())
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        unexpected = sorted(actual_keys - expected_keys)
        raise V2AlignedInputError(
            "health: reader result key set does not match the requested "
            f"(exchange, metric) cross product — missing={missing!r}, "
            f"unexpected={unexpected!r}")
    for (exchange, metric), row in health.items():
        if row is None:
            continue
        _check_provenance(row, request=request, label="health")
        if row.get("exchange") != exchange or row.get("metric") != metric:
            raise V2AlignedInputError(
                "health: row exchange/metric does not match its (exchange, metric) key")
        if row.get("symbol") != request.symbol or row.get("market_type") != request.market_type:
            raise V2AlignedInputError("health: symbol/market_type does not match the request")
        snapshot_ts = row.get("snapshot_ts")
        if snapshot_ts is None:
            raise V2AlignedInputError(
                f"health: row for {(exchange, metric)!r} has a missing/malformed snapshot_ts")
        snapshot_ts = _validate_utc_instant(
            snapshot_ts, label=f"health: row for {(exchange, metric)!r} snapshot_ts")
        if snapshot_ts > bucket_end:
            raise V2AlignedInputError(
                "health: snapshot_ts is after the bucket-end cutoff (no-lookahead defense)")


def _validate_reference_feature_row(row: Optional[Mapping], *, timeframe: str,
                                    bucket_ts: datetime,
                                    request: V2AlignedInputRequest) -> None:
    if row is None:
        return
    _check_provenance(row, request=request, label="reference_feature")
    if row.get("exchange") != V2_REFERENCE_EXCHANGE:
        raise V2AlignedInputError(
            f"reference_feature: exchange must be the canonical reference exchange "
            f"{V2_REFERENCE_EXCHANGE!r}, got {row.get('exchange')!r}")
    if row.get("timeframe") != timeframe:
        raise V2AlignedInputError("reference_feature: timeframe does not match the request")
    if row.get("bucket_ts") != bucket_ts:
        raise V2AlignedInputError(
            "reference_feature: bucket_ts does not match the selected bucket")
    if row.get("symbol") != request.symbol or row.get("market_type") != request.market_type:
        raise V2AlignedInputError(
            "reference_feature: symbol/market_type does not match the request")


def _validate_reference_klines_identity(
    klines: "tuple[Mapping, ...]", *, exchange: str, symbol: str,
) -> None:
    for bar in klines:
        if bar.get("exchange") != exchange or bar.get("symbol") != symbol:
            raise V2AlignedInputError(
                "reference_klines: a returned bar's exchange/symbol does not match the "
                "requested canonical reference exchange/symbol")


# ---- assembly ----------------------------------------------------------------
async def load_v2_aligned_inputs(
    reader: V2AlignedInputReader, request: V2AlignedInputRequest,
) -> V2AlignedInputs:
    """Deterministically assemble ONE `V2AlignedInputs` snapshot for
    `request.T`, reading through `reader` (a `V2AlignedInputReader`) only.
    Never reads a clock, environment, config file, or generates a random/
    uuid value — `request.T` is the only logical time input.

    For each of exactly `ALIGNED_TIMEFRAMES` (`5m`, `15m`, `1h`, `4h`),
    sequentially (no `asyncio.gather` — deterministic, easy-to-audit call
    order, not a runtime-performance claim):

      1. `B = selected_bucket(tf, request.T)`, `bucket_end = B + tf`.
      2. Exact consensus row at `B`.
      3. Exact consensus-scope percentile rows at `B`.
      4. Health snapshot map at cutoff = **this bucket's own `bucket_end`**
         — NEVER the global `request.T` (§2's per-family no-lookahead
         rule: a 4h/1h/15m bucket's health cutoff is its OWN close, not
         whatever 5m instant `T` happens to be).
      5. Exact canonical-Binance reference `ExchangeFeatureVector` at `B`.
      6. Only for `15m`/`1h`: if the reference feature PASSES the §11
         gate, fetch its exact raw constituent klines and derive
         `HTF_high`/`HTF_low` (§7.0a); if it fails the gate (or is
         missing), the raw-kline fetch is skipped entirely and both
         `reference_klines`/`reference_extrema` stay `None`.

    Every returned row is defensively re-validated against the request
    (`calculation_version`, `feature_schema_version`, `bucket_ts`,
    `timeframe`, `symbol`/`market_type`, the canonical reference exchange,
    the percentile no-lookahead invariant, the health cutoff invariant) —
    a reader is never trusted blindly. Raises `V2AlignedInputError` for
    any such inconsistency; legitimately missing data is preserved as
    `None`/`()`, never an error and never a reason to fail the whole
    snapshot."""
    by_timeframe: dict = {}
    for timeframe in ALIGNED_TIMEFRAMES:
        try:
            bucket_ts = selected_bucket(timeframe, request.T)
        except V2AlignmentError as exc:
            raise V2AlignedInputError(
                f"failed to select the {timeframe} bucket for T={request.T!r}: {exc}") from exc
        bucket_end = bucket_ts + timedelta(minutes=TIMEFRAME_MINUTES[timeframe])

        consensus = await reader.fetch_v2_consensus_feature(
            symbol=request.symbol, market_type=request.market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=request.calculation_version)
        _validate_consensus_row(
            consensus, timeframe=timeframe, bucket_ts=bucket_ts, request=request)

        percentiles = await reader.fetch_v2_consensus_percentiles(
            symbol=request.symbol, market_type=request.market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=request.calculation_version)
        _validate_percentile_rows(
            percentiles, timeframe=timeframe, bucket_ts=bucket_ts, request=request)

        health = await reader.fetch_v2_data_health_at_cutoff(
            symbol=request.symbol, market_type=request.market_type,
            exchanges=request.health_exchanges, metrics=request.health_metrics,
            cutoff_ts=bucket_end, calculation_version=request.calculation_version)
        _validate_health_map(health, bucket_end=bucket_end, request=request)

        reference_feature = await reader.fetch_v2_reference_feature(
            exchange=V2_REFERENCE_EXCHANGE, symbol=request.symbol,
            market_type=request.market_type, timeframe=timeframe, bucket_ts=bucket_ts,
            calculation_version=request.calculation_version)
        _validate_reference_feature_row(
            reference_feature, timeframe=timeframe, bucket_ts=bucket_ts, request=request)

        reference_klines: Optional[tuple] = None
        reference_extrema: Optional[V2ReferenceExtrema] = None
        if timeframe in STRUCTURAL_OHLC_TIMEFRAMES:
            if reference_feature is not None and _reference_feature_gate_passes(reference_feature):
                fetched_klines = await reader.fetch_v2_reference_klines(
                    exchange=V2_REFERENCE_EXCHANGE, symbol=request.symbol,
                    bucket_start=bucket_ts, bucket_end=bucket_end)
                _validate_reference_klines_identity(
                    fetched_klines, exchange=V2_REFERENCE_EXCHANGE, symbol=request.symbol)
                reference_extrema = derive_reference_extrema(
                    timeframe=timeframe, bucket_ts=bucket_ts,
                    reference_feature=reference_feature, reference_klines=fetched_klines)
                reference_klines = fetched_klines
            # else: gate fails or reference_feature missing -> no raw fetch;
            # reference_klines/reference_extrema stay None (§30).

        # Deep-freeze every family right before it is stored: the reader
        # is a structural Protocol, not necessarily storage.db.Database,
        # so nothing above can be assumed to have already detached its
        # nested dict/list values (see `_deep_freeze`'s own docstring).
        by_timeframe[timeframe] = V2TimeframeInputs(
            timeframe=timeframe, bucket_ts=bucket_ts, bucket_end=bucket_end,
            consensus=_deep_freeze(consensus), percentiles=_deep_freeze(percentiles),
            health=_deep_freeze(health),
            reference_feature=_deep_freeze(reference_feature),
            reference_klines=_deep_freeze(reference_klines),
            reference_extrema=reference_extrema,
        )

    return V2AlignedInputs(
        T=request.T, symbol=request.symbol, market_type=request.market_type,
        calculation_version=request.calculation_version,
        feature_schema_version=request.feature_schema_version,
        reference_exchange=V2_REFERENCE_EXCHANGE,
        by_timeframe=MappingProxyType(by_timeframe),
    )
