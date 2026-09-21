#!/usr/bin/env python3
"""MARKET-06 canonical runner.

Permit architecture (red-team F-05). The runner no longer refuses
unconditionally and no longer ends its success path in an ``unreachable``
RuntimeError. It refuses today because no tracked ARM exists, and the SAME
frozen scientific bytes proceed once a valid tracked ARM and an unconsumed
tracked reservation exist.

CLI flags, environment variables, and kwargs cannot authorize evaluation of
the retained 2022-2024 dataset.
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


def canonical_execution(permit: Any) -> dict[str, Any]:
    """Run the one canonical evaluation under an authenticated permit.

    Imports are local so that merely importing the runner can never pull the
    canonical reconstruction path into an unauthorized process.
    """

    authenticated = lifecycle.require_permit(permit)
    lifecycle.verify_execution_reservation(authenticated)

    from scripts.research.market_06_canonical_reconstruction import (
        reconstruct_canonical_dataset,
    )
    from scripts.research.market_06_cross_venue_dislocation_evaluator import (
        evaluate_from_bars,
    )

    with lifecycle.Market06ExecutionLock(authenticated.run_identity):
        perp, spot, audit = reconstruct_canonical_dataset(authenticated)
        outcome = evaluate_from_bars(perp, spot)
    return {"run_identity": authenticated.run_identity, "audit": audit, "outcome": outcome}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        authority = verify_prereg_authority()
        data = verify_git_bound_data_authority(hash_raw_objects=False)
        permit = lifecycle.canonical_execution_permit_or_refuse()
    except Market06ExecutionNotAuthorized as exc:
        print(
            json.dumps(
                {
                    "REAL_CANONICAL_EXECUTION_REFUSED": True,
                    "classification": "MARKET_06_EXECUTION_NOT_AUTHORIZED",
                    "reason": str(exc),
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
        executed = canonical_execution(permit)
    except Market06IncompleteExecution as exc:
        print(
            json.dumps(
                {
                    "classification": "MARKET_06_INCOMPLETE_EXECUTION",
                    "reason": exc.reason,
                    "authority": authority["prereg_freeze_head"],
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
