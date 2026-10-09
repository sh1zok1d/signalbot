"""Pinned CORE BTCUSDT perpetual 1m 2020-01..2024-12 -> 5m grid with quote and taker-buy quote.

Every monthly object is the CORE_BTC_BINANCE_V0 inventory object, fetched through the R03 pinned fetcher
(SHA256 verified, 2025/2026 URLs refused). Nothing outside 2020-01-01 .. 2024-12-31 is read. No outcome here.
"""
from __future__ import annotations

import numpy as np

from scripts.research.owner_cards_r03 import data as RD

from . import constants as K

COLS = (0, 1, 2, 3, 4, 7, 10)   # open_time, open, high, low, close, quote volume, taker-buy quote volume


def core_digest() -> str:
    return RD.btc_dataset_digest()


def load_core_1m() -> dict[str, np.ndarray]:
    if core_digest() != K.CORE_ZIP_LIST_SHA256:
        raise SystemExit("CORE_DIGEST_DRIFT")
    cache = RD.cache_root() / "btc_1m"
    parsed = cache / f"dss2_1m_{K.CORE_ZIP_LIST_SHA256[:16]}.npz"
    if parsed.exists():
        z = np.load(parsed)
        panel = {k: z[k] for k in z.files}
    else:
        parts = []
        for spec in RD.btc_pinned_sources():
            path = RD._fetch(RD.S3_ORIGIN + spec["KEY"], cache / spec["FILENAME"], spec["SHA256"])
            parts.append(RD._read_kline_zip(path, spec["CSV"], COLS))
        raw = np.concatenate(parts, axis=0)
        raw = raw[np.argsort(raw[:, 0], kind="mergesort")]
        panel = {"open_ms": np.rint(raw[:, 0]).astype(np.int64), "open": raw[:, 1], "high": raw[:, 2],
                 "low": raw[:, 3], "close": raw[:, 4], "quote": raw[:, 5], "tbq": raw[:, 6]}
        cache.mkdir(parents=True, exist_ok=True)
        np.savez(parsed, **panel)
    t = panel["open_ms"]
    if int(t[0]) != K.SURFACE_START_MS or int(t[-1]) != K.SURFACE_END_MS - K.MINUTE_MS:
        raise SystemExit("CORE_BOUNDS")
    if not np.all(np.diff(t) == K.MINUTE_MS):
        raise SystemExit("CORE_1M_GAPS")
    if np.any(panel["low"] <= 0) or np.any(panel["high"] < panel["low"]):
        raise SystemExit("CORE_MALFORMED")
    if np.any(panel["tbq"] < -1e-9) or np.any(panel["tbq"] > panel["quote"] * (1 + 1e-9) + 1e-6):
        raise SystemExit("CORE_TAKER_MALFORMED")
    return panel


def to_5m(m1: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Aggregate the gapless 1m grid to 5m bars aligned on 5-minute UTC boundaries (aggregation only)."""
    n = m1["open_ms"].size
    if n % 5 or int(m1["open_ms"][0]) % K.BAR_MS:
        raise SystemExit("CORE_5M_ALIGNMENT")
    r = lambda a: a.reshape(-1, 5)
    return {"open_ms": r(m1["open_ms"])[:, 0].copy(), "open": r(m1["open"])[:, 0].copy(),
            "high": r(m1["high"]).max(axis=1), "low": r(m1["low"]).min(axis=1),
            "close": r(m1["close"])[:, -1].copy(), "quote": r(m1["quote"]).sum(axis=1),
            "tbq": r(m1["tbq"]).sum(axis=1)}
