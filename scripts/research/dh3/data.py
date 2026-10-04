"""DH3 data: free public sources, every object pinned (published CHECKSUM or a committed digest).

- `DH3_BINANCE_UM_BTC_METRICS_5M_V0`: Binance Vision daily `metrics` for BTCUSDT 2020-09-01..2024-12-31
  (5m OI and long/short ratios). Product rule: the snapshot labelled with bar j's open is used at
  bar j's close.
- `DH3_BINANCE_UM_BOOKDEPTH_V0`: Binance Vision daily `bookDepth` (±1..5 % notional) for six coins,
  2023-01-01..2024-12-31, reduced to the ±1 % notional of the last snapshot at or before each 5m
  bar close (stale above 10 minutes -> missing).
- `DH3_DERIBIT_DVOL_1H_V0`: Deribit public DVOL hourly candles for BTC and ETH, 2021-03-25..2024-12-31,
  committed as a CSV with its digest (the API has no published checksum).
- aggTrades features: `aggtrades.py`.

No object at or after 2025-01-01 is requested. No outcome is read here.
"""

from __future__ import annotations

import datetime as dt
import gzip
import io
import json
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from scripts.research.dh1 import data as D1
from scripts.research.dh2 import constants as K2

from . import constants as K

REPO = Path(__file__).resolve().parents[3]
METRICS_DIR = REPO / "docs/research_data/DH3_BINANCE_UM_BTC_METRICS_5M_V0"
BOOK_DIR = REPO / "docs/research_data/DH3_BINANCE_UM_BOOKDEPTH_V0"
DVOL_DIR = REPO / "docs/research_data/DH3_DERIBIT_DVOL_1H_V0"
DVOL_CSV = DVOL_DIR / "dvol_1h.csv.gz"
METRICS_KEY = "data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-{d}.zip"
BOOK_KEY = "data/futures/um/daily/bookDepth/{pair}/{pair}-bookDepth-{d}.zip"
DERIBIT = "https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={c}&start_timestamp={a}&end_timestamp={z}&resolution=3600"


def days(first: str, last: str) -> list[str]:
    d0, d1 = dt.date.fromisoformat(first), dt.date.fromisoformat(last)
    return [(d0 + dt.timedelta(days=k)).isoformat() for k in range((d1 - d0).days + 1)]


def _fetch(key: str, sub: str, published: str | None = None) -> tuple[bytes, str]:
    cache = D1.cache_root() / sub / Path(key).name
    if published is None:
        published = D1._get(D1.VISION + key + ".CHECKSUM").decode().split()[0]
    payload = cache.read_bytes() if cache.exists() else b""
    if D1.sha256_bytes(payload) != published:
        payload = D1._get(D1.VISION + key)
        if D1.sha256_bytes(payload) != published:
            raise RuntimeError(f"{key}: digest mismatch")
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(".part")
        tmp.write_bytes(payload)
        tmp.replace(cache)
    return payload, published


def _guard(day: str) -> None:
    D1._refuse_protected(dt.date.fromisoformat(day))


# ---------------------------------------------------------------- metrics (OI, long/short ratios)
def _num(x: str) -> float:
    x = x.strip().strip('"')
    try:
        return float(x) if x else np.nan
    except ValueError:
        return np.nan


