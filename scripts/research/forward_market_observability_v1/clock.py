"""Local receipt clocks.

UTC is legal_available_at. Monotonic ns is process-local order only.
Neither is replaced by exchange event time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic_ns, time_ns
from typing import Any

from scripts.research.forward_market_observability_v1.schemas import EVENT_CLOCK_ANOMALY

UTC = timezone.utc

# Wall-clock backward motion of any size is an anomaly if monotonic advanced.
# Material forward jump while monotonic barely moved: 2 seconds.
DEFAULT_FORWARD_JUMP_NS = 2_000_000_000


@dataclass(frozen=True)
class ReceiptStamp:
    local_received_at_utc: str
    local_received_monotonic_ns: int
    utc_epoch_ns: int

    @property
    def legal_available_at(self) -> str:
        return self.local_received_at_utc


def utc_now_ns() -> int:
    return time_ns()


def format_utc_ns(epoch_ns: int) -> str:
    seconds, nanos = divmod(epoch_ns, 1_000_000_000)
    dt = datetime.fromtimestamp(seconds, tz=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{nanos:09d}Z"


def capture_receipt() -> ReceiptStamp:
    """Assign receipt timestamps. Call BEFORE parsing or analysis."""
    mono = monotonic_ns()
    utc_ns = utc_now_ns()
    return ReceiptStamp(
        local_received_at_utc=format_utc_ns(utc_ns),
        local_received_monotonic_ns=mono,
        utc_epoch_ns=utc_ns,
    )


class ClockWatch:
    """Detect wall-clock anomalies without rewriting stamps."""

    def __init__(self, *, forward_jump_ns: int = DEFAULT_FORWARD_JUMP_NS) -> None:
        self.forward_jump_ns = forward_jump_ns
        self._last: ReceiptStamp | None = None
        self.anomaly_count = 0

    def observe(self, stamp: ReceiptStamp) -> dict[str, Any] | None:
        prev = self._last
        self._last = stamp
        if prev is None:
            return None
        mono_delta = stamp.local_received_monotonic_ns - prev.local_received_monotonic_ns
        utc_delta = stamp.utc_epoch_ns - prev.utc_epoch_ns
        if mono_delta < 0:
            # Monotonic should never go backward in-process; still record.
            self.anomaly_count += 1
            return _anomaly(
                "MONOTONIC_BACKWARD",
                prev,
                stamp,
                mono_delta=mono_delta,
                utc_delta=utc_delta,
            )
        if utc_delta < 0 and mono_delta >= 0:
            self.anomaly_count += 1
            return _anomaly(
                "UTC_BACKWARD",
                prev,
                stamp,
                mono_delta=mono_delta,
                utc_delta=utc_delta,
            )
        if utc_delta > self.forward_jump_ns and mono_delta < utc_delta // 2:
            self.anomaly_count += 1
            return _anomaly(
                "UTC_FORWARD_JUMP",
                prev,
                stamp,
                mono_delta=mono_delta,
                utc_delta=utc_delta,
            )
        return None


def _anomaly(
    kind: str,
    prev: ReceiptStamp,
    stamp: ReceiptStamp,
    *,
    mono_delta: int,
    utc_delta: int,
) -> dict[str, Any]:
    return {
        "event_type": EVENT_CLOCK_ANOMALY,
        "clock_anomaly_kind": kind,
        "previous_local_received_at_utc": prev.local_received_at_utc,
        "previous_local_received_monotonic_ns": prev.local_received_monotonic_ns,
        "local_received_at_utc": stamp.local_received_at_utc,
        "local_received_monotonic_ns": stamp.local_received_monotonic_ns,
        "utc_delta_ns": utc_delta,
        "monotonic_delta_ns": mono_delta,
        "rewrote_receipt_timestamps": False,
        "replaced_utc_with_exchange_time": False,
    }
