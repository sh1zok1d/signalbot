"""Clock, survival, and refusal tests. No market outcome is read here."""

from pathlib import Path

import numpy as np

from scripts.research.level_time_to_resolution_discovery_v1 import claim, clock, inference, survival
from scripts.research.level_time_to_resolution_discovery_v1 import constants as K
from scripts.research.level_time_to_resolution_discovery_v1.evaluate import refuse_if_recorded


def _grid(n=80):
    high = np.full(n, 100.0)
    low = np.full(n, 100.0)
    return high, low


def test_touch_bar_is_not_a_resolution():
    high, low = _grid()
    high[10] = 200.0
    low[10] = 50.0
    row = clock.resolution_clock(high, low, 10, 1, 99.0, 101.0, 0.01)
    assert row["status"] == "CENSORED"
    assert row["time_min"] is None
    assert row["censor_min"] == 240


def test_break_and_reject_times_and_ambiguity():
    high, low = _grid()
    # from below: break is high >= 101 * 1.01, reject is low <= 99 * 0.99
    high[12] = 102.2  # bar j+2, k=2, 10 minutes, BREAK only
    row = clock.resolution_clock(high, low, 10, 1, 99.0, 101.0, 0.01)
    assert row["kind"] == "BREAK"
    assert row["k"] == 2
    assert row["time_min"] == 10
    high[:], low[:] = 100.0, 100.0
    low[14] = 97.0  # j+4, REJECT
    row = clock.resolution_clock(high, low, 10, 1, 99.0, 101.0, 0.01)
    assert row["kind"] == "REJECT"
    assert row["time_min"] == 20
    high[:], low[:] = 100.0, 100.0
    high[11] = 130.0
    low[11] = 70.0
    row = clock.resolution_clock(high, low, 10, 1, 99.0, 101.0, 0.01)
    assert row["kind"] == "AMBIGUOUS"
    assert row["status"] == "RESOLVED"
    assert row["time_min"] == 5


def test_from_above_orientation_and_censor():
    high, low = _grid()
    low[11] = 90.0  # break downward
    row = clock.resolution_clock(high, low, 10, -1, 99.0, 101.0, 0.01)
    assert row["kind"] == "BREAK"
    assert row["time_min"] == 5
    high[:], low[:] = 100.0, 100.0
    row = clock.resolution_clock(high, low, 10, -1, 99.0, 101.0, 0.01)
    assert row["status"] == "CENSORED"
    assert row["time_min"] is None


def test_missing_bar_is_not_filled():
    high, low = _grid()
    high[11] = np.nan
    low[11] = np.nan
    high[12] = 130.0
    row = clock.resolution_clock(high, low, 10, 1, 99.0, 101.0, 0.01)
    assert row["kind"] == "BREAK"
    assert row["time_min"] == 10


def test_km_rmut_and_checkpoints():
    times = np.array([5.0, 5.0])
    events = np.array([1, 1])
    jumps = survival.km_jumps(times, events)
    assert survival.rmut(jumps) == 5.0
    assert survival.survival_at(jumps, 15) == 0.0
    times = np.array([240.0, 240.0])
    events = np.array([0, 0])
    jumps = survival.km_jumps(times, events)
    assert jumps == []
    assert survival.rmut(jumps) == 240.0
    assert survival.survival_at(jumps, 240) == 1.0
    times = np.array([10.0, 240.0])
    events = np.array([1, 0])
    jumps = survival.km_jumps(times, events)
    assert survival.rmut(jumps) == 125.0
    points = survival.checkpoints(jumps)
    assert points["15"]["unresolved"] == 0.5
    assert points["15"]["resolved_by"] == 0.5
    hazards = survival.interval_hazards(times, events)
    first = hazards[0]
    assert first["left"] == 0 and first["right"] == 15
    assert first["resolved"] == 1 and first["at_risk"] == 2
    assert first["rate"] == 0.5


