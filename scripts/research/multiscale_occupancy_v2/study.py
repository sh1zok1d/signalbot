"""MULTISCALE_ADAPTIVE_OCCUPANCY_V2 synthetic adequacy study (outcome-free).

    python -m scripts.research.multiscale_occupancy_v2.study stage1 OUT.json     # architecture selection
    python -m scripts.research.multiscale_occupancy_v2.study stage2 STAGE1.json OUT.json   # fresh seeds
    python -m scripts.research.multiscale_occupancy_v2.study validate STAGE1.json OUT.json # exact IRLS spot check
                                                                                           # and coefficient paths
Real features, real schedule, synthetic outcomes. No market outcome is read."""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict

import numpy as np

from . import constants as K
from . import dgp
from . import engine as EN
from . import exact as EX
from .data import load_features

NULLS = ("NULL", "NULL_DRIFT")
SIGNALS = ("CONSTANT_OCC_4H", "SWITCHING_OCC_2H_8H", "OCC_OFF_ON")


def levels() -> list:
    return [(s, 0.0) for s in NULLS] + [(s, lv) for s in SIGNALS for lv in K.LADDER]


def seeds_for(stage_seed: int, scenario: str, level: float, n: int) -> list:
    lid = 99 if scenario in NULLS else K.LADDER.index(level)
    return [(stage_seed, K.SCENARIOS.index(scenario), lid, r) for r in range(n)]


def candidates(include_reference: bool = True) -> list:
    mems = K.MEMORIES + (K.REFERENCE_MEMORIES if include_reference else ())
    return [EN.v2_spec(st, m, w, lam) for st in K.STRUCTURES for (m, w) in mems for lam in K.LAMBDAS_OCC]


def _q(a: np.ndarray) -> dict:
    return {q: float(np.quantile(a, float(q))) for q in ("0.05", "0.25", "0.5", "0.75", "0.95")}


def aggregate(per: dict) -> dict:
    out = {}
    for m, d in per.items():
        a = {k: np.concatenate(v) for k, v in d.items()}
        r = {"n": int(a["d_brier"].size), "p_support": float(a["support"].mean()), "p_beat": float(a["beat"].mean()),
             "p_worse": float(a["worse"].mean()), "d_brier_mean": float(a["d_brier"].mean()),
             "d_brier_q": _q(a["d_brier"]), "d_logloss_mean": float(a["d_logloss"].mean()),
             "d_brier_vs_static_mean": float(a["vs_static"].mean()), "p_beat_static": float((a["vs_static"] < 0).mean())}
        if "support_cw" in a:
            r.update({"p_support_cw": float(a["support_cw"].mean()), "cw_mean": float(a["cw"].mean())})
        out[m] = r
    return out


def run_stage(stage_seed: int, r_sig: int, r_null: int, specs: list, with_v1: bool, keep: tuple = ()) -> dict:
    t0 = time.time()
    rows = load_features()
    g = EN.build_geometry(rows, K.EWMA_HALF_LIFE_WEEKS)
    sig = dgp.residual_signals(rows, g.X)
    C = EN.boot_counts(g.week_ids.size, K.BOOT_DRAWS, K.BOOT_SEED)
    cnt = EN.week_counts(g)
    models = [s.name for s in specs] + ["STATIC_OCC4", "CLIM"] + (["V1"] if with_v1 else [])
    res, per_rep = {}, {}
    for sc, lv in levels():
        n = r_null if sc in NULLS else r_sig
        sds = seeds_for(stage_seed, sc, lv, n)
        per = defaultdict(lambda: defaultdict(list))
        for b0 in range(0, n, K.BATCH):
            Y = dgp.outcomes(rows, sig, sc, lv * K.RHO_OBS, K.KAPPA, sds[b0:b0 + K.BATCH], K.DRIFT_SD)
            ev = EN.evaluate_batch(g, Y, specs, with_v1)
            acc = ev["acc"]
            for m in models:
                s = EN.summarize(acc, C, cnt, m)
                vs = EN.boot_pair(C, cnt, acc.brier[m], acc.brier["STATIC_OCC4"])["point"]
                for k in ("d_brier", "d_logloss", "support", "beat", "worse") + (
                        ("support_cw", "cw") if "support_cw" in s else ()):
                    per[m][k].append(np.asarray(s[k]))
                per[m]["vs_static"].append(vs)
        key = f"{sc}@{lv:g}"
        res[key] = aggregate(per)
        if keep:
            per_rep[key] = {m: {k: np.concatenate(per[m][k]).tolist() for k in ("d_brier", "support", "beat")}
                            for m in keep if m in per}
        print(f"{key} done {time.time() - t0:.0f}s", flush=True)
    return {"results": res, "per_rep": per_rep, "seconds": round(time.time() - t0, 1),
            "segments": int(g.bounds.size), "weeks": int(g.week_ids.size), "outer_rows": int(g.outer.sum())}


# ------------------------------------------------------------------ frozen selection rule
def _simplicity(name: str) -> tuple:
    _, st, mem, lam = name.split("|")
    morder = {"TRAIL_104": 0, "TRAIL_52": 1, "EWMA_26": 2}
    return (-float(lam), 0 if st == "OFFSET" else 1, morder.get(mem, 9))


