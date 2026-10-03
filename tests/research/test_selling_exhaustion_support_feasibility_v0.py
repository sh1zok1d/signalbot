"""SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0. Offline; synthetic data only; no market byte, no outcome."""
import hashlib
import inspect
import json
import math
from pathlib import Path

import numpy as np
import pytest

from scripts.research import divergence_full_history_v0_lib as F
from scripts.research import seed0001_regular_divergence_lib as L
from scripts.research import selling_exhaustion_support_feasibility_v0 as RUN
from scripts.research import selling_exhaustion_support_feasibility_v0_lib as S

REPO = Path(__file__).resolve().parents[2]
H = L.BAR_MS
T0 = F.ms("2024-03-01T00:00:00Z")
SYMS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT")


def _bars(n: int = 900, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    vol = rng.uniform(50.0, 150.0, n)
    return {"open_time_ms": T0 + np.arange(n, dtype=np.int64) * H, "volume": vol,
            "taker_buy": vol * rng.uniform(0.35, 0.65, n), "close": 100.0 + rng.standard_normal(n).cumsum(),
            "low": np.full(n, 90.0), "high": np.full(n, 110.0), "complete": np.ones(n, dtype=bool)}


def _ep(bars: dict, i: int = 800, j: int = 780) -> dict:
    t = int(bars["open_time_ms"][i + L.PIVOT_RIGHT]) + H
    return {"PIVOT_BAR_OPEN_UTC": L.iso_utc(int(bars["open_time_ms"][i])),
            "COMPARISON_PIVOT_OPEN_UTC": L.iso_utc(int(bars["open_time_ms"][j])), "DECISION_TIME_MS": t}


def _oi(bars: dict, slope: float) -> dict:
    t = np.arange(int(bars["open_time_ms"][0]), int(bars["open_time_ms"][-1]) + 2 * H, 5 * 60_000, dtype=np.int64)
    return {"available_ms": t + 5 * 60_000, "value": 1000.0 + slope * (t - t[0]) / H}


# ------------------------------------------------------------- boundaries

def test_surface_ends_at_the_e1_safe_cutoffs():
    assert L.iso_utc(RUN.FIRST_DECISION_MS) == "2023-01-01T00:00:00Z"
    assert L.iso_utc(RUN.LAST_DECISION_MS) == "2026-08-11T00:00:00Z"
    assert L.iso_utc(F.READ_HORIZON_MS) == "2026-08-15T00:00:00Z"
    assert RUN.LAST_DECISION_MS + L.PRIMARY_CAP_HOURS * H < F.E1_HOLDOUT_START_MS


def test_state_blind_outcome_records_carry_no_state_and_skip_gap_decisions():
    params = list(inspect.signature(RUN.state_blind_outcomes).parameters)
    assert params == ["minutes", "support", "symbol"]
    t = F.ms("2024-06-03T00:00:00Z")
    minutes = {"t": t + np.arange(49 * 60, dtype=np.int64) * 60_000, "high": np.full(49 * 60, 101.0),
               "low": np.full(49 * 60, 99.5), "close": np.full(49 * 60, 100.0)}
    ep = {"DECISION_TIME_MS": t, "ENTRY_REF_PRICE": 100.0, "STOP_PRICE": 99.0, "WEEK_BLOCK": 74, "SE_LEG": 1}
    gap = {**ep, "DECISION_TIME_MS": F.ms("2024-12-30T00:00:00Z")}
    recs = RUN.state_blind_outcomes(minutes, [ep, gap], "BTCUSDT")
    assert len(recs) == 1
    assert set(recs[0]) == {"Y", "SYMBOL", "DECISION_TIME_MS", "WEEK_BLOCK"}
    params = list(inspect.signature(RUN.outcome_dependence).parameters)
    assert params == ["blind"]


# ----------------------------------------------------------------- states

def test_leg_inputs_equal_the_prespecified_full_history_features():
    bars = _bars()
    oi = _oi(bars, -0.5)
    ep = _ep(bars)
    x = S.state_inputs(bars, oi, ep)
    n = bars["volume"].size
    ind = {k: np.zeros(n) for k in ("rsi14", "rsi21", "macd")} | {"atr": np.ones(n)}
    full = {**ep, "DECLINE_ATR": 4.0, "SUPPORT_MAX_IMBALANCE": 0.2, "SUPPORT_TRAILING_Q80": 0.1, "NETFLOW24": 0.0,
            "RV24": 0.01}
    f = F.episode_features(bars, ind, np.zeros(n), np.zeros(n), oi, {"BTCUSDT": {}}, full)
    assert x["LEG_FLOW_CHANGE"] == f["SELL_PRESSURE_CHANGE"]
    assert x["LEG_OI_CHANGE"] == f["OI_CHG_LEG"]
    flags = S.state_flags(x)
    assert flags["SE_LEG"] == F.deeper_state_flow_oi(f)


def test_state_rules_use_no_change_thresholds_and_flag_missing_inputs():
    base = {"LEG_FLOW_CHANGE": 0.01, "LEG_OI_CHANGE": 0.0, "APPROACH_FLOW_EXCESS": 0.0, "APPROACH_OI_CHANGE": -0.02}
    flags = S.state_flags(base)
    assert flags == {"SE_LEG": 1, "SE_BASELINE": 0}          # OI change 0 counts as not expanding; flow 0 is not weaker
    assert S.state_flags({**base, "LEG_OI_CHANGE": 1e-9})["SE_LEG"] == 0
    assert S.state_flags({**base, "LEG_OI_CHANGE": float("nan")})["SE_LEG"] is None
    assert S.state_flags({**base, "APPROACH_FLOW_EXCESS": 1e-9})["SE_BASELINE"] == 1


def test_selling_weakening_and_oi_contraction_are_detected():
    bars = _bars()
    i, j = 800, 780
    gap = i - j
    bars["taker_buy"][j - gap + 1:j + 1] = 0.30 * bars["volume"][j - gap + 1:j + 1]   # heavy selling, first leg
    bars["taker_buy"][j + 1:i + 1] = 0.48 * bars["volume"][j + 1:i + 1]               # lighter selling, second leg
    x = S.state_inputs(bars, _oi(bars, -0.5), _ep(bars, i, j))
    assert x["LEG_FLOW_CHANGE"] > 0 and x["LEG_OI_CHANGE"] < 0
    assert S.state_flags(x)["SE_LEG"] == 1
    y = S.state_inputs(bars, _oi(bars, +0.5), _ep(bars, i, j))
    assert y["LEG_OI_CHANGE"] > 0 and S.state_flags(y)["SE_LEG"] == 0


def test_inputs_read_only_bars_i_minus_719_through_i():
    bars = _bars()
    ep = _ep(bars)
    oi = _oi(bars, -0.1)
    ref = S.state_inputs(bars, oi, ep)
    b2 = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in bars.items()}
    b2["volume"][801:] *= 7.0
    b2["taker_buy"][801:] *= 0.1
    b2["volume"][:800 - 720 + 1] *= 5.0
    assert S.state_inputs(b2, oi, ep) == ref
    b3 = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in bars.items()}
    b3["taker_buy"][800 - 719:500] = 0.0                 # inside the baseline span
    assert S.state_inputs(b3, oi, ep)["APPROACH_FLOW_BASELINE"] != ref["APPROACH_FLOW_BASELINE"]


