"""Real-PostgreSQL proof of Stage 6 Unit 1's persisted-history read
foundation (`storage/v2_episode_history_readers.py` +
`Database.fetch_v2_episode_history`, `docs/
V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §12.10/§13.4/§2.1a).

Deliberately a REAL PostgreSQL suite, not a FakeConn one: the whole point
is genuine SQL scoping/ordering/`as_of` behavior and genuine
`execution_stream` isolation, none of which a mocked connection can prove.

Mirrors `tests/storage/test_v2_episode_event_transactions.py`'s established
pattern exactly — per-test uniquely-named schema, one `asyncio.run()` per
test, and the same `V2_EPISODE_EVENT_TEST_DSN` fail-vs-skip contract (unset
-> best-effort SKIP on connection failure; explicitly set, as CI does -> a
connection/setup failure is a genuine FAILURE, never a silent skip). The
table DDL is imported from that suite rather than hand-copied a second
time.

Every row is written through the REAL writer
(`Database.insert_v2_episode_events`) with events built by the REAL
canonical factory (`build_v2_episode_event`) — never a hand-assembled
`V2EpisodeEvent` and never a raw INSERT — so what this suite reads back is
exactly what a real Stage 6 writer would have persisted.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2.episode_history import (
    HISTORY_BEFORE_T, HISTORY_THROUGH_T, V2EpisodeHistoryCorruptionError,
    V2EpisodeHistoryError, build_confirmed_breakout_anchor,
    build_trend_pullback_anchor, reconstruct_episode_history,
)
from analytics.forecasting_v2.event_factory import build_v2_episode_event
from analytics.forecasting_v2.events import (
    COMPLETED, CONFIRMED, CONFIRMED_BREAKOUT, EARLY_SIGNAL, INVALIDATED, LIVE,
    LONG, REPLAY, TREND_PULLBACK, WEAKENING,
)
from analytics.forecasting_v2.provenance import V2EventProvenance
from common.v2_config import MODEL_FAMILY
from storage.db import Database
from storage.v2_episode_history_readers import (
    EPISODE_HISTORY_COLUMNS, V2EpisodeHistoryReaderError, read_v2_episode_history,
)
from tests.storage.test_v2_episode_event_transactions import (
    _run as _run_with_events_table,
)

UTC = timezone.utc
T0 = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)     # legal 5m boundary
H64 = "a" * 64
H16 = "b" * 16
LIVE_RUN = "live-stream-1"
REPLAY_RUN = "replay-run-1"


def _t(n: int) -> datetime:
    return T0 + timedelta(minutes=5 * n)


def _q(n: int) -> datetime:
    """A legal 15m bucket START (family anchors live on the 15m grid)."""
    return T0 + timedelta(minutes=15 * n)


def _run(body):
    """One isolated schema containing exactly one `v2_episode_events`
    table, reusing the transaction suite's fixture verbatim."""
    _run_with_events_table(body)


def _provenance(*, run_kind=LIVE, run_id=LIVE_RUN, **over) -> V2EventProvenance:
    base = dict(
        run_kind=run_kind, run_id=run_id, model_family=MODEL_FAMILY,
        rules_version="v2-rules-v0.1.0", symbol="BTCUSDT", market_type="perp",
        feature_schema_version=1, calculation_version=H16, config_hash=H64,
        config_version="2.1.0", code_version="feat-code-1",
        decision_code_version="decision-code-1",
    )
    base.update(over)
    return V2EventProvenance(**base)


TP_ANCHOR = build_trend_pullback_anchor(bucket_ts=T0)


