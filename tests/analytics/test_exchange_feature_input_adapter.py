"""Unit tests for analytics/feature_engine/input_adapter.py.

Pure/deterministic — no DB, network, clock. Uses fake raw bundles and a fake
reader; async is driven with asyncio.run (no pytest-asyncio dependency).
"""
from __future__ import annotations

import asyncio
import copy
import dataclasses
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from common.stage2_config import Stage2Config
from common.versioning import compute_calculation_version
from storage.stage2_readers import ExchangeFeatureRawBundle
from analytics.feature_engine.exchange_features import compute_exchange_features
from analytics.feature_engine.models import TIMEFRAME_MINUTES
from analytics.feature_engine.input_adapter import (
    AssemblyContext, FeatureInputError, _allowed_missing_bars,
    assemble_exchange_feature_request, build_assembly_context,
    load_exchange_feature_request,
)

CFG = Stage2Config.load()
EX, SYM, MT = "binance", "BTCUSDT", "perp"
B = datetime(2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc)   # 5m/1h/4h aligned, whole minute
_S = object()


def _run(coro):
    return asyncio.run(coro)


def _m(**kw):
    return MappingProxyType(dict(kw))


def _kline(minute, **kw):
    base = dict(exchange=EX, symbol=SYM, ts=B + timedelta(minutes=minute),
                open=100.0, high=110.0, low=95.0, close=101.0, volume=10.0,
                taker_buy_volume=None, taker_sell_volume=None)
    base.update(kw)
    return _m(**base)


def _oi(minute, oi_raw=100.0, oi_unit="base", **kw):
    base = dict(exchange=EX, symbol=SYM, ts=B + timedelta(minutes=minute),
                oi_raw=oi_raw, oi_unit=oi_unit)
    base.update(kw)
    return _m(**base)


def _fund(minute=-1, funding_rate=0.0001, **kw):
    base = dict(exchange=EX, symbol=SYM, ts=B + timedelta(minutes=minute),
                funding_rate=funding_rate)
    base.update(kw)
    return _m(**base)


def _liq(id_, minute, side="long", notional=100.0, snap=True, **kw):
    base = dict(id=id_, exchange=EX, symbol=SYM, ts=B + timedelta(minutes=minute),
                side=side, notional=notional, is_snapshot_feed=snap)
    base.update(kw)
    return _m(**base)


def _inst(**kw):
    base = dict(exchange=EX, symbol=SYM, market_type=MT, exchange_instrument_id="ID",
                quantity_unit="base", contract_multiplier=None, tick_size=0.1,
                price_precision=None, quantity_precision=None,
                metadata_source="exchange_api", fetched_at=B, is_stale=False, note=None)
    base.update(kw)
    return _m(**base)


def _cap(coverage_type="snapshot", **kw):
    base = dict(exchange=EX, symbol=SYM, market_type=MT, metric="liquidations",
                live_supported=True, historical_supported=False,
                coverage_type=coverage_type, expected_freshness_s=None, enabled=True)
    base.update(kw)
    return _m(**base)


def _bundle(*, klines=(), oi=(), funding=None, liqs=(), inst=_S, cap=_S):
    return ExchangeFeatureRawBundle(
        klines=tuple(klines), open_interest=tuple(oi), latest_funding=funding,
        liquidations=tuple(liqs), instrument=(_inst() if inst is _S else inst),
        liquidation_capability=(_cap() if cap is _S else cap))


def _ctx(**over):
    kw = dict(exchange=EX, symbol=SYM, market_type=MT, timeframe="5m", bucket_ts=B,
              code_version="code-v1", liquidation_feed_available=True)
    kw.update(over)
    return build_assembly_context(CFG, **kw)


# ============================ A. context / no-read ==========================
@pytest.mark.parametrize("ex", ["binance", "bybit", "okx"])
def test_valid_contexts(ex):
    ctx = _ctx(exchange=ex)
    assert ctx.exchange == ex and ctx.market_type == "perp"
    assert ctx.bucket_end == B + timedelta(minutes=5)


