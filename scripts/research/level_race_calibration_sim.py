"""Synthetic operating characteristics of the level race calibrator, gates, monitors and states.

Design note: docs/research/LEVEL_RACE_CALIBRATION_MONITORING_V1_DESIGN.md. Synthetic data only: no market
bar and no real outcome is read. The worlds use planning numbers from docs/FORECAST_LAYER_DECISION_V1.md
§2/§4 and the descriptive development numbers F1 recorded and the mini-head relayed
(LEVEL_RACE_FORECAST_V1_DESIGN.md §11b: level − generic intercepts R +0.92 / B +0.33, head B slope 0.78);
those are disclosed as dev-informed in the design note.

    python -m scripts.research.level_race_calibration_sim --reps 200 --out docs/research/LEVEL_RACE_CALIBRATION_MONITORING_V1_SIM.json
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
HOLDOUT_WEEKS = 84
LIVE_WEEKS = 104
LEVELS = ("LEVEL_T0", "LEVEL_T15")


@dataclass(frozen=True)
class World:
    tau: float = 0.25                 # weekly random effect (logit) on every class and head, unknown to models
    gen_rate: float = 40.0            # independent generic 4h windows per week
    t0_rate: float = 7.5
    t15_rate: float = 5.0
    off_r: tuple = (1.07, 0.74)       # level − generic intercept, head R (T0, T15): F1 dev
    off_b: tuple = (0.33, 0.32)       # head B
    b0_gap_r: float = 0.45            # raw B0 misses part of the level offset (dev: B0 CITL +5.7 / −4.1 pp)
    b0_gap_b: float = 0.20
    level_slope_b: float = 1.0        # truth slope of head B on the level classes vs M1 (R3: 0.78)
    generic_slope_b: float = 1.0      # truth slope of head B on the generic stream vs G1
    m1_noise: float = 0.10            # M1 estimation error of its level terms (logit SD)
    shift_b: float = 0.0              # held-out + live miscalibration of M1 head B (logit)
    drift_b: float = 0.0              # live drift of the level truth, head B, from live week drift_week
    drift_r: float = 0.0
    drift_week: int = 26
    drift_slope_b: float = 0.0        # > 0: the level head-B truth slope becomes this from drift_week
    drift_market: bool = False        # drifts also apply to the generic stream (a market-wide shift)
    level_effect: float = 1.0         # 0: no level effect in truth (M1's offset wrong)
    chal_beta: float = 0.0            # C1 covariate effect on head B, T15 only
    s_level: float = 1.0
    s_slope_level: float = -1.0       # < 0: the module default (PRIOR_S_SLOPE_LEVEL); 0: one shared slope
    level_raw_fb: bool = False        # level rows feed the calibrator G1@event raw (F1 R2 diagnostic) instead of M1


def _cls_params(w: World, c: str):
    if c == "GENERIC":
        return dict(rate=w.gen_rate, mu_r=L.logit(0.75).item(), sd_r=0.6, mu_b=0.0, sd_b=1.0, off_r=0.0, off_b=0.0)
    k = LEVELS.index(c)
    return dict(rate=(w.t0_rate, w.t15_rate)[k], mu_r=L.logit(0.75).item(), sd_r=0.5, mu_b=-0.3,
                sd_b=(0.5, 1.0)[k], off_r=w.off_r[k] * w.level_effect, off_b=w.off_b[k] * w.level_effect)


def gen(w: World, c: str, weeks: int, week0: int, rng, *, live: bool, u):
    p = _cls_params(w, c)
    n_wk = rng.poisson(p["rate"], size=weeks)
    week = np.repeat(np.arange(weeks), n_wk)
    n = week.size
    t_ms = np.sort(week * WEEK_MS + (rng.random(n) * WEEK_MS).astype(np.int64)) + week0 * WEEK_MS
    zr, zb, zc = rng.normal(size=n), rng.normal(size=n), rng.normal(size=n)
    lvl = c != "GENERIC"
    k = LEVELS.index(c) if lvl else 0
    g1_r = p["mu_r"] + p["sd_r"] * zr                    # generic model (G1, or G1@event at a level)
    g1_b = p["mu_b"] + p["sd_b"] * zb
    m1_r = g1_r + (w.off_r[k] + rng.normal(0, w.m1_noise) if lvl else 0.0)
    m1_b = g1_b + (w.off_b[k] + rng.normal(0, w.m1_noise) + w.shift_b if lvl else 0.0)
    slope = w.level_slope_b if lvl else w.generic_slope_b
    tr_r = g1_r + p["off_r"]
    tr_b_mean = g1_b + p["off_b"]
    centre = p["mu_b"] + p["off_b"]
    on = (week >= w.drift_week) if (live and (lvl or w.drift_market)) else np.zeros(n, bool)
    slope_arr = np.where(on, w.drift_slope_b, slope) if w.drift_slope_b > 0 else slope
    tr_b = centre + slope_arr * (tr_b_mean - centre)
    tr_r = tr_r + u[week + week0] + w.drift_r * on
    tr_b = tr_b + u[week + week0] + w.drift_b * on
    if c == "LEVEL_T15":
        tr_b = tr_b + w.chal_beta * zc
    ya = rng.random(n) < L.expit(tr_r)
    yb = rng.random(n) < L.expit(tr_b)
    outcome = np.where(~ya, "NEITHER", np.where(yb, "BREAK", "REJECT"))
    m1 = L.probs_from_heads(L.expit(m1_r), L.expit(m1_b))
    fb = L.probs_from_heads(L.expit(g1_r), L.expit(g1_b))
    b0 = L.probs_from_heads(L.expit(m1_r - w.b0_gap_r * lvl), L.expit(m1_b - w.b0_gap_b * lvl))
    beta_hat = w.chal_beta + rng.normal(0, w.m1_noise)
    chal = L.probs_from_heads(L.expit(m1_r), L.expit(m1_b + beta_hat * zc)) if c == "LEVEL_T15" else m1
    return [{"cal_class": c, "t_ms": int(t_ms[i]), "resolved_ms": int(t_ms[i] + HOUR4_MS),
             "week": int(week[i] + week0), "outcome": str(outcome[i]), "weight": 1.0,
             "p_raw": (m1[i] if lvl and not w.level_raw_fb else fb[i]).tolist(), "p_fb_raw": fb[i].tolist(),
             "p_b0": b0[i].tolist(), "p_chal_raw": chal[i].tolist()} for i in range(n)]


def publish(recs, prior, cuts):
    """Walk forward: each record gets the calibrator of the last cutoff ≤ its issue time."""
    order = sorted(recs, key=lambda r: r["t_ms"])
    p0 = L.prior_calibrator(prior)
    versions = [L.fit_calibrator(order, prior, cutoff_ms=c) for c in cuts]
    for r in order:
        r["_cal"] = L.calibrator_at(r["t_ms"], versions, p0)
    return order, [(v.cutoff_ms, v) for v in versions]


def stamp(recs, case):
    for r in recs:
        cal = r.pop("_cal")
        if r["cal_class"] == "GENERIC":
            continue
        r["p_champ"] = L.apply_calibrator(cal, r["p_raw"], r["cal_class"]).tolist()
        r["p_fb"] = L.apply_calibrator(cal, r["p_fb_raw"], "GENERIC").tolist()
        r["p_pub"] = r["p_champ"] if case[r["cal_class"]] == "A" else r["p_fb"]


def rep_generic(w, seed):
    """The generic-stream monitor alone: held-out walk-forward and final fit, p_ref under the frozen
    held-out map with the held-out margin, the alarm state at every live cutoff."""
    rng = np.random.default_rng(seed)
    u = rng.normal(0, w.tau, HOLDOUT_WEEKS + LIVE_WEEKS)
    prior0 = {h: L.identity_prior() for h in L.HEADS}
    ho = gen(w, "GENERIC", HOLDOUT_WEEKS, 0, rng, live=False, u=u)
    ho_end = HOLDOUT_WEEKS * WEEK_MS
    ho_final = L.fit_calibrator(ho, prior0, cutoff_ms=ho_end + 1)
    for r in ho:
        r["p_ref"] = L.apply_calibrator(ho_final, r["p_raw"], "GENERIC").tolist()
    oa = L.outcome_arrays(ho, "p_ref")
    margin = {}
    for o in L.OUTCOMES:
        c = L.citl(*oa[o])
        margin[o] = (c["hi"] - c["lo"]) / 200 if c["lo"] is not None else 0.0
    live = gen(w, "GENERIC", LIVE_WEEKS, HOLDOUT_WEEKS, rng, live=True, u=u)
    for r in live:
        r["p_ref"] = L.apply_calibrator(ho_final, r["p_raw"], "GENERIC").tolist()
    gs, alarms, clears = L.GenericState(), [], []
    for wk in range(1, LIVE_WEEKS + 1):
        cut = ho_end + wk * WEEK_MS
        done = [r for r in live if r["resolved_ms"] < cut]
        new = L.next_generic_state(gs, done, margin=margin, now_ms=cut)
        if new.alarm and not gs.alarm:
            alarms.append((wk, sum(1 for r in done if r["week"] - HOLDOUT_WEEKS >= w.drift_week)))
        if gs.alarm and not new.alarm:
            clears.append(wk)
        gs = new
    return {"alarms": alarms, "clears": clears, "margin": margin}


def rep(args):
    w, seed, mode = args
    if mode == "generic":
        return rep_generic(w, seed)
    rng = np.random.default_rng(seed)
    u = rng.normal(0, w.tau, HOLDOUT_WEEKS + LIVE_WEEKS)
    prior0 = {h: L.identity_prior(w.s_level, None if w.s_slope_level < 0 else w.s_slope_level) for h in L.HEADS}
    ho = [r for c in L.CAL_CLASSES for r in gen(w, c, HOLDOUT_WEEKS, 0, rng, live=False, u=u)]
    ho_end = HOLDOUT_WEEKS * WEEK_MS
    ho, _ = publish(ho, prior0, L.batch_cutoffs(0, ho_end))
    ho_final = L.fit_calibrator(ho, prior0, cutoff_ms=ho_end + 1)
    stamp(ho, {c: "A" for c in LEVELS})
    case, setup, res = {}, {}, {"classes": {}}
    for c in LEVELS:
        rc = [r for r in ho if r["cal_class"] == c]
        bb0, bfb = L.beats(rc, "p_raw", "p_b0"), L.beats(rc, "p_raw", "p_fb_raw")
        a = bb0 and bfb
        case[c] = "A" if a else "B"
        for r in rc:
            r["p_pub"] = r["p_champ"] if a else r["p_fb"]
        g, gc = L.gates(rc, "p_pub"), L.gates(rc, "p_champ")
        fb_g2 = L.g2_only(rc, "p_fb")
        setup[c] = L.Setup(mode="MODEL", case=case[c], holdout_passed=g["passed"], fallback_g2_holdout=fb_g2)
        res["classes"][c] = {
            "case": case[c], "beats_b0": bb0, "beats_g1": bfb,
            "gain_b0": L.paired_log_loss(rc, "p_raw", "p_b0")["est"],
            "gain_g1": L.paired_log_loss(rc, "p_raw", "p_fb_raw")["est"],
            "margin": {o: (gc["G2"]["outcomes"][o]["hi"] - gc["G2"]["outcomes"][o]["lo"]) / 200
                       if gc["G2"]["outcomes"][o]["lo"] is not None else 0.0 for o in L.OUTCOMES},
            "gate": g["passed"], "G1": g["G1"]["pass"], "G2": g["G2"]["pass"], "G3": g["G3"]["pass"],
            "champ_gate": gc["passed"], "champ_G2": gc["G2"]["pass"], "champ_G3": gc["G3"]["pass"],
            "champ_slope_B": gc["G3"]["heads"]["B"]["est"], "fb_g2": fb_g2, "n_ho": len(rc),
            "citl_champ": {o: gc["G2"]["outcomes"][o]["est"] for o in L.OUTCOMES}}
    res["ho_b"], res["ho_r"] = ho_final.heads["B"]["mean"], ho_final.heads["R"]["mean"]
    if mode == "holdout":
        return res
    lp = L.live_prior(ho_final, ho)
    live = [r for c in L.CAL_CLASSES for r in gen(w, c, LIVE_WEEKS, HOLDOUT_WEEKS, rng, live=True, u=u)]
    cuts = L.batch_cutoffs(ho_end, ho_end + LIVE_WEEKS * WEEK_MS)
    if mode == "challenger":
        chal = [{**r, "p_raw": r["p_chal_raw"]} for r in live]
        chal, _ = publish(chal, lp, cuts)
        cmap = {(r["cal_class"], r["t_ms"]): L.apply_calibrator(r.pop("_cal"), r["p_raw"], r["cal_class"]).tolist()
                for r in chal}
    live, cals = publish(live, lp, cuts)
    stamp(live, case)
    for r in live:
        if r["cal_class"] != "GENERIC":
            r["p_ref"] = L.apply_calibrator(ho_final, r["p_raw"], r["cal_class"]).tolist()
    if mode == "challenger":
        t15 = [r for r in live if r["cal_class"] == "LEVEL_T15"]
        for r in t15:
            r["p_chal"], r["p_pub"] = cmap[("LEVEL_T15", r["t_ms"])], r["p_champ"]
        looks = [L.challenger_look(t15[:n]) for n in (150, 300, 450, 600) if n <= len(t15)]
        res["challenger"] = [{"n": x["n"], "promoted": x["promoted"], "gain": x["gain"]["est"]} for x in looks if x]
        return res
    res["live_b"] = cals[-1][1].heads["B"]["mean"] if cals else None
    for c in LEVELS:
        lv = [r for r in live if r["cal_class"] == c]
        st = L.initial_state(setup[c], now_ms=ho_end)
        trans, first = [(0, st.state, st.reason)], {}
        fbk = "p_fb" if case[c] == "A" else None
        for cut in cuts:
            done = [r for r in lv if r["resolved_ms"] < cut]
            if not done:
                continue
            wk = (cut - ho_end) // WEEK_MS
            ep = min(st.epoch_start, len(done))
            m = L.monitors(done, key="p_pub", epoch_start=ep, fallback_key=fbk)
            mf = L.monitors(done, key="p_fb", epoch_start=ep, fallback_key=None) if fbk else None
            m0 = m if ep == 0 else L.monitors(done, key="p_pub", epoch_start=0, fallback_key=fbk)
            for why in L.drift_reasons(m0):
                first.setdefault(why.split(":")[0], int(wk))
            if "D1ref" not in first and L.d1_triggered(L.d1_value(done, "p_ref")):
                first["D1ref"] = int(wk)
            if "D1reftol" not in first:
                pth = L.d1_paths(done, "p_ref", margin=res["classes"][c]["margin"])
                if L.d1_triggered({"e": dict(zip(L.OUTCOMES, pth[-1]))}):
                    first["D1reftol"] = int(wk)
            new = L.next_state(st, setup[c], health=L.Health(), mon=m, mon_fb=mf, now_ms=cut)
            if new.state != st.state:
                trans.append((int(wk), new.state, new.reason, len(done)))
            st = new
        n_pre = sum(1 for r in lv if r["week"] - HOLDOUT_WEEKS < w.drift_week)
        res["classes"][c].update(transitions=trans, first=first, final=st.state, n_live=len(lv), n_pre=n_pre)
    return res


def scenarios():
    base = World()
    out = [("null", base, "live"), ("null_tau0", replace(base, tau=0.0), "live"),
           ("r3_level_only", replace(base, level_slope_b=0.78), "live"),
           ("r3_shared", replace(base, level_slope_b=0.78, generic_slope_b=0.78), "live"),
           ("r3_level_only_tied", replace(base, level_slope_b=0.78, s_slope_level=0.0), "live"),
           ("r3_shared_tied", replace(base, level_slope_b=0.78, generic_slope_b=0.78, s_slope_level=0.0), "live"),
           ("no_level_effect", replace(base, level_effect=0.0), "live")]
    for d in (0.3, 0.45, 0.6):
        out.append((f"drift_b+{d}", replace(base, drift_b=d), "live"))
        out.append((f"drift_b-{d}", replace(base, drift_b=-d), "live"))
    out += [("drift_r-0.6", replace(base, drift_r=-0.6), "live"), ("drift_r+0.6", replace(base, drift_r=0.6), "live")]
    out += [("gen_null", base, "generic"), ("gen_null_tau0", replace(base, tau=0.0), "generic"),
            ("gen_b+0.4", replace(base, drift_b=0.4, drift_market=True), "generic"),
            ("gen_b-0.4", replace(base, drift_b=-0.4, drift_market=True), "generic"),
            ("gen_r-0.4", replace(base, drift_r=-0.4, drift_market=True), "generic"),
            ("gen_r+0.4", replace(base, drift_r=0.4, drift_market=True), "generic")]
    out += [("delay_b+0.4", replace(base, drift_b=0.4), "live"), ("delay_b-0.4", replace(base, drift_b=-0.4), "live"),
            ("delay_slope0.7", replace(base, drift_slope_b=0.7), "live")]
    out += [(f"ho_shift_b{sh}", replace(base, shift_b=sh), "holdout") for sh in (0.2, 0.4, 0.6)]
    out += [("ho_dev_gains", replace(base, b0_gap_r=0.6, b0_gap_b=0.25), "holdout"),
            ("ho_dev_gains_tau0", replace(base, b0_gap_r=0.6, b0_gap_b=0.25, tau=0.0), "holdout")]
    out += [(f"ho_s_level{s}", replace(base, s_level=s), "holdout") for s in (0.5, 1.0, 1.5)]
    out += [(f"ho_fbraw_s_level{s}", replace(base, s_level=s, level_raw_fb=True), "holdout") for s in (0.5, 1.0, 1.5)]
    out += [(f"chal_beta{b}", replace(base, chal_beta=b), "challenger") for b in (0.0, 0.2, 0.35)]
    return out


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def summarize_generic(w, rs):
    dw = w.drift_week
    first = [r["alarms"][0] if r["alarms"] else None for r in rs]
    pre = [f is not None and f[0] < dw for f in first]
    post = [(f[0] - dw, f[1]) if f is not None and f[0] >= dw else (float("inf"), float("inf")) for f in first]
    post = [p for p, b in zip(post, pre) if not b]
    wk = [p[0] for p in post]
    ev = [p[1] for p in post]
    med = (lambda xs: float(np.median(xs)) if xs and np.isfinite(np.median(xs)) else None)
    return {"world": dict(w.__dict__), "mode": "generic", "reps": len(rs),
            "alarm_by_52w": _mean([f is not None and f[0] <= 52 for f in first]),
            "alarm_by_104w": _mean([f is not None for f in first]),
            "alarm_before_onset": _mean(pre),
            "delay_median_weeks": med(wk), "delay_median_events": med(ev),
            "detected_within_8w": _mean([x <= 8 for x in wk]), "detected_within_26w": _mean([x <= 26 for x in wk]),
            "cleared_after_alarm": _mean([bool(r["clears"]) for r in rs if r["alarms"]]) if any(r["alarms"] for r in rs) else None,
            "margin_mean_pp": {o: _mean([r["margin"][o] * 100 for r in rs]) for o in L.OUTCOMES}}


def summarize(w, mode, rs):
    if mode == "generic":
        return summarize_generic(w, rs)
    s = {"world": dict(w.__dict__), "mode": mode, "reps": len(rs),
         "ho_b": [_mean([r["ho_b"][k] for r in rs]) for k in range(len(rs[0]["ho_b"]))],
         "ho_r": [_mean([r["ho_r"][k] for r in rs]) for k in range(len(rs[0]["ho_r"]))], "classes": {}}
    if mode == "challenger":
        looks = [r.get("challenger") or [] for r in rs]
        s["promoted_any"] = _mean([any(x["promoted"] for x in lk) for lk in looks])
        s["promoted_by_look"] = [_mean([len(lk) > i and lk[i]["promoted"] for lk in looks]) for i in range(4)]
        s["looks_reached"] = [_mean([len(lk) > i for lk in looks]) for i in range(4)]
        return s
    if mode == "live":
        s["live_b"] = [_mean([r["live_b"][k] for r in rs if r.get("live_b")]) for k in range(len(rs[0]["ho_b"]))]
    for c in LEVELS:
        cs = [r["classes"][c] for r in rs]
        d = {"case_A": _mean([x["case"] == "A" for x in cs]), "gate_pass": _mean([x["gate"] for x in cs]),
             "beats_b0": _mean([x["beats_b0"] for x in cs]), "beats_g1": _mean([x["beats_g1"] for x in cs]),
             "gain_b0": _mean([x["gain_b0"] for x in cs]), "gain_g1": _mean([x["gain_g1"] for x in cs]),
             "G1": _mean([x["G1"] for x in cs]), "G2": _mean([x["G2"] for x in cs]), "G3": _mean([x["G3"] for x in cs]),
             "champ_gate": _mean([x["champ_gate"] for x in cs]), "champ_G2": _mean([x["champ_G2"] for x in cs]),
             "champ_G3": _mean([x["champ_G3"] for x in cs]), "champ_slope_B": _mean([x["champ_slope_B"] for x in cs]),
             "fb_g2": _mean([x["fb_g2"] for x in cs]), "n_ho": _mean([x["n_ho"] for x in cs]),
             "citl_champ": {o: _mean([x["citl_champ"][o] for x in cs]) for o in L.OUTCOMES}}
        if mode == "live":
            dw = w.drift_week

            def first_exit(x):
                return next((t for t in x["transitions"][1:] if t[2].startswith(("drift", "fallback_drift"))), None)
            ex = [first_exit(x) for x in cs]
            l3 = [x["transitions"][0][1].startswith("L3") for x in cs]
            k = max(sum(l3), 1)

            def share(pred):
                return sum(1 for e, s0 in zip(ex, l3) if s0 and e and pred(e[0])) / k
            d.update(start_l3=_mean(l3), exit_by_52w=share(lambda t: t <= 52), exit_by_104w=share(lambda t: True),
                     exit_before_drift=share(lambda t: t < dw), exit_within_26w=share(lambda t: dw <= t < dw + 26),
                     exit_within_52w=share(lambda t: dw <= t < dw + 52),
                     exit_to={z: _mean([bool(e and e[1] == z) for e in ex]) for z in ("FALLBACK", "HIST")},
                     returned=_mean([any(t[2] == "recovered" for t in x["transitions"]) for x in cs]),
                     two_exits=_mean([sum(t[2].startswith("drift") for t in x["transitions"]) >= 2 for x in cs]),
                     l3_live=_mean([any(t[1] == "L3_LIVE" for t in x["transitions"]) for x in cs]),
                     l3_live_week=_mean([next((t[0] for t in x["transitions"] if t[1] == "L3_LIVE"), None) for x in cs]),
                     first_any={m: _mean([m in x["first"] for x in cs]) for m in ("D1", "D2", "D3")},
                     first_any_l3={m: _mean([m in x["first"] for x, s0 in zip(cs, l3) if s0])
                                   for m in ("D1", "D2", "D3", "D1ref", "D1reftol")},
                     first_l3_by_52w={m: _mean([x["first"].get(m, 999) <= 52 for x, s0 in zip(cs, l3) if s0])
                                      for m in ("D1", "D2", "D3", "D1ref", "D1reftol")},
                     first_l3_after_drift_26w={m: _mean([dw <= x["first"].get(m, 999) < dw + 26 for x, s0 in zip(cs, l3) if s0])
                                               for m in ("D1", "D2", "D3", "D1ref", "D1reftol")},
                     first_before_drift={m: _mean([x["first"].get(m, 999) < dw for x in cs]) for m in ("D1", "D2", "D3")},
                     n_live=_mean([x["n_live"] for x in cs]),
                     **_delays(cs, ex, l3, dw))
        s["classes"][c] = d
    return s


def _delays(cs, ex, l3, dw):
    """Median delay from drift onset to the first exit from L3, among runs in L3 at onset; runs with
    no exit by the end are censored at the horizon (median reported only when ≥ 50 % detected)."""
    horizon = LIVE_WEEKS - dw
    wk, ev, det = [], [], 0
    pool = [(x, e) for x, e, s0 in zip(cs, ex, l3) if s0 and not (e and e[0] < dw)]
    for x, e in pool:
        if e:
            det += 1
            wk.append(e[0] - dw)
            ev.append(e[3] - x["n_pre"])
        else:
            wk.append(float("inf"))
            ev.append(float("inf"))
    if not pool:
        return {}
    med_w, med_e = float(np.median(wk)), float(np.median(ev))
    return {"delay_runs": len(pool), "detected_by_end": det / len(pool), "horizon_weeks": horizon,
            "delay_median_weeks": med_w if np.isfinite(med_w) else None,
            "delay_median_events": med_e if np.isfinite(med_e) else None,
            "delay_q25_weeks": float(np.quantile(wk, 0.25)) if np.isfinite(np.quantile(wk, 0.25)) else None}


def _apply(overrides):
    for k, v in overrides.items():
        if not hasattr(L, k):
            raise SystemExit(f"unknown constant {k}")
        cur = getattr(L, k)
        setattr(L, k, v if isinstance(cur, str) else type(cur)(v))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--only", default="", help="comma-separated substrings of scenario names")
    ap.add_argument("--out", default="")
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--set", action="append", default=[], help="NAME=VALUE: override a module constant")
    a = ap.parse_args()
    overrides = {k: (float(v) if v.replace(".", "", 1).lstrip("-").isdigit() else v)
                 for k, v in (x.split("=", 1) for x in a.set)}
    _apply(overrides)
    out = {"design": "docs/research/LEVEL_RACE_CALIBRATION_MONITORING_V1_DESIGN.md", "seed": SEED,
           "synthetic_only": True, "holdout_weeks": HOLDOUT_WEEKS, "live_weeks": LIVE_WEEKS,
           "calibration_version": L.LR_CAL_VERSION, "state_version": L.LR_STATE_VERSION,
           "overrides": overrides, "scenarios": {}}
    with Pool(a.procs, initializer=_apply, initargs=(overrides,)) as pool:
        for k, (name, w, mode) in enumerate(scenarios()):
            if a.only and not any(x and x in name for x in a.only.split(",")):
                continue
            t = time.time()
            rs = pool.map(rep, [(w, SEED + 100_000 * k + i, mode) for i in range(a.reps)])
            out["scenarios"][name] = summarize(w, mode, rs)
            print(name, round(time.time() - t, 1), json.dumps({kk: v for kk, v in out["scenarios"][name].items()
                                                              if kk != "world"}), flush=True)
            if a.out:
                with open(a.out, "w") as f:
                    json.dump(out, f, indent=1, sort_keys=True)
                    f.write("\n")


if __name__ == "__main__":
    main()
