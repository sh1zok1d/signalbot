"""Outcome-blind guards for MARKET-06 OKX source-route design review."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

FORBIDDEN = {
    "dislocation",
    "spread",
    "zscore",
    "future_return",
    "mae",
    "beta",
    "prediction",
    "drawdown",
}


def _walk_keys(payload, acc: set[str]) -> None:
    if isinstance(payload, dict):
        for k, v in payload.items():
            acc.add(str(k).lower())
            _walk_keys(v, acc)
    elif isinstance(payload, list):
        for item in payload:
            _walk_keys(item, acc)


def test_bybit_feasibility_artifact_preserved():
    path = REPO / "docs/research/MARKET_06_CROSS_VENUE_FEASIBILITY.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "MARKET_06_HISTORICAL_FEASIBILITY_REQUIRES_DESIGN_REVIEW"
    assert payload["data"]["bybit_source_endpoint"].startswith("GET https://api.bybit.com")
    assert payload["scientific_outcomes_inspected"] is False


def test_okx_design_review_is_outcome_blind_and_confirmed():
    path = REPO / "docs/research/MARKET_06_OKX_SPOT_ROUTE_DESIGN_REVIEW.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["verdict"] == "MARKET_06_OKX_HISTORICAL_FEASIBILITY_CONFIRMED"
    assert payload["market_06_status"] == "CONCEPT_SELECTED_NOT_PREREGISTERED"
    assert payload["scientific_outcomes_inspected"] is False
    assert payload["dislocation_computed"] is False
    assert payload["future_returns_computed"] is False
    assert payload["source_change_occurred_before_prereg"] is True
    assert payload["binance_spot_adopted"] is False
    assert payload["previous_feasibility_artifact_rewritten"] is False
    assert payload["structural_probes"]["okx_2022_probe_valid"] is True
    assert payload["structural_probes"]["okx_2023_probe_valid"] is True
    assert payload["structural_probes"]["okx_2024_probe_valid"] is True
    assert payload["census"]["ALIGNMENT_RATE"] == 1.0
    assert payload["census"]["ALIGNED_TIMESTAMPS"] == 315648
    keys: set[str] = set()
    _walk_keys(payload, keys)
    assert not (keys & FORBIDDEN)
    for name in (
        "docs/research/MARKET_06.md",
        "docs/research/MARKET_06_PREREG.md",
        "docs/research/MARKET_06_ARM.json",
        "docs/research/MARKET_06_RESULT.json",
    ):
        assert not (REPO / name).exists()


def test_timestamp_census_has_no_price_fields():
    path = REPO / "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/timestamp_census.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    keys: set[str] = set()
    _walk_keys(payload, keys)
    assert not (keys & FORBIDDEN)
    assert payload["interpolation"] is False
    assert payload["forward_fill"] is False
    assert payload["BINANCE_ROWS"] == payload["OKX_ROWS"] == 315648
