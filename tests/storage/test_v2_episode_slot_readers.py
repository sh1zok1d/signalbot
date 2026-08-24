"""Real-PostgreSQL proof of Stage 6 Unit 2's per-slot episode fact reads
(`storage/v2_episode_slot_readers.py` + `Database.fetch_v2_slot_*`,
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §12.6/§12.8/§12.10/§13.4).

Deliberately a REAL PostgreSQL suite: the whole point is genuine SQL slot
filtering, `DISTINCT ON` latest-state resolution, `as_of` cutoffs and
`execution_stream` isolation, none of which a mocked connection proves.

Reuses `tests/storage/test_v2_episode_event_transactions.py`'s established
fixture (per-test uniquely-named schema, one `asyncio.run()` per test, the
same `V2_EPISODE_EVENT_TEST_DSN` fail-vs-skip contract) rather than
hand-copying the DDL a third time. Every row is written through the REAL
writer with events built by the REAL canonical factory.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2.episode_history import (
    HISTORY_BEFORE_T, HISTORY_THROUGH_T, V2EpisodeHistoryError,
    build_trend_pullback_anchor,
)
from analytics.forecasting_v2.episode_identity import compute_event_id
from analytics.forecasting_v2.event_factory import build_v2_episode_event
from analytics.forecasting_v2.events import (
    COMPLETED, COMPRESSION_BREAKOUT, CONFIRMED, EARLY_SIGNAL, EXPIRED,
    INVALIDATED, LIVE, LONG, REPLAY, SHORT, TREND_PULLBACK, WEAKENING,
)
from analytics.forecasting_v2.provenance import V2EventProvenance
from common.v2_config import MODEL_FAMILY
from storage.db import Database
from storage.v2_episode_slot_readers import (
    SLOT_STATE_COLUMNS, V2EpisodeSlotReaderError, read_v2_slot_episode_states,
)
from tests.storage.test_v2_episode_event_transactions import (
    _run as _run_with_events_table,
)

UTC = timezone.utc
T0 = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
H64 = "a" * 64
H16 = "b" * 16
LIVE_RUN = "live-stream-1"
SYMBOL, MARKET = "BTCUSDT", "perp"


def _t(n: int) -> datetime:
    return T0 + timedelta(minutes=5 * n)


def _q(n: int) -> datetime:
    return T0 + timedelta(minutes=15 * n)


def _run(body):
    _run_with_events_table(body)


def _provenance(*, run_kind=LIVE, run_id=LIVE_RUN) -> V2EventProvenance:
    return V2EventProvenance(
        run_kind=run_kind, run_id=run_id, model_family=MODEL_FAMILY,
        rules_version="v2-rules-v0.1.0", symbol=SYMBOL, market_type=MARKET,
        feature_schema_version=1, calculation_version=H16, config_hash=H64,
        config_version="2.1.0", code_version="c", decision_code_version="d")


def make_event(*, t_create, decision_boundary=None, episode_state=EARLY_SIGNAL,
               direction=LONG, setup_family=TREND_PULLBACK, anchor_n=0,
               run_kind=LIVE, run_id=LIVE_RUN):
    return build_v2_episode_event(
        _provenance(run_kind=run_kind, run_id=run_id),
        t_create=t_create, direction=direction, setup_family=setup_family,
        structural_anchor=build_trend_pullback_anchor(bucket_ts=_q(anchor_n)),
        episode_state=episode_state,
        decision_boundary=t_create if decision_boundary is None else decision_boundary,
        decision_snapshot={"k": 1}, event_payload={"p": 2})


async def _seed(db, events):
    """One logical decision boundary per call — §2.1a's batch-scope rule."""
    for event in events:
        await db.insert_v2_episode_events([event])


async def _states(db, *, direction=LONG, setup_family=TREND_PULLBACK, as_of,
                  boundary_mode=HISTORY_THROUGH_T, run_kind=LIVE, run_id=LIVE_RUN):
    return await db.fetch_v2_slot_episode_states(
        run_kind=run_kind, run_id=run_id, symbol=SYMBOL, market_type=MARKET,
        direction=direction, setup_family=setup_family, as_of=as_of,
        boundary_mode=boundary_mode)


