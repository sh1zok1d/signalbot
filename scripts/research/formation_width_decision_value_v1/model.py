"""Train-only logistic decisions for upper-quartile next-hour activity.

No market loader belongs here. The route reads signs and intervals only.
"""

from __future__ import annotations

import numpy as np

from scripts.research.formation_width_incremental_predictive_value_v1.model import (
    apply_train_rank_scores,
    train_rank_scores,
)
from scripts.research.formation_width_regime_v1.amendment_a1 import average_ranks

from . import constants as K

CODE_NOT_INTERPRETABLE = "INFERENCE_NOT_INTERPRETABLE"
CODE_HETEROGENEOUS = "WIDTH_DECISION_EFFECT_HETEROGENEOUS"
CODE_CONSISTENT = "WIDTH_ADDS_CONSISTENT_DECISION_VALUE"
CODE_LITTLE = "WIDTH_ADDS_LITTLE_OR_NO_DECISION_VALUE"
CODE_UNCERTAIN = "WIDTH_SIGNAL_PRESENT_DECISION_VALUE_UNCERTAIN"


def _sigmoid(eta: np.ndarray) -> np.ndarray:
    z = np.asarray(eta, dtype=np.float64)
    out = np.empty(z.shape, dtype=np.float64)
    positive = z >= 0.0
    out[positive] = 1.0 / (1.0 + np.exp(-z[positive]))
    ez = np.exp(z[~positive])
    out[~positive] = ez / (1.0 + ez)
    return out


def _design(columns: list[np.ndarray]) -> np.ndarray:
    parts = [np.ones(len(columns[0]), dtype=np.float64)]
    parts.extend(np.asarray(column, dtype=np.float64) for column in columns)
    return np.column_stack(parts)


def fit_logistic(train_columns: list[np.ndarray], y_train: np.ndarray) -> np.ndarray:
    """Unpenalized Newton. Stops on singularity, a non-finite step, or the iteration budget."""
    design = _design(train_columns)
    y = np.asarray(y_train, dtype=np.float64)
    if int(np.linalg.matrix_rank(design)) < design.shape[1]:
        raise RuntimeError("FOLD_RANK_DEFICIENT")
    beta = np.zeros(design.shape[1], dtype=np.float64)
    for _ in range(K.NEWTON_MAX_ITER):
        p = _sigmoid(design @ beta)
        w = p * (1.0 - p)
        weighted = design * w[:, None]
        hessian = design.T @ weighted
        gradient = design.T @ (y - p)
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError as exc:
            raise RuntimeError("FOLD_RANK_DEFICIENT") from exc
        if not np.all(np.isfinite(step)):
            raise RuntimeError("LOGISTIC_DID_NOT_CONVERGE")
        beta = beta + step
        if float(np.max(np.abs(step))) < K.NEWTON_TOL:
            return beta
    raise RuntimeError("LOGISTIC_DID_NOT_CONVERGE")


def predict_logistic(beta: np.ndarray, columns: list[np.ndarray]) -> np.ndarray:
    return _sigmoid(_design(columns) @ np.asarray(beta, dtype=np.float64))


def auroc(score: np.ndarray, label: np.ndarray) -> float | None:
    y = np.asarray(label, dtype=np.float64)
    s = np.asarray(score, dtype=np.float64)
    positive = y == 1.0
    n_pos = int(np.count_nonzero(positive))
    n_neg = int(len(y) - n_pos)
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = average_ranks(s)
    sum_pos = float(ranks[positive].sum())
    return (sum_pos - n_pos * (n_pos + 1) / 2.0) / float(n_pos * n_neg)


def _interval(samples: np.ndarray) -> dict:
    column = np.asarray(samples, dtype=np.float64)
    finite = column[np.isfinite(column)]
    fraction = float(len(finite) / len(column)) if len(column) else 0.0
    if fraction < K.MIN_VALID_FRACTION or len(finite) == 0:
        return {"lo": None, "hi": None, "valid_fraction": fraction, "valid_draws": int(len(finite)),
                "interpretable": False}
    lo, hi = np.quantile(finite, [K.QUANTILE_LO, K.QUANTILE_HI], method="linear")
    return {"lo": float(lo), "hi": float(hi), "valid_fraction": fraction, "valid_draws": int(len(finite)),
            "interpretable": True, "share_positive": float(np.mean(finite > 0.0))}


