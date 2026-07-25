"""Unit tests for main.py CLI parsing and the early telegram-command execution
branch. No subprocess; run() is driven with lightweight fakes so we can prove
the telegram branch bypasses the entire Stage 1 startup path (schema, Redis,
backfill, ingestion manager), is mutually exclusive with the shadow branch, and
that omitted/explicit operational caps behave correctly end-to-end.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys

import pytest

import main


def _run(coro):
    return asyncio.run(coro)


class _isolate_root_logging:
    def __enter__(self):
        self._root = logging.getLogger()
        self._saved = self._root.handlers[:]
        self._root.handlers.clear()
        return self

    def __exit__(self, *exc):
        self._root.handlers[:] = self._saved
        return False


# ============================================================================
# parser behavior
# ============================================================================
@pytest.mark.parametrize("flag,attr", [
    ("--telegram-once", "telegram_once"),
    ("--telegram-status", "telegram_status"),
    ("--telegram-test", "telegram_test"),
])
def test_three_commands_recognized(flag, attr):
    args = main.parse_args([flag])
    assert getattr(args, attr) is True
    from runtime.telegram_cli import is_telegram_command
    assert is_telegram_command(args) is True


@pytest.mark.parametrize("combo", [
    ["--telegram-once", "--telegram-status"],
    ["--telegram-once", "--telegram-test"],
    ["--telegram-status", "--telegram-test"],
])
def test_mutual_exclusion(combo):
    with pytest.raises(SystemExit):
        main.parse_args(combo)


@pytest.mark.parametrize("combo", [
    ["--telegram-once", "--validate"],
    ["--telegram-status", "--backfill-only"],
    ["--telegram-test", "--skip-backfill"],
])
def test_incompatible_stage1_flags_rejected(combo):
    with pytest.raises(SystemExit):
        main.parse_args(combo)


@pytest.mark.parametrize("combo", [
    ["--telegram-once", "--shadow-status"],
    ["--telegram-status", "--shadow-once"],
    ["--shadow-dry-run", "--telegram-test"],
])
def test_telegram_and_shadow_commands_mutually_exclusive(combo):
    with pytest.raises(SystemExit):
        main.parse_args(combo)


@pytest.mark.parametrize("combo", [
    ["--telegram-json"],                                  # no command at all
    ["--telegram-max-scan", "50"],                         # no --telegram-once
    ["--telegram-max-send", "5"],                          # no --telegram-once
    ["--telegram-status", "--telegram-max-scan", "50"],    # wrong command
    ["--telegram-test", "--telegram-max-send", "5"],       # wrong command
])
def test_telegram_only_options_rejected_without_correct_command(combo):
    with pytest.raises(SystemExit):
        main.parse_args(combo)


def test_telegram_json_valid_with_each_command():
    for cmd in ("--telegram-once", "--telegram-status", "--telegram-test"):
        args = main.parse_args([cmd, "--telegram-json"])
        assert args.telegram_json is True


def test_caps_valid_with_telegram_once():
    args = main.parse_args(["--telegram-once", "--telegram-max-scan", "50",
                            "--telegram-max-send", "5", "--telegram-json"])
    assert args.telegram_max_scan == 50
    assert args.telegram_max_send == 5
    assert args.telegram_json is True


def test_caps_default_to_none_when_omitted():
    args = main.parse_args(["--telegram-once"])
    assert args.telegram_max_scan is None
    assert args.telegram_max_send is None


def test_explicit_zero_parses_at_argparse_level_deferred_to_runtime_check():
    # argparse itself accepts an int 0 — rejection of the explicit 0 happens in
    # validate_operational_cap (an `is None` check, never `value or default`).
    args = main.parse_args(["--telegram-once", "--telegram-max-scan", "0"])
    assert args.telegram_max_scan == 0


def test_log_level_still_works_for_telegram_commands():
    args = main.parse_args(["--telegram-once", "--log-level", "DEBUG"])
    assert args.log_level == "DEBUG"


def test_existing_stage1_flags_unaffected():
    from runtime.telegram_cli import is_telegram_command
    assert main.parse_args([]).validate is False
    for a in (main.parse_args([]), main.parse_args(["--validate"]),
              main.parse_args(["--backfill-only"]), main.parse_args(["--skip-backfill"])):
        assert is_telegram_command(a) is False


# ============================================================================
# execution branching
# ============================================================================
class _FakeCfg:
    symbol = "BTCUSDT"
    enabled_exchanges = ["binance", "bybit", "okx"]

    def __getitem__(self, key):
        return {"backfill": {"window_days": 1}}[key]


class _Sentinel:
    instances = 0

    def __init__(self, *a, **k):
        type(self).instances += 1


def _fake_secrets():
    return type("S", (), {"postgres_dsn": "postgresql://x", "redis_url": "redis://x",
                          "telegram_token": "123456:ABC", "telegram_chat_id": "12345"})()


def _patch_common(monkeypatch):
    monkeypatch.setattr(main.Config, "load", staticmethod(lambda: _FakeCfg()))
    monkeypatch.setattr(main, "load_secrets", lambda cfg: _fake_secrets())


def test_telegram_command_branches_before_stage1(monkeypatch):
    _patch_common(monkeypatch)
    spy = {"n": 0}

    async def fake_telegram(args, cfg, secrets):
        spy["n"] += 1

    monkeypatch.setattr(main, "run_telegram_cli_command", fake_telegram)

    class _DB(_Sentinel):
        pass

    class _Redis(_Sentinel):
        pass

    class _Mgr(_Sentinel):
        pass

    _DB.instances = _Redis.instances = _Mgr.instances = 0
    monkeypatch.setattr(main, "Database", _DB)
    monkeypatch.setattr(main, "RedisState", _Redis)
    monkeypatch.setattr(main, "IngestionManager", _Mgr)

    async def _boom_backfill(*a, **k):
        raise AssertionError("backfill must not run on the telegram path")

    monkeypatch.setattr(main, "run_backfill", _boom_backfill)
    monkeypatch.setattr(main, "run_gap_fill", _boom_backfill)

    _run(main.run(main.parse_args(["--telegram-status"])))
    assert spy["n"] == 1
    assert _DB.instances == 0 and _Redis.instances == 0 and _Mgr.instances == 0


def test_normal_backfill_only_does_not_dispatch_to_telegram(monkeypatch):
    _patch_common(monkeypatch)
    events = []

    class _DB:
        def __init__(self, dsn):
            events.append("db_init")

        async def connect(self):
            events.append("connect")

        async def init_schema(self):
            events.append("init_schema")

        async def seed_capabilities(self, rows, enabled_exchanges=None):
            events.append("seed_caps")

        async def cancel_stale_backfill_runs(self):
            events.append("sweep")
            return "UPDATE 0"

        async def close(self):
            events.append("close")

    class _Redis:
        def __init__(self, url):
            events.append("redis_init")

        async def connect(self):
            events.append("redis_connect")

        async def close(self):
            events.append("redis_close")

    async def _backfill(*a, **k):
        events.append("backfill")

    def _telegram_forbidden(*a, **k):
        raise AssertionError("run_telegram_cli_command must not run for a normal invocation")

    monkeypatch.setattr(main, "Database", _DB)
    monkeypatch.setattr(main, "RedisState", _Redis)
    monkeypatch.setattr(main, "run_backfill", _backfill)
    monkeypatch.setattr(main, "run_telegram_cli_command", _telegram_forbidden)
    monkeypatch.setattr(main, "IngestionManager",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("manager must not start for --backfill-only")))

    _run(main.run(main.parse_args(["--backfill-only"])))
    assert "init_schema" in events
    assert "backfill" in events
    assert "close" in events


def test_shadow_command_does_not_dispatch_to_telegram(monkeypatch):
    _patch_common(monkeypatch)

    async def fake_shadow(args, cfg, secrets):
        pass

    def _telegram_forbidden(*a, **k):
        raise AssertionError("run_telegram_cli_command must not run for a shadow invocation")

    monkeypatch.setattr(main, "run_shadow_cli_command", fake_shadow)
    monkeypatch.setattr(main, "run_telegram_cli_command", _telegram_forbidden)

    _run(main.run(main.parse_args(["--shadow-status"])))


# ============================================================================
# --telegram-json: stdout is exactly one machine-valid JSON object
# ============================================================================
@pytest.mark.parametrize("cmd", ["--telegram-once", "--telegram-status", "--telegram-test"])
def test_telegram_json_stdout_is_single_json_object(monkeypatch, capsys, cmd):
    _patch_common(monkeypatch)

    async def fake_telegram(args, cfg, secrets):
        logging.getLogger("main").info("Connected to TimescaleDB")
        print(json.dumps({"command": cmd, "state": "READY"}))

    monkeypatch.setattr(main, "run_telegram_cli_command", fake_telegram)
    monkeypatch.setattr(sys, "argv", ["main.py", cmd, "--telegram-json"])

    with _isolate_root_logging():
        main.main()
    out, err = capsys.readouterr()

    parsed = json.loads(out)
    assert isinstance(parsed, dict) and parsed["command"] == cmd
    assert out.strip().count("\n") == 0
    assert "Connected to TimescaleDB" not in out
    assert "Connected to TimescaleDB" in err
    for secret in ("postgresql://", "redis://", "123456:ABC"):
        assert secret not in out


def test_human_telegram_logging_unchanged(monkeypatch, capsys):
    _patch_common(monkeypatch)

    async def fake_telegram(args, cfg, secrets):
        logging.getLogger("main").info("diagnostic-line")
        print("=== TELEGRAM STATUS ===")

    monkeypatch.setattr(main, "run_telegram_cli_command", fake_telegram)
    monkeypatch.setattr(sys, "argv", ["main.py", "--telegram-status"])

    with _isolate_root_logging():
        main.main()
    out, err = capsys.readouterr()
    assert "=== TELEGRAM STATUS ===" in out
    assert "diagnostic-line" in out
    assert "diagnostic-line" not in err


def test_configure_cli_logging_redirects_for_telegram_json(capsys):
    with _isolate_root_logging():
        root = logging.getLogger()

        main.configure_cli_logging(main.parse_args(["--telegram-status", "--telegram-json"]))
        stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
        assert stream_handlers
        assert all(h.stream is not sys.stdout for h in stream_handlers)
        assert any(h.stream is sys.stderr for h in stream_handlers)


# ============================================================================
# end-to-end: omitted caps use defaults; explicit caps pass through unchanged
# ============================================================================
class _NoOpDB:
    """Only connect/close implemented — proves cap validation happens before
    any Database method (lock/schema/etc.) is reached."""

    def __init__(self, dsn):
        pass

    async def connect(self):
        pass

    async def close(self):
        pass


def test_omitted_caps_use_defaults_end_to_end(monkeypatch):
    import runtime.telegram_cli as tc
    seen = {}

    async def fake_execute(db, cfg, secrets, *, now, max_scan=None, max_send=None, telegram_sender=None):
        seen["max_scan"] = max_scan
        seen["max_send"] = max_send
        raise tc.TelegramCliError("stop before any DB work")

    monkeypatch.setattr(tc, "execute_telegram_once", fake_execute)
    monkeypatch.setattr(tc, "Database", _NoOpDB)
    args = main.parse_args(["--telegram-once"])
    with pytest.raises(tc.TelegramCliError):
        _run(tc.run_telegram_cli_command(args, _FakeCfg(), _fake_secrets()))
    assert seen == {"max_scan": None, "max_send": None}


def test_explicit_caps_pass_through_unchanged(monkeypatch):
    import runtime.telegram_cli as tc
    seen = {}

    async def fake_execute(db, cfg, secrets, *, now, max_scan=None, max_send=None, telegram_sender=None):
        seen["max_scan"] = max_scan
        seen["max_send"] = max_send
        raise tc.TelegramCliError("stop before any DB work")

    monkeypatch.setattr(tc, "execute_telegram_once", fake_execute)
    monkeypatch.setattr(tc, "Database", _NoOpDB)
    args = main.parse_args(["--telegram-once", "--telegram-max-scan", "1", "--telegram-max-send", "1"])
    with pytest.raises(tc.TelegramCliError):
        _run(tc.run_telegram_cli_command(args, _FakeCfg(), _fake_secrets()))
    assert seen == {"max_scan": 1, "max_send": 1}


def test_explicit_zero_reaches_executor_intact_never_coerced_to_default(monkeypatch):
    import runtime.telegram_cli as tc
    seen = {}

    async def fake_execute(db, cfg, secrets, *, now, max_scan=None, max_send=None, telegram_sender=None):
        seen["max_scan"] = max_scan
        raise tc.TelegramCliError("stop before any DB work")

    monkeypatch.setattr(tc, "execute_telegram_once", fake_execute)
    monkeypatch.setattr(tc, "Database", _NoOpDB)
    args = main.parse_args(["--telegram-once", "--telegram-max-scan", "0"])
    with pytest.raises(tc.TelegramCliError):
        _run(tc.run_telegram_cli_command(args, _FakeCfg(), _fake_secrets()))
    assert seen == {"max_scan": 0}   # explicit 0 reached the executor, not silently replaced


@pytest.mark.parametrize("flag", ["--telegram-max-scan", "--telegram-max-send"])
@pytest.mark.parametrize("value", ["0", "-1", "99999"])
def test_bad_caps_rejected_before_any_db_work(monkeypatch, flag, value):
    import runtime.telegram_cli as tc
    monkeypatch.setattr(tc, "Database", _NoOpDB)
    args = main.parse_args(["--telegram-once", flag, value])
    with pytest.raises(tc.TelegramCliError):
        _run(tc.run_telegram_cli_command(args, _FakeCfg(), _fake_secrets()))
    # _NoOpDB has no lock/schema/etc. methods: reaching any of them would
    # AttributeError instead of TelegramCliError, proving the cap was
    # rejected before any Database work began.
