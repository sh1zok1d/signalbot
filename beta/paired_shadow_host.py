"""Host-side helpers for the paired shadow. Nothing here starts a timer or writes a forecast.

The database URL is read from ``PAIRED_SHADOW_DSN``. It is never taken from
process arguments and never printed. The product bot does not import this module.
"""
from __future__ import annotations

import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional, Sequence

DSN_ENV = "PAIRED_SHADOW_DSN"
ENV_FILE = Path("/opt/signalbot/.env.paired-shadow")
SNAPSHOT_DIR_ENV = "PAIRED_SHADOW_SNAPSHOT_DIR"
DEFAULT_SNAPSHOT_DIR = Path("/var/lib/signalbot/paired-shadow/snapshots")
HOUR_APPROVED = "PAIRED_SHADOW_HOUR_APPROVED"
SCHEMA_APPROVED = "PAIRED_SHADOW_SCHEMA_APPROVED"
SNAPSHOT_APPROVED = "PAIRED_SHADOW_SNAPSHOT_APPROVED"
SNAPSHOT_LOCK_KEY = 7_311_000_457
MIN_FREE_BYTES = 2 * 1024 ** 3
BACKUP_MAX_AGE_H = 36


def argv_carries_dsn(argv: Sequence[str]) -> bool:
    return any("://" in arg or arg.lower().startswith("postgres") for arg in argv)


def require_dsn(argv: Sequence[str] = ()) -> str:
    """The URL from the environment. Exit 2 when it is missing or was passed on the command line."""
    if argv_carries_dsn(argv):
        print("refusing: a database URL was passed as an argument", file=sys.stderr)
        raise SystemExit(2)
    raw = (os.environ.get(DSN_ENV) or "").strip()
    if not raw or any(char in raw for char in "\n\r\x00"):
        print(f"{DSN_ENV} is not set", file=sys.stderr)
        raise SystemExit(2)
    return raw


def approved(name: str) -> bool:
    return os.environ.get(name) == "1"


def write_env_file(path: Path, dsn: str, *, replace: bool = False) -> dict:
    """Store the URL in a new file, mode 0600. The return value has no secret."""
    if not dsn or any(char in dsn for char in "\n\r\x00"):
        raise ValueError("DSN_UNUSABLE")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if replace else os.O_EXCL)
    fd = os.open(path, flags, 0o600)
    try:
        payload = f'{DSN_ENV}="{_env_quote(dsn)}"\n'.encode("utf-8")
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(path, 0o600)
    return {"path": str(path), "mode": "0600", "bytes": path.stat().st_size}


def file_mode(path: Path) -> Optional[str]:
    try:
        return oct(path.stat().st_mode & 0o777)[2:]
    except OSError:
        return None


def env_file_status(path: Path = ENV_FILE) -> dict:
    """Whether the connection file exists and is unreadable by group and others. The file is not opened."""
    if not path.exists():
        return {"status": "NOT_READY", "reason": "ENV_FILE_MISSING", "path": str(path)}
    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        return {"status": "FAIL", "reason": "ENV_FILE_READABLE_BY_OTHERS", "path": str(path),
                "mode": oct(mode & 0o777)[2:]}
    return {"status": "PASS", "reason": None, "path": str(path), "mode": oct(mode & 0o777)[2:]}


def overall(checks: Mapping[str, Mapping]) -> str:
    statuses = [str(item.get("status") or "FAIL") for item in checks.values()]
    if any(status == "FAIL" for status in statuses):
        return "FAIL"
    if any(status in ("NOT_READY", "SKIPPED") for status in statuses):
        return "NOT_READY"
    return "PASS"


def _env_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


