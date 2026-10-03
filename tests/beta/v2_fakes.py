"""Synthetic Binance-like 5m history for the decision-support tests (PRODUCT_DECISION_V2).

Deterministic: a random walk with volatility clustering, volume and taker flow tied to the
move, and an open-interest walk. Nothing here is market data.
"""
from __future__ import annotations

import glob
import hashlib
import io
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

BAR_MS = 300_000
REPO = Path(__file__).resolve().parents[2]
VISION_DIR = REPO / "docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/durable_raw/binance"


def synthetic_rows(start: datetime, days: int, *, seed: int = 7, price: float = 60000.0) -> tuple:
    """(bar rows, oi rows) on the 5m grid from `start` for `days` days."""
    rng = np.random.default_rng(seed)
    n = days * 288
    vol = np.empty(n)
    v = 0.0012
    shocks = np.abs(rng.standard_normal(n))
    for i in range(n):                      # mean-reverting volatility around ~0.12% per 5m
        v = 0.98 * v + 0.02 * 0.0009 * (0.5 + shocks[i])
        vol[i] = v
    rets = rng.standard_normal(n) * vol
    close = price * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[price], close[:-1]])
    wig = np.abs(rng.standard_normal(n)) * vol * close * 0.6
    high = np.maximum(open_, close) + wig
    low = np.minimum(open_, close) - np.abs(rng.standard_normal(n)) * vol * close * 0.6
    quote = 5e7 * (1 + 200 * np.abs(rets)) * (1 + 0.2 * rng.random(n))
    tbq = quote * np.clip(0.5 + 30 * rets + 0.05 * rng.standard_normal(n), 0.05, 0.95)
    oi = 80000 * np.exp(np.cumsum(rng.normal(0, 0.0015, n) + 0.3 * rets))
    t0 = int(start.timestamp() * 1000)
    bars, ois = [], []
    for i in range(n):
        ms = t0 + i * BAR_MS
        bars.append({"open_time_ms": ms, "open": float(open_[i]), "high": float(high[i]), "low": float(low[i]),
                     "close": float(close[i]), "volume": float(quote[i] / close[i]), "quote_volume": float(quote[i]),
                     "taker_buy_quote": float(tbq[i]), "trades": 1000})
        ois.append({"ts_ms": ms, "oi_base": float(oi[i]), "oi_usd": float(oi[i] * close[i])})
    return bars, ois


def one_minute_rows(bars, *, exchange: str = "binance", symbol: str = "BTCUSDT"):
    """Split 5m rows into five 1m klines_1m rows (open → high → low → mid → close)."""
    out = []
    for r in bars:
        o, h, l, c = r["open"], r["high"], r["low"], r["close"]
        path = [o, h, l, (l + c) / 2, c]
        for m in range(5):
            ts = datetime.fromtimestamp(r["open_time_ms"] / 1000 + 60 * m, tz=timezone.utc)
            po = path[m - 1] if m else o
            pc = path[m]
            out.append((exchange, symbol, ts, po, max(po, pc), min(po, pc), pc, r["volume"] / 5,
                        r["volume"] / 10, "live"))
    return out


def repo_vision_zips(months):
    return [str(VISION_DIR / f"BTCUSDT-5m-{m}.zip") for m in months]


def kline_zip(rows, name: str, *, header: bool = True) -> bytes:
    lines = []
    if header:
        lines.append("open_time,open,high,low,close,volume,close_time,quote_volume,count,"
                     "taker_buy_volume,taker_buy_quote_volume,ignore")
    for r in rows:
        lines.append(f"{r['open_time_ms']},{r['open']},{r['high']},{r['low']},{r['close']},{r['volume']},"
                     f"{r['open_time_ms'] + BAR_MS - 1},{r['quote_volume']},{r['trades']},"
                     f"{r['volume'] / 2},{r['taker_buy_quote']},0")
    return _zip(name, "\n".join(lines) + "\n")


def metrics_zip(ois, name: str) -> bytes:
    lines = ["create_time,symbol,sum_open_interest,sum_open_interest_value,count_toptrader_long_short_ratio,"
             "sum_toptrader_long_short_ratio,count_long_short_ratio,sum_taker_long_short_vol_ratio"]
    for r in ois:
        ts = datetime.fromtimestamp(r["ts_ms"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{ts},BTCUSDT,{r['oi_base']},{r['oi_usd']},1,1,1,1")
    return _zip(name, "\n".join(lines) + "\n")


def _zip(name: str, text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name.replace(".zip", ".csv"), text)
    return buf.getvalue()


def checksum_text(body: bytes, name: str) -> bytes:
    return f"{hashlib.sha256(body).hexdigest()}  {name}\n".encode()


def ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


__all__ = ["synthetic_rows", "one_minute_rows", "repo_vision_zips", "kline_zip", "metrics_zip",
           "checksum_text", "ms", "day", "timedelta", "glob"]
