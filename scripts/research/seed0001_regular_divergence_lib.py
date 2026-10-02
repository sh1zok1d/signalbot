"""SEED-0001 regular bullish divergence with order-book support: PIT-safe detector.

Implements the frozen definitions of
`docs/research/SEED0001_REGULAR_DIVERGENCE_PREREG.md` / `.json`.

In-memory arrays only. This module never opens files, talks to the network or
reads Git. For an episode whose decision time is T (the close of bar i+3) it
reads nothing after T. It has no outcome fields: no future return, no +1R/-1R,
no +2R/-1R, no MFE/MAE and no post-decision price.

Frozen summary (prereg section in brackets):

- UTC 1h bars aggregated from complete 1m rows; a bar with fewer than 60
  minutes is incomplete and breaks the series into segments [S2];
- swing low at bar i: low_i below the 3 previous lows and not above the 3 next
  lows; confirmed, and decided, at the close of bar i+3 [S3];
- pronounced decline: max high of bars i-48..i minus low_i >= 3 ATR14(i) [S3];
- comparison pivot j: the most recent swing low with i-48 <= j <= i-5; the
  episode needs a lower low, low_i < low_j [S3];
- divergence families: RSI (14 AND 21 higher at i than at j), MACD line
  (EMA12 - EMA26 of close, higher at i), CVD (net taker delta over bars j+1..i
  above zero); divergence = at least 2 of 3 families [S4];
- book support: hourly mean of (bid - ask) / (bid + ask) notional within 5%;
  support if some hour among i+1..i+3 is above zero and at or above the
  trailing P80 of hours i-719..i (at least 480 present) [S5];
- arms A (support and divergence), B (support only), C (divergence only),
  D (neither) [S6];
- adjustment covariates at T: RV24, UTC hour of T, decline in ATR, net taker
  flow share over 24 bars, risk width in ATR [S7].
"""

from __future__ import annotations

import datetime as dt

import numpy as np

CARD_ID = "SEED0001_REGULAR_DIVERGENCE_BOOK_SUPPORT_V1"
DETECTOR_VERSION = "SEED0001_DETECTOR_V1"

MINUTE_MS = 60_000
BAR_MS = 3_600_000
WEEK_MS = 7 * 24 * BAR_MS
# 2023-01-02T00:00:00Z, a Monday: weekly inference clusters start on Mondays.
WEEK_ANCHOR_MS = 1_672_617_600_000

PIVOT_LEFT = 3
PIVOT_RIGHT = 3
DECLINE_LOOKBACK_BARS = 48
DECLINE_MIN_ATR = 3.0
COMPARISON_MIN_GAP = 5
COMPARISON_MAX_GAP = 48
RSI_PERIODS = (14, 21)
MACD_FAST = 12
MACD_SLOW = 26
ATR_PERIOD = 14
MIN_DIVERGENT_FAMILIES = 2
MIN_RISK_ATR = 0.25
RV_BARS = 24
FLOW_BARS = 24
WARMUP_BARS = 720

BOOK_BAND_PCT = 5
BOOK_MIN_SNAPSHOTS_PER_HOUR = 60
SUPPORT_HOURS_AFTER_LOW = (1, 2, 3)
SUPPORT_TRAILING_HOURS = 720
SUPPORT_MIN_PRESENT_HOURS = 480
SUPPORT_QUANTILE = 0.80

PRIMARY_CAP_HOURS = 48
SENSITIVITY_CAP_HOURS = 96
PROTECTED_START_MS = 1_735_689_600_000  # 2025-01-01T00:00:00Z

ARMS = ("A", "B", "C", "D")
FUNNEL_ORDER = (
    "SWING_LOW_IN_DECISION_WINDOW",
    "EXCLUDED_KLINE_WINDOW_INCOMPLETE",
    "NOT_PRONOUNCED_DECLINE",
    "NO_COMPARISON_PIVOT",
    "NOT_LOWER_LOW",
    "POPULATION",
    "EXCLUDED_DEGENERATE_RISK",
    "EXCLUDED_BOOK_WINDOW_MISSING",
    "EXCLUDED_BOOK_BASELINE_IMMATURE",
    "ELIGIBLE",
)
# Substrings that must never appear in an episode field name: the detector
# carries no outcome or post-decision information.
FORBIDDEN_FIELD_TOKENS = ("FUTURE", "OUTCOME", "HIT", "MFE", "MAE", "TARGET", "RETURN_AFTER", "POST_DECISION", "PNL")


