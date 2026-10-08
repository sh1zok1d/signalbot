"""LEVEL_LIQUIDITY_STATE_DISCOVERY_V1. Schema, PIT, features, labels, and the estimator."""

from __future__ import annotations

import json
import math

import numpy as np

from scripts.research.level_liquidity_state_discovery_v1 import constants as K
from scripts.research.level_liquidity_state_discovery_v1.analyze import y_of
from scripts.research.level_liquidity_state_discovery_v1.book import (
    _refuse_day,
    book_features,
    features_from_snapshots,
    inventory_identity,
    orient,
    parse_book_csv,
    snapshot_at,
)
from scripts.research.level_liquidity_state_discovery_v1.claim import conjunction, route, specificity_label
from scripts.research.level_liquidity_state_discovery_v1.cohort import (
    epoch_of,
    geometry_status,
    price_nuisance,
)
from scripts.research.level_liquidity_state_discovery_v1.inference import (
    bh_adjust,
    fit_rows,
    freeze_scales,
    redundancy,
)
from scripts.research.level_touch_degradation_v1.outcomes import classify


ROOT_INV = "docs/research_data/DH3_BINANCE_UM_BOOKDEPTH_V0/SOURCE_INVENTORY.json"
T0 = 1_672_531_200_000  # 2023-01-01 00:00:00Z


def _book(rows):
    t = np.array([r[0] for r in rows], dtype=np.int64)
    return {
        "t": t,
        "bid": np.array([r[1] for r in rows], dtype=float),
        "ask": np.array([r[2] for r in rows], dtype=float),
    }


def test_inventory_is_btc_bookdepth_through_2024_only():
    inv = json.loads(open(ROOT_INV).read())
    assert inv["DATASET_ID"] == "DH3_BINANCE_UM_BOOKDEPTH_V0"
    assert inventory_identity(inv) == K.BOOK_OBJECT_LIST_SHA256
    days = []
    for obj in inv["OBJECTS"]:
        assert obj["DAY"] < "2025-01-01"
        assert "2025" not in obj["KEY"] and "2026" not in obj["KEY"]
        if obj["SYMBOL"] == "BTC":
            days.append(obj["DAY"])
    assert days[0] == "2023-01-01" and days[-1] == "2024-12-31"
    missing = [o["DAY"] for o in inv["OBJECTS"] if o["SYMBOL"] == "BTC" and o["STATUS"] != "VERIFIED"]
    assert missing == ["2023-02-08", "2023-02-09", "2024-04-18"]


def test_parser_keeps_pm1_notional_and_rejects_a_zoned_stamp():
    text = "\n".join([
        "timestamp,percentage,depth,notional",
        "2023-01-01 00:06:05,-5,10,500",
        "2023-01-01 00:06:05,-1,4,100",
        "2023-01-01 00:06:05,1,5,120",
        "2023-01-01 00:06:05,5,20,900",
        "2023-01-01 00:06:35,-1,4,110",
        "2023-01-01 00:06:35,1,5,130",
    ])
    parsed = parse_book_csv(text)
    assert parsed["bands"] == {-5, -1, 1, 5}
    assert parsed["narrower"] is False
    assert parsed["t"].tolist() == [
        int(__import__("datetime").datetime(2023, 1, 1, 0, 6, 5, tzinfo=__import__("datetime").timezone.utc).timestamp() * 1000),
        int(__import__("datetime").datetime(2023, 1, 1, 0, 6, 35, tzinfo=__import__("datetime").timezone.utc).timestamp() * 1000),
    ]
    assert parsed["bid"][0] == 100.0 and parsed["ask"][0] == 120.0
    assert math.isnan(parse_book_csv("2023-01-01 00:06:05,-1,-1,10\n2023-01-01 00:06:05,1,1,10\n")["bid"][0])
    conflict = "\n".join([
        "2023-01-01 00:06:05,-1,1,10",
        "2023-01-01 00:06:05,-1,1,11",
        "2023-01-01 00:06:05,1,1,12",
    ])
    assert math.isnan(parse_book_csv(conflict)["bid"][0])


def test_loader_refuses_2025():
    try:
        _refuse_day("2025-01-01", "data/futures/um/daily/bookDepth/BTCUSDT/BTCUSDT-bookDepth-2025-01-01.zip")
    except RuntimeError as exc:
        assert "refuses" in str(exc)
    else:
        raise AssertionError("2025 day was accepted")


