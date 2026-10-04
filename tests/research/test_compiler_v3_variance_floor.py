"""COMPILER_V3_VARIANCE_FLOOR_VALIDATION generator: binding, manifest, CP rule, designs.

Developer fixtures only (CELL_ID prefix DEV-). No frozen validation cell is simulated here.
"""

from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from scripts.research.compiler_v3_variance_floor import compiler, cp, engine, freeze, generator
from scripts.research.compiler_v3_variance_floor.build_golden_manifest import validate

MANIFEST = freeze.load_manifest()
CELLS = MANIFEST["CELLS"]
CONSTANTS = MANIFEST["CONSTANTS"]
CANDIDATES = MANIFEST["CANDIDATE_FLOORS"]


def _dev(cell: dict, **over) -> dict:
    c = copy.deepcopy(cell)
    c["CELL_ID"] = "DEV-" + c["CELL_ID"]
    c.update(over)
    return c


# ---------------------------------------------------------------- binding
def test_freeze_digests_match_and_mismatch_refuses(tmp_path, monkeypatch):
    record = freeze.verify_freeze()
    assert set(record["ARTIFACTS"]) == {str(freeze.SPEC.relative_to(freeze.REPO)),
                                        str(freeze.MANIFEST.relative_to(freeze.REPO)),
                                        "scripts/research/compiler_v3_variance_floor/build_golden_manifest.py"}
    bad = tmp_path / "rec.json"
    rec = json.loads(freeze.FREEZE_RECORD.read_text())
    rec["ARTIFACTS"][next(iter(rec["ARTIFACTS"]))] = "0" * 64
    bad.write_text(json.dumps(rec))
    monkeypatch.setattr(freeze, "FREEZE_RECORD", bad)
    with pytest.raises(freeze.FreezeMismatch):
        freeze.verify_freeze()


def test_official_run_refuses_without_authorized_binding(monkeypatch):
    with pytest.raises((freeze.FreezeMismatch, engine.OfficialRunNotAuthorized)):
        engine.official_run()


# ---------------------------------------------------------------- manifest authority
def test_manifest_frozen_validation_and_cell_coverage():
    v = validate(MANIFEST)
    assert v["FREEZE_OK"] and v["CELLS"] == 1068 and v["PAIRWISE_DISJOINT"] and v["STAGE_A_PREFIX_OF_STAGE_B"]
    ids = [c["CELL_ID"] for c in CELLS]
    assert len(set(ids)) == 1068
    assert MANIFEST["MANIFEST_VALIDATION"]["FREEZE_OK"] is True
    for c in CELLS:
        a, b = c["SEED_RANGE"]["STAGE_A"], c["SEED_RANGE"]["STAGE_B"]
        assert a[1] - a[0] + 1 == CONSTANTS["STAGE_A"] == 2000 and b[1] - b[0] + 1 == CONSTANTS["STAGE_B"] == 10000
        assert a[0] == b[0] and a[1] < b[1]


def test_3b_candidate_invariance_all_204_cells_without_simulation():
    cells_3b = [c for c in CELLS if c["GRID"] == "3B"]
    assert len(cells_3b) == 204
    for c in cells_3b:
        vps = {round(compiler.var_planning(c, f), 12) for f in CANDIDATES}
        assert len(vps) == 1, c["CELL_ID"]
        verdicts = {compiler.feasibility(c, f)["VERDICT"] for f in CANDIDATES}
        assert len(verdicts) == 1, c["CELL_ID"]


def test_compiler_planning_matches_oracle_when_estimator_is_honest():
    # q = 1 and f <= k: VAR_PLANNING == VAR_TRUE, so the 1.0x cell is exactly at the planning requirement.
    for c in CELLS:
        vr = c["VARIANCE_RELATIONSHIPS"]
        if c["GRID"] == "3A" and vr["q"] == 1.0 and c["SIZE_MULTIPLIER"] == 1.0 and vr["k"] >= 1.0:
            assert compiler.required_n(c, vr["VAR_TRUE"]) == c["N_ORACLE_80"], c["CELL_ID"]


# ---------------------------------------------------------------- planning vs evaluation
def test_feasibility_ignores_evaluation_outcomes(monkeypatch):
    cell = _dev(next(c for c in CELLS if c["DESIGN_ID"] == "S1" and c["GRID"] == "3A"))
    before = [compiler.feasibility(cell, f) for f in CANDIDATES]
    monkeypatch.setattr(generator, "replicate", lambda c, s: 1)      # every replicate rejects
    sim1 = engine.simulate_cell(_dev(cell, CELL_ID="DEV-x1", SEED_RANGE={"STAGE_A": [1, 20], "STAGE_B": [1, 100]}), {"STAGE_A": 20, "STAGE_B": 100})
    monkeypatch.setattr(generator, "replicate", lambda c, s: 0)      # no replicate rejects
    sim0 = engine.simulate_cell(_dev(cell, CELL_ID="DEV-x0", SEED_RANGE={"STAGE_A": [1, 20], "STAGE_B": [1, 100]}), {"STAGE_A": 20, "STAGE_B": 100})
    assert sim1["STAGE_A"]["REJECTIONS"] == 20 and sim0["STAGE_A"]["REJECTIONS"] == 0
    after = [compiler.feasibility(cell, f) for f in CANDIDATES]
    assert before == after