@pytest.mark.parametrize("over", [
    {"exchange": "bitget"}, {"exchange": "unknown"}, {"exchange": 5},
    {"symbol": "ETHUSDT"}, {"symbol": "btcusdt"},
    {"market_type": "spot"},
    {"timeframe": "3m"}, {"timeframe": "1d"},
    {"bucket_ts": datetime(2026, 3, 1)},                                   # naive
    {"bucket_ts": datetime(2026, 3, 1, tzinfo=timezone(timedelta(hours=1)))},  # non-UTC
    {"bucket_ts": B + timedelta(seconds=30)},                             # not whole minute
    {"bucket_ts": B + timedelta(minutes=3), "timeframe": "5m"},           # off-grid
    {"code_version": ""}, {"code_version": "  "}, {"code_version": 5},
    {"liquidation_feed_available": "yes"}, {"liquidation_feed_available": 1},
])
def test_invalid_context_rejected(over):
    with pytest.raises(FeatureInputError):
        _ctx(**over)


def test_invalid_context_causes_zero_reader_calls():
    class Reader:
        def __init__(self): self.calls = 0

        async def fetch_exchange_feature_raw_bundle(self, **kw):
            self.calls += 1
            return _bundle()
    r = Reader()
    with pytest.raises(FeatureInputError):
        _run(load_exchange_feature_request(
            r, CFG, exchange="bitget", symbol=SYM, market_type=MT, timeframe="5m",
            bucket_ts=B, code_version="v", liquidation_feed_available=True))
    assert r.calls == 0


def test_stage2_config_type_checked():
    with pytest.raises(FeatureInputError):
        build_assembly_context(object(), exchange=EX, symbol=SYM, market_type=MT,
                               timeframe="5m", bucket_ts=B, code_version="v",
                               liquidation_feed_available=True)


# ============================= B. versioning ================================
def test_versioning_uses_resolved_and_global_exactly():
    ctx = _ctx()
    resolved = CFG.resolve(SYM)
    assert ctx.config_hash == resolved.config_hash()
    assert ctx.config_version == CFG.config_version
    assert ctx.feature_schema_version == CFG.feature_schema_version
    assert ctx.calculation_version == compute_calculation_version(
        CFG.feature_schema_version, resolved.config_hash(), "code-v1")


def test_code_version_change_forks_calc_version():
    assert _ctx(code_version="a").calculation_version != _ctx(code_version="b").calculation_version


# ------------------ B2. instrument_metadata_revision (review 4991738511) ----
def test_context_exposes_instrument_metadata_revision():
    ctx = _ctx()
    assert ctx.instrument_metadata_revision == CFG.resolve(SYM)["instrument_metadata_revision"]
    assert ctx.instrument_metadata_revision == 1   # config/stage2.yaml's own current default


def test_instrument_metadata_revision_change_forks_calc_version():
    raw = copy.deepcopy(CFG._raw)
    raw["defaults"]["instrument_metadata_revision"] = 2
    cfg2 = Stage2Config(raw)
    cfg2._validate()
    other = build_assembly_context(cfg2, exchange=EX, symbol=SYM, market_type=MT,
                                   timeframe="5m", bucket_ts=B, code_version="code-v1",
                                   liquidation_feed_available=True)
    assert other.instrument_metadata_revision == 2
    assert other.calculation_version != _ctx().calculation_version


def test_assemble_fails_closed_on_required_metadata_revision_mismatch():
    """(Tech-lead review 4991738511) The FIRST check assemble_exchange_
    feature_request performs: the resolved config's own
    instrument_metadata_revision must equal the raw bundle's LIVE
    required_metadata_revision, or this fails closed before constructing
    any ExchangeFeatureRequest."""
    bundle = _bundle(inst=_inst(tick_size=0.5))
    stale_bundle = dataclasses.replace(bundle, required_metadata_revision=2)
    with pytest.raises(FeatureInputError, match="instrument_metadata_revision"):
        assemble_exchange_feature_request(_ctx(), stale_bundle)
    # The matching (default) revision succeeds.
    req = assemble_exchange_feature_request(_ctx(), bundle)
    assert req.instrument_metadata.tick_size == 0.5


def test_config_change_forks_calc_version():
    raw = copy.deepcopy(CFG._raw)
    raw["defaults"]["outliers"]["robust_z_threshold"] = 9.9   # any config change
    cfg2 = Stage2Config(raw)
    cfg2._validate()
    other = build_assembly_context(cfg2, exchange=EX, symbol=SYM, market_type=MT,
                                   timeframe="5m", bucket_ts=B, code_version="code-v1",
                                   liquidation_feed_available=True)
    assert other.calculation_version != _ctx().calculation_version


