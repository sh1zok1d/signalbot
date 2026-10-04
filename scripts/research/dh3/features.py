"""DH3 events, states and nuisance for the five cards, point-in-time at decision time T (the close
of the decision bar j). Every feature reads bars, snapshots or candles closed at or before T. No
outcome is computed here (`outcomes.py` is imported only by the evaluator).
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from beta import levels as LV
from beta.hist_series import BARS_PER_DAY, Bars
from scripts.research.dh1 import constants as K1
from scripts.research.dh1 import data as D1
from scripts.research.dh1 import events as E1
from scripts.research.dh2 import constants as K2
from scripts.research.dh2 import data as D2
from scripts.research.dh2 import events as E2

from . import constants as K
from . import data as D

BAR = K1.BAR_MS
HOUR = 3_600_000


# ---------------------------------------------------------------- shared
def epoch_of(ms: int) -> Optional[str]:
    return E2.epoch_of(ms, K.EPOCHS_ALL)


def hourly_js(b: Bars, start_ms: int, end_ms: int) -> list:
    out = []
    first = max(K1.SCALE_BARS + 60, 0)
    for j in range(first, b.n - K1.HOLD_BARS - 1):
        T = E1.decision_ms(b, j)
        if T % HOUR == 0 and start_ms <= T and T + K1.HOLD_BARS * BAR <= end_ms:
            out.append(j)
    return out


def _window_range(b: Bars, a: int, z: int) -> Optional[float]:
    if a < 0:
        return None
    hi, lo = b.high[a:z + 1], b.low[a:z + 1]
    ok = np.isfinite(hi) & np.isfinite(lo)
    if ok.mean() < K1.MIN_PRESENT or not math.isfinite(b.close[z]):
        return None
    return float(math.log((hi[ok].max() - lo[ok].min()) / b.close[z])) if hi[ok].max() > lo[ok].min() else None


def _logret(b: Bars, j: int, k: int) -> Optional[float]:
    if j - k < 0:
        return None
    a, z = b.close[j - k], b.close[j]
    return float(math.log(z / a)) if (math.isfinite(a) and math.isfinite(z) and a > 0) else None


def base(b: Bars, j: int, sigma: np.ndarray, symbol: str, endpoint: str, *, d: int = 1, side: int = 1) -> Optional[dict]:
    T = E1.decision_ms(b, j)
    sg = sigma[j]
    if not math.isfinite(sg) or sg <= 0:
        return None
    if endpoint == "RANGE_4H":
        lag = _window_range(b, j - K1.LAG_BARS + 1, j)
    elif endpoint == "UP_FIRST_4H":
        lag = _logret(b, j, K1.LAG_BARS)
    elif endpoint == "CONT_FIRST_4H":
        r = _logret(b, j - 12, K1.LAG_BARS)
        lag = None if r is None else d * r
    else:  # LEVEL_HOLD_4H
        r = _logret(b, j, K1.LAG_BARS)
        lag = None if r is None else side * r
    r1, r24 = _logret(b, j, 12), _logret(b, j, 288)
    if lag is None or r1 is None or r24 is None:
        return None
    return {"SYMBOL": symbol, "J": int(j), "T_MS": int(T), "EPOCH": epoch_of(T), "WEEK": E1.week_of(T),
            "HOUR_BLOCK": E1.hour_block(T), "RV": float(sg), "LAG": float(lag), "ABS_RET1": abs(r1), "TREND24": r24,
            "DIR": int(d), "SIDE": int(side), "ENDPOINT": endpoint,
            "X": float(K1.BARRIER_FRACTION * K1.CORRIDOR_Z * sg * math.sqrt(K1.HOLD_BARS))}


def _q(values, p):
    x = np.array([v for v in values if v is not None and math.isfinite(v)], dtype=float)
    return float(np.quantile(x, p)) if x.size else math.nan


# ---------------------------------------------------------------- card P (BTC positioning)
def card_p() -> dict:
    sym = "BTC"
    b = D1.to_bars(D1.load_binance_perp_5m(), K._ms("2020-01-01"), K._ms(K.SURFACES["DH3-P"]["END"]))
    m = D.metrics_on_grid(D.load_metrics(), b.t0, b.n)
    sigma = E1.rolling_sigma(b.close)
    js = hourly_js(b, K._ms(K.SURFACES["DH3-P"]["START"]), K._ms(K.SURFACES["DH3-P"]["END"]))
    ls_hourly = {j: m["ls"][j] for j in js}
    raw = []
    for k, j in enumerate(js):
        oi, oi4, oi1 = m["oi"][j], m["oi"][j - K.OI_LOOKBACK_4H], m["oi"][j - K.OI_LOOKBACK_1H]
        hist = [ls_hourly[x] for x in js[max(0, k - 24 * K.CROWD_Z_DAYS):k]]
        hist = np.array([v for v in hist if math.isfinite(v)])
        z = None
        if hist.size >= 600 and math.isfinite(m["ls"][j]) and hist.std() > 0:
            z = float((m["ls"][j] - hist.mean()) / hist.std())
        raw.append({"J": j, "DOI4": float(math.log(oi / oi4)) if (oi > 0 and oi4 > 0) else None,
                    "DOI1": float(math.log(oi / oi1)) if (oi > 0 and oi1 > 0) else None, "CROWD_Z": z,
                    "QUIET": _window_range(b, j - K1.LAG_BARS + 1, j)})
    q_quiet = _q([r["QUIET"] for r in raw], 1 / 3)
    q_doi4 = _q([r["DOI4"] for r in raw], 2 / 3)
    q_doi1 = _q([r["DOI1"] for r in raw], K.DELEVERAGE_DECILE)
    q_z = (_q([r["CROWD_Z"] for r in raw], 0.2), _q([r["CROWD_Z"] for r in raw], 0.8))
    out = {"DH3-P1": [], "DH3-P2": [], "DH3-P3": []}
    for r in raw:
        j = r["J"]
        if r["DOI4"] is not None and r["QUIET"] is not None and r["QUIET"] <= q_quiet:
            row = base(b, j, sigma, sym, "RANGE_4H")
            if row:
                out["DH3-P1"].append({**row, "S": int(r["DOI4"] >= q_doi4)})
        if r["DOI1"] is not None:
            row = base(b, j, sigma, sym, "RANGE_4H")
            if row:
                out["DH3-P2"].append({**row, "S": int(r["DOI1"] <= q_doi1)})
        if r["CROWD_Z"] is not None and (r["CROWD_Z"] <= q_z[0] or r["CROWD_Z"] >= q_z[1]):
            row = base(b, j, sigma, sym, "UP_FIRST_4H")
            if row:
                out["DH3-P3"].append({**row, "S": int(r["CROWD_Z"] >= q_z[1])})
    return {"ROWS": out, "BARS": {sym: b}}


# ---------------------------------------------------------------- card L (book depth, six coins)
def card_l() -> dict:
    out = {"DH3-L1": [], "DH3-L2": [], "DH3-L3": []}
    bars_by = {}
    start, end = K._ms(K.SURFACES["DH3-L"]["START"]), K._ms(K.SURFACES["DH3-L"]["END"])
    for sym in K.SURFACES["DH3-L"]["SYMBOLS"]:
        b, spot = D2.discovery(sym)
        bars_by[sym] = b
        book = D.book_on_grid(sym, b.t0, b.n)
        depth = book["bid1"] + book["ask1"]
        sigma = E1.rolling_sigma(b.close)
        js = hourly_js(b, start, end)
        hourly_depth = np.array([depth[j] for j in js])
        raw = []
        for k, j in enumerate(js):
            hist = hourly_depth[max(0, k - 24 * K.THIN_LOOKBACK_DAYS):k]
            hist = hist[np.isfinite(hist)]
            ratio = float(depth[j] / np.median(hist)) if (hist.size >= 120 and math.isfinite(depth[j])) else None
            bid, ask = book["bid1"][j], book["ask1"][j]
            asym = float(math.log(bid / ask)) if (math.isfinite(bid) and math.isfinite(ask) and bid > 0 and ask > 0) else None
            raw.append((j, ratio, asym))
        q_thin = _q([r[1] for r in raw], K.THIN_QUINTILE)
        q_a = (_q([r[2] for r in raw], 0.2), _q([r[2] for r in raw], 0.8))
        for j, ratio, asym in raw:
            if ratio is not None:
                row = base(b, j, sigma, sym, "RANGE_4H")
                if row:
                    out["DH3-L1"].append({**row, "S": int(ratio <= q_thin)})
            if asym is not None and (asym <= q_a[0] or asym >= q_a[1]):
                row = base(b, j, sigma, sym, "UP_FIRST_4H")
                if row:
                    out["DH3-L2"].append({**row, "S": int(asym >= q_a[1])})
        moves = E2.move_events(b, spot, sym, start, end - K.RECOVERY_LAG_BARS * BAR, K.EPOCHS_ALL)
        recs = []
        for mv in moves:
            i = mv["J"]
            j2 = i + K.RECOVERY_LAG_BARS
            before, after = depth[i - K1.MOVE_BARS], depth[j2]
            if j2 + K1.HOLD_BARS >= b.n or not (math.isfinite(before) and math.isfinite(after)) or before <= 0:
                continue
            row = base(b, j2, sigma, sym, "RANGE_4H")
            if row and row["T_MS"] + K1.HOLD_BARS * BAR <= end:
                recs.append({**row, "REC": float(after / before), "RATIO": mv["RATIO"]})
        q_rec = _q([r["REC"] for r in recs], 1 / 3)
        for r in recs:
            out["DH3-L3"].append({**r, "S": int(r["REC"] <= q_rec)})
    for rows in out.values():                     # card L epochs are half-years (constants.EPOCHS_L)
        for r in rows:
            r["EPOCH"] = E2.epoch_of(r["T_MS"], K.EPOCHS_L)
    return {"ROWS": out, "BARS": bars_by}


# ---------------------------------------------------------------- card O (DVOL, BTC and ETH)
def card_o() -> dict:
    out = {"DH3-O1": [], "DH3-O2": [], "DH3-O3": []}
    bars_by = {}
    start, end = K._ms(K.SURFACES["DH3-O"]["START"]), K._ms(K.SURFACES["DH3-O"]["END"])
    for sym in K.SURFACES["DH3-O"]["SYMBOLS"]:
        b = D1.to_bars(D1.load_binance_perp_5m(), K._ms("2020-01-01"), end) if sym == "BTC" else D2.discovery(sym)[0]
        bars_by[sym] = b
        dv = D.load_dvol(sym)
        dvol_at = dict(zip(dv["t"].tolist(), dv["close"].tolist()))
        sigma = E1.rolling_sigma(b.close)
        raw = []
        for j in hourly_js(b, start, end):
            T = E1.decision_ms(b, j)
            v1, v2 = dvol_at.get(T - HOUR), dvol_at.get(T - 2 * HOUR)
            if v1 is None or v2 is None or v1 <= 0 or v2 <= 0:
                continue
            implied = v1 / 100.0 * math.sqrt(4 / 8760)
            realized = sigma[j] * math.sqrt(K1.HOLD_BARS)
            series = [dvol_at.get(T - (k + 1) * HOUR) for k in range(K.UPVOL_WINDOW_H + 1)]
            prices = [b.close[j - 12 * k] if j - 12 * k >= 0 else np.nan for k in range(K.UPVOL_WINDOW_H + 1)]
            corr = None
            if all(v is not None and v > 0 for v in series) and np.isfinite(prices).all():
                dvs = np.diff(np.log(np.array(series[::-1])))
                dps = np.diff(np.log(np.array(prices[::-1])))
                if dvs.std() > 0 and dps.std() > 0:
                    corr = float(np.corrcoef(dvs, dps)[0, 1])
            raw.append((j, math.log(implied / realized) if realized > 0 else None, math.log(v1 / v2), corr))
        q1 = _q([r[1] for r in raw], 2 / 3)
        q2 = _q([r[2] for r in raw], K.DVOL_JUMP_DECILE)
        for j, r_ir, r_dv, corr in raw:
            row = base(b, j, sigma, sym, "RANGE_4H")
            if row and r_ir is not None:
                out["DH3-O1"].append({**row, "S": int(r_ir >= q1)})
            if row:
                out["DH3-O2"].append({**row, "S": int(r_dv >= q2)})
            if corr is not None:
                row3 = base(b, j, sigma, sym, "UP_FIRST_4H")
                if row3:
                    out["DH3-O3"].append({**row3, "S": int(corr > 0)})
    return {"ROWS": out, "BARS": bars_by}


# ---------------------------------------------------------------- card V (levels extended)
def _first_touch(b: Bars, a: int, z: int, level: float, side: int) -> Optional[int]:
    a, z = max(a, 0), min(z, b.n - 1)
    if a > z:
        return None
    return LV._first_touch(b, a, z, level, side)


def session_events(b: Bars, symbol: str, start_ms: int, end_ms: int, rng) -> list:
    sigma = E1.rolling_sigma(b.close)
    day0 = b.t0 // K1.DAY_MS
    ndays = b.n // BARS_PER_DAY + 1
    reals = []
    for dd in range(ndays):
        day_ms = (day0 + dd) * K1.DAY_MS
        for sess, (h0, m0, h1, m1) in K.SESSIONS.items():
            a = (day_ms + (h0 * 60 + m0) * 60_000 - b.t0) // BAR
            z = (day_ms + (h1 * 60 + m1) * 60_000 - b.t0) // BAR
            if a < 0 or z + K.SESSION_WINDOW_BARS >= b.n:
                continue
            seg = slice(int(a), int(z))
            if np.isfinite(b.close[seg]).mean() < 0.95:
                continue
            c_end = b.close[int(z) - 1]
            if not math.isfinite(c_end):
                continue
            for side, lvl in ((+1, float(np.nanmax(b.high[seg]))), (-1, float(np.nanmin(b.low[seg])))):
                if side * (lvl - c_end) <= 0:
                    continue
                reals.append((int(z), sess, side, lvl, float(c_end)))
    dist = {s: [lvl / c - 1 for (_, _, sd, lvl, c) in reals if sd == s] for s in (+1, -1)}
    rows = []
    for z, sess, side, lvl, c_end in reals:
        cands = [(1, lvl)] + [(0, c_end * (1 + float(rng.choice(dist[side])))) for _ in range(K.CONTROLS_PER_EVENT)]
        for s_flag, level in cands:
            j = _first_touch(b, z, z + K.SESSION_WINDOW_BARS - 1, level, side)
            if j is None:
                continue
            row = base(b, j, sigma, symbol, "LEVEL_HOLD_4H", side=side)
            if row and start_ms <= row["T_MS"] and row["T_MS"] + K1.HOLD_BARS * BAR <= end_ms:
                rows.append({**row, "LEVEL": level, "SESSION": sess, "S": s_flag})
    return rows


def key_level_events(b: Bars, symbol: str, start_ms: int, end_ms: int, rng) -> list:
    """Real first touches of PD/PW/PM highs and lows and the previous day's POC, and 2 random control
    levels per real level at distances drawn from the real distance distribution (product method)."""
    sigma = E1.rolling_sigma(b.close)
    keys = LV.period_keys(b)
    reals = []   # (period row, type, side, level)
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
                reals.append((cur, typ, side, float(lvl)))
    days = LV._period_table(b, keys["day"])
    for p in range(1, len(days)):
        prev, cur = days[p - 1], days[p]
        if prev["key"] != cur["key"] - 1 or not LV._full_period(cur, BARS_PER_DAY) or not LV._full_period(prev, BARS_PER_DAY):
            continue
        poc = LV.volume_poc(b, prev["first"], prev["last"] + 1)
        if poc is not None and abs(poc / cur["open"] - 1) >= 0.001:
            side = +1 if poc > cur["open"] else -1
            reals.append((cur, "POC_UP" if side > 0 else "POC_DOWN", side, float(poc)))
    dist: dict = {}
    for cur, typ, side, lvl in reals:
        dist.setdefault(typ, []).append(lvl / cur["open"] - 1)
    rows = []
    for cur, typ, side, lvl in reals:
        cands = [(1, lvl)] + [(0, cur["open"] * (1 + float(rng.choice(dist[typ])))) for _ in range(K.CONTROLS_PER_EVENT)]
        for s_flag, level in cands:
            j = _first_touch(b, cur["first"], cur["last"], level, side)
            if j is None:
                continue
            row = base(b, j, sigma, symbol, "RANGE_4H")
            if row and start_ms <= row["T_MS"] and row["T_MS"] + K1.HOLD_BARS * BAR <= end_ms:
                rows.append({**row, "LEVEL": level, "SIDE": side, "TYPE_GROUP": K2.TYPE_GROUP[typ], "S": s_flag})
    return rows


def retest_events(b: Bars, symbol: str, start_ms: int, end_ms: int) -> list:
    sigma = E1.rolling_sigma(b.close)
    rows = []
    for j1, typ, lvl, side in E1.raw_level_touches(b):
        if typ not in ("PDH", "PDL") or not math.isfinite(sigma[j1]):
            continue
        day_end = ((E1.decision_ms(b, j1) - 1) // K1.DAY_MS + 1) * K1.DAY_MS
        last = min(b.n - 1, (day_end - b.t0) // BAR - 1)
        row1 = base(b, j1, sigma, symbol, "LEVEL_HOLD_4H", side=side)
        if row1 and start_ms <= row1["T_MS"] and row1["T_MS"] + K1.HOLD_BARS * BAR <= end_ms:
            rows.append({**row1, "LEVEL": lvl, "TYPE": typ, "S": 0})
        x = K.RETEST_RETREAT_X * K1.BARRIER_FRACTION * K1.CORRIDOR_Z * sigma[j1] * math.sqrt(K1.HOLD_BARS)
        target = lvl * (1 - side * x)
        k = _first_touch(b, j1 + 1, last, target, -side)
        if k is None:
            continue
        j2 = _first_touch(b, k + 1, last, lvl, side)
        if j2 is None:
            continue
        row2 = base(b, j2, sigma, symbol, "LEVEL_HOLD_4H", side=side)
        if row2 and start_ms <= row2["T_MS"] and row2["T_MS"] + K1.HOLD_BARS * BAR <= end_ms:
            rows.append({**row2, "LEVEL": lvl, "TYPE": typ, "S": 1})
    return rows


def card_v(surface: str = "DISCOVERY") -> dict:
    out = {"DH3-V1": [], "DH3-V2": [], "DH3-V3": []}
    bars_by = {}
    if surface == "DISCOVERY":
        plan = [(s, *D2.discovery(s)[:1], K._ms(K2.DISCOVERY[s][1]), K._ms(K2.DISCOVERY_END))
                for s in K.SURFACES["DH3-V"]["SYMBOLS"]]
    else:
        plan = [(s, D2.replication_spot(s), K._ms(K2.REPLICATION_SPOT[s][1]), K._ms(K2.REPLICATION_END))
                for s in K2.REPLICATION_SPOT]
    for k, (sym, b, start, end) in enumerate(plan):
        bars_by[sym] = b
        rng = np.random.default_rng(K.CONTROL_SEED + 31 * k + (0 if surface == "DISCOVERY" else 1000))
        out["DH3-V1"] += session_events(b, sym, start, end, rng)
        out["DH3-V2"] += key_level_events(b, sym, start, end, rng)
        out["DH3-V3"] += retest_events(b, sym, start, end)
    return {"ROWS": out, "BARS": bars_by}


# ---------------------------------------------------------------- card S (spot<->perp at one second)
def card_s() -> dict:
    from . import aggtrades as A
    sym = "BTC"
    b = D1.to_bars(D1.load_binance_perp_5m(), K._ms("2020-01-01"), K._ms(K.SURFACES["DH3-S"]["END"]))
    sigma = E1.rolling_sigma(b.close)
    feats = A.load()
    end = K._ms(K.SURFACES["DH3-S"]["END"])
    raw = []
    for hour, f in sorted(feats.items()):
        T = hour + HOUR
        j = (T - b.t0) // BAR - 1
        if j < 0 or j + K1.HOLD_BARS >= b.n or T + K1.HOLD_BARS * BAR > end:
            continue
        r1 = _logret(b, j, 12)
        if r1 is None or r1 == 0:
            continue
        raw.append((j, f, 1 if r1 > 0 else -1))
    q_large = _q([f["N_LARGE_PERP"] for _, f, _ in raw if f["N_LARGE_PERP"] is not None], 2 / 3)
    thr = max(q_large, 0.0) if math.isfinite(q_large) else 0.0
    out = {"DH3-S1": [], "DH3-S2": [], "DH3-S3": []}
    for j, f, d in raw:
        if f["LEAD_SCORE"] is not None:
            row = base(b, j, sigma, sym, "RANGE_4H")
            if row:
                out["DH3-S1"].append({**row, "S": int(f["LEAD_SCORE"] < 0)})
            row2 = base(b, j, sigma, sym, "CONT_FIRST_4H", d=d)
            if row2:
                out["DH3-S2"].append({**row2, "S": int(f["LEAD_SCORE"] < 0)})
        if f["N_LARGE_PERP"] is not None:
            row = base(b, j, sigma, sym, "RANGE_4H")
            if row:
                out["DH3-S3"].append({**row, "S": int(f["N_LARGE_PERP"] > thr)})
    return {"ROWS": out, "BARS": {sym: b}}


BUILDERS = {"DH3-P": card_p, "DH3-L": card_l, "DH3-O": card_o, "DH3-V": card_v, "DH3-S": card_s}


# ---------------------------------------------------------------- design
TERCILE_SOURCES = {"RV_TERCILE": "RV", "LAG_TERCILE": "LAG", "ABS_RET1_TERCILE": "ABS_RET1",
                   "TREND24_TERCILE": "TREND24", "MOVE_TERCILE": "RATIO"}


def nuisance_names(h: dict) -> tuple:
    return tuple(K.NUISANCE_COMMON) + tuple(h["EXTRA"])


def cell_rows(rows: list, h: dict) -> list:
    names = nuisance_names(h)
    rows = [r for r in rows if r.get("EPOCH") is not None]
    out = [dict(r) for r in rows]
    for name, src in TERCILE_SOURCES.items():
        if name in names:
            vals = E2._terciles_within_symbol(rows, src)
            for r, v in zip(out, vals):
                r[name] = v
    return [r for r in out if all(r.get(n) is not None for n in names)]


def design_matrix(rows: list, h: dict, levels: Optional[dict] = None) -> tuple:
    names = nuisance_names(h)
    if levels is None:
        levels = {n: sorted({r[n] for r in rows}, key=str) for n in names}
    cols = [np.ones(len(rows)), np.array([r["S"] for r in rows], dtype=float)]
    labels = ["INTERCEPT", "S"]
    for n in names:
        for lv in levels[n][1:]:
            cols.append(np.array([1.0 if r[n] == lv else 0.0 for r in rows]))
            labels.append(f"{n}={lv}")
    return np.column_stack(cols), labels, levels
