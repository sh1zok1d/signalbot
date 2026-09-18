"""Independent frozen-sequential oracle for HARNESS_PERFORMANCE_V1.

Loads exact reviewed bytes from git commit 3fadc39. Must not import the
live optimized implementation under another name as the scientific oracle.
"""

from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
import types
from pathlib import Path
from typing import Any, Mapping

ORACLE_COMMIT = "3fadc391ee0002e35463b526301d287d4a662828"
ORACLE_LIB_REL = "scripts/research/harness_synthetic_edge_calibration_v1_lib.py"
ORACLE_PRODUCTION_REL = "scripts/research/harness_synthetic_edge_calibration_v1_production.py"
ORACLE_LIB_SHA256 = "12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51"
ORACLE_MODULE_NAME = "harn_oracle_lib_3fadc391ee0002e35463b526301d287d4a662828"
ORACLE_PROD_HELPER_NAME = "harn_oracle_prod_3fadc391ee0002e35463b526301d287d4a662828"


def _git_show(rel: str) -> bytes:
    proc = subprocess.run(
        ["git", "show", f"{ORACLE_COMMIT}:{rel}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"oracle git show failed for {rel}: {proc.stderr!r}")
    return proc.stdout


def load_oracle_lib():
    """Exec frozen lib bytes into a uniquely named module. Never the live module."""
    src = _git_show(ORACLE_LIB_REL)
    digest = hashlib.sha256(src).hexdigest()
    if digest != ORACLE_LIB_SHA256:
        raise RuntimeError(
            f"oracle lib digest {digest} != frozen {ORACLE_LIB_SHA256}"
        )
    existing = sys.modules.get(ORACLE_MODULE_NAME)
    if existing is not None:
        live = sys.modules.get("scripts.research.harness_synthetic_edge_calibration_v1_lib")
        if live is existing:
            raise RuntimeError("oracle lib must not alias the live scientific module")
        return existing
    mod = types.ModuleType(ORACLE_MODULE_NAME)
    live_lib_path = (
        Path(__file__).resolve().parents[2] / ORACLE_LIB_REL
    )
    mod.__file__ = str(live_lib_path)
    sys.modules[ORACLE_MODULE_NAME] = mod
    exec(compile(src, f"<oracle:{ORACLE_COMMIT}:{ORACLE_LIB_REL}>", "exec"), mod.__dict__)
    sys.modules[ORACLE_MODULE_NAME] = mod
    live = sys.modules.get("scripts.research.harness_synthetic_edge_calibration_v1_lib")
    if live is mod:
        raise RuntimeError("oracle lib must not alias the live scientific module")
    return mod


def _extract_functions(src: str, names: tuple[str, ...]) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(src)
    found: dict[str, ast.FunctionDef] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            found[node.name] = node
    missing = [name for name in names if name not in found]
    if missing:
        raise RuntimeError(f"oracle production missing functions: {missing}")
    return found


def load_oracle_world_evaluator():
    """Historical evaluate_production_candidate + _evaluate_planned_world_body."""
    olib = load_oracle_lib()
    live_lib = sys.modules.get("scripts.research.harness_synthetic_edge_calibration_v1_lib")
    if live_lib is olib:
        raise RuntimeError("oracle lib aliased live lib")
    if olib.placebo_q95 is getattr(live_lib, "placebo_q95", None):
        raise RuntimeError("oracle placebo_q95 must not be the live function")
    prod_src = _git_show(ORACLE_PRODUCTION_REL).decode("utf-8")
    fns = _extract_functions(
        prod_src,
        ("_jsonable", "evaluate_production_candidate", "_evaluate_planned_world_body"),
    )
    helper = types.ModuleType(ORACLE_PROD_HELPER_NAME)
    ns = helper.__dict__
    ns.update(
        {
            "__name__": ORACLE_PROD_HELPER_NAME,
            "Any": Any,
            "Mapping": Mapping,
            "np": olib.np,
            "math": __import__("math"),
            "Path": Path,
            "FEATURE_IDS": olib.FEATURE_IDS,
            "PRODUCTION_BLOCK_ROWS": olib.PRODUCTION_BLOCK_ROWS,
            "PRODUCTION_BOOTSTRAP_REPLICATES": olib.PRODUCTION_BOOTSTRAP_REPLICATES,
            "PRODUCTION_PLACEBO_REPLICATES": olib.PRODUCTION_PLACEBO_REPLICATES,
            "PRODUCTION_VISIBILITY_REPLICATES": olib.PRODUCTION_VISIBILITY_REPLICATES,
            "IncompleteWorld": olib.IncompleteWorld,
            "ae_metrics": olib.ae_metrics,
            "candidate_features": olib.candidate_features,
            "compose_gates": olib.compose_gates,
            "era_mean_improvements": olib.era_mean_improvements,
            "expanding_era_predictions": olib.expanding_era_predictions,
            "materiality_fraction_of_attainable": olib.materiality_fraction_of_attainable,
            "namespace_seed": olib.namespace_seed,
            "pcg64_generator": olib.pcg64_generator,
            "placebo_q95": olib.placebo_q95,
            "prediction_bootstrap": olib.prediction_bootstrap,
            "scenario_by_id": olib.scenario_by_id,
            "scored_mask": olib.scored_mask,
            "select_blind": olib.select_blind,
            "simulate_dgp": olib.simulate_dgp,
            "support_diagnostics": olib.support_diagnostics,
            "taxonomy_flags": olib.taxonomy_flags,
            "taxonomy_of": olib.taxonomy_of,
            "visibility_from_residuals": olib.visibility_from_residuals,
            "world_identity": olib.world_identity,
            "world_seed": olib.world_seed,
        }
    )
    for name in ("_jsonable", "evaluate_production_candidate", "_evaluate_planned_world_body"):
        module = ast.Module(body=[fns[name]], type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, f"<oracle:{ORACLE_COMMIT}:{name}>", "exec"), ns)
    existing = sys.modules.get(ORACLE_PROD_HELPER_NAME)
    if existing is not None and existing is not helper:
        return existing
    sys.modules[ORACLE_PROD_HELPER_NAME] = helper
    return helper


def oracle_evaluate_planned_world(scenario_id: str, n_rows: int, world_index: int) -> dict:
    helper = load_oracle_world_evaluator()
    return helper._evaluate_planned_world_body(scenario_id, int(n_rows), int(world_index))


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]
