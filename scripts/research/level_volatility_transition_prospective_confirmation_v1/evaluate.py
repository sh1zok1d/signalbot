"""One-shot evaluator. It refuses until the cohort, the pair map and the stop exist.

A second legal run refuses as well. This module does not import the RV
estimator at import time.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import constants as K
from .surface import (
    MANIFEST,
    PAIR_MAP,
    PEEK_FLAG,
    RESULT_JSON,
    RESULT_MD,
    load_manifest,
)
from .pairing import digest_of


def refusal(*, manifest_ok: bool, cohort_closed: bool, stop_met: bool,
            pair_map_present: bool, digest_ok: bool, peek: bool,
            result_exists: bool, information_limited_without_read: bool) -> str | None:
    if result_exists:
        return "REFUSING_RERUN"
    if peek:
        return "REFUSING_PREMATURE_PROSPECTIVE_EVALUATION"
    if information_limited_without_read:
        return "REFUSING_PREMATURE_PROSPECTIVE_EVALUATION"
    if not (manifest_ok and cohort_closed and stop_met and pair_map_present and digest_ok):
        return "REFUSING_PREMATURE_PROSPECTIVE_EVALUATION"
    return None


def _state_from_disk() -> dict:
    manifest_ok = False
    cohort_closed = False
    stop_met = False
    try:
        manifest = load_manifest(MANIFEST)
        manifest_ok = True
        cohort_closed = bool(manifest.get("cohort_closed"))
        stop_met = bool(manifest.get("stop_met"))
    except (OSError, RuntimeError, json.JSONDecodeError, KeyError):
        manifest = None
    pair_present = PAIR_MAP.exists()
    digest_ok = False
    if pair_present:
        try:
            payload = json.loads(PAIR_MAP.read_text())
            digest_ok = payload.get("pair_map_digest") == digest_of(payload)
            keys = set()

            def walk(value) -> None:
                if isinstance(value, dict):
                    keys.update(str(key).lower() for key in value)
                    for item in value.values():
                        walk(item)
                elif isinstance(value, list):
                    for item in value:
                        walk(item)

            walk(payload)
            if keys & {"rv_post", "pair_delta", "vol_transition", "delta_transition"}:
                digest_ok = False
        except (OSError, json.JSONDecodeError):
            digest_ok = False
    return {
        "manifest_ok": manifest_ok,
        "cohort_closed": cohort_closed,
        "stop_met": stop_met,
        "pair_map_present": pair_present,
        "digest_ok": digest_ok,
        "peek": PEEK_FLAG.exists(),
        "result_exists": RESULT_JSON.exists() or RESULT_MD.exists(),
        "information_limited_without_read": bool(manifest and manifest.get("information_limited_close")),
    }


def main() -> None:
    reason = refusal(**_state_from_disk())
    if reason == "REFUSING_RERUN":
        raise SystemExit("REFUSING_RERUN")
    if reason:
        raise SystemExit("REFUSING_PREMATURE_PROSPECTIVE_EVALUATION")
    raise RuntimeError("legal prospective evaluation is not reachable in the setup task")


if __name__ == "__main__":
    main()


def assert_package_has_no_result(root: Path | None = None) -> None:
    """Used by tests. The setup task must not leave a prospective result."""
    if RESULT_JSON.exists() or RESULT_MD.exists():
        raise RuntimeError("a prospective result exists; the setup task must not write one")
    del root
    if K.SURFACE_EVIDENCE_CLASS != "PRISTINE_CONFIRMATION":
        raise RuntimeError("evidence class drifted")
