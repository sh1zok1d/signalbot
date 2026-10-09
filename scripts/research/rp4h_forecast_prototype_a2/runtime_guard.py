"""A2 runtime guard for the vendored ISO-week clock. Reads no market data.

`folds.iso_parts` (vendored byte-identical) converts a pandas timestamp to
milliseconds with `astype("int64") // 1_000_000`, which assumes nanosecond
resolution. pandas 2.2.3 (the pin in requirements.txt) returns nanoseconds;
pandas 3 returns millisecond resolution for `unit="ms"`, and every block start
collapses to 1970. This check fails closed on such a runtime instead of
producing a wrong fold schedule.
"""

from __future__ import annotations

import numpy as np

from .folds import iso_parts

DAY_MS = 86_400_000
_PROBES = np.array([
    1_735_513_200_000,  # 2024-12-29T23:00:00Z, Sunday -> Monday 2024-12-23
    1_735_517_700_000,  # 2024-12-30T00:15:00Z, Monday -> 2024-12-30
    1_462_752_000_000,  # 2016-05-09T00:00:00Z, Monday -> itself
    1_786_838_400_000,  # 2026-08-16T00:00:00Z, Sunday -> Monday 2026-08-10
], dtype=np.int64)


def expected_monday_ms(close_ms: np.ndarray) -> np.ndarray:
    """Monday 00:00 UTC by integer arithmetic. 1970-01-01 was a Thursday."""
    close_ms = np.asarray(close_ms, dtype=np.int64)
    days = np.floor_divide(close_ms, DAY_MS)
    weekday = np.mod(days + 3, 7)
    return (days - weekday) * DAY_MS


def assert_fold_clock() -> None:
    _year, _week, monday = iso_parts(_PROBES)
    if not np.array_equal(np.asarray(monday, dtype=np.int64), expected_monday_ms(_PROBES)):
        raise SystemExit("FOLD_CLOCK_RUNTIME_MISMATCH")
