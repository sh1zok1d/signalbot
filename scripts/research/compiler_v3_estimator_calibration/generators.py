"""Synthetic sample generators for the calibration executor (Protocol V3; spec section 4).

One replicate = one frozen replicate seed. RNG: root = SeedSequence(seed); data_ss,
reserved_ss = root.spawn(2); DATA = default_rng(data_ss); child 1 is reserved and unused.
The candidate never enters the derivation. A sample is generated ONCE per (cell, seed)
and every candidate is applied to that same sample.

Truth: each sample carries VAR_TRUE_USED, the exact variance (n x Var of the unit-mean
statistic) of the process that was generated, and VAR_TRUE_FROZEN_FORMULA, the value or
formula of the frozen grid. They coincide except in the CLUSTERED HETERO cells with
phi_G > 0 (see INTERPRETATIONS in the executor README section of the audit).

No Run 1 artifact and no market data is read here.
"""

from __future__ import annotations

import math

import numpy as np

STUDENT_DF = {"GAUSS": None, "T4": 4, "T3": 3}


def substreams(seed: int) -> tuple[np.random.Generator, np.random.SeedSequence]:
    root = np.random.SeedSequence(int(seed))
    data_ss, reserved_ss = root.spawn(2)
    return np.random.default_rng(data_ss), reserved_ss


def innovations(rng: np.random.Generator, size, tail: str) -> np.ndarray:
    """Unit-variance innovations: Gaussian or Student t scaled to variance 1."""
    df = STUDENT_DF[tail]
    if df is None:
        return rng.standard_normal(size)
    return rng.standard_t(df, size) * math.sqrt((df - 2) / df)


def ar1_unit(rng: np.random.Generator, n: int, phi: float, tail: str, scale: np.ndarray | None = None) -> np.ndarray:
    """AR(1) sequence with marginal variance 1 (times scale_t^2 on the innovation when scale is given):
    x_1 = s_1 * e_1; x_t = phi x_{t-1} + sqrt(1 - phi^2) s_t e_t. Stationary start."""
    e = innovations(rng, n, tail)
    if scale is not None:
        e = e * scale
    x = np.empty(n)
    x[0] = e[0]
    c = math.sqrt(1.0 - phi * phi)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + c * e[t]
    return x


def ar_factor(n: int, phi: float) -> float:
    return 1.0 + 2.0 * sum((1.0 - h / n) * phi**h for h in range(1, n))


def generate(cell: dict, seed: int) -> dict:
    """Return the sample for one cell and replicate seed, with the exact truth."""
    rng, _reserved = substreams(seed)
    fam, lv, n = cell["FAMILY"][:2], cell["LEVELS"], int(cell["N"])
    if fam == "F5":
        fam = lv["base_family"]                   # out-of-domain cells generate from their base family
    lam = float(lv.get("lambda", 1.0))          # F5 out-of-domain: exposed sample at variance 1, truth x lambda
    if fam == "F1":
        phi, tail = lv["phi"], lv["tail"]
        xa, xb = ar1_unit(rng, n, phi, tail), ar1_unit(rng, n, phi, tail)
        truth = ar_factor(n, phi)
        return {"CLASS": "TWO_SAMPLE", "ARMS": (xa, xb), "VAR_TRUE_USED": lam * truth,
                "VAR_TRUE_FROZEN_FORMULA": lam * truth, "TRUTH_MATCHES_FROZEN": True}
    if fam == "F2":
        phi, tail = lv["phi"], lv["tail"]
        d = ar1_unit(rng, n, phi, tail)
        truth = ar_factor(n, phi)
        return {"CLASS": "PAIRED_UNITS", "SEQUENCE": d, "VAR_TRUE_USED": lam * truth,
                "VAR_TRUE_FROZEN_FORMULA": lam * truth, "TRUTH_MATCHES_FROZEN": True}
    if fam == "F3":
        icc, phi, tail = lv["icc"], lv["phi_G"], lv["tail"]
        if lv["sizes"] == "EQUAL":
            m = np.full(n, int(lv["m_nominal"]))
        else:
            lo, hi = lv["m_range"]
            m = rng.integers(lo, hi + 1, size=n)
        v = icc + (1.0 - icc) / m                                  # variance of each cluster mean
        z = ar1_unit(rng, n, phi, tail)                            # unit-variance AR(1) across ordered clusters
        s = np.sqrt(v) * z                                         # cluster-level mean statistic
        frozen = float(np.mean(v)) * ar_factor(n, phi)
        if phi == 0.0 or lv["sizes"] == "EQUAL":
            exact = frozen
        else:
            sv = np.sqrt(v)
            idx = np.arange(n)
            exact = float((sv[:, None] * sv[None, :] * phi ** np.abs(idx[:, None] - idx[None, :])).sum()) / n
        return {"CLASS": "CLUSTERED", "SEQUENCE": s, "CLUSTER_SIZES": m, "VAR_TRUE_USED": lam * exact,
                "VAR_TRUE_FROZEN_FORMULA": lam * frozen, "TRUTH_MATCHES_FROZEN": math.isclose(exact, frozen, rel_tol=1e-12)}
    if fam == "F4":
        vc, phi, tail = lv["venue_corr"], lv["phi_e"], lv["tail"]
        c = (1.0 + 2.0 * vc) / 3.0                                 # variance of the venue-averaged statistic
        if lv["scale"] == "HETERO":
            mult = np.exp(0.5 * rng.standard_normal(n))            # per-event SD multiplier on the innovation
            em2 = math.exp(0.5)
        else:
            mult, em2 = None, 1.0
        s = math.sqrt(c) * ar1_unit(rng, n, phi, tail, scale=mult)
        truth = c * em2 * ar_factor(n, phi)                        # exact: Var(s_g) = c E[m^2], Cov = phi^h Var
        return {"CLASS": "RARE_EVENT", "SEQUENCE": s, "VAR_TRUE_USED": lam * truth,
                "VAR_TRUE_FROZEN_FORMULA": lam * truth, "TRUTH_MATCHES_FROZEN": True}
    raise KeyError(f"unsupported family {cell['FAMILY']}")
