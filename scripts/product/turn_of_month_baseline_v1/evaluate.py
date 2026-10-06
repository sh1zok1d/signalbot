"""TURN_OF_MONTH_BASELINE_UNIT_V1 evaluator (docs/TURN_OF_MONTH_BASELINE_UNIT_V1.md §4, §6, §8).

Offline, single-venue proxy on CORE_BTC_BINANCE_V0 2020-2024 (pinned loader). Imports read-only:
the frozen weekday/weekend V2 evaluator (values, ranks, C0/C1 references, TOD, labels, clustered
rates), G01's turn-of-month day sets, the R03 loader and R03's sign-flip / moving-block inference.
Part B: label calibration on TOM vs MID windows under C1 (primary) and C0. Part A: day-level
participation and range shift. Writes only the result file it is asked to write.

Implementation readings of the design note, fixed in code before any outcome is read:
- calendar: G01 `tom_state_days` / `comparator_days` on [2020-01-31, 2025-01-01) (§5), so a
  month m contributes TOM days only if they fall on or after 2020-01-31; this gives the 58 month
  units with both sets and the 826 MID days of §5. Both parts use this calendar;
- Part B rates pool every usable window of a set (a MID-only month adds MID windows); the
  month-clustered SE counts every month with a usable window in either set (G), t uses G - 1;
- Part A z uses ddof = 1 (R03 `outcomes.standardize`); the moving-block SE uses R03's 2000 draws
  and the note's seed 20261005, months in calendar order.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from scripts.product.weekday_weekend_baseline_v2 import evaluate as WW
from scripts.research.autogen_g01 import states as G01

REPO = Path(__file__).resolve().parents[3]
VERSION = "TURN_OF_MONTH_BASELINE_UNIT_V1_EVAL_V1"
DESIGN_NOTE = "docs/TURN_OF_MONTH_BASELINE_UNIT_V1.md"
DAY_MS = 86_400_000
MATURITY = dt.date(2020, 1, 31)              # C0 / C1 / 24h maturity (§4); calendar start (§5)
SURFACE_END = dt.date(2025, 1, 1)            # exclusive
YEARS = (2020, 2021, 2022, 2023, 2024)
CONSTRUCTIONS = ("C1", "C0")                  # C1 decides; C0 reported with the same rule
SETS = ("TOM", "MID")
H24 = 288
PRIOR_DAYS, MATURE_DAYS = 30, 20               # beta.horizons _PRIOR_DAYS / _MATURE_DAYS
SIGNFLIP_DRAWS, SEED = 20000, 20261005
BLOCK_MONTHS, BLOCK_DRAWS = 3, 2000
PART_A_OUTCOMES = ("log_quote_volume", "log_trade_count", "log_range")
PART_A_MATERIAL_SD = 0.15
YEARS_SAME_SIGN = 4

# (family, label) -> nominal, tolerance. 13 decision labels (§4, §6); the gate is reported only.
DECISION_LABELS = {
    "1h:flag_range": (0.05, 0.02), "1h:flag_volume": (0.05, 0.02), "1h:flag_price": (0.10, 0.02),
    "1h:band_range_low": (0.20, 0.04), "1h:band_price_up": (0.20, 0.04), "1h:band_price_down": (0.20, 0.04),
    "4h:band_range_low": (0.20, 0.04), "4h:band_price_up": (0.20, 0.04), "4h:band_price_down": (0.20, 0.04),
    "tod:range": (0.50, 0.04), "tod:volume": (0.50, 0.04),
    "24h:range": (0.50, 0.04), "24h:volume": (0.50, 0.04),
}
REPORTED_ONLY = ("1h:qualified",)


# ----------------------------------------------------------------------------- t quantile
def _betacf(a: float, b: float, x: float) -> float:
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(1.0 + aa / c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(1.0 + aa / c) > 1e-300 else 1e-300
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x)
    if x < (a + 1.0) / (a + b + 2.0):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: int) -> float:
    tail = 0.5 * _betainc(df / 2.0, 0.5, df / (df + t * t))
    return 1.0 - tail if t >= 0 else tail


def t_crit(df: int, q: float = 0.975) -> float:
    """Student-t quantile by bisection on the CDF (scipy is not a dependency)."""
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if t_cdf(mid, df) < q:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ----------------------------------------------------------------------------- calendar
def _ms(d: dt.date) -> int:
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000)


def calendar(start: dt.date = MATURITY, end: dt.date = SURFACE_END) -> dict:
    """date -> (set, month unit 'YYYY-MM') from G01's day functions, unchanged."""
    s, e = _ms(start), _ms(end)
    out: dict[dt.date, tuple[str, str]] = {}
    for y, m in G01._months(_ms(dt.date(start.year, start.month, 1)), e):
        unit = f"{y}-{m:02d}"
        for d in G01.tom_state_days(y, m, s, e):
            out[d] = ("TOM", unit)
        for d in G01.comparator_days(y, m, s, e):
            if d in out:
                raise RuntimeError(f"{d} in both sets")
            out[d] = ("MID", unit)
    return out