def test_staleness_future_and_gap_are_fail_closed():
    t = T0 + 3_600_000
    book = _book([
        (t - 600_000, 10.0, 10.0),
        (t - 20_000, 30.0, 40.0),
        (t, 99.0, 99.0),
        (t + 10_000, 1.0, 1.0),
    ])
    now = snapshot_at(book, t, strict=True)
    assert now["t"] == t - 20_000 and now["bid"] == 30.0
    stale = _book([(t - 100_000, 10.0, 12.0)])
    assert snapshot_at(stale, t, strict=True) is None
    assert snapshot_at(_book([(t + 5_000, 10.0, 12.0)]), t, strict=True) is None
    # A bad print does not forward-fill across a gap, and a fresh good print still counts.
    mixed = _book([
        (t - 40_000, 7.0, 8.0),
        (t - 10_000, np.nan, np.nan),
    ])
    assert snapshot_at(mixed, t, strict=True)["bid"] == 7.0
    only_bad = _book([(t - 10_000, np.nan, 8.0), (t - 200_000, 1.0, 1.0)])
    assert snapshot_at(only_bad, t, strict=True) is None


def test_orientation_imbalance_and_zero_safe_logs():
    assert orient(10.0, 40.0, 1) == (40.0, 10.0)
    assert orient(10.0, 40.0, -1) == (10.0, 40.0)
    now = {"t": 100, "bid": 10.0, "ask": 40.0, "age_ms": 20}
    past = {"t": 50, "bid": 20.0, "ask": 20.0, "age_ms": 10}
    feat = features_from_snapshots(now, past, 1)
    assert feat["TOTAL_LOCAL_DEPTH"] == 50.0
    assert feat["ORIENTED_DEPTH_IMBALANCE"] == (40.0 - 10.0) / 50.0
    assert feat["AHEAD_DEPTH_CHANGE_60M"] == math.log(40.0 / 20.0)
    assert feat["BEHIND_DEPTH_CHANGE_60M"] == math.log(10.0 / 20.0)
    assert feat["TOTAL_DEPTH_CHANGE_60M"] == math.log(50.0 / 40.0)
    zero_now = {"t": 100, "bid": 0.0, "ask": 40.0, "age_ms": 20}
    zeroed = features_from_snapshots(zero_now, past, 1)
    assert zeroed["AHEAD_DEPTH_CHANGE_60M"] == math.log(40.0 / 20.0)
    assert zeroed["BEHIND_DEPTH_CHANGE_60M"] is None
    assert zeroed["TOTAL_LOCAL_DEPTH"] == 40.0
    support = features_from_snapshots(now, past, -1)
    assert support["ahead_now"] == 10.0 and support["behind_now"] == 40.0
    assert features_from_snapshots(None, past, 1)["book_status"] == "NO_OR_STALE_NOW"
    assert features_from_snapshots(now, None, 1)["book_status"] == "NO_OR_STALE_PAST"


def test_touch_bar_and_60m_snapshot_are_excluded_when_illegal():
    t = T0 + 2 * 3_600_000
    book = _book([
        (t - K.PRIMARY_MS - 30_000, 5.0, 6.0),
        (t - K.PRIMARY_MS, 8.0, 9.0),
        (t - 15_000, 12.0, 7.0),
        (t, 100.0, 100.0),
    ])
    got = book_features(book, t, 1)
    assert got["book_now_ms"] == t - 15_000
    assert got["book_past_ms"] == t - K.PRIMARY_MS
    assert got["ahead_now"] == 7.0
    missing_past = _book([
        (t - K.PRIMARY_MS - 200_000, 5.0, 6.0),
        (t - 15_000, 12.0, 7.0),
    ])
    assert book_features(missing_past, t, 1)["book_status"] == "NO_OR_STALE_PAST"
    assert book_features(book, t, 1)["book_now_ms"] < t


