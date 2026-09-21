"""Firewalled D2 BitMEX replication evaluator.

Outcome-blind implementation specification. Scientific execution is not
authorized. Frozen rv_btc_24h / btc_ret_24h / arithmetic_mae are bound as
callables but are not applied to BitMEX paths in this unit.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Sequence

import numpy as np

from scripts.research.d2_bitmex_pre2020 import (
    FUTURE_BARS,
    PRE2020_END_EXCLUSIVE,
    refuse_d2_outcome_request,
)
from scripts.research.d2_bitmex_replication_prereg import (
    D2_BITMEX_REPLICATION_RANDOM_SEED,
    N_REPLICATES as PREREG_N_REPLICATES,
)
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_cross_venue_dislocation_evaluator import (
    arithmetic_mae,
    btc_ret_24h,
    btc_side_from_ret,
    rv_btc_24h,
)

EXECUTION_AUTHORIZED = False
N_REPLICATES = int(PREREG_N_REPLICATES)
REPLICATION_RANDOM_SEED = int(D2_BITMEX_REPLICATION_RANDOM_SEED)

SCIENTIFIC_RV = rv_btc_24h
SCIENTIFIC_RET = btc_ret_24h
SCIENTIFIC_SIDE = btc_side_from_ret
SCIENTIFIC_MAE = arithmetic_mae
SCIENTIFIC_RV_MASK = C.rv_abstention_mask
SCIENTIFIC_YEAR_MATCHED_CONTROLS = C.rate_matched_random_abstention


class ExecutionNotAuthorized(RuntimeError):
    """BitMEX D2 scientific execution is not authorized."""


def verify_eligibility(*, repo=None) -> dict[str, Any]:
    """Timestamp/gap/hash census only. No D2 outcomes."""
    from scripts.research.d2_bitmex_replication_prereg import verify_frozen_eligibility

    return verify_frozen_eligibility(repo)


def year_matched_control_replicate_means(
    years: Sequence[int],
    severity: Sequence[float],
    abstain: np.ndarray,
    *,
    seed: int,
    n_replicates: int = N_REPLICATES,
) -> np.ndarray:
    """Year-matched RATE_MATCHED_RANDOM_ABSTENTION means. No pooled K."""
    years_arr = np.asarray(list(years), dtype=np.int64)
    sev = np.asarray(list(severity), dtype=np.float64)
    mask = np.asarray(abstain, dtype=bool)
    if years_arr.size != sev.size or years_arr.size != mask.size:
        raise ValueError("CONTROL_SHAPE")
    pooled_k_is_forbidden(years_arr, mask)
    replicates = SCIENTIFIC_YEAR_MATCHED_CONTROLS(
        years_arr, mask, seed=int(seed), n_replicates=int(n_replicates)
    )
    return np.asarray([float(np.mean(sev[rep])) for rep in replicates], dtype=np.float64)


def pooled_k_is_forbidden(years: Sequence[int], abstain: np.ndarray) -> None:
    years_arr = np.asarray(list(years), dtype=np.int64)
    mask = np.asarray(abstain, dtype=bool)
    unique = sorted(set(int(y) for y in years_arr.tolist()))
    k_y = [int(mask[years_arr == y].sum()) for y in unique]
    if int(sum(k_y)) != int(mask.sum()):
        raise ValueError("K_YEAR_SUM")
    if len(unique) >= 2 and int(mask.sum()) > 0 and all(k == 0 for k in k_y):
        raise ValueError("POOLED_K_EMPTY_YEARS")


def last_future_bar_end(decision: datetime) -> datetime:
    return decision + timedelta(minutes=5 * FUTURE_BARS)


def assert_pre2020_future(decision: datetime) -> None:
    if last_future_bar_end(decision) >= PRE2020_END_EXCLUSIVE:
        raise ValueError("FUTURE_CROSSES_2020")
    if decision.year >= 2020:
        raise ValueError("DECISION_IN_2020")


def execute_replication(**_kwargs: Any) -> dict[str, Any]:
    """Scientific replication. Hard-refused in this unit."""
    refuse_d2_outcome_request("EXECUTE_REPLICATION")
    raise ExecutionNotAuthorized("EXECUTION_NOT_AUTHORIZED:EXECUTE_REPLICATION")


def compute_mu_rule(*_a: Any, **_k: Any) -> float:
    refuse_d2_outcome_request("MU_RULE")
    raise ExecutionNotAuthorized("MU_RULE")


def compute_delta(*_a: Any, **_k: Any) -> float:
    refuse_d2_outcome_request("DELTA")
    raise ExecutionNotAuthorized("DELTA")
