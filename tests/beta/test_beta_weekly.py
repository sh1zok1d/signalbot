"""Weekly report (backlog B4), pure: the Sunday slot, the week's corridors, the text with N and its
comparators, «мало данных» below the one threshold, and the config rule. Synthetic rows only."""
from datetime import datetime, timedelta, timezone

import pytest

from beta.config import BetaConfig, BetaConfigError
from beta.weekly import format_weekly, week_corridors, weekly_slot

UTC = timezone.utc
SUN = datetime(2026, 5, 17, 16, 5, tzinfo=UTC)                 # Sunday 19:05 Kyiv (UTC+3)


def test_the_slot_is_sunday_evening_kyiv_only():
    assert weekly_slot(SUN, "sun", "19:00") == (SUN.date(), datetime(2026, 5, 17, 16, 0, tzinfo=UTC))
    assert weekly_slot(SUN - timedelta(minutes=6), "sun", "19:00") is None            # 18:59 Kyiv
    assert weekly_slot(SUN - timedelta(days=1), "sun", "19:00") is None               # Saturday
    assert weekly_slot(SUN + timedelta(hours=5), "sun", "19:00") is None              # Monday 00:05 Kyiv
    assert weekly_slot(SUN, "sat", "19:00") is None


def _row(h, issued, *, outcome="INSIDE", high=101.0, low=99.0):
    return {"horizon": h, "issued_at": issued, "anchor_price": 100.0, "lower": 98.0, "upper": 102.0,
            "outcome": outcome, "realized_high": high, "realized_low": low}


def _week_rows():
    start = SUN - timedelta(days=7)
    rows = [_row("1h", start + timedelta(hours=i)) for i in range(36)]
    rows += [_row("1h", start + timedelta(hours=36), outcome="OUTSIDE", high=103.02),
             _row("1h", start + timedelta(hours=37), outcome="OUTSIDE", high=104.04),
             _row("1h", start + timedelta(hours=38), outcome="OUTSIDE", low=97.02),
             _row("1h", start + timedelta(hours=39), outcome="OUTSIDE", low=97.02)]
    rows += [_row("24h", start + timedelta(days=d)) for d in range(5)]
    rows += [_row("1h", start - timedelta(hours=1)), _row("4h", SUN)]                  # outside the week
    return rows


def test_the_week_counts_corridors_issued_and_scored_inside_it():
    start = SUN - timedelta(days=7)
    cor = week_corridors(_week_rows(), start=start, end=SUN)
    assert set(cor) == {"1h", "24h"}
    h1 = cor["1h"]
    assert h1["n"] == h1["n_eff"] == 40 and h1["inside"] == 0.9
    assert h1["half_width_pct"] == pytest.approx(2.0)
    assert h1["miss_up"]["share"] == 0.05 and h1["miss_up"]["median_pct"] == pytest.approx(1.5)
    assert h1["miss_down"]["share"] == 0.05 and h1["miss_down"]["median_pct"] == pytest.approx(1.0)
    assert cor["24h"]["n_eff"] == 5


def _payload(**kw):
    start = SUN - timedelta(days=7)
    base = {"version": "BETA_WEEKLY_V1", "from": start.isoformat(), "to": SUN.isoformat(), "coverage": 0.8,
            "holdout": {"1h": 0.81, "4h": 0.8, "24h": 0.79},
            "corridors": week_corridors(_week_rows(), start=start, end=SUN),
            "touch": {"1h": [{"bin": [0.05, 0.15], "n": 300, "n_eff": 120, "predicted": 0.1, "realized": 0.08},
                             {"bin": [0.5, 0.7], "n": 20, "n_eff": 12, "predicted": 0.6, "realized": 0.5}],
                      "4h": [{"bin": [0.15, 0.3], "n": 40, "n_eff": 20, "predicted": 0.2, "realized": 0.3}],
                      "24h": []},
            "alerts": {"level": 2, "move": 1}}
    return {**base, **kw}


def test_the_text_carries_n_and_comparators_and_hides_small_samples():
    ru = format_weekly(_payload(), "ru")
    assert "Неделя бота: 10.05–17.05" in ru
    assert "расчётная — 80%" in ru
    assert "• 1ч: 90% (N=40; на отложенном годе 81%) · ширина ±2,00%" in ru
    assert "выше коридора 5% (медиана на 1,50%), ниже 5% (медиана на 1,00%)" in ru
    assert "• 24ч: мало данных (N=5)" in ru                       # 5 independent days < 30
    assert "• 1ч: 10% → 8% (N=120)" in ru and "60% → 50%" not in ru  # only bins at N_eff >= 30
    assert "• 4ч: мало данных (N=20)" in ru
    assert "уровни 2, события 0, резкие движения 1" in ru
    assert "/push weekly off" in ru
    en = format_weekly(_payload(), "en")
    assert "The bot's week: 10.05–17.05" in en and "• 1h: 90% (N=40; held-out year 81%) · width ±2.00%" in en


def test_an_empty_week_says_so():
    ru = format_weekly(_payload(corridors={}, touch={}, alerts={}), "ru")
    assert "за неделю нет проверенных коридоров" in ru and "Шанс дойти" not in ru
    assert "уровни 0, события 0, резкие движения 0" in ru


@pytest.mark.parametrize("bad", [{"weekday_kyiv": "sunday"}, {"time_kyiv": "7pm"}, {"max_delay_min": 0},
                                 {"enabled": "yes"}, {"extra": 1}])
def test_the_committed_schedule_and_its_validation(bad):
    cfg = BetaConfig.load()
    w = cfg.section("decision")["weekly_report"]
    assert w == {"enabled": True, "weekday_kyiv": "sun", "time_kyiv": "19:00", "max_delay_min": 120}
    with pytest.raises(BetaConfigError):
        cfg.with_overrides(decision={**cfg.section("decision"), "weekly_report": {**w, **bad}})
