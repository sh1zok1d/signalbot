"""Derivatives beside their «обычно» (backlog G2), pure: the nightly OI statistic over non-overlapping
UTC days, the 30-day funding comparator from the same tape, and the text on the 24h surfaces with N.
Synthetic data only."""
from datetime import datetime, timedelta, timezone

import numpy as np

from beta.derivatives import MIN_DAYS, derivatives_block, funding_typical, oi_change_stats
from beta.formatter import _line_24h, derivative_lines
from beta.hist_series import BAR_MS, empty_bars
from beta.state_tape import BUCKET

UTC = timezone.utc
T0 = int(datetime(2026, 1, 1, tzinfo=UTC).timestamp() * 1000)


def test_oi_statistic_uses_one_window_per_utc_day():
    days = 41
    b = empty_bars(T0, days * 288)
    # OI alternates +2 % / -1 % from one UTC midnight to the next; intraday values are noise
    level, rng = 100.0, np.random.default_rng(1)
    for d in range(days):
        b.oi[d * 288:(d + 1) * 288] = level * (1 + rng.uniform(-0.05, 0.05, 288))
        b.oi[d * 288] = level
        level *= 1.02 if d % 2 == 0 else 0.99
    s = oi_change_stats(b)
    assert s["n_days"] == days - 1 and s["source"] == "binance"
    assert abs(s["median_abs_pct"] - 1.5) < 1e-9                        # 20 days at 2 %, 20 at 1 %
    assert abs(s["p90_abs_pct"] - 2.0) < 1e-9
    assert s["from_ms"] == T0 and s["to_ms"] == T0 + (days - 1) * 288 * BAR_MS
    short = empty_bars(T0, (MIN_DAYS - 1) * 288 + 1)
    short.oi[:] = 100.0
    assert oi_change_stats(short)["median_abs_pct"] is None and oi_change_stats(short)["n_days"] == MIN_DAYS - 1


def _metrics(as_of, days, value_of_day, *, present=288):
    out = {}
    for d in range(1, days + 1):
        end = as_of - timedelta(days=d)
        for i in range(present):
            out[end - i * BUCKET] = {"c:funding_rate_median": value_of_day(d)}
    return out


def test_funding_comparator_is_the_median_of_prior_daily_means():
    as_of = datetime(2026, 5, 12, 6, 0, tzinfo=UTC)
    m = _metrics(as_of, 30, lambda d: 0.0001 * d)
    m[as_of] = {"c:funding_rate_median": 0.05}                         # the current day never counts
    f = funding_typical(m, as_of)
    assert f["days"] == 30 and abs(f["median"] - 0.00155) < 1e-12
    assert funding_typical(_metrics(as_of, 30, lambda d: 0.0001, present=100), as_of) == {"days": 0, "median": None}
    few = funding_typical(_metrics(as_of, MIN_DAYS - 1, lambda d: 0.0001), as_of)
    assert few == {"days": MIN_DAYS - 1, "median": None}


def _view(**der):
    horizons = {"24h": {"oi_change_pct": 3.24, "funding_rate_avg": 0.0001, "price_complete": False}}
    block = derivatives_block(horizons=horizons, funding={"days": 30, "median": 0.00008},
                              oi_stats={"median_abs_pct": 1.84, "p90_abs_pct": 4.1, "n_days": 1500, "source": "binance"},
                              long_short={"ratio": 1.853, "at": "x", "typical": 1.62, "n_days": 30})
    block.update(der)
    return {"horizons": horizons, "derivatives": block, "now": {"reference_price": 64000.0}}


def test_the_24h_line_and_tab_carry_the_comparator_with_n():
    line = _line_24h(_view(), "ru")
    assert "OI +3,2% за 24ч (обычно ±1,8%, N=1500)" in line
    assert "(платят лонги; обычно 0,008%, N=30)" in line
    assert derivative_lines(_view(), "ru", part="oi") == ["   обычно OI за сутки меняется на ±1,8% (медиана, Binance, N=1500 дн.)"]
    assert derivative_lines(_view(), "ru", part="funding") == ["   обычно среднее за 24 ч 0,008% (медиана за 30 дн.)"]
    assert derivative_lines(_view(), "ru", part="long_short") == [
        "Соотношение счетов лонг/шорт (Binance): 1,85 · обычно 1,62 (медиана за 30 дн.)"]
    assert derivative_lines(_view(), "en", part="long_short") == [
        "Long/short account ratio (Binance): 1.85 · usually 1.62 (median of 30 days)"]


def test_without_a_comparator_the_surfaces_say_so_or_stay_silent():
    view = _view(oi_24h={"change_pct": 3.24, "typical_abs_pct": None, "n_days": 12, "source": "binance"},
                 funding_24h={"avg": 0.0001, "typical": None, "n_days": 0}, long_short=None)
    line = _line_24h(view, "ru")
    assert "OI +3,2% за 24ч ·" in line and "обычно" not in line
    assert derivative_lines(view, "ru", part="oi") == ["   обычно: мало данных (N=12 дн.)"]
    assert derivative_lines(view, "ru", part="funding") == []
    assert derivative_lines(view, "ru", part="long_short") == []
    assert derivative_lines({"horizons": {}}, "ru", part="oi") == []           # a view stored before G2
