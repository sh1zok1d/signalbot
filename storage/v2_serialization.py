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

No DB handle, no clock, no I/O.
"""
from __future__ import annotations

from dataclasses import fields as dataclass_fields

from analytics.forecasting_v2.events import V2EpisodeEvent
from storage.stage2_serialization import (
    Stage2SerializationError, Stage2WriterSpec, dumps_canonical_jsonb,
    serialize_batch, to_jsonable,
)

__all__ = [
    "V2_EPISODE_EVENT_SPEC",
    "serialize_batch", "Stage2SerializationError", "Stage2WriterSpec",
    "to_jsonable", "dumps_canonical_jsonb",
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