def day_index(d: dt.date) -> int:
    return (d - WW.D0).days


def type_days(day_idx: np.ndarray, cal: dict) -> tuple[np.ndarray, np.ndarray]:
    """(set array: 'TOM' / 'MID' / '', unit array 'YYYY-MM' / '') for day indices from D0."""
    by_idx = {day_index(d): v for d, v in cal.items()}
    sets = np.array([by_idx.get(int(i), ("", ""))[0] for i in day_idx])
    units = np.array([by_idx.get(int(i), ("", ""))[1] for i in day_idx])
    return sets, units


# ----------------------------------------------------------------------------- Part B values
def clock_grid(N: int, n: int) -> np.ndarray:
    grid = np.arange(n - 1, N)
    return grid[(grid + 1) % n == 0]


def ranks_c0_c1(vals: dict, grid: np.ndarray, n: int, N: int) -> tuple[dict, dict]:
    """({cand: {metric: ranks}}, {cand: (ref_samples, ref_dates)}) for C0 / C1 only."""
    rb = WW.RefBuilder(n, N)
    out = {c: {m: np.full(len(grid), np.nan) for m in WW.METRICS} for c in CONSTRUCTIONS}
    size = {c: (np.full(len(grid), np.nan), np.full(len(grid), np.nan)) for c in CONSTRUCTIONS}
    for i, j in enumerate(grid):
        for c in CONSTRUCTIONS:
            idx = rb.indices(c, int(j))
            if idx is None:
                continue
            arr = np.arange(N)[idx] if isinstance(idx, slice) else idx
            size[c][0][i] = len(arr)
            size[c][1][i] = len(np.unique(rb.sample_day[arr]))
            for m in WW.METRICS:
                ref = vals[m][idx]
                x = vals[m][j]
                if np.isfinite(x) and not np.isnan(ref).any():
                    out[c][m][i] = WW.mid_rank(ref, x)
    return out, size


def tod_ref_days(grid: np.ndarray, n: int = 12) -> dict:
    """Number of reference days in the TOD baseline: C0 = days 1..30, C1 = same-type among them."""
    T = WW.is_weekend_day(WW.start_day(grid, n))
    c1 = np.zeros(len(grid))
    for d in range(1, 31):
        c1 += WW.is_weekend_day(WW.start_day(grid - d * WW.BPD, n)) == T
    return {"C0": np.full(len(grid), 30.0), "C1": c1}


def h24_above(b5: dict, day_idx: np.ndarray) -> dict:
    """{metric: 1.0 / 0.0 / nan} per UTC day D: production rolling 24h value of D against the
    _baseline_24h median of the 30 prior days' values (>= 20), evaluated at D+1 00:00."""
    v = WW.rolling(b5, H24)
    out = {"range": np.full(len(day_idx), np.nan), "volume": np.full(len(day_idx), np.nan)}
    for i, d in enumerate(day_idx):
        j = (int(d) + 1) * H24 - 1
        if j >= len(v["range"]):
            continue
        for m in out:
            prior = [v[m][j - k * H24] for k in range(1, PRIOR_DAYS + 1) if j - k * H24 >= H24 - 1]
            prior = [p for p in prior if np.isfinite(p)]
            if len(prior) >= MATURE_DAYS and np.isfinite(v[m][j]):
                out[m][i] = float(v[m][j] > float(np.median(prior)))
    return out