def _bootstrap(d_net, d_brier, p_b, p_c, y, week_keys, *, draws: int, seed: int) -> dict:
    weeks = sorted(set(week_keys))
    groups = {week: [] for week in weeks}
    for index, week in enumerate(week_keys):
        groups[week].append(index)
    lists = [np.asarray(groups[week], dtype=np.int64) for week in weeks]
    rng = np.random.default_rng(seed)
    n_weeks = len(weeks)
    net_s = np.empty(draws, dtype=np.float64)
    brier_s = np.empty(draws, dtype=np.float64)
    auroc_s = np.empty(draws, dtype=np.float64)
    for draw in range(draws):
        picked = rng.choice(n_weeks, size=n_weeks, replace=True)
        idx = np.concatenate([lists[int(choice)] for choice in picked])
        net_s[draw] = float(d_net[idx].mean())
        brier_s[draw] = float(d_brier[idx].mean())
        left = auroc(p_b[idx], y[idx])
        right = auroc(p_c[idx], y[idx])
        auroc_s[draw] = np.nan if left is None or right is None else right - left
    return {"net": _interval(net_s), "brier": _interval(brier_s), "auroc": _interval(auroc_s)}


def _quartile_id(train: np.ndarray, values: np.ndarray) -> np.ndarray:
    edges = np.quantile(np.asarray(train, dtype=np.float64), [0.25, 0.50, 0.75], method="linear")
    return np.searchsorted(edges, np.asarray(values, dtype=np.float64), side="right")


def _cell(mask: np.ndarray, changed, d_net, d_brier) -> dict:
    n = int(np.count_nonzero(mask))
    if n == 0:
        return {"n": 0, "decision_change_rate": None, "net": None, "brier_gain": None}
    return {
        "n": n,
        "decision_change_rate": float(changed[mask].mean()),
        "net": float(d_net[mask].mean()),
        "brier_gain": float(d_brier[mask].mean()),
    }


def _one_cut(rv, width, activity, train, test, quantile: float) -> dict:
    q = float(np.quantile(activity[train], quantile, method="linear"))
    y_train = (activity[train] >= q).astype(np.float64)
    y_test = (activity[test] >= q).astype(np.float64)
    if int(y_train.sum()) < K.MIN_CLASS or int((1.0 - y_train).sum()) < K.MIN_CLASS:
        raise RuntimeError("CLASS_DEGENERATE")
    rv_train = train_rank_scores(rv[train])
    rv_test = apply_train_rank_scores(rv[train], rv[test])
    v_train = train_rank_scores(width[train])
    v_test = apply_train_rank_scores(width[train], width[test])
    beta_b = fit_logistic([rv_train], y_train)
    beta_c = fit_logistic([rv_train, v_train], y_train)
    p_b_train = predict_logistic(beta_b, [rv_train])
    p_c_train = predict_logistic(beta_c, [rv_train, v_train])
    p_b = predict_logistic(beta_b, [rv_test])
    p_c = predict_logistic(beta_c, [rv_test, v_test])
    tau_b = float(np.quantile(p_b_train, quantile, method="linear"))
    tau_c = float(np.quantile(p_c_train, quantile, method="linear"))
    call_b = p_b >= tau_b
    call_c = p_c >= tau_c
    return {
        "threshold_activity": q,
        "tau_baseline": tau_b,
        "tau_candidate": tau_c,
        "beta_baseline": [float(v) for v in beta_b],
        "beta_candidate": [float(v) for v in beta_c],
        "y": y_test,
        "p_baseline": p_b,
        "p_candidate": p_c,
        "call_baseline": call_b,
        "call_candidate": call_c,
        "train_high_rate": float(y_train.mean()),
    }


