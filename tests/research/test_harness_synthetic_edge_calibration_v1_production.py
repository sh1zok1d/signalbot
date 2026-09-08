"""Production durability tests for HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1.

Tiny synthetic fixtures and mocked 3200-world records only. These tests must
not run the frozen 3200-world Monte Carlo, mint a live production RESULT, access
real market data, open B2-06, or inspect 2025/2026.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

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
    repo.mkdir()
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


def test_stale_imported_module_disk_restoration_cannot_execute(tmp_path, monkeypatch, capfd):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    source = Path(prod.__file__).read_text(encoding="utf-8")
    assert "subprocess.run" in source
    assert "sys.executable" in source
    assert prod.WORKER_FLAG in source
    original = (repo / PRODUCTION_PATH).read_bytes()
    stale_spawn = prod.spawn_canonical_production_process
    tampered = original + b"\nSTALE_IMPORT_MARKER = True  # stale tamper\n"
    outside = tmp_path / "outside_git_root"
    tamper_path = outside / "stale_production.py"
    _write(tamper_path, tampered)
    spec = importlib.util.spec_from_file_location("stale_production_mod", tamper_path)
    stale_mod = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(stale_mod)
    assert stale_mod is not prod
    assert stale_mod.STALE_IMPORT_MARKER is True
    (repo / PRODUCTION_PATH).write_bytes(tampered)
    (repo / PRODUCTION_PATH).write_bytes(original)
    assert (repo / PRODUCTION_PATH).read_bytes() == original
    assert not hasattr(prod, "STALE_IMPORT_MARKER")
    _assert_clean(repo)
    rc = stale_spawn()
    captured = capfd.readouterr()
    _assert_clean(repo)
    assert rc == 2
    assert "production_monte_carlo_arm_authorized=false" in captured.err
    assert "working tree is not clean" not in captured.err
    assert prod.production_monte_carlo_arm_authorized(repo) is False
    with pytest.raises(prod.ProductionNotArmed, match="production_monte_carlo_arm_authorized=false"):
        prod.evaluate_production_world("NULL", 5000, 0)


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
    doc_a = prod.bind_result_document(aggregates=prod.aggregate_planned_worlds(_planned_records()), repo_root=repo)
    _bind_prod(monkeypatch, clone)
    doc_b = prod.bind_result_document(aggregates=prod.aggregate_planned_worlds(_planned_records()), repo_root=clone)
    assert doc_a["run_identity"] == doc_b["run_identity"] == ident_a
    assert prod.canonical_json_bytes(doc_a) == prod.canonical_json_bytes(doc_b)


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
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="partial world set cannot finalize"):
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
    incomplete = prod.aggregate_planned_worlds(_planned_records()[:10])
    assert incomplete["mechanical_conclusion"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
    all_fail_null = _planned_records(
        {("NULL", 5000): {"oracle_model": True, "any_edge": True}}
    )
    repaired = prod.aggregate_planned_worlds(all_fail_null)
    expected = lib.mechanical_conclusion(
        incomplete_execution=False,
        oracle_null_specificity=repaired["verdicts"]["oracle_null_specificity"],
        blind_null_specificity=repaired["verdicts"]["blind_null_specificity"],
        trap_specificity=repaired["verdicts"]["trap_specificity"],
        easy_oracle_power=repaired["verdicts"]["easy_oracle_power"],
        moderate_oracle_power=repaired["verdicts"]["moderate_oracle_power"],
        easy_blind_useful=repaired["verdicts"]["easy_blind_useful"],
        moderate_blind_useful=repaired["verdicts"]["moderate_blind_useful"],
        visibility_wilson_upper=repaired["arms"]["VISIBILITY_FLOOR_EASY_ORACLE"]["interval"]["upper"],
        model_detection_wilson_upper=repaired["arms"]["MODEL_FLOOR_EASY_ORACLE"]["interval"]["upper"],
        materiality_only_failure=repaired["arms"]["MATERIALITY_ONLY_DIAGNOSTIC"][
            "materiality_only_failure"
        ],
    )
    assert repaired["mechanical_conclusion"] == expected
    assert expected == "METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06"


def test_canonical_result_bytes_deterministic(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    aggregates = prod.aggregate_planned_worlds(_planned_records())
    first = prod.bind_result_document(aggregates=aggregates, repo_root=repo)
    second = prod.bind_result_document(aggregates=aggregates, repo_root=repo)
    assert prod.canonical_json_bytes(first) == prod.canonical_json_bytes(second)
    assert first["result_sha256"] == second["result_sha256"]
    assert first["result_size"] == second["result_size"]
    assert first["run_identity"] == prod.canonical_run_identity(repo)
    assert first["frozen_lib_sha256"] == FROZEN_LIB_SHA256
    assert first["real_market_data_access_authorized"] is False
    assert first["b2_06_scientific_execution_authorized"] is False
    assert first["validation_2025_authorized"] is False
    assert first["oos_2026_authorized"] is False
    prod.verify_bound_result_document(first, repo_root=repo)


def test_digest_size_run_identity_tamper_detected(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_prod(monkeypatch, repo)
    document = prod.bind_result_document(
        aggregates=prod.aggregate_planned_worlds(_planned_records()), repo_root=repo
    )
    digest_tamper = dict(document)
    digest_tamper["result_sha256"] = "ab" * 32
    with pytest.raises(prod.ProductionIntegrityError, match="result digest tamper"):
        prod.verify_bound_result_document(digest_tamper, repo_root=repo)
    size_tamper = dict(document)
    size_tamper["result_size"] = int(document["result_size"]) + 1
    with pytest.raises(prod.ProductionIntegrityError, match="result size tamper"):
        prod.verify_bound_result_document(size_tamper, repo_root=repo)
    ident_tamper = dict(document)
    ident_tamper["run_identity"] = "cd" * 32
    ident_tamper["result_sha256"] = _sha(
        prod.canonical_json_bytes(
            {key: value for key, value in ident_tamper.items() if key not in {"result_sha256", "result_size"}}
        )
    )
    ident_tamper["result_size"] = len(
        prod.canonical_json_bytes(
            {key: value for key, value in ident_tamper.items() if key not in {"result_sha256", "result_size"}}
        )
    )
    with pytest.raises(prod.ProductionIntegrityError, match="run_identity tamper"):
        prod.verify_bound_result_document(ident_tamper, repo_root=repo)


def test_114_local_reservation_superseded_when_production_module_tracked(tmp_path, monkeypatch):
    repo = _commit_production_tree(tmp_path)
    _bind_auth(monkeypatch, repo)
    with pytest.raises(lib.SyntheticExecutionNotAuthorized, match="supersedes"):
        auth.run_authorized_production_grid()


def test_cli_uses_fresh_process_and_stays_unarmed():
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "spawn_canonical_production_process" in source
    assert "run_authorized_production_grid" not in source
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