# ----------------------------------------------------------------------------- Part B statistics
def diff_se(x: np.ndarray, is_tom: np.ndarray, groups: np.ndarray) -> tuple:
    """(D = r_TOM - r_MID, cluster-robust SE with G/(G-1), G) from per-cluster linearized
    contributions of both sets."""
    xt, xm = x[is_tom], x[~is_tom]
    if not len(xt) or not len(xm):
        return (None, None, 0)
    rt, rm = float(xt.mean()), float(xm.mean())
    phi = np.where(is_tom, (x - rt) / len(xt), -(x - rm) / len(xm))
    keys, inv = np.unique(groups, return_inverse=True)
    G = len(keys)
    U = np.bincount(inv, weights=phi)
    var = (G / (G - 1)) * float((U ** 2).sum()) if G > 1 else float("nan")
    return (rt - rm, math.sqrt(var), G)


def label_status(lo: float, hi: float, tol: float, yearly: dict, d: float) -> str:
    if lo >= -tol and hi <= tol:
        return "WITHIN_TOLERANCE"
    sign = 1 if lo > tol else (-1 if hi < -tol else 0)
    if sign:
        same = sum(1 for v in yearly.values() if v is not None and np.sign(v) == sign)
        if same >= YEARS_SAME_SIGN:
            return "BEYOND_TOLERANCE"
    return "NOT_RESOLVED"


def evaluate_label(x: np.ndarray, usable: np.ndarray, sets: np.ndarray, units: np.ndarray,
                   dates: np.ndarray, nominal: float | None, tol: float | None) -> dict:
    keep = usable & (sets != "")
    x = x[keep].astype(float)
    st, un, da = sets[keep], units[keep], dates[keep]
    is_tom = st == "TOM"
    D, se_m, G = diff_se(x, is_tom, un)
    _, se_d, Gd = diff_se(x, is_tom, da)
    se = max(se_m, se_d)
    t = t_crit(G - 1)
    lo, hi = D - t * se, D + t * se
    years = np.array([int(u[:4]) for u in un])
    yearly = {}
    for y in YEARS:
        my = years == y
        if (my & is_tom).any() and (my & ~is_tom).any():
            yearly[str(y)] = float(x[my & is_tom].mean() - x[my & ~is_tom].mean())
        else:
            yearly[str(y)] = None
    gaps = {}
    for s in SETS:
        m = st == s
        r, se_sm = WW.clustered(x[m], un[m])
        _, se_sd = WW.clustered(x[m], da[m])
        gs = len(np.unique(un[m]))
        ts = t_crit(gs - 1)
        sse = max(se_sm, se_sd)
        gap = None if nominal is None else r - nominal
        gaps[s] = {"N": int(m.sum()), "MONTHS": gs, "RATE": r, "SE": sse,
                   "GAP_TO_NOMINAL": gap,
                   "GAP_CI95": None if nominal is None else [gap - ts * sse, gap + ts * sse]}
    per_month = {}
    for u in np.unique(un):
        mu = un == u
        per_month[str(u)] = {s: [int((mu & (st == s)).sum()), int(x[mu & (st == s)].sum())] for s in SETS}
    out = {"D": D, "SE_MONTH": se_m, "SE_DATE": se_d, "SE": se, "G_MONTHS": G, "G_DATES": Gd,
           "T_CRIT": t, "CI95": [lo, hi], "YEARLY_D": yearly, "SETS": gaps,
           "N_TOM": int(is_tom.sum()), "N_MID": int((~is_tom).sum()), "PER_MONTH_N_SUM": per_month}
    if tol is not None:
        out["TOLERANCE"] = tol
        out["STATUS"] = label_status(lo, hi, tol, yearly, D)
    return out