def make_event(*, t_create=T0, decision_boundary=None, episode_state=EARLY_SIGNAL,
               direction=LONG, setup_family=TREND_PULLBACK, structural_anchor=None,
               provenance=None):
    return build_v2_episode_event(
        provenance if provenance is not None else _provenance(),
        t_create=t_create,
        direction=direction,
        setup_family=setup_family,
        structural_anchor=TP_ANCHOR if structural_anchor is None else structural_anchor,
        episode_state=episode_state,
        decision_boundary=t_create if decision_boundary is None else decision_boundary,
        decision_snapshot={"consensus_confidence": 87.5},
        event_payload={"entry_zone": {"low": 64500.0, "high": 65000.0}},
    )


async def _seed(db, events):
    """Persist events through the REAL writer, ONE logical decision
    boundary per call — `insert_v2_episode_events` enforces §2.1a's
    "one call must persist exactly one logical decision boundary's events"
    batch-scope rule, so a multi-boundary history is necessarily written as
    several successive publications, exactly as a real Stage 6 runtime
    would write it."""
    for event in events:
        await db.insert_v2_episode_events([event])


def _lifecycle(*, provenance=None, states=((0, EARLY_SIGNAL), (1, CONFIRMED), (2, COMPLETED))):
    """One episode's canonical multi-boundary history."""
    return [
        make_event(decision_boundary=_t(n), episode_state=state, provenance=provenance)
        for n, state in states
    ]


# ============================================================================
# 1. basic read: ordering, column surface, immutability
# ============================================================================
def test_history_is_returned_oldest_first_with_the_full_column_surface():
    async def body(db, _dsn):
        events = _lifecycle()
        await _seed(db, events)
        rows = await db.fetch_v2_episode_history(
            run_kind=LIVE, run_id=LIVE_RUN, episode_id=events[0].episode_id,
            as_of=_t(50), boundary_mode=HISTORY_THROUGH_T)

        assert [r["decision_boundary"] for r in rows] == [_t(0), _t(1), _t(2)]
        assert [r["episode_state"] for r in rows] == [EARLY_SIGNAL, CONFIRMED, COMPLETED]
        assert set(rows[0].keys()) == set(EPISODE_HISTORY_COLUMNS)
        # created_at is DB-owned wall-clock metadata and must never surface
        assert "created_at" not in rows[0]

    _run(body)


def test_returned_rows_and_their_jsonb_are_deeply_immutable():
    async def body(db, _dsn):
        events = _lifecycle()
        await _seed(db, events)
        rows = await db.fetch_v2_episode_history(
            run_kind=LIVE, run_id=LIVE_RUN, episode_id=events[0].episode_id,
            as_of=_t(50), boundary_mode=HISTORY_THROUGH_T)

        with pytest.raises(TypeError):
            rows[0]["episode_state"] = "tampered"
        with pytest.raises(TypeError):
            rows[0]["event_payload"]["entry_zone"] = "tampered"
        with pytest.raises(TypeError):
            rows[0]["event_payload"]["entry_zone"]["low"] = 0.0
        assert isinstance(rows, tuple)

    _run(body)


def test_insertion_order_does_not_determine_read_order():
    """DB natural/heap order is never the contract: seed newest-first and
    still read oldest-first."""
    async def body(db, _dsn):
        events = _lifecycle()
        await _seed(db, list(reversed(events)))
        rows = await db.fetch_v2_episode_history(
            run_kind=LIVE, run_id=LIVE_RUN, episode_id=events[0].episode_id,
            as_of=_t(50), boundary_mode=HISTORY_THROUGH_T)
        assert [r["decision_boundary"] for r in rows] == [_t(0), _t(1), _t(2)]

    _run(body)


# ============================================================================
# 2. as-of cutoff + §13.4's two frozen same-T windows
# ============================================================================
def test_as_of_returns_the_correct_prefix_and_never_a_future_event():
    async def body(db, _dsn):
        events = _lifecycle()
        await _seed(db, events)
        for n, expected in [(0, 1), (1, 2), (2, 3), (3, 3)]:
            rows = await db.fetch_v2_episode_history(
                run_kind=LIVE, run_id=LIVE_RUN, episode_id=events[0].episode_id,
                as_of=_t(n), boundary_mode=HISTORY_THROUGH_T)
            assert len(rows) == expected
            assert all(r["decision_boundary"] <= _t(n) for r in rows)

    _run(body)


