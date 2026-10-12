"""Dry-run one paired-forecast record.

The default prints statuses and issue counts and writes nothing. ``--write`` needs
``PAIRED_SHADOW_HOUR_APPROVED=1`` and an explicit DSN argument. That variable is
not set for production. A write records the hour and then launches settlement of
elapsed, not-yet-scored anchors. ``--bars`` supplies the 5m rows settlement scores.
Without bars, settlement launches and reports ``NO_BARS``. The script does not read
``BETA_DSN`` and does not print the connection string. It does not load the full journal.
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

from beta.paired_shadow import DEFAULT_SETTLE_BATCHES, DEFAULT_SETTLE_LIMIT, execute_hour, plan_shadow_record

UTC = timezone.utc


def main(argv: list) -> int:
    write, bars_path, settle_limit, settle_batches, args = _parse(argv[1:])
    if write and os.environ.get("PAIRED_SHADOW_HOUR_APPROVED") != "1":
        print("paired shadow hour was not written: owner approval is not set", file=sys.stderr)
        return 2
    if write and len(args) != 2:
        print("usage: PAIRED_SHADOW_HOUR_APPROVED=1 python3 scripts/beta/run_paired_shadow_hour.py "
              "--write RECORD.json DSN [--bars BARS.json] [--settle-limit N] [--settle-batches N]",
              file=sys.stderr)
        return 1
    if not write and (len(args) != 1 or bars_path or settle_limit != DEFAULT_SETTLE_LIMIT):
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
            "settlement": {"launched": False},
        }
        print(json.dumps(summary, sort_keys=True))
        return 0
    from beta.hist_series import bars_from_rows
    from beta.paired_shadow_pg import PgShadowLedger
    bars = None
    if bars_path:
        payload = json.loads(Path(bars_path).read_text(encoding="utf-8"))
        rows = payload["bars"] if isinstance(payload, dict) else payload
        bars = bars_from_rows(rows)
    result = execute_hour(
        record, PgShadowLedger(args[1]), issue_slot=issue_slot, allow_write=True,
        bars=bars, now=datetime.now(UTC), score=True, settle_limit=settle_limit,
        settle_batches=settle_batches, report=False,
    )
    settlement = result["settlement"]
    print(json.dumps({
        "status": result["status"],
        "reason": result["reason"],
        "issue_slot": issue_slot.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inserted": result["inserted"],
        "kept": result["kept"],
        "horizons": result["horizons"],
        "written": result["written"],
        "settlement": {
            "launched": settlement["launched"],
            "status": settlement["status"],
            "limit": settlement["limit"],
            "batches": settlement.get("batches", 0),
            "selected": settlement["selected"],
            "stored": settlement["stored"],
            "kept": settlement["kept"],
            "pending": settlement["pending"],
        },
    }, sort_keys=True))
    return 0


def _parse(argv: list) -> tuple:
    write = False
    bars_path = None
    settle_limit = DEFAULT_SETTLE_LIMIT
    settle_batches = DEFAULT_SETTLE_BATCHES
    args = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--write":
            write = True
            index += 1
            continue
        if arg == "--bars":
            bars_path = argv[index + 1]
            index += 2
            continue
        if arg == "--settle-limit":
            settle_limit = int(argv[index + 1])
            index += 2
            continue
        if arg == "--settle-batches":
            settle_batches = int(argv[index + 1])
            index += 2
            continue
        args.append(arg)
        index += 1
    return write, bars_path, settle_limit, settle_batches, args


def _slot(record: dict) -> datetime:
    raw = record.get("as_of")
    if not raw:
        return datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(UTC)
    return moment.replace(minute=0, second=0, microsecond=0)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
