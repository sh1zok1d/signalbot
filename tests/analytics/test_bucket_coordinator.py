"""Unit + integration tests for analytics/feature_engine/bucket_coordinator.py.

Uses the real Stage2Config, real immutable models, and the real exchange /
consensus pipelines with fake readers/writers (no DB, network, clock). The
feature/consensus algorithms are NOT re-implemented, and no helper is imported
from other test modules.
"""
from __future__ import annotations

import ast
import asyncio
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from common.stage2_config import Stage2Config
from storage.stage2_readers import ExchangeFeatureRawBundle
from analytics.feature_engine.models import ExchangeFeatureVector
from analytics.feature_engine.consensus_models import FAMILIES
from analytics.feature_engine.consensus import ConsensusError
from analytics.feature_engine.consensus_input_adapter import ConsensusInputError
from analytics.feature_engine.bucket_coordinator import (
    BAR_DATA_UNUSABLE, BucketCoordinatorError, EXCHANGE_PROCESSING_FAILED,
    ExchangeBucketFailure, LIQUIDATION_UNAVAILABLE, METRIC_UNAVAILABLE,
    Stage2BucketResult, process_stage2_bucket, _derive_family_exclusions,
)

CFG = Stage2Config.load()
SYM, MT = "BTCUSDT", "perp"
B = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)          # 5m/1h/4h aligned
EXS = ("binance", "bybit", "okx")
# structural liquidation feed quality per exchange (symbols.registry authority)
COV = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}


def _run(coro):
    return asyncio.run(coro)


def _m(**kw):
    return MappingProxyType(dict(kw))


# ---- per-exchange raw-bundle builders (valid, fully-contributing) ----------
def _kline(ex, minute):
    return _m(exchange=ex, symbol=SYM, ts=B + timedelta(minutes=minute),
              open=100.0 + minute, high=110.0 + minute, low=95.0 + minute,
              close=101.0 + minute, volume=10.0 + minute,
              taker_buy_volume=1.0 + minute, taker_sell_volume=0.5 + minute)


def _oi(ex, minute, v):
    return _m(exchange=ex, symbol=SYM, ts=B + timedelta(minutes=minute),
              oi_raw=v, oi_unit="base")


def _fund(ex):
    return _m(exchange=ex, symbol=SYM, ts=B - timedelta(minutes=1), funding_rate=0.0001)


def _liq(ex, id_, minute, side="long"):
    return _m(id=id_, exchange=ex, symbol=SYM, ts=B + timedelta(minutes=minute),
              side=side, notional=100.0, is_snapshot_feed=(COV[ex] == "snapshot"))


def _inst(ex):
    return _m(exchange=ex, symbol=SYM, market_type=MT, exchange_instrument_id="BTCUSDT",
              quantity_unit="base", contract_multiplier=None, tick_size=0.1,
              price_precision=None, quantity_precision=None,
              metadata_source="exchange_api", fetched_at=B, is_stale=False, note=None)


def _cap(ex):
    return _m(exchange=ex, symbol=SYM, market_type=MT, metric="liquidations",
              live_supported=True, historical_supported=False,
              coverage_type=COV[ex], expected_freshness_s=None, enabled=True)


def _bundle(ex, n_klines=5):
    return ExchangeFeatureRawBundle(
        klines=tuple(_kline(ex, i) for i in range(n_klines)),
        open_interest=(_oi(ex, 0, 100.0), _oi(ex, 4, 110.0)),
        latest_funding=_fund(ex),
        liquidations=(_liq(ex, 1, 1), _liq(ex, 2, 2, "short")),
        instrument=_inst(ex), liquidation_capability=_cap(ex))


# ---- fakes -----------------------------------------------------------------
class Reader:
    """Per-exchange bundle dispatcher; may fail or shorten specific exchanges."""
    def __init__(self, fail=(), short=(), events=None):
        self.fail = set(fail)
        self.short = set(short)
        self.calls = []
        self.events = events

    async def fetch_exchange_feature_raw_bundle(self, *, exchange, **kw):
        self.calls.append(exchange)
        if self.events is not None:
            self.events.append(("read", exchange))
        if exchange in self.fail:
            raise ValueError(f"reader boom {exchange}")
        return _bundle(exchange, 4 if exchange in self.short else 5)


