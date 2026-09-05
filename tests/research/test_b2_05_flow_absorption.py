"""Adversarial synthetic tests for the frozen B2-05 implementation.

These tests must not open real CORE parquet, create a production evidence
reservation, claim outcome access, or invoke run_development against real
market data. Synthetic fixtures only.

Sections follow the required adversarial matrix in the implementation brief:
chronology/no-lookahead, same support, malformed flow, canonical identity,
percentile/state, nuisance quintiles, OLS solver, placebo, bootstrap,
promotion, anti-rescue, performance-equivalence oracles, and static source
audits.
"""
from __future__ import annotations

import ast
import hashlib
import math
from pathlib import Path

import numpy as np
import pytest

from scripts.research import b2_05_flow_absorption as runner
from scripts.research import b2_05_flow_absorption_lib as lib
from scripts.research.lib.batch02_source_policy import validate_batch02_source_tree


REPO_ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DIR = REPO_ROOT / "scripts" / "research"
LIB_SRC = (RESEARCH_DIR / "b2_05_flow_absorption_lib.py").read_text(encoding="utf-8")
RUNNER_SRC = (RESEARCH_DIR / "b2_05_flow_absorption.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
def _flat_frame(n_days, *, base_volume=10.0, taker_ratio=0.5, seed=0, vol=0.0006, start_ms=None):
    """A synthetic 1m frame: geometric-random-walk close, roughly balanced
    or side-biased taker flow depending on `taker_ratio`."""
    rng = np.random.default_rng(seed)
    n = int(n_days) * 24 * 60
    start = lib.WARMUP_START_MS if start_ms is None else int(start_ms)
    open_ms = start + np.arange(n, dtype=np.int64) * lib.BAR_MS
    avail_ms = open_ms + lib.BAR_MS
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, vol, n)))
    if isinstance(base_volume, (int, float)):
        bv = np.full(n, float(base_volume))
    else:
        bv = np.asarray(base_volume, dtype=np.float64)
    if isinstance(taker_ratio, (int, float)):
        tr = np.full(n, float(taker_ratio))
    else:
        tr = np.asarray(taker_ratio, dtype=np.float64)
    taker_buy = bv * tr
    return {
        "open_time_ms": open_ms,
        "available_at_ms": avail_ms,
        "close": close,
        "base_volume": bv,
        "taker_buy_base_volume": taker_buy,
    }


def _varying_frame(n_days, *, taker_ratio_mean=0.5, seed=0, vol=0.0006, start_ms=None):
    """Like `_flat_frame`, but base_volume and the taker ratio jitter around
    their means instead of being perfectly constant. A perfectly flat
    volume/ratio makes ABS_IMB/RV_W/LOG_ACTIVITY exactly constant across an
    entire pool, which fails OLS standardization (std == 0) for every week
    and silently produces zero scored records -- this fixture is required
    for any test that needs a genuinely scoreable (N > 0) cell. The ratio
    mean is centered near 0.5 (not strongly biased toward one side): a
    strong bias leaves ~0 rows of the minority side in most windows, making
    SIDE_BUY constant and perfectly collinear with the intercept -- a
    genuine (correctly detected) rank-deficient baseline design, not a bug,
    but not what a "both sides present" fixture needs either."""
    rng = np.random.default_rng(seed)
    n = int(n_days) * 24 * 60
    start = lib.WARMUP_START_MS if start_ms is None else int(start_ms)
    open_ms = start + np.arange(n, dtype=np.int64) * lib.BAR_MS
    avail_ms = open_ms + lib.BAR_MS
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, vol, n)))
    base_volume = np.abs(rng.normal(10.0, 2.0, n)) + 1.0
    ratio = np.clip(rng.normal(taker_ratio_mean, 0.06, n), 0.05, 0.95)
    taker_buy = base_volume * ratio
    return {
        "open_time_ms": open_ms,
        "available_at_ms": avail_ms,
        "close": close,
        "base_volume": base_volume,
        "taker_buy_base_volume": taker_buy,
    }


def _shrink_thresholds(monkeypatch, **overrides):
    """Shrink the frozen-but-large minimum-N / lookback constants so a small
    synthetic frame can exercise the full weekly walk-forward + placebo
    pipeline quickly. Every value shrunk here is a *quantity threshold*, never
    a formula, seed, or solver -- the scientific contract is not altered."""
    defaults = {
        "MIN_IMPACT_REF_N": 5,
        "MIN_NUISANCE_REF_N": 5,
        "MIN_BASELINE_N": 8,
        "MIN_CANDIDATE_N": 6,
        "MIN_CANDIDATE_N_PER_STATE": 2,
        "IMPACT_REF_MS": 3 * lib.DAY_MS,
        "NUISANCE_REF_MS": 3 * lib.DAY_MS,
        "TRAIN_MS": 6 * lib.DAY_MS,
        "N_PLACEBO": 5,
        "N_BOOT": 20,
    }
    defaults.update(overrides)
    for name, value in defaults.items():
        monkeypatch.setattr(lib, name, value)


# ---------------------------------------------------------------------------
# 1. chronology / no lookahead
# ---------------------------------------------------------------------------
def test_scoring_eligible_rejects_equality_at_2025_boundary_and_accepts_before():
    h = 30
    t_at_boundary = lib.DEV_END_MS - h * lib.BAR_MS  # T + H == DEV_END_MS exactly
    assert lib.scoring_eligible(t_at_boundary, h) is False
    t_one_grid_earlier = t_at_boundary - lib.HTF_MS
    assert lib.scoring_eligible(t_one_grid_earlier, h) is True


def test_scoring_eligible_rejects_off_grid_and_pre_dev_start():
    assert lib.scoring_eligible(lib.DEV_START_MS + 1, 30) is False  # off 15m grid
    assert lib.scoring_eligible(lib.DEV_START_MS - lib.HTF_MS, 30) is False  # pre-dev
    assert lib.scoring_eligible(lib.DEV_START_MS, 30) is True


def test_horizon_returns_excludes_illegal_and_off_grid_destinations():
    close15 = np.array([100.0, 101.0, 102.0, 103.0])
    t_ms15 = np.array(
        [lib.DEV_END_MS - 4 * lib.HTF_MS, lib.DEV_END_MS - 3 * lib.HTF_MS,
         lib.DEV_END_MS - 2 * lib.HTF_MS, lib.DEV_END_MS - lib.HTF_MS],
        dtype=np.int64,
    )
    out = lib.horizon_returns(close15, t_ms15, lib.HTF_MIN)
    # last index has no destination in-array -> nan regardless of legality
    assert math.isnan(out[-1])
    # first index: T+H = DEV_END_MS-3*HTF -> legal, on-grid, destination exists
    assert math.isfinite(out[0])
    assert out[0] == pytest.approx(math.log(101.0 / 100.0))


def test_impact_state_reference_excludes_current_and_future():
    # Two same-side records 1 day apart; the earlier's IMPACT_INTERACTION
    # must not be influenced by the later (future) one, and a record is
    # never its own reference.
    t_ms = np.array([0, lib.DAY_MS], dtype=np.int64)
    side_code = np.array([1, 1], dtype=np.int8)
    values = np.array([1.0, 100.0], dtype=np.float64)
    pct = lib._causal_standing_by_side(
        t_ms, side_code, values, lookback_ms=10 * lib.DAY_MS, min_ref_n=1
    )
    # first record has zero references (nothing precedes it) -> NaN despite
    # min_ref_n=1 (0 refs available)
    assert math.isnan(pct[0])
    # second record's percentile is computed purely from the FIRST (past)
    # record, not from itself: with one smaller reference and no equal
    # reference, midrank = (count(<x) + 0.5*count(==x)) / N = (1+0)/1 = 1.0
    assert pct[1] == pytest.approx(1.0)


def test_target_scale_reference_requires_t_plus_h_le_t_and_excludes_future(monkeypatch):
    monkeypatch.setattr(lib, "SCALE_REF_STEPS", 4)
    n = 12
    close15 = 100.0 * np.exp(np.cumsum(np.full(n, 0.001)))
    t_ms15 = np.arange(n, dtype=np.int64) * lib.HTF_MS
    raw = lib.horizon_returns(close15, t_ms15, lib.HTF_MIN)
    scale = lib.past_median_abs_return(np.abs(raw), lib.HTF_MIN)
    # span = SCALE_REF_STEPS - h_steps + 1 = 4-1+1 = 4; index 4 is the first
    # with a full 4-wide window of *matured* references strictly before it
    assert math.isnan(scale[3])  # not enough matured history yet
    assert math.isfinite(scale[4])


