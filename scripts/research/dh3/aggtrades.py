"""Stream Binance aggTrades (USD-M and spot BTCUSDT, 2020-01..2024-12) into per-stress-hour
features for card DH3-S. Each monthly zip is verified against its published CHECKSUM, read in
chunks, reduced to the stress hours and deleted; only the digests and the per-hour features are
kept (`docs/research_data/DH3_BINANCE_AGGTRADES_STRESS_V0`).

A stress hour is a UTC hour whose perp log range (from the pinned CORE_BTC 5m bars) is in the top
decile of the DH3-S surface. Features (all inside the hour, so known at its close):
- LEAD_SCORE = sum over k = 1..3 s of corr(perp r_t, spot r_t+k) - corr(spot r_t, perp r_t+k), from
  1-second last-trade log returns (> 0: perp leads; < 0: spot leads);
- N_LARGE_PERP = number of perp aggTrades with price * quantity >= 1M USD.
No outcome is read here.

python -m scripts.research.dh3.aggtrades
"""

from __future__ import annotations

import datetime as dt
import io
import json
import os
import zipfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from scripts.research.dh1 import data as D1

from . import constants as K

REPO = Path(__file__).resolve().parents[3]
OUT_DIR = REPO / "docs/research_data/DH3_BINANCE_AGGTRADES_STRESS_V0"
FEATURES = OUT_DIR / "stress_hour_features.csv"
INVENTORY = OUT_DIR / "SOURCE_INVENTORY.json"
KEYS = {"UM": "data/futures/um/monthly/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{m}.zip",
        "SPOT": "data/spot/monthly/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{m}.zip"}
HOUR_MS = 3_600_000


def months() -> list[str]:
    out, y, m = [], 2020, 1
    while f"{y}-{m:02d}" <= K.AGG_LAST_MONTH:
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def stress_hours() -> tuple[np.ndarray, float]:
    """Hour-start times (ms) of the stress hours and the decile cut, from CORE_BTC 5m bars."""
    perp = D1.load_binance_perp_5m()
    start, end = K._ms(K.SURFACES["DH3-S"]["START"]), K._ms(K.SURFACES["DH3-S"]["END"])
    b = D1.to_bars(perp, K._ms("2020-01-01"), end)
    n = b.n // 12 * 12
    hi = b.high[:n].reshape(-1, 12)
    lo = b.low[:n].reshape(-1, 12)
    ok = np.isfinite(hi).all(1) & np.isfinite(lo).all(1)
    rng = np.full(hi.shape[0], np.nan)
    rng[ok] = np.log(hi[ok].max(1) / lo[ok].min(1))
    t = b.t0 + np.arange(hi.shape[0], dtype=np.int64) * HOUR_MS
    eligible = ok & (t >= start) & (t + HOUR_MS <= end)
    cut = float(np.quantile(rng[eligible], K.STRESS_DECILE))
    return t[eligible & (rng >= cut)], cut


def _read_trades(path: Path, hours: set, spot: bool) -> dict:
    """{hour_ms: (times_ms, prices, quotes)} for trades inside the given hours."""
    import pandas as pd
    out: dict = {}
    hour_arr = np.array(sorted(hours), dtype=np.int64)
    with zipfile.ZipFile(path) as z:
        name = z.namelist()[0]
        with z.open(name) as fh:
            first = fh.readline()
        header = first[:1].isalpha()
        with z.open(name) as fh:
            reader = pd.read_csv(fh, header=0 if header else None, usecols=[1, 2, 5], chunksize=5_000_000,
                                 names=None if header else list(range(8 if spot else 7)))
            for chunk in reader:
                cols = list(chunk.columns)
                t = chunk[cols[2]].to_numpy(dtype=np.int64)
                if t.size and t.max() > 10 ** 14:          # microseconds (not expected before 2025)
                    t = t // 1000
                h = t - t % HOUR_MS
                m = np.isin(h, hour_arr)
                if not m.any():
                    continue
                t, h = t[m], h[m]
                p = chunk[cols[0]].to_numpy(dtype=float)[m]
                q = chunk[cols[1]].to_numpy(dtype=float)[m]
                for hh in np.unique(h):
                    sel = h == hh
                    prev = out.get(int(hh))
                    part = (t[sel], p[sel], p[sel] * q[sel])
                    out[int(hh)] = part if prev is None else tuple(np.concatenate([a, b]) for a, b in zip(prev, part))
    return out


