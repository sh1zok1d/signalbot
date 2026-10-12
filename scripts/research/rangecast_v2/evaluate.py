"""RANGECAST_V2 evaluation (design: docs/research/RANGECAST_V2_DESIGN.md).

    python -m scripts.research.rangecast_v2.evaluate develop      # folds 2021-2024, whole menu, selection rule
    python -m scripts.research.rangecast_v2.evaluate read2025     # once, after develop: selected model vs V1

`develop` writes docs/research/RANGECAST_V2_DEVELOPMENT.json. `read2025` refuses to run without it and refuses
to run a second time (docs/research/RANGECAST_V2_READ_2025_2026.json exists).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from beta import rangecast as rc
from beta import rangecast_v2 as v2
from beta.calendar_events import event_times_ms, load_calendar
from beta.hist_series import BAR_MS

from . import data as D

REPO = Path(__file__).resolve().parents[3]
DEV_PATH = REPO / "docs/research/RANGECAST_V2_DEVELOPMENT.json"
READ_PATH = REPO / "docs/research/RANGECAST_V2_READ_2025_2026.json"
PRED_DIR = D.cache_root() / "predictions"
YEARS = (2021, 2022, 2023, 2024)
GRID_RANGE = {"1h": (0.1, 2.5), "4h": (0.2, 5.0), "24h": (0.5, 12.5)}
N_GRID = 16
JOURNAL_GRID = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0)
NEITHER_GRID = (0.5, 1.0, 2.0, 3.0)
PROB_BINS = (0.0, 0.05, 0.15, 0.3, 0.5, 0.7, 0.85, 1.0000001)
B_BOOT = 2000
SEED = 20261012
HALF_LIFE_DAYS = 365.0
LADDER = ("L1", "L2", "L3")
GBM_PARAMS = {"objective": "regression", "num_leaves": 31, "learning_rate": 0.05, "min_data_in_leaf": 200,
              "bagging_fraction": 0.8, "bagging_freq": 1, "seed": 1, "verbose": -1, "num_threads": 4}
GBM_ROUNDS = 400


def ms(y: int, m: int = 1, d: int = 1) -> int:
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp() * 1000)


def grid(h: str) -> np.ndarray:
    lo, hi = GRID_RANGE[h]
    return np.exp(np.linspace(math.log(lo), math.log(hi), N_GRID))


def week_id(close_ms: np.ndarray) -> np.ndarray:
    return (close_ms // 86_400_000 + 3) // 7          # ISO weeks start on Monday (1970-01-01 was a Thursday)


# ---- surface -----------------------------------------------------------------------------------------
class Surface:
    def __init__(self):
        self.b, self.manifest = D.load_bars()
        self.events = event_times_ms(load_calendar())
        self.F = v2.bar_features(self.b)
        self.logs = rc.past_log_ranges(self.b)
        self.close_ms = self.b.times + BAR_MS
        self.h = {}

    def horizon(self, h_name: str) -> dict:
        if h_name in self.h:
            return self.h[h_name]
        b, h = self.b, rc.HORIZONS[h_name]
        tg = v2.side_targets(b, h)
        rows = v2.valid_rows(b, self.F, tg, "L3")
        for n in rc.PAST_WINDOWS:
            rows = rows[np.isfinite(self.logs[n][rows])]
        zone = rc.in_event_zone(self.close_ms[rows], self.events, rc.HORIZON_MS[h_name])
        out = {"tg": tg, "rows": rows, "zone": zone, "weekend": rc.weekend_share(b, h), "tg_v1": rc.targets(b, h)}
        self.h[h_name] = out
        return out

    def split(self, h_name: str, test_lo: int, test_hi: int) -> tuple:
        H = self.horizon(h_name)
        c = self.close_ms[H["rows"]]
        train = H["rows"][c + rc.HORIZON_MS[h_name] <= test_lo]
        sel = (c >= test_lo) & (c < test_hi) & ~H["zone"]
        return train, H["rows"][sel]


# ---- models: each returns (P dense [n,16,2], J journal [n,6,2], N neither [n,16] or None, pit [n,2] or None)
def _probs_from(fn_touch, fn_neither, dist: np.ndarray, n: int):
    P = np.stack([np.stack([fn_touch(s, np.full(n, d)) for s in ("up", "down")], axis=1) for d in dist], axis=1)
    J = np.stack([np.stack([fn_touch(s, np.full(n, d)) for s in ("up", "down")], axis=1) for d in JOURNAL_GRID], axis=1)
    N = None
    if fn_neither is not None:
        N = np.stack([fn_neither(np.full(n, du), np.full(n, dd)) for du in NEITHER_GRID for dd in NEITHER_GRID], axis=1)
    return P, J, N


def model_clim(S: Surface, h_name, train, test):
    tg = S.horizon(h_name)["tg"]
    fr = {s: np.sort(tg[s][train]) for s in ("up", "down")}

    def touch(side, d):
        f = 1.0 - np.searchsorted(fr[side], d, side="left") / fr[side].size
        return np.clip(f, v2.PROB_MIN, v2.PROB_MAX)
    P, J, N = _probs_from(touch, None, grid(h_name), test.size)
    return P, J, N, None


def model_v1(S: Surface, h_name, train, test):
    H = S.horizon(h_name)
    m = rc._fit_one(S.b, train, h_name, logs=S.logs, events=S.events, tg=H["tg_v1"], weekend=H["weekend"])
    X = rc.design(S.b, test, h_name, logs=S.logs, season=m["season"], events=S.events, weekend=H["weekend"])
    Sc = np.exp(X @ np.asarray(m["beta"]))
    qs = np.asarray(m["q_one"])

    def touch(side, d):
        u = np.clip(np.interp(d / Sc, qs, rc.P_GRID), rc.P_GRID[0], rc.P_GRID[-1])   # = touch_probability
        return np.clip(1.0 - u, v2.PROB_MIN, v2.PROB_MAX)

    def neither(du, dd):
        return np.clip(rc.neither_shown(m["q_one"], m["q_joint"], du / Sc, dd / Sc), v2.PROB_MIN, v2.PROB_MAX)
    P, J, N = _probs_from(touch, neither, grid(h_name), test.size)
    tg = H["tg"]
    pit = np.stack([np.interp(tg[s][test] / Sc, qs, rc.P_GRID) for s in ("up", "down")], axis=1)
    return P, J, N, pit


def _level_inputs(S: Surface, h_name, idx):
    H = S.horizon(h_name)
    cal = v2.calendar_columns(S.b, idx, h_name, S.events, weekend=H["weekend"])
    return {k: v[idx] for k, v in S.F.items()}, cal


def model_level(S: Surface, h_name, train, test, level, *, weights=None, names=None, signed=None, use_calendar=True):
    tg = S.horizon(h_name)["tg"]
    Ftr, ctr = _level_inputs(S, h_name, train)
    m = v2.fit_level(level, Ftr, ctr, tg["up"][train], tg["down"][train], weights=weights, names=names,
                     signed=signed, use_calendar=use_calendar)
    Fte, cte = _level_inputs(S, h_name, test)
    st = v2.state(m, Fte, cte)
    P, J, N = _probs_from(lambda s, d: v2.touch_prob(m, st, s, d), lambda a, b: v2.neither_prob(m, st, a, b),
                          grid(h_name), test.size)
    if level == "L1":
        pit = np.stack([v2._cdf(m["q_one"], tg[s][test] / st["S"]) for s in ("up", "down")], axis=1)
    else:
        pit = np.stack([v2._cdf(m[f"q_{s}"], (np.log(tg[s][test] + v2.FLOOR) - st[f"mu_{s}"]) / st[f"sigma_{s}"])
                        for s in ("up", "down")], axis=1)
    return P, J, N, pit


def model_r24(S, h_name, train, test):
    return model_level(S, h_name, train, test, "L1", names=("lr_24h",), signed=(), use_calendar=False)


def model_w(level):
    def run(S, h_name, train, test):
        c = S.close_ms[train]
        w = 0.5 ** ((c.max() - c) / 86_400_000 / HALF_LIFE_DAYS)
        return model_level(S, h_name, train, test, level, weights=w)
    return run


def model_gbm(S: Surface, h_name, train, test):
    """L3 with the two means by LightGBM (diagnostic). σ and ε come from residuals of a fit on the first
    80 % of the training rows, scored on the last 20 % (in-sample GBM residuals would be too small)."""
    sys.path.append(os.environ.get("RANGECAST_V2_PYLIBS", ""))
    import lightgbm as lgb
    tg = S.horizon(h_name)["tg"]
    names = v2.SYMMETRIC + v2.SIGNED

    def mat(idx):
        F, cal = _level_inputs(S, h_name, idx)
        return np.column_stack([F[n] for n in names] + [cal["dow"], cal["hour"], cal["weekend"],
                                                        cal["event_cpi"], cal["event_fomc"]])
    Xtr, Xte = mat(train), mat(test)
    cut = int(train.size * 0.8)
    Ftr, ctr = _level_inputs(S, h_name, train)
    sym_names = v2.SYMMETRIC
    season = [[0.0] * 24 for _ in range(7)]
    Xs_tr = v2._design(Ftr, ctr, sym_names, season)
    Fte, cte = _level_inputs(S, h_name, test)
    Xs_te = v2._design(Fte, cte, sym_names, season)
    out = {}
    for side in ("up", "down"):
        y = np.log(tg[side][train] + v2.FLOOR)
        g_a = lgb.train(GBM_PARAMS, lgb.Dataset(Xtr[:cut], y[:cut]), num_boost_round=GBM_ROUNDS)
        r = y[cut:] - g_a.predict(Xtr[cut:])
        gamma = v2._ridge(Xs_tr[cut:], np.log(np.abs(r) + 0.01))
        e = r / np.exp(Xs_tr[cut:] @ gamma)
        g = lgb.train(GBM_PARAMS, lgb.Dataset(Xtr, y), num_boost_round=GBM_ROUNDS)
        lg = Xs_tr[cut:] @ gamma
        out[side] = {"mu": g.predict(Xte), "sigma": np.exp(np.clip(Xs_te @ gamma, lg.min(), lg.max())),
                     "q": np.quantile(e, v2.Q_GRID), "e": e}
    joint = rc._joint_table(out["up"]["e"], out["down"]["e"])

    def touch(side, d):
        x = (np.log(d + v2.FLOOR) - out[side]["mu"]) / out[side]["sigma"]
        return np.clip(1.0 - np.interp(x, out[side]["q"], v2.Q_GRID), v2.PROB_MIN, v2.PROB_MAX)

    def neither(du, dd):
        a = (np.log(du + v2.FLOOR) - out["up"]["mu"]) / out["up"]["sigma"]
        b = (np.log(dd + v2.FLOOR) - out["down"]["mu"]) / out["down"]["sigma"]
        p = rc.joint_cdf(joint, a, b)
        pu, pd_ = touch("up", du), touch("down", dd)
        return np.clip(np.minimum(np.maximum(p, 1 - pu - pd_), 1 - np.maximum(pu, pd_)), v2.PROB_MIN, v2.PROB_MAX)
    P, J, N = _probs_from(touch, neither, grid(h_name), test.size)
    pit = np.stack([np.interp((np.log(tg[s][test] + v2.FLOOR) - out[s]["mu"]) / out[s]["sigma"], out[s]["q"], v2.Q_GRID)
                    for s in ("up", "down")], axis=1)
    return P, J, N, pit


MODELS = {"B_CLIM": model_clim, "B_R24": model_r24, "V1": model_v1,
          "L1": lambda S, h, tr, te: model_level(S, h, tr, te, "L1"),
          "L2": lambda S, h, tr, te: model_level(S, h, tr, te, "L2"),
          "L3": lambda S, h, tr, te: model_level(S, h, tr, te, "L3"),
          "G": model_gbm}


# ---- scores ------------------------------------------------------------------------------------------
def outcomes(S: Surface, h_name, test) -> dict:
    tg = S.horizon(h_name)["tg"]
    up, dn = tg["up"][test], tg["down"][test]
    Y = np.stack([np.stack([up >= d, dn >= d], axis=1) for d in grid(h_name)], axis=1).astype(float)
    YJ = np.stack([np.stack([up >= d, dn >= d], axis=1) for d in JOURNAL_GRID], axis=1).astype(float)
    YN = np.stack([(up < du) & (dn < dd) for du in NEITHER_GRID for dd in NEITHER_GRID], axis=1).astype(float)
    return {"Y": Y, "YJ": YJ, "YN": YN}


def logloss(p, y):
    p = np.clip(p, v2.PROB_MIN, v2.PROB_MAX)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def boot_ci(diff: np.ndarray, weeks: np.ndarray, rng) -> list:
    u, inv = np.unique(weeks, return_inverse=True)
    s = np.bincount(inv, weights=diff)
    c = np.bincount(inv).astype(float)
    W = rng.multinomial(u.size, np.full(u.size, 1.0 / u.size), size=B_BOOT).astype(float)
    d = (W @ s) / (W @ c)
    return [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))]


def recal(p: np.ndarray, y: np.ndarray) -> dict:
    """Pooled logistic recalibration logit P(y) = a + b logit p."""
    p = np.clip(p.ravel(), v2.PROB_MIN, v2.PROB_MAX)
    y = y.ravel()
    x = np.log(p / (1 - p))
    X = np.column_stack([np.ones(x.size), x])
    th = np.array([0.0, 1.0])
    for _ in range(50):
        q = 1 / (1 + np.exp(-(X @ th)))
        H = (X * (q * (1 - q))[:, None]).T @ X
        step = np.linalg.solve(H + np.eye(2) * 1e-9, X.T @ (y - q))
        th += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return {"intercept": round(float(th[0]), 4), "slope": round(float(th[1]), 4)}


def reliability(p: np.ndarray, y: np.ndarray) -> list:
    p, y = p.ravel(), y.ravel()
    out = []
    for lo, hi in zip(PROB_BINS[:-1], PROB_BINS[1:]):
        s = (p >= lo) & (p < hi)
        if s.any():
            out.append({"bin": [lo, min(hi, 1.0)], "n": int(s.sum()), "predicted": round(float(p[s].mean()), 4),
                        "realized": round(float(y[s].mean()), 4), "diff_pp": round(float((y[s] - p[s]).mean() * 100), 2)})
    return out


def pit_deciles(pit: np.ndarray) -> list:
    h = np.histogram(np.clip(pit.ravel(), 0, 1), bins=np.linspace(0, 1, 11))[0]
    return [round(float(x) / pit.size, 4) for x in h]


# ---- develop -------------------------------------------------------------------------------------------
def run_models(S: Surface, names, horizons=("1h", "4h", "24h")) -> dict:
    """{h: {model: {'P','J','N','pit'} concatenated over the four folds}, 'meta': per-fold rows}"""
    res = {}
    for h_name in horizons:
        res[h_name] = {"_test": [], "_year": []}
        for y in YEARS:
            train, test = S.split(h_name, ms(y), ms(y + 1))
            res[h_name]["_test"].append(test)
            res[h_name]["_year"].append(np.full(test.size, y))
            for name in names:
                P, J, N, pit = MODELS[name](S, h_name, train, test)
                d = res[h_name].setdefault(name, {"P": [], "J": [], "N": [], "pit": []})
                d["P"].append(P.astype(np.float32)); d["J"].append(J.astype(np.float32))
                d["N"].append(None if N is None else N.astype(np.float32)); d["pit"].append(None if pit is None else pit)
            print(h_name, y, "train", train.size, "test", test.size, flush=True)
        test = np.concatenate(res[h_name].pop("_test")); year = np.concatenate(res[h_name].pop("_year"))
        for name in names:
            d = res[h_name][name]
            for k in ("P", "J", "N", "pit"):
                d[k] = None if d[k][0] is None else np.concatenate(d[k])
        res[h_name]["_meta"] = {"test": test, "year": year}
    return res


def summarize(S: Surface, res: dict, names, rng) -> dict:
    out = {}
    for h_name, R in res.items():
        test, year = R["_meta"]["test"], R["_meta"]["year"]
        O = outcomes(S, h_name, test)
        weeks = week_id(S.close_ms[test])
        vol = S.F["lr_30d"][test]
        terc = np.zeros(test.size, dtype=int)
        for y in YEARS:
            s = year == y
            e = np.quantile(vol[s], [1 / 3, 2 / 3])
            terc[s] = np.searchsorted(e, vol[s])
        wkend = (v2.utc_weekday(S.close_ms[test]) >= 5)
        g = grid(h_name)
        near, far = g <= 0.5 * GRID_RANGE[h_name][1] / 5.0 * 1.0001, g >= 2.0 * GRID_RANGE[h_name][1] / 5.0 * 0.9999
        hs = {"rows": int(test.size), "weeks": int(np.unique(weeks).size),
              "rows_by_year": {str(y): int((year == y).sum()) for y in YEARS},
              "grid_pct": [round(float(x), 4) for x in g], "models": {}}
        ll = {n: logloss(R[n]["P"], O["Y"]).mean(axis=(1, 2)) for n in names}
        br = {n: ((R[n]["P"] - O["Y"]) ** 2).mean(axis=(1, 2)) for n in names}
        for n in names:
            P = R[n]["P"]
            L = logloss(P, O["Y"])
            m = {"logloss": round(float(ll[n].mean()), 5), "brier": round(float(br[n].mean()), 5),
                 "logloss_journal_grid": round(float(logloss(R[n]["J"], O["YJ"]).mean()), 5),
                 "logloss_by_year": {str(y): round(float(ll[n][year == y].mean()), 5) for y in YEARS},
                 "logloss_by_distance": [round(float(x), 5) for x in L.mean(axis=(0, 2))],
                 "recalibration": recal(P, O["Y"]), "reliability": reliability(P, O["Y"])}
            if R[n]["N"] is not None:
                m["neither_logloss"] = round(float(logloss(R[n]["N"], O["YN"]).mean()), 5)
                m["neither_recalibration"] = recal(R[n]["N"], O["YN"])
            if R[n]["pit"] is not None:
                m["pit_deciles_up"] = pit_deciles(R[n]["pit"][:, 0])
                m["pit_deciles_down"] = pit_deciles(R[n]["pit"][:, 1])
            if n != "V1":
                d = ll[n] - ll["V1"]
                m["vs_V1"] = {"diff": round(float(d.mean()), 6), "ci95": [round(x, 6) for x in boot_ci(d, weeks, rng)],
                              "rel_pct": round(float(d.mean() / ll["V1"].mean() * 100), 3),
                              "by_year": {str(y): round(float(d[year == y].mean()), 6) for y in YEARS},
                              "by_vol_tercile": [round(float(d[terc == k].mean()), 6) for k in range(3)],
                              "weekday_weekend": [round(float(d[~wkend].mean()), 6), round(float(d[wkend].mean()), 6)],
                              "brier_diff": round(float((br[n] - br["V1"]).mean()), 6)}
                dn = (logloss(P[:, near], O["Y"][:, near]).mean(axis=(1, 2)) -
                      logloss(R["V1"]["P"][:, near], O["Y"][:, near]).mean(axis=(1, 2)))
                df = (logloss(P[:, far], O["Y"][:, far]).mean(axis=(1, 2)) -
                      logloss(R["V1"]["P"][:, far], O["Y"][:, far]).mean(axis=(1, 2)))
                m["vs_V1"]["near_group"] = {"diff": round(float(dn.mean()), 6), "ci95": [round(x, 6) for x in boot_ci(dn, weeks, rng)]}
                m["vs_V1"]["far_group"] = {"diff": round(float(df.mean()), 6), "ci95": [round(x, 6) for x in boot_ci(df, weeks, rng)]}
            hs["models"][n] = m
        hs["_ll"] = ll
        hs["_weeks"] = weeks
        hs["_year"] = year
        out[h_name] = hs
    return out


def step_test(ll_new, ll_ref, weeks, year, rng) -> dict:
    d = ll_new - ll_ref
    ci = boot_ci(d, weeks, rng)
    by_year = {str(y): float(d[year == y].mean()) for y in YEARS}
    neg_years = sum(1 for v in by_year.values() if v < 0)
    return {"diff": round(float(d.mean()), 6), "ci95": [round(x, 6) for x in ci],
            "by_year": {k: round(v, 6) for k, v in by_year.items()}, "negative_years": neg_years,
            "accepted": bool(ci[1] < 0 and neg_years >= 3)}


def develop() -> dict:
    S = Surface()
    rng = np.random.default_rng(SEED)
    base = ("B_CLIM", "B_R24", "V1", "L1", "L2", "L3", "G")
    res = run_models(S, base)
    summ = summarize(S, res, base, rng)
    h4 = summ["4h"]
    # selection (design §6)
    accepted, steps = "V1", {}
    for lvl in LADDER:
        t = step_test(h4["_ll"][lvl], h4["_ll"][accepted], h4["_weeks"], h4["_year"], rng)
        t["against"] = accepted
        steps[lvl] = t
        if t["accepted"]:
            accepted = lvl
    selection = {"ladder": steps, "selected_level": accepted}
    if accepted != "V1":
        wname = f"W_{accepted}"
        MODELS[wname] = model_w(accepted)
        resw = run_models(S, (wname,))
        for h_name in resw:
            res[h_name][wname] = resw[h_name][wname]
        names = base + (wname,)
        summ = summarize(S, res, names, rng)
        h4 = summ["4h"]
        t = step_test(h4["_ll"][wname], h4["_ll"][accepted], h4["_weeks"], h4["_year"], rng)
        t["against"] = accepted
        selection["recency"] = t
        selected = wname if t["accepted"] else accepted
    else:
        names, selected = base, "V1"
    selection["selected"] = selected
    # G diagnostic (design §6.3)
    if selected != "V1":
        gd = h4["_ll"]["G"] - h4["_ll"][selected]
        ci = boot_ci(gd, h4["_weeks"], rng)
        selection["gbm_vs_selected"] = {"diff": round(float(gd.mean()), 6), "ci95": [round(x, 6) for x in ci],
                                        "untapped_nonlinear": bool(ci[1] < 0 and -gd.mean() > 0.01 * h4["_ll"]["V1"].mean())}
        # guardrails (design §6.4)
        g = {"slope_4h": h4["models"][selected]["recalibration"]["slope"]}
        g["slope_ok"] = 0.9 <= g["slope_4h"] <= 1.1
        for hz in ("1h", "24h"):
            v = summ[hz]["models"][selected]["vs_V1"]
            g[f"{hz}_not_worse"] = not (v["ci95"][0] > 0)
        v = h4["models"][selected]["vs_V1"]
        g["near_not_worse"] = not (v["near_group"]["ci95"][0] > 0)
        g["far_not_worse"] = not (v["far_group"]["ci95"][0] > 0)
        g["all_pass"] = all(val for k, val in g.items() if k.endswith(("_ok", "_not_worse")))
        selection["guardrails"] = g
    out = {"unit": "RANGECAST_V2", "stage": "development (folds 2021-2024)",
           "design": "docs/research/RANGECAST_V2_DESIGN.md", "data": {k: S.manifest[k] for k in
                                                                       ("source", "symbol", "data_end_exclusive",
                                                                        "objects_sha256", "refused_before_request")},
           "n_objects": len(S.manifest["objects"]), "selection": selection,
           "horizons": {h: {k: v for k, v in s.items() if not k.startswith("_")} for h, s in summ.items()}}
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    for h_name, R in res.items():
        np.savez_compressed(PRED_DIR / f"dev_{h_name}.npz", test=R["_meta"]["test"], year=R["_meta"]["year"],
                            **{f"{n}_P": R[n]["P"] for n in names})
    DEV_PATH.write_text(json.dumps(out, indent=1) + "\n")
    return out


# ---- read 2025-2026 (once) -------------------------------------------------------------------------------
def read2025() -> dict:
    if not DEV_PATH.exists():
        raise SystemExit("REFUSING: run develop first")
    if READ_PATH.exists():
        raise SystemExit("REFUSING_RERUN: the 2025-2026 read exists")
    dev = json.loads(DEV_PATH.read_text())
    selected = dev["selection"]["selected"]
    S = Surface()
    rng = np.random.default_rng(SEED + 1)
    if selected.startswith("W_"):
        MODELS[selected] = model_w(selected[2:])
    names = ("V1", selected) if selected != "V1" else ("V1",)
    lo, hi = ms(2025), ms(2026, 10, 12)
    out = {"unit": "RANGECAST_V2", "stage": "time-disjoint exposed read 2025-01-01 .. 2026-10-11 (once)",
           "selected": selected, "development_sha256": hashlib.sha256(DEV_PATH.read_bytes()).hexdigest(),
           "e1_refused_objects": dev["data"]["refused_before_request"], "horizons": {}}
    for h_name in ("1h", "4h", "24h"):
        train, test = S.split(h_name, lo, hi)
        O = outcomes(S, h_name, test)
        weeks = week_id(S.close_ms[test])
        R = {n: MODELS[n](S, h_name, train, test) for n in names}
        ll = {n: logloss(R[n][0], O["Y"]).mean(axis=(1, 2)) for n in names}
        hs = {"train_rows": int(train.size), "rows": int(test.size), "weeks": int(np.unique(weeks).size),
              "models": {n: {"logloss": round(float(ll[n].mean()), 5),
                             "brier": round(float(((R[n][0] - O["Y"]) ** 2).mean()), 5),
                             "logloss_journal_grid": round(float(logloss(R[n][1], O["YJ"]).mean()), 5),
                             "recalibration": recal(R[n][0], O["Y"]), "reliability": reliability(R[n][0], O["Y"]),
                             "logloss_by_distance": [round(float(x), 5) for x in logloss(R[n][0], O["Y"]).mean(axis=(0, 2))],
                             **({"neither_logloss": round(float(logloss(R[n][2], O["YN"]).mean()), 5)} if R[n][2] is not None else {}),
                             **({"pit_deciles_up": pit_deciles(R[n][3][:, 0]), "pit_deciles_down": pit_deciles(R[n][3][:, 1])}
                                if R[n][3] is not None else {})}
                         for n in names}}
        if selected != "V1":
            d = ll[selected] - ll["V1"]
            yr = np.where(S.close_ms[test] < ms(2026), 2025, 2026)
            hs["selected_vs_V1"] = {"diff": round(float(d.mean()), 6), "ci95": [round(x, 6) for x in boot_ci(d, weeks, rng)],
                                    "rel_pct": round(float(d.mean() / ll["V1"].mean() * 100), 3),
                                    "by_year": {str(y): round(float(d[yr == y].mean()), 6) for y in (2025, 2026)}}
        out["horizons"][h_name] = hs
        print(h_name, json.dumps(hs.get("selected_vs_V1")), flush=True)
    READ_PATH.write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "develop":
        r = develop()
        print(json.dumps(r["selection"], indent=1))
    elif cmd == "read2025":
        read2025()
    else:
        raise SystemExit(__doc__)
