"""MARKET-02 implementation tests. Synthetic/unit fixtures only.

Does not load CORE/OI snapshots, enumerate real MARKET-02 episodes,
inspect real MARKET-02 outcomes, ARM, or execute bound snapshots.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import math
from pathlib import Path

import numpy as np
import pytest

from scripts.research.market_01_oi_expansion_weak_continuation_authority import (
    FROZEN_FREEZE_JSON_SHA256,
    FROZEN_FREEZE_MD_SHA256,
    FROZEN_PREREG_JSON_SHA256 as M01_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256 as M01_PREREG_MD_SHA256,
    LIB_ARMED_LIFECYCLE_SHA256,
    sha256_file,
)
from scripts.research.market_01_oi_expansion_weak_continuation_lib import (
    EpisodeRecord as Market01EpisodeRecord,
)
from scripts.research.market_02_oi_expansion_price_confirmation_lib import (
    ALPHA,
    BAR_MS,
    BOOTSTRAP_B,
    BOOTSTRAP_CONTEXT,
    BOOTSTRAP_NAMESPACE,
    CLASS_FRAGILE,
    CLASS_NO_EVIDENCE,
    CLASS_NOT_IDENTIFIABLE,
    CLASS_ROBUST,
    COMMON_START_MS,
    CONFIRMATION_CUT,
    ERA_BOUNDS_MS,
    FIVE_MS,
    FROZEN_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256,
    MARKET_02_BOOTSTRAP_SEED,
    MARKET_02_TEST_CALIBRATED,
    OI_SNAPSHOT_ID,
    PRICE_SNAPSHOT_ID,
    RESEARCH_ID,
    SEED_MATERIAL,
    SEED_MATERIAL_SHA256,
    SIXTY_M_MS,
    SYNTHETIC_SNAPSHOT,
    THIRTY_M_MS,
    EpisodeRecord,
    Market02NotArmed,
    OiView,
    PriceView,
    authenticate_frozen_prereg_bytes,
    classify_price_confirmation,
    confirmatory_rows,
    construct_episodes,
    continuation_return,
    design_matrix,
    detected_rule,
    dumps_result,
    evaluate_bound_market_02,
    evaluate_from_confirmatory_rows,
    evaluate_market_02,
    final_classification,
    fit_stratified_ols,
    loeo_sign_stable,
    one_sided_p,
    run_stationary_bootstrap,
    support_gate,
    usable_strata,
)


REPO = Path(__file__).resolve().parents[2]
CALENDAR_DAY_MS = 86_400_000
M01_RESULT_SHA256 = "5310946b44dd3ebc609d05a13f92f6cb414e3a0727141d0ee324bce0aa626c5e"


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


def _row(T: int, continuation: float, cand: int, stratum: str, impulse_start: int | None = None):
    if impulse_start is None:
        impulse_start = int(T) - THIRTY_M_MS
    return {
        "impulse_end_t_ms": int(T) - THIRTY_M_MS,
        "impulse_start_ms": impulse_start,
        "decision_T_ms": int(T),
        "continuation_return": float(continuation),
        "candidate_indicator": int(cand),
        "stratum_id": stratum,
    }


def _balanced_rows(*, n_eras: int = 5, per_cell: int = 8) -> list[dict]:
    strata = ["HIGH|HIGH", "HIGH|MID", "MID|MID"]
    rows = []
    seq = 0
    for _era_name, start, _end in ERA_BOUNDS_MS[:n_eras]:
        for sid in strata:
            for cand, cont in ((1, 1.25), (0, 0.05)):
                for _ in range(per_cell):
                    T = start + 3_600_000 + seq * FIVE_MS
                    rows.append(_row(T, cont, cand, sid))
                    seq += 1
    rows.sort(key=lambda r: (r["decision_T_ms"], r["impulse_start_ms"]))
    return rows


def _impulse_fixture(
    *,
    impulse: float = 0.08,
    state: float = 0.03,
    outcome: float = 0.04,
    oi_expand: bool = True,
    second_impulse: bool = False,
    nan_state: bool = False,
    nan_outcome: bool = False,
    future_impulse: float | None = None,
):
    hist_start = COMMON_START_MS - 31 * CALENDAR_DAY_MS
    t0 = COMMON_START_MS + THIRTY_M_MS
    t1 = t0 + FIVE_MS
    last_t = t1 if second_impulse else t0
    n = int((last_t + 90 * BAR_MS - hist_start) / BAR_MS) + 10
    closes = np.full(n, 100.0, dtype=np.float64)

    def set_close(clock_ms: int, value: float) -> None:
        idx = (clock_ms - BAR_MS - hist_start) // BAR_MS
        closes[idx] = value

    set_close(t0, 100.0 * math.exp(impulse))
    if nan_state:
        set_close(t0 + THIRTY_M_MS, float("nan"))
    else:
        set_close(t0 + THIRTY_M_MS, 100.0 * math.exp(impulse + state))
    if nan_outcome:
        set_close(t0 + THIRTY_M_MS + SIXTY_M_MS, float("nan"))
    else:
        set_close(
            t0 + THIRTY_M_MS + SIXTY_M_MS,
            100.0 * math.exp(impulse + state + outcome),
        )
    if second_impulse:
        set_close(t1, 100.0 * math.exp(impulse))
    if future_impulse is not None:
        set_close(t0 + FIVE_MS, 100.0 * math.exp(future_impulse))
    price = _price(n, hist_start, closes)
    oi_n = int((n * BAR_MS) / FIVE_MS) + 4
    values = np.full(oi_n, 10.0, dtype=np.float64)
    if oi_expand:
        T = t0 + THIRTY_M_MS
        idx_T = (T - FIVE_MS - hist_start) // FIVE_MS
        values[idx_T] = 10.0 * math.exp(1.0)
    oi = _oi(oi_n, hist_start, values)
    return price, oi, t0


def test_prereg_byte_identity_and_md_seed_authority():
    authenticate_frozen_prereg_bytes()
    md = REPO / "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.md"
    js = REPO / "docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.json"
    assert sha256_file(md) == FROZEN_PREREG_MD_SHA256
    assert sha256_file(js) == FROZEN_PREREG_JSON_SHA256
    twin = json.loads(js.read_text(encoding="utf-8"))
    assert hashlib.sha256(SEED_MATERIAL.encode("utf-8")).hexdigest() == SEED_MATERIAL_SHA256
    assert MARKET_02_BOOTSTRAP_SEED == int(SEED_MATERIAL_SHA256[:16], 16)
    assert MARKET_02_BOOTSTRAP_SEED == 1852983754304692007
    # Frozen JSON numeric is IEEE/JSON precision loss; MD seed is authority.
    assert twin["bootstrap"]["seed"] == 1852983754304692000
    assert twin["bootstrap"]["seed"] != MARKET_02_BOOTSTRAP_SEED
    assert twin["authority"]["json_never_overrides_md"] is True


def test_episode_record_is_not_market_01_reversal_identity():
    fields = set(EpisodeRecord.__dataclass_fields__)
    assert "continuation_return" in fields
    assert "price_confirmation" in fields
    assert "weak_or_nonconfirmation" in fields
    assert "primary_population" in fields
    assert "reversal_return" not in fields
    assert "weak_continuation" not in fields
    assert EpisodeRecord is not Market01EpisodeRecord
    assert RESEARCH_ID == "MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION"


def test_fast_precompute_is_the_contiguous_path():
    src = inspect.getsource(construct_episodes)
    pre = inspect.getsource(
        __import__(
            "scripts.research.market_02_oi_expansion_price_confirmation_lib",
            fromlist=["_construct_episodes_precomputed"],
        )._construct_episodes_precomputed
    )
    assert "_contiguous_1m" in src
    assert "_construct_episodes_precomputed" in src
    assert "_close_1m_clock" in pre
    assert "continuation_return" in pre or "int(d) * outcome" in pre
    assert "-int(d) * outcome" not in pre
    assert "market_01_oi_expansion_weak_continuation_lib.construct_episodes" not in src


def test_confirmation_boundary_candidate_vs_baseline():
    start = COMMON_START_MS
    n = 90
    closes = np.full(n, 100.0, dtype=np.float64)
    t = start + 40 * BAR_MS
    T = t + THIRTY_M_MS
    idx_t = (t - BAR_MS - start) // BAR_MS
    idx_T = (T - BAR_MS - start) // BAR_MS
    closes[idx_t] = 100.0 * math.exp(0.04)

    closes[idx_T] = closes[idx_t] * math.exp(0.01)
    eq = classify_price_confirmation(_price(n, start, closes), t, d=1, abs_impulse=0.04)
    assert eq[1]["continuation_ratio"] == pytest.approx(0.25)
    assert eq[0] is False
    assert eq[1]["weak_or_nonconfirmation"] is True
    assert eq[1]["price_confirmation"] is False

    closes[idx_T] = closes[idx_t] * math.exp(0.01 + 1e-12)
    gt = classify_price_confirmation(_price(n, start, closes), t, d=1, abs_impulse=0.04)
    assert gt[1]["continuation_ratio"] > CONFIRMATION_CUT
    assert gt[0] is True
    assert gt[1]["price_confirmation"] is True
    assert gt[1]["weak_or_nonconfirmation"] is False

    closes[idx_T] = closes[idx_t] * math.exp(0.009)
    lt = classify_price_confirmation(_price(n, start, closes), t, d=1, abs_impulse=0.04)
    assert lt[1]["continuation_ratio"] < CONFIRMATION_CUT
    assert lt[0] is False
    assert lt[1]["weak_or_nonconfirmation"] is True


def test_non_oi_expansion_is_outside_primary_not_a_baseline():
    price, oi, _t0 = _impulse_fixture(oi_expand=False, state=0.03)
    episodes = construct_episodes(price, oi)
    occupying = [e for e in episodes if e.occupies_slot]
    assert occupying
    first = occupying[0]
    assert first.qualifying_impulse is True
    assert first.oi_expansion is False
    assert first.primary_population is False
    assert first.candidate is False
    assert first.confirmatory_eligible is False
    assert first.exclusion_reason == "not_oi_expansion"
    rows = confirmatory_rows(episodes)
    assert rows == []


def test_outcome_sign_is_continuation_not_market_01_reversal():
    price, oi, t0 = _impulse_fixture(impulse=0.08, state=0.03, outcome=0.05, oi_expand=True)
    d = 1
    cont = continuation_return(price, t0, d)
    assert cont is not None
    T = t0 + THIRTY_M_MS
    expected = d * math.log(
        math.exp(0.08 + 0.03 + 0.05) / math.exp(0.08 + 0.03)
    )
    assert cont == pytest.approx(expected)
    assert cont > 0.0
    reversal_sign = -d * expected
    assert cont != pytest.approx(reversal_sign)
    episodes = construct_episodes(price, oi)
    eligible = [e for e in episodes if e.confirmatory_eligible]
    assert eligible
    rec = eligible[0]
    assert rec.continuation_return == pytest.approx(cont)
    assert rec.D == 1
    assert rec.candidate is True
    assert rec.price_confirmation is True


def test_earliest_first_120m_occupancy():
    price, oi, t0 = _impulse_fixture(second_impulse=True, oi_expand=True)
    episodes = construct_episodes(price, oi)
    occupying = [e for e in episodes if e.occupies_slot]
    assert occupying
    first = occupying[0]
    assert first.impulse_end_t_ms == t0
    skipped = [
        e
        for e in episodes
        if e.exclusion_reason == "overlap_skip"
        and first.impulse_start_ms < e.impulse_start_ms < first.impulse_start_ms + 120 * BAR_MS
    ]
    assert skipped
    missing_oi_price, missing_oi, _ = _impulse_fixture(oi_expand=False, second_impulse=True)
    missing_oi = _oi(1, COMMON_START_MS - 31 * CALENDAR_DAY_MS, np.array([1.0]))
    occupied_then_failed = construct_episodes(missing_oi_price, missing_oi)
    first_fail = next(e for e in occupied_then_failed if e.occupies_slot)
    assert first_fail.exclusion_reason == "missing_or_invalid_oi"
    later_skip = [
        e
        for e in occupied_then_failed
        if e.exclusion_reason == "overlap_skip"
        and e.impulse_start_ms > first_fail.impulse_start_ms
        and e.impulse_start_ms < first_fail.impulse_start_ms + 120 * BAR_MS
    ]
    assert later_skip


def test_pit_history_excludes_current_impulse_and_state():
    price, oi, t0 = _impulse_fixture(
        impulse=0.05, state=0.03, oi_expand=True, future_impulse=5.0
    )
    episodes = construct_episodes(price, oi)
    occupying = [e for e in episodes if e.occupies_slot]
    assert occupying
    rec = occupying[0]
    assert rec.impulse_end_t_ms == t0
    assert rec.p_impulse == 1.0
    assert rec.qualifying_impulse is True
    assert rec.p_oi == 1.0
    assert rec.impulse_start_ms == COMMON_START_MS


def test_support_floors_and_usable_stratum_rules():
    rows = []
    for i in range(5):
        rows.append(_row(COMMON_START_MS + i * FIVE_MS, 1.0, 1, "HIGH|HIGH"))
        rows.append(_row(COMMON_START_MS + (i + 10) * FIVE_MS, 0.0, 0, "HIGH|HIGH"))
    assert usable_strata(rows) == ["HIGH|HIGH"]
    assert usable_strata(rows[:-1]) == []
    weak = _balanced_rows(n_eras=1, per_cell=5)
    extra = _row(COMMON_START_MS + 90_000_000, 9.0, 1, "LOW|LOW")
    mixed = weak + [extra]
    usable = usable_strata(mixed)
    assert "LOW|LOW" not in usable
    gate = support_gate(mixed, usable)
    assert all(r["stratum_id"] != "LOW|LOW" for r in gate["primary_rows"])
    assert gate["ok"] is False
    full = _balanced_rows(per_cell=8)
    usable_full = usable_strata(full)
    gate_full = support_gate(full, usable_full)
    assert gate_full["ok"] is True
    assert gate_full["TOTAL_ELIGIBLE_EPISODES"] >= 100
    assert gate_full["CANDIDATE_EPISODES"] >= 30
    assert gate_full["BASELINE_EPISODES"] >= 30
    assert gate_full["USABLE_STRATA"] >= 3


def test_design_matrix_lex_order_no_intercept_rank_failure():
    rows = []
    for i in range(8):
        rows.append(_row(COMMON_START_MS + i * FIVE_MS, 3.0, 1, "A|A"))
        rows.append(_row(COMMON_START_MS + (i + 20) * FIVE_MS, 1.0, 0, "A|A"))
        rows.append(_row(COMMON_START_MS + (i + 40) * FIVE_MS, 4.0, 1, "B|B"))
        rows.append(_row(COMMON_START_MS + (i + 60) * FIVE_MS, 2.0, 0, "B|B"))
    usable = ["A|A", "B|B"]
    x, y = design_matrix(rows, usable)
    assert x.shape[1] == 3
    assert np.all(x[:, 0] + x[:, 1] == 1.0)
    assert list(x[:, -1]) == [float(r["candidate_indicator"]) for r in rows]
    assert np.all(np.isfinite(y))
    fit = fit_stratified_ols(rows, usable)
    assert fit["ok"] is True
    assert fit["beta_confirmation"] == pytest.approx(2.0)
    assert "beta_candidate" not in fit
    rank_fail = [_row(COMMON_START_MS + i * FIVE_MS, 1.0, 1, "HIGH|HIGH") for i in range(10)]
    unfit = fit_stratified_ols(rank_fail, ["HIGH|HIGH", "LOW|LOW"])
    assert unfit["ok"] is False
    assert unfit["reason"] == "rank_deficient"
    bad = [_row(COMMON_START_MS, float("nan"), 1, "HIGH|HIGH") for _ in range(10)]
    bad += [_row(COMMON_START_MS + FIVE_MS, 0.0, 0, "HIGH|HIGH") for _ in range(10)]
    unfit2 = fit_stratified_ols(bad, ["HIGH|HIGH"])
    assert unfit2["ok"] is False


def test_bootstrap_seed_hash_namespace_and_detected_rule():
    assert hashlib.sha256(SEED_MATERIAL.encode("utf-8")).hexdigest() == SEED_MATERIAL_SHA256
    assert BOOTSTRAP_NAMESPACE == "BOOTSTRAP"
    assert BOOTSTRAP_CONTEXT == "PRIMARY_BETA_CONFIRMATION"
    rows = _balanced_rows()
    usable = usable_strata(rows)
    primary = support_gate(rows, usable)["primary_rows"]
    fit = fit_stratified_ols(primary, usable)
    a = run_stationary_bootstrap(primary, usable, fit["beta_confirmation"])
    b = run_stationary_bootstrap(primary, usable, fit["beta_confirmation"])
    assert a["ok"] and b["ok"]
    assert a["p_one_sided"] == b["p_one_sided"]
    assert a["MARKET_02_BOOTSTRAP_SEED"] == MARKET_02_BOOTSTRAP_SEED
    assert a["seed_material_sha256"] == SEED_MATERIAL_SHA256
    assert a["namespace"] == ["BOOTSTRAP", "PRIMARY_BETA_CONFIRMATION"]
    assert a["B"] == 999
    t_star = np.array([-2.0, 0.0, 4.0])
    assert one_sided_p(t_star, 4.0) == (1.0 + 1.0) / (BOOTSTRAP_B + 1.0)
    assert detected_rule(1.0, ALPHA) is True
    assert detected_rule(1.0, ALPHA + 1e-12) is False
    assert detected_rule(0.0, 0.01) is False
    assert detected_rule(-0.1, 0.01) is False


def test_detected_direction_and_p_value_rule_in_evaluate():
    rows = _balanced_rows(per_cell=8)
    result = evaluate_from_confirmatory_rows(rows)
    assert result["beta_confirmation"] > 0.0
    assert result["p_one_sided"] <= ALPHA
    assert result["detected"] is True
    assert result["MARKET_02_TEST_CALIBRATED"] is False


def test_robustness_cannot_rescue_no_evidence():
    rows = _balanced_rows(per_cell=8)
    flipped = []
    for row in rows:
        item = dict(row)
        if int(item["candidate_indicator"]) == 1:
            item["continuation_return"] = -1.25
        else:
            item["continuation_return"] = 0.05
        flipped.append(item)
    result = evaluate_from_confirmatory_rows(flipped)
    assert result["detected"] is False
    assert result["robustness"] is None
    assert result["final_classification"] == CLASS_NO_EVIDENCE
    rescued = final_classification(
        identifiable=True,
        beta_hat=-1.0,
        p_one_sided=0.9,
        detected=False,
        robustness_pass=True,
    )
    assert rescued == CLASS_NO_EVIDENCE


def test_loeo_keeps_primary_strata_fixed():
    strata = ["HIGH|HIGH", "HIGH|MID", "MID|MID"]
    rows = []
    seq = 0
    for era_i, (_name, start, _end) in enumerate(ERA_BOUNDS_MS):
        for sid in strata:
            n_cand = 8
            n_base = 8
            if sid == "MID|MID":
                n_cand = 40 if era_i == 0 else 1
            for _ in range(n_cand):
                rows.append(_row(start + 3_600_000 + seq * FIVE_MS, 1.2, 1, sid))
                seq += 1
            for _ in range(n_base):
                rows.append(_row(start + 7_200_000 + seq * FIVE_MS, 0.1, 0, sid))
                seq += 1
    usable = ["HIGH|HIGH", "HIGH|MID", "MID|MID"]
    sign = loeo_sign_stable(rows, usable)
    assert sign["usable_stratum_ids_fixed"] == usable
    assert sign["reasons"]["ERA_1"] == "insufficient_support"
    assert sign["ROBUSTNESS_SIGN_STABLE"] is False
    recomputed = usable_strata(
        [r for r in rows if not (ERA_BOUNDS_MS[0][1] <= int(r["decision_T_ms"]) < ERA_BOUNDS_MS[0][2])]
    )
    assert "MID|MID" not in recomputed
    assert sign["usable_stratum_ids_fixed"] == usable


def test_final_classification_mapping():
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
            robustness_pass=True,
        )
        == CLASS_ROBUST
    )
    assert (
        final_classification(
            identifiable=True,
            beta_hat=1.0,
            p_one_sided=ALPHA,
            detected=True,
            robustness_pass=False,
        )
        == CLASS_FRAGILE
    )
    assert CLASS_ROBUST == "EVIDENCE_WITH_PROSPECTIVE_ROBUSTNESS"
    assert CLASS_FRAGILE == "EVIDENCE_FRAGILE_NONSTATIONARITY"
    assert CLASS_NOT_IDENTIFIABLE == "NOT_IDENTIFIABLE_OR_INSUFFICIENT_SUPPORT"
    assert CLASS_NO_EVIDENCE == "NO_EVIDENCE"


def test_missing_nonfinite_data_fail_closed():
    price, oi, _t0 = _impulse_fixture(oi_expand=True, nan_state=True)
    episodes = construct_episodes(price, oi)
    occupying = [e for e in episodes if e.occupies_slot]
    assert occupying
    rec = occupying[0]
    assert rec.primary_population is True
    assert rec.confirmatory_eligible is False
    assert rec.exclusion_reason == "missing_state_return"
    price2, oi2, _ = _impulse_fixture(oi_expand=True, nan_outcome=True)
    episodes2 = construct_episodes(price2, oi2)
    rec2 = next(e for e in episodes2 if e.occupies_slot)
    assert rec2.exclusion_reason == "missing_outcome"
    assert rec2.confirmatory_eligible is False
    zero = _price(3, COMMON_START_MS, np.array([100.0, 100.0, 100.0]))
    assert continuation_return(zero, COMMON_START_MS + THIRTY_M_MS, 1) is None


def test_bound_snapshots_refused_because_not_armed():
    price, oi, _ = _impulse_fixture()
    bound_price = PriceView(
        price.open_time_ms,
        price.available_at_ms,
        price.close,
        snapshot_id=PRICE_SNAPSHOT_ID,
    )
    bound_oi = OiView(
        oi.create_time_ms,
        oi.available_at_ms,
        oi.sum_open_interest,
        snapshot_id=OI_SNAPSHOT_ID,
    )
    with pytest.raises(Market02NotArmed, match="MARKET_02_NOT_ARMED"):
        construct_episodes(bound_price, oi)
    with pytest.raises(Market02NotArmed, match="MARKET_02_NOT_ARMED"):
        construct_episodes(price, bound_oi)
    with pytest.raises(Market02NotArmed, match="MARKET_02_NOT_ARMED"):
        evaluate_bound_market_02(bound_price, bound_oi)
    with pytest.raises(Market02NotArmed, match="MARKET_02_NOT_ARMED"):
        evaluate_bound_market_02()


def test_market_01_frozen_scientific_bytes_remain_identical():
    m01_md = REPO / "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md"
    m01_js = REPO / "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json"
    freeze_md = REPO / "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.md"
    freeze_js = REPO / "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.json"
    result = REPO / "docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json"
    lib = REPO / "scripts/research/market_01_oi_expansion_weak_continuation_lib.py"
    assert sha256_file(m01_md) == M01_PREREG_MD_SHA256
    assert sha256_file(m01_js) == M01_PREREG_JSON_SHA256
    assert sha256_file(freeze_md) == FROZEN_FREEZE_MD_SHA256
    assert sha256_file(freeze_js) == FROZEN_FREEZE_JSON_SHA256
    assert hashlib.sha256(result.read_bytes()).hexdigest() == M01_RESULT_SHA256
    assert sha256_file(lib) == LIB_ARMED_LIFECYCLE_SHA256


def test_robust_and_fragile_paths_and_uncalibrated_flag():
    rows = _balanced_rows(per_cell=8)
    a = evaluate_from_confirmatory_rows(rows)
    b = evaluate_from_confirmatory_rows(rows)
    assert a["final_classification"] == CLASS_ROBUST
    assert a["MARKET_02_TEST_CALIBRATED"] is False
    assert a["MARKET_02_ARMED"] is False
    assert a["MARKET_02_EXECUTED"] is False
    assert a["PROTECTED_OOS_TOUCHED"] is False
    assert a["B2_06_EXECUTION_AUTHORIZED"] is False
    assert a["DEFAULT_V4"] is False
    assert a["implementation_frozen"] is False
    assert dumps_result(a) == dumps_result(b)
    strata = ["HIGH|HIGH", "HIGH|MID", "MID|MID"]
    concentrated = []
    seq = 0
    era1 = ERA_BOUNDS_MS[0]
    other = ERA_BOUNDS_MS[4]
    for sid in strata:
        for _ in range(40):
            concentrated.append(_row(era1[1] + seq * FIVE_MS, 1.2, 1, sid))
            seq += 1
        for _ in range(20):
            concentrated.append(_row(other[1] + seq * FIVE_MS, 0.1, 0, sid))
            seq += 1
        for _ in range(20):
            concentrated.append(_row(era1[1] + 10_000_000 + seq * FIVE_MS, 0.1, 0, sid))
            seq += 1
    concentrated.sort(key=lambda r: r["decision_T_ms"])
    fragile = evaluate_from_confirmatory_rows(concentrated)
    assert fragile["detected"] is True
    assert fragile["robustness"]["max_candidate_share"] > 0.50
    assert fragile["final_classification"] == CLASS_FRAGILE
    tiny = [_row(COMMON_START_MS + i * FIVE_MS, 1.0, 1, "HIGH|HIGH") for i in range(10)]
    tiny += [_row(COMMON_START_MS + (i + 50) * FIVE_MS, 0.0, 0, "HIGH|HIGH") for i in range(10)]
    short = evaluate_from_confirmatory_rows(tiny)
    assert short["final_classification"] == CLASS_NOT_IDENTIFIABLE


def test_evaluate_market_02_synthetic_does_not_use_bound_snapshots():
    start = COMMON_START_MS
    price = _price(120, start, np.full(120, 100.0))
    oi = _oi(30, start, np.full(30, 10.0))
    result = evaluate_market_02(price, oi)
    assert result["final_classification"] == CLASS_NOT_IDENTIFIABLE
    assert result["price_snapshot_id"] == PRICE_SNAPSHOT_ID
    assert result["MARKET_02_ARMED"] is False
    assert result["MARKET_02_TEST_CALIBRATED"] is MARKET_02_TEST_CALIBRATED
    assert np.__version__ == "2.1.3"


def test_canonical_path_supplies_chronological_confirmatory_rows():
    """Canonical evaluate_market_02 feeds T-sorted rows into bootstrap.

    Does not redesign evaluate_from_confirmatory_rows. Does not add a
    scientific transformation. Proves confirmatory_rows sorts by
    (decision_T_ms, impulse_start_ms) and that evaluate_market_02 uses
    that function before evaluate_from_confirmatory_rows.
    """
    canon = inspect.getsource(evaluate_market_02)
    assert "rows = confirmatory_rows(episodes)" in canon
    assert "evaluate_from_confirmatory_rows(rows" in canon
    rows_src = inspect.getsource(confirmatory_rows)
    assert 'rows.sort(key=lambda r: (int(r["decision_T_ms"]), int(r["impulse_start_ms"])))' in rows_src

    def _eligible(T: int, start: int) -> EpisodeRecord:
        return EpisodeRecord(
            impulse_end_t_ms=int(T) - THIRTY_M_MS,
            impulse_start_ms=int(start),
            decision_T_ms=int(T),
            outcome_end_ms=int(T) + SIXTY_M_MS,
            D=1,
            oi_expansion=True,
            primary_population=True,
            candidate=True,
            stratum_id="HIGH|HIGH",
            continuation_return=0.01,
            confirmatory_eligible=True,
        )

    late = COMMON_START_MS + 9 * FIVE_MS
    mid = COMMON_START_MS + 5 * FIVE_MS
    early = COMMON_START_MS + FIVE_MS
    shuffled = [
        _eligible(late, late - THIRTY_M_MS),
        _eligible(early, early - THIRTY_M_MS + 1),
        _eligible(early, early - THIRTY_M_MS),
        _eligible(mid, mid - THIRTY_M_MS),
    ]
    ordered = confirmatory_rows(shuffled)
    keys = [(r["decision_T_ms"], r["impulse_start_ms"]) for r in ordered]
    assert keys == sorted(keys)
    assert keys[0][0] == early
    assert keys[0][1] < keys[1][1]
    assert [r["decision_T_ms"] for r in ordered] == [early, early, mid, late]
