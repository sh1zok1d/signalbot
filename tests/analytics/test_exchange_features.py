"""Unit tests for analytics/feature_engine/exchange_features.py (pure)."""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from common.instrument_metadata import InstrumentMetadata
from analytics.feature_engine.exchange_features import (
    FeatureError, _price_features, compute_exchange_features,
)
from analytics.feature_engine.models import (
    ExchangeFeatureRequest, ExchangeFeatureVector, FundingObservation,
    KlineBar, LiquidationEvent, LiquidationFeedState, OpenInterestObservation,
)

BASE = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
CV16 = "0123456789abcdef"
CH64 = "a" * 64


def _meta(unit="base", mult=None, *, exchange="binance", symbol="BTCUSDT",
          market_type="perp"):
    return InstrumentMetadata(
        exchange=exchange, symbol=symbol, market_type=market_type,
        exchange_instrument_id="ID", quantity_unit=unit, contract_multiplier=mult,
        tick_size=0.1, price_precision=None, quantity_precision=None,
        metadata_source="exchange_api", fetched_at=BASE, is_stale=False)


def _bar(minute, o=100.0, h=105.0, lo=99.0, c=102.0, v=10.0, tb=None, ts_=None,
         sec=0):
    return KlineBar(ts=BASE + timedelta(minutes=minute, seconds=sec),
                    open=o, high=h, low=lo, close=c, volume=v,
                    taker_buy_volume=tb, taker_sell_volume=ts_)


def _feed(is_available=True, coverage="full", snapshot=False):
    return LiquidationFeedState(is_available=is_available, coverage_type=coverage,
                                is_snapshot_feed=snapshot)


def _req(**kw):
    d = dict(
        exchange="binance", symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=BASE, feature_schema_version=1, calculation_version=CV16,
        config_hash=CH64, config_version="2.1.0", code_version="test-v1",
        bars=[], open_interest=[], funding=[], liquidations=[],
        liquidation_feed_state=_feed(), instrument_metadata=_meta("base"),
        allowed_missing_bars=0,
    )
    d.update(kw)
    return ExchangeFeatureRequest(**d)


def _bars_5m(with_taker=True):
    out = []
    for m in range(5):
        tb = (m + 1.0) if with_taker else None
        ts_ = (m + 0.5) if with_taker else None
        out.append(_bar(m, o=100.0 + m, h=110.0 + m, lo=95.0 + m, c=101.0 + m,
                        v=10.0 + m, tb=tb, ts_=ts_))
    return out


# ============================ identity / input ==============================
def test_valid_btcusdt_perp_1m():
    v = compute_exchange_features(_req(timeframe="1m", bars=[_bar(0)],
                                       allowed_missing_bars=0))
    assert isinstance(v, ExchangeFeatureVector)
    assert v.symbol == "BTCUSDT" and v.timeframe == "1m"
    assert v.bars_expected == 1 and v.bars_present == 1 and v.is_usable is True


def test_unsupported_spot_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(market_type="spot", bars=[_bar(0)]))


def test_unsupported_timeframe_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(timeframe="3m", bars=[_bar(0)]))


def test_naive_bucket_ts_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(bucket_ts=datetime(2026, 1, 1), bars=[]))


def test_bad_calculation_version_fails():
    for bad in ("XYZ", "0123456789ABCDEF", "0123", "g" * 16):
        with pytest.raises(FeatureError):
            compute_exchange_features(_req(calculation_version=bad, bars=[_bar(0)]))


def test_bad_config_hash_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(config_hash="short", bars=[_bar(0)]))


def test_blank_versions_fail():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(config_version="  ", bars=[_bar(0)]))
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(code_version="", bars=[_bar(0)]))


def test_deterministic_under_reordered_inputs():
    bars = _bars_5m()
    oi = [OpenInterestObservation(BASE + timedelta(minutes=1), 100.0, "base"),
          OpenInterestObservation(BASE + timedelta(minutes=3), 110.0, "base")]
    fund = [FundingObservation(BASE - timedelta(minutes=1), 0.0001),
            FundingObservation(BASE + timedelta(minutes=2), 0.0002)]
    liq = [LiquidationEvent(BASE + timedelta(minutes=1), "long", 100.0),
           LiquidationEvent(BASE + timedelta(minutes=2), "short", 50.0)]
    a = compute_exchange_features(_req(bars=bars, open_interest=oi, funding=fund,
                                       liquidations=liq))
    b = compute_exchange_features(_req(bars=list(reversed(bars)),
                                       open_interest=list(reversed(oi)),
                                       funding=list(reversed(fund)),
                                       liquidations=list(reversed(liq))))
    assert a == b


