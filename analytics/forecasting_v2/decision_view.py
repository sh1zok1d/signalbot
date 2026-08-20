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

`resolve_decision_view()` is the ONE constructor path: it requires the
provenance's `calculation_version` to equal the readiness result's
`calculation_version`, and the provenance's `decision_boundary` to equal the
readiness result's `decision_boundary` -- a caller cannot accidentally
compose a provenance for version A with a readiness result computed for
version B, or for a different `T`, and get a silently-mismatched view back.
A `NOT_READY` view is still a legitimately constructed, informative
object -- `resolve_decision_view()` never raises merely because
`readiness.ready` is `False`; what a caller does with a `NOT_READY` view
(block, alert, keep draining) is left to the future orchestration layer,
not this module.

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
    same `(calculation_version, decision_boundary)` identity -- refused,
    never silently composed anyway. Also raised for a wrong-typed
    argument."""


@dataclass(frozen=True)
class V2DecisionView:
    """Immutable composition of one decision boundary's resolved identity
    (`provenance`) and its readiness verdict (`readiness`). Only ever
    constructed via `resolve_decision_view()`, which enforces the two
    objects actually describe the same identity."""
    provenance: V2DecisionProvenance
    readiness: V2ActivationReadinessResult

    @property
    def ready(self) -> bool:
        """Convenience mirror of `readiness.ready` -- never independently
        computed, so it can never drift from the readiness result this
        view was built from."""
        return self.readiness.ready


def resolve_decision_view(
    provenance: V2DecisionProvenance, readiness: V2ActivationReadinessResult,
) -> V2DecisionView:
    """The one constructor path for `V2DecisionView`. Raises
    `V2DecisionViewError` if `provenance` and `readiness` do not describe
    the same `(calculation_version, decision_boundary)` identity, or if
    either argument is not the expected type. Never re-validates the
    individual objects' own fields -- both already self-validated in their
    own `__post_init__`."""
    if not isinstance(provenance, V2DecisionProvenance):
        raise V2DecisionViewError(
            f"provenance must be a V2DecisionProvenance, got {type(provenance).__name__}")
    if not isinstance(readiness, V2ActivationReadinessResult):
        raise V2DecisionViewError(
            f"readiness must be a V2ActivationReadinessResult, got {type(readiness).__name__}")
    if provenance.calculation_version != readiness.calculation_version:
        raise V2DecisionViewError(
            "provenance.calculation_version does not match readiness.calculation_version -- "
            "refusing to compose a decision view for mismatched identities")
    if provenance.decision_boundary != readiness.decision_boundary:
        raise V2DecisionViewError(
            "provenance.decision_boundary does not match readiness.decision_boundary -- "
            "refusing to compose a decision view for mismatched identities")
    return V2DecisionView(provenance=provenance, readiness=readiness)
