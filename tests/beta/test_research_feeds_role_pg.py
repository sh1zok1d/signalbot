"""Research evidence production prerequisites on real PostgreSQL ($BETA_TEST_DSN;
docs/RESEARCH_EVIDENCE_DEPLOY_PLAN_V1.md §G):

- PREREQ-1: the feed jobs never run DDL. They verify the schema from the catalog and refuse to run,
  writing nothing, when a table, column, key, check, grant or the expected role is missing.
- PREREQ-2: collection runs with presentation off; presentation never changes the decision block
  (beyond `evidence`), the tracked forecasts or a push decision.
- PREREQ-3: the role from deploy/beta_feeds_role.sql runs both jobs and can do nothing else.

Synthetic data only; no network, no Telegram. The role is cluster-wide: each test re-applies the
idempotent role script and leaves the role NOLOGIN without a password."""
import asyncio
import json
import os
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import asyncpg
import numpy as np
import pytest

from beta_fakes import CFG, TEST_DSN, fresh_pool, run
from storage.beta_v0_store import BetaStore, apply_beta_schema
from test_beta_v2_pg import DAY, NOW, _rows, _seed
from test_research_evidence_pg import _ms, fake_public_api

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")
ROOT = Path(__file__).resolve().parents[2]
ROLE = "signalbot_beta_feeds"
ROLE_PW = "feeds-test-only"                  # test cluster only; production sets a random one from stdin
ROLE_SQL = (ROOT / "deploy" / "beta_feeds_role.sql").read_text()
FEED_TABLES = ("beta_feed_metrics_5m", "beta_feed_dvol_1h", "beta_feed_depth", "beta_feed_spot_5m",
               "beta_feed_stress_hours")


def _feeds_dsn() -> str:
    u = urlparse(TEST_DSN)
    return urlunparse(u._replace(netloc=f"{ROLE}:{ROLE_PW}@{u.hostname}:{u.port or 5432}"))


async def _install_role(pool):
    async with pool.acquire() as c:
        if not await c.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = current_user"):
            pytest.skip("the BETA_TEST_DSN role is not a superuser: it cannot create the feed role")
        await c.execute(ROLE_SQL)
        await c.execute(ROLE_SQL)                                  # idempotent
        await c.execute(f"ALTER ROLE {ROLE} PASSWORD '{ROLE_PW}'")


async def _lock_role(pool):
    async with pool.acquire() as c:
        await c.execute(f"ALTER ROLE {ROLE} NOLOGIN PASSWORD NULL")


def _api(now):
    """Fake public responses: 2 days of 5m metrics, 3 days of DVOL and spot, a covered book, and one
    stress hour with trades on both venues."""
    t_end = _ms(now) - _ms(now) % 300_000
    rows = list(range(t_end - 2 * 86_400_000, t_end, 300_000))
    oi = [{"timestamp": t, "sumOpenInterest": repr(80000.0 + k)} for k, t in enumerate(rows)]
    ls = [{"timestamp": t, "longShortRatio": "1.8"} for t in rows]
    h0 = _ms(now) - _ms(now) % 3_600_000
    dvol = [[h0 - k * 3_600_000, 50.0, 51.0, 49.0, 50.0] for k in range(1, 72)]
    book = {"T": _ms(now), "bids": [[str(60000 - 1 - k), "1"] for k in range(1000)],
            "asks": [[str(60000 + 1 + k), "1"] for k in range(1000)]}
    spot = [[t, "60000", "60010", "59990", "60000", "1", t + 299_999, "60000", 10, "0.5", "30000", "0"]
            for t in range(t_end - 3 * 86_400_000, t_end, 300_000)]
    hour = h0 - 3_600_000
    ts = np.sort(np.random.default_rng(1).integers(hour, hour + 3_600_000, 400))
    perp = [{"a": k, "p": str(60000 + k), "q": "20" if k % 50 == 0 else "0.1", "T": int(t)} for k, t in enumerate(ts)]
    spt = [{"a": k, "p": str(60001 + k), "q": "0.1", "T": int(t)} for k, t in enumerate(ts)]
    k1h = [[hour, "60000", "61500", "60000", "61000", "1", hour + 3_599_999]]
    fetch, calls = fake_public_api(now, oi_rows=oi, ls_rows=ls, dvol=dvol, book=book, spot=spot, k1h=k1h,
                                   perp_trades=perp, spot_trades=spt)
    return fetch, calls


