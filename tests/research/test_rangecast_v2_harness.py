"""RANGECAST_V2 harness guards (scripts/research/rangecast_v2): the loader never plans or requests an
E1-RUN-001 object, the committed development record follows the frozen selection rule, and the one
2025-2026 read cannot run twice. No network and no market data are read here."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_the_loader_never_plans_or_requests_an_e1_object():
    from beta import history_data as hd
    from scripts.research.rangecast_v2 import data as D
    planned, refused = D.kline_objects(date(2026, 10, 12))
    assert all(hd.object_protected(o) is None for o in planned)
    assert len(refused) == 11 and all(hd.object_protected(o) for o in refused)
    with pytest.raises(hd.ProtectedObjectRefused):
        D._get(hd.VISION_ROOT + "/daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-20.zip")


def test_the_development_record_follows_the_frozen_rule():
    dev = json.loads((ROOT / "docs/research/RANGECAST_V2_DEVELOPMENT.json").read_text())
    sel = dev["selection"]
    accepted = "V1"
    for lvl in ("L1", "L2", "L3"):
        t = sel["ladder"][lvl]
        assert t["against"] == accepted
        ok = t["ci95"][1] < 0 and sum(1 for v in t["by_year"].values() if v < 0) >= 3
        assert t["accepted"] == ok
        accepted = lvl if ok else accepted
    assert sel["selected_level"] == accepted == "L1"
    r = sel["recency"]
    assert r["accepted"] == (r["ci95"][1] < 0 and sum(1 for v in r["by_year"].values() if v < 0) >= 3)
    assert sel["selected"] == "W_L1" and sel["guardrails"]["all_pass"]


def test_the_2025_2026_read_cannot_run_twice():
    from scripts.research.rangecast_v2 import evaluate as E
    assert E.READ_PATH.exists()
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        E.read2025()
