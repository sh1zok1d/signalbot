"""V2 episode-event insert-once writer against a fake asyncpg pool (no real
DB). Mirrors `tests/storage/test_stage2_writers.py`'s forecast-prediction
writer tests, extended for the batch return count `insert_v2_episode_events`
needs (each row's own `RETURNING TRUE`/`NULL`, not one batch-wide result).

Covers: `storage.v2_serialization` spec/SQL contract, `Database.
insert_v2_episode_events` batch behavior, JSONB round-tripping, caller-input
immutability after write, and the §2.1 historical-truth/no-rewrite
guarantee (insert-once SQL, no `DO UPDATE`, no update/trigger path
anywhere). No Docker / PostgreSQL / network / env required.
"""
from __future__ import annotations

import ast
import asyncio
import dataclasses
import inspect
import json
import re
import textwrap
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2.episode_identity import compute_episode_id, compute_event_id
from analytics.forecasting_v2.events import (
    COMPRESSION_BREAKOUT, CONFIRMED, EARLY_SIGNAL, LIVE, LONG, REPLAY, SHORT,
    TREND_PULLBACK, V2EpisodeEvent, V2EventInputError,
)
from common.v2_config import MODEL_FAMILY
from storage.db import Database
from storage.stage2_serialization import Stage2SerializationError as _CoreSerializationError
from storage.v2_serialization import (
    V2_EPISODE_EVENT_SPEC, Stage2SerializationError, V2EventBatchScopeError,
    V2EventIdentityConflictError, rows_semantically_equal, serialize_batch,
)

UTC = timezone.utc
B = datetime(2026, 7, 22, 12, 15, 0, tzinfo=UTC)
H64 = "a" * 64
H16 = "b" * 16


class _NoOpTransaction:
    # Mirrors tests/storage/test_stage2_db.py's identical fake -- a plain
    # no-op async context manager. __aexit__ returns False (never
    # suppresses an exception), exactly like real asyncpg's own
    # Transaction, so a raised V2EventIdentityConflictError still
    # propagates normally through `async with conn.transaction():` in
    # these mocked-pool tests. Real transactional atomicity/rollback is
    # proven for real in tests/storage/test_v2_episode_event_transactions.py.
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


# ---- fake asyncpg pool (per-row fetchval, like insert_forecast_prediction) --
class FakeConn:
    def __init__(self):
        self.executemany_calls: list[tuple] = []
        self.execute_calls: list[tuple] = []
        self.fetchval_calls: list[tuple] = []
        self.fetchrow_calls: list[tuple] = []
        # queue of results consumed in call order; falls back to `default`
        # once exhausted so single-row tests don't need to prime a queue.
        self.fetchval_results: list = []
        self.fetchval_default = True
        # Default fetchrow() behavior: ECHO back a Mapping built from
        # whichever row's own params were just attempted via fetchval() --
        # simulating "the existing row is byte-identical to this retry",
        # i.e. a genuine idempotent retry. This is exactly what every
        # EXISTING test in this file expects when fetchval_default=None
        # simulates "already stored". Set to an explicit Mapping (to
        # simulate a genuinely DIFFERENT existing row -> conflict) or to
        # None (to simulate "the just-conflicted row vanished before the
        # SELECT could read it back") to exercise those paths instead.
        self.fetchrow_override = "ECHO"
        self._last_fetchval_params: tuple = ()
        self.transaction_calls: int = 0

    async def executemany(self, sql, rows):
        self.executemany_calls.append((sql, list(rows)))

    async def execute(self, sql, *args):
        self.execute_calls.append((sql, args))
        return "OK"

    async def fetchval(self, sql, *args):
        self.fetchval_calls.append((sql, args))
        self._last_fetchval_params = args
        if self.fetchval_results:
            return self.fetchval_results.pop(0)
        return self.fetchval_default

    async def fetchrow(self, sql, *args):
        self.fetchrow_calls.append((sql, args))
        if self.fetchrow_override != "ECHO":
            return self.fetchrow_override
        return dict(zip(V2_EPISODE_EVENT_SPEC.columns, self._last_fetchval_params))

    def transaction(self):
        self.transaction_calls += 1
        return _NoOpTransaction()


class _Acquire:
    def __init__(self, pool):
        self.pool = pool

    async def __aenter__(self):
        self.pool.acquire_count += 1
        return self.pool.conn

    async def __aexit__(self, *exc):
        return False


