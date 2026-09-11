"""Runtime ARM/freeze wiring against the performance/execution freeze.

Authorization-only. Does not start canonical production, mint RESULT, persist
WORLD_RECORDS, create a reservation/claim, or consume one-shot authority.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts.research import harness_synthetic_edge_calibration_v1_production as prod
from tests.research.test_harness_synthetic_edge_calibration_v1_production import (
    REPO,
    _bind_prod,
    _commit_arm_authorizing_parent,
    _commit_driver_freeze,
    _commit_performance_freeze,
    _commit_production_tree,
    _git,
    _write,
)

PERFORMANCE_ARM = "120ac456df3a22884c48eed45852bdd001706f54"
PERFORMANCE_FREEZE = "ccaffe135c2b8a9a0a75af30c0712ba3063b82f6"
OLD_ARM = "0abc5fe167e018ebe1f7efbb70694887ac095e17"
FREEZE_REL = prod.CANONICAL_PERFORMANCE_FREEZE_PATH
ARM_REL = prod.CANONICAL_ARM_PATH
PLAN_SHA256 = "5adf682ee48a868acbe01d9e0b9e33133db26089119396b3539b4e9cb8af5bb6"


def _blob(commit: str, rel: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO), "cat-file", "blob", f"{commit}:{rel}"])


def _live_arm() -> dict:
    return json.loads(_blob(PERFORMANCE_ARM, ARM_REL).decode("utf-8"))


def _old_arm() -> dict:
    return json.loads(_blob(OLD_ARM, ARM_REL).decode("utf-8"))


def test_runtime_source_keys_performance_freeze_not_driver_freeze_for_authorization():
    src = Path(prod.__file__).read_text(encoding="utf-8")
    assert "def _reviewed_implementation_binds_parent" in src
    reviewed = src.split("def _reviewed_implementation_binds_parent", 1)[1]
    reviewed = reviewed.split("def ", 1)[0]
    assert "_performance_freeze_binds_parent" in reviewed
    assert "_driver_freeze_binds_parent" not in reviewed


def test_old_driver_freeze_arm_refused():
    old = _old_arm()
    parent = subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", f"{OLD_ARM}^"], text=True
    ).strip()
    assert old["freeze_artifact_path"] == prod.CANONICAL_DRIVER_FREEZE_PATH
    assert prod._arm_payload_authorizes_at_commit(REPO, OLD_ARM, old) is False
    assert prod._driver_freeze_binds_parent(REPO, old, parent) is True


def test_old_arm_refused_at_live_and_performance_heads():
    old = _old_arm()
    assert prod._arm_payload_authorizes_at_commit(REPO, PERFORMANCE_FREEZE, old) is False
    assert prod._arm_payload_authorizes_at_commit(REPO, PERFORMANCE_ARM, old) is False
    live = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    assert prod._arm_payload_authorizes_at_commit(REPO, live, old) is False


def test_canonical_performance_freeze_topology_accepted_without_execution():
    arm = _live_arm()
    assert arm["freeze_artifact_path"] == FREEZE_REL
    assert arm["authorized_plan_sha256"] == PLAN_SHA256
    assert prod._arm_payload_authorizes_at_commit(REPO, PERFORMANCE_ARM, arm) is True
    live = subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()
    if live != PERFORMANCE_ARM:
        assert prod._arm_payload_authorizes_at_commit(REPO, live, arm) is False
        assert prod.production_monte_carlo_arm_authorized() is False
    assert (REPO / prod.CANONICAL_RESULT_PATH).exists() is False
    assert (REPO / prod.CANONICAL_WORLD_RECORDS_PATH).exists() is False


def test_fixture_performance_freeze_topology_accepted_without_execution(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    parent = _commit_arm_authorizing_parent(repo)
    _bind_prod(monkeypatch, repo)
    assert _git(repo, "rev-parse", "HEAD^") == parent
    assert prod.production_monte_carlo_arm_authorized(repo) is True
    assert (repo / prod.CANONICAL_RESULT_PATH).exists() is False
    assert (repo / prod.CANONICAL_WORLD_RECORDS_PATH).exists() is False
    assert (repo / prod.CANONICAL_RESERVATION_PATH).exists() is False
    assert (repo / prod.CANONICAL_CLAIM_PATH).exists() is False


def test_driver_freeze_fixture_cannot_arm_current_runtime(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _commit_driver_freeze(repo)
    parent = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    freeze = json.loads((repo / prod.CANONICAL_DRIVER_FREEZE_PATH).read_text(encoding="utf-8"))
    payload = {
        "production_monte_carlo_arm_authorized": True,
        "authorized_execution_commit": parent,
        "authorized_execution_tree": tree,
        "freeze_artifact_path": prod.CANONICAL_DRIVER_FREEZE_PATH,
        "freeze_artifact_sha256": hashlib.sha256(
            (repo / prod.CANONICAL_DRIVER_FREEZE_PATH).read_bytes()
        ).hexdigest(),
        "freeze_artifact_size": (repo / prod.CANONICAL_DRIVER_FREEZE_PATH).stat().st_size,
        "execution_authority_sha256": {
            "lib": prod.FROZEN_REVIEWED_LIB_SHA256,
            "runner": hashlib.sha256((repo / prod.RUNNER_REL).read_bytes()).hexdigest(),
            "auth": hashlib.sha256((repo / prod.AUTH_REL).read_bytes()).hexdigest(),
            "production": hashlib.sha256((repo / prod.PRODUCTION_REL).read_bytes()).hexdigest(),
            "worker": prod.FROZEN_WORKER_SHA256,
            "prereg_json": hashlib.sha256((repo / prod.PREREG_JSON_REL).read_bytes()).hexdigest(),
            "prereg_md": hashlib.sha256((repo / prod.PREREG_MD_REL).read_bytes()).hexdigest(),
        },
        "reviewed_implementation_head": freeze["reviewed_implementation_head"],
        "reviewed_implementation_tree": freeze["reviewed_implementation_tree"],
        "authorized_grid": prod.frozen_production_grid(),
        "authorized_plan_sha256": prod.planned_jobs_sha256(prod.planned_production_jobs()),
        **prod.ARM_REQUIRED_LITERALS,
    }
    _write(repo / ARM_REL, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "driver-freeze ARM")
    _bind_prod(monkeypatch, repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is False


def _armed_payload(repo: Path) -> dict:
    freeze_blob = (repo / FREEZE_REL).read_bytes()
    freeze = json.loads(freeze_blob.decode("utf-8"))
    parent = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    listed = {
        "lib": hashlib.sha256((repo / prod.LIB_REL).read_bytes()).hexdigest(),
        "runner": hashlib.sha256((repo / prod.RUNNER_REL).read_bytes()).hexdigest(),
        "auth": hashlib.sha256((repo / prod.AUTH_REL).read_bytes()).hexdigest(),
        "production": hashlib.sha256((repo / prod.PRODUCTION_REL).read_bytes()).hexdigest(),
        "worker": hashlib.sha256((repo / prod.WORKER_REL).read_bytes()).hexdigest(),
        "prereg_json": hashlib.sha256((repo / prod.PREREG_JSON_REL).read_bytes()).hexdigest(),
        "prereg_md": hashlib.sha256((repo / prod.PREREG_MD_REL).read_bytes()).hexdigest(),
    }
    return {
        "production_monte_carlo_arm_authorized": True,
        "authorized_execution_commit": parent,
        "authorized_execution_tree": tree,
        "freeze_parent_head": parent,
        "freeze_parent_tree": tree,
        "freeze_artifact_path": FREEZE_REL,
        "freeze_artifact_sha256": hashlib.sha256(freeze_blob).hexdigest(),
        "freeze_artifact_size": len(freeze_blob),
        "execution_authority_sha256": listed,
        "execution_tcb": freeze["execution_tcb"],
        "reviewed_implementation_head": freeze["reviewed_implementation_head"],
        "reviewed_implementation_tree": freeze["reviewed_implementation_tree"],
        "authorized_grid": prod.frozen_production_grid(),
        "authorized_plan_sha256": prod.planned_jobs_sha256(prod.planned_production_jobs()),
        **prod.ARM_REQUIRED_LITERALS,
    }


def _commit_arm_payload(repo: Path, payload: dict, message: str) -> str:
    _write(repo / ARM_REL, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.mark.parametrize(
    "mutator",
    [
        pytest.param(
            lambda p: p.__setitem__("freeze_artifact_sha256", "a" * 64),
            id="wrong_freeze_sha",
        ),
        pytest.param(
            lambda p: p.__setitem__("freeze_artifact_size", 1),
            id="wrong_freeze_size",
        ),
        pytest.param(
            lambda p: p.__setitem__("reviewed_implementation_head", "2" * 40),
            id="wrong_reviewed_head",
        ),
        pytest.param(
            lambda p: p["execution_authority_sha256"].__setitem__("lib", "b" * 64),
            id="wrong_tcb_digest",
        ),
        pytest.param(
            lambda p: p.__setitem__("authorized_plan_sha256", "c" * 64),
            id="wrong_plan_hash",
        ),
        pytest.param(
            lambda p: p.__setitem__("authorization_consumed", True),
            id="consumed_authority",
        ),
    ],
)
def test_tampered_performance_arm_refused(tmp_path, monkeypatch, mutator):
    repo = _commit_production_tree(tmp_path)
    _commit_performance_freeze(repo)
    payload = _armed_payload(repo)
    mutator(payload)
    arm_commit = _commit_arm_payload(repo, payload, "tampered ARM")
    _bind_prod(monkeypatch, repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    assert prod._arm_payload_authorizes_at_commit(repo, arm_commit, payload) is False


def test_wrong_performance_freeze_bytes_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _commit_performance_freeze(repo)
    freeze_path = repo / FREEZE_REL
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    freeze["frozen_lib_sha256"] = "ab" * 32
    _write(freeze_path, json.dumps(freeze, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "wrong performance freeze")
    payload = _armed_payload(repo)
    arm_commit = _commit_arm_payload(repo, payload, "ARM on wrong freeze")
    _bind_prod(monkeypatch, repo)
    assert prod._arm_payload_authorizes_at_commit(repo, arm_commit, payload) is False
    assert prod.production_monte_carlo_arm_authorized(repo) is False


def test_non_immediate_child_arm_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    parent = _commit_arm_authorizing_parent(repo)
    _bind_prod(monkeypatch, repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is True
    arm_commit = _git(repo, "rev-parse", "HEAD")
    _write(repo / "docs/research/NOTE.txt", "grandchild\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "non-immediate descendant")
    assert _git(repo, "rev-parse", "HEAD^") != parent
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    payload = json.loads((repo / ARM_REL).read_text(encoding="utf-8"))
    live = _git(repo, "rev-parse", "HEAD")
    assert prod._arm_payload_authorizes_at_commit(repo, live, payload) is False
    assert prod._arm_payload_authorizes_at_commit(repo, arm_commit, payload) is True


def test_authorization_tests_do_not_start_production():
    src = Path(__file__).read_text(encoding="utf-8")
    forbidden = (
        "run_canonical" + "_production_execution",
        "spawn_canonical" + "_production_process",
        "--run-production" + "-grid",
    )
    for token in forbidden:
        assert src.count(token) == 0
