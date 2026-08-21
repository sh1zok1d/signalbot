"""
V2 `TREND_PULLBACK` historical input assembler (Stage 5 — Setup
Detectors, PR 2 of ~4, docs/FORECASTING_ROADMAP.md §I stage 5).

Narrow asynchronous composition layer over `V2SetupHistoryReader`
(`ports.py`, #39) that turns "one already-computed `V2ContextSnapshot`"
into "the exact historical rows `trend_pullback.py::detect_trend_pullback`
needs" -- mirroring Stage 3's own `aligned_inputs.py` layering split
(pure classification logic in one module, narrow async read composition in
a sibling). This module performs ZERO setup-detector classification of
its own: it never inspects `regime_4h`/`bias_1h`, never computes a
retracement, and never decides whether the fetched history is usable --
`detect_trend_pullback()` alone interprets what this module reads (see
`trend_pullback.py`'s own docstring for the Stage 5/6 boundary this whole
package respects).

**Only skips storage reads for a non-15m-formation `T` (§7 formation
clock).** `load_trend_pullback_inputs()` re-derives `B15 =
selected_bucket("15m", context.T)` and returns `None` immediately -- zero
`reader` calls -- unless `B15 + 15m == context.T`. This is the SAME
formation-boundary rule `detect_trend_pullback()` itself enforces (kept in
exact sync, never re-derived independently) -- but re-checking it here
means a caller repeatedly invoking this loader at every 5m tick (`T=12:15,
12:20, 12:25, ...`) only ever issues real reads at the 15m boundaries,
never redundantly fetches 48+14 rows for a `T` that could not possibly
qualify.

**Reads exactly three things, nothing else (§13 — this PR needs no
percentile/kline/5m/1h/4h/health/OI/funding/liquidation/taker-flow read
at all; the already-computed `context` supplies the 4h/1h facts):**

  1. `reader.fetch_v2_reference_feature_window(...)` -- the exact
     `LOOKBACK_15M=48`-bucket reference-close window
     `[B15 - 47*15m, B15]`, canonical `V2_REFERENCE_EXCHANGE` only.
  2. `reader.fetch_v2_consensus_feature_window(...)` -- the exact
     `RANGE_PROXY_N=14`-bucket consensus window `[B15 - 13*15m, B15]`,
     the same interval `setup_common.range_proxy_pct()` itself expects.
  3. `reader.fetch_v2_instrument(..., as_of=context.T)` -- the single
     canonical-exchange historical metadata version actually in effect at
     `context.T` (V2-H2c), for `protection_buffer()`'s `tick_size`. Never
     the current `exchange_instruments` LKG row -- see `ports.py`'s
     `V2SetupHistoryReader.fetch_v2_instrument` docstring.

Sequential awaits, in that order (no `asyncio.gather` -- deterministic,
easy-to-audit call order, mirroring `aligned_inputs.py`'s own posture, not
a runtime-performance claim). Every one of `storage/v2_setup_readers.py`'s
readers already returns fully detached (`MappingProxyType`/`tuple`) rows,
so this module does not re-freeze anything.

**This module does not decide the setup (§54).** It returns whatever
history physically exists -- even a window that will later turn out
retracement-invalid or incomplete once `detect_trend_pullback()` inspects
it. `V2TrendPullbackInputs` is trusted-shape from a real reader by
construction, but `detect_trend_pullback()` still independently
re-validates every row's identity/shape (see `trend_pullback.py`'s
docstring) -- this loader never pre-filters or interprets rows itself,
exactly like `aligned_inputs.py` never decides 4h regime/1h bias.

**Layering (§35/§56).** Depends only on `ports.V2SetupHistoryReader` (a
structural `Protocol` -- never imports `storage.db.Database` or
`storage.v2_setup_readers` directly, so a minimal test double never needs
to import `storage/` at all), `context_snapshot.V2ContextSnapshot`,
`alignment.selected_bucket`, `aligned_inputs.V2_REFERENCE_EXCHANGE`, and
this package's own `trend_pullback.py` (`LOOKBACK_15M`,
`V2TrendPullbackInputs`, `V2TrendPullbackError` -- the last one only for
this module's own cheap non-`V2ContextSnapshot` `context` boundary check,
never for re-validating detector semantics). If `reader` itself
raises (a real/fake reader's own domain error, e.g.
`V2SetupReaderError`), this module never swallows it into `None` --
propagated unchanged, exactly like `aligned_inputs.py` never wraps a
reader's own raised exception.

Pure of side effects beyond the three reads above: no wall clock (no
`datetime.now()`/`utcnow()`/`time.time()`), no writes, no config loading,
no `random`/`uuid`. `context.T` is the only logical time input.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from analytics.forecasting_v2.aligned_inputs import V2_REFERENCE_EXCHANGE
from analytics.forecasting_v2.alignment import TIMEFRAME_MINUTES, selected_bucket
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot
from analytics.forecasting_v2.ports import V2SetupHistoryReader
from analytics.forecasting_v2.setup_common import RANGE_PROXY_N
from analytics.forecasting_v2.trend_pullback import (
    LOOKBACK_15M, V2TrendPullbackError, V2TrendPullbackInputs,
)

__all__ = ["load_trend_pullback_inputs"]

_FIFTEEN_MIN = timedelta(minutes=TIMEFRAME_MINUTES["15m"])


async def load_trend_pullback_inputs(
    reader: V2SetupHistoryReader, *, context: V2ContextSnapshot,
) -> Optional[V2TrendPullbackInputs]:
    """Assemble the exact historical rows `detect_trend_pullback()` needs
    for `context.T`, reading through `reader` (a `V2SetupHistoryReader`)
    only. Returns `None` WITHOUT issuing any read at all if `context.T` is
    not a legal 15m formation boundary (see module docstring); otherwise
    always returns a `V2TrendPullbackInputs` (never `None` once storage is
    actually consulted -- an empty/incomplete/gate-failed history is still
    a valid, fully-populated `V2TrendPullbackInputs`; `detect_trend_
    pullback()` alone decides whether that history is usable).

    Never reads a clock, environment, config file, or generates a
    random/uuid value. Propagates any exception `reader` itself raises,
    unchanged.

    Raises `V2TrendPullbackError` for a non-`V2ContextSnapshot` `context`
    (cheap public-boundary hardening, checked before `context.T` is ever
    accessed) -- this is the only validation this module performs; it
    never re-validates detector semantics (that remains `detect_trend_
    pullback()`'s own job)."""
    if not isinstance(context, V2ContextSnapshot):
        raise V2TrendPullbackError(
            f"context must be a V2ContextSnapshot, got {type(context).__name__}")

    B15 = selected_bucket("15m", context.T)
    if B15 + _FIFTEEN_MIN != context.T:
        return None  # not a 15m formation boundary -- zero storage reads

    reference_rows = await reader.fetch_v2_reference_feature_window(
        exchange=V2_REFERENCE_EXCHANGE, symbol=context.symbol, market_type=context.market_type,
        timeframe="15m", bucket_start=B15 - (LOOKBACK_15M - 1) * _FIFTEEN_MIN, bucket_end=B15,
        calculation_version=context.calculation_version)

    range_proxy_rows = await reader.fetch_v2_consensus_feature_window(
        symbol=context.symbol, market_type=context.market_type, timeframe="15m",
        bucket_start=B15 - (RANGE_PROXY_N - 1) * _FIFTEEN_MIN, bucket_end=B15,
        calculation_version=context.calculation_version)

    instrument = await reader.fetch_v2_instrument(
        exchange=V2_REFERENCE_EXCHANGE, symbol=context.symbol, market_type=context.market_type,
        as_of=context.T)

    return V2TrendPullbackInputs(
        context=context,
        reference_15m_rows=tuple(reference_rows),
        range_proxy_15m_rows=tuple(range_proxy_rows),
        instrument=instrument,
    )