class FakePool:
    def __init__(self):
        self.conn = FakeConn()
        self.acquire_count = 0

    def acquire(self):
        return _Acquire(self)


def _db():
    db = Database("postgresql://unused")
    db.pool = FakePool()
    return db


def _run(coro):
    return asyncio.run(coro)


def _hex_id(n: int) -> str:
    """A deterministic, guaranteed-valid 64-lowercase-hex-char placeholder,
    parametrized by a plain int -- used ONLY where a test needs an
    arbitrary-but-distinct identity string and does not care whether it
    is the semantically-correct compute_episode_id()/compute_event_id()
    output for the event's OTHER fields (episode_identity.py's own
    determinism/correctness is exercised exhaustively in
    tests/analytics/test_forecasting_v2_episode_identity.py, never here --
    this file exercises the WRITER's SQL/transaction/conflict behavior)."""
    return f"{n:064x}"


# ---- model factory ----------------------------------------------------------
def make_event(*, event_id=None, episode_id=None, **over) -> V2EpisodeEvent:
    """V2-H3 amendment (§2.1a): event_id/episode_id are no longer arbitrary
    opaque defaults -- by default this factory derives BOTH deterministically
    from whichever direction/setup_family/structural_anchor/decision_boundary
    end up in the constructed event (threading any caller override into the
    derivation too, so the default case is always internally consistent),
    exactly mirroring how a real caller is expected to use
    `episode_identity.py`. Pass `event_id=`/`episode_id=` explicitly (e.g.
    via `_hex_id()`) when a test needs an arbitrary-but-distinct identity
    without caring whether it is the "correct" hash for the event's other
    fields -- V2EpisodeEvent itself only enforces the 64-hex-char SHAPE,
    never full re-derivation (see events.py's own module docstring for why)."""
    direction = over.get("direction", LONG)
    setup_family = over.get("setup_family", TREND_PULLBACK)
    structural_anchor = over.get("structural_anchor", {"bucket_ts": "2026-07-22T12:10:00+00:00"})
    decision_boundary = over.get("decision_boundary", B)
    if episode_id is None:
        episode_id = compute_episode_id(
            model_family=MODEL_FAMILY, rules_version=over.get("rules_version", "v2-rules-v0.1.0"),
            calculation_version=over.get("calculation_version", H16),
            symbol=over.get("symbol", "BTCUSDT"), market_type=over.get("market_type", "perp"),
            direction=direction, setup_family=setup_family,
            structural_anchor=structural_anchor, t_create=decision_boundary)
    if event_id is None:
        event_id = compute_event_id(episode_id=episode_id, decision_boundary=decision_boundary)
    base = dict(
        run_kind=LIVE, run_id="live-shadow", event_id=event_id, episode_id=episode_id,
        model_family="v2", rules_version="v2-rules-v0.1.0",
        symbol="BTCUSDT", market_type="perp", direction=direction,
        setup_family=setup_family, structural_anchor=structural_anchor,
        episode_state=EARLY_SIGNAL, decision_boundary=decision_boundary,
        feature_schema_version=1, calculation_version=H16, config_hash=H64,
        config_version="2.1.0", code_version="deadbeef",
        decision_code_version="decision-deadbeef",
        decision_snapshot={"consensus_confidence": 87.5, "components": {"a": 1}},
        event_payload={"entry_zone": {"low": 64500.0, "high": 65000.0}, "reasons": ["x", "y"]},
    )
    base.update(over)
    return V2EpisodeEvent(**base)


# ============================================================================
# 1. spec / model parity
# ============================================================================
def test_spec_model_parity():
    model_fields = tuple(f.name for f in dataclasses.fields(V2EpisodeEvent))
    assert V2_EPISODE_EVENT_SPEC.columns == model_fields
    assert "created_at" not in V2_EPISODE_EVENT_SPEC.columns
    assert V2_EPISODE_EVENT_SPEC.table == "v2_episode_events"
    assert V2_EPISODE_EVENT_SPEC.pk == ("run_kind", "run_id", "event_id")
    assert V2_EPISODE_EVENT_SPEC.jsonb_columns == frozenset(
        {"structural_anchor", "decision_snapshot", "event_payload"})


