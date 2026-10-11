"""Point-in-time frame. Future bars affect only the outcome columns."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from scripts.research.level_race_forecast_v1.b0 import race_raw

from . import constants as K


def _bad_bars(high: np.ndarray, low: np.ndarray, close: np.ndarray, quote: np.ndarray) -> np.ndarray:
    return (
        ~np.isfinite(high) | ~np.isfinite(low) | ~np.isfinite(close) | ~np.isfinite(quote)
        | (high < low) | (close > high) | (close < low) | (low <= 0.0) | (quote < 0.0)
    )


def _window_mean(values: np.ndarray, width: int) -> np.ndarray:
    view = np.lib.stride_tricks.sliding_window_view(values, width)
    return view.mean(axis=1)


def _window_sum(values: np.ndarray, width: int) -> np.ndarray:
    view = np.lib.stride_tricks.sliding_window_view(values, width)
    return view.sum(axis=1)


def geometric_impulse(close: float, sigma_5m: float, k: float) -> float:
    sigma_4h = sigma_5m * math.sqrt(K.HORIZON_BARS)
    upper = close * math.exp(k * sigma_4h)
    lower = close * math.exp(-k * sigma_4h)
    p_up, p_down, _p_neither = race_raw(close, upper, lower, sigma_5m, float(K.HORIZON_BARS))
    return float(p_up + p_down)


def label_available_at(close_ms: np.ndarray) -> np.ndarray:
    return np.asarray(close_ms, dtype=np.int64) + np.int64(K.HORIZON_BARS) * np.int64(K.BAR_MS)


def build_frame(bars: dict, k: float = K.PRIMARY_K) -> dict:
    """Kept decision rows for one frozen multiplier. Ambiguous rows are counted and removed."""
    open_ms = np.asarray(bars["open_ms"], dtype=np.int64)
    high = np.asarray(bars["high"], dtype=np.float64)
    low = np.asarray(bars["low"], dtype=np.float64)
    close = np.asarray(bars["close"], dtype=np.float64)
    quote = np.asarray(bars["quote"], dtype=np.float64)
    n = int(open_ms.shape[0])
    if np.any(open_ms >= K.SURFACE_END_MS):
        raise RuntimeError("a bar opens at or after 2025-01-01")
    if n <= K.LOOKBACK + K.HORIZON_BARS:
        raise RuntimeError("series is shorter than the lookback plus the horizon")

    close_ms = open_ms + np.int64(K.BAR_MS)
    bad = _bad_bars(high, low, close, quote)
    bad_cs = np.r_[0, np.cumsum(bad.astype(np.int32))]
    returns = np.full(n, np.nan, dtype=np.float64)
    step = np.diff(open_ms) == np.int64(K.BAR_MS)
    good_step = step & ~bad[1:] & ~bad[:-1]
    returns[1:][good_step] = np.log(close[1:][good_step] / close[:-1][good_step])
    square = np.where(np.isfinite(returns), returns * returns, np.nan)

    mean_288 = _window_mean(np.nan_to_num(square, nan=0.0), K.LOOKBACK)
    finite_288 = np.lib.stride_tricks.sliding_window_view(np.isfinite(square), K.LOOKBACK).all(axis=1)
    mean_48 = _window_mean(np.nan_to_num(square, nan=0.0), K.BARS_4H)
    finite_48 = np.lib.stride_tricks.sliding_window_view(np.isfinite(square), K.BARS_4H).all(axis=1)
    mean_12 = _window_mean(np.nan_to_num(square, nan=0.0), K.BARS_1H)
    finite_12 = np.lib.stride_tricks.sliding_window_view(np.isfinite(square), K.BARS_1H).all(axis=1)
    mean_3 = _window_mean(np.nan_to_num(square, nan=0.0), K.BARS_15M)
    finite_3 = np.lib.stride_tricks.sliding_window_view(np.isfinite(square), K.BARS_15M).all(axis=1)
    quote_288 = _window_sum(quote, K.LOOKBACK)
    quote_48 = _window_sum(quote, K.BARS_4H)
    quote_12 = _window_sum(quote, K.BARS_1H)
    quote_3 = _window_sum(quote, K.BARS_15M)
    high_48 = np.lib.stride_tricks.sliding_window_view(high, K.BARS_4H).max(axis=1)
    low_48 = np.lib.stride_tricks.sliding_window_view(low, K.BARS_4H).min(axis=1)
    future_high = np.lib.stride_tricks.sliding_window_view(high, K.HORIZON_BARS)
    future_low = np.lib.stride_tricks.sliding_window_view(low, K.HORIZON_BARS)

    index = np.arange(n, dtype=np.int64)
    clock = (close_ms % np.int64(K.DECISION_MS) == 0) & (close_ms < K.SURFACE_END_MS)
    room = (index >= K.LOOKBACK) & (index + K.HORIZON_BARS < n)
    horizon_end = close_ms + np.int64(K.HORIZON_BARS) * np.int64(K.BAR_MS)
    eligible_clock = np.flatnonzero(clock & room & (horizon_end <= K.SURFACE_END_MS))
    step_ok = np.zeros(n, dtype=np.int32)
    step_ok[1:] = (np.diff(open_ms) == np.int64(K.BAR_MS)).astype(np.int32)
    step_cs = np.r_[0, np.cumsum(step_ok)]
    # Every completed bar in the lookback and the forward path, not only the endpoints.
    back_steps = (step_cs[eligible_clock + 1] - step_cs[eligible_clock - K.LOOKBACK + 1]) == K.LOOKBACK
    fwd_steps = (step_cs[eligible_clock + K.HORIZON_BARS + 1] - step_cs[eligible_clock + 1]) == K.HORIZON_BARS
    back_clean = (bad_cs[eligible_clock + 1] - bad_cs[eligible_clock - K.LOOKBACK]) == 0
    fwd_clean = (bad_cs[eligible_clock + K.HORIZON_BARS + 1] - bad_cs[eligible_clock + 1]) == 0
    idx = eligible_clock[back_steps & fwd_steps & back_clean & fwd_clean]
    counts = {
        "clock_rows": int(eligible_clock.size),
        "dropped_gap_or_malformed": int(eligible_clock.size - idx.size),
    }
    if idx.size == 0:
        raise RuntimeError("no contiguous decision row")

    end_288 = idx - K.LOOKBACK + 1
    sigma2 = mean_288[end_288]
    finite_scale = finite_288[end_288] & (sigma2 > 0.0)
    sigma = np.sqrt(np.where(finite_scale, sigma2, np.nan))
    sigma_4h = sigma * math.sqrt(K.HORIZON_BARS)
    up = close[idx] * np.exp(k * sigma_4h)
    down = close[idx] * np.exp(-k * sigma_4h)
    path_high = future_high[idx + 1]
    path_low = future_low[idx + 1]
    hit_up = path_high >= up[:, None]
    hit_down = path_low <= down[:, None]
    either = hit_up | hit_down
    has = either.any(axis=1)
    first = np.argmax(either, axis=1)
    row = np.arange(idx.size)
    both = has & hit_up[row, first] & hit_down[row, first]
    up_only = has & hit_up[row, first] & ~hit_down[row, first]
    down_only = has & hit_down[row, first] & ~hit_up[row, first]
    outcome = np.zeros(idx.size, dtype=np.int8)
    outcome[up_only] = 1
    outcome[down_only] = 2
    outcome[both] = 3

    ret_15 = np.log(close[idx] / close[idx - K.BARS_15M])
    ret_1h = np.log(close[idx] / close[idx - K.BARS_1H])
    ret_4h = np.log(close[idx] / close[idx - K.BARS_4H])
    ret_15_z = ret_15 / sigma_4h
    ret_1h_z = ret_1h / sigma_4h
    ret_4h_z = ret_4h / sigma_4h
    past_high = high_48[idx - K.BARS_4H + 1]
    past_low = low_48[idx - K.BARS_4H + 1]
    width = past_high - past_low
    range_pos = np.where(width > 0.0, (close[idx] - past_low) / width, np.nan)
    log_range = np.where((past_high > 0.0) & (past_low > 0.0), np.log(past_high / past_low), np.nan)
    range_vs = log_range / sigma_4h
    rv3 = np.sqrt(mean_3[idx - K.BARS_15M + 1])
    rv12 = np.sqrt(mean_12[idx - K.BARS_1H + 1])
    rv48 = np.sqrt(mean_48[idx - K.BARS_4H + 1])
    finite_rv = finite_3[idx - K.BARS_15M + 1] & finite_12[idx - K.BARS_1H + 1] & finite_48[idx - K.BARS_4H + 1]
    with np.errstate(invalid="ignore", divide="ignore"):
        rv_15_1 = np.where((rv12 > 0.0) & finite_rv, rv3 / rv12, np.nan)
        rv_1_4 = np.where((rv48 > 0.0) & finite_rv, rv12 / rv48, np.nan)
        rv_4_24 = np.where(sigma > 0.0, rv48 / sigma, np.nan)
    q288 = quote_288[idx - K.LOOKBACK + 1]
    q48 = quote_48[idx - K.BARS_4H + 1]
    q12 = quote_12[idx - K.BARS_1H + 1]
    q3 = quote_3[idx - K.BARS_15M + 1]
    vol_15 = np.where(q288 > 0.0, q3 / (q288 * (K.BARS_15M / K.LOOKBACK)), np.nan)
    vol_1h = np.where(q288 > 0.0, q12 / (q288 * (K.BARS_1H / K.LOOKBACK)), np.nan)
    vol_4h = np.where(q288 > 0.0, q48 / (q288 * (K.BARS_4H / K.LOOKBACK)), np.nan)
    ts = pd.to_datetime(close_ms[idx], unit="ms", utc=True)
    hour = ts.hour.to_numpy(dtype=np.float64) + ts.minute.to_numpy(dtype=np.float64) / 60.0
    dow = ts.dayofweek.to_numpy(dtype=np.float64)
    hour_sin = np.sin(2.0 * math.pi * hour / 24.0)
    hour_cos = np.cos(2.0 * math.pi * hour / 24.0)
    dow_sin = np.sin(2.0 * math.pi * dow / 7.0)
    dow_cos = np.cos(2.0 * math.pi * dow / 7.0)
    log_rv = np.log(sigma)
    accel = ret_15_z - ret_1h_z / 4.0
    columns = {
        "log_rv_24h": log_rv,
        "ret_15m_z": ret_15_z,
        "ret_1h_z": ret_1h_z,
        "ret_4h_z": ret_4h_z,
        "range_pos_4h": range_pos,
        "rv_ratio_15m_1h": rv_15_1,
        "rv_ratio_1h_4h": rv_1_4,
        "rv_ratio_4h_24h": rv_4_24,
        "range_vs_sigma_4h": range_vs,
        "vol_ratio_15m": vol_15,
        "vol_ratio_1h": vol_1h,
        "vol_ratio_4h": vol_4h,
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "dow_sin": dow_sin,
        "dow_cos": dow_cos,
        "accel": accel,
    }
    columns["ix_pos_ret4"] = columns["range_pos_4h"] * columns["ret_4h_z"]
    columns["ix_rv_range"] = columns["rv_ratio_15m_1h"] * columns["range_vs_sigma_4h"]
    columns["ix_vol_range"] = columns["vol_ratio_1h"] * columns["range_vs_sigma_4h"]
    columns["ix_pos_rv4"] = columns["range_pos_4h"] * columns["rv_ratio_4h_24h"]
    feature_ok = np.ones(idx.size, dtype=bool)
    for name in (*K.CANDIDATE_FEATURES, "accel"):
        feature_ok &= np.isfinite(columns[name])
    feature_ok &= finite_scale & np.isfinite(sigma_4h)
    kept = feature_ok & (outcome != 3)
    counts["ambiguous"] = int(np.sum(outcome == 3))
    counts["dropped_nonfinite_feature"] = int(np.sum(feature_ok.size and ~feature_ok & (outcome != 3)))
    counts["kept"] = int(np.sum(kept))
    if counts["kept"] == 0:
        raise RuntimeError("no kept decision row")

    kept_idx = idx[kept]
    kept_sigma = sigma[kept]
    p0 = geometric_impulse(float(close[kept_idx[0]]), float(kept_sigma[0]), float(k))
    probe = np.unique(np.linspace(0, kept_idx.size - 1, num=min(64, kept_idx.size), dtype=int))
    for probe_i in probe[1:]:
        probed = geometric_impulse(float(close[kept_idx[probe_i]]), float(kept_sigma[probe_i]), float(k))
        if abs(probed - p0) > 1e-8:
            raise RuntimeError("GEOMETRIC_PROBABILITY_NOT_CONSTANT")
    p_geom = np.full(kept_idx.size, p0, dtype=np.float64)
    touch_ms = np.full(idx.size, -1, dtype=np.int64)
    touch_ms[has] = open_ms[idx[has] + 1 + first[has]] + np.int64(K.BAR_MS)
    wick = np.full(idx.size, np.nan, dtype=np.float64)
    wick[up_only] = np.log(path_high[row[up_only], first[up_only]] / close[idx[up_only]]) / sigma_4h[up_only]
    wick[down_only] = np.log(close[idx[down_only]] / path_low[row[down_only], first[down_only]]) / sigma_4h[down_only]
    matrix = np.column_stack([columns[name][kept] for name in K.CANDIDATE_FEATURES])
    return {
        "k": float(k),
        "counts": counts,
        "close_ms": close_ms[idx[kept]],
        "y": (outcome[kept] > 0).astype(np.float64),
        "direction": np.where(outcome[kept] == 1, 1, np.where(outcome[kept] == 2, -1, 0)).astype(np.int8),
        "outcome": outcome[kept],
        "sigma_5m": sigma[kept],
        "sigma_4h": sigma_4h[kept],
        "p_geom": p_geom,
        "touch_ms": touch_ms[kept],
        "first_offset": np.where(has[kept], first[kept], -1).astype(np.int16),
        "wick_z": wick[kept],
        "features": matrix,
        "feature_names": K.CANDIDATE_FEATURES,
        "accel": columns["accel"][kept],
        "hour": hour[kept],
        "dow": dow[kept].astype(np.int8),
        "map_values": {name: columns[name][kept] for name in (
            "ret_15m_z", "ret_1h_z", "ret_4h_z", "accel",
            "rv_ratio_15m_1h", "rv_ratio_1h_4h", "rv_ratio_4h_24h",
            "vol_ratio_15m", "vol_ratio_1h", "vol_ratio_4h",
            "range_pos_4h", "range_vs_sigma_4h",
        )},
    }
