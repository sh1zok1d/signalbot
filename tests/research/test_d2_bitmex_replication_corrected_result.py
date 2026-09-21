"""Stored-outcome tests for the corrected D2 BitMEX replication RESULT.

Does not execute a second scientific corrected BitMEX run.
Does not open Binance 2025/2026.
Does not create MARKET-07.
"""

from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

import pytest

from scripts.research.d2_bitmex_replication_corrected_one_shot import (
    AMENDMENT_JSON_REL,
    CLASS_CORRECTED_INVALID,
    CORRECTED_CONSTRUCTED_N,
    CORRECTED_ELIGIBLE_N,
    CORRECTED_FIRST_T,
    CORRECTED_LAST_T,
    CORRECTED_WARMUP_N,
    CORRECTED_YEAR_ELIGIBLE_N,
    EXPECTED_DROPPED,
    FROZEN_ADJUDICATION_SHA256,
    FROZEN_AMENDMENT_SHA256,
    FROZEN_IMPLEMENTATION_SHA256,
    FROZEN_PREREG_SHA256,
    FROZEN_SOURCE_AUTHORITY_SHA256,
    NEW_RUN_IDENTITY,
    ORIGINAL_INVALID_RESULT_PAYLOAD_SHA256,
    ORIGINAL_INVALID_RUN_IDENTITY,
    ORIGINAL_RESULT_JSON_REL,
    ORCHESTRATION_REL,
    PERMIT_REL,
    RESULT_JSON_REL,
    RESULT_MD_REL,
    execute_corrected_one_shot,
    verify_frozen_authorities,
)
from scripts.research.d2_bitmex_replication_evaluator import (
    CLASS_NOT_SUPPORTED,
    CLASS_SUPPORTED,
    FROZEN_CANONICAL_GZ_SHA256,
    FROZEN_CANONICAL_JSONL_SHA256,
    N_REPLICATES,
    REPLICATION_RANDOM_SEED,
    classify_replication,
    practical_gate,
    statistical_gate,
    year_matched_control_masks,
)
from scripts.research.d2_bitmex_replication_prereg import JSON_REL, file_sha256
from scripts.research.market_06_result_persistence import result_payload_sha256

REPO = Path(__file__).resolve().parents[2]
PERMIT_COMMIT = "14e9c9dfbfd6bdb989ef592b891aab1eb963f6f3"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def _result() -> dict:
    return json.loads((REPO / RESULT_JSON_REL).read_text(encoding="utf-8"))


def _original() -> dict:
    return json.loads((REPO / ORIGINAL_RESULT_JSON_REL).read_text(encoding="utf-8"))


def test_original_invalid_result_and_prereg_bytes_unchanged() -> None:
    original_json = REPO / ORIGINAL_RESULT_JSON_REL
    original_md = REPO / "docs/research/D2_BITMEX_REPLICATION_RESULT.md"
    prereg = REPO / JSON_REL
    for rel in (
        ORIGINAL_RESULT_JSON_REL,
        "docs/research/D2_BITMEX_REPLICATION_RESULT.md",
        JSON_REL,
        "scripts/research/d2_bitmex_replication_evaluator.py",
        "docs/research/D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION.json",
        "docs/research/D2_BITMEX_REPLICATION_PREREG_AMENDMENT_V1.json",
    ):
        frozen = subprocess.check_output(["git", "show", f"{PERMIT_COMMIT}:{rel}"], cwd=REPO)
        assert (REPO / rel).read_bytes() == frozen
    original = _original()
    hashed = {k: v for k, v in original.items() if k != "RESULT_PAYLOAD_SHA256"}
    assert original["RUN_IDENTITY"] == ORIGINAL_INVALID_RUN_IDENTITY
    assert original["RESULT_PAYLOAD_SHA256"] == ORIGINAL_INVALID_RESULT_PAYLOAD_SHA256
    assert result_payload_sha256(hashed) == ORIGINAL_INVALID_RESULT_PAYLOAD_SHA256
    assert original["CLASSIFICATION"] == "D2_BITMEX_REPLICATION_INVALID"
    assert original["D2_BITMEX_OUTCOME_COMPUTED"] is False
    assert file_sha256(prereg) == FROZEN_PREREG_SHA256
    del original_json, original_md


