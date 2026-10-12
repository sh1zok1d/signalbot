"""Apply the paired-shadow tables to an explicitly named database.

The production schema applicator does not call this. Set
PAIRED_SHADOW_SCHEMA_APPROVED=1 only after the owner has allowed the tables.
The script does not read BETA_DSN and does not print the connection string.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_SCHEMA = Path(__file__).resolve().parents[2] / "storage" / "beta_paired_shadow_schema.sql"


def main(argv: list) -> int:
    if os.environ.get("PAIRED_SHADOW_SCHEMA_APPROVED") != "1":
        print("paired shadow schema was not applied: owner approval is not set", file=sys.stderr)
        return 2
    if len(argv) != 2:
        print("usage: PAIRED_SHADOW_SCHEMA_APPROVED=1 python3 scripts/beta/apply_paired_shadow_schema.py DSN",
              file=sys.stderr)
        return 1
    if not _SCHEMA.is_file():
        print("paired shadow schema file is missing", file=sys.stderr)
        return 1
    completed = subprocess.run(
        ["psql", argv[1], "-X", "-v", "ON_ERROR_STOP=1", "-f", str(_SCHEMA)],
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
