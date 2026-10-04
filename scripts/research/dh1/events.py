"""DH1 events, states and nuisance features, point-in-time at the decision boundary.

Decision time T is the close of the event bar. Every feature reads bars that closed at or before
T. No outcome is computed here (outcomes live in `outcomes.py`, imported only by the evaluator).

Level events reuse the product's level rules (`beta/levels.py`): first touch in the period of
PDH/PDL/PWH/PWL/PMH/PML, round numbers within ±3 % of the UTC day open and the previous day's POC.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from beta import levels as LV
from beta.hist_series import BARS_PER_DAY, Bars

from . import constants as K


# ---------------------------------------------------------------- helpers
def log_returns(close: np.ndarray) -> np.ndarray:
    r = np.full(close.shape[0], np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        r[1:] = np.log(close[1:] / close[:-1])
    return r


def rolling_sigma(close: np.ndarray, window: int = K.SCALE_BARS, min_frac: float = K.MIN_PRESENT) -> np.ndarray:
    """sigma[e] = std of the 5m log returns r[e-window+1 .. e] (r[k] = log c[k]/c[k-1]); NaN if
    fewer than min_frac of them are finite. Known at the close of bar e."""
    r = log_returns(close)
    ok = np.isfinite(r)
    x = np.where(ok, r, 0.0)
    c0 = np.concatenate([[0], np.cumsum(ok)])
    c1 = np.concatenate([[0.0], np.cumsum(x)])
    c2 = np.concatenate([[0.0], np.cumsum(x * x)])
    n = close.shape[0]
    out = np.full(n, np.nan)
    e = np.arange(window - 1, n)
    cnt = c0[e + 1] - c0[e + 1 - window]
    s1 = c1[e + 1] - c1[e + 1 - window]
    s2 = c2[e + 1] - c2[e + 1 - window]
    with np.errstate(invalid="ignore", divide="ignore"):
        var = (s2 - s1 * s1 / cnt) / (cnt - 1)
    good = cnt >= min_frac * window
    out[e[good]] = np.sqrt(np.maximum(var[good], 0.0))
    return out


def window_sum(x: np.ndarray, a: int, z: int, min_frac: float = K.MIN_PRESENT) -> Optional[float]:
    """Sum of x[a..z] inclusive, or None if fewer than min_frac of the bars are present."""
    if a < 0:
        return None
    seg = x[a:z + 1]
    ok = np.isfinite(seg)
    if ok.mean() < min_frac:
        return None
    return float(seg[ok].sum())


def decision_ms(b: Bars, j: int) -> int:
    return b.t0 + (j + 1) * K.BAR_MS


def hour_block(ms: int) -> int:
    return int((ms // K.HOUR_MS) % 24) // 4


def epoch_of(ms: int, surface: str) -> Optional[str]:
    for name, a, z in K.SURFACES[surface]["EPOCHS"]:
        if K._ms(a) <= ms < K._ms(z):
            return name
    return None


def week_of(ms: int) -> int:
    """ISO week index (Monday-based) since the epoch; the cluster unit."""
    return int((ms // K.DAY_MS + 3) // 7)


def flow_terms(perp: Bars, spot: dict, a: int, z: int, side: int) -> dict:
    """Aligned spot net taker flow and perp taker imbalance over bars a..z (inclusive)."""
    out = {"SPOT_NET": None, "PERP_IMB": None, "SPOT_QUOTE": None, "PERP_QUOTE": None}
    sq, stb = window_sum(spot["quote"], a, z), window_sum(spot["taker_buy_quote"], a, z)
    pq, ptb = window_sum(perp.quote, a, z), window_sum(perp.taker_buy_quote, a, z)
    if sq is not None and stb is not None:
        out["SPOT_NET"] = side * (2.0 * stb - sq)
        out["SPOT_QUOTE"] = sq
    if pq is not None and ptb is not None and pq > 0:
        out["PERP_IMB"] = side * (2.0 * ptb - pq) / pq
        out["PERP_QUOTE"] = pq
    return out


# ---------------------------------------------------------------- level events (card L)
def raw_level_touches(b: Bars) -> list:
    """[(touch bar j, type, level, side)] by the product's first-touch rules (real levels only)."""
    keys = LV.period_keys(b)
    out = []
    spec = {"D": ("day", BARS_PER_DAY), "W": ("week", 7 * BARS_PER_DAY), "M": ("month", None)}
    for pref, (name, exp) in spec.items():
        periods = LV._period_table(b, keys[name])
        for typ, side in ((f"P{pref}H", +1), (f"P{pref}L", -1)):
            for p in range(1, len(periods)):
                prev, cur = periods[p - 1], periods[p]
                if prev["key"] != cur["key"] - 1 or not LV._full_period(prev, exp) or not LV._full_period(cur, exp):
                    continue
                lvl = prev["high"] if side > 0 else prev["low"]
                if side * (lvl - cur["open"]) <= 0:
                    continue
                j = LV._first_touch(b, cur["first"], cur["last"], lvl, side)
                if j is not None:
                    out.append((j, typ, float(lvl), side))
    days = LV._period_table(b, keys["day"])
    for p in range(1, len(days)):
        prev, cur = days[p - 1], days[p]
        if prev["key"] != cur["key"] - 1 or not LV._full_period(cur, BARS_PER_DAY):
            continue
        o = cur["open"]
        lo, hi = math.ceil(o * 0.97 / LV.ROUND_STEP), math.floor(o * 1.03 / LV.ROUND_STEP)
        for k in range(lo, hi + 1):
            lvl = k * LV.ROUND_STEP
            if abs(lvl / o - 1) < 0.001:
                continue
            side = +1 if lvl > o else -1
            j = LV._first_touch(b, cur["first"], cur["last"], lvl, side)
            if j is not None:
                out.append((j, "ROUND_UP" if side > 0 else "ROUND_DOWN", float(lvl), side))
        if LV._full_period(prev, BARS_PER_DAY):
            poc = LV.volume_poc(b, prev["first"], prev["last"] + 1)
            if poc is not None and abs(poc / o - 1) >= 0.001:
                side = +1 if poc > o else -1
                j = LV._first_touch(b, cur["first"], cur["last"], poc, side)
                if j is not None:
                    out.append((j, "POC_UP" if side > 0 else "POC_DOWN", float(poc), side))
    return out


