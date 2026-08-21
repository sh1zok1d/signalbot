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
                                     "instrument_metadata_revision": None,
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


# ============================================================================
# recovery CLI options + automatic --shadow-once dispatch
# ============================================================================
def test_recovery_caps_valid_with_shadow_once():
    a = main.parse_args(["--shadow-once", "--shadow-max-catchup-buckets", "6",
                         "--shadow-max-outcome-jobs", "50"])
    assert a.shadow_max_catchup_buckets == 6 and a.shadow_max_outcome_jobs == 50


@pytest.mark.parametrize("combo", [
    ["--shadow-max-catchup-buckets", "6"],                       # no command
    ["--shadow-dry-run", "--shadow-max-catchup-buckets", "6"],   # dry-run
    ["--shadow-status", "--shadow-max-outcome-jobs", "5"],       # status
    ["--shadow-once", "--shadow-bucket-ts", "2026-07-24T05:00:00Z",
     "--shadow-max-catchup-buckets", "6"],                       # explicit bucket
])
def test_recovery_caps_rejected_out_of_scope(combo):
    with pytest.raises(SystemExit):
        main.parse_args(combo)


def _recovery_report():
    from datetime import datetime, timezone
    from runtime.shadow_recovery import ShadowRecoveryReport, LOCK_ACQUIRED
    return ShadowRecoveryReport(
        lock_status=LOCK_ACQUIRED, latest_closed_bucket=datetime(2026, 3, 1, tzinfo=timezone.utc),
        recovery_lookback_buckets=288, catchup_truncated_by_lookback=False,
        catchup_truncated_by_cap=False, watermark_before=None, watermark_after=None,
        prediction_buckets_planned=1, prediction_buckets_attempted=1,
        per_bucket_status=(), outcome_jobs_discovered=0, outcome_jobs_attempted=0,
        outcome_evaluations_complete=0, outcome_evaluations_incomplete=0,
        horizons_represented=(), writes_enabled=True, stage2_global_enabled=False,
        reference_exchange="binance", code_version="cli")


def test_automatic_shadow_once_dispatches_to_recovery(monkeypatch, capsys):
    import runtime.shadow_cli as shadow_cli
    import runtime.shadow_recovery as shadow_recovery
    calls = {"recovery": 0, "once": 0}

    async def fake_recovery(*a, **k):
        calls["recovery"] += 1
        return _recovery_report()

    async def fake_once(*a, **k):
        calls["once"] += 1
        raise AssertionError("execute_shadow_once must not run for automatic --shadow-once")

    class _DB:
        def __init__(self, dsn): pass
        async def connect(self): pass
        async def close(self): pass

    monkeypatch.setattr(shadow_recovery, "execute_shadow_recovery", fake_recovery)
    monkeypatch.setattr(shadow_cli, "execute_shadow_once", fake_once)
    monkeypatch.setattr(shadow_cli, "Database", _DB)

    args = main.parse_args(["--shadow-once", "--shadow-json"])
    cfg = _FakeCfg()
    secrets = type("S", (), {"postgres_dsn": "postgresql://x", "redis_url": "redis://x",
                             "telegram_token": None, "telegram_chat_id": None})()
    _run(shadow_cli.run_shadow_cli_command(args, cfg, secrets))
    out, _err = capsys.readouterr()
    assert calls["recovery"] == 1 and calls["once"] == 0
    assert json.loads(out)["command"] == "SHADOW_RECOVERY"


def test_explicit_bucket_shadow_once_does_not_dispatch_to_recovery(monkeypatch, capsys):
    # CONTRACT CHANGE (locking hardening): an explicit --shadow-bucket-ts run now
    # goes through execute_shadow_once_locked (same advisory lock as automatic
    # recovery, deterministic one-bucket work internally via execute_shadow_once)
    # instead of calling execute_shadow_once directly and unlocked. This test
    # asserts the CLI dispatches to the LOCKED explicit wrapper, never to the
    # automatic recovery pass.
    import runtime.shadow_cli as shadow_cli
    import runtime.shadow_recovery as shadow_recovery
    calls = {"recovery": 0, "locked_once": 0}

    async def fake_recovery(*a, **k):
        calls["recovery"] += 1
        raise AssertionError("automatic recovery must not run for an explicit bucket")

    async def fake_locked_once(*a, **kw):
        calls["locked_once"] += 1
        assert kw["explicit_bucket_ts"] == "2026-07-24T05:00:00Z"
        return "locked-report-sentinel"

    monkeypatch.setattr(shadow_recovery, "execute_shadow_recovery", fake_recovery)
    monkeypatch.setattr(shadow_recovery, "execute_shadow_once_locked", fake_locked_once)
    monkeypatch.setattr(shadow_recovery, "render_locked_once_report_json",
                        lambda r: '{"command":"SHADOW_ONCE"}')

    class _DB:
        def __init__(self, dsn): pass
        async def connect(self): pass
        async def close(self): pass

    monkeypatch.setattr(shadow_cli, "Database", _DB)
    args = main.parse_args(["--shadow-once", "--shadow-bucket-ts", "2026-07-24T05:00:00Z",
                            "--shadow-json"])
    cfg = _FakeCfg()
    secrets = type("S", (), {"postgres_dsn": "postgresql://x", "redis_url": "redis://x",
                             "telegram_token": None, "telegram_chat_id": None})()
    _run(shadow_cli.run_shadow_cli_command(args, cfg, secrets))
    out, _err = capsys.readouterr()
    assert calls["locked_once"] == 1 and calls["recovery"] == 0
    assert json.loads(out)["command"] == "SHADOW_ONCE"


