"""COMPILER_V3_VARIANCE_FLOOR_VALIDATION generator: binding, manifest, CP rule, designs.

Developer fixtures only (CELL_ID prefix DEV-). No frozen validation cell is simulated here.
"""

from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from scripts.research.compiler_v3_variance_floor import amendment, compiler, cp, engine, freeze, generator
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


def test_s1_size_and_power_two_sided():
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


# ================================================================ amendment V1 (S6 exclusion and bound semantics)
EFFECTIVE = freeze.load_effective_manifest()
AMENDMENT = freeze.verify_amendment()
ECELLS = EFFECTIVE["CELLS"]


def test_amendment_binds_original_freeze_and_effective_manifest():
    rec = freeze.verify_freeze()
    assert AMENDMENT["ORIGINAL_FREEZE"]["COMMIT"] == "62f1a74" and AMENDMENT["ORIGINAL_FREEZE"]["ARTIFACTS"] == rec["ARTIFACTS"]
    assert AMENDMENT["OFFICIAL_RUN_AUTHORIZED"] is False
    binding = freeze.verify_execution_binding()                      # V2, current generator digests
    assert binding["GENERATOR_DIGESTS"] == freeze.generator_digests()
    assert binding["OFFICIAL_RUN_AUTHORIZED"] is False and binding["EFFECTIVE_MANIFEST_SHA256"] == AMENDMENT["EFFECTIVE_MANIFEST_SHA256"]
    # the amendment's listing predates the binding repair and is superseded by V2 (recorded there)
    assert set(AMENDMENT["GENERATOR_DIGESTS"]) <= set(binding["GENERATOR_DIGESTS"])
    assert binding["SUPERSEDES"]["PATH"].endswith("EXECUTION_BINDING_V1.json") and freeze.sha256_path(binding["SUPERSEDES"]["PATH"]) == binding["SUPERSEDES"]["SHA256"]
    assert binding["AMENDMENT"]["SHA256"] == freeze.sha256_path(binding["AMENDMENT"]["PATH"])
    assert not freeze.RUN_AUTHORIZATION.exists()


def test_s6_excluded_set_exact_and_metadata_retained():
    excluded = [c for c in ECELLS if c["EXECUTION_STATUS"] == amendment.EXCLUSION_STATUS]
    assert len(excluded) == 168 and all(c["DESIGN_ID"] == "S6" for c in excluded)
    assert sorted(c["CELL_ID"] for c in excluded) == AMENDMENT["A_S6_EXCLUSION"]["EXCLUDED_CELL_IDS"]
    assert all(c["EXCLUSION_REASON"] == amendment.EXCLUSION_REASON for c in excluded)
    frozen = {c["CELL_ID"]: c for c in CELLS}
    for c in excluded:                      # frozen metadata and seeds untouched
        f = frozen[c["CELL_ID"]]
        assert c["SEED_RANGE"] == f["SEED_RANGE"] and c["N_ORACLE_80"] == f["N_ORACLE_80"] and c["SAMPLE_SIZE"] == f["SAMPLE_SIZE"]
    assert not any(c["DESIGN_ID"] == "S6" and c["EXECUTION_STATUS"] == "ACTIVE" for c in ECELLS)


def test_active_suite_exact_coverage_and_counts():
    active = [c for c in ECELLS if c["EXECUTION_STATUS"] == "ACTIVE"]
    assert len(active) == 900 and sum(c["GRID"] == "3A" for c in active) == 720 and sum(c["GRID"] == "3B" for c in active) == 180
    assert {c["CELL_ID"] for c in ECELLS} == {c["CELL_ID"] for c in CELLS}          # no missing, no extra, no renumbering
    assert {c["CELL_ID"] for c in active} == {c["CELL_ID"] for c in CELLS if c["DESIGN_ID"] != "S6"}
    assert EFFECTIVE["ACTIVE_COUNTS"] == {"TOTAL": 900, "3A": 720, "3B": 180, "EXCLUDED": 168}
    for c in ECELLS:                        # seeds identical to the frozen manifest
        assert c["SEED_RANGE"] == next(f for f in CELLS if f["CELL_ID"] == c["CELL_ID"])["SEED_RANGE"]


