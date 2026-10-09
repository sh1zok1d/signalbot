"""Past-only state features for PRE_IMPULSE_STATE_ATLAS_V1.

Feature i uses bars at index <= i only. A missing bar is NaN and is not filled.
A window that contains a NaN is NaN. Zero range makes a ratio NaN.
"""

from __future__ import annotations

import numpy as np

from . import constants as K

FORMULA = {
    "rv_1h": "sqrt of the sum of 12 squared 5m log returns ending at T",
    "rv_4h": "sqrt of the sum of 48 squared 5m log returns ending at T",
    "log_range_1h": "log(max high / min low) over the 12 bars ending at T",
    "log_range_4h": "log(max high / min low) over the 48 bars ending at T",
    "range_ratio_30_240": "log-range of 6 bars divided by log-range of 48 bars, both ending at T",
    "range_ratio_60_240": "log-range of 12 bars divided by log-range of 48 bars, both ending at T",
    "range_ratio_120_240": "log-range of 24 bars divided by log-range of 48 bars, both ending at T",
    "rv_ratio_60_240": "RV of 12 bars divided by RV of 48 bars, both ending at T",
    "compression_slope_1h": "log-range of the last 12 bars minus log-range of the prior 12 bars",
    "efficiency_1h": "abs(sum of 12 log returns) / sum of absolute log returns, ending at T",
    "efficiency_4h": "abs(sum of 48 log returns) / sum of absolute log returns, ending at T",
    "close_pos_4h": "(close - min low) / (max high - min low) on the 48 bars ending at T",
    "dir_changes_1h": "count of adjacent 5m returns with opposite nonzero signs inside the last 12",
    "midpoint_slope_4h": "(late 2h midpoint - early 2h midpoint) / 4h range, inside the 48 bars ending at T",
    "dist_upper_4h": "(4h high - close) / 4h range",
    "dist_lower_4h": "(close - 4h low) / 4h range",
    "frac_near_upper_4h": "fraction of the 48 closes at or above the 4h high minus 0.15 of the 4h range",
    "frac_near_lower_4h": "fraction of the 48 closes at or below the 4h low plus 0.15 of the 4h range",
    "bars_since_upper_4h": "bars since the last upper-band close inside the 48; NaN if none",
    "bars_since_lower_4h": "bars since the last lower-band close inside the 48; NaN if none",
    "touch_count_upper_4h": "entries into the upper band inside the 48, counting a start inside the band",
    "touch_count_lower_4h": "entries into the lower band inside the 48, counting a start inside the band",
    "last_rejection_upper_4h": "pullback from the last upper-band bar to the later low, over the 4h range; 0 if that bar is T",
    "last_rejection_lower_4h": "pullback from the last lower-band bar to the later high, over the 4h range; 0 if that bar is T",
    "extension_up": "(max high of the last 48 bars - max high of the prior 48) / prior 48 range",
    "extension_down": "(min low of the prior 48 - min low of the last 48) / prior 48 range",
    "frac_above_prior_high": "fraction of the last 48 closes strictly above the prior 48 high",
    "frac_below_prior_low": "fraction of the last 48 closes strictly below the prior 48 low",
    "reentry_up": "count of steps from above the prior 48 high back to at or below it, inside the last 48 closes",
    "reentry_down": "count of steps from below the prior 48 low back to at or above it, inside the last 48 closes",
    "adverse_share_4h": "share of absolute 48-return path that moves against the sign of the 4h net log move",
    "last_against_share_4h": "share of absolute path in the trailing run of against-direction returns",
    "countertrend_last_frac_4h": "trailing against-run divided by all against-direction path; NaN if there is none",
    "up_bars_per_vol": "smallest k in 1..48 with log(close[T]/close[T-k]) >= RV_4h; NaN if not reached",
    "down_bars_per_vol": "smallest k in 1..48 with log(close[T-k]/close[T]) >= RV_4h; NaN if not reached",
    "speed_ratio_up_down": "up_bars_per_vol / down_bars_per_vol",
    "mean_clv_1h": "mean of (close-low)/(high-low) on the last 12 bars",
    "mean_upper_wick_1h": "mean of (high-max(open,close))/(high-low) on the last 12 bars",
    "mean_lower_wick_1h": "mean of (min(open,close)-low)/(high-low) on the last 12 bars",
    "mean_body_1h": "mean of abs(close-open)/(high-low) on the last 12 bars",
    "frac_close_upper_1h": "fraction of the last 12 closes in the top quarter of that 12-bar range",
    "frac_close_lower_1h": "fraction of the last 12 closes in the bottom quarter of that 12-bar range",
    "wick_asym_slope_1h": "slope of (lower wick - upper wick) on time centered inside the last 12 bars",
    "xdisp_std_15m": "population std of the Binance, Bybit and OKX 15m log returns ending at T; NaN unless all three exist",
    "n_confirm_15m": "how many of the three 15m returns share the Binance sign, counting Binance; a missing venue does not count",
    "binance_lag_15m": "mean of the finite other-venue 15m returns minus the Binance 15m return",
    "bybit_leader_signed": "sign of the Bybit 15m return when its absolute return is strictly the largest, else 0; NaN if Bybit is missing",
    "okx_leader_signed": "sign of the OKX 15m return when its absolute return is strictly the largest, else 0; NaN if OKX is missing",
    "flow_beta_1h": "demeaned slope of the 12 five-minute log returns on taker imbalance; ineligible",
    "flow_corr_1h": "correlation of those 12 returns with taker imbalance; ineligible",
}