def test_training_pool_requires_t_e_plus_h_le_s(monkeypatch):
    _shrink_thresholds(monkeypatch, MIN_BASELINE_N=1000000, MIN_CANDIDATE_N=1000000)
    frame = _flat_frame(20)
    frame15 = lib.aggregate_1m_to_15m(frame)
    flow = lib.build_flow_frame(frame, 15, frame15["close"], frame15["t_ms"])
    flow = lib.attach_impact_state(flow)
    flow = lib.attach_nuisance_bins(flow)
    # With impossibly high minimums every week is unavailable -> zero scored
    cell = lib.evaluate_cell(flow, 30)
    assert cell["N"] == 0


def test_training_pool_boundary_t_e_plus_h_equals_s_is_eligible_greater_is_not():
    # Direct boundary proof against the exact predicate evaluate_cell's
    # weekly walk-forward loop uses (lib.training_pool_window), independent
    # of OLS rank/standardization concerns.
    h = 30
    s = lib.iso_week_start_ms(lib.DEV_START_MS + 100 * lib.DAY_MS)
    boundary_t_eligible = s - h * lib.BAR_MS  # T_e + H == S exactly
    boundary_t_ineligible = boundary_t_eligible + lib.HTF_MS  # T_e + H == S + 15m > S

    times_eligible = np.array([boundary_t_eligible], dtype=np.int64)
    left, right = lib.training_pool_window(times_eligible, s, h, 1000 * lib.DAY_MS)
    assert (left, right) == (0, 1)  # included

    times_ineligible = np.array([boundary_t_ineligible], dtype=np.int64)
    left, right = lib.training_pool_window(times_ineligible, s, h, 1000 * lib.DAY_MS)
    assert (left, right) == (0, 0)  # excluded


def test_training_pool_window_matches_brute_force_oracle():
    # s/h/train_ms chosen so the window [cutoff_low, upper_bound] is
    # genuinely non-empty against the sampled `times` domain -- a prior
    # revision of this fixture (s=1_500_000, h=30, train_ms=900_000) gave
    # upper_bound = -300_000, which is unreachable by any t >= 0 and made
    # the oracle vacuously pass on an always-empty interval.
    rng = np.random.default_rng(13)
    times = np.sort(rng.choice(np.arange(0, 2_000_000, 15_000), size=80, replace=False)).astype(np.int64)
    s = 3_000_000
    h = 30
    train_ms = 2_000_000
    left, right = lib.training_pool_window(times, s, h, train_ms)
    upper_bound = s - h * lib.BAR_MS
    cutoff_low = s - train_ms
    brute_included = [i for i, t in enumerate(times) if cutoff_low <= t <= upper_bound]
    assert brute_included  # the fixture must exercise a non-empty window
    assert left == brute_included[0]
    assert right == brute_included[-1] + 1


def test_training_pool_window_boundary_matches_brute_force_at_exact_edges():
    # Direct exact-boundary proof, independent of the general oracle above:
    # T_e + H == S must be included; T_e + H == S + one grid step (> S)
    # must be excluded. Failing either would mean the production helper's
    # boundary drifted.
    h = 30
    s = 3_000_000
    train_ms = 2_000_000
    included_t = s - h * lib.BAR_MS
    excluded_t = included_t + lib.HTF_MS
    times = np.array([included_t, excluded_t], dtype=np.int64)
    left, right = lib.training_pool_window(times, s, h, train_ms)
    assert (left, right) == (0, 1)


# ---------------------------------------------------------------------------
# 2. same support
# ---------------------------------------------------------------------------
def test_baseline_and_candidate_current_score_ids_are_exactly_equal(monkeypatch):
    _shrink_thresholds(monkeypatch)
    # _varying_frame (not _flat_frame): a perfectly flat volume/ratio makes
    # every continuous feature exactly constant across a whole pool, which
    # fails OLS standardization (std == 0) every week and silently produces
    # zero scored records -- a vacuously-passing test.
    frame = _varying_frame(40)
    frame15 = lib.aggregate_1m_to_15m(frame)
    flow = lib.build_flow_frame(frame, 15, frame15["close"], frame15["t_ms"])
    flow = lib.attach_impact_state(flow)
    flow = lib.attach_nuisance_bins(flow)
    cell = lib.evaluate_cell(flow, 30)
    assert cell["N"] > 0  # non-vacuous: this cell must actually score records
    for record in cell["scored"]:
        # every scored record carries both a base_pred and candidate_pred --
        # there is no code path that scores one model without the other.
        assert math.isfinite(record["base_pred"])
        assert math.isfinite(record["candidate_pred"])
    assert cell["same_support"]["score_record_count"] == len(cell["score_record_ids"])
    assert len(set(cell["score_record_ids"])) == len(cell["score_record_ids"])


def test_canonical_row_order_differs_from_t_only_order_for_mixed_sides():
    # The frozen CANONICAL_SCORE_RECORD_ID places `side` BEFORE the
    # timestamp fields, so a pool mixing BUY and SELL rows sorted by id
    # groups all BUY rows (lexicographically first) ahead of all SELL rows
    # -- NOT the same order as a plain ascending-T sort across both sides.
    base_t = lib.DEV_START_MS
    pool = np.array([0, 1, 2, 3], dtype=np.int64)  # positional indices
    t_ms = np.array(
        [base_t, base_t + lib.HTF_MS, base_t + 2 * lib.HTF_MS, base_t + 3 * lib.HTF_MS],
        dtype=np.int64,
    )
    # T-ascending sides: SELL, BUY, SELL, BUY
    side_code = np.array([-1, 1, -1, 1], dtype=np.int8)

    t_order = np.sort(pool)
    assert list(t_order) == [0, 1, 2, 3]  # the old (buggy) T-only order

    id_order = lib._sort_pool_by_canonical_score_id(
        pool, w_minutes=15, h_minutes=30, side_code=side_code, t_ms=t_ms,
        snapshot_id=lib.REQUIRED_SNAPSHOT,
    )
    # canonical-id order groups BUY (indices 1, 3) before SELL (0, 2),
    # each side internally ascending by T -- exactly [1, 3, 0, 2].
    assert list(id_order) == [1, 3, 0, 2]
    assert list(id_order) != list(t_order)

    ids = lib._pool_score_ids(
        pool, w_minutes=15, h_minutes=30, side_code=side_code, t_ms=t_ms,
        snapshot_id=lib.REQUIRED_SNAPSHOT,
    )
    reordered_ids = [ids[i] for i in id_order]
    assert reordered_ids == sorted(ids)