def test_before_t_excludes_the_exact_boundary_through_t_includes_it():
    """§13.4: step 1 wants strictly-before-T; step 3b's cooldown lookup
    explicitly includes an episode that became terminal at this very T."""
    async def body(db, _dsn):
        events = _lifecycle(states=((0, EARLY_SIGNAL), (1, CONFIRMED), (2, INVALIDATED)))
        await _seed(db, events)
        episode_id = events[0].episode_id

        before = await db.fetch_v2_episode_history(
            run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
            as_of=_t(2), boundary_mode=HISTORY_BEFORE_T)
        through = await db.fetch_v2_episode_history(
            run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
            as_of=_t(2), boundary_mode=HISTORY_THROUGH_T)

        assert [r["decision_boundary"] for r in before] == [_t(0), _t(1)]
        assert [r["decision_boundary"] for r in through] == [_t(0), _t(1), _t(2)]
        # the same-T terminal event is invisible to step 1 and visible to 3b
        assert before[-1]["episode_state"] == CONFIRMED
        assert through[-1]["episode_state"] == INVALIDATED

    _run(body)


def test_boundary_mode_is_required_and_validated():
    async def body(db, _dsn):
        with pytest.raises(TypeError):
            await db.fetch_v2_episode_history(
                run_kind=LIVE, run_id=LIVE_RUN, episode_id="a" * 64, as_of=T0)
        with pytest.raises(V2EpisodeHistoryError):
            await db.fetch_v2_episode_history(
                run_kind=LIVE, run_id=LIVE_RUN, episode_id="a" * 64,
                as_of=T0, boundary_mode="LATEST")

    _run(body)


def test_reader_validates_scope_before_touching_the_connection():
    """A malformed scope must fail before any SQL is issued."""
    class _PoisonConn:
        def __getattr__(self, name):
            raise AssertionError(f"reader must not touch the connection ({name!r})")

    async def body():
        for kwargs in (
            dict(run_kind="NOPE", run_id=LIVE_RUN, episode_id="a" * 64,
                 as_of=T0, boundary_mode=HISTORY_THROUGH_T),
            dict(run_kind=LIVE, run_id="  ", episode_id="a" * 64,
                 as_of=T0, boundary_mode=HISTORY_THROUGH_T),
            dict(run_kind=LIVE, run_id=LIVE_RUN, episode_id="not-a-hash",
                 as_of=T0, boundary_mode=HISTORY_THROUGH_T),
            dict(run_kind=LIVE, run_id=LIVE_RUN, episode_id="a" * 64,
                 as_of=datetime(2026, 8, 20, 12, 0), boundary_mode=HISTORY_THROUGH_T),
            dict(run_kind=LIVE, run_id=LIVE_RUN, episode_id="a" * 64,
                 as_of=T0, boundary_mode="LATEST"),
        ):
            with pytest.raises(V2EpisodeHistoryError):
                await read_v2_episode_history(_PoisonConn(), **kwargs)

    asyncio.run(body())