def test_price_nuisance_excludes_the_touch_bar():
    t0 = T0
    n = 400
    quote = np.ones(n)
    quote[-1] = 1e9
    open_ = np.full(n, 100.0)
    close = np.full(n, 100.0)
    close[-2] = 110.0
    decision = t0 + (n - 1) * K.BAR_MS
    got = price_nuisance(open_, close, quote, t0, decision, 1)
    assert got["disp"] == math.log(110.0 / 100.0)
    assert got["rel_volume"] < 2.0
    quote[(n - 1) - 12:(n - 1)] = 0.0
    assert price_nuisance(open_, close, quote, t0, decision, 1)["rel_volume"] == 0.0


def test_geometry_requires_a_born_level_and_the_book_window():
    base = {
        "touch_number": 1, "open_ms": K.EVENT_START_MS, "j": 10, "i0": 10,
        "window_ok_48": True, "side": 1, "x_primary": 0.01, "sigma": 0.002,
    }
    assert geometry_status(base) == "LEGITIMATE"
    assert geometry_status({**base, "j": 9}) == "LEVEL_NOT_YET_BORN"
    assert geometry_status({**base, "touch_number": 2}) == "NOT_FIRST"
    assert geometry_status({**base, "open_ms": K.EVENT_START_MS - K.BAR_MS}) == "OUTSIDE_WINDOW"
    assert epoch_of(K._ms("2023-06-30T23:00:00+00:00")) == "2023H1"
    assert epoch_of(K._ms("2023-07-01T00:00:00+00:00")) == "2023H2"
    assert epoch_of(K._ms("2024-12-31T23:00:00+00:00")) == "2024H2"
    assert epoch_of(K._ms("2025-01-01T00:00:00+00:00")) is None


def test_outcomes_and_a_barrier_path():
    assert y_of("BREAK", "RESOLVE_4H") == 1.0
    assert y_of("REJECT", "RESOLVE_4H") == 1.0
    assert y_of("NEITHER", "RESOLVE_4H") == 0.0
    assert y_of("AMBIGUOUS", "RESOLVE_4H") is None
    assert y_of("BREAK", "BREAK_GIVEN_RESOLVED") == 1.0
    assert y_of("REJECT", "BREAK_GIVEN_RESOLVED") == 0.0
    assert y_of("NEITHER", "BREAK_GIVEN_RESOLVED") is None
    high = np.array([100.0, 100.2, 120.0])
    low = np.array([99.0, 99.5, 100.0])
    assert classify(high, low, 0, 1, 100.0, 101.0, 0.01, 2) == "BREAK"
    flat_h = np.array([100.0, 100.2, 100.3])
    flat_l = np.array([99.8, 99.9, 99.9])
    assert classify(flat_h, flat_l, 0, 1, 100.0, 101.0, 0.01, 2) == "NEITHER"