def part_b(panel: dict, cal: dict, *, progress=None) -> dict:
    b5 = WW.to_5m(panel)
    N = len(b5["o"])
    mature = day_index(MATURITY)
    res = {"LABELS": {c: {} for c in CONSTRUCTIONS}, "AVAILABILITY": {}, "REFERENCE_SIZE": {},
           "LABEL_SWITCH_TOM": {}}
    labels_by = {c: {} for c in CONSTRUCTIONS}
    usable_by = {c: {} for c in CONSTRUCTIONS}
    typing = {}
    for name, n in (("1h", 12), ("4h", 48)):
        vals = WW.rolling(b5, n)
        grid = clock_grid(N, n)
        sd = WW.start_day(grid, n)
        sets, units = type_days(sd, cal)
        sel = (sets != "") & (sd >= mature)
        grid, sd, sets, units = grid[sel], sd[sel], sets[sel], units[sel]
        typing[name] = (sets, units, sd)
        ranks, size = ranks_c0_c1(vals, grid, n, N)
        for c in CONSTRUCTIONS:
            usable = np.all([np.isfinite(ranks[c][m]) for m in WW.METRICS], axis=0)
            L = WW.labels_1h(ranks[c])
            keys = ("flag_range", "flag_volume", "flag_price", "qualified",
                    "band_range_low", "band_price_up", "band_price_down") if name == "1h" else \
                ("band_range_low", "band_price_up", "band_price_down")
            for k in keys:
                labels_by[c][f"{name}:{k}"] = L[k]
                usable_by[c][f"{name}:{k}"] = usable
            res["AVAILABILITY"][f"{name}:{c}"] = {s: float(usable[sets == s].mean()) for s in SETS}
            res["REFERENCE_SIZE"][f"{name}:{c}"] = {
                s: {"median_samples": float(np.nanmedian(size[c][0][sets == s])),
                    "median_dates": float(np.nanmedian(size[c][1][sets == s]))} for s in SETS}
        if name == "1h":
            tod = WW.tod_above(vals, grid, {m: {"factor": {}} for m in WW.METRICS})
            td = tod_ref_days(grid)
            for c in CONSTRUCTIONS:
                for m in WW.TOD_METRICS:
                    labels_by[c][f"tod:{m}"] = tod[c][m] == 1.0
                    usable_by[c][f"tod:{m}"] = np.isfinite(tod[c][m])
                res["AVAILABILITY"][f"tod:{c}"] = {
                    s: float(np.all([np.isfinite(tod[c][m]) for m in WW.TOD_METRICS], axis=0)[sets == s].mean())
                    for s in SETS}
                res["REFERENCE_SIZE"][f"tod:{c}"] = {s: {"median_dates": float(np.median(td[c][sets == s]))}
                                                      for s in SETS}
        if progress:
            progress(f"{name} done")
    # 24h: one window per typed day; identical under C0 and C1 (§3)
    days = np.array(sorted(day_index(d) for d in cal if d >= MATURITY))
    sets24, units24 = type_days(days, cal)
    a24 = h24_above(b5, days)
    typing["24h"] = (sets24, units24, days)
    for c in CONSTRUCTIONS:
        for m in ("range", "volume"):
            labels_by[c][f"24h:{m}"] = a24[m] == 1.0
            usable_by[c][f"24h:{m}"] = np.isfinite(a24[m])
        res["AVAILABILITY"][f"24h:{c}"] = {
            s: float((np.isfinite(a24["range"]) & np.isfinite(a24["volume"]))[sets24 == s].mean()) for s in SETS}
    res["REFERENCE_SIZE"]["24h"] = {"prior_days": PRIOR_DAYS, "min_days": MATURE_DAYS}
    # evaluate every label
    for c in CONSTRUCTIONS:
        for key in list(DECISION_LABELS) + list(REPORTED_ONLY):
            fam = key.split(":")[0]
            sets, units, sd = typing["1h" if fam == "tod" else fam]
            nominal, tol = DECISION_LABELS.get(key, (None, None))
            res["LABELS"][c][key] = evaluate_label(labels_by[c][key], usable_by[c][key], sets, units, sd,
                                                   nominal, tol)
    # label switch C1 vs C0 on TOM windows usable under both
    fams = {"1h": [k for k in labels_by["C1"] if k.startswith("1h:")],
            "4h": [k for k in labels_by["C1"] if k.startswith("4h:")],
            "tod": [k for k in labels_by["C1"] if k.startswith("tod:")],
            "24h": [k for k in labels_by["C1"] if k.startswith("24h:")]}
    for fam, keys in fams.items():
        sets = typing["1h" if fam == "tod" else fam][0]
        both = np.all([usable_by["C1"][k] & usable_by["C0"][k] for k in keys], axis=0) & (sets == "TOM")
        diff = np.any([labels_by["C1"][k] != labels_by["C0"][k] for k in keys], axis=0)
        res["LABEL_SWITCH_TOM"][fam] = {"N": int(both.sum()), "RATE": float(diff[both].mean()) if both.any() else None}
    res["WINDOWS"] = {fam: {s: int((typing[fam][0] == s).sum()) for s in SETS} for fam in typing}
    res["DECISION"] = decide(res)
    return res