def test_evaluate_cell_calls_the_canonical_sort_not_a_bare_t_sort():
    # Mutation-proof for Blocker 3: OLS is permutation-invariant in its row
    # order (the fitted coefficients do not observably change), so an
    # end-to-end numeric comparison cannot distinguish "sorted by canonical
    # score id" from "sorted by bare T" -- the two orderings must instead be
    # enforced structurally. This inspects evaluate_cell's own source body
    # to prove it calls _sort_pool_by_canonical_score_id for both pools and
    # does not fall back to a bare np.sort(pool) substitute.
    tree = ast.parse(LIB_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "evaluate_cell":
            src = ast.get_source_segment(LIB_SRC, node)
            assert src.count("_sort_pool_by_canonical_score_id(") == 2
            assert "np.sort(baseline_pool)" not in src
            assert "np.sort(candidate_pool)" not in src
            break
    else:
        raise AssertionError("evaluate_cell not found")


def test_candidate_unavailability_removes_current_record_from_both(monkeypatch):
    # Force candidate to always be unavailable (impossible per-state N) while
    # baseline remains trivially satisfiable; scoring must then be zero for
    # BOTH models, not baseline-only.
    _shrink_thresholds(monkeypatch, MIN_CANDIDATE_N_PER_STATE=1000000)
    frame = _flat_frame(40, taker_ratio=0.6)
    frame15 = lib.aggregate_1m_to_15m(frame)
    flow = lib.build_flow_frame(frame, 15, frame15["close"], frame15["t_ms"])
    flow = lib.attach_impact_state(flow)
    flow = lib.attach_nuisance_bins(flow)
    cell = lib.evaluate_cell(flow, 30)
    assert cell["N"] == 0


def test_placebo_uses_exact_real_scored_support_not_all_current_week(monkeypatch):
    """Blocker 2 regression: one current-week candidate index whose REAL
    base/candidate prediction is nonfinite (here, an overflowed FLOW_RET
    standardization -- the same `math.isfinite(base_pred)`/
    `math.isfinite(cand_pred)` check the production code already applies to
    every scored record) must be silently excluded from scoring -- and,
    critically, must not appear only in the placebo accumulation either
    (which would KeyError on base_ae_by_i or silently normalize by a
    different denominator than the real support)."""
    _shrink_thresholds(monkeypatch, N_PLACEBO=3)
    frame = _varying_frame(40)
    frame15 = lib.aggregate_1m_to_15m(frame)
    flow = lib.build_flow_frame(frame, 15, frame15["close"], frame15["t_ms"])
    flow = lib.attach_impact_state(flow)
    flow = lib.attach_nuisance_bins(flow)

    # Establish a normal baseline run first to find a genuinely scoreable
    # current-week index to poison.
    baseline_cell = lib.evaluate_cell(flow, 30)
    assert baseline_cell["N"] > 0
    poisoned_index = baseline_cell["scored"][-1]["index"]

    # Inject a non-finite FLOW_RET at that one current record only -- once
    # standardized (z = (x - mean) / std) and dotted with a nonzero
    # coefficient, this deterministically overflows base_pred/cand_pred to
    # a non-finite value, exercising the exact `math.isfinite` guard the
    # production code already applies. Every other record is untouched.
    poisoned_flow_ret = np.array(flow["flow_ret"], copy=True)
    poisoned_flow_ret[poisoned_index] = np.inf
    flow["flow_ret"] = poisoned_flow_ret
    flow["impact_interaction"] = np.where(
        flow["side_code"] != 0, flow["abs_imb"] * flow["flow_ret"], np.nan
    )

    cell = lib.evaluate_cell(flow, 30)  # must not raise (no KeyError)
    scored_indices = {r["index"] for r in cell["scored"]}
    assert poisoned_index not in scored_indices
    assert cell["N"] == baseline_cell["N"] - 1
    assert cell["placebo_replicate_count_finite"] <= lib.N_PLACEBO


def test_evaluate_cell_requires_joint_finite_predictions_before_scoring():
    """Same-support construction must not rescue a failed candidate
    prediction with a dummy (0.0 / baseline-only) value. The joint
    `isfinite(base_pred) and isfinite(cand_pred)` gate is the production
    enforcement; a mutation that keeps the event when only the candidate
    is nonfinite would otherwise survive the FLOW_RET-poison test above
    (that poison overflows both models)."""
    tree = ast.parse(LIB_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "evaluate_cell":
            src = ast.get_source_segment(LIB_SRC, node)
            assert "math.isfinite(base_pred) and math.isfinite(cand_pred)" in src
            assert "cand_pred = 0.0" not in src
            break
    else:
        raise AssertionError("evaluate_cell not found")


def test_nonfinite_candidate_standardization_does_not_retain_baseline_only(
    monkeypatch,
):
    """Candidate-only z-score explosion must drop the current record from
    both models. A dummy `cand_pred = 0.0` rescue would keep N unchanged."""
    _shrink_thresholds(monkeypatch)
    frame = _varying_frame(40)
    frame15 = lib.aggregate_1m_to_15m(frame)
    flow = lib.build_flow_frame(frame, 15, frame15["close"], frame15["t_ms"])
    flow = lib.attach_impact_state(flow)
    flow = lib.attach_nuisance_bins(flow)
    baseline_cell = lib.evaluate_cell(flow, 30)
    assert baseline_cell["N"] > 0

    real_standardize = lib._standardize
    calls = {"n": 0}

    def explode_candidate_std(pool_matrix):
        mean, std = real_standardize(pool_matrix)
        calls["n"] += 1
        if mean is None or std is None:
            return mean, std
        # evaluate_cell standardizes baseline then candidate each week.
        if calls["n"] % 2 == 0:
            std = np.asarray(std, dtype=np.float64).copy()
            std[:] = 1e-320
        return mean, std

    monkeypatch.setattr(lib, "_standardize", explode_candidate_std)
    exploded = lib.evaluate_cell(flow, 30)
    assert exploded["N"] < baseline_cell["N"]
    for record in exploded["scored"]:
        assert math.isfinite(record["base_pred"])
        assert math.isfinite(record["candidate_pred"])


# ---------------------------------------------------------------------------
# 3. malformed flow rows fail closed
# ---------------------------------------------------------------------------
def _flow_at(flow, m):
    return {
        "total_w": flow["total_w"][m],
        "taker_buy_w": flow["taker_buy_w"][m],
        "imb": flow["imb"][m],
        "side_code": flow["side_code"][m],
        "valid_features": flow["valid_features"][m],
    }


def test_negative_base_volume_row_poisons_touching_windows():
    # taker_ratio != 0.5 so IMB is nonzero (side determined) away from the
    # malformed row -- a flat 0.5 ratio would make every window's IMB
    # exactly zero and mask the poisoning-scope assertion below.
    frame = _flat_frame(3, base_volume=10.0, taker_ratio=0.6)
    frame["base_volume"][100] = -1.0  # one malformed row
    frame15 = lib.aggregate_1m_to_15m(frame)
    flow = lib.build_flow_frame(frame, 15, frame15["close"], frame15["t_ms"])
    # the 15m bucket containing 1m index 100 must be invalid
    bucket = 100 // lib.HTF_MIN
    assert not flow["valid_features"][bucket]
    # a bucket far away must remain valid
    assert flow["valid_features"][bucket + 50]


def test_taker_buy_negative_or_exceeding_base_fails_closed():
    # taker_ratio=0.6 (not the flat-0.5 default) so IMB is nonzero and side
    # is determined away from the malformed rows -- a flat 0.5 ratio would
    # make every window's IMB exactly zero and mask the positive-control
    # (distant clean window) assertion below.
    frame = _flat_frame(3, taker_ratio=0.6)
    frame["taker_buy_base_volume"][50] = -0.1
    frame["taker_buy_base_volume"][51] = frame["base_volume"][51] * 2.0
    frame15 = lib.aggregate_1m_to_15m(frame)
    flow = lib.build_flow_frame(frame, 15, frame15["close"], frame15["t_ms"])
    bucket_50 = 50 // lib.HTF_MIN
    bucket_51 = 51 // lib.HTF_MIN
    assert not flow["valid_features"][bucket_50]
    assert not flow["valid_features"][bucket_51]
    # positive control: a distant, untouched window remains valid
    far = bucket_51 + 40
    assert flow["valid_features"][far]


def test_total_w_zero_is_unavailable():
    frame = _flat_frame(3, base_volume=0.0, taker_ratio=0.0)
    frame15 = lib.aggregate_1m_to_15m(frame)
    flow = lib.build_flow_frame(frame, 15, frame15["close"], frame15["t_ms"])
    assert not np.any(flow["valid_features"])
    assert np.all(flow["side_code"] == 0)


def test_imb_exactly_zero_is_unavailable():
    # taker_ratio == 0.5 => TAKER_BUY_W == TOTAL_W/2 => IMB == 0 exactly
    frame = _flat_frame(3, base_volume=10.0, taker_ratio=0.5, vol=0.0)
    frame15 = lib.aggregate_1m_to_15m(frame)
    flow = lib.build_flow_frame(frame, 15, frame15["close"], frame15["t_ms"])
    assert np.all(flow["side_code"] == 0)
    assert not np.any(flow["valid_features"])


def test_nan_and_inf_volume_rows_fail_closed_not_propagate():
    # taker_ratio=0.6 so side is determined away from the malformed rows --
    # see test_taker_buy_negative_or_exceeding_base_fails_closed for why the
    # flat-0.5 default would make this a vacuous positive control.
    frame = _flat_frame(3, taker_ratio=0.6)
    frame["base_volume"][200] = float("nan")
    frame["taker_buy_base_volume"][201] = float("inf")
    frame15 = lib.aggregate_1m_to_15m(frame)
    flow = lib.build_flow_frame(frame, 15, frame15["close"], frame15["t_ms"])
    b1 = 200 // lib.HTF_MIN
    b2 = 201 // lib.HTF_MIN
    assert not flow["valid_features"][b1]
    assert not flow["valid_features"][b2]
    # positive control: no NaN/inf leaks into an otherwise-valid distant
    # bucket -- a hard assertion, not a conditional one.
    far = b1 + 40
    assert flow["valid_features"][far]
    assert math.isfinite(flow["total_w"][far])


def test_table_to_1m_frame_tolerates_malformed_volume_without_raising():
    class _Col:
        def __init__(self, values):
            self._values = np.asarray(values)

        def to_numpy(self, zero_copy_only=False):
            del zero_copy_only
            return self._values

    class _Table:
        def __init__(self, columns):
            self._columns = columns

        def column(self, name):
            return self._columns[name]

    n = lib.HTF_MIN * 4
    open_ms = lib.WARMUP_START_MS + np.arange(n, dtype=np.int64) * lib.BAR_MS
    base_volume = np.full(n, 10.0)
    base_volume[0] = -5.0  # malformed, must not raise at table-conversion time
    table = _Table(
        {
            "open_time_ms": _Col(open_ms),
            "available_at_ms": _Col(open_ms + lib.BAR_MS),
            "close": _Col(np.full(n, 100.0)),
            "base_volume": _Col(base_volume),
            "taker_buy_base_volume": _Col(np.full(n, 5.0)),
        }
    )
    frame = runner.table_to_1m_frame(table)
    assert frame["base_volume"][0] == -5.0


# ---------------------------------------------------------------------------
# 4. canonical identity never collides
# ---------------------------------------------------------------------------
def test_canonical_ids_differ_by_W_side_T_H():
    base = dict(W=15, side="BUY", T_ms=lib.DEV_START_MS)
    id_a = lib.canonical_base_event_id(**base)
    id_w = lib.canonical_base_event_id(**{**base, "W": 30})
    id_side = lib.canonical_base_event_id(**{**base, "side": "SELL"})
    id_t = lib.canonical_base_event_id(**{**base, "T_ms": lib.DEV_START_MS + lib.HTF_MS})
    ids = {id_a, id_w, id_side, id_t}
    assert len(ids) == 4
    score_a = lib.canonical_score_record_id(id_a, 30)
    score_b = lib.canonical_score_record_id(id_a, 60)
    assert score_a != score_b
    assert score_a.startswith(id_a + "|")


def test_canonical_base_event_id_rejects_invalid_side():
    with pytest.raises(lib.B205Error):
        lib.canonical_base_event_id(W=15, side="UP", T_ms=0)


def test_canonical_score_record_id_rejects_horizon_outside_frozen_set():
    base = lib.canonical_base_event_id(W=15, side="BUY", T_ms=0)
    with pytest.raises(lib.B205Error):
        lib.canonical_score_record_id(base, 45)


# ---------------------------------------------------------------------------
# 5. percentile / state boundaries
# ---------------------------------------------------------------------------
def test_tertile_state_exact_boundaries():
    assert lib._tertile_state(0.0) == lib.STATE_LOW
    assert lib._tertile_state(1.0 / 3.0 - 1e-12) == lib.STATE_LOW
    assert lib._tertile_state(1.0 / 3.0) == lib.STATE_MID
    assert lib._tertile_state(2.0 / 3.0 - 1e-12) == lib.STATE_MID
    assert lib._tertile_state(2.0 / 3.0) == lib.STATE_HIGH
    assert lib._tertile_state(1.0) == lib.STATE_HIGH
    assert lib._tertile_state(float("nan")) is None


def test_midrank_ties_split_evenly():
    # three equal-valued references: midrank of a fourth equal value is
    # (count(<x) + 0.5*count(==x)) / N = (0 + 0.5*3)/3 = 0.5
    t_ms = np.array([0, 1, 2, 3], dtype=np.int64)
    side_code = np.array([1, 1, 1, 1], dtype=np.int8)
    values = np.array([5.0, 5.0, 5.0, 5.0], dtype=np.float64)
    pct = lib._causal_standing_by_side(t_ms, side_code, values, lookback_ms=100, min_ref_n=1)
    assert pct[3] == pytest.approx(0.5)


def test_midrank_p_equals_one_is_high_not_mid():
    t_ms = np.array([0, 1, 2, 3], dtype=np.int64)
    side_code = np.array([1, 1, 1, 1], dtype=np.int8)
    values = np.array([1.0, 2.0, 3.0, 100.0], dtype=np.float64)
    pct = lib._causal_standing_by_side(t_ms, side_code, values, lookback_ms=100, min_ref_n=1)
    assert pct[3] == pytest.approx(1.0)
    assert lib._tertile_state(float(pct[3])) == lib.STATE_HIGH


def test_impact_state_unavailable_below_minimum_reference_n():
    t_ms = np.arange(5, dtype=np.int64)
    side_code = np.ones(5, dtype=np.int8)
    values = np.arange(5, dtype=np.float64) + 1.0
    pct = lib._causal_standing_by_side(t_ms, side_code, values, lookback_ms=100, min_ref_n=3)
    # index 1 has exactly 1 reference (< 3) -> NaN; index 3 has 3 refs -> finite
    assert math.isnan(pct[1])
    assert math.isfinite(pct[3])


# ---------------------------------------------------------------------------
# 6. nuisance quintile boundaries
# ---------------------------------------------------------------------------
def test_quintile_label_exact_boundaries():
    assert lib._quintile_label(0.0) == "Q1"
    assert lib._quintile_label(0.2 - 1e-12) == "Q1"
    assert lib._quintile_label(0.2) == "Q2"
    assert lib._quintile_label(0.4) == "Q3"
    assert lib._quintile_label(0.6) == "Q4"
    assert lib._quintile_label(0.8) == "Q5"
    assert lib._quintile_label(1.0) == "Q5"
    assert lib._quintile_label(float("nan")) is None


# ---------------------------------------------------------------------------
# 7. OLS: exact frozen lstsq primitive
# ---------------------------------------------------------------------------
def test_ols_fit_rank_deficient_returns_none():
    # second column is a scalar multiple of the first -> rank-deficient
    x = np.column_stack((np.ones(6), np.arange(6.0), 2.0 * np.arange(6.0)))
    y = np.arange(6.0)
    assert lib.ols_fit(x, y) is None


def test_ols_fit_nonfinite_inputs_return_none():
    x = np.column_stack((np.ones(5), np.arange(5.0)))
    y = np.arange(5.0)
    x_bad = x.copy()
    x_bad[0, 1] = np.nan
    assert lib.ols_fit(x_bad, y) is None
    y_bad = y.copy()
    y_bad[0] = np.inf
    assert lib.ols_fit(x, y_bad) is None


def test_ols_fit_matches_lstsq_reference_on_well_posed_design():
    rng = np.random.default_rng(3)
    x = np.column_stack((np.ones(50), rng.normal(size=50), rng.normal(size=50)))
    true_beta = np.array([1.0, 2.0, -0.5])
    y = x @ true_beta + rng.normal(scale=0.01, size=50)
    beta = lib.ols_fit(x, y)
    expected = np.linalg.lstsq(x, y, rcond=None)[0]
    assert beta is not None
    assert np.allclose(beta, expected)


def test_lib_source_uses_lstsq_only_no_pinv_no_normal_equations():
    assert "numpy.linalg.lstsq" in LIB_SRC or "np.linalg.lstsq" in LIB_SRC
    forbidden_substrings = (
        "linalg.pinv",
        "linalg.cholesky",
        "linalg.solve(",
        "X.T @ X",
        "matrix.T @ matrix",
    )
    for token in forbidden_substrings:
        assert token not in LIB_SRC, f"forbidden solver primitive found: {token}"


def test_ols_fit_body_calls_lstsq_with_rcond_none():
    tree = ast.parse(LIB_SRC)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "ols_fit":
            src = ast.get_source_segment(LIB_SRC, node)
            assert "np.linalg.lstsq(matrix, y, rcond=None)" in src
            found = True
    assert found


# ---------------------------------------------------------------------------
# 8. placebo
# ---------------------------------------------------------------------------
def test_seed_int_matches_frozen_primitive_reproduction():
    parts = (20260907, 0, 15, 30, 12345, "2020-02|SIDE=BUY|IMB_Q=Q1|FLOW_Q=Q1")
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    expected = int.from_bytes(hashlib.sha256(raw).digest()[:8], "big", signed=False)
    assert lib.seed_int(parts) == expected


def test_seed_int_is_deterministic_and_order_sensitive():
    a = lib.seed_int((20260907, 0, 15, 30))
    b = lib.seed_int((20260907, 0, 15, 30))
    c = lib.seed_int((20260907, 1, 15, 30))
    assert a == b
    assert a != c


def test_permutation_stratum_id_format_and_ordering():
    sid = lib.permutation_stratum_id(
        T_e_ms=lib.DEV_START_MS, side="BUY", abs_imb_quintile="Q3", flow_ret_quintile="Q1"
    )
    assert sid.startswith("2020-02|SIDE=BUY|IMB_Q=Q3|FLOW_Q=Q1")


def test_permutation_stratum_id_rejects_bad_side_or_quintile():
    with pytest.raises(lib.B205Error):
        lib.permutation_stratum_id(
            T_e_ms=0, side="UP", abs_imb_quintile="Q1", flow_ret_quintile="Q1"
        )
    with pytest.raises(lib.B205Error):
        lib.permutation_stratum_id(
            T_e_ms=0, side="BUY", abs_imb_quintile="Q9", flow_ret_quintile="Q1"
        )


def test_one_record_stratum_still_calls_permutation_and_leaves_label_unchanged():
    label_vec = np.asarray([lib.STATE_LABEL_CODE[lib.STATE_HIGH]], dtype=np.int64)
    rng = np.random.default_rng(lib.seed_int((lib.SEED_PLACEBO, 0, 15, 30, 0, "stratum")))
    permuted = rng.permutation(label_vec)
    assert permuted.tolist() == label_vec.tolist()


def test_placebo_requires_all_replicates_finite_else_unavailable(monkeypatch):
    monkeypatch.setattr(lib, "N_PLACEBO", 4)
    scored = [
        {
            "score_record_id": "synthetic|0",
            "ae_improvement": 0.1,
            "base_ae": 0.2,
            "candidate_ae": 0.1,
            "T": lib.DEV_START_MS,
            "side": "BUY",
            "base_residual": 0.05,
            "impact_state": "HIGH",
        }
    ]
    all_finite = np.array([0.1, 0.2, 0.3, 0.4])
    summary_ok = lib._summarize_cell(W=15, H=30, scored=scored, placebo_sums=all_finite)
    assert summary_ok["placebo_replicate_count_finite"] == 4
    assert summary_ok["placebo_q95"] is not None

    one_missing = np.array([0.1, 0.2, 0.3, float("nan")])
    summary_bad = lib._summarize_cell(W=15, H=30, scored=scored, placebo_sums=one_missing)
    assert summary_bad["placebo_replicate_count_finite"] == 3
    assert summary_bad["placebo_q95"] is None
    assert summary_bad["per_cell_conditions"]["placebo_separation"] is False


def test_single_event_failure_poisons_whole_replicate_via_nan_propagation():
    # Simulates the accumulator contract directly: once a replicate's running
    # sum is poisoned by one nonfinite event contribution, later finite
    # contributions from other weeks/events must not "heal" it.
    sums = np.zeros(3)
    sums[0] += 1.0
    sums[0] = float("nan")  # one bad event this week
    sums[0] += 5.0  # a later week's otherwise-fine contribution
    assert math.isnan(sums[0])


# ---------------------------------------------------------------------------
# 9. bootstrap
# ---------------------------------------------------------------------------
def _synthetic_score_ids(times, sides=None):
    ids = []
    for k, t in enumerate(times):
        side = "BUY" if sides is None else sides[k]
        ids.append(f"snap|1m|15m|15|{side}|{int(t) - 15 * lib.BAR_MS}|{int(t)}|{int(t)}|30")
    return ids


def test_bootstrap_is_deterministic_for_fixed_inputs():
    times = np.array(
        [lib.DEV_START_MS + i * lib.DAY_MS for i in range(20)], dtype=np.int64
    )
    values = np.linspace(-1.0, 1.0, 20)
    ids = _synthetic_score_ids(times)
    a = lib._week_bootstrap_interval(values, times, ids, 15, 30)
    b = lib._week_bootstrap_interval(values, times, ids, 15, 30)
    assert a == b


def test_bootstrap_iso_year_boundary_uses_isocalendar_not_gregorian_year():
    # 2021-01-01 is a Friday; ISO week of 2020-12-28..2021-01-03 belongs to
    # ISO year 2020 week 53 for the days before Jan 1, and ISO week 1 of 2021
    # starts Monday 2021-01-04. Confirm iso_week_id crosses correctly.
    dec_28 = 1_609_113_600_000  # 2020-12-28T00:00:00Z (Monday)
    jan_1_2021 = 1_609_459_200_000  # 2021-01-01T00:00:00Z (Friday)
    jan_4 = 1_609_718_400_000  # 2021-01-04T00:00:00Z (Monday)
    assert lib.iso_week_id(dec_28) // 100 == 2020
    # Gregorian calendar year is 2021, but the ISO week-numbering year/week
    # is 2020-W53 -- this is exactly the divergence the frozen contract
    # requires (bootstrap_week_id must use isocalendar(), not the Gregorian
    # year).
    assert lib.utc_year(jan_1_2021) == 2021
    assert lib.iso_week_id(jan_1_2021) == 2020 * 100 + 53
    assert lib.iso_week_id(jan_4) // 100 == 2021


def test_bootstrap_within_week_sums_in_canonical_score_id_order_not_t_order():
    # A week with mixed BUY/SELL rows: canonical id order groups BUY rows
    # (lexicographically first) ahead of SELL rows, which differs from a
    # plain ascending-T order whenever sides interleave in time.
    base = lib.DEV_START_MS
    times = np.array([base, base + lib.HTF_MS, base + 2 * lib.HTF_MS], dtype=np.int64)
    # T-ascending sides: SELL, BUY, SELL -- canonical-id order groups BUY
    # first (single row), then the two SELL rows in ascending T.
    sides = ["SELL", "BUY", "SELL"]
    ids = _synthetic_score_ids(times, sides)
    order_by_id = sorted(range(len(ids)), key=lambda k: ids[k])
    ordered_sides = [sides[k] for k in order_by_id]
    assert ordered_sides == ["BUY", "SELL", "SELL"]
    assert ordered_sides != sides  # proves id-order differs from T-order
    values = np.array([1.0, 2.0, 3.0])
    low, high = lib._week_bootstrap_interval(values, times, ids, 15, 30)
    assert math.isfinite(low) and math.isfinite(high)


def test_week_bootstrap_interval_sorts_within_week_by_score_id_not_insertion_order():
    # Mutation-proof for Blocker 4: since scalar addition is (to observable
    # precision) order-invariant for typical inputs, the id-ordered
    # within-week traversal is enforced structurally rather than through a
    # numeric-difference assertion. Inspects _week_bootstrap_interval's own
    # source body to prove it sorts each week's (score_id, value) pairs by
    # score_id before summing, rather than relying on insertion/T order.
    tree = ast.parse(LIB_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_week_bootstrap_interval":
            src = ast.get_source_segment(LIB_SRC, node)
            assert "sorted(groups[key], key=lambda pair: pair[0])" in src
            assert "score_id" in src
            break
    else:
        raise AssertionError("_week_bootstrap_interval not found")


def test_bootstrap_single_block_uses_it_every_replicate():
    times = np.array([lib.DEV_START_MS] * 5, dtype=np.int64)
    values = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
    ids = _synthetic_score_ids(times)
    low, high = lib._week_bootstrap_interval(values, times, ids, 15, 30)
    assert low == pytest.approx(1.0)
    assert high == pytest.approx(1.0)


def test_bootstrap_zero_observations_is_unavailable():
    low, high = lib._week_bootstrap_interval(
        np.array([]), np.array([], dtype=np.int64), [], 15, 30
    )
    assert math.isnan(low)
    assert math.isnan(high)


def test_bootstrap_mismatched_parallel_sequence_lengths_fail_closed():
    # values/times/score_ids must be the exact same length; a caller bug
    # producing mismatched arrays must raise, not silently truncate to the
    # shortest sequence (which would drop real observations unnoticed).
    times = np.array([lib.DEV_START_MS, lib.DEV_START_MS + lib.HTF_MS], dtype=np.int64)
    values = np.array([1.0, 2.0, 3.0])  # one extra value, no matching time/id
    ids = _synthetic_score_ids(times)
    with pytest.raises(ValueError):
        lib._week_bootstrap_interval(values, times, ids, 15, 30)


def test_bootstrap_block_multiplicity_preserved_in_seed_derivation():
    seed_a = lib.seed_int((lib.SEED_BOOT, 15, 30))
    seed_b = lib.seed_int((lib.SEED_BOOT, 15, 60))
    assert seed_a != seed_b


# ---------------------------------------------------------------------------
# 10. promotion
# ---------------------------------------------------------------------------
def _cell(W, H, *, six_pass=False, year_pass=False):
    conditions = {name: bool(six_pass) for name in lib.PER_CELL_GATE_NAMES}
    return {
        "W": W,
        "H": H,
        "per_cell_conditions": conditions,
        "year_stability_pass": bool(year_pass),
    }


def test_single_good_cell_cannot_promote():
    cells = [_cell(15, 30, six_pass=True, year_pass=True)]
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert neighborhoods == []
    assert gates["horizon_robustness"] is False


def test_single_w_cannot_promote_even_with_full_adjacent_pair():
    cells = [
        _cell(15, 30, six_pass=True, year_pass=True),
        _cell(15, 60, six_pass=True, year_pass=True),
    ]
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["horizon_robustness"] is True
    assert gates["parameter_robustness"] is False
    assert neighborhoods == []


def test_crossed_h_pairs_across_w_cannot_promote():
    # W=15 passes (30,60); W=30 passes (60,120) -- no SHARED adjacent pair.
    cells = [
        _cell(15, 30, six_pass=True, year_pass=True),
        _cell(15, 60, six_pass=True, year_pass=True),
        _cell(30, 60, six_pass=True, year_pass=True),
        _cell(30, 120, six_pass=True, year_pass=True),
    ]
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["parameter_robustness"] is False
    assert neighborhoods == []


def test_same_pair_at_two_w_qualifies_a_neighborhood():
    cells = [
        _cell(15, 30, six_pass=True, year_pass=True),
        _cell(15, 60, six_pass=True, year_pass=True),
        _cell(30, 30, six_pass=True, year_pass=True),
        _cell(30, 60, six_pass=True, year_pass=True),
    ]
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert gates["horizon_robustness"] is True
    assert gates["parameter_robustness"] is True
    assert gates["year_stability"] is True
    assert len(neighborhoods) == 1
    assert neighborhoods[0]["H_pair"] == [30, 60]
    assert neighborhoods[0]["W"] == [15, 30]


def test_all_three_w_pass_selects_first_lexicographic_w_pair_exactly_four_cells():
    # All three W (15, 30, 60) six-gate-pass and are year-stable at the
    # (30,60) H-pair -- the neighborhood must still be exactly the FIRST
    # lexicographic W-pair (15,30), never all three W's / six cells.
    cells = [
        _cell(w, h, six_pass=True, year_pass=True)
        for w in lib.W_VALUES
        for h in (30, 60)
    ]
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert len(neighborhoods) == 1
    assert neighborhoods[0]["H_pair"] == [30, 60]
    assert neighborhoods[0]["W"] == [15, 30]
    assert len(neighborhoods[0]["cells"]) == 4
    assert {(c["W"], c["H"]) for c in neighborhoods[0]["cells"]} == {
        (15, 30), (15, 60), (30, 30), (30, 60),
    }


def test_multiple_qualifying_h_pairs_selects_only_the_first_frozen_h_pair():
    # Both (30,60) and (60,120) qualify at W=15,30; only the first frozen
    # H-pair order entry, (30,60), may be selected.
    cells = [
        _cell(w, h, six_pass=True, year_pass=True)
        for w in (15, 30)
        for h in (30, 60, 120)
    ]
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert len(neighborhoods) == 1
    assert neighborhoods[0]["H_pair"] == [30, 60]


def test_only_w_15_and_60_pass_neighborhood_uses_exactly_those_two_w():
    # W=30 never six-gate-passes at this H-pair; only W=15 and W=60 do, so
    # the qualifying neighborhood must use exactly {15, 60}, skipping 30.
    cells = [
        _cell(15, 30, six_pass=True, year_pass=True),
        _cell(15, 60, six_pass=True, year_pass=True),
        _cell(30, 30, six_pass=False, year_pass=False),
        _cell(30, 60, six_pass=False, year_pass=False),
        _cell(60, 30, six_pass=True, year_pass=True),
        _cell(60, 60, six_pass=True, year_pass=True),
    ]
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert len(neighborhoods) == 1
    assert neighborhoods[0]["H_pair"] == [30, 60]
    assert neighborhoods[0]["W"] == [15, 60]
    assert {(c["W"], c["H"]) for c in neighborhoods[0]["cells"]} == {
        (15, 30), (15, 60), (60, 30), (60, 60),
    }


def test_promotion_neighborhood_mutation_all_three_w_would_be_caught():
    # Mutation-proof: reintroducing the old bug (dumping every qualifying W
    # into one neighborhood) would report 3 W's / 6 cells here instead of 2/4.
    cells = [
        _cell(w, h, six_pass=True, year_pass=True)
        for w in lib.W_VALUES
        for h in (30, 60)
    ]
    _gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert len(neighborhoods[0]["W"]) == 2
    assert len(neighborhoods[0]["cells"]) == 4


def _scored_record(*, year, ae_improvement):
    year_ms = lib._days_from_civil(year, 6, 15) * lib.DAY_MS  # mid-year, arbitrary day
    return {
        "score_record_id": f"synthetic|{year}",
        "ae_improvement": ae_improvement,
        "base_ae": abs(ae_improvement) + 1.0,
        "candidate_ae": 1.0,
        "T": year_ms,
        "side": "BUY",
        "base_residual": 0.0,
        "impact_state": "MID",
    }


def test_year_stability_three_of_five_fails_four_of_five_passes():
    # Drives the real cell-summarization pipeline (lib._summarize_cell)
    # rather than reimplementing the positive-years arithmetic in the test.
    scored_3_of_5 = [
        _scored_record(year=2020, ae_improvement=0.1),
        _scored_record(year=2021, ae_improvement=0.1),
        _scored_record(year=2022, ae_improvement=0.1),
        _scored_record(year=2023, ae_improvement=-0.1),
        _scored_record(year=2024, ae_improvement=-0.1),
    ]
    cell_3_of_5 = lib._summarize_cell(
        W=15, H=30, scored=scored_3_of_5, placebo_sums=np.full(lib.N_PLACEBO, np.nan)
    )
    assert cell_3_of_5["positive_years"] == 3
    assert cell_3_of_5["year_stability_pass"] is False

    scored_4_of_5 = [
        _scored_record(year=2020, ae_improvement=0.1),
        _scored_record(year=2021, ae_improvement=0.1),
        _scored_record(year=2022, ae_improvement=0.1),
        _scored_record(year=2023, ae_improvement=0.1),
        _scored_record(year=2024, ae_improvement=-0.1),
    ]
    cell_4_of_5 = lib._summarize_cell(
        W=15, H=30, scored=scored_4_of_5, placebo_sums=np.full(lib.N_PLACEBO, np.nan)
    )
    assert cell_4_of_5["positive_years"] == 4
    assert cell_4_of_5["year_stability_pass"] is True


def test_missing_mandatory_gate_fails_promotion_even_with_a_neighborhood():
    cells = [
        _cell(15, 30, six_pass=True, year_pass=True),
        _cell(15, 60, six_pass=True, year_pass=True),
        _cell(30, 30, six_pass=True, year_pass=True),
        _cell(30, 60, six_pass=True, year_pass=True),
    ]
    gates, neighborhoods = lib.determine_promotion_gates(cells)
    assert neighborhoods  # a qualifying neighborhood exists
    passed, verdict = lib.promotion_verdict(gates, neighborhoods)
    assert passed is True
    assert verdict == lib.VERDICT_PROMOTED

    gates["side_stability"] = False  # simulate a missing top-level gate
    passed, verdict = lib.promotion_verdict(gates, neighborhoods)
    assert passed is False
    assert verdict == lib.VERDICT_CLOSED


def test_per_cell_conditions_zero_is_not_positive():
    conditions = lib.per_cell_conditions(
        mean_improvement=0.0,
        relative=0.0,
        bootstrap_lower=0.0,
        placebo_q95=0.0,
        residual_low=-1.0,
        residual_mid=0.0,
        residual_high=1.0,
        buy_mean_improvement=0.0,
        buy_ordering_gap=0.0,
        sell_mean_improvement=0.0,
        sell_ordering_gap=0.0,
    )
    assert conditions["primary_positive"] is False
    assert conditions["bootstrap_positive"] is False
    assert conditions["side_stability"] is False


def test_per_cell_conditions_nan_fails_every_gate():
    nan = float("nan")
    conditions = lib.per_cell_conditions(
        mean_improvement=nan,
        relative=nan,
        bootstrap_lower=nan,
        placebo_q95=nan,
        residual_low=nan,
        residual_mid=nan,
        residual_high=nan,
        buy_mean_improvement=nan,
        buy_ordering_gap=nan,
        sell_mean_improvement=nan,
        sell_ordering_gap=nan,
    )
    assert all(v is False for v in conditions.values())


def test_impact_ordering_requires_strict_chain():
    conditions = lib.per_cell_conditions(
        mean_improvement=1.0,
        relative=0.1,
        bootstrap_lower=0.1,
        placebo_q95=0.0,
        residual_low=0.0,
        residual_mid=0.0,  # tie -- not a strict chain
        residual_high=1.0,
        buy_mean_improvement=1.0,
        buy_ordering_gap=1.0,
        sell_mean_improvement=1.0,
        sell_ordering_gap=1.0,
    )
    assert conditions["impact_ordering"] is False


def test_side_stability_requires_both_sides_independently():
    conditions = lib.per_cell_conditions(
        mean_improvement=1.0,
        relative=0.1,
        bootstrap_lower=0.1,
        placebo_q95=0.0,
        residual_low=-1.0,
        residual_mid=0.0,
        residual_high=1.0,
        buy_mean_improvement=1.0,
        buy_ordering_gap=1.0,
        sell_mean_improvement=-0.1,  # SELL fails
        sell_ordering_gap=1.0,
    )
    assert conditions["side_stability"] is False


# ---------------------------------------------------------------------------
# 11. anti-rescue -- no alternate descriptor/sign/horizon/window path
# ---------------------------------------------------------------------------
def test_no_alternate_structural_descriptor_in_source():
    forbidden = (
        "IMB / ",
        "price_move /",
        "epsilon",
        "cvd",
        "CVD",
        "order_book",
        "orderbook",
    )
    for token in forbidden:
        assert token not in LIB_SRC, f"forbidden alternate descriptor path found: {token}"


def test_search_surface_constants_are_exactly_frozen():
    assert lib.W_VALUES == (15, 30, 60)
    assert lib.H_VALUES == (30, 60, 120, 240)
    assert lib.PRIMARY_CELLS == 12
    assert lib.ADJACENT_H_PAIRS == ((30, 60), (60, 120), (120, 240))


def test_structural_descriptor_formula_is_exactly_abs_imb_times_flow_ret():
    tree = ast.parse(LIB_SRC)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "build_flow_frame":
            src = ast.get_source_segment(LIB_SRC, node)
            assert "abs_imb * flow_ret" in src
            found = True
    assert found


# ---------------------------------------------------------------------------
# 12. performance-optimization equivalence oracles
# ---------------------------------------------------------------------------
def test_rolling_sum_flow_construction_matches_brute_force_oracle():
    frame = _flat_frame(2, base_volume=1.0, taker_ratio=0.5, seed=7)
    rng = np.random.default_rng(7)
    n = len(frame["open_time_ms"])
    frame["base_volume"] = np.abs(rng.normal(10.0, 3.0, n))
    frame["taker_buy_base_volume"] = np.clip(
        frame["base_volume"] * rng.uniform(0.1, 0.9, n), 0.0, frame["base_volume"]
    )
    frame15 = lib.aggregate_1m_to_15m(frame)
    close15, t_ms15 = frame15["close"], frame15["t_ms"]
    flow = lib.build_flow_frame(frame, 30, close15, t_ms15)

    close = frame["close"]
    base_volume = frame["base_volume"]
    taker_buy = frame["taker_buy_base_volume"]
    w_minutes = 30
    for m in (0, 5, 40, len(t_ms15) - 1):
        i_end = m * lib.HTF_MIN + (lib.HTF_MIN - 1)
        start = i_end - w_minutes + 1
        prior = i_end - w_minutes
        if start < 0 or prior < 0:
            assert math.isnan(flow["total_w"][m])
            continue
        oracle_total = float(np.sum(base_volume[start: i_end + 1]))
        oracle_taker = float(np.sum(taker_buy[start: i_end + 1]))
        # Exactly W one-minute returns cover [T-W,T): from close(T-W) (at
        # bar index `prior`) through close(T) (at bar index `i_end`).
        rets = np.log(close[start: i_end + 1] / close[prior: i_end])
        oracle_rv = float(np.sqrt(np.sum(rets ** 2)))
        assert len(rets) == w_minutes
        oracle_flow_ret_raw = float(np.log(close[i_end] / close[prior]))
        assert flow["total_w"][m] == pytest.approx(oracle_total)
        assert flow["taker_buy_w"][m] == pytest.approx(oracle_taker)
        assert flow["rv_w"][m] == pytest.approx(oracle_rv)
        d = float(flow["side_code"][m])
        if d != 0.0:
            assert flow["flow_ret"][m] == pytest.approx(d * oracle_flow_ret_raw)


def test_past_median_abs_return_matches_brute_force_oracle(monkeypatch):
    monkeypatch.setattr(lib, "SCALE_REF_STEPS", 6)
    rng = np.random.default_rng(11)
    n = 30
    close15 = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.001, n)))
    t_ms15 = np.arange(n, dtype=np.int64) * lib.HTF_MS
    h = lib.HTF_MIN * 2
    raw = lib.horizon_returns(close15, t_ms15, h)
    abs_ret = np.abs(raw)
    fast = lib.past_median_abs_return(abs_ret, h)

    h_steps = h // lib.HTF_MIN
    span = lib.SCALE_REF_STEPS - h_steps + 1
    oracle = np.full(n, np.nan)
    for i in range(n):
        j = i - h_steps
        if j < span - 1:
            continue
        window = abs_ret[j - span + 1: j + 1]
        if not np.all(np.isfinite(window)):
            continue
        med = float(np.median(window))
        oracle[i] = med if med > 0.0 else np.nan

    for i in range(n):
        if math.isnan(oracle[i]):
            assert math.isnan(fast[i])
        else:
            assert fast[i] == pytest.approx(oracle[i])


