"""
V2-H2b: durable version-switch state storage
(`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3.1).

Pure storage: static/trusted SQL, row<->`V2VersionSwitchState` conversion,
and the real atomicity/concurrency mechanism (bootstrap-if-missing +
`SELECT ... FOR UPDATE` row lock inside one transaction). Imports NO
analytics decision logic beyond the already-pure `version_switch.py` value
objects it converts to/from rows -- it makes no transition decision itself
(that remains `analytics/forecasting_v2/version_switch.py`'s job).

`storage/db.py`'s `Database.evaluate_v2_version_switch` owns the
connection/transaction; this module only provides the SQL and the
row-shape conversion functions it calls against an already-acquired
`asyncpg.Connection`.

Atomicity/concurrency mechanism: real PostgreSQL row-level locking via
`SELECT ... FOR UPDATE` inside one transaction. `PRIMARY KEY (run_kind,
run_id)` means there is exactly one row per `execution_stream`; a second
caller evaluating the SAME `execution_stream` concurrently blocks at the
`FOR UPDATE` select until the first caller's transaction commits (or rolls
back), then observes the FIRST caller's already-durably-persisted result --
never a torn/interleaved read, never two callers computing a transition
from the same stale state. `tests/storage/test_v2_version_switch_readers.py`
proves this against a REAL PostgreSQL instance, not a mocked connection.
"""
from __future__ import annotations

from analytics.forecasting_v2.version_switch import (
    SWITCH_PHASES, V2SemanticTuple, V2VersionSwitchState,
)

__all__ = [
    "V2VersionSwitchReaderError",
    "bootstrap_and_lock_v2_version_switch_state",
    "persist_v2_version_switch_state",
]


class V2VersionSwitchReaderError(ValueError):
    """Invalid version-switch reader/writer argument, or a row read back
    from `v2_version_switch_state` that fails `V2VersionSwitchState`'s own
    self-validation (a genuinely corrupted/inconsistent row -- the table's
    own CHECK constraints should make this unreachable in practice; this
    is defense-in-depth, never silently repaired)."""


# `run_kind`/`run_id` are validated implicitly by `V2VersionSwitchState`'s
# own `__post_init__` once a row is converted -- this module does not
# duplicate that check before issuing SQL (mirrors
# `storage/shadow_recovery_readers.py`'s validate-in-the-value-object
# convention for this exact kind of narrow identity input).

_BOOTSTRAP_SQL = """
INSERT INTO v2_version_switch_state (run_kind, run_id, phase)
VALUES ($1, $2, 'NO_PENDING_SWITCH')
ON CONFLICT (run_kind, run_id) DO NOTHING
"""

_SELECT_FOR_UPDATE_SQL = """
SELECT
    run_kind, run_id,
    active_rules_version, active_calculation_version, active_decision_code_version,
    pending_rules_version, pending_calculation_version, pending_decision_code_version,
    phase, drain_complete_at, requested_at
FROM v2_version_switch_state
WHERE run_kind = $1 AND run_id = $2
FOR UPDATE
"""

_UPDATE_SQL = """
UPDATE v2_version_switch_state
SET
    active_rules_version = $3, active_calculation_version = $4,
    active_decision_code_version = $5,
    pending_rules_version = $6, pending_calculation_version = $7,
    pending_decision_code_version = $8,
    phase = $9, drain_complete_at = $10, requested_at = $11,
    updated_at = now()
WHERE run_kind = $1 AND run_id = $2
"""


def _row_to_state(row) -> V2VersionSwitchState:
    active = None
    if row["active_rules_version"] is not None:
        active = V2SemanticTuple(
            rules_version=row["active_rules_version"],
            calculation_version=row["active_calculation_version"],
            decision_code_version=row["active_decision_code_version"])
    pending = None
    if row["pending_rules_version"] is not None:
        pending = V2SemanticTuple(
            rules_version=row["pending_rules_version"],
            calculation_version=row["pending_calculation_version"],
            decision_code_version=row["pending_decision_code_version"])
    phase = row["phase"]
    if phase not in SWITCH_PHASES:
        raise V2VersionSwitchReaderError(
            f"v2_version_switch_state row has an unrecognized phase {phase!r} -- "
            f"expected one of {SWITCH_PHASES}; table CHECK constraints should make "
            "this unreachable, this is defense-in-depth only")
    return V2VersionSwitchState(
        run_kind=row["run_kind"], run_id=row["run_id"], active=active, pending=pending,
        phase=phase, drain_complete_at=row["drain_complete_at"], requested_at=row["requested_at"])


def _state_to_update_params(state: V2VersionSwitchState) -> tuple:
    active = state.active
    pending = state.pending
    return (
        state.run_kind, state.run_id,
        active.rules_version if active is not None else None,
        active.calculation_version if active is not None else None,
        active.decision_code_version if active is not None else None,
        pending.rules_version if pending is not None else None,
        pending.calculation_version if pending is not None else None,
        pending.decision_code_version if pending is not None else None,
        state.phase, state.drain_complete_at, state.requested_at,
    )


async def bootstrap_and_lock_v2_version_switch_state(
    conn, *, run_kind: str, run_id: str,
) -> V2VersionSwitchState:
    """MUST be called inside an already-open transaction on `conn`
    (`storage/db.py` owns `conn.transaction()`). Ensures a row exists for
    this `execution_stream` (idempotent `INSERT ... ON CONFLICT DO
    NOTHING`, bootstrapping a fresh stream's `NO_PENDING_SWITCH`/`active=
    NULL` identity — see `version_switch.initial_switch_state`), then reads
    it back with `SELECT ... FOR UPDATE`, acquiring the real PostgreSQL row
    lock that serializes any concurrent caller evaluating the SAME
    `execution_stream` until this transaction commits or rolls back. The
    caller MUST NOT release/close the transaction before calling
    `persist_v2_version_switch_state` with the resolved next state -- doing
    so would drop the lock before the write, reopening the exact race this
    function exists to prevent."""
    if not isinstance(run_kind, str) or not isinstance(run_id, str):
        raise V2VersionSwitchReaderError("run_kind/run_id must be strings")
    await conn.execute(_BOOTSTRAP_SQL, run_kind, run_id)
    row = await conn.fetchrow(_SELECT_FOR_UPDATE_SQL, run_kind, run_id)
    if row is None:
        # Unreachable in practice (the bootstrap INSERT above guarantees a
        # row exists before this SELECT) -- defense-in-depth only, never a
        # silent fabrication of a fresh state here.
        raise V2VersionSwitchReaderError(
            f"no v2_version_switch_state row for (run_kind={run_kind!r}, "
            f"run_id={run_id!r}) even after bootstrap -- this should be unreachable")
    return _row_to_state(row)


async def persist_v2_version_switch_state(conn, state: V2VersionSwitchState) -> None:
    """Durably persist `state` as the new row for its `execution_stream`.
    MUST be called on the SAME `conn`/transaction that held the `FOR
    UPDATE` lock from `bootstrap_and_lock_v2_version_switch_state` --
    calling this on a different connection would write without the lock
    that made the read-compute-write sequence atomic. A single `UPDATE ...
    WHERE run_kind = $1 AND run_id = $2` -- never an `INSERT`, since
    `bootstrap_and_lock_v2_version_switch_state` already guarantees the row
    exists."""
    if not isinstance(state, V2VersionSwitchState):
        raise V2VersionSwitchReaderError(
            f"state must be a V2VersionSwitchState, got {type(state).__name__}")
    await conn.execute(_UPDATE_SQL, *_state_to_update_params(state))