def _no_fetch(url, params):
    raise AssertionError(f"a refused job must not fetch: {url}")


async def _health(pool) -> dict:
    async with pool.acquire() as c:
        rows = await c.fetch("SELECT component, last_error_type, last_success_at FROM beta_runtime_health")
    return {r["component"]: (r["last_error_type"], r["last_success_at"]) for r in rows}


async def _counts(pool) -> dict:
    out = {}
    async with pool.acquire() as c:
        for t in FEED_TABLES + ("beta_runtime_health",):
            out[t] = await c.fetchval(f"SELECT count(*) FROM {t}") if await c.fetchval(
                "SELECT to_regclass($1) IS NOT NULL", t) else None
    return out


async def _catalog_digest(c) -> str:
    rows = await c.fetch("""SELECT c.relname, c.relkind::text, a.attname, a.atttypid::regtype::text AS typ
                            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                            LEFT JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
                            WHERE n.nspname = 'public' ORDER BY 1, 3""")
    cons = await c.fetch("""SELECT conrelid::regclass::text AS t, conname FROM pg_constraint k
                            JOIN pg_namespace n ON n.oid = k.connamespace WHERE n.nspname = 'public' ORDER BY 1, 2""")
    return json.dumps([list(r.values()) for r in rows] + [list(r.values()) for r in cons])


# ---- PREREQ-3 + PREREQ-1: the restricted role runs both jobs ----------------------------------------------
def test_the_core_role_applies_the_schema_and_the_restricted_role_runs_both_jobs():
    from beta.research_feeds import feed_schema_readiness, run_feeds_job, run_stress_job

    async def body():
        pool = await fresh_pool()                                   # the core role applied the schema
        await _install_role(pool)
        fpool = await asyncpg.create_pool(_feeds_dsn(), min_size=1, max_size=3)
        try:
            fstore = BetaStore(fpool)
            async with fstore.connect() as c:
                assert await c.conn.fetchval("SHOW statement_timeout") == "1min"
                rd = await feed_schema_readiness(c, "feeds", expected_role=ROLE)
                rs = await feed_schema_readiness(c, "stress", expected_role=ROLE)
            assert rd == {"ready": True, "status": "OK", "db_role": ROLE, "missing": []}
            assert rs["ready"] and rs["db_role"] == ROLE
            fetch, calls = _api(NOW)
            rep = await run_feeds_job(fstore, now=NOW, fetch=fetch, pause=lambda s: asyncio.sleep(0),
                                      expected_role=ROLE)
            assert rep["status"] == "OK" and not rep["errors"], rep
            assert rep["depth"] == "COVERED"
            srep = await run_stress_job(fstore, now=NOW, fetch=fetch, pause=lambda s: asyncio.sleep(0),
                                        expected_role=ROLE)
            assert srep["status"] == "OK" and srep["stress"] == 1, srep
            assert all("api_key" not in json.dumps(p).lower() for _u, p in calls)
            n = await _counts(pool)
            assert all(n[t] > 0 for t in FEED_TABLES), n
            health = {r["component"]: r for r in await _rows(
                pool, "SELECT component, last_success_at, last_error_type FROM beta_runtime_health")}
            for comp in ("research_feeds", "research_feeds_definition", "research_stress_hours"):
                assert comp in health
            assert health["research_feeds"]["last_success_at"] is not None
            assert health["research_stress_hours"]["last_success_at"] is not None
        finally:
            await fpool.close()
            await _lock_role(pool)
            await pool.close()
    run(body())


