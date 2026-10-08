"""Outcome-blind census. Parent first-event labels only. No opposite-barrier scan."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from .cohort import assemble, first_event_counts, gate_from_counts

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_BREAK_REJECT_SEQUENCE_DISCOVERY_V1_PREFLIGHT.json"


def run() -> dict:
    bars = load_discovery_bars()
    if int(bars.times[-1]) >= K.EVENT_END_MS:
        raise RuntimeError("discovery grid reaches the protected surface")
    built = assemble(bars)
    counts = first_event_counts(bars, built["pairs"])
    gates = gate_from_counts(counts)
    payload = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "outcomes_sequence_read": False,
        "first_event_type_already_exposed": K.FIRST_EVENT_TYPE_ALREADY_EXPOSED,
        "post_first_opposite_barrier_sequence_not_yet_read": (
            K.POST_FIRST_OPPOSITE_BARRIER_SEQUENCE_NOT_YET_READ
        ),
        "novelty_ok": K.NOVELTY_OK,
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
        "first_event": counts,
        "gates": gates,
        "denominator_gate": K.DENOM_GATE,
        "history_ok": True,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


PARENT_START = "2020-02-01T00:00:00+00:00"
PARENT_END = "2025-01-01T00:00:00+00:00"
