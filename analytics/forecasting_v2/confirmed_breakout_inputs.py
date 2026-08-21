"""
V2 `CONFIRMED_BREAKOUT` historical input assembler (Stage 5 — Setup
Detectors, PR 4 of ~4, FINAL planned Stage 5 detector PR,
docs/FORECASTING_ROADMAP.md §I stage 5).

Narrow asynchronous composition layer over `V2SetupHistoryReader`
(`ports.py`, #39) that turns "one already-computed `V2ContextSnapshot`"
into "the exact historical rows `confirmed_breakout.py::detect_confirmed_
breakout` needs" -- mirroring `compression_breakout_inputs.py`'s own
layering split (pure classification logic in one module, narrow async
read composition in a sibling). This module performs ZERO setup-detector
classification of its own: it never derives an `HTF_high`/`HTF_low`,
never selects a resistance/support anchor, and never decides whether the
fetched history is usable -- `detect_confirmed_breakout()` alone
interprets what this module reads.

**Every legal 5m `T` issues the full read set (no 1h-boundary skip),
like `compression_breakout_inputs.py` and UNLIKE `trend_pullback_
inputs.py`.** §7.3's breakout trigger is a 5m-close event -- every legal
V2 5m decision boundary is a possible `CONFIRMED_BREAKOUT` evaluation
instant, so there is no cheaper "not the right kind of boundary" case to
special-case here.

**Reads exactly FIVE things, nothing else (load-bearing difference from
`compression_breakout_inputs.py`'s seven -- §7.3 has no taker-flow/
agreement EARLY_SIGNAL requirement for this family, so there is
deliberately NO current-B5 5m consensus read here, unlike #41's loader;
see `confirmed_breakout.py`'s own docstring):**

  1. `reader.fetch_v2_consensus_feature_window(...)` -- the exact
     `RANGE_PROXY_N=14`-bucket 1h consensus window `[B1h-13h, B1h]`
     (dual-purpose: `RANGE_PROXY_pct(1h,14,B1h)` AND the current-B1h
     setup-quality gate -- a SEPARATE, smaller window from read #2's
     48-bucket structural lookback, which carries no consensus rows at
     all).
  2. `reader.fetch_v2_reference_feature_window(...)` -- the exact
     `LEVEL_LOOKBACK=48`-bucket 1h reference-feature window
     `[B1h-47h, B1h]`, canonical `V2_REFERENCE_EXCHANGE` only.
  3. `reader.fetch_v2_reference_klines(...)` -- ONE raw-1m-bar window
     `[B1h-47h, B1h+1h)` (half-open), wide enough to cover the whole 48h
     structural lookback; `detect_confirmed_breakout()` alone splits
     these by owning 1h bucket.
  4. `reader.fetch_v2_reference_feature_window(...)` -- exactly the two
     closed 5m reference-feature buckets `[B5-5m, B5]` the fresh-cross
     check needs.
  5. `reader.fetch_v2_instrument(..., as_of=context.T)` -- the single
     canonical-exchange historical metadata version actually in effect at
     `context.T` (V2-H2c), for `protection_buffer()`'s `tick_size`. Never
     the current `exchange_instruments` LKG row -- see `ports.py`'s
     `V2SetupHistoryReader.fetch_v2_instrument` docstring.

No 1h/5m percentile read, no current-B5 5m consensus read, no 15m/4h
historical window, no OI/funding/liquidation/health/orderbook/spot/
CoinGlass/marketcap read of any kind, and no extra current-1h read (B1h's
own reference row is already inside the 48-bucket structural window's own
last entry -- no second storage read).

Sequential awaits, in that exact order (no `asyncio.gather` --
deterministic, easy-to-audit call order, mirroring `aligned_inputs.py`/
`trend_pullback_inputs.py`/`compression_breakout_inputs.py`'s own
posture, not a runtime-performance claim). Every one of
`storage/v2_setup_readers.py`'s readers (plus Stage 3's `read_v2_
reference_klines`, reused unchanged) already returns fully detached
(`MappingProxyType`/`tuple`) rows, so this module does not re-freeze
anything.

**This module does not decide the setup.** It returns whatever history
physically exists -- even a structural window that will later turn out
non-qualifying, incomplete, or gate-failed once `detect_confirmed_
breakout()` inspects it. `V2ConfirmedBreakoutInputs` is trusted-shape
from a real reader by construction, but `detect_confirmed_breakout()`
still independently re-validates every row's identity/shape -- this
loader never pre-filters or interprets rows itself.

**Layering.** Depends only on `ports.V2SetupHistoryReader` (a structural
`Protocol` -- never imports `storage.db.Database` or `storage.v2_setup_
readers` directly, so a minimal test double never needs to import
`storage/` at all), `context_snapshot.V2ContextSnapshot`,
`alignment.selected_bucket`, `aligned_inputs.V2_REFERENCE_EXCHANGE`, and
this package's own `confirmed_breakout.py` (`LEVEL_LOOKBACK`,
`V2ConfirmedBreakoutInputs`, `V2ConfirmedBreakoutError` -- the last one
only for this module's own cheap non-`V2ContextSnapshot` `context`
boundary check, never for re-validating detector semantics). If `reader`
itself raises (a real/fake reader's own domain error, e.g.
`V2SetupReaderError`), this module never swallows it into `None` --
propagated unchanged.

Pure of side effects beyond the five reads above: no wall clock (no
`datetime.now()`/`utcnow()`/`time.time()`), no writes, no config loading,
no `random`/`uuid`. `context.T` is the only logical time input.
"""
from __future__ import annotations

