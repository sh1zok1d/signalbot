"""DIVERGENCE_PANEL_FEASIBILITY_V0. Offline, synthetic layouts only; no market data, no outcome."""
import json
import hashlib
from pathlib import Path

import numpy as np
import pytest

from scripts.research import divergence_panel_feasibility_v0 as P
from scripts.research import seed0001_regular_divergence_lib as L

REPO = Path(__file__).resolve().parents[2]
H = L.BAR_MS
T0 = L.WEEK_ANCHOR_MS


def _eps(n_days=400, per_day=2, seed=0, simultaneous=False):
    rng = np.random.default_rng(seed)
    eps = []
    for d in range(n_days):
        arms = rng.choice(list("ABCD"), size=per_day, p=[0.15, 0.35, 0.15, 0.35])
        for j in range(per_day):
            t = T0 + d * 86_400_000 + int(rng.integers(0, 20)) * H
            syms = P.PANEL if simultaneous else (P.PANEL[int(rng.integers(0, 6))],)
            for s in syms:
                eps.append({"ARM": str(arms[j]), "SYMBOL": s, "DECISION_TIME_MS": t,
                            "WEEK_BLOCK": int(L.week_block(t)), "EPOCH": L.half_year_epoch(t)})
    return eps


def test_spend_window_is_85_weeks_and_stays_clear_of_e1():
    assert P.spend_weeks() == 85
    assert P.spend_window_respects_e1()
    assert P.ms(P.SPEND_LAST_DECISION_UTC) + 96 * H <= P.ms(P.E1_HOLDOUT_UTC[0]) - 86_400_000


def test_null_size_and_power_increase():
    eps = _eps()
    cols = P._cols(eps)
    null = P.simulate(*cols, 0.0, P.PROFILES["INDEPENDENT"], reps=3000, seed=1)["POWER_INTERACTION"]
    assert null < 0.045                       # one-sided rejection share of a two-sided 0.05 test ~ 0.025
    big = P.simulate(*cols, 0.35, P.PROFILES["INDEPENDENT"], reps=500, seed=2)["POWER_INTERACTION"]
    assert big > 0.9


def test_simultaneous_cross_symbol_copies_are_not_independent_under_stress():
    one = _eps(n_days=150, simultaneous=False, seed=3)
    six = _eps(n_days=150, simultaneous=True, seed=3)
    ind_six = P.simulate(*P._cols(six), 0.15, P.PROFILES["INDEPENDENT"], reps=600, seed=4)["POWER_INTERACTION"]
    stress_six = P.simulate(*P._cols(six), 0.15, P.PROFILES["STRESS"], reps=600, seed=4)["POWER_INTERACTION"]
    collapsed = P.simulate(*P._cols(P.collapse(six)), 0.15, P.COLLAPSED_PROFILE, reps=600, seed=4)["POWER_INTERACTION"]
    assert stress_six < ind_six - 0.2          # counting simultaneous copies as independent inflates power
    assert collapsed < ind_six - 0.2
    assert len(P.collapse(six)) <= len({(P.date_key(e), e["ARM"]) for e in six})
    assert len(one) < len(six)


def test_cross_symbol_overlap_counts_same_hour_and_window():
    t = T0 + 100 * H
    eps = [{"ARM": "A", "SYMBOL": "BTCUSDT", "DECISION_TIME_MS": t},
           {"ARM": "A", "SYMBOL": "ETHUSDT", "DECISION_TIME_MS": t},
           {"ARM": "B", "SYMBOL": "SOLUSDT", "DECISION_TIME_MS": t + 5 * H},
           {"ARM": "A", "SYMBOL": "XRPUSDT", "DECISION_TIME_MS": t + 30 * H}]
    o = P.cross_symbol_overlap(eps)
    assert o["A_WITH_OTHER_SYMBOL_SAME_ARM_WITHIN_0H"]["COUNT"] == 2
    assert o["A_WITH_OTHER_SYMBOL_ANY_ARM_WITHIN_6H"]["COUNT"] == 2
    assert o["A_WITH_OTHER_SYMBOL_SAME_ARM_WITHIN_24H"]["COUNT"] == 2
    assert o["A_WITH_OTHER_SYMBOL_ANY_ARM_WITHIN_24H"]["COUNT"] == 2


def test_verdict_order():
    ok = {"MIN_A_WEEK_CLUSTERS": 40, "MIN_C_WEEK_CLUSTERS": 40}
    assert P.verdict(False, ok, 0.2, 0.9)[0] == "DATA_BLOCKED"
    assert P.verdict(True, {"MIN_A_WEEK_CLUSTERS": 29, "MIN_C_WEEK_CLUSTERS": 40}, 0.2, 0.9)[0] == "INFERENCE_SUPPORT_INSUFFICIENT"
    assert P.verdict(True, ok, 0.6, 0.9)[0] == "STRUCTURAL_INFERENCE_RISK"
    assert P.verdict(True, ok, 0.2, 0.79)[0] == "INFORMATIONALLY_WEAK"
    assert P.verdict(True, ok, 0.2, 0.80)[0] == "FEASIBLE_FOR_PREREGISTRATION"


def test_projected_layouts_have_spend_window_length():
    eps = _eps(n_days=720)
    lay = P.projected_layouts(eps)
    for part in lay.values():
        weeks = {e["WEEK_BLOCK"] for e in part}
        assert max(weeks) - min(weeks) + 1 <= P.spend_weeks()


def test_design_binds_code_and_frozen_rules():
    design = json.loads((REPO / P.DESIGN_REL).read_text())
    for rel, digest in design["CODE_IDENTITY"].items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
    rule = design["FROZEN_RULES"]
    assert rule["MIN_EFFECT_OF_INTEREST"] == P.MIN_EFFECT == 0.15
    assert rule["GATE_PROFILE"] == P.GATE_PROFILE == "STRESS"
    assert rule["TARGET_POWER"] == P.TARGET_POWER == 0.80
    assert rule["PANEL"] == list(P.PANEL)
    assert design["PRIMARY_ESTIMAND"] == "(A - B) - (C - D)"
    assert design["BOUNDARY"]["PROTECTED_2025_2026_OPENED"] is False
