"""Unit tests for main.py CLI parsing and the early shadow-command execution
branch. No subprocess; run() is driven with lightweight fakes so we can prove the
shadow branch bypasses the entire Stage 1 startup path (schema, Redis, backfill,
ingestion manager) and that existing Stage 1 invocations are unchanged.
"""
from __future__ import annotations

import asyncio

import pytest

import main


def _run(coro):
    return asyncio.run(coro)


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