def _row(i, feature, y, epoch="2023H1", family="DAY", side=1, week=None):
    rng = np.random.default_rng(1000 + i)
    return {
        "feature": feature,
        "y": y,
        "family": family,
        "side": side,
        "support": 0.0 if side > 0 else 1.0,
        "epoch": epoch,
        "vol_tercile": int(rng.integers(0, 3)),
        "time_block": int(rng.integers(0, 4)),
        "disp": float(rng.normal()),
        "rel_volume": float(abs(rng.normal()) + 0.2),
        "cluster": int(i // 3) if week is None else int(week),
        "nuisance_ok": True,
        "TOTAL_LOCAL_DEPTH": feature,
    }


def test_scale_fdr_effect_and_week_bootstrap():
    rng = np.random.default_rng(11)
    rows = []
    for i in range(240):
        z = float(rng.normal())
        y = 1.0 if z + float(rng.normal()) > 0 else 0.0
        epoch = K.EPOCHS[int(rng.integers(0, 4))]
        family = ("DAY", "WEEK", "MONTH")[int(rng.integers(0, 3))]
        side = 1 if rng.random() > 0.5 else -1
        rows.append(_row(i, 100.0 + 10.0 * z, y, epoch=epoch, family=family, side=side, week=int(rng.integers(0, 40))))
    scales = freeze_scales(rows, ["TOTAL_LOCAL_DEPTH"])
    assert scales["TOTAL_LOCAL_DEPTH"]["sd"] > 0
    cell = fit_rows(rows, "TOTAL_LOCAL_DEPTH", scales, draws=40, seed=11)
    assert cell["n"] == 240
    assert cell["bootstrap_valid"] >= 30
    assert cell["coef"] is not None and cell["ci95"] is not None
    qs = bh_adjust([0.01, 0.2, None])
    assert qs[0] <= qs[1] <= 1.0
    redundant = []
    for i in range(40):
        x = float(i)
        redundant.append({
            "TOTAL_LOCAL_DEPTH": x,
            "ORIENTED_DEPTH_IMBALANCE": x / 100.0,
            "AHEAD_DEPTH_CHANGE_60M": float(np.sin(i)),
            "BEHIND_DEPTH_CHANGE_60M": float(np.cos(i)),
            "TOTAL_DEPTH_CHANGE_60M": float(np.sin(i)) + 0.01,
        })
    rule = redundancy(redundant)
    assert "ORIENTED_DEPTH_IMBALANCE" in {item["feature"] for item in rule["dropped"]}
    assert "TOTAL_LOCAL_DEPTH" in rule["kept"]


def test_candidate_rule_and_specificity_do_not_rescue_a_null():
    cell = {"n": 200, "q": 0.04, "coef": 0.05, "ci95": [0.02, 0.08]}
    epochs = [{"n": 40, "coef": 0.04} for _ in range(4)]
    loeo = [{"n": 150, "coef": 0.03} for _ in range(4)]
    lofo = [{"n": 80, "coef": 0.04} for _ in range(3)]
    sides = [{"n": 90, "coef": 0.04}, {"n": 90, "coef": 0.02}]
    assert conjunction(cell, epochs, loeo, lofo, sides)["pass"]
    flipped = [dict(sides[0]), {"n": 90, "coef": -0.04}]
    assert "side" in conjunction(cell, epochs, loeo, lofo, flipped)["failed"]
    weak = {**cell, "coef": 0.01, "q": 0.4, "ci95": [-0.01, 0.03]}
    assert conjunction(weak, epochs, loeo, lofo, sides)["pass"] is False
    material = specificity_label(cell, {
        "delta": 0.04, "ci95": [0.01, 0.07], "beta_real": 0.05, "beta_pseudo": 0.01,
    })
    assert material == "LEVEL_LIQUIDITY_INTERACTION_CANDIDATE"
    similar = specificity_label(cell, {
        "delta": 0.01, "ci95": [-0.02, 0.04], "beta_real": 0.05, "beta_pseudo": 0.04,
    })
    assert similar == "GENERIC_LIQUIDITY_STATE_CANDIDATE"
    unresolved = specificity_label(cell, {
        "delta": 0.01, "ci95": [-0.02, 0.04], "beta_real": 0.05, "beta_pseudo": -0.02,
    })
    assert unresolved == "SPECIFICITY_UNRESOLVED"
    decisions = [{
        "label": "NONE", "statistical_hit": False, "conjunction_pass": False,
    }]
    assert route(decisions, n_resolve=400, clusters=80) == "NO_INCREMENTAL_LEVEL_LIQUIDITY_STRUCTURE"
    assert route(
        [{"label": "LEVEL_LIQUIDITY_INTERACTION_CANDIDATE", "statistical_hit": True, "conjunction_pass": True}],
        n_resolve=400, clusters=80,
    ) == "LEVEL_LIQUIDITY_STRUCTURE_PRESENT"
    assert route(decisions, n_resolve=20, clusters=4) == "INFORMATION_LIMITED"


def test_pseudo_formula_uses_the_pseudo_clock_and_not_the_book_to_move_price():
    real_t = T0 + 5 * 3_600_000
    pseudo_t = real_t + 12 * K.BAR_MS
    book = _book([
        (real_t - K.PRIMARY_MS, 10.0, 10.0),
        (real_t - 10_000, 20.0, 30.0),
        (pseudo_t - K.PRIMARY_MS, 11.0, 12.0),
        (pseudo_t - 10_000, 40.0, 15.0),
    ])
    real = book_features(book, real_t, 1)
    pseudo = book_features(book, pseudo_t, -1)
    assert real["book_now_ms"] != pseudo["book_now_ms"]
    assert pseudo["ahead_now"] == 40.0
    assert real["ahead_now"] == 30.0
    pair = {"episode_id": "PDH:1", "pseudo_episode_id": "PDH:1:pseudo", "real": real, "pseudo": pseudo}
    assert pair["real"]["book_now_ms"] == real_t - 10_000
    assert pair["pseudo"]["book_past_ms"] == pseudo_t - K.PRIMARY_MS