def test_episode_id_not_in_pk():
    # episode_id is a LOGICAL identity component (§12), not part of the
    # storage identity — the persisted row's PK is (run_kind, run_id, event_id).
    assert "episode_id" not in V2_EPISODE_EVENT_SPEC.pk


def test_serialize_batch_reexported_matches_core():
    # storage.v2_serialization re-exports the SAME serialize_batch/error type
    # storage.stage2_serialization defines — it does not fork its own.
    assert Stage2SerializationError is _CoreSerializationError


# ============================================================================
# 2. SQL contract (insert-once, no DO UPDATE anywhere)
# ============================================================================
def _parse_insert_columns(sql: str) -> list[str]:
    m = re.search(r"INSERT INTO \w+\s*\(([^)]*)\)", sql, re.S)
    assert m
    return [c.strip() for c in m.group(1).split(",")]


def _parse_placeholders(sql: str) -> list[str]:
    m = re.search(r"VALUES \(([^)]*)\)", sql, re.S)
    assert m
    return [p.strip() for p in m.group(1).split(",")]


def test_sql_is_insert_once():
    sql = V2_EPISODE_EVENT_SPEC.insert_sql
    assert sql.startswith("INSERT INTO v2_episode_events")
    assert "ON CONFLICT (run_kind, run_id, event_id) DO NOTHING" in sql
    assert "RETURNING TRUE" in sql
    assert "DO UPDATE" not in sql
    assert "UPDATE" not in sql.replace("RETURNING TRUE", "")  # no stray UPDATE keyword
    assert "created_at" not in sql


def test_placeholders_jsonb_cast_matches_spec():
    sql = V2_EPISODE_EVENT_SPEC.insert_sql
    cols = _parse_insert_columns(sql)
    placeholders = _parse_placeholders(sql)
    assert cols == list(V2_EPISODE_EVENT_SPEC.columns)
    assert len(cols) == len(placeholders) == len(V2_EPISODE_EVENT_SPEC.columns)
    for i, (col, ph) in enumerate(zip(cols, placeholders), start=1):
        if col in V2_EPISODE_EVENT_SPEC.jsonb_columns:
            assert ph == f"${i}::jsonb"
        else:
            assert ph == f"${i}"


def test_conflict_target_is_exact_pk_no_more_no_less():
    sql = V2_EPISODE_EVENT_SPEC.insert_sql
    m = re.search(r"ON CONFLICT \(([^)]*)\)", sql)
    assert m
    target = tuple(c.strip() for c in m.group(1).split(","))
    assert target == V2_EPISODE_EVENT_SPEC.pk


# ============================================================================
# 3. successful first insert
# ============================================================================
def test_first_insert_returns_one_single_row():
    db = _db()
    db.pool.conn.fetchval_default = True
    result = _run(db.insert_v2_episode_events([make_event()]))
    assert result == 1
    assert db.pool.acquire_count == 1
    assert len(db.pool.conn.fetchval_calls) == 1
    assert db.pool.conn.executemany_calls == []          # never the correction-friendly path
    assert db.pool.conn.execute_calls == []
    sql, args = db.pool.conn.fetchval_calls[0]
    assert sql == V2_EPISODE_EVENT_SPEC.insert_sql
    assert len(args) == len(V2_EPISODE_EVENT_SPEC.columns)


# ============================================================================
# 4. duplicate
# ============================================================================
def test_duplicate_returns_zero_single_call():
    db = _db()
    db.pool.conn.fetchval_default = None                 # ON CONFLICT DO NOTHING -> no row
    result = _run(db.insert_v2_episode_events([make_event()]))
    assert result == 0
    assert db.pool.acquire_count == 1
    assert len(db.pool.conn.fetchval_calls) == 1
    assert db.pool.conn.execute_calls == []               # no follow-up update query


# ============================================================================
# 5. honest per-row batch count (mixed insert/duplicate)
# ============================================================================
def test_batch_honest_count_mixed_insert_and_duplicate():
    db = _db()
    # row 0 -> inserted, row 1 -> duplicate, row 2 -> inserted
    db.pool.conn.fetchval_results = [True, None, True]
    rows = [make_event(event_id=_hex_id(1)), make_event(event_id=_hex_id(2)),
            make_event(event_id=_hex_id(3))]
    result = _run(db.insert_v2_episode_events(rows))
    assert result == 2
    assert db.pool.acquire_count == 1                     # one connection acquired for the batch
    assert len(db.pool.conn.fetchval_calls) == 3           # one fetchval per row, not executemany
    assert db.pool.conn.executemany_calls == []