def test_stage2_disabled_still_constructs():
    assert CFG.enabled is False           # master gate off
    assert _ctx().calculation_version      # deterministic construction still works


def test_config_not_mutated_by_build():
    before = copy.deepcopy(CFG._raw)
    _ctx()
    assert CFG._raw == before


# ============================ C. coverage conversion ========================
@pytest.mark.parametrize("tf, expected_allowed", [
    ("1m", 0), ("5m", 0), ("15m", 0), ("1h", 3), ("4h", 12)])
def test_allowed_missing_bars_per_timeframe_at_0_95(tf, expected_allowed):
    assert _ctx(timeframe=tf).allowed_missing_bars == expected_allowed


def test_allowed_missing_bars_coverage_one_and_small():
    for tf in TIMEFRAME_MINUTES:
        assert _allowed_missing_bars(tf, 1.0) == 0                        # full coverage
    assert _allowed_missing_bars("4h", 0.01) == 240 - 3                   # ceil(2.4)=3


@pytest.mark.parametrize("bad", [0, -0.1, 1.0001, 2, True, "0.95",
                                 float("nan"), float("inf")])
def test_invalid_minimum_metric_coverage_rejected(bad):
    with pytest.raises(FeatureInputError):
        _allowed_missing_bars("1h", bad)


def test_decimal_boundary_no_float_drift():
    # 0.95 * 60 = 57 exactly under Decimal; result must be 3 (not 2 via float rounding)
    assert _allowed_missing_bars("1h", 0.95) == 3
    # a value whose float product would dip just under an integer still ceils safely
    assert _allowed_missing_bars("5m", 0.8) == 5 - 4                      # ceil(4.0)=4 -> 1


# =============================== D. bars ====================================
def _five_bars(with_taker=False):
    out = []
    for i in range(5):
        kw = {}
        if with_taker:
            kw = dict(taker_buy_volume=(i + 1.0), taker_sell_volume=(i + 0.5))
        out.append(_kline(i, open=100.0 + i, high=110.0 + i, low=95.0 + i,
                          close=101.0 + i, volume=10.0 + i, **kw))
    return out


def test_bars_complete_bucket_and_order_independent():
    ctx = _ctx()
    req = assemble_exchange_feature_request(ctx, _bundle(klines=_five_bars()))
    assert len(req.bars) == 5
    req_rev = assemble_exchange_feature_request(ctx, _bundle(klines=list(reversed(_five_bars()))))
    assert req.bars == req_rev.bars                                       # sorted by ts


def test_bars_missing_slots_not_synthesized():
    req = assemble_exchange_feature_request(_ctx(), _bundle(klines=[_kline(0), _kline(3)]))
    assert len(req.bars) == 2                                             # gaps left as gaps


def test_bars_nullable_taker_preserved_and_measured_zero():
    req = assemble_exchange_feature_request(_ctx(), _bundle(klines=[
        _kline(0, taker_buy_volume=0.0, taker_sell_volume=0.0), _kline(1)]))
    assert req.bars[0].taker_buy_volume == 0.0                            # measured zero
    assert req.bars[1].taker_buy_volume is None                           # NULL preserved


def test_bars_identity_mismatch_and_required_null_rejected():
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(klines=[_kline(0, exchange="bybit")]))
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(klines=[_kline(0, close=None)]))


# ================================ E. OI =====================================
def test_oi_two_valid_sorted():
    req = assemble_exchange_feature_request(_ctx(), _bundle(oi=[_oi(4, 110.0), _oi(0, 100.0)]))
    assert [o.oi_raw for o in req.open_interest] == [100.0, 110.0]        # ts-sorted


def test_oi_single_and_empty():
    assert len(assemble_exchange_feature_request(_ctx(), _bundle(oi=[_oi(0)])).open_interest) == 1
    assert assemble_exchange_feature_request(_ctx(), _bundle(oi=[])).open_interest == ()


@pytest.mark.parametrize("bad", [{"oi_raw": None}, {"oi_unit": None}, {"oi_unit": "  "},
                                 {"exchange": "okx"}])
def test_oi_invalid_rejected(bad):
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(oi=[_oi(0, **bad)]))


def test_oi_conflicting_duplicates_visible_to_core():
    # adapter passes both through; the pure core fails loudly on conflict
    ctx = _ctx()
    req = assemble_exchange_feature_request(ctx, _bundle(
        klines=[_kline(0)], oi=[_oi(0, 100.0), _oi(0, 101.0)]))
    with pytest.raises(Exception):
        compute_exchange_features(req)