# ============================================================================
# 3. §12.10 execution-namespace physical isolation
# ============================================================================
def test_live_and_replay_share_the_semantic_id_but_never_the_history():
    """Semantic IDs coincide across streams BY DESIGN (`episode_id`
    excludes run_kind/run_id); the physical histories must not."""
    async def body(db, _dsn):
        live = _lifecycle(provenance=_provenance(run_kind=LIVE, run_id=LIVE_RUN))
        replay = _lifecycle(
            provenance=_provenance(run_kind=REPLAY, run_id=REPLAY_RUN),
            states=((0, EARLY_SIGNAL), (1, WEAKENING)))
        episode_id = live[0].episode_id
        assert replay[0].episode_id == episode_id      # same semantic identity
        await _seed(db, live)
        await _seed(db, replay)

        live_rows = await db.fetch_v2_episode_history(
            run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
            as_of=_t(50), boundary_mode=HISTORY_THROUGH_T)
        replay_rows = await db.fetch_v2_episode_history(
            run_kind=REPLAY, run_id=REPLAY_RUN, episode_id=episode_id,
            as_of=_t(50), boundary_mode=HISTORY_THROUGH_T)

        assert [r["episode_state"] for r in live_rows] == [EARLY_SIGNAL, CONFIRMED, COMPLETED]
        assert [r["episode_state"] for r in replay_rows] == [EARLY_SIGNAL, WEAKENING]
        assert all(r["run_kind"] == LIVE for r in live_rows)
        assert all(r["run_kind"] == REPLAY for r in replay_rows)

    _run(body)


def test_two_replay_run_ids_are_isolated_from_each_other():
    async def body(db, _dsn):
        a = _lifecycle(provenance=_provenance(run_kind=REPLAY, run_id="replay-A"))
        b = _lifecycle(provenance=_provenance(run_kind=REPLAY, run_id="replay-B"),
                       states=((0, EARLY_SIGNAL),))
        await _seed(db, a)
        await _seed(db, b)
        episode_id = a[0].episode_id

        rows_b = await db.fetch_v2_episode_history(
            run_kind=REPLAY, run_id="replay-B", episode_id=episode_id,
            as_of=_t(50), boundary_mode=HISTORY_THROUGH_T)
        assert len(rows_b) == 1
        assert all(r["run_id"] == "replay-B" for r in rows_b)

    _run(body)


def test_unknown_stream_or_episode_reads_empty_not_an_error():
    async def body(db, _dsn):
        await _seed(db, _lifecycle())
        for kwargs in (
            dict(run_kind=REPLAY, run_id="never-ran"),
            dict(run_kind=LIVE, run_id="other-live-stream"),
        ):
            rows = await db.fetch_v2_episode_history(
                episode_id=_lifecycle()[0].episode_id, as_of=_t(50),
                boundary_mode=HISTORY_THROUGH_T, **kwargs)
            assert rows == ()

        rows = await db.fetch_v2_episode_history(
            run_kind=LIVE, run_id=LIVE_RUN, episode_id="c" * 64,
            as_of=_t(50), boundary_mode=HISTORY_THROUGH_T)
        assert rows == ()

    _run(body)


def test_other_episodes_in_the_same_stream_do_not_leak_in():
    async def body(db, _dsn):
        first = _lifecycle()
        second = [make_event(
            t_create=_t(4), decision_boundary=_t(4),
            structural_anchor=build_trend_pullback_anchor(bucket_ts=_q(4)))]
        await _seed(db, first)
        await _seed(db, second)
        assert first[0].episode_id != second[0].episode_id

        rows = await db.fetch_v2_episode_history(
            run_kind=LIVE, run_id=LIVE_RUN, episode_id=first[0].episode_id,
            as_of=_t(50), boundary_mode=HISTORY_THROUGH_T)
        assert len(rows) == 3
        assert all(r["episode_id"] == first[0].episode_id for r in rows)

    _run(body)


