"""Unit tests for main.py CLI parsing and the early shadow-command execution
branch. No subprocess; run() is driven with lightweight fakes so we can prove the
shadow branch bypasses the entire Stage 1 startup path (schema, Redis, backfill,
ingestion manager) and that existing Stage 1 invocations are unchanged.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from types import MappingProxyType

import pytest

import main


def _run(coro):
    return asyncio.run(coro)


class _isolate_root_logging:
    """Context manager that clears root logging handlers (so main's basicConfig
    actually attaches a fresh stdout handler bound to the capsys stream) and
    restores the original handlers afterwards."""

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
    ("--shadow-once", "shadow_once"),
    ("--shadow-dry-run", "shadow_dry_run"),
    ("--shadow-status", "shadow_status"),
])
def test_three_commands_recognized(flag, attr):
    args = main.parse_args([flag])
    assert getattr(args, attr) is True
    assert main.is_shadow_command(args) is True


@pytest.mark.parametrize("combo", [
    ["--shadow-once", "--shadow-dry-run"],
    ["--shadow-once", "--shadow-status"],
    ["--shadow-dry-run", "--shadow-status"],
])
def test_mutual_exclusion(combo):
    with pytest.raises(SystemExit):
        main.parse_args(combo)


@pytest.mark.parametrize("combo", [
    ["--shadow-once", "--validate"],
    ["--shadow-dry-run", "--backfill-only"],
    ["--shadow-status", "--skip-backfill"],
])
def test_incompatible_stage1_flags_rejected(combo):
    with pytest.raises(SystemExit):
        main.parse_args(combo)


@pytest.mark.parametrize("combo", [
    ["--shadow-bucket-ts", "2026-07-24T05:00:00Z"],
    ["--shadow-reference-exchange", "bybit"],
    ["--shadow-code-version", "x"],
    ["--shadow-json"],
])
def test_shadow_only_options_rejected_without_command(combo):
    with pytest.raises(SystemExit):
        main.parse_args(combo)


@pytest.mark.parametrize("cmd", ["--shadow-once", "--shadow-dry-run"])
def test_shadow_value_options_valid_with_execution_commands(cmd):
    args = main.parse_args([cmd, "--shadow-bucket-ts", "2026-07-24T05:00:00Z",
                            "--shadow-reference-exchange", "bybit",
                            "--shadow-code-version", "v", "--shadow-json"])
    assert args.shadow_bucket_ts == "2026-07-24T05:00:00Z"
    assert args.shadow_reference_exchange == "bybit"
    assert args.shadow_code_version == "v" and args.shadow_json is True


def test_shadow_json_valid_with_status():
    args = main.parse_args(["--shadow-status", "--shadow-json"])
    assert args.shadow_json is True


def test_reference_default_binance():
    # Not supplied -> namespace None; run_shadow_cli_command normalizes to binance.
    args = main.parse_args(["--shadow-once"])
    assert args.shadow_reference_exchange is None
    assert (args.shadow_reference_exchange or "binance") == "binance"


def test_log_level_still_works():
    assert main.parse_args(["--log-level", "DEBUG"]).log_level == "DEBUG"
    assert main.parse_args([]).log_level == "INFO"


def test_existing_stage1_flags_unchanged():
    assert main.parse_args([]).validate is False
    assert main.parse_args(["--validate"]).validate is True
    assert main.parse_args(["--backfill-only"]).backfill_only is True
    assert main.parse_args(["--skip-backfill"]).skip_backfill is True
    for a in (main.parse_args([]), main.parse_args(["--validate"]),
              main.parse_args(["--backfill-only"]), main.parse_args(["--skip-backfill"])):
        assert main.is_shadow_command(a) is False


# ============================================================================
# execution branching
# ============================================================================
class _FakeCfg:
    symbol = "BTCUSDT"
    enabled_exchanges = ["binance", "bybit", "okx"]

    def __getitem__(self, key):
        return {"backfill": {"window_days": 1}}[key]


class _Sentinel:
    """Records instantiation; any attribute access is a call the shadow path must
    not make."""
    instances = 0

    def __init__(self, *a, **k):
        type(self).instances += 1


def _patch_common(monkeypatch):
    monkeypatch.setattr(main.Config, "load", staticmethod(lambda: _FakeCfg()))
    monkeypatch.setattr(main, "load_secrets",
                        lambda cfg: type("S", (), {"postgres_dsn": "postgresql://x",
                                                   "redis_url": "redis://x",
                                                   "telegram_token": None,
                                                   "telegram_chat_id": None})())


def test_shadow_command_branches_before_stage1(monkeypatch):
    _patch_common(monkeypatch)
    spy = {"n": 0, "args": None}

    async def fake_shadow(args, cfg, secrets):
        spy["n"] += 1
        spy["args"] = args

    monkeypatch.setattr(main, "run_shadow_cli_command", fake_shadow)

    # Any Stage 1 construction must NOT happen on the shadow path.
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
        raise AssertionError("backfill must not run on the shadow path")

    monkeypatch.setattr(main, "run_backfill", _boom_backfill)
    monkeypatch.setattr(main, "run_gap_fill", _boom_backfill)

    _run(main.run(main.parse_args(["--shadow-status"])))
    assert spy["n"] == 1
    assert _DB.instances == 0 and _Redis.instances == 0 and _Mgr.instances == 0


def test_normal_backfill_only_follows_stage1(monkeypatch):
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

    def _shadow_forbidden(*a, **k):
        raise AssertionError("run_shadow_cli_command must not run for a normal invocation")

    monkeypatch.setattr(main, "Database", _DB)
    monkeypatch.setattr(main, "RedisState", _Redis)
    monkeypatch.setattr(main, "run_backfill", _backfill)
    monkeypatch.setattr(main, "run_shadow_cli_command", _shadow_forbidden)
    monkeypatch.setattr(main, "IngestionManager",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("manager must not start for --backfill-only")))

    _run(main.run(main.parse_args(["--backfill-only"])))
    assert "init_schema" in events          # Stage 1 startup ran
    assert "backfill" in events
    assert "close" in events                # clean shutdown


def test_validate_follows_existing_path(monkeypatch):
    _patch_common(monkeypatch)
    events = []

    class _DB:
        def __init__(self, dsn): pass
        async def connect(self): events.append("connect")
        async def init_schema(self): events.append("init_schema")
        async def seed_capabilities(self, rows, enabled_exchanges=None): pass
        async def cancel_stale_backfill_runs(self): return "UPDATE 0"
        async def close(self): events.append("close")

    class _Redis:
        def __init__(self, url): pass
        async def connect(self): pass
        async def close(self): pass

    async def _validate(db, cfg, redis=None):
        events.append("validate")

    def _shadow_forbidden(*a, **k):
        raise AssertionError("shadow path must not run for --validate")

    monkeypatch.setattr(main, "Database", _DB)
    monkeypatch.setattr(main, "RedisState", _Redis)
    monkeypatch.setattr(main, "validate_ingestion", _validate)
    monkeypatch.setattr(main, "run_shadow_cli_command", _shadow_forbidden)

    _run(main.run(main.parse_args(["--validate"])))
    assert events.count("validate") == 1
    assert "init_schema" in events


# ============================================================================
# --shadow-json: stdout is exactly one machine-valid JSON object; logs -> stderr
# ============================================================================
def _patch_config_only(monkeypatch):
    monkeypatch.setattr(main.Config, "load", staticmethod(lambda: _FakeCfg()))
    monkeypatch.setattr(main, "load_secrets",
                        lambda cfg: type("S", (), {"postgres_dsn": "postgresql://secret",
                                                   "redis_url": "redis://secret",
                                                   "telegram_token": None,
                                                   "telegram_chat_id": None})())


@pytest.mark.parametrize("cmd", ["--shadow-once", "--shadow-dry-run", "--shadow-status"])
def test_shadow_json_stdout_is_single_json_object(monkeypatch, capsys, cmd):
    _patch_config_only(monkeypatch)

    async def fake_shadow(args, cfg, secrets):
        # a real diagnostic INFO log emitted during async execution
        logging.getLogger("main").info("Connected to TimescaleDB")
        print(json.dumps({"command": cmd, "state": "NOT_INITIALIZED"}))

    monkeypatch.setattr(main, "run_shadow_cli_command", fake_shadow)
    monkeypatch.setattr(sys, "argv", ["main.py", cmd, "--shadow-json"])

    with _isolate_root_logging():
        main.main()                          # real logging setup + stdout/stderr routing
    out, err = capsys.readouterr()

    # stdout: exactly one JSON object, no log prefix
    parsed = json.loads(out)                 # succeeds -> machine-valid
    assert isinstance(parsed, dict) and parsed["command"] == cmd
    assert out.strip().count("\n") == 0      # a single JSON value (one line)
    assert "| INFO" not in out and "Connected to TimescaleDB" not in out

    # the INFO diagnostic went to stderr, and no secret is on stdout
    assert "Connected to TimescaleDB" in err
    for secret in ("postgresql://", "redis://", "secret"):
        assert secret not in out


def test_shadow_json_full_cli_path_status_smoke(monkeypatch, capsys):
    """Faithful section-F smoke: the REAL run_shadow_cli_command +
    execute_shadow_status + renderer + print run over a fake Database, with
    logging enabled — proving the complete CLI stdout is directly json.loads-able."""
    _patch_config_only(monkeypatch)

    class _FakeStatusDB:
        def __init__(self, dsn):
            pass

        async def connect(self):
            logging.getLogger("storage.db").info("Connected to TimescaleDB")

        async def close(self):
            pass

        async def fetch_shadow_status(self, *, exchanges, symbol, market_type, timeframe):
            return MappingProxyType({"state": "NOT_INITIALIZED", "prerequisites": (),
                                     "latest_prediction": None, "outcomes": ()})

    import runtime.shadow_cli as sc
    monkeypatch.setattr(sc, "Database", _FakeStatusDB)
    monkeypatch.setattr(sys, "argv", ["main.py", "--shadow-status", "--shadow-json"])

    with _isolate_root_logging():
        main.main()
    out, err = capsys.readouterr()

    parsed = json.loads(out)                 # the complete CLI path emitted valid JSON
    assert parsed["state"] == "NOT_INITIALIZED"
    assert parsed["symbol"] == "BTCUSDT"
    assert "Connected to TimescaleDB" in err and "Connected to TimescaleDB" not in out


def test_human_shadow_logging_unchanged(monkeypatch, capsys):
    """A human (non-JSON) shadow command keeps logging on stdout (unchanged)."""
    _patch_config_only(monkeypatch)

    async def fake_shadow(args, cfg, secrets):
        logging.getLogger("main").info("diagnostic-line")
        print("=== SHADOW STATUS ===")

    monkeypatch.setattr(main, "run_shadow_cli_command", fake_shadow)
    monkeypatch.setattr(sys, "argv", ["main.py", "--shadow-status"])

    with _isolate_root_logging():
        main.main()
    out, err = capsys.readouterr()
    assert "=== SHADOW STATUS ===" in out
    assert "diagnostic-line" in out          # human command: logs stay on stdout
    assert "diagnostic-line" not in err


def test_configure_cli_logging_redirects_only_for_json(capsys):
    """Routing logic: --shadow-json redirects the stdout handler to stderr;
    every other invocation leaves normal stdout logging in place."""
    with _isolate_root_logging():
        root = logging.getLogger()

        main.configure_cli_logging(main.parse_args([]))          # normal Stage 1
        stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
        assert stream_handlers and all(h.stream is sys.stdout for h in stream_handlers)

        root.handlers.clear()
        main.configure_cli_logging(main.parse_args(["--shadow-status", "--shadow-json"]))
        stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
        assert stream_handlers
        assert all(h.stream is not sys.stdout for h in stream_handlers)
        assert any(h.stream is sys.stderr for h in stream_handlers)