# ============================== F. funding ==================================
def test_funding_none_is_empty():
    assert assemble_exchange_feature_request(_ctx(), _bundle(funding=None)).funding == ()


def test_funding_valid_latest():
    req = assemble_exchange_feature_request(_ctx(), _bundle(funding=_fund(-1, 0.0003)))
    assert len(req.funding) == 1 and req.funding[0].funding_rate == 0.0003


@pytest.mark.parametrize("minute", [5, 6])   # at bucket_end and after
def test_funding_at_or_after_bucket_end_rejected(minute):
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(funding=_fund(minute)))


def test_funding_identity_mismatch_rejected():
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(funding=_fund(-1, symbol="ETHUSDT")))


# ============================ G. liquidations ===============================
def test_liq_available_no_events_measured_zero():
    req = assemble_exchange_feature_request(_ctx(), _bundle(klines=[_kline(0)], liqs=[]))
    v = compute_exchange_features(req)
    assert v.long_liquidation_notional == 0.0 and v.liquidation_event_count == 0


def test_liq_unavailable_no_events_null():
    req = assemble_exchange_feature_request(
        _ctx(liquidation_feed_available=False), _bundle(klines=[_kline(0)], liqs=[]))
    assert req.liquidation_feed_state.is_available is False
    v = compute_exchange_features(req)
    assert v.long_liquidation_notional is None and v.liquidation_event_count is None


def test_liq_unavailable_with_events_rejected():
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(
            _ctx(liquidation_feed_available=False), _bundle(liqs=[_liq(1, 1)]))


def test_liq_null_notional_rejected_zero_preserved():
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(liqs=[_liq(1, 1, notional=None)]))
    req = assemble_exchange_feature_request(_ctx(), _bundle(klines=[_kline(0)], liqs=[_liq(1, 1, notional=0.0)]))
    assert req.liquidations[0].notional == 0.0


def test_liq_identity_and_out_of_window_rejected():
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(liqs=[_liq(1, 1, exchange="okx")]))
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(liqs=[_liq(1, 5)]))   # == bucket_end


def test_liq_snapshot_consistency_binance():
    # snapshot capability -> every event flag must be True
    assemble_exchange_feature_request(_ctx(), _bundle(klines=[_kline(0)], liqs=[_liq(1, 1, snap=True)]))
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(liqs=[_liq(1, 1, snap=False)]))


def test_liq_non_snapshot_consistency_bybit_okx():
    for cov in ("full", "aggregated"):
        ctx = _ctx()
        assemble_exchange_feature_request(ctx, _bundle(
            klines=[_kline(0)], liqs=[_liq(1, 1, snap=False)], cap=_cap(coverage_type=cov)))
        with pytest.raises(FeatureInputError):
            assemble_exchange_feature_request(ctx, _bundle(
                liqs=[_liq(1, 1, snap=True)], cap=_cap(coverage_type=cov)))


def test_liq_same_timestamp_ordered_by_id_all_preserved():
    req = assemble_exchange_feature_request(_ctx(), _bundle(
        klines=[_kline(0)], liqs=[_liq(3, 1), _liq(1, 1), _liq(2, 1)]))
    assert len(req.liquidations) == 3                                     # all preserved
    # deterministic regardless of input order
    req2 = assemble_exchange_feature_request(_ctx(), _bundle(
        klines=[_kline(0)], liqs=[_liq(2, 1), _liq(3, 1), _liq(1, 1)]))
    assert req.liquidations == req2.liquidations


def test_liq_event_presence_never_flips_availability():
    req = assemble_exchange_feature_request(_ctx(liquidation_feed_available=True),
                                            _bundle(klines=[_kline(0)], liqs=[_liq(1, 1)]))
    assert req.liquidation_feed_state.is_available is True   # from the flag, not row presence


# ========================== H. instrument metadata =========================
def test_instrument_full_and_absent():
    req = assemble_exchange_feature_request(_ctx(), _bundle(inst=_inst(quantity_unit="contracts",
                                            contract_multiplier=0.01)))
    assert req.instrument_metadata.quantity_unit == "contracts"
    assert req.instrument_metadata.contract_multiplier == 0.01
    assert assemble_exchange_feature_request(_ctx(), _bundle(inst=None)).instrument_metadata is None