def test_the_restricted_role_cannot_run_ddl_reach_other_tables_or_escalate():
    async def body():
        pool = await fresh_pool()
        await _install_role(pool)
        core_user = urlparse(TEST_DSN).username
        fconn = await asyncpg.connect(_feeds_dsn())
        try:
            async with pool.acquire() as c:
                before = await _catalog_digest(c)
                attrs = await c.fetchrow("SELECT rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolreplication, "
                                         "rolbypassrls, rolcanlogin, rolconnlimit, rolconfig FROM pg_roles "
                                         "WHERE rolname = $1", ROLE)
                members = await c.fetchval("SELECT count(*) FROM pg_auth_members m JOIN pg_roles u ON u.oid = m.member "
                                           "WHERE u.rolname = $1", ROLE)
            assert not any(attrs[k] for k in ("rolsuper", "rolcreatedb", "rolcreaterole", "rolinherit",
                                               "rolreplication", "rolbypassrls"))
            assert attrs["rolcanlogin"] and attrs["rolconnlimit"] == 4 and members == 0
            assert "statement_timeout=60s" in attrs["rolconfig"]

            # initialization is the core role's: under the feed role it fails and changes nothing
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await apply_beta_schema(fconn)
            denied = {
                "create_table": "CREATE TABLE public.x_feeds_probe (a int)",
                "create_schema": "CREATE SCHEMA x_feeds_probe",
                "alter_table": "ALTER TABLE beta_feed_depth ADD COLUMN x int",
                "drop_table": "DROP TABLE beta_feed_depth",
                "create_index": "CREATE INDEX x_feeds_probe ON beta_feed_metrics_5m (fetched_at)",
                "drop_constraint": "ALTER TABLE beta_feed_depth DROP CONSTRAINT ck_beta_feed_depth_cover",
                "delete": "DELETE FROM beta_feed_metrics_5m",
                "truncate": "TRUNCATE beta_feed_dvol_1h",
                "update_depth": "UPDATE beta_feed_depth SET levels = levels",
                "delete_health": "DELETE FROM beta_runtime_health",
                "read_users": "SELECT 1 FROM beta_users LIMIT 1",
                "read_allowlist": "SELECT 1 FROM beta_allowlist LIMIT 1",
                "read_invites": "SELECT 1 FROM beta_invites LIMIT 1",
                "read_deliveries": "SELECT 1 FROM beta_notification_deliveries LIMIT 1",
                "read_push_decisions": "SELECT 1 FROM beta_push_decisions LIMIT 1",
                "write_push_decisions": "DELETE FROM beta_push_decisions",
                "read_market_alerts": "SELECT 1 FROM beta_market_alerts LIMIT 1",
                "write_market_alerts": "DELETE FROM beta_market_alerts",
                "read_klines_1m": "SELECT 1 FROM klines_1m LIMIT 1",
                "read_hist_oi_other_columns": "SELECT oi_usd FROM beta_hist_oi_5m LIMIT 1",
                "write_hist_oi": "UPDATE beta_hist_oi_5m SET oi_base = oi_base",
                "set_role_core": f'SET ROLE "{core_user}"',
                "grant_self": f"GRANT SELECT ON beta_users TO {ROLE}",
            }
            got = {}
            for name, sql in denied.items():
                try:
                    await fconn.execute(sql)
                    got[name] = "ALLOWED"
                except (asyncpg.InsufficientPrivilegeError, asyncpg.exceptions.InvalidGrantOperationError):
                    got[name] = "DENIED"
            assert set(got.values()) == {"DENIED"}, got
            async with pool.acquire() as c:
                assert await _catalog_digest(c) == before
        finally:
            await fconn.close()
            await _lock_role(pool)
            await pool.close()
    run(body())