def test_all_duplicates_returns_zero():
    db = _db()
    db.pool.conn.fetchval_results = [None, None]
    rows = [make_event(event_id=_hex_id(1)), make_event(event_id=_hex_id(2))]
    assert _run(db.insert_v2_episode_events(rows)) == 0


# ============================================================================
# 6. empty batch
# ============================================================================
@pytest.mark.parametrize("empty", [[], ()])
def test_empty_batch_returns_zero_without_acquiring(empty):
    db = _db()
    result = _run(db.insert_v2_episode_events(empty))
    assert result == 0
    assert db.pool.acquire_count == 0
    assert db.pool.conn.fetchval_calls == []


# ============================================================================
# 7. wrong row type / malformed container rejected before acquire
# ============================================================================
@pytest.mark.parametrize("bad", [object(), None, {"run_kind": "LIVE"}, "not-a-row"])
def test_wrong_type_rejected_before_acquire(bad):
    db = _db()
    with pytest.raises(Stage2SerializationError):
        _run(db.insert_v2_episode_events([bad]))
    assert db.pool.acquire_count == 0
    assert db.pool.conn.fetchval_calls == []


def test_mixed_batch_rejected_before_acquire():
    db = _db()
    with pytest.raises(Stage2SerializationError):
        _run(db.insert_v2_episode_events([make_event(), object()]))
    assert db.pool.acquire_count == 0
    assert db.pool.conn.fetchval_calls == []


def test_malformed_container_rejected_before_acquire():
    db = _db()
    with pytest.raises(Stage2SerializationError):
        _run(db.insert_v2_episode_events(make_event()))   # a single row, not a Sequence of rows
    assert db.pool.acquire_count == 0


def test_generator_rejected_not_consumed():
    db = _db()

    def gen():
        yield make_event()

    with pytest.raises(Stage2SerializationError):
        _run(db.insert_v2_episode_events(gen()))
    assert db.pool.acquire_count == 0


# ============================================================================
# 8. no pool
# ============================================================================
def test_no_pool_valid_batch_hits_assertion():
    db = Database("postgresql://unused")                  # pool is None
    with pytest.raises(AssertionError):
        _run(db.insert_v2_episode_events([make_event()]))


def test_no_pool_malformed_batch_fails_serialization_first():
    db = Database("postgresql://unused")
    with pytest.raises(Stage2SerializationError):
        _run(db.insert_v2_episode_events([object()]))


def test_no_pool_empty_batch_returns_zero_without_error():
    db = Database("postgresql://unused")
    assert _run(db.insert_v2_episode_events([])) == 0


# ============================================================================
# 9. JSONB serialization + round-trip
# ============================================================================
def test_jsonb_columns_serialized_and_roundtrip():
    ev = make_event()
    params = dict(zip(V2_EPISODE_EVENT_SPEC.columns,
                      serialize_batch(V2_EPISODE_EVENT_SPEC, (ev,))[0]))
    for col in ("structural_anchor", "decision_snapshot", "event_payload"):
        assert isinstance(params[col], str)
    assert json.loads(params["structural_anchor"]) == dict(ev.structural_anchor)
    assert json.loads(params["decision_snapshot"]) == {
        "consensus_confidence": 87.5, "components": {"a": 1}}
    assert json.loads(params["event_payload"]) == {
        "entry_zone": {"low": 64500.0, "high": 65000.0}, "reasons": ["x", "y"]}
    # non-JSONB scalars pass through unchanged
    assert params["run_kind"] == LIVE
    assert params["direction"] == LONG
    assert params["decision_boundary"] == B


def test_decision_boundary_passed_as_datetime_not_stringified():
    # decision_boundary is a plain TIMESTAMPTZ column, not JSONB — asyncpg
    # gets the real datetime object, not an ISO string.
    ev = make_event()
    params = dict(zip(V2_EPISODE_EVENT_SPEC.columns,
                      serialize_batch(V2_EPISODE_EVENT_SPEC, (ev,))[0]))
    assert isinstance(params["decision_boundary"], datetime)