def test_duplicate_bar_timestamps_fail():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(bars=[_bar(0), _bar(0)]))


def test_out_of_bucket_bar_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(bars=[_bar(0), _bar(5)]))  # minute 5 >= 5m end


def test_inputs_not_mutated():
    bars = _bars_5m()
    snapshot = list(bars)
    compute_exchange_features(_req(bars=bars))
    assert bars == snapshot           # caller's list untouched


# ================================ price ======================================
def test_exact_price_move_and_range():
    v = compute_exchange_features(_req(timeframe="1m", bars=[
        _bar(0, o=100.0, h=110.0, lo=95.0, c=110.0)]))
    assert v.price_move_pct == pytest.approx(10.0)     # (110-100)/100*100
    assert v.range_width_pct == pytest.approx(15.0)    # (110-95)/100*100
    assert v.close_price == 110.0


def test_first_open_last_close_by_timestamp():
    # bars provided out of order; open from earliest, close from latest
    b_early = _bar(0, o=100.0, h=105.0, lo=99.0, c=101.0)
    b_late = _bar(4, o=104.0, h=121.0, lo=99.0, c=120.0)
    v = compute_exchange_features(_req(bars=[b_late, b_early],
                                       allowed_missing_bars=3))
    assert v.price_move_pct == pytest.approx((120.0 - 100.0) / 100.0 * 100)
    assert v.close_price == 120.0


def test_open_zero_percentage_none_internal_guard():
    # _price_features guards open_first==0 (compute() rejects open<=0 via OHLC).
    bar0 = KlineBar(ts=BASE, open=0.0, high=1.0, low=0.0, close=1.0, volume=1.0)
    pm, rw, close = _price_features([bar0])
    assert pm is None and rw is None and close == 1.0


def test_bad_ohlc_invariant_fails():
    # high < max(open, close, low)
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(timeframe="1m",
                                       bars=[_bar(0, o=100.0, h=101.0, lo=99.0, c=105.0)]))


# ============================= bars / gaps ===================================
@pytest.mark.parametrize("tf, expected", [
    ("1m", 1), ("5m", 5), ("15m", 15), ("1h", 60), ("4h", 240)])
def test_bars_expected_per_timeframe(tf, expected):
    v = compute_exchange_features(_req(timeframe=tf, bars=[_bar(0)],
                                       allowed_missing_bars=expected))
    assert v.bars_expected == expected


def test_complete_bucket_usable():
    v = compute_exchange_features(_req(bars=_bars_5m(), allowed_missing_bars=0))
    assert v.bars_present == 5 and v.has_gap is False and v.is_usable is True


def test_tolerated_missing_bar_usable_with_gap():
    v = compute_exchange_features(_req(bars=_bars_5m()[:4], allowed_missing_bars=1))
    assert v.bars_present == 4 and v.has_gap is True and v.is_usable is True


def test_gap_above_tolerance_unusable():
    v = compute_exchange_features(_req(bars=_bars_5m()[:3], allowed_missing_bars=1))
    assert v.bars_present == 3 and v.has_gap is True and v.is_usable is False


def test_empty_bucket():
    v = compute_exchange_features(_req(bars=[], allowed_missing_bars=5))
    assert v.bars_present == 0 and v.is_usable is False
    assert v.price_move_pct is None and v.close_price is None
    assert v.volume_raw is None and v.volume_notional_usd is None


def test_bars_present_exceeds_expected_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(timeframe="1m",
                                       bars=[_bar(0, sec=0), _bar(0, sec=30)]))


def test_negative_allowed_missing_bars_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(bars=_bars_5m(), allowed_missing_bars=-1))


# ================================ volume =====================================
def test_volume_raw_sum():
    v = compute_exchange_features(_req(bars=_bars_5m()))
    assert v.volume_raw == pytest.approx(sum(10.0 + m for m in range(5)))  # 60
    assert v.volume_raw_unit == "base"


