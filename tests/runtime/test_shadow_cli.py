"""Unit tests for runtime/shadow_cli.py — the operational one-shot shadow CLI.

Fake Database (no real DB / Docker / network); the real process_shadow_cycle,
real feature/consensus/forecast pipelines, and real config objects flow through.
Covers: pure bucket selection / explicit parsing, config-scope validation, code
version, one-shot execution order, instrument-metadata bootstrap, dry-run zero
writes, read-only status, renderers, architecture, and "status is not recovery".
"""
from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from common.config import Config
from common.instrument_metadata import (
    FailClosedError, InstrumentMetadata, MetadataMismatchError, MetadataUnavailableError,
)
from common.stage2_config import Stage2Config, Stage2ConfigError
from common.symbol_mapper import to_exchange_symbol
from common.versioning import VersioningError
from storage.stage2_readers import ExchangeFeatureRawBundle
from analytics.forecasting.shadow_cycle import ShadowCycleResult

import runtime.shadow_cli as sc
from runtime.shadow_cli import (
    BUCKET_AUTO, BUCKET_EXPLICIT, SHADOW_DRY_RUN, SHADOW_ONCE,
    STATUS_EMPTY, STATUS_NOT_INITIALIZED, STATUS_PARTIAL_SCHEMA, STATUS_READY,
    ShadowCliError, ShadowExecutionReport, ShadowStatusReport,
    execute_shadow_dry_run, execute_shadow_once, execute_shadow_status,
    parse_shadow_bucket_ts, select_latest_closed_5m_bucket,
    _resolve_shadow_scope,
)

UTC = timezone.utc
B = datetime(2026, 3, 1, 0, 0, tzinfo=UTC)
SYM, MT = "BTCUSDT", "perp"
EXS = ("binance", "bybit", "okx")
COV = {"binance": "snapshot", "bybit": "full", "okx": "aggregated"}


def _run(coro):
    return asyncio.run(coro)


# ---- raw bundle fixtures (mirror the shadow-cycle integration fixtures) -----
def _m(**kw):
    return MappingProxyType(dict(kw))


def _kline(ex, minute, *, close=None):
    close = 101.0 + minute if close is None else close
    o = 100.0 + minute
    return _m(exchange=ex, symbol=SYM, ts=B + timedelta(minutes=minute), open=o,
              high=max(110.0 + minute, o, close), low=min(95.0 + minute, o, close),
              close=close, volume=10.0 + minute,
              taker_buy_volume=1.0 + minute, taker_sell_volume=0.5 + minute)


def _oi(ex, minute, v):
    return _m(exchange=ex, symbol=SYM, ts=B + timedelta(minutes=minute), oi_raw=v, oi_unit="base")


def _fund(ex):
    return _m(exchange=ex, symbol=SYM, ts=B - timedelta(minutes=1), funding_rate=0.0001)


def _liq(ex, id_, minute, side="long"):
    return _m(id=id_, exchange=ex, symbol=SYM, ts=B + timedelta(minutes=minute),
              side=side, notional=100.0, is_snapshot_feed=(COV[ex] == "snapshot"))


def _inst_row(ex, *, is_stale=False, tick=0.1):
    return _m(exchange=ex, symbol=SYM, market_type=MT, exchange_instrument_id="BTCUSDT",
              quantity_unit="base", contract_multiplier=None, tick_size=tick,
              price_precision=None, quantity_precision=None,
              metadata_source="exchange_api", fetched_at=B, is_stale=is_stale, note=None)


def _cap(ex):
    return _m(exchange=ex, symbol=SYM, market_type=MT, metric="liquidations",
              live_supported=True, historical_supported=False, coverage_type=COV[ex],
              expected_freshness_s=None, enabled=True)


def _bundle(ex, *, final_close=None):
    return ExchangeFeatureRawBundle(
        klines=tuple(_kline(ex, i, close=final_close if i == 4 else None) for i in range(5)),
        open_interest=(_oi(ex, 0, 100.0), _oi(ex, 4, 110.0)), latest_funding=_fund(ex),
        liquidations=(_liq(ex, 1, 1), _liq(ex, 2, 2, "short")),
        instrument=_inst_row(ex), liquidation_capability=_cap(ex))