class ExWriter:
    def __init__(self, exc=None, events=None):
        self.calls = []
        self.exc = exc
        self.events = events

    async def upsert_exchange_feature_vectors(self, rows):
        self.calls.append(rows)
        if self.events is not None:
            self.events.append(("ex_write", rows[0].exchange))
        if self.exc is not None:
            raise self.exc
        return len(rows)


class CoWriter:
    def __init__(self, exc=None, events=None):
        self.calls = []
        self.exc = exc
        self.events = events

    async def upsert_consensus_feature_vectors(self, rows):
        self.calls.append(rows)
        if self.events is not None:
            self.events.append(("co_write",))
        if self.exc is not None:
            raise self.exc
        return len(rows)


def _avail(exchanges=EXS, **over):
    d = {e: True for e in exchanges}
    d.update(over)
    return d


def _process(reader, ew, cw, **over):
    kw = dict(exchanges=list(EXS), symbol=SYM, market_type=MT, timeframe="5m",
              bucket_ts=B, code_version="code-v1",
              liquidation_feed_available_by_exchange=_avail())
    kw.update(over)
    return _run(process_stage2_bucket(reader, ew, cw, CFG, **kw))


def _disabled_cfg():
    raw = copy.deepcopy(CFG._raw)
    raw["symbols"]["BTCUSDT"]["enabled"] = False
    cfg = Stage2Config(raw)
    cfg._validate()
    return cfg


def _efv(ex="binance", **over):
    base = dict(
        exchange=ex, symbol=SYM, market_type=MT, timeframe="5m", bucket_ts=B,
        feature_schema_version=1, calculation_version="0" * 16,
        price_move_pct=1.0, range_width_pct=5.0, close_price=100.0,
        volume_raw=10.0, volume_raw_unit="base", volume_notional_usd=1000.0,
        taker_buy_notional_usd=6.0, taker_sell_notional_usd=4.0,
        taker_delta_notional_usd=2.0, cvd_delta_notional_usd=2.0,
        oi_change_pct=2.0, oi_unit="base", funding_rate=0.0001,
        long_liquidation_notional=0.0, short_liquidation_notional=0.0,
        liquidation_event_count=0, liquidation_feed_quality=COV[ex],
        is_snapshot_feed=(ex == "binance"),
        bars_expected=5, bars_present=5, has_gap=False, is_usable=True,
        config_hash="a" * 64, config_version="2.1.0", code_version="t")
    base.update(over)
    return ExchangeFeatureVector(**base)


# ============================================================================
# 14. shared-input validation (fails with BucketCoordinatorError before any I/O)
# ============================================================================
def test_not_a_stage2_config_rejected_no_io():
    r, ew, cw = Reader(), ExWriter(), CoWriter()
    with pytest.raises(BucketCoordinatorError):
        _run(process_stage2_bucket(
            r, ew, cw, object(), exchanges=list(EXS), symbol=SYM, market_type=MT,
            timeframe="5m", bucket_ts=B, code_version="code-v1",
            liquidation_feed_available_by_exchange=_avail()))
    assert r.calls == [] and ew.calls == [] and cw.calls == []


_BAD_EXCHANGE_CONTAINERS = [
    None, True, False, 0, 3.5, "", "binance", b"x", bytearray(b"x"),
    {"binance": 1}, {"binance"}, frozenset({"binance"}),
    (e for e in EXS), iter(EXS), object(), [], (),
]


@pytest.mark.parametrize("bad", _BAD_EXCHANGE_CONTAINERS, ids=lambda b: type(b).__name__)
def test_bad_exchanges_container_rejected_no_io(bad):
    r, ew, cw = Reader(), ExWriter(), CoWriter()
    with pytest.raises(BucketCoordinatorError):
        _run(process_stage2_bucket(
            r, ew, cw, CFG, exchanges=bad, symbol=SYM, market_type=MT,
            timeframe="5m", bucket_ts=B, code_version="code-v1",
            liquidation_feed_available_by_exchange=_avail()))
    assert r.calls == [] and ew.calls == [] and cw.calls == []


