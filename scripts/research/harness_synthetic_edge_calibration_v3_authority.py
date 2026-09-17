"""V3 implementation-freeze / pre-ARM execution binding.

This module does not redefine V3 scientific semantics. It records and
enforces already-accepted authority so a later unit can arm exactly one
canonical V3 execution.

It does not ARM, reserve, execute world_index 10000..10399, or mint
WORLD_RECORDS / RESULT. Caller kwargs, environment variables, and
alternate paths cannot substitute scientific authority.

Reuse: ``verify_git_freeze``, ``canonical_json_bytes``,
``SyntheticExecutionNotAuthorized``. Freeze identity is never hardcoded
here (self-reference cycle); the freeze artifact at the canonical path is
authenticated against the accepted implementation commit/tree and the
byte hashes recorded below.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    SyntheticExecutionNotAuthorized,
)
from scripts.research.harness_synthetic_edge_calibration_v1_production import (
    canonical_json_bytes,
)
from scripts.research.harness_synthetic_edge_calibration_v3_confirmatory import (
    V3_AGGREGATE_TARGETS,
    V3_CANDIDATE_FEATURE_ID,
    V3_FRESH_WORLD_COUNT_PER_SCENARIO,
    V3_PRIMARY_SCENARIOS,
    V3_STATIONARY_BOOTSTRAP_REPLICATES,
    V3_WILSON_Z_ONE_SIDED,
    V3_WORLD_INDEX_END,
    V3_WORLD_INDEX_START,
    is_fresh_v3_world_index,
)
from scripts.research.lib.research_harness import CodeIdentityError, verify_git_freeze

CANONICAL_FREEZE_JSON_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_IMPLEMENTATION_FREEZE.json"
)
CANONICAL_FREEZE_MD_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_IMPLEMENTATION_FREEZE.md"
)
CANONICAL_PREREG_MD_PATH = "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md"
CANONICAL_PREREG_JSON_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.json"
)
CANONICAL_PREREG_FREEZE_JSON_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE.json"
)
CANONICAL_V3_ARM_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PRODUCTION_ARM.json"
)
CANONICAL_V3_RESERVATION_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PRODUCTION_RESERVATION.json"
)
CANONICAL_V3_WORLD_RECORDS_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_WORLD_RECORDS.json"
)
CANONICAL_V3_RESULT_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_RESULT.json"
)
CANONICAL_V3_CLAIM_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PRODUCTION_CLAIM.json"
)

CONFIRMATORY_REL = (
    "scripts/research/harness_synthetic_edge_calibration_v3_confirmatory.py"
)
RNG_REL = "scripts/research/harness_synthetic_edge_calibration_v3_rng.py"
V1_LIB_REL = "scripts/research/harness_synthetic_edge_calibration_v1_lib.py"
CONFIRMATORY_TESTS_REL = (
    "tests/research/test_harness_synthetic_edge_calibration_v3_confirmatory.py"
)
RNG_TESTS_REL = "tests/research/test_harness_synthetic_edge_calibration_v3_rng.py"

ACCEPTED_IMPLEMENTATION_HEAD = (
    "70673673f5bc0108e6bcf2aaf55a762ebc49940a"
)
ACCEPTED_IMPLEMENTATION_TREE = (
    "e94e18cb900a44824b96dee1d4b6cbb574c95e5a"
)
PREREG_FREEZE_HEAD = "fd21ed7f8cf8279d367d7a7cf3f1740398d73883"
PREREG_FREEZE_TREE = "a854578e6d88ef2d6f546824f3196e33f4e95e55"
PREREG_CONTENT_HEAD = "543687fe79ba2e6254e879b0574e58a1909c15fe"

FROZEN_CONFIRMATORY_SHA256 = (
    "38a494917dcf721b828a7c3f885d4c60ab6df437003abc0c71e510e33b4b0505"
)
FROZEN_CONFIRMATORY_SIZE = 24059
FROZEN_RNG_SHA256 = (
    "8bd6aef151139bc1afd4d890d7ba293b1adec5cf66b405dde677eccb3b06d698"
)
FROZEN_RNG_SIZE = 2325
FROZEN_PREREG_MD_SHA256 = (
    "ab03c68a3781c13cf5ba74d08d6c212dd9da42b87f7642700cf79294147918e0"
)
FROZEN_PREREG_MD_SIZE = 29885
FROZEN_PREREG_JSON_SHA256 = (
    "194fed692018560661879dc67e14a4d139c79978fc0dac00aa6e0f934bd399b5"
)
FROZEN_PREREG_JSON_SIZE = 35373
FROZEN_V1_LIB_SHA256 = (
    "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
)
FROZEN_V1_LIB_SIZE = 37636
FROZEN_CONFIRMATORY_TESTS_SHA256 = (
    "97125ae8aa0af16095ccfa651a1c3e32f8978c5881305f98161338d7533a696a"
)
FROZEN_RNG_TESTS_SHA256 = (
    "3412ea308a46dd2043d91355ce435fa1924c35f8cb8df2eee15c314add528f51"
)

FROZEN_SELECTOR_AUTHORITY = {
    "package": "arch",
    "package_version": "8.0.0",
    "source_file": "arch/bootstrap/base.py",
    "source_file_sha256": (
        "104d3552a8e79a801e2f8cd0401160f83a7263b4ff13da44a82d763e5664fd21"
    ),
    "source_file_size_bytes": 60275,
    "public_entry_point": "arch.bootstrap.optimal_block_length",
    "public_entry_point_source_sha256": (
        "b70543178ffb368cb22490f508de9bf35152eb9882ca4b66f26d338c5f1f4f12"
    ),
    "implementing_function": "_single_optimal_block",
    "implementing_function_source_sha256": (
        "355cfaf81a09a42f32dd643d2cd5fd39a78d16faec1e4cc06a79a83d729b7421"
    ),
}

FROZEN_SCENARIOS = ("EASY", "MODERATE", "NULL", "NONSTATIONARY_TRAP")
FROZEN_N_ROWS = 5000
FROZEN_WORLD_INDEX_START = 10000
FROZEN_WORLD_INDEX_END = 10399
FROZEN_WORLDS_PER_CELL = 400
FROZEN_PLANNED_WORLDS = 1600
FROZEN_B = 999
FROZEN_FEATURE_ID = "F03"
FROZEN_WILSON_Z = 1.6448536269514722
FROZEN_ACCEPTANCE = {
    "EASY": {
        "kind": "power_min",
        "value": 0.9,
        "PASS_min_x": 370,
        "FAIL_max_x": 350,
        "INDETERMINATE_x_range": [351, 369],
    },
    "MODERATE": {
        "kind": "power_min",
        "value": 0.7,
        "PASS_min_x": 296,
        "FAIL_max_x": 264,
        "INDETERMINATE_x_range": [265, 295],
    },
    "NULL": {
        "kind": "fpr_max",
        "value": 0.05,
        "PASS_max_x": 12,
        "FAIL_min_x": 28,
        "INDETERMINATE_x_range": [13, 27],
    },
    "NONSTATIONARY_TRAP": {
        "kind": "detect_max",
        "value": 0.2,
        "PASS_max_x": 66,
        "FAIL_min_x": 94,
        "INDETERMINATE_x_range": [67, 93],
    },
}

SCIENTIFIC_PATHS = (
    CONFIRMATORY_REL,
    RNG_REL,
    V1_LIB_REL,
    CANONICAL_PREREG_MD_PATH,
    CANONICAL_PREREG_JSON_PATH,
)
PROTECTED_V3_AUTHORITY_PATHS = (
    CANONICAL_V3_ARM_PATH,
    CANONICAL_V3_RESERVATION_PATH,
    CANONICAL_V3_WORLD_RECORDS_PATH,
    CANONICAL_V3_RESULT_PATH,
    CANONICAL_V3_CLAIM_PATH,
)
_FORBIDDEN_ENV = (
    "HARNESS_V3_PREREG_PATH",
    "HARNESS_V3_PREREG_JSON",
    "HARNESS_V3_FREEZE_PATH",
    "HARNESS_V3_IMPL_PATH",
    "HARNESS_V3_RNG_PATH",
    "V3_PREREG_PATH",
    "V3_FREEZE_PATH",
)


class V3ExecutionNotAuthorized(SyntheticExecutionNotAuthorized):
    """V3 canonical execution is not authorized by freeze/pre-ARM binding."""


class V3NotArmed(V3ExecutionNotAuthorized):
    """V3 canonical Monte Carlo is not armed."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _refuse(detail: str) -> None:
    raise V3ExecutionNotAuthorized(f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {detail}")


def _reject_caller_kwargs(args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> None:
    if args or kwargs:
        _refuse("caller arguments cannot redefine V3 scientific authority")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _require_git_ok(proc: subprocess.CompletedProcess[bytes], what: str) -> bytes:
    if proc.returncode != 0:
        _refuse(f"git {what} failed")
    return proc.stdout


def _head_sha(repo_root: Path) -> str:
    proc = _run_git(repo_root, "rev-parse", "HEAD")
    return _require_git_ok(proc, "rev-parse HEAD").decode("ascii").strip().lower()


def _tree_sha(repo_root: Path) -> str:
    proc = _run_git(repo_root, "rev-parse", "HEAD^{tree}")
    return _require_git_ok(proc, "rev-parse HEAD^{tree}").decode("ascii").strip().lower()


def _commit_blob(repo_root: Path, commit: str, git_path: str) -> bytes | None:
    if git_path.startswith("/") or ".." in Path(git_path).parts:
        _refuse("scientific path is not canonical")
    proc = _run_git(repo_root, "cat-file", "-e", f"{commit}:{git_path}")
    if proc.returncode != 0:
        return None
    proc = _run_git(repo_root, "cat-file", "blob", f"{commit}:{git_path}")
    return _require_git_ok(proc, f"cat-file {commit}:{git_path}")


def _worktree_bytes(repo_root: Path, rel: str) -> bytes:
    if rel.startswith("/") or ".." in Path(rel).parts:
        _refuse("scientific path is not canonical")
    path = repo_root / rel
    if path.is_symlink() or not path.is_file():
        _refuse(f"scientific file missing or not a regular file: {rel}")
    return path.read_bytes()


def _refuse_env_substitution() -> None:
    for key in _FORBIDDEN_ENV:
        if os.environ.get(key):
            _refuse(f"environment substitution of scientific authority is forbidden ({key})")


def _file_record(path: str, sha256: str, size: int) -> dict[str, Any]:
    return {"path": path, "sha256": sha256, "size_bytes": size}


def _literal_grid() -> dict[str, Any]:
    return {
        "scenarios": list(FROZEN_SCENARIOS),
        "n_rows": int(FROZEN_N_ROWS),
        "world_index_start": int(FROZEN_WORLD_INDEX_START),
        "world_index_end": int(FROZEN_WORLD_INDEX_END),
        "worlds_per_cell": int(FROZEN_WORLDS_PER_CELL),
        "planned_worlds": int(FROZEN_PLANNED_WORLDS),
        "bootstrap_replicates": int(FROZEN_B),
        "feature_id": str(FROZEN_FEATURE_ID),
        "wilson_z": float(FROZEN_WILSON_Z),
        "acceptance_cells": {
            cell: {
                "kind": spec["kind"],
                "value": spec["value"],
                **(
                    {"PASS_min_x": spec["PASS_min_x"], "FAIL_max_x": spec["FAIL_max_x"]}
                    if "PASS_min_x" in spec
                    else {"PASS_max_x": spec["PASS_max_x"], "FAIL_min_x": spec["FAIL_min_x"]}
                ),
                "INDETERMINATE_x_range": list(spec["INDETERMINATE_x_range"]),
            }
            for cell, spec in FROZEN_ACCEPTANCE.items()
        },
    }


def _imported_grid() -> dict[str, Any]:
    if tuple(V3_PRIMARY_SCENARIOS) != FROZEN_SCENARIOS:
        _refuse("imported confirmatory scenarios are not the frozen authority")
    if int(V3_WORLD_INDEX_START) != FROZEN_WORLD_INDEX_START:
        _refuse("imported world_index_start is not the frozen authority")
    if int(V3_WORLD_INDEX_END) != FROZEN_WORLD_INDEX_END:
        _refuse("imported world_index_end is not the frozen authority")
    if int(V3_FRESH_WORLD_COUNT_PER_SCENARIO) != FROZEN_WORLDS_PER_CELL:
        _refuse("imported worlds_per_cell is not the frozen authority")
    if int(V3_STATIONARY_BOOTSTRAP_REPLICATES) != FROZEN_B:
        _refuse("imported B is not the frozen authority")
    if str(V3_CANDIDATE_FEATURE_ID) != FROZEN_FEATURE_ID:
        _refuse("imported feature identity is not the frozen authority")
    if float(V3_WILSON_Z_ONE_SIDED) != FROZEN_WILSON_Z:
        _refuse("imported Wilson z is not the frozen authority")
    if set(V3_AGGREGATE_TARGETS) != set(FROZEN_ACCEPTANCE):
        _refuse("imported acceptance cells are not the frozen authority")
    for cell, spec in FROZEN_ACCEPTANCE.items():
        live = V3_AGGREGATE_TARGETS[cell]
        if live["kind"] != spec["kind"] or float(live["value"]) != float(spec["value"]):
            _refuse(f"imported acceptance mapping drifted for {cell}")
    return _literal_grid()


def _bound_file_sha256(entry: Mapping[str, Any]) -> str:
    return str(entry.get("sha256", "")).lower()


def _require_bound_file(
    freeze: Mapping[str, Any],
    *,
    collection: str,
    role: str | None,
    path: str,
    sha256: str,
    size: int | None = None,
) -> None:
    if collection == "inherited_v1_scientific_authority":
        entry = freeze.get(collection)
        if not isinstance(entry, Mapping):
            _refuse("missing inherited V1 scientific authority")
        entries = [entry]
    elif collection == "prereg_authority":
        block = freeze.get("prereg_authority")
        if not isinstance(block, Mapping) or not isinstance(block.get("files"), list):
            _refuse("missing prereg_authority files")
        entries = block["files"]
    elif collection == "selector_authority":
        entry = freeze.get(collection)
        if not isinstance(entry, Mapping):
            _refuse("missing selector authority")
        if str(entry.get("source_file_sha256", "")).lower() != FROZEN_SELECTOR_AUTHORITY[
            "source_file_sha256"
        ]:
            _refuse("selector source_file_sha256 is not the frozen arch 8.0.0 authority")
        if str(entry.get("implementing_function_source_sha256", "")).lower() != (
            FROZEN_SELECTOR_AUTHORITY["implementing_function_source_sha256"]
        ):
            _refuse("selector implementing_function hash is not the frozen authority")
        if str(entry.get("public_entry_point_source_sha256", "")).lower() != (
            FROZEN_SELECTOR_AUTHORITY["public_entry_point_source_sha256"]
        ):
            _refuse("selector public_entry_point hash is not the frozen authority")
        if str(entry.get("package_version", "")) != "8.0.0":
            _refuse("selector package_version is not arch 8.0.0")
        return
    else:
        raw = freeze.get(collection)
        if not isinstance(raw, list):
            _refuse(f"missing {collection}")
        entries = raw
    match = None
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        if role is not None and entry.get("role") != role:
            continue
        if entry.get("path") == path:
            match = entry
            break
    if match is None:
        _refuse(f"freeze does not bind {path}")
    if _bound_file_sha256(match) != sha256.lower():
        _refuse(f"freeze hash mismatch for {path}")
    if size is not None and int(match.get("size_bytes", -1)) != int(size):
        _refuse(f"freeze size mismatch for {path}")


def _load_freeze_payload(repo_root: Path) -> dict[str, Any]:
    raw = _worktree_bytes(repo_root, CANONICAL_FREEZE_JSON_PATH)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        _refuse("implementation freeze artifact is not valid JSON")
    if not isinstance(payload, dict):
        _refuse("implementation freeze artifact is not an object")
    if payload.get("schema") != "harness_synthetic_edge_calibration_v3_implementation_freeze":
        _refuse("implementation freeze schema is not the V3 freeze schema")
    if payload.get("unit_id") != "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_IMPLEMENTATION_FREEZE":
        _refuse("implementation freeze unit_id mismatch")
    if payload.get("implementation_review_verdict") != "IMPLEMENTATION_ACCEPTED":
        _refuse("implementation freeze is not IMPLEMENTATION_ACCEPTED")
    reviewed = payload.get("reviewed_implementation")
    if not isinstance(reviewed, Mapping):
        _refuse("missing reviewed_implementation")
    if str(reviewed.get("head", "")).lower() != ACCEPTED_IMPLEMENTATION_HEAD:
        _refuse("freeze does not bind the accepted implementation commit")
    if str(reviewed.get("tree", "")).lower() != ACCEPTED_IMPLEMENTATION_TREE:
        _refuse("freeze does not bind the accepted implementation tree")
    if str(payload.get("freeze_parent_expected_head", "")).lower() != ACCEPTED_IMPLEMENTATION_HEAD:
        _refuse("freeze_parent_expected_head is not the accepted implementation")
    prereg = payload.get("prereg_authority")
    if not isinstance(prereg, Mapping):
        _refuse("missing prereg_authority")
    if str(prereg.get("prereg_freeze_head", "")).lower() != PREREG_FREEZE_HEAD:
        _refuse("freeze does not bind the frozen V3 prereg freeze head")
    _require_bound_file(
        payload,
        collection="execution_authoritative_implementation_sources",
        role="CONFIRMATORY",
        path=CONFIRMATORY_REL,
        sha256=FROZEN_CONFIRMATORY_SHA256,
        size=FROZEN_CONFIRMATORY_SIZE,
    )
    _require_bound_file(
        payload,
        collection="execution_authoritative_implementation_sources",
        role="RNG_SHIM",
        path=RNG_REL,
        sha256=FROZEN_RNG_SHA256,
        size=FROZEN_RNG_SIZE,
    )
    _require_bound_file(
        payload,
        collection="prereg_authority",
        role="PREREG_MD",
        path=CANONICAL_PREREG_MD_PATH,
        sha256=FROZEN_PREREG_MD_SHA256,
        size=FROZEN_PREREG_MD_SIZE,
    )
    _require_bound_file(
        payload,
        collection="prereg_authority",
        role="PREREG_JSON",
        path=CANONICAL_PREREG_JSON_PATH,
        sha256=FROZEN_PREREG_JSON_SHA256,
        size=FROZEN_PREREG_JSON_SIZE,
    )
    _require_bound_file(
        payload,
        collection="inherited_v1_scientific_authority",
        role=None,
        path=V1_LIB_REL,
        sha256=FROZEN_V1_LIB_SHA256,
        size=FROZEN_V1_LIB_SIZE,
    )
    _require_bound_file(
        payload,
        collection="selector_authority",
        role=None,
        path=FROZEN_SELECTOR_AUTHORITY["source_file"],
        sha256=FROZEN_SELECTOR_AUTHORITY["source_file_sha256"],
    )
    _require_bound_file(
        payload,
        collection="accepted_implementation_test_identity",
        role="CONFIRMATORY_TESTS",
        path=CONFIRMATORY_TESTS_REL,
        sha256=FROZEN_CONFIRMATORY_TESTS_SHA256,
    )
    _require_bound_file(
        payload,
        collection="accepted_implementation_test_identity",
        role="RNG_TESTS",
        path=RNG_TESTS_REL,
        sha256=FROZEN_RNG_TESTS_SHA256,
    )
    spec = payload.get("canonical_v3_execution_spec")
    if not isinstance(spec, Mapping):
        _refuse("missing canonical_v3_execution_spec")
    _require_spec_matches_frozen(spec)
    state = payload.get("explicit_state")
    if not isinstance(state, Mapping):
        _refuse("missing explicit_state")
    if state.get("v3_run_authorized") is not False or state.get("v3_armed") is not False:
        _refuse("implementation freeze cannot itself authorize or ARM V3")
    return payload


def _require_spec_matches_frozen(spec: Mapping[str, Any]) -> None:
    expected = _literal_grid()
    if list(spec.get("scenarios") or []) != expected["scenarios"]:
        _refuse("canonical scenario set is not the frozen prereg set")
    if int(spec.get("world_index_start", -1)) != expected["world_index_start"]:
        _refuse("canonical world_index_start is not the frozen prereg range")
    if int(spec.get("world_index_end", -1)) != expected["world_index_end"]:
        _refuse("canonical world_index_end is not the frozen prereg range")
    if int(spec.get("worlds_per_cell", -1)) != expected["worlds_per_cell"]:
        _refuse("canonical worlds_per_cell is not the frozen prereg value")
    if int(spec.get("planned_worlds", -1)) != expected["planned_worlds"]:
        _refuse("canonical planned_worlds is not 1600")
    if int(spec.get("bootstrap_replicates", -1)) != expected["bootstrap_replicates"]:
        _refuse("canonical B is not the frozen prereg value")
    if str(spec.get("feature_id", "")) != expected["feature_id"]:
        _refuse("canonical feature identity is not F03")
    if int(spec.get("n_rows", -1)) != expected["n_rows"]:
        _refuse("canonical n_rows is not the frozen prereg value")
    wilson = spec.get("wilson")
    if not isinstance(wilson, Mapping) or float(wilson.get("z", 0.0)) != FROZEN_WILSON_Z:
        _refuse("canonical Wilson z is not the frozen one-sided authority")
    cells = spec.get("acceptance_cells")
    if not isinstance(cells, Mapping):
        _refuse("missing acceptance_cells")
    if set(cells) != set(FROZEN_ACCEPTANCE):
        _refuse("acceptance cell set is not the frozen mapping")
    for cell, expected_cell in FROZEN_ACCEPTANCE.items():
        got = cells.get(cell)
        if not isinstance(got, Mapping):
            _refuse(f"missing acceptance cell {cell}")
        for key, value in expected_cell.items():
            actual = got.get(key)
            if key == "INDETERMINATE_x_range":
                if list(actual or []) != list(value):
                    _refuse(f"acceptance-boundary/verdict-map mutation rejected for {cell}.{key}")
            elif actual != value:
                _refuse(f"acceptance-boundary/verdict-map mutation rejected for {cell}.{key}")


def _assert_bytes_match_frozen(repo_root: Path) -> dict[str, dict[str, Any]]:
    expected = {
        CONFIRMATORY_REL: (FROZEN_CONFIRMATORY_SHA256, FROZEN_CONFIRMATORY_SIZE),
        RNG_REL: (FROZEN_RNG_SHA256, FROZEN_RNG_SIZE),
        V1_LIB_REL: (FROZEN_V1_LIB_SHA256, FROZEN_V1_LIB_SIZE),
        CANONICAL_PREREG_MD_PATH: (FROZEN_PREREG_MD_SHA256, FROZEN_PREREG_MD_SIZE),
        CANONICAL_PREREG_JSON_PATH: (FROZEN_PREREG_JSON_SHA256, FROZEN_PREREG_JSON_SIZE),
    }
    records: dict[str, dict[str, Any]] = {}
    head = _head_sha(repo_root)
    for rel, (sha256, size) in expected.items():
        worktree = _worktree_bytes(repo_root, rel)
        if len(worktree) != size or _sha256_bytes(worktree) != sha256:
            _refuse(f"worktree mutation of scientific authority rejected: {rel}")
        blob = _commit_blob(repo_root, "HEAD", rel)
        if blob is None or _sha256_bytes(blob) != sha256 or len(blob) != size:
            _refuse(f"HEAD blob is not the frozen scientific authority: {rel}")
        accepted = _commit_blob(repo_root, ACCEPTED_IMPLEMENTATION_HEAD, rel)
        if accepted is not None and _sha256_bytes(accepted) != sha256:
            _refuse(f"accepted implementation commit no longer matches freeze for {rel}")
        records[rel] = _file_record(rel, sha256, size)
    _ = head
    return records


def _scientific_run_identity_payload(
    freeze: Mapping[str, Any], file_records: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    grid = _literal_grid()
    return {
        "schema": "harness_synthetic_edge_calibration_v3_scientific_run_identity",
        "schema_version": "1.0.0",
        "prereg_freeze_head": PREREG_FREEZE_HEAD,
        "prereg_freeze_tree": PREREG_FREEZE_TREE,
        "prereg_content_head": PREREG_CONTENT_HEAD,
        "accepted_implementation_head": ACCEPTED_IMPLEMENTATION_HEAD,
        "accepted_implementation_tree": ACCEPTED_IMPLEMENTATION_TREE,
        "freeze_unit_id": freeze["unit_id"],
        "confirmatory": file_records[CONFIRMATORY_REL],
        "rng_shim": file_records[RNG_REL],
        "prereg_md": file_records[CANONICAL_PREREG_MD_PATH],
        "prereg_json": file_records[CANONICAL_PREREG_JSON_PATH],
        "inherited_v1_lib": file_records[V1_LIB_REL],
        "selector_authority": dict(FROZEN_SELECTOR_AUTHORITY),
        "canonical_grid": grid,
        "accepted_implementation_test_identity": {
            "confirmatory_tests_sha256": FROZEN_CONFIRMATORY_TESTS_SHA256,
            "rng_tests_sha256": FROZEN_RNG_TESTS_SHA256,
        },
    }


def load_v3_implementation_freeze(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Load and authenticate the tracked V3 implementation-freeze artifact."""
    _reject_caller_kwargs(args, kwargs)
    _refuse_env_substitution()
    return _load_freeze_payload(_repo_root())


def assert_v3_scientific_authority_intact(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Fail closed if any bound scientific byte or imported constant drifted."""
    _reject_caller_kwargs(args, kwargs)
    _refuse_env_substitution()
    repo_root = _repo_root()
    freeze = _load_freeze_payload(repo_root)
    records = _assert_bytes_match_frozen(repo_root)
    _imported_grid()
    return {"freeze": freeze, "files": records}


def canonical_v3_execution_spec(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Bind the prereg canonical grid. Does not consume world identities."""
    _reject_caller_kwargs(args, kwargs)
    assert_v3_scientific_authority_intact()
    spec = _literal_grid()
    if tuple(spec["scenarios"]) != FROZEN_SCENARIOS:
        _refuse("canonical scenario mutation rejected")
    if (
        spec["world_index_start"] != FROZEN_WORLD_INDEX_START
        or spec["world_index_end"] != FROZEN_WORLD_INDEX_END
    ):
        _refuse("canonical range mutation rejected")
    return spec


def canonical_v3_jobs(*args: Any, **kwargs: Any) -> tuple[tuple[str, int, int], ...]:
    """Identity of the 1600 canonical jobs. Does not execute them."""
    _reject_caller_kwargs(args, kwargs)
    spec = canonical_v3_execution_spec()
    jobs = tuple(
        (scenario, int(spec["n_rows"]), world_index)
        for scenario in spec["scenarios"]
        for world_index in range(int(spec["world_index_start"]), int(spec["world_index_end"]) + 1)
    )
    if len(jobs) != FROZEN_PLANNED_WORLDS:
        _refuse("canonical job count is not 1600")
    return jobs


def canonical_v3_plan(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Deterministic plan identity from frozen authority only."""
    _reject_caller_kwargs(args, kwargs)
    freeze = load_v3_implementation_freeze()
    records = _assert_bytes_match_frozen(_repo_root())
    payload = _scientific_run_identity_payload(freeze, records)
    digest = _sha256_bytes(canonical_json_bytes(payload))
    return {"payload": payload, "sha256": digest}


def derive_v3_run_identity(*args: Any, **kwargs: Any) -> str:
    """SHA256 of the canonical scientific run-identity payload."""
    _reject_caller_kwargs(args, kwargs)
    return str(canonical_v3_plan()["sha256"])


def v3_protected_artifacts_present(*args: Any, **kwargs: Any) -> bool:
    _reject_caller_kwargs(args, kwargs)
    repo_root = _repo_root()
    for rel in PROTECTED_V3_AUTHORITY_PATHS:
        if (repo_root / rel).exists() or _commit_blob(repo_root, "HEAD", rel) is not None:
            return True
    return False


def v3_arm_authorized(*args: Any, **kwargs: Any) -> bool:
    """True only if a later unit committed a verified ARM. This unit never does."""
    _reject_caller_kwargs(args, kwargs)
    repo_root = _repo_root()
    if _commit_blob(repo_root, "HEAD", CANONICAL_V3_ARM_PATH) is not None:
        _refuse("V3 ARM artifact is present but this unit does not authenticate ARM")
    if (repo_root / CANONICAL_V3_ARM_PATH).exists():
        _refuse("uncommitted V3 ARM artifact cannot authorize execution")
    return False


def required_v3_arm_binding_fields(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Fields a later one-shot ARM must bind. Does not create the ARM."""
    _reject_caller_kwargs(args, kwargs)
    freeze = load_v3_implementation_freeze()
    plan = canonical_v3_plan()
    freeze_bytes = _worktree_bytes(_repo_root(), CANONICAL_FREEZE_JSON_PATH)
    return {
        "schema": "harness_synthetic_edge_calibration_v3_production_arm",
        "status": "ARMED_FOR_ONE_CANONICAL_V3_PRODUCTION_EXECUTION",
        "authorized_run_count": 1,
        "authorization_consumed": False,
        "freeze_artifact_path": CANONICAL_FREEZE_JSON_PATH,
        "freeze_artifact_sha256": _sha256_bytes(freeze_bytes),
        "freeze_artifact_size": len(freeze_bytes),
        "reviewed_implementation_head": ACCEPTED_IMPLEMENTATION_HEAD,
        "reviewed_implementation_tree": ACCEPTED_IMPLEMENTATION_TREE,
        "prereg_freeze_head": PREREG_FREEZE_HEAD,
        "confirmatory_sha256": FROZEN_CONFIRMATORY_SHA256,
        "rng_sha256": FROZEN_RNG_SHA256,
        "v1_lib_sha256": FROZEN_V1_LIB_SHA256,
        "selector_source_file_sha256": FROZEN_SELECTOR_AUTHORITY["source_file_sha256"],
        "canonical_v3_plan_sha256": plan["sha256"],
        "canonical_world_count": FROZEN_PLANNED_WORLDS,
        "run_identity": plan["sha256"],
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
        "default_v4": False,
        "implementation_review_verdict": freeze["implementation_review_verdict"],
    }


def v3_pre_arm_state(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _reject_caller_kwargs(args, kwargs)
    assert_v3_scientific_authority_intact()
    armed = v3_arm_authorized()
    protected = v3_protected_artifacts_present()
    if protected:
        _refuse("canonical V3 result/evidence/reservation/ARM artifact already present")
    return {
        "v3_implementation_frozen": True,
        "v3_pre_arm_binding_complete": True,
        "v3_run_authorized": False,
        "v3_armed": armed,
        "reservation_created": False,
        "world_records_created": False,
        "result_minted": False,
        "default_v4": False,
        "b2_06_execution_authorized": False,
        "run_identity": derive_v3_run_identity(),
        "canonical_world_count": FROZEN_PLANNED_WORLDS,
    }


def assert_v3_executed_bytes_bound(*args: Any, **kwargs: Any) -> None:
    """Require a clean executed checkout before any future canonical run."""
    _reject_caller_kwargs(args, kwargs)
    repo_root = _repo_root()
    assert_v3_scientific_authority_intact()
    head = _head_sha(repo_root)
    try:
        freeze = verify_git_freeze(repo_root, head)
    except CodeIdentityError as exc:
        raise V3ExecutionNotAuthorized(
            f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: executed checkout is not a clean verified freeze ({exc})"
        ) from exc
    if freeze.code_sha != head or freeze.tree_oid != _tree_sha(repo_root):
        _refuse("verified freeze identity drifted from HEAD")


def evaluate_v3_canonical_world(*args: Any, **kwargs: Any) -> None:
    _refuse("canonical V3 world evaluation is not authorized before ARM")


def run_canonical_v3_grid(*args: Any, **kwargs: Any) -> None:
    if args or kwargs:
        _refuse("caller arguments cannot authorize the canonical V3 grid")
    if v3_arm_authorized() is not True:
        raise V3NotArmed("SYNTHETIC_EXECUTION_NOT_AUTHORIZED: v3_arm_authorized=false")
    _refuse("canonical V3 grid execution is not authorized by this freeze unit")


def reserve_v3_canonical_run(*args: Any, **kwargs: Any) -> None:
    _reject_caller_kwargs(args, kwargs)
    _refuse("V3 reservation cannot be created before ARM")


def mint_v3_world_records(*args: Any, **kwargs: Any) -> None:
    _reject_caller_kwargs(args, kwargs)
    _refuse("V3 WORLD_RECORDS cannot be minted before ARM/reservation")


def mint_v3_result(*args: Any, **kwargs: Any) -> None:
    _reject_caller_kwargs(args, kwargs)
    _refuse("V3 RESULT cannot be minted before ARM/reservation")


def assert_index_not_canonical(world_index: int) -> None:
    """Disposable-test helper: canonical acceptance indices are not consumed here."""
    if is_fresh_v3_world_index(int(world_index)):
        _refuse("disposable tests cannot consume canonical world indices")
    if 0 <= int(world_index) <= 399:
        _refuse("disposable tests cannot consume V1/V2 canonical world indices")
