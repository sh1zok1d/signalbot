"""D13 holding-week terminal-mark rule (frozen pre-outcome). Pure; no market I/O.

Daily closes are keyed by the UTC-midnight open time of the 1d candle. The
price at a Monday decision clock T is the close of the Sunday candle opening at
T - 1 day. The holding week's candles open at T, T+1d, ..., T+6d; the close of
the candle opening at T+6d is the price at T+7d. Only candles inside the
holding week are ever read, so later relisting data cannot leak in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

DAY_MS = 86_400_000
HOLDING_DAYS = 7

FULL_WEEK = "FULL_WEEK"
INTRAWEEK_FINAL_CLOSE = "INTRAWEEK_FINAL_CLOSE"
NO_POST_T_CLOSE = "NO_POST_T_CLOSE"
DEFERRED_TERMINAL_MARK_UNRESOLVED = "DEFERRED_TERMINAL_MARK_UNRESOLVED"


class D13TerminalMarkUnresolved(RuntimeError):
    """A symbol selected at T has no observed close after T and no terminal-mark authority."""


@dataclass(frozen=True)
class TerminalMark:
    symbol: str
    status: str
    entry_close: float
    terminal_close: float | None
    terminal_candle_open_ms: int | None


def terminal_mark(symbol: str, t_ms: int, daily_closes: Mapping[int, float]) -> TerminalMark:
    if t_ms % DAY_MS:
        raise ValueError(f"D13_T_NOT_UTC_MIDNIGHT:{t_ms}")
    entry = daily_closes.get(t_ms - DAY_MS)
    if entry is None:
        raise ValueError(f"D13_SELECTED_WITHOUT_ENTRY_CLOSE:{symbol}:{t_ms}")
    last_open = None
    for k in range(HOLDING_DAYS):
        open_ms = t_ms + k * DAY_MS
        if open_ms in daily_closes:
            last_open = open_ms
    if last_open is None:
        return TerminalMark(symbol, NO_POST_T_CLOSE, entry, None, None)
    status = FULL_WEEK if last_open == t_ms + (HOLDING_DAYS - 1) * DAY_MS else INTRAWEEK_FINAL_CLOSE
    return TerminalMark(symbol, status, entry, daily_closes[last_open], last_open)


def no_post_t_close_selected_n(marks: Iterable[TerminalMark]) -> int:
    return sum(1 for m in marks if m.status == NO_POST_T_CLOSE)


def assert_terminal_marks_resolved(
    marks: Iterable[TerminalMark],
    *,
    terminal_mark_authority: Mapping[str, float] | None = None,
) -> None:
    """Fail closed. A NO_POST_T_CLOSE symbol is never dropped and never assigned a zero return.

    Scientific execution may proceed only if every such symbol has a value in a
    deterministic, point-in-time terminal-mark authority frozen before outcomes.
    """

    authority = terminal_mark_authority or {}
    unresolved = [m.symbol for m in marks if m.status == NO_POST_T_CLOSE and m.symbol not in authority]
    if unresolved:
        raise D13TerminalMarkUnresolved(
            f"{DEFERRED_TERMINAL_MARK_UNRESOLVED}:NO_POST_T_CLOSE_SELECTED_N={len(unresolved)}"
        )