def test_base_notional_per_bar():
    v = compute_exchange_features(_req(bars=_bars_5m(), instrument_metadata=_meta("base")))
    expected = sum((10.0 + m) * (101.0 + m) for m in range(5))
    assert v.volume_notional_usd == pytest.approx(expected)


def test_contracts_notional_with_ctval():
    v = compute_exchange_features(_req(bars=_bars_5m(),
                                       instrument_metadata=_meta("contracts", 0.01)))
    expected = sum((10.0 + m) * 0.01 * (101.0 + m) for m in range(5))
    assert v.volume_notional_usd == pytest.approx(expected)


def test_missing_metadata_leaves_raw_but_notional_none():
    v = compute_exchange_features(_req(bars=_bars_5m(), instrument_metadata=None))
    assert v.volume_raw == pytest.approx(60.0)
    assert v.volume_raw_unit is None
    assert v.volume_notional_usd is None


def test_contracts_without_multiplier_notional_none():
    v = compute_exchange_features(_req(bars=_bars_5m(),
                                       instrument_metadata=_meta("contracts", None)))
    assert v.volume_raw == pytest.approx(60.0)
    assert v.volume_notional_usd is None      # fail-closed -> None, not base


def test_volume_raw_never_interpreted_as_base_for_contracts():
    v = compute_exchange_features(_req(bars=_bars_5m(),
                                       instrument_metadata=_meta("contracts", 0.01)))
    # raw stays the exchange-denominated sum, unit says contracts
    assert v.volume_raw == pytest.approx(60.0)
    assert v.volume_raw_unit == "contracts"


# ============================= taker / cvd ===================================
def test_taker_buy_sell_delta_exact():
    v = compute_exchange_features(_req(bars=_bars_5m(with_taker=True),
                                       instrument_metadata=_meta("base")))
    buy = sum((m + 1.0) * (101.0 + m) for m in range(5))
    sell = sum((m + 0.5) * (101.0 + m) for m in range(5))
    assert v.taker_buy_notional_usd == pytest.approx(buy)
    assert v.taker_sell_notional_usd == pytest.approx(sell)
    assert v.taker_delta_notional_usd == pytest.approx(buy - sell)


def test_cvd_is_windowed_sum_of_taker_delta():
    v = compute_exchange_features(_req(bars=_bars_5m(with_taker=True),
                                       instrument_metadata=_meta("base")))
    assert v.cvd_delta_notional_usd == pytest.approx(v.taker_delta_notional_usd)


def test_missing_taker_split_none_not_zero():
    bars = _bars_5m(with_taker=True)
    # blank one bar's split (historical Bybit/OKX)
    bars[2] = dataclasses.replace(bars[2], taker_buy_volume=None, taker_sell_volume=None)
    v = compute_exchange_features(_req(bars=bars, instrument_metadata=_meta("base")))
    assert v.taker_buy_notional_usd is None
    assert v.taker_delta_notional_usd is None
    assert v.cvd_delta_notional_usd is None       # None, never 0.0


def test_cvd_none_when_gap_above_tolerance():
    v = compute_exchange_features(_req(bars=_bars_5m(with_taker=True)[:3],
                                       allowed_missing_bars=1,
                                       instrument_metadata=_meta("base")))
    assert v.is_usable is False
    assert v.cvd_delta_notional_usd is None
    assert v.taker_delta_notional_usd is not None  # still computed on present bars


def test_no_state_leak_between_buckets():
    r1 = _req(bars=_bars_5m(), instrument_metadata=_meta("base"))
    r2 = _req(bars=_bars_5m()[:2], allowed_missing_bars=3, instrument_metadata=_meta("base"))
    v1 = compute_exchange_features(r1)
    v2 = compute_exchange_features(r2)
    v1b = compute_exchange_features(r1)
    assert v1 == v1b                # repeatable
    assert v2.cvd_delta_notional_usd != v1.cvd_delta_notional_usd


# ================================== OI =======================================
def test_oi_exact_percentage_change():
    oi = [OpenInterestObservation(BASE + timedelta(minutes=0), 100.0, "base"),
          OpenInterestObservation(BASE + timedelta(minutes=4), 110.0, "base")]
    v = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       open_interest=oi))
    assert v.oi_change_pct == pytest.approx(10.0)
    assert v.oi_unit == "base"


