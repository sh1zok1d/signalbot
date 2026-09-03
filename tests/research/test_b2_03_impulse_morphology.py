"""Synthetic adversarial tests for B2-03 impulse morphology.

These tests must not open real CORE parquet, create a production evidence
reservation, or invoke run_development against real market data.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from scripts.research import b2_03_impulse_morphology as runner
from scripts.research import b2_03_impulse_morphology_lib as lib
from scripts.research.lib.batch02_source_policy import validate_batch02_source_tree


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = REPO_ROOT / "scripts" / "research"
PREREG = REPO_ROOT / "docs" / "research" / "B2_03_IMPULSE_MORPHOLOGY_PREREG.json"


def _frame(n: int, close: np.ndarray | None = None) -> dict[str, np.ndarray]:
    open_ms = lib.WARMUP_START_MS + np.arange(n, dtype=np.int64) * lib.BAR_MS
    avail = open_ms + lib.BAR_MS
    if close is None:
        close = 100.0 + 0.01 * np.arange(n, dtype=np.float64)
    return {
        "open_time_ms": open_ms,
        "available_at_ms": avail,
        "close": np.asarray(close, dtype=np.float64),
    }


def _freeze() -> dict:
    return json.loads(PREREG.read_text(encoding="utf-8"))


def test_prereg_constants_match_implementation_freeze():
    freeze = _freeze()
    assert freeze["formulation_id"] == lib.HYPOTHESIS_ID
    assert freeze["dataset"]["dataset_id"] == lib.DATASET_ID
    assert freeze["dataset"]["snapshot_id"] == lib.REQUIRED_SNAPSHOT
    assert tuple(freeze["impulse_windows_minutes"]) == lib.W_VALUES
    assert tuple(freeze["horizons_minutes"]) == lib.H_VALUES
    assert freeze["search_surface_primary_cells"] == lib.PRIMARY_CELLS
    assert freeze["forecast"]["baseline_min_count"] == lib.BASELINE_MIN_COUNT
    assert freeze["forecast"]["candidate_min_count"] == lib.CANDIDATE_MIN_COUNT
    assert freeze["controls"]["permutation_seed"] == lib.SEED_PLACEBO
    assert freeze["controls"]["permutation_replicates"] == lib.N_PLACEBO
    assert freeze["controls"]["bootstrap_seed"] == lib.SEED_BOOT
    assert freeze["controls"]["bootstrap_replicates"] == lib.N_BOOT
    assert freeze["per_cell_thresholds"]["relative_mae_improvement_min"] == lib.RELATIVE_MAE_MIN
    assert tuple(freeze["promotion_gate_contract"]["required_gate_names"]) == lib.GATE_NAMES
    assert len(lib.GATE_NAMES) == 8
    assert lib.PREREG_MERGE_SHA == "61bc9cfde80c6a142ac147ebee6487a1ae710324"


def test_1m_chronology_rejects_malformed_frames():
    good = _frame(10)
    lib.validate_1m_frame(good)
    missing = dict(good)
    missing["open_time_ms"] = good["open_time_ms"][:-1]
    with pytest.raises(lib.B203Error, match="equal"):
        lib.validate_1m_frame(missing)
    dup = _frame(10)
    dup["open_time_ms"] = dup["open_time_ms"].copy()
    dup["open_time_ms"][3] = dup["open_time_ms"][2]
    with pytest.raises(lib.B203Error):
        lib.validate_1m_frame(dup)
    shuffled = _frame(10)
    order = np.arange(10)
    order[1], order[2] = order[2], order[1]
    shuffled["open_time_ms"] = shuffled["open_time_ms"][order]
    shuffled["available_at_ms"] = shuffled["available_at_ms"][order]
    shuffled["close"] = shuffled["close"][order]
    with pytest.raises(lib.B203Error, match="contiguous"):
        lib.validate_1m_frame(shuffled)
    avail = _frame(10)
    avail["available_at_ms"] = avail["available_at_ms"].copy()
    avail["available_at_ms"][0] += 1
    with pytest.raises(lib.B203Error, match="60000"):
        lib.validate_1m_frame(avail)
    bad_close = _frame(10)
    bad_close["close"] = bad_close["close"].copy()
    bad_close["close"][1] = np.nan
    with pytest.raises(lib.B203Error, match="finite"):
        lib.validate_1m_frame(bad_close)
    nonpos = _frame(10)
    nonpos["close"] = nonpos["close"].copy()
    nonpos["close"][2] = 0.0
    with pytest.raises(lib.B203Error, match="positive"):
        lib.validate_1m_frame(nonpos)
    future = _frame(10)
    future["open_time_ms"] = future["open_time_ms"].copy() + (
        lib.DEV_END_MS - lib.WARMUP_START_MS
    )
    future["available_at_ms"] = future["open_time_ms"] + lib.BAR_MS
    with pytest.raises(lib.B203Error, match="2025"):
        lib.validate_1m_frame(future)


def test_pre_vol_is_exactly_sixty_returns():
    n = 3 * 60
    close = np.full(n, 100.0, dtype=np.float64)
    # 60 multiplicative 1.01 steps ending at 02:00Z.
    t = lib.WARMUP_START_MS + 2 * lib.HOUR_MS
    for k in range(61):
        end = t - (60 - k) * lib.BAR_MS
        idx = (end - lib.BAR_MS - lib.WARMUP_START_MS) // lib.BAR_MS
        close[idx] = 100.0 * (1.01 ** k)
    frame = _frame(n, close)
    value = lib.pre_vol_60(
        frame["open_time_ms"],
        frame["available_at_ms"],
        frame["close"],
        t,
    )
    expected = math.sqrt(60 * math.log(1.01) ** 2)
    assert value is not None
    assert abs(value - expected) < 1e-12
    # 59-return window (T-59m) is a different T and must not be accepted as PRE_VOL_60(T).
    short = lib.pre_vol_60(
        frame["open_time_ms"][: 60 + 58],
        frame["available_at_ms"][: 60 + 58],
        frame["close"][: 60 + 58],
        t,
    )
    assert short is None
    extra = _frame(n + 5, np.concatenate([close, np.full(5, 999.0)]))
    value_extra = lib.pre_vol_60(
        extra["open_time_ms"],
        extra["available_at_ms"],
        extra["close"],
        t,
    )
    assert value_extra == pytest.approx(expected)


def test_5m_aggregation_uses_complete_bucket_end():
    n = 15
    close = np.arange(1, n + 1, dtype=np.float64) + 100.0
    frame = _frame(n, close)
    first_end = lib.WARMUP_START_MS + 5 * lib.BAR_MS
    value = lib._complete_5m_close(
        frame["open_time_ms"],
        frame["available_at_ms"],
        frame["close"],
        first_end,
    )
    assert value == float(close[4])
    partial = lib._complete_5m_close(
        frame["open_time_ms"],
        frame["available_at_ms"],
        frame["close"],
        lib.WARMUP_START_MS + 3 * lib.BAR_MS,
    )
    assert partial is None
    incomplete = lib._complete_5m_close(
        frame["open_time_ms"][:4],
        frame["available_at_ms"][:4],
        frame["close"][:4],
        first_end,
    )
    assert incomplete is None


def test_event_population_is_hourly_and_not_gated_by_morphology_state():
    frame = _frame(8 * 60)
    events = lib.construct_events(frame)
    assert events
    assert all(int(event["T"]) % lib.HOUR_MS == 0 for event in events)
    assert all(float(event["D_W"]) != 0.0 for event in events)
    attached = lib.attach_states(events, frame)
    missing = [event for event in attached if int(event["morphology_state"]) < 0]
    assert missing
    missing_ids = {(int(event["T"]), int(event["W"])) for event in missing}
    constructed_ids = {(int(event["T"]), int(event["W"])) for event in events}
    assert missing_ids.issubset(constructed_ids)
    assert constructed_ids == {(int(event["T"]), int(event["W"])) for event in attached}


def test_canonical_event_id_known_vector_and_rejects_aliases():
    t = 1_577_844_000_000
    known = lib.canonical_event_id(W=15, direction="UP", T_ms=t, H=30)
    expected = (
        f"{lib.REQUIRED_SNAPSHOT}|1m|5m|1h|15|UP|{t - 15 * lib.BAR_MS}|{t}|{t}|30"
    )
    assert known == expected
    assert " " not in known
    reordered = f"{lib.REQUIRED_SNAPSHOT}|1m|5m|1h|15|UP|{t}|{t}|{t - 15 * lib.BAR_MS}|30"
    assert known != reordered
    with pytest.raises(lib.B203Error):
        lib.canonical_event_id(W=15, direction="up", T_ms=t, H=30)
    iso = "2020-01-01T02:00:00Z"
    assert iso not in known
    assert known.split("|")[6].isdigit()


def test_tertile_boundaries_are_half_open():
    assert lib._tertile(0.0) == lib.STATE_LOW
    assert lib._tertile(1.0 / 3.0 - 1e-12) == lib.STATE_LOW
    assert lib._tertile(1.0 / 3.0) == lib.STATE_MID
    assert lib._tertile(2.0 / 3.0 - 1e-12) == lib.STATE_MID
    assert lib._tertile(2.0 / 3.0) == lib.STATE_HIGH
    assert lib._tertile(1.0) == lib.STATE_HIGH
    assert lib._tertile(float("nan")) == lib.STATE_MISSING


def test_morphology_components_hand_derived_paths():
    d_w = math.log(1.03)
    shock = np.array([0.0, 0.0, d_w], dtype=np.float64)
    shock_c = lib.morphology_components(shock, 1, float(np.sum(shock)))
    assert shock_c is not None
    assert abs(shock_c["distributedness"] - (1.0 - 1.0)) < 1e-12
    assert abs(shock_c["path_efficiency"] - 1.0) < 1e-12
    assert shock_c["directional_bar_share"] == 1.0 / 3.0

    smooth = np.array([d_w / 3.0, d_w / 3.0, d_w / 3.0], dtype=np.float64)
    smooth_c = lib.morphology_components(smooth, 1, float(np.sum(smooth)))
    assert smooth_c is not None
    assert abs(smooth_c["distributedness"] - (1.0 - (1.0 / 3.0))) < 1e-12
    assert abs(smooth_c["path_efficiency"] - 1.0) < 1e-12
    assert smooth_c["directional_bar_share"] == 1.0

    choppy = np.array([0.10, -0.09, 0.02], dtype=np.float64)
    d_w_choppy = float(np.sum(choppy))
    choppy_c = lib.morphology_components(choppy, 1, d_w_choppy)
    assert choppy_c is not None
    assert choppy_c["path_efficiency"] < shock_c["path_efficiency"]
    assert choppy_c["countermove_shallowness"] < 1.0

    counter = np.array([0.05, -0.04, 0.08], dtype=np.float64)
    counter_c = lib.morphology_components(counter, 1, float(np.sum(counter)))
    assert counter_c is not None
    tv = 0.17
    assert counter_c["tv"] == pytest.approx(tv)
    assert counter_c["path_efficiency"] == pytest.approx(0.09 / tv)
    assert counter_c["distributedness"] == pytest.approx(1.0 - 0.08 / tv)
    assert counter_c["directional_bar_share"] == pytest.approx(2.0 / 3.0)
    assert counter_c["max_countermove"] == pytest.approx(0.04)
    assert counter_c["countermove_shallowness"] == pytest.approx(1.0 - 0.04 / tv)

    assert lib.morphology_components(np.zeros(3), 1, 0.0) is None
    with pytest.raises(lib.B203Error, match="PATH_EFFICIENCY"):
        lib.morphology_components(np.array([0.1, -0.2], dtype=np.float64), 1, 10.0)


def test_current_event_excluded_from_same_w_percentile():
    times = np.asarray(
        [
            lib.WARMUP_START_MS + lib.HOUR_MS,
            lib.WARMUP_START_MS + 2 * lib.HOUR_MS,
        ],
        dtype=np.int64,
    )
    values = np.asarray([1.0, 2.0], dtype=np.float64)
    states, scores = lib._causal_tertile_states(values, times)
    assert math.isnan(float(scores[0]))
    assert math.isfinite(float(scores[1]))
    assert int(states[0]) == lib.STATE_MISSING
    from scripts.research.lib.batch02_contracts import rolling_midrank_percentile

    scores2 = rolling_midrank_percentile(
        values, timestamps_ms=times, lookback_ms=lib.REF_MS
    )
    # Current excluded: the only reference is 1.0, so 2.0 ranks at 1.0.
    # Including the current point would have produced 0.75.
    assert scores2[1] == pytest.approx(1.0)
    assert scores[1] == pytest.approx(scores2[1])
    assert scores2[1] != pytest.approx(0.75)


def test_target_scale_ignores_unresolved_and_future_references():
    n = 8 * 60
    close = 100.0 + 0.01 * np.arange(n, dtype=np.float64)
    frame = _frame(n, close)
    t = lib.WARMUP_START_MS + 6 * lib.HOUR_MS
    h = 60
    scale = lib._past_median_abs_ret(
        frame["open_time_ms"],
        frame["available_at_ms"],
        frame["close"],
        t,
        h,
    )
    assert scale is not None and scale > 0.0
    spiked = close.copy()
    # Close after T that would affect an illegal ref_t = T-15m with H=60.
    future_end = t + 45 * lib.BAR_MS
    future_idx = (future_end - lib.BAR_MS - lib.WARMUP_START_MS) // lib.BAR_MS
    spiked[future_idx] = 10_000.0
    spiked_frame = _frame(n, spiked)
    scale_spiked = lib._past_median_abs_ret(
        spiked_frame["open_time_ms"],
        spiked_frame["available_at_ms"],
        spiked_frame["close"],
        t,
        h,
    )
    assert scale_spiked == pytest.approx(scale)


def _oracle_past_median_abs_ret(frame: dict[str, np.ndarray], T_ms: int, H: int) -> float | None:
    t = int(T_ms)
    h_ms = int(H) * lib.BAR_MS
    window_start = t - lib.REF_MS
    last_ref = t - h_ms
    if last_ref < window_start:
        return None
    first_grid = ((window_start + lib.SCALE_GRID_MS - 1) // lib.SCALE_GRID_MS) * lib.SCALE_GRID_MS
    values: list[float] = []
    ref = first_grid
    while ref <= last_ref:
        left = lib._close_ending_at(
            frame["open_time_ms"], frame["available_at_ms"], frame["close"], ref
        )
        right = lib._close_ending_at(
            frame["open_time_ms"],
            frame["available_at_ms"],
            frame["close"],
            ref + h_ms,
        )
        if left is not None and right is not None and left > 0.0 and right > 0.0:
            ret = abs(math.log(right / left))
            if math.isfinite(ret):
                values.append(ret)
        ref += lib.SCALE_GRID_MS
    if not values:
        return None
    median = float(np.median(np.asarray(values, dtype=np.float64)))
    if not math.isfinite(median) or median <= 0.0:
        return None
    return median


def test_target_scale_vectorized_matches_close_ending_loop_and_is_cached():
    frame = _frame(12 * 60)
    t = lib.WARMUP_START_MS + 8 * lib.HOUR_MS
    cache: dict[tuple[int, int], float | None] = {}
    for H in lib.H_VALUES:
        vectorized = lib._past_median_abs_ret(
            frame["open_time_ms"],
            frame["available_at_ms"],
            frame["close"],
            t,
            H,
            cache=cache,
        )
        oracle = _oracle_past_median_abs_ret(frame, t, H)
        if oracle is None:
            assert vectorized is None
        else:
            assert vectorized == pytest.approx(oracle)
        assert (t, H) in cache
        again = lib._past_median_abs_ret(
            frame["open_time_ms"],
            frame["available_at_ms"],
            frame["close"],
            t,
            H,
            cache=cache,
        )
        assert again is vectorized or again == pytest.approx(vectorized)
    early = lib.WARMUP_START_MS + lib.HOUR_MS
    got = lib._past_median_abs_ret(
        frame["open_time_ms"],
        frame["available_at_ms"],
        frame["close"],
        early,
        240,
    )
    want = _oracle_past_median_abs_ret(frame, early, 240)
    if want is None:
        assert got is None
    else:
        assert got == pytest.approx(want)


def test_target_scale_fails_closed_on_invalid_present_close():
    n = 12 * 60
    close = 100.0 + 0.01 * np.arange(n, dtype=np.float64)
    t = lib.WARMUP_START_MS + 8 * lib.HOUR_MS
    ref = t - 60 * lib.BAR_MS
    idx = (ref - lib.BAR_MS - lib.WARMUP_START_MS) // lib.BAR_MS
    poisoned = close.copy()
    poisoned[idx] = 0.0
    frame = _frame(n, poisoned)
    with pytest.raises(lib.B203Error, match="valid price"):
        lib._past_median_abs_ret(
            frame["open_time_ms"],
            frame["available_at_ms"],
            frame["close"],
            t,
            60,
        )
    poisoned_nan = close.copy()
    poisoned_nan[idx] = np.nan
    frame_nan = _frame(n, poisoned_nan)
    with pytest.raises(lib.B203Error, match="valid price"):
        lib._past_median_abs_ret(
            frame_nan["open_time_ms"],
            frame_nan["available_at_ms"],
            frame_nan["close"],
            t,
            60,
        )


def test_2025_boundary_last_legal_t_and_one_step_beyond():
    assert lib.last_legal_t_ms(15) == 1_735_686_000_000
    assert lib.last_legal_t_ms(30) == 1_735_686_000_000
    assert lib.last_legal_t_ms(60) == 1_735_682_400_000
    assert lib.last_legal_t_ms(120) == 1_735_678_800_000
    assert lib.last_legal_t_ms(240) == 1_735_671_600_000
    assert lib.scoring_eligible(lib.last_legal_t_ms(15), 15) is True
    assert lib.scoring_eligible(lib.last_legal_t_ms(15) + lib.HOUR_MS, 15) is False
    assert lib.scoring_eligible(lib.last_legal_t_ms(60), 60) is True
    assert lib.scoring_eligible(lib.last_legal_t_ms(60) + lib.HOUR_MS, 60) is False
    assert lib.last_legal_t_ms(15) + 15 * lib.BAR_MS < lib.DEV_END_MS
    assert lib.last_legal_t_ms(60) + lib.HOUR_MS + 60 * lib.BAR_MS == lib.DEV_END_MS


def test_walk_forward_horizon_equality_is_the_frozen_training_rule():
    current_t = lib.DEV_START_MS + 10 * lib.HOUR_MS
    h_ms = 60 * lib.BAR_MS
    assert current_t - h_ms + h_ms == current_t
    allowed = current_t - h_ms
    forbidden = current_t - h_ms + lib.BAR_MS
    assert allowed + h_ms <= current_t
    assert forbidden + h_ms > current_t


def test_same_support_joint_unavailability_via_empty_cell():
    frame = _frame(12 * 60)
    result = lib.evaluate_b2_03(frame)
    assert len(result["cells"]) == 15
    for cell in result["cells"]:
        assert cell["N"] == 0
        ids = cell["event_ids"]
        assert ids == []
        assert cell["per_cell_gates"]["primary_positive"] is False


def test_placebo_seed_vector_and_row_order_invariance():
    t = 1_580_600_000_000
    stratum = lib.baseline_stratum_id(
        W=15,
        direction="UP",
        displacement_mag_state="LOW",
        vol_state="MID",
    )
    assert stratum == "15|UP|LOW|MID"
    seed = lib.seed_int((lib.SEED_PLACEBO, 0, 15, 30, t, stratum))
    raw = "|".join(str(p) for p in (20260904, 0, 15, 30, t, stratum)).encode("utf-8")
    assert seed == int(hashlib.sha256(raw).hexdigest()[:16], 16)
    labels = np.asarray(["LOW", "HIGH", "MID", "HIGH"])
    y = np.asarray([1.0, 2.0, 3.0, 4.0])
    items_a = list(zip((10, 20, 30, 40), y, labels, ["id-d", "id-a", "id-c", "id-b"]))
    items_b = list(reversed(items_a))
    def permute(items):
        ordered = sorted(items, key=lambda item: str(item[3]))
        rng = np.random.default_rng(seed)
        return tuple(rng.permutation(np.asarray([item[2] for item in ordered])))
    assert permute(items_a) == permute(items_b)


def test_bootstrap_is_deterministic_for_fixed_weeks():
    improvements = np.asarray([0.1, -0.2, 0.3, 0.05], dtype=np.float64)
    t0 = lib.DEV_START_MS
    times = np.asarray(
        [t0, t0 + 3 * lib.DAY_MS, t0 + 10 * lib.DAY_MS, t0 + 11 * lib.DAY_MS],
        dtype=np.int64,
    )
    a = lib._week_bootstrap_interval(improvements, times, 15, 30)
    b = lib._week_bootstrap_interval(improvements, times, 15, 30)
    assert a == b
    assert a[0] <= a[1]


def test_gate_zero_is_not_positive():
    cells = []
    for W in lib.W_VALUES:
        for H in lib.H_VALUES:
            cells.append(
                {
                    "W": W,
                    "H": H,
                    "year_stability_pass": True,
                    "per_cell_gates": {
                        "primary_positive": False,
                        "material_relative_mae": False,
                        "bootstrap_positive": False,
                        "placebo_separation": False,
                        "morphology_ordering": False,
                    },
                }
            )
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["horizon_robustness"] is False
    assert neighborhoods == []
    assert lib.per_cell_gates(
        mean_improvement=0.0,
        up_mean=0.0,
        down_mean=0.0,
        relative=0.05,
        bootstrap_lower=0.1,
        placebo_q95=-1.0,
        sep_pooled=0.1,
        sep_up=0.1,
        sep_down=0.1,
    )["primary_positive"] is False


def _pass_cell(W: int, H: int, year: bool = True) -> dict[str, object]:
    return {
        "W": W,
        "H": H,
        "year_stability_pass": year,
        "per_cell_gates": {name: True for name in lib.PER_CELL_GATE_NAMES},
    }


def _fail_cell(W: int, H: int) -> dict[str, object]:
    return {
        "W": W,
        "H": H,
        "year_stability_pass": False,
        "per_cell_gates": {name: False for name in lib.PER_CELL_GATE_NAMES},
    }


def test_isolated_cell_and_single_w_cannot_promote():
    cells = [_fail_cell(W, H) for W in lib.W_VALUES for H in lib.H_VALUES]
    cells[0] = _pass_cell(15, 15)
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["horizon_robustness"] is False
    assert gates["parameter_robustness"] is False
    assert neighborhoods == []

    cells = [_fail_cell(W, H) for W in lib.W_VALUES for H in lib.H_VALUES]
    by = {(c["W"], c["H"]): i for i, c in enumerate(cells)}
    cells[by[(15, 15)]] = _pass_cell(15, 15)
    cells[by[(15, 30)]] = _pass_cell(15, 30)
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["horizon_robustness"] is True
    assert gates["parameter_robustness"] is False
    assert neighborhoods == []


def test_two_w_same_adjacent_h_can_satisfy_parameter_robustness():
    cells = [_fail_cell(W, H) for W in lib.W_VALUES for H in lib.H_VALUES]
    by = {(c["W"], c["H"]): i for i, c in enumerate(cells)}
    for W in (15, 30):
        cells[by[(W, 15)]] = _pass_cell(W, 15)
        cells[by[(W, 30)]] = _pass_cell(W, 30)
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["horizon_robustness"] is True
    assert gates["parameter_robustness"] is True
    assert gates["year_stability"] is True
    assert neighborhoods
    assert neighborhoods[0]["H_pair"] == [15, 30]
    assert neighborhoods[0]["W"] == [15, 30]


def test_year_stability_requires_four_of_five():
    cells = [_fail_cell(W, H) for W in lib.W_VALUES for H in lib.H_VALUES]
    by = {(c["W"], c["H"]): i for i, c in enumerate(cells)}
    for W in (15, 30):
        cells[by[(W, 15)]] = _pass_cell(W, 15, year=False)
        cells[by[(W, 30)]] = _pass_cell(W, 30, year=False)
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["parameter_robustness"] is True
    assert gates["year_stability"] is False
    assert neighborhoods == []


def test_one_sided_metrics_cannot_pass_anti_rescue_gates():
    up_only = lib.per_cell_gates(
        mean_improvement=1.0,
        up_mean=2.0,
        down_mean=float("nan"),
        relative=0.05,
        bootstrap_lower=0.1,
        placebo_q95=0.0,
        sep_pooled=1.0,
        sep_up=2.0,
        sep_down=float("nan"),
    )
    assert up_only["primary_positive"] is False
    assert up_only["morphology_ordering"] is False
    down_only = lib.per_cell_gates(
        mean_improvement=1.0,
        up_mean=float("nan"),
        down_mean=2.0,
        relative=0.05,
        bootstrap_lower=0.1,
        placebo_q95=0.0,
        sep_pooled=1.0,
        sep_up=float("nan"),
        sep_down=2.0,
    )
    assert down_only["primary_positive"] is False
    pooled_pos_down_neg = lib.per_cell_gates(
        mean_improvement=0.5,
        up_mean=1.2,
        down_mean=-0.2,
        relative=0.05,
        bootstrap_lower=0.1,
        placebo_q95=0.0,
        sep_pooled=0.4,
        sep_up=0.8,
        sep_down=-0.1,
    )
    assert pooled_pos_down_neg["primary_positive"] is False
    pooled_pos_up_neg = lib.per_cell_gates(
        mean_improvement=0.5,
        up_mean=-0.2,
        down_mean=1.2,
        relative=0.05,
        bootstrap_lower=0.1,
        placebo_q95=0.0,
        sep_pooled=0.4,
        sep_up=-0.1,
        sep_down=0.8,
    )
    assert pooled_pos_up_neg["primary_positive"] is False
    missing_high_low = lib._morphology_separation(
        [{"direction": "UP", "morphology_state": lib.STATE_MID, "base_residual": 1.0}]
    )
    assert math.isnan(missing_high_low)


def test_negative_morphology_sign_is_not_exhaustion_promotion():
    gates = lib.per_cell_gates(
        mean_improvement=0.5,
        up_mean=0.2,
        down_mean=0.2,
        relative=0.05,
        bootstrap_lower=0.1,
        placebo_q95=0.0,
        sep_pooled=-0.4,
        sep_up=-0.4,
        sep_down=-0.4,
    )
    assert gates["morphology_ordering"] is False
    cell = _pass_cell(15, 15)
    cell["per_cell_gates"]["morphology_ordering"] = gates["morphology_ordering"]
    assert cell["per_cell_gates"]["morphology_ordering"] is False


def test_result_reports_all_fifteen_cells():
    result = lib.evaluate_b2_03(_frame(6 * 60))
    assert result["search_surface"]["primary_cells"] == 15
    assert len(result["cells"]) == 15
    pairs = {(int(cell["W"]), int(cell["H"])) for cell in result["cells"]}
    expected = {(W, H) for W in lib.W_VALUES for H in lib.H_VALUES}
    assert pairs == expected
    assert result["promotion"]["verdict"] in {
        "B2_03_PROMOTED_CANDIDATE",
        "B2_03_CLOSED_NO_PROMOTION",
    }
    cell = result["cells"][0]
    for key in (
        "N",
        "unique_utc_days",
        "unique_utc_weeks",
        "unique_utc_months",
        "UP_count",
        "DOWN_count",
        "yearly_2020_2024_mean_ae_improvement",
        "baseline_state_counts",
        "morphology_state_counts",
        "largest_month_support_share",
        "top5_month_support_share",
        "mean_ae_improvement",
        "median_ae_improvement",
        "relative_mae_improvement",
        "bootstrap_lower_95",
        "bootstrap_upper_95",
        "morphology_separation_pooled",
        "placebo_q95",
        "up",
        "down",
        "anti_rescue",
        "per_cell_gates",
        "event_ids",
    ):
        assert key in cell
    assert set(cell["per_cell_gates"]) == set(lib.PER_CELL_GATE_NAMES)
    assert "scored" not in cell


def test_runner_call_order_uses_retained_ceremony(monkeypatch):
    calls: list[str] = []

    class Freeze:
        code_sha = "a" * 40
        tree_oid = "b" * 40
        repo_root = REPO_ROOT

    class Reservation:
        hypothesis_id = lib.HYPOTHESIS_ID
        stage = "development"
        dataset_id = lib.DATASET_ID
        snapshot_id = lib.REQUIRED_SNAPSHOT
        start_inclusive_ms = lib.DEV_START_MS
        end_exclusive_ms = lib.DEV_END_MS
        allowed_years = (2020, 2021, 2022, 2023, 2024)
        required_gate_names = lib.GATE_NAMES
        seeds = {"bootstrap": lib.SEED_BOOT, "placebo": lib.SEED_PLACEBO}
        def assert_minted(self):
            return None

    class Proof:
        artifact_sha256 = "c" * 64
        result_path = runner.RESULT_PATH

    class Receipt:
        archive_commit_sha = "d" * 40

    class Context:
        run_identity = {
            "hypothesis_id": lib.HYPOTHESIS_ID,
            "window": {
                "start_inclusive_ms": lib.DEV_START_MS,
                "end_exclusive_ms": lib.DEV_END_MS,
                "allowed_years": [2020, 2021, 2022, 2023, 2024],
            },
            "partitions": [{"relative_path": "canonical/1m/monthly/2020-02.parquet"}],
        }
        code_freeze = Freeze()
        def assert_minted(self):
            return None

    class Table:
        def column(self, name):
            frame = _frame(180)
            class Col:
                def __init__(self, values):
                    self._values = values
                def to_numpy(self, zero_copy_only=False):
                    return self._values
            return Col(frame[name])

    monkeypatch.setattr(runner, "verify_batch02_code", lambda **k: calls.append("verify") or Freeze())
    monkeypatch.setattr(
        runner,
        "prepare_batch02_evidence_reservation",
        lambda **k: calls.append("reserve") or Reservation(),
    )
    monkeypatch.setattr(
        runner,
        "prepare_batch02_retained_run",
        lambda **k: calls.append("retained") or Context(),
    )
    monkeypatch.setattr(
        runner,
        "load_authorized_parquet_table",
        lambda **k: calls.append("load") or Table(),
    )
    monkeypatch.setattr(
        runner,
        "persist_batch02_retained_result",
        lambda *a, **k: calls.append("persist") or Proof(),
    )
    monkeypatch.setattr(
        runner,
        "archive_batch02_result",
        lambda **k: calls.append("archive") or Receipt(),
    )
    monkeypatch.setattr(runner, "evaluate_b2_03", lambda frame: {
        "promotion": {"verdict": "B2_03_CLOSED_NO_PROMOTION"}
    })
    monkeypatch.setattr(
        runner,
        "derive_forbidden_window_evidence",
        lambda *a, **k: {"2025_validation": False, "2026_oos": False},
    )
    out = runner.run_development("a" * 40, outcome_access_acknowledged=True)
    assert calls == ["verify", "reserve", "retained", "load", "persist", "archive"]
    assert out["validation_2025_accessed"] is False
    assert "prepare_batch02_run" not in Path(runner.__file__).read_text(encoding="utf-8")
    assert "persist_batch02_result" not in Path(runner.__file__).read_text(encoding="utf-8").replace(
        "persist_batch02_retained_result", ""
    )


def test_runner_source_blocks_historical_api():
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "prepare_batch02_run(" not in source
    assert "persist_batch02_result(" not in source
    assert "prepare_batch02_evidence_reservation" in source
    assert "prepare_batch02_retained_run" in source
    assert "persist_batch02_retained_result" in source
    assert "archive_batch02_result" in source
    lib_source = Path(lib.__file__).read_text(encoding="utf-8")
    assert "batch02_evidence_retention" not in lib_source
    assert "read_parquet" not in lib_source
    assert "rankdata" not in lib_source
    assert "percentileofscore" not in lib_source
    assert "searchsorted" not in lib_source


def test_source_policy_visits_b2_03_runtime_files():
    visited = set(
        validate_batch02_source_tree(
            RESEARCH_DIR,
            repo_root=REPO_ROOT,
        )
    )
    assert RESEARCH_DIR / "b2_03_impulse_morphology.py" in visited
    assert RESEARCH_DIR / "b2_03_impulse_morphology_lib.py" in visited


def test_identity_does_not_touch_outcomes(monkeypatch):
    class Freeze:
        code_sha = "e" * 40
    monkeypatch.setattr(runner, "verify_batch02_code", lambda **k: Freeze())
    out = runner.identity("e" * 40)
    assert out["outcome_accessed"] is False
    assert out["validation_2025_accessed"] is False
    assert out["oos_2026_accessed"] is False
    assert out["prereg_merge_sha"] == lib.PREREG_MERGE_SHA


def test_direction_stratum_has_no_up_down_fallback():
    assert "DIRECTION" in _freeze()["forecast"]["baseline_match"]
    assert _freeze()["baseline_context"]["direction_pooled_in_baseline_dimension"] is False
    up = lib.baseline_stratum_id(
        W=30, direction="UP", displacement_mag_state="LOW", vol_state="HIGH"
    )
    down = lib.baseline_stratum_id(
        W=30, direction="DOWN", displacement_mag_state="LOW", vol_state="HIGH"
    )
    assert up != down


def test_result_path_matches_retained_contract():
    assert runner.RESULT_PATH.as_posix().endswith(
        "artifacts/b2_03_impulse_morphology/B2_03_IMPULSE_MORPHOLOGY_DEV_RESULTS.json"
    )


def _ready_event(
    t: int,
    *,
    W: int = 15,
    direction: str = "UP",
    morph: int = lib.STATE_HIGH,
    mag: int = lib.STATE_MID,
    vol: int = lib.STATE_MID,
) -> dict[str, object]:
    d = 1 if direction == "UP" else -1
    return {
        "T": int(t),
        "W": int(W),
        "d": int(d),
        "direction": direction,
        "D_W": 0.01 * d,
        "abs_disp": 0.01,
        "pre_vol": 0.1,
        "mag_state": int(mag),
        "vol_state": int(vol),
        "morphology_state": int(morph),
        "warmup_only": bool(t < lib.DEV_START_MS),
    }


def _stamp_targets(events, frame, H, scale_cache=None):
    del frame, scale_cache
    out = []
    for event in events:
        record = dict(event)
        record["Y"] = 1.0 if str(event["direction"]) == "UP" else 0.5
        record["target_available"] = True
        record["H"] = int(H)
        out.append(record)
    return out


def test_constant_close_does_not_construct_zero_displacement_events():
    frame = _frame(4 * 60, np.full(4 * 60, 100.0, dtype=np.float64))
    events = lib.construct_events(frame)
    assert events == []


def test_gate_operators_zero_and_nan_are_not_pass():
    zero = lib.per_cell_gates(
        mean_improvement=0.0,
        up_mean=0.1,
        down_mean=0.1,
        relative=0.02,
        bootstrap_lower=0.0,
        placebo_q95=-0.1,
        sep_pooled=0.0,
        sep_up=0.1,
        sep_down=0.1,
    )
    assert zero["primary_positive"] is False
    assert zero["bootstrap_positive"] is False
    assert zero["morphology_ordering"] is False
    nan_down = lib.per_cell_gates(
        mean_improvement=0.5,
        up_mean=1.2,
        down_mean=float("nan"),
        relative=0.05,
        bootstrap_lower=0.1,
        placebo_q95=0.0,
        sep_pooled=0.2,
        sep_up=0.2,
        sep_down=0.2,
    )
    assert nan_down["primary_positive"] is False
    relative_below = lib.per_cell_gates(
        mean_improvement=0.5,
        up_mean=0.1,
        down_mean=0.1,
        relative=0.019999,
        bootstrap_lower=0.1,
        placebo_q95=0.0,
        sep_pooled=0.2,
        sep_up=0.2,
        sep_down=0.2,
    )
    assert relative_below["material_relative_mae"] is False
    relative_eq = lib.per_cell_gates(
        mean_improvement=0.5,
        up_mean=0.1,
        down_mean=0.1,
        relative=0.02,
        bootstrap_lower=0.1,
        placebo_q95=0.0,
        sep_pooled=0.2,
        sep_up=0.2,
        sep_down=0.2,
    )
    assert relative_eq["material_relative_mae"] is True
    placebo_eq = lib.per_cell_gates(
        mean_improvement=0.2,
        up_mean=0.1,
        down_mean=0.1,
        relative=0.05,
        bootstrap_lower=0.1,
        placebo_q95=0.2,
        sep_pooled=0.2,
        sep_up=0.2,
        sep_down=0.2,
    )
    assert placebo_eq["placebo_separation"] is False


def test_one_sided_rescue_fails_primary_and_ordering_operators():
    up_rescue = lib.per_cell_gates(
        mean_improvement=0.5,
        up_mean=1.2,
        down_mean=-0.2,
        relative=0.05,
        bootstrap_lower=0.1,
        placebo_q95=0.0,
        sep_pooled=0.4,
        sep_up=0.8,
        sep_down=-0.1,
    )
    assert up_rescue["primary_positive"] is False
    assert up_rescue["morphology_ordering"] is False
    down_rescue = lib.per_cell_gates(
        mean_improvement=0.5,
        up_mean=-0.2,
        down_mean=1.2,
        relative=0.05,
        bootstrap_lower=0.1,
        placebo_q95=0.0,
        sep_pooled=0.4,
        sep_up=-0.1,
        sep_down=0.8,
    )
    assert down_rescue["primary_positive"] is False
    assert down_rescue["morphology_ordering"] is False
    missing_side = lib._morphology_separation(
        [
            {
                "direction": "UP",
                "morphology_state": lib.STATE_HIGH,
                "base_residual": 1.0,
            },
            {
                "direction": "UP",
                "morphology_state": lib.STATE_LOW,
                "base_residual": 0.1,
            },
        ],
        "DOWN",
    )
    assert math.isnan(missing_side)
    assert missing_side != 0.0


def test_walk_forward_maturation_admits_exact_horizon_boundary(monkeypatch):
    monkeypatch.setattr(lib, "N_PLACEBO", 3)
    monkeypatch.setattr(lib, "N_BOOT", 8)
    monkeypatch.setattr(lib, "BASELINE_MIN_COUNT", 2)
    monkeypatch.setattr(lib, "CANDIDATE_MIN_COUNT", 2)
    monkeypatch.setattr(lib, "_attach_targets", _stamp_targets)
    t0 = lib.DEV_START_MS + 10 * lib.HOUR_MS
    events = [_ready_event(t0 + i * lib.HOUR_MS) for i in range(8)]
    cell_h60 = lib.evaluate_cell(events, {"unused": True}, 15, 60)
    scored = cell_h60["scored"]
    assert scored
    first = scored[0]
    assert first["T"] == t0 + 2 * lib.HOUR_MS
    assert first["baseline_count"] == 2
    assert first["T"] - lib.HOUR_MS + 60 * lib.BAR_MS == first["T"]
    assert all(item.endswith("|60") for item in cell_h60["event_ids"])
    cell_h120 = lib.evaluate_cell(events, {"unused": True}, 15, 120)
    assert cell_h120["N"] == cell_h60["N"] - 1


def test_same_support_candidate_and_baseline_ids_match(monkeypatch):
    monkeypatch.setattr(lib, "N_PLACEBO", 2)
    monkeypatch.setattr(lib, "N_BOOT", 8)
    monkeypatch.setattr(lib, "BASELINE_MIN_COUNT", 4)
    monkeypatch.setattr(lib, "CANDIDATE_MIN_COUNT", 2)
    monkeypatch.setattr(lib, "_attach_targets", _stamp_targets)
    t0 = lib.DEV_START_MS + 20 * lib.HOUR_MS
    events = [
        _ready_event(t0 + i * lib.HOUR_MS, morph=lib.STATE_HIGH if i % 2 else lib.STATE_LOW)
        for i in range(12)
    ]
    cell = lib.evaluate_cell(events, {"unused": True}, 15, 60)
    assert cell["event_ids"]
    assert cell["event_ids"] == [record["event_id"] for record in cell["scored"]]
    for record in cell["scored"]:
        assert record["baseline_count"] >= 4
        assert record["candidate_count"] >= 2
        assert record["event_id"] == lib.canonical_event_id(
            W=15,
            direction=str(record["direction"]),
            T_ms=int(record["T"]),
            H=60,
        )


def test_direction_stratum_does_not_borrow_the_other_side(monkeypatch):
    monkeypatch.setattr(lib, "N_PLACEBO", 2)
    monkeypatch.setattr(lib, "N_BOOT", 8)
    monkeypatch.setattr(lib, "BASELINE_MIN_COUNT", 5)
    monkeypatch.setattr(lib, "CANDIDATE_MIN_COUNT", 3)
    monkeypatch.setattr(lib, "_attach_targets", _stamp_targets)
    t0 = lib.DEV_START_MS + 30 * lib.HOUR_MS
    events = [_ready_event(t0 + i * lib.HOUR_MS, direction="UP") for i in range(10)]
    events.extend(
        [
            _ready_event(
                t0 + (10 + i) * lib.HOUR_MS,
                direction="DOWN",
            )
            for i in range(3)
        ]
    )
    cell = lib.evaluate_cell(events, {"unused": True}, 15, 60)
    assert cell["scored"]
    assert all(record["direction"] == "UP" for record in cell["scored"])
    assert cell["DOWN_count"] == 0
    assert cell["per_cell_gates"]["primary_positive"] is False


def test_placebo_row_order_and_evaluation_label_are_causal(monkeypatch):
    monkeypatch.setattr(lib, "N_PLACEBO", 4)
    monkeypatch.setattr(lib, "N_BOOT", 8)
    monkeypatch.setattr(lib, "BASELINE_MIN_COUNT", 3)
    monkeypatch.setattr(lib, "CANDIDATE_MIN_COUNT", 2)
    monkeypatch.setattr(lib, "_attach_targets", _stamp_targets)
    t0 = lib.DEV_START_MS + 40 * lib.HOUR_MS
    events = [
        _ready_event(
            t0 + i * lib.HOUR_MS,
            morph=lib.STATE_HIGH if i % 2 else lib.STATE_LOW,
        )
        for i in range(10)
    ]
    forward = lib.evaluate_cell(events, {"unused": True}, 15, 60)
    reversed_events = list(reversed(events))
    backward = lib.evaluate_cell(reversed_events, {"unused": True}, 15, 60)
    assert forward["placebo_q95"] == backward["placebo_q95"]
    assert forward["event_ids"] == backward["event_ids"]
    original_by_t = {int(event["T"]): int(event["morphology_state"]) for event in events}
    for record in forward["scored"]:
        assert int(record["morphology_state"]) == original_by_t[int(record["T"])]


def test_support_minima_make_both_models_unavailable(monkeypatch):
    monkeypatch.setattr(lib, "N_PLACEBO", 2)
    monkeypatch.setattr(lib, "N_BOOT", 8)
    monkeypatch.setattr(lib, "BASELINE_MIN_COUNT", 80)
    monkeypatch.setattr(lib, "CANDIDATE_MIN_COUNT", 40)
    monkeypatch.setattr(lib, "_attach_targets", _stamp_targets)
    t0 = lib.DEV_START_MS + 50 * lib.HOUR_MS
    events = [_ready_event(t0 + i * lib.HOUR_MS) for i in range(50)]
    cell = lib.evaluate_cell(events, {"unused": True}, 15, 60)
    assert cell["N"] == 0
    assert cell["event_ids"] == []
    assert cell["per_cell_gates"]["primary_positive"] is False


def _authorized_identity(
    *,
    allowed_years=(2020, 2021, 2022, 2023, 2024),
    end_exclusive_ms=lib.DEV_END_MS,
    partition_paths=(
        "canonical/1m/monthly/2020-02.parquet",
        "canonical/1m/monthly/2024-12.parquet",
    ),
):
    return {
        "hypothesis_id": lib.HYPOTHESIS_ID,
        "window": {
            "start_inclusive_ms": lib.DEV_START_MS,
            "end_exclusive_ms": end_exclusive_ms,
            "allowed_years": list(allowed_years),
        },
        "partitions": [{"relative_path": path} for path in partition_paths],
    }


def _loaded_frame(last_open: int) -> dict[str, np.ndarray]:
    return {
        "open_time_ms": np.asarray([last_open], dtype=np.int64),
        "available_at_ms": np.asarray([last_open + lib.BAR_MS], dtype=np.int64),
        "close": np.asarray([100.0], dtype=np.float64),
    }


def test_forbidden_window_evidence_is_derived_not_asserted():
    last_open = lib.DEV_END_MS - lib.BAR_MS
    evidence = lib.derive_forbidden_window_evidence(
        _authorized_identity(),
        _loaded_frame(last_open),
    )
    assert evidence["2025_validation"] is False
    assert evidence["2026_oos"] is False
    assert evidence["derivation"] == "authorized-view-and-loaded-bytes"
    assert evidence["authorized_max_partition_year"] == 2024
    assert evidence["observed_max_available_at_ms"] <= lib.VALIDATION_2025_START_MS


def test_forbidden_window_evidence_fails_closed_on_2025_identity():
    last_open = lib.DEV_END_MS - lib.BAR_MS
    frame = _loaded_frame(last_open)
    with pytest.raises(lib.B203Error, match="forbidden window"):
        lib.derive_forbidden_window_evidence(
            _authorized_identity(allowed_years=(2020, 2025)),
            frame,
        )
    with pytest.raises(lib.B203Error, match="partitions reach a forbidden window"):
        lib.derive_forbidden_window_evidence(
            _authorized_identity(
                partition_paths=(
                    "canonical/1m/monthly/2020-01.parquet",
                    "canonical/1m/monthly/2025-01.parquet",
                ),
            ),
            frame,
        )
    with pytest.raises(lib.B203Error, match="reserved 2025"):
        lib.derive_forbidden_window_evidence(
            _authorized_identity(end_exclusive_ms=lib.DEV_END_MS + 1),
            frame,
        )
    with pytest.raises(lib.B203Error, match="loaded development bytes"):
        lib.derive_forbidden_window_evidence(
            _authorized_identity(),
            _loaded_frame(lib.DEV_END_MS),
        )


# --- Adversarial red-team repair unit (PR #101 independent review) ---


def test_vol_state_reference_is_the_hourly_grid_not_the_event_population():
    """Attack 1: an hourly T with a valid PRE_VOL_60 but D_W(T)==0 for every W
    must still occupy a slot in the causal VOL_STATE reference population,
    even though it produces zero (T,W) events of its own."""
    n_hours = 8
    n_bars = n_hours * 60 + 1
    open_ms = lib.WARMUP_START_MS + np.arange(n_bars, dtype=np.int64) * lib.BAR_MS
    avail = open_ms + lib.BAR_MS
    close = np.full(n_bars, 100.0, dtype=np.float64)

    t0 = lib.WARMUP_START_MS + 2 * lib.HOUR_MS

    def idx_at(t_end):
        return int((t_end - lib.WARMUP_START_MS) // lib.BAR_MS) - 1

    rng = np.random.default_rng(42)
    # Oscillate strictly inside each 15m sub-segment of PRE_VOL_60(t0)'s 60m
    # window, but leave every 15m anchor (t0-60m, -45m, -30m, -15m, t0) at the
    # same price, so D_15(t0)=D_30(t0)=D_60(t0)=0 exactly while PRE_VOL_60(t0)
    # is nonzero.
    for anchor_offset in range(0, 60, 15):
        seg_start_t = t0 - 60 * lib.BAR_MS + anchor_offset * lib.BAR_MS
        start_i = idx_at(seg_start_t)
        end_i = idx_at(seg_start_t + 15 * lib.BAR_MS)
        for k in range(start_i + 1, end_i):
            close[k] = 100.0 * (1.0 + 0.01 * rng.standard_normal())

    # A later hourly point t1 with a genuine nonzero displacement, so it
    # becomes a real (T,W) event that needs a VOL_STATE percentile.
    t1 = lib.WARMUP_START_MS + 5 * lib.HOUR_MS
    close[idx_at(t1)] = 105.0

    frame = {"open_time_ms": open_ms, "available_at_ms": avail, "close": close}

    vol_times, vol_values = lib.construct_hourly_vol_grid(frame)
    assert int(t0) in {int(t) for t in vol_times}
    t0_value = float(vol_values[list(vol_times).index(t0)])
    assert math.isfinite(t0_value) and t0_value > 0.0

    events = lib.construct_events(frame)
    assert (int(t0), 15) not in {(int(e["T"]), int(e["W"])) for e in events}
    assert (int(t0), 30) not in {(int(e["T"]), int(e["W"])) for e in events}
    assert (int(t0), 60) not in {(int(e["T"]), int(e["W"])) for e in events}

    out = lib.attach_states(events, frame)
    t1_rows = [e for e in out if int(e["T"]) == t1]
    assert t1_rows
    for row in t1_rows:
        # With t0 correctly contributing a prior reference point, t1's
        # VOL_STATE must be decision-available, not spuriously MISSING.
        assert int(row["vol_state"]) >= 0
        assert math.isfinite(float(row["vol_score"]))


def test_construct_events_output_is_unchanged_by_the_vol_grid_refactor():
    """The event-construction refactor that introduced `_iter_hourly_grid`
    must not change `construct_events`' own output at all."""
    frame = _frame(8 * 60)
    events = lib.construct_events(frame)
    assert events
    assert all(int(event["T"]) % lib.HOUR_MS == 0 for event in events)
    assert all(float(event["D_W"]) != 0.0 for event in events)
    assert all(event["W"] in lib.W_VALUES for event in events)
    # Every event must be reachable from the (unfiltered) hourly grid times.
    grid_times = {int(t) for t in lib.construct_hourly_vol_grid(frame)[0]}
    assert {int(event["T"]) for event in events}.issubset(grid_times)


