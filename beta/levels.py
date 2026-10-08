"""Objective price levels and what happened at them before (PRODUCT_DECISION_V2 §2.2).

Only levels the whole market can see, computed from Binance USD-M BTCUSDT 5m bars (periods are
UTC, like the exchange's daily candle):

- previous day / week / month high and low (PDH, PDL, PWH, PWL, PMH, PML);
- day / week / month open (DO, WO, MO);
- the high and low of the last completed Asia, Europe and US sessions;
- the current UTC day's VWAP and the previous day's volume point of control (POC);
- round numbers (multiples of 1000; multiples of 5000 are "крупный");
- the last 24h liquidation clusters (live collector only; no history exists).

No hand-drawn lines, no "support/resistance" claims. Nearby levels merge into one zone.

`level_reaction_stats` measures, on history, the first touch of a level in its period: how
often price stayed beyond it after 1h / 4h, the typical move further and back, and the same
for random levels at the same distance from the period open (the control). A difference is
called only after a period-clustered bootstrap with a Holm correction across the family and a
materiality floor (PRODUCT_DECISION_V2 §3).

Pure numpy; no I/O.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

import numpy as np

from .hist_series import BAR_MS, BARS_PER_DAY, Bars, forward_extremes

LEVELS_VERSION = "BETA_LEVELS_V1"
LEVEL_STATS_VERSION = "BETA_LEVEL_STATS_V1"
DAY_MS = 86_400_000

# importance order (first = most important) — used to name a zone and to pick push levels
LEVEL_ORDER = ("PMH", "PML", "PWH", "PWL", "PDH", "PDL", "MO", "WO", "DO", "LIQ_LONG", "LIQ_SHORT",
               "POC_PD", "US_H", "US_L", "EU_H", "EU_L", "ASIA_H", "ASIA_L", "VWAP_D", "ROUND")
PUSH_LEVELS = ("PDH", "PDL", "PWH", "PWL", "PMH", "PML")
# Venues in the clusters. OKX stays out: until the collector fix (2026-10, data reliability D1) it
# stored no row at all, and its feed "doesn't represent the total number of liquidations" (OKX
# docs), so its clusters would be partial. Rows are now in BTC (sz x ctVal); old-mapping Bybit
# rows are read with their side swapped (storage fetch_liquidations, beta.liq_mapping).
LIQ_VENUES = ("binance", "bybit")
SESSIONS = {"ASIA": (0, 0, 8, 0), "EU": (8, 0, 13, 30), "US": (13, 30, 20, 0)}   # UTC h, m → h, m
ZONE_TOL_PCT = 0.15
AT_LEVEL_PCT = 0.03
ROUND_STEP = 1000.0
ROUND_MAJOR = 5000.0
POC_BIN_PCT = 0.05
LIQ_BIN_USD = 100.0
LIQ_MIN_NOTIONAL = 2_000_000.0
LIQ_WINDOW_MS = DAY_MS
SHOW_EACH_SIDE = 3

# history statistics
STAT_TYPES = ("PDH", "PDL", "PWH", "PWL", "PMH", "PML", "ROUND_UP", "ROUND_DOWN", "POC_UP", "POC_DOWN")
OUTCOME_BARS = {"1h": 12, "4h": 48}
CONTROLS_PER_PERIOD = 5
BOOTSTRAP_B = 1000
MIN_EVENTS = 30
MIN_PERIODS = 15
MATERIAL_DIFF = 0.03
ALPHA = 0.05
SEED = 20261003


# ---- periods ------------------------------------------------------------------------------
def _month_key(ms: np.ndarray) -> np.ndarray:
    d = (np.asarray(ms, dtype="datetime64[ms]")).astype("datetime64[M]")
    return d.astype(np.int64)


def period_keys(b: Bars) -> dict:
    t = b.times
    day = t // DAY_MS
    return {"day": day, "week": (day + 3) // 7, "month": _month_key(t)}


def _period_table(b: Bars, key: np.ndarray) -> list:
    """[(key, first index, last index, open, high, low, complete)] in order."""
    out = []
    if b.n == 0:
        return out
    edges = np.flatnonzero(np.diff(key)) + 1
    starts = np.concatenate([[0], edges])
    ends = np.concatenate([edges, [b.n]])
    for s, e in zip(starts, ends):
        present = np.isfinite(b.close[s:e])
        frac = present.mean() if e > s else 0.0
        hi = np.nanmax(b.high[s:e]) if present.any() else np.nan
        lo = np.nanmin(b.low[s:e]) if present.any() else np.nan
        out.append({"key": int(key[s]), "first": int(s), "last": int(e - 1), "open": float(b.open[s]),
                    "high": float(hi), "low": float(lo), "frac": float(frac), "bars": int(e - s)})
    return out


def _full_period(row: Mapping[str, Any], expected_bars: Optional[int]) -> bool:
    if expected_bars is not None and row["bars"] < expected_bars * 0.98:
        return False
    return row["frac"] >= 0.95 and math.isfinite(row["high"]) and math.isfinite(row["low"])


def volume_poc(b: Bars, a: int, z: int, *, bin_pct: float = POC_BIN_PCT) -> Optional[float]:
    """Point of control of bars [a, z): each bar's volume spread evenly over its price range."""
    hi, lo, vol = b.high[a:z], b.low[a:z], b.volume[a:z]
    ok = np.isfinite(hi) & np.isfinite(lo) & np.isfinite(vol)
    if ok.sum() < 12:
        return None
    hi, lo, vol = hi[ok], lo[ok], vol[ok]
    width = float(np.median(lo)) * bin_pct / 100.0
    base = float(lo.min())
    i0 = np.floor((lo - base) / width).astype(np.int64)
    i1 = np.floor((hi - base) / width).astype(np.int64)
    span = i1 - i0 + 1
    nbins = int(i1.max()) + 1
    prof = np.zeros(nbins)
    rep = np.repeat(np.arange(i0.size), span)
    offs = np.arange(rep.size) - np.repeat(np.cumsum(span) - span, span)
    np.add.at(prof, i0[rep] + offs, (vol / span)[rep])
    k = int(np.argmax(prof))
    return base + (k + 0.5) * width


