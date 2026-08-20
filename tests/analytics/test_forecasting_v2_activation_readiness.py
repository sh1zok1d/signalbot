"""Tests for analytics/forecasting_v2/activation_readiness.py.

No real DB -- a fake `V2SetupHistoryReader` recording every call, matching
the existing V2 loader test style
(tests/analytics/test_forecasting_v2_trend_pullback_inputs.py's
`RecordingReader`).
"""
from __future__ import annotations

import asyncio
import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2 import bias_1h as bias_1h_mod
from analytics.forecasting_v2 import compression_breakout as compression_breakout_mod
from analytics.forecasting_v2 import regime_4h as regime_4h_mod
from analytics.forecasting_v2.activation_readiness import (
    MANDATORY_PERCENTILE_COVERAGE, V2ActivationReadinessError,
    V2ActivationReadinessResult, V2CoverageStatus, V2RequiredPercentileCoverage,
    check_activation_readiness,
)
from analytics.forecasting_v2.context_evidence import MIN_PCTL_TIER

UTC = timezone.utc
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"
CALC_VERSION = "a" * 16
T = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def _run(coro):
    return asyncio.run(coro)


class FakePercentileReader:
    """Satisfies `V2SetupHistoryReader` structurally (only the one method
    `check_activation_readiness` calls). `rows_by_key` maps
    `(metric, timeframe, percentile_window)` to the tuple of rows that key
    should return; a missing key returns `()`, matching a real empty
    read."""
    def __init__(self, rows_by_key=None):
        self._rows_by_key = rows_by_key or {}
        self.calls: list = []

    async def fetch_v2_consensus_percentile_window(self, **kw):
        self.calls.append(kw)
        key = (kw["metric"], kw["timeframe"], kw["percentile_window"])
        return self._rows_by_key.get(key, ())

    # Unused by this module, present only for full Protocol conformance.
    async def fetch_v2_consensus_feature_window(self, **kw):
        raise AssertionError("must not be called")

    async def fetch_v2_reference_feature_window(self, **kw):
        raise AssertionError("must not be called")

    async def fetch_v2_reference_klines(self, **kw):
        raise AssertionError("must not be called")

    async def fetch_v2_instrument(self, **kw):
        raise AssertionError("must not be called")


class RaisingReader:
    class Boom(RuntimeError):
        pass

    async def fetch_v2_consensus_percentile_window(self, **kw):
        raise self.Boom("corrupted percentile_snapshots row")


def _row(*, bucket_ts=T, value=1.0, percentile_rank=0.5, confidence_tier="mature"):
    return {
        "bucket_ts": bucket_ts, "value": value, "percentile_rank": percentile_rank,
        "confidence_tier": confidence_tier,
    }


def _ready_rows_for_all() -> dict:
    return {
        (req.metric, req.timeframe, req.percentile_window): (_row(),)
        for req in MANDATORY_PERCENTILE_COVERAGE
    }


# ============================================================================
# MANDATORY_PERCENTILE_COVERAGE — sourced from real frozen family constants
# ============================================================================
def test_mandatory_coverage_has_exactly_four_entries():
    assert len(MANDATORY_PERCENTILE_COVERAGE) == 4


def test_mandatory_coverage_sourced_from_real_family_constants():
    by_source = {req.source: req for req in MANDATORY_PERCENTILE_COVERAGE}
    assert by_source["regime_4h.price"].metric == regime_4h_mod._PRICE_METRIC
    assert by_source["regime_4h.price"].timeframe == regime_4h_mod._REGIME_TIMEFRAME
    assert (
        by_source["regime_4h.price"].percentile_window
        == regime_4h_mod._REGIME_PERCENTILE_WINDOW)
    assert by_source["regime_4h.compression"].metric == regime_4h_mod._COMPRESSION_METRIC
    assert by_source["bias_1h.price"].metric == bias_1h_mod._PRICE_METRIC
    assert by_source["bias_1h.price"].timeframe == bias_1h_mod._BIAS_TIMEFRAME
    assert (
        by_source["bias_1h.price"].percentile_window == bias_1h_mod._BIAS_PERCENTILE_WINDOW)
    assert (
        by_source["compression_breakout.compression"].metric
        == compression_breakout_mod._COMPRESSION_METRIC)
    assert (
        by_source["compression_breakout.compression"].percentile_window
        == compression_breakout_mod.COMPRESSION_PERCENTILE_WINDOW)


