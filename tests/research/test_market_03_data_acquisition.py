"""MARKET-03 data-acquisition report tests.

Does not run EmaCross/EmaCrossFunding or compute strategy outcomes.
Does not read gitignored raw ZIP/JSONL row values.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MD = REPO / "docs/research/MARKET_03_DATA_ACQUISITION.md"
JS = REPO / "docs/research/MARKET_03_DATA_ACQUISITION.json"
SNAP = (
    REPO
    / "docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0"
    / "SNAPSHOT_2ce1f504.json"
)
QUALITY = (
    REPO
    / "docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0"
    / "QUALITY_REPORT_2ce1f504.json"
)
FUNDING = (
    REPO
    / "docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0"
    / "FUNDING_COMPATIBILITY_2ce1f504.json"
)

EXPECTED_SNAPSHOT = (
    "2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345"
)
EXPECTED_JSON_SHA256 = (
    "f1dfd27c42c39ab09c8047df0f83bd27518cb84d9e82244f4f3954249fe07cf2"
)
EXPECTED_CODE = {
    "scripts/research/market_03_binance_spot_btcusdt_1h_v0_acquire.py": (
        "8337e51b25b1d87bd4d64310e7f55f313b28a6dd2ac4706a43acdf1c1209cce1"
    ),
    "scripts/research/market_03_binance_spot_btcusdt_1h_v0_lib.py": (
        "592cc173f8f1ce4f3e46a7072d825923d5defeeb7619a319564d8ca9948a2974"
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_acquisition_report_verdict_and_flags():
    payload = json.loads(JS.read_text(encoding="utf-8"))
    assert payload["feasibility_verdict"] == "READY_FOR_MARKET_03_PREREG_DESIGN"
    assert payload["feasibility_verdict_letter"] == "A"
    assert payload["replication_level"] == "LEVEL_2_FAITHFUL_REIMPLEMENTATION"
    assert payload["replication_level_not_upgraded_to"] == "LEVEL_1_EXACT_REPRODUCTION"
    assert payload["STRICT_HISTORICAL_PUBLICATION_LATENCY"] == "UNPROVEN"
    assert payload["REPRODUCTION_FUNDINGTIME_ASSUMPTION"] == "ACCEPTABLE"
    assert payload["SPOT_DATASET_ID"] == "MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0"
    assert payload["SPOT_SNAPSHOT_ID"] == EXPECTED_SNAPSHOT
    assert payload["SPOT_ROWS"] == 47477
    assert payload["SPOT_GAPS"] == 43
    assert payload["SPOT_DUPLICATES"] == 0
    assert payload["SPOT_DATA_SHA256"] == (
        "e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4"
    )
    assert payload["MARKET_03_STRATEGY_EXECUTED"] is False
    assert payload["MARKET_03_OUTCOMES_INSPECTED"] is False
    assert payload["MARKET_03_PARAMETER_SEARCH"] is False
    assert payload["MARKET_03_PREREGISTERED"] is False
    assert payload["MARKET_03_ARMED"] is False
    assert payload["PROTECTED_OOS_USED_FOR_SCIENCE"] is False
    assert payload["B2_06_EXECUTION_AUTHORIZED"] is False
    assert payload["market_03_scientifically_bound"] is False
    assert payload["external_source"]["commit"] == (
        "b68a5518b4a3eba2fde1733160d7d7de356023b5"
    )
    assert payload["external_source"]["replaced"] is False
    assert _sha256(JS) == EXPECTED_JSON_SHA256
    text = MD.read_text(encoding="utf-8")
    assert "READY_FOR_MARKET_03_PREREG_DESIGN" in text
    assert "LEVEL_2_FAITHFUL_REIMPLEMENTATION" in text
    assert "MARKET_03_STRATEGY_EXECUTED     = NO" in text
    assert "PROTECTED_OOS_USED_FOR_SCIENCE  = NO" in text
    assert "Do not begin preregistration" in text or "does **not** begin preregistration" in text


def test_snapshot_identity_and_construction_hashes():
    snapshot = json.loads(SNAP.read_text(encoding="utf-8"))
    assert snapshot["snapshot_id"] == EXPECTED_SNAPSHOT
    payload = snapshot["identity_payload"]
    assert payload["dataset_id"] == "MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0"
    assert payload["market_type"] == "SPOT"
    assert payload["interval"] == "1h"
    assert payload["end_exclusive"] == "2025-01-01T00:00:00Z"
    assert payload["market_03_scientifically_bound"] is False
    assert payload["construction_code_sha256"] == EXPECTED_CODE
    for rel, digest in EXPECTED_CODE.items():
        assert _sha256(REPO / rel) == digest
    quality = json.loads(QUALITY.read_text(encoding="utf-8"))
    assert quality["row_count"] == 47477
    assert quality["gap_count"] == 43
    assert quality["duplicate_count"] == 0
    assert quality["protected_oos_used_for_science"] is False
    funding = json.loads(FUNDING.read_text(encoding="utf-8"))
    assert funding["strict_historical_publication_latency"] == "UNPROVEN"
    assert funding["b2_06_execution_authorized"] is False
    assert funding["protected_oos_compared"] is False
    assert funding["strategy_outcomes_compared"] is False
    eq = funding["record_level_semantic_equivalence_authorized_overlap"]
    assert eq["exact_timestamp_rate_equal_count"] == 5481
    assert eq["exact_timestamp_rate_mismatch_count"] == 0
    zipc = funding["vision_vs_b2_06_container_identity"]
    assert zipc["container_sha256_equal_count"] == 52
    assert zipc["container_sha256_mismatch_count"] == 0


def test_no_strategy_quantities_in_acquisition_json():
    payload = json.loads(JS.read_text(encoding="utf-8"))
    blob = json.dumps(payload)
    for token in (
        "ema600",
        "funding_pct",
        "equity_curve",
        "cagr",
        "sharpe",
        "sortino",
        "drawdown",
    ):
        assert token not in blob.lower()
