"""Stage-1 startup-recovery barrier and bounded post-recovery repair (pure parts).

After a host power cycle Stage-1 restores the outage's raw 1m bars by its startup
gap-fill. A detector run that catches the outage buckets up BEFORE that gap-fill
is done records LIVE rows without the raw bars (2026-10-02 incident). Two parts:

- `startup_gate`: the detector does not catch up while the newest Stage-1
  startup-recovery row (common.startup_recovery, in PostgreSQL) is not ready.
  A row written before this host booted is a previous boot's: the current
  Stage-1 has not started its recovery yet. The wait is bounded: after
  `max_wait` the detector proceeds (OVERDUE, owner alert) because waiting
  longer than its catch-up bound would turn buckets into DETECTION_GAP.
- `stale_buckets`: after a ready recovery, the decided buckets of the recovery
  window whose stored per-venue bar count is below the raw count now in
  PostgreSQL. The detector re-checks exactly those through the existing
  CORRECTION_CHECK path (append-only; no episode, transition or push).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from common.startup_recovery import READY_STATUSES, RUNNING

from .state_tape import BUCKET

NO_SIGNAL = "NO_SIGNAL"                                 # no Stage-1 row at all (pre-signal deployment)
WAITING_FOR_STAGE1_START = "WAITING_FOR_STAGE1_START"   # newest row is a previous boot's
RECOVERING = "RECOVERING"                               # Stage-1 gap-fill still running
NOT_READY = "NOT_READY"                                 # recovery cancelled/failed; awaiting a restart
READY = "READY"
OVERDUE = "OVERDUE"                                     # waited max_wait; proceeding, alerted
BLOCKING = (WAITING_FOR_STAGE1_START, RECOVERING, NOT_READY)

REPAIR_COMPONENT = "startup_recovery_repair"            # beta_runtime_health marker


def _iso(ts: Optional[datetime]) -> Optional[str]:
    return None if ts is None else ts.astimezone(timezone.utc).isoformat()


def floor_bucket(ts: datetime) -> datetime:
    ts = ts.astimezone(timezone.utc)
    return ts.replace(minute=ts.minute - ts.minute % 5, second=0, microsecond=0)


def max_wait(cfg) -> timedelta:
    """The detector's own catch-up bound: waiting longer loses buckets anyway."""
    return cfg["detector"]["max_catchup_buckets_per_run"] * BUCKET


def startup_gate(row: Optional[Mapping[str, Any]], *, now: datetime,
                 host_boot_time: Optional[datetime], max_wait: timedelta,
                 blocked_since: Optional[datetime] = None) -> dict:
    """{state, proceed, recovery_run_id, waiting_since, waited_s} for one detector run.
    `blocked_since`: when the detector's CURRENT continuous block began (see
    `continuing_block`), so a Stage-1 crash loop, which writes a new row on every
    start, cannot reset the bound."""
    if row is None:
        return {"state": NO_SIGNAL, "proceed": True, "recovery_run_id": None,
                "waiting_since": None, "waited_s": None}
    status, started = row["status"], row["started_at"]
    if host_boot_time is not None and started < host_boot_time:
        state, since = WAITING_FOR_STAGE1_START, host_boot_time
    elif status == RUNNING:
        state, since = RECOVERING, started
    elif status in READY_STATUSES:
        return {"state": READY, "proceed": True, "recovery_run_id": row["id"],
                "recovery_status": status, "waiting_since": None, "waited_s": None}
    else:
        state, since = NOT_READY, row.get("finished_at") or started
    if blocked_since is not None and blocked_since < since:
        since = blocked_since
    waited = max(0.0, (now - since).total_seconds())
    out = {"state": state, "proceed": False, "recovery_run_id": row["id"], "recovery_status": status,
           "waiting_since": _iso(since), "waited_s": waited}
    if waited >= max_wait.total_seconds():
        out.update(state=OVERDUE, proceed=True, blocked_state=state)
    return out


def continuing_block(previous: Optional[Mapping[str, Any]], *, now: datetime,
                     max_wait: timedelta) -> Optional[datetime]:
    """When the block the detector's previous run reported began, if that run was
    recent enough to be the same continuous block (it runs every 5 minutes);
    None otherwise. `previous` = the detector's beta_runtime_health row."""
    if not previous:
        return None
    gate = (previous.get("detail") or {}).get("startup_recovery") or {}
    last_run = previous.get("last_run_at")
    if gate.get("state") not in BLOCKING + (OVERDUE,) or not gate.get("waiting_since") or last_run is None:
        return None
    if now - last_run > max_wait:
        return None
    return datetime.fromisoformat(gate["waiting_since"])


def repair_window(row: Mapping[str, Any], *, max_catchup: int) -> tuple:
    """[start, end] bucket starts a recovery could have left degraded: a run that
    caught up before the gap-fill finished wrote at most `max_catchup` buckets
    older than the recovery start, and nothing degraded after it finished."""
    start = floor_bucket(row["started_at"]) - max_catchup * BUCKET
    end = floor_bucket(row["finished_at"] or row["started_at"])
    return start, end


def stale_buckets(decided_bars: Mapping[datetime, Mapping[str, int]],
                  raw_counts: Mapping[tuple, int], exchanges: Sequence[str]) -> list:
    """Decided buckets (oldest first) whose stored bar count of any venue is below
    the raw 1m-bar count now present for that venue and bucket."""
    out = []
    for b in sorted(decided_bars):
        stored = decided_bars[b] or {}
        if any(int(raw_counts.get((b, ex), 0)) > int(stored.get(ex) or 0) for ex in exchanges):
            out.append(b)
    return out


def read_host_boot_time(path: str = "/proc/stat") -> Optional[datetime]:
    """This host's boot time (Linux `btime`), or None when unreadable."""
    try:
        with open(path, encoding="ascii") as fh:
            for line in fh:
                if line.startswith("btime "):
                    return datetime.fromtimestamp(int(line.split()[1]), tz=timezone.utc)
    except (OSError, ValueError, IndexError):
        return None
    return None
