"""RP4H_TREND_EXHAUSTION_INTERACTION_V1 — outcome-free information-adequacy gate.

    python -m scripts.research.rp4h_trend_exhaustion_v1.study gate OUT.json       # calibration, Monte Carlo, adequacy
    python -m scripts.research.rp4h_trend_exhaustion_v1.study validate OUT.json   # canonical re-rank bootstrap check
Real features and support of each candidate surface; synthetic outcomes only. No market interaction outcome is read."""
from __future__ import annotations

import json
import sys
import time

import numpy as np

from . import constants as K
from . import dgp
from . import estimator as E
from .surfaces import load

BATCH = 50


def prepare(name: str) -> dict:
    rows = load(name)
    sig = dgp.signals(rows)
    p_int = E.Partial(E.product_term(rows["rp"], rows["ts"]), [rows[c] for c in K.PRIMARY_CONTROLS], rows["week"])
    p_main = E.Partial(rows["rp"], [rows["ret4"], rows["rv4"]], rows["week"])
    return {"rows": rows, "sig": sig, "p_int": p_int, "p_main": p_main,
            "C": E.boot_counts(p_int.W, K.BOOT_DRAWS, K.BOOT_SEED),
            "noise": {"HETERO": dgp.noise_parts(rows, True), "HOMO": dgp.noise_parts(rows, False)}}


def _draws(P: dict, dgp_name: str, bm: float, bi: float, seeds: list) -> np.ndarray:
    s, sigma = P["noise"][dgp_name]
    return np.column_stack([dgp.latent(P["rows"], P["sig"], s, sigma, bm, bi, sd) for sd in seeds])


def calibrate(P: dict, sid: int, dgp_name: str) -> dict:
    """Paired: rho(estimator) with and without beta * sigma * g on the same noise draw."""
    seeds = [(K.STUDY_SEED, 900 + sid, 1 if dgp_name == "HETERO" else 2, r) for r in range(K.CALIB_DRAWS)]
    y0 = _draws(P, dgp_name, 0.0, 0.0, seeds)
    ym = _draws(P, dgp_name, K.CALIB_BETA, 0.0, seeds)
    km = (P["p_main"].rho(P["p_main"].residual_y(ym)) - P["p_main"].rho(P["p_main"].residual_y(y0))) / K.CALIB_BETA
    b_main = K.MAIN_RP4H_PARTIAL / float(km.mean())
    y0 = _draws(P, dgp_name, b_main, 0.0, seeds)
    yi = _draws(P, dgp_name, b_main, K.CALIB_BETA, seeds)
    ki = (P["p_int"].rho(P["p_int"].residual_y(yi)) - P["p_int"].rho(P["p_int"].residual_y(y0))) / K.CALIB_BETA
    return {"kappa_main": float(km.mean()), "kappa_main_se": float(km.std(ddof=1) / np.sqrt(km.size)),
            "kappa_int": float(ki.mean()), "kappa_int_se": float(ki.std(ddof=1) / np.sqrt(ki.size)),
            "beta_main": b_main}


def simulate(P: dict, sid: int, dgp_name: str, cal: dict, level: float, reps: int, seed: int) -> dict:
    bi = level * K.DISCOVERY_INTERACTION_B0 / cal["kappa_int"]
    pts, los, his, ses, valid, mains = [], [], [], [], [], []
    for b0 in range(0, reps, BATCH):
        seeds = [(seed, sid, int(round(level * 10)), r) for r in range(b0, min(reps, b0 + BATCH))]
        Y = _draws(P, dgp_name, cal["beta_main"], bi, seeds)
        ey = P["p_int"].residual_y(Y)
        pts.append(P["p_int"].rho(ey))
        ci = E.fast_ci(P["C"], P["p_int"].week_sums(ey))
        los.append(ci["lo"]), his.append(ci["hi"]), ses.append(ci["se"]), valid.append(ci["valid"])
        if b0 == 0:
            mains.append(P["p_main"].rho(P["p_main"].residual_y(Y)))
    pt, lo, hi = np.concatenate(pts), np.concatenate(los), np.concatenate(his)
    se, va = np.concatenate(ses), np.concatenate(valid)
    routes = [E.route(float(a), float(b), float(c), int(d)) for a, b, c, d in zip(pt, lo, hi, va)]
    share = lambda r: float(np.mean([x == r for x in routes]))
    w = hi - lo
    return {"level": level, "reps": int(pt.size), "beta_int": bi,
            "p_supported": share(K.ROUTE_SUPPORTED), "p_uncertain": share(K.ROUTE_UNCERTAIN),
            "p_not": share(K.ROUTE_NOT), "p_opposes": share(K.ROUTE_OPPOSES), "p_invalid": share(K.ROUTE_INVALID),
            "p_correct_sign": float(np.mean(pt < 0)), "mean_point": float(pt.mean()), "sd_point": float(pt.std(ddof=1)),
            "mean_se": float(se.mean()),
            "ci_width_q": {q: float(np.quantile(w, float(q))) for q in ("0.05", "0.5", "0.95")},
            "main_effect_check_mean": float(np.mean(mains[0])),
            "_pt": pt.tolist(), "_se": se.tolist()}


def mde80(curve: list) -> float | None:
    xs = [c["level"] for c in curve]
    ps = [c["p_supported"] for c in curve]
    for i, p in enumerate(ps):
        if p >= 0.8 and i > 0:
            x0, x1, p0 = xs[i - 1], xs[i], ps[i - 1]
            return x0 + (0.8 - p0) * (x1 - x0) / (p - p0) if p > p0 else x1
    return None


