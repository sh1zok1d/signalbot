"""Stored-outcome tests for the D2 BitMEX one-shot RESULT.

Does not execute a second scientific BitMEX run.
Does not open Binance 2025/2026.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.research.d2_bitmex_replication_evaluator import (
    CLASS_INVALID,
    EXECUTION_PERMIT_REL as EVALUATOR_STUB_PERMIT_REL,
    FROZEN_CANONICAL_GZ_SHA256,
    FROZEN_CANONICAL_JSONL_SHA256,
)
from scripts.research.d2_bitmex_replication_one_shot import (
    FROZEN_IMPLEMENTATION_SHA256,
    FROZEN_PREREG_SHA256,
    FROZEN_RUN_IDENTITY,
    FROZEN_SOURCE_AUTHORITY_SHA256,
    PERMIT_REL,
    RESULT_JSON_REL,
    RESULT_MD_REL,
)
from scripts.research.d2_bitmex_replication_prereg import file_sha256
from scripts.research.market_06_result_persistence import result_payload_sha256

REPO = Path(__file__).resolve().parents[2]
PERMIT_COMMIT = "d23f48b0c49d28dfbd0bf55047cb0e3d6e2cc0f2"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def _result() -> dict:
    return json.loads((REPO / RESULT_JSON_REL).read_text(encoding="utf-8"))


def test_result_run_identity_and_frozen_bytes() -> None:
    result = _result()
    assert result["RUN_IDENTITY"] == FROZEN_RUN_IDENTITY
    assert result["PREREG_ARTIFACT_SHA256"] == FROZEN_PREREG_SHA256
    assert result["FINAL_IMPLEMENTATION_SHA256"] == FROZEN_IMPLEMENTATION_SHA256
    assert result["BITMEX_CANONICAL_SHA256"] == FROZEN_CANONICAL_JSONL_SHA256
    assert result["BITMEX_CANONICAL_GZ_SHA256"] == FROZEN_CANONICAL_GZ_SHA256
    assert result["SOURCE_AUTHORITY_SHA256"] == FROZEN_SOURCE_AUTHORITY_SHA256
    assert (
        file_sha256(REPO / "scripts/research/d2_bitmex_replication_evaluator.py")
        == FROZEN_IMPLEMENTATION_SHA256
    )
    assert (
        file_sha256(REPO / "docs/research/D2_BITMEX_REPLICATION_PREREG.json")
        == FROZEN_PREREG_SHA256
    )


def test_permit_predates_outcome() -> None:
    result = _result()
    assert result["PERMIT_COMMIT"] == PERMIT_COMMIT
    assert PERMIT_COMMIT in _git("rev-list", "HEAD")
    permit_at_commit = _git("show", f"{PERMIT_COMMIT}:{PERMIT_REL}")
    permit = json.loads(permit_at_commit)
    assert permit["RUN_IDENTITY"] == FROZEN_RUN_IDENTITY
    assert permit["EXECUTION_AUTHORIZED"] is True
    assert permit["ONE_SHOT"] is True
    assert permit["RERUN_AUTHORIZED"] is False
    missing = subprocess.run(
        ["git", "cat-file", "-e", f"{PERMIT_COMMIT}:{RESULT_JSON_REL}"],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    assert missing.returncode != 0
    assert not (REPO / EVALUATOR_STUB_PERMIT_REL).is_file()


def test_sample_identity_gate_invalid_not_not_supported() -> None:
    result = _result()
    sample = result["SAMPLE_IDENTITY"]
    assert sample["YEAR_ELIGIBLE_N_CENSUS"] == {"2017": 341, "2018": 364, "2019": 364}
    assert sample["ELIGIBLE_N"] == 1067
    assert sample["YEAR_ELIGIBLE_N"] == {"2017": 341, "2018": 363, "2019": 363}
    assert sample["FIRST_T"] == "2017-01-24T00:05:00Z"
    assert sample["LAST_T"] == "2019-12-30T00:05:00Z"
    assert sample["KNOWN_GAP_NEVER_FILLED"] is True
    assert "ELIGIBLE_N:1067" in result["BLOCKER"]
    assert result["CLASSIFICATION"] == CLASS_INVALID
    assert result["CLASSIFICATION"] != "D2_BITMEX_REPLICATION_NOT_SUPPORTED"
    assert result["D2_BITMEX_OUTCOME_COMPUTED"] is False
    primary = result["PRIMARY_METRICS"]
    for key in (
        "MU_RULE",
        "MU_CONTROL_MEAN",
        "DELTA",
        "CONTROL_P95",
        "MC_P",
        "ABSTAIN_COUNT_TOTAL",
        "K_2017",
        "K_2018",
        "K_2019",
        "RELATIVE_DELTA",
        "UNCONDITIONAL_MEAN",
        "ABSTAIN_RATE",
    ):
        assert primary[key] is None
    assert result["GATES"]["STATISTICAL_GATE"] is False
    assert result["GATES"]["PRACTICAL_GATE"] is False
    assert result["GATES"]["PRIMARY_PASS"] is False


def test_ky_controls_not_computed_when_invalid() -> None:
    result = _result()
    primary = result["PRIMARY_METRICS"]
    assert primary["K_2017"] is None
    assert primary["K_2018"] is None
    assert primary["K_2019"] is None
    assert primary["ABSTAIN_COUNT_2017"] is None
    assert primary["ABSTAIN_COUNT_2018"] is None
    assert primary["ABSTAIN_COUNT_2019"] is None
    for year in ("2017", "2018", "2019"):
        body = result["YEARLY_DIAGNOSTICS"][year]
        assert body["K"] is None
        assert body["MU_RULE"] is None
        assert body["DELTA"] is None


def test_result_payload_sha256_matches_canonical_bytes() -> None:
    result = _result()
    hashed = {k: v for k, v in result.items() if k != "RESULT_PAYLOAD_SHA256"}
    assert result["RESULT_PAYLOAD_SHA256"] == result_payload_sha256(hashed)
    assert (REPO / RESULT_MD_REL).is_file()
    md = (REPO / RESULT_MD_REL).read_text(encoding="utf-8")
    assert result["RESULT_PAYLOAD_SHA256"] in md
    assert result["CLASSIFICATION"] in md


def test_program_flags_sealed() -> None:
    result = _result()
    assert result["RERUN_AUTHORIZED"] is False
    assert result["PROTECTED_2025_OPENED"] is False
    assert result["PROTECTED_2026_OPENED"] is False
    assert result["2025_OPEN_AUTHORIZED"] is False
    assert result["2026_OPEN_AUTHORIZED"] is False
    assert result["MARKET_07_CREATED"] is False
    assert result["ONE_SHOT"] is True
    assert result["NEXT_UNIT"] == "D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION"
    assert result["NOT_EXACT_BINANCE_CONFIRMATION"] is True
    assert result["D2_DISCOVERY_STATUS"] == "PROMISING_PROTOTYPE"
    binding = json.loads(
        (REPO / "docs/research_data/D2_BITMEX_REPLICATION_EXECUTION_BINDING.json").read_text(
            encoding="utf-8"
        )
    )
    assert binding["CLASSIFICATION_ASSIGNED"] == CLASS_INVALID
    assert binding["RERUN_AUTHORIZED"] is False
    assert binding["PERMIT_COMMIT"] == PERMIT_COMMIT
    review = json.loads(
        (REPO / "docs/research/D2_BITMEX_REPLICATION_IMPLEMENTATION_REVIEW.json").read_text(
            encoding="utf-8"
        )
    )
    assert review["CLASSIFICATION_ASSIGNED"] is None
    assert review["D2_BITMEX_OUTCOME_COMPUTED"] is False
    assert review["EXECUTION_AUTHORIZED"] is False


def test_history_bytes_unmutated() -> None:
    for rel in (
        "docs/research/discovery_results/D2_DISCOVERY_RESULT.json",
        "docs/research/D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY.json",
        "docs/research/D2_BITMEX_REPLICATION_PREREG.json",
        "docs/research/D2_BITMEX_REPLICATION_IMPLEMENTATION_REVIEW.json",
        "scripts/research/d2_bitmex_replication_evaluator.py",
    ):
        committed = subprocess.check_output(["git", "show", f"HEAD:{rel}"], cwd=REPO)
        # Working tree may add the RESULT commit after these tests run against
        # the dirty tree; compare to the permit-commit frozen scientific bytes.
        frozen = subprocess.check_output(["git", "show", f"{PERMIT_COMMIT}:{rel}"], cwd=REPO)
        assert (REPO / rel).read_bytes() == frozen
        del committed
