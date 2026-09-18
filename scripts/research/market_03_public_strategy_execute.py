"""Fail-closed MARKET-03 production execution stub.

This implementation unit cannot run the strategy against the bound real
spot or funding snapshots. Canonical execution remains unauthorized.
"""

from __future__ import annotations

import argparse
import sys

from scripts.research.market_03_public_strategy_authority import (
    CANONICAL_EXECUTIONS_AUTHORIZED,
    MARKET_03_ARMED,
    MARKET_03_BOUND_EXECUTION_AUTHORIZED,
    Market03ExecutionNotAuthorized,
    inspect_market_03_authorization_state,
    refuse_bound_execution,
)


def execute_bound_market_03(*_args: object, **_kwargs: object) -> None:
    refuse_bound_execution(
        "MARKET_03_BOUND_EXECUTION_REFUSED_IMPLEMENTATION_UNIT:"
        f"ARMED={MARKET_03_ARMED},"
        f"BOUND_AUTHORIZED={MARKET_03_BOUND_EXECUTION_AUTHORIZED},"
        f"CANONICAL_AUTHORIZED={CANONICAL_EXECUTIONS_AUTHORIZED}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="MARKET-03 bound execution (fail-closed in this unit)"
    )
    parser.add_argument("--force", action="store_true", help=argparse.SUPPRESS)
    parser.parse_args(argv)
    state = inspect_market_03_authorization_state()
    if state["MARKET_03_BOUND_EXECUTION_AUTHORIZED"] or state["MARKET_03_ARMED"]:
        raise Market03ExecutionNotAuthorized("MARKET_03_LIFECYCLE_FLAG_MUST_REMAIN_UNARMED")
    try:
        execute_bound_market_03()
    except Market03ExecutionNotAuthorized as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
