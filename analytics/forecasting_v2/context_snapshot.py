"""
V2 final combined context snapshot (Stage 4 — Context Engines, PR 3 of
~3, FINAL planned Stage 4 PR, docs/FORECASTING_ROADMAP.md §I stage 4).

PR 2 (`regime_4h.py`, merged) answers "what is the established 4h market
regime?" This PR's other module, `bias_1h.py`, answers "which way does
the nearer-term 1h tape lean, if at all?" This module combines both
already-computed facts, for ONE explicit decision boundary, into a single
immutable result:

    build_v2_context_snapshot(aligned: V2AlignedInputs) -> V2ContextSnapshot

This is **not** a detector. It makes no LONG/SHORT, trade, setup, or
compatibility decision of any kind — it only preserves, side by side, the
two independent Stage 4 facts a future Stage 5 setup detector will read
differently depending on which family it is.

**Why the public builder accepts exactly ONE `V2AlignedInputs` (load-
bearing).** Stage 3's entire purpose is that every timeframe in a
`V2AlignedInputs` snapshot is selected from ONE explicit decision boundary
`T` (`aligned_inputs.py`'s own framing). A public API shaped as
`build_context(regime_inputs, bias_inputs)` would let a caller
accidentally pair a 4h context computed from one `T` with a 1h context
computed from a DIFFERENT `T` — exactly the class of bug Stage 3 exists to
prevent. This module never accepts two independent input objects; it
always derives both `classify_4h_regime`/`classify_1h_bias` inputs from
the SAME `aligned.by_timeframe`.

**Decision-boundary identity (load-bearing, fails closed against
mixing).** `V2ContextSnapshot.__post_init__` re-validates `T` as a legal
V2 decision boundary via `selected_bucket("5m", T)` (discarding the
result, exactly like `V2AlignedInputRequest` already does — never a
second grid-alignment implementation), then computes
`selected_bucket("4h", T)`/`selected_bucket("1h", T)` and requires
`regime_4h.bucket_ts`/`bias_1h.bucket_ts` to match EXACTLY. This applies
whether the snapshot is built through `build_v2_context_snapshot` (where
it is always true by construction) or hand-constructed directly (tests, a
future replay harness) — a `V2RegimeResult`/`V2BiasResult` computed for a
DIFFERENT `T` can never be silently paired into a snapshot that claims a
different one.

**Legitimate `INSUFFICIENT_DATA`/`"UNAVAILABLE"` results are VALID context
facts, not failures (load-bearing).** `V2ContextSnapshotError` is reserved
for malformed input/containers, an impossible mixed-decision-boundary
pairing, and wrapped classifier errors — never for a legitimately-computed
`regime_4h.regime == INSUFFICIENT_DATA` or `bias_1h.bias == "UNAVAILABLE"`.
The combined snapshot is still constructed and returned in both cases;
Stage 5 later decides which detector families can proceed from a
partially-unavailable context, not this module.

**No overall/combined direction (§4.4, load-bearing).** This module does
NOT compute `overall_direction`/`trade_direction`/`setup_allowed`/
`trade_allowed`/a compatibility score, and `V2ContextSnapshot` carries no
such field. §4.4 keeps regime and bias deliberately independent — they
read different evidence compositions (different windows, different
thresholds, and bias never reads OI/compression at all) precisely so
different Stage 5 detector families can consume them differently
(`TREND_PULLBACK` will require strict agreement; the breakout families use
a different compatibility rule, `§7.0b`). Collapsing them into one vote
here would destroy information a later stage needs. `directional_context_
gate` (§7.0b) is Stage 5 setup-detector logic and is explicitly NOT
implemented anywhere in this module.

**Source identity hardening (load-bearing, pre-merge amendment).** A real
`load_v2_aligned_inputs()` snapshot already guarantees every nested
consensus/percentile row belongs to the SAME logical identity as its own
top-level `symbol`/`market_type`/`calculation_version`/
`feature_schema_version` (`aligned_inputs.py`'s own `_check_provenance`/
`_validate_consensus_row`/`_validate_percentile_rows`). But
`V2AlignedInputs` is a plain frozen dataclass with no `__post_init__` of
its own enforcing that — and this module explicitly supports a
hand-constructed one too (tests, a future replay harness). Without an
extra check here, a hand-built `V2AlignedInputs` could carry a top-level
identity (e.g. `symbol="BTCUSDT"`) while its nested 4h/1h consensus/
percentile rows actually belong to a DIFFERENT identity (a different
symbol, market type, `calculation_version`, or `feature_schema_version`)
— `classify_4h_regime`/`classify_1h_bias` only ever see the narrower
`V2TimeframeInputs` and have no way to compare it against the top-level
aligned identity, so this final boundary is the only place left that
still can. `build_v2_context_snapshot` therefore calls
`_validate_context_input_identity` for `"4h"`/`"1h"` BEFORE
classification: it re-derives `selected_bucket(timeframe, aligned.T)` and
requires `inputs.bucket_ts` to match it; requires a PRESENT
`inputs.consensus` to be a `Mapping` whose `symbol`/`market_type`/
`timeframe`/`bucket_ts`/`calculation_version`/`feature_schema_version`
all equal the aligned top-level identity (`inputs.consensus is None`
remains legitimate missingness, never an error); and requires EVERY row
in `inputs.percentiles` to be a `Mapping` with `scope == "consensus"`,
`exchange == ""`, and the same `symbol`/`market_type`/`timeframe`/
`bucket_ts`/`calculation_version`/`feature_schema_version` — an empty
`inputs.percentiles` tuple remains legitimate and simply yields the
frozen `INSUFFICIENT_DATA`/`"UNAVAILABLE"` result downstream. This
checks ONLY identity fields, never percentile-rank math, confidence-tier
ordering, sample windows, or the metric allow-list — those remain PR 1's
(`context_evidence.py`'s) own responsibility, not re-implemented here.
Health/`reference_feature`/`reference_klines`/`reference_extrema`/5m/15m
are never inspected — not consumed by Stage 4 context classification at
all, and out of scope for this identity check too.

`V2ContextSnapshot.__post_init__`'s own decision-boundary check (see
above) is a SECOND, independent defensive layer, not a replacement for
this one: the builder validates SOURCE inputs before computing; the
result validates the resulting `regime_4h`/`bias_1h` bucket pairing
after computing (or on direct construction). A hand-constructed
`V2ContextSnapshot` built directly (bypassing `build_v2_context_snapshot`
entirely) is validated ONLY by `__post_init__` — it can prove the
`T`/bucket pairing the snapshot's own fields actually carry, but it
cannot prove the underlying evidence's provenance, because
`V2RegimeResult`/`V2BiasResult` (frozen in PR 2/this PR, never modified
here) carry no `symbol`/`calculation_version`/`feature_schema_version`
fields of their own to check against.

**Pure module.** No DB, no `asyncpg`, no network, no filesystem, no
clock, no config loading, no `random`/`uuid`/`subprocess`. Consumes only
the already-immutable Stage 3 `V2AlignedInputs` and this PR's own
`classify_4h_regime`/`classify_1h_bias` — no `T`/reader/wall-clock
parameter of its own (the `T` it validates comes from `aligned.T`, already
fixed by Stage 3). Every public function is synchronous. Only `aligned.
by_timeframe["4h"]`/`["1h"]` are ever dereferenced — 5m/15m are never
inspected here; Stage 4 context is a 4h/1h concept only (§4.1/§4.3)."""
from __future__ import annotations

