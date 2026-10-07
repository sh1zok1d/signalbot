"""LEVEL_TOUCH_DEGRADATION_V1 semantics on a hand-built fixture. No market panel is read."""

from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from beta.hist_series import BARS_PER_DAY, Bars

from scripts.research.level_touch_degradation_v1 import claim, constants as K, control, events, inference, outcomes, preflight
from scripts.research.level_touch_degradation_v1.events import build_episodes, level_instances

REPO = Path(__file__).resolve().parents[2]
MOD = REPO / "scripts" / "research" / "level_touch_degradation_v1"


def _ms(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _bars(t0: int, n: int, price: float = 100.0) -> Bars:
    c = np.full(n, price, dtype=float)
    return Bars(t0=t0, open=c.copy(), high=c.copy(), low=c.copy(), close=c.copy(),
                volume=np.ones(n), quote=np.ones(n), taker_buy_quote=np.ones(n), oi=np.full(n, np.nan))


def _x_sigma(x: float = 0.01) -> float:
    return x / (K.BARRIER_FRACTION_PRIMARY * K.CORRIDOR_Z * K.HOLD_BARS_PRIMARY ** 0.5)


def _episode(i0, i1, price=100.0, kind="PDH", family="DAY"):
    w = K.ZONE_HALF_PRIMARY
    return {
        "episode_id": f"{kind}:0:{i0}", "kind": kind, "family": family, "struct_side": 1 if kind.endswith("H") else -1,
        "priority": K.PRIORITY[kind], "anchor_price": price, "zone_low": price * (1 - w), "zone_high": price * (1 + w),
        "i0": i0, "i1": i1, "period_open": price * 0.95, "source_key": 0, "period_key": 1,
        "member_kinds": [kind], "n_members": 1, "absorbed_later": [], "population": "real", "zone_half": w,
    }


def test_level_uses_only_the_completed_source_period():
    t0 = _ms(2020, 1, 5)  # Sunday
    b = _bars(t0, 2 * BARS_PER_DAY, 95.0)
    b.high[10] = 100.0
    b.low[20] = 90.0
    inst, _ = level_instances(b)
    pdh = [r for r in inst if r["kind"] == "PDH"]
    assert len(pdh) == 1
    assert pdh[0]["price"] == 100.0
    assert pdh[0]["i0"] == BARS_PER_DAY
    b.high[BARS_PER_DAY + 5] = 250.0  # future high of the active day
    inst2, _ = level_instances(b)
    assert [r["price"] for r in inst2 if r["kind"] == "PDH"] == [100.0]
    b.high[10] = 150.0
    inst3, _ = level_instances(b)
    assert [r["price"] for r in inst3 if r["kind"] == "PDH"] == [150.0]
    episodes, _ = build_episodes(inst3, K.ZONE_HALF_PRIMARY)
    touches = events.scan_all(b, episodes, np.full(b.n, _x_sigma()))
    assert touches
    assert all(t["j"] >= BARS_PER_DAY for t in touches if t["kind"] == "PDH")


def test_zone_clusters_nearby_levels_and_keeps_distant_ones():
    common = dict(i0=0, i1=100, period_open=100.0, source_key=1, period_key=2, struct_side=1, family="MONTH")
    near = [
        {**common, "kind": "PMH", "family": "MONTH", "price": 100.0, "struct_side": 1},
        {**common, "kind": "PDH", "family": "DAY", "price": 100.10, "struct_side": 1, "i1": 10},
    ]
    # 100.10 / 100 - 1 = 0.10% < 0.15%, so one zone, anchored by the month high.
    episodes, info = build_episodes(near, K.ZONE_HALF_PRIMARY)
    assert len(episodes) == 1 and episodes[0]["kind"] == "PMH" and episodes[0]["n_members"] == 2
    assert info["absorbed_at_birth"] == 1
    assert episodes[0]["zone_low"] <= 100.0 and episodes[0]["zone_high"] >= 100.10
    far = [
        {**common, "kind": "PMH", "price": 100.0},
        {**common, "kind": "PDH", "family": "DAY", "price": 102.0, "i1": 10},
    ]
    episodes, _ = build_episodes(far, K.ZONE_HALF_PRIMARY)
    assert len(episodes) == 2


def test_a_later_level_inside_an_active_zone_does_not_open_a_second_counter():
    rows = [
        {"kind": "PMH", "family": "MONTH", "struct_side": 1, "price": 100.0, "i0": 0, "i1": 200,
         "period_open": 95.0, "source_key": 1, "period_key": 2},
        {"kind": "PDH", "family": "DAY", "struct_side": 1, "price": 100.05, "i0": 50, "i1": 80,
         "period_open": 99.0, "source_key": 3, "period_key": 4},
    ]
    episodes, info = build_episodes(rows, K.ZONE_HALF_PRIMARY)
    assert len(episodes) == 1
    assert info["absorbed_later"] == 1
    assert episodes[0]["absorbed_later"] == ["PDH"]
    assert episodes[0]["zone_low"] == pytest.approx(100.0 * (1 - K.ZONE_HALF_PRIMARY))


def test_distinct_touches_refractory_and_numbering():
    """Five bars inside the zone are one touch. Touch 2 starts only after a clearance of X.
    Touch 4 is bucket 3+. The story: touch 1 rejects, touch 2 breaks."""
    n = 40
    t0 = _ms(2020, 6, 2)
    b = _bars(t0, n, 95.0)
    ep = _episode(0, n - 1, 100.0)
    zlo, zhi = ep["zone_low"], ep["zone_high"]
    x = 0.01
    # Touch 1 at bar 2.
    b.high[2], b.low[2], b.close[2] = 100.05, 99.90, 100.0
    for j in range(3, 8):  # still inside or not yet X away: must not count
        b.high[j], b.low[j], b.close[j] = zhi - 0.01, zlo + 0.01, 100.0
    # Leave the zone but not by X.
    b.high[8], b.low[8], b.close[8] = zlo - 0.01, zlo - 0.05, zlo - 0.02
    # Clearance beyond X, then touch 2.
    clear = zlo * (1 - x) - 0.05
    b.high[9], b.low[9], b.close[9] = clear, clear - 0.2, clear - 0.1
    b.high[11], b.low[11], b.close[11] = 100.05, 99.90, 100.0
    # Clear again and two more touches so the fourth is bucket 3+.
    b.high[12], b.low[12], b.close[12] = clear, clear - 0.2, clear
    b.high[14], b.low[14], b.close[14] = 100.05, 99.90, 100.0
    b.high[15], b.low[15], b.close[15] = clear, clear - 0.2, clear
    b.high[17], b.low[17], b.close[17] = 100.05, 99.90, 100.0
    sigma = np.full(n, _x_sigma(x))
    touches = events.scan_episode(b.high, b.low, b.close, b.open, sigma, t0, ep, end_ms=t0 + n * K.BAR_MS + K.DAY_MS)
    numbers = [t["touch_number"] for t in touches]
    assert numbers == [1, 2, 3, 4]
    assert [t["j"] for t in touches] == [2, 11, 14, 17]
    assert [t["bucket"] for t in touches] == ["1", "2", "3+", "3+"]
    assert all(t["side"] == 1 for t in touches)  # approach from below


def test_fixture_touch1_rejects_and_touch2_breaks():
    """Hand story: the level is 100, touch 1 rejects, price clears, touch 2 breaks."""
    n = 16
    b = _bars(_ms(2020, 6, 4), n, 95.0)
    ep = _episode(0, n - 1, 100.0)
    zlo, zhi = ep["zone_low"], ep["zone_high"]
    x = 0.01
    b.high[2], b.low[2], b.close[2] = 100.05, 99.95, 100.0          # touch 1
    b.high[3], b.low[3] = zlo - 0.02, zlo * (1 - x) - 0.05           # reject, not yet a full clearance
    b.high[4], b.low[4], b.close[4] = zlo * (1 - x) - 0.1, zlo * (1 - x) - 0.3, zlo * (1 - x) - 0.2
    b.high[6], b.low[6], b.close[6] = 100.05, 99.95, 100.0           # touch 2
    b.high[7], b.low[7] = zhi * (1 + x) + 0.2, zlo + 0.02            # break, low stays above the reject
    sigma = np.full(n, _x_sigma(x))
    touches = events.scan_episode(b.high, b.low, b.close, b.open, sigma, b.t0, ep,
                                  end_ms=b.t0 + (n + K.HOLD_BARS_PRIMARY) * K.BAR_MS)
    assert [t["j"] for t in touches] == [2, 6]
    assert outcomes.classify(b.high, b.low, 2, 1, zlo, zhi, x, horizon=4) == "REJECT"
    assert outcomes.classify(b.high, b.low, 6, 1, zlo, zhi, x, horizon=4) == "BREAK"


def test_support_orientation_and_downward_break():
    n = 20
    b = _bars(_ms(2020, 6, 3), n, 105.0)
    ep = _episode(0, n - 1, 100.0, kind="PDL")
    zlo, zhi = ep["zone_low"], ep["zone_high"]
    x = 0.01
    b.high[2], b.low[2], b.close[2] = zhi + 0.2, zlo + 0.01, 100.0  # enter from above
    b.low[3] = zlo * (1 - x) - 0.1
    b.high[3] = zlo - 0.01
    sigma = np.full(n, _x_sigma(x))
    touches = events.scan_episode(b.high, b.low, b.close, b.open, sigma, b.t0, ep, end_ms=b.t0 + n * K.BAR_MS + K.DAY_MS)
    assert touches[0]["side"] == -1
    assert outcomes.classify(b.high, b.low, touches[0]["j"], -1, zlo, zhi, x, 4) == "BREAK"


def test_ambiguous_same_bar_is_not_assigned():
    high = np.full(10, 100.0)
    low = np.full(10, 100.0)
    zlo, zhi, x = 99.85, 100.15, 0.01
    high[2] = zhi * (1 + x) + 1
    low[2] = zlo * (1 - x) - 1
    assert outcomes.classify(high, low, 1, 1, zlo, zhi, x, horizon=4) == "AMBIGUOUS"


def test_horizon_cutoff_is_exact_and_missing_bars_drop_the_window():
    horizon = K.HOLD_BARS_PRIMARY
    n = horizon + 5
    high = np.full(n, 100.0)
    low = np.full(n, 100.0)
    zlo, zhi, x = 99.85, 100.15, 0.01
    # Last included bar is j+horizon. A break only on the next bar is NEITHER.
    j = 1
    high[j + horizon] = zhi * (1 + x) + 1
    assert outcomes.classify(high, low, j, 1, zlo, zhi, x, horizon) == "BREAK"
    high[j + horizon] = 100.0
    high[j + horizon + 1] = zhi * (1 + x) + 1
    assert outcomes.classify(high, low, j, 1, zlo, zhi, x, horizon) == "NEITHER"
    high[j + 2] = zhi * (1 + x) + 1
    for k in range(4):
        high[j + 3 + k] = np.nan
        low[j + 3 + k] = np.nan
    # 4 / 48 missing stays at or above the 90% floor (44/48).
    assert outcomes.classify(high, low, j, 1, zlo, zhi, x, horizon) == "BREAK"
    for k in range(6):
        high[j + 1 + k] = np.nan
        low[j + 1 + k] = np.nan
    assert outcomes.classify(high, low, j, 1, zlo, zhi, x, horizon) is None


def test_sigma_excludes_the_touch_bar_and_week_month_year_boundaries():
    t0 = _ms(2020, 1, 6)  # Monday
    n = 3 * 7 * BARS_PER_DAY
    b = _bars(t0, n, 100.0)
    b.close[K.SCALE_BARS + 5] = 130.0  # a return that ends at this bar
    sig = events.sigma_before_touch(b.close)
    from scripts.research.dh1.events import rolling_sigma
    full = rolling_sigma(b.close)
    j = K.SCALE_BARS + 5
    assert sig[j] == pytest.approx(full[j - 1])
    assert sig[j] != pytest.approx(full[j])
    sunday = _ms(2020, 1, 12, 23, 55)
    monday = _ms(2020, 1, 13, 0, 0)
    assert events.touch_week(sunday) + 1 == events.touch_week(monday)
    assert events.touch_year(_ms(2020, 12, 31, 23, 55)) == 2020
    assert events.touch_year(_ms(2021, 1, 1, 0, 0)) == 2021
    # Three Monday-start weeks: the first week level is active only on the second week.
    b.high[BARS_PER_DAY] = 140.0  # Tuesday of week 1
    inst, _ = level_instances(b)
    weeks = [r for r in inst if r["kind"] == "PWH"]
    assert weeks
    assert all(r["i0"] >= 7 * BARS_PER_DAY for r in weeks)
    assert weeks[0]["price"] == 140.0
    # Month: January's high is February's PMH, and a February high does not leak backward.
    t1 = _ms(2020, 1, 1)
    n_m = (31 + 29) * BARS_PER_DAY  # 2020 is a leap year
    bm = _bars(t1, n_m, 100.0)
    bm.high[10] = 180.0
    bm.high[31 * BARS_PER_DAY + 10] = 220.0
    inst_m, _ = level_instances(bm)
    pmh = [r for r in inst_m if r["kind"] == "PMH"]
    assert len(pmh) == 1
    assert pmh[0]["price"] == 180.0
    assert pmh[0]["i0"] == 31 * BARS_PER_DAY


def test_protected_surface_and_preflight_module_is_outcome_blind():
    legal = np.array([K.DATA_START_MS, K.SURFACE_END_MS - K.BAR_MS], dtype=np.int64)
    from scripts.research.level_touch_degradation_v1.data import assert_panel_legal
    assert_panel_legal(legal)
    with pytest.raises(RuntimeError):
        assert_panel_legal(np.array([K.SURFACE_END_MS], dtype=np.int64))
    with pytest.raises(RuntimeError):
        assert_panel_legal(np.array([K.E1_START_MS], dtype=np.int64))
    src = (MOD / "preflight.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
    assert not any("outcomes" in name for name in imported)
    for banned in ("funding", "liquidation", "bybit", "okx", "2026-08"):
        assert banned not in src
    data_src = (MOD / "data.py").read_text(encoding="utf-8")
    for banned in ("funding", "liquidation", "bybit", "okx"):
        assert banned not in data_src


def test_control_is_deterministic_and_skips_real_levels():
    def ep(i, price, kind="PDH"):
        row = _episode(i * 10, i * 10 + 5, price, kind=kind)
        row["episode_id"] = f"{kind}:{i}"
        row["period_open"] = 100.0
        return row
    episodes = [ep(0, 110.0), ep(1, 120.0), ep(2, 130.0), ep(3, 140.0)]
    instances = [{"price": e["anchor_price"], "i0": e["i0"], "i1": e["i1"]} for e in episodes]
    a = control.control_episodes(episodes, instances, K.ZONE_HALF_PRIMARY)
    b = control.control_episodes(episodes, instances, K.ZONE_HALF_PRIMARY)
    assert [r["anchor_price"] for r in a] == [r["anchor_price"] for r in b]
    assert a
    for row in a:
        for inst in instances:
            if not (row["i0"] <= inst["i1"] and inst["i0"] <= row["i1"]):
                continue
            gap = abs(row["anchor_price"] - inst["price"]) / min(row["anchor_price"], inst["price"])
            assert gap > K.ZONE_HALF_PRIMARY


def test_standardization_matches_a_hand_computed_difference():
    rows = []
    # Two strata (approach side), equal touch-1 weight. Touch2: 0.8 and 0.4. Touch1: 0.5 and 0.2.
    plan = [
        (1, "1", 20, 10),
        (1, "2", 20, 16),
        (1, "3+", 20, 4),
        (-1, "1", 20, 4),
        (-1, "2", 20, 8),
        (-1, "3+", 20, 4),
    ]
    k = 0
    for side, bucket, n, breaks in plan:
        number = {"1": 1, "2": 2, "3+": 3}[bucket]
        for i in range(n):
            rows.append({
                "outcome": "BREAK" if i < breaks else "REJECT",
                "sigma": 0.01, "family": "DAY", "side": side, "bucket": bucket,
                "week": k, "year": 2020, "touch_number": number, "feature_eligible": True,
            })
            k += 1
    edges = inference.tercile_edges(np.full(len(rows), 0.01))
    got = inference.contrasts(rows, edges, standardized=True, draws=300, seed=7)
    assert got["d2"] == pytest.approx(0.25)
    assert got["d3"] == pytest.approx(-0.15)
    assert got["ci2"][0] < got["d2"] < got["ci2"][1]


def test_integration_rule_is_fixed_and_preflight_rejects_an_outcome():
    years = {y: (40, 40) for y in K.YEARS}
    year_d = {y: 0.04 for y in K.YEARS}
    yes = claim.integration_candidate(
        d2=0.02, d3=0.04, ci3=(0.01, 0.07), control_d3=0.005, control_ci3=(-0.01, 0.02),
        year_d3=year_d, year_n=years, max_year_share=0.3, max_family_share_touch3=0.5, weeks=120)
    assert yes["candidate"] is True
    no = claim.integration_candidate(
        d2=0.001, d3=0.001, ci3=(-0.02, 0.02), control_d3=0.0, control_ci3=(-0.01, 0.01),
        year_d3={y: 0.001 for y in K.YEARS}, year_n=years, max_year_share=0.3,
        max_family_share_touch3=0.5, weeks=120)
    assert no["candidate"] is False
    assert claim.both_near_zero(0.001, (-0.02, 0.02), 0.001, (-0.01, 0.01))
    bad = [{"bucket": "1", "feature_eligible": False, "outcome": "BREAK", "window_ok_48": True,
            "window_ok_12": True, "chain_stop": False, "year": 2020, "family": "DAY", "side": 1, "week": 1}]
    with pytest.raises(RuntimeError):
        preflight._tallies(bad)