# ---- live levels -----------------------------------------------------------------------------
def _add(out: list, kind: str, price: Optional[float], **extra) -> None:
    if price is None or not math.isfinite(price) or price <= 0:
        return
    out.append({"kind": kind, "price": float(price), **extra})


def compute_levels(b: Bars, *, now_ms: int, price: float, liquidations: Iterable[Mapping] = ()) -> list:
    """Every candidate level as of `now_ms` from bars that closed before it."""
    out: list = []
    if b.n == 0:
        return out
    keys = period_keys(b)
    now_day = now_ms // DAY_MS
    now_week = (now_day + 3) // 7
    now_month = int(np.asarray([now_ms], dtype="datetime64[ms]").astype("datetime64[M]").astype(np.int64)[0])
    for name, cur, pref, exp in (("day", now_day, "D", BARS_PER_DAY), ("week", now_week, "W", 7 * BARS_PER_DAY),
                                 ("month", now_month, "M", None)):
        table = {r["key"]: r for r in _period_table(b, keys[name])}
        prev = table.get(cur - 1)
        if prev is not None and _full_period(prev, exp):
            _add(out, f"P{pref}H", prev["high"], period=name)
            _add(out, f"P{pref}L", prev["low"], period=name)
        cur_row = table.get(cur)
        if cur_row is not None and np.isfinite(b.open[cur_row["first"]]) \
                and b.t0 + cur_row["first"] * BAR_MS == _period_start_ms(name, now_ms):
            _add(out, f"{pref}O", cur_row["open"], period=name)
    # sessions: the most recent completed occurrence within the last 24h
    for sess, (h0, m0, h1, m1) in SESSIONS.items():
        for back in (0, 1):
            day0 = (now_day - back) * DAY_MS
            s, e = day0 + (h0 * 60 + m0) * 60_000, day0 + (h1 * 60 + m1) * 60_000
            if e > now_ms or now_ms - e > DAY_MS:
                continue
            a, z = (s - b.t0) // BAR_MS, (e - b.t0) // BAR_MS
            if a < 0 or z > b.n:
                continue
            seg = slice(int(a), int(z))
            if np.isfinite(b.close[seg]).mean() < 0.95:
                break
            _add(out, f"{sess}_H", float(np.nanmax(b.high[seg])), session=sess, ended_ms=int(e))
            _add(out, f"{sess}_L", float(np.nanmin(b.low[seg])), session=sess, ended_ms=int(e))
            break
    # VWAP of the current UTC day (after at least one hour)
    a = (now_day * DAY_MS - b.t0) // BAR_MS
    if 0 <= a < b.n and b.n - a >= 12:
        seg = slice(int(a), b.n)
        tp = (b.high[seg] + b.low[seg] + b.close[seg]) / 3.0
        vol = b.volume[seg]
        ok = np.isfinite(tp) & np.isfinite(vol)
        if ok.sum() >= 12 and vol[ok].sum() > 0:
            _add(out, "VWAP_D", float(np.sum(tp[ok] * vol[ok]) / np.sum(vol[ok])))
    # previous day's volume point of control
    pa, pz = a - BARS_PER_DAY, a
    if pa >= 0 and np.isfinite(b.close[int(pa):int(pz)]).mean() >= 0.95:
        _add(out, "POC_PD", volume_poc(b, int(pa), int(pz)))
    # round numbers around the price
    base = math.floor(price / ROUND_STEP) * ROUND_STEP
    for k in (-1, 0, 1, 2):
        lvl = base + k * ROUND_STEP
        _add(out, "ROUND", lvl, major=bool(lvl % ROUND_MAJOR == 0))
    out.extend(liquidation_clusters(liquidations, now_ms=now_ms, price=price))
    return out


def _period_start_ms(name: str, now_ms: int) -> int:
    day = now_ms // DAY_MS
    if name == "day":
        return day * DAY_MS
    if name == "week":
        return (day - (day + 3) % 7) * DAY_MS
    dt = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc)
    return int(datetime(dt.year, dt.month, 1, tzinfo=timezone.utc).timestamp() * 1000)