def test_oi_fewer_than_two_observations_none():
    oi = [OpenInterestObservation(BASE, 100.0, "base")]
    v = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       open_interest=oi))
    assert v.oi_change_pct is None and v.oi_unit is None


def test_oi_zero_first_none():
    oi = [OpenInterestObservation(BASE, 0.0, "base"),
          OpenInterestObservation(BASE + timedelta(minutes=1), 10.0, "base")]
    v = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       open_interest=oi))
    assert v.oi_change_pct is None and v.oi_unit == "base"


def test_oi_unit_change_none():
    oi = [OpenInterestObservation(BASE, 100.0, "base"),
          OpenInterestObservation(BASE + timedelta(minutes=1), 110.0, "contracts")]
    v = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       open_interest=oi))
    assert v.oi_change_pct is None and v.oi_unit is None


def test_oi_reordering_deterministic():
    oi = [OpenInterestObservation(BASE + timedelta(minutes=4), 110.0, "base"),
          OpenInterestObservation(BASE + timedelta(minutes=0), 100.0, "base")]
    v1 = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                        open_interest=oi))
    v2 = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                        open_interest=list(reversed(oi))))
    assert v1.oi_change_pct == v2.oi_change_pct == pytest.approx(10.0)


# ================================ funding ====================================
def test_funding_last_value_before_bucket_end():
    fund = [FundingObservation(BASE + timedelta(minutes=1), 0.0001),
            FundingObservation(BASE + timedelta(minutes=4), 0.0003)]
    v = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       funding=fund))
    assert v.funding_rate == pytest.approx(0.0003)


def test_funding_future_excluded():
    fund = [FundingObservation(BASE + timedelta(minutes=1), 0.0001),
            FundingObservation(BASE + timedelta(minutes=5), 0.0009)]  # at bucket_end
    v = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       funding=fund))
    assert v.funding_rate == pytest.approx(0.0001)


def test_funding_no_observation_none():
    v = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       funding=[]))
    assert v.funding_rate is None


def test_funding_duplicate_conflicting_ts_fails():
    fund = [FundingObservation(BASE + timedelta(minutes=1), 0.0001),
            FundingObservation(BASE + timedelta(minutes=1), 0.0002)]
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       funding=fund))


# ============================= liquidations ==================================
def test_healthy_quiet_feed_zeros():
    v = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       liquidation_feed_state=_feed(True, "full"),
                                       liquidations=[]))
    assert v.long_liquidation_notional == 0.0
    assert v.short_liquidation_notional == 0.0
    assert v.liquidation_event_count == 0


def test_unavailable_feed_null():
    v = compute_exchange_features(_req(
        bars=[_bar(0)], allowed_missing_bars=5,
        liquidation_feed_state=_feed(False, "unavailable"), liquidations=[]))
    assert v.long_liquidation_notional is None
    assert v.short_liquidation_notional is None
    assert v.liquidation_event_count is None


def test_long_short_sums_and_count():
    liq = [LiquidationEvent(BASE + timedelta(minutes=1), "long", 100.0),
           LiquidationEvent(BASE + timedelta(minutes=2), "long", 50.0),
           LiquidationEvent(BASE + timedelta(minutes=3), "short", 30.0)]
    v = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       liquidations=liq))
    assert v.long_liquidation_notional == pytest.approx(150.0)
    assert v.short_liquidation_notional == pytest.approx(30.0)
    assert v.liquidation_event_count == 3


@pytest.mark.parametrize("cov, snap", [("full", False), ("snapshot", True),
                                       ("aggregated", False)])
def test_liquidation_provenance_passthrough(cov, snap):
    v = compute_exchange_features(_req(
        bars=[_bar(0)], allowed_missing_bars=5,
        liquidation_feed_state=_feed(True, cov, snap), liquidations=[]))
    assert v.liquidation_feed_quality == cov
    assert v.is_snapshot_feed is snap


def test_unknown_liquidation_side_fails():
    liq = [LiquidationEvent(BASE + timedelta(minutes=1), "sideways", 100.0)]
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       liquidations=liq))


