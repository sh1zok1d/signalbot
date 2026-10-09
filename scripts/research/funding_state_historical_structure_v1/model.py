"""Association statistics for the frozen funding-state design.

The future path is an input. This module does not load a market file.
"""

from __future__ import annotations

import math

import numpy as np

from scripts.research.formation_width_regime_v1.amendment_a1 import average_ranks, partial_spearman

from . import constants as K


def funding_state(rates: np.ndarray, min_past: int = K.MIN_PAST) -> np.ndarray:
    """Past-only percentile. The current rate is outside the reference multiset."""
    rates = np.asarray(rates, dtype=np.float64)
    n = int(rates.shape[0])
    state = np.full(n, np.nan, dtype=np.float64)
    for i in range(int(min_past), n):
        past = rates[:i]
        x = rates[i]
        state[i] = (1.0 + float(np.sum(past < x)) + 0.5 * float(np.sum(past == x))) / (i + 1.0)
    return state


def adverse_long(p0: float, lows: np.ndarray) -> float:
    """Long-side maximum adverse log excursion. Zero when the path never prints below P0."""
    window = np.asarray(lows, dtype=np.float64)
    if not np.isfinite(p0) or p0 <= 0.0 or window.size == 0 or not np.all(np.isfinite(window)):
        raise RuntimeError("ADVERSE_PATH_INCOMPLETE")
    lowest = float(np.min(window))
    if lowest <= 0.0:
        raise RuntimeError("ADVERSE_PATH_NONPOSITIVE")
    drop = -math.log(lowest / p0)
    return drop if drop > 0.0 else 0.0


def absolute_excursion(p0: float, lows: np.ndarray, highs: np.ndarray) -> float:
    window_lo = np.asarray(lows, dtype=np.float64)
    window_hi = np.asarray(highs, dtype=np.float64)
    if (
        not np.isfinite(p0)
        or p0 <= 0.0
        or not np.all(np.isfinite(window_lo))
        or not np.all(np.isfinite(window_hi))
    ):
        raise RuntimeError("ADVERSE_PATH_INCOMPLETE")
    lowest = float(np.min(window_lo))
    highest = float(np.max(window_hi))
    if lowest <= 0.0 or highest <= 0.0:
        raise RuntimeError("ADVERSE_PATH_NONPOSITIVE")
    return max(abs(math.log(highest / p0)), abs(math.log(lowest / p0)))


def _pearson(a: np.ndarray, b: np.ndarray) -> float:
    left = a - a.mean()
    right = b - b.mean()
    denom = math.sqrt(float(np.dot(left, left) * np.dot(right, right)))
    if denom == 0.0:
        return float("nan")
    return float(np.dot(left, right) / denom)


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    return _pearson(average_ranks(np.asarray(a, dtype=np.float64)), average_ranks(np.asarray(b, dtype=np.float64)))


def incremental_rho(state: np.ndarray, outcome: np.ndarray, rv: np.ndarray) -> float:
    row = partial_spearman(state, outcome, rv)
    if row["degenerate"] or row["rho"] is None:
        return float("nan")
    return float(row["rho"])


def _quantile_interval(draws: np.ndarray) -> dict:
    finite = draws[np.isfinite(draws)]
    valid = int(finite.size)
    fraction = valid / float(draws.size)
    interpretable = fraction >= K.MIN_VALID_FRACTION
    if valid == 0:
        lo = hi = float("nan")
    else:
        lo, hi = np.quantile(finite, [K.BOOT_LO, K.BOOT_HI], method="linear")
    return {
        "lo": float(lo),
        "hi": float(hi),
        "valid_draws": valid,
        "valid_fraction": fraction,
        "interpretable": bool(interpretable),
        "share_positive": None if valid == 0 else float(np.mean(finite > 0.0)),
    }


def _bootstrap(state, outcome, rv, weeks, *, draws: int, seed: int) -> dict:
    order = {}
    for i, week in enumerate(weeks):
        order.setdefault(week, []).append(i)
    keys = sorted(order)
    groups = [np.asarray(order[key], dtype=np.int64) for key in keys]
    n_weeks = len(groups)
    rng = np.random.default_rng(seed)
    raw = np.empty(draws, dtype=np.float64)
    partial = np.empty(draws, dtype=np.float64)
    for draw in range(draws):
        picked = rng.choice(n_weeks, size=n_weeks, replace=True)
        idx = np.concatenate([groups[int(j)] for j in picked])
        raw[draw] = spearman(state[idx], outcome[idx])
        partial[draw] = incremental_rho(state[idx], outcome[idx], rv[idx])
    return {"raw": _quantile_interval(raw), "partial": _quantile_interval(partial), "draws": draws, "weeks": n_weeks}


