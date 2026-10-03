"""Long-window (24h, /catchup span) price completeness with per-venue OHLC gaps.

A bucket row may exist while a venue's kline OHLC is NULL (an internal OHLC gap).
For the 24h window and the /catchup span that is one missing observation for that
venue, under the same allowance as a missing row (282 of 288, scaled for a shorter
span); the first and last bucket stay mandatory. The 1h and 4h windows are unchanged:
every bucket must be complete. Pure; no DB."""
from datetime import datetime, timedelta, timezone

from beta import context as cx
from beta.config import BetaConfig
from beta.horizons import rolling_24h_values, span_min_present
from beta.state_tape import BUCKET, metric_key

CFG = BetaConfig.load()
EXS = CFG.exchanges
AS_OF = datetime(2026, 10, 3, 6, 0, tzinfo=timezone.utc)
OHLC = ("kline_open", "kline_high", "kline_low", "kline_close")


def rows(n, *, gaps=None, as_of=AS_OF):
    """n complete rows ending at `as_of`; `gaps` = {bucket_index_from_oldest: venues}
    whose OHLC is NULL in that (still present) row."""
    gaps = gaps or {}
    out = {}
    for i in range(n):
        b = as_of - (n - 1 - i) * BUCKET
        row = {"c:volume_notional_usd_sum": 1.0, "c:taker_delta_notional_usd_sum": 1.0,
               "c:funding_rate_median": 0.0001}
        for ex in EXS:
            null = ex in gaps.get(i, ())
            row[metric_key(ex, "kline_open")] = None if null else 100.0
            row[metric_key(ex, "kline_high")] = None if null else 101.0
            row[metric_key(ex, "kline_low")] = None if null else 99.0
            row[metric_key(ex, "kline_close")] = None if null else 100.5
        out[b] = row
    return out


def internal(k, n, venues=EXS):
    """k internal OHLC gaps on `venues`, away from the first and the last bucket."""
    return {i: tuple(venues) for i in range(5, 5 + k)}


def h24(r):
    return rolling_24h_values(CFG, r, AS_OF)


def span(r, n):
    return rolling_24h_values(CFG, r, AS_OF, n=n, min_present=span_min_present(n))


# A
def test_24h_one_internal_bucket_with_null_ohlc_on_every_venue_is_complete():
    out = h24(rows(288, gaps=internal(1, 288)))
    assert out["buckets_present"] == 288
    assert out["price_complete"]
    assert out["price_move_pct"] == 0.5 and out["high"] == 101.0 and out["low"] == 99.0
    assert out["volume_complete"]                       # volume semantics unchanged: every row has volume


# B
def test_24h_allowance_is_six_internal_ohlc_gaps_not_seven():
    assert h24(rows(288, gaps=internal(6, 288)))["price_complete"]
    assert not h24(rows(288, gaps=internal(7, 288)))["price_complete"]


def test_24h_allowance_counts_missing_rows_and_ohlc_gaps_together():
    r = rows(288, gaps=internal(3, 288))
    for i in (100, 101, 102):                           # three rows missing as well -> 6 in total
        del r[AS_OF - (287 - i) * BUCKET]
    assert h24(r)["price_complete"]
    del r[AS_OF - (287 - 103) * BUCKET]                 # 7 in total
    assert not h24(r)["price_complete"]


# C
def test_8h_catchup_span_uses_the_scaled_allowance():
    n = 96
    assert span_min_present(n) == 94
    assert span(rows(n, gaps=internal(2, n)), n)["price_complete"]
    assert not span(rows(n, gaps=internal(3, n)), n)["price_complete"]


# D, E
def test_first_and_last_bucket_ohlc_stay_mandatory():
    assert not h24(rows(288, gaps={0: EXS}))["price_complete"]
    assert not h24(rows(288, gaps={287: EXS}))["price_complete"]
    assert not span(rows(96, gaps={0: EXS}), 96)["price_complete"]
    assert not span(rows(96, gaps={95: EXS}), 96)["price_complete"]


def test_a_missing_end_on_one_venue_drops_only_that_venue():
    assert len(EXS) == 3 and CFG.min_venues == 2
    assert h24(rows(288, gaps={0: (EXS[0],)}))["price_complete"]           # two venues still usable
    assert h24(rows(288, gaps={287: (EXS[0],)}))["price_complete"]
    assert not h24(rows(288, gaps={0: (EXS[0],), 287: (EXS[1],)}))["price_complete"]   # one venue left


# F
def test_one_thin_venue_is_dropped_and_two_full_venues_still_complete():
    gaps = {i: (EXS[0],) for i in range(5, 15)}         # 10 gaps on one venue only
    out = h24(rows(288, gaps=gaps))
    assert out["price_complete"] and out["price_move_pct"] == 0.5


# G
def test_only_one_usable_venue_is_not_complete():
    gaps = {i: tuple(EXS[:2]) for i in range(5, 15)}    # two venues too thin, one full
    assert CFG.min_venues == 2
    assert not h24(rows(288, gaps=gaps))["price_complete"]


def test_ohlc_gap_and_valid_observation_mix_per_venue_is_not_pooled():
    """Six gaps on venue A and six different gaps on venue B: each venue alone is
    within the allowance, so both stay usable (the allowance is per venue)."""
    gaps = {i: (EXS[0],) for i in range(5, 11)}
    gaps.update({i: (EXS[1],) for i in range(20, 26)})
    out = h24(rows(288, gaps=gaps))
    assert out["price_complete"]
    gaps.update({i: (EXS[0], EXS[1]) for i in range(30, 31)})   # one more gap on both: 7 each
    out = h24(rows(288, gaps=gaps))
    assert not out["price_complete"]                    # only one venue left


# H
def test_1h_and_4h_still_need_every_bucket_complete():
    for n in (12, 48):
        r = rows(n, gaps={n // 2: EXS})
        v = cx.rolling_window_values(CFG, r, AS_OF, n)
        assert v is not None and v["price_move_pct_median"] is None and v["range_width_pct_median"] is None
        r1 = rows(n, gaps={n // 2: (EXS[0],)})
        v1 = cx.rolling_window_values(CFG, r1, AS_OF, n)
        assert v1["venues"] == list(EXS[1:])          # the gapped venue is out of the short window
    r = rows(12, gaps={6: EXS})
    v = cx.rolling_1h_values(CFG, r, AS_OF)
    assert v["price_move_pct_median"] is None
    gap = dict(rows(12))
    del gap[AS_OF - 5 * BUCKET]                         # a missing row in a short window
    assert cx.rolling_window_values(CFG, gap, AS_OF, 12) is None
