"""One official replication. Refuses a second read of the BitMEX transition."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np

from . import constants as K
from . import preflight, report

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / "docs" / "research" / "LEVEL_VOLATILITY_TRANSITION_BITMEX_REPLICATION_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "LEVEL_VOLATILITY_TRANSITION_BITMEX_REPLICATION_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "LEVEL_VOLATILITY_TRANSITION_BITMEX_REPLICATION_V1_RESULT.md"
PACKAGE = Path(__file__).resolve().parent
TEST = ROOT / "tests" / "research" / "test_level_volatility_transition_bitmex_replication_v1.py"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def assert_clean_and_committed() -> str:
    paths = [DESIGN, preflight.OUT, TEST, *sorted(PACKAGE.glob("*.py"))]
    dirty = _git("status", "--porcelain", "--", *[str(p.relative_to(ROOT)) for p in paths])
    if dirty:
        raise RuntimeError("design or evaluator is dirty; refusing to read post-touch RV")
    sha = _git("log", "-1", "--format=%H", "--", str(DESIGN.relative_to(ROOT)))
    if not sha:
        raise RuntimeError("design note is not committed")
    return sha


def refuse_if_recorded(json_path: Path = RESULT_JSON, md_path: Path = RESULT_MD) -> None:
    if json_path.exists() or md_path.exists():
        raise SystemExit("REFUSING_RERUN: a replication result is already recorded")


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


def _closed(design_sha: str, note: str) -> dict:
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "surface_evidence_class": K.SURFACE_EVIDENCE_CLASS,
        "claim_ceiling": K.CLAIM_CEILING,
        "design_sha": design_sha,
        "outcomes_read": False,
        "routing": "REPLICATION_INFORMATION_LIMITED",
        "evidence_label": "REPLICATION_INFORMATION_LIMITED",
        "product_integration_candidate": False,
        "prospective_started": False,
        "note": note,
    }


def main() -> None:
    refuse_if_recorded()
    design_sha = assert_clean_and_committed()
    frozen = json.loads(preflight.OUT.read_text())
    if not frozen.get("pre_outcome_gate_pass"):
        payload = _closed(
            design_sha,
            "The outcome-blind planning width cannot separate a 10% log multiplier from zero. Post-touch RV was not read.",
        )
    else:
        from .analyze import run
        from scripts.research.level_first_touch_resolution_confirmation_v1.data import load_confirmation_bars

        bars, _identity = load_confirmation_bars()
        payload = run(bars, frozen)
        payload["design_sha"] = design_sha
    text = report.render(payload)
    _write(RESULT_JSON, json.dumps(_py(payload), indent=2, sort_keys=True) + "\n")
    _write(RESULT_MD, text)
    print(payload["routing"])


if __name__ == "__main__":
    main()
