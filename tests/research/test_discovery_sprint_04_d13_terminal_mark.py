"""Synthetic tests for the frozen D13 holding-week terminal-mark rule. No market data."""

from __future__ import annotations

import datetime as dt

import pytest

from scripts.research.discovery_sprint_04 import d13_terminal_mark as TM

DAY = TM.DAY_MS
T = int(dt.datetime(2022, 6, 6, tzinfo=dt.timezone.utc).timestamp() * 1000)  # a Monday


def _closes(offsets_days: list[int], start: float = 100.0) -> dict[int, float]:
    return {T + k * DAY: start + k for k in offsets_days}


def test_full_week_asset_uses_close_at_t_plus_7d():
    mark = TM.terminal_mark("AAAUSDT", T, _closes(list(range(-1, 7))))
    assert mark.status == TM.FULL_WEEK
    assert mark.entry_close == 99.0
    assert mark.terminal_candle_open_ms == T + 6 * DAY
    assert mark.terminal_close == 106.0


def test_intraweek_delisting_uses_final_traded_close():
    mark = TM.terminal_mark("BBBUSDT", T, _closes([-1, 0, 1, 2]))
    assert mark.status == TM.INTRAWEEK_FINAL_CLOSE
    assert mark.terminal_candle_open_ms == T + 2 * DAY
    assert mark.terminal_close == 102.0
    TM.assert_terminal_marks_resolved([mark])


def test_selected_asset_without_post_t_close_fails_closed_not_dropped():
    mark = TM.terminal_mark("CCCUSDT", T, _closes([-1]))
    assert mark.status == TM.NO_POST_T_CLOSE
    assert mark.terminal_close is None
    marks = [TM.terminal_mark("AAAUSDT", T, _closes(list(range(-1, 7)))), mark]
    assert TM.no_post_t_close_selected_n(marks) == 1
    with pytest.raises(TM.D13TerminalMarkUnresolved, match="DEFERRED_TERMINAL_MARK_UNRESOLVED"):
        TM.assert_terminal_marks_resolved(marks)
    TM.assert_terminal_marks_resolved(marks, terminal_mark_authority={"CCCUSDT": 42.0})


def test_later_relisting_is_never_used_as_terminal_mark():
    closes = _closes([-1])
    closes[T + 30 * DAY] = 500.0
    mark = TM.terminal_mark("DDDUSDT", T, closes)
    assert mark.status == TM.NO_POST_T_CLOSE
    assert mark.terminal_close is None


def test_selection_requires_entry_close_at_t():
    with pytest.raises(ValueError, match="D13_SELECTED_WITHOUT_ENTRY_CLOSE"):
        TM.terminal_mark("EEEUSDT", T, _closes([0, 1]))
