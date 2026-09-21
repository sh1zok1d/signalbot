"""Etap 4: parameter sweep -> macierz zwrotow do PBO/DSR.

PBO (Probability of Backtest Overfitting) wymaga wielu wariantow strategii,
nie jednego. Odpalamy siatke parametrow i zbieramy dzienna krzywa kapitalu
kazdego wariantu. Liczba wariantow to jednoczesnie num_trials dla DSR -
czyli uczciwa kara za to, ile razy probowalismy.
"""
from __future__ import annotations

import itertools
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PARAMS_FILE = ROOT / "user_data/strategies/EmaCrossFunding.json"
RESULTS = ROOT / "user_data/backtest_results"
OUT = ROOT / "research/out"
TIMERANGE = "20191001-"  # od kiedy mamy funding

GRID = {
    "ema_period": [500, 600, 700],
    "funding_max_pct": [40, 50, 60, 70, 80, 90, 100],
}
FIXED_BUY: dict = {}
FIXED_SELL: dict = {}


def write_params(combo: dict) -> None:
    PARAMS_FILE.write_text(json.dumps({
        "strategy_name": "EmaCrossFunding",
        "params": {
            "buy": {"ema_period": combo["ema_period"],
                    "funding_max_pct": combo["funding_max_pct"], **FIXED_BUY},
            "sell": {"exit_threshold": 2.0, **FIXED_SELL},
            "roi": {}, "stoploss": {}, "trailing": {},
        },
    }, indent=2))


def run_one(tag: str) -> pd.Series | None:
    """Freqtrade IGNORUJE --export-filename i zapisuje jako backtest-result-<ts>.zip,
    wiec nie da sie znalezc wyniku po nazwie. Bierzemy najnowszy zip powstaly
    po starcie tego konkretnego backtestu."""
    before = {p for p in RESULTS.glob("*.zip")}
    cmd = [str(ROOT / ".venv/bin/freqtrade"), "backtesting",
           "-c", str(ROOT / "config.json"), "-s", "EmaCrossFunding",
           "--timeframe", "1h", "--timerange", TIMERANGE,
           "--fee", "0.001", "--cache", "none", "--export", "trades"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  BLAD {tag}: {r.stderr[-300:]}", flush=True)
        return None
    zips = sorted({p for p in RESULTS.glob("*.zip")} - before)
    if not zips:
        print(f"  BRAK WYNIKU {tag}", flush=True)
        return None
    sys.path.insert(0, str(ROOT / "research"))
    from results import load
    equity, _, _ = load(zips[-1])
    zips[-1].unlink(missing_ok=True)  # nie zasmiecaj katalogu
    return equity


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    keys = list(GRID)
    combos = [dict(zip(keys, v)) for v in itertools.product(*GRID.values())]
    print(f"Siatka: {len(combos)} wariantow\n", flush=True)

    curves: dict[str, pd.Series] = {}
    for i, combo in enumerate(combos, 1):
        tag = f"ema{combo['ema_period']}_f{combo['funding_max_pct']}"
        print(f"[{i}/{len(combos)}] {tag}", flush=True)
        write_params(combo)
        eq = run_one(tag)
        if eq is not None:
            curves[tag] = eq

    PARAMS_FILE.unlink(missing_ok=True)
    shutil.rmtree(RESULTS / "_extracted", ignore_errors=True)

    mat = pd.DataFrame(curves).ffill().dropna()
    mat.to_feather(OUT / "sweep_funding.feather")
    print(f"\nZapisano {mat.shape[1]} krzywych x {mat.shape[0]} dni "
          f"-> research/out/sweep_equity.feather")
    tot = (mat.iloc[-1] / mat.iloc[0] - 1) * 100
    print("\nZwrot calkowity per wariant (%):")
    print(tot.sort_values(ascending=False).round(1).to_string())


if __name__ == "__main__":
    main()
