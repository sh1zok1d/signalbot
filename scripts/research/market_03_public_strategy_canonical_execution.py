#!/usr/bin/env python3
"""MARKET-03 canonical execution wrapper. Lifecycle plumbing only.

Verifies frozen scientific bytes, prereg, implementation freeze, ARM,
RUN_IDENTITY, spot/funding authorities, authorized=1/consumed=0, and
protected OOS rejection. Does not load bound market rows into strategy
logic in this ARM unit. Does not consume the reservation. Does not
create RESULT.

Scientific functions remain in the frozen lib. This wrapper does not
reimplement signals, wallet, MDD, or classification.
"""

from __future__ import annotations

import sys
from typing import Any, Mapping

from scripts.research.market_03_public_strategy_arm_authority import (
    B2_06_EXECUTION_AUTHORIZED,
    CANONICAL_EXECUTIONS_AUTHORIZED,
    CANONICAL_EXECUTIONS_CONSUMED,
    EVALUATION_END_EXCLUSIVE,
    FROZEN_MARKET_03_RUN_IDENTITY,
    PROTECTED_OOS_AUTHORIZED,
    authenticate_market_03_canonical_execution,
    consume_authorization_atomically,
    reject_protected_oos_extension,
)
from scripts.research.market_03_public_strategy_authority import (
    inspect_market_03_authorization_state,
)


class PreConsumptionBlocker(RuntimeError):
    """Authority or bound-data failure before outcome-bearing evaluation."""


class Market03CanonicalExecutionReserved(RuntimeError):
    def __init__(
        self,
        message: str = "MARKET_03_CANONICAL_EXECUTION_RESERVED_FOR_EXECUTION_UNIT",
    ) -> None:
        super().__init__(message)


def authenticate_pre_execution(*args: Any, **kwargs: Any) -> dict[str, Any]:
    if args or kwargs:
        raise PreConsumptionBlocker(
            "caller arguments cannot redefine MARKET-03 canonical execution"
        )
    try:
        bound = authenticate_market_03_canonical_execution()
    except Exception as exc:
        raise PreConsumptionBlocker(str(exc)) from exc
    reservation = bound["reservation"]
    if int(reservation["CANONICAL_EXECUTIONS_AUTHORIZED"]) != 1:
        raise PreConsumptionBlocker("MARKET_03_RESERVATION_AUTHORIZED_MISMATCH")
    if int(reservation["CANONICAL_EXECUTIONS_CONSUMED"]) != 0:
        raise PreConsumptionBlocker("MARKET_03_RESERVATION_ALREADY_CONSUMED")
    if CANONICAL_EXECUTIONS_AUTHORIZED != 1:
        raise PreConsumptionBlocker("MARKET_03_ARM_MODULE_AUTHORIZED_MISMATCH")
    if CANONICAL_EXECUTIONS_CONSUMED != 0:
        raise PreConsumptionBlocker("MARKET_03_ARM_MODULE_ALREADY_CONSUMED")
    if B2_06_EXECUTION_AUTHORIZED is not False:
        raise PreConsumptionBlocker("MARKET_03_B2_06_MUTATED")
    if PROTECTED_OOS_AUTHORIZED is not False:
        raise PreConsumptionBlocker("MARKET_03_PROTECTED_OOS_MUTATED")
    if bound["run_identity"] != FROZEN_MARKET_03_RUN_IDENTITY:
        raise PreConsumptionBlocker("MARKET_03_RUN_IDENTITY_MISMATCH")
    reject_protected_oos_extension(EVALUATION_END_EXCLUSIVE)
    frozen = inspect_market_03_authorization_state()
    if frozen["MARKET_03_ARMED"] is not False:
        raise PreConsumptionBlocker("MARKET_03_FROZEN_AUTHORITY_MUST_REMAIN_UNARMED")
    return bound


def permit_canonical_scientific_execution(
    *args: Any, **kwargs: Any
) -> dict[str, Any]:
    """Return a pre-execution permit. Does not consume. Does not load rows."""
    bound = authenticate_pre_execution(*args, **kwargs)
    return {
        "permitted": True,
        "consumed": False,
        "run_identity": bound["run_identity"],
        "CANONICAL_EXECUTIONS_AUTHORIZED": 1,
        "CANONICAL_EXECUTIONS_CONSUMED": 0,
        "scientific_evaluation_reserved": True,
        "bound_rows_loaded": False,
    }


def evaluate_bound_after_arm_consumption(
    *args: Any, **kwargs: Any
) -> Mapping[str, Any]:
    """Future execution unit only. Never invoked with bound series here."""
    raise Market03CanonicalExecutionReserved(
        "MARKET_03_BOUND_SCIENTIFIC_EVALUATION_RESERVED_FOR_EXECUTION_UNIT"
    )


def run_canonical_market_03(*args: Any, **kwargs: Any) -> int:
    """Authenticate, then stop. Does not consume, load, simulate, or RESULT."""
    if args or kwargs:
        print(
            "caller arguments cannot redefine MARKET-03 canonical execution",
            file=sys.stderr,
        )
        return 2
    try:
        permit = permit_canonical_scientific_execution()
    except PreConsumptionBlocker as exc:
        print(f"PRE_CONSUMPTION_BLOCKER:{exc}", file=sys.stderr)
        return 3
    print("PRE_EXECUTION_AUTH_OK", file=sys.stderr)
    print(f"RUN_IDENTITY={permit['run_identity']}", file=sys.stderr)
    print("CANONICAL_EXECUTIONS_AUTHORIZED=1", file=sys.stderr)
    print("CANONICAL_EXECUTIONS_CONSUMED=0", file=sys.stderr)
    print(
        "MARKET_03_CANONICAL_EXECUTION_RESERVED_FOR_EXECUTION_UNIT",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv:
        print(
            "caller arguments cannot redefine MARKET-03 canonical execution",
            file=sys.stderr,
        )
        return 2
    return run_canonical_market_03()


# consume_authorization_atomically is imported for the future execution
# unit. This ARM wrapper never calls it.
_CONSUME_RESERVED = consume_authorization_atomically


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
