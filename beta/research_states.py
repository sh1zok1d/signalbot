"""Live states of closed research units, computed exactly as their frozen research code did.

Pure numpy; no I/O. Each function names the frozen definition it reproduces. The parity tests
(`tests/beta/test_research_evidence.py`) run these functions and the research implementations on
the same inputs and require identical results, so a live state can only mean what the research
state meant. Quantile states use the frozen cut points in `config/beta_research_cuts.json`
(`scripts/research/evidence/freeze_live_cuts.py`), never quantiles recomputed on live data.

Conventions: `b` is a contiguous 5m grid (beta.hist_series.Bars); bar j closes at
T = t0 + (j + 1) * 5m (the research decision time). Arrays aligned to the grid hold, at index j,
the value known at bar j's close. A missing input yields None, never a filled value.
"""
from __future__ import annotations

import math
from typing import Mapping, Optional, Sequence

import numpy as np

from .hist_series import BAR_MS, Bars

HOUR_MS = 3_600_000
DAY_MS = 86_400_000
# DH1 constants (scripts/research/dh1/constants.py)
SCALE_BARS = 288
MIN_PRESENT = 0.9
HOLD_BARS = 48
LAG_BARS = 48
MOVE_BARS = 3
MOVE_RATIO_MIN = 2.0
MOVE_REFRACTORY_BARS = 12
CORRIDOR_Z = 1.2816
BARRIER_FRACTION = 0.5
APPROACH_BARS = 12
STALE_BARS = 288
CONFLUENCE_TOL = 0.0015
# DH3 constants (scripts/research/dh3/constants.py)
OI_LOOKBACK_4H = 48
OI_LOOKBACK_1H = 12
CROWD_Z_HOURS = 24 * 30
CROWD_Z_MIN = 600
THIN_LOOKBACK_H = 24 * 7
THIN_MIN = 120
RECOVERY_LAG_BARS = 6
UPVOL_WINDOW_H = 24
RETEST_RETREAT_X = 1.0
SESSION_WINDOW_BARS = 288
DEPTH_MAX_AGE_MS = 600_000
# H-series 15-minute grid (scripts/research/h0[345]_*_lib.py)
GRID15_MS = 900_000
REF_STEPS_15 = 30 * 24 * 4                   # 2880
H03_WINDOWS = (15, 30, 60)
H03_Q_MIN = 0.90
H05_WINDOWS = (15, 30, 60)
H05_Q_MIN = 0.80
H04_LOOKBACKS = (240, 480, 960)
H04_PULLBACK_MIN = 60
H04_TREND_Q = 0.80
H04_DEPTH_MIN, H04_DEPTH_MAX = 0.10, 1.0
H02_LOOKBACKS = (60, 120, 240)
# MARKET-01/02 (MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.md §3-6)
M_IMPULSE_BARS = 6
M_REF_BARS = 30 * 288
M_IMPULSE_Q = 0.90
M_OI_Q = 0.75
M_CONFIRM_RATIO = 0.25
# D2 RULE_1 (D2_BITMEX_REPLICATION_PREREG.md "Frozen rule")
D2_TRAILING = 250
D2_RETURNS = 288


