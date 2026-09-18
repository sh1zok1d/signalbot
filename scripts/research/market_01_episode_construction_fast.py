"""Semantics-preserving fast episode construction for MARKET-01-style rules.

Does not change the frozen MARKET-01 scientific library, RESULT, prereg,
thresholds, or estimand. Does not consume the canonical reservation.
Does not evaluate confirmatory OLS/bootstrap/classification.

`construct_episodes_fast` must match frozen `construct_episodes` episode
fields on the same PriceView/OiView. Bound CORE/OI snapshot identities
still refuse through the frozen guard.

This module is research-throughput infrastructure for later MARKET
hypotheses. It is not a second MARKET-01 scientific execution.
"""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from scripts.research.market_01_oi_expansion_weak_continuation_lib import (
    BAR_MS,
    COMMON_END_MS,
    COMMON_START_MS,
    CONTINUATION_MAX,
    EPISODE_MS,
    FIVE_MS,
    HIST_MS,
    IMPULSE_P_MIN,
    NINETY_M_MS,
    OI_STALE_MS,
    OI_P_STRICT,
    SIXTY_M_MS,
    THIRTY_M_MS,
    EpisodeRecord,
    Market01Error,
    OiView,
    PriceView,
    _five_minute_range,
    _guard_views,
    construct_episodes,
    log_ratio,
    midrank_percentile,
    stratum_id,
    tertile_state,
)

_VOL_RETURNS = 60

EPISODE_FIELDS = (
    "impulse_end_t_ms",
    "impulse_start_ms",
    "decision_T_ms",
    "outcome_end_ms",
    "impulse_return",
    "D",
    "abs_impulse",
    "p_impulse",
    "qualifying_impulse",
    "occupies_slot",
    "oi_start",
    "oi_end",
    "delta_oi",
    "p_oi",
    "oi_expansion",
    "state_return",
    "continuation_ratio",
    "weak_continuation",
    "candidate",
    "pre_vol_60",
    "impulse_mag_state",
    "trailing_vol_state",
    "stratum_id",
    "reversal_return",
    "confirmatory_eligible",
    "exclusion_reason",
)


def _as_int64(arr: np.ndarray) -> np.ndarray:
    return np.asarray(arr, dtype=np.int64)


def _contiguous_1m(price: PriceView) -> bool:
    open_ms = _as_int64(price.open_time_ms)
    avail = _as_int64(price.available_at_ms)
    if open_ms.size < 1:
        return False
    if int(open_ms[0]) % BAR_MS != 0:
        return False
    if open_ms.size > 1 and np.any(np.diff(open_ms) != BAR_MS):
        return False
    if np.any(avail != open_ms + BAR_MS):
        return False
    return True


def _close_1m_clock(price: PriceView, clock_ms: np.ndarray) -> np.ndarray:
    """Vectorized close_at for many bar_end_exclusive clocks. NaN if illegal."""
    open0 = int(price.open_time_ms[0])
    n = int(price.close.shape[0])
    clock = np.asarray(clock_ms, dtype=np.int64)
    out = np.full(clock.shape, np.nan, dtype=np.float64)
    open_t = clock - BAR_MS
    delta = open_t - open0
    ok = (delta >= 0) & (delta % BAR_MS == 0)
    idx = np.zeros(clock.shape, dtype=np.int64)
    idx[ok] = delta[ok] // BAR_MS
    ok &= (idx >= 0) & (idx < n)
    if not np.any(ok):
        return out
    idx_ok = idx[ok]
    open_ok = _as_int64(price.open_time_ms)[idx_ok]
    avail_ok = _as_int64(price.available_at_ms)[idx_ok]
    close_ok = np.asarray(price.close, dtype=np.float64)[idx_ok]
    aligned = (open_ok == open_t[ok]) & (avail_ok == clock[ok])
    pos = np.isfinite(close_ok) & (close_ok > 0.0)
    keep = aligned & pos
    dest = np.flatnonzero(ok)[keep]
    out[dest] = close_ok[keep]
    return out


