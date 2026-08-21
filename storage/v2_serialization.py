"""
V2 episode-event storage serialization (SEPARATE from
storage/stage2_serialization.py, which this module reuses but never
modifies).

Bridges ONE V2 output model — `analytics/forecasting_v2/events.py`'s
`V2EpisodeEvent` — to its additive table, `v2_episode_events`
(`storage/stage2_schema.sql`). Reuses the generic, already-public Stage 2
serialization primitives unchanged (`Stage2WriterSpec`,
`Stage2SerializationError`, `to_jsonable`, `dumps_canonical_jsonb`,
`serialize_batch`) — nothing V1-specific is imported, and
`storage/stage2_serialization.py` is never touched by this module or by
this PR.

Write discipline: INSERT-ONCE EVENT, mirroring `forecast_predictions`'
insert-once pattern (`ON CONFLICT (...) DO NOTHING RETURNING TRUE`) — a
stored V2 episode event is historical truth
(`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §2.1) and is **never**
rewritten. There is no `DO UPDATE` path anywhere in this module. A
corrected research result uses a different `REPLAY` `run_id`, never an
update to an existing row.

**V2-H3 additions (§2.1a): batch-scope homogeneity + conflict-identity
comparison.** `assert_homogeneous_batch_scope()` and
`rows_semantically_equal()` are the two PURE, storage-shape-aware helpers
`storage/db.py::Database.insert_v2_episode_events` composes with real I/O
to satisfy §2.1a's atomic-publication and idempotent-retry requirements —
this module still performs no I/O of its own; see each function's own
docstring.

No DB handle, no clock, no I/O.
"""
from __future__ import annotations

import json
from dataclasses import fields as dataclass_fields
from typing import Mapping, Sequence

from analytics.forecasting_v2.events import V2EpisodeEvent
from storage.stage2_serialization import (
    Stage2SerializationError, Stage2WriterSpec, dumps_canonical_jsonb,
    serialize_batch, to_jsonable,
)

__all__ = [
    "V2_EPISODE_EVENT_SPEC",
    "serialize_batch", "Stage2SerializationError", "Stage2WriterSpec",
    "to_jsonable", "dumps_canonical_jsonb",
    "V2EventIdentityConflictError", "V2EventBatchScopeError",
    "assert_homogeneous_batch_scope", "rows_semantically_equal",
    "select_existing_v2_episode_event_sql",
]


def _build_v2_insert_once_sql(table: str, columns: tuple[str, ...], pk: tuple[str, ...],
                              jsonb_columns: frozenset) -> str:
    """Static parameterized `INSERT ... ON CONFLICT DO NOTHING RETURNING
    TRUE` for an insert-once V2 episode event row. Mirrors — does **not**
    import — `storage/stage2_serialization.py`'s private
    `_build_insert_once_sql`: the shape is identical because both freeze the
    same "immutable historical-truth event" discipline
    (`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §2.1 for V2,
    `analytics/forecasting/persistence.py`'s own docstring for V1). Kept as
    a small local copy rather than a cross-module import of a private
    helper, so `storage/stage2_serialization.py`'s V1 surface stays
    completely untouched by this PR. There is **no** `DO UPDATE` clause: a
    stored row can never be rewritten; `RETURNING TRUE` lets the writer tell
    a first insert (row → `True`) from a duplicate (row → `None`)."""
    placeholders = []
    for i, col in enumerate(columns, start=1):
        ph = f"${i}::jsonb" if col in jsonb_columns else f"${i}"
        placeholders.append(ph)
    return (
        f"INSERT INTO {table}\n"
        f"    ({', '.join(columns)})\n"
        f"VALUES ({', '.join(placeholders)})\n"
        f"ON CONFLICT ({', '.join(pk)}) DO NOTHING\n"
        f"RETURNING TRUE"
    )