# ---- PREREQ-1: missing schema fails closed ----------------------------------------------------------------
def test_a_missing_schema_column_check_grant_or_role_fails_closed_and_writes_no_feed_data():
    """Refused before any fetch: no feed row is written. Since the external review of A3 the refusal is
    recorded as a failed run of the job's own health row (when the role may write it), so the owner's
    FEEDS_FAILING / STRESS_HOURS_FAILING alert sees it."""
    from beta.research_feeds import feed_schema_readiness, run_feeds_job, run_stress_job

    async def body():
        pause = lambda s: asyncio.sleep(0)                          # noqa: E731
        # (a) no beta schema at all: refused, nothing created
        pool = await fresh_pool()
        async with pool.acquire() as c:
            await c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        store = BetaStore(pool)
        for job in (run_feeds_job, run_stress_job):
            rep = await job(store, now=NOW, fetch=_no_fetch, pause=pause)
            assert rep["status"] == "SCHEMA_NOT_READY" and "table:beta_runtime_health" in rep["missing"], rep
        assert (await _rows(pool, "SELECT count(*) AS n FROM pg_tables WHERE schemaname = 'public'")) == [{"n": 0}]
        await pool.close()

        # (b) a dropped check and a dropped column: the feeds job is refused, the stress job (which uses
        # neither) still runs; the refused job writes no feed data, only its failed health row
        pool = await fresh_pool()
        store = BetaStore(pool)
        async with pool.acquire() as c:
            await c.execute("ALTER TABLE beta_feed_depth DROP CONSTRAINT ck_beta_feed_depth_cover; "
                            "ALTER TABLE beta_hist_oi_5m DROP COLUMN ls_account_ratio;")
        async with store.connect() as c:
            rd = await feed_schema_readiness(c, "feeds")
            rs = await feed_schema_readiness(c, "stress")
        assert rd["status"] == "SCHEMA_NOT_READY"
        assert sorted(rd["missing"]) == ["check:beta_feed_depth.ck_beta_feed_depth_cover",
                                         "column:beta_hist_oi_5m.ls_account_ratio"]
        assert rs["ready"]
        rep = await run_feeds_job(store, now=NOW, fetch=_no_fetch, pause=pause)
        assert rep["status"] == "SCHEMA_NOT_READY"
        assert await _counts(pool) == {**{t: 0 for t in FEED_TABLES}, "beta_runtime_health": 1}
        assert await _health(pool) == {"research_feeds": ("SCHEMA_NOT_READY", None)}
        await pool.close()

        # (c) a missing grant on the restricted role: refused before any fetch or write
        pool = await fresh_pool()
        await _install_role(pool)
        async with pool.acquire() as c:
            await c.execute(f"REVOKE INSERT ON beta_feed_depth FROM {ROLE}")
        fpool = await asyncpg.create_pool(_feeds_dsn(), min_size=1, max_size=3)
        try:
            rep = await run_feeds_job(BetaStore(fpool), now=NOW, fetch=_no_fetch, pause=pause, expected_role=ROLE)
            assert rep["status"] == "SCHEMA_NOT_READY" and rep["missing"] == ["grant:INSERT:beta_feed_depth"], rep
            assert rep["db_role"] == ROLE
            assert await _counts(pool) == {**{t: 0 for t in FEED_TABLES}, "beta_runtime_health": 1}
            assert await _health(pool) == {"research_feeds": ("SCHEMA_NOT_READY", None)}
        finally:
            await fpool.close()
            await _lock_role(pool)

        # (d) connected as another role than the unit expects: refused, no silent run as the core role
        for job in (run_feeds_job, run_stress_job):
            rep = await job(BetaStore(pool), now=NOW, fetch=_no_fetch, pause=pause, expected_role=ROLE)
            assert rep["status"] == "WRONG_DB_ROLE" and rep["db_role"] != ROLE
        assert await _counts(pool) == {**{t: 0 for t in FEED_TABLES}, "beta_runtime_health": 2}
        assert await _health(pool) == {"research_feeds": ("WRONG_DB_ROLE", None),
                                       "research_stress_hours": ("WRONG_DB_ROLE", None)}
        await pool.close()
    run(body())


