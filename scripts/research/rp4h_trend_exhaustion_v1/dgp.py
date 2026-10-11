"""Synthetic outcomes for the adequacy gate (no market outcome).

R_i = sum_{k=i+1}^{i+12} s_k e_k  +  sigma_i * (beta_main * g_main_i + beta_int * g_int_i),   e_k ~ N(0, 1) per grid bar
  s_k     = past-only per-bar volatility scale (surfaces.vol_scale; uses bars <= k-13, i.e. before every anchor whose
            1h target contains bar k); the homoskedastic sensitivity sets s_k = 1;
  sigma_i = sqrt(sum_{k=i+1}^{i+12} s_k^2), the anchor's own noise scale, so the planted association is scale-free;
  g_main  = the standardized rank residual of RP4H on (RET_4H, RV_4H) ranks (the canonical main-effect estimator);
  g_int   = the standardized rank residual of the Unit-1 product term on (RP4H, TS, RET_4H, RV_4H) ranks.
Overlapping anchors share 9 of 12 innovations, exactly like real overlapping 1h targets. TS has no planted main effect."""
from __future__ import annotations

import numpy as np

from . import constants as K
from . import estimator as E


def signals(rows: dict) -> dict:
    gm, _ = E.x_residual(rows["rp"], [rows["ret4"], rows["rv4"]])
    gi, _ = E.x_residual(E.product_term(rows["rp"], rows["ts"]), [rows[c] for c in K.PRIMARY_CONTROLS])
    return {"main": (gm - gm.mean()) / gm.std(), "int": (gi - gi.mean()) / gi.std()}


def noise_parts(rows: dict, hetero: bool) -> tuple:
    s = rows["scale"] if hetero else np.ones(rows["n_bars"])
    c2 = np.concatenate([[0.0], np.cumsum(s * s)])
    b = rows["bar"]
    sigma = np.sqrt(c2[b + 13] - c2[b + 1])
    return s, sigma


def latent(rows: dict, sig: dict, s: np.ndarray, sigma: np.ndarray, beta_main: float, beta_int: float,
           seed: tuple) -> np.ndarray:
    rng = np.random.default_rng(np.random.SeedSequence(list(seed)))
    e = rng.standard_normal(s.size) * s
    cs = np.concatenate([[0.0], np.cumsum(e)])
    b = rows["bar"]
    return (cs[b + 13] - cs[b + 1]) + sigma * (beta_main * sig["main"] + beta_int * sig["int"])
