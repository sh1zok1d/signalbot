"""Unit tests for storage/shadow_cli_readers.py + the two Database shadow-CLI
read methods. Fake asyncpg-style pool/connection — no DB, Docker, or network.
Async driven with asyncio.run (matching the other storage writer/reader tests).
"""
from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

from storage.db import Database
from storage.shadow_cli_readers import (
    LATEST_SHADOW_OUTCOMES_SQL, LATEST_SHADOW_PREDICTION_SQL,
    SHADOW_LIQUIDATION_AVAILABILITY_SQL, SHADOW_PREREQUISITES_SQL,
    SHADOW_SCHEMA_STATE_SQL, SHADOW_STATUS_TABLES, ShadowCliReaderError,
    read_shadow_liquidation_availability, read_shadow_status,
)

UTC = timezone.utc
B = datetime(2026, 3, 1, 0, 0, tzinfo=UTC)
SRC = Path("storage/shadow_cli_readers.py")


def _run(coro):
    return asyncio.run(coro)


# ---- fake asyncpg pool / connection ----------------------------------------
class FakeConn:
    def __init__(self, *, fetch_map=None, fetchrow_map=None):
        self.fetch_calls = []
        self.fetchrow_calls = []
        self._fetch_map = fetch_map or {}
        self._fetchrow_map = fetchrow_map or {}

    async def fetch(self, sql, *args):
        self.fetch_calls.append((sql, args))
        r = self._fetch_map.get(sql)
        if callable(r):
            return r(args)
        return [] if r is None else r

    async def fetchrow(self, sql, *args):
        self.fetchrow_calls.append((sql, args))
        r = self._fetchrow_map.get(sql)
        return r(args) if callable(r) else r

    async def execute(self, *a, **k):          # pragma: no cover - must never run
        raise AssertionError("execute() must not be called")

    async def executemany(self, *a, **k):      # pragma: no cover
        raise AssertionError("executemany() must not be called")


class FakePool:
    def __init__(self, conn):
        self.conn = conn
        self.acquire_count = 0

    def acquire(self):
        pool = self

        class _Acq:
            async def __aenter__(self_):
                pool.acquire_count += 1
                return pool.conn

            async def __aexit__(self_, *a):
                return False
        return _Acq()


class BoomConn:
    async def fetch(self, *a, **k):
        raise RuntimeError("db boom")

    async def fetchrow(self, *a, **k):
        raise RuntimeError("db boom")


def _db(conn) -> Database:
    db = Database("postgresql://ignored")
    db.pool = FakePool(conn)
    return db


def _cap_row(exchange, *, live=True, enabled=True, coverage="full"):
    return {"exchange": exchange, "live_supported": live,
            "enabled": enabled, "coverage_type": coverage}


# ============================================================================
# A. liquidation availability SQL shape
# ============================================================================
def test_liquidation_sql_explicit_fields_and_filters():
    sql = SHADOW_LIQUIDATION_AVAILABILITY_SQL
    assert "SELECT exchange, live_supported, enabled, coverage_type" in sql
    assert "*" not in sql
    assert "FROM symbol_exchange_capabilities" in sql
    assert "exchange = ANY($1::text[])" in sql
    assert "symbol = $2" in sql and "market_type = $3" in sql
    assert "metric = 'liquidations'" in sql


# ============================================================================
# B. liquidation availability reader behavior
# ============================================================================
def test_availability_semantics_and_order_preserved():
    conn = FakeConn(fetch_map={SHADOW_LIQUIDATION_AVAILABILITY_SQL: [
        _cap_row("binance", coverage="snapshot"),
        _cap_row("okx", coverage="aggregated"),
        _cap_row("bybit", coverage="full"),
    ]})
    result = _run(read_shadow_liquidation_availability(
        conn, exchanges=["okx", "binance", "bybit"], symbol="BTCUSDT", market_type="perp"))
    assert isinstance(result, MappingProxyType)
    assert list(result.keys()) == ["okx", "binance", "bybit"]       # caller order
    assert result == {"okx": True, "binance": True, "bybit": True}


@pytest.mark.parametrize("row,expected", [
    (_cap_row("binance", live=False), False),
    (_cap_row("binance", enabled=False), False),
    (_cap_row("binance", coverage="unavailable"), False),
    (_cap_row("binance", live=True, enabled=True, coverage="snapshot"), True),
])
def test_availability_boolean_rules(row, expected):
    conn = FakeConn(fetch_map={SHADOW_LIQUIDATION_AVAILABILITY_SQL: [row]})
    result = _run(read_shadow_liquidation_availability(
        conn, exchanges=["binance"], symbol="BTCUSDT", market_type="perp"))
    assert result["binance"] is expected


