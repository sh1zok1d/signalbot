"""One official discovery run. Refuses to overwrite a recorded result."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np

from scripts.research.level_cross_venue_reaction_discovery_v1.series import load_reaction_series
from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from . import preflight, report
from .analyze import load_frozen, run
from .cohort import assemble
from .spot import load_spot

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / "docs" / "research" / "LEVEL_SPOT_PERP_REACTION_DISCOVERY_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "LEVEL_SPOT_PERP_REACTION_DISCOVERY_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "LEVEL_SPOT_PERP_REACTION_DISCOVERY_V1_RESULT.md"
PACKAGE = Path(__file__).resolve().parent
TEST = ROOT / "tests" / "research" / "test_level_spot_perp_reaction_discovery_v1.py"


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
        "novelty_ok": True,
        "history_ok": bool(frozen.get("history_ok")),
    }


def main() -> None:
    refuse_if_recorded()
    design_sha = assert_clean_and_committed()
    frozen = load_frozen()
    if not frozen.get("pre_outcome_gate_pass"):
        payload = _base(design_sha, frozen, outcomes_read=False)
        payload.update({
            "routing": "SPOT_PERP_REACTION_INFORMATION_INSUFFICIENT",
            "candidate_class": "NONE",
            "baseline": {"endpos_coef": None, "cv1_coef": None, "n": 0},
            "features": [],
            "note": "The outcome-blind gate did not pass. Late labels were not read.",
        })
        text = report.render(payload)
        _write(RESULT_JSON, json.dumps(_py(payload), indent=2, sort_keys=True) + "\n")
        _write(RESULT_MD, text)
        print(payload["routing"])
        return
    bars = load_discovery_bars()
    venues = load_reaction_series()
    spot, _census = load_spot()
    built = assemble(bars, venues, spot)
    payload = run(bars, built, frozen)
    payload["design_sha"] = design_sha
    text = report.render(payload)
    _write(RESULT_JSON, json.dumps(_py(payload), indent=2, sort_keys=True) + "\n")
    _write(RESULT_MD, text)
    print(payload["routing"])


if __name__ == "__main__":
    main()
