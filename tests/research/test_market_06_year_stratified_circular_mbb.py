"""Synthetic-year tests for MARKET-06 year-stratified circular MBB.

Does not inspect market OHLC, dislocation, eligible-row counts, MAE, or
coefficients. Labels are fake year tokens only.
"""

from __future__ import annotations

from pathlib import Path

from scripts.research.market_06_year_stratified_circular_mbb import (
    BLOCK_LENGTH_DAYS,
    BOOTSTRAP_REPLICATES,
    RANDOM_SEED,
    concatenated_then_sample,
    pcg64_generator,
    year_stratified_predictive_resample,
)

SAMPLER_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "research"
    / "market_06_year_stratified_circular_mbb.py"
)


def _labeled(year: int, n: int) -> list[tuple[int, str]]:
    return [(year, f"{year}-{i:04d}") for i in range(n)]


def test_year_stratified_preserves_n_and_forbids_cross_year_blocks():
    seq_2023 = _labeled(2023, 20)
    seq_2024 = _labeled(2024, 18)
    rng = pcg64_generator(RANDOM_SEED)
    boot_2023, boot_2024, blocks_2023, blocks_2024 = (
        year_stratified_predictive_resample(
            seq_2023, seq_2024, block_length=BLOCK_LENGTH_DAYS, rng=rng
        )
    )
    assert len(boot_2023) == 20
    assert len(boot_2024) == 18
    assert all(item[0] == 2023 for item in boot_2023)
    assert all(item[0] == 2024 for item in boot_2024)
    pooled = boot_2023 + boot_2024
    assert [item[0] for item in pooled[:20]] == [2023] * 20
    assert [item[0] for item in pooled[20:]] == [2024] * 18
    for block in blocks_2023:
        assert len(block) == BLOCK_LENGTH_DAYS
        assert all(0 <= i < 20 for i in block)
    for block in blocks_2024:
        assert len(block) == BLOCK_LENGTH_DAYS
        assert all(0 <= i < 18 for i in block)


def test_5000_replicates_never_cross_year_and_preserve_counts():
    seq_2023 = _labeled(2023, 30)
    seq_2024 = _labeled(2024, 25)
    rng = pcg64_generator(RANDOM_SEED)
    assert BOOTSTRAP_REPLICATES == 5000
    assert RANDOM_SEED == 2026092106
    assert BLOCK_LENGTH_DAYS == 14
    for _ in range(BOOTSTRAP_REPLICATES):
        boot_2023, boot_2024, blocks_2023, blocks_2024 = (
            year_stratified_predictive_resample(
                seq_2023, seq_2024, block_length=BLOCK_LENGTH_DAYS, rng=rng
            )
        )
        assert len(boot_2023) == 30
        assert len(boot_2024) == 25
        assert all(item[0] == 2023 for item in boot_2023)
        assert all(item[0] == 2024 for item in boot_2024)
        for block in blocks_2023:
            years = {seq_2023[i][0] for i in block}
            assert years == {2023}
        for block in blocks_2024:
            years = {seq_2024[i][0] for i in block}
            assert years == {2024}


def test_concatenated_before_sampling_can_cross_year_and_is_forbidden():
    seq_2023 = _labeled(2023, 16)
    seq_2024 = _labeled(2024, 16)
    crossed = False
    rng = pcg64_generator(RANDOM_SEED)
    for _ in range(200):
        _sample, blocks = concatenated_then_sample(
            seq_2023, seq_2024, block_length=BLOCK_LENGTH_DAYS, rng=rng
        )
        combined = list(seq_2023) + list(seq_2024)
        for block in blocks:
            years = {combined[i][0] for i in block}
            if years == {2023, 2024}:
                crossed = True
                break
        if crossed:
            break
    assert crossed is True


def test_circular_wrap_stays_inside_year_when_n_less_than_block():
    seq_2023 = _labeled(2023, 10)
    seq_2024 = _labeled(2024, 9)
    rng = pcg64_generator(RANDOM_SEED)
    boot_2023, boot_2024, blocks_2023, blocks_2024 = (
        year_stratified_predictive_resample(
            seq_2023, seq_2024, block_length=BLOCK_LENGTH_DAYS, rng=rng
        )
    )
    assert len(boot_2023) == 10
    assert len(boot_2024) == 9
    assert all(item[0] == 2023 for item in boot_2023)
    assert all(item[0] == 2024 for item in boot_2024)
    for block in blocks_2023:
        assert all(0 <= i < 10 for i in block)
        assert {seq_2023[i][0] for i in block} == {2023}
    for block in blocks_2024:
        assert all(0 <= i < 9 for i in block)
        assert {seq_2024[i][0] for i in block} == {2024}


def test_sampler_module_does_not_refit_predictive_models():
    src = SAMPLER_PATH.read_text(encoding="utf-8").lower()
    for token in (
        "lstsq",
        "linearregression",
        "numpy.linalg.solve",
        ".fit(",
        "refit",
    ):
        assert token not in src
