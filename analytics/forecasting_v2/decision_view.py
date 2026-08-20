"""
V2 coherent decision view (V2-H2a; `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`
§3.4's identity/coherent-view half).

`V2DecisionView` composes an already-resolved `V2DecisionProvenance`
(`decision_provenance.py`, §3.2) with an already-computed
`V2ActivationReadinessResult` (`activation_readiness.py`, §3.3b) into ONE
object representing "this decision boundary's Stage 3/4/5/6 computation is
backed by one coherent, ready identity". §3.4 requires "one decision
boundary T must consume ONE coherent data view" -- a future orchestration
layer (out of scope here; no such orchestration exists yet, per the "no V2
runtime wiring" hard invariant) resolves provenance, checks readiness, and
should construct exactly ONE `V2DecisionView` per decision boundary BEFORE
Stage 3 begins reading, then thread that same view's provenance
(`calculation_version`/`feature_schema_version`, already how
`trend_pullback_inputs.py`'s `load_trend_pullback_inputs` consumes
`V2ContextSnapshot.calculation_version` today) through every Stage 3/5
read -- never re-resolve provenance or re-check readiness mid-computation
for the same `T`.

**Coherence is enforced at `V2DecisionView`'s own construction boundary,
not only by `resolve_decision_view()` (Qodo amendment round 1, finding
5).** `V2DecisionView.__post_init__` itself requires the provenance's
`symbol`/`market_type`/`calculation_version`/`decision_boundary` to equal
the readiness result's -- a caller cannot bypass the coherence checks by
constructing `V2DecisionView(...)` directly instead of going through
`resolve_decision_view()`; there is exactly one way for this type to exist
with a mismatched identity, and that is never. Binding `symbol`/
`market_type` (not just `calculation_version`/`decision_boundary`) closes
the scope-confusion gap `V2ActivationReadinessResult` used to have before
it started carrying its own queried scope (Qodo amendment round 1, finding
3) -- readiness computed for a different symbol/market can no longer be
composed with provenance for another just because the other two fields
happen to match. `resolve_decision_view()` remains as a small,
explicitly-named convenience wrapper over the constructor -- it adds
nothing `V2DecisionView(...)` does not already enforce on its own.

A `NOT_READY` view is still a legitimately constructed, informative
object -- neither `V2DecisionView.__post_init__` nor `resolve_decision_
view()` raises merely because `readiness.ready` is `False`; what a caller
does with a `NOT_READY` view (block, alert, keep draining) is left to the
future orchestration layer, not this module.

This module composes ONLY; it resolves nothing itself:
  - it does not call `check_activation_readiness()` (the caller's job --
    keeps this module free of any DB/reader dependency, pure);
  - it does not construct `V2DecisionProvenance` (the caller's job);
  - it does not implement DRAIN-BEFORE-ACTIVATE's version-SWITCH state
    machine (§3.1, V2-H2b, out of scope);
  - it does not gate Stage 2 correction-generation publication
    completeness (§3.4's OTHER half -- never combining pre-/post-correction
    data even within one `calculation_version`; V2-H2e, out of scope).

Pure only: no DB, network, filesystem, clock, `uuid`, or `random` access --
identical purity discipline to `decision_provenance.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

from analytics.forecasting_v2.activation_readiness import V2ActivationReadinessResult
from analytics.forecasting_v2.decision_provenance import V2DecisionProvenance

__all__ = ["V2DecisionViewError", "V2DecisionView", "resolve_decision_view"]


class V2DecisionViewError(ValueError):
    """The supplied provenance and readiness result do not describe the
    same `(symbol, market_type, calculation_version, decision_boundary)`
    identity -- refused, never silently composed anyway. Also raised for a
    wrong-typed argument. Raised from `V2DecisionView.__post_init__`
    itself, so this holds for EVERY construction path, including a direct
    `V2DecisionView(...)` call -- not only `resolve_decision_view()`."""


@dataclass(frozen=True)
class V2DecisionView:
    """Immutable composition of one decision boundary's resolved identity
    (`provenance`) and its readiness verdict (`readiness`). Self-validates
    in `__post_init__`: both arguments must be the expected type, and
    their `symbol`/`market_type`/`calculation_version`/`decision_boundary`
    must all agree -- there is no construction path (direct call or via
    `resolve_decision_view()`) that can produce a mismatched instance."""
    provenance: V2DecisionProvenance
    readiness: V2ActivationReadinessResult

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, V2DecisionProvenance):
            raise V2DecisionViewError(
                f"provenance must be a V2DecisionProvenance, "
                f"got {type(self.provenance).__name__}")
        if not isinstance(self.readiness, V2ActivationReadinessResult):
            raise V2DecisionViewError(
                f"readiness must be a V2ActivationReadinessResult, "
                f"got {type(self.readiness).__name__}")
        if self.provenance.symbol != self.readiness.symbol:
            raise V2DecisionViewError(
                "provenance.symbol does not match readiness.symbol -- refusing to compose "
                "a decision view for mismatched identities")
        if self.provenance.market_type != self.readiness.market_type:
            raise V2DecisionViewError(
                "provenance.market_type does not match readiness.market_type -- refusing to "
                "compose a decision view for mismatched identities")
        if self.provenance.calculation_version != self.readiness.calculation_version:
            raise V2DecisionViewError(
                "provenance.calculation_version does not match readiness.calculation_version -- "
                "refusing to compose a decision view for mismatched identities")
        if self.provenance.decision_boundary != self.readiness.decision_boundary:
            raise V2DecisionViewError(
                "provenance.decision_boundary does not match readiness.decision_boundary -- "
                "refusing to compose a decision view for mismatched identities")

    @property
    def ready(self) -> bool:
        """Convenience mirror of `readiness.ready` -- never independently
        computed, so it can never drift from the readiness result this
        view was built from."""
        return self.readiness.ready


def resolve_decision_view(
    provenance: V2DecisionProvenance, readiness: V2ActivationReadinessResult,
) -> V2DecisionView:
    """A small, explicitly-named convenience wrapper over
    `V2DecisionView(...)`. All coherence/type checks live in
    `V2DecisionView.__post_init__` itself (so they run for every
    construction path, not only this function) -- this wrapper adds
    nothing beyond a descriptive call site for callers who prefer a
    function name to a bare constructor call."""
    return V2DecisionView(provenance=provenance, readiness=readiness)
