"""Data reliability D2 (docs/BETA_DATA_RELIABILITY_FIX_PLAN_V1.md R1, R2): how a venue's liquidation
rows of one bucket were written, how old tape rows are read, and how OKX is shown. Pure."""
from datetime import datetime, timedelta, timezone

from beta.liq_mapping import (LIQ_MAPPING_KEY, MIXED, NEW, OLD, UNPROVEN, bucket_state, correct_metrics,
                              correct_raw_rows, mark_okx_lower_bound, okx_liq_shown, without_okx_liq)

T = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
CUT = {"bybit": {"first_new": T + timedelta(minutes=2), "last_old": T + timedelta(minutes=1)},
       "okx": {"first_new": T + timedelta(minutes=7), "last_old": None}}


def test_each_bucket_knows_how_its_rows_were_written():
    assert bucket_state(CUT, "bybit", T - timedelta(minutes=5)) == OLD
    assert bucket_state(CUT, "bybit", T) == MIXED                    # the restart's own bucket
    assert bucket_state(CUT, "bybit", T + timedelta(minutes=5)) == NEW
    assert bucket_state(CUT, "okx", T) == UNPROVEN and bucket_state(CUT, "okx", T + timedelta(minutes=5)) == NEW
    assert bucket_state(CUT, "binance", T - timedelta(days=9)) == NEW
    none = {"bybit": {"first_new": None, "last_old": T}, "okx": {"first_new": None, "last_old": None}}
    assert bucket_state(none, "bybit", T + timedelta(days=1)) == OLD and bucket_state(none, "okx", T) == UNPROVEN


def test_old_rows_are_corrected_once_and_marked():
    m = {"x:bybit:long_liquidation_notional": 1.0, "x:bybit:short_liquidation_notional": 9.0,
         "x:okx:long_liquidation_notional": 0.0, "x:okx:short_liquidation_notional": 0.0,
         "x:binance:long_liquidation_notional": 3.0, "x:binance:short_liquidation_notional": 4.0, "c:x": 5.0}
    old = correct_metrics(m, T - timedelta(minutes=5), CUT, ("binance", "bybit", "okx"))
    assert (old["x:bybit:long_liquidation_notional"], old["x:bybit:short_liquidation_notional"]) == (9.0, 1.0)
    assert old["x:okx:long_liquidation_notional"] is None and old["x:binance:long_liquidation_notional"] == 3.0
    assert old["c:x"] == 5.0 and old[LIQ_MAPPING_KEY] == 2.0
    assert correct_metrics(old, T - timedelta(minutes=5), CUT, ("bybit",)) == old          # never twice
    mixed = correct_metrics(m, T, CUT, ("bybit",))
    assert mixed["x:bybit:long_liquidation_notional"] is None and mixed["x:bybit:short_liquidation_notional"] is None
    assert correct_metrics(m, T + timedelta(minutes=5), CUT, ("bybit",))["x:bybit:long_liquidation_notional"] == 1.0


def test_raw_rows_old_bybit_swapped_old_okx_dropped():
    rows = [{"exchange": "bybit", "side": "long", "mapping_version": None},
            {"exchange": "bybit", "side": "long", "mapping_version": 2},
            {"exchange": "okx", "side": "long", "mapping_version": None},
            {"exchange": "binance", "side": "long", "mapping_version": None}]
    assert [(r["exchange"], r["side"]) for r in correct_raw_rows(rows)] == [
        ("bybit", "short"), ("bybit", "long"), ("binance", "long")]


def test_okx_is_shown_only_with_mature_history_and_then_as_a_lower_bound():
    """Review of #374, point 4: the OKX feed "doesn't represent the total"; a shown sum is «≥»."""
    young = {"x:okx:long_liquidation_notional": {"tier": "building"},
             "x:okx:short_liquidation_notional": {"tier": "mature"}}
    mature = {k: {"tier": "mature"} for k in young}
    assert not okx_liq_shown(young) and not okx_liq_shown(None) and okx_liq_shown(mature)
    assert without_okx_liq({"x:okx:long_liquidation_notional": 5.0, "c:y": 1})["x:okx:long_liquidation_notional"] is None
    h = {"24h": {"liquidations": {"venues": {
        "okx": {"long": {"amount": 500.0, "missing": False, "lower_bound": False},
                "short": {"amount": None, "missing": True, "lower_bound": False}},
        "bybit": {"long": {"amount": 1.0, "missing": False, "lower_bound": False}}}}}, "as_of": "x"}
    out = mark_okx_lower_bound(h)["24h"]["liquidations"]["venues"]
    assert out["okx"]["long"]["lower_bound"] is True and out["okx"]["short"]["lower_bound"] is False
    assert out["bybit"]["long"]["lower_bound"] is False


def test_the_event_tab_prints_okx_only_where_it_could_vote_and_as_a_lower_bound():
    from beta.formatter import _anchor_liq_map
    view = {"liquidations": {"long": {"per_venue": {"binance": 10.0, "bybit": 5.0, "okx": 500.0},
                                      "eligible": ["binance", "bybit"]},
                             "short": {"per_venue": {"binance": 1.0, "bybit": 2.0, "okx": 3.0},
                                       "eligible": ["binance", "bybit", "okx"]}}}
    m = _anchor_liq_map(view)
    assert m["long"]["okx"]["missing"] is True                         # «н/д» while OKX cannot vote
    assert m["short"]["okx"] == {"amount": 3.0, "missing": False, "lower_bound": True}
    assert m["long"]["bybit"]["lower_bound"] is False
