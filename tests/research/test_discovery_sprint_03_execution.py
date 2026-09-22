"""Execution-runner contract tests. Do not recompute real D9/D10/D11 outcomes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.research.discovery_sprint_03 import common as C
from scripts.research.discovery_sprint_03 import d9 as D9
from scripts.research.discovery_sprint_03 import d10 as D10
from scripts.research.discovery_sprint_03 import d11 as D11
from scripts.research.discovery_sprint_03 import execute_scientific as X

REPO = Path(__file__).resolve().parents[2]


def test_import_does_not_authorize_or_read_market_data():
    assert C.EXECUTION_AUTHORIZED is False
    assert X.EXECUTION_ROOT == "e2852f57ee946ec8380f09fa4cf834579c40f872"
    assert X.EXPECTED_TREE == "8805ee7d39b29c267589e7f9400384ebdb1f66ca"


def test_execute_refuses_without_authorization():
    with pytest.raises(C.RealScientificOutcomeForbidden):
        X.execute(repo=REPO, authorize=False, write=False)


def test_identity_only_verifies_execution_root_hashes():
    assert X.main(["--identity-only"]) == 0
    hashes = X.verify_implementation_identity(REPO)
    assert hashes == X.IMPLEMENTATION_HASHES_AT_ROOT


def test_hash_mismatch_fails_closed(tmp_path, monkeypatch):
    target = tmp_path / "scripts/research/discovery_sprint_03"
    target.mkdir(parents=True)
    (tmp_path / "docs/research").mkdir(parents=True)
    for rel, digest in X.IMPLEMENTATION_HASHES_AT_ROOT.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"not-the-frozen-bytes")
    with pytest.raises(X.ExecutionAbortedPreResult, match="IMPLEMENTATION_HASH_MISMATCH"):
        X.verify_implementation_identity(tmp_path)


def test_protected_paths_fail_closed():
    with pytest.raises(C.ProtectedYearRefused):
        C.assert_openable(Path("canonical/1m/monthly/2025-01.parquet"))
    with pytest.raises(C.ProtectedYearRefused):
        C.assert_openable(Path("canonical/1m/monthly/2026-12.parquet"))


def test_pure_supplied_arrays_are_deterministic():
    event = [0.70 + 0.01 * (i % 10) for i in range(61)]
    control = [0.48 + 0.01 * (i % 5) for i in range(61)]
    yearly = {"2022": event[:21], "2023": event[21:41], "2024": event[41:]}
    cells_e = {"A": event[:31], "B": event[31:]}
    cells_c = {"A": control[:31], "B": control[31:]}
    support = {"SUPPORT_PASS": True, "IDENTITY_OK": True}
    a = D9.evaluate_d9_scientific(
        event, control, yearly, support=support, event_by_cell=cells_e, control_by_cell=cells_c
    )
    b = D9.evaluate_d9_scientific(
        event, control, yearly, support=support, event_by_cell=cells_e, control_by_cell=cells_c
    )
    assert a == b
    assert a["CLASSIFICATION"] in {
        "PROMISING_PROTOTYPE",
        "NO_USEFUL_STRUCTURE",
        "INCONCLUSIVE_DISCOVERY",
        "INVALID_DISCOVERY",
    }
    d10_a = D10.evaluate_d10_scientific(
        [0.002] * 30,
        [0.0] * 30,
        {"2022": [0.002] * 10, "2023": [0.002] * 10, "2024": [0.002] * 10},
        {"2022": [0.0] * 10, "2023": [0.0] * 10, "2024": [0.0] * 10},
        support=support,
        event_by_cell={"A": [0.002] * 15, "B": [0.002] * 15},
        control_by_cell={"A": [0.0] * 15, "B": [0.0] * 15},
    )
    d10_b = D10.evaluate_d10_scientific(
        [0.002] * 30,
        [0.0] * 30,
        {"2022": [0.002] * 10, "2023": [0.002] * 10, "2024": [0.002] * 10},
        {"2022": [0.0] * 10, "2023": [0.0] * 10, "2024": [0.0] * 10},
        support=support,
        event_by_cell={"A": [0.002] * 15, "B": [0.002] * 15},
        control_by_cell={"A": [0.0] * 15, "B": [0.0] * 15},
    )
    assert d10_a == d10_b
    d11_a = D11.evaluate_d11_scientific(
        [0.02] * 24,
        [0.01] * 80,
        {"2022": [0.02] * 8, "2023": [0.02] * 8, "2024": [0.02] * 8},
        {"2022": [0.01] * 20, "2023": [0.01] * 30, "2024": [0.01] * 30},
        support=support,
    )
    d11_b = D11.evaluate_d11_scientific(
        [0.02] * 24,
        [0.01] * 80,
        {"2022": [0.02] * 8, "2023": [0.02] * 8, "2024": [0.02] * 8},
        {"2022": [0.01] * 20, "2023": [0.01] * 30, "2024": [0.01] * 30},
        support=support,
    )
    assert d11_a == d11_b


def test_classification_follows_frozen_gates_exactly():
    for fn in (D9.classify_d9_from_summary, D10.classify_d10_from_summary, D11.classify_d11_from_summary):
        assert fn({"IDENTITY_OK": False, "SUPPORT_PASS": False}) == "INVALID_DISCOVERY"
        assert fn({"IDENTITY_OK": True, "SUPPORT_PASS": False}) == "INCONCLUSIVE_DISCOVERY"
        assert (
            fn(
                {
                    "IDENTITY_OK": True,
                    "SUPPORT_PASS": True,
                    "STATISTICAL_GATE": True,
                    "PRACTICAL_GATE": True,
                    "TEMPORAL_GATE": True,
                }
            )
            == "PROMISING_PROTOTYPE"
        )
        assert (
            fn(
                {
                    "IDENTITY_OK": True,
                    "SUPPORT_PASS": True,
                    "STATISTICAL_GATE": True,
                    "PRACTICAL_GATE": True,
                    "TEMPORAL_GATE": False,
                }
            )
            == "NO_USEFUL_STRUCTURE"
        )


def test_result_schema_when_present():
    path = REPO / "docs/research/discovery_results/D9_DISCOVERY_RESULT.json"
    assert path.is_file()
    expected = {
        "D9": "NO_USEFUL_STRUCTURE",
        "D10": "NO_USEFUL_STRUCTURE",
        "D11": "PROMISING_PROTOTYPE",
    }
    for disc in ("D9", "D10", "D11"):
        payload = json.loads(
            (REPO / f"docs/research/discovery_results/{disc}_DISCOVERY_RESULT.json").read_text(
                encoding="utf-8"
            )
        )
        assert payload["EXECUTION_ROOT"] == X.EXECUTION_ROOT
        assert payload["IMPLEMENTATION_HASHES"] == X.IMPLEMENTATION_HASHES_AT_ROOT
        assert payload["PROTECTED_2025_OPENED"] is False
        assert payload["PROTECTED_2026_OPENED"] is False
        assert payload["MARKET_07_CREATED"] is False
        assert payload["D7_RERUN_PERFORMED"] is False
        assert payload["D8_EXECUTED"] is False
        assert payload["CLASSIFICATION"] == expected[disc]
        assert payload["RESULT_PAYLOAD_SHA256"] == X.payload_sha256(payload)
        if disc == "D9":
            assert payload["DATA_IDENTITY"]["SNAPSHOT_ID"] == C.M06_SNAPSHOT_ID
            assert payload["SCIENTIFIC_CLAIM_MAY_ESTABLISH"] == (
                "CONDITIONAL_VENUE_RESOLUTION_ATTRIBUTION"
            )
            assert payload["STATISTICAL_GATE"] is False
            assert payload["PRACTICAL_GATE"] is False
            assert payload["TEMPORAL_GATE"] is False
        if disc == "D10":
            assert payload["CORE_BTC_SNAPSHOT_ID"] == C.CORE_BTC_SNAPSHOT_ID
            assert payload["CORE_ETH_SNAPSHOT_ID"] == C.CORE_ETH_SNAPSHOT_ID
            assert payload["REGRESSION_SPECIFICATION"] == "NO_INTERCEPT_OLS"
            assert payload["STATISTICAL_GATE"] is False
            assert payload["PRACTICAL_GATE"] is False
        if disc == "D11":
            assert payload["CORE_BTC_SNAPSHOT_ID"] == C.CORE_BTC_SNAPSHOT_ID
            assert payload["EVENT_FAMILY"] == "SCHEDULED_FOMC_MONETARY_POLICY_ANNOUNCEMENTS"
            assert payload["DIRECTIONAL_SIGN_USED"] is False
            assert payload["STATISTICAL_GATE"] is True
            assert payload["PRACTICAL_GATE"] is True
            assert payload["TEMPORAL_GATE"] is True
    batch = json.loads((REPO / "docs/research/DISCOVERY_SPRINT_03_RESULT.json").read_text(encoding="utf-8"))
    assert batch["RESULT_PAYLOAD_SHA256"] == X.payload_sha256(batch)
    assert batch["SPRINT04_HYPOTHESES_SELECTED"] is False
    assert batch["INTERNAL_DISCOVERY_CARDS_EXECUTED"] == 8
    assert batch["INTERNAL_PROMISING_PROTOTYPES"] == 3
    assert batch["NEXT_UNIT"] == "DISCOVERY_SPRINT_03_POST_RESULT_PROGRAM_DECISION"
