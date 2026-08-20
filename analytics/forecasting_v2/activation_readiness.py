"""
V2 activation readiness (V2-H2a; `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`
§3.3b).

Fail-closed predicate: whether one `calculation_version` has enough
materialized historical percentile prerequisites to be eligible for V2
decision processing at one decision boundary `T`, for one `symbol`/
`market_type` scope. §3.3b requires this be checked "per §4-§7's own frozen
percentile-window/lookback requirements" -- this module REUSES those
already-frozen per-family selectors (never re-derives new ones) and REUSES
the already-frozen `MIN_PCTL_TIER` confidence floor (`context_evidence.py`)
as the exact "sufficiently materialized" bar, rather than inventing a new
threshold.

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

**Exact bucket, not a lookback window (Qodo amendment round 1, finding 1).**
Each mandatory requirement is checked against EXACTLY the fully-closed
bucket the associated detector itself consumes for `T` --
`alignment.selected_bucket(req.timeframe, T)`, the SAME function
`context_snapshot.py`/`compression_breakout_inputs.py`/
`trend_pullback_inputs.py` already derive their own buckets from. A prior
version of this module queried an ad-hoc `[T - timeframe_width, T]` window
instead, which for a non-timeframe-aligned `T` (e.g. `T=12:05`) starts
AFTER the bucket a live detector would actually read (`selected_bucket
("4h", 12:05) == 08:00`, well before `08:05`) -- silently reporting
NOT_READY for perfectly materialized history, or in principle accepting a
newer/unrelated snapshot the detector itself would never consume. Using
`selected_bucket()` directly makes "the bucket readiness inspects" and "the
bucket the detector reads" provably the SAME expression, not two
independently-maintained ones that can drift apart.

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

**Self-validating result (Qodo amendment round 1, findings 3 and 4).**
`V2ActivationReadinessResult` now carries `symbol`/`market_type` (the exact
scope the reads were issued for -- previously discarded, letting
`resolve_decision_view()` compose readiness computed for one scope with
provenance for a DIFFERENT scope whenever `calculation_version`/
`decision_boundary` happened to match) and validates its own `ready ==
all(status.ready for status in statuses)` invariant in `__post_init__` --
every construction path, not just `check_activation_readiness()`'s own
return, is guaranteed internally consistent; there is no way to
hand-construct a forged `ready=True` result with empty or failing statuses.

**Full canonical coverage, never a partial probe (tech-lead amendment
round 2).** §3.3b's activation readiness means ALL mandatory V2 historical
feature/percentile prerequisites are sufficiently materialized -- not
"the ones a caller happened to ask about". `V2ActivationReadinessResult.
__post_init__` therefore also requires `statuses` to cover EXACTLY
`MANDATORY_PERCENTILE_COVERAGE` (no missing requirement, no extra/
noncanonical one, no duplicate) -- a result built from a one-requirement
or three-of-four subset can never be constructed, ready or not. The
public `check_activation_readiness()` no longer accepts a caller-supplied
`requirements` override at all, so there is no public way to weaken
activation readiness by probing a subset and having it silently pass as a
global verdict. Focused/internal evaluation of an arbitrary requirement
subset is still available -- `_evaluate_requirements()`, a private
helper that returns bare `V2CoverageStatus` tuples, never a
`V2ActivationReadinessResult` -- so unit tests can still exercise
per-requirement behavior without being able to manufacture a production
"globally ready" object out of partial evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from importlib import import_module
from typing import Any, Optional, Sequence

from analytics.forecasting_v2.alignment import (
    TIMEFRAME_MINUTES, V2AlignmentError, selected_bucket,
)
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
    calculation_version/decision_boundary/requirements), or a
    self-validation failure on `V2ActivationReadinessResult`/
    `V2CoverageStatus` construction (a forged/inconsistent `ready` flag,
    empty/malformed `statuses`, a duplicate requirement, or `statuses` not
    covering EXACTLY `MANDATORY_PERCENTILE_COVERAGE` -- missing or extra).
    Never raised for legitimately missing/immature history -- that is a
    NOT_READY result, not an error. A reader's own domain error for
    genuinely INCONSISTENT row data is not wrapped here -- it propagates
    as the reader's own exception type unchanged."""


