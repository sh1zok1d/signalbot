"""
Pure V2 episode-event construction/factory function (Multi-model Framework
PR 3, docs/FORECASTING_ROADMAP.md §I stage 2).

`build_v2_episode_event()` is the ONE canonical way to stamp run
provenance, V2 model identity, and shared Stage 2 feature provenance
(`provenance.py`'s `V2EventProvenance`) onto an already-decided event's
event-specific facts, producing a `V2EpisodeEvent`
(`events.py`) ready to persist.

This exists so later V2 modules (detectors, the Episode State Machine,
future replay orchestration) do not each hand-assemble all twenty
`V2EpisodeEvent` fields at every call site, silently re-deriving or
re-typing the eleven provenance fields over and over — a copy-paste
surface where one call site could accidentally supply a stale
`rules_version`, or the wrong `model_family`, or a `calculation_version`
computed by a different path than another call site used.

HARD BOUNDARY: this factory does not decide the event. It does exactly:

    validated V2EventProvenance + already-decided event-specific facts
    -> V2EpisodeEvent

It never calculates direction, setup_family, structural_anchor, confidence,
an entry zone, invalidation, or send eligibility; never decides
episode_state; never creates event_id/episode_id; never derives
decision_boundary; never inspects prior events; never reads a DB, config
file, or clock. `V2EpisodeEvent` itself remains the final, self-validating
persistence model — this factory does not add or loosen any validation
`V2EpisodeEvent.__post_init__` already performs, and does not silently
normalize a malformed value on the caller's behalf; a bad input still fails
via `V2EpisodeEvent`'s own `V2EventInputError`.

Provenance fields (`run_kind`, `run_id`, `model_family`, `rules_version`,
`symbol`, `market_type`, `feature_schema_version`, `calculation_version`,
`config_hash`, `config_version`, `code_version`) are NOT parameters of this
function — they come exclusively from the `provenance` argument. A caller
therefore has no way to pass a competing value for any of them; Python
itself rejects an attempt to do so (`TypeError: unexpected keyword
argument`), the same way `V2EpisodeEvent`'s own dataclass fields would.

Pure only: no DB, network, filesystem, clock, `uuid`, or `random` access.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping

from analytics.forecasting_v2.events import V2EpisodeEvent
from analytics.forecasting_v2.provenance import V2EventProvenance

__all__ = ["build_v2_episode_event"]


def build_v2_episode_event(
    provenance: V2EventProvenance,
    *,
    event_id: str,
    episode_id: str,
    direction: str,
    setup_family: str,
    structural_anchor: Mapping,
    episode_state: str,
    decision_boundary: datetime,
    decision_snapshot: Mapping,
    event_payload: Mapping,
) -> V2EpisodeEvent:
    """Combine `provenance` (run/model/shared-provenance identity, already
    resolved and validated) with the caller's already-decided event-specific
    facts into one immutable, self-validating `V2EpisodeEvent`.

    `provenance` is read, never mutated — a `V2EventProvenance` is itself
    frozen, so there is nothing for this function to mutate even
    accidentally. Malformed event-specific arguments (e.g. an unsupported
    `direction`, a non-Mapping `event_payload`, a naive `decision_boundary`)
    are NOT caught or normalized here; they fail exactly as they would
    constructing a `V2EpisodeEvent` directly, via `V2EventInputError`,
    because this function performs no validation of its own beyond
    delegating to `V2EpisodeEvent.__post_init__`."""
    return V2EpisodeEvent(
        run_kind=provenance.run_kind,
        run_id=provenance.run_id,
        event_id=event_id,
        episode_id=episode_id,
        model_family=provenance.model_family,
        rules_version=provenance.rules_version,
        symbol=provenance.symbol,
        market_type=provenance.market_type,
        direction=direction,
        setup_family=setup_family,
        structural_anchor=structural_anchor,
        episode_state=episode_state,
        decision_boundary=decision_boundary,
        feature_schema_version=provenance.feature_schema_version,
        calculation_version=provenance.calculation_version,
        config_hash=provenance.config_hash,
        config_version=provenance.config_version,
        code_version=provenance.code_version,
        decision_snapshot=decision_snapshot,
        event_payload=event_payload,
    )