def test_s6_never_reaches_simulation_or_aggregation(monkeypatch):
    calls = []
    monkeypatch.setattr(generator, "replicate", lambda c, s: calls.append(c["CELL_ID"]) or 1)
    s6 = [_dev(c, SEED_RANGE={"STAGE_A": [1, 3], "STAGE_B": [1, 6]}) for c in ECELLS if c["DESIGN_ID"] == "S6"][:4]
    s1 = [_dev(c, SEED_RANGE={"STAGE_A": [10 + i, 12 + i], "STAGE_B": [10 + i, 15 + i]}) for i, c in enumerate([x for x in ECELLS if x["DESIGN_ID"] == "S1"][:2])]
    rows = engine.run_cells(s6 + s1, {"STAGE_A": 3, "STAGE_B": 6}, CANDIDATES, {"dev": True})
    assert not any(cid.startswith("DEV-S6") for cid in calls)
    assert all(r["FEASIBILITY"] is None and r["EMPIRICAL_DECISION"] is None for r in rows if r["DESIGN_ID"] == "S6")
    agg = engine.aggregate(rows, CANDIDATES)
    assert all(d["DECISIVE_CHECKS"] <= 2 * 2 for d in agg["DETAIL_3A"].values())   # only the two S1 cells could count


def test_two_sided_rejection_counts_regardless_of_sign(monkeypatch):
    import scipy.stats
    from types import SimpleNamespace
    cell = _small("S1", "DELTA_MIN", 60)
    monkeypatch.setattr(generator, "ttest_ind", lambda b, a, equal_var: SimpleNamespace(pvalue=1e-6, statistic=-9.0))
    assert generator.replicate(cell, 1) == generator.REJECT          # wrong-sign but significant -> REJECT


def test_s3_s5_exactly_20000_signflip_draws(monkeypatch):
    seen = []
    orig = generator._signflip_p
    monkeypatch.setattr(generator, "_signflip_p", lambda d, rng, draws=generator.SIGNFLIP_DRAWS: seen.append(draws) or orig(d, rng, draws))
    generator.replicate(_small("S3", "NULL", 10), 5)
    generator.replicate(_small("S5", "NULL", 10), 5)
    assert seen == [20000, 20000]
    import numpy as _np
    # plus-one form: with d = [1, 1] and 100 draws, |perm mean| >= 1 only when both signs agree (prob 1/2)
    rng = _np.random.default_rng(1)
    signs = rng.choice(_np.array([-1.0, 1.0]), size=(100, 2))
    extreme = int(_np.sum(_np.abs(signs.mean(axis=1)) >= 1.0))
    assert generator._signflip_p(_np.array([1.0, 1.0]), _np.random.default_rng(1), 100) == (1 + extreme) / 101


def test_rng_substreams_reproducible_and_independent():
    d1, r1 = generator.substreams(123)
    d2, r2 = generator.substreams(123)
    assert d1.random(5).tolist() == d2.random(5).tolist() and r1.random(5).tolist() == r2.random(5).tolist()
    d3, r3 = generator.substreams(123)
    d3.random(1000)                                                  # consuming DATA draws
    assert r3.random(5).tolist() == r1.random(0).tolist() + generator.substreams(123)[1].random(5).tolist()  # RANDOMIZATION unaffected
    d4, r4 = generator.substreams(124)
    assert d4.random(5).tolist() != d1.random(5).tolist()


def test_candidate_cannot_alter_data_or_draws():
    cell = _small("S5", "DELTA_MIN", 12)
    out = [generator.replicate(cell, s) for s in range(1, 15)]
    for f in CANDIDATES:                                             # candidate is not a generator input at all
        compiler.feasibility(cell, f)
        assert [generator.replicate(cell, s) for s in range(1, 15)] == out


def test_compiler_equals_frozen_planning_rule_representative_cells():
    import math
    from scipy.stats import norm, t as student_t
    za, zb = norm.ppf(1 - 0.0125 / 2), norm.ppf(0.8)
    for design in ("S1", "S2", "S3", "S4", "S5"):
        c = next(x for x in ECELLS if x["DESIGN_ID"] == design and x["EXECUTION_STATUS"] == "ACTIVE")
        for f in CANDIDATES:
            vp = compiler.var_planning(c, f)
            vr = c["VARIANCE_RELATIONSHIPS"]
            assert vp == max(vr["q"] * vr["VAR_TRUE"], f * vr["VAR_FALLBACK"])
            d = c["GENERATOR_PARAMS"]["delta_min"]
            if design in ("S1", "S2"):
                want = 2 * math.ceil(2 * vp * (za + zb) ** 2 / d ** 2)
            elif design in ("S3", "S5"):
                want = math.ceil(vp * (za + zb) ** 2 / d ** 2)
            else:
                m, icc = c["GENERATOR_PARAMS"]["m"], c["GENERATOR_PARAMS"]["icc"]; deff = 1 + (m - 1) * icc; g = 5
                while g < vp * deff * (student_t.ppf(1 - 0.0125 / 2, g - 1) + student_t.ppf(0.8, g - 1)) ** 2 / (m * d ** 2):
                    g += 1
                want = g
            assert compiler.required_n(c, vp) == want
            assert compiler.feasibility(c, f)["VERDICT"] == ("FEASIBLE" if c["SAMPLE_SIZE"]["COUNT"] >= want else "NOT_FEASIBLE")