# ============================================================================
# 4. THE restart vector: a fresh process reconstructs from persisted history
# ============================================================================
def test_restart_reconstructs_creation_identity_from_persisted_history_alone():
    """Process A persists a creation event plus later events, then
    disappears. Process B has NO process-local episode state, no detector
    candidate, no instrument metadata and no wall clock — it reads the
    persisted history at T and must recover the identical immutable
    creation identity and the correct current lifecycle position."""
    async def body(db_a, scoped_dsn):
        events = _lifecycle(states=((0, EARLY_SIGNAL), (2, CONFIRMED), (5, WEAKENING)))
        await _seed(db_a, events)
        episode_id = events[0].episode_id
        await db_a.close()                       # process A disappears

        db_b = Database(scoped_dsn)              # genuinely fresh pool/process
        await db_b.connect()
        try:
            rows = await db_b.fetch_v2_episode_history(
                run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
                as_of=_t(5), boundary_mode=HISTORY_THROUGH_T)
            history = reconstruct_episode_history(
                rows, run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
                as_of=_t(5), boundary_mode=HISTORY_THROUGH_T)
        finally:
            await db_b.close()
        # reopen so the fixture's own close/teardown stays valid
        await db_a.connect()

        identity = history.creation_identity
        assert identity.episode_id == episode_id
        assert identity.t_create == T0
        assert identity.direction == LONG
        assert identity.setup_family == TREND_PULLBACK
        assert dict(identity.structural_anchor) == dict(TP_ANCHOR)
        assert identity.slot == ("BTCUSDT", "perp", LONG, TREND_PULLBACK)
        assert history.current_state == WEAKENING
        assert history.is_terminal is False
        assert history.creation_event.decision_boundary == T0
        assert len(history.events) == 3

    _run(body)


def test_restart_reconstruction_is_identical_across_as_of_snapshots():
    async def body(db, _dsn):
        events = _lifecycle(states=((0, EARLY_SIGNAL), (1, CONFIRMED), (2, COMPLETED)))
        await _seed(db, events)
        episode_id = events[0].episode_id

        seen = []
        for n, expected_state in [(0, EARLY_SIGNAL), (1, CONFIRMED), (2, COMPLETED)]:
            rows = await db.fetch_v2_episode_history(
                run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
                as_of=_t(n), boundary_mode=HISTORY_THROUGH_T)
            history = reconstruct_episode_history(
                rows, run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
                as_of=_t(n), boundary_mode=HISTORY_THROUGH_T)
            assert history.current_state == expected_state
            assert len(history.events) == n + 1
            seen.append(history.creation_identity)

        assert all(i == seen[0] for i in seen)
        assert seen[-1].t_create == T0

    _run(body)


# ============================================================================
# 5. CONFIRMED_BREAKOUT creation tick grid survives a real round trip (§12.5a)
# ============================================================================
def test_confirmed_breakout_creation_tick_grid_round_trips_through_postgres():
    """The creation grid must survive JSONB persistence losslessly and be
    reconstructable after restart WITHOUT re-reading instrument metadata —
    even though today's tick_size is finer."""
    from decimal import Decimal

    async def body(db, scoped_dsn):
        anchor = build_confirmed_breakout_anchor(
            level_anchor_bucket=T0, raw_level_price=66200.04,
            creation_identity_tick_size=0.1)
        events = [
            make_event(setup_family=CONFIRMED_BREAKOUT, structural_anchor=anchor),
            make_event(decision_boundary=_t(3), episode_state=CONFIRMED,
                       setup_family=CONFIRMED_BREAKOUT, structural_anchor=anchor),
        ]
        await _seed(db, events)
        episode_id = events[0].episode_id
        await db.close()

        db_b = Database(scoped_dsn)
        await db_b.connect()
        try:
            rows = await db_b.fetch_v2_episode_history(
                run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
                as_of=_t(3), boundary_mode=HISTORY_THROUGH_T)
            identity = reconstruct_episode_history(
                rows, run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
                as_of=_t(3), boundary_mode=HISTORY_THROUGH_T).creation_identity
        finally:
            await db_b.close()
        await db.connect()

        assert identity.creation_identity_tick_size == Decimal("0.1")
        assert identity.creation_level_tick_index == 662000
        assert identity.creation_normalized_level_price == Decimal("66200.0")
        # persisted losslessly as exact strings/ints, never JSON floats
        raw_anchor = rows[0]["structural_anchor"]
        assert raw_anchor["creation_identity_tick_size"] == "0.1"
        assert raw_anchor["level_normalized_price"] == "66200"   # canonical plain decimal
        assert raw_anchor["level_tick_index"] == 662000

    _run(body)


