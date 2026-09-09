"""Production durability tests for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

Tiny synthetic fixtures and mocked 3200-world records only. These tests must
not run the frozen 3200-world Monte Carlo, mint a live production RESULT, access
real market data, open B2-06, or inspect 2025/2026.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from scripts.research import harness_synthetic_edge_calibration_v1 as runner
from scripts.research import harness_synthetic_edge_calibration_v1_auth as auth
from scripts.research import harness_synthetic_edge_calibration_v1_lib as lib
from scripts.research import harness_synthetic_edge_calibration_v1_production as prod

REPO = Path(__file__).resolve().parents[2]
PREREG_JSON = REPO / "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json"
PREREG_MD = REPO / "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md"
LIB_PATH = prod.LIB_REL
RUNNER_PATH = prod.RUNNER_REL
AUTH_MOD_PATH = prod.AUTH_REL
PRODUCTION_PATH = prod.PRODUCTION_REL
FROZEN_LIB_SHA256 = "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
FROZEN_PREREG_JSON_SHA256 = (
    "78fcddf03ce84a0369a955d5b571c2423129d12b22e35f77eab26d6ac5eff708"
)
FROZEN_PREREG_MD_SHA256 = (
    "a54c838d2b4903f039b4fd39d79198415ce095f5a9726fc51949cbb47153e5a3"
)


def _git(repo: Path, *args: str) -> str:
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


def _commit_production_tree(tmp_path: Path, *, extra: dict[str, bytes] | None = None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "test")
    _git(repo, "config", "commit.gpgsign", "false")
    copies = {
        "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json": PREREG_JSON.read_bytes(),
        "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md": PREREG_MD.read_bytes(),
        LIB_PATH: _live_bytes(LIB_PATH),
        RUNNER_PATH: _live_bytes(RUNNER_PATH),
        AUTH_MOD_PATH: _live_bytes(AUTH_MOD_PATH),
        PRODUCTION_PATH: _live_bytes(PRODUCTION_PATH),
        "scripts/__init__.py": _live_bytes("scripts/__init__.py"),
        "scripts/research/__init__.py": _live_bytes("scripts/research/__init__.py"),
        "scripts/research/lib/__init__.py": _live_bytes("scripts/research/lib/__init__.py"),
        "scripts/research/lib/research_harness.py": _live_bytes(
            "scripts/research/lib/research_harness.py"
        ),
    }
    if extra:
        copies.update(extra)
    for rel, data in copies.items():
        _write(repo / rel, data)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "production durability tree")
    return repo


def _porcelain(repo: Path) -> str:
    return _git(repo, "status", "--porcelain", "--untracked-files=all")


def _assert_clean(repo: Path) -> None:
    status = _porcelain(repo)
    assert status == "", f"temporary checkout is dirty before/at the barrier:\n{status}"


def _bind_prod(monkeypatch, repo: Path) -> None:
    monkeypatch.setattr(prod, "_repo_root", lambda: repo)
    monkeypatch.setattr(prod, "_executing_file", lambda rel: (repo / rel).resolve())


def _bind_auth(monkeypatch, repo: Path) -> None:
    monkeypatch.setattr(auth, "_repo_root", lambda: repo)
    monkeypatch.setattr(auth, "_executing_authority_file", lambda rel: (repo / rel).resolve())


def _mock_record(
    scenario_id: str,
    n_rows: int,
    world_index: int,
    *,
    oracle_model: bool = False,
    any_edge: bool = False,
    useful: bool = False,
    strict_ex: bool = False,
    strict: bool = False,
    visible: bool = False,
    valid: bool = True,
    invalid_reasons: tuple[str, ...] = (),
) -> dict:
    identity = lib.world_identity(scenario_id, n_rows, world_index)
    return {
        "scenario_id": scenario_id,
        "n_rows": n_rows,
        "world_index": world_index,
        "world_identity": identity,
        "world_seed": int(lib.world_seed(identity)),
        "valid": valid,
        "invalid_reasons": list(invalid_reasons),
        "oracle_F03": {
            "gates": {
                "MODEL_DETECTED": oracle_model,
                "STRICT_PASS_EX_MATERIALITY": strict_ex,
                "STRICT_PASS": strict,
            },
            "visibility": {"GROUND_TRUTH_VISIBLE": visible},
        },
        "selected_STRICT_PASS_EX_MATERIALITY": "F03" if useful else "NO_CANDIDATE",
        "selected_STRICT_PASS": "F03" if useful else "NO_CANDIDATE",
        "taxonomy": "TRUE_DISCOVERY" if useful else "NO_DISCOVERY",
        "taxonomy_flags": {
            "TRUE_DISCOVERY": useful,
            "ANY_EDGE_DECLARED": any_edge,
            "USEFUL_DISCOVERY": useful,
        },
        "visibility": {"GROUND_TRUTH_VISIBLE": visible},
        "materiality": {
            "STRICT_PASS": strict,
            "STRICT_PASS_EX_MATERIALITY": strict_ex,
        },
        "stays_in_denominator": True,
    }


def _planned_records(cell_flags=None) -> list[dict]:
    records = []
    flags = cell_flags or {}
    for scenario_id, n_rows, world_index in prod.planned_production_jobs():
        key = (scenario_id, n_rows)
        kwargs = dict(flags.get(key, {}))
        records.append(_mock_record(scenario_id, n_rows, world_index, **kwargs))
    return records


def _authority_sha_map(repo: Path) -> dict[str, str]:
    return {
        "lib": _sha((repo / LIB_PATH).read_bytes()),
        "runner": _sha((repo / RUNNER_PATH).read_bytes()),
        "auth": _sha((repo / AUTH_MOD_PATH).read_bytes()),
        "production": _sha((repo / PRODUCTION_PATH).read_bytes()),
        "prereg_json": _sha(
            (repo / "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json").read_bytes()
        ),
        "prereg_md": _sha(
            (repo / "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md").read_bytes()
        ),
    }


def _commit_arm_authorizing_parent(repo: Path) -> str:
    parent = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = {
        "production_monte_carlo_arm_authorized": True,
        "authorized_execution_commit": parent,
        "authorized_execution_tree": tree,
        "execution_authority_sha256": _authority_sha_map(repo),
    }
    _write(repo / prod.CANONICAL_ARM_PATH, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "arm parent execution commit")
    return parent


def _rank_safe_world(n_rows: int = 50) -> dict:
    width = n_rows // 5
    pattern_x1 = np.array([-2.0, -1.5, -0.4, 0.3, 0.8, 1.2, 1.6, 2.0, -0.2, 0.5], dtype=np.float64)
    pattern_x2 = np.array([-2.0, -1.4, -0.3, 0.2, 0.7, 1.1, -1.2, 1.8, 0.1, -0.6], dtype=np.float64)
    pattern_s = np.array([0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0], dtype=np.float64)
    x1 = np.empty(n_rows, dtype=np.float64)
    x2 = np.empty(n_rows, dtype=np.float64)
    s = np.empty(n_rows, dtype=np.float64)
    for i in range(5):
        slc = slice(i * width, (i + 1) * width)
        x1[slc] = np.resize(pattern_x1, width)
        x2[slc] = np.resize(pattern_x2, width)
        s[slc] = np.resize(pattern_s, width)
    y = (0.20 * x1 - 0.15 * x2 + 0.25 * s + 0.01 * np.arange(n_rows, dtype=np.float64)).astype(
        np.float64
    )
    return {
        "Y": y,
        "X1": x1,
        "X2": x2,
        "S": s,
        "world_identity": lib.world_identity("EASY", n_rows, 0),
    }


def _records_with_invalid_prefix(n_invalid: int) -> list[dict]:
    records = _planned_records()
    for i in range(n_invalid):
        rec = dict(records[i])
        rec["valid"] = False
        rec["invalid_reasons"] = ["bootstrap_invalid"]
        records[i] = rec
    return records


def _records_with_cell_successes(scenario_id: str, n_rows: int, field: str, k: int) -> list[dict]:
    records = []
    seen = 0
    for rec in _planned_records():
        if rec["scenario_id"] == scenario_id and rec["n_rows"] == n_rows and seen < k:
            records.append(
                _mock_record(scenario_id, n_rows, rec["world_index"], **{field: True})
            )
            seen += 1
        else:
            records.append(rec)
    return records


def _k_for_verdict(kind: str, threshold: float, wanted: str, n: int = 400) -> int:
    fn = lib.specificity_verdict if kind == "specificity" else lib.power_verdict
    for k in range(n + 1):
        if fn(lib.wilson_interval(k, n), threshold) == wanted:
            return k
    raise AssertionError(f"no success count yields {wanted} for {kind} {threshold}")


def test_frozen_lib_and_prereg_unchanged():
    assert _sha((REPO / LIB_PATH).read_bytes()) == FROZEN_LIB_SHA256
    assert _sha(PREREG_JSON.read_bytes()) == FROZEN_PREREG_JSON_SHA256
    assert _sha(PREREG_MD.read_bytes()) == FROZEN_PREREG_MD_SHA256
    assert prod.FROZEN_REVIEWED_LIB_SHA256 == FROZEN_LIB_SHA256


def test_fixture_guard_still_rejects_production_n_and_replicates():
    with pytest.raises(lib.SyntheticExecutionNotAuthorized):
        lib.FixtureExecutionConfig(
            n_rows=5000,
            scenario_id="EASY",
            visibility_replicates=500,
            bootstrap_replicates=500,
            placebo_replicates=999,
            block_rows=50,
        )
    for n_rows in (2500, 5000, 10000):
        with pytest.raises(lib.SyntheticExecutionNotAuthorized):
            lib.FixtureExecutionConfig(
                n_rows=n_rows,
                scenario_id="EASY",
                visibility_replicates=3,
                bootstrap_replicates=3,
                placebo_replicates=3,
            )
    with pytest.raises(lib.SyntheticExecutionNotAuthorized):
        lib.FixtureExecutionConfig(
            n_rows=50,
            scenario_id="EASY",
            visibility_replicates=500,
            bootstrap_replicates=3,
            placebo_replicates=3,
        )


def test_frozen_grid_is_derived_from_tracked_authority_only():
    grid = prod.frozen_production_grid()
    assert grid == prod.FROZEN_GRID_LITERALS
    assert grid["root_seed"] == 20260908
    assert grid["planned_worlds"] == 3200
    jobs = prod.planned_production_jobs()
    assert len(jobs) == 3200
    assert jobs[0] == ("NULL", 5000, 0)
    assert jobs[-1] == ("SMALL", 10000, 399)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        prod.spawn_canonical_production_process(grid=grid)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        prod.mint_final_result([], grid=grid)


def test_stale_imported_module_disk_restoration_cannot_execute(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    source = Path(prod.__file__).read_text(encoding="utf-8")
    assert "-I" in source
    assert "-P" in source
    assert "ISOLATED_CHILD_BOOTSTRAP" in source
    _assert_clean(repo)

    def tampered_gates(**kwargs):
        return {
            "primary_positive": False,
            "material_relative_mae": False,
            "bootstrap_positive": False,
            "placebo_separation": False,
            "era_stability": False,
            "support_sanity": False,
            "MODEL_DETECTED": False,
            "STRICT_PASS_EX_MATERIALITY": False,
            "STRICT_PASS": False,
            "TAMPERED_IN_PARENT": True,
        }

    monkeypatch.setattr(lib, "compose_gates", tampered_gates)
    monkeypatch.setattr(prod, "compose_gates", tampered_gates)
    assert lib.compose_gates(**prod.R1_PROBE_GATE_ARGS)["TAMPERED_IN_PARENT"] is True
    _assert_clean(repo)
    proc = prod.spawn_isolated_r1_probe()
    assert proc.returncode == 0, proc.stderr
    fingerprint = json.loads(proc.stdout)
    assert fingerprint["module"] == "scripts.research.harness_synthetic_edge_calibration_v1_production"
    assert fingerprint["compose_gates"]["MODEL_DETECTED"] is True
    assert fingerprint["compose_gates"].get("TAMPERED_IN_PARENT") is None
    assert fingerprint["production_monte_carlo_arm_authorized"] is False
    assert fingerprint["frozen_lib_sha256"] == FROZEN_LIB_SHA256
    _assert_clean(repo)
    assert prod.spawn_canonical_production_process() == 2


def test_modified_runner_bytes_fail(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    (repo / RUNNER_PATH).write_bytes(_live_bytes(RUNNER_PATH) + b"\n# tamper\n")
    _bind_prod(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="clean verified freeze|worktree|executed bytes"):
        prod.verify_executed_production_authority(repo)


def test_modified_auth_bytes_fail(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    (repo / AUTH_MOD_PATH).write_bytes(_live_bytes(AUTH_MOD_PATH) + b"\n# tamper\n")
    _bind_prod(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="clean verified freeze|worktree|executed bytes"):
        prod.verify_executed_production_authority(repo)


def test_modified_production_executor_bytes_fail(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    (repo / PRODUCTION_PATH).write_bytes(_live_bytes(PRODUCTION_PATH) + b"\n# tamper\n")
    _bind_prod(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="clean verified freeze|worktree|executed bytes"):
        prod.verify_executed_production_authority(repo)


def test_skip_worktree_tamper_fails(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _git(repo, "update-index", "--skip-worktree", PRODUCTION_PATH)
    (repo / PRODUCTION_PATH).write_bytes(_live_bytes(PRODUCTION_PATH) + b"\n# hidden\n")
    assert _git(repo, "status", "--porcelain") == ""
    _bind_prod(monkeypatch, repo)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="skip-worktree|clean verified freeze"
    ):
        prod.verify_executed_production_authority(repo)


def test_assume_unchanged_tamper_fails(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _git(repo, "update-index", "--assume-unchanged", PRODUCTION_PATH)
    (repo / PRODUCTION_PATH).write_bytes(_live_bytes(PRODUCTION_PATH) + b"\n# hidden\n")
    assert _git(repo, "status", "--porcelain") == ""
    _bind_prod(monkeypatch, repo)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="assume-unchanged|clean verified freeze"
    ):
        prod.verify_executed_production_authority(repo)


def test_descendant_commit_not_explicitly_armed_fails(tmp_path, monkeypatch, capfd):
    repo = _commit_production_tree(tmp_path)
    ancestor_head = _git(repo, "rev-parse", "HEAD")
    ancestor_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    _write(
        repo / prod.CANONICAL_ARM_PATH,
        json.dumps(
            {
                "production_monte_carlo_arm_authorized": True,
                "armed_head_sha": ancestor_head,
                "armed_tree_sha": ancestor_tree,
            },
            indent=2,
        )
        + "\n",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "descendant with ancestor ARM")
    descendant_head = _git(repo, "rev-parse", "HEAD")
    assert descendant_head != ancestor_head
    _git(repo, "merge-base", "--is-ancestor", ancestor_head, descendant_head)
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    rc = prod.spawn_canonical_production_process()
    captured = capfd.readouterr()
    _assert_clean(repo)
    assert rc == 2
    assert "production_monte_carlo_arm_authorized=false" in captured.err
    assert "working tree is not clean" not in captured.err
    with pytest.raises(prod.ProductionNotArmed, match="unarmed"):
        prod.mint_final_result(_planned_records())


def test_alternate_clone_cannot_mint_distinct_run_identity(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    clone = tmp_path / "clone"
    subprocess.check_output(["git", "clone", str(repo), str(clone)])
    _bind_prod(monkeypatch, repo)
    ident_a = prod.canonical_run_identity(repo)
    reservation_a = prod.canonical_json_bytes(prod.durable_reservation_document(repo))
    _bind_prod(monkeypatch, clone)
    ident_b = prod.canonical_run_identity(clone)
    reservation_b = prod.canonical_json_bytes(prod.durable_reservation_document(clone))
    assert ident_a == ident_b
    assert reservation_a == reservation_b
    records = _planned_records()
    assert prod.world_set_sha256(records) == prod.world_set_sha256(records)
    assert prod.canonical_run_identity(repo) == ident_a


def test_reservation_deletion_cannot_create_distinct_run(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    ident_1 = prod.canonical_run_identity(repo)
    reservation = prod.durable_reservation_document(repo)
    path = repo / prod.CANONICAL_RESERVATION_PATH
    _write(path, prod.canonical_json_bytes(reservation))
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="clean verified freeze"
    ):
        prod.canonical_run_identity(repo)
    path.unlink()
    ident_3 = prod.canonical_run_identity(repo)
    recreated = prod.durable_reservation_document(repo)
    assert ident_1 == ident_3
    assert prod.canonical_json_bytes(reservation) == prod.canonical_json_bytes(recreated)
    assert prod.durable_claim_document(repo)["run_identity"] == ident_1


def test_forged_proof_config_grid_result_payload_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    forged_grid = {**prod.FROZEN_GRID_LITERALS, "root_seed": 999}
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        prod.spawn_canonical_production_process(proof={"authorized": True}, grid=forged_grid)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        prod.mint_final_result(_planned_records(), result={"run_identity": "forged"})
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        prod.recover_partial_from_tracked_authority(digest="ab" * 32, path="evil.json")
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        prod.evaluate_production_world("NULL", 5000, 0, config=forged_grid)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="absent"):
        prod.recover_partial_from_tracked_authority()


def test_caller_args_cannot_authorize(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    for kwargs in (
        {"authorized": True},
        {"force": True},
        {"unsafe": True},
        {"authority_path": str(tmp_path / "evil.json")},
    ):
        with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
            prod.spawn_canonical_production_process(**kwargs)
        with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
            prod.mint_final_result(_planned_records(), **kwargs)


def test_environment_variables_cannot_authorize(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    monkeypatch.setenv("SYNTHETIC_EXECUTION_AUTHORIZED", "true")
    monkeypatch.setenv("HARNESS_FORCE", "1")
    monkeypatch.setenv("PRODUCTION_MONTE_CARLO_ARM_AUTHORIZED", "true")
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    assert prod.spawn_canonical_production_process() == 2
    source = Path(prod.__file__).read_text(encoding="utf-8")
    assert "getenv" not in source
    assert "SYNTHETIC_EXECUTION_AUTHORIZED" not in source


def test_alternate_paths_cannot_authorize(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    evil = tmp_path / "evil_result.json"
    _write(evil, json.dumps({"run_identity": "forged", "production_calibration_executed": True}))
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        prod.mint_final_result(_planned_records(), result_path=str(evil))
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        prod.persist_partial_worlds([], path=str(evil))
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        prod.recover_partial_from_tracked_authority(authority_path=str(evil))


def test_partial_world_set_cannot_finalize(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    records = _planned_records()[:-1]
    aggregates = prod.aggregate_planned_worlds(records)
    assert aggregates["incomplete_execution"] is True
    assert aggregates["mechanical_conclusion"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
    monkeypatch.setattr(prod, "production_monte_carlo_arm_authorized", lambda repo_root=None: True)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="incomplete execution cannot mint"):
        prod.mint_final_result(records)
    partial = prod.persist_partial_worlds(records)
    assert partial["final_result_minted"] is False
    assert partial["automatic_retry_authorized"] is False


def test_duplicate_world_identity_cannot_finalize():
    records = _planned_records()
    records.append(dict(records[0]))
    with pytest.raises(prod.ProductionIntegrityError, match="duplicate world identity"):
        prod.aggregate_planned_worlds(records)


def test_conflicting_duplicate_identity_cannot_finalize():
    records = _planned_records()
    conflict = dict(records[0])
    conflict["valid"] = False
    conflict["invalid_reasons"] = ["bootstrap_invalid"]
    records.append(conflict)
    with pytest.raises(prod.ProductionIntegrityError, match="conflicting duplicate world identity"):
        prod.aggregate_planned_worlds(records)


def test_invalid_worlds_remain_in_planned_denominator():
    def mutate_null(rec):
        if rec["scenario_id"] == "NULL" and rec["world_index"] < 10:
            rec = dict(rec)
            rec["valid"] = False
            rec["invalid_reasons"] = ["bootstrap_invalid"]
            rec["oracle_F03"] = {
                "gates": {
                    "MODEL_DETECTED": False,
                    "STRICT_PASS_EX_MATERIALITY": False,
                    "STRICT_PASS": False,
                },
                "visibility": {"GROUND_TRUTH_VISIBLE": False},
            }
        return rec

    records = [mutate_null(rec) for rec in _planned_records()]
    aggregates = prod.aggregate_planned_worlds(records)
    arm = aggregates["arms"]["ORACLE_NULL_MODEL_DETECTED"]
    assert arm["n"] == 400
    assert arm["successes"] == 0
    assert aggregates["invalid_counts_by_cell"]["NULL|5000"]["invalid_count"] == 10
    assert aggregates["invalid_counts_total"]["invalid_count"] == 10
    assert aggregates["invalid_counts_total"]["reasons"]["bootstrap_invalid"] == 10
    assert aggregates["incomplete_execution"] is True
    assert aggregates["mechanical_conclusion"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"


def test_wilson_thresholds_exact():
    records = _planned_records()
    aggregates = prod.aggregate_planned_worlds(records)
    expected = lib.wilson_interval(0, 400)
    arm = aggregates["arms"]["ORACLE_NULL_MODEL_DETECTED"]
    assert arm["n"] == 400
    assert arm["interval"] == expected
    assert arm["verdict"] == lib.specificity_verdict(expected, 0.05)
    assert arm["threshold"] == 0.05
    assert aggregates["arms"]["BLIND_NULL_ANY_EDGE_DECLARED"]["threshold"] == 0.10
    assert aggregates["arms"]["NONSTATIONARY_TRAP_STRICT_PASS_EX_MATERIALITY"]["threshold"] == 0.20
    assert aggregates["arms"]["ORACLE_EASY_MODEL_DETECTED"]["threshold"] == 0.90
    assert aggregates["arms"]["ORACLE_MODERATE_MODEL_DETECTED"]["threshold"] == 0.70
    assert aggregates["arms"]["BLIND_EASY_USEFUL_DISCOVERY"]["threshold"] == 0.80
    assert aggregates["arms"]["BLIND_MODERATE_USEFUL_DISCOVERY"]["threshold"] == 0.50


def test_mechanical_conclusion_priority_exact():
    vectors = [
        (
            "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM",
            dict(
                incomplete_execution=True,
                oracle_null_specificity=lib.FAIL,
                blind_null_specificity=lib.PASS,
                trap_specificity=lib.PASS,
                easy_oracle_power=lib.FAIL,
                moderate_oracle_power=lib.PASS,
                easy_blind_useful=lib.PASS,
                moderate_blind_useful=lib.PASS,
            ),
        ),
        (
            "METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06",
            dict(
                incomplete_execution=False,
                oracle_null_specificity=lib.FAIL,
                blind_null_specificity=lib.PASS,
                trap_specificity=lib.PASS,
                easy_oracle_power=lib.PASS,
                moderate_oracle_power=lib.PASS,
                easy_blind_useful=lib.PASS,
                moderate_blind_useful=lib.PASS,
            ),
        ),
        (
            "METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06",
            dict(
                incomplete_execution=False,
                oracle_null_specificity=lib.PASS,
                blind_null_specificity=lib.PASS,
                trap_specificity=lib.PASS,
                easy_oracle_power=lib.FAIL,
                moderate_oracle_power=lib.PASS,
                easy_blind_useful=lib.PASS,
                moderate_blind_useful=lib.PASS,
            ),
        ),
        (
            "CALIBRATION_INDETERMINATE",
            dict(
                incomplete_execution=False,
                oracle_null_specificity=lib.INDETERMINATE,
                blind_null_specificity=lib.PASS,
                trap_specificity=lib.PASS,
                easy_oracle_power=lib.PASS,
                moderate_oracle_power=lib.PASS,
                easy_blind_useful=lib.PASS,
                moderate_blind_useful=lib.PASS,
            ),
        ),
        (
            "DISCOVERY_BOTTLENECK_BEFORE_B2_06",
            dict(
                incomplete_execution=False,
                oracle_null_specificity=lib.PASS,
                blind_null_specificity=lib.PASS,
                trap_specificity=lib.PASS,
                easy_oracle_power=lib.PASS,
                moderate_oracle_power=lib.PASS,
                easy_blind_useful=lib.FAIL,
                moderate_blind_useful=lib.PASS,
            ),
        ),
        (
            "VISIBILITY_FLOOR",
            dict(
                incomplete_execution=False,
                oracle_null_specificity=lib.PASS,
                blind_null_specificity=lib.PASS,
                trap_specificity=lib.PASS,
                easy_oracle_power=lib.PASS,
                moderate_oracle_power=lib.PASS,
                easy_blind_useful=lib.PASS,
                moderate_blind_useful=lib.PASS,
                visibility_wilson_upper=0.49,
                model_detection_wilson_upper=0.90,
            ),
        ),
        (
            "MODEL_FLOOR",
            dict(
                incomplete_execution=False,
                oracle_null_specificity=lib.PASS,
                blind_null_specificity=lib.PASS,
                trap_specificity=lib.PASS,
                easy_oracle_power=lib.PASS,
                moderate_oracle_power=lib.PASS,
                easy_blind_useful=lib.PASS,
                moderate_blind_useful=lib.PASS,
                visibility_wilson_upper=0.90,
                model_detection_wilson_upper=0.49,
            ),
        ),
        (
            "MATERIALITY_ONLY_DIAGNOSTIC",
            dict(
                incomplete_execution=False,
                oracle_null_specificity=lib.PASS,
                blind_null_specificity=lib.PASS,
                trap_specificity=lib.PASS,
                easy_oracle_power=lib.PASS,
                moderate_oracle_power=lib.PASS,
                easy_blind_useful=lib.PASS,
                moderate_blind_useful=lib.PASS,
                visibility_wilson_upper=0.90,
                model_detection_wilson_upper=0.90,
                materiality_only_failure=True,
            ),
        ),
        (
            "NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK",
            dict(
                incomplete_execution=False,
                oracle_null_specificity=lib.PASS,
                blind_null_specificity=lib.PASS,
                trap_specificity=lib.PASS,
                easy_oracle_power=lib.PASS,
                moderate_oracle_power=lib.PASS,
                easy_blind_useful=lib.PASS,
                moderate_blind_useful=lib.PASS,
                visibility_wilson_upper=0.90,
                model_detection_wilson_upper=0.90,
                materiality_only_failure=False,
            ),
        ),
    ]
    for expected, kwargs in vectors:
        assert lib.mechanical_conclusion(**kwargs) == expected


def test_canonical_result_bytes_deterministic(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    records = _planned_records()
    monkeypatch.setattr(prod, "production_monte_carlo_arm_authorized", lambda repo_root=None: True)
    first = prod.mint_final_result(records)
    second = prod.mint_final_result(records)
    assert prod.canonical_json_bytes(first) == prod.canonical_json_bytes(second)
    assert first["core_sha256"] == second["core_sha256"]
    assert first["core_size"] == second["core_size"]
    assert first["core_size"] == len(prod.canonical_json_bytes(first["core"]))
    assert "result_sha256" not in first
    assert "result_sha256" not in first["core"]
    assert first["core"]["run_identity"] == prod.canonical_run_identity(repo)
    assert first["core"]["world_set_sha256"] == prod.world_set_sha256(records)
    assert first["core"]["frozen_lib_sha256"] == FROZEN_LIB_SHA256
    assert first["core"]["real_market_data_access_authorized"] is False
    assert first["core"]["b2_06_scientific_execution_authorized"] is False
    assert first["core"]["validation_2025_authorized"] is False
    assert first["core"]["oos_2026_authorized"] is False
    prod.verify_bound_result_document(first, records)


def test_digest_size_run_identity_tamper_detected(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    records = _planned_records()
    monkeypatch.setattr(prod, "production_monte_carlo_arm_authorized", lambda repo_root=None: True)
    document = prod.mint_final_result(records)
    digest_tamper = dict(document)
    digest_tamper["core_sha256"] = "ab" * 32
    with pytest.raises(prod.ProductionIntegrityError, match="core digest tamper"):
        prod.verify_bound_result_document(digest_tamper, records)
    size_tamper = dict(document)
    size_tamper["core_size"] = int(document["core_size"]) + 1
    with pytest.raises(prod.ProductionIntegrityError, match="core size tamper"):
        prod.verify_bound_result_document(size_tamper, records)
    ident_core = dict(document["core"])
    ident_core["run_identity"] = "cd" * 32
    ident_bytes = prod.canonical_json_bytes(prod._jsonable(dict(ident_core)))
    ident_tamper = {
        "core": ident_core,
        "core_sha256": _sha(ident_bytes),
        "core_size": len(ident_bytes),
    }
    with pytest.raises(prod.ProductionIntegrityError, match="run_identity tamper"):
        prod.verify_bound_result_document(ident_tamper, records)
    world_core = dict(document["core"])
    world_core["world_set_sha256"] = "ee" * 32
    world_bytes = prod.canonical_json_bytes(prod._jsonable(dict(world_core)))
    world_tamper = {
        "core": world_core,
        "core_sha256": _sha(world_bytes),
        "core_size": len(world_bytes),
    }
    with pytest.raises(prod.ProductionIntegrityError, match="world_set_sha256 tamper"):
        prod.verify_bound_result_document(world_tamper, records)
    for field, value in (
        ("mechanical_conclusion", "NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK"),
        ("real_market_data_access_authorized", True),
        ("b2_06_scientific_execution_authorized", True),
        ("validation_2025_authorized", True),
        ("oos_2026_authorized", True),
        ("production_monte_carlo_arm_authorized", True),
        ("production_calibration_executed", True),
    ):
        field_core = dict(document["core"])
        field_core[field] = value
        field_bytes = prod.canonical_json_bytes(prod._jsonable(dict(field_core)))
        field_tamper = {
            "core": field_core,
            "core_sha256": _sha(field_bytes),
            "core_size": len(field_bytes),
        }
        with pytest.raises(prod.ProductionIntegrityError, match="core payload tamper"):
            prod.verify_bound_result_document(field_tamper, records)
    extra_core = dict(document["core"])
    extra_core["attacker_field"] = True
    extra_bytes = prod.canonical_json_bytes(prod._jsonable(dict(extra_core)))
    extra_tamper = {
        "core": extra_core,
        "core_sha256": _sha(extra_bytes),
        "core_size": len(extra_bytes),
    }
    with pytest.raises(prod.ProductionIntegrityError, match="core payload tamper"):
        prod.verify_bound_result_document(extra_tamper, records)
    envelope_tamper = dict(document)
    envelope_tamper["attacker_field"] = True
    with pytest.raises(prod.ProductionIntegrityError, match="canonical core envelope"):
        prod.verify_bound_result_document(envelope_tamper, records)


def test_forged_aggregates_without_world_records_refused(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    forged_core = {
        "aggregates": {"mechanical_conclusion": "NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK"},
        "reservation_sha256": "aa" * 32,
        "claim_sha256": "bb" * 32,
        "run_identity": "cc" * 32,
        "world_set_sha256": "dd" * 32,
        "planned_world_count": 3200,
        "observed_world_count": 3200,
    }
    core_bytes = prod.canonical_json_bytes(forged_core)
    forged = {
        "core": forged_core,
        "core_sha256": _sha(core_bytes),
        "core_size": len(core_bytes),
    }
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller-supplied aggregates"):
        prod.bind_result_document(
            aggregates=forged_core["aggregates"],
            reservation_sha256=forged_core["reservation_sha256"],
            claim_sha256=forged_core["claim_sha256"],
        )
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="caller arguments"):
        prod.mint_final_result(
            [],
            aggregates=forged_core["aggregates"],
            reservation_sha256="aa" * 32,
            claim_sha256="bb" * 32,
        )
    with pytest.raises(prod.ProductionIntegrityError):
        prod.verify_bound_result_document(forged, [])


@pytest.mark.parametrize("n_invalid", [1, 25])
def test_invalid_worlds_force_incomplete_and_refuse_mint(tmp_path, monkeypatch, n_invalid):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    records = _records_with_invalid_prefix(n_invalid)
    aggregates = prod.aggregate_planned_worlds(records)
    assert aggregates["observed_world_count"] == 3200
    assert aggregates["planned_world_count"] == 3200
    assert aggregates["invalid_counts_by_cell"]["NULL|5000"]["planned"] == 400
    assert aggregates["invalid_counts_by_cell"]["NULL|5000"]["invalid_count"] == n_invalid
    assert aggregates["invalid_counts_total"]["invalid_count"] == n_invalid
    assert aggregates["incomplete_execution"] is True
    assert aggregates["mechanical_conclusion"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
    monkeypatch.setattr(prod, "production_monte_carlo_arm_authorized", lambda repo_root=None: True)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="incomplete execution cannot mint"):
        prod.mint_final_result(records)


def test_extra_non_planned_world_rejected():
    records = _planned_records()
    records.append(_mock_record("NULL", 5000, 999))
    with pytest.raises(prod.ProductionIntegrityError, match="extra world is not in the planned production set"):
        prod.aggregate_planned_worlds(records)


def test_descriptive_small_bands_and_true_discovery_interval():
    aggregates = prod.aggregate_planned_worlds(_planned_records())
    allowed = {"HIGH", "MODERATE", "LOW", "VERY_LOW", "INDETERMINATE"}
    for name in (
        "SMALL_ORACLE_MODEL_DETECTED_N5000",
        "SMALL_ORACLE_MODEL_DETECTED_N2500",
        "SMALL_ORACLE_MODEL_DETECTED_N10000",
    ):
        arm = aggregates["arms"][name]
        assert arm["band"] in allowed
        assert "interval" in arm
        assert arm["n"] == 400
    discovery = aggregates["arms"]["TRUE_DISCOVERY_RATE"]
    assert discovery["descriptive_only"] is True
    assert "interval" in discovery
    assert "lower" in discovery["interval"]
    assert "upper" in discovery["interval"]
    assert discovery["band"] in allowed


def test_wilson_boundary_success_counts_at_each_threshold():
    cases = (
        ("ORACLE_NULL_MODEL_DETECTED", "NULL", 5000, "oracle_model", 0.05, "specificity"),
        ("BLIND_NULL_ANY_EDGE_DECLARED", "NULL", 5000, "any_edge", 0.10, "specificity"),
        ("NONSTATIONARY_TRAP_STRICT_PASS_EX_MATERIALITY", "NONSTATIONARY_TRAP", 5000, "strict_ex", 0.20, "specificity"),
        ("ORACLE_EASY_MODEL_DETECTED", "EASY", 5000, "oracle_model", 0.90, "power"),
        ("ORACLE_MODERATE_MODEL_DETECTED", "MODERATE", 5000, "oracle_model", 0.70, "power"),
        ("BLIND_EASY_USEFUL_DISCOVERY", "EASY", 5000, "useful", 0.80, "power"),
        ("BLIND_MODERATE_USEFUL_DISCOVERY", "MODERATE", 5000, "useful", 0.50, "power"),
    )
    for arm_name, scenario_id, n_rows, field, threshold, kind in cases:
        for wanted in (lib.PASS, lib.INDETERMINATE, lib.FAIL):
            k = _k_for_verdict(kind, threshold, wanted)
            records = _records_with_cell_successes(scenario_id, n_rows, field, k)
            aggregates = prod.aggregate_planned_worlds(records)
            arm = aggregates["arms"][arm_name]
            assert arm["n"] == 400
            assert arm["successes"] == k
            assert arm["verdict"] == wanted
            assert arm["threshold"] == threshold
            assert aggregates["incomplete_execution"] is False


def test_incomplete_world_is_recorded_invalid_and_stays_in_denominator():
    n = 50
    world = {
        "Y": np.arange(n, dtype=np.float64),
        "X1": np.ones(n, dtype=np.float64),
        "X2": np.ones(n, dtype=np.float64),
        "S": np.ones(n, dtype=np.float64),
        "world_identity": lib.world_identity("NULL", 5000, 0),
    }
    out = prod.evaluate_production_candidate(
        world, "F03", scenario_id="NULL", n_rows=n, world_index=0
    )
    assert out["valid"] is False
    assert out["stays_in_denominator"] is True
    assert any("full rank" in str(reason) for reason in out["invalid_reasons"])
    records = _planned_records()
    invalid = dict(records[0])
    invalid["valid"] = False
    invalid["invalid_reasons"] = list(out["invalid_reasons"])
    records[0] = invalid
    aggregates = prod.aggregate_planned_worlds(records)
    assert aggregates["observed_world_count"] == 3200
    assert aggregates["invalid_counts_by_cell"]["NULL|5000"]["planned"] == 400
    assert aggregates["invalid_counts_by_cell"]["NULL|5000"]["invalid_count"] == 1
    assert aggregates["incomplete_execution"] is True
    assert aggregates["mechanical_conclusion"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"


def test_incomplete_world_world_record_does_not_escape(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    monkeypatch.setattr(prod, "production_monte_carlo_arm_authorized", lambda repo_root=None: True)
    n = 5000
    rank_deficient = {
        "Y": np.ones(n, dtype=np.float64),
        "X1": np.ones(n, dtype=np.float64),
        "X2": np.ones(n, dtype=np.float64),
        "S": np.ones(n, dtype=np.float64),
        "world_identity": lib.world_identity("NULL", 5000, 0),
    }
    monkeypatch.setattr(prod, "simulate_dgp", lambda **kwargs: rank_deficient)
    rec = prod.evaluate_production_world("NULL", 5000, 0)
    assert rec["valid"] is False
    assert rec["stays_in_denominator"] is True
    assert rec["world_identity"] == lib.world_identity("NULL", 5000, 0)
    assert rec["scenario_id"] == "NULL"
    assert rec["n_rows"] == 5000
    assert rec["world_index"] == 0
    assert rec["invalid_reasons"]
    assert any(
        "full rank" in str(reason) or "design shape" in str(reason)
        for reason in rec["invalid_reasons"]
    )
    records = _planned_records()
    records[0] = {
        **records[0],
        "valid": False,
        "invalid_reasons": list(rec["invalid_reasons"]),
        "stays_in_denominator": True,
    }
    aggregates = prod.aggregate_planned_worlds(records)
    assert aggregates["observed_world_count"] == 3200
    assert aggregates["invalid_counts_by_cell"]["NULL|5000"]["planned"] == 400
    assert aggregates["incomplete_execution"] is True
    assert aggregates["mechanical_conclusion"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"


def test_train_end_by_score_era_preserved_on_candidate(monkeypatch):
    world = _rank_safe_world(50)
    monkeypatch.setattr(
        prod,
        "visibility_from_residuals",
        lambda *args, **kwargs: {"GROUND_TRUTH_VISIBLE": False},
    )
    monkeypatch.setattr(
        prod,
        "prediction_bootstrap",
        lambda *args, **kwargs: {"world_invalid": False, "bootstrap_positive": True},
    )
    monkeypatch.setattr(
        prod,
        "placebo_q95",
        lambda *args, **kwargs: {
            "world_invalid": False,
            "placebo_invalid": False,
            "placebo_q95": 0.0,
        },
    )
    out = prod.evaluate_production_candidate(
        world, "F03", scenario_id="EASY", n_rows=50, world_index=0
    )
    assert out["valid"] is True
    assert "train_end_by_score_era" in out
    assert set(out["train_end_by_score_era"]) == {"E2", "E3", "E4", "E5"}
    source = Path(prod.__file__).read_text(encoding="utf-8")
    assert "train_end_by_score_era" in source


def test_malicious_usercustomize_cannot_alter_compose_gates(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    marker = tmp_path / "usercustomize_ran"
    user_site = (
        tmp_path
        / "userbase"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    user_site.mkdir(parents=True)
    _write(
        user_site / "usercustomize.py",
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
    )
    monkeypatch.setenv("PYTHONUSERBASE", str(tmp_path / "userbase"))
    proc = prod.spawn_isolated_r1_probe()
    assert proc.returncode == 0, proc.stderr
    fingerprint = json.loads(proc.stdout)
    assert fingerprint["compose_gates"]["MODEL_DETECTED"] is True
    assert fingerprint["module"] == "scripts.research.harness_synthetic_edge_calibration_v1_production"
    assert marker.exists() is False


def test_malicious_sitecustomize_cannot_alter_scientific_module(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    marker = tmp_path / "sitecustomize_ran"
    site_dir = tmp_path / "sitecustomize_dir"
    site_dir.mkdir()
    _write(
        site_dir / "sitecustomize.py",
        (
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('ran')\n"
            "import builtins\n"
            "_real = builtins.__import__\n"
            "def _hook(name, *args, **kwargs):\n"
            "    mod = _real(name, *args, **kwargs)\n"
            "    if 'harness_synthetic_edge_calibration_v1_lib' in name:\n"
            "        mod.compose_gates = lambda **kw: {'MODEL_DETECTED': False, 'TAMPERED_SITECUSTOMIZE': True}\n"
            "    return mod\n"
            "builtins.__import__ = _hook\n"
        ),
    )
    monkeypatch.setenv("PYTHONPATH", str(site_dir))
    proc = prod.spawn_isolated_r1_probe()
    assert proc.returncode == 0, proc.stderr
    fingerprint = json.loads(proc.stdout)
    assert fingerprint["compose_gates"]["MODEL_DETECTED"] is True
    assert fingerprint["compose_gates"].get("TAMPERED_SITECUSTOMIZE") is None
    assert marker.exists() is False


def test_hostile_scripts_research_numpy_cannot_execute_before_verification(tmp_path, monkeypatch):
    marker = tmp_path / "hostile_numpy_ran"
    hostile = (
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('hostile numpy executed')\n"
        "raise RuntimeError('hostile numpy executed')\n"
    )
    repo = _commit_production_tree(
        tmp_path, extra={"scripts/research/numpy.py": hostile.encode("utf-8")}
    )
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    proc = prod.spawn_isolated_r1_probe()
    assert proc.returncode == 0, proc.stderr
    fingerprint = json.loads(proc.stdout)
    assert fingerprint["module"] == "scripts.research.harness_synthetic_edge_calibration_v1_production"
    assert fingerprint["compose_gates"]["MODEL_DETECTED"] is True
    assert marker.exists() is False


def test_isolated_child_canonical_module_identity_not_main(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    proc = prod.spawn_isolated_r1_probe()
    assert proc.returncode == 0, proc.stderr
    fingerprint = json.loads(proc.stdout)
    assert fingerprint["module"] == "scripts.research.harness_synthetic_edge_calibration_v1_production"
    assert fingerprint["module"] != "__main__"
    assert Path(fingerprint["sys_path0"]).resolve() == repo.resolve()


def test_inherited_pythonpath_cannot_substitute_another_checkout(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    hostile = tmp_path / "hostile_checkout"
    package = hostile / "scripts" / "research"
    package.mkdir(parents=True)
    _write(hostile / "scripts" / "__init__.py", "")
    _write(package / "__init__.py", "")
    _write(
        package / "harness_synthetic_edge_calibration_v1_production.py",
        (
            "def _isolated_child_main(mode):\n"
            "    print('{\"module\": \"TAMPERED_PYTHONPATH\", \"compose_gates\": {\"MODEL_DETECTED\": false}}')\n"
            "    return 0\n"
        ),
    )
    monkeypatch.setenv("PYTHONPATH", str(hostile))
    proc = prod.spawn_isolated_r1_probe()
    assert proc.returncode == 0, proc.stderr
    fingerprint = json.loads(proc.stdout)
    assert fingerprint["module"] == "scripts.research.harness_synthetic_edge_calibration_v1_production"
    assert fingerprint["compose_gates"]["MODEL_DETECTED"] is True
    assert fingerprint["module"] != "TAMPERED_PYTHONPATH"


def test_arm_parent_commit_positive_control(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    parent = _commit_arm_authorizing_parent(repo)
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is True
    assert _git(repo, "rev-parse", "HEAD^") == parent
    rc = prod.spawn_canonical_production_process()
    assert rc == 2
    _write(repo / "docs/research/NOTE.txt", "descendant after ARM\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "descendant after ARM")
    assert prod.production_monte_carlo_arm_authorized(repo) is False


def test_arm_wrong_parent_tree_digest_and_modified_bytes_fail(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    parent = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    digests = _authority_sha_map(repo)
    wrong_parent = dict(
        production_monte_carlo_arm_authorized=True,
        authorized_execution_commit="0" * 40,
        authorized_execution_tree=tree,
        execution_authority_sha256=digests,
    )
    _write(repo / prod.CANONICAL_ARM_PATH, json.dumps(wrong_parent, indent=2) + "\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "wrong parent ARM")
    _bind_prod(monkeypatch, repo)
    assert prod.production_monte_carlo_arm_authorized(repo) is False

    repo2 = _commit_production_tree(tmp_path / "tree")
    wrong_tree = {
        "production_monte_carlo_arm_authorized": True,
        "authorized_execution_commit": _git(repo2, "rev-parse", "HEAD"),
        "authorized_execution_tree": "0" * 40,
        "execution_authority_sha256": _authority_sha_map(repo2),
    }
    _write(repo2 / prod.CANONICAL_ARM_PATH, json.dumps(wrong_tree, indent=2) + "\n")
    _git(repo2, "add", "-A")
    _git(repo2, "commit", "-m", "wrong tree ARM")
    _bind_prod(monkeypatch, repo2)
    assert prod.production_monte_carlo_arm_authorized(repo2) is False

    repo3 = _commit_production_tree(tmp_path / "digest")
    parent3 = _git(repo3, "rev-parse", "HEAD")
    tree3 = _git(repo3, "rev-parse", "HEAD^{tree}")
    bad_digests = dict(_authority_sha_map(repo3))
    bad_digests["lib"] = "ab" * 32
    wrong_digest = {
        "production_monte_carlo_arm_authorized": True,
        "authorized_execution_commit": parent3,
        "authorized_execution_tree": tree3,
        "execution_authority_sha256": bad_digests,
    }
    _write(repo3 / prod.CANONICAL_ARM_PATH, json.dumps(wrong_digest, indent=2) + "\n")
    _git(repo3, "add", "-A")
    _git(repo3, "commit", "-m", "wrong digest ARM")
    _bind_prod(monkeypatch, repo3)
    assert prod.production_monte_carlo_arm_authorized(repo3) is False

    repo4 = _commit_production_tree(tmp_path / "bytes")
    parent4 = _git(repo4, "rev-parse", "HEAD")
    tree4 = _git(repo4, "rev-parse", "HEAD^{tree}")
    payload = {
        "production_monte_carlo_arm_authorized": True,
        "authorized_execution_commit": parent4,
        "authorized_execution_tree": tree4,
        "execution_authority_sha256": _authority_sha_map(repo4),
    }
    _write(repo4 / prod.CANONICAL_ARM_PATH, json.dumps(payload, indent=2) + "\n")
    (repo4 / RUNNER_PATH).write_bytes(_live_bytes(RUNNER_PATH) + b"\n# arm-commit tamper\n")
    _git(repo4, "add", "-A")
    _git(repo4, "commit", "-m", "ARM plus modified runner")
    _bind_prod(monkeypatch, repo4)
    assert prod.production_monte_carlo_arm_authorized(repo4) is False


def test_recover_partial_from_committed_artifact_and_reject_foreign_identity(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    records = _planned_records()[:10]
    payload = prod.persist_partial_worlds(records)
    exec_head = payload["execution_head"]
    _write(repo / prod.CANONICAL_PARTIAL_PATH, prod.canonical_json_bytes(payload).decode("utf-8"))
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="clean verified freeze"):
        prod.recover_partial_from_tracked_authority()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "commit partial artifact")
    recovered = prod.recover_partial_from_tracked_authority()
    assert recovered["canonical_path"] == prod.CANONICAL_PARTIAL_PATH
    assert recovered["run_identity"] == payload["run_identity"]
    assert recovered["execution_head"] == exec_head
    assert recovered["observed_world_count"] == 10
    assert recovered["final_result_minted"] is False

    forged = dict(payload)
    forged["run_identity"] = "ab" * 32
    body = {key: value for key, value in forged.items() if key not in {"partial_sha256", "partial_size"}}
    raw = prod.canonical_json_bytes(body)
    forged["partial_sha256"] = _sha(raw)
    forged["partial_size"] = len(raw)
    _write(repo / prod.CANONICAL_PARTIAL_PATH, prod.canonical_json_bytes(forged).decode("utf-8"))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "foreign run identity partial")
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="run_identity does not match the named execution identity",
    ):
        prod.recover_partial_from_tracked_authority()


def test_114_local_reservation_superseded_when_production_module_tracked(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_auth(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="supersedes"):
        auth.run_authorized_production_grid()


def test_cli_uses_fresh_process_and_stays_unarmed():
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "spawn_canonical_production_process" in source
    assert "run_authorized_production_grid" not in source
    production_source = Path(prod.__file__).read_text(encoding="utf-8")
    assert "-I" in production_source
    assert "-P" in production_source
    assert "ISOLATED_CHILD_BOOTSTRAP" in production_source
    identity = json.loads(
        subprocess.check_output(
            [
                sys.executable,
                "-m",
                "scripts.research.harness_synthetic_edge_calibration_v1",
                "--identity",
            ],
            cwd=REPO,
            text=True,
        )
    )
    assert identity["production_monte_carlo_arm_authorized"] is False
    assert identity["production_calibration_executed"] is False
    assert identity["production_result_minted"] is False
    assert identity["monte_carlo_armed"] is False
    assert identity["real_data_path"] is False
    assert (REPO / prod.CANONICAL_RESULT_PATH).exists() is False
    assert (REPO / prod.CANONICAL_ARM_PATH).exists() is False


def test_production_modules_have_no_real_data_path():
    source = (
        Path(prod.__file__).read_text(encoding="utf-8")
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
    assert prod.production_durability_identity()["global_process_exclusion_claimed"] is False
