#!/usr/bin/env python3
"""Fail-closed MARKET-05 production execution stub.

Ordinary invocation, --help, import, and pytest cannot execute the
scientific study. Canonical execution requires a later ARM artifact.
"""

from __future__ import annotations

import argparse
import sys

from scripts.research.market05_cross_asset_authority import (
    Market05ExecutionNotAuthorized,
    inspect_market_05_authorization_state,
    refuse_scientific_result_instantiation,
    refuse_unarmed_canonical_execution,
    require_execution_authorized_before_outcome_load,
)


def execute_bound_market_05(*_args: object, **_kwargs: object) -> None:
    require_execution_authorized_before_outcome_load()
    refuse_unarmed_canonical_execution()


def write_scientific_result(*_args: object, **_kwargs: object) -> None:
    refuse_scientific_result_instantiation()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="MARKET-05 bound execution (fail-closed until ARM)"
    )
    parser.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--write-result",
        action="store_true",
        help="Attempt scientific RESULT write (refused in this unit)",
    )
    args = parser.parse_args(argv)
    state = inspect_market_05_authorization_state()
    if state["MARKET_05_EXECUTION_AUTHORIZED"] or state["MARKET_05_ARMED"]:
        raise Market05ExecutionNotAuthorized(
            "MARKET_05_LIFECYCLE_FLAG_MUST_REMAIN_UNARMED"
        )
    try:
        if args.write_result:
            write_scientific_result()
        execute_bound_market_05()
    except Market05ExecutionNotAuthorized as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