def pooled(a: list, b: list) -> list:
    """Informational only: inverse-variance combination of the two surfaces' estimates, replication by replication."""
    out = []
    for ca, cb in zip(a, b):
        pa, pb, sa, sb = (np.array(ca["_pt"]), np.array(cb["_pt"]), np.array(ca["_se"]), np.array(cb["_se"]))
        wa, wb = 1 / sa ** 2, 1 / sb ** 2
        est = (wa * pa + wb * pb) / (wa + wb)
        se = 1 / np.sqrt(wa + wb)
        out.append({"level": ca["level"], "p_supported": float(np.mean(est + 1.96 * se < 0)),
                    "p_opposes": float(np.mean(est - 1.96 * se > 0)), "p_correct_sign": float(np.mean(est < 0)),
                    "mean_se": float(se.mean())})
    return out


def adequacy(curve: list, sens: list) -> dict:
    at = lambda cv, lv: next(c for c in cv if c["level"] == lv)
    n0, n1 = at(curve, 0.0), at(curve, 1.0)
    s0, s1 = at(sens, 0.0), at(sens, 1.0)
    a1 = n0["p_supported"] <= K.NULL_FALSE_SUPPORT_MAX and n0["p_opposes"] <= K.NULL_FALSE_SUPPORT_MAX
    a1s = s0["p_supported"] <= K.NULL_FALSE_SUPPORT_MAX and s0["p_opposes"] <= K.NULL_FALSE_SUPPORT_MAX
    a2 = n1["p_supported"] >= K.POWER_MIN_AT_1X
    a2s = s1["p_supported"] >= K.POWER_MIN_AT_1X
    return {"null_control_primary": a1, "null_control_sensitivity": a1s, "power_1x_primary": n1["p_supported"],
            "power_1x_sensitivity": s1["p_supported"], "adequate": bool(a1 and a1s and a2 and a2s)}


def surface_rule(adq: dict, fresh: dict) -> dict:
    """Owner's frozen rule: modern first if adequate; else BitMEX if adequate (modern stability unresolved); else none.
    A surface with an EXACT or EQUIVALENT prior read of the interaction (exposure audit) is not eligible."""
    bm, bn = K.SURFACES
    ok = {s: adq[s]["adequate"] and fresh.get(s, False) for s in K.SURFACES}
    if ok[bn]:
        return {"selected": bn, "reason": "Binance 2025-26 adequately powered at 1x: tests modern stability directly"}
    if ok[bm]:
        return {"selected": bm, "reason": "modern surface underpowered (or not fresh); BitMEX adequately powered; "
                                          "modern stability remains unresolved"}
    return {"selected": None, "verdict": K.VERDICT_INSUFFICIENT,
            "reason": "neither surface is adequately powered (and fresh) at 1x the discovery magnitude"}


def gate() -> dict:
    t0 = time.time()
    out = {"unit": K.UNIT, "stage": K.STAGE, "market_interaction_outcome_read": False, "surfaces": {}}
    curves = {}
    for sid, name in enumerate(K.SURFACES):
        P = prepare(name)
        cal = {d: calibrate(P, sid, d) for d in ("HETERO", "HOMO")}
        curve = [simulate(P, sid, "HETERO", cal["HETERO"], lv, K.REPS, K.STUDY_SEED) for lv in K.LADDER]
        sens = [simulate(P, sid, "HOMO", cal["HOMO"], lv, K.SENS_REPS, K.SENS_SEED) for lv in K.SENS_LEVELS]
        curves[name] = curve
        out["surfaces"][name] = {"support": P["rows"]["support"], "calibration": cal,
                                 "curve": [{k: v for k, v in c.items() if not k.startswith("_")} for c in curve],
                                 "sensitivity_homoskedastic": [{k: v for k, v in c.items() if not k.startswith("_")}
                                                               for c in sens],
                                 "mde80_primary": mde80(curve), "adequacy": adequacy(curve, sens)}
        print(name, "done", round(time.time() - t0), "s", flush=True)
    out["pooled_informational"] = pooled(curves[K.SURFACES[0]], curves[K.SURFACES[1]])
    out["seconds"] = round(time.time() - t0, 1)
    return out


def validate() -> dict:
    """Canonical (re-rank) bootstrap and the imported Unit-1 point estimator against the fast versions."""
    res = []
    for sid, name in enumerate(K.SURFACES):
        P = prepare(name)
        cal = calibrate(P, sid, "HETERO")
        bi = K.DISCOVERY_INTERACTION_B0 / cal["kappa_int"]
        for r in range(K.VALIDATE_REPS):
            y = _draws(P, "HETERO", cal["beta_main"], bi, [(K.STUDY_SEED, 700 + sid, 10, r)])
            ey = P["p_int"].residual_y(y)
            fast = E.fast_ci(P["C"], P["p_int"].week_sums(ey))
            can = E.canonical_ci(P["rows"], y[:, 0])
            res.append({"surface": name, "rep": r, "point_fast": float(P["p_int"].rho(ey)[0]),
                        "point_unit1": float(E.interaction_point(P["rows"], y[:, 0])),
                        "fast": [float(fast["lo"][0]), float(fast["hi"][0]), float(fast["se"][0])],
                        "canonical": [can["lo"], can["hi"], can["se"]],
                        "width_ratio": (can["hi"] - can["lo"]) / float(fast["hi"][0] - fast["lo"][0])})
            print(res[-1], flush=True)
    return {"checks": res, "max_width_ratio": max(c["width_ratio"] for c in res),
            "redo_threshold": K.CI_WIDTH_RATIO_REDO}


def main() -> None:
    step, path = sys.argv[1], sys.argv[2]
    out = gate() if step == "gate" else validate() if step == "validate" else None
    if out is None:
        raise SystemExit("step: gate | validate")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
