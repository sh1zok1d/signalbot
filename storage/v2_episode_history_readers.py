"""
Stage 6 Unit 1/5 — persisted episode-history PostgreSQL reads
(`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §12.10/§13.4/§2.1a).

The concrete storage half of the foundation whose pure domain half is
`analytics/forecasting_v2/episode_history.py`. This module owns exactly
one thing: reading one episode's already-persisted `v2_episode_events`
rows, physically scoped to one `execution_stream` and one logical decision
boundary, in a deterministic order — and nothing else.

Same posture as `storage/v2_alignment_readers.py`/`storage/
v2_setup_readers.py`: static/trusted SQL, explicit column list, JSONB
detached and deeply frozen before it leaves this module, no analytics
decision logic, no clock, no I/O beyond the caller's already-acquired
`asyncpg.Connection`. `storage/db.py::Database.fetch_v2_episode_history`
is the thin wrapper that owns the connection.

**Execution namespace is mandatory, never optional (§12.10).** Every query
here pins BOTH `run_kind` AND `run_id`. There is deliberately no
"read this episode across streams" entry point: §12.10 requires that
episode-identity reconstruction "MUST NEVER mix LIVE history with REPLAY
history" or "one REPLAY `run_id`'s history with a different REPLAY
`run_id`'s history." Semantic IDs are *designed* to coincide across
streams (`episode_identity.py` excludes `run_kind`/`run_id` from
`episode_id` on purpose), which is exactly why the PHYSICAL read must
always be namespaced — an un-namespaced `WHERE episode_id = ...` would
silently return another stream's rows for the identical semantic episode.

**Logical `as_of`, never a wall clock.** The upper bound is always the
caller's explicit logical decision boundary. This module contains no
`now()`, `CURRENT_TIMESTAMP`, or "latest row regardless of `T`" path.
`boundary_mode` selects between §13.4's two frozen windows — strictly
before `T` (step 1's "ACTIVE immediately before `T`") and through `T`
inclusive (step 3b's cooldown lookup, where `T_terminal = T` is
"immediately-effective") — and has no default, so no caller can silently
inherit the wrong one. The comparison operator is chosen from that
validated enum and interpolated into otherwise-static SQL; every value
remains a bound parameter.

**Deterministic ordering, and why the tie-break is not a state
resolution.** `ORDER BY decision_boundary ASC, event_id ASC`. The primary
key is the semantic one §13.4 reasons about. The secondary `event_id` is
NOT a per-`T` event ordinal — §2.1a freezes "at most one persisted
`V2EpisodeEvent` per (execution_stream, episode_id, decision_boundary)"
and `ux_v2ee_episode_decision_boundary` enforces it physically, so a tie
is IMPOSSIBLE in a sound database. It exists solely so that IF the
database were somehow corrupt, this read is still byte-reproducible rather
than returning rows in arbitrary heap order — and
`reconstruct_episode_history()` then REJECTS that duplicate boundary as
corruption rather than picking a winner. A deterministic read of corrupt
data that then fails loudly beats a non-deterministic read that fails
intermittently.

**Index.** `storage/stage2_schema.sql`'s existing
`ix_v2ee_episode_history (run_kind, run_id, episode_id, decision_boundary
ASC)` already covers this access pattern exactly — leading equality on all
three scope columns, then the ranged/ordered `decision_boundary`. No new
index and no schema change is introduced by this module.
"""
from __future__ import annotations

import json
from collections.abc import Mapping as _AbcMapping
from types import MappingProxyType
from typing import Any

from analytics.forecasting_v2.episode_history import (
    HISTORY_BEFORE_T, HISTORY_THROUGH_T, validate_episode_history_scope,
)

__all__ = [
    "V2EpisodeHistoryReaderError",
    "EPISODE_HISTORY_COLUMNS",
    "read_v2_episode_history",
]


class V2EpisodeHistoryReaderError(ValueError):
    """A persisted `v2_episode_events` row this reader cannot even shape-
    check: a non-row-shaped record, a missing selected column, or malformed
    JSONB. Semantic corruption (identity drift, lookahead, duplicate
    boundaries) is NOT this module's job — that is
    `analytics/forecasting_v2/episode_history.py`'s
    `V2EpisodeHistoryCorruptionError`, raised once, over the whole
    reconstructed history."""