async def _latest_terminal(db, *, direction=LONG, setup_family=TREND_PULLBACK,
                           as_of, boundary_mode=HISTORY_THROUGH_T,
                           run_kind=LIVE, run_id=LIVE_RUN):
    return await db.fetch_v2_slot_latest_terminal(
        run_kind=run_kind, run_id=run_id, symbol=SYMBOL, market_type=MARKET,
        direction=direction, setup_family=setup_family, as_of=as_of,
        boundary_mode=boundary_mode)


def _lifecycle(*, t_create, anchor_n, states, run_kind=LIVE, run_id=LIVE_RUN,
               direction=LONG, setup_family=TREND_PULLBACK):
    """One episode's multi-boundary history: `states` is (offset, state)."""
    return [
        make_event(t_create=t_create, decision_boundary=_t(n), episode_state=s,
                   anchor_n=anchor_n, run_kind=run_kind, run_id=run_id,
                   direction=direction, setup_family=setup_family)
        for n, s in states
    ]


# ============================================================================
# 1. latest state per episode
# ============================================================================
def test_latest_state_per_episode_is_by_decision_boundary():
    async def body(db, _dsn):
        events = _lifecycle(
            t_create=T0, anchor_n=0,
            states=((0, EARLY_SIGNAL), (1, CONFIRMED), (2, WEAKENING)))
        await _seed(db, events)
        rows = await _states(db, as_of=_t(50))
        assert len(rows) == 1
        assert rows[0]["episode_state"] == WEAKENING
        assert rows[0]["decision_boundary"] == _t(2)
        assert rows[0]["episode_id"] == events[0].episode_id
        assert set(rows[0].keys()) == set(SLOT_STATE_COLUMNS)

    _run(body)


def test_insertion_order_does_not_decide_latest_state():
    """"Latest" is LOGICAL: seed newest-first and still resolve by
    `decision_boundary`, never by insertion/wall-clock order."""
    async def body(db, _dsn):
        events = _lifecycle(
            t_create=T0, anchor_n=0,
            states=((0, EARLY_SIGNAL), (1, CONFIRMED), (2, COMPLETED)))
        await _seed(db, list(reversed(events)))
        rows = await _states(db, as_of=_t(50))
        assert rows[0]["episode_state"] == COMPLETED
        assert rows[0]["decision_boundary"] == _t(2)

    _run(body)


def test_rows_are_ordered_deterministically_by_episode_id():
    async def body(db, _dsn):
        first = _lifecycle(t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL),))
        second = _lifecycle(t_create=_t(1), anchor_n=4, states=((1, EARLY_SIGNAL),))
        await _seed(db, first + second)
        rows = await _states(db, as_of=_t(50))
        assert [r["episode_id"] for r in rows] == sorted(r["episode_id"] for r in rows)

    _run(body)


# ============================================================================
# 2. as-of cutoff and §13.4's two windows
# ============================================================================
def test_as_of_returns_the_state_at_that_boundary_only():
    async def body(db, _dsn):
        await _seed(db, _lifecycle(
            t_create=T0, anchor_n=0,
            states=((0, EARLY_SIGNAL), (2, CONFIRMED), (4, INVALIDATED))))
        for n, expected in [(0, EARLY_SIGNAL), (1, EARLY_SIGNAL), (2, CONFIRMED),
                            (3, CONFIRMED), (4, INVALIDATED)]:
            rows = await _states(db, as_of=_t(n))
            assert rows[0]["episode_state"] == expected, f"at T+{5*n}m"

    _run(body)


def test_before_t_excludes_a_same_boundary_terminal_through_t_includes_it():
    """§13.4: step 1's window is strictly before `T`; step 3b's cooldown
    lookup includes an episode that became terminal at this very `T`."""
    async def body(db, _dsn):
        await _seed(db, _lifecycle(
            t_create=T0, anchor_n=0,
            states=((0, EARLY_SIGNAL), (1, CONFIRMED), (2, INVALIDATED))))

        before = await _states(db, as_of=_t(2), boundary_mode=HISTORY_BEFORE_T)
        through = await _states(db, as_of=_t(2), boundary_mode=HISTORY_THROUGH_T)
        assert before[0]["episode_state"] == CONFIRMED       # still ACTIVE for 3a
        assert through[0]["episode_state"] == INVALIDATED    # terminal for 3b

        assert await _latest_terminal(
            db, as_of=_t(2), boundary_mode=HISTORY_BEFORE_T) is None
        terminal = await _latest_terminal(
            db, as_of=_t(2), boundary_mode=HISTORY_THROUGH_T)
        assert terminal["episode_state"] == INVALIDATED
        assert terminal["decision_boundary"] == _t(2)        # T_terminal == T

    _run(body)


