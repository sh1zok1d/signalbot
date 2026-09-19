"""MARKET-03 dedicated REST funding snapshot tests.

Outcome-blind. Does not run EmaCross/EmaCrossFunding or compute strategy
outcomes. Does not require gitignored raw JSONL for the identity checks.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.research.market_03_binance_um_btcusdt_fundingrate_rest_v0_lib import (
    DATASET_ID,
    EXPECTED_SOURCE_SHA256,
    EXPECTED_SOURCE_SIZE,
    FORBIDDEN_STRATEGY_TOKENS,
    PRE_SNAPSHOT_HEAD,
    PRE_SNAPSHOT_TREE,
    PREREG_JSON_SHA256,
    PREREG_MD_SHA256,
    SOURCE_RELATIVE_PATH,
    SPOT_DATA_SHA256,
    SPOT_DATASET_ID,
    SPOT_SNAPSHOT_ID,
    STRICT_HISTORICAL_PUBLICATION_LATENCY,
    Market03FundingSnapshotError,
    assert_no_strategy_quantities,
    audit_funding_rows,
    canonical_jsonl_bytes,
    parse_rest_funding_jsonl,
    prove_source_fidelity,
    refuse_b2_06_as_authority,
    sha256_of_canonical_identity_payload,
    snapshot_from_payload,
)

REPO = Path(__file__).resolve().parents[2]
MD = REPO / "docs/research/MARKET_03_FUNDING_SNAPSHOT.md"
JS = REPO / "docs/research/MARKET_03_FUNDING_SNAPSHOT.json"
PREREG_MD = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.md"
PREREG_JS = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json"
SPOT_SNAP = (
    REPO
    / "docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0"
    / "SNAPSHOT_2ce1f504.json"
)
EVIDENCE = REPO / "docs/research_data/MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0"
SNAP = EVIDENCE / "SNAPSHOT_d47b7b78.json"
LEDGER = EVIDENCE / "SOURCE_LEDGER_d47b7b78.json"
QUALITY = EVIDENCE / "QUALITY_REPORT_d47b7b78.json"
MANIFEST = REPO / "docs/manifests/MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0.yaml"

EXPECTED_SNAPSHOT = (
    "d47b7b78b6e7dbb842c7d9eb122c81063e0b804e179a53dd87723f9a8a8adc68"
)
EXPECTED_REPORT_JSON_SHA256 = (
    "870dd3974fa6565b8cca1399be59d100d60a87722d9942ec43eba5eee89e5af3"
)
EXPECTED_CODE = {
    "scripts/research/market_03_binance_um_btcusdt_fundingrate_rest_v0_lib.py": (
        "4f626eea335b062f384aa6c9192cf4e55266085a4fa0b0c11686e7494a2d9a25"
    ),
    "scripts/research/market_03_binance_um_btcusdt_fundingrate_rest_v0_materialize.py": (
        "cbbfc63b48f32b6125b8d4517a605a523297dd3e97e9971537323928f2beadc4"
    ),
}
EXPECTED_IDENTITY_HASHES = {
    "SNAPSHOT_d47b7b78.json": (
        "5cf01f672b2e2de2d6ce7966109d91a0fcfc82ec8dd08fe11fcf0b1321d3b210"
    ),
    "SOURCE_LEDGER_d47b7b78.json": (
        "7232016e568f06e8328034ee9f665301052267a13feb1645788af40bb395bef6"
    ),
    "QUALITY_REPORT_d47b7b78.json": (
        "01881f1762a4faaa80ba8e6c286165c01dadfc2d91869904c94463ccc20ddde2"
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _payload() -> dict:
    return json.loads(JS.read_text(encoding="utf-8"))


def test_prereg_and_spot_bytes_unchanged():
    assert _sha256(PREREG_MD) == PREREG_MD_SHA256
    assert _sha256(PREREG_JS) == PREREG_JSON_SHA256
    assert PREREG_MD.stat().st_size == 15063
    assert PREREG_JS.stat().st_size == 15587
    spot = json.loads(SPOT_SNAP.read_text(encoding="utf-8"))
    assert spot["snapshot_id"] == SPOT_SNAPSHOT_ID
    assert spot["identity_payload"]["dataset_id"] == SPOT_DATASET_ID
    assert spot["identity_payload"]["canonical_klines_sha256"] == SPOT_DATA_SHA256


def test_funding_snapshot_record_verdict_and_flags():
    payload = _payload()
    assert payload["unit_verdict"] == "A. FUNDING_SNAPSHOT_READY"
    assert payload["status"] == "FUNDING_SNAPSHOT_READY"
    assert payload["FUNDING_DATASET_ID"] == DATASET_ID
    assert payload["FUNDING_SNAPSHOT_ID"] == EXPECTED_SNAPSHOT
    assert payload["SOURCE_SHA256"] == EXPECTED_SOURCE_SHA256
    assert payload["SOURCE_SIZE"] == EXPECTED_SOURCE_SIZE
    assert payload["FUNDING_DATA_SHA256"] == EXPECTED_SOURCE_SHA256
    assert payload["FUNDING_ROWS"] == 5819
    bounds = payload["FUNDING_TIME_BOUNDS"]
    assert bounds["first_fundingTime_utc"] == "2019-09-10T08:00:00Z"
    assert bounds["last_fundingTime_utc"] == "2024-12-31T16:00:00Z"
    assert bounds["request_end_exclusive"] == "2025-01-01T00:00:00Z"
    assert payload["DUPLICATES"]["duplicate_fundingTime_count"] == 0
    assert payload["GAPS"]["missing_expected_8h_hour_floor_count"] == 0
    assert payload["STRICT_HISTORICAL_PUBLICATION_LATENCY"] == "UNPROVEN"
    assert payload["REPRODUCTION_FUNDINGTIME_ASSUMPTION"] == "ACCEPTABLE"
    assert payload["publication_latency_not_upgraded"] is True
    assert payload["fundingtime_not_legal_available_at"] is True
    assert payload["b2_06_is_not_market_03_authority"] is True
    assert payload["SPOT_SNAPSHOT_UNCHANGED"] is True
    assert payload["PREREG_UNCHANGED"] is True
    assert payload["MARKET_03_STRATEGY_EXECUTED"] is False
    assert payload["MARKET_03_OUTCOMES_INSPECTED"] is False
    assert payload["MARKET_03_PARAMETER_SEARCH"] is False
    assert payload["MARKET_03_ARMED"] is False
    assert payload["CANONICAL_EXECUTIONS_AUTHORIZED"] == 0
    assert payload["CANONICAL_EXECUTIONS_CONSUMED"] == 0
    assert payload["PROTECTED_OOS_TOUCHED"] is False
    assert payload["pre_snapshot"]["head"] == PRE_SNAPSHOT_HEAD
    assert payload["pre_snapshot"]["tree"] == PRE_SNAPSHOT_TREE
    assert _sha256(JS) == EXPECTED_REPORT_JSON_SHA256
    text = MD.read_text(encoding="utf-8")
    assert "A. FUNDING_SNAPSHOT_READY" in text
    assert EXPECTED_SNAPSHOT in text
    assert EXPECTED_SOURCE_SHA256 in text
    assert "MARKET_03_STRATEGY_EXECUTED            = NO" in text
    assert "PROTECTED_OOS_TOUCHED                  = NO" in text
    assert "does **not** begin implementation" in text


def test_snapshot_identity_hashes_and_construction_code():
    snapshot = json.loads(SNAP.read_text(encoding="utf-8"))
    assert snapshot["snapshot_id"] == EXPECTED_SNAPSHOT
    payload = snapshot["identity_payload"]
    assert payload["dataset_id"] == DATASET_ID
    assert payload["source_sha256"] == EXPECTED_SOURCE_SHA256
    assert payload["canonical_funding_sha256"] == EXPECTED_SOURCE_SHA256
    assert payload["source_size_bytes"] == EXPECTED_SOURCE_SIZE
    assert payload["canonical_row_count"] == 5819
    assert payload["b2_06_is_not_market_03_authority"] is True
    assert payload["market_03_arm_bound"] is False
    assert payload["protected_oos_excluded"] is True
    assert payload["strict_historical_publication_latency"] == (
        STRICT_HISTORICAL_PUBLICATION_LATENCY
    )
    assert payload["reproduction_fundingtime_assumption"] == "ACCEPTABLE"
    assert payload["construction_code_sha256"] == EXPECTED_CODE
    for rel, digest in EXPECTED_CODE.items():
        assert _sha256(REPO / rel) == digest
    recomputed = sha256_of_canonical_identity_payload(payload)
    assert recomputed == EXPECTED_SNAPSHOT
    rebuilt = snapshot_from_payload(payload)
    assert rebuilt["snapshot_id"] == EXPECTED_SNAPSHOT
    for name, digest in EXPECTED_IDENTITY_HASHES.items():
        assert _sha256(EVIDENCE / name) == digest
    quality = json.loads(QUALITY.read_text(encoding="utf-8"))
    assert quality["row_count"] == 5819
    assert quality["duplicate_fundingTime_count"] == 0
    assert quality["missing_expected_8h_hour_floor_count"] == 0
    assert quality["protected_oos_used_for_science"] is False
    assert quality["strategy_quantities_computed"] is False
    assert quality["b2_06_used_as_authority"] is False
    assert quality["fidelity"]["scientifically_relevant_values_unaltered"] is True
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert ledger["source"]["sha256"] == EXPECTED_SOURCE_SHA256
    assert ledger["normalized"]["identity_copy_of_source"] is True
    manifest = MANIFEST.read_text(encoding="utf-8")
    assert EXPECTED_SNAPSHOT in manifest
    assert "research_authorized: false" in manifest
    assert "B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0" in manifest


def test_no_strategy_quantities_in_funding_snapshot_json():
    payload = _payload()
    blob = json.dumps(payload).lower()
    for token in FORBIDDEN_STRATEGY_TOKENS:
        assert token not in blob
    assert_no_strategy_quantities(payload.keys())


def test_parse_audit_fidelity_and_refuse_oos_and_b2_06():
    text = (
        '{"fundingRate":"0.00010000","fundingTime":1568102400000,"symbol":"BTCUSDT"}\n'
        '{"fundingRate":"0.00020000","fundingTime":1568131200000,"symbol":"BTCUSDT"}\n'
    )
    rows = parse_rest_funding_jsonl(text)
    assert len(rows) == 2
    assert rows[0].funding_rate == "0.00010000"
    canonical = canonical_jsonl_bytes(rows)
    fidelity = prove_source_fidelity(rows, canonical)
    assert fidelity["scientifically_relevant_values_unaltered"] is True
    audit = audit_funding_rows(rows)
    assert audit["duplicate_fundingTime_count"] == 0
    assert audit["missing_expected_8h_hour_floor_count"] == 0
    oos = (
        '{"fundingRate":"0.00010000","fundingTime":1735689600000,"symbol":"BTCUSDT"}\n'
    )
    with pytest.raises(Market03FundingSnapshotError):
        parse_rest_funding_jsonl(oos)
    with pytest.raises(Market03FundingSnapshotError):
        refuse_b2_06_as_authority("B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0")


def test_local_source_jsonl_matches_frozen_identity_when_present():
    path = REPO / SOURCE_RELATIVE_PATH
    if not path.is_file():
        pytest.skip("acquired REST JSONL not retained in this checkout")
    assert path.stat().st_size == EXPECTED_SOURCE_SIZE
    assert _sha256(path) == EXPECTED_SOURCE_SHA256
