"""HARNESS_PERFORMANCE_V1: oracle equivalence, workers, fail-closed, isolation.

These tests must not run the frozen 3200-world production grid, consume the
unused ARM, mint RESULT/WORLD_RECORDS, or touch B2-06 / 2025 / 2026 / real
market data.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pytest

from scripts.research import harness_synthetic_edge_calibration_v1_lib as lib
from scripts.research import harness_synthetic_edge_calibration_v1_performance as perf
from scripts.research import harness_synthetic_edge_calibration_v1_production as prod
from scripts.research import harness_synthetic_edge_calibration_v1_worker as worker
from tests.research.harness_synthetic_frozen_oracle import (
    ORACLE_COMMIT,
    ORACLE_LIB_SHA256,
    load_oracle_lib,
    oracle_evaluate_planned_world,
)
from tests.research.test_harness_synthetic_edge_calibration_v1_production import (
    REPO,
    _canonical_arm_commit,
    _head_is_canonical_arm,
)

DIAG_JOBS = perf.diagnostic_jobs()
ONE_JOB = ("EASY", 80, 0)


def _record_job(scenario_id: str, n_rows: int, world_index: int) -> dict:
    identity = lib.world_identity(scenario_id, n_rows, world_index)
    return {
        "scenario_id": scenario_id,
        "n_rows": int(n_rows),
        "world_index": int(world_index),
        "world_identity": identity,
        "world_seed": int(lib.world_seed(identity)),
        "stays_in_denominator": True,
        "valid": True,
    }


def _record_digest(rec) -> str:
    return prod._record_content_digest(rec)


def test_oracle_is_historical_bytes_not_live_alias():
    olib = load_oracle_lib()
    assert olib.__name__ != lib.__name__
    assert olib is not lib
    assert olib.placebo_q95 is not lib.placebo_q95
    assert olib.placebo_q95 is not prod.placebo_q95
    digest = hashlib.sha256(Path(lib.__file__).read_bytes()).hexdigest()
    assert digest == ORACLE_LIB_SHA256
    assert digest == prod.FROZEN_REVIEWED_LIB_SHA256
    assert olib.placebo_q95 is not prod.placebo_q95_base_cached


def test_dgp_arrays_match_oracle():
    olib = load_oracle_lib()
    live_world = lib.simulate_dgp(scenario_id="EASY", n_rows=80, world_index=0)
    oracle_world = olib.simulate_dgp(scenario_id="EASY", n_rows=80, world_index=0)
    assert live_world["world_identity"] == oracle_world["world_identity"]
    assert int(lib.world_seed(live_world["world_identity"])) == int(
        olib.world_seed(oracle_world["world_identity"])
    )
    for key in ("Y", "X1", "X2", "S"):
        assert np.array_equal(live_world[key], oracle_world[key])


def test_lstsq_rank_matches_frozen_fit_lstsq_exactly():
    olib = load_oracle_lib()
    rng = np.random.default_rng(20260910)
    mismatches = 0
    for _ in range(200):
        n_rows, k = 40, 4
        x = rng.normal(size=(n_rows, k))
        if rng.random() < 0.25:
            x[:, -1] = x[:, 0]
        y = rng.normal(size=n_rows)
        frozen_err = None
        new_err = None
        frozen_coef = None
        new_coef = None
        try:
            frozen_coef = olib.fit_lstsq(x, y)
        except olib.IncompleteWorld as exc:
            frozen_err = str(exc)
        try:
            new_coef = prod.fit_lstsq_lstsq_rank(x, y)
        except lib.IncompleteWorld as exc:
            new_err = str(exc)
        if frozen_err != new_err:
            mismatches += 1
        elif frozen_coef is not None:
            if not np.array_equal(frozen_coef, new_coef):
                mismatches += 1
    assert mismatches == 0
    dgp = lib.simulate_dgp(scenario_id="EASY", n_rows=80, world_index=0)
    y = np.asarray(dgp["Y"], dtype=np.float64)
    x1 = np.asarray(dgp["X1"], dtype=np.float64)
    x2 = np.asarray(dgp["X2"], dtype=np.float64)
    feature = lib.candidate_features(dgp)["F03"]
    slices = lib.era_slices(80)
    for _era_name, slc in slices.items():
        if slc.start == 0:
            continue
        train = slice(0, slc.start)
        x_base = lib._design_matrix(x1[train], x2[train])
        x_cand = lib._design_matrix(x1[train], x2[train], feature[train])
        y_train = y[train]
        for design in (x_base, x_cand):
            frozen_err = None
            new_err = None
            frozen_coef = None
            new_coef = None
            try:
                frozen_coef = olib.fit_lstsq(design, y_train)
            except olib.IncompleteWorld as exc:
                frozen_err = str(exc)
            try:
                new_coef = prod.fit_lstsq_lstsq_rank(design, y_train)
            except lib.IncompleteWorld as exc:
                new_err = str(exc)
            assert frozen_err == new_err
            if frozen_coef is not None:
                assert np.array_equal(frozen_coef, new_coef)


def test_placebo_base_cache_matches_oracle_and_rng_state():
    olib = load_oracle_lib()
    world = olib.simulate_dgp(scenario_id="EASY", n_rows=80, world_index=0)
    feature = olib.candidate_features(world)["F03"]
    identity = str(world["world_identity"])
    seed = olib.namespace_seed(olib.world_seed(identity), "PLACEBO", "F03")
    rng_oracle = olib.pcg64_generator(seed)
    rng_cached = olib.pcg64_generator(seed)
    oracle = olib.placebo_q95(
        world=world,
        feature=feature,
        n_rows=80,
        replicates=lib.PRODUCTION_PLACEBO_REPLICATES,
        rng=rng_oracle,
    )
    cached = prod.placebo_q95_base_cached(
        world=world,
        feature=feature,
        n_rows=80,
        replicates=lib.PRODUCTION_PLACEBO_REPLICATES,
        rng=rng_cached,
    )
    assert oracle["placebo_invalid"] is cached["placebo_invalid"]
    assert oracle["world_invalid"] is cached["world_invalid"]
    if oracle["placebo_invalid"]:
        assert cached["placebo_invalid"] is True
    else:
        assert oracle["placebo_q95"] == cached["placebo_q95"]
    assert rng_oracle.bit_generator.state == rng_cached.bit_generator.state


def test_sequential_oracle_equivalence_one_world():
    oracle = oracle_evaluate_planned_world(*ONE_JOB)
    live = prod._evaluate_planned_world_body(*ONE_JOB)
    assert oracle["world_identity"] == live["world_identity"]
    assert oracle["world_seed"] == live["world_seed"]
    oracle_bytes = prod.canonical_json_bytes(oracle)
    live_bytes = prod.canonical_json_bytes(live)
    assert oracle_bytes == live_bytes
    assert hashlib.sha256(oracle_bytes).hexdigest() == hashlib.sha256(live_bytes).hexdigest()
    assert oracle["valid"] is live["valid"]
    assert oracle["invalid_reasons"] == live["invalid_reasons"]
    assert oracle["taxonomy"] == live["taxonomy"]
    assert oracle["selected_STRICT_PASS"] == live["selected_STRICT_PASS"]
    for live_cand, oracle_cand in zip(live["candidates"], oracle["candidates"]):
        assert live_cand["feature_id"] == oracle_cand["feature_id"]
        assert live_cand["valid"] is oracle_cand["valid"]
        assert live_cand.get("MEAN_AE_IMPROVEMENT") == oracle_cand.get("MEAN_AE_IMPROVEMENT")
        assert live_cand.get("bootstrap") == oracle_cand.get("bootstrap")
        assert live_cand.get("visibility") == oracle_cand.get("visibility")
        assert live_cand.get("placebo") == oracle_cand.get("placebo")
        assert live_cand.get("gates") == oracle_cand.get("gates")


def test_wilson_and_mechanical_conclusion_bytes_unchanged():
    olib = load_oracle_lib()
    assert olib.wilson_interval(0, 400) == lib.wilson_interval(0, 400)
    assert olib.wilson_interval(37, 400) == lib.wilson_interval(37, 400)
    kwargs = dict(
        incomplete_execution=False,
        oracle_null_specificity=lib.PASS,
        blind_null_specificity=lib.PASS,
        trap_specificity=lib.PASS,
        easy_oracle_power=lib.PASS,
        moderate_oracle_power=lib.PASS,
        easy_blind_useful=lib.PASS,
        moderate_blind_useful=lib.PASS,
        visibility_wilson_upper=0.9,
        model_detection_wilson_upper=0.9,
        materiality_only_failure=False,
    )
    assert olib.mechanical_conclusion(**kwargs) == lib.mechanical_conclusion(**kwargs)


def test_workers_1_2_4_and_completion_order_independent():
    payloads = {}
    for workers_n in (1, 2, 4):
        payloads[workers_n] = perf.run_non_production_performance_diagnostic(
            DIAG_JOBS, workers=workers_n
        )
    reference = payloads[1]
    assert reference["label"] == "NON_PRODUCTION_PERFORMANCE_DIAGNOSTIC"
    assert reference["not_a_production_result"] is True
    planned_ids = [lib.world_identity(*job) for job in DIAG_JOBS]
    for payload in payloads.values():
        assert payload["world_identities"] == planned_ids
        assert payload["world_seeds"] == reference["world_seeds"]
        assert payload["record_digest_chain"] == reference["record_digest_chain"]
        assert payload["world_set_sha256"] == reference["world_set_sha256"]
        assert prod.canonical_json_bytes({"worlds": payload["records"]}) == prod.canonical_json_bytes(
            {"worlds": reference["records"]}
        )
        assert payload["records"][0]["world_identity"] == planned_ids[0]
        assert payload["records"][-1]["world_identity"] == planned_ids[-1]
    shuffled = list(reversed(list(reference["records"])))
    reordered = prod.assemble_canonical_world_records(
        planned_jobs=DIAG_JOBS, completed_records=shuffled
    )
    assert [rec["world_identity"] for rec in reordered] == planned_ids
    assert [_record_digest(rec) for rec in reordered] == reference["record_digest_chain"]


def test_duplicate_missing_unexpected_rejection():
    a = _record_job("EASY", 80, 0)
    b = _record_job("NULL", 80, 0)
    planned = (("EASY", 80, 0), ("NULL", 80, 0))
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="duplicate world identity"):
        prod.assemble_canonical_world_records(planned_jobs=planned, completed_records=(a, a))
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="missing planned world"):
        prod.assemble_canonical_world_records(planned_jobs=planned, completed_records=(a,))
    extra = _record_job("EASY", 80, 1)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="unexpected world identity"):
        prod.assemble_canonical_world_records(planned_jobs=planned, completed_records=(a, b, extra))
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="malformed worker record"):
        prod.assemble_canonical_world_records(planned_jobs=planned, completed_records=("nope",))


def test_worker_crash_fail_closed(monkeypatch):
    monkeypatch.setenv(worker.TEST_WORKER_CRASH_ENV, "1")
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="failed closed"):
        prod.evaluate_planned_jobs_fail_closed(
            (("EASY", 80, 0), ("NULL", 80, 0)), workers=2
        )


def test_production_session_refuses_crash_injection_env(monkeypatch):
    monkeypatch.setenv(worker.TEST_WORKER_CRASH_ENV, "1")
    session = prod._CanonicalExecutionSession()
    session.production = True
    session.jobs = (("EASY", 80, 0),)
    session.capability = None
    session.records = ()
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="cannot enter production"
    ):
        prod._run_session_jobs(session, workers=1)


def test_deterministic_repeated_execution():
    first = prod.evaluate_planned_jobs_fail_closed((ONE_JOB,), workers=1)
    second = prod.evaluate_planned_jobs_fail_closed((ONE_JOB,), workers=1)
    assert prod.canonical_json_bytes({"worlds": first}) == prod.canonical_json_bytes(
        {"worlds": second}
    )


def test_diagnostic_cannot_enter_production_path():
    src = Path(perf.__file__).read_text(encoding="utf-8")
    assert "run_canonical_production_execution" not in src
    assert "spawn_canonical_production_process" not in src
    assert "verify_executed_production_authority" not in src
    assert "mint_final_result" not in src
    assert "NON_PRODUCTION_PERFORMANCE_DIAGNOSTIC" in src
    rc = perf.main(["--run-production-grid"])
    assert rc == 2
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="production N"):
        perf.assert_non_production_jobs((("EASY", 5000, 0),))
    huge = tuple(("EASY", 80, i) for i in range(3200))
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="3200"):
        perf.assert_non_production_jobs(huge)


def test_diagnostic_does_not_use_arm_as_permission(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("production authorization surface touched")

    monkeypatch.setattr(prod, "production_monte_carlo_arm_authorized", boom)
    monkeypatch.setattr(prod, "verify_executed_production_authority", boom)
    monkeypatch.setattr(prod, "run_canonical_production_execution", boom)
    monkeypatch.setattr(prod, "mint_final_result", boom)
    recs = prod.evaluate_planned_jobs_fail_closed((ONE_JOB,), workers=1)
    assert recs[0]["world_identity"] == lib.world_identity(*ONE_JOB)
    assert recs[0]["world_seed"] == int(lib.world_seed(recs[0]["world_identity"]))


def test_no_production_artifact_writes_and_arm_unconsumed():
    arm_path = REPO / prod.CANONICAL_ARM_PATH
    arm = json.loads(arm_path.read_text(encoding="utf-8"))
    assert arm["authorization_consumed"] is False
    assert arm["production_calibration_executed"] is False
    assert arm["production_result_minted"] is False
    assert arm["world_records_persisted"] is False
    assert (REPO / prod.CANONICAL_RESULT_PATH).exists() is False
    assert (REPO / prod.CANONICAL_WORLD_RECORDS_PATH).exists() is False
    assert (REPO / prod.CANONICAL_RESERVATION_PATH).exists() is False
    assert (REPO / prod.CANONICAL_CLAIM_PATH).exists() is False
    assert (REPO / prod.CANONICAL_PARTIAL_PATH).exists() is False
    arm_commit = _canonical_arm_commit(REPO)
    assert arm_commit == "0abc5fe167e018ebe1f7efbb70694887ac095e17"
    tracked = json.loads(
        __import__("subprocess").check_output(
            ["git", "-C", str(REPO), "cat-file", "blob", f"{arm_commit}:{prod.CANONICAL_ARM_PATH}"]
        )
    )
    assert tracked["authorization_consumed"] is False
    if not _head_is_canonical_arm(REPO):
        assert prod.production_monte_carlo_arm_authorized() is False
    payload = perf.run_non_production_performance_diagnostic((ONE_JOB,), workers=1)
    assert payload["not_a_production_result"] is True
    assert payload["authority_consumed"] is False
    assert (REPO / prod.CANONICAL_RESULT_PATH).exists() is False
    assert (REPO / prod.CANONICAL_WORLD_RECORDS_PATH).exists() is False
    assert json.loads(arm_path.read_text(encoding="utf-8"))["authorization_consumed"] is False


def test_worker_count_explicit_and_blas_env():
    assert prod.resolve_execution_workers(None) == 1
    assert prod.resolve_execution_workers(4) == 4
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="workers"):
        prod.resolve_execution_workers(0)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="workers"):
        prod.resolve_execution_workers(True)
    prod.apply_worker_blas_thread_limits()
    for key in prod.BLAS_THREAD_LIMIT_KEYS:
        assert os.environ[key] == "1"
    hint = prod.conservative_worker_count()
    assert type(hint) is int and hint >= 1
    cpu = os.cpu_count() or 1
    assert hint <= max(1, int(cpu))


def test_cli_workers_flag_exists_and_does_not_run_grid():
    from scripts.research.harness_synthetic_edge_calibration_v1 import main as runner_main

    rc = runner_main(["--identity"])
    assert rc == 0
    source = Path("scripts/research/harness_synthetic_edge_calibration_v1.py").read_text(
        encoding="utf-8"
    )
    assert "--workers" in source


def test_oracle_commit_is_reviewed_implementation():
    assert ORACLE_COMMIT == "3fadc391ee0002e35463b526301d287d4a662828"
