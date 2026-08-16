"""
Narrow V2 event-writer dependency port (Multi-model Framework PR 3,
docs/FORECASTING_ROADMAP.md §I stage 2).

`V2EpisodeEventWriter` is a structural-typing `Protocol` future V2
orchestration/analytics code should depend on, instead of importing the
concrete `storage.db.Database`. `storage.db.Database` already implements
this shape (`insert_v2_episode_events`, added in Multi-model Framework
PR 2) — nothing here changes that method or wires it into anything; this
module only names the narrow slice of `Database`'s surface a future V2
caller is allowed to depend on.

Why a `Protocol` and not a base class: `storage.db.Database` is not made to
inherit from this Protocol, and no wrapper subclass is introduced either —
`typing.Protocol` gives structural ("duck") typing, so any object exposing
a matching `insert_v2_episode_events` coroutine method satisfies the port
for free, without a runtime inheritance relationship. A minimal fake writer
built purely for a future analytics test can satisfy this Protocol without
importing `storage/db.py` at all.

This module intentionally adds NOTHING beyond the type shape:
  - no retries;
  - no transactions;
  - no DB reads;
  - no business/validation logic of its own — `V2EpisodeEvent`
    (`events.py`) and the writer's own `serialize_batch` call
    (`storage/v2_serialization.py`) already own that;
  - no runtime wiring — nothing in this PR calls a `V2EpisodeEventWriter`
    outside its own tests.

Pure only: this is a type definition, not an implementation. No DB,
network, filesystem, clock, `uuid`, or `random` access.
"""
from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from analytics.forecasting_v2.events import V2EpisodeEvent

__all__ = ["V2EpisodeEventWriter"]


@runtime_checkable
class V2EpisodeEventWriter(Protocol):
    """Structural port for anything that can durably, insert-once persist a
    batch of already-decided `V2EpisodeEvent` rows and report how many were
    actually inserted (never overwritten — see `events.py`/§2.1 for the
    insert-once, historical-truth discipline this count reflects).

    `storage.db.Database.insert_v2_episode_events` matches this shape
    structurally today; this Protocol does not import or reference that
    class, so a caller depending on `V2EpisodeEventWriter` never needs to
    import `storage/db.py`."""

    async def insert_v2_episode_events(
        self,
        rows: Sequence[V2EpisodeEvent],
    ) -> int:
        ...
