"""
Narrow V2 storage dependency ports (Multi-model Framework PR 3 /
Multi-timeframe Alignment PR 3, docs/FORECASTING_ROADMAP.md §I stages 2-3).

Two structural-typing `Protocol`s future V2 orchestration/analytics code
should depend on, instead of importing the concrete `storage.db.Database`:

  - `V2EpisodeEventWriter` — the narrow write port for immutable
    `V2EpisodeEvent` persistence (Multi-model Framework PR 2).
  - `V2AlignedInputReader` — the narrow read port the Stage 3 aligned-input
    assembler (`analytics/forecasting_v2/aligned_inputs.py`) depends on:
    exact-bucket consensus/percentile reads, bounded health-at-cutoff
    reads, and exact-bucket reference-exchange feature/raw-kline reads.

`storage.db.Database` already implements both shapes — nothing here
changes those methods or wires them into anything; this module only names
the narrow slices of `Database`'s surface a future V2 caller is allowed to
depend on.

Why a `Protocol` and not a base class: `storage.db.Database` is not made to
inherit from either Protocol, and no wrapper subclass is introduced either —
`typing.Protocol` gives structural ("duck") typing, so any object exposing
matching coroutine methods satisfies a port for free, without a runtime
inheritance relationship. A minimal fake writer/reader built purely for a
future analytics test can satisfy either Protocol without importing
`storage/db.py` at all.

This module intentionally adds NOTHING beyond the type shape:
  - no retries;
  - no transactions;
  - no DB reads/writes of its own;
  - no business/validation logic of its own — `V2EpisodeEvent`
    (`events.py`), the writer's own `serialize_batch` call
    (`storage/v2_serialization.py`), and `storage/v2_alignment_readers.py`'s
    own validators already own that;
  - no runtime wiring — nothing in this PR calls either Protocol outside
    its own tests.

Pure only: this is a type definition, not an implementation. No DB,
network, filesystem, clock, `uuid`, or `random` access.
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, Optional, Protocol, Sequence, runtime_checkable

from analytics.forecasting_v2.events import V2EpisodeEvent

__all__ = ["V2EpisodeEventWriter", "V2AlignedInputReader"]


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


@runtime_checkable
class V2AlignedInputReader(Protocol):
    """Structural port for the five exact/bounded Stage 2 + reference-
    exchange reads `analytics/forecasting_v2/aligned_inputs.py::
    load_v2_aligned_inputs` needs: exact-bucket consensus, exact-bucket
    consensus-scope percentiles, bounded health-at-cutoff, exact-bucket
    reference-exchange feature, and half-open-interval raw reference
    klines. Every method's contract (exact identity, no fallback, explicit
    `calculation_version`, bounded — never wall-clock — cutoffs) is owned
    by `storage/v2_alignment_readers.py`, not by this Protocol.

    `storage.db.Database` matches this shape structurally today (its five
    `fetch_v2_*` methods, Multi-timeframe Alignment PR 2/PR 3); this
    Protocol does not import or reference that class, so a caller
    depending on `V2AlignedInputReader` never needs to import
    `storage/db.py`."""

    async def fetch_v2_consensus_feature(
        self, *, symbol: str, market_type: str, timeframe: str,
        bucket_ts: datetime, calculation_version: str,
    ) -> Optional[Mapping]:
        ...

    async def fetch_v2_consensus_percentiles(
        self, *, symbol: str, market_type: str, timeframe: str,
        bucket_ts: datetime, calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        ...

    async def fetch_v2_data_health_at_cutoff(
        self, *, symbol: str, market_type: str, exchanges: Sequence[str],
        metrics: Sequence[str], cutoff_ts: datetime, calculation_version: str,
    ) -> Mapping:
        ...

    async def fetch_v2_reference_feature(
        self, *, exchange: str, symbol: str, market_type: str, timeframe: str,
        bucket_ts: datetime, calculation_version: str,
    ) -> Optional[Mapping]:
        ...

    async def fetch_v2_reference_klines(
        self, *, exchange: str, symbol: str, bucket_start: datetime, bucket_end: datetime,
    ) -> "tuple[Mapping, ...]":
        ...
