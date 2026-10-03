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
    }


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
            cal["holdout_from_ms"] = int(b.times[test[0]] + BAR_MS)
            cal["holdout_to_ms"] = int(b.times[test[-1]] + BAR_MS)
            out["calibration"][h_name] = cal
        out["horizons"][h_name] = _fit_one(b, idx, h_name, logs=logs, events=events, tg=tg, weekend=weekend)
        out["horizons"][h_name]["data_from_ms"] = int(close_ms[0])
        out["horizons"][h_name]["data_to_ms"] = int(close_ms[-1])
    out["move"] = sharp_move_threshold(b, out, logs=logs, events=events)
    return out


# ---- sharp 15-minute move (push) ----------------------------------------------------------
def move_ratio(b: Bars, model: Mapping[str, Any], *, logs, events) -> np.ndarray:
    """|15-minute return| over the 1h scale known before the move started, for every bar."""
    w = MOVE_WINDOW_BARS
    m1h = model["horizons"]["1h"]
    idx = np.arange(b.n)
    ok = np.ones(b.n, dtype=bool)
    for n in PAST_WINDOWS:
        ok &= np.isfinite(logs[n])
    out = np.full(b.n, np.nan)
    base = idx[ok]
    if base.size == 0:
        return out
    X = design(b, base, "1h", logs=logs, season=m1h["season"], events=events)
    S = np.full(b.n, np.nan)
    S[base] = np.exp(X @ np.asarray(m1h["beta"]))
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


def sharp_move_threshold(b: Bars, model: Mapping[str, Any], *, logs, events) -> dict:
    r = move_ratio(b, model, logs=logs, events=events)
    fin = r[np.isfinite(r)]
    if fin.size < BARS_PER_DAY * 30:
        return {"threshold": None, "reason": "NOT_ENOUGH_DATA"}
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