def test_mandatory_coverage_excludes_oi_veto_and_percentile_free_families():
    """regime_4h's OI veto is optional/modulating -- never included.
    trend_pullback/confirmed_breakout have no percentile dependency at
    all -- never included."""
    sources = {req.source for req in MANDATORY_PERCENTILE_COVERAGE}
    assert not any("oi" in s.lower() for s in sources)
    assert not any("trend_pullback" in s for s in sources)
    assert not any("confirmed_breakout" in s for s in sources)


# ============================================================================
# V2RequiredPercentileCoverage validation
# ============================================================================
@pytest.mark.parametrize("field", ["source", "metric", "timeframe", "percentile_window"])
@pytest.mark.parametrize("bad", ["", "   "])
def test_required_coverage_rejects_blank_fields(field, bad):
    kwargs = dict(source="s", metric="m", timeframe="4h", percentile_window="30d")
    kwargs[field] = bad
    with pytest.raises(V2ActivationReadinessError, match=field):
        V2RequiredPercentileCoverage(**kwargs)


def test_required_coverage_rejects_unrecognized_timeframe():
    with pytest.raises(V2ActivationReadinessError, match="timeframe"):
        V2RequiredPercentileCoverage(
            source="s", metric="m", timeframe="3h", percentile_window="30d")


def test_required_coverage_is_frozen():
    req = V2RequiredPercentileCoverage(
        source="s", metric="m", timeframe="4h", percentile_window="30d")
    with pytest.raises(dataclasses.FrozenInstanceError):
        req.metric = "other"  # type: ignore[misc]


# ============================================================================
# check_activation_readiness — happy path
# ============================================================================
def test_all_requirements_ready_yields_ready_true():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    assert isinstance(result, V2ActivationReadinessResult)
    assert result.ready is True
    assert result.calculation_version == CALC_VERSION
    assert result.decision_boundary == T
    assert len(result.statuses) == 4
    assert all(status.ready for status in result.statuses)


def test_calculation_version_passed_straight_through_never_defaulted():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    assert len(reader.calls) == 4
    for call in reader.calls:
        assert call["calculation_version"] == CALC_VERSION
        assert call["symbol"] == SYMBOL
        assert call["market_type"] == MARKET_TYPE


def test_lookback_window_is_exactly_one_bucket_width_per_requirement():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    by_timeframe = {call["timeframe"]: call for call in reader.calls}
    assert by_timeframe["4h"]["bucket_start"] == T - timedelta(hours=4)
    assert by_timeframe["4h"]["bucket_end"] == T
    assert by_timeframe["1h"]["bucket_start"] == T - timedelta(hours=1)
    assert by_timeframe["15m"]["bucket_start"] == T - timedelta(minutes=15)


# ============================================================================
# check_activation_readiness — fail-closed NOT_READY cases
# ============================================================================
def test_missing_row_for_one_requirement_makes_whole_result_not_ready():
    rows = _ready_rows_for_all()
    key = (regime_4h_mod._PRICE_METRIC, regime_4h_mod._REGIME_TIMEFRAME,
           regime_4h_mod._REGIME_PERCENTILE_WINDOW)
    rows[key] = ()  # no row at all for regime_4h.price
    reader = FakePercentileReader(rows_by_key=rows)
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    assert result.ready is False
    by_source = {s.requirement.source: s for s in result.statuses}
    assert by_source["regime_4h.price"].ready is False
    assert "no percentile_snapshots row" in by_source["regime_4h.price"].reason
    # every OTHER requirement independently still reports ready=True --
    # never a partial/majority pass, but each status is its own verdict.
    assert by_source["bias_1h.price"].ready is True


def test_none_value_makes_requirement_not_ready():
    rows = _ready_rows_for_all()
    key = (bias_1h_mod._PRICE_METRIC, bias_1h_mod._BIAS_TIMEFRAME,
           bias_1h_mod._BIAS_PERCENTILE_WINDOW)
    rows[key] = (_row(value=None),)
    reader = FakePercentileReader(rows_by_key=rows)
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    assert result.ready is False
    by_source = {s.requirement.source: s for s in result.statuses}
    assert by_source["bias_1h.price"].ready is False
    assert "missing value/percentile_rank" in by_source["bias_1h.price"].reason


