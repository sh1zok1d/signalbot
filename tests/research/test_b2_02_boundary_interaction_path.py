from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from scripts.research import b2_02_boundary_interaction_path_lib as lib
from scripts.research.lib.batch02_source_policy import (
    validate_batch02_source_tree,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = REPO_ROOT / "scripts" / "research"
PREREG = (
    REPO_ROOT
    / "docs"
    / "research"
    / "B2_02_BOUNDARY_INTERACTION_PATH_PREREG.json"
)


def _small_frame(n: int = 10) -> dict[str, np.ndarray]:
    open_ms = (
        lib.WARMUP_START_MS
        + np.arange(n, dtype=np.int64) * lib.BAR_MS
    )
    close = 100.0 + np.arange(n, dtype=np.float64) * 0.01
    opn = np.concatenate(([100.0], close[:-1]))
    high = np.maximum(opn, close) + 0.05
    low = np.minimum(opn, close) - 0.05
    return {
        "open_time_ms": open_ms,
        "available_at_ms": open_ms + lib.BAR_MS,
        "open": opn,
        "high": high,
        "low": low,
        "close": close,
    }


def _cell(L: int, H: int, passed: bool, stable: bool) -> dict:
    gates = {
        name: passed
        for name in lib.PER_CELL_GATE_NAMES
    }
    return {
        "L": L,
        "H": H,
        "per_cell_gates": gates,
        "year_stability_pass": stable,
    }


def test_prereg_constants_match_implementation_freeze():
    freeze = json.loads(PREREG.read_text(encoding="utf-8"))
    assert freeze["formulation_id"] == lib.HYPOTHESIS_ID
    assert freeze["dataset"]["dataset_id"] == lib.DATASET_ID
    assert freeze["dataset"]["snapshot_id"] == lib.REQUIRED_SNAPSHOT
    assert tuple(freeze["prior_range_lookbacks_minutes"]) == lib.LOOKBACKS
    assert tuple(freeze["horizons_minutes"]) == lib.HORIZONS
    assert freeze["chronology"]["path_observation_minutes"] == lib.PATH_MIN
    assert freeze["forecast"]["training_lookback_days"] == lib.TRAIN_DAYS
    assert freeze["forecast"]["baseline_min_count"] == lib.BASELINE_MIN_COUNT
    assert freeze["forecast"]["candidate_min_count"] == lib.CANDIDATE_MIN_COUNT
    assert tuple(
        freeze["promotion_gate_contract"]["required_gate_names"]
    ) == lib.GATE_NAMES
    assert freeze["search_surface_primary_cells"] == 12
    assert freeze["outcome_access_authorized"] is False
    assert freeze["validation_2025_authorized"] is False
    assert freeze["oos_2026_authorized"] is False


def test_aggregate_1m_to_5m_uses_complete_buckets_and_availability():
    frame = _small_frame(10)
    five = lib.aggregate_1m_to_5m(frame)
    assert len(five["close"]) == 2
    assert five["open"][0] == frame["open"][0]
    assert five["close"][0] == frame["close"][4]
    assert five["high"][0] == np.max(frame["high"][:5])
    assert five["low"][0] == np.min(frame["low"][:5])
    assert five["available_at_ms"][0] == lib.WARMUP_START_MS + 5 * lib.BAR_MS


def test_context_and_path_states_are_causal_same_L():
    base = lib.DEV_START_MS
    events = []
    for i, value in enumerate((1.0, 2.0, 3.0, 4.0)):
        t0 = base + i * lib.DAY_MS
        events.append(
            {
                "L": 60,
                "side": "UPPER",
                "direction": 1,
                "T0": t0,
                "T": t0 + lib.PATH_MS,
                "T_index": i,
                "breach_mag": value,
                "pre_vol": value,
                "pre_drift": value,
                "residence": value / 4.0,
                "terminal_extension": value,
                "max_extension": value,
                "path_efficiency": value / 10.0,
            }
        )
    states = lib.attach_states(events)
    assert states[0]["breach_state"] == lib.STATE_MISSING
    assert states[0]["path_state"] == lib.STATE_MISSING
    assert states[1]["breach_state"] == lib.STATE_HIGH
    assert states[1]["pre_vol_state"] == lib.STATE_HIGH
    assert states[1]["pre_drift_state"] == lib.STATE_HIGH
    assert states[1]["path_state"] == lib.STATE_HIGH


def test_event_identity_binds_timeframes_and_horizon():
    event = {
        "L": 120,
        "side": "LOWER",
        "T0": 123,
        "T": 456,
    }
    identity = lib._event_id(event, 60)
    assert identity.split("|") == [
        lib.REQUIRED_SNAPSHOT,
        "1m",
        "5m",
        "120",
        "LOWER",
        "123",
        "456",
        "60",
    ]


def test_training_maturity_respects_horizon(monkeypatch):
    monkeypatch.setattr(lib, "N_PLACEBO", 5)
    monkeypatch.setattr(lib, "N_BOOT", 20)
    monkeypatch.setattr(
        lib,
        "_target_scale",
        lambda close, H: np.ones(len(close), dtype=np.float64),
    )

    frame5 = {
        "close": 100.0 + np.arange(800, dtype=np.float64) * 0.01,
    }
    events = []
    for i in range(100):
        t = lib.DEV_START_MS + i * lib.PATH_MS
        events.append(
            {
                "L": 60,
                "side": "UPPER",
                "direction": 1,
                "T0": t - lib.PATH_MS,
                "T": t,
                "T_index": i * lib.PATH_BARS,
                "breach_state": 1,
                "pre_vol_state": 1,
                "pre_drift_state": 1,
                "path_state": 1,
            }
        )

    c30 = lib.evaluate_cell(frame5, events, 60, 30)
    c60 = lib.evaluate_cell(frame5, events, 60, 60)
    assert c30["N"] == 20
    assert c60["N"] == 19
    assert len(c30["event_ids"]) == c30["N"]
    assert all(event_id.endswith("|30") for event_id in c30["event_ids"])


def test_promotion_requires_same_adjacent_h_pair_on_two_L_values():
    cells = [
        _cell(L, H, passed=(L in {60, 120} and H in {30, 60}), stable=(L in {60, 120} and H in {30, 60}))
        for L in lib.LOOKBACKS
        for H in lib.HORIZONS
    ]
    gates, selected = lib.determine_promotion_gates(cells)
    assert gates == {
        "primary_positive": True,
        "material_relative_mae": True,
        "bootstrap_positive": True,
        "placebo_separation": True,
        "path_ordering": True,
        "horizon_robustness": True,
        "parameter_robustness": True,
        "year_stability": True,
    }
    assert selected == [
        {"L": 60, "H": 30},
        {"L": 60, "H": 60},
        {"L": 120, "H": 30},
        {"L": 120, "H": 60},
    ]


def test_actual_future_b2_source_tree_passes_canonical_policy():
    visited = validate_batch02_source_tree(
        RESEARCH_DIR,
        repo_root=REPO_ROOT,
    )
    names = {path.name for path in visited}
    assert "b2_02_boundary_interaction_path.py" in names
    assert "b2_02_boundary_interaction_path_lib.py" in names


# ---------------------------------------------------------------------------
# Breach-geometry / refractory fixtures.
#
# A canonical 1m frame is built so that its 5m aggregation is exactly the bars
# requested. The base tape oscillates so every prior range is strictly positive
# (prior_log_range > 0) and every 1m return is finite, which is what the frozen
# qualification and PRE_VOL rules require before geometry can even be tested.
# ---------------------------------------------------------------------------

# 5m bar whose T0 is the first legal development T0 (2020-02-01T00:00:00Z).
FIRST_DEV_BAR = (lib.DEV_START_MS - lib.WARMUP_START_MS) // lib.FIVE_MS - 1
BASE_HIGH = 100.5
BASE_LOW = 99.5
BASE_OPEN = 100.0


def _blank_5m_bars(count: int) -> list[list[float]]:
    """Quiet oscillating base tape: open inside a strictly positive range."""
    return [[BASE_OPEN, BASE_HIGH, BASE_LOW, BASE_OPEN] for _ in range(count)]


def _frame_from_5m(bars: list[list[float]]) -> dict[str, np.ndarray]:
    """Canonical 1m frame whose exact 5m aggregation is `bars`."""
    n = len(bars) * lib.FIVE_MIN
    open_ms = lib.WARMUP_START_MS + np.arange(n, dtype=np.int64) * lib.BAR_MS
    opn = np.empty(n, dtype=np.float64)
    high = np.empty(n, dtype=np.float64)
    low = np.empty(n, dtype=np.float64)
    close = np.empty(n, dtype=np.float64)
    for index, (bar_open, bar_high, bar_low, bar_close) in enumerate(bars):
        start = index * lib.FIVE_MIN
        closes = [
            bar_open + (bar_close - bar_open) * (k + 1) / lib.FIVE_MIN
            for k in range(lib.FIVE_MIN)
        ]
        opens = [bar_open] + closes[:-1]
        for k in range(lib.FIVE_MIN):
            opn[start + k] = opens[k]
            close[start + k] = closes[k]
            high[start + k] = max(opens[k], closes[k])
            low[start + k] = min(opens[k], closes[k])
        # The 5m extremes are realized inside the bucket; they must bracket the
        # whole intrabar ramp for the aggregation to reproduce them exactly.
        assert bar_high >= max(bar_open, bar_close)
        assert bar_low <= min(bar_open, bar_close)
        high[start + 1] = bar_high
        low[start + 2] = bar_low
    return {
        "open_time_ms": open_ms,
        "available_at_ms": open_ms + lib.BAR_MS,
        "open": opn,
        "high": high,
        "low": low,
        "close": close,
    }


def _upper_bar(high: float) -> list[float]:
    """UPPER breach: high above the prior range, low still inside it."""
    return [BASE_OPEN, high, 99.9, 100.4]


def _lower_bar(low: float) -> list[float]:
    """LOWER breach: low below the prior range, high still inside it."""
    return [BASE_OPEN, 100.3, low, 99.7]


# A breach bar joins the prior-range window of every later bar, so successive
# synthetic breaches must escalate to keep qualifying.
UPPER_BAR = _upper_bar(101.0)
UPPER_BAR_HIGHER = _upper_bar(102.0)
UPPER_BAR_HIGHEST = _upper_bar(103.0)
LOWER_BAR = _lower_bar(99.0)
DOUBLE_BAR = [BASE_OPEN, 101.0, 99.0, 100.2]
OPEN_ABOVE_BAR = [101.0, 101.5, 100.9, 101.2]
FLAT_BAR = [100.4, 100.4, 100.4, 100.4]


def _events_at(
    overrides: dict[int, list[float]],
    *,
    L: int = 60,
    span: int = 40,
) -> list[dict[str, object]]:
    """Detect L-events for a quiet tape with specific 5m bars overridden."""
    bars = _blank_5m_bars(FIRST_DEV_BAR + span)
    for index, bar in overrides.items():
        bars[index] = bar
    frame_1m = _frame_from_5m(bars)
    _, events = lib.detect_breaches(frame_1m)
    return [event for event in events if int(event["L"]) == L]


def test_breach_geometry_accepts_upper_and_binds_side_t0_and_path_clock():
    index = FIRST_DEV_BAR + 4
    events = _events_at({index: UPPER_BAR})
    assert len(events) == 1
    event = events[0]
    assert event["side"] == "UPPER"
    assert int(event["direction"]) == lib.DIR_UPPER
    # T0 is the breach bar's availability: the bar [T0-5m, T0) is complete at T0.
    assert int(event["T0"]) == lib.WARMUP_START_MS + (index + 1) * lib.FIVE_MS
    assert int(event["T0"]) >= lib.DEV_START_MS
    assert int(event["T"]) == int(event["T0"]) + lib.PATH_MS
    assert float(event["breach_mag"]) > 0.0


def test_breach_geometry_accepts_lower_and_normalizes_direction():
    index = FIRST_DEV_BAR + 4
    events = _events_at({index: LOWER_BAR})
    assert len(events) == 1
    event = events[0]
    assert event["side"] == "LOWER"
    assert int(event["direction"]) == lib.DIR_LOWER
    assert float(event["breach_mag"]) > 0.0
    assert int(event["T"]) == int(event["T0"]) + lib.PATH_MS


def test_breach_geometry_excludes_double_break_and_open_outside_prior_range():
    index = FIRST_DEV_BAR + 4
    assert _events_at({index: DOUBLE_BAR}) == []
    assert _events_at({index: OPEN_ABOVE_BAR}) == []


def test_refractory_suppresses_a_second_breach_inside_thirty_minutes():
    first = FIRST_DEV_BAR + 4
    # PATH_MS is 30m == 6 five-minute bars, so +5 bars is 25m: inside. The
    # second bar escalates above the first so it qualifies on its own geometry
    # and is therefore suppressed by the refractory alone, not by failing to
    # clear the (now higher) prior range.
    events = _events_at({first: UPPER_BAR, first + 5: UPPER_BAR_HIGHER})
    assert [int(event["T0"]) for event in events] == [
        lib.WARMUP_START_MS + (first + 1) * lib.FIVE_MS
    ]
    # Control: the same escalating bar 30m later is accepted, proving the
    # suppression above came from the refractory and not from the geometry.
    spaced = _events_at({first: UPPER_BAR, first + 6: UPPER_BAR_HIGHER})
    assert len(spaced) == 2


def test_refractory_admits_a_breach_exactly_at_the_thirty_minute_boundary():
    first = FIRST_DEV_BAR + 4
    events = _events_at({first: UPPER_BAR, first + 6: UPPER_BAR_HIGHER})
    t0s = [int(event["T0"]) for event in events]
    assert t0s == [
        lib.WARMUP_START_MS + (first + 1) * lib.FIVE_MS,
        lib.WARMUP_START_MS + (first + 7) * lib.FIVE_MS,
    ]
    assert t0s[1] - t0s[0] == lib.PATH_MS


def test_non_qualifying_breach_never_consumes_a_refractory_slot():
    """Qualification precedes the refractory (prereg sections 4-5).

    A bar that is not a qualifying breach -- here a double break and an
    open-outside bar -- must not occupy a refractory slot, so a genuinely
    qualifying breach 25m later is still accepted. If the refractory were
    applied to the raw breach candidates instead of the qualifying population,
    the later real breach would be silently suppressed.
    """
    first = FIRST_DEV_BAR + 4
    for non_qualifying in (DOUBLE_BAR, OPEN_ABOVE_BAR):
        events = _events_at(
            {first: non_qualifying, first + 5: UPPER_BAR_HIGHER},
        )
        assert [int(event["T0"]) for event in events] == [
            lib.WARMUP_START_MS + (first + 6) * lib.FIVE_MS
        ]


def test_breach_magnitude_is_positive_whenever_geometry_qualifies():
    """BREACH_MAG > 0 is implied by the frozen geometry mask.

    UPPER requires high_B > R_high and LOWER requires low_B < R_low, both with
    prior_log_range > 0, so the direction-normalized magnitude is strictly
    positive for every qualifying bar. The implementation still evaluates it as
    part of qualification -- before the refractory -- so the ordering stays
    correct if the geometry mask is ever widened.
    """
    first = FIRST_DEV_BAR + 4
    events = _events_at({first: UPPER_BAR, first + 6: LOWER_BAR})
    assert len(events) == 2
    for event in events:
        assert float(event["breach_mag"]) > 0.0
        assert float(event["prior_log_range"]) > 0.0


def test_unavailable_for_decision_event_stays_in_the_qualifying_population():
    """Decision availability is not qualification.

    A completely flat 30m path makes the PATH_EFFICIENCY denominator zero, so
    the event is UNAVAILABLE_FOR_DECISION for candidate and baseline alike.
    It nonetheless remains a qualifying breach: the event is still constructed,
    still occupies the population, and is excluded only later, by its path
    state resolving to MISSING. Dropping such an event at qualification -- or
    hoisting path availability ahead of the refractory -- would silently change
    the frozen event population.
    """
    first = FIRST_DEV_BAR + 4
    overrides: dict[int, list[float]] = {first: UPPER_BAR}
    # Freeze the whole 30m path at the breach close so every path return is 0.
    for step in range(1, lib.PATH_BARS + 1):
        overrides[first + step] = FLAT_BAR
    events = _events_at(overrides)
    assert len(events) == 1
    assert not np.isfinite(float(events[0]["path_efficiency"]))
    stated = lib.attach_states(events)
    assert int(stated[0]["path_state"]) == lib.STATE_MISSING


def test_unavailable_for_decision_event_still_consumes_its_refractory_slot():
    """The refractory follows qualification, not scoring availability.

    The first accepted breach here has no 30-calendar-day causal reference set
    yet, so every one of its context states resolves to MISSING and it is
    UNAVAILABLE_FOR_DECISION. It is still a qualifying breach, so it keeps its
    refractory slot and suppresses the escalating breach 25m later.
    """
    first = FIRST_DEV_BAR + 4
    events = _events_at({first: UPPER_BAR, first + 5: UPPER_BAR_HIGHER})
    assert [int(event["T0"]) for event in events] == [
        lib.WARMUP_START_MS + (first + 1) * lib.FIVE_MS
    ]
    stated = lib.attach_states(events)
    assert int(stated[0]["breach_state"]) == lib.STATE_MISSING
    assert int(stated[0]["pre_vol_state"]) == lib.STATE_MISSING
    assert int(stated[0]["pre_drift_state"]) == lib.STATE_MISSING


def _mixed_path_state_events(count: int) -> list[dict[str, object]]:
    """One baseline stratum pooling two path states.

    The baseline queue therefore strictly contains the candidate queue, which
    is the configuration the placebo stratum invariant is about.
    """
    events: list[dict[str, object]] = []
    for i in range(count):
        t = lib.DEV_START_MS + i * lib.PATH_MS
        events.append(
            {
                "L": 60,
                "side": "UPPER" if i % 2 == 0 else "LOWER",
                "direction": 1,
                "T0": t - lib.PATH_MS,
                "T": t,
                "T_index": i * lib.PATH_BARS,
                "breach_state": 1,
                "pre_vol_state": 1,
                "pre_drift_state": 1,
                "path_state": 1 if i % 3 == 0 else 0,
            }
        )
    return events


def test_placebo_stratum_invariant_holds_on_a_pooled_baseline(monkeypatch):
    """The placebo stratum count never diverges from the candidate support.

    Every matured event is appended to its baseline and candidate queues in the
    same iteration, and both are purged with the same monotone cutoff, so the
    subset of the baseline queue carrying the event's path state is exactly the
    candidate queue. This exercises that path with a baseline stratum that
    genuinely pools two path states -- so the candidate queue is a strict
    subset -- and asserts the fail-closed invariant does not fire.
    """
    monkeypatch.setattr(lib, "N_PLACEBO", 5)
    monkeypatch.setattr(lib, "N_BOOT", 20)
    monkeypatch.setattr(
        lib,
        "_target_scale",
        lambda close, H: np.ones(len(close), dtype=np.float64),
    )
    frame5 = {"close": 100.0 + np.arange(2400, dtype=np.float64) * 0.01}
    events = _mixed_path_state_events(300)

    cell = lib.evaluate_cell(frame5, events, 60, 30)

    assert int(cell["N"]) > 0
    # Non-vacuity: the scored support really does span both path states, so the
    # baseline stratum pooled strictly more records than the candidate stratum.
    assert len(cell["support"]["path_state_counts"]) == 2


def test_placebo_cost_is_exactly_one_draw_per_replicate_per_scored_event(
    monkeypatch,
):
    """Pin the placebo work factor without touching its statistical semantics.

    The negative control draws exactly N_PLACEBO permutations per scored event,
    each seeded from (SEED_PLACEBO, rep, L, H, T, stratum). That product -- not
    a tunable -- is the cost driver, so it is asserted here as a deterministic
    count rather than as a wall-clock budget. Synthetic scaling measurements
    are recorded in the repair report; the replicate count, seed derivation and
    permutation strata are frozen and are not adjusted for performance.
    """
    monkeypatch.setattr(lib, "N_BOOT", 20)
    monkeypatch.setattr(
        lib,
        "_target_scale",
        lambda close, H: np.ones(len(close), dtype=np.float64),
    )
    calls: list[object] = []
    real_default_rng = np.random.default_rng

    def counting_default_rng(seed=None):
        calls.append(seed)
        return real_default_rng(seed)

    monkeypatch.setattr(np.random, "default_rng", counting_default_rng)
    frame5 = {"close": 100.0 + np.arange(2400, dtype=np.float64) * 0.01}
    events = _mixed_path_state_events(300)

    cell = lib.evaluate_cell(frame5, events, 60, 30)

    scored = int(cell["N"])
    assert scored > 0
    # N_PLACEBO placebo generators per scored event, plus the single
    # UTC-week bootstrap generator for the whole cell.
    assert len(calls) == scored * lib.N_PLACEBO + 1
    # Every placebo seed is distinct, so no replicate silently reuses another
    # replicate's permutation.
    assert len(set(calls)) == len(calls)


def test_placebo_stratum_invariant_is_fail_closed(monkeypatch):
    """A diverged stratum aborts the run instead of degrading it.

    The condition is an internal bookkeeping inconsistency, not one of the
    frozen contract's unavailability cases, so it must not be downgraded to a
    partial or diagnostic-only research result.
    """
    monkeypatch.setattr(lib, "N_PLACEBO", 5)
    monkeypatch.setattr(lib, "N_BOOT", 20)
    monkeypatch.setattr(
        lib,
        "_target_scale",
        lambda close, H: np.ones(len(close), dtype=np.float64),
    )

    real_purge = lib._purge
    state = {"calls": 0}

    def corrupting_purge(queue, cutoff):
        # Drop one matured record from the candidate queue only, which is
        # exactly the divergence the invariant exists to catch.
        real_purge(queue, cutoff)
        state["calls"] += 1
        if state["calls"] % 2 == 0 and len(queue) > lib.CANDIDATE_MIN_COUNT:
            queue.popleft()

    monkeypatch.setattr(lib, "_purge", corrupting_purge)
    frame5 = {"close": 100.0 + np.arange(2400, dtype=np.float64) * 0.01}
    events = _mixed_path_state_events(300)

    with pytest.raises(lib.B202Error, match="placebo stratum count diverged"):
        lib.evaluate_cell(frame5, events, 60, 30)


# ---------------------------------------------------------------------------
# Forbidden-window provenance is derived from the authorized view and the bytes
# actually loaded -- never asserted as a constant, and never by touching a
# 2025/2026 partition.
# ---------------------------------------------------------------------------


def _authorized_identity(
    *,
    end_exclusive_ms: int = lib.DEV_END_MS,
    allowed_years: tuple[int, ...] = (2020, 2021, 2022, 2023, 2024),
    partition_paths: tuple[str, ...] = (
        "canonical/1m/monthly/2020-01.parquet",
        "canonical/1m/monthly/2024-12.parquet",
    ),
) -> dict[str, object]:
    return {
        "window": {
            "start_inclusive_ms": lib.DEV_START_MS,
            "end_exclusive_ms": end_exclusive_ms,
            "allowed_years": list(allowed_years),
        },
        "partitions": [
            {"relative_path": path, "sha256": "0" * 64}
            for path in partition_paths
        ],
    }


def _loaded_frame(last_open_ms: int) -> dict[str, np.ndarray]:
    open_ms = np.asarray(
        [lib.WARMUP_START_MS, last_open_ms],
        dtype=np.int64,
    )
    return {
        "open_time_ms": open_ms,
        "available_at_ms": open_ms + lib.BAR_MS,
    }


def test_forbidden_window_evidence_is_derived_not_asserted():
    last_open = lib.DEV_END_MS - lib.BAR_MS
    evidence = lib.derive_forbidden_window_evidence(
        _authorized_identity(),
        _loaded_frame(last_open),
    )
    assert evidence["2025_validation"] is False
    assert evidence["2026_oos"] is False
    # The claim is checkable from the recorded numbers, not from a constant.
    assert evidence["derivation"] == "authorized-view-and-loaded-bytes"
    assert evidence["authorized_window_end_exclusive_ms"] == lib.DEV_END_MS
    assert evidence["authorized_allowed_years"] == [2020, 2021, 2022, 2023, 2024]
    assert evidence["authorized_max_partition_year"] == 2024
    assert evidence["authorized_partition_count"] == 2
    assert evidence["observed_max_open_time_ms"] == last_open
    assert evidence["observed_max_available_at_ms"] == last_open + lib.BAR_MS
    assert evidence["observed_max_available_at_ms"] <= lib.VALIDATION_2025_START_MS
    assert evidence["validation_2025_start_ms"] == lib.DEV_END_MS
    assert evidence["oos_2026_start_ms"] == lib.OOS_2026_START_MS


def test_forbidden_window_evidence_fails_closed_on_a_2025_authorized_year():
    with pytest.raises(lib.B202Error, match="forbidden window"):
        lib.derive_forbidden_window_evidence(
            _authorized_identity(allowed_years=(2020, 2025)),
            _loaded_frame(lib.DEV_END_MS - lib.BAR_MS),
        )


def test_forbidden_window_evidence_fails_closed_on_a_2025_partition():
    with pytest.raises(lib.B202Error, match="partitions reach a forbidden window"):
        lib.derive_forbidden_window_evidence(
            _authorized_identity(
                partition_paths=(
                    "canonical/1m/monthly/2020-01.parquet",
                    "canonical/1m/monthly/2025-01.parquet",
                ),
            ),
            _loaded_frame(lib.DEV_END_MS - lib.BAR_MS),
        )


def test_forbidden_window_evidence_fails_closed_on_a_widened_window():
    with pytest.raises(lib.B202Error, match="reserved 2025 validation pool"):
        lib.derive_forbidden_window_evidence(
            _authorized_identity(end_exclusive_ms=lib.DEV_END_MS + 1),
            _loaded_frame(lib.DEV_END_MS - lib.BAR_MS),
        )


def test_forbidden_window_evidence_fails_closed_on_loaded_2025_bytes():
    with pytest.raises(lib.B202Error, match="loaded development bytes"):
        lib.derive_forbidden_window_evidence(
            _authorized_identity(),
            _loaded_frame(lib.DEV_END_MS),
        )


def test_forbidden_window_evidence_requires_real_authorized_evidence():
    with pytest.raises(lib.B202Error, match="authorized window"):
        lib.derive_forbidden_window_evidence(
            {"partitions": []},
            _loaded_frame(lib.DEV_END_MS - lib.BAR_MS),
        )
    with pytest.raises(lib.B202Error, match="partition evidence"):
        lib.derive_forbidden_window_evidence(
            {"window": _authorized_identity()["window"]},
            _loaded_frame(lib.DEV_END_MS - lib.BAR_MS),
        )


def test_time_window_midrank_inputs_are_strictly_increasing_per_lookback():
    """The strict-clock contract is an invariant of the frozen B2-02 design.

    Accepted breaches for one L are separated by at least the 30m refractory,
    and T = T0 + 30m, so both the context clock (T0) and the path clock (T) are
    strictly increasing inside each L group. The canonical midrank primitive is
    therefore called with strictly increasing timestamps by construction, and
    its strict-ordering rejection is not a limitation to be relaxed.
    """
    first = FIRST_DEV_BAR + 4
    events = _events_at(
        {first: UPPER_BAR, first + 6: LOWER_BAR, first + 12: UPPER_BAR_HIGHER},
    )
    assert len(events) == 3
    t0s = [int(event["T0"]) for event in events]
    ts = [int(event["T"]) for event in events]
    assert all(b - a >= lib.PATH_MS for a, b in zip(t0s, t0s[1:]))
    assert all(b > a for a, b in zip(ts, ts[1:]))