def _prereq(ex, *, instrument=True, stale=False, capability=True):
    return MappingProxyType({
        "exchange": ex, "instrument_present": instrument, "instrument_is_stale": stale,
        "liquidation_capability_present": capability, "liquidation_live_supported": True,
        "liquidation_enabled": True, "liquidation_coverage_type": COV[ex]})


def _status_snapshot(state, *, exchanges=EXS, prereq_overrides=None, latest=None, outcomes=()):
    overrides = prereq_overrides or {}
    prereqs = tuple(overrides.get(ex, _prereq(ex)) for ex in exchanges)
    if state in (STATUS_NOT_INITIALIZED, STATUS_PARTIAL_SCHEMA):
        prereqs = ()
    return MappingProxyType({
        "state": state, "prerequisites": prereqs,
        "latest_prediction": latest, "outcomes": tuple(outcomes)})


# ---- fake Database ---------------------------------------------------------
class FakeDB:
    def __init__(self, *, bundles=None, instruments=None, status=None,
                 availability=None, fetch_json_calls=None):
        self.bundles = bundles if bundles is not None else {ex: _bundle(ex) for ex in EXS}
        self.instruments = instruments if instruments is not None else {}
        self.status = status
        self.availability = availability
        self.calls: list = []
        self.seeded_symbols = None
        self.seeded_caps = None
        self.upserted_instruments: list = []

    async def connect(self):
        self.calls.append("connect")

    async def close(self):
        self.calls.append("close")

    async def init_schema(self):                       # must NEVER be called
        self.calls.append("init_schema")

    async def init_stage2_schema(self):
        self.calls.append("init_stage2_schema")

    async def seed_symbols(self, rows):
        self.calls.append("seed_symbols")
        self.seeded_symbols = tuple(rows)
        return len(rows)

    async def seed_symbol_exchange_capabilities(self, rows):
        self.calls.append("seed_caps")
        self.seeded_caps = tuple(rows)
        return len(rows)

    async def get_exchange_instrument(self, exchange, symbol, market_type="perp"):
        self.calls.append(("get_instr", exchange))
        return self.instruments.get(exchange)

    async def upsert_exchange_instrument(self, **kw):
        self.calls.append(("upsert_instr", kw["exchange"]))
        self.upserted_instruments.append(kw)
        return "OK"

    async def fetch_shadow_liquidation_availability(self, *, exchanges, symbol, market_type):
        self.calls.append("avail")
        if self.availability is not None:
            return self.availability
        return MappingProxyType({ex: True for ex in exchanges})

    async def fetch_shadow_status(self, *, exchanges, symbol, market_type, timeframe):
        self.calls.append("status")
        return self.status

    async def fetch_exchange_feature_raw_bundle(self, *, exchange, symbol, market_type,
                                                bucket_start, bucket_end):
        self.calls.append(("raw", exchange))
        return self.bundles[exchange]

    async def upsert_exchange_feature_vectors(self, rows):
        self.calls.append("efv")
        return len(rows)

    async def upsert_consensus_feature_vectors(self, rows):
        self.calls.append("consensus")
        return len(rows)

    async def insert_forecast_prediction(self, row):
        self.calls.append("insert_pred")
        return True

    async def upsert_forecast_outcomes(self, rows):
        self.calls.append("outcome")
        return len(rows)


def _configs():
    return Config.load(), Stage2Config.load()


# ---- injected instrument-metadata JSON fetcher -----------------------------
def _fetch_json_factory(*, tick="0.1", okx_ctval="0.01", fail=(), counter=None):
    okx_id = to_exchange_symbol("okx", SYM, MT)

    async def fetch_json(url, params):
        if counter is not None:
            counter.append((url, params))
        if "binance" in url:
            if "binance" in fail:
                raise RuntimeError("net binance")
            return {"symbols": [{"symbol": SYM,
                                 "filters": [{"filterType": "PRICE_FILTER", "tickSize": tick}],
                                 "pricePrecision": 2, "quantityPrecision": 3}]}
        if "bybit" in url:
            if "bybit" in fail:
                raise RuntimeError("net bybit")
            return {"result": {"list": [{"symbol": SYM, "priceFilter": {"tickSize": tick},
                                         "lotSizeFilter": {"qtyStep": "1"}}]}}
        if "okx" in url:
            if "okx" in fail:
                raise RuntimeError("net okx")
            row = {"instId": okx_id, "tickSz": tick}
            if okx_ctval is not None:
                row["ctVal"] = okx_ctval
            return {"data": [row]}
        raise AssertionError(f"unexpected url {url}")

    return fetch_json


