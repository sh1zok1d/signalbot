"""DIVERGENCE_FULL_HISTORY_RESEARCH_V0. Offline, synthetic data only; no market byte, no outcome."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from scripts.research import divergence_full_history_v0 as RUN
from scripts.research import divergence_full_history_v0_lib as F
from scripts.research import seed0001_exploratory_outcomes as X
from scripts.research import seed0001_regular_divergence_lib as L

REPO = Path(__file__).resolve().parents[2]
H = L.BAR_MS


# ------------------------------------------------------------- boundaries

def test_e1_safe_cutoffs_are_derived_mechanically():
    assert L.iso_utc(F.VALIDATION_LAST_DECISION_MS) == "2026-08-11T00:00:00Z"
    assert L.iso_utc(F.READ_HORIZON_MS) == "2026-08-15T00:00:00Z"
    assert F.READ_HORIZON_MS + F.E1_MARGIN_HOURS * H == F.E1_HOLDOUT_START_MS
    assert F.VALIDATION_LAST_DECISION_MS + F.MAX_FORWARD_HOURS * H <= F.E1_HOLDOUT_START_MS - 24 * H
    F.assert_read_allowed(0, F.READ_HORIZON_MS)
    with pytest.raises(F.E1BoundaryError):
        F.assert_read_allowed(0, F.READ_HORIZON_MS + 1)


def test_url_guard_never_requests_the_e1_month_or_days_after_the_horizon():
    RUN.assert_url_allowed(RUN.urls("KLINES_1M", "BTCUSDT", "2026-07"))
    RUN.assert_url_allowed(RUN.urls("KLINES_1M_DAILY", "BTCUSDT", "2026-08-14"))
    RUN.assert_url_allowed(RUN.urls("BOOKDEPTH", "SOLUSDT", "2025-01-01"))
    RUN.assert_url_allowed(RUN.urls("METRICS", "XRPUSDT", "2022-11-01"))
    for bad in (RUN.urls("KLINES_1M", "BTCUSDT", "2026-08"), RUN.urls("KLINES_1M_DAILY", "BTCUSDT", "2026-08-15"),
                RUN.urls("BOOKDEPTH", "BTCUSDT", "2026-08-20"), RUN.urls("METRICS", "BTCUSDT", "2026-09-01"),
                RUN.ARCHIVE + "/x.zip"):
        with pytest.raises(RUN.ProtectedAccessError):
            RUN.assert_url_allowed(bad)
    assert RUN.MONTHS_NEW[-1] == "2026-07" and RUN.DAILY_KLINE_DAYS[-1] == "2026-08-14"
    assert RUN.new_book_days()[-1] == "2026-08-14" and RUN.metrics_days()[-1] == "2026-08-14"


def test_slices_are_disjoint_and_skip_the_year_end_gap():
    assert F.slice_of(F.ms("2024-12-28T00:00:00Z")) == "DISCOVERY"
    assert F.slice_of(F.ms("2024-12-30T00:00:00Z")) is None
    assert F.slice_of(F.ms("2025-01-01T00:00:00Z")) == "VALIDATION"
    assert F.slice_of(F.ms("2026-08-11T01:00:00Z")) is None


def test_detector_guard_is_substituted_only_inside_the_scope():
    before = L.PROTECTED_START_MS
    with RUN.e1_safe_detector_guard():
        assert L.PROTECTED_START_MS == F.E1_HOLDOUT_START_MS
    assert L.PROTECTED_START_MS == before
    with pytest.raises(RuntimeError):
        with RUN.e1_safe_detector_guard():
            raise RuntimeError("boom")
    assert L.PROTECTED_START_MS == before


# ---------------------------------------------------------------- outcomes

T0 = F.ms("2024-06-03T00:00:00Z")


def _minutes(n, base=100.0):
    t = T0 + np.arange(n, dtype=np.int64) * F.MINUTE_MS
    return {"t": t, "high": np.full(n, base + 0.5), "low": np.full(n, base - 0.5), "close": np.full(n, base)}


def _ep(entry=100.0, stop=98.0):
    return {"EPISODE_ID": "X", "DECISION_TIME_MS": T0, "ENTRY_REF_PRICE": entry, "STOP_PRICE": stop}


def test_outcomes_match_the_seed0001_evaluator_and_add_timing_and_net_r():
    rng = np.random.default_rng(1)
    for _ in range(20):
        m = _minutes(96 * 60 + 5)
        walk = np.cumsum(rng.normal(0, 0.15, m["t"].size))
        m["close"] = 100 + walk
        m["high"] = m["close"] + rng.uniform(0, 0.3, m["t"].size)
        m["low"] = m["close"] - rng.uniform(0, 0.3, m["t"].size)
        ep = _ep(stop=100 - float(rng.uniform(0.5, 3)))
        mine, ref = F.episode_outcomes(m, ep), X.episode_outcomes(m, ep)
        for k, v in ref.items():
            if k in ("EPISODE_ID",):
                continue
            assert mine[k] == pytest.approx(v) if isinstance(v, float) else mine[k] == v, k
        for k in (1, 2):
            for cap in (48, 96):
                wln = mine[f"Y{k}_{cap}H_WLN"]
                gross = k if wln == "WIN" else -1 if wln == "LOSS" else mine[f"FWD_R_{cap}H"]
                assert mine[f"NET_R{k}_{cap}H"] == pytest.approx(gross - mine["COST_R"])


def test_timing_fields():
    m = _minutes(96 * 60)
    m["high"][120] = 102.5      # +1R at minute 120 (2h); also the 48h MFE
    m["low"][600] = 97.0        # stop at minute 600 (10h)
    out = F.episode_outcomes(m, _ep())
    assert out["T_HIT_P1R_H"] == pytest.approx(2.0) and out["T_HIT_M1R_H"] == pytest.approx(10.0)
    assert out["T_MFE_H_48H"] == pytest.approx(2.0) and out["T_MAE_H_48H"] == pytest.approx(10.0)
    assert out["COST_R"] == pytest.approx(0.0010 * 100 / 2)


def test_outcome_windows_never_cross_the_read_horizon():
    t = np.array([F.READ_HORIZON_MS - 60 * F.MINUTE_MS], dtype=np.int64)
    with pytest.raises(F.E1BoundaryError):
        F.window_slice(t, F.READ_HORIZON_MS - 47 * H, 48)


# ---------------------------------------------------------------- features

def _synthetic_symbol(n=2400, seed=5):
    rng = np.random.default_rng(seed)
    close = 1000 + np.cumsum(rng.normal(0, 1.0, n))
    open_ = np.r_[close[0], close[:-1]]
    bars = {"open_time_ms": F.ms("2024-01-01T00:00:00Z") + np.arange(n, dtype=np.int64) * H,
            "open": open_, "high": np.maximum(open_, close) + rng.uniform(0.1, 0.5, n),
            "low": np.minimum(open_, close) - rng.uniform(0.1, 0.5, n), "close": close,
            "volume": rng.uniform(80, 120, n), "taker_buy": rng.uniform(40, 60, n), "complete": np.ones(n, dtype=bool)}
    book = {"open_time_ms": bars["open_time_ms"].copy(), "imbalance": rng.normal(0, 0.1, n)}
    oi_t = bars["open_time_ms"][0] + np.arange(n * 12, dtype=np.int64) * 5 * F.MINUTE_MS + 5 * F.MINUTE_MS
    oi = {"available_ms": oi_t, "value": 1e5 + np.cumsum(rng.normal(0, 10, oi_t.size))}
    return bars, book, oi


def _features(bars, book, oi, market, ep):
    ind = L.indicators(bars)
    return F.episode_features(bars, ind, F.ema_by_segment(bars, F.HTF_EMA_BARS), book["imbalance"], oi, market, ep)


def test_features_are_identical_when_data_end_at_the_decision_time():
    bars, book, oi = _synthetic_symbol()
    eth, _, _ = _synthetic_symbol(seed=9)
    market = {"BTCUSDT": F.close_by_decision_time(bars), "ETHUSDT": F.close_by_decision_time(eth)}
    first = int(bars["open_time_ms"][0]) + 800 * H
    eps = L.detect(bars, book, decision_start_ms=first, decision_last_ms=int(bars["open_time_ms"][-1]))["EPISODES"]
    assert len(eps) >= 5
    for ep in eps[:8]:
        full = _features(bars, book, oi, market, ep)
        keep = bars["open_time_ms"] + H <= ep["DECISION_TIME_MS"]
        tb = {k: v[keep] for k, v in bars.items()}
        tk = {k: v[keep] for k, v in book.items()}
        to = {k: v[oi["available_ms"] <= ep["DECISION_TIME_MS"]] for k, v in oi.items()}
        tm = {s: {t: c for t, c in m.items() if t <= ep["DECISION_TIME_MS"]} for s, m in market.items()}
        trunc = _features(tb, tk, to, tm, ep)
        assert set(full) == set(F.FEATURES)
        for k in F.FEATURES:
            a, b = full[k], trunc[k]
            assert (math.isnan(a) and math.isnan(b)) or a == pytest.approx(b), k


def test_oi_asof_uses_bucket_end_and_staleness():
    oi = {"available_ms": np.array([1_000, 301_000], dtype=np.int64), "value": np.array([5.0, 6.0])}
    assert math.isnan(F.oi_asof(oi, 999))
    assert F.oi_asof(oi, 300_999) == 5.0 and F.oi_asof(oi, 301_000) == 6.0
    assert math.isnan(F.oi_asof(oi, 301_000 + 31 * F.MINUTE_MS))


def test_book_parsing_matches_the_seed0001_rule():
    csv = ("timestamp,percentage,depth,notional\n"
           "2024-01-01 00:00:05,-5,1,300\n2024-01-01 00:00:05,5,1,100\n2024-01-01 00:00:05,-5,1,999\n"
           "2024-01-01 00:00:35,-5,1,200\n2024-01-01 00:00:35,-1,1,50\n"
           "2024-01-01 00:01:05,-5,1,150\n2024-01-01 00:01:05,5,1,150\n").encode()
    ts, bid, ask, dropped = RUN.parse_book_csv(csv)
    assert ts.tolist() == [F.ms("2024-01-01T00:00:05Z") + 0, F.ms("2024-01-01T00:01:05Z")]
    assert bid.tolist() == [300.0, 150.0] and ask.tolist() == [100.0, 150.0] and dropped == 1


# -------------------------------------------------------------- statistics

def test_ols_cr1_matches_statsmodels():
    sm = pytest.importorskip("statsmodels.api")
    rng = np.random.default_rng(2)
    Xd = np.column_stack([np.ones(400), rng.normal(size=(400, 3))])
    y = Xd @ np.array([0.1, 0.3, -0.2, 0.0]) + rng.normal(size=400)
    g = rng.integers(0, 50, size=400)
    mine = F.ols_cr1(Xd, y, g)
    ref = sm.OLS(y, Xd).fit(cov_type="cluster", cov_kwds={"groups": g})
    np.testing.assert_allclose(mine["beta"], ref.params)
    np.testing.assert_allclose(mine["V"], ref.cov_params(), rtol=1e-9)


def test_holm_and_heterogeneity():
    adj = F.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj["a"] == pytest.approx(0.03) and adj["c"] == pytest.approx(0.06) and adj["b"] == pytest.approx(0.06)
    q = F.heterogeneity_q([(0.1, 0.05), (0.1, 0.05), (0.1, 0.05)])
    assert q["Q"] == pytest.approx(0.0) and q["P"] == pytest.approx(1.0)


def test_labels_follow_the_frozen_rules():
    def rep(est, lo, hi, a=50, het_p=0.5):
        return {"ARM_SUMMARY": {"A": {"N": a, "WEEK_CLUSTERS": a}},
                "MODELS": {"Y1_48H": {"ESTIMABLE": True, "A_MINUS_B": {"ESTIMATE": est, "CI95": [lo, hi]},
                                      "INTERACTION": {"ESTIMATE": est, "CI95": [lo, hi]}}},
                "BY_SYMBOL_HETEROGENEITY_A_MINUS_B": {"P": het_p}, "BY_SYMBOL_HETEROGENEITY_INTERACTION": {"P": het_p}}
    disc = rep(0.05, -0.1, 0.2)
    assert RUN.labels(rep(0.02, -0.05, 0.09), disc)["A_MINUS_B"] == [
        "SAME_DIRECTION", "COMPATIBLE_WITH_ZERO", "BELOW_MEOI", "ECONOMICALLY_SMALL", "NO_DETECTED_SYMBOL_HETEROGENEITY"]
    assert RUN.labels(rep(-0.2, -0.3, -0.1, het_p=0.01), disc)["A_MINUS_B"][:2] == ["OPPOSITE_DIRECTION", "DISTINGUISHABLE_FROM_ZERO"]
    assert "HETEROGENEOUS_ACROSS_SYMBOLS" in RUN.labels(rep(-0.2, -0.3, -0.1, het_p=0.01), disc)["A_MINUS_B"]
    assert RUN.labels(rep(0.2, 0.1, 0.3, a=20), disc)["A_MINUS_B"] == ["INCONCLUSIVE_SAMPLE"]


# ------------------------------------------------------------------ design

def test_design_binds_code_frozen_artifacts_and_boundaries():
    design = json.loads((REPO / RUN.DESIGN_REL).read_text())
    for rel, digest in {**design["CODE_IDENTITY"], **design["FROZEN_ARTIFACTS"]}.items():
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
    b = design["BOUNDARIES"]
    assert b["VALIDATION_DECISIONS_UTC"] == ["2025-01-01T00:00:00Z", "2026-08-11T00:00:00Z"]
    assert b["READ_HORIZON_EXCLUSIVE_UTC"] == "2026-08-15T00:00:00Z"
    assert design["PANEL"] == list(RUN.PANEL)
    assert design["ESTIMANDS"]["PRIMARY_PRACTICAL"]["CONTRAST"] == "A - B"
    assert design["FEATURE_REGISTRY"]["FEATURES"] == list(F.FEATURES)
    assert design["BOUNDARY_FLAGS"]["PROTECTED_2025_PLUS_READ_AT_FREEZE"] is False
