#!/usr/bin/env python3
"""Write one W_L1 snapshot inside STATE_DIRECTORY and show that the rest is read-only.

This is a sandbox probe, not a nightly fit. It runs only when
PAIRED_SHADOW_SANDBOX_PROBE=1. The JSON result has no path and no connection string.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from beta.hist_series import bars_from_rows
from beta.paired_shadow_host import snapshot_directory
from beta.rangecast_shadow import OK, SnapshotStore, fit_nightly_snapshot

UTC = timezone.utc


def main(argv: list) -> int:
    if len(argv) != 1 or os.environ.get("PAIRED_SHADOW_SANDBOX_PROBE") != "1":
        print("usage: PAIRED_SHADOW_SANDBOX_PROBE=1 python3 scripts/beta/paired_shadow_sandbox_probe.py",
              file=sys.stderr)
        return 2
    if not (os.environ.get("STATE_DIRECTORY") or "").strip():
        print(json.dumps({"status": "FAIL", "reason": "STATE_DIRECTORY_UNSET"}, sort_keys=True))
        return 1
    try:
        root = snapshot_directory()
    except RuntimeError as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, sort_keys=True))
        return 1
    outside_refused = _outside_write_refused()
    end = datetime(2026, 5, 1, tzinfo=UTC) + timedelta(days=140)
    rows, _oi = _synthetic_rows(datetime(2026, 5, 1, tzinfo=UTC), 140, seed=9)
    bars = bars_from_rows(rows)
    record = fit_nightly_snapshot(bars, calendar={"events": [], "version": "SANDBOX_PROBE"}, built_at=end)
    stored = SnapshotStore(root).put(record)
    status, _reason, got = SnapshotStore(root).select(end + timedelta(hours=1))
    mode = oct(Path(stored["path"]).stat().st_mode & 0o777)
    ok = stored["stored"] and status == OK and got is not None and outside_refused and mode == "0o600"
    print(json.dumps({
        "status": "OK" if ok else "FAIL",
        "snapshot": status,
        "stored": bool(stored["stored"]),
        "outside_refused": outside_refused,
        "mode": mode,
    }, sort_keys=True))
    return 0 if ok else 1


def _synthetic_rows(start: datetime, days: int, *, seed: int):
    path = _ROOT / "tests/beta/v2_fakes.py"
    spec = importlib.util.spec_from_file_location("paired_shadow_v2_fakes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.synthetic_rows(start, days, seed=seed)


def _outside_write_refused() -> bool:
    target = Path("/var/lib/paired-shadow-sandbox-outside")
    try:
        target.mkdir(parents=True, exist_ok=True)
        (target / "no.json").write_text("{}\n", encoding="utf-8")
    except OSError:
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