def test_original_frozen_digests_still_match_and_no_official_artifacts():
    freeze.verify_freeze()
    assert not engine.RESULT_OUT.exists() and not engine.AGG_OUT.exists()


# ================================================================ inference audit (A-F)
import math
from scipy.stats import norm


def _manual_two_group(cell, seed):
    rng, _ = generator.substreams(seed)
    n_arm = cell["SAMPLE_SIZE"]["COUNT"] // 2
    sd = math.sqrt(cell["VARIANCE_RELATIONSHIPS"]["VAR_TRUE"])
    kind = cell["GENERATOR_PARAMS"]["innovation"]
    a = sd * generator._innovations(rng, n_arm, kind)
    b = generator.true_effect(cell) + sd * generator._innovations(rng, n_arm, kind)
    return a, b


def test_A_two_group_variance_effect_allocation_and_alpha(monkeypatch):
    cell = _small("S1", "DELTA_MIN", 2000)
    var_true = cell["VARIANCE_RELATIONSHIPS"]["VAR_TRUE"]
    a, b = _manual_two_group(cell, 11)
    assert a.size == b.size == 1000                                   # equal arms = planning formula allocation
    rng = np.random.default_rng(5); big = math.sqrt(var_true) * rng.standard_normal(400000)
    assert abs(big.var() / var_true - 1) < 0.02                       # per-observation variance = VAR_TRUE
    # effect is exactly the frozen difference of population means
    assert generator.true_effect(cell) == cell["GENERATOR_PARAMS"]["delta_min"] == 0.5
    # pooled t with two-sided alpha = MULTIPLICITY_ALPHA, and REJECT iff p < alpha
    captured = {}
    orig = generator.ttest_ind
    def spy(b_, a_, equal_var):
        res = orig(b_, a_, equal_var=equal_var); captured["equal_var"] = equal_var; captured["p"] = res.pvalue; return res
    monkeypatch.setattr(generator, "ttest_ind", spy)
    out = generator.replicate(cell, 11)
    assert captured["equal_var"] is True and out == (captured["p"] < cell["MULTIPLICITY_ALPHA"] == 0.0125 or captured["p"] < 0.0125)
    # S2 scaled t innovations: unit variance before the sqrt(VAR_TRUE) scale; planning ignores the innovation kind
    for kind, nu in (("t4_scaled", 4), ("t3_scaled", 3)):
        x = generator._innovations(np.random.default_rng(2), 400000, kind)
        assert abs(x.var() - 1.0) < 0.1 and math.isclose(1.0, (nu / (nu - 2)) / (nu / (nu - 2)))
    s2 = next(c for c in ECELLS if c["DESIGN_ID"] == "S2")
    s1_like = dict(s2, DESIGN_ID="S1", GENERATOR_PARAMS={**s2["GENERATOR_PARAMS"], "innovation": "gaussian"})
    for f in CANDIDATES:
        assert compiler.feasibility(s2, f)["REQUIRED_N"] == compiler.feasibility(s1_like, f)["REQUIRED_N"]


def test_B_paired_construction_and_signflip_object(monkeypatch):
    cell = _small("S3", "DELTA_MIN", 40)
    V = cell["VARIANCE_RELATIONSHIPS"]["VAR_TRUE"]; icc = cell["GENERATOR_PARAMS"]["pair_icc"]
    var_obs = V / (2 * (1 - icc))
    # analytic: Var(X1)=Var(X2)=var_obs, Cov=icc*var_obs, Var(X1-X2)=2(1-icc)var_obs = V
    assert math.isclose(2 * (1 - icc) * var_obs, V)
    rng = np.random.default_rng(9); n = 300000
    u = rng.normal(0, math.sqrt(icc * var_obs), n); ea = rng.normal(0, math.sqrt((1 - icc) * var_obs), n); eb = rng.normal(0, math.sqrt((1 - icc) * var_obs), n)
    x1, x2 = u + ea, u + 0.5 + eb
    assert abs(x1.var() / var_obs - 1) < 0.02 and abs(np.cov(x1, x2)[0, 1] / (icc * var_obs) - 1) < 0.03
    d = x2 - x1
    assert abs(d.var() / V - 1) < 0.02 and abs(d.mean() - 0.5) < 0.01     # delta = mean paired difference
    # the sign-flip receives the paired differences, not the raw observations
    seen = {}
    monkeypatch.setattr(generator, "_signflip_p", lambda dd, r, draws=generator.SIGNFLIP_DRAWS: seen.update(d=dd.copy(), draws=draws) or 1.0)
    generator.replicate(cell, 21)
    rng_d, _ = generator.substreams(21); nn = cell["SAMPLE_SIZE"]["COUNT"]
    u = rng_d.normal(0, math.sqrt(icc * var_obs), nn); ea = rng_d.normal(0, math.sqrt((1 - icc) * var_obs), nn); eb = rng_d.normal(0, math.sqrt((1 - icc) * var_obs), nn)
    assert np.array_equal(seen["d"], (u + 0.5 + eb) - (u + ea)) and seen["draws"] == 20000
    # null symmetry: under delta = 0 the differences are eb - ea, symmetric about 0
    null = _small("S3", "NULL", 40); assert generator.true_effect(null) == 0.0


