"""Execution ARM tests for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

Disposable-repo positive/negative controls plus live ARM identity checks.
These tests must not run the frozen 3200-world Monte Carlo, mint a live
production RESULT, consume production authority, access real market data,
open B2-06, or inspect 2025/2026.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts.research import harness_synthetic_edge_calibration_v1_lib as lib
from scripts.research import harness_synthetic_edge_calibration_v1_production as prod
from tests.research.test_harness_synthetic_edge_calibration_v1_production import (
    AUTH_MOD_PATH,
    FROZEN_LIB_SHA256,
    FROZEN_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256,
    LIB_PATH,
    PRODUCTION_PATH,
    REPO,
    RUNNER_PATH,
    _assert_clean,
    _authority_sha_map,
    _bind_prod,
    _commit_arm_authorizing_parent,
    _commit_production_tree,
    _git,
    _live_bytes,
    _write,
)

FREEZE_HEAD = "502a62ddee0a3106967b21f0095be7e1629a56b2"
FREEZE_TREE = "f21570983530f785d85639554741f3dd82164278"
ARM_PATH = REPO / prod.CANONICAL_ARM_PATH


def _arm_payload(repo: Path, **overrides) -> dict:
    payload = {
        "production_monte_carlo_arm_authorized": True,
        "authorized_execution_commit": _git(repo, "rev-parse", "HEAD"),
        "authorized_execution_tree": _git(repo, "rev-parse", "HEAD^{tree}"),
        "execution_authority_sha256": _authority_sha_map(repo),
        "authorized_run_count": 1,
        "unit_id": "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1",
    }
    payload.update(overrides)
    return payload


def _commit_arm(repo: Path, payload: dict, *, extra_files: dict[str, bytes] | None = None) -> None:
    _write(repo / prod.CANONICAL_ARM_PATH, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if extra_files:
        for rel, data in extra_files.items():
            _write(repo / rel, data)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "arm commit")


def _spawn_err(repo: Path, monkeypatch) -> tuple[int, str]:
    _bind_prod(monkeypatch, repo)
    proc = prod._spawn_isolated_child(prod.WORKER_MODE, repo_root=repo)
    return int(proc.returncode), proc.stderr or ""


def _arm_introducing_commit() -> str:
    log = _git(
        REPO,
        "log",
        "--diff-filter=A",
        "--format=%H",
        "--",
        prod.CANONICAL_ARM_PATH,
    )
    commits = [line.strip() for line in log.splitlines() if line.strip()]
    assert commits, "tracked ARM introducing commit is missing"
    return commits[-1]


def test_live_arm_authorizes_exact_freeze_parent(tmp_path, monkeypatch):
    assert ARM_PATH.is_file()
    payload = json.loads(ARM_PATH.read_text(encoding="utf-8"))
    arm_commit = _arm_introducing_commit()
    parent = _git(REPO, "rev-parse", f"{arm_commit}^")
    parent_tree = _git(REPO, "rev-parse", f"{arm_commit}^^{{tree}}")
    assert parent == FREEZE_HEAD
    assert parent_tree == FREEZE_TREE
    assert payload["production_monte_carlo_arm_authorized"] is True
    assert payload["authorized_execution_commit"] == FREEZE_HEAD
    assert payload["authorized_execution_tree"] == FREEZE_TREE
    assert payload["authorized_run_count"] == 1
    assert payload["unit_id"] == "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1"
    assert payload["scope"] == "production_synthetic_calibration_only"
    assert payload["authorized_grid"]["planned_worlds"] == 3200
    assert payload["frozen_lib_sha256"] == FROZEN_LIB_SHA256
    assert payload["prereg_json_sha256"] == FROZEN_PREREG_JSON_SHA256
    assert payload["prereg_md_sha256"] == FROZEN_PREREG_MD_SHA256
    assert payload["B2_06_scientific_execution_authorized"] is False
    assert payload["real_market_data_access_authorized"] is False
    assert payload["validation_2025_authorized"] is False
    assert payload["oos_2026_authorized"] is False
    assert payload["other_hypothesis_authorized"] is False
    assert payload["descendant_implementation_change_authorized"] is False
    assert payload["production_calibration_executed"] is False
    assert payload["production_result_minted"] is False
    assert payload["authorization_consumed"] is False
    clone = tmp_path / "arm_head"
    _git(REPO, "worktree", "add", "--detach", str(clone), arm_commit)
    try:
        _bind_prod(monkeypatch, clone)
        _assert_clean(clone)
        assert prod.production_monte_carlo_arm_authorized(clone) is True
        assert _git(clone, "rev-parse", "HEAD") == arm_commit
        assert _git(clone, "rev-parse", "HEAD^") == payload["authorized_execution_commit"]
    finally:
        subprocess.run(
            ["git", "-C", str(REPO), "worktree", "remove", "--force", str(clone)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def test_live_arm_does_not_execute_or_mint_or_consume():
    assert (REPO / prod.CANONICAL_RESULT_PATH).exists() is False
    assert (REPO / prod.CANONICAL_RESERVATION_PATH).exists() is False
    assert (REPO / prod.CANONICAL_CLAIM_PATH).exists() is False
    assert prod.production_durability_identity()["authorization_consumed"] is False
    assert prod.production_durability_identity()["production_result_minted"] is False
    payload = json.loads(ARM_PATH.read_text(encoding="utf-8"))
    assert payload["authorization_consumed"] is False
    assert payload["production_result_minted"] is False
    assert payload["production_calibration_executed"] is False
    # Do not invoke the live worker; disposable-repo tests cover ARM reachability
    # without consuming the tracked one-shot.


def test_artifacts_root_package_not_activated():
    assert not (REPO / "artifacts" / "__init__.py").exists()
    assert not (REPO / "artifacts" / "__init__.pyc").exists()
    source = Path(prod.__file__).read_text(encoding="utf-8")
    assert "ALLOWED_ROOT_DIRS" in source
    assert '"artifacts"' in prod.ISOLATED_CHILD_BOOTSTRAP
    assert "import artifacts" not in source
    assert "from artifacts" not in source


def test_correct_arm_commit_is_recognized(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    parent = _commit_arm_authorizing_parent(repo)
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is True
    assert _git(repo, "rev-parse", "HEAD^") == parent
    assert _git(repo, "rev-parse", "HEAD^^{tree}") == json.loads(
        (repo / prod.CANONICAL_ARM_PATH).read_text(encoding="utf-8")
    )["authorized_execution_tree"]
    rc, err = _spawn_err(repo, monkeypatch)
    assert rc == 2
    assert "armed production Monte Carlo is not part of this durability unit" in err
    assert "production_monte_carlo_arm_authorized=false" not in err
    assert (repo / prod.CANONICAL_RESULT_PATH).exists() is False


def test_wrong_parent_commit_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    payload = _arm_payload(repo, authorized_execution_commit="0" * 40)
    _commit_arm(repo, payload)
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    rc, err = _spawn_err(repo, monkeypatch)
    assert rc == 2
    assert "production_monte_carlo_arm_authorized=false" in err
    assert "working tree is not clean" not in err


def test_wrong_parent_tree_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    payload = _arm_payload(repo, authorized_execution_tree="0" * 40)
    _commit_arm(repo, payload)
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    rc, err = _spawn_err(repo, monkeypatch)
    assert rc == 2
    assert "production_monte_carlo_arm_authorized=false" in err
    assert "working tree is not clean" not in err


def test_modified_production_module_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    payload = _arm_payload(repo)
    _commit_arm(
        repo,
        payload,
        extra_files={PRODUCTION_PATH: _live_bytes(PRODUCTION_PATH) + b"\n# production tamper\n"},
    )
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    rc, err = _spawn_err(repo, monkeypatch)
    assert rc == 2
    assert "production_monte_carlo_arm_authorized=false" in err
    assert "working tree is not clean" not in err


def test_wrong_frozen_lib_digest_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    listed = dict(_authority_sha_map(repo))
    listed["lib"] = "ab" * 32
    payload = _arm_payload(repo, execution_authority_sha256=listed)
    _commit_arm(repo, payload)
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert listed["runner"] == _authority_sha_map(repo)["runner"]
    assert listed["production"] == _authority_sha_map(repo)["production"]
    assert listed["prereg_json"] == _authority_sha_map(repo)["prereg_json"]
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    rc, err = _spawn_err(repo, monkeypatch)
    assert rc == 2
    assert "production_monte_carlo_arm_authorized=false" in err
    assert "working tree is not clean" not in err


def test_wrong_prereg_digest_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    listed = dict(_authority_sha_map(repo))
    listed["prereg_json"] = "cd" * 32
    payload = _arm_payload(repo, execution_authority_sha256=listed)
    _commit_arm(repo, payload)
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert listed["lib"] == FROZEN_LIB_SHA256
    assert listed["prereg_md"] == FROZEN_PREREG_MD_SHA256
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    rc, err = _spawn_err(repo, monkeypatch)
    assert rc == 2
    assert "production_monte_carlo_arm_authorized=false" in err
    assert "working tree is not clean" not in err


def test_descendant_commit_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    parent = _commit_arm_authorizing_parent(repo)
    _bind_prod(monkeypatch, repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is True
    _write(repo / "docs/research/NOTE.txt", "descendant after ARM\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "descendant after ARM")
    _assert_clean(repo)
    assert _git(repo, "rev-parse", "HEAD^") != parent
    _git(repo, "merge-base", "--is-ancestor", parent, "HEAD")
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    rc, err = _spawn_err(repo, monkeypatch)
    assert rc == 2
    assert "production_monte_carlo_arm_authorized=false" in err
    assert "working tree is not clean" not in err


def test_arm_copied_into_another_checkout_identity_refused(tmp_path, monkeypatch):
    live = json.loads(ARM_PATH.read_text(encoding="utf-8"))
    repo = _commit_production_tree(tmp_path)
    _commit_arm(repo, live)
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert live["authorized_execution_commit"] == FREEZE_HEAD
    assert _git(repo, "rev-parse", "HEAD^") != FREEZE_HEAD
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    rc, err = _spawn_err(repo, monkeypatch)
    assert rc == 2
    assert "production_monte_carlo_arm_authorized=false" in err
    assert "working tree is not clean" not in err


def test_extra_implementation_change_between_parent_and_arm_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    payload = _arm_payload(repo)
    _commit_arm(
        repo,
        payload,
        extra_files={AUTH_MOD_PATH: _live_bytes(AUTH_MOD_PATH) + b"\n# extra auth change\n"},
    )
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert payload["authorized_execution_commit"] == _git(repo, "rev-parse", "HEAD^")
    assert payload["authorized_execution_tree"] == _git(repo, "rev-parse", "HEAD^^{tree}")
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    rc, err = _spawn_err(repo, monkeypatch)
    assert rc == 2
    assert "production_monte_carlo_arm_authorized=false" in err
    assert "working tree is not clean" not in err


def test_untracked_arm_substitution_does_not_authorize(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    payload = _arm_payload(repo)
    _write(repo / prod.CANONICAL_ARM_PATH, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _bind_prod(monkeypatch, repo)
    assert (repo / prod.CANONICAL_ARM_PATH).exists() is True
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    rc, err = _spawn_err(repo, monkeypatch)
    assert rc == 2
    assert "working tree is not clean" in err
    assert "production_monte_carlo_arm_authorized=false" not in err


def test_dirty_authority_substitution_cannot_execute(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _commit_arm_authorizing_parent(repo)
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is True
    (repo / PRODUCTION_PATH).write_bytes(_live_bytes(PRODUCTION_PATH) + b"\n# dirty worktree\n")
    assert prod.production_monte_carlo_arm_authorized(repo) is True
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="clean verified freeze|worktree"
    ):
        prod.verify_executed_production_authority(repo)
    rc, err = _spawn_err(repo, monkeypatch)
    assert rc == 2
    assert "working tree is not clean" in err
    assert "production_monte_carlo_arm_authorized=false" not in err
    assert (repo / prod.CANONICAL_RESULT_PATH).exists() is False


def test_skip_worktree_hiding_cannot_execute(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _commit_arm_authorizing_parent(repo)
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is True
    _git(repo, "update-index", "--skip-worktree", PRODUCTION_PATH)
    (repo / PRODUCTION_PATH).write_bytes(_live_bytes(PRODUCTION_PATH) + b"\n# hidden\n")
    assert _git(repo, "status", "--porcelain") == ""
    assert prod.production_monte_carlo_arm_authorized(repo) is True
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="skip-worktree|clean verified freeze"
    ):
        prod.verify_executed_production_authority(repo)
    rc, err = _spawn_err(repo, monkeypatch)
    assert rc == 2
    assert "skip-worktree/assume-unchanged" in err
    assert "production_monte_carlo_arm_authorized=false" not in err


def test_assume_unchanged_hiding_cannot_execute(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _commit_arm_authorizing_parent(repo)
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is True
    _git(repo, "update-index", "--assume-unchanged", PRODUCTION_PATH)
    (repo / PRODUCTION_PATH).write_bytes(_live_bytes(PRODUCTION_PATH) + b"\n# hidden\n")
    assert _git(repo, "status", "--porcelain") == ""
    assert prod.production_monte_carlo_arm_authorized(repo) is True
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="assume-unchanged|clean verified freeze"
    ):
        prod.verify_executed_production_authority(repo)
    rc, err = _spawn_err(repo, monkeypatch)
    assert rc == 2
    assert "skip-worktree/assume-unchanged" in err
    assert "production_monte_carlo_arm_authorized=false" not in err


def test_frozen_lib_and_prereg_bytes_unchanged():
    assert prod._sha256_bytes((REPO / LIB_PATH).read_bytes()) == FROZEN_LIB_SHA256
    assert prod._sha256_bytes(
        (REPO / "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json").read_bytes()
    ) == FROZEN_PREREG_JSON_SHA256
    assert prod._sha256_bytes(
        (REPO / "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md").read_bytes()
    ) == FROZEN_PREREG_MD_SHA256
    assert (REPO / PRODUCTION_PATH).read_bytes() == _git_blob(FREEZE_HEAD, PRODUCTION_PATH)
    assert (REPO / RUNNER_PATH).read_bytes() == _git_blob(FREEZE_HEAD, RUNNER_PATH)
    assert (REPO / AUTH_MOD_PATH).read_bytes() == _git_blob(FREEZE_HEAD, AUTH_MOD_PATH)
    assert (REPO / LIB_PATH).read_bytes() == _git_blob(FREEZE_HEAD, LIB_PATH)


def _git_blob(commit: str, rel: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(REPO), "cat-file", "blob", f"{commit}:{rel}"])
