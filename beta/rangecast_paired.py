"""Paired shadow comparison of the range model V1 and W_L1, and the promotion rule fixed before any outcome.

NOT WIRED. A pure function of the paired shadow store's joined rows (`beta.paired_shadow.ShadowLedger.
joined_rows`, or the same fields from its export). It reads no database, writes nothing, changes no user text
and switches nothing: its output is a recommendation to the owner. Plan and rule:
docs/RANGECAST_V2_SHADOW_PLAN_V2.md.

`rows_from_ledger` pairs the store's rows by anchor (one market question, both procedures, one outcome) into
the evaluator's rows:
    pair_key (issue slot and horizon), horizon (1h / 4h / 24h), family (touch / neither), subject_key (the
    store's anchor key), as_of, p_v1, p_v2, outcome (0 / 1), status, coverage, distance_pct (touch).
A row left out (status other than COMPLETE, or coverage under 0.9) leaves out both models together.

Per horizon and family: the paired difference V2 − V1 in log loss and Brier per anchor (touch on the
journal grid, «ни один» on its pairs), its weekly means (ISO weeks, equal weight per week), the near and
far touch groups, and each model's calibration (pooled logistic intercept and slope, reliability bins).

Rule `RANGECAST_V2_PROMOTION_RULE_V2` (replaces V1 before any shadow outcome; V1 was never applied):
- one look, on the first 12 complete ISO weeks;
- primary (non-inferiority): the combined weekly endpoint C = (Δ1h + Δ4h) / 2 of the touch log loss. PASS when
  mean(C) < 0 and mean(C) + 1.5 · t(0.975, W−1) · sd(C) / √W < 0.001 (V2 not worse by more than 0.001 nats,
  the standard error inflated by 1.5 for week-to-week regime persistence measured on the development folds);
- 4h gate: the observed 4h result is not against V2. For touch and «ни один» at 4h, the mean weekly
  difference V2 − V1 is below 0 in log loss and in Brier;
- gates: no horizon or family significantly worse (lower bound above 0, same inflation); 4h near and far
  touch groups not significantly worse; V2 calibration slope in [0.85, 1.15] and |intercept| ≤ 0.15 at 1h and
  4h; no V2 book of calibration monitor V2 suspected, confirmed, faulted or incomplete; one spec digest per
  procedure over the look, and every V2 snapshot verifiable;
- harm stop from week 6: the combined lower bound above 0;
- outcome: RECOMMEND_SWITCH or NO_RECOMMENDATION at the look, a recommendation to the owner and never a
  switch. Non-inferiority is not superiority: the evidence label says SUPERIORITY_SHOWN only when the
  stricter interval (inflation 2.0) lies below 0, and NON_INFERIORITY_ONLY otherwise;
- a failed look is not extended. Continuing needs a new registered rule.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

import numpy as np

EVALUATOR_VERSION = "RANGECAST_PAIRED_EVAL_V2"
PROMOTION_RULE_ID = "RANGECAST_V2_PROMOTION_RULE_V2"
V1_PAIR = ("RANGECAST_V1", "RANGECAST_V1")          # (procedure_id, spec_id) = beta.paired_shadow (test-pinned)
V2_PAIR = ("RANGECAST_V2", "W_L1")
HORIZONS = ("1h", "4h", "24h")
FAMILIES = ("touch", "neither")
LOOK_WEEKS = 12
HARM_FROM_WEEK = 6
NI_MARGIN = 0.001
SE_INFLATION = 1.5
SUPERIORITY_SE_INFLATION = 2.0          # the evidence label only; never a recommendation condition
MIN_WEEK_ANCHORS = 140                  # usable hourly anchors per horizon for a week to count (of 168)
COVERAGE_MIN = 0.9                      # = beta.claims.COVERAGE_MIN
P_CLIP = (1e-4, 1 - 1e-4)
SLOPE_BAND = (0.85, 1.15)
INTERCEPT_MAX = 0.15
NEAR_MAX_PCT = 0.5
FAR_MIN_PCT = 2.0
PROB_BINS = (0.0, 0.05, 0.15, 0.3, 0.5, 0.7, 0.85, 1.0000001)
BLOCKING_MONITOR_STATES = ("SUSPECTED_DEGRADATION", "CONFIRMED_DIVERGENCE", "TECHNICAL_FAULT", "INCOMPLETE_DATA")

RECOMMEND_SWITCH = "RECOMMEND_SWITCH"
NO_RECOMMENDATION = "NO_RECOMMENDATION"
CONTINUE = "CONTINUE"
STOP_HARM = "STOP_HARM"
NOT_EVALUABLE = "NOT_EVALUABLE"
SUPERIORITY_SHOWN = "SUPERIORITY_SHOWN"
NON_INFERIORITY_ONLY = "NON_INFERIORITY_ONLY"


# ---- small statistics ------------------------------------------------------------------------------
_T975 = (12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145, 2.131,
         2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042)


def t975(df: int) -> float:
    """Student t 0.975 quantile: the exact table to df 30, Cornish–Fisher above (error under 0.001)."""
    if df <= 0:
        return float("inf")
    if df <= len(_T975):
        return _T975[df - 1]
    z = 1.959964
    return z + (z ** 3 + z) / (4 * df) + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * df ** 2) + \
        (3 * z ** 7 + 19 * z ** 5 + 17 * z ** 3 - 15 * z) / (384 * df ** 3)


def _ll(p: float, y: float) -> float:
    p = min(max(p, P_CLIP[0]), P_CLIP[1])
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


def _week(dt: datetime) -> int:
    return (int(dt.timestamp()) // 86400 + 3) // 7


def _as_utc(v) -> Optional[datetime]:
    if isinstance(v, str):
        v = datetime.fromisoformat(v.replace("Z", "+00:00"))
    if not isinstance(v, datetime) or v.tzinfo is None:
        return None
    return v.astimezone(timezone.utc)


def weekly_interval(means: Sequence[float], inflation: float) -> Optional[dict]:
    w = len(means)
    if w < 2:
        return None
    m = sum(means) / w
    sd = math.sqrt(sum((x - m) ** 2 for x in means) / (w - 1))
    half = inflation * t975(w - 1) * sd / math.sqrt(w)
    return {"weeks": w, "mean": m, "sd": sd, "lo": m - half, "hi": m + half, "inflation": inflation}


def recalibration(ps: Sequence[float], ys: Sequence[float]) -> Optional[dict]:
    """Pooled logistic logit P(y) = a + b · logit p (Newton)."""
    if len(ps) < 20 or len(set(ys)) < 2:
        return None
    p = np.clip(np.asarray(ps, float), *P_CLIP)
    y = np.asarray(ys, float)
    X = np.column_stack([np.ones(p.size), np.log(p / (1 - p))])
    th = np.array([0.0, 1.0])
    for _ in range(50):
        q = 1 / (1 + np.exp(-(X @ th)))
        H = (X * (q * (1 - q))[:, None]).T @ X
        if np.linalg.det(H) <= 1e-12:
            return None
        step = np.linalg.solve(H, X.T @ (y - q))
        th = th + step
        if float(np.max(np.abs(step))) < 1e-10:
            break
    return {"intercept": float(th[0]), "slope": float(th[1]), "n": int(p.size)}


def reliability(ps: Sequence[float], ys: Sequence[float]) -> list:
    out = []
    for lo, hi in zip(PROB_BINS[:-1], PROB_BINS[1:]):
        sel = [(p, y) for p, y in zip(ps, ys) if lo <= p < hi]
        if sel:
            n = len(sel)
            mp, my = sum(p for p, _ in sel) / n, sum(y for _, y in sel) / n
            out.append({"bin": [lo, min(hi, 1.0)], "n": n, "predicted": mp, "realized": my, "diff_pp": (my - mp) * 100})
    return out


# ---- report --------------------------------------------------------------------------------------
def _prepare(rows: Sequence[Mapping[str, Any]]) -> tuple:
    usable, faults, dropped = [], [], 0
    for r in rows:
        h, fam = r.get("horizon"), r.get("family")
        at = _as_utc(r.get("as_of"))
        try:
            p1, p2 = float(r["p_v1"]), float(r["p_v2"])
        except (KeyError, TypeError, ValueError):
            faults.append("PROBABILITY_MISSING")
            continue
        if h not in HORIZONS or fam not in FAMILIES or at is None or not r.get("pair_key"):
            faults.append("IDENTITY")
            continue
        if not (0.0 <= p1 <= 1.0 and 0.0 <= p2 <= 1.0 and math.isfinite(p1) and math.isfinite(p2)):
            faults.append("PROBABILITY_RANGE")
            continue
        cov = r.get("coverage")
        if r.get("status") != "COMPLETE" or (cov is not None and float(cov) < COVERAGE_MIN):
            dropped += 1
            continue
        y = r.get("outcome")
        if y not in (0, 1, True, False):
            faults.append("OUTCOME")
            continue
        if fam == "touch" and r.get("source", "GRID") != "GRID":
            continue
        usable.append({"h": h, "fam": fam, "key": r["pair_key"], "week": _week(at), "p1": p1, "p2": p2,
                       "y": float(y), "d": r.get("distance_pct")})
    return usable, faults, dropped


def _anchor_diffs(items: Sequence[Mapping], subset=None) -> dict:
    """{pair_key: (week, mean ΔLL, mean ΔBrier)} over the rows of one anchor (optionally a subset)."""
    acc: dict = {}
    for it in items:
        if subset is not None and not subset(it):
            continue
        a = acc.setdefault(it["key"], [it["week"], 0.0, 0.0, 0])
        a[1] += _ll(it["p2"], it["y"]) - _ll(it["p1"], it["y"])
        a[2] += (it["p2"] - it["y"]) ** 2 - (it["p1"] - it["y"]) ** 2
        a[3] += 1
    return {k: (v[0], v[1] / v[3], v[2] / v[3]) for k, v in acc.items()}


def _weekly(diffs: Mapping[str, tuple], which: int, weeks: Sequence[int]) -> list:
    by: dict = {}
    for wk, dl, db in diffs.values():
        by.setdefault(wk, []).append(dl if which == 1 else db)
    return [sum(by[w]) / len(by[w]) for w in weeks if w in by]


def paired_report(rows: Sequence[Mapping[str, Any]], *, weeks_limit: Optional[int] = None) -> dict:
    """The comparison tables. With `weeks_limit`, only the first that many complete weeks are used."""
    usable, faults, dropped = _prepare(rows)
    counts: dict = {}
    for it in usable:
        if it["fam"] == "touch":
            counts.setdefault(it["h"], {}).setdefault(it["week"], set()).add(it["key"])
    complete = sorted(set.intersection(*[{w for w, ks in counts.get(h, {}).items() if len(ks) >= MIN_WEEK_ANCHORS}
                                          for h in ("1h", "4h")])) if counts else []
    if weeks_limit is not None:
        complete = complete[:weeks_limit]
    wk_set = set(complete)
    rep: dict = {"evaluator": EVALUATOR_VERSION, "rule": PROMOTION_RULE_ID, "faults": sorted(set(faults)),
                 "n_faults": len(faults), "dropped_incomplete": dropped, "complete_weeks": complete, "books": {}}
    for h in HORIZONS:
        for fam in FAMILIES:
            items = [it for it in usable if it["h"] == h and it["fam"] == fam and it["week"] in wk_set]
            if not items:
                continue
            diffs = _anchor_diffs(items)
            book = {"rows": len(items), "anchors": len(diffs),
                    "logloss_diff": weekly_interval(_weekly(diffs, 1, complete), SE_INFLATION),
                    "brier_diff": weekly_interval(_weekly(diffs, 2, complete), SE_INFLATION),
                    "logloss_v1": sum(_ll(i["p1"], i["y"]) for i in items) / len(items),
                    "logloss_v2": sum(_ll(i["p2"], i["y"]) for i in items) / len(items),
                    "calibration_v1": recalibration([i["p1"] for i in items], [i["y"] for i in items]),
                    "calibration_v2": recalibration([i["p2"] for i in items], [i["y"] for i in items]),
                    "reliability_v1": reliability([i["p1"] for i in items], [i["y"] for i in items]),
                    "reliability_v2": reliability([i["p2"] for i in items], [i["y"] for i in items])}
            if fam == "touch":
                for name, cond in (("near", lambda it: it["d"] is not None and it["d"] <= NEAR_MAX_PCT),
                                   ("far", lambda it: it["d"] is not None and it["d"] >= FAR_MIN_PCT)):
                    book[f"{name}_logloss_diff"] = weekly_interval(_weekly(_anchor_diffs(items, cond), 1, complete),
                                                                   SE_INFLATION)
            rep["books"][f"{fam}_{h}"] = book
    w1 = dict(zip(complete, _weekly(_anchor_diffs([i for i in usable if i["h"] == "1h" and i["fam"] == "touch"]), 1, complete)))
    w4 = dict(zip(complete, _weekly(_anchor_diffs([i for i in usable if i["h"] == "4h" and i["fam"] == "touch"]), 1, complete)))
    comb = [(w1[w] + w4[w]) / 2 for w in complete if w in w1 and w in w4]
    rep["combined"] = weekly_interval(comb, SE_INFLATION)
    rep["combined_superiority"] = weekly_interval(comb, SUPERIORITY_SE_INFLATION)
    return rep


# ---- the paired shadow store's rows --------------------------------------------------------------------
def rows_from_ledger(joined: Sequence[Mapping[str, Any]], *, v1: tuple = V1_PAIR, v2: tuple = V2_PAIR) -> tuple:
    """(rows, info) from `ShadowLedger.joined_rows()` (or its export fields). One row per anchor that both
    specifications hold; `info` counts unpaired anchors and lists the spec digests and V2 snapshot ids seen,
    so the caller can check one digest per procedure and every snapshot against the snapshot store."""
    by: dict = {}
    digests: dict = {v1: set(), v2: set()}
    snapshots: set = set()
    for r in joined:
        ident = (r.get("procedure_id"), r.get("spec_id"))
        if ident not in (v1, v2):
            continue
        digests[ident].add(r.get("spec_digest"))
        if ident == v2:
            snapshots.add(r.get("snapshot_id"))
        by.setdefault(r["anchor_key"], {})[ident] = r
    rows, unpaired = [], 0
    for key, pair in by.items():
        a, b = pair.get(v1), pair.get(v2)
        if a is None or b is None:
            unpaired += 1
            continue
        slot = a.get("issue_slot")
        slot = slot.isoformat() if isinstance(slot, datetime) else slot
        rows.append({"pair_key": f"{slot}|{a['horizon']}", "horizon": a["horizon"], "family": a["family"],
                     "subject_key": key, "source": "GRID", "as_of": a.get("as_of"), "distance_pct": a.get("distance_pct"),
                     "p_v1": a.get("probability"), "p_v2": b.get("probability"), "outcome": a.get("outcome"),
                     "status": a.get("status"), "coverage": a.get("coverage")})
    faults = [f"SPEC_DIGESTS:{ident[0]}:{len(d)}" for ident, d in digests.items() if len(d) > 1]
    return rows, {"unpaired_anchors": unpaired, "spec_digests": {f"{k[0]}/{k[1]}": sorted(x for x in d if x)
                                                                  for k, d in digests.items()},
                  "v2_snapshot_ids": sorted(s for s in snapshots if s), "identity_faults": faults}


# ---- decision ------------------------------------------------------------------------------------------
def _statement(decision: str, evidence: Optional[str]) -> str:
    if decision == RECOMMEND_SWITCH and evidence == SUPERIORITY_SHOWN:
        return ("Recommendation to the owner: W_L1 scored better than V1 on the live record, and the stricter "
                "interval excludes no difference. Switching is the owner's decision.")
    if decision == RECOMMEND_SWITCH:
        return ("Recommendation to the owner: W_L1 is not worse than V1 within 0.001 nats and was observed better at "
                "4h. Superiority is not shown. Switching is the owner's decision.")
    return {CONTINUE: "The look has not been reached; nothing is recommended.",
            STOP_HARM: "W_L1 is worse than V1 on the live record; the shadow stops and nothing is recommended.",
            NOT_EVALUABLE: "The comparison is not evaluable; nothing is recommended."}.get(
        decision, "The rule did not hold at the look; no switch is recommended.")


def decide(rows: Sequence[Mapping[str, Any]], *, monitor_states: Optional[Mapping[str, str]] = None,
           identity_faults: int = 0, unverified_snapshots: int = 0) -> dict:
    """Apply RANGECAST_V2_PROMOTION_RULE_V2. `monitor_states` maps 'touch_1h' … to the states of calibration
    monitor V2's W_L1 books. The result is a recommendation to the owner; nothing switches."""
    full = paired_report(rows)
    checks: dict = {"faults": full["n_faults"] == 0 and identity_faults == 0 and unverified_snapshots == 0}
    out = {"rule": PROMOTION_RULE_ID, "weeks": len(full["complete_weeks"]), "checks": checks, "report": full,
           "evidence": None, "automatic_switch": False}
    if not checks["faults"]:
        return {**out, "decision": NOT_EVALUABLE, "reason": "FAULTS_OR_IDENTITY_OR_SNAPSHOTS",
                "statement": _statement(NOT_EVALUABLE, None)}
    c = full["combined"]
    if c is not None and out["weeks"] >= HARM_FROM_WEEK and c["lo"] > 0:
        return {**out, "decision": STOP_HARM, "reason": "COMBINED_LOWER_BOUND_ABOVE_0",
                "statement": _statement(STOP_HARM, None)}
    if out["weeks"] < LOOK_WEEKS:
        return {**out, "decision": CONTINUE, "reason": f"{out['weeks']}_OF_{LOOK_WEEKS}_WEEKS",
                "statement": _statement(CONTINUE, None)}
    rep = paired_report(rows, weeks_limit=LOOK_WEEKS)                 # the look: the first 12 complete weeks only
    out["report"] = rep
    c = rep["combined"]
    checks["primary"] = bool(c and c["mean"] < 0 and c["hi"] < NI_MARGIN)
    four = {}
    for fam in FAMILIES:
        book = rep["books"].get(f"{fam}_4h") or {}
        ll, br = book.get("logloss_diff"), book.get("brier_diff")
        four[fam] = bool(ll and br and ll["mean"] < 0 and br["mean"] < 0)
    checks["four_hour_observed"] = all(four.values())
    harm = {}
    for name, book in rep["books"].items():
        iv = book["logloss_diff"]
        harm[name] = bool(iv is None or iv["lo"] <= 0)
    checks["no_book_worse"] = all(harm.values()) and all(f"{f}_{h}" in rep["books"] for f in FAMILIES for h in ("1h", "4h"))
    t4 = rep["books"].get("touch_4h") or {}
    checks["near_far_not_worse"] = all((t4.get(g) or {"lo": 1}).get("lo", 1) <= 0 for g in ("near_logloss_diff", "far_logloss_diff"))
    cal = {}
    for h in ("1h", "4h"):
        cv = (rep["books"].get(f"touch_{h}") or {}).get("calibration_v2")
        cal[h] = bool(cv and SLOPE_BAND[0] <= cv["slope"] <= SLOPE_BAND[1] and abs(cv["intercept"]) <= INTERCEPT_MAX)
    checks["calibration"] = all(cal.values())
    ms = dict(monitor_states or {})
    checks["monitor"] = all(ms.get(f"{f}_{h}") not in BLOCKING_MONITOR_STATES and f"{f}_{h}" in ms
                            for f in FAMILIES for h in ("1h", "4h"))
    ok = all(checks[k] for k in ("primary", "four_hour_observed", "no_book_worse", "near_far_not_worse",
                                 "calibration", "monitor"))
    decision = RECOMMEND_SWITCH if ok else NO_RECOMMENDATION
    sup = rep["combined_superiority"]
    evidence = (SUPERIORITY_SHOWN if (sup and sup["hi"] < 0) else NON_INFERIORITY_ONLY) if ok else None
    return {**out, "decision": decision, "evidence": evidence,
            "reason": None if ok else ",".join(k for k, v in checks.items() if not v),
            "statement": _statement(decision, evidence)}