INPUTS = {
    "rv_1h": "close",
    "rv_4h": "close",
    "log_range_1h": "high,low",
    "log_range_4h": "high,low",
    "range_ratio_30_240": "high,low",
    "range_ratio_60_240": "high,low",
    "range_ratio_120_240": "high,low",
    "rv_ratio_60_240": "close",
    "compression_slope_1h": "high,low",
    "efficiency_1h": "close",
    "efficiency_4h": "close",
    "close_pos_4h": "high,low,close",
    "dir_changes_1h": "close",
    "midpoint_slope_4h": "high,low",
    "dist_upper_4h": "high,low,close",
    "dist_lower_4h": "high,low,close",
    "frac_near_upper_4h": "high,low,close",
    "frac_near_lower_4h": "high,low,close",
    "bars_since_upper_4h": "high,low,close",
    "bars_since_lower_4h": "high,low,close",
    "touch_count_upper_4h": "high,low,close",
    "touch_count_lower_4h": "high,low,close",
    "last_rejection_upper_4h": "high,low",
    "last_rejection_lower_4h": "high,low",
    "extension_up": "high,low",
    "extension_down": "high,low",
    "frac_above_prior_high": "high,low,close",
    "frac_below_prior_low": "high,low,close",
    "reentry_up": "high,low,close",
    "reentry_down": "high,low,close",
    "adverse_share_4h": "close",
    "last_against_share_4h": "close",
    "countertrend_last_frac_4h": "close",
    "up_bars_per_vol": "close",
    "down_bars_per_vol": "close",
    "speed_ratio_up_down": "close",
    "mean_clv_1h": "open,high,low,close",
    "mean_upper_wick_1h": "open,high,low",
    "mean_lower_wick_1h": "open,high,low",
    "mean_body_1h": "open,high,low,close",
    "frac_close_upper_1h": "high,low,close",
    "frac_close_lower_1h": "high,low,close",
    "wick_asym_slope_1h": "open,high,low,close",
    "xdisp_std_15m": "binance close, bybit close, okx close",
    "n_confirm_15m": "binance close, bybit close, okx close",
    "binance_lag_15m": "binance close, bybit close, okx close",
    "bybit_leader_signed": "binance close, bybit close, okx close",
    "okx_leader_signed": "binance close, bybit close, okx close",
    "flow_beta_1h": "close, quote, taker_buy_quote",
    "flow_corr_1h": "close, quote, taker_buy_quote",
}

