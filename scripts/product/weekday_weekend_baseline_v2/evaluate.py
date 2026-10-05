"""WEEKDAY_WEEKEND_BASELINE_UNIT_V2 evaluator (docs/WEEKDAY_WEEKEND_BASELINE_UNIT_V2.md §9).

Offline, single-venue proxy on CORE_BTC_BINANCE_V0 2020-2024 (pinned loader). Reproduces the
production rolling values, mid-rank percentile, 30-day reference and TOD baseline in numpy
(parity-tested against beta.context / analytics.percentile_engine / beta.horizons), then
evaluates the frozen candidates C0-C3. Writes only the result files it is asked to write.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

REPO = Path(__file__).resolve().parents[3]
VERSION = "WEEKDAY_WEEKEND_BASELINE_UNIT_V2_EVAL_V1"
T0 = datetime(2020, 1, 1, tzinfo=timezone.utc)
D0 = date(2020, 1, 1)
BPD = 288                       # 5m buckets per day
REF_BUCKETS = 30 * BPD          # production 30-day reference
CANDIDATES = ("C0", "C1", "C2", "C3")
MATURITY_CUTOFF = date(2020, 7, 6)   # §9.1: availability / common support counted after this date
HIGH, LOW_BAND, HIGH_BAND = 0.95, 0.20, 0.80
METRICS = ("range", "move", "volume")
TOD_METRICS = ("range", "volume")


# ----------------------------------------------------------------------------- data
def to_5m(panel: dict) -> dict:
    t = panel["open_ms"]
    if int(t[0]) != int(T0.timestamp() * 1000) or not np.all(np.diff(t) == 60_000) or len(t) % 5:
        raise RuntimeError("1m panel is not the gapless 2020-01-01 aligned panel")
    o, h, l, c, q = (np.asarray(panel[k], dtype=float) for k in ("open", "high", "low", "close", "quote"))
    return {"o": o[::5].copy(), "h": h.reshape(-1, 5).max(1), "l": l.reshape(-1, 5).min(1),
            "c": c[4::5].copy(), "q": q.reshape(-1, 5).sum(1)}


def rolling(b5: dict, n: int) -> dict:
    """Production rolling_window_values for one venue, at every end bucket j (nan for j < n-1)."""
    N = len(b5["o"])
    out = {m: np.full(N, np.nan) for m in METRICS}
    hmax = sliding_window_view(b5["h"], n).max(1)
    lmin = sliding_window_view(b5["l"], n).min(1)
    o_first = b5["o"][: N - n + 1]
    c_last = b5["c"][n - 1:]
    out["range"][n - 1:] = (hmax - lmin) / o_first * 100.0
    out["move"][n - 1:] = (c_last - o_first) / o_first * 100.0
    cs = np.concatenate([[0.0], np.cumsum(b5["q"])])
    out["volume"][n - 1:] = cs[n:] - cs[: N - n + 1]
    return out


def start_day(j, n: int):
    return (np.asarray(j) - n + 1) // BPD


def is_weekend_day(day_idx) -> np.ndarray:
    return ((np.asarray(day_idx) + D0.weekday()) % 7) >= 5


def mid_rank(ref: np.ndarray, x: float) -> float:
    return (float(np.count_nonzero(ref < x)) + 0.5 * float(np.count_nonzero(ref == x))) / len(ref)


# ----------------------------------------------------------------------------- C3 factor
def iso_week_key(day_idx: int) -> tuple:
    y, w, _ = (D0 + timedelta(days=int(day_idx))).isocalendar()
    return (y, w)


def _wk_int(day_idx: int) -> int:
    y, w = iso_week_key(day_idx)
    return y * 100 + w


def weekend_factors(vals: dict, grid: np.ndarray, n: int) -> dict:
    """{metric: {iso_week: factor or None}} - f_m for windows whose start falls in that ISO week,
    from the 52 most recent earlier ISO weeks with ratios (>= 26), §9.3."""
    sd = start_day(grid, n)
    hour = ((grid - n + 1) % BPD) // 12
    weeks = [iso_week_key(d) for d in sd]
    wd = (sd + D0.weekday()) % 7
    table: dict = {}
    for i, j in enumerate(grid):
        table.setdefault(weeks[i], {}).setdefault(int(hour[i]), {})[int(wd[i])] = i
    ordered = sorted(set(weeks))
    out = {}
    for m in METRICS:
        v = np.abs(vals[m][grid]) if m == "move" else vals[m][grid]
        per_week = {}
        skipped = 0
        for wk in ordered:
            logs = []
            for k, by in table[wk].items():
                wdv = [v[by[d]] for d in range(5) if d in by and np.isfinite(v[by[d]])]
                if len(wdv) < 3:
                    continue
                ref = float(np.median(wdv))
                if ref <= 0:
                    continue
                for d in (5, 6):
                    if d in by and np.isfinite(v[by[d]]):
                        r = v[by[d]] / ref
                        if r > 0:
                            logs.append(math.log(r))
                        else:
                            skipped += 1
            if logs:
                per_week[wk] = logs
        f = {}
        hist = [wk for wk in ordered if wk in per_week]
        for wk in ordered:
            prior = [w for w in hist if w < wk][-52:]
            f[wk] = float(math.exp(np.median(np.concatenate([per_week[w] for w in prior])))) if len(prior) >= 26 else None
        out[m] = {"factor": f, "nonpositive_ratios_skipped": skipped}
    return out


# ----------------------------------------------------------------------------- references
class RefBuilder:
    def __init__(self, n: int, N: int):
        self.n, self.N = n, N
        days = np.arange(N // BPD + 2)
        self.typed = {False: np.flatnonzero(~is_weekend_day(days)), True: np.flatnonzero(is_weekend_day(days))}
        self.sample_we = is_weekend_day(start_day(np.arange(N), n))
        self.sample_day = start_day(np.arange(N), n)

    def indices(self, cand: str, j: int):
        """Reference bucket indices (array or slice) for the window ending at j, or None if unusable."""
        n = self.n
        lo = j - REF_BUCKETS
        T = bool(is_weekend_day(start_day(j, n)))
        if cand in ("C0", "C3"):
            return slice(lo, j) if lo >= n - 1 else None
        if cand == "C1":
            if lo < n - 1:
                return None
            idx = lo + np.flatnonzero(self.sample_we[lo:j] == T)
            days = np.unique(self.sample_day[idx]) if len(idx) else []
            return idx if len(days) >= 8 else None
        if cand == "C2":
            s = int(start_day(j, n))
            typed = self.typed[T]
            p = int(np.searchsorted(typed, s))
            if p >= len(typed) or typed[p] != s or p < 29:
                return None
            first = max(int(typed[p - 29]) * BPD + n - 1, n - 1)
            idx = first + np.flatnonzero(self.sample_we[first:j] == T)
            return idx if len(idx) else None
        raise ValueError(cand)


def rank_all(vals: dict, grid: np.ndarray, n: int, factors: dict) -> dict:
    """{cand: {metric: ranks array (nan = unusable)}} for the evaluated grid."""
    N = len(vals["range"])
    rb = RefBuilder(n, N)
    out = {c: {m: np.full(len(grid), np.nan) for m in METRICS} for c in CANDIDATES}
    we_eval = is_weekend_day(start_day(grid, n))
    weeks = [iso_week_key(d) for d in start_day(grid, n)]
    for i, j in enumerate(grid):
        for cand in CANDIDATES:
            ref_idx = rb.indices(cand, int(j))
            if ref_idx is None:
                continue
            for m in METRICS:
                x = vals[m][j]
                ref = vals[m][ref_idx]
                if cand == "C3":
                    f = factors[m]["factor"].get(weeks[i])
                    if f is None:
                        break
                    sw = rb.sample_we[ref_idx]
                    ref = np.where(sw, ref / f, ref)
                    if we_eval[i]:
                        x = x / f
                if not np.isfinite(x) or np.isnan(ref).any():
                    continue
                out[cand][m][i] = mid_rank(ref, x)
    return out


# ----------------------------------------------------------------------------- TOD
def tod_above(vals: dict, grid: np.ndarray, factors: dict) -> dict:
    """{cand: {metric: 1.0 above / 0.0 not / nan unusable}} for the 1h grid (§9.3 TOD)."""
    n = 12
    out = {c: {m: np.full(len(grid), np.nan) for m in TOD_METRICS} for c in CANDIDATES}
    weeks = [iso_week_key(d) for d in start_day(grid, n)]
    deltas = np.arange(-6, 7)

    def daily(m, j, d):
        idx = j - d * BPD + deltas
        idx = idx[idx >= n - 1]
        if not len(idx):
            return None
        v = vals[m][idx]
        v = v[np.isfinite(v)]
        return float(np.median(v)) if len(v) else None

    for i, j in enumerate(grid):
        j = int(j)
        T = bool(is_weekend_day(start_day(j, n)))
        for m in TOD_METRICS:
            x = vals[m][j]
            if not np.isfinite(x):
                continue
            # C0 / C3 days 1..30
            d30 = [(d, daily(m, j, d)) for d in range(1, 31)]
            d30 = [(d, v) for d, v in d30 if v is not None]
            if len(d30) >= 20:
                out["C0"][m][i] = float(x > np.median([v for _, v in d30]))
                f = factors[m]["factor"].get(weeks[i])
                if f is not None:
                    adj = [v / f if is_weekend_day(start_day(j - d * BPD, n)) else v for d, v in d30]
                    xx = x / f if T else x
                    out["C3"][m][i] = float(xx > np.median(adj))
            c1 = [v for d, v in d30 if bool(is_weekend_day(start_day(j - d * BPD, n))) == T]
            if len(c1) >= 8:
                out["C1"][m][i] = float(x > np.median(c1))
            c2, d = [], 1
            while len(c2) < 30 and j - d * BPD + 6 >= n - 1:
                if bool(is_weekend_day(start_day(j - d * BPD, n))) == T:
                    v = daily(m, j, d)
                    if v is not None:
                        c2.append(v)
                d += 1
            if len(c2) >= 20:
                out["C2"][m][i] = float(x > np.median(c2))
    return out


# ----------------------------------------------------------------------------- statistics
def clustered(x: np.ndarray, groups: np.ndarray) -> tuple:
    """(rate, se) with the G/(G-1) cluster-robust variance of a ratio estimator."""
    N = len(x)
    if N == 0:
        return (None, None)
    E = float(x.mean())
    keys, inv = np.unique(groups, return_inverse=True)
    G = len(keys)
    xs = np.bincount(inv, weights=x)
    ns = np.bincount(inv)
    u = xs - E * ns
    var = (G / (G - 1)) * float((u ** 2).sum()) / N ** 2 if G > 1 else float("nan")
    return (E, math.sqrt(var))


def overdispersion(x: np.ndarray, weeks: np.ndarray) -> float | None:
    keys, inv = np.unique(weeks, return_inverse=True)
    ns = np.bincount(inv)
    keep = ns >= 24
    if keep.sum() < 10:
        return None
    rates = (np.bincount(inv, weights=x) / ns)[keep]
    p = float(x.mean())
    if p <= 0 or p >= 1:
        return None
    expected = math.sqrt(p * (1 - p) / float(ns[keep].mean()))
    return float(rates.std(ddof=1) / expected)


def labels_1h(r: dict) -> dict:
    """Binary label arrays from one candidate's 1h ranks."""
    rng, vol, mv = r["range"], r["volume"], r["move"]
    fr, fv = rng >= HIGH, vol >= HIGH
    fp = (mv >= HIGH) | (mv <= 1 - HIGH)
    return {"flag_range": fr, "flag_volume": fv, "flag_price": fp,
            "qualified": (fr.astype(int) + fv.astype(int) + fp.astype(int)) >= 2,
            "band_range_low": rng <= LOW_BAND, "band_price_up": mv >= HIGH_BAND, "band_price_down": mv <= LOW_BAND}