def liquidation_clusters(rows: Iterable[Mapping], *, now_ms: int, price: float,
                         bin_usd: float = LIQ_BIN_USD, min_notional: float = LIQ_MIN_NOTIONAL,
                         max_distance_pct: float = 6.0) -> list:
    """Price bins of the last 24h with the largest liquidated notional, per liquidated side."""
    sums: dict = {}
    for r in rows:
        ts = r["ts"]
        ms = int(ts.timestamp() * 1000) if isinstance(ts, datetime) else int(ts)
        if not (now_ms - LIQ_WINDOW_MS <= ms <= now_ms):
            continue
        p = float(r["price"])
        notional = r.get("notional")
        notional = float(notional) if notional is not None else p * float(r.get("qty") or 0.0)
        side = str(r["side"]).lower()
        if side not in ("long", "short") or notional <= 0:
            continue
        key = (side, math.floor(p / bin_usd))
        sums[key] = sums.get(key, 0.0) + notional
    out = []
    for side in ("long", "short"):
        cand = sorted(((v, k[1]) for k, v in sums.items() if k[0] == side), reverse=True)
        for v, kbin in cand[:2]:
            mid = (kbin + 0.5) * bin_usd
            if v >= min_notional and abs(mid / price - 1) * 100 <= max_distance_pct:
                out.append({"kind": "LIQ_LONG" if side == "long" else "LIQ_SHORT", "price": mid,
                            "notional_usd": v})
    return out


def merge_zones(levels: Sequence[Mapping], *, price: float, tol_pct: float = ZONE_TOL_PCT) -> list:
    """Sort by price and merge levels closer than `tol_pct` into zones."""
    pts = sorted(levels, key=lambda r: r["price"])
    zones: list = []
    for lv in pts:
        if zones and (lv["price"] - zones[-1]["high"]) / price * 100.0 <= tol_pct:
            z = zones[-1]
            z["high"] = max(z["high"], lv["price"])
            z["members"].append(dict(lv))
        else:
            zones.append({"low": lv["price"], "high": lv["price"], "members": [dict(lv)]})
    for z in zones:
        z["members"].sort(key=lambda m: LEVEL_ORDER.index(m["kind"]) if m["kind"] in LEVEL_ORDER else 99)
        z["kinds"] = [m["kind"] for m in z["members"]]
        z["mid"] = (z["low"] + z["high"]) / 2.0
    return zones


def _rank(zone: Mapping[str, Any]) -> int:
    return min(LEVEL_ORDER.index(k) if k in LEVEL_ORDER else 99 for k in zone["kinds"])


def nearest_zones(zones: Sequence[Mapping], *, price: float, each_side: int = SHOW_EACH_SIDE,
                  at_pct: float = AT_LEVEL_PCT, reach_pct: Optional[float] = None) -> dict:
    """The zones shown above and below, and the zone the price sits at (if any).

    Per side: among zones within `reach_pct` (the 24h corridor half-width, at least 1%), the
    most important ones first (LEVEL_ORDER), then the nearest; at most one bare round number;
    if fewer than `each_side` are within reach, the nearest beyond fill in. Shown nearest
    first."""
    above, below, at = [], [], None
    for z in zones:
        lo_d = (z["low"] / price - 1) * 100.0
        hi_d = (z["high"] / price - 1) * 100.0
        if lo_d <= at_pct and hi_d >= -at_pct:
            if at is None or _rank(z) < _rank(at):
                at = z
        elif lo_d > 0:
            above.append(z)
        else:
            below.append(z)
    reach = max(1.0, float(reach_pct or 0.0))
    return {"above": [_with_distance(z, price, z["low"]) for z in _pick(above, each_side, price, reach)],
            "below": [_with_distance(z, price, z["high"]) for z in _pick(below, each_side, price, reach)],
            "at": _with_distance(at, price, at["mid"]) if at else None}


def _dist(z: Mapping[str, Any], price: float) -> float:
    return min(abs(z["low"] / price - 1), abs(z["high"] / price - 1)) * 100.0


def _pick(zones: list, n: int, price: float, reach: float) -> list:
    """The nearest zone first (what the price meets next), then the most important within
    reach, then the nearest beyond reach."""
    by_dist = sorted(zones, key=lambda z: _dist(z, price))
    first = by_dist[:1]
    near = sorted((z for z in by_dist[1:] if _dist(z, price) <= reach), key=lambda z: (_rank(z), _dist(z, price)))
    far = [z for z in by_dist[1:] if _dist(z, price) > reach]
    out, bare_round = [], False
    for z in first + near + far:
        if len(out) >= n:
            break
        if z["kinds"] == ["ROUND"]:
            if bare_round:
                continue
            bare_round = True
        out.append(z)
    return sorted(out, key=lambda z: _dist(z, price))


def _with_distance(z: Mapping[str, Any], price: float, edge: float) -> dict:
    return {**z, "edge": edge, "distance_pct": (edge / price - 1) * 100.0}


# ---- history: reaction at the first touch ---------------------------------------------------
def _first_touch(b: Bars, a: int, z: int, level: float, side: int) -> Optional[int]:
    seg = b.high[a:z + 1] >= level if side > 0 else b.low[a:z + 1] <= level
    seg = np.nan_to_num(seg, nan=0).astype(bool)
    if not seg.any():
        return None
    return a + int(np.argmax(seg))


def _outcome(fwd: Mapping[str, tuple], j: int, level: float, side: int) -> Optional[dict]:
    out = {}
    for h, (fhi, flo, fcl) in fwd.items():
        if not (math.isfinite(fhi[j]) and math.isfinite(flo[j]) and math.isfinite(fcl[j])):
            return None
        if side > 0:
            further, back = (fhi[j] - level) / level * 100.0, (level - flo[j]) / level * 100.0
        else:
            further, back = (level - flo[j]) / level * 100.0, (fhi[j] - level) / level * 100.0
        out[h] = {"hold": bool(side * (fcl[j] - level) > 0), "further": max(further, 0.0), "back": max(back, 0.0)}
    return out


