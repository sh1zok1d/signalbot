"""Frozen inference for R03: sign-flip test over units, Holm within a card, epoch
heterogeneity record, nuisance wording rule, and the classification predicate.
"""

from __future__ import annotations

import numpy as np

from . import constants as K


def signflip_p(d: np.ndarray, draws: int, seed: int) -> dict:
    d = d[np.isfinite(d)]
    n = d.size
    if n == 0:
        return {"N": 0, "ESTIMATE": None, "P_TWO_SIDED": 1.0, "SE_SIGNFLIP": None}
    obs = float(np.mean(d))
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(draws, n))
    perm = (signs * d[None, :]).mean(axis=1)
    p = (1.0 + float(np.sum(np.abs(perm) >= abs(obs)))) / (1.0 + draws)
    return {"N": n, "ESTIMATE": obs, "P_TWO_SIDED": p, "SE_SIGNFLIP": float(np.std(perm, ddof=1)),
            "P_ONE_SIDED_POSITIVE": (1.0 + float(np.sum(perm >= obs))) / (1.0 + draws),
            "P_ONE_SIDED_NEGATIVE": (1.0 + float(np.sum(perm <= obs))) / (1.0 + draws)}


def moving_block_se(d: np.ndarray, block: int, draws: int, seed: int) -> float | None:
    d = d[np.isfinite(d)]
    n = d.size
    if n < 2 * block:
        return None
    rng = np.random.default_rng(seed)
    starts = np.arange(0, n - block + 1)
    k = int(np.ceil(n / block))
    means = []
    for _ in range(draws):
        pick = rng.choice(starts, size=k)
        sample = np.concatenate([d[s:s + block] for s in pick])[:n]
        means.append(sample.mean())
    return float(np.std(means, ddof=1))


def holm(pvalues: dict[str, float], alpha: float) -> dict[str, dict]:
    order = sorted(pvalues, key=lambda k: pvalues[k])
    m = len(order)
    out, stop = {}, False
    for rank, key in enumerate(order):
        threshold = alpha / (m - rank)
        reject = (not stop) and pvalues[key] <= threshold
        if not reject:
            stop = True
        out[key] = {"P": pvalues[key], "RANK": rank + 1, "THRESHOLD": threshold, "REJECT": reject,
                    "P_ADJUSTED": min(1.0, max((m - r) * pvalues[k2] for r, k2 in enumerate(order[:rank + 1])))}
    return out


def epoch_record(d: np.ndarray, years: np.ndarray, *, seed: int) -> dict:
    """Per-year estimates, a block-permutation heterogeneity test, and the opposite-sign test."""
    ok = np.isfinite(d)
    d, years = d[ok], years[ok]
    pooled = float(np.mean(d)) if d.size else 0.0
    per = {}
    for y in sorted(set(years.tolist())):
        dy = d[years == y]
        if dy.size < 2:
            continue
        se = float(np.std(dy, ddof=1) / np.sqrt(dy.size))
        per[str(y)] = {"N": int(dy.size), "ESTIMATE": float(np.mean(dy)), "SE": se}
    if len(per) < 3:
        return {"EPOCHS": per, "HETEROGENEITY_P": None, "OPPOSITE_SIGN_EPOCHS": [], "STATUS": "NOT_ASSESSABLE"}

    def q_stat(dd, yy):
        q, ests = 0.0, []
        for y in per:
            dy = dd[yy == int(y)]
            if dy.size < 2:
                continue
            se2 = float(np.var(dy, ddof=1) / dy.size)
            if se2 <= 0:
                continue
            ests.append((float(np.mean(dy)), se2))
        if not ests:
            return 0.0
        w = np.array([1 / s for _, s in ests]); e = np.array([m for m, _ in ests])
        theta_w = float(np.sum(w * e) / np.sum(w))
        return float(np.sum((e - theta_w) ** 2 * w))

    q_obs = q_stat(d, years)
    rng = np.random.default_rng(seed)
    # block permutation: shuffle blocks of consecutive units across epochs, keeping epoch sizes
    n = d.size
    blocks = [np.arange(i, min(i + K.HET_BLOCK_UNITS, n)) for i in range(0, n, K.HET_BLOCK_UNITS)]
    count = 0
    for _ in range(K.HET_DRAWS):
        order = rng.permutation(len(blocks))
        idx = np.concatenate([blocks[i] for i in order])
        if q_stat(d[idx], years) >= q_obs:
            count += 1
    het_p = (1.0 + count) / (1.0 + K.HET_DRAWS)
    opposite = []
    for y, rec in per.items():
        dy = d[years == int(y)]
        if np.sign(rec["ESTIMATE"]) != np.sign(pooled) and rec["ESTIMATE"] != 0:
            flip = signflip_p(dy, 4000, seed + int(y))
            p_one = flip["P_ONE_SIDED_NEGATIVE"] if pooled > 0 else flip["P_ONE_SIDED_POSITIVE"]
            if p_one < 0.05:
                opposite.append(y)
    status = "PASS"
    if het_p <= K.ALPHA_HET:
        status = "FAIL_HETEROGENEOUS_UNEXPLAINED" if opposite else "PASS_MAGNITUDE_VARIES_BY_EPOCH"
    largest_share = max(r["N"] for r in per.values()) / n
    loo = {y: float(np.mean(d[years != int(y)])) for y in per}
    return {"EPOCHS": per, "Q_OBS": q_obs, "HETEROGENEITY_P": het_p, "OPPOSITE_SIGN_EPOCHS": opposite,
            "STATUS": status, "LARGEST_EPOCH_SHARE": largest_share, "LEAVE_ONE_EPOCH_OUT": loo}


def practical_gate(estimate: float | None, direction: str) -> dict:
    if estimate is None:
        return {"PASS": False, "REASON": "no estimate"}
    sign_ok = {"POSITIVE": estimate > 0, "NEGATIVE": estimate < 0, "TWO_SIDED": estimate != 0}[direction]
    return {"PASS": bool(sign_ok and abs(estimate) >= K.MIN_MEANINGFUL_EFFECT),
            "SIGN_AS_EXPECTED": bool(sign_ok), "ABS_ESTIMATE": abs(estimate), "BAR": K.MIN_MEANINGFUL_EFFECT}


def nuisance_wording(raw: float | None, adjusted: float | None) -> dict:
    if raw is None or adjusted is None or not np.isfinite(adjusted) or raw == 0:
        return {"RETENTION": None, "WORDING": "NUISANCE_DIAGNOSTIC_UNAVAILABLE"}
    retention = adjusted / raw
    state_specific = retention >= K.NUISANCE_RETENTION_FOR_STATE_SPECIFIC_WORDING
    return {"RETENTION": float(retention),
            "WORDING": "STATE_SPECIFIC_BEYOND_VOLATILITY_REGIME" if state_specific else "REFLECTS_GENERAL_VOLATILITY_REGIME"}


def classify(*, integrity: bool, statistical: bool, practical: bool, epoch_status: str, assessable: bool) -> str:
    if not integrity:
        return "INVALID_RUN"
    if not (statistical and practical):
        return "NO_INCREMENTAL_STRUCTURE"
    if assessable and epoch_status == "FAIL_HETEROGENEOUS_UNEXPLAINED":
        return "HETEROGENEOUS_UNEXPLAINED"
    return "PROMISING_PROTOTYPE"
