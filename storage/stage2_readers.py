"""
Stage 2.1 raw-input reader: fetches the fixed set of Stage 1 raw rows + Stage 2
metadata/capability rows needed to assemble ONE ExchangeFeatureRequest for one
(exchange, symbol, market_type, bucket).

Pure storage layer: this module builds SQL and an immutable raw bundle only. It
performs NO analytics computation and imports NO analytics module. All SQL is
static/trusted; no caller-provided identifier is ever interpolated into SQL.

The Stage 1 raw tables (klines_1m, open_interest, funding_rate, liquidations)
have NO market_type column, so their queries never reference it. The Stage 2
tables (exchange_instruments, symbol_exchange_capabilities) DO carry market_type.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Mapping, Optional, Sequence


class Stage2ReaderError(ValueError):
    """Invalid raw-bundle request argument (validated before any DB access)."""


# ---- static, trusted SQL (no SELECT *, no dynamic identifiers) --------------
# A. Klines for this bucket [start, end). Underlying 1m rows (never a continuous
#    aggregate) so the pure core can compute exact bar completeness + taker/CVD.
KLINES_SQL = """
SELECT exchange, symbol, ts, open, high, low, close, volume,
       taker_buy_volume, taker_sell_volume
FROM klines_1m
WHERE exchange = $1 AND symbol = $2 AND ts >= $3 AND ts < $4
ORDER BY ts ASC
"""

# B. Open interest inside this bucket [start, end). Authoritative oi_raw/oi_unit
#    only; NULLs are NOT filtered in SQL — the adapter fails loudly on them.
OPEN_INTEREST_SQL = """
SELECT exchange, symbol, ts, oi_raw, oi_unit
FROM open_interest
WHERE exchange = $1 AND symbol = $2 AND ts >= $3 AND ts < $4
ORDER BY ts ASC
"""

# C. Latest funding STRICTLY before bucket end (no look-ahead, no lower bound).
LATEST_FUNDING_SQL = """
SELECT exchange, symbol, ts, funding_rate
FROM funding_rate
WHERE exchange = $1 AND symbol = $2 AND ts < $3
ORDER BY ts DESC
LIMIT 1
"""

# D. Liquidations inside this bucket [start, end); deterministic (ts, id) order.
LIQUIDATIONS_SQL = """
SELECT id, exchange, symbol, ts, side, notional, is_snapshot_feed
FROM liquidations
WHERE exchange = $1 AND symbol = $2 AND ts >= $3 AND ts < $4
ORDER BY ts ASC, id ASC
"""

# E. Instrument metadata (Stage 2 authority) — uses market_type.
INSTRUMENT_SQL = """
SELECT exchange, symbol, market_type, exchange_instrument_id, quantity_unit,
       contract_multiplier, tick_size, price_precision, quantity_precision,
       metadata_source, fetched_at, is_stale, note
FROM exchange_instruments
WHERE exchange = $1 AND symbol = $2 AND market_type = $3
"""

# F. Liquidation capability (Stage 2 authority) — uses market_type + metric.
LIQUIDATION_CAPABILITY_SQL = """
SELECT exchange, symbol, market_type, metric, live_supported, historical_supported,
       coverage_type, expected_freshness_s, enabled
FROM symbol_exchange_capabilities
WHERE exchange = $1 AND symbol = $2 AND market_type = $3 AND metric = $4
"""


# ---- immutable raw bundle ---------------------------------------------------
@dataclass(frozen=True)
class ExchangeFeatureRawBundle:
    """Detached, connection-independent, deeply-immutable raw inputs. Every row
    is a read-only mapping; collection fields are tuples. No analytics types."""
    klines: tuple[Mapping, ...]
    open_interest: tuple[Mapping, ...]
    latest_funding: Optional[Mapping]
    liquidations: tuple[Mapping, ...]
    instrument: Optional[Mapping]
    liquidation_capability: Optional[Mapping]


def _freeze_row(record) -> Mapping:
    """Detach an asyncpg Record (or any mapping) into an immutable snapshot that
    cannot be mutated through the bundle and does not retain the connection."""
    return MappingProxyType(dict(record))


def _freeze_rows(records: Sequence) -> tuple[Mapping, ...]:
    return tuple(_freeze_row(r) for r in records)


# ---- argument validation (BEFORE any connection is acquired) ---------------
def _nonblank(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Stage2ReaderError(f"{name} must be a non-empty string")
    return value


def _utc_dt(value, name: str) -> datetime:
    # bool is an int, not a datetime, so it is rejected here too.
    if not isinstance(value, datetime):
        raise Stage2ReaderError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise Stage2ReaderError(f"{name} must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise Stage2ReaderError(f"{name} must be UTC (offset 0), got {value.utcoffset()}")
    return value


def validate_raw_bundle_args(*, exchange: str, symbol: str, market_type: str,
                             bucket_start: datetime, bucket_end: datetime) -> None:
    """Validate every argument. Raises Stage2ReaderError; performs no I/O."""
    _nonblank(exchange, "exchange")
    _nonblank(symbol, "symbol")
    _nonblank(market_type, "market_type")
    _utc_dt(bucket_start, "bucket_start")
    _utc_dt(bucket_end, "bucket_end")
    if not (bucket_start < bucket_end):
        raise Stage2ReaderError(
            f"bucket_start ({bucket_start.isoformat()}) must be < bucket_end "
            f"({bucket_end.isoformat()})")


# ---- the fixed reads on a single caller-supplied connection -----------------
async def read_exchange_feature_raw_bundle(
    conn, *, exchange: str, symbol: str, market_type: str,
    bucket_start: datetime, bucket_end: datetime,
) -> ExchangeFeatureRawBundle:
    """Run the six fixed reads on ONE already-acquired connection and return an
    immutable bundle. Arguments must already be validated. No writes, no clock.
    """
    klines = await conn.fetch(KLINES_SQL, exchange, symbol, bucket_start, bucket_end)
    open_interest = await conn.fetch(OPEN_INTEREST_SQL, exchange, symbol,
                                     bucket_start, bucket_end)
    funding_row = await conn.fetchrow(LATEST_FUNDING_SQL, exchange, symbol, bucket_end)
    liquidations = await conn.fetch(LIQUIDATIONS_SQL, exchange, symbol,
                                    bucket_start, bucket_end)
    instrument_row = await conn.fetchrow(INSTRUMENT_SQL, exchange, symbol, market_type)
    capability_row = await conn.fetchrow(
        LIQUIDATION_CAPABILITY_SQL, exchange, symbol, market_type, "liquidations")

    return ExchangeFeatureRawBundle(
        klines=_freeze_rows(klines),
        open_interest=_freeze_rows(open_interest),
        latest_funding=_freeze_row(funding_row) if funding_row is not None else None,
        liquidations=_freeze_rows(liquidations),
        instrument=_freeze_row(instrument_row) if instrument_row is not None else None,
        liquidation_capability=(_freeze_row(capability_row)
                                if capability_row is not None else None),
    )
