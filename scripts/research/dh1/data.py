"""DH1 data: free public archives only, every byte SHA256-pinned in a committed inventory.

- Perp, discovery: CORE_BTC_BINANCE_V0 (Binance USD-M BTCUSDT 1m, 2020-01..2024-12), read through
  the frozen R03 helpers (imported unchanged) and aggregated to 5m with the taker-buy quote volume.
- Spot, both eras: Binance spot BTCUSDT 5m monthly klines 2017-08..2024-12
  (`DH1_BINANCE_SPOT_BTCUSDT_5M_V0`, inventory built from the archive's CHECKSUM files).
- Perp, replication: BitMEX XBTUSD public trades 2017-08-01..2019-12-31, aggregated to 5m with the
  taker side (`DH1_BITMEX_XBTUSD_TRADES_5M_V0`); daily file digests and the canonical 5m file are
  committed.

No object at or after 2025-01-01 is ever requested. This module reads no outcome: it returns bars.
"""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import io
import json
import os
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from beta.hist_series import Bars
from scripts.research.owner_cards_r03 import data as RD

from . import constants as K

REPO = Path(__file__).resolve().parents[3]
DATA_DIR = REPO / "docs/research_data"
SPOT_DIR = DATA_DIR / "DH1_BINANCE_SPOT_BTCUSDT_5M_V0"
SPOT_INVENTORY = SPOT_DIR / "SOURCE_INVENTORY.json"
BITMEX_DIR = DATA_DIR / "DH1_BITMEX_XBTUSD_TRADES_5M_V0"
BITMEX_INVENTORY = BITMEX_DIR / "SOURCE_INVENTORY.json"
BITMEX_CANONICAL = BITMEX_DIR / "xbtusd_5m.csv.gz"
VISION = "https://data.binance.vision/"
BITMEX_ORIGIN = "https://s3-eu-west-1.amazonaws.com/public.bitmex.com/data/trade/"
SPOT_KEY = "data/spot/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-{month}.zip"
BITMEX_COLUMNS = ("open_time_ms", "open", "high", "low", "close", "volume_xbt", "quote_usd",
                  "taker_buy_quote_usd", "trades")
UA = {"User-Agent": "signalbot-research/dh1"}


