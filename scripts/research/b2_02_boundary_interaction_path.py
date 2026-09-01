#!/usr/bin/env python3
"""Canonical B2-02 boundary-interaction runner.

The implementation-review stage may call identity() and synthetic helpers only.
run_development() requires an exact reviewed Git SHA plus explicit outcome-access
acknowledgement before canonical dataset loading becomes reachable.
"""
from __future__ import annotations

from pathlib import Path

from scripts.research.b2_02_boundary_interaction_path_lib import (
    DATASET_ID,
    DEV_END_MS,
    DEV_START_MS,
    GATE_NAMES,
    HYPOTHESIS_ID,
    REQUIRED_SNAPSHOT,
    SEED_BOOT,
    SEED_PLACEBO,
    evaluate_b2_02,
    table_to_1m_frame,
)
from scripts.research.lib.batch02_contracts import (
    load_authorized_parquet_table,
    persist_batch02_result,
    prepare_batch02_run,
    verify_batch02_code,
)


REPO_ROOT = Path(__file__).parents[2]
DEFAULT_DATASET_ROOT = (
    REPO_ROOT
    / "artifacts"
    / "research_data"
    / DATASET_ID
)
RESULT_PATH = (
    REPO_ROOT
    / "artifacts"
    / HYPOTHESIS_ID.lower()
    / "B2_02_BOUNDARY_INTERACTION_PATH_DEV_RESULTS.json"
)
PREREG_MERGE_SHA = "cbf447276c1dc47c9a755038cfd6013199207eef"


def identity(expected_code_sha: str) -> dict[str, object]:
    code_freeze = verify_batch02_code(
        repo_root=REPO_ROOT,
        expected_code_sha=expected_code_sha,
    )
    return {
        "stage": "identity",
        "hypothesis_id": HYPOTHESIS_ID,
        "dataset_id": DATASET_ID,
        "snapshot_id": REQUIRED_SNAPSHOT,
        "code_sha": code_freeze.code_sha,
        "prereg_merge_sha": PREREG_MERGE_SHA,
        "outcome_accessed": False,
        "validation_2025_accessed": False,
        "oos_2026_accessed": False,
    }


def run_development(
    expected_code_sha: str,
    *,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    outcome_access_acknowledged: bool = False,
) -> dict[str, object]:
    code_freeze = verify_batch02_code(
        repo_root=REPO_ROOT,
        expected_code_sha=expected_code_sha,
    )
    run_context = prepare_batch02_run(
        code_freeze=code_freeze,
        outcome_access_acknowledged=outcome_access_acknowledged,
        dataset_root=dataset_root,
        dataset_id=DATASET_ID,
        snapshot_id=REQUIRED_SNAPSHOT,
        start_inclusive_ms=DEV_START_MS,
        end_exclusive_ms=DEV_END_MS,
        allowed_years=(2020, 2021, 2022, 2023, 2024),
        required_gate_names=GATE_NAMES,
        hypothesis_id=HYPOTHESIS_ID,
        stage="development",
        command=(
            "python-api",
            "scripts.research.b2_02_boundary_interaction_path.run_development",
            expected_code_sha,
        ),
        seeds={
            "bootstrap": SEED_BOOT,
            "placebo": SEED_PLACEBO,
        },
    )
    table = load_authorized_parquet_table(
        run_context=run_context,
        columns=(
            "open_time_ms",
            "available_at_ms",
            "open",
            "high",
            "low",
            "close",
        ),
    )
    frame = table_to_1m_frame(table)
    result = evaluate_b2_02(frame)
    result["preregistration"] = {
        "merge_sha": PREREG_MERGE_SHA,
        "formulation_id": HYPOTHESIS_ID,
    }
    result["forbidden_windows_inspected"] = {
        "2025_validation": False,
        "2026_oos": False,
    }
    digest = persist_batch02_result(
        RESULT_PATH,
        result,
        run_context=run_context,
    )
    return {
        "overall_status": result["promotion"]["verdict"],
        "result_path": str(RESULT_PATH),
        "result_sha256": digest,
        "code_sha": code_freeze.code_sha,
        "validation_2025_accessed": False,
        "oos_2026_accessed": False,
    }