def _validate_decision_boundary(value: Any) -> datetime:
    """A legal V2 5m decision boundary -- delegated to
    `alignment.selected_bucket("5m", value)`, exactly like
    `decision_provenance.py::_validate_decision_boundary` (see that
    function's docstring for the full rationale: this is the single
    canonical source of truth for "is T a legal V2 5m decision boundary",
    and delegating to it means this function never itself calls
    `.utcoffset()` -- any exception `selected_bucket()` raises (the
    expected `V2AlignmentError`, or an unexpected one from a
    malformed/malicious custom `tzinfo`) is translated into
    `V2ActivationReadinessError` exactly once, right here, never leaked
    past this module's boundary as a raw exception)."""
    try:
        selected_bucket("5m", value)
    except V2AlignmentError as exc:
        raise V2ActivationReadinessError(f"decision_boundary: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - malformed/malicious tzinfo, or any
        # other unexpected failure inside the delegated alignment check --
        # never leaked past this module's boundary as a raw exception.
        raise V2ActivationReadinessError(
            f"decision_boundary failed alignment validation: "
            f"{type(exc).__name__}: {exc}") from exc
    return value


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
    rather than reaching into another module's private surface. Compares
    by canonical `CONFIDENCE_TIERS` index, never alphabetically. An
    unknown tier string is corrupted input, not a legitimately
    low-maturity one."""
    if tier not in CONFIDENCE_TIERS:
        raise V2ActivationReadinessError(
            f"unknown confidence_tier {tier!r} (expected one of {CONFIDENCE_TIERS})")
    return CONFIDENCE_TIERS.index(tier) >= _MIN_TIER_INDEX


@dataclass(frozen=True)
class V2CoverageStatus:
    """Per-requirement diagnostic: whether ONE mandatory percentile
    prerequisite has a usable (present, non-missing,
    at-or-above-`MIN_PCTL_TIER`) snapshot at the exact bucket the
    associated detector consumes for `T`. Self-validates its own field
    shape -- a caller hand-constructing a `V2CoverageStatus` cannot slip
    a wrong-typed `requirement`/`ready`/`reason`/`latest_bucket_ts` past
    `V2ActivationReadinessResult.__post_init__`'s `isinstance` check,
    since that check only confirms the TYPE, not the substance; this
    class's own `__post_init__` confirms the substance."""
    requirement: V2RequiredPercentileCoverage
    ready: bool
    reason: str
    latest_bucket_ts: Optional[datetime]

    def __post_init__(self) -> None:
        if not isinstance(self.requirement, V2RequiredPercentileCoverage):
            raise V2ActivationReadinessError(
                f"requirement must be a V2RequiredPercentileCoverage, "
                f"got {type(self.requirement).__name__}")
        if not isinstance(self.ready, bool):
            raise V2ActivationReadinessError(
                f"ready must be a bool, got {type(self.ready).__name__}")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise V2ActivationReadinessError("reason must be a non-empty string")
        if self.latest_bucket_ts is not None and type(self.latest_bucket_ts) is not datetime:
            raise V2ActivationReadinessError(
                f"latest_bucket_ts must be None or a datetime, "
                f"got {type(self.latest_bucket_ts).__name__}")


@dataclass(frozen=True)
class V2ActivationReadinessResult:
    """Fail-closed, self-validating readiness verdict for one `(symbol,
    market_type, calculation_version, decision_boundary)` identity:
    `ready` is `True` iff EVERY status in `statuses` is itself ready --
    never a partial/majority pass, and never independently settable by a
    caller. `symbol`/`market_type` are the exact scope the underlying
    reads were issued for -- carried here so `resolve_decision_view()`
    can refuse to compose readiness computed for one scope with
    provenance for a different one (Qodo amendment round 1, finding 3).

    Constructing an instance with a mismatched `ready` flag, empty/
    malformed `statuses`, a duplicate requirement, or a malformed identity
    field raises `V2ActivationReadinessError` -- there is no way to
    "forge" a ready result by hand-constructing this type; the invariant
    holds for EVERY construction path, not just `check_activation_
    readiness()`'s own return (Qodo amendment round 1, finding 4)."""
    symbol: str
    market_type: str
    calculation_version: str
    decision_boundary: datetime
    ready: bool
    statuses: "tuple[V2CoverageStatus, ...]"

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol.strip():
            raise V2ActivationReadinessError("symbol must be a non-empty string")
        if not isinstance(self.market_type, str) or not self.market_type.strip():
            raise V2ActivationReadinessError("market_type must be a non-empty string")
        if not isinstance(self.calculation_version, str) or not self.calculation_version.strip():
            raise V2ActivationReadinessError("calculation_version must be a non-empty string")
        _validate_decision_boundary(self.decision_boundary)
        if not isinstance(self.ready, bool):
            raise V2ActivationReadinessError(
                f"ready must be a bool, got {type(self.ready).__name__}")
        if not isinstance(self.statuses, tuple) or not self.statuses:
            raise V2ActivationReadinessError("statuses must be a non-empty tuple")
        seen_requirements: set = set()
        for status in self.statuses:
            if not isinstance(status, V2CoverageStatus):
                raise V2ActivationReadinessError(
                    f"every status must be a V2CoverageStatus, got {type(status).__name__}")
            if status.requirement in seen_requirements:
                raise V2ActivationReadinessError(
                    f"duplicate requirement {status.requirement!r} in statuses")
            seen_requirements.add(status.requirement)
        # §3.3b: activation readiness means ALL mandatory prerequisites are
        # materialized -- never "the subset a caller happened to ask
        # about". `statuses` must cover EXACTLY the canonical mandatory
        # set: no missing requirement, no extra/noncanonical one. Order
        # does not matter -- the contract nowhere makes evaluation order
        # significant, only membership.
        canonical = set(MANDATORY_PERCENTILE_COVERAGE)
        if seen_requirements != canonical:
            missing = canonical - seen_requirements
            extra = seen_requirements - canonical
            raise V2ActivationReadinessError(
                "statuses must cover EXACTLY MANDATORY_PERCENTILE_COVERAGE -- "
                f"missing={sorted(r.source for r in missing)!r}, "
                f"extra={sorted(r.source for r in extra)!r} -- a partial probe can never "
                "be represented as a global activation-readiness result")
        expected_ready = all(status.ready for status in self.statuses)
        if self.ready != expected_ready:
            raise V2ActivationReadinessError(
                f"ready={self.ready!r} does not match "
                f"all(status.ready for status in statuses)={expected_ready!r} -- the class "
                "invariant 'ready iff every status is ready' would be violated")


async def _evaluate_requirements(
    reader: V2SetupHistoryReader, *, symbol: str, market_type: str,
    calculation_version: str, decision_boundary: datetime,
    requirements: Sequence[V2RequiredPercentileCoverage],
) -> "tuple[V2CoverageStatus, ...]":
    """Private: evaluate an ARBITRARY `requirements` sequence and return
    bare `V2CoverageStatus` tuples -- never a `V2ActivationReadinessResult`
    (that type can only represent EXACT `MANDATORY_PERCENTILE_COVERAGE`
    coverage, see its own `__post_init__`). This is the shared per-
    requirement evaluation logic `check_activation_readiness()` calls with
    the canonical requirement set; it also exists so unit tests (and any
    future internal decomposition) can exercise per-requirement behavior
    against a focused subset WITHOUT being able to construct a production
    object that misrepresents a partial probe as global activation
    readiness. Not exported (absent from `__all__`) -- never call this
    from outside this module expecting a production readiness verdict.

    For each requirement, reads exactly
    `alignment.selected_bucket(req.timeframe, decision_boundary)` -- the
    same fully-closed bucket a live detector consumes for that timeframe
    at `decision_boundary` -- under `calculation_version`, never a window,
    never a fallback to an older version or a stale/unrelated bucket."""
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
        # The exact bucket a live detector would read for this
        # requirement's timeframe at `decision_boundary` -- never a
        # window, never anything wider (see module docstring, finding 1).
        bucket = selected_bucket(req.timeframe, decision_boundary)
        rows = await reader.fetch_v2_consensus_percentile_window(
            symbol=symbol, market_type=market_type, metric=req.metric,
            timeframe=req.timeframe, percentile_window=req.percentile_window,
            bucket_start=bucket, bucket_end=bucket,
            calculation_version=calculation_version)
        if not rows:
            statuses.append(V2CoverageStatus(
                requirement=req, ready=False,
                reason=f"no percentile_snapshots row at the exact bucket {bucket.isoformat()}",
                latest_bucket_ts=None))
            continue
        if len(rows) > 1:
            # Defense-in-depth against a fake/misbehaving reader -- the
            # real reader's own contract already forbids more than one row
            # per exact `(scope/exchange/symbol/market_type/metric/
            # timeframe/percentile_window/bucket_ts/calculation_version)`
            # identity, and `bucket_start == bucket_end` here narrows the
            # requested interval to that single `bucket_ts`.
            raise V2ActivationReadinessError(
                f"reader returned {len(rows)} rows for the single exact bucket "
                f"{bucket.isoformat()} (requirement={req.source!r}) -- expected at most 1")
        row = rows[0]
        if row.get("value") is None or row.get("percentile_rank") is None:
            statuses.append(V2CoverageStatus(
                requirement=req, ready=False,
                reason="percentile_snapshots row is missing value/percentile_rank",
                latest_bucket_ts=row.get("bucket_ts")))
            continue
        if not _tier_usable(row.get("confidence_tier")):
            statuses.append(V2CoverageStatus(
                requirement=req, ready=False,
                reason=(
                    f"percentile_snapshots row confidence_tier "
                    f"{row.get('confidence_tier')!r} is below MIN_PCTL_TIER {MIN_PCTL_TIER!r}"),
                latest_bucket_ts=row.get("bucket_ts")))
            continue
        statuses.append(V2CoverageStatus(
            requirement=req, ready=True, reason="ready", latest_bucket_ts=row.get("bucket_ts")))

    return tuple(statuses)


async def check_activation_readiness(
    reader: V2SetupHistoryReader, *, symbol: str, market_type: str,
    calculation_version: str, decision_boundary: datetime,
) -> V2ActivationReadinessResult:
    """Fail-closed, production entry point: always evaluates the FULL
    canonical `MANDATORY_PERCENTILE_COVERAGE` -- there is no public way to
    weaken activation readiness by supplying a caller-chosen subset (tech-
    lead amendment round 2). The returned result's `ready` is `True` iff
    EVERY mandatory requirement has a usable `percentile_snapshots` row at
    EXACTLY `alignment.selected_bucket(req.timeframe, decision_boundary)`
    -- the same fully-closed bucket a live detector consumes for that
    timeframe at `decision_boundary` -- under `calculation_version`. A
    missing row, a `None` `value`/`percentile_rank`, or a below-floor
    `confidence_tier` for even ONE mandatory requirement makes the WHOLE
    result NOT_READY -- never a silent partial pass, never a fallback to
    an older `calculation_version`, an unrelated bucket, or stale data.

    `calculation_version` is passed straight through to `reader` (never
    derived here, never defaulted) -- a caller checking readiness for a
    version OTHER than the one currently active can never accidentally
    query the wrong bucket."""
    statuses = await _evaluate_requirements(
        reader, symbol=symbol, market_type=market_type,
        calculation_version=calculation_version, decision_boundary=decision_boundary,
        requirements=MANDATORY_PERCENTILE_COVERAGE)
    ready = all(status.ready for status in statuses)
    return V2ActivationReadinessResult(
        symbol=symbol, market_type=market_type, calculation_version=calculation_version,
        decision_boundary=decision_boundary, ready=ready, statuses=statuses)