def _log_ratio_arr(end: np.ndarray, start: np.ndarray) -> np.ndarray:
    out = np.full(end.shape, np.nan, dtype=np.float64)
    ok = (
        np.isfinite(end)
        & np.isfinite(start)
        & (end > 0.0)
        & (start > 0.0)
    )
    if not np.any(ok):
        return out
    # math.log per element so values match the frozen log_ratio contract.
    end_ok = end[ok]
    start_ok = start[ok]
    vals = np.empty(end_ok.shape[0], dtype=np.float64)
    for i in range(end_ok.shape[0]):
        v = math.log(float(end_ok[i]) / float(start_ok[i]))
        vals[i] = v if math.isfinite(v) else np.nan
    out[ok] = vals
    return out


def _logret_1m(price: PriceView) -> np.ndarray:
    """1m log returns aligned to bar i (return ending at available_at[i])."""
    n = int(price.close.shape[0])
    close = np.asarray(price.close, dtype=np.float64)
    logret = np.full(n, np.nan, dtype=np.float64)
    for i in range(1, n):
        left = float(close[i - 1])
        right = float(close[i])
        if not (
            math.isfinite(left)
            and left > 0.0
            and math.isfinite(right)
            and right > 0.0
        ):
            continue
        ret = math.log(right / left)
        if math.isfinite(ret):
            logret[i] = ret
    return logret


def _pre_vol_on_clocks(
    price: PriceView, clocks: np.ndarray, logret: np.ndarray
) -> np.ndarray:
    """PRE_VOL_60 at each clock using b2_03's 60-term math.sqrt accumulation."""
    open0 = int(price.open_time_ms[0])
    n = int(logret.shape[0])
    open_ms = _as_int64(price.open_time_ms)
    avail = _as_int64(price.available_at_ms)
    out = np.full(clocks.shape, np.nan, dtype=np.float64)
    window = _VOL_RETURNS
    for i, raw_clock in enumerate(clocks):
        clock = int(raw_clock)
        open_t = clock - BAR_MS
        delta = open_t - open0
        if delta < 0 or delta % BAR_MS != 0:
            continue
        j = delta // BAR_MS
        if j < window or j >= n:
            continue
        if int(open_ms[j]) != open_t or int(avail[j]) != clock:
            continue
        start_k = j - (window - 1)
        energy = 0.0
        good = True
        for k in range(start_k, j + 1):
            ret = float(logret[k])
            if not math.isfinite(ret):
                good = False
                break
            energy += ret * ret
        if not good or energy < 0.0:
            continue
        value = math.sqrt(energy)
        if math.isfinite(value):
            out[i] = value
    return out


def _legal_oi_vector(oi: OiView, clocks: np.ndarray) -> np.ndarray:
    avail = _as_int64(oi.available_at_ms)
    values = np.asarray(oi.sum_open_interest, dtype=np.float64)
    clocks = np.asarray(clocks, dtype=np.int64)
    out = np.full(clocks.shape, np.nan, dtype=np.float64)
    if avail.size == 0 or clocks.size == 0:
        return out
    idx = np.searchsorted(avail, clocks, side="right") - 1
    valid = idx >= 0
    if not np.any(valid):
        return out
    idx_v = idx[valid]
    available_at = avail[idx_v]
    stale = clocks[valid] - available_at
    good = (available_at <= clocks[valid]) & (stale <= OI_STALE_MS)
    picked = values[idx_v]
    pos = np.isfinite(picked) & (picked > 0.0)
    keep = good & pos
    dest = np.flatnonzero(valid)[keep]
    out[dest] = picked[keep]
    return out


def _slice_or_empty(arr: np.ndarray, lo: int, hi: int) -> np.ndarray:
    if hi <= 0:
        return arr[:0]
    if lo < 0:
        lo = 0
    if lo >= hi:
        return arr[:0]
    if hi > arr.shape[0]:
        hi = int(arr.shape[0])
    if lo >= hi:
        return arr[:0]
    return arr[lo:hi]


def _at(arr: np.ndarray, i: int) -> float:
    if i < 0 or i >= arr.shape[0]:
        return float("nan")
    return float(arr[i])


