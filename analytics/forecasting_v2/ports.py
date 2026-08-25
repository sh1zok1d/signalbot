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
    `V2SetupHistoryReader` method, and vice versa. `fetch_v2_instrument`
    requires an explicit `as_of` (V2-H2c,
    `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §12.5a): it resolves the
    `exchange_instrument_history` version actually in effect at `as_of`,
    never the current `exchange_instruments` LKG row and never a future
    version — see `storage/v2_setup_readers.py::read_v2_instrument`'s own
    docstring for the exact interval semantics this method's
    implementation encodes.
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
this module only names the narrow slices of `Database`'s surface a
future V2 caller is allowed to depend on; it does not itself wire
anything. (V2-H2c changed `Database.fetch_v2_instrument`'s own signature
to require `as_of`, matching this Protocol's method exactly — this
module's own definition of the method is what changed here, not an
independent edit to `Database` that this Protocol merely happens to
describe.) The fourth Protocol,
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
    "V2VersionDrainStatusReader", "V2EpisodeHistoryReader",
    "V2EpisodeSlotReader",
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
    exists), and an as-of `exchange_instrument_history` lookup (V2-H2c)
    for `protection_buffer()`'s `tick_size` input. Every method's contract
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
        self, *, exchange: str, symbol: str, market_type: str, as_of: datetime,
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
    query against a table this repository does not yet populate.

    **Stage 6 Unit 1 analysis (deliberately still NOT implemented here).**
    Unit 1 added the persisted-history read foundation
    (`episode_history.py`/`storage/v2_episode_history_readers.py`) this
    Protocol would be built on, and re-examined whether a concrete
    implementation could land with it. It cannot, without inventing
    contract that is not frozen anywhere:

      - **Episode-to-tuple attribution is undefined when
        `decision_code_version` varies within one episode.** This Protocol
        is scoped by the full OLD semantic tuple *including*
        `decision_code_version` (§3.1), but `episode_id` deliberately
        EXCLUDES it (§2.1a) precisely so a Stage 6 bug-fix release does not
        fork an episode's identity — so one episode's events may legally
        carry different `decision_code_version` values. Whether such an
        episode counts toward OLD's population by its creation event, its
        latest event, or not at all is not frozen.
      - **`active_cooldown_count` requires per-slot aggregation this unit
        does not build.** The granularity itself is NOT undefined — §12.8 is
        explicit that "cooldown scope remains the `slot` — `(symbol,
        market_type, direction, setup_family)`", so the count is DISTINCT
        SLOTS still inside a cooldown window, never one per terminal
        episode. What is missing is the machinery: computing it means
        grouping every terminal episode in the stream by slot, taking each
        slot's MOST RECENT terminal episode and its `T_terminal` (§13.4 step
        3b), and comparing against `as_of`. That is exactly the per-slot
        terminal/cooldown aggregation Stage 6 Unit 2 builds for creation
        eligibility, and Unit 1 is a single-episode read foundation with no
        cross-episode aggregation surface at all.

    **Stage 6 Unit 2 re-examination — gap 2 CLOSED, gap 1 still blocks.**
    Unit 2 built the missing per-slot substrate: `V2EpisodeSlotReader`
    below now answers, per `execution_stream` and slot, every episode's
    latest persisted state and the slot's most recent terminal
    fact/`T_terminal` as of `T`, and `episode_creation.py` owns §12.8's
    exact cooldown clock. Counting OLD's non-terminal episodes and its
    DISTINCT active-cooldown slots is therefore now mechanically possible,
    so gap 2 is no longer a blocker.

    Gap 1 was, until Stage 6 Unit 3, the remaining blocker: §3.1 said "Old-
    version episodes continue under their ORIGINAL, frozen semantic tuple"
    without a mechanical definition of which event fixes that tuple, while
    §2.1a deliberately excludes `decision_code_version` from `episode_id`
    so a Stage 6 bug-fix release does not fork an episode's identity — which
    left it arguable that one episode's events could legally carry
    different `decision_code_version` values. Nothing frozen resolved which
    reading governed when counting an episode against a tuple that
    INCLUDES `decision_code_version`.

    **Stage 6 Unit 3 — gap 1 SEMANTICALLY CLOSED; the concrete
    implementation is still deliberately deferred.** An independent
    red-team of Unit 3 forced that ambiguity to be resolved rather than
    worked around, and §3.1 now freezes the attribution rule explicitly:

        An episode is attributed to the semantic tuple recorded by its
        CREATION event, and EVERY later lifecycle transition through its
        terminal state continues under that same creation tuple —
        `decision_code_version` included. A decision-code-only release
        therefore does not fork `episode_id` (§2.1a, unchanged) AND may not
        reinterpret an already-existing episode (§3.1).

    So the counting rule this Protocol needed is no longer undefined: an
    episode counts against the tuple its own creation event records, and
    against no other; `episode_lifecycle.py` enforces the same rule on the
    write side, refusing a lifecycle event whose `decision_code_version`
    differs from the creation event's. Both remaining pieces — the per-slot
    cooldown substrate (gap 2, Unit 2) and the attribution rule (gap 1,
    Unit 3) — now exist.

    What is still absent is only the concrete
    `storage.db.Database`-backed query and its real-PostgreSQL proof. That
    is deliberately NOT written here: Unit 3 owns lifecycle transitions and
    does not consume drain status at all (§3.1 requires an existing episode
    to keep transitioning THROUGHOUT a drain, so no Unit 3 decision is
    drain-gated), and implementing an unused reader would ship an
    unexercised production query on a table this repository does not yet
    populate. It belongs with the unit that actually consumes it.

    A wrong answer changes the DRAIN decision itself, not merely its
    reported numbers. A deliberately WRONG placeholder (notably
    `non_terminal = count(latest state non-terminal)` with
    `active_cooldowns = 0`, which would let a switch ACTIVATE while a real
    same-slot cooldown is still running) is worse than no implementation: a
    version switch must fail closed, never optimistically."""

    async def fetch_v2_version_drain_status(
        self, *, run_kind: str, run_id: str, rules_version: str,
        calculation_version: str, decision_code_version: str, as_of: datetime,
    ) -> "V2DrainFact":
        ...


@runtime_checkable
class V2EpisodeHistoryReader(Protocol):
    """Structural port for Stage 6 Unit 1's persisted-history read
    foundation (`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §12.10/§13.4):
    one existing episode's already-persisted `v2_episode_events` rows,
    physically scoped to exactly one `execution_stream` and bounded by
    exactly one logical decision boundary.

    Satisfied structurally by `storage.db.Database`
    (`fetch_v2_episode_history`) exactly as the three Protocols above are —
    this Protocol does not import or reference that class, so a
    deterministic analytics test fake satisfies it without any storage
    import.

    `run_kind`/`run_id` are BOTH required and are never optional: §12.10
    forbids mixing `LIVE` with `REPLAY` history, or one `REPLAY` `run_id`'s
    history with another's, and semantic `episode_id`s are deliberately
    designed to coincide across streams. `boundary_mode` selects between
    §13.4's two frozen same-`T` windows (`HISTORY_BEFORE_T` /
    `HISTORY_THROUGH_T`, `analytics/forecasting_v2/episode_history.py`) and
    has no default. Rows come back oldest-first; interpreting them is
    `reconstruct_episode_history()`'s job, never this port's."""

    async def fetch_v2_episode_history(
        self, *, run_kind: str, run_id: str, episode_id: str,
        as_of: datetime, boundary_mode: str,
    ) -> "Sequence[Mapping]":
        ...


@runtime_checkable
class V2EpisodeSlotReader(Protocol):
    """Structural port for Stage 6 Unit 2's per-slot episode facts
    (`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §12.6/§12.8/§12.10/§13.4).

    Unit 1's `V2EpisodeHistoryReader` answers "one episode's history by
    `episode_id`". Unit 2's eligibility rules ask a slot-shaped question of
    the same immutable event log: which episodes exist in one `slot`
    (`(symbol, market_type, direction, setup_family)`), what state is each
    one in as of `T`, and which terminal one is the most recent.

    Satisfied structurally by `storage.db.Database`
    (`fetch_v2_slot_episode_states` / `fetch_v2_slot_latest_terminal`), the
    same way the four Protocols above are — this Protocol imports nothing
    from storage, so a deterministic analytics test fake satisfies it with
    no storage import at all.

    `run_kind`/`run_id` are BOTH required (§12.10: semantic `episode_id`s
    are designed to coincide across streams, so a slot read MUST be
    physically namespaced or one stream's active episode would suppress
    another's). `boundary_mode` selects between §13.4's two frozen same-`T`
    windows and has no default: step 1's "ACTIVE immediately before `T`"
    and step 3b's cooldown lookup (which includes an episode that became
    terminal at this very `T`) are genuinely different windows.

    **This port DISCOVERS episodes; it does not certify them.** What it
    returns is a projection of persisted rows, not proof that the episodes
    behind them have valid histories. A trusted §12.8 cooldown fact is
    built in the analytics layer from a history reconstructed through
    `V2EpisodeHistoryReader` + `reconstruct_episode_history()`
    (`episode_creation.V2SlotTerminalFact` accepts nothing else), so an
    impossible persisted lifecycle cannot suppress creation merely because
    its newest row happens to read as terminal."""

    async def fetch_v2_slot_episode_states(
        self, *, run_kind: str, run_id: str, symbol: str, market_type: str,
        direction: str, setup_family: str, as_of: datetime, boundary_mode: str,
    ) -> "Sequence[Mapping]":
        ...

    async def fetch_v2_slot_latest_terminal(
        self, *, run_kind: str, run_id: str, symbol: str, market_type: str,
        direction: str, setup_family: str, as_of: datetime, boundary_mode: str,
    ) -> "Optional[Mapping]":
        ...
