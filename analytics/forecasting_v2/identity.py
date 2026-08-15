"""
V2 model/version identity primitives (Multi-model Framework foundation PR 1,
docs/FORECASTING_ROADMAP.md §I stage 2).

Freezes exactly the identity model docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md
§3 defines — `model_family` and `rules_version` — as a small, immutable,
self-validating value object. Nothing else: no detector, scoring, episode,
context, or lifecycle logic exists in this package yet, deliberately (that
section's own framing: "V2 introduces one new logical identity of its own").

Pure only: no clock, DB, network, or filesystem access. `V2ModelIdentity`
never reads config/v2.yaml itself — a caller resolves the active identity via
`common.v2_config.V2Config.load()` and passes the resulting values in.
"""
from __future__ import annotations

from dataclasses import dataclass

from common.v2_config import MODEL_FAMILY, validate_rules_version

__all__ = ["MODEL_FAMILY", "V2IdentityError", "V2ModelIdentity"]


class V2IdentityError(ValueError):
    """Raised when a V2ModelIdentity is constructed with an invalid
    model_family / rules_version (explicit, no coercion)."""


@dataclass(frozen=True)
class V2ModelIdentity:
    """Deeply-immutable V2 decision-rule identity: `(model_family,
    rules_version)`. Mirrors V1's `ForecastRuleSet.rule_version` role one
    layer up (`analytics/forecasting/models.py`) — V2's `rules_version` is a
    disjoint namespace from V1's `rule_version`, never valid as the other
    (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3).

    `model_family` MUST always be exactly `"v2"` — it is not a free-form
    field a caller can set to something else; the constructor enforces it so
    a typo can never silently produce an unidentifiable row family.
    """
    model_family: str
    rules_version: str

    def __post_init__(self) -> None:
        if self.model_family != MODEL_FAMILY:
            raise V2IdentityError(
                f"model_family must be exactly {MODEL_FAMILY!r}, got {self.model_family!r}")
        try:
            validate_rules_version(self.rules_version)
        except ValueError as exc:
            # Re-raised as this module's own error type so a caller
            # constructing a V2ModelIdentity directly (not via V2Config)
            # never has to catch a config-loading exception type for what is,
            # from here, a pure value-object validation failure.
            raise V2IdentityError(str(exc)) from exc
