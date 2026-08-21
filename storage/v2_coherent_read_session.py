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
connection; `_conn` is set once in `__init__` and never reassigned. This
is what makes the "raw-new/derived-old" gap unreachable through this
session: a correction that commits after the snapshot was taken is
invisible to every subsequent read the session performs, and the
publication-state CLEAN/DIRTY check
(`Database.open_v2_coherent_read_session`) is the FIRST read on this same
connection/transaction, before this object is even constructed -- so a
scope already DIRTY when the snapshot is taken is refused before any
Stage 3/5 read is attempted.

Pure structural glue only: no retries, no transaction management, no
validation logic beyond what each delegated reader/validator already
owns, no clock/`uuid`/`random` access.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, Optional, Sequence

__all__ = ["V2CoherentReadSession"]


class V2CoherentReadSession:
    """Structurally satisfies `V2AlignedInputReader` AND
    `V2SetupHistoryReader` (`analytics/forecasting_v2/ports.py`) over ONE
    pinned connection/transaction. Construct only via
    `Database.open_v2_coherent_read_session`."""

    __slots__ = ("_conn",)

    def __init__(self, conn) -> None:
        self._conn = conn

    # -- V2AlignedInputReader (Stage 3) --------------------------------
    async def fetch_v2_consensus_feature(
        self, *, symbol: str, market_type: str, timeframe: str,
        bucket_ts: datetime, calculation_version: str,
    ) -> Optional[Mapping]:
        from storage.v2_alignment_readers import (
            read_v2_consensus_feature, validate_consensus_feature_args)
        validate_consensus_feature_args(
            symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=calculation_version)
        return await read_v2_consensus_feature(
            self._conn, symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=calculation_version)

    async def fetch_v2_consensus_percentiles(
        self, *, symbol: str, market_type: str, timeframe: str,
        bucket_ts: datetime, calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        from storage.v2_alignment_readers import (
            read_v2_consensus_percentiles, validate_consensus_feature_args)
        validate_consensus_feature_args(
            symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=calculation_version)
        return await read_v2_consensus_percentiles(
            self._conn, symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=calculation_version)

    async def fetch_v2_data_health_at_cutoff(
        self, *, symbol: str, market_type: str, exchanges: Sequence[str],
        metrics: Sequence[str], cutoff_ts: datetime, calculation_version: str,
    ) -> Mapping:
        from storage.v2_alignment_readers import (
            read_v2_data_health_at_cutoff, validate_data_health_args)
        validated_exchanges, validated_metrics = validate_data_health_args(
            symbol=symbol, market_type=market_type, exchanges=exchanges,
            metrics=metrics, cutoff_ts=cutoff_ts, calculation_version=calculation_version)
        return await read_v2_data_health_at_cutoff(
            self._conn, symbol=symbol, market_type=market_type,
            exchanges=validated_exchanges, metrics=validated_metrics,
            cutoff_ts=cutoff_ts, calculation_version=calculation_version)

    async def fetch_v2_reference_feature(
        self, *, exchange: str, symbol: str, market_type: str, timeframe: str,
        bucket_ts: datetime, calculation_version: str,
    ) -> Optional[Mapping]:
        from storage.v2_alignment_readers import (
            read_v2_reference_feature, validate_reference_feature_args)
        validate_reference_feature_args(
            exchange=exchange, symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_ts=bucket_ts, calculation_version=calculation_version)
        return await read_v2_reference_feature(
            self._conn, exchange=exchange, symbol=symbol, market_type=market_type,
            timeframe=timeframe, bucket_ts=bucket_ts, calculation_version=calculation_version)

    async def fetch_v2_reference_klines(
        self, *, exchange: str, symbol: str, bucket_start: datetime, bucket_end: datetime,
    ) -> "tuple[Mapping, ...]":
        from storage.v2_alignment_readers import (
            read_v2_reference_klines, validate_reference_klines_args)
        validate_reference_klines_args(
            exchange=exchange, symbol=symbol, bucket_start=bucket_start, bucket_end=bucket_end)
        return await read_v2_reference_klines(
            self._conn, exchange=exchange, symbol=symbol,
            bucket_start=bucket_start, bucket_end=bucket_end)

    # -- V2SetupHistoryReader (Stage 5) ---------------------------------
    async def fetch_v2_consensus_feature_window(
        self, *, symbol: str, market_type: str, timeframe: str,
        bucket_start: datetime, bucket_end: datetime, calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        from storage.v2_setup_readers import (
            read_v2_consensus_feature_window, validate_consensus_feature_window_args)
        validate_consensus_feature_window_args(
            symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_start=bucket_start, bucket_end=bucket_end,
            calculation_version=calculation_version)
        return await read_v2_consensus_feature_window(
            self._conn, symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_start=bucket_start, bucket_end=bucket_end,
            calculation_version=calculation_version)

    async def fetch_v2_consensus_percentile_window(
        self, *, symbol: str, market_type: str, metric: str, timeframe: str,
        percentile_window: str, bucket_start: datetime, bucket_end: datetime,
        calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        from storage.v2_setup_readers import (
            read_v2_consensus_percentile_window, validate_consensus_percentile_window_args)
        validate_consensus_percentile_window_args(
            symbol=symbol, market_type=market_type, metric=metric, timeframe=timeframe,
            percentile_window=percentile_window, bucket_start=bucket_start,
            bucket_end=bucket_end, calculation_version=calculation_version)
        return await read_v2_consensus_percentile_window(
            self._conn, symbol=symbol, market_type=market_type, metric=metric,
            timeframe=timeframe, percentile_window=percentile_window,
            bucket_start=bucket_start, bucket_end=bucket_end,
            calculation_version=calculation_version)

    async def fetch_v2_reference_feature_window(
        self, *, exchange: str, symbol: str, market_type: str, timeframe: str,
        bucket_start: datetime, bucket_end: datetime, calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        from storage.v2_setup_readers import (
            read_v2_reference_feature_window, validate_reference_feature_window_args)
        validate_reference_feature_window_args(
            exchange=exchange, symbol=symbol, market_type=market_type, timeframe=timeframe,
            bucket_start=bucket_start, bucket_end=bucket_end,
            calculation_version=calculation_version)
        return await read_v2_reference_feature_window(
            self._conn, exchange=exchange, symbol=symbol, market_type=market_type,
            timeframe=timeframe, bucket_start=bucket_start, bucket_end=bucket_end,
            calculation_version=calculation_version)

    async def fetch_v2_instrument(
        self, *, exchange: str, symbol: str, market_type: str, as_of: datetime,
    ) -> Optional[Mapping]:
        from storage.v2_setup_readers import read_v2_instrument, validate_instrument_args
        validate_instrument_args(exchange=exchange, symbol=symbol, market_type=market_type, as_of=as_of)
        return await read_v2_instrument(
            self._conn, exchange=exchange, symbol=symbol, market_type=market_type, as_of=as_of)
