"""
V2-H2e: the canonical ONE-coherent-V2-read-session object
(`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3.4).

`V2CoherentReadSession` pins exactly ONE already-acquired asyncpg
connection, already inside ONE `REPEATABLE READ, readonly` transaction
(both owned by `Database.open_v2_coherent_read_session`, never by this
class), and structurally satisfies BOTH `analytics.forecasting_v2.ports
.V2AlignedInputReader` and `V2SetupHistoryReader` -- every method below
exactly mirrors the corresponding `Database.fetch_v2_*` method's signature
and delegates to the SAME free reader functions
(`storage/v2_alignment_readers.py`, `storage/v2_setup_readers.py`) those
`Database` methods already use, so this module owns NO SQL and NO
row-parsing of its own.

The one deliberate difference from `Database.fetch_v2_*`: those methods
each do `async with self.pool.acquire() as conn:` -- a FRESH connection
(and therefore a fresh, unrelated snapshot) per call. This class instead
reuses `self._conn` for every call, so every read issued through one
session observes the exact same REPEATABLE READ snapshot -- there is no
attribute, method, or code path on this class that acquires a second
connection; `_conn` is set once in `__init__` and never reassigned.

**Session identity binding (tech-lead review round 2, finding 4).** A
session is opened and proven CLEAN for ONE exact `(symbol, market_type,
calculation_version)` identity (`Database.open_v2_coherent_read_session`).
Without a binding check, nothing would stop a caller from opening a
session for calculation_version A (verified CLEAN) and then calling a read
method with calculation_version B (which might be STALE) through the SAME
session object -- silently escaping the coherence check for B. Every
method below therefore checks its own `symbol`/`market_type`/
`calculation_version` arguments (whichever the method's own signature
carries -- `fetch_v2_reference_klines` has no `calculation_version` at
all, raw klines carry none; `fetch_v2_instrument` has no
`calculation_version` either, H2c's `as_of` history lookup is a distinct
generation) against the identity this session was opened for, and raises
`V2SessionIdentityError` BEFORE issuing any SQL if they differ.

**No-lookahead session boundary (tech-lead review round 4).** A session is
opened for ONE logical V2 decision boundary `decision_boundary` (`T`), not
just a `(symbol, market_type, calculation_version)` identity -- §3.4's "one
coherent data view per logical decision" freezes T as part of what the
view is coherent FOR, not merely which scope/version it reads. The storage
readers this class delegates to intentionally accept caller-supplied
bucket/window boundaries and know nothing about the outer decision T, so
without an additional guard here a CLEAN, correctly-scoped session could
still be misused to issue a read whose requested time range extends AFTER
T -- one Postgres snapshot and one calculation_version, but historically
illegal lookahead for the decision actually being made. Every method
below therefore ALSO checks its own upper-bound time argument (whichever
one the method's own signature carries) against `decision_boundary` and
raises `V2SessionBoundaryError` BEFORE issuing any SQL if it would reach
past it. This class deliberately does NOT reimplement
`selected_bucket()`/timeframe-alignment/lookback-sizing -- it owns only
the outer "never past T" bound; choosing the exact legal bucket/window
inside that bound remains the analytics layer's job."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping, Optional, Sequence

__all__ = [
    "V2CoherentReadSession", "V2SessionBoundaryError", "V2SessionIdentityError",
    "validate_decision_boundary",
]


class V2SessionIdentityError(ValueError):
    """Raised by a `V2CoherentReadSession` method when its own
    `symbol`/`market_type`/`calculation_version` argument does not match
    the identity this session was opened and proven CLEAN for. Raised
    BEFORE any SQL is issued -- the mismatched call never reaches the
    database."""


class V2SessionBoundaryError(ValueError):
    """Raised by a `V2CoherentReadSession` method when its own upper-bound
    time argument (an exact `bucket_ts`, a window's `bucket_end`, a
    `cutoff_ts`, or an instrument `as_of`) would reach PAST this session's
    frozen `decision_boundary` (T) -- historically illegal lookahead for
    the decision being made at T, even though the read would otherwise
    share the session's one coherent snapshot/scope/version. Raised BEFORE
    any SQL is issued -- the offending call never reaches the database."""


def validate_decision_boundary(value) -> datetime:
    """The same UTC-aware, whole-minute datetime discipline every other V2
    storage boundary argument uses (`storage/v2_alignment_readers.py`/
    `storage/v2_setup_readers.py`'s own `_validate_whole_minute_utc`,
    duplicated here rather than cross-imported, matching this codebase's
    existing per-module-copy convention for that helper). Exact `datetime`
    type check (never a subclass/bool), timezone-aware, UTC offset exactly
    zero, no seconds/microseconds. Never reads a wall clock -- this only
    validates the caller-supplied value's shape."""
    if type(value) is not datetime:
        raise V2SessionBoundaryError(
            f"decision_boundary must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2SessionBoundaryError("decision_boundary must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise V2SessionBoundaryError(
            f"decision_boundary must be UTC (offset 0), got {value.utcoffset()}")
    if value.second != 0 or value.microsecond != 0:
        raise V2SessionBoundaryError(
            "decision_boundary must be a whole minute (no seconds/microseconds)")
    return value


class V2CoherentReadSession:
    """Structurally satisfies `V2AlignedInputReader` AND
    `V2SetupHistoryReader` (`analytics/forecasting_v2/ports.py`) over ONE
    pinned connection/transaction, bound to ONE `(symbol, market_type,
    calculation_version)` identity AND ONE `decision_boundary` (T) no read
    may reach past. Construct only via
    `Database.open_v2_coherent_read_session`."""

    __slots__ = ("_conn", "_symbol", "_market_type", "_calculation_version", "_decision_boundary")

    def __init__(
        self, conn, *, symbol: str, market_type: str, calculation_version: str,
        decision_boundary: datetime,
    ) -> None:
        self._conn = conn
        self._symbol = symbol
        self._market_type = market_type
        self._calculation_version = calculation_version
        self._decision_boundary = validate_decision_boundary(decision_boundary)

    def _check_identity(
        self, *, symbol: "Optional[str]" = None, market_type: "Optional[str]" = None,
        calculation_version: "Optional[str]" = None,
    ) -> None:
        """Checks only the identity dimensions the calling method's own
        signature actually carries (pass `None` to skip a dimension the
        method doesn't have -- e.g. `fetch_v2_reference_klines` has no
        `calculation_version`)."""
        if symbol is not None and symbol != self._symbol:
            raise V2SessionIdentityError(
                f"session bound to symbol={self._symbol!r}, called with symbol={symbol!r}")
        if market_type is not None and market_type != self._market_type:
            raise V2SessionIdentityError(
                f"session bound to market_type={self._market_type!r}, called with "
                f"market_type={market_type!r}")
        if calculation_version is not None and calculation_version != self._calculation_version:
            raise V2SessionIdentityError(
                f"session bound to calculation_version={self._calculation_version!r}, called "
                f"with calculation_version={calculation_version!r}")

    def _check_boundary(self, *, value: datetime, name: str) -> None:
        """`value` (an exact `bucket_ts`, a window's `bucket_end`, a
        `cutoff_ts`, or an instrument `as_of`) must not be AFTER this
        session's frozen `decision_boundary` -- an upper bound only, never
        equality-only: a legitimate read of an earlier historical
        bucket/window/as-of is always allowed, only reaching past T is
        rejected. This does NOT validate `value`'s own shape (each
        delegated reader's own `validate_*_args` already does that) --
        purely the no-lookahead comparison, and it runs BEFORE that
        delegation."""
        if value > self._decision_boundary:
            raise V2SessionBoundaryError(
                f"{name}={value.isoformat()!r} is after this session's decision_boundary="
                f"{self._decision_boundary.isoformat()!r} -- no read through a coherent V2 "
                "session may reach past its frozen decision boundary (historically illegal "
                "lookahead)")

    # -- V2AlignedInputReader (Stage 3) --------------------------------
    async def fetch_v2_consensus_feature(
        self, *, symbol: str, market_type: str, timeframe: str,
        bucket_ts: datetime, calculation_version: str,
    ) -> Optional[Mapping]:
        self._check_identity(
            symbol=symbol, market_type=market_type, calculation_version=calculation_version)
        from storage.v2_alignment_readers import (
            read_v2_consensus_feature, validate_consensus_feature_args)
        validate_consensus_feature_args(
            symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=calculation_version)
        self._check_boundary(value=bucket_ts, name="bucket_ts")
        return await read_v2_consensus_feature(
            self._conn, symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=calculation_version)

    async def fetch_v2_consensus_percentiles(
        self, *, symbol: str, market_type: str, timeframe: str,
        bucket_ts: datetime, calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        self._check_identity(
            symbol=symbol, market_type=market_type, calculation_version=calculation_version)
        from storage.v2_alignment_readers import (
            read_v2_consensus_percentiles, validate_consensus_feature_args)
        validate_consensus_feature_args(
            symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=calculation_version)
        self._check_boundary(value=bucket_ts, name="bucket_ts")
        return await read_v2_consensus_percentiles(
            self._conn, symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=calculation_version)

    async def fetch_v2_data_health_at_cutoff(
        self, *, symbol: str, market_type: str, exchanges: Sequence[str],
        metrics: Sequence[str], cutoff_ts: datetime, calculation_version: str,
    ) -> Mapping:
        self._check_identity(
            symbol=symbol, market_type=market_type, calculation_version=calculation_version)
        from storage.v2_alignment_readers import (
            read_v2_data_health_at_cutoff, validate_data_health_args)
        validated_exchanges, validated_metrics = validate_data_health_args(
            symbol=symbol, market_type=market_type, exchanges=exchanges,
            metrics=metrics, cutoff_ts=cutoff_ts, calculation_version=calculation_version)
        self._check_boundary(value=cutoff_ts, name="cutoff_ts")
        return await read_v2_data_health_at_cutoff(
            self._conn, symbol=symbol, market_type=market_type,
            exchanges=validated_exchanges, metrics=validated_metrics,
            cutoff_ts=cutoff_ts, calculation_version=calculation_version)

    async def fetch_v2_reference_feature(
        self, *, exchange: str, symbol: str, market_type: str, timeframe: str,
        bucket_ts: datetime, calculation_version: str,
    ) -> Optional[Mapping]:
        self._check_identity(
            symbol=symbol, market_type=market_type, calculation_version=calculation_version)
        from storage.v2_alignment_readers import (
            read_v2_reference_feature, validate_reference_feature_args)
        validate_reference_feature_args(
            exchange=exchange, symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=calculation_version)
        self._check_boundary(value=bucket_ts, name="bucket_ts")
        return await read_v2_reference_feature(
            self._conn, exchange=exchange, symbol=symbol, market_type=market_type,
            timeframe=timeframe, bucket_ts=bucket_ts, calculation_version=calculation_version)

    async def fetch_v2_reference_klines(
        self, *, exchange: str, symbol: str, bucket_start: datetime, bucket_end: datetime,
    ) -> "tuple[Mapping, ...]":
        # No calculation_version/market_type on this raw-kline read -- only
        # symbol is checkable against the session's bound identity.
        self._check_identity(symbol=symbol)
        from storage.v2_alignment_readers import (
            read_v2_reference_klines, validate_reference_klines_args)
        validate_reference_klines_args(
            exchange=exchange, symbol=symbol, bucket_start=bucket_start, bucket_end=bucket_end)
        # Half-open [bucket_start, bucket_end) -- bucket_end == decision_boundary is
        # legal (the read strictly excludes decision_boundary itself); only
        # bucket_end > decision_boundary reaches past it.
        self._check_boundary(value=bucket_end, name="bucket_end")
        return await read_v2_reference_klines(
            self._conn, exchange=exchange, symbol=symbol,
            bucket_start=bucket_start, bucket_end=bucket_end)

    # -- V2SetupHistoryReader (Stage 5) ---------------------------------
    async def fetch_v2_consensus_feature_window(
        self, *, symbol: str, market_type: str, timeframe: str,
        bucket_start: datetime, bucket_end: datetime, calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        self._check_identity(
            symbol=symbol, market_type=market_type, calculation_version=calculation_version)
        from storage.v2_setup_readers import (
            read_v2_consensus_feature_window, validate_consensus_feature_window_args)
        validate_consensus_feature_window_args(
            symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_start=bucket_start, bucket_end=bucket_end,
            calculation_version=calculation_version)
        self._check_boundary(value=bucket_end, name="bucket_end")
        return await read_v2_consensus_feature_window(
            self._conn, symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_start=bucket_start, bucket_end=bucket_end,
            calculation_version=calculation_version)

    async def fetch_v2_consensus_percentile_window(
        self, *, symbol: str, market_type: str, metric: str, timeframe: str,
        percentile_window: str, bucket_start: datetime, bucket_end: datetime,
        calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        self._check_identity(
            symbol=symbol, market_type=market_type, calculation_version=calculation_version)
        from storage.v2_setup_readers import (
            read_v2_consensus_percentile_window, validate_consensus_percentile_window_args)
        validate_consensus_percentile_window_args(
            symbol=symbol, market_type=market_type, metric=metric, timeframe=timeframe,
            percentile_window=percentile_window, bucket_start=bucket_start,
            bucket_end=bucket_end, calculation_version=calculation_version)
        self._check_boundary(value=bucket_end, name="bucket_end")
        return await read_v2_consensus_percentile_window(
            self._conn, symbol=symbol, market_type=market_type, metric=metric,
            timeframe=timeframe, percentile_window=percentile_window,
            bucket_start=bucket_start, bucket_end=bucket_end,
            calculation_version=calculation_version)

    async def fetch_v2_reference_feature_window(
        self, *, exchange: str, symbol: str, market_type: str, timeframe: str,
        bucket_start: datetime, bucket_end: datetime, calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        self._check_identity(
            symbol=symbol, market_type=market_type, calculation_version=calculation_version)
        from storage.v2_setup_readers import (
            read_v2_reference_feature_window, validate_reference_feature_window_args)
        validate_reference_feature_window_args(
            exchange=exchange, symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_start=bucket_start, bucket_end=bucket_end,
            calculation_version=calculation_version)
        self._check_boundary(value=bucket_end, name="bucket_end")
        return await read_v2_reference_feature_window(
            self._conn, exchange=exchange, symbol=symbol, market_type=market_type,
            timeframe=timeframe, bucket_start=bucket_start, bucket_end=bucket_end,
            calculation_version=calculation_version)

    async def fetch_v2_instrument(
        self, *, exchange: str, symbol: str, market_type: str, as_of: datetime,
    ) -> Optional[Mapping]:
        # No calculation_version on H2c's as-of instrument lookup -- a
        # distinct generation (instrument-metadata revision), never this
        # session's own calculation_version identity.
        self._check_identity(symbol=symbol, market_type=market_type)
        from storage.v2_setup_readers import read_v2_instrument, validate_instrument_args
        validate_instrument_args(exchange=exchange, symbol=symbol, market_type=market_type, as_of=as_of)
        # Every current real Stage 5 caller passes as_of=context.T exactly
        # (trend_pullback_inputs.py/compression_breakout_inputs.py/
        # confirmed_breakout_inputs.py); H2c's own as-of semantics
        # (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §12.5a) do not
        # themselves require EXACT equality to T, only that the resolved
        # history version is the one in effect at as_of and never a future
        # one -- so the upper bound here is the same "<= decision_boundary"
        # discipline as every other method, not a stricter equality-only
        # rule this task did not ask for. An EARLIER legitimate as_of
        # remains allowed; only as_of > decision_boundary is lookahead.
        self._check_boundary(value=as_of, name="as_of")
        return await read_v2_instrument(
            self._conn, exchange=exchange, symbol=symbol, market_type=market_type, as_of=as_of)
