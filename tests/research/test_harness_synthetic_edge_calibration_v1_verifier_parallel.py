"""Verifier parallelism and observed_world_count contract.

Bounded NON-PRODUCTION fixtures. Does not run the 3200-world grid,
consume ARM 0abc5fe, or mint RESULT/WORLD_RECORDS.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    SyntheticExecutionNotAuthorized,
)
from scripts.research import harness_synthetic_edge_calibration_v1_production as prod
from tests.research.test_harness_synthetic_edge_calibration_v1_checkpoint_forgery import (
    ONE,
    TWO,
    _bind_prod,
    _commit_production_tree,
    _legit_records,
    _mock_record,
)
from tests.research.test_harness_synthetic_edge_calibration_v1_production import (
    _git,
)


def _proof_from_payload(payload, bound, *, observed_world_count):
    records = payload["records"]
    worlds = prod.canonical_json_bytes({"worlds": prod._jsonable(list(records))})
    return {
        "schema_version": "1.0",
        "kind": prod.AUTHENTICATE_CACHED_RECORDS_PROOF_KIND,
        "mode": prod.AUTHENTICATE_CACHED_RECORDS_MODE,
        "verification_success": True,
        "trust_state": prod.CHECKPOINT_SCIENTIFICALLY_VERIFIED,
        "execution_head": bound["head_sha"],
        "execution_tree": bound["tree_sha"],
        "run_identity": prod._run_identity_from_bound(bound),
        "plan_sha256": payload["plan_sha256"],
        "world_set_sha256": prod._sha256_bytes(worlds),
        "record_digest_chain": list(prod._ordered_record_digest_chain(records)),
        "observed_world_count": observed_world_count,
        "verification_authority": "ISOLATED_FROZEN_GIT_EXECUTION",
    }


def _fake_child(proof):
    return SimpleNamespace(
        returncode=0,
        stdout=prod.canonical_json_bytes(prod._jsonable(proof)),
        stderr=b"",
    )


def _install_eval_stub(repo: Path, body: str) -> None:
    path = repo / prod.PRODUCTION_REL
    text = path.read_text(encoding="utf-8")
    marker = 'if __name__ == "__main__":\n'
    if marker not in text:
        raise AssertionError("production.py is missing the isolated-child main guard")
    path.write_text(text.replace(marker, body + "\n" + marker, 1), encoding="utf-8")


@pytest.mark.parametrize(
    "count",
    [-1, 0, 2, 10**9, "1", True],
    ids=["minus_one", "zero", "plus_one", "very_large", "string", "bool_true"],
)
def test_observed_world_count_mismatch_refused(tmp_path, monkeypatch, count):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    records = [_mock_record(*ONE[0])]
    bound = prod.verify_executed_production_authority(repo)
    payload = prod._untrusted_cached_records_payload(
        bound=bound, planned=ONE, records=records, production=False
    )
    proof = _proof_from_payload(payload, bound, observed_world_count=count)

    def fake_spawn(*args, **kwargs):
        return _fake_child(proof)

    monkeypatch.setattr(prod, "_spawn_isolated_child", fake_spawn)
    with pytest.raises(
        SyntheticExecutionNotAuthorized,
        match="observed_world_count",
    ):
        prod.authenticate_cached_world_records_from_frozen_execution(
            planned=ONE, records=records, repo_root=repo, production=False
        )


def test_correct_digests_with_wrong_observed_world_count_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    records = [_mock_record(*job) for job in TWO]
    bound = prod.verify_executed_production_authority(repo)
    payload = prod._untrusted_cached_records_payload(
        bound=bound, planned=TWO, records=records, production=False
    )
    proof = _proof_from_payload(payload, bound, observed_world_count=1)
    assert proof["world_set_sha256"] == prod._sha256_bytes(
        prod.canonical_json_bytes({"worlds": prod._jsonable(list(payload["records"]))})
    )

    def fake_spawn(*args, **kwargs):
        return _fake_child(proof)

    monkeypatch.setattr(prod, "_spawn_isolated_child", fake_spawn)
    with pytest.raises(
        SyntheticExecutionNotAuthorized,
        match="observed_world_count does not match",
    ):
        prod.authenticate_cached_world_records_from_frozen_execution(
            planned=TWO, records=records, repo_root=repo, production=False
        )


def test_auth_workers_1_2_4_exact(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    monkeypatch.setenv("HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_VERIFY_STAGGER_MS", "50")
    _, records = _legit_records(tmp_path, repo, jobs=TWO)
    proofs = []
    for workers in (1, 2, 4):
        proof = prod.authenticate_cached_world_records_from_frozen_execution(
            planned=TWO,
            records=records,
            repo_root=repo,
            production=False,
            workers=workers,
        )
        proofs.append(proof)
    for proof in proofs[1:]:
        assert proof["world_set_sha256"] == proofs[0]["world_set_sha256"]
        assert proof["record_digest_chain"] == proofs[0]["record_digest_chain"]
        assert proof["plan_sha256"] == proofs[0]["plan_sha256"]
        assert proof["observed_world_count"] == 2
        assert proof["run_identity"] == proofs[0]["run_identity"]
        assert proof.get("workers") is None


def test_inprocess_verify_workers_1_2_4_exact(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    monkeypatch.setenv("HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_VERIFY_STAGGER_MS", "40")
    jobs = TWO
    by_workers = {}
    for workers in (1, 2, 4):
        recs = prod._evaluate_jobs_for_verification(jobs, workers)
        by_workers[workers] = recs
        assert [(r["scenario_id"], r["n_rows"], r["world_index"]) for r in recs] == list(
            jobs
        )
    one = by_workers[1]
    for other in (2, 4):
        assert prod.canonical_json_bytes({"worlds": one}) == prod.canonical_json_bytes(
            {"worlds": by_workers[other]}
        )
        assert [r["world_identity"] for r in one] == [
            r["world_identity"] for r in by_workers[other]
        ]
        assert [r["world_seed"] for r in one] == [r["world_seed"] for r in by_workers[other]]
        assert list(prod._ordered_record_digest_chain(one)) == list(
            prod._ordered_record_digest_chain(by_workers[other])
        )


def test_historical_recompute_uses_shared_parallel_helper():
    src = Path(prod.__file__).read_text(encoding="utf-8")
    recompute_src = src.split(
        "def _recompute_production_records_from_frozen_execution", 1
    )[1].split("def _compare_recomputed_world_records", 1)[0]
    helper_src = src.split("def _evaluate_jobs_for_verification", 1)[1].split(
        "def evaluate_production_candidate", 1
    )[0]
    child_src = src.split("def historical_recompute_worker_main", 1)[1].split(
        "def _isolated_child_main", 1
    )[0]
    assert "_evaluate_jobs_for_verification" in recompute_src
    assert "resolve_verification_workers" in recompute_src
    assert "_evaluate_jobs_multiprocess" in helper_src
    assert "_evaluate_planned_world_body" in helper_src
    mp_src = src.split("def _evaluate_jobs_multiprocess", 1)[1].split(
        "def _evaluate_jobs_for_verification", 1
    )[0]
    assert "evaluate_job_payload" in mp_src
    assert "multiprocessing_worker_init" in mp_src
    assert "_recompute_production_records_from_frozen_execution" in child_src
    auth_child = src.split("def authenticate_cached_records_worker_main", 1)[1].split(
        "def _job_from_record", 1
    )[0]
    assert "_evaluate_jobs_for_verification" in auth_child


def _crash_stub():
    return '''
def _evaluate_planned_world_body(scenario_id: str, n_rows: int, world_index: int):
    raise RuntimeError("injected verifier worker crash")
'''


def _malformed_stub():
    return '''
def _evaluate_planned_world_body(scenario_id: str, n_rows: int, world_index: int):
    return "not-a-record"
'''


def _duplicate_stub():
    return '''
def _evaluate_planned_world_body(scenario_id: str, n_rows: int, world_index: int):
    identity = world_identity("EASY", 80, 0)
    return {
        "scenario_id": "EASY",
        "n_rows": 80,
        "world_index": 0,
        "world_identity": identity,
        "world_seed": int(world_seed(identity)),
        "valid": True,
        "invalid_reasons": [],
        "stays_in_denominator": True,
    }
'''


def _unexpected_stub():
    return '''
def _evaluate_planned_world_body(scenario_id: str, n_rows: int, world_index: int):
    identity = world_identity("TINY_NOISY", 80, 99)
    return {
        "scenario_id": "TINY_NOISY",
        "n_rows": 80,
        "world_index": 99,
        "world_identity": identity,
        "world_seed": int(world_seed(identity)),
        "valid": True,
        "invalid_reasons": [],
        "stays_in_denominator": True,
    }
'''


def _wrong_identity_stub():
    return '''
def _evaluate_planned_world_body(scenario_id: str, n_rows: int, world_index: int):
    identity = world_identity(scenario_id, int(n_rows), int(world_index))
    return {
        "scenario_id": scenario_id,
        "n_rows": n_rows,
        "world_index": world_index,
        "world_identity": identity + "-stale",
        "world_seed": int(world_seed(identity)),
        "valid": True,
        "invalid_reasons": [],
        "stays_in_denominator": True,
    }
'''


@pytest.mark.parametrize(
    "stub_factory,match",
    [
        (_crash_stub, "failed closed|injected verifier worker crash|cached world records"),
        (_malformed_stub, "malformed|cached world records|failed closed"),
        (_duplicate_stub, "duplicate|identity|cached world records"),
        (_unexpected_stub, "unexpected|identity|cached world records"),
        (_wrong_identity_stub, "identity|cached world records"),
    ],
    ids=["crash", "malformed", "duplicate", "unexpected", "wrong_identity"],
)
def test_isolated_auth_parallel_fail_closed(tmp_path, monkeypatch, stub_factory, match):
    repo = _commit_production_tree(tmp_path)
    _install_eval_stub(repo, stub_factory())
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "verifier fail stub")
    _bind_prod(monkeypatch, repo)
    records = [_mock_record(*job) for job in TWO]
    with pytest.raises(SyntheticExecutionNotAuthorized, match=match):
        prod.authenticate_cached_world_records_from_frozen_execution(
            planned=TWO,
            records=records,
            repo_root=repo,
            production=False,
            workers=2,
        )


def test_isolated_auth_does_not_import_live_worktree(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _, records = _legit_records(tmp_path, repo, jobs=ONE)
    live = Path(prod.__file__).resolve()
    original = live.read_bytes()
    try:
        live.write_bytes(
            original.replace(
                b"def _evaluate_planned_world_body(",
                b"def _evaluate_planned_world_body_LIVE_TAMPER(",
                1,
            )
        )
        proof = prod.authenticate_cached_world_records_from_frozen_execution(
            planned=ONE,
            records=records,
            repo_root=repo,
            production=False,
            workers=2,
        )
        assert proof["observed_world_count"] == 1
        assert proof["verification_authority"] == "ISOLATED_FROZEN_GIT_EXECUTION"
    finally:
        live.write_bytes(original)


def test_worker_import_isolation_source_and_pin():
    src = Path(prod.__file__).read_text(encoding="utf-8")
    worker_path = Path(
        "scripts/research/harness_synthetic_edge_calibration_v1_worker.py"
    )
    worker_src = worker_path.read_text(encoding="utf-8")
    worker_bytes = worker_path.read_bytes()
    assert "_pin_frozen_package_sys_path" in worker_src
    assert "_assert_frozen_package_provenance" in worker_src
    mp_src = src.split("def _evaluate_jobs_multiprocess", 1)[1].split(
        "def _evaluate_jobs_for_verification", 1
    )[0]
    assert "evaluate_job_payload" in mp_src
    assert "multiprocessing_worker_init" in mp_src
    assert 'os.environ["PYTHONPATH"]' in mp_src
    assert "os.chdir(frozen_root)" in mp_src
    assert "sys.path.insert(0, frozen_root)" in mp_src
    assert "_spawn_verifier_evaluate_job" not in src
    assert prod.FROZEN_WORKER_SHA256 == __import__("hashlib").sha256(worker_bytes).hexdigest()
    assert prod.FROZEN_WORKER_SIZE == len(worker_bytes)
    assert "VERIFY_WORKERS_ENV" in src
    assert "resolve_verification_workers" in src
    tcb = prod.EXECUTION_AUTHORITY_PATHS
    assert prod.WORKER_REL in tcb
    assert prod.PRODUCTION_REL in tcb
    assert prod.LIB_REL in tcb
    assert prod.RUNNER_REL in tcb
    assert prod.AUTH_REL in tcb


def test_verification_workers_are_not_scientific_authority():
    src = Path(prod.__file__).read_text(encoding="utf-8")
    parent = src[
        src.index("def authenticate_cached_world_records_from_frozen_execution") : src.index(
            "\ndef _parse_authenticate_cached_records_proof"
        )
    ]
    assert "workers_n = resolve_verification_workers" in parent
    assert '"workers"' not in src[
        src.index("_AUTHENTICATE_CACHED_RECORDS_PROOF_KEYS") : src.index("DURABLE_PARTIAL_REL")
    ]