def test_run_development_rejects_unacknowledged_before_any_ceremony_call(monkeypatch):
    """Attack 16: prepare_batch02_retained_run durably claims the one-shot
    remote outcome-access slot before it checks outcome_access_acknowledged.
    run_development() must reject an unacknowledged call before reaching
    verify_batch02_code/prepare_batch02_evidence_reservation/
    prepare_batch02_retained_run at all, so the safe default can never
    accidentally consume the one-shot claim."""

    def _boom(*a, **k):
        raise AssertionError(
            "must not be called before outcome_access_acknowledged is checked"
        )

    monkeypatch.setattr(runner, "verify_batch02_code", _boom)
    monkeypatch.setattr(runner, "prepare_batch02_evidence_reservation", _boom)
    monkeypatch.setattr(runner, "prepare_batch02_retained_run", _boom)
    monkeypatch.setattr(runner, "load_authorized_parquet_table", _boom)
    monkeypatch.setattr(runner, "persist_batch02_retained_result", _boom)
    monkeypatch.setattr(runner, "archive_batch02_result", _boom)

    with pytest.raises(ValueError, match="outcome_access_acknowledged"):
        runner.run_development("a" * 40, outcome_access_acknowledged=False)
    # The safe default (omitted) must behave identically.
    with pytest.raises(ValueError, match="outcome_access_acknowledged"):
        runner.run_development("a" * 40)


