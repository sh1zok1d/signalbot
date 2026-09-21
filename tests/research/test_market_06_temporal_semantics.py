"""Adversarial open-time vs bar-end tests (red-team F-01 / F-09).

The superseded suite stored a synthetic bar at key ``e_ms`` and then
asserted against a lookup of that same key, which canonized the bug instead
of detecting it. Every fixture here represents ``open_time``, ``bar_end``,
``FEATURE_CUTOFF`` and ``T`` as four SEPARATE quantities and asserts exact
open-times.

Synthetic fixtures only. No retained bytes, no real OHLC, no outcomes.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scripts.research import market_06_cross_venue_dislocation_evaluator as ev
from scripts.research.market_06_cross_venue_dislocation_parsers import BAR_MS, PerpBar

T = datetime(2024, 6, 15, 0, 5, tzinfo=timezone.utc)
T_MS = int(T.timestamp() * 1000)
E_MS = T_MS - BAR_MS

D_E_OPEN = "2024-06-14T23:55:00Z"
NEWEST_REFERENCE_OPEN = "2024-06-14T23:50:00Z"
OLDEST_REFERENCE_OPEN = "2024-05-15T23:55:00Z"
BTC_RET_NUMERATOR_OPEN = "2024-06-14T23:55:00Z"
BTC_RET_DENOMINATOR_OPEN = "2024-06-13T23:55:00Z"
RV_FIRST_CLOSE_BAR_OPEN = "2024-06-13T23:55:00Z"
RV_LAST_CLOSE_BAR_OPEN = "2024-06-14T23:55:00Z"
ENTRY_OPEN = "2024-06-15T00:05:00Z"
FIRST_OUTCOME_OPEN = "2024-06-15T00:05:00Z"
LAST_OUTCOME_OPEN = "2024-06-16T00:00:00Z"

# The bar OPENING at the feature cutoff. It ends at T, so it is not
# available at FEATURE_CUTOFF and must never touch a feature.
LEAK_BAR_OPEN_MS = E_MS
LEAK_BAR_END_MS = E_MS + BAR_MS


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RecordingMap(dict):
    """Records every key the evaluator actually looks up."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reads: list[int] = []

    def get(self, key, default=None):
        self.reads.append(key)
        return super().get(key, default)


def _grid(leak_price: float | None = None):
    perp: dict[int, PerpBar] = {}
    spot: dict[int, float] = {}
    ts = E_MS - 9000 * BAR_MS
    idx = 0
    while ts <= T_MS + 400 * BAR_MS:
        idx += 1
        px = 100.0 + (idx % 97) * 0.01
        perp[ts] = PerpBar(ts, px, px + 0.5, px - 0.5, px + 0.1)
        spot[ts] = px
        ts += BAR_MS
    if leak_price is not None:
        perp[LEAK_BAR_OPEN_MS] = PerpBar(
            LEAK_BAR_OPEN_MS,
            leak_price,
            leak_price * 2.0,
            leak_price / 2.0,
            leak_price,
        )
        spot[LEAK_BAR_OPEN_MS] = leak_price / 7.0
    return perp, spot


def _consumed_open_times():
    perp, spot = _grid()
    p, s = RecordingMap(perp), RecordingMap(spot)
    row = ev.construct_row_or_none(T_MS, "HOLDOUT_2024", p, s)
    assert row is not None
    spot_reads = s.reads
    perp_tail = p.reads[len(spot_reads):]
    rv = perp_tail[2 : 2 + ev.RV_RETURN_COUNT + 1]
    rest = perp_tail[2 + ev.RV_RETURN_COUNT + 1 :]
    return {
        "D_E": spot_reads[0],
        "NEWEST_REFERENCE": spot_reads[1],
        "OLDEST_REFERENCE": spot_reads[ev.REFERENCE_COUNT],
        "BTC_RET_NUMERATOR": perp_tail[0],
        "BTC_RET_DENOMINATOR": perp_tail[1],
        "RV_FIRST_CLOSE_BAR": rv[0],
        "RV_LAST_CLOSE_BAR": rv[-1],
        "ENTRY": rest[0],
        "FIRST_OUTCOME": rest[1],
        "LAST_OUTCOME": rest[-1],
        "_all_reads": set(p.reads) | set(s.reads),
        "_outcome_count": len(rest) - 1,
    }


def test_bar_open_for_close_at_is_the_single_mapping():
    assert ev.bar_open_for_close_at(E_MS) == E_MS - BAR_MS
    assert ev.bar_end_for_open_at(E_MS - BAR_MS) == E_MS
    assert ev.feature_cutoff_ms(T_MS) == E_MS


