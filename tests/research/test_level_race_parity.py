"""One detector (FORECAST_LAYER_DECISION_V1 §3): the product's structural first touch equals the
#352 constructor (scripts/research/level_touch_degradation_v1, `level_instances` → `build_episodes`
→ touch 1 of `scan_episode`).

A research-side parity test (tests/beta must not import scripts.research; test_beta_d7). Bars, levels and
touches only; no outcome is computed. The opt-in real-data test runs only when the #352 5m panel
is already in the DH1 cache and never fetches.
"""
import math
import os
from pathlib import Path

import numpy as np
import pytest

from beta import levels as LV
from beta.hist_series import BAR_MS, BARS_PER_DAY, Bars
from scripts.research.level_touch_degradation_v1 import constants as K
from scripts.research.level_touch_degradation_v1 import events as R

DAY_MS = 86_400_000
T0_2021 = 1609459200000                     # 2021-01-01T00:00Z
FIELDS = ("touch_open_ms", "side", "zone_low", "zone_high", "anchor_price", "member_kinds", "sigma", "x",
          "break_barrier", "reject_barrier")


def _bars(days=80, *, seed=7, gaps=(), t0=T0_2021, vol=0.0025):
    rng = np.random.default_rng(seed)
    n = days * BARS_PER_DAY
    c = 30000.0 * np.exp(np.cumsum(rng.normal(0, vol, n)))
    o = np.r_[30000.0, c[:-1]]
    wig = np.abs(rng.normal(0, vol / 2, n))
    hi = np.maximum(o, c) * (1 + wig)
    lo = np.minimum(o, c) * (1 - wig)
    cols = {k: v.copy() for k, v in (("open", o), ("high", hi), ("low", lo), ("close", c))}
    for a, z in gaps:
        for v in cols.values():
            v[a:z] = np.nan
    return Bars(t0=t0, volume=np.ones(n), quote=np.ones(n), taker_buy_quote=np.full(n, np.nan),
                oi=np.full(n, np.nan), **cols)


def _research(b: Bars, *, end_ms=None, sigma=None) -> dict:
    """#352 touch 1 keyed by the product event id (anchor kind : source key : active period open)."""
    sig = R.sigma_before_touch(b.close) if sigma is None else sigma
    inst, _drops = R.level_instances(b)
    eps, _info = R.build_episodes(inst, K.ZONE_HALF_PRIMARY)
    out = {}
    for t in R.scan_all(b, eps, sig, end_ms=end_ms or b.end_ms):
        if t["touch_number"] != 1:
            continue
        kind, sk, i0 = t["episode_id"].split(":")
        eid = f"{kind}:{sk}:{b.t0 + int(i0) * BAR_MS}"
        x = t["x_primary"]
        side = t["side"]
        brk = rej = None
        if x is not None and side in (1, -1):
            brk = t["zone_high"] * (1 + x) if side > 0 else t["zone_low"] * (1 - x)
            rej = t["zone_low"] * (1 - x) if side > 0 else t["zone_high"] * (1 + x)
        out[eid] = {"touch_open_ms": t["open_ms"], "side": side, "zone_low": t["zone_low"],
                    "zone_high": t["zone_high"], "anchor_price": t["anchor_price"],
                    "member_kinds": t["member_kinds"], "sigma": t["sigma"], "x": x, "break_barrier": brk,
                    "reject_barrier": rej, "eligible": not t["chain_stop"] and side in (1, -1)}
    return out


def _product(b: Bars, sigma=None) -> dict:
    return {e["event_id"]: e for e in LV.structural_first_touches(b, sigma=sigma, require_active_complete=True)}


FLOAT_FIELDS = ("sigma", "x", "break_barrier", "reject_barrier")
REL_TOL = 1e-9          # #352 takes the scale from running sums over its whole surface; the product
                        # from the 288 returns alone, so the two agree to rounding, not to the bit


def _same(a, b, f) -> bool:
    if f in FLOAT_FIELDS and a is not None and b is not None:
        return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=0.0)
    return a == b


def _assert_same(r: dict, p: dict) -> None:
    assert set(r) == set(p)
    for k in r:
        for f in FIELDS:
            assert _same(p[k][f], r[k][f], f), (k, f, p[k][f], r[k][f])
        if p[k]["ineligible_reason"] == "WINDOW_TOO_SHORT":     # the tape's first month: flagged, not kept
            assert p[k]["active_open_ms"] - p[k]["touch_open_ms"] <= 0 and not p[k]["eligible"]
            continue
        assert p[k]["eligible"] == r[k]["eligible"], k
        if p[k]["x"] is not None and p[k]["eligible"]:
            assert p[k]["p_up"] == p[k]["zone_high"] * (1 + p[k]["x"])
            assert p[k]["p_dn"] == p[k]["zone_low"] * (1 - p[k]["x"])
            assert {p[k]["p_up"], p[k]["p_dn"]} == {p[k]["break_barrier"], p[k]["reject_barrier"]}