def test_placebo_precompute_optimization_matches_naive_per_replicate_recompute():
    """Independent oracle (not a call-the-same-function-twice check): proves
    recomputing each scored event's standardized candidate features fresh
    inside the N_PLACEBO loop (the naive approach) is numerically identical
    to using the values precomputed once outside the loop (the actual
    implementation's optimization -- `cur_z`/`cur_side_buy`/`cur_low`/
    `cur_high` in evaluate_cell), on synthetic beta/feature data built
    directly here."""
    rng = np.random.default_rng(21)
    n_events = 6
    abs_imb = rng.normal(0.1, 0.02, n_events)
    flow_ret = rng.normal(0.0, 0.001, n_events)
    rv_w = rng.normal(0.002, 0.0005, n_events)
    log_activity = rng.normal(5.0, 0.2, n_events)
    side_buy = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0])
    states = ["LOW", "MID", "HIGH", "LOW", "MID", "HIGH"]
    cand_mean = np.array([0.1, 0.0, 0.002, 5.0])
    cand_std = np.array([0.02, 0.001, 0.0005, 0.2])

    def naive_predictions(beta):
        # recomputes zci/low_i/high_i fresh for every event, as the code
        # would if it did NOT hoist this out of the replicate loop
        preds = []
        for i in range(n_events):
            zci = (
                np.asarray([abs_imb[i], flow_ret[i], rv_w[i], log_activity[i]]) - cand_mean
            ) / cand_std
            low_i = 1.0 if states[i] == "LOW" else 0.0
            high_i = 1.0 if states[i] == "HIGH" else 0.0
            pred = float(
                beta[0]
                + np.dot(beta[1:5], zci)
                + beta[5] * side_buy[i]
                + beta[6] * low_i
                + beta[7] * high_i
            )
            preds.append(pred)
        return np.asarray(preds)

    def precomputed_predictions(beta):
        # the actual implementation's optimization: standardized features
        # and state dummies computed once, reused across every replicate
        cur_cols = np.column_stack((abs_imb, flow_ret, rv_w, log_activity))
        cur_z = (cur_cols - cand_mean) / cand_std
        cur_low = np.asarray([1.0 if s == "LOW" else 0.0 for s in states])
        cur_high = np.asarray([1.0 if s == "HIGH" else 0.0 for s in states])
        return (
            beta[0]
            + cur_z @ beta[1:5]
            + beta[5] * side_buy
            + beta[6] * cur_low
            + beta[7] * cur_high
        )

    for _replicate in range(20):
        beta = rng.normal(size=8)  # a different "weekly placebo fit" each time
        naive = naive_predictions(beta)
        precomputed = precomputed_predictions(beta)
        assert np.allclose(naive, precomputed)