def test_adjudication_amendment_and_orchestration_hashes_bound() -> None:
    result = _result()
    permit = json.loads((REPO / PERMIT_REL).read_text(encoding="utf-8"))
    assert file_sha256(REPO / "docs/research/D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION.json") == (
        FROZEN_ADJUDICATION_SHA256
    )
    assert file_sha256(REPO / AMENDMENT_JSON_REL) == FROZEN_AMENDMENT_SHA256
    orch_sha = file_sha256(REPO / ORCHESTRATION_REL)
    assert permit["ADJUDICATION_JSON_SHA256"] == FROZEN_ADJUDICATION_SHA256
    assert permit["PREREG_AMENDMENT_JSON_SHA256"] == FROZEN_AMENDMENT_SHA256
    assert permit["ORIGINAL_PREREG_JSON_SHA256"] == FROZEN_PREREG_SHA256
    assert permit["SOURCE_AUTHORITY_SHA256"] == FROZEN_SOURCE_AUTHORITY_SHA256
    assert permit["CORRECTED_ORCHESTRATION_SHA256"] == orch_sha
    assert result["ADJUDICATION_JSON_SHA256"] == FROZEN_ADJUDICATION_SHA256
    assert result["PREREG_AMENDMENT_JSON_SHA256"] == FROZEN_AMENDMENT_SHA256
    assert result["ORIGINAL_PREREG_JSON_SHA256"] == FROZEN_PREREG_SHA256
    assert result["SOURCE_AUTHORITY_SHA256"] == FROZEN_SOURCE_AUTHORITY_SHA256
    assert result["CORRECTED_ORCHESTRATION_SHA256"] == orch_sha
    assert result["FINAL_IMPLEMENTATION_SHA256"] == FROZEN_IMPLEMENTATION_SHA256
    assert (
        file_sha256(REPO / "scripts/research/d2_bitmex_replication_evaluator.py")
        == FROZEN_IMPLEMENTATION_SHA256
    )
    assert result["BITMEX_CANONICAL_SHA256"] == FROZEN_CANONICAL_JSONL_SHA256
    assert result["BITMEX_CANONICAL_GZ_SHA256"] == FROZEN_CANONICAL_GZ_SHA256
    assert verify_frozen_authorities(REPO) == []


def test_corrected_sample_identity_and_two_zero_return_exclusions() -> None:
    result = _result()
    sample = result["SAMPLE_IDENTITY"]
    assert sample["TIMESTAMP_CENSUS_N"] == 1069
    assert sample["CONSTRUCTED_N"] == CORRECTED_CONSTRUCTED_N == 1317
    assert sample["WARMUP_N"] == CORRECTED_WARMUP_N == 250
    assert sample["ELIGIBLE_N"] == CORRECTED_ELIGIBLE_N == 1067
    assert sample["YEAR_ELIGIBLE_N"] == CORRECTED_YEAR_ELIGIBLE_N == {
        "2017": 341,
        "2018": 363,
        "2019": 363,
    }
    assert sample["FIRST_T"] == CORRECTED_FIRST_T == "2017-01-24T00:05:00Z"
    assert sample["LAST_T"] == CORRECTED_LAST_T == "2019-12-30T00:05:00Z"
    assert sample["TRAILING_HISTORY_AUTHORITY"] == "VALID_CONSTRUCTED_ROWS"
    dropped = sample["DROPPED_ROWS"]
    assert dropped == [
        {
            "DROP_TIMESTAMP": ts,
            "DROP_YEAR": int(ts[:4]),
            "EXACT_INELIGIBILITY_REASON": reason,
        }
        for ts, reason in EXPECTED_DROPPED
    ]
    assert dropped[0]["DROP_TIMESTAMP"] == "2018-03-17T00:05:00Z"
    assert dropped[1]["DROP_TIMESTAMP"] == "2019-02-10T00:05:00Z"
    assert dropped[0]["EXACT_INELIGIBILITY_REASON"] == "BTC_RET_24H_EQ_0"
    assert dropped[1]["EXACT_INELIGIBILITY_REASON"] == "BTC_RET_24H_EQ_0"


def test_same_frozen_seed_and_year_matched_controls() -> None:
    result = _result()
    permit = json.loads((REPO / PERMIT_REL).read_text(encoding="utf-8"))
    assert result["RANDOM_SEED"] == REPLICATION_RANDOM_SEED == 20260921125
    assert permit["RANDOM_SEED"] == REPLICATION_RANDOM_SEED
    assert result["N_CONTROLS"] == N_REPLICATES == 10000
    assert permit["N_CONTROLS"] == N_REPLICATES
    primary = result["PRIMARY_METRICS"]
    assert primary["K_2017"] + primary["K_2018"] + primary["K_2019"] == primary["ABSTAIN_COUNT_TOTAL"]
    source = inspect.getsource(year_matched_control_masks)
    assert "for year, idx in year_indices.items()" in source
    assert "pooled" not in source.lower() or "pooled_k_is_forbidden" in source
    assert "rng.choice(idx, size=count, replace=False)" in source


def test_no_controls_before_sample_gate() -> None:
    source = inspect.getsource(execute_corrected_one_shot)
    reconstruct_at = source.find("reconstruct_corrected_sample")
    evaluate_at = source.find("evaluate_constructed_rows")
    gate_at = source.find("if sample_blockers or rows is None")
    assert reconstruct_at != -1
    assert evaluate_at != -1
    assert gate_at != -1
    assert reconstruct_at < gate_at < evaluate_at
    original = _original()
    assert original["PRIMARY_METRICS"]["MU_CONTROL_MEAN"] is None
    assert original["PRIMARY_METRICS"]["MC_P"] is None
    assert original["D2_BITMEX_OUTCOME_COMPUTED"] is False
    assert original["CLASSIFICATION"] == "D2_BITMEX_REPLICATION_INVALID"


