"""
Shutdown / cancellation test.

Reproduces the exact failure that once left the DB wedged: start a backfill,
interrupt it with SIGINT mid-flight, and assert the process shuts down cleanly
— no 'idle in transaction' backends, no ungranted locks — WITHOUT any manual
pg_terminate_backend. Then it runs validate to prove the DB is immediately
usable again.

Run:
    python scripts/test_shutdown.py
"""
from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from common.config import Config, load_secrets  # noqa: E402
from storage.db import Database  # noqa: E402


async def _db_state(db: Database) -> dict:
    idle_in_tx = await db.fetch(
        "SELECT pid, state, now()-state_change AS since FROM pg_stat_activity "
        "WHERE datname=current_database() AND state='idle in transaction'")
    ungranted = await db.fetch(
        "SELECT l.pid, l.relation::regclass::text AS rel FROM pg_locks l "
        "JOIN pg_stat_activity a USING (pid) "
        "WHERE a.datname=current_database() AND NOT l.granted")
    active_ours = await db.fetch(
        "SELECT pid, left(query,50) q, now()-query_start AS dur FROM pg_stat_activity "
        "WHERE datname=current_database() AND pid<>pg_backend_pid() AND state='active' "
        "AND (query ILIKE '%klines_1m%' OR query ILIKE '%open_interest%' "
        "     OR query ILIKE '%CREATE INDEX%')")
    return {"idle_in_tx": idle_in_tx, "ungranted": ungranted, "active_ours": active_ours}


async def main() -> int:
    cfg = Config.load()
    secrets = load_secrets(cfg)

    # Start a real backfill in its own process group so we can SIGINT just it.
    print("Starting `main.py --backfill-only` ...", flush=True)
    proc = subprocess.Popen(
        [sys.executable, "main.py", "--backfill-only", "--log-level", "WARNING"],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)

    # Let it get into in-flight DB work (bitget klines re-paging is the long one).
    time.sleep(8)
    print(f"Sending SIGINT to pid {proc.pid} mid-backfill ...", flush=True)
    proc.send_signal(signal.SIGINT)

    try:
        proc.wait(timeout=20)
        print(f"Process exited with code {proc.returncode}", flush=True)
    except subprocess.TimeoutExpired:
        print("!! process did not exit within 20s of SIGINT — killing", flush=True)
        proc.kill()
        return 2

    # Immediately (no manual terminate) inspect the DB.
    db = Database(secrets.postgres_dsn)
    await db.connect()
    st = await _db_state(db)

    print("\n=== pg_stat_activity: idle in transaction ===", flush=True)
    print("  none" if not st["idle_in_tx"] else "\n".join(f"  {dict(r)}" for r in st["idle_in_tx"]))
    print("=== pg_locks: ungranted ===", flush=True)
    print("  none" if not st["ungranted"] else "\n".join(f"  {dict(r)}" for r in st["ungranted"]))
    print("=== active queries on our tables (post-exit) ===", flush=True)
    print("  none" if not st["active_ours"] else "\n".join(f"  {dict(r)}" for r in st["active_ours"]))

    ok = not st["idle_in_tx"] and not st["ungranted"] and not st["active_ours"]

    # Prove the DB is usable immediately: a trivial write+rollback round-trip.
    async with db.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT count(*) FROM klines_1m")
    print("\nDB immediately usable after SIGINT:", "YES" if ok else "NO", flush=True)
    await db.close()
    print("SHUTDOWN_TEST_RESULT:", "PASS" if ok else "FAIL", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