# ============================================================================
# 1. bucket selector
# ============================================================================
@pytest.mark.parametrize("h,m,s,expect", [
    (12, 10, 4, "12:00"), (12, 10, 5, "12:05"),
    (12, 14, 59, "12:05"), (12, 15, 5, "12:10"),
])
def test_bucket_selector_boundaries(h, m, s, expect):
    now = datetime(2026, 7, 24, h, m, s, tzinfo=UTC)
    bucket = select_latest_closed_5m_bucket(now, soft_grace_s=5)
    assert bucket.strftime("%H:%M") == expect
    assert bucket.tzinfo == UTC and bucket.second == 0 and bucket.minute % 5 == 0


def test_bucket_selector_rejects_naive_and_nonutc():
    with pytest.raises(ShadowCliError):
        select_latest_closed_5m_bucket(datetime(2026, 7, 24, 12, 0), soft_grace_s=5)
    with pytest.raises(ShadowCliError):
        select_latest_closed_5m_bucket(
            datetime(2026, 7, 24, 12, 0, tzinfo=timezone(timedelta(hours=2))), soft_grace_s=5)


@pytest.mark.parametrize("grace", [True, 5.0, "5", -1])
def test_bucket_selector_rejects_bad_grace(grace):
    with pytest.raises(ShadowCliError):
        select_latest_closed_5m_bucket(datetime(2026, 7, 24, 12, 0, tzinfo=UTC), soft_grace_s=grace)


def test_bucket_selector_deterministic_no_mutation():
    now = datetime(2026, 7, 24, 12, 10, 5, tzinfo=UTC)
    a = select_latest_closed_5m_bucket(now, soft_grace_s=5)
    b = select_latest_closed_5m_bucket(now, soft_grace_s=5)
    assert a == b
    assert now == datetime(2026, 7, 24, 12, 10, 5, tzinfo=UTC)


# ============================================================================
# 2. explicit parser
# ============================================================================
def test_parse_explicit_accepts_z_and_offset():
    now = datetime(2026, 7, 24, 6, 0, tzinfo=UTC)
    a = parse_shadow_bucket_ts("2026-07-24T05:00:00Z", now=now)
    b = parse_shadow_bucket_ts("2026-07-24T05:00:00+00:00", now=now)
    assert a == b == datetime(2026, 7, 24, 5, 0, tzinfo=UTC)


@pytest.mark.parametrize("value", [
    "", "   ", "not-a-date", "2026-07-24T05:00:00",          # blank/malformed/naive
    "2026-07-24T05:00:00+02:00",                              # non-UTC
    "2026-07-24T05:00:30Z",                                   # seconds
    "2026-07-24T05:02:00Z",                                   # non-5m
])
def test_parse_explicit_rejects(value):
    now = datetime(2026, 7, 24, 6, 0, tzinfo=UTC)
    with pytest.raises(ShadowCliError):
        parse_shadow_bucket_ts(value, now=now)


def test_parse_explicit_rejects_future_unclosed():
    now = datetime(2026, 7, 24, 5, 3, tzinfo=UTC)   # bucket 05:00 ends 05:05 > now
    with pytest.raises(ShadowCliError):
        parse_shadow_bucket_ts("2026-07-24T05:00:00Z", now=now)


def test_parse_explicit_accepts_historical_closed():
    now = datetime(2026, 7, 24, 6, 0, tzinfo=UTC)
    assert parse_shadow_bucket_ts("2026-07-01T00:00:00Z", now=now) == datetime(2026, 7, 1, tzinfo=UTC)


# ============================================================================
# 3. config-scope validation
# ============================================================================
class _Stage1:
    def __init__(self, symbol=SYM, enabled_exchanges=EXS):
        self._symbol = symbol
        self._enabled = list(enabled_exchanges)

    @property
    def symbol(self):
        return self._symbol

    @property
    def enabled_exchanges(self):
        return self._enabled


