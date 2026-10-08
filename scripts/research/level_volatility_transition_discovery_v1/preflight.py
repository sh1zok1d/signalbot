"""Outcome-blind census. Path flags only. No post-touch RV and no transition."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from .claim import support_gate
from .cohort import assemble

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_VOLATILITY_TRANSITION_DISCOVERY_V1_PREFLIGHT.json"

_FORBIDDEN = ("vol_transition", "rv_post", "rv_pre", "expansion", "pair_delta", "delta_transition")


def build_payload(bars=None) -> dict:
    if bars is None:
        bars = load_discovery_bars()
    assembled = assemble(bars)
    path = assembled["slices_path"]
    gate = support_gate(assembled["path_complete_pairs"], path["weeks"], path["year"])
    payload = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "outcomes_transition_read": False,
        "novelty_ok": K.NOVELTY_OK,
        "blocked_reopening_key_level_range": K.BLOCKED_REOPENING_KEY_LEVEL_RANGE,
        "blocked_reopening_volatility_transition_cell": K.BLOCKED_REOPENING_VOLATILITY_TRANSITION_CELL,
        "adjusted_sensitivity": K.ADJUSTED_SENSITIVITY,
        "compression_subgroup": K.COMPRESSION_SUBGROUP,
        "alternative_horizons": list(K.ALTERNATIVE_HORIZONS),
        "range_4h_endpoint": K.RANGE_4H_ENDPOINT,
        "event_start": "2020-02-01T00:00:00Z",
        "event_end": "2025-01-01T00:00:00Z",
        "structural_episodes": assembled["structural_episodes"],
        "real_status": assembled["real_status"],
        "pseudo_status": assembled["pseudo_status"],
        "real_legitimate": assembled["real_legitimate"],
        "pseudo_legitimate": assembled["pseudo_legitimate"],
        "matched_pairs": assembled["matched_pairs"],
        "path_complete_pairs": assembled["path_complete_pairs"],
        "slices_matched": assembled["slices_matched"],
        "slices_path": path,
        "pre_outcome_gate": gate,
        "pre_outcome_gate_pass": bool(gate["pass"] and K.NOVELTY_OK),
    }
    blob = json.dumps(payload).lower()
    for token in _FORBIDDEN:
        if token in blob:
            raise RuntimeError(f"preflight payload contains a transition field: {token}")
    return payload


def main() -> None:
    payload = build_payload()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "path_complete_pairs": payload["path_complete_pairs"],
        "weeks": payload["slices_path"]["weeks"],
        "years_eligible": payload["pre_outcome_gate"]["years_eligible"],
        "pre_outcome_gate_pass": payload["pre_outcome_gate_pass"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
