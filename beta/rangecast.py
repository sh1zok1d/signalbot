"""Range model: how far BTC can move over the next 1h / 4h / 24h (PRODUCT_DECISION_V2 §2.1).

Volatility clusters; direction does not (every directional research test of this project is
a null). So the model forecasts the size of the move, never its sign.

Model (one per horizon H, fitted by ordinary least squares on hourly anchors):

    log R_H(t) = b0 + b1 log R_1h + b2 log R_4h + b3 log R_24h + b4 log R_7d
                 + b5 season_H(UTC hour) + b6 weekend share + b7 CPI in window + b8 FOMC in window

R_H(t) is the realized range of the next H measured from the anchor close (up excursion plus
down excursion, % of the close); the R_* on the right are past ranges ending at the anchor.
`season_H` is the median log future range by UTC hour of the training anchors. CPI / FOMC are
scheduled events inside (t, t + H]; they are known in advance, so using them is not lookahead.

The fitted scale S = exp(Xb) standardizes every move: z = move / S. The empirical quantiles of
the standardized one-sided excursion, of the larger of the two excursions and of the close
return give the corridor (containment), the touch probability of a distance and the stop
statistics of /risk. A held-out last year checks the corridor coverage before the final fit
on all data.

Binance USD-M BTCUSDT 5m only. Pure numpy / pandas.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from .hist_series import (BAR_MS, BARS_PER_DAY, Bars, forward_extremes, past_range_pct, utc_hour,
                          utc_weekday)

RANGE_MODEL_VERSION = "BETA_RANGE_MODEL_V1"
HORIZONS = {"1h": 12, "4h": 48, "24h": 288}
HORIZON_MS = {k: v * BAR_MS for k, v in HORIZONS.items()}
PAST_WINDOWS = (12, 48, 288, 2016)
EVENT_KINDS = ("CPI", "FOMC")
FLOOR_PCT = 0.02
COVERAGE = 0.80
ANCHOR_STRIDE = 12
P_GRID = [round(0.01 * k, 2) for k in range(1, 100)] + [0.995, 0.999]
HOLDOUT_DAYS = 365
MIN_TRAIN_ANCHORS = 2000
FEATURES = ("const", "log_r1h", "log_r4h", "log_r24h", "log_r7d", "season", "weekend") + tuple(
    "event_" + k.lower() for k in EVENT_KINDS)
MOVE_QUANTILES = (0.99, 0.995, 0.998, 0.999, 0.9995)
MOVE_TARGET_EPISODES_PER_DAY = 0.35
MOVE_DECLUSTER_BARS = 24             # 2h between two sharp-move episodes
MOVE_WINDOW_BARS = 3                 # 15 minutes
# SHARP_MOVE_EVENT_CONDITIONING = DISABLED_PENDING_VALIDATION
# (BETA_EVENT_CORRIDOR_TEMPORAL_REPAIR_DESIGN_V1 §10). The sharp-move statistic divides by the 1h
# scale with every CPI/FOMC column at 0; the corridor keeps its event term. A threshold is only
# used with the statistic it was calibrated on, named here.
MOVE_STATISTIC = "MOVE15_OVER_1H_SCALE_EVENT_NEUTRAL_V1"
_NO_EVENTS: Mapping[str, Sequence[int]] = {}


class RangeModelError(RuntimeError):
    pass


# ---- features ----------------------------------------------------------------------------
def past_log_ranges(b: Bars) -> dict:
    return {n: np.log(np.maximum(past_range_pct(b, n), FLOOR_PCT)) for n in PAST_WINDOWS}


def weekend_share(b: Bars, h: int) -> np.ndarray:
    """Share of bars i+1 .. i+h whose open falls on Saturday or Sunday (UTC)."""
    # the weekday comes from the clock, so the window may run past the data (live anchor)
    times = b.t0 + np.arange(b.n + h, dtype=np.int64) * BAR_MS
    wk = (utc_weekday(times) >= 5).astype(np.float64)
    cum = np.concatenate([[0.0], np.cumsum(wk)])
    i = np.arange(b.n)
    return (cum[i + h + 1] - cum[i + 1]) / h


def event_in_window(anchor_close_ms: np.ndarray, events_ms: Sequence[int], horizon_ms: int) -> np.ndarray:
    """1 when an event falls in [anchor close, anchor close + H): the forward window starts at the
    anchor's close, so a release exactly on the hour belongs to the window that starts then."""
    ev = np.sort(np.asarray(list(events_ms), dtype=np.int64))
    if ev.size == 0:
        return np.zeros(anchor_close_ms.shape[0])
    a = np.searchsorted(ev, anchor_close_ms, side="left")
    z = np.searchsorted(ev, anchor_close_ms + horizon_ms, side="left")
    return (z > a).astype(np.float64)


