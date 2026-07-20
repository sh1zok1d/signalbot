#!/usr/bin/env python3
"""QA infrastructure smoke test.

Proves the LOCAL TEST TimescaleDB + Redis (docker-compose.test.yml, ports
5433/6380) are reachable through the project's own code and that Stage 1 schema
initialises idempotently — nothing more. It never touches exchanges, the real
production stack, main.py, backfill, live WebSocket clients, or Telegram, and it
must NOT create the Stage 2 schema.

Run via `make qa-infra-smoke` (which brings the test stack up first) or directly:
    SIGNALBOT_ENV_FILE=.env.test .venv/bin/python scripts/qa-smoke.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Pin to the TEST env BEFORE importing the project config (which loads dotenv at
# import time). This guarantees we can never accidentally smoke-test production.
os.environ.setdefault("SIGNALBOT_ENV_FILE", ".env.test")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config import Config, load_secrets          # noqa: E402
from storage.db import Database                          # noqa: E402
from storage.redis_client import RedisState             # noqa: E402

EXPECTED_HOST = "127.0.0.1"
EXPECTED_PG_PORT = 5433
EXPECTED_PG_DB = "signalbot_test"
EXPECTED_REDIS_PORT = 6380
STAGE1_SENTINEL = "exchange_capabilities"     # created by init_schema()
STAGE2_SENTINEL = "consensus_feature_vectors"  # must NOT exist after init_schema()

_passed = 0
_failed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global _passed, _failed
    mark = "PASS" if ok else "FAIL"
    if ok:
        _passed += 1
    else:
        _failed += 1
    line = f"  [{mark}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)


async def main() -> int:
    print(f"QA smoke — env file: {os.environ.get('SIGNALBOT_ENV_FILE')}")

    # 1. Config + secrets load (no secret values printed).
    cfg = Config.load()
    secrets = load_secrets(cfg)
    check("Config.load() + load_secrets()", True)

    # 2. Test Postgres DSN points at the TEST database, not production.
    pg = urlparse(secrets.postgres_dsn)
    pg_db = (pg.path or "").lstrip("/")
    check("Postgres target is the test env",
          pg.hostname == EXPECTED_HOST and pg.port == EXPECTED_PG_PORT
          and pg_db == EXPECTED_PG_DB,
          f"{pg.hostname}:{pg.port}/{pg_db}")
    if not (pg.hostname == EXPECTED_HOST and pg.port == EXPECTED_PG_PORT
            and pg_db == EXPECTED_PG_DB):
        print("  refusing to continue: DSN is not the test database")
        return 1

    # 3. Redis URL points at the TEST instance.
    rd = urlparse(secrets.redis_url)
    check("Redis target is the test env",
          rd.hostname == EXPECTED_HOST and rd.port == EXPECTED_REDIS_PORT,
          f"{rd.hostname}:{rd.port}{rd.path}")

    # 4. Telegram is NOT configured for tests.
    check("Telegram unused (no token/chat)",
          not secrets.telegram_token and not secrets.telegram_chat_id)

    # 5–8. TimescaleDB: connect, init schema twice (idempotent), assert Stage 1
    #      present and Stage 2 absent.
    db = Database(secrets.postgres_dsn)
    await db.connect()
    try:
        check("TimescaleDB connect", True)
        await db.init_schema()
        check("Database.init_schema() (first run)", True)
        await db.init_schema()
        check("Database.init_schema() again (idempotent)", True)

        stage1 = await db.fetchval("SELECT to_regclass($1)", f"public.{STAGE1_SENTINEL}")
        check("Stage 1 schema created", stage1 is not None, STAGE1_SENTINEL)

        stage2 = await db.fetchval("SELECT to_regclass($1)", f"public.{STAGE2_SENTINEL}")
        check("Stage 2 schema NOT auto-created", stage2 is None, STAGE2_SENTINEL)
    finally:
        await db.close()

    # 9–11. Redis: connect (pings), explicit ping, heartbeat round-trip.
    redis = RedisState(secrets.redis_url)
    await redis.connect()
    try:
        check("Redis connect", True)
        pong = await redis.client.ping()
        check("Redis PING", bool(pong))
        await redis.set_heartbeat()
        hb = await redis.get_heartbeat()
        check("Redis heartbeat write+read", isinstance(hb, float))
    finally:
        await redis.close()

    print(f"\nQA smoke: {_passed} passed, {_failed} failed")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except SystemExit:
        raise
    except Exception as exc:  # surface the real project error, do not mask it
        print(f"\nQA smoke crashed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
