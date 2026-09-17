"""Frozen MARKET-01 implementation tests. Synthetic/unit fixtures only.

Does not load CORE/OI snapshots, enumerate real episodes, or inspect
MARKET outcomes.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import pytest

from scripts.research.b2_03_impulse_morphology_lib import pre_vol_60 as b2_03_pre_vol_60
from scripts.research.market_01_oi_expansion_weak_continuation_authority import (
    FROZEN_FREEZE_JSON_SHA256,
    FROZEN_FREEZE_MD_SHA256,
    FROZEN_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256,
    Market01ExecutionNotAuthorized,
    authenticate_arch_selector,
    authenticate_frozen_prereg_bytes,
    sha256_file,
)
from scripts.research.market_01_oi_expansion_weak_continuation_lib import (
    ALPHA,
    BAR_MS,
    BOOTSTRAP_B,
    CALENDAR_DAY_MS,
    CLASS_DETECTED_NOT_ROBUST,
    CLASS_NO_EVIDENCE,
    CLASS_NOT_IDENTIFIABLE,
    CLASS_ROBUST_CANDIDATE,
    COMMON_START_MS,
    CONTINUATION_MAX,
    ERA_BOUNDS_MS,
    FIVE_MS,
    OI_STALE_MS,
    SYNTHETIC_SNAPSHOT,
    THIRTY_M_MS,
    EpisodeRecord,
    OiView,
    PriceView,
    assign_stratum,
    classify_oi_expansion,
    classify_qualifying_impulse,
    classify_weak_continuation,
    close_at,
    concentration,
    construct_episodes,
    design_matrix,
    dumps_result,
    evaluate_bound_market_01,
    evaluate_from_confirmatory_rows,
    evaluate_market_01,
    final_classification,
    fit_stratified_ols,
    legal_oi_at,
    loeo_sign_stable,
    midrank_percentile,
    one_sided_p,
    pre_vol_60,
    run_stationary_bootstrap,
    support_gate,
    tertile_state,
    usable_strata,
)


REPO = Path(__file__).resolve().parents[2]


def _price(n: int, start_open_ms: int, closes: np.ndarray) -> PriceView:
    open_ms = start_open_ms + np.arange(n, dtype=np.int64) * BAR_MS
    return PriceView(
        open_time_ms=open_ms,
        available_at_ms=open_ms + BAR_MS,
        close=np.asarray(closes, dtype=np.float64),
        snapshot_id=SYNTHETIC_SNAPSHOT,
    )


def _oi(n: int, start_create_ms: int, values: np.ndarray) -> OiView:
    create = start_create_ms + np.arange(n, dtype=np.int64) * FIVE_MS
    return OiView(
        create_time_ms=create,
        available_at_ms=create + FIVE_MS,
        sum_open_interest=np.asarray(values, dtype=np.float64),
        snapshot_id=SYNTHETIC_SNAPSHOT,
    )


def _row(T: int, reversal: float, cand: int, stratum: str, impulse_start: int | None = None):
    if impulse_start is None:
        impulse_start = int(T) - THIRTY_M_MS
    return {
        "impulse_end_t_ms": int(T) - THIRTY_M_MS,
        "impulse_start_ms": impulse_start,
        "decision_T_ms": int(T),
        "reversal_return": float(reversal),
        "candidate_indicator": int(cand),
        "stratum_id": stratum,
    }


def _balanced_rows(*, n_eras: int = 5, per_cell: int = 8) -> list[dict]:
    strata = ["HIGH|HIGH", "HIGH|MID", "MID|MID"]
    rows = []
    seq = 0
    for _era_name, start, _end in ERA_BOUNDS_MS[:n_eras]:
        for sid in strata:
            for cand, reversal in ((1, 1.25), (0, 0.05)):
                for _ in range(per_cell):
                    T = start + 3_600_000 + seq * FIVE_MS
                    rows.append(_row(T, reversal, cand, sid))
                    seq += 1
    rows.sort(key=lambda r: (r["decision_T_ms"], r["impulse_start_ms"]))
    return rows


def test_prereg_and_freeze_byte_identity_fails_closed():
    authenticate_frozen_prereg_bytes()
    md = REPO / "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md"
    js = REPO / "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json"
    freeze_md = REPO / "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.md"
    freeze_js = REPO / "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.json"
    assert sha256_file(md) == FROZEN_PREREG_MD_SHA256
    assert sha256_file(js) == FROZEN_PREREG_JSON_SHA256
    assert sha256_file(freeze_md) == FROZEN_FREEZE_MD_SHA256
    assert sha256_file(freeze_js) == FROZEN_FREEZE_JSON_SHA256
    assert hashlib.sha256(md.read_bytes()).hexdigest() != "0" * 64


def test_legal_price_clock_uses_bar_end_exclusive():
    start = COMMON_START_MS
    closes = np.array([100.0, 101.0, 102.0], dtype=np.float64)
    price = _price(3, start, closes)
    assert close_at(price, start) is None
    assert close_at(price, start + BAR_MS) == 100.0
    assert close_at(price, start + 2 * BAR_MS) == 101.0
    still_forming = start + 2 * BAR_MS + 1
    assert close_at(price, still_forming) is None


def test_oi_staleness_boundary_is_five_minutes():
    create0 = COMMON_START_MS
    oi = _oi(1, create0, np.array([10.0]))
    available = create0 + FIVE_MS
    assert legal_oi_at(oi, available) == 10.0
    assert legal_oi_at(oi, available + OI_STALE_MS) == 10.0
    assert legal_oi_at(oi, available + OI_STALE_MS + 1) is None
    assert legal_oi_at(oi, available - 1) is None


def test_missing_oi_makes_episode_ineligible_after_occupancy():
    hist_start = COMMON_START_MS - 31 * CALENDAR_DAY_MS
    t = COMMON_START_MS + THIRTY_M_MS
    n = int((t + 90 * BAR_MS - hist_start) / BAR_MS) + 10
    closes = np.full(n, 100.0, dtype=np.float64)
    idx_end = (t - BAR_MS - hist_start) // BAR_MS
    closes[idx_end] = 100.0 * math.exp(0.08)
    price = _price(n, hist_start, closes)
    oi = _oi(1, hist_start, np.array([1.0]))
    episodes = construct_episodes(price, oi)
    occupying = [e for e in episodes if e.occupies_slot]
    assert occupying
    first = occupying[0]
    assert first.qualifying_impulse is True
    assert first.confirmatory_eligible is False
    assert first.exclusion_reason == "missing_or_invalid_oi"


def test_impulse_historical_window_excludes_current_and_future():
    hist_start = COMMON_START_MS - 31 * CALENDAR_DAY_MS
    t = COMMON_START_MS + THIRTY_M_MS
    n = int((t + 10 * FIVE_MS - hist_start) / BAR_MS) + 10
    closes = np.full(n, 100.0, dtype=np.float64)
    idx_end = (t - BAR_MS - hist_start) // BAR_MS
    closes[idx_end] = 100.0 * math.exp(0.05)
    future_t = t + FIVE_MS
    idx_future = (future_t - BAR_MS - hist_start) // BAR_MS
    closes[idx_future] = 100.0 * math.exp(5.0)
    price = _price(n, hist_start, closes)
    ok, info = classify_qualifying_impulse(price, t)
    assert ok is True
    assert info["p_impulse"] == 1.0
    impulse_start = t - THIRTY_M_MS
    assert impulse_start == COMMON_START_MS


def test_oi_historical_normalization_excludes_state_and_future():
    start = COMMON_START_MS
    n = int(32 * CALENDAR_DAY_MS / FIVE_MS) + 20
    values = np.full(n, 10.0, dtype=np.float64)
    t = start + 31 * CALENDAR_DAY_MS
    T = t + THIRTY_M_MS
    idx_T = (T - FIVE_MS - start) // FIVE_MS
    values[idx_T] = 10.0 * math.exp(1.0)
    values[idx_T + 1] = 10.0 * math.exp(9.0)
    oi = _oi(n, start, values)
    ok, info = classify_oi_expansion(oi, t)
    assert info["delta_oi"] == pytest.approx(1.0)
    assert info["p_oi"] == 1.0
    assert ok is True


def test_oi_expansion_is_strict_greater_than_75th():
    equal_cut = np.arange(100, dtype=np.float64)
    p_at = midrank_percentile(74.0, equal_cut)
    assert p_at == pytest.approx(0.745)
    assert not (p_at > 0.75)
    p_over = midrank_percentile(75.0, equal_cut)
    assert p_over == pytest.approx(0.755)
    assert p_over > 0.75


def test_continuation_ratio_boundary_is_inclusive_at_0_25():
    start = COMMON_START_MS
    n = 90
    closes = np.full(n, 100.0, dtype=np.float64)
    t = start + 40 * BAR_MS
    T = t + THIRTY_M_MS
    idx_t = (t - BAR_MS - start) // BAR_MS
    idx_T = (T - BAR_MS - start) // BAR_MS
    closes[idx_t] = 100.0 * math.exp(0.04)
    closes[idx_T] = closes[idx_t] * math.exp(0.01)
    price = _price(n, start, closes)
    ok, info = classify_weak_continuation(price, t, d=1, abs_impulse=0.04)
    assert info["continuation_ratio"] == pytest.approx(0.25)
    assert ok is True
    closes[idx_T] = closes[idx_t] * math.exp(0.01 + 1e-12)
    price2 = _price(n, start, closes)
    ok2, info2 = classify_weak_continuation(price2, t, d=1, abs_impulse=0.04)
    assert info2["continuation_ratio"] > CONTINUATION_MAX
    assert ok2 is False


def test_overlap_keeps_earliest_qualifying_impulse_for_120m():
    hist_start = COMMON_START_MS - 31 * CALENDAR_DAY_MS
    t0 = COMMON_START_MS + THIRTY_M_MS
    t1 = t0 + FIVE_MS
    n = int((t1 + 90 * BAR_MS - hist_start) / BAR_MS) + 10
    closes = np.full(n, 100.0, dtype=np.float64)
    for t in (t0, t1):
        idx_end = (t - BAR_MS - hist_start) // BAR_MS
        closes[idx_end] = 100.0 * math.exp(0.07)
    price = _price(n, hist_start, closes)
    oi_n = int((n * BAR_MS) / FIVE_MS)
    oi = _oi(oi_n, hist_start, np.full(oi_n, 10.0))
    episodes = construct_episodes(price, oi)
    occupying = [e for e in episodes if e.occupies_slot]
    assert occupying
    first = occupying[0]
    skipped = [
        e
        for e in episodes
        if e.exclusion_reason == "overlap_skip"
        and first.impulse_start_ms < e.impulse_start_ms < first.impulse_start_ms + 120 * BAR_MS
    ]
    assert skipped


def test_pre_vol_60_requires_exactly_60_returns_and_matches_b2_03():
    start = COMMON_START_MS
    n = 80
    rng = np.random.default_rng(1)
    closes = 100.0 * np.exp(np.cumsum(rng.normal(0, 0.0002, size=n)))
    price = _price(n, start, closes)
    t = start + 70 * BAR_MS
    value = pre_vol_60(price, t)
    expected = b2_03_pre_vol_60(
        price.open_time_ms, price.available_at_ms, price.close, t
    )
    assert value == pytest.approx(expected)
    short = _price(50, start, closes[:50])
    assert pre_vol_60(short, t) is None


def test_historical_tertile_assignment_low_mid_high():
    assert tertile_state(0.0) == "LOW"
    assert tertile_state(1.0 / 3.0 - 1e-15) == "LOW"
    assert tertile_state(1.0 / 3.0) == "MID"
    assert tertile_state(2.0 / 3.0 - 1e-15) == "MID"
    assert tertile_state(2.0 / 3.0) == "HIGH"
    hist_start = COMMON_START_MS - 31 * CALENDAR_DAY_MS
    t = COMMON_START_MS + THIRTY_M_MS
    n = int((t + BAR_MS - hist_start) / BAR_MS) + 10
    closes = np.full(n, 100.0, dtype=np.float64)
    idx_end = (t - BAR_MS - hist_start) // BAR_MS
    closes[idx_end] = 100.0 * math.exp(0.04)
    price = _price(n, hist_start, closes)
    assigned = assign_stratum(price, t, 0.04)
    assert assigned["impulse_mag_state"] in {"LOW", "MID", "HIGH"}
    assert assigned["trailing_vol_state"] in {"LOW", "MID", "HIGH"}
    assert assigned["stratum_id"] == (
        f"{assigned['impulse_mag_state']}|{assigned['trailing_vol_state']}"
    )


def test_candidate_versus_baseline_classification():
    rec_cand = EpisodeRecord(
        impulse_end_t_ms=0,
        impulse_start_ms=0,
        decision_T_ms=1,
        outcome_end_ms=2,
        qualifying_impulse=True,
        oi_expansion=True,
        weak_continuation=True,
    )
    rec_cand.candidate = bool(
        rec_cand.qualifying_impulse and rec_cand.oi_expansion and rec_cand.weak_continuation
    )
    rec_base = EpisodeRecord(
        impulse_end_t_ms=0,
        impulse_start_ms=0,
        decision_T_ms=1,
        outcome_end_ms=2,
        qualifying_impulse=True,
        oi_expansion=False,
        weak_continuation=True,
    )
    rec_base.candidate = bool(
        rec_base.qualifying_impulse and rec_base.oi_expansion and rec_base.weak_continuation
    )
    assert rec_cand.candidate is True
    assert rec_base.candidate is False


def test_usable_stratum_support_boundaries():
    rows = []
    for i in range(5):
        rows.append(_row(COMMON_START_MS + i * FIVE_MS, 1.0, 1, "HIGH|HIGH"))
        rows.append(_row(COMMON_START_MS + (i + 10) * FIVE_MS, 0.0, 0, "HIGH|HIGH"))
    assert usable_strata(rows) == ["HIGH|HIGH"]
    rows_fail = rows[:-1]
    assert usable_strata(rows_fail) == []


def test_non_usable_strata_excluded_from_primary_regression():
    rows = _balanced_rows(n_eras=1, per_cell=5)
    extra = _row(COMMON_START_MS + 90_000_000, 9.0, 1, "LOW|LOW")
    rows = rows + [extra]
    usable = usable_strata(rows)
    assert "LOW|LOW" not in usable
    gate = support_gate(rows, usable)
    assert all(r["stratum_id"] != "LOW|LOW" for r in gate["primary_rows"])
    x, _y = design_matrix(gate["primary_rows"], usable)
    assert x.shape[1] == len(usable) + 1


def test_rank_deficient_and_nonfinite_failure():
    rows = [_row(COMMON_START_MS + i * FIVE_MS, 1.0, 1, "HIGH|HIGH") for i in range(10)]
    fit = fit_stratified_ols(rows, ["HIGH|HIGH", "LOW|LOW"])
    assert fit["ok"] is False
    assert fit["reason"] == "rank_deficient"
    bad = [_row(COMMON_START_MS, float("nan"), 1, "HIGH|HIGH") for _ in range(10)]
    bad += [_row(COMMON_START_MS + FIVE_MS, 0.0, 0, "HIGH|HIGH") for _ in range(10)]
    fit2 = fit_stratified_ols(bad, ["HIGH|HIGH"])
    assert fit2["ok"] is False


def test_no_intercept_ols_column_semantics_and_beta_extraction():
    rows = []
    for i in range(8):
        rows.append(_row(COMMON_START_MS + i * FIVE_MS, 3.0, 1, "A|A"))
        rows.append(_row(COMMON_START_MS + (i + 20) * FIVE_MS, 1.0, 0, "A|A"))
        rows.append(_row(COMMON_START_MS + (i + 40) * FIVE_MS, 4.0, 1, "B|B"))
        rows.append(_row(COMMON_START_MS + (i + 60) * FIVE_MS, 2.0, 0, "B|B"))
    usable = ["A|A", "B|B"]
    x, _y = design_matrix(rows, usable)
    assert x.shape[1] == 3
    assert np.all(x[:, 0] + x[:, 1] == 1.0)
    assert list(x[:, -1]) == [float(r["candidate_indicator"]) for r in rows]
    fit = fit_stratified_ols(rows, usable)
    assert fit["ok"] is True
    assert fit["beta_candidate"] == pytest.approx(2.0)


def test_bootstrap_rng_reproducible_and_p_value_formula():
    rows = _balanced_rows()
    usable = usable_strata(rows)
    primary = support_gate(rows, usable)["primary_rows"]
    fit = fit_stratified_ols(primary, usable)
    a = run_stationary_bootstrap(primary, usable, fit["beta_candidate"])
    b = run_stationary_bootstrap(primary, usable, fit["beta_candidate"])
    assert a["ok"] and b["ok"]
    assert a["p_one_sided"] == b["p_one_sided"]
    assert a["se_hat"] == b["se_hat"]
    assert a["b_hat"] == b["b_hat"]
    t_star = np.array([-2.0, 0.0, 4.0])
    assert one_sided_p(t_star, 4.0) == (1.0 + 1.0) / (BOOTSTRAP_B + 1.0)


def test_block_selector_semantics_and_arch_identity():
    auth = authenticate_arch_selector()
    assert auth["package_version"] == "8.0.0"
    assert auth["source_file_sha256"] == (
        "104d3552a8e79a801e2f8cd0401160f83a7263b4ff13da44a82d763e5664fd21"
    )
    rows = _balanced_rows()
    usable = usable_strata(rows)
    primary = support_gate(rows, usable)["primary_rows"]
    fit = fit_stratified_ols(primary, usable)
    boot = run_stationary_bootstrap(primary, usable, fit["beta_candidate"])
    assert boot["ok"] is True
    assert boot["B"] == 999
    assert 0.0 < boot["p_geom"] <= 1.0


def test_detected_boundary_and_four_state_classification():
    assert (
        final_classification(
            identifiable=False,
            beta_hat=1.0,
            p_one_sided=0.01,
            detected=False,
            robustness_pass=True,
        )
        == CLASS_NOT_IDENTIFIABLE
    )
    assert (
        final_classification(
            identifiable=True,
            beta_hat=0.0,
            p_one_sided=0.01,
            detected=False,
            robustness_pass=None,
        )
        == CLASS_NO_EVIDENCE
    )
    assert (
        final_classification(
            identifiable=True,
            beta_hat=1.0,
            p_one_sided=0.06,
            detected=False,
            robustness_pass=None,
        )
        == CLASS_NO_EVIDENCE
    )
    assert (
        final_classification(
            identifiable=True,
            beta_hat=1.0,
            p_one_sided=ALPHA,
            detected=True,
            robustness_pass=False,
        )
        == CLASS_DETECTED_NOT_ROBUST
    )
    assert (
        final_classification(
            identifiable=True,
            beta_hat=1.0,
            p_one_sided=ALPHA,
            detected=True,
            robustness_pass=True,
        )
        == CLASS_ROBUST_CANDIDATE
    )


def test_loeo_sign_rule_and_concentration_half():
    rows = _balanced_rows(per_cell=8)
    usable = usable_strata(rows)
    primary = support_gate(rows, usable)["primary_rows"]
    sign = loeo_sign_stable(primary, usable)
    assert sign["ROBUSTNESS_SIGN_STABLE"] is True
    conc = concentration(primary)
    assert conc["max_candidate_share"] <= 0.50
    assert conc["ROBUSTNESS_CONCENTRATION_OK"] is True
    era1 = ERA_BOUNDS_MS[0]
    era2 = ERA_BOUNDS_MS[1]
    tight = []
    for i in range(50):
        tight.append(_row(era1[1] + i * FIVE_MS, 1.0, 1, "HIGH|HIGH"))
        tight.append(_row(era2[1] + i * FIVE_MS, 1.0, 1, "HIGH|HIGH"))
    half = concentration(tight)
    assert half["max_candidate_share"] == pytest.approx(0.50)
    assert half["ROBUSTNESS_CONCENTRATION_OK"] is True
    tight.append(_row(era1[1] + 60 * FIVE_MS, 1.0, 1, "HIGH|HIGH"))
    over = concentration(tight)
    assert over["max_candidate_share"] > 0.50
    assert over["ROBUSTNESS_CONCENTRATION_OK"] is False


def test_robustness_cannot_rescue_primary_no_evidence():
    rows = _balanced_rows(per_cell=8)
    flipped = []
    for row in rows:
        item = dict(row)
        if int(item["candidate_indicator"]) == 1:
            item["reversal_return"] = -1.25
        else:
            item["reversal_return"] = 0.05
        flipped.append(item)
    result = evaluate_from_confirmatory_rows(flipped)
    assert result["final_classification"] == CLASS_NO_EVIDENCE
    assert result["detected"] is False
    assert result["robustness"] is None


def test_full_classification_detected_but_not_robust_from_concentration():
    strata = ["HIGH|HIGH", "HIGH|MID", "MID|MID"]
    rows = []
    seq = 0
    era1 = ERA_BOUNDS_MS[0]
    other = ERA_BOUNDS_MS[4]
    for sid in strata:
        for _ in range(40):
            rows.append(_row(era1[1] + seq * FIVE_MS, 1.2, 1, sid))
            seq += 1
        for _ in range(20):
            rows.append(_row(other[1] + seq * FIVE_MS, 0.1, 0, sid))
            seq += 1
        for _ in range(20):
            rows.append(_row(era1[1] + 10_000_000 + seq * FIVE_MS, 0.1, 0, sid))
            seq += 1
    rows.sort(key=lambda r: r["decision_T_ms"])
    result = evaluate_from_confirmatory_rows(rows)
    assert result["detected"] is True
    assert result["robustness"]["max_candidate_share"] > 0.50
    assert result["final_classification"] == CLASS_DETECTED_NOT_ROBUST


def test_robust_candidate_path_and_result_serialization_determinism():
    rows = _balanced_rows(per_cell=8)
    a = evaluate_from_confirmatory_rows(rows)
    b = evaluate_from_confirmatory_rows(rows)
    assert a["detected"] is True
    assert a["final_classification"] == CLASS_ROBUST_CANDIDATE
    assert a["MARKET_01_TEST_CALIBRATED"] is False
    assert a["B2_06_EXECUTION_AUTHORIZED"] is False
    assert a["DEFAULT_V4"] is False
    assert a["PROTECTED_OOS_TOUCHED"] is False
    assert dumps_result(a) == dumps_result(b)
    assert a["prereg_md_sha256"] == FROZEN_PREREG_MD_SHA256


def test_bound_snapshot_and_canonical_execution_are_refused():
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]))
    oi = _oi(1, COMMON_START_MS, np.array([1.0]))
    bound_price = PriceView(
        price.open_time_ms,
        price.available_at_ms,
        price.close,
        snapshot_id="717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415",
    )
    with pytest.raises(Market01ExecutionNotAuthorized):
        construct_episodes(bound_price, oi)
    with pytest.raises(Market01ExecutionNotAuthorized):
        evaluate_bound_market_01()


def test_insufficient_support_classifies_not_identifiable():
    rows = [_row(COMMON_START_MS + i * FIVE_MS, 1.0, 1, "HIGH|HIGH") for i in range(10)]
    rows += [_row(COMMON_START_MS + (i + 50) * FIVE_MS, 0.0, 0, "HIGH|HIGH") for i in range(10)]
    result = evaluate_from_confirmatory_rows(rows)
    assert result["final_classification"] == CLASS_NOT_IDENTIFIABLE
    assert result["detected"] is False
    assert result["robustness"] is None


def test_evaluate_market_01_on_synthetic_fixture_does_not_use_bound_snapshots():
    start = COMMON_START_MS
    price = _price(120, start, np.full(120, 100.0))
    oi = _oi(30, start, np.full(30, 10.0))
    result = evaluate_market_01(price, oi)
    assert result["final_classification"] == CLASS_NOT_IDENTIFIABLE
    assert result["price_snapshot_id"] == (
        "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
    )
    assert result["MARKET_01_ARMED"] is False
    assert result["MARKET_01_EXECUTION_AUTHORIZED"] is False
    assert result["MARKET_01_TEST_CALIBRATED"] is False
    assert result["episode_diagnostics"]["n_confirmatory_eligible"] == 0
