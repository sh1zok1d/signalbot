"""CLI flag isolation, read-only commands, kill switches, and code isolation from the
frozen V1/V2 forecast engines and the legacy Telegram notifier."""
import ast
import re
from pathlib import Path

import pytest

import main
from beta.config import BetaConfigError
from beta_fakes import TEST_DSN, run
from runtime.beta_cli import is_beta_command, run_beta_cli_command

REPO = Path(__file__).resolve().parents[2]
BETA_FILES = sorted((REPO / "beta").glob("*.py")) + sorted((REPO / "runtime").glob("beta_*.py")) + \
    [REPO / "storage/beta_v0_store.py"]


@pytest.mark.parametrize("flag", ["--beta-bootstrap", "--beta-once", "--beta-status", "--beta-outcomes-once",
                                  "--beta-notify-once", "--beta-health", "--beta-usage-report"])
def test_each_beta_command_parses_alone(flag):
    args = main.parse_args([flag, "--beta-json"])
    assert is_beta_command(args)


@pytest.mark.parametrize("argv", [
    ["--beta-once", "--beta-status"],
    ["--beta-once", "--shadow-once"],
    ["--beta-status", "--telegram-status"],
    ["--beta-once", "--validate"],
    ["--beta-notify-once", "--backfill-only"],
    ["--beta-status", "--beta-bucket-ts", "2026-03-01T00:00:00Z"],
    ["--beta-json"],
    ["--shadow-once", "--beta-json"],
])
def test_cross_command_exclusivity(argv):
    with pytest.raises(SystemExit):
        main.parse_args(argv)


def test_context_dry_run_flag_and_its_options():
    args = main.parse_args(["--beta-context-dry-run", "--dry-run-days", "7", "--dry-run-provisional"])
    assert is_beta_command(args) and args.dry_run_days == 7 and args.dry_run_provisional
    from runtime.beta_cli import READ_ONLY_COMMANDS
    assert "beta_context_dry_run" in READ_ONLY_COMMANDS
    for argv in (["--beta-status", "--dry-run-provisional"], ["--beta-context-dry-run", "--dry-run-days", "0"],
                 ["--beta-context-dry-run", "--dry-run-days", "31"], ["--beta-context-dry-run", "--beta-once"]):
        with pytest.raises(SystemExit):
            main.parse_args(argv)


def test_bucket_ts_allowed_with_beta_once_only():
    args = main.parse_args(["--beta-once", "--beta-bucket-ts", "2026-03-01T00:05:00Z"])
    assert args.beta_once and args.beta_bucket_ts
    assert not is_beta_command(main.parse_args(["--shadow-status"]))


def _imports(path: Path) -> set:
    tree = ast.parse(path.read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module)
        elif isinstance(n, ast.Import):
            mods.update(a.name for a in n.names)
    return mods


def test_beta_code_never_imports_forecast_engines_or_legacy_notifier():
    for f in BETA_FILES:
        for m in _imports(f):
            assert not m.startswith("analytics.forecasting"), (f, m)
            assert m not in ("notifications.telegram_formatter", "notifications.telegram_models",
                             "runtime.telegram_cli", "storage.telegram_notification_readers"), (f, m)
            assert not any(x in m.lower() for x in ("llm", "openai", "anthropic")), (f, m)
    assert "notifications.telegram_client" in _imports(REPO / "runtime/beta_bot.py")
    assert "analytics.feature_engine.bucket_coordinator" in _imports(REPO / "beta/state_tape.py")
    assert "analytics.percentile_engine.compute" in _imports(REPO / "beta/state_tape.py")


def test_beta_code_never_logs_ids_or_tokens():
    for f in BETA_FILES:
        for line in f.read_text().splitlines():
            if re.search(r"\blogger\.|\blogging\.|(?<![\w.])print\(", line):
                low = line.lower()
                assert "user_id" not in low and "chat_id" not in low and "token" not in low, (f, line)


def test_disabled_committed_config_makes_every_write_command_a_noop():
    class NoDb:            # any DB access would fail the test
        def __getattr__(self, name):
            raise AssertionError(f"DB touched: {name}")
    for flag in ("--beta-once", "--beta-bootstrap", "--beta-outcomes-once", "--beta-notify-once",
                 "--beta-d7-once", "--beta-d7-backfill"):
        for env in ({}, {"BETA_ENABLED": ""}, {"BETA_ENABLED": "0", "BETA_PUSH_ENABLED": "1"}):
            rep = run(run_beta_cli_command(main.parse_args([flag, "--beta-json"]), db=NoDb(), env=env))
            assert rep["status"] == "DISABLED" and rep["switches"]["BETA_ENABLED"] is False


