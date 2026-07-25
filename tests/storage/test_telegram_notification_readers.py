"""Unit tests for storage/telegram_notification_readers.py. Fake asyncpg-style
connection only — no DB, Docker, or network. Async driven with asyncio.run."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from storage.telegram_notification_readers import (
    MATERIALIZE_DELIVERIES_SQL, NOTIFIER_STATE_INSERT_SQL,
    NOTIFIER_STATE_SELECT_SQL, NOTIFIER_STATUS_AGGREGATE_SQL,
    PENDING_DELIVERIES_SQL, RECORD_ATTEMPT_START_SQL, RECORD_FAILURE_SQL,
    RECORD_SENT_SQL, TELEGRAM_SCHEMA_STATE_SQL, TelegramNotificationReaderError,
    ensure_notifier_started_at, materialize_telegram_deliveries,
    read_notifier_started_at, read_notifier_status_aggregate,
    read_pending_telegram_deliveries, read_telegram_schema_state,
    record_delivery_attempt_start, record_delivery_failure, record_delivery_sent,
    validate_notifier_scope, validate_recipient_scope,
)

UTC = timezone.utc
B = datetime(2026, 3, 1, tzinfo=UTC)
FP = "a" * 64


def _run(coro):
    return asyncio.run(coro)


# ---- fake asyncpg connection -------------------------------------------------
class FakeConn:
    def __init__(self, *, fetchval_map=None, fetch_map=None, fetchrow_map=None,
                 execute_map=None):
        self.fetchval_calls = []
        self.fetch_calls = []
        self.fetchrow_calls = []
        self.execute_calls = []
        self._fetchval_map = fetchval_map or {}
        self._fetch_map = fetch_map or {}
        self._fetchrow_map = fetchrow_map or {}
        self._execute_map = execute_map or {}

    async def fetchval(self, sql, *args):
        self.fetchval_calls.append((sql, args))
        r = self._fetchval_map.get(sql)
        return r(args) if callable(r) else r

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

    async def execute(self, sql, *args):
        self.execute_calls.append((sql, args))
        r = self._execute_map.get(sql)
        if callable(r):
            return r(args)
        return r if r is not None else "OK"


def _rec(d: dict):
    """A minimal asyncpg.Record-like stand-in supporting keys()/__getitem__."""
    class _R:
        def keys(self_):
            return d.keys()

        def __getitem__(self_, k):
            return d[k]
    return _R()


def _pending_row_dict(bucket_ts=B, direction="LONG"):
    return dict(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=bucket_ts,
        calculation_version="c" * 16, rule_version="r1", attempt_count=0,
        direction=direction, confidence=0.5, final_score=0.4, reference_price=100.0,
        reference_price_source="binance_close_5m", horizon_set='["15m","1h"]',
        reasons='["a","b"]', exchanges_expected_max=3, min_coverage_ratio=1.0,
        data_confidence_overall=80.0, consensus_confidence=80.0,
        is_partial_consensus=False, prediction_created_at=bucket_ts + timedelta(seconds=1))


# ============================================================================
# A. SQL shape: explicit columns, no SELECT *, no consensus_snapshot
# ============================================================================
def test_pending_sql_has_no_select_star():
    assert "SELECT *" not in PENDING_DELIVERIES_SQL
    assert "*" not in PENDING_DELIVERIES_SQL


def test_pending_sql_never_selects_consensus_snapshot():
    assert "consensus_snapshot" not in PENDING_DELIVERIES_SQL.lower()


def test_materialize_sql_never_selects_consensus_snapshot():
    assert "consensus_snapshot" not in MATERIALIZE_DELIVERIES_SQL.lower()


def test_materialize_sql_no_select_star():
    assert "SELECT *" not in MATERIALIZE_DELIVERIES_SQL


def test_materialize_sql_uses_not_exists_anti_join():
    assert "NOT EXISTS" in MATERIALIZE_DELIVERIES_SQL


def test_materialize_sql_filters_actionable_directions_only():
    assert "direction IN ('LONG', 'SHORT')" in MATERIALIZE_DELIVERIES_SQL
    assert "NEUTRAL" not in MATERIALIZE_DELIVERIES_SQL


def test_materialize_sql_orders_by_created_at_not_bucket_ts():
    assert "ORDER BY fp.created_at ASC" in MATERIALIZE_DELIVERIES_SQL


def test_materialize_sql_has_on_conflict_do_nothing():
    assert "ON CONFLICT" in MATERIALIZE_DELIVERIES_SQL
    assert "DO NOTHING" in MATERIALIZE_DELIVERIES_SQL


def test_notifier_state_insert_has_on_conflict_do_nothing():
    assert "ON CONFLICT" in NOTIFIER_STATE_INSERT_SQL
    assert "DO NOTHING" in NOTIFIER_STATE_INSERT_SQL


def test_pending_sql_filters_unsent_and_due():
    assert "d.sent_at IS NULL" in PENDING_DELIVERIES_SQL
    assert "d.next_attempt_at <= $3" in PENDING_DELIVERIES_SQL


def test_pending_sql_deterministic_order():
    assert "ORDER BY d.next_attempt_at ASC, d.bucket_ts ASC" in PENDING_DELIVERIES_SQL


def test_schema_state_sql_uses_to_regclass_gating():
    assert "to_regclass" in TELEGRAM_SCHEMA_STATE_SQL


# ============================================================================
# B. validators
# ============================================================================
def test_validate_notifier_scope_accepts_valid():
    validate_notifier_scope(runner_name="telegram_forecast_v1", channel="telegram",
                            recipient_fingerprint=FP)


@pytest.mark.parametrize("bad_fp", ["", "short", "A" * 64, "g" * 64, "a" * 63, 12345])
def test_validate_notifier_scope_rejects_bad_fingerprint(bad_fp):
    with pytest.raises(TelegramNotificationReaderError):
        validate_notifier_scope(runner_name="r", channel="telegram", recipient_fingerprint=bad_fp)


def test_validate_notifier_scope_rejects_blank_runner_name():
    with pytest.raises(TelegramNotificationReaderError):
        validate_notifier_scope(runner_name="", channel="telegram", recipient_fingerprint=FP)


def test_validate_recipient_scope_accepts_valid():
    validate_recipient_scope(channel="telegram", recipient_fingerprint=FP)


def test_validate_recipient_scope_rejects_blank_channel():
    with pytest.raises(TelegramNotificationReaderError):
        validate_recipient_scope(channel="", recipient_fingerprint=FP)


# ============================================================================
# C. bootstrap
# ============================================================================
def test_read_notifier_started_at_returns_none_when_absent():
    conn = FakeConn(fetchval_map={NOTIFIER_STATE_SELECT_SQL: None})
    result = _run(read_notifier_started_at(
        conn, runner_name="telegram_forecast_v1", channel="telegram", recipient_fingerprint=FP))
    assert result is None


def test_read_notifier_started_at_returns_existing_value():
    conn = FakeConn(fetchval_map={NOTIFIER_STATE_SELECT_SQL: B})
    result = _run(read_notifier_started_at(
        conn, runner_name="telegram_forecast_v1", channel="telegram", recipient_fingerprint=FP))
    assert result == B


def test_ensure_notifier_started_at_fresh_bootstrap_inserts_then_rereads():
    calls = {"n": 0}

    def select_side_effect(args):
        calls["n"] += 1
        return None if calls["n"] == 1 else B

    conn = FakeConn(fetchval_map={NOTIFIER_STATE_SELECT_SQL: select_side_effect})
    started_at, bootstrapped = _run(ensure_notifier_started_at(
        conn, runner_name="telegram_forecast_v1", channel="telegram",
        recipient_fingerprint=FP, now=B))
    assert bootstrapped is True
    assert started_at == B
    assert len(conn.execute_calls) == 1
    assert conn.execute_calls[0][0] == NOTIFIER_STATE_INSERT_SQL


def test_ensure_notifier_started_at_already_initialized_never_inserts():
    conn = FakeConn(fetchval_map={NOTIFIER_STATE_SELECT_SQL: B})
    started_at, bootstrapped = _run(ensure_notifier_started_at(
        conn, runner_name="telegram_forecast_v1", channel="telegram",
        recipient_fingerprint=FP, now=B + timedelta(hours=1)))
    assert bootstrapped is False
    assert started_at == B
    assert conn.execute_calls == []


def test_ensure_notifier_started_at_rejects_naive_now():
    conn = FakeConn(fetchval_map={NOTIFIER_STATE_SELECT_SQL: None})
    with pytest.raises(TelegramNotificationReaderError):
        _run(ensure_notifier_started_at(
            conn, runner_name="telegram_forecast_v1", channel="telegram",
            recipient_fingerprint=FP, now=datetime(2026, 3, 1)))


# ============================================================================
# D. materialization
# ============================================================================
def test_materialize_parses_insert_command_tag_count():
    conn = FakeConn(execute_map={MATERIALIZE_DELIVERIES_SQL: "INSERT 0 3"})
    count = _run(materialize_telegram_deliveries(
        conn, channel="telegram", recipient_fingerprint=FP, symbol="BTCUSDT",
        market_type="perp", timeframe="5m", started_at=B, limit=200))
    assert count == 3


def test_materialize_zero_rows_returns_zero():
    conn = FakeConn(execute_map={MATERIALIZE_DELIVERIES_SQL: "INSERT 0 0"})
    count = _run(materialize_telegram_deliveries(
        conn, channel="telegram", recipient_fingerprint=FP, symbol="BTCUSDT",
        market_type="perp", timeframe="5m", started_at=B, limit=200))
    assert count == 0


def test_materialize_passes_bound_limit():
    conn = FakeConn(execute_map={MATERIALIZE_DELIVERIES_SQL: "INSERT 0 1"})
    _run(materialize_telegram_deliveries(
        conn, channel="telegram", recipient_fingerprint=FP, symbol="BTCUSDT",
        market_type="perp", timeframe="5m", started_at=B, limit=200))
    sql, args = conn.execute_calls[0]
    assert args[-1] == 200


@pytest.mark.parametrize("limit", [0, -1, 100001, 1.5, True])
def test_materialize_rejects_invalid_limit(limit):
    conn = FakeConn()
    with pytest.raises(TelegramNotificationReaderError):
        _run(materialize_telegram_deliveries(
            conn, channel="telegram", recipient_fingerprint=FP, symbol="BTCUSDT",
            market_type="perp", timeframe="5m", started_at=B, limit=limit))


def test_materialize_rejects_naive_started_at():
    conn = FakeConn()
    with pytest.raises(TelegramNotificationReaderError):
        _run(materialize_telegram_deliveries(
            conn, channel="telegram", recipient_fingerprint=FP, symbol="BTCUSDT",
            market_type="perp", timeframe="5m", started_at=datetime(2026, 3, 1), limit=200))


# ============================================================================
# E. pending discovery
# ============================================================================
def test_read_pending_deliveries_detaches_and_parses_jsonb():
    conn = FakeConn(fetch_map={PENDING_DELIVERIES_SQL: [_rec(_pending_row_dict())]})
    rows = _run(read_pending_telegram_deliveries(
        conn, channel="telegram", recipient_fingerprint=FP, now=B, limit=20))
    assert len(rows) == 1
    row = rows[0]
    assert row["horizon_set"] == ["15m", "1h"]
    assert row["reasons"] == ["a", "b"]
    assert isinstance(row, MappingProxyType)


def test_read_pending_deliveries_empty_when_none_due():
    conn = FakeConn(fetch_map={PENDING_DELIVERIES_SQL: []})
    rows = _run(read_pending_telegram_deliveries(
        conn, channel="telegram", recipient_fingerprint=FP, now=B, limit=20))
    assert rows == ()


def test_read_pending_deliveries_passes_through_args_in_order():
    conn = FakeConn(fetch_map={PENDING_DELIVERIES_SQL: []})
    _run(read_pending_telegram_deliveries(
        conn, channel="telegram", recipient_fingerprint=FP, now=B, limit=20))
    sql, args = conn.fetch_calls[0]
    assert args == ("telegram", FP, B, 20)


def test_read_pending_deliveries_rejects_bad_limit():
    conn = FakeConn()
    with pytest.raises(TelegramNotificationReaderError):
        _run(read_pending_telegram_deliveries(
            conn, channel="telegram", recipient_fingerprint=FP, now=B, limit=0))


def test_parse_jsonb_accepts_already_parsed_list():
    row = _pending_row_dict()
    row["horizon_set"] = ["15m"]   # already a python list (driver-dependent)
    conn = FakeConn(fetch_map={PENDING_DELIVERIES_SQL: [_rec(row)]})
    rows = _run(read_pending_telegram_deliveries(
        conn, channel="telegram", recipient_fingerprint=FP, now=B, limit=20))
    assert rows[0]["horizon_set"] == ["15m"]


def test_parse_jsonb_rejects_unexpected_type():
    row = _pending_row_dict()
    row["horizon_set"] = 12345
    conn = FakeConn(fetch_map={PENDING_DELIVERIES_SQL: [_rec(row)]})
    with pytest.raises(TelegramNotificationReaderError):
        _run(read_pending_telegram_deliveries(
            conn, channel="telegram", recipient_fingerprint=FP, now=B, limit=20))


# ============================================================================
# F. attempt bookkeeping
# ============================================================================
def _identity_kwargs():
    return dict(channel="telegram", recipient_fingerprint=FP, symbol="BTCUSDT",
                market_type="perp", timeframe="5m", bucket_ts=B,
                calculation_version="c" * 16, rule_version="r1")


def test_record_attempt_start_returns_incremented_count():
    conn = FakeConn(fetchval_map={RECORD_ATTEMPT_START_SQL: 1})
    result = _run(record_delivery_attempt_start(conn, **_identity_kwargs()))
    assert result == 1
    assert conn.fetchval_calls[0][0] == RECORD_ATTEMPT_START_SQL


def test_record_sent_executes_with_message_id():
    conn = FakeConn()
    _run(record_delivery_sent(conn, **_identity_kwargs(), telegram_message_id=555))
    sql, args = conn.execute_calls[0]
    assert sql == RECORD_SENT_SQL
    assert args[-1] == 555


def test_record_sent_rejects_non_int_message_id():
    conn = FakeConn()
    with pytest.raises(TelegramNotificationReaderError):
        _run(record_delivery_sent(conn, **_identity_kwargs(), telegram_message_id="555"))


def test_record_failure_executes_with_next_attempt_and_error():
    conn = FakeConn()
    _run(record_delivery_failure(
        conn, **_identity_kwargs(), next_attempt_at=B + timedelta(seconds=60),
        error_class="TelegramSendError", error_summary="boom"))
    sql, args = conn.execute_calls[0]
    assert sql == RECORD_FAILURE_SQL
    assert args[-3] == B + timedelta(seconds=60)
    assert args[-2] == "TelegramSendError"
    assert args[-1] == "boom"


def test_record_failure_rejects_naive_next_attempt_at():
    conn = FakeConn()
    with pytest.raises(TelegramNotificationReaderError):
        _run(record_delivery_failure(
            conn, **_identity_kwargs(), next_attempt_at=datetime(2026, 3, 1),
            error_class="X", error_summary="y"))


def test_record_failure_rejects_blank_error_class():
    conn = FakeConn()
    with pytest.raises(TelegramNotificationReaderError):
        _run(record_delivery_failure(
            conn, **_identity_kwargs(), next_attempt_at=B, error_class="", error_summary="y"))


# ============================================================================
# G. status / schema-state (read-only)
# ============================================================================
def test_read_telegram_schema_state_both_present():
    conn = FakeConn(fetchrow_map={TELEGRAM_SCHEMA_STATE_SQL: lambda a: _rec({
        "telegram_notifier_state": "telegram_notifier_state",
        "telegram_notification_deliveries": "telegram_notification_deliveries"})})
    state = _run(read_telegram_schema_state(conn))
    assert state["telegram_notifier_state"] is True
    assert state["telegram_notification_deliveries"] is True


def test_read_telegram_schema_state_missing_table_reports_false():
    conn = FakeConn(fetchrow_map={TELEGRAM_SCHEMA_STATE_SQL: lambda a: _rec({
        "telegram_notifier_state": None,
        "telegram_notification_deliveries": "telegram_notification_deliveries"})})
    state = _run(read_telegram_schema_state(conn))
    assert state["telegram_notifier_state"] is False
    assert state["telegram_notification_deliveries"] is True


def test_read_notifier_status_aggregate_shape():
    conn = FakeConn(fetchrow_map={NOTIFIER_STATUS_AGGREGATE_SQL: lambda a: _rec({
        "total_pending": 2, "due_pending": 1, "total_sent": 5,
        "last_sent_at": B, "earliest_next_attempt_at": B + timedelta(seconds=60)})})
    agg = _run(read_notifier_status_aggregate(
        conn, channel="telegram", recipient_fingerprint=FP, now=B))
    assert agg["total_pending"] == 2
    assert agg["due_pending"] == 1
    assert agg["total_sent"] == 5
    assert agg["last_sent_at"] == B
    assert agg["earliest_next_attempt_at"] == B + timedelta(seconds=60)


def test_status_aggregate_sql_uses_filter_clauses():
    assert "FILTER (WHERE sent_at IS NULL)" in NOTIFIER_STATUS_AGGREGATE_SQL
    assert "FILTER (WHERE sent_at IS NOT NULL)" in NOTIFIER_STATUS_AGGREGATE_SQL