# ============================================================================
# 6. corrupt persisted history the DB itself cannot prevent
# ============================================================================
def test_creation_identity_drift_written_directly_is_rejected_on_read():
    """The DB has no cross-row CHECK that an episode's frozen creation
    facts stay constant, so this corruption is genuinely reachable — and
    must fail closed at reconstruction, never be silently accepted."""
    async def body(db, _dsn):
        events = _lifecycle(states=((0, EARLY_SIGNAL), (1, CONFIRMED)))
        await _seed(db, events)
        episode_id = events[0].episode_id
        async with db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE v2_episode_events SET direction = 'SHORT' "
                "WHERE episode_id = $1 AND decision_boundary = $2",
                episode_id, _t(1))

        rows = await db.fetch_v2_episode_history(
            run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
            as_of=_t(9), boundary_mode=HISTORY_THROUGH_T)
        assert len(rows) == 2                      # the read itself still works
        with pytest.raises(V2EpisodeHistoryCorruptionError, match="direction"):
            reconstruct_episode_history(
                rows, run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
                as_of=_t(9), boundary_mode=HISTORY_THROUGH_T)

    _run(body)


def test_history_without_a_creation_event_is_rejected_on_read():
    async def body(db, _dsn):
        events = _lifecycle(states=((0, EARLY_SIGNAL), (1, CONFIRMED)))
        await _seed(db, events)
        episode_id = events[0].episode_id
        async with db.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM v2_episode_events WHERE episode_id = $1 AND decision_boundary = $2",
                episode_id, _t(0))

        rows = await db.fetch_v2_episode_history(
            run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
            as_of=_t(9), boundary_mode=HISTORY_THROUGH_T)
        with pytest.raises(V2EpisodeHistoryCorruptionError, match="oldest persisted event"):
            reconstruct_episode_history(
                rows, run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
                as_of=_t(9), boundary_mode=HISTORY_THROUGH_T)

    _run(body)


def test_malformed_structural_anchor_json_is_rejected_by_the_reader():
    """A JSONB value that is a valid JSON scalar but not an object is
    blocked by the DB's own CHECK; an object whose *shape* is wrong reaches
    the reader, which must still hand back something the domain layer
    rejects rather than silently coercing it."""
    async def body(db, _dsn):
        events = _lifecycle(states=((0, EARLY_SIGNAL),))
        await _seed(db, events)
        episode_id = events[0].episode_id
        async with db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE v2_episode_events SET structural_anchor = '{\"bucket_ts\": 12345}'::jsonb "
                "WHERE episode_id = $1", episode_id)

        rows = await db.fetch_v2_episode_history(
            run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
            as_of=_t(9), boundary_mode=HISTORY_THROUGH_T)
        # the anchor no longer reproduces the persisted episode_id
        with pytest.raises(V2EpisodeHistoryCorruptionError):
            reconstruct_episode_history(
                rows, run_kind=LIVE, run_id=LIVE_RUN, episode_id=episode_id,
                as_of=_t(9), boundary_mode=HISTORY_THROUGH_T)

    _run(body)


def test_reader_rejects_a_row_missing_a_selected_column():
    """A connection returning an under-populated record must fail closed
    rather than silently yielding a partial row."""
    class _ShortRowConn:
        async def fetch(self, *args):
            return [{"run_kind": LIVE, "run_id": LIVE_RUN}]

    async def body():
        with pytest.raises(V2EpisodeHistoryReaderError, match="missing selected column"):
            await read_v2_episode_history(
                _ShortRowConn(), run_kind=LIVE, run_id=LIVE_RUN, episode_id="a" * 64,
                as_of=T0, boundary_mode=HISTORY_THROUGH_T)

    asyncio.run(body())
