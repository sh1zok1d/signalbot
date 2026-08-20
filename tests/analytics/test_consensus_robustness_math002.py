"""MATH-002A / issue #52 deterministic 2-of-3 consensus characterization.

Pure measurement-layer tests only. They exercise the real
``compute_consensus_features(...)`` entry point and intentionally do NOT alter
production consensus semantics, V2 thresholds, config, schemas, or versioning.

The purpose is to make the allowed 2/3 failure envelope explicit before any
historical robustness study or remedy decision:

* with 3 contributors, a median resists one extreme venue;
* with 2 contributors, the median is the arithmetic midpoint;
* same-sign 2/3 can retain full direction agreement despite large magnitude
  disagreement;
* two-point robust-z scores are symmetric around the midpoint and therefore do
  not identify one side as an outlier under the frozen threshold.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from analytics.feature_engine.consensus import compute_consensus_features
from analytics.feature_engine.consensus_models import (
    FAMILIES,
    OUTLIER_REASON_MAD_ZERO,
    ROBUST_Z_SCALE,
    ConsensusFeatureRequest,
)
from analytics.feature_engine.models import ExchangeFeatureVector
from analytics.forecasting_v2.regime_4h import (
    REGIME_MIN_AGREEMENT,
    REGIME_MIN_CONFIDENCE,
    REGIME_MIN_COVERAGE,
)

BASE = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
CV16 = "0123456789abcdef"
CH64 = "a" * 64
EXCHANGES = ("binance", "bybit", "okx")
LQ_QUALITY = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}
WEIGHTS = {"coverage": 0.50, "agreement": 0.30, "dispersion": 0.20}
ROBUST_Z_THRESHOLD = 3.5


def _efv(
    exchange: str,
    *,
    price_move: float,
    oi: float,
    range_width: float = 5.0,
) -> ExchangeFeatureVector:
    return ExchangeFeatureVector(
        exchange=exchange,
        symbol="BTCUSDT",
        market_type="perp",
        timeframe="5m",
        bucket_ts=BASE,
        feature_schema_version=1,
        calculation_version=CV16,
        price_move_pct=price_move,
        range_width_pct=range_width,
        close_price=100.0,
        volume_raw=10.0,
        volume_raw_unit="base",
        volume_notional_usd=1000.0,
        taker_buy_notional_usd=600.0,
        taker_sell_notional_usd=400.0,
        taker_delta_notional_usd=200.0,
        cvd_delta_notional_usd=200.0,
        oi_change_pct=oi,
        oi_unit="base",
        funding_rate=0.0001,
        long_liquidation_notional=0.0,
        short_liquidation_notional=0.0,
        liquidation_event_count=0,
        liquidation_feed_quality=LQ_QUALITY[exchange],
        is_snapshot_feed=(exchange == "binance"),
        bars_expected=5,
        bars_present=5,
        has_gap=False,
        is_usable=True,
        config_hash=CH64,
        config_version="2.1.0",
        code_version="math002a",
    )


def _request(features: list[ExchangeFeatureVector]) -> ConsensusFeatureRequest:
    present = {feature.exchange for feature in features}
    missing = tuple(exchange for exchange in EXCHANGES if exchange not in present)
    exclusions = {
        family: {exchange: "MATH002A_SYNTHETIC_ABSENCE" for exchange in missing}
        for family in FAMILIES
        if missing
    }
    return ConsensusFeatureRequest(
        symbol="BTCUSDT",
        market_type="perp",
        timeframe="5m",
        bucket_ts=BASE,
        feature_schema_version=1,
        calculation_version=CV16,
        config_hash=CH64,
        config_version="2.1.0",
        code_version="math002a",
        exchange_features=features,
        expected_exchanges_by_family={family: EXCHANGES for family in FAMILIES},
        exclusion_reasons_by_family=exclusions,
        minimum_exchange_coverage=2,
        confidence_weights=WEIGHTS,
        robust_z_threshold=ROBUST_Z_THRESHOLD,
    )


def _compute(values: tuple[float, ...], *, range_widths: tuple[float, ...] | None = None):
    assert len(values) in (2, 3)
    if range_widths is None:
        range_widths = tuple(5.0 + i for i in range(len(values)))
    assert len(range_widths) == len(values)
    features = [
        _efv(exchange, price_move=value, oi=value, range_width=range_width)
        for exchange, value, range_width in zip(EXCHANGES, values, range_widths)
    ]
    return compute_consensus_features(_request(features))


def _dispersion(median: float, mad: float) -> float:
    if mad == 0:
        return 1.0
    if median == 0:
        return 0.0
    return 1.0 / (1.0 + mad / abs(median))


def _family_confidence(*, coverage: float, agreement: float, dispersion: float) -> float:
    return 100.0 * (
        WEIGHTS["coverage"] * coverage
        + WEIGHTS["agreement"] * agreement
        + WEIGHTS["dispersion"] * dispersion
    )


def test_math002_three_venue_median_resists_one_extreme():
    result = _compute((1.0, 1.0, 100.0))

    assert result.price_move_pct_median == 1.0
    assert result.oi_change_pct_median == 1.0
    assert result.price_move_pct_mad == 0.0
    assert result.oi_change_pct_mad == 0.0
    assert result.price_direction_agreement == 1.0
    assert result.oi_direction_agreement == 1.0
    assert result.data_confidence_by_metric["price_structure"] == pytest.approx(100.0)
    assert result.data_confidence_by_metric["oi"] == pytest.approx(100.0)

    for metric in ("price_move_pct", "oi_change_pct"):
        assert tuple(result.outlier_exchanges[metric]) == ("okx",)
        entry = result.outlier_exchanges[metric]["okx"]
        assert entry.robust_z is None
        assert entry.reason == OUTLIER_REASON_MAD_ZERO


@pytest.mark.parametrize(
    "values,expected_median,expected_mad,expected_agreement,expected_dispersion,expected_confidence",
    [
        ((1.0, 100.0), 50.5, 49.5, 1.0, 0.505, 73.43333333333334),
        ((-1.0, -100.0), -50.5, 49.5, 1.0, 0.505, 73.43333333333334),
        ((0.1, 10.0), 5.05, 4.95, 1.0, 0.505, 73.43333333333334),
        ((-0.1, -10.0), -5.05, 4.95, 1.0, 0.505, 73.43333333333334),
        ((1.0, -100.0), -49.5, 50.5, 0.5, 0.495, 58.233333333333334),
        ((-1.0, 100.0), 49.5, 50.5, 0.5, 0.495, 58.233333333333334),
        ((1.0, 1.0), 1.0, 0.0, 1.0, 1.0, 83.33333333333333),
        ((-1.0, -1.0), -1.0, 0.0, 1.0, 1.0, 83.33333333333333),
    ],
)
def test_math002_requested_two_venue_vectors(
    values,
    expected_median,
    expected_mad,
    expected_agreement,
    expected_dispersion,
    expected_confidence,
):
    result = _compute(values)

    for family in ("price_structure", "oi"):
        coverage = result.coverage_by_metric[family]
        assert (coverage.available, coverage.expected, coverage.ratio) == (2, 3, 2.0 / 3.0)
        assert result.data_confidence_by_metric[family] == pytest.approx(expected_confidence)

    assert result.price_move_pct_median == pytest.approx(expected_median)
    assert result.oi_change_pct_median == pytest.approx(expected_median)
    assert result.price_move_pct_mad == pytest.approx(expected_mad)
    assert result.oi_change_pct_mad == pytest.approx(expected_mad)
    assert result.price_direction_agreement == pytest.approx(expected_agreement)
    assert result.oi_direction_agreement == pytest.approx(expected_agreement)

    assert _dispersion(expected_median, expected_mad) == pytest.approx(expected_dispersion)
    assert _family_confidence(
        coverage=2.0 / 3.0,
        agreement=expected_agreement,
        dispersion=expected_dispersion,
    ) == pytest.approx(expected_confidence)


def test_math002_two_venue_median_loses_single_outlier_resistance():
    full = _compute((1.0, 1.0, 100.0))
    partial = _compute((1.0, 100.0))

    assert full.price_move_pct_median == 1.0
    assert partial.price_move_pct_median == 50.5
    assert abs(partial.price_move_pct_median - full.price_move_pct_median) == 49.5
    assert partial.price_move_pct_median / full.price_move_pct_median == 50.5

    assert full.oi_change_pct_median == 1.0
    assert partial.oi_change_pct_median == 50.5


def test_math002_same_sign_two_venue_extremes_keep_full_direction_agreement():
    for values in ((1.0, 100.0), (-1.0, -100.0), (0.1, 10.0), (-0.1, -10.0)):
        result = _compute(values)
        assert result.price_direction_agreement == 1.0
        assert result.oi_direction_agreement == 1.0


def test_math002_opposite_sign_pair_reduces_direction_agreement():
    for values in ((1.0, -100.0), (-1.0, 100.0)):
        result = _compute(values)
        assert result.price_direction_agreement == 0.5
        assert result.oi_direction_agreement == 0.5


def test_math002_two_unequal_contributors_are_symmetric_and_not_flagged_as_outliers():
    values = (1.0, 100.0)
    result = _compute(values)
    median = result.price_move_pct_median
    mad = result.price_move_pct_mad

    assert median == 50.5
    assert mad == 49.5
    robust_z = tuple(ROBUST_Z_SCALE * (value - median) / mad for value in values)
    assert robust_z[0] == pytest.approx(-ROBUST_Z_SCALE)
    assert robust_z[1] == pytest.approx(ROBUST_Z_SCALE)
    assert all(abs(value) < ROBUST_Z_THRESHOLD for value in robust_z)
    assert "price_move_pct" not in result.outlier_exchanges
    assert "oi_change_pct" not in result.outlier_exchanges


def test_math002_equal_pair_has_full_dispersion_and_no_outlier_report():
    result = _compute((1.0, 1.0))
    assert result.price_move_pct_mad == 0.0
    assert result.oi_change_pct_mad == 0.0
    assert _dispersion(result.price_move_pct_median, result.price_move_pct_mad) == 1.0
    assert "price_move_pct" not in result.outlier_exchanges
    assert "oi_change_pct" not in result.outlier_exchanges


def test_math002_range_width_uses_valid_positive_two_venue_values():
    result = _compute((1.0, 100.0), range_widths=(0.1, 10.0))
    assert result.range_width_pct_median == pytest.approx(5.05)
    assert result.range_width_pct_median > 0.0


def test_math002_two_of_three_stays_above_current_quality_floors():
    for values in (
        (1.0, 100.0),
        (-1.0, -100.0),
        (0.1, 10.0),
        (-0.1, -10.0),
        (1.0, -100.0),
        (-1.0, 100.0),
        (1.0, 1.0),
        (-1.0, -1.0),
    ):
        result = _compute(values)
        for family in ("price_structure", "oi"):
            assert result.coverage_by_metric[family].ratio >= REGIME_MIN_COVERAGE
            assert result.data_confidence_by_metric[family] >= REGIME_MIN_CONFIDENCE


def test_math002_same_sign_two_of_three_also_passes_regime_agreement_floor():
    for values in ((1.0, 100.0), (-1.0, -100.0), (0.1, 10.0), (-0.1, -10.0)):
        result = _compute(values)
        assert result.price_direction_agreement >= REGIME_MIN_AGREEMENT


def test_math002_opposite_sign_two_of_three_fails_only_the_separate_agreement_floor():
    for values in ((1.0, -100.0), (-1.0, 100.0)):
        result = _compute(values)
        assert result.coverage_by_metric["price_structure"].ratio >= REGIME_MIN_COVERAGE
        assert result.data_confidence_by_metric["price_structure"] >= REGIME_MIN_CONFIDENCE
        assert result.price_direction_agreement < REGIME_MIN_AGREEMENT


def test_math002_partial_consensus_preserves_contributor_provenance():
    result = _compute((1.0, 100.0))
    assert result.is_partial_consensus is True
    for family in ("price_structure", "oi"):
        provenance = result.provenance_by_metric[family]
        assert provenance.contributing == ("binance", "bybit")
        assert provenance.excluded == (("okx", "MATH002A_SYNTHETIC_ABSENCE"),)