def _make_v2_insert_once_spec(model: type, table: str, pk: tuple[str, ...],
                              jsonb_columns: frozenset) -> Stage2WriterSpec:
    columns = tuple(f.name for f in dataclass_fields(model))
    missing_pk = [c for c in pk if c not in columns]
    if missing_pk:
        raise Stage2SerializationError(f"{table} PK names not in model: {missing_pk}")
    missing_json = [c for c in jsonb_columns if c not in columns]
    if missing_json:
        raise Stage2SerializationError(f"{table} JSONB names not in model: {missing_json}")
    return Stage2WriterSpec(
        model=model, table=table, columns=columns, pk=pk,
        jsonb_columns=jsonb_columns,
        insert_sql=_build_v2_insert_once_sql(table, columns, pk, jsonb_columns),
    )


# V2EpisodeEvent is an insert-once EVENT — historical truth, never rewritten
# (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §2.1). (run_kind, run_id,
# event_id) is the storage identity: it namespaces LIVE vs. REPLAY execution
# apart, so a REPLAY run may legitimately reuse an event_id a LIVE run
# already used without colliding — and two distinct REPLAY runs remain
# distinguishable by their own run_id. created_at is never emitted — the
# table DEFAULT fills it.
V2_EPISODE_EVENT_SPEC = _make_v2_insert_once_spec(
    V2EpisodeEvent,
    "v2_episode_events",
    pk=("run_kind", "run_id", "event_id"),
    jsonb_columns=frozenset({"structural_anchor", "decision_snapshot", "event_payload"}),
)


# ============================================================================
# V2-H3: batch-scope homogeneity + conflict-identity comparison
# (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §2.1a).
# ============================================================================
class V2EventBatchScopeError(ValueError):
    """One `Database.insert_v2_episode_events` call must persist AT MOST
    one logical decision boundary's event batch (§2.1a) -- exactly the
    unit that writer commits atomically. Raised BEFORE any connection is
    acquired when a supplied batch spans more than one
    `(run_kind, run_id, decision_boundary)` scope."""


class V2EventIdentityConflictError(RuntimeError):
    """A `(run_kind, run_id, event_id)` identity that already exists in
    `v2_episode_events` was targeted again by a NEW attempt whose
    persisted, semantically-immutable fields differ from the already-
    stored row. Raised instead of silently accepting `ON CONFLICT DO
    NOTHING`'s no-op: a retried, byte-identical publish is legitimate
    idempotent success (§2.1a's own "Retry model, stated precisely" —
    identical deterministically-derived inputs reproduce identical IDs, so
    a retry's `ON CONFLICT DO NOTHING` guard is a safe no-op), but this
    EXACT deterministic identity describing two DIFFERENT payloads is
    never legitimate: it means either a hash collision, a caller bug
    (e.g. re-deriving `episode_id`/`event_id` from mutated inputs), or an
    attempt to reuse another event's identity for different content.
    Raising here inside the writer's own transaction rolls the WHOLE
    batch back (`storage/db.py`'s `conn.transaction()`) — the first
    writer's already-committed row is never touched (it was already
    durably committed as its own successful transaction, on a strictly
    earlier call), and this second, conflicting attempt's batch persists
    NOTHING, rather than silently keeping the first writer's row while
    discarding the second writer's differing content without any signal."""


def assert_homogeneous_batch_scope(rows: Sequence[V2EpisodeEvent]) -> None:
    """One physical `insert_v2_episode_events` call represents AT MOST one
    logical decision boundary's full event-insert batch (§2.1a) — exactly
    the unit `storage/db.py` commits atomically in one transaction. Reject
    a batch spanning more than one `(run_kind, run_id, decision_boundary)`
    scope BEFORE any connection is acquired, rather than silently accepting
    a caller bug that would leave "one atomic transaction" ambiguous about
    which logical unit it actually protects.

    Deliberately does NOT also require a single `episode_id` or a single
    `(rules_version, calculation_version, decision_code_version)` semantic
    tuple across the batch: §13.4 step 8 explicitly allows one decision
    boundary to touch MULTIPLE episodes at once (e.g. a lifecycle
    transition on one episode plus a `REVERSAL_CANDIDATE` cross-reference
    recorded on a different, pre-existing episode), and nothing in the
    frozen contract requires every event at one `T` to share one semantic
    tuple. Inventing either constraint here would encode a Stage-6-level
    business-logic assumption this persistence-only module is not
    authorized to assume (docs/FORECASTING_ROADMAP.md's V2-H3 scope:
    "MUST NOT implement Stage 6 state transitions").

    Assumes `rows` has already passed `serialize_batch()` (so every
    element really is a `V2EpisodeEvent`) — this function does not
    itself re-validate element types."""
    if len(rows) <= 1:
        return
    scopes = {(r.run_kind, r.run_id, r.decision_boundary) for r in rows}
    if len(scopes) > 1:
        raise V2EventBatchScopeError(
            "insert_v2_episode_events batch spans more than one logical decision "
            f"boundary -- found {len(scopes)} distinct (run_kind, run_id, "
            f"decision_boundary) scopes in one batch: {sorted(scopes)!r}; one call "
            "must persist exactly one logical decision boundary's events")