def test_none_percentile_rank_makes_requirement_not_ready():
    rows = _ready_rows_for_all()
    key = (bias_1h_mod._PRICE_METRIC, bias_1h_mod._BIAS_TIMEFRAME,
           bias_1h_mod._BIAS_PERCENTILE_WINDOW)
    rows[key] = (_row(percentile_rank=None),)
    reader = FakePercentileReader(rows_by_key=rows)
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    assert result.ready is False


@pytest.mark.parametrize("tier,expected_ready", [
    ("none", False), ("low", False), ("building", True), ("mature", True),
])
def test_confidence_tier_floor_is_min_pctl_tier(tier, expected_ready):
    assert MIN_PCTL_TIER == "building"  # sanity: this test tracks the real frozen floor
    rows = _ready_rows_for_all()
    key = (bias_1h_mod._PRICE_METRIC, bias_1h_mod._BIAS_TIMEFRAME,
           bias_1h_mod._BIAS_PERCENTILE_WINDOW)
    rows[key] = (_row(confidence_tier=tier),)
    reader = FakePercentileReader(rows_by_key=rows)
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    by_source = {s.requirement.source: s for s in result.statuses}
    assert by_source["bias_1h.price"].ready is expected_ready
    assert result.ready is expected_ready


def test_unknown_confidence_tier_raises_not_downgraded_to_not_ready():
    """Corruption (an impossible tier string) is never silently treated as
    a legitimate NOT_READY -- it is a real error."""
    rows = _ready_rows_for_all()
    key = (bias_1h_mod._PRICE_METRIC, bias_1h_mod._BIAS_TIMEFRAME,
           bias_1h_mod._BIAS_PERCENTILE_WINDOW)
    rows[key] = (_row(confidence_tier="bogus_tier"),)
    reader = FakePercentileReader(rows_by_key=rows)
    with pytest.raises(V2ActivationReadinessError, match="confidence_tier"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=T))


def test_latest_row_is_the_last_one_returned_never_the_first():
    rows = _ready_rows_for_all()
    key = (bias_1h_mod._PRICE_METRIC, bias_1h_mod._BIAS_TIMEFRAME,
           bias_1h_mod._BIAS_PERCENTILE_WINDOW)
    stale = _row(bucket_ts=T - timedelta(hours=1), confidence_tier="none")
    fresh = _row(bucket_ts=T, confidence_tier="mature")
    rows[key] = (stale, fresh)  # ascending order, matching the real reader's contract
    reader = FakePercentileReader(rows_by_key=rows)
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    by_source = {s.requirement.source: s for s in result.statuses}
    assert by_source["bias_1h.price"].ready is True
    assert by_source["bias_1h.price"].latest_bucket_ts == T


# ============================================================================
# corruption is never swallowed
# ============================================================================
def test_reader_error_propagates_unchanged_never_downgraded():
    with pytest.raises(RaisingReader.Boom):
        _run(check_activation_readiness(
            RaisingReader(), symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=T))


# ============================================================================
# input validation
# ============================================================================
@pytest.mark.parametrize("bad", ["", "   ", None])
def test_blank_symbol_rejected(bad):
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="symbol"):
        _run(check_activation_readiness(
            reader, symbol=bad, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=T))


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_blank_market_type_rejected(bad):
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="market_type"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=bad,
            calculation_version=CALC_VERSION, decision_boundary=T))


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_blank_calculation_version_rejected(bad):
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="calculation_version"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=bad, decision_boundary=T))


def test_naive_decision_boundary_rejected():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="decision_boundary"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=datetime(2026, 8, 20, 12, 0)))


def test_non_utc_decision_boundary_rejected():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    non_utc = datetime(2026, 8, 20, 12, 0, tzinfo=timezone(timedelta(hours=2)))
    with pytest.raises(V2ActivationReadinessError, match="decision_boundary"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=non_utc))


def test_non_whole_minute_decision_boundary_rejected():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="decision_boundary"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION,
            decision_boundary=datetime(2026, 8, 20, 12, 0, 30, tzinfo=UTC)))


def test_empty_requirements_rejected():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="requirements"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=T, requirements=()))


def test_wrong_type_requirement_rejected():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="V2RequiredPercentileCoverage"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=T,
            requirements=("not-a-requirement",)))  # type: ignore[arg-type]


# ============================================================================
# result immutability
# ============================================================================
def test_result_and_status_are_frozen():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.ready = False  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.statuses[0].ready = False  # type: ignore[misc]
