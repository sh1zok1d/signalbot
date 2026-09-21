"""MARKET-06 coefficient and year-stratified predictive bootstrap.

RNG consumption order is frozen before any real execution:

1. Initialize one ``numpy.random.Generator(numpy.random.PCG64(2026092106))``.
2. Coefficient bootstrap: all 5000 TRAIN circular-MBB replicates.
3. Predictive bootstrap: all 5000 replicates; within each replicate
   sample 2023 first, then 2024, via ``year_stratified_predictive_resample``.

Does not import or call ``concatenated_then_sample``.
Does not refit predictive models. Does not re-estimate train mean/sd
inside coefficient replicates.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from scripts.research.market_06_cross_venue_dislocation_authority import (
    Market06IncompleteExecution,
)
from scripts.research.market_06_year_stratified_circular_mbb import (
    BLOCK_LENGTH_DAYS,
    BOOTSTRAP_REPLICATES,
    RANDOM_SEED,
    circular_moving_block_indices,
    pcg64_generator,
    year_stratified_predictive_resample,
)

PERCENTILE_Q = [2.5, 97.5]
PERCENTILE_METHOD = "linear"
RNG_ORDER = (
    "init_pcg64_once",
    "coefficient_bootstrap_5000",
    "predictive_bootstrap_5000",
    "within_predictive_replicate_sample_2023_then_2024",
)


def make_rng(seed: int = RANDOM_SEED) -> np.random.Generator:
    return pcg64_generator(seed)


def percentile_ci(replicates: np.ndarray) -> tuple[float, float]:
    low, high = np.percentile(replicates, PERCENTILE_Q, method=PERCENTILE_METHOD)
    return float(low), float(high)


def ols_solve(design: np.ndarray, y: np.ndarray) -> np.ndarray:
    xtx = design.T @ design
    xty = design.T @ y
    try:
        beta = np.linalg.solve(xtx, xty)
    except np.linalg.LinAlgError as exc:
        raise Market06IncompleteExecution("RANK_DEFICIENT") from exc
    if not np.all(np.isfinite(beta)):
        raise Market06IncompleteExecution("NONFINITE_BETA")
    return beta


def coefficient_moving_block_bootstrap(
    design: np.ndarray,
    y: np.ndarray,
    rng: np.random.Generator,
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    block_length: int = BLOCK_LENGTH_DAYS,
) -> np.ndarray:
    """Refit candidate OLS on circular TRAIN blocks. Frozen standardization already in design."""

    n = int(design.shape[0])
    if n < block_length:
        raise Market06IncompleteExecution("TRAIN_TOO_SHORT_FOR_14D_BLOCK")
    betas = np.empty(replicates, dtype=np.float64)
    for i in range(replicates):
        idx, _blocks = circular_moving_block_indices(
            n, block_length=block_length, rng=rng
        )
        beta = ols_solve(design[idx], y[idx])
        value = float(beta[-1])
        if not np.isfinite(value):
            raise Market06IncompleteExecution("NONFINITE_COEFFICIENT_REPLICATE")
        betas[i] = value
    return betas


def relative_mae_improvement(mae_candidate: float, mae_baseline: float) -> float:
    if not np.isfinite(mae_baseline) or mae_baseline <= 0.0:
        raise Market06IncompleteExecution("NONFINITE_POOLED_BASELINE_MAE")
    if not np.isfinite(mae_candidate) or mae_candidate < 0.0:
        raise Market06IncompleteExecution("NONFINITE_CANDIDATE_MAE")
    return float(1.0 - (mae_candidate / mae_baseline))


def _mae_from_loss_tuples(rows: Sequence[tuple[float, float]]) -> tuple[float, float]:
    if not rows:
        raise Market06IncompleteExecution("EMPTY_LOSS_TUPLES")
    baseline = float(np.mean([row[0] for row in rows]))
    candidate = float(np.mean([row[1] for row in rows]))
    return baseline, candidate


def year_stratified_predictive_bootstrap(
    loss_2023: Sequence[tuple[float, float]],
    loss_2024: Sequence[tuple[float, float]],
    rng: np.random.Generator,
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    block_length: int = BLOCK_LENGTH_DAYS,
) -> np.ndarray:
    n_2023 = len(loss_2023)
    n_2024 = len(loss_2024)
    if n_2023 == 0 or n_2024 == 0:
        raise Market06IncompleteExecution("EMPTY_PREDICTIVE_YEAR")
    stats = np.empty(replicates, dtype=np.float64)
    for i in range(replicates):
        boot_2023, boot_2024, _b23, _b24 = year_stratified_predictive_resample(
            loss_2023,
            loss_2024,
            block_length=block_length,
            rng=rng,
        )
        if len(boot_2023) != n_2023 or len(boot_2024) != n_2024:
            raise Market06IncompleteExecution("YEAR_SAMPLE_SIZE_NOT_PRESERVED")
        pooled = list(boot_2023) + list(boot_2024)
        mae_base, mae_cand = _mae_from_loss_tuples(pooled)
        stats[i] = relative_mae_improvement(mae_cand, mae_base)
    return stats