def construct_episodes_fast(price: PriceView, oi: OiView) -> list[EpisodeRecord]:
    """Frozen-rule episode construction with precomputed rolling arrays.

    Falls back to frozen ``construct_episodes`` when 1m price is not a
    contiguous bar_end_exclusive grid (the CORE/MARKET-01 case is).
    """
    _guard_views(price, oi)
    if int(price.open_time_ms[0]) % BAR_MS != 0:
        raise Market01Error("price open_time_ms is not 1m aligned")
    if not _contiguous_1m(price):
        return construct_episodes(price, oi)

    first_end = int(price.available_at_ms[0])
    last_end = int(price.available_at_ms[-1])
    t_lo = max(first_end, COMMON_START_MS + THIRTY_M_MS)
    t_hi = min(last_end, COMMON_END_MS - NINETY_M_MS)
    eval_ts = _five_minute_range(t_lo, t_hi + 1)
    if eval_ts.size == 0:
        return []

    hist_need = int(eval_ts[0]) - THIRTY_M_MS - HIST_MS
    series_lo = min(first_end, hist_need)
    series_hi = int(eval_ts[-1]) + THIRTY_M_MS + SIXTY_M_MS
    clocks5 = _five_minute_range(series_lo, series_hi + 1)
    if clocks5.size == 0:
        return construct_episodes(price, oi)
    grid0 = int(clocks5[0])
    n5 = int(clocks5.shape[0])

    def idx5(clock: int) -> int:
        return (int(clock) - grid0) // FIVE_MS

    close5 = _close_1m_clock(price, clocks5)
    close5_lag = _close_1m_clock(price, clocks5 - THIRTY_M_MS)
    signed_imp = _log_ratio_arr(close5, close5_lag)
    abs_imp = np.abs(signed_imp)

    oi5 = _legal_oi_vector(oi, clocks5)
    oi5_lag = _legal_oi_vector(oi, clocks5 - THIRTY_M_MS)
    delta_oi = _log_ratio_arr(oi5, oi5_lag)

    logret = _logret_1m(price)
    vol5 = _pre_vol_on_clocks(price, clocks5, logret)

    episodes: list[EpisodeRecord] = []
    occupied_until_impulse_start = -1
    for t in eval_ts:
        t = int(t)
        impulse_start = t - THIRTY_M_MS
        T = t + THIRTY_M_MS
        outcome_end = T + SIXTY_M_MS
        rec = EpisodeRecord(
            impulse_end_t_ms=t,
            impulse_start_ms=impulse_start,
            decision_T_ms=T,
            outcome_end_ms=outcome_end,
        )
        if impulse_start < COMMON_START_MS or outcome_end > COMMON_END_MS:
            rec.exclusion_reason = "not_completable_inside_common_period"
            episodes.append(rec)
            continue
        if impulse_start < occupied_until_impulse_start:
            rec.exclusion_reason = "overlap_skip"
            episodes.append(rec)
            continue
        i_t = idx5(t)
        if i_t < 0 or i_t >= n5:
            rec.exclusion_reason = "not_qualifying_impulse"
            episodes.append(rec)
            continue
        ret_raw = signed_imp[i_t]
        if not math.isfinite(float(ret_raw)):
            rec.exclusion_reason = "not_qualifying_impulse"
            episodes.append(rec)
            continue
        ret = float(ret_raw)
        if ret == 0.0:
            rec.impulse_return = 0.0
            rec.exclusion_reason = "not_qualifying_impulse"
            episodes.append(rec)
            continue
        d = 1 if ret > 0.0 else -1
        abs_i = abs(ret)
        i_imp_start = idx5(impulse_start)
        i_imp_hist_lo = idx5(impulse_start - HIST_MS)
        mag_refs = _slice_or_empty(abs_imp, i_imp_hist_lo, i_imp_start)
        p_imp = midrank_percentile(abs_i, mag_refs)
        rec.impulse_return = ret
        rec.D = d
        rec.abs_impulse = abs_i
        rec.p_impulse = p_imp
        rec.qualifying_impulse = bool(p_imp is not None and p_imp >= IMPULSE_P_MIN)
        if not rec.qualifying_impulse:
            rec.exclusion_reason = "not_qualifying_impulse"
            episodes.append(rec)
            continue
        rec.occupies_slot = True
        occupied_until_impulse_start = impulse_start + EPISODE_MS

        i_state = i_t
        i_T = idx5(T)
        oi_start_raw = _at(oi5, i_state)
        oi_end_raw = _at(oi5, i_T)
        oi_start = oi_start_raw if math.isfinite(oi_start_raw) else None
        oi_end = oi_end_raw if math.isfinite(oi_end_raw) else None
        rec.oi_start = oi_start
        rec.oi_end = oi_end
        delta = None
        if oi_start is not None and oi_end is not None:
            delta = log_ratio(oi_end, oi_start)
        rec.delta_oi = delta
        p_oi = None
        if delta is not None:
            i_oi_hist_lo = idx5(t - HIST_MS)
            d_refs = _slice_or_empty(delta_oi, i_oi_hist_lo, i_state)
            p_oi = midrank_percentile(float(delta), d_refs)
        rec.p_oi = p_oi
        rec.oi_expansion = bool(p_oi is not None and p_oi > OI_P_STRICT)
        if rec.oi_start is None or rec.oi_end is None or rec.delta_oi is None or rec.p_oi is None:
            rec.exclusion_reason = "missing_or_invalid_oi"
            episodes.append(rec)
            continue

        close_T = _at(close5, i_T)
        close_t = _at(close5, i_t)
        state_ret = log_ratio(
            close_T if math.isfinite(close_T) else float("nan"),
            close_t if math.isfinite(close_t) else float("nan"),
        )
        rec.state_return = state_ret
        if state_ret is None or abs_i == 0.0 or not math.isfinite(abs_i):
            rec.exclusion_reason = "missing_state_return"
            episodes.append(rec)
            continue
        ratio = (d * state_ret) / abs_i
        rec.continuation_ratio = ratio
        if not math.isfinite(ratio):
            rec.weak_continuation = False
        else:
            rec.weak_continuation = bool(ratio <= CONTINUATION_MAX)
        rec.candidate = bool(
            rec.qualifying_impulse and rec.oi_expansion and rec.weak_continuation
        )

        vol_raw = _at(vol5, i_t)
        vol = vol_raw if math.isfinite(vol_raw) else None
        rec.pre_vol_60 = vol
        p_mag = midrank_percentile(abs_i, mag_refs)
        vol_refs = _slice_or_empty(vol5, i_imp_hist_lo, i_imp_start)
        p_vol = None if vol is None else midrank_percentile(vol, vol_refs)
        mag_state = tertile_state(p_mag)
        vol_state = tertile_state(p_vol)
        sid = None
        if mag_state is not None and vol_state is not None:
            sid = stratum_id(mag_state, vol_state)
        rec.impulse_mag_state = mag_state
        rec.trailing_vol_state = vol_state
        rec.stratum_id = sid
        if rec.stratum_id is None:
            rec.exclusion_reason = "stratum_unavailable"
            episodes.append(rec)
            continue

        i_out = idx5(outcome_end)
        close_out = _at(close5, i_out)
        outcome = log_ratio(
            close_out if math.isfinite(close_out) else float("nan"),
            close_T if math.isfinite(close_T) else float("nan"),
        )
        if outcome is None:
            rec.exclusion_reason = "missing_outcome"
            episodes.append(rec)
            continue
        rev = -int(d) * outcome
        if not math.isfinite(rev):
            rec.exclusion_reason = "missing_outcome"
            episodes.append(rec)
            continue
        rec.reversal_return = rev
        rec.confirmatory_eligible = True
        episodes.append(rec)
    return episodes


def episode_field_pairs(
    left: Sequence[EpisodeRecord], right: Sequence[EpisodeRecord]
) -> None:
    """Raise AssertionError on the first scientific-field mismatch."""
    if len(left) != len(right):
        raise AssertionError(f"episode count {len(left)} != {len(right)}")
    for i, (a, b) in enumerate(zip(left, right)):
        for name in EPISODE_FIELDS:
            va = getattr(a, name)
            vb = getattr(b, name)
            if va is None and vb is None:
                continue
            if isinstance(va, float) and isinstance(vb, float):
                if math.isnan(va) and math.isnan(vb):
                    continue
                if va == vb:
                    continue
                raise AssertionError(f"episode[{i}].{name} {va!r} != {vb!r}")
            if va != vb:
                raise AssertionError(f"episode[{i}].{name} {va!r} != {vb!r}")
