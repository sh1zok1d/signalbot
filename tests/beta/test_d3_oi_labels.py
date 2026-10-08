"""D3 (docs/BETA_DATA_RELIABILITY_FIX_PLAN_V1.md R4, R5): the OI headline is a cross-venue median and says so;
it needs at least two venues on every horizon; the «обычно» comparator (Binance's daily |change| since 2020)
stands beside Binance's own 24h change, never beside the median. Synthetic payloads."""
import re

import pytest

from test_beta_btc_view import CFG
from beta import horizons as hz
from beta.formatter import _horizon_oi_line, _line_24h, derivative_lines, format_24h_tab, horizon_oi

OI_STATS = {"change_pct": None, "typical_abs_pct": 1.84, "n_days": 1500, "source": "binance"}


def plain(s):
    return re.sub(r"<[^>]+>", "", s)


def _view(by, med):
    h24 = {"oi_change_pct": med, "oi_by_venue": by, "funding_rate_avg": None, "price_complete": False,
           "window_end": "2026-10-08T12:00:00+00:00"}
    return {"horizons": {"version": hz.HORIZON_VERSION, "24h": h24}, "derivatives": {"oi_24h": OI_STATS},
            "now": {"reference_price": 64000.0}}


def test_one_venue_never_makes_the_oi_headline():
    T, E = "start", "end"
    one = {T: {"binance": {"x": 1}}, E: {"binance": {"x": 2}}}
    import beta.horizons as H
    orig = H.venue_oi_change_pct
    H.venue_oi_change_pct = lambda a, b: None if a is None or b is None else 4.4
    try:
        out = H._oi_for(CFG, T, E, one)
        assert out["oi_change_pct"] is None and out["oi_by_venue"]["binance"] == 4.4
        two = {T: {"binance": {"x": 1}, "okx": {"x": 1}}, E: {"binance": {"x": 2}, "okx": {"x": 2}}}
        assert H._oi_for(CFG, T, E, two)["oi_change_pct"] == 4.4
    finally:
        H.venue_oi_change_pct = orig


def test_a_stored_block_with_one_venue_shows_no_headline():
    view = _view({"binance": None, "bybit": None, "okx": 4.4}, 4.4)     # a payload stored before V4
    assert horizon_oi(view["horizons"]["24h"]) is None
    assert "OI за 24ч н/д" in _line_24h(view, "ru") and "4,4" not in _line_24h(view, "ru")
    assert _horizon_oi_line(view["horizons"]["24h"], "ru").startswith("OI: ")       # venues only, no headline


@pytest.mark.parametrize("lang,head,usual", [
    ("ru", "OI +3,2% за 24ч (медиана бирж; Binance +2,7%, обычно ±1,8%, N=1500 дн.)",
     "   Binance +2,7% · обычно OI Binance за сутки меняется на ±1,8% (медиана, N=1500 дн.)"),
    ("en", "OI +3.2% over 24h (median across exchanges; Binance +2.7%, usually ±1.8%, N=1500 days)",
     "   Binance +2.7% · Binance OI usually moves ±1.8% a day (median, N=1500 days)"),
])
def test_the_median_is_labelled_and_usual_stands_beside_binance(lang, head, usual):
    view = _view({"binance": 2.71, "bybit": 3.24, "okx": 3.9}, 3.24)
    assert head in _line_24h(view, lang)
    assert derivative_lines(view, lang, part="oi") == [usual]
    tab = plain(format_24h_tab(CFG, view, lang))
    assert ("OI +3,2% (медиана бирж): Binance +2,7%" if lang == "ru"
            else "OI +3.2% (median across exchanges): Binance +2.7%") in tab


def test_without_binance_no_usual_beside_the_median():
    view = _view({"binance": None, "bybit": 3.24, "okx": 3.9}, 3.57)
    line = _line_24h(view, "ru")
    assert "OI +3,6% за 24ч (медиана бирж)" in line and "обычно ±" not in line
    assert derivative_lines(view, "ru", part="oi") == []


def test_v3_payloads_keep_the_day_type_rule_after_the_v4_bump():
    from beta.formatter import _day_type_tod
    for v in ("BETA_HORIZON_TOD_V3", "BETA_HORIZON_TOD_V4"):
        assert _day_type_tod({"horizons": {"version": v}}, "volume_notional_usd_sum")
    assert not _day_type_tod({"horizons": {"version": "BETA_HORIZON_TOD_V2"}}, "volume_notional_usd_sum")
    assert hz.HORIZON_VERSION == "BETA_HORIZON_TOD_V4" and hz.verify_horizon_digest()
    assert hz.horizon_definition()["oi"]["min_venues"]
