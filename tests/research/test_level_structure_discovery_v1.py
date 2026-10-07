"""LEVEL_STRUCTURE_DISCOVERY_V1 structural features. No market panel is read.

Expected feature values come from the frozen formulas. No break, reject or neither
rate on the discovery surface is computed here.
"""

from __future__ import annotations

import datetime as dt
import math
from pathlib import Path

import numpy as np
import pytest

from beta.hist_series import BARS_PER_DAY, Bars

from scripts.research.level_structure_discovery_v1 import claim, constants as K, inference, redundancy
from scripts.research.level_structure_discovery_v1.features import touch_features
from scripts.research.level_structure_discovery_v1.formation import formation_of, period_catalog
from scripts.research.level_structure_discovery_v1.membership import members_as_of, replay
from scripts.research.level_structure_discovery_v1.preflight import _parity
from scripts.research.level_structure_discovery_v1.rows import (
    _base, complete, control_rows, real_rows, restrict_matched, vol_tercile,
)
from scripts.research.level_touch_degradation_v1 import constants as P
from scripts.research.level_touch_degradation_v1 import events, outcomes
from scripts.research.level_touch_degradation_v1.data import assert_panel_legal
from scripts.research.level_touch_degradation_v1.events import build_episodes, level_instances


def _ms(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _bars(high, low, close, quote, *, t0=None, open_=None):
    n = int(close.shape[0])
    return Bars(
        t0=_ms(2020, 1, 1) if t0 is None else t0,
        open=np.full(n, 100.0) if open_ is None else open_,
        high=np.asarray(high, dtype=float),
        low=np.asarray(low, dtype=float),
        close=np.asarray(close, dtype=float),
        volume=np.ones(n),
        quote=np.asarray(quote, dtype=float),
        taker_buy_quote=np.full(n, -999.0),
        oi=np.full(n, np.nan),
    )


def _day_arrays(ranges, *, quote=10.0, n_extra=0):
    """One full UTC day per range. `ranges` is (high-low)/open with open fixed at 100."""
    n_days = len(ranges) + n_extra
    n = n_days * BARS_PER_DAY
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close = np.full(n, 100.0)
    q = np.full(n, float(quote))
    for d, rel in enumerate(ranges):
        half = 100.0 * float(rel) / 2.0
        sl = slice(d * BARS_PER_DAY, (d + 1) * BARS_PER_DAY)
        high[sl] = 100.0 + half
        low[sl] = 100.0 - half
    return high, low, close, q


def _inst(kind, price, i0, i1, source_key):
    return {
        "kind": kind,
        "family": P.FAMILY_OF[kind],
        "struct_side": P.STRUCT_SIDE[kind],
        "price": float(price),
        "i0": int(i0),
        "i1": int(i1),
        "period_open": 100.0,
        "source_key": int(source_key),
        "period_key": int(source_key) + 1,
    }


def _birth(**overrides):
    base = {
        "formation_range": 0.0,
        "formation_volume": 0.0,
        "close_off_extreme": 0.0,
        "extreme_timing": 0.0,
        "extreme_density": 0.0,
    }
    base.update(overrides)
    return base


def _ledger(members, *, i0=0, i1=288, anchor="PDH", family="DAY", side=1, source_key=10, price=100.0):
    return {
        "episode_id": f"{anchor}:{source_key}:{i0}",
        "i0": i0,
        "i1": i1,
        "anchor_kind": anchor,
        "anchor_family": family,
        "anchor_side": side,
        "anchor_price": price,
        "source_key": source_key,
        "members": members,
        "absorbed_kinds": [],
    }


def _member(kind, price, available, *, family=None, source_key=1, side=None, birth=True):
    return {
        "kind": kind,
        "family": family or P.FAMILY_OF[kind],
        "price": float(price),
        "available_i0": int(available),
        "source_key": int(source_key),
        "struct_side": P.STRUCT_SIDE[kind] if side is None else int(side),
        "birth": birth,
    }


def test_level_birth_uses_the_previous_period_and_ignores_the_active_extreme():
    n = 2 * BARS_PER_DAY
    high = np.full(n, 95.0)
    low = np.full(n, 95.0)
    high[10] = 100.0
    low[20] = 90.0
    bars = _bars(high, low, np.full(n, 95.0), np.ones(n))
    inst, _ = level_instances(bars)
    pdh = [row for row in inst if row["kind"] == "PDH"]
    pdl = [row for row in inst if row["kind"] == "PDL"]
    assert [row["price"] for row in pdh] == [100.0]
    assert [row["price"] for row in pdl] == [90.0]
    assert pdh[0]["i0"] == BARS_PER_DAY
    assert pdh[0]["i1"] == 2 * BARS_PER_DAY - 1
    assert pdh[0]["i1"] - pdh[0]["i0"] + 1 == BARS_PER_DAY
    high[BARS_PER_DAY + 5] = 250.0
    low[BARS_PER_DAY + 6] = 10.0
    inst2, _ = level_instances(bars)
    assert [row["price"] for row in inst2 if row["kind"] == "PDH"] == [100.0]
    assert [row["price"] for row in inst2 if row["kind"] == "PDL"] == [90.0]


def test_replay_matches_parent_birth_and_hides_a_future_member():
    instances = [
        _inst("PDH", 100.0, 0, 400, 1),
        _inst("PWH", 100.10, 0, 400, 1),
        _inst("PMH", 100.05, 0, 400, 1),
        _inst("PDH", 100.02, 100, 400, 2),
    ]
    episodes, _ = build_episodes(instances, P.ZONE_HALF_PRIMARY)
    ledgers = replay(instances, P.ZONE_HALF_PRIMARY)
    _parity(episodes, ledgers)
    assert len(episodes) == 1
    ledger = next(iter(ledgers.values()))
    assert {m["family"] for m in ledger["members"] if m["birth"]} == {"DAY", "WEEK", "MONTH"}
    assert len(members_as_of(ledger, 0)) == 3
    assert len(members_as_of(ledger, 99)) == 3
    later = members_as_of(ledger, 100)
    assert len(later) == 4
    assert sum(1 for m in later if m["kind"] == "PDH") == 2
    assert all(m["available_i0"] <= 100 for m in later)


def test_age_confluence_diversity_and_span_are_known_before_the_touch_bar():
    members = [
        _member("PDH", 100.0, 0, source_key=1),
        _member("PWH", 100.10, 0, source_key=1),
        _member("PMH", 100.05, 0, source_key=1),
        _member("PDL", 100.04, 80, source_key=2, birth=False),
    ]
    ledger = _ledger(members, i0=0, i1=200)
    early = touch_features(ledger, _birth(), j=40, x=0.01)
    assert early["age"] == pytest.approx(40 / 200)
    assert early["confluence"] == 3
    assert early["diversity"] == 3
    assert early["zone_span"] == pytest.approx((100.10 - 100.0) / 100.0 / 0.01)
    late = touch_features(ledger, _birth(), j=80, x=0.01)
    assert late["confluence"] == 4
    assert late["diversity"] == 3
    assert touch_features(ledger, _birth(), j=-1, x=0.01) is None
    assert touch_features(ledger, _birth(), j=201, x=0.01) is None
    single = _ledger([_member("PDH", 100.0, 0)], i0=0, i1=100)
    alone = touch_features(single, _birth(), j=0, x=0.01)
    assert alone["age"] == 0.0
    assert alone["confluence"] == 1
    assert alone["diversity"] == 1
    assert alone["zone_span"] == 0.0
    assert touch_features(single, _birth(), j=100, x=0.01)["age"] == 1.0


def test_zone_span_needs_a_usable_scale_and_singleton_stays_zero():
    pair = _ledger([
        _member("PDH", 100.0, 0),
        _member("PWH", 101.0, 0),
    ], i0=0, i1=10)
    assert math.isnan(touch_features(pair, _birth(), j=1, x=None)["zone_span"])
    assert math.isnan(touch_features(pair, _birth(), j=1, x=0.0)["zone_span"])


def _formation(ranges, *, side=1, mutate=None, source_at=-1):
    high, low, close, quote = _day_arrays(ranges)
    if mutate is not None:
        mutate(high, low, close, quote)
    bars = _bars(high, low, close, quote)
    catalog = period_catalog(bars)
    source = catalog["DAY"][source_at if source_at >= 0 else len(ranges) - 1]
    got = formation_of(catalog, bars, family="DAY", source_key=source["key"], side=side)
    return got, source, bars, catalog


def test_formation_range_and_volume_use_only_prior_same_family_periods():
    ranges = [0.50] * 10 + [0.01] * 8 + [0.08] * 12 + [0.08]
    got, source, bars, catalog = _formation(ranges, side=1)
    assert source["full"]
    assert got["formation_range"] == pytest.approx(0.0)
    priors = [row["range_rel"] for row in catalog["DAY"] if row["key"] < source["key"] and row["full"]]
    assert abs(float(np.median(priors[-20:])) - 0.08) < 1e-12
    assert abs(float(np.median(priors[:20])) - float(np.median(priors[-20:]))) > 0.01
    high, low, close, quote = _day_arrays([0.01, 0.02, 0.03, 0.04, 0.10], quote=10.0)
    sl = slice(4 * BARS_PER_DAY, 5 * BARS_PER_DAY)
    quote[sl] = 40.0
    bars = _bars(high, low, close, quote)
    catalog = period_catalog(bars)
    source = catalog["DAY"][4]
    got = formation_of(catalog, bars, family="DAY", source_key=source["key"], side=1)
    assert got["formation_range"] == pytest.approx(math.log(0.10 / 0.025))
    assert got["formation_volume"] == pytest.approx(math.log(4.0))
    poisoned = _bars(high, low, close, quote)
    poisoned.taker_buy_quote[:] = 1e9
    again = formation_of(period_catalog(poisoned), poisoned, family="DAY", source_key=source["key"], side=1)
    assert again["formation_volume"] == got["formation_volume"]
    quote[sl][:40] = np.nan
    thin = _bars(high, low, close, quote)
    missing_volume = formation_of(period_catalog(thin), thin, family="DAY", source_key=source["key"], side=1)
    assert math.isnan(missing_volume["formation_volume"])
    assert missing_volume["formation_range"] == pytest.approx(got["formation_range"])


def test_close_off_extreme_is_oriented_and_the_active_period_does_not_enter():
    def near_high(high, low, close, quote):
        sl = slice(4 * BARS_PER_DAY, 5 * BARS_PER_DAY)
        high[sl] = 110.0
        low[sl] = 100.0
        close[sl] = 109.5

    got, source, bars, _ = _formation([0.02] * 6, mutate=near_high, source_at=4)
    assert got["close_off_extreme"] == pytest.approx(0.05)
    bars.high[int(source["last"]) + 1] = 500.0
    bars.close[int(source["last"]) + 1] = 1.0
    again = formation_of(period_catalog(bars), bars, family="DAY", source_key=source["key"], side=1)
    assert again["close_off_extreme"] == pytest.approx(0.05)

    def far_low(high, low, close, quote):
        sl = slice(4 * BARS_PER_DAY, 5 * BARS_PER_DAY)
        high[sl] = 110.0
        low[sl] = 100.0
        close[sl] = 109.0

    far, _, _, _ = _formation([0.02] * 5, side=-1, mutate=far_low)
    assert far["close_off_extreme"] == pytest.approx(0.9)

    def near_low(high, low, close, quote):
        sl = slice(4 * BARS_PER_DAY, 5 * BARS_PER_DAY)
        high[sl] = 110.0
        low[sl] = 100.0
        close[sl] = 100.5

    near, _, _, _ = _formation([0.02] * 5, side=-1, mutate=near_low)
    assert near["close_off_extreme"] == pytest.approx(0.05)


def test_extreme_timing_and_density_use_the_frozen_tolerance():
    def paint(high, low, close, quote, indexes):
        sl = slice(4 * BARS_PER_DAY, 5 * BARS_PER_DAY)
        high[sl] = 101.0
        low[sl] = 99.0
        for idx in indexes:
            high[4 * BARS_PER_DAY + idx] = 110.0

    early, _, _, _ = _formation([0.02] * 5, mutate=lambda *a: paint(*a, [0]))
    assert early["extreme_timing"] == pytest.approx(0.0)
    assert early["extreme_density"] == pytest.approx(1.0 / BARS_PER_DAY)

    late, _, _, _ = _formation([0.02] * 5, mutate=lambda *a: paint(*a, [BARS_PER_DAY - 1]))
    assert late["extreme_timing"] == pytest.approx(1.0)
    assert late["extreme_density"] == pytest.approx(1.0 / BARS_PER_DAY)

    dense_idx = list(range(10, 70))
    dense, _, _, _ = _formation([0.02] * 5, mutate=lambda *a: paint(*a, dense_idx))
    assert dense["extreme_timing"] == pytest.approx(69 / (BARS_PER_DAY - 1))
    assert dense["extreme_density"] == pytest.approx(60 / BARS_PER_DAY)

    def outside(high, low, close, quote):
        paint(high, low, close, quote, [BARS_PER_DAY - 1])
        high[4 * BARS_PER_DAY + 3] = 110.0 * (1.0 - K.EXTREME_TOL) - 1e-6

    isolated, _, _, _ = _formation([0.02] * 5, mutate=outside)
    assert isolated["extreme_density"] == pytest.approx(1.0 / BARS_PER_DAY)
    assert K.EXTREME_TOL == 0.0005
    assert K.EXTREME_TOL != P.ZONE_HALF_PRIMARY


def test_missing_and_incomplete_source_periods_are_undefined():
    high, low, close, quote = _day_arrays([0.02] * 6)
    close[10:40] = np.nan
    bars = _bars(high, low, close, quote)
    catalog = period_catalog(bars)
    incomplete = catalog["DAY"][0]
    assert incomplete["full"] is False
    missing = formation_of(catalog, bars, family="DAY", source_key=incomplete["key"], side=1)
    assert all(math.isnan(missing[name]) for name in (
        "formation_range", "formation_volume", "close_off_extreme", "extreme_timing", "extreme_density"))
    assert all(math.isnan(v) for v in formation_of(
        catalog, bars, family="DAY", source_key=10**9, side=1).values())
    short = _bars(*_day_arrays([0.02] * 3))
    short_catalog = period_catalog(short)
    too_few = formation_of(
        short_catalog, short, family="DAY", source_key=short_catalog["DAY"][-1]["key"], side=1)
    assert math.isnan(too_few["formation_range"])
    assert math.isnan(too_few["formation_volume"])


def test_touch_ordinal_side_and_parent_volatility_terciles():
    touch = {
        "feature_eligible": True, "sigma": K.PARENT_SIGMA_LO, "x_primary": 0.01,
        "bucket": "3+", "side": -1, "year": 2024, "j": 12, "i0": 0,
        "zone_low": 99.0, "zone_high": 101.0, "episode_id": "E", "family": "DAY",
    }
    row = _base(touch, match_id="E", real=True)
    assert row["touch3"] == 1.0 and row["touch2"] == 0.0
    assert row["support"] == 1.0
    assert row["vol_tercile"] == 0
    touch["side"] = 1
    touch["bucket"] = "2"
    touch["sigma"] = K.PARENT_SIGMA_HI + 1e-6
    above = _base(touch, match_id="E", real=False)
    assert above["support"] == 0.0
    assert above["touch2"] == 1.0
    assert above["vol_tercile"] == 2
    assert above["real"] == 0.0
    assert vol_tercile(None) is None
    assert _base({**touch, "feature_eligible": False}, match_id="E", real=True) is None


def test_exact_four_hour_outcome_ignores_the_touch_bar():
    n = 80
    high = np.full(n, 100.0)
    low = np.full(n, 100.0)
    high[0] = 1_000.0
    assert outcomes.classify(high, low, 0, 1, 99.0, 101.0, 0.01, 48) == "NEITHER"
    high[1] = 103.0
    assert outcomes.classify(high, low, 0, 1, 99.0, 101.0, 0.01, 48) == "BREAK"
    high[1] = 100.0
    low[2] = 97.0
    assert outcomes.classify(high, low, 0, -1, 99.0, 101.0, 0.01, 48) == "BREAK"
    low[2] = 100.0
    high[3] = 103.0
    low[3] = 97.0
    assert outcomes.classify(high, low, 0, 1, 99.0, 101.0, 0.01, 48) == "AMBIGUOUS"
    high[3] = 100.0
    low[3] = 100.0
    low[4] = 97.0
    high[6] = 103.0
    assert outcomes.classify(high, low, 0, 1, 99.0, 101.0, 0.01, 48) == "REJECT"
    assert P.HOLD_BARS_PRIMARY == 48


def test_control_rows_keep_real_metadata_and_the_rotated_touch_clock():
    members = [
        _member("PDH", 100.0, 0),
        _member("PWH", 100.10, 0),
    ]
    ledger = _ledger(members, i0=10, i1=300, anchor="PWH", family="WEEK", side=1, source_key=7, price=100.0)
    birth = _birth(formation_range=1.25, close_off_extreme=0.4, extreme_timing=0.2, extreme_density=0.1,
                   formation_volume=-0.3)
    prepared = {"ledgers": {"PWH:7:10": ledger}, "birth": {"PWH:7:10": birth}}
    touch = {
        "episode_id": "CTRL:PWH:7:10:OTHER",
        "population": "control",
        "feature_eligible": True,
        "sigma": 0.0015,
        "x_primary": 0.02,
        "bucket": "1",
        "side": 1,
        "year": 2022,
        "j": 20,
        "i0": 10,
        "zone_low": 90.0,
        "zone_high": 91.0,
        "family": "WEEK",
    }
    controls = [{"episode_id": touch["episode_id"], "shadow_id": "PWH:7:10", "n_members": 1}]
    rows = control_rows([touch], controls, prepared, {"PWH:7:10"})
    assert len(rows) == 1
    assert rows[0]["match_id"] == "PWH:7:10"
    assert rows[0]["real"] == 0.0
    assert rows[0]["confluence"] == 2
    assert rows[0]["formation_range"] == pytest.approx(1.25)
    assert rows[0]["zone_low"] == 90.0
    assert rows[0]["j"] == 20
    assert rows[0]["age"] == pytest.approx((20 - 10) / (300 - 10))
    assert control_rows([touch], controls, prepared, set()) == []
    real_touch = {**touch, "episode_id": "PWH:7:10", "population": "real", "zone_low": 99.0, "j": 40}
    real = real_rows([real_touch], prepared)
    assert real[0]["formation_range"] == rows[0]["formation_range"]
    assert real[0]["confluence"] == rows[0]["confluence"]
    assert real[0]["j"] != rows[0]["j"]


def _factorial():
    rows = []
    i = 0
    for real in (1.0, 0.0):
        for year in K.YEARS:
            for family in K.FAMILIES:
                for bucket in ("1", "2", "3+"):
                    for support in (0.0, 1.0):
                        for vol in (0, 1, 2):
                            for feature in (-1.0, 1.0):
                                rows.append({
                                    "cluster": f"c{i % 50}",
                                    "real": real,
                                    "family": family,
                                    "bucket": bucket,
                                    "touch2": 1.0 if bucket == "2" else 0.0,
                                    "touch3": 1.0 if bucket == "3+" else 0.0,
                                    "support": support,
                                    "year": year,
                                    "vol_tercile": vol,
                                    "age": 0.2 + 0.07 * ((i * 3) % 11),
                                    "formation_range": feature,
                                    "outcome": "BREAK" if real == 1.0 and feature > 0 else "REJECT",
                                })
                                i += 1
    return rows


def test_stacked_estimand_is_real_minus_pseudo_and_standardizes_on_the_real_scale():
    sample = _factorial()
    real = [row for row in sample if row["real"] == 1.0]
    scales = inference.freeze_scales(real, ["formation_range", "age"], {})
    assert scales["formation_range"]["mean"] == pytest.approx(0.0)
    assert scales["formation_range"]["sd"] == pytest.approx(1.0)
    assert inference._z(1.0, scales["formation_range"]) == pytest.approx(1.0)
    binary_scale = {"mean": 0.2, "sd": 0.4, "binary": True}
    assert inference._z(1.0, binary_scale) == 1.0
    got = inference.lpm(
        sample, scales, "formation_range", "BREAK", {}, ["formation_range"], spec="full", draws=0)
    assert got["delta"] is not None and got["delta"] > 0.05
    assert got["beta_real"] == pytest.approx(got["beta_pseudo"] + got["delta"])
    assert abs(got["beta_pseudo"]) < abs(got["delta"])


def test_shape_bootstrap_matches_row_repetition():
    rng = np.random.default_rng(0)
    rows = []
    for i in range(60):
        rows.append({
            "cluster": f"c{i % 12}",
            "real": 1.0 if i < 30 else 0.0,
            "formation_range": float(rng.normal()),
            "confluence": 1.0 if i % 4 else 0.0,
            "outcome": "BREAK" if rng.random() > 0.6 else "NEITHER",
        })
    scales = inference.freeze_scales(
        [row for row in rows if row["real"] == 1.0], ["formation_range", "confluence"],
        {"confluence": {"coding": "binary"}})
    draws, seed = 40, 11
    acc = inference._shape_bootstrap(rows, "formation_range", "BREAK", scales["formation_range"], draws, seed)
    clusters = [row["cluster"] for row in rows]
    keys = sorted(set(clusters))
    code = {key: i for i, key in enumerate(keys)}
    cluster = np.asarray([code[c] for c in clusters], dtype=int)
    draw = np.random.default_rng(seed).integers(0, len(keys), size=(draws, len(keys)))
    naive = np.full(draws, np.nan)
    q33, q66 = scales["formation_range"]["q33"], scales["formation_range"]["q66"]
    for b in range(draws):
        counts = np.bincount(draw[b], minlength=len(keys))
        parts = [np.repeat(np.flatnonzero(cluster == c), int(counts[c])) for c in range(len(keys)) if counts[c]]
        sample = [rows[int(i)] for i in np.concatenate(parts)]
        got = inference._tertile_gap(sample, "formation_range", "BREAK", q33, q66)
        naive[b] = np.nan if got is None else got
    assert np.allclose(acc, naive, equal_nan=True)
    binary = inference._shape_bootstrap(rows, "confluence", "BREAK", scales["confluence"], draws, seed)
    draw_b = np.random.default_rng(seed).integers(0, len(keys), size=(draws, len(keys)))
    naive_b = np.full(draws, np.nan)
    for b in range(draws):
        counts = np.bincount(draw_b[b], minlength=len(keys))
        parts = [np.repeat(np.flatnonzero(cluster == c), int(counts[c])) for c in range(len(keys)) if counts[c]]
        sample = [rows[int(i)] for i in np.concatenate(parts)]
        got = inference._binary_gap(sample, "confluence", "BREAK")
        naive_b[b] = np.nan if got is None else got
    assert np.allclose(binary, naive_b, equal_nan=True)


def test_sparse_count_coding_and_redundancy_are_outcome_blind():
    binary = redundancy.code_count(np.array([1, 1, 1, 2, 1, 2], dtype=float))
    assert binary["coding"] == "binary"
    continuous = redundancy.code_count(np.concatenate([np.ones(95), np.full(5, 3.0)]))
    assert continuous["coding"] == "continuous"
    assert redundancy.code_count(np.ones(10))["coding"] == "drop"
    rows = [{"confluence": v, "outcome": "BREAK"} for v in (1, 1, 2, 1, 2, 1)]
    decision = redundancy.apply_coding(rows, "confluence")
    assert decision["contrast"] == "multi_minus_singleton"
    assert [row["confluence"] for row in rows] == [0.0, 0.0, 1.0, 0.0, 1.0, 0.0]
    paired = []
    for i, value in enumerate(np.linspace(0.1, 0.9, 12)):
        paired.append({"age": value, "zone_span": value, "formation_range": float((i % 3) - 1)})
    rule = redundancy.apply_rule(paired, ("age", "zone_span", "formation_range"))
    assert rule["retained"][0] == "age"
    assert any(row["feature"] == "zone_span" and abs(row["rho"]) >= 0.90 for row in rule["dropped"])
    assert "formation_range" in rule["retained"]
    assert redundancy.missing_rate([{"age": 1.0}, {"age": None}, {"age": math.nan}], "age") == pytest.approx(2 / 3)


def test_bh_hand_example_and_successor_clauses():
    adjusted = inference.bh_adjust([0.001, 0.04, 0.03, 0.2])
    assert adjusted[0] == pytest.approx(0.004)
    assert adjusted[1] == pytest.approx(0.04 * 4 / 3)
    assert adjusted[2] == pytest.approx(0.04 * 4 / 3)
    assert adjusted[3] == pytest.approx(0.2)
    assert inference.bh_adjust([None, 0.01])[0] == pytest.approx(1.0)

    def years(sign, n=40):
        return [{"beta_real": sign * 0.04, "delta": sign * 0.04, "n_real": n, "n_pseudo": n} for _ in K.YEARS]

    primary = {"delta": 0.04, "beta_real": 0.05, "delta_ci95": [0.01, 0.08]}
    quiet = {"delta": 0.0, "delta_ci95": [-0.01, 0.01]}
    assert claim.successor_ok(
        primary=primary, years=years(1), loyo=years(1), families=years(1)[:3], lofo=years(1)[:3],
        no_touch=quiet, q=0.05) is True
    assert claim.successor_ok(
        primary={"delta": 0.04, "beta_real": 0.05, "delta_ci95": [-0.01, 0.08]},
        years=years(1), loyo=years(1), families=years(1)[:3], lofo=years(1)[:3],
        no_touch=quiet, q=0.05) is False
    assert claim.successor_ok(
        primary=primary, years=years(1), loyo=years(1), families=years(1)[:3], lofo=years(1)[:3],
        no_touch=quiet, q=0.20) is False
    thin = [{"delta": 0.04, "n_real": 10, "n_pseudo": 10}]
    assert claim.successor_ok(
        primary=primary, years=years(1), loyo=years(1), families=years(1)[:1], lofo=thin,
        no_touch=quiet, q=0.05) is True
    flipped = [{"delta": -0.04, "n_real": 40, "n_pseudo": 40}]
    assert claim.successor_ok(
        primary=primary, years=years(1), loyo=years(1), families=years(1)[:3], lofo=flipped,
        no_touch=quiet, q=0.05) is False
    opposite = {"delta": -0.05, "delta_ci95": [-0.08, -0.02]}
    assert claim.successor_ok(
        primary=primary, years=years(1), loyo=years(1), families=years(1)[:3], lofo=years(1)[:3],
        no_touch=opposite, q=0.05) is False
    notable = {"delta": 0.04, "delta_ci95": [0.01, 0.08], "beta_real": 0.01, "beta_real_ci95": [-0.01, 0.02]}
    real_only = {"delta": 0.01, "delta_ci95": [-0.01, 0.02], "beta_real": 0.05, "beta_real_ci95": [0.01, 0.08]}
    assert claim.routing_status(1, [notable], [], sparse_note=False) == "LEVEL_SPECIFIC_STRUCTURE_PRESENT"
    assert claim.routing_status(0, [notable], [], sparse_note=False) == "STRUCTURE_PRESENT_BUT_UNSTABLE"
    assert claim.routing_status(0, [real_only], [], sparse_note=False) == "NO_LEVEL_SPECIFIC_STRUCTURE"
    assert claim.routing_status(0, [real_only], [notable], sparse_note=False) == "NO_LEVEL_SPECIFIC_STRUCTURE"
    assert claim.routing_status(0, [], [notable], sparse_note=False) == "REDUNDANT_WITH_KNOWN_STATE"
    assert claim.routing_status(0, [], [], sparse_note=True) == "INFORMATION_LIMITED"
    assert claim.atlas_state("NO_LEVEL_SPECIFIC_STRUCTURE") == "NO_STRUCTURE"
    assert claim.atlas_state("LEVEL_SPECIFIC_STRUCTURE_PRESENT") == "CLOSED_ON_SURFACE"
    assert claim.claim_level("LEVEL_SPECIFIC_STRUCTURE_PRESENT", 500) == "DISCOVERY_ONLY"
    assert claim.claim_level("NO_LEVEL_SPECIFIC_STRUCTURE", 500) == "L2"
    assert claim.claim_level("NO_LEVEL_SPECIFIC_STRUCTURE", 10) == "not_issued"


def test_columns_keep_the_level_specific_term_and_do_not_inherit_a_family_cap():
    full = inference.columns_for("formation_range", {}, ["formation_range", "confluence"])
    assert "feature_x_real" in full
    assert "age_z" in full
    assert "confluence_z" not in full
    span = inference.columns_for("zone_span", {}, ["zone_span", "confluence"])
    assert "confluence_z" in span
    age_cols = inference.columns_for("age", {}, ["age"])
    assert "age_z" not in age_cols
    loyo = inference.columns_for("age", {}, ["age"], spec="loyo", drop_year=2020)
    assert "feature_x_real" in loyo and "y2021" not in loyo and "y2022" in loyo
    assert "y2023" not in inference.columns_for("age", {}, ["age"], spec="loyo", drop_year=2023)
    day = inference.columns_for("age", {}, ["age"], spec="lofo", drop_family="DAY")
    assert "fam_week" not in day and "fam_month" in day
    assert "fam_month" not in inference.columns_for("age", {}, ["age"], spec="lofo", drop_family="MONTH")
    assert "touch2" not in inference.columns_for("age", {}, ["age"], spec="no_touch")
    assert K.cells_per_feature_outcome() == 24
    assert not hasattr(K, "MAX_FAMILY_SHARE")


def test_shape_labels_and_complete_rows():
    bands = {
        "low": {"diff": 0.01},
        "mid": {"diff": 0.02},
        "high": {"diff": 0.05},
    }
    assert inference.shape_label(bands, {"binary": False, "coef": 0.04, "ci95": [0.01, 0.08]}) == "monotonic"
    u = {"low": {"diff": 0.01}, "mid": {"diff": 0.20}, "high": {"diff": 0.02}}
    assert inference.shape_label(u, {"binary": False, "coef": 0.04, "ci95": [0.01, 0.08]}) == "u_shape"
    assert inference.shape_label(bands, {"binary": True}) == "binary_contrast"
    assert inference.shape_label({"low": {"diff": None}, "mid": {"diff": 0.0}, "high": {"diff": 0.0}},
                                  {"binary": False}) == "insufficient"
    kept = complete(
        [{"age": 1.0, "confluence": 2.0}, {"age": None, "confluence": 2.0}],
        ["age", "confluence"],
    )
    assert len(kept) == 1


def test_matched_control_keeps_only_episodes_present_on_both_sides():
    real = [{"cluster": "a", "age": 1.0}, {"cluster": "b", "age": 1.0}]
    pseudo = [{"cluster": "a", "age": 0.2}, {"cluster": "c", "age": 0.2}]
    kept_real, kept_pseudo = restrict_matched(real, pseudo)
    assert [row["cluster"] for row in kept_real] == ["a"]
    assert [row["cluster"] for row in kept_pseudo] == ["a"]


def test_protected_surface_and_feature_modules_do_not_classify_outcomes():
    with pytest.raises(RuntimeError):
        assert_panel_legal(np.array([P.E1_START_MS]))
    with pytest.raises(RuntimeError):
        assert_panel_legal(np.array([P.SURFACE_END_MS]))
    assert_panel_legal(np.array([P.DATA_START_MS, P.DATA_START_MS + P.BAR_MS]))
    assert events.touch_year(_ms(2020, 12, 31, 23, 55)) == 2020
    assert events.touch_year(_ms(2021, 1, 1, 0, 0)) == 2021
    root = Path("scripts/research/level_structure_discovery_v1")
    for name in ("preflight.py", "rows.py", "formation.py", "features.py", "membership.py", "redundancy.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "level_touch_degradation_v1.outcomes" not in text
        assert "import outcomes" not in text
    evaluate = (root / "evaluate.py").read_text(encoding="utf-8")
    assert "outcomes import attach" in evaluate or "outcomes import" in evaluate
    assert "taker_buy_quote" not in (root / "formation.py").read_text(encoding="utf-8")
