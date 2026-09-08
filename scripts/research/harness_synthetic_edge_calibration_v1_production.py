"""Production durability, aggregation, and result persistence for the frozen harness.

This layer sits above frozen scientific primitives. It does not change RNG, DGP,
gates, Wilson, taxonomy, or mechanical-conclusion semantics. It does not weaken
FixtureExecutionConfig.

Production Monte Carlo remains unarmed. Canonical execution, when later armed by a
separate unit, must cross a fresh Python interpreter boundary and re-verify exact
HEAD/tree plus execution-authority bytes inside that process.

Run identity is a pure function of tracked authority at the exact execution
commit. Local untracked reservation files cannot mint a distinct run/result.
This module does not claim global process exclusion.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    FEATURE_IDS,
    PRODUCTION_BLOCK_ROWS,
    PRODUCTION_BOOTSTRAP_REPLICATES,
    PRODUCTION_PLACEBO_REPLICATES,
    PRODUCTION_PLANNED_TOTAL_WORLDS,
    PRODUCTION_PRIMARY_N,
    PRODUCTION_SMALL_N,
    PRODUCTION_VISIBILITY_REPLICATES,
    PRODUCTION_WORLDS_PER_CELL,
    ROOT_SEED,
    UNIT_ID,
    SyntheticExecutionNotAuthorized,
    ae_metrics,
    candidate_features,
    compose_gates,
    era_mean_improvements,
    expanding_era_predictions,
    materiality_fraction_of_attainable,
    mechanical_conclusion,
    namespace_seed,
    pcg64_generator,
    placebo_q95,
    power_verdict,
    prediction_bootstrap,
    scenario_by_id,
    scored_mask,
    select_blind,
    simulate_dgp,
    specificity_verdict,
    support_diagnostics,
    taxonomy_flags,
    taxonomy_of,
    visibility_from_residuals,
    wilson_interval,
    world_identity,
    world_seed,
)
from scripts.research.lib.research_harness import CodeIdentityError, verify_git_freeze

DURABILITY_ID = "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DURABILITY_V1"
LIB_REL = "scripts/research/harness_synthetic_edge_calibration_v1_lib.py"
RUNNER_REL = "scripts/research/harness_synthetic_edge_calibration_v1.py"
AUTH_REL = "scripts/research/harness_synthetic_edge_calibration_v1_auth.py"
PRODUCTION_REL = "scripts/research/harness_synthetic_edge_calibration_v1_production.py"
EXECUTION_AUTHORITY_PATHS = (LIB_REL, RUNNER_REL, AUTH_REL, PRODUCTION_REL)
FROZEN_REVIEWED_LIB_SHA256 = (
    "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
)
PREREG_JSON_REL = "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json"
PREREG_MD_REL = "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md"
CANONICAL_AUTHORIZATION_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json"
)
CANONICAL_RESERVATION_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_RESERVATION.json"
)
CANONICAL_CLAIM_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_EXECUTION_CLAIM.json"
)
CANONICAL_RESULT_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_RESULT.json"
)
CANONICAL_PARTIAL_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_PARTIAL.json"
)
CANONICAL_DURABILITY_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DURABILITY.json"
)
CANONICAL_ARM_PATH = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json"
)
FROZEN_GRID_LITERALS = {
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
}
ORACLE_NULL_FPR_MAX = 0.05
BLIND_NULL_FPR_MAX = 0.10
TRAP_STRICT_EX_MAX = 0.20
ORACLE_EASY_MIN = 0.90
ORACLE_MODERATE_MIN = 0.70
BLIND_EASY_USEFUL_MIN = 0.80
BLIND_MODERATE_USEFUL_MIN = 0.50
WORKER_FLAG = "--fresh-process-worker"


class ProductionNotArmed(SyntheticExecutionNotAuthorized):
    """Production Monte Carlo is not armed by this durability unit."""


class ProductionIntegrityError(SyntheticExecutionNotAuthorized):
    """World-set or result identity integrity failed closed."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _refuse(detail: str) -> None:
    raise SyntheticExecutionNotAuthorized(
        f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {detail}"
    )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    """Deterministic JSON: sorted keys, indent 2, trailing newline, no NaN."""
    return (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(val) for key, val in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return str(value)


def frozen_production_grid() -> dict[str, Any]:
    """Derive the production grid from frozen literals and independently check constants."""
    from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
        frozen_production_authority,
        load_frozen_prereg,
    )

    prereg = load_frozen_prereg()
    live = frozen_production_authority()
    derived = {
        "planned_worlds": int(live["planned_total_worlds"]),
        "worlds_per_cell": int(live["worlds_per_primary_scenario"]),
        "scenario_ids": [item["id"] for item in prereg["scenarios"]],
        "root_seed": int(live["root_seed"]),
        "primary_n_rows": int(live["primary_N"]),
        "small_sensitivity_n": list(live["small_sensitivity_N"]),
        "bootstrap_replicates": int(live["bootstrap_replicates"]),
        "placebo_replicates": int(live["placebo_replicates"]),
        "visibility_replicates": int(live["visibility_replicates"]),
        "block_rows": int(live["block_rows"]),
    }
    if derived != FROZEN_GRID_LITERALS:
        _refuse("derived production grid is not the frozen literal authority")
    if (
        derived["planned_worlds"] != PRODUCTION_PLANNED_TOTAL_WORLDS
        or derived["worlds_per_cell"] != PRODUCTION_WORLDS_PER_CELL
        or derived["root_seed"] != ROOT_SEED
        or derived["primary_n_rows"] != PRODUCTION_PRIMARY_N
        or derived["small_sensitivity_n"] != list(PRODUCTION_SMALL_N)
        or derived["bootstrap_replicates"] != PRODUCTION_BOOTSTRAP_REPLICATES
        or derived["placebo_replicates"] != PRODUCTION_PLACEBO_REPLICATES
        or derived["visibility_replicates"] != PRODUCTION_VISIBILITY_REPLICATES
        or derived["block_rows"] != PRODUCTION_BLOCK_ROWS
    ):
        _refuse("production grid drifted from frozen module constants")
    return dict(derived)


