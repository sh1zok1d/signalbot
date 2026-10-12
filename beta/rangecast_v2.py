"""Range model V2 candidate: touch probabilities of an arbitrary price within 1h / 4h / 24h.

NOT WIRED. Nothing in the product imports this module; the production model is `beta/rangecast.py`.
Design and evidence: docs/research/RANGECAST_V2_DESIGN.md and RANGECAST_V2_RESULT.md.

Three levels, each a generalization of V1:

- **L1**: V1's structure (OLS of the log future range, one pooled distribution of the standardized
  one-sided excursion z = side / S) with a richer scale: log ranges of 15m … 30d, log realized
  volatility of 5m returns, base-volume activity, recent move size, a day-of-week × hour season,
  weekend share and CPI / FOMC.
- **L2**: a location–scale model of log(side % + FLOOR) for both sides with one symmetric mean,
  a state-dependent scale σ(x) (OLS of log |residual|) and one pooled empirical distribution of
  the standardized residual ε. The shape of the excursion distribution then depends on the state.
- **L3**: L2 with a separate mean and scale for the up and the down side and signed inputs
  (recent signed returns, close position in the 4h / 24h / 7d range) in the two means.

P(touch d) = 1 − F_side((log(d + FLOOR) − μ_side(x)) / σ_side(x)). «Ни один» of a level above and
one below comes from the joint table of the two standardized residuals (V1's construction) and is
kept coherent with the single chances.

Every feature uses bars at or before the anchor. Features are clipped to their training range
before the coefficients are applied (a live value never extrapolates a coefficient). Volume is
base volume, which the live 1m tail carries exactly (its quote volume is approximated).

Pure numpy / pandas.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from . import rangecast as rc
from .hist_series import BAR_MS, Bars, past_range_pct, utc_hour, utc_weekday

RANGE_MODEL_V2_VERSION = "BETA_RANGE_MODEL_V2_CANDIDATE"
HORIZONS = rc.HORIZONS
HORIZON_MS = rc.HORIZON_MS
FLOOR = rc.FLOOR_PCT                       # % added to a side before the log; also V1's range floor
Q_GRID = [0.001, 0.005] + list(rc.P_GRID)  # quantile levels of the stored residual distributions
PROB_MIN, PROB_MAX = 0.001, 0.999
RIDGE = 1.0                                # on standardized columns; guards collinearity only
CLIP_Q = (0.001, 0.999)                    # feature clip quantiles (training)
SEASON_MIN_ROWS = 30
LOOKBACK_BARS = 8640                       # 30 days: the longest window a feature reads

RANGE_WINDOWS = {"lr_15m": 3, "lr_1h": 12, "lr_4h": 48, "lr_24h": 288, "lr_7d": 2016, "lr_30d": 8640}
RV_WINDOWS = {"lrv_1h": 12, "lrv_4h": 48, "lrv_24h": 288}
ACT_WINDOWS = {"lva_1h": 12, "lva_24h": 288}
MOVE_WINDOWS = {"am_1h": 12, "am_4h": 48}
SIGNED_RET = {"sr_1h": 12, "sr_4h": 48, "sr_24h": 288}
SIGNED_POS = {"pos_4h": 48, "pos_24h": 288, "pos_7d": 2016}
CALENDAR = ("season", "weekend", "event_cpi", "event_fomc")
SYMMETRIC = tuple(RANGE_WINDOWS) + tuple(RV_WINDOWS) + tuple(ACT_WINDOWS) + tuple(MOVE_WINDOWS)
SIGNED = tuple(SIGNED_RET) + tuple(SIGNED_POS)
LEVEL_FEATURES = {"L1": SYMMETRIC, "L2": SYMMETRIC, "L3": SYMMETRIC}
LEVEL_SIGNED = {"L1": (), "L2": (), "L3": SIGNED}


class RangeModelV2Error(RuntimeError):
    pass


# ---- features (point in time) --------------------------------------------------------------------
def _rolling(a: np.ndarray, n: int, how: str, min_frac: float = 0.9) -> np.ndarray:
    s = pd.Series(a).rolling(int(n), min_periods=max(1, int(math.ceil(n * min_frac))))
    return getattr(s, how)().to_numpy()


def bar_features(b: Bars) -> dict:
    """Every per-bar feature at the close of each bar (NaN where its window is incomplete)."""
    c = b.close
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.log(c[1:] / c[:-1])
    r = np.concatenate([[np.nan], r])
    out: dict = {}
    rng = {k: past_range_pct(b, n) for k, n in RANGE_WINDOWS.items()}
    for k, v in rng.items():
        out[k] = np.log(np.maximum(v, FLOOR))
    r2 = r * r
    for k, n in RV_WINDOWS.items():
        ssum, cnt = _rolling(r2, n, "sum"), _rolling(np.isfinite(r2).astype(float), n, "sum", min_frac=0.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            rv = np.sqrt(ssum * n / cnt) * 100.0
        out[k] = np.log(np.maximum(rv, 0.01))
    vol = b.volume
    base = _rolling(vol, LOOKBACK_BARS, "mean")
    for k, n in ACT_WINDOWS.items():
        with np.errstate(invalid="ignore", divide="ignore"):
            out[k] = np.log(np.maximum(_rolling(vol, n, "mean") / base, 0.05))
    r24 = rng["lr_24h"]
    for k, n in {**MOVE_WINDOWS, **SIGNED_RET}.items():
        prev = np.concatenate([np.full(n, np.nan), c[:-n]])
        with np.errstate(invalid="ignore", divide="ignore"):
            ret = np.log(c / prev) * 100.0 / np.maximum(r24, FLOOR)
        out[k] = np.clip(np.abs(ret), 0.0, 3.0) if k.startswith("am_") else np.clip(ret, -3.0, 3.0)
    for k, n in SIGNED_POS.items():
        hi, lo = _rolling(b.high, n, "max"), _rolling(b.low, n, "min")
        with np.errstate(invalid="ignore", divide="ignore"):
            pos = np.where(hi > lo, (c - lo) / (hi - lo), 0.5) - 0.5
        out[k] = np.where(np.isfinite(hi) & np.isfinite(lo) & np.isfinite(c), pos, np.nan)
    return out


def calendar_columns(b: Bars, idx: np.ndarray, h_name: str, events: Mapping[str, Sequence[int]],
                     weekend: Optional[np.ndarray] = None) -> dict:
    close_ms = b.times[idx] + BAR_MS
    wk = weekend if weekend is not None else rc.weekend_share(b, HORIZONS[h_name])
    return {"dow": utc_weekday(close_ms), "hour": utc_hour(close_ms), "weekend": wk[idx],
            "event_cpi": rc.event_in_window(close_ms, events.get("CPI", ()), HORIZON_MS[h_name]),
            "event_fomc": rc.event_in_window(close_ms, events.get("FOMC", ()), HORIZON_MS[h_name])}


def side_targets(b: Bars, h: int) -> dict:
    tg = rc.targets(b, h)
    full = _rolling(np.isfinite(b.close).astype(float), h, "sum", min_frac=0.0)
    complete = np.concatenate([full[h:], np.full(h, np.nan)]) == h          # all h forward bars present
    return {"up": np.where(complete, tg["up"], np.nan), "down": np.where(complete, tg["down"], np.nan),
            "range": np.where(complete, tg["range"], np.nan)}


# ---- fitting helpers -------------------------------------------------------------------------------
def weighted_quantiles(x: np.ndarray, q: Sequence[float], w: Optional[np.ndarray] = None) -> np.ndarray:
    x = np.asarray(x, float)
    if w is None:
        return np.quantile(x, q)
    o = np.argsort(x)
    xs, ws = x[o], np.asarray(w, float)[o]
    cw = (np.cumsum(ws) - 0.5 * ws) / ws.sum()
    return np.interp(q, cw, xs)


def _season_table(y: np.ndarray, dow: np.ndarray, hour: np.ndarray, w: Optional[np.ndarray]) -> list:
    overall = float(weighted_quantiles(y, [0.5], w)[0])
    by_hour = []
    for h in range(24):
        s = hour == h
        by_hour.append(float(weighted_quantiles(y[s], [0.5], None if w is None else w[s])[0]) if s.sum() >= SEASON_MIN_ROWS
                       else overall)
    table = []
    for d in range(7):
        row = []
        for h in range(24):
            s = (dow == d) & (hour == h)
            row.append(float(weighted_quantiles(y[s], [0.5], None if w is None else w[s])[0]) if s.sum() >= SEASON_MIN_ROWS
                       else by_hour[h])
        table.append(row)
    return table


def _design(F: Mapping[str, np.ndarray], cal: Mapping[str, np.ndarray], names: Sequence[str],
            season: Sequence[Sequence[float]], clip: Optional[Mapping[str, Sequence[float]]] = None) -> np.ndarray:
    cols = [np.ones(len(cal["dow"]))]
    for n in names:
        v = np.asarray(F[n], float)
        if clip is not None:
            lo, hi = clip[n]
            v = np.clip(v, lo, hi)
        cols.append(v)
    cols.append(np.asarray(season, float)[cal["dow"], cal["hour"]])
    cols += [np.asarray(cal["weekend"], float), np.asarray(cal["event_cpi"], float), np.asarray(cal["event_fomc"], float)]
    return np.column_stack(cols)


def _ridge(X: np.ndarray, y: np.ndarray, w: Optional[np.ndarray] = None) -> np.ndarray:
    """Weighted ridge with the intercept unpenalized, on standardized columns; returns raw-scale beta."""
    w = np.ones(y.size) if w is None else np.asarray(w, float)
    sw = w / w.sum()
    mu = sw @ X
    sd = np.sqrt(sw @ (X - mu) ** 2)
    sd[0] = 1.0
    sd[sd == 0] = 1.0
    Z = (X - mu) / sd
    Z[:, 0] = 1.0
    A = (Z * w[:, None]).T @ Z
    pen = np.eye(X.shape[1]) * RIDGE
    pen[0, 0] = 0.0
    g = np.linalg.solve(A + pen, (Z * w[:, None]).T @ y)
    beta = g / sd
    beta[0] = g[0] - np.sum(g[1:] * mu[1:] / sd[1:])
    return beta


def _clip_bounds(F: Mapping[str, np.ndarray], names: Sequence[str], w: Optional[np.ndarray]) -> dict:
    return {n: [float(v) for v in weighted_quantiles(np.asarray(F[n], float), CLIP_Q, w)] for n in names}


# ---- fit -------------------------------------------------------------------------------------------
def fit_level(level: str, F: Mapping[str, np.ndarray], cal: Mapping[str, np.ndarray], up: np.ndarray,
              down: np.ndarray, *, weights: Optional[np.ndarray] = None,
              names: Optional[Sequence[str]] = None, signed: Optional[Sequence[str]] = None,
              use_calendar: bool = True) -> dict:
    """Fit one horizon of a level on the rows given (features already selected to those rows)."""
    names = tuple(LEVEL_FEATURES[level] if names is None else names)
    signed = tuple(LEVEL_SIGNED[level] if signed is None else signed)
    w = weights
    clip = _clip_bounds(F, names + signed, w)
    out: dict = {"level": level, "features": list(names), "signed": list(signed), "clip": clip,
                 "use_calendar": bool(use_calendar), "n": int(up.size), "q_grid": Q_GRID}
    cal_eff = cal if use_calendar else {**cal, "weekend": np.zeros_like(cal["weekend"]),
                                        "event_cpi": np.zeros_like(cal["event_cpi"]),
                                        "event_fomc": np.zeros_like(cal["event_fomc"])}
    zero_season = [[0.0] * 24 for _ in range(7)]
    if level == "L1":
        y = np.log(np.maximum(up + down, FLOOR))
        season = _season_table(y, cal["dow"], cal["hour"], w) if use_calendar else zero_season
        X = _design(F, cal_eff, names, season, clip)
        beta = _ridge(X, y, w)
        S = np.exp(X @ beta)
        zu, zd = up / S, down / S
        out.update(season=season, beta=[float(v) for v in beta],
                   q_one=[float(v) for v in weighted_quantiles(np.concatenate([zu, zd]), Q_GRID,
                                                               None if w is None else np.concatenate([w, w]))],
                   q_joint=rc._joint_table(zu, zd))
        return out
    yu, yd = np.log(up + FLOOR), np.log(down + FLOOR)
    season = _season_table(np.concatenate([yu, yd]), np.concatenate([cal["dow"], cal["dow"]]),
                           np.concatenate([cal["hour"], cal["hour"]]),
                           None if w is None else np.concatenate([w, w])) if use_calendar else zero_season
    Xs = _design(F, cal_eff, names, season, clip)
    out["season"] = season
    if level == "L2":
        ww = None if w is None else np.concatenate([w, w])
        beta = _ridge(np.vstack([Xs, Xs]), np.concatenate([yu, yd]), ww)
        mu = Xs @ beta
        ru, rd = yu - mu, yd - mu
        gamma = _ridge(np.vstack([Xs, Xs]), np.log(np.abs(np.concatenate([ru, rd])) + 0.01), ww)
        sig = np.exp(Xs @ gamma)
        eu, ed = ru / sig, rd / sig
        q = weighted_quantiles(np.concatenate([eu, ed]), Q_GRID, ww)
        out.update(beta_up=[float(v) for v in beta], beta_down=[float(v) for v in beta],
                   gamma_up=[float(v) for v in gamma], gamma_down=[float(v) for v in gamma],
                   q_up=[float(v) for v in q], q_down=[float(v) for v in q], q_joint=rc._joint_table(eu, ed),
                   log_sigma_range=[float(np.min(Xs @ gamma)), float(np.max(Xs @ gamma))])
        return out
    if level != "L3":
        raise RangeModelV2Error(f"unknown level {level!r}")
    Xa = np.column_stack([Xs] + [np.clip(np.asarray(F[n], float), *clip[n]) for n in signed])
    res = {}
    for side, y in (("up", yu), ("down", yd)):
        beta = _ridge(Xa, y, w)
        r = y - Xa @ beta
        gamma = _ridge(Xs, np.log(np.abs(r) + 0.01), w)
        e = r / np.exp(Xs @ gamma)
        res[side] = (beta, gamma, e)
        out[f"beta_{side}"] = [float(v) for v in beta]
        out[f"gamma_{side}"] = [float(v) for v in gamma]
        out[f"q_{side}"] = [float(v) for v in weighted_quantiles(e, Q_GRID, w)]
    lg = np.concatenate([Xs @ res["up"][1], Xs @ res["down"][1]])
    out.update(q_joint=rc._joint_table(res["up"][2], res["down"][2]),
               log_sigma_range=[float(lg.min()), float(lg.max())])
    return out


# ---- predict ---------------------------------------------------------------------------------------
def _cdf(q: Sequence[float], x: np.ndarray) -> np.ndarray:
    return np.interp(x, np.asarray(q, float), np.asarray(Q_GRID, float))


def state(model_h: Mapping[str, Any], F: Mapping[str, np.ndarray], cal: Mapping[str, np.ndarray]) -> dict:
    """The per-row predictive parameters: S (L1) or (μ, σ) per side (L2 / L3)."""
    cal_eff = cal if model_h["use_calendar"] else {**cal, "weekend": np.zeros_like(np.asarray(cal["weekend"], float)),
                                                   "event_cpi": np.zeros(len(cal["dow"])),
                                                   "event_fomc": np.zeros(len(cal["dow"]))}
    Xs = _design(F, cal_eff, model_h["features"], model_h["season"], model_h["clip"])
    if model_h["level"] == "L1":
        return {"S": np.exp(Xs @ np.asarray(model_h["beta"]))}
    lo, hi = model_h["log_sigma_range"]
    Xa = Xs if not model_h["signed"] else np.column_stack(
        [Xs] + [np.clip(np.asarray(F[n], float), *model_h["clip"][n]) for n in model_h["signed"]])
    out = {}
    for side in ("up", "down"):
        Xm = Xa if model_h["level"] == "L3" else Xs
        out[f"mu_{side}"] = Xm @ np.asarray(model_h[f"beta_{side}"])
        out[f"sigma_{side}"] = np.exp(np.clip(Xs @ np.asarray(model_h[f"gamma_{side}"]), lo, hi))
    return out


def touch_prob(model_h: Mapping[str, Any], st: Mapping[str, np.ndarray], side: str, distance_pct) -> np.ndarray:
    """Chance to reach `distance_pct` (% , > 0) on `side` ('up' | 'down') within the horizon, per row."""
    d = np.asarray(distance_pct, float)
    if model_h["level"] == "L1":
        p = 1.0 - _cdf(model_h["q_one"], d / st["S"])
    else:
        x = (np.log(d + FLOOR) - st[f"mu_{side}"]) / st[f"sigma_{side}"]
        p = 1.0 - _cdf(model_h[f"q_{side}"], x)
    return np.clip(p, PROB_MIN, PROB_MAX)


def neither_prob(model_h: Mapping[str, Any], st: Mapping[str, np.ndarray], up_pct, down_pct) -> np.ndarray:
    """Chance that neither a level `up_pct` above nor one `down_pct` below is reached, coherent with
    the two single chances (1 − p_up − p_down <= neither <= 1 − max(p_up, p_down))."""
    du, dd = np.asarray(up_pct, float), np.asarray(down_pct, float)
    if model_h["level"] == "L1":
        a, b = du / st["S"], dd / st["S"]
    else:
        a = (np.log(du + FLOOR) - st["mu_up"]) / st["sigma_up"]
        b = (np.log(dd + FLOOR) - st["mu_down"]) / st["sigma_down"]
    p = rc.joint_cdf(model_h["q_joint"], a, b)
    pu, pd_ = touch_prob(model_h, st, "up", du), touch_prob(model_h, st, "down", dd)
    p = np.minimum(np.maximum(p, 1.0 - pu - pd_), 1.0 - np.maximum(pu, pd_))
    return np.clip(p, PROB_MIN, PROB_MAX)


# ---- production-shaped entry points (not wired) ------------------------------------------------------
def valid_rows(b: Bars, F: Mapping[str, np.ndarray], tg: Mapping[str, np.ndarray], level: str,
               stride: int = rc.ANCHOR_STRIDE) -> np.ndarray:
    close_ms = b.times + BAR_MS
    ok = ((close_ms % (stride * BAR_MS)) == 0) & np.isfinite(b.close) & np.isfinite(tg["up"]) & np.isfinite(tg["down"])
    for n in LEVEL_FEATURES[level] + LEVEL_SIGNED[level]:
        ok &= np.isfinite(F[n])
    return np.flatnonzero(ok)


def fit_range_model_v2(b: Bars, *, events: Mapping[str, Sequence[int]], level: str = "L3",
                       half_life_days: Optional[float] = None) -> dict:
    """Fit every horizon on all valid hourly anchors of `b`. JSON-ready."""
    F = bar_features(b)
    out = {"version": RANGE_MODEL_V2_VERSION, "level": level, "half_life_days": half_life_days, "horizons": {}}
    for h_name, h in HORIZONS.items():
        tg = side_targets(b, h)
        idx = valid_rows(b, F, tg, level)
        if idx.size < rc.MIN_TRAIN_ANCHORS:
            raise RangeModelV2Error(f"NOT_ENOUGH_ANCHORS:{h_name}:{idx.size}")
        close_ms = b.times[idx] + BAR_MS
        w = None if half_life_days is None else 0.5 ** ((close_ms[-1] - close_ms) / 86_400_000 / half_life_days)
        cal = calendar_columns(b, idx, h_name, events)
        Fi = {k: v[idx] for k, v in F.items()}
        m = fit_level(level, Fi, cal, tg["up"][idx], tg["down"][idx], weights=w)
        m.update(horizon=h_name, data_from_ms=int(close_ms[0]), data_to_ms=int(close_ms[-1]),
                 n_days=int(np.unique(close_ms // 86_400_000).size))
        out["horizons"][h_name] = m
    return out


def state_at(model: Mapping[str, Any], b: Bars, i: int, h_name: str, *,
             events: Mapping[str, Sequence[int]]) -> Optional[dict]:
    """Predictive parameters for an anchor at the close of bar i, from bars <= i only."""
    m = model["horizons"].get(h_name)
    if m is None or i is None or i < LOOKBACK_BARS:
        return None
    sub = b.slice(i - LOOKBACK_BARS - 1, i + 1)
    j = sub.n - 1
    F = bar_features(sub)
    names = tuple(m["features"]) + tuple(m["signed"])
    if any(not np.isfinite(F[n][j]) for n in names):
        return None
    Fj = {n: F[n][[j]] for n in names}
    cal = calendar_columns(sub, np.array([j]), h_name, events)
    return {k: float(v[0]) for k, v in state(m, Fj, cal).items()}


def touch_probability_v2(model: Mapping[str, Any], h_name: str, st: Mapping[str, float], side: int,
                         distance_pct: float) -> float:
    """Single-request form of `touch_prob` (side +1 above, −1 below)."""
    if distance_pct <= 0:
        return 1.0
    m = model["horizons"][h_name]
    s = {k: np.array([v]) for k, v in st.items()}
    return float(touch_prob(m, s, "up" if side > 0 else "down", np.array([abs(distance_pct)]))[0])