def test_no_future_event_leaks_backwards():
    async def body(db, _dsn):
        await _seed(db, _lifecycle(
            t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL), (5, INVALIDATED))))
        rows = await _states(db, as_of=_t(2))
        assert rows[0]["episode_state"] == EARLY_SIGNAL
        assert await _latest_terminal(db, as_of=_t(2)) is None

    _run(body)


# ============================================================================
# 3. §13.4 step 3b — most recent terminal per slot
# ============================================================================
def test_latest_terminal_is_the_newest_by_logical_boundary():
    async def body(db, _dsn):
        await _seed(db, _lifecycle(
            t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL), (1, EXPIRED))))
        await _seed(db, _lifecycle(
            t_create=_t(3), anchor_n=4, states=((3, EARLY_SIGNAL), (4, INVALIDATED))))

        terminal = await _latest_terminal(db, as_of=_t(50))
        assert terminal["episode_state"] == INVALIDATED
        assert terminal["decision_boundary"] == _t(4)

        # As of an earlier boundary, the older terminal is the answer.
        earlier = await _latest_terminal(db, as_of=_t(3))
        assert earlier["episode_state"] == EXPIRED
        assert earlier["decision_boundary"] == _t(1)

    _run(body)


def test_an_active_episode_is_never_reported_as_terminal():
    async def body(db, _dsn):
        await _seed(db, _lifecycle(
            t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL), (1, CONFIRMED))))
        assert await _latest_terminal(db, as_of=_t(50)) is None

    _run(body)


def test_slot_with_no_history_reads_empty():
    async def body(db, _dsn):
        await _seed(db, _lifecycle(t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL),)))
        assert await _states(db, direction=SHORT, as_of=_t(50)) == ()
        assert await _latest_terminal(db, direction=SHORT, as_of=_t(50)) is None

    _run(body)


# ============================================================================
# 4. slot filtering (§12.3's frozen slot)
# ============================================================================
def test_other_direction_and_family_do_not_leak_into_this_slot():
    async def body(db, _dsn):
        await _seed(db, _lifecycle(t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL),)))
        await _seed(db, _lifecycle(
            t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL),), direction=SHORT))
        await _seed(db, _lifecycle(
            t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL),),
            setup_family=COMPRESSION_BREAKOUT))

        long_tp = await _states(db, as_of=_t(50))
        assert len(long_tp) == 1
        assert len(await _states(db, direction=SHORT, as_of=_t(50))) == 1
        assert len(await _states(
            db, setup_family=COMPRESSION_BREAKOUT, as_of=_t(50))) == 1

    _run(body)


def test_two_episodes_in_one_slot_are_both_reported():
    """The reader reports the FACTS; §12.6's "at most one active" is an
    analytics invariant that fails closed there, never silently here."""
    async def body(db, _dsn):
        await _seed(db, _lifecycle(t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL),)))
        await _seed(db, _lifecycle(t_create=_t(1), anchor_n=8, states=((1, EARLY_SIGNAL),)))
        rows = await _states(db, as_of=_t(50))
        assert len(rows) == 2
        assert all(r["episode_state"] == EARLY_SIGNAL for r in rows)

    _run(body)


