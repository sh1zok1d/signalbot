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


_HISTORICAL_RECOMPUTE_TEST_STUB = '''
# HISTORICAL_RECOMPUTE_TEST_STUB: disposable-topology surrogate evaluator.
# Bound by ARM on this checkout only. Not present on the live workspace.

def _evaluate_planned_world_body(scenario_id: str, n_rows: int, world_index: int) -> dict[str, Any]:
    identity = world_identity(scenario_id, int(n_rows), int(world_index))
    return {
        "scenario_id": scenario_id,
        "n_rows": n_rows,
        "world_index": world_index,
        "world_identity": identity,
        "world_seed": int(world_seed(identity)),
        "valid": True,
        "invalid_reasons": [],
        "oracle_F03": {
            "gates": {
                "MODEL_DETECTED": False,
                "STRICT_PASS_EX_MATERIALITY": False,
                "STRICT_PASS": False,
            },
            "visibility": {"GROUND_TRUTH_VISIBLE": False},
        },
        "selected_STRICT_PASS_EX_MATERIALITY": "NO_CANDIDATE",
        "selected_STRICT_PASS": "NO_CANDIDATE",
        "taxonomy": "NO_DISCOVERY",
        "taxonomy_flags": {
            "TRUE_DISCOVERY": False,
            "ANY_EDGE_DECLARED": False,
            "USEFUL_DISCOVERY": False,
        },
        "visibility": {"GROUND_TRUTH_VISIBLE": False},
        "materiality": {
            "STRICT_PASS": False,
            "STRICT_PASS_EX_MATERIALITY": False,
        },
        "stays_in_denominator": True,
    }

'''


def _install_historical_recompute_test_stub(repo: Path) -> None:
    path = repo / PRODUCTION_PATH
    text = path.read_text(encoding="utf-8")
    marker = 'if __name__ == "__main__":\n'
    if marker not in text:
        raise AssertionError("production.py is missing the isolated-child main guard")
    if "HISTORICAL_RECOMPUTE_TEST_STUB" in text:
        return
    path.write_text(text.replace(marker, _HISTORICAL_RECOMPUTE_TEST_STUB + marker, 1), encoding="utf-8")


def _commit_production_tree(
    tmp_path: Path,
    *,
    extra: dict[str, bytes] | None = None,
    historical_recompute_stub: bool = False,
) -> Path:
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
    if historical_recompute_stub:
        _install_historical_recompute_test_stub(repo)
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


def _driver_freeze_payload(repo: Path, reviewed_head: str, reviewed_tree: str) -> dict:
    return {
        "schema_version": "1.0",
        "unit_id": prod.UNIT_ID,
        "freeze_status": "FIXTURE_DRIVER_IMPLEMENTATION_FROZEN_UNARMED",
        "reviewed_implementation_head": reviewed_head,
        "reviewed_implementation_tree": reviewed_tree,
        "reviewed_production_sha256": _sha((repo / PRODUCTION_PATH).read_bytes()),
        "frozen_lib_sha256": FROZEN_LIB_SHA256,
        "prereg_json_sha256": FROZEN_PREREG_JSON_SHA256,
        "prereg_md_sha256": FROZEN_PREREG_MD_SHA256,
        **prod.DRIVER_FREEZE_REQUIRED_LITERALS,
    }


def _commit_driver_freeze(repo: Path) -> tuple[str, str]:
    reviewed_head = _git(repo, "rev-parse", "HEAD")
    reviewed_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    payload = _driver_freeze_payload(repo, reviewed_head, reviewed_tree)
    _write(
        repo / prod.CANONICAL_DRIVER_FREEZE_PATH,
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "docs-only driver freeze")
    return reviewed_head, reviewed_tree


def _commit_arm_authorizing_parent(repo: Path) -> str:
    tracked_freeze = _git(repo, "ls-files", prod.CANONICAL_DRIVER_FREEZE_PATH)
    if not tracked_freeze:
        _commit_driver_freeze(repo)
    parent = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    freeze = json.loads((repo / prod.CANONICAL_DRIVER_FREEZE_PATH).read_text(encoding="utf-8"))
    payload = {
        "production_monte_carlo_arm_authorized": True,
        "authorized_execution_commit": parent,
        "authorized_execution_tree": tree,
        "execution_authority_sha256": _authority_sha_map(repo),
        "reviewed_implementation_head": freeze["reviewed_implementation_head"],
        "reviewed_implementation_tree": freeze["reviewed_implementation_tree"],
        "authorized_grid": prod.frozen_production_grid(),
        **prod.ARM_REQUIRED_LITERALS,
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
    assert "-B" in source
    assert "-P" in source
    assert "ISOLATED_CHILD_BOOTSTRAP" in source
    assert "repo-root module shadow" in prod.ISOLATED_CHILD_BOOTSTRAP
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
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="caller-supplied records cannot mint"
    ):
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
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="caller-supplied records cannot mint"
    ):
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
    core = prod._bind_result_core(records=records, repo_root=repo)
    core_bytes = prod.canonical_json_bytes(prod._jsonable(core))
    first = {
        "core": core,
        "core_sha256": _sha(core_bytes),
        "core_size": len(core_bytes),
    }
    second_core = prod._bind_result_core(records=records, repo_root=repo)
    second_bytes = prod.canonical_json_bytes(prod._jsonable(second_core))
    second = {
        "core": second_core,
        "core_sha256": _sha(second_bytes),
        "core_size": len(second_bytes),
    }
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
    core = prod._bind_result_core(records=records, repo_root=repo)
    core_bytes = prod.canonical_json_bytes(prod._jsonable(core))
    document = {
        "core": core,
        "core_sha256": _sha(core_bytes),
        "core_size": len(core_bytes),
    }
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
        # A complete production core legitimately carries True, so the tamper
        # under test is flipping it to False.
        ("production_calibration_executed", False),
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
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized, match="caller-supplied records cannot mint"
    ):
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