def test_the_feed_commands_never_initialize_the_schema_and_exit_3_when_refused(monkeypatch):
    import main
    from beta import research_feeds as RF
    from runtime.beta_cli import run_beta_cli_command
    from storage.db import Database

    def no_init(self):
        raise AssertionError("a feed command must never apply the schema (DDL)")
    monkeypatch.setattr(Database, "init_beta_v0_schema", no_init)
    fetch, _ = _api(NOW)
    monkeypatch.setattr(RF, "_session_fetch", lambda session: fetch)       # the CLI's own pauses stay real
    env = {"BETA_ENABLED": "1", "BETA_FEEDS_EXPECTED_DB_ROLE": ROLE}

    async def body():
        pool = await fresh_pool()
        await _install_role(pool)
        db = Database(_feeds_dsn())
        await db.connect()
        try:
            for flag in ("--beta-feeds-once", "--beta-stress-once"):
                rep = await run_beta_cli_command(main.parse_args([flag, "--beta-json"]), db=db, env=env,
                                                 clock=lambda: NOW)
                assert rep["status"] == "OK", rep
            assert all(v > 0 for v in (await _counts(pool)).values())
        finally:
            await db.close()
        # the same commands as the core role while the unit expects the feed role: exit 3, nothing run
        core = Database(TEST_DSN)
        await core.connect()
        try:
            for flag in ("--beta-feeds-once", "--beta-stress-once"):
                with pytest.raises(SystemExit) as e:
                    await run_beta_cli_command(main.parse_args([flag, "--beta-json"]), db=core, env=env,
                                               clock=lambda: NOW)
                assert e.value.code == 3
        finally:
            await core.close()
            await _lock_role(pool)
            await pool.close()
    run(body())


# ---- PREREQ-2: collection with presentation off; presentation never changes numbers or pushes -------------
def _cfg_with(enabled: bool):
    d = CFG.section("decision")
    return CFG.with_overrides(decision={**d, "research_evidence": {**d["research_evidence"], "enabled": enabled}})


def test_collection_runs_with_presentation_off_and_the_block_is_identical_without_evidence(monkeypatch):
    import main
    from beta import research_feeds as RF
    from beta.config import BetaConfig
    from beta.decision import build_decision, reset_cache
    from beta.history_stats import run_history_build
    from runtime.beta_cli import run_beta_cli_command
    from storage.db import Database

    fetch, _ = _api(NOW)
    monkeypatch.setattr(RF, "_session_fetch", lambda session: fetch)

    async def block(store, cfg):
        reset_cache()
        async with store.connect() as conn:
            return await build_decision(conn, cfg, now=NOW)

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        await _seed(pool)
        await run_history_build(store, CFG, now=DAY + timedelta(hours=2))
        db = Database(TEST_DSN)
        await db.connect()
        try:
            # presentation off in the config: both collectors still run, insert and record health
            monkeypatch.setattr(BetaConfig, "load", classmethod(lambda cls, *a, **k: _cfg_with(False)))
            for flag in ("--beta-feeds-once", "--beta-stress-once"):
                rep = await run_beta_cli_command(main.parse_args([flag, "--beta-json"]), db=db,
                                                 env={"BETA_ENABLED": "1"}, clock=lambda: NOW)
                assert rep["status"] == "OK", rep
            n1 = await _counts(pool)
            assert all(n1[t] > 0 for t in FEED_TABLES), n1
            # presentation off by env: the collectors do not even read it
            monkeypatch.setattr(BetaConfig, "load", classmethod(lambda cls, *a, **k: _cfg_with(True)))
            rep = await run_beta_cli_command(main.parse_args(["--beta-feeds-once", "--beta-json"]), db=db,
                                             env={"BETA_ENABLED": "1", "BETA_RESEARCH_EVIDENCE_ENABLED": "0"},
                                             clock=lambda: NOW + timedelta(minutes=5))
            assert rep["status"] == "OK", rep
            health = await _rows(pool, "SELECT last_run_at FROM beta_runtime_health WHERE component='research_feeds'")
            assert health[0]["last_run_at"] == NOW + timedelta(minutes=5)
        finally:
            await db.close()

        # presentation on / off (env) / off (config): the block differs only by `evidence`, byte for byte
        monkeypatch.delenv("BETA_RESEARCH_EVIDENCE_ENABLED", raising=False)
        on = await block(store, _cfg_with(True))
        monkeypatch.setenv("BETA_RESEARCH_EVIDENCE_ENABLED", "0")
        off_env = await block(store, _cfg_with(True))
        monkeypatch.delenv("BETA_RESEARCH_EVIDENCE_ENABLED")
        off_cfg = await block(store, _cfg_with(False))
        assert on["available"] and on.get("evidence") and not on["evidence"].get("error_type")
        assert off_env.get("evidence") is None and off_cfg.get("evidence") is None
        strip = lambda b: json.dumps({k: v for k, v in b.items() if k != "evidence"},  # noqa: E731
                                     sort_keys=True, default=str)
        assert strip(on) == strip(off_env) == strip(off_cfg)
        await pool.close()
    run(body())


