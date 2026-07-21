"""Unit tests for analytics/feature_engine/consensus.py (pure, no I/O).

Covers Consensus Contract Revision 0.2.3 (docs/STAGE2_SPEC.md §11). No DB,
Docker, Redis, network, real clock, env, sleep, or subprocess.
"""
from __future__ import annotations

import dataclasses
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from analytics.feature_engine.models import ExchangeFeatureVector
from analytics.feature_engine.consensus_models import (
    ConsensusFeatureRequest, ConsensusFeatureVector, FAMILIES, ROBUST_Z_SCALE,
)
from analytics.feature_engine.consensus import compute_consensus_features, ConsensusError

BASE = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
CV16 = "0123456789abcdef"
CH64 = "a" * 64
EXS = ("binance", "bybit", "okx")
# Structural liquidation feed quality per exchange (symbols.registry authority).
LQ = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}
WEIGHTS = {"coverage": 0.50, "agreement": 0.30, "dispersion": 0.20}


def _efv(ex, *, price_move=1.0, range_width=5.0, close=100.0,
         volume=1000.0, tbuy=600.0, tsell=400.0, tdelta=200.0, cvd=200.0,
         oi=2.0, funding=0.0001, long_liq=0.0, short_liq=0.0, liq_count=0,
         is_usable=True, quality=None):
    return ExchangeFeatureVector(
        exchange=ex, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=BASE, feature_schema_version=1, calculation_version=CV16,
        price_move_pct=price_move, range_width_pct=range_width, close_price=close,
        volume_raw=10.0, volume_raw_unit="base", volume_notional_usd=volume,
        taker_buy_notional_usd=tbuy, taker_sell_notional_usd=tsell,
        taker_delta_notional_usd=tdelta, cvd_delta_notional_usd=cvd,
        oi_change_pct=oi, oi_unit="base", funding_rate=funding,
        long_liquidation_notional=long_liq, short_liquidation_notional=short_liq,
        liquidation_event_count=liq_count,
        liquidation_feed_quality=(quality or LQ[ex]), is_snapshot_feed=(ex == "binance"),
        bars_expected=5, bars_present=5, has_gap=False, is_usable=is_usable,
        config_hash=CH64, config_version="2.1.0", code_version="t")


def _req(features, *, expected=None, exclusions=None, minimum=2,
         weights=None, threshold=3.5, **over):
    exp = expected if expected is not None else {f: tuple(EXS) for f in FAMILIES}
    d = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=BASE,
        feature_schema_version=1, calculation_version=CV16, config_hash=CH64,
        config_version="2.1.0", code_version="t",
        exchange_features=features, expected_exchanges_by_family=exp,
        exclusion_reasons_by_family=(exclusions or {}),
        minimum_exchange_coverage=minimum,
        confidence_weights=(weights or WEIGHTS), robust_z_threshold=threshold)
    d.update(over)
    return ConsensusFeatureRequest(**d)


def _three():
    return [_efv("binance"), _efv("bybit"), _efv("okx")]


# =========================== 1. full 3/3 ====================================
def test_full_consensus_3_of_3():
    v = compute_consensus_features(_req(_three()))
    for fam in FAMILIES:
        assert v.coverage_by_metric[fam] == dataclasses.replace(
            v.coverage_by_metric[fam], available=3, expected=3, ratio=1.0)
    assert v.is_partial_consensus is False
    assert v.volume_notional_usd_sum == pytest.approx(3000.0)
    assert v.observed_liquidation_event_count_sum == 0
    assert set(v.coverage_by_metric) == set(FAMILIES)


# =========================== 2. partial 2/3 =================================
def test_partial_consensus_2_of_3():
    feats = [_efv("binance"), _efv("bybit")]  # okx absent, excluded by reason
    excl = {f: {"okx": "NO_HISTORICAL_DATA"} for f in FAMILIES}
    v = compute_consensus_features(_req(feats, exclusions=excl))
    cov = v.coverage_by_metric["oi"]
    assert (cov.available, cov.expected, cov.ratio) == (2, 3, 2 / 3)
    assert v.is_partial_consensus is True
    prov = v.provenance_by_metric["oi"]
    assert prov.contributing == ("binance", "bybit")
    assert prov.excluded == (("okx", "NO_HISTORICAL_DATA"),)
    assert v.oi_change_pct_median is not None      # 2 >= minimum


