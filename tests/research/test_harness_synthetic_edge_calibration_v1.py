"""Fixture-only tests for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

Tiny deterministic synthetic worlds only. These tests must not run the frozen
3200-world grid, access real market data, open B2-06, or inspect 2025/2026.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from scripts.research import harness_synthetic_edge_calibration_v1 as runner
from scripts.research import harness_synthetic_edge_calibration_v1_lib as lib

REPO = Path(__file__).resolve().parents[2]
PREREG_JSON = REPO / "docs" / "research" / "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json"
PREREG_MD = REPO / "docs" / "research" / "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md"


def _prereg() -> dict:
    return json.loads(PREREG_JSON.read_text(encoding="utf-8"))


def _tiny(**kwargs) -> lib.FixtureExecutionConfig:
    params = {
        "n_rows": 50,
        "scenario_id": "EASY",
        "world_index": 0,
        "visibility_replicates": 3,
        "bootstrap_replicates": 3,
        "placebo_replicates": 3,
        "block_rows": 5,
    }
    params.update(kwargs)
    return lib.FixtureExecutionConfig(**params)


def _rank_safe_world(n_rows: int = 50) -> dict:
    """Synthetic arrays with era-local rank for intercept+X1+X2+Fj."""
    width = n_rows // 5
    pattern_x1 = np.array([-2.0, -1.5, -0.4, 0.3, 0.8, 1.2, 1.6, 2.0, -0.2, 0.5], dtype=np.float64)
    pattern_x2 = np.array([-2.0, -1.4, -0.3, 0.2, 0.7, 1.1, -1.2, 1.8, 0.1, -0.6], dtype=np.float64)
    pattern_s = np.array([0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0], dtype=np.float64)
    x1 = np.empty(n_rows, dtype=np.float64)
    x2 = np.empty(n_rows, dtype=np.float64)
    s = np.empty(n_rows, dtype=np.float64)
    for i in range(5):
        slc = slice(i * width, (i + 1) * width)
        x1[slc] = np.resize(pattern_x1, width)
        x2[slc] = np.resize(pattern_x2, width)
        s[slc] = np.resize(pattern_s, width)
    y = (0.20 * x1 - 0.15 * x2 + 0.25 * s + 0.01 * np.arange(n_rows, dtype=np.float64)).astype(
        np.float64
    )
    return {
        "Y": y,
        "X1": x1,
        "X2": x2,
        "S": s,
        "world_identity": lib.world_identity("EASY", n_rows, 0),
    }


def test_frozen_constants_match_json_prereg():
    prereg = _prereg()
    authority = lib.frozen_production_authority()
    assert prereg["status"] == "FROZEN_BEFORE_IMPLEMENTATION"
    assert authority["root_seed"] == 20260908 == prereg["rng_authority"]["root_seed"]
    assert authority["rho"] == 0.90 == prereg["dgp"]["mechanism"]["rho"]
    assert authority["primary_N"] == 5000
    assert authority["small_sensitivity_N"] == [2500, 10000]
    assert authority["bootstrap_replicates"] == 500 == prereg["bootstrap"]["replicates"]
    assert authority["visibility_replicates"] == 500
    assert authority["placebo_replicates"] == 999 == prereg["placebo"]["replicates"]
    assert authority["block_rows"] == 50
    assert authority["planned_total_worlds"] == 3200
    assert authority["worlds_per_primary_scenario"] == 400
    assert authority["materiality_gate"] == 0.02
    assert lib.WILSON_Z == 1.959963984540054
    assert lib.SUPPORT_SANITY_MIN == 50
    assert prereg["acceptance"]["discovery"]["EASY_BLIND_USEFUL_DISCOVERY_min"] == 0.80
    assert prereg["acceptance"]["discovery"]["MODERATE_BLIND_USEFUL_DISCOVERY_min"] == 0.50
    assert prereg["implementation_exists"] is False
    assert prereg["production_calibration_executed"] is False
    assert prereg["boundaries"]["synthetic_execution_authorized"] is False


def test_json_prereg_scientific_bytes_untouched_by_this_module():
    digest_before = hashlib.sha256(PREREG_JSON.read_bytes()).hexdigest()
    lib.load_frozen_prereg()
    assert hashlib.sha256(PREREG_JSON.read_bytes()).hexdigest() == digest_before
    assert PREREG_MD.is_file()


def test_deterministic_seed_derivation():
    ident = lib.world_identity("EASY", 50, 0)
    assert ident == "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1|EASY|50|0"
    expected_world = int.from_bytes(
        hashlib.sha256(b"20260908|" + ident.encode("utf-8")).digest()[:8],
        "big",
        signed=False,
    )
    a = lib.world_seed(ident)
    b = lib.world_seed(ident)
    assert a == b == expected_world
    assert lib.world_seed(ident, root_seed=20260908) != lib.world_seed(ident, root_seed=1)
    expected_dgp = int.from_bytes(
        hashlib.sha256(f"{a}|DGP".encode("utf-8")).digest()[:8],
        "big",
        signed=False,
    )
    expected_boot = int.from_bytes(
        hashlib.sha256(f"{a}|BOOTSTRAP|F03".encode("utf-8")).digest()[:8],
        "big",
        signed=False,
    )
    dgp = lib.namespace_seed(a, "DGP")
    boot = lib.namespace_seed(a, "BOOTSTRAP", "F03")
    assert dgp == expected_dgp
    assert boot == expected_boot
    assert dgp != boot
    with pytest.raises(ValueError, match="unknown namespace"):
        lib.namespace_seed(a, "REROLL")


def test_python_hash_and_reroll_are_absent():
    source = Path(lib.__file__).read_text(encoding="utf-8")
    assert "hashlib.sha256" in source
    assert "hash(" not in source.replace("sha256(", "DIGEST(")
    assert "os.environ" not in source
    assert "getenv" not in source
    assert "authorized=True" not in source


def test_dgp_reproducibility_and_float64():
    a = lib.simulate_dgp(scenario_id="MODERATE", n_rows=50, world_index=1)
    b = lib.simulate_dgp(scenario_id="MODERATE", n_rows=50, world_index=1)
    for key in ("X1", "X2", "S", "Y", "MU_BASE", "NOISE"):
        np.testing.assert_array_equal(a[key], b[key])
        assert a[key].dtype == np.float64
    c = lib.simulate_dgp(scenario_id="MODERATE", n_rows=50, world_index=2)
    assert not np.array_equal(a["Y"], c["Y"])
    assert a["X1"][0] == 0.0 and a["X2"][0] == 0.0


def test_markov_support_mechanics():
    assert lib.p01(0.10, 0.90) == pytest.approx(0.10 * 0.10 / 0.90)
    world = lib.simulate_dgp(scenario_id="NULL", n_rows=50, world_index=0)
    assert set(np.unique(world["S"])).issubset({0.0, 1.0})
    trap = lib.simulate_dgp(scenario_id="NONSTATIONARY_TRAP", n_rows=50, world_index=0)
    slices = lib.era_slices(50)
    assert np.all(trap["beta"][slices["E1"]] == 0.30)
    assert np.all(trap["beta"][slices["E4"]] == 0.0)
    assert np.all(trap["beta"][slices["E5"]] == 0.0)


def test_candidate_definitions_and_taxonomy_partition():
    world = lib.simulate_dgp(scenario_id="EASY", n_rows=50, world_index=0)
    feats = lib.candidate_features(world)
    assert tuple(sorted(feats)) == tuple(sorted(lib.FEATURE_IDS))
    assert len(feats) == 10
    np.testing.assert_array_equal(feats["F03"], world["S"])
    assert feats["F01"][0] == 0.0
    np.testing.assert_array_equal(feats["F01"][1:], world["S"][:-1])
    np.testing.assert_array_equal(
        feats["F02"], world["S"] * (world["X1"] > 0.0).astype(np.float64)
    )
    np.testing.assert_array_equal(feats["F04"], (world["X1"] > 0.0).astype(np.float64))
    np.testing.assert_array_equal(feats["F07"], (world["X2"] < -1.0).astype(np.float64))
    np.testing.assert_array_equal(feats["F05"], (world["X2"] > 0.0).astype(np.float64))
    np.testing.assert_array_equal(feats["F06"], (world["X1"] > 1.0).astype(np.float64))
    np.testing.assert_array_equal(
        feats["F08"], world["S"] * (world["X2"] > 0.0).astype(np.float64)
    )
    np.testing.assert_array_equal(
        feats["F09"], ((world["X1"] + world["X2"]) > 0.0).astype(np.float64)
    )
    np.testing.assert_array_equal(
        feats["F10"], ((world["X1"] - world["X2"]) > 0.0).astype(np.float64)
    )
    true, proxy, false = lib.TRUE_FEATURES, lib.PROXY_FEATURES, lib.FALSE_FEATURES
    assert true | proxy | false == set(lib.FEATURE_IDS)
    assert not (true & proxy) and not (true & false) and not (proxy & false)
    assert lib.taxonomy_of("F03") == "TRUE_DISCOVERY"
    assert lib.taxonomy_of("F01") == "PROXY_DISCOVERY"
    assert lib.taxonomy_of("F10") == "FALSE_DISCOVERY"
    assert lib.taxonomy_of(None) == "NO_DISCOVERY"
    flags = lib.taxonomy_flags("TRUE_DISCOVERY")
    assert flags["USEFUL_DISCOVERY"] and flags["ANY_EDGE_DECLARED"]
    assert lib.taxonomy_flags("NO_DISCOVERY")["USEFUL_DISCOVERY"] is False


def test_chronology_no_lookahead():
    world = lib.simulate_dgp(scenario_id="EASY", n_rows=50, world_index=0)
    feature = lib.candidate_features(world)["F04"]
    preds = lib.expanding_era_predictions(
        world["Y"], world["X1"], world["X2"], feature, 50
    )
    slices = lib.era_slices(50)
    train_end = preds["train_end_by_score_era"]
    assert train_end["E2"] == slices["E2"].start
    assert train_end["E3"] == slices["E3"].start
    assert train_end["E5"] == slices["E5"].start
    assert np.all(np.isnan(preds["BASE_PRED"][slices["E1"]]))
    for era in ("E2", "E3", "E4", "E5"):
        assert np.all(np.isfinite(preds["BASE_PRED"][slices[era]]))


def test_chronology_future_era_mutation_does_not_change_earlier_scores():
    world = lib.simulate_dgp(scenario_id="EASY", n_rows=50, world_index=0)
    feature = lib.candidate_features(world)["F04"]
    y = world["Y"].copy()
    x1 = world["X1"].copy()
    x2 = world["X2"].copy()
    feat = feature.copy()
    first = lib.expanding_era_predictions(y, x1, x2, feat, 50)
    slices = lib.era_slices(50)
    y[slices["E5"]] = 1.0e6
    x1[slices["E4"]] = -1.0e6
    feat[slices["E3"]] = 1.0 - feat[slices["E3"]]
    second = lib.expanding_era_predictions(y, x1, x2, feat, 50)
    np.testing.assert_array_equal(
        first["BASE_PRED"][slices["E2"]], second["BASE_PRED"][slices["E2"]]
    )
    np.testing.assert_array_equal(
        first["CAND_PRED"][slices["E2"]], second["CAND_PRED"][slices["E2"]]
    )


def test_rank_failure_is_incomplete_not_dropped():
    n = 50
    y = np.arange(n, dtype=np.float64)
    x1 = np.ones(n, dtype=np.float64)
    x2 = np.ones(n, dtype=np.float64)
    with pytest.raises(lib.IncompleteWorld, match="full rank"):
        lib.expanding_era_predictions(y, x1, x2, np.ones(n), n)


def test_nonfinite_failure_is_incomplete():
    world = lib.simulate_dgp(scenario_id="EASY", n_rows=50, world_index=0)
    y = world["Y"].copy()
    y[0] = np.inf
    with pytest.raises(lib.IncompleteWorld):
        lib.expanding_era_predictions(y, world["X1"], world["X2"], world["S"], 50)


def test_metric_formulas():
    y = np.array([1.0, 3.0, 5.0, 7.0])
    base = np.array([0.0, 2.0, 4.0, 8.0])
    cand = np.array([1.0, 3.0, 4.0, 7.0])
    mask = np.array([True, True, True, True])
    out = lib.ae_metrics(y, base, cand, mask)
    base_ae = np.abs(y - base)
    cand_ae = np.abs(y - cand)
    assert out["MEAN_AE_IMPROVEMENT"] == pytest.approx(float(np.mean(base_ae - cand_ae)))
    assert out["RELATIVE_MAE_IMPROVEMENT"] == pytest.approx(
        1.0 - float(np.mean(cand_ae)) / float(np.mean(base_ae))
    )


def test_effective_support_n_truncation_and_cap():
    s = np.array([1.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0], dtype=np.float64)
    n_eff = lib.effective_support_n(s)
    n_pos = float(np.sum(s == 1.0))
    assert 1.0 <= n_eff <= n_pos
    empty = lib.effective_support_n(np.zeros(8))
    assert math.isnan(empty)
    ones = np.ones(12, dtype=np.float64)
    capped = lib.effective_support_n(ones)
    assert 1.0 <= capped <= 12.0
    alternating = np.array([1.0, 0.0] * 8, dtype=np.float64)
    rho1 = lib.sample_acf(alternating, 1)
    rho2 = lib.sample_acf(alternating, 2)
    n_eff_alt = lib.effective_support_n(alternating)
    n_pos_alt = float(np.sum(alternating == 1.0))
    if rho1 + rho2 <= 0.0:
        assert n_eff_alt == pytest.approx(n_pos_alt)
    else:
        assert 1.0 <= n_eff_alt <= n_pos_alt


def test_support_run_lengths_break_at_era_boundary():
    n = 50
    s = np.zeros(n, dtype=np.float64)
    s[9] = 1.0  # last row of E1; not scored
    s[10] = 1.0  # first scored row of E2
    s[19] = 1.0  # last row of E2
    s[20] = 1.0  # first row of E3; era boundary must break the run
    ae = np.zeros(n, dtype=np.float64)
    diag = lib.support_diagnostics(s, ae, lib.scored_mask(n), n)
    assert diag["N_positive"] == 3
    assert diag["SUPPORT_CLUSTER_COUNT"] == 3
    assert diag["SUPPORT_RUN_LENGTHS"] == (1, 1, 1)


def test_block_construction_retains_short_terminal_and_stays_in_era():
    blocks = lib.era_blocks(10, 4)
    assert [(b.start, b.stop) for b in blocks] == [(0, 4), (4, 8), (8, 10)]
    rng = lib.pcg64_generator(1)
    values = np.arange(10, dtype=np.float64)
    draw = lib.resample_era_rows(values, 4, rng)
    assert draw is None or len(draw) == 10


def test_visibility_invalid_replicate_fail_closed():
    residual = np.ones(50, dtype=np.float64)
    trigger = np.ones(50, dtype=np.float64)
    out = lib.visibility_from_residuals(
        residual,
        trigger,
        50,
        replicates=3,
        block_rows=5,
        rng=lib.pcg64_generator(3),
    )
    assert out["visibility_invalid"] is True
    assert out["GROUND_TRUTH_VISIBLE"] is False
    assert out["stays_in_denominator"] is True


def test_bootstrap_invalid_replicate_fail_closed():
    ae = np.full(50, np.nan, dtype=np.float64)
    out = lib.prediction_bootstrap(
        ae, 50, replicates=3, block_rows=5, rng=lib.pcg64_generator(4)
    )
    assert out["bootstrap_invalid"] is True
    assert out["bootstrap_positive"] is False
    assert out["world_invalid"] is True
    assert out["stays_in_denominator"] is True


def test_placebo_invalid_replicate_fail_closed():
    y = np.ones(50, dtype=np.float64)
    x1 = np.ones(50, dtype=np.float64)
    x2 = np.linspace(0.0, 1.0, 50)
    world = {"Y": y, "X1": x1, "X2": x2}
    out = lib.placebo_q95(
        world=world,
        feature=np.ones(50),
        n_rows=50,
        replicates=2,
        rng=lib.pcg64_generator(5),
    )
    assert out["placebo_invalid"] is True
    assert out["world_invalid"] is True
    assert out["stays_in_denominator"] is True


def test_no_reroll_on_invalid_bootstrap_length():
    for fn in (lib.prediction_bootstrap, lib.visibility_from_residuals, lib.placebo_q95):
        source = inspect.getsource(fn)
        assert "while" not in source
        assert "reroll" not in source


def test_gate_composition_and_two_percent_unchanged():
    era = {"E2": 0.1, "E3": 0.1, "E4": 0.1, "E5": -0.01}
    gates = lib.compose_gates(
        mean_ae_improvement=0.05,
        relative_mae_improvement=0.019999,
        bootstrap_positive=True,
        placebo_separation=True,
        era_improvements=era,
        candidate_positive_count=50,
    )
    assert gates["primary_positive"] is True
    assert gates["material_relative_mae"] is False
    assert gates["MODEL_DETECTED"] is True
    assert gates["era_stability"] is True
    assert gates["support_sanity"] is True
    assert gates["STRICT_PASS_EX_MATERIALITY"] is True
    assert gates["STRICT_PASS"] is False
    assert lib.MATERIALITY_GATE == 0.02
    gates2 = lib.compose_gates(
        mean_ae_improvement=0.05,
        relative_mae_improvement=0.02,
        bootstrap_positive=True,
        placebo_separation=True,
        era_improvements=era,
        candidate_positive_count=49,
    )
    assert gates2["support_sanity"] is False
    assert gates2["STRICT_PASS_EX_MATERIALITY"] is False


def test_blind_tie_break_ascending_feature_id():
    rows = [
        {
            "feature_id": "F05",
            "MEAN_AE_IMPROVEMENT": 0.4,
            "gates": {"STRICT_PASS_EX_MATERIALITY": True},
        },
        {
            "feature_id": "F02",
            "MEAN_AE_IMPROVEMENT": 0.4,
            "gates": {"STRICT_PASS_EX_MATERIALITY": True},
        },
        {
            "feature_id": "F03",
            "MEAN_AE_IMPROVEMENT": 0.3,
            "gates": {"STRICT_PASS_EX_MATERIALITY": True},
        },
    ]
    assert lib.select_blind(rows, gate="STRICT_PASS_EX_MATERIALITY") == "F02"
    none_rows = [
        {"feature_id": "F03", "MEAN_AE_IMPROVEMENT": 0.1, "gates": {"STRICT_PASS_EX_MATERIALITY": False}}
    ]
    assert lib.select_blind(none_rows, gate="STRICT_PASS_EX_MATERIALITY") == "NO_CANDIDATE"


def test_wilson_formula_and_threshold_straddling():
    k, n = 20, 400
    z = 1.959963984540054
    phat = k / n
    denom = 1.0 + z**2 / n
    center = (phat + z**2 / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt(phat * (1.0 - phat) / n + z**2 / (4.0 * n * n))
    interval = lib.wilson_interval(k, n)
    assert interval["center"] == pytest.approx(center)
    assert interval["lower"] == pytest.approx(center - half)
    assert interval["upper"] == pytest.approx(center + half)
    max_spec = interval["upper"]
    assert lib.specificity_verdict(interval, max_spec) == lib.PASS
    straddling_max = (interval["lower"] + interval["upper"]) / 2.0
    assert interval["lower"] <= straddling_max < interval["upper"]
    assert lib.specificity_verdict(interval, straddling_max) == lib.INDETERMINATE
    power_min = interval["lower"]
    assert lib.power_verdict(interval, power_min) == lib.PASS
    assert lib.power_verdict(interval, interval["upper"] + 0.1) == lib.FAIL
    inside = (interval["lower"] + interval["upper"]) / 2.0
    assert interval["lower"] < inside < interval["upper"]
    assert lib.power_verdict(interval, inside) == lib.INDETERMINATE
    high = lib.wilson_interval(80, 800)
    assert high["lower"] > 0.05
    assert lib.specificity_verdict(high, 0.05) == lib.FAIL
    low = lib.wilson_interval(8, 800)
    assert low["upper"] < 0.50
    assert lib.power_verdict(low, 0.50) == lib.FAIL


def test_indeterminate_precedence_three_states():
    shared = dict(
        incomplete_execution=False,
        trap_specificity=lib.PASS,
        easy_oracle_power=lib.PASS,
        moderate_oracle_power=lib.PASS,
        easy_blind_useful=lib.FAIL,
        moderate_blind_useful=lib.PASS,
    )
    a = lib.mechanical_conclusion(
        oracle_null_specificity=lib.PASS,
        blind_null_specificity=lib.PASS,
        **{**shared, "easy_oracle_power": lib.INDETERMINATE, "moderate_oracle_power": lib.PASS},
    )
    b = lib.mechanical_conclusion(
        oracle_null_specificity=lib.INDETERMINATE,
        blind_null_specificity=lib.PASS,
        **shared,
    )
    c = lib.mechanical_conclusion(
        oracle_null_specificity=lib.INDETERMINATE,
        blind_null_specificity=lib.PASS,
        **{**shared, "easy_oracle_power": lib.INDETERMINATE},
    )
    assert a == b == c == "CALIBRATION_INDETERMINATE"


def test_incomplete_execution_precedes_everything():
    label = lib.mechanical_conclusion(
        incomplete_execution=True,
        oracle_null_specificity=lib.FAIL,
        blind_null_specificity=lib.FAIL,
        trap_specificity=lib.FAIL,
        easy_oracle_power=lib.FAIL,
        moderate_oracle_power=lib.FAIL,
        easy_blind_useful=lib.FAIL,
        moderate_blind_useful=lib.FAIL,
    )
    assert label == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"


def test_discovery_bottleneck_requires_controlled_specificity_and_oracle_power():
    label = lib.mechanical_conclusion(
        incomplete_execution=False,
        oracle_null_specificity=lib.PASS,
        blind_null_specificity=lib.PASS,
        trap_specificity=lib.PASS,
        easy_oracle_power=lib.PASS,
        moderate_oracle_power=lib.PASS,
        easy_blind_useful=lib.FAIL,
        moderate_blind_useful=lib.PASS,
    )
    assert label == "DISCOVERY_BOTTLENECK_BEFORE_B2_06"
    no_edge = lib.mechanical_conclusion(
        incomplete_execution=False,
        oracle_null_specificity=lib.PASS,
        blind_null_specificity=lib.PASS,
        trap_specificity=lib.PASS,
        easy_oracle_power=lib.PASS,
        moderate_oracle_power=lib.PASS,
        easy_blind_useful=lib.PASS,
        moderate_blind_useful=lib.PASS,
    )
    assert no_edge == "NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK"


def test_production_execution_lock():
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="SYNTHETIC_EXECUTION_NOT_AUTHORIZED"):
        lib.run_frozen_production_grid()
    with pytest.raises(lib.SyntheticExecutionNotAuthorized):
        lib.run_frozen_production_grid(authorized=True)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized):
        lib.run_frozen_production_grid(worlds=1, n_rows=50)
    desc = lib.planned_production_grid_descriptor()
    assert desc["planned_total_worlds"] == 3200
    assert desc["callable"] is False
    assert runner.main(["--run-production-grid"]) == 2
    assert runner.main([]) == 2
    identity = json.loads(
        subprocess.check_output(
            [
                sys.executable,
                "-m",
                "scripts.research.harness_synthetic_edge_calibration_v1",
                "--identity",
            ],
            cwd=REPO,
            text=True,
        )
    )
    assert identity["synthetic_execution_authorized"] is False
    assert identity["production_calibration_executed"] is False
    assert identity["real_data_path"] is False
    source = Path(lib.__file__).read_text(encoding="utf-8") + Path(runner.__file__).read_text(
        encoding="utf-8"
    )
    for token in ("--authorize", "--force", "--unsafe", "getenv", "authorized=True"):
        assert token not in source


def test_fixture_envelope_rejects_near_production_and_accepts_tiny():
    accepted = _tiny()
    assert accepted.n_rows == 50
    lib.FixtureExecutionConfig(
        n_rows=500,
        scenario_id="EASY",
        visibility_replicates=50,
        bootstrap_replicates=50,
        placebo_replicates=50,
        block_rows=5,
    )
    rejected = [
        {
            "n_rows": 5000,
            "scenario_id": "EASY",
            "visibility_replicates": 500,
            "bootstrap_replicates": 500,
            "placebo_replicates": 999,
            "block_rows": 50,
        },
        {
            "n_rows": 5000,
            "scenario_id": "EASY",
            "visibility_replicates": 499,
            "bootstrap_replicates": 500,
            "placebo_replicates": 999,
        },
        {
            "n_rows": 5000,
            "scenario_id": "EASY",
            "visibility_replicates": 500,
            "bootstrap_replicates": 500,
            "placebo_replicates": 998,
        },
        {
            "n_rows": 5000,
            "scenario_id": "EASY",
            "visibility_replicates": 500,
            "bootstrap_replicates": 499,
            "placebo_replicates": 999,
        },
        {
            "n_rows": 5005,
            "scenario_id": "EASY",
            "visibility_replicates": 500,
            "bootstrap_replicates": 500,
            "placebo_replicates": 999,
        },
        {
            "n_rows": 5005,
            "scenario_id": "EASY",
            "visibility_replicates": 3,
            "bootstrap_replicates": 3,
            "placebo_replicates": 3,
        },
        {
            "n_rows": 2500,
            "scenario_id": "EASY",
            "visibility_replicates": 3,
            "bootstrap_replicates": 3,
            "placebo_replicates": 3,
        },
        {
            "n_rows": 10000,
            "scenario_id": "EASY",
            "visibility_replicates": 3,
            "bootstrap_replicates": 3,
            "placebo_replicates": 3,
        },
        {
            "n_rows": 50,
            "scenario_id": "EASY",
            "visibility_replicates": 51,
            "bootstrap_replicates": 3,
            "placebo_replicates": 3,
        },
        {
            "n_rows": 50,
            "scenario_id": "EASY",
            "visibility_replicates": 3,
            "bootstrap_replicates": 51,
            "placebo_replicates": 3,
        },
        {
            "n_rows": 50,
            "scenario_id": "EASY",
            "visibility_replicates": 3,
            "bootstrap_replicates": 3,
            "placebo_replicates": 51,
        },
    ]
    for params in rejected:
        with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="SYNTHETIC_EXECUTION_NOT_AUTHORIZED"):
            lib.FixtureExecutionConfig(**params)


def test_no_real_data_path():
    source = Path(lib.__file__).read_text(encoding="utf-8") + Path(runner.__file__).read_text(
        encoding="utf-8"
    )
    for token in (
        "parquet",
        "CORE_BTC",
        "authorize_dataset",
        "outcome_access_acknowledged",
        "prepare_batch02",
        "b2_06_evaluator",
    ):
        assert token not in source
    ident = lib.implementation_identity()
    assert ident["b2_06_scientific_execution_authorized"] is False
    assert ident["validation_2025_authorized"] is False
    assert ident["oos_2026_authorized"] is False


def test_fixture_world_stays_in_denominator_and_is_deterministic():
    cfg = _tiny()
    a = lib.evaluate_fixture_world(cfg)
    b = lib.evaluate_fixture_world(cfg)
    assert a["stays_in_denominator"] is True
    assert a["world_identity"] == b["world_identity"]
    assert a["selected_STRICT_PASS_EX_MATERIALITY"] == b["selected_STRICT_PASS_EX_MATERIALITY"]
    assert len(a["candidates"]) == 10
    assert a["taxonomy"] in {
        "TRUE_DISCOVERY",
        "PROXY_DISCOVERY",
        "FALSE_DISCOVERY",
        "NO_DISCOVERY",
    }


def test_visibility_invalid_does_not_invalidate_candidate_or_world(monkeypatch):
    n = 50
    world = _rank_safe_world(n)
    world = dict(world)
    world["S"] = np.ones(n, dtype=np.float64)
    world["Y"] = (0.20 * world["X1"] - 0.15 * world["X2"] + 0.25 * world["S"]).astype(np.float64)
    ev = lib.evaluate_fixture_candidate(world, "F04", _tiny())
    vis = ev.payload["visibility"]
    assert vis["visibility_invalid"] is True
    assert vis["GROUND_TRUTH_VISIBLE"] is False
    assert ev.valid is True
    assert "visibility_invalid" not in ev.invalid_reasons
    assert "GROUND_TRUTH_VISIBLE" not in ev.payload["gates"]
    assert ev.payload["gates"]["bootstrap_positive"] in {True, False}

    monkeypatch.setattr(lib, "simulate_dgp", lambda **kwargs: _rank_safe_world(kwargs["n_rows"]))
    monkeypatch.setattr(
        lib,
        "visibility_from_residuals",
        lambda *args, **kwargs: {
            "GROUND_TRUTH_VISIBLE": False,
            "visibility_invalid": True,
            "visibility_q025": float("nan"),
            "stays_in_denominator": True,
        },
    )
    out = lib.evaluate_fixture_world(_tiny())
    assert all(row["visibility"]["visibility_invalid"] for row in out["candidates"])
    assert all(row["visibility"]["GROUND_TRUTH_VISIBLE"] is False for row in out["candidates"])
    assert out["valid"] is True
    assert out["incomplete_execution"] is False
    assert "visibility_invalid" not in out["invalid_reasons"]
    assert out["selected_STRICT_PASS_EX_MATERIALITY"] in (*lib.FEATURE_IDS, "NO_CANDIDATE")


def test_bootstrap_invalidity_still_invalidates_world(monkeypatch):
    monkeypatch.setattr(lib, "simulate_dgp", lambda **kwargs: _rank_safe_world(kwargs["n_rows"]))
    monkeypatch.setattr(
        lib,
        "prediction_bootstrap",
        lambda *args, **kwargs: {
            "bootstrap_positive": False,
            "bootstrap_invalid": True,
            "bootstrap_q025": float("nan"),
            "world_invalid": True,
            "stays_in_denominator": True,
        },
    )
    out = lib.evaluate_fixture_world(_tiny())
    assert out["valid"] is False
    assert out["incomplete_execution"] is True
    assert "bootstrap_invalid" in out["invalid_reasons"]
    assert out["stays_in_denominator"] is True


def test_placebo_invalidity_still_invalidates_world(monkeypatch):
    monkeypatch.setattr(lib, "simulate_dgp", lambda **kwargs: _rank_safe_world(kwargs["n_rows"]))
    monkeypatch.setattr(
        lib,
        "placebo_q95",
        lambda *args, **kwargs: {
            "placebo_q95": float("nan"),
            "placebo_invalid": True,
            "world_invalid": True,
            "stays_in_denominator": True,
        },
    )
    out = lib.evaluate_fixture_world(_tiny())
    assert out["valid"] is False
    assert out["incomplete_execution"] is True
    assert "placebo_invalid" in out["invalid_reasons"]
    assert out["stays_in_denominator"] is True


def test_invalid_candidate_remains_in_planned_denominator():
    n = 50
    world = {
        "Y": np.ones(n, dtype=np.float64),
        "X1": np.ones(n, dtype=np.float64),
        "X2": np.ones(n, dtype=np.float64),
        "S": np.zeros(n, dtype=np.float64),
        "world_identity": "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1|EASY|50|0",
    }
    ev = lib.evaluate_fixture_candidate(world, "F04", _tiny())
    assert ev.valid is False
    assert ev.stays_in_denominator is True
    assert ev.invalid_reasons


def test_materiality_fraction_unavailable_when_denominator_nonpositive():
    assert math.isnan(lib.materiality_fraction_of_attainable(0.01, 0.0))
    assert lib.materiality_fraction_of_attainable(0.005, 0.0107) == pytest.approx(
        0.005 / 0.0107
    )


def test_dgp_locked_tiny_world_bytes():
    world = lib.simulate_dgp(scenario_id="EASY", n_rows=50, world_index=0)
    digest = hashlib.sha256(np.ascontiguousarray(world["Y"]).tobytes()).hexdigest()
    rerun = lib.simulate_dgp(scenario_id="EASY", n_rows=50, world_index=0)
    assert hashlib.sha256(np.ascontiguousarray(rerun["Y"]).tobytes()).hexdigest() == digest
    assert digest == "59978d055ae443edc2df33c4a396678db52120be679cfc09e3f21bbfa393635c"


def test_production_n_not_used_as_fixture_default():
    cfg = _tiny()
    assert cfg.n_rows not in {2500, 5000, 10000}
    assert cfg.bootstrap_replicates != 500
    assert cfg.placebo_replicates != 999
    assert lib.PRODUCTION_PRIMARY_N == 5000
    assert lib.PRODUCTION_BOOTSTRAP_REPLICATES == 500
    assert lib.PRODUCTION_PLACEBO_REPLICATES == 999