def _make_stage2(*, symbol=SYM, enabled=True, market_types=("perp",),
                 timeframes=("1m", "5m"), active_exchanges=EXS, soft_grace_s=5):
    raw = {
        "stage2": {"enabled": False, "config_version": "2.1.0", "feature_schema_version": 1},
        "active_exchanges": list(active_exchanges),
        "defaults": {"timeframes": list(timeframes),
                     "bucket_close": {"soft_grace_s": soft_grace_s, "hard_deadline_s": 15}},
        "asset_tiers": {"major": {}},
        "symbols": {symbol: {"tier": "major", "enabled": enabled,
                             "market_types": list(market_types)}},
    }
    return Stage2Config(raw)


def test_scope_ok_real_configs():
    c1, c2 = _configs()
    symbol, exchanges, resolved = _resolve_shadow_scope(c1, c2, reference_exchange="binance")
    assert symbol == "BTCUSDT" and exchanges == EXS


def test_scope_unknown_symbol_rejected():
    with pytest.raises((ShadowCliError, Stage2ConfigError)):
        _resolve_shadow_scope(_Stage1(symbol="ETHUSDT"), _make_stage2(),
                              reference_exchange="binance")


def test_scope_disabled_symbol_rejected():
    with pytest.raises(ShadowCliError):
        _resolve_shadow_scope(_Stage1(), _make_stage2(enabled=False),
                              reference_exchange="binance")


def test_scope_perp_missing_rejected():
    with pytest.raises((ShadowCliError, Stage2ConfigError)):
        _resolve_shadow_scope(_Stage1(), _make_stage2(market_types=("spot",)),
                              reference_exchange="binance")


def test_scope_5m_missing_rejected():
    with pytest.raises(ShadowCliError):
        _resolve_shadow_scope(_Stage1(), _make_stage2(timeframes=("1m", "15m")),
                              reference_exchange="binance")


@pytest.mark.parametrize("active", ["binance", [], ["binance", "kraken"], ["binance", "binance"]])
def test_scope_malformed_active_exchanges_rejected(active):
    with pytest.raises(ShadowCliError):
        _resolve_shadow_scope(_Stage1(), _make_stage2(active_exchanges=active),
                              reference_exchange="binance")


def test_scope_active_exchange_absent_from_stage1_enabled():
    with pytest.raises(ShadowCliError):
        _resolve_shadow_scope(_Stage1(enabled_exchanges=("binance", "bybit")), _make_stage2(),
                              reference_exchange="binance")


@pytest.mark.parametrize("ref", ["kraken", "bitget"])
def test_scope_reference_invalid_or_not_active(ref):
    with pytest.raises(ShadowCliError):
        _resolve_shadow_scope(_Stage1(), _make_stage2(), reference_exchange=ref)


# ============================================================================
# 4. code version
# ============================================================================
def test_code_version_explicit_passthrough():
    c1, c2 = _configs()
    db = FakeDB(instruments={ex: _inst_row(ex) for ex in EXS})
    rep = _run(execute_shadow_once(
        db, c1, c2, now=datetime(2026, 3, 1, 0, 10, tzinfo=UTC),
        explicit_bucket_ts="2026-03-01T00:00:00Z", reference_exchange="binance",
        explicit_code_version="cli-explicit", metadata_fetch_json=_fetch_json_factory()))
    assert rep.code_version == "cli-explicit"


def test_code_version_resolver_failure_propagates(monkeypatch):
    c1, c2 = _configs()
    monkeypatch.delenv("STAGE2_CODE_VERSION", raising=False)

    def boom(explicit=None, **kw):
        raise VersioningError("no version")

    monkeypatch.setattr(sc, "resolve_feature_code_version", boom)
    db = FakeDB()
    with pytest.raises(VersioningError):
        _run(execute_shadow_once(
            db, c1, c2, now=datetime(2026, 3, 1, 0, 10, tzinfo=UTC),
            explicit_bucket_ts="2026-03-01T00:00:00Z", reference_exchange="binance",
            explicit_code_version=None, metadata_fetch_json=_fetch_json_factory()))
    assert db.calls == []          # failed before any DB write


