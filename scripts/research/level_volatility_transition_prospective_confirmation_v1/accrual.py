"""Outcome-blind stop. Counts and clocks only. No transition."""

from __future__ import annotations

import datetime as dt

from . import constants as K
from .surface import UTC, parse_utc

WEEK = dt.timedelta(milliseconds=K.WEEK_MS)


def completed_weeks(now: dt.datetime, start: dt.datetime) -> int:
    now = now.astimezone(UTC)
    start = start.astimezone(UTC)
    if now < start:
        return 0
    return int((now - start) // WEEK)


def checkpoint_end(start: dt.datetime, weeks: int) -> dt.datetime:
    if int(weeks) not in K.CHECKPOINT_WEEKS:
        raise ValueError("checkpoint is not on the frozen schedule")
    return start.astimezone(UTC) + WEEK * int(weeks)


def next_checkpoint(done: int) -> int | None:
    for weeks in K.CHECKPOINT_WEEKS:
        if done < weeks:
            return int(weeks)
    return None


def epoch_bounds(start: dt.datetime, n_epochs: int = 6) -> list[tuple[str, dt.datetime, dt.datetime]]:
    start = start.astimezone(UTC)
    width = WEEK * K.EPOCH_WEEKS
    out = []
    for i in range(int(n_epochs)):
        lo = start + width * i
        out.append((f"E{i + 1}", lo, lo + width))
    return out


def stop_decision(*, completed: int, matched_pairs: int | None, at_checkpoint: bool) -> dict:
    """First checkpoint that clears both floors closes the cohort.

    At 156 weeks a shortfall closes as information-limited and does not
    authorize an outcome read.
    """
    weeks_ok = int(completed) >= K.MIN_COMPLETED_ISO_WEEKS
    pairs_ok = matched_pairs is not None and int(matched_pairs) >= K.MIN_MATCHED_PATH_COMPLETE_PAIRS
    if not at_checkpoint:
        return {
            "stop": False,
            "information_limited": False,
            "read_outcomes": False,
            "reason": "between checkpoints",
        }
    if weeks_ok and pairs_ok:
        return {
            "stop": True,
            "information_limited": False,
            "read_outcomes": False,
            "reason": "both floors met; pair map may be frozen; outcomes stay unread until evaluate",
        }
    if int(completed) >= K.MAX_ACCRUAL_WEEKS and not pairs_ok:
        return {
            "stop": True,
            "information_limited": True,
            "read_outcomes": False,
            "reason": "PROSPECTIVE_CONFIRMATION_INFORMATION_LIMITED",
        }
    return {
        "stop": False,
        "information_limited": False,
        "read_outcomes": False,
        "reason": "checkpoint short of the frozen floors",
    }


def clock_status(now: dt.datetime, start_iso: str) -> dict:
    start = parse_utc(start_iso)
    done = completed_weeks(now, start)
    return {
        "prospective_start": start_iso,
        "start_reached": now.astimezone(UTC) >= start,
        "completed_weeks": done,
        "next_checkpoint": next_checkpoint(done),
        "max_accrual_weeks": K.MAX_ACCRUAL_WEEKS,
        "min_pairs": K.MIN_MATCHED_PATH_COMPLETE_PAIRS,
        "min_weeks": K.MIN_COMPLETED_ISO_WEEKS,
    }
