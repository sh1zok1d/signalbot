"""Predeclared state cells. Edges are constants, not sample quantiles."""

from __future__ import annotations

import numpy as np

from . import constants as K


def _labels(edges: tuple[float, ...], kind: str) -> list[str]:
    if kind == "z":
        return ["lt_-1", "m1_to_m0.25", "m0.25_to_0.25", "p0.25_to_1", "ge_1"]
    if kind == "ratio":
        return ["lt_0.7", "0.7_to_1", "1_to_1.4", "ge_1.4"]
    if kind == "pos":
        return ["0_to_0.2", "0.2_to_0.4", "0.4_to_0.6", "0.6_to_0.8", "0.8_to_1"]
    if kind == "sigma":
        return ["lt_1", "1_to_2", "2_to_3", "ge_3"]
    raise KeyError(kind)


def cell_masks(frame: dict) -> list[dict]:
    values = frame["map_values"]
    masks: list[dict] = []

    def add_bins(feature: str, edges: tuple[float, ...], kind: str, family: str) -> None:
        bins = np.digitize(values[feature], np.asarray(edges, dtype=np.float64), right=False)
        for code, label in enumerate(_labels(edges, kind)):
            masks.append({
                "cell": f"{feature}|{label}",
                "family": family,
                "mask": bins == code,
            })

    for feature in ("ret_15m_z", "ret_1h_z", "ret_4h_z"):
        add_bins(feature, K.Z_EDGES, "z", "prior_return")
    add_bins("accel", K.Z_EDGES, "z", "acceleration")
    for feature in ("rv_ratio_15m_1h", "rv_ratio_1h_4h", "rv_ratio_4h_24h"):
        add_bins(feature, K.RATIO_EDGES, "ratio", "volatility_ratio")
    for feature in ("vol_ratio_15m", "vol_ratio_1h", "vol_ratio_4h"):
        add_bins(feature, K.RATIO_EDGES, "ratio", "volume")
    add_bins("range_pos_4h", K.RANGE_POS_EDGES, "pos", "range_position")
    add_bins("range_vs_sigma_4h", K.RANGE_SIGMA_EDGES, "sigma", "range_compression")
    session = np.digitize(frame["hour"], np.asarray([7.0, 13.0, 21.0]), right=False)
    for code, label in enumerate(("asia_0_7", "europe_7_13", "us_13_21", "late_21_24")):
        masks.append({"cell": f"session|{label}", "family": "clock", "mask": session == code})
    for code in range(7):
        masks.append({"cell": f"dow|{code}", "family": "clock", "mask": frame["dow"] == code})
    joints = (
        ("joint|compressed", "joint", (values["rv_ratio_15m_1h"] < 0.7) & (values["range_vs_sigma_4h"] < 1.0)),
        ("joint|already_wide", "joint", (values["rv_ratio_15m_1h"] >= 1.4) & (values["range_vs_sigma_4h"] >= 2.0)),
        ("joint|upper_range_up", "joint", (values["range_pos_4h"] >= 0.8) & (values["ret_4h_z"] >= 0.25)),
        ("joint|lower_range_down", "joint", (values["range_pos_4h"] < 0.2) & (values["ret_4h_z"] <= -0.25)),
        ("joint|quiet_volume_tight", "joint", (values["vol_ratio_1h"] < 0.7) & (values["range_vs_sigma_4h"] < 1.0)),
        ("joint|active_squeeze", "joint", (values["vol_ratio_1h"] >= 1.4) & (values["range_vs_sigma_4h"] < 1.0)),
    )
    for name, family, mask in joints:
        masks.append({"cell": name, "family": family, "mask": np.asarray(mask, dtype=bool)})
    return masks