def test_constants_are_the_352_design():
    assert LV.STRUCT_ZONE_HALF == K.ZONE_HALF_PRIMARY == K.MERGE_TOL
    assert LV.STRUCT_PRIORITY == K.PRIORITY and LV.STRUCT_SIDE == K.STRUCT_SIDE
    assert (LV.RACE_SIGMA_BARS, LV.RACE_SIGMA_MIN_PRESENT, LV.RACE_CORRIDOR_Z, LV.RACE_BARS,
            LV.RACE_BARRIER_FRACTION, LV.RACE_X_MIN, LV.RACE_X_MAX) == (
        K.SCALE_BARS, K.MIN_PRESENT, K.CORRIDOR_Z, K.HOLD_BARS_PRIMARY, K.BARRIER_FRACTION_PRIMARY,
        K.X_MIN, K.X_MAX)
    assert LV.race_x(0.0013) == K.x_from_sigma(0.0013)


def test_sigma_at_equals_research():
    b = _bars(days=10, gaps=((500, 520), (1700, 1702)))
    ref = R.sigma_before_touch(b.close)
    mine = np.array([LV.sigma_at(b.close, j) for j in range(b.n)])
    assert np.array_equal(np.isnan(mine), np.isnan(ref))
    ok = np.isfinite(ref)
    assert ok.sum() > 2000
    np.testing.assert_allclose(mine[ok], ref[ok], rtol=REL_TOL, atol=0)


@pytest.mark.parametrize("seed", [1, 7, 23])
def test_first_touches_equal_research_on_synthetic_bars(seed):
    b = _bars(days=80, seed=seed, gaps=((20 * BARS_PER_DAY + 30, 20 * BARS_PER_DAY + 60),))
    r, p = _research(b), _product(b)
    assert len(r) > 20
    _assert_same(r, p)


def test_unusable_sigma_makes_the_touch_ineligible_like_research():
    # the same scale array for both, unusable over days 34-43 (a hole in the 24h returns)
    b = _bars(days=50, seed=3)
    sig = np.array([LV.sigma_at(b.close, j) for j in range(b.n)])
    sig[34 * BARS_PER_DAY:44 * BARS_PER_DAY] = np.nan
    r, p = _research(b, sigma=sig), _product(b, sigma=sig)
    _assert_same(r, p)
    assert any(not e["eligible"] and e["ineligible_reason"] == "SIGMA_UNUSABLE" for e in p.values())


def test_confluence_and_absorption_equal_research():
    """Levels born together chain-merge; a level born later inside an active zone is absorbed."""
    base = [
        # month and week levels born together at i0=0, chained within 0.15 %
        {"kind": "PMH", "family": "MONTH", "struct_side": 1, "price": 100.0, "i0": 0, "i1": 999},
        {"kind": "PWH", "family": "WEEK", "struct_side": 1, "price": 100.12, "i0": 0, "i1": 499},
        {"kind": "PDH", "family": "DAY", "struct_side": 1, "price": 100.24, "i0": 0, "i1": 99},
        {"kind": "PDL", "family": "DAY", "struct_side": -1, "price": 95.0, "i0": 0, "i1": 99},
        # born later: one inside the month zone (absorbed), one near the anchor, one free
        {"kind": "PDH", "family": "DAY", "struct_side": 1, "price": 100.30, "i0": 100, "i1": 199},
        {"kind": "PDL", "family": "DAY", "struct_side": -1, "price": 99.9, "i0": 100, "i1": 199},
        {"kind": "PDH", "family": "DAY", "struct_side": 1, "price": 101.0, "i0": 200, "i1": 299},
    ]
    research_inst = [{**x, "source_key": k, "period_open": 1.0, "period_key": k + 1} for k, x in enumerate(base)]
    product_lv = [{**x, "source_key": k, "active_complete": True} for k, x in enumerate(base)]
    b = _bars(days=4)
    rep, _ = R.build_episodes(research_inst, K.ZONE_HALF_PRIMARY)
    pep = LV.structural_episodes(b, product_lv)
    assert [(e["kind"], e["member_kinds"], e["zone_low"], e["zone_high"], e["absorbed_later"]) for e in rep] == \
        [(e["kind"], e["member_kinds"], e["zone_low"], e["zone_high"], e["absorbed_later"]) for e in pep]
    pmh = next(e for e in pep if e["kind"] == "PMH")
    assert pmh["member_kinds"] == ["PMH", "PWH", "PDH"] and pmh["absorbed_later"] == ["PDH", "PDL"]


