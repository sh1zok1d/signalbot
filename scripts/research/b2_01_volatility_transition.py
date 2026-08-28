#!/usr/bin/env python3
"""B2-01 volatility-transition runner.

The implementation-freeze PR must use only --stage identity and synthetic unit
tests. A later real development run requires explicit acknowledgement plus an
exact clean reviewed Git SHA and Harness-authorized CORE_BTC_BINANCE_V0 bytes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.research.b2_01_volatility_transition_lib import (
    BAR_MS,
    DATASET_ID,
    DEV_END_MS,
    DEV_START_MS,
    HYPOTHESIS_ID,
    MAX_H_MIN,
    PREREG_JSON,
    REPO_ROOT,
    REQUIRED_SNAPSHOT,
    SEED_BOOT,
    SEED_PLACEBO,
    T_MAX_MS,
    YEAR_BLOCKS,
    build_panel,
    evaluate_b2_01,
    load_authorized_1m,
    load_prereg,
    promotion_gate_contract,
    validate_prereg,
)
from scripts.research.lib.research_harness import (
    DatasetIdentityContract,
    OutcomeAccessPolicy,
    authorize_dataset_access,
    build_run_identity,
    sha256_file,
    verify_git_freeze,
    write_json_new,
)

DEFAULT_ROOT = REPO_ROOT / "artifacts" / "research_data" / DATASET_ID
DEFAULT_OUT = REPO_ROOT / "artifacts" / "b2_01"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage", required=True, choices=("identity", "dev-run"))
    p.add_argument("--expected-code-sha", required=True)
    p.add_argument("--dataset-root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument(
        "--acknowledge-development-outcome-access",
        action="store_true",
        help=(
            "Required for --stage dev-run. Never use during preregistration/"
            "implementation freeze; use only after the exact implementation SHA "
            "has passed all required review gates."
        ),
    )
    return p


def main(argv=None) -> int:
    args = _parser().parse_args(argv)

    prereg = load_prereg()
    validate_prereg(prereg)
    code_freeze = verify_git_freeze(REPO_ROOT, args.expected_code_sha)

    identity_payload = {
        "stage": args.stage,
        "hypothesis_id": HYPOTHESIS_ID,
        "dataset_id": DATASET_ID,
        "snapshot_id": REQUIRED_SNAPSHOT,
        "code_sha": code_freeze.code_sha,
        "prereg_path": str(PREREG_JSON.relative_to(REPO_ROOT)),
        "prereg_sha256": sha256_file(PREREG_JSON),
        "outcome_accessed": False,
        "validation_2025_accessed": False,
        "oos_2026_accessed": False,
    }
    print(json.dumps(identity_payload, sort_keys=True))

    if args.stage == "identity":
        return 0

    if not args.acknowledge_development_outcome_access:
        print(
            "--stage dev-run requires --acknowledge-development-outcome-access",
            file=sys.stderr,
        )
        return 2

    identity = DatasetIdentityContract(
        dataset_id=DATASET_ID,
        snapshot_id=REQUIRED_SNAPSHOT,
    )
    policy = OutcomeAccessPolicy(
        stage="development",
        start_inclusive_ms=DEV_START_MS,
        end_exclusive_ms=DEV_END_MS,
        allowed_years=YEAR_BLOCKS,
    )
    authorized = authorize_dataset_access(
        code_freeze=code_freeze,
        dataset_root=args.dataset_root,
        identity=identity,
        policy=policy,
    )
    # Harness boundary proof for the earliest legal decision and the maximum
    # preregistered horizon at the latest legal decision.
    authorized.assert_outcome_window(DEV_START_MS, 0)
    authorized.assert_outcome_window(T_MAX_MS, MAX_H_MIN * BAR_MS)

    gate_contract = promotion_gate_contract()
    run_identity = build_run_identity(
        hypothesis_id=HYPOTHESIS_ID,
        stage="development",
        code_freeze=code_freeze,
        authorized_dataset=authorized,
        gate_contract=gate_contract,
        command=[
            "python",
            "-m",
            "scripts.research.b2_01_volatility_transition",
            "--stage",
            "dev-run",
            "--expected-code-sha",
            code_freeze.code_sha,
            "--dataset-root",
            str(args.dataset_root.resolve()),
            "--out-dir",
            str(args.out_dir.resolve()),
            "--acknowledge-development-outcome-access",
        ],
        seeds={
            "bootstrap": SEED_BOOT,
            "placebo": SEED_PLACEBO,
        },
    )

    frame = load_authorized_1m(authorized)
    panel = build_panel(frame)
    result = evaluate_b2_01(panel)
    result["provenance"] = run_identity
    result["prereg"] = {
        "path": str(PREREG_JSON.relative_to(REPO_ROOT)),
        "sha256": sha256_file(PREREG_JSON),
    }
    validation_2025_accessed = 2025 in policy.allowed_years
    oos_2026_accessed = any(year >= 2026 for year in policy.allowed_years)
    reserved_boundary_breached = policy.end_exclusive_ms > DEV_END_MS
    if validation_2025_accessed or oos_2026_accessed or reserved_boundary_breached:
        raise RuntimeError(
            "development authorization reaches a reserved validation/OOS boundary"
        )
    result["forbidden_windows_inspected"] = {
        "2025_validation": validation_2025_accessed,
        "2026_oos": oos_2026_accessed,
        "allowed_years": list(policy.allowed_years),
        "development_end_exclusive_ms": policy.end_exclusive_ms,
    }

    out_path = args.out_dir / "B2_01_DEV_RESULTS.json"
    digest = write_json_new(out_path, result)
    print(
        json.dumps(
            {
                "overall_status": result["promotion"]["verdict"],
                "result_path": str(out_path),
                "result_sha256": digest,
                "code_sha": code_freeze.code_sha,
                "validation_2025_accessed": validation_2025_accessed,
                "oos_2026_accessed": oos_2026_accessed,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
