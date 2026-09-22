"""Synthetic tests for the D2 excess path-risk decomposition design.

Does not compute real Binance ADVERSE_SHARE / DELTA_SHARE.
Does not open 2025/2026.
Does not reuse BitMEX 2017-2019.
Does not change the frozen D2 selector.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from scripts.research.d2_excess_path_risk_beyond_vol_clustering_design import (
    CLASS_INVALID,
    CLASS_NO_STRUCTURE,
    CLASS_PROMISING,
    CLASS_SCALE_COMPATIBLE,
    FUTURE_BAR_COUNT,
    JSON_REL,
    MD_REL,
    N_RANDOM_CONTROLS,
    PRACTICAL_DELTA_SHARE,
    PRIMARY_SELECTOR,
    PRIMARY_TARGET,
    RANDOM_SEED,
    RV_PCTL,
    RV_TRAILING_WINDOW,
    TARGET_INELIGIBLE_REASON,
    RealDecompositionForbidden,
    adverse_share,
    classify_decomposition,
    file_sha256,
    frozen_d2_selector_contract,
    identity_metadata_from_frozen_discovery,
    mae_pair,
    mc_p_share,
    path_asymmetry,
    path_scale,
    path_scale_materially_elevated,
    practical_gate,
    refuse_real_decomposition_outcome,
    statistical_gate,
    target_ineligible_reason,
    temporal_gate,
    verify_design_authorities,
)
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_cross_venue_dislocation_evaluator import arithmetic_mae
from scripts.research.market_06_cross_venue_dislocation_parsers import PerpBar

REPO = Path(__file__).resolve().parents[2]
ENTRY = 100.0
N_BARS = 288


def _path(*, low: float, high: float, n: int = N_BARS) -> list[PerpBar]:
    bars: list[PerpBar] = []
    for i in range(n):
        bars.append(
            PerpBar(
                open_time_ms=i * 300_000,
                open=ENTRY,
                high=float(high),
                low=float(low),
                close=ENTRY,
            )
        )
    return bars


def test_mirror_side_is_exactly_negative_side_on_same_path() -> None:
    future = _path(low=90.0, high=112.0)
    side = 1.0
    mae_side, mae_opp = mae_pair(side, ENTRY, future)
    assert mae_side == arithmetic_mae(side, ENTRY, future)
    assert mae_opp == arithmetic_mae(-side, ENTRY, future)
    swapped_side, swapped_opp = mae_pair(-side, ENTRY, future)
    assert swapped_side == mae_opp
    assert swapped_opp == mae_side
    share = adverse_share(mae_side, mae_opp)
    swapped = adverse_share(swapped_side, swapped_opp)
    assert share is not None and swapped is not None
    assert abs(share + swapped - 1.0) < 1e-15
    assert 0.0 <= share <= 1.0
    assert 0.0 <= swapped <= 1.0


def test_symmetric_path_share_is_half_and_scale_cancels() -> None:
    small = _path(low=95.0, high=105.0)
    large = _path(low=80.0, high=120.0)
    side = 1.0
    s_small, o_small = mae_pair(side, ENTRY, small)
    s_large, o_large = mae_pair(side, ENTRY, large)
    share_small = adverse_share(s_small, o_small)
    share_large = adverse_share(s_large, o_large)
    assert share_small == pytest.approx(0.5)
    assert share_large == pytest.approx(0.5)
    assert path_scale(s_large, o_large) > path_scale(s_small, o_small)
    assert share_small == share_large
    assert path_asymmetry(share_small) == pytest.approx(0.0)


def test_common_path_scale_alone_does_not_change_share() -> None:
    base = _path(low=90.0, high=105.0)
    scaled = _path(low=80.0, high=110.0)
    # scaled has double the deviation from entry on both sides (10 and 5 -> 20 and 10).
    side = 1.0
    s0, o0 = mae_pair(side, ENTRY, base)
    s1, o1 = mae_pair(side, ENTRY, scaled)
    assert path_scale(s1, o1) == pytest.approx(2.0 * path_scale(s0, o0))
    assert adverse_share(s0, o0) == pytest.approx(adverse_share(s1, o1))
    assert adverse_share(s0, o0) == pytest.approx(0.10 / 0.15)


def test_zero_path_scale_is_ineligible_without_epsilon() -> None:
    flat = _path(low=ENTRY, high=ENTRY)
    mae_side, mae_opp = mae_pair(1.0, ENTRY, flat)
    assert mae_side == 0.0
    assert mae_opp == 0.0
    assert path_scale(mae_side, mae_opp) == 0.0
    assert adverse_share(mae_side, mae_opp) is None
    assert target_ineligible_reason(mae_side, mae_opp) == TARGET_INELIGIBLE_REASON


def test_frozen_d2_mask_semantics_unchanged() -> None:
    source = inspect.getsource(C.rv_abstention_mask)
    assert "trailing = rvs[i - RV_TRAILING_WINDOW : i]" in source
    assert "mask[i] = bool(rvs[i] > threshold)" in source
    assert "np.percentile(trailing, RV_PCTL)" in source
    assert RV_TRAILING_WINDOW == 250
    assert RV_PCTL == 90.0
    assert FUTURE_BAR_COUNT == 288
    contract = frozen_d2_selector_contract()
    assert contract["D2_SELECTOR_CHANGED"] is False
    assert contract["NO_P85_P95"] is True
    rows = []
    t0 = C.ms_from_utc(C.RULE1_INTERVAL_START)
    for i in range(260):
        rows.append(
            C.DiscoveryRow(
                t_ms=t0 + i * 86_400_000,
                year=2020,
                rv=1.0 if i < 250 else 100.0,
                ret=0.01,
                side=1.0,
                severity=0.01,
                entry_open=ENTRY,
                future_closes=tuple([ENTRY] * 288),
            )
        )
    mask = C.rv_abstention_mask(rows)
    assert int(mask[:250].sum()) == 0
    assert bool(mask[250]) is True


def test_design_json_frozen_and_no_real_outcome() -> None:
    decision = json.loads((REPO / JSON_REL).read_text(encoding="utf-8"))
    md = (REPO / MD_REL).read_text(encoding="utf-8")
    assert decision["DESIGN_STATUS"] == "FROZEN"
    assert decision["PRIMARY_SELECTOR"] == PRIMARY_SELECTOR
    assert decision["PRIMARY_TARGET"] == PRIMARY_TARGET
    assert decision["ADVERSE_SHARE_FORMULA"] == "MAE_SIDE / (MAE_SIDE + MAE_OPPOSITE)"
    assert decision["PATH_SCALE_FORMULA"] == "MAE_SIDE + MAE_OPPOSITE"
    assert decision["TARGET_SPECIFIC_INELIGIBILITY"] == TARGET_INELIGIBLE_REASON
    assert decision["RANDOM_SEED"] == RANDOM_SEED == 20260922131
    assert decision["N_RANDOM_CONTROLS"] == N_RANDOM_CONTROLS == 10000
    assert decision["STATISTICAL_GATE"] == "MU_SHARE_RULE > CONTROL_SHARE_P95"
    assert decision["PRACTICAL_GATE"] == "DELTA_SHARE >= 0.05"
    assert PRACTICAL_DELTA_SHARE == 0.05
    assert decision["TEMPORAL_GATE"].startswith("DELTA_SHARE > 0 in at least 3 of 5 years")
    assert decision["REAL_DECOMPOSITION_OUTCOME_COMPUTED"] is False
    assert decision["BITMEX_2017_2019_REUSED_FOR_NEW_TARGET"] is False
    assert decision["PROTECTED_2025_OPENED"] is False
    assert decision["PROTECTED_2026_OPENED"] is False
    assert decision["MARKET_07_CREATED"] is False
    assert decision["EXECUTION_AUTHORIZED"] is False
    assert decision["D2_SELECTOR_CHANGED"] is False
    assert decision["HORIZON_CHANGED"] is False
    assert decision["RV_RULE_CHANGED"] is False
    assert decision["TARGET_CHANGED_FROM_ORIGINAL_D2"] is True
    assert decision["NO_FUTURE_VOL_MATCHING_IN_PRIMARY"] is True
    assert decision["MC_P_SHARE"] == (
        "(1 + count(CONTROL_SHARE_MEAN >= MU_SHARE_RULE)) / 10001"
    )
    assert decision["FUTURE_PATH_RECONSTRUCTION"].startswith("DiscoveryRow stores future_closes")
    assert decision["DESIGN_DOES_NOT_REBUILD_MASK_ON_REAL_ROWS"] is True
    assert decision["NEXT_UNIT"] == (
        "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW"
    )
    assert CLASS_PROMISING in decision["CLASSIFICATION_VOCABULARY"]
    assert "POST_REPLICATION_MECHANISM_DECOMPOSITION_DISCOVERY" in md
    assert verify_design_authorities(REPO) == []
    with pytest.raises(RealDecompositionForbidden):
        refuse_real_decomposition_outcome()
    market_07 = list((REPO / "docs").rglob("*MARKET_07*")) + list(
        (REPO / "docs").rglob("*MARKET-07*")
    )
    assert market_07 == []


def test_gates_and_path_scale_cannot_rescue_primary() -> None:
    assert statistical_gate(0.56, 0.55) is True
    assert statistical_gate(0.55, 0.55) is False
    assert practical_gate(0.05) is True
    assert practical_gate(0.049999) is False
    years = {"2020": 0.01, "2021": 0.01, "2022": 0.01, "2023": -0.01, "2024": -0.01}
    assert temporal_gate(years) is True
    years["2022"] = -0.01
    assert temporal_gate(years) is False
    elevated = path_scale_materially_elevated(
        mu_path_scale_rule=0.12,
        mu_path_scale_control=0.08,
        control_path_scale_p95=0.10,
    )
    assert elevated is True
    assert (
        classify_decomposition(
            integrity_invalid=False,
            statistical=False,
            practical=False,
            temporal=False,
            path_scale_elevated=True,
        )
        == CLASS_SCALE_COMPATIBLE
    )
    assert (
        classify_decomposition(
            integrity_invalid=False,
            statistical=True,
            practical=True,
            temporal=True,
            path_scale_elevated=False,
        )
        == CLASS_PROMISING
    )
    assert (
        classify_decomposition(
            integrity_invalid=False,
            statistical=False,
            practical=False,
            temporal=False,
            path_scale_elevated=False,
        )
        == CLASS_NO_STRUCTURE
    )
    assert (
        classify_decomposition(
            integrity_invalid=True,
            statistical=True,
            practical=True,
            temporal=True,
            path_scale_elevated=True,
        )
        == CLASS_INVALID
    )


def test_previous_d2_result_and_program_decision_bytes_unmutated() -> None:
    assert file_sha256(REPO / "docs/research/discovery_results/D2_DISCOVERY_RESULT.json") == (
        "42ee5d7db19a17e62d861513759192ec78898ee9ec901902b3db58e7386966c2"
    )
    assert file_sha256(
        REPO / "docs/research/PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED.json"
    ) == "d9b6000273d93ea86b0d02282dfa9f12f3b1aad9bb25322dbbbcc689f008448d"
    original = json.loads(
        (REPO / "docs/research/D2_BITMEX_REPLICATION_RESULT.json").read_text(encoding="utf-8")
    )
    corrected = json.loads(
        (REPO / "docs/research/D2_BITMEX_REPLICATION_CORRECTED_RESULT.json").read_text(
            encoding="utf-8"
        )
    )
    assert original["CLASSIFICATION"] == "D2_BITMEX_REPLICATION_INVALID"
    assert corrected["CLASSIFICATION"] == "D2_BITMEX_REPLICATION_SUPPORTED"
    src = inspect.getsource(C.rv_abstention_mask)
    assert "2025" not in src
    assert RANDOM_SEED != 20260921125
    meta = identity_metadata_from_frozen_discovery(REPO)
    assert meta["RULE_1_ROW_COUNT"] == 1791
    assert meta["RULE_1_YEAR_BREAKDOWN"] == {
        "2020": 334,
        "2021": 364,
        "2022": 364,
        "2023": 364,
        "2024": 365,
    }
    assert meta["RULE_1_INTERVAL"] == (
        "2020-02-01T00:05:00Z -> 2025-01-01T00:00:00Z exclusive"
    )
    assert meta["CORE_BTC_SNAPSHOT"] == (
        "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
    )


def test_mae_pair_uses_identical_future_path_and_mc_p_formula() -> None:
    source = inspect.getsource(mae_pair)
    assert "arithmetic_mae(float(side), float(entry), future_bars)" in source
    assert "arithmetic_mae(float(-side), float(entry), future_bars)" in source
    future = _path(low=88.0, high=107.0)
    side = -1.0
    mae_side, mae_opp = mae_pair(side, ENTRY, future)
    assert mae_side == arithmetic_mae(side, ENTRY, future)
    assert mae_opp == arithmetic_mae(-side, ENTRY, future)
    share = adverse_share(mae_side, mae_opp)
    assert share is not None
    assert 0.0 <= share <= 1.0
    assert path_asymmetry(share) == pytest.approx(2.0 * share - 1.0)
    assert mc_p_share(0.55, [0.50, 0.55, 0.60]) == pytest.approx(3.0 / 4.0)
    assert mc_p_share(0.61, [0.50, 0.55, 0.60]) == pytest.approx(1.0 / 4.0)


def test_no_real_binance_or_bitmex_load_in_design_module() -> None:
    source = inspect.getsource(
        __import__(
            "scripts.research.d2_excess_path_risk_beyond_vol_clustering_design",
            fromlist=["mae_pair"],
        )
    )
    module = Path(
        "scripts/research/d2_excess_path_risk_beyond_vol_clustering_design.py"
    ).read_text(encoding="utf-8")
    assert "load_core" not in module.lower()
    assert "canonical_5m.jsonl" not in module
    assert "build_rows(" not in module
    assert "evaluate_constructed_rows" not in module
    assert "load_bitmex" not in module.lower()
    assert "xbtusd" not in module.lower()
    del source