def test_causal_event_appears_at_t0_and_is_unchanged_at_t15():
    b = _bars(days=80, seed=11)
    full = _product(b)
    checked = 0
    for eid, e in full.items():
        j = e["j"]
        if j + 3 > b.n or e["touch_open_ms"] - b.t0 < 40 * DAY_MS:
            continue
        before = {x["event_id"] for x in LV.structural_first_touches(b.slice(0, j))}
        assert eid not in before
        for land in ("t0_ms", "t15_ms"):
            cut = (e[land] - b.t0) // BAR_MS
            seen = {x["event_id"]: x for x in LV.structural_first_touches(b.slice(0, cut))}
            assert all(seen[eid][f] == e[f] for f in FIELDS), (eid, land)
        assert e["t0_ms"] == e["touch_open_ms"] + BAR_MS
        assert e["t15_ms"] == e["touch_open_ms"] + 3 * BAR_MS
        assert e["window_end_ms"] == e["touch_open_ms"] + 49 * BAR_MS
        checked += 1
    assert checked > 10


def test_live_window_of_70_days_gives_the_same_event():
    """The live tape starts 70 days before midnight (beta.decision.LOOKBACK_DAYS)."""
    from beta.decision import LOOKBACK_DAYS
    b = _bars(days=120, seed=5)
    full = _product(b)
    checked = 0
    for eid, e in full.items():
        start = (e["t0_ms"] // DAY_MS - LOOKBACK_DAYS) * DAY_MS
        if start < b.t0:
            continue
        a, z = (start - b.t0) // BAR_MS, (e["t0_ms"] - b.t0) // BAR_MS
        seen = {x["event_id"]: x for x in LV.structural_first_touches(b.slice(a, z))}
        assert all(seen[eid][f] == e[f] for f in FIELDS), eid      # bit-identical: the digest is stable
        assert seen[eid]["ineligible_reason"] != "WINDOW_TOO_SHORT" and seen[eid]["eligible"] == e["eligible"]
        checked += 1
    assert checked > 10


def _cached_panel():
    root = Path(os.environ.get("DH1_CACHE", "/tmp/dh1_cache"))
    found = sorted(root.glob("core_btc_5m_*.npz")) if root.exists() else []
    return found[0] if found else None


@pytest.mark.skipif(_cached_panel() is None, reason="#352 5m panel not in the DH1 cache (opt-in; never fetched)")
def test_history_2020_2024_equals_352():
    """Whole discovery surface: the same 1952 touch-1 events (1919 from 2020-02-01), every field equal.
    The one product-only event is a level whose active period ended incomplete (#352 drops it; a live
    caller cannot know that before the period ends); with that drop applied the two are the same."""
    from scripts.research.dh1.data import to_bars
    from scripts.research.level_touch_degradation_v1.data import assert_panel_legal
    panel = dict(np.load(_cached_panel()))
    assert_panel_legal(panel["open_ms"])
    b = to_bars(panel, K.DATA_START_MS, K.SURFACE_END_MS)
    r = _research(b, end_ms=K.SURFACE_END_MS)
    p_all = {e["event_id"]: e for e in LV.structural_first_touches(b)}
    p = _product(b)
    assert len(r) == 1952
    assert sum(1 for x in r.values() if x["touch_open_ms"] >= K.EVENT_START_MS) == 1919
    assert set(p_all) - set(p) == {k for k, e in p_all.items() if not e["active_complete"]} and len(p_all) - len(p) == 1
    _assert_same(r, p)
    flagged = [e for e in p.values() if e["ineligible_reason"] == "WINDOW_TOO_SHORT"]
    # only episodes born in the tape's first 32 days (2020-01-01 .. 2020-02-01), never a later one
    assert flagged and all(e["active_open_ms"] - b.t0 < LV.ABSORPTION_LOOKBACK_MS for e in flagged)


def test_an_episode_born_in_the_tapes_first_month_is_flagged_not_kept():
    b = _bars(days=80, seed=7)
    evs = LV.structural_first_touches(b)
    short = [e for e in evs if e["ineligible_reason"] == "WINDOW_TOO_SHORT"]
    assert short and all(e["active_open_ms"] - b.t0 < LV.ABSORPTION_LOOKBACK_MS and not e["eligible"] for e in short)
    assert all(e["active_open_ms"] - b.t0 >= LV.ABSORPTION_LOOKBACK_MS for e in evs if e not in short)
