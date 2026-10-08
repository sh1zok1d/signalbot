"""D3 (docs/BETA_DATA_RELIABILITY_FIX_PLAN_V1.md R6, R7).

R6: «no large change vs the previous 24h» names the checks that ran, lists those that could not, is never
said when none could run, and is not said from a payload that does not record its checks (pre-V5).
R7: the 24h volume is partial, and no 30-day baseline day, when a bucket was summed without every venue."""
import re

import pytest

from test_beta_horizons_ohlc_gaps import AS_OF, CFG, EXS, h24, rows
from beta.formatter import _changes_lines, format_24h_tab
from beta.horizons import changes_checked, select_changes

ALL = dict(range_w=2.0, range_p=2.0, volume_w=10.0, volume_p=10.0, volume_w_complete=True,
           volume_p_complete=True, price_w=0.2, oi_w=0.1, funding_now=0.0001, funding_p=0.0001)


def test_checked_lists_only_the_rules_with_inputs_on_both_windows():
    assert changes_checked(**ALL) == ["range", "volume", "oi_price", "funding"]
    assert select_changes(CFG, **ALL) == []
    gone = {**ALL, "range_p": None, "volume_p_complete": False, "oi_w": None, "funding_p": None}
    assert changes_checked(**gone) == []


@pytest.mark.parametrize("lang,full,part,na", [
    ("ru", "К предыдущим 24 ч крупных изменений нет по проверкам: диапазон, объём, OI вместе с ценой и смена знака Funding",
     "К предыдущим 24 ч крупных изменений нет по проверкам: диапазон и объём (не проверено: OI вместе с ценой и смена знака Funding — нет данных)",
     "Сравнить с предыдущими 24 ч нельзя: данных не хватает"),
    ("en", "No large change vs previous 24h in the checks: range, volume, OI together with price and Funding sign change",
     "No large change vs previous 24h in the checks: range and volume (not checked: OI together with price and Funding sign change — no data)",
     "No comparison with the previous 24h: not enough data"),
])
def test_none_names_its_checks_and_is_never_said_when_none_ran(lang, full, part, na):
    assert _changes_lines({"changes": [], "changes_checked": ["range", "volume", "oi_price", "funding"]}, lang) == [full]
    assert _changes_lines({"changes": [], "changes_checked": ["range", "volume"]}, lang) == [part]
    assert _changes_lines({"changes": [], "changes_checked": []}, lang) == [na]
    assert _changes_lines({"changes": []}, lang) == []                   # pre-V5: which checks ran is unknown


def test_a_found_change_is_listed_as_before():
    out = _changes_lines({"changes": [{"rule": "oi_price", "oi_up": True, "price_up": False}],
                          "changes_checked": ["oi_price"]}, "ru")
    assert out == ["Изменения к предыдущим 24 ч:", "· OI вырос, пока цена падала"]


def test_a_bucket_without_one_venue_makes_the_volume_partial():
    full = h24(rows(288))
    assert full["volume_complete"] and not full["volume_partial"]
    one = h24(rows(288, gaps={100: (EXS[-1],)}))                       # 2 of 3 venues in one bucket
    assert not one["volume_complete"] and one["volume_partial"] and one["volume_venue_gap"]
    assert one["price_complete"]                                       # the price rule is unchanged
    every = h24(rows(288, gaps={100: tuple(EXS)}))                     # no venue's OHLC: says nothing of volume
    assert every["volume_complete"]


def test_a_partial_volume_day_is_no_baseline_day():
    from datetime import timedelta
    from beta.horizons import _baseline_24h
    days = 25
    r = rows(288 * (days + 1))
    clean = _baseline_24h(CFG, r, AS_OF)["days"]["volume_notional_usd"]
    k = 288 * (days + 1) - 1 - 288                                     # a bucket inside yesterday's window
    r2 = rows(288 * (days + 1), gaps={k - 10: (EXS[0],)})
    assert _baseline_24h(CFG, r2, AS_OF)["days"]["volume_notional_usd"] == clean - 1