def _parse_metrics(payload: bytes) -> list:
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        text = z.read(z.namelist()[0]).decode()
    rows = []
    for line in text.splitlines():
        if not line or line[0].isalpha():
            continue
        f = line.split(",")
        t = int(dt.datetime.fromisoformat(f[0].strip('"')).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        rows.append((t, _num(f[2]), _num(f[6]) if len(f) > 6 else np.nan))
    return rows


def build_metrics(workers: int = 8) -> dict:
    ds = days(K.METRICS_FIRST_DAY, K.METRICS_LAST_DAY)
    for d in ds:
        _guard(d)
    keys = [METRICS_KEY.format(d=d) for d in ds]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        res = list(pool.map(lambda k: _fetch(k, "dh3_metrics"), keys))
    objects = [{"DAY": d, "KEY": k, "SHA256": sha, "BYTES": len(p), "ROWS": len(_parse_metrics(p)),
                "CHECKSUM_VERIFICATION": "VERIFIED"} for d, k, (p, sha) in zip(ds, keys, res)]
    body = {"DATASET_ID": "DH3_BINANCE_UM_BTC_METRICS_5M_V0", "SOURCE": D1.VISION, "INSTRUMENT": "Binance USD-M BTCUSDT",
            "DAYS": f"{ds[0]}..{ds[-1]}", "COLUMNS_USED": "create_time, sum_open_interest, count_long_short_ratio",
            "OBJECTS": objects}
    body["OBJECT_LIST_SHA256"] = D1.sha256_bytes(json.dumps([[o["DAY"], o["SHA256"]] for o in objects],
                                                            separators=(",", ":")).encode())
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    (METRICS_DIR / "SOURCE_INVENTORY.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return body


def load_metrics() -> dict:
    inv = json.loads((METRICS_DIR / "SOURCE_INVENTORY.json").read_text())
    rows = []
    for o in inv["OBJECTS"]:
        _guard(o["DAY"])
        payload, _ = _fetch(o["KEY"], "dh3_metrics", o["SHA256"])
        rows += _parse_metrics(payload)
    rows.sort()
    t = np.array([r[0] for r in rows], dtype=np.int64)
    keep = np.r_[True, np.diff(t) > 0]
    return {"t": t[keep], "oi": np.array([r[1] for r in rows])[keep], "ls": np.array([r[2] for r in rows])[keep]}


def metrics_on_grid(metrics: dict, t0: int, n: int) -> dict:
    """oi[j], ls[j] = the snapshot labelled with bar j's open time (usable at bar j's close)."""
    out = {"oi": np.full(n, np.nan), "ls": np.full(n, np.nan)}
    idx = (metrics["t"] - t0) // 300_000
    ok = ((metrics["t"] - t0) % 300_000 == 0) & (idx >= 0) & (idx < n)
    out["oi"][idx[ok]] = metrics["oi"][ok]
    out["ls"][idx[ok]] = metrics["ls"][ok]
    return out


# ---------------------------------------------------------------- bookDepth (±1 % notional)
def _parse_book(payload: bytes) -> np.ndarray:
    """(t_ms, bid1_notional, ask1_notional) per snapshot."""
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        text = z.read(z.namelist()[0]).decode()
    snaps: dict = {}
    for line in text.splitlines():
        if not line or line[0].isalpha():
            continue
        f = line.split(",")
        pct = int(float(f[1]))
        if pct not in (-K.DEPTH_BAND, K.DEPTH_BAND):
            continue
        t = int(dt.datetime.fromisoformat(f[0]).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        rec = snaps.setdefault(t, [np.nan, np.nan])
        rec[0 if pct < 0 else 1] = float(f[3])
    return np.array([(t, v[0], v[1]) for t, v in sorted(snaps.items())], dtype=float).reshape(-1, 3)


def book_plan() -> list:
    return [(s, d, BOOK_KEY.format(pair=K2.PAIR[s], d=d)) for s in K.SURFACES["DH3-L"]["SYMBOLS"]
            for d in days(K.BOOKDEPTH_FIRST_DAY, K.BOOKDEPTH_LAST_DAY)]


def build_book(workers: int = 8) -> dict:
    plan = book_plan()
    for _, d, _ in plan:
        _guard(d)

    def one(item):
        sym, d, key = item
        try:
            payload, sha = _fetch(key, "dh3_book")
        except RuntimeError as exc:
            if "fetch failed" in str(exc):
                return {"SYMBOL": sym, "DAY": d, "KEY": key, "STATUS": "MISSING"}
            raise
        return {"SYMBOL": sym, "DAY": d, "KEY": key, "SHA256": sha, "BYTES": len(payload),
                "SNAPSHOTS": int(_parse_book(payload).shape[0]), "STATUS": "VERIFIED"}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        objects = list(pool.map(one, plan))
    body = {"DATASET_ID": "DH3_BINANCE_UM_BOOKDEPTH_V0", "SOURCE": D1.VISION,
            "INSTRUMENTS": [K2.PAIR[s] for s in K.SURFACES["DH3-L"]["SYMBOLS"]],
            "DAYS": f"{K.BOOKDEPTH_FIRST_DAY}..{K.BOOKDEPTH_LAST_DAY}", "BAND_USED": "±1 % notional", "OBJECTS": objects,
            "MISSING": sum(1 for o in objects if o["STATUS"] == "MISSING")}
    body["OBJECT_LIST_SHA256"] = D1.sha256_bytes(json.dumps([[o["KEY"], o.get("SHA256")] for o in objects],
                                                            separators=(",", ":")).encode())
    BOOK_DIR.mkdir(parents=True, exist_ok=True)
    (BOOK_DIR / "SOURCE_INVENTORY.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return body


def book_on_grid(symbol: str, t0: int, n: int) -> dict:
    """bid1[j], ask1[j] = ±1 % notional of the last snapshot at or before bar j's close (<= 10 min old)."""
    inv = json.loads((BOOK_DIR / "SOURCE_INVENTORY.json").read_text())
    parts = []
    for o in inv["OBJECTS"]:
        if o["SYMBOL"] != symbol or o["STATUS"] != "VERIFIED":
            continue
        _guard(o["DAY"])
        payload, _ = _fetch(o["KEY"], "dh3_book", o["SHA256"])
        parts.append(_parse_book(payload))
    snaps = np.concatenate(parts) if parts else np.zeros((0, 3))
    snaps = snaps[np.argsort(snaps[:, 0], kind="mergesort")]
    close_t = t0 + (np.arange(n, dtype=np.int64) + 1) * 300_000
    pos = np.searchsorted(snaps[:, 0], close_t, side="right") - 1
    out = {"bid1": np.full(n, np.nan), "ask1": np.full(n, np.nan)}
    ok = (pos >= 0)
    ok[ok] &= (close_t[ok] - snaps[pos[ok], 0]) <= 600_000
    out["bid1"][ok] = snaps[pos[ok], 1]
    out["ask1"][ok] = snaps[pos[ok], 2]
    return out


# ---------------------------------------------------------------- Deribit DVOL hourly
def build_dvol() -> dict:
    a0, z0 = K._ms(K.DVOL_START), K._ms(K.DVOL_END)
    rows, digests = [], []
    for cur in ("BTC", "ETH"):
        a = a0
        while a < z0:
            z = min(a + 900 * 3_600_000, z0)
            raw = D1._get(DERIBIT.format(c=cur, a=a, z=z - 1))
            digests.append([cur, a, z, D1.sha256_bytes(raw)])
            for ts, o, h, lo, c in json.loads(raw)["result"]["data"]:
                if a0 <= ts < z0:
                    rows.append((cur, int(ts), float(o), float(h), float(lo), float(c)))
            a = z
            time.sleep(0.2)
    rows = sorted(set(rows), key=lambda r: (r[0], r[1]))
    text = "currency,timestamp_ms,open,high,low,close\n" + "".join(f"{r[0]},{r[1]},{r[2]!r},{r[3]!r},{r[4]!r},{r[5]!r}\n"
                                                                  for r in rows)
    DVOL_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(DVOL_CSV, "wb", mtime=0) as fh:
        fh.write(text.encode())
    body = {"DATASET_ID": "DH3_DERIBIT_DVOL_1H_V0", "SOURCE": "https://www.deribit.com/api/v2/public/get_volatility_index_data",
            "CURRENCIES": ["BTC", "ETH"], "PERIOD": f"{K.DVOL_START}..{K.DVOL_END} (exclusive)", "RESOLUTION": "3600 s",
            "TIMESTAMP_SEMANTICS": "candle timestamp; DH3 uses the candle stamped T - 1h at decision time T (closed by T whether the stamp is the start or the end)",
            "ROWS": len(rows), "CSV": DVOL_CSV.name, "CSV_SHA256": D1.sha256_bytes(DVOL_CSV.read_bytes()),
            "RESPONSE_DIGESTS": digests, "FETCHED": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    (DVOL_DIR / "SOURCE_INVENTORY.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return body


def load_dvol(currency: str) -> dict:
    inv = json.loads((DVOL_DIR / "SOURCE_INVENTORY.json").read_text())
    payload = DVOL_CSV.read_bytes()
    if D1.sha256_bytes(payload) != inv["CSV_SHA256"]:
        raise RuntimeError("DVOL csv drifted")
    t, c = [], []
    for line in gzip.decompress(payload).decode().splitlines()[1:]:
        f = line.split(",")
        if f[0] == currency:
            t.append(int(f[1]))
            c.append(float(f[5]))
    return {"t": np.array(t, dtype=np.int64), "close": np.array(c)}


def dataset_identity() -> dict:
    out = {}
    for name, d in (("METRICS", METRICS_DIR), ("BOOK", BOOK_DIR), ("DVOL", DVOL_DIR)):
        inv = json.loads((d / "SOURCE_INVENTORY.json").read_text())
        out[name] = {"DATASET_ID": inv["DATASET_ID"], "DIGEST": inv.get("OBJECT_LIST_SHA256") or inv.get("CSV_SHA256")}
    from . import aggtrades as A
    inv = json.loads(A.INVENTORY.read_text())
    out["AGGTRADES"] = {"DATASET_ID": inv["DATASET_ID"], "DIGEST": inv["OBJECT_LIST_SHA256"],
                        "FEATURES_SHA256": inv["FEATURES_SHA256"]}
    from scripts.research.dh2 import data as D2
    out["DH2"] = D2.dataset_identity()
    out["OBJECTS_2025_2026"] = "none"
    return out
