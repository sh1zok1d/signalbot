"""Integrity-adjudication tests for the D2 BitMEX INVALID sample identity.

Does not compute D2 effect metrics. Does not open Binance 2025/2026.
"""

from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

import pytest

from scripts.research.d2_bitmex_replication_evaluator import compute_run_identity
from scripts.research.d2_bitmex_replication_integrity_adjudication import (
    ADJUDICATION_CLASS,
    ADJUDICATION_JSON_REL,
    AMENDMENT_JSON_REL,
    FROZEN_IMPLEMENTATION_SHA256,
    ORIGINAL_PREREG_SHA256,
    ORIGINAL_RESULT_COMMIT,
    ORIGINAL_RESULT_PAYLOAD_SHA256,
    ORIGINAL_RUN_IDENTITY,
    PREREG_JSON_REL,
    RESULT_JSON_REL,
)
from scripts.research.d2_bitmex_replication_integrity_diagnostic import (
    diagnose_scientific_eligibility,
    dropped_timestamp_complete_decisions,
)
from scripts.research.d2_bitmex_replication_prereg import file_sha256
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_result_persistence import result_payload_sha256

REPO = Path(__file__).resolve().parents[2]
RESULT_COMMIT = ORIGINAL_RESULT_COMMIT


def _git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=REPO)


def _adjudication() -> dict:
    return json.loads((REPO / ADJUDICATION_JSON_REL).read_text(encoding="utf-8"))


def test_exactly_two_deterministic_drops_with_kernel_reasons() -> None:
    diag = dropped_timestamp_complete_decisions(REPO)
    assert diag["TIMESTAMP_COMPLETE_N"] == 1319
    assert len(diag["DROPPED"]) == 2
    assert diag["DROPPED"][0] == {
        "DROP_TIMESTAMP": "2018-03-17T00:05:00Z",
        "DROP_YEAR": 2018,
        "EXACT_INELIGIBILITY_REASON": "BTC_RET_24H_EQ_0",
    }
    assert diag["DROPPED"][1] == {
        "DROP_TIMESTAMP": "2019-02-10T00:05:00Z",
        "DROP_YEAR": 2019,
        "EXACT_INELIGIBILITY_REASON": "BTC_RET_24H_EQ_0",
    }
    assert diag["SCIENTIFIC_ELIGIBLE_N"] == 1067
    assert diag["SCIENTIFIC_CONSTRUCTED_N"] == 1317
    assert diag["SCIENTIFIC_WARMUP_N"] == 250
    assert diag["SCIENTIFIC_YEAR_ELIGIBLE_N"] == {"2017": 341, "2018": 363, "2019": 363}
    assert diag["SCIENTIFIC_FIRST_T"] == "2017-01-24T00:05:00Z"
    assert diag["SCIENTIFIC_LAST_T"] == "2019-12-30T00:05:00Z"
    assert diag["ARITHMETIC_MAE_COMPUTED"] is False
    assert diag["PRIMARY_OUTCOME_COMPUTED"] is False


def test_diagnostic_does_not_compute_arithmetic_mae(monkeypatch: pytest.MonkeyPatch) -> None:
    source = inspect.getsource(diagnose_scientific_eligibility)
    assert "arithmetic_mae(" not in source
    dropped_src = inspect.getsource(dropped_timestamp_complete_decisions)
    assert "evaluate_constructed_rows" not in dropped_src
    assert "arithmetic_mae(" not in dropped_src

    def _boom(*_args, **_kwargs):
        raise AssertionError("ARITHMETIC_MAE_CALLED")

    monkeypatch.setattr(
        "scripts.research.market_06_cross_venue_dislocation_evaluator.arithmetic_mae",
        _boom,
    )
    monkeypatch.setattr(
        "scripts.research.discovery_sprint_01.common.arithmetic_mae",
        _boom,
    )
    dropped_timestamp_complete_decisions(REPO)


def test_original_invalid_result_and_prereg_bytes_unchanged() -> None:
    current_result = (REPO / RESULT_JSON_REL).read_bytes()
    frozen_result = _git("show", f"{RESULT_COMMIT}:{RESULT_JSON_REL}")
    assert current_result == frozen_result
    current_prereg = (REPO / PREREG_JSON_REL).read_bytes()
    frozen_prereg = _git("show", f"{RESULT_COMMIT}:{PREREG_JSON_REL}")
    assert current_prereg == frozen_prereg
    result = json.loads(current_result)
    assert result["CLASSIFICATION"] == "D2_BITMEX_REPLICATION_INVALID"
    assert result["RUN_IDENTITY"] == ORIGINAL_RUN_IDENTITY
    assert result["RESULT_PAYLOAD_SHA256"] == ORIGINAL_RESULT_PAYLOAD_SHA256
    assert result["D2_BITMEX_OUTCOME_COMPUTED"] is False
    assert result["PRIMARY_METRICS"]["MU_RULE"] is None
    assert result["PRIMARY_METRICS"]["MU_CONTROL_MEAN"] is None
    assert result["PRIMARY_METRICS"]["MC_P"] is None
    assert file_sha256(REPO / PREREG_JSON_REL) == ORIGINAL_PREREG_SHA256


