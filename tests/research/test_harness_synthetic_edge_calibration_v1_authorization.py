"""Authorization-boundary tests for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

These tests never run the frozen 3200-world Monte Carlo and never access
real market data, B2-06, 2025, or 2026. They do not reserve the live checkout.
"""

from __future__ import annotations

import hashlib
import json
import threading
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
RESERVATION_PATH = auth.CANONICAL_RESERVATION_PATH
LIB_PATH = auth.LIB_REL
RUNNER_PATH = auth.RUNNER_REL
AUTH_MOD_PATH = auth.AUTH_REL


def _git(repo: Path, *args: str) -> str:
    import subprocess

    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _live_bytes(rel: str) -> bytes:
    return (REPO / rel).read_bytes()


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
            "json_sha256": _sha(PREREG_JSON.read_bytes()),
            "md_sha256": _sha(PREREG_MD.read_bytes()),
        },
        "frozen_implementation_identity": {
            "reviewed_implementation_commit": impl_commit,
            "reviewed_implementation_tree": impl_tree,
            "implementation_freeze_commit": impl_commit,
            "main_merge_commit": impl_commit,
            "lib_path": LIB_PATH,
            "lib_sha256_at_reviewed_implementation_commit": lib_sha,
        },
        "execution_authority": {
            "paths": [LIB_PATH, RUNNER_PATH, AUTH_MOD_PATH],
            "lib_sha256": _sha(_live_bytes(LIB_PATH)),
            "runner_sha256": _sha(_live_bytes(RUNNER_PATH)),
            "auth_sha256": _sha(_live_bytes(AUTH_MOD_PATH)),
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
            "durable_reservation_path": RESERVATION_PATH,
            "durable_claim_path": CLAIM_PATH,
            "transition": "AUTHORIZED_UNUSED -> RESERVED -> EXECUTED_CONSUMED or FAILED_CONSUMED",
            "second_run_policy": "fail_closed",
            "automatic_retry_authorized": False,
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
    _git(repo, "config", "commit.gpgsign", "false")
    _write(repo / PREREG_JSON.relative_to(REPO), PREREG_JSON.read_bytes())
    _write(repo / PREREG_MD.relative_to(REPO), PREREG_MD.read_bytes())
    _write(repo / LIB_PATH, _live_bytes(LIB_PATH))
    _write(repo / RUNNER_PATH, _live_bytes(RUNNER_PATH))
    _write(repo / AUTH_MOD_PATH, _live_bytes(AUTH_MOD_PATH))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "implementation freeze")
    impl_commit = _git(repo, "rev-parse", "HEAD")
    impl_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    lib_sha = _sha(_live_bytes(LIB_PATH))
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


def _bind_repo(monkeypatch, repo: Path) -> None:
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    monkeypatch.setattr(
        auth, "_executing_authority_file", lambda rel: (repo / rel).resolve()
    )


def _run_prod():
    return auth.run_authorized_production_grid()


def test_no_authorization_artifact_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="authorization artifact absent"):
        _run_prod()


def test_malformed_authorization_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    _write(repo / AUTH_PATH, "{not-json")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "malformed auth")
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="malformed"):
        _run_prod()


def test_wrong_unit_id_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    impl_commit = _git(repo, "rev-parse", "HEAD")
    impl_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = _auth_payload(
        impl_commit=impl_commit,
        impl_tree=impl_tree,
        lib_sha=_sha(_live_bytes(LIB_PATH)),
        unit_id="WRONG_UNIT",
    )
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "wrong unit")
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="wrong unit_id"):
        _run_prod()


def test_wrong_prereg_identity_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    impl_commit = _git(repo, "rev-parse", "HEAD")
    impl_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = _auth_payload(
        impl_commit=impl_commit,
        impl_tree=impl_tree,
        lib_sha=_sha(_live_bytes(LIB_PATH)),
    )
    payload["frozen_prereg_identity"]["json_sha256"] = "ab" * 32
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "wrong prereg")
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="wrong prereg"):
        _run_prod()


def test_wrong_implementation_identity_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    payload = _auth_payload(
        impl_commit="deadbeef" * 5,
        impl_tree="cafebabe" * 5,
        lib_sha=_sha(_live_bytes(LIB_PATH)),
    )
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "wrong implementation")
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="implementation"):
        _run_prod()