NOMINAL = {"flag_range": 0.05, "flag_volume": 0.05, "flag_price": 0.10, "band_range_low": 0.20,
           "band_price_up": 0.20, "band_price_down": 0.20, "tod_range": 0.50, "tod_volume": 0.50}
GATE_FLAGS = ("flag_range", "flag_volume", "flag_price")
PS_1H = ("flag_range", "flag_volume", "flag_price", "band_range_low", "band_price_up", "band_price_down")
PS_4H = ("band_range_low", "band_price_up", "band_price_down")
UNDERFLAG_TOL = {"flag_range": 0.02, "flag_volume": 0.02, "flag_price": 0.02, "band_range_low": 0.04,
                 "band_price_up": 0.04, "band_price_down": 0.04, "tod_range": 0.04, "tod_volume": 0.04}


def evaluate(panel: dict, *, progress=None) -> dict:
    b5 = to_5m(panel)
    N = len(b5["o"])
    surfaces = {}
    meta = {}
    for name, n in (("1h", 12), ("4h", 48)):
        vals = rolling(b5, n)
        grid = np.arange(n - 1, N)
        grid = grid[(grid + 1) % n == 0]
        factors = weekend_factors(vals, grid, n)
        ranks = rank_all(vals, grid, n, factors)
        sd = start_day(grid, n)
        surfaces[name] = {"grid": grid, "ranks": ranks, "sd": sd, "we": is_weekend_day(sd), "vals": vals}
        meta[name] = {"factor_skipped": {m: factors[m]["nonpositive_ratios_skipped"] for m in METRICS},
                      "factors_by_year": _factor_summary(factors, sd)}
        if name == "1h":
            surfaces[name]["tod"] = tod_above(vals, grid, factors)
        if progress:
            progress(f"{name} done")
    return summarize(surfaces, meta)