# ============================================================================
# 10. caller-input immutability after write
# ============================================================================
def test_inputs_unchanged_after_serialize_and_write():
    ev = make_event()
    before = (ev.run_kind, ev.event_id, dict(ev.structural_anchor),
              dict(ev.decision_snapshot), dict(ev.event_payload))
    db = _db()
    _run(db.insert_v2_episode_events([ev]))
    after = (ev.run_kind, ev.event_id, dict(ev.structural_anchor),
             dict(ev.decision_snapshot), dict(ev.event_payload))
    assert before == after


def test_mutating_caller_source_dict_after_construction_does_not_leak_into_write():
    payload = {"entry_zone": {"low": 64500.0}, "reasons": ["x"]}
    ev = make_event(event_payload=payload)
    payload["reasons"].append("mutated-after-construction")
    payload["entry_zone"]["low"] = -1.0
    params = dict(zip(V2_EPISODE_EVENT_SPEC.columns,
                      serialize_batch(V2_EPISODE_EVENT_SPEC, (ev,))[0]))
    stored = json.loads(params["event_payload"])
    assert stored["reasons"] == ["x"]
    assert stored["entry_zone"]["low"] == 64500.0


# ============================================================================
# 11. LIVE vs REPLAY provenance — writer-level coexistence
# ============================================================================
def test_live_and_replay_same_event_id_are_distinct_params_not_merged():
    shared_event_id = _hex_id(1)
    live = make_event(run_kind=LIVE, run_id="live-shadow", event_id=shared_event_id)
    replay = make_event(run_kind=REPLAY, run_id="replay-001", event_id=shared_event_id)
    params = serialize_batch(V2_EPISODE_EVENT_SPEC, (live, replay))
    assert len(params) == 2
    live_row = dict(zip(V2_EPISODE_EVENT_SPEC.columns, params[0]))
    replay_row = dict(zip(V2_EPISODE_EVENT_SPEC.columns, params[1]))
    assert live_row["run_kind"] == "LIVE" and live_row["run_id"] == "live-shadow"
    assert replay_row["run_kind"] == "REPLAY" and replay_row["run_id"] == "replay-001"
    assert live_row["event_id"] == replay_row["event_id"] == shared_event_id
    # the storage PK tuple differs even though event_id collides
    live_pk = tuple(live_row[c] for c in V2_EPISODE_EVENT_SPEC.pk)
    replay_pk = tuple(replay_row[c] for c in V2_EPISODE_EVENT_SPEC.pk)
    assert live_pk != replay_pk


def test_two_replay_runs_remain_distinguishable_by_run_id():
    shared_event_id = _hex_id(1)
    r1 = make_event(run_kind=REPLAY, run_id="replay-001", event_id=shared_event_id)
    r2 = make_event(run_kind=REPLAY, run_id="replay-002", event_id=shared_event_id)
    params = serialize_batch(V2_EPISODE_EVENT_SPEC, (r1, r2))
    row1 = dict(zip(V2_EPISODE_EVENT_SPEC.columns, params[0]))
    row2 = dict(zip(V2_EPISODE_EVENT_SPEC.columns, params[1]))
    pk1 = tuple(row1[c] for c in V2_EPISODE_EVENT_SPEC.pk)
    pk2 = tuple(row2[c] for c in V2_EPISODE_EVENT_SPEC.pk)
    assert pk1 != pk2


def test_live_and_replay_in_one_call_rejected_as_mixed_scope():
    # V2-H3 (§2.1a): a single insert_v2_episode_events() call must persist
    # AT MOST one logical decision boundary's batch. LIVE and REPLAY are
    # different execution_streams -- mixing them in ONE call is a caller
    # bug, rejected before any connection is acquired, never silently
    # accepted as "two independent inserts that happened to share a call".
    db = _db()
    db.pool.conn.fetchval_default = True
    shared_event_id = _hex_id(1)
    live = make_event(run_kind=LIVE, run_id="live-shadow", event_id=shared_event_id)
    replay = make_event(run_kind=REPLAY, run_id="replay-001", event_id=shared_event_id)
    with pytest.raises(V2EventBatchScopeError):
        _run(db.insert_v2_episode_events([live, replay]))
    assert db.pool.acquire_count == 0
    assert db.pool.conn.fetchval_calls == []


