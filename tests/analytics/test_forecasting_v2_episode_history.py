"""Pure-domain tests for Stage 6 Unit 1's episode-history foundation
(`analytics/forecasting_v2/episode_history.py`).

No database: every vector here is over already-read row mappings, exactly
the shape `storage/v2_episode_history_readers.py` returns. The real
PostgreSQL scope/ordering/isolation proofs live in
`tests/storage/test_v2_episode_history_readers.py`.

Rows are built through the CANONICAL construction path
(`event_factory.py::build_v2_episode_event()`), never by hand-assembling a
`V2EpisodeEvent` — so these fixtures cannot drift from what a real writer
would have persisted, and every `episode_id`/`event_id` here is a genuine
`episode_identity.py` digest rather than a placeholder.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from analytics.forecasting_v2.episode_history import (
    ANCHOR_BUCKET_TS, ANCHOR_LEVEL_NORMALIZED_PRICE, ANCHOR_LEVEL_TICK_INDEX,
    CREATION_IDENTITY_TICK_SIZE, HISTORY_BEFORE_T, HISTORY_THROUGH_T,
    NON_TERMINAL_EPISODE_STATES, TERMINAL_EPISODE_STATES,
    V2EpisodeHistoryCorruptionError, V2EpisodeHistoryError,
    V2EpisodeCreationIdentity, V2EpisodeHistory, V2PersistedEpisodeEvent,
    build_compression_breakout_anchor, build_confirmed_breakout_anchor,
    build_trend_pullback_anchor, canonical_decimal_text, normalize_price_to_tick,
    reconstruct_episode_history,
)
from analytics.forecasting_v2.episode_identity import compute_episode_id
from analytics.forecasting_v2.event_factory import build_v2_episode_event
from analytics.forecasting_v2.events import (
    COMPLETED, COMPRESSION_BREAKOUT, CONFIRMED, CONFIRMED_BREAKOUT, EARLY_SIGNAL,
    EXPIRED, INVALIDATED, LIVE, LONG, REPLAY, SHORT, TREND_PULLBACK, WEAKENING,
)
from analytics.forecasting_v2.provenance import V2EventProvenance
from common.v2_config import MODEL_FAMILY

UTC = timezone.utc
T0 = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)       # legal 5m boundary
H64 = "a" * 64
H16 = "b" * 16
RUN_ID = "v2-shadow-live"


def _t(n: int) -> datetime:
    return T0 + timedelta(minutes=5 * n)


def _q(n: int) -> datetime:
    """A legal 15m bucket START (family anchors live on the 15m grid)."""
    return T0 + timedelta(minutes=15 * n)


def _provenance(*, run_kind=LIVE, run_id=RUN_ID, **over) -> V2EventProvenance:
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


def _row(event) -> dict:
    """One persisted-row mapping, exactly the column set the storage reader
    selects (`created_at` deliberately excluded)."""
    return {
        "run_kind": event.run_kind, "run_id": event.run_id,
        "event_id": event.event_id, "episode_id": event.episode_id,
        "model_family": event.model_family, "rules_version": event.rules_version,
        "symbol": event.symbol, "market_type": event.market_type,
        "direction": event.direction, "setup_family": event.setup_family,
        "structural_anchor": dict(event.structural_anchor),
        "episode_state": event.episode_state,
        "decision_boundary": event.decision_boundary,
        "feature_schema_version": event.feature_schema_version,
        "calculation_version": event.calculation_version,
        "config_hash": event.config_hash, "config_version": event.config_version,
        "code_version": event.code_version,
        "decision_code_version": event.decision_code_version,
        "decision_snapshot": dict(event.decision_snapshot),
        "event_payload": dict(event.event_payload),
    }


def make_row(*, t_create=T0, decision_boundary=None, episode_state=EARLY_SIGNAL,
             direction=LONG, setup_family=TREND_PULLBACK, structural_anchor=None,
             provenance=None, decision_snapshot=None, event_payload=None) -> dict:
    """Build ONE persisted row through the canonical factory."""
    event = build_v2_episode_event(
        provenance if provenance is not None else _provenance(),
        t_create=t_create,
        direction=direction,
        setup_family=setup_family,
        structural_anchor=TP_ANCHOR if structural_anchor is None else structural_anchor,
        episode_state=episode_state,
        decision_boundary=t_create if decision_boundary is None else decision_boundary,
        decision_snapshot=decision_snapshot if decision_snapshot is not None else {"k": 1},
        event_payload=event_payload if event_payload is not None else {"p": 2},
    )
    return _row(event)


def _reconstruct(rows, *, run_kind=LIVE, run_id=RUN_ID, episode_id=None,
                 as_of=None, boundary_mode=HISTORY_THROUGH_T):
    episode_id = episode_id if episode_id is not None else rows[0]["episode_id"]
    as_of = as_of if as_of is not None else _t(100)
    return reconstruct_episode_history(
        rows, run_kind=run_kind, run_id=run_id, episode_id=episode_id,
        as_of=as_of, boundary_mode=boundary_mode)


# ============================================================================
# 1. §12.5 tick normalization (exact Decimal, never binary float)
# ============================================================================
@pytest.mark.parametrize(("raw", "tick", "index", "normalized"), [
    # §12.5's own worked-example table (tick_size = 0.1).
    (66200.04, 0.1, 662000, "66200.0"),
    (66200.05, 0.1, 662001, "66200.1"),   # exact half -> ROUND_HALF_UP
    (66200.06, 0.1, 662001, "66200.1"),
    # §12.5a's worked vector.
    (100.04, 0.1, 1000, "100.0"),
    (100.04, 0.01, 10004, "100.04"),
])
def test_tick_normalization_matches_contract_worked_examples(raw, tick, index, normalized):
    got_index, got_normalized = normalize_price_to_tick(raw, tick)
    assert got_index == index
    assert got_normalized == Decimal(normalized)


def test_tick_normalization_half_rounds_up_not_half_to_even():
    """§12.5 explicitly excludes Python's built-in `round()`, "whose
    binary-float/round-half-to-even semantics are not the contract being
    frozen here". 66200.05/0.1 is an exact half: ROUND_HALF_UP gives
    662001, round-half-to-even would give 662000."""
    assert normalize_price_to_tick(66200.05, 0.1)[0] == 662001
    assert round(66200.05 / 0.1) != 662001        # the wrong answer, pinned


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), "abc", None, True])
def test_tick_normalization_rejects_non_positive_or_malformed(bad):
    with pytest.raises(V2EpisodeHistoryError):
        normalize_price_to_tick(bad, 0.1)
    with pytest.raises(V2EpisodeHistoryError):
        normalize_price_to_tick(100.0, bad)


# ============================================================================
# 2. canonical per-family creation-anchor shapes (§12.1/§12.5a)
# ============================================================================
def test_trend_pullback_anchor_is_the_15m_extreme_bucket():
    anchor = build_trend_pullback_anchor(bucket_ts=T0)
    assert dict(anchor) == {ANCHOR_BUCKET_TS: T0.isoformat()}


def test_compression_breakout_anchor_is_the_first_compression_bucket():
    anchor = build_compression_breakout_anchor(bucket_ts=T0)
    assert dict(anchor) == {ANCHOR_BUCKET_TS: T0.isoformat()}


def test_confirmed_breakout_anchor_carries_the_frozen_creation_tick_grid():
    """§12.5a: the tick grid and the values it produces are recorded BY
    VALUE, as lossless strings/ints -- never JSON floats."""
    anchor = build_confirmed_breakout_anchor(
        level_anchor_bucket=T0, raw_level_price=66200.05, creation_identity_tick_size=0.1)
    assert dict(anchor) == {
        ANCHOR_BUCKET_TS: T0.isoformat(),
        ANCHOR_LEVEL_TICK_INDEX: 662001,
        ANCHOR_LEVEL_NORMALIZED_PRICE: "66200.1",
        CREATION_IDENTITY_TICK_SIZE: "0.1",
    }
    assert isinstance(anchor[ANCHOR_LEVEL_TICK_INDEX], int)
    for key in (ANCHOR_LEVEL_NORMALIZED_PRICE, CREATION_IDENTITY_TICK_SIZE):
        assert isinstance(anchor[key], str), f"{key} must persist as an exact string, never a float"


def test_anchors_are_immutable():
    anchor = build_trend_pullback_anchor(bucket_ts=T0)
    with pytest.raises(TypeError):
        anchor[ANCHOR_BUCKET_TS] = "tampered"


@pytest.mark.parametrize("bad", [
    "2026-08-20T12:00:00+00:00",                          # string, not datetime
    datetime(2026, 8, 20, 12, 0),                          # naive
    datetime(2026, 8, 20, 12, 0, tzinfo=timezone(timedelta(hours=2))),   # non-UTC
])
def test_anchor_builders_reject_bad_bucket(bad):
    with pytest.raises(V2EpisodeHistoryError):
        build_trend_pullback_anchor(bucket_ts=bad)


# ============================================================================
# 3. absent history is NOT corruption
# ============================================================================
def test_no_rows_returns_none_not_an_error():
    assert reconstruct_episode_history(
        (), run_kind=LIVE, run_id=RUN_ID, episode_id="c" * 64,
        as_of=T0, boundary_mode=HISTORY_THROUGH_T) is None


def test_malformed_scope_is_a_different_error_than_corruption():
    rows = [make_row()]
    with pytest.raises(V2EpisodeHistoryError) as exc:
        _reconstruct(rows, boundary_mode="WHENEVER")
    assert not isinstance(exc.value, V2EpisodeHistoryCorruptionError)


# ============================================================================
# 4. creation identity reconstruction + integrity
# ============================================================================
def test_creation_identity_comes_from_the_persisted_creation_event():
    rows = [
        make_row(decision_boundary=T0, episode_state=EARLY_SIGNAL),
        make_row(decision_boundary=_t(1), episode_state=CONFIRMED),
        make_row(decision_boundary=_t(2), episode_state=WEAKENING),
    ]
    history = _reconstruct(rows)
    identity = history.creation_identity
    assert identity.t_create == T0
    assert identity.episode_id == rows[0]["episode_id"]
    assert identity.direction == LONG
    assert identity.setup_family == TREND_PULLBACK
    assert dict(identity.structural_anchor) == dict(TP_ANCHOR)
    assert identity.slot == ("BTCUSDT", "perp", LONG, TREND_PULLBACK)
    # the creation event is explicit -- never events[0]-and-hope
    assert history.creation_event.episode_state == EARLY_SIGNAL
    assert history.creation_event.decision_boundary == T0
    # projection of the persisted position, not a decision
    assert history.current_state == WEAKENING
    assert history.is_terminal is False
    assert history.terminal_boundary is None


def test_episode_id_must_reproduce_from_its_own_creation_facts():
    """The persisted identity and the persisted contents must agree --
    proven by recomputing through H3's `compute_episode_id`, never a second
    hash implementation."""
    rows = [make_row()]
    rows[0]["episode_id"] = "f" * 64            # valid shape, wrong value
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="does not match its own persisted"):
        _reconstruct(rows, episode_id="f" * 64)


def test_event_id_must_reproduce_from_episode_id_and_boundary():
    rows = [make_row(), make_row(decision_boundary=_t(1), episode_state=CONFIRMED)]
    rows[1]["event_id"] = "e" * 64
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="compute_event_id"):
        _reconstruct(rows)


def test_oldest_event_must_be_early_signal():
    """RT-63-01: creation is identified by POSITION (the oldest event),
    which must be EARLY_SIGNAL -- an episode cannot have persisted history
    before its own creation, so t_create would be unrecoverable."""
    rows = [make_row(decision_boundary=_t(1), episode_state=CONFIRMED)]
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="oldest persisted event"):
        _reconstruct(rows)


def test_multiple_early_signal_events_are_legal_history():
    """RT-63-01: §12.2a explicitly allows a TREND_PULLBACK episode, WHILE
    STILL EARLY_SIGNAL, to record further material pre-confirmation updates
    as "a **new**, immutable history event". Such an episode legally has
    SEVERAL EARLY_SIGNAL events; it is still created exactly once."""
    rows = [
        make_row(decision_boundary=T0, episode_state=EARLY_SIGNAL),
        make_row(decision_boundary=_t(1), episode_state=EARLY_SIGNAL),
        make_row(decision_boundary=_t(2), episode_state=EARLY_SIGNAL),
        make_row(decision_boundary=_t(3), episode_state=CONFIRMED),
    ]
    history = _reconstruct(rows)
    assert len(history.events) == 4
    assert history.creation_identity.t_create == T0
    assert history.creation_event.decision_boundary == T0
    assert history.current_state == CONFIRMED


# ============================================================================
# 5. §12.2 creation identity is immutable across the episode
# ============================================================================
@pytest.mark.parametrize(("field", "value"), [
    ("direction", SHORT),
    ("setup_family", COMPRESSION_BREAKOUT),
    ("symbol", "ETHUSDT"),
    ("market_type", "spot"),
    ("rules_version", "v2-rules-v0.2.0"),
    ("calculation_version", "c" * 16),
])
def test_creation_identity_field_drift_mid_history_is_corruption(field, value):
    rows = [make_row(), make_row(decision_boundary=_t(1), episode_state=CONFIRMED)]
    rows[1][field] = value
    with pytest.raises(V2EpisodeHistoryError):
        _reconstruct(rows)


def test_structural_anchor_drift_mid_history_is_corruption():
    """§12.2: a later observed candidate anchor never rewrites creation
    identity -- it belongs in decision_snapshot/event_payload."""
    rows = [make_row(), make_row(decision_boundary=_t(1), episode_state=CONFIRMED)]
    rows[1]["structural_anchor"] = dict(build_trend_pullback_anchor(bucket_ts=_q(9)))
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="structural_anchor"):
        _reconstruct(rows)


def test_decision_code_version_may_legitimately_vary_across_events():
    """§3.2/§2.1a: `decision_code_version` is captured BY VALUE per event
    and is deliberately EXCLUDED from `episode_id`, precisely so a Stage 6
    bug-fix release does not fork an episode's semantic identity.
    Rejecting it here would contradict that frozen decision."""
    rows = [
        make_row(),
        make_row(decision_boundary=_t(1), episode_state=CONFIRMED,
                 provenance=_provenance(decision_code_version="decision-code-2")),
    ]
    history = _reconstruct(rows)
    assert history.events[0].decision_code_version == "decision-code-1"
    assert history.events[1].decision_code_version == "decision-code-2"
    assert history.creation_identity.episode_id == rows[0]["episode_id"]


# ============================================================================
# 6. execution namespace + as-of window
# ============================================================================
def test_foreign_execution_stream_row_is_corruption():
    rows = [make_row(), make_row(decision_boundary=_t(1), episode_state=CONFIRMED,
                                 provenance=_provenance(run_kind=REPLAY, run_id="replay-1"))]
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="execution_stream leak"):
        _reconstruct(rows)


def test_foreign_episode_row_is_corruption():
    rows = [make_row(), make_row(decision_boundary=_t(1), episode_state=CONFIRMED,
                                 structural_anchor=build_trend_pullback_anchor(bucket_ts=_q(7)),
                                 t_create=T0)]
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="episode leak"):
        _reconstruct(rows, episode_id=rows[0]["episode_id"])


def test_future_event_past_as_of_is_corruption():
    rows = [make_row(), make_row(decision_boundary=_t(5), episode_state=CONFIRMED)]
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="lookahead"):
        _reconstruct(rows, as_of=_t(2))


def test_before_t_mode_excludes_the_exact_boundary_row():
    """§13.4 step 1 reconstructs what was ACTIVE *immediately before* T --
    an event AT T is outside that window and must not leak in."""
    rows = [make_row(), make_row(decision_boundary=_t(2), episode_state=CONFIRMED)]
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="lookahead"):
        _reconstruct(rows, as_of=_t(2), boundary_mode=HISTORY_BEFORE_T)
    # ... while THROUGH_T (step 3b's cooldown window) legitimately includes it
    history = _reconstruct(rows, as_of=_t(2), boundary_mode=HISTORY_THROUGH_T)
    assert history.latest_event.decision_boundary == _t(2)


def test_boundary_mode_has_no_default():
    with pytest.raises(TypeError):
        reconstruct_episode_history(
            (), run_kind=LIVE, run_id=RUN_ID, episode_id="c" * 64, as_of=T0)


# ============================================================================
# 7. §2.1a one-event-per-T + deterministic ordering
# ============================================================================
def test_duplicate_decision_boundary_is_corruption_never_silently_resolved():
    rows = [make_row(), make_row(decision_boundary=T0, episode_state=CONFIRMED)]
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="share decision_boundary"):
        _reconstruct(rows)


def test_descending_rows_are_corruption():
    rows = [make_row(decision_boundary=_t(3), episode_state=CONFIRMED, t_create=T0),
            make_row(decision_boundary=T0, episode_state=EARLY_SIGNAL)]
    with pytest.raises(V2EpisodeHistoryCorruptionError):
        _reconstruct(rows)


# ============================================================================
# 8. terminal projection (a READ, never an eligibility decision)
# ============================================================================
@pytest.mark.parametrize("terminal", TERMINAL_EPISODE_STATES)
def test_terminal_boundary_is_the_terminal_events_own_boundary(terminal):
    # COMPLETED is only reachable from CONFIRMED/WEAKENING (§13.2), so the
    # vector walks a legal path rather than an impossible direct edge.
    rows = [make_row(),
            make_row(decision_boundary=_t(1), episode_state=CONFIRMED),
            make_row(decision_boundary=_t(4), episode_state=terminal)]
    history = _reconstruct(rows)
    assert history.is_terminal is True
    assert history.terminal_boundary == _t(4)      # §12.8's T_terminal, raw fact only


@pytest.mark.parametrize("state", NON_TERMINAL_EPISODE_STATES)
def test_non_terminal_states_report_no_terminal_boundary(state):
    if state == EARLY_SIGNAL:
        rows = [make_row()]
    elif state == CONFIRMED:
        rows = [make_row(), make_row(decision_boundary=_t(1), episode_state=CONFIRMED)]
    else:   # WEAKENING is reachable only from CONFIRMED (§13.2)
        rows = [make_row(),
                make_row(decision_boundary=_t(1), episode_state=CONFIRMED),
                make_row(decision_boundary=_t(2), episode_state=state)]
    history = _reconstruct(rows)
    assert history.is_terminal is False
    assert history.terminal_boundary is None


def test_terminal_and_non_terminal_partition_all_states():
    assert set(TERMINAL_EPISODE_STATES) == {INVALIDATED, EXPIRED, COMPLETED}
    assert not set(TERMINAL_EPISODE_STATES) & set(NON_TERMINAL_EPISODE_STATES)


# ============================================================================
# 9. as-of prefixes over one episode's life (§12.10 restart semantics)
# ============================================================================
def test_same_episode_at_three_boundaries_yields_growing_prefixes():
    """Creation identity is IDENTICAL at every snapshot; only the visible
    prefix and the projected current state grow."""
    all_rows = [
        make_row(decision_boundary=T0, episode_state=EARLY_SIGNAL),
        make_row(decision_boundary=_t(1), episode_state=CONFIRMED),
        make_row(decision_boundary=_t(2), episode_state=COMPLETED),
    ]
    expected = [(T0, 1, EARLY_SIGNAL), (_t(1), 2, CONFIRMED), (_t(2), 3, COMPLETED)]
    identities = []
    for as_of, count, state in expected:
        visible = [r for r in all_rows if r["decision_boundary"] <= as_of]
        history = _reconstruct(visible, as_of=as_of, boundary_mode=HISTORY_THROUGH_T)
        assert len(history.events) == count
        assert history.current_state == state
        identities.append(history.creation_identity)
    assert all(i == identities[0] for i in identities)
    assert all(i.t_create == T0 for i in identities)


# ============================================================================
# 10. LIVE/REPLAY: same semantic id, physically isolated histories
# ============================================================================
def test_live_and_replay_reproduce_the_same_episode_id():
    """§2.1a/§12.10: `run_kind`/`run_id` are the PHYSICAL namespace and are
    deliberately excluded from `episode_id`, so identical historical facts
    reproduce the identical semantic identity across streams."""
    live = make_row(provenance=_provenance(run_kind=LIVE, run_id="live-1"))
    replay = make_row(provenance=_provenance(run_kind=REPLAY, run_id="replay-1"))
    assert live["episode_id"] == replay["episode_id"]
    assert live["event_id"] == replay["event_id"]


def test_replay_history_cannot_be_reconstructed_under_the_live_stream():
    replay = make_row(provenance=_provenance(run_kind=REPLAY, run_id="replay-1"))
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="execution_stream leak"):
        _reconstruct([replay], run_kind=LIVE, run_id="live-1")


# ============================================================================
# 11. CONFIRMED_BREAKOUT tick-grid restart reconstruction (§12.5a)
# ============================================================================
def test_confirmed_breakout_creation_grid_survives_a_later_tick_size_change():
    """§12.5a's core restart guarantee: after the instrument's `tick_size`
    changes from 0.1 to 0.01, a reconstruction of the EXISTING episode must
    still report the CREATION grid (0.1) and the level it produced -- with
    no access to any current instrument metadata."""
    creation_tick, later_tick = 0.1, 0.01
    raw_level = 66200.04
    anchor = build_confirmed_breakout_anchor(
        level_anchor_bucket=T0, raw_level_price=raw_level,
        creation_identity_tick_size=creation_tick)
    rows = [
        make_row(setup_family=CONFIRMED_BREAKOUT, structural_anchor=anchor),
        make_row(decision_boundary=_t(3), episode_state=CONFIRMED,
                 setup_family=CONFIRMED_BREAKOUT, structural_anchor=anchor),
    ]
    identity = _reconstruct(rows).creation_identity

    assert identity.creation_identity_tick_size == Decimal("0.1")
    assert identity.creation_level_tick_index == 662000
    assert identity.creation_normalized_level_price == Decimal("66200.0")

    # The SAME raw level on today's finer grid would normalize differently --
    # which is exactly the value the reconstruction must NOT report.
    assert normalize_price_to_tick(raw_level, later_tick) == (6620004, Decimal("66200.04"))
    assert identity.creation_level_tick_index != 6620004


def test_non_confirmed_breakout_families_report_no_tick_grid():
    identity = _reconstruct([make_row()]).creation_identity
    assert identity.creation_identity_tick_size is None
    assert identity.creation_level_tick_index is None
    assert identity.creation_normalized_level_price is None


# ============================================================================
# 12. deep immutability of everything handed downstream
# ============================================================================
def test_reconstructed_history_is_deeply_immutable():
    rows = [make_row(decision_snapshot={"nested": {"a": [1, 2]}})]
    history = _reconstruct(rows)
    event = history.events[0]

    with pytest.raises(TypeError):
        event.decision_snapshot["nested"] = "tampered"
    with pytest.raises(TypeError):
        event.decision_snapshot["nested"]["a"] = "tampered"
    assert isinstance(event.decision_snapshot["nested"]["a"], tuple)
    with pytest.raises(AttributeError):
        event.episode_state = COMPLETED
    with pytest.raises(AttributeError):
        history.creation_identity.t_create = _t(9)
    assert isinstance(history.events, tuple)


def test_mutating_the_caller_s_source_dict_cannot_change_the_history():
    """Deep detachment: the reconstruction must retain NO reference to a
    caller-owned mutable structure. The row is rebuilt here with genuinely
    mutable nested dicts/lists (the canonical factory already deep-freezes
    its own inputs, so a factory-built row could not prove this)."""
    source = make_row()
    source["decision_snapshot"] = {"nested": {"a": [1, 2]}}
    history = _reconstruct([source])

    source["decision_snapshot"]["nested"]["a"].append(3)
    source["decision_snapshot"]["nested"]["b"] = "added"
    source["episode_state"] = COMPLETED

    assert history.events[0].decision_snapshot["nested"]["a"] == (1, 2)
    assert "b" not in history.events[0].decision_snapshot["nested"]
    assert history.events[0].episode_state == EARLY_SIGNAL


# ============================================================================
# 13. malformed persisted shapes fail closed
# ============================================================================
@pytest.mark.parametrize("field", [
    "run_kind", "episode_state", "direction", "setup_family", "structural_anchor",
    "decision_boundary", "event_id", "feature_schema_version", "calculation_version",
])
def test_missing_required_column_fails_closed(field):
    rows = [make_row()]
    del rows[0][field]
    with pytest.raises(V2EpisodeHistoryError):
        _reconstruct(rows, episode_id=make_row()["episode_id"])


@pytest.mark.parametrize("bad_anchor", ["not-an-object", 5, None, ["a"]])
def test_non_object_structural_anchor_fails_closed(bad_anchor):
    rows = [make_row()]
    rows[0]["structural_anchor"] = bad_anchor
    with pytest.raises(V2EpisodeHistoryError):
        _reconstruct(rows, episode_id=make_row()["episode_id"])


def test_off_grid_creation_boundary_is_corruption():
    """A creation event whose boundary is not a legal 5m V2 boundary could
    never have been produced by the canonical factory."""
    rows = [make_row()]
    rows[0]["decision_boundary"] = T0 + timedelta(minutes=2)
    with pytest.raises(V2EpisodeHistoryError):
        _reconstruct(rows, episode_id=rows[0]["episode_id"])


def test_rows_must_be_a_sequence_of_mappings():
    with pytest.raises(V2EpisodeHistoryError):
        _reconstruct(["not-a-row"], episode_id="c" * 64)


# ============================================================================
# 14. canonical-factory architecture invariant (Stage 6 guard)
# ============================================================================
def test_only_the_canonical_factory_constructs_v2_episode_event():
    """Production code MUST NOT call `V2EpisodeEvent(...)` directly for real
    event construction — `event_factory.py::build_v2_episode_event()` is the
    ONE canonical path, because it alone computes `episode_id`/`event_id`
    deterministically via `episode_identity.py` instead of accepting opaque
    caller-supplied strings.

    Stage 6 Unit 1 is on the READ side and constructs no events at all;
    this scan exists so units 2-5, which WILL construct them, cannot
    quietly bypass the factory. `event_factory.py` itself is the single
    allowed construction site by definition."""
    import ast
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    allowed = {repo_root / "analytics" / "forecasting_v2" / "event_factory.py"}
    offenders = []
    for package in ("analytics", "storage", "runtime", "common"):
        for path in sorted((repo_root / package).rglob("*.py")):
            if path in allowed:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                # BOTH spellings: the bare imported name `V2EpisodeEvent(...)`
                # AND the attribute form `events.V2EpisodeEvent(...)` / any
                # `<module>.V2EpisodeEvent(...)`, which a name-only scan would
                # silently miss (CodeRabbit finding).
                called = (
                    func.id if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute)
                    else None)
                if called == "V2EpisodeEvent":
                    offenders.append(f"{path.relative_to(repo_root)}:{node.lineno}")

    assert offenders == [], (
        "V2EpisodeEvent must only ever be constructed by "
        "analytics/forecasting_v2/event_factory.py::build_v2_episode_event(); "
        f"direct construction found at: {offenders}")


# ============================================================================
# 15. RT-63-02 -- §13.2 persisted state SEQUENCE integrity
# ============================================================================
def _seq(*states):
    """A history walking the given states at consecutive 5m boundaries."""
    return [make_row(decision_boundary=_t(i), episode_state=s) for i, s in enumerate(states)]


def test_terminal_resurrection_is_rejected():
    """§13.2 gives terminal states no outgoing edges, so an episode's
    history ends there."""
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="terminal"):
        _reconstruct(_seq(EARLY_SIGNAL, CONFIRMED, INVALIDATED, CONFIRMED))


def test_any_event_after_a_terminal_event_is_rejected():
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="AFTER it reached the terminal"):
        _reconstruct(_seq(EARLY_SIGNAL, CONFIRMED, COMPLETED, WEAKENING))


def test_same_state_event_after_terminal_is_also_rejected():
    """Fail-closed: nothing in the frozen contract permits a post-terminal
    observation, not even a same-state one."""
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="AFTER it reached the terminal"):
        _reconstruct(_seq(EARLY_SIGNAL, CONFIRMED, EXPIRED, EXPIRED))


@pytest.mark.parametrize(("previous", "illegal"), [
    (EARLY_SIGNAL, WEAKENING),    # §13.2: EARLY_SIGNAL never goes straight to WEAKENING
    (EARLY_SIGNAL, COMPLETED),    # ... nor straight to COMPLETED
])
def test_illegal_state_changing_edge_is_rejected(previous, illegal):
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="does not allow"):
        _reconstruct(_seq(previous, illegal))


@pytest.mark.parametrize("states", [
    (EARLY_SIGNAL, CONFIRMED),
    (EARLY_SIGNAL, INVALIDATED),
    (EARLY_SIGNAL, EXPIRED),
    (EARLY_SIGNAL, CONFIRMED, WEAKENING, CONFIRMED),        # §13.2 recovery
    (EARLY_SIGNAL, CONFIRMED, WEAKENING, COMPLETED),
    (EARLY_SIGNAL, EARLY_SIGNAL, CONFIRMED, INVALIDATED),   # §12.2a same-state update
])
def test_legal_state_sequences_are_accepted(states):
    history = _reconstruct(_seq(*states))
    assert history.current_state == states[-1]
    assert history.creation_identity.t_create == T0


def test_same_state_confirmed_event_is_not_a_transition():
    """A same-state event is a NEW event that leaves the episode where it
    was -- never a self-edge the §13.2 graph must draw."""
    history = _reconstruct(_seq(EARLY_SIGNAL, CONFIRMED, CONFIRMED))
    assert history.current_state == CONFIRMED
    assert len(history.events) == 3


# ============================================================================
# 16. RT-63-03/off-grid boundaries
# ============================================================================
@pytest.mark.parametrize("bad_as_of", [
    datetime(2026, 8, 20, 12, 3, tzinfo=UTC),                  # not on the 5m grid
    datetime(2026, 8, 20, 12, 10, 1, tzinfo=UTC),               # stray second
    datetime(2026, 8, 20, 12, 10, 0, 500000, tzinfo=UTC),       # stray microsecond
])
@pytest.mark.parametrize("mode", [HISTORY_BEFORE_T, HISTORY_THROUGH_T])
def test_off_grid_as_of_is_rejected_in_both_modes(bad_as_of, mode):
    with pytest.raises(V2EpisodeHistoryError, match="5m decision boundary"):
        reconstruct_episode_history(
            (), run_kind=LIVE, run_id=RUN_ID, episode_id="c" * 64,
            as_of=bad_as_of, boundary_mode=mode)


@pytest.mark.parametrize("mode", [HISTORY_BEFORE_T, HISTORY_THROUGH_T])
def test_legal_as_of_is_accepted_in_both_modes(mode):
    assert reconstruct_episode_history(
        (), run_kind=LIVE, run_id=RUN_ID, episode_id="c" * 64,
        as_of=datetime(2026, 8, 20, 12, 10, tzinfo=UTC), boundary_mode=mode) is None


def test_off_grid_later_persisted_event_is_corruption_not_an_identity_error():
    """A corrupt persisted boundary must surface inside THIS module's error
    hierarchy, never as a foreign V2EpisodeIdentityError escaping from
    compute_event_id()."""
    rows = [make_row(), make_row(decision_boundary=_t(1), episode_state=CONFIRMED)]
    rows[1]["decision_boundary"] = T0 + timedelta(minutes=7)
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="5m decision boundary"):
        _reconstruct(rows)


def test_off_grid_creation_boundary_is_exactly_the_corruption_subclass():
    rows = [make_row()]
    rows[0]["decision_boundary"] = T0 + timedelta(minutes=2)
    with pytest.raises(V2EpisodeHistoryCorruptionError):
        _reconstruct(rows, episode_id=rows[0]["episode_id"])


# ============================================================================
# 17. RT-63-04 -- family anchor grids
# ============================================================================
@pytest.mark.parametrize("builder", [
    build_trend_pullback_anchor, build_compression_breakout_anchor])
@pytest.mark.parametrize("minutes", [7, 10, 5, 1])
def test_15m_family_anchors_reject_off_grid_buckets(builder, minutes):
    with pytest.raises(V2EpisodeHistoryError, match="15m bucket"):
        builder(bucket_ts=T0 + timedelta(minutes=minutes))


@pytest.mark.parametrize("minutes", [0, 15, 30, 45])
def test_15m_family_anchors_accept_real_grid_starts(minutes):
    ts = T0 + timedelta(minutes=minutes)
    for builder in (build_trend_pullback_anchor, build_compression_breakout_anchor):
        assert builder(bucket_ts=ts)[ANCHOR_BUCKET_TS] == ts.isoformat()


@pytest.mark.parametrize("minutes", [15, 30, 7, 45])
def test_confirmed_breakout_anchor_rejects_non_1h_buckets(minutes):
    with pytest.raises(V2EpisodeHistoryError, match="1h bucket"):
        build_confirmed_breakout_anchor(
            level_anchor_bucket=T0 + timedelta(minutes=minutes),
            raw_level_price=100.0, creation_identity_tick_size=0.1)


@pytest.mark.parametrize("hours", [0, 1, 5])
def test_confirmed_breakout_anchor_accepts_real_1h_starts(hours):
    ts = T0 + timedelta(hours=hours)
    anchor = build_confirmed_breakout_anchor(
        level_anchor_bucket=ts, raw_level_price=100.0, creation_identity_tick_size=0.1)
    assert anchor[ANCHOR_BUCKET_TS] == ts.isoformat()


# ============================================================================
# 18. RT-63-05 -- canonical Decimal textual identity
# ============================================================================
@pytest.mark.parametrize("equivalents", [
    ["0.1", "0.10", "1E-1", "0.100"],
    ["100", "100.0", "1E2", "100.00"],
    ["0.01", "1E-2", "0.010"],
])
def test_equivalent_decimals_share_one_canonical_text(equivalents):
    texts = {canonical_decimal_text(Decimal(v)) for v in equivalents}
    assert len(texts) == 1, f"{equivalents} -> {texts}"


def test_canonical_text_is_plain_notation_never_scientific():
    for value in ("1E2", "1E+10", "1E-3"):
        assert "E" not in canonical_decimal_text(Decimal(value)).upper()


def test_equivalent_tick_representations_produce_identical_anchor_and_episode_id():
    """The load-bearing consequence: `structural_anchor` feeds
    `compute_episode_id()`, so formatting alone must never fork identity."""
    anchors = [
        build_confirmed_breakout_anchor(
            level_anchor_bucket=T0, raw_level_price="66200.04",
            creation_identity_tick_size=Decimal(tick))
        for tick in ("0.1", "0.10", "1E-1")
    ]
    assert all(dict(a) == dict(anchors[0]) for a in anchors)

    episode_ids = {
        make_row(setup_family=CONFIRMED_BREAKOUT, structural_anchor=a)["episode_id"]
        for a in anchors
    }
    assert len(episode_ids) == 1


# ============================================================================
# 19. persisted CONFIRMED_BREAKOUT anchor type/coherence integrity
# ============================================================================
CB_ANCHOR = build_confirmed_breakout_anchor(
    level_anchor_bucket=T0, raw_level_price="66200.04", creation_identity_tick_size="0.1")


def _cb_rows(**anchor_over):
    anchor = dict(CB_ANCHOR)
    anchor.update(anchor_over)
    rows = [make_row(setup_family=CONFIRMED_BREAKOUT, structural_anchor=CB_ANCHOR)]
    rows[0]["structural_anchor"] = anchor
    return rows


@pytest.mark.parametrize("key", [CREATION_IDENTITY_TICK_SIZE, ANCHOR_LEVEL_NORMALIZED_PRICE])
@pytest.mark.parametrize("bad", [0.1, 1, True, None, ["0.1"]])
def test_persisted_decimal_anchor_fields_reject_non_string(key, bad):
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="exact decimal string"):
        _reconstruct(_cb_rows(**{key: bad}))


@pytest.mark.parametrize("bad", [True, False, "662000", 662000.0, None])
def test_persisted_tick_index_rejects_bool_and_non_int(bad):
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="exact JSON integer"):
        _reconstruct(_cb_rows(**{ANCHOR_LEVEL_TICK_INDEX: bad}))


@pytest.mark.parametrize("bad", ["not-a-decimal", "", "NaN", "Infinity", "-0.1", "0"])
def test_malformed_persisted_decimal_strings_are_corruption(bad):
    with pytest.raises(V2EpisodeHistoryCorruptionError,
                       match=CREATION_IDENTITY_TICK_SIZE):
        _reconstruct(_cb_rows(**{CREATION_IDENTITY_TICK_SIZE: bad}))


def test_incoherent_persisted_tick_grid_is_corruption():
    """normalized must equal tick_index * tick (§12.5)."""
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="incoherent"):
        _reconstruct(_cb_rows(**{ANCHOR_LEVEL_NORMALIZED_PRICE: "99999.9"}))


def test_confirmed_breakout_missing_creation_tick_grid_is_corruption():
    anchor = {ANCHOR_BUCKET_TS: T0.isoformat()}
    rows = [make_row(setup_family=CONFIRMED_BREAKOUT, structural_anchor=CB_ANCHOR)]
    rows[0]["structural_anchor"] = anchor
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="missing required creation"):
        _reconstruct(rows)


def test_non_confirmed_breakout_family_carrying_tick_fields_is_corruption():
    """`structural_anchor` IS the semantic identity -- a bucket-only family
    must not smuggle extra identity fields into it (later observations
    belong in decision_snapshot/event_payload)."""
    rows = [make_row()]
    rows[0]["structural_anchor"] = dict(CB_ANCHOR)
    with pytest.raises(V2EpisodeHistoryCorruptionError,
                       match="carries CONFIRMED_BREAKOUT tick-grid field"):
        _reconstruct(rows, episode_id=rows[0]["episode_id"])


# ============================================================================
# 20. decimal-precision failures stay inside the domain error hierarchy
# ============================================================================
@pytest.mark.parametrize(("price", "tick"), [
    ("1E+1000000", "1E-1000000"),   # overflow
    ("1E-1000000", "1E+1000000"),   # underflow -> would round to the zero tick
])
def test_extreme_precision_normalization_stays_in_the_domain_error_hierarchy(price, tick):
    """An extreme but syntactically valid ratio can exceed the decimal
    context's precision/exponent range; it must never leak a raw
    decimal.DecimalException, and must never silently produce a degenerate
    zero-priced identity."""
    with pytest.raises(V2EpisodeHistoryError):
        normalize_price_to_tick(Decimal(price), Decimal(tick))


def test_price_rounding_down_to_the_zero_tick_is_rejected():
    """A positive structural level can never normalize to a zero price."""
    with pytest.raises(V2EpisodeHistoryError, match="normalized price of zero"):
        normalize_price_to_tick(0.04, 0.1)


# ============================================================================
# 21. RT-63-06 -- non-finite floats rejected on the READ path
# ============================================================================
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("column", ["decision_snapshot", "event_payload"])
def test_non_finite_floats_in_persisted_json_are_rejected(bad, column):
    rows = [make_row()]
    rows[0][column] = {"nested": {"v": bad}}
    with pytest.raises(V2EpisodeHistoryError, match="non-finite"):
        _reconstruct(rows, episode_id=rows[0]["episode_id"])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_floats_in_structural_anchor_are_rejected(bad):
    rows = [make_row()]
    rows[0]["structural_anchor"] = {ANCHOR_BUCKET_TS: T0.isoformat(), "junk": bad}
    with pytest.raises(V2EpisodeHistoryError, match="non-finite"):
        _reconstruct(rows, episode_id=rows[0]["episode_id"])


# ============================================================================
# 22. RT-63-07 -- public value objects uphold deep immutability themselves
# ============================================================================
def test_directly_constructed_creation_identity_is_deeply_immutable():
    source = {"nested": {"a": [1, 2]}}
    identity = V2EpisodeCreationIdentity(
        episode_id="a" * 64, t_create=T0, model_family=MODEL_FAMILY,
        rules_version="v2-rules-v0.1.0", calculation_version=H16,
        symbol="BTCUSDT", market_type="perp", direction=LONG,
        setup_family=TREND_PULLBACK, structural_anchor=source)
    source["nested"]["a"].append(3)
    source["nested"]["b"] = "added"

    assert identity.structural_anchor["nested"]["a"] == (1, 2)
    assert "b" not in identity.structural_anchor["nested"]
    with pytest.raises(TypeError):
        identity.structural_anchor["nested"]["a"] = "tampered"


def test_directly_constructed_persisted_event_is_deeply_immutable():
    source = {"nested": {"a": 1}}
    row = make_row()
    event = V2PersistedEpisodeEvent(
        run_kind=LIVE, run_id=RUN_ID, event_id=row["event_id"],
        episode_id=row["episode_id"], model_family=MODEL_FAMILY,
        rules_version="v2-rules-v0.1.0", symbol="BTCUSDT", market_type="perp",
        direction=LONG, setup_family=TREND_PULLBACK,
        structural_anchor=dict(TP_ANCHOR), episode_state=EARLY_SIGNAL,
        decision_boundary=T0, feature_schema_version=1, calculation_version=H16,
        config_hash=H64, config_version="2.1.0", code_version="c",
        decision_code_version="d", decision_snapshot=source, event_payload={})
    source["nested"]["a"] = 999

    assert event.decision_snapshot["nested"]["a"] == 1
    with pytest.raises(TypeError):
        event.decision_snapshot["nested"]["a"] = 7


def test_history_rejects_a_non_event_sequence():
    with pytest.raises(V2EpisodeHistoryError):
        V2EpisodeHistory(
            run_kind=LIVE, run_id=RUN_ID, episode_id="a" * 64, as_of=T0,
            boundary_mode=HISTORY_THROUGH_T, events=("not-an-event",),
            creation_identity=_reconstruct([make_row()]).creation_identity)


# ============================================================================
# 23. RT-63-R1 -- persisted structural_anchor.bucket_ts family-grid integrity
# ============================================================================
def _self_consistent_row(*, bucket_ts, setup_family, with_tick_grid=None):
    """A persisted row whose `episode_id`/`event_id` are recomputed FROM the
    given (possibly malformed) anchor, so identity revalidation passes and
    only an independent grid check can catch the corruption.

    The canonical builders reject off-grid buckets outright, so the anchor
    is assembled directly here -- which is exactly the corrupt-storage shape
    this module must survive after restart/replay."""
    anchor = {ANCHOR_BUCKET_TS: bucket_ts}
    if with_tick_grid is not None:
        anchor.update({k: v for k, v in with_tick_grid.items() if k != ANCHOR_BUCKET_TS})
    return make_row(setup_family=setup_family, structural_anchor=anchor)


_CB_GRID = dict(build_confirmed_breakout_anchor(
    level_anchor_bucket=T0, raw_level_price="100.0", creation_identity_tick_size="0.1"))


@pytest.mark.parametrize("family", [TREND_PULLBACK, COMPRESSION_BREAKOUT])
@pytest.mark.parametrize("minutes", [10, 7, 1, 5])
def test_persisted_15m_family_anchor_off_grid_is_corruption(family, minutes):
    """RT-63-R1: a self-consistently-hashed row whose persisted anchor is
    not a 15m bucket start must fail closed -- identity revalidation alone
    cannot catch it."""
    row = _self_consistent_row(
        bucket_ts=(T0 + timedelta(minutes=minutes)).isoformat(), setup_family=family)
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="15m bucket start"):
        _reconstruct([row], episode_id=row["episode_id"])


@pytest.mark.parametrize("family", [TREND_PULLBACK, COMPRESSION_BREAKOUT])
@pytest.mark.parametrize("minutes", [0, 15, 30, 45])
def test_persisted_15m_family_anchor_on_grid_reconstructs(family, minutes):
    ts = T0 + timedelta(minutes=minutes)
    row = _self_consistent_row(bucket_ts=ts.isoformat(), setup_family=family)
    history = _reconstruct([row], episode_id=row["episode_id"])
    assert history.creation_identity.structural_anchor[ANCHOR_BUCKET_TS] == ts.isoformat()


@pytest.mark.parametrize("minutes", [15, 30, 45, 7])
def test_persisted_confirmed_breakout_anchor_off_1h_grid_is_corruption(minutes):
    row = _self_consistent_row(
        bucket_ts=(T0 + timedelta(minutes=minutes)).isoformat(),
        setup_family=CONFIRMED_BREAKOUT, with_tick_grid=_CB_GRID)
    with pytest.raises(V2EpisodeHistoryCorruptionError, match="1h bucket start"):
        _reconstruct([row], episode_id=row["episode_id"])


@pytest.mark.parametrize("hours", [0, 1, 2])
def test_persisted_confirmed_breakout_anchor_on_1h_grid_reconstructs(hours):
    ts = T0 + timedelta(hours=hours)
    row = _self_consistent_row(
        bucket_ts=ts.isoformat(), setup_family=CONFIRMED_BREAKOUT, with_tick_grid=_CB_GRID)
    history = _reconstruct([row], episode_id=row["episode_id"])
    assert history.creation_identity.structural_anchor[ANCHOR_BUCKET_TS] == ts.isoformat()


@pytest.mark.parametrize("bad", [
    "not-an-iso-date",
    "",
    "2026-08-20T12:00:00",          # naive
    "2026-08-20T12:00:00+02:00",    # non-UTC offset
])
def test_malformed_persisted_bucket_ts_is_corruption(bad):
    row = _self_consistent_row(bucket_ts=bad, setup_family=TREND_PULLBACK)
    with pytest.raises(V2EpisodeHistoryCorruptionError):
        _reconstruct([row], episode_id=row["episode_id"])


def test_persisted_anchor_grid_is_checked_even_when_ids_are_self_consistent():
    """Pins the exact reason this check must exist: the corrupt row's own
    episode_id genuinely recomputes from its own contents, so the identity
    revalidation step passes and cannot be what rejects it."""
    row = _self_consistent_row(
        bucket_ts=(T0 + timedelta(minutes=10)).isoformat(), setup_family=TREND_PULLBACK)
    recomputed = compute_episode_id(
        model_family=MODEL_FAMILY, rules_version="v2-rules-v0.1.0",
        calculation_version=H16, symbol="BTCUSDT", market_type="perp",
        direction=LONG, setup_family=TREND_PULLBACK,
        structural_anchor=row["structural_anchor"], t_create=T0)
    assert recomputed == row["episode_id"], "fixture must be self-consistent to be meaningful"

    with pytest.raises(V2EpisodeHistoryCorruptionError, match="15m bucket start"):
        _reconstruct([row], episode_id=row["episode_id"])