def cache_root() -> Path:
    return Path(os.environ.get("DH1_CACHE", "/tmp/dh1_cache"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _refuse_protected(period_start: dt.date) -> None:
    if period_start >= dt.date.fromisoformat(K.PROTECTED_FROM):
        raise RuntimeError(f"DH1 refuses an object from {period_start} (protected from {K.PROTECTED_FROM})")


def _get(url: str, *, attempts: int = 4) -> bytes:
    last = None
    for k in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as response:
                return response.read()
        except Exception as exc:  # network retry with backoff
            last = exc
            import time
            time.sleep(2 ** (k + 1))
    raise RuntimeError(f"fetch failed for {url}: {last}")


# ---------------------------------------------------------------- spot 5m klines
def spot_months() -> list[str]:
    out, y, m = [], 2017, 8
    while (y, m) <= (2024, 12):
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    if out[0] != K.SPOT_FIRST_MONTH or out[-1] != K.SPOT_LAST_MONTH:
        raise RuntimeError("spot month list drifted")
    return out


def _parse_kline_zip(payload: bytes, csv_name: str) -> np.ndarray:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if archive.namelist() != [csv_name]:
            raise RuntimeError(f"unexpected members in {csv_name}")
        body = archive.read(csv_name)
    if body[:1].isalpha():
        body = body.split(b"\n", 1)[1]
    raw = np.loadtxt(io.BytesIO(body), delimiter=",", usecols=(0, 1, 2, 3, 4, 5, 7, 10), ndmin=2)
    return raw


def build_spot_inventory() -> dict:
    """Download every spot month once, verify it against the archive CHECKSUM, pin the digest."""
    objects = []
    cache = cache_root() / "spot_5m"
    cache.mkdir(parents=True, exist_ok=True)
    for month in spot_months():
        _refuse_protected(dt.date.fromisoformat(month + "-01"))
        key = SPOT_KEY.format(month=month)
        published = _get(VISION + key + ".CHECKSUM").decode().split()[0]
        payload = _get(VISION + key)
        if sha256_bytes(payload) != published:
            raise RuntimeError(f"spot {month}: checksum mismatch")
        (cache / Path(key).name).write_bytes(payload)
        raw = _parse_kline_zip(payload, Path(key).name.replace(".zip", ".csv"))
        objects.append({"MONTH": month, "KEY": key, "SHA256": published, "BYTES": len(payload), "ROWS": int(raw.shape[0]),
                        "FIRST_OPEN_MS": int(raw[0, 0]), "LAST_OPEN_MS": int(raw[-1, 0]),
                        "CHECKSUM_VERIFICATION": "VERIFIED"})
    body = {"DATASET_ID": "DH1_BINANCE_SPOT_BTCUSDT_5M_V0", "SOURCE": VISION + "data/spot/monthly/klines/BTCUSDT/5m/",
            "INSTRUMENT": "Binance spot BTCUSDT", "INTERVAL": "5m", "MONTHS": f"{spot_months()[0]}..{spot_months()[-1]}",
            "COLUMNS_USED": "open_time, open, high, low, close, volume, quote_volume, taker_buy_quote_volume",
            "OBJECTS": objects}
    body["OBJECT_LIST_SHA256"] = sha256_bytes(json.dumps(
        [{"MONTH": o["MONTH"], "SHA256": o["SHA256"]} for o in objects], separators=(",", ":")).encode())
    SPOT_DIR.mkdir(parents=True, exist_ok=True)
    SPOT_INVENTORY.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return body


def load_spot_5m() -> dict:
    """open_ms, quote, taker_buy_quote (and OHLC) for every pinned spot month, digest-verified."""
    inv = json.loads(SPOT_INVENTORY.read_text())
    cache = cache_root() / "spot_5m"
    cache.mkdir(parents=True, exist_ok=True)
    parts = []
    for obj in inv["OBJECTS"]:
        _refuse_protected(dt.date.fromisoformat(obj["MONTH"] + "-01"))
        path = cache / Path(obj["KEY"]).name
        payload = path.read_bytes() if path.exists() else _get(VISION + obj["KEY"])
        if sha256_bytes(payload) != obj["SHA256"]:
            raise RuntimeError(f"spot {obj['MONTH']}: digest drifted")
        if not path.exists():
            path.write_bytes(payload)
        parts.append(_parse_kline_zip(payload, Path(obj["KEY"]).name.replace(".zip", ".csv")))
    raw = np.concatenate(parts, axis=0)
    raw = raw[np.argsort(raw[:, 0], kind="mergesort")]
    t = np.rint(raw[:, 0]).astype(np.int64)
    if np.any(np.diff(t) <= 0):
        raise RuntimeError("spot open times not strictly increasing")
    return {"open_ms": t, "open": raw[:, 1], "high": raw[:, 2], "low": raw[:, 3], "close": raw[:, 4],
            "volume": raw[:, 5], "quote": raw[:, 6], "taker_buy_quote": raw[:, 7]}


# ---------------------------------------------------------------- Binance perp (CORE_BTC 1m -> 5m)
def load_binance_perp_5m() -> dict:
    """CORE_BTC_BINANCE_V0 1m (2020-01..2024-12) aggregated to 5m; complete 5m bins only."""
    cache = cache_root() / f"core_btc_5m_{RD.btc_dataset_digest()[:16]}.npz"
    if cache.exists():
        loaded = np.load(cache)
        return {k: loaded[k] for k in loaded.files}
    parts = []
    for spec in RD.btc_pinned_sources():
        path = RD._fetch(RD.S3_ORIGIN + spec["KEY"], RD.cache_root() / "btc_1m" / spec["FILENAME"], spec["SHA256"])
        parts.append(RD._read_kline_zip(path, spec["CSV"], (0, 1, 2, 3, 4, 5, 7, 10)))
    raw = np.concatenate(parts, axis=0)
    raw = raw[np.argsort(raw[:, 0], kind="mergesort")]
    t1 = np.rint(raw[:, 0]).astype(np.int64)
    out = aggregate_1m_to_5m(t1, raw[:, 1], raw[:, 2], raw[:, 3], raw[:, 4], raw[:, 5], raw[:, 6], raw[:, 7])
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, **out)
    return out


def aggregate_1m_to_5m(t, o, h, lo, c, vol, quote, tbq) -> dict:
    """Complete 5m bins (all five minutes present) only; nothing is filled."""
    t = np.asarray(t, dtype=np.int64)
    if np.any(np.diff(t) <= 0):
        raise RuntimeError("1m open times not strictly increasing")
    b = t // K.BAR_MS
    starts = np.flatnonzero(np.r_[True, b[1:] != b[:-1]])
    ends = np.r_[starts[1:], t.size]
    full = (ends - starts) == 5
    s, e = starts[full], ends[full]
    return {"open_ms": b[s] * K.BAR_MS, "open": o[s], "high": np.maximum.reduceat(h, starts)[full],
            "low": np.minimum.reduceat(lo, starts)[full], "close": c[e - 1],
            "volume": np.add.reduceat(vol, starts)[full], "quote": np.add.reduceat(quote, starts)[full],
            "taker_buy_quote": np.add.reduceat(tbq, starts)[full]}


# ---------------------------------------------------------------- BitMEX XBTUSD trades -> 5m
def bitmex_days() -> list[dt.date]:
    d0, d1 = dt.date.fromisoformat(K.BITMEX_FIRST_DAY), dt.date.fromisoformat(K.BITMEX_LAST_DAY)
    return [d0 + dt.timedelta(days=k) for k in range((d1 - d0).days + 1)]


def aggregate_bitmex_day(payload: bytes, day: dt.date) -> tuple[list, int]:
    """XBTUSD trades of one daily file -> 5m rows (bins with at least one trade)."""
    import pandas as pd
    frame = pd.read_csv(io.BytesIO(payload), compression="gzip",
                        usecols=["timestamp", "symbol", "side", "price", "homeNotional", "foreignNotional"],
                        dtype={"symbol": str, "side": str})
    frame = frame[frame["symbol"] == "XBTUSD"]
    if frame.empty:
        return [], 0
    ts = pd.to_datetime(frame["timestamp"].str.replace("D", " ", regex=False), format="%Y-%m-%d %H:%M:%S.%f")
    ms = ts.to_numpy().astype("datetime64[ms]").astype(np.int64)
    day0 = int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp() * 1000)
    if ms.min() < day0 or ms.max() >= day0 + K.DAY_MS:
        raise RuntimeError(f"BitMEX {day}: trade outside its day")
    order = np.argsort(ms, kind="mergesort")
    ms = ms[order]
    price = frame["price"].to_numpy(dtype=float)[order]
    home = frame["homeNotional"].to_numpy(dtype=float)[order]
    foreign = frame["foreignNotional"].to_numpy(dtype=float)[order]
    buy = (frame["side"].to_numpy() == "Buy")[order]
    b = ms // K.BAR_MS
    starts = np.flatnonzero(np.r_[True, b[1:] != b[:-1]])
    ends = np.r_[starts[1:], ms.size]
    rows = []
    hi = np.maximum.reduceat(price, starts)
    lo = np.minimum.reduceat(price, starts)
    vol = np.add.reduceat(home, starts)
    quote = np.add.reduceat(foreign, starts)
    tbq = np.add.reduceat(np.where(buy, foreign, 0.0), starts)
    for k, (s, e) in enumerate(zip(starts, ends)):
        rows.append((int(b[s] * K.BAR_MS), float(price[s]), float(hi[k]), float(lo[k]), float(price[e - 1]),
                     float(vol[k]), float(quote[k]), float(tbq[k]), int(e - s)))
    return rows, int(ms.size)


