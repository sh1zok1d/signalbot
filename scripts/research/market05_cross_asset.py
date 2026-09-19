#!/usr/bin/env python3
"""MARKET-05 production entry.

Ordinary --help and unarmed invocation do not execute science.
When an authenticated ARM exists, this process delegates to the
canonical bootstrap (authority root first; claim before outcomes).
"""

from __future__ import annotations

import argparse
import sys


def write_scientific_result(*_args: object, **_kwargs: object) -> None:
    from scripts.research.market05_cross_asset_authority import (
        refuse_scientific_result_instantiation,
    )

    refuse_scientific_result_instantiation()


def execute_bound_market_05(*_args: object, **_kwargs: object) -> None:
    from scripts.research.market05_cross_asset_authority import (
        refuse_unarmed_canonical_execution,
        require_execution_authorized_before_outcome_load,
    )

    require_execution_authorized_before_outcome_load()
    refuse_unarmed_canonical_execution()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="MARKET-05 bound execution (claim-before-outcomes)"
    )
    parser.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--write-result",
        action="store_true",
        help="Attempt canonical RESULT write (requires ARM + unconsumed claim slot)",
    )
    args = parser.parse_args(argv)

    from scripts.research.market05_cross_asset_authority import (
        Market05ExecutionNotAuthorized,
        inspect_market_05_authorization_state,
    )

    state = inspect_market_05_authorization_state()
    if not state["MARKET_05_ARMED"] and not state["MARKET_05_EXECUTION_AUTHORIZED"]:
        try:
            from scripts.research.market05_cross_asset_authority import (
                refuse_unarmed_canonical_execution,
            )

            refuse_unarmed_canonical_execution()
        except Market05ExecutionNotAuthorized as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return 1

    from scripts.research.market05_cross_asset_bootstrap import (
        run_canonical_market_05_bootstrap,
    )

    try:
        run_canonical_market_05_bootstrap()
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