def test_liquidation_outside_bucket_fails():
    liq = [LiquidationEvent(BASE + timedelta(minutes=6), "long", 100.0)]
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       liquidations=liq))


def test_unavailable_coverage_but_available_true_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(
            bars=[_bar(0)], allowed_missing_bars=5,
            liquidation_feed_state=_feed(True, "unavailable")))


def test_no_liquidation_dedup():
    # two identical events must both be counted (no dedup in this PR)
    e = LiquidationEvent(BASE + timedelta(minutes=1), "long", 100.0)
    v = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       liquidations=[e, e]))
    assert v.liquidation_event_count == 2
    assert v.long_liquidation_notional == pytest.approx(200.0)


# =========================== schema alignment ================================
def test_output_fields_align_with_schema():
    fields = {f.name for f in dataclasses.fields(ExchangeFeatureVector)}
    assert "computed_at" not in fields          # DB default/writer fills it
    assert "volume_base" not in fields          # legacy name must not appear
    # no consensus-only fields leaked into the per-exchange model
    for consensus_only in ("coverage_by_metric", "provenance_by_metric",
                           "data_confidence_by_metric", "funding_rate_median",
                           "volume_notional_usd_sum"):
        assert consensus_only not in fields
    assert "volume_raw" in fields and "volume_raw_unit" in fields


# ==================== request <-> metadata identity (BLOCKER) ================
def test_metadata_exchange_mismatch_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(
            exchange="binance", bars=_bars_5m(),
            instrument_metadata=_meta("contracts", 0.01, exchange="okx")))


def test_metadata_symbol_mismatch_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(
            symbol="BTCUSDT", bars=_bars_5m(),
            instrument_metadata=_meta("base", symbol="ETHUSDT")))


def test_metadata_market_type_mismatch_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(
            market_type="perp", bars=_bars_5m(),
            instrument_metadata=_meta("base", market_type="spot")))


def test_metadata_identity_match_passes():
    v = compute_exchange_features(_req(
        exchange="bybit", bars=_bars_5m(),
        instrument_metadata=_meta("base", exchange="bybit")))
    assert v.exchange == "bybit"
    assert v.volume_notional_usd is not None


def test_metadata_mismatch_never_influences_notional():
    # An OKX contracts multiplier (0.01) attached to a binance request would
    # divide the notional ~100x if it silently leaked. It must raise instead,
    # BEFORE any volume/taker notional is derived.
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(
            exchange="binance", bars=_bars_5m(with_taker=True),
            instrument_metadata=_meta("contracts", 0.01, exchange="okx")))


# ============================ canonical identity ============================
def test_unknown_exchange_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(exchange="unknown", bars=[_bar(0)],
                                       instrument_metadata=None))


def test_inactive_symbol_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(symbol="DOGEUSDT", bars=[_bar(0)],
                                       instrument_metadata=None))


def test_lowercase_symbol_not_normalized_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(symbol="btcusdt", bars=[_bar(0)],
                                       instrument_metadata=None))


def test_eth_and_sol_not_activated():
    for sym in ("ETHUSDT", "SOLUSDT"):
        with pytest.raises(FeatureError):
            compute_exchange_features(_req(symbol=sym, bars=[_bar(0)],
                                           instrument_metadata=None))


def test_bitget_not_activated():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(exchange="bitget", bars=[_bar(0)],
                                       instrument_metadata=None))


@pytest.mark.parametrize("ex", ["binance", "bybit", "okx"])
def test_active_exchanges_accepted(ex):
    v = compute_exchange_features(_req(exchange=ex, timeframe="1m", bars=[_bar(0)],
                                       instrument_metadata=None))
    assert v.exchange == ex


# ======================= bucket alignment / 1m grid =========================
def test_5m_bucket_off_grid_fails():
    off = datetime(2026, 1, 1, 12, 3, 0, tzinfo=timezone.utc)
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(timeframe="5m", bucket_ts=off,
                                       bars=[], allowed_missing_bars=5,
                                       instrument_metadata=None))


def test_1h_bucket_minute_nonzero_fails():
    off = datetime(2026, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(timeframe="1h", bucket_ts=off,
                                       bars=[], allowed_missing_bars=60,
                                       instrument_metadata=None))


