"""
Immutable V2 event provenance snapshot (Multi-model Framework PR 3,
docs/FORECASTING_ROADMAP.md §I stage 2).

`V2EventProvenance` captures the already-resolved identity/provenance
fields shared by ONE event-construction operation: run provenance
(`run_kind`/`run_id`, §2.1), model/version identity (`model_family`/
`rules_version`, §3), the episode's fixed scope (`symbol`/`market_type`),
and the shared Stage 2 feature-computation provenance
(`feature_schema_version`/`calculation_version`/`config_hash`/
`config_version`/`code_version`).

It is NOT:
  - a detector result — it carries no direction/setup_family/structural
    information;
  - an episode — it carries no episode_id/episode_state;
  - a state machine — it makes no lifecycle decision of any kind;
  - a global registry or runtime session manager — it is a plain, frozen,
    stateless value a caller constructs once and passes to
    `event_factory.build_v2_episode_event()` for as many events as share
    that provenance.

Pure only: no DB, network, filesystem, clock, `uuid`, or `random` access —
identical purity discipline to `events.py`'s `V2EpisodeEvent`. Every field
is caller-supplied, already resolved. This is deliberate for replay
correctness (§20): a historical replay operates on HISTORICAL provenance —
the exact `rules_version`/`calculation_version`/`config_hash`/etc. that
were active at decision time — and MUST NOT have this object silently
substitute today's active config/version in their place. The future
orchestration/alignment layer resolves and supplies those already-decided
values; this module only validates and freezes them.

Cross-event scope note (§3, §9 below in the design discussion): this
object guarantees that ONE event explicitly carries its own
`rules_version`/`calculation_version` and cannot have them silently
sourced from the wrong field. It does NOT — and cannot — guarantee the
correctness-contract invariant that an existing EPISODE's `rules_version`
stays fixed across that episode's entire life (§3's "an episode/decision
record's `rules_version`... MUST NOT change over that record's life").
Enforcing that requires comparing a new event's provenance against the
episode's prior events' history, which requires state the future Episode
State Machine owns — not something a stateless per-call provenance
snapshot can see or enforce.
"""
from __future__ import annotations

from dataclasses import dataclass

from analytics.forecasting_v2._validation import (
    SUPPORTED_MARKET_TYPE, SUPPORTED_SYMBOL, nonblank, one_of,
    validate_calculation_version, validate_config_hash,
    validate_feature_schema_version, validate_market_type, validate_symbol,
)
from analytics.forecasting_v2.events import RUN_KINDS
from common.v2_config import MODEL_FAMILY, validate_rules_version

__all__ = ["V2ProvenanceError", "V2EventProvenance"]


class V2ProvenanceError(ValueError):
    """Malformed V2EventProvenance input: bad run identity, unsupported
    scope, an invalid model/version identity, or a malformed shared Stage 2
    provenance field. Never silently coerced."""


@dataclass(frozen=True)
class V2EventProvenance:
    """Deeply-immutable, self-validating snapshot of one event-construction
    operation's identity/provenance. See module docstring for exactly what
    this is and is not.

    Field groups:
      - run provenance (§2.1): `run_kind` (`LIVE`|`REPLAY`), `run_id`
        (non-empty caller-supplied namespace for the execution).
      - model/version identity (§3): `model_family` (always exactly
        `"v2"`), `rules_version` (the frozen
        `v2-rules-v<major>.<minor>.<patch>` namespace, validated via
        `common.v2_config.validate_rules_version` — the same validator
        `V2EpisodeEvent` itself uses, never a second competing regex).
      - initial V2 scope (V2_PRODUCT_CONTRACT.md §1): `symbol`,
        `market_type` — pinned to the same `SUPPORTED_SYMBOL`/
        `SUPPORTED_MARKET_TYPE` constants `V2EpisodeEvent` enforces.
      - shared Stage 2 provenance (§3): `feature_schema_version`,
        `calculation_version`, `config_hash`, `config_version`,
        `code_version` — recorded as supplied, never recomputed or loaded
        from `config/stage2.yaml`/`config/v2.yaml` here.
    """
    run_kind: str
    run_id: str

    model_family: str
    rules_version: str

    symbol: str
    market_type: str

    feature_schema_version: int
    calculation_version: str
    config_hash: str
    config_version: str
    code_version: str

    def __post_init__(self) -> None:
        one_of(self.run_kind, "run_kind", RUN_KINDS, V2ProvenanceError)
        nonblank(self.run_id, "run_id", V2ProvenanceError)

        if self.model_family != MODEL_FAMILY:
            raise V2ProvenanceError(
                f"model_family must be exactly {MODEL_FAMILY!r}, got {self.model_family!r}")
        try:
            validate_rules_version(self.rules_version)
        except ValueError as exc:
            raise V2ProvenanceError(str(exc)) from exc

        validate_symbol(self.symbol, V2ProvenanceError)
        validate_market_type(self.market_type, V2ProvenanceError)

        validate_feature_schema_version(self.feature_schema_version, V2ProvenanceError)
        validate_calculation_version(self.calculation_version, V2ProvenanceError)
        validate_config_hash(self.config_hash, V2ProvenanceError)
        nonblank(self.config_version, "config_version", V2ProvenanceError)
        nonblank(self.code_version, "code_version", V2ProvenanceError)