def test_instrument_stale_lkg_preserved_and_null_note_default():
    req = assemble_exchange_feature_request(_ctx(), _bundle(inst=_inst(is_stale=True, note=None)))
    assert req.instrument_metadata.is_stale is True          # stale LKG not rejected
    assert req.instrument_metadata.note == ""                # NULL note -> model default


def test_instrument_contracts_null_multiplier_passed_honestly():
    req = assemble_exchange_feature_request(_ctx(), _bundle(klines=_five_bars(), inst=_inst(
        quantity_unit="contracts", contract_multiplier=None)))
    v = compute_exchange_features(req)
    assert v.volume_raw is not None and v.volume_notional_usd is None      # fail-closed, no default


@pytest.mark.parametrize("bad", [
    {"exchange": "okx"}, {"symbol": "ETHUSDT"}, {"market_type": "spot"},
    {"quantity_unit": "lots"}, {"metadata_source": "guessed"},
    {"is_stale": "no"}, {"price_precision": 1.5}, {"exchange_instrument_id": ""},
    {"fetched_at": 123}])
def test_instrument_malformed_rejected(bad):
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(inst=_inst(**bad)))


# ============================== I. capability ===============================
@pytest.mark.parametrize("cov", ["snapshot", "full", "aggregated"])
def test_capability_valid_coverage_types(cov):
    snap = cov == "snapshot"
    req = assemble_exchange_feature_request(_ctx(), _bundle(
        klines=[_kline(0)], liqs=[_liq(1, 1, snap=snap)], cap=_cap(coverage_type=cov)))
    assert req.liquidation_feed_state.coverage_type == cov
    assert req.liquidation_feed_state.is_snapshot_feed is snap


def test_capability_missing_rejected():
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(cap=None))


@pytest.mark.parametrize("bad", [
    {"exchange": "okx"}, {"symbol": "ETHUSDT"}, {"market_type": "spot"},
    {"metric": "ohlcv"}, {"enabled": False}, {"live_supported": "yes"},
    {"historical_supported": 1}, {"coverage_type": "weird"},
    {"live_supported": True, "coverage_type": "unavailable"},             # contradiction
    {"live_supported": False, "coverage_type": "full"}])                  # contradiction
def test_capability_invalid_rejected(bad):
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(cap=_cap(**bad)))


# =========================== J. pure-core integration =======================
def _full_bundle(**over):
    kw = dict(klines=_five_bars(with_taker=True),
              oi=[_oi(0, 100.0), _oi(4, 110.0)],
              funding=_fund(-1, 0.0002),
              liqs=[_liq(1, 1, notional=100.0, snap=True)],
              inst=_inst(), cap=_cap())
    kw.update(over)
    return _bundle(**kw)


def test_integration_valid_5m_bucket():
    v = compute_exchange_features(assemble_exchange_feature_request(_ctx(), _full_bundle()))
    assert v.bars_expected == 5 and v.bars_present == 5 and v.is_usable is True
    assert v.oi_change_pct == pytest.approx(10.0)
    assert v.funding_rate == pytest.approx(0.0002)
    assert v.long_liquidation_notional == pytest.approx(100.0)


def test_integration_missing_metadata_keeps_price_null_notional():
    v = compute_exchange_features(assemble_exchange_feature_request(
        _ctx(), _full_bundle(inst=None)))
    assert v.price_move_pct is not None                       # price/structure fine
    assert v.volume_notional_usd is None and v.volume_raw is not None  # normalized notional NULL


def test_integration_okx_contract_multiplier_notional():
    req = assemble_exchange_feature_request(_ctx(exchange="okx"), _full_bundle(
        klines=[_ok_kline(i) for i in range(5)],
        oi=[_ok(_oi(0, 100.0)), _ok(_oi(4, 110.0))],
        funding=_ok(_fund(-1, 0.0002)),
        liqs=[_ok(_liq(1, 1, snap=False))],
        inst=_ok(_inst(quantity_unit="contracts", contract_multiplier=0.01)),
        cap=_ok(_cap(coverage_type="aggregated"))))
    v = compute_exchange_features(req)
    expected = sum((10.0 + i) * 0.01 * (101.0 + i) for i in range(5))
    assert v.volume_notional_usd == pytest.approx(expected)


