"""One official discovery run. Refuses to overwrite a recorded sequence result."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from . import preflight, report
from .cohort import assemble

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / "docs" / "research" / "LEVEL_BREAK_REJECT_SEQUENCE_DISCOVERY_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "LEVEL_BREAK_REJECT_SEQUENCE_DISCOVERY_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "LEVEL_BREAK_REJECT_SEQUENCE_DISCOVERY_V1_RESULT.md"
PACKAGE = Path(__file__).resolve().parent
TEST = ROOT / "tests" / "research" / "test_level_break_reject_sequence_discovery_v1.py"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def assert_clean_and_committed() -> str:
    paths = [DESIGN, preflight.OUT, TEST, *sorted(PACKAGE.glob("*.py"))]
    dirty = _git("status", "--porcelain", "--", *[str(p.relative_to(ROOT)) for p in paths])
    if dirty:
        raise RuntimeError("design or evaluator is dirty; refusing to read opposite-barrier sequences")
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


def _closed(design_sha: str, routing: str, note: str, outcomes: bool) -> dict:
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "claim_ceiling": K.CLAIM_CEILING,
        "exposure_status": K.EXPOSURE_STATUS,
        "design_sha": design_sha,
        "outcomes_sequence_read": outcomes,
        "routing": routing,
        "p1_class": "NONE",
        "p2_class": "NONE",
        "overall_candidate": False,
        "candidate_classes": [],
        "product_integration_candidate": False,
        "successor_candidate": "NONE",
        "primaries": {},
        "note": note,
    }


def main() -> None:
    refuse_if_recorded()
    design_sha = assert_clean_and_committed()
    frozen = json.loads(preflight.OUT.read_text())
    gates = frozen.get("gates") or {}
    if not frozen.get("novelty_ok"):
        payload = _closed(
            design_sha, "BLOCKED_REOPENING_FAILED_BREAKOUT_SEQUENCE",
            "Novelty audit failed. Opposite-barrier sequences were not read.", False,
        )
    elif not gates.get("P1") and not gates.get("P2"):
        payload = _closed(
            design_sha, "INFORMATION_LIMITED",
            "Both conditional denominators failed the pre-sequence gate. Sequences were not read.",
            False,
        )
    else:
        from .analyze import run
        bars = load_discovery_bars()
        built = assemble(bars)
        payload = run(bars, built, frozen)
        payload["design_sha"] = design_sha
    text = report.render(payload)
    _write(RESULT_JSON, json.dumps(_py(payload), indent=2, sort_keys=True) + "\n")
    _write(RESULT_MD, text)
    print(payload["routing"])


if __name__ == "__main__":
    main()
