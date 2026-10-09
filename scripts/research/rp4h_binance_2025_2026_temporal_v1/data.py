"""Binance USD-M BTCUSDT 5m objects for Unit B: manifest-verified, E1-guarded by the product rule, no fill."""

from __future__ import annotations

import hashlib
import io
import json
import os
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from beta.history_data import drop_protected, in_protected_window, url_refusal

from . import constants as K

ROOT = Path(__file__).resolve().parents[3]


def _cache() -> Path:
    return Path(os.environ.get("RP4H_B_CACHE", "/tmp/rp4h_b_cache"))


def manifest() -> list:
    body = json.loads((ROOT / K.MANIFEST).read_text())
    objs = body["OBJECTS"]
    digest = hashlib.sha256(json.dumps(objs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != K.OBJECT_LIST_SHA256:
        raise SystemExit("MANIFEST_MISMATCH")
    for o in objs:
        if url_refusal(K.VISION + o["key"]) is not None:
            raise SystemExit(f"MANIFEST_CONTAINS_PROTECTED_OBJECT {o['key']}")
    return objs


def fetch(obj: dict) -> bytes:
    url = K.VISION + obj["key"]
    why = url_refusal(url)
    if why is not None:                                   # refused before any request (fail closed)
        raise SystemExit(f"REFUSED_PROTECTED_OBJECT {obj['key']} {why}")
    path = _cache() / obj["key"]
    payload = path.read_bytes() if path.exists() else None
    if payload is None:
        last = None
        for _ in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "rp4h-b"}), timeout=120) as r:
                    payload = r.read()
                break
            except Exception as exc:  # noqa: BLE001
                last = exc
        if payload is None:
            raise SystemExit(f"FETCH_FAILED {obj['key']} {last}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    if hashlib.sha256(payload).hexdigest() != obj["sha256"]:
        raise SystemExit(f"OBJECT_HASH_MISMATCH {obj['key']}")
    return payload


def parse(payload: bytes) -> list:
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        text = z.read(z.namelist()[0]).decode()
    rows = []
    for line in text.splitlines():
        if not line or not line[0].isdigit():
            continue
        f = line.split(",")
        t = int(f[0])
        if t > 10 ** 14:                                  # microsecond open times
            t //= 1000
        rows.append({"open_ms": t, "high": float(f[2]), "low": float(f[3]), "close": float(f[4])})
    return rows


def series_from_rows(rows: list) -> dict:
    """Every published row is a bar; rows inside a protected window are dropped (the product rule);
    rows outside the surface are refused; duplicates and off-grid times are refused."""
    rows = drop_protected(rows, "open_ms")
    rows.sort(key=lambda r: r["open_ms"])
    t = np.array([r["open_ms"] for r in rows], dtype=np.int64)
    if t.size == 0:
        raise SystemExit("EMPTY_SERIES")
    if np.any(np.diff(t) <= 0):
        raise SystemExit("DUPLICATE_OR_UNSORTED_OPEN")
    if np.any(t % K.BAR_MS != 0):
        raise SystemExit("OFF_GRID_OPEN")
    if t[0] < K.SURFACE_START_MS or t[-1] >= K.SURFACE_END_MS:
        raise SystemExit("ROW_OUTSIDE_SURFACE")
    if any(in_protected_window(int(x)) for x in t):
        raise SystemExit("PROTECTED_ROW_PRESENT")
    return {"open_ms": t, "high": np.array([r["high"] for r in rows]), "low": np.array([r["low"] for r in rows]),
            "close": np.array([r["close"] for r in rows])}


def load_series() -> dict:
    objs = manifest()
    with ThreadPoolExecutor(max_workers=8) as pool:
        payloads = list(pool.map(fetch, objs))
    return series_from_rows([r for p in payloads for r in parse(p)])


def holes(open_ms: np.ndarray) -> np.ndarray:
    """Absent clock slots over the whole surface [start, end)."""
    full = np.arange(K.SURFACE_START_MS, K.SURFACE_END_MS, K.BAR_MS, dtype=np.int64)
    return np.setdiff1d(full, open_ms, assume_unique=True)


def census(series: dict) -> dict:
    h = holes(series["open_ms"])
    protected = int(sum(1 for x in h if in_protected_window(int(x))))
    return {"rows": int(series["open_ms"].size), "holes": int(h.size), "holes_in_e1_window": protected,
            "holes_outside_e1_window": int(h.size - protected),
            "holes_sha256": hashlib.sha256(h.astype("<i8").tobytes()).hexdigest(),
            "first_open_ms": int(series["open_ms"][0]), "last_open_ms": int(series["open_ms"][-1])}


def place(series: dict) -> dict:
    """The complete 5m grid over the whole surface; holes stay NaN; nothing is filled."""
    n = int((K.SURFACE_END_MS - K.SURFACE_START_MS) // K.BAR_MS)
    slot = (series["open_ms"] - K.SURFACE_START_MS) // K.BAR_MS
    out = {"grid_open": K.SURFACE_START_MS + np.arange(n, dtype=np.int64) * K.BAR_MS, "slots": n,
           "occupied": int(slot.size), "holes": int(n - slot.size)}
    for c in ("high", "low", "close"):
        arr = np.full(n, np.nan)
        arr[slot] = series[c]
        out[c] = arr
    return out


def anchor_mask(grid_open: np.ndarray) -> np.ndarray:
    """Parent phase (floor modulo from 2020-01-01): bar opens at minute 10 mod 15; T before the surface end."""
    idx = (grid_open - K.PHASE_ORIGIN_MS) // K.BAR_MS
    return ((idx % 3) == 2) & (grid_open + K.BAR_MS < K.SURFACE_END_MS)
