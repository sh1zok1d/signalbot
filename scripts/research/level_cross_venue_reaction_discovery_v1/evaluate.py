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
from .analyze import load_frozen, run
from .cohort import assemble
from .series import load_reaction_series

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / "docs" / "research" / "LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1_RESULT.md"
PACKAGE = Path(__file__).resolve().parent
TEST = ROOT / "tests" / "research" / "test_level_cross_venue_reaction_discovery_v1.py"


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
        "tier": K.TIER,
        "novelty_ok": True,
        "history_ok": bool(frozen.get("history_ok")),
        "dependencies": {
            "touch": K.DEPENDENCY_TOUCH_SHA,
            "memory": K.DEPENDENCY_MEMORY_SHA,
            "method": K.DEPENDENCY_METHOD_SHA,
            "approach": K.DEPENDENCY_APPROACH_SHA,
            "structure": K.DEPENDENCY_STRUCTURE_SHA,
            "confirm": K.DEPENDENCY_CONFIRM_SHA,
            "position": K.DEPENDENCY_POSITION_SHA,
            "joint": K.DEPENDENCY_JOINT_SHA,
            "liquidity": K.DEPENDENCY_LIQUIDITY_SHA,
            "reaction": K.DEPENDENCY_REACTION_SHA,
            "path": K.DEPENDENCY_PATH_SHA,
        },
    }


def main() -> None:
    refuse_if_recorded()
    design_sha = assert_clean_and_committed()
    frozen = load_frozen()
    if not frozen.get("pre_outcome_gate_pass"):
        payload = _base(design_sha, frozen, outcomes_read=False)
        payload.update({
            "routing": "CROSS_VENUE_HISTORY_INSUFFICIENT" if not frozen.get("history_ok") else "NO_INCREMENTAL_CROSS_VENUE_REACTION_STRUCTURE",
            "candidate_class": "NONE",
            "baseline": {"coef": None, "ci95": None, "n": 0},
            "features": [],
            "note": "The outcome-blind gate did not pass. Late labels were not read.",
        })
        if frozen.get("venue_artifact"):
            payload["routing"] = "CROSS_VENUE_HISTORY_INSUFFICIENT"
            payload["note"] = "The Bybit kline did not match the public trade tape. Late labels were not read."
        text = report.render(payload)
        _write(RESULT_JSON, json.dumps(_py(payload), indent=2, sort_keys=True) + "\n")
        _write(RESULT_MD, text)
        print(payload["routing"])
        return
    bars = load_discovery_bars()
    venues = load_reaction_series()
    built = assemble(bars, venues)
    fitted = run(bars, built, frozen)
    payload = _base(design_sha, frozen, outcomes_read=True)
    payload.update(fitted)
    payload["note"] = (
        "Discovery only. A historical association is not a current probability. "
        "No venue is described as leading or causally confirming the barrier."
    )
    text = report.render(payload)
    _write(RESULT_JSON, json.dumps(_py(payload), indent=2, sort_keys=True) + "\n")
    _write(RESULT_MD, text)
    print(payload["routing"])


if __name__ == "__main__":
    main()
