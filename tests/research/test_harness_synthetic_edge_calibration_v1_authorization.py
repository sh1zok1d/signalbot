"""Authorization-boundary tests for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

These tests never run the frozen 3200-world Monte Carlo and never access
real market data, B2-06, 2025, or 2026.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts.research import harness_synthetic_edge_calibration_v1 as runner
from scripts.research import harness_synthetic_edge_calibration_v1_auth as auth
from scripts.research import harness_synthetic_edge_calibration_v1_lib as lib

REPO = Path(__file__).resolve().parents[2]
PREREG_JSON = REPO / "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json"
PREREG_MD = REPO / "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md"
AUTH_PATH = auth.CANONICAL_AUTHORIZATION_PATH
CLAIM_PATH = auth.CANONICAL_CLAIM_PATH
LIB_PATH = "scripts/research/harness_synthetic_edge_calibration_v1_lib.py"
LIB_STUB = b"frozen-reviewed-lib-bytes\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)


def _auth_payload(*, impl_commit: str, impl_tree: str, lib_sha: str, **overrides) -> dict:
    payload = {
        "schema_version": "1.0",
        "unit_id": lib.UNIT_ID,
        "authorization_id": auth.AUTHORIZATION_ID,
        "status": "AUTHORIZED_FOR_ONE_PRODUCTION_EXECUTION",
        "lifecycle": "AUTHORIZED_UNUSED",
        "authorized_run_count": 1,
        "frozen_prereg_identity": {
            "json_path": "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json",
            "md_path": "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md",
            "json_sha256": hashlib.sha256(PREREG_JSON.read_bytes()).hexdigest(),
            "md_sha256": hashlib.sha256(PREREG_MD.read_bytes()).hexdigest(),
        },
        "frozen_implementation_identity": {
            "reviewed_implementation_commit": impl_commit,
            "reviewed_implementation_tree": impl_tree,
            "implementation_freeze_commit": impl_commit,
            "main_merge_commit": impl_commit,
            "lib_path": LIB_PATH,
            "lib_sha256_at_reviewed_implementation_commit": lib_sha,
        },
        "authorized_grid": {
            "planned_worlds": 3200,
            "worlds_per_cell": 400,
            "scenario_ids": [
                "NULL",
                "EASY",
                "MODERATE",
                "SMALL",
                "TINY_NOISY",
                "NONSTATIONARY_TRAP",
            ],
            "root_seed": 20260908,
            "primary_n_rows": 5000,
            "small_sensitivity_n": [2500, 10000],
            "bootstrap_replicates": 500,
            "placebo_replicates": 999,
            "visibility_replicates": 500,
            "block_rows": 50,
        },
        "synthetic_execution_authorized": True,
        "production_calibration_executed": False,
        "authorization_consumed": False,
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
        "consumption": {
            "durable_claim_path": CLAIM_PATH,
            "transition": "AUTHORIZED_UNUSED -> production execution -> immutable RESULT/claim -> AUTHORIZATION_CONSUMED",
            "second_run_policy": "fail_closed",
        },
        "authorization_commit_binding": {
            "canonical_path": AUTH_PATH,
        },
    }
    payload.update(overrides)
    return payload


def _commit_tree(
    tmp_path: Path,
    *,
    include_auth: bool,
    payload: dict | None,
    include_claim: bool = False,
) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    _write(repo / PREREG_JSON.relative_to(REPO), PREREG_JSON.read_bytes())
    _write(repo / PREREG_MD.relative_to(REPO), PREREG_MD.read_bytes())
    _write(repo / LIB_PATH, LIB_STUB)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "implementation freeze")
    impl_commit = _git(repo, "rev-parse", "HEAD")
    impl_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    lib_sha = hashlib.sha256(LIB_STUB).hexdigest()
    if include_auth:
        body = payload
        if body is None:
            body = _auth_payload(impl_commit=impl_commit, impl_tree=impl_tree, lib_sha=lib_sha)
        _write(repo / AUTH_PATH, json.dumps(body, indent=2) + "\n")
    if include_claim:
        _write(
            repo / CLAIM_PATH,
            json.dumps(
                {
                    "authorization_id": auth.AUTHORIZATION_ID,
                    "authorization_consumed": True,
                    "production_calibration_executed": True,
                }
            ),
        )
    if include_auth or include_claim:
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", "authorization overlay")
    return repo


def test_no_authorization_artifact_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="authorization artifact absent"):
        lib.run_frozen_production_grid()


def test_malformed_authorization_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    _write(repo / AUTH_PATH, "{not-json")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "malformed auth")
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="malformed"):
        lib.run_frozen_production_grid()


def test_wrong_unit_id_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    impl_commit = _git(repo, "rev-parse", "HEAD")
    impl_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = _auth_payload(
        impl_commit=impl_commit,
        impl_tree=impl_tree,
        lib_sha=hashlib.sha256(LIB_STUB).hexdigest(),
        unit_id="WRONG_UNIT",
    )
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "wrong unit")
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="wrong unit_id"):
        lib.run_frozen_production_grid()


def test_wrong_prereg_identity_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    impl_commit = _git(repo, "rev-parse", "HEAD")
    impl_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = _auth_payload(
        impl_commit=impl_commit,
        impl_tree=impl_tree,
        lib_sha=hashlib.sha256(LIB_STUB).hexdigest(),
    )
    payload["frozen_prereg_identity"]["json_sha256"] = "ab" * 32
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "wrong prereg")
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="wrong prereg"):
        lib.run_frozen_production_grid()


def test_wrong_implementation_identity_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    payload = _auth_payload(
        impl_commit="deadbeef" * 5,
        impl_tree="cafebabe" * 5,
        lib_sha=hashlib.sha256(LIB_STUB).hexdigest(),
    )
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "wrong implementation")
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="implementation"):
        lib.run_frozen_production_grid()


def test_modified_production_grid_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    impl_commit = _git(repo, "rev-parse", "HEAD")
    impl_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = _auth_payload(
        impl_commit=impl_commit,
        impl_tree=impl_tree,
        lib_sha=hashlib.sha256(LIB_STUB).hexdigest(),
    )
    payload["authorized_grid"]["planned_worlds"] = 3199
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "mutated grid")
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="modified production grid"):
        lib.run_frozen_production_grid()


def test_caller_kwargs_cannot_bypass(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    for kwargs in (
        {"authorized": True},
        {"force": True},
        {"unsafe": True},
        {"authority_path": str(tmp_path / "evil.json")},
    ):
        with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
            lib.run_frozen_production_grid(**kwargs)


def test_env_var_cannot_bypass(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    monkeypatch.setenv("SYNTHETIC_EXECUTION_AUTHORIZED", "true")
    monkeypatch.setenv("HARNESS_FORCE", "1")
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="authorization artifact absent"):
        lib.run_frozen_production_grid()
    source = Path(auth.__file__).read_text(encoding="utf-8")
    assert "os.environ" not in source
    assert "getenv" not in source


def test_worktree_authority_path_cannot_substitute_head(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    evil = _auth_payload(
        impl_commit=_git(repo, "rev-parse", "HEAD"),
        impl_tree=_git(repo, "rev-parse", "HEAD^{tree}"),
        lib_sha=hashlib.sha256(LIB_STUB).hexdigest(),
    )
    _write(repo / AUTH_PATH, json.dumps(evil, indent=2) + "\n")
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="authorization artifact absent"):
        lib.run_frozen_production_grid()


def test_valid_authorization_reaches_unarmed_execution_boundary(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    with pytest.raises(auth.AuthorizedExecutionBoundaryReached) as excinfo:
        lib.run_frozen_production_grid()
    proof = excinfo.value.proof
    proof.assert_minted()
    plan = auth.production_world_plan(proof)
    assert len(plan) == 3200
    assert plan[0] == ("NULL", 5000, 0)
    assert plan[399] == ("NULL", 5000, 399)
    assert plan[400] == ("EASY", 5000, 0)
    assert plan[-1] == ("SMALL", 10000, 399)
    assert proof.lifecycle == auth.LIFECYCLE_AUTHORIZED_UNUSED


def test_consumed_authorization_second_run_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None, include_claim=True)
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    with pytest.raises(auth.AuthorizationConsumed, match="consumed"):
        lib.run_frozen_production_grid()


def test_real_market_and_holdout_flags_remain_false(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    impl_commit = _git(repo, "rev-parse", "HEAD")
    impl_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = _auth_payload(
        impl_commit=impl_commit,
        impl_tree=impl_tree,
        lib_sha=hashlib.sha256(LIB_STUB).hexdigest(),
        real_market_data_access_authorized=True,
    )
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "market flag")
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="real_market"):
        lib.run_frozen_production_grid()


@pytest.mark.parametrize(
    "flag",
    [
        "b2_06_scientific_execution_authorized",
        "validation_2025_authorized",
        "oos_2026_authorized",
    ],
)
def test_authorization_does_not_permit_b2_06_or_holdouts(tmp_path, monkeypatch, flag):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    impl_commit = _git(repo, "rev-parse", "HEAD")
    impl_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = _auth_payload(
        impl_commit=impl_commit,
        impl_tree=impl_tree,
        lib_sha=hashlib.sha256(LIB_STUB).hexdigest(),
        **{flag: True},
    )
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", flag)
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match=flag):
        lib.run_frozen_production_grid()


def test_fixture_execution_semantics_remain_unchanged():
    cfg = lib.FixtureExecutionConfig(
        n_rows=50,
        scenario_id="EASY",
        visibility_replicates=3,
        bootstrap_replicates=3,
        placebo_replicates=3,
        block_rows=5,
    )
    out = lib.evaluate_fixture_world(cfg)
    assert out["stays_in_denominator"] is True
    assert len(out["candidates"]) == 10
    with pytest.raises(lib.SyntheticExecutionNotAuthorized):
        lib.FixtureExecutionConfig(
            n_rows=5000,
            scenario_id="EASY",
            visibility_replicates=500,
            bootstrap_replicates=500,
            placebo_replicates=999,
        )


def test_auth_modules_have_no_real_data_path():
    source = (
        Path(auth.__file__).read_text(encoding="utf-8")
        + Path(lib.__file__).read_text(encoding="utf-8")
        + Path(runner.__file__).read_text(encoding="utf-8")
    )
    for token in (
        "parquet",
        "CORE_BTC",
        "authorize_dataset",
        "prepare_batch02",
        "b2_06_evaluator",
        "--authorize",
        "--force",
        "--unsafe",
    ):
        assert token not in source
    ident = lib.implementation_identity()
    assert ident["real_data_path"] is False
    assert ident["b2_06_scientific_execution_authorized"] is False
    assert ident["validation_2025_authorized"] is False
    assert ident["oos_2026_authorized"] is False
    assert ident["production_calibration_executed"] is False
    assert ident["monte_carlo_armed"] is False
