#!/usr/bin/env python3
"""One paired-shadow hour.

A file record is planned and not written unless ``--write`` and
``PAIRED_SHADOW_HOUR_APPROVED=1``. ``--from-live`` builds the record from the
V1 statistics row and the W_L1 snapshot on one market anchor, and refuses when
either is unavailable. The database URL is ``PAIRED_SHADOW_DSN``, never an
argument, and it is not printed.

``--bars-from-db`` scores elapsed anchors from the same bar grid the product
reads. Without a bar source, settlement launches and reports ``NO_BARS``.
"""
from __future__ import annotations

import asyncio
import fcntl
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from beta.paired_shadow import DEFAULT_SETTLE_BATCHES, DEFAULT_SETTLE_LIMIT, execute_hour, plan_shadow_record
from beta.paired_shadow_host import (
    HOUR_APPROVED, approved, require_dsn, snapshot_directory,
)
from beta.rangecast_shadow import issue_live_record, issue_summary

UTC = timezone.utc


def main(argv: list) -> int:
    opts = _parse(argv[1:])
    if opts["write"] and not approved(HOUR_APPROVED):
        print("paired shadow hour was not written: owner approval is not set", file=sys.stderr)
        return 2
    try:
        if opts["from_live"] or opts["write"] or opts["bars_from_db"]:
            dsn = require_dsn(argv[1:])
        else:
            dsn = None
    except SystemExit as exc:
        return int(exc.code)
    if opts["from_live"]:
        now = datetime.now(UTC)
        try:
            market = asyncio.run(_market(dsn, now, opts["snapshot_dir"]))
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"status": "NOT_COMPUTABLE", "reason": type(exc).__name__, "written": False},
                             sort_keys=True))
            return 1
        record = issue_live_record(
            market["snap"], v1_state=market["v1_state"], v1_model=market["v1_model"],
            v2_status=market["v2_status"], v2_reason=market["v2_reason"],
            v2_model=market["v2_model"], v1_stats_pk=market["v1_stats_pk"],
        )
        if record.get("status") != "OK":
            summary = issue_summary(record)
            summary["written"] = False
            print(json.dumps(summary, sort_keys=True))
            return 3
        bars = market["bars"] if opts["bars_from_db"] else _file_bars(opts["bars_path"])
    else:
        if opts["record_path"] is None:
            print("usage: python3 scripts/beta/run_paired_shadow_hour.py RECORD.json", file=sys.stderr)
            return 2
        record = json.loads(Path(opts["record_path"]).read_text(encoding="utf-8"))
        bars = _file_bars(opts["bars_path"])
        if opts["bars_from_db"]:
            try:
                bars = asyncio.run(_bars_only(dsn, datetime.now(UTC)))
            except Exception as exc:  # noqa: BLE001
                print(json.dumps({"status": "NO_BARS", "reason": type(exc).__name__, "written": False},
                                 sort_keys=True))
                return 1
            if bars is None or getattr(bars, "n", 0) <= 0:
                print(json.dumps({"status": "NO_BARS", "reason": "EMPTY_GRID", "written": False}, sort_keys=True))
                return 1
    if opts["bars_from_db"] and (bars is None or getattr(bars, "n", 0) <= 0):
        print(json.dumps({"status": "NO_BARS", "reason": "EMPTY_GRID", "written": False}, sort_keys=True))
        return 1
    if not opts["write"]:
        planned = plan_shadow_record(record, issue_slot=_slot(record))
        print(json.dumps({
            "status": planned["status"], "reason": planned["reason"],
            "issue_slot": _slot(record).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "n_issues": len(planned["rows"]), "horizons": planned["horizons"],
            "written": False, "settlement": {"launched": False},
        }, sort_keys=True))
        return 0
    lock = _lock()
    if lock is None:
        print(json.dumps({"status": "BUSY", "reason": "HOUR_LOCK_HELD", "written": False}, sort_keys=True))
        return 0
    from beta.paired_shadow_pg import PgShadowLedger
    result = execute_hour(
        record, PgShadowLedger(dsn), issue_slot=_slot(record), allow_write=True,
        bars=bars, now=datetime.now(UTC), score=True, settle_limit=opts["settle_limit"],
        settle_batches=opts["settle_batches"], report=False,
    )
    settlement = result["settlement"]
    print(json.dumps({
        "status": result["status"], "reason": result["reason"],
        "issue_slot": _slot(record).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inserted": result["inserted"], "kept": result["kept"], "horizons": result["horizons"],
        "written": result["written"],
        "settlement": {
            "launched": settlement["launched"], "status": settlement["status"],
            "limit": settlement["limit"], "batches": settlement.get("batches", 0),
            "selected": settlement["selected"], "stored": settlement["stored"],
            "kept": settlement["kept"], "pending": settlement["pending"],
        },
    }, sort_keys=True))
    return 0


async def _market(dsn: str, now: datetime, snapshot_dir: Path) -> dict:
    from beta.paired_shadow_host import load_market
    return await load_market(dsn, now=now, snapshot_dir=snapshot_dir)


async def _bars_only(dsn: str, now: datetime):
    market = await _market(dsn, now, snapshot_directory())
    return market["bars"]


def _file_bars(path):
    if not path:
        return None
    from beta.hist_series import bars_from_rows
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload["bars"] if isinstance(payload, dict) else payload
    return bars_from_rows(rows)


def _lock():
    directory = os.environ.get("RUNTIME_DIRECTORY")
    path = Path(directory) / "hour.lock" if directory else Path("/tmp/paired-shadow-hour.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def _parse(argv: list) -> dict:
    opts = {
        "write": False, "from_live": False, "bars_from_db": False, "bars_path": None,
        "record_path": None, "settle_limit": DEFAULT_SETTLE_LIMIT,
        "settle_batches": DEFAULT_SETTLE_BATCHES,
        "snapshot_dir": None,
    }
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--write":
            opts["write"] = True
            index += 1
            continue
        if arg == "--from-live":
            opts["from_live"] = True
            index += 1
            continue
        if arg == "--bars-from-db":
            opts["bars_from_db"] = True
            index += 1
            continue
        if arg == "--bars":
            opts["bars_path"] = argv[index + 1]
            index += 2
            continue
        if arg == "--settle-limit":
            opts["settle_limit"] = int(argv[index + 1])
            index += 2
            continue
        if arg == "--settle-batches":
            opts["settle_batches"] = int(argv[index + 1])
            index += 2
            continue
        if arg == "--snapshot-dir":
            opts["snapshot_dir"] = Path(argv[index + 1])
            index += 2
            continue
        if opts["record_path"] is None and not arg.startswith("--"):
            opts["record_path"] = arg
            index += 1
            continue
        print("usage: python3 scripts/beta/run_paired_shadow_hour.py "
              "[--from-live] [--write] [--bars-from-db | --bars BARS.json] [RECORD.json]",
              file=sys.stderr)
        raise SystemExit(2)
    if opts["bars_path"] and opts["bars_from_db"]:
        print("pass either --bars or --bars-from-db", file=sys.stderr)
        raise SystemExit(2)
    if opts["snapshot_dir"] is None:
        try:
            opts["snapshot_dir"] = snapshot_directory()
        except RuntimeError as exc:
            print(json.dumps({"status": "NOT_COMPUTABLE", "reason": str(exc), "written": False},
                             sort_keys=True))
            raise SystemExit(1) from None
    return opts


def _slot(record: dict) -> datetime:
    raw = record.get("as_of")
    if not raw:
        return datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(UTC)
    return moment.replace(minute=0, second=0, microsecond=0)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