@pytest.mark.parametrize(
    "rel",
    (
        "numpy.py",
        "numpy/__init__.py",
        "json/__init__.py",
        "math/__init__.py",
    ),
)
def test_root_shadows_do_not_execute_before_authority_verification(tmp_path, monkeypatch, rel):
    marker = tmp_path / "root_shadow_ran"
    hostile = (
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text({rel!r})\n"
        "raise RuntimeError('root shadow executed')\n"
    )
    repo = _commit_production_tree(tmp_path, extra={rel: hostile.encode("utf-8")})
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    bootstrap = prod.ISOLATED_CHILD_BOOTSTRAP
    insert_at = bootstrap.find("sys.path.insert")
    import_at = bootstrap.find("from scripts.research.harness_synthetic_edge_calibration_v1_production import")
    assert "import hashlib" in bootstrap
    assert "import subprocess" in bootstrap
    assert "ALLOWED_ROOT_DIRS" in bootstrap
    assert "repo-root module shadow" in bootstrap
    assert insert_at != -1 and import_at != -1 and insert_at < import_at
    assert bootstrap.find("import numpy") == -1
    proc = prod.spawn_isolated_r1_probe()
    assert marker.exists() is False
    assert proc.returncode == 2
    assert "repo-root module shadow is not allowed execution authority" in proc.stderr
    assert "root shadow executed" not in (proc.stdout + proc.stderr)


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
    # Isolated worker would run the 3200-world driver once armed. This unit
    # never invokes that path; fixture-driver tests cover orchestration.
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


FIXTURE_JOBS = (
    ("NULL", 50, 0),
    ("EASY", 50, 0),
    ("MODERATE", 50, 1),
)


def _clear_sessions() -> None:
    prod._LIVE_SESSIONS.clear()
    prod._CAPABILITY_KEEPALIVE.clear()
    prod._CLOSED_SESSIONS.clear()
    prod._CLOSED_CAPABILITY_KEEPALIVE.clear()


def _fixture_eval(scenario_id: str, n_rows: int, world_index: int) -> dict:
    return _mock_record(scenario_id, n_rows, world_index)


def _rehash_result(core: dict) -> dict:
    core_bytes = prod.canonical_json_bytes(prod._jsonable(dict(core)))
    return {
        "core": core,
        "core_sha256": _sha(core_bytes),
        "core_size": len(core_bytes),
    }


def _commit_result_envelope(
    repo: Path,
    envelope: dict,
    message: str = "tracked RESULT",
    world_records: dict | None = None,
) -> bytes:
    raw = prod.canonical_json_bytes(prod._jsonable(envelope))
    _write(repo / prod.CANONICAL_RESULT_PATH, raw.decode("utf-8"))
    if world_records is not None:
        _write(
            repo / prod.CANONICAL_WORLD_RECORDS_PATH,
            prod.canonical_json_bytes(prod._jsonable(world_records)).decode("utf-8"),
        )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return raw


def _bind_mock_production_evaluator(monkeypatch) -> None:
    """Disposable mock evaluator. Tests must not invoke the real production Monte Carlo."""

    def fake(scenario_id, n_rows, world_index):
        return _mock_record(scenario_id, n_rows, world_index)

    monkeypatch.setattr(prod, "_evaluate_planned_world_body", fake)


def _armed_fixture_repo(tmp_path, monkeypatch) -> Path:
    repo = _commit_production_tree(tmp_path, historical_recompute_stub=True)
    _commit_arm_authorizing_parent(repo)
    _bind_prod(monkeypatch, repo)
    _assert_clean(repo)
    return repo


def _mint_fixture_envelope(repo: Path) -> tuple[dict, list]:
    _clear_sessions()
    cap = prod.open_canonical_fixture_session(FIXTURE_JOBS, _fixture_eval)
    records = [prod.evaluate_canonical_session_job(cap, *job) for job in FIXTURE_JOBS]
    envelope = prod.mint_session_result(cap)
    return envelope, records


