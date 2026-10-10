"""Outcome-free feature rows for MULTISCALE_ADAPTIVE_OCCUPANCY_V2 design work.

The rows, anchors, OCC_L and B1 quantities are exactly ADAPTIVE_OCCUPANCY_TIMESCALE_V1's (imported loader, pinned
feature digest). R_1H and Y are deleted on load and never cached: this package reads no market outcome."""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from scripts.research.adaptive_occupancy_v1 import constants as K1
from scripts.research.adaptive_occupancy_v1.evaluate import feature_digest

FEATURES = ("close_ms", "era", "venue", "bar", "rp", "ret4", "rv4", "ret1h", "ret15") + tuple(
    f"OCC_{h}H" for h in K1.LOOKBACK_HOURS)
OUTCOME_KEYS = ("r1", "y")


def cache_path() -> Path:
    root = Path(os.environ.get("MSOCC_V2_CACHE", "/tmp/msocc_v2_cache"))
    return root / f"features_{K1.EXPECTED_FEATURE_SHA256[:16]}.npz"


def strip_outcomes(rows: dict) -> dict:
    out = {k: rows[k] for k in FEATURES}
    for k in OUTCOME_KEYS:
        if k in out:
            raise SystemExit("OUTCOME_IN_FEATURES")
    return out


def load_features() -> dict:
    path = cache_path()
    if path.exists():
        z = np.load(path)
        rows = {k: z[k] for k in FEATURES}
    else:
        from scripts.research.adaptive_occupancy_v1.surfaces import load_all
        full = load_all()
        rows = strip_outcomes(full)
        del full
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, **rows)
    if feature_digest(rows) != K1.EXPECTED_FEATURE_SHA256:
        raise SystemExit("FEATURE_DIGEST_MISMATCH")
    return rows
