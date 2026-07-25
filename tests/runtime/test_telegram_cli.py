"""Unit tests for runtime/telegram_cli.py — the operational Telegram notifier
CLI. Fake Database (no real DB/Docker/network) and a fake Telegram sender (no
real network call, no `telegram` package import). Covers: lock behavior, cap
validation, bootstrap/materialize/pending/send/record sequencing, failure
isolation, JSON secret-freedom, read-only status, and isolation from the
shadow-recovery lock namespace.
"""
from __future__ import annotations

import ast
import asyncio
import contextlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType

import pytest

import runtime.telegram_cli as tc
from runtime.shadow_recovery import shadow_recovery_lock_key
from notifications.telegram_client import TelegramSendError, TelegramSendResult
from notifications.telegram_models import compute_recipient_fingerprint

UTC = timezone.utc
B = datetime(2026, 3, 1, tzinfo=UTC)
FP = compute_recipient_fingerprint("12345")
SRC = Path("runtime/telegram_cli.py")


def _run(coro):
    return asyncio.run(coro)


class FakeSecrets:
    telegram_token = "123456:ABC-token"
    telegram_chat_id = "12345"
    postgres_dsn = "postgresql://x"
    redis_url = "redis://x"


class FakeCfg:
    symbol = "BTCUSDT"


class FakeDB:
    def __init__(self, *, lock_free=True, started_at=None, materialized=1,
                 pending_rows=None, schema_present=True):
        self.lock_free = lock_free
        self.started_at = started_at
        self.materialized = materialized
        self.pending_rows = pending_rows if pending_rows is not None else []
        self.schema_present = schema_present
        self.calls: list = []
        self.sent: list = []
        self.failed: list = []
        self.attempt_starts: list = []
        self.lock_keys_seen: list = []

    @contextlib.asynccontextmanager
    async def telegram_notifier_lock(self, key):
        self.calls.append("lock")
        self.lock_keys_seen.append(key)
        try:
            yield self.lock_free
        finally:
            self.calls.append("unlock")

    async def init_stage2_schema(self):
        self.calls.append("init_stage2_schema")

    async def ensure_telegram_notifier_state(self, *, runner_name, channel, recipient_fingerprint, now):
        self.calls.append("bootstrap")
        if self.started_at is None:
            self.started_at = now
            return now, True
        return self.started_at, False

    async def materialize_telegram_deliveries(self, **kw):
        self.calls.append("materialize")
        return self.materialized

    async def fetch_pending_telegram_deliveries(self, **kw):
        self.calls.append("pending")
        return tuple(self.pending_rows)

    async def record_telegram_attempt_start(self, **kw):
        self.attempt_starts.append(kw)
        self.calls.append("attempt_start")
        return len(self.attempt_starts)

    async def record_telegram_sent(self, **kw):
        self.sent.append(kw)
        self.calls.append("sent")

    async def record_telegram_failure(self, **kw):
        self.failed.append(kw)
        self.calls.append("failure")

    async def fetch_telegram_notifier_status(self, **kw):
        self.calls.append("status_agg")
        return MappingProxyType({"total_pending": 0, "due_pending": 0, "total_sent": 1,
                                 "last_sent_at": B, "earliest_next_attempt_at": None})

    async def fetch_telegram_schema_state(self):
        self.calls.append("schema_state")
        present = self.schema_present
        return MappingProxyType({"telegram_notifier_state": present,
                                 "telegram_notification_deliveries": present})

    async def fetch_telegram_notifier_started_at(self, **kw):
        self.calls.append("started_at_read")
        return self.started_at


def _row(bucket_ts=B, direction="LONG"):
    return MappingProxyType({
        "symbol": "BTCUSDT", "market_type": "perp", "timeframe": "5m", "bucket_ts": bucket_ts,
        "calculation_version": "c" * 16, "rule_version": "r1", "attempt_count": 0,
        "direction": direction, "confidence": 0.5, "final_score": 0.4,
        "reference_price": 100.0, "reference_price_source": "binance_close_5m",
        "horizon_set": ["15m", "1h"], "reasons": ["X"], "exchanges_expected_max": 3,
        "min_coverage_ratio": 1.0, "data_confidence_overall": 80.0, "consensus_confidence": 80.0,
        "is_partial_consensus": False, "prediction_created_at": bucket_ts + timedelta(seconds=1)})


class FakeSenderOK:
    def __init__(self):
        self.calls: list = []

    async def send_message(self, *, chat_id, html):
        self.calls.append((chat_id, html))
        return TelegramSendResult(message_id=42)


class FakeSenderFail:
    def __init__(self, retry_after=None):
        self.retry_after = retry_after
        self.calls: list = []

    async def send_message(self, *, chat_id, html):
        self.calls.append((chat_id, html))
        raise TelegramSendError("boom", retry_after=self.retry_after)