# ================= 3. 1/3 below minimum -> NULL aggregates ==================
def test_below_minimum_nulls_but_keeps_coverage():
    feats = [_efv("binance")]
    excl = {f: {"bybit": "NO_HISTORICAL_DATA", "okx": "NO_HISTORICAL_DATA"}
            for f in FAMILIES}
    v = compute_consensus_features(_req(feats, exclusions=excl))
    assert v.coverage_by_metric["oi"].available == 1
    assert v.oi_change_pct_median is None and v.oi_change_pct_mad is None
    assert v.oi_direction_agreement is None
    assert v.volume_notional_usd_sum is None
    assert v.observed_long_liquidation_notional_sum is None
    # confidence from coverage only: ratio * 100
    assert v.data_confidence_by_metric["oi"] == pytest.approx(100.0 / 3.0)


# ==================== 4. different expected sets per family =================
def test_different_expected_sets_per_family():
    exp = {f: tuple(EXS) for f in FAMILIES}
    exp["taker_flow"] = ("binance",)            # only Binance expected (historical)
    exp["oi"] = ("binance", "bybit")            # OKX no historical OI
    v = compute_consensus_features(_req(_three(), expected=exp, minimum=1))
    assert v.coverage_by_metric["taker_flow"].expected == 1
    assert v.coverage_by_metric["oi"].expected == 2
    assert v.coverage_by_metric["price_structure"].expected == 3
    assert v.exchanges_expected_max == 3


# ==================== 5-9, 33 rejections ====================================
def test_empty_expected_set_rejected():
    exp = {f: tuple(EXS) for f in FAMILIES}
    exp["funding"] = ()
    with pytest.raises(ConsensusError):
        compute_consensus_features(_req(_three(), expected=exp))


def test_bitget_rejected():
    exp = {f: tuple(EXS) for f in FAMILIES}
    exp["price_structure"] = ("binance", "bybit", "bitget")
    with pytest.raises(ConsensusError):
        compute_consensus_features(_req(_three(), expected=exp))


def test_duplicate_exchange_rejected():
    feats = [_efv("binance"), _efv("binance"), _efv("bybit")]
    with pytest.raises(ConsensusError):
        compute_consensus_features(_req(feats))


def test_identity_mismatch_rejected():
    bad = dataclasses.replace(_efv("okx"), bucket_ts=BASE + timedelta(minutes=5))
    with pytest.raises(ConsensusError):
        compute_consensus_features(_req([_efv("binance"), _efv("bybit"), bad]))


def test_expected_without_efv_or_reason_rejected():
    # okx expected everywhere but neither present nor excluded
    with pytest.raises(ConsensusError):
        compute_consensus_features(_req([_efv("binance"), _efv("bybit")]))


def test_unexpected_exchange_efv_rejected():
    exp = {f: ("binance", "bybit") for f in FAMILIES}   # okx not expected anywhere
    with pytest.raises(ConsensusError):
        compute_consensus_features(_req(_three(), expected=exp, minimum=1))


def test_nan_value_rejected():
    bad = dataclasses.replace(_efv("okx"), price_move_pct=float("nan"))
    with pytest.raises(ConsensusError):
        compute_consensus_features(_req([_efv("binance"), _efv("bybit"), bad]))


def test_infinity_value_rejected():
    bad = dataclasses.replace(_efv("okx"), funding_rate=float("inf"))
    with pytest.raises(ConsensusError):
        compute_consensus_features(_req([_efv("binance"), _efv("bybit"), bad]))


# ============ 10. explicit STALE/LATE_BAR excludes numeric EFV ==============
def test_exclusion_reason_overrides_numeric_efv():
    # okx has a perfectly good EFV but is explicitly excluded as STALE for oi.
    excl = {"oi": {"okx": "STALE"}}
    v = compute_consensus_features(_req(_three(), exclusions=excl))
    assert v.coverage_by_metric["oi"].available == 2
    assert v.provenance_by_metric["oi"].excluded == (("okx", "STALE"),)
    assert "okx" not in v.provenance_by_metric["oi"].contributing
    # other families still 3/3
    assert v.coverage_by_metric["price_structure"].available == 3


