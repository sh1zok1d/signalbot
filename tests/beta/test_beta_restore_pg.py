"""Restore drill (backlog A6) on real PostgreSQL ($BETA_TEST_DSN): `deploy/restore.sh` end to end against a
dump made the way `deploy/backup.sh` makes it (`--no-owner --no-privileges`). `docker exec` is replaced by
the local psql; the cluster has no TimescaleDB, so the shim answers only the three TimescaleDB calls of the
script and runs everything else. Synthetic data only."""
import gzip
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import asyncpg
import pytest

from beta_fakes import STAGE1_MIN_SQL, TEST_DSN, run
from storage.beta_v0_store import apply_beta_schema

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "deploy" / "restore.sh"
ROLE = "signalbot_beta_feeds"
SRC, LIVE, COPY = "beta_restore_src", "beta_restore_live", "beta_restore_copy"

pytestmark = [
    pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)"),
    pytest.mark.skipif(shutil.which("psql") is None or shutil.which("pg_dump") is None,
                       reason="needs the psql and pg_dump clients"),
]


def _dsn(db):
    u = urlparse(TEST_DSN)
    return urlunparse(u._replace(path="/" + db))


def _bash(*lines):
    return "\n".join(lines) + "\n"


def test_the_expected_table_list_is_every_beta_table_of_the_schema():
    schema = (ROOT / "storage" / "beta_v0_schema.sql").read_text()
    res = subprocess.run(["bash", "-c", 'source <(sed -n "/^beta_expected_tables()/,/^}/p" "$1"); '
                          'BETA_SCHEMA="$2"; beta_expected_tables', "x", str(SCRIPT),
                          str(ROOT / "storage" / "beta_v0_schema.sql")], capture_output=True, text=True, check=True)
    listed = res.stdout.split()
    assert listed == sorted(set(re.findall(r"CREATE TABLE(?: IF NOT EXISTS)?\s+(beta_[a-z0-9_]+)", schema)))
    assert len(listed) >= 40 and "beta_users" in listed and "beta_claims" in listed


async def _admin(sql):
    c = await asyncpg.connect(TEST_DSN)
    try:
        for s in sql:
            await c.execute(s)
    finally:
        await c.close()


async def _source(drop=None):
    # template0: in CI (timescale image) template1 carries the timescaledb extension, whose catalog would
    # enter the dump and need the pre/post-restore calls the shim skips; the beta tables need no TimescaleDB
    await _admin([f'DROP DATABASE IF EXISTS "{d}"' for d in (SRC, LIVE, COPY)]
                 + [f'CREATE DATABASE "{SRC}" TEMPLATE template0'])
    c = await asyncpg.connect(_dsn(SRC))
    try:
        await c.execute(STAGE1_MIN_SQL)
        await apply_beta_schema(c)
        await c.execute((ROOT / "deploy" / "beta_feeds_role.sql").read_text())     # the role exists on the host
        await c.execute("INSERT INTO klines_1m (exchange, symbol, ts, high, low, close) "
                        "VALUES ('binance', 'BTCUSDT', now(), 1, 1, 1)")
        await c.execute("INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at, "
                        "stopped_at, lang) VALUES (7, 7, 'ACTIVE', now(), now(), NULL, 'ru')")
        if drop:
            await c.execute(f"DROP TABLE {drop} CASCADE")
    finally:
        await c.close()


def _dump(tmp_path, name):
    u = urlparse(TEST_DSN)
    out = tmp_path / name
    dump = subprocess.run(["pg_dump", "-h", u.hostname, "-p", str(u.port or 5432), "-U", u.username or "postgres",
                           "-d", SRC, "--no-owner", "--no-privileges"],
                          capture_output=True, check=True, env={**os.environ, "PGPASSWORD": u.password or ""})
    out.write_bytes(gzip.compress(dump.stdout))
    return out


