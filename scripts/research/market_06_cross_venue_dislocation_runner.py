#!/usr/bin/env python3
"""MARKET-06 canonical runner. Execution is refused in this unit.

CLI flags, environment variables, and kwargs cannot authorize evaluation
of the retained 2022-2024 dataset.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from scripts.research.market_06_cross_venue_dislocation_authority import (
    Market06AuthorityError,
    Market06ExecutionNotAuthorized,
    refuse_canonical_execution,
    verify_git_bound_data_authority,
    verify_prereg_authority,
)
from scripts.research.market_06_cross_venue_dislocation_evaluator import (
    evaluate_canonical_market_06,
)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        authority = verify_prereg_authority()
        data = verify_git_bound_data_authority(hash_raw_objects=False)
        evaluate_canonical_market_06()
        refuse_canonical_execution()
    except Market06ExecutionNotAuthorized as exc:
        payload: dict[str, Any] = {
            "REAL_CANONICAL_EXECUTION_REFUSED": True,
            "classification": "MARKET_06_EXECUTION_NOT_AUTHORIZED",
            "reason": str(exc),
            "argv": args,
            "scientific_outcomes_inspected": False,
            "real_data_parsed_for_science": False,
        }
        print(json.dumps(payload, sort_keys=True, indent=2))
        return 2
    except Market06AuthorityError as exc:
        print(json.dumps({"authority_error": str(exc)}, sort_keys=True, indent=2))
        return 3
    raise RuntimeError(f"unreachable:{authority}:{data}")


if __name__ == "__main__":
    raise SystemExit(main())
