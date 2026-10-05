"""Executor of COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1: DEV fixtures only.
No frozen CAL/EVAL cell is executed here; no C-table is built from frozen cells."""

import ast
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from scripts.research.compiler_v3_estimator_calibration import aggregate as AG
from scripts.research.compiler_v3_estimator_calibration import amendment_v3 as A3
from scripts.research.compiler_v3_estimator_calibration import amendment_v4 as A4
from scripts.research.compiler_v3_estimator_calibration import cells as C
from scripts.research.compiler_v3_estimator_calibration import checkpoint as CK
from scripts.research.compiler_v3_estimator_calibration import ctable, engine
from scripts.research.compiler_v3_estimator_calibration import estimators as E
from scripts.research.compiler_v3_estimator_calibration import generators as G
from scripts.research.compiler_v3_estimator_calibration import run as R

PKG = Path(engine.__file__).parent


def dev_cell(klass, n, levels=None, cid=None, seed_base=2_000_000):
    fam = {"TWO_SAMPLE": "F1", "PAIRED_UNITS": "F2", "CLUSTERED": "F3", "RARE_EVENT": "F4"}[klass]
    lv = levels or {"F1": {"phi": 0.3, "tail": "T4"}, "F2": {"phi": 0.6, "tail": "GAUSS"},
                    "F3": {"icc": 0.3, "sizes": "HETERO", "phi_G": 0.3, "tail": "GAUSS", "m_nominal": 24, "m_range": [12, 36]},
                    "F4": {"venue_corr": 0.9, "scale": "HETERO", "phi_e": 0.3, "tail": "T4", "venues": 3, "scale_multiplier": "exp(0.5*Z)"}}[fam]
    return {"CELL_ID": cid or f"DEV-{klass}-{n}", "FAMILY": fam, "CLASS": klass, "N": n, "LABEL": "MUST", "DECISIVE": True, "LEVELS": lv,
            "SEED_RANGE": {"CAL": [seed_base, seed_base + 99], "EVAL_STAGE_B": [seed_base + 500, seed_base + 699]}}


# ------------------------------------------------------------------ RNG / replay

def test_replay_identical_across_calls_and_processes():
    cell = dev_cell("CLUSTERED", 13)
    a = G.generate(cell, 123456)
    b = G.generate(cell, 123456)
    assert np.array_equal(a["SEQUENCE"], b["SEQUENCE"]) and a["VAR_TRUE"] == b["VAR_TRUE"]
    code = ("import json,sys,numpy as np;from scripts.research.compiler_v3_estimator_calibration import generators as G;"
            f"c=json.loads(sys.argv[1]);s=G.generate(c,123456);print(json.dumps([s['SEQUENCE'].tolist(),s['VAR_TRUE']]))")
    out = subprocess.check_output([sys.executable, "-c", code, json.dumps(cell)], cwd=str(C.REPO)).decode()
    seq, truth = json.loads(out)
    assert np.array_equal(np.array(seq), a["SEQUENCE"]) and truth == a["VAR_TRUE"]
    # different seed -> different sample; candidate is not part of the derivation (there is no candidate argument at all)
    assert not np.array_equal(G.generate(cell, 123457)["SEQUENCE"], a["SEQUENCE"])


def test_substreams_reserved_child_unused():
    rng, reserved = G.substreams(42)
    assert isinstance(reserved, np.random.SeedSequence)
    first = rng.standard_normal()
    rng2, _ = G.substreams(42)
    assert rng2.standard_normal() == first


# ------------------------------------------------------------------ estimators and objects

