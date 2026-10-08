"""Weekly level race report (scripts/research/level_race_weekly_report.py); synthetic records only."""
import json

import numpy as np

from beta import level_race_calibration as L
from scripts.research import level_race_weekly_report as R


def _rows(n=400, seed=1):
    rng = np.random.default_rng(seed)
    la, lb = rng.normal(2.0, 0.4, n), rng.normal(-0.2, 0.9, n)
    ya, yb = rng.random(n) < L.expit(la), rng.random(n) < L.expit(lb)
    p = L.probs_from_heads(L.expit(la), L.expit(lb))
    b0 = L.probs_from_heads(L.expit(la), L.expit(np.full(n, -0.2)))
    out = []
    for i in range(n):
        out.append({"claim_class": "L3_LEVEL_RACE_T15_4H", "t_ms": i * 10 ** 7, "week": i // 6,
                    "outcome": "NEITHER" if not ya[i] else ("BREAK" if yb[i] else "REJECT"),
                    "p_raw": p[i].tolist(), "p_pub": p[i].tolist(), "p_b0": b0[i].tolist(),
                    "challengers": {"C1": p[i].tolist()}})
    out.append({**out[0], "outcome": "UNKNOWN"})
    return out


def test_auc():
    assert R.auc([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1]) == 1.0
    assert R.auc([0.5, 0.5], [0, 1]) == 0.5
    assert R.auc([0.3], [1]) is None


def test_reliability_decomposition_matches_brier_on_binned_forecasts():
    rng = np.random.default_rng(2)
    p = rng.choice([0.1, 0.3, 0.5, 0.7, 0.9], 5000)
    y = (rng.random(5000) < p) * 1.0
    r = R.reliability(p, y)
    assert abs(r["brier"] - (r["reliability"] - r["resolution"] + r["uncertainty"])) < 1e-4
    assert len(r["bins"]) == 5


def test_report_structure_and_skill(tmp_path):
    rows = _rows()
    rep = R.report(rows)
    assert rep["skipped_unresolved"] == 1
    cr = rep["classes"]["L3_LEVEL_RACE_T15_4H"]
    assert cr["n"] == 400
    assert cr["published"]["skill_vs_B0"]["skill"] > 0             # the model knows the per-event spread
    assert set(cr["published"]["heads"]) == set(L.HEADS)
    assert set(cr["published"]["outcomes"]) == set(L.OUTCOMES)
    assert cr["challengers"]["C1"]["ll_gain_over_champion"]["est"] == 0.0
    seg = R.report(rows, [200 * 10 ** 7])["classes"]["L3_LEVEL_RACE_T15_4H"]["segments"]
    assert [x["n"] for x in seg] == [200, 200]
    assert "segment" in R.markdown(R.report(rows, [200 * 10 ** 7]))
    path = tmp_path / "j.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows))
    assert "L3_LEVEL_RACE_T15_4H" in R.markdown(rep)


def test_header_carries_the_drift_sentence_verbatim():
    s = ("a level-specific drift of about ±10 pp is detected in about a year, not weeks; "
         "inside the beta the accuracy line next to the number is the guard")
    rep = R.report(_rows(50))
    assert rep["note"] == s and s in R.markdown(rep).splitlines()[2]