def test_inputs_are_identical_when_data_end_at_the_decision_time():
    bars = _bars(seed=3)
    ep = _ep(bars)
    oi = _oi(bars, 0.2)
    keep = bars["open_time_ms"] + H <= ep["DECISION_TIME_MS"]
    tb = {k: v[keep] for k, v in bars.items()}
    ko = oi["available_ms"] <= ep["DECISION_TIME_MS"]
    toi = {"available_ms": oi["available_ms"][ko], "value": oi["value"][ko]}
    assert RUN._same(S.state_inputs(tb, toi, ep), S.state_inputs(bars, oi, ep))


def test_oi_is_read_as_of_the_close_of_the_pivot_bar():
    bars = _bars()
    ep = _ep(bars)
    oi = _oi(bars, -0.3)
    ref = S.state_inputs(bars, oi, ep)
    at_i = int(bars["open_time_ms"][800]) + H
    later = oi["available_ms"] > at_i
    oi2 = {"available_ms": oi["available_ms"], "value": np.where(later, 9e9, oi["value"])}
    assert S.state_inputs(bars, oi2, ep) == ref


def test_score_is_robust_scaled_clipped_and_sign_flips_oi():
    rows = [{"SYMBOL": "BTCUSDT", "LEG_FLOW_CHANGE": float(k), "LEG_OI_CHANGE": float(-k)} for k in range(-5, 6)]
    c = S.robust_constants(rows, "SE_LEG")
    assert c["BTCUSDT"]["LEG_FLOW_CHANGE"]["MEDIAN"] == 0.0
    hi = S.score({"SYMBOL": "BTCUSDT", "LEG_FLOW_CHANGE": 1e6, "LEG_OI_CHANGE": -1e6}, "SE_LEG", c)
    assert hi == pytest.approx(S.SCORE_CLIP)
    mid = S.score({"SYMBOL": "BTCUSDT", "LEG_FLOW_CHANGE": 0.0, "LEG_OI_CHANGE": 0.0}, "SE_LEG", c)
    assert mid == 0.0
    assert math.isnan(S.score({"SYMBOL": "BTCUSDT", "LEG_FLOW_CHANGE": float("nan"), "LEG_OI_CHANGE": 0.0}, "SE_LEG", c))


