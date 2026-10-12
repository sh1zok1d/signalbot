"""Paired shadow evaluator and the frozen promotion rule (beta/rangecast_paired.py). Synthetic rows only."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from beta import rangecast_paired as rp

UTC = timezone.utc
START = datetime(2026, 10, 19, tzinfo=UTC)          # a Monday
GRID = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0)
PAIRS = [(a, b) for a in (0.5, 1.0, 2.0, 3.0) for b in (0.5, 1.0, 2.0, 3.0)]
SCALE = {"1h": 0.5, "4h": 1.1, "24h": 2.8}
OK_MONITOR = {f"{f}_{h}": "WITHIN_NOISE" for f in rp.FAMILIES for h in rp.HORIZONS}


def _logit(p):
    return math.log(p / (1 - p))


def _expit(x):
    return 1 / (1 + math.exp(-x))


def stream(weeks: int, *, v1_shift: float = 0.35, v2_shift: float = 0.0, seed: int = 1, start=START,
           hours_per_week: int = 168, status=lambda i: "COMPLETE"):
    """Hourly anchors; truth q from a random scale; V2 = truth shifted by v2_shift in logit, V1 by v1_shift."""
    rng = np.random.default_rng(seed)
    rows, k = [], 0
    for w in range(weeks):
        for hr in range(hours_per_week):
            at = start + timedelta(weeks=w, hours=hr)
            vol = math.exp(rng.normal(0, 0.4))
            for h in rp.HORIZONS:
                s = SCALE[h] * vol
                key = f"{at.isoformat()}|{h}"
                for d in GRID:
                    q = min(max(math.exp(-d / s), 1e-3), 0.999)
                    for side in (+1, -1):
                        y = int(rng.random() < q)
                        rows.append({"pair_key": key, "horizon": h, "family": "touch", "subject_key": f"{side:+d}:{d}",
                                     "source": "GRID", "as_of": at.isoformat(), "distance_pct": d, "outcome": y,
                                     "p_v1": _expit(_logit(q) + v1_shift), "p_v2": _expit(_logit(q) + v2_shift),
                                     "status": status(k), "coverage": 1.0})
                        k += 1
                for du, dd in PAIRS:
                    q = min(max((1 - math.exp(-du / s)) * (1 - math.exp(-dd / s)), 1e-3), 0.999)
                    y = int(rng.random() < q)
                    rows.append({"pair_key": key, "horizon": h, "family": "neither", "subject_key": f"{du}:{dd}",
                                 "as_of": at.isoformat(), "outcome": y, "p_v1": _expit(_logit(q) - v1_shift),
                                 "p_v2": _expit(_logit(q) - v2_shift), "status": status(k), "coverage": 1.0})
                    k += 1
    return rows


@pytest.fixture(scope="module")
def good12():
    return stream(12)


def test_t_quantile_is_close_to_exact():
    exact = {3: 3.182, 5: 2.571, 11: 2.201, 19: 2.093, 30: 2.042, 100: 1.984}
    for df, q in exact.items():
        assert abs(rp.t975(df) - q) < 0.003, df


def test_scores_on_a_hand_example():
    at = START.isoformat()
    rows = [{"pair_key": "a", "horizon": "4h", "family": "touch", "source": "GRID", "as_of": at, "distance_pct": 1.0,
             "p_v1": 0.8, "p_v2": 0.6, "outcome": 0, "status": "COMPLETE", "coverage": 1.0}]
    usable, faults, dropped = rp._prepare(rows)
    d = rp._anchor_diffs(usable)["a"]
    assert d[1] == pytest.approx(-math.log(0.4) + math.log(0.2))
    assert d[2] == pytest.approx(0.36 - 0.64)


def test_a_better_calibrated_v2_is_promoted_at_the_look(good12):
    r = rp.decide(good12, monitor_states=OK_MONITOR)
    assert r["decision"] == rp.PROMOTE, r["reason"]
    rep = r["report"]
    assert rep["complete_weeks"] and len(rep["complete_weeks"]) == rp.LOOK_WEEKS
    assert rep["combined"]["mean"] < 0 and rep["combined"]["hi"] < rp.NI_MARGIN
    t4 = rep["books"]["touch_4h"]
    assert t4["logloss_v2"] < t4["logloss_v1"] and t4["brier_diff"]["mean"] < 0
    assert abs(t4["calibration_v2"]["slope"] - 1) < 0.1 and t4["calibration_v1"]["intercept"] < -0.2


def test_a_blocking_monitor_state_or_a_missing_book_stops_promotion(good12):
    r = rp.decide(good12, monitor_states={**OK_MONITOR, "touch_4h": "CONFIRMED_DIVERGENCE"})
    assert r["decision"] == rp.NO_PROMOTION and "monitor" in r["reason"]
    r = rp.decide(good12, monitor_states={k: v for k, v in OK_MONITOR.items() if k != "neither_1h"})
    assert r["decision"] == rp.NO_PROMOTION


def test_before_the_look_the_rule_waits():
    r = rp.decide(stream(8), monitor_states=OK_MONITOR)
    assert r["decision"] == rp.CONTINUE and r["weeks"] == 8


def test_a_worse_v2_is_stopped_for_harm():
    r = rp.decide(stream(7, v1_shift=0.0, v2_shift=0.35), monitor_states=OK_MONITOR)
    assert r["decision"] == rp.STOP_HARM


def test_equal_models_never_earn_the_superiority_label():
    """Equal models can pass non-inferiority (the rule relies on the historical superiority record); the live
    superiority label needs the stricter interval and does not appear."""
    for s in (3, 9):
        r = rp.decide(stream(12, v1_shift=0.0, v2_shift=0.0, seed=s, hours_per_week=150), monitor_states=OK_MONITOR)
        assert r["decision"] in (rp.PROMOTE, rp.NO_PROMOTION) and r["label"] == "NON_INFERIOR_ONLY"


def test_faults_make_the_comparison_not_evaluable(good12):
    bad = list(good12[:-1]) + [{**good12[-1], "p_v2": 1.2}]
    assert rp.decide(bad, monitor_states=OK_MONITOR)["decision"] == rp.NOT_EVALUABLE
    assert rp.decide(good12, monitor_states=OK_MONITOR, artifact_unchanged=False)["decision"] == rp.NOT_EVALUABLE
    assert rp.decide(good12, monitor_states=OK_MONITOR, parity_faults=1)["decision"] == rp.NOT_EVALUABLE


def test_the_look_uses_only_the_first_twelve_complete_weeks(good12):
    later = stream(4, v1_shift=0.0, v2_shift=0.2, seed=7, start=START + timedelta(weeks=12))
    a = rp.decide(good12, monitor_states=OK_MONITOR)
    b = rp.decide(good12 + later, monitor_states=OK_MONITOR)
    assert b["weeks"] == 16 and b["report"]["complete_weeks"] == a["report"]["complete_weeks"]
    assert b["report"]["combined"]["mean"] == pytest.approx(a["report"]["combined"]["mean"])
    assert b["decision"] == a["decision"]


def test_incomplete_rows_leave_both_models_out_and_thin_weeks_do_not_count():
    rows = stream(2, status=lambda i: "NO_DATA" if i % 10 == 0 else "COMPLETE")
    usable, faults, dropped = rp._prepare(rows)
    assert dropped == sum(1 for r in rows if r["status"] != "COMPLETE") and not faults
    thin = stream(3, hours_per_week=100)
    assert rp.paired_report(thin)["complete_weeks"] == []