def _events_for(b: Bars, periods: Sequence[Mapping], levels: Sequence[tuple], fwd) -> list:
    """levels = [(period index, level, side)] → events with outcomes (touched or not)."""
    out = []
    for p, level, side in levels:
        row = periods[p]
        j = _first_touch(b, row["first"], row["last"], level, side)
        rec = {"period": int(row["key"]), "touched": j is not None, "outcome": None}
        if j is not None:
            rec["outcome"] = _outcome(fwd, j, level, side)
        out.append(rec)
    return out


def _real_and_control(b: Bars, *, seed: int) -> dict:
    keys = period_keys(b)
    fwd = {h: forward_extremes(b, n) for h, n in OUTCOME_BARS.items()}
    rng = np.random.default_rng(seed)
    out: dict = {}
    spec = {"D": ("day", BARS_PER_DAY), "W": ("week", 7 * BARS_PER_DAY), "M": ("month", None)}
    for pref, (name, exp) in spec.items():
        periods = _period_table(b, keys[name])
        for typ, side in ((f"P{pref}H", +1), (f"P{pref}L", -1)):
            real, deltas = [], []
            for p in range(1, len(periods)):
                prev, cur = periods[p - 1], periods[p]
                if prev["key"] != cur["key"] - 1 or not _full_period(prev, exp) or not _full_period(cur, exp):
                    continue
                lvl = prev["high"] if side > 0 else prev["low"]
                if side * (lvl - cur["open"]) <= 0:
                    continue                    # opened beyond the level: no approach
                real.append((p, lvl, side))
                deltas.append(lvl / cur["open"] - 1)
            ctrl = []
            if deltas:
                d = np.asarray(deltas)
                for p, _lvl, _s in real:
                    for dd in rng.choice(d, size=CONTROLS_PER_PERIOD, replace=True):
                        ctrl.append((p, periods[p]["open"] * (1 + float(dd)), side))
            out[typ] = {"real": _events_for(b, periods, real, fwd), "control": _events_for(b, periods, ctrl, fwd),
                        "period": name}
    # round numbers and the previous day's POC, per UTC day, on either side of the open
    days = _period_table(b, keys["day"])
    rounds = {+1: [], -1: []}
    rctrl = {+1: [], -1: []}
    pocs = {+1: [], -1: []}
    pdeltas = {+1: [], -1: []}
    for p in range(1, len(days)):
        prev, cur = days[p - 1], days[p]
        if prev["key"] != cur["key"] - 1 or not _full_period(cur, BARS_PER_DAY):
            continue
        o = cur["open"]
        lo, hi = math.ceil(o * 0.97 / ROUND_STEP), math.floor(o * 1.03 / ROUND_STEP)
        for k in range(lo, hi + 1):
            lvl = k * ROUND_STEP
            if abs(lvl / o - 1) < 0.001:
                continue
            side = +1 if lvl > o else -1
            rounds[side].append((p, lvl, side))
            for u in rng.uniform(0.0015, 0.0045, size=2) * rng.choice([-1, 1], size=2):
                c = lvl * (1 + float(u))
                if side * (c - o) > 0 and abs(c / o - 1) >= 0.001:
                    rctrl[side].append((p, c, side))
        if _full_period(prev, BARS_PER_DAY):
            poc = volume_poc(b, prev["first"], prev["last"] + 1)
            if poc is not None and abs(poc / o - 1) >= 0.001:
                side = +1 if poc > o else -1
                pocs[side].append((p, poc, side))
                pdeltas[side].append(poc / o - 1)
    for side, name in ((+1, "UP"), (-1, "DOWN")):
        out[f"ROUND_{name}"] = {"real": _events_for(b, days, rounds[side], fwd),
                                "control": _events_for(b, days, rctrl[side], fwd), "period": "day"}
        ctrl = []
        if pdeltas[side]:
            d = np.asarray(pdeltas[side])
            for p, _l, s in pocs[side]:
                for dd in rng.choice(d, size=CONTROLS_PER_PERIOD, replace=True):
                    ctrl.append((p, days[p]["open"] * (1 + float(dd)), s))
        out[f"POC_{name}"] = {"real": _events_for(b, days, pocs[side], fwd),
                              "control": _events_for(b, days, ctrl, fwd), "period": "day"}
    return out


def _summ(events: Sequence[Mapping]) -> dict:
    touched = [e for e in events if e["touched"]]
    done = [e for e in touched if e["outcome"] is not None]
    res = {"approaches": len(events), "touched": len(touched),
           "touch_rate": (len(touched) / len(events)) if events else None, "n": len(done),
           "periods": len({e["period"] for e in done})}
    for h in OUTCOME_BARS:
        if not done:
            res[h] = None
            continue
        res[h] = {"hold_rate": float(np.mean([e["outcome"][h]["hold"] for e in done])),
                  "further_median": float(np.median([e["outcome"][h]["further"] for e in done])),
                  "back_median": float(np.median([e["outcome"][h]["back"] for e in done]))}
    return res