def test_historical_result_verifies_after_commit_and_later_docs_only(tmp_path, monkeypatch):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    envelope, records = _mint_fixture_envelope(repo)
    prod.verify_bound_result_document(envelope, records)
    execution_head = envelope["core"]["execution_head"]
    execution_tree = envelope["core"]["execution_tree"]
    assert execution_head == _git(repo, "rev-parse", "HEAD")
    assert envelope["core"]["production_monte_carlo_arm_authorized"] is True
    raw = _commit_result_envelope(repo, envelope)
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    with pytest.raises(prod.ProductionIntegrityError):
        prod.verify_bound_result_document(envelope, records)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="caller-supplied historical RESULT authority is refused",
    ):
        prod.verify_bound_result_from_tracked_authority(
            repo, envelope, execution_head=execution_head
        )
    verified = prod.verify_bound_result_from_tracked_authority(repo, envelope)
    assert verified["core"]["execution_head"] == execution_head
    assert verified["core"]["execution_tree"] == execution_tree
    tracked = prod.verify_bound_result_from_tracked_authority(repo)
    assert tracked["core"]["run_identity"] == envelope["core"]["run_identity"]
    claim = prod.durable_result_claim_from_tracked_authority(repo, envelope)
    assert claim["run_identity"] == envelope["core"]["run_identity"]
    assert claim["execution_head"] == execution_head
    assert claim["artifact_sha256"] == _sha(raw)
    assert claim["artifact_size"] == len(raw)
    assert claim["final_result_minted"] is True
    assert claim["artifact_kind"] == "result"
    _write(repo / "docs/research/LATER_DESCENDANT.md", "docs-only descendant\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "later docs-only descendant")
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    later = prod.verify_bound_result_from_tracked_authority(repo, envelope)
    assert later["core"]["execution_head"] == execution_head
    again = prod.durable_result_claim_from_tracked_authority(repo)
    assert again["artifact_sha256"] == claim["artifact_sha256"]


def test_historical_result_post_commit_attacks_refused(tmp_path, monkeypatch):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    freeze = _git(repo, "rev-parse", "HEAD^")
    envelope, _records = _mint_fixture_envelope(repo)
    arm_head = envelope["core"]["execution_head"]
    _commit_result_envelope(repo, envelope)
    initial = _git(repo, "rev-list", "--max-parents=0", "HEAD")

    def refuse(document, match):
        with pytest.raises(lib.SyntheticExecutionNotAuthorized, match=match):
            prod.verify_bound_result_from_tracked_authority(repo, document)

    head_core = dict(envelope["core"])
    head_core["execution_head"] = freeze
    head_core["execution_tree"] = _git(repo, "rev-parse", f"{freeze}^{{tree}}")
    refuse(_rehash_result(head_core), "not armed|ARM topology")
    tree_core = dict(envelope["core"])
    tree_core["execution_tree"] = "ab" * 20
    refuse(_rehash_result(tree_core), "execution tree")
    ident_core = dict(envelope["core"])
    ident_core["run_identity"] = "cd" * 32
    refuse(_rehash_result(ident_core), "run_identity tamper")
    digest_tamper = dict(envelope)
    digest_tamper["core_sha256"] = "ab" * 32
    refuse(digest_tamper, "core digest tamper")
    size_tamper = dict(envelope)
    size_tamper["core_size"] = int(envelope["core_size"]) + 1
    refuse(size_tamper, "core size tamper")
    rec_core = dict(envelope["core"])
    records = [dict(item) for item in rec_core["records"]]
    records[0] = dict(records[0])
    records[0]["taxonomy"] = "TRUE_DISCOVERY"
    rec_core["records"] = records
    refuse(_rehash_result(rec_core), "world_set|core payload tamper")
    conclusion_core = dict(envelope["core"])
    conclusion_core["mechanical_conclusion"] = "NO_V1_EVIDENCE_OF_DISCOVERY_BOTTLENECK"
    refuse(_rehash_result(conclusion_core), "core payload tamper")
    result_head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", freeze)
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="not an ancestor of current HEAD",
    ):
        prod.verify_bound_result_from_tracked_authority(repo, envelope)
    _git(repo, "checkout", result_head)
    fake_core = dict(envelope["core"])
    fake_core["execution_head"] = initial
    fake_core["execution_tree"] = _git(repo, "rev-parse", f"{initial}^{{tree}}")
    refuse(_rehash_result(fake_core), "not armed|ARM topology")
    wrong_run = dict(envelope["core"])
    wrong_run["run_identity"] = _sha(b"different-run")
    refuse(_rehash_result(wrong_run), "run_identity tamper")
    alt_records = [dict(item) for item in envelope["core"]["records"]]
    alt_records[0] = dict(alt_records[0])
    alt_records[0]["taxonomy"] = "TRUE_DISCOVERY"
    bound = prod._bound_from_commit_blobs(repo, arm_head)
    alt_core = prod._bind_result_core_from_bound(
        alt_records, bound=bound, fixture=True, armed=True
    )
    _commit_result_envelope(repo, _rehash_result(alt_core), "conflicting terminal RESULT")
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="duplicate/conflicting terminal production RESULT",
    ):
        prod.verify_bound_result_from_tracked_authority(repo)
    assert arm_head == envelope["core"]["execution_head"]


def test_historical_result_production_blob_and_wrong_arm_topology(tmp_path, monkeypatch):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    freeze = _git(repo, "rev-parse", "HEAD^")
    records = _planned_records()
    core = prod._bind_result_core(records=records, repo_root=repo, fixture=False)
    world_records = prod._production_world_records_from_bound(
        records, bound=prod.verify_executed_production_authority(repo)
    )
    envelope = {
        "core": core,
        "core_sha256": _sha(prod.canonical_json_bytes(prod._jsonable(core))),
        "core_size": len(prod.canonical_json_bytes(prod._jsonable(core))),
    }
    _commit_result_envelope(repo, envelope, world_records=world_records)
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    prod.verify_bound_result_from_tracked_authority(repo, envelope)
    blob_core = dict(core)
    listed = dict(blob_core["authority_sha256"])
    listed["production"] = "ab" * 32
    blob_core["authority_sha256"] = listed
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="production blob differs from bound digest",
    ):
        prod.verify_bound_result_from_tracked_authority(repo, _rehash_result(blob_core))
    freeze_core = dict(core)
    freeze_core["execution_head"] = freeze
    freeze_core["execution_tree"] = _git(repo, "rev-parse", f"{freeze}^{{tree}}")
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="not armed|ARM topology",
    ):
        prod.verify_bound_result_from_tracked_authority(repo, _rehash_result(freeze_core))