class FakeSenderCounting:
    """Fails once then succeeds — used to prove sequential (not concurrent)
    per-delivery handling."""
    def __init__(self):
        self.calls: list = []

    async def send_message(self, *, chat_id, html):
        self.calls.append(html)
        if len(self.calls) == 1:
            raise TelegramSendError("first fails")
        return TelegramSendResult(message_id=len(self.calls))


# ============================================================================
# is_telegram_command
# ============================================================================
class _Args:
    def __init__(self, **kw):
        self.telegram_once = kw.get("telegram_once", False)
        self.telegram_status = kw.get("telegram_status", False)
        self.telegram_test = kw.get("telegram_test", False)


def test_is_telegram_command_true_for_each_flag():
    assert tc.is_telegram_command(_Args(telegram_once=True))
    assert tc.is_telegram_command(_Args(telegram_status=True))
    assert tc.is_telegram_command(_Args(telegram_test=True))


def test_is_telegram_command_false_when_none_set():
    assert not tc.is_telegram_command(_Args())


# ============================================================================
# validate_operational_cap
# ============================================================================
def test_validate_cap_accepts_valid_int():
    assert tc.validate_operational_cap(50, "max_scan", 2000) == 50


@pytest.mark.parametrize("bad", [0, -1, 2001, True, False, 1.5, "50", None])
def test_validate_cap_rejects_invalid(bad):
    with pytest.raises(tc.TelegramCliError):
        tc.validate_operational_cap(bad, "max_scan", 2000)


def test_validate_cap_accepts_upper_bound():
    assert tc.validate_operational_cap(2000, "max_scan", 2000) == 2000


def test_validate_cap_accepts_lower_bound():
    assert tc.validate_operational_cap(1, "max_scan", 2000) == 1


# ============================================================================
# telegram_notifier_lock_key: deterministic + isolated from shadow lock
# ============================================================================
def test_lock_key_deterministic():
    k1 = tc.telegram_notifier_lock_key("telegram_forecast_v1", "telegram", FP)
    k2 = tc.telegram_notifier_lock_key("telegram_forecast_v1", "telegram", FP)
    assert k1 == k2


def test_lock_key_differs_by_recipient():
    k1 = tc.telegram_notifier_lock_key("telegram_forecast_v1", "telegram", FP)
    other_fp = compute_recipient_fingerprint("99999")
    k2 = tc.telegram_notifier_lock_key("telegram_forecast_v1", "telegram", other_fp)
    assert k1 != k2


def test_lock_key_is_signed_int64():
    k = tc.telegram_notifier_lock_key("telegram_forecast_v1", "telegram", FP)
    assert isinstance(k, int)
    assert -(2 ** 63) <= k < 2 ** 63


@pytest.mark.parametrize("bad", ["", "   "])
def test_lock_key_rejects_blank_component(bad):
    with pytest.raises(tc.TelegramCliError):
        tc.telegram_notifier_lock_key(bad, "telegram", FP)


def test_lock_key_never_collides_with_shadow_recovery_lock():
    telegram_key = tc.telegram_notifier_lock_key("telegram_forecast_v1", "telegram", FP)
    shadow_key = shadow_recovery_lock_key("shadow_forecast_v1", "BTCUSDT", "perp", "5m")
    assert telegram_key != shadow_key


def test_lock_key_uses_distinct_separator_from_shadow():
    # \x1e (telegram) vs \x1f (shadow) guarantees no cross-namespace collision
    # even when component strings happen to match across the two subsystems.
    text = SRC.read_text()
    assert '"\\x1e"' in text or "'\\x1e'" in text


# ============================================================================
# hydrate_notification_candidate: fail-closed on malformed rows
# ============================================================================
def test_hydrate_valid_row():
    candidate = tc.hydrate_notification_candidate(_row())
    assert candidate.symbol == "BTCUSDT"
    assert candidate.direction == "LONG"


def test_hydrate_rejects_non_mapping():
    with pytest.raises(tc.TelegramCliError):
        tc.hydrate_notification_candidate(["not", "a", "mapping"])


def test_hydrate_rejects_missing_key():
    row = dict(_row())
    del row["confidence"]
    with pytest.raises(tc.TelegramCliError):
        tc.hydrate_notification_candidate(row)


def test_hydrate_rejects_invalid_direction():
    row = dict(_row())
    row["direction"] = "NEUTRAL"
    with pytest.raises(tc.TelegramCliError):
        tc.hydrate_notification_candidate(row)


def test_hydrate_rejects_out_of_range_confidence():
    row = dict(_row())
    row["confidence"] = 1.5
    with pytest.raises(tc.TelegramCliError):
        tc.hydrate_notification_candidate(row)


