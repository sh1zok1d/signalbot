"""Synthetic operating characteristics of the level race gates, monitors and state machine.

Design note: docs/research/LEVEL_RACE_CALIBRATION_MONITORING_V1_DESIGN.md. Synthetic data only: no
market bar and no real outcome is read. The worlds use the planning numbers recorded in
docs/FORECAST_LAYER_DECISION_V1.md §2 and §4 (event rates, outcome shares, the B0 spread at T+15m, the
structural BREAK offset) and nothing else.

    python -m scripts.research.level_race_calibration_sim --reps 400 --out docs/research/LEVEL_RACE_CALIBRATION_MONITORING_V1_SIM.json
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, replace
from multiprocessing import Pool

import numpy as np

from beta import level_race_calibration as L

WEEK_MS = 7 * 86_400_000
HOUR4_MS = 4 * 3_600_000
SEED = 20261008
HOLDOUT_WEEKS = 84          # 2025-01-01 → about 2026-08, minus the E1 holdout window
LIVE_WEEKS = 104


@dataclass(frozen=True)
class World:
    name: str
    rate: float              # events per week
    mu_a: float              # logit P(resolve)
    sd_a: float              # spread of the per-event logit P(resolve) known to the model
    mu_b: float              # logit P(BREAK | resolve) of B0 (geometry)
    sd_b: float
    offset: float = 0.35     # structural BREAK offset over B0 (≈ +9 pp, FORECAST_LAYER §2), known to M1
    tau: float = 0.0         # week random effect (logit), unknown to every model
    m1_noise: float = 0.10   # error of M1's offset estimate (sd, logit)
    # raw-model miscalibration on the held-out and live periods (head B / head A)
    raw_shift_b: float = 0.0
    raw_shift_a: float = 0.0
    raw_slope_b: float = 1.0
    # live drift: true shift from live week drift_week on
    drift_b: float = 0.0
    drift_a: float = 0.0
    drift_week: int = 26
    challenger_beta: float = 0.0   # effect of a challenger covariate z ~ N(0, 1) on head B (logit)


T0 = World("T0", rate=7.5, mu_a=L.logit(0.90).item(), sd_a=0.4, mu_b=L.logit(0.43).item(), sd_b=0.5)
T15 = World("T15", rate=5.0, mu_a=L.logit(0.86).item(), sd_a=0.4, mu_b=L.logit(0.37).item(), sd_b=1.0)


def gen(w: World, weeks: int, rng, *, live: bool):
    n_wk = rng.poisson(w.rate, size=weeks)
    week = np.repeat(np.arange(weeks), n_wk)
    n = week.size
    t_ms = np.sort(week * WEEK_MS + (rng.random(n) * WEEK_MS).astype(np.int64))
    ua, ub = rng.normal(0, w.tau, weeks), rng.normal(0, w.tau, weeks)
    za, zb, zc = rng.normal(size=n), rng.normal(size=n), rng.normal(size=n)
    la_model = w.mu_a + w.sd_a * za
    lb_b0 = w.mu_b + w.sd_b * zb
    lb_true_mean = lb_b0 + w.offset
    drift_on = (week >= w.drift_week) if live else np.zeros(n, bool)
    la_true = la_model + ua[week] + w.drift_a * drift_on
    lb_true = lb_true_mean + ub[week] + w.drift_b * drift_on + w.challenger_beta * zc
    ya = (rng.random(n) < L.expit(la_true)).astype(float)
    yb = (rng.random(n) < L.expit(lb_true)).astype(float)
    m1_off = w.offset + rng.normal(0, w.m1_noise)
    lb_m1 = w.raw_shift_b + w.raw_slope_b * (lb_b0 + m1_off - w.mu_b) + w.mu_b
    la_m1 = la_model + w.raw_shift_a
    beta_hat = w.challenger_beta + rng.normal(0, w.m1_noise)   # the challenger's coefficient is estimated
    lb_chal = lb_m1 + beta_hat * zc
    out = {"week": week, "t_ms": t_ms, "ya": ya, "yb": yb, "zc": zc,
           "m1": L.probs_from_heads(L.expit(la_m1), L.expit(lb_m1)),
           "b0": L.probs_from_heads(L.expit(la_model), L.expit(lb_b0)),
           "chal": L.probs_from_heads(L.expit(la_m1), L.expit(lb_chal))}
    out["outcome"] = np.where(ya == 0, "NEITHER", np.where(yb == 1, "BREAK", "REJECT"))
    return out


def records(d, *, t0_ms: int = 0, week0: int = 0):
    return [{"t_ms": int(t0_ms + d["t_ms"][i]), "resolved_ms": int(t0_ms + d["t_ms"][i] + HOUR4_MS),
             "week": int(week0 + d["week"][i]), "outcome": str(d["outcome"][i]),
             "p_raw": d["m1"][i].tolist(), "p_b0": d["b0"][i].tolist(), "p_chal_raw": d["chal"][i].tolist()}
            for i in range(d["week"].size)]


def walk_forward(recs, priors, *, start_ms: int, end_ms: int, raw_key="p_raw", pub_key="p_pub"):
    """Publish each record with the calibrator of the last cutoff before it (the prior before the first
    cutoff); returns the calibrator fitted on every record (the held-out fit)."""
    cuts = L.batch_cutoffs(start_ms, end_ms)
    cal = L.make_calibrator("SIM", start_ms, {h: {**priors[h], "n": 0} for h in L.HEADS}, priors)
    ci = -1
    for r in recs:
        while ci + 1 < len(cuts) and cuts[ci + 1] <= r["t_ms"]:
            ci += 1
            cal = _fit_key(recs, priors, cuts[ci], raw_key)
        r[pub_key] = L.apply_calibrator(cal, r[raw_key]).tolist()
    return _fit_key(recs, priors, end_ms + 1, raw_key)


def _fit_key(recs, priors, cutoff, key):
    tmp = recs if key == "p_raw" else [{**r, "p_raw": r[key]} for r in recs]
    return L.fit_calibrator("SIM", tmp, priors, cutoff_ms=cutoff)


def raw_logits_by_head(recs, key="p_raw"):
    arr = L.head_arrays(recs, key)
    return {h: L.logit(arr[h][0]) for h in L.HEADS}


# ---- one replication -------------------------------------------------------------------------------
def rep(args):
    w, seed, mode = args
    rng = np.random.default_rng(seed)
    ho = records(gen(w, HOLDOUT_WEEKS, rng, live=False))
    ho_end = HOLDOUT_WEEKS * WEEK_MS
    design = raw_logits_by_head(ho)
    base = L.identity_priors(design)
    ho_cal = walk_forward(ho, base, start_ms=0, end_ms=ho_end)
    gate = L.holdout_gate(ho)
    res = {"gate": gate["passed"], "beats_b0": L.beats_b0(gate),
           "ho_ll_gain": gate["ll_vs_b0"]["est"],
           "ho_citl": {h: gate["heads"][h]["citl"]["est"] for h in L.HEADS},
           "ho_slope": {h: gate["heads"][h]["slope"]["est"] for h in L.HEADS},
           "ho_curve": {h: gate["heads"][h]["slope"]["curve_dev_pp"] for h in L.HEADS},
           "ho_head_pass": {h: gate["heads"][h]["passed"] for h in L.HEADS},
           "ho_raw_citl": {h: gate["heads"][h]["raw_citl"]["est"] for h in L.HEADS}}
    if mode == "holdout":
        return res
    # live
    lp = L.live_priors(ho_cal, design)
    t0 = ho_end
    live = records(gen(w, LIVE_WEEKS, rng, live=True), t0_ms=t0, week0=HOLDOUT_WEEKS)
    cuts = L.batch_cutoffs(t0, t0 + LIVE_WEEKS * WEEK_MS)
    # publish every live record with the calibrator of its last cutoff (shadow: published or not)
    cal, ci, cals = L.make_calibrator("SIM", t0, {h: {**lp[h], "n": 0} for h in L.HEADS}, lp), -1, {}
    for r in live:
        while ci + 1 < len(cuts) and cuts[ci + 1] <= r["t_ms"]:
            ci += 1
            cal = L.fit_calibrator("SIM", [x for x in live if x["resolved_ms"] < cuts[ci]], lp, cutoff_ms=cuts[ci])
            cals[ci] = cal
        r["p_pub"] = L.apply_calibrator(cal, r["p_raw"]).tolist()
        if L.E_KEY == "p_ref":
            r["p_ref"] = L.apply_calibrator(ho_cal, r["p_raw"]).tolist()
    st = L.initial_state(holdout_passed=True, model_version="SIM", now_ms=t0)  # the gate is studied separately
    trans, first = [], {}
    e_thr = {10: None, 20: None, 50: None}
    for k, c in enumerate(cuts):
        done = [x for x in live if x["resolved_ms"] < c]
        if not done:
            continue
        calk = cals.get(k)
        mon = L.monitors(done, epoch_start=st.epoch_start, cal=calk, raw_logits_by_head=design)
        wk = (c - t0) // WEEK_MS
        # single-monitor first triggers from the version start (no state interplay)
        m0 = mon if st.epoch_start == 0 else L.monitors(done, epoch_start=0, cal=calk, raw_logits_by_head=design)
        for name in L.drift_reasons(m0):
            first.setdefault(name.split(":")[0], int(wk))
        for thr in e_thr:
            if e_thr[thr] is None and m0.e_max >= thr:
                e_thr[thr] = int(wk)
        new = L.next_state(st, health=L.Health(), mon=mon, now_ms=c)
        if new.state != st.state:
            trans.append((int(wk), new.state, new.reason, len(done)))
        st = new
    res.update(transitions=trans, first_trigger=first, e_first=e_thr, final_state=st.state, n_live=len(live))
    if w.challenger_beta or mode == "challenger":
        _ = walk_forward(live, lp, start_ms=t0, end_ms=t0 + LIVE_WEEKS * WEEK_MS, raw_key="p_chal_raw",
                         pub_key="p_chal")
        looks = [L.challenger_look(live[:n]) for n in range(150, 601, 150) if n <= len(live)]
        res["challenger"] = [None if x is None else {"n": x["n"], "promoted": x["promoted"],
                                                     "gain": x["gain"]["est"]} for x in looks]
    return res


# ---- scenarios ---------------------------------------------------------------------------------------
def scenarios():
    out = []
    for base in (T0, T15):
        for tau in (0.0, 0.25):
            b = replace(base, tau=tau)
            tag = f"{base.name}_tau{tau}"
            out.append((f"null_{tag}", b, "live"))
            for d in (0.3, 0.45, 0.6):
                out.append((f"drift_b{d}_{tag}", replace(b, drift_b=d), "live"))
                out.append((f"drift_b-{d}_{tag}", replace(b, drift_b=-d), "live"))
            out.append((f"drift_a0.6_{tag}", replace(b, drift_a=0.6), "live"))
            out.append((f"drift_a-0.6_{tag}", replace(b, drift_a=-0.6), "live"))
            for sh in (0.2, 0.4, 0.6):
                out.append((f"ho_shift_b{sh}_{tag}", replace(b, raw_shift_b=sh), "holdout"))
            for sl in (0.7, 1.4):
                out.append((f"ho_slope_b{sl}_{tag}", replace(b, raw_slope_b=sl), "holdout"))
            for off in (0.0, 0.2, 0.35, 0.5):
                out.append((f"ho_offset{off}_{tag}", replace(b, offset=off), "holdout"))
            for beta in (0.0, 0.15, 0.3):
                out.append((f"chal_beta{beta}_{tag}", replace(b, challenger_beta=beta), "challenger"))
    return out


def summarize(name, w, mode, rs):
    n = len(rs)
    s = {"world": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in w.__dict__.items()},
         "mode": mode, "reps": n,
         "gate_pass": np.mean([r["gate"] for r in rs]),
         "beats_b0": np.mean([r["beats_b0"] for r in rs]),
         "ho_ll_gain_mean": float(np.mean([r["ho_ll_gain"] for r in rs]))}
    for h in L.HEADS:
        s[f"ho_citl_sd_{h}"] = float(np.std([r["ho_citl"][h] for r in rs]))
        s[f"ho_curve_p90_{h}"] = float(np.nanquantile([np.nan if r["ho_curve"][h] is None else r["ho_curve"][h]
                                                        for r in rs], 0.9))
        s[f"ho_head_pass_{h}"] = float(np.mean([r["ho_head_pass"][h] for r in rs]))
        s[f"ho_slope_sd_{h}"] = float(np.nanstd([np.nan if r["ho_slope"][h] is None else r["ho_slope"][h] for r in rs]))
    if mode in ("live", "challenger"):
        def frac(pred):
            return float(np.mean([pred(r) for r in rs]))
        dw = w.drift_week
        fb = [next((t for t in r["transitions"] if t[1] == "FALLBACK"), None) for r in rs]
        live_at = [next((t[0] for t in r["transitions"] if t[1] == "L3_LIVE"), None) for r in rs]
        s.update(
            fallback_any=frac(lambda r: any(t[1] == "FALLBACK" for t in r["transitions"])),
            fallback_by_52w=float(np.mean([f is not None and f[0] <= 52 for f in fb])),
            fallback_before_drift=float(np.mean([f is not None and f[0] < dw for f in fb])),
            fallback_within_26w_of_drift=float(np.mean([f is not None and dw <= f[0] < dw + 26 for f in fb])),
            fallback_within_52w_of_drift=float(np.mean([f is not None and dw <= f[0] < dw + 52 for f in fb])),
            median_weeks_to_fallback_after_drift=(None if not [f for f in fb if f and f[0] >= dw] else
                                                  float(np.median([f[0] - dw for f in fb if f and f[0] >= dw]))),
            l3_live_reached=float(np.mean([x is not None for x in live_at])),
            l3_live_median_week=(None if not [x for x in live_at if x is not None] else
                                 float(np.median([x for x in live_at if x is not None]))),
            returns=frac(lambda r: any(t[2] == "recovered" for t in r["transitions"])),
            flaps_2plus=frac(lambda r: sum(t[1] == "FALLBACK" for t in r["transitions"]) >= 2),
            final_fallback=frac(lambda r: r["final_state"] == "FALLBACK"),
            first_trigger_any_104w={k: float(np.mean([k in r["first_trigger"] for r in rs]))
                                    for k in ("e_process", "rolling_intercept", "worse_than_b0", "large_correction")},
            first_trigger_before_drift={k: float(np.mean([r["first_trigger"].get(k, 999) < dw for r in rs]))
                                        for k in ("e_process", "rolling_intercept", "worse_than_b0", "large_correction")},
            e_first_any={str(k): float(np.mean([r["e_first"][k] is not None for r in rs])) for k in (10, 20, 50)},
            e_first_before_drift={str(k): float(np.mean([(r["e_first"][k] or 999) < dw for r in rs]))
                                  for k in (10, 20, 50)},
            n_live_mean=float(np.mean([r["n_live"] for r in rs])))
    if mode == "challenger":
        looks = [r.get("challenger") or [] for r in rs]
        s["challenger_promoted_any"] = float(np.mean([any(x and x["promoted"] for x in lk) for lk in looks]))
        s["challenger_promoted_by_look"] = [float(np.mean([len(lk) > i and lk[i] is not None and lk[i]["promoted"]
                                                          for lk in looks])) for i in range(4)]
        s["challenger_gain_mean_at_600"] = float(np.nanmean([lk[3]["gain"] if len(lk) > 3 and lk[3] else np.nan
                                                             for lk in looks]))
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}


def _apply(overrides):
    for k, v in overrides.items():
        if not hasattr(L, k):
            raise SystemExit(f"unknown constant {k}")
        cur = getattr(L, k)
        setattr(L, k, v if isinstance(cur, str) else type(cur)(v))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=400)
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--set", action="append", default=[], help="NAME=VALUE: override a module constant")
    a = ap.parse_args()
    overrides = {k: (v if not v.replace(".", "", 1).lstrip("-").isdigit() else float(v))
                 for k, v in (x.split("=", 1) for x in a.set)}
    out = {"design": "docs/research/LEVEL_RACE_CALIBRATION_MONITORING_V1_DESIGN.md", "seed": SEED,
           "synthetic_only": True, "holdout_weeks": HOLDOUT_WEEKS, "live_weeks": LIVE_WEEKS,
           "calibration_version": L.LR_CAL_VERSION, "state_version": L.LR_STATE_VERSION, "scenarios": {}}
    _apply(overrides)
    out["overrides"] = overrides
    with Pool(a.procs, initializer=_apply, initargs=(overrides,)) as pool:
        for k, (name, w, mode) in enumerate(scenarios()):
            if a.only and a.only not in name:
                continue
            t = time.time()
            rs = pool.map(rep, [(w, SEED + 100_000 * k + i, mode) for i in range(a.reps)])
            out["scenarios"][name] = summarize(name, w, mode, rs)
            print(name, round(time.time() - t, 1), json.dumps({kk: v for kk, v in out["scenarios"][name].items()
                                                              if kk != "world"}), flush=True)
            if a.out:
                with open(a.out, "w") as f:
                    json.dump(out, f, indent=1, sort_keys=True)
                    f.write("\n")


if __name__ == "__main__":
    main()
