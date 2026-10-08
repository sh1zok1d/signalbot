"""Stream official USD-M BTCUSDT aggTrades into per-event aggregates.

The raw monthly zip is deleted after the checksum-verified reduction.
Aggressor side is not an input. Late labels are not an input.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Optional

import numpy as np

from . import constants as K


def assert_month_legal(month: str) -> None:
    if month < K.LOOKBACK_MONTH or month > K.LAST_MONTH:
        raise RuntimeError(f"refusing aggTrades month {month}")


def quote_notional(price: np.ndarray, quantity: np.ndarray) -> np.ndarray:
    """USD-M BTCUSDT quantity is base BTC. Quote notional is price times quantity."""
    return np.asarray(price, dtype=float) * np.asarray(quantity, dtype=float)


def empty_acc() -> dict:
    return {
        "pre60_notional": 0.0,
        "zone_notional_15m": 0.0,
        "total_notional_15m": 0.0,
        "seconds": set(),
        "tau_ms": None,
        "touch_in_zone": 0,
    }


def accumulate(times: np.ndarray, prices: np.ndarray, quantity: np.ndarray,
               events: list[dict], acc: dict) -> dict:
    """Add one time-sorted chunk. T is inclusive, D and the touch-bar end are exclusive.

    A trade may update more than one event. That is recorded, not removed.
    """
    if times.size == 0:
        return {"multi_event_trades": 0, "assigned_trades": 0}
    times = np.asarray(times)
    prices = np.asarray(prices, dtype=float)
    quotes = quote_notional(prices, quantity)
    t0 = int(times[0])
    t1 = int(times[-1]) + 1
    active = [ev for ev in events if ev["pre_ms"] < t1 and ev["d_ms"] > t0]
    hits = np.zeros(times.size, dtype=np.int16)
    for ev in active:
        m = (times >= ev["pre_ms"]) & (times < ev["d_ms"])
        if not np.any(m):
            continue
        hits[m] += 1
        tt = times[m]
        pp = prices[m]
        qq = quotes[m]
        pre = tt < ev["t_ms"]
        post = ~pre
        key = ev["key"]
        bucket = acc.setdefault(key, empty_acc())
        if np.any(pre):
            bucket["pre60_notional"] += float(qq[pre].sum())
        if np.any(post):
            bucket["total_notional_15m"] += float(qq[post].sum())
        in_zone = (pp >= ev["zone_low"]) & (pp <= ev["zone_high"])
        zpost = post & in_zone
        if np.any(zpost):
            bucket["zone_notional_15m"] += float(qq[zpost].sum())
            idx = (tt[zpost] // 1000) - (ev["t_ms"] // 1000)
            idx = idx[(idx >= 0) & (idx < K.ACTIVE_SECONDS_DENOM)]
            bucket["seconds"].update(int(v) for v in idx)
        touch = (tt >= ev["t_ms"]) & (tt < ev["touch_end_ms"]) & in_zone
        if np.any(touch):
            tau = int(tt[touch].min())
            prev = bucket["tau_ms"]
            bucket["tau_ms"] = tau if prev is None else min(prev, tau)
            bucket["touch_in_zone"] += int(touch.sum())
    return {
        "multi_event_trades": int(np.sum(hits >= 2)),
        "assigned_trades": int(np.sum(hits >= 1)),
    }


def finalize_record(key: str, bucket: dict) -> dict:
    return {
        "key": key,
        "pre60_notional": float(bucket["pre60_notional"]),
        "zone_notional_15m": float(bucket["zone_notional_15m"]),
        "total_notional_15m": float(bucket["total_notional_15m"]),
        "zone_active_seconds": int(len(bucket["seconds"])),
        "tau_ms": bucket["tau_ms"],
        "touch_in_zone": int(bucket["touch_in_zone"]),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 22), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamps_ms(values: np.ndarray) -> np.ndarray:
    out = np.asarray(values, dtype=np.int64)
    if out.size and int(out.max()) > 10 ** 14:
        out = out // 1000
    return out


def read_zip_header(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        name = archive.namelist()[0]
        with archive.open(name) as handle:
            first = handle.readline()
    text = first.decode("utf-8", errors="replace").strip()
    header = text[:1].isalpha()
    if header and text != K.UM_HEADER:
        raise RuntimeError(f"unexpected aggTrades header: {text}")
    return {"inner_name": name, "header": header, "first": text}


def notional_audit(prices: np.ndarray, quantity: np.ndarray) -> dict:
    """Outcome-blind unit check. Quantity is BTC, so price times quantity is USDT."""
    quotes = quote_notional(prices, quantity)
    finite = np.isfinite(quotes) & np.isfinite(prices) & (prices > 0) & (quantity > 0)
    if int(finite.sum()) < 100:
        raise RuntimeError("aggTrades sample is too small to audit notional units")
    med_px = float(np.median(prices[finite]))
    med_qty = float(np.median(quantity[finite]))
    med_quote = float(np.median(quotes[finite]))
    if not (1_000.0 <= med_px <= 200_000.0 and 1.0 <= med_quote <= 5.0e7 and med_qty > 0.0):
        raise RuntimeError(
            f"notional unit audit failed: median price {med_px}, qty {med_qty}, quote {med_quote}"
        )
    return {"median_price": med_px, "median_quantity": med_qty, "median_quote_notional": med_quote}


def stream_zip(path: Path, events: list[dict], acc: dict, *, surface_end_ms: int) -> dict:
    import pandas as pd
    meta = read_zip_header(path)
    stats = {"rows": 0, "dropped_at_or_after_surface": 0, "multi_event_trades": 0, "assigned_trades": 0}
    audited = False
    with zipfile.ZipFile(path) as archive:
        with archive.open(meta["inner_name"]) as handle:
            reader = pd.read_csv(
                handle, header=0 if meta["header"] else None, usecols=[K.PRICE_COL, K.QTY_COL, K.TIME_COL],
                chunksize=2_000_000, names=None if meta["header"] else list(range(K.N_UM_COLUMNS)),
            )
            for chunk in reader:
                cols = list(chunk.columns)
                times = _timestamps_ms(chunk[cols[2]].to_numpy())
                prices = chunk[cols[0]].to_numpy(dtype=float)
                quantity = chunk[cols[1]].to_numpy(dtype=float)
                late = times >= surface_end_ms
                stats["dropped_at_or_after_surface"] += int(late.sum())
                if np.any(late):
                    keep = ~late
                    times, prices, quantity = times[keep], prices[keep], quantity[keep]
                if times.size == 0:
                    continue
                if not audited:
                    stats["notional_audit"] = notional_audit(prices[:100_000], quantity[:100_000])
                    audited = True
                got = accumulate(times, prices, quantity, events, acc)
                stats["rows"] += int(times.size)
                stats["multi_event_trades"] += got["multi_event_trades"]
                stats["assigned_trades"] += got["assigned_trades"]
    stats["header"] = meta["header"]
    if stats["dropped_at_or_after_surface"]:
        raise RuntimeError("aggTrades file contains a timestamp at or after 2025-01-01")
    return stats
