"""Pobieranie darmowych danych rynkowych spoza swiec.

Zrodla (publiczne, bez kluczy API):
  - Binance Futures: historia funding rate BTCUSDT (od 2019)
  - Alternative.me: Fear & Greed Index (od 2018)
Wszystko z timestampem publikacji, zeby nie wstrzykiwac przyszlosci do backtestu.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests

OUT = Path(__file__).resolve().parent / "webdata"
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "btcTrader-research/1.0"}


def funding_rate(symbol: str = "BTCUSDT") -> pd.DataFrame:
    """Funding rate co 8h. API oddaje max 1000 rekordow na strzal, wiec stronicujemy."""
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    start = int(pd.Timestamp("2019-09-01", tz="UTC").timestamp() * 1000)
    rows: list[dict] = []
    while True:
        r = requests.get(url, params={"symbol": symbol, "startTime": start, "limit": 1000},
                         headers=UA, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows += batch
        last = batch[-1]["fundingTime"]
        if last <= start or len(batch) < 1000:
            break
        start = last + 1
        time.sleep(0.25)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df.fundingTime, unit="ms", utc=True)
    df["funding"] = df.fundingRate.astype(float)
    return df[["date", "funding"]].drop_duplicates("date").sort_values("date")


def fear_greed() -> pd.DataFrame:
    r = requests.get("https://api.alternative.me/fng/", params={"limit": 0},
                     headers=UA, timeout=30)
    r.raise_for_status()
    df = pd.DataFrame(r.json()["data"])
    df["date"] = pd.to_datetime(df.timestamp.astype(int), unit="s", utc=True)
    df["fng"] = df.value.astype(int)
    return df[["date", "fng"]].sort_values("date")


if __name__ == "__main__":
    fr = funding_rate()
    fr.to_feather(OUT / "funding.feather")
    print(f"funding: {len(fr)} rekordow, {fr.date.min().date()} -> {fr.date.max().date()}")
    print(fr.funding.describe().round(6).to_string())

    fg = fear_greed()
    fg.to_feather(OUT / "fear_greed.feather")
    print(f"\nfear&greed: {len(fg)} rekordow, {fg.date.min().date()} -> {fg.date.max().date()}")
