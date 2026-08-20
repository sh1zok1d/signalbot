"""
V2-H2b thin orchestration boundary
(`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3.1).

The ONLY async/impure layer V2-H2b adds. Everything it does:

  1. load durable switch state (caller's job -- see
     `storage/v2_version_switch_readers.py`/`storage/db.py`'s
     `Database.evaluate_v2_version_switch`, which wraps this function in
     one row-locked transaction);
  2. decide WHICH of the two facts `version_switch.py`'s pure state machine
     might need for this call (`V2DrainFact` while `DRAINING`;
     §3.3 activation readiness once drain is already known complete) and
     issue ONLY those reads -- never a speculative read that could not
     possibly affect this call's outcome, and never a swallowed exception
     turned into a soft "not ready"/"not drained" (§3.1/§3.3's fail-closed
     discipline: corruption/reader-errors propagate unchanged, never
     silently reinterpreted as legitimate absence);
  3. run the pure transition (`version_switch.evaluate_version_switch_
     transition`);
  4. return the result for the caller to durably, atomically persist.

This module does NOT itself persist anything -- no DB writes, no
transaction, no locking. It is deliberately reusable against ANY
`V2SetupHistoryReader`/`V2VersionDrainStatusReader` pair (real or fake),
which is exactly what lets it be unit-tested with deterministic fakes
without a real database, while the real atomicity/concurrency guarantee
(`storage/db.py`) wraps it with a real row lock and a real transaction.

Does NOT implement Stage 6, candidate arbitration, or any episode
lifecycle logic -- see `version_switch.py`'s module docstring for the
exact non-scope this shares.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from analytics.forecasting_v2.activation_readiness import check_activation_readiness
from analytics.forecasting_v2.alignment import V2AlignmentError, selected_bucket
from analytics.forecasting_v2.ports import V2SetupHistoryReader, V2VersionDrainStatusReader
from analytics.forecasting_v2.version_switch import (
    PHASE_AWAITING_ACTIVATION_READINESS, PHASE_DRAINING, PHASE_NO_PENDING_SWITCH,
    V2DrainFact, V2SemanticTuple, V2VersionSwitchError, V2VersionSwitchState,
    V2VersionSwitchTransitionResult, evaluate_version_switch_transition,
)

__all__ = ["resolve_version_switch_transition"]

# OLD's vacuous population when `state.active is None` (a fresh
# execution_stream that has never activated a tuple) -- there is nothing to
# drain, so this is supplied directly rather than issued as a query against
# a nonexistent OLD identity.
_VACUOUS_DRAIN = V2DrainFact(non_terminal_episode_count=0, active_cooldown_count=0)


def _validate_decision_boundary(value) -> datetime:
    """Identical pattern to every other H2a/H2b module's own private copy
    (see `version_switch.py`'s own docstring for why this is not shared as
    a cross-module import): delegates to `alignment.selected_bucket("5m",
    value)`, translating any exception -- expected or from a malformed/
    malicious custom `tzinfo` -- into this module's own domain error,
    exactly once, at this boundary."""
    try:
        selected_bucket("5m", value)
    except V2AlignmentError as exc:
        raise V2VersionSwitchError(f"decision_boundary: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - see module-level rationale above.
        raise V2VersionSwitchError(
            f"decision_boundary failed alignment validation: "
            f"{type(exc).__name__}: {exc}") from exc
    return value


async def resolve_version_switch_transition(
    *,
    state: V2VersionSwitchState,
    decision_boundary: datetime,
    symbol: str,
    market_type: str,
    requested: Optional[V2SemanticTuple],
    readiness_reader: V2SetupHistoryReader,
    drain_reader: V2VersionDrainStatusReader,
) -> V2VersionSwitchTransitionResult:
    """Resolve exactly one legal 5m decision boundary's version-switch
    transition for `state`'s `execution_stream`, issuing only the reads
    this specific call could possibly need.

    `symbol`/`market_type` are used ONLY for the §3.3 activation-readiness
    check (`check_activation_readiness`, already-merged H2a) -- never as
    part of the switch's own scope, which remains exactly
    `(state.run_kind, state.run_id)` per §12.10 (see `version_switch.py`'s
    module docstring for why).

    Any exception `readiness_reader`/`drain_reader` raises (a genuine
    reader/storage domain error -- corrupted or inconsistent row data)
    propagates UNCHANGED; it is never caught here and turned into a soft
    NOT_READY/NOT_DRAINED result (task requirement: reader/readiness
    corruption fails closed, never silently reinterpreted as legitimate
    absence)."""
    T = _validate_decision_boundary(decision_boundary)
    if requested is not None and not isinstance(requested, V2SemanticTuple):
        raise V2VersionSwitchError(
            f"requested must be None or a V2SemanticTuple, got {type(requested).__name__}")

    # ---- drain_fact: needed only while DRAINING, or when this call would
    # start a genuinely new switch from NO_PENDING_SWITCH. -----------------
    will_need_drain_fact = state.phase == PHASE_DRAINING or (
        state.phase == PHASE_NO_PENDING_SWITCH
        and requested is not None
        and requested != state.active)
    drain_fact = None
    if will_need_drain_fact:
        old = state.active
        if old is None:
            drain_fact = _VACUOUS_DRAIN
        else:
            drain_fact = await drain_reader.fetch_v2_version_drain_status(
                run_kind=state.run_kind, run_id=state.run_id,
                rules_version=old.rules_version,
                calculation_version=old.calculation_version,
                decision_code_version=old.decision_code_version,
                as_of=T)

    # ---- candidate_ready: needed only once drain is ALREADY known complete
    # from an earlier boundary AND this boundary is strictly later than
    # drain_complete_at -- reading it any earlier can never affect the
    # outcome (drain gates first, unconditionally), and is therefore never
    # attempted. -------------------------------------------------------------
    candidate_ready = None
    if (state.phase == PHASE_AWAITING_ACTIVATION_READINESS
            and T > state.drain_complete_at):
        candidate = state.pending
        readiness = await check_activation_readiness(
            readiness_reader, symbol=symbol, market_type=market_type,
            calculation_version=candidate.calculation_version, decision_boundary=T)
        candidate_ready = readiness.ready

    return evaluate_version_switch_transition(
        state, decision_boundary=T, requested=requested,
        drain_fact=drain_fact, candidate_ready=candidate_ready)