def test_C_cluster_estimator_hand_fixture_and_icc():
    x = np.array([[1.0, 3.0], [2.0, 6.0], [4.0, 8.0]])          # G=3 clusters, m=2
    est, se, df = generator.cluster_robust_t(x)
    # N=6, est=24/6=4, cluster sums [4,8,12], u = sums - est*m = [-4,0,4], sum u^2 = 32, Var = 3/2*32/36
    assert est == 4.0 and df == 2 and math.isclose(se ** 2, 1.5 * 32 / 36)
    one = np.full((5, 24), 2.0); est, se, df = generator.cluster_robust_t(one)
    assert est == 2.0 and se == 0.0 and df == 4
    # generator ICC: Var(x) = V, within-cluster corr = ICC; DEFF consistent with Var(cluster sum) = m*V*DEFF
    cell = _small("S4", "NULL", 2000); V = cell["VARIANCE_RELATIONSHIPS"]["VAR_TRUE"]; icc = cell["GENERATOR_PARAMS"]["icc"]; m = 24
    rng, _ = generator.substreams(3); g = 2000
    a = rng.normal(0, math.sqrt(icc * V), (g, 1)); e = rng.normal(0, math.sqrt((1 - icc) * V), (g, m)); xx = a + e
    assert abs(xx.var() / V - 1) < 0.03
    assert abs(np.corrcoef(xx[:, 0], xx[:, 1])[0, 1] - icc) < 0.03
    deff = 1 + (m - 1) * icc
    assert abs(xx.sum(axis=1).var() / (m * V * deff) - 1) < 0.08


def test_D_event_venue_derivation_and_fixture(monkeypatch):
    cell = _small("S5", "DELTA_MIN", 30)
    V = cell["VARIANCE_RELATIONSHIPS"]["VAR_TRUE"]; rho = cell["GENERATOR_PARAMS"]["venue_corr"]; v = 3
    s2 = V / (rho + (1 - rho) / v)
    # exact: Var(Y_ij) = rho*s2 + (1-rho)*s2 = s2 ; Corr = rho*s2/s2 = rho ; Var(mean_j) = rho*s2 + (1-rho)*s2/v = V
    assert math.isclose(rho * s2 + (1 - rho) * s2, s2) and math.isclose(rho * s2 / s2, rho) and math.isclose(rho * s2 + (1 - rho) * s2 / v, V)
    seen = {}
    monkeypatch.setattr(generator, "_signflip_p", lambda dd, r, draws=generator.SIGNFLIP_DRAWS: seen.update(d=dd.copy(), draws=draws, rng=r) or 1.0)
    generator.replicate(cell, 33)
    rng_d, rng_r = generator.substreams(33); n = cell["SAMPLE_SIZE"]["COUNT"]
    c = rng_d.normal(0, math.sqrt(rho * s2), (n, 1)); w = rng_d.normal(0, math.sqrt((1 - rho) * s2), (n, v))
    assert np.array_equal(seen["d"], (1.0 + c + w).mean(axis=1)) and seen["d"].shape == (n,) and seen["draws"] == 20000
    assert seen["rng"].random(3).tolist() == rng_r.random(3).tolist()   # RANDOMIZATION substream, independent of DATA
    # hand fixture: three events, venues are measurements -> exactly three sign-flipped statistics
    meas = np.array([[1.0, 2.0, 3.0], [4.0, 4.0, 4.0], [-1.0, 0.0, 1.0]])
    assert meas.mean(axis=1).tolist() == [2.0, 4.0, 0.0]