def test_duplicate_exchange_rejected_no_io():
    r, ew, cw = Reader(), ExWriter(), CoWriter()
    with pytest.raises(BucketCoordinatorError):
        _process(r, ew, cw, exchanges=["binance", "binance"],
                 liquidation_feed_available_by_exchange={"binance": True})
    assert r.calls == [] and ew.calls == [] and cw.calls == []


def test_unknown_exchange_rejected_no_io():
    r, ew, cw = Reader(), ExWriter(), CoWriter()
    with pytest.raises(BucketCoordinatorError):
        _process(r, ew, cw, exchanges=["bitget"],
                 liquidation_feed_available_by_exchange={"bitget": True})
    assert r.calls == [] and ew.calls == [] and cw.calls == []


def test_non_string_exchange_rejected_no_io():
    r, ew, cw = Reader(), ExWriter(), CoWriter()
    with pytest.raises(BucketCoordinatorError):
        _process(r, ew, cw, exchanges=[5],
                 liquidation_feed_available_by_exchange={5: True})
    assert r.calls == [] and ew.calls == []


def test_availability_not_a_mapping_rejected_no_io():
    r, ew, cw = Reader(), ExWriter(), CoWriter()
    with pytest.raises(BucketCoordinatorError):
        _process(r, ew, cw, liquidation_feed_available_by_exchange=[True, True, True])
    assert r.calls == []


def test_availability_missing_key_rejected_no_io():
    r, ew, cw = Reader(), ExWriter(), CoWriter()
    with pytest.raises(BucketCoordinatorError):
        _process(r, ew, cw, liquidation_feed_available_by_exchange={"binance": True, "bybit": True})
    assert r.calls == []


def test_availability_extra_key_rejected_no_io():
    r, ew, cw = Reader(), ExWriter(), CoWriter()
    with pytest.raises(BucketCoordinatorError):
        _process(r, ew, cw, liquidation_feed_available_by_exchange=_avail(kraken=True))
    assert r.calls == []


@pytest.mark.parametrize("bad", [1, 0, "yes", None, 1.0])
def test_availability_non_bool_value_rejected_no_io(bad):
    r, ew, cw = Reader(), ExWriter(), CoWriter()
    av = _avail(); av["bybit"] = bad
    with pytest.raises(BucketCoordinatorError):
        _process(r, ew, cw, liquidation_feed_available_by_exchange=av)
    assert r.calls == []


@pytest.mark.parametrize("over", [
    {"symbol": "ETHUSDT"},
    {"market_type": "spot"},
    {"timeframe": "3m"},
    {"bucket_ts": B + timedelta(minutes=3)},                 # off the 5m grid
    {"bucket_ts": datetime(2026, 3, 1)},                     # naive
    {"bucket_ts": datetime(2026, 3, 1, tzinfo=timezone(timedelta(hours=1)))},  # non-UTC
    {"code_version": "   "},
])
def test_shared_context_failures_wrapped_no_io(over):
    r, ew, cw = Reader(), ExWriter(), CoWriter()
    with pytest.raises(BucketCoordinatorError):
        _process(r, ew, cw, **over)
    assert r.calls == [] and ew.calls == [] and cw.calls == []


def test_shared_context_failure_preserves_cause():
    r, ew, cw = Reader(), ExWriter(), CoWriter()
    with pytest.raises(BucketCoordinatorError) as ei:
        _process(r, ew, cw, timeframe="3m")
    assert ei.value.__cause__ is not None                    # original error preserved


def test_resolved_disabled_symbol_rejected_no_io():
    r, ew, cw = Reader(), ExWriter(), CoWriter()
    with pytest.raises(BucketCoordinatorError):
        _run(process_stage2_bucket(
            r, ew, cw, _disabled_cfg(), exchanges=list(EXS), symbol=SYM,
            market_type=MT, timeframe="5m", bucket_ts=B, code_version="code-v1",
            liquidation_feed_available_by_exchange=_avail()))
    assert r.calls == [] and ew.calls == [] and cw.calls == []


def test_stage2_disabled_still_allows_explicit_call():
    assert CFG.enabled is False
    res = _process(Reader(), ExWriter(), CoWriter())
    assert isinstance(res, Stage2BucketResult)
    assert res.consensus_feature is not None


