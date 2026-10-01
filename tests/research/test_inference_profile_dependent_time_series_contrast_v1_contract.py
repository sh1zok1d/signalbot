"""Lock the reusable inference-profile contract. No validation draws and no outcomes."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JSON_PATH = ROOT / "docs/research/INFERENCE_PROFILE_DEPENDENT_TIME_SERIES_CONTRAST_V1.json"
MD_PATH = ROOT / "docs/research/INFERENCE_PROFILE_DEPENDENT_TIME_SERIES_CONTRAST_V1.md"

DEVELOPMENT_SEEDS = {20260930171, 20260930181, 20260930211, 20260930311, 20260930317}


def load_contract():
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def test_contract_files_exist():
    assert JSON_PATH.is_file()
    assert MD_PATH.is_file()


def test_decision_and_closed_flags():
    contract = load_contract()
    assert contract["DECISION"] == "REUSABLE_V2_CONTRACT_READY_FOR_INDEPENDENT_REVIEW"
    assert contract["DESIGN_ONLY"] is True
    assert contract["VALIDATION_EXECUTED"] is False
    assert contract["IMPLEMENTATION_AUTHORIZED"] is False
    assert contract["PROFILE_VALIDATED"] is False
    assert contract["TARGET_OPENING"] == "FORBIDDEN"
    assert contract["V2_AUTOMATIC_METHOD_SWITCHING"] is False
    assert contract["D7_V2_ESTIMAND_CHANGED"] is False
    assert contract["D7_HYPOTHESIS_FAILED"] is False
    assert contract["D7_BITMEX_PRIMARY_TARGET_OPENED"] is False
    assert contract["D7_PRIMARY_EFFECT_COMPUTED"] is False
    assert contract["NEXT_IMPLEMENTATION_AUTHORIZED_BY_THIS_CONTRACT"] is False
    assert contract["COMPILER_EDIT_AUTHORIZED"] is False


def test_profile_identity_is_generic():
    contract = load_contract()
    assert contract["REUSABLE_PROFILE_ID"] == "DEPENDENT_TIME_SERIES_CONTRAST_V1"
    assert contract["PRIMARY_D7_V2_METHOD"] == "FIXED_B_BARTLETT_HAC"
    assert contract["INFERENCE_CLASS"] == "DEPENDENT_TIME_SERIES_CONTRAST"
    assert contract["REJECTED_CANDIDATES"]["DEPENDENT_WILD_OR_STATIONARY_BOOTSTRAP"] == "NOT_PRIMARY"
    assert contract["REJECTED_CANDIDATES"]["SUBSAMPLING"] == "NOT_PRIMARY"
    assert contract["OWNS_TEMPORAL_GATE"] is False
    assert contract["TYPE_I_VALIDATION_FIRST"] is True
    assert "D7InferenceV2" not in json.dumps(contract)
    assert contract["STATISTIC"]["BANDWIDTH_RULE"].startswith("H = hypothesis.structural_dependence_horizon")
    assert contract["N_EFF_REPLACES_POWER_GATE"] is False


def test_seeds_are_new_and_disjoint():
    contract = load_contract()
    master = contract["VALIDATION_MASTER_SEED"]
    table = contract["FIXED_B_LIMIT_TABLE_SEED"]
    assert master == 20260930427
    assert table == 20260930431
    assert master != table
    assert master not in DEVELOPMENT_SEEDS
    assert table not in DEVELOPMENT_SEEDS
    assert set(contract["DEVELOPMENT_SEEDS_NOT_VALIDATION"]) == DEVELOPMENT_SEEDS
    assert contract["LABEL_PREFIX"] == "dts-v1:"


def test_type_i_gate_and_sample_size():
    contract = load_contract()
    design = contract["VALIDATION_DESIGN"]
    gate = contract["TYPE_I_GATE"]
    assert contract["ALPHA"] == 0.05
    assert contract["TYPE_I_CEILING"] == 0.06
    assert contract["WILSON_Z_95"] == 1.959963984540054
    assert contract["CATASTROPHIC_WILSON_UPPER_CAP"] == 0.075
    assert contract["WILSON_UPPER_QUANTILE"] == 0.9
    assert contract["WILSON_UPPER_QUANTILE_CEILING"] == 0.06
    assert design["FAMILY_COUNT"] == 7
    assert design["CONFIGS_PER_FAMILY"] == 8
    assert design["CONFIGURATION_COUNT"] == 56
    assert design["SIMS_PER_CONFIGURATION"] == 10000
    assert design["TYPE_I_EVALUATIONS"] == 560000
    assert design["DESIGN_DRAW_FAILED_IS_PROFILE_FAIL"] is True
    assert gate["Q90_OF_WILSON_UPPERS_LTE"] == 0.06
    assert gate["EVERY_WILSON_LOWER_LTE"] == 0.06
    assert gate["EVERY_WILSON_UPPER_LTE"] == 0.075
    assert gate["ADD_SIMS_ONLY_TO_FAILURES"] is False
    assert gate["DROP_CONFIGS_AFTER_RESULTS"] is False
    assert design["FAMILY_5_BINARY_SLOTS"] == "REASSIGNED_TO_CONTINUOUS_STOCHASTIC_VOLATILITY"


def test_d7_adapter_does_not_change_the_estimand():
    contract = load_contract()
    adapter = contract["D7_ADAPTER"]
    assert adapter["STRUCTURAL_DEPENDENCE_HORIZON"] == 721
    assert adapter["WEIGHT_SCHEME"] == "WITHIN_STRATUM_RATE_MATCHED"
    assert adapter["PRACTICAL_EFFECT_THRESHOLD"] == 0.05
    assert adapter["DIRECTION"] == "ONE_SIDED_UPPER"
    assert "mean(Y|X=1,s) - mean(Y|eligible,s)" in adapter["ESTIMAND"]
    assert adapter["SELECTOR_DIGEST"] == "88b6e9571e26c0037ee14522249f21ec7f0d46261982dcb5e5bb0964cd396cc6"
    temporal = adapter["TEMPORAL_GATE"]
    assert temporal["OWNED_BY_PROFILE"] is False
    assert temporal["YEARS"] == [2017, 2018, 2019]
    assert temporal["POSITIVE_YEARS_REQUIRED"] == 2
    assert temporal["DIAGNOSTIC_YEAR"] == 2016
    power = adapter["POWER_ADMISSION"]
    assert power["GATE_DELTA"] == 0.05
    assert power["USES_REAL_OUTCOME"] is False
    assert power["BASE_POWER_MIN"] == 0.8
    assert power["STRESS_POWER_MIN"] == 0.5
    assert contract["SENSITIVITY_ONLY"]["NORMAL_CRITICAL_VALUE_HAC_SAME_H"]["MAY_FLIP_PRIMARY"] is False


def test_markdown_matches_locked_tokens():
    text = MD_PATH.read_text(encoding="utf-8")
    for token in (
        "REUSABLE_V2_CONTRACT_READY_FOR_INDEPENDENT_REVIEW",
        "REUSABLE_PROFILE_ID = DEPENDENT_TIME_SERIES_CONTRAST_V1",
        "PRIMARY_D7_V2_METHOD = FIXED_B_BARTLETT_HAC",
        "D7_V2_ESTIMAND_CHANGED = false",
        "V2_AUTOMATIC_METHOD_SWITCHING = false",
        "D7_HYPOTHESIS_FAILED = false",
        "D7_BITMEX_PRIMARY_TARGET_OPENED = false",
        "D7_PRIMARY_EFFECT_COMPUTED = false",
        "VALIDATION_MASTER_SEED = 20260930427",
        "FIXED_B_LIMIT_TABLE_SEED = 20260930431",
        "TARGET_OPENING = FORBIDDEN",
        "PROFILE_VALIDATED = false",
    ):
        assert token in text
