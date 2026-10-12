"""Freeze W_L1 for the paired shadow: one fit on the product surface, written once.

    python -m scripts.research.rangecast_v2.freeze

Fits `beta.rangecast_v2.fit_range_model_v2` (L1, half-life 365 days) on Binance USD-M BTCUSDT 5m from
2020-01-01 to 2026-10-11 (the loader of this unit; E1-RUN-001 objects refused before any request) and
writes docs/research/RANGECAST_V2_W_L1_MODEL_V1.json. No outcome is scored here: this is the fit the
production model V1 also makes nightly on the same surface. Refuses to overwrite an existing artifact.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from beta import rangecast_v2 as v2
from beta.calendar_events import event_times_ms, load_calendar

from . import data as D

REPO = Path(__file__).resolve().parents[3]
ARTIFACT = REPO / "docs/research/RANGECAST_V2_W_L1_MODEL_V1.json"
ARTIFACT_ID = "RANGECAST_V2_W_L1_MODEL_V1"


def main() -> dict:
    if ARTIFACT.exists():
        raise SystemExit(f"REFUSING_OVERWRITE: {ARTIFACT.name} exists")
    b, manifest = D.load_bars()
    cal = load_calendar()
    model = v2.fit_range_model_v2(b, events=event_times_ms(cal))
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    model["artifact_id"] = ARTIFACT_ID
    model["params_digest"] = v2.params_digest(model)
    model["freeze"] = {"data_source": manifest["source"], "symbol": manifest["symbol"],
                       "data_end_exclusive": manifest["data_end_exclusive"], "objects_sha256": manifest["objects_sha256"],
                       "n_objects": len(manifest["objects"]), "refused_before_request": manifest["refused_before_request"],
                       "calendar_version": cal.get("version"), "code_commit": head,
                       "note": "fit only; no outcome scored. E1-RUN-001 holdout objects never requested."}
    body = json.dumps(model, sort_keys=True, separators=(",", ":"))
    ARTIFACT.write_text(body + "\n")
    out = {"artifact": str(ARTIFACT.relative_to(REPO)), "file_sha256": hashlib.sha256(ARTIFACT.read_bytes()).hexdigest(),
           "params_digest": model["params_digest"], "spec_digest": model["spec_digest"], "bytes": ARTIFACT.stat().st_size}
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
