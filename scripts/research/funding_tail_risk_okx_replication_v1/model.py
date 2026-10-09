"""Association statistics for the frozen OKX funding-extremity design.

The future path is an input. This module does not load a market file.
"""

from __future__ import annotations

import datetime as dt
import math

import numpy as np

from scripts.research.funding_state_historical_structure_v1.model import (
    absolute_excursion,
    adverse_long,
    funding_state,
    incremental_rho,
    spearman,
)

from . import constants as K

UTC = dt.timezone.utc
BIN_LABELS = ("[0, 0.10)", "[0.10, 0.25)", "[0.25, 0.75)", "[0.75, 0.90)", "[0.90, 1]")


def decision_time(funding_time_ms: int) -> int | None:
    """UTC hour of a settlement print. None when the print is not on the 8-hour clock."""
    stamp = int(funding_time_ms)
    residual = stamp % K.HOUR_MS
    hour = stamp - residual
    if residual > K.RESIDUAL_MAX_MS:
        return None
    if dt.datetime.fromtimestamp(hour / 1000.0, tz=UTC).hour not in K.SETTLEMENT_HOURS:
        return None
    return hour


def upside(p0: float, highs: np.ndarray) -> float:
    """Mirror of the parent's long-side downside. Zero when the path never prints above P0."""
    window = np.asarray(highs, dtype=np.float64)
    if not np.isfinite(p0) or p0 <= 0.0 or window.size == 0 or not np.all(np.isfinite(window)):
        raise RuntimeError("ADVERSE_PATH_INCOMPLETE")
    highest = float(np.max(window))
    if highest <= 0.0:
        raise RuntimeError("ADVERSE_PATH_NONPOSITIVE")
    rise = math.log(highest / p0)
    return rise if rise > 0.0 else 0.0


def extremity(rank: np.ndarray) -> np.ndarray:
    return np.abs(np.asarray(rank, dtype=np.float64) - 0.5)


def bin_id(rank: np.ndarray) -> np.ndarray:
    edges = np.asarray(K.BIN_EDGES, dtype=np.float64)
    return np.searchsorted(edges, np.asarray(rank, dtype=np.float64), side="right").astype(np.int64)


def _mean(mask: np.ndarray, outcome: np.ndarray) -> float:
    if not np.any(mask):
        return float("nan")
    return float(np.mean(outcome[mask]))


def tail_contrasts(rank: np.ndarray, outcome: np.ndarray) -> tuple[float, float]:
    ident = bin_id(rank)
    center = _mean(ident == 2, outcome)
    upper = _mean(ident == 4, outcome) - center
    lower = _mean(ident == 0, outcome) - center
    return upper, lower


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


def _bootstrap(rank, extremity_values, outcome, rv, weeks, *, draws: int, seed: int) -> dict:
    order = {}
    for i, week in enumerate(weeks):
        order.setdefault(week, []).append(i)
    keys = sorted(order)
    groups = [np.asarray(order[key], dtype=np.int64) for key in keys]
    n_weeks = len(groups)
    rng = np.random.default_rng(seed)
    raw = np.empty(draws, dtype=np.float64)
    partial = np.empty(draws, dtype=np.float64)
    upper = np.empty(draws, dtype=np.float64)
    lower = np.empty(draws, dtype=np.float64)
    for draw in range(draws):
        picked = rng.choice(n_weeks, size=n_weeks, replace=True)
        idx = np.concatenate([groups[int(j)] for j in picked])
        raw[draw] = spearman(extremity_values[idx], outcome[idx])
        partial[draw] = incremental_rho(extremity_values[idx], outcome[idx], rv[idx])
        upper[draw], lower[draw] = tail_contrasts(rank[idx], outcome[idx])
    return {
        "raw": _quantile_interval(raw),
        "partial": _quantile_interval(partial),
        "upper_tail": _quantile_interval(upper),
        "lower_tail": _quantile_interval(lower),
        "draws": draws,
        "weeks": n_weeks,
    }


def _bin_table(rank, outcome, downside, upside_values) -> list[dict]:
    ident = bin_id(rank)
    rows = []
    for i, label in enumerate(BIN_LABELS):
        mask = ident == i
        rows.append({
            "bin": label,
            "n": int(mask.sum()),
            "mean_abs_excursion": None if not np.any(mask) else float(np.mean(outcome[mask])),
            "median_abs_excursion": None if not np.any(mask) else float(np.median(outcome[mask])),
            "mean_downside": None if not np.any(mask) else float(np.mean(downside[mask])),
            "mean_upside": None if not np.any(mask) else float(np.mean(upside_values[mask])),
            "route_input": False,
        })
    return rows


def _year_table(year, extremity_values, outcome, rv) -> list[dict]:
    rows = []
    for value in sorted(set(int(v) for v in year)):
        mask = year == value
        rows.append({
            "year": value,
            "n": int(mask.sum()),
            "spearman": spearman(extremity_values[mask], outcome[mask]),
            "partial": incremental_rho(extremity_values[mask], outcome[mask], rv[mask]),
            "route_input": False,
        })
    return rows