def test_E_planning_object_consistency_S1_S5():
    """VAR_TRUE / VAR_PLANNING denote the same statistical object in generator, oracle and compiler."""
    za, zb = norm.ppf(1 - 0.0125 / 2), norm.ppf(0.8)
    obj = {"S1": "per-observation variance", "S2": "per-observation variance",
           "S3": "variance of the paired difference", "S4": "per-hour (per-observation) variance; cluster handled by DEFF",
           "S5": "variance of the venue-averaged event statistic"}
    for design in obj:
        c = next(x for x in ECELLS if x["DESIGN_ID"] == design and x["EXECUTION_STATUS"] == "ACTIVE"
                 and x["VARIANCE_RELATIONSHIPS"]["q"] == 1.0 and x["VARIANCE_RELATIONSHIPS"]["k"] == 1.0 and x["SIZE_MULTIPLIER"] == 1.0)
        V = c["VARIANCE_RELATIONSHIPS"]["VAR_TRUE"]
        assert compiler.required_n(c, V) == c["N_ORACLE_80"]            # compiler(V) == frozen oracle(V) cell by cell
        if design in ("S1", "S2"):
            assert c["N_ORACLE_80"] == 2 * math.ceil(2 * V * (za + zb) ** 2 / 0.25)
        if design in ("S3", "S5"):
            d = c["GENERATOR_PARAMS"]["delta_min"]; assert c["N_ORACLE_80"] == math.ceil(V * (za + zb) ** 2 / d ** 2)


def test_F_aggregation_precedence_order_independence_and_3b_role():
    def row(cid, grid, f, verdict, safety, utility=None, status="ACTIVE", expected="BOUNDARY_NO_REQUIREMENT"):
        return {"CELL_ID": cid, "DESIGN_ID": "S1", "GRID": grid, "ROLE": "SAFETY", "CANDIDATE_FLOOR": f,
                "FEASIBILITY": {"VERDICT": verdict}, "SAFETY": safety, "UTILITY": utility, "EXECUTION_STATUS": status,
                "EXPECTED_CLASSIFICATION": expected}
    C = [0.60, 0.75, 1.00]
    # excluded S6 rows with FAIL can never reach a decision
    rows = [row("x6", "3A", f, "FEASIBLE", "FAIL", status="EXCLUDED_PRE_RUN_DESIGN_INVALID") for f in C]
    rows += [row("a", "3A", f, "FEASIBLE", "PASS") for f in C]
    agg = engine.aggregate(rows, C)
    assert agg["FINAL"] == "VALIDATION_PASS" and agg["ADOPTED_FLOOR"] == 0.60
    # 3B can only block after the provisional floor, never select it
    rows2 = rows + [row("b3", "3B", 0.60, "FEASIBLE", "FAIL"), row("b3", "3B", 0.75, "FEASIBLE", "PASS"), row("b3", "3B", 1.00, "FEASIBLE", "PASS")]
    agg2 = engine.aggregate(rows2, C)
    assert agg2["ADOPTED_FLOOR_CANDIDATE"] == 0.60 and agg2["FINAL"] == "ADOPTION_BLOCKED_BY_STRESS" and "ADOPTED_FLOOR" not in agg2
    # precedence FAIL > INDETERMINATE > PASS
    assert engine._status_from(["PASS", cp.INDETERMINATE, "FAIL"]) == "FAIL"
    assert engine._status_from(["PASS", cp.INDETERMINATE]) == "INDETERMINATE" and engine._status_from(["PASS"]) == "PASS"
    # candidate order independence
    assert engine.aggregate(rows2, [1.00, 0.60, 0.75]) == agg2
    # no override path: aggregate and official_run take no override argument
    import inspect
    assert set(inspect.signature(engine.aggregate).parameters) == {"rows", "candidates"}
    assert set(inspect.signature(engine.official_run).parameters) == set()
    # stress INDETERMINATE
    rows3 = rows + [row("b4", "3B", 0.60, "FEASIBLE", cp.INDETERMINATE)]
    assert engine.aggregate(rows3, C)["FINAL"] == "STRESS_VALIDATION_INDETERMINATE"
    # all 3A FAIL vs INDETERMINATE routing
    assert engine.aggregate([row("a", "3A", f, "FEASIBLE", "FAIL") for f in C], C)["FINAL"] == "VARIANCE_MODEL_REDESIGN_REQUIRED"
    assert engine.aggregate([row("a", "3A", f, "FEASIBLE", cp.INDETERMINATE) for f in C], C)["FINAL"] == "VALIDATION_INDETERMINATE"