class DetectorInputError(ValueError):
    pass


def iso_utc(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def half_year_epoch(ms: int) -> str:
    t = dt.datetime.fromtimestamp(ms / 1000, tz=dt.timezone.utc)
    return f"{t.year}H{1 if t.month <= 6 else 2}"


def week_block(ms: int) -> int:
    return (ms - WEEK_ANCHOR_MS) // WEEK_MS


# --------------------------------------------------------------------------- bars

def hourly_bars(open_time_ms, open_, high, low, close, volume, taker_buy) -> dict:
    """Aggregate 1m rows into UTC 1h bars [h, h + 1h).

    The rows must be strictly increasing and minute-aligned. Every hour between
    the first and last hour gets a bar. An hour with fewer than 60 minutes is
    incomplete: its fields are NaN and `complete` is False.
    """
    t = np.asarray(open_time_ms, dtype=np.int64)
    if t.size == 0:
        raise DetectorInputError("no 1m rows")
    if np.any(t % MINUTE_MS != 0):
        raise DetectorInputError("1m open times are not minute-aligned")
    if np.any(np.diff(t) <= 0):
        raise DetectorInputError("1m open times are not strictly increasing")
    cols = [np.asarray(c, dtype=np.float64) for c in (open_, high, low, close, volume, taker_buy)]
    if any(c.shape != t.shape for c in cols):
        raise DetectorInputError("column length mismatch")
    o, h, l, c, v, tb = cols
    hour = t // BAR_MS * BAR_MS
    starts = np.flatnonzero(np.r_[True, hour[1:] != hour[:-1]])
    counts = np.diff(np.r_[starts, t.size])
    hours = hour[starts]
    grid = np.arange(hours[0], hours[-1] + BAR_MS, BAR_MS, dtype=np.int64)
    pos = ((hours - grid[0]) // BAR_MS).astype(np.int64)
    out = {"open_time_ms": grid, "complete": np.zeros(grid.size, dtype=bool)}
    for name in ("open", "high", "low", "close", "volume", "taker_buy"):
        out[name] = np.full(grid.size, np.nan)
    full = counts == 60
    ends = np.r_[starts[1:], t.size] - 1
    agg = {
        "open": o[starts],
        "high": np.maximum.reduceat(h, starts),
        "low": np.minimum.reduceat(l, starts),
        "close": c[ends],
        "volume": np.add.reduceat(v, starts),
        "taker_buy": np.add.reduceat(tb, starts),
    }
    for name, values in agg.items():
        out[name][pos[full]] = values[full]
    out["complete"][pos[full]] = True
    return out


def segments(complete) -> list[tuple[int, int]]:
    """Maximal runs of complete bars as half-open index intervals."""
    complete = np.asarray(complete, dtype=bool)
    edges = np.diff(np.r_[0, complete.astype(np.int8), 0])
    return list(zip(np.flatnonzero(edges == 1).tolist(), np.flatnonzero(edges == -1).tolist()))


# --------------------------------------------------------------------- indicators

def ema(x, n: int) -> np.ndarray:
    """EMA with alpha = 2 / (n + 1), seeded with the first value."""
    x = np.asarray(x, dtype=np.float64)
    out = np.empty_like(x)
    alpha = 2.0 / (n + 1.0)
    acc = x[0]
    for k in range(x.size):
        acc = x[k] if k == 0 else acc + alpha * (x[k] - acc)
        out[k] = acc
    return out


def wilder_rma(x, n: int) -> np.ndarray:
    """Wilder smoothing seeded with the mean of the first n values; NaN before."""
    x = np.asarray(x, dtype=np.float64)
    out = np.full(x.size, np.nan)
    if x.size < n:
        return out
    acc = float(np.mean(x[:n]))
    out[n - 1] = acc
    for k in range(n, x.size):
        acc = (acc * (n - 1) + x[k]) / n
        out[k] = acc
    return out


def rsi(close, n: int) -> np.ndarray:
    """Wilder RSI on close; value at k uses closes 0..k. NaN until n deltas."""
    close = np.asarray(close, dtype=np.float64)
    out = np.full(close.size, np.nan)
    if close.size <= n:
        return out
    d = np.diff(close)
    gain = wilder_rma(np.maximum(d, 0.0), n)
    loss = wilder_rma(np.maximum(-d, 0.0), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        value = np.where(loss == 0.0, 100.0, 100.0 - 100.0 / (1.0 + gain / loss))
    out[1:] = np.where(np.isnan(gain), np.nan, value)
    return out


def macd_line(close) -> np.ndarray:
    return ema(close, MACD_FAST) - ema(close, MACD_SLOW)


def atr(high, low, close, n: int = ATR_PERIOD) -> np.ndarray:
    high, low, close = (np.asarray(a, dtype=np.float64) for a in (high, low, close))
    prev = np.r_[np.nan, close[:-1]]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    tr[0] = high[0] - low[0]
    return wilder_rma(tr, n)


def cvd(volume, taker_buy) -> np.ndarray:
    """Cumulative taker delta (buy minus sell volume) in base units."""
    return np.cumsum(2.0 * np.asarray(taker_buy, dtype=np.float64) - np.asarray(volume, dtype=np.float64))


def swing_lows(low) -> np.ndarray:
    """Swing low at k: low_k below lows k-3..k-1 and not above lows k+1..k+3.

    The flag at k uses bars up to k+3 only; it is False where those bars are
    absent.
    """
    low = np.asarray(low, dtype=np.float64)
    n = low.size
    flag = np.zeros(n, dtype=bool)
    for k in range(PIVOT_LEFT, n - PIVOT_RIGHT):
        left = low[k - PIVOT_LEFT:k]
        right = low[k + 1:k + 1 + PIVOT_RIGHT]
        flag[k] = bool(low[k] < left.min() and low[k] <= right.min())
    return flag


def indicators(bars: dict) -> dict:
    """Causal indicators computed independently inside every complete segment."""
    n = bars["open_time_ms"].size
    out = {name: np.full(n, np.nan) for name in ("rsi14", "rsi21", "macd", "atr", "cvd")}
    out["segment_start"] = np.full(n, -1, dtype=np.int64)
    out["segment_end"] = np.full(n, -1, dtype=np.int64)
    for a, b in segments(bars["complete"]):
        sl = slice(a, b)
        c = bars["close"][sl]
        out["rsi14"][sl] = rsi(c, RSI_PERIODS[0])
        out["rsi21"][sl] = rsi(c, RSI_PERIODS[1])
        out["macd"][sl] = macd_line(c)
        out["atr"][sl] = atr(bars["high"][sl], bars["low"][sl], c)
        out["cvd"][sl] = cvd(bars["volume"][sl], bars["taker_buy"][sl])
        out["segment_start"][sl] = a
        out["segment_end"][sl] = b
    return out


# ------------------------------------------------------------------- order book

def book_hourly_imbalance(snapshot_ms, bid_notional, ask_notional, hour_grid_ms) -> dict:
    """Hourly mean of (bid - ask) / (bid + ask) cumulative notional within 5%.

    A snapshot belongs to hour h when h <= t < h + 1h, so the value of hour h is
    available at h + 1h. Snapshots with a non-positive side are dropped. An hour
    with fewer than BOOK_MIN_SNAPSHOTS_PER_HOUR valid snapshots is NaN.
    """
    t = np.asarray(snapshot_ms, dtype=np.int64)
    bid = np.asarray(bid_notional, dtype=np.float64)
    ask = np.asarray(ask_notional, dtype=np.float64)
    grid = np.asarray(hour_grid_ms, dtype=np.int64)
    if t.size and np.any(np.diff(t) < 0):
        raise DetectorInputError("book snapshots are not time-ordered")
    ok = (bid > 0) & (ask > 0) & np.isfinite(bid) & np.isfinite(ask)
    t, bid, ask = t[ok], bid[ok], ask[ok]
    imb = (bid - ask) / (bid + ask)
    idx = (t - grid[0]) // BAR_MS
    inside = (idx >= 0) & (idx < grid.size)
    idx, imb = idx[inside], imb[inside]
    count = np.bincount(idx, minlength=grid.size)
    total = np.bincount(idx, weights=imb, minlength=grid.size)
    value = np.full(grid.size, np.nan)
    enough = count >= BOOK_MIN_SNAPSHOTS_PER_HOUR
    value[enough] = total[enough] / count[enough]
    return {"open_time_ms": grid, "imbalance": value, "snapshots": count}


# --------------------------------------------------------------------- detector

def _decision_close_index(i: int) -> int:
    return i + PIVOT_RIGHT


def detect(bars: dict, book: dict, *, decision_start_ms: int, decision_last_ms: int) -> dict:
    """Detect SEED-0001 episodes with decision time T in [start, last].

    `book["open_time_ms"]` must equal `bars["open_time_ms"]`. Returns the funnel
    counts and one record per eligible episode (pre-decision fields only).
    """
    grid = np.asarray(bars["open_time_ms"], dtype=np.int64)
    if not np.array_equal(grid, np.asarray(book["open_time_ms"], dtype=np.int64)):
        raise DetectorInputError("book hour grid differs from the bar grid")
    if decision_last_ms + SENSITIVITY_CAP_HOURS * BAR_MS > PROTECTED_START_MS:
        raise DetectorInputError("an outcome window would reach the protected 2025 surface")
    ind = indicators(bars)
    pivots = swing_lows(np.where(bars["complete"], bars["low"], np.inf))
    low, high, close = bars["low"], bars["high"], bars["close"]
    vol, tb = bars["volume"], bars["taker_buy"]
    imb = np.asarray(book["imbalance"], dtype=np.float64)
    funnel = {k: 0 for k in FUNNEL_ORDER}
    episodes = []
    n = grid.size
    for i in np.flatnonzero(pivots).tolist():
        d = _decision_close_index(i)
        if d >= n:
            continue
        t_ms = int(grid[d]) + BAR_MS
        if t_ms < decision_start_ms or t_ms > decision_last_ms:
            continue
        funnel["SWING_LOW_IN_DECISION_WINDOW"] += 1
        a = int(ind["segment_start"][i])
        if a < 0 or i - a < WARMUP_BARS or d >= int(ind["segment_end"][i]):
            funnel["EXCLUDED_KLINE_WINDOW_INCOMPLETE"] += 1
            continue
        atr_i = float(ind["atr"][i])
        peak = float(np.max(high[i - DECLINE_LOOKBACK_BARS:i + 1]))
        decline_atr = (peak - float(low[i])) / atr_i
        if not decline_atr >= DECLINE_MIN_ATR:
            funnel["NOT_PRONOUNCED_DECLINE"] += 1
            continue
        window = np.flatnonzero(pivots[i - COMPARISON_MAX_GAP:i - COMPARISON_MIN_GAP + 1])
        if window.size == 0:
            funnel["NO_COMPARISON_PIVOT"] += 1
            continue
        j = i - COMPARISON_MAX_GAP + int(window[-1])
        if not float(low[i]) < float(low[j]):
            funnel["NOT_LOWER_LOW"] += 1
            continue
        funnel["POPULATION"] += 1

        entry_ref = float(close[d])
        risk = entry_ref - float(low[i])
        risk_atr = risk / atr_i
        if not risk_atr >= MIN_RISK_ATR:
            funnel["EXCLUDED_DEGENERATE_RISK"] += 1
            continue
        support_hours = imb[[i + k for k in SUPPORT_HOURS_AFTER_LOW]]
        if np.any(np.isnan(support_hours)):
            funnel["EXCLUDED_BOOK_WINDOW_MISSING"] += 1
            continue
        lo = i - SUPPORT_TRAILING_HOURS + 1
        trailing = imb[max(lo, 0):i + 1]
        trailing = trailing[~np.isnan(trailing)]
        if lo < 0 or trailing.size < SUPPORT_MIN_PRESENT_HOURS:
            funnel["EXCLUDED_BOOK_BASELINE_IMMATURE"] += 1
            continue
        q80 = float(np.quantile(trailing, SUPPORT_QUANTILE))
        support = bool(np.any((support_hours > 0.0) & (support_hours >= q80)))

        rsi14_div = bool(ind["rsi14"][i] > ind["rsi14"][j])
        rsi21_div = bool(ind["rsi21"][i] > ind["rsi21"][j])
        rsi_family = rsi14_div and rsi21_div
        macd_family = bool(ind["macd"][i] > ind["macd"][j])
        cvd_family = bool(ind["cvd"][i] - ind["cvd"][j] > 0.0)
        div_count = int(rsi_family) + int(macd_family) + int(cvd_family)
        divergence = div_count >= MIN_DIVERGENT_FAMILIES
        arm = "A" if support and divergence else "B" if support else "C" if divergence else "D"

        r = np.diff(np.log(close[d - RV_BARS:d + 1]))
        rv24 = float(np.std(r, ddof=1))
        fv = vol[d - FLOW_BARS + 1:d + 1]
        ftb = tb[d - FLOW_BARS + 1:d + 1]
        netflow = float(np.sum(2.0 * ftb - fv) / np.sum(fv))
        funnel["ELIGIBLE"] += 1
        episodes.append({
            "DECISION_TIME_MS": t_ms,
            "DECISION_TIME_UTC": iso_utc(t_ms),
            "DECISION_DATE_UTC": iso_utc(t_ms)[:10],
            "EPOCH": half_year_epoch(t_ms),
            "WEEK_BLOCK": int(week_block(t_ms)),
            "PIVOT_BAR_OPEN_UTC": iso_utc(int(grid[i])),
            "COMPARISON_PIVOT_OPEN_UTC": iso_utc(int(grid[j])),
            "COMPARISON_GAP_BARS": i - j,
            "MAX_INPUT_BAR_CLOSE_MS": int(grid[d]) + BAR_MS,
            "STOP_PRICE": float(low[i]),
            "ENTRY_REF_PRICE": entry_ref,
            "RISK_FRACTION": risk / entry_ref,
            "ATR14": atr_i,
            "DECLINE_ATR": decline_atr,
            "RISK_ATR": risk_atr,
            "RV24": rv24,
            "TOD_HOUR_UTC": int((t_ms // BAR_MS) % 24),
            "NETFLOW24": netflow,
            "RSI14_DIV": rsi14_div,
            "RSI21_DIV": rsi21_div,
            "RSI_FAMILY": rsi_family,
            "MACD_FAMILY": macd_family,
            "CVD_FAMILY": cvd_family,
            "DIV_COUNT": div_count,
            "DIVERGENCE": divergence,
            "SUPPORT_MAX_IMBALANCE": float(np.max(support_hours)),
            "SUPPORT_TRAILING_Q80": q80,
            "SUPPORT_TRAILING_PRESENT": int(trailing.size),
            "SUPPORT": support,
            "ARM": arm,
        })
    return {"FUNNEL": funnel, "EPISODES": episodes}


def overlap_chains(decision_ms, window_hours: int = PRIMARY_CAP_HOURS) -> np.ndarray:
    """Single-linkage chains of episodes whose outcome windows overlap.

    Uses decision timestamps only. Episodes sorted by time start a new chain
    when the gap to the previous episode is at least the window length.
    """
    t = np.asarray(decision_ms, dtype=np.int64)
    order = np.argsort(t, kind="stable")
    gaps = np.diff(t[order]) >= window_hours * BAR_MS
    chain_sorted = np.r_[0, np.cumsum(gaps)]
    out = np.empty(t.size, dtype=np.int64)
    out[order] = chain_sorted
    return out


def assert_outcome_blind(episodes) -> None:
    for ep in episodes:
        for key in ep:
            if any(tok in key.upper() for tok in FORBIDDEN_FIELD_TOKENS):
                raise AssertionError(f"forbidden post-decision field {key}")
        if ep["MAX_INPUT_BAR_CLOSE_MS"] != ep["DECISION_TIME_MS"]:
            raise AssertionError("episode read a bar after its decision time")
        if ep["DECISION_TIME_MS"] + SENSITIVITY_CAP_HOURS * BAR_MS > PROTECTED_START_MS:
            raise AssertionError("episode outcome window reaches the protected surface")


def episode_digest_rows(episodes, symbol: str) -> list[str]:
    """Canonical one-line-per-episode text used for the frozen episode digest."""
    rows = []
    for ep in sorted(episodes, key=lambda e: e["DECISION_TIME_MS"]):
        rows.append("|".join([
            symbol, ep["DECISION_TIME_UTC"], ep["PIVOT_BAR_OPEN_UTC"], ep["COMPARISON_PIVOT_OPEN_UTC"], ep["ARM"],
            str(ep["DIV_COUNT"]), "1" if ep["SUPPORT"] else "0",
            *(repr(round(float(ep[k]), 12)) for k in ("DECLINE_ATR", "RISK_ATR", "RV24", "NETFLOW24")),
            str(ep["TOD_HOUR_UTC"]),
        ]))
    return rows
