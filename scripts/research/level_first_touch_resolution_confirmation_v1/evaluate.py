"""One official confirmation run. Refuses to overwrite a recorded result."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np

from . import analyze, cohort, constants as K, data, inference, preflight, report

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / "docs" / "research" / "LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1_RESULT.md"
PACKAGE = Path(__file__).resolve().parent


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def assert_clean_and_committed() -> str:
    paths = [DESIGN, preflight.OUT, *sorted(PACKAGE.glob("*.py"))]
    dirty = _git("status", "--porcelain", "--", *[str(p.relative_to(ROOT)) for p in paths])
    if dirty:
        raise RuntimeError("design or evaluator is dirty; refusing to read outcomes")
    sha = _git("log", "-1", "--format=%H", "--", str(DESIGN.relative_to(ROOT)))
    if not sha:
        raise RuntimeError("design note is not committed")
    return sha


def _write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def _py(value):
    if isinstance(value, dict):
        return {str(k): _py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_py(v) for v in value]
    if isinstance(value, (np.floating, float)):
        return float(value)
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def main() -> None:
    if RESULT_JSON.exists() or RESULT_MD.exists():
        raise SystemExit("REFUSING_RERUN: a confirmation result is already recorded")
    design_sha = assert_clean_and_committed()
    frozen = json.loads(preflight.OUT.read_text())
    if not frozen.get("proceed_to_outcomes"):
        raise SystemExit(f"CONFIRMATION_BLOCKED_BEFORE_OUTCOME: {frozen.get('blocked_reason')}")
    bars, identity = data.load_confirmation_bars()
    if identity["canonical_sha256"] != frozen["dataset"]["canonical_sha256"]:
        raise RuntimeError("canonical file changed after the preflight")
    counted = cohort.census(cohort.population(bars))
    pairs = counted.pop("pairs")
    current = {key: counted[key] for key in preflight.PARITY_KEYS}
    frozen_view = {key: frozen[key] for key in preflight.PARITY_KEYS}
    if current != frozen_view:
        raise RuntimeError("cohort census drifted from the frozen preflight")
    recomputed = inference.tercile_edges([p["real_sigma"] for p in pairs])
    recomputed_hex = [float(recomputed[0]).hex(), float(recomputed[1]).hex()]
    if recomputed_hex != list(frozen["sigma_tercile_edges_hex"]):
        raise RuntimeError("tercile edges drifted from the frozen preflight")
    edges = (float.fromhex(frozen["sigma_tercile_edges_hex"][0]), float.fromhex(frozen["sigma_tercile_edges_hex"][1]))
    columns = list(frozen["adjusted_columns"])
    real_labels, pseudo_labels = analyze.label_matched(bars.high, bars.low, pairs)
    estimated = analyze.estimate(
        pairs,
        [row["outcome"] for row in real_labels],
        [row["outcome"] for row in pseudo_labels],
        edges=edges,
        columns=columns,
        draws=K.BOOT_DRAWS,
        seed=K.BOOT_SEED,
    )
    result = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "design_sha": design_sha,
        "exposure_status": K.EXPOSURE_STATUS,
        "event_window": [K.EVENT_START, K.EVENT_END],
        "dataset": identity,
        "bootstrap": {"draws": K.BOOT_DRAWS, "seed": K.BOOT_SEED, "cluster": "real_touch_product_week"},
        "search_cells": K.N_CELLS,
        "preflight_matched_pairs": frozen["matched_pairs"],
        **estimated,
    }
    result = _py(result)
    text = report.render(result)
    _write(RESULT_JSON, json.dumps(result, indent=2, sort_keys=True) + "\n")
    _write(RESULT_MD, text)
    print(f"recorded {RESULT_JSON.name} design {design_sha}")


if __name__ == "__main__":
    main()