# ============================================================================
# 5. one-shot execution order
# ============================================================================
def test_once_execution_order_and_due_jobs_empty(monkeypatch):
    c1, c2 = _configs()
    db = FakeDB(instruments={ex: _inst_row(ex) for ex in EXS})   # fresh -> no network
    captured = {}
    real = sc.process_shadow_cycle
    calls = []

    async def spy(*a, **k):
        calls.append(1)
        captured["kwargs"] = k
        return await real(*a, **k)

    monkeypatch.setattr(sc, "process_shadow_cycle", spy)
    rep = _run(execute_shadow_once(
        db, c1, c2, now=datetime(2026, 3, 1, 0, 10, tzinfo=UTC),
        explicit_bucket_ts="2026-03-01T00:00:00Z", reference_exchange="binance",
        explicit_code_version="cli", metadata_fetch_json=_fetch_json_factory()))
    order = [c if isinstance(c, str) else c[0] for c in db.calls]
    assert order[:6] == ["init_stage2_schema", "seed_symbols", "seed_caps",
                         "get_instr", "get_instr", "get_instr"]
    assert "avail" in order and order.index("avail") > order.index("seed_caps")
    assert sum(calls) == 1
    assert captured["kwargs"]["due_outcome_jobs"] == ()
    assert isinstance(rep, ShadowExecutionReport)
    assert rep.result is captured_result(rep)      # result returned unchanged
    assert db.seeded_symbols is not None and len(db.seeded_caps) == 18
    assert rep.stage2_global_enabled is False       # global disabled did not block


def captured_result(rep):
    return rep.result   # identity helper (the report holds the exact cycle result)


def test_once_validation_before_db_writes():
    c1, c2 = _configs()
    db = FakeDB()
    with pytest.raises(ShadowCliError):
        _run(execute_shadow_once(
            db, c1, c2, now=datetime(2026, 3, 1, 0, 10, tzinfo=UTC),
            explicit_bucket_ts="2026-03-01T00:00:00Z", reference_exchange="kraken",
            explicit_code_version="cli", metadata_fetch_json=_fetch_json_factory()))
    assert db.calls == []           # nothing initialized/seeded/written


# ============================================================================
# 6. instrument-metadata bootstrap
# ============================================================================
def _bootstrap_once(db, *, fetch_json):
    c1, c2 = _configs()
    return _run(execute_shadow_once(
        db, c1, c2, now=datetime(2026, 3, 1, 0, 10, tzinfo=UTC),
        explicit_bucket_ts="2026-03-01T00:00:00Z", reference_exchange="binance",
        explicit_code_version="cli", metadata_fetch_json=fetch_json))


def test_metadata_fresh_row_no_network_no_write():
    db = FakeDB(instruments={ex: _inst_row(ex, is_stale=False) for ex in EXS})
    calls = []
    _bootstrap_once(db, fetch_json=_fetch_json_factory(counter=calls))
    assert calls == []                                        # no network
    assert db.upserted_instruments == []                     # no rewrite


def test_metadata_missing_row_fetched_and_inserted():
    db = FakeDB(instruments={})                               # all missing
    calls = []
    _bootstrap_once(db, fetch_json=_fetch_json_factory(counter=calls))
    assert len(calls) == 3                                    # one fetch per exchange
    assert {kw["exchange"] for kw in db.upserted_instruments} == set(EXS)
    for kw in db.upserted_instruments:
        assert kw["accept_mismatch"] is False
        assert kw["is_stale"] is False


def test_metadata_stale_lkg_refreshed_on_failed_fetch_stored_stale():
    db = FakeDB(instruments={"binance": _inst_row("binance", is_stale=True),
                             "bybit": _inst_row("bybit"), "okx": _inst_row("okx")})
    # binance refetch fails -> LKG returned as stale and stored stale
    _bootstrap_once(db, fetch_json=_fetch_json_factory(fail=("binance",)))
    binance_upserts = [kw for kw in db.upserted_instruments if kw["exchange"] == "binance"]
    assert len(binance_upserts) == 1 and binance_upserts[0]["is_stale"] is True


