"""One official discovery run. Refuses to overwrite a recorded zone-traded result."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np

from . import constants as K
from . import preflight, report

ROOT = Path(__file__).resolve().parents[3]
DESIGN = ROOT / "docs" / "research" / "LEVEL_ZONE_TRADED_ACTIVITY_DISCOVERY_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "LEVEL_ZONE_TRADED_ACTIVITY_DISCOVERY_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "LEVEL_ZONE_TRADED_ACTIVITY_DISCOVERY_V1_RESULT.md"
PACKAGE = Path(__file__).resolve().parent
TEST = ROOT / "tests" / "research" / "test_level_zone_traded_activity_discovery_v1.py"
DATA = ROOT / "docs" / "research_data" / K.TRADE_DATASET_ID


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def assert_clean_and_committed() -> str:
    paths = [
        DESIGN, preflight.OUT, TEST,
        DATA / "event_aggregates.json", DATA / "SOURCE_INVENTORY.json",
        *sorted(PACKAGE.glob("*.py")),
    ]
    dirty = _git("status", "--porcelain", "--", *[str(p.relative_to(ROOT)) for p in paths])
    if dirty:
        raise RuntimeError("design or evaluator is dirty; refusing to read late labels")
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


def _closed(design_sha: str, routing: str, note: str) -> dict:
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "claim_ceiling": K.CLAIM_CEILING,
        "exposure_status": K.EXPOSURE_STATUS,
        "design_sha": design_sha,
        "outcomes_read": False,
        "routing": routing,
        "overall_candidate_class": "NONE",
        "product_integration_candidate": False,
        "successor_candidate": "NONE",
        "features": [],
        "baseline": {},
        "note": note,
    }


def main() -> None:
    refuse_if_recorded()
    design_sha = assert_clean_and_committed()
    frozen = json.loads(preflight.OUT.read_text())
    if not frozen.get("novelty_ok"):
        payload = _closed(
            design_sha, "BLOCKED_REOPENING_ZONE_TRADED_ACTIVITY_CELL",
            "Novelty audit failed. Late labels were not read.",
        )
    elif not frozen.get("touch_identity_pass"):
        payload = _closed(
            design_sha, "AGGTRADE_TOUCH_IDENTITY_FAILED",
            "Raw aggTrades did not reproduce the parent structural touch. Late labels were not read.",
        )
    elif not frozen.get("pre_outcome_gate_pass"):
        payload = _closed(
            design_sha, "ZONE_TRADED_ACTIVITY_INFORMATION_INSUFFICIENT",
            "The pre-outcome information gate failed. Late labels were not read.",
        )
    else:
        from .analyze import run
        from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

        payload = run(load_discovery_bars(), frozen)
        payload["design_sha"] = design_sha
    text = report.render(payload)
    _write(RESULT_JSON, json.dumps(_py(payload), indent=2, sort_keys=True) + "\n")
    _write(RESULT_MD, text)
    print(payload["routing"])


if __name__ == "__main__":
    main()