def test_env_enable_keeps_push_off_and_no_telegram_notify_touches_nothing():
    class NoDb:
        def __getattr__(self, name):
            raise AssertionError(f"DB touched: {name}")
    rep = run(run_beta_cli_command(main.parse_args(["--beta-notify-once", "--beta-json"]), db=NoDb(),
                                   env={"BETA_ENABLED": "1", "BETA_TELEGRAM_ENABLED": "0"}))
    assert rep["status"] == "TELEGRAM_DISABLED"
    assert rep["switches"]["BETA_ENABLED"] is True and rep["switches"]["BETA_PUSH_ENABLED"] is False
    # enabled push contradicts the no-Telegram mode: refused before any DB access
    with pytest.raises(BetaConfigError):
        run(run_beta_cli_command(main.parse_args(["--beta-notify-once", "--beta-json"]), db=NoDb(),
                                 env={"BETA_ENABLED": "1", "BETA_PUSH_ENABLED": "1",
                                      "BETA_TELEGRAM_ENABLED": "0"}))


def test_bot_does_not_start_in_no_telegram_mode(monkeypatch, caplog):
    import logging
    from runtime import beta_bot
    for k, v in {"BETA_ENABLED": "1", "BETA_TELEGRAM_ENABLED": "0", "BETA_TELEGRAM_BOT_TOKEN": "",
                 "BETA_PUSH_ENABLED": ""}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(beta_bot.asyncio, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("started")))
    with caplog.at_level(logging.INFO):
        beta_bot.main()
    assert "no-Telegram shadow mode" in caplog.text


@pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set")
def test_status_and_health_are_read_only():
    async def body():
        import asyncpg
        from beta_fakes import STAGE1_MIN_SQL
        from storage.db import Database
        admin = await asyncpg.connect(TEST_DSN)
        await admin.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        db = Database(TEST_DSN)
        await db.connect()
        try:
            for flag in ("--beta-status", "--beta-health", "--beta-usage-report"):
                rep = await run_beta_cli_command(main.parse_args([flag, "--beta-json"]), db=db, env={})
                assert rep["status"] == "NOT_INITIALIZED"
            assert await admin.fetchval("SELECT count(*) FROM pg_tables WHERE schemaname='public'") == 0
            await db.init_beta_v0_schema()
            await db.init_beta_v0_schema()                      # idempotent
            await admin.execute(STAGE1_MIN_SQL)
            snapshot_sql = ("SELECT (SELECT count(*) FROM beta_runtime_health), (SELECT count(*) FROM beta_state_tape), "
                            "(SELECT count(*) FROM beta_admin_audit), (SELECT count(*) FROM beta_detector_watermark)")
            before = tuple(await admin.fetchrow(snapshot_sql))
            for flag in ("--beta-status", "--beta-health", "--beta-usage-report"):
                rep = await run_beta_cli_command(main.parse_args([flag, "--beta-json"]), db=db, env={})
                assert rep["status"] in ("OK", "ALERTS")
            assert tuple(await admin.fetchrow(snapshot_sql)) == before == (0, 0, 0, 0)
        finally:
            await db.close()
            await admin.close()
    run(body())


@pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set")
def test_beta_health_on_postgres_respects_no_telegram_mode():
    async def body():
        import asyncpg
        from beta_fakes import STAGE1_MIN_SQL
        from storage.db import Database
        admin = await asyncpg.connect(TEST_DSN)
        await admin.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        db = Database(TEST_DSN)
        await db.connect()
        try:
            await db.init_beta_v0_schema()
            await admin.execute(STAGE1_MIN_SQL)
            args = main.parse_args(["--beta-health", "--beta-json"])
            tg = await run_beta_cli_command(args, db=db, env={"BETA_ENABLED": "1"})
            shadow = await run_beta_cli_command(args, db=db, env={"BETA_ENABLED": "1",
                                                                  "BETA_TELEGRAM_ENABLED": "0"})
            keys = lambda r: {a["key"] for a in r["health"]["alerts"]}
            assert {"BOT_RECEIVER_DOWN", "NOTIFIER_NOT_RUNNING"} <= keys(tg)
            assert not keys(shadow) & {"BOT_RECEIVER_DOWN", "NOTIFIER_NOT_RUNNING"}
            assert keys(tg) - keys(shadow) == {"BOT_RECEIVER_DOWN", "NOTIFIER_NOT_RUNNING"}
            assert shadow["health"]["switches"]["BETA_TELEGRAM_ENABLED"] is False
        finally:
            await db.close()
            await admin.close()
    run(body())