def bin_id(state: np.ndarray) -> np.ndarray:
    edges = np.asarray(K.BIN_EDGES, dtype=np.float64)
    return np.searchsorted(edges, np.asarray(state, dtype=np.float64), side="right").astype(np.int64)


def _bin_table(state: np.ndarray, outcome: np.ndarray) -> list[dict]:
    labels = ("[0, 0.10)", "[0.10, 0.25)", "[0.25, 0.75)", "[0.75, 0.90)", "[0.90, 1]")
    ident = bin_id(state)
    rows = []
    for i, label in enumerate(labels):
        mask = ident == i
        rows.append({
            "bin": label,
            "n": int(mask.sum()),
            "mean_adverse": None if not np.any(mask) else float(np.mean(outcome[mask])),
            "route_input": False,
        })
    return rows


def _year_table(year: np.ndarray, state: np.ndarray, outcome: np.ndarray, rv: np.ndarray) -> list[dict]:
    rows = []
    for value in sorted(set(int(v) for v in year)):
        mask = year == value
        rows.append({
            "year": value,
            "n": int(mask.sum()),
            "spearman": spearman(state[mask], outcome[mask]),
            "partial": incremental_rho(state[mask], outcome[mask], rv[mask]),
            "route_input": False,
        })
    return rows


def _side_table(rate: np.ndarray, state: np.ndarray, outcome: np.ndarray) -> list[dict]:
    rows = []
    for name, mask in (("positive_funding", rate > 0.0), ("negative_funding", rate < 0.0)):
        rows.append({
            "side": name,
            "n": int(mask.sum()),
            "spearman": None if int(mask.sum()) < 3 else spearman(state[mask], outcome[mask]),
            "route_input": False,
        })
    return rows


def summarize(frame: dict, *, bootstrap: bool = True) -> dict:
    state = np.asarray(frame["state"], dtype=np.float64)
    outcome = np.asarray(frame["adverse_8h"], dtype=np.float64)
    rv = np.asarray(frame["rv"], dtype=np.float64)
    raw = spearman(state, outcome)
    partial = incremental_rho(state, outcome, rv)
    out = {
        "n": int(state.size),
        "n_weeks": len(set(frame["week"])),
        "n_zero_rate": int(np.sum(np.asarray(frame["rate"], dtype=np.float64) == 0.0)),
        "spearman": raw,
        "partial": partial,
        "bins": _bin_table(state, outcome),
        "years": _year_table(np.asarray(frame["year"]), state, outcome, rv),
        "sides": _side_table(np.asarray(frame["rate"]), state, outcome),
        "secondary": [],
    }
    for name in ("adverse_1h", "adverse_4h", "abs_excursion_8h"):
        y = np.asarray(frame[name], dtype=np.float64)
        out["secondary"].append({
            "name": name,
            "spearman": spearman(state, y),
            "partial": incremental_rho(state, y, rv),
            "route_input": False,
        })
    if bootstrap:
        out["interval"] = _bootstrap(
            state, outcome, rv, list(frame["week"]), draws=K.BOOT_DRAWS, seed=K.BOOT_SEED,
        )
    return out


def interpret(summary: dict) -> dict:
    """Sign and interval exclusion only. Bins, years, sides, and secondary horizons are invisible."""
    interval = summary["interval"]["partial"]
    point = summary["partial"]
    if not interval["interpretable"] or point is None or not math.isfinite(point):
        code = K.CODE_NOT_INTERPRETABLE
    elif point > 0.0 and interval["lo"] > 0.0:
        code = K.CODE_POSITIVE
    elif point < 0.0 and interval["hi"] < 0.0:
        code = K.CODE_NEGATIVE
    else:
        code = K.CODE_UNCERTAIN
    return {
        "code": code,
        "product_integration_candidate": False,
        "evidence_tier_raised": False,
        "market_04_rewritten": False,
        "causal_claim": False,
        "bins_are_route_inputs": False,
    }
