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
  not identify one side as an outlier under the frozen threshold;
* this holds identically for EVERY N=2 contributor pair (Binance+Bybit,
  Binance+OKX, Bybit+OKX) -- the failure envelope is a property of "exactly
  two contributors", not of which venue happens to be omitted.

Amendment (research follow-up on merged PR #56): the original ``_compute()``
helper always assigned ``values`` via ``zip(EXCHANGES, values, ...)`` with
``EXCHANGES = ("binance", "bybit", "okx")``. Every N=2 vector therefore only
ever exercised Binance+Bybit (OKX always the omitted venue) -- a genuine test
coverage gap, not a production defect: the numerical conclusions PR #56 drew
were correct for the pair it actually tested, they just did not characterize
the other two N=2 pairs at all. This file now runs every N=2 adversarial
vector across all three pairs explicitly, and separately proves the pure
median/MAD math is symmetric with respect to venue LABELS (never claiming the
three venues are statistically equivalent as real-world data sources -- that
is a historical-data question, addressed separately in
``docs/V2_CONSENSUS_ROBUSTNESS_HISTORICAL_AUDIT.md``).
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
from analytics.forecasting_v2.bias_1h import (
    BIAS_MIN_AGREEMENT,
    BIAS_MIN_CONFIDENCE,
    BIAS_MIN_COVERAGE,
)
from analytics.forecasting_v2.compression_breakout import BREAKOUT_MIN_AGREEMENT
from analytics.forecasting_v2.regime_4h import (
    REGIME_MIN_AGREEMENT,
    REGIME_MIN_CONFIDENCE,
    REGIME_MIN_COVERAGE,
)
from analytics.forecasting_v2.setup_common import SETUP_MIN_CONFIDENCE, SETUP_MIN_COVERAGE

BASE = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
CV16 = "0123456789abcdef"
CH64 = "a" * 64
EXCHANGES = ("binance", "bybit", "okx")
LQ_QUALITY = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}
WEIGHTS = {"coverage": 0.50, "agreement": 0.30, "dispersion": 0.20}
ROBUST_Z_THRESHOLD = 3.5

# ---- MATH-002A amendment: explicit N=2 contributor pairs ------------------
# Every relevant N=2 adversarial vector must be exercised under all three,
# not only "omit OKX" (the accidental default of zip(EXCHANGES, values)).
PAIRS: dict[str, tuple[str, str]] = {
    "BB": ("binance", "bybit"),    # omit okx
    "BO": ("binance", "okx"),      # omit bybit
    "BYO": ("bybit", "okx"),       # omit binance
}


def _omitted(pair_name: str) -> str:
    contributing = set(PAIRS[pair_name])
    (omitted,) = (ex for ex in EXCHANGES if ex not in contributing)
    return omitted


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


