"""MARKET-05 bootstrap determinism and circular-block golden tests.

Independent splitmix64 / wrap expectations. Does not execute scientific
MARKET-05 on real development rows.
"""

from __future__ import annotations

import pytest

from scripts.research.market05_cross_asset_lib import (
    BLOCK_LENGTH,
    BOOTSTRAP_REPLICATES,
    RANDOM_SEED,
    EligibleRow,
    Market05IntegrityError,
    SplitMix64,
    circular_moving_block_indices,
    coefficient_bootstrap,
    percentile_2p5_97p5,
    predictive_relative_mae_bootstrap,
    relative_mae_improvement,
    scientific_rng,
)

SPLITMIX64_FIRST_U64 = (
    16691122141672249309,
    8095568991954668857,
    15966305906299674551,
    9014679396895480376,
    15124412926049896196,
    13893994340662272934,
    7838463231040106950,
    8711197918110342525,
)
SPLITMIX64_FIRST_MOD5 = (4, 2, 1, 1, 1, 4, 0, 0)


def test_splitmix64_golden_sequence_and_seed_binding():
    assert RANDOM_SEED == 2026091905
    rng = SplitMix64(RANDOM_SEED)
    got = tuple(rng.next_u64() for _ in range(len(SPLITMIX64_FIRST_U64)))
    assert got == SPLITMIX64_FIRST_U64
    rng2 = scientific_rng()
    assert tuple(rng2.next_u64() for _ in range(8)) == SPLITMIX64_FIRST_U64
    rng3 = SplitMix64(RANDOM_SEED)
    assert tuple(rng3.next_index(5) for _ in range(8)) == SPLITMIX64_FIRST_MOD5
    other = SplitMix64(2026091906)
    assert other.next_u64() != SPLITMIX64_FIRST_U64[0]


def test_circular_moving_block_wraps_and_truncates():
    series = [0, 1, 2, 3, 4]
    rng = SplitMix64(RANDOM_SEED)
    idx = circular_moving_block_indices(len(series), block_length=3, rng=rng)
    assert len(idx) == 5
    first_start = SPLITMIX64_FIRST_MOD5[0]
    expected_first_block = [(first_start + i) % 5 for i in range(3)]
    assert idx[:3].tolist() == expected_first_block
    second_start = SPLITMIX64_FIRST_MOD5[1]
    expected_tail = [(second_start + i) % 5 for i in range(2)]
    assert idx[3:].tolist() == expected_tail
    assert 0 in set(range(5))
    wrapped = circular_moving_block_indices(5, 3, SplitMix64(RANDOM_SEED))
    assert (wrapped == idx).all()


def test_scientific_block_length_remains_14():
    assert BLOCK_LENGTH == 14
    assert BOOTSTRAP_REPLICATES == 5000
    rng = SplitMix64(RANDOM_SEED)
    idx = circular_moving_block_indices(20, BLOCK_LENGTH, rng)
    assert len(idx) == 20
    start = SPLITMIX64_FIRST_U64[0] % 20
    assert idx[:14].tolist() == [(start + i) % 20 for i in range(14)]


def test_predictive_bootstrap_no_refit_reduced_replicates():
    abs_b = [0.10, 0.20, 0.30, 0.40, 0.50]
    abs_c = [0.05, 0.10, 0.15, 0.20, 0.25]
    rng = SplitMix64(RANDOM_SEED)
    reps = predictive_relative_mae_bootstrap(
        abs_b, abs_c, block_length=3, replicates=3, rng=rng, refit=False
    )
    replay = SplitMix64(RANDOM_SEED)
    expected = []
    for _ in range(3):
        idx = circular_moving_block_indices(5, 3, replay)
        mae_b = sum(abs_b[int(i)] for i in idx) / 5.0
        mae_c = sum(abs_c[int(i)] for i in idx) / 5.0
        expected.append(1.0 - mae_c / mae_b)
    assert list(reps) == pytest.approx(expected)
    with pytest.raises(Market05IntegrityError, match="must not refit"):
        predictive_relative_mae_bootstrap(
            abs_b, abs_c, block_length=3, replicates=1, rng=SplitMix64(1), refit=True
        )


def test_percentiles_and_relative_formula():
    values = [i / 100.0 for i in range(1, 101)]
    lo, hi = percentile_2p5_97p5(values)
    assert lo == pytest.approx(0.025 + (2.5 % 1) * 0.0, abs=0.02)
    assert relative_mae_improvement(0.4, 0.3) == pytest.approx(0.25)


def test_coefficient_bootstrap_refit_required_and_deterministic():
    rows = [
        EligibleRow(
            t_ms=1578009600000 + i * 86_400_000,
            btc_side=1.0 if i % 2 == 0 else -1.0,
            abs_z_btc=0.5 + 0.37 * ((i * 3) % 5),
            rv_btc_24h=0.01 + 0.004 * ((i * 2) % 7),
            eth_confirmation=-0.5 + 0.31 * ((i * 5) % 4),
            y=0.08 + 0.01 * i - 0.03 * (-0.5 + 0.31 * ((i * 5) % 4)),
        )
        for i in range(8)
    ]
    a = coefficient_bootstrap(
        rows, block_length=3, replicates=4, rng=SplitMix64(RANDOM_SEED), refit=True
    )
    b = coefficient_bootstrap(
        rows, block_length=3, replicates=4, rng=SplitMix64(RANDOM_SEED), refit=True
    )
    assert list(a) == pytest.approx(list(b))
    with pytest.raises(Market05IntegrityError, match="must refit"):
        coefficient_bootstrap(
            rows, block_length=3, replicates=1, rng=SplitMix64(RANDOM_SEED), refit=False
        )