def test_4h_bucket_hour_not_multiple_fails():
    off = datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc)  # hour 13
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(timeframe="4h", bucket_ts=off,
                                       bars=[], allowed_missing_bars=240,
                                       instrument_metadata=None))


def test_4h_bucket_aligned_ok():
    ok = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)  # hour 12 % 4 == 0
    v = compute_exchange_features(_req(timeframe="4h", bucket_ts=ok,
                                       bars=[], allowed_missing_bars=240,
                                       instrument_metadata=None))
    assert v.bars_expected == 240


def test_bucket_ts_non_utc_offset_fails():
    tz = timezone(timedelta(hours=2))
    off = datetime(2026, 1, 1, 0, 0, 0, tzinfo=tz)
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(timeframe="1m", bucket_ts=off,
                                       bars=[], allowed_missing_bars=1,
                                       instrument_metadata=None))


def test_bar_second_nonzero_fails():
    bad = KlineBar(ts=BASE + timedelta(seconds=30), open=100.0, high=105.0,
                   low=99.0, close=102.0, volume=1.0)
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(timeframe="5m", bars=[bad],
                                       allowed_missing_bars=5, instrument_metadata=None))


def test_bar_microsecond_nonzero_fails():
    bad = KlineBar(ts=BASE + timedelta(microseconds=1), open=100.0, high=105.0,
                   low=99.0, close=102.0, volume=1.0)
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(timeframe="5m", bars=[bad],
                                       allowed_missing_bars=5, instrument_metadata=None))


def test_bar_non_utc_offset_fails():
    tz = timezone(timedelta(hours=2))
    bad = KlineBar(ts=datetime(2026, 1, 1, 0, 0, 0, tzinfo=tz), open=100.0,
                   high=105.0, low=99.0, close=102.0, volume=1.0)
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(timeframe="5m", bars=[bad],
                                       allowed_missing_bars=5, instrument_metadata=None))


def test_five_correct_slots_complete():
    v = compute_exchange_features(_req(timeframe="5m", bars=_bars_5m(),
                                       allowed_missing_bars=0))
    assert v.bars_present == 5 and v.has_gap is False and v.is_usable is True


def test_four_correct_slots_gap():
    v = compute_exchange_features(_req(timeframe="5m", bars=_bars_5m()[:4],
                                       allowed_missing_bars=1))
    assert v.bars_present == 4 and v.has_gap is True


def test_arbitrary_sub_minute_rows_not_complete():
    # Five rows within the bucket but off the 1m grid must NOT count as complete;
    # they fail loudly (no silent rounding into slots).
    bars = [KlineBar(ts=BASE + timedelta(minutes=m, seconds=30), open=100.0,
                     high=105.0, low=99.0, close=102.0, volume=1.0)
            for m in range(5)]
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(timeframe="5m", bars=bars,
                                       allowed_missing_bars=0, instrument_metadata=None))


def test_allowed_missing_exceeds_expected_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(timeframe="5m", bars=_bars_5m(),
                                       allowed_missing_bars=6))


# ==================== liquidation feed-state matrix =========================
def test_invalid_coverage_type_fails():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(
            bars=[_bar(0)], allowed_missing_bars=5,
            liquidation_feed_state=_feed(True, "partial")))


def test_snapshot_flag_requires_snapshot_coverage():
    # is_snapshot_feed=True with coverage 'full' is contradictory.
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(
            bars=[_bar(0)], allowed_missing_bars=5,
            liquidation_feed_state=_feed(True, "full", snapshot=True)))


def test_snapshot_coverage_requires_snapshot_flag():
    # coverage 'snapshot' with is_snapshot_feed=False is contradictory.
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(
            bars=[_bar(0)], allowed_missing_bars=5,
            liquidation_feed_state=_feed(True, "snapshot", snapshot=False)))


def test_aggregated_coverage_requires_non_snapshot_flag():
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(
            bars=[_bar(0)], allowed_missing_bars=5,
            liquidation_feed_state=_feed(True, "aggregated", snapshot=True)))


def test_unavailable_feed_with_events_fails():
    liq = [LiquidationEvent(BASE + timedelta(minutes=1), "long", 100.0)]
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(
            bars=[_bar(0)], allowed_missing_bars=5,
            liquidation_feed_state=_feed(False, "unavailable"), liquidations=liq))