def test_presentation_never_changes_a_push_decision_or_a_tracked_forecast(monkeypatch):
    from beta import market_alerts as MA
    from beta.history_stats import run_history_build
    from beta_fakes import Clock

    real = MA.detect_level_touches

    def detect(block, b, closed, **kw):         # the real detector, or a fixed touch of the first push level
        out = real(block, b, closed, **kw)
        if out:
            return out
        from beta.levels import PUSH_LEVELS
        lv = next(x for x in block["levels"]["all"] if x["kind"] in PUSH_LEVELS)
        return [{"kind": "level", "key": f"level:{lv['kind']}:{NOW.date().isoformat()}",
                 "payload": {"at": NOW.isoformat(), "level_kind": lv["kind"], "level": lv["price"],
                             "side": 1 if lv["kind"].endswith("H") else -1, "period": "D", "price": block["price"],
                             "history": None, "next": None, "corridor_4h": None, "event_zone": {}}}]
    monkeypatch.setattr(MA, "detect_level_touches", detect)

    async def one(presentation: bool):
        if presentation:
            monkeypatch.delenv("BETA_RESEARCH_EVIDENCE_ENABLED", raising=False)
        else:
            monkeypatch.setenv("BETA_RESEARCH_EVIDENCE_ENABLED", "0")
        from beta.decision import reset_cache
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        await _seed(pool)
        await run_history_build(store, CFG, now=DAY + timedelta(hours=2))
        async with store.connect() as conn:
            rep = await MA.run_market_alerts(conn, CFG, sender=None, clock=Clock(NOW), push_on=True)
        alerts = await _rows(pool, "SELECT kind, alert_key, decision_ts, decision, suppression_reason, payload "
                                   "FROM beta_market_alerts ORDER BY alert_pk")
        forecasts = await _rows(pool, "SELECT horizon, issued_at, horizon_end, anchor_price, lower, upper, coverage, "
                                      "model_version, outcome FROM beta_forecasts ORDER BY horizon, issued_at")
        await pool.close()
        for a in alerts:
            p = json.loads(a["payload"]) if isinstance(a["payload"], str) else dict(a["payload"])
            a["evidence"] = p.pop("evidence", None)
            a["payload"] = json.dumps(p, sort_keys=True, default=str)
        return rep, alerts, forecasts

    async def body():
        rep_on, alerts_on, fc_on = await one(True)
        rep_off, alerts_off, fc_off = await one(False)
        assert rep_on["detected"] >= 1 and rep_on == rep_off
        assert fc_on and fc_on == fc_off
        assert all(a["evidence"] is None for a in alerts_off)
        assert all(a["evidence"] is not None for a in alerts_on if a["kind"] == "level")   # evidence was attached
        strip = lambda rows: [{k: v for k, v in r.items() if k != "evidence"} for r in rows]  # noqa: E731
        assert strip(alerts_on) == strip(alerts_off)
    run(body())