def test_metadata_mismatch_propagates():
    db = FakeDB(instruments={"binance": _inst_row("binance", is_stale=True, tick=0.5)})
    with pytest.raises(MetadataMismatchError):
        _bootstrap_once(db, fetch_json=_fetch_json_factory(tick="0.1"))   # tick differs -> mismatch


def test_metadata_missing_with_no_lkg_failure_propagates():
    db = FakeDB(instruments={})            # binance missing, fetch fails, no LKG
    with pytest.raises(MetadataUnavailableError):
        _bootstrap_once(db, fetch_json=_fetch_json_factory(fail=("binance",)))


def test_metadata_okx_missing_ctval_fails_closed():
    db = FakeDB(instruments={})
    with pytest.raises(FailClosedError):
        _bootstrap_once(db, fetch_json=_fetch_json_factory(okx_ctval=None))


def test_metadata_single_shared_session(monkeypatch):
    # default path (no injected fetcher) must open exactly ONE aiohttp session.
    import aiohttp
    created = []
    okx_id = to_exchange_symbol("okx", SYM, MT)

    class FakeResp:
        def __init__(self, url):
            self._url = url

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def raise_for_status(self):
            return None

        async def json(self):
            if "binance" in self._url:
                return {"symbols": [{"symbol": SYM, "filters": [
                    {"filterType": "PRICE_FILTER", "tickSize": "0.1"}]}]}
            if "bybit" in self._url:
                return {"result": {"list": [{"symbol": SYM,
                                             "priceFilter": {"tickSize": "0.1"},
                                             "lotSizeFilter": {"qtyStep": "1"}}]}}
            return {"data": [{"instId": okx_id, "tickSz": "0.1", "ctVal": "0.01"}]}

    class FakeSession:
        def __init__(self, *a, **k):
            created.append(1)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def get(self, url, params=None):
            return FakeResp(url)

    monkeypatch.setattr(aiohttp, "ClientSession", FakeSession)
    db = FakeDB(instruments={})       # all missing -> default fetch path
    _bootstrap_once(db, fetch_json=None)
    assert created == [1]             # exactly one shared session
    assert {kw["exchange"] for kw in db.upserted_instruments} == set(EXS)


# ============================================================================
# 7. dry-run
# ============================================================================
def _dry_run(db, *, bucket="2026-03-01T00:00:00Z", ref="binance"):
    c1, c2 = _configs()
    return _run(execute_shadow_dry_run(
        db, c1, c2, now=datetime(2026, 3, 1, 0, 10, tzinfo=UTC),
        explicit_bucket_ts=bucket, reference_exchange=ref, explicit_code_version="cli"))


def test_dry_run_zero_writes_and_labels_would_insert():
    db = FakeDB(status=_status_snapshot(STATUS_EMPTY))
    rep = _dry_run(db)
    assert rep.command == SHADOW_DRY_RUN and rep.writes_enabled is False
    # real reads happened; no init/seed/metadata/analytic writes on the DB
    order = [c if isinstance(c, str) else c[0] for c in db.calls]
    assert "raw" in order
    for forbidden in ("init_stage2_schema", "init_schema", "seed_symbols", "seed_caps",
                      "get_instr", "upsert_instr", "efv", "consensus", "insert_pred", "outcome"):
        assert forbidden not in order
    human = sc.render_shadow_execution_report(rep)
    # the persistence EFFECT (right of the arrow) must be WOULD_INSERT, never a
    # bare INSERTED (the core status name PREDICTION_INSERTED may still appear).
    assert "-> WOULD_INSERT" in human and "-> INSERTED" not in human


def test_dry_run_missing_schema_errors_before_cycle():
    db = FakeDB(status=_status_snapshot(STATUS_NOT_INITIALIZED))
    with pytest.raises(ShadowCliError):
        _dry_run(db)
    order = [c if isinstance(c, str) else c[0] for c in db.calls]
    assert "raw" not in order and "avail" not in order        # stopped before the cycle


def test_dry_run_missing_prerequisite_errors_before_cycle():
    status = _status_snapshot(STATUS_EMPTY,
                              prereq_overrides={"okx": _prereq("okx", instrument=False)})
    db = FakeDB(status=status)
    with pytest.raises(ShadowCliError):
        _dry_run(db)
    order = [c if isinstance(c, str) else c[0] for c in db.calls]
    assert "raw" not in order


