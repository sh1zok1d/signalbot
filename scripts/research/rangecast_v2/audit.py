"""Shadow-readiness audit of W_L1 on the development folds 2021-2024 (the consumed selection surface).

    python -m scripts.research.rangecast_v2.audit

No 2025-2026 outcome is read: the one read of that surface is done and stays done. Writes
docs/research/RANGECAST_V2_SHADOW_AUDIT.json with:
1. anchors: V1 and W_L1, fitted on hourly anchors as evaluated, scored at 5-minute anchor offsets
   (every 15 minutes, all four quarter-hour offsets);
2. tails: the research path against the V1 view (`as_v1_horizon`) on the evaluation grids, fold 2024;
3. neither: monotonicity in both levels and the Fréchet bounds against the single chances, fold 2024;
4. planning: weekly variability of the paired log-loss difference on the claim-journal grid, and the
   historical behaviour of the promotion rule `RANGECAST_V2_PROMOTION_RULE_V1` (beta/rangecast_paired.py).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from beta import rangecast as rc
from beta import rangecast_paired as rp
from beta import rangecast_v2 as v2
from beta.hist_series import BAR_MS

from . import evaluate as E

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "docs/research/RANGECAST_V2_SHADOW_AUDIT.json"


def anchors(S) -> dict:
    out = {}
    for h in ("1h", "4h", "24h"):
        H = S.horizon(h)
        rows = v2.valid_rows(S.b, S.F, H["tg"], "L3", stride=1)
        for n in rc.PAST_WINDOWS:
            rows = rows[np.isfinite(S.logs[n][rows])]
        c = S.close_ms[rows]
        zone = rc.in_event_zone(c, S.events, rc.HORIZON_MS[h])
        acc = {m: {"ll": [], "p": [], "y": [], "minute": []} for m in ("V1", "W_L1")}
        for y in E.YEARS:
            train, _ = S.split(h, E.ms(y), E.ms(y + 1))
            test = rows[(c >= E.ms(y)) & (c < E.ms(y + 1)) & ~zone][::3]
            minute = ((S.close_ms[test] // BAR_MS) % 12) * 5
            O = E.outcomes(S, h, test)
            for m, fn in (("V1", E.model_v1), ("W_L1", E.model_w("L1"))):
                P = fn(S, h, train, test)[0]
                acc[m]["ll"].append(E.logloss(P, O["Y"]).mean(axis=(1, 2)))
                acc[m]["p"].append(P.reshape(len(test), -1)); acc[m]["y"].append(O["Y"].reshape(len(test), -1))
                acc[m]["minute"].append(minute)
        r = {}
        for m in acc:
            ll, p, yv, mi = (np.concatenate(acc[m][k]) for k in ("ll", "p", "y", "minute"))
            r[m] = {int(k): {"anchors": int((mi == k).sum()), "logloss": round(float(ll[mi == k].mean()), 5),
                             "citl_pp": round(float((yv[mi == k] - p[mi == k]).mean() * 100), 3),
                             **E.recal(p[mi == k], yv[mi == k])} for k in sorted(set(mi.tolist()))}
        d = np.concatenate(acc["W_L1"]["ll"]) - np.concatenate(acc["V1"]["ll"])
        mi = np.concatenate(acc["V1"]["minute"])
        r["W_L1_minus_V1"] = {int(k): round(float(d[mi == k].mean()), 6) for k in sorted(set(mi.tolist()))}
        out[h] = r
        print("anchors", h, r["W_L1_minus_V1"], flush=True)
    return out


def tails_and_neither(S) -> dict:
    out = {}
    rng = np.random.default_rng(1)
    for h in ("1h", "4h", "24h"):
        tg = S.horizon(h)["tg"]
        train, test = S.split(h, E.ms(2024), E.ms(2025))
        c = S.close_ms[train]
        w = 0.5 ** ((c.max() - c) / 86_400_000 / E.HALF_LIFE_DAYS)
        Ftr, ctr = E._level_inputs(S, h, train)
        m = v2.fit_level("L1", Ftr, ctr, tg["up"][train], tg["down"][train], weights=w)
        m["horizon"] = h
        Fte, cte = E._level_inputs(S, h, test)
        st = v2.state(m, Fte, cte)
        view = {"horizons": {h: v2.as_v1_horizon(m)}}
        dist = np.concatenate([E.grid(h), np.array(E.JOURNAL_GRID), np.array([0.05])])
        pr = np.concatenate([v2.touch_prob(m, st, "up", np.full(test.size, d)) for d in dist])
        pv = np.concatenate([np.clip([rc.touch_probability(view, h, float(s), float(d)) for s in st["S"]],
                                     v2.PROB_MIN, v2.PROB_MAX) for d in dist])
        diff = np.abs(pr - pv)
        r = {"probabilities": int(pr.size), "share_above_0_99": round(float(np.mean(pr > 0.99)), 6),
             "max_abs_diff": float(diff.max()), "max_abs_diff_at_or_below_0_99": float(diff[pr <= 0.99].max()),
             "distances_pct": [round(float(x), 4) for x in dist]}
        rows = rng.choice(test.size, 400, replace=False)
        lv = np.exp(np.linspace(np.log(0.05), np.log(15.0), 25))
        mono = frechet = 0
        for i in rows:
            s1 = {k: v[[i]] for k, v in st.items()}
            N = np.array([[float(v2.neither_prob(m, s1, np.array([a]), np.array([b]))[0]) for b in lv] for a in lv])
            mono += int((np.diff(N, axis=0) < -1e-12).sum() + (np.diff(N, axis=1) < -1e-12).sum())
            pu = np.array([float(v2.touch_prob(m, s1, "up", np.array([a]))[0]) for a in lv])
            pd_ = np.array([float(v2.touch_prob(m, s1, "down", np.array([b]))[0]) for b in lv])
            lo = np.maximum(1 - pu[:, None] - pd_[None, :], v2.PROB_MIN) - 1e-12
            hi = np.minimum(1 - np.maximum(pu[:, None], pd_[None, :]), v2.PROB_MAX) + 1e-12
            frechet += int(((N < lo) | (N > hi)).sum())
        r["neither"] = {"states": int(rows.size), "level_pairs_per_state": int(lv.size ** 2),
                        "monotonicity_violations": mono, "frechet_bound_violations": frechet}
        out[h] = r
        print("tails/neither", h, r, flush=True)
    return out


def planning(S) -> dict:
    weekly, per = {}, {}
    for h in ("1h", "4h", "24h"):
        dj, dn, wk = [], [], []
        for y in E.YEARS:
            train, test = S.split(h, E.ms(y), E.ms(y + 1))
            O = E.outcomes(S, h, test)
            R1, R2 = E.model_v1(S, h, train, test), E.model_w("L1")(S, h, train, test)
            dj.append(E.logloss(R2[1], O["YJ"]).mean(axis=(1, 2)) - E.logloss(R1[1], O["YJ"]).mean(axis=(1, 2)))
            dn.append(E.logloss(R2[2], O["YN"]).mean(axis=1) - E.logloss(R1[2], O["YN"]).mean(axis=1))
            wk.append(E.week_id(S.close_ms[test]))
        wk = np.concatenate(wk)
        u, inv = np.unique(wk, return_inverse=True)
        r = {}
        for name, d in (("touch_journal_grid", np.concatenate(dj)), ("neither", np.concatenate(dn))):
            wm = np.bincount(inv, weights=d) / np.bincount(inv)
            sd = float(wm.std(ddof=1))
            r[name] = {"mean_diff": round(float(d.mean()), 6), "weekly_sd": round(sd, 6), "weeks": int(u.size),
                       "weeks_for_80pct_power_at_mean": round(float(((1.96 + 0.84) * sd / abs(d.mean())) ** 2), 1)}
            if name == "touch_journal_grid":
                weekly[h] = dict(zip(u.tolist(), wm.tolist()))
        per[h] = r
    weeks = sorted(set(weekly["1h"]) & set(weekly["4h"]))
    comb = np.array([(weekly["1h"][w] + weekly["4h"][w]) / 2 for w in weeks])
    lag = [round(float(np.corrcoef(comb[:-k], comb[k:])[0, 1]), 3) for k in (1, 2, 4, 8)]
    W, M, k = rp.LOOK_WEEKS, rp.NI_MARGIN, rp.SE_INFLATION
    passed, null_pass, sup, sup_null = [], [], [], []
    for s0 in range(0, comb.size - W + 1, 2):
        a = comb[s0:s0 + W]
        z = a - comb.mean() + M                                   # same week-to-week noise, V2 worse by M
        for series, acc in ((a, passed), (z, null_pass)):
            iv = rp.weekly_interval(list(series), k)
            acc.append(iv["mean"] < 0 and iv["hi"] < M)
        for series, acc in ((a, sup), (a - comb.mean(), sup_null)):
            iv = rp.weekly_interval(list(series), rp.SUPERIORITY_SE_INFLATION)
            acc.append(iv["hi"] < 0)
    # the two designs that were rejected: a plain superiority look (no inflation) with the gain removed, and a
    # second non-inferiority look at 20 weeks when V2 is worse by the margin
    plain_null, two_look_null = [], []
    for s0 in range(0, comb.size - 20 + 1, 2):
        a = comb[s0:s0 + W] - comb.mean()
        plain_null.append(rp.weekly_interval(list(a), 1.0)["hi"] < 0)
        z = comb[s0:s0 + 20] - comb.mean() + M
        first, both = rp.weekly_interval(list(z[:W]), k), rp.weekly_interval(list(z), k)
        two_look_null.append((first["mean"] < 0 and first["hi"] < M) or (both["mean"] < 0 and both["hi"] < M))
    return {"per_horizon": per, "rejected_designs": {
                "plain_superiority_12w_share_promoted_when_no_gain": round(float(np.mean(plain_null)), 3),
                "non_inferiority_looks_12_and_20w_share_passed_when_v2_worse_by_margin": round(float(np.mean(two_look_null)), 3)},
            "combined_weekly": {"mean": round(float(comb.mean()), 6),
                                                   "sd": round(float(comb.std(ddof=1)), 6),
                                                   "autocorrelation_lags_1_2_4_8": lag, "weeks": int(comb.size)},
            "rule_on_history": {"look_weeks": W, "ni_margin": M, "se_inflation": k, "windows": len(passed),
                                "share_primary_passed": round(float(np.mean(passed)), 3),
                                "share_passed_when_v2_worse_by_margin": round(float(np.mean(null_pass)), 3),
                                "share_superiority_label": round(float(np.mean(sup)), 3),
                                "share_superiority_label_when_no_gain": round(float(np.mean(sup_null)), 3)}}


def main() -> dict:
    S = E.Surface()
    out = {"surface": "development folds 2021-2024 (consumed); no 2025-2026 outcome read",
           "anchors": anchors(S), "tails_and_neither": tails_and_neither(S), "planning": planning(S)}
    print("planning", json.dumps(out["planning"]["rule_on_history"]), flush=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    main()