def build_bitmex(workers: int = 6) -> dict:
    """Download every day once, pin its digest, aggregate XBTUSD to 5m, write the canonical file."""
    days = bitmex_days()
    for d in days:
        _refuse_protected(d)

    def one(day: dt.date):
        url = BITMEX_ORIGIN + day.strftime("%Y%m%d") + ".csv.gz"
        payload = _get(url)
        rows, n = aggregate_bitmex_day(payload, day)
        return day, url, sha256_bytes(payload), len(payload), n, rows

    objects, all_rows = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for day, url, digest, size, n, rows in pool.map(one, days):
            objects.append({"DAY": day.isoformat(), "URL": url, "SHA256": digest, "BYTES": size, "XBTUSD_TRADES": n,
                            "BINS": len(rows)})
            all_rows.extend(rows)
    all_rows.sort(key=lambda r: r[0])
    text = io.StringIO()
    text.write(",".join(BITMEX_COLUMNS) + "\n")
    for r in all_rows:
        text.write(f"{r[0]},{r[1]!r},{r[2]!r},{r[3]!r},{r[4]!r},{r[5]!r},{r[6]!r},{r[7]!r},{r[8]}\n")
    BITMEX_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.GzipFile(BITMEX_CANONICAL, "wb", mtime=0) as handle:
        handle.write(text.getvalue().encode())
    body = {"DATASET_ID": "DH1_BITMEX_XBTUSD_TRADES_5M_V0", "SOURCE": BITMEX_ORIGIN, "INSTRUMENT": "BitMEX XBTUSD (inverse perpetual)",
            "DAYS": f"{days[0]}..{days[-1]}", "AGGREGATION": (
                "trades of symbol XBTUSD only; 5m bins by trade timestamp (UTC); open/close = first/last trade price, "
                "high/low = max/min trade price; volume_xbt = sum homeNotional; quote_usd = sum foreignNotional; "
                "taker_buy_quote_usd = sum foreignNotional where side == Buy (BitMEX side is the taker side); bins "
                "without a trade are absent"),
            "COLUMNS": list(BITMEX_COLUMNS), "OBJECTS": objects, "ROWS": len(all_rows),
            "CANONICAL_FILE": BITMEX_CANONICAL.name, "CANONICAL_SHA256": sha256_bytes(BITMEX_CANONICAL.read_bytes())}
    body["OBJECT_LIST_SHA256"] = sha256_bytes(json.dumps(
        [{"DAY": o["DAY"], "SHA256": o["SHA256"]} for o in objects], separators=(",", ":")).encode())
    BITMEX_INVENTORY.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    return body


