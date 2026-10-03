"""Stage-1 startup-recovery readiness signal (durable, in PostgreSQL).

Every Stage-1 process start that is going live records ONE `backfill_runs` row
(exchange '*', source 'startup_recovery') BEFORE its startup backfill/gap-fill
and finishes it once the gap-fill is done. A new process start writes a new row,
so readiness is invalidated per start; the startup sweep turns a row left
'running' by a killed process into 'cancelled'. The beta detector reads the
newest row and does not catch up buckets while it is not ready.

No schema change: `backfill_runs` is the existing Stage-1 bookkeeping table.
"""
from __future__ import annotations

from typing import Mapping

SOURCE = "startup_recovery"
EXCHANGE = "*"                       # one row for the whole startup, not per venue

RUNNING = "running"
COMPLETE = "complete"                # every enabled venue's gap-fill finished
PARTIAL = "partial"                  # gap-fill finished, but at least one venue failed
CANCELLED = "cancelled"              # stop requested / process died before the end
FAILED = "failed"                    # startup raised before the gap-fill finished
READY_STATUSES = (COMPLETE, PARTIAL)

# run_gap_fill per-venue outcomes
GAP_FILLED = "filled"
GAP_CURRENT = "current"
GAP_FAILED = "failed"
GAP_NO_HISTORY = "no_history"
GAP_UNSUPPORTED = "unsupported"


def finish_status(results: Mapping[str, Mapping]) -> tuple:
    """(status, rows_written, note) of a startup recovery from run_gap_fill's results."""
    failed = sorted(ex for ex, r in results.items() if r.get("status") == GAP_FAILED)
    rows = sum(int(r.get("bars") or 0) for r in results.values())
    note = " ".join(f"{ex}={r.get('status')}:{int(r.get('bars') or 0)}" for ex, r in sorted(results.items()))
    return (PARTIAL if failed else COMPLETE), rows, note
