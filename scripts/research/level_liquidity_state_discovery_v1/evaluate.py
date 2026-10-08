"""One official discovery run. Refuses to overwrite a recorded result."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import analyze, constants as K, preflight, report
from .book import load_btc_book
from .cohort import assemble, population
from .inference import scale_hex

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / "docs" / "research" / "LEVEL_LIQUIDITY_STATE_DISCOVERY_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "LEVEL_LIQUIDITY_STATE_DISCOVERY_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "LEVEL_LIQUIDITY_STATE_DISCOVERY_V1_RESULT.md"
PACKAGE = Path(__file__).resolve().parent
TEST = ROOT / "tests" / "research" / "test_level_liquidity_state_discovery_v1.py"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def assert_clean_and_committed() -> str:
    paths = [DESIGN, preflight.OUT, TEST, *sorted(PACKAGE.glob("*.py"))]
    dirty = _git("status", "--porcelain", "--", *[str(p.relative_to(ROOT)) for p in paths])
    if dirty:
        raise RuntimeError("design or evaluator is dirty; refusing to read outcomes")
    sha = _git("log", "-1", "--format=%H", "--", str(DESIGN.relative_to(ROOT)))
    if not sha:
        raise RuntimeError("design note is not committed")
    return sha


def _py(value):
    if isinstance(value, dict):
        return {str(k): _py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_py(v) for v in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return None if not math.isfinite(number) else number
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def main() -> None:
    if RESULT_JSON.exists() or RESULT_MD.exists():
        raise SystemExit("REFUSING_RERUN: a discovery result is already recorded")
    design_sha = assert_clean_and_committed()
    frozen = json.loads(preflight.OUT.read_text())
    if not frozen.get("proceed_to_outcomes"):
        raise SystemExit(f"BLOCKED_BEFORE_OUTCOME: {frozen.get('blocked_reason')}")
    if frozen.get("outcome_blind") is not True:
        raise SystemExit("preflight is not marked outcome-blind")
    bars = load_discovery_bars()
    book, meta = load_btc_book()
    if meta["object_list_sha256"] != frozen["book_object_list_sha256"]:
        raise RuntimeError("book bytes changed after the preflight")
    if int(meta["last_ms"]) >= K.SURFACE_END_MS:
        raise RuntimeError("book series enters 2025")
    built = population(bars)
    current = preflight.summarize(bars, book, meta, built)
    current_py = preflight._py(current)
    for key in preflight.PARITY_KEYS:
        if current_py[key] != frozen[key]:
            raise RuntimeError(f"preflight parity failed for {key}")
    kept = list(frozen["kept_features"])
    if current_py["kept_features"] != kept:
        raise RuntimeError("retained features drifted")
    recomputed_hex = {
        name: scale_hex(current["scales"][name]) for name in list(kept) + ["disp", "rel_volume"]
    }
    if preflight._py(recomputed_hex) != frozen["scale_hex"]:
        raise RuntimeError("feature scales drifted from the frozen preflight")
    assembled = assemble(bars, book, built)
    real, pairs = analyze.label_assembled(bars, assembled)
    estimated = analyze.estimate(real, pairs, current["scales"], kept, draws=K.BOOT_DRAWS)
    result = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "family": K.FAMILY,
        "tracks": list(K.TRACKS),
        "claim_ceiling": K.CLAIM_CEILING,
        "product_integration_candidate": False,
        "exposure_status": K.EXPOSURE_STATUS,
        "state_term": K.STATE_TERM,
        "design_sha": design_sha,
        "source_main": K.SOURCE_MAIN_HEAD,
        "dependencies": {
            "touch": K.DEPENDENCY_TOUCH_SHA,
            "memory": K.DEPENDENCY_MEMORY_SHA,
            "method": K.DEPENDENCY_METHOD_SHA,
            "approach": K.DEPENDENCY_APPROACH_SHA,
            "structure": K.DEPENDENCY_STRUCTURE_SHA,
            "confirmation": K.DEPENDENCY_CONFIRM_SHA,
            "positioning_flow": K.DEPENDENCY_POSITION_SHA,
            "joint_state": K.DEPENDENCY_JOINT_SHA,
        },
        "core": frozen["core"],
        "book": frozen["book"],
        "event_window": frozen["event_window"],
        "kept_features": kept,
        "dropped_features": frozen["redundancy"]["dropped"],
        "search_exposure": K.exposure(len(kept)),
        "seed": K.BOOT_SEED,
        "draws": K.BOOT_DRAWS,
        "fdr_q": K.FDR_Q,
        "practical_scale": K.PRACTICAL_SCALE,
        "census": {key: frozen[key] for key in preflight.PARITY_KEYS},
        **estimated,
    }
    payload = _py(result)
    _write(RESULT_JSON, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _write(RESULT_MD, report.render(payload))
    print(json.dumps({
        "routing": payload["routing"],
        "successor_candidate": payload["successor_candidate"],
        "design_sha": design_sha,
        "n_primary": len(payload["primary"]),
        "interaction": len(payload["level_liquidity_interaction_candidate"]),
        "generic": len(payload["generic_liquidity_state_candidate"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
