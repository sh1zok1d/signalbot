"""P3 confirmation V1 (docs/research/P3_CONFIRMATION_V1_PREREG.md): parity gate on the DH3 discovery surface,
then one shot on surface C (Binance BTCUSDT, 2025-01-01 .. 2026-08-15, nothing at or after 2026-08-15 requested).

    python -m scripts.research.p3c.run parity
    python -m scripts.research.p3c.run confirm      # refuses unless the parity result passed

Reuses DH3's state, endpoint, nuisance and estimator unchanged; only the data loader is new (5m archives).
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import math
import os
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from scripts.research.dh1 import constants as K1
from scripts.research.dh1 import data as D1
from scripts.research.dh1 import events as E1
from scripts.research.dh3 import constants as K
from scripts.research.dh3 import data as D3
from scripts.research.dh3 import evaluate as V
from scripts.research.dh3 import features as FT
from scripts.research.dh3 import outcomes as O

VISION = "https://data.binance.vision/"
KL_MONTH = "data/futures/um/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-{m}.zip"
KL_DAY = "data/futures/um/daily/klines/BTCUSDT/5m/BTCUSDT-5m-{d}.zip"
METRICS_DAY = "data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-{d}.zip"
HARD_STOP = dt.date(2026, 8, 15)          # no object dated on or after this day is ever requested
OUT_DIR = Path("docs/research")
PARITY_OUT = OUT_DIR / "P3_CONFIRMATION_V1_PARITY.json"
RESULT_OUT = OUT_DIR / "P3_CONFIRMATION_V1_RESULT.json"
SEED = 20261009
COST = 0.0012
SENSITIVITY_COSTS = (0.0004, 0.0)
DISC_SHIFT, DISC_N = -0.059246006066674496, 14218
H = K.HYPOTHESIS_BY_ID["DH3-P3"]
CONFIRM_EPOCHS = [("2025", "2025-01-01", "2026-01-01"), ("2026A", "2026-01-01", "2026-08-15")]


def _ms(s: str) -> int:
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def cache_root() -> Path:
    return Path(os.environ.get("P3C_CACHE", "/tmp/p3c_cache"))


def _guard(day: dt.date) -> None:
    if day >= HARD_STOP:
        raise RuntimeError(f"P3C refuses an object dated {day} (hard stop {HARD_STOP})")


def _get(key: str) -> bytes:
    path = cache_root() / key
    if path.exists():
        return path.read_bytes()
    last = None
    for _ in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(VISION + key, headers={"User-Agent": "p3c"}),
                                        timeout=120) as r:
                payload = r.read()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            return payload
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(f"fetch failed {key}: {last}")


def _months(first: str, last: str) -> list:
    y, m = map(int, first.split("-"))
    ly, lm = map(int, last.split("-"))
    out = []
    while (y, m) <= (ly, lm):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _days(first: str, last: str) -> list:
    a, b = dt.date.fromisoformat(first), dt.date.fromisoformat(last)
    return [(a + dt.timedelta(days=k)).isoformat() for k in range((b - a).days + 1)]


def _parse_klines(payload: bytes) -> list:
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        text = z.read(z.namelist()[0]).decode()
    rows = []
    for line in text.splitlines():
        if not line or not line[0].isdigit():
            continue
        f = line.split(",")
        t = int(f[0])
        if t > 10 ** 14:          # microsecond timestamps in newer archives
            t //= 1000
        rows.append((t, float(f[1]), float(f[2]), float(f[3]), float(f[4]), float(f[5]), float(f[7]), float(f[10])))
    return rows


def load_klines(months: list, days: list) -> dict:
    keys = []
    for m in months:
        _guard(dt.date.fromisoformat(m + "-01").replace(day=28))
        keys.append(KL_MONTH.format(m=m))
    for d in days:
        _guard(dt.date.fromisoformat(d))
        keys.append(KL_DAY.format(d=d))
    with ThreadPoolExecutor(max_workers=8) as pool:
        payloads = list(pool.map(_get, keys))
    rows = sorted(r for p in payloads for r in _parse_klines(p))
    a = np.array(rows, dtype=float)
    t = a[:, 0].astype(np.int64)
    keep = np.r_[True, np.diff(t) > 0]
    a, t = a[keep], t[keep]
    return {"open_ms": t, "open": a[:, 1], "high": a[:, 2], "low": a[:, 3], "close": a[:, 4], "volume": a[:, 5],
            "quote": a[:, 6], "taker_buy_quote": a[:, 7]}


def load_metrics(days: list) -> dict:
    for d in days:
        _guard(dt.date.fromisoformat(d))
    with ThreadPoolExecutor(max_workers=12) as pool:
        payloads = list(pool.map(lambda d: _get(METRICS_DAY.format(d=d)), days))
    rows = sorted(r for p in payloads for r in D3._parse_metrics(p))
    t = np.array([r[0] for r in rows], dtype=np.int64)
    keep = np.r_[True, np.diff(t) > 0]
    return {"t": t[keep], "oi": np.array([r[1] for r in rows])[keep], "ls": np.array([r[2] for r in rows])[keep]}


def crowd_rows(b, m: dict, hist_from_ms: int, rows_from_ms: int, end_ms: int) -> tuple:
    """DH3 card_p's P3 state: hourly decision bars, z of the ls ratio against the trailing 30 days of hourly
    values (>= 600 present, history counted from hist_from_ms like card_p's js list)."""
    sigma = E1.rolling_sigma(b.close)
    js = FT.hourly_js(b, hist_from_ms, end_ms)
    raw = []
    for k, j in enumerate(js):
        hist = np.array([m["ls"][x] for x in js[max(0, k - 24 * K.CROWD_Z_DAYS):k]])
        hist = hist[np.isfinite(hist)]
        z = None
        if hist.size >= 600 and math.isfinite(m["ls"][j]) and hist.std() > 0:
            z = float((m["ls"][j] - hist.mean()) / hist.std())
        if E1.decision_ms(b, j) >= rows_from_ms:
            raw.append({"J": j, "CROWD_Z": z})
    return raw, sigma


def state_rows(b, raw: list, sigma, q20: float, q80: float) -> list:
    out = []
    for r in raw:
        z = r["CROWD_Z"]
        if z is not None and (z <= q20 or z >= q80):
            row = FT.base(b, r["J"], sigma, "BTC", "UP_FIRST_4H")
            if row:
                out.append({**row, "S": int(z >= q80)})
    return out


def evaluate(b, rows: list, model=None) -> dict:
    with_y = O.attach({"BTC": b}, rows)
    cell = FT.cell_rows(with_y, H)
    res = V.evaluate_cell(cell, H, SEED, model)
    se = (res["CI95"][1] - res["CI95"][0]) / 3.92
    res["MDE_80POWER"] = 2.8 * se
    res.pop("MODEL", None) if model is not None else None
    return res, cell


def trade(b, j: int, side: int, x: float) -> tuple:
    """(gross return, exit index) for a position opened at close[j]; both barriers in one bar -> the stop."""
    entry = b.close[j]
    hi, lo = b.high[j + 1:j + 1 + K1.HOLD_BARS], b.low[j + 1:j + 1 + K1.HOLD_BARS]
    up, dn = entry * (1 + x), entry * (1 - x)
    for k in range(hi.size):
        h_up = math.isfinite(hi[k]) and hi[k] >= up
        h_dn = math.isfinite(lo[k]) and lo[k] <= dn
        if h_up or h_dn:
            if h_up and h_dn:
                return -x, j + 1 + k
            win = (h_up and side > 0) or (h_dn and side < 0)
            return (x if win else -x), j + 1 + k
    last = j + K1.HOLD_BARS
    while last > j and not math.isfinite(b.close[last]):
        last -= 1
    if last == j:
        return None, j
    return side * (b.close[last] / entry - 1.0), last


def trading(b, rows: list) -> dict:
    trades, busy_until = [], -1
    for r in sorted(rows, key=lambda r: r["J"]):
        j = r["J"]
        if j <= busy_until:
            continue
        side = -1 if r["S"] == 1 else +1          # crowd long -> short, crowd short -> long
        g, exit_j = trade(b, j, side, r["X"])
        if g is None:
            continue
        busy_until = exit_j
        trades.append({"T_MS": r["T_MS"], "WEEK": r["WEEK"], "EPOCH": r["EPOCH"], "SIDE": side, "X": r["X"], "GROSS": g})
    return summarize(trades)


def _boot_mean(vals: np.ndarray, weeks: np.ndarray) -> list:
    rng = np.random.default_rng(SEED)
    uw = np.unique(weeks)
    groups = {w: vals[weeks == w] for w in uw}
    sums = np.array([groups[w].sum() for w in uw])
    cnts = np.array([groups[w].size for w in uw])
    draws = []
    for _ in range(K1.BOOT_DRAWS):
        idx = rng.integers(0, uw.size, uw.size)
        draws.append(sums[idx].sum() / cnts[idx].sum())
    return [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]


def summarize(trades: list) -> dict:
    if not trades:
        return {"TRADES": 0}
    g = np.array([t["GROSS"] for t in trades])
    x = np.array([t["X"] for t in trades])
    weeks = np.array([t["WEEK"] for t in trades])
    out = {"TRADES": len(trades), "WIN_RATE_GROSS": float((g > 0).mean()), "MEAN_X_PCT": float(x.mean() * 100),
           "MEAN_GROSS_PCT": float(g.mean() * 100)}
    for cost in (COST,) + SENSITIVITY_COSTS:
        net = g - cost
        cum = np.cumsum(net)
        dd = float((np.maximum.accumulate(cum) - cum).max())
        out[f"COST_{cost * 100:.2f}PCT"] = {
            "MEAN_NET_PCT": float(net.mean() * 100), "MEAN_NET_IN_X": float((net / x).mean()),
            "SUM_NET_PCT": float(net.sum() * 100), "MAX_DRAWDOWN_PCT": dd * 100,
            "CI95_MEAN_NET_PCT": [v * 100 for v in _boot_mean(net, weeks)]}
    for key, sel in (("BY_SIDE", lambda t: "long" if t["SIDE"] > 0 else "short"), ("BY_EPOCH", lambda t: t["EPOCH"])):
        part = {}
        for k in sorted({sel(t) for t in trades}):
            gg = np.array([t["GROSS"] for t in trades if sel(t) == k])
            part[k] = {"TRADES": int(gg.size), "MEAN_NET_PCT": float((gg - COST).mean() * 100)}
        out[key] = part
    main = out[f"COST_{COST * 100:.2f}PCT"]
    out["CLASS"] = "TRADING_PASS" if (main["MEAN_NET_PCT"] > 0 and main["CI95_MEAN_NET_PCT"][0] > 0) else "TRADING_FAIL"
    return out


def discovery_surface() -> tuple:
    b = D1.to_bars(load_klines(_months("2020-01", "2024-12"), []), _ms("2020-01-01"), _ms("2025-01-01"))
    m = D3.metrics_on_grid(load_metrics(_days(K.METRICS_FIRST_DAY, K.METRICS_LAST_DAY)), b.t0, b.n)
    start, end = _ms(K.SURFACES["DH3-P"]["START"]), _ms(K.SURFACES["DH3-P"]["END"])
    raw, sigma = crowd_rows(b, m, start, start, end)
    zs = [r["CROWD_Z"] for r in raw if r["CROWD_Z"] is not None]
    q20, q80 = float(np.quantile(zs, 0.2)), float(np.quantile(zs, 0.8))
    return b, raw, sigma, q20, q80


def parity() -> dict:
    b, raw, sigma, q20, q80 = discovery_surface()
    rows = state_rows(b, raw, sigma, q20, q80)
    res, cell = evaluate(b, rows)
    ok = abs(res["ADJUSTED_SHIFT"] - DISC_SHIFT) <= 0.01 and abs(res["N"] - DISC_N) <= 0.03 * DISC_N
    out = {"SURFACE": "DH3-P discovery 2020-10-01..2025-01-01 (5m archives)", "Q20": q20, "Q80": q80,
           "N": res["N"], "ADJUSTED_SHIFT": res["ADJUSTED_SHIFT"], "CI95": res["CI95"],
           "MEAN_STATE": res["MEAN_STATE"], "MEAN_COMPARATOR": res["MEAN_COMPARATOR"],
           "DH3_REFERENCE": {"ADJUSTED_SHIFT": DISC_SHIFT, "N": DISC_N}, "PARITY": "PASS" if ok else "FAIL",
           "TRADING_DISCOVERY_REFERENCE": trading(b, cell)}
    PARITY_OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return out


def confirm() -> dict:
    par = json.loads(PARITY_OUT.read_text())
    if par["PARITY"] != "PASS":
        raise RuntimeError("parity failed: the confirmation is not run")
    if RESULT_OUT.exists():
        raise RuntimeError("one shot: the result already exists")
    K.EPOCHS_ALL = list(K.EPOCHS_ALL) + CONFIRM_EPOCHS
    K.EPOCH_ORDER = list(K.EPOCH_ORDER) + [e[0] for e in CONFIRM_EPOCHS]
    end = _ms("2026-08-15")
    kl = load_klines(_months("2024-11", "2026-07"), _days("2026-08-01", "2026-08-14"))
    b = D1.to_bars(kl, _ms("2024-11-01"), end)
    m = D3.metrics_on_grid(load_metrics(_days("2024-11-01", "2026-08-14")), b.t0, b.n)
    raw, sigma = crowd_rows(b, m, _ms("2024-11-01"), _ms("2025-01-01"), end)
    rows = state_rows(b, raw, sigma, par["Q20"], par["Q80"])
    model = json.loads(Path("docs/research/DH3_RESULT_DISCOVERY.json").read_text())["CELLS"]["DH3-P3"]["MODEL"]
    res, cell = evaluate(b, rows, model)
    sh, (lo, hi) = res["ADJUSTED_SHIFT"], res["CI95"]
    cls = ("OPPOSITE" if lo > 0 else "NOT_CONFIRMED" if hi >= 0 else "CONFIRMED" if sh <= -0.03 else "PRESENT_BELOW_BAR")
    out = {"PREREG": "docs/research/P3_CONFIRMATION_V1_PREREG.md", "SURFACE": "C: 2025-01-01..2026-08-15 (exclusive)",
           "THRESHOLDS": {"Q20": par["Q20"], "Q80": par["Q80"]}, "CLASS": cls, "STATISTICAL": res,
           "TRADING": trading(b, cell), "LAST_OBJECT_DAY": "2026-08-14"}
    RESULT_OUT.write_text(json.dumps(out, indent=2, sort_keys=True, default=str) + "\n")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("parity", "confirm"))
    a = ap.parse_args()
    res = parity() if a.step == "parity" else confirm()
    print(json.dumps(res, indent=2, sort_keys=True, default=str)[:6000])


if __name__ == "__main__":
    main()