def design(b: Bars, idx: np.ndarray, h_name: str, *, logs: Mapping[int, np.ndarray],
           season: Sequence[float], events: Mapping[str, Sequence[int]],
           weekend: Optional[np.ndarray] = None) -> np.ndarray:
    h = HORIZONS[h_name]
    close_ms = b.times[idx] + BAR_MS
    hod = utc_hour(close_ms)
    wk = weekend if weekend is not None else weekend_share(b, h)
    cols = [np.ones(idx.size), logs[12][idx], logs[48][idx], logs[288][idx], logs[2016][idx],
            np.asarray(season, dtype=np.float64)[hod], wk[idx]]
    for k in EVENT_KINDS:
        cols.append(event_in_window(close_ms, events.get(k, ()), HORIZON_MS[h_name]))
    return np.column_stack(cols)


def targets(b: Bars, h: int) -> dict:
    fwd_hi, fwd_lo, fwd_close = forward_extremes(b, h)
    with np.errstate(invalid="ignore", divide="ignore"):
        up = np.maximum((fwd_hi - b.close) / b.close * 100.0, 0.0)
        dn = np.maximum((b.close - fwd_lo) / b.close * 100.0, 0.0)
        ret = (fwd_close - b.close) / b.close * 100.0
    return {"up": up, "down": dn, "ret": ret, "range": up + dn}


def _quantiles(x: np.ndarray) -> list:
    x = x[np.isfinite(x)]
    if x.size == 0:
        raise RangeModelError("EMPTY_SAMPLE")
    return [float(v) for v in np.quantile(x, P_GRID)]


def _ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def _season(log_target: np.ndarray, close_ms: np.ndarray) -> list:
    hod = utc_hour(close_ms)
    overall = float(np.median(log_target))
    out = []
    for hr in range(24):
        sel = log_target[hod == hr]
        out.append(float(np.median(sel)) if sel.size >= 30 else overall)
    return out