def select(stage1: dict) -> dict:
    r = stage1["results"]
    names = [s.name for s in candidates(include_reference=False)]
    table = []
    for nm in names:
        nulls = [r[f"{s}@0"][nm] for s in NULLS]
        elig = all(x["p_support"] <= K.SELECT_NULL_FALSE_SUPPORT_MAX and x["p_beat"] <= K.SELECT_NULL_BEAT_MAX
                   for x in nulls)
        score = float(np.mean([r[f"{s}@{lv:g}"][nm]["p_support"] for s, lv in K.SELECT_SCORE]))
        second = float(np.mean([r[f"{s}@{lv:g}"][nm]["p_support"] for s, lv in K.SELECT_SECONDARY]))
        table.append({"name": nm, "eligible": elig, "score": score, "secondary": second,
                      "null_false_support": [x["p_support"] for x in nulls], "null_beat": [x["p_beat"] for x in nulls]})
    el = [t for t in table if t["eligible"]]
    if not el:
        return {"selected": None, "table": table}
    best = max(t["score"] for t in el)
    band = [t for t in el if t["score"] >= best - K.SELECT_TIE_BAND]
    band.sort(key=lambda t: (-t["secondary"],) + _simplicity(t["name"]))
    return {"selected": band[0]["name"], "band": [t["name"] for t in band], "table": table}


def spec_by_name(name: str) -> EN.Spec:
    for s in candidates():
        if s.name == name:
            return s
    raise SystemExit(f"UNKNOWN_SPEC_{name}")


def twin(spec: EN.Spec) -> EN.Spec:
    _, st, _, lam = spec.name.split("|")
    return EN.v2_spec(st, "EXPANDING", 0, float(lam))


# ------------------------------------------------------------------ frozen adequacy criterion
def adequacy(stage2: dict, v2: str, support_key: str = "p_support") -> dict:
    r = stage2["results"]
    at = lambda s, lv, m: r[f"{s}@{lv:g}"][m]
    c1 = all(at(s, 0, v2)[support_key] <= K.C1_FALSE_SUPPORT_MAX for s in NULLS)
    c2 = all(at(s, 0, v2)["p_beat"] <= K.C2_BEAT_MAX for s in NULLS)
    sw = "SWITCHING_OCC_2H_8H"
    c3a = at(sw, 2.0, v2)[support_key] - at(sw, 2.0, "V1")["p_support"]
    c3b = at(sw, 1.0, v2)["p_beat"] - at(sw, 1.0, "V1")["p_beat"]
    c3 = c3a >= K.C3_SUPPORT_GAIN_OVER_V1_AT_2X and c3b >= K.C3_BEAT_GAIN_OVER_V1_AT_1X
    c4v = {s: at(s, K.C4_LEVEL, v2)[support_key] for s in (sw, "CONSTANT_OCC_4H")}
    c4 = all(v >= K.C4_POWER_MIN for v in c4v.values())
    c5v = at("OCC_OFF_ON", K.C5_OFF_ON_LEVEL, v2)["d_brier_mean"]
    c5 = c5v < 0
    ok = c1 and c2 and c3 and c4 and c5
    return {"C1_null_false_support": {"pass": c1, "values": [at(s, 0, v2)[support_key] for s in NULLS]},
            "C2_null_beat": {"pass": c2, "values": [at(s, 0, v2)["p_beat"] for s in NULLS]},
            "C3_better_than_v1_switching": {"pass": c3, "support_gain_2x": c3a, "beat_gain_1x": c3b},
            "C4_power_2x": {"pass": c4, "values": c4v},
            "C5_off_on_2x_mean_dbrier": {"pass": c5, "value": c5v},
            "verdict": K.VERDICT_PASS if ok else K.VERDICT_FAIL}


def mde80(stage: dict, model: str, scenario: str, key: str = "p_support") -> float | None:
    """Smallest rho (multiples of RHO_OBS, linear interpolation over the ladder) with power >= 0.80; None if not
    reached by the top of the ladder."""
    xs = list(K.LADDER)
    ps = [stage["results"][f"{scenario}@{lv:g}"][model][key] for lv in xs]
    for i, p in enumerate(ps):
        if p >= 0.8:
            if i == 0:
                return xs[0]
            x0, x1, p0, p1 = xs[i - 1], xs[i], ps[i - 1], p
            return x0 + (0.8 - p0) * (x1 - x0) / (p1 - p0) if p1 > p0 else x1
    return None