from collections.abc import Mapping as _AbcMapping
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from analytics.forecasting_v2._validation import (
    validate_calculation_version, validate_feature_schema_version,
    validate_market_type, validate_symbol,
)
from analytics.forecasting_v2.aligned_inputs import V2AlignedInputs, V2TimeframeInputs
from analytics.forecasting_v2.alignment import V2AlignmentError, selected_bucket
from analytics.forecasting_v2.bias_1h import V2BiasError, V2BiasResult, classify_1h_bias
from analytics.forecasting_v2.regime_4h import V2RegimeError, V2RegimeResult, classify_4h_regime

__all__ = [
    "V2ContextSnapshotError",
    "V2ContextSnapshot",
    "build_v2_context_snapshot",
]


class V2ContextSnapshotError(ValueError):
    """Malformed top-level input/container (a non-`V2AlignedInputs`
    argument, a non-`Mapping` `by_timeframe`, a missing `"4h"`/`"1h"`
    key, a wrong value type or mismatched `.timeframe` under either key),
    a source-identity mismatch between `aligned`'s own top-level
    `symbol`/`market_type`/`calculation_version`/`feature_schema_version`
    and a PRESENT `"4h"`/`"1h"` consensus row or any PRESENT percentile
    row (`_validate_context_input_identity`; see module docstring's
    "Source identity hardening" section), an impossible
    mixed-decision-boundary pairing (a `regime_4h`/`bias_1h` whose own
    `bucket_ts` does not match `selected_bucket("4h"|"1h", T)`), a
    malformed top-level identity field (`T`/`symbol`/`market_type`/
    `calculation_version`/`feature_schema_version`), or a `V2RegimeError`/
    `V2BiasError` raised by the underlying classifiers for genuinely
    corrupted (not missing/unavailable) evidence — always re-raised as
    this type, exception-chained, never swallowed. Never raised for a
    legitimately-computed `INSUFFICIENT_DATA` 4h regime or `"UNAVAILABLE"`
    1h bias, a `None` `inputs.consensus`, or an empty `inputs.percentiles`
    — those are all VALID/legitimate context inputs/results the snapshot
    still carries; see module docstring."""


