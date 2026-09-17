"""V3 implementation-freeze and pre-ARM binding tests.

Disposable identities only. These tests never execute world_index
10000..10399, never mint WORLD_RECORDS/RESULT, and never create an ARM
or reservation.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts.research import harness_synthetic_edge_calibration_v3_authority as v3a
from scripts.research.harness_synthetic_edge_calibration_v3_authority import (
    V3ExecutionNotAuthorized,
    V3NotArmed,
)

REPO = Path(__file__).resolve().parents[2]
ACCEPTED_HEAD = v3a.ACCEPTED_IMPLEMENTATION_HEAD
ACCEPTED_TREE = v3a.ACCEPTED_IMPLEMENTATION_TREE
FREEZE_JSON = v3a.CANONICAL_FREEZE_JSON_PATH
FREEZE_MD = v3a.CANONICAL_FREEZE_MD_PATH

AUTHORITY_MUST_BE_UNCHANGED = (
    v3a.CONFIRMATORY_REL,
    v3a.RNG_REL,
    v3a.V1_LIB_REL,
    v3a.CANONICAL_PREREG_MD_PATH,
    v3a.CANONICAL_PREREG_JSON_PATH,
    v3a.CANONICAL_PREREG_FREEZE_JSON_PATH,
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE.md",
    v3a.CONFIRMATORY_TESTS_REL,
    v3a.RNG_TESTS_REL,
)

FREEZE_ALLOWED_CHANGED_PATHS = {
    FREEZE_JSON,
    FREEZE_MD,
    "scripts/research/harness_synthetic_edge_calibration_v3_authority.py",
    "tests/research/test_harness_synthetic_edge_calibration_v3_implementation_freeze.py",
    "docs/PROJECT_STATUS.md",
    "docs/RESEARCH_LEDGER.md",
    "docs/RESEARCH_ROADMAP.md",
    "docs/DOCUMENTATION_INDEX.md",
}

_DISPOSABLE = 900_001


def _git(*args: str, repo: Path = REPO) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _blob(commit: str, path: str, repo: Path = REPO) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), "cat-file", "-p", f"{commit}:{path}"])


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)


def _copy_live(rel: str, dest_root: Path) -> None:
    _write(dest_root / rel, (REPO / rel).read_bytes())


def _commit_binding_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", repo=repo)
    _git("config", "user.email", "test@example.com", repo=repo)
    _git("config", "user.name", "test", repo=repo)
    _git("config", "commit.gpgsign", "false", repo=repo)
    for rel in (
        v3a.CONFIRMATORY_REL,
        v3a.RNG_REL,
        v3a.V1_LIB_REL,
        v3a.CANONICAL_PREREG_MD_PATH,
        v3a.CANONICAL_PREREG_JSON_PATH,
        FREEZE_JSON,
        FREEZE_MD,
        v3a.CONFIRMATORY_TESTS_REL,
        v3a.RNG_TESTS_REL,
    ):
        _copy_live(rel, repo)
    _git("add", "-A", repo=repo)
    _git("commit", "-m", "v3 freeze binding fixture", repo=repo)
    return repo


def _bind(monkeypatch, repo: Path) -> None:
    monkeypatch.setattr(v3a, "_repo_root", lambda: repo)


def _load_freeze(repo: Path | None = None) -> dict:
    root = repo or REPO
    return json.loads((root / FREEZE_JSON).read_text(encoding="utf-8"))


def _dump_freeze(repo: Path, payload: dict) -> None:
    _write(repo / FREEZE_JSON, json.dumps(payload, indent=2) + "\n")
    _git("add", FREEZE_JSON, repo=repo)
    _git("commit", "-m", "mutate freeze", repo=repo)


def test_freeze_binds_accepted_implementation_commit_and_tree():
    freeze = _load_freeze()
    reviewed = freeze["reviewed_implementation"]
    assert reviewed["head"] == ACCEPTED_HEAD
    assert reviewed["tree"] == ACCEPTED_TREE
    assert freeze["freeze_parent_expected_head"] == ACCEPTED_HEAD
    assert _git("rev-parse", f"{ACCEPTED_HEAD}^{{tree}}") == ACCEPTED_TREE
    assert freeze["implementation_review_verdict"] == "IMPLEMENTATION_ACCEPTED"
    assert freeze["findings"] == {"F1": "CLOSED", "F2": "CLOSED", "F3": "CLOSED"}
    assert freeze["explicit_state"]["v3_run_authorized"] is False
    assert freeze["explicit_state"]["v3_armed"] is False
    v3a.load_v3_implementation_freeze()


def test_accepted_scientific_bytes_identical_to_reviewed_head():
    for rel, sha256, size in (
        (v3a.CONFIRMATORY_REL, v3a.FROZEN_CONFIRMATORY_SHA256, v3a.FROZEN_CONFIRMATORY_SIZE),
        (v3a.RNG_REL, v3a.FROZEN_RNG_SHA256, v3a.FROZEN_RNG_SIZE),
        (v3a.V1_LIB_REL, v3a.FROZEN_V1_LIB_SHA256, v3a.FROZEN_V1_LIB_SIZE),
        (v3a.CANONICAL_PREREG_MD_PATH, v3a.FROZEN_PREREG_MD_SHA256, v3a.FROZEN_PREREG_MD_SIZE),
        (v3a.CANONICAL_PREREG_JSON_PATH, v3a.FROZEN_PREREG_JSON_SHA256, v3a.FROZEN_PREREG_JSON_SIZE),
    ):
        head = _blob("HEAD", rel)
        accepted = _blob(ACCEPTED_HEAD, rel)
        assert _sha(head) == sha256
        assert len(head) == size
        assert head == accepted


def test_prereg_freeze_bytes_unchanged():
    for rel, sha256 in (
        (v3a.CANONICAL_PREREG_MD_PATH, v3a.FROZEN_PREREG_MD_SHA256),
        (v3a.CANONICAL_PREREG_JSON_PATH, v3a.FROZEN_PREREG_JSON_SHA256),
        (
            v3a.CANONICAL_PREREG_FREEZE_JSON_PATH,
            "c095570a87bb5fc906a4d781e86c00548d47c22d7259022c0ad02ac877eefe16",
        ),
    ):
        assert _sha(_blob("HEAD", rel)) == sha256
        assert _blob("HEAD", rel) == _blob(ACCEPTED_HEAD, rel)


def test_implementation_file_mutation_rejected(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    v3a.assert_v3_scientific_authority_intact()
    target = repo / v3a.CONFIRMATORY_REL
    target.write_bytes(target.read_bytes() + b"\n# mutated\n")
    _git("add", v3a.CONFIRMATORY_REL, repo=repo)
    _git("commit", "-m", "mutate confirmatory", repo=repo)
    with pytest.raises(V3ExecutionNotAuthorized, match="scientific authority"):
        v3a.assert_v3_scientific_authority_intact()


def test_prereg_mutation_rejected(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    target = repo / v3a.CANONICAL_PREREG_JSON_PATH
    target.write_bytes(target.read_bytes().replace(b"F03", b"F99", 1))
    _git("add", v3a.CANONICAL_PREREG_JSON_PATH, repo=repo)
    _git("commit", "-m", "mutate prereg", repo=repo)
    with pytest.raises(V3ExecutionNotAuthorized, match="scientific authority"):
        v3a.assert_v3_scientific_authority_intact()


def test_rng_shim_mutation_rejected(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    target = repo / v3a.RNG_REL
    target.write_bytes(target.read_bytes() + b"\n# mutated rng\n")
    _git("add", v3a.RNG_REL, repo=repo)
    _git("commit", "-m", "mutate rng", repo=repo)
    with pytest.raises(V3ExecutionNotAuthorized, match="scientific authority"):
        v3a.assert_v3_scientific_authority_intact()


def test_inherited_v1_authority_mutation_rejected(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    target = repo / v3a.V1_LIB_REL
    target.write_bytes(target.read_bytes() + b"\n# mutated v1\n")
    _git("add", v3a.V1_LIB_REL, repo=repo)
    _git("commit", "-m", "mutate v1 lib", repo=repo)
    with pytest.raises(V3ExecutionNotAuthorized, match="scientific authority"):
        v3a.assert_v3_scientific_authority_intact()


def test_selector_authority_mismatch_rejected(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    freeze = _load_freeze(repo)
    freeze["selector_authority"]["source_file_sha256"] = "0" * 64
    _dump_freeze(repo, freeze)
    with pytest.raises(V3ExecutionNotAuthorized, match="selector"):
        v3a.load_v3_implementation_freeze()


def test_canonical_scenario_mutation_rejected(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    freeze = _load_freeze(repo)
    freeze["canonical_v3_execution_spec"]["scenarios"] = [
        "EASY",
        "MODERATE",
        "NULL",
        "SMALL",
    ]
    _dump_freeze(repo, freeze)
    with pytest.raises(V3ExecutionNotAuthorized, match="scenario"):
        v3a.load_v3_implementation_freeze()


def test_canonical_range_mutation_rejected(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    freeze = _load_freeze(repo)
    freeze["canonical_v3_execution_spec"]["world_index_start"] = 0
    _dump_freeze(repo, freeze)
    with pytest.raises(V3ExecutionNotAuthorized, match="world_index_start"):
        v3a.load_v3_implementation_freeze()


def test_worlds_per_cell_mutation_rejected(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    freeze = _load_freeze(repo)
    freeze["canonical_v3_execution_spec"]["worlds_per_cell"] = 200
    _dump_freeze(repo, freeze)
    with pytest.raises(V3ExecutionNotAuthorized, match="worlds_per_cell"):
        v3a.load_v3_implementation_freeze()


def test_b_mutation_rejected(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    freeze = _load_freeze(repo)
    freeze["canonical_v3_execution_spec"]["bootstrap_replicates"] = 500
    _dump_freeze(repo, freeze)
    with pytest.raises(V3ExecutionNotAuthorized, match="canonical B"):
        v3a.load_v3_implementation_freeze()


def test_feature_mutation_rejected(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    freeze = _load_freeze(repo)
    freeze["canonical_v3_execution_spec"]["feature_id"] = "F01"
    _dump_freeze(repo, freeze)
    with pytest.raises(V3ExecutionNotAuthorized, match="feature"):
        v3a.load_v3_implementation_freeze()


def test_acceptance_boundary_mutation_rejected(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    freeze = _load_freeze(repo)
    freeze["canonical_v3_execution_spec"]["acceptance_cells"]["EASY"]["PASS_min_x"] = 1
    _dump_freeze(repo, freeze)
    with pytest.raises(V3ExecutionNotAuthorized, match="acceptance-boundary|verdict-map"):
        v3a.load_v3_implementation_freeze()


def test_caller_cannot_redirect_scientific_paths(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    evil = tmp_path / "evil.json"
    evil.write_text("{}", encoding="utf-8")
    with pytest.raises(V3ExecutionNotAuthorized, match="caller arguments"):
        v3a.load_v3_implementation_freeze(path=str(evil))
    with pytest.raises(V3ExecutionNotAuthorized, match="caller arguments"):
        v3a.canonical_v3_execution_spec(prereg_path=str(evil))
    with pytest.raises(V3ExecutionNotAuthorized, match="caller arguments"):
        v3a.derive_v3_run_identity(run_identity="forged")
    monkeypatch.setenv("HARNESS_V3_PREREG_PATH", str(evil))
    monkeypatch.setenv("V3_FREEZE_PATH", str(evil))
    with pytest.raises(V3ExecutionNotAuthorized, match="environment substitution"):
        v3a.load_v3_implementation_freeze()


def test_dirty_scientific_worktree_fails_closed(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    v3a.assert_v3_executed_bytes_bound()
    target = repo / v3a.CONFIRMATORY_REL
    target.write_bytes(target.read_bytes() + b"\n# dirty\n")
    with pytest.raises(V3ExecutionNotAuthorized, match="worktree mutation|clean verified freeze"):
        v3a.assert_v3_scientific_authority_intact()
    with pytest.raises(V3ExecutionNotAuthorized, match="worktree mutation|clean verified freeze"):
        v3a.assert_v3_executed_bytes_bound()


def test_run_identity_deterministic_for_identical_frozen_authority(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    first = v3a.derive_v3_run_identity()
    second = v3a.derive_v3_run_identity()
    assert first == second
    assert len(first) == 64


def test_scientific_authority_mutation_changes_or_rejects_identity(tmp_path, monkeypatch):
    repo = _commit_binding_repo(tmp_path)
    _bind(monkeypatch, repo)
    baseline = v3a.derive_v3_run_identity()
    freeze = _load_freeze(repo)
    freeze["prereg_authority"]["prereg_freeze_head"] = "0" * 40
    _dump_freeze(repo, freeze)
    with pytest.raises(V3ExecutionNotAuthorized, match="prereg freeze head"):
        v3a.derive_v3_run_identity()
    _ = baseline


def test_imported_constant_mutation_rejected(monkeypatch):
    monkeypatch.setattr(v3a, "V3_PRIMARY_SCENARIOS", ("EASY", "NULL"))
    with pytest.raises(V3ExecutionNotAuthorized, match="scenarios"):
        v3a._imported_grid()
    monkeypatch.setattr(v3a, "V3_PRIMARY_SCENARIOS", v3a.FROZEN_SCENARIOS)
    monkeypatch.setattr(v3a, "V3_STATIONARY_BOOTSTRAP_REPLICATES", 500)
    with pytest.raises(V3ExecutionNotAuthorized, match="imported B"):
        v3a._imported_grid()
    monkeypatch.setattr(v3a, "V3_STATIONARY_BOOTSTRAP_REPLICATES", 999)
    monkeypatch.setattr(v3a, "V3_CANDIDATE_FEATURE_ID", "F01")
    with pytest.raises(V3ExecutionNotAuthorized, match="feature"):
        v3a._imported_grid()
    monkeypatch.setattr(v3a, "V3_CANDIDATE_FEATURE_ID", "F03")
    monkeypatch.setattr(v3a, "V3_WORLD_INDEX_START", 0)
    with pytest.raises(V3ExecutionNotAuthorized, match="world_index_start"):
        v3a._imported_grid()
    monkeypatch.setattr(v3a, "V3_WORLD_INDEX_START", 10000)
    monkeypatch.setattr(v3a, "V3_FRESH_WORLD_COUNT_PER_SCENARIO", 200)
    with pytest.raises(V3ExecutionNotAuthorized, match="worlds_per_cell"):
        v3a._imported_grid()


def test_disposable_tests_cannot_consume_canonical_world_indices():
    v3a.assert_index_not_canonical(_DISPOSABLE)
    with pytest.raises(V3ExecutionNotAuthorized, match="canonical world indices"):
        v3a.assert_index_not_canonical(10000)
    with pytest.raises(V3ExecutionNotAuthorized, match="canonical world indices"):
        v3a.assert_index_not_canonical(10399)
    with pytest.raises(V3ExecutionNotAuthorized, match="V1/V2"):
        v3a.assert_index_not_canonical(0)
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    called = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            called.add(func.id)
        elif isinstance(func, ast.Attribute):
            called.add(func.attr)
    assert "evaluate_v3_world" not in called
    assert "simulate_dgp" not in called


def test_no_canonical_result_or_reservation_before_arm():
    assert v3a.v3_arm_authorized() is False
    assert v3a.v3_protected_artifacts_present() is False
    with pytest.raises(V3NotArmed):
        v3a.run_canonical_v3_grid()
    with pytest.raises(V3ExecutionNotAuthorized, match="not authorized before ARM"):
        v3a.evaluate_v3_canonical_world("EASY", 5000, 10000)
    with pytest.raises(V3ExecutionNotAuthorized, match="reservation"):
        v3a.reserve_v3_canonical_run()
    with pytest.raises(V3ExecutionNotAuthorized, match="WORLD_RECORDS"):
        v3a.mint_v3_world_records()
    with pytest.raises(V3ExecutionNotAuthorized, match="RESULT"):
        v3a.mint_v3_result()
    for rel in v3a.PROTECTED_V3_AUTHORITY_PATHS:
        assert (REPO / rel).exists() is False
        proc = subprocess.run(
            ["git", "-C", str(REPO), "cat-file", "-e", f"HEAD:{rel}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        assert proc.returncode != 0


def test_historical_v1_v2_evidence_untouched():
    v1_lib = _blob("HEAD", v3a.V1_LIB_REL)
    assert _sha(v1_lib) == v3a.FROZEN_V1_LIB_SHA256
    assert v1_lib == _blob(ACCEPTED_HEAD, v3a.V1_LIB_REL)
    v2_result = (
        "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_RESULT.json"
    )
    assert _blob("HEAD", v2_result) == _blob(ACCEPTED_HEAD, v2_result)


def test_canonical_grid_binding_identity_only():
    spec = v3a.canonical_v3_execution_spec()
    assert spec["scenarios"] == list(v3a.FROZEN_SCENARIOS)
    assert spec["world_index_start"] == 10000
    assert spec["world_index_end"] == 10399
    assert spec["worlds_per_cell"] == 400
    assert spec["planned_worlds"] == 1600
    assert spec["bootstrap_replicates"] == 999
    assert spec["feature_id"] == "F03"
    jobs = v3a.canonical_v3_jobs()
    assert len(jobs) == 1600
    assert jobs[0] == ("EASY", 5000, 10000)
    assert jobs[-1] == ("NONSTATIONARY_TRAP", 5000, 10399)
    state = v3a.v3_pre_arm_state()
    assert state["v3_implementation_frozen"] is True
    assert state["v3_pre_arm_binding_complete"] is True
    assert state["v3_run_authorized"] is False
    assert state["v3_armed"] is False
    assert state["world_records_created"] is False
    assert state["result_minted"] is False
    fields = v3a.required_v3_arm_binding_fields()
    assert fields["authorization_consumed"] is False
    assert fields["canonical_world_count"] == 1600
    assert fields["b2_06_scientific_execution_authorized"] is False
    assert (REPO / v3a.CANONICAL_V3_ARM_PATH).exists() is False


def test_freeze_commit_does_not_change_scientific_bytes():
    if FREEZE_JSON not in _git("ls-tree", "-r", "--name-only", "HEAD"):
        pytest.skip("freeze artifact not yet committed")
    added = _git("log", "--diff-filter=A", "--format=%H", "--", FREEZE_JSON).splitlines()
    assert added, "freeze artifact must be added by a tracked commit"
    freeze_commit = added[-1]
    parent = _git("rev-parse", f"{freeze_commit}^")
    assert parent == ACCEPTED_HEAD
    for path in AUTHORITY_MUST_BE_UNCHANGED:
        assert _git("diff", f"{ACCEPTED_HEAD}..HEAD", "--", path) == ""
    changed = set(_git("diff-tree", "--no-commit-id", "--name-only", "-r", freeze_commit).splitlines())
    assert FREEZE_JSON in changed
    later = set(_git("diff", "--name-only", f"{ACCEPTED_HEAD}..HEAD").splitlines())
    assert later <= FREEZE_ALLOWED_CHANGED_PATHS
    for path in AUTHORITY_MUST_BE_UNCHANGED:
        assert path not in later
