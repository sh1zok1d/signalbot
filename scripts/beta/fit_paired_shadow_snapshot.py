#!/usr/bin/env python3
"""Fit one W_L1 snapshot on the V1 nightly grid and store it beside V1.

Does not call ``fit_range_model`` and does not insert ``beta_hist_stats``.
The V1 build keeps its own lock and its own row. Set
PAIRED_SHADOW_SNAPSHOT_APPROVED=1 only when the owner has allowed this fit.
The database URL comes from PAIRED_SHADOW_DSN and is not printed.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from beta.paired_shadow_host import (
    SNAPSHOT_APPROVED, SNAPSHOT_LOCK_KEY, approved, require_dsn, snapshot_directory,
)
from beta.rangecast_shadow import OK, SnapshotStore, fit_nightly_snapshot

UTC = timezone.utc


def main(argv: list) -> int:
    if len(argv) != 1:
        print("usage: PAIRED_SHADOW_SNAPSHOT_APPROVED=1 PAIRED_SHADOW_DSN=... "
              "python3 scripts/beta/fit_paired_shadow_snapshot.py", file=sys.stderr)
        return 2
    if not approved(SNAPSHOT_APPROVED):
        print("W_L1 snapshot was not fitted: owner approval is not set", file=sys.stderr)
        return 2
    try:
        dsn = require_dsn()
    except SystemExit as exc:
        return int(exc.code)
    try:
        root = snapshot_directory()
    except RuntimeError as exc:
        print(json.dumps({"status": "NOT_COMPUTABLE", "reason": str(exc)}, sort_keys=True))
        return 1
    now = datetime.now(UTC)
    try:
        outcome = asyncio.run(_fit(dsn, now, root))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"status": "NOT_COMPUTABLE", "reason": type(exc).__name__}, sort_keys=True))
        return 1
    print(json.dumps(outcome, sort_keys=True))
    return 0 if outcome["status"] == OK else 3


async def _fit(dsn: str, now: datetime, root: Path) -> dict:
    from storage.db import Database

    from beta.calendar_events import load_calendar
    from beta.history_stats import MIN_HISTORY_DAYS, load_history_grid
    from beta.rangecast_shadow import ShadowModelError

    db = Database(dsn)
    await db.connect()
    try:
        async with db.beta_store().advisory_lock(SNAPSHOT_LOCK_KEY) as acquired:
            if not acquired:
                return {"status": "BUSY", "reason": "SNAPSHOT_LOCK_HELD"}
            async with db.beta_store().connect() as conn:
                bounds = await conn.hist_bounds()
                if bounds["bars_from"] is None:
                    return {"status": "NO_HISTORY", "reason": "NO_HIST_BARS"}
                end = min(bounds["bars_through"] + timedelta(minutes=5),
                          now.replace(hour=0, minute=0, second=0, microsecond=0))
                start = bounds["bars_from"]
                if (end - start).days < MIN_HISTORY_DAYS:
                    return {"status": "NOT_ENOUGH_HISTORY", "reason": "GRID_SHORTER_THAN_V1",
                            "days": (end - start).days}
                bars = await load_history_grid(conn, start=start, end=end)
            store = SnapshotStore(root)
            before, before_reason, _ = store.select(now)
            try:
                record = fit_nightly_snapshot(bars, calendar=load_calendar(), built_at=now)
            except ShadowModelError as exc:
                return {"status": "NOT_COMPUTABLE", "reason": str(exc).split(":", 1)[0][:80],
                        "previous": before}
            saved = store.put(record)
            status, reason, selected = store.select(now)
            return {
                "status": status,
                "reason": reason,
                "previous": before,
                "previous_reason": before_reason,
                "stored": bool(saved["stored"]),
                "replaced_corrupt": bool(saved.get("replaced_corrupt")),
                "snapshot_id": None if selected is None else selected.get("snapshot_id"),
                "spec_digest": record.get("spec_digest"),
                "data_through": record.get("data_through"),
                "built_at": record.get("built_at"),
            }
    finally:
        await db.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
