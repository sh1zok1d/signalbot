"""Confirmation semantics on fixtures. The market panel is read only by the loader identity test."""

from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from beta.hist_series import BARS_PER_DAY, Bars

from scripts.research.level_touch_degradation_v1 import constants as PARENT
from scripts.research.level_touch_degradation_v1 import outcomes
from scripts.research.level_touch_degradation_v1.control import control_episodes
from scripts.research.level_touch_degradation_v1.events import build_episodes, level_instances, scan_episode

from scripts.research.level_first_touch_resolution_confirmation_v1 import (
    analyze,
    claim,
    cohort,
    constants as K,
    data,
    endpoint,
    evaluate,
    inference,
    report,
)

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "scripts" / "research" / "level_first_touch_resolution_confirmation_v1"


def _ms(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _bars(t0, n, price=100.0):
    c = np.full(n, price, dtype=float)
    return Bars(t0=t0, open=c.copy(), high=c.copy(), low=c.copy(), close=c.copy(),
                volume=np.ones(n), quote=np.ones(n), taker_buy_quote=np.ones(n), oi=np.full(n, np.nan))


def _touch(**over):
    base = {
        "episode_id": "PDH:1:10", "touch_number": 1, "open_ms": _ms(2018, 6, 1), "week": 100,
        "side": 1, "x_primary": 0.01, "window_ok_48": True, "sigma": 0.002, "year": 2018,
        "j": 3, "zone_low": 99.85, "zone_high": 100.15,
    }
    base.update(over)
    return base


def _pair(epoch="2018", family="DAY", week=100, real_side=1, pseudo_side=1, real_sigma=0.002,
          pseudo_sigma=0.002):
    return {
        "episode_id": f"{family}:{week}", "family": family, "week": week, "epoch": epoch,
        "pseudo_epoch": epoch, "real_side": real_side, "pseudo_side": pseudo_side,
        "real_sigma": real_sigma, "pseudo_sigma": pseudo_sigma,
        "real_touch": _touch(), "pseudo_touch": _touch(episode_id="CTRL"),
    }


def test_loader_identity_and_no_post_2019_bar():
    inv = data.inventory()
    assert inv["DATASET_ID"] == "DH1_BITMEX_XBTUSD_TRADES_5M_V0"
    assert inv["DAYS"].startswith("2017-08-01")
    assert inv["DAYS"].endswith("2019-12-31")
    bars, ident = data.load_confirmation_bars()
    assert ident["canonical_sha256"] == inv["CANONICAL_SHA256"]
    assert bars.t0 == K.DATA_START_MS
    assert bars.end_ms == K.EVENT_END_MS
    assert int(bars.times.max()) < K.EVENT_END_MS
    assert int(bars.times.max()) < K.PROTECTED_FROM_MS
    assert K.EVENT_END < "2025-01-01"
    assert K.N_CELLS == 16


def test_panel_guard_rejects_2020_2025_and_the_e1_window():
    ok = {"open_ms": np.array([_ms(2018, 1, 1)])}
    data.assert_panel(ok)
    with pytest.raises(RuntimeError):
        data.assert_panel({"open_ms": np.array([K.EVENT_END_MS])})
    with pytest.raises(RuntimeError):
        data.assert_panel({"open_ms": np.array([K.PROTECTED_FROM_MS])})
    with pytest.raises(RuntimeError):
        data.assert_panel({"open_ms": np.array([K.DATA_START_MS - K.HOLD_BARS])})
    with pytest.raises(RuntimeError):
        data.assert_panel({"open_ms": np.array([K.E1_START_MS])})


def test_full_previous_day_week_and_month():
    t0 = _ms(2017, 8, 1)
    n = (31 + 30 + 31) * BARS_PER_DAY
    b = _bars(t0, n, 100.0)
    inst, _drops = level_instances(b)
    days = [i for i in inst if i["kind"] == "PDH"]
    assert days and days[0]["i0"] == BARS_PER_DAY
    weeks = [i for i in inst if i["family"] == "WEEK"]
    assert weeks and min(i["i0"] for i in weeks) >= 13 * BARS_PER_DAY
    months = [i for i in inst if i["family"] == "MONTH"]
    assert {i["kind"] for i in months} >= {"PMH", "PML"}
    assert min(i["i0"] for i in months) == 31 * BARS_PER_DAY
    gappy = _bars(t0, n, 100.0)
    gappy.close[: 31 * BARS_PER_DAY] = np.nan
    gappy.high[: 31 * BARS_PER_DAY] = np.nan
    gappy.low[: 31 * BARS_PER_DAY] = np.nan
    inst_g, drops = level_instances(gappy)
    assert drops["incomplete_source"] > 0
    assert not any(i["family"] == "MONTH" and i["i0"] == 31 * BARS_PER_DAY for i in inst_g)


def test_first_touch_only_and_parent_flag_is_not_reused():
    touch = _touch(open_ms=_ms(2018, 6, 1))
    assert cohort.first_touch_status(touch, event_start_ms=K.EVENT_START_MS, event_end_ms=K.EVENT_END_MS) == "LEGITIMATE"
    assert touch["open_ms"] < PARENT.EVENT_START_MS
    assert cohort.first_touch_status(_touch(touch_number=2), event_start_ms=K.EVENT_START_MS,
                                     event_end_ms=K.EVENT_END_MS) == "NOT_FIRST"
    assert cohort.first_touch_status(_touch(open_ms=_ms(2017, 8, 15)), event_start_ms=K.EVENT_START_MS,
                                     event_end_ms=K.EVENT_END_MS) == "OUTSIDE_WINDOW"
    assert cohort.first_touch_status(_touch(window_ok_48=False), event_start_ms=K.EVENT_START_MS,
                                     event_end_ms=K.EVENT_END_MS) == "INCOMPLETE_4H"


def test_zone_orientation_and_pseudo_link():
    assert K.ZONE_HALF == PARENT.ZONE_HALF_PRIMARY
    instances = [
        {"kind": "PDH", "family": "DAY", "struct_side": 1, "price": 100.0, "i0": 0, "i1": 10,
         "period_open": 90.0, "source_key": 1, "period_key": 2},
        {"kind": "PDH", "family": "DAY", "struct_side": 1, "price": 100.1, "i0": 0, "i1": 10,
         "period_open": 90.0, "source_key": 1, "period_key": 2},
        {"kind": "PDH", "family": "DAY", "struct_side": 1, "price": 130.0, "i0": 20, "i1": 30,
         "period_open": 120.0, "source_key": 3, "period_key": 4},
    ]
    episodes, _info = build_episodes(instances, K.ZONE_HALF)
    assert len(episodes) == 2
    assert episodes[0]["zone_low"] == pytest.approx(100.0 * (1 - K.ZONE_HALF))
    assert episodes[0]["n_members"] == 2
    first = control_episodes(episodes, instances, K.ZONE_HALF)
    second = control_episodes(episodes, instances, K.ZONE_HALF)
    assert [c["episode_id"] for c in first] == [c["episode_id"] for c in second]
    assert {c["shadow_id"] for c in first} == {ep["episode_id"] for ep in episodes}
    assert cohort.control_episodes is control_episodes
    n = 30
    b = _bars(_ms(2018, 6, 2), n, 105.0)
    ep = dict(episodes[0])
    ep.update({"i0": 0, "i1": n - 1, "zone_low": 99.85, "zone_high": 100.15, "anchor_price": 100.0})
    b.high[2], b.low[2], b.close[2] = 100.2, 99.9, 100.0
    sigma = np.full(n, 0.01)
    touches = scan_episode(b.high, b.low, b.close, b.open, sigma, b.t0, ep, end_ms=b.t0 + n * PARENT.BAR_MS)
    assert touches[0]["side"] == -1
    assert touches[0]["touch_number"] == 1


def test_matched_episode_keeps_only_the_first_touch():
    real_id = "PDH:1:0"
    other_id = "PDH:2:20"
    population = {
        "episodes": [
            {"episode_id": real_id, "family": "DAY", "struct_side": 1},
            {"episode_id": other_id, "family": "WEEK", "struct_side": 1},
        ],
        "controls": [{
            "episode_id": f"CTRL:{real_id}:{other_id}", "shadow_id": real_id, "partner_id": other_id,
        }],
        "touches": [
            _touch(episode_id=real_id, touch_number=1, week=10),
            _touch(episode_id=real_id, touch_number=2, week=11),
            _touch(episode_id=other_id, touch_number=1, window_ok_48=False),
        ],
        "control_touches": [
            _touch(episode_id=f"CTRL:{real_id}:{other_id}", touch_number=1, week=10, side=-1),
        ],
    }
    counted = cohort.census(population)
    assert counted["matched_pairs"] == 1
    assert counted["pairs"][0]["episode_id"] == real_id
    assert counted["pairs"][0]["control_id"] == f"CTRL:{real_id}:{other_id}"
    assert counted["real_status"]["LEGITIMATE"] == 1
    assert counted["real_status"]["INCOMPLETE_4H"] == 1
    assert counted["pseudo_status"]["NO_CONTROL"] == 1


def test_barrier_aggregation_and_same_bar_ambiguity():
    cases = (("BREAK", "NEITHER", 1), ("REJECT", "NEITHER", 1), ("NEITHER", "BREAK", -1),
             ("BREAK", "REJECT", 0), ("NEITHER", "NEITHER", 0), ("REJECT", "BREAK", 0))
    for real, pseudo, diff in cases:
        assert inference.pair_diff(endpoint.resolved(real), endpoint.resolved(pseudo)) == diff
    high = np.full(10, 100.0)
    low = np.full(10, 100.0)
    zlo, zhi, x = 99.85, 100.15, 0.01
    high[3] = zhi * (1 + x) + 1
    low[3] = 100.0
    assert outcomes.classify(high, low, 1, 1, zlo, zhi, x, 4) == "BREAK"
    flat_h = np.full(10, 100.0)
    flat_l = np.full(10, 100.0)
    assert outcomes.classify(flat_h, flat_l, 1, 1, zlo, zhi, x, 4) == "NEITHER"
    assert inference.pair_diff(1, 0) == 1
    high[2] = zhi * (1 + x) + 1
    low[2] = zlo * (1 - x) - 1
    assert outcomes.classify(high, low, 1, 1, zlo, zhi, x, 4) == "AMBIGUOUS"
    assert endpoint.resolved("AMBIGUOUS") is None
    assert endpoint.resolved("BREAK") == 1 and endpoint.resolved("REJECT") == 1
    assert endpoint.resolved("NEITHER") == 0
    missing = flat_h.copy()
    missing_l = flat_l.copy()
    missing[2:6] = np.nan
    missing_l[2:6] = np.nan
    assert outcomes.classify(missing, missing_l, 1, 1, zlo, zhi, x, 4) is None
    short_h = np.full(6, 100.0)
    short_l = np.full(6, 100.0)
    assert outcomes.classify(short_h, short_l, 4, 1, zlo, zhi, x, 4) is None


def test_paired_estimator_bootstrap_and_slices():
    y_real = np.array([1.0, 0.0])
    y_pseudo = np.array([0.0, 1.0])
    same_week = inference.block_mean_draws(y_real - y_pseudo, np.array([7, 7]), np.random.default_rng(1), 40)
    assert np.all(same_week == 0.0)
    split = inference.block_mean_draws(y_real - y_pseudo, np.array([1, 2]), np.random.default_rng(2), 80)
    assert set(np.round(split, 6)).issubset({-1.0, 0.0, 1.0})
    pairs = [
        _pair(epoch="2017H2", week=1),
        _pair(epoch="2018", week=2),
        _pair(epoch="2019", week=3, family="WEEK", real_side=-1),
    ]
    estimated = analyze.estimate(
        pairs, ["BREAK", "NEITHER", "REJECT"], ["NEITHER", "BREAK", "NEITHER"],
        edges=(0.001, 0.003), columns=[], draws=30, seed=11,
    )
    assert estimated["primary"]["estimate"] == pytest.approx((1 - 1 + 1) / 3)
    assert estimated["n_analysis"] == 3
    assert estimated["discordant"]["real_only"] == 2
    assert estimated["discordant"]["pseudo_only"] == 1
    by_epoch = {row["name"]: row["estimate"] for row in estimated["epochs"]}
    assert by_epoch["2017H2"] == pytest.approx(1.0)
    assert by_epoch["2018"] == pytest.approx(-1.0)
    assert by_epoch["2019"] == pytest.approx(1.0)
    omitted = {row["name"]: row["estimate"] for row in estimated["leave_one_epoch_out"]}
    assert omitted["omit_2018"] == pytest.approx(1.0)
    ambiguous = analyze.estimate(
        pairs[:2], ["AMBIGUOUS", "REJECT"], ["NEITHER", "NEITHER"],
        edges=(0.001, 0.003), columns=[], draws=10, seed=3,
    )
    assert ambiguous["n_analysis"] == 1
    assert ambiguous["n_excluded_ambiguous"] == 1
    assert ambiguous["primary"]["estimate"] == pytest.approx(1.0)
    z_real = np.zeros((4, 0))
    z_pseudo = np.zeros((4, 0))
    y_r = np.array([1.0, 0.0, 1.0, 0.0])
    y_p = np.array([0.0, 0.0, 1.0, 1.0])
    assert inference.adjusted_from_z(y_r, y_p, z_real, z_pseudo, np.arange(4)) == pytest.approx(
        inference.mean_diff(y_r, y_p)
    )
    assert inference.adjusted_from_z(y_r, y_p, np.ones((4, 1)), np.zeros((4, 1)), np.arange(4)) is None


def test_evidence_labels_follow_the_frozen_order():
    loeo = [{"estimate": 0.04}, {"estimate": 0.05}, {"estimate": 0.03}]
    epochs = [{"n": 40, "estimate": 0.02}, {"n": 40, "estimate": 0.05}, {"n": 10, "estimate": -1.0}]
    primary = {"estimate": 0.04, "ci_low": 0.01, "ci_high": 0.08}
    clauses = claim.supporting_clauses(primary, epochs, loeo)
    assert claim.evidence_label(primary, clauses) == K.LABEL_REPLICATED
    unstable_epochs = [{"n": 40, "estimate": -0.02}, {"n": 40, "estimate": -0.01}, {"n": 40, "estimate": 0.05}]
    uclauses = claim.supporting_clauses(primary, unstable_epochs, loeo)
    assert claim.evidence_label(primary, uclauses) == K.LABEL_UNSTABLE
    narrow = {"estimate": 0.01, "ci_low": -0.005, "ci_high": 0.02}
    assert claim.evidence_label(narrow, claim.supporting_clauses(narrow, epochs, loeo)) == K.LABEL_NO_MATERIAL
    wide = {"estimate": 0.04, "ci_low": -0.01, "ci_high": 0.09}
    assert claim.evidence_label(wide, claim.supporting_clauses(wide, epochs, loeo)) == K.LABEL_LIMITED
    decision = claim.claim_decision(40, K.LABEL_REPLICATED)
    assert decision["claim_level"] == "L2"
    assert decision["product_integration_candidate"] == "YES"
    assert claim.claim_decision(40, K.LABEL_LIMITED)["product_integration_candidate"] == "NO"
    assert claim.claim_decision(10, K.LABEL_REPLICATED)["claim_status"] == "not_issued"


def test_renderer_has_no_trade_wording_and_evaluate_refuses_a_rerun(tmp_path, monkeypatch):
    result = {
        "mode": "CONFIRMATION", "design_sha": "abc", "evidence_label": K.LABEL_LIMITED,
        "supporting_clauses": {}, "primary": {"estimate": 0.01, "ci_low": -0.02, "ci_high": 0.05,
                                              "p_real": 0.8, "p_pseudo": 0.79},
        "n_analysis": 10, "n_matched_available": 12, "weeks": 4,
        "n_ambiguous_real": 1, "n_ambiguous_pseudo": 1, "n_excluded_ambiguous": 2,
        "n_excluded_unclassified": 0,
        "discordant": {"both_resolved": 1, "both_neither": 1, "real_only": 1, "pseudo_only": 1},
        "adjusted": {"estimate": 0.01, "ci_low": -0.02, "ci_high": 0.04, "status": "ok", "columns": []},
        "decomposition": {name: {"estimate": 0.0, "ci_low": -0.1, "ci_high": 0.1, "p_real": 0.5, "p_pseudo": 0.5}
                          for name in ("BREAK", "REJECT", "NEITHER")},
        "epochs": [{"name": "2018", "n": 10, "estimate": 0.01, "ci_low": -0.1, "ci_high": 0.1,
                    "p_real": 0.5, "p_pseudo": 0.5}],
        "families": [], "sides": [], "leave_one_epoch_out": [],
        "claim_level": "not_issued", "claim_status": "not_issued",
        "replicated_historical_mechanism": False, "product_integration_candidate": "NO",
        "bootstrap": {"draws": 10, "seed": 1}, "search_cells": 16,
        "dataset": {"dataset_id": K.SURFACE_ID, "days": "2017-08-01..2019-12-31", "canonical_sha256": "abc"},
        "event_window": [K.EVENT_START, K.EVENT_END], "exposure_status": K.EXPOSURE_STATUS,
    }
    text = report.render(result)
    for phrase in ("support means buy", "resistance means sell", "the level is strong",
                   "the level holds", "will break", "chance of a move", "PASS"):
        assert phrase not in text
    monkeypatch.setattr(evaluate, "RESULT_JSON", tmp_path / "r.json")
    monkeypatch.setattr(evaluate, "RESULT_MD", tmp_path / "r.md")
    (tmp_path / "r.json").write_text("{}")
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        evaluate.main()


def test_preflight_modules_do_not_import_outcomes():
    for name in ("preflight.py", "cohort.py", "data.py", "constants.py", "inference.py", "endpoint.py", "claim.py"):
        tree = ast.parse((PKG / name).read_text())
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
        assert not any("outcomes" in module for module in modules)
        assert not any(module.endswith(".analyze") for module in modules)