# ============================================================================
# 15. happy path (3/3) + call order + integration
# ============================================================================
def test_three_of_three_success_order_and_shapes():
    events = []
    r = Reader(events=events)
    ew = ExWriter(events=events)
    cw = CoWriter(events=events)
    res = _process(r, ew, cw)
    # sequential reads in requested order
    assert r.calls == list(EXS)
    # one exchange write per exchange, then exactly one consensus write, in order
    assert events == [("read", "binance"), ("ex_write", "binance"),
                      ("read", "bybit"), ("ex_write", "bybit"),
                      ("read", "okx"), ("ex_write", "okx"), ("co_write",)]
    assert [v.exchange for v in res.exchange_features] == list(EXS)
    assert all(isinstance(c, tuple) and len(c) == 1 for c in ew.calls)
    assert len(cw.calls) == 1 and len(cw.calls[0]) == 1
    assert res.failures == ()
    assert all(len(res.exclusion_reasons_by_family[f]) == 0 for f in FAMILIES)
    for f in FAMILIES:
        assert tuple(res.expected_exchanges_by_family[f]) == EXS
    assert res.consensus_feature.is_partial_consensus is False
    # returned consensus is the exact object handed to the consensus writer
    assert res.consensus_feature is cw.calls[0][0]


def test_liquidation_availability_forwarded_per_exchange():
    # a False availability for one venue is honored: with zero liq rows it would
    # NULL liquidation metrics; here rows exist so False + events must error INSIDE
    # that exchange pipeline -> isolated failure (not a coordinator error).
    r = Reader()
    ew, cw = ExWriter(), CoWriter()
    res = _process(r, ew, cw, liquidation_feed_available_by_exchange=_avail(bybit=False))
    # bybit's bundle has liquidation rows but availability False -> pipeline raises,
    # isolated as a per-exchange failure.
    assert any(fl.exchange == "bybit" for fl in res.failures)
    assert [v.exchange for v in res.exchange_features] == ["binance", "okx"]


# ============================================================================
# 16. failure isolation (2/3, 1/3, 0/3) + exception boundaries
# ============================================================================
def test_two_of_three_isolates_one_failure_and_writes_partial():
    r = Reader(fail={"bybit"})
    ew, cw = ExWriter(), CoWriter()
    res = _process(r, ew, cw)
    assert [v.exchange for v in res.exchange_features] == ["binance", "okx"]
    assert res.failures == (ExchangeBucketFailure("bybit", EXCHANGE_PROCESSING_FAILED, "ValueError"),)
    for f in FAMILIES:
        assert res.exclusion_reasons_by_family[f]["bybit"] == EXCHANGE_PROCESSING_FAILED
        assert tuple(res.expected_exchanges_by_family[f]) == EXS          # denominator intact
    assert res.consensus_feature.is_partial_consensus is True
    assert len(cw.calls) == 1


def test_one_of_three_still_runs_consensus():
    r = Reader(fail={"bybit", "okx"})
    ew, cw = ExWriter(), CoWriter()
    res = _process(r, ew, cw)
    assert [v.exchange for v in res.exchange_features] == ["binance"]
    assert {fl.exchange for fl in res.failures} == {"bybit", "okx"}
    for f in FAMILIES:
        assert tuple(res.expected_exchanges_by_family[f]) == EXS
    assert res.consensus_feature is not None                              # coverage-insufficient is core's concern
    assert len(cw.calls) == 1


def test_zero_of_three_skips_consensus():
    r = Reader(fail=set(EXS))
    ew, cw = ExWriter(), CoWriter()
    res = _process(r, ew, cw)
    assert res.exchange_features == ()
    assert [fl.exchange for fl in res.failures] == list(EXS)              # requested order
    for f in FAMILIES:
        for e in EXS:
            assert res.exclusion_reasons_by_family[f][e] == EXCHANGE_PROCESSING_FAILED
    assert res.consensus_feature is None
    assert cw.calls == []                                                 # consensus writer untouched


