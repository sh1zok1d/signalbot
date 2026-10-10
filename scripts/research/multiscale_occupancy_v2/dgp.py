"""Synthetic data-generating processes for the V2 adequacy study (no market outcome is read).

Latent next-hour return of row T:  R(T) = N(T) + beta_L * g_L(T) [L active at T] + drift(T)
  N(T)       = (sum of the next 12 per-bar N(0,1) innovations on the row's own series grid) / sqrt(12); anchors 15 minutes
               apart share 9 of their 12 innovations, exactly as real overlapping 1h targets do;
  g_L        = OCC_L residualized on the B1 design (with intercept) within each series, scaled to unit variance, so that
               beta is (to rank-correlation precision) the partial association of OCC_L with R given B1;
  periods    = 52-week periods counted from the first row; even / odd;
  drift      = NULL_DRIFT only: a per-13-week level shift N(0, sigma^2) (P(UP) moves by about 1 pp per 0.025).
Y = 1{R > 0}. Each replication has its own seed: numpy SeedSequence([stage seed, scenario id, level id, replication])."""
from __future__ import annotations

import numpy as np

from . import engine as EN

PERIOD_WEEKS = 52
DRIFT_WEEKS = 13
SCENARIOS = ("NULL", "NULL_DRIFT", "CONSTANT_OCC_4H", "SWITCHING_OCC_2H_8H", "OCC_OFF_ON")


def residual_signals(rows: dict, X: np.ndarray) -> dict:
    out = {}
    for h in EN.LOOKBACKS:
        col = X[:, EN.OCC_IDX[h]]
        g = np.empty(col.size)
        for era in np.unique(rows["era"]):
            m = rows["era"] == era
            d = np.column_stack([np.ones(int(m.sum())), X[m][:, EN.B1_IDX]])
            coef, *_ = np.linalg.lstsq(d, col[m], rcond=None)
            r = col[m] - d @ coef
            g[m] = r / r.std()
        out[h] = g
    return out


def periods(rows: dict, weeks: int) -> np.ndarray:
    t = rows["close_ms"]
    return (t - t[0]) // (weeks * EN.K1.WEEK_MS)


def signal(rows: dict, sig: dict, scenario: str, rho: float, kappa: dict) -> np.ndarray:
    """rho = target partial Spearman (| B1) of the active scale within its active periods; beta_L = rho / kappa_L."""
    n = rows["close_ms"].size
    if scenario in ("NULL", "NULL_DRIFT") or rho == 0:
        return np.zeros(n)
    odd = periods(rows, PERIOD_WEEKS) % 2 == 1
    b = {h: rho / kappa[h] for h in kappa}
    if scenario == "CONSTANT_OCC_4H":
        return b[4] * sig[4]
    if scenario == "SWITCHING_OCC_2H_8H":
        return np.where(odd, b[8] * sig[8], b[2] * sig[2])
    if scenario == "OCC_OFF_ON":
        return np.where(odd, b[4] * sig[4], 0.0)
    raise SystemExit(f"UNKNOWN_SCENARIO_{scenario}")


def noise(rows: dict, rng: np.random.Generator) -> np.ndarray:
    r = np.empty(rows["close_ms"].size)
    for era in range(3):
        m = rows["era"] == era
        bars = rows["bar"][m]
        e = rng.standard_normal(int(bars.max()) + 14)
        cs = np.concatenate([[0.0], np.cumsum(e)])
        r[m] = (cs[bars + 13] - cs[bars + 1]) / np.sqrt(12.0)
    return r


def latent(rows: dict, sig: dict, scenario: str, rho: float, kappa: dict, seed: tuple, drift_sd: float) -> np.ndarray:
    rng = np.random.default_rng(np.random.SeedSequence(list(seed)))
    r = noise(rows, rng) + signal(rows, sig, scenario, rho, kappa)
    if scenario == "NULL_DRIFT":
        q = periods(rows, DRIFT_WEEKS)
        r = r + rng.normal(0.0, drift_sd, int(q.max()) + 1)[q]
    return r


def outcomes(rows: dict, sig: dict, scenario: str, rho: float, kappa: dict, seeds: list, drift_sd: float) -> np.ndarray:
    Y = np.empty((rows["close_ms"].size, len(seeds)), dtype=np.int8)
    for j, sd in enumerate(seeds):
        Y[:, j] = latent(rows, sig, scenario, rho, kappa, sd, drift_sd) > 0
    return Y
