"""Training-only rank scores, yearly expanding OLS, and the paired-loss bootstrap.

No market loader belongs in this module. The transformations and the
interpretation labels are the frozen design.
"""

from __future__ import annotations

import datetime as dt
import math

import numpy as np

from scripts.research.formation_width_regime_v1.amendment_a1 import average_ranks

from . import constants as K

UTC = dt.timezone.utc

CODE_NOT_INTERPRETABLE = "INFERENCE_NOT_INTERPRETABLE"
CODE_DISAGREE = "VENUES_DO_NOT_AGREE"
CODE_BOTH_POSITIVE = "POSITIVE_INCREMENTAL_PREDICTIVE_VALUE_WITHIN_MODEL_CLASS"
CODE_BOTH_NEGATIVE = "PARTIAL_CORRELATION_DID_NOT_TRANSLATE"
CODE_POINTS_POSITIVE = "POINT_ESTIMATES_FAVOR_GAIN_INTERVALS_DO_NOT_BOTH_EXCLUDE_ZERO"
CODE_POINTS_NOT_POSITIVE = "POINT_ESTIMATES_DO_NOT_FAVOR_WIDTH"


def day_ms(day: str) -> int:
    stamp = dt.datetime.fromisoformat(day).replace(tzinfo=UTC)
    return int(stamp.timestamp() * 1000)


def train_rank_scores(train: np.ndarray) -> np.ndarray:
    """Midrank scores. Not the test-point map."""
    column = np.asarray(train, dtype=np.float64)
    n = int(column.shape[0])
    if n < 1 or not np.all(np.isfinite(column)):
        raise RuntimeError("training rank scores need a finite column")
    return average_ranks(column) / float(n + 1)


