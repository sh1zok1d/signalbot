"""Outcome-blind C025-R1 event admission.

A minute is classified at its close using the bar itself and earlier bars.
No field from after the bar close is read. A later burst cannot drop an
admitted event: the refractory rule looks only backward.
"""

from __future__ import annotations

import math

import numpy as np

from .constants import (
    PRE_WINDOW_MINUTES,
    PRIMARY_QUANTILE,
    PRIMARY_THETA,
    REFRACTORY_MINUTES,
    TRAIL_BARS,
    TWO_SIDED_MAX,
    assert_locked_primary,
)

MINUTE_MS = 60_000


def linear_quantile_from_sorted(sorted_values: np.ndarray, q: float) -> float:
    """numpy.quantile(..., method='linear') on an already sorted window."""
    n = int(sorted_values.shape[0])
    if n < 2:
        raise RuntimeError("quantile window is too short")
    index = q * (n - 1)
    lo = int(math.floor(index))
    hi = int(math.ceil(index))
    weight = index - lo
    return float(sorted_values[lo] * (1.0 - weight) + sorted_values[hi] * weight)


def _slide_sorted(buf: np.ndarray, old: float, new: float) -> None:
    """Replace one occurrence of old with new, preserving sort. In place."""
    if old == new:
        return
    j = int(np.searchsorted(buf, old, side="left"))
    if j >= buf.shape[0] or buf[j] != old:
        raise RuntimeError("sorted window lost the outgoing volume")
    i = int(np.searchsorted(buf, new, side="left"))
    if i > j:
        buf[j:i - 1] = buf[j + 1:i]
        buf[i - 1] = new
    elif i < j:
        buf[i + 1:j + 1] = buf[i:j]
        buf[i] = new
    else:
        buf[j] = new


def trailing_quantile_thresholds(volume: np.ndarray, trail: int, q: float, *, with_rank: bool = False):
    """Quantile of the trail bars strictly before each index. Earlier bars are NaN.

    The value at index i is not inside its own threshold. Future values are
    not inside it either: the window is volume[i-trail:i]. When `with_rank`
    is set, also return the fraction of that window strictly below volume[i].
    """
    volume = np.asarray(volume, dtype=np.float64)
    n = int(volume.shape[0])
    out = np.full(n, np.nan, dtype=np.float64)
    ranks = np.full(n, np.nan, dtype=np.float64)
    if n <= trail:
        return (out, ranks) if with_rank else out
    if trail < 2 or not (0.0 < q < 1.0):
        raise RuntimeError("invalid trailing quantile")
    buf = np.sort(volume[:trail].copy())
    index = q * (trail - 1)
    lo = int(math.floor(index))
    hi = int(math.ceil(index))
    weight = index - lo
    for i in range(trail, n):
        out[i] = buf[lo] * (1.0 - weight) + buf[hi] * weight
        if with_rank:
            ranks[i] = np.searchsorted(buf, volume[i], side="left") / float(trail)
        if i + 1 < n:
            _slide_sorted(buf, float(volume[i - trail]), float(volume[i]))
        if i % 500_000 == 0:
            print(f"C025_R1 quantile {i}/{n}", flush=True)
    return (out, ranks) if with_rank else out


def one_side_score(quote: np.ndarray, taker_quote: np.ndarray) -> np.ndarray:
    """2 * abs(taker_buy_quote / quote - 0.5). Undefined when quote is 0."""
    quote = np.asarray(quote, dtype=np.float64)
    taker = np.asarray(taker_quote, dtype=np.float64)
    score = np.full(quote.shape[0], np.nan, dtype=np.float64)
    ok = quote > 0.0
    share = np.zeros_like(score)
    share[ok] = taker[ok] / quote[ok]
    score[ok] = 2.0 * np.abs(share[ok] - 0.5)
    return score