# ---- PREREQ-3: the install script, end to end against this cluster (docker replaced by local psql) ---------
@pytest.mark.skipif(shutil.which("psql") is None or os.geteuid() != 0,
                    reason="needs the psql client and root (the script chowns the env file)")
def test_the_install_script_applies_the_grants_and_writes_a_private_env_file(tmp_path):
    u = urlparse(TEST_DSN)

    async def prepare():
        pool = await fresh_pool()                                   # the core role applied the schema
        try:
            async with pool.acquire() as c:
                return bool(await c.fetchval("SELECT rolsuper FROM pg_roles WHERE rolname = current_user"))
        finally:
            await pool.close()

    async def cleanup():
        c = await asyncpg.connect(TEST_DSN)
        try:
            await c.execute(f"ALTER ROLE {ROLE} NOLOGIN PASSWORD NULL")
        finally:
            await c.close()
    if not run(prepare()):
        pytest.skip("the BETA_TEST_DSN role is not a superuser")
    try:
        root = tmp_path / "signalbot"
        (root / "deploy").mkdir(parents=True)
        shutil.copy(ROOT / "deploy" / "beta_feeds_role.sql", root / "deploy" / "beta_feeds_role.sql")
        (root / ".env").write_text(f"POSTGRES_USER={u.username}\nPOSTGRES_DB={u.path.lstrip('/')}\n"
                                   f"POSTGRES_HOST={u.hostname}\nPOSTGRES_PORT={u.port or 5432}\n"
                                   "TELEGRAM_BOT_TOKEN=must-not-be-copied\nBETA_ENABLED=true\n")
        shim = tmp_path / "bin"
        shim.mkdir()
        (shim / "docker").write_text("#!/bin/sh\n# docker exec -i CONTAINER psql|sh ... -> the same on this host\n"
                                     "shift 3\nif [ \"$1\" = psql ]; then shift; "
                                     "exec psql -h \"$PGHOST\" -p \"$PGPORT\" \"$@\"; fi\n"
                                     "unset PGPASSWORD\nexec \"$@\"\n")
        (shim / "docker").chmod(0o755)
        env = {**os.environ, "PATH": f"{shim}:{os.environ['PATH']}", "SIGNALBOT_ROOT": str(root),
               "PGHOST": u.hostname, "PGPORT": str(u.port or 5432), "PGPASSWORD": u.password or ""}
        script = ROOT / "deploy" / "install_beta_feeds_role.sh"
        for args in ([], ["--set-password"], ["--set-password"]):           # idempotent; password rotates
            res = subprocess.run(["bash", str(script), *args], env=env, capture_output=True, text=True, timeout=60)
            assert res.returncode == 0, res.stderr
            assert "must-not-be-copied" not in res.stdout + res.stderr
            if args:
                assert f"role {ROLE}: login verified" in res.stdout, res.stdout
        # two rotations at once are serialized: the file always holds the password the role has
        procs = [subprocess.Popen(["bash", str(script), "--set-password"], env=env, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True) for _ in range(2)]
        outs = [pr.communicate(timeout=120) for pr in procs]
        assert [pr.returncode for pr in procs] == [0, 0], outs
        assert all(f"role {ROLE}: login verified" in o for o, _e in outs)
        assert [x.name for x in root.glob(".env.beta-feeds.*")] == []
        # a broken password change leaves no temp credential file and the old file untouched
        before = (root / ".env.beta-feeds").read_text()
        (shim / "docker").write_text("#!/bin/sh\n# as above, but the password change fails\nshift 3\n"
                                     "if [ \"$1\" = psql ]; then shift; t=$(mktemp); cat > \"$t\"; "
                                     "if grep -q 'PASSWORD' \"$t\"; then rm -f \"$t\"; exit 1; fi; "
                                     "psql -h \"$PGHOST\" -p \"$PGPORT\" \"$@\" < \"$t\"; r=$?; rm -f \"$t\"; "
                                     "exit $r; fi\nunset PGPASSWORD\nexec \"$@\"\n")
        bad = subprocess.run(["bash", str(script), "--set-password"], env=env, capture_output=True, text=True,
                             timeout=60, stdin=subprocess.DEVNULL)
        assert bad.returncode != 0
        assert (root / ".env.beta-feeds").read_text() == before
        assert [x.name for x in root.glob(".env.beta-feeds.*")] == []
        (shim / "docker").write_text("#!/bin/sh\nshift 3\nif [ \"$1\" = psql ]; then shift; "
                                     "exec psql -h \"$PGHOST\" -p \"$PGPORT\" \"$@\"; fi\n"
                                     "unset PGPASSWORD\nexec \"$@\"\n")
        f = root / ".env.beta-feeds"
        st = f.stat()
        assert oct(st.st_mode & 0o777) == "0o600" and st.st_uid == 0 and st.st_gid == 0
        content = dict(line.split("=", 1) for line in f.read_text().splitlines() if line and not line.startswith("#"))
        assert set(content) == {"POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
                                "BETA_ENABLED"}
        assert content["POSTGRES_USER"] == ROLE and len(content["POSTGRES_PASSWORD"]) == 48
        assert content["POSTGRES_PASSWORD"] not in res.stdout + res.stderr

        async def login():
            dsn = urlunparse(u._replace(netloc=f"{ROLE}:{content['POSTGRES_PASSWORD']}@{u.hostname}:{u.port or 5432}"))
            c = await asyncpg.connect(dsn)
            try:
                return await c.fetchval("SELECT current_user")
            finally:
                await c.close()
        assert run(login()) == ROLE
    finally:
        run(cleanup())