LOOKBACK = {
    "rv_1h": "1h",
    "rv_4h": "4h",
    "log_range_1h": "1h",
    "log_range_4h": "4h",
    "range_ratio_30_240": "4h",
    "range_ratio_60_240": "4h",
    "range_ratio_120_240": "4h",
    "rv_ratio_60_240": "4h",
    "compression_slope_1h": "2h",
    "efficiency_1h": "1h",
    "efficiency_4h": "4h",
    "close_pos_4h": "4h",
    "dir_changes_1h": "1h",
    "midpoint_slope_4h": "4h",
    "dist_upper_4h": "4h",
    "dist_lower_4h": "4h",
    "frac_near_upper_4h": "4h",
    "frac_near_lower_4h": "4h",
    "bars_since_upper_4h": "4h",
    "bars_since_lower_4h": "4h",
    "touch_count_upper_4h": "4h",
    "touch_count_lower_4h": "4h",
    "last_rejection_upper_4h": "4h",
    "last_rejection_lower_4h": "4h",
    "extension_up": "8h",
    "extension_down": "8h",
    "frac_above_prior_high": "8h",
    "frac_below_prior_low": "8h",
    "reentry_up": "8h",
    "reentry_down": "8h",
    "adverse_share_4h": "4h",
    "last_against_share_4h": "4h",
    "countertrend_last_frac_4h": "4h",
    "up_bars_per_vol": "4h",
    "down_bars_per_vol": "4h",
    "speed_ratio_up_down": "4h",
    "mean_clv_1h": "1h",
    "mean_upper_wick_1h": "1h",
    "mean_lower_wick_1h": "1h",
    "mean_body_1h": "1h",
    "frac_close_upper_1h": "1h",
    "frac_close_lower_1h": "1h",
    "wick_asym_slope_1h": "1h",
    "xdisp_std_15m": "15m",
    "n_confirm_15m": "15m",
    "binance_lag_15m": "15m",
    "bybit_leader_signed": "15m",
    "okx_leader_signed": "15m",
    "flow_beta_1h": "1h",
    "flow_corr_1h": "1h",
}


def _nan(n: int) -> np.ndarray:
    return np.full(n, np.nan, dtype=np.float64)


def _roll_extreme(x: np.ndarray, w: int, kind: str) -> np.ndarray:
    out = _nan(x.shape[0])
    if x.shape[0] < w:
        return out
    view = np.lib.stride_tricks.sliding_window_view(x, w)
    fn = np.max if kind == "max" else np.min
    out[w - 1 :] = fn(view, axis=1)
    return out


def _shift(x: np.ndarray, k: int) -> np.ndarray:
    out = np.full_like(x, np.nan)
    out[k:] = x[:-k]
    return out


def _log_returns(close: np.ndarray) -> np.ndarray:
    out = _nan(close.shape[0])
    with np.errstate(divide="ignore", invalid="ignore"):
        out[1:] = np.log(close[1:] / close[:-1])
    return out


def _roll_sum(x: np.ndarray, w: int) -> np.ndarray:
    out = _nan(x.shape[0])
    if x.shape[0] < w:
        return out
    view = np.lib.stride_tricks.sliding_window_view(x, w)
    out[w - 1 :] = np.sum(view, axis=1)
    return out


def _log_range(high: np.ndarray, low: np.ndarray, w: int) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        hi = _roll_extreme(np.log(high), w, "max")
        lo = _roll_extreme(np.log(low), w, "min")
    return hi - lo


def _ratio(short: np.ndarray, long: np.ndarray) -> np.ndarray:
    out = _nan(short.shape[0])
    ok = np.isfinite(short) & np.isfinite(long) & (long > 0.0)
    out[ok] = short[ok] / long[ok]
    return out