def test_placebo_replicate_count_is_reported(monkeypatch):
    monkeypatch.setattr(lib, "_attach_targets", _stamp_targets)
    monkeypatch.setattr(lib, "N_PLACEBO", 5)
    monkeypatch.setattr(lib, "N_BOOT", 8)
    monkeypatch.setattr(lib, "BASELINE_MIN_COUNT", 4)
    monkeypatch.setattr(lib, "CANDIDATE_MIN_COUNT", 2)
    t0 = lib.DEV_START_MS + 60 * lib.HOUR_MS
    events = [
        _ready_event(t0 + i * lib.HOUR_MS, morph=lib.STATE_HIGH if i % 2 else lib.STATE_LOW)
        for i in range(8)
    ]
    cell = lib.evaluate_cell(events, {"unused": True}, 15, 60)
    assert cell["placebo_replicate_count_nominal"] == 5
    assert 0 <= cell["placebo_replicate_count_finite"] <= 5


def test_placebo_replicate_can_never_go_nan_given_the_candidate_min_count_gate(monkeypatch):
    """Attack 10, resolved: a permutation preserves label COUNTS exactly, and
    every candidate-queue member is also a baseline-queue member (inserted at
    the same maturation step), so len(candidate_queue) >= CANDIDATE_MIN_COUNT
    structurally guarantees the evaluation event's own morphology-state label
    appears at least CANDIDATE_MIN_COUNT times in the baseline pool. This
    pins that invariant: with the smallest legal CANDIDATE_MIN_COUNT (1),
    every placebo replicate must be finite -- 0 -> 100 degradation is not
    reachable through this gate."""
    monkeypatch.setattr(lib, "N_PLACEBO", 50)
    monkeypatch.setattr(lib, "N_BOOT", 8)
    monkeypatch.setattr(lib, "BASELINE_MIN_COUNT", 5)
    monkeypatch.setattr(lib, "CANDIDATE_MIN_COUNT", 1)
    monkeypatch.setattr(lib, "_attach_targets", _stamp_targets)
    t0 = lib.DEV_START_MS + 100 * lib.HOUR_MS
    events = [_ready_event(t0 + i * lib.HOUR_MS, morph=lib.STATE_LOW) for i in range(4)]
    events.append(_ready_event(t0 + 4 * lib.HOUR_MS, morph=lib.STATE_HIGH))
    events.append(_ready_event(t0 + 5 * lib.HOUR_MS, morph=lib.STATE_HIGH))
    cell = lib.evaluate_cell(events, {"unused": True}, 15, 60)
    assert cell["N"] == 1
    assert cell["placebo_replicate_count_nominal"] == 50
    assert cell["placebo_replicate_count_finite"] == 50
    assert cell["placebo_q95"] is not None