# ============================================================================
# execute_telegram_once: lock, bootstrap, materialize, send, record
# ============================================================================
def test_lock_held_skips_all_work_and_reports_zero():
    db = FakeDB(lock_free=False)
    report = _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B))
    assert report.lock_status == tc.LOCK_HELD_SKIPPED
    assert report.writes_enabled is False
    assert report.sent_count == 0
    assert report.materialized_count == 0
    assert "bootstrap" not in db.calls
    assert "materialize" not in db.calls
    assert "pending" not in db.calls


def test_lock_released_on_success():
    db = FakeDB(pending_rows=[_row()])
    _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B, telegram_sender=FakeSenderOK()))
    assert db.calls[0] == "lock"
    assert db.calls[-1] == "unlock" or "unlock" in db.calls


def test_lock_released_on_internal_exception():
    class ExplodingDB(FakeDB):
        async def init_stage2_schema(self):
            raise RuntimeError("boom")

    db = ExplodingDB()
    with pytest.raises(RuntimeError):
        _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B))
    assert "unlock" in db.calls


def test_fresh_bootstrap_reports_bootstrapped_no_history():
    db = FakeDB(pending_rows=[])
    report = _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B))
    assert report.bootstrap_status == tc.BOOTSTRAPPED_NO_HISTORY


def test_already_initialized_reports_already_initialized():
    db = FakeDB(started_at=B - timedelta(days=1), pending_rows=[])
    report = _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B))
    assert report.bootstrap_status == tc.ALREADY_INITIALIZED


def test_successful_send_records_message_id_and_counts():
    db = FakeDB(pending_rows=[_row()])
    sender = FakeSenderOK()
    report = _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B, telegram_sender=sender))
    assert report.lock_status == tc.LOCK_ACQUIRED
    assert report.sent_count == 1
    assert report.failed_count == 0
    assert len(sender.calls) == 1
    assert db.sent[0]["telegram_message_id"] == 42
    assert "LONG" in sender.calls[0][1] and "BTCUSDT" in sender.calls[0][1]


def test_neutral_never_reaches_pending_rows_is_impossible_via_hydration():
    # a NEUTRAL row surfacing in pending_rows must fail closed, never be sent
    db = FakeDB(pending_rows=[_row(direction="NEUTRAL")])
    with pytest.raises(tc.TelegramCliError):
        _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B, telegram_sender=FakeSenderOK()))


def test_failure_path_records_retry_and_does_not_raise():
    db = FakeDB(pending_rows=[_row()])
    report = _run(tc.execute_telegram_once(
        db, FakeCfg(), FakeSecrets(), now=B, telegram_sender=FakeSenderFail(retry_after=30)))
    assert report.sent_count == 0
    assert report.failed_count == 1
    assert len(report.failures) == 1
    assert db.failed[0]["next_attempt_at"] == B + timedelta(seconds=60)   # base 60s > retry_after 30s


def test_failure_does_not_abort_remaining_deliveries():
    rows = [_row(bucket_ts=B), _row(bucket_ts=B + timedelta(minutes=5))]
    db = FakeDB(pending_rows=rows)
    sender = FakeSenderCounting()
    report = _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B, telegram_sender=sender))
    assert report.attempted_count == 2
    assert report.failed_count == 1
    assert report.sent_count == 1


def test_one_send_attempt_per_delivery_per_invocation():
    db = FakeDB(pending_rows=[_row()])
    sender = FakeSenderFail()
    _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B, telegram_sender=sender))
    assert len(sender.calls) == 1   # no in-process retry


def test_sequential_processing_preserves_row_order():
    rows = [_row(bucket_ts=B + timedelta(minutes=i)) for i in range(5)]
    db = FakeDB(pending_rows=rows)
    sender = FakeSenderOK()
    _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B, telegram_sender=sender))
    sent_bucket_order = [kw["bucket_ts"] for kw in db.sent]
    assert sent_bucket_order == [r["bucket_ts"] for r in rows]


def test_caps_validated_before_any_lock_or_write():
    db = FakeDB()
    with pytest.raises(tc.TelegramCliError):
        _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B, max_scan=0))
    assert db.calls == []   # never even attempted the lock


@pytest.mark.parametrize("bad_scan", [0, -1, 2001, True])
def test_execute_once_rejects_bad_max_scan(bad_scan):
    with pytest.raises(tc.TelegramCliError):
        _run(tc.execute_telegram_once(FakeDB(), FakeCfg(), FakeSecrets(), now=B, max_scan=bad_scan))