# -------------------------------------------------------------- dependence

def _layout_rows(n_weeks=60, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for w in range(n_weeks):
        for _ in range(int(rng.integers(6, 14))):
            rows.append({"SYMBOL": SYMS[int(rng.integers(6))], "WEEK_BLOCK": w, "EPOCH": "X",
                         "DECISION_TIME_MS": L.WEEK_ANCHOR_MS + w * L.WEEK_MS + int(rng.integers(0, 168)) * H,
                         "ST": int(rng.random() < 0.3)})
    return rows


def test_pair_class_phi_matches_brute_force():
    rng = np.random.default_rng(5)
    rows = _layout_rows(12, seed=5)
    y = rng.integers(0, 2, len(rows)).astype(float)
    sym = [r["SYMBOL"] for r in rows]
    t = [r["DECISION_TIME_MS"] for r in rows]
    wk = [r["WEEK_BLOCK"] for r in rows]
    chains = S.symbol_chains(sym, t)
    pw, wi = S.outcome_pair_stats(y, sym, t, wk)
    phi = S.phi_from_pairs(pw, y, wi)
    ybar = y.mean()
    acc = {k: [0.0, 0] for k in S.PAIR_CLASSES}
    for a in range(len(rows)):
        for b in range(a + 1, len(rows)):
            if wk[a] != wk[b]:
                continue
            da, db = S.date_key(t[a]), S.date_key(t[b])
            prod = (y[a] - ybar) * (y[b] - ybar)
            if da != db and sym[a] != sym[b]:
                acc["WEEK_OTHER_DATE_OTHER_SYMBOL"][0] += prod; acc["WEEK_OTHER_DATE_OTHER_SYMBOL"][1] += 1
            if da == db and sym[a] != sym[b]:
                acc["DATE_OTHER_SYMBOL"][0] += prod; acc["DATE_OTHER_SYMBOL"][1] += 1
            if chains[a] == chains[b] and da != db:
                acc["SYMBOL_CHAIN_OTHER_DATE_SAME_WEEK"][0] += prod; acc["SYMBOL_CHAIN_OTHER_DATE_SAME_WEEK"][1] += 1
    for k, (s, c) in acc.items():
        if c:
            assert phi[k] == pytest.approx(s / (c * ybar * (1 - ybar)))
            assert phi[k + "_PAIRS"] == c


def test_latent_profile_inverts_the_arcsine_link_and_floors():
    rho = {"WEEK_OTHER_DATE_OTHER_SYMBOL": 0.05, "DATE_OTHER_SYMBOL": 0.15, "SYMBOL_CHAIN_OTHER_DATE_SAME_WEEK": 0.30}
    phi = {k: 2 / math.pi * math.asin(v) for k, v in rho.items()}
    prof = S.latent_profile(phi)
    assert prof["LATENT_CORR"]["WEEK"] == pytest.approx(0.05)
    assert prof["LATENT_CORR"]["DATE"] == pytest.approx(0.10)
    assert prof["LATENT_CORR"]["CHAIN"] == pytest.approx(0.25)
    v = 1 + prof["WEEK"] + prof["DATE"] + prof["CHAIN"]
    assert prof["DATE"] / v == pytest.approx(0.10)
    neg = S.latent_profile({k: -0.1 for k in S.PAIR_CLASSES})
    assert neg["WEEK"] == neg["DATE"] == neg["CHAIN"] == 0.0


def test_layout_stats_count_states_and_concentration():
    rows = [{**r, "SE": r["ST"]} for r in _layout_rows()]
    st = S.state_layout_stats(rows, "SE")
    assert st["E"]["EPISODES"] + st["S"]["EPISODES"] == len(rows)
    assert 0 < st["PREVALENCE_E_AMONG_DEFINED_SUPPORT"] < 1
    assert st["E"]["WEEK_CLUSTERS"] <= 60 and st["E"]["MAX_SYMBOL_SHARE"] <= 1


# -------------------------------------------------------------- simulation

def test_simulator_is_sized_and_powered_monotonically():
    rows = _layout_rows(120, seed=2)
    lay = S.layout_arrays(rows, "ST")
    x = lay["STATE"].astype(float)
    for prof in ({}, S.PROFILES["STRESS"], {"WEEK": 0.05, "DATE": 0.1, "CHAIN": 0.3}):
        null = S.simulate(lay, p=S.step_probabilities(lay["STATE"], 0.0), regressors={"B": x}, profile=prof,
                          reps=3000, seed=11)["B"]
        assert 0.012 < null["POWER"] < 0.042
        lo = S.simulate(lay, p=S.step_probabilities(lay["STATE"], 0.03), regressors={"B": x}, profile=prof,
                        reps=1500, seed=12)["B"]["POWER"]
        hi = S.simulate(lay, p=S.step_probabilities(lay["STATE"], 0.12), regressors={"B": x}, profile=prof,
                        reps=1500, seed=13)["B"]["POWER"]
        assert hi > lo


def test_linear_probabilities_imply_the_requested_rate_gap():
    rng = np.random.default_rng(4)
    state = (rng.random(4000) < 0.3).astype(int)
    z = S.standardize(rng.standard_normal(4000) + 0.9 * state)
    p, clipped = S.linear_probabilities(state, z, 0.05)
    assert clipped == 0.0
    assert p[state == 1].mean() - p[state == 0].mean() == pytest.approx(0.05)


def test_weeks_projection_and_prospective_rows():
    assert S.weeks_for_power(100, 0.01, S.Z80 * 0.01) == pytest.approx(100)
    assert S.weeks_for_power(100, 0.01, S.Z80 * 0.02) == pytest.approx(25)
    assert S.weeks_for_power(100, 0.01, 0.0) == float("inf")
    rows = [{**r, "SE": r["ST"]} for r in _layout_rows(10)]
    pros = S.prospective_rows(rows, 25)
    assert {r["WEEK_BLOCK"] for r in pros} <= set(range(1_000_000, 1_000_025))
    assert len(pros) == 2 * len(rows) + sum(r["WEEK_BLOCK"] < 5 for r in rows)


def test_verdict_follows_the_frozen_rule():
    def var(stress, base, emp, ok=True):
        return {"SUPPORT_OK": ok, "WEEKS_FOR_80": {"STRESS": {"0.05": stress}, "BASE": {"0.05": base},
                                                   "EMPIRICAL": {"0.05": emp}}}
    assert S.verdict({"A": var(90, 50, 60)}, data_ok=True, pit_ok=True)["STATUS"] == "FEASIBLE_FOR_PREREGISTRATION"
    weak = S.verdict({"A": var(300, 90, 400)}, data_ok=True, pit_ok=True)
    assert weak == {"STATUS": "INFORMATIONALLY_WEAK", "REASONS": ["FEASIBLE_ONLY_UNDER_WEAKER_DEPENDENCE"]}
    none = S.verdict({"A": var(900, 500, 600)}, data_ok=True, pit_ok=True)
    assert none["REASONS"] == ["NOT_TESTABLE_WITHIN_REALISTIC_HORIZON"]
    assert S.verdict({"A": var(10, 10, 10, ok=False)}, data_ok=True, pit_ok=True)["STATUS"] == "INFERENCE_SUPPORT_INSUFFICIENT"
    assert S.verdict({"A": var(10, 10, 10)}, data_ok=True, pit_ok=False)["STATUS"] == "PIT_BLOCKED"


def test_json_sanitizer_drops_non_finite_values():
    out = RUN.finite_or_none({"a": float("inf"), "b": [np.float64("nan"), np.int64(3)], "c": np.bool_(True)})
    assert out == {"a": None, "b": [None, 3], "c": True}
    json.dumps(out, allow_nan=False)


# ------------------------------------------------------------------ design

def test_design_binds_code_and_frozen_artifacts():
    dsg = json.loads((REPO / RUN.DESIGN_REL).read_text())
    assert dsg["UNIT"] == "SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0"
    assert dsg["STATUS"] == "FROZEN_BEFORE_STATE_COUNTS"
    for rel, digest in {**dsg["CODE_IDENTITY"], **dsg["FROZEN_ARTIFACTS"]}.items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
    assert dsg["CANDIDATE_STATES"]["VARIANTS"].keys() == set(S.VARIANTS)
    assert dsg["EFFECTS"]["REPORTED"] == list(S.REPORTED_EFFECTS)
    assert dsg["VERDICT_RULE"]["REALISTIC_HORIZON_WEEKS"] == S.REALISTIC_HORIZON_WEEKS
    assert dsg["SURFACE"]["LAST_DECISION_UTC"] == "2026-08-11T00:00:00Z"
