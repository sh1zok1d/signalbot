"""
Stage 6 Unit 2 — per-slot episode fact reads
(`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §12.6/§12.8/§12.10/§13.4).

Unit 1's `storage/v2_episode_history_readers.py` answers "give me ONE
episode's history by `episode_id`". Unit 2's eligibility rules ask two
different, slot-shaped questions of the same immutable event log:

  - `read_v2_slot_episode_states` — for every episode in one `slot`
    (`(symbol, market_type, direction, setup_family)`, §12.3) within one
    `execution_stream`, the episode's LATEST persisted `episode_state` and
    the boundary it was recorded at, as of one logical `T`. From this the
    caller derives both "which episodes are non-terminal here" (§12.6) and
    "what is this slot's most recent terminal fact and its `T_terminal`"
    (§12.8).
  - `read_v2_slot_latest_terminal` — the same question narrowed to §13.4
    step 3b's single answer: the slot's MOST RECENT terminal episode and
    its `T_terminal`, or `None`.

Same posture as every other V2 reader: static/trusted SQL, explicit column
list, deterministic ordering, no analytics decision logic, no clock, no
I/O beyond the caller's already-acquired `asyncpg.Connection`.
`storage/db.py`'s thin wrappers own the connection.

**"Latest" is LOGICAL, never physical (§12.8/§13.4).** The per-episode
state is resolved by `decision_boundary`, never by `created_at` wall-clock
insertion time, never by DB insertion order, and never by lexical
`episode_id` order. `created_at` is deliberately not even selected.

**Execution namespace is mandatory (§12.10).** Every query pins BOTH
`run_kind` AND `run_id`. Semantic `episode_id`s are designed to coincide
across LIVE and REPLAY, so an un-namespaced slot read would let one
stream's active episode or cooldown suppress another's.

**Same-`T` visibility is the caller's explicit choice.** `boundary_mode`
reuses Unit 1's two frozen §13.4 windows verbatim (`HISTORY_BEFORE_T` /
`HISTORY_THROUGH_T`) and has no default — step 1's "ACTIVE immediately
before `T`" and step 3b's cooldown lookup (which includes an episode that
became terminal at this very `T`) are different windows over this same
table, and silently picking one would guarantee a wrong answer for the
other.

**Index.** `storage/stage2_schema.sql`'s existing `ix_v2ee_episode_history
(run_kind, run_id, episode_id, decision_boundary ASC)` covers the
stream-scoped scan these queries perform; the additional `symbol`/
`market_type`/`direction`/`setup_family` predicates are filters on a
low-volume, additive table (one row per persisted lifecycle event). No new
index and no schema change is introduced.
"""
from __future__ import annotations

from collections.abc import Mapping as _AbcMapping
from types import MappingProxyType
from typing import Any, Optional

from analytics.forecasting_v2.episode_history import (
    HISTORY_BEFORE_T, HISTORY_THROUGH_T, TERMINAL_EPISODE_STATES,
    validate_episode_history_scope,
)

__all__ = [
    "V2EpisodeSlotReaderError",
    "SLOT_STATE_COLUMNS",
    "read_v2_slot_episode_states",
    "read_v2_slot_latest_terminal",
]


class V2EpisodeSlotReaderError(ValueError):
    """A malformed slot-read scope, or a persisted row this reader cannot
    even shape-check. Semantic corruption over a whole episode history
    remains `analytics/forecasting_v2/episode_history.py`'s
    `V2EpisodeHistoryCorruptionError`, raised once, there."""


SLOT_STATE_COLUMNS = ("episode_id", "episode_state", "decision_boundary")

_BOUNDARY_OPERATORS = MappingProxyType({
    HISTORY_BEFORE_T: "<",
    HISTORY_THROUGH_T: "<=",
})

# For each episode in the slot/stream, the state recorded at its own
# LATEST visible decision_boundary. DISTINCT ON is resolved by
# decision_boundary DESC, with event_id DESC only as a deterministic
# tie-break -- §2.1a's ux_v2ee_episode_decision_boundary makes a tie
# impossible in a sound database, so this exists purely so a corrupt one
# is still read reproducibly rather than in arbitrary heap order.
_SLOT_STATES_SQL_TEMPLATE = """
SELECT DISTINCT ON (episode_id)
       episode_id, episode_state, decision_boundary
FROM v2_episode_events
WHERE run_kind = $1
  AND run_id = $2
  AND symbol = $3
  AND market_type = $4
  AND direction = $5
  AND setup_family = $6
  AND decision_boundary {operator} $7
ORDER BY episode_id ASC, decision_boundary DESC, event_id DESC
"""