def test_mosaic_per_gate_evidence_cannot_promote_without_a_qualifying_neighborhood():
    """Attack 13: a disjoint mosaic of individual-gate passes spread across
    different W's, with no single W holding all five per-cell gates
    together, must not promote -- even though it can make every one of the
    five aggregated per-gate booleans read True."""

    def cell(W, H, gate_names, year=True):
        return {
            "W": W,
            "H": H,
            "year_stability_pass": year,
            "per_cell_gates": {
                name: (name in gate_names) for name in lib.PER_CELL_GATE_NAMES
            },
        }

    cells = [
        cell(W, H, set())
        for W in lib.W_VALUES
        for H in lib.H_VALUES
    ]
    by = {(c["W"], c["H"]): i for i, c in enumerate(cells)}
    w15 = {"primary_positive", "material_relative_mae", "morphology_ordering"}
    w30 = {
        "primary_positive",
        "material_relative_mae",
        "bootstrap_positive",
        "placebo_separation",
    }
    w60 = {"bootstrap_positive", "placebo_separation", "morphology_ordering"}
    for H in (15, 30):
        cells[by[(15, H)]] = cell(15, H, w15)
        cells[by[(30, H)]] = cell(30, H, w30)
        cells[by[(60, H)]] = cell(60, H, w60)

    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert all(gates[name] is True for name in lib.PER_CELL_GATE_NAMES)
    assert gates["horizon_robustness"] is False
    assert gates["parameter_robustness"] is False
    assert gates["year_stability"] is False
    assert neighborhoods == []
    passed = bool(neighborhoods) and all(
        gates.get(name) is True for name in lib.GATE_NAMES
    )
    assert passed is False