def test_original_random_controls_never_computed() -> None:
    result = json.loads((REPO / RESULT_JSON_REL).read_text(encoding="utf-8"))
    adj = _adjudication()
    assert result["PRIMARY_METRICS"]["MU_CONTROL_MEAN"] is None
    assert result["PRIMARY_METRICS"]["CONTROL_P95"] is None
    assert adj["ORIGINAL_RANDOM_CONTROLS_COMPUTED"] is False
    assert adj["ORIGINAL_PRIMARY_OUTCOME_COMPUTED"] is False
    assert adj["ORIGINAL_RERUN_AUTHORIZED"] is False


def test_trailing_250_authority_matches_original_d2_code() -> None:
    source = inspect.getsource(C.rv_abstention_mask).replace(" ", "")
    assert "rvs[i-RV_TRAILING_WINDOW:i]" in source
    build = inspect.getsource(C.build_rows)
    assert "construct_discovery_row" in build
    assert "if row is not None" in build
    d2 = inspect.getsource(
        __import__(
            "scripts.research.discovery_sprint_01.d2_abstention_tail_risk",
            fromlist=["evaluate_rule_1"],
        ).evaluate_rule_1
    )
    assert "rv_abstention_mask" in d2
    adj = _adjudication()
    assert adj["TRAILING_HISTORY_AUTHORITY"] == "VALID_CONSTRUCTED_ROWS"


def test_adjudication_class_a_and_new_run_identity() -> None:
    adj = _adjudication()
    assert adj["ADJUDICATION_CLASS"] == ADJUDICATION_CLASS
    assert adj["CORRECTED_EXECUTION_SCIENTIFICALLY_PERMISSIBLE"] is True
    assert adj["EXECUTION_AUTHORIZED"] is False
    assert adj["NEW_RUN_IDENTITY"] != ORIGINAL_RUN_IDENTITY
    assert adj["NEW_RUN_IDENTITY"] == compute_run_identity(adj["NEW_RUN_IDENTITY_INPUTS"])
    hashed = {k: v for k, v in adj.items() if k != "ADJUDICATION_PAYLOAD_SHA256"}
    assert adj["ADJUDICATION_PAYLOAD_SHA256"] == result_payload_sha256(hashed)
    amendment = json.loads((REPO / AMENDMENT_JSON_REL).read_text(encoding="utf-8"))
    assert amendment["ORIGINAL_EXPECTED_N"] == 1069
    assert amendment["CORRECTED_EXPECTED_N"] == 1067
    assert amendment["SCIENTIFIC_RULE_CHANGED"] is False
    assert amendment["TARGET_CHANGED"] is False
    assert amendment["THRESHOLD_CHANGED"] is False
    assert amendment["COMPARATOR_CHANGED"] is False
    assert amendment["DATA_CHANGED"] is False
    assert amendment["REPLICATION_RANDOM_SEED"] == 20260921125
    assert (
        file_sha256(REPO / "scripts/research/d2_bitmex_replication_evaluator.py")
        == FROZEN_IMPLEMENTATION_SHA256
    )


def test_no_binance_protected_open() -> None:
    from scripts.research.d2_confirmation_feasibility_and_design import (
        refuse_protected_price_path,
    )
    from scripts.research.discovery_sprint_01.common import ProtectedYearRefused

    with pytest.raises(ProtectedYearRefused):
        refuse_protected_price_path(
            REPO
            / "artifacts/research_data/CORE_BTC_BINANCE_V0/canonical/1m/monthly/2025-01.parquet"
        )
    adj = _adjudication()
    assert adj["PROTECTED_2025_OPENED"] is False
    assert adj["PROTECTED_2026_OPENED"] is False
    assert adj["MARKET_07_CREATED"] is False
    assert adj["NEXT_UNIT"] == "D2_BITMEX_REPLICATION_CORRECTED_EXECUTION_PERMIT"
    assert adj["D2_DISCOVERY_STATUS"] == "PROMISING_PROTOTYPE"
    assert adj["SUPPORTED_MARKED"] is False
    assert adj["NOT_SUPPORTED_MARKED"] is False