# The FULL explicit column set this module selects -- `created_at` is
# deliberately EXCLUDED: it is DB-owned wall-clock insertion metadata
# (`storage/stage2_schema.sql`: "metadata only"), never a logical decision
# fact, and letting it reach the domain layer would invite exactly the
# wall-clock ordering/visibility bug §12.10/§13.4 forbid.
EPISODE_HISTORY_COLUMNS = (
    "run_kind", "run_id", "event_id", "episode_id",
    "model_family", "rules_version",
    "symbol", "market_type", "direction", "setup_family", "structural_anchor",
    "episode_state", "decision_boundary",
    "feature_schema_version", "calculation_version", "config_hash",
    "config_version", "code_version", "decision_code_version",
    "decision_snapshot", "event_payload",
)

_JSONB_COLUMNS = ("structural_anchor", "decision_snapshot", "event_payload")

# Static SQL modulo ONE operator chosen from a validated two-value enum
# (never caller text). Both windows share every other clause.
_EPISODE_HISTORY_SQL_TEMPLATE = f"""
SELECT {', '.join(EPISODE_HISTORY_COLUMNS)}
FROM v2_episode_events
WHERE run_kind = $1
  AND run_id = $2
  AND episode_id = $3
  AND decision_boundary {{operator}} $4
ORDER BY decision_boundary ASC, event_id ASC
"""

_BOUNDARY_OPERATORS = MappingProxyType({
    HISTORY_BEFORE_T: "<",
    HISTORY_THROUGH_T: "<=",
})


def _freeze_json_value(value: Any, name: str) -> Any:
    """Detach + deeply freeze one JSONB value, identical posture to
    `storage/v2_setup_readers.py::_freeze_json_value` (this module raises
    its own error type at its own boundary, matching how each V2 reader
    module already does)."""
    if isinstance(value, _AbcMapping):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise V2EpisodeHistoryReaderError(
                    f"{name}: JSON object keys must be str, got {type(k).__name__}: {k!r}")
            out[k] = _freeze_json_value(v, f"{name}.{k}")
        return MappingProxyType(out)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_value(v, f"{name}[]") for v in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise V2EpisodeHistoryReaderError(
        f"{name}: unsupported JSON value of type {type(value).__name__}")


def _parse_required_json_column(value: Any, name: str) -> Any:
    if value is None:
        raise V2EpisodeHistoryReaderError(f"{name} must not be NULL")
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError) as exc:
            raise V2EpisodeHistoryReaderError(f"{name}: malformed JSON: {exc}") from exc
        return _freeze_json_value(decoded, name)
    return _freeze_json_value(value, name)


def _detach_row(rec: Any, *, index: int) -> "MappingProxyType":
    """Copy one asyncpg `Record` into a plain frozen mapping, parsing every
    JSONB column. Nothing DB-owned (or lazily-bound to a released
    connection) escapes this module."""
    if isinstance(rec, (str, bytes, bytearray)) or not isinstance(rec, _AbcMapping):
        try:
            rec = dict(rec)
        except (TypeError, ValueError) as exc:
            raise V2EpisodeHistoryReaderError(
                f"v2_episode_events row[{index}] is not row-shaped: "
                f"{type(rec).__name__}") from exc
    out = {}
    for column in EPISODE_HISTORY_COLUMNS:
        try:
            value = rec[column]
        except (KeyError, TypeError) as exc:
            raise V2EpisodeHistoryReaderError(
                f"v2_episode_events row[{index}] is missing selected column "
                f"{column!r}") from exc
        out[column] = (
            _parse_required_json_column(value, column) if column in _JSONB_COLUMNS else value)
    return MappingProxyType(out)


async def read_v2_episode_history(
    conn,
    *,
    run_kind: str,
    run_id: str,
    episode_id: str,
    as_of,
    boundary_mode: str,
) -> "tuple[MappingProxyType, ...]":
    """Every persisted `v2_episode_events` row for EXACTLY one
    `(run_kind, run_id, episode_id)` whose `decision_boundary` falls inside
    the `as_of` window selected by `boundary_mode`, oldest first.

    Returns a (possibly empty) tuple of deeply-frozen row mappings. An
    empty tuple means "this execution stream has no history for this
    episode in this window" — a legitimate answer, not an error. This
    function makes NO semantic judgement about the rows it returns; hand
    the result to
    `analytics/forecasting_v2/episode_history.py::reconstruct_episode_history()`
    for the §12.2/§2.1a integrity checks and the immutable creation-identity
    projection."""
    validate_episode_history_scope(
        run_kind=run_kind, run_id=run_id, episode_id=episode_id,
        as_of=as_of, boundary_mode=boundary_mode)
    sql = _EPISODE_HISTORY_SQL_TEMPLATE.format(operator=_BOUNDARY_OPERATORS[boundary_mode])
    rows = await conn.fetch(sql, run_kind, run_id, episode_id, as_of)
    return tuple(_detach_row(rec, index=i) for i, rec in enumerate(rows))
