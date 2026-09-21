"""Metryki ryzyka i zwrotu wg skilla risk-report.

Uwaga o annualizacji: krypto handluje sie 24/7, wiec periods_per_year = 365.
SPY jest forward-fillowany na weekendy, wiec ma zerowe zwroty w soboty/niedziele.
Zaniza to jego zmiennosc rocznie o ok. sqrt(252/365), ale utrzymuje wspolna os
czasu dla wszystkich trzech krzywych - inaczej porownanie byloby niespojne.
Konsekwencja: Sharpe SPY liczony tak jest LEKKO zawyzony wzgledem konwencji
gieldowej. Przy porownaniu z botem to dziala na niekorzysc bota, wiec jest to
konserwatywne zalozenie.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PPY = 365


def _cagr(cum: pd.Series, n: int, ppy: int) -> float:
    return float(cum.iloc[-1] ** (ppy / n) - 1)


def risk_report(returns: pd.Series, ppy: int = PPY,
                bench: dict[str, pd.Series] | None = None) -> dict:
    r = returns.dropna()
    if len(r) < 2 or r.std() == 0:
        return {}
    cum = (1 + r).cumprod()
    dd = cum / cum.cummax() - 1
    downside = r[r < 0]
    var95, var99 = np.percentile(r, 5), np.percentile(r, 1)
    cvar95 = r[r <= var95].mean()
    cvar99 = r[r <= var99].mean()
    cagr = _cagr(cum, len(r), ppy)
    max_dd = float(dd.min())

    # dlugosc najdluzszego drawdownu w dniach
    dd_len = (dd < 0).astype(int).groupby(dd.eq(0).cumsum()).sum()
    monthly = (1 + r).resample("ME").prod() - 1

    p95, p5 = np.percentile(r, 95), np.percentile(r, 5)
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()

    out = {
        "Total return": cum.iloc[-1] - 1,
        "CAGR": cagr,
        "Vol (ann.)": r.std() * np.sqrt(ppy),
        "Max drawdown": max_dd,
        "Max DD duration (dni)": int(dd_len.max()) if len(dd_len) else 0,
        "Ulcer index": float(np.sqrt((dd**2).mean())),
        "Downside dev (ann.)": downside.std() * np.sqrt(ppy) if len(downside) else np.nan,
        "Sharpe": r.mean() / r.std() * np.sqrt(ppy),
        "Sortino": r.mean() / downside.std() * np.sqrt(ppy) if len(downside) else np.nan,
        "Calmar": cagr / abs(max_dd) if max_dd else np.nan,
        "Omega": gains / losses if losses else np.nan,
        "VaR 95%": var95,
        "CVaR 95%": cvar95,
        "VaR 99%": var99,
        "CVaR 99%": cvar99,
        "Tail ratio": abs(p95 / p5) if p5 else np.nan,
        "Skew": r.skew(),
        "Kurtosis": r.kurtosis(),
        "Hit rate (dzienny)": (r > 0).mean(),
        "Hit rate (miesieczny)": (monthly > 0).mean(),
        "Miesiecy": len(monthly),
        "DD > 5%": int((dd_len[dd_len > 0].index.map(
            lambda g: dd[dd.eq(0).cumsum() == g].min()) < -0.05).sum()),
        "DD > 10%": int((dd_len[dd_len > 0].index.map(
            lambda g: dd[dd.eq(0).cumsum() == g].min()) < -0.10).sum()),
        "DD > 20%": int((dd_len[dd_len > 0].index.map(
            lambda g: dd[dd.eq(0).cumsum() == g].min()) < -0.20).sum()),
        "Ekspozycja (% dni w rynku)": (r != 0).mean(),
    }
    for name, b in (bench or {}).items():
        br = b.reindex(r.index).dropna()
        common = r.index.intersection(br.index)
        if len(common) > 30 and br.loc[common].var() > 0:
            out[f"Beta vs {name}"] = (r.loc[common].cov(br.loc[common])
                                      / br.loc[common].var())
            out[f"Korelacja vs {name}"] = r.loc[common].corr(br.loc[common])
    return out


FLAGS = {
    "Sharpe": (lambda v: v > 3, "podejrzanie wysoki - sprawdz look-ahead bias"),
    "Max drawdown": (lambda v: v < -0.40, "gleboki drawdown"),
    "Skew": (lambda v: v < -1, "ciezki lewy ogon - rzadkie duze straty"),
    "Kurtosis": (lambda v: v > 5, "grube ogony"),
}

PCT = {"Total return", "CAGR", "Vol (ann.)", "Max drawdown", "Downside dev (ann.)",
       "VaR 95%", "CVaR 95%", "VaR 99%", "CVaR 99%", "Hit rate (dzienny)",
       "Hit rate (miesieczny)", "Ekspozycja (% dni w rynku)"}


def fmt(key: str, val) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "-"
    if key in PCT:
        return f"{val * 100:.2f}%"
    if isinstance(val, (int, np.integer)):
        return str(int(val))
    return f"{val:.2f}"


def compare_table(reports: dict[str, dict]) -> str:
    names = list(reports)
    keys = list(next(iter(reports.values())))
    lines = ["| Metryka | " + " | ".join(names) + " |",
             "|---" * (len(names) + 1) + "|"]
    for k in keys:
        cells = [fmt(k, reports[n].get(k)) for n in names]
        note = ""
        if k in FLAGS:
            bad = [n for n in names if reports[n].get(k) is not None
                   and not np.isnan(reports[n][k]) and FLAGS[k][0](reports[n][k])]
            if bad:
                note = f"  <- {', '.join(bad)}: {FLAGS[k][1]}"
        lines.append(f"| {k} | " + " | ".join(cells) + f" |{note}")
    return "\n".join(lines)