def test_availability_missing_row_rejected_not_filled_false():
    conn = FakeConn(fetch_map={SHADOW_LIQUIDATION_AVAILABILITY_SQL: [_cap_row("binance")]})
    with pytest.raises(ShadowCliReaderError):
        _run(read_shadow_liquidation_availability(
            conn, exchanges=["binance", "bybit"], symbol="BTCUSDT", market_type="perp"))


def test_availability_duplicate_row_rejected():
    conn = FakeConn(fetch_map={SHADOW_LIQUIDATION_AVAILABILITY_SQL: [
        _cap_row("binance"), _cap_row("binance")]})
    with pytest.raises(ShadowCliReaderError):
        _run(read_shadow_liquidation_availability(
            conn, exchanges=["binance"], symbol="BTCUSDT", market_type="perp"))


def test_availability_unexpected_row_rejected():
    conn = FakeConn(fetch_map={SHADOW_LIQUIDATION_AVAILABILITY_SQL: [
        _cap_row("binance"), _cap_row("kraken")]})
    with pytest.raises(ShadowCliReaderError):
        _run(read_shadow_liquidation_availability(
            conn, exchanges=["binance"], symbol="BTCUSDT", market_type="perp"))


def test_availability_malformed_bool_rejected():
    bad = {"exchange": "binance", "live_supported": "t", "enabled": True, "coverage_type": "full"}
    conn = FakeConn(fetch_map={SHADOW_LIQUIDATION_AVAILABILITY_SQL: [bad]})
    with pytest.raises(ShadowCliReaderError):
        _run(read_shadow_liquidation_availability(
            conn, exchanges=["binance"], symbol="BTCUSDT", market_type="perp"))


def test_availability_result_immutable():
    conn = FakeConn(fetch_map={SHADOW_LIQUIDATION_AVAILABILITY_SQL: [_cap_row("binance")]})
    result = _run(read_shadow_liquidation_availability(
        conn, exchanges=["binance"], symbol="BTCUSDT", market_type="perp"))
    with pytest.raises(TypeError):
        result["binance"] = False


# ============================================================================
# C. Database.fetch_shadow_liquidation_availability (validation + one acquire)
# ============================================================================
@pytest.mark.parametrize("over", [
    {"exchanges": []}, {"exchanges": "binance"}, {"exchanges": ["binance", "binance"]},
    {"exchanges": [5]}, {"symbol": ""}, {"market_type": "  "},
])
def test_db_availability_validates_before_acquire(over):
    conn = FakeConn(fetch_map={SHADOW_LIQUIDATION_AVAILABILITY_SQL: [_cap_row("binance")]})
    db = _db(conn)
    kw = dict(exchanges=["binance"], symbol="BTCUSDT", market_type="perp")
    kw.update(over)
    with pytest.raises(ShadowCliReaderError):
        _run(db.fetch_shadow_liquidation_availability(**kw))
    assert db.pool.acquire_count == 0


def test_db_availability_one_acquire():
    conn = FakeConn(fetch_map={SHADOW_LIQUIDATION_AVAILABILITY_SQL: [
        _cap_row("binance"), _cap_row("bybit"), _cap_row("okx")]})
    db = _db(conn)
    result = _run(db.fetch_shadow_liquidation_availability(
        exchanges=["binance", "bybit", "okx"], symbol="BTCUSDT", market_type="perp"))
    assert db.pool.acquire_count == 1
    assert len(conn.fetch_calls) == 1
    assert dict(result) == {"binance": True, "bybit": True, "okx": True}


def test_db_availability_exception_propagates():
    db = _db(BoomConn())
    with pytest.raises(RuntimeError, match="db boom"):
        _run(db.fetch_shadow_liquidation_availability(
            exchanges=["binance"], symbol="BTCUSDT", market_type="perp"))


# ============================================================================
# D. status SQL shape (to_regclass, no writes, no SELECT *)
# ============================================================================
def test_schema_state_sql_uses_to_regclass_for_all_tables():
    sql = SHADOW_SCHEMA_STATE_SQL
    for table in SHADOW_STATUS_TABLES:
        assert f"to_regclass('public.{table}')" in sql