def _pack(parts: list[dict], *, quantile: float, draws: int, seed: int, bootstrap: bool,
          with_rows: bool, train_slices: list[dict] | None) -> dict:
    y = np.concatenate([p["y"] for p in parts])
    p_b = np.concatenate([p["p_baseline"] for p in parts])
    p_c = np.concatenate([p["p_candidate"] for p in parts])
    call_b = np.concatenate([p["call_baseline"] for p in parts])
    call_c = np.concatenate([p["call_candidate"] for p in parts])
    changed = call_b != call_c
    observed = y == 1.0
    d_net = (call_c == observed).astype(np.float64) - (call_b == observed).astype(np.float64)
    d_brier = (p_b - y) ** 2 - (p_c - y) ** 2
    n = int(len(y))
    n_changed = int(changed.sum())
    upgrade = changed & call_c & ~call_b
    downgrade = changed & call_b & ~call_c
    correct = changed & (d_net > 0)
    harmful = changed & (d_net < 0)
    brier_b = float(np.mean((p_b - y) ** 2))
    brier_c = float(np.mean((p_c - y) ** 2))
    auc_b = auroc(p_b, y)
    auc_c = auroc(p_c, y)
    out = {
        "route_input": bool(bootstrap),
        "quantile": quantile,
        "n_oos": n,
        "high_rate": float(y.mean()),
        "decision_change_rate": float(changed.mean()),
        "n_changed": n_changed,
        "n_correct_changes": int(correct.sum()),
        "n_harmful_changes": int(harmful.sum()),
        "correct_change_rate": None if n_changed == 0 else float(correct.sum() / n_changed),
        "harmful_change_rate": None if n_changed == 0 else float(harmful.sum() / n_changed),
        "n_upgrade": int(upgrade.sum()),
        "n_downgrade": int(downgrade.sum()),
        "upgrade_hit_rate": None if int(upgrade.sum()) == 0 else float(y[upgrade].mean()),
        "downgrade_hit_rate": None if int(downgrade.sum()) == 0 else float(1.0 - y[downgrade].mean()),
        "net": float(d_net.mean()),
        "brier_baseline": brier_b,
        "brier_candidate": brier_c,
        "brier_gain": float(d_brier.mean()),
        "brier_relative": None if brier_b == 0.0 else float(d_brier.mean() / brier_b),
        "auroc_baseline": auc_b,
        "auroc_candidate": auc_c,
        "auroc_change": None if auc_b is None or auc_c is None else float(auc_c - auc_b),
    }
    if with_rows and train_slices is not None:
        weeks = []
        rows = []
        for part, sl in zip(parts, train_slices):
            for i in range(len(part["y"])):
                rows.append({
                    "day_ms": int(sl["day_ms"][i]),
                    "fold": sl["fold"],
                    "y": int(part["y"][i]),
                    "p_baseline": float(part["p_baseline"][i]),
                    "p_candidate": float(part["p_candidate"][i]),
                    "call_baseline": int(part["call_baseline"][i]),
                    "call_candidate": int(part["call_candidate"][i]),
                })
            weeks.extend(sl["week"])
        out["rows"] = rows
        bin_p = np.concatenate([sl["bin_p"] for sl in train_slices])
        bin_w = np.concatenate([sl["bin_w"] for sl in train_slices])
        bin_rv = np.concatenate([sl["bin_rv"] for sl in train_slices])
        fold_id = np.concatenate([
            np.full(len(sl["week"]), sl["fold_index"], dtype=np.int64) for sl in train_slices
        ])
        out["decomposition"] = {
            "role": "descriptive_only",
            "baseline_probability_quartile": [
                _cell(bin_p == i, changed, d_net, d_brier) for i in range(4)
            ],
            "width_quartile": [_cell(bin_w == i, changed, d_net, d_brier) for i in range(4)],
            "rv_formation_quartile": [_cell(bin_rv == i, changed, d_net, d_brier) for i in range(4)],
            "folds": [_cell(fold_id == i, changed, d_net, d_brier) for i in range(len(parts))],
        }
        if bootstrap:
            out["interval"] = _bootstrap(
                d_net, d_brier, p_b, p_c, y, weeks, draws=draws, seed=seed,
            )
    return out