def _factor_summary(factors: dict, sd: np.ndarray) -> dict:
    out = {}
    for m in METRICS:
        f = factors[m]["factor"]
        by = {}
        for wk, v in f.items():
            if v is not None:
                by.setdefault(str(wk[0]), []).append(v)
        out[m] = {y: round(float(np.median(v)), 4) for y, v in sorted(by.items())}
    return out


def summarize(surfaces: dict, meta: dict) -> dict:
    s1, s4 = surfaces["1h"], surfaces["4h"]
    cutoff = (MATURITY_CUTOFF - D0).days
    res = {"VERSION": VERSION, "META": meta, "CANDIDATES": {}}

    def usable(s, c, keys):
        return np.all([np.isfinite(s["ranks"][c][m]) for m in keys], axis=0)

    cs1 = np.all([usable(s1, c, METRICS) for c in CANDIDATES], axis=0)
    cs4 = np.all([usable(s4, c, METRICS) for c in CANDIDATES], axis=0)
    tod_cs = np.all([np.isfinite(s1["tod"][c][m]) for c in CANDIDATES for m in TOD_METRICS], axis=0)
    after1, after4 = s1["sd"] >= cutoff, s4["sd"] >= cutoff
    res["SUPPORT"] = {
        "1h_hours": int(len(s1["grid"])), "1h_common": int(cs1.sum()), "4h_windows": int(len(s4["grid"])),
        "4h_common": int(cs4.sum()), "tod_common": int(tod_cs.sum()),
        "first_common_1h": str(D0 + timedelta(days=int(s1["sd"][cs1].min()))) if cs1.any() else None,
        "common_share_after_cutoff": {
            st: round(float(cs1[after1 & (s1["we"] == (st == "WEEKEND"))].mean()), 4) for st in ("WEEKDAY", "WEEKEND")},
    }
    strata = {"WEEKDAY": ~s1["we"], "WEEKEND": s1["we"], "ALL": np.ones(len(s1["grid"]), bool)}
    strata4 = {"WEEKDAY": ~s4["we"], "WEEKEND": s4["we"], "ALL": np.ones(len(s4["grid"]), bool)}
    years1 = np.array([(D0 + timedelta(days=int(d))).year for d in s1["sd"]])
    years4 = np.array([(D0 + timedelta(days=int(d))).year for d in s4["sd"]])
    weeks1 = np.array([_wk_int(int(d)) for d in s1["sd"]])
    weeks4 = np.array([_wk_int(int(d)) for d in s4["sd"]])

    def stat(x, mask, days, weeks):
        r, se_d = clustered(x[mask].astype(float), days[mask])
        _, se_w = clustered(x[mask].astype(float), weeks[mask])
        return r, max(se_d, se_w) if se_d is not None and se_w is not None else None

    base1 = labels_1h(s1["ranks"]["C0"])
    base4 = labels_1h(s4["ranks"]["C0"])
    for c in CANDIDATES:
        L1 = labels_1h(s1["ranks"][c])
        L4 = labels_1h(s4["ranks"][c])
        tod = {f"tod_{m}": s1["tod"][c][m] == 1.0 for m in TOD_METRICS}
        out = {"GAPS": {}, "YEARS": {}, "SE": {}}
        # calibration gaps on common support
        for st in ("WEEKDAY", "WEEKEND", "ALL"):
            for key in PS_1H:
                r, se = stat(L1[key], cs1 & strata[st], s1["sd"], weeks1)
                out["GAPS"][f"1h:{key}:{st}"] = r - NOMINAL[key]
                out["SE"][f"1h:{key}:{st}"] = se
            for key in GATE_FLAGS + PS_4H:
                r, se = stat(L4[key], cs4 & strata4[st], s4["sd"], weeks4)
                out["GAPS"][f"4h:{key}:{st}"] = r - NOMINAL[key]
                out["SE"][f"4h:{key}:{st}"] = se
            for key in tod:
                r, se = stat(tod[key], tod_cs & strata[st], s1["sd"], weeks1)
                out["GAPS"][f"tod:{key}:{st}"] = r - NOMINAL[key]
                out["SE"][f"tod:{key}:{st}"] = se
            q, qse = stat(L1["qualified"], cs1 & strata[st], s1["sd"], weeks1)
            out.setdefault("GATE_U", {})[st] = q
            out.setdefault("GATE_U_SE", {})[st] = qse
        out["GATE_IMBALANCE"] = out["GATE_U"]["WEEKEND"] - out["GATE_U"]["WEEKDAY"]
        ps_keys = ([f"1h:{k}" for k in PS_1H] + [f"4h:{k}" for k in PS_4H] + [f"tod:{k}" for k in tod])
        out["P_S"] = max(abs(out["GAPS"][f"{k}:{st}"]) for k in ps_keys for st in ("WEEKDAY", "WEEKEND"))
        out["P_S_ARGMAX"] = max(((abs(out["GAPS"][f"{k}:{st}"]), f"{k}:{st}") for k in ps_keys
                                 for st in ("WEEKDAY", "WEEKEND")))[1]
        # by year
        for y in range(2020, 2025):
            gaps = {}
            for st in ("WEEKDAY", "WEEKEND"):
                for key in PS_1H:
                    m = cs1 & strata[st] & (years1 == y)
                    if m.sum():
                        gaps[f"1h:{key}:{st}"] = float(L1[key][m].mean()) - NOMINAL[key]
                for key in PS_4H:
                    m = cs4 & strata4[st] & (years4 == y)
                    if m.sum():
                        gaps[f"4h:{key}:{st}"] = float(L4[key][m].mean()) - NOMINAL[key]
                for key in tod:
                    m = tod_cs & strata[st] & (years1 == y)
                    if m.sum():
                        gaps[f"tod:{key}:{st}"] = float(tod[key][m].mean()) - NOMINAL[key]
            if gaps:
                out["YEARS"][str(y)] = {"P_S": max(abs(v) for v in gaps.values()),
                                        "weekend_gate_flags": {k: round(gaps.get(f"1h:{k}:WEEKEND", float("nan")), 4) for k in GATE_FLAGS},
                                        "weekday_gate_flags": {k: round(gaps.get(f"1h:{k}:WEEKDAY", float("nan")), 4) for k in GATE_FLAGS}}
        # label switch / rank change vs C0
        any1 = np.zeros(len(s1["grid"]), bool)
        for key in ("flag_range", "flag_volume", "qualified", "band_range_low"):
            any1 |= L1[key] != base1[key]
        price_c = np.where(L1["flag_price"], np.sign(s1["ranks"][c]["move"] - 0.5), 0)
        price_0 = np.where(base1["flag_price"], np.sign(s1["ranks"]["C0"]["move"] - 0.5), 0)
        band_c = np.where(L1["band_price_up"], 1, np.where(L1["band_price_down"], -1, 0))
        band_0 = np.where(base1["band_price_up"], 1, np.where(base1["band_price_down"], -1, 0))
        any1 |= (price_c != price_0) | (band_c != band_0)
        b4c = np.where(L4["band_price_up"], 1, np.where(L4["band_price_down"], -1, 0))
        b40 = np.where(base4["band_price_up"], 1, np.where(base4["band_price_down"], -1, 0))
        any4 = (L4["band_range_low"] != base4["band_range_low"]) | (b4c != b40)
        tod0 = {f"tod_{m}": s1["tod"]["C0"][m] == 1.0 for m in TOD_METRICS}
        anyt = np.zeros(len(s1["grid"]), bool)
        for k in tod:
            anyt |= tod[k] != tod0[k]
        out["LABEL_SWITCH"] = {st: {"1h": float(any1[cs1 & strata[st]].mean()),
                                    "4h_bands": float(any4[cs4 & strata4[st]].mean()),
                                    "tod": float(anyt[tod_cs & strata[st]].mean())} for st in ("WEEKDAY", "WEEKEND")}
        out["RANK_CHANGE"] = {st: {m: float(np.nanmean(np.abs(s1["ranks"][c][m] - s1["ranks"]["C0"][m])[cs1 & strata[st]]))
                                   for m in METRICS} for st in ("WEEKDAY", "WEEKEND")}
        # availability after cutoff (own support)
        own = usable(s1, c, METRICS)
        out["AVAILABILITY_AFTER_CUTOFF"] = {st: float(own[after1 & strata[st]].mean()) for st in ("WEEKDAY", "WEEKEND")}
        out["OWN_SUPPORT_FIRST_DAY"] = str(D0 + timedelta(days=int(s1["sd"][own].min()))) if own.any() else None
        # overdispersion of weekend gate flags
        out["OVERDISPERSION_WEEKEND"] = {k: overdispersion(L1[k][cs1 & s1["we"]].astype(float), weeks1[cs1 & s1["we"]])
                                         for k in GATE_FLAGS}
        # pairwise support vs C0 (secondary)
        pair = usable(s1, c, METRICS) & usable(s1, "C0", METRICS)
        out["PAIRWISE_WITH_C0_1h"] = {
            "hours": int(pair.sum()),
            "first_day": str(D0 + timedelta(days=int(s1["sd"][pair].min()))) if pair.any() else None,
            "weekend_gate_flags": {k: float(L1[k][pair & s1["we"]].mean()) - NOMINAL[k] for k in GATE_FLAGS},
            "weekday_gate_flags": {k: float(L1[k][pair & ~s1["we"]].mean()) - NOMINAL[k] for k in GATE_FLAGS}}
        res["CANDIDATES"][c] = out
    res["INFORMATION"] = _information(s1, cs1)
    res["DECISION"] = decide(res)
    return res