# ================= 11-12. NULL vs measured-zero liquidations ================
def test_measured_zero_liquidations_participate():
    feats = [_efv(e, long_liq=0.0, short_liq=0.0, liq_count=0) for e in EXS]
    v = compute_consensus_features(_req(feats))
    assert v.observed_long_liquidation_notional_sum == 0.0
    assert v.observed_short_liquidation_notional_sum == 0.0
    assert v.observed_liquidation_event_count_sum == 0
    assert v.coverage_by_metric["liquidations"].available == 3


def test_null_never_becomes_zero_below_minimum():
    feats = [_efv("binance")]
    excl = {f: {"bybit": "NO_HISTORICAL_DATA", "okx": "NO_HISTORICAL_DATA"} for f in FAMILIES}
    v = compute_consensus_features(_req(feats, exclusions=excl))
    assert v.observed_long_liquidation_notional_sum is None   # None, never 0
    assert v.volume_notional_usd_sum is None


# ================= 13. is_usable gate only bar-derived ======================
def test_is_usable_gate_only_bar_derived():
    # okx not usable: excluded from bar-derived families, still contributes to
    # oi/funding/liquidations.
    okx = _efv("okx", is_usable=False)
    excl = {"price_structure": {"okx": "LATE_BAR"},
            "volume": {"okx": "LATE_BAR"},
            "taker_flow": {"okx": "LATE_BAR"}}
    v = compute_consensus_features(_req([_efv("binance"), _efv("bybit"), okx],
                                        exclusions=excl))
    assert v.coverage_by_metric["price_structure"].available == 2
    assert v.coverage_by_metric["volume"].available == 2
    assert v.coverage_by_metric["taker_flow"].available == 2
    assert v.coverage_by_metric["oi"].available == 3          # not gated
    assert v.coverage_by_metric["funding"].available == 3
    assert v.coverage_by_metric["liquidations"].available == 3


def test_usable_false_without_reason_is_rejected():
    okx = _efv("okx", is_usable=False)   # bar-derived families need a reason
    with pytest.raises(ConsensusError):
        compute_consensus_features(_req([_efv("binance"), _efv("bybit"), okx]))


# ========= 14. missing multiplier degrades volume/taker, not price =========
def test_missing_multiplier_degrades_volume_taker_not_price():
    okx = _efv("okx", volume=None, tbuy=None, tsell=None, tdelta=None, cvd=None)
    excl = {"volume": {"okx": "MISSING_CONTRACT_MULTIPLIER"},
            "taker_flow": {"okx": "MISSING_CONTRACT_MULTIPLIER"}}
    v = compute_consensus_features(_req([_efv("binance"), _efv("bybit"), okx],
                                        exclusions=excl))
    assert v.coverage_by_metric["price_structure"].available == 3   # unaffected
    assert v.coverage_by_metric["volume"].available == 2
    assert v.coverage_by_metric["taker_flow"].available == 2
    assert v.price_move_pct_median is not None
    assert v.data_confidence_by_metric["price_structure"] == pytest.approx(100.0)


# ==================== 15-16. direction agreement ============================
def test_all_flat_direction_agreement_is_one():
    feats = [_efv(e, price_move=0.0) for e in EXS]
    v = compute_consensus_features(_req(feats))
    assert v.price_direction_agreement == 1.0
    assert v.price_move_pct_median == 0.0


def test_mixed_direction_agreement():
    feats = [_efv("binance", oi=-1.0), _efv("bybit", oi=0.0), _efv("okx", oi=1.0)]
    v = compute_consensus_features(_req(feats))
    assert v.oi_direction_agreement == pytest.approx(1 / 3)


# ==================== 17-19. median / MAD / dispersion ======================
def test_median_even_count():
    feats = [_efv("binance", price_move=1.0), _efv("bybit", price_move=2.0)]
    excl = {f: {"okx": "NO_HISTORICAL_DATA"} for f in FAMILIES}
    v = compute_consensus_features(_req(feats, exclusions=excl))
    assert v.price_move_pct_median == pytest.approx(1.5)   # even -> mean of middle two


def test_median_odd_count():
    feats = [_efv("binance", oi=1.0), _efv("bybit", oi=5.0), _efv("okx", oi=2.0)]
    v = compute_consensus_features(_req(feats))
    assert v.oi_change_pct_median == 2.0


