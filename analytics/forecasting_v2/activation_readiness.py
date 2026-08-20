"""
V2 activation readiness (V2-H2a; `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`
§3.3b).

Fail-closed predicate: whether one `calculation_version` has enough
materialized historical percentile prerequisites to be eligible for V2
decision processing at one decision boundary `T`. §3.3b requires this be
checked "per §4-§7's own frozen percentile-window/lookback requirements" --
this module REUSES those already-frozen per-family selectors (never
re-derives new ones) and REUSES the already-frozen `MIN_PCTL_TIER`
confidence floor (`context_evidence.py`) as the exact "sufficiently
materialized" bar, rather than inventing a new threshold.

Why `confidence_tier` alone is the right signal (not a separately-invented
coverage-ratio/day-count check): `percentile_engine`'s `confidence_tier`
already IS the materialization signal -- `MIN_PCTL_TIER`'s own frozen
definition (§4.1) is "the loosest confidence-tier floor that still excludes
brand-new, single-digit-sample distributions". A percentile snapshot whose
`confidence_tier` has reached `MIN_PCTL_TIER` has, by construction, already
accumulated the sample history its own percentile-window requires. This
module's readiness check is therefore exactly the question "if a live
detector ran against this `calculation_version` right now at `T`, would it
see real evidence (not a missing-data short-circuit) for every mandatory
family" -- no new tunable parameter, no new rules-manifest surface.

Scope, deliberately narrow: covers exactly the MANDATORY (hard-gated, never
optional/veto-only) percentile prerequisites of the currently-implemented
Stage 4/5 surface:
  - `regime_4h`'s STEP 1 hard gate: price AND compression evidence (both
    required -- `_is_missing_data()` for either forces `INSUFFICIENT_DATA`
    before OI is ever consulted);
  - `bias_1h`'s single price evidence input;
  - `compression_breakout`'s compression evidence input
    (`compression_score()`, the only percentile read that family makes).
Deliberately EXCLUDES:
  - `regime_4h`'s OI veto -- confirmed by direct inspection (regime_4h.py)
    to be an optional, symmetric MODULATING veto, never consulted unless a
    price+agreement candidate already exists, and never forcing
    `INSUFFICIENT_DATA` on its own absence. Gating activation on an input
    that a live decision does not itself require would make readiness
    STRICTER than the decision logic it exists to unblock -- wrong in the
    other direction from a silent fallback.
  - `trend_pullback` and `confirmed_breakout` -- confirmed by direct
    inspection to have NO `percentile_snapshots`/`find_consensus_percentile`
    dependency at all (neither family reads percentile evidence; both key
    off raw/reference price structure instead).

This module answers ONLY "is `calculation_version` X ready right now for
`symbol`/`market_type` at `T`" -- it does NOT implement DRAIN-BEFORE-ACTIVATE's
version-SWITCH state machine (§3.1, V2-H2b left open), and a NOT_READY
result here says nothing about what a caller should do about it (keep
draining, refuse to switch, alert) -- that decision belongs to whatever
future orchestration layer consumes this result.

Async because it must read `percentile_snapshots` via the storage layer --
depends only on the existing `V2SetupHistoryReader` port
(`fetch_v2_consensus_percentile_window`, already merged and already
fail-closed on identity/duplicates/ordering), never a new reader or new SQL.
A reader's own domain error (corrupted/inconsistent row) is NEVER downgraded
to NOT_READY here -- it propagates unchanged, so genuine corruption is never
silently confused with legitimate absence (missingness and corruption stay
distinct, matching every other V2-v0 module's posture).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib import import_module
from typing import Any, Optional, Sequence

from analytics.forecasting_v2.alignment import TIMEFRAME_MINUTES
from analytics.forecasting_v2.context_evidence import MIN_PCTL_TIER
from analytics.forecasting_v2.ports import V2SetupHistoryReader
from analytics.percentile_engine.models import CONFIDENCE_TIERS

# `importlib.import_module()` (never `import pkg.mod as alias`) -- exactly
# `rules_manifest.py`'s own convention, for exactly the same reason: several
# of these modules' PUBLIC FUNCTIONS are re-exported at package level under
# the same bare name as their module (see `rules_manifest.py`'s module
# docstring); `import_module()` returns `sys.modules[name]` directly,
# immune to that shadowing.
_regime_4h = import_module("analytics.forecasting_v2.regime_4h")
_bias_1h = import_module("analytics.forecasting_v2.bias_1h")
_compression_breakout = import_module("analytics.forecasting_v2.compression_breakout")

__all__ = [
    "V2ActivationReadinessError",
    "V2RequiredPercentileCoverage",
    "MANDATORY_PERCENTILE_COVERAGE",
    "V2CoverageStatus",
    "V2ActivationReadinessResult",
    "check_activation_readiness",
]


class V2ActivationReadinessError(ValueError):
    """Malformed readiness-check input (bad symbol/market_type/
    calculation_version/decision_boundary/requirements). Never raised for
    legitimately missing/immature history -- that is a NOT_READY result,
    not an error. A reader's own domain error for genuinely INCONSISTENT
    row data is not wrapped here -- it propagates as the reader's own
    exception type unchanged."""


@dataclass(frozen=True)
class V2RequiredPercentileCoverage:
    """One mandatory `(metric, timeframe, percentile_window)` percentile
    prerequisite, plus a `source` label identifying which family/gate it
    comes from (diagnostics only -- never consulted by the readiness
    check itself)."""
    source: str
    metric: str
    timeframe: str
    percentile_window: str

    def __post_init__(self) -> None:
        for name in ("source", "metric", "timeframe", "percentile_window"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise V2ActivationReadinessError(f"{name} must be a non-empty string")
        if self.timeframe not in TIMEFRAME_MINUTES:
            raise V2ActivationReadinessError(
                f"timeframe {self.timeframe!r} is not a recognized V2 timeframe "
                f"(expected one of {tuple(TIMEFRAME_MINUTES)})")


# Explicit, reviewable list of every MANDATORY percentile prerequisite across
# the currently-implemented Stage 4/5 surface -- see module docstring for
# exactly what is/isn't included and why. Every `metric`/`timeframe`/
# `percentile_window` value is sourced directly from each family's own
# frozen module constant (never a re-declared literal string), matching
# `rules_manifest.py`'s "explicit allow-list, never introspection"
# convention for the analogous problem on the V2-rules side.
MANDATORY_PERCENTILE_COVERAGE: "tuple[V2RequiredPercentileCoverage, ...]" = (
    V2RequiredPercentileCoverage(
        source="regime_4h.price", metric=_regime_4h._PRICE_METRIC,
        timeframe=_regime_4h._REGIME_TIMEFRAME,
        percentile_window=_regime_4h._REGIME_PERCENTILE_WINDOW),
    V2RequiredPercentileCoverage(
        source="regime_4h.compression", metric=_regime_4h._COMPRESSION_METRIC,
        timeframe=_regime_4h._REGIME_TIMEFRAME,
        percentile_window=_regime_4h._REGIME_PERCENTILE_WINDOW),
    V2RequiredPercentileCoverage(
        source="bias_1h.price", metric=_bias_1h._PRICE_METRIC,
        timeframe=_bias_1h._BIAS_TIMEFRAME,
        percentile_window=_bias_1h._BIAS_PERCENTILE_WINDOW),
    V2RequiredPercentileCoverage(
        source="compression_breakout.compression",
        metric=_compression_breakout._COMPRESSION_METRIC,
        # compression_breakout.py itself has no named timeframe constant
        # (unlike _REGIME_TIMEFRAME/_BIAS_TIMEFRAME) -- "15m" is the frozen
        # timeframe its own percentile read is keyed by
        # (compression_breakout_inputs.py's `read_v2_consensus_percentile_
        # window(..., timeframe="15m", ...)` call, unchanged since #41).
        timeframe="15m",
        percentile_window=_compression_breakout.COMPRESSION_PERCENTILE_WINDOW),
)

_MIN_TIER_INDEX = CONFIDENCE_TIERS.index(MIN_PCTL_TIER)


def _tier_usable(tier: Any) -> bool:
    """Same comparison `context_evidence.py`'s private
    `_percentile_tier_usable()` makes, re-implemented locally rather than
    imported -- `_percentile_tier_usable` is not exported
    (`context_evidence.__all__` omits it) and every other V2-v0 module
    that needs this exact comparison already keeps its own local copy
    rather than reaching into another module's private surface (see
    `decision_provenance.py`'s `_validate_decision_boundary` docstring for
    the same convention). Compares by canonical `CONFIDENCE_TIERS` index,
    never alphabetically. An unknown tier string is corrupted input, not a
    legitimately low-maturity one."""
    if tier not in CONFIDENCE_TIERS:
        raise V2ActivationReadinessError(
            f"unknown confidence_tier {tier!r} (expected one of {CONFIDENCE_TIERS})")
    return CONFIDENCE_TIERS.index(tier) >= _MIN_TIER_INDEX


@dataclass(frozen=True)
class V2CoverageStatus:
    """Per-requirement diagnostic: whether ONE mandatory percentile
    prerequisite has a usable (present, non-missing,
    at-or-above-`MIN_PCTL_TIER`) latest snapshot at-or-before `T`."""
    requirement: V2RequiredPercentileCoverage
    ready: bool
    reason: str
    latest_bucket_ts: Optional[datetime]


@dataclass(frozen=True)
class V2ActivationReadinessResult:
    """Fail-closed readiness verdict for one `(calculation_version,
    decision_boundary)` pair: `ready` is `True` iff EVERY status in
    `statuses` is itself ready -- never a partial/majority pass."""
    calculation_version: str
    decision_boundary: datetime
    ready: bool
    statuses: "tuple[V2CoverageStatus, ...]"


def _validate_decision_boundary(value: Any) -> datetime:
    if type(value) is not datetime:
        raise V2ActivationReadinessError(
            f"decision_boundary must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2ActivationReadinessError("decision_boundary must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise V2ActivationReadinessError(
            f"decision_boundary must be UTC (offset 0), got {value.utcoffset()}")
    if value.second != 0 or value.microsecond != 0:
        raise V2ActivationReadinessError(
            "decision_boundary must be a whole minute (no seconds/microseconds)")
    return value


async def check_activation_readiness(
    reader: V2SetupHistoryReader, *, symbol: str, market_type: str,
    calculation_version: str, decision_boundary: datetime,
    requirements: Sequence[V2RequiredPercentileCoverage] = MANDATORY_PERCENTILE_COVERAGE,
) -> V2ActivationReadinessResult:
    """Fail-closed: the returned result's `ready` is `True` iff EVERY
    requirement in `requirements` has a usable latest `percentile_snapshots`
    row at-or-before `decision_boundary` under `calculation_version`. A
    missing row, a `None` `value`/`percentile_rank`, or a below-floor
    `confidence_tier` for even ONE requirement makes the WHOLE result
    NOT_READY -- never a silent partial pass, never a fallback to an older
    `calculation_version` or to stale data (this function never queries any
    version/window other than exactly the ones the caller supplied).

    Per-requirement lookback window is exactly one bucket-width of that
    requirement's own `timeframe` ending at `decision_boundary`
    (`[decision_boundary - timeframe_width, decision_boundary]`) -- wide
    enough to find the most recently expected snapshot for that timeframe's
    own cadence, deliberately NOT widened further: a version whose most
    recent expected snapshot for a mandatory family is simply absent is
    correctly NOT_READY, not silently satisfied by an older, stale row from
    further back.

    `calculation_version` is passed straight through to `reader` (never
    derived here, never defaulted) -- a caller checking readiness for a
    version OTHER than the one currently active can never accidentally
    query the wrong window."""
    if not isinstance(symbol, str) or not symbol.strip():
        raise V2ActivationReadinessError("symbol must be a non-empty string")
    if not isinstance(market_type, str) or not market_type.strip():
        raise V2ActivationReadinessError("market_type must be a non-empty string")
    if not isinstance(calculation_version, str) or not calculation_version.strip():
        raise V2ActivationReadinessError("calculation_version must be a non-empty string")
    _validate_decision_boundary(decision_boundary)
    if not requirements:
        raise V2ActivationReadinessError("requirements must be non-empty")
    for req in requirements:
        if not isinstance(req, V2RequiredPercentileCoverage):
            raise V2ActivationReadinessError(
                f"every requirement must be a V2RequiredPercentileCoverage, "
                f"got {type(req).__name__}")

    statuses: "list[V2CoverageStatus]" = []
    for req in requirements:
        window = timedelta(minutes=TIMEFRAME_MINUTES[req.timeframe])
        window_start = decision_boundary - window
        rows = await reader.fetch_v2_consensus_percentile_window(
            symbol=symbol, market_type=market_type, metric=req.metric,
            timeframe=req.timeframe, percentile_window=req.percentile_window,
            bucket_start=window_start, bucket_end=decision_boundary,
            calculation_version=calculation_version)
        if not rows:
            statuses.append(V2CoverageStatus(
                requirement=req, ready=False,
                reason="no percentile_snapshots row in the expected lookback window",
                latest_bucket_ts=None))
            continue
        # The reader's own contract guarantees ascending, non-descending
        # `bucket_ts` order -- the LAST row is the latest.
        latest = rows[-1]
        latest_bucket_ts = latest.get("bucket_ts")
        if latest.get("value") is None or latest.get("percentile_rank") is None:
            statuses.append(V2CoverageStatus(
                requirement=req, ready=False,
                reason="latest percentile_snapshots row is missing value/percentile_rank",
                latest_bucket_ts=latest_bucket_ts))
            continue
        if not _tier_usable(latest.get("confidence_tier")):
            statuses.append(V2CoverageStatus(
                requirement=req, ready=False,
                reason=(
                    f"latest percentile_snapshots row confidence_tier "
                    f"{latest.get('confidence_tier')!r} is below MIN_PCTL_TIER "
                    f"{MIN_PCTL_TIER!r}"),
                latest_bucket_ts=latest_bucket_ts))
            continue
        statuses.append(V2CoverageStatus(
            requirement=req, ready=True, reason="ready", latest_bucket_ts=latest_bucket_ts))

    ready = all(status.ready for status in statuses)
    return V2ActivationReadinessResult(
        calculation_version=calculation_version, decision_boundary=decision_boundary,
        ready=ready, statuses=tuple(statuses))