def test_exchange_failure_records_exact_exception_class_name():
    class Boomy(Reader):
        async def fetch_exchange_feature_raw_bundle(self, *, exchange, **kw):
            self.calls.append(exchange)
            raise KeyError("k")
    r = Boomy()
    res = _process(r, ExWriter(), CoWriter())
    assert res.failures[0].error_type == "KeyError"
    assert res.failures[0].reason == EXCHANGE_PROCESSING_FAILED


def test_consensus_writer_exception_propagates_unchanged():
    exc = RuntimeError("consensus writer boom")
    cw = CoWriter(exc=exc)
    with pytest.raises(RuntimeError) as got:
        _process(Reader(), ExWriter(), cw)
    assert got.value is exc


def test_consensus_core_exception_propagates_unchanged(monkeypatch):
    # force the consensus core to raise; it must NOT be converted to a result
    import analytics.feature_engine.consensus_pipeline as cp
    def boom(_req):
        raise ConsensusError("core boom")
    monkeypatch.setattr(cp, "compute_consensus_features", boom)
    cw = CoWriter()
    with pytest.raises(ConsensusError):
        _process(Reader(), ExWriter(), cw)
    assert cw.calls == []                                                 # writer not reached


def test_keyboardinterrupt_from_exchange_not_swallowed():
    class KI(Reader):
        async def fetch_exchange_feature_raw_bundle(self, *, exchange, **kw):
            self.calls.append(exchange)
            raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        _process(KI(), ExWriter(), CoWriter())


def test_systemexit_from_exchange_not_swallowed():
    class SE(Reader):
        async def fetch_exchange_feature_raw_bundle(self, *, exchange, **kw):
            self.calls.append(exchange)
            raise SystemExit(1)
    with pytest.raises(SystemExit):
        _process(SE(), ExWriter(), CoWriter())


def test_cancellation_not_swallowed():
    # asyncio.CancelledError is BaseException in current Python -> must propagate
    class CX(Reader):
        async def fetch_exchange_feature_raw_bundle(self, *, exchange, **kw):
            self.calls.append(exchange)
            raise asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        _process(CX(), ExWriter(), CoWriter())


# ============================================================================
# 17. per-family exclusion derivation
# ============================================================================
def test_exclusion_is_usable_false_only_bar_families():
    excl = _derive_family_exclusions(_efv(is_usable=False))
    assert excl == {"price_structure": BAR_DATA_UNUSABLE,
                    "volume": BAR_DATA_UNUSABLE,
                    "taker_flow": BAR_DATA_UNUSABLE}
    # oi/funding/liquidations NOT excluded (their values exist)
    assert "oi" not in excl and "funding" not in excl and "liquidations" not in excl


@pytest.mark.parametrize("field", ["price_move_pct", "range_width_pct", "close_price"])
def test_exclusion_missing_price_field_price_structure_only(field):
    assert _derive_family_exclusions(_efv(**{field: None})) == {"price_structure": METRIC_UNAVAILABLE}


def test_exclusion_volume_missing_only_volume():
    assert _derive_family_exclusions(_efv(volume_notional_usd=None)) == {"volume": METRIC_UNAVAILABLE}


@pytest.mark.parametrize("field", ["taker_buy_notional_usd", "taker_sell_notional_usd",
                                   "taker_delta_notional_usd", "cvd_delta_notional_usd"])
def test_exclusion_missing_taker_field_taker_only(field):
    assert _derive_family_exclusions(_efv(**{field: None})) == {"taker_flow": METRIC_UNAVAILABLE}


def test_exclusion_oi_missing_only_oi():
    assert _derive_family_exclusions(_efv(oi_change_pct=None)) == {"oi": METRIC_UNAVAILABLE}


def test_exclusion_funding_missing_only_funding():
    assert _derive_family_exclusions(_efv(funding_rate=None)) == {"funding": METRIC_UNAVAILABLE}


@pytest.mark.parametrize("field", ["long_liquidation_notional", "short_liquidation_notional",
                                   "liquidation_event_count"])
def test_exclusion_missing_liquidation_field(field):
    assert _derive_family_exclusions(_efv(**{field: None})) == {"liquidations": LIQUIDATION_UNAVAILABLE}