def apply_train_rank_scores(train: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Map values through the training multiset only.

    rank = 1 + #{train < x} + 0.5 * #{train == x}, divided by (n_train + 1).
    Other values in `values` do not enter the map.
    """
    reference = np.asarray(train, dtype=np.float64)
    column = np.asarray(values, dtype=np.float64)
    n = int(reference.shape[0])
    if n < 1 or not np.all(np.isfinite(reference)) or not np.all(np.isfinite(column)):
        raise RuntimeError("test rank scores need finite inputs")
    ordered = np.sort(reference, kind="mergesort")
    less = np.searchsorted(ordered, column, side="left")
    not_greater = np.searchsorted(ordered, column, side="right")
    rank = 1.0 + less.astype(np.float64) + 0.5 * (not_greater - less).astype(np.float64)
    return rank / float(n + 1)


def insertion_rank_scores(train: np.ndarray) -> np.ndarray:
    """The test map applied to the training points themselves.

    This is not the training score. It exists so a test can show the two maps differ.
    """
    return apply_train_rank_scores(train, train)


def _design(columns: list[np.ndarray]) -> np.ndarray:
    parts = [np.ones(len(columns[0]), dtype=np.float64)]
    parts.extend(np.asarray(column, dtype=np.float64) for column in columns)
    return np.column_stack(parts)


def ols_predict(train_columns: list[np.ndarray], y_train: np.ndarray, test_columns: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    design = _design(train_columns)
    rank = int(np.linalg.matrix_rank(design))
    if rank < design.shape[1]:
        raise RuntimeError("FOLD_RANK_DEFICIENT")
    beta, _, _, _ = np.linalg.lstsq(design, np.asarray(y_train, dtype=np.float64), rcond=None)
    prediction = _design(test_columns) @ beta
    return np.asarray(prediction, dtype=np.float64), np.asarray(beta, dtype=np.float64)


def fold_masks(day_values: np.ndarray, venue_start: str) -> list[tuple[np.ndarray, np.ndarray, str, str]]:
    start = day_ms(venue_start)
    stamps = np.asarray(day_values, dtype=np.int64)
    masks = []
    for test_start, test_end in K.TEST_FOLDS:
        left = day_ms(test_start)
        right = day_ms(test_end)
        train = np.flatnonzero((stamps >= start) & (stamps < left))
        test = np.flatnonzero((stamps >= left) & (stamps < right))
        masks.append((train, test, test_start, test_end))
    return masks


def _mse(y: np.ndarray, pred: np.ndarray) -> float:
    error = np.asarray(y, dtype=np.float64) - np.asarray(pred, dtype=np.float64)
    return float(np.dot(error, error) / len(error))


def spearman(prediction: np.ndarray, actual: np.ndarray) -> float | None:
    left = average_ranks(np.asarray(prediction, dtype=np.float64))
    right = average_ranks(np.asarray(actual, dtype=np.float64))
    left = left - float(left.mean())
    right = right - float(right.mean())
    denom = math.sqrt(float(np.dot(left, left) * np.dot(right, right)))
    if denom == 0.0 or not math.isfinite(denom):
        return None
    return float(np.dot(left, right) / denom)


def block_bootstrap_means(differences: np.ndarray, week_keys: list[tuple[int, int]], *, draws: int, seed: int) -> np.ndarray:
    """Resample ISO weeks of already formed paired losses. Does not refit."""
    column = np.asarray(differences, dtype=np.float64)
    if len(column) != len(week_keys):
        raise RuntimeError("bootstrap length mismatch")
    weeks = sorted(set(week_keys))
    groups = {week: [] for week in weeks}
    for index, week in enumerate(week_keys):
        groups[week].append(index)
    week_sum = np.asarray([float(column[groups[week]].sum()) for week in weeks], dtype=np.float64)
    week_n = np.asarray([float(len(groups[week])) for week in weeks], dtype=np.float64)
    rng = np.random.default_rng(seed)
    out = np.empty(draws, dtype=np.float64)
    n_weeks = len(weeks)
    for draw in range(draws):
        picked = rng.choice(n_weeks, size=n_weeks, replace=True)
        out[draw] = float(week_sum[picked].sum() / week_n[picked].sum())
    return out


def _interval(samples: np.ndarray) -> dict:
    column = np.asarray(samples, dtype=np.float64)
    finite = column[np.isfinite(column)]
    fraction = float(len(finite) / len(column)) if len(column) else 0.0
    if fraction < K.MIN_VALID_FRACTION or len(finite) == 0:
        return {
            "lo": None,
            "hi": None,
            "valid_fraction": fraction,
            "valid_draws": int(len(finite)),
            "interpretable": False,
            "share_positive": None,
        }
    lo, hi = np.quantile(finite, [K.QUANTILE_LO, K.QUANTILE_HI], method="linear")
    return {
        "lo": float(lo),
        "hi": float(hi),
        "valid_fraction": fraction,
        "valid_draws": int(len(finite)),
        "interpretable": True,
        "share_positive": float(np.mean(finite > 0.0)),
    }


def evaluate_surface(
    day_values: np.ndarray,
    rv: np.ndarray,
    width: np.ndarray,
    activity: np.ndarray,
    week_keys: list[tuple[int, int]],
    *,
    venue_start: str,
    seed: int,
    draws: int = K.BOOT_DRAWS,
) -> dict:
    """One venue. Baseline and candidate share rows, folds, target scores, and the RV score."""
    stamps = np.asarray(day_values, dtype=np.int64)
    rv = np.asarray(rv, dtype=np.float64)
    width = np.asarray(width, dtype=np.float64)
    activity = np.asarray(activity, dtype=np.float64)
    n = int(len(stamps))
    if not (n == len(rv) == len(width) == len(activity) == len(week_keys)):
        raise RuntimeError("surface columns differ in length")
    if n < 1 or not (np.all(np.isfinite(rv)) and np.all(np.isfinite(width)) and np.all(np.isfinite(activity))):
        raise RuntimeError("surface columns must be finite")

    y_parts = []
    pred_b_parts = []
    pred_c_parts = []
    raw_parts = []
    week_parts = []
    folds = []
    for train, test, test_start, test_end in fold_masks(stamps, venue_start):
        if len(train) < K.MIN_TRAIN or len(test) < K.MIN_TEST:
            raise RuntimeError(
                f"FOLD_BELOW_FROZEN_MINIMUM {venue_start} {test_start} train={len(train)} test={len(test)}"
            )
        y_train = train_rank_scores(activity[train])
        y_test = apply_train_rank_scores(activity[train], activity[test])
        rv_train = train_rank_scores(rv[train])
        rv_test = apply_train_rank_scores(rv[train], rv[test])
        v_train = train_rank_scores(width[train])
        v_test = apply_train_rank_scores(width[train], width[test])
        pred_b, beta_b = ols_predict([rv_train], y_train, [rv_test])
        pred_c, beta_c = ols_predict([rv_train, v_train], y_train, [rv_test, v_test])
        mse_b = _mse(y_test, pred_b)
        mse_c = _mse(y_test, pred_c)
        delta = mse_b - mse_c
        if mse_b == 0.0:
            raise RuntimeError("BASELINE_LOSS_DEGENERATE")
        folds.append({
            "test_start": test_start,
            "test_end_exclusive": test_end,
            "n_train": int(len(train)),
            "n_test": int(len(test)),
            "mse_baseline": mse_b,
            "mse_candidate": mse_c,
            "delta_mse": delta,
            "relative": delta / mse_b,
            "beta_baseline": [float(item) for item in beta_b],
            "beta_candidate": [float(item) for item in beta_c],
        })
        y_parts.append(y_test)
        pred_b_parts.append(pred_b)
        pred_c_parts.append(pred_c)
        raw_parts.append(activity[test])
        week_parts.extend(week_keys[int(index)] for index in test)

    y = np.concatenate(y_parts)
    pred_b = np.concatenate(pred_b_parts)
    pred_c = np.concatenate(pred_c_parts)
    raw = np.concatenate(raw_parts)
    mse_b = _mse(y, pred_b)
    mse_c = _mse(y, pred_c)
    differences = (y - pred_b) ** 2 - (y - pred_c) ** 2
    delta = float(differences.mean())
    if not math.isclose(delta, mse_b - mse_c, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError("pooled delta left the paired mean")
    if mse_b == 0.0:
        raise RuntimeError("BASELINE_LOSS_DEGENERATE")
    samples = block_bootstrap_means(differences, week_parts, draws=draws, seed=seed)
    return {
        "n_analysis": n,
        "n_oos": int(len(y)),
        "oos_iso_weeks": len(set(week_parts)),
        "mse_baseline": mse_b,
        "mse_candidate": mse_c,
        "rmse_baseline": float(math.sqrt(mse_b)),
        "rmse_candidate": float(math.sqrt(mse_c)),
        "delta_mse": delta,
        "relative": delta / mse_b,
        "relative_percent": 100.0 * delta / mse_b,
        "spearman_baseline": spearman(pred_b, raw),
        "spearman_candidate": spearman(pred_c, raw),
        "interval": _interval(samples),
        "folds": folds,
        "seed": seed,
        "draws": draws,
    }


def interpret(binance: dict, bybit: dict) -> dict:
    """Label the frozen interval geometry. Magnitude stays in the venue tables."""
    left = binance["interval"]
    right = bybit["interval"]
    if not (left["interpretable"] and right["interpretable"]):
        code = CODE_NOT_INTERPRETABLE
        text = "The block bootstrap did not produce an interpretable interval on both venues."
    elif binance["delta_mse"] * bybit["delta_mse"] < 0.0:
        code = CODE_DISAGREE
        text = "The two venues do not agree on the sign of the incremental predictive gain."
    elif left["lo"] > 0.0 and right["lo"] > 0.0:
        code = CODE_BOTH_POSITIVE
        text = (
            "Width carries predictive information not fully captured by formation realized "
            "volatility within this model class. The gain is the estimated magnitude on each "
            "venue. This is not a statement that width causes activity."
        )
    elif left["hi"] < 0.0 and right["hi"] < 0.0:
        code = CODE_BOTH_NEGATIVE
        text = "The partial correlation did not translate into robust out-of-sample predictive improvement."
    elif binance["delta_mse"] > 0.0 and bybit["delta_mse"] > 0.0:
        code = CODE_POINTS_POSITIVE
        text = (
            "Point estimates favor a gain from width on both venues. The uncertainty intervals "
            "do not both lie entirely above zero."
        )
    else:
        code = CODE_POINTS_NOT_POSITIVE
        text = "Point estimates do not favor width under this frozen evaluation."
    return {
        "code": code,
        "text": text,
        "sign_agreement": bool(binance["delta_mse"] * bybit["delta_mse"] > 0.0),
        "pooling": "none",
        "future_validation_decided": False,
        "product_decision": False,
        "evidence_tier_raised": False,
    }