def test_historical_result_claim_conflict_and_duplicate_abandon_removed(tmp_path, monkeypatch):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    envelope, _records = _mint_fixture_envelope(repo)
    _commit_result_envelope(repo, envelope)
    claim = prod.durable_result_claim_from_tracked_authority(repo, envelope)
    other = dict(claim)
    other["run_identity"] = "ab" * 32
    _write(
        repo / prod.CANONICAL_CLAIM_PATH,
        prod.canonical_json_bytes(other).decode("utf-8"),
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "conflicting durable claim")
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="duplicate/conflicting durable RESULT claim",
    ):
        prod.durable_result_claim_from_tracked_authority(repo, envelope)
    source = Path(prod.__file__).read_text(encoding="utf-8")
    assert source.count("def abandon_canonical_session") == 1


def _commit_production_result(
    repo: Path, *, core_mut=None, world_records_mut=None, rebind_artifact: bool = True
):
    """Commit exactly ONE production-shaped RESULT plus sibling WORLD_RECORDS.

    A single tracked version per topology, so the duplicate/conflicting-RESULT
    guard can never mask a scientific tamper.
    """
    records = _planned_records()
    bound = prod.verify_executed_production_authority(repo)
    core = prod._bind_result_core_from_bound(
        records, bound=bound, fixture=False, armed=True
    )
    world_records = prod._production_world_records_from_bound(records, bound=bound)
    core = json.loads(json.dumps(prod._jsonable(core)))
    world_records = json.loads(json.dumps(prod._jsonable(world_records)))
    if world_records_mut is not None:
        world_records = world_records_mut(world_records)
        body = {
            key: value
            for key, value in world_records.items()
            if key not in {"world_records_sha256", "world_records_size"}
        }
        raw = prod.canonical_json_bytes(prod._jsonable(body))
        world_records["world_records_sha256"] = _sha(raw)
        world_records["world_records_size"] = len(raw)
        if rebind_artifact:
            full = prod.canonical_json_bytes(prod._jsonable(world_records))
            core["records_artifact_sha256"] = _sha(full)
            core["records_artifact_size"] = len(full)
    if core_mut is not None:
        core = core_mut(core)
    envelope = prod._result_envelope_from_core(core)
    _commit_result_envelope(repo, envelope, world_records=world_records)
    return envelope, world_records


def test_historical_production_result_verifies_and_binds_world_records(
    tmp_path, monkeypatch
):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    envelope, world_records = _commit_production_result(repo)
    core = envelope["core"]
    assert core["production_calibration_executed"] is True
    assert "fixture" not in core
    assert core["records_artifact_path"] == prod.CANONICAL_WORLD_RECORDS_PATH
    assert core["record_count"] == 3200
    assert len(world_records["records"]) == 3200
    assert len(world_records["record_digest_chain"]) == 3200
    assert world_records["world_set_sha256"] == core["world_set_sha256"]
    tracked = prod.canonical_json_bytes(prod._jsonable(world_records))
    assert core["records_artifact_sha256"] == _sha(tracked)
    assert core["records_artifact_size"] == len(tracked)
    verified = prod.verify_bound_result_from_tracked_authority(repo)
    assert verified["core"]["mechanical_conclusion"] == core["mechanical_conclusion"]
    claim = prod.durable_result_claim_from_tracked_authority(repo)
    assert claim["final_result_minted"] is True
    assert claim["production_calibration_executed"] is True
    assert claim["result_artifact_sha256"] == claim["artifact_sha256"]
    assert claim["result_artifact_size"] == claim["artifact_size"]
    assert claim["records_artifact_sha256"] == core["records_artifact_sha256"]
    assert claim["records_artifact_size"] == core["records_artifact_size"]
    assert claim["records_artifact_path"] == prod.CANONICAL_WORLD_RECORDS_PATH
    assert claim["execution_head"] == core["execution_head"]
    assert claim["execution_tree"] == core["execution_tree"]
    assert claim["run_identity"] == core["run_identity"]
    assert claim["terminal_commit"]
    assert claim["terminal_tree"]


def test_historical_production_result_requires_tracked_world_records(
    tmp_path, monkeypatch
):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    records = _planned_records()
    bound = prod.verify_executed_production_authority(repo)
    core = prod._bind_result_core_from_bound(
        records, bound=bound, fixture=False, armed=True
    )
    _commit_result_envelope(repo, prod._result_envelope_from_core(core))
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="tracked production WORLD_RECORDS artifact is absent",
    ):
        prod.verify_bound_result_from_tracked_authority(repo)


def test_historical_world_records_worktree_is_not_authority(tmp_path, monkeypatch):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    envelope, world_records = _commit_production_result(repo)
    committed = prod.canonical_json_bytes(prod._jsonable(world_records))
    forged_records = _records_with_cell_successes("NULL", 5000, "oracle_model", 400)
    bound = prod._bound_from_commit_blobs(repo, envelope["core"]["execution_head"])
    forged = prod._production_world_records_from_bound(forged_records, bound=bound)
    forged_bytes = prod.canonical_json_bytes(prod._jsonable(forged))
    _write(
        repo / prod.CANONICAL_WORLD_RECORDS_PATH,
        forged_bytes.decode("utf-8"),
    )
    blob = prod._head_blob(repo, prod.CANONICAL_WORLD_RECORDS_PATH)
    assert blob == committed
    assert blob != forged_bytes
    _git(repo, "checkout", "--", prod.CANONICAL_WORLD_RECORDS_PATH)
    verified = prod.verify_bound_result_from_tracked_authority(repo)
    assert verified["core"]["world_set_sha256"] == envelope["core"]["world_set_sha256"]
    assert (
        verified["core"]["aggregates"]["arms"]["ORACLE_NULL_MODEL_DETECTED"]["successes"]
        == 0
    )