from datetime import timedelta

from analytics.forecasting_v2.aligned_inputs import V2_REFERENCE_EXCHANGE
from analytics.forecasting_v2.alignment import TIMEFRAME_MINUTES, selected_bucket
from analytics.forecasting_v2.confirmed_breakout import (
    LEVEL_LOOKBACK, V2ConfirmedBreakoutError, V2ConfirmedBreakoutInputs,
)
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.ports import V2SetupHistoryReader
from analytics.forecasting_v2.setup_common import RANGE_PROXY_N

__all__ = ["load_confirmed_breakout_inputs"]

_FIVE_MIN = timedelta(minutes=TIMEFRAME_MINUTES["5m"])
_ONE_HOUR = timedelta(minutes=TIMEFRAME_MINUTES["1h"])


async def load_confirmed_breakout_inputs(
    reader: V2SetupHistoryReader, *, context: V2ContextSnapshot,
) -> V2ConfirmedBreakoutInputs:
    """Assemble the exact historical rows `detect_confirmed_breakout()`
    needs for `context.T`, reading through `reader` (a
    `V2SetupHistoryReader`) only. Like `load_compression_breakout_
    inputs()`, every legal V2 5m decision boundary is a possible
    breakout instant -- this function always issues its full 5-read set
    (see module docstring), never a cheap `None` short-circuit for a
    "wrong kind of" `T`.

    Never reads a clock, environment, config file, or generates a
    random/uuid value. Propagates any exception `reader` itself raises,
    unchanged.

    Raises `V2ConfirmedBreakoutError` for a non-`V2ContextSnapshot`
    `context` (cheap public-boundary hardening, checked before
    `context.T` is ever accessed) -- this is the only validation this
    module performs; it never re-validates detector semantics (that
    remains `detect_confirmed_breakout()`'s own job)."""
    if not isinstance(context, V2ContextSnapshot):
        raise V2ConfirmedBreakoutError(
            f"context must be a V2ContextSnapshot, got {type(context).__name__}")

    B5 = selected_bucket("5m", context.T)
    B1h = selected_bucket("1h", context.T)
    proxy_start = B1h - (RANGE_PROXY_N - 1) * _ONE_HOUR
    level_start = B1h - (LEVEL_LOOKBACK - 1) * _ONE_HOUR

    consensus_1h_rows = await reader.fetch_v2_consensus_feature_window(
        symbol=context.symbol, market_type=context.market_type, timeframe="1h",
        bucket_start=proxy_start, bucket_end=B1h,
        calculation_version=context.calculation_version)

    reference_1h_rows = await reader.fetch_v2_reference_feature_window(
        exchange=V2_REFERENCE_EXCHANGE, symbol=context.symbol, market_type=context.market_type,
        timeframe="1h", bucket_start=level_start, bucket_end=B1h,
        calculation_version=context.calculation_version)

    reference_1m_rows = await reader.fetch_v2_reference_klines(
        exchange=V2_REFERENCE_EXCHANGE, symbol=context.symbol,
        bucket_start=level_start, bucket_end=B1h + _ONE_HOUR)

    reference_5m_rows = await reader.fetch_v2_reference_feature_window(
        exchange=V2_REFERENCE_EXCHANGE, symbol=context.symbol, market_type=context.market_type,
        timeframe="5m", bucket_start=B5 - _FIVE_MIN, bucket_end=B5,
        calculation_version=context.calculation_version)

    instrument = await reader.fetch_v2_instrument(
        exchange=V2_REFERENCE_EXCHANGE, symbol=context.symbol, market_type=context.market_type,
        as_of=context.T)

    return V2ConfirmedBreakoutInputs(
        context=context,
        consensus_1h_rows=tuple(consensus_1h_rows),
        reference_1h_rows=tuple(reference_1h_rows),
        reference_1m_rows=tuple(reference_1m_rows),
        reference_5m_rows=tuple(reference_5m_rows),
        instrument=instrument,
    )