def test_modified_production_grid_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    impl_commit = _git(repo, "rev-parse", "HEAD")
    impl_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = _auth_payload(
        impl_commit=impl_commit,
        impl_tree=impl_tree,
        lib_sha=_sha(_live_bytes(LIB_PATH)),
    )
    payload["authorized_grid"]["planned_worlds"] = 3199
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "mutated grid")
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="modified production grid"):
        _run_prod()


def test_caller_kwargs_cannot_bypass(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    _bind_repo(monkeypatch, repo)
    for kwargs in (
        {"authorized": True},
        {"force": True},
        {"unsafe": True},
        {"authority_path": str(tmp_path / "evil.json")},
    ):
        with pytest.raises(lib.SyntheticExecutionNotAuthorized):
            lib.run_frozen_production_grid(**kwargs)
        with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
            auth.run_authorized_production_grid(**kwargs)


def test_env_var_cannot_bypass(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    _bind_repo(monkeypatch, repo)
    monkeypatch.setenv("SYNTHETIC_EXECUTION_AUTHORIZED", "true")
    monkeypatch.setenv("HARNESS_FORCE", "1")
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="authorization artifact absent"):
        _run_prod()
    source = Path(auth.__file__).read_text(encoding="utf-8")
    assert "os.environ" not in source
    assert "getenv" not in source


def test_worktree_authority_path_cannot_substitute_head(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    evil = _auth_payload(
        impl_commit=_git(repo, "rev-parse", "HEAD"),
        impl_tree=_git(repo, "rev-parse", "HEAD^{tree}"),
        lib_sha=_sha(_live_bytes(LIB_PATH)),
    )
    _write(repo / AUTH_PATH, json.dumps(evil, indent=2) + "\n")
    _bind_repo(monkeypatch, repo)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="not a clean verified freeze|authorization artifact absent",
    ):
        _run_prod()


def test_valid_authorization_reaches_unarmed_execution_boundary(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    _bind_repo(monkeypatch, repo)
    with pytest.raises(auth.AuthorizedExecutionBoundaryReached) as excinfo:
        _run_prod()
    diagnostics = excinfo.value.diagnostics
    assert excinfo.value.proof is None
    assert diagnostics.monte_carlo_invoked is False
    assert diagnostics.reservation_lifecycle == auth.LIFECYCLE_RESERVED
    plan = auth.production_world_plan()
    assert len(plan) == 3200
    assert plan[0] == ("NULL", 5000, 0)
    assert plan[399] == ("NULL", 5000, 399)
    assert plan[400] == ("EASY", 5000, 0)
    assert plan[-1] == ("SMALL", 10000, 399)
    reservation = json.loads((repo / RESERVATION_PATH).read_text(encoding="utf-8"))
    assert reservation["lifecycle"] == auth.LIFECYCLE_RESERVED
    assert reservation["automatic_retry_authorized"] is False


def test_consumed_authorization_second_run_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None, include_claim=True)
    _bind_repo(monkeypatch, repo)
    with pytest.raises(auth.AuthorizationConsumed, match="consumed"):
        _run_prod()


def test_real_market_and_holdout_flags_remain_false(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    impl_commit = _git(repo, "rev-parse", "HEAD")
    impl_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = _auth_payload(
        impl_commit=impl_commit,
        impl_tree=impl_tree,
        lib_sha=_sha(_live_bytes(LIB_PATH)),
        real_market_data_access_authorized=True,
    )
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "market flag")
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="real_market"):
        _run_prod()


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
        lib_sha=_sha(_live_bytes(LIB_PATH)),
        **{flag: True},
    )
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", flag)
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match=flag):
        _run_prod()


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
    with pytest.raises(lib.SyntheticExecutionNotAuthorized):
        lib.run_frozen_production_grid()


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
    assert ident["synthetic_execution_authorized"] is False


def test_worktree_scientific_lib_tamper_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    (repo / LIB_PATH).write_bytes(_live_bytes(LIB_PATH) + b"\n# tamper\n")
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="clean verified freeze|worktree"):
        _run_prod()


def test_worktree_entrypoint_tamper_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    (repo / RUNNER_PATH).write_bytes(_live_bytes(RUNNER_PATH) + b"\n# tamper\n")
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="clean verified freeze|worktree"):
        _run_prod()


def test_worktree_auth_wrapper_tamper_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    (repo / AUTH_MOD_PATH).write_bytes(_live_bytes(AUTH_MOD_PATH) + b"\n# tamper\n")
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="clean verified freeze|worktree"):
        _run_prod()