async def load_market(dsn: str, *, now: datetime, snapshot_dir: Path) -> dict:
    """The hour's inputs: one bar grid, the fresh V1 statistics row, and the W_L1 snapshot.

    Read-only. The returned bars are the same object the record and settlement share.
    """
    from storage.db import Database

    from beta.calendar_events import load_calendar
    from beta.config import BetaConfig
    from beta.decision import latest_stats, load_live_bars, stats_stale
    from beta.rangecast_shadow import Snapshot, SnapshotStore

    cfg = BetaConfig.load()
    db = Database(dsn)
    await db.connect()
    try:
        async with db.beta_store().connect() as conn:
            bars, price, price_ts = await load_live_bars(conn, cfg, now=now)
            stats = await latest_stats(conn, now=now)
    finally:
        await db.close()
    if stats is None or not stats.get("range_model"):
        v1_state, v1_model, stats_pk = "missing", None, None
    elif stats_stale(stats, now):
        v1_state, v1_model, stats_pk = "stale", None, stats.get("_stats_pk")
    else:
        v1_state, v1_model, stats_pk = "ok", stats.get("range_model"), stats.get("_stats_pk")
    v2_status, v2_reason, v2_record = SnapshotStore(snapshot_dir).select(now)
    v2_model = None if v2_record is None else v2_record.get("model")
    snap = Snapshot(bars=bars, price=price, price_ts=price_ts, now=now, calendar=load_calendar())
    return {"snap": snap, "bars": bars, "v1_state": v1_state, "v1_model": v1_model,
            "v1_stats_pk": stats_pk, "v2_status": v2_status, "v2_reason": v2_reason,
            "v2_model": v2_model}


async def source_facts(dsn: str, *, now: datetime) -> dict:
    """Counts and timestamps of the market tables. No prices and no user rows."""
    from storage.db import Database

    from beta.config import BetaConfig
    from beta.decision import STATS_MAX_AGE

    cfg = BetaConfig.load()
    db = Database(dsn)
    await db.connect()
    try:
        async with db.beta_store().connect() as conn:
            version = await conn.conn.fetchval("SHOW server_version")
            bounds = await conn.hist_bounds()
            meta = await conn.fetch_latest_hist_stats_meta()
            live_ts = await conn.conn.fetchval(
                "SELECT max(ts) FROM klines_1m WHERE exchange = $1 AND symbol = $2",
                "binance", cfg.symbol)
            shadow = await conn.conn.fetchval("SELECT to_regclass('public.beta_shadow_anchors')")
    finally:
        await db.close()
    bars_through = bounds.get("bars_through")
    built = None if meta is None else meta.get("built_at")
    return {
        "status": "PASS",
        "postgres": str(version),
        "symbol": cfg.symbol,
        "hist_bars": int(bounds.get("bars_count") or 0),
        "hist_through": _iso(bars_through),
        "hist_age_h": _age_h(now, bars_through),
        "oi_rows": int(bounds.get("oi_count") or 0),
        "stats_built_at": _iso(built),
        "stats_age_h": _age_h(now, built),
        "stats_stale": built is None or (now - built) > STATS_MAX_AGE,
        "live_1m_at": _iso(live_ts),
        "live_age_min": None if live_ts is None else round((now - live_ts).total_seconds() / 60, 1),
        "shadow_tables": shadow is not None,
    }


def judge_sources(facts: Mapping) -> dict:
    if facts.get("status") != "PASS":
        return {"status": facts.get("status") or "FAIL", "reason": facts.get("reason") or "SOURCE_UNREADABLE"}
    if facts.get("hist_bars", 0) <= 0 or facts.get("stats_built_at") is None:
        return {"status": "NOT_READY", "reason": "NO_HISTORY"}
    if facts.get("stats_stale") or (facts.get("hist_age_h") or 999) > 48:
        return {"status": "NOT_READY", "reason": "STALE_HISTORY"}
    if facts.get("live_age_min") is None or facts["live_age_min"] > 15:
        return {"status": "NOT_READY", "reason": "STALE_LIVE_BARS"}
    return {"status": "PASS", "reason": None}


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def _age_h(now: datetime, earlier) -> Optional[float]:
    if earlier is None:
        return None
    if earlier.tzinfo is None:
        earlier = earlier.replace(tzinfo=timezone.utc)
    return round((now - earlier).total_seconds() / 3600, 2)