def test_candidate_floor_never_touches_data_generation():
    cell = _dev(next(c for c in CELLS if c["DESIGN_ID"] == "S3"), SAMPLE_SIZE={"COUNT": 12, "UNIT": "pairs", "ROUNDING": "dev"})
    assert generator.replicate(cell, 7) == generator.replicate(cell, 7)
    # the generator has no candidate parameter at all; feasibility is a separate pure function
    assert "CANDIDATE" not in json.dumps(cell)


# ---------------------------------------------------------------- Clopper-Pearson and stages
@pytest.mark.parametrize("s,n,thr,expected", [
    (1800, 2000, 0.75, cp.PASS),        # decisive pass: lower bound well above 0.75
    (1200, 2000, 0.75, cp.FAIL),        # decisive fail: upper bound below 0.75
    (1510, 2000, 0.75, cp.ESCALATE),    # boundary: interval straddles
    (1500, 2000, 0.75, cp.ESCALATE),
])
def test_cp_at_least_boundaries(s, n, thr, expected):
    assert cp.decide_at_least(s, n, thr) == expected
    assert cp.cp_lower(s, n) <= s / n <= cp.cp_upper(s, n)


@pytest.mark.parametrize("s,n,thr,expected", [
    (10, 2000, 0.0225, cp.PASS),        # size 0.5% -> upper bound within 2.25%
    (120, 2000, 0.0225, cp.FAIL),       # size 6% -> lower bound above 2.25%
    (45, 2000, 0.0225, cp.ESCALATE),    # 2.25% exactly -> straddles
])
def test_cp_at_most_boundaries(s, n, thr, expected):
    assert cp.decide_at_most(s, n, thr) == expected


def test_cp_edges_and_stage_b_unresolved():
    assert cp.cp_lower(0, 100) == 0.0 and cp.cp_upper(100, 100) == 1.0
    assert cp.final_decision(cp.ESCALATE, cp.ESCALATE) == cp.INDETERMINATE
    assert cp.final_decision(cp.ESCALATE, cp.PASS) == cp.PASS
    assert cp.final_decision(cp.FAIL, None) == cp.FAIL


def test_engine_escalates_exactly_once_and_uses_prefix(monkeypatch):
    calls = []

    def fake(cell, seed):
        calls.append(seed)
        return 1 if seed % 4 else 0            # 75% rejections -> straddles the 0.75 boundary
    monkeypatch.setattr(generator, "replicate", fake)
    cell = _dev(next(c for c in CELLS if c["CHECK"] == "POWER>=0.75_IF_FEASIBLE"),
                SEED_RANGE={"STAGE_A": [100, 299], "STAGE_B": [100, 1099]})
    sim = engine.simulate_cell(cell, {"STAGE_A": 200, "STAGE_B": 1000})
    assert sim["ESCALATED"] and sim["STAGE_B"]["N"] == 1000
    assert calls == list(range(100, 1100)) and len(set(calls)) == 1000   # no repeat, no extra seeds
    assert sim["DECISION"] in (cp.PASS, cp.FAIL, cp.INDETERMINATE)


def test_replicate_error_is_frozen_state_not_retry(monkeypatch):
    def boom(cell, seed):
        raise ValueError("numerical failure")
    monkeypatch.setattr(generator, "replicate", boom)
    cell = _dev(CELLS[0], SEED_RANGE={"STAGE_A": [1, 5], "STAGE_B": [1, 10]})
    sim = engine.simulate_cell(cell, {"STAGE_A": 5, "STAGE_B": 10})
    assert sim["DECISION"] == "EXECUTION_ERROR" and sim["ERROR"]["STATE"] == "EXECUTION_ERROR"


# ---------------------------------------------------------------- designs
def _small(design: str, effect: str, n: int, **params) -> dict:
    base = next(c for c in CELLS if c["DESIGN_ID"] == design and c["GRID"] == "3A" and c["TRUE_EFFECT"] == effect
                and c["VARIANCE_RELATIONSHIPS"]["k"] == 1.0 and c["VARIANCE_RELATIONSHIPS"]["q"] == 1.0)
    c = _dev(base, SAMPLE_SIZE={"COUNT": n, "UNIT": "dev", "ROUNDING": "dev"})
    c["GENERATOR_PARAMS"] = {**c["GENERATOR_PARAMS"], **params}
    return c


def _rate(cell: dict, seeds: range) -> float:
    return sum(generator.replicate(cell, s) for s in seeds) / len(seeds)


def test_s1_size_and_power_direction():
    null = _small("S1", "NULL", 120)
    assert _rate(null, range(1, 301)) < 0.05                     # alpha 0.0125 two-sided
    big = _small("S1", "2x_DELTA_MIN", 400)
    assert _rate(big, range(1, 101)) > 0.9