def test_descendant_scientific_lib_change_refuses_even_if_reviewed_is_ancestor(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    payload = json.loads((repo / AUTH_PATH).read_text(encoding="utf-8"))
    reviewed = payload["frozen_implementation_identity"]["reviewed_implementation_commit"]
    mutated = _live_bytes(LIB_PATH) + b"\n# descendant scientific change\n"
    (repo / LIB_PATH).write_bytes(mutated)
    payload["execution_authority"]["lib_sha256"] = _sha(mutated)
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "descendant lib change")
    _git(repo, "merge-base", "--is-ancestor", reviewed, "HEAD")
    _bind_repo(monkeypatch, repo)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="frozen reviewed implementation|differs from frozen reviewed",
    ):
        _run_prod()


def test_skip_worktree_bypass_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    _git(repo, "update-index", "--skip-worktree", LIB_PATH)
    (repo / LIB_PATH).write_bytes(_live_bytes(LIB_PATH) + b"\n# hidden\n")
    assert _git(repo, "status", "--porcelain") == ""
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="skip-worktree|clean verified freeze"):
        _run_prod()


def test_assume_unchanged_bypass_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    _git(repo, "update-index", "--assume-unchanged", LIB_PATH)
    (repo / LIB_PATH).write_bytes(_live_bytes(LIB_PATH) + b"\n# hidden\n")
    assert _git(repo, "status", "--porcelain") == ""
    _bind_repo(monkeypatch, repo)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="assume-unchanged|clean verified freeze"
    ):
        _run_prod()