def _boundary(high: np.ndarray, low: np.ndarray, close: np.ndarray, w: int = 48) -> dict[str, np.ndarray]:
    n = close.shape[0]
    keys = (
        "dist_upper", "dist_lower", "frac_upper", "frac_lower",
        "since_upper", "since_lower", "touch_upper", "touch_lower",
        "rej_upper", "rej_lower",
    )
    out = {k: _nan(n) for k in keys}
    if n < w:
        return out
    hv = np.lib.stride_tricks.sliding_window_view(high, w)
    lv = np.lib.stride_tricks.sliding_window_view(low, w)
    cv = np.lib.stride_tricks.sliding_window_view(close, w)
    hi = np.max(hv, axis=1)
    lo = np.min(lv, axis=1)
    rng = hi - lo
    finite = np.isfinite(hv).all(axis=1) & np.isfinite(lv).all(axis=1) & np.isfinite(cv).all(axis=1)
    ok = finite & np.isfinite(rng) & (rng > 0.0)
    band = K.NEAR_BAND * rng
    upper = cv >= (hi - band)[:, None]
    lower = cv <= (lo + band)[:, None]
    prev_u = np.zeros_like(upper)
    prev_l = np.zeros_like(lower)
    prev_u[:, 1:] = upper[:, :-1]
    prev_l[:, 1:] = lower[:, :-1]
    touch_u = (upper & ~prev_u).sum(axis=1).astype(np.float64)
    touch_l = (lower & ~prev_l).sum(axis=1).astype(np.float64)
    pos = np.arange(w, dtype=np.int64)
    last_u = np.where(upper, pos, -1).max(axis=1)
    last_l = np.where(lower, pos, -1).max(axis=1)
    since_u = np.where(last_u >= 0, (w - 1) - last_u, np.nan)
    since_l = np.where(last_l >= 0, (w - 1) - last_l, np.nan)
    m = hv.shape[0]
    idx = np.arange(m)
    safe_u = np.clip(last_u, 0, w - 1)
    safe_l = np.clip(last_l, 0, w - 1)
    cummin = np.minimum.accumulate(lv[:, ::-1], axis=1)[:, ::-1]
    cummax = np.maximum.accumulate(hv[:, ::-1], axis=1)[:, ::-1]
    rej_u = (hv[idx, safe_u] - cummin[idx, safe_u]) / rng
    rej_l = (cummax[idx, safe_l] - lv[idx, safe_l]) / rng
    rej_u = np.where(last_u == w - 1, 0.0, rej_u)
    rej_l = np.where(last_l == w - 1, 0.0, rej_l)
    rej_u = np.where(last_u >= 0, rej_u, np.nan)
    rej_l = np.where(last_l >= 0, rej_l, np.nan)
    dist_u = (hi - cv[:, -1]) / rng
    dist_l = (cv[:, -1] - lo) / rng
    frac_u = upper.mean(axis=1)
    frac_l = lower.mean(axis=1)
    sl = slice(w - 1, None)
    for name, arr in (
        ("dist_upper", dist_u), ("dist_lower", dist_l),
        ("frac_upper", frac_u), ("frac_lower", frac_l),
        ("since_upper", since_u), ("since_lower", since_l),
        ("touch_upper", touch_u), ("touch_lower", touch_l),
        ("rej_upper", rej_u), ("rej_lower", rej_l),
    ):
        out[name][sl] = np.where(ok, arr, np.nan)
    return out


