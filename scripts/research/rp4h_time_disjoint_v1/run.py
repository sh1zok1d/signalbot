"""RANGE_POSITION_4H_TIME_DISJOINT_REPLICATION_V1 (docs/research/RANGE_POSITION_4H_TIME_DISJOINT_REPLICATION_V1_DESIGN.md).

Time-disjoint replication of PRE_IMPULSE_STATE_ATLAS_V1's RANGE_POSITION_4H on BitMEX XBTUSD 2016-05..2019-12 (ERA) and
Binance USD-M BTCUSDT 2025-01-01..2026-10-08 (RECENT; no object overlapping the E1-RUN-001 holdout is ever requested),
with Binance spot 2017-08..2019-12 as same-period robustness.

    python -m scripts.research.rp4h_time_disjoint_v1.run census      # outcome-blind anchor counts
    python -m scripts.research.rp4h_time_disjoint_v1.run run --go    # one shot; refuses if the result exists
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import os
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
DESIGN = REPO / "docs/research/RANGE_POSITION_4H_TIME_DISJOINT_REPLICATION_V1_DESIGN.md"
RESULT_JSON = REPO / "docs/research/RANGE_POSITION_4H_TIME_DISJOINT_REPLICATION_V1_RESULT.json"
BITMEX_FILE = REPO / "docs/research_data/D2_BITMEX_PRE2020_XBTUSD/canonical_5m.jsonl.gz"
SPOT_INVENTORY = REPO / "docs/research_data/DH1_BINANCE_SPOT_BTCUSDT_5M_V0/SOURCE_INVENTORY.json"
VISION = "https://data.binance.vision/"
UM_MONTH = "data/futures/um/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-{m}.zip"
UM_DAY = "data/futures/um/daily/klines/BTCUSDT/5m/BTCUSDT-5m-{d}.zip"

BAR = 300_000
HOUR = 3_600_000
WIN = 48            # bars in the 4h window
HOR = 12            # bars in the 1h horizon
PHASE = 600_000     # anchor bar opens at minute ≡ 10 (mod 15), so T = close at :00/:15/:30/:45
SEED = 20261118
B = 2000
MIN_VALID = 1900
EDGES = (0.2, 0.4, 0.6, 0.8)
DEGENERATE = 1e-12


def _ms(s: str) -> int:
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


E1_START, E1_END = _ms("2026-08-16T00:00:00"), _ms("2026-08-25T17:20:00")
SURFACES = {
    "ERA": {"start": _ms("2016-05-13T11:55:00"), "end": _ms("2020-01-01T00:00:00"), "route": True},
    "RECENT": {"start": _ms("2025-01-01T00:00:00"), "end": _ms("2026-10-09T00:00:00"), "route": True},
    "ERA_SPOT": {"start": _ms("2017-08-17T00:00:00"), "end": _ms("2020-01-01T00:00:00"), "route": False},
}


# ---------------------------------------------------------------- guards and fetch
def overlaps_e1(start_ms: int, end_ms: int) -> bool:
    """True if [start_ms, end_ms) overlaps the E1-RUN-001 holdout."""
    return start_ms < E1_END and end_ms > E1_START


def recent_objects() -> list:
    """Vision objects for RECENT, none overlapping the E1 holdout (refused before any request)."""
    keys = []
    m = dt.date(2025, 1, 1)
    while m <= dt.date(2026, 7, 1):
        nxt = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
        keys.append((UM_MONTH.format(m=m.strftime("%Y-%m")), _ms(m.isoformat() + "T00:00:00"), _ms(nxt.isoformat() + "T00:00:00")))
        m = nxt
    d = dt.date(2026, 8, 1)
    while d <= dt.date(2026, 10, 8):
        s, e = _ms(d.isoformat() + "T00:00:00"), _ms((d + dt.timedelta(days=1)).isoformat() + "T00:00:00")
        if not overlaps_e1(s, e):
            keys.append((UM_DAY.format(d=d.isoformat()), s, e))
        d += dt.timedelta(days=1)
    for _, s, e in keys:
        if overlaps_e1(s, e):
            raise RuntimeError("an object overlapping the E1 holdout was planned")
    return keys


def _cache() -> Path:
    return Path(os.environ.get("RP4H_CACHE", "/tmp/rp4h_cache"))


def _get(key: str) -> bytes:
    path = _cache() / key
    if path.exists():
        return path.read_bytes()
    last = None
    for _ in range(4):
        try:
            req = urllib.request.Request(VISION + key, headers={"User-Agent": "rp4h"})
            with urllib.request.urlopen(req, timeout=120) as r:
                payload = r.read()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            return payload
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(f"fetch failed {key}: {last}")


def _parse_kline_zip(payload: bytes) -> list:
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        text = z.read(z.namelist()[0]).decode()
    rows = []
    for line in text.splitlines():
        if not line or not line[0].isdigit():
            continue
        f = line.split(",")
        t = int(f[0])
        if t > 10 ** 14:  # microsecond open times in newer archives
            t //= 1000
        rows.append((t, float(f[1]), float(f[2]), float(f[3]), float(f[4])))
    return rows


def _panel(rows: list) -> dict:
    rows = sorted(rows)
    a = np.array(rows, dtype=float).reshape(-1, 5)
    t = a[:, 0].astype(np.int64)
    keep = np.r_[True, np.diff(t) > 0]
    a, t = a[keep], t[keep]
    return {"open_ms": t, "open": a[:, 1], "high": a[:, 2], "low": a[:, 3], "close": a[:, 4]}


# ---------------------------------------------------------------- loaders
def parse_bitmex_lines(lines) -> dict:
    """D2 canonical 5m rows; buckets with trades == 0 carry the last price and are treated as missing."""
    rows = []
    for line in lines:
        r = json.loads(line)
        if not r.get("trades"):
            continue
        rows.append((int(r["open_time_ms"]), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])))
    return _panel(rows)


def load_bitmex() -> dict:
    with gzip.open(BITMEX_FILE, "rt") as fh:
        return parse_bitmex_lines(fh)


def load_recent() -> dict:
    keys = recent_objects()
    with ThreadPoolExecutor(max_workers=8) as pool:
        payloads = list(pool.map(lambda k: _get(k[0]), keys))
    rows = [r for p in payloads for r in _parse_kline_zip(p)]
    rows = [r for r in rows if not overlaps_e1(r[0], r[0] + BAR)]
    return _panel(rows)


def load_spot_era() -> dict:
    inv = json.loads(SPOT_INVENTORY.read_text())
    objs = [o for o in inv["OBJECTS"] if o["MONTH"] <= "2019-12"]

    def fetch(o):
        payload = _get(o["KEY"])
        if hashlib.sha256(payload).hexdigest() != o["SHA256"]:
            raise RuntimeError(f"spot {o['MONTH']}: digest drifted")
        return payload

    with ThreadPoolExecutor(max_workers=8) as pool:
        payloads = list(pool.map(fetch, objs))
    return _panel([r for p in payloads for r in _parse_kline_zip(p)])


LOADERS = {"ERA": load_bitmex, "RECENT": load_recent, "ERA_SPOT": load_spot_era}


# ---------------------------------------------------------------- grid and features
def to_grid(panel: dict, start_ms: int, end_ms: int) -> dict:
    """Contiguous 5m grid aligned to the 5m clock; missing bars are NaN, nothing is filled."""
    t0 = start_ms - start_ms % BAR
    n = (end_ms - t0) // BAR
    out = {"t0": t0, "n": int(n)}
    t = panel["open_ms"]
    keep = (t >= t0) & (t < end_ms) & (t % BAR == 0)
    idx = ((t[keep] - t0) // BAR).astype(np.int64)
    for c in ("high", "low", "close"):
        arr = np.full(n, np.nan)
        arr[idx] = panel[c][keep]
        out[c] = arr
    return out


def features(g: dict, end_ms: int) -> dict:
    """Anchor rows with every quantity of the design; anchors with any missing input are dropped."""
    from numpy.lib.stride_tricks import sliding_window_view as swv
    n, t0 = g["n"], g["t0"]
    hi, lo, cl = g["high"], g["low"], g["close"]
    i = np.arange(WIN + 1, n - HOR)
    i = i[((t0 + i * BAR) % (15 * 60_000)) == PHASE]
    i = i[t0 + (i + HOR) * BAR + BAR <= end_ms]          # the horizon bar closes inside the surface
    lc = np.log(cl)
    r5 = np.r_[np.nan, np.diff(lc)]
    hw = swv(hi, WIN)            # hw[k] = hi[k : k+WIN]
    lw = swv(lo, WIN)
    rw = swv(r5, WIN)
    win_hi = hw[i - WIN + 1].max(axis=1)                 # bars i-47..i
    win_lo = lw[i - WIN + 1].min(axis=1)
    rv = np.sqrt((rw[i - WIN + 1] ** 2).sum(axis=1))      # returns of bars i-47..i (closes i-48..i)
    prev_hi = hw[i - WIN].max(axis=1)                      # bars i-48..i-1
    prev_lo = lw[i - WIN].min(axis=1)
    span = win_hi - win_lo
    pspan = prev_hi - prev_lo
    with np.errstate(invalid="ignore", divide="ignore"):
        rows = {
            "T_MS": t0 + i * BAR + BAR,
            "RP4H": np.where(span > 0, (cl[i] - win_lo) / span, np.nan),
            "RET_4H": lc[i] - lc[i - WIN],
            "RV_4H": rv,
            "R_1H": lc[i + HOR] - lc[i],
            "RANGE_WIDTH_4H": np.log(win_hi) - np.log(win_lo),
            "RET_1H_LAG": lc[i] - lc[i - 12],
            "RET_15M_LAG": lc[i] - lc[i - 3],
            "RP4H_PREV": np.where(pspan > 0, (cl[i - 1] - prev_lo) / pspan, np.nan),
        }
    ok = np.ones(i.size, dtype=bool)
    for v in rows.values():
        ok &= np.isfinite(v)
    return {k: v[ok] for k, v in rows.items()}


# ---------------------------------------------------------------- statistics
def average_ranks(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x, kind="mergesort")
    xs = x[order]
    ranks = np.empty(x.size, dtype=float)
    starts = np.r_[0, np.flatnonzero(np.diff(xs) != 0) + 1]
    ends = np.r_[starts[1:], x.size]
    avg = (starts + ends + 1) / 2.0                         # 1-based average rank of each tie group
    ranks[order] = np.repeat(avg, ends - starts)
    return ranks


def _resid(y: np.ndarray, X: np.ndarray):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    tss = float(((y - y.mean()) ** 2).sum())
    rss = float((r ** 2).sum())
    if tss == 0 or rss <= DEGENERATE * tss:
        return None
    return r


def partial_spearman(x: np.ndarray, y: np.ndarray, covs: list):
    rx, ry = average_ranks(x), average_ranks(y)
    if not covs:
        a, b = rx - rx.mean(), ry - ry.mean()
        den = math.sqrt(float((a * a).sum() * (b * b).sum()))
        return None if den == 0 else float((a * b).sum() / den)
    X = np.column_stack([np.ones(x.size)] + [average_ranks(c) for c in covs])
    ex, ey = _resid(rx, X), _resid(ry, X)
    if ex is None or ey is None:
        return None
    den = math.sqrt(float((ex * ex).sum() * (ey * ey).sum()))
    return None if den == 0 else float((ex * ey).sum() / den)


ESTIMANDS = {
    "RAW": [],
    "PRIMARY": ["RET_4H", "RV_4H"],
    "SECONDARY_RECENT_PATH": ["RET_4H", "RV_4H", "RET_1H_LAG", "RET_15M_LAG"],
}
DIAGNOSTICS = {
    "GIVEN_RET_ONLY": ("RP4H", ["RET_4H"]),
    "GIVEN_RET_RV_WIDTH": ("RP4H", ["RET_4H", "RV_4H", "RANGE_WIDTH_4H"]),
    "PREV_BAR_POSITION_GIVEN_RET_RV": ("RP4H_PREV", ["RET_4H", "RV_4H"]),
}


def estimate(rows: dict, idx=None) -> dict:
    sel = (lambda v: v) if idx is None else (lambda v: v[idx])
    out = {k: partial_spearman(sel(rows["RP4H"]), sel(rows["R_1H"]), [sel(rows[c]) for c in cov]) for k, cov in ESTIMANDS.items()}
    q1 = sel(rows["RP4H"]) < EDGES[0]
    q5 = sel(rows["RP4H"]) >= EDGES[-1]
    r = sel(rows["R_1H"])
    if q1.any() and q5.any():
        out["Q1_MINUS_Q5_P_UP"] = float((r[q1] > 0).mean() - (r[q5] > 0).mean())
        out["Q1_MINUS_Q5_MEAN"] = float(r[q1].mean() - r[q5].mean())
    else:
        out["Q1_MINUS_Q5_P_UP"] = out["Q1_MINUS_Q5_MEAN"] = None
    return out


def iso_weeks(t_ms: np.ndarray) -> np.ndarray:
    days = (t_ms // 86_400_000).astype(np.int64)
    uniq, inv = np.unique(days, return_inverse=True)
    keys = []
    for d in uniq:
        y, w, _ = dt.date(1970, 1, 1).fromordinal(dt.date(1970, 1, 1).toordinal() + int(d)).isocalendar()
        keys.append(y * 100 + w)
    return np.array(keys)[inv]


def bootstrap(rows: dict) -> dict:
    weeks = iso_weeks(rows["T_MS"])
    uw, inv = np.unique(weeks, return_inverse=True)
    order = np.argsort(inv, kind="mergesort")
    bounds = np.r_[0, np.cumsum(np.bincount(inv, minlength=uw.size))]
    groups = [order[bounds[k]:bounds[k + 1]] for k in range(uw.size)]
    rng = np.random.default_rng(SEED)
    draws = {k: [] for k in list(ESTIMANDS) + ["Q1_MINUS_Q5_P_UP", "Q1_MINUS_Q5_MEAN"]}
    for _ in range(B):
        pick = rng.integers(0, uw.size, uw.size)
        idx = np.concatenate([groups[p] for p in pick])
        est = estimate(rows, idx)
        for k in draws:
            if est.get(k) is not None:
                draws[k].append(est[k])
    out = {}
    for k, v in draws.items():
        out[k] = {"VALID_DRAWS": len(v),
                  "CI95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v else None}
    out["WEEKS"] = int(uw.size)
    return out


def describe(rows: dict) -> dict:
    rp, r = rows["RP4H"], rows["R_1H"]
    b = np.digitize(rp, EDGES, right=False)
    quint = []
    for k in range(5):
        m = b == k
        quint.append({"BIN": k + 1, "N": int(m.sum()), "P_UP": float((r[m] > 0).mean()) if m.any() else None,
                      "MEAN_R_1H": float(r[m].mean()) if m.any() else None,
                      "MEDIAN_R_1H": float(np.median(r[m])) if m.any() else None})
    years = {}
    yr = np.array([dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).year for t in rows["T_MS"]])
    for y in sorted(set(yr.tolist())):
        idx = np.flatnonzero(yr == y)
        e = estimate(rows, idx)
        years[str(y)] = {"N": int(idx.size), "RAW": e["RAW"], "PRIMARY": e["PRIMARY"]}
    med = np.median(rows["T_MS"])
    halves = {}
    for name, idx in (("FIRST", np.flatnonzero(rows["T_MS"] <= med)), ("SECOND", np.flatnonzero(rows["T_MS"] > med))):
        e = estimate(rows, idx)
        halves[name] = {"N": int(idx.size), "RAW": e["RAW"], "PRIMARY": e["PRIMARY"]}
    diag = {k: partial_spearman(rows[f], r, [rows[c] for c in cov]) for k, (f, cov) in DIAGNOSTICS.items()}
    diag["SPEARMAN_RP4H_WIDTH"] = partial_spearman(rp, rows["RANGE_WIDTH_4H"], [])
    return {"QUINTILES": quint, "YEARS": years, "HALVES": halves, "DIAGNOSTICS": diag}


# ---------------------------------------------------------------- routes
def route(point: dict, boot: dict) -> str:
    if boot["RAW"]["VALID_DRAWS"] < MIN_VALID or boot["PRIMARY"]["VALID_DRAWS"] < MIN_VALID:
        return "ESTIMATE_UNAVAILABLE"
    raw, prim = point["RAW"], point["PRIMARY"]
    (rlo, rhi), (plo, phi) = boot["RAW"]["CI95"], boot["PRIMARY"]["CI95"]
    if raw is None or prim is None:
        return "ESTIMATE_UNAVAILABLE"
    if raw >= 0:
        return "NOT_REPLICATED"
    if prim < 0 and phi < 0:
        return "SUPPORTED"
    if rhi < 0 and plo > 0:
        return "INCREMENTAL_SIGN_OPPOSES"
    if rhi < 0 and plo <= 0 <= phi:
        return "RAW_ONLY"
    return "COMPATIBLE_UNCERTAIN"


def overall(era: str, recent: str) -> str:
    routes = {era, recent}
    if "ESTIMATE_UNAVAILABLE" in routes:
        return "UNAVAILABLE"
    if era == recent == "SUPPORTED":
        return "TIME_DISJOINT_REPLICATED_BOTH"
    if "SUPPORTED" in routes:
        other = recent if era == "SUPPORTED" else era
        if other in ("RAW_ONLY", "COMPATIBLE_UNCERTAIN"):
            return "TIME_DISJOINT_REPLICATED_ONE"
        return "TIME_DISJOINT_CONFLICT"
    return "TIME_DISJOINT_NOT_REPLICATED"


def label(ci, below: str, inside: str, above: str) -> str:
    if ci is None:
        return "UNAVAILABLE"
    lo, hi = ci
    return below if hi < 0 else above if lo > 0 else inside


def economic_label(ci) -> str:
    """MEAN_SHIFT_PRESENT when the Q1 - Q5 mean interval excludes 0; otherwise SIGN_ONLY."""
    if ci is None:
        return "UNAVAILABLE"
    return "MEAN_SHIFT_PRESENT" if (ci[1] < 0 or ci[0] > 0) else "SIGN_ONLY"


# ---------------------------------------------------------------- commands
def surface_rows(name: str) -> dict:
    spec = SURFACES[name]
    g = to_grid(LOADERS[name](), spec["start"], spec["end"])
    return features(g, spec["end"])


def census() -> dict:
    """Outcome-blind: anchor counts and weeks per surface (the outcome is not summarized)."""
    out = {}
    for name in SURFACES:
        rows = surface_rows(name)
        out[name] = {"ANCHORS": int(rows["T_MS"].size), "WEEKS": int(np.unique(iso_weeks(rows["T_MS"])).size),
                     "FIRST_T": dt.datetime.fromtimestamp(rows["T_MS"][0] / 1000, dt.timezone.utc).isoformat() if rows["T_MS"].size else None,
                     "LAST_T": dt.datetime.fromtimestamp(rows["T_MS"][-1] / 1000, dt.timezone.utc).isoformat() if rows["T_MS"].size else None}
    return out


def run() -> dict:
    if RESULT_JSON.exists():
        raise RuntimeError("one shot: the result already exists")
    design_sha = hashlib.sha256(DESIGN.read_bytes()).hexdigest()
    out = {"UNIT": "RANGE_POSITION_4H_TIME_DISJOINT_REPLICATION_V1", "DESIGN_SHA256": design_sha, "SEED": SEED, "B": B,
           "SURFACES": {}}
    for name in SURFACES:
        rows = surface_rows(name)
        point = estimate(rows)
        boot = bootstrap(rows)
        s = {"N": int(rows["T_MS"].size), "POINT": point, "BOOTSTRAP": boot, "DESCRIPTION": describe(rows),
             "RECENT_PATH_LABEL": label(boot["SECONDARY_RECENT_PATH"]["CI95"], "SURVIVES_RECENT_PATH", "ABSORBED_BY_RECENT_PATH", "OPPOSITE"),
             "ECONOMIC_LABEL": economic_label(boot["Q1_MINUS_Q5_MEAN"]["CI95"])}
        s["ROUTE"] = route(point, boot) if SURFACES[name]["route"] else "ROBUSTNESS_ONLY"
        if not SURFACES[name]["route"]:
            s["ROBUSTNESS_READING"] = route(point, boot)
        out["SURFACES"][name] = s
    out["OVERALL"] = overall(out["SURFACES"]["ERA"]["ROUTE"], out["SURFACES"]["RECENT"]["ROUTE"])
    RESULT_JSON.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("census", "run"))
    ap.add_argument("--go", action="store_true", help="required for the one-shot run (owner go recorded)")
    a = ap.parse_args()
    if a.step == "run" and not a.go:
        raise SystemExit("refusing: the one-shot run needs --go after the owner's go")
    res = census() if a.step == "census" else run()
    print(json.dumps(res, indent=2, sort_keys=True)[:8000])


if __name__ == "__main__":
    main()
