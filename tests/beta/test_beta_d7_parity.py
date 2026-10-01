"""D7 parity with the research definition.

This is the only test module allowed to import scripts.research.
The opt-in real-data test does not run unless D7_PARITY_CORE_ROOT is set, and
it refuses any 2025/2026 path before reading file bytes.
"""
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from beta.regime_d7 import (BAR_MS, HOUR_MS, HourBar, MinuteBar, aggregate_completed_hours,
                            build_d7_states)
from scripts.research import discovery_sprint_02_impl as research

UTC = timezone.utc
PROTECTED_MS = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)


def _pair(n_hours=1460):
    """Synthetic 1m bars in 2021, with whole-hour gaps and one incomplete hour."""
    start = datetime(2021, 1, 1, tzinfo=UTC)
    research_bars = []
    beta_bars = []
    for hour in range(n_hours):
        if hour in (4, 80):
            continue
        for minute in range(60):
            if hour == 40 and minute == 7:
                continue
            open_dt = start + timedelta(hours=hour, minutes=minute)
            open_ms = int(open_dt.timestamp() * 1000)
            ret = ((hour * 17) % 100) / 10000.0
            first_open = 100.0
            close_px = first_open if minute != 59 else first_open * math.exp(ret)
            qv = 1_000_000.0 + (hour % 30) * 1000.0
            research_bars.append(research.MinuteBar(
                open_time_ms=open_ms, available_at_ms=open_ms + BAR_MS, open=first_open,
                close=close_px, quote_volume=qv, trade_count=1, taker_buy_quote_volume=0.0))
            beta_bars.append(MinuteBar(
                open_time_ms=open_ms, available_at_ms=open_ms + BAR_MS, open=first_open,
                close=close_px, quote_volume=qv))
    return research_bars, beta_bars


def test_synthetic_1m_states_match_the_research_definition():
    research_bars, beta_bars = _pair()
    assert max(bar.open_time_ms for bar in research_bars) < PROTECTED_MS
    left = research.build_d7_states(research.aggregate_completed_hours(research_bars))
    right = build_d7_states(aggregate_completed_hours(beta_bars))
    assert [row.hour.hour_start_ms for row in left] == [row.hour.hour_start_ms for row in right]
    assert [row.d7_state for row in left] == [row.d7_state for row in right]
    assert any(row.d7_state is True for row in right)
    assert any(row.d7_state is False for row in right)
    dropped = {int((datetime(2021, 1, 1, tzinfo=UTC) + timedelta(hours=h)).timestamp() * 1000)
               for h in (4, 40, 80)}
    assert dropped.isdisjoint(row.hour.hour_start_ms for row in right)


def _edge_hours(last_ret):
    base = datetime(2021, 6, 1, tzinfo=UTC)
    beta, sci = [], []
    for i in range(1441):
        if i < 720:
            ret = 0.01
        elif i < 1440:
            ret = float(i - 720)
        else:
            ret = last_ret
        ms = int((base + timedelta(hours=i)).timestamp() * 1000)
        beta.append(HourBar(ms, ms + HOUR_MS, 100.0, 100.0, 1.0, abs(ret), ret))
        sci.append(research.HourBar(
            hour_start_ms=ms, available_at_ms=ms + HOUR_MS, year=2021, open_1h=100.0,
            close_1h=100.0, quote_volume_1h=1.0, trade_count_1h=60,
            taker_buy_quote_volume_1h=0.0, ret_abs_1h=abs(ret), event_return=ret))
    return beta, sci


def test_p90_linear_edge_matches_research():
    impacts = [float(i) for i in range(720)]
    p90 = research.percentile(impacts, 90.0)
    for last, expect in ((p90, False), (p90 + 1.0, True)):
        beta, sci = _edge_hours(last)
        left = research.build_d7_states(sci)
        right = build_d7_states(beta)
        assert [row.d7_state for row in left] == [row.d7_state for row in right]
        assert left[1439].d7_state is None
        assert right[1440].d7_state is expect
        assert right[1440].p90 == pytest.approx(p90)


def _refuse_protected_names(root: Path) -> None:
    """List names only. A 2025/2026 path fails before any file is opened."""
    for dirpath, dirnames, filenames in os.walk(root):
        for name in list(dirnames) + list(filenames):
            if name.startswith(("2025", "2026")) or "2025-" in name or "2026-" in name:
                raise AssertionError(f"refused protected partition before read: {name}")


@pytest.mark.skipif(not os.environ.get("D7_PARITY_CORE_ROOT"), reason="D7_PARITY_CORE_ROOT not set")
def test_opt_in_core_2020_2024_parity_refuses_protected_years():
    root = Path(os.environ["D7_PARITY_CORE_ROOT"])
    _refuse_protected_names(root)
    bars = research.load_legal_1m_bars(dataset_root=root)
    for bar in bars:
        if bar.open_time_ms >= PROTECTED_MS or bar.available_at_ms > PROTECTED_MS:
            raise AssertionError(f"refused protected timestamp: {bar.open_time_ms}")
    beta_bars = [MinuteBar(bar.open_time_ms, bar.available_at_ms, bar.open, bar.close, bar.quote_volume)
                 for bar in bars]
    left = research.build_d7_states(research.aggregate_completed_hours(bars))
    right = build_d7_states(aggregate_completed_hours(beta_bars))
    assert [row.d7_state for row in left] == [row.d7_state for row in right]