def test_live_and_replay_insert_independently_via_separate_calls():
    # The correct way to persist both: two SEPARATE calls, one per
    # execution_stream -- each its own atomic batch.
    db = _db()
    db.pool.conn.fetchval_default = True
    shared_event_id = _hex_id(1)
    live = make_event(run_kind=LIVE, run_id="live-shadow", event_id=shared_event_id)
    replay = make_event(run_kind=REPLAY, run_id="replay-001", event_id=shared_event_id)
    result_live = _run(db.insert_v2_episode_events([live]))
    result_replay = _run(db.insert_v2_episode_events([replay]))
    assert result_live == 1
    assert result_replay == 1
    assert len(db.pool.conn.fetchval_calls) == 2


# ============================================================================
# 12. historical truth / no-rewrite architectural regression
# ============================================================================
def test_writer_cannot_overwrite_existing_event():
    # The SQL policy itself is the guarantee in this no-Postgres suite: a
    # later write under the same (run_kind, run_id, event_id) is silently
    # skipped, never rewritten. A corrected research result must use a
    # different REPLAY run_id, never an update to an existing row.
    sql = V2_EPISODE_EVENT_SPEC.insert_sql
    assert "DO NOTHING" in sql and "DO UPDATE" not in sql
    db = _db()
    db.pool.conn.fetchval_default = None                  # simulate "already stored"
    assert _run(db.insert_v2_episode_events([make_event()])) == 0


def test_writer_does_not_route_through_correction_friendly_upsert_path():
    tree = ast.parse(textwrap.dedent(inspect.getsource(Database.insert_v2_episode_events)))
    called_attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert "_upsert_stage2" not in called_attrs
    assert "executemany" not in called_attrs
    assert "fetchval" in called_attrs


def test_writer_source_has_no_update_or_delete_calls():
    # The docstring legitimately *says* "no DO UPDATE path" in prose — strip
    # the docstring and check only the executable body for a stray UPDATE/
    # DELETE statement or call.
    tree = ast.parse(textwrap.dedent(inspect.getsource(Database.insert_v2_episode_events)))
    fn = tree.body[0]
    fn.body = fn.body[1:] if isinstance(fn.body[0], ast.Expr) and isinstance(
        fn.body[0].value, ast.Constant) and isinstance(fn.body[0].value.value, str) else fn.body
    body_src = ast.unparse(fn)
    assert "UPDATE" not in body_src.upper()
    assert "DELETE" not in body_src.upper()


def test_writer_never_calls_clock_or_random_or_uuid():
    src = inspect.getsource(Database.insert_v2_episode_events)
    for forbidden in ("datetime.now(", "time.time(", "uuid.uuid4(", "random."):
        assert forbidden not in src


def test_writer_not_called_from_connect_or_init_schema():
    # This PR must not wire the writer into any startup/runtime path.
    src = inspect.getsource(Database)
    # exclude the method's own definition line and docstring occurrences
    call_sites = [
        m.start() for m in re.finditer(r"\bself\.insert_v2_episode_events\(", src)]
    assert call_sites == []


# ============================================================================
# 14. V2-H3: atomicity + conflict-identity handling (fake-pool level)
# ============================================================================
def test_writer_uses_exactly_one_acquire_and_one_transaction_for_multi_row_batch():
    # Behavioral proof (CodeRabbit finding: a source-text `"conn.transaction()"
    # in src` assertion cannot distinguish "one transaction wrapping the
    # whole batch" from "one transaction call per row" -- both would
    # contain that literal substring exactly once in the source). A
    # 5-row batch must still acquire exactly ONE connection and open
    # exactly ONE transaction -- never one pair per row.
    db = _db()
    db.pool.conn.fetchval_default = True
    rows = [make_event(event_id=_hex_id(i)) for i in range(5)]
    result = _run(db.insert_v2_episode_events(rows))
    assert result == 5
    assert db.pool.acquire_count == 1
    assert db.pool.conn.transaction_calls == 1
    assert len(db.pool.conn.fetchval_calls) == 5


def test_identical_retry_after_conflict_is_idempotent_success():
    # fetchval_default=None simulates "this exact (run_kind, run_id,
    # event_id) already exists"; fetchrow's default ECHO behavior
    # simulates that the existing row is byte-identical to this retry --
    # the genuine idempotent-retry case. No exception; not counted.
    db = _db()
    db.pool.conn.fetchval_default = None
    result = _run(db.insert_v2_episode_events([make_event()]))
    assert result == 0
    assert len(db.pool.conn.fetchrow_calls) == 1


