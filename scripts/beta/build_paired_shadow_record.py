#!/usr/bin/env python3
"""Build one paired-shadow record from the live V1 statistics row and the W_L1 snapshot.

Both models see one market snapshot. A missing, stale or unreadable input writes
no record. The database URL comes from PAIRED_SHADOW_DSN and is not printed.
This command does not write the shadow tables.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from beta.paired_shadow_host import DEFAULT_SNAPSHOT_DIR, SNAPSHOT_DIR_ENV, require_dsn
from beta.rangecast_shadow import issue_live_record, issue_summary

UTC = timezone.utc


def main(argv: list) -> int:
    out_path, snapshot_dir = _parse(argv[1:])
    try:
        dsn = require_dsn(argv[1:])
    except SystemExit as exc:
        return int(exc.code)
    now = datetime.now(UTC)
    try:
        market = asyncio.run(_load(dsn, now, snapshot_dir))
    except Exception as exc:  # noqa: BLE001 - the class name is the only client-visible detail
        print(json.dumps({"status": "NOT_COMPUTABLE", "reason": type(exc).__name__}, sort_keys=True))
        return 1
    record = issue_live_record(
        market["snap"], v1_state=market["v1_state"], v1_model=market["v1_model"],
        v2_status=market["v2_status"], v2_reason=market["v2_reason"], v2_model=market["v2_model"],
        v1_stats_pk=market["v1_stats_pk"],
    )
    summary = issue_summary(record)
    if record.get("status") == "OK" and out_path is not None:
        _write_private(out_path, record)
        summary["record_file"] = str(out_path)
    elif out_path is not None:
        summary["record_file"] = None
    print(json.dumps(summary, sort_keys=True))
    return 0 if record.get("status") == "OK" else 3


async def _load(dsn: str, now: datetime, snapshot_dir: Path) -> dict:
    from beta.paired_shadow_host import load_market
    return await load_market(dsn, now=now, snapshot_dir=snapshot_dir)


def _write_private(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(record, handle, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)


def _parse(argv: list) -> tuple:
    out_path = None
    snapshot_dir = Path(os.environ.get(SNAPSHOT_DIR_ENV) or DEFAULT_SNAPSHOT_DIR)
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--out":
            out_path = Path(argv[index + 1])
            index += 2
            continue
        if arg == "--snapshot-dir":
            snapshot_dir = Path(argv[index + 1])
            index += 2
            continue
        print("usage: PAIRED_SHADOW_DSN=... python3 scripts/beta/build_paired_shadow_record.py "
              "[--out RECORD.json] [--snapshot-dir DIR]", file=sys.stderr)
        raise SystemExit(2)
    return out_path, snapshot_dir


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