def _require_timeframe_inputs(by_timeframe: Mapping, timeframe: str) -> V2TimeframeInputs:
    """`aligned.by_timeframe[timeframe]`, defensively re-checked so a
    malformed container never leaks a bare `KeyError`/`TypeError` out of
    this module — always `V2ContextSnapshotError` instead."""
    if timeframe not in by_timeframe:
        raise V2ContextSnapshotError(
            f"aligned.by_timeframe is missing the required {timeframe!r} entry")
    value = by_timeframe[timeframe]
    if not isinstance(value, V2TimeframeInputs):
        raise V2ContextSnapshotError(
            f"aligned.by_timeframe[{timeframe!r}] must be a V2TimeframeInputs, "
            f"got {type(value).__name__}")
    if value.timeframe != timeframe:
        raise V2ContextSnapshotError(
            f"aligned.by_timeframe[{timeframe!r}].timeframe does not match its own key "
            f"(got {value.timeframe!r})")
    return value


def _validate_context_input_identity(
    aligned: V2AlignedInputs, inputs: V2TimeframeInputs, timeframe: str,
) -> None:
    """Ties `inputs` (already known to be a `V2TimeframeInputs` whose own
    `.timeframe` matches `timeframe` — `_require_timeframe_inputs`'s job)
    back to `aligned`'s own top-level identity, BEFORE classification (see
    module docstring's "Source identity hardening" section for the full
    rationale and the concrete counter-example this closes). Checks ONLY
    the identity fields the context evidence this module actually
    consumes depends on — never percentile-rank math, confidence-tier
    ordering, sample windows, or the metric allow-list (PR 1's own
    responsibility)."""
    try:
        expected_bucket = selected_bucket(timeframe, aligned.T)
    except V2AlignmentError as exc:
        raise V2ContextSnapshotError(
            f"aligned.T must be a legal V2 decision boundary: {exc}") from exc
    if inputs.bucket_ts != expected_bucket:
        raise V2ContextSnapshotError(
            f"{timeframe} inputs.bucket_ts does not match "
            f"selected_bucket({timeframe!r}, aligned.T) — expected {expected_bucket!r}, "
            f"got {inputs.bucket_ts!r}")

    consensus = inputs.consensus
    if consensus is not None:
        if not isinstance(consensus, _AbcMapping):
            raise V2ContextSnapshotError(
                f"{timeframe} inputs.consensus must be a Mapping, got "
                f"{type(consensus).__name__}")
        if consensus.get("symbol") != aligned.symbol:
            raise V2ContextSnapshotError(
                f"{timeframe} consensus symbol does not match the aligned identity — "
                f"expected {aligned.symbol!r}, got {consensus.get('symbol')!r}")
        if consensus.get("market_type") != aligned.market_type:
            raise V2ContextSnapshotError(
                f"{timeframe} consensus market_type does not match the aligned identity — "
                f"expected {aligned.market_type!r}, got {consensus.get('market_type')!r}")
        if consensus.get("timeframe") != timeframe:
            raise V2ContextSnapshotError(
                f"{timeframe} consensus timeframe does not match the aligned identity — "
                f"expected {timeframe!r}, got {consensus.get('timeframe')!r}")
        if consensus.get("bucket_ts") != inputs.bucket_ts:
            raise V2ContextSnapshotError(
                f"{timeframe} consensus bucket_ts does not match inputs.bucket_ts — "
                f"expected {inputs.bucket_ts!r}, got {consensus.get('bucket_ts')!r}")
        if consensus.get("calculation_version") != aligned.calculation_version:
            raise V2ContextSnapshotError(
                f"{timeframe} consensus calculation_version does not match the aligned "
                f"identity — expected {aligned.calculation_version!r}, "
                f"got {consensus.get('calculation_version')!r}")
        if consensus.get("feature_schema_version") != aligned.feature_schema_version:
            raise V2ContextSnapshotError(
                f"{timeframe} consensus feature_schema_version does not match the aligned "
                f"identity — expected {aligned.feature_schema_version!r}, "
                f"got {consensus.get('feature_schema_version')!r}")

    for row in inputs.percentiles:
        if not isinstance(row, _AbcMapping):
            raise V2ContextSnapshotError(
                f"{timeframe} inputs.percentiles must contain only Mapping rows, got "
                f"{type(row).__name__}: {row!r}")
        if row.get("scope") != "consensus":
            raise V2ContextSnapshotError(
                f"{timeframe} percentile row scope must be 'consensus', "
                f"got {row.get('scope')!r}")
        if row.get("exchange") != "":
            raise V2ContextSnapshotError(
                f"{timeframe} percentile row exchange must be '' for consensus-scope rows, "
                f"got {row.get('exchange')!r}")
        if row.get("symbol") != aligned.symbol:
            raise V2ContextSnapshotError(
                f"{timeframe} percentile row symbol does not match the aligned identity — "
                f"expected {aligned.symbol!r}, got {row.get('symbol')!r}")
        if row.get("market_type") != aligned.market_type:
            raise V2ContextSnapshotError(
                f"{timeframe} percentile row market_type does not match the aligned "
                f"identity — expected {aligned.market_type!r}, got {row.get('market_type')!r}")
        if row.get("timeframe") != timeframe:
            raise V2ContextSnapshotError(
                f"{timeframe} percentile row timeframe does not match the aligned identity — "
                f"expected {timeframe!r}, got {row.get('timeframe')!r}")
        if row.get("bucket_ts") != inputs.bucket_ts:
            raise V2ContextSnapshotError(
                f"{timeframe} percentile row bucket_ts does not match inputs.bucket_ts — "
                f"expected {inputs.bucket_ts!r}, got {row.get('bucket_ts')!r}")
        if row.get("calculation_version") != aligned.calculation_version:
            raise V2ContextSnapshotError(
                f"{timeframe} percentile row calculation_version does not match the "
                f"aligned identity — expected {aligned.calculation_version!r}, "
                f"got {row.get('calculation_version')!r}")
        if row.get("feature_schema_version") != aligned.feature_schema_version:
            raise V2ContextSnapshotError(
                f"{timeframe} percentile row feature_schema_version does not match the "
                f"aligned identity — expected {aligned.feature_schema_version!r}, "
                f"got {row.get('feature_schema_version')!r}")


