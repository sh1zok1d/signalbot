"""Outcome-blind census. Does not label late resolution."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

from . import constants as K
from .cohort import assemble, column, early_census, population, unresolved_rows
from .inference import freeze_scales, scale_hex, scales_usable
from .overlap import overlap_audit, rough_mde

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "research" / "LEVEL_ACCEPTANCE_PATH_DISCOVERY_V1_PREFLIGHT.json"

PARITY_KEYS = (
    "structural_episodes",
    "real_legitimate",
    "pseudo_legitimate",
    "geometry_pairs",
    "real_nuisance_unresolved",
    "n_unresolved",
    "n_early_resolved",
    "n_early_ambiguous",
    "sequence_counts",
    "state_counts",
    "eligible_contrasts",
    "scale_hex",
    "overlap_pass",
)


def _counts(rows: list[dict], key: str) -> dict:
    return {str(k): int(v) for k, v in sorted(Counter(row.get(key) for row in rows).items(), key=lambda item: str(item[0]))}


def _sequence_counts(rows: list[dict]) -> dict:
    counts = Counter(row.get("sequence") for row in rows)
    out = {name: int(counts[name]) for name in K.SEQUENCES}
    out["UNAVAILABLE"] = int(sum(v for k, v in counts.items() if k not in K.SEQUENCES))
    return out


def _state_counts(rows: list[dict]) -> dict:
    counts = Counter(row.get("state") for row in rows)
    out = {name: int(counts[name]) for name in K.STATES}
    out["UNAVAILABLE"] = int(sum(v for k, v in counts.items() if k not in K.STATES))
    return out


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


def _contrast_bundle(rows: list[dict], contrast: str) -> dict:
    arm = [row for row in rows if row.get("contrast") == contrast and row.get("nuisance_ok")]
    treated_name = K.TREATED_STATE[contrast]
    reference_name = K.REFERENCE_STATE[contrast]
    treated = [row for row in arm if row["state"] == treated_name]
    reference = [row for row in arm if row["state"] == reference_name]
    audit = overlap_audit(column(treated, "END_POSITION_X"), column(reference, "END_POSITION_X"), contrast=contrast)
    scales = freeze_scales(arm)
    usable = scales_usable(scales)
    reasons = list(audit["block_reasons"])
    if not usable:
        reasons.append("NONPOSITIVE_SCALE")
    eligible = bool(audit["arm_n_pass"] and audit["overlap_pass"] and usable)
    return {
        "audit": audit,
        "scales": scales,
        "scale_usable": usable,
        "eligible": eligible,
        "block_reasons": reasons,
        "n_arm": len(arm),
        "n_treated": len(treated),
        "n_reference": len(reference),
        "by_epoch": _counts(arm, "epoch"),
        "by_family": _counts(arm, "family"),
        "by_side": _counts(arm, "side"),
        "rough_80pct_mde": rough_mde(len(treated), len(reference)),
    }


def summarize(bars, built: dict | None = None) -> dict:
    built = population(bars) if built is None else built
    assembled = assemble(bars, built)
    real = assembled["real_rows"]
    census = early_census(real)
    unresolved = unresolved_rows(real)
    nuisance = [row for row in unresolved if row.get("nuisance_ok")]
    contrasts = {name: _contrast_bundle(unresolved, name) for name in K.CONTRASTS}
    eligible = [name for name in K.CONTRASTS if contrasts[name]["eligible"]]
    pseudo_unresolved = unresolved_rows([pair["pseudo"] for pair in assembled["pairs"]])
    blocked = None if eligible else "LEVEL_ACCEPTANCE_PATH_INFORMATION_LIMITED"
    return {
        "outcome_blind": True,
        "mode": K.MODE,
        "exposure_status": K.EXPOSURE_STATUS,
        "blocked_reason": blocked,
        "proceed_to_outcomes": blocked is None,
        "event_window": {"start": K.EVENT_START, "end_exclusive": K.EVENT_END},
        "decision": {
            "T": "open of the touch bar",
            "D": "T + 15 minutes",
            "reaction_bars": "j, j+1, j+2",
            "early_bars": "j+1, j+2",
            "late_bars": "j+3 .. j+48",
            "touch_bar_is_not_a_resolution": True,
        },
        "structural_episodes": assembled["structural_episodes"],
        "controls_built": assembled["controls_built"],
        "real_status": assembled["real_status"],
        "pseudo_status": assembled["pseudo_status"],
        "real_legitimate": int(assembled["real_status"]["LEGITIMATE"]),
        "pseudo_legitimate": int(assembled["pseudo_status"]["LEGITIMATE"]),
        "geometry_pairs": len(assembled["pairs"]),
        "real_weeks": len({int(row["week"]) for row in real}),
        "unresolved_weeks": len({int(row["week"]) for row in unresolved}),
        "early_census": census,
        "n_unresolved": census["n_unresolved"],
        "n_early_resolved": census["n_early_resolved"],
        "n_early_ambiguous": census["n_early_ambiguous"],
        "real_nuisance_unresolved": len(nuisance),
        "sequence_counts": _sequence_counts(unresolved),
        "state_counts": _state_counts(unresolved),
        "sequence_counts_nuisance": _sequence_counts(nuisance),
        "state_counts_nuisance": _state_counts(nuisance),
        "by_epoch_unresolved": _counts(unresolved, "epoch"),
        "by_family_unresolved": _counts(unresolved, "family"),
        "by_side_unresolved": _counts(unresolved, "side"),
        "by_time_block_unresolved": _counts(unresolved, "time_block"),
        "by_vol_tercile_unresolved": _counts(unresolved, "vol_tercile"),
        "pseudo_unresolved": len(pseudo_unresolved),
        "pseudo_sequence_counts": _sequence_counts(pseudo_unresolved),
        "pseudo_state_counts": _state_counts(pseudo_unresolved),
        "contrasts": contrasts,
        "eligible_contrasts": eligible,
        "overlap_pass": {name: bool(contrasts[name]["audit"]["overlap_pass"]) for name in K.CONTRASTS},
        "information": {
            name: {
                "n_treated": contrasts[name]["n_treated"],
                "n_reference": contrasts[name]["n_reference"],
                "rough_80pct_mde": contrasts[name]["rough_80pct_mde"],
                "eligible": contrasts[name]["eligible"],
                "deff_assumed": K.INFO_DEFF,
            }
            for name in K.CONTRASTS
        },
        "core": {
            "dataset_id": K.CORE_DATASET_ID,
            "zip_list_sha256": K.CORE_ZIP_LIST_SHA256,
            "bars": int(bars.n),
            "t0": int(bars.t0),
        },
        "price_only": True,
        "search_exposure_if_run": K.exposure(len(eligible)),
    }


def _attach_scale_hex(payload: dict) -> dict:
    payload["scale_hex"] = _scale_hex_map(payload["contrasts"])
    return payload


def _scale_hex_map(contrasts: dict) -> dict:
    out = {}
    for name in K.CONTRASTS:
        out[name] = {
            "END_POSITION_X": scale_hex(contrasts[name]["scales"]["END_POSITION_X"]),
            "disp": scale_hex(contrasts[name]["scales"]["disp"]),
        }
    return out


def summarize_clean(bars, built: dict | None = None) -> dict:
    return _attach_scale_hex(summarize(bars, built))


def main() -> None:
    bars = load_discovery_bars()
    payload = _py(summarize_clean(bars))
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "proceed": payload["proceed_to_outcomes"],
        "blocked": payload["blocked_reason"],
        "legitimate": payload["real_legitimate"],
        "unresolved": payload["n_unresolved"],
        "early_resolved": payload["n_early_resolved"],
        "early_ambiguous": payload["n_early_ambiguous"],
        "eligible": payload["eligible_contrasts"],
        "states": payload["state_counts"],
        "weeks": payload["unresolved_weeks"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