def test_consistent_aggregate_rewrite_refused(tmp_path, monkeypatch):
    """Keep original WORLD_RECORDS, rewrite RESULT science from a different record set."""
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    honest_records = _planned_records()
    forged_records = _records_with_cell_successes("NULL", 5000, "oracle_model", 400)
    bound = prod.verify_executed_production_authority(repo)
    honest = prod._bind_result_core_from_bound(
        honest_records, bound=bound, fixture=False, armed=True
    )
    forged = prod._bind_result_core_from_bound(
        forged_records, bound=bound, fixture=False, armed=True
    )
    assert honest["aggregates"]["arms"]["ORACLE_NULL_MODEL_DETECTED"]["successes"] == 0
    assert forged["aggregates"]["arms"]["ORACLE_NULL_MODEL_DETECTED"]["successes"] == 400
    assert honest["mechanical_conclusion"] != forged["mechanical_conclusion"]
    rewritten = dict(honest)
    for key in (
        "aggregates",
        "verdicts",
        "wilson_intervals",
        "mechanical_conclusion",
        "planned_world_count",
        "observed_world_count",
    ):
        rewritten[key] = forged[key]
    assert rewritten["execution_head"] == honest["execution_head"]
    assert rewritten["execution_tree"] == honest["execution_tree"]
    assert rewritten["run_identity"] == honest["run_identity"]
    assert rewritten["world_set_sha256"] == honest["world_set_sha256"]
    assert rewritten["record_digest_chain"] == honest["record_digest_chain"]
    assert rewritten["records_artifact_sha256"] == honest["records_artifact_sha256"]
    world_records = prod._production_world_records_from_bound(
        honest_records, bound=bound
    )
    _commit_result_envelope(
        repo, prod._result_envelope_from_core(rewritten), world_records=world_records
    )
    with pytest.raises(lib.SyntheticExecutionNotAuthorized) as excinfo:
        prod.verify_bound_result_from_tracked_authority(repo)
    detail = str(excinfo.value)
    assert "duplicate/conflicting" not in detail
    assert (
        "aggregates were not derived from the world set" in detail
        or "core payload tamper" in detail
    )


def test_historical_production_recomputes_all_3200_worlds(tmp_path, monkeypatch):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    _commit_production_result(repo)
    modes: list[str] = []
    original = prod._spawn_isolated_child

    def wrapped(mode, repo_root=None, **kwargs):
        modes.append(mode)
        return original(mode, repo_root=repo_root, **kwargs)

    def boom(*args, **kwargs):
        raise AssertionError("parent in-process historical recomputation")

    monkeypatch.setattr(prod, "_spawn_isolated_child", wrapped)
    monkeypatch.setattr(prod, "_recompute_production_records_from_frozen_execution", boom)
    monkeypatch.setattr(prod, "_evaluate_planned_world_body", boom)
    verified = prod.verify_bound_result_from_tracked_authority(repo)
    assert modes == [prod.HISTORICAL_RECOMPUTE_MODE]
    assert verified["core"]["record_count"] == 3200
    assert verified["core"]["aggregates"]["arms"]["ORACLE_NULL_MODEL_DETECTED"]["successes"] == 0
    source = Path(prod.__file__).read_text(encoding="utf-8")
    child_src = source.split("def _isolated_child_main", 1)[1].split(
        "def fresh_process_worker_main", 1
    )[0]
    worker_src = source.split("def historical_recompute_worker_main", 1)[1].split(
        "def _isolated_child_main", 1
    )[0]
    verify_src = source.split("def verify_bound_result_from_tracked_authority", 1)[1].split(
        "def durable_result_claim_from_tracked_authority", 1
    )[0]
    assert "HISTORICAL_RECOMPUTE_MODE" in child_src
    assert "_recompute_production_records_from_frozen_execution" in worker_src
    assert "_load_tracked_world_records" in worker_src
    assert "_assert_historical_recompute_uses_authorized_code" in worker_src
    recompute_src = source.split(
        "def _recompute_production_records_from_frozen_execution", 1
    )[1].split("def _compare_recomputed_world_records", 1)[0]
    assert "planned_production_jobs" in recompute_src
    assert "_evaluate_planned_world_body" in recompute_src
    assert "_require_isolated_historical_recompute" in verify_src
    assert "_recompute_production_records_from_frozen_execution" not in verify_src
    assert "_evaluate_planned_world_body" not in verify_src
    assert "HISTORICAL_RECOMPUTE_TEST_STUB" not in source