def decide(res: dict) -> dict:
    status = {c: {k: res["LABELS"][c][k]["STATUS"] for k in DECISION_LABELS} for c in CONSTRUCTIONS}
    beyond = [k for k, s in status["C1"].items() if s == "BEYOND_TOLERANCE"]
    return {
        "PRIMARY": "C1",
        "STATUS_C1": status["C1"], "STATUS_C0_REPORTED_ONLY": status["C0"],
        "BEYOND_TOLERANCE_C1": beyond,
        "WITHIN_TOLERANCE_C1": [k for k, s in status["C1"].items() if s == "WITHIN_TOLERANCE"],
        "NOT_RESOLVED_C1": [k for k, s in status["C1"].items() if s == "NOT_RESOLVED"],
        "RECOMMENDATION": "PROPOSE_CORRECTION_UNIT" if beyond else "NO_CHANGE",
    }


# ----------------------------------------------------------------------------- Part A
def daily_metrics(panel: dict, trades: np.ndarray) -> dict:
    t = panel["open_ms"]
    if len(t) % 1440 or int(t[0]) != _ms(WW.D0):
        raise RuntimeError("panel is not whole UTC days from 2020-01-01")
    h = np.asarray(panel["high"]).reshape(-1, 1440).max(1)
    lo = np.asarray(panel["low"]).reshape(-1, 1440).min(1)
    q = np.asarray(panel["quote"]).reshape(-1, 1440).sum(1)
    n = np.asarray(trades, dtype=float).reshape(-1, 1440).sum(1)
    return {"log_quote_volume": np.log(q), "log_trade_count": np.log(n), "log_range": np.log(h / lo)}


def standardize(values: np.ndarray, dates: list[dt.date]) -> np.ndarray:
    """z per calendar year and weekday class over all UTC days of that year-class (label-blind)."""
    keys = np.array([f"{d.year}:{G01.wd_class(d)}" for d in dates])
    z = np.full(len(values), np.nan)
    for k in np.unique(keys):
        m = keys == k
        v = values[m]
        z[m] = (v - v.mean()) / v.std(ddof=1)
    return z


def month_differences(z: np.ndarray, dates: list[dt.date], cal: dict) -> tuple[list[str], np.ndarray]:
    pos = {d: i for i, d in enumerate(dates)}
    by: dict[str, dict[str, list[float]]] = {}
    for d, (s, u) in cal.items():
        if d in pos and np.isfinite(z[pos[d]]):
            by.setdefault(u, {"TOM": [], "MID": []})[s].append(float(z[pos[d]]))
    units = sorted(u for u, v in by.items() if v["TOM"] and v["MID"])
    d = np.array([np.mean(by[u]["TOM"]) - np.mean(by[u]["MID"]) for u in units])
    return units, d


def part_a_outcome(d: np.ndarray, units: list[str]) -> dict:
    from scripts.research.owner_cards_r03 import evaluate as R03E
    M = len(d)
    est = float(d.mean())
    se = float(d.std(ddof=1) / math.sqrt(M))
    t = t_crit(M - 1)
    lo, hi = est - t * se, est + t * se
    years = np.array([int(u[:4]) for u in units])
    yearly = {str(y): (float(d[years == y].mean()) if (years == y).any() else None) for y in YEARS}
    flip = R03E.signflip_p(d.copy(), SIGNFLIP_DRAWS, SEED)
    block = R03E.moving_block_se(d.copy(), BLOCK_MONTHS, BLOCK_DRAWS, SEED)
    if -PART_A_MATERIAL_SD <= lo and hi <= PART_A_MATERIAL_SD:
        claim = "NO_PRODUCT_RELEVANT_SHIFT"
    elif (lo > 0 or hi < 0) and sum(1 for v in yearly.values()
                                    if v is not None and np.sign(v) == np.sign(est)) >= YEARS_SAME_SIGN:
        claim = "L1_CONTEXT_LINE_PERMITTED"
    else:
        claim = "INFORMATION_INSUFFICIENT"
    return {"MONTHS": M, "ESTIMATE_SD": est, "SE_T": se, "T_CRIT": t, "CI95": [lo, hi], "YEARLY_MEAN_D": yearly,
            "SIGNFLIP_P_TWO_SIDED": flip["P_TWO_SIDED"], "SE_SIGNFLIP": flip["SE_SIGNFLIP"],
            "SE_MOVING_BLOCK_3M": block, "CLAIM_DECISION": claim,
            "PER_MONTH_D": {u: float(x) for u, x in zip(units, d)}}