def test_causal_reference_count_matches_two_pointer_and_brute_force():
    rng = np.random.default_rng(2)
    times = np.sort(rng.choice(np.arange(0, 100_000, 100), size=200, replace=False)).astype(np.int64)
    lookback = 5_000
    fast = lib.causal_reference_count(times, lookback)
    brute = np.zeros(len(times), dtype=np.int64)
    for i in range(len(times)):
        cutoff = times[i] - lookback
        brute[i] = int(np.sum((times[:i] >= cutoff)))
    assert np.array_equal(fast, brute)


def test_causal_reference_count_requires_strictly_increasing_times():
    with pytest.raises(lib.B205Error):
        lib.causal_reference_count(np.array([0, 0, 1], dtype=np.int64), 10)


# ---------------------------------------------------------------------------
# 13. full-pipeline smoke (tiny synthetic domain, shrunk thresholds)
# ---------------------------------------------------------------------------
def test_evaluate_b2_05_produces_all_twelve_cells(monkeypatch):
    _shrink_thresholds(monkeypatch)
    monkeypatch.setattr(lib, "DEV_START_MS", lib.WARMUP_START_MS + 3 * lib.DAY_MS)
    monkeypatch.setattr(lib, "DEV_END_MS", lib.WARMUP_START_MS + 30 * lib.DAY_MS)
    monkeypatch.setattr(lib, "VALIDATION_2025_START_MS", lib.DEV_END_MS)
    frame = _flat_frame(30, taker_ratio=0.6, seed=9)
    result = lib.evaluate_b2_05(frame)
    assert len(result["cells"]) == 12
    seen = {(c["W"], c["H"]) for c in result["cells"]}
    assert seen == {(w, h) for w in lib.W_VALUES for h in lib.H_VALUES}
    assert result["promotion"]["verdict"] in (lib.VERDICT_PROMOTED, lib.VERDICT_CLOSED)
    for cell in result["cells"]:
        assert "scored" not in cell  # stripped before returning from evaluate_b2_05