def _compute(
    values: tuple[float, ...],
    *,
    exchanges: tuple[str, ...] = EXCHANGES,
    range_widths: tuple[float, ...] | None = None,
):
    """Compute real consensus for ``values`` assigned to ``exchanges`` (same
    order/length). Defaults to the canonical 3-venue order for N=3 vectors;
    callers exercising an N=2 pair pass ``exchanges=PAIRS[pair_name]``
    explicitly -- there is no implicit "always omit OKX" behavior any more."""
    assert len(values) == len(exchanges)
    if range_widths is None:
        range_widths = tuple(5.0 + i for i in range(len(values)))
    assert len(range_widths) == len(values)
    features = [
        _efv(exchange, price_move=value, oi=value, range_width=range_width)
        for exchange, value, range_width in zip(exchanges, values, range_widths)
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


# ============================================================================
# 3/3 control (unchanged from PR #56 -- kept as the baseline every 2/3 pair
# result below is compared against).
# ============================================================================
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


# ============================================================================
# MATH-002A amendment: EVERY required N=2 vector, run against ALL THREE
# contributor pairs (BB / BO / BYO), not only the accidental "omit OKX" case.
# ============================================================================
_TWO_VENUE_VECTORS = [
    ((1.0, 100.0), 50.5, 49.5, 1.0, 0.505, 73.43333333333334),
    ((-1.0, -100.0), -50.5, 49.5, 1.0, 0.505, 73.43333333333334),
    ((0.1, 10.0), 5.05, 4.95, 1.0, 0.505, 73.43333333333334),
    ((-0.1, -10.0), -5.05, 4.95, 1.0, 0.505, 73.43333333333334),
    ((1.0, -100.0), -49.5, 50.5, 0.5, 0.495, 58.233333333333334),
    ((-1.0, 100.0), 49.5, 50.5, 0.5, 0.495, 58.233333333333334),
    ((1.0, 1.0), 1.0, 0.0, 1.0, 1.0, 83.33333333333333),
    ((-1.0, -1.0), -1.0, 0.0, 1.0, 1.0, 83.33333333333333),
]


@pytest.mark.parametrize("pair_name", sorted(PAIRS))
@pytest.mark.parametrize(
    "values,expected_median,expected_mad,expected_agreement,expected_dispersion,expected_confidence",
    _TWO_VENUE_VECTORS,
)
def test_math002_requested_two_venue_vectors_all_pairs(
    pair_name,
    values,
    expected_median,
    expected_mad,
    expected_agreement,
    expected_dispersion,
    expected_confidence,
):
    """The full issue #52 N=2 vector matrix, run under every contributor
    pair. The median/MAD/agreement/confidence numbers are IDENTICAL across
    BB/BO/BYO for the same numeric pair -- proving the failure envelope
    depends only on "exactly 2 contributors exist", never on WHICH real
    venue happens to be the omitted one. Provenance (contributing/excluded
    venue identity) differs correctly per pair."""
    exchanges = PAIRS[pair_name]
    omitted = _omitted(pair_name)
    result = _compute(values, exchanges=exchanges)

    for family in ("price_structure", "oi"):
        coverage = result.coverage_by_metric[family]
        assert (coverage.available, coverage.expected, coverage.ratio) == (2, 3, 2.0 / 3.0)
        assert result.data_confidence_by_metric[family] == pytest.approx(expected_confidence)
        provenance = result.provenance_by_metric[family]
        assert provenance.contributing == tuple(sorted(exchanges))
        assert provenance.excluded == ((omitted, "MATH002A_SYNTHETIC_ABSENCE"),)

    assert result.price_move_pct_median == pytest.approx(expected_median)
    assert result.oi_change_pct_median == pytest.approx(expected_median)
    assert result.price_move_pct_mad == pytest.approx(expected_mad)
    assert result.oi_change_pct_mad == pytest.approx(expected_mad)
    assert result.price_direction_agreement == pytest.approx(expected_agreement)
    assert result.oi_direction_agreement == pytest.approx(expected_agreement)
    assert result.is_partial_consensus is True

    assert _dispersion(expected_median, expected_mad) == pytest.approx(expected_dispersion)
    assert _family_confidence(
        coverage=2.0 / 3.0,
        agreement=expected_agreement,
        dispersion=expected_dispersion,
    ) == pytest.approx(expected_confidence)


@pytest.mark.parametrize("pair_name", sorted(PAIRS))
def test_math002_two_venue_median_loses_single_outlier_resistance_all_pairs(pair_name):
    exchanges = PAIRS[pair_name]
    full = _compute((1.0, 1.0, 100.0))
    partial = _compute((1.0, 100.0), exchanges=exchanges)

    assert full.price_move_pct_median == 1.0
    assert partial.price_move_pct_median == 50.5
    assert abs(partial.price_move_pct_median - full.price_move_pct_median) == 49.5

    assert full.oi_change_pct_median == 1.0
    assert partial.oi_change_pct_median == 50.5


@pytest.mark.parametrize("pair_name", sorted(PAIRS))
def test_math002_same_sign_two_venue_extremes_keep_full_direction_agreement_all_pairs(pair_name):
    exchanges = PAIRS[pair_name]
    for values in ((1.0, 100.0), (-1.0, -100.0), (0.1, 10.0), (-0.1, -10.0)):
        result = _compute(values, exchanges=exchanges)
        assert result.price_direction_agreement == 1.0
        assert result.oi_direction_agreement == 1.0


@pytest.mark.parametrize("pair_name", sorted(PAIRS))
def test_math002_opposite_sign_pair_reduces_direction_agreement_all_pairs(pair_name):
    exchanges = PAIRS[pair_name]
    for values in ((1.0, -100.0), (-1.0, 100.0)):
        result = _compute(values, exchanges=exchanges)
        assert result.price_direction_agreement == 0.5
        assert result.oi_direction_agreement == 0.5


@pytest.mark.parametrize("pair_name", sorted(PAIRS))
def test_math002_two_unequal_contributors_are_symmetric_and_not_flagged_as_outliers_all_pairs(
    pair_name,
):
    exchanges = PAIRS[pair_name]
    values = (1.0, 100.0)
    result = _compute(values, exchanges=exchanges)
    median = result.price_move_pct_median
    mad = result.price_move_pct_mad

    assert median == 50.5
    assert mad == 49.5
    robust_z = tuple(ROBUST_Z_SCALE * (value - median) / mad for value in values)
    assert robust_z[0] == pytest.approx(-ROBUST_Z_SCALE)
    assert robust_z[1] == pytest.approx(ROBUST_Z_SCALE)
    assert ROBUST_Z_SCALE == pytest.approx(0.67448975, abs=1e-8)
    assert all(abs(value) < ROBUST_Z_THRESHOLD for value in robust_z)
    assert "price_move_pct" not in result.outlier_exchanges
    assert "oi_change_pct" not in result.outlier_exchanges


@pytest.mark.parametrize("pair_name", sorted(PAIRS))
def test_math002_equal_pair_has_full_dispersion_and_no_outlier_report_all_pairs(pair_name):
    exchanges = PAIRS[pair_name]
    result = _compute((1.0, 1.0), exchanges=exchanges)
    assert result.price_move_pct_mad == 0.0
    assert result.oi_change_pct_mad == 0.0
    assert _dispersion(result.price_move_pct_median, result.price_move_pct_mad) == 1.0
    assert "price_move_pct" not in result.outlier_exchanges
    assert "oi_change_pct" not in result.outlier_exchanges


@pytest.mark.parametrize("pair_name", sorted(PAIRS))
def test_math002_range_width_uses_valid_positive_two_venue_values_all_pairs(pair_name):
    exchanges = PAIRS[pair_name]
    result = _compute((1.0, 100.0), exchanges=exchanges, range_widths=(0.1, 10.0))
    assert result.range_width_pct_median == pytest.approx(5.05)
    assert result.range_width_pct_median > 0.0


def test_math002_partial_consensus_preserves_contributor_provenance_all_pairs():
    for pair_name, exchanges in PAIRS.items():
        result = _compute((1.0, 100.0), exchanges=exchanges)
        assert result.is_partial_consensus is True
        omitted = _omitted(pair_name)
        for family in ("price_structure", "oi"):
            provenance = result.provenance_by_metric[family]
            assert provenance.contributing == tuple(sorted(exchanges))
            assert provenance.excluded == ((omitted, "MATH002A_SYNTHETIC_ABSENCE"),)


# ============================================================================
# Venue-label symmetry: the pure median/MAD math must not depend on WHICH
# venue reports WHICH value, nor on which pair is used, for the same numeric
# multiset. This proves the IMPLEMENTATION's math is symmetric with respect
# to venue identity -- it does NOT claim the three real exchanges are
# statistically equivalent data sources (that is a historical-data question,
# addressed separately, not a pure-math one).
# ============================================================================
def test_math002_median_mad_are_identical_across_all_three_pairs_for_same_values():
    """Same numeric pair, three different venue-identity assignments (which
    two real venues hold the values) -- median/MAD must be byte-identical."""
    results = {
        pair_name: _compute((1.0, 100.0), exchanges=exchanges)
        for pair_name, exchanges in PAIRS.items()
    }
    medians = {r.price_move_pct_median for r in results.values()}
    mads = {r.price_move_pct_mad for r in results.values()}
    agreements = {r.price_direction_agreement for r in results.values()}
    confidences = {
        round(r.data_confidence_by_metric["price_structure"], 12) for r in results.values()
    }
    assert medians == {50.5}
    assert mads == {49.5}
    assert agreements == {1.0}
    assert len(confidences) == 1


def test_math002_swapping_which_venue_holds_which_value_does_not_change_median_mad():
    """Within ONE pair (Binance+OKX), swap which of the two venues reports
    the low value vs the high value -- median/MAD are unchanged. Proves
    venue LABEL (not venue ordinal position) never enters the arithmetic."""
    forward = _compute((1.0, 100.0), exchanges=("binance", "okx"))
    reversed_ = _compute((100.0, 1.0), exchanges=("binance", "okx"))
    assert forward.price_move_pct_median == reversed_.price_move_pct_median == 50.5
    assert forward.price_move_pct_mad == reversed_.price_move_pct_mad == 49.5
    assert forward.oi_change_pct_median == reversed_.oi_change_pct_median == 50.5
    # Contributing venue SET is identical either way -- only which venue
    # reported which raw number differs, and that has no effect on the
    # symmetric aggregate.
    assert (
        forward.provenance_by_metric["price_structure"].contributing
        == reversed_.provenance_by_metric["price_structure"].contributing
    )


# ============================================================================
# Exact current V2 quality-gate characterization (research-follow-up
# amendment). PR #56 imported only REGIME_* constants and phrased its
# assertions more broadly than what was actually checked. This section makes
# explicit, by name, which distinct frozen floor each family/detector
# actually uses -- 4h regime, 1h bias, and Stage-5 shared setup floors are
# SEPARATE constants that currently happen to share the same numeric values
# (50.0 / 2/3), never assumed equal. `compression_breakout`'s own
# `BREAKOUT_MIN_AGREEMENT` is the one Stage-5 family-specific directional
# gate actually reachable from `price_structure` data alone;
# `trend_pullback`/`confirmed_breakout` have no analogous named agreement
# constant of their own (inspected directly -- neither module declares one).
#
# IMPORTANT: passing these row-level quality floors is necessary but NOT
# sufficient for a Stage-5 setup to qualify -- a real setup additionally
# requires its own structural conditions (fresh crossing, compression run,
# retracement zone, taker-flow sign, etc.). These tests characterize ONLY
# the shared row-level quality gate every family/detector reads from the
# SAME consensus row, never a claim that a full setup would fire.
# ============================================================================
def test_math002_two_of_three_stays_above_every_current_quality_floor():
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
        for pair_name, exchanges in PAIRS.items():
            result = _compute(values, exchanges=exchanges)
            for family in ("price_structure", "oi"):
                ratio = result.coverage_by_metric[family].ratio
                confidence = result.data_confidence_by_metric[family]
                # 4h regime floor
                assert ratio >= REGIME_MIN_COVERAGE
                assert confidence >= REGIME_MIN_CONFIDENCE
                # 1h bias floor -- a DISTINCT named constant, checked
                # separately (not assumed equal to the regime floor).
                assert ratio >= BIAS_MIN_COVERAGE
                assert confidence >= BIAS_MIN_CONFIDENCE
                # Stage-5 shared setup floor -- also a DISTINCT named
                # constant, checked separately.
                assert ratio >= SETUP_MIN_COVERAGE
                assert confidence >= SETUP_MIN_CONFIDENCE


def test_math002_same_sign_two_of_three_passes_every_current_agreement_floor():
    for values in ((1.0, 100.0), (-1.0, -100.0), (0.1, 10.0), (-0.1, -10.0)):
        for exchanges in PAIRS.values():
            result = _compute(values, exchanges=exchanges)
            agreement = result.price_direction_agreement
            assert agreement >= REGIME_MIN_AGREEMENT
            assert agreement >= BIAS_MIN_AGREEMENT
            assert agreement >= BREAKOUT_MIN_AGREEMENT


def test_math002_opposite_sign_two_of_three_fails_every_current_agreement_floor():
    for values in ((1.0, -100.0), (-1.0, 100.0)):
        for exchanges in PAIRS.values():
            result = _compute(values, exchanges=exchanges)
            assert result.coverage_by_metric["price_structure"].ratio >= REGIME_MIN_COVERAGE
            assert result.data_confidence_by_metric["price_structure"] >= REGIME_MIN_CONFIDENCE
            agreement = result.price_direction_agreement
            # Each agreement floor checked by its own name -- currently all
            # three happen to equal 2/3, but that is verified, not assumed.
            assert agreement < REGIME_MIN_AGREEMENT
            assert agreement < BIAS_MIN_AGREEMENT
            assert agreement < BREAKOUT_MIN_AGREEMENT


def test_math002_named_quality_constants_are_not_assumed_equal_they_are_checked():
    """Documents the CURRENT numeric relationship explicitly rather than
    silently relying on it. If a future PR changes one floor independently
    of the others, this test -- not a passing assumption baked into the
    tests above -- is what will catch the divergence."""
    assert REGIME_MIN_CONFIDENCE == BIAS_MIN_CONFIDENCE == SETUP_MIN_CONFIDENCE == 50.0
    assert REGIME_MIN_COVERAGE == BIAS_MIN_COVERAGE == SETUP_MIN_COVERAGE == pytest.approx(2.0 / 3.0)
    assert REGIME_MIN_AGREEMENT == BIAS_MIN_AGREEMENT == BREAKOUT_MIN_AGREEMENT == pytest.approx(2.0 / 3.0)
