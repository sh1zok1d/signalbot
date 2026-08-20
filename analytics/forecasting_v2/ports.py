"""
Narrow V2 storage dependency ports (Multi-model Framework PR 3 /
Multi-timeframe Alignment PR 3 / Setup Detectors PR 1,
docs/FORECASTING_ROADMAP.md §I stages 2-3, 5).

Four structural-typing `Protocol`s future V2 orchestration/analytics
code should depend on, instead of importing the concrete
`storage.db.Database`:

  - `V2EpisodeEventWriter` — the narrow write port for immutable
    `V2EpisodeEvent` persistence (Multi-model Framework PR 2).
  - `V2AlignedInputReader` — the narrow read port the Stage 3 aligned-input
    assembler (`analytics/forecasting_v2/aligned_inputs.py`) depends on:
    exact-bucket consensus/percentile reads, bounded health-at-cutoff
    reads, and exact-bucket reference-exchange feature/raw-kline reads.
  - `V2SetupHistoryReader` — the narrow read port future Stage 5 detector
    assemblers (PR 2/~4 onward) will depend on: deterministic HISTORICAL
    WINDOW reads (`storage/v2_setup_readers.py`) plus the existing
    Stage 3 raw-kline window read reused unchanged
    (`read_v2_reference_klines`). Deliberately a SEPARATE Protocol from
    `V2AlignedInputReader`, not an extension of it — Stage 3's exact
    single-bucket reads and Stage 5's historical-window reads are
    different semantic scopes, and widening `V2AlignedInputReader` would
    unnecessarily change the Stage 3 interface and could invalidate
    existing Stage 3 test doubles that only ever needed to satisfy the
    original five-method shape. There is no inheritance relationship
    between the two Protocols; a fake satisfying only
    `V2AlignedInputReader` does not need to implement any
    `V2SetupHistoryReader` method, and vice versa.
  - `V2VersionDrainStatusReader` — the narrow read port V2-H2b's
    orchestration layer (`analytics/forecasting_v2/
    version_switch_orchestrator.py`) depends on for the ONE fact
    `version_switch.py`'s pure state machine needs while a switch is
    `DRAINING`: OLD's non-terminal-episode/active-cooldown counts, scoped
    to exactly one `execution_stream` and exactly the OLD semantic tuple
    (§3.1/§12.10). Deliberately abstract: Stage 6 (the episode state
    machine that would own a real `v2_episode_events`-backed answer to
    "how many non-terminal episodes/active cooldowns does this tuple have
    right now") has NOT been implemented yet (out of scope for V2-H2b by
    explicit task instruction) — there is today no concrete, real
    implementation of this Protocol anywhere in the codebase, only
    deterministic fakes in tests. A real Stage-6-backed implementation is
    deferred, explicitly, to whichever future Stage 6 PR first needs to
    answer this question for real; wiring it to `storage.db.Database` is
    NOT this PR's job.

`storage.db.Database` already implements the first three shapes
(`V2EpisodeEventWriter`/`V2AlignedInputReader`/`V2SetupHistoryReader`) —
nothing here changes those methods or wires them into anything; this
module only names the narrow slices of `Database`'s surface a future V2
caller is allowed to depend on. The fourth Protocol,
`V2VersionDrainStatusReader`, is deliberately DIFFERENT: `Database` does
NOT implement it (see that Protocol's own docstring) — no concrete,
real implementation of it exists anywhere in this codebase yet, only
deterministic fakes in tests, since the Stage 6 query it would wrap does
not exist.

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
from analytics.forecasting_v2.version_switch import V2DrainFact

__all__ = [
    "V2EpisodeEventWriter", "V2AlignedInputReader", "V2SetupHistoryReader",
    "V2VersionDrainStatusReader",
]


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


@runtime_checkable
class V2SetupHistoryReader(Protocol):
    """Structural port for the deterministic historical-window reads
    future Stage 5 detector assemblers (PR 2/~4 onward) will need: a
    `consensus_feature_vectors` window, a consensus-scope
    `percentile_snapshots` window, an `exchange_feature_vectors` window,
    the existing raw-kline half-open-interval read (reused unchanged from
    Stage 3, `read_v2_reference_klines` — no second raw-kline window API
    exists), and a single-row `exchange_instruments` lookup for
    `protection_buffer()`'s `tick_size` input. Every method's contract
    (inclusive bucket-START interval semantics, no fallback, explicit
    `calculation_version`, missing rows preserved as absence rather than
    fabricated) is owned by `storage/v2_setup_readers.py`, not by this
    Protocol.

    `storage.db.Database` matches this shape structurally today (its
    Stage 5 `fetch_v2_*` methods plus the Stage 3
    `fetch_v2_reference_klines` it already had); this Protocol does not
    import or reference that class, so a caller depending on
    `V2SetupHistoryReader` never needs to import `storage/db.py`."""

    async def fetch_v2_consensus_feature_window(
        self, *, symbol: str, market_type: str, timeframe: str,
        bucket_start: datetime, bucket_end: datetime, calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        ...

    async def fetch_v2_consensus_percentile_window(
        self, *, symbol: str, market_type: str, metric: str, timeframe: str,
        percentile_window: str, bucket_start: datetime, bucket_end: datetime,
        calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        ...

    async def fetch_v2_reference_feature_window(
        self, *, exchange: str, symbol: str, market_type: str, timeframe: str,
        bucket_start: datetime, bucket_end: datetime, calculation_version: str,
    ) -> "tuple[Mapping, ...]":
        ...

    async def fetch_v2_reference_klines(
        self, *, exchange: str, symbol: str, bucket_start: datetime, bucket_end: datetime,
    ) -> "tuple[Mapping, ...]":
        ...

    async def fetch_v2_instrument(
        self, *, exchange: str, symbol: str, market_type: str,
    ) -> Optional[Mapping]:
        ...


@runtime_checkable
class V2VersionDrainStatusReader(Protocol):
    """Structural port for the ONE fact V2-H2b's orchestration layer
    (`version_switch_orchestrator.py`) needs while a version switch is
    `DRAINING`: OLD's non-terminal-episode/active-cooldown population,
    scoped to exactly one `execution_stream` and exactly the OLD semantic
    tuple (`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3.1/§12.10).

    No concrete implementation of this Protocol exists in this codebase
    today — Stage 6 (the episode state machine that would own a real
    `v2_episode_events`-backed count of non-terminal episodes and active
    same-slot cooldowns) has deliberately NOT been implemented as part of
    V2-H2b (out of scope by explicit task instruction; see
    `analytics/forecasting_v2/version_switch.py`'s module docstring). Only
    deterministic test fakes satisfy this Protocol for now. Wiring a real
    `storage.db.Database`-backed implementation is future Stage-6-adjacent
    work, not this PR's job — this Protocol exists so V2-H2b's
    orchestration boundary and its tests can be written and proven correct
    against the exact fact shape the pure state machine
    (`version_switch.py`'s `V2DrainFact`) needs, without inventing a real
    query against a table this repository does not yet populate."""

    async def fetch_v2_version_drain_status(
        self, *, run_kind: str, run_id: str, rules_version: str,
        calculation_version: str, decision_code_version: str, as_of: datetime,
    ) -> "V2DrainFact":
        ...
