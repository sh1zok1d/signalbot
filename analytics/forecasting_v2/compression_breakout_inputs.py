"""
V2 `COMPRESSION_BREAKOUT` historical input assembler (Stage 5 — Setup
Detectors, PR 3 of ~4, docs/FORECASTING_ROADMAP.md §I stage 5).

Narrow asynchronous composition layer over `V2SetupHistoryReader`
(`ports.py`, #39) that turns "one already-computed `V2ContextSnapshot`"
into "the exact historical rows `compression_breakout.py::detect_
compression_breakout` needs" -- mirroring `trend_pullback_inputs.py`'s
own layering split (pure classification logic in one module, narrow async
read composition in a sibling). This module performs ZERO setup-detector
classification of its own: it never computes a compression score, never
selects a compression run, never derives a structural range, and never
decides whether the fetched history is usable -- `detect_compression_
breakout()` alone interprets what this module reads.

**Unlike `trend_pullback_inputs.py`, there is NO formation-boundary skip
here (load-bearing).** `TREND_PULLBACK` only forms on 15m formation
boundaries, so its loader can cheaply return `None` (zero reads) for a
non-formation `T`. `COMPRESSION_BREAKOUT`'s breakout trigger is a 5m-close
event -- EVERY legal V2 5m decision boundary `T` is a possible breakout
instant (`compression_breakout.py`'s own docstring). This loader therefore
always issues its full read set for any legal `context.T`; there is no
cheaper "not a formation boundary" case to special-case here.

**Reads exactly seven things, nothing else:**

  1. `reader.fetch_v2_consensus_feature_window(...)` -- the exact
     `COMPRESSION_LOOKBACK=16`-bucket 15m consensus window
     `[B15 - 15*15m, B15]` (dual-purpose: per-bucket compression quality
     AND, via its own final 14 rows, `RANGE_PROXY_pct(15m,14,B15)` -- no
     second 14-row query).
  2. `reader.fetch_v2_consensus_percentile_window(...)` -- the matching
     16-bucket `range_width_pct_median`/`30d` consensus-percentile
     window, for `compression_score()`.
  3. `reader.fetch_v2_reference_feature_window(...)` -- the same
     16-bucket 15m canonical-`V2_REFERENCE_EXCHANGE` reference-feature
     window (also supplies the B15 reference close for
     `protection_buffer()`).
  4. `reader.fetch_v2_reference_klines(...)` -- ONE raw-1m-bar window
     `[B15 - 15*15m, B15 + 15m)` (half-open), wide enough to cover the
     whole 16-bucket lookback; `detect_compression_breakout()` alone
     splits these by owning 15m bucket and only actually needs the
     SELECTED compression run's own buckets.
  5. `reader.fetch_v2_reference_feature_window(...)` -- exactly the two
     closed 5m reference-feature buckets `[B5 - 5m, B5]` the fresh-cross
     check needs.
  6. `reader.fetch_v2_consensus_feature_window(...)` -- exactly the
     current `B5` 5m consensus trigger row (`bucket_start=bucket_end=B5`).
  7. `reader.fetch_v2_instrument(..., as_of=context.T)` -- the single
     canonical-exchange historical metadata version actually in effect at
     `context.T` (V2-H2c), for `protection_buffer()`'s `tick_size`. Never
     the current `exchange_instruments` LKG row -- see `ports.py`'s
     `V2SetupHistoryReader.fetch_v2_instrument` docstring.

No 5m/15m percentile beyond item 2, no 1h/4h historical window, no OI/
funding/liquidation/health/orderbook/spot/CoinGlass/marketcap read of any
kind, and no extra current-15m or second RANGE_PROXY read (both already
covered by item 1's own window).

Sequential awaits, in that exact order (no `asyncio.gather` --
deterministic, easy-to-audit call order, mirroring `aligned_inputs.py`/
`trend_pullback_inputs.py`'s own posture, not a runtime-performance
claim). Every one of `storage/v2_setup_readers.py`'s readers (plus Stage
3's `read_v2_reference_klines`, reused unchanged) already returns fully
detached (`MappingProxyType`/`tuple`) rows, so this module does not
re-freeze anything.

**This module does not decide the setup.** It returns whatever history
physically exists -- even a compression window that will later turn out
non-qualifying, incomplete, or gate-failed once `detect_compression_
breakout()` inspects it. `V2CompressionBreakoutInputs` is trusted-shape
from a real reader by construction, but `detect_compression_breakout()`
still independently re-validates every row's identity/shape -- this
loader never pre-filters or interprets rows itself.

**Layering.** Depends only on `ports.V2SetupHistoryReader` (a structural
`Protocol` -- never imports `storage.db.Database` or
`storage.v2_setup_readers` directly, so a minimal test double never needs
to import `storage/` at all), `context_snapshot.V2ContextSnapshot`,
`alignment.selected_bucket`, `aligned_inputs.V2_REFERENCE_EXCHANGE`, and
this package's own `compression_breakout.py` (`COMPRESSION_LOOKBACK`,
`COMPRESSION_PERCENTILE_WINDOW`, `V2CompressionBreakoutInputs`,
`V2CompressionBreakoutError` -- the last one only for this module's own
cheap non-`V2ContextSnapshot` `context` boundary check, never for
re-validating detector semantics). If `reader` itself raises (a real/fake
reader's own domain error, e.g. `V2SetupReaderError`), this module never
swallows it into `None` -- propagated unchanged.

Pure of side effects beyond the seven reads above: no wall clock (no
`datetime.now()`/`utcnow()`/`time.time()`), no writes, no config loading,
no `random`/`uuid`. `context.T` is the only logical time input.
"""
from __future__ import annotations