def test_exact_gates_and_classification_from_stored_metrics() -> None:
    result = _result()
    primary = result["PRIMARY_METRICS"]
    gates = result["GATES"]
    mu_rule = float(primary["MU_RULE"])
    control_p95 = float(primary["CONTROL_P95"])
    delta = float(primary["DELTA"])
    uncond = float(primary["UNCONDITIONAL_MEAN"])
    assert statistical_gate(mu_rule, control_p95) is True
    assert practical_gate(delta, uncond) is True
    assert gates["STATISTICAL_GATE"] is True
    assert gates["PRACTICAL_GATE"] is True
    assert gates["PRIMARY_PASS"] is True
    assert mu_rule > control_p95
    assert delta >= 0.20 * uncond
    assert abs(delta - (mu_rule - float(primary["MU_CONTROL_MEAN"]))) < 1e-15
    assert abs(float(primary["RELATIVE_DELTA"]) - (delta / uncond)) < 1e-15
    assert classify_replication(
        integrity_invalid=False,
        statistical=True,
        practical=True,
    ) == CLASS_SUPPORTED
    assert result["CLASSIFICATION"] == CLASS_SUPPORTED
    assert result["CLASSIFICATION"] != CLASS_CORRECTED_INVALID
    assert result["CLASSIFICATION"] != CLASS_NOT_SUPPORTED
    assert result["CLASSIFICATION"] != "D2_BITMEX_REPLICATION_INVALID"
    assert result["EVIDENCE_LABEL"] == (
        "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION_SUPPORTED"
    )
    assert result["NOT_EXACT_BINANCE_CONFIRMATION"] is True
    assert result["NOT_PROVEN_ALPHA"] is True
    assert result["NOT_VALIDATED_TRADING_EDGE"] is True
    yearly = result["YEARLY_DIAGNOSTICS"]
    assert result["YEARLY_BREAKDOWN_DIAGNOSTIC_ONLY"] is True
    assert result["NO_YEARLY_RESCUE"] is True
    assert yearly["2017"]["ELIGIBLE_N"] == 341
    assert yearly["2018"]["ELIGIBLE_N"] == 363
    assert yearly["2019"]["ELIGIBLE_N"] == 363


def test_corrected_payload_sha_and_two_commit_lifecycle() -> None:
    result = _result()
    hashed = {k: v for k, v in result.items() if k != "CORRECTED_RESULT_PAYLOAD_SHA256"}
    assert result["CORRECTED_RESULT_PAYLOAD_SHA256"] == result_payload_sha256(hashed)
    assert result["RUN_IDENTITY"] == NEW_RUN_IDENTITY
    assert result["CORRECTED_PERMIT_COMMIT"] == PERMIT_COMMIT
    assert PERMIT_COMMIT in _git("rev-list", "HEAD")
    missing = subprocess.run(
        ["git", "cat-file", "-e", f"{PERMIT_COMMIT}:{RESULT_JSON_REL}"],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    assert missing.returncode != 0
    assert (REPO / RESULT_MD_REL).is_file()
    md = (REPO / RESULT_MD_REL).read_text(encoding="utf-8")
    assert result["CORRECTED_RESULT_PAYLOAD_SHA256"] in md
    assert result["CLASSIFICATION"] in md
    assert "EXACT_BINANCE_CONFIRMATION" in md
    assert result["ORIGINAL_RUN_CLASSIFICATION"] == "D2_BITMEX_REPLICATION_INVALID"
    assert result["ORIGINAL_PRIMARY_OUTCOME_COMPUTED"] is False


def test_program_flags_sealed_no_binance_no_market_07() -> None:
    result = _result()
    permit = json.loads((REPO / PERMIT_REL).read_text(encoding="utf-8"))
    assert result["RERUN_AUTHORIZED"] is False
    assert permit["RERUN_AUTHORIZED"] is False
    assert result["PROTECTED_2025_OPENED"] is False
    assert result["PROTECTED_2026_OPENED"] is False
    assert result["2025_OPEN_AUTHORIZED"] is False
    assert result["2026_OPEN_AUTHORIZED"] is False
    assert result["MARKET_07_CREATED"] is False
    assert permit["MARKET_07_CREATED"] is False
    assert result["ONE_SHOT"] is True
    assert result["NEXT_UNIT"] == "PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED"
    assert result["D2_DISCOVERY_STATUS"] == "PROMISING_PROTOTYPE"
    assert (
        result["D2_REPLICATION_STATUS"]
        == "SUPPORTED_ON_INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_SURFACE"
    )
    market_07 = list((REPO / "docs").rglob("*MARKET_07*")) + list(
        (REPO / "docs").rglob("*MARKET-07*")
    )
    assert market_07 == []
    orch_src = inspect.getsource(execute_corrected_one_shot)
    assert "2025" not in orch_src or "PROTECTED_2025_OPENED" in orch_src
    assert "binance" not in orch_src.lower() or "refuse_binance_protected_path" in orch_src


def test_second_corrected_run_refused_without_science() -> None:
    with pytest.raises(RuntimeError, match="CORRECTED_RESULT_ALREADY_EXISTS_RERUN_FORBIDDEN"):
        execute_corrected_one_shot(REPO)