def test_feature_side_helpers_use_ending_at_semantics():
    perp, spot = _grid()
    bar = ev.get_perp_bar_ending_at(perp, E_MS)
    assert bar is not None
    assert iso(bar.open_time_ms) == D_E_OPEN
    assert ev.bar_end_for_open_at(bar.open_time_ms) == E_MS
    # opening-at is a DIFFERENT bar, and is what entry/outcome use
    opening = ev.get_perp_bar_opening_at(perp, T_MS)
    assert iso(opening.open_time_ms) == ENTRY_OPEN


@pytest.mark.parametrize(
    "label,expected",
    [
        ("D_E", D_E_OPEN),
        ("NEWEST_REFERENCE", NEWEST_REFERENCE_OPEN),
        ("OLDEST_REFERENCE", OLDEST_REFERENCE_OPEN),
        ("BTC_RET_NUMERATOR", BTC_RET_NUMERATOR_OPEN),
        ("BTC_RET_DENOMINATOR", BTC_RET_DENOMINATOR_OPEN),
        ("RV_FIRST_CLOSE_BAR", RV_FIRST_CLOSE_BAR_OPEN),
        ("RV_LAST_CLOSE_BAR", RV_LAST_CLOSE_BAR_OPEN),
        ("ENTRY", ENTRY_OPEN),
        ("FIRST_OUTCOME", FIRST_OUTCOME_OPEN),
        ("LAST_OUTCOME", LAST_OUTCOME_OPEN),
    ],
)
def test_exact_open_times_consumed(label, expected):
    assert iso(_consumed_open_times()[label]) == expected


def test_rv_final_return_ends_at_feature_cutoff_not_at_t():
    consumed = _consumed_open_times()
    last_close_bar = consumed["RV_LAST_CLOSE_BAR"]
    assert ev.bar_end_for_open_at(last_close_bar) == E_MS
    assert ev.bar_end_for_open_at(last_close_bar) != T_MS


def test_outcome_window_is_288_bars_opening_at_t():
    consumed = _consumed_open_times()
    assert consumed["_outcome_count"] == ev.FUTURE_BARS == 288
    assert consumed["ENTRY"] == T_MS
    assert consumed["LAST_OUTCOME"] == T_MS + 287 * BAR_MS
    assert consumed["LAST_OUTCOME"] < T_MS + 288 * BAR_MS


def test_bar_opening_at_feature_cutoff_is_never_read_for_features():
    """The [E, E+5m) bar ends at T and must not be a feature input."""

    consumed = _consumed_open_times()
    feature_keys = {
        consumed[name]
        for name in (
            "D_E",
            "NEWEST_REFERENCE",
            "OLDEST_REFERENCE",
            "BTC_RET_NUMERATOR",
            "BTC_RET_DENOMINATOR",
            "RV_FIRST_CLOSE_BAR",
            "RV_LAST_CLOSE_BAR",
        )
    }
    assert LEAK_BAR_OPEN_MS not in feature_keys
    assert LEAK_BAR_END_MS == T_MS


def test_malicious_bar_at_feature_cutoff_cannot_move_any_feature():
    """Extreme prices on [E, E+5m) must leave every feature identical."""

    clean_perp, clean_spot = _grid()
    clean = ev.construct_row_or_none(T_MS, "HOLDOUT_2024", clean_perp, clean_spot)
    assert clean is not None

    for leak_price in (1.0, 1e9):
        perp, spot = _grid(leak_price=leak_price)
        poisoned = ev.construct_row_or_none(T_MS, "HOLDOUT_2024", perp, spot)
        assert poisoned is not None
        assert poisoned.abs_dislocation_z == clean.abs_dislocation_z
        assert poisoned.btc_side == clean.btc_side
        assert poisoned.abs_btc_ret_24h == clean.abs_btc_ret_24h
        assert poisoned.rv_btc_24h == clean.rv_btc_24h


def test_reference_window_excludes_d_e_by_boundary_not_by_key():
    consumed = _consumed_open_times()
    perp, spot = _grid()
    ref_boundaries = [E_MS - k * BAR_MS for k in range(1, ev.REFERENCE_COUNT + 1)]
    ref_opens = {ev.bar_open_for_close_at(b) for b in ref_boundaries}
    assert consumed["D_E"] not in ref_opens
    assert consumed["NEWEST_REFERENCE"] in ref_opens
    assert consumed["OLDEST_REFERENCE"] in ref_opens
    assert len(ref_opens) == ev.REFERENCE_COUNT == 8640