# ------------------------------------------------------------------ diagnostics on the selected architecture
def coefficient_paths(spec: EN.Spec, n_reps: int = 5, level: float = 2.0) -> dict:
    """Mean standardized OCC coefficients per regime in SWITCHING_OCC_2H_8H (stage-2 seeds, surrogate fits)."""
    rows = load_features()
    g = EN.build_geometry(rows, K.EWMA_HALF_LIFE_WEEKS)
    sig = dgp.residual_signals(rows, g.X)
    sds = seeds_for(K.STAGE2_SEED, "SWITCHING_OCC_2H_8H", level, n_reps)
    Y = dgp.outcomes(rows, sig, "SWITCHING_OCC_2H_8H", level * K.RHO_OBS, K.KAPPA, sds, K.DRIFT_SD).astype(float)
    oc = EN.outcome_cums(g, Y)
    by = {0: [], 1: []}
    t0 = rows["close_ms"][0]
    for v, sv in g.sched.items():
        for S in (int(s) for s in sv["outer_starts"]):
            fb = EN.fit_std(g, oc, v, S, EN.b1_spec())
            if spec.structure == "STD":
                coef = EN.fit_std(g, oc, v, S, spec)["beta"][5:]
            else:
                coef = EN.fit_offset(g, oc, v, S, spec, fb)["gamma"]
            regime = int(((S - t0) // (52 * EN.K1.WEEK_MS)) % 2)
            by[regime].append(coef.mean(axis=1))
    lab = [f"OCC_{h}H" for h in EN.LOOKBACKS]
    return {("ACTIVE_OCC_2H" if k == 0 else "ACTIVE_OCC_8H"): dict(zip(lab, np.mean(v, axis=0).round(5).tolist()))
            for k, v in by.items() if v}


def exact_check(spec: EN.Spec, n_reps: int = 2, level: float = 2.0) -> list:
    """Full Newton-IRLS (with the +-5 clip) vs the surrogate for B1 and the selected V2 on every outer block."""
    rows = load_features()
    g = EN.build_geometry(rows, K.EWMA_HALF_LIFE_WEEKS)
    sig = dgp.residual_signals(rows, g.X)
    C = EN.boot_counts(g.week_ids.size, K.BOOT_DRAWS, K.BOOT_SEED)
    cnt = EN.week_counts(g)
    sds = seeds_for(K.STAGE2_SEED, "SWITCHING_OCC_2H_8H", level, n_reps)
    Y = dgp.outcomes(rows, sig, "SWITCHING_OCC_2H_8H", level * K.RHO_OBS, K.KAPPA, sds, K.DRIFT_SD).astype(float)
    sur = EN.evaluate_batch(g, Y, [spec], with_v1=False)["acc"]
    out = []
    for r in range(n_reps):
        acc = EN.Acc(g.week_ids.size, 1)
        y = Y[:, r]
        for v, sv in g.sched.items():
            for S in (int(s) for s in sv["outer_starts"]):
                ix = np.arange(g.idx_lt(v, S), g.idx_lt(v, S + EN.WF1.block_ms()))
                if ix.size == 0:
                    continue
                wm = EN._week_matrix(g, ix)
                acc.add("B1", wm, EX.predict_block(g, y, v, S, EN.b1_spec(), ix)[:, None], y[ix, None])
                acc.add(spec.name, wm, EX.predict_block(g, y, v, S, spec, ix)[:, None], y[ix, None])
        e = EN.boot_pair(C, cnt, acc.brier[spec.name], acc.brier["B1"])
        s = EN.boot_pair(C, cnt, sur.brier[spec.name][:, [r]], sur.brier["B1"][:, [r]])
        out.append({"rep": r, "exact": [float(e["point"][0]), float(e["lo"][0]), float(e["hi"][0])],
                    "surrogate": [float(s["point"][0]), float(s["lo"][0]), float(s["hi"][0])]})
    return out


def main() -> None:
    step = sys.argv[1]
    if step == "stage1":
        out = run_stage(K.STAGE1_SEED, K.STAGE1_R, K.STAGE1_R_NULL, candidates(), with_v1=False)
        out["selection"] = select(out)
        path = sys.argv[2]
    elif step == "stage2":
        s1 = json.load(open(sys.argv[2]))
        name = s1["selection"]["selected"]
        if name is None:
            raise SystemExit("NO_ELIGIBLE_ARCHITECTURE")
        spec = spec_by_name(name)
        out = run_stage(K.STAGE2_SEED, K.STAGE2_R, K.STAGE2_R_NULL, [spec, twin(spec)], with_v1=True,
                        keep=(spec.name, "V1"))
        out["selected"] = name
        out["adequacy"] = adequacy(out, name)
        out["adequacy_cw_option"] = adequacy(out, name, "p_support_cw")
        out["mde80"] = {sc: {"V2": mde80(out, name, sc), "V2_cw": mde80(out, name, sc, "p_support_cw"),
                             "V1": mde80(out, "V1", sc), "STATIC_OCC4": mde80(out, "STATIC_OCC4", sc)}
                        for sc in SIGNALS}
        path = sys.argv[3]
    elif step == "validate":
        s1 = json.load(open(sys.argv[2]))
        spec = spec_by_name(s1["selection"]["selected"])
        out = {"exact_check": exact_check(spec), "coefficient_paths_2x": coefficient_paths(spec),
               "coefficient_paths_1x": coefficient_paths(spec, level=1.0)}
        path = sys.argv[3]
    else:
        raise SystemExit("step: stage1 | stage2 | validate")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))


if __name__ == "__main__":
    main()