def part_a(panel: dict, trades: np.ndarray, cal: dict) -> dict:
    metrics = daily_metrics(panel, trades)
    dates = [WW.D0 + dt.timedelta(days=i) for i in range(len(metrics["log_range"]))]
    out = {}
    for name in PART_A_OUTCOMES:
        z = standardize(metrics[name], dates)
        units, d = month_differences(z, dates, cal)
        out[name] = part_a_outcome(d, units)
    tom = sum(1 for s, _ in cal.values() if s == "TOM")
    mid = sum(1 for s, _ in cal.values() if s == "MID")
    out["DAYS"] = {"TOM": tom, "MID": mid}
    return out


# ----------------------------------------------------------------------------- data
def read_trade_counts(specs: list[dict], fetch, cache: Path, origin: str, reader) -> np.ndarray:
    """(open_ms, trades) from column 8 of the same pinned zips (SHA-verified by `fetch`)."""
    parts = []
    for spec in specs:
        path = fetch(origin + spec["KEY"], cache / spec["FILENAME"], spec["SHA256"])
        parts.append(reader(path, spec["CSV"], (0, 8)))
    raw = np.concatenate(parts, axis=0)
    return raw[np.argsort(raw[:, 0], kind="mergesort")]


def align_trades(open_ms: np.ndarray, raw: np.ndarray) -> np.ndarray:
    t = np.rint(raw[:, 0]).astype(np.int64)
    if len(t) != len(open_ms) or not np.array_equal(t, np.asarray(open_ms, dtype=np.int64)):
        raise RuntimeError("trade-count column does not align with the loader's open_ms")
    return raw[:, 1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "docs/TURN_OF_MONTH_BASELINE_UNIT_V1_RESULT.json"))
    a = ap.parse_args()
    from scripts.research.owner_cards_r03 import data as R03
    panel = R03.load_btc_1m()
    raw = read_trade_counts(R03.btc_pinned_sources(), R03._fetch, R03.cache_root() / "btc_1m",
                            R03.S3_ORIGIN, R03._read_kline_zip)
    trades = align_trades(panel["open_ms"], raw)
    cal = calendar()
    res = {"VERSION": VERSION, "DESIGN_NOTE": DESIGN_NOTE,
           "PART_B": part_b(panel, cal, progress=lambda s: print(s, flush=True)),
           "PART_A": part_a(panel, trades, cal)}
    res["DATA"] = {"DATASET": "CORE_BTC_BINANCE_V0", "LOADER": "scripts/research/owner_cards_r03/data.py::load_btc_1m",
                   "TRADE_COUNT": "column 8 of the same pinned zips, aligned on open_ms",
                   "PINNED_DIGEST": R03.btc_dataset_digest(), "ROWS_1M": int(len(panel["open_ms"])),
                   "WINDOW": "2020-01-01..2024-12-31", "CALENDAR": "G01 day sets on [2020-01-31, 2025-01-01)",
                   "PROXY": "PROXY_SINGLE_VENUE (Binance)"}
    res["EVALUATOR_SHA256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    res["IMPORTED_SHA256"] = {p: hashlib.sha256((REPO / p).read_bytes()).hexdigest() for p in (
        "scripts/product/weekday_weekend_baseline_v2/evaluate.py", "scripts/research/autogen_g01/states.py",
        "scripts/research/owner_cards_r03/data.py", "scripts/research/owner_cards_r03/evaluate.py")}
    Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True, default=WW._json) + "\n")
    print(json.dumps({"PART_B": res["PART_B"]["DECISION"],
                      "PART_A": {k: res["PART_A"][k]["CLAIM_DECISION"] for k in PART_A_OUTCOMES}},
                     indent=1, default=WW._json))


if __name__ == "__main__":
    main()
