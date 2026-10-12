"""Dry-run one paired-forecast record.

The default prints statuses and issue counts and writes nothing. ``--write`` needs
``PAIRED_SHADOW_HOUR_APPROVED=1`` and an explicit DSN argument. That variable is
not set for production. The script does not read ``BETA_DSN`` and does not print
the connection string.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from beta.paired_shadow import execute_hour, plan_shadow_record

UTC = timezone.utc


def main(argv: list) -> int:
    write = "--write" in argv
    args = [arg for arg in argv[1:] if arg != "--write"]
    if write and os.environ.get("PAIRED_SHADOW_HOUR_APPROVED") != "1":
        print("paired shadow hour was not written: owner approval is not set", file=sys.stderr)
        return 2
    if write and len(args) != 2:
        print("usage: PAIRED_SHADOW_HOUR_APPROVED=1 python3 scripts/beta/run_paired_shadow_hour.py "
              "--write RECORD.json DSN", file=sys.stderr)
        return 1
    if not write and len(args) != 1:
        print("usage: python3 scripts/beta/run_paired_shadow_hour.py RECORD.json", file=sys.stderr)
        return 1
    record = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    issue_slot = _slot(record)
    if not write:
        planned = plan_shadow_record(record, issue_slot=issue_slot)
        summary = {
            "status": planned["status"],
            "reason": planned["reason"],
            "issue_slot": issue_slot.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_issues": len(planned["rows"]),
            "horizons": planned["horizons"],
            "written": False,
        }
        print(json.dumps(summary, sort_keys=True))
        return 0
    from beta.paired_shadow_pg import PgShadowLedger
    result = execute_hour(record, PgShadowLedger(args[1]), issue_slot=issue_slot, allow_write=True)
    print(json.dumps({
        "status": result["status"],
        "reason": result["reason"],
        "issue_slot": issue_slot.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inserted": result["inserted"],
        "kept": result["kept"],
        "horizons": result["horizons"],
        "written": result["written"],
    }, sort_keys=True))
    return 0


def _slot(record: dict) -> datetime:
    raw = record.get("as_of")
    if not raw:
        return datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(UTC)
    return moment.replace(minute=0, second=0, microsecond=0)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