@pytest.mark.parametrize("bad_send", [0, -1, 101, True])
def test_execute_once_rejects_bad_max_send(bad_send):
    with pytest.raises(tc.TelegramCliError):
        _run(tc.execute_telegram_once(FakeDB(), FakeCfg(), FakeSecrets(), now=B, max_send=bad_send))


def test_missing_token_rejected_before_any_db_call():
    class NoToken(FakeSecrets):
        telegram_token = None
    db = FakeDB()
    with pytest.raises(tc.TelegramCliError):
        _run(tc.execute_telegram_once(db, FakeCfg(), NoToken(), now=B))
    assert db.calls == []


def test_missing_chat_id_rejected_before_any_db_call():
    class NoChatId(FakeSecrets):
        telegram_chat_id = None
    db = FakeDB()
    with pytest.raises(tc.TelegramCliError):
        _run(tc.execute_telegram_once(db, FakeCfg(), NoChatId(), now=B))
    assert db.calls == []


def test_no_candidates_is_a_clean_zero_send_report():
    db = FakeDB(pending_rows=[])
    report = _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B))
    assert report.pending_count == 0
    assert report.sent_count == 0
    assert report.attempted_count == 0


# ============================================================================
# execute_telegram_status: strictly read-only
# ============================================================================
def test_status_not_initialized_when_schema_missing():
    db = FakeDB(schema_present=False)
    status = _run(tc.execute_telegram_status(db, FakeSecrets(), now=B))
    assert status.state == tc.STATUS_NOT_INITIALIZED
    assert status.notifier_initialized is False


def test_status_ready_when_initialized():
    db = FakeDB(started_at=B)
    status = _run(tc.execute_telegram_status(db, FakeSecrets(), now=B))
    assert status.state == tc.STATUS_READY
    assert status.notifier_initialized is True
    assert status.started_at == B


def test_status_never_acquires_lock():
    db = FakeDB(started_at=B)
    _run(tc.execute_telegram_status(db, FakeSecrets(), now=B))
    assert "lock" not in db.calls


def test_status_never_calls_bootstrap_or_materialize_or_send():
    db = FakeDB(schema_present=True, started_at=B)
    _run(tc.execute_telegram_status(db, FakeSecrets(), now=B))
    for forbidden in ("bootstrap", "materialize", "sent", "failure", "attempt_start"):
        assert forbidden not in db.calls


def test_status_rejects_missing_chat_id():
    class NoChatId(FakeSecrets):
        telegram_chat_id = None
    with pytest.raises(tc.TelegramCliError):
        _run(tc.execute_telegram_status(FakeDB(), NoChatId(), now=B))


# ============================================================================
# JSON rendering: no secrets, correct shape
# ============================================================================
def test_execution_report_json_has_no_secrets():
    db = FakeDB(pending_rows=[_row()])
    report = _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B, telegram_sender=FakeSenderOK()))
    js = tc.render_execution_report_json(report)
    assert "123456" not in js
    assert "ABC-token" not in js
    assert "12345" not in js   # raw chat id never appears; only its fingerprint
    parsed = json.loads(js)
    assert parsed["recipient_fingerprint"] == FP


def test_status_report_json_has_no_secrets():
    db = FakeDB(started_at=B)
    status = _run(tc.execute_telegram_status(db, FakeSecrets(), now=B))
    js = tc.render_status_report_json(status)
    assert "123456" not in js
    assert "ABC-token" not in js


def test_execution_report_json_is_deterministic_key_order():
    db = FakeDB(pending_rows=[_row()])
    report = _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B, telegram_sender=FakeSenderOK()))
    js1 = tc.render_execution_report_json(report)
    js2 = tc.render_execution_report_json(report)
    assert js1 == js2


def test_human_render_masks_recipient_fingerprint():
    db = FakeDB(pending_rows=[_row()])
    report = _run(tc.execute_telegram_once(db, FakeCfg(), FakeSecrets(), now=B, telegram_sender=FakeSenderOK()))
    text = tc.render_execution_report(report)
    assert FP not in text            # full fingerprint never printed in human view
    assert FP[:12] in text           # only a short prefix + ellipsis


# ============================================================================
# architecture: no asyncio.gather, no sleep, no top-level DB/network import
# ============================================================================
def test_no_asyncio_gather_in_source():
    text = SRC.read_text()
    assert "asyncio.gather" not in text


def test_no_sleep_in_source():
    text = SRC.read_text()
    assert "time.sleep" not in text
    assert "asyncio.sleep" not in text


def test_no_while_true_background_loop():
    tree = ast.parse(SRC.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            raise AssertionError("runtime/telegram_cli.py must contain no while-loop")


def test_module_never_imports_shadow_cli_or_shadow_recovery_process_path():
    tree = ast.parse(SRC.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not any(m.startswith("runtime.shadow_cli") or m == "runtime.shadow_recovery"
                   for m in imported)