def load_bitmex_5m() -> dict:
    inv = json.loads(BITMEX_INVENTORY.read_text())
    payload = BITMEX_CANONICAL.read_bytes()
    if sha256_bytes(payload) != inv["CANONICAL_SHA256"]:
        raise RuntimeError("BitMEX canonical 5m file drifted")
    raw = np.loadtxt(io.BytesIO(gzip.decompress(payload)), delimiter=",", skiprows=1, ndmin=2)
    return {"open_ms": np.rint(raw[:, 0]).astype(np.int64), "open": raw[:, 1], "high": raw[:, 2], "low": raw[:, 3],
            "close": raw[:, 4], "volume": raw[:, 5], "quote": raw[:, 6], "taker_buy_quote": raw[:, 7]}


# ---------------------------------------------------------------- grids
def to_bars(panel: dict, start_ms: int, end_ms: int) -> Bars:
    """A contiguous 5m grid [start, end); missing bars are NaN, nothing is filled."""
    n = (end_ms - start_ms) // K.BAR_MS
    cols = {c: np.full(n, np.nan) for c in ("open", "high", "low", "close", "volume", "quote", "taker_buy_quote")}
    t = panel["open_ms"]
    keep = (t >= start_ms) & (t < end_ms)
    idx = ((t[keep] - start_ms) // K.BAR_MS).astype(np.int64)
    for c in cols:
        cols[c][idx] = panel[c][keep]
    return Bars(t0=int(start_ms), oi=np.full(n, np.nan), **cols)


def spot_on_grid(spot: dict, bars: Bars) -> dict:
    n = bars.n
    out = {"quote": np.full(n, np.nan), "taker_buy_quote": np.full(n, np.nan)}
    t = spot["open_ms"]
    keep = (t >= bars.t0) & (t < bars.end_ms)
    idx = ((t[keep] - bars.t0) // K.BAR_MS).astype(np.int64)
    out["quote"][idx] = spot["quote"][keep]
    out["taker_buy_quote"][idx] = spot["taker_buy_quote"][keep]
    return out


def surface(name: str) -> tuple[Bars, dict]:
    """(perp bars, spot arrays on the same grid) for DISCOVERY or REPLICATION."""
    s = K.SURFACES[name]
    start, end = K._ms(s["DATA_START"]), K._ms(s["END"])
    if end > K._ms(K.PROTECTED_FROM):
        raise RuntimeError("DH1 surface reaches the protected window")
    perp = load_binance_perp_5m() if name == "DISCOVERY" else load_bitmex_5m()
    bars = to_bars(perp, start, end)
    return bars, spot_on_grid(load_spot_5m(), bars)


def dataset_identity() -> dict:
    spot = json.loads(SPOT_INVENTORY.read_text())
    bitmex = json.loads(BITMEX_INVENTORY.read_text())
    return {
        "PERP_DISCOVERY": {"DATASET_ID": "CORE_BTC_BINANCE_V0", "ZIP_LIST_SHA256": RD.btc_dataset_digest(),
                           "MONTHS": "2020-01..2024-12"},
        "SPOT": {"DATASET_ID": spot["DATASET_ID"], "OBJECT_LIST_SHA256": spot["OBJECT_LIST_SHA256"], "MONTHS": spot["MONTHS"]},
        "PERP_REPLICATION": {"DATASET_ID": bitmex["DATASET_ID"], "OBJECT_LIST_SHA256": bitmex["OBJECT_LIST_SHA256"],
                             "CANONICAL_SHA256": bitmex["CANONICAL_SHA256"], "DAYS": bitmex["DAYS"]},
        "OBJECTS_2025_2026": "none",
    }