def test_evaluate_cell_result_has_no_arbitrary_omission_of_failed_cells(monkeypatch):
    _shrink_thresholds(monkeypatch, MIN_BASELINE_N=10_000_000)  # force every week unavailable
    frame = _flat_frame(20, taker_ratio=0.6, seed=4)
    frame15 = lib.aggregate_1m_to_15m(frame)
    flow = lib.build_flow_frame(frame, 15, frame15["close"], frame15["t_ms"])
    flow = lib.attach_impact_state(flow)
    flow = lib.attach_nuisance_bins(flow)
    cell = lib.evaluate_cell(flow, 30)
    # a fully-failed cell is still represented with N=0, not omitted
    assert cell["N"] == 0
    assert cell["W"] == 15 and cell["H"] == 30
    assert set(lib.PER_CELL_GATE_NAMES) <= set(cell["per_cell_conditions"])


# ---------------------------------------------------------------------------
# forbidden-window evidence
# ---------------------------------------------------------------------------
def test_derive_forbidden_window_evidence_rejects_2025_reaching_window():
    frame = {
        "open_time_ms": np.array([lib.DEV_START_MS], dtype=np.int64),
        "available_at_ms": np.array([lib.DEV_START_MS + lib.BAR_MS], dtype=np.int64),
    }
    identity = {
        "window": {
            "start_inclusive_ms": lib.DEV_START_MS,
            "end_exclusive_ms": lib.DEV_END_MS + 1,
            "allowed_years": [2024],
        },
        "partitions": [{"relative_path": "2024-12.parquet"}],
    }
    with pytest.raises(lib.B205Error):
        lib.derive_forbidden_window_evidence(identity, frame)