# ============================================================================
# amendment: zero caps must never be silently replaced by defaults
# ============================================================================
def _cap_secrets():
    return type("S", (), {"postgres_dsn": "postgresql://x", "redis_url": "redis://x",
                          "telegram_token": None, "telegram_chat_id": None})()


class _NoOpDB:
    """Only connect/close are implemented — proves validate_operational_cap
    rejects a bad cap BEFORE any recovery DB method (lock/schema/seed/etc.) is
    ever reached, since any other attribute access would AttributeError."""

    def __init__(self, dsn):
        pass

    async def connect(self):
        pass

    async def close(self):
        pass


def test_omitted_caps_use_defaults_end_to_end(monkeypatch):
    import runtime.shadow_cli as shadow_cli
    import runtime.shadow_recovery as shadow_recovery
    seen = {}

    async def fake_recovery(*a, **kw):
        seen["max_catchup_buckets"] = kw["max_catchup_buckets"]
        seen["max_outcome_jobs"] = kw["max_outcome_jobs"]
        return _recovery_report()

    monkeypatch.setattr(shadow_recovery, "execute_shadow_recovery", fake_recovery)
    monkeypatch.setattr(shadow_cli, "Database", _NoOpDB)
    args = main.parse_args(["--shadow-once", "--shadow-json"])   # both caps omitted
    _run(shadow_cli.run_shadow_cli_command(args, _FakeCfg(), _cap_secrets()))
    assert seen == {"max_catchup_buckets": 12, "max_outcome_jobs": 100}


def test_explicit_one_passes_through_unchanged(monkeypatch):
    import runtime.shadow_cli as shadow_cli
    import runtime.shadow_recovery as shadow_recovery
    seen = {}

    async def fake_recovery(*a, **kw):
        seen["max_catchup_buckets"] = kw["max_catchup_buckets"]
        seen["max_outcome_jobs"] = kw["max_outcome_jobs"]
        return _recovery_report()

    monkeypatch.setattr(shadow_recovery, "execute_shadow_recovery", fake_recovery)
    monkeypatch.setattr(shadow_cli, "Database", _NoOpDB)
    args = main.parse_args(["--shadow-once", "--shadow-json",
                           "--shadow-max-catchup-buckets", "1",
                           "--shadow-max-outcome-jobs", "1"])
    _run(shadow_cli.run_shadow_cli_command(args, _FakeCfg(), _cap_secrets()))
    assert seen == {"max_catchup_buckets": 1, "max_outcome_jobs": 1}   # 1, never coerced


@pytest.mark.parametrize("flag", ["--shadow-max-catchup-buckets", "--shadow-max-outcome-jobs"])
@pytest.mark.parametrize("value", ["0", "-1", "99999"])
def test_explicit_zero_negative_over_limit_rejected_before_recovery_work(monkeypatch, flag, value):
    import runtime.shadow_cli as shadow_cli
    from runtime.shadow_recovery import ShadowRecoveryError
    monkeypatch.setattr(shadow_cli, "Database", _NoOpDB)
    args = main.parse_args(["--shadow-once", flag, value])
    with pytest.raises(ShadowRecoveryError):
        _run(shadow_cli.run_shadow_cli_command(args, _FakeCfg(), _cap_secrets()))
    # _NoOpDB has no lock/schema/seed methods: reaching any of them would
    # AttributeError instead of the expected ShadowRecoveryError, proving the
    # bad cap was rejected before any recovery DB work began.


def test_recovery_executor_never_receives_zero_as_defaulted_value(monkeypatch):
    """Directly exercises the shadow_cli dispatch branch with catchup omitted
    (None) and outcomes explicitly 0: the executor must see (12, 0) — never
    (12, 12) or any other silent substitution for the explicit zero."""
    import runtime.shadow_cli as shadow_cli
    import runtime.shadow_recovery as shadow_recovery
    seen = {}

    async def fake_recovery(*a, **kw):
        seen["max_catchup_buckets"] = kw["max_catchup_buckets"]
        seen["max_outcome_jobs"] = kw["max_outcome_jobs"]
        raise shadow_recovery.ShadowRecoveryError("stop before any DB work")

    monkeypatch.setattr(shadow_recovery, "execute_shadow_recovery", fake_recovery)
    monkeypatch.setattr(shadow_cli, "Database", _NoOpDB)
    args = main.parse_args(["--shadow-once", "--shadow-max-outcome-jobs", "0"])
    with pytest.raises(shadow_recovery.ShadowRecoveryError):
        _run(shadow_cli.run_shadow_cli_command(args, _FakeCfg(), _cap_secrets()))
    assert seen == {"max_catchup_buckets": 12, "max_outcome_jobs": 0}   # 0 reached the executor intact
