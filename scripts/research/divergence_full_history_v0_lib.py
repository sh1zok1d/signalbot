"""DIVERGENCE_FULL_HISTORY_RESEARCH_V0: pure functions (outcomes, features, statistics).

Frozen design: `docs/research/DIVERGENCE_FULL_HISTORY_RESEARCH_V0_DESIGN.json`.

In-memory arrays only. Outcome definitions are those of SEED-0001
(`seed0001_exploratory_outcomes.py`), re-implemented with the E1-safe read
horizon instead of the 2025 guard and extended with net R, time to MFE/MAE and
time to +1R / -1R. Mechanism features are point-in-time at the decision time T
and are research covariates only: they never select or exclude episodes.
"""

from __future__ import annotations

import datetime as dt
import math

import numpy as np
from scipy import sparse, stats

from scripts.research import seed0001_regular_divergence_lib as L

MINUTE_MS = 60_000
HOUR_MS = L.BAR_MS


def ms(iso: str) -> int:
    return int(dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


# ------------------------------------------------------------- boundaries

E1_HOLDOUT_START_MS = ms("2026-08-16T00:00:00Z")
E1_HOLDOUT_END_MS = ms("2026-08-25T17:20:00Z")
MAX_FORWARD_HOURS = L.SENSITIVITY_CAP_HOURS            # 96h: the longest outcome / MFE / MAE window
E1_MARGIN_HOURS = 24
DISCOVERY_FIRST_DECISION_MS = ms("2023-01-01T00:00:00Z")
DISCOVERY_LAST_DECISION_MS = ms("2024-12-28T00:00:00Z")
VALIDATION_FIRST_DECISION_MS = ms("2025-01-01T00:00:00Z")
VALIDATION_LAST_DECISION_MS = E1_HOLDOUT_START_MS - (MAX_FORWARD_HOURS + E1_MARGIN_HOURS) * HOUR_MS
READ_HORIZON_MS = VALIDATION_LAST_DECISION_MS + MAX_FORWARD_HOURS * HOUR_MS   # exclusive


class E1BoundaryError(RuntimeError):
    pass


def assert_read_allowed(start_ms: int, end_ms: int) -> None:
    """No read may reach the E1-safe horizon (and so never the E1 holdout)."""
    if end_ms > READ_HORIZON_MS or end_ms > E1_HOLDOUT_START_MS:
        raise E1BoundaryError(f"read [{start_ms}, {end_ms}) reaches the E1-safe horizon")


def slice_of(decision_ms: int) -> str | None:
    if DISCOVERY_FIRST_DECISION_MS <= decision_ms <= DISCOVERY_LAST_DECISION_MS:
        return "DISCOVERY"
    if VALIDATION_FIRST_DECISION_MS <= decision_ms <= VALIDATION_LAST_DECISION_MS:
        return "VALIDATION"
    return None


# --------------------------------------------------------------- outcomes

CAPS_HOURS = (48, 96)
KS = (1, 2)
ROUND_TRIP_COST = 0.0010


def window_slice(t: np.ndarray, start_ms: int, hours: int) -> slice | None:
    end_ms = start_ms + hours * HOUR_MS
    assert_read_allowed(start_ms, end_ms)
    a = int(np.searchsorted(t, start_ms))
    b = int(np.searchsorted(t, end_ms))
    if b - a != hours * 60 or a >= t.size or t[a] != start_ms or t[b - 1] != end_ms - MINUTE_MS:
        return None
    return slice(a, b)


def bracket(high: np.ndarray, low: np.ndarray, entry: float, stop: float, k: int) -> str:
    """SEED-0001 bracket: stop = low < S; target = high >= E + kR; same minute = stop."""
    risk = entry - stop
    s_hits = np.flatnonzero(low < stop)
    g_hits = np.flatnonzero(high >= entry + k * risk)
    s = int(s_hits[0]) if s_hits.size else None
    g = int(g_hits[0]) if g_hits.size else None
    if s is None and g is None:
        return "NEUTRAL"
    if g is not None and (s is None or g < s):
        return "WIN"
    return "LOSS"


def episode_outcomes(minutes: dict, ep: dict) -> dict:
    t, high, low, close = minutes["t"], minutes["high"], minutes["low"], minutes["close"]
    entry, stop = float(ep["ENTRY_REF_PRICE"]), float(ep["STOP_PRICE"])
    risk = entry - stop
    cost_r = ROUND_TRIP_COST * entry / risk
    out = {"R": risk, "COST_R": cost_r}
    for cap in CAPS_HOURS:
        sl = window_slice(t, int(ep["DECISION_TIME_MS"]), cap)
        if sl is None:
            for k in KS:
                out[f"Y{k}_{cap}H_WLN"], out[f"Y{k}_{cap}H"], out[f"NET_R{k}_{cap}H"] = "UNAVAILABLE", None, None
            for key in ("FWD_RET", "FWD_R", "MFE_R", "MAE_R", "T_MFE_H", "T_MAE_H"):
                out[f"{key}_{cap}H"] = None
            continue
        h, lo, c_h = high[sl], low[sl], float(close[sl.stop - 1])
        fwd_r = (c_h - entry) / risk
        for k in KS:
            wln = bracket(h, lo, entry, stop, k)
            out[f"Y{k}_{cap}H_WLN"], out[f"Y{k}_{cap}H"] = wln, int(wln == "WIN")
            gross = float(k) if wln == "WIN" else -1.0 if wln == "LOSS" else fwd_r
            out[f"NET_R{k}_{cap}H"] = gross - cost_r
        out[f"FWD_RET_{cap}H"] = c_h / entry - 1.0
        out[f"FWD_R_{cap}H"] = fwd_r
        out[f"MFE_R_{cap}H"] = (float(h.max()) - entry) / risk
        out[f"MAE_R_{cap}H"] = (entry - float(lo.min())) / risk
        out[f"T_MFE_H_{cap}H"] = int(np.argmax(h)) / 60.0
        out[f"T_MAE_H_{cap}H"] = int(np.argmin(lo)) / 60.0
    sl = window_slice(t, int(ep["DECISION_TIME_MS"]), MAX_FORWARD_HOURS)
    if sl is None:
        out["T_HIT_P1R_H"], out["T_HIT_M1R_H"] = None, None
    else:
        up = np.flatnonzero(high[sl] >= entry + risk)
        dn = np.flatnonzero(low[sl] < stop)
        out["T_HIT_P1R_H"] = int(up[0]) / 60.0 if up.size else None
        out["T_HIT_M1R_H"] = int(dn[0]) / 60.0 if dn.size else None
    return out


# --------------------------------------------------------------- features

FEATURES = (
    "DIV_RSI14_DELTA", "DIV_RSI21_DELTA", "DIV_MACD_DELTA_ATR", "DIV_CVD_SHARE",
    "LEG_DEPTH_ATR", "NEW_LOW_DEPTH_ATR", "PIVOT_SPACING_BARS",
    "SUPPORT_EXCESS", "BOOK_IMB_AT_LOW",
    "NETFLOW24", "SELL_PRESSURE_CHANGE", "FLOW_AFTER_LOW",
    "OI_CHG_24H", "OI_CHG_LEG", "LIQ_PROXY",
    "RV24_LOG", "ATR_PCT", "HTF_EMA168_DIST_ATR", "RET_7D", "NEW_LOW_30D_ATR",
    "MKT_RET24", "BTC_RET24",
)
HTF_EMA_BARS = 168
LIQ_OI_DROP = -0.01
LIQ_VOLUME_MULT = 3.0


def _share(tb: np.ndarray, v: np.ndarray) -> float:
    s = float(np.sum(v))
    return float(np.sum(2.0 * tb - v) / s) if s > 0 else float("nan")


def oi_asof(oi: dict | None, at_ms: int) -> float:
    """Open interest available at at_ms: the last 5m record with create_time + 5min <= at_ms."""
    if oi is None or oi["available_ms"].size == 0:
        return float("nan")
    k = int(np.searchsorted(oi["available_ms"], at_ms, side="right")) - 1
    if k < 0 or at_ms - oi["available_ms"][k] > 30 * MINUTE_MS:
        return float("nan")
    return float(oi["value"][k])


def episode_features(bars: dict, ind: dict, ema168: np.ndarray, book_imb: np.ndarray, oi: dict | None,
                     market_close: dict, ep: dict) -> dict:
    """Point-in-time mechanism features at T (bars up to i+3, book hours up to i+3, OI available at T)."""
    grid = bars["open_time_ms"]
    i = int(np.searchsorted(grid, ms(ep["PIVOT_BAR_OPEN_UTC"])))
    j = int(np.searchsorted(grid, ms(ep["COMPARISON_PIVOT_OPEN_UTC"])))
    d = i + L.PIVOT_RIGHT
    t_ms = int(ep["DECISION_TIME_MS"])
    if int(grid[d]) + HOUR_MS != t_ms:
        raise ValueError("episode does not align with the bar grid")
    atr_i = float(ind["atr"][i])
    vol, tb, close, low = bars["volume"], bars["taker_buy"], bars["close"], bars["low"]
    gap = i - j
    lo_prev = max(j - gap + 1, 0)
    f = {
        "DIV_RSI14_DELTA": float(ind["rsi14"][i] - ind["rsi14"][j]),
        "DIV_RSI21_DELTA": float(ind["rsi21"][i] - ind["rsi21"][j]),
        "DIV_MACD_DELTA_ATR": float((ind["macd"][i] - ind["macd"][j]) / atr_i),
        "DIV_CVD_SHARE": _share(tb[j + 1:i + 1], vol[j + 1:i + 1]),
        "LEG_DEPTH_ATR": float(ep["DECLINE_ATR"]),
        "NEW_LOW_DEPTH_ATR": float((low[j] - low[i]) / atr_i),
        "PIVOT_SPACING_BARS": float(gap),
        "SUPPORT_EXCESS": float(ep["SUPPORT_MAX_IMBALANCE"]) - float(ep["SUPPORT_TRAILING_Q80"]),
        "BOOK_IMB_AT_LOW": float(book_imb[i]),
        "NETFLOW24": float(ep["NETFLOW24"]),
        "SELL_PRESSURE_CHANGE": _share(tb[j + 1:i + 1], vol[j + 1:i + 1]) - _share(tb[lo_prev:j + 1], vol[lo_prev:j + 1]),
        "FLOW_AFTER_LOW": _share(tb[i + 1:d + 1], vol[i + 1:d + 1]),
        "RV24_LOG": float(np.log(float(ep["RV24"]))),
        "ATR_PCT": atr_i / float(close[i]),
        "HTF_EMA168_DIST_ATR": float((close[d] - ema168[d]) / atr_i),
        "RET_7D": float(close[d] / close[d - 168] - 1.0) if d >= 168 else float("nan"),
        "NEW_LOW_30D_ATR": float((np.min(low[max(i - 720, 0):i]) - low[i]) / atr_i) if i >= 720 else float("nan"),
    }
    oi_t, oi_24 = oi_asof(oi, t_ms), oi_asof(oi, t_ms - 24 * HOUR_MS)
    oi_i, oi_j = oi_asof(oi, int(grid[i]) + HOUR_MS), oi_asof(oi, int(grid[j]) + HOUR_MS)
    oi_i6 = oi_asof(oi, int(grid[i]) + HOUR_MS - 6 * HOUR_MS)
    f["OI_CHG_24H"] = oi_t / oi_24 - 1.0 if oi_24 > 0 else float("nan")
    f["OI_CHG_LEG"] = oi_i / oi_j - 1.0 if oi_j > 0 else float("nan")
    oi_drop = oi_i / oi_i6 - 1.0 if oi_i6 > 0 else float("nan")
    base = vol[max(i - 720, 0):i]
    med = float(np.median(base)) if base.size else float("nan")
    spike = float(np.max(vol[i - 5:i + 1])) >= LIQ_VOLUME_MULT * med if med > 0 else False
    f["LIQ_PROXY"] = float(oi_drop <= LIQ_OI_DROP and spike) if not math.isnan(oi_drop) else float("nan")
    rets = []
    for sym_close in market_close.values():
        c_d, c_0 = sym_close.get(t_ms), sym_close.get(t_ms - 24 * HOUR_MS)
        if c_d and c_0:
            rets.append(math.log(c_d / c_0))
    f["MKT_RET24"] = float(np.mean(rets)) if len(rets) == len(market_close) else float("nan")
    btc = market_close.get("BTCUSDT", {})
    c_d, c_0 = btc.get(t_ms), btc.get(t_ms - 24 * HOUR_MS)
    f["BTC_RET24"] = math.log(c_d / c_0) if c_d and c_0 else float("nan")
    return f


def ema_by_segment(bars: dict, n: int) -> np.ndarray:
    out = np.full(bars["open_time_ms"].size, np.nan)
    for a, b in L.segments(bars["complete"]):
        out[a:b] = L.ema(bars["close"][a:b], n)
    return out


def close_by_decision_time(bars: dict) -> dict:
    """Map decision time (bar close) -> close, for complete bars only."""
    t = bars["open_time_ms"] + HOUR_MS
    ok = bars["complete"]
    return dict(zip(t[ok].tolist(), bars["close"][ok].tolist()))


# Pre-specified mechanism states (research covariates, never selection rules).
def deeper_state_flow_oi(f: dict) -> float:
    """Selling weakens into the new low and OI does not expand: no oscillator input."""
    if math.isnan(f["SELL_PRESSURE_CHANGE"]) or math.isnan(f["OI_CHG_LEG"]):
        return float("nan")
    return float(f["SELL_PRESSURE_CHANGE"] > 0 and f["OI_CHG_LEG"] <= 0)


# ------------------------------------------------------------- statistics

def ols_cr1(X: np.ndarray, y: np.ndarray, clusters) -> dict:
    n, k = X.shape
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    resid = y - X @ beta
    _, g = np.unique(np.asarray(clusters), return_inverse=True)
    n_g = int(g.max()) + 1
    member = sparse.csr_matrix((np.ones(n), (g, np.arange(n))), shape=(n_g, n))
    scores = member @ (X * resid[:, None])
    meat = scores.T @ scores
    factor = n_g / (n_g - 1) * (n - 1) / (n - k) if n_g > 1 and n > k else float("nan")
    return {"beta": beta, "V": factor * xtx_inv @ meat @ xtx_inv, "G": n_g, "n": n}


def contrast(fit: dict, c) -> dict:
    c = np.asarray(c, dtype=float)
    est = float(c @ fit["beta"])
    var = float(c @ fit["V"] @ c)
    se = math.sqrt(var) if var > 0 else float("nan")
    df = fit["G"] - 1
    if not se > 0 or df < 1:
        return {"ESTIMATE": est, "SE_CR1": se, "DF": df, "P_TWO_SIDED": None, "CI95": [None, None]}
    t = est / se
    half = float(stats.t.ppf(0.975, df)) * se
    return {"ESTIMATE": est, "SE_CR1": se, "DF": df, "P_TWO_SIDED": float(2 * stats.t.sf(abs(t), df)),
            "CI95": [est - half, est + half]}


def holm(pvalues: dict) -> dict:
    items = sorted((p, k) for k, p in pvalues.items() if p is not None)
    m = len(items)
    adj, running = {}, 0.0
    for rank, (p, k) in enumerate(items):
        running = max(running, min(1.0, (m - rank) * p))
        adj[k] = running
    return adj


def heterogeneity_q(estimates: list[tuple[float, float]]) -> dict:
    rows = [(e, s) for e, s in estimates if s is not None and not math.isnan(s) and s > 0]
    if len(rows) < 2:
        return {"Q": None, "DF": None, "P": None, "K": len(rows)}
    th = np.array([r[0] for r in rows])
    w = 1.0 / np.array([r[1] for r in rows]) ** 2
    pooled = float((w * th).sum() / w.sum())
    q = float((w * (th - pooled) ** 2).sum())
    return {"Q": q, "DF": len(rows) - 1, "P": float(stats.chi2.sf(q, len(rows) - 1)), "K": len(rows),
            "INVERSE_VARIANCE_POOLED": pooled}


def week_bootstrap(X: np.ndarray, y: np.ndarray, clusters, c, *, resamples: int, seed: int) -> dict:
    keys, g = np.unique(np.asarray(clusters), return_inverse=True)
    members = [np.flatnonzero(g == j) for j in range(keys.size)]
    rng = np.random.default_rng(seed)
    c = np.asarray(c, dtype=float)
    draws, skipped = [], 0
    for _ in range(resamples):
        idx = np.concatenate([members[j] for j in rng.integers(0, keys.size, size=keys.size)])
        Xb = X[idx]
        if np.linalg.matrix_rank(Xb) < Xb.shape[1]:
            skipped += 1
            continue
        beta = np.linalg.lstsq(Xb, y[idx], rcond=None)[0]
        draws.append(float(c @ beta))
    d = np.array(draws)
    return {"RESAMPLES": resamples, "SEED": seed, "USED": int(d.size), "SKIPPED": skipped,
            "CI95_PERCENTILE": [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))] if d.size else [None, None]}


def smd(a, b) -> float | None:
    a = np.asarray([x for x in a if x is not None and not math.isnan(x)], dtype=float)
    b = np.asarray([x for x in b if x is not None and not math.isnan(x)], dtype=float)
    if a.size < 2 or b.size < 2:
        return None
    pooled = math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0)
    return None if pooled == 0 else float((a.mean() - b.mean()) / pooled)