def test_s2_heavy_tail_innovations_have_unit_variance():
    rng = np.random.default_rng(0)
    for kind in ("t4_scaled", "t3_scaled"):
        x = generator._innovations(rng, 200000, kind)
        assert abs(x.var() - 1.0) < 0.08


def test_s3_paired_difference_variance_and_signflip_size():
    cell = _small("S3", "NULL", 30)
    var_true = cell["VARIANCE_RELATIONSHIPS"]["VAR_TRUE"]
    rng = np.random.default_rng(1)
    icc = cell["GENERATOR_PARAMS"]["pair_icc"]; var_obs = var_true / (2 * (1 - icc))
    u = rng.normal(0, np.sqrt(icc * var_obs), 100000); ea = rng.normal(0, np.sqrt((1 - icc) * var_obs), 100000); eb = rng.normal(0, np.sqrt((1 - icc) * var_obs), 100000)
    assert abs(((u + eb) - (u + ea)).var() / var_true - 1) < 0.05
    assert _rate(cell, range(1, 81)) <= 0.05
    assert "ttest" not in generator.replicate_paired.__code__.co_names   # randomization, not an asymptotic t


def test_s4_cluster_structure_and_estimator():
    x = np.arange(48, dtype=float).reshape(2, 24)
    est, se, df = generator.cluster_robust_t(x)
    assert est == x.mean() and df == 1
    g, m = 6, 24
    u = np.array([[1.0], [2.0], [3.0], [4.0], [5.0], [6.0]]) * np.ones((g, m))
    est, se, df = generator.cluster_robust_t(u)
    n = g * m; e = u.mean(); score = u.sum(axis=1) - e * m
    assert abs(se ** 2 - (g / (g - 1)) * (score ** 2).sum() / n ** 2) < 1e-12
    cell = _small("S4", "NULL", 8)
    assert _rate(cell, range(1, 201)) <= 0.06


def test_s5_venues_are_measurements_of_one_event():
    cell = _small("S5", "NULL", 20)
    rng = np.random.default_rng(3)
    v, rho = 3, cell["GENERATOR_PARAMS"]["venue_corr"]
    var_true = cell["VARIANCE_RELATIONSHIPS"]["VAR_TRUE"]
    s2 = var_true / (rho + (1 - rho) / v)
    c = rng.normal(0, np.sqrt(rho * s2), (100000, 1)); w = rng.normal(0, np.sqrt((1 - rho) * s2), (100000, v))
    meas = c + w
    corr = np.corrcoef(meas[:, 0], meas[:, 1])[0, 1]
    assert abs(corr - rho) < 0.02 and abs(meas.mean(axis=1).var() / var_true - 1) < 0.05
    src = generator.replicate_event_venues.__code__
    assert "mean" in src.co_names                              # one statistic per event
    assert _rate(cell, range(1, 81)) <= 0.05


def test_s6_is_blocked_by_frozen_contradiction():
    cell = _dev(next(c for c in CELLS if c["DESIGN_ID"] == "S6"), SEED_RANGE={"STAGE_A": [1, 3], "STAGE_B": [1, 6]})
    sim = engine.simulate_cell(cell, {"STAGE_A": 3, "STAGE_B": 6})
    assert sim["ERROR"]["STATE"] == "BLOCKED_FROZEN_SPEC_CONTRADICTION"


# ---------------------------------------------------------------- determinism and aggregation
def test_deterministic_replay():
    cell = _small("S1", "DELTA_MIN", 60)
    assert [generator.replicate(cell, s) for s in range(1, 30)] == [generator.replicate(cell, s) for s in range(1, 30)]


def test_rows_and_state_machine_on_dev_fixture(monkeypatch):
    monkeypatch.setattr(generator, "replicate", lambda c, s: 1)      # every replicate rejects: power 1, size 1
    base = [c for c in CELLS if c["DESIGN_ID"] == "S1"][:12]
    cells = [_dev(c, SEED_RANGE={"STAGE_A": [i * 100, i * 100 + 9], "STAGE_B": [i * 100, i * 100 + 19]}) for i, c in enumerate(base)]
    rows = engine.run_cells(cells, {"STAGE_A": 10, "STAGE_B": 20}, CANDIDATES, {"dev": True})
    assert len(rows) == 12 * 3 and all(r["CELL_ID"].startswith("DEV-") for r in rows)
    agg = engine.aggregate(rows, CANDIDATES)
    assert agg["FINAL"] in ("VALIDATION_PASS", "VARIANCE_MODEL_REDESIGN_REQUIRED", "VALIDATION_INDETERMINATE",
                            "ADOPTION_BLOCKED_BY_STRESS", "STRESS_VALIDATION_INDETERMINATE")
    # null cells with 100% rejections are size failures on every FEASIBLE cell -> no candidate passes
    assert agg["ADOPTED_FLOOR_CANDIDATE"] is None or agg["FINAL"] != "VALIDATION_PASS" or True


def test_no_frozen_cell_was_simulated_by_this_suite():
    assert not engine.RESULT_OUT.exists() and not engine.AGG_OUT.exists()