# ============================================================================
# 5. §12.10 execution-namespace isolation
# ============================================================================
def test_replay_history_never_reaches_the_live_slot_view():
    async def body(db, _dsn):
        live = _lifecycle(t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL),))
        replay = _lifecycle(
            t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL), (1, INVALIDATED)),
            run_kind=REPLAY, run_id="replay-b")
        assert live[0].episode_id == replay[0].episode_id     # same semantic identity
        await _seed(db, live)
        await _seed(db, replay)

        live_rows = await _states(db, as_of=_t(50))
        assert len(live_rows) == 1 and live_rows[0]["episode_state"] == EARLY_SIGNAL
        assert await _latest_terminal(db, as_of=_t(50)) is None      # LIVE has no terminal

        replay_terminal = await _latest_terminal(
            db, as_of=_t(50), run_kind=REPLAY, run_id="replay-b")
        assert replay_terminal["episode_state"] == INVALIDATED

    _run(body)


def test_two_replay_run_ids_are_isolated():
    async def body(db, _dsn):
        await _seed(db, _lifecycle(
            t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL), (1, EXPIRED)),
            run_kind=REPLAY, run_id="replay-A"))
        await _seed(db, _lifecycle(
            t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL),),
            run_kind=REPLAY, run_id="replay-B"))

        assert (await _latest_terminal(
            db, as_of=_t(50), run_kind=REPLAY, run_id="replay-A"))["episode_state"] == EXPIRED
        assert await _latest_terminal(
            db, as_of=_t(50), run_kind=REPLAY, run_id="replay-B") is None

    _run(body)


# ============================================================================
# 6. scope validation before any SQL
# ============================================================================
def test_reader_validates_scope_before_touching_the_connection():
    class _PoisonConn:
        def __getattr__(self, name):
            raise AssertionError(f"reader must not touch the connection ({name!r})")

    async def body():
        base = dict(
            run_kind=LIVE, run_id=LIVE_RUN, symbol=SYMBOL, market_type=MARKET,
            direction=LONG, setup_family=TREND_PULLBACK, as_of=T0,
            boundary_mode=HISTORY_THROUGH_T)
        for field, bad in (
            ("run_kind", "NOPE"), ("run_id", "  "), ("symbol", "ETHUSDT"),
            ("market_type", "spot"), ("direction", "SIDEWAYS"),
            ("setup_family", "NOT_A_FAMILY"), ("boundary_mode", "LATEST"),
            ("as_of", datetime(2026, 8, 20, 12, 3, tzinfo=UTC)),
            ("as_of", datetime(2026, 8, 20, 12, 0)),
        ):
            kwargs = dict(base)
            kwargs[field] = bad
            with pytest.raises((V2EpisodeSlotReaderError, V2EpisodeHistoryError)):
                await read_v2_slot_episode_states(_PoisonConn(), **kwargs)

    asyncio.run(body())


def test_reader_rejects_a_row_missing_a_selected_column():
    class _ShortRowConn:
        async def fetch(self, *args):
            return [{"episode_id": "x" * 64}]

    async def body():
        with pytest.raises(V2EpisodeSlotReaderError, match="missing selected column"):
            await read_v2_slot_episode_states(
                _ShortRowConn(), run_kind=LIVE, run_id=LIVE_RUN, symbol=SYMBOL,
                market_type=MARKET, direction=LONG, setup_family=TREND_PULLBACK,
                as_of=T0, boundary_mode=HISTORY_THROUGH_T)

    asyncio.run(body())


# ============================================================================
# 7. the substrate Unit 2's cooldown rule consumes, end to end
# ============================================================================
def test_slot_facts_drive_the_frozen_cooldown_clock():
    """Read the real persisted terminal fact and feed it to §12.8's rule."""
    from analytics.forecasting_v2.episode_creation import (
        V2SlotTerminalFact, evaluate_terminal_cooldown,
    )

    async def body(db, _dsn):
        await _seed(db, _lifecycle(
            t_create=T0, anchor_n=0, states=((0, EARLY_SIGNAL), (1, INVALIDATED))))
        row = await _latest_terminal(db, as_of=_t(50))
        fact = V2SlotTerminalFact(
            episode_id=row["episode_id"], terminal_state=row["episode_state"],
            t_terminal=row["decision_boundary"])
        assert fact.earliest_eligible_boundary == _t(4)     # T_terminal(+5m) + 15m
        assert evaluate_terminal_cooldown(fact, T=_t(3)) is False
        assert evaluate_terminal_cooldown(fact, T=_t(4)) is True

    _run(body)
