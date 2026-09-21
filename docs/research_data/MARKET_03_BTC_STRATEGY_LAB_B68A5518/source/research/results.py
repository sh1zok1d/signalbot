"""Wczytywanie wynikow backtestu Freqtrade -> dzienna krzywa kapitalu."""
from __future__ import annotations

import glob
import json
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "user_data/backtest_results"


def latest_zip() -> Path:
    files = sorted(glob.glob(str(RESULTS / "*.zip")))
    if not files:
        raise FileNotFoundError("Brak wynikow backtestu - uruchom freqtrade backtesting --export trades")
    return Path(files[-1])


def load(path: Path | None = None) -> tuple[pd.Series, pd.DataFrame, dict]:
    """Zwraca (dzienna krzywa kapitalu, transakcje, statystyki)."""
    path = path or latest_zip()
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        wallet_name = next(n for n in names if n.endswith("_wallet.feather"))
        json_name = next(n for n in names if n.endswith(".json")
                         and not n.endswith("_config.json"))
        z.extractall(RESULTS / "_extracted")
        wallet = pd.read_feather(RESULTS / "_extracted" / wallet_name)
        with z.open(json_name) as f:
            raw = json.load(f)

    strat = next(iter(raw["strategy"].values()))
    trades = pd.DataFrame(strat["trades"])
    for col in ("open_date", "close_date"):
        if col in trades:
            trades[col] = pd.to_datetime(trades[col], utc=True)

    wallet["date"] = pd.to_datetime(wallet["date"], utc=True)
    # wallet ma wiersz per waluta (USDT + BTC gdy jestesmy w pozycji);
    # wartosc portfela = suma total_quote po walutach w danym momencie
    equity = (wallet.groupby("date")["total_quote"].sum()
              .resample("D").last().ffill()
              .rename("BOT"))
    return equity, trades, strat


if __name__ == "__main__":
    eq, tr, strat = load()
    print(f"Equity: {eq.index[0].date()} -> {eq.index[-1].date()} ({len(eq)} dni)")
    print(eq.head(2)); print(eq.tail(2))
    print(f"\nTransakcje: {len(tr)}")
    print(tr[["open_date", "close_date", "profit_ratio", "exit_reason"]].head())
    print("\nPowody wyjscia:\n", tr.exit_reason.value_counts())
