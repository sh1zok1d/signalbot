"""Pinned Binance USD-M BTCUSDT bookDepth, 2023–2024.

The archive row is timestamp, percentage, depth, notional. Percentage is the
cumulative band around the contemporaneous mid: −1..−5 bids, +1..+5 asks.
There is no price ladder, no best bid or ask, and no midpoint column.

This module reads the ±1% notional only. That is the narrowest native band.
It does not difference wider bands into a reconstructed ladder, and it does
not forward-fill a gap. A snapshot is usable only when its own timestamp is
inside the frozen staleness of the decision time.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import math
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import numpy as np

from scripts.research.dh1 import data as D1
from scripts.research.dh3 import data as DH3

from . import constants as K

REPO = Path(__file__).resolve().parents[3]
INVENTORY = REPO / K.BOOK_INVENTORY


def _ms_utc(text: str) -> int:
    """Naive archive timestamps are UTC. A zoned stamp is refused."""
    if text.endswith("Z") or "+" in text[10:]:
        raise ValueError(f"unexpected zoned book timestamp {text}")
    parsed = dt.datetime.fromisoformat(text).replace(tzinfo=dt.timezone.utc)
    return int(parsed.timestamp() * 1000)


def parse_book_csv(text: str) -> dict:
    """One day. Returns parallel arrays for snapshots that have a ±1% row.

    A repeated percentage at the same timestamp with a different notional or
    depth marks that snapshot unusable. Negative depth or notional does too.
    """
    bands: set[int] = set()
    narrower = False
    bid: dict[int, float] = {}
    ask: dict[int, float] = {}
    bad: set[int] = set()
    n_rows = 0
    for line in text.splitlines():
        if not line or line[0] < "0" or line[0] > "9":
            continue
        n_rows += 1
        parts = line.split(",")
        if len(parts) != 4:
            raise ValueError("bookDepth row does not have 4 columns")
        pct = int(float(parts[1]))
        if abs(float(parts[1]) - pct) > 1e-9:
            narrower = True
            bands.add(pct)
            continue
        bands.add(pct)
        if 0 < abs(pct) < K.DEPTH_BAND_PCT:
            narrower = True
        if pct not in (-K.DEPTH_BAND_PCT, K.DEPTH_BAND_PCT):
            continue
        ts = _ms_utc(parts[0])
        depth = float(parts[2])
        notional = float(parts[3])
        if depth < 0.0 or notional < 0.0 or not math.isfinite(depth) or not math.isfinite(notional):
            bad.add(ts)
            continue
        store = bid if pct < 0 else ask
        previous = store.get(ts)
        if previous is None:
            store[ts] = notional
        elif previous != notional:
            bad.add(ts)
    times = sorted(set(bid) | set(ask) | bad)
    out_t = np.empty(len(times), dtype=np.int64)
    out_b = np.full(len(times), np.nan)
    out_a = np.full(len(times), np.nan)
    for i, ts in enumerate(times):
        out_t[i] = ts
        if ts in bad:
            continue
        if ts in bid and ts in ask:
            out_b[i] = bid[ts]
            out_a[i] = ask[ts]
    return {
        "t": out_t,
        "bid": out_b,
        "ask": out_a,
        "bands": bands,
        "narrower": narrower,
        "rows": n_rows,
    }


def _refuse_day(day: str, key: str) -> None:
    if day >= "2025-01-01" or "2025" in key or "2026" in key:
        raise RuntimeError(f"book loader refuses {key}")
    if not key.startswith(f"data/futures/um/daily/bookDepth/{K.BOOK_PAIR}/"):
        raise RuntimeError(f"unexpected book key {key}")


def inventory_identity(inv: dict) -> str:
    raw = json.dumps(
        [[o["KEY"], o.get("SHA256")] for o in inv["OBJECTS"]],
        separators=(",", ":"),
    ).encode()
    return D1.sha256_bytes(raw)


def load_btc_book(workers: int = 8) -> tuple[dict, dict]:
    """Load every verified BTC day. Missing archive days stay missing. No 2025/2026."""
    inv = json.loads(INVENTORY.read_text())
    if inv.get("DATASET_ID") != K.BOOK_DATASET_ID:
        raise RuntimeError("book dataset id drifted")
    digest = inventory_identity(inv)
    if digest != K.BOOK_OBJECT_LIST_SHA256 or digest != inv.get("OBJECT_LIST_SHA256"):
        raise RuntimeError("book object-list digest drifted")
    objects = [o for o in inv["OBJECTS"] if o.get("SYMBOL") == K.BOOK_SYMBOL]
    if not objects:
        raise RuntimeError("BTC book inventory is empty")
    verified = []
    missing_days = []
    for obj in objects:
        _refuse_day(obj["DAY"], obj["KEY"])
        if obj.get("STATUS") != "VERIFIED":
            missing_days.append(obj["DAY"])
            continue
        verified.append(obj)

    def one(obj: dict) -> dict:
        _refuse_day(obj["DAY"], obj["KEY"])
        payload, _sha = DH3._fetch(obj["KEY"], "dh3_book", obj["SHA256"])
        if D1.sha256_bytes(payload) != obj["SHA256"]:
            raise RuntimeError(f"sha drifted after fetch {obj['KEY']}")
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            names = zf.namelist()
            if len(names) != 1:
                raise RuntimeError(f"zip members {obj['KEY']}: {names}")
            parsed = parse_book_csv(zf.read(names[0]).decode())
        parsed["day"] = obj["DAY"]
        return parsed

    with ThreadPoolExecutor(max_workers=workers) as pool:
        parts = list(pool.map(one, verified))
    bands: set[int] = set()
    narrower = False
    chunks_t, chunks_b, chunks_a = [], [], []
    for part in parts:
        bands |= set(part["bands"])
        narrower = narrower or bool(part["narrower"])
        if part["t"].size:
            chunks_t.append(part["t"])
            chunks_b.append(part["bid"])
            chunks_a.append(part["ask"])
    if narrower or any(abs(int(b)) < K.DEPTH_BAND_PCT and int(b) != 0 for b in bands):
        raise RuntimeError(
            "LEVEL_LIQUIDITY_OBSERVABILITY_INSUFFICIENT: a band narrower than ±1% is present; "
            f"bands={sorted(bands)}"
        )
    if K.DEPTH_BAND_PCT not in {abs(int(b)) for b in bands}:
        raise RuntimeError(f"±1% band missing; bands={sorted(bands)}")
    t = np.concatenate(chunks_t) if chunks_t else np.zeros(0, dtype=np.int64)
    bid = np.concatenate(chunks_b) if chunks_b else np.zeros(0, dtype=float)
    ask = np.concatenate(chunks_a) if chunks_a else np.zeros(0, dtype=float)
    order = np.argsort(t, kind="mergesort")
    t, bid, ask = t[order], bid[order], ask[order]
    if t.size and (int(t[0]) < 0 or int(t[-1]) >= K.SURFACE_END_MS):
        raise RuntimeError("book timestamp outside 2023–2024")
    # Identical timestamps from overlapping days are unusable rather than averaged.
    if t.size > 1:
        dup = np.flatnonzero(np.diff(t) == 0)
        for i in dup:
            bid[i] = np.nan
            ask[i] = np.nan
            bid[i + 1] = np.nan
            ask[i + 1] = np.nan
    gaps = np.diff(t.astype(np.int64)) if t.size > 1 else np.zeros(0, dtype=np.int64)
    finite_gaps = gaps[gaps > 0] if gaps.size else gaps
    meta = {
        "dataset_id": K.BOOK_DATASET_ID,
        "object_list_sha256": digest,
        "symbol": K.BOOK_SYMBOL,
        "pair": K.BOOK_PAIR,
        "days_verified": len(verified),
        "days_missing": missing_days,
        "snapshots": int(t.size),
        "bands": sorted(int(b) for b in bands),
        "narrower_than_1pct": False,
        "max_staleness_ms": K.MAX_STALENESS_MS,
        "depth_band_pct": K.DEPTH_BAND_PCT,
        "notional": "USDT cumulative notional within the percentage of mid",
        "first_ms": None if t.size == 0 else int(t[0]),
        "last_ms": None if t.size == 0 else int(t[-1]),
        "gap_p50_ms": None if finite_gaps.size == 0 else int(np.quantile(finite_gaps, 0.50)),
        "gap_p99_ms": None if finite_gaps.size == 0 else int(np.quantile(finite_gaps, 0.99)),
        "gap_max_ms": None if finite_gaps.size == 0 else int(finite_gaps.max()),
        "gaps_over_staleness": int(np.sum(finite_gaps > K.MAX_STALENESS_MS)) if finite_gaps.size else 0,
        "usable_snapshots": int(np.sum(np.isfinite(bid) & np.isfinite(ask) & (bid >= 0) & (ask >= 0))),
    }
    return {"t": t, "bid": bid, "ask": ask}, meta


def _side_ok(bid: float, ask: float) -> bool:
    return bool(
        math.isfinite(bid) and math.isfinite(ask) and bid >= 0.0 and ask >= 0.0
    )


def snapshot_at(book: dict, target_ms: int, *, strict: bool) -> Optional[dict]:
    """Last legal snapshot. Strict means timestamp < target. No interpolation.

    A malformed snapshot is skipped. The walk stops when the next older
    snapshot is outside the frozen staleness. That older print is not copied
    forward across the gap.
    """
    times = book["t"]
    if times.size == 0:
        return None
    target = int(target_ms)
    if strict:
        pos = int(np.searchsorted(times, target, side="left")) - 1
    else:
        pos = int(np.searchsorted(times, target, side="right")) - 1
    while pos >= 0:
        ts = int(times[pos])
        if strict and ts >= target:
            pos -= 1
            continue
        if (not strict) and ts > target:
            pos -= 1
            continue
        age = target - ts
        if age < 0:
            pos -= 1
            continue
        if strict and age == 0:
            pos -= 1
            continue
        if age > K.MAX_STALENESS_MS:
            return None
        bid = float(book["bid"][pos])
        ask = float(book["ask"][pos])
        if _side_ok(bid, ask):
            return {"t": ts, "bid": bid, "ask": ask, "age_ms": age}
        pos -= 1
    return None


def orient(bid: float, ask: float, side: int) -> Optional[tuple[float, float]]:
    """Ahead is the book the approach has to consume to go through the level.

    side +1 is an approach from below, so ahead is the ask band.
    side −1 is an approach from above, so ahead is the bid band.
    """
    if side not in (1, -1) or not _side_ok(bid, ask):
        return None
    if side == 1:
        return ask, bid
    return bid, ask


def _log_ratio(now: float, past: float) -> Optional[float]:
    """Zeros are unavailable. No epsilon is added."""
    if not math.isfinite(now) or not math.isfinite(past) or now <= 0.0 or past <= 0.0:
        return None
    return math.log(now / past)


def features_from_snapshots(now: Optional[dict], past: Optional[dict], side: int) -> dict:
    empty = {
        "TOTAL_LOCAL_DEPTH": None,
        "ORIENTED_DEPTH_IMBALANCE": None,
        "AHEAD_DEPTH_CHANGE_60M": None,
        "BEHIND_DEPTH_CHANGE_60M": None,
        "TOTAL_DEPTH_CHANGE_60M": None,
        "bid_now": None,
        "ask_now": None,
        "ahead_now": None,
        "behind_now": None,
        "book_now_ms": None,
        "book_past_ms": None,
        "age_now_ms": None,
        "age_past_ms": None,
        "book_status": "NO_OR_STALE_NOW" if now is None else "NO_OR_STALE_PAST",
    }
    if now is None or past is None:
        return empty
    oriented_now = orient(now["bid"], now["ask"], side)
    oriented_past = orient(past["bid"], past["ask"], side)
    if oriented_now is None or oriented_past is None:
        empty["book_status"] = "BAD_SIDE"
        return empty
    ahead, behind = oriented_now
    ahead_past, behind_past = oriented_past
    total = ahead + behind
    total_past = ahead_past + behind_past
    imbalance = None
    if total > 0.0:
        imbalance = (ahead - behind) / total
    return {
        "TOTAL_LOCAL_DEPTH": total if total > 0.0 else None,
        "ORIENTED_DEPTH_IMBALANCE": imbalance,
        "AHEAD_DEPTH_CHANGE_60M": _log_ratio(ahead, ahead_past),
        "BEHIND_DEPTH_CHANGE_60M": _log_ratio(behind, behind_past),
        "TOTAL_DEPTH_CHANGE_60M": _log_ratio(total, total_past),
        "bid_now": now["bid"],
        "ask_now": now["ask"],
        "ahead_now": ahead,
        "behind_now": behind,
        "book_now_ms": int(now["t"]),
        "book_past_ms": int(past["t"]),
        "age_now_ms": int(now["age_ms"]),
        "age_past_ms": int(past["age_ms"]),
        "book_status": "OK",
    }


def book_features(book: dict, decision_ms: int, side: int) -> dict:
    """Current snapshot is the last one strictly before T, within staleness.

    The comparison snapshot is the last one at or before T−60m, within the
    same staleness. The touch instant itself is not a book observation.
    """
    t = int(decision_ms)
    if t >= K.SURFACE_END_MS or side not in (1, -1):
        out = features_from_snapshots(None, None, side)
        out["book_status"] = "OUTSIDE"
        return out
    now = snapshot_at(book, t, strict=True)
    past = snapshot_at(book, t - K.PRIMARY_MS, strict=False)
    return features_from_snapshots(now, past, side)