def _restore(tmp_path, *args, stdin=None):
    u = urlparse(TEST_DSN)
    shim = tmp_path / "bin"
    shim.mkdir(exist_ok=True)
    (shim / "docker").write_text(_bash(
        "#!/bin/sh",
        "# docker exec -i CONTAINER psql ... -> the local psql; TimescaleDB is not in this cluster",
        "shift 3",
        'case "$*" in *timescaledb*) exit 0;; esac',
        'exec "$@" -h "$PGHOST" -p "$PGPORT"'))
    (shim / "docker").chmod(0o755)
    env = {**os.environ, "PATH": f"{shim}:{os.environ['PATH']}", "PGHOST": u.hostname, "PGPORT": str(u.port or 5432),
           "PGPASSWORD": u.password or "", "POSTGRES_USER": u.username or "postgres", "POSTGRES_DB": LIVE,
           "BACKUP_DIR": str(tmp_path)}
    return subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=180,
                          input=stdin)


async def _feed_insert_allowed(db):
    c = await asyncpg.connect(_dsn(db))
    try:
        return await c.fetchval(f"SELECT has_table_privilege('{ROLE}', 'beta_feed_metrics_5m', 'INSERT')")
    finally:
        await c.close()


async def _selftest_dbs():
    c = await asyncpg.connect(TEST_DSN)
    try:
        return await c.fetchval("SELECT count(*) FROM pg_database WHERE datname LIKE 'btcbot_restore_selftest_%'")
    finally:
        await c.close()


def test_the_self_test_checks_the_beta_tables_and_the_feed_role(tmp_path):
    run(_source())
    dump = _dump(tmp_path, "btcbot_20261006T031500Z.sql.gz")
    res = _restore(tmp_path, "--self-test", str(dump))
    assert res.returncode == 0, res.stdout + res.stderr
    out = res.stdout
    assert "klines_1m rows in restored copy: 1" in out
    assert re.search(r"all \d+ beta tables present", out) and "the current beta schema applies" in out
    assert "beta_users rows: 1" in out
    assert f"research feed role {ROLE}: grants re-applied" in out and "SELF_TEST_RESULT: PASS" in out
    assert run(_selftest_dbs()) == 0                                  # the throwaway copy is always dropped

    # a dump that lost a beta table fails, and names it
    run(_source(drop="beta_claims"))
    bad = _restore(tmp_path, "--self-test", str(_dump(tmp_path, "btcbot_20261006T041500Z.sql.gz")))
    assert bad.returncode == 1
    assert "beta tables missing from the restored copy: beta_claims" in bad.stdout
    assert "SELF_TEST_RESULT: FAIL (beta tables or grants)" in bad.stdout
    assert run(_selftest_dbs()) == 0
    run(_admin([f'DROP DATABASE IF EXISTS "{SRC}"']))


def test_a_restore_carries_no_grants_and_force_live_re_grants_the_feed_role(tmp_path):
    run(_source())
    dump = _dump(tmp_path, "btcbot_20261006T031500Z.sql.gz")
    # a plain restore into a new database: the dump has no privileges, so the feed role reaches nothing
    plain = _restore(tmp_path, str(dump), COPY)
    assert plain.returncode == 0, plain.stderr
    assert run(_feed_insert_allowed(COPY)) is False
    # over the live database: the confirmation phrase is required, and the grants come back
    assert _restore(tmp_path, "--force-live", str(dump), stdin="no\n").returncode == 1
    live = _restore(tmp_path, "--force-live", str(dump), stdin="RESTORE-OVER-LIVE\n")
    assert live.returncode == 0, live.stdout + live.stderr
    assert f"research feed role {ROLE}: grants re-applied in {LIVE}" in live.stdout
    assert "install_beta_feeds_role.sh" in live.stdout
    assert run(_feed_insert_allowed(LIVE)) is True
    run(_admin([f'DROP DATABASE IF EXISTS "{d}"' for d in (SRC, LIVE, COPY)]))
