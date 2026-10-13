#!/usr/bin/env python3
"""Block until PAIRED_SHADOW_DSN accepts SELECT 1.

The paired-shadow units cannot read /opt/signalbot/.env. This check uses only
PAIRED_SHADOW_DSN. It does not load the core config or the core database
password. The URL and the password are never printed.

Retry matches deploy/wait_for_infra.py: a 5s connect timeout, then 2s between
attempts, until --timeout. Production units keep wait_for_infra.py.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg  # noqa: E402

from beta.paired_shadow_host import require_dsn  # noqa: E402
from beta.paired_shadow_pg import redact_connection  # noqa: E402


async def wait_for_paired_shadow(dsn: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    last = "Error"
    while True:
        try:
            conn = await asyncpg.connect(dsn, timeout=5)
            try:
                await conn.execute("SELECT 1")
            finally:
                await conn.close()
            print("wait_for_paired_shadow: PostgreSQL ready (SELECT 1 ok)", flush=True)
            return
        except Exception as exc:  # noqa: BLE001 - the class name is redacted; the message is not printed
            last = redact_connection(type(exc).__name__, dsn)
            if time.monotonic() >= deadline:
                print(f"wait_for_paired_shadow: PostgreSQL not ready after {timeout:.0f}s: {last}",
                      file=sys.stderr, flush=True)
                raise SystemExit(1) from None
            await asyncio.sleep(2)


def main(argv: list | None = None) -> None:
    incoming = list(sys.argv[1:] if argv is None else argv)
    # Refuse a URL argument before argparse, which would otherwise echo it.
    dsn = require_dsn(incoming)
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=90.0)
    args = ap.parse_args(incoming)
    asyncio.run(wait_for_paired_shadow(dsn, args.timeout))
    print("wait_for_paired_shadow: infra ready", flush=True)


if __name__ == "__main__":
    main()