def evaluate_surface(day_values, rv, width, activity, week_keys, *, venue_start: str, seed: int,
                     draws: int = K.BOOT_DRAWS) -> dict:
    from scripts.research.formation_width_incremental_predictive_value_v1.model import day_ms

    stamps = np.asarray(day_values, dtype=np.int64)
    rv = np.asarray(rv, dtype=np.float64)
    width = np.asarray(width, dtype=np.float64)
    activity = np.asarray(activity, dtype=np.float64)
    start = day_ms(venue_start)
    primary_parts = []
    slices = []
    descriptive = []
    fold_index = 0
    for test_start, test_end in K.TEST_FOLDS:
        left = day_ms(test_start)
        right = day_ms(test_end)
        train = np.flatnonzero((stamps >= start) & (stamps < left))
        test = np.flatnonzero((stamps >= left) & (stamps < right))
        if len(train) < K.MIN_TRAIN or len(test) < K.MIN_TEST:
            raise RuntimeError(
                f"FOLD_BELOW_FROZEN_MINIMUM {venue_start} {test_start} train={len(train)} test={len(test)}"
            )
        primary = _one_cut(rv, width, activity, train, test, K.PRIMARY_QUANTILE)
        primary_parts.append(primary)
        p_train = predict_logistic(
            np.asarray(primary["beta_baseline"], dtype=np.float64),
            [train_rank_scores(rv[train])],
        )
        slices.append({
            "day_ms": stamps[test],
            "week": [week_keys[int(i)] for i in test],
            "fold": test_start,
            "fold_index": fold_index,
            "bin_p": _quartile_id(p_train, primary["p_baseline"]),
            "bin_w": _quartile_id(width[train], width[test]),
            "bin_rv": _quartile_id(rv[train], rv[test]),
        })
        fold_index += 1
    primary_out = _pack(
        primary_parts, quantile=K.PRIMARY_QUANTILE, draws=draws, seed=seed, bootstrap=True,
        with_rows=True, train_slices=slices,
    )
    # Descriptive cuts are refit. They do not receive a bootstrap and are not a route input.
    for quantile in K.DESCRIPTIVE_QUANTILES:
        parts = []
        for test_start, test_end in K.TEST_FOLDS:
            left = day_ms(test_start)
            right = day_ms(test_end)
            train = np.flatnonzero((stamps >= start) & (stamps < left))
            test = np.flatnonzero((stamps >= left) & (stamps < right))
            parts.append(_one_cut(rv, width, activity, train, test, quantile))
        descriptive.append(_pack(
            parts, quantile=quantile, draws=0, seed=seed, bootstrap=False, with_rows=False, train_slices=None,
        ))
    primary_out["folds"] = []
    # Fold point estimates are the decomposition fold cells plus the per-fold fit sizes.
    for part, sl in zip(primary_parts, slices):
        y = part["y"]
        d_net = (part["call_candidate"] == (y == 1.0)).astype(np.float64) - (
            part["call_baseline"] == (y == 1.0)
        ).astype(np.float64)
        d_brier = (part["p_baseline"] - y) ** 2 - (part["p_candidate"] - y) ** 2
        primary_out["folds"].append({
            "test_start": sl["fold"],
            "n_test": int(len(y)),
            "net": float(d_net.mean()),
            "brier_gain": float(d_brier.mean()),
            "decision_change_rate": float((part["call_baseline"] != part["call_candidate"]).mean()),
            "train_high_rate": part["train_high_rate"],
            "beta_candidate": part["beta_candidate"],
        })
    primary_out["descriptive_cuts"] = descriptive
    primary_out["seed"] = seed
    primary_out["draws"] = draws
    return primary_out


def interpret(binance: dict, bybit: dict) -> dict:
    """Sign and interval geometry of net decision improvement and Brier gain. No size floor."""
    pairs = (
        (binance["net"], binance["interval"]["net"]),
        (binance["brier_gain"], binance["interval"]["brier"]),
        (bybit["net"], bybit["interval"]["net"]),
        (bybit["brier_gain"], bybit["interval"]["brier"]),
    )
    if not all(interval["interpretable"] for _point, interval in pairs):
        code = CODE_NOT_INTERPRETABLE
        text = "The block bootstrap did not produce an interpretable interval for every primary estimand on both venues."
    elif binance["net"] * bybit["net"] < 0.0 or binance["brier_gain"] * bybit["brier_gain"] < 0.0:
        code = CODE_HETEROGENEOUS
        text = "The venues do not agree on the sign of the decision improvement or of the Brier improvement."
    elif all(point > 0.0 and interval["lo"] > 0.0 for point, interval in pairs):
        code = CODE_CONSISTENT
        text = (
            "On both venues the upper-quartile calls and the Brier score improve, and each "
            "interval lies above zero. Width changes some forecasts inside this model class, "
            "and those changes improve the frozen decision and the proper score."
        )
    elif all(point <= 0.0 for point, _interval in pairs):
        code = CODE_LITTLE
        text = "Point estimates do not favor a decision or proper-score gain from width."
    else:
        code = CODE_UNCERTAIN
        text = (
            "Point estimates favor a gain from width on at least one primary estimand, and the "
            "intervals do not all lie above zero."
        )
    return {
        "code": code,
        "text": text,
        "pooling": "none",
        "future_validation_decided": False,
        "enter_forecast_architecture": False,
        "product_decision": False,
        "evidence_tier_raised": False,
        "descriptive_cuts_are_route_inputs": False,
    }