def _validate_slot_scope(
    *, run_kind: Any, run_id: Any, symbol: Any, market_type: Any, direction: Any,
    setup_family: Any, as_of: Any, boundary_mode: Any,
) -> None:
    """Validate one slot read's full scope BEFORE any I/O.

    `run_kind`/`run_id`/`as_of`/`boundary_mode` are delegated to Unit 1's
    own `validate_episode_history_scope` so the two readers can never drift
    on what a legal execution stream or decision boundary is; a placeholder
    `episode_id` is supplied because this read is slot-scoped rather than
    episode-scoped."""
    from analytics.forecasting_v2._validation import (
        one_of, validate_market_type, validate_symbol,
    )
    from analytics.forecasting_v2.events import DIRECTIONS, SETUP_FAMILIES

    validate_episode_history_scope(
        run_kind=run_kind, run_id=run_id, episode_id="0" * 64,
        as_of=as_of, boundary_mode=boundary_mode)
    validate_symbol(symbol, V2EpisodeSlotReaderError)
    validate_market_type(market_type, V2EpisodeSlotReaderError)
    one_of(direction, "direction", DIRECTIONS, V2EpisodeSlotReaderError)
    one_of(setup_family, "setup_family", SETUP_FAMILIES, V2EpisodeSlotReaderError)


def _detach_row(rec: Any, *, index: int) -> "MappingProxyType":
    if isinstance(rec, (str, bytes, bytearray)) or not isinstance(rec, _AbcMapping):
        try:
            rec = dict(rec)
        except (TypeError, ValueError) as exc:
            raise V2EpisodeSlotReaderError(
                f"v2_episode_events row[{index}] is not row-shaped: "
                f"{type(rec).__name__}") from exc
    out = {}
    for column in SLOT_STATE_COLUMNS:
        try:
            out[column] = rec[column]
        except (KeyError, TypeError) as exc:
            raise V2EpisodeSlotReaderError(
                f"v2_episode_events row[{index}] is missing selected column "
                f"{column!r}") from exc
    return MappingProxyType(out)


async def read_v2_slot_episode_states(
    conn, *, run_kind: str, run_id: str, symbol: str, market_type: str,
    direction: str, setup_family: str, as_of, boundary_mode: str,
) -> "tuple[MappingProxyType, ...]":
    """Every episode in one `(execution_stream, slot)` with its LATEST
    persisted `episode_state` and that state's own `decision_boundary`, as
    of `as_of` under `boundary_mode`.

    Ordered deterministically by `episode_id`. Returns a (possibly empty)
    tuple of frozen mappings; an empty tuple means this stream has never
    persisted an episode in this slot within this window — a legitimate
    answer, not an error. This function makes no eligibility judgement:
    deciding which of these are §12.6 active occupants and which is §12.8's
    most recent terminal is the analytics layer's job."""
    _validate_slot_scope(
        run_kind=run_kind, run_id=run_id, symbol=symbol, market_type=market_type,
        direction=direction, setup_family=setup_family, as_of=as_of,
        boundary_mode=boundary_mode)
    sql = _SLOT_STATES_SQL_TEMPLATE.format(operator=_BOUNDARY_OPERATORS[boundary_mode])
    rows = await conn.fetch(
        sql, run_kind, run_id, symbol, market_type, direction, setup_family, as_of)
    return tuple(_detach_row(rec, index=i) for i, rec in enumerate(rows))


async def read_v2_slot_latest_terminal(
    conn, *, run_kind: str, run_id: str, symbol: str, market_type: str,
    direction: str, setup_family: str, as_of, boundary_mode: str,
) -> "Optional[MappingProxyType]":
    """§13.4 step 3b's single answer for one slot: the MOST RECENT terminal
    episode and its `T_terminal`, or `None` if this slot has never had one
    in this stream/window.

    "Most recent" is by logical `decision_boundary` (§12.8: "`T_terminal` =
    the decision boundary of the terminal event"), never by wall clock or
    insertion order. Under `HISTORY_THROUGH_T` this correctly INCLUDES an
    episode whose `T_terminal` is `as_of` itself — §12.8 makes that "a
    valid, immediately-effective value".

    An episode that later left its terminal state cannot exist (§13.2 gives
    terminal states no outgoing edges, and Unit 1's reconstruction rejects
    any history that claims otherwise), so this is computed from each
    episode's LATEST state rather than from any terminal row ever written:
    a row that is terminal but superseded is impossible history, not a
    candidate for "most recent terminal"."""
    states = await read_v2_slot_episode_states(
        conn, run_kind=run_kind, run_id=run_id, symbol=symbol, market_type=market_type,
        direction=direction, setup_family=setup_family, as_of=as_of,
        boundary_mode=boundary_mode)
    terminal = [r for r in states if r["episode_state"] in TERMINAL_EPISODE_STATES]
    if not terminal:
        return None
    # Deterministic: newest T_terminal wins; episode_id breaks an exact tie
    # so a slot with two same-boundary terminals reads reproducibly (the
    # analytics layer decides whether that state is legal at all).
    terminal.sort(key=lambda r: (r["decision_boundary"], r["episode_id"]), reverse=True)
    return terminal[0]
