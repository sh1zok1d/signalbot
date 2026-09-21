"""Walk-forward, wersja rownolegla.

Trzy rzeczy, ktore przyspieszaja to ~10x wzgledem walk_forward.py:
  1. Okna liczone rownolegle na wielu rdzeniach.
  2. Zero eksportu do zip - metryki czytane wprost ze stdout freqtrade.
  3. Kazdy worker ma wlasny katalog ze strategia, wiec nie bija sie o ten sam
     plik z parametrami.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from itertools import product
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "research/out"
SRC = ROOT / "user_data/strategies/EmaCross.py"

GRID = {"ema_period": [400, 500, 600, 700, 800, 1000, 1200],
        "exit_threshold": [1.0, 2.0, 3.0]}
TRAIN_MONTHS, TEST_MONTHS = 24, 6
START, END = pd.Timestamp("2018-01-01"), pd.Timestamp("2026-08-01")
WORKERS = max(1, min(8, (os.cpu_count() or 4) - 2))

RE_PROFIT = re.compile(r"Total profit %\s*│\s*(-?[\d.]+)%")
RE_DD = re.compile(r"Absolute drawdown\s*│\s*[\d.]+ USDT \(([\d.]+)%\)")
RE_TRADES = re.compile(r"Total/Daily Avg Trades\s*│\s*(\d+)")


def run(workdir: Path, combo: dict, a: pd.Timestamp, b: pd.Timestamp) -> tuple[float, float, int]:
    """Zwraca (zysk %, obsuniecie %, liczba transakcji) dla okna [a, b)."""
    (workdir / "EmaCross.json").write_text(json.dumps({
        "strategy_name": "EmaCross",
        "params": {"buy": {"ema_period": combo["ema_period"]},
                   "sell": {"exit_threshold": combo["exit_threshold"]},
                   "roi": {}, "stoploss": {}, "trailing": {}}}))
    r = subprocess.run(
        [str(ROOT / ".venv/bin/freqtrade"), "backtesting", "-c", str(ROOT / "config.json"),
         "--strategy-path", str(workdir), "-s", "EmaCross", "--timeframe", "1h",
         "--timerange", f"{a:%Y%m%d}-{b:%Y%m%d}", "--fee", "0.001", "--cache", "none"],
        capture_output=True, text=True)
    out = r.stdout
    p, d, t = RE_PROFIT.search(out), RE_DD.search(out), RE_TRADES.search(out)
    if not p:
        return -999.0, 100.0, 0
    return float(p.group(1)), float(d.group(1)) if d else 0.0, int(t.group(1)) if t else 0


def calmar(profit: float, dd: float, months: int) -> float:
    """Zysk zannualizowany podzielony przez obsuniecie. Nie sam zysk - inaczej
    zawsze wygrywalby najbardziej agresywny wariant."""
    if profit <= -99:
        return -99.0
    ann = (1 + profit / 100) ** (12 / months) - 1
    return ann / (dd / 100) if dd > 1 else ann


def fold(args) -> dict | None:
    i, tr_a, tr_b, te_b = args
    work = Path(tempfile.mkdtemp(prefix=f"wf{i}_"))
    try:
        shutil.copy(SRC, work / "EmaCross.py")
        combos = [dict(zip(GRID, v)) for v in product(*GRID.values())]

        best, best_s = None, -1e9
        for c in combos:
            profit, dd, _ = run(work, c, tr_a, tr_b)
            s = calmar(profit, dd, TRAIN_MONTHS)
            if s > best_s:
                best, best_s = c, s
        if best is None:
            return None

        profit, dd, trades = run(work, best, tr_b, te_b)
        return {"okno": f"{tr_b:%Y-%m}", "ema": best["ema_period"],
                "prog": best["exit_threshold"], "zysk_oos_%": profit,
                "dd_oos_%": -dd, "transakcje": trades}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    folds, t = [], START
    while True:
        tr_b = t + pd.DateOffset(months=TRAIN_MONTHS)
        te_b = tr_b + pd.DateOffset(months=TEST_MONTHS)
        if te_b > END:
            break
        folds.append((len(folds) + 1, t, tr_b, te_b))
        t += pd.DateOffset(months=TEST_MONTHS)

    n_bt = len(folds) * (len(list(product(*GRID.values()))) + 1)
    print(f"{len(folds)} okien, {n_bt} backtestow, {WORKERS} rownolegle\n", flush=True)

    rows = []
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        for res in ex.map(fold, folds):
            if res:
                rows.append(res)
                print(f"  {res['okno']}: ema{res['ema']}/{res['prog']} "
                      f"-> {res['zysk_oos_%']:+.1f}%", flush=True)

    df = pd.DataFrame(rows).sort_values("okno").reset_index(drop=True)
    df.to_csv(OUT / "walk_forward.csv", index=False)

    total = (1 + df["zysk_oos_%"] / 100).prod()
    print("\n" + "=" * 62)
    print(df.round(1).to_string(index=False))
    print("\n## Out-of-sample\n")
    print(f"- Okien: **{len(df)}**")
    print(f"- Zyskownych: **{(df['zysk_oos_%'] > 0).sum()} / {len(df)}**")
    print(f"- Zlozony zwrot: **{(total - 1) * 100:+.0f}%**")
    print(f"- Mediana okna: **{df['zysk_oos_%'].median():+.1f}%**")
    print(f"- Najgorsze okno: **{df['zysk_oos_%'].min():+.1f}%**")
    print(f"- Transakcji lacznie: **{df.transakcje.sum()}**")
    print(f"- Wybierane ema: {sorted(df.ema.unique().tolist())}")


if __name__ == "__main__":
    main()
