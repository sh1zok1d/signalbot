"""Outcome-blind census and planning width. No post-touch RV."""

from __future__ import annotations

import json
import math
from pathlib import Path

from scripts.research.level_first_touch_resolution_confirmation_v1.data import load_confirmation_bars

from . import constants as K
from .cohort import assemble

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_VOLATILITY_TRANSITION_BITMEX_REPLICATION_V1_PREFLIGHT.json"

_FORBIDDEN = (
    "rv_post", "rv_pre", "vol_transition", "pair_delta", "delta_transition",
    "break", "reject", "neither", "rmut", "first_hit",
)


def planning(n_pairs: int, n_weeks: int) -> dict:
    """Transfer the published #368 cluster SE by week count. No BitMEX transition."""
    if int(n_pairs) < K.MIN_PAIRS or int(n_weeks) < 2:
        se = None
        half = None
        mde80 = None
        adequate = False
    else:
        se = K.DISCOVERY_BOOT_SE * math.sqrt(K.DISCOVERY_WEEKS / float(n_weeks))
        half = K.PLANNING_Z * se
        mde80 = (K.PLANNING_Z + K.PLANNING_Z_80) * se
        adequate = half < K.PRACTICAL_LOG
    return {
        "n_pairs": int(n_pairs),
        "n_weeks": int(n_weeks),
        "planning_se": se,
        "planning_ci_half_width": half,
        "planning_mde80": mde80,
        "practical_log": K.PRACTICAL_LOG,
        "adequate": adequate,
        "gate": "REPLICATION_INFORMATION_ADEQUATE" if adequate else "REPLICATION_INFORMATION_LIMITED",
        "scale": "published #368 week-bootstrap SE, scaled by sqrt(discovery weeks / target weeks)",
    }


def build_payload(bars=None) -> dict:
    if bars is None:
        bars, identity = load_confirmation_bars()
    else:
        identity = {"dataset_id": K.SURFACE_ID, "canonical_sha256": K.CANONICAL_SHA256}
    if identity.get("canonical_sha256") not in (None, K.CANONICAL_SHA256):
        raise RuntimeError("BitMEX canonical SHA does not match the frozen digest")
    assembled = assemble(bars)
    path = assembled["slices_path"]
    plan = planning(assembled["path_complete_pairs"], path["weeks"])
    payload = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "surface_evidence_class": K.SURFACE_EVIDENCE_CLASS,
        "surface_pristine": K.SURFACE_PRISTINE,
        "exact_claim_previously_read": K.EXACT_CLAIM_PREVIOUSLY_READ,
        "neighboring_post_touch_path_previously_read": K.NEIGHBORING_POST_TOUCH_PATH_PREVIOUSLY_READ,
        "replication_allowed": K.REPLICATION_ALLOWED,
        "outcomes_transition_read": False,
        "resolution_labels_used": False,
        "alternative_horizons": list(K.ALTERNATIVE_HORIZONS),
        "event_start": "2017-09-01T00:00:00Z",
        "event_end_exclusive": "2020-01-01T00:00:00Z",
        "dataset_id": identity.get("dataset_id"),
        "canonical_sha256": identity.get("canonical_sha256", K.CANONICAL_SHA256),
        "structural_episodes": assembled["structural_episodes"],
        "real_status": assembled["real_status"],
        "pseudo_status": assembled["pseudo_status"],
        "real_legitimate": assembled["real_legitimate"],
        "pseudo_legitimate": assembled["pseudo_legitimate"],
        "matched_pairs": assembled["matched_pairs"],
        "path_complete_pairs": assembled["path_complete_pairs"],
        "slices_path": path,
        "planning": plan,
        "pre_outcome_gate": plan["gate"],
        "pre_outcome_gate_pass": bool(plan["adequate"]),
    }
    blob = json.dumps(payload).lower()
    for token in _FORBIDDEN:
        if token in blob:
            raise RuntimeError(f"preflight payload contains a forbidden field: {token}")
    return payload


def main() -> None:
    payload = build_payload()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "path_complete_pairs": payload["path_complete_pairs"],
        "weeks": payload["slices_path"]["weeks"],
        "epochs": payload["slices_path"]["epoch"],
        "pre_outcome_gate": payload["pre_outcome_gate"],
        "planning_ci_half_width": payload["planning"]["planning_ci_half_width"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
