"""Discovery statistics. No magnitude cutoff is applied here."""

from __future__ import annotations

import math

import numpy as np

from scripts.research.formation_width_regime_v1.amendment_a1 import average_ranks, partial_spearman

from . import constants as K


def average_ranks_fast(values: np.ndarray) -> np.ndarray:
    """Same tie-average ranks as average_ranks, without a Python loop over ties."""
    x = np.asarray(values, dtype=np.float64)
    n = int(x.shape[0])
    order = np.argsort(x, kind="mergesort")
    sorted_x = x[order]
    change = np.empty(n, dtype=bool)
    change[0] = True
    if n > 1:
        change[1:] = sorted_x[1:] != sorted_x[:-1]
    starts = np.flatnonzero(change)
    ends = np.empty(starts.shape[0], dtype=np.int64)
    ends[:-1] = starts[1:]
    ends[-1] = n
    avg = 0.5 * ((starts.astype(np.float64) + 1.0) + ends.astype(np.float64))
    ranks = np.empty(n, dtype=np.float64)
    ranks[order] = np.repeat(avg, ends - starts)
    return ranks


def spearman(x: np.ndarray, y: np.ndarray) -> float | None:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.shape[0] < 3 or np.unique(x).size < 2 or np.unique(y).size < 2:
        return None
    rx = average_ranks_fast(x)
    ry = average_ranks_fast(y)
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    denom = math.sqrt(float(np.dot(rx, rx) * np.dot(ry, ry)))
    if denom == 0.0:
        return None
    return float(np.dot(rx, ry) / denom)


def hour_adjust(y: np.ndarray, hour: np.ndarray) -> np.ndarray:
    hour = np.asarray(hour, dtype=np.int64)
    y = np.asarray(y, dtype=np.float64)
    sums = np.bincount(hour, weights=y, minlength=24)
    cnts = np.bincount(hour, minlength=24).astype(np.float64)
    means = np.divide(sums, cnts, out=np.zeros(24, dtype=np.float64), where=cnts > 0)
    return y - means[hour]


def quintile_table(x: np.ndarray, y: np.ndarray) -> dict:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.size < 5:
        return {"degenerate": True, "bins": None, "delta_p": None, "delta_mean": None}
    qs = np.quantile(x, [0.2, 0.4, 0.6, 0.8])
    if not (qs[0] < qs[1] < qs[2] < qs[3]):
        return {"degenerate": True, "bins": None, "delta_p": None, "delta_mean": None, "edges": [float(v) for v in qs]}
    bins = np.digitize(x, qs, right=False)
    rows = []
    for k in range(5):
        m = bins == k
        yy = y[m]
        rows.append({
            "bin": k,
            "n": int(m.sum()),
            "p_up": float(np.mean(yy > 0.0)) if yy.size else None,
            "mean_return": float(yy.mean()) if yy.size else None,
            "median_return": float(np.median(yy)) if yy.size else None,
        })
    top, bot = rows[4], rows[0]
    delta_p = None if top["p_up"] is None or bot["p_up"] is None else float(top["p_up"] - bot["p_up"])
    delta_mean = None if top["mean_return"] is None or bot["mean_return"] is None else float(top["mean_return"] - bot["mean_return"])
    return {
        "degenerate": False,
        "edges": [float(v) for v in qs],
        "bins": rows,
        "delta_p": delta_p,
        "delta_mean": delta_mean,
    }


def state_from_sign(table: dict, rho: float | None, y: np.ndarray) -> dict:
    """The state is the top quintile when rho > 0 and the bottom quintile when rho < 0."""
    baseline_p = float(np.mean(np.asarray(y) > 0.0)) if len(y) else None
    baseline_mean = float(np.mean(y)) if len(y) else None
    empty = {
        "side": None, "p_up": None, "baseline_p_up": baseline_p, "delta_p": None,
        "mean_return": None, "baseline_mean": baseline_mean, "mean_difference": None, "n": None,
    }
    if table.get("degenerate") or rho is None or not math.isfinite(rho) or rho == 0.0:
        return empty
    row = table["bins"][4] if rho > 0.0 else table["bins"][0]
    if row["p_up"] is None:
        return empty
    return {
        "side": "top_quintile" if rho > 0.0 else "bottom_quintile",
        "p_up": row["p_up"],
        "baseline_p_up": baseline_p,
        "delta_p": float(row["p_up"] - baseline_p),
        "mean_return": row["mean_return"],
        "baseline_mean": baseline_mean,
        "mean_difference": float(row["mean_return"] - baseline_mean),
        "n": row["n"],
    }


def weekly_spearman(x: np.ndarray, y: np.ndarray, blocks: np.ndarray) -> dict:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    blocks = np.asarray(blocks)
    rhos = []
    if x.size:
        order = np.argsort(blocks, kind="mergesort")
        bsort = blocks[order]
        xs, ys = x[order], y[order]
        cuts = np.flatnonzero(np.diff(bsort)) + 1
        starts = np.r_[0, cuts]
        ends = np.r_[cuts, bsort.shape[0]]
        for a, b in zip(starts, ends):
            if b - a < K.WEEK_MIN_ANCHORS:
                continue
            rho = spearman(xs[a:b], ys[a:b])
            if rho is not None:
                rhos.append(rho)
    arr = np.asarray(rhos, dtype=np.float64)
    if arr.size == 0:
        return {"n_weeks": 0, "week_mean": None, "week_se": None}
    se = None
    if arr.size > 1:
        se = float(arr.std(ddof=1) / math.sqrt(arr.size))
    return {"n_weeks": int(arr.size), "week_mean": float(arr.mean()), "week_se": se}