def _information(s1: dict, cs1: np.ndarray) -> dict:
    n = 12
    N = len(s1["vals"]["range"])
    rb = RefBuilder(n, N)
    out = {}
    sample = s1["grid"][cs1][:: max(1, int(cs1.sum()) // 400)]
    for c in CANDIDATES:
        for st, want in (("WEEKDAY", False), ("WEEKEND", True)):
            sizes, days = [], []
            for j in sample:
                if bool(is_weekend_day(start_day(j, n))) != want:
                    continue
                idx = rb.indices(c, int(j))
                arr = np.arange(N)[idx] if isinstance(idx, slice) else idx
                sizes.append(len(arr))
                days.append(len(np.unique(rb.sample_day[arr])))
                lookback = (int(start_day(j, n)) - int(rb.sample_day[arr].min()))
                days[-1] = (days[-1], lookback)
            out[f"{c}:{st}"] = {"median_reference_samples": int(np.median(sizes)),
                                "median_reference_dates": int(np.median([d[0] for d in days])),
                                "median_lookback_days": int(np.median([d[1] for d in days]))}
    weeks = len({iso_week_key(int(d)) for d in s1["sd"][cs1]})
    out["COMMON_SUPPORT_1H"] = {"WEEKDAY_hours": int((cs1 & ~s1["we"]).sum()), "WEEKEND_hours": int((cs1 & s1["we"]).sum()),
                                "WEEKDAY_dates": int(len(np.unique(s1["sd"][cs1 & ~s1["we"]]))),
                                "WEEKEND_dates": int(len(np.unique(s1["sd"][cs1 & s1["we"]]))), "ISO_weeks": weeks}
    return out


def decide(res: dict) -> dict:
    C = res["CANDIDATES"]
    c0 = C["C0"]
    elig, reasons = {}, {}
    for c in CANDIDATES:
        x, r = C[c], []
        for st in ("WEEKDAY", "WEEKEND"):
            if x["AVAILABILITY_AFTER_CUTOFF"][st] < c0["AVAILABILITY_AFTER_CUTOFF"][st] - 0.05:
                r.append(f"availability {st}")
        for k, g in x["GAPS"].items():
            if k.endswith(":ALL") or k.startswith("4h:flag"):
                continue
            key = k.split(":")[1]
            if g < -UNDERFLAG_TOL[key]:
                r.append(f"under-flag {k} {g:+.4f}")
            if k.endswith(":WEEKDAY") and abs(g) > abs(c0["GAPS"][k]) + 0.005:
                r.append(f"weekday worse {k}")
        for y, yv in x["YEARS"].items():
            if yv["P_S"] > c0["YEARS"][y]["P_S"] + 0.01:
                r.append(f"YEAR {y} P_S {yv['P_S']:.4f} vs C0 {c0['YEARS'][y]['P_S']:.4f}")
        for k, v in x["OVERDISPERSION_WEEKEND"].items():
            v0 = c0["OVERDISPERSION_WEEKEND"][k]
            if v is not None and v0 is not None and v > 1.25 * v0:
                r.append(f"OVERDISPERSION {k} {v:.2f} vs C0 {v0:.2f}")
        if abs(x["GATE_IMBALANCE"]) > abs(c0["GATE_IMBALANCE"]) + 1e-12:
            r.append("gate imbalance larger than C0")
        elig[c], reasons[c] = (not r), r
    order = ("C0", "C3", "C1", "C2")
    eligible = [c for c in order if elig[c]]
    best = min(eligible, key=lambda c: C[c]["P_S"]) if eligible else "C0"
    for c in order:                                   # simpler within 0.5 pp
        if c in eligible and C[c]["P_S"] <= C[best]["P_S"] + 0.005:
            best = c
            break
    improve = c0["P_S"] - C[best]["P_S"]
    robust_only = [c for c in CANDIDATES if c != "C0" and not elig[c] and c0["P_S"] - C[c]["P_S"] >= 0.01
                   and all(s.startswith(("YEAR", "OVERDISPERSION")) for s in reasons[c])]
    support_ok = all(v >= 0.90 for v in res["SUPPORT"]["common_share_after_cutoff"].values())
    if not support_ok:
        rec = "INSUFFICIENT_TO_CHANGE"
    elif best != "C0" and improve >= 0.01:
        rec = f"CHANGE_BASELINE ({best})"
    elif robust_only:
        rec = "INSUFFICIENT_TO_CHANGE"
    else:
        rec = "KEEP_CURRENT"
    return {"ELIGIBLE": elig, "INELIGIBLE_REASONS": reasons, "PROPOSAL": best, "P_S_IMPROVEMENT_VS_C0": improve,
            "IMPROVES_BUT_NOT_ROBUST": robust_only, "SUPPORT_OK": support_ok, "RECOMMENDATION": rec}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "docs/WEEKDAY_WEEKEND_BASELINE_UNIT_V2_RESULT.json"))
    a = ap.parse_args()
    from scripts.research.owner_cards_r03 import data as R03
    panel = R03.load_btc_1m()
    res = evaluate(panel, progress=lambda s: print(s, flush=True))
    res["DATA"] = {"DATASET": "CORE_BTC_BINANCE_V0", "LOADER": "scripts/research/owner_cards_r03/data.py::load_btc_1m",
                   "PINNED_DIGEST": R03.btc_dataset_digest(), "ROWS_1M": int(len(panel["open_ms"])),
                   "WINDOW": "2020-01-01..2024-12-31", "PROXY": "PROXY_SINGLE_VENUE (Binance)"}
    res["EVALUATOR_SHA256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True, default=_json) + "\n")
    print(json.dumps(res["DECISION"], indent=1, default=_json))


def _json(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


if __name__ == "__main__":
    main()