def test_consistent_result_plus_world_records_rewrite_refused(tmp_path, monkeypatch):
    """First-and-only self-consistent fabricated WORLD_RECORDS + RESULT pair."""
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    bound = prod.verify_executed_production_authority(repo)
    honest_records = _planned_records()
    forged_records = _records_with_cell_successes("NULL", 5000, "oracle_model", 400)
    honest = prod._bind_result_core_from_bound(
        honest_records, bound=bound, fixture=False, armed=True
    )
    forged = prod._bind_result_core_from_bound(
        forged_records, bound=bound, fixture=False, armed=True
    )
    forged_world_records = prod._production_world_records_from_bound(
        forged_records, bound=bound
    )
    assert honest["aggregates"]["arms"]["ORACLE_NULL_MODEL_DETECTED"]["successes"] == 0
    assert forged["aggregates"]["arms"]["ORACLE_NULL_MODEL_DETECTED"]["successes"] == 400
    assert honest["mechanical_conclusion"] != forged["mechanical_conclusion"]
    assert forged["execution_head"] == honest["execution_head"]
    assert forged["execution_tree"] == honest["execution_tree"]
    assert forged["run_identity"] == honest["run_identity"]
    assert forged["records_artifact_sha256"] != honest["records_artifact_sha256"]
    _commit_result_envelope(
        repo,
        prod._result_envelope_from_core(forged),
        world_records=forged_world_records,
    )
    with pytest.raises(lib.SyntheticExecutionNotAuthorized) as excinfo:
        prod.verify_bound_result_from_tracked_authority(repo)
    detail = str(excinfo.value)
    assert "duplicate/conflicting" not in detail
    assert "tracked WORLD_RECORDS were not produced by frozen execution" in detail
    with pytest.raises(lib.SyntheticExecutionNotAuthorized) as claim_exc:
        prod.durable_result_claim_from_tracked_authority(repo)
    claim_detail = str(claim_exc.value)
    assert "duplicate/conflicting" not in claim_detail
    assert "tracked WORLD_RECORDS were not produced by frozen execution" in claim_detail


def test_historical_spotcheck_is_not_claim_authority(tmp_path, monkeypatch):
    source = Path(prod.__file__).read_text(encoding="utf-8")
    claim_src = source.split("def durable_result_claim_from_tracked_authority", 1)[1].split(
        "def persist_partial_worlds", 1
    )[0]
    verify_src = source.split("def verify_bound_result_from_tracked_authority", 1)[1].split(
        "def durable_result_claim_from_tracked_authority", 1
    )[0]
    assert "diagnose_historical_result_spotcheck" not in claim_src
    assert "diagnose_historical_result_spotcheck" not in verify_src
    assert prod.AUTHORITATIVE_HISTORICAL_VERIFICATION == "FULL_3200_RECOMPUTATION"
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    _commit_production_result(repo)
    _bind_mock_production_evaluator(monkeypatch)
    diagnostic = prod.diagnose_historical_result_spotcheck(repo)
    assert diagnostic["authoritative"] is False
    assert diagnostic["authoritative_historical_verification"] is False
    assert diagnostic["durable_claim_authorized"] is False
    assert diagnostic["full_recompute"] is False
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="caller arguments cannot authorize a historical spot-check",
    ):
        prod.diagnose_historical_result_spotcheck(repo, n=8)


def _mut_arm(core, arm, key, value):
    core = dict(core)
    aggregates = json.loads(json.dumps(core["aggregates"]))
    aggregates["arms"][arm][key] = value
    core["aggregates"] = aggregates
    return core


PRODUCTION_CORE_TAMPERS = (
    (
        "mechanical_conclusion",
        lambda c: {**c, "mechanical_conclusion": "HARNESS_METHODOLOGY_VALIDATED_FOR_B2_06"},
        "core payload tamper",
    ),
    (
        "one_verdict",
        lambda c: {**c, "verdicts": {**c["verdicts"], "trap_specificity": "FAIL"}},
        "core payload tamper",
    ),
    (
        "aggregate_count",
        lambda c: _mut_arm(c, "ORACLE_NULL_MODEL_DETECTED", "successes", 7),
        "aggregates were not derived from the world set",
    ),
    (
        "wilson_interval",
        lambda c: _mut_arm(
            c,
            "ORACLE_EASY_MODEL_DETECTED",
            "interval",
            {
                "n": 400.0,
                "successes": 400.0,
                "phat": 1.0,
                "center": 0.9,
                "lower": 0.99,
                "upper": 1.0,
            },
        ),
        "aggregates were not derived from the world set",
    ),
    (
        "observed_world_count",
        lambda c: {**c, "observed_world_count": 1},
        "core payload tamper",
    ),
    (
        "incomplete_execution",
        lambda c: {
            **c,
            "aggregates": {**c["aggregates"], "incomplete_execution": True},
        },
        "aggregates were not derived from the world set",
    ),
    (
        "world_set_sha256",
        lambda c: {**c, "world_set_sha256": "aa" * 32},
        "world_set_sha256 tamper detected",
    ),
    (
        "record_digest_chain",
        lambda c: {**c, "record_digest_chain": ["00" * 32] * 3200},
        "record_digest_chain tamper detected",
    ),
    (
        "records_artifact_sha256",
        lambda c: {**c, "records_artifact_sha256": "aa" * 32},
        "records_artifact_sha256 does not match tracked WORLD_RECORDS bytes",
    ),
    (
        "records_artifact_size",
        lambda c: {**c, "records_artifact_size": int(c["records_artifact_size"]) + 1},
        "records_artifact_size does not match tracked WORLD_RECORDS bytes",
    ),
    (
        "records_artifact_path",
        lambda c: {**c, "records_artifact_path": "docs/research/FORGED_WORLD_RECORDS.json"},
        "records_artifact_path is not the canonical WORLD_RECORDS path",
    ),
    (
        "record_count",
        lambda c: {**c, "record_count": 1},
        "record_count is not the frozen 3200-world plan",
    ),
    (
        "production_calibration_executed",
        lambda c: {**c, "production_calibration_executed": False},
        "protected scope authorization flag tamper detected",
    ),
    (
        "b2_06_scientific_execution_authorized",
        lambda c: {**c, "b2_06_scientific_execution_authorized": True},
        "protected scope authorization flag tamper detected",
    ),
    (
        "validation_2025_authorized",
        lambda c: {**c, "validation_2025_authorized": True},
        "protected scope authorization flag tamper detected",
    ),
    (
        "oos_2026_authorized",
        lambda c: {**c, "oos_2026_authorized": True},
        "protected scope authorization flag tamper detected",
    ),
    (
        "aggregate_scope_flag",
        lambda c: {
            **c,
            "aggregates": {
                **c["aggregates"],
                "b2_06_scientific_execution_authorized": True,
            },
        },
        "aggregates were not derived from the world set",
    ),
    (
        "aggregate_mechanical_conclusion",
        lambda c: {
            **c,
            "aggregates": {
                **c["aggregates"],
                "mechanical_conclusion": "HARNESS_METHODOLOGY_VALIDATED_FOR_B2_06",
            },
        },
        "aggregates were not derived from the world set",
    ),
    (
        "wilson_intervals_wiped",
        lambda c: {**c, "wilson_intervals": {}},
        "core payload tamper",
    ),
)