def yearly_table(x: np.ndarray, y: np.ndarray, year: np.ndarray) -> list[dict]:
    rows = []
    for yv in sorted(set(int(v) for v in year)):
        m = year == yv
        rho = spearman(x[m], y[m]) if int(m.sum()) >= 3 else None
        rows.append({"year": int(yv), "n": int(m.sum()), "spearman": rho})
    return rows


def discovery_score(rho: float | None, years: list[dict], n_weeks: int) -> float:
    """abs(rho) * year-sign consistency * min(1, n_weeks/100). No correlation floor."""
    if rho is None or not math.isfinite(rho) or rho == 0.0 or n_weeks <= 0:
        return 0.0
    usable = [row for row in years if row["n"] >= K.YEAR_MIN_N and row["spearman"] is not None and math.isfinite(row["spearman"])]
    if not usable:
        return 0.0
    sign = math.copysign(1.0, rho)
    agree = sum(1 for row in usable if math.copysign(1.0, row["spearman"]) == sign and row["spearman"] != 0.0)
    consistency = agree / len(usable)
    support = min(1.0, n_weeks / float(K.SUPPORT_WEEK_SCALE))
    return float(abs(rho) * consistency * support)


def outcome_slices(x: np.ndarray, y: np.ndarray, q10: float, q90: float) -> dict:
    y = np.asarray(y, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    groups = {
        "strong_down": y <= q10,
        "ordinary": (y > q10) & (y < q90),
        "strong_up": y >= q90,
    }
    out = {}
    for name, m in groups.items():
        xx = x[m]
        out[name] = {
            "n": int(m.sum()),
            "mean_feature": float(xx.mean()) if xx.size and np.isfinite(xx).any() else None,
        }
    return out


def half_split(x: np.ndarray, y: np.ndarray, when: np.ndarray) -> dict:
    if x.size < 6:
        return {"first": None, "second": None, "median_t": None}
    med = float(np.median(when))
    left = when <= med
    right = ~left
    return {
        "median_t": med,
        "first": {"n": int(left.sum()), "spearman": spearman(x[left], y[left]) if left.sum() >= 3 else None},
        "second": {"n": int(right.sum()), "spearman": spearman(x[right], y[right]) if right.sum() >= 3 else None},
    }


def leave_one_year_out(x: np.ndarray, y: np.ndarray, year: np.ndarray) -> list[dict]:
    rows = []
    for yv in sorted(set(int(v) for v in year)):
        m = year != yv
        rows.append({"left_out": int(yv), "n": int(m.sum()), "spearman": spearman(x[m], y[m]) if m.sum() >= 3 else None})
    return rows


def _quantile_edges(x: np.ndarray) -> np.ndarray | None:
    if x.size < 5:
        return None
    qs = np.quantile(x, [0.2, 0.4, 0.6, 0.8])
    if not (qs[0] < qs[1] < qs[2] < qs[3]):
        return None
    return qs


def _state_delta(x: np.ndarray, y: np.ndarray, side_top: bool) -> tuple[float | None, float | None]:
    qs = _quantile_edges(x)
    if qs is None:
        return None, None
    bins = np.digitize(x, qs, right=False)
    m = bins == (4 if side_top else 0)
    if not np.any(m):
        return None, None
    yy = y[m]
    p_state = float(np.mean(yy > 0.0))
    p_all = float(np.mean(y > 0.0))
    return p_state - p_all, float(yy.mean() - y.mean())


def bootstrap_cell(x: np.ndarray, y: np.ndarray, blocks: np.ndarray, *, side_top: bool) -> dict:
    """Week-block bootstrap. The state side is locked from the full-sample sign."""
    rng = np.random.default_rng(K.BOOT_SEED)
    uniq, inverse = np.unique(blocks, return_inverse=True)
    groups = [np.flatnonzero(inverse == i) for i in range(uniq.shape[0])]
    n_weeks = len(groups)
    rhos = np.empty(K.BOOT_DRAWS, dtype=np.float64)
    dps = np.empty(K.BOOT_DRAWS, dtype=np.float64)
    dms = np.empty(K.BOOT_DRAWS, dtype=np.float64)
    for draw in range(K.BOOT_DRAWS):
        pick = rng.integers(0, n_weeks, size=n_weeks)
        idx = np.concatenate([groups[i] for i in pick])
        rho = spearman(x[idx], y[idx])
        dp, dm = _state_delta(x[idx], y[idx], side_top)
        rhos[draw] = np.nan if rho is None else rho
        dps[draw] = np.nan if dp is None else dp
        dms[draw] = np.nan if dm is None else dm

    def pack(arr: np.ndarray) -> dict:
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            return {"lo": None, "hi": None, "valid": 0, "draws": K.BOOT_DRAWS}
        return {
            "lo": float(np.quantile(finite, K.BOOT_LO)),
            "hi": float(np.quantile(finite, K.BOOT_HI)),
            "valid": int(finite.size),
            "draws": K.BOOT_DRAWS,
        }

    return {"spearman": pack(rhos), "delta_p": pack(dps), "mean_difference": pack(dms)}


def partial_given_rv(x: np.ndarray, y: np.ndarray, rv: np.ndarray) -> dict:
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(rv)
    if int(mask.sum()) < 3:
        return {"rho": None, "degenerate": True, "n": int(mask.sum())}
    try:
        out = partial_spearman(x[mask], y[mask], rv[mask])
    except RuntimeError:
        return {"rho": None, "degenerate": True, "n": int(mask.sum())}
    return {"rho": out["rho"], "degenerate": bool(out["degenerate"]), "n": int(mask.sum())}


def ranks_match_reference(values: np.ndarray) -> bool:
    a = average_ranks(np.asarray(values, dtype=np.float64))
    b = average_ranks_fast(values)
    return bool(np.allclose(a, b))