@dataclass(frozen=True)
class V2ContextSnapshot:
    """The complete, immutable Stage 4 context for one V2 decision
    boundary `T`: the already-computed 4h regime and 1h bias, preserved
    SEPARATELY (see module docstring — there is deliberately no combined/
    overall direction field). Self-validates every identity field and the
    decision-boundary pairing between `regime_4h`/`bias_1h` and `T` — this
    runs whether the snapshot is built via `build_v2_context_snapshot` or
    hand-constructed directly."""
    T: datetime
    symbol: str
    market_type: str
    calculation_version: str
    feature_schema_version: int
    regime_4h: V2RegimeResult
    bias_1h: V2BiasResult

    def __post_init__(self) -> None:
        try:
            selected_bucket("5m", self.T)
        except V2AlignmentError as exc:
            raise V2ContextSnapshotError(
                f"T must be a legal V2 decision boundary: {exc}") from exc

        validate_symbol(self.symbol, V2ContextSnapshotError)
        validate_market_type(self.market_type, V2ContextSnapshotError)
        validate_calculation_version(self.calculation_version, V2ContextSnapshotError)
        validate_feature_schema_version(self.feature_schema_version, V2ContextSnapshotError)

        if not isinstance(self.regime_4h, V2RegimeResult):
            raise V2ContextSnapshotError(
                f"regime_4h must be a V2RegimeResult, got {type(self.regime_4h).__name__}")
        if not isinstance(self.bias_1h, V2BiasResult):
            raise V2ContextSnapshotError(
                f"bias_1h must be a V2BiasResult, got {type(self.bias_1h).__name__}")

        # Decision-boundary anti-mixing defense (load-bearing — see module
        # docstring): a regime_4h/bias_1h computed for a DIFFERENT T can
        # never be silently paired into a snapshot claiming this T.
        expected_4h = selected_bucket("4h", self.T)
        if self.regime_4h.bucket_ts != expected_4h:
            raise V2ContextSnapshotError(
                "regime_4h.bucket_ts does not match selected_bucket('4h', T) — "
                f"expected {expected_4h!r}, got {self.regime_4h.bucket_ts!r}")
        expected_1h = selected_bucket("1h", self.T)
        if self.bias_1h.bucket_ts != expected_1h:
            raise V2ContextSnapshotError(
                "bias_1h.bucket_ts does not match selected_bucket('1h', T) — "
                f"expected {expected_1h!r}, got {self.bias_1h.bucket_ts!r}")