@pytest.mark.parametrize("label,mutate,message", PRODUCTION_CORE_TAMPERS)
def test_historical_production_scientific_payload_tamper_refused(
    tmp_path, monkeypatch, label, mutate, message
):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    _commit_production_result(repo, core_mut=mutate)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized) as excinfo:
        prod.verify_bound_result_from_tracked_authority(repo)
    detail = str(excinfo.value)
    assert message in detail, detail
    # Never satisfied by the duplicate/conflicting-RESULT guard.
    assert "duplicate/conflicting" not in detail


def _unrelated_world_records(artifact):
    forged_records = _records_with_cell_successes("NULL", 5000, "oracle_model", 400)
    artifact = dict(artifact)
    artifact["records"] = forged_records
    artifact["world_set_sha256"] = prod.world_set_sha256(forged_records)
    artifact["record_digest_chain"] = list(prod._ordered_record_digest_chain(forged_records))
    return artifact


PRODUCTION_WORLD_RECORDS_TAMPERS = (
    (
        "chain",
        lambda m: {**m, "record_digest_chain": ["11" * 32] * 3200},
        "WORLD_RECORDS record_digest_chain was not derived from the records",
    ),
    (
        "world_set",
        lambda m: {**m, "world_set_sha256": "bb" * 32},
        "WORLD_RECORDS world_set_sha256 was not derived from the records",
    ),
    (
        "jobs",
        lambda m: {**m, "jobs": m["jobs"][:-1]},
        "job plan is not the frozen 3200-world plan",
    ),
    (
        "run_identity",
        lambda m: {**m, "run_identity": "cc" * 32},
        "run_identity does not match",
    ),
    (
        "execution_head",
        lambda m: {**m, "execution_head": "de" * 20},
        "execution_head does not match",
    ),
    (
        "unrelated_records",
        _unrelated_world_records,
        "world_set_sha256 tamper detected",
    ),
)


@pytest.mark.parametrize("label,mutate,message", PRODUCTION_WORLD_RECORDS_TAMPERS)
def test_historical_production_world_records_tamper_refused(
    tmp_path, monkeypatch, label, mutate, message
):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    _commit_production_result(repo, world_records_mut=mutate)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized) as excinfo:
        prod.verify_bound_result_from_tracked_authority(repo)
    detail = str(excinfo.value)
    assert message in detail, detail
    assert "duplicate/conflicting" not in detail


def test_historical_production_world_records_unbound_content_tamper_refused(
    tmp_path, monkeypatch
):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    _commit_production_result(
        repo,
        world_records_mut=lambda m: {**m, "world_set_sha256": "bb" * 32},
        rebind_artifact=False,
    )
    with pytest.raises(
        lib.SyntheticExecutionNotAuthorized,
        match="records_artifact_sha256 does not match tracked WORLD_RECORDS bytes",
    ):
        prod.verify_bound_result_from_tracked_authority(repo)


def test_fixture_historical_verify_does_not_spawn_isolated_child(tmp_path, monkeypatch):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    envelope, _records = _mint_fixture_envelope(repo)
    _commit_result_envelope(repo, envelope)

    def boom(*args, **kwargs):
        raise AssertionError("fixture historical verify must not spawn an isolated child")

    monkeypatch.setattr(prod, "_spawn_isolated_child", boom)
    verified = prod.verify_bound_result_from_tracked_authority(repo, envelope)
    assert verified["core"]["fixture"] is True


def _parent_science_boom(*args, **kwargs):
    raise AssertionError("parent-process science must not authorize historical verification")


