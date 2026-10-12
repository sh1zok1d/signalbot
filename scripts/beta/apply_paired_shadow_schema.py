#!/usr/bin/env python3
"""Apply the paired-shadow tables to the database named by PAIRED_SHADOW_DSN.

The production schema applicator does not call this. Set
PAIRED_SHADOW_SCHEMA_APPROVED=1 only after the owner has allowed the tables.
The URL is not an argument and is not printed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from beta.paired_shadow_host import SCHEMA_APPROVED, approved, require_dsn
from beta.paired_shadow_pg import psql_invocation, redact_connection

_SCHEMA = Path(__file__).resolve().parents[2] / "storage" / "beta_paired_shadow_schema.sql"


def main(argv: list) -> int:
    if argv_has_url(argv[1:]):
        print("refusing: a database URL was passed as an argument", file=sys.stderr)
        return 2
    if not approved(SCHEMA_APPROVED):
        print("paired shadow schema was not applied: owner approval is not set", file=sys.stderr)
        return 2
    if len(argv) != 1:
        print("usage: PAIRED_SHADOW_SCHEMA_APPROVED=1 PAIRED_SHADOW_DSN=... "
              "python3 scripts/beta/apply_paired_shadow_schema.py", file=sys.stderr)
        return 2
    if not _SCHEMA.is_file():
        print("paired shadow schema file is missing", file=sys.stderr)
        return 1
    try:
        dsn = require_dsn()
    except SystemExit as exc:
        return int(exc.code)
    argv_psql, env = psql_invocation(dsn, extra=["-f", str(_SCHEMA)])
    import subprocess
    completed = subprocess.run(argv_psql, check=False, env=env, capture_output=True, text=True)
    if completed.returncode != 0:
        print(redact_connection(completed.stderr or completed.stdout, dsn), file=sys.stderr)
    return completed.returncode


def argv_has_url(argv: list) -> bool:
    from beta.paired_shadow_host import argv_carries_dsn
    return argv_carries_dsn(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