def build_v2_context_snapshot(aligned: V2AlignedInputs) -> V2ContextSnapshot:
    """The ONE canonical way to combine an already-aligned Stage 3
    `V2AlignedInputs` snapshot into the final Stage 4 `V2ContextSnapshot`
    (see module docstring for why this accepts exactly one such object,
    never two independent `regime_inputs`/`bias_inputs` arguments).

    Deterministic call order: (1) obtain/validate the `"4h"`/`"1h"`
    entries from `aligned.by_timeframe`; (2) tie each to `aligned`'s own
    top-level identity (`_validate_context_input_identity` — see module
    docstring's "Source identity hardening" section); (3)
    `classify_4h_regime`; (4) `classify_1h_bias`; (5) construct the final
    `V2ContextSnapshot` (whose own `__post_init__` re-validates the
    decision-boundary pairing as a second, independent defensive layer).
    Only `"4h"`/`"1h"` are ever read — `"5m"`/`"15m"` are never inspected
    here.

    Raises `V2ContextSnapshotError` for: a non-`V2AlignedInputs` `aligned`;
    a non-`Mapping` `aligned.by_timeframe`; a missing `"4h"`/`"1h"` key; a
    wrong value type or mismatched `.timeframe` under either key; a
    `"4h"`/`"1h"` `inputs.bucket_ts` that does not match
    `selected_bucket(timeframe, aligned.T)`; a PRESENT `inputs.consensus`
    that is not a `Mapping`, or whose `symbol`/`market_type`/`timeframe`/
    `bucket_ts`/`calculation_version`/`feature_schema_version` do not
    match `aligned`'s own; any PRESENT `inputs.percentiles` row that is
    not a `Mapping`, or whose `scope`/`exchange`/`symbol`/`market_type`/
    `timeframe`/`bucket_ts`/`calculation_version`/`feature_schema_version`
    do not match; or a `V2RegimeError`/`V2BiasError` from the underlying
    classifiers for genuinely corrupted (not missing/unavailable)
    evidence — re-raised here, exception-chained. A legitimately-computed
    `INSUFFICIENT_DATA` 4h regime, `"UNAVAILABLE"` 1h bias, a `None`
    `inputs.consensus`, or an empty `inputs.percentiles` is NOT an error —
    the snapshot is still built and returned; see module docstring."""
    if not isinstance(aligned, V2AlignedInputs):
        raise V2ContextSnapshotError(
            f"aligned must be a V2AlignedInputs, got {type(aligned).__name__}")

    by_timeframe = aligned.by_timeframe
    if not isinstance(by_timeframe, _AbcMapping):
        raise V2ContextSnapshotError(
            f"aligned.by_timeframe must be a Mapping, got {type(by_timeframe).__name__}")

    inputs_4h = _require_timeframe_inputs(by_timeframe, "4h")
    inputs_1h = _require_timeframe_inputs(by_timeframe, "1h")

    _validate_context_input_identity(aligned, inputs_4h, "4h")
    _validate_context_input_identity(aligned, inputs_1h, "1h")

    try:
        regime_result = classify_4h_regime(inputs_4h)
    except V2RegimeError as exc:
        raise V2ContextSnapshotError(f"4h regime classification failed: {exc}") from exc

    try:
        bias_result = classify_1h_bias(inputs_1h)
    except V2BiasError as exc:
        raise V2ContextSnapshotError(f"1h bias classification failed: {exc}") from exc

    return V2ContextSnapshot(
        T=aligned.T, symbol=aligned.symbol, market_type=aligned.market_type,
        calculation_version=aligned.calculation_version,
        feature_schema_version=aligned.feature_schema_version,
        regime_4h=regime_result, bias_1h=bias_result,
    )
