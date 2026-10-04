"""DH2 data: free Binance Vision 5m klines, every object pinned by its published CHECKSUM.

- `DH2_BINANCE_UM_ALTS_5M_V0`: USD-M ETH, XRP, BNB, DOGE, SOL perps, first full month..2024-12.
- `DH2_BINANCE_SPOT_ALTS_5M_V0`: spot ETH, XRP, BNB, DOGE, SOL for the discovery months, and spot
  ETH, BNB, XRP 2017..2019 for the DH2-L3 replication surface.
- BTC reuses DH1's pinned surfaces (CORE_BTC perp, DH1 spot, DH1 BitMEX), loaded through DH1.

No object at or after 2025-01-01 is requested. No outcome is read here.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np

from beta.hist_series import Bars
from scripts.research.dh1 import data as D1

from . import constants as K

REPO = Path(__file__).resolve().parents[3]
UM_DIR = REPO / "docs/research_data/DH2_BINANCE_UM_ALTS_5M_V0"
SPOT_DIR = REPO / "docs/research_data/DH2_BINANCE_SPOT_ALTS_5M_V0"
UM_KEY = "data/futures/um/monthly/klines/{pair}/5m/{pair}-5m-{month}.zip"
SPOT_KEY = "data/spot/monthly/klines/{pair}/5m/{pair}-5m-{month}.zip"
ALTS = tuple(s for s in K.SYMBOLS if s != "BTC")


def months(first: str, last: str) -> list[str]:
    y, m = int(first[:4]), int(first[5:7])
    out = []
    while f"{y}-{m:02d}" <= last:
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def planned() -> dict:
    um = [(s, mo, UM_KEY.format(pair=K.PAIR[s], month=mo)) for s in ALTS
          for mo in months(K.DISCOVERY[s][0][:7], K.LAST_MONTH)]
    spot = [(s, mo, SPOT_KEY.format(pair=K.PAIR[s], month=mo)) for s in ALTS
            for mo in months(K.DISCOVERY[s][0][:7], K.LAST_MONTH)]
    spot += [(s, mo, SPOT_KEY.format(pair=K.PAIR[s], month=mo)) for s, first in K.SPOT_EARLY_FIRST_MONTH.items()
             for mo in months(first, K.SPOT_EARLY_LAST_MONTH)]
    for _, mo, _ in um + spot:
        D1._refuse_protected(dt.date.fromisoformat(mo + "-01"))
    return {"UM": um, "SPOT": spot}


def _fetch_verified(key: str, published: str | None = None) -> bytes:
    cache = D1.cache_root() / "dh2" / Path(key).name
    if published is None:
        published = D1._get(D1.VISION + key + ".CHECKSUM").decode().split()[0]
    payload = cache.read_bytes() if cache.exists() else b""
    if D1.sha256_bytes(payload) != published:      # absent or a partial cache write: fetch again
        payload = D1._get(D1.VISION + key)
        if D1.sha256_bytes(payload) != published:
            raise RuntimeError(f"{key}: digest mismatch")
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_suffix(".part")
        tmp.write_bytes(payload)
        tmp.replace(cache)
    return payload


def build_inventories(workers: int = 8) -> dict:
    plan = planned()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers) as pool:   # prefetch into the cache, digest-verified
        list(pool.map(lambda item: _fetch_verified(item[2]), plan["UM"] + plan["SPOT"]))
    out = {}
    for kind, directory, dataset in (("UM", UM_DIR, "DH2_BINANCE_UM_ALTS_5M_V0"),
                                     ("SPOT", SPOT_DIR, "DH2_BINANCE_SPOT_ALTS_5M_V0")):
        objects = []
        for sym, mo, key in plan[kind]:
            payload = _fetch_verified(key)
            raw = D1._parse_kline_zip(payload, Path(key).name.replace(".zip", ".csv"))
            objects.append({"SYMBOL": sym, "MONTH": mo, "KEY": key, "SHA256": D1.sha256_bytes(payload),
                            "BYTES": len(payload), "ROWS": int(raw.shape[0]), "FIRST_OPEN_MS": int(raw[0, 0]),
                            "LAST_OPEN_MS": int(raw[-1, 0]), "CHECKSUM_VERIFICATION": "VERIFIED"})
        body = {"DATASET_ID": dataset, "SOURCE": D1.VISION, "INTERVAL": "5m",
                "COLUMNS_USED": "open_time, open, high, low, close, volume, quote_volume, taker_buy_quote_volume",
                "OBJECTS": objects}
        body["OBJECT_LIST_SHA256"] = D1.sha256_bytes(json.dumps(
            [{"KEY": o["KEY"], "SHA256": o["SHA256"]} for o in objects], separators=(",", ":")).encode())
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "SOURCE_INVENTORY.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
        out[kind] = body
    return out


def _load(kind: str, symbol: str, first: str, last: str) -> dict:
    directory = UM_DIR if kind == "UM" else SPOT_DIR
    inv = json.loads((directory / "SOURCE_INVENTORY.json").read_text())
    parts = []
    for o in inv["OBJECTS"]:
        if o["SYMBOL"] != symbol or not (first <= o["MONTH"] <= last):
            continue
        D1._refuse_protected(dt.date.fromisoformat(o["MONTH"] + "-01"))
        payload = _fetch_verified(o["KEY"], o["SHA256"])
        parts.append(D1._parse_kline_zip(payload, Path(o["KEY"]).name.replace(".zip", ".csv")))
    if not parts:
        raise RuntimeError(f"DH2: no {kind} objects for {symbol} {first}..{last}")
    raw = np.concatenate(parts, axis=0)
    raw = raw[np.argsort(raw[:, 0], kind="mergesort")]
    t = np.rint(raw[:, 0]).astype(np.int64)
    if np.any(np.diff(t) <= 0):
        raise RuntimeError(f"DH2: {kind} {symbol} open times not strictly increasing")
    return {"open_ms": t, "open": raw[:, 1], "high": raw[:, 2], "low": raw[:, 3], "close": raw[:, 4],
            "volume": raw[:, 5], "quote": raw[:, 6], "taker_buy_quote": raw[:, 7]}


def discovery(symbol: str) -> tuple[Bars, dict]:
    start, end = K._ms(K.DISCOVERY[symbol][0]), K._ms(K.DISCOVERY_END)
    if symbol == "BTC":
        perp, spot = D1.load_binance_perp_5m(), D1.load_spot_5m()
    else:
        first = K.DISCOVERY[symbol][0][:7]
        perp = _load("UM", symbol, first, K.LAST_MONTH)
        spot = _load("SPOT", symbol, first, K.LAST_MONTH)
    bars = D1.to_bars(perp, start, end)
    return bars, D1.spot_on_grid(spot, bars)


def replication_spot(symbol: str) -> Bars:
    """Spot price bars for the DH2-L3 replication surface (spot replaces the perp: declared)."""
    start, end = K._ms(K.REPLICATION_SPOT[symbol][0]), K._ms(K.REPLICATION_END)
    spot = D1.load_spot_5m() if symbol == "BTC" else _load("SPOT", symbol, K.SPOT_EARLY_FIRST_MONTH[symbol],
                                                           K.SPOT_EARLY_LAST_MONTH)
    return D1.to_bars(spot, start, end)


def replication_btc() -> tuple[Bars, dict]:
    """The DH1 BTC replication surface (BitMEX XBTUSD trades + Binance spot), for DH2-L1 and DH2-B2."""
    return D1.surface("REPLICATION")


def dataset_identity() -> dict:
    um = json.loads((UM_DIR / "SOURCE_INVENTORY.json").read_text())
    spot = json.loads((SPOT_DIR / "SOURCE_INVENTORY.json").read_text())
    return {"DH1": D1.dataset_identity(),
            "UM_ALTS": {"DATASET_ID": um["DATASET_ID"], "OBJECT_LIST_SHA256": um["OBJECT_LIST_SHA256"], "OBJECTS": len(um["OBJECTS"])},
            "SPOT_ALTS": {"DATASET_ID": spot["DATASET_ID"], "OBJECT_LIST_SHA256": spot["OBJECT_LIST_SHA256"],
                          "OBJECTS": len(spot["OBJECTS"])},
            "OBJECTS_2025_2026": "none"}


def digest_of(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
