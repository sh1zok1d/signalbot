"""The cross-venue unit stops before any Bybit outcome. No market path is scored."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FEASIBILITY = ROOT / "docs" / "research" / "FUNDING_TAIL_RISK_CROSS_VENUE_V1_FEASIBILITY.json"
PARENT = ROOT / "docs" / "research" / "FUNDING_STATE_HISTORICAL_STRUCTURE_V1_RESULT.json"


def test_funding_provenance_blocks_before_an_outcome():
    payload = json.loads(FEASIBILITY.read_text(encoding="utf-8"))
    assert payload["status"] == "BLOCKED_BY_CROSS_VENUE_FUNDING_PROVENANCE"
    assert payload["outcome_read"] is False
    assert payload["bybit_funding_rows_acquired"] == 0
    assert payload["price_high_low_close_used"] is False
    assert payload["premium_scored"] is False
    assert payload["oi_opened"] is False
    assert payload["objects_2025_2026_used"] is False
    assert payload["product_integration_candidate"] is False
    assert payload["parent_rerun"] is False
    assert not (ROOT / "docs" / "research" / "FUNDING_TAIL_RISK_CROSS_VENUE_V1_RESULT.json").exists()


def test_parent_verdict_is_not_rewritten():
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    assert parent["interpretation"]["code"] == "INCREMENTAL_ASSOCIATION_UNCERTAIN"
    assert parent["outcome_read"] is True