def dedupe_touches(touches: list) -> list:
    """One event per (touch bar, side): the most important type is kept."""
    best: dict = {}
    for j, typ, lvl, side in touches:
        key = (j, side)
        if key not in best or K.TYPE_PRIORITY[typ] < K.TYPE_PRIORITY[best[key][1]]:
            best[key] = (j, typ, lvl, side)
    return sorted(best.values())


def confluent(b: Bars, j: int, typ: str, lvl: float) -> Optional[bool]:
    a = max(0, j + 1 - K.CONFLUENCE_LOOKBACK_BARS)
    sub = b.slice(a, j + 1)
    price = float(b.close[j])
    if not math.isfinite(price):
        return None
    own = K.LIVE_KIND[typ]
    near = {lv["kind"] for lv in LV.compute_levels(sub, now_ms=decision_ms(b, j), price=price)
            if not lv["kind"].startswith("LIQ") and lv["kind"] != own
            and abs(lv["price"] / lvl - 1) <= K.CONFLUENCE_TOL}
    return bool(near)


def stale(b: Bars, j: int, lvl: float) -> Optional[bool]:
    a = j - K.STALE_BARS
    if a < 0:
        return None
    hi, lo = b.high[a:j], b.low[a:j]
    ok = np.isfinite(hi) & np.isfinite(lo)
    if ok.mean() < K.MIN_PRESENT:
        return None
    traded = (lo[ok] <= lvl) & (hi[ok] >= lvl)
    return not bool(traded.any())


def level_events(b: Bars, spot: dict, surface: str) -> list:
    s = K.SURFACES[surface]
    start, end = K._ms(s["EVENT_START"]), K._ms(s["END"])
    sigma = rolling_sigma(b.close)
    out = []
    for j, typ, lvl, side in dedupe_touches(raw_level_touches(b)):
        T = decision_ms(b, j)
        if T < start or T + K.HOLD_BARS * K.BAR_MS > end or j + K.HOLD_BARS >= b.n:
            continue
        c, c_lag = b.close[j], (b.close[j - K.LAG_BARS] if j >= K.LAG_BARS else np.nan)
        flow = flow_terms(b, spot, j - K.APPROACH_BARS + 1, j, side)
        rec = {"J": int(j), "T_MS": int(T), "TYPE": typ, "TYPE_GROUP": K.TYPE_GROUP[typ], "LEVEL": lvl, "SIDE": int(side),
               "EPOCH": epoch_of(T, surface), "WEEK": week_of(T), "HOUR_BLOCK": hour_block(T),
               "RV": float(sigma[j]) if math.isfinite(sigma[j]) else None,
               "LAG": float(side * math.log(c / c_lag)) if (math.isfinite(c) and math.isfinite(c_lag)) else None,
               "PERP_IMB": flow["PERP_IMB"],
               "SPOT_CONFIRMED_APPROACH": (None if flow["SPOT_NET"] is None else bool(flow["SPOT_NET"] > 0)),
               "CONFLUENT_LEVEL": confluent(b, j, typ, lvl),
               "STALE_LEVEL": stale(b, j, lvl)}
        out.append(rec)
    return out


