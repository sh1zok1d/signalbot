"""DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1. Offline, synthetic layouts only; no market data, no outcome."""
import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.research import divergence_conditional_support_feasibility_v1 as V1
from scripts.research import divergence_panel_feasibility_v0 as V0
from scripts.research import seed0001_regular_divergence_lib as L

REPO = Path(__file__).resolve().parents[2]
T0 = L.WEEK_ANCHOR_MS


def _eps(n_weeks=60, per_week=20, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for w in range(n_weeks):
        for _ in range(per_week):
            t = T0 + w * L.WEEK_MS + int(rng.integers(0, 7 * 24)) * L.BAR_MS
            out.append({"ARM": str(rng.choice(list("ABCD"), p=[0.05, 0.3, 0.1, 0.55])),
                        "SYMBOL": V0.PANEL[int(rng.integers(0, 6))], "DECISION_TIME_MS": t,
                        "WEEK_BLOCK": int(L.week_block(t)), "EPOCH": L.half_year_epoch(t)})
    return out


def test_primary_is_a_minus_b_and_null_is_controlled():
    eps = _eps()
    null = V1.simulate(*V1.cols(eps), 0.0, V1.PROFILES["INDEPENDENT"], reps=3000, seed=1)
    assert null["POWER_A_MINUS_B"] < 0.045
    big = V1.simulate(*V1.cols(eps), 0.35, V1.PROFILES["STRESS"], reps=500, seed=2)
    assert big["POWER_A_MINUS_B"] > big["POWER_INTERACTION"]      # the two-cell contrast is more informative


def test_continuation_never_shares_clusters_or_dates_with_the_proxy():
    eps = _eps()
    lo, hi = V1.week_span(eps)
    pros = V1.continuation(eps, lo + 10, 30)
    assert {e["WEEK_BLOCK"] for e in pros}.isdisjoint({e["WEEK_BLOCK"] for e in eps})
    assert {V0.date_key(e) for e in pros}.isdisjoint({V0.date_key(e) for e in eps})
    assert len({e["WEEK_BLOCK"] for e in pros}) <= 30
    no_btc = V1.continuation(eps, lo, 30, exclude_symbols=("BTCUSDT",))
    assert all(e["SYMBOL"] != "BTCUSDT" for e in no_btc)


def test_more_prospective_weeks_raise_power():
    eps = _eps(n_weeks=40)
    lo, _ = V1.week_span(eps)
    p0 = V1.simulate(*V1.cols(eps), 0.15, V1.PROFILES["STRESS"], reps=1500, seed=3)["POWER_A_MINUS_B"]
    more = eps + V1.continuation(eps, lo, 80)
    p1 = V1.simulate(*V1.cols(more), 0.15, V1.PROFILES["STRESS"], reps=1500, seed=3)["POWER_A_MINUS_B"]
    assert p1 > p0 + 0.1


def test_stopping_rule_takes_the_more_demanding_proxy():
    found = [{"FIRST_PASS": {"PROSPECTIVE_WEEKS": 20, "TOTAL": {"A_EPISODES": 170, "A_WEEK_CLUSTERS": 70}}},
             {"FIRST_PASS": {"PROSPECTIVE_WEEKS": 28, "TOTAL": {"A_EPISODES": 165, "A_WEEK_CLUSTERS": 74}}}]
    rule = V1.stopping_rule(found)
    assert rule["EXPECTED_PROSPECTIVE_WEEKS"] == 28
    assert rule["CUMULATIVE_A_EPISODES"] == 170 and rule["CUMULATIVE_A_WEEK_CLUSTERS"] == 74
    assert rule["DEADLINE_UTC"] > rule["EXPECTED_STOP_DATE_UTC"]
    assert V1.stopping_rule([{"FIRST_PASS": None}]) is None


def test_prospective_reads_and_spend_window_avoid_e1():
    assert V0.ms(V1.PROSPECTIVE_READS_NOT_BEFORE_UTC) > V0.ms(V0.E1_HOLDOUT_UTC[1])
    assert V0.ms(V1.PROSPECTIVE_START_UTC) >= V0.ms("2026-10-05T00:00:00Z")
    assert V0.spend_window_respects_e1()


def test_design_binds_code_and_frozen_rules():
    design = json.loads((REPO / V1.DESIGN_REL).read_text())
    for rel, digest in design["CODE_IDENTITY"].items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
    rule = design["FROZEN_RULES"]
    assert design["PRIMARY_ESTIMAND"] == "A - B" and design["SECONDARY_ESTIMAND"] == "(A - B) - (C - D)"
    assert rule["MIN_EFFECT_OF_INTEREST"] == V1.MIN_EFFECT == 0.15
    assert rule["GATE_PROFILE"] == V1.GATE_PROFILE == "STRESS" and rule["GATE_REPS"] == V1.GATE_REPS == 10_000
    assert design["V0_VERDICT_UNCHANGED"] == "INFORMATIONALLY_WEAK"
    assert design["BOUNDARY"]["PROTECTED_2025_2026_OPENED"] is False and design["BOUNDARY"]["SEED0003_CREATED"] is False
