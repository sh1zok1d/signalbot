"""Weekly report of the level race forecasts (FORECAST_LAYER_DECISION_V1 §5; design note
docs/research/LEVEL_RACE_CALIBRATION_MONITORING_V1_DESIGN.md §8).

Input: JSON lines, one resolved forecast each (the claim journal export; synthetic in tests):
    {"claim_class": "L3_LEVEL_RACE_T15_4H", "t_ms": ..., "week": ..., "outcome": "BREAK|REJECT|NEITHER",
     "p_raw": [b, r, n], "p_pub": [b, r, n], "p_b0": [b, r, n],
     "p_g1": [b, r, n] (raw G1@event, the «обычно» of the model states), "p_fb": [b, r, n] (fallback model),
     "p_b1": [b, r, n] (optional),
     "challengers": {"C1": [b, r, n], ...} (optional, the challenger's own published probabilities)}
Records whose outcome is not one of the three are skipped (UNKNOWN, NO_DATA).

Metrics per class, in the order of §5, for raw and published probabilities separately:
1. log-loss skill against B0, G1@event, the fallback model (and B1), week-clustered paired intervals;
2. calibration intercept (pp) and slope per head with intervals, and a 5-bin reliability table per outcome;
3. Brier score (three categories) and, per outcome, its reliability / resolution / uncertainty parts;
4. sharpness: share of forecasts outside 40–60 % per outcome;
5. AUC per outcome (one against the rest), a diagnostic;
plus ECE (5 bins, descriptive) and the paired challenger comparisons. `--cut` dates (dated layer
events, FORECAST_LAYER §6a) split every class into segments that are reported separately.

    python -m scripts.research.level_race_weekly_report journal.jsonl --out report.json [--md report.md]
        [--cut 2026-11-02T00:00Z ...]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from typing import Any, Mapping, Sequence

import numpy as np

from beta import level_race_calibration as L

REL_BINS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0000001)
SHARP_BAND = (0.4, 0.6)


def _r(x, k=4):
    return None if x is None else round(float(x), k)


def auc(p, y) -> float | None:
    p, y = np.asarray(p, float), np.asarray(y, int)
    n1, n0 = int(y.sum()), int((1 - y).sum())
    if not n1 or not n0:
        return None
    order = np.argsort(p, kind="mergesort")
    ranks = np.empty(p.size)
    ps = p[order]
    i = 0
    while i < ps.size:                     # average ranks for ties
        j = i
        while j + 1 < ps.size and ps[j + 1] == ps[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def reliability(p, y) -> dict:
    """5-bin table, the Murphy decomposition on those bins (Brier ≈ REL − RES + UNC) and ECE."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    n = p.size
    base = float(y.mean()) if n else 0.0
    rows, rel, res, ece = [], 0.0, 0.0, 0.0
    for lo, hi in zip(REL_BINS[:-1], REL_BINS[1:]):
        m = (p >= lo) & (p < hi)
        k = int(m.sum())
        if not k:
            continue
        pm, ym = float(p[m].mean()), float(y[m].mean())
        rows.append({"bin": [lo, min(hi, 1.0)], "n": k, "predicted": _r(pm), "realized": _r(ym)})
        rel += k * (pm - ym) ** 2
        res += k * (ym - base) ** 2
        ece += k * abs(pm - ym)
    n = max(n, 1)
    return {"bins": rows, "brier": _r(float(np.mean((p - y) ** 2)) if p.size else None, 5),
            "reliability": _r(rel / n, 5), "resolution": _r(res / n, 5), "uncertainty": _r(base * (1 - base), 5),
            "ece_descriptive": _r(ece / n)}


def _ci(d: Mapping[str, Any], k=5) -> dict:
    return {"est": _r(d.get("est"), k), "lo": _r(d.get("lo"), k), "hi": _r(d.get("hi"), k), "n": d.get("n"),
            "weeks": d.get("clusters")}


def block(recs: Sequence[Mapping[str, Any]], key: str) -> dict:
    """Every metric of §5 for the probabilities under `key`."""
    p3 = np.array([r[key] for r in recs], dtype=float)
    o = [r["outcome"] for r in recs]
    y3 = np.array([[1.0 if x == k else 0.0 for k in L.OUTCOMES] for x in o])
    ll = L.log_loss3(p3, o)
    out: dict = {"log_loss": _r(ll.mean(), 5)}
    for ref in ("p_b0", "p_g1", "p_fb", "p_b1"):
        if ref != key and all(ref in r for r in recs):
            lr = L.log_loss3(np.array([r[ref] for r in recs]), o)
            d = L.paired_log_loss(recs, key, ref)
            out[f"skill_vs_{ref[2:].upper()}"] = {"skill": _r(1 - ll.mean() / lr.mean()), "ll_gain": _ci(d)}
    heads = L.head_arrays(recs, key)
    out["heads"] = {}
    for h in L.HEADS:
        c, s = L.citl(*heads[h]), L.cal_slope(*heads[h])
        out["heads"][h] = {"intercept_pp": _ci(c, 2), "slope": _ci(s, 3), "recal_intercept": _r(s.get("a"), 3)}
    out["brier3"] = _r(float(np.mean(np.sum((p3 - y3) ** 2, axis=1))), 5)
    out["outcomes"] = {}
    for k, name in enumerate(L.OUTCOMES):
        pk, yk = p3[:, k], y3[:, k]
        out["outcomes"][name] = {"reliability": reliability(pk, yk),
                                 "sharpness_outside_40_60": _r(float(np.mean((pk < SHARP_BAND[0]) | (pk > SHARP_BAND[1])))),
                                 "auc": _r(auc(pk, yk))}
    return out