def _oracle_week_bootstrap(improvements, times, W, H):
    groups: dict[int, list[float]] = {}
    for value, t in zip(improvements, times):
        day = int(t) // lib.DAY_MS
        week = (day + 3) // 7
        groups.setdefault(week, []).append(float(value))
    keys = sorted(groups)
    sums = np.asarray([sum(groups[k]) for k in keys])
    counts = np.asarray([len(groups[k]) for k in keys])
    rng = np.random.default_rng(lib.seed_int((lib.SEED_BOOT, int(W), int(H))))
    draws = np.empty(lib.N_BOOT)
    for rep in range(lib.N_BOOT):
        sampled = rng.integers(0, len(keys), size=len(keys))
        denom = int(np.sum(counts[sampled]))
        draws[rep] = float(np.sum(sums[sampled]) / denom) if denom > 0 else float("nan")
    finite = draws[np.isfinite(draws)]
    return float(np.quantile(finite, 0.025)), float(np.quantile(finite, 0.975))


def test_independent_oracle_matches_week_bootstrap_pooled_weighting():
    """Attack 11: independently reproduce the resampling using only
    the seed/week-key primitives (not by calling `_week_bootstrap_interval`
    internals), for weeks with unequal event counts."""
    improvements = np.asarray([1.0, 1.0, 1.0, 1.0, 1.0, -10.0], dtype=np.float64)
    t0 = lib.DEV_START_MS
    times = np.asarray(
        [t0 + i * lib.DAY_MS for i in range(5)] + [t0 + 30 * lib.DAY_MS],
        dtype=np.int64,
    )
    lo, hi = lib._week_bootstrap_interval(improvements, times, 15, 60)
    oracle_lo, oracle_hi = _oracle_week_bootstrap(improvements, times, 15, 60)
    assert lo == oracle_lo
    assert hi == oracle_hi