def test_dry_run_global_disabled_does_not_block():
    db = FakeDB(status=_status_snapshot(STATUS_EMPTY))
    rep = _dry_run(db)
    assert rep.stage2_global_enabled is False


def test_dry_run_no_consensus(monkeypatch):
    # every exchange raw read fails -> zero successful features -> no consensus.
    db = FakeDB(status=_status_snapshot(STATUS_EMPTY))

    async def boom_raw(*, exchange, **kw):
        db.calls.append(("raw", exchange))
        raise ValueError(f"raw boom {exchange}")

    db.fetch_exchange_feature_raw_bundle = boom_raw
    rep = _dry_run(db)
    from analytics.forecasting.shadow_cycle import PREDICTION_SKIPPED_NO_CONSENSUS
    assert rep.result.prediction_status == PREDICTION_SKIPPED_NO_CONSENSUS
    human = sc.render_shadow_execution_report(rep)
    assert "DRY_RUN_PREDICTION_SKIPPED_NO_CONSENSUS" in human


# ============================================================================
# 8. status
# ============================================================================
@pytest.mark.parametrize("state", [
    STATUS_NOT_INITIALIZED, STATUS_PARTIAL_SCHEMA, STATUS_EMPTY])
def test_status_states_without_prediction(state):
    db = FakeDB(status=_status_snapshot(state))
    c1, c2 = _configs()
    rep = _run(execute_shadow_status(db, c1, c2))
    assert rep.state == state
    assert rep.latest_prediction is None and rep.outcomes == ()
    # status touches only fetch_shadow_status: no init/seed/writer/network/clock
    assert db.calls == ["status"]


def test_status_ready_with_prediction_and_outcomes():
    latest = MappingProxyType({
        "symbol": SYM, "market_type": MT, "timeframe": "5m", "bucket_ts": B,
        "calculation_version": "0123456789abcdef", "rule_version": "r1",
        "direction": "LONG", "confidence": 0.4, "final_score": 0.3,
        "reference_price": 105.0, "reference_price_source": "binance_close_5m",
        "horizon_set": ("15m", "1h", "4h"), "reasons": ("PRICE_BULLISH",),
        "exchanges_expected_max": 3, "min_coverage_ratio": 1.0,
        "data_confidence_overall": 80.0, "consensus_confidence": 80.0,
        "is_partial_consensus": False, "config_version": "2.1.0",
        "code_version": "c1", "created_at": B})
    outcomes = (MappingProxyType({
        "horizon": "15m", "outcome_version": "v", "evaluation_exchange": "binance",
        "evaluation_price_source": "klines_1m", "target_close_price": 105.0,
        "market_return_pct": 1.0, "directional_return_pct": 1.0,
        "mfe_pct": 2.0, "mae_pct": -0.5, "computed_at": B}),)
    db = FakeDB(status=_status_snapshot(STATUS_READY, latest=latest, outcomes=outcomes))
    c1, c2 = _configs()
    rep = _run(execute_shadow_status(db, c1, c2))
    assert rep.state == STATUS_READY and rep.latest_prediction is not None
    human = sc.render_shadow_status_report(rep)
    assert "15m" in human and "RECORDED" in human and "NOT_RECORDED" in human   # 1h/4h missing
    js = sc.status_report_to_jsonable(rep)
    assert js["outcomes_by_horizon"]["15m"]["status"] == "RECORDED"
    assert js["outcomes_by_horizon"]["1h"]["status"] == "NOT_RECORDED"


# ============================================================================
# 9. renderers / JSON
# ============================================================================
def _once_report():
    db = FakeDB(instruments={ex: _inst_row(ex) for ex in EXS})
    return _bootstrap_once(db, fetch_json=_fetch_json_factory())


def test_execution_json_separates_status_writes_effect():
    rep = _once_report()
    js = sc.execution_report_to_jsonable(rep)
    assert js["core_prediction_status"] == "PREDICTION_INSERTED"
    assert js["writes_enabled"] is True
    assert js["persistence_effect"] == "INSERTED"
    assert js["outcomes_attempted"] == 0