# Columns compared for §2.1a conflict-identity equality -- every persisted
# column EXCEPT the conflict target itself (run_kind/run_id/event_id,
# identical between the new attempt and the existing row BY DEFINITION, or
# there would be no ON CONFLICT to compare in the first place -- comparing
# them again would be a tautology, not a semantic-equality check) and the
# DB-owned created_at (metadata, never part of an event's semantic content).
_IDENTITY_CONFLICT_COMPARISON_COLUMNS = tuple(
    c for c in V2_EPISODE_EVENT_SPEC.columns if c not in ("run_kind", "run_id", "event_id"))


def select_existing_v2_episode_event_sql() -> str:
    """Static, parameterized `SELECT` of every persisted column (in
    `V2_EPISODE_EVENT_SPEC.columns` order — never a hand-maintained second
    column list that could silently drift from the model) for one exact
    `(run_kind, run_id, event_id)` identity. Used by `storage/db.py` to
    fetch the existing row a conflicting `ON CONFLICT DO NOTHING` just
    matched, so it can be compared via `rows_semantically_equal()` before
    deciding whether that conflict was an idempotent retry or a genuine
    identity-reuse conflict."""
    cols = ", ".join(V2_EPISODE_EVENT_SPEC.columns)
    return (
        f"SELECT {cols} FROM {V2_EPISODE_EVENT_SPEC.table} "
        "WHERE run_kind = $1 AND run_id = $2 AND event_id = $3"
    )


def rows_semantically_equal(new_params: "tuple", existing_row: Mapping) -> bool:
    """Compare a new attempt's serialized INSERT parameters (already
    produced by `serialize_batch()`, in `V2_EPISODE_EVENT_SPEC.columns`
    order) against an EXISTING persisted row (an `asyncpg.Record`/`Mapping`
    keyed by the same column names, e.g. from
    `select_existing_v2_episode_event_sql()`) for exact semantic equality
    on every column in `_IDENTITY_CONFLICT_COMPARISON_COLUMNS`.

    JSONB columns are compared as PARSED JSON, never as raw text:
    PostgreSQL's own internal `jsonb` storage/output can legitimately
    reorder keys differently from the exact byte sequence this writer sent
    (`dumps_canonical_jsonb()`'s sorted-key output is canonical on the
    PYTHON side; it is not a guarantee about Postgres's own `jsonb::text`
    formatting) — a raw string comparison could therefore report a FALSE
    conflict for two semantically-identical payloads. `decision_boundary`
    (`TIMESTAMPTZ`) compares as Python `datetime` objects directly — aware-
    datetime equality in Python already compares by absolute instant, not
    by naive field values, so this is correct regardless of which specific
    UTC-offset `tzinfo` instance either side happens to carry."""
    new_by_col = dict(zip(V2_EPISODE_EVENT_SPEC.columns, new_params))
    for col in _IDENTITY_CONFLICT_COMPARISON_COLUMNS:
        new_value = new_by_col[col]
        existing_value = existing_row[col]
        if col in V2_EPISODE_EVENT_SPEC.jsonb_columns:
            if json.loads(new_value) != json.loads(existing_value):
                return False
        elif new_value != existing_value:
            return False
    return True
