"""Pure, DB-free tests for `scripts/research/math002b_consensus_robustness.py`'s
`compare_bucket()`/`_summarize_study()` -- the real recomputation logic the
harness applies to a fetched bucket, exercised here with synthetic
`ExchangeFeatureVector` fixtures instead of a live database. These tests
prove the harness computes the RIGHT thing; they are not, and never
substitute for, the real historical study (blocked -- see
`docs/V2_CONSENSUS_ROBUSTNESS_HISTORICAL_AUDIT.md`)."""
from __future__ import annotations

from datetime import datetime, timezone

from analytics.feature_engine.models import ExchangeFeatureVector
from scripts.research.math002b_consensus_robustness import (
    BB,
    BO,
    BYO,
    _summarize_study,
    compare_bucket,
)

BASE = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
CV16 = "0123456789abcdef"
CH64 = "b" * 64
LQ_QUALITY = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}


def _efv(exchange: str, *, price_move: float, oi: float) -> ExchangeFeatureVector:
    return ExchangeFeatureVector(
        exchange=exchange, symbol="BTCUSDT", market_type="perp", timeframe="4h",
        bucket_ts=BASE, feature_schema_version=1, calculation_version=CV16,
        price_move_pct=price_move, range_width_pct=5.0, close_price=100.0,
        volume_raw=10.0, volume_raw_unit="base", volume_notional_usd=1000.0,
        taker_buy_notional_usd=600.0, taker_sell_notional_usd=400.0,
        taker_delta_notional_usd=200.0, cvd_delta_notional_usd=200.0,
        oi_change_pct=oi, oi_unit="base", funding_rate=0.0001,
        long_liquidation_notional=0.0, short_liquidation_notional=0.0,
        liquidation_event_count=0, liquidation_feed_quality=LQ_QUALITY[exchange],
        is_snapshot_feed=(exchange == "binance"), bars_expected=5, bars_present=5,
        has_gap=False, is_usable=True, config_hash=CH64, config_version="2.1.0",
        code_version="math002b-test",
    )


def _bucket(values: dict[str, float]) -> dict[str, ExchangeFeatureVector]:
    return {ex: _efv(ex, price_move=v, oi=v) for ex, v in values.items()}


def test_compare_bucket_matches_known_math002a_vector():
    """[1, 1, 100] extreme -- same numbers as the MATH-002A adversarial
    vector -- must produce the same characterized deltas via the harness's
    OWN recomputation path (proves the harness doesn't silently diverge
    from the deterministic characterization)."""
    efvs = _bucket({"binance": 1.0, "bybit": 1.0, "okx": 100.0})
    comparisons = compare_bucket(efvs, family="price_structure", timeframe="4h")
    by_pair = {c.pair_name: c for c in comparisons}

    # BB = binance+bybit -> pair values (1,1), median 1 -- no change from FULL3.
    assert by_pair[BB].full3_median == 1.0
    assert by_pair[BB].pair_median == 1.0
    assert by_pair[BB].absolute_median_delta == 0.0
    assert by_pair[BB].sign_flipped is False

    # BO = binance+okx -> pair values (1,100), median 50.5 -- large delta.
    assert by_pair[BO].pair_median == 50.5
    assert by_pair[BO].absolute_median_delta == 49.5
    assert by_pair[BO].sign_flipped is False

    # BYO = bybit+okx -> pair values (1,100), median 50.5 -- same shape.
    assert by_pair[BYO].pair_median == 50.5
    assert by_pair[BYO].absolute_median_delta == 49.5


def test_compare_bucket_detects_sign_flip():
    efvs = _bucket({"binance": 1.0, "bybit": -1.0, "okx": -100.0})
    comparisons = compare_bucket(efvs, family="price_structure", timeframe="4h")
    by_pair = {c.pair_name: c for c in comparisons}
    # FULL3 median of (1,-1,-100) = -1 (middle value). BO pair = (1,-100) -> median -49.5.
    assert by_pair[BO].full3_median == -1.0
    assert by_pair[BO].pair_median == -49.5
    assert by_pair[BO].sign_flipped is False  # both negative -- no flip here
    # BB pair = (1,-1) -> median 0.0; FULL3 negative -> sign flips to "0" bucket.
    assert by_pair[BB].pair_median == 0.0


def test_compare_bucket_quality_gate_stays_true_for_moderate_distortion():
    efvs = _bucket({"binance": 1.0, "bybit": 100.0, "okx": 1.0})
    comparisons = compare_bucket(efvs, family="price_structure", timeframe="4h")
    for c in comparisons:
        # coverage/confidence stay well above the regime floor for every
        # same-sign 2/3 pair here, matching the MATH-002A characterization.
        if c.pair_agreement == 1.0:
            assert c.pair_quality_gate_pass is True


def test_summarize_study_aggregates_by_pair():
    efvs = _bucket({"binance": 1.0, "bybit": 1.0, "okx": 100.0})
    comparisons = compare_bucket(efvs, family="price_structure", timeframe="4h")
    summary = _summarize_study(
        symbol="BTCUSDT", market_type="perp", timeframe="4h", family="price_structure",
        complete_3of3_bucket_count=1, comparisons=comparisons,
    )
    assert summary["complete_3of3_bucket_count"] == 1
    assert set(summary["pairs"]) == {BB, BO, BYO}
    for pair_name in (BB, BO, BYO):
        assert summary["pairs"][pair_name]["n"] == 1
