"""Frozen cell sets of the calibration unit, read-only (grid 621, probes 198, dense 4716)."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DOCS = REPO / "docs/research"
GRID = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_GRID_V1.json"
PROBES = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_GRID_PROBES_V1.json"
DENSE = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_GRID_DENSE_SUPPORT_V1.json"
AMENDMENT_V3 = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_FREEZE_AMENDMENT_V3.json"

CLASS_OF_FAMILY = {"F1": "TWO_SAMPLE", "F2": "PAIRED_UNITS", "F3": "CLUSTERED", "F4": "RARE_EVENT"}
CAL_SIZES = {"TWO_SAMPLE": [30, 60, 120, 250, 500], "PAIRED_UNITS": [40, 60, 100, 160, 260, 400],
             "CLUSTERED": [8, 15, 25, 40], "RARE_EVENT": [30, 50, 75, 100]}
REQUIRED_CLASSES = ["TWO_SAMPLE", "PAIRED_UNITS", "CLUSTERED", "RARE_EVENT"]
STAGE_A, STAGE_B, CAL_N = 4000, 20000, 4000


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def frozen() -> dict:
    grid, probes, dense = (json.loads(p.read_text()) for p in (GRID, PROBES, DENSE))
    am = json.loads(AMENDMENT_V3.read_text())
    return {"GRID": grid, "PROBES": probes, "DENSE": dense, "AMENDMENT_V3": am,
            "DIGESTS": {"GRID": sha(GRID), "PROBES": sha(PROBES), "DENSE": sha(DENSE), "AMENDMENT_V3": sha(AMENDMENT_V3)},
            "SUPPORTED_RANGE": dense["SUPPORTED_RANGE"], "REALISTIC_MAX": grid["CONSTANTS"]["REALISTIC_MAX"]}


def digests_match_amendment() -> bool:
    f = frozen()
    b = f["AMENDMENT_V3"]["BOUND_ARTIFACTS"]
    return (b["GRID"]["SHA256"] == f["DIGESTS"]["GRID"] and b["GRID_PROBES"]["SHA256"] == f["DIGESTS"]["PROBES"]
            and b["GRID_DENSE_SUPPORT"]["SHA256"] == f["DIGESTS"]["DENSE"])


def cal_cells() -> list[dict]:
    """CAL phase cells: MUST cells of the 621 grid (the only cells in the Candidate C pool)."""
    return [c for c in frozen()["GRID"]["CELLS"] if c["LABEL"] == "MUST"]


def eval_cells() -> list[dict]:
    """EVAL phase cells: all 621 grid cells (MUST, STRESS, OUT_OF_DOMAIN), 198 probes, 4716 dense."""
    f = frozen()
    return list(f["GRID"]["CELLS"]) + list(f["PROBES"]["CELLS"]) + list(f["DENSE"]["CELLS"])


@lru_cache(maxsize=1)
def frozen_cell_ids() -> frozenset:
    return frozenset(c["CELL_ID"] for c in eval_cells())


def cell_class(cell: dict) -> str:
    return cell["CLASS"]


def nearest_lower_calibrated(klass: str, n: int) -> int | None:
    sizes = CAL_SIZES[klass]
    if n < sizes[0]:
        return None
    return max(s for s in sizes if s <= n)


def in_supported_range(klass: str, n: int) -> bool:
    lo, hi = frozen()["SUPPORTED_RANGE"][klass]
    return lo <= n <= hi


def required_for_class(klass: str) -> list[dict]:
    """Required EVAL cells of a class (Protocol V3 C6): calibrated MUST cells in range, probes, dense."""
    f = frozen()
    out = [c for c in f["GRID"]["CELLS"] if c["CLASS"] == klass and c["LABEL"] == "MUST" and in_supported_range(klass, c["N"])]
    out += [c for c in f["PROBES"]["CELLS"] if c["CLASS"] == klass and in_supported_range(klass, c["N"])]
    out += [c for c in f["DENSE"]["CELLS"] if c["CLASS"] == klass]
    return out


def cal_seed_range(cell: dict) -> tuple[int, int]:
    return tuple(cell["SEED_RANGE"]["CAL"])


def eval_seeds(cell: dict, stage: str) -> list[int]:
    lo, hi = cell["SEED_RANGE"]["EVAL_STAGE_B"]
    if stage == "A":
        return list(range(lo, lo + STAGE_A))
    return list(range(lo + STAGE_A, hi + 1))          # Stage B continuation seeds; Stage A is the prefix