def test_dry_run_json_persistence_effect_would_insert():
    db = FakeDB(status=_status_snapshot(STATUS_EMPTY))
    rep = _dry_run(db)
    js = sc.execution_report_to_jsonable(rep)
    assert js["writes_enabled"] is False
    assert js["persistence_effect"] == "WOULD_INSERT"
    assert js["persistence_effect"] != "INSERTED"


def test_reports_have_no_secrets_or_consensus_snapshot():
    rep = _once_report()
    for text in (sc.render_shadow_execution_report(rep), sc.render_execution_report_json(rep)):
        low = text.lower()
        for banned in ("postgres", "dsn", "redis", "consensus_snapshot", "password", "telegram"):
            assert banned not in low


def test_json_rejects_non_finite():
    with pytest.raises(ShadowCliError):
        sc._to_jsonable(float("nan"))
    with pytest.raises(ShadowCliError):
        sc._to_jsonable(float("inf"))


def test_json_is_deterministic_utc_isoformat():
    rep = _once_report()
    js = sc.execution_report_to_jsonable(rep)
    assert js["bucket_ts"].endswith("+00:00")
    assert sc.render_execution_report_json(rep) == sc.render_execution_report_json(rep)


def test_render_does_not_mutate_report():
    rep = _once_report()
    before_exchanges = tuple(e.exchange for e in rep.result.bucket_result.exchange_features)
    sc.render_shadow_execution_report(rep)
    sc.render_execution_report_json(rep)
    after = tuple(e.exchange for e in rep.result.bucket_result.exchange_features)
    assert before_exchanges == after


# ============================================================================
# 10. status is NOT recovery (section 30)
# ============================================================================
def test_status_does_not_enqueue_or_infer_due(monkeypatch):
    # status must never construct a DueOutcomeJob nor call process_shadow_cycle.
    def forbidden(*a, **k):
        raise AssertionError("status must not run the cycle")

    monkeypatch.setattr(sc, "process_shadow_cycle", forbidden)
    db = FakeDB(status=_status_snapshot(STATUS_EMPTY))
    c1, c2 = _configs()
    rep = _run(execute_shadow_status(db, c1, c2))
    assert rep.state == STATUS_EMPTY
    assert db.calls == ["status"]


def test_once_and_dry_run_pass_empty_due_jobs(monkeypatch):
    seen = []
    real = sc.process_shadow_cycle

    async def spy(*a, **k):
        seen.append(k["due_outcome_jobs"])
        return await real(*a, **k)

    monkeypatch.setattr(sc, "process_shadow_cycle", spy)
    _bootstrap_once(FakeDB(instruments={ex: _inst_row(ex) for ex in EXS}),
                    fetch_json=_fetch_json_factory())
    _dry_run(FakeDB(status=_status_snapshot(STATUS_EMPTY)))
    assert seen == [(), ()]


# ============================================================================
# 11. architecture (section 29)
# ============================================================================
_RUNTIME_SRC = Path("runtime/shadow_cli.py")


def test_runtime_has_no_while_or_forbidden_async_calls():
    tree = ast.parse(_RUNTIME_SRC.read_text())
    for node in ast.walk(tree):
        assert not isinstance(node, ast.While), "no while loops allowed"
        if isinstance(node, ast.Attribute):
            assert node.attr not in {"gather", "create_task", "ensure_future", "sleep"}


def test_runtime_has_no_raw_sql():
    # Whole-word uppercase SQL keywords only, so labels like WOULD_INSERT /
    # INSERTED and method names like insert_forecast_prediction don't false-match.
    import re
    src = _RUNTIME_SRC.read_text()
    for kw in ("SELECT", "INSERT", "UPDATE", "DELETE", "FROM"):
        assert not re.search(rf"\b{kw}\b", src), kw
    assert "CREATE TABLE" not in src


def test_runtime_imports_no_analytics_implementation_details():
    tree = ast.parse(_RUNTIME_SRC.read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            modules.add(node.module or "")
    # It composes the shadow_cycle boundary only — not feature/consensus/forecast cores.
    for banned in ("analytics.feature_engine.pipeline",
                   "analytics.feature_engine.consensus_pipeline",
                   "analytics.forecasting.core", "analytics.forecasting.outcomes"):
        assert banned not in modules