def test_parent_monkeypatch_cannot_affect_honest_historical_verify(tmp_path, monkeypatch):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    envelope, _world_records = _commit_production_result(repo)
    production_bytes = (repo / PRODUCTION_PATH).read_bytes()
    assert "HISTORICAL_RECOMPUTE_TEST_STUB" in production_bytes.decode("utf-8")

    def fabricated(scenario_id, n_rows, world_index):
        return _mock_record(
            scenario_id,
            n_rows,
            world_index,
            oracle_model=scenario_id == "NULL" and n_rows == 5000,
        )

    monkeypatch.setattr(prod, "_evaluate_planned_world_body", fabricated)
    monkeypatch.setattr(prod, "aggregate_planned_worlds", _parent_science_boom)
    monkeypatch.setattr(prod, "planned_production_jobs", _parent_science_boom)
    monkeypatch.setattr(prod, "_recompute_production_records_from_frozen_execution", _parent_science_boom)
    monkeypatch.setattr(prod, "_bind_result_core_from_bound", _parent_science_boom)
    verified = prod.verify_bound_result_from_tracked_authority(repo)
    assert verified["core"]["execution_head"] == envelope["core"]["execution_head"]
    assert verified["core"]["run_identity"] == envelope["core"]["run_identity"]
    assert verified["core"]["aggregates"]["arms"]["ORACLE_NULL_MODEL_DETECTED"]["successes"] == 0
    assert (repo / PRODUCTION_PATH).read_bytes() == production_bytes
    claim = prod.durable_result_claim_from_tracked_authority(repo)
    assert claim["records_artifact_sha256"] == envelope["core"]["records_artifact_sha256"]


def test_parent_monkeypatch_cannot_mint_fabricated_historical_pair(tmp_path, monkeypatch):
    repo = _armed_fixture_repo(tmp_path, monkeypatch)
    production_bytes = (repo / PRODUCTION_PATH).read_bytes()
    bound = prod.verify_executed_production_authority(repo)
    honest_records = _planned_records()
    forged_records = _records_with_cell_successes("NULL", 5000, "oracle_model", 400)
    honest = prod._bind_result_core_from_bound(
        honest_records, bound=bound, fixture=False, armed=True
    )
    forged = prod._bind_result_core_from_bound(
        forged_records, bound=bound, fixture=False, armed=True
    )
    forged_world_records = prod._production_world_records_from_bound(
        forged_records, bound=bound
    )
    assert honest["aggregates"]["arms"]["ORACLE_NULL_MODEL_DETECTED"]["successes"] == 0
    assert forged["aggregates"]["arms"]["ORACLE_NULL_MODEL_DETECTED"]["successes"] == 400
    assert honest["mechanical_conclusion"] != forged["mechanical_conclusion"]
    assert forged["execution_head"] == honest["execution_head"]
    assert forged["run_identity"] == honest["run_identity"]

    def fabricated(scenario_id, n_rows, world_index):
        return _mock_record(
            scenario_id,
            n_rows,
            world_index,
            oracle_model=scenario_id == "NULL" and n_rows == 5000,
        )

    monkeypatch.setattr(prod, "_evaluate_planned_world_body", fabricated)
    monkeypatch.setattr(prod, "aggregate_planned_worlds", _parent_science_boom)
    monkeypatch.setattr(prod, "planned_production_jobs", _parent_science_boom)
    monkeypatch.setattr(prod, "_recompute_production_records_from_frozen_execution", _parent_science_boom)
    _commit_result_envelope(
        repo,
        prod._result_envelope_from_core(forged),
        world_records=forged_world_records,
    )
    assert (repo / PRODUCTION_PATH).read_bytes() == production_bytes
    with pytest.raises(lib.SyntheticExecutionNotAuthorized) as excinfo:
        prod.verify_bound_result_from_tracked_authority(repo)
    detail = str(excinfo.value)
    assert "duplicate/conflicting" not in detail
    assert "tracked WORLD_RECORDS were not produced by frozen execution" in detail
    with pytest.raises(lib.SyntheticExecutionNotAuthorized) as claim_exc:
        prod.durable_result_claim_from_tracked_authority(repo)
    claim_detail = str(claim_exc.value)
    assert "duplicate/conflicting" not in claim_detail
    assert "tracked WORLD_RECORDS were not produced by frozen execution" in claim_detail
    assert (repo / PRODUCTION_PATH).read_bytes() == production_bytes


def test_malformed_historical_recompute_proof_fails_closed():
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="produced no proof"):
        prod._parse_historical_recompute_proof(b"")
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="not JSON"):
        prod._parse_historical_recompute_proof(b"not-json")
    proof = {
        "schema_version": "1.0",
        "kind": prod.HISTORICAL_RECOMPUTE_PROOF_KIND,
        "mode": prod.HISTORICAL_RECOMPUTE_MODE,
        "verification": prod.AUTHORITATIVE_HISTORICAL_VERIFICATION,
        "verification_success": True,
        "execution_head": "ab" * 20,
        "execution_tree": "cd" * 20,
        "run_identity": "ef" * 32,
        "result_artifact_sha256": "11" * 32,
        "result_artifact_size": 1,
        "records_artifact_sha256": "22" * 32,
        "records_artifact_size": 1,
        "recomputed_world_records_sha256": "22" * 32,
    }
    raw = prod.canonical_json_bytes(proof)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="duplicate or trailing"):
        prod._parse_historical_recompute_proof(raw + b'{"extra": true}\n')
    proof["verification_success"] = False
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="did not attest success"):
        prod._parse_historical_recompute_proof(prod.canonical_json_bytes(proof))
    proof["verification_success"] = True
    proof["extra"] = True
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="keys are not canonical"):
        prod._parse_historical_recompute_proof(prod.canonical_json_bytes(proof))
