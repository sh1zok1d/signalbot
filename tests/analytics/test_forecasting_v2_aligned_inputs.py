"""Tests for analytics/forecasting_v2/aligned_inputs.py (Stage 3 —
Multi-timeframe Alignment PR 3, the FINAL Stage 3 PR). No DB — a minimal
in-memory fake `V2AlignedInputReader` only, following the existing V2
analytics test style (tests/analytics/test_forecasting_v2_alignment.py,
tests/analytics/test_forecasting_v2_ports.py).

Exercises `load_v2_aligned_inputs()`'s central contract: the exact
per-timeframe bucket/bucket_end vectors from §1.4 composed with PR 3's own
load-bearing rule that a bucket's health cutoff is its OWN `bucket_end`
(never the global `T`); canonical-Binance-only reference reads with no
failover; §7.0a structural extrema derivation (`derive_reference_extrema`)
for both the 15m/15-bar and 1h/60-bar cases, all required success/failure
vectors; missingness-vs-corruption (`None`/`()` for legitimate absence,
`V2AlignedInputError` for any reader-returned row that is internally
inconsistent with what was requested); request immutability/TOCTOU; and a
source-level guarantee that no context/regime/bias/detector logic exists
anywhere in this module yet.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from analytics.forecasting_v2 import aligned_inputs as aligned_inputs_module
from analytics.forecasting_v2.aligned_inputs import (
    ALIGNED_TIMEFRAMES,
    STRUCTURAL_OHLC_TIMEFRAMES,
    V2_REFERENCE_EXCHANGE,
    V2AlignedInputError,
    V2AlignedInputRequest,
    V2AlignedInputs,
    V2ReferenceExtrema,
    V2TimeframeInputs,
    derive_reference_extrema,
    load_v2_aligned_inputs,
)

UTC = timezone.utc
H16 = "a" * 16


def dt(y, mo, d, h, mi, s=0, us=0):
    return datetime(y, mo, d, h, mi, s, us, tzinfo=UTC)


def _run(coro):
    import asyncio
    return asyncio.run(coro)


# ============================================================================
# row factories — plain dicts, matching what storage.db.Database's fetch_v2_*
# wrappers return after detachment (a Mapping); aligned_inputs.py only ever
# calls .get()/[] on these, so a plain dict is a faithful stand-in.
# ============================================================================
def make_consensus_row(*, bucket_ts, timeframe, **over):
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe=timeframe, bucket_ts=bucket_ts,
        feature_schema_version=1, calculation_version=H16,
        price_move_pct_median=0.1, oi_change_pct_median=0.02, oi_direction_agreement=0.75,
    )
    base.update(over)
    return base


def make_percentile_row(*, bucket_ts, timeframe, metric, percentile_window, **over):
    base = dict(
        scope="consensus", exchange="", symbol="BTCUSDT", market_type="perp",
        metric=metric, timeframe=timeframe, percentile_window=percentile_window,
        bucket_ts=bucket_ts, value=0.1, percentile_rank=0.9, sample_size=100,
        sample_window_start=bucket_ts - timedelta(days=30),
        sample_window_end=bucket_ts - timedelta(minutes=5),
        confidence_tier="mature", feature_schema_version=1, calculation_version=H16,
    )
    base.update(over)
    return base


def make_health_row(*, snapshot_ts, **over):
    base = dict(
        symbol="BTCUSDT", exchange="binance", market_type="perp", metric="price",
        snapshot_ts=snapshot_ts, is_stale=False, is_usable=True,
        feature_schema_version=1, calculation_version=H16,
    )
    base.update(over)
    return base


def make_reference_feature_row(*, bucket_ts, timeframe, exchange="binance",
                               bars_expected=15, bars_present=None, **over):
    if bars_present is None:
        bars_present = bars_expected
    base = dict(
        exchange=exchange, symbol="BTCUSDT", market_type="perp", timeframe=timeframe,
        bucket_ts=bucket_ts, feature_schema_version=1, calculation_version=H16,
        close_price=65000.0, bars_expected=bars_expected, bars_present=bars_present,
        has_gap=False, is_usable=True,
    )
    base.update(over)
    return base


def make_kline_row(*, ts, exchange="binance", symbol="BTCUSDT", high=65100.0, low=64900.0,
                   **over):
    base = dict(exchange=exchange, symbol=symbol, ts=ts, open=65000.0, high=high, low=low,
                close=65000.0)
    base.update(over)
    return base


def make_klines(bucket_ts, count, *, high=65100.0, low=64900.0):
    return tuple(
        make_kline_row(ts=bucket_ts + timedelta(minutes=i), high=high, low=low)
        for i in range(count))


# ============================================================================
# fake V2AlignedInputReader — lookup-table driven, records every call
# ============================================================================
class RecordingReader:
    """Satisfies `V2AlignedInputReader` structurally. Each `fetch_v2_*`
    method looks up its response from a per-timeframe (or per-cutoff, for
    health) table; a missing entry returns the family's own "legitimately
    absent" value (`None`/`()`) — matching a real empty-result read, never
    an error. Every call's exact kwargs are recorded for assertion.

    `fetch_v2_data_health_at_cutoff` emulates the REAL PR #34 contract
    (`storage/v2_alignment_readers.py::read_v2_data_health_at_cutoff`):
    the result always contains EVERY requested `(exchange, metric)` key —
    defaulting to `None` — never a silently omitted pair; `health_by_cutoff`
    only supplies the OVERRIDES for pairs that have an actual eligible
    snapshot, keyed `cutoff_ts -> {(exchange, metric): row}`."""
    def __init__(self, *, consensus=None, percentiles=None, health_by_cutoff=None,
                reference_feature=None, reference_klines=None):
        self._consensus = consensus or {}
        self._percentiles = percentiles or {}
        self._health_by_cutoff = health_by_cutoff or {}
        self._reference_feature = reference_feature or {}
        self._reference_klines = reference_klines or {}
        self.calls: list = []

    async def fetch_v2_consensus_feature(self, **kw):
        self.calls.append(("consensus_feature", kw))
        return self._consensus.get(kw["timeframe"])

    async def fetch_v2_consensus_percentiles(self, **kw):
        self.calls.append(("consensus_percentiles", kw))
        return self._percentiles.get(kw["timeframe"], ())

    async def fetch_v2_data_health_at_cutoff(self, **kw):
        self.calls.append(("data_health_at_cutoff", kw))
        overrides = self._health_by_cutoff.get(kw["cutoff_ts"], {})
        return {
            (exchange, metric): overrides.get((exchange, metric))
            for exchange in kw["exchanges"]
            for metric in kw["metrics"]
        }

    async def fetch_v2_reference_feature(self, **kw):
        self.calls.append(("reference_feature", kw))
        return self._reference_feature.get(kw["timeframe"])

    async def fetch_v2_reference_klines(self, **kw):
        self.calls.append(("reference_klines", kw))
        # fetch_v2_reference_klines has no `timeframe` parameter (raw
        # klines_1m carries no timeframe identity) — keyed by bucket_start
        # instead, which is exactly that timeframe's bucket_ts.
        return self._reference_klines.get(kw["bucket_start"], ())


def _default_request(T, **over):
    kwargs = dict(
        T=T, symbol="BTCUSDT", market_type="perp", calculation_version=H16,
        feature_schema_version=1, health_exchanges=("binance",), health_metrics=("price",))
    kwargs.update(over)
    return V2AlignedInputRequest(**kwargs)


# ============================================================================
# 1. V2AlignedInputRequest — validation, immutability, TOCTOU
# ============================================================================
def test_request_valid_construction():
    req = _default_request(dt(2026, 8, 15, 12, 10))
    assert req.symbol == "BTCUSDT"
    assert req.health_exchanges == ("binance",)
    assert req.health_metrics == ("price",)


def test_request_detaches_health_lists_to_tuples():
    req = _default_request(
        dt(2026, 8, 15, 12, 10),
        health_exchanges=["binance", "bybit"], health_metrics=["price", "oi"])
    assert req.health_exchanges == ("binance", "bybit")
    assert req.health_metrics == ("price", "oi")
    assert isinstance(req.health_exchanges, tuple)
    assert isinstance(req.health_metrics, tuple)


def test_request_toctou_mutating_original_list_after_construction_has_no_effect():
    exchanges = ["binance"]
    metrics = ["price"]
    req = _default_request(
        dt(2026, 8, 15, 12, 10), health_exchanges=exchanges, health_metrics=metrics)
    exchanges.append("bybit")
    metrics.append("oi")
    assert req.health_exchanges == ("binance",)
    assert req.health_metrics == ("price",)


@pytest.mark.parametrize("bad", ["binance", b"binance", 5, None, [], ["binance", "binance"],
                                 ["binance", ""], ["binance", None]])
def test_request_rejects_malformed_health_exchanges(bad):
    with pytest.raises(V2AlignedInputError, match="health_exchanges"):
        _default_request(dt(2026, 8, 15, 12, 10), health_exchanges=bad)


@pytest.mark.parametrize("bad", ["price", 5, None, [], ["price", "price"]])
def test_request_rejects_malformed_health_metrics(bad):
    with pytest.raises(V2AlignedInputError, match="health_metrics"):
        _default_request(dt(2026, 8, 15, 12, 10), health_metrics=bad)


def test_request_rejects_unsupported_symbol():
    with pytest.raises(V2AlignedInputError, match="symbol"):
        _default_request(dt(2026, 8, 15, 12, 10), symbol="ETHUSDT")


def test_request_rejects_unsupported_market_type():
    with pytest.raises(V2AlignedInputError, match="market_type"):
        _default_request(dt(2026, 8, 15, 12, 10), market_type="spot")


@pytest.mark.parametrize("bad_cv", ["", "A" * 16, "g" * 16, "a" * 15, None, 123])
def test_request_rejects_malformed_calculation_version(bad_cv):
    with pytest.raises(V2AlignedInputError, match="calculation_version"):
        _default_request(dt(2026, 8, 15, 12, 10), calculation_version=bad_cv)


@pytest.mark.parametrize("bad_fsv", [0, -1, True, False, "1", None, 1.5])
def test_request_rejects_malformed_feature_schema_version(bad_fsv):
    with pytest.raises(V2AlignedInputError, match="feature_schema_version"):
        _default_request(dt(2026, 8, 15, 12, 10), feature_schema_version=bad_fsv)


@pytest.mark.parametrize("bad_T", [
    dt(2026, 8, 15, 12, 3),          # not on the 5m grid
    dt(2026, 8, 15, 12, 10, 1),      # has seconds
    datetime(2026, 8, 15, 12, 10),   # naive
])
def test_request_rejects_t_not_a_legal_decision_boundary(bad_T):
    with pytest.raises(V2AlignedInputError, match="T must be a legal V2 decision boundary"):
        _default_request(bad_T)


def test_request_is_frozen():
    req = _default_request(dt(2026, 8, 15, 12, 10))
    with pytest.raises((AttributeError, TypeError)):
        req.symbol = "ETHUSDT"  # type: ignore[misc]


# ============================================================================
# 2. §1.4 x §2 LOAD-BEARING VECTOR: per-timeframe bucket_ts/bucket_end AND
# health cutoff = the BUCKET'S OWN bucket_end, never the global T.
# ============================================================================
def test_t_1210_full_alignment_vector():
    reader = RecordingReader()
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))

    expected = {
        "5m": (dt(2026, 8, 15, 12, 5), dt(2026, 8, 15, 12, 10)),
        "15m": (dt(2026, 8, 15, 11, 45), dt(2026, 8, 15, 12, 0)),
        "1h": (dt(2026, 8, 15, 11, 0), dt(2026, 8, 15, 12, 0)),
        "4h": (dt(2026, 8, 15, 8, 0), dt(2026, 8, 15, 12, 0)),
    }
    for tf, (bucket_ts, bucket_end) in expected.items():
        tf_inputs = result.by_timeframe[tf]
        assert tf_inputs.bucket_ts == bucket_ts, tf
        assert tf_inputs.bucket_end == bucket_end, tf

    # health cutoff actually SENT to the reader must be each bucket's own
    # end, never the global T=12:10 for 15m/1h/4h — see the dedicated
    # test below for a direct per-timeframe assertion of this.
    assert result.by_timeframe["5m"].bucket_end == dt(2026, 8, 15, 12, 10)
    assert result.by_timeframe["15m"].bucket_end == dt(2026, 8, 15, 12, 0)
    assert result.by_timeframe["1h"].bucket_end == dt(2026, 8, 15, 12, 0)
    assert result.by_timeframe["4h"].bucket_end == dt(2026, 8, 15, 12, 0)


def test_t_1210_health_cutoff_is_each_buckets_own_end_not_global_t():
    # A reader that hands back a DIFFERENT health snapshot per cutoff_ts
    # proves the actual cutoff sent for each timeframe, directly, rather
    # than inferring it from bucket_end alone.
    cutoff_5m = dt(2026, 8, 15, 12, 10)
    cutoff_rest = dt(2026, 8, 15, 12, 0)
    reader = RecordingReader(health_by_cutoff={
        cutoff_5m: {("binance", "price"): make_health_row(snapshot_ts=cutoff_5m)},
        cutoff_rest: {("binance", "price"): make_health_row(snapshot_ts=cutoff_rest)},
    })
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))

    assert result.by_timeframe["5m"].health[("binance", "price")]["snapshot_ts"] == cutoff_5m
    assert result.by_timeframe["15m"].health[("binance", "price")]["snapshot_ts"] == cutoff_rest
    assert result.by_timeframe["1h"].health[("binance", "price")]["snapshot_ts"] == cutoff_rest
    assert result.by_timeframe["4h"].health[("binance", "price")]["snapshot_ts"] == cutoff_rest


def test_t_1215_next_boundary_vector():
    reader = RecordingReader()
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 15))))

    expected = {
        "5m": (dt(2026, 8, 15, 12, 10), dt(2026, 8, 15, 12, 15)),
        "15m": (dt(2026, 8, 15, 12, 0), dt(2026, 8, 15, 12, 15)),
        "1h": (dt(2026, 8, 15, 11, 0), dt(2026, 8, 15, 12, 0)),
        "4h": (dt(2026, 8, 15, 8, 0), dt(2026, 8, 15, 12, 0)),
    }
    for tf, (bucket_ts, bucket_end) in expected.items():
        tf_inputs = result.by_timeframe[tf]
        assert tf_inputs.bucket_ts == bucket_ts, tf
        assert tf_inputs.bucket_end == bucket_end, tf


def test_result_by_timeframe_covers_exactly_the_four_aligned_timeframes():
    reader = RecordingReader()
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    assert set(result.by_timeframe.keys()) == set(ALIGNED_TIMEFRAMES) == {"5m", "15m", "1h", "4h"}


def test_structural_ohlc_timeframes_is_exactly_15m_and_1h():
    assert STRUCTURAL_OHLC_TIMEFRAMES == ("15m", "1h")


def test_reader_call_order_is_sequential_five_calls_per_structural_tf_four_otherwise():
    reader = RecordingReader()
    _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    # 4 non-structural fetches (consensus/percentiles/health/reference_feature)
    # per timeframe, plus a 5th (reference_klines) ONLY when the structural
    # gate passes -- here it never passes (no reference_feature at all), so
    # exactly 4 * 4 = 16 calls total, zero reference_klines calls.
    assert len(reader.calls) == 16
    assert not any(name == "reference_klines" for name, _ in reader.calls)


# ============================================================================
# 3. CANONICAL REFERENCE EXCHANGE — always "binance", never a failover
# ============================================================================
def test_reference_feature_always_requested_as_binance():
    reader = RecordingReader()
    _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    exchanges_requested = {
        kw["exchange"] for name, kw in reader.calls if name == "reference_feature"}
    assert exchanges_requested == {"binance"}


def test_reference_klines_always_requested_as_binance_when_gate_passes():
    bucket_ts = dt(2026, 8, 15, 11, 45)  # 15m bucket for T=12:10
    reader = RecordingReader(
        reference_feature={"15m": make_reference_feature_row(
            bucket_ts=bucket_ts, timeframe="15m", bars_expected=15)},
        reference_klines={bucket_ts: make_klines(bucket_ts, 15)},
    )
    _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    exchanges_requested = {
        kw["exchange"] for name, kw in reader.calls if name == "reference_klines"}
    assert exchanges_requested == {"binance"}


def test_v2_reference_exchange_constant_is_binance():
    assert V2_REFERENCE_EXCHANGE == "binance"


def test_no_bybit_or_okx_literal_in_executable_code():
    # The module docstring legitimately explains the no-failover guarantee
    # in prose ("...never silently substitutes Bybit, OKX..."); this check
    # is only about EXECUTABLE code never containing a literal fallback.
    body_src = _executable_body_source(aligned_inputs_module)
    assert "bybit" not in body_src.lower()
    assert "okx" not in body_src.lower()


def test_reference_feature_wrong_exchange_from_reader_rejected():
    # a misbehaving/fake reader returning a bybit row despite binance being
    # requested must never be silently accepted as "the reference".
    bucket_ts = dt(2026, 8, 15, 12, 5)
    reader = RecordingReader(
        reference_feature={"5m": make_reference_feature_row(
            bucket_ts=bucket_ts, timeframe="5m", exchange="bybit")})
    with pytest.raises(V2AlignedInputError, match="canonical reference exchange"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


# ============================================================================
# 4. §7.0a STRUCTURAL EXTREMA — derive_reference_extrema, both 15m/1h
# ============================================================================
@pytest.mark.parametrize("timeframe,bar_count", [("15m", 15), ("1h", 60)])
def test_extrema_complete_bucket_returns_exact_high_low(timeframe, bar_count):
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(bucket_ts=bucket_ts, timeframe=timeframe,
                                     bars_expected=bar_count)
    klines = list(make_klines(bucket_ts, bar_count, high=65000.0, low=64900.0))
    # inject a distinct max/min at a known position
    klines[3] = dict(klines[3], high=65500.0)
    klines[7] = dict(klines[7], low=64200.0)
    result = derive_reference_extrema(
        timeframe=timeframe, bucket_ts=bucket_ts, reference_feature=ref,
        reference_klines=tuple(klines))
    assert result == V2ReferenceExtrema(high=65500.0, low=64200.0)


@pytest.mark.parametrize("timeframe,bar_count", [("15m", 15), ("1h", 60)])
def test_extrema_missing_one_bar_but_efv_claims_full_errors(timeframe, bar_count):
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(bucket_ts=bucket_ts, timeframe=timeframe,
                                     bars_expected=bar_count)
    klines = make_klines(bucket_ts, bar_count - 1)  # one short
    with pytest.raises(V2AlignedInputError, match="expected exactly"):
        derive_reference_extrema(
            timeframe=timeframe, bucket_ts=bucket_ts, reference_feature=ref,
            reference_klines=klines)


def test_extrema_duplicate_minute_errors():
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(bucket_ts=bucket_ts, timeframe="15m", bars_expected=15)
    klines = list(make_klines(bucket_ts, 15))
    klines[1] = dict(klines[1], ts=klines[0]["ts"])  # duplicate ts, still 15 rows total
    with pytest.raises(V2AlignedInputError, match="duplicate constituent bar"):
        derive_reference_extrema(
            timeframe="15m", bucket_ts=bucket_ts, reference_feature=ref,
            reference_klines=tuple(klines))


def test_extrema_bar_at_bucket_end_errors():
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(bucket_ts=bucket_ts, timeframe="15m", bars_expected=15)
    klines = list(make_klines(bucket_ts, 14))
    klines.append(make_kline_row(ts=bucket_ts + timedelta(minutes=15)))  # == bucket_end
    with pytest.raises(V2AlignedInputError, match="not on the exact"):
        derive_reference_extrema(
            timeframe="15m", bucket_ts=bucket_ts, reference_feature=ref,
            reference_klines=tuple(klines))


def test_extrema_non_finite_high_errors():
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(bucket_ts=bucket_ts, timeframe="15m", bars_expected=15)
    klines = list(make_klines(bucket_ts, 15))
    klines[0] = dict(klines[0], high=float("inf"))
    with pytest.raises(V2AlignedInputError, match="non-finite"):
        derive_reference_extrema(
            timeframe="15m", bucket_ts=bucket_ts, reference_feature=ref,
            reference_klines=tuple(klines))


def test_extrema_nan_low_errors():
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(bucket_ts=bucket_ts, timeframe="15m", bars_expected=15)
    klines = list(make_klines(bucket_ts, 15))
    klines[0] = dict(klines[0], low=float("nan"))
    with pytest.raises(V2AlignedInputError, match="non-finite"):
        derive_reference_extrema(
            timeframe="15m", bucket_ts=bucket_ts, reference_feature=ref,
            reference_klines=tuple(klines))


def test_extrema_high_less_than_low_errors():
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(bucket_ts=bucket_ts, timeframe="15m", bars_expected=15)
    klines = list(make_klines(bucket_ts, 15))
    klines[0] = dict(klines[0], high=100.0, low=200.0)
    with pytest.raises(V2AlignedInputError, match="high < low"):
        derive_reference_extrema(
            timeframe="15m", bucket_ts=bucket_ts, reference_feature=ref,
            reference_klines=tuple(klines))


def test_extrema_has_gap_true_is_unavailable_not_error():
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(bucket_ts=bucket_ts, timeframe="15m", has_gap=True)
    result = derive_reference_extrema(
        timeframe="15m", bucket_ts=bucket_ts, reference_feature=ref, reference_klines=())
    assert result is None


def test_extrema_is_usable_false_is_unavailable_not_error():
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(bucket_ts=bucket_ts, timeframe="15m", is_usable=False)
    result = derive_reference_extrema(
        timeframe="15m", bucket_ts=bucket_ts, reference_feature=ref, reference_klines=())
    assert result is None


def test_extrema_bars_present_not_equal_expected_is_unavailable_not_error():
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(
        bucket_ts=bucket_ts, timeframe="15m", bars_expected=15, bars_present=14)
    result = derive_reference_extrema(
        timeframe="15m", bucket_ts=bucket_ts, reference_feature=ref, reference_klines=())
    assert result is None


def test_extrema_close_price_none_is_unavailable_not_error():
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(bucket_ts=bucket_ts, timeframe="15m", close_price=None)
    result = derive_reference_extrema(
        timeframe="15m", bucket_ts=bucket_ts, reference_feature=ref, reference_klines=())
    assert result is None


def test_extrema_reference_feature_missing_is_unavailable_not_error():
    result = derive_reference_extrema(
        timeframe="15m", bucket_ts=dt(2026, 8, 15, 11, 0), reference_feature=None,
        reference_klines=())
    assert result is None


def test_extrema_rejects_timeframes_outside_structural_set():
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(bucket_ts=bucket_ts, timeframe="5m", bars_expected=5)
    with pytest.raises(V2AlignedInputError, match="only defined for"):
        derive_reference_extrema(
            timeframe="5m", bucket_ts=bucket_ts, reference_feature=ref,
            reference_klines=make_klines(bucket_ts, 5))


# ---- malformed bar ts: a structurally-conforming but broken/fake reader
# can bypass storage's own ts validation entirely, so this module's own
# defense must fire -- V2AlignedInputError, never a bare
# TypeError/AttributeError leaking out of a comparison or .isoformat() call.
def test_extrema_string_bar_ts_rejected_not_a_bare_exception():
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(bucket_ts=bucket_ts, timeframe="15m", bars_expected=15)
    klines = list(make_klines(bucket_ts, 15))
    klines[0] = dict(klines[0], ts="2026-08-15T11:00:00Z")
    with pytest.raises(V2AlignedInputError, match="must be a datetime"):
        derive_reference_extrema(
            timeframe="15m", bucket_ts=bucket_ts, reference_feature=ref,
            reference_klines=tuple(klines))


def test_extrema_naive_bar_ts_rejected_not_a_bare_exception():
    bucket_ts = dt(2026, 8, 15, 11, 0)
    ref = make_reference_feature_row(bucket_ts=bucket_ts, timeframe="15m", bars_expected=15)
    klines = list(make_klines(bucket_ts, 15))
    klines[0] = dict(klines[0], ts=datetime(2026, 8, 15, 11, 0))  # no tzinfo
    with pytest.raises(V2AlignedInputError, match="timezone-aware"):
        derive_reference_extrema(
            timeframe="15m", bucket_ts=bucket_ts, reference_feature=ref,
            reference_klines=tuple(klines))


# ---- end-to-end: the assembler skips the raw fetch when the gate fails ----
def test_assembler_skips_raw_kline_fetch_when_reference_feature_missing():
    reader = RecordingReader()  # no reference_feature entries at all
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    assert result.by_timeframe["15m"].reference_klines is None
    assert result.by_timeframe["15m"].reference_extrema is None
    assert not any(name == "reference_klines" for name, _ in reader.calls)


def test_assembler_skips_raw_kline_fetch_when_gate_fails():
    bucket_ts = dt(2026, 8, 15, 11, 45)  # 15m bucket for T=12:10
    reader = RecordingReader(
        reference_feature={"15m": make_reference_feature_row(
            bucket_ts=bucket_ts, timeframe="15m", is_usable=False)})
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    assert result.by_timeframe["15m"].reference_klines is None
    assert result.by_timeframe["15m"].reference_extrema is None
    assert not any(name == "reference_klines" for name, _ in reader.calls)


def test_assembler_fetches_and_derives_extrema_when_gate_passes():
    bucket_ts = dt(2026, 8, 15, 11, 45)  # 15m bucket for T=12:10
    reader = RecordingReader(
        reference_feature={"15m": make_reference_feature_row(
            bucket_ts=bucket_ts, timeframe="15m", bars_expected=15)},
        reference_klines={bucket_ts: make_klines(bucket_ts, 15, high=65200.0, low=64800.0)},
    )
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    tf_inputs = result.by_timeframe["15m"]
    assert tf_inputs.reference_klines is not None and len(tf_inputs.reference_klines) == 15
    assert tf_inputs.reference_extrema == V2ReferenceExtrema(high=65200.0, low=64800.0)


def test_assembler_raises_when_gate_passes_but_raw_set_is_corrupt():
    # EFV claims full/usable coverage, but the reader hands back a broken
    # (too-short) raw set -- must fail loudly, never silently downgrade to
    # None/partial.
    bucket_ts = dt(2026, 8, 15, 11, 45)
    reader = RecordingReader(
        reference_feature={"15m": make_reference_feature_row(
            bucket_ts=bucket_ts, timeframe="15m", bars_expected=15)},
        reference_klines={bucket_ts: make_klines(bucket_ts, 14)},  # one short
    )
    with pytest.raises(V2AlignedInputError, match="expected exactly"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_5m_and_4h_never_populate_reference_klines_or_extrema():
    bucket_ts_5m = dt(2026, 8, 15, 12, 5)
    bucket_ts_4h = dt(2026, 8, 15, 8, 0)
    reader = RecordingReader(
        reference_feature={
            "5m": make_reference_feature_row(bucket_ts=bucket_ts_5m, timeframe="5m",
                                             bars_expected=5),
            "4h": make_reference_feature_row(bucket_ts=bucket_ts_4h, timeframe="4h",
                                             bars_expected=240),
        },
    )
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    assert result.by_timeframe["5m"].reference_klines is None
    assert result.by_timeframe["5m"].reference_extrema is None
    assert result.by_timeframe["4h"].reference_klines is None
    assert result.by_timeframe["4h"].reference_extrema is None
    assert not any(name == "reference_klines" for name, _ in reader.calls)


# ============================================================================
# 5. DEFENSIVE FAKE-READER TESTS — every mismatch must raise
# V2AlignedInputError, never a bare KeyError/TypeError, never trusted.
# ============================================================================
def test_consensus_wrong_bucket_ts_rejected():
    reader = RecordingReader(consensus={"5m": make_consensus_row(
        bucket_ts=dt(2026, 8, 15, 12, 0), timeframe="5m")})  # wrong bucket
    with pytest.raises(V2AlignedInputError, match="consensus"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_consensus_wrong_calculation_version_rejected():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    reader = RecordingReader(consensus={"5m": make_consensus_row(
        bucket_ts=bucket_ts, timeframe="5m", calculation_version="c" * 16)})
    with pytest.raises(V2AlignedInputError, match="calculation_version"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_consensus_wrong_feature_schema_version_rejected():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    reader = RecordingReader(consensus={"5m": make_consensus_row(
        bucket_ts=bucket_ts, timeframe="5m", feature_schema_version=99)})
    with pytest.raises(V2AlignedInputError, match="feature_schema_version"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_percentile_lookahead_violation_rejected():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    reader = RecordingReader(percentiles={"5m": (make_percentile_row(
        bucket_ts=bucket_ts, timeframe="5m", metric="price_move_pct_median",
        percentile_window="7d", sample_window_end=bucket_ts),)})  # == bucket_ts, forbidden
    with pytest.raises(V2AlignedInputError, match="no-lookahead"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_health_snapshot_after_bucket_end_cutoff_rejected():
    bucket_ts_5m = dt(2026, 8, 15, 12, 5)
    bucket_end_5m = dt(2026, 8, 15, 12, 10)
    reader = RecordingReader(health_by_cutoff={
        bucket_end_5m: {("binance", "price"): make_health_row(
            snapshot_ts=bucket_end_5m + timedelta(minutes=1))},
    })
    with pytest.raises(V2AlignedInputError, match="no-lookahead"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


# ============================================================================
# 5b. DOMAIN-ERROR HARDENING FOR MALFORMED PRESENT TIMESTAMPS (V2-H2d,
# docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §2.1c). Confirmed live bug:
# `snapshot_ts`/`sample_window_end` used to be compared directly with no
# (or an incomplete) type/timezone check first, so a naive/non-UTC/
# wrong-type PRESENT value leaked a raw TypeError instead of failing as
# the documented V2AlignedInputError. Corruption precedence: these are
# malformed PRESENT values, never treated as ordinary missingness.
# ============================================================================
def test_percentile_sample_window_end_wrong_type_rejected_not_a_bare_exception():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    reader = RecordingReader(percentiles={"5m": (make_percentile_row(
        bucket_ts=bucket_ts, timeframe="5m", metric="price_move_pct_median",
        percentile_window="7d", sample_window_end="not-a-datetime"),)})
    with pytest.raises(V2AlignedInputError, match="sample_window_end"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_percentile_sample_window_end_naive_datetime_rejected_not_a_bare_typeerror():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    naive = datetime(2026, 8, 15, 12, 0)  # no tzinfo -- would raise a raw
                                           # TypeError comparing against an
                                           # aware bucket_ts, pre-fix
    reader = RecordingReader(percentiles={"5m": (make_percentile_row(
        bucket_ts=bucket_ts, timeframe="5m", metric="price_move_pct_median",
        percentile_window="7d", sample_window_end=naive),)})
    with pytest.raises(V2AlignedInputError, match="sample_window_end"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_percentile_sample_window_end_non_utc_rejected():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    non_utc = datetime(2026, 8, 15, 11, 0, tzinfo=timezone(timedelta(hours=1)))
    reader = RecordingReader(percentiles={"5m": (make_percentile_row(
        bucket_ts=bucket_ts, timeframe="5m", metric="price_move_pct_median",
        percentile_window="7d", sample_window_end=non_utc),)})
    with pytest.raises(V2AlignedInputError, match="sample_window_end"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_percentile_sample_window_end_strictly_after_bucket_ts_rejected():
    # A well-typed UTC value that is simply in the FUTURE relative to
    # bucket_ts (not merely equal to it, the case test_percentile_
    # lookahead_violation_rejected above already covers) must also be
    # rejected by the same no-lookahead check.
    bucket_ts = dt(2026, 8, 15, 12, 5)
    reader = RecordingReader(percentiles={"5m": (make_percentile_row(
        bucket_ts=bucket_ts, timeframe="5m", metric="price_move_pct_median",
        percentile_window="7d", sample_window_end=bucket_ts + timedelta(minutes=1)),)})
    with pytest.raises(V2AlignedInputError, match="no-lookahead"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_health_snapshot_ts_wrong_type_rejected_not_a_bare_exception():
    bucket_end_5m = dt(2026, 8, 15, 12, 10)
    reader = RecordingReader(health_by_cutoff={
        bucket_end_5m: {("binance", "price"): make_health_row(snapshot_ts="not-a-datetime")},
    })
    with pytest.raises(V2AlignedInputError, match="snapshot_ts"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_health_snapshot_ts_naive_datetime_rejected_not_a_bare_typeerror():
    bucket_end_5m = dt(2026, 8, 15, 12, 10)
    naive = datetime(2026, 8, 15, 12, 0)  # no tzinfo -- would raise a raw
                                           # TypeError comparing against an
                                           # aware bucket_end, pre-fix
    reader = RecordingReader(health_by_cutoff={
        bucket_end_5m: {("binance", "price"): make_health_row(snapshot_ts=naive)},
    })
    with pytest.raises(V2AlignedInputError, match="snapshot_ts"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_health_snapshot_ts_non_utc_rejected():
    bucket_end_5m = dt(2026, 8, 15, 12, 10)
    non_utc = datetime(2026, 8, 15, 11, 5, tzinfo=timezone(timedelta(hours=1)))
    reader = RecordingReader(health_by_cutoff={
        bucket_end_5m: {("binance", "price"): make_health_row(snapshot_ts=non_utc)},
    })
    with pytest.raises(V2AlignedInputError, match="snapshot_ts"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_reference_feature_wrong_bucket_ts_rejected():
    reader = RecordingReader(reference_feature={"5m": make_reference_feature_row(
        bucket_ts=dt(2026, 8, 15, 12, 0), timeframe="5m")})  # wrong bucket for 5m@12:10
    with pytest.raises(V2AlignedInputError, match="reference_feature"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_reference_feature_wrong_timeframe_rejected():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    reader = RecordingReader(reference_feature={"5m": make_reference_feature_row(
        bucket_ts=bucket_ts, timeframe="15m")})  # served under "5m" key but tagged 15m
    with pytest.raises(V2AlignedInputError, match="reference_feature"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_reference_feature_wrong_symbol_rejected():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    reader = RecordingReader(reference_feature={"5m": make_reference_feature_row(
        bucket_ts=bucket_ts, timeframe="5m", symbol="ETHUSDT")})
    with pytest.raises(V2AlignedInputError, match="reference_feature"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_reference_klines_wrong_exchange_rejected():
    bucket_ts = dt(2026, 8, 15, 11, 45)
    reader = RecordingReader(
        reference_feature={"15m": make_reference_feature_row(
            bucket_ts=bucket_ts, timeframe="15m", bars_expected=15)},
        reference_klines={bucket_ts: tuple(
            dict(bar, exchange="bybit") for bar in make_klines(bucket_ts, 15))},
    )
    with pytest.raises(V2AlignedInputError, match="reference_klines"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_reference_klines_wrong_symbol_rejected():
    bucket_ts = dt(2026, 8, 15, 11, 45)
    reader = RecordingReader(
        reference_feature={"15m": make_reference_feature_row(
            bucket_ts=bucket_ts, timeframe="15m", bars_expected=15)},
        reference_klines={bucket_ts: tuple(
            dict(bar, symbol="ETHUSDT") for bar in make_klines(bucket_ts, 15))},
    )
    with pytest.raises(V2AlignedInputError, match="reference_klines"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_percentile_wrong_calculation_version_rejected():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    reader = RecordingReader(percentiles={"5m": (make_percentile_row(
        bucket_ts=bucket_ts, timeframe="5m", metric="price_move_pct_median",
        percentile_window="7d", calculation_version="c" * 16),)})
    with pytest.raises(V2AlignedInputError, match="calculation_version"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_percentile_wrong_scope_rejected():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    reader = RecordingReader(percentiles={"5m": (make_percentile_row(
        bucket_ts=bucket_ts, timeframe="5m", metric="price_move_pct_median",
        percentile_window="7d", scope="exchange"),)})
    with pytest.raises(V2AlignedInputError, match="scope"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_percentile_nonblank_exchange_rejected():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    reader = RecordingReader(percentiles={"5m": (make_percentile_row(
        bucket_ts=bucket_ts, timeframe="5m", metric="price_move_pct_median",
        percentile_window="7d", exchange="binance"),)})
    with pytest.raises(V2AlignedInputError, match="exchange"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_percentile_wrong_symbol_rejected():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    reader = RecordingReader(percentiles={"5m": (make_percentile_row(
        bucket_ts=bucket_ts, timeframe="5m", metric="price_move_pct_median",
        percentile_window="7d", symbol="ETHUSDT"),)})
    with pytest.raises(V2AlignedInputError, match="symbol"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_percentile_duplicate_metric_window_pair_rejected():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    row = make_percentile_row(
        bucket_ts=bucket_ts, timeframe="5m", metric="price_move_pct_median",
        percentile_window="7d")
    reader = RecordingReader(percentiles={"5m": (row, dict(row))})
    with pytest.raises(V2AlignedInputError, match="duplicate"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_health_reader_omitting_a_requested_key_rejected():
    # A broken/malformed reader that silently drops a requested pair
    # instead of returning it as an explicit None -- reader-side
    # corruption, must fail loudly rather than being patched up here.
    class OmittingReader(RecordingReader):
        async def fetch_v2_data_health_at_cutoff(self, **kw):
            self.calls.append(("data_health_at_cutoff", kw))
            return {}  # omits the requested ("binance", "price") key entirely

    reader = OmittingReader()
    with pytest.raises(V2AlignedInputError, match="missing"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_health_reader_returning_an_unrequested_key_rejected():
    class ExtraKeyReader(RecordingReader):
        async def fetch_v2_data_health_at_cutoff(self, **kw):
            self.calls.append(("data_health_at_cutoff", kw))
            return {("binance", "price"): None, ("okx", "funding"): None}

    reader = ExtraKeyReader()
    with pytest.raises(V2AlignedInputError, match="unexpected"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_health_row_exchange_metric_mismatch_with_its_key_rejected():
    bucket_end_5m = dt(2026, 8, 15, 12, 10)
    reader = RecordingReader(health_by_cutoff={
        bucket_end_5m: {("binance", "price"): make_health_row(
            snapshot_ts=bucket_end_5m, exchange="bybit", metric="price")},
    })
    with pytest.raises(V2AlignedInputError, match="exchange/metric"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_health_row_wrong_symbol_rejected():
    bucket_end_5m = dt(2026, 8, 15, 12, 10)
    reader = RecordingReader(health_by_cutoff={
        bucket_end_5m: {("binance", "price"): make_health_row(
            snapshot_ts=bucket_end_5m, symbol="ETHUSDT")},
    })
    with pytest.raises(V2AlignedInputError, match="symbol"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


def test_health_row_malformed_snapshot_ts_rejected():
    bucket_end_5m = dt(2026, 8, 15, 12, 10)
    reader = RecordingReader(health_by_cutoff={
        bucket_end_5m: {("binance", "price"): make_health_row(snapshot_ts="not-a-datetime")},
    })
    with pytest.raises(V2AlignedInputError, match="snapshot_ts"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


# ============================================================================
# 6. MISSINGNESS IS PRESERVED — never a fallback, never fails the snapshot
# ============================================================================
def test_missing_consensus_is_none_not_an_error():
    reader = RecordingReader()
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    for tf in ALIGNED_TIMEFRAMES:
        assert result.by_timeframe[tf].consensus is None


def test_missing_percentiles_is_empty_tuple_not_an_error():
    reader = RecordingReader()
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    for tf in ALIGNED_TIMEFRAMES:
        assert result.by_timeframe[tf].percentiles == ()


def test_missing_health_pair_is_none_not_an_error():
    # PR #34's frozen contract: the health result mapping contains EVERY
    # requested (exchange, metric) key, explicitly mapped to None when no
    # eligible snapshot exists — the key is never silently omitted.
    reader = RecordingReader()  # no overrides -> every requested pair is None
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    for tf in ALIGNED_TIMEFRAMES:
        health = result.by_timeframe[tf].health
        assert ("binance", "price") in health
        assert health[("binance", "price")] is None


def test_missing_reference_feature_is_none_not_an_error():
    reader = RecordingReader()
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    for tf in ALIGNED_TIMEFRAMES:
        assert result.by_timeframe[tf].reference_feature is None


def test_a_reader_returning_no_data_at_all_still_produces_a_full_snapshot():
    # legitimate absence across the board must never fail the WHOLE snapshot.
    reader = RecordingReader()
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    assert isinstance(result, V2AlignedInputs)
    assert set(result.by_timeframe) == set(ALIGNED_TIMEFRAMES)


# ============================================================================
# 7. IMMUTABILITY
# ============================================================================
def test_result_is_frozen_and_by_timeframe_is_a_mappingproxy():
    reader = RecordingReader()
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    assert isinstance(result.by_timeframe, MappingProxyType)
    with pytest.raises((AttributeError, TypeError)):
        result.T = dt(2026, 8, 15, 12, 15)  # type: ignore[misc]


def test_timeframe_inputs_is_frozen():
    reader = RecordingReader()
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    tf_inputs = result.by_timeframe["5m"]
    assert isinstance(tf_inputs, V2TimeframeInputs)
    with pytest.raises((AttributeError, TypeError)):
        tf_inputs.consensus = {}  # type: ignore[misc]


def test_reference_extrema_is_frozen():
    extrema = V2ReferenceExtrema(high=1.0, low=0.5)
    with pytest.raises((AttributeError, TypeError)):
        extrema.high = 2.0  # type: ignore[misc]


# ---- deep freeze: a frozen dataclass only stops REASSIGNING its own
# fields -- it does nothing about a nested dict/list a field points at.
# `V2AlignedInputReader` is a structural Protocol (every reader here is a
# plain mutable dict), so the snapshot must own DETACHED, deeply immutable
# copies: mutating the reader's ORIGINAL objects after load must never be
# visible in the snapshot, and mutating the snapshot's own nested output
# must fail.
def test_deep_freeze_consensus_immutable_and_independent_of_original():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    nested_values = [1, 2, 3]
    consensus = make_consensus_row(
        bucket_ts=bucket_ts, timeframe="5m", nested={"values": nested_values})
    reader = RecordingReader(consensus={"5m": consensus})
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    snapshot = result.by_timeframe["5m"].consensus

    nested_values.append(4)
    consensus["price_move_pct_median"] = 999

    assert snapshot["price_move_pct_median"] == 0.1
    assert snapshot["nested"]["values"] == (1, 2, 3)
    assert isinstance(snapshot, MappingProxyType)
    assert isinstance(snapshot["nested"], MappingProxyType)
    assert isinstance(snapshot["nested"]["values"], tuple)
    with pytest.raises(TypeError):
        snapshot["price_move_pct_median"] = 111
    with pytest.raises(TypeError):
        snapshot["nested"]["x"] = 1


def test_deep_freeze_percentile_row_immutable_and_independent_of_original():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    nested_values = [1, 2, 3]
    row = make_percentile_row(
        bucket_ts=bucket_ts, timeframe="5m", metric="price_move_pct_median",
        percentile_window="7d", nested={"values": nested_values})
    reader = RecordingReader(percentiles={"5m": (row,)})
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    percentiles = result.by_timeframe["5m"].percentiles
    assert isinstance(percentiles, tuple)
    snapshot = percentiles[0]

    nested_values.append(4)
    row["value"] = 999

    assert snapshot["value"] == 0.1
    assert snapshot["nested"]["values"] == (1, 2, 3)
    with pytest.raises(TypeError):
        snapshot["value"] = 111


def test_deep_freeze_health_row_immutable_and_independent_of_original():
    bucket_end_5m = dt(2026, 8, 15, 12, 10)
    nested_values = [1, 2, 3]
    row = make_health_row(snapshot_ts=bucket_end_5m, nested={"values": nested_values})
    reader = RecordingReader(health_by_cutoff={bucket_end_5m: {("binance", "price"): row}})
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    health = result.by_timeframe["5m"].health
    assert isinstance(health, MappingProxyType)
    snapshot = health[("binance", "price")]

    nested_values.append(4)
    row["is_usable"] = False

    assert snapshot["is_usable"] is True
    assert snapshot["nested"]["values"] == (1, 2, 3)
    with pytest.raises(TypeError):
        snapshot["is_usable"] = False


def test_deep_freeze_reference_feature_immutable_and_independent_of_original():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    nested_values = [1, 2, 3]
    row = make_reference_feature_row(
        bucket_ts=bucket_ts, timeframe="5m", nested={"values": nested_values})
    reader = RecordingReader(reference_feature={"5m": row})
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    snapshot = result.by_timeframe["5m"].reference_feature

    nested_values.append(4)
    row["close_price"] = 0.0

    assert snapshot["close_price"] == 65000.0
    assert snapshot["nested"]["values"] == (1, 2, 3)
    with pytest.raises(TypeError):
        snapshot["close_price"] = 0.0


def test_deep_freeze_reference_kline_immutable_and_independent_of_original():
    bucket_ts = dt(2026, 8, 15, 11, 45)  # 15m bucket for T=12:10
    nested_values = [1, 2, 3]
    klines = list(make_klines(bucket_ts, 15))
    klines[0] = dict(klines[0], nested={"values": nested_values})
    reader = RecordingReader(
        reference_feature={"15m": make_reference_feature_row(
            bucket_ts=bucket_ts, timeframe="15m", bars_expected=15)},
        reference_klines={bucket_ts: tuple(klines)},
    )
    result = _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))
    snapshot_klines = result.by_timeframe["15m"].reference_klines
    assert isinstance(snapshot_klines, tuple)
    snapshot = snapshot_klines[0]

    nested_values.append(4)
    klines[0]["high"] = 0.0

    assert snapshot["nested"]["values"] == (1, 2, 3)
    with pytest.raises(TypeError):
        snapshot["high"] = 0.0


def test_deep_freeze_rejects_unrecognized_value_type():
    bucket_ts = dt(2026, 8, 15, 12, 5)
    consensus = make_consensus_row(bucket_ts=bucket_ts, timeframe="5m", weird=frozenset({1, 2}))
    reader = RecordingReader(consensus={"5m": consensus})
    with pytest.raises(V2AlignedInputError, match="unrecognized type"):
        _run(load_v2_aligned_inputs(reader, _default_request(dt(2026, 8, 15, 12, 10))))


# ============================================================================
# 8. NO WALL CLOCK / NO NEW I/O — module-source purity checks
# ============================================================================
def _executable_body_source(module) -> str:
    """Source with every docstring stripped so a prose mention inside
    documentation cannot false-positive a forbidden-token scan (mirrors
    tests/storage/test_v2_alignment_readers.py's own helper)."""
    import ast
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_module_has_no_clock_random_uuid_network_filesystem_access():
    body_src = _executable_body_source(aligned_inputs_module)
    forbidden = (
        "datetime.now(", "datetime.utcnow(", "time.time(", "time.monotonic(",
        "import random", "import uuid", "import yaml", "os.environ", "os.getenv",
        "requests.", "httpx.", "open(", "asyncpg", "subprocess",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden token found: {token!r}"


def test_module_imports_nothing_from_storage_runtime_main_notifications():
    import ast
    tree = ast.parse(inspect.getsource(aligned_inputs_module))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            for banned in ("storage", "runtime", "main", "notifications"):
                assert not name.startswith(banned), f"forbidden import: {name}"


def test_load_v2_aligned_inputs_is_a_coroutine_function():
    assert inspect.iscoroutinefunction(load_v2_aligned_inputs)


def test_derive_reference_extrema_is_a_plain_sync_function():
    assert not inspect.iscoroutinefunction(derive_reference_extrema)


# ============================================================================
# 9. NO CONTEXT/REGIME/BIAS/DETECTOR LOGIC — source-level guarantee this
# PR does ZERO Stage 4/5 decision-making.
# ============================================================================
def test_no_context_or_setup_logic_implemented_yet():
    body_src = _executable_body_source(aligned_inputs_module)
    forbidden = (
        "normalized_evidence", "compression_score", "REGIME_", "BIAS_",
        "oi_confirmation", "directional_context_gate",
        "TREND_PULLBACK", "COMPRESSION_BREAKOUT", "CONFIRMED_BREAKOUT",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden Stage 4/5 token found: {token!r}"