def _per_period(events: Sequence[Mapping], periods: Sequence[int], h: Optional[str]) -> tuple:
    """(denominator, numerator) per period: (done, held) for a hold test, (approaches, touched)
    for the touch test (h is None)."""
    pos = {p: k for k, p in enumerate(periods)}
    den, num = np.zeros(len(periods)), np.zeros(len(periods))
    for e in events:
        k = pos[e["period"]]
        if h is None:
            den[k] += 1
            num[k] += bool(e["touched"])
        elif e["touched"] and e["outcome"] is not None:
            den[k] += 1
            num[k] += bool(e["outcome"][h]["hold"])
    return den, num


def _boot_p(real: Sequence[Mapping], ctrl: Sequence[Mapping], h: Optional[str], rng,
            b_reps: int = BOOTSTRAP_B) -> Optional[tuple]:
    """(two-sided bootstrap p-value of rate(real) − rate(control) = 0, its 95% percentile interval),
    resampling periods (multinomial period weights; vectorized). The interval comes from the same
    draws, so adding it changed no p-value."""
    periods = sorted({e["period"] for e in real} | {e["period"] for e in ctrl})
    if len(periods) < MIN_PERIODS:
        return None
    rd, rn = _per_period(real, periods, h)
    cd, cn = _per_period(ctrl, periods, h)
    W = rng.multinomial(len(periods), np.full(len(periods), 1.0 / len(periods)), size=b_reps).astype(np.float64)
    with np.errstate(invalid="ignore", divide="ignore"):
        d = (W @ rn) / (W @ rd) - (W @ cn) / (W @ cd)
    d = d[np.isfinite(d)]
    if d.size < b_reps * 0.9:
        return None
    return (float(min(1.0, 2 * min(np.mean(d <= 0), np.mean(d >= 0)))),
            (float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))))


def holm(pvals: Mapping[Any, Optional[float]]) -> dict:
    items = sorted(((p, k) for k, p in pvals.items() if p is not None), key=lambda x: x[0])
    m = len(items)
    adj: dict = {}
    running = 0.0
    for r, (p, k) in enumerate(items):
        running = max(running, min(1.0, (m - r) * p))
        adj[k] = running
    return adj


def level_reaction_stats(b: Bars, *, seed: int = SEED, bootstrap: int = BOOTSTRAP_B) -> dict:
    """Per level type: touch rate, hold rates after 1h / 4h, typical move further and back, the
    same for the control levels, and a verdict per comparison."""
    raw = _real_and_control(b, seed=seed)
    rng = np.random.default_rng(seed + 1)
    out: dict = {"version": LEVEL_STATS_VERSION, "types": {}, "family_size": 0,
                 "method": {"control": "random levels at the same distance from the period open, "
                                       f"{CONTROLS_PER_PERIOD} per period", "bootstrap": bootstrap,
                            "cluster": "period", "correction": "Holm", "alpha": ALPHA,
                            "materiality": MATERIAL_DIFF, "min_events": MIN_EVENTS,
                            "min_periods": MIN_PERIODS}}
    pvals: dict = {}
    cis: dict = {}
    for typ, d in raw.items():
        real, ctrl = _summ(d["real"]), _summ(d["control"])
        out["types"][typ] = {"period": d["period"], "real": real, "control": ctrl, "verdicts": {}}
        if real["n"] < MIN_EVENTS or real["periods"] < MIN_PERIODS:
            continue
        for test in list(OUTCOME_BARS) + ["touch"]:
            res = _boot_p(d["real"], d["control"], None if test == "touch" else test, rng, bootstrap)
            pvals[(typ, test)] = None if res is None else res[0]
            cis[(typ, test)] = None if res is None else res[1]
    adj = holm(pvals)
    out["family_size"] = len([p for p in pvals.values() if p is not None])
    for typ, rec in out["types"].items():
        real, ctrl = rec["real"], rec["control"]
        for test in list(OUTCOME_BARS) + ["touch"]:
            if (typ, test) not in pvals or pvals[(typ, test)] is None:
                rec["verdicts"][test] = "insufficient"
                continue
            if test == "touch":
                diff = (real["touch_rate"] or 0) - (ctrl["touch_rate"] or 0)
            else:
                diff = real[test]["hold_rate"] - ctrl[test]["hold_rate"]
            rec["verdicts"][test] = "differs" if adj[(typ, test)] < ALPHA and abs(diff) >= MATERIAL_DIFF \
                else "as_usual"
            rec.setdefault("p_holm", {})[test] = round(adj[(typ, test)], 5)
            # the difference's 95% interval (unadjusted), for the quantitative L2 line
            rec.setdefault("ci95", {})[test] = [round(cis[(typ, test)][0], 5), round(cis[(typ, test)][1], 5)]
    return out


def history_view(rec: Mapping[str, Any]) -> dict:
    """The fields of a level type's statistics that a surface or an alert payload carries: both cohorts,
    the verdicts and the differences' 95% intervals (one whitelist for /levels, /check and the alerts)."""
    return {**{k: rec[k] for k in ("real", "control", "verdicts")}, "ci95": rec.get("ci95") or {}}


