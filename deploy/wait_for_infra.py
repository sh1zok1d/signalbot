#!/usr/bin/env python
"""Block until infra is actually usable, then exit 0 — used as the
signalbot.service ExecStartPre.

An open TCP port is not enough (Postgres accepts connections before it can serve
queries during init). This performs REAL readiness checks with the project's own
libraries and config, so "ready" means exactly "the bot can connect":
  * Postgres: asyncpg.connect + `SELECT 1`
  * Redis:    redis.asyncio ping

Run via the venv python (has asyncpg + redis). No docker access, no extra host
packages (pg_isready/redis-cli not required).

Usage: python deploy/wait_for_infra.py [--timeout SECONDS]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg  # noqa: E402
import redis.asyncio as aioredis  # noqa: E402

from common.config import Config, load_secrets  # noqa: E402


async def _wait_pg(dsn: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last = None
    while True:
        try:
            conn = await asyncpg.connect(dsn, timeout=5)
            try:
                await conn.execute("SELECT 1")
            finally:
                await conn.close()
            print("wait_for_infra: PostgreSQL ready (SELECT 1 ok)", flush=True)
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            if time.monotonic() >= deadline:
                print(f"wait_for_infra: PostgreSQL not ready after {timeout:.0f}s: {last}",
                      file=sys.stderr, flush=True)
                sys.exit(1)
            await asyncio.sleep(2)


async def _wait_redis(url: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last = None
    while True:
        client = aioredis.from_url(url, decode_responses=True)
        try:
            if await client.ping():
                print("wait_for_infra: Redis ready (PING ok)", flush=True)
                return
        except Exception as exc:  # noqa: BLE001
            last = exc
        finally:
            await client.aclose()
        if time.monotonic() >= deadline:
            print(f"wait_for_infra: Redis not ready after {timeout:.0f}s: {last}",
                  file=sys.stderr, flush=True)
            sys.exit(1)
        await asyncio.sleep(2)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=90.0)
    args = ap.parse_args()
    secrets = load_secrets(Config.load())
    await _wait_pg(secrets.postgres_dsn, args.timeout)
    await _wait_redis(secrets.redis_url, args.timeout)
    print("wait_for_infra: infra ready", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
