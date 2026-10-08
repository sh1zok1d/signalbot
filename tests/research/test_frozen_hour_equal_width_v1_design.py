"""The equal-width note is a design. It does not open a market file or rewrite the parent JSON."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / "docs" / "research" / "FROZEN_HOUR_EQUAL_WIDTH_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_RESULT.json"
PARENT_JSON_SHA = "9d21dafa4272bc0dab16329187edd65a7acf50adad071b80c8d63f2ea3c57fae"


def test_parent_result_json_is_the_published_read():
    assert hashlib.sha256(RESULT_JSON.read_bytes()).hexdigest() == PARENT_JSON_SHA


def test_design_freezes_the_control_and_does_not_report_an_outcome():
    text = DESIGN.read_text(encoding="utf-8")
    for phrase in (
        "outcome_read = false",
        "DH1_BINANCE_SPOT_BTCUSDT_5M_V0",
        "2017-09-01",
        "2020-01-01",
        "E1_RUN_001_FINAL_HOLDOUT",
        "exp(k u)",
        "1e-9",
        "immediate",
        "20261031",
        "20261102",
        "0.03",
        "614",
        "WIDTH_HELD_DIFFERENCE_PRESENT",
        "NO_WIDTH_HELD_RESOLUTION_DIFFERENCE",
        "INFORMATION_LIMITED_STOP_BEFORE_OUTCOME",
    ):
        assert phrase in text
    assert "resolution rate" not in text.lower()
    assert "paired delta" not in text.lower()