def test_mad_zero_gives_full_dispersion_confidence():
    feats = [_efv(e, funding=0.0005) for e in EXS]   # identical -> MAD 0
    v = compute_consensus_features(_req(feats))
    assert v.funding_rate_mad == 0.0
    # funding confidence: coverage 0.5 + dispersion 0.2 renormalized; dispersion=1
    exp = 100.0 * (WEIGHTS["coverage"] * 1.0 + WEIGHTS["dispersion"] * 1.0) / (
        WEIGHTS["coverage"] + WEIGHTS["dispersion"])
    assert v.data_confidence_by_metric["funding"] == pytest.approx(exp)


def test_mad_positive_median_zero_gives_zero_dispersion():
    feats = [_efv("binance", funding=-1.0), _efv("bybit", funding=0.0),
             _efv("okx", funding=1.0)]        # median 0, mad 1 -> dispersion 0
    v = compute_consensus_features(_req(feats))
    assert v.funding_rate_median == 0.0 and v.funding_rate_mad == 1.0
    exp = 100.0 * (WEIGHTS["coverage"] * 1.0 + WEIGHTS["dispersion"] * 0.0) / (
        WEIGHTS["coverage"] + WEIGHTS["dispersion"])
    assert v.data_confidence_by_metric["funding"] == pytest.approx(exp)


# ==================== 20-23. confidence ====================================
def test_volume_confidence_is_coverage_only():
    v = compute_consensus_features(_req(_three()))
    assert v.data_confidence_by_metric["volume"] == pytest.approx(100.0)
    assert v.data_confidence_by_metric["liquidations"] == pytest.approx(100.0)


def test_weight_renormalization_price_structure():
    feats = [_efv("binance", price_move=1.0), _efv("bybit", price_move=1.0),
             _efv("okx", price_move=1.0)]     # all equal -> agreement 1, dispersion 1
    v = compute_consensus_features(_req(feats))
    # all three components applicable & = 1.0 -> score 100 regardless of weights
    assert v.data_confidence_by_metric["price_structure"] == pytest.approx(100.0)


def test_overall_is_mean_and_consensus_is_min():
    feats = [_efv("binance")]
    excl = {"oi": {"bybit": "X", "okx": "Y"}}   # oi below minimum -> low score
    # keep others 3/3
    v = compute_consensus_features(_req(_three(), exclusions=excl))
    scores = [v.data_confidence_by_metric[f] for f in FAMILIES]
    assert v.data_confidence_overall == pytest.approx(sum(scores) / 6)
    assert v.consensus_confidence == pytest.approx(min(scores))


# ==================== 24-27. outliers ======================================
def test_robust_z_outlier_above_threshold():
    feats = [_efv("binance", oi=1.0), _efv("bybit", oi=2.0), _efv("okx", oi=10.0)]
    v = compute_consensus_features(_req(feats, threshold=3.5))
    assert "oi_change_pct" in v.outlier_exchanges
    entry = v.outlier_exchanges["oi_change_pct"]["okx"]
    assert entry.reason == "ROBUST_Z_THRESHOLD"
    assert entry.robust_z == pytest.approx(ROBUST_Z_SCALE * (10.0 - 2.0) / 1.0)
    # 27: outlier remains in the aggregate (median unchanged by its presence)
    assert v.oi_change_pct_median == 2.0
    assert v.coverage_by_metric["oi"].available == 3


def test_threshold_equality_is_not_outlier():
    # two distinct values -> |robust_z| == ROBUST_Z_SCALE exactly for both.
    feats = [_efv("binance", oi=1.0), _efv("bybit", oi=2.0)]
    excl = {f: {"okx": "NO_HISTORICAL_DATA"} for f in FAMILIES}
    v = compute_consensus_features(_req(feats, exclusions=excl, threshold=ROBUST_Z_SCALE))
    assert v.outlier_exchanges == {}          # equality is not '>'


def test_mad_zero_nonmedian_outlier():
    feats = [_efv("binance", oi=1.0), _efv("bybit", oi=1.0), _efv("okx", oi=5.0)]
    v = compute_consensus_features(_req(feats))
    entry = v.outlier_exchanges["oi_change_pct"]["okx"]
    assert entry.reason == "MAD_ZERO_NONMEDIAN" and entry.robust_z is None


