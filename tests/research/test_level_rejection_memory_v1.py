"""LEVEL_REJECTION_MEMORY_V1 pair semantics. No market panel is read."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from beta.hist_series import BARS_PER_DAY, Bars

from scripts.research.level_rejection_memory_v1 import claim, constants as K, hits, inference, pairs
from scripts.research.level_touch_degradation_v1 import constants as P
from scripts.research.level_touch_degradation_v1 import events, outcomes
from scripts.research.level_touch_degradation_v1.data import assert_panel_legal
from scripts.research.level_touch_degradation_v1.events import level_instances

REPO_EDGE = (K.PARENT_SIGMA_LO, K.PARENT_SIGMA_HI)


def _ms(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _x_sigma(x: float = 0.01) -> float:
    return x / (P.BARRIER_FRACTION_PRIMARY * P.CORRIDOR_Z * P.HOLD_BARS_PRIMARY ** 0.5)


def _episode(i0, i1, price=100.0, kind="PDH", family="DAY"):
    w = P.ZONE_HALF_PRIMARY
    return {
        "episode_id": f"{kind}:0:{i0}", "kind": kind, "family": family,
        "struct_side": 1, "priority": P.PRIORITY[kind], "anchor_price": price,
        "zone_low": price * (1 - w), "zone_high": price * (1 + w),
        "i0": i0, "i1": i1, "period_open": price, "source_key": 0, "period_key": 1,
        "member_kinds": [kind], "n_members": 1, "absorbed_later": [],
        "population": "real", "zone_half": w,
    }


def _flat(n, price, sigma):
    c = np.full(n, price)
    return c.copy(), c.copy(), c.copy(), c.copy(), np.full(n, sigma)


def _story_bars():
    """Touch 1 rejects on the next bar, price leaves, touch 2 breaks."""
    n = 250
    sigma = _x_sigma(0.01)
    o, h, l, c = (np.full(n, 99.0) for _ in range(4))
    h[:] = 99.2
    l[:] = 98.9
    # touch 1
    h[100], l[100], c[100], o[100] = 100.1, 99.5, 100.0, 99.4
    # reject, not yet a full clearance (high still above zlo*(1-X))
    h[101], l[101], c[101], o[101] = 99.0, 98.0, 98.5, 100.0
    # clearance
    h[102], l[102], c[102] = 98.5, 98.0, 98.2
    h[103:111] = 98.4
    l[103:111] = 97.5
    c[103:111] = 98.0
    # touch 2
    o[111], h[111], l[111], c[111] = 98.5, 100.3, 99.0, 100.1
    # break, low stays above the reject barrier
    o[112], h[112], l[112], c[112] = 100.1, 102.0, 100.0, 101.5
    return o, h, l, c, np.full(n, sigma)


def test_passage_matches_parent_classify_and_counts_bars():
    rng = np.random.default_rng(7)
    high = 100 + rng.normal(0, 1, 80)
    low = high - rng.uniform(0.1, 2.0, 80)
    label, b_break, b_reject = hits.passage(high, low, 10, 1, 99.0, 101.0, 0.01, 48)
    parent = outcomes.classify(high, low, 10, 1, 99.0, 101.0, 0.01, 48)
    assert label == parent
    if label == "REJECT":
        assert b_reject is not None and b_reject < (b_break or 99)


def test_rejection_time_ignores_bars_after_the_hit():
    o, h, l, c, sigma = _story_bars()
    label, _, bars = hits.passage(h, l, 100, 1, 100 * 0.9985, 100 * 1.0015, 0.01, 48)
    assert label == "REJECT" and bars == 1
    h2 = h.copy()
    h2[102:] = 200
    l2 = l.copy()
    l2[102:] = 1
    label2, _, bars2 = hits.passage(h2, l2, 100, 1, 100 * 0.9985, 100 * 1.0015, 0.01, 48)
    assert (label2, bars2) == (label, bars)


def test_fixture_fast_reject_then_break_is_one_pair():
    o, h, l, c, sigma = _story_bars()
    t0 = _ms(2020, 2, 1)
    ep = _episode(0, 240)
    raw = events.scan_episode(h, l, c, o, sigma, t0, ep, end_ms=P.SURFACE_END_MS)
    touched = hits.annotate(h, l, raw)
    assert [t["touch_number"] for t in touched][:2] == [1, 2]
    assert touched[0]["outcome"] == "REJECT" and touched[0]["bars_to_reject"] == 1
    assert touched[1]["outcome"] == "BREAK"
    feat = pairs.pair_features(touched[0], touched[1])
    assert feat is not None
    assert feat["bars_to_reject"] == 1
    assert feat["gap_bars"] == touched[1]["j"] - (touched[0]["j"] + 1)
    assert feat["gap_bars"] + feat["bars_to_reject"] == touched[1]["j"] - touched[0]["j"]
    assert "next_outcome" not in feat
    rows, drops = pairs.analysis_pairs(touched)
    assert len(rows) == 1 and rows[0]["next_outcome"] == "BREAK" and drops["ambiguous"] == 0
    assert rows[0]["next_bucket"] == "2" and rows[0]["touch3"] == 0
    assert rows[0]["side"] == 1 and rows[0]["year"] == 2020


def test_break_then_retest_is_not_a_pair():
    o, h, l, c, sigma = _story_bars()
    # Make touch 1 break before any reject: bar 101 trades up through the break barrier.
    h[101], l[101], c[101] = 102.0, 100.2, 101.0
    t0 = _ms(2020, 2, 1)
    raw = events.scan_episode(h, l, c, o, sigma, t0, _episode(0, 240), end_ms=P.SURFACE_END_MS)
    touched = hits.annotate(h, l, raw)
    assert touched[0]["outcome"] == "BREAK"
    assert pairs.feature_pairs(touched) == []


def test_slow_rejection_is_a_larger_bar_count():
    o, h, l, c, sigma = _story_bars()
    # Hold inside/near the zone until bar 130, then reject and clear, then a later touch.
    for j in range(101, 130):
        o[j], h[j], l[j], c[j] = 100.0, 100.1, 99.9, 100.0
    h[130], l[130], c[130] = 99.0, 98.0, 98.5
    h[131], l[131], c[131] = 98.5, 98.0, 98.2
    for j in range(132, 160):
        o[j], h[j], l[j], c[j] = 98.0, 98.4, 97.5, 98.0
    o[160], h[160], l[160], c[160] = 98.5, 100.2, 99.0, 100.0
    o[161], h[161], l[161], c[161] = 100.0, 100.05, 99.9, 100.0  # neither barrier in the first bars
    t0 = _ms(2020, 2, 1)
    raw = events.scan_episode(h, l, c, o, sigma, t0, _episode(0, 240), end_ms=P.SURFACE_END_MS)
    touched = hits.annotate(h, l, raw)
    assert touched[0]["outcome"] == "REJECT"
    assert touched[0]["bars_to_reject"] == 30
    feat = pairs.pair_features(touched[0], touched[1])
    assert feat["bars_to_reject"] == 30
    assert feat["speed_raw"] == pytest.approx(-np.log(30.0))
    assert feat["j_next"] > feat["j_reject"]


def test_predictor_does_not_read_the_next_outcome():
    prev = _manual("E", 1, 10, "REJECT", bars=4)
    nxt = _manual("E", 2, 40, "BREAK")
    a = pairs.pair_features(prev, nxt)
    nxt["outcome"] = "NEITHER"
    b = pairs.pair_features(prev, nxt)
    assert a == b and "next_outcome" not in a


def test_neither_stays_in_the_sample_and_ambiguous_is_dropped():
    prev = _manual("E", 1, 10, "REJECT", bars=4)
    nxt = _manual("E", 2, 40, "NEITHER")
    rows, drops = pairs.analysis_pairs([prev, nxt])
    assert len(rows) == 1 and rows[0]["next_outcome"] == "NEITHER" and drops["ambiguous"] == 0
    nxt["outcome"] = "AMBIGUOUS"
    rows, drops = pairs.analysis_pairs([prev, nxt])
    assert rows == [] and drops["ambiguous"] == 1


def test_two_rejection_pairs_on_one_level_keep_touch_numbers():
    t1 = _manual("E", 1, 10, "REJECT", bars=3)
    t2 = _manual("E", 2, 30, "REJECT", bars=5)
    t3 = _manual("E", 3, 80, "BREAK")
    rows, _ = pairs.analysis_pairs([t1, t2, t3])
    assert [r["next_touch_number"] for r in rows] == [2, 3]
    assert [r["next_bucket"] for r in rows] == ["2", "3+"]
    assert rows[0]["cluster"] == rows[1]["cluster"]


def test_support_side_and_vol_tercile_and_year_come_from_the_next_touch():
    prev = _manual("E", 1, 10, "REJECT", bars=2, year=2020)
    nxt = _manual("E", 2, 50, "BREAK", side=-1, year=2021, sigma=0.002)
    feat = pairs.pair_features(prev, nxt)
    assert feat["support"] == 1 and feat["side"] == -1
    assert feat["vol_tercile"] == 2 and feat["year"] == 2021
    nxt["sigma"] = 0.001
    assert pairs.pair_features(prev, nxt)["vol_tercile"] == 0


def test_month_cluster_is_the_episode_and_day_cluster_is_the_week():
    assert pairs.cluster_key("MONTH", "PMH:1:2", 99).startswith("M:")
    assert pairs.cluster_key("DAY", "PDH:1:2", 99) == "W:99"
    assert pairs.cluster_key("WEEK", "PWH:1:2", 99) == "W:99"


def test_gap_nonpositive_is_not_a_pair():
    prev = _manual("E", 1, 10, "REJECT", bars=8)
    nxt = _manual("E", 2, 12, "BREAK")  # j_reject = 18, next is earlier
    assert pairs.pair_features(prev, nxt) is None


def test_missing_window_does_not_form_a_pair():
    o, h, l, c, sigma = _story_bars()
    # Touch 1's 4h window ends at bar 148. Blank only the tail of touch 2's window.
    h[149:180] = np.nan
    l[149:180] = np.nan
    t0 = _ms(2020, 2, 1)
    raw = events.scan_episode(h, l, c, o, sigma, t0, _episode(0, 240), end_ms=P.SURFACE_END_MS)
    touched = hits.annotate(h, l, raw)
    assert touched[0]["outcome"] == "REJECT"
    assert pairs.feature_pairs(touched) == []


def test_level_price_ignores_the_active_period_extreme():
    t0 = _ms(2020, 1, 5)
    b = Bars(t0=t0, open=np.full(2 * BARS_PER_DAY, 95.0), high=np.full(2 * BARS_PER_DAY, 95.0),
             low=np.full(2 * BARS_PER_DAY, 95.0), close=np.full(2 * BARS_PER_DAY, 95.0),
             volume=np.ones(2 * BARS_PER_DAY), quote=np.ones(2 * BARS_PER_DAY),
             taker_buy_quote=np.ones(2 * BARS_PER_DAY), oi=np.full(2 * BARS_PER_DAY, np.nan))
    b.high[10] = 100.0
    inst, _ = level_instances(b)
    assert [r["price"] for r in inst if r["kind"] == "PDH"] == [100.0]
    b.high[BARS_PER_DAY + 5] = 250.0
    inst2, _ = level_instances(b)
    assert [r["price"] for r in inst2 if r["kind"] == "PDH"] == [100.0]


def test_protected_interval_is_refused():
    open_ms = np.array([P.E1_START_MS])
    with pytest.raises(RuntimeError):
        assert_panel_legal(open_ms)


def test_control_rotation_is_deterministic():
    from scripts.research.level_touch_degradation_v1.control import control_episodes
    eps = []
    inst = []
    for i, price in enumerate((100.0, 110.0, 120.0)):
        ep = _episode(i * 10, i * 10 + 5, price=price)
        ep["episode_id"] = f"PDH:{i}"
        ep["period_open"] = 100.0
        ep["anchor_price"] = price
        eps.append(ep)
        inst.append({"price": price, "i0": ep["i0"], "i1": ep["i1"]})
    a = control_episodes(eps, inst, P.ZONE_HALF_PRIMARY)
    b = control_episodes(list(reversed(eps)), list(reversed(inst)), P.ZONE_HALF_PRIMARY)
    assert [r["episode_id"] for r in a] == [r["episode_id"] for r in b]
    assert a and all(r["population"] == "control" for r in a)


def test_overshoot_uses_only_the_rejecting_bar():
    high = np.zeros(10)
    low = np.zeros(10)
    low[3] = 90.0
    high[3] = 95.0
    # j=1, bars_to_reject=2 → bar index 3. zone_low=100, x=0.01, reject_px=99, unit=1
    value = hits.overshoot_at_reject(high, low, 1, 1, 100.0, 101.0, 0.01, 2)
    assert value == pytest.approx((99.0 - 90.0) / 1.0)
    low[4] = 1.0
    assert hits.overshoot_at_reject(high, low, 1, 1, 100.0, 101.0, 0.01, 2) == value


def test_lpm_sign_and_frozen_scale_on_a_known_slope():
    scales = {
        "speed_mean": 0.0, "speed_sd": 1.0,
        "linear_mean": 0.0, "linear_sd": 1.0,
        "gap_mean": 0.0, "gap_sd": 1.0,
        "overshoot_mean": 0.0, "overshoot_sd": 1.0,
        "speed_q33": -0.2, "speed_q66": 0.2,
    }
    rows = []
    for i in range(80):
        speed = -1.0 if i < 40 else 1.0
        rows.append({
            "speed_raw": speed, "linear_raw": speed, "overshoot": 0.0, "log_gap": 0.03 * i,
            "touch3": 1 if i % 2 == 0 else 0, "family": ("DAY", "WEEK", "MONTH")[i % 3],
            "support": 1 if (i // 2) % 2 == 0 else 0,
            "vol_tercile": (i // 3) % 3, "year": 2020 + (i % 5), "next_outcome": "BREAK" if speed > 0 and i % 4 != 0 else "NEITHER",
            "cluster": f"W:{i // 4}", "side": 1, "next_bucket": "3+" if i % 2 else "2",
        })
    # Faster half breaks more often, so the coefficient is positive. Draws stay small.
    out = inference.lpm_effect(rows, scales, draws=30, seed=1)
    assert out["coef"] is not None and out["coef"] > 0
    assert out["ci95"] is not None


def test_integration_requires_the_adjusted_coefficient():
    primary = {"coef": 0.04, "ci95": [0.01, 0.07]}
    years = [{"n": 40, "coef": 0.02} for _ in range(4)] + [{"n": 10, "coef": -0.2}]
    control = {"coef": 0.0, "ci95": [-0.01, 0.01]}
    flag = claim.integration_candidate(primary, years, control, max_year_share=0.3,
                                       max_family_share=0.5, clusters=120)
    assert flag["candidate"] is True
    killed = claim.integration_candidate(
        {"coef": 0.01, "ci95": [-0.02, 0.03]}, years, control,
        max_year_share=0.3, max_family_share=0.5, clusters=120)
    assert killed["candidate"] is False


def test_preflight_module_does_not_aggregate_next_outcomes():
    import scripts.research.level_rejection_memory_v1.preflight as preflight
    text = open(preflight.__file__, encoding="utf-8").read()
    assert "next_outcome" in text  # the guard that forbids the key
    assert "p_break" not in text
    assert "endpoint" not in text


def _manual(eid, number, j, outcome, bars=None, side=1, family="DAY", year=2020, week=100,
            sigma=0.0015, overshoot=0.1):
    bucket = "1" if number <= 1 else "2" if number == 2 else "3+"
    return {
        "episode_id": eid, "touch_number": number, "bucket": bucket, "j": j,
        "outcome": outcome, "bars_to_reject": bars, "feature_eligible": True,
        "side": side, "family": family, "year": year, "week": week, "sigma": sigma,
        "overshoot": overshoot, "population": "real",
    }