def test_presentation_off_hides_research_lines_the_button_and_a_stored_research_tab(monkeypatch):
    from beta.decision import reset_cache
    from beta.history_stats import run_history_build
    from beta_fakes import Clock
    from test_beta_v2_pg import _handler, _join, plain

    async def body():
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        await _seed(pool)
        await run_history_build(store, CFG, now=DAY + timedelta(hours=2))
        h = _handler(pool, 900000000001, Clock(NOW))
        uid = 900000000111
        async with store.connect() as conn:
            await conn.allowlist_add(uid)
        msg = await _join(h, uid, 10)
        async with store.connect() as conn:
            await conn.mark_privacy_notice_seen(uid, 4)
        monkeypatch.delenv("BETA_RESEARCH_EVIDENCE_ENABLED", raising=False)
        out_on = await h.handle(msg("/btc", 50))                         # presentation on: the stored view has evidence
        btn = [b for row in out_on[-1].buttons for b in row if b[1].endswith(":research")]
        assert len(btn) == 1
        monkeypatch.setenv("BETA_RESEARCH_EVIDENCE_ENABLED", "0")
        reset_cache()
        out_off = await h.handle(msg("/btc", 51))
        assert "🔬" not in plain(out_off[-1].html)
        assert not [b for row in (out_off[-1].buttons or []) for b in row if b[1].endswith(":research")]
        view = (await _rows(pool, "SELECT payload FROM beta_btc_views WHERE kind='btc' ORDER BY view_pk DESC LIMIT 1"))[0]
        payload = json.loads(view["payload"]) if isinstance(view["payload"], str) else view["payload"]
        assert payload["decision"].get("evidence") is None
        # the earlier view still carries evidence, but its research tab no longer opens
        cb = {"update_id": 60, "callback_query": {"id": "c60", "from": {"id": uid},
                                                 "message": {"chat": {"id": uid}, "message_id": 1}, "data": btn[0][1]}}
        res = await h.handle(cb)
        assert "Исследования к рынку сейчас" not in "".join(plain(getattr(r, "html", "") or "") for r in res)
        assert await _rows(pool, "SELECT count(*) AS n FROM beta_details_opens WHERE tab = 'research'") == [{"n": 0}]
        await pool.close()
    run(body())