def test_no_outliers_returns_empty_mapping():
    v = compute_consensus_features(_req(_three()))
    assert v.outlier_exchanges == {}
    assert isinstance(v.outlier_exchanges, MappingProxyType)


# ==================== 28-29. liquidation quality ===========================
def test_liquidation_quality_includes_all_expected():
    # okx excluded from liquidations, but quality map still lists all expected.
    excl = {"liquidations": {"okx": "NO_HISTORICAL_DATA"}}
    feats = [_efv("binance"), _efv("bybit"), _efv("okx")]
    v = compute_consensus_features(_req(feats, exclusions=excl))
    assert dict(v.liquidation_feed_quality_by_exchange) == LQ
    assert v.coverage_by_metric["liquidations"].available == 2


def test_contributing_quality_mismatch_rejected():
    bad = _efv("okx", quality="full")   # registry says 'aggregated'
    with pytest.raises(ConsensusError):
        compute_consensus_features(_req([_efv("binance"), _efv("bybit"), bad]))


# ==================== 30-32. determinism / immutability =====================
def test_input_order_independence():
    feats = _three()
    a = compute_consensus_features(_req(feats))
    b = compute_consensus_features(_req(list(reversed(feats))))
    assert a == b


def test_output_maps_deterministic_family_order():
    v = compute_consensus_features(_req(_three()))
    assert list(v.coverage_by_metric) == list(FAMILIES)
    assert list(v.provenance_by_metric) == list(FAMILIES)
    assert list(v.data_confidence_by_metric) == list(FAMILIES)


def test_request_and_output_nested_immutability():
    req = _req(_three())
    with pytest.raises(TypeError):
        req.expected_exchanges_by_family["oi"] = ("binance",)
    with pytest.raises(TypeError):
        req.confidence_weights["coverage"] = 0.9
    v = compute_consensus_features(req)
    with pytest.raises(TypeError):
        v.coverage_by_metric["oi"] = None
    with pytest.raises(TypeError):
        v.liquidation_feed_quality_by_exchange["binance"] = "full"
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.consensus_confidence = 0.0


# ==================== 33-34. invalid config / no raw OI =====================
@pytest.mark.parametrize("weights", [
    {"coverage": 0.5, "agreement": 0.3},                       # missing key
    {"coverage": 0.5, "agreement": 0.3, "dispersion": 0.3},    # sum != 1
    {"coverage": 0.0, "agreement": 0.5, "dispersion": 0.5},    # coverage == 0
    {"coverage": 0.6, "agreement": -0.1, "dispersion": 0.5},   # negative
    {"coverage": 0.5, "agreement": 0.3, "dispersion": 0.2, "x": 0.0},  # unknown
])
def test_invalid_weights_rejected(weights):
    with pytest.raises(ConsensusError):
        compute_consensus_features(_req(_three(), weights=weights))


@pytest.mark.parametrize("threshold", [0.0, -1.0, float("nan"), float("inf")])
def test_invalid_threshold_rejected(threshold):
    with pytest.raises(ConsensusError):
        compute_consensus_features(_req(_three(), threshold=threshold))


def test_no_raw_oi_aggregation_path():
    fields = {f.name for f in dataclasses.fields(ConsensusFeatureVector)}
    for forbidden in ("oi_raw", "oi_raw_sum", "oi_change_pct_sum",
                      "volume_raw_sum", "volume_raw"):
        assert forbidden not in fields
    # OI is present only as a percentage-change median, never a raw level/sum.
    assert "oi_change_pct_median" in fields


# ==================== 35. schema-field parity ==============================
def test_output_fields_match_schema_minus_computed_at():
    sql = Path("storage/stage2_schema.sql").read_text(encoding="utf-8")
    m = re.search(
        r"CREATE TABLE IF NOT EXISTS consensus_feature_vectors\s*\((.*?)\n\s*PRIMARY KEY",
        sql, re.S)
    assert m, "consensus_feature_vectors block not found"
    cols = re.findall(
        r"^\s+([a-z_]+)\s+(?:TEXT|JSONB|INTEGER|DOUBLE PRECISION|TIMESTAMPTZ|BOOLEAN)",
        m.group(1), re.M)
    schema_cols = {c for c in cols if c != "computed_at"}
    fields = {f.name for f in dataclasses.fields(ConsensusFeatureVector)}
    assert fields == schema_cols
    assert "computed_at" not in fields