def planned_production_jobs() -> tuple[tuple[str, int, int], ...]:
    grid = frozen_production_grid()
    jobs: list[tuple[str, int, int]] = []
    worlds = int(grid["worlds_per_cell"])
    primary_n = int(grid["primary_n_rows"])
    for scenario_id in grid["scenario_ids"]:
        for world_index in range(worlds):
            jobs.append((str(scenario_id), primary_n, world_index))
    for extra_n in [int(n) for n in grid["small_sensitivity_n"]]:
        for world_index in range(worlds):
            jobs.append(("SMALL", extra_n, world_index))
    if len(jobs) != PRODUCTION_PLANNED_TOTAL_WORLDS:
        _refuse("production world plan is not 3200 identities")
    if jobs[0] != ("NULL", 5000, 0) or jobs[-1] != ("SMALL", 10000, 399):
        _refuse("production world plan identity order drifted")
    return tuple(jobs)


def _git(repo_root: Path, *args: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        _refuse(f"git {' '.join(args)} failed")
    return proc.stdout


def _head_sha(repo_root: Path) -> str:
    return _git(repo_root, "rev-parse", "HEAD").decode("ascii").strip().lower()


def _tree_sha(repo_root: Path) -> str:
    return _git(repo_root, "rev-parse", "HEAD^{tree}").decode("ascii").strip().lower()


def _head_blob(repo_root: Path, git_path: str) -> bytes | None:
    if git_path.startswith("/") or ".." in Path(git_path).parts:
        _refuse("invalid git path")
    exists = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-e", f"HEAD:{git_path}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if exists.returncode != 0:
        return None
    return _git(repo_root, "cat-file", "blob", f"HEAD:{git_path}")


def production_monte_carlo_arm_authorized(repo_root: Path | None = None) -> bool:
    """Arming is a separate later unit. This durability PR keeps the flag false.

    A tracked ARM artifact may not authorize a descendant commit. The armed
    HEAD/tree inside the artifact must match the exact executing commit.
    """
    root = repo_root or _repo_root()
    blob = _head_blob(root, CANONICAL_ARM_PATH)
    if blob is None:
        return False
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    if payload.get("production_monte_carlo_arm_authorized") is not True:
        return False
    armed_head = str(payload.get("armed_head_sha") or "").strip().lower()
    armed_tree = str(payload.get("armed_tree_sha") or "").strip().lower()
    return armed_head == _head_sha(root) and armed_tree == _tree_sha(root)


def _executing_file(rel: str) -> Path:
    names = {
        LIB_REL: "harness_synthetic_edge_calibration_v1_lib.py",
        RUNNER_REL: "harness_synthetic_edge_calibration_v1.py",
        AUTH_REL: "harness_synthetic_edge_calibration_v1_auth.py",
        PRODUCTION_REL: "harness_synthetic_edge_calibration_v1_production.py",
    }
    return Path(__file__).resolve().with_name(names[rel])


def verify_executed_production_authority(repo_root: Path | None = None) -> dict[str, str]:
    """Re-verify exact HEAD/tree and execution bytes. Call inside the fresh process."""
    root = repo_root or _repo_root()
    head = _head_sha(root)
    try:
        freeze = verify_git_freeze(root, head)
    except CodeIdentityError as exc:
        raise SyntheticExecutionNotAuthorized(
            f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: executed checkout is not a clean verified freeze ({exc})"
        ) from exc
    tree = _tree_sha(root)
    if freeze.code_sha != head or freeze.tree_oid != tree:
        _refuse("verified freeze identity drifted from HEAD")
    bound: dict[str, str] = {"head_sha": head, "tree_sha": tree}
    for rel in EXECUTION_AUTHORITY_PATHS:
        head_bytes = _head_blob(root, rel)
        if head_bytes is None:
            _refuse(f"execution authority missing from HEAD: {rel}")
        worktree = root / rel
        if worktree.is_symlink() or not worktree.is_file():
            _refuse(f"execution authority worktree is not a regular file: {rel}")
        worktree_bytes = worktree.read_bytes()
        executing_bytes = _executing_file(rel).read_bytes()
        if worktree_bytes != head_bytes:
            _refuse(f"worktree bytes differ from HEAD for {rel}")
        if executing_bytes != head_bytes:
            _refuse(f"executed bytes differ from HEAD for {rel}")
        digest = _sha256_bytes(head_bytes)
        if rel == LIB_REL and digest != FROZEN_REVIEWED_LIB_SHA256:
            _refuse("HEAD scientific lib is not the frozen reviewed implementation")
        bound[rel] = digest
    for rel, expected_key in (
        (PREREG_JSON_REL, "prereg_json_sha256"),
        (PREREG_MD_REL, "prereg_md_sha256"),
    ):
        blob = _head_blob(root, rel)
        if blob is None:
            _refuse(f"frozen prereg missing from HEAD: {rel}")
        if (root / rel).read_bytes() != blob:
            _refuse(f"worktree prereg bytes differ from HEAD for {rel}")
        bound[expected_key] = _sha256_bytes(blob)
    auth_blob = _head_blob(root, CANONICAL_AUTHORIZATION_PATH)
    if auth_blob is not None:
        bound["authorization_sha256"] = _sha256_bytes(auth_blob)
    return bound


def canonical_run_identity(repo_root: Path | None = None) -> str:
    """Durable run identity from tracked execution-commit authority only."""
    root = repo_root or _repo_root()
    bound = verify_executed_production_authority(root)
    grid = frozen_production_grid()
    payload = {
        "durability_id": DURABILITY_ID,
        "unit_id": UNIT_ID,
        "head_sha": bound["head_sha"],
        "tree_sha": bound["tree_sha"],
        "lib_sha256": bound[LIB_REL],
        "runner_sha256": bound[RUNNER_REL],
        "auth_sha256": bound[AUTH_REL],
        "production_sha256": bound[PRODUCTION_REL],
        "prereg_json_sha256": bound["prereg_json_sha256"],
        "prereg_md_sha256": bound["prereg_md_sha256"],
        "grid": grid,
        "authorization_sha256": bound.get("authorization_sha256"),
        "result_path": CANONICAL_RESULT_PATH,
        "reservation_path": CANONICAL_RESERVATION_PATH,
        "claim_path": CANONICAL_CLAIM_PATH,
    }
    return _sha256_bytes(canonical_json_bytes(payload))


def _optional_head_sha256(repo_root: Path, git_path: str) -> str | None:
    blob = _head_blob(repo_root, git_path)
    if blob is None:
        return None
    return _sha256_bytes(blob)


def durable_reservation_document(repo_root: Path | None = None) -> dict[str, Any]:
    """Reservation identity is a function of tracked commit authority only."""
    root = repo_root or _repo_root()
    bound = verify_executed_production_authority(root)
    return {
        "schema_version": "1.0",
        "durability_id": DURABILITY_ID,
        "unit_id": UNIT_ID,
        "canonical_path": CANONICAL_RESERVATION_PATH,
        "run_identity": canonical_run_identity(root),
        "execution_head": bound["head_sha"],
        "execution_tree": bound["tree_sha"],
        "authority_sha256": {
            "lib": bound[LIB_REL],
            "runner": bound[RUNNER_REL],
            "auth": bound[AUTH_REL],
            "production": bound[PRODUCTION_REL],
        },
        "prereg_json_sha256": bound["prereg_json_sha256"],
        "prereg_md_sha256": bound["prereg_md_sha256"],
        "authorization_sha256": bound.get("authorization_sha256"),
        "lifecycle": "TRACKED_IDENTITY_UNARMED",
        "automatic_retry_authorized": False,
        "global_process_exclusion_claimed": False,
        "production_monte_carlo_arm_authorized": False,
    }


def durable_claim_document(repo_root: Path | None = None) -> dict[str, Any]:
    """Claim identity is the same tracked run identity as the reservation."""
    reservation = durable_reservation_document(repo_root)
    return {
        "schema_version": "1.0",
        "durability_id": DURABILITY_ID,
        "unit_id": UNIT_ID,
        "canonical_path": CANONICAL_CLAIM_PATH,
        "run_identity": reservation["run_identity"],
        "execution_head": reservation["execution_head"],
        "execution_tree": reservation["execution_tree"],
        "reservation_sha256": _sha256_bytes(canonical_json_bytes(reservation)),
        "lifecycle": "TRACKED_IDENTITY_UNARMED",
        "automatic_retry_authorized": False,
        "global_process_exclusion_claimed": False,
        "production_monte_carlo_arm_authorized": False,
        "production_calibration_executed": False,
        "final_result_minted": False,
    }


def evaluate_production_candidate(
    world: Mapping[str, Any],
    feature_id: str,
    *,
    scenario_id: str,
    n_rows: int,
    world_index: int,
) -> dict[str, Any]:
    """Orchestrate frozen primitives for one candidate. Does not use FixtureExecutionConfig."""
    n = int(n_rows)
    features = candidate_features(world)
    feature = features[feature_id]
    y = world["Y"]
    x1 = world["X1"]
    x2 = world["X2"]
    s = world["S"]
    reasons: list[str] = []
    preds = expanding_era_predictions(y, x1, x2, feature, n)
    mask = scored_mask(n)
    metrics = ae_metrics(y, preds["BASE_PRED"], preds["CAND_PRED"], mask)
    ae_imp_full = np.full(n, np.nan, dtype=np.float64)
    ae_imp_full[mask] = np.abs(y[mask] - preds["BASE_PRED"][mask]) - np.abs(
        y[mask] - preds["CAND_PRED"][mask]
    )
    diag = support_diagnostics(s, ae_imp_full, mask, n)
    era_imp = era_mean_improvements(y, preds["BASE_PRED"], preds["CAND_PRED"], n)
    cand_pos = int(np.sum(feature[mask] == 1.0))
    identity = str(world.get("world_identity", world_identity(scenario_id, n, world_index)))
    wseed = int(world_seed(identity))
    vis = visibility_from_residuals(
        y - preds["BASE_PRED"],
        s,
        n,
        replicates=PRODUCTION_VISIBILITY_REPLICATES,
        block_rows=PRODUCTION_BLOCK_ROWS,
        rng=pcg64_generator(namespace_seed(wseed, "VISIBILITY")),
    )
    boot = prediction_bootstrap(
        ae_imp_full,
        n,
        replicates=PRODUCTION_BOOTSTRAP_REPLICATES,
        block_rows=PRODUCTION_BLOCK_ROWS,
        rng=pcg64_generator(namespace_seed(wseed, "BOOTSTRAP", feature_id)),
    )
    if boot["world_invalid"]:
        reasons.append("bootstrap_invalid")
    plac = placebo_q95(
        world=world,
        feature=feature,
        n_rows=n,
        replicates=PRODUCTION_PLACEBO_REPLICATES,
        rng=pcg64_generator(namespace_seed(wseed, "PLACEBO", feature_id)),
    )
    if plac["world_invalid"]:
        reasons.append("placebo_invalid")
    placebo_sep = (
        (not plac["placebo_invalid"])
        and np.isfinite(plac["placebo_q95"])
        and metrics["MEAN_AE_IMPROVEMENT"] > plac["placebo_q95"]
    )
    scenario = scenario_by_id(scenario_id)
    materiality_fraction = materiality_fraction_of_attainable(
        metrics["RELATIVE_MAE_IMPROVEMENT"],
        float(scenario.get("asymptotic_max_relative_mae_improvement_approx", 0.0)),
    )
    gates = compose_gates(
        mean_ae_improvement=metrics["MEAN_AE_IMPROVEMENT"],
        relative_mae_improvement=metrics["RELATIVE_MAE_IMPROVEMENT"],
        bootstrap_positive=bool(boot["bootstrap_positive"]),
        placebo_separation=bool(placebo_sep),
        era_improvements=era_imp,
        candidate_positive_count=cand_pos,
    )
    return {
        "feature_id": feature_id,
        "valid": not reasons,
        "invalid_reasons": tuple(reasons),
        "MEAN_AE_IMPROVEMENT": metrics["MEAN_AE_IMPROVEMENT"],
        "RELATIVE_MAE_IMPROVEMENT": metrics["RELATIVE_MAE_IMPROVEMENT"],
        "gates": gates,
        "diagnostics": diag,
        "visibility": vis,
        "bootstrap": boot,
        "placebo": plac,
        "era_improvements": era_imp,
        "candidate_positive_count": cand_pos,
        "MATERIALITY_FRACTION_OF_ATTAINABLE": materiality_fraction,
        "stays_in_denominator": True,
    }


def evaluate_production_world(
    scenario_id: str,
    n_rows: int,
    world_index: int,
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    """Evaluate one frozen-grid world. Refuses unless a later unit has armed Monte Carlo."""
    if args or kwargs:
        _refuse("caller arguments cannot authorize production evaluation")
    root = _repo_root()
    verify_executed_production_authority(root)
    if (scenario_id, int(n_rows), int(world_index)) not in set(planned_production_jobs()):
        _refuse("world is not a frozen production-grid identity")
    if production_monte_carlo_arm_authorized(root) is not True:
        raise ProductionNotArmed(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: production_monte_carlo_arm_authorized=false"
        )
    world = simulate_dgp(
        scenario_id=scenario_id,
        n_rows=int(n_rows),
        world_index=int(world_index),
    )
    rows = []
    any_invalid = False
    reasons: list[str] = []
    for feature_id in FEATURE_IDS:
        ev = evaluate_production_candidate(
            world,
            feature_id,
            scenario_id=scenario_id,
            n_rows=int(n_rows),
            world_index=int(world_index),
        )
        if not ev["valid"]:
            any_invalid = True
            reasons.extend(ev["invalid_reasons"])
        rows.append(ev)
    oracle = next(row for row in rows if row["feature_id"] == "F03")
    selected_ex = select_blind(rows, gate="STRICT_PASS_EX_MATERIALITY")
    selected_strict = select_blind(rows, gate="STRICT_PASS")
    label = taxonomy_of(None if selected_ex == "NO_CANDIDATE" else selected_ex)
    identity = world_identity(scenario_id, int(n_rows), int(world_index))
    return _jsonable(
        {
            "scenario_id": scenario_id,
            "n_rows": int(n_rows),
            "world_index": int(world_index),
            "world_identity": identity,
            "world_seed": int(world_seed(identity)),
            "valid": not any_invalid,
            "invalid_reasons": tuple(reasons),
            "oracle_F03": oracle,
            "candidates": rows,
            "selected_STRICT_PASS_EX_MATERIALITY": selected_ex,
            "selected_STRICT_PASS": selected_strict,
            "taxonomy": label,
            "taxonomy_flags": taxonomy_flags(label),
            "visibility": oracle["visibility"],
            "materiality": {
                "RELATIVE_MAE_IMPROVEMENT": oracle["RELATIVE_MAE_IMPROVEMENT"],
                "MATERIALITY_FRACTION_OF_ATTAINABLE": oracle[
                    "MATERIALITY_FRACTION_OF_ATTAINABLE"
                ],
                "STRICT_PASS": oracle["gates"]["STRICT_PASS"],
                "STRICT_PASS_EX_MATERIALITY": oracle["gates"]["STRICT_PASS_EX_MATERIALITY"],
            },
            "stays_in_denominator": True,
        }
    )


def _cell_records(
    records: Sequence[Mapping[str, Any]], scenario_id: str, n_rows: int
) -> list[Mapping[str, Any]]:
    return [
        rec
        for rec in records
        if rec.get("scenario_id") == scenario_id and int(rec.get("n_rows", -1)) == n_rows
    ]


def _require_unique_planned_set(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    jobs = planned_production_jobs()
    by_identity: dict[str, Mapping[str, Any]] = {}
    by_job: dict[tuple[str, int, int], Mapping[str, Any]] = {}
    for rec in records:
        identity = str(rec.get("world_identity", ""))
        job = (
            str(rec.get("scenario_id")),
            int(rec.get("n_rows", -1)),
            int(rec.get("world_index", -1)),
        )
        expected_identity = world_identity(*job)
        if identity != expected_identity:
            raise ProductionIntegrityError(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: world identity does not match job"
            )
        digest = _sha256_bytes(canonical_json_bytes(_jsonable(dict(rec))))
        if identity in by_identity:
            prior = _sha256_bytes(canonical_json_bytes(_jsonable(dict(by_identity[identity]))))
            if prior != digest:
                raise ProductionIntegrityError(
                    "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: conflicting duplicate world identity"
                )
            raise ProductionIntegrityError(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: duplicate world identity"
            )
        if job in by_job:
            raise ProductionIntegrityError(
                "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: duplicate world identity"
            )
        by_identity[identity] = rec
        by_job[job] = rec
    missing = [job for job in jobs if job not in by_job]
    return {
        "by_job": by_job,
        "missing": missing,
        "incomplete_execution": bool(missing),
        "planned_world_count": len(jobs),
        "observed_world_count": len(by_job),
    }


def _wilson_arm(records: Sequence[Mapping[str, Any]], predicate) -> dict[str, Any]:
    n = len(records)
    successes = sum(1 for rec in records if predicate(rec))
    if n <= 0:
        interval = {
            "n": 0.0,
            "successes": 0.0,
            "phat": 0.0,
            "center": 0.0,
            "lower": 0.0,
            "upper": 0.0,
        }
    else:
        interval = wilson_interval(successes, n)
    return {
        "successes": successes,
        "n": n,
        "interval": interval,
        "incomplete_cell": n != PRODUCTION_WORLDS_PER_CELL,
    }


def _oracle_model_detected(rec: Mapping[str, Any]) -> bool:
    gates = ((rec.get("oracle_F03") or {}).get("gates")) or {}
    return gates.get("MODEL_DETECTED") is True


def _oracle_strict_ex(rec: Mapping[str, Any]) -> bool:
    gates = ((rec.get("oracle_F03") or {}).get("gates")) or {}
    return gates.get("STRICT_PASS_EX_MATERIALITY") is True


def _oracle_strict(rec: Mapping[str, Any]) -> bool:
    gates = ((rec.get("oracle_F03") or {}).get("gates")) or {}
    return gates.get("STRICT_PASS") is True


def _oracle_visible(rec: Mapping[str, Any]) -> bool:
    vis = rec.get("visibility") or (rec.get("oracle_F03") or {}).get("visibility") or {}
    return vis.get("GROUND_TRUTH_VISIBLE") is True


def aggregate_planned_worlds(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate exactly the planned 3200-world set. Invalid worlds stay in the denominator."""
    frozen_production_grid()
    integrity = _require_unique_planned_set(records)
    records = list(records)
    nulls = _cell_records(records, "NULL", 5000)
    easys = _cell_records(records, "EASY", 5000)
    moderates = _cell_records(records, "MODERATE", 5000)
    traps = _cell_records(records, "NONSTATIONARY_TRAP", 5000)
    small_5000 = _cell_records(records, "SMALL", 5000)
    small_2500 = _cell_records(records, "SMALL", 2500)
    small_10000 = _cell_records(records, "SMALL", 10000)

    oracle_null = _wilson_arm(nulls, _oracle_model_detected)
    blind_null = _wilson_arm(
        nulls, lambda rec: bool((rec.get("taxonomy_flags") or {}).get("ANY_EDGE_DECLARED"))
    )
    trap_ex = _wilson_arm(traps, _oracle_strict_ex)
    easy_oracle = _wilson_arm(easys, _oracle_model_detected)
    moderate_oracle = _wilson_arm(moderates, _oracle_model_detected)
    easy_useful = _wilson_arm(
        easys, lambda rec: bool((rec.get("taxonomy_flags") or {}).get("USEFUL_DISCOVERY"))
    )
    moderate_useful = _wilson_arm(
        moderates, lambda rec: bool((rec.get("taxonomy_flags") or {}).get("USEFUL_DISCOVERY"))
    )
    small_oracle_5000 = _wilson_arm(small_5000, _oracle_model_detected)
    small_oracle_2500 = _wilson_arm(small_2500, _oracle_model_detected)
    small_oracle_10000 = _wilson_arm(small_10000, _oracle_model_detected)
    easy_visibility = _wilson_arm(easys, _oracle_visible)
    easy_strict = _wilson_arm(easys, _oracle_strict)
    easy_strict_ex = _wilson_arm(easys, _oracle_strict_ex)

    incomplete = bool(integrity["incomplete_execution"])

    def _spec(arm: dict[str, Any], maximum: float) -> str:
        return specificity_verdict(arm["interval"], maximum) if arm["n"] else "INDETERMINATE"

    def _pow(arm: dict[str, Any], minimum: float) -> str:
        return power_verdict(arm["interval"], minimum) if arm["n"] else "INDETERMINATE"

    oracle_null_v = _spec(oracle_null, ORACLE_NULL_FPR_MAX)
    blind_null_v = _spec(blind_null, BLIND_NULL_FPR_MAX)
    trap_v = _spec(trap_ex, TRAP_STRICT_EX_MAX)
    easy_oracle_v = _pow(easy_oracle, ORACLE_EASY_MIN)
    moderate_oracle_v = _pow(moderate_oracle, ORACLE_MODERATE_MIN)
    easy_useful_v = _pow(easy_useful, BLIND_EASY_USEFUL_MIN)
    moderate_useful_v = _pow(moderate_useful, BLIND_MODERATE_USEFUL_MIN)
    visibility_upper = float(easy_visibility["interval"]["upper"]) if easy_visibility["n"] else None
    model_upper = float(easy_oracle["interval"]["upper"]) if easy_oracle["n"] else None
    materiality_only = bool(
        easy_strict_ex["successes"] > easy_strict["successes"]
        and easy_strict_ex["n"] == PRODUCTION_WORLDS_PER_CELL
    )

    invalid_by_cell: dict[str, Any] = {}
    total_invalid = 0
    reason_counts: dict[str, int] = {}
    for scenario_id, n_rows in (
        ("NULL", 5000),
        ("EASY", 5000),
        ("MODERATE", 5000),
        ("SMALL", 5000),
        ("TINY_NOISY", 5000),
        ("NONSTATIONARY_TRAP", 5000),
        ("SMALL", 2500),
        ("SMALL", 10000),
    ):
        cell = _cell_records(records, scenario_id, n_rows)
        invalid = [rec for rec in cell if rec.get("valid") is False]
        total_invalid += len(invalid)
        reasons: dict[str, int] = {}
        for rec in invalid:
            for reason in rec.get("invalid_reasons") or ():
                reasons[str(reason)] = reasons.get(str(reason), 0) + 1
                reason_counts[str(reason)] = reason_counts.get(str(reason), 0) + 1
        invalid_by_cell[f"{scenario_id}|{n_rows}"] = {
            "invalid_count": len(invalid),
            "planned": PRODUCTION_WORLDS_PER_CELL,
            "observed": len(cell),
            "reasons": reasons,
        }

    conclusion = mechanical_conclusion(
        incomplete_execution=incomplete,
        oracle_null_specificity=oracle_null_v,
        blind_null_specificity=blind_null_v,
        trap_specificity=trap_v,
        easy_oracle_power=easy_oracle_v,
        moderate_oracle_power=moderate_oracle_v,
        easy_blind_useful=easy_useful_v,
        moderate_blind_useful=moderate_useful_v,
        visibility_wilson_upper=visibility_upper,
        model_detection_wilson_upper=model_upper,
        materiality_only_failure=materiality_only,
    )
    return {
        "planned_world_count": integrity["planned_world_count"],
        "observed_world_count": integrity["observed_world_count"],
        "incomplete_execution": incomplete,
        "missing_jobs": [list(job) for job in integrity["missing"]],
        "arms": {
            "ORACLE_NULL_MODEL_DETECTED": {
                **oracle_null,
                "verdict": oracle_null_v,
                "threshold": ORACLE_NULL_FPR_MAX,
            },
            "BLIND_NULL_ANY_EDGE_DECLARED": {
                **blind_null,
                "verdict": blind_null_v,
                "threshold": BLIND_NULL_FPR_MAX,
            },
            "NONSTATIONARY_TRAP_STRICT_PASS_EX_MATERIALITY": {
                **trap_ex,
                "verdict": trap_v,
                "threshold": TRAP_STRICT_EX_MAX,
            },
            "ORACLE_EASY_MODEL_DETECTED": {
                **easy_oracle,
                "verdict": easy_oracle_v,
                "threshold": ORACLE_EASY_MIN,
            },
            "ORACLE_MODERATE_MODEL_DETECTED": {
                **moderate_oracle,
                "verdict": moderate_oracle_v,
                "threshold": ORACLE_MODERATE_MIN,
            },
            "BLIND_EASY_USEFUL_DISCOVERY": {
                **easy_useful,
                "verdict": easy_useful_v,
                "threshold": BLIND_EASY_USEFUL_MIN,
            },
            "BLIND_MODERATE_USEFUL_DISCOVERY": {
                **moderate_useful,
                "verdict": moderate_useful_v,
                "threshold": BLIND_MODERATE_USEFUL_MIN,
            },
            "SMALL_ORACLE_MODEL_DETECTED_N5000": small_oracle_5000,
            "SMALL_ORACLE_MODEL_DETECTED_N2500": small_oracle_2500,
            "SMALL_ORACLE_MODEL_DETECTED_N10000": small_oracle_10000,
            "VISIBILITY_FLOOR_EASY_ORACLE": easy_visibility,
            "MODEL_FLOOR_EASY_ORACLE": easy_oracle,
            "MATERIALITY_ONLY_DIAGNOSTIC": {
                "strict_ex": easy_strict_ex,
                "strict": easy_strict,
                "materiality_only_failure": materiality_only,
            },
        },
        "invalid_counts_by_cell": invalid_by_cell,
        "invalid_counts_total": {"invalid_count": total_invalid, "reasons": reason_counts},
        "verdicts": {
            "oracle_null_specificity": oracle_null_v,
            "blind_null_specificity": blind_null_v,
            "trap_specificity": trap_v,
            "easy_oracle_power": easy_oracle_v,
            "moderate_oracle_power": moderate_oracle_v,
            "easy_blind_useful": easy_useful_v,
            "moderate_blind_useful": moderate_useful_v,
        },
        "mechanical_conclusion": conclusion,
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
    }


def bind_result_document(
    *,
    aggregates: Mapping[str, Any],
    repo_root: Path | None = None,
    reservation_sha256: str | None = None,
    claim_sha256: str | None = None,
) -> dict[str, Any]:
    root = repo_root or _repo_root()
    bound = verify_executed_production_authority(root)
    run_identity = canonical_run_identity(root)
    core = {
        "schema_version": "1.0",
        "unit_id": UNIT_ID,
        "durability_id": DURABILITY_ID,
        "execution_head": bound["head_sha"],
        "execution_tree": bound["tree_sha"],
        "authority_paths": list(EXECUTION_AUTHORITY_PATHS),
        "authority_sha256": {
            "lib": bound[LIB_REL],
            "runner": bound[RUNNER_REL],
            "auth": bound[AUTH_REL],
            "production": bound[PRODUCTION_REL],
        },
        "prereg_json_sha256": bound["prereg_json_sha256"],
        "prereg_md_sha256": bound["prereg_md_sha256"],
        "frozen_lib_sha256": bound[LIB_REL],
        "authorization_sha256": bound.get("authorization_sha256"),
        "reservation_sha256": reservation_sha256
        if reservation_sha256 is not None
        else _optional_head_sha256(root, CANONICAL_RESERVATION_PATH),
        "claim_sha256": claim_sha256
        if claim_sha256 is not None
        else _optional_head_sha256(root, CANONICAL_CLAIM_PATH),
        "run_identity": run_identity,
        "planned_world_count": aggregates["planned_world_count"],
        "observed_world_count": aggregates["observed_world_count"],
        "aggregates": _jsonable(aggregates),
        "mechanical_conclusion": aggregates["mechanical_conclusion"],
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
        "production_monte_carlo_arm_authorized": False,
        "production_calibration_executed": False,
        "verdicts": aggregates["verdicts"],
        "wilson_intervals": {
            name: arm.get("interval")
            for name, arm in aggregates.get("arms", {}).items()
            if isinstance(arm, Mapping) and "interval" in arm
        },
    }
    raw = canonical_json_bytes(core)
    document = dict(core)
    document["result_sha256"] = _sha256_bytes(raw)
    document["result_size"] = len(raw)
    return document


def verify_bound_result_document(document: Mapping[str, Any], repo_root: Path | None = None) -> None:
    core = {
        key: value
        for key, value in document.items()
        if key not in {"result_sha256", "result_size"}
    }
    raw = canonical_json_bytes(core)
    if document.get("result_sha256") != _sha256_bytes(raw):
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: result digest tamper detected"
        )
    if document.get("result_size") != len(raw):
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: result size tamper detected"
        )
    expected_run = canonical_run_identity(repo_root)
    if document.get("run_identity") != expected_run:
        raise ProductionIntegrityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: run_identity tamper detected"
        )


def mint_final_result(
    records: Sequence[Mapping[str, Any]],
    *args: Any,
    **kwargs: Any,
) -> dict[str, Any]:
    if args or kwargs:
        _refuse("caller arguments cannot authorize a production RESULT")
    root = _repo_root()
    verify_executed_production_authority(root)
    if production_monte_carlo_arm_authorized(root) is not True:
        raise ProductionNotArmed(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: production RESULT cannot be minted while unarmed"
        )
    aggregates = aggregate_planned_worlds(records)
    if (
        aggregates["incomplete_execution"]
        or aggregates["observed_world_count"] != PRODUCTION_PLANNED_TOTAL_WORLDS
    ):
        _refuse("partial world set cannot finalize")
    if aggregates["mechanical_conclusion"] == "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM":
        _refuse("incomplete execution cannot mint a final RESULT")
    reservation = durable_reservation_document(root)
    claim = durable_claim_document(root)
    return bind_result_document(
        aggregates=aggregates,
        repo_root=root,
        reservation_sha256=_sha256_bytes(canonical_json_bytes(reservation)),
        claim_sha256=_sha256_bytes(canonical_json_bytes(claim)),
    )


def persist_partial_worlds(records: Sequence[Mapping[str, Any]], *args: Any, **kwargs: Any) -> dict[str, Any]:
    if args or kwargs:
        _refuse("caller arguments cannot authorize partial persistence")
    return {
        "schema_version": "1.0",
        "status": "PARTIAL_NOT_RESULT",
        "unit_id": UNIT_ID,
        "observed_world_count": len(records),
        "planned_world_count": PRODUCTION_PLANNED_TOTAL_WORLDS,
        "final_result_minted": False,
        "automatic_retry_authorized": False,
        "records": _jsonable(list(records)),
    }


def recover_partial_from_tracked_authority(*args: Any, **kwargs: Any) -> dict[str, Any]:
    if args or kwargs:
        _refuse("caller arguments cannot supply recovery/digest/grid/result authority")
    root = _repo_root()
    blob = _head_blob(root, CANONICAL_PARTIAL_PATH)
    if blob is None:
        _refuse("tracked recovery authority/partial artifact is absent")
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyntheticExecutionNotAuthorized(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: malformed tracked partial artifact"
        ) from exc
    if payload.get("final_result_minted") is True:
        _refuse("partial artifact must not claim a final RESULT")
    return payload


def spawn_canonical_production_process(*args: Any, **kwargs: Any) -> int:
    """Canonical production path: a fresh interpreter, then re-verify, then refuse if unarmed.

    The child executes this checkout's tracked production module by absolute
    path. Inherited PYTHONPATH cannot substitute another tree. Bytecode is not
    written into the worktree.
    """
    if args or kwargs:
        _refuse("caller arguments cannot authorize production execution")
    root = _repo_root()
    env = {
        key: value
        for key, value in os.environ.items()
        if "AUTHORIZ" not in key.upper() and key != "PYTHONPATH"
    }
    env["PYTHONPATH"] = str(root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    worker = root / PRODUCTION_REL
    if worker.is_symlink() or not worker.is_file():
        _refuse("canonical production worker is not a regular file")
    proc = subprocess.run(
        [sys.executable, "-B", str(worker), WORKER_FLAG],
        cwd=str(root),
        env=env,
        check=False,
    )
    return int(proc.returncode)


def fresh_process_worker_main() -> int:
    """Runs only inside a fresh interpreter. Re-verifies then fail-closes while unarmed."""
    root = _repo_root()
    verify_executed_production_authority(root)
    frozen_production_grid()
    planned_production_jobs()
    if production_monte_carlo_arm_authorized(root) is not True:
        print(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: production_monte_carlo_arm_authorized=false",
            file=sys.stderr,
        )
        return 2
    _refuse("armed production Monte Carlo is not part of this durability unit")
    return 2


def production_durability_identity() -> dict[str, Any]:
    return {
        "stage": "production_durability_unarmed",
        "unit_id": UNIT_ID,
        "durability_id": DURABILITY_ID,
        "production_monte_carlo_arm_authorized": False,
        "production_calibration_executed": False,
        "production_result_minted": False,
        "fresh_process_required": True,
        "durable_run_identity": True,
        "global_process_exclusion_claimed": False,
        "real_market_data_access_authorized": False,
        "b2_06_scientific_execution_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
        "real_data_path": False,
        "monte_carlo_armed": False,
        "authorization_consumed": False,
        "synthetic_execution_authorized": False,
        "canonical_paths": {
            "reservation": CANONICAL_RESERVATION_PATH,
            "claim": CANONICAL_CLAIM_PATH,
            "result": CANONICAL_RESULT_PATH,
            "partial": CANONICAL_PARTIAL_PATH,
            "durability": CANONICAL_DURABILITY_PATH,
            "arm": CANONICAL_ARM_PATH,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args == [WORKER_FLAG]:
        try:
            return fresh_process_worker_main()
        except SyntheticExecutionNotAuthorized as exc:
            print(str(exc), file=sys.stderr)
            return 2
    print("SYNTHETIC_EXECUTION_NOT_AUTHORIZED", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