# ---- shared ---------------------------------------------------------------------------
def rolling_sigma(close: np.ndarray, window: int = SCALE_BARS, min_frac: float = MIN_PRESENT) -> np.ndarray:
    """DH1 events.rolling_sigma: std of the 5m log returns r[e-window+1 .. e]; NaN when fewer than
    min_frac of them are finite. Known at the close of bar e."""
    n = close.shape[0]
    r = np.full(n, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        r[1:] = np.log(close[1:] / close[:-1])
    ok = np.isfinite(r)
    x = np.where(ok, r, 0.0)
    c0 = np.concatenate([[0], np.cumsum(ok)])
    c1 = np.concatenate([[0.0], np.cumsum(x)])
    c2 = np.concatenate([[0.0], np.cumsum(x * x)])
    out = np.full(n, np.nan)
    e = np.arange(window - 1, n)
    if e.size == 0:
        return out
    cnt = c0[e + 1] - c0[e + 1 - window]
    s1 = c1[e + 1] - c1[e + 1 - window]
    s2 = c2[e + 1] - c2[e + 1 - window]
    with np.errstate(invalid="ignore", divide="ignore"):
        var = (s2 - s1 * s1 / cnt) / (cnt - 1)
    good = cnt >= min_frac * window
    out[e[good]] = np.sqrt(np.maximum(var[good], 0.0))
    return out


def barrier_x(sigma_j: float) -> float:
    """DH1 X = half of the 4h corridor half-width."""
    return float(BARRIER_FRACTION * CORRIDOR_Z * sigma_j * math.sqrt(HOLD_BARS))


def window_log_range(b: Bars, a: int, z: int) -> Optional[float]:
    """DH3 features._window_range: log((max high - min low) / close[z]) over bars a..z."""
    if a < 0 or z >= b.n:
        return None
    hi, lo = b.high[a:z + 1], b.low[a:z + 1]
    ok = np.isfinite(hi) & np.isfinite(lo)
    if ok.mean() < MIN_PRESENT or not math.isfinite(b.close[z]):
        return None
    if hi[ok].max() <= lo[ok].min():
        return None
    return float(math.log((hi[ok].max() - lo[ok].min()) / b.close[z]))


def logret(close: np.ndarray, j: int, k: int) -> Optional[float]:
    if j - k < 0 or j >= close.shape[0]:
        return None
    a, z = close[j - k], close[j]
    return float(math.log(z / a)) if (math.isfinite(a) and math.isfinite(z) and a > 0) else None


def decision_ms(b: Bars, j: int) -> int:
    return b.t0 + (j + 1) * BAR_MS


def index_closing_at(b: Bars, t_ms: int) -> Optional[int]:
    j = (int(t_ms) - b.t0) // BAR_MS - 1
    return int(j) if 0 <= j < b.n and (int(t_ms) - b.t0) % BAR_MS == 0 else None


def last_hour_index(b: Bars, now_ms: int) -> Optional[int]:
    """The bar closing at the latest full hour <= now, if that bar is present."""
    t = int(now_ms) - int(now_ms) % HOUR_MS
    j = index_closing_at(b, t)
    return j if j is not None and math.isfinite(b.close[j]) else None


def midrank(ref: np.ndarray, x: float) -> Optional[float]:
    """(count(ref < x) + 0.5 count(ref == x)) / N_ref over the finite reference values."""
    ref = ref[np.isfinite(ref)]
    if ref.size == 0 or not math.isfinite(x):
        return None
    return float((np.sum(ref < x) + 0.5 * np.sum(ref == x)) / ref.size)


def grid_values(times_ms: np.ndarray, values: np.ndarray, t0: int, n: int, step_ms: int = BAR_MS) -> np.ndarray:
    out = np.full(n, np.nan)
    times_ms = np.asarray(times_ms, dtype=np.int64)
    idx = (times_ms - t0) // step_ms
    ok = ((times_ms - t0) % step_ms == 0) & (idx >= 0) & (idx < n)
    out[idx[ok]] = np.asarray(values, dtype=float)[ok]
    return out


# ---- card DH3-P (OI metrics) ---------------------------------------------------------------
def oi_states(b: Bars, oi: np.ndarray, j: int, cuts: Mapping[str, float]) -> dict:
    """DH3 features.card_p at decision bar j. `oi[j]` is the metrics snapshot labelled with bar j's
    open (usable at its close)."""
    out = {"quiet": None, "doi4": None, "doi1": None, "P1": None, "P2": None}
    quiet = window_log_range(b, j - LAG_BARS + 1, j)
    v, v4, v1 = oi[j], (oi[j - OI_LOOKBACK_4H] if j >= OI_LOOKBACK_4H else np.nan), \
        (oi[j - OI_LOOKBACK_1H] if j >= OI_LOOKBACK_1H else np.nan)
    doi4 = float(math.log(v / v4)) if (v > 0 and v4 > 0) else None
    doi1 = float(math.log(v / v1)) if (v > 0 and v1 > 0) else None
    out.update(quiet=quiet, doi4=doi4, doi1=doi1)
    if doi4 is not None and quiet is not None and quiet <= cuts["P1_QUIET_RANGE_MAX"]:
        out["P1"] = bool(doi4 >= cuts["P1_DOI4_MIN"])
    if doi1 is not None:
        out["P2"] = bool(doi1 <= cuts["P2_DOI1_MAX"])
    return out


def crowd_z(b: Bars, ls: np.ndarray, j: int) -> Optional[float]:
    """DH3 P3: z of the ratio at hour T against the previous 720 hourly values (>= 600 finite;
    population std, as numpy's default)."""
    if (decision_ms(b, j)) % HOUR_MS:
        return None
    hours = [j - 12 * k for k in range(CROWD_Z_HOURS, 0, -1)]
    hist = np.array([ls[x] for x in hours if x >= 0])
    hist = hist[np.isfinite(hist)]
    if hist.size < CROWD_Z_MIN or not math.isfinite(ls[j]) or hist.std() <= 0:
        return None
    return float((ls[j] - hist.mean()) / hist.std())


def crowd_state(z: Optional[float], cuts: Mapping[str, float]) -> Optional[str]:
    if z is None:
        return None
    if z >= cuts["P3_CROWD_Z_LONG_MIN"]:
        return "CROWD_LONG"
    if z <= cuts["P3_CROWD_Z_SHORT_MAX"]:
        return "CROWD_SHORT"
    return "NEITHER"


# ---- card DH3-L (book depth ±1 %) ----------------------------------------------------------
def book_on_grid(snap_ms: Sequence[int], bid1: Sequence[float], ask1: Sequence[float], t0: int, n: int) -> dict:
    """DH3 data.book_on_grid: the last snapshot at or before each bar's close, at most 10 minutes old."""
    order = np.argsort(np.asarray(snap_ms, dtype=np.int64), kind="mergesort")
    t = np.asarray(snap_ms, dtype=np.int64)[order]
    bid = np.asarray(bid1, dtype=float)[order]
    ask = np.asarray(ask1, dtype=float)[order]
    close_t = t0 + (np.arange(n, dtype=np.int64) + 1) * BAR_MS
    pos = np.searchsorted(t, close_t, side="right") - 1
    out = {"bid1": np.full(n, np.nan), "ask1": np.full(n, np.nan)}
    ok = pos >= 0
    ok[ok] &= (close_t[ok] - t[pos[ok]]) <= DEPTH_MAX_AGE_MS
    out["bid1"][ok] = bid[pos[ok]]
    out["ask1"][ok] = ask[pos[ok]]
    return out


def depth_states(b: Bars, book: Mapping[str, np.ndarray], j: int, cuts: Mapping[str, float]) -> dict:
    """DH3 L1 (thin book vs its 7-day median of hourly values) and L2 (bid/ask asymmetry) at hour j."""
    out = {"depth_ratio": None, "asym": None, "L1": None, "L2": None}
    depth = book["bid1"] + book["ask1"]
    hours = [j - 12 * k for k in range(THIN_LOOKBACK_H, 0, -1) if j - 12 * k >= 0]
    hist = np.array([depth[x] for x in hours])
    hist = hist[np.isfinite(hist)]
    if hist.size >= THIN_MIN and math.isfinite(depth[j]):
        out["depth_ratio"] = float(depth[j] / np.median(hist))
        out["L1"] = bool(out["depth_ratio"] <= cuts["L1_DEPTH_RATIO_MAX"])
    bid, ask = book["bid1"][j], book["ask1"][j]
    if math.isfinite(bid) and math.isfinite(ask) and bid > 0 and ask > 0:
        out["asym"] = float(math.log(bid / ask))
        if out["asym"] >= cuts["L2_ASYM_BID_HEAVY_MIN"]:
            out["L2"] = "BID_HEAVY"
        elif out["asym"] <= cuts["L2_ASYM_ASK_HEAVY_MAX"]:
            out["L2"] = "ASK_HEAVY"
        else:
            out["L2"] = "NEITHER"
    return out


def sharp_moves(b: Bars, sigma: np.ndarray, *, first: int = 0) -> list:
    """DH2 events.move_events detection (DH1 rule): |15m log move| >= 2 x the 1h scale known
    before the move, one per hour at most. [(i, direction, ratio)] with i the move's last bar."""
    c = b.close
    out = []
    i = max(MOVE_BARS + SCALE_BARS + 1, first)
    last_event = -10 ** 9
    while i < b.n:
        if i - last_event <= MOVE_REFRACTORY_BARS:
            i += 1
            continue
        c0, c1, sg = c[i - MOVE_BARS], c[i], sigma[i - MOVE_BARS]
        if not (math.isfinite(c0) and math.isfinite(c1) and math.isfinite(sg)) or sg <= 0 \
                or not np.isfinite(c[i - MOVE_BARS:i + 1]).all():
            i += 1
            continue
        move = math.log(c1 / c0)
        ratio = abs(move) / (sg * math.sqrt(12))
        if ratio < MOVE_RATIO_MIN or move == 0:
            i += 1
            continue
        last_event = i
        out.append((int(i), 1 if move > 0 else -1, float(ratio)))
        i += 1
    return out


def book_recovery(book: Mapping[str, np.ndarray], i: int, cuts: Mapping[str, float]) -> Optional[dict]:
    """DH3 L3: depth at move end + 30 min over depth 15 min before the move end."""
    depth = book["bid1"] + book["ask1"]
    j2 = i + RECOVERY_LAG_BARS
    if i - MOVE_BARS < 0 or j2 >= depth.shape[0]:
        return None
    before, after = depth[i - MOVE_BARS], depth[j2]
    if not (math.isfinite(before) and math.isfinite(after)) or before <= 0:
        return None
    rec = float(after / before)
    return {"recovery": rec, "L3": bool(rec <= cuts["L3_RECOVERY_MAX"]), "j": int(j2)}


# ---- card DH3-O (DVOL) ---------------------------------------------------------------------
def dvol_states(b: Bars, dvol_at: Mapping[int, float], sigma: np.ndarray, j: int,
                cuts: Mapping[str, float]) -> Optional[dict]:
    """DH3 features.card_o at hour T (bar j): the candle starting at T - 1h is the one closed by T."""
    T = decision_ms(b, j)
    if T % HOUR_MS:
        return None
    v1, v2 = dvol_at.get(T - HOUR_MS), dvol_at.get(T - 2 * HOUR_MS)
    if v1 is None or v2 is None or v1 <= 0 or v2 <= 0:
        return None
    out = {"dvol": float(v1), "dvol_jump": float(math.log(v1 / v2)), "implied_realized": None, "corr": None}
    implied = v1 / 100.0 * math.sqrt(4 / 8760)
    realized = sigma[j] * math.sqrt(HOLD_BARS) if math.isfinite(sigma[j]) else float("nan")
    if math.isfinite(realized) and realized > 0:
        out["implied_realized"] = float(math.log(implied / realized))
    series = [dvol_at.get(T - (k + 1) * HOUR_MS) for k in range(UPVOL_WINDOW_H + 1)]
    prices = [b.close[j - 12 * k] if j - 12 * k >= 0 else np.nan for k in range(UPVOL_WINDOW_H + 1)]
    if all(v is not None and v > 0 for v in series) and np.isfinite(prices).all():
        dvs = np.diff(np.log(np.array(series[::-1])))
        dps = np.diff(np.log(np.array(prices[::-1])))
        if dvs.std() > 0 and dps.std() > 0:
            out["corr"] = float(np.corrcoef(dvs, dps)[0, 1])
    out["O1"] = None if out["implied_realized"] is None else bool(out["implied_realized"] >= cuts["O1_IMPLIED_REALIZED_MIN"])
    out["O2"] = bool(out["dvol_jump"] >= cuts["O2_DVOL_JUMP_MIN"])
    out["O3"] = None if out["corr"] is None else bool(out["corr"] > 0)
    return out


# ---- card DH3-S (stress hours) -------------------------------------------------------------
def stress_states(row: Mapping, cuts: Mapping[str, float]) -> Optional[dict]:
    """DH3 features.card_s for one stored stress hour (status OK)."""
    if row.get("status") != "OK" or float(row["perp_log_range"]) < cuts["S_STRESS_HOUR_LOG_RANGE_MIN"]:
        return None
    thr = max(float(cuts["S3_LARGE_PRINTS_Q67"]), 0.0)
    lead = row.get("lead_score")
    n_large = row.get("n_large_perp")
    return {"lead_score": lead, "n_large_perp": n_large,
            "S1": None if lead is None else ("SPOT_LED" if lead < 0 else "PERP_LED"),
            "S3": None if n_large is None else bool(n_large > thr)}


# ---- levels (DH1 / DH2 / DH3-V) ------------------------------------------------------------
def first_touch(b: Bars, a: int, z: int, level: float, side: int) -> Optional[int]:
    """beta.levels._first_touch over bars a..z (inclusive)."""
    a, z = max(a, 0), min(z, b.n - 1)
    if a > z:
        return None
    seg = b.high[a:z + 1] >= level if side > 0 else b.low[a:z + 1] <= level
    seg = np.nan_to_num(seg, nan=0).astype(bool)
    if not seg.any():
        return None
    return a + int(np.argmax(seg))


def stale_level(b: Bars, j: int, level: float) -> Optional[bool]:
    """DH1 events.stale: the level was not traded during the 24h before bar j."""
    a = j - STALE_BARS
    if a < 0:
        return None
    hi, lo = b.high[a:j], b.low[a:j]
    ok = np.isfinite(hi) & np.isfinite(lo)
    if ok.mean() < MIN_PRESENT:
        return None
    return not bool(((lo[ok] <= level) & (hi[ok] >= level)).any())


def confluent(level_kinds_prices: Sequence[tuple], own_kind: str, level: float) -> bool:
    """DH1 events.confluent: another product level (not a liquidation cluster, not the own kind)
    within ±0.15 % of the touched level."""
    return any(k != own_kind and not k.startswith("LIQ") and abs(p / level - 1) <= CONFLUENCE_TOL
               for k, p in level_kinds_prices)


def retest_state(b: Bars, sigma: np.ndarray, level: float, side: int, day_first: int, day_last: int) -> dict:
    """DH3 features.retest_events for one PDH (side +1) or PDL (-1) in the current UTC day:
    the first touch, the retreat of at least X beyond it, and the second touch (the retest)."""
    out = {"first": None, "retreat": None, "retest": None, "x": None}
    j1 = first_touch(b, day_first, day_last, level, side)
    if j1 is None or not math.isfinite(sigma[j1]):
        return out
    out["first"] = int(j1)
    x = RETEST_RETREAT_X * barrier_x(sigma[j1])
    out["x"] = x
    k = first_touch(b, j1 + 1, day_last, level * (1 - side * x), -side)
    if k is None:
        return out
    out["retreat"] = int(k)
    j2 = first_touch(b, k + 1, day_last, level, side)
    out["retest"] = None if j2 is None else int(j2)
    return out


def spot_flow(spot: Mapping[str, np.ndarray], a: int, z: int, side: int) -> Optional[float]:
    """DH1 events.flow_terms SPOT_NET over bars a..z: side * (2 * taker buy quote - quote)."""
    if a < 0:
        return None
    sq, stb = spot["quote"][a:z + 1], spot["taker_buy_quote"][a:z + 1]
    if np.isfinite(sq).mean() < MIN_PRESENT or np.isfinite(stb).mean() < MIN_PRESENT:
        return None
    return float(side * (2.0 * np.nansum(stb) - np.nansum(sq)))


def window_sum(x: np.ndarray, a: int, z: int) -> Optional[float]:
    if a < 0:
        return None
    seg = x[a:z + 1]
    ok = np.isfinite(seg)
    if ok.mean() < MIN_PRESENT:
        return None
    return float(seg[ok].sum())


def spot_share_high(b: Bars, spot: Mapping[str, np.ndarray], i: int) -> Optional[bool]:
    """DH2 events.move_events SPOT_SHARE_HIGH_MOVE for the move ending at bar i."""
    a, z = i - MOVE_BARS + 1, i
    sq, pq = window_sum(spot["quote"], a, z), window_sum(b.quote, a, z)
    sq_base = window_sum(spot["quote"], a - SCALE_BARS, a - 1)
    pq_base = window_sum(b.quote, a - SCALE_BARS, a - 1)
    if None in (sq, pq, sq_base, pq_base) or sq + pq <= 0 or sq_base + pq_base <= 0:
        return None
    return bool(sq / (sq + pq) > sq_base / (sq_base + pq_base))


# ---- H-series (15-minute grid) and MARKET-01/02 ----------------------------------------------
def grid15_closes(b: Bars) -> tuple:
    """(T_ms, close) at every UTC 15-minute boundary T covered by the 5m grid: close(T) is the close
    of the 5m bar ending at T (= the last 1m close before T)."""
    t_close = b.t0 + (np.arange(b.n, dtype=np.int64) + 1) * BAR_MS
    keep = t_close % GRID15_MS == 0
    return t_close[keep], b.close[keep]


def h03_state(t15: np.ndarray, c15: np.ndarray) -> Optional[dict]:
    """H03 at the last 15m boundary: for each W, P_W = midrank of |ln close(T)/close(T-W)| among the
    previous 2880 grid values (full trailing window required); the state holds when P_W >= 0.90."""
    n = c15.shape[0]
    if n < REF_STEPS_15 + 5:
        return None
    best = None
    for w in H03_WINDOWS:
        step = w // 15
        r = np.full(n, np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            r[step:] = np.log(c15[step:] / c15[:-step])
        x = r[-1]
        if not math.isfinite(x) or x == 0:
            continue
        p = midrank(np.abs(r[-1 - REF_STEPS_15:-1]), abs(x))
        if p is not None and p >= H03_Q_MIN and (best is None or p > best["pctl"]):
            best = {"window_min": w, "pctl": p, "ret": float(x)}
    return {"T_ms": int(t15[-1]), "state": best is not None, "best": best}


def h05_state(bucket_ms: np.ndarray, buy: np.ndarray, total: np.ndarray) -> Optional[dict]:
    """H05 at the last complete 15m bucket boundary: TAKER_IMBALANCE_W = (BUY - SELL) / TOTAL over
    [T-W, T) from base volumes; P = midrank of |imbalance| among the previous 2880 grid values;
    the state holds when P >= 0.80 for some W."""
    n = bucket_ms.shape[0]
    if n < REF_STEPS_15 + 4:
        return None
    best = None
    for w in H05_WINDOWS:
        k = w // 15
        bw = np.convolve(buy, np.ones(k), mode="full")[:n]
        tw = np.convolve(total, np.ones(k), mode="full")[:n]
        bw[:k - 1] = np.nan
        tw[:k - 1] = np.nan
        with np.errstate(divide="ignore", invalid="ignore"):
            imb = np.where(np.isfinite(tw) & (tw != 0), (2 * bw - tw) / tw, np.nan)
        x = imb[-1]
        if not math.isfinite(x) or x == 0:
            continue
        p = midrank(np.abs(imb[-1 - REF_STEPS_15:-1]), abs(x))
        if p is not None and p >= H05_Q_MIN and (best is None or p > best["pctl"]):
            best = {"window_min": w, "pctl": p, "imbalance": float(x)}
    return {"T_ms": int(bucket_ms[-1]) + GRID15_MS, "state": best is not None, "best": best}


def h04_state(t15: np.ndarray, c15: np.ndarray) -> Optional[dict]:
    """H04 at the last 15m boundary: an established trend over [T-60m-L, T-60m) (|trend| percentile
    >= 0.80 among the previous 2880 grid values) followed by a counter-trend 60m pullback with
    depth in [0.10, 1.0) of the trend leg."""
    n = c15.shape[0]
    p_steps = H04_PULLBACK_MIN // 15
    best = None
    for lmin in H04_LOOKBACKS:
        ls = lmin // 15
        if n < REF_STEPS_15 + ls + p_steps + 1:
            continue
        tr = np.full(n, np.nan)
        with np.errstate(divide="ignore", invalid="ignore"):
            tr[p_steps + ls:] = np.log(c15[ls:n - p_steps] / c15[:n - p_steps - ls])
        x = tr[-1]
        if not math.isfinite(x) or x == 0:
            continue
        pctl = midrank(np.abs(tr[-1 - REF_STEPS_15:-1]), abs(x))
        if pctl is None or pctl < H04_TREND_Q:
            continue
        d = 1 if x > 0 else -1
        pb = d * math.log(c15[-1] / c15[-1 - p_steps])
        if not (pb < 0):
            continue
        depth = -pb / abs(x)
        if H04_DEPTH_MIN <= depth < H04_DEPTH_MAX and (best is None or pctl > best["pctl"]):
            best = {"lookback_min": lmin, "pctl": pctl, "depth": depth, "direction": d}
    return {"T_ms": int(t15[-1]), "state": best is not None, "best": best}


def h02_state(b: Bars, i: int) -> Optional[dict]:
    """H02 failed breakout at the event bar i (closes at T): the bar opens and closes inside the
    range of the previous L minutes and pokes out of exactly one side, for some L in 60/120/240."""
    if i < 0 or i >= b.n or not math.isfinite(b.close[i]):
        return None
    o, h, lo, c = b.open[i], b.high[i], b.low[i], b.close[i]
    for lmin in H02_LOOKBACKS:
        k = lmin // 5
        if i - k < 0:
            continue
        hi_r, lo_r = b.high[i - k:i], b.low[i - k:i]
        if not (np.isfinite(hi_r).all() and np.isfinite(lo_r).all()):
            continue
        r_hi, r_lo = float(hi_r.max()), float(lo_r.min())
        if not (r_hi > r_lo) or not (r_lo <= o <= r_hi and r_lo <= c <= r_hi):
            continue
        up, down = h > r_hi, lo < r_lo
        if up and not down:
            return {"side": +1, "lookback_min": lmin, "level": r_hi}
        if down and not up:
            return {"side": -1, "lookback_min": lmin, "level": r_lo}
    return None


def market_0102_state(b: Bars, oi: np.ndarray, t_idx: int) -> Optional[dict]:
    """MARKET-01/02 at decision T = close of bar t_idx (t = T - 30m): a qualifying 30m impulse at t
    (percentile >= 0.90 among the previous 30 days of 30m impulses ending before t - 30m), OI
    expansion over [t, T] (percentile > 0.75 among the previous 30 days of 30m OI changes ending
    before t) and the continuation ratio over [t, T] (> 0.25: MARKET-02's arm; else MARKET-01's)."""
    k = M_IMPULSE_BARS
    i_t = t_idx - k                                    # bar closing at t
    if i_t - k - M_REF_BARS < 0:
        return None
    c = b.close
    if not (math.isfinite(c[i_t]) and math.isfinite(c[i_t - k]) and math.isfinite(c[t_idx])):
        return None
    imp = math.log(c[i_t] / c[i_t - k])
    if imp == 0:
        return None
    with np.errstate(divide="ignore", invalid="ignore"):
        all_imp = np.full(b.n, np.nan)
        all_imp[k:] = np.abs(np.log(c[k:] / c[:-k]))
        all_doi = np.full(b.n, np.nan)
        all_doi[k:] = np.where((oi[k:] > 0) & (oi[:-k] > 0), np.log(oi[k:] / oi[:-k]), np.nan)
    ref_imp = all_imp[i_t - k - M_REF_BARS:i_t - k]   # windows ending strictly before t - 30m
    p_imp = midrank(ref_imp, abs(imp))
    if p_imp is None or p_imp < M_IMPULSE_Q:
        return None
    if not (oi[i_t] > 0 and oi[t_idx] > 0):
        return None
    doi = math.log(oi[t_idx] / oi[i_t])
    p_oi = midrank(all_doi[i_t - M_REF_BARS:i_t], doi)   # 30m OI changes ending before t
    if p_oi is None or not p_oi > M_OI_Q:
        return {"qualifying_impulse": True, "oi_expansion": False}
    d = 1 if imp > 0 else -1
    ratio = d * math.log(c[t_idx] / c[i_t]) / abs(imp)
    return {"qualifying_impulse": True, "oi_expansion": True, "direction": d, "impulse": imp,
            "continuation_ratio": ratio, "confirmed": bool(ratio > M_CONFIRM_RATIO)}


# ---- D2 (RV abstention rule) ---------------------------------------------------------------
def d2_state(daily: Sequence[tuple]) -> Optional[dict]:
    """D2 RULE_1 for the newest decision day: daily = [(day_ms, rv or None)] oldest first, where
    rv is sqrt(sum of the 288 squared 5m log returns) of that UTC day (None when incomplete).
    ABSTAIN iff the newest valid rv > P90 of the previous 250 valid ones (t excluded, strict >)."""
    if not daily or daily[-1][1] is None:
        return None
    prev = [rv for _d, rv in daily[:-1] if rv is not None][-D2_TRAILING:]
    if len(prev) < D2_TRAILING:
        return None
    p90 = float(np.quantile(np.asarray(prev, dtype=float), 0.90))
    rv = float(daily[-1][1])
    return {"day_ms": int(daily[-1][0]), "rv": rv, "p90": p90, "state": bool(rv > p90)}
