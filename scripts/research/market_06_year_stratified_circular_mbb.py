"""Year-stratified circular moving-block sampler for MARKET-06.

Sampling-structure primitive only. Not an evaluator. Does not read OHLC,
dislocation, eligible-row counts, MAE, or coefficients.
"""

from __future__ import annotations

from typing import Sequence, TypeVar

import numpy as np

T = TypeVar("T")

BLOCK_LENGTH_DAYS = 14
BOOTSTRAP_REPLICATES = 5000
RANDOM_SEED = 2026092106


def pcg64_generator(seed: int = RANDOM_SEED) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(int(seed)))


def circular_moving_block_indices(
    n: int,
    *,
    block_length: int = BLOCK_LENGTH_DAYS,
    rng: np.random.Generator,
) -> tuple[list[int], list[list[int]]]:
    """Resample length-n indices with circular wrap inside this series only.

    Concatenate blocks of ``block_length`` until length >= n, then trim the
    final block so the returned index path has length exactly n.
    """

    if n <= 0:
        raise ValueError("empty series cannot form circular moving blocks")
    if block_length <= 0:
        raise ValueError("block_length must be positive")
    collected: list[int] = []
    blocks: list[list[int]] = []
    while len(collected) < n:
        start = int(rng.integers(0, n))
        block = [int((start + j) % n) for j in range(block_length)]
        blocks.append(block)
        collected.extend(block)
    return collected[:n], blocks


def year_stratified_predictive_resample(
    seq_2023: Sequence[T],
    seq_2024: Sequence[T],
    *,
    block_length: int = BLOCK_LENGTH_DAYS,
    rng: np.random.Generator,
) -> tuple[list[T], list[T], list[list[int]], list[list[int]]]:
    """Independent circular MBB within each year, then concatenate 2023 then 2024.

    Returns ``(boot_2023, boot_2024, blocks_2023, blocks_2024)``. Callers that
    need the pooled replicate concatenate ``boot_2023 + boot_2024`` *after*
    sampling. Concatenating before sampling is forbidden.
    """

    n_2023 = len(seq_2023)
    n_2024 = len(seq_2024)
    idx_2023, blocks_2023 = circular_moving_block_indices(
        n_2023, block_length=block_length, rng=rng
    )
    idx_2024, blocks_2024 = circular_moving_block_indices(
        n_2024, block_length=block_length, rng=rng
    )
    boot_2023 = [seq_2023[i] for i in idx_2023]
    boot_2024 = [seq_2024[i] for i in idx_2024]
    if len(boot_2023) != n_2023 or len(boot_2024) != n_2024:
        raise RuntimeError("year sample size was not preserved")
    return boot_2023, boot_2024, blocks_2023, blocks_2024


def concatenated_then_sample(
    seq_2023: Sequence[T],
    seq_2024: Sequence[T],
    *,
    block_length: int = BLOCK_LENGTH_DAYS,
    rng: np.random.Generator,
) -> tuple[list[T], list[list[int]]]:
    """Forbidden concatenated-before-sampling path, kept only as a contrast."""

    combined = list(seq_2023) + list(seq_2024)
    idx, blocks = circular_moving_block_indices(
        len(combined), block_length=block_length, rng=rng
    )
    return [combined[i] for i in idx], blocks