def test_status_sql_has_no_write_or_star():
    import re
    for sql in (SHADOW_SCHEMA_STATE_SQL, SHADOW_PREREQUISITES_SQL,
                LATEST_SHADOW_PREDICTION_SQL, LATEST_SHADOW_OUTCOMES_SQL):
        up = sql.upper()
        assert "SELECT *" not in up
        # whole-word DML keywords only (so a column like created_at is fine)
        for banned in ("CREATE", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE"):
            assert not re.search(rf"\b{banned}\b", up), banned


def test_latest_prediction_sql_fields_ordering_limit_no_snapshot():
    sql = LATEST_SHADOW_PREDICTION_SQL
    assert "consensus_snapshot" not in sql                      # never selected for CLI
    for col in ("symbol", "market_type", "timeframe", "bucket_ts", "calculation_version",
                "rule_version", "direction", "confidence", "final_score", "reference_price",
                "reference_price_source", "horizon_set", "reasons", "exchanges_expected_max",
                "min_coverage_ratio", "data_confidence_overall", "consensus_confidence",
                "is_partial_consensus", "config_version", "code_version", "created_at"):
        assert col in sql
    assert ("ORDER BY bucket_ts DESC, created_at DESC, calculation_version DESC, "
            "rule_version DESC") in sql
    assert "LIMIT 1" in sql


def test_latest_outcomes_sql_identity_filter_and_horizon_order():
    sql = LATEST_SHADOW_OUTCOMES_SQL
    for col in ("symbol = $1", "market_type = $2", "timeframe = $3",
                "bucket_ts = $4", "calculation_version = $5", "rule_version = $6"):
        assert col in sql
    # 15m -> 1h -> 4h
    assert "WHEN '15m' THEN 0 WHEN '1h' THEN 1 WHEN '4h' THEN 2" in sql


# ============================================================================
# E. status reader state machine
# ============================================================================
def _schema_row(present_tables):
    return {t: (f"public.{t}" if t in present_tables else None) for t in SHADOW_STATUS_TABLES}


def _pred_row():
    return {
        "symbol": "BTCUSDT", "market_type": "perp", "timeframe": "5m", "bucket_ts": B,
        "calculation_version": "0123456789abcdef", "rule_version": "rules-v1",
        "direction": "LONG", "confidence": 0.4, "final_score": 0.3,
        "reference_price": 105.0, "reference_price_source": "binance_close_5m",
        "horizon_set": '["15m", "1h", "4h"]', "reasons": '["PRICE_BULLISH"]',
        "exchanges_expected_max": 3, "min_coverage_ratio": 1.0,
        "data_confidence_overall": 80.0, "consensus_confidence": 80.0,
        "is_partial_consensus": False, "config_version": "2.1.0",
        "code_version": "code-v1", "created_at": B,
    }


def _outcome_row(horizon):
    return {"horizon": horizon, "outcome_version": "forecast-outcome-v0.1.0",
            "evaluation_exchange": "binance", "evaluation_price_source": "klines_1m",
            "target_close_price": 105.0, "market_return_pct": 1.0,
            "directional_return_pct": 1.0, "mfe_pct": 2.0, "mae_pct": -0.5, "computed_at": B}


def _status(schema_present, *, pred=None, outcomes=(), exchanges=("binance", "bybit", "okx")):
    prereq_rows = [
        {"exchange": ex, "instrument_present": True, "instrument_is_stale": False,
         "liquidation_capability_present": True, "liquidation_live_supported": True,
         "liquidation_enabled": True, "liquidation_coverage_type": "full"}
        for ex in exchanges
    ]
    conn = FakeConn(
        fetchrow_map={
            SHADOW_SCHEMA_STATE_SQL: lambda a: _schema_row(schema_present),
            LATEST_SHADOW_PREDICTION_SQL: lambda a: pred,
        },
        fetch_map={
            SHADOW_PREREQUISITES_SQL: lambda a: prereq_rows,
            LATEST_SHADOW_OUTCOMES_SQL: lambda a: list(outcomes),
        })
    snapshot = _run(read_shadow_status(
        conn, exchanges=list(exchanges), symbol="BTCUSDT", market_type="perp", timeframe="5m"))
    return conn, snapshot


def test_status_not_initialized_queries_no_other_tables():
    conn, snap = _status(())          # no tables present
    assert snap["state"] == "NOT_INITIALIZED"
    assert snap["prerequisites"] == () and snap["latest_prediction"] is None
    assert snap["outcomes"] == ()
    # only the schema-state fetchrow ran; no prereq/prediction/outcome queries
    assert len(conn.fetchrow_calls) == 1
    assert conn.fetch_calls == []


def test_status_partial_schema_queries_no_missing_tables():
    conn, snap = _status(("symbols", "exchange_instruments"))   # some, not all
    assert snap["state"] == "PARTIAL_SCHEMA"
    assert snap["latest_prediction"] is None and snap["outcomes"] == ()
    assert len(conn.fetchrow_calls) == 1                        # only schema-state
    assert conn.fetch_calls == []


def test_status_empty_all_tables_no_prediction():
    conn, snap = _status(SHADOW_STATUS_TABLES, pred=None)
    assert snap["state"] == "EMPTY"
    assert snap["latest_prediction"] is None and snap["outcomes"] == ()
    assert len(snap["prerequisites"]) == 3                      # prereqs read
    # schema + prediction fetchrow; prereq fetch; no outcome fetch
    prediction_calls = [c for c in conn.fetchrow_calls if c[0] == LATEST_SHADOW_PREDICTION_SQL]
    assert len(prediction_calls) == 1
    outcome_calls = [c for c in conn.fetch_calls if c[0] == LATEST_SHADOW_OUTCOMES_SQL]
    assert outcome_calls == []


def test_status_ready_no_outcomes():
    conn, snap = _status(SHADOW_STATUS_TABLES, pred=_pred_row(), outcomes=())
    assert snap["state"] == "READY"
    assert snap["latest_prediction"] is not None
    assert snap["latest_prediction"]["horizon_set"] == ("15m", "1h", "4h")   # JSON parsed
    assert snap["outcomes"] == ()
    # the outcome identity filter was passed the prediction identity
    outcome_call = [c for c in conn.fetch_calls if c[0] == LATEST_SHADOW_OUTCOMES_SQL][0]
    assert outcome_call[1] == ("BTCUSDT", "perp", "5m", B, "0123456789abcdef", "rules-v1")


def test_status_ready_all_outcomes_detached():
    outcomes = [_outcome_row("15m"), _outcome_row("1h"), _outcome_row("4h")]
    conn, snap = _status(SHADOW_STATUS_TABLES, pred=_pred_row(), outcomes=outcomes)
    assert snap["state"] == "READY"
    assert len(snap["outcomes"]) == 3
    assert all(isinstance(o, MappingProxyType) for o in snap["outcomes"])
    assert isinstance(snap["latest_prediction"], MappingProxyType)
    with pytest.raises(TypeError):
        snap["outcomes"][0]["horizon"] = "x"


# ============================================================================
# F. Database.fetch_shadow_status
# ============================================================================
def test_db_status_validates_before_acquire():
    conn = FakeConn(fetchrow_map={SHADOW_SCHEMA_STATE_SQL: lambda a: _schema_row(())})
    db = _db(conn)
    with pytest.raises(ShadowCliReaderError):
        _run(db.fetch_shadow_status(exchanges=[], symbol="BTCUSDT",
                                    market_type="perp", timeframe="5m"))
    assert db.pool.acquire_count == 0


def test_db_status_one_acquire_no_writes():
    conn = FakeConn(fetchrow_map={SHADOW_SCHEMA_STATE_SQL: lambda a: _schema_row(())})
    db = _db(conn)
    snap = _run(db.fetch_shadow_status(
        exchanges=["binance"], symbol="BTCUSDT", market_type="perp", timeframe="5m"))
    assert db.pool.acquire_count == 1
    assert snap["state"] == "NOT_INITIALIZED"


# ============================================================================
# G. architecture: no analytics/runtime/main/network import, no clock
# ============================================================================
def test_reader_module_imports_are_pure_storage():
    tree = ast.parse(SRC.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    for mod in imported:
        top = mod.split(".")[0]
        assert top not in {"analytics", "runtime", "main", "aiohttp", "asyncpg", "requests"}, mod


def test_reader_module_has_no_clock():
    src = SRC.read_text()
    for banned in ("datetime.now", "utcnow", "time.time", "now()"):
        assert banned not in src, banned


# ============================================================================
# H. direct readers validate BEFORE any DB access
# ============================================================================
@pytest.mark.parametrize("over", [
    {"exchanges": []}, {"exchanges": "binance"}, {"exchanges": ["binance", "binance"]},
    {"exchanges": [5]}, {"symbol": ""}, {"market_type": "  "},
])
def test_direct_availability_reader_validates_before_io(over):
    conn = FakeConn(fetch_map={SHADOW_LIQUIDATION_AVAILABILITY_SQL: [_cap_row("binance")]})
    kw = dict(exchanges=["binance"], symbol="BTCUSDT", market_type="perp")
    kw.update(over)
    with pytest.raises(ShadowCliReaderError):
        _run(read_shadow_liquidation_availability(conn, **kw))
    assert conn.fetch_calls == []                     # no DB access happened


@pytest.mark.parametrize("over", [
    {"exchanges": []}, {"exchanges": "binance"}, {"exchanges": ["a", "a"]},
    {"symbol": ""}, {"market_type": ""}, {"timeframe": "  "},
])
def test_direct_status_reader_validates_before_io(over):
    conn = FakeConn(fetchrow_map={SHADOW_SCHEMA_STATE_SQL: lambda a: _schema_row(())})
    kw = dict(exchanges=["binance"], symbol="BTCUSDT", market_type="perp", timeframe="5m")
    kw.update(over)
    with pytest.raises(ShadowCliReaderError):
        _run(read_shadow_status(conn, **kw))
    assert conn.fetch_calls == [] and conn.fetchrow_calls == []   # no DB access


# ============================================================================
# I. mutation-race: the validated exchange snapshot survives a blocked acquire
# ============================================================================
class GatedPool:
    """A pool whose acquire() blocks inside __aenter__ until `release` is set,
    letting a test mutate the caller's exchanges list mid-acquire."""

    def __init__(self, conn, started, release):
        self.conn = conn
        self.started = started
        self.release = release
        self.acquire_count = 0

    def acquire(self):
        pool = self

        class _Acq:
            async def __aenter__(self_):
                pool.acquire_count += 1
                pool.started.set()
                await pool.release.wait()
                return pool.conn

            async def __aexit__(self_, *a):
                return False
        return _Acq()


def _gated_db(conn):
    started, release = asyncio.Event(), asyncio.Event()
    db = Database("postgresql://ignored")
    db.pool = GatedPool(conn, started, release)
    return db, started, release


def test_availability_uses_validated_snapshot_across_acquire():
    conn = FakeConn(fetch_map={SHADOW_LIQUIDATION_AVAILABILITY_SQL: lambda a: [
        _cap_row("binance"), _cap_row("bybit"), _cap_row("okx")]})
    exchanges = ["binance", "bybit", "okx"]

    async def scenario():
        db, started, release = _gated_db(conn)
        task = asyncio.create_task(db.fetch_shadow_liquidation_availability(
            exchanges=exchanges, symbol="BTCUSDT", market_type="perp"))
        await started.wait()
        # mutate the caller list while acquire is blocked: add, remove, reorder
        exchanges.append("kraken")
        exchanges[0] = "okx"
        del exchanges[1]
        release.set()
        return await task

    result = _run(scenario())
    sql, args = conn.fetch_calls[0]
    assert args[0] == ["binance", "bybit", "okx"]            # only the original snapshot
    assert list(result.keys()) == ["binance", "bybit", "okx"]  # snapshot order preserved


def test_status_uses_validated_snapshot_across_acquire():
    conn = FakeConn(
        fetchrow_map={
            SHADOW_SCHEMA_STATE_SQL: lambda a: _schema_row(SHADOW_STATUS_TABLES),
            LATEST_SHADOW_PREDICTION_SQL: lambda a: None,      # EMPTY -> prereqs queried
        },
        fetch_map={
            SHADOW_PREREQUISITES_SQL: lambda a: [],
        })
    exchanges = ["binance", "bybit", "okx"]

    async def scenario():
        db, started, release = _gated_db(conn)
        task = asyncio.create_task(db.fetch_shadow_status(
            exchanges=exchanges, symbol="BTCUSDT", market_type="perp", timeframe="5m"))
        await started.wait()
        exchanges.append("kraken")
        exchanges[0] = "okx"
        del exchanges[1]
        release.set()
        return await task

    snap = _run(scenario())
    assert snap["state"] == "EMPTY"
    prereq_call = [c for c in conn.fetch_calls if c[0] == SHADOW_PREREQUISITES_SQL][0]
    assert prereq_call[1][0] == ["binance", "bybit", "okx"]   # only the original snapshot