def stat_type_for(kind: str, side: int) -> Optional[str]:
    """Map a live level kind (and the side it is approached from) to its statistics type."""
    if kind in ("PDH", "PWH", "PMH"):
        return kind if side > 0 else None          # history exists for the approach from below only
    if kind in ("PDL", "PWL", "PML"):
        return kind if side < 0 else None          # … and from above only
    if kind == "ROUND":
        return "ROUND_UP" if side > 0 else "ROUND_DOWN"
    if kind == "POC_PD":
        return "POC_UP" if side > 0 else "POC_DOWN"
    return None


# ---- arbitrary price levels («/check»: what followed touches of similar levels) --------------------
DISTANCE_REACTIONS_VERSION = "BETA_DISTANCE_REACTIONS_V1"
DISTANCE_GRID_PCT = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0)              # = beta.claims.TOUCH_GRID_PCT (test-pinned)
DISTANCE_WINDOW_BARS = 288                                       # a first touch within 24h
_CHUNK = 4000


def distance_reaction_stats(b: Bars, *, stride: int = 12) -> dict:
    """For a price `d` % above (or below) an hourly close, on history: how often it was touched within
    24h and, after its first touch, how often the price stayed beyond it 1h / 4h later with the median
    move further and back. The same measurement as `level_reaction_stats`, for a level with no
    meaning of its own: it is the «обычно» of an arbitrary level. Pure numpy."""
    from .hist_series import forward_extremes
    close_ms = b.times + BAR_MS
    anchors = np.flatnonzero(((close_ms % (stride * BAR_MS)) == 0) & np.isfinite(b.close))
    anchors = anchors[anchors + DISTANCE_WINDOW_BARS < b.n]
    fwd = {h: forward_extremes(b, n) for h, n in OUTCOME_BARS.items()}
    out = {"version": DISTANCE_REACTIONS_VERSION, "window_h": 24, "cells": []}
    if anchors.size == 0:
        return out
    acc = {(d, s): {"n_anchors": 0, "touched": 0, "events": []} for d in DISTANCE_GRID_PCT for s in (1, -1)}
    offs = np.arange(1, DISTANCE_WINDOW_BARS + 1)
    for c0 in range(0, anchors.size, _CHUNK):
        a = anchors[c0:c0 + _CHUNK]
        rows = a[:, None] + offs[None, :]
        hi, lo = b.high[rows], b.low[rows]
        c = b.close[a]
        for d in DISTANCE_GRID_PCT:
            for side in (1, -1):
                lvl = c * (1 + side * d / 100.0)
                hit = (hi >= lvl[:, None]) if side > 0 else (lo <= lvl[:, None])
                hit = np.nan_to_num(hit, nan=0).astype(bool)
                any_hit = hit.any(axis=1)
                rec = acc[(d, side)]
                rec["n_anchors"] += int(a.size)
                rec["touched"] += int(any_hit.sum())
                k = np.argmax(hit, axis=1)
                for ai in np.flatnonzero(any_hit):
                    j = int(a[ai] + 1 + k[ai])
                    o = _outcome(fwd, j, float(lvl[ai]), side)
                    if o is not None:
                        rec["events"].append((int(close_ms[a[ai]] // 86_400_000), o))
    for (d, side), rec in acc.items():
        ev = rec["events"]
        cell = {"distance_pct": d, "side": side, "n_anchors": rec["n_anchors"], "touched": rec["touched"],
                "touch_rate": rec["touched"] / rec["n_anchors"] if rec["n_anchors"] else None, "n": len(ev),
                "days": len({day for day, _o in ev})}
        for h in OUTCOME_BARS:
            cell[h] = None if not ev else {
                "hold_rate": float(np.mean([o[h]["hold"] for _d, o in ev])),
                "further_median": float(np.median([o[h]["further"] for _d, o in ev])),
                "back_median": float(np.median([o[h]["back"] for _d, o in ev]))}
        out["cells"].append(cell)
    return out


def distance_reaction(stats: Optional[Mapping[str, Any]], distance_pct: float) -> Optional[dict]:
    """The cell of the grid distance nearest to |distance_pct| (in log terms) on its side."""
    if not stats or stats.get("version") != DISTANCE_REACTIONS_VERSION or not distance_pct:
        return None
    side = 1 if distance_pct > 0 else -1
    d = abs(float(distance_pct))
    cells = [c for c in stats.get("cells") or () if int(c["side"]) == side]
    if not cells:
        return None
    return min(cells, key=lambda c: abs(math.log(float(c["distance_pct"]) / d)))


# ---- structural first touches (the forecast layer's event; FORECAST_LAYER_DECISION_V1 §3) -----------
# One detector: this is the #352 constructor (scripts/research/level_touch_degradation_v1/events.py,
# `level_instances` → `build_episodes` → touch 1 of `scan_episode`) on the product period rules above.
# tests/beta/test_level_race_parity.py pins it to that constructor. Bars, levels and touches only:
# no outcome is read here.
STRUCTURAL_VERSION = "BETA_STRUCTURAL_TOUCH_V1"
STRUCT_PRIORITY = {k: i for i, k in enumerate(("PMH", "PML", "PWH", "PWL", "PDH", "PDL"))}
STRUCT_SIDE = {"PMH": 1, "PWH": 1, "PDH": 1, "PML": -1, "PWL": -1, "PDL": -1}
STRUCT_FAMILY = {"D": "DAY", "W": "WEEK", "M": "MONTH"}
STRUCT_ZONE_HALF = ZONE_TOL_PCT / 100.0          # #352 primary zone half-width and birth-merge tolerance
RACE_SIGMA_BARS = 288                             # 24h of 5m log returns ending at the bar before the touch
RACE_SIGMA_MIN_PRESENT = 0.9
RACE_CORRIDOR_Z = 1.2816
RACE_BARS = 48                                    # the original 4h window, bars j+1 .. j+48
RACE_BARRIER_FRACTION = 0.5
RACE_X_MIN, RACE_X_MAX = 1e-8, 0.5
T15_OFFSET_BARS = 2                               # T15 = close of bar j+2
# A level can be absorbed only by an episode active at its birth, and an episode lasts at most a calendar
# month: an episode born less than this after the tape's first bar may have lost a host that started
# before the tape. Its event is flagged WINDOW_TOO_SHORT, never silently kept (the live tape is 70 days).
ABSORPTION_LOOKBACK_MS = 32 * 86_400_000


def sigma_at(close: np.ndarray, j: int, *, window: int = RACE_SIGMA_BARS,
             min_frac: float = RACE_SIGMA_MIN_PRESENT) -> float:
    """The std (ddof 1) of the 5m log returns r[j-window .. j-1] (r[k] = log c[k]/c[k-1]): the scale
    known at the close of bar j-1, NaN when fewer than `min_frac` of them are finite. Computed from
    those bars alone, so it does not depend on where the caller's tape starts (#352 takes DH1's
    running sums over its whole surface; the two agree to rounding)."""
    if j - window < 0 or j > close.shape[0]:
        return math.nan
    seg = np.asarray(close[j - window - 1:j] if j > window else np.r_[np.nan, close[:j]], dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.log(seg[1:] / seg[:-1])
    r = r[np.isfinite(r)]
    if r.size < min_frac * window or r.size < 2:
        return math.nan
    return float(np.std(r, ddof=1))


def race_x(sigma: float) -> float:
    """The barrier distance (fraction): half the 80 % corridor half-width of the 4h window."""
    return RACE_BARRIER_FRACTION * RACE_CORRIDOR_Z * float(sigma) * math.sqrt(RACE_BARS)


def structural_levels(b: Bars, *, require_active_complete: bool = False) -> list:
    """Previous-period highs and lows, each active over the next period only. The source period
    must be complete under `_full_period`. #352 also drops a level whose ACTIVE period ends
    incomplete; that is known only after the period, so it is only flagged (`active_complete`,
    False while the period is still running). `require_active_complete` drops such levels before the
    episodes are built, as #352 does on a closed surface: the history parity test only."""
    keys = period_keys(b)
    out = []
    for name, pref, exp in (("day", "D", BARS_PER_DAY), ("week", "W", 7 * BARS_PER_DAY), ("month", "M", None)):
        periods = _period_table(b, keys[name])
        for p in range(1, len(periods)):
            prev, cur = periods[p - 1], periods[p]
            if prev["key"] != cur["key"] - 1 or not _full_period(prev, exp):
                continue
            if require_active_complete and not _full_period(cur, exp):
                continue
            for kind, price in ((f"P{pref}H", prev["high"]), (f"P{pref}L", prev["low"])):
                if not math.isfinite(price) or price <= 0 or not math.isfinite(cur["open"]):
                    continue
                out.append({"kind": kind, "family": STRUCT_FAMILY[pref], "struct_side": STRUCT_SIDE[kind],
                            "price": float(price), "i0": int(cur["first"]), "i1": int(cur["last"]),
                            "source_key": int(prev["key"]), "active_complete": _full_period(cur, exp)})
    return out


def _near_rel(a: float, c: float, tol: float) -> bool:
    lo, hi = (a, c) if a < c else (c, a)
    return lo > 0 and (hi - lo) / lo <= tol


def structural_episodes(b: Bars, levels: Optional[Sequence[Mapping]] = None, *,
                        zone_half: float = STRUCT_ZONE_HALF) -> list:
    """One episode per confluence zone, fixed at birth: levels born together chain-merge within
    `zone_half`; a level born later inside an active zone (or within `zone_half` of its anchor) is
    absorbed and gets no touch of its own. The anchor is the most important member."""
    levels = structural_levels(b) if levels is None else levels
    born: dict = {}
    for lv in levels:
        born.setdefault(int(lv["i0"]), []).append(lv)
    episodes: list = []
    for i0 in sorted(born):
        active = [ep for ep in episodes if ep["i0"] < i0 <= ep["i1"]]
        free = []
        for lv in born[i0]:
            hosts = [ep for ep in active if ep["zone_low"] <= lv["price"] <= ep["zone_high"]
                     or _near_rel(lv["price"], ep["anchor_price"], zone_half)]
            if hosts:
                host = min(hosts, key=lambda ep: (ep["priority"], abs(ep["anchor_price"] - lv["price"])))
                host["absorbed_later"].append(lv["kind"])
            else:
                free.append(lv)
        free.sort(key=lambda r: (r["price"], STRUCT_PRIORITY[r["kind"]], r["kind"]))
        clusters: list = []
        for lv in free:
            if clusters and _near_rel(lv["price"], clusters[-1][-1]["price"], zone_half):
                clusters[-1].append(lv)
            else:
                clusters.append([lv])
        for cl in clusters:
            anchor = min(cl, key=lambda r: (STRUCT_PRIORITY[r["kind"]], r["price"], r["kind"]))
            zlo = min(r["price"] for r in cl) * (1.0 - zone_half)
            zhi = max(r["price"] for r in cl) * (1.0 + zone_half)
            if not (zlo > 0 and zhi > zlo):
                continue
            active_open_ms = int(b.t0 + anchor["i0"] * BAR_MS)
            episodes.append({"event_id": f"{anchor['kind']}:{anchor['source_key']}:{active_open_ms}",
                             "kind": anchor["kind"], "family": anchor["family"],
                             "struct_side": anchor["struct_side"], "priority": STRUCT_PRIORITY[anchor["kind"]],
                             "anchor_price": anchor["price"], "zone_low": float(zlo), "zone_high": float(zhi),
                             "i0": anchor["i0"], "i1": anchor["i1"], "source_key": anchor["source_key"],
                             "active_open_ms": active_open_ms, "member_kinds": [r["kind"] for r in cl],
                             "active_complete": bool(anchor["active_complete"]), "absorbed_later": []})
    return episodes


def _hits(b: Bars, j: int, zlo: float, zhi: float) -> bool:
    hi, lo = b.high[j], b.low[j]
    return bool(np.isfinite(hi) and np.isfinite(lo) and hi >= zlo and lo <= zhi)


def _approach_side(b: Bars, j: int, i0: int, zlo: float, zhi: float) -> int:
    """+1 from below (the far barrier is above), -1 from above, 0 unknown; bars before j only."""
    for k in range(j - 1, i0 - 1, -1):
        if np.isfinite(b.high[k]) and np.isfinite(b.low[k]) and not _hits(b, k, zlo, zhi):
            c = b.close[k]
            if np.isfinite(c) and c < zlo:
                return 1
            if np.isfinite(c) and c > zhi:
                return -1
    if j > 0 and np.isfinite(b.close[j - 1]):
        c = float(b.close[j - 1])
        if c < zlo:
            return 1
        if c > zhi:
            return -1
        return 1 if c <= 0.5 * (zlo + zhi) else -1
    if not np.isfinite(b.open[j]):
        return 0
    return 1 if float(b.open[j]) <= 0.5 * (zlo + zhi) else -1


def structural_first_touches(b: Bars, *, zone_half: float = STRUCT_ZONE_HALF,
                             sigma: Optional[np.ndarray] = None, require_active_complete: bool = False) -> list:
    """Touch 1 of every structural episode in `b` (closed 5m bars only): the first bar of the
    active period whose range meets the zone. Each carries its landmarks (T0 = close of the touch
    bar, T15 = close of bar j+2), the approach side, the scale σ known before the touch, the barrier
    distance X, the upper / lower barrier prices `p_up` / `p_dn` (the one source of the race geometry)
    and the same two as BREAK / REJECT (BREAK beyond the zone in the approach
    direction, REJECT back beyond its near edge; internal names, never user words), and `eligible` with the reason when not. Whether the
    4h window later has enough bars is an outcome-time question and is not decided here.
    `sigma` replaces the scale per bar and `require_active_complete` applies the #352 closed-surface
    drop (tests only)."""
    out = []
    levels = structural_levels(b, require_active_complete=require_active_complete)
    for ep in structural_episodes(b, levels, zone_half=zone_half):
        i0, i1 = ep["i0"], min(ep["i1"], b.n - 1)
        j = next((k for k in range(i0, i1 + 1) if _hits(b, k, ep["zone_low"], ep["zone_high"])), None)
        if j is None:
            continue
        s = sigma_at(b.close, j) if sigma is None else float(sigma[j])
        x = race_x(s) if math.isfinite(s) else math.nan
        usable = bool(math.isfinite(x) and RACE_X_MIN < x < RACE_X_MAX)
        side = _approach_side(b, j, i0, ep["zone_low"], ep["zone_high"])
        brk, rej = (ep["zone_high"] * (1.0 + x), ep["zone_low"] * (1.0 - x)) if side > 0 else \
            (ep["zone_low"] * (1.0 - x), ep["zone_high"] * (1.0 + x))
        touch_ms = int(b.t0 + j * BAR_MS)
        reason = None if usable and side in (1, -1) else ("SIGMA_UNUSABLE" if not usable else "SIDE_UNKNOWN")
        if ep["active_open_ms"] - b.t0 < ABSORPTION_LOOKBACK_MS:
            reason = "WINDOW_TOO_SHORT"
        out.append({**{k: v for k, v in ep.items() if k not in ("i0", "i1", "priority")},
                    "version": STRUCTURAL_VERSION, "zone_half": float(zone_half), "j": int(j),
                    "touch_open_ms": touch_ms, "t0_ms": touch_ms + BAR_MS,
                    "t15_ms": touch_ms + (1 + T15_OFFSET_BARS) * BAR_MS,
                    "window_end_ms": touch_ms + (1 + RACE_BARS) * BAR_MS, "side": int(side),
                    "sigma": s if math.isfinite(s) else None, "x": x if math.isfinite(x) else None,
                    "break_barrier": float(brk) if usable and side else None,
                    "reject_barrier": float(rej) if usable and side else None,
                    "p_up": float(ep["zone_high"] * (1.0 + x)) if usable else None,
                    "p_dn": float(ep["zone_low"] * (1.0 - x)) if usable else None,
                    "eligible": reason is None, "ineligible_reason": reason})
    return out
