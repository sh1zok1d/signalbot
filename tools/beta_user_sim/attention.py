"""Deterministic attention schedule. The harness, not the model, decides availability.

Time is cut into fixed slots aligned to the UTC epoch. A slot whose start falls in
the nightly sleep window (Kyiv local time) is SLEEPING. Every other slot is BUSY
with probability `p_busy`, drawn from `random.Random(seed)` once per slot in slot
order (a draw is made for sleeping slots too, so the sequence never shifts). The
same seed and configuration always give the same schedule.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

from .surface import AVAILABLE, BUSY, SLEEPING

ATTENTION_MODEL_VERSION = "ATTENTION_SLOTS_V0"
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class AttentionConfig:
    seed: int = 7
    slot_minutes: int = 30
    p_busy: float = 0.45
    sleep_start: str = "00:30"
    sleep_end: str = "07:30"
    tz: str = "Europe/Kyiv"

    def as_dict(self) -> dict:
        return {"model": ATTENTION_MODEL_VERSION, **asdict(self)}


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime
    state: str


def _hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def _sleeping(cfg: AttentionConfig, at: datetime) -> bool:
    local = at.astimezone(ZoneInfo(cfg.tz)).time()
    a, b = _hm(cfg.sleep_start), _hm(cfg.sleep_end)
    return (a <= local < b) if a <= b else (local >= a or local < b)


def _floor(at: datetime, slot: timedelta) -> datetime:
    n = (at - _EPOCH) // slot
    return _EPOCH + n * slot


class AttentionSchedule:
    def __init__(self, cfg: AttentionConfig, start: datetime, end: datetime):
        if end <= start:
            raise ValueError("attention schedule needs end > start")
        self.cfg = cfg
        slot = timedelta(minutes=cfg.slot_minutes)
        rng = random.Random(cfg.seed)
        intervals: list = []
        t = _floor(start, slot)
        while t < end:
            draw = rng.random()
            state = SLEEPING if _sleeping(cfg, t) else (BUSY if draw < cfg.p_busy else AVAILABLE)
            if intervals and intervals[-1].state == state and intervals[-1].end == t:
                intervals[-1] = Interval(intervals[-1].start, t + slot, state)
            else:
                intervals.append(Interval(t, t + slot, state))
            t += slot
        self.intervals: Sequence[Interval] = tuple(intervals)

    def state_at(self, at: datetime) -> str:
        for iv in self.intervals:
            if iv.start <= at < iv.end:
                return iv.state
        return SLEEPING

    def available_starts(self) -> list:
        """Every instant the user turns AVAILABLE after not being available."""
        return [iv.start for i, iv in enumerate(self.intervals)
                if iv.state == AVAILABLE and i > 0 and self.intervals[i - 1].state != AVAILABLE]

    def next_available(self, at: datetime) -> Optional[datetime]:
        for iv in self.intervals:
            if iv.end <= at:
                continue
            if iv.state == AVAILABLE:
                return max(at, iv.start)
        return None

    def as_list(self) -> list:
        return [{"start": iv.start.isoformat(), "end": iv.end.isoformat(), "state": iv.state}
                for iv in self.intervals]