def _fit_one(b: Bars, idx: np.ndarray, h_name: str, *, logs, events, tg, weekend) -> dict:
    close_ms = b.times[idx] + BAR_MS
    y = np.log(np.maximum(tg["range"][idx], FLOOR_PCT))
    season = _season(y, close_ms)
    X = design(b, idx, h_name, logs=logs, season=season, events=events, weekend=weekend)
    beta = _ols(X, y)
    S = np.exp(X @ beta)
    z_up, z_dn = tg["up"][idx] / S, tg["down"][idx] / S
    resid = y - X @ beta
    return {
        "horizon": h_name, "bars": HORIZONS[h_name], "beta": [float(v) for v in beta],
        "season": season, "n_anchors": int(idx.size),
        "n_days": int(np.unique(close_ms // 86_400_000).size),
        "resid_sd": float(np.std(resid)),
        "q_one": _quantiles(np.concatenate([z_up, z_dn])),
        "q_max": _quantiles(np.maximum(z_up, z_dn)),
        "q_up": _quantiles(z_up), "q_down": _quantiles(z_dn),
        "q_ret": _quantiles(tg["ret"][idx] / S),
        "q_joint": _joint_table(z_up, z_dn),
    }


# ---- «ни один»: the joint distribution of the two excursions (calibration note §7) -----------------
JOINT_LEVELS = [0.01] + [round(0.05 * k, 2) for k in range(1, 20)] + [0.99]


def _joint_table(z_up: np.ndarray, z_dn: np.ndarray) -> dict:
    """P(z_up <= u_i, z_dn <= v_j) on the 21 x 21 marginal quantiles of the fit."""
    ok = np.isfinite(z_up) & np.isfinite(z_dn)
    zu, zd = z_up[ok], z_dn[ok]
    if zu.size == 0:
        raise RangeModelError("EMPTY_SAMPLE")
    u = np.quantile(zu, JOINT_LEVELS)
    v = np.quantile(zd, JOINT_LEVELS)
    table = np.empty((len(JOINT_LEVELS), len(JOINT_LEVELS)))
    for i, ui in enumerate(u):                                  # one sorted pass per row
        table[i] = np.searchsorted(np.sort(zd[zu <= ui]), v, side="right") / zu.size
    return {"u": [float(x) for x in u], "v": [float(x) for x in v], "F": [[round(float(x), 6) for x in row] for row in table]}


def joint_cdf(q_joint: Mapping[str, Any], a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Bilinear P(z_up <= a, z_dn <= b) from the stored table (clamped to its grid)."""
    u, v, F = np.asarray(q_joint["u"]), np.asarray(q_joint["v"]), np.asarray(q_joint["F"])
    k = np.arange(u.size, dtype=np.float64)
    fi = np.interp(np.asarray(a, dtype=np.float64), u, k)
    fj = np.interp(np.asarray(b, dtype=np.float64), v, k)
    i0, j0 = np.floor(fi).astype(int), np.floor(fj).astype(int)
    i1, j1 = np.minimum(i0 + 1, u.size - 1), np.minimum(j0 + 1, v.size - 1)
    di, dj = fi - i0, fj - j0
    return (F[i0, j0] * (1 - di) * (1 - dj) + F[i1, j0] * di * (1 - dj)
            + F[i0, j1] * (1 - di) * dj + F[i1, j1] * di * dj)


def neither_probability(model: Mapping[str, Any], h_name: str, scale_pct: float, up_pct: float, down_pct: float,
                        *, p_up: Optional[float] = None, p_down: Optional[float] = None) -> float:
    """Chance that within the horizon the price touches neither a level `up_pct` above nor one
    `down_pct` below, from the joint excursion table (never a product of two chances). When the
    single-level chances shown beside it are given, the result is kept coherent with them:
    1 − p_up − p_down <= neither <= 1 − max(p_up, p_down)."""
    m = model["horizons"][h_name]
    p = float(joint_cdf(m["q_joint"], np.array([up_pct / scale_pct]), np.array([down_pct / scale_pct]))[0])
    if p_up is not None and p_down is not None:
        p = min(max(p, 1.0 - p_up - p_down), 1.0 - max(p_up, p_down))
    return float(min(max(p, P_GRID[0] / 10), P_GRID[-1]))


def neither_shown(q_one: Sequence[float], q_joint, xu, xd) -> np.ndarray:
    """`neither_probability` with the single chances it is printed beside, vectorized over standardized
    distances: the value every surface shows and the held-out check scores (note §9)."""
    qs = np.asarray(q_one, dtype=np.float64)
    xu, xd = np.asarray(xu, dtype=np.float64), np.asarray(xd, dtype=np.float64)
    pu = 1.0 - np.interp(xu, qs, P_GRID)                       # = touch_probability (clamped ends)
    pd_ = 1.0 - np.interp(xd, qs, P_GRID)
    p = joint_cdf(q_joint, xu, xd)
    p = np.minimum(np.maximum(p, 1.0 - pu - pd_), 1.0 - np.maximum(pu, pd_))
    return np.clip(p, P_GRID[0] / 10, P_GRID[-1])


def _valid_anchors(b: Bars, logs, tg, h: int, *, stride: int) -> np.ndarray:
    close_ms = b.times + BAR_MS
    on_grid = (close_ms % (stride * BAR_MS)) == 0
    ok = on_grid & np.isfinite(b.close)
    for n in PAST_WINDOWS:
        ok &= np.isfinite(logs[n])
    ok &= np.isfinite(tg["range"]) & np.isfinite(tg["ret"])
    ok[: max(PAST_WINDOWS)] = False
    return np.flatnonzero(ok)


def coverage_of(model_h: Mapping[str, Any], b: Bars, idx: np.ndarray, *, logs, events, tg, weekend,
                coverage: float = COVERAGE) -> dict:
    """Out-of-sample check of a fitted horizon on anchors `idx`."""
    X = design(b, idx, model_h["horizon"], logs=logs, season=model_h["season"], events=events,
               weekend=weekend)
    S = np.exp(X @ np.asarray(model_h["beta"]))
    k = quantile_at(model_h["q_max"], coverage)
    z_max = np.maximum(tg["up"][idx], tg["down"][idx]) / S
    z_one = np.concatenate([tg["up"][idx], tg["down"][idx]]) / np.concatenate([S, S])
    rel = []
    for p in (0.5, 0.8, 0.9):
        u = quantile_at(model_h["q_one"], p)
        rel.append({"predicted_touch": round(1 - p, 3), "realized_touch": round(float(np.mean(z_one >= u)), 4)})
    close_ms = b.times[idx] + BAR_MS
    return {"coverage_target": coverage, "coverage_realized": round(float(np.mean(z_max <= k)), 4),
            "n_anchors": int(idx.size), "n_days": int(np.unique(close_ms // 86_400_000).size),
            "touch_reliability": rel}


# ---- touch-chance calibration on the held-out year (docs/BETA_CHECK_CALIBRATION_DESIGN_V1.md) --------
TOUCH_CAL_VERSION = "TOUCH_CAL_V1"
TOUCH_CAL_GRID_PCT = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0)              # = beta.claims.TOUCH_GRID_PCT (test-pinned)
TOUCH_CAL_BINS = (0.0, 0.05, 0.15, 0.3, 0.5, 0.7, 0.85, 1.0000001)  # = beta.claims.PROB_BINS (test-pinned)
TOUCH_CAL_TOLERANCE = 0.05
TOUCH_CAL_MIN_NEFF = 30                                         # = decision_format.MIN_N_SHOWN (test-pinned)
TOUCH_CAL_EVENT_POST_MS = 60 * 60_000                           # = decision.EVENT_ZONE_POST_MS (test-pinned)
TOUCH_CAL_BOOT = 1000
TOUCH_CAL_SEED = 20261005


def in_event_zone(anchor_close_ms: np.ndarray, events: Mapping[str, Sequence[int]], horizon_ms: int) -> np.ndarray:
    """True where a CPI / FOMC release r has r − H <= anchor < r + 60 min (the live event zone)."""
    ev = np.sort(np.asarray([t for k in EVENT_KINDS for t in events.get(k, ())], dtype=np.int64))
    if ev.size == 0:
        return np.zeros(anchor_close_ms.shape[0], dtype=bool)
    a = np.searchsorted(ev, anchor_close_ms - TOUCH_CAL_EVENT_POST_MS, side="right")
    z = np.searchsorted(ev, anchor_close_ms + horizon_ms, side="right")
    return z > a


def touch_calibration(model_h: Mapping[str, Any], b: Bars, idx: np.ndarray, *, logs, events, tg, weekend,
                      seed: int = TOUCH_CAL_SEED, boot: int = TOUCH_CAL_BOOT) -> dict:
    """Held-out reliability of the touch chance, binned by predicted probability: for every anchor
    outside an event zone, every grid distance and both sides, the train model's chance against
    whether the excursion reached it. Per bin: mean predicted, realized share, the difference,
    raw and effective N (distinct horizon-length slots), a day-clustered 95 % interval of the
    difference and the design note's pass verdict (N_eff >= 30 and |difference| <= 5 pp)."""
    h_name = model_h["horizon"]
    hms = HORIZON_MS[h_name]
    close_ms = b.times[idx] + BAR_MS
    keep = ~in_event_zone(close_ms, events, hms)
    idx, close_ms = idx[keep], close_ms[keep]
    out = {"version": TOUCH_CAL_VERSION, "tolerance_pp": TOUCH_CAL_TOLERANCE * 100, "min_n_eff": TOUCH_CAL_MIN_NEFF,
           "grid_pct": list(TOUCH_CAL_GRID_PCT), "n_anchors": int(idx.size), "bins": []}
    if idx.size == 0:
        return out
    X = design(b, idx, h_name, logs=logs, season=model_h["season"], events=events, weekend=weekend)
    S = np.exp(X @ np.asarray(model_h["beta"]))
    qs = np.asarray(model_h["q_one"], dtype=np.float64)
    ps, ys, slots, days = [], [], [], []
    for d in TOUCH_CAL_GRID_PCT:
        p = 1.0 - np.interp(d / S, qs, P_GRID)             # = touch_probability, vectorized (clamped ends)
        for side in ("up", "down"):
            ps.append(p)
            ys.append((tg[side][idx] >= d).astype(np.float64))
            slots.append(close_ms // hms)
            days.append(close_ms // 86_400_000)
    p, y = np.concatenate(ps), np.concatenate(ys)
    slot, day = np.concatenate(slots), np.concatenate(days)
    rng = np.random.default_rng(seed)
    for lo, hi in zip(TOUCH_CAL_BINS[:-1], TOUCH_CAL_BINS[1:]):
        sel = (p >= lo) & (p < hi)
        n = int(sel.sum())
        if not n:
            continue
        pred, real = float(p[sel].mean()), float(y[sel].mean())
        n_eff = int(np.unique(slot[sel]).size)
        uniq, inv = np.unique(day[sel], return_inverse=True)
        diff_sum = np.bincount(inv, weights=y[sel] - p[sel])
        cnt = np.bincount(inv).astype(np.float64)
        W = rng.multinomial(uniq.size, np.full(uniq.size, 1.0 / uniq.size), size=boot).astype(np.float64)
        with np.errstate(invalid="ignore", divide="ignore"):
            bd = (W @ diff_sum) / (W @ cnt)
        bd = bd[np.isfinite(bd)]
        interval = [round(float(np.quantile(bd, 0.025)) * 100, 2), round(float(np.quantile(bd, 0.975)) * 100, 2)] \
            if bd.size else None
        out["bins"].append({"bin": [lo, min(hi, 1.0)], "n": n, "n_eff": n_eff, "predicted": round(pred, 4),
                            "realized": round(real, 4), "diff_pp": round((real - pred) * 100, 2),
                            "interval_pp": interval,
                            "passed": bool(n_eff >= TOUCH_CAL_MIN_NEFF and abs(real - pred) <= TOUCH_CAL_TOLERANCE)})
    return out


NEITHER_CAL_GRID_PCT = (0.5, 1.0, 2.0, 3.0)                       # = beta.claims.NEITHER_GRID_PCT (test-pinned)


def _binned(p: np.ndarray, y: np.ndarray, slot: np.ndarray, day: np.ndarray, *, seed: int, boot: int) -> list:
    rng = np.random.default_rng(seed)
    out = []
    for lo, hi in zip(TOUCH_CAL_BINS[:-1], TOUCH_CAL_BINS[1:]):
        sel = (p >= lo) & (p < hi)
        n = int(sel.sum())
        if not n:
            continue
        pred, real = float(p[sel].mean()), float(y[sel].mean())
        n_eff = int(np.unique(slot[sel]).size)
        uniq, inv = np.unique(day[sel], return_inverse=True)
        diff_sum = np.bincount(inv, weights=y[sel] - p[sel])
        cnt = np.bincount(inv).astype(np.float64)
        W = rng.multinomial(uniq.size, np.full(uniq.size, 1.0 / uniq.size), size=boot).astype(np.float64)
        with np.errstate(invalid="ignore", divide="ignore"):
            bd = (W @ diff_sum) / (W @ cnt)
        bd = bd[np.isfinite(bd)]
        interval = [round(float(np.quantile(bd, 0.025)) * 100, 2), round(float(np.quantile(bd, 0.975)) * 100, 2)] \
            if bd.size else None
        out.append({"bin": [lo, min(hi, 1.0)], "n": n, "n_eff": n_eff, "predicted": round(pred, 4),
                    "realized": round(real, 4), "diff_pp": round((real - pred) * 100, 2), "interval_pp": interval,
                    "passed": bool(n_eff >= TOUCH_CAL_MIN_NEFF and abs(real - pred) <= TOUCH_CAL_TOLERANCE)})
    return out


def neither_calibration(model_h: Mapping[str, Any], b: Bars, idx: np.ndarray, *, logs, events, tg, weekend,
                        seed: int = TOUCH_CAL_SEED, boot: int = TOUCH_CAL_BOOT) -> dict:
    """Held-out reliability of the «ни один» chance (calibration note §7, corrected in §9): the value the
    surfaces show — the train model's joint table kept coherent with the two single-level chances
    (`neither_probability`) — on the held-out anchors outside event zones, for every pair of the grid."""
    hms = HORIZON_MS[model_h["horizon"]]
    close_ms = b.times[idx] + BAR_MS
    keep = ~in_event_zone(close_ms, events, hms)
    idx, close_ms = idx[keep], close_ms[keep]
    out = {"version": TOUCH_CAL_VERSION, "grid_pct": list(NEITHER_CAL_GRID_PCT), "n_anchors": int(idx.size), "bins": []}
    if idx.size == 0 or "q_joint" not in model_h:
        return out
    X = design(b, idx, model_h["horizon"], logs=logs, season=model_h["season"], events=events, weekend=weekend)
    S = np.exp(X @ np.asarray(model_h["beta"]))
    ps, ys = [], []
    for du in NEITHER_CAL_GRID_PCT:
        for dd in NEITHER_CAL_GRID_PCT:
            ps.append(neither_shown(model_h["q_one"], model_h["q_joint"], du / S, dd / S))
            ys.append(((tg["up"][idx] < du) & (tg["down"][idx] < dd)).astype(np.float64))
    k = len(ps)
    out["bins"] = _binned(np.concatenate(ps), np.concatenate(ys), np.tile(close_ms // hms, k),
                          np.tile(close_ms // 86_400_000, k), seed=seed, boot=boot)
    return out


def touch_bin(p: float) -> Optional[list]:
    """The calibration bin [lo, hi] a predicted chance falls in."""
    for lo, hi in zip(TOUCH_CAL_BINS[:-1], TOUCH_CAL_BINS[1:]):
        if lo <= p < hi:
            return [lo, min(hi, 1.0)]
    return None


def fit_range_model(b: Bars, *, events: Mapping[str, Sequence[int]], stride: int = ANCHOR_STRIDE,
                    holdout_days: int = HOLDOUT_DAYS) -> dict:
    """Fit every horizon; check corridor coverage on the held-out last `holdout_days`, then
    refit on all data. The returned dict is JSON-ready."""
    logs = past_log_ranges(b)
    out: dict = {"version": RANGE_MODEL_VERSION, "features": list(FEATURES), "coverage": COVERAGE,
                 "p_grid": P_GRID, "horizons": {}, "calibration": {}}
    for h_name, h in HORIZONS.items():
        tg = targets(b, h)
        weekend = weekend_share(b, h)
        idx = _valid_anchors(b, logs, tg, h, stride=stride)
        if idx.size < MIN_TRAIN_ANCHORS:
            raise RangeModelError(f"NOT_ENOUGH_ANCHORS:{h_name}:{idx.size}")
        close_ms = b.times[idx] + BAR_MS
        split = close_ms[-1] - holdout_days * 86_400_000
        train, test = idx[close_ms <= split - HORIZON_MS[h_name]], idx[close_ms > split]
        if train.size >= MIN_TRAIN_ANCHORS and test.size >= 200:
            m_train = _fit_one(b, train, h_name, logs=logs, events=events, tg=tg, weekend=weekend)
            cal = coverage_of(m_train, b, test, logs=logs, events=events, tg=tg, weekend=weekend)
            cal["touch_bins"] = touch_calibration(m_train, b, test, logs=logs, events=events, tg=tg, weekend=weekend)
            cal["neither_bins"] = neither_calibration(m_train, b, test, logs=logs, events=events, tg=tg,
                                                      weekend=weekend)
            cal["holdout_from_ms"] = int(b.times[test[0]] + BAR_MS)
            cal["holdout_to_ms"] = int(b.times[test[-1]] + BAR_MS)
            out["calibration"][h_name] = cal
        out["horizons"][h_name] = _fit_one(b, idx, h_name, logs=logs, events=events, tg=tg, weekend=weekend)
        out["horizons"][h_name]["data_from_ms"] = int(close_ms[0])
        out["horizons"][h_name]["data_to_ms"] = int(close_ms[-1])
    out["move"] = sharp_move_threshold(b, out, logs=logs)
    return out


# ---- sharp 15-minute move (push) ----------------------------------------------------------
def sharp_move_scale(b: Bars, idx: np.ndarray, model: Mapping[str, Any], *, logs) -> np.ndarray:
    """The 1h rangecast scale at anchors `idx` with every CPI/FOMC column at 0: same fitted
    coefficients, same volatility, time-of-day and weekend terms; the event term contributes
    nothing. The only scale the sharp-move statistic uses, live and in calibration."""
    m1h = model["horizons"]["1h"]
    X = design(b, idx, "1h", logs=logs, season=m1h["season"], events=_NO_EVENTS)
    return np.exp(X @ np.asarray(m1h["beta"]))


def move_ratio(b: Bars, model: Mapping[str, Any], *, logs) -> np.ndarray:
    """|15-minute return| over the event-neutral 1h scale known before the move started, for
    every bar. The nightly threshold is calibrated on it and the live detector reads it
    (`move_ratio_at`)."""
    w = MOVE_WINDOW_BARS
    idx = np.arange(b.n)
    ok = np.ones(b.n, dtype=bool)
    for n in PAST_WINDOWS:
        ok &= np.isfinite(logs[n])
    out = np.full(b.n, np.nan)
    base = idx[ok]
    if base.size == 0:
        return out
    S = np.full(b.n, np.nan)
    S[base] = sharp_move_scale(b, base, model, logs=logs)
    with np.errstate(invalid="ignore", divide="ignore"):
        prev_close = np.roll(b.close, w)
        prev_S = np.roll(S, w)
        r = np.abs(b.close - prev_close) / prev_close * 100.0 / prev_S
    r[:w] = np.nan
    return r


def _episodes(flags: np.ndarray, gap: int) -> int:
    hits = np.flatnonzero(flags)
    if hits.size == 0:
        return 0
    return int(1 + np.sum(np.diff(hits) > gap))


def move_ratio_at(model: Mapping[str, Any], b: Bars, i: int) -> Optional[float]:
    """`move_ratio` for the move ending at the close of bar i, from bars <= i only: the same
    function the threshold is calibrated with, on the slice that bar's features need."""
    w = MOVE_WINDOW_BARS
    if i is None or i < w or i >= b.n:
        return None
    sub = b.slice(max(0, i - w - max(PAST_WINDOWS) - 1), i + 1)
    r = float(move_ratio(sub, model, logs=past_log_ranges(sub))[-1])
    return r if math.isfinite(r) else None


def sharp_move_threshold(b: Bars, model: Mapping[str, Any], *, logs) -> dict:
    r = move_ratio(b, model, logs=logs)
    fin = r[np.isfinite(r)]
    if fin.size < BARS_PER_DAY * 30:
        return {"threshold": None, "reason": "NOT_ENOUGH_DATA", "statistic": MOVE_STATISTIC}
    days = fin.size / BARS_PER_DAY
    best = None
    for q in MOVE_QUANTILES:
        thr = float(np.quantile(fin, q))
        eps = _episodes(np.nan_to_num(r, nan=0.0) >= thr, MOVE_DECLUSTER_BARS) / days
        cand = {"quantile": q, "threshold": thr, "episodes_per_day": round(eps, 4)}
        if best is None or abs(math.log(max(eps, 1e-6) / MOVE_TARGET_EPISODES_PER_DAY)) < \
                abs(math.log(max(best["episodes_per_day"], 1e-6) / MOVE_TARGET_EPISODES_PER_DAY)):
            best = cand
    best["window_minutes"] = MOVE_WINDOW_BARS * 5
    best["decluster_minutes"] = MOVE_DECLUSTER_BARS * 5
    best["statistic"] = MOVE_STATISTIC
    return best


# ---- live use --------------------------------------------------------------------------
def quantile_at(q: Sequence[float], p: float) -> float:
    return float(np.interp(p, P_GRID, q))


def cdf_at(q: Sequence[float], u: float) -> float:
    """P(z <= u) from a quantile table (clamped to the grid ends)."""
    qs = np.asarray(q, dtype=np.float64)
    if u <= qs[0]:
        return P_GRID[0]
    if u >= qs[-1]:
        return P_GRID[-1]
    return float(np.interp(u, qs, P_GRID))


def scale_at(model: Mapping[str, Any], b: Bars, i: int, h_name: str, *,
             events: Mapping[str, Sequence[int]]) -> Optional[float]:
    """S for an anchor at the close of bar i (features from bars <= i only)."""
    m = model["horizons"].get(h_name)
    if m is None or i is None or i < 0:
        return None
    sub = b.slice(max(0, i - max(PAST_WINDOWS) - 1), i + 1)
    j = sub.n - 1
    logs = past_log_ranges(sub)
    if any(not np.isfinite(logs[n][j]) for n in PAST_WINDOWS):
        return None
    X = design(sub, np.array([j]), h_name, logs=logs, season=m["season"], events=events)
    return float(np.exp(X @ np.asarray(m["beta"]))[0])


def forecast(model: Mapping[str, Any], b: Bars, *, price: float, events: Mapping[str, Sequence[int]],
             coverage: float = COVERAGE) -> dict:
    """Corridor and typical move for every horizon, centred on `price`, anchored at the last
    complete bar. Empty horizons when the past windows are incomplete (never guessed)."""
    i = b.last_complete_index()
    out = {"version": model.get("version"), "price": float(price), "anchor_close_ms": None,
           "coverage": coverage, "horizons": {}}
    if i is None:
        return out
    out["anchor_close_ms"] = int(b.t0 + (i + 1) * BAR_MS)
    for h_name, m in model["horizons"].items():
        S = scale_at(model, b, i, h_name, events=events)
        if S is None:
            continue
        k = quantile_at(m["q_max"], coverage)
        half = k * S
        out["horizons"][h_name] = {
            "scale_pct": S, "half_width_pct": half,
            "lower": price * (1 - half / 100.0), "upper": price * (1 + half / 100.0),
            "typical_move_pct": quantile_at(m["q_one"], 0.5) * S,
            "event_in_window": {k_: bool(event_in_window(np.array([out["anchor_close_ms"]]),
                                                          events.get(k_, ()), HORIZON_MS[h_name])[0])
                                for k_ in EVENT_KINDS},
        }
    return out


def touch_probability(model: Mapping[str, Any], h_name: str, scale_pct: float, distance_pct: float) -> float:
    """Chance that the price reaches a point `distance_pct` away (one side) within the horizon."""
    m = model["horizons"][h_name]
    if distance_pct <= 0:
        return 1.0
    return 1.0 - cdf_at(m["q_one"], abs(distance_pct) / scale_pct)


def stop_stats(model: Mapping[str, Any], fc: Mapping[str, Any], stop_pct: float) -> dict:
    """/risk: for each horizon, how often a move of `stop_pct` against a position happened."""
    out = {}
    for h_name, h in (fc.get("horizons") or {}).items():
        out[h_name] = {"hit_probability": touch_probability(model, h_name, h["scale_pct"], stop_pct),
                       "typical_move_pct": h["typical_move_pct"]}
    return out
