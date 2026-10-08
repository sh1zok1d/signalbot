"""Outcome-blind accrual status.

This module must not import the transition estimator.
"""

from __future__ import annotations

import datetime as dt
import json

from . import accrual, constants as K
from .surface import MANIFEST, PAIR_MAP, PEEK_FLAG, RESULT_JSON, UTC, load_manifest

_FORBIDDEN = K.FORBIDDEN_STATUS_FIELDS


def _keys(value) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.append(str(key).lower())
            found.extend(_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_keys(item))
    return found


def _clean(payload: dict) -> dict:
    found = set(_keys(payload))
    for token in _FORBIDDEN:
        if token in found:
            raise RuntimeError(f"status exposed a forbidden field {token}")
    return payload


def build_status(now: dt.datetime, manifest: dict, *, panel_bound: bool = False,
                 structural_episodes: int = 0, real_first_touches: int = 0,
                 family_counts: dict | None = None, side_counts: dict | None = None,
                 matched_pairs: int | None = None, gaps: int = 0) -> dict:
    clock = accrual.clock_status(now, manifest["prospective_start_utc"])
    at_checkpoint = clock["completed_weeks"] in K.CHECKPOINT_WEEKS
    decision = accrual.stop_decision(
        completed=clock["completed_weeks"],
        matched_pairs=matched_pairs,
        at_checkpoint=at_checkpoint,
    )
    if now.astimezone(UTC) < dt.datetime.fromisoformat(
        manifest["prospective_start_utc"].replace("Z", "+00:00")
    ):
        accrual_state = "AWAITING_START"
    else:
        accrual_state = "ACCRUING"
    payload = {
        "unit": K.UNIT,
        "protocol": "PROSPECTIVE_CONFIRMATION_STARTED",
        "status": accrual_state,
        "surface_evidence_class": K.SURFACE_EVIDENCE_CLASS,
        "prospective_start": manifest["prospective_start_utc"],
        "design_sha": manifest["design_sha"],
        "completed_weeks": clock["completed_weeks"],
        "start_reached": clock["start_reached"],
        "structural_episodes": int(structural_episodes) if panel_bound else 0,
        "real_first_touches": int(real_first_touches) if panel_bound else 0,
        "family_counts": family_counts or {},
        "side_counts": side_counts or {},
        "matched_path_complete_provisional": matched_pairs if panel_bound else None,
        "panel_bound": bool(panel_bound),
        "bar_gaps_logged": int(gaps),
        "distinct_iso_weeks_note": "counted only from a bound forward panel",
        "next_checkpoint": clock["next_checkpoint"],
        "stop_condition_met": bool(decision["stop"] and not decision["information_limited"]),
        "information_limited_close": bool(decision["information_limited"]),
        "cohort_closed": bool(manifest.get("cohort_closed")),
        "pair_map_frozen": bool(manifest.get("pair_map_frozen")),
        "exact_outcome_read": False,
        "peek_flag_present": PEEK_FLAG.exists(),
        "pair_map_present": PAIR_MAP.exists(),
        "result_present": RESULT_JSON.exists(),
    }
    if payload["exact_outcome_read"]:
        raise RuntimeError("status must not report an outcome read")
    return _clean(payload)


def main() -> None:
    manifest = load_manifest(MANIFEST)
    payload = build_status(dt.datetime.now(UTC), manifest, panel_bound=False)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