from datetime import timedelta

from analytics.forecasting_v2.aligned_inputs import V2_REFERENCE_EXCHANGE
from analytics.forecasting_v2.alignment import TIMEFRAME_MINUTES, selected_bucket
from analytics.forecasting_v2.compression_breakout import (
    COMPRESSION_LOOKBACK, COMPRESSION_PERCENTILE_WINDOW, V2CompressionBreakoutError,
    V2CompressionBreakoutInputs,
)
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.ports import V2SetupHistoryReader

__all__ = ["load_compression_breakout_inputs"]

_FIVE_MIN = timedelta(minutes=TIMEFRAME_MINUTES["5m"])
_FIFTEEN_MIN = timedelta(minutes=TIMEFRAME_MINUTES["15m"])
_COMPRESSION_METRIC = "range_width_pct_median"


async def load_compression_breakout_inputs(
    reader: V2SetupHistoryReader, *, context: V2ContextSnapshot,
) -> V2CompressionBreakoutInputs:
    """Assemble the exact historical rows `detect_compression_breakout()`
    needs for `context.T`, reading through `reader` (a
    `V2SetupHistoryReader`) only. Unlike `load_trend_pullback_inputs()`,
    every legal V2 5m decision boundary is a possible breakout instant --
    this function always issues its full 7-read set (see module
    docstring), never a cheap `None` short-circuit for a "wrong kind of"
    `T`.

    Never reads a clock, environment, config file, or generates a
    random/uuid value. Propagates any exception `reader` itself raises,
    unchanged.

    Raises `V2CompressionBreakoutError` for a non-`V2ContextSnapshot`
    `context` (cheap public-boundary hardening, checked before
    `context.T` is ever accessed) -- this is the only validation this
    module performs; it never re-validates detector semantics (that
    remains `detect_compression_breakout()`'s own job)."""
    if not isinstance(context, V2ContextSnapshot):
        raise V2CompressionBreakoutError(
            f"context must be a V2ContextSnapshot, got {type(context).__name__}")

    B5 = selected_bucket("5m", context.T)
    B15 = selected_bucket("15m", context.T)
    lookback_start_15m = B15 - (COMPRESSION_LOOKBACK - 1) * _FIFTEEN_MIN
    B5_previous = B5 - _FIVE_MIN

    consensus_15m_rows = await reader.fetch_v2_consensus_feature_window(
        symbol=context.symbol, market_type=context.market_type, timeframe="15m",
        bucket_start=lookback_start_15m, bucket_end=B15,
        calculation_version=context.calculation_version)

    percentile_15m_rows = await reader.fetch_v2_consensus_percentile_window(
        symbol=context.symbol, market_type=context.market_type,
        metric=_COMPRESSION_METRIC, timeframe="15m",
        percentile_window=COMPRESSION_PERCENTILE_WINDOW,
        bucket_start=lookback_start_15m, bucket_end=B15,
        calculation_version=context.calculation_version)

    reference_15m_rows = await reader.fetch_v2_reference_feature_window(
        exchange=V2_REFERENCE_EXCHANGE, symbol=context.symbol, market_type=context.market_type,
        timeframe="15m", bucket_start=lookback_start_15m, bucket_end=B15,
        calculation_version=context.calculation_version)

    reference_1m_rows = await reader.fetch_v2_reference_klines(
        exchange=V2_REFERENCE_EXCHANGE, symbol=context.symbol,
        bucket_start=lookback_start_15m, bucket_end=B15 + _FIFTEEN_MIN)

    reference_5m_rows = await reader.fetch_v2_reference_feature_window(
        exchange=V2_REFERENCE_EXCHANGE, symbol=context.symbol, market_type=context.market_type,
        timeframe="5m", bucket_start=B5_previous, bucket_end=B5,
        calculation_version=context.calculation_version)

    consensus_5m_rows = await reader.fetch_v2_consensus_feature_window(
        symbol=context.symbol, market_type=context.market_type, timeframe="5m",
        bucket_start=B5, bucket_end=B5,
        calculation_version=context.calculation_version)

    instrument = await reader.fetch_v2_instrument(
        exchange=V2_REFERENCE_EXCHANGE, symbol=context.symbol, market_type=context.market_type,
        as_of=context.T)

    return V2CompressionBreakoutInputs(
        context=context,
        consensus_15m_rows=tuple(consensus_15m_rows),
        percentile_15m_rows=tuple(percentile_15m_rows),
        reference_15m_rows=tuple(reference_15m_rows),
        reference_1m_rows=tuple(reference_1m_rows),
        reference_5m_rows=tuple(reference_5m_rows),
        consensus_5m_rows=tuple(consensus_5m_rows),
        instrument=instrument,
    )