def test_sequential_second_reservation_fails(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    _bind_repo(monkeypatch, repo)
    with pytest.raises(auth.AuthorizedExecutionBoundaryReached):
        _run_prod()
    with pytest.raises(auth.AuthorizationConsumed):
        _run_prod()


def test_concurrent_reservation_has_exactly_one_winner(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    _bind_repo(monkeypatch, repo)
    original = auth._atomic_create_exclusive
    barrier = threading.Barrier(8)
    def racing(path, data):
        barrier.wait(timeout=10)
        return original(path, data)

    monkeypatch.setattr(auth, "_atomic_create_exclusive", racing)
    results: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            _run_prod()
            outcome = "returned"
        except auth.AuthorizedExecutionBoundaryReached:
            outcome = "winner"
        except auth.AuthorizationConsumed:
            outcome = "consumed"
        except lib.SyntheticExecutionNotAuthorized:
            outcome = "refused"
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    assert len(results) == 8
    assert results.count("winner") == 1
    assert results.count("returned") == 0
    assert results.count("winner") + results.count("consumed") + results.count("refused") == 8


def test_failure_after_reservation_consumes_authorization(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    _bind_repo(monkeypatch, repo)

    def boom(_reservation):
        raise RuntimeError("simulated production failure after reservation")

    monkeypatch.setattr(auth, "_production_monte_carlo_seam", boom)
    with pytest.raises(RuntimeError, match="simulated production failure"):
        _run_prod()
    reservation = json.loads((repo / RESERVATION_PATH).read_text(encoding="utf-8"))
    assert reservation["lifecycle"] == auth.LIFECYCLE_FAILED_CONSUMED
    with pytest.raises(auth.AuthorizationConsumed):
        _run_prod()


def test_successful_attempt_state_is_consumed(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    _bind_repo(monkeypatch, repo)
    with pytest.raises(auth.AuthorizedExecutionBoundaryReached):
        _run_prod()
    state = auth.describe_authorization_state()
    assert state["lifecycle"] == auth.LIFECYCLE_RESERVED
    assert state["authorization_consumed"] is True
    assert state["synthetic_execution_authorized"] is False


def test_uncommitted_claim_consumes_authorization(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    _write(
        repo / CLAIM_PATH,
        json.dumps({"authorization_id": auth.AUTHORIZATION_ID, "authorization_consumed": True}),
    )
    _bind_repo(monkeypatch, repo)
    with pytest.raises(auth.AuthorizationConsumed):
        _run_prod()


def test_reservation_bound_to_wrong_authorization_fails(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    _write(
        repo / RESERVATION_PATH,
        json.dumps(
            {
                "lifecycle": auth.LIFECYCLE_RESERVED,
                "authorization_blob_sha256": "ab" * 32,
                "authorization_id": "WRONG",
            }
        )
        + "\n",
    )
    _bind_repo(monkeypatch, repo)
    with pytest.raises(auth.AuthorizationConsumed):
        _run_prod()


def test_reservation_and_claim_path_substitution_refuses(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=False, payload=None)
    impl_commit = _git(repo, "rev-parse", "HEAD")
    impl_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = _auth_payload(
        impl_commit=impl_commit,
        impl_tree=impl_tree,
        lib_sha=_sha(_live_bytes(LIB_PATH)),
    )
    payload["consumption"]["durable_reservation_path"] = "docs/research/evil_reservation.json"
    payload["consumption"]["durable_claim_path"] = "docs/research/evil_claim.json"
    _write(repo / AUTH_PATH, json.dumps(payload, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "path substitution")
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="path is not canonical"):
        _run_prod()


def test_manually_constructed_proof_cannot_alter_production_behavior():
    forged = auth.VerifiedProductionAuthorization(
        authorization_id=auth.AUTHORIZATION_ID,
        authorization_blob_sha256="ab" * 32,
        head_sha="cd" * 20,
        tree_sha="ef" * 20,
        unit_id=lib.UNIT_ID,
        grid={
            **auth._literal_grid(),
            "root_seed": 999,
            "primary_n_rows": 123,
            "planned_worlds": 7,
        },
        lifecycle=auth.LIFECYCLE_AUTHORIZED_UNUSED,
        _mint=auth._MINT,
    )
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="proof objects cannot authorize"):
        forged.assert_minted()
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        auth.production_world_plan(forged)
    plan = auth.production_world_plan()
    assert plan[0] == ("NULL", 5000, 0)
    assert plan[-1] == ("SMALL", 10000, 399)
    assert len(plan) == 3200


def test_imported_mint_token_cannot_authorize_altered_grid():
    forged = auth.VerifiedProductionAuthorization(
        authorization_id=auth.AUTHORIZATION_ID,
        authorization_blob_sha256="00" * 32,
        head_sha="11" * 20,
        tree_sha="22" * 20,
        unit_id=lib.UNIT_ID,
        grid={**auth._literal_grid(), "root_seed": 999, "small_sensitivity_n": [1, 2]},
        lifecycle=auth.LIFECYCLE_AUTHORIZED_UNUSED,
        _mint=auth._MINT,
    )
    plan = auth.production_world_plan()
    assert all(job[1] in {2500, 5000, 10000} for job in plan)
    assert plan[0][1] == 5000
    with pytest.raises(lib.SyntheticExecutionNotAuthorized):
        auth._require_frozen_grid(forged.grid)


def test_forged_root_seed_does_not_control_world_plan():
    forged_grid = {**auth._literal_grid(), "root_seed": 999}
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="frozen authority"):
        auth._require_frozen_grid(forged_grid)
    plan = auth.production_world_plan()
    assert lib.ROOT_SEED == 20260908
    assert plan[0] == ("NULL", 5000, 0)


def test_forged_n_values_are_rejected_or_ignored():
    forged = {**auth._literal_grid(), "primary_n_rows": 1, "small_sensitivity_n": [2, 3]}
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="frozen authority"):
        auth._require_frozen_grid(forged)
    plan = auth.production_world_plan()
    assert {job[1] for job in plan} == {2500, 5000, 10000}


def test_production_world_plan_rederives_frozen_grid():
    plan = auth.production_world_plan()
    grid = auth._expected_grid()
    assert grid["root_seed"] == 20260908
    assert grid["planned_worlds"] == 3200
    assert len(plan) == grid["planned_worlds"]


def test_production_seam_independently_rejects_grid_mismatch(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    _bind_repo(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="frozen authority"):
        auth._production_monte_carlo_seam(
            {
                "grid": {**auth._literal_grid(), "planned_worlds": 1},
                "authorization_blob_sha256": "ab" * 32,
                "head_sha": "cd" * 20,
                "tree_sha": "ef" * 20,
                "lifecycle": auth.LIFECYCLE_RESERVED,
                "run_identity": "nope",
            }
        )


def test_captured_boundary_does_not_export_reusable_proof(tmp_path, monkeypatch):
    repo = _commit_tree(tmp_path, include_auth=True, payload=None)
    _bind_repo(monkeypatch, repo)
    with pytest.raises(auth.AuthorizedExecutionBoundaryReached) as excinfo:
        _run_prod()
    captured = excinfo.value
    assert captured.proof is None
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        auth.run_authorized_production_grid(proof=captured)
    with pytest.raises(auth.AuthorizationConsumed):
        _run_prod()
