"""
Pure V2 episode-event construction/factory function (Multi-model Framework
PR 3, docs/FORECASTING_ROADMAP.md §I stage 2; V2-H3 amendment,
docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §2.1a).

`build_v2_episode_event()` is the ONE canonical way to stamp run
provenance, V2 model identity, shared Stage 2 feature provenance
(`provenance.py`'s `V2EventProvenance`), and DETERMINISTIC `episode_id`/
`event_id` identity (`episode_identity.py`) onto an already-decided event's
event-specific facts, producing a `V2EpisodeEvent` (`events.py`) ready to
persist.

**V2-H3 amendment: `event_id`/`episode_id` are no longer caller-supplied
parameters of this function at all (closes a confirmed blocker).** Before
this amendment, this factory accepted `event_id: str, episode_id: str`
directly from the caller — despite being "the ONE canonical way" to
construct a persistence-ready event, it did nothing to actually enforce
deterministic identity; a future Stage 6 caller could simply forget to
call `episode_identity.py`'s `compute_episode_id()`/`compute_event_id()`
and supply an arbitrary string instead, and this factory would have
happily accepted it. Both are now ALWAYS computed internally:

    episode_id = compute_episode_id(..., direction, setup_family,
                                     structural_anchor, t_create)
    event_id   = compute_event_id(episode_id, decision_boundary)

`t_create` — the episode's own fixed `EARLY_SIGNAL` creation decision
boundary — is now a REQUIRED parameter of this function instead of
`episode_id`. This is not a new concept invented here: `direction`,
`setup_family`, and `structural_anchor` were ALREADY required parameters
of this factory, and per `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`
§12.2/§12.2a they are ALREADY required to stay fixed at their creation
values for every event of one episode's entire life (this is exactly what
`events.py`'s own docstring means by "`structural_anchor` ... form[s]
`episode_logical_key`" — the top-level `V2EpisodeEvent.structural_anchor`
field is the episode's frozen identity anchor, never a later drifted
observation, which belongs in `decision_snapshot`/`event_payload` instead
per §12.3's own text). A caller that can correctly persist ANY event for
an existing episode already necessarily knows these facts; requiring
`t_create` alongside them, rather than accepting an opaque `episode_id`
string instead, is what actually makes `episode_id` deterministically
REPRODUCIBLE from this factory rather than merely "recommended" by a
parallel, optional module. For the episode's own creation event,
`t_create == decision_boundary` (the same instant, passed under both
names, since decision_boundary is that event's own T); for every later
event of the same episode, `t_create` remains the ORIGINAL creation
boundary while `decision_boundary` is that later event's own, later T.

This exists so later V2 modules (detectors, the Episode State Machine,
future replay orchestration) do not each hand-assemble all twenty-one
`V2EpisodeEvent` fields (or manually re-derive `episode_id`/`event_id`) at
every call site, silently re-deriving or re-typing the provenance/identity
fields over and over — a copy-paste surface where one call site could
accidentally supply a stale `rules_version`, the wrong `model_family`, a
`calculation_version` computed by a different path than another call site
used, or (before this amendment) a non-deterministic `event_id`.

HARD BOUNDARY: this factory does not decide the event. It does exactly:

    validated V2EventProvenance + already-decided event-specific facts
    -> deterministic episode_id/event_id (episode_identity.py)
    -> V2EpisodeEvent

It never calculates direction, setup_family, structural_anchor, confidence,
an entry zone, invalidation, or send eligibility; never decides
episode_state; never derives decision_boundary; never inspects prior
events; never reads a DB, config file, or clock. `V2EpisodeEvent` itself
remains the final, self-validating persistence model — this factory does
not add or loosen any validation `V2EpisodeEvent.__post_init__` already
performs, and does not silently normalize a malformed value on the
caller's behalf. A malformed `direction`/`setup_family`/`structural_anchor`/
`t_create` now fails FIRST at `compute_episode_id()`'s own validation
(`V2EpisodeIdentityError`, never `V2EventInputError`, since that failure
happens before a `V2EpisodeEvent` is ever constructed) — every other
malformed field (e.g. a non-Mapping `event_payload`, an unsupported
`episode_state`) still fails exactly as it would constructing a
`V2EpisodeEvent` directly, via `V2EventInputError`.

Provenance fields (`run_kind`, `run_id`, `model_family`, `rules_version`,
`symbol`, `market_type`, `feature_schema_version`, `calculation_version`,
`config_hash`, `config_version`, `code_version`, `decision_code_version`)
are NOT parameters of this function — they come exclusively from the
`provenance` argument. A caller therefore has no way to pass a competing
value for any of them; Python itself rejects an attempt to do so
(`TypeError: unexpected keyword argument`), the same way `V2EpisodeEvent`'s
own dataclass fields would. `event_id`/`episode_id` are, likewise, no
longer parameters at all -- the same `TypeError` now protects them too.

Pure only: no DB, network, filesystem, clock, `uuid`, or `random` access.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping

from analytics.forecasting_v2.episode_identity import compute_episode_id, compute_event_id
from analytics.forecasting_v2.events import V2EpisodeEvent
from analytics.forecasting_v2.provenance import V2EventProvenance

__all__ = ["build_v2_episode_event"]


def build_v2_episode_event(
    provenance: V2EventProvenance,
    *,
    t_create: datetime,
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
    facts into one immutable, self-validating `V2EpisodeEvent` — computing
    `episode_id`/`event_id` deterministically via `episode_identity.py`
    rather than accepting either as an opaque caller-supplied string.

    `t_create` MUST be the episode's own fixed `EARLY_SIGNAL` creation
    decision boundary — the SAME value for every event of one episode's
    entire life, per §12.2/§12.2a (never a later "current" decision
    boundary; see module docstring for the full rationale). `direction`/
    `setup_family`/`structural_anchor` MUST likewise be that same episode's
    frozen creation identity facts for every one of its events, exactly as
    `events.py`'s own `episode_logical_key` framing already required before
    this amendment — this function does not introduce a new invariant, it
    only makes the ALREADY-required facts also drive `episode_id`
    deterministically.

    `provenance` is read, never mutated — a `V2EventProvenance` is itself
    frozen, so there is nothing for this function to mutate even
    accidentally.

    Raises `V2EpisodeIdentityError` (from `compute_episode_id()`/
    `compute_event_id()`) for a malformed `direction`/`setup_family`/
    `structural_anchor`/`t_create`/`decision_boundary` — before any
    `V2EpisodeEvent` is constructed. Raises `V2EventInputError` for every
    other malformed field (e.g. a non-Mapping `event_payload`, an
    unsupported `episode_state`), exactly as constructing a `V2EpisodeEvent`
    directly would; this function performs no additional validation of its
    own for those fields beyond delegating to `V2EpisodeEvent.__post_init__`."""
    episode_id = compute_episode_id(
        model_family=provenance.model_family,
        rules_version=provenance.rules_version,
        calculation_version=provenance.calculation_version,
        symbol=provenance.symbol,
        market_type=provenance.market_type,
        direction=direction,
        setup_family=setup_family,
        structural_anchor=structural_anchor,
        t_create=t_create,
    )
    event_id = compute_event_id(episode_id=episode_id, decision_boundary=decision_boundary)
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
        decision_code_version=provenance.decision_code_version,
        decision_snapshot=decision_snapshot,
        event_payload=event_payload,
    )