def test_exclusion_zero_liquidation_values_not_excluded():
    assert _derive_family_exclusions(
        _efv(long_liquidation_notional=0.0, short_liquidation_notional=0.0,
             liquidation_event_count=0)) == {}


def test_exclusion_precedence_is_usable_beats_missing_bar_field():
    # is_usable False AND a missing price field -> BAR_DATA_UNUSABLE wins
    excl = _derive_family_exclusions(_efv(is_usable=False, price_move_pct=None))
    assert excl["price_structure"] == BAR_DATA_UNUSABLE


def test_derived_exclusions_produce_core_accepted_request():
    # one venue is_usable=False (short klines) -> excluded from bar families but
    # still contributes oi/funding/liquidations; the real consensus core must
    # accept the coordinator-built request.
    r = Reader(short={"bybit"})
    ew, cw = ExWriter(), CoWriter()
    res = _process(r, ew, cw)
    assert res.failures == ()
    for fam in ("price_structure", "volume", "taker_flow"):
        assert res.exclusion_reasons_by_family[fam]["bybit"] == BAR_DATA_UNUSABLE
    for fam in ("oi", "funding", "liquidations"):
        assert "bybit" not in res.exclusion_reasons_by_family[fam]
    assert res.consensus_feature is not None and len(cw.calls) == 1


# ============================================================================
# 18. immutability & determinism
# ============================================================================
def test_result_containers_are_immutable_and_detached():
    exchanges = list(EXS)
    av = _avail()
    res = _process(Reader(), ExWriter(), CoWriter(), exchanges=exchanges,
                   liquidation_feed_available_by_exchange=av)
    assert isinstance(res.exchange_features, tuple)
    assert isinstance(res.failures, tuple)
    with pytest.raises(TypeError):
        res.expected_exchanges_by_family["oi"] = ()
    with pytest.raises(TypeError):
        res.exclusion_reasons_by_family["oi"]["x"] = "y"
    # mutating the caller's containers after the call does not change the result
    exchanges.append("kraken")
    av["binance"] = False
    assert tuple(res.expected_exchanges_by_family["oi"]) == EXS


def test_input_efv_and_config_not_mutated():
    before_cfg = copy.deepcopy(CFG._raw)
    res = _process(Reader(), ExWriter(), CoWriter())
    assert CFG._raw == before_cfg
    # returned EFVs are the pipeline outputs, unmutated frozen dataclasses
    assert all(isinstance(v, ExchangeFeatureVector) for v in res.exchange_features)


def test_repeated_identical_calls_equal_results():
    a = _process(Reader(), ExWriter(), CoWriter())
    b = _process(Reader(), ExWriter(), CoWriter())
    assert a == b


def test_requested_order_preserved_for_vectors_and_failures():
    r = Reader(fail={"binance"})
    res = _process(r, ExWriter(), CoWriter())
    assert r.calls == list(EXS)                                           # attempts in order
    assert [v.exchange for v in res.exchange_features] == ["bybit", "okx"]
    assert [fl.exchange for fl in res.failures] == ["binance"]


# ============================================================================
# 19. architecture
# ============================================================================
def test_architecture_no_forbidden_imports_or_behavior():
    # AST-based (not substring) so the docstring may NAME what the module avoids.
    src = Path("analytics/feature_engine/bucket_coordinator.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    used_attrs = set()
    used_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Attribute):
            used_attrs.add(node.attr)
        elif isinstance(node, ast.Name):
            used_names.add(node.id)
        # no unbounded loops (only the finite requested-exchange / FAMILIES for-loops)
        assert not isinstance(node, (ast.While, ast.AsyncFor))
    forbidden_modules = {
        "storage", "asyncpg", "redis", "aiohttp", "requests", "subprocess",
        "os", "dotenv", "main", "data_ingestion", "backfill", "socket", "asyncio",
    }
    assert not (imported & forbidden_modules), imported & forbidden_modules
    # no clock / sleep / concurrency / env / schema-init calls actually used
    assert not (used_attrs & {"sleep", "gather", "create_task", "now", "utcnow",
                              "today", "environ", "getenv"}), used_attrs
    # no concrete Database / schema-init / forecast identifiers referenced
    assert not ({"Database", "init_schema", "init_stage2_schema"} & (used_names | used_attrs))