def second_grid(times: np.ndarray, prices: np.ndarray, hour: int) -> np.ndarray:
    """Last trade price at the end of each second of the hour (leading seconds take the first price)."""
    order = np.argsort(times, kind="mergesort")
    times, prices = times[order], prices[order]
    sec = ((times - hour) // 1000).astype(np.int64)
    grid = np.full(3600, np.nan)
    last_idx = np.flatnonzero(np.r_[sec[1:] != sec[:-1], True])
    grid[sec[last_idx]] = prices[last_idx]
    if np.isnan(grid[0]):
        grid[0] = prices[0]
    idx = np.where(np.isfinite(grid), np.arange(3600), 0)
    return grid[np.maximum.accumulate(idx)]


def lead_score(perp_grid: np.ndarray, spot_grid: np.ndarray) -> float | None:
    rp, rs = np.diff(np.log(perp_grid)), np.diff(np.log(spot_grid))
    if np.std(rp) == 0 or np.std(rs) == 0:
        return None
    total = 0.0
    for k in K.LEAD_LAGS_S:
        a = np.corrcoef(rp[:-k], rs[k:])[0, 1]
        b = np.corrcoef(rs[:-k], rp[k:])[0, 1]
        if not (np.isfinite(a) and np.isfinite(b)):
            return None
        total += a - b
    return float(total)


def process_month(month: str, hours: list) -> dict:
    cache = D1.cache_root() / "dh3_agg"
    cache.mkdir(parents=True, exist_ok=True)
    hours_set = set(int(h) for h in hours)
    rec = {"MONTH": month, "OBJECTS": {}, "ROWS": []}
    trades = {}
    for kind in ("UM", "SPOT"):
        key = KEYS[kind].format(m=month)
        published = D1._get(D1.VISION + key + ".CHECKSUM").decode().split()[0]
        path = cache / Path(key).name
        if not path.exists() or D1.sha256_bytes(path.read_bytes()) != published:
            import urllib.request
            tmp = path.with_suffix(".part")
            with urllib.request.urlopen(urllib.request.Request(D1.VISION + key, headers=D1.UA), timeout=600) as r, \
                    open(tmp, "wb") as fh:
                while True:
                    chunk = r.read(1 << 22)
                    if not chunk:
                        break
                    fh.write(chunk)
            tmp.replace(path)
        import hashlib
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 22), b""):
                h.update(chunk)
        if h.hexdigest() != published:
            raise RuntimeError(f"{key}: digest mismatch")
        rec["OBJECTS"][kind] = {"KEY": key, "SHA256": published, "BYTES": path.stat().st_size,
                                "CHECKSUM_VERIFICATION": "VERIFIED"}
        trades[kind] = _read_trades(path, hours_set, spot=(kind == "SPOT")) if hours_set else {}
        path.unlink()
    for hour in sorted(hours_set):
        up, sp = trades["UM"].get(hour), trades["SPOT"].get(hour)
        if up is None or sp is None or up[0].size < 100 or sp[0].size < 100:
            rec["ROWS"].append((hour, None, None, 0 if up is None else int(up[0].size), 0 if sp is None else int(sp[0].size)))
            continue
        score = lead_score(second_grid(up[0], up[1], hour), second_grid(sp[0], sp[1], hour))
        n_large = int(np.sum(up[2] >= K.LARGE_PRINT_USD))
        rec["ROWS"].append((hour, score, n_large, int(up[0].size), int(sp[0].size)))
    return rec


def build(workers: int = 2) -> dict:
    hours, cut = stress_hours()
    by_month: dict = {}
    for h in hours:
        m = dt.datetime.fromtimestamp(int(h) / 1000, tz=dt.timezone.utc).strftime("%Y-%m")
        by_month.setdefault(m, []).append(int(h))
    for m in months():
        D1._refuse_protected(dt.date.fromisoformat(m + "-01"))
    recs = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(process_month, m, by_month.get(m, [])): m for m in months()}
        for f in futs:
            recs.append(f.result())
            print("month done", futs[f], flush=True)
    recs.sort(key=lambda r: r["MONTH"])
    rows = sorted(r for rec in recs for r in rec["ROWS"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["hour_ms,lead_score,n_large_perp,n_perp_trades,n_spot_trades"]
    for hour, score, n_large, npt, nst in rows:
        lines.append(f"{hour},{'' if score is None else repr(score)},{'' if n_large is None else n_large},{npt},{nst}")
    FEATURES.write_text("\n".join(lines) + "\n")
    body = {"DATASET_ID": "DH3_BINANCE_AGGTRADES_STRESS_V0", "SOURCE": D1.VISION,
            "INSTRUMENTS": "Binance USD-M BTCUSDT and spot BTCUSDT aggTrades", "MONTHS": f"{months()[0]}..{months()[-1]}",
            "STRESS_RULE": f"hour perp log range >= {cut!r} (top decile of the DH3-S surface, CORE_BTC 5m bars)",
            "STRESS_HOURS": int(len(hours)), "FEATURES_FILE": FEATURES.name,
            "FEATURES_SHA256": D1.sha256_bytes(FEATURES.read_bytes()),
            "OBJECTS": [{"MONTH": r["MONTH"], **{k: v for k, v in r["OBJECTS"].items()}} for r in recs]}
    body["OBJECT_LIST_SHA256"] = D1.sha256_bytes(json.dumps(
        [[r["MONTH"], r["OBJECTS"]["UM"]["SHA256"], r["OBJECTS"]["SPOT"]["SHA256"]] for r in recs],
        separators=(",", ":")).encode())
    INVENTORY.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return body


def load() -> dict:
    inv = json.loads(INVENTORY.read_text())
    if D1.sha256_bytes(FEATURES.read_bytes()) != inv["FEATURES_SHA256"]:
        raise RuntimeError("DH3 aggTrades features drifted")
    out = {}
    for line in FEATURES.read_text().splitlines()[1:]:
        hour, score, n_large, npt, nst = line.split(",")
        out[int(hour)] = {"LEAD_SCORE": float(score) if score else None, "N_LARGE_PERP": int(n_large) if n_large else None,
                          "N_PERP": int(npt), "N_SPOT": int(nst)}
    return out


if __name__ == "__main__":
    workers = int(os.environ.get("DH3_AGG_WORKERS", "2"))
    b = build(workers)
    print("DONE", b["STRESS_HOURS"], b["OBJECT_LIST_SHA256"])