def test_conflicting_retry_raises_dedicated_identity_conflict_error():
    db = _db()
    db.pool.conn.fetchval_default = None  # conflict on ON CONFLICT DO NOTHING
    # Existing row differs from the new attempt (a different direction) --
    # a genuine conflicting identity reuse, never silently accepted.
    ev = make_event()
    conflicting_row = dict(zip(
        V2_EPISODE_EVENT_SPEC.columns, serialize_batch(V2_EPISODE_EVENT_SPEC, (ev,))[0]))
    conflicting_row["direction"] = SHORT
    db.pool.conn.fetchrow_override = conflicting_row
    with pytest.raises(V2EventIdentityConflictError, match="event_id"):
        _run(db.insert_v2_episode_events([ev]))


def test_conflicting_retry_error_message_names_the_identity():
    db = _db()
    db.pool.conn.fetchval_default = None
    conflict_event_id = _hex_id(0xC0FFEE)
    ev = make_event(run_kind=LIVE, run_id="live-shadow", event_id=conflict_event_id)
    conflicting_row = dict(zip(
        V2_EPISODE_EVENT_SPEC.columns, serialize_batch(V2_EPISODE_EVENT_SPEC, (ev,))[0]))
    conflicting_row["episode_state"] = "CONFIRMED"  # differs from EARLY_SIGNAL
    db.pool.conn.fetchrow_override = conflicting_row
    with pytest.raises(V2EventIdentityConflictError) as excinfo:
        _run(db.insert_v2_episode_events([ev]))
    assert "live-shadow" in str(excinfo.value)
    assert conflict_event_id in str(excinfo.value)


def test_conflict_row_vanished_before_reread_fails_closed():
    # An extreme, defensive edge case: ON CONFLICT DO NOTHING fired (a row
    # exists) but the follow-up SELECT inside the SAME transaction finds
    # nothing. This should never happen in a real, correctly-isolated
    # transaction, but the writer must fail closed rather than silently
    # treat a vanished row as "no conflict".
    db = _db()
    db.pool.conn.fetchval_default = None
    db.pool.conn.fetchrow_override = None
    with pytest.raises(V2EventIdentityConflictError):
        _run(db.insert_v2_episode_events([make_event()]))


# ============================================================================
# 15. rows_semantically_equal(): tolerates JSONB values that are either raw
# JSON text (asyncpg's default) OR already decoded by a registered type
# codec (dict/list/etc.) -- on EITHER side, independently.
# ============================================================================
def _new_params_for(ev) -> tuple:
    return serialize_batch(V2_EPISODE_EVENT_SPEC, (ev,))[0]


def _existing_row_from(ev, *, decode_jsonb: bool) -> dict:
    """An `existing_row`-shaped Mapping for `rows_semantically_equal()`'s
    second argument. `decode_jsonb=False` mirrors asyncpg's own default
    (JSONB columns arrive as raw `str`); `decode_jsonb=True` simulates a
    caller-registered type codec that already decoded them into plain
    Python structures before this function ever sees them."""
    row = dict(zip(V2_EPISODE_EVENT_SPEC.columns, _new_params_for(ev)))
    if decode_jsonb:
        for col in V2_EPISODE_EVENT_SPEC.jsonb_columns:
            row[col] = json.loads(row[col])
    return row


@pytest.mark.parametrize("decode_jsonb", [False, True])
def test_rows_semantically_equal_true_for_identical_content(decode_jsonb):
    ev = make_event()
    existing = _existing_row_from(ev, decode_jsonb=decode_jsonb)
    assert rows_semantically_equal(_new_params_for(ev), existing) is True


@pytest.mark.parametrize("decode_jsonb", [False, True])
def test_rows_semantically_equal_false_for_different_jsonb_content(decode_jsonb):
    ev = make_event(event_payload={"entry_zone": {"low": 1.0}})
    existing = _existing_row_from(
        make_event(event_payload={"entry_zone": {"low": 2.0}}), decode_jsonb=decode_jsonb)
    assert rows_semantically_equal(_new_params_for(ev), existing) is False


