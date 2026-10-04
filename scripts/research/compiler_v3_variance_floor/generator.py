"""Design-specific data generators and inference for S1-S6 (spec §7, V2 §5 estimator).

One replicate = one seed. The replicate's RNG draws the evaluation data first and
then, for randomization tests, the sign-flip draws. Candidate floors never enter.

S6 is NOT implemented: the frozen S6 definition (random era location shifts of
SD 0.5 under the null, an era-stratified sign-flip, and an oracle that assumes
the shifts are removed) is internally inconsistent; see FROZEN_S6_CONTRADICTION.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import t as student_t, ttest_ind

SIGNFLIP_DRAWS = 20000
REJECT, ACCEPT = 1, 0

FROZEN_S6_CONTRADICTION = (
    "S6: the manifest generates era location shifts ~ N(0, 0.5^2) that are present under the "
    "null, the frozen inference is an era-stratified sign-flip, and the frozen oracle assumes the "
    "shifts are removed by stratification. A sign-flip of raw values within an era is not a valid "
    "level-alpha test when the era center is not zero; centering within era removes the common "
    "effect delta together with the shift, so delta is not identified. No generator can satisfy "
    "the generator, the inference and the oracle at once. STOP: owner amendment of the freeze required."
)


class FrozenSpecContradiction(RuntimeError):
    pass


def true_effect(cell: dict) -> float:
    d = cell["GENERATOR_PARAMS"]["delta_min"]
    return {"NULL": 0.0, "DELTA_MIN": d, "2x_DELTA_MIN": 2 * d}[cell["TRUE_EFFECT"]]


def _signflip_p(d: np.ndarray, rng: np.random.Generator, draws: int = SIGNFLIP_DRAWS) -> float:
    obs = abs(float(d.mean()))
    signs = rng.choice(np.array([-1.0, 1.0]), size=(draws, d.size))
    perm = np.abs((signs * d[None, :]).mean(axis=1))
    return (1.0 + float(np.sum(perm >= obs))) / (1.0 + draws)


# ---------------------------------------------------------------- S1 / S2
def _innovations(rng: np.random.Generator, n: int, kind: str) -> np.ndarray:
    if kind == "gaussian":
        return rng.standard_normal(n)
    if kind in ("t4_scaled", "t3_scaled"):
        nu = 4 if kind == "t4_scaled" else 3
        return rng.standard_t(nu, n) / math.sqrt(nu / (nu - 2))   # unit variance
    raise KeyError(kind)


def replicate_two_group(cell: dict, seed: int) -> int:
    rng = np.random.default_rng(seed)
    n = cell["SAMPLE_SIZE"]["COUNT"]
    n_arm = n // 2
    sd = math.sqrt(cell["VARIANCE_RELATIONSHIPS"]["VAR_TRUE"])
    kind = cell["GENERATOR_PARAMS"]["innovation"]
    delta = true_effect(cell)
    a = sd * _innovations(rng, n_arm, kind)
    b = delta + sd * _innovations(rng, n_arm, kind)
    res = ttest_ind(b, a, equal_var=True)
    alpha = cell["MULTIPLICITY_ALPHA"]
    return REJECT if (res.pvalue < alpha and (delta == 0.0 or res.statistic > 0)) else ACCEPT


# ---------------------------------------------------------------- S3
def replicate_paired(cell: dict, seed: int) -> int:
    rng = np.random.default_rng(seed)
    n = cell["SAMPLE_SIZE"]["COUNT"]
    icc = cell["GENERATOR_PARAMS"]["pair_icc"]
    var_true = cell["VARIANCE_RELATIONSHIPS"]["VAR_TRUE"]            # variance of the paired difference
    var_obs = var_true / (2.0 * (1.0 - icc))
    u = rng.normal(0.0, math.sqrt(icc * var_obs), n)
    e_a = rng.normal(0.0, math.sqrt((1 - icc) * var_obs), n)
    e_b = rng.normal(0.0, math.sqrt((1 - icc) * var_obs), n)
    delta = true_effect(cell)
    d = (u + delta + e_b) - (u + e_a)
    p = _signflip_p(d, rng)
    return REJECT if (p < cell["MULTIPLICITY_ALPHA"] and (delta == 0.0 or d.mean() > 0)) else ACCEPT


# ---------------------------------------------------------------- S4
def cluster_robust_t(x: np.ndarray) -> tuple[float, float, int]:
    """V2 §5 estimator on equal clusters: mean, SE with G/(G-1), df G-1. x shape (G, m)."""
    g, m = x.shape
    n = g * m
    est = float(x.sum() / n)
    u = x.sum(axis=1) - est * m
    var = (g / (g - 1)) * float(np.sum(u ** 2)) / n ** 2
    return est, math.sqrt(var), g - 1


def replicate_clustered(cell: dict, seed: int) -> int:
    rng = np.random.default_rng(seed)
    g = cell["SAMPLE_SIZE"]["COUNT"]
    m, icc = cell["GENERATOR_PARAMS"]["m"], cell["GENERATOR_PARAMS"]["icc"]
    var_true = cell["VARIANCE_RELATIONSHIPS"]["VAR_TRUE"]
    delta = true_effect(cell)
    a = rng.normal(0.0, math.sqrt(icc * var_true), (g, 1))
    e = rng.normal(0.0, math.sqrt((1 - icc) * var_true), (g, m))
    x = delta + a + e
    est, se, df = cluster_robust_t(x)
    tstat = est / se if se > 0 else 0.0
    p = 2 * (1 - student_t.cdf(abs(tstat), df))
    return REJECT if (p < cell["MULTIPLICITY_ALPHA"] and (delta == 0.0 or est > 0)) else ACCEPT


# ---------------------------------------------------------------- S5
def replicate_event_venues(cell: dict, seed: int) -> int:
    rng = np.random.default_rng(seed)
    n = cell["SAMPLE_SIZE"]["COUNT"]
    v, rho = cell["GENERATOR_PARAMS"]["venues"], cell["GENERATOR_PARAMS"]["venue_corr"]
    var_true = cell["VARIANCE_RELATIONSHIPS"]["VAR_TRUE"]            # variance of the venue-averaged statistic
    s2 = var_true / (rho + (1 - rho) / v)                              # per-measurement variance
    c = rng.normal(0.0, math.sqrt(rho * s2), (n, 1))                   # event component (shared by venues)
    w = rng.normal(0.0, math.sqrt((1 - rho) * s2), (n, v))             # venue-specific measurement noise
    delta = true_effect(cell)
    measurements = delta + c + w                                       # (n events, v venues)
    d = measurements.mean(axis=1)                                      # one statistic per event
    p = _signflip_p(d, rng)
    return REJECT if (p < cell["MULTIPLICITY_ALPHA"] and (delta == 0.0 or d.mean() > 0)) else ACCEPT


# ---------------------------------------------------------------- S6 (blocked)
def replicate_era(cell: dict, seed: int) -> int:
    raise FrozenSpecContradiction(FROZEN_S6_CONTRADICTION)


REPLICATE = {"S1": replicate_two_group, "S2": replicate_two_group, "S3": replicate_paired,
             "S4": replicate_clustered, "S5": replicate_event_venues, "S6": replicate_era}


def replicate(cell: dict, seed: int) -> int:
    return REPLICATE[cell["DESIGN_ID"]](cell, seed)
