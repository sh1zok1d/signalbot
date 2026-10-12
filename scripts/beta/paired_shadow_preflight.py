#!/usr/bin/env python3
"""Read-only paired-shadow preflight.

Prints deployed SHA, source freshness, PostgreSQL version, free disk, backup
age, scheduler state and the pinned digests. It does not print a connection
URL, a password, a price, or a user row, and it does not write.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from beta.paired_shadow import SHADOW_RECORDING_ENABLED, V1_SPEC_DIGEST, V2_SPEC_DIGEST
from beta.paired_shadow_host import (
    BACKUP_MAX_AGE_H, DEFAULT_SNAPSHOT_DIR, ENV_FILE, MIN_FREE_BYTES, SNAPSHOT_DIR_ENV,
    env_file_status, judge_sources, overall, source_facts,
)

UTC = timezone.utc
UNITS = (
    "signalbot-beta-history.timer",
    "signalbot-beta-outcomes.timer",
    "signalbot-beta-feeds.timer",
    "signalbot-beta-notify.timer",
    "signalbot-beta-detector.timer",
    "signalbot-backup.timer",
    "signalbot-paired-shadow-hour.timer",
    "signalbot-paired-shadow-snapshot.timer",
)


def main(argv: list) -> int:
    if len(argv) != 1:
        print("usage: python3 scripts/beta/paired_shadow_preflight.py", file=sys.stderr)
        return 2
    now = datetime.now(UTC)
    checks = {
        "sha": _sha(_ROOT),
        "env_file": env_file_status(ENV_FILE),
        "digests": _digests(),
        "recording": {"status": "PASS" if SHADOW_RECORDING_ENABLED is False else "FAIL",
                      "reason": None if SHADOW_RECORDING_ENABLED is False else "RECORDING_ENABLED"},
        "sources": _sources(now),
        "disk": _disk(),
        "backup": _backup(_ROOT, now),
        "schedulers": _schedulers(),
        "snapshot": _snapshot(now),
    }
    report = {"schema": "PAIRED_SHADOW_PREFLIGHT_V1", "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "status": overall(checks), "checks": checks}
    print(json.dumps(report, sort_keys=True))
    return {"PASS": 0, "NOT_READY": 3, "FAIL": 1}[report["status"]]


def _sha(root: Path) -> dict:
    build = root / "BUILD_SHA"
    file_sha = build.read_text(encoding="utf-8").strip() if build.is_file() else None
    git_sha = _git_head(root)
    sha = file_sha or git_sha
    if not sha:
        return {"status": "NOT_READY", "reason": "SHA_UNKNOWN"}
    expected = (os.environ.get("PAIRED_SHADOW_EXPECTED_SHA") or "").strip() or None
    status, reason = "PASS", None
    if sha.endswith("-dirty"):
        status, reason = "FAIL", "DIRTY_TREE"
    elif expected and not sha.startswith(expected):
        status, reason = "FAIL", "SHA_MISMATCH"
    return {"status": status, "reason": reason, "sha": sha, "source": "BUILD_SHA" if file_sha else "git",
            "matches_git": None if not (file_sha and git_sha) else file_sha == git_sha}


def _digests() -> dict:
    try:
        from beta.rangecast_shadow import v1_spec_digest
        from beta.rangecast_v2 import shadow_spec_digest
        v1, v2 = v1_spec_digest(), shadow_spec_digest()
    except Exception as exc:  # noqa: BLE001
        return {"status": "FAIL", "reason": type(exc).__name__}
    match = v1 == V1_SPEC_DIGEST and v2 == V2_SPEC_DIGEST
    return {"status": "PASS" if match else "FAIL", "reason": None if match else "DIGEST_MISMATCH",
            "v1_spec_digest": v1, "v2_spec_digest": v2}


def _sources(now: datetime) -> dict:
    from beta.paired_shadow_host import DSN_ENV
    if not (os.environ.get(DSN_ENV) or "").strip():
        return {"status": "NOT_READY", "reason": "DSN_UNSET"}
    try:
        from beta.paired_shadow_host import require_dsn
        facts = asyncio.run(source_facts(require_dsn(), now=now))
    except Exception as exc:  # noqa: BLE001 - class name only; the URL stays out of the report
        return {"status": "FAIL", "reason": type(exc).__name__}
    verdict = judge_sources(facts)
    return {**facts, "status": verdict["status"], "reason": verdict["reason"]}


def _disk() -> dict:
    path = Path(os.environ.get(SNAPSHOT_DIR_ENV) or DEFAULT_SNAPSHOT_DIR)
    probe = path if path.exists() else path.parent if path.parent.exists() else Path("/")
    free = shutil.disk_usage(probe).free
    return {"status": "PASS" if free >= MIN_FREE_BYTES else "FAIL",
            "reason": None if free >= MIN_FREE_BYTES else "DISK_LOW",
            "path": str(probe), "free_gib": round(free / 1024 ** 3, 2)}


def _backup(root: Path, now: datetime) -> dict:
    shown = _systemctl_show("signalbot-backup.timer")
    if shown is None:
        return {"status": "NOT_READY", "reason": "SYSTEMCTL_UNAVAILABLE"}
    enabled = shown.get("UnitFileState")
    dumps = sorted((root / "backups").glob("btcbot_*.sql.gz"), key=lambda item: item.stat().st_mtime)
    newest = dumps[-1] if dumps else None
    age_h = None if newest is None else round((now.timestamp() - newest.stat().st_mtime) / 3600, 2)
    if enabled not in ("enabled", "static"):
        return {"status": "NOT_READY", "reason": "BACKUP_TIMER_INACTIVE", "unit_state": enabled, "dump_age_h": age_h}
    if age_h is None or age_h > BACKUP_MAX_AGE_H:
        return {"status": "NOT_READY", "reason": "BACKUP_STALE", "unit_state": enabled, "dump_age_h": age_h}
    return {"status": "PASS", "reason": None, "unit_state": enabled, "dump_age_h": age_h,
            "dump_bytes": newest.stat().st_size}


def _schedulers() -> dict:
    listed = []
    paired_on = False
    for unit in UNITS:
        state = _systemctl_show(unit)
        if state is None:
            return {"status": "NOT_READY", "reason": "SYSTEMCTL_UNAVAILABLE"}
        enabled = state.get("UnitFileState")
        listed.append({"unit": unit, "state": enabled})
        if unit.startswith("signalbot-paired-shadow-") and enabled == "enabled":
            paired_on = True
    if all(not item["state"] for item in listed):
        return {"status": "NOT_READY", "reason": "SYSTEMCTL_UNAVAILABLE", "units": listed}
    if paired_on:
        return {"status": "NOT_READY", "reason": "PAIRED_SHADOW_TIMER_ALREADY_ENABLED", "units": listed}
    return {"status": "PASS", "reason": None, "units": listed}


def _snapshot(now: datetime) -> dict:
    from beta.rangecast_shadow import OK, SnapshotStore
    root = Path(os.environ.get(SNAPSHOT_DIR_ENV) or DEFAULT_SNAPSHOT_DIR)
    status, reason, record = SnapshotStore(root).select(now)
    return {"status": "PASS" if status == OK else "NOT_READY", "reason": reason,
            "snapshot": status, "files": len(list(root.glob('*_*.json'))) if root.is_dir() else 0}


def _systemctl_show(unit: str):
    try:
        completed = subprocess.run(
            ["systemctl", "show", unit, "-p", "UnitFileState", "-p", "ActiveState"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0 and "UnitFileState=" not in completed.stdout:
        return {}
    out = {}
    for line in completed.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            out[key] = value
    return out


def _git_head(root: Path):
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