# ---------------------------------------------------------------- sharp-move events (card B)
def move_events(b: Bars, spot: dict, surface: str) -> list:
    s = K.SURFACES[surface]
    start, end = K._ms(s["EVENT_START"]), K._ms(s["END"])
    sigma = rolling_sigma(b.close)
    c = b.close
    out = []
    i = K.MOVE_BARS + K.SCALE_BARS + 1
    last_event = -10 ** 9
    while i < b.n:
        if i - last_event <= K.MOVE_REFRACTORY_BARS:
            i += 1
            continue
        c0, c1, sg = c[i - K.MOVE_BARS], c[i], sigma[i - K.MOVE_BARS]
        if not (math.isfinite(c0) and math.isfinite(c1) and math.isfinite(sg)) or sg <= 0 \
                or not np.isfinite(c[i - K.MOVE_BARS:i + 1]).all():
            i += 1
            continue
        move = math.log(c1 / c0)
        ratio = abs(move) / (sg * math.sqrt(12))
        if ratio < K.MOVE_RATIO_MIN or move == 0:
            i += 1
            continue
        last_event = i
        T = decision_ms(b, i)
        if T < start or T + K.HOLD_BARS * K.BAR_MS > end or i + K.HOLD_BARS >= b.n:
            i += 1
            continue
        d = 1 if move > 0 else -1
        a, z = i - K.MOVE_BARS + 1, i
        flow = flow_terms(b, spot, a, z, d)
        c_lag = c[i - K.MOVE_BARS - K.LAG_BARS] if i - K.MOVE_BARS - K.LAG_BARS >= 0 else np.nan
        share_move = share_base = None
        sq_base = window_sum(spot["quote"], a - K.SCALE_BARS, a - 1)
        pq_base = window_sum(b.quote, a - K.SCALE_BARS, a - 1)
        if flow["SPOT_QUOTE"] is not None and flow["PERP_QUOTE"] is not None and sq_base is not None and pq_base is not None:
            if flow["SPOT_QUOTE"] + flow["PERP_QUOTE"] > 0 and sq_base + pq_base > 0:
                share_move = flow["SPOT_QUOTE"] / (flow["SPOT_QUOTE"] + flow["PERP_QUOTE"])
                share_base = sq_base / (sq_base + pq_base)
        x = K.BARRIER_FRACTION * K.CORRIDOR_Z * sg * math.sqrt(K.HOLD_BARS)
        out.append({"J": int(i), "T_MS": int(T), "DIR": d, "RATIO": float(ratio), "X": float(x),
                    "EPOCH": epoch_of(T, surface), "WEEK": week_of(T), "HOUR_BLOCK": hour_block(T),
                    "RV": float(sg),
                    "LAG": float(d * math.log(c0 / c_lag)) if math.isfinite(c_lag) else None,
                    "PERP_IMB": flow["PERP_IMB"],
                    "SPOT_CONFIRMED_MOVE": (None if flow["SPOT_NET"] is None else bool(flow["SPOT_NET"] > 0)),
                    "SPOT_SHARE_HIGH_MOVE": (None if share_move is None else bool(share_move > share_base))})
        i += 1
    return out


# ---------------------------------------------------------------- design
def tercile(values: list) -> list:
    """Within-surface tercile index (0, 1, 2) of each value; None stays None. Frozen rule."""
    x = np.array([v for v in values if v is not None], dtype=float)
    if x.size < 3:
        return [None] * len(values)
    q1, q2 = np.quantile(x, [1 / 3, 2 / 3])
    return [None if v is None else int(v > q1) + int(v > q2) for v in values]


def cell_rows(events: list, hypothesis: dict) -> list:
    """Events of one primary cell with complete state and nuisance; terciles within the cell."""
    card = K.CARDS[hypothesis["CARD"]]
    state = hypothesis["STATE"]
    need = ["RV", "LAG"] + (["PERP_IMB"] if "PERP_IMB_TERCILE" in hypothesis["NUISANCE_EXTRA"] else [])
    rows = [e for e in events if e.get(state) is not None and e["EPOCH"] is not None
            and all(e.get(k) is not None for k in need)]
    rv_t = tercile([e["RV"] for e in rows])
    lag_t = tercile([e["LAG"] for e in rows])
    mv_t = tercile([e.get("RATIO") for e in rows]) if "MOVE_TERCILE" in card["NUISANCE_EXTRA"] else [None] * len(rows)
    imb_t = tercile([e["PERP_IMB"] for e in rows]) if "PERP_IMB" in need else [None] * len(rows)
    out = []
    for k, e in enumerate(rows):
        r = dict(e)
        r.update({"S": int(bool(e[state])), "RV_TERCILE": rv_t[k], "LAG_TERCILE": lag_t[k],
                  "MOVE_TERCILE": mv_t[k], "PERP_IMB_TERCILE": imb_t[k]})
        out.append(r)
    return out


def nuisance_names(hypothesis: dict) -> tuple:
    card = K.CARDS[hypothesis["CARD"]]
    return tuple(K.NUISANCE_COMMON) + tuple(card["NUISANCE_EXTRA"]) + tuple(hypothesis["NUISANCE_EXTRA"])


def design_matrix(rows: list, hypothesis: dict, levels: Optional[dict] = None) -> tuple:
    """[1, S, nuisance dummies (first level dropped)]; `levels` freezes the dummy coding."""
    names = nuisance_names(hypothesis)
    if levels is None:
        levels = {n: sorted({r[n] for r in rows}) for n in names}
    cols = [np.ones(len(rows)), np.array([r["S"] for r in rows], dtype=float)]
    labels = ["INTERCEPT", "S"]
    for n in names:
        for lv in levels[n][1:]:
            cols.append(np.array([1.0 if r[n] == lv else 0.0 for r in rows]))
            labels.append(f"{n}={lv}")
    return np.column_stack(cols), labels, levels
