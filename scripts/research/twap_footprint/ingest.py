"""Stream one Binance spot BTCUSDT aggTrades month into two outcome-free extracts.

1. Taker prints: all aggTrades of one taker side in the same millisecond, summed.
   Only prints of at least MIN_PRINT_USD are kept (time, side, quantity in 1e-8
   units, notional key rounded to $10, notional).
2. Minute aggregates: per UTC minute the aggTrade count, taker-buy and taker-sell
   notional, and the last trade price.

Neither extract is a scientific outcome: no return, no post-event window and no
episode-conditioned quantity is computed here. Files from 2025 or later are refused.
"""
from __future__ import annotations

import hashlib
import io
import json
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv

BASE = "https://data.binance.vision/data/spot/monthly/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{ym}.zip"
MIN_PRINT_USD = 1_000.0
NOTIONAL_ROUND_USD = 10.0
COLS = ["agg_id", "price", "qty", "first_id", "last_id", "time", "buyer_maker", "best_match"]


def refuse_protected(ym: str) -> None:
    if int(ym[:4]) >= 2025:
        raise SystemExit(f"protected month refused: {ym}")


def download(ym: str, dest: Path) -> dict:
    refuse_protected(ym)
    url = BASE.format(ym=ym)
    zpath = dest / f"BTCUSDT-aggTrades-{ym}.zip"
    for attempt in range(5):
        try:
            urllib.request.urlretrieve(url, zpath)
            with urllib.request.urlopen(url + ".CHECKSUM") as r:
                expected = r.read().decode().split()[0]
            break
        except Exception:  # noqa: BLE001 - network retry with backoff
            if attempt == 4:
                raise
            time.sleep(2 ** (attempt + 1))
    h = hashlib.sha256()
    with zpath.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    if h.hexdigest() != expected:
        raise SystemExit(f"checksum mismatch {ym}")
    return {"ym": ym, "zip": str(zpath), "sha256": expected, "bytes": zpath.stat().st_size}


def _batches(zpath: Path):
    with zipfile.ZipFile(zpath) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            head = f.peek(64) if hasattr(f, "peek") else b""
            skip = 1 if head[:1].isalpha() else 0
            reader = pacsv.open_csv(
                f,
                read_options=pacsv.ReadOptions(column_names=COLS, block_size=64 << 20, skip_rows=skip),
                convert_options=pacsv.ConvertOptions(
                    include_columns=["price", "qty", "time", "buyer_maker"],
                    column_types={"price": pa.float64(), "qty": pa.float64(), "time": pa.int64(),
                                  "buyer_maker": pa.bool_()}),
            )
            for batch in reader:
                yield (batch.column("time").to_numpy(), batch.column("price").to_numpy(),
                       batch.column("qty").to_numpy(), batch.column("buyer_maker").to_numpy(zero_copy_only=False))


def _group_prints(t, side, q, usd):
    key = t * 2 + (side > 0)
    order = np.argsort(key, kind="stable")
    key, q, usd = key[order], q[order], usd[order]
    starts = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
    k = key[starts]
    return k // 2, np.where(k % 2 == 1, 1, -1).astype(np.int8), np.add.reduceat(q, starts), np.add.reduceat(usd, starts)


def process(zpath: Path, out_dir: Path, ym: str) -> dict:
    refuse_protected(ym)
    prints, minutes = [], []
    carry = None
    n_rows = 0
    first_t = last_t = None
    for t, price, qty, bm in _batches(zpath):
        n_rows += len(t)
        if first_t is None:
            first_t = int(t[0])
        last_t = int(t[-1])
        side = np.where(bm, -1, 1).astype(np.int8)
        q = np.rint(qty * 1e8).astype(np.int64)
        usd = price * qty
        minute = t // 60_000
        buy = np.where(side > 0, usd, 0.0)
        sell = np.where(side < 0, usd, 0.0)
        mdf = pd.DataFrame({"minute": minute, "n": 1, "buy_usd": buy, "sell_usd": sell, "close": price})
        minutes.append(mdf.groupby("minute", sort=True).agg(n=("n", "sum"), buy_usd=("buy_usd", "sum"),
                                                              sell_usd=("sell_usd", "sum"), close=("close", "last")))
        if carry is not None:
            t = np.concatenate([carry[0], t]); side = np.concatenate([carry[1], side])
            q = np.concatenate([carry[2], q]); usd = np.concatenate([carry[3], usd])
        tail = t == t[-1]
        carry = (t[tail], side[tail], q[tail], usd[tail])
        keep = ~tail
        if keep.any():
            pt, ps, pq, pu = _group_prints(t[keep], side[keep], q[keep], usd[keep])
            sel = pu >= MIN_PRINT_USD
            prints.append((pt[sel], ps[sel], pq[sel], pu[sel]))
    if carry is not None and len(carry[0]):
        pt, ps, pq, pu = _group_prints(*carry)
        sel = pu >= MIN_PRINT_USD
        prints.append((pt[sel], ps[sel], pq[sel], pu[sel]))
    pt = np.concatenate([p[0] for p in prints]); ps = np.concatenate([p[1] for p in prints])
    pq = np.concatenate([p[2] for p in prints]); pu = np.concatenate([p[3] for p in prints])
    order = np.argsort(pt, kind="stable")
    pdf = pd.DataFrame({"time": pt[order], "side": ps[order], "q": pq[order],
                        "nkey": np.rint(pu[order] / NOTIONAL_ROUND_USD).astype(np.int64),
                        "usd": pu[order].astype(np.float64)})
    m = pd.concat(minutes)
    m = m.groupby(level=0, sort=True).agg(n=("n", "sum"), buy_usd=("buy_usd", "sum"),
                                          sell_usd=("sell_usd", "sum"), close=("close", "last"))
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf["usd"] = pdf["usd"].astype(np.float32)
    pdf.to_parquet(out_dir / f"prints_{ym}.parquet", index=False, compression="zstd")
    m.reset_index().to_parquet(out_dir / f"minutes_{ym}.parquet", index=False, compression="zstd")
    return {"ym": ym, "agg_rows": n_rows, "prints_ge_1000": int(len(pdf)), "minutes": int(len(m)),
            "first_time_ms": first_t, "last_time_ms": last_t}


def month_list(start: str, end: str) -> list[str]:
    out = []
    y, mo = int(start[:4]), int(start[5:])
    while (y, mo) <= (int(end[:4]), int(end[5:])):
        out.append(f"{y:04d}-{mo:02d}")
        mo += 1
        if mo == 13:
            y, mo = y + 1, 1
    return out


if __name__ == "__main__":
    import sys
    from concurrent.futures import ThreadPoolExecutor
    root = Path(sys.argv[1])
    months = sys.argv[2:]
    zdir, mdir = root / "zips", root / "months"
    log = root / "ingest_log.jsonl"
    done = set()
    if log.exists():
        done = {json.loads(l)["ym"] for l in log.read_text().splitlines() if l.strip()}
    todo = [m for m in months if m not in done]
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(download, todo[0], zdir) if todo else None
        for i, ym in enumerate(todo):
            meta = fut.result()
            fut = pool.submit(download, todo[i + 1], zdir) if i + 1 < len(todo) else None
            t0 = time.time()
            info = process(Path(meta["zip"]), mdir, ym)
            Path(meta["zip"]).unlink()
            row = {**meta, **info, "seconds": round(time.time() - t0, 1)}
            row.pop("zip")
            with log.open("a") as f:
                f.write(json.dumps(row) + "\n")
            print(json.dumps(row), flush=True)