def test_integration_quiet_available_vs_unavailable_liquidations():
    quiet = compute_exchange_features(assemble_exchange_feature_request(
        _ctx(), _full_bundle(liqs=[])))
    assert quiet.long_liquidation_notional == 0.0
    unavail = compute_exchange_features(assemble_exchange_feature_request(
        _ctx(liquidation_feed_available=False), _full_bundle(liqs=[])))
    assert unavail.long_liquidation_notional is None


def test_integration_deterministic_regardless_of_input_order():
    ctx = _ctx()
    a = compute_exchange_features(assemble_exchange_feature_request(ctx, _full_bundle()))
    shuffled = _full_bundle(klines=list(reversed(_five_bars(with_taker=True))),
                            oi=[_oi(4, 110.0), _oi(0, 100.0)])
    b = compute_exchange_features(assemble_exchange_feature_request(ctx, shuffled))
    assert a == b


# -- OKX identity helpers (rewrite exchange to okx on a row mapping) ---------
def _ok(row):
    return _m(**{**dict(row), "exchange": "okx"})


def _ok_kline(minute):
    return _ok(_kline(minute, open=100.0 + minute, high=110.0 + minute,
                      low=95.0 + minute, close=101.0 + minute, volume=10.0 + minute))


# ============================== load() wiring ===============================
def test_load_calls_reader_once_with_bucket_bounds():
    class Reader:
        def __init__(self): self.calls = []

        async def fetch_exchange_feature_raw_bundle(self, **kw):
            self.calls.append(kw)
            return _full_bundle()
    r = Reader()
    req = _run(load_exchange_feature_request(
        r, CFG, exchange=EX, symbol=SYM, market_type=MT, timeframe="5m",
        bucket_ts=B, code_version="code-v1", liquidation_feed_available=True))
    assert len(r.calls) == 1
    assert r.calls[0]["bucket_start"] == B
    assert r.calls[0]["bucket_end"] == B + timedelta(minutes=5)
    assert isinstance(req.calculation_version, str)


# ============================================================================
# K. Fail-loud amendment (PR #12): non-finite/overflow numerics, liquidation id,
#    capability drift, resolved symbol enablement.
# ============================================================================
_HUGE_INT = 10 ** 400   # not representable as a float


# --- 1. non-finite / overflowing numeric values -----------------------------
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), _HUGE_INT])
@pytest.mark.parametrize("field", ["open", "high", "low", "close", "volume"])
def test_kline_non_finite_or_overflow_rejected(field, bad):
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(klines=[_kline(0, **{field: bad})]))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), _HUGE_INT])
def test_kline_taker_non_finite_rejected(bad):
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(klines=[_kline(0, taker_buy_volume=bad)]))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), _HUGE_INT])
def test_oi_raw_non_finite_or_overflow_rejected(bad):
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(oi=[_oi(0, oi_raw=bad)]))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), _HUGE_INT])
def test_funding_rate_non_finite_or_overflow_rejected(bad):
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(funding=_fund(-1, funding_rate=bad)))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), _HUGE_INT, -0.01])
def test_liquidation_notional_non_finite_overflow_or_negative_rejected(bad):
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(liqs=[_liq(1, 1, notional=bad)]))


def test_liquidation_notional_measured_zero_still_valid():
    req = assemble_exchange_feature_request(
        _ctx(), _bundle(klines=[_kline(0)], liqs=[_liq(1, 1, notional=0.0)]))
    assert req.liquidations[0].notional == 0.0


@pytest.mark.parametrize("field", ["contract_multiplier", "tick_size"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), _HUGE_INT, 0.0, -1.0])
def test_instrument_multiplier_tick_non_finite_or_nonpositive_rejected(field, bad):
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(inst=_inst(**{field: bad})))


def test_instrument_missing_multiplier_still_allowed_and_degrades_fail_closed():
    # a NaN multiplier must NOT be able to masquerade as "missing metadata" and
    # silently null the notional — it must be rejected; None stays valid.
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(
            klines=_five_bars(), inst=_inst(quantity_unit="contracts",
                                            contract_multiplier=float("nan"))))
    req = assemble_exchange_feature_request(_ctx(), _bundle(
        klines=_five_bars(), inst=_inst(quantity_unit="contracts", contract_multiplier=None)))
    v = compute_exchange_features(req)
    assert v.volume_raw is not None and v.volume_notional_usd is None   # fail-closed, no default