def test_bartlett_literal_and_two_sample_pooling():
    rng = np.random.default_rng(3)
    x, y = rng.standard_normal(27), rng.standard_normal(64)
    n, L = 27, 3
    d = x - x.mean()
    gamma = [sum(d[t] * d[t - l] for t in range(l, n)) / n for l in range(L + 1)]
    omega = gamma[0] + 2 * sum((1 - l / (L + 1)) * gamma[l] for l in range(1, L + 1))
    assert abs(E.bartlett_omega(x) - omega) < 1e-12
    s = {"CLASS": "TWO_SAMPLE", "ARMS": (x, y)}
    assert abs(E.bartlett_omega(y) - E.bartlett_omega(y)) < 1e-12
    # V4 D4: TWO_SAMPLE nu_B = 2 * (floor(n/(L(n)+1)) - 1) with the per-arm bandwidth; unequal arms are an error
    s_eq = {"CLASS": "TWO_SAMPLE", "ARMS": (x, rng.standard_normal(27))}
    assert E.long_run_variance(s_eq)[1] == 2 * (27 // (E.bandwidth(27) + 1) - 1) == A4.nu_b_two_sample(27)
    with pytest.raises(E.CalibrationExecutionError, match="EQUAL_ARMS_ONLY"):
        E.long_run_variance(s)


def test_error_rule_not_repaired():
    with pytest.raises(E.CalibrationExecutionError):
        E.bartlett_omega(np.ones(20))
    with pytest.raises(E.CalibrationExecutionError):
        E.naive_variance({"CLASS": "PAIRED_UNITS", "SEQUENCE": np.ones(20)})


def test_statistical_objects_per_class():
    # CLUSTERED: estimator is the variance of cluster-level means, not of per-hour observations.
    cell = dev_cell("CLUSTERED", 20)
    s = G.generate(cell, 7)
    va, nu = E.naive_variance(s)
    assert nu == 19 and abs(va - np.var(s["SEQUENCE"], ddof=1)) < 1e-12 and len(s["SEQUENCE"]) == 20
    assert "CLUSTER_SIZES" in s and s["CLUSTER_SIZES"].min() >= 12 and s["CLUSTER_SIZES"].max() <= 36
    # TWO_SAMPLE: per-observation within-arm variance, equal arms only.
    s2 = G.generate(dev_cell("TWO_SAMPLE", 33), 7)
    xa, xb = s2["ARMS"]
    assert len(xa) == len(xb) == 33
    va2, nu2 = E.naive_variance(s2)
    assert nu2 == 64 and abs(va2 - (32 * np.var(xa, ddof=1) + 32 * np.var(xb, ddof=1)) / 64) < 1e-12
    # PAIRED_UNITS / RARE_EVENT: single sequence of unit statistics.
    for klass in ("PAIRED_UNITS", "RARE_EVENT"):
        s3 = G.generate(dev_cell(klass, 45), 7)
        assert len(s3["SEQUENCE"]) == 45 and E.naive_variance(s3)[1] == 44
    # ERA_STRATIFIED is unsupported.
    with pytest.raises(KeyError):
        G.generate({"FAMILY": "F6", "CLASS": "ERA_STRATIFIED", "N": 10, "LEVELS": {}}, 1)


@pytest.mark.parametrize("klass,n,levels", [
    ("PAIRED_UNITS", 50, {"phi": 0.6, "tail": "GAUSS"}),
    ("PAIRED_UNITS", 50, {"phi": 0.3, "tail": "T4"}),
    ("TWO_SAMPLE", 40, {"phi": 0.3, "tail": "GAUSS"}),
    ("CLUSTERED", 12, {"icc": 0.3, "sizes": "HETERO", "phi_G": 0.3, "tail": "GAUSS", "m_nominal": 24, "m_range": [12, 36]}),
    ("RARE_EVENT", 35, {"venue_corr": 0.9, "scale": "HETERO", "phi_e": 0.3, "tail": "GAUSS", "venues": 3, "scale_multiplier": "exp(0.5*Z)"}),
])
def test_truth_matches_generated_process(klass, n, levels):
    """DEV check: n x Var(mean of the unit statistic) over many DEV seeds equals VAR_TRUE_USED (within MC error)."""
    cell = dev_cell(klass, n, levels)
    reps = 6000
    means, truths = [], []
    for seed in range(3_000_000, 3_000_000 + reps):
        s = G.generate(cell, seed)
        seq = np.concatenate(s["ARMS"]) if klass == "TWO_SAMPLE" else s["SEQUENCE"]
        if klass == "TWO_SAMPLE":
            xa, xb = s["ARMS"]
            means.append(xa.mean() - xb.mean())
            truths.append(s["VAR_TRUE"] * 2 / n)         # Var(diff of means) = sigma2_LR * (1/n + 1/n)
        else:
            means.append(seq.mean())
            truths.append(s["VAR_TRUE"] / n)
    emp = np.var(means, ddof=1)
    ref = np.mean(truths)                                        # realized truth averaged over replicates (CLUSTERED HETERO varies)
    assert abs(emp / ref - 1) < 0.08, (emp, ref)


def test_clustered_truth_is_exact_single_authoritative():
    s = G.generate(dev_cell("CLUSTERED", 12), 11)
    assert "VAR_TRUE_FROZEN_FORMULA" not in s and "TRUTH_MATCHES_FROZEN" not in s
    v = 0.3 + 0.7 / s["CLUSTER_SIZES"]
    assert abs(s["VAR_TRUE"] - A4.clustered_truth_by_covariance(v, 0.3)) < 1e-10
    # analytic properties (V4 D2)
    assert abs(A4.clustered_truth(v, 0.0) - v.mean()) < 1e-12
    veq = np.full(12, 0.3 + 0.7 / 24)
    assert abs(A4.clustered_truth(veq, 0.3) - veq[0] * G.ar_factor(12, 0.3)) < 1e-12
    assert abs(A4.clustered_truth(veq, 0.0) - (0.3 + 0.7 / 24)) < 1e-12


def test_rare_event_truth_identity():
    for n, phi, vc, h in [(30, 0.3, 0.9, True), (50, 0.0, 0.5, False), (100, 0.6, 0.7, True)]:
        assert abs(A4.rare_event_truth_by_covariance(n, phi, vc, h) - A4.rare_event_truth_formula(n, phi, vc, h)) < 1e-9
    lv = {"venue_corr": 0.9, "scale": "HETERO", "phi_e": 0.3, "tail": "GAUSS", "venues": 3, "scale_multiplier": "exp(0.5*Z)"}
    s = G.generate(dev_cell("RARE_EVENT", 30, lv), 1)
    assert abs(s["VAR_TRUE"] - A4.rare_event_truth_formula(30, 0.3, 0.9, True)) < 1e-12


# ------------------------------------------------------------------ candidate-independent reuse

def test_single_sample_all_candidates():
    cell = dev_cell("RARE_EVENT", 40)
    row = engine.eval_replicate(cell, 5)
    assert set(row) == set(A4.SLIM_ROW_KEYS["EVAL"]) and row["P"] == "EVAL" and row["E"] is None
    s = G.generate(cell, 5)
    va, _ = E.naive_variance(s)
    assert row["VA"] == va and row["T"] == s["VAR_TRUE"]
    d = engine.derive(row, cell, 1.3)
    assert d["MISS_A"] == (row["T"] > E.chi2_bound(va, 39)) and d["MISS_C"] == (row["T"] > va * 1.3) and d["UTIL_D"] == (4.0 / row["T"] <= 1.5)
    assert set(engine.cal_replicate(cell, 5)) == set(A4.SLIM_ROW_KEYS["CAL"])


# ------------------------------------------------------------------ phases, sealing, guards

def test_cal_seal_eval_state_machine(tmp_path):
    cal, ev, realistic, rng = R.dev_cells(n_cal=40, n_eval=40)
    with pytest.raises(RuntimeError, match="CAL not complete"):
        engine.run_eval(tmp_path, ev, stage_a=40, stage_b=80)
    path = engine.run_cal(tmp_path, cal, cal_n=40)
    body = json.loads(path.read_text())
    for klass, t in body["TABLE"].items():
        sizes = sorted(int(k) for k in t)
        env = [t[str(n)]["C_ENV"] for n in sizes]
        assert all(a >= b for a, b in zip(env, env[1:]))                    # suffix max, non-increasing
        for n in sizes:
            assert t[str(n)]["RANK"] == int(np.ceil(0.99 * t[str(n)]["M"])) and t[str(n)]["C_ENV"] >= t[str(n)]["C_RAW"]
            assert t[str(n)]["CAL_CELL_IDS"] and t[str(n)]["CAL_SEED_RANGES"]
    with pytest.raises(RuntimeError, match="already sealed"):
        ctable.seal_c_table(tmp_path, {}, "x", {})
    rec = json.loads((tmp_path / engine.CAL_DONE_NAME).read_text())
    # tamper -> EVAL refused
    path.write_text(path.read_text() + "\n")
    with pytest.raises(RuntimeError, match="digest"):
        engine.run_eval(tmp_path, ev, stage_a=40, stage_b=80)
    path.write_text(path.read_text()[:-1])
    res = engine.run_eval(tmp_path, ev, stage_a=40, stage_b=80)
    assert len(res) == len(ev) and rec["C_TABLE_SHA256"] == ctable.load_sealed(tmp_path)["_SHA256"]


def test_eval_code_path_has_no_c_table_writer():
    """The EVAL path (engine.run_eval / eval_gate / eval_replicate) never calls seal_c_table or writes the C-table."""
    tree = ast.parse((PKG / "engine.py").read_text())
    funcs = {f.name: f for f in tree.body if isinstance(f, ast.FunctionDef)}
    for name in ("run_eval", "eval_gate", "eval_replicate", "derive", "decide_cell", "_decide_rows"):
        calls = [n.attr for n in ast.walk(funcs[name]) if isinstance(n, ast.Attribute)]
        assert "seal_c_table" not in calls and "write_text" not in calls and "build_c_table" not in calls
    assert "seal_c_table" in [n.attr for n in ast.walk(funcs["run_cal"]) if isinstance(n, ast.Attribute)]
    src = (PKG / "ctable.py").read_text()
    assert src.count("write_text") == 1                                          # the single writer lives in seal_c_table


def test_official_refused_and_frozen_cells_guarded(tmp_path):
    with pytest.raises(engine.OfficialExecutionRefused):
        engine.run_cal(tmp_path, C.cal_cells()[:1], cal_n=1, official=True)
    frozen = C.cal_cells()[0]
    with pytest.raises(engine.OfficialExecutionRefused):
        engine.run_cal(tmp_path, [frozen], cal_n=1, official=False)
    bad = dev_cell("PAIRED_UNITS", 41, seed_base=5 * 10**12)                     # non-DEV seed space refused
    with pytest.raises(engine.OfficialExecutionRefused):
        engine.run_cal(tmp_path, [bad], cal_n=1)
    assert not (tmp_path / "replicates.jsonl").exists() or (tmp_path / "replicates.jsonl").stat().st_size == 0


# ------------------------------------------------------------------ checkpoint / resume

def test_checkpoint_resume_idempotent_and_integrity(tmp_path):
    cal, ev, _, _ = R.dev_cells(n_cal=20, n_eval=20)
    engine.run_cal(tmp_path, cal[:2], cal_n=20)
    ck = CK.Checkpoint(tmp_path / "replicates.jsonl")
    n0 = len(ck.index)
    row = ck.rows("CAL")[0]
    ck.record(row)                                                               # bit-identical duplicate: no-op
    assert len(ck.index) == n0
    bad = dict(row); bad["VA"] = row["VA"] + 1e-9
    with pytest.raises(CK.ExecutionIntegrityError):
        ck.record(bad)
    ck.close()
    # Resume with a truncated checkpoint executes only the missing seeds and reproduces identical rows.
    lines = (tmp_path / "replicates.jsonl").read_text().splitlines()
    (tmp_path / "replicates.jsonl").write_text("\n".join(lines[: 1 + n0 // 2]) + "\n")   # keep the header line
    (tmp_path / ctable.C_TABLE_NAME).unlink(); (tmp_path / engine.CAL_DONE_NAME).unlink()
    engine.run_cal(tmp_path, cal[:2], cal_n=20)
    ck2 = CK.Checkpoint(tmp_path / "replicates.jsonl")
    assert sorted(ck2.index.values()) == sorted(ck.index.values())
    ck2.close()


def test_order_independence_of_rows(tmp_path):
    cal, _, _, _ = R.dev_cells(n_cal=15, n_eval=15)
    engine.run_cal(tmp_path / "a", cal[:2], cal_n=15)
    engine.run_cal(tmp_path / "b", list(reversed(cal[:2])), cal_n=15)
    ra = CK.Checkpoint(tmp_path / "a/replicates.jsonl").rows("CAL")
    rb = CK.Checkpoint(tmp_path / "b/replicates.jsonl").rows("CAL")
    assert ra == rb
    ta = json.loads((tmp_path / "a" / ctable.C_TABLE_NAME).read_text())["TABLE"]
    tb = json.loads((tmp_path / "b" / ctable.C_TABLE_NAME).read_text())["TABLE"]
    assert ta == tb


# ------------------------------------------------------------------ aggregation fixtures (Protocol V3 C6/C7)

def _res(klass, n, cov, util, candidates=("A", "B", "C"), decisive=True, cid=None):
    dec = {x: {"COVERAGE": cov[x] if isinstance(cov, dict) else cov, "UTILITY": util[x] if isinstance(util, dict) else util} for x in candidates}
    dec["D"] = {"COVERAGE": "PASS", "UTILITY": "FAIL"}
    return {"CELL_ID": cid or f"{klass}-{n}", "CLASS": klass, "N": n, "DECISIVE": decisive, "DECISIONS": dec}


REAL = {"TWO_SAMPLE": 250, "PAIRED_UNITS": 260, "CLUSTERED": 40, "RARE_EVENT": 100}
RNG = {"TWO_SAMPLE": [30, 250], "PAIRED_UNITS": [40, 260], "CLUSTERED": [8, 40], "RARE_EVENT": [30, 100]}


def _all_pass(klass, sizes, cov=None, util=None):
    return [_res(klass, n, cov or "PASS", util or "PASS") for n in sizes]


def test_different_winners_per_class_and_four_class_pass():
    res = (_all_pass("TWO_SAMPLE", [30, 31, 60])
           + _all_pass("PAIRED_UNITS", [40, 41], cov={"A": "FAIL", "B": "PASS", "C": "PASS"})
           + _all_pass("CLUSTERED", [8, 9], cov={"A": "FAIL", "B": "FAIL", "C": "PASS"})
           + _all_pass("RARE_EVENT", [30, 31], cov={"A": "PASS", "B": "PASS", "C": "PASS"}, util={"A": "FAIL", "B": "PASS", "C": "PASS"}))
    agg = AG.aggregate(res, REAL, RNG)
    sel = {k: v["SELECTED_CANDIDATE"] for k, v in agg["CLASSES"].items()}
    assert sel == {"TWO_SAMPLE": "A", "PAIRED_UNITS": "B", "CLUSTERED": "C", "RARE_EVENT": "B"}
    assert agg["GLOBAL_STATUS"] == "ESTIMATOR_CALIBRATION_PASS"
    po = agg["CLASSES"]["TWO_SAMPLE"]["PASS_OUTPUT"]
    assert po["ALLOCATION_DOMAIN"] == "EQUAL_ARMS_ONLY" and po["SUPPORTED_COUNT_SET"] == [30, 31, 60] and po["UTILITY_FRONTIER"] == 30
    assert "cluster-level" in agg["CLASSES"]["CLUSTERED"]["PASS_OUTPUT"]["DOWNSTREAM_REVALIDATION"]


def test_a_coverage_pass_utility_fail_then_b_considered():
    res = _all_pass("PAIRED_UNITS", [40, 41], util={"A": "FAIL", "B": "PASS", "C": "PASS"})
    c = AG.aggregate_class("PAIRED_UNITS", res, 260, (40, 260))
    assert c["CANDIDATES"]["A"]["STATE"] == "NOT_ELIGIBLE_DECISIVE" and c["SELECTED_CANDIDATE"] == "B"


def test_one_dense_coverage_fail_makes_candidate_not_eligible_not_sparse_support():
    res = _all_pass("CLUSTERED", [8, 9, 10, 11])
    res[2]["DECISIONS"]["A"]["COVERAGE"] = "FAIL"                                # one dense count fails for A
    c = AG.aggregate_class("CLUSTERED", res, 40, (8, 40))
    assert c["CANDIDATES"]["A"]["STATE"] == "NOT_ELIGIBLE_DECISIVE" and c["SELECTED_CANDIDATE"] == "B"
    assert c["COUNT_SUPPORT"]["A"][10] == "UNSUPPORTED_DECISIVE" and c["COUNT_SUPPORT"]["A"][9] == "SUPPORTED"


def test_coverage_hole_differs_from_utility_frontier():
    # Complete coverage, utility fails at the smallest counts: candidate stays eligible, support starts at the frontier.
    res = _all_pass("RARE_EVENT", [30, 31, 32, 33])
    for r in res[:2]:
        for x in ("A", "B", "C"):
            r["DECISIONS"][x]["UTILITY"] = "FAIL"
    c = AG.aggregate_class("RARE_EVENT", res, 100, (30, 100))
    assert c["SELECTED_CANDIDATE"] == "A" and c["PASS_OUTPUT"]["UTILITY_FRONTIER"] == 32
    assert c["PASS_OUTPUT"]["OPERATIONAL_SUPPORT_STARTS_AT"] == 32 and c["PASS_OUTPUT"]["SUPPORTED_COUNT_SET"] == [32, 33]
    # Whereas a coverage hole at the same counts kills eligibility.
    res2 = _all_pass("RARE_EVENT", [30, 31, 32, 33])
    res2[0]["DECISIONS"]["A"]["COVERAGE"] = "FAIL"
    c2 = AG.aggregate_class("RARE_EVENT", res2, 100, (30, 100))
    assert c2["CANDIDATES"]["A"]["STATE"] == "NOT_ELIGIBLE_DECISIVE"


def test_class_indeterminate_decisive_fail_and_execution_error():
    ind = _all_pass("TWO_SAMPLE", [30, 31], cov={"A": "CALIBRATION_INDETERMINATE", "B": "PASS", "C": "PASS"})
    assert AG.aggregate_class("TWO_SAMPLE", ind, 250, (30, 250))["CLASS_STATUS"] == "CALIBRATION_CLASS_INDETERMINATE"
    fail = _all_pass("TWO_SAMPLE", [30, 31], cov="FAIL")
    assert AG.aggregate_class("TWO_SAMPLE", fail, 250, (30, 250))["CLASS_STATUS"] == "CALIBRATION_CLASS_FAIL_INFORMATION_INSUFFICIENT"
    err = _all_pass("TWO_SAMPLE", [30, 31], cov={"A": "CALIBRATION_EXECUTION_ERROR", "B": "PASS", "C": "PASS"},
                    util={"A": "CALIBRATION_EXECUTION_ERROR", "B": "PASS", "C": "PASS"})
    assert AG.aggregate_class("TWO_SAMPLE", err, 250, (30, 250))["CLASS_STATUS"] == "CALIBRATION_CLASS_EXECUTION_ERROR"


def test_global_mixed_statuses():
    ok = lambda k, s: _all_pass(k, s)
    base = ok("TWO_SAMPLE", [30]) + ok("PAIRED_UNITS", [40]) + ok("CLUSTERED", [8])
    mixed_fail = base + _all_pass("RARE_EVENT", [30], cov="FAIL")
    assert AG.aggregate(mixed_fail, REAL, RNG)["GLOBAL_STATUS"] == "ESTIMATOR_CALIBRATION_FAIL_INFORMATION_INSUFFICIENT"
    mixed_ind = base + _all_pass("RARE_EVENT", [30], cov={"A": "ESCALATE", "B": "PASS", "C": "PASS"})
    agg = AG.aggregate(mixed_ind, REAL, RNG)
    assert agg["GLOBAL_STATUS"] == "CALIBRATION_INDETERMINATE" and agg["CLASSES"]["TWO_SAMPLE"]["CLASS_STATUS"] == "CALIBRATION_CLASS_PASS"
    errs = base + _all_pass("RARE_EVENT", [30], cov={"A": "CALIBRATION_EXECUTION_ERROR", "B": "PASS", "C": "PASS"})
    assert AG.aggregate(errs, REAL, RNG)["GLOBAL_STATUS"] == "ESTIMATOR_CALIBRATION_EXECUTION_ERROR"


# ------------------------------------------------------------------ stage logic and thresholds

def test_stage_b_uses_stage_a_as_prefix_and_thresholds(tmp_path):
    cal, ev, _, _ = R.dev_cells(n_cal=30, n_eval=30)
    engine.run_cal(tmp_path, cal[:1], cal_n=30)
    res = engine.run_eval(tmp_path, ev[:1], stage_a=10, stage_b=30)
    ck = CK.Checkpoint(tmp_path / "replicates.jsonl")
    seeds = sorted(r["S"] for r in ck.rows("EVAL"))
    lo = ev[0]["SEED_RANGE"]["EVAL_STAGE_B"][0]
    assert seeds[:10] == list(range(lo, lo + 10)) and (len(seeds) in (10, 30))
    assert res[0]["ESCALATED"] == (len(seeds) == 30)
    t = A3.thresholds()
    assert t["4000"]["COVERAGE_PASS_IF_MISSES_LE"] == 21


def test_v4_strict_preference_scenarios():
    ok_util = {x: {40: ["PASS"]} for x in ("A", "B", "C")}
    def cls(cov, err=None):
        return AG.aggregate_class("PAIRED_UNITS", _all_pass("PAIRED_UNITS", [40], cov=cov), 260, (40, 260)) if err is None else None
    # A unresolved, B pass -> INDETERMINATE, no selection
    c = cls({"A": "CALIBRATION_INDETERMINATE", "B": "PASS", "C": "PASS"})
    assert c["CLASS_STATUS"] == "CALIBRATION_CLASS_INDETERMINATE" and c["SELECTED_CANDIDATE"] is None
    # A error, B pass -> ERROR, no selection
    c = cls({"A": "CALIBRATION_EXECUTION_ERROR", "B": "PASS", "C": "PASS"})
    assert c["CLASS_STATUS"] == "CALIBRATION_CLASS_EXECUTION_ERROR" and c["SELECTED_CANDIDATE"] is None
    # A fail, B unresolved, C pass -> INDETERMINATE
    c = cls({"A": "FAIL", "B": "ESCALATE", "C": "PASS"})
    assert c["CLASS_STATUS"] == "CALIBRATION_CLASS_INDETERMINATE"
    # A fail, B error, C pass -> ERROR
    c = cls({"A": "FAIL", "B": "CALIBRATION_EXECUTION_ERROR", "C": "PASS"})
    assert c["CLASS_STATUS"] == "CALIBRATION_CLASS_EXECUTION_ERROR"
    # A fail, B fail, C pass -> select C
    c = cls({"A": "FAIL", "B": "FAIL", "C": "PASS"})
    assert c["SELECTED_CANDIDATE"] == "C"
    # A pass while B/C error -> select A
    c = cls({"A": "PASS", "B": "CALIBRATION_EXECUTION_ERROR", "C": "CALIBRATION_EXECUTION_ERROR"})
    assert c["SELECTED_CANDIDATE"] == "A" and c["CLASS_STATUS"] == "CALIBRATION_CLASS_PASS"


def _derived(n_pass_a, n_total, miss_b_frac=0.0, util_all=True, miss_c=0):
    """Build derived rows: candidate A misses exactly n_total - n_pass_a times; B misses a fraction; C misses miss_c."""
    rows = []
    for i in range(n_total):
        rows.append({"ERROR": None,
                     "MISS_A": i >= n_pass_a, "UTIL_A": util_all,
                     "MISS_B": i < int(miss_b_frac * n_total), "UTIL_B": True,
                     "MISS_C": i < miss_c, "UTIL_C": True,
                     "MISS_D": False, "UTIL_D": False})
    return rows


def test_stage_a_decisions_locked_per_check():
    # Stage A: A coverage PASS (0 misses in 4000); B coverage ESCALATE (~1.5% misses).
    a_rows = _derived(4000, 4000, miss_b_frac=0.015)
    dec_a = engine.decide_cell(a_rows, None)
    assert dec_a["A"]["COVERAGE"]["STAGE_A"] == "PASS" and dec_a["B"]["COVERAGE"]["STAGE_A"] == "ESCALATE"
    assert engine.needs_stage_b(dec_a)
    # Stage B rows would make A fail badly (all misses) -> A remains PASS (locked at Stage A); B decided on pooled rows.
    b_rows = _derived(0, 16000, miss_b_frac=0.0)
    dec = engine.decide_cell(a_rows, b_rows)
    assert dec["A"]["COVERAGE"]["FINAL"] == "PASS" and dec["A"]["COVERAGE"]["DECIDED_AT"] == "A" and dec["A"]["COVERAGE"]["STAGE_B"] is None
    assert dec["B"]["COVERAGE"]["DECIDED_AT"] == "B" and dec["B"]["COVERAGE"]["FINAL"] in ("PASS", "FAIL", "CALIBRATION_INDETERMINATE")
    # A utility FAIL at Stage A, C escalates -> A utility remains FAIL even though Stage B rows have UTIL_A True.
    a_rows2 = _derived(4000, 4000, util_all=False, miss_c=60)
    dec2 = engine.decide_cell(a_rows2, _derived(16000, 16000, util_all=True, miss_c=0))
    assert dec2["A"]["UTILITY"]["STAGE_A"] == "FAIL" and dec2["A"]["UTILITY"]["FINAL"] == "FAIL" and dec2["C"]["COVERAGE"]["DECIDED_AT"] == "B"
    # Only escalated checks consume Stage-B logic.
    assert all(dec2[x][m]["STAGE_B"] is None for x in ("A", "B", "C", "D") for m in ("COVERAGE", "UTILITY") if dec2[x][m]["STAGE_A"] != "ESCALATE")


def test_slim_checkpoint_schema_and_header(tmp_path):
    cal, ev, _, _ = R.dev_cells(n_cal=12, n_eval=12)
    engine.run_cal(tmp_path, cal[:1], cal_n=12)
    lines = (tmp_path / "replicates.jsonl").read_text().splitlines()
    head = json.loads(lines[0])
    assert "HEADER" in head and head["HEADER"]["EXECUTOR_DIGEST"] == engine.executor_digest()["EXECUTOR_DIGEST"] and head["HEADER"]["SCHEMA"] == "SLIM_V4"
    assert all(set(json.loads(l)) == set(A4.SLIM_ROW_KEYS["CAL"]) for l in lines[1:])
    with pytest.raises(CK.ExecutionIntegrityError, match="header"):
        CK.Checkpoint(tmp_path / "replicates.jsonl", header={"EXECUTOR_DIGEST": "other", "INPUT_DIGESTS": {}, "SCHEMA": "SLIM_V4"})


def test_frozen_digests_match_and_no_frozen_cell_touched():
    assert C.digests_match_amendment()
    assert len(C.cal_cells()) == 258 and len(C.eval_cells()) == 621 + 198 + 4716
    # Official CAL ran once (2026-10-05): the only C-table in the tree is the sealed one recorded
    # in the CAL completion record, byte for byte (the pre-run "absent" check no longer applies).
    import hashlib
    committed = C.DOCS / ctable.C_TABLE_NAME
    completion = json.loads((C.DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_CAL_COMPLETION_V1.json").read_text())
    assert hashlib.sha256(committed.read_bytes()).hexdigest() == completion["C_TABLE"]["SHA256"]
    assert not engine.RUN_AUTHORIZATION.exists()