def test_independent_oracle_matches_baseline_candidate_ae_improvement_and_placebo(
    monkeypatch,
):
    """Attack 18: a from-scratch oracle for the core evaluate_cell arithmetic
    (baseline/candidate median, AE improvement, and the single-replicate
    placebo mapping), computed without calling evaluate_cell's own helpers
    for the compared quantities."""
    monkeypatch.setattr(lib, "N_PLACEBO", 1)
    monkeypatch.setattr(lib, "N_BOOT", 8)
    monkeypatch.setattr(lib, "BASELINE_MIN_COUNT", 80)
    monkeypatch.setattr(lib, "CANDIDATE_MIN_COUNT", 5)
    monkeypatch.setattr(lib, "_attach_targets", _stamp_targets_with_values)

    t0 = lib.DEV_START_MS + 200 * lib.HOUR_MS
    low_ys = [float(i) for i in range(30)]
    mid_ys = [float(100 + i) for i in range(25)]
    high_ys = [float(200 + i) for i in range(25)]
    events = []
    i = 0
    for y in low_ys:
        events.append(_ready_event_with_y(t0 + i * lib.HOUR_MS, lib.STATE_LOW, y))
        i += 1
    for y in mid_ys:
        events.append(_ready_event_with_y(t0 + i * lib.HOUR_MS, lib.STATE_MID, y))
        i += 1
    for y in high_ys:
        events.append(_ready_event_with_y(t0 + i * lib.HOUR_MS, lib.STATE_HIGH, y))
        i += 1
    eval_t = t0 + i * lib.HOUR_MS
    eval_y = 999.0
    events.append(_ready_event_with_y(eval_t, lib.STATE_HIGH, eval_y))

    cell = lib.evaluate_cell(events, {"unused": True}, 15, 60)
    assert cell["N"] == 1
    record = cell["scored"][0]

    all_ys = sorted(low_ys + mid_ys + high_ys)
    oracle_base_pred = float(np.median(np.asarray(all_ys)))
    oracle_cand_pred = float(np.median(np.asarray(sorted(high_ys))))
    oracle_base_ae = abs(eval_y - oracle_base_pred)
    oracle_cand_ae = abs(eval_y - oracle_cand_pred)
    oracle_improvement = oracle_base_ae - oracle_cand_ae

    assert record["base_pred"] == oracle_base_pred
    assert record["candidate_pred"] == oracle_cand_pred
    assert record["base_ae"] == pytest.approx(oracle_base_ae)
    assert record["candidate_ae"] == pytest.approx(oracle_cand_ae)
    assert record["ae_improvement"] == pytest.approx(oracle_improvement)

    sorted_items = sorted(
        [
            (
                int(e["T"]),
                float(e["Y"]),
                lib.state_label(int(e["morphology_state"])),
                lib.canonical_event_id(W=15, direction="UP", T_ms=int(e["T"]), H=60),
            )
            for e in events[:-1]
        ],
        key=lambda item: item[3],
    )
    sorted_y = np.asarray([item[1] for item in sorted_items])
    sorted_labels = np.asarray([item[2] for item in sorted_items])
    stratum = lib.baseline_stratum_id(
        W=15, direction="UP", displacement_mag_state="MID", vol_state="MID"
    )
    rng = np.random.default_rng(
        lib.seed_int((lib.SEED_PLACEBO, 0, 15, 60, eval_t, stratum))
    )
    permuted = rng.permutation(sorted_labels)
    chosen = sorted_y[permuted == "HIGH"]
    oracle_placebo_pred = float(np.median(chosen))
    oracle_placebo_improvement = oracle_base_ae - abs(eval_y - oracle_placebo_pred)
    assert cell["placebo_q95"] == pytest.approx(oracle_placebo_improvement)


def _ready_event_with_y(t, morph, y, *, W=15, direction="UP", mag=lib.STATE_MID, vol=lib.STATE_MID):
    d = 1 if direction == "UP" else -1
    return {
        "T": int(t), "W": int(W), "d": int(d), "direction": direction,
        "D_W": 0.01 * d, "abs_disp": 0.01, "pre_vol": 0.1,
        "mag_state": int(mag), "vol_state": int(vol), "morphology_state": int(morph),
        "warmup_only": False, "Y": float(y), "target_available": True,
    }


def _stamp_targets_with_values(events, frame, H, scale_cache=None):
    del frame, scale_cache
    out = []
    for event in events:
        record = dict(event)
        record["H"] = int(H)
        out.append(record)
    return out
