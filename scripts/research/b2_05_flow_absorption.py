#!/usr/bin/env python3
"""Canonical B2-05 flow-absorption runner.

The implementation stage may call identity() and synthetic helpers only.
run_development() is implemented but must not be invoked against real CORE
data in this unit. Default outcome_access_acknowledged=False keeps the
one-shot unused.

This module deliberately does not use `from __future__ import annotations`:
the merged Batch02 static source policy default-denies every non-repository
import that is not on its explicit transform allowlist, and B2-0x source is
adapted to that bounded policy rather than the policy being widened. Python
3.11 evaluates the annotations used here natively.
"""

from pathlib import Path

from scripts.research.b2_05_flow_absorption_lib import (
    DATASET_ID,
    DEV_END_MS,
    DEV_START_MS,
    GATE_NAMES,
    HYPOTHESIS_ID,
    PREREG_MERGE_SHA,
    REQUIRED_SNAPSHOT,
    REQUIRED_SOURCE_COLUMNS,
    SEED_BOOT,
    SEED_PLACEBO,
    derive_forbidden_window_evidence,
    evaluate_b2_05,
    table_to_1m_frame,
)
from scripts.research.lib.batch02_contracts import (
    archive_batch02_result,
    load_authorized_parquet_table,
    persist_batch02_retained_result,
    prepare_batch02_evidence_reservation,
    prepare_batch02_retained_run,
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
    / "b2_05_flow_absorption"
    / "B2_05_FLOW_ABSORPTION_DEV_RESULTS.json"
)


def identity(expected_code_sha):
    """Verify exact clean Git identity. Does not reserve, claim, or load data."""
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
    expected_code_sha,
    *,
    dataset_root=DEFAULT_DATASET_ROOT,
    outcome_access_acknowledged=False,
):
    """Production B2-05 ceremony. Do not invoke against real CORE in this unit.

    `prepare_batch02_retained_run()` durably claims the one-shot remote
    outcome-access slot (RESERVED -> OUTCOME_ACCESS_CLAIMED, with independent
    remote readback) before its own `outcome_access_acknowledged` check runs,
    so a call reaching that far with the safe default would still burn the
    B2-05 one-shot slot on the remote evidence ref before raising. This guard
    rejects an unacknowledged call before it can reach
    `prepare_batch02_evidence_reservation`, `prepare_batch02_retained_run`, or
    the authorized loader at all. Only the literal boolean `True` is accepted:
    truthy stand-ins (1, "true", non-empty objects) are rejected.
    """
    if outcome_access_acknowledged is not True:
        raise ValueError(
            "run_development requires outcome_access_acknowledged=True; "
            "refusing before any reservation/claim/loader call, because "
            "prepare_batch02_retained_run durably claims the one-shot remote "
            "outcome-access slot before it checks this flag"
        )
    code_freeze = verify_batch02_code(
        repo_root=REPO_ROOT,
        expected_code_sha=expected_code_sha,
    )
    reservation = prepare_batch02_evidence_reservation(
        code_freeze=code_freeze,
        hypothesis_id=HYPOTHESIS_ID,
        stage="development",
        dataset_id=DATASET_ID,
        snapshot_id=REQUIRED_SNAPSHOT,
        start_inclusive_ms=DEV_START_MS,
        end_exclusive_ms=DEV_END_MS,
        allowed_years=(2020, 2021, 2022, 2023, 2024),
        required_gate_names=GATE_NAMES,
        seeds={
            "bootstrap": SEED_BOOT,
            "placebo": SEED_PLACEBO,
        },
    )
    run_context = prepare_batch02_retained_run(
        reservation=reservation,
        outcome_access_acknowledged=outcome_access_acknowledged,
        dataset_root=dataset_root,
        command=(
            "python-api",
            "scripts.research.b2_05_flow_absorption.run_development",
            expected_code_sha,
        ),
    )
    table = load_authorized_parquet_table(
        run_context=run_context,
        columns=tuple(REQUIRED_SOURCE_COLUMNS),
    )
    frame = table_to_1m_frame(table)
    forbidden_windows = derive_forbidden_window_evidence(
        run_context.run_identity,
        frame,
    )
    result = evaluate_b2_05(frame)
    result["preregistration"] = {
        "merge_sha": PREREG_MERGE_SHA,
        "formulation_id": HYPOTHESIS_ID,
    }
    result["forbidden_windows_inspected"] = forbidden_windows
    persisted = persist_batch02_retained_result(
        RESULT_PATH,
        result,
        run_context=run_context,
    )
    receipt = archive_batch02_result(
        persisted_result=persisted,
        run_context=run_context,
    )
    return {
        "overall_status": result["promotion"]["verdict"],
        "result_path": str(RESULT_PATH),
        "result_sha256": persisted.artifact_sha256,
        "archive_commit_sha": receipt.archive_commit_sha,
        "code_sha": code_freeze.code_sha,
        "validation_2025_accessed": bool(forbidden_windows["2025_validation"]),
        "oos_2026_accessed": bool(forbidden_windows["2026_oos"]),
    }