def bar_log_return(open_: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Return inside the minute: log(close/open). Available at that bar's close."""
    return np.log(np.asarray(close, dtype=np.float64) / np.asarray(open_, dtype=np.float64))


def _rolling_sum_ending_exclusive(values: np.ndarray, window: int) -> np.ndarray:
    """Sum of values[i-window:i] at each i. The first window positions are NaN."""
    cum = np.cumsum(values, dtype=np.float64)
    out = np.full(values.shape[0], np.nan, dtype=np.float64)
    if values.shape[0] <= window:
        return out
    out[window:] = cum[window - 1:-1] - np.concatenate(([0.0], cum[:-window - 1]))
    # cum[i-1] - cum[i-window-1] = sum(values[i-window:i])
    # For i=window, sum(values[0:window]) = cum[window-1]
    out[window] = cum[window - 1]
    return out


def pre_window_sums(abs_ret: np.ndarray, sq_ret: np.ndarray, quote: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        _rolling_sum_ending_exclusive(abs_ret, window),
        _rolling_sum_ending_exclusive(sq_ret, window),
        _rolling_sum_ending_exclusive(quote, window),
    )


def funding_indicator(open_ms: np.ndarray) -> np.ndarray:
    """1 when the minute is inside [settlement-15m, settlement+15m). Clock only."""
    minute = (np.asarray(open_ms) // MINUTE_MS) % 1440
    mod = minute % 480
    dist = np.minimum(mod, 480 - mod)
    return (dist < 15).astype(np.int64)


def clock_parts(open_ms: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ms = np.asarray(open_ms)
    hour = ((ms // 3_600_000) % 24).astype(np.int64)
    year = (ms.astype("datetime64[ms]").astype("datetime64[Y]").astype(np.int64) + 1970)
    return year, hour


def detect_events(panel: dict[str, np.ndarray], *, trail: int | None = None, quantile: float | None = None,
                   theta: float | None = None) -> dict:
    """Admit one-sided and two-sided bursts. Primary constants are the default.

    Tests of the no-lookahead rule may pass a shorter trail. The market path
    calls detect_primary, which refuses overrides.
    """
    if trail is None:
        trail = TRAIL_BARS
    if quantile is None:
        quantile = PRIMARY_QUANTILE
    if theta is None:
        theta = PRIMARY_THETA
    open_ms = np.asarray(panel["open_ms"])
    quote = np.asarray(panel["quote"], dtype=np.float64)
    ret = bar_log_return(panel["open"], panel["close"])
    abs_ret = np.abs(ret)
    score = one_side_score(quote, panel["taker_quote"])
    thresholds, trail_rank = trailing_quantile_thresholds(quote, trail, quantile, with_rank=True)
    burst = (quote >= thresholds) & (quote > 0.0) & np.isfinite(thresholds)
    pre_abs, pre_sq, pre_quote = pre_window_sums(abs_ret, ret * ret, quote, PRE_WINDOW_MINUTES)
    pre_impact = np.divide(pre_abs, pre_quote, out=np.full(pre_abs.shape, np.nan), where=np.isfinite(pre_quote) & (pre_quote > 0.0))
    prior_rv = np.sqrt(pre_sq)
    eligible_pre = (
        np.isfinite(pre_impact) & (pre_impact > 0.0) & np.isfinite(prior_rv) & (pre_quote > 0.0)
    )
    one = burst & eligible_pre & np.isfinite(score) & (score >= theta)
    two = burst & eligible_pre & np.isfinite(score) & (score <= TWO_SIDED_MAX)
    neither = burst & np.isfinite(score) & (score > TWO_SIDED_MAX) & (score < theta)
    # Past-only refractory. Neither-arm bursts do not start it.
    refractory_ms = REFRACTORY_MINUTES * MINUTE_MS
    candidate = np.flatnonzero(one | two)
    accepted = []
    last = None
    rejected_refractory = 0
    for idx in candidate.tolist():
        stamp = int(open_ms[idx])
        if last is not None and stamp - last < refractory_ms:
            rejected_refractory += 1
            continue
        accepted.append(idx)
        last = stamp
    accepted_idx = np.asarray(accepted, dtype=np.int64)
    arm = np.zeros(accepted_idx.shape[0], dtype=np.int64)
    if accepted_idx.size:
        arm[one[accepted_idx]] = 1
        # two-sided stays 0. A bar cannot be both: theta 0.70 > 0.30.
        if np.any(one[accepted_idx] & two[accepted_idx]):
            raise RuntimeError("a bar was labeled both arms")
    year = np.zeros(accepted_idx.shape[0], dtype=np.int64)
    hour = np.zeros(accepted_idx.shape[0], dtype=np.int64)
    if accepted_idx.size:
        year, hour = clock_parts(open_ms[accepted_idx])
    summary = {
        "TOTAL_MINUTES": int(open_ms.shape[0]),
        "RAW_BURSTS": int(np.sum(burst)),
        "NEITHER_N": int(np.sum(neither)),
        "ARM_ELIGIBLE_BEFORE_DECLUSTER": int(candidate.shape[0]),
        "REFRACTORY_REJECTED": int(rejected_refractory),
        "DECLUSTERED_BURSTS": int(accepted_idx.shape[0]),
        "ONE_SIDED_N": int(np.sum(arm == 1)),
        "TWO_SIDED_N": int(np.sum(arm == 0)) if accepted_idx.size else 0,
        "TRAIL_BARS": int(trail),
        "QUANTILE": float(quantile),
        "THETA": float(theta),
    }
    events = {
        "index": accepted_idx,
        "open_ms": open_ms[accepted_idx] if accepted_idx.size else accepted_idx,
        "year": year,
        "hour": hour,
        "arm": arm,
        "quote": quote[accepted_idx] if accepted_idx.size else np.zeros(0),
        "abs_ret": abs_ret[accepted_idx] if accepted_idx.size else np.zeros(0),
        "prior_rv": prior_rv[accepted_idx] if accepted_idx.size else np.zeros(0),
        "pre_impact": pre_impact[accepted_idx] if accepted_idx.size else np.zeros(0),
        "vol_rank": trail_rank[accepted_idx] if accepted_idx.size else np.zeros(0),
        "funding": funding_indicator(open_ms[accepted_idx]) if accepted_idx.size else np.zeros(0, dtype=np.int64),
        "one_side": score[accepted_idx] if accepted_idx.size else np.zeros(0),
    }
    return {
        "summary": summary,
        "events": events,
        "burst": burst,
        "score": score,
        "abs_ret": abs_ret,
        "pre_impact": pre_impact,
        "prior_rv": prior_rv,
        "thresholds": thresholds,
    }


def placebo_candidate_indices(open_ms: np.ndarray, burst: np.ndarray, pre_impact: np.ndarray,
                              prior_rv: np.ndarray, pre_edges: list[float], rv_edges: list[float],
                              max_per: int) -> np.ndarray:
    """Non-burst minutes, chosen with pre-T fields only. At most `max_per` per placebo stratum."""
    year, hour = clock_parts(open_ms)
    fund = funding_indicator(open_ms)
    valid = (~np.asarray(burst)) & np.isfinite(pre_impact) & (pre_impact > 0.0) & np.isfinite(prior_rv)
    decile = np.searchsorted(np.asarray(pre_edges, dtype=np.float64), pre_impact, side="left")
    rv_bin = np.searchsorted(np.asarray(rv_edges, dtype=np.float64), prior_rv, side="left")
    keys = year * 1_000_000 + hour * 10_000 + decile.astype(np.int64) * 100 + rv_bin.astype(np.int64) * 10 + fund
    idx = np.flatnonzero(valid)
    if idx.size == 0:
        return idx.astype(np.int64)
    order = np.argsort(keys[idx], kind="mergesort")
    idx = idx[order]
    sorted_keys = keys[idx]
    cuts = np.flatnonzero(np.diff(sorted_keys)) + 1
    starts = np.concatenate(([0], cuts))
    ends = np.concatenate((cuts, [idx.size]))
    chosen = []
    for start, end in zip(starts.tolist(), ends.tolist()):
        block = idx[start:end]
        if block.size < 2:
            continue
        if block.size > max_per:
            pos = np.unique(np.rint(np.linspace(0, block.size - 1, max_per)).astype(np.int64))
            block = block[pos]
        if block.size >= 2:
            chosen.append(block)
    if not chosen:
        return np.zeros(0, dtype=np.int64)
    return np.concatenate(chosen)


def detect_primary(panel: dict[str, np.ndarray]) -> dict:
    """Market path. The primary variant cannot be replaced from the caller."""
    assert_locked_primary()
    found = detect_events(panel, trail=TRAIL_BARS, quantile=PRIMARY_QUANTILE, theta=PRIMARY_THETA)
    if found["summary"]["THETA"] != PRIMARY_THETA or found["summary"]["QUANTILE"] != PRIMARY_QUANTILE:
        raise RuntimeError("primary detector drifted")
    return found