@pytest.mark.parametrize("bad", [_HUGE_INT, float("nan"), float("inf"), float("-inf"),
                                 True, "0.95", 0, -0.1, 1.0001, 2])
def test_allowed_missing_bars_rejects_bad_without_overflow(bad):
    with pytest.raises(FeatureInputError):
        _allowed_missing_bars("1h", bad)


# --- 2. liquidation event id ------------------------------------------------
@pytest.mark.parametrize("bad_id", [True, False, 0, -1, -5, 1.0, "1", None])
def test_liquidation_id_malformed_rejected(bad_id):
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(liqs=[_liq(bad_id, 1)]))


def test_liquidation_mixed_ids_same_ts_raise_not_sort_typeerror():
    # two events at the same ts, one with a malformed id -> FeatureInputError,
    # never a TypeError leaking from sorting int vs str.
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(
            _ctx(), _bundle(liqs=[_liq(1, 1), _liq("x", 1)]))


def test_liquidation_same_ts_valid_distinct_ids_preserved_and_ordered():
    req = assemble_exchange_feature_request(_ctx(), _bundle(
        klines=[_kline(0)], liqs=[_liq(3, 1), _liq(1, 1), _liq(2, 1)]))
    assert len(req.liquidations) == 3           # all preserved, none dropped


@pytest.mark.parametrize("bad_side", ["up", "LONG", "", "buy", 1, None])
def test_liquidation_side_not_in_allow_list_rejected(bad_side):
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(liqs=[_liq(1, 1, side=bad_side)]))


# --- 3. liquidation capability drift ----------------------------------------
@pytest.mark.parametrize("cov", ["snapshot", "full", "aggregated"])
def test_capability_accepts_only_live_coverage_types(cov):
    snap = cov == "snapshot"
    req = assemble_exchange_feature_request(_ctx(), _bundle(
        klines=[_kline(0)], liqs=[_liq(1, 1, snap=snap)], cap=_cap(coverage_type=cov)))
    assert req.liquidation_feed_state.coverage_type == cov


@pytest.mark.parametrize("drift", [
    {"live_supported": False},
    {"historical_supported": True},
    {"expected_freshness_s": 30},
    {"expected_freshness_s": 0},
    {"coverage_type": "unavailable"},
    {"enabled": False},
    {"live_supported": "yes"},
    {"historical_supported": 1},
    {"enabled": 1},
])
def test_capability_drift_rejected(drift):
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(cap=_cap(**drift)))


def test_capability_feed_available_true_without_live_support_rejected():
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(
            _ctx(liquidation_feed_available=True),
            _bundle(cap=_cap(live_supported=False)))


def test_capability_identity_and_snapshot_flag_still_checked():
    # identity drift still fails, and event snapshot flag must match coverage type
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(cap=_cap(exchange="okx")))
    with pytest.raises(FeatureInputError):
        assemble_exchange_feature_request(_ctx(), _bundle(
            liqs=[_liq(1, 1, snap=False)], cap=_cap(coverage_type="snapshot")))


# --- 4. resolved symbol enablement ------------------------------------------
def _disabled_symbol_cfg():
    raw = copy.deepcopy(CFG._raw)
    raw["symbols"]["BTCUSDT"]["enabled"] = False
    cfg = Stage2Config(raw)
    cfg._validate()
    return cfg


def test_resolved_symbol_disabled_rejects_build_context():
    cfg = _disabled_symbol_cfg()
    with pytest.raises(FeatureInputError):
        build_assembly_context(cfg, exchange=EX, symbol=SYM, market_type=MT,
                               timeframe="5m", bucket_ts=B, code_version="v",
                               liquidation_feed_available=True)


def test_resolved_symbol_disabled_causes_zero_reader_calls():
    cfg = _disabled_symbol_cfg()

    class Reader:
        def __init__(self): self.calls = 0

        async def fetch_exchange_feature_raw_bundle(self, **kw):
            self.calls += 1
            return _bundle()
    r = Reader()
    with pytest.raises(FeatureInputError):
        _run(load_exchange_feature_request(
            r, cfg, exchange=EX, symbol=SYM, market_type=MT, timeframe="5m",
            bucket_ts=B, code_version="v", liquidation_feed_available=True))
    assert r.calls == 0


def test_master_switch_still_not_required():
    # stage2.enabled stays false; a per-symbol-enabled config still builds fine.
    assert CFG.enabled is False
    assert _ctx().calculation_version