def test_derive_forbidden_window_evidence_accepts_clean_dev_window():
    frame = {
        "open_time_ms": np.array([lib.DEV_START_MS], dtype=np.int64),
        "available_at_ms": np.array([lib.DEV_START_MS + lib.BAR_MS], dtype=np.int64),
    }
    identity = {
        "window": {
            "start_inclusive_ms": lib.DEV_START_MS,
            "end_exclusive_ms": lib.DEV_END_MS,
            "allowed_years": [2020, 2021, 2022, 2023, 2024],
        },
        "partitions": [{"relative_path": "2024-12.parquet"}],
    }
    evidence = lib.derive_forbidden_window_evidence(identity, frame)
    assert evidence["2025_validation"] is False
    assert evidence["2026_oos"] is False


def test_runner_repo_root_is_an_absolute_repository_path():
    # runner.REPO_ROOT is `Path(__file__).parents[2]`, NOT
    # `Path(__file__).resolve().parents[2]`: `.resolve()` (and `.absolute()`)
    # are unconditionally forbidden filesystem-touching pathlib attribute
    # names under this repo's Batch02 source policy for hypothesis
    # runner/lib code (validate_batch02_source_tree flags any `.resolve(`
    # attribute access as "forbidden direct I/O or mutation call", verified
    # directly against this exact file -- adding `.resolve()` here breaks
    # that validator). `__file__` for a normally-imported module is already
    # an absolute path without needing resolution, so this proves the
    # weaker-but-true property the source policy actually allows: REPO_ROOT
    # is absolute and points at the real repository root.
    assert runner.REPO_ROOT.is_absolute()
    assert (runner.REPO_ROOT / "scripts" / "research" / "b2_05_flow_absorption.py").is_file()
    assert "resolve" not in RUNNER_SRC


