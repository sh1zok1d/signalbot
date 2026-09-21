#!/usr/bin/env python3
"""MARKET-06 canonical runner.

Authority chain (red-team L10/L11):

    CLAIM -> RESERVATION -> ARM -> IMPLEMENTATION FREEZE

The runner never infers the ARM from current HEAD. It reads the tracked
CLAIM from an immutable commit; the claim names its reservation commit; the
reservation names its ARM commit; the ARM names its implementation freeze.
No lifecycle artifact contains its own commit SHA.

The durable CLAIM is consumed BEFORE any market data is parsed, so a crash
between outcome computation and RESULT persistence cannot silently return
the one shot. A failure after the claim is
MARKET_06_INCOMPLETE_EXECUTION under an already-consumed claim; it is never
an automatic rerun.

CLI flags, environment variables, and kwargs cannot authorize execution.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from scripts.research import market_06_execution_lifecycle as lifecycle
from scripts.research.market_06_cross_venue_dislocation_authority import (
    Market06AuthorityError,
    Market06IncompleteExecution,
    verify_git_bound_data_authority,
    verify_prereg_authority,
)
from scripts.research.market_06_execution_lifecycle import (
    Market06ExecutionNotAuthorized,
    Market06LifecycleError,
)


def run_from_claim_commit(claim_commit: str) -> dict[str, Any]:
    """The canonical execution entry point.

    Imports of the scientific path are local so that merely importing this
    runner can never pull the canonical reconstruction into an
    unauthorized process.
    """

    authority = lifecycle.verify_claim_from_commit(claim_commit)

    from scripts.research import market_06_result_persistence as persistence
    from scripts.research.market_06_canonical_reconstruction import (
        reconstruct_canonical_dataset,
    )
    from scripts.research.market_06_cross_venue_dislocation_evaluator import (
        evaluate_from_bars,
    )

    lifecycle.assert_shot_not_already_consumed(authority.run_identity)

    with lifecycle.Market06ExecutionLock(authority.run_identity):
        # Durably consume the shot BEFORE any market data is parsed.
        lifecycle.record_execution_attempt(authority)
        perp, spot, audit = reconstruct_canonical_dataset(authority.permit)
        outcome = evaluate_from_bars(perp, spot)
        staged = persistence.stage_canonical_result(authority, outcome, audit)

    return {
        "run_identity": authority.run_identity,
        "authority_chain": {
            "claim_commit": authority.claim_commit,
            "reservation_commit": authority.reservation_commit,
            "arm_commit": authority.arm_commit,
            "implementation_freeze_head": authority.permit.implementation_freeze_head,
            "prereg_freeze_head": lifecycle.PREREG_FREEZE_HEAD,
        },
        "result_sha256": staged.sha256,
        "result_paths": list(staged.written_paths()),
        "classification": staged.payload["classification"],
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        authority_identity = verify_prereg_authority()
        data = verify_git_bound_data_authority(hash_raw_objects=False)
        claim_authority = lifecycle.canonical_execution_permit_or_refuse()
    except Market06ExecutionNotAuthorized as exc:
        print(
            json.dumps(
                {
                    "REAL_CANONICAL_EXECUTION_REFUSED": True,
                    "classification": "MARKET_06_EXECUTION_NOT_AUTHORIZED",
                    "reason": str(exc),
                    "authority_chain": (
                        "CLAIM -> RESERVATION -> ARM -> IMPLEMENTATION_FREEZE"
                    ),
                    "argv": args,
                    "scientific_outcomes_inspected": False,
                    "real_data_parsed_for_science": False,
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 2
    except Market06AuthorityError as exc:
        print(json.dumps({"authority_error": str(exc)}, sort_keys=True, indent=2))
        return 3
    except Market06LifecycleError as exc:
        print(json.dumps({"lifecycle_error": str(exc)}, sort_keys=True, indent=2))
        return 4

    try:
        executed = run_from_claim_commit(claim_authority.claim_commit)
    except Market06IncompleteExecution as exc:
        # The claim stays consumed. This is never an automatic rerun.
        print(
            json.dumps(
                {
                    "classification": "MARKET_06_INCOMPLETE_EXECUTION",
                    "reason": exc.reason,
                    "claim_consumed": True,
                    "automatic_rerun_authorized": False,
                    "prereg_freeze_head": authority_identity["prereg_freeze_head"],
                    "dataset_id": data["dataset_id"],
                },
                sort_keys=True,
                indent=2,
            )
        )
        return 5
    print(json.dumps(executed, sort_keys=True, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
