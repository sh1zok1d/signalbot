"""BLOCKER-1 worker TCB and MAJOR-1 durable partial evidence.

Bounded NON-PRODUCTION fixtures only. Does not run the 3200-world grid,
consume ARM 0abc5fe, mint RESULT/WORLD_RECORDS, or touch B2-06 / 2025 / 2026.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.research import harness_synthetic_edge_calibration_v1_lib as lib
from scripts.research import harness_synthetic_edge_calibration_v1_production as prod
from scripts.research import harness_synthetic_edge_calibration_v1_worker as worker
from tests.research.test_harness_synthetic_edge_calibration_v1_production import (
    REPO,
    _authority_sha_map,
    _bind_prod,
    _commit_driver_freeze,
    _commit_production_tree,
    _git,
    _mock_record,
    _sha,
    _write,
)

OLD_ARM = "0abc5fe167e018ebe1f7efbb70694887ac095e17"
JOBS = (("EASY", 80, 0), ("NULL", 80, 1), ("MODERATE", 80, 2))
ONE = (("EASY", 80, 0),)


@pytest.fixture(autouse=True)
def _reset_durability_hook():
    prod._TEST_DURABILITY_HOOK = None
    yield
    prod._TEST_DURABILITY_HOOK = None


def _cheap_world(scenario_id: str, n_rows: int, world_index: int) -> dict:
    return _mock_record(scenario_id, n_rows, world_index)


def _bind_cheap_eval(monkeypatch) -> None:
    monkeypatch.setattr(prod, "_evaluate_planned_world_body", _cheap_world)


def _store(tmp_path: Path, repo: Path, jobs=JOBS) -> prod.DurablePartialWorldStore:
    bound = prod.verify_executed_production_authority(repo)
    return prod.DurablePartialWorldStore.open(
        tmp_path / "durable_partial",
        bound=bound,
        planned=jobs,
        repo_root=repo,
    )


def _world_bytes(records) -> bytes:
    return prod.canonical_json_bytes({"worlds": prod._jsonable(list(records))})


def test_execution_tcb_pins_worker_git_bytes(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    head = _git(repo, "rev-parse", "HEAD")
    manifest = prod.execution_tcb_manifest(repo_root=repo, execution_head=head)
    paths = [item["path"] for item in manifest["files"]]
    assert prod.WORKER_REL in paths
    assert prod.LIB_REL in paths
    assert prod.RUNNER_REL in paths
    assert prod.AUTH_REL in paths
    assert prod.PRODUCTION_REL in paths
    worker_row = next(item for item in manifest["files"] if item["path"] == prod.WORKER_REL)
    blob = subprocess.check_output(
        ["git", "-C", str(repo), "cat-file", "blob", f"HEAD:{prod.WORKER_REL}"]
    )
    assert worker_row["sha256"] == _sha(blob)
    assert worker_row["size"] == len(blob)
    assert worker_row["sha256"] == prod.FROZEN_WORKER_SHA256
    assert worker_row["size"] == prod.FROZEN_WORKER_SIZE
    bound = prod.verify_executed_production_authority(repo)
    assert bound["worker_sha256"] == prod.FROZEN_WORKER_SHA256
    assert bound["worker_path"] == prod.WORKER_REL
    assert bound["worker_size"] == str(prod.FROZEN_WORKER_SIZE)
    prod.assert_execution_tcb_current(manifest, repo_root=repo)


def test_worktree_worker_tamper_is_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    (repo / prod.WORKER_REL).write_bytes(_live_worker() + b"\n# worktree tamper\n")
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="worktree bytes differ|working tree is not clean",
    ):
        prod.verify_executed_production_authority(repo)


def test_tracked_worker_bytes_differ_from_frozen_authority(tmp_path, monkeypatch):
    repo = _commit_production_tree(
        tmp_path, extra={prod.WORKER_REL: _live_worker() + b"\n# tracked tamper\n"}
    )
    _bind_prod(monkeypatch, repo)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="pinned execution-TCB implementation",
    ):
        prod.verify_executed_production_authority(repo)


def test_worker_path_substitution_is_refused(tmp_path):
    alt = tmp_path / "substituted_worker.py"
    alt.write_bytes(_live_worker())
    with pytest.raises(RuntimeError, match="pinned execution path"):
        worker.assert_pinned_worker_bytes(prod.FROZEN_WORKER_SHA256, str(alt))


def test_caller_forged_worker_digest_and_size_are_refused():
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        prod.evaluate_planned_jobs_fail_closed(ONE, worker_sha256="0" * 64)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        prod.evaluate_planned_jobs_fail_closed(ONE, worker_size=1)
    with pytest.raises(RuntimeError, match="do not match tracked execution authority"):
        worker.assert_pinned_worker_bytes("0" * 64, str(Path(worker.__file__)))


def test_import_shadowing_is_refused(tmp_path):
    shadow = tmp_path / "shadow_worker.py"
    shadow.write_text(
        "def evaluate_job_payload(payload):\n    raise RuntimeError('shadow worker')\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="pinned execution path"):
        worker.assert_pinned_worker_bytes(prod.FROZEN_WORKER_SHA256, str(shadow))


def test_lib_substitution_is_refused_as_science_module(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    (repo / prod.LIB_REL).write_bytes((repo / prod.LIB_REL).read_bytes() + b"\n# tamper\n")
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="worktree bytes differ|working tree is not clean",
    ):
        prod.verify_executed_production_authority(repo)


def test_old_arm_does_not_authorize_live_or_tmp_head(tmp_path, monkeypatch):
    arm = json.loads(
        subprocess.check_output(
            ["git", "-C", str(REPO), "cat-file", "blob", f"{OLD_ARM}:{prod.CANONICAL_ARM_PATH}"]
        )
    )
    live = _git(REPO, "rev-parse", "HEAD")
    assert prod._arm_payload_authorizes_at_commit(REPO, live, arm) is False
    assert prod._arm_payload_authorizes_at_commit(REPO, OLD_ARM, arm) is False
    assert prod.production_monte_carlo_arm_authorized() is True
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    live_tmp = _git(repo, "rev-parse", "HEAD")
    assert prod._arm_payload_authorizes_at_commit(repo, live_tmp, arm) is False


def test_stale_authority_manifest_without_worker_is_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _commit_driver_freeze(repo)
    parent = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    freeze = json.loads((repo / prod.CANONICAL_DRIVER_FREEZE_PATH).read_text(encoding="utf-8"))
    listed = dict(_authority_sha_map(repo))
    listed.pop("worker", None)
    payload = {
        "production_monte_carlo_arm_authorized": True,
        "authorized_execution_commit": parent,
        "authorized_execution_tree": tree,
        "execution_authority_sha256": listed,
        "reviewed_implementation_head": freeze["reviewed_implementation_head"],
        "reviewed_implementation_tree": freeze["reviewed_implementation_tree"],
        "authorized_grid": prod.frozen_production_grid(),
        **prod.ARM_REQUIRED_LITERALS,
    }
    _write(repo / prod.CANONICAL_ARM_PATH, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "stale ARM missing worker")
    _bind_prod(monkeypatch, repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    head = _git(repo, "rev-parse", "HEAD")
    stale = prod.execution_tcb_manifest(repo_root=repo, execution_head=head)
    for item in stale["files"]:
        if item["path"] == prod.WORKER_REL:
            item["sha256"] = "ab" * 32
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="stale|does not match"):
        prod.assert_execution_tcb_current(stale, repo_root=repo)


def test_stale_tcb_head_is_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    head = _git(repo, "rev-parse", "HEAD")
    manifest = prod.execution_tcb_manifest(repo_root=repo, execution_head=head)
    manifest["execution_head"] = "0" * 40
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="stale"):
        prod.assert_execution_tcb_current(manifest, repo_root=repo)


def test_abort_with_partial_is_not_consumed(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _bind_cheap_eval(monkeypatch)
    store = _store(tmp_path, repo)
    prod._TEST_DURABILITY_HOOK = {"interrupt_after": 1}
    with pytest.raises(RuntimeError, match="interrupt after checkpoint"):
        prod.evaluate_planned_jobs_fail_closed(JOBS, durable_partial=store)
    identity = json.loads(store.identity_path.read_text(encoding="utf-8"))
    assert identity["not_a_production_result"] is True
    assert identity["not_canonical_world_records"] is True
    assert identity["authorization_consumed"] is False
    assert identity["calibration_complete"] is False
    assert identity["kind"] == prod.DURABLE_PARTIAL_KIND
    assert identity["kind"] != prod.WORLD_RECORDS_KIND
    assert (repo / prod.CANONICAL_RESULT_PATH).exists() is False
    assert (repo / prod.CANONICAL_WORLD_RECORDS_PATH).exists() is False
    durability = prod.production_durability_identity()
    assert durability["authorization_consumed"] is False
    assert durability["durable_partial_is_not_result"] is True


def test_crash_a_interrupt_after_zero(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _bind_cheap_eval(monkeypatch)
    store = _store(tmp_path, repo)
    prod._TEST_DURABILITY_HOOK = {"interrupt_after": 0}
    with pytest.raises(RuntimeError, match="interrupt after checkpoint"):
        prod.evaluate_planned_jobs_fail_closed(JOBS, durable_partial=store)
    prod._TEST_DURABILITY_HOOK = None
    assert store.load_verified_completed() == {}
    resumed = prod.evaluate_planned_jobs_fail_closed(JOBS, durable_partial=store)
    assert [ (r["scenario_id"], r["n_rows"], r["world_index"]) for r in resumed ] == list(JOBS)


def test_crash_b_and_c_interrupt_after_one_and_several(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _bind_cheap_eval(monkeypatch)
    store = _store(tmp_path, repo)
    prod._TEST_DURABILITY_HOOK = {"interrupt_after": 1}
    with pytest.raises(RuntimeError, match="interrupt after checkpoint"):
        prod.evaluate_planned_jobs_fail_closed(JOBS, durable_partial=store)
    prod._TEST_DURABILITY_HOOK = None
    assert len(store.load_verified_completed()) == 1
    store2 = _store(tmp_path / "several", repo)
    prod._TEST_DURABILITY_HOOK = {"interrupt_after": 2}
    with pytest.raises(RuntimeError, match="interrupt after checkpoint"):
        prod.evaluate_planned_jobs_fail_closed(JOBS, durable_partial=store2)
    prod._TEST_DURABILITY_HOOK = None
    assert len(store2.load_verified_completed()) == 2
    resumed = prod.evaluate_planned_jobs_fail_closed(JOBS, durable_partial=store2)
    assert len(resumed) == 3


def test_crash_d_during_checkpoint_write(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _bind_cheap_eval(monkeypatch)
    store = _store(tmp_path, repo)
    prod._TEST_DURABILITY_HOOK = {"crash_during_write": True}
    with pytest.raises(RuntimeError, match="crash during checkpoint write"):
        prod.evaluate_planned_jobs_fail_closed(JOBS, durable_partial=store)
    prod._TEST_DURABILITY_HOOK = None
    tmps = list(store.worlds_dir.glob("*.tmp"))
    assert tmps
    assert store.load_verified_completed() == {}
    resumed = prod.evaluate_planned_jobs_fail_closed(JOBS, durable_partial=store)
    assert len(resumed) == 3


def test_crash_e_worker_crash_before_completion(tmp_path, monkeypatch):
    head = _git(REPO, "rev-parse", "HEAD")
    bound = prod._bound_from_commit_blobs(REPO, head)
    store = prod.DurablePartialWorldStore.open(
        tmp_path / "durable_partial",
        bound=bound,
        planned=ONE,
        repo_root=REPO,
    )
    monkeypatch.setenv(worker.TEST_WORKER_CRASH_ENV, "1")
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="failed closed"):
        prod.evaluate_planned_jobs_fail_closed(ONE, workers=2, durable_partial=store)
    monkeypatch.delenv(worker.TEST_WORKER_CRASH_ENV)
    _bind_cheap_eval(monkeypatch)
    assert store.load_verified_completed() == {}
    resumed = prod.evaluate_planned_jobs_fail_closed(ONE, durable_partial=store)
    assert len(resumed) == 1


def test_crash_f_before_durable_checkpoint_ack(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _bind_cheap_eval(monkeypatch)
    store = _store(tmp_path, repo)
    prod._TEST_DURABILITY_HOOK = {"before_checkpoint": True}
    with pytest.raises(RuntimeError, match="before durable checkpoint"):
        prod.evaluate_planned_jobs_fail_closed(JOBS, durable_partial=store)
    prod._TEST_DURABILITY_HOOK = None
    assert store.load_verified_completed() == {}
    resumed = prod.evaluate_planned_jobs_fail_closed(JOBS, durable_partial=store)
    assert len(resumed) == 3


def test_crash_g_duplicate_persisted_world(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _bind_cheap_eval(monkeypatch)
    store = _store(tmp_path, repo)
    rec = _cheap_world(*JOBS[0])
    store.checkpoint_completed_world(rec, JOBS[0])
    payload = json.loads(next(store.worlds_dir.glob("*.json")).read_text(encoding="utf-8"))
    _write(store.worlds_dir / "duplicate.json", json.dumps(payload) + "\n")
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="duplicate persisted world"):
        store.load_verified_completed()


def test_crash_h_truncated_checkpoint(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _bind_cheap_eval(monkeypatch)
    store = _store(tmp_path, repo)
    rec = _cheap_world(*JOBS[0])
    store.checkpoint_completed_world(rec, JOBS[0])
    target = next(store.worlds_dir.glob("*.json"))
    target.write_bytes(b'{"kind": "DURABLE_PARTIAL_WORLD_EVIDENCE_RECORD"')
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="torn or malformed"):
        store.load_verified_completed()


def test_crash_i_modified_checkpoint_bytes(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _bind_cheap_eval(monkeypatch)
    store = _store(tmp_path, repo)
    rec = _cheap_world(*JOBS[0])
    store.checkpoint_completed_world(rec, JOBS[0])
    target = next(store.worlds_dir.glob("*.json"))
    payload = json.loads(target.read_text(encoding="utf-8"))
    payload["record"]["valid"] = not payload["record"]["valid"]
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="digest mismatch"):
        store.load_verified_completed()


def test_crash_j_checkpoint_from_wrong_head(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _bind_cheap_eval(monkeypatch)
    store = _store(tmp_path, repo)
    rec = _cheap_world(*JOBS[0])
    store.checkpoint_completed_world(rec, JOBS[0])
    payload = json.loads(store.identity_path.read_text(encoding="utf-8"))
    payload["execution_head"] = "0" * 40
    store.identity_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    bound = prod.verify_executed_production_authority(repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="frozen execution identity"):
        prod.DurablePartialWorldStore.open(
            store.path, bound=bound, planned=JOBS, repo_root=repo
        )


def test_crash_k_checkpoint_from_wrong_plan(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _bind_cheap_eval(monkeypatch)
    store = _store(tmp_path, repo)
    rec = _cheap_world(*JOBS[0])
    store.checkpoint_completed_world(rec, JOBS[0])
    other_plan = (("EASY", 80, 0), ("TINY_NOISY", 80, 0))
    bound = prod.verify_executed_production_authority(repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="frozen execution identity"):
        prod.DurablePartialWorldStore.open(
            store.path, bound=bound, planned=other_plan, repo_root=repo
        )


def test_crash_l_unexpected_world(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    _bind_cheap_eval(monkeypatch)
    store = _store(tmp_path, repo)
    rec = _cheap_world("TINY_NOISY", 80, 0)
    payload = {
        "kind": prod.DURABLE_PARTIAL_RECORD_KIND,
        "schema_version": 1,
        "completion_status": "COMPLETE",
        "execution_head": store.identity["execution_head"],
        "execution_tree": store.identity["execution_tree"],
        "run_identity": store.identity["run_identity"],
        "plan_sha256": store.identity["plan_sha256"],
        "scenario_id": "TINY_NOISY",
        "n_rows": 80,
        "world_index": 0,
        "world_identity": rec["world_identity"],
        "world_seed": rec["world_seed"],
        "record": rec,
        "record_sha256": prod._record_content_digest(rec),
        "record_size": len(prod.canonical_json_bytes(rec)),
    }
    _write(store.worlds_dir / "unexpected.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="unexpected persisted world"):
        store.load_verified_completed()


def test_crash_m_n_resume_matches_uninterrupted(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    jobs = (("EASY", 80, 0), ("NULL", 80, 1))
    uninterrupted = prod.evaluate_planned_jobs_fail_closed(jobs)
    store = _store(tmp_path, repo, jobs=jobs)
    prod._TEST_DURABILITY_HOOK = {"interrupt_after": 1}
    with pytest.raises(RuntimeError, match="interrupt after checkpoint"):
        prod.evaluate_planned_jobs_fail_closed(jobs, durable_partial=store)
    prod._TEST_DURABILITY_HOOK = None
    resumed = prod.evaluate_planned_jobs_fail_closed(jobs, durable_partial=store)
    assert _world_bytes(uninterrupted) == _world_bytes(resumed)
    assert prod._ordered_record_digest_chain(uninterrupted) == prod._ordered_record_digest_chain(
        resumed
    )
    assert [ (r["scenario_id"], r["n_rows"], r["world_index"]) for r in resumed ] == list(jobs)


def test_production_session_refuses_durability_hooks(monkeypatch):
    prod._TEST_DURABILITY_HOOK = {"interrupt_after": 1}
    session = prod._CanonicalExecutionSession()
    session.production = True
    session.jobs = ONE
    session.capability = None
    session.records = ()
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="cannot enter production"):
        prod._run_session_jobs(session, workers=1)


def test_partial_never_becomes_result_or_world_records():
    src = Path(prod.__file__).read_text(encoding="utf-8")
    assert "DURABLE_PARTIAL_WORLD_EVIDENCE" in src
    assert "not_a_production_result" in src
    assert "not_canonical_world_records" in src
    assert prod.DURABLE_PARTIAL_KIND != prod.WORLD_RECORDS_KIND
    assert prod.WORKER_REL in prod.EXECUTION_AUTHORITY_PATHS
    identity = prod.production_durability_identity()
    assert identity["canonical_paths"]["durable_partial_world_evidence"] == prod.DURABLE_PARTIAL_REL
    assert identity["durable_partial_is_not_result"] is True


def test_spawn_worker_pin_uses_git_not_caller_digest(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    digest, path = prod._spawn_worker_pin(repo)
    assert digest == prod.FROZEN_WORKER_SHA256
    assert Path(path).resolve() == (repo / prod.WORKER_REL).resolve()
    (repo / prod.WORKER_REL).write_bytes(_live_worker() + b"\n# pin tamper\n")
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="worktree worker bytes|executed worker bytes differ from git HEAD",
    ):
        prod._spawn_worker_pin(repo)


def _live_worker() -> bytes:
    return Path(REPO / prod.WORKER_REL).read_bytes()