def test_rows_semantically_equal_true_when_only_existing_side_is_predecoded():
    # The new-attempt side is ALWAYS str (serialize_batch's own
    # dumps_canonical_jsonb output) -- this proves the EXISTING side alone
    # being pre-decoded (e.g. a registered asyncpg codec) does not, by
    # itself, produce a false conflict.
    ev = make_event()
    existing = _existing_row_from(ev, decode_jsonb=True)
    assert isinstance(existing["event_payload"], dict)   # genuinely pre-decoded
    assert rows_semantically_equal(_new_params_for(ev), existing) is True


def test_rows_semantically_equal_jsonb_key_order_never_causes_false_conflict():
    # Simulates PostgreSQL's own internal jsonb key-reordering: the
    # existing row's raw text differs byte-for-byte from this writer's
    # canonical output, but is semantically identical once parsed.
    ev = make_event(event_payload={"a": 1, "b": 2})
    reordered_text = json.dumps({"b": 2, "a": 1})
    existing = _existing_row_from(ev, decode_jsonb=False)
    existing["event_payload"] = reordered_text
    assert rows_semantically_equal(_new_params_for(ev), existing) is True


def test_rows_semantically_equal_non_jsonb_columns_compared_directly():
    ev = make_event(direction=SHORT)
    existing = _existing_row_from(make_event(direction=LONG), decode_jsonb=False)
    assert rows_semantically_equal(_new_params_for(ev), existing) is False


def test_batch_with_multiple_episodes_same_scope_is_allowed():
    # §13.4 step 8: one decision boundary MAY touch multiple episodes at
    # once (e.g. a lifecycle transition plus a REVERSAL_CANDIDATE
    # cross-reference on a different episode) -- homogeneity is required
    # only on (run_kind, run_id, decision_boundary), never on episode_id.
    db = _db()
    db.pool.conn.fetchval_default = True
    ev1 = make_event(event_id=_hex_id(1), episode_id=_hex_id(101))
    ev2 = make_event(event_id=_hex_id(2), episode_id=_hex_id(102))
    result = _run(db.insert_v2_episode_events([ev1, ev2]))
    assert result == 2


def test_batch_scope_error_raised_before_any_connection_acquired():
    db = _db()
    ev1 = make_event(decision_boundary=B)
    ev2 = make_event(decision_boundary=B + timedelta(minutes=5))
    with pytest.raises(V2EventBatchScopeError):
        _run(db.insert_v2_episode_events([ev1, ev2]))
    assert db.pool.acquire_count == 0


def test_different_run_id_same_run_kind_rejected_as_mixed_scope():
    db = _db()
    ev1 = make_event(run_kind=LIVE, run_id="live-shadow-a")
    ev2 = make_event(run_kind=LIVE, run_id="live-shadow-b")
    with pytest.raises(V2EventBatchScopeError):
        _run(db.insert_v2_episode_events([ev1, ev2]))


# ============================================================================
# 13. model-level rejection still applies at the writer boundary
# ============================================================================
def test_reversal_candidate_not_constructible_as_episode_state():
    with pytest.raises(V2EventInputError):
        make_event(episode_state="REVERSAL_CANDIDATE")


def test_neutral_direction_not_constructible():
    # An explicit episode_id override bypasses make_event()'s auto
    # episode_id derivation (which would itself reject "NEUTRAL" earlier,
    # via compute_episode_id()'s own V2EpisodeIdentityError) -- this test's
    # subject is specifically V2EpisodeEvent's OWN direction validation, so
    # it must actually reach that code path.
    with pytest.raises(V2EventInputError, match="direction"):
        make_event(direction="NEUTRAL", episode_id=_hex_id(1))


def test_confirmed_state_and_compression_breakout_family_round_trip():
    ev = make_event(episode_state=CONFIRMED, setup_family=COMPRESSION_BREAKOUT,
                     direction=SHORT, structural_anchor={"bucket_ts": "x", "price": 64000.0})
    params = dict(zip(V2_EPISODE_EVENT_SPEC.columns,
                      serialize_batch(V2_EPISODE_EVENT_SPEC, (ev,))[0]))
    assert params["episode_state"] == "CONFIRMED"
    assert params["setup_family"] == "COMPRESSION_BREAKOUT"
    assert params["direction"] == "SHORT"
