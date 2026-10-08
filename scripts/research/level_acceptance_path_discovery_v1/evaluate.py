"""One official discovery run. Refuses to overwrite a recorded result."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from . import preflight, report
from .cohort import assemble, population

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / "docs" / "research" / "LEVEL_ACCEPTANCE_PATH_DISCOVERY_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "LEVEL_ACCEPTANCE_PATH_DISCOVERY_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "LEVEL_ACCEPTANCE_PATH_DISCOVERY_V1_RESULT.md"
PACKAGE = Path(__file__).resolve().parent
TEST = ROOT / "tests" / "research" / "test_level_acceptance_path_discovery_v1.py"


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


def refuse_if_recorded(json_path: Path = RESULT_JSON, md_path: Path = RESULT_MD) -> None:
    if json_path.exists() or md_path.exists():
        raise SystemExit("REFUSING_RERUN: a discovery result is already recorded")


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


def _base(design_sha: str, frozen: dict, *, outcomes_read: bool) -> dict:
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "family": K.FAMILY,
        "tracks": list(K.TRACKS),
        "claim_ceiling": K.CLAIM_CEILING,
        "product_integration_candidate": False,
        "exposure_status": K.EXPOSURE_STATUS,
        "design_sha": design_sha,
        "source_main": K.SOURCE_MAIN_HEAD,
        "outcomes_read": outcomes_read,
        "dependencies": {
            "touch": K.DEPENDENCY_TOUCH_SHA,
            "memory": K.DEPENDENCY_MEMORY_SHA,
            "method": K.DEPENDENCY_METHOD_SHA,
            "approach": K.DEPENDENCY_APPROACH_SHA,
            "structure": K.DEPENDENCY_STRUCTURE_SHA,
            "confirmation": K.DEPENDENCY_CONFIRM_SHA,
            "positioning_flow": K.DEPENDENCY_POSITION_SHA,
            "joint_state": K.DEPENDENCY_JOINT_SHA,
            "liquidity": K.DEPENDENCY_LIQUIDITY_SHA,
            "post_touch_reaction": K.DEPENDENCY_REACTION_SHA,
        },
        "core": frozen["core"],
        "event_window": frozen["event_window"],
        "seed": K.BOOT_SEED,
        "draws": K.BOOT_DRAWS,
        "fdr_q": K.FDR_Q,
        "practical_scale": K.PRACTICAL_SCALE,
        "eligible_contrasts": list(frozen["eligible_contrasts"]),
        "contrasts": frozen["contrasts"],
        "information": frozen["information"],
        "early_census": frozen["early_census"],
        "sequence_counts": frozen["sequence_counts"],
        "state_counts": frozen["state_counts"],
        "pseudo_state_counts": frozen["pseudo_state_counts"],
        "pseudo_sequence_counts": frozen["pseudo_sequence_counts"],
        "successor_candidate": "NONE",
    }


def _limited(design_sha: str, frozen: dict) -> dict:
    payload = _base(design_sha, frozen, outcomes_read=False)
    payload.update({
        "routing": "INFORMATION_LIMITED",
        "blocked_reason": frozen.get("blocked_reason"),
        "search_exposure": K.exposure(0),
        "primary": [],
        "pseudo": [],
        "specificity": [],
        "stability": [],
        "loyo": [],
        "sequence_table": [],
        "state_table": [],
        "decisions": [],
        "path_memory_candidate": [],
        "level_acceptance_path_candidate": [],
        "generic_price_path_memory_candidate": [],
        "note": "Late labels were not read. Neither contrast passed the frozen arm and overlap gate.",
    })
    return payload


def main() -> None:
    refuse_if_recorded()
    design_sha = assert_clean_and_committed()
    frozen = json.loads(preflight.OUT.read_text())
    if frozen.get("outcome_blind") is not True:
        raise SystemExit("preflight is not marked outcome-blind")
    if not frozen.get("proceed_to_outcomes"):
        payload = _py(_limited(design_sha, frozen))
        _write(RESULT_JSON, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        _write(RESULT_MD, report.render(payload))
        print(json.dumps({
            "routing": payload["routing"],
            "outcomes_read": False,
            "design_sha": design_sha,
        }, sort_keys=True))
        return
    from . import analyze
    bars = load_discovery_bars()
    built = population(bars)
    current = preflight.summarize_clean(bars, built)
    current_py = preflight._py(current)
    for key in preflight.PARITY_KEYS:
        if current_py[key] != frozen[key]:
            raise RuntimeError(f"preflight parity failed for {key}")
    assembled = assemble(bars, built)
    real, pairs = analyze.label_assembled(bars, assembled)
    estimated = analyze.estimate(
        real, pairs, current["contrasts"], list(frozen["eligible_contrasts"]), draws=K.BOOT_DRAWS,
    )
    payload = _base(design_sha, frozen, outcomes_read=True)
    payload["search_exposure"] = K.exposure(len(frozen["eligible_contrasts"]))
    payload.update(estimated)
    payload = _py(payload)
    _write(RESULT_JSON, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _write(RESULT_MD, report.render(payload))
    print(json.dumps({
        "routing": payload["routing"],
        "successor_candidate": payload["successor_candidate"],
        "design_sha": design_sha,
        "outcomes_read": True,
        "n_primary": len(payload["primary"]),
        "path_memory": len(payload["path_memory_candidate"]),
        "level_specific": len(payload["level_acceptance_path_candidate"]),
        "generic": len(payload["generic_price_path_memory_candidate"]),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
