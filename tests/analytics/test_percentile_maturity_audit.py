"""MATH-001 / issue #51 adversarial percentile-maturity vectors.

These tests intentionally DO NOT introduce a new density gate. They freeze and
make explicit the current Stage 2.1 contract: percentile confidence_tier is
calendar-span based once at least two non-NULL historical observations exist.
The vectors quantify the rank resolution available at small N and prove the
same sparse-span behavior is reachable for every percentile identity V2-v0
currently requires.

Pure tests only: no DB, network, wall clock, runtime orchestration, or future
returns. They are research-governance evidence, not a model redesign.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from analytics.percentile_engine import (
    ConfidenceTierThresholds,
    PercentileRequest,
    PercentileSample,
    compute_percentile_snapshot,
)

B = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
CV = "0123456789abcdef"
CFG = "a" * 64
THRESHOLDS = ConfidenceTierThresholds(3, 7, 30)
MINUTE = timedelta(minutes=1)
DAY = timedelta(days=1)


def _sample(*, ts: datetime, value: float, metric: str, timeframe: str) -> PercentileSample:
    return PercentileSample(
        scope="consensus",
        exchange="",
        symbol="BTCUSDT",
        market_type="perp",
        metric=metric,
        timeframe=timeframe,
        bucket_ts=ts,
        value=value,
        feature_schema_version=1,
        calculation_version=CV,
    )


def _snapshot(
    *,
    metric: str = "price_move_pct_median",
    timeframe: str = "4h",
    window: str = "30d",
    current: float = 999.0,
    values: tuple[float, ...] = (1.0, 2.0),
    earliest_delta: timedelta = 30 * DAY,
):
    # First observation controls confidence span; remaining observations are
    # intentionally clustered near B to make internal missingness explicit.
    samples = [
        _sample(ts=B - earliest_delta, value=values[0], metric=metric, timeframe=timeframe)
    ]
    for i, value in enumerate(values[1:], start=1):
        samples.append(
            _sample(ts=B - i * MINUTE, value=value, metric=metric, timeframe=timeframe)
        )
    return compute_percentile_snapshot(
        PercentileRequest(
            scope="consensus",
            exchange="",
            symbol="BTCUSDT",
            market_type="perp",
            metric=metric,
            timeframe=timeframe,
            percentile_window=window,
            bucket_ts=B,
            value=current,
            samples=tuple(samples),
            confidence_tier_thresholds=THRESHOLDS,
            config_hash=CFG,
            config_version="2.1.0",
            code_version="audit",
            feature_schema_version=1,
            calculation_version=CV,
        )
    )


@pytest.mark.parametrize("n", [2, 3, 5, 10])
def test_long_span_small_n_can_be_mature_and_rank_extreme(n):
    """Calendar span, not observation count/density, controls maturity."""
    snap = _snapshot(values=tuple(float(i) for i in range(1, n + 1)))
    assert snap.sample_size == n
    assert snap.confidence_tier == "mature"
    assert snap.percentile_rank == 1.0


def test_two_identical_sparse_samples_have_midrank_half():
    snap = _snapshot(values=(5.0, 5.0), current=5.0)
    assert snap.sample_size == 2
    assert snap.confidence_tier == "mature"
    assert snap.percentile_rank == 0.5


def test_sparse_long_span_and_dense_short_span_are_distinct_concepts():
    sparse = _snapshot(values=(1.0, 2.0), earliest_delta=30 * DAY)
    dense_short = _snapshot(
        values=tuple(float(i) for i in range(1, 11)),
        earliest_delta=2 * DAY,
    )
    assert sparse.sample_size == 2
    assert sparse.confidence_tier == "mature"
    assert dense_short.sample_size == 10
    assert dense_short.confidence_tier == "none"


@pytest.mark.parametrize(
    "delta, expected_tier",
    [
        (3 * DAY - MINUTE, "none"),
        (3 * DAY, "low"),
        (7 * DAY - MINUTE, "low"),
        (7 * DAY, "building"),
        (30 * DAY - MINUTE, "building"),
        (30 * DAY, "mature"),
    ],
)
def test_two_sample_exact_tier_boundaries(delta, expected_tier):
    snap = _snapshot(values=(1.0, 2.0), earliest_delta=delta)
    assert snap.sample_size == 2
    assert snap.confidence_tier == expected_tier


@pytest.mark.parametrize(
    "metric,timeframe,window,current,expected_tier,expected_rank",
    [
        # regime_4h price evidence
        ("price_move_pct_median", "4h", "30d", 999.0, "mature", 1.0),
        # regime_4h compression evidence
        ("range_width_pct_median", "4h", "30d", 0.0, "mature", 0.0),
        # bias_1h price evidence: 7d is structurally capped at building
        ("price_move_pct_median", "1h", "7d", 999.0, "building", 1.0),
        # compression_breakout 15m compression evidence
        ("range_width_pct_median", "15m", "30d", 0.0, "mature", 0.0),
    ],
)
def test_sparse_two_sample_vectors_cover_every_mandatory_v2_percentile_identity(
    metric, timeframe, window, current, expected_tier, expected_rank
):
    earliest = 7 * DAY if window == "7d" else 30 * DAY
    snap = _snapshot(
        metric=metric,
        timeframe=timeframe,
        window=window,
        current=current,
        values=(1.0, 2.0),
        earliest_delta=earliest,
    )
    assert snap.sample_size == 2
    assert snap.confidence_tier == expected_tier
    assert snap.percentile_rank == expected_rank


@pytest.mark.parametrize(
    "n,current,expected_rank",
    [
        # With distinct historical values 1..N and current equal to an observed
        # value k, mid-rank is (k - 0.5) / N. These concrete points show the
        # coarse finite-N rank lattice without claiming statistical reliability.
        (2, 2.0, 0.75),
        (3, 3.0, 5.0 / 6.0),
        (5, 4.0, 0.7),
        (10, 7.0, 0.65),
    ],
)
def test_small_n_midrank_resolution_examples(n, current, expected_rank):
    snap = _snapshot(
        values=tuple(float(i) for i in range(1, n + 1)),
        current=current,
    )
    assert snap.sample_size == n
    assert snap.percentile_rank == expected_rank


def test_two_sample_rank_can_cross_all_frozen_v2_percentile_thresholds():
    """Numerical reachability only; this is NOT evidence that N=2 is reliable."""
    # Positive price evidence: p=.75 -> E=.50, clearing both 4h=.40 and 1h=.25.
    positive = _snapshot(values=(1.0, 2.0), current=2.0)
    p = positive.percentile_rank
    assert p == 0.75
    assert max(0.0, 2.0 * p - 1.0) == 0.5
    assert 0.5 >= 0.40
    assert 0.5 >= 0.25

    # Compression: p=0 -> score=1, clearing compression=.75.
    compressed = _snapshot(
        metric="range_width_pct_median", values=(1.0, 2.0), current=0.0
    )
    assert compressed.percentile_rank == 0.0
    assert 1.0 - compressed.percentile_rank == 1.0
    assert 1.0 >= 0.75