def _acceptance(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> dict[str, np.ndarray]:
    n = close.shape[0]
    w = 48
    names = ("extension_up", "extension_down", "frac_above_prior_high", "frac_below_prior_low", "reentry_up", "reentry_down")
    out = {k: _nan(n) for k in names}
    if n < 2 * w:
        return out
    hi = _roll_extreme(high, w, "max")
    lo = _roll_extreme(low, w, "min")
    prior_hi = _shift(hi, w)
    prior_lo = _shift(lo, w)
    prior_rng = prior_hi - prior_lo
    ok_rng = np.isfinite(prior_rng) & (prior_rng > 0.0) & np.isfinite(hi) & np.isfinite(lo)
    out["extension_up"][ok_rng] = (hi[ok_rng] - prior_hi[ok_rng]) / prior_rng[ok_rng]
    out["extension_down"][ok_rng] = (prior_lo[ok_rng] - lo[ok_rng]) / prior_rng[ok_rng]
    cv = np.lib.stride_tricks.sliding_window_view(close, w)
    # row j ends at index j+w-1
    end = np.arange(w - 1, n)
    phi = prior_hi[end]
    plo = prior_lo[end]
    finite = np.isfinite(cv).all(axis=1) & np.isfinite(phi) & np.isfinite(plo) & ok_rng[end]
    above = cv > phi[:, None]
    below = cv < plo[:, None]
    frac_a = above.mean(axis=1)
    frac_b = below.mean(axis=1)
    re_u = (above[:, :-1] & ~above[:, 1:]).sum(axis=1).astype(np.float64)
    re_d = (below[:, :-1] & ~below[:, 1:]).sum(axis=1).astype(np.float64)
    out["frac_above_prior_high"][end] = np.where(finite, frac_a, np.nan)
    out["frac_below_prior_low"][end] = np.where(finite, frac_b, np.nan)
    out["reentry_up"][end] = np.where(finite, re_u, np.nan)
    out["reentry_down"][end] = np.where(finite, re_d, np.nan)
    return out


def _countertrend(ret: np.ndarray) -> dict[str, np.ndarray]:
    n = ret.shape[0]
    w = 48
    out = {k: _nan(n) for k in ("adverse_share_4h", "last_against_share_4h", "countertrend_last_frac_4h")}
    if n < w:
        return out
    view = np.lib.stride_tricks.sliding_window_view(ret, w)
    net = np.sum(view, axis=1)
    sign = np.sign(net)
    against = -sign[:, None] * view
    den = np.sum(np.abs(view), axis=1)
    adverse = np.clip(against, 0.0, None)
    adverse_sum = np.sum(adverse, axis=1)
    mask = against > 0.0
    trail = np.cumprod(mask[:, ::-1].astype(np.int8), axis=1)[:, ::-1].astype(bool)
    last_against = np.sum(adverse * trail, axis=1)
    base = np.isfinite(net) & (sign != 0.0) & (den > 0.0)
    sl = slice(w - 1, None)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["adverse_share_4h"][sl] = np.divide(adverse_sum, den, out=np.full_like(den, np.nan), where=base)
        out["last_against_share_4h"][sl] = np.divide(last_against, den, out=np.full_like(den, np.nan), where=base)
        out["countertrend_last_frac_4h"][sl] = np.divide(
            last_against, adverse_sum, out=np.full_like(den, np.nan), where=base & (adverse_sum > 0.0)
        )
    return out


def _speed(close: np.ndarray, rv_4h: np.ndarray) -> dict[str, np.ndarray]:
    n = close.shape[0]
    out = {k: _nan(n) for k in ("up_bars_per_vol", "down_bars_per_vol", "speed_ratio_up_down")}
    w = 49
    if n < w:
        return out
    with np.errstate(divide="ignore", invalid="ignore"):
        logc = np.log(close)
    view = np.lib.stride_tricks.sliding_window_view(logc, w)
    end = view[:, -1:]
    up_k = (end - view[:, :-1])[:, ::-1]
    down_k = (view[:, :-1] - end)[:, ::-1]
    d = rv_4h[w - 1 :] * K.DIST_MULT
    valid = np.isfinite(d) & (d > 0.0) & np.isfinite(view).all(axis=1)
    up_hit = up_k >= d[:, None]
    down_hit = down_k >= d[:, None]
    up_any = up_hit.any(axis=1) & valid
    down_any = down_hit.any(axis=1) & valid
    up = np.where(up_any, np.argmax(up_hit, axis=1) + 1, np.nan)
    down = np.where(down_any, np.argmax(down_hit, axis=1) + 1, np.nan)
    sl = slice(w - 1, None)
    out["up_bars_per_vol"][sl] = up
    out["down_bars_per_vol"][sl] = down
    both = np.isfinite(up) & np.isfinite(down) & (down > 0.0)
    ratio = _nan(up.shape[0])
    ratio[both] = up[both] / down[both]
    out["speed_ratio_up_down"][sl] = ratio
    return out


def _morphology(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> dict[str, np.ndarray]:
    n = close.shape[0]
    names = (
        "mean_clv_1h", "mean_upper_wick_1h", "mean_lower_wick_1h", "mean_body_1h",
        "frac_close_upper_1h", "frac_close_lower_1h", "wick_asym_slope_1h",
    )
    out = {k: _nan(n) for k in names}
    rng = high - low
    with np.errstate(divide="ignore", invalid="ignore"):
        clv = (close - low) / rng
        upper = (high - np.maximum(open_, close)) / rng
        lower = (np.minimum(open_, close) - low) / rng
        body = np.abs(close - open_) / rng
    bad = ~np.isfinite(rng) | (rng <= 0.0)
    for arr in (clv, upper, lower, body):
        arr[bad] = np.nan
    w = 12
    if n < w:
        return out

    def strict_mean(x: np.ndarray) -> np.ndarray:
        view = np.lib.stride_tricks.sliding_window_view(x, w)
        good = np.isfinite(view).all(axis=1)
        vals = np.where(good, view.mean(axis=1), np.nan)
        dest = _nan(n)
        dest[w - 1 :] = vals
        return dest

    out["mean_clv_1h"] = strict_mean(clv)
    out["mean_upper_wick_1h"] = strict_mean(upper)
    out["mean_lower_wick_1h"] = strict_mean(lower)
    out["mean_body_1h"] = strict_mean(body)
    hi = _roll_extreme(high, w, "max")
    lo = _roll_extreme(low, w, "min")
    span = hi - lo
    cv = np.lib.stride_tricks.sliding_window_view(close, w)
    end = np.arange(w - 1, n)
    top = lo[end] + 0.75 * span[end]
    bot = lo[end] + 0.25 * span[end]
    good = np.isfinite(cv).all(axis=1) & np.isfinite(span[end]) & (span[end] > 0.0)
    frac_u = np.mean(cv >= top[:, None], axis=1)
    frac_l = np.mean(cv <= bot[:, None], axis=1)
    out["frac_close_upper_1h"][end] = np.where(good, frac_u, np.nan)
    out["frac_close_lower_1h"][end] = np.where(good, frac_l, np.nan)
    y = lower - upper
    yv = np.lib.stride_tricks.sliding_window_view(y, w)
    t = np.arange(w, dtype=np.float64) - (w - 1) / 2.0
    tvar = float(np.dot(t, t))
    slope = (yv * t).sum(axis=1) / tvar
    ygood = np.isfinite(yv).all(axis=1)
    out["wick_asym_slope_1h"][w - 1 :] = np.where(ygood, slope, np.nan)
    return out


def _flow(ret: np.ndarray, quote: np.ndarray, taker: np.ndarray) -> dict[str, np.ndarray]:
    n = ret.shape[0]
    out = {"flow_beta_1h": _nan(n), "flow_corr_1h": _nan(n)}
    with np.errstate(divide="ignore", invalid="ignore"):
        imb = np.where(np.isfinite(quote) & (quote > 0.0) & np.isfinite(taker), (2.0 * taker - quote) / quote, np.nan)
    w = 12
    if n < w:
        return out
    rv = np.lib.stride_tricks.sliding_window_view(ret, w)
    iv = np.lib.stride_tricks.sliding_window_view(imb, w)
    good = np.isfinite(rv).all(axis=1) & np.isfinite(iv).all(axis=1)
    rf = rv - rv.mean(axis=1, keepdims=True)
    inf = iv - iv.mean(axis=1, keepdims=True)
    var_i = np.sum(inf * inf, axis=1)
    var_r = np.sum(rf * rf, axis=1)
    cov = np.sum(rf * inf, axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        beta = np.divide(cov, var_i, out=np.full_like(cov, np.nan), where=good & (var_i > 0.0))
        denom = np.sqrt(var_i * var_r)
        corr = np.divide(cov, denom, out=np.full_like(cov, np.nan), where=good & (denom > 0.0))
    out["flow_beta_1h"][w - 1 :] = beta
    out["flow_corr_1h"][w - 1 :] = corr
    return out


def fifteen_minute_return(close: np.ndarray) -> np.ndarray:
    out = _nan(close.shape[0])
    if close.shape[0] < 4:
        return out
    with np.errstate(divide="ignore", invalid="ignore"):
        out[3:] = np.log(close[3:] / close[:-3])
    return out


def cross_venue_features(binance_close: np.ndarray, bybit_close: np.ndarray, okx_close: np.ndarray) -> dict[str, np.ndarray]:
    n = binance_close.shape[0]
    b = fifteen_minute_return(binance_close)
    y = fifteen_minute_return(bybit_close)
    o = fifteen_minute_return(okx_close)
    stacked = np.vstack([b, y, o])
    all3 = np.isfinite(stacked).all(axis=0)
    std = _nan(n)
    std[all3] = stacked[:, all3].std(axis=0, ddof=0)
    sign_b = np.sign(b)
    confirm = _nan(n)
    live = np.isfinite(b) & (sign_b != 0.0)
    same_y = live & np.isfinite(y) & (np.sign(y) == sign_b)
    same_o = live & np.isfinite(o) & (np.sign(o) == sign_b)
    confirm[live] = 1.0 + same_y[live].astype(np.float64) + same_o[live].astype(np.float64)
    others = np.vstack([y, o])
    cnt = np.isfinite(others).sum(axis=0)
    mean_o = np.divide(np.nansum(others, axis=0), cnt, out=_nan(n), where=cnt > 0)
    lag = _nan(n)
    both = np.isfinite(mean_o) & np.isfinite(b)
    lag[both] = mean_o[both] - b[both]

    def leader(own: np.ndarray, peers: list[np.ndarray]) -> np.ndarray:
        dest = _nan(n)
        have = np.isfinite(own)
        own_abs = np.abs(own)
        strict = have.copy()
        for peer in peers:
            peer_abs = np.abs(peer)
            peer_ok = np.isfinite(peer)
            strict &= ~peer_ok | (own_abs > peer_abs)
        dest[have & strict] = np.sign(own[have & strict])
        dest[have & ~strict] = 0.0
        return dest

    return {
        "xdisp_std_15m": std,
        "n_confirm_15m": confirm,
        "binance_lag_15m": lag,
        "bybit_leader_signed": leader(y, [b, o]),
        "okx_leader_signed": leader(o, [b, y]),
    }


def align_closes(grid_open_ms: np.ndarray, venue_open_ms: np.ndarray, venue_close: np.ndarray) -> np.ndarray:
    """Exact open-time match. A missing venue bar stays NaN. Nothing is carried forward."""
    out = _nan(grid_open_ms.shape[0])
    if venue_open_ms.size == 0:
        return out
    pos = np.searchsorted(venue_open_ms, grid_open_ms, side="left")
    valid = pos < venue_open_ms.shape[0]
    pos_c = np.clip(pos, 0, venue_open_ms.shape[0] - 1)
    match = valid & (venue_open_ms[pos_c] == grid_open_ms)
    out[match] = venue_close[pos_c[match]]
    return out


def compute_features(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    quote: np.ndarray,
    taker: np.ndarray,
    bybit_close: np.ndarray | None = None,
    okx_close: np.ndarray | None = None,
) -> dict[str, np.ndarray]:
    n = close.shape[0]
    ret = _log_returns(close)
    rv_1h = np.sqrt(_roll_sum(ret * ret, 12))
    rv_4h = np.sqrt(_roll_sum(ret * ret, 48))
    lr_30 = _log_range(high, low, 6)
    lr_1h = _log_range(high, low, 12)
    lr_2h = _log_range(high, low, 24)
    lr_4h = _log_range(high, low, 48)
    hi4 = _roll_extreme(high, 48, "max")
    lo4 = _roll_extreme(low, 48, "min")
    span4 = hi4 - lo4
    close_pos = _nan(n)
    ok_span = np.isfinite(span4) & (span4 > 0.0) & np.isfinite(close) & np.isfinite(hi4) & np.isfinite(lo4)
    close_pos[ok_span] = (close[ok_span] - lo4[ok_span]) / span4[ok_span]
    hi2 = _roll_extreme(high, 24, "max")
    lo2 = _roll_extreme(low, 24, "min")
    mid = (hi2 + lo2) / 2.0
    early = _shift(mid, 24)
    late = mid
    slope = _nan(n)
    ok_mid = ok_span & np.isfinite(early) & np.isfinite(late)
    slope[ok_mid] = (late[ok_mid] - early[ok_mid]) / span4[ok_mid]
    eff_1 = _nan(n)
    path1 = _roll_sum(np.abs(ret), 12)
    net1 = _roll_sum(ret, 12)
    ok1 = np.isfinite(path1) & (path1 > 0.0)
    eff_1[ok1] = np.abs(net1[ok1]) / path1[ok1]
    eff_4 = _nan(n)
    path4 = _roll_sum(np.abs(ret), 48)
    net4 = _roll_sum(ret, 48)
    ok4 = np.isfinite(path4) & (path4 > 0.0)
    eff_4[ok4] = np.abs(net4[ok4]) / path4[ok4]
    changes = _nan(n)
    if n >= 12:
        view = np.lib.stride_tricks.sliding_window_view(ret, 12)
        good = np.isfinite(view).all(axis=1)
        flips = np.sum(view[:, 1:] * view[:, :-1] < 0.0, axis=1)
        changes[11:] = np.where(good, flips, np.nan)
    bound = _boundary(high, low, close, 48)
    acc = _acceptance(high, low, close)
    ctr = _countertrend(ret)
    spd = _speed(close, rv_4h)
    morph = _morphology(open_, high, low, close)
    flow = _flow(ret, quote, taker)
    if bybit_close is None:
        bybit_close = _nan(n)
    if okx_close is None:
        okx_close = _nan(n)
    xv = cross_venue_features(close, bybit_close, okx_close)
    feat = {
        "rv_1h": rv_1h,
        "rv_4h": rv_4h,
        "log_range_1h": lr_1h,
        "log_range_4h": lr_4h,
        "range_ratio_30_240": _ratio(lr_30, lr_4h),
        "range_ratio_60_240": _ratio(lr_1h, lr_4h),
        "range_ratio_120_240": _ratio(lr_2h, lr_4h),
        "rv_ratio_60_240": _ratio(rv_1h, rv_4h),
        "compression_slope_1h": lr_1h - _shift(lr_1h, 12),
        "efficiency_1h": eff_1,
        "efficiency_4h": eff_4,
        "close_pos_4h": close_pos,
        "dir_changes_1h": changes,
        "midpoint_slope_4h": slope,
        "dist_upper_4h": bound["dist_upper"],
        "dist_lower_4h": bound["dist_lower"],
        "frac_near_upper_4h": bound["frac_upper"],
        "frac_near_lower_4h": bound["frac_lower"],
        "bars_since_upper_4h": bound["since_upper"],
        "bars_since_lower_4h": bound["since_lower"],
        "touch_count_upper_4h": bound["touch_upper"],
        "touch_count_lower_4h": bound["touch_lower"],
        "last_rejection_upper_4h": bound["rej_upper"],
        "last_rejection_lower_4h": bound["rej_lower"],
        "extension_up": acc["extension_up"],
        "extension_down": acc["extension_down"],
        "frac_above_prior_high": acc["frac_above_prior_high"],
        "frac_below_prior_low": acc["frac_below_prior_low"],
        "reentry_up": acc["reentry_up"],
        "reentry_down": acc["reentry_down"],
        "adverse_share_4h": ctr["adverse_share_4h"],
        "last_against_share_4h": ctr["last_against_share_4h"],
        "countertrend_last_frac_4h": ctr["countertrend_last_frac_4h"],
        "up_bars_per_vol": spd["up_bars_per_vol"],
        "down_bars_per_vol": spd["down_bars_per_vol"],
        "speed_ratio_up_down": spd["speed_ratio_up_down"],
        **morph,
        **xv,
        **flow,
    }
    missing = [row["id"] for row in K.FEATURES if row["id"] not in feat]
    if missing:
        raise RuntimeError(f"feature builder missed {missing}")
    return feat