def _week_mean_interval(delta: np.ndarray, week: np.ndarray, mask: np.ndarray, draws: int, seed: int,
                        cell: str) -> dict:
    kept_week = week[mask]
    kept_delta = delta[mask]
    if kept_week.size == 0:
        return {"lo": None, "hi": None, "valid_draws": 0}
    codes, inverse = np.unique(kept_week, return_inverse=True)
    sums = np.bincount(inverse, weights=kept_delta)
    counts = np.bincount(inverse).astype(np.float64)
    salt = sum((index + 1) * ord(ch) for index, ch in enumerate(cell)) % 1_000_003
    rng = np.random.default_rng(int(seed) + int(salt))
    choice = rng.integers(0, codes.size, size=(int(draws), codes.size))
    out = np.empty(int(draws), dtype=np.float64)
    valid = 0
    for draw, picked in enumerate(choice):
        mult = np.bincount(picked, minlength=codes.size).astype(np.float64)
        denom = float(mult @ counts)
        if denom <= 0.0:
            continue
        out[valid] = float(mult @ sums) / denom
        valid += 1
    if valid < K.MIN_VALID_DRAWS:
        return {"lo": None, "hi": None, "valid_draws": int(valid)}
    taken = out[:valid]
    return {
        "lo": float(np.quantile(taken, K.BOOT_LO)),
        "hi": float(np.quantile(taken, K.BOOT_HI)),
        "valid_draws": int(valid),
    }


def score_cell(delta: float, year_deltas: list[dict], n: int) -> float:
    qualified = [row for row in year_deltas if row["n"] >= K.MIN_YEAR_N]
    if len(qualified) < K.MIN_YEARS_FOR_SCORE or delta == 0.0 or not np.isfinite(delta):
        return 0.0
    sign = 1.0 if delta > 0.0 else -1.0
    agree = sum(1.0 for row in qualified if row["delta"] * sign > 0.0) / float(len(qualified))
    return float(abs(delta) * agree * min(1.0, n / float(K.SCORE_N_SCALE)))


def evaluate_cells(frame: dict, scored: np.ndarray, p_b1: np.ndarray, week: np.ndarray, year: np.ndarray) -> list[dict]:
    y = np.asarray(frame["y"], dtype=np.float64)
    delta = y - np.asarray(p_b1, dtype=np.float64)
    global_rate = float(np.mean(y[scored])) if np.any(scored) else float("nan")
    rows = []
    for spec in cell_masks(frame):
        mask = np.asarray(spec["mask"], dtype=bool) & scored & np.isfinite(p_b1)
        n = int(mask.sum())
        rate = float(np.mean(y[mask])) if n else None
        baseline_b1 = float(np.mean(p_b1[mask])) if n else None
        point = None if rate is None else rate - baseline_b1
        year_rows = []
        if n:
            for one_year in sorted(set(int(v) for v in year[mask])):
                year_mask = mask & (year == one_year)
                n_year = int(year_mask.sum())
                year_rows.append({
                    "year": int(one_year),
                    "n": n_year,
                    "rate": float(np.mean(y[year_mask])) if n_year else None,
                    "delta": float(np.mean(delta[year_mask])) if n_year else None,
                })
        interval = _week_mean_interval(delta, week, mask, K.BOOT_DRAWS, K.CELL_BOOT_SEED, spec["cell"]) if n >= K.MIN_CELL_N else {
            "lo": None, "hi": None, "valid_draws": 0,
        }
        point_value = 0.0 if point is None else float(point)
        cell_score = score_cell(point_value, year_rows, n) if n >= K.MIN_CELL_N else 0.0
        rows.append({
            "cell": spec["cell"],
            "family": spec["family"],
            "n": n,
            "rate": rate,
            "baseline_b0": global_rate,
            "baseline_b1": baseline_b1,
            "delta_vs_b1": point,
            "delta_vs_b0": None if rate is None else rate - global_rate,
            "ratio_vs_b1": None if rate is None or baseline_b1 in (None, 0.0) else rate / baseline_b1,
            "interval_lo": interval["lo"],
            "interval_hi": interval["hi"],
            "valid_draws": interval["valid_draws"],
            "years": year_rows,
            "score": cell_score,
            "low_n": bool(n < K.MIN_CELL_N),
        })
    rows.sort(key=lambda row: (-float(row["score"]), -abs(float(row["delta_vs_b1"] or 0.0)), row["cell"]))
    return rows