def _side_table(rate, rank, extremity_values, outcome) -> list[dict]:
    rows = []
    for name, mask in (("positive_funding", rate > 0.0), ("negative_funding", rate < 0.0)):
        n = int(mask.sum())
        rows.append({
            "side": name,
            "n": n,
            "spearman_rank": None if n < 3 else spearman(rank[mask], outcome[mask]),
            "spearman_extremity": None if n < 3 else spearman(extremity_values[mask], outcome[mask]),
            "route_input": False,
        })
    return rows


def summarize(frame: dict, *, bootstrap: bool = True) -> dict:
    rank = np.asarray(frame["rank"], dtype=np.float64)
    extremity_values = np.asarray(frame["extremity"], dtype=np.float64)
    outcome = np.asarray(frame["abs_excursion"], dtype=np.float64)
    downside = np.asarray(frame["downside"], dtype=np.float64)
    upside_values = np.asarray(frame["upside"], dtype=np.float64)
    rv = np.asarray(frame["rv"], dtype=np.float64)
    raw = spearman(extremity_values, outcome)
    partial = incremental_rho(extremity_values, outcome, rv)
    upper, lower = tail_contrasts(rank, outcome)
    out = {
        "n": int(rank.size),
        "n_weeks": len(set(frame["week"])),
        "n_zero_rate": int(np.sum(np.asarray(frame["rate"], dtype=np.float64) == 0.0)),
        "spearman": raw,
        "partial": partial,
        "bins": _bin_table(rank, outcome, downside, upside_values),
        "years": _year_table(np.asarray(frame["year"]), extremity_values, outcome, rv),
        "sides": _side_table(np.asarray(frame["rate"]), rank, extremity_values, outcome),
        "contrasts": {
            "upper": {"point": upper, "route_input": False},
            "lower": {"point": lower, "route_input": False},
        },
    }
    if bootstrap:
        out["interval"] = _bootstrap(
            rank, extremity_values, outcome, rv, list(frame["week"]),
            draws=K.BOOT_DRAWS, seed=K.BOOT_SEED,
        )
    return out


def interpret(summary: dict) -> dict:
    """Sign and interval exclusion of the partial only. Bins, years, sides, and tails are invisible."""
    interval = summary["interval"]["partial"]
    point = summary["partial"]
    if not interval["interpretable"] or point is None or not math.isfinite(point):
        code = K.CODE_NOT_INTERPRETABLE
    elif point > 0.0 and interval["lo"] > 0.0:
        code = K.CODE_SUPPORTED
    elif point > 0.0:
        code = K.CODE_UNCERTAIN
    else:
        code = K.CODE_NOT_OBSERVED
    return {
        "code": code,
        "product_integration_candidate": code == K.CODE_SUPPORTED,
        "causal_claim": False,
        "threshold_55_applied": False,
        "practical_rho_applied": False,
    }


def _shape(upper: float, lower: float) -> str:
    upper_up = math.isfinite(upper) and upper > 0.0
    lower_up = math.isfinite(lower) and lower > 0.0
    if upper_up and lower_up:
        return "BOTH_TAILS_ABOVE_CENTER"
    if upper_up != lower_up:
        return "ASYMMETRIC"
    return "TAILS_NOT_ABOVE_CENTER"


def synthesis(summary: dict, interpretation: dict) -> dict:
    """Descriptive comparison. It does not change the route and it applies no similarity cutoff."""
    raw = float(summary["spearman"])
    partial = float(summary["partial"])
    upper = float(summary["contrasts"]["upper"]["point"])
    lower = float(summary["contrasts"]["lower"]["point"])
    if not math.isfinite(raw) or raw <= 0.0:
        attenuation = "RAW_NOT_POSITIVE"
    elif partial < raw:
        attenuation = "CONTROL_REDUCED_THE_POINT"
    else:
        attenuation = "CONTROL_DID_NOT_REDUCE_THE_POINT"
    code = interpretation["code"]
    if code == K.CODE_SUPPORTED:
        conclusion = "A_SUPPORTED"
    elif code == K.CODE_UNCERTAIN:
        conclusion = "B_POINT_POSITIVE_UNCERTAIN"
    elif code == K.CODE_NOT_OBSERVED:
        conclusion = "C_NOT_OBSERVED"
    else:
        conclusion = "NOT_INTERPRETABLE"
    if math.isfinite(partial) and partial > 0.0:
        market_03 = "COMPATIBLE_WITH_HISTORICAL_DRAWDOWN_REDUCTION"
    else:
        market_03 = "NO_POSITIVE_EXTREMITY_ASSOCIATION_TO_PLACE_BESIDE_MARKET_03"
    return {
        "extremity_point_positive": bool(math.isfinite(partial) and partial > 0.0),
        "attenuation": attenuation,
        "upper_tail_above_center": bool(math.isfinite(upper) and upper > 0.0),
        "lower_tail_above_center": bool(math.isfinite(lower) and lower > 0.0),
        "shape": _shape(upper, lower),
        "okx_partial": partial,
        "parent_partial": K.PARENT_PARTIAL,
        "similarity_cutoff_applied": False,
        "conclusion": conclusion,
        "market_03": market_03,
        "causal_claim": False,
        "route_input": False,
    }
