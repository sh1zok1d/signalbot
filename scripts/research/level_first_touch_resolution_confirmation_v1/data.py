"""BitMEX confirmation bars. Price grid only. No outcome is computed here."""

from __future__ import annotations

import json

import numpy as np

from scripts.research.dh1.data import BITMEX_INVENTORY, load_bitmex_5m, to_bars

from . import constants as K


def inventory() -> dict:
    body = json.loads(BITMEX_INVENTORY.read_text())
    if body.get("DATASET_ID") != K.SURFACE_ID:
        raise RuntimeError("BitMEX inventory is not DH1_BITMEX_XBTUSD_TRADES_5M_V0")
    days = str(body.get("DAYS", ""))
    if not days.startswith("2017-08-01") or not days.endswith("2019-12-31"):
        raise RuntimeError(f"BitMEX inventory days are {days}")
    return body


def assert_panel(panel: dict) -> None:
    """Refuse any bar outside 2017-08-01 .. 2020-01-01, and any protected window."""
    t = np.asarray(panel["open_ms"])
    if t.size == 0:
        raise RuntimeError("BitMEX panel is empty")
    tmin = int(t.min())
    tmax = int(t.max())
    if tmin < K.DATA_START_MS:
        raise RuntimeError("BitMEX panel contains a bar before 2017-08-01")
    if tmax >= K.EVENT_END_MS:
        raise RuntimeError("BitMEX panel contains a bar at or after 2020-01-01")
    if tmax >= K.PROTECTED_FROM_MS or np.any(t >= K.PROTECTED_FROM_MS):
        raise RuntimeError("BitMEX panel contains a 2025/2026 bar")
    if np.any((t >= K.E1_START_MS) & (t < K.E1_END_MS)):
        raise RuntimeError("BitMEX panel overlaps the E1 holdout")


def load_confirmation_bars():
    """Canonical 5m grid [2017-08-01, 2020-01-01). Missing trade bins stay NaN."""
    inv = inventory()
    panel = load_bitmex_5m()
    assert_panel(panel)
    bars = to_bars(panel, K.DATA_START_MS, K.EVENT_END_MS)
    if int(bars.t0) != K.DATA_START_MS or int(bars.end_ms) != K.EVENT_END_MS:
        raise RuntimeError("confirmation grid is not [2017-08-01, 2020-01-01)")
    identity = {
        "dataset_id": inv["DATASET_ID"],
        "days": inv["DAYS"],
        "canonical_sha256": inv["CANONICAL_SHA256"],
        "object_list_sha256": inv.get("OBJECT_LIST_SHA256"),
        "rows": inv.get("ROWS"),
        "grid_start": K.DATA_START,
        "grid_end_exclusive": K.EVENT_END,
        "n_bars": int(bars.n),
        "objects_2025_2026": "none",
    }
    return bars, identity