def test_available_empty_events_measured_zero():
    v = compute_exchange_features(_req(
        bars=[_bar(0)], allowed_missing_bars=5,
        liquidation_feed_state=_feed(True, "snapshot", snapshot=True), liquidations=[]))
    assert v.long_liquidation_notional == 0.0
    assert v.short_liquidation_notional == 0.0
    assert v.liquidation_event_count == 0


def test_unavailable_empty_events_none():
    v = compute_exchange_features(_req(
        bars=[_bar(0)], allowed_missing_bars=5,
        liquidation_feed_state=_feed(False, "aggregated"), liquidations=[]))
    assert v.long_liquidation_notional is None
    assert v.short_liquidation_notional is None
    assert v.liquidation_event_count is None
    assert v.liquidation_feed_quality == "aggregated"


# ========================= duplicate OI timestamps ==========================
def test_oi_identical_duplicate_deduplicated():
    ts0, ts4 = BASE, BASE + timedelta(minutes=4)
    oi = [OpenInterestObservation(ts0, 100.0, "base"),
          OpenInterestObservation(ts0, 100.0, "base"),   # identical dup
          OpenInterestObservation(ts4, 110.0, "base")]
    v = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       open_interest=oi))
    assert v.oi_change_pct == pytest.approx(10.0)
    assert v.oi_unit == "base"


def test_oi_conflicting_value_same_ts_fails():
    oi = [OpenInterestObservation(BASE, 100.0, "base"),
          OpenInterestObservation(BASE, 101.0, "base")]
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       open_interest=oi))


def test_oi_conflicting_unit_same_ts_fails():
    oi = [OpenInterestObservation(BASE, 100.0, "base"),
          OpenInterestObservation(BASE, 100.0, "contracts")]
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       open_interest=oi))


def test_oi_duplicate_order_independent():
    ts0, ts4 = BASE, BASE + timedelta(minutes=4)
    a = [OpenInterestObservation(ts0, 100.0, "base"),
         OpenInterestObservation(ts4, 110.0, "base"),
         OpenInterestObservation(ts0, 100.0, "base")]
    v1 = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                        open_interest=a))
    v2 = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                        open_interest=list(reversed(a))))
    assert v1.oi_change_pct == v2.oi_change_pct == pytest.approx(10.0)


# ===================== naive-datetime rejection matrix ======================
def test_naive_bar_ts_fails():
    bad = KlineBar(ts=datetime(2026, 1, 1, 0, 0, 0), open=100.0, high=105.0,
                   low=99.0, close=102.0, volume=1.0)
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(timeframe="5m", bars=[bad],
                                       allowed_missing_bars=5, instrument_metadata=None))


def test_naive_oi_ts_fails():
    oi = [OpenInterestObservation(datetime(2026, 1, 1), 100.0, "base"),
          OpenInterestObservation(BASE + timedelta(minutes=1), 110.0, "base")]
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       open_interest=oi))


def test_naive_funding_ts_fails():
    fund = [FundingObservation(datetime(2026, 1, 1), 0.0001)]
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       funding=fund))


def test_naive_liquidation_ts_fails():
    liq = [LiquidationEvent(datetime(2026, 1, 1), "long", 100.0)]
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       liquidations=liq))


# ============================ funding edge cases ============================
def test_funding_exactly_at_bucket_end_excluded():
    fund = [FundingObservation(BASE + timedelta(minutes=1), 0.0001),
            FundingObservation(BASE + timedelta(minutes=5), 0.0009)]  # == bucket_end
    v = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       funding=fund))
    assert v.funding_rate == pytest.approx(0.0001)


def test_funding_identical_duplicate_deterministic():
    fund = [FundingObservation(BASE + timedelta(minutes=1), 0.0002),
            FundingObservation(BASE + timedelta(minutes=1), 0.0002)]
    v = compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       funding=fund))
    assert v.funding_rate == pytest.approx(0.0002)


def test_funding_conflicting_same_ts_fails():
    fund = [FundingObservation(BASE + timedelta(minutes=1), 0.0002),
            FundingObservation(BASE + timedelta(minutes=1), 0.0003)]
    with pytest.raises(FeatureError):
        compute_exchange_features(_req(bars=[_bar(0)], allowed_missing_bars=5,
                                       funding=fund))