def test_last_bar_event_is_not_a_censor():
    times = np.array([240.0, 240.0])
    events = np.array([1, 0])
    jumps = survival.km_jumps(times, events)
    assert survival.survival_at(jumps, 240) == 0.5
    assert survival.rmut(jumps) == 240.0


def test_paired_bootstrap_moves_rows_together():
    weeks = np.array([1, 1, 2])
    real_t = np.array([10.0, 20.0, 30.0])
    real_e = np.array([1, 1, 1])
    pseudo_t = np.array([40.0, 50.0, 60.0])
    pseudo_e = np.array([1, 1, 1])
    out = inference.bootstrap_delta(
        weeks, real_t, real_e, pseudo_t, pseudo_e, draws=20, seed=K.BOOT_SEED,
    )
    assert out["delta"] < 0
    assert out["n"] == 3
    assert out["bootstrap_valid"] == 20
    assert out["delta_ci95"][1] < 0


def test_year_family_side_and_loyo_rules():
    full = -20.0
    epochs = [{"n": 40, "delta": -10.0}, {"n": 40, "delta": -8.0},
              {"n": 40, "delta": -6.0}, {"n": 40, "delta": -4.0},
              {"n": 40, "delta": 3.0}]
    assert claim.year_stability(full, epochs)["pass"]
    epochs[-1]["delta"] = 20.0
    epochs[-2]["delta"] = 20.0
    assert not claim.year_stability(full, epochs)["pass"]
    loyo = [{"n": 100, "delta": -5.0} for _ in range(5)]
    assert claim.loyo_stability(full, loyo)["pass"]
    loyo[0]["delta"] = 5.0
    assert not claim.loyo_stability(full, loyo)["pass"]
    families = [
        {"name": "DAY", "n": 80, "delta": -20.0},
        {"name": "WEEK", "n": 40, "delta": 20.0},
        {"name": "MONTH", "n": 5, "delta": 1.0},
    ]
    assert not claim.family_stability(families)["pass"]
    families[1]["delta"] = -2.0
    assert claim.family_stability(families)["pass"]
    sides = [
        {"name": "resistance", "n": 50, "delta": -20.0},
        {"name": "support", "n": 50, "delta": 16.0},
    ]
    assert not claim.side_stability(sides)["pass"]
    sides[1]["delta"] = 4.0
    assert claim.side_stability(sides)["pass"]


def test_candidate_and_routes():
    assert claim.candidate_pass(
        -20.0, (-30.0, -10.0), years_ok=True, loyo_ok=True, family_ok=True,
        side_ok=True, artifact=False, n=500,
    )
    assert not claim.candidate_pass(
        -10.0, (-12.0, -8.0), years_ok=True, loyo_ok=True, family_ok=True,
        side_ok=True, artifact=False, n=500,
    )
    assert claim.route(
        novelty_ok=False, gate_pass=True, candidate=False, material_effect=False,
        ci_excludes_0=False, stable=True, info_limited=False,
    ) == "BLOCKED_REOPENING_TIME_TO_RESOLUTION_CELL"
    assert claim.route(
        novelty_ok=True, gate_pass=True, candidate=False, material_effect=True,
        ci_excludes_0=True, stable=False, info_limited=False,
    ) == "STRUCTURE_PRESENT_BUT_UNSTABLE"
    assert claim.route(
        novelty_ok=True, gate_pass=True, candidate=False, material_effect=False,
        ci_excludes_0=False, stable=True, info_limited=False,
    ) == "GENERIC_OR_NO_RESOLUTION_CLOCK_DIFFERENCE"


def test_preflight_does_not_import_the_clock():
    text = Path("scripts/research/level_time_to_resolution_discovery_v1/preflight.py").read_text()
    assert "resolution_clock" not in text
    assert "km_jumps" not in text
    assert "time_min" not in text


def test_refusing_rerun(tmp_path):
    target = tmp_path / "RESULT.json"
    target.write_text("{}")
    try:
        refuse_if_recorded(target, tmp_path / "missing.md")
    except SystemExit as exc:
        assert "REFUSING_RERUN" in str(exc)
    else:
        raise AssertionError("second run was allowed")
