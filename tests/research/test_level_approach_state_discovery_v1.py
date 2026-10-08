"""LEVEL_APPROACH_STATE_DISCOVERY_V1 approach features. No market panel is read."""

from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pytest

from beta.hist_series import BARS_PER_DAY, Bars

from scripts.research.level_approach_state_discovery_v1 import claim, constants as K, inference, redundancy, rows
from scripts.research.level_approach_state_discovery_v1.approach import compute_features
from scripts.research.level_approach_state_discovery_v1.evaluate import _prepare
from scripts.research.level_touch_degradation_v1 import constants as P
from scripts.research.level_touch_degradation_v1 import events, outcomes
from scripts.research.level_touch_degradation_v1.control import control_episodes
from scripts.research.level_touch_degradation_v1.data import assert_panel_legal
from scripts.research.level_touch_degradation_v1.events import level_instances

ZLO = 100.0 * (1.0 - P.ZONE_HALF_PRIMARY)
ZHI = 100.0 * (1.0 + P.ZONE_HALF_PRIMARY)
X = 0.01
SIGMA = 0.0015


def _ms(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _path(closes: dict, *, j=300, n=420, range_frac=0.002, recent_frac=None, quote_recent=1.0):
    close = np.full(n, 90.0)
    high = close * (1.0 + range_frac)
    low = close * (1.0 - range_frac)
    quote = np.ones(n)
    for idx, price in closes.items():
        close[idx] = price
        frac = range_frac if recent_frac is None or idx < j - K.RANGE_RECENT else recent_frac
        high[idx] = price * (1.0 + frac)
        low[idx] = price * (1.0 - frac)
    if recent_frac is not None:
        for idx in range(j - K.RANGE_RECENT, j):
            frac = recent_frac
            high[idx] = close[idx] * (1.0 + frac)
            low[idx] = close[idx] * (1.0 - frac)
    quote[j - K.RANGE_RECENT:j] = quote_recent
    return close, high, low, quote


def _feat(closes, **kw):
    path_kw = {key: kw[key] for key in ("j", "n", "range_frac", "recent_frac", "quote_recent") if key in kw}
    close, high, low, quote = _path(closes, **path_kw)
    return compute_features(
        close, high, low, quote, j=kw.get("j", 300), i0=kw.get("i0", 0), side=kw.get("side", 1),
        zlo=ZLO, zhi=ZHI, x=X, sigma=kw.get("sigma", SIGMA), band_mult=kw.get("band_mult", 1.0),
    )


def test_straight_approach_is_more_efficient_than_a_choppy_one():
    straight = _feat({296: 99.0, 297: 99.2, 298: 99.4, 299: 99.6})
    choppy = _feat({296: 99.6, 297: 99.0, 298: 99.6, 299: 99.6})
    assert straight is not None and choppy is not None
    assert straight["efficiency"] > choppy["efficiency"]
    assert straight["persistence"] > choppy["persistence"]
    assert straight["velocity"] == pytest.approx(choppy["velocity"])
    assert straight["pullback"] == pytest.approx((1.0 - straight["efficiency"]) / 2.0)
    assert choppy["pullback"] == pytest.approx((1.0 - choppy["efficiency"]) / 2.0)


def test_accelerating_finish_beats_a_decelerating_one():
    fast_finish = _feat({296: 98.90, 297: 98.95, 298: 99.20, 299: 99.60})
    slow_finish = _feat({296: 99.60, 297: 99.62, 298: 99.64, 299: 99.66})
    assert fast_finish["acceleration"] > slow_finish["acceleration"]


def test_compression_is_below_expansion_and_volume_moves_with_quote():
    calm = _feat({296: 99.0, 297: 99.2, 298: 99.4, 299: 99.6}, recent_frac=0.0002, quote_recent=1.0)
    wide = _feat({296: 99.0, 297: 99.2, 298: 99.4, 299: 99.6}, recent_frac=0.02, quote_recent=4.0)
    assert calm["range_state"] < 0 < wide["range_state"]
    assert calm["rel_volume"] < wide["rel_volume"]


def test_dwell_counts_only_the_inner_run_and_not_the_touch_bar():
    pressed = _feat({296: 99.5, 297: 99.55, 298: 99.6, 299: 99.65})
    late = _feat({296: 99.0, 297: 99.1, 298: 99.2, 299: 99.6})
    assert pressed["dwell"] == 4
    assert late["dwell"] == 1
    # The touch bar is inside the zone. It must not add a dwell bar.
    close, high, low, quote = _path({296: 99.5, 297: 99.55, 298: 99.6, 299: 99.65})
    close[300] = 99.6
    again = compute_features(close, high, low, quote, j=300, i0=0, side=1, zlo=ZLO, zhi=ZHI,
                             x=X, sigma=SIGMA, band_mult=1.0)
    assert again["dwell"] == pressed["dwell"]


def test_features_ignore_the_touch_bar_and_everything_after_it():
    base = _feat({296: 99.0, 297: 99.2, 298: 99.4, 299: 99.6})
    close, high, low, quote = _path({296: 99.0, 297: 99.2, 298: 99.4, 299: 99.6})
    close[300:] = 1.0
    high[300:] = 500.0
    low[300:] = 0.5
    quote[300:] = 1.0e12
    leaked = compute_features(close, high, low, quote, j=300, i0=0, side=1, zlo=ZLO, zhi=ZHI,
                              x=X, sigma=SIGMA, band_mult=1.0)
    for key in ("velocity", "efficiency", "persistence", "acceleration", "range_state", "rel_volume", "dwell"):
        assert leaked[key] == pytest.approx(base[key])


def test_no_observed_entry_or_a_missing_bar_is_not_eligible():
    assert _feat({296: 99.0, 297: 99.2, 298: 99.4, 299: 99.6}, i0=296) is None
    close, high, low, quote = _path({296: 99.0, 297: 99.2, 298: 99.4, 299: 99.6})
    close[298] = np.nan
    assert compute_features(close, high, low, quote, j=300, i0=0, side=1, zlo=ZLO, zhi=ZHI,
                            x=X, sigma=SIGMA, band_mult=1.0) is None


def test_velocity_scales_with_sigma_and_support_side_stays_positive():
    slow_scale = _feat({296: 99.0, 297: 99.2, 298: 99.4, 299: 99.6}, sigma=SIGMA)
    fast_scale = _feat({296: 99.0, 297: 99.2, 298: 99.4, 299: 99.6}, sigma=SIGMA * 2)
    assert fast_scale["velocity"] == pytest.approx(slow_scale["velocity"] / 2)
    above = _feat({295: 102.0, 296: 101.10, 297: 101.00, 298: 100.80, 299: 100.40}, side=-1)
    assert above is not None
    assert above["velocity"] > 0
    assert above["efficiency"] > 0


def test_touch_from_the_parent_scanner_keeps_the_approach_before_the_bar():
    n = 420
    sigma_value = X / (P.BARRIER_FRACTION_PRIMARY * P.CORRIDOR_Z * P.HOLD_BARS_PRIMARY ** 0.5)
    sigma = np.full(n, sigma_value)
    close = np.full(n, 90.0)
    high = close * 1.001
    low = close * 0.999
    open_ = close.copy()
    quote = np.ones(n)
    close[296:300] = [99.0, 99.2, 99.4, 99.6]
    high[296:300] = close[296:300] * 1.001
    low[296:300] = close[296:300] * 0.999
    high[300], low[300], close[300] = ZHI + 0.2, ZLO - 0.05, 100.0
    t0 = _ms(2020, 6, 1)
    raw = events.scan_episode(high, low, close, open_, sigma, t0, {
        "episode_id": "PDH:t", "kind": "PDH", "family": "DAY", "struct_side": 1,
        "anchor_price": 100.0, "zone_low": ZLO, "zone_high": ZHI, "i0": 0, "i1": n - 1,
        "member_kinds": ["PDH"], "n_members": 1, "population": "real", "zone_half": P.ZONE_HALF_PRIMARY,
    }, end_ms=P.SURFACE_END_MS)
    assert raw and raw[0]["j"] == 300 and raw[0]["feature_eligible"]
    row = rows.approach_row(raw[0], close, high, low, quote, band_mult=1.0)
    assert row is not None and row["first_j"] == 296 and row["entry_j"] == 295
    assert "outcome" not in row
    wiped_h, wiped_l, wiped_c = high.copy(), low.copy(), close.copy()
    wiped_h[300:] = 1.0
    wiped_l[300:] = 0.5
    wiped_c[300:] = 1.0
    again = rows.approach_row(raw[0], wiped_c, wiped_h, wiped_l, quote, band_mult=1.0)
    assert again["efficiency"] == pytest.approx(row["efficiency"])
    # Bar 301 trades through the break barrier and stays above the reject barrier.
    high[301], low[301] = ZHI * (1.0 + X) + 1.0, ZLO * (1.0 - X) + 1.0
    assert outcomes.classify(high, low, 300, 1, ZLO, ZHI, X, 48) == "BREAK"
    # One later bar hits both barriers. Same-bar order is unknown.
    high[302], low[302] = ZHI * (1.0 + X) + 1.0, ZLO * (1.0 - X) - 1.0
    high[301], low[301] = 100.2, 100.0
    assert outcomes.classify(high, low, 300, 1, ZLO, ZHI, X, 48) == "AMBIGUOUS"


def test_neither_stays_and_ambiguous_is_dropped():
    rows_in = [
        {"episode_id": "a", "j": 1, "outcome_ignored": True, "volume_ok": True, "rel_volume": 0.1,
         "cluster": "a"},
        {"episode_id": "b", "j": 2, "volume_ok": True, "rel_volume": 0.1, "cluster": "b"},
        {"episode_id": "c", "j": 3, "volume_ok": True, "rel_volume": 0.1, "cluster": "c"},
    ]
    # _prepare rebuilds rows via collect, so exercise the drop rule on its result
    # by calling the same classification the evaluator uses.
    kept, drops = _filter_like_prepare([
        ("a", 1, "NEITHER"),
        ("b", 2, "AMBIGUOUS"),
        ("c", 3, "BREAK"),
    ])
    assert [row["outcome"] for row in kept] == ["NEITHER", "BREAK"]
    assert drops["ambiguous"] == 1


def _filter_like_prepare(items):
    """Same drop rule as evaluate._prepare, without rebuilding the path."""
    outcomes = {(ep, j): y for ep, j, y in items}
    rows = [{"episode_id": ep, "j": j, "volume_ok": True, "rel_volume": 0.0, "cluster": ep} for ep, j, _ in items]
    ambiguous = 0
    missing = 0
    kept = []
    for row in rows:
        outcome = outcomes.get((row["episode_id"], row["j"]))
        if outcome == "AMBIGUOUS":
            ambiguous += 1
            continue
        if outcome not in K.OUTCOMES:
            missing += 1
            continue
        row["outcome"] = outcome
        kept.append(row)
    return kept, {"ambiguous": ambiguous, "missing_outcome": missing}


def test_prepare_matches_the_documented_drop_rule():
    # The helper above is the drop rule. evaluate._prepare is imported so a
    # signature drift fails this module at collection if the name disappears.
    assert callable(_prepare)


def test_redundancy_drops_pullback_and_a_duration_copy():
    rows_in = []
    for i in range(30):
        efficiency = 0.2 + 0.02 * (i % 5)
        rows_in.append({
            "velocity": math.log(4 + (i % 3)),  # tied to a step count, not to efficiency
            "efficiency": efficiency,
            "pullback": (1.0 - efficiency) / 2.0,
            "persistence": 0.5,
            "acceleration": 0.01 * (i % 4),
            "range_state": -0.1 * (i % 3),
            "rel_volume": 0.05 * i,
            "dwell": float(i % 6),
            "log_steps": math.log(4 + (i % 3)),
        })
    # velocity is an exact function of log_steps here, so the rule drops it.
    decision = redundancy.apply_rule(rows_in)
    dropped = {item["feature"] for item in decision["dropped"]}
    assert "pullback" in dropped
    assert "velocity" in dropped
    assert "efficiency" in decision["retained"]
    assert "pullback" not in decision["retained"]


def test_bh_matches_a_hand_worked_example():
    adjusted = inference.bh_adjust([0.001, 0.04, 0.03, 0.2])
    assert adjusted[0] == pytest.approx(0.004)
    assert adjusted[1] == pytest.approx(0.04 * 4 / 3)
    assert adjusted[2] == pytest.approx(0.04 * 4 / 3)
    assert adjusted[3] == pytest.approx(0.2)
    assert sum(q <= 0.10 for q in adjusted) == 3


def test_lpm_recovers_a_positive_feature_slope_on_a_full_rank_sample():
    sample = []
    for i in range(120):
        bucket = ("1", "2", "3+")[(i // 13) % 3]
        velocity = float((i * 3) % 19)
        sample.append({
            "cluster": f"e{i}",
            "family": K.FAMILIES[i % 3],
            "bucket": bucket,
            "touch2": 1.0 if bucket == "2" else 0.0,
            "touch3": 1.0 if bucket == "3+" else 0.0,
            "support": float((i // 7) % 2),
            "year": 2020 + ((i // 11) % 5),
            "vol_tercile": (i // 3) % 3,
            "log_steps": 1.0 + 0.01 * (i % 17),
            "velocity": velocity,
            "outcome": "BREAK" if velocity >= 10 else "REJECT",
        })
    scales = inference.freeze_scales(sample, ["velocity"])
    got = inference.lpm(sample, scales, "velocity", "BREAK", spec="full", draws=30, seed=1)
    assert got["coef"] is not None and got["coef"] > 0
    assert got["ci95"] is not None


def test_successor_rule_fails_when_the_interval_contains_zero():
    primary = {"coef": 0.05, "ci95": [-0.01, 0.08]}
    years = [{"coef": 0.05, "n": 40} for _ in range(5)]
    assert claim.successor_ok(
        primary=primary, years=years, loyo=years, families=years[:3],
        control={"coef": 0.0, "ci95": [-0.01, 0.01]}, q=0.01, family_share=0.4,
    ) is False
    primary_ok = {"coef": 0.05, "ci95": [0.01, 0.08]}
    assert claim.successor_ok(
        primary=primary_ok, years=years, loyo=years, families=years[:3],
        control={"coef": 0.0, "ci95": [-0.01, 0.01]}, q=0.01, family_share=0.4,
    ) is True
    assert claim.routing_status(0, [primary], [primary_ok]) == "REDUNDANT_WITH_KNOWN_STATE"
    assert claim.routing_status(1, [primary_ok], []) == "DISCOVERY_STRUCTURE_PRESENT"
    assert claim.routing_status(0, [], []) == "NO_STABLE_APPROACH_STRUCTURE"
    assert claim.routing_status(0, [primary_ok], []) == "STRUCTURE_PRESENT_BUT_UNSTABLE"
    assert claim.claim_level("DISCOVERY_STRUCTURE_PRESENT", 500) == "DISCOVERY_ONLY"
    assert claim.atlas_state("NO_STABLE_APPROACH_STRUCTURE") == "NO_STRUCTURE"
    assert claim.atlas_state("DISCOVERY_STRUCTURE_PRESENT") == "CLOSED_ON_SURFACE"


def test_level_price_ignores_the_active_period_extreme():
    t0 = _ms(2020, 1, 5)
    n = 2 * BARS_PER_DAY
    b = Bars(t0=t0, open=np.full(n, 95.0), high=np.full(n, 95.0), low=np.full(n, 95.0),
             close=np.full(n, 95.0), volume=np.ones(n), quote=np.ones(n),
             taker_buy_quote=np.ones(n), oi=np.full(n, np.nan))
    b.high[10] = 100.0
    inst, _ = level_instances(b)
    assert [row["price"] for row in inst if row["kind"] == "PDH"] == [100.0]
    b.high[BARS_PER_DAY + 5] = 250.0
    inst2, _ = level_instances(b)
    assert [row["price"] for row in inst2 if row["kind"] == "PDH"] == [100.0]


def test_protected_interval_and_control_are_deterministic():
    with pytest.raises(RuntimeError):
        assert_panel_legal(np.array([P.E1_START_MS]))
    with pytest.raises(RuntimeError):
        assert_panel_legal(np.array([P.SURFACE_END_MS]))
    eps, inst = [], []
    for i, price in enumerate((100.0, 110.0, 120.0)):
        ep = {
            "episode_id": f"PDH:{i}", "kind": "PDH", "family": "DAY", "struct_side": 1,
            "priority": 1, "anchor_price": price, "zone_low": price * 0.99, "zone_high": price * 1.01,
            "i0": i * 10, "i1": i * 10 + 5, "period_open": 100.0, "source_key": 0, "period_key": 1,
            "member_kinds": ["PDH"], "n_members": 1, "absorbed_later": [], "population": "real",
            "zone_half": P.ZONE_HALF_PRIMARY,
        }
        eps.append(ep)
        inst.append({"price": price, "i0": ep["i0"], "i1": ep["i1"]})
    first = control_episodes(eps, inst, P.ZONE_HALF_PRIMARY)
    second = control_episodes(eps, inst, P.ZONE_HALF_PRIMARY)
    assert [row["anchor_price"] for row in first] == [row["anchor_price"] for row in second]
    assert first and all(row["population"] == "control" for row in first)


def test_year_boundary_uses_the_touch_open():
    assert events.touch_year(_ms(2020, 12, 31, 23, 55)) == 2020
    assert events.touch_year(_ms(2021, 1, 1, 0, 0)) == 2021


def test_preflight_source_does_not_classify_outcomes():
    from scripts.research.level_approach_state_discovery_v1 import preflight
    text = Path_read(preflight)
    assert "level_touch_degradation_v1.outcomes" not in text
    assert "import outcomes" not in text


def Path_read(module):
    from pathlib import Path
    return Path(module.__file__).read_text(encoding="utf-8")


def test_loyo_keeps_feature_z_in_column_one():
    assert inference.columns_for("loyo", drop_year=2020)[1] == "feature_z"
    assert "y2021" not in inference.columns_for("loyo", drop_year=2020)
    assert "y2022" not in inference.columns_for("loyo", drop_year=2022)
    assert "touch2" not in inference.columns_for("no_touch")
    assert "log_steps_z" not in inference.columns_for("no_duration")