def class_report(recs: Sequence[Mapping[str, Any]]) -> dict:
    recs = sorted(recs, key=lambda r: int(r["t_ms"]))
    rep = {"n": len(recs), "weeks": len({int(r["week"]) for r in recs}),
           "outcome_shares": {k: _r(np.mean([r["outcome"] == k for r in recs])) for k in L.OUTCOMES},
           "raw": block(recs, "p_raw"), "published": block(recs, "p_pub"), "challengers": {}}
    names = sorted({c for r in recs for c in (r.get("challengers") or {})})
    for c in names:
        paired = [{**r, "p_chal": r["challengers"][c]} for r in recs if c in (r.get("challengers") or {})]
        look = L.challenger_look(paired)
        rep["challengers"][c] = {"paired": len(paired), "ll_gain_over_champion": _ci(L.paired_log_loss(paired, "p_chal", "p_pub")),
                                 "metrics": block(paired, "p_chal"),
                                 "look": None if look is None else {"promoted": look["promoted"],
                                                                    "retired": look["retired"],
                                                                    "calibration_ok": look["calibration_ok"]}}
    return rep


def report(rows: Sequence[Mapping[str, Any]], cuts_ms: Sequence[int] = ()) -> dict:
    by = defaultdict(list)
    for r in rows:
        if r.get("outcome") in L.OUTCOMES:
            by[r["claim_class"]].append(r)
    out = {"version": "LEVEL_RACE_WEEKLY_REPORT_V1", "calibration_version": L.LR_CAL_VERSION,
           "skipped_unresolved": sum(1 for r in rows if r.get("outcome") not in L.OUTCOMES),
           "cuts_ms": sorted(int(x) for x in cuts_ms), "classes": {}}
    for c, v in sorted(by.items()):
        if not cuts_ms:
            out["classes"][c] = class_report(v)
            continue
        out["classes"][c] = {"segments": [{"start_ms": lo, "end_ms": hi, **class_report(seg)}
                                          for lo, hi, seg in L.split_by_events(v, cuts_ms) if seg]}
    return out


def markdown(rep: Mapping[str, Any]) -> str:
    lines = ["# Level race — weekly report", ""]
    items = []
    for c, cr in rep["classes"].items():
        if "segments" in cr:
            items += [(f"{c} · segment from {s['start_ms']}", s) for s in cr["segments"]]
        else:
            items.append((c, cr))
    for c, cr in items:
        lines += [f"## {c}", "", f"N = {cr['n']}, weeks = {cr['weeks']}, shares {cr['outcome_shares']}", ""]
        lines += ["| | raw | published |", "|---|---|---|"]
        for k in ("skill_vs_B0", "skill_vs_G1", "skill_vs_FB", "skill_vs_B1"):
            if k in cr["published"]:
                f = lambda b: f"{b[k]['skill']} (gain {b[k]['ll_gain']['est']} [{b[k]['ll_gain']['lo']}, {b[k]['ll_gain']['hi']}])"
                lines.append(f"| log-loss skill {k[-2:]} | {f(cr['raw'])} | {f(cr['published'])} |")
        for h in L.HEADS:
            g = lambda b: (f"{b['heads'][h]['intercept_pp']['est']} pp [{b['heads'][h]['intercept_pp']['lo']}, "
                           f"{b['heads'][h]['intercept_pp']['hi']}], slope {b['heads'][h]['slope']['est']}")
            lines.append(f"| {h} | {g(cr['raw'])} | {g(cr['published'])} |")
        lines.append(f"| Brier (3) | {cr['raw']['brier3']} | {cr['published']['brier3']} |")
        for o in L.OUTCOMES:
            g = lambda b: (f"AUC {b['outcomes'][o]['auc']}, sharp {b['outcomes'][o]['sharpness_outside_40_60']}, "
                           f"ECE {b['outcomes'][o]['reliability']['ece_descriptive']}")
            lines.append(f"| {o} | {g(cr['raw'])} | {g(cr['published'])} |")
        for n, ch in cr["challengers"].items():
            gg = ch["ll_gain_over_champion"]
            lines.append(f"| challenger {n} | paired {ch['paired']} | gain {gg['est']} [{gg['lo']}, {gg['hi']}] |")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("journal")
    ap.add_argument("--out", required=True)
    ap.add_argument("--md", default="")
    ap.add_argument("--cut", action="append", default=[], help="ISO time of a dated layer event")
    a = ap.parse_args()
    from datetime import datetime
    cuts = [int(datetime.fromisoformat(x.replace("Z", "+00:00")).timestamp() * 1000) for x in a.cut]
    with open(a.journal) as f:
        rows = [json.loads(x) for x in f if x.strip()]
    rep = report(rows, cuts)
    with open(a.out, "w") as f:
        json.dump(rep, f, indent=1, sort_keys=True)
        f.write("\n")
    if a.md:
        with open(a.md, "w") as f:
            f.write(markdown(rep))


if __name__ == "__main__":
    main()