# ---------------------------------------------------------------------------
# runner: identity() only touches code freeze, never data
# ---------------------------------------------------------------------------
def test_runner_identity_does_not_reserve_claim_or_load(monkeypatch):
    calls = []

    class _FakeFreeze:
        code_sha = "deadbeef"

    def _fake_verify(*, repo_root, expected_code_sha):
        calls.append(("verify_batch02_code", repo_root, expected_code_sha))
        return _FakeFreeze()

    monkeypatch.setattr(runner, "verify_batch02_code", _fake_verify)
    result = runner.identity("deadbeef")
    assert calls == [("verify_batch02_code", runner.REPO_ROOT, "deadbeef")]
    assert result["outcome_accessed"] is False
    assert result["validation_2025_accessed"] is False
    assert result["oos_2026_accessed"] is False
    assert result["hypothesis_id"] == lib.HYPOTHESIS_ID


def test_run_development_rejects_non_true_acknowledgement(monkeypatch):
    called = {"reservation": False}

    def _boom(*args, **kwargs):
        called["reservation"] = True
        raise AssertionError("must not be reached before the literal-True check")

    monkeypatch.setattr(runner, "prepare_batch02_evidence_reservation", _boom)
    for bad in (False, 1, "true", None, [], {}):
        with pytest.raises(ValueError):
            runner.run_development("deadbeef", outcome_access_acknowledged=bad)
    assert called["reservation"] is False


# ---------------------------------------------------------------------------
# static source audit
# ---------------------------------------------------------------------------
FORBIDDEN_STATIC_TOKENS = (
    "pinv",
    "cholesky",
    "bfill",
    "backfill",
    "interpolate",
    "center=True",
)
# Quoted 2025/2026 date-string literals used as actual code tokens (e.g. a
# runtime comparison against "2025-01-01") are forbidden; a documentation
# comment naming the epoch-ms constant's calendar date (e.g. "# 2025-01-01
# T00:00:00Z") is fine and expected -- literal chronology constants in
# comments/docs are explicitly permitted, only runtime string-literal access
# to a reserved year is checked here.
FORBIDDEN_QUOTED_YEAR_PATTERNS = (
    '"2025-', "'2025-",
    '"2026-', "'2026-",
)


def test_static_audit_forbidden_primitives_absent_from_runtime_source():
    for token in FORBIDDEN_STATIC_TOKENS:
        assert token not in LIB_SRC, f"forbidden token in lib: {token}"
        assert token not in RUNNER_SRC, f"forbidden token in runner: {token}"
    for token in FORBIDDEN_QUOTED_YEAR_PATTERNS:
        assert token not in LIB_SRC, f"forbidden quoted-year literal in lib: {token}"
        assert token not in RUNNER_SRC, f"forbidden quoted-year literal in runner: {token}"


def test_source_tree_validator_accepts_the_b2_05_module_pair():
    visited = validate_batch02_source_tree(RESEARCH_DIR, repo_root=REPO_ROOT)
    names = {p.name for p in visited}
    assert "b2_05_flow_absorption.py" in names
    assert "b2_05_flow_absorption_lib.py" in names


def test_runner_references_the_retention_ceremony_calls():
    for name in (
        "verify_batch02_code",
        "prepare_batch02_evidence_reservation",
        "prepare_batch02_retained_run",
        "persist_batch02_retained_result",
        "archive_batch02_result",
        "load_authorized_parquet_table",
    ):
        assert name in RUNNER_SRC


def test_runner_requires_all_five_frozen_source_columns():
    for column in lib.REQUIRED_SOURCE_COLUMNS:
        assert column in RUNNER_SRC or column in LIB_SRC
    assert lib.REQUIRED_SOURCE_COLUMNS == (
        "open_time_ms",
        "available_at_ms",
        "close",
        "base_volume",
        "taker_buy_base_volume",
    )
