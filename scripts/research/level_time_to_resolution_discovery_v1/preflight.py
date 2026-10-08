"""Outcome-blind census. Does not read a barrier time or a survival curve."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from .cohort import assemble

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_TIME_TO_RESOLUTION_DISCOVERY_V1_PREFLIGHT.json"


def run() -> dict:
    bars = load_discovery_bars()
    if int(bars.times[-1]) >= K.EVENT_END_MS:
        raise RuntimeError("discovery grid reaches the protected surface")
    built = assemble(bars)
    gate = built["matched_pairs"] >= K.MATCHED_GATE and built["slices"]["other_year"] == 0
    payload = {
        "unit": K.UNIT,
        "outcomes_read": False,
        "resolution_times_read": False,
        "novelty_ok": True,
        "event_window": [PARENT_START, PARENT_END],
        "structural_episodes": built["structural_episodes"],
        "real_status": built["real_status"],
        "pseudo_status": built["pseudo_status"],
        "real_legitimate": built["real_legitimate"],
        "pseudo_legitimate": built["pseudo_legitimate"],
        "matched_pairs": built["matched_pairs"],
        "incomplete_4h_real": built["incomplete_4h_real"],
        "incomplete_4h_pseudo": built["incomplete_4h_pseudo"],
        "slices": built["slices"],
        "pre_outcome_gate_pass": gate,
        "history_ok": True,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


PARENT_START = "2020-02-01T00:00:00+00:00"
PARENT_END = "2025-01-01T00:00:00+00:00"
