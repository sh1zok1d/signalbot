"""
V2 decision provenance tuple (V2-H2a; `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`
§3.2).

`V2DecisionProvenance` is the immutable identity tuple that §3.2 requires be
resolved ONCE, before ANY Stage 3/4/5/6 computation begins for one logical
decision boundary `T`. It binds, at minimum: the execution stream
(`run_kind`/`run_id`), the decision boundary `T` itself, `symbol`/
`market_type`, `model_family`/`rules_version`, the shared Stage 2 feature-
computation identity (`feature_schema_version`/`calculation_version`/
`config_hash`/`config_version`/`code_version`), and `decision_code_version`
-- the Stage 4/5/6 DECISION-code identity, deliberately distinct from
`code_version` (Stage 2's FEATURE-computation-code identity, §3.3). The same
tuple must follow one computation through every stage it passes through; a
candidate computed under tuple A must never later be wrapped/persisted as
tuple B.

Relationship to `provenance.py`'s `V2EventProvenance` (Multi-model Framework
PR 3): `V2EventProvenance` is the narrower, already-established snapshot
`event_factory.build_v2_episode_event()` consumes at EVENT-CONSTRUCTION time
(Stage 6, not yet implemented). `V2DecisionProvenance` is a superset resolved
earlier, at DECISION time (before Stage 3 even runs) -- it adds exactly the
two fields §3.2 requires that `V2EventProvenance` does not carry:
`decision_boundary` (`T`) and `decision_code_version`. The two objects are
deliberately NOT the same dataclass: an event-construction-time snapshot and
a pre-computation decision identity have different validity windows and
different callers, and collapsing them would let a future change to one
silently perturb the other's field set. Field VALIDATION is shared (both
reuse `analytics.forecasting_v2._validation`'s helpers and
`common.v2_config`'s model/rules-version validators), so the two objects can
never validate the same field two different ways.

Pure only: no DB, network, filesystem, clock, `uuid`, or `random` access --
identical purity discipline to `provenance.py`'s `V2EventProvenance`. Every
field is caller-supplied, already resolved; this module only validates and
freezes them. This is deliberate for replay correctness (§20): a historical
replay operates on HISTORICAL provenance -- the exact `rules_version`/
`calculation_version`/`config_hash`/`decision_code_version`/etc. that were
active at decision time -- and MUST NOT have this object silently substitute
today's active config/version in their place.

Deliberately NOT included here (out of scope for V2-H2a):
  - activation readiness (whether `calculation_version` is fit to compute
    against right now) -- `analytics/forecasting_v2/activation_readiness.py`;
  - composing this tuple with a readiness result into one coherent view for
    a future orchestration layer -- `analytics/forecasting_v2/decision_view.py`;
  - DRAIN-BEFORE-ACTIVATE version-switch state (§3.1) -- V2-H2b;
  - as-of/historical instrument metadata (§12.5a) -- V2-H2c;
  - Stage 2 correction-generation publication completeness (§3.4's other
    half) and replay-determinism harness -- V2-H2e;
  - any runtime orchestration that actually RESOLVES a live tuple's field
    values from a running system (execution stream, wall-clock `T`,
    currently-active config) -- left open by the contract as "a future
    implementation choice", not this PR's job.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from analytics.forecasting_v2._validation import (
    nonblank, one_of, validate_calculation_version, validate_config_hash,
    validate_feature_schema_version, validate_market_type, validate_symbol,
)
from analytics.forecasting_v2.events import RUN_KINDS
from common.v2_config import MODEL_FAMILY, validate_rules_version

__all__ = ["V2DecisionProvenanceError", "V2DecisionProvenance"]


class V2DecisionProvenanceError(ValueError):
    """Malformed V2DecisionProvenance input: bad run identity, a decision
    boundary that is not an aware/UTC/whole-minute instant, unsupported
    scope, an invalid model/version identity, or a malformed shared Stage 2
    or decision-code provenance field. Never silently coerced."""


def _validate_decision_boundary(value: Any) -> datetime:
    """Aware, UTC, whole-minute `datetime` -- the exact same posture every
    other V2-v0 module's local `_validate_utc_whole_minute`/
    `_validate_utc_datetime` helper already enforces for `T`
    (`compression_breakout.py`, `trend_pullback.py`, `regime_4h.py`,
    `bias_1h.py`, `context_evidence.py`, `alignment.py`). Re-implemented
    locally rather than imported from any one of those modules: none of
    them exports it as public API, and each already keeps its own private
    copy by established convention -- this module follows the same
    precedent rather than inventing a new shared cross-module dependency."""
    if type(value) is not datetime:
        raise V2DecisionProvenanceError(
            f"decision_boundary must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2DecisionProvenanceError("decision_boundary must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise V2DecisionProvenanceError(
            f"decision_boundary must be UTC (offset 0), got {value.utcoffset()}")
    if value.second != 0 or value.microsecond != 0:
        raise V2DecisionProvenanceError(
            "decision_boundary must be a whole minute (no seconds/microseconds)")
    return value


@dataclass(frozen=True)
class V2DecisionProvenance:
    """Deeply-immutable, self-validating snapshot of the identity tuple that
    MUST be resolved before Stage 3/4/5/6 computation begins for one decision
    boundary. See module docstring for exactly what this is and is not.

    Field groups (§3.2):
      - execution stream: `run_kind` (`LIVE`|`REPLAY`), `run_id` (non-empty
        caller-supplied namespace for the execution).
      - `decision_boundary`: the decision boundary `T` this tuple is bound
        to -- aware, UTC, whole-minute.
      - scope: `symbol`, `market_type` -- pinned to the same
        `SUPPORTED_SYMBOL`/`SUPPORTED_MARKET_TYPE` constants every other V2
        value object enforces.
      - model/version identity: `model_family` (always exactly `"v2"`),
        `rules_version` (the frozen `v2-rules-v<major>.<minor>.<patch>`
        namespace).
      - shared Stage 2 feature-computation provenance (§3.3): must follow
        one Stage 2 feature computation's OWN identity through Stage 3/5's
        reads unchanged -- `feature_schema_version`, `calculation_version`,
        `config_hash`, `config_version`, `code_version`.
      - `decision_code_version`: the Stage 4/5/6 DECISION-code identity --
        deliberately a SEPARATE field from `code_version` (§3.3's Stage 2
        feature-computation-code identity). Changing the decision code
        (Stage 4/5/6 logic) must never be conflated with, or silently
        change, Stage 2's `calculation_version` namespace, and vice versa.
    """
    run_kind: str
    run_id: str

    decision_boundary: datetime

    symbol: str
    market_type: str

    model_family: str
    rules_version: str

    feature_schema_version: int
    calculation_version: str
    config_hash: str
    config_version: str
    code_version: str

    decision_code_version: str

    def __post_init__(self) -> None:
        one_of(self.run_kind, "run_kind", RUN_KINDS, V2DecisionProvenanceError)
        nonblank(self.run_id, "run_id", V2DecisionProvenanceError)

        _validate_decision_boundary(self.decision_boundary)

        validate_symbol(self.symbol, V2DecisionProvenanceError)
        validate_market_type(self.market_type, V2DecisionProvenanceError)

        if self.model_family != MODEL_FAMILY:
            raise V2DecisionProvenanceError(
                f"model_family must be exactly {MODEL_FAMILY!r}, got {self.model_family!r}")
        try:
            validate_rules_version(self.rules_version)
        except ValueError as exc:
            raise V2DecisionProvenanceError(str(exc)) from exc

        validate_feature_schema_version(self.feature_schema_version, V2DecisionProvenanceError)
        validate_calculation_version(self.calculation_version, V2DecisionProvenanceError)
        validate_config_hash(self.config_hash, V2DecisionProvenanceError)
        nonblank(self.config_version, "config_version", V2DecisionProvenanceError)
        nonblank(self.code_version, "code_version", V2DecisionProvenanceError)
        nonblank(self.decision_code_version, "decision_code_version", V2DecisionProvenanceError)
