"""Walk-forward scorer for the frozen forecast prototype.

`evaluate_frame` scores an in-memory frame. It does not read a market series.
`main` and `run_market` exit before any price load while `OWNER_GO` is false.
"""

from __future__ import annotations

import numpy as np

from . import constants as K
from .folds import assign_folds, calendar_year, iso_parts, label_available_at
from .model import (
    ImplementationInvalid,
    apply_scaler,
    assign_route,
    brier,
    fit_logistic,
    fit_scaler,
    log_loss,
    predict,
)

TRAIN_SOURCES = {
    "BITMEX_2016_2019": ("BITMEX_2016_2019",),
    "BINANCE_2020_2024": ("BINANCE_2020_2024",),
    "BINANCE_2025_2026": ("BINANCE_2020_2024", "BINANCE_2025_2026"),
}
N_FEATURES = 5
_FOLD_PUBLIC = (
    "segment", "iso_year", "iso_week", "block_start", "n_train", "n_train_weeks", "n_test",
    "max_train_label_available_at", "train_segments",
)


def build_training_matrix(close_ms: np.ndarray, x: np.ndarray, y: np.ndarray, row_segment: np.ndarray,
                          block_start_ms: int, allowed_segments, admit_mask: np.ndarray | None = None):
    """Rows whose label is known by `block_start_ms` and whose source is allowed.

    The availability rule is applied here, on the rows that enter the fit. A caller-supplied
    mask that keeps a late label, a disallowed source, or a non-finite value is invalid.
    """
    close_ms = np.asarray(close_ms, dtype=np.int64)
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    row_segment = np.asarray(row_segment)
    available = label_available_at(close_ms)
    source_ok = np.isin(row_segment, np.asarray(list(allowed_segments)))
    if admit_mask is None:
        admit = (available <= int(block_start_ms)) & source_ok
    else:
        admit = np.asarray(admit_mask, dtype=bool)
        if admit.shape != close_ms.shape:
            raise ImplementationInvalid("ADMIT_MASK_SHAPE")
    if np.any(admit & (available > int(block_start_ms))):
        raise ImplementationInvalid("LABEL_AVAILABILITY_VIOLATION")
    if np.any(admit & ~source_ok):
        raise ImplementationInvalid("TRAINING_SOURCE_VIOLATION")
    if np.any(admit & ~np.isfinite(y)):
        raise ImplementationInvalid("NON_FINITE_TRAINING_VALUE")
    if admit.any() and not np.all(np.isfinite(x[admit])):
        raise ImplementationInvalid("NON_FINITE_TRAINING_VALUE")
    if admit.any() and int(available[admit].max()) > int(block_start_ms):
        raise ImplementationInvalid("LABEL_AVAILABILITY_VIOLATION")
    return x[admit], y[admit], close_ms[admit], available[admit], row_segment[admit]


def _average_ranks(score: np.ndarray) -> np.ndarray:
    order = np.argsort(score, kind="mergesort")
    sorted_score = score[order]
    ranks = np.empty(score.shape[0], dtype=np.float64)
    n = int(score.shape[0])
    start = 0
    while start < n:
        stop = start + 1
        while stop < n and sorted_score[stop] == sorted_score[start]:
            stop += 1
        # 1-based average rank of this tie group.
        average = 0.5 * ((start + 1) + stop)
        ranks[order[start:stop]] = average
        start = stop
    return ranks


def auroc(y: np.ndarray, score: np.ndarray) -> float | None:
    """Mann–Whitney AUROC with average ranks for ties. A one-class sample has no AUROC."""
    y = np.asarray(y, dtype=np.float64)
    score = np.asarray(score, dtype=np.float64)
    n_pos = int(np.sum(y == 1.0))
    n_neg = int(np.sum(y == 0.0))
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = _average_ranks(score)
    sum_pos = float(ranks[y == 1.0].sum())
    return (sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def reliability_table(y: np.ndarray, prob: np.ndarray) -> list[dict]:
    edges = (-np.inf, *K.PROBABILITY_BINS, np.inf)
    y = np.asarray(y, dtype=np.float64)
    prob = np.asarray(prob, dtype=np.float64)
    rows = []
    for left, right in zip(edges[:-1], edges[1:]):
        mask = (prob >= left) & (prob < right) if np.isfinite(left) else (prob < right)
        n = int(mask.sum())
        if n == 0:
            rows.append({
                "bin_left": None if not np.isfinite(left) else float(left),
                "bin_right": None if not np.isfinite(right) else float(right),
                "n": 0,
                "mean_predicted": None,
                "observed_up": None,
                "difference": None,
            })
            continue
        mean_p = float(prob[mask].mean())
        observed = float(y[mask].mean())
        rows.append({
            "bin_left": None if not np.isfinite(left) else float(left),
            "bin_right": None if not np.isfinite(right) else float(right),
            "n": n,
            "mean_predicted": mean_p,
            "observed_up": observed,
            "difference": observed - mean_p,
        })
    return rows


def amplitude(delta: np.ndarray) -> dict:
    delta = np.asarray(delta, dtype=np.float64)
    points = np.quantile(delta, (0.10, 0.25, 0.50, 0.75, 0.90))
    return {
        "minimum": float(delta.min()),
        "p10": float(points[0]),
        "p25": float(points[1]),
        "p50": float(points[2]),
        "p75": float(points[3]),
        "p90": float(points[4]),
        "maximum": float(delta.max()),
        "median_absolute": float(np.median(np.abs(delta))),
    }


def _row_groups(block_id: np.ndarray) -> list[np.ndarray]:
    groups: list[list[int]] = []
    index: dict[int, int] = {}
    for i, raw in enumerate(block_id.tolist()):
        key = int(raw)
        slot = index.get(key)
        if slot is None:
            index[key] = len(groups)
            groups.append([i])
        else:
            groups[slot].append(i)
    return [np.asarray(group, dtype=np.int64) for group in groups]


def resample_rows(groups: list[np.ndarray], choice: np.ndarray) -> np.ndarray:
    """Repeat a block's rows once for each time the draw selects that block."""
    return np.concatenate([groups[int(j)] for j in choice])


def _bootstrap_losses(y: np.ndarray, p_clim: np.ndarray, p_base: np.ndarray, p_cand: np.ndarray,
                      block_id: np.ndarray, draws: int, seed: int) -> dict:
    """Resample stored probabilities. This function does not fit a model."""
    groups = _row_groups(block_id)
    n_blocks = len(groups)
    if n_blocks == 0:
        raise ImplementationInvalid("BOOTSTRAP_WITHOUT_BLOCKS")
    rng = np.random.default_rng(int(seed))
    brier_delta = np.empty(draws, dtype=np.float64)
    log_delta = np.empty(draws, dtype=np.float64)
    valid = 0
    for _ in range(int(draws)):
        choice = rng.integers(0, n_blocks, size=n_blocks)
        idx = resample_rows(groups, choice)
        db = brier(y[idx], p_cand[idx]) - brier(y[idx], p_base[idx])
        dl = log_loss(y[idx], p_cand[idx]) - log_loss(y[idx], p_base[idx])
        if np.isfinite(db) and np.isfinite(dl):
            brier_delta[valid] = db
            log_delta[valid] = dl
            valid += 1
    if valid == 0:
        return {"valid_draws": 0, "brier_lo": None, "brier_hi": None, "logloss_lo": None, "logloss_hi": None}
    taken_b = brier_delta[:valid]
    taken_l = log_delta[:valid]
    return {
        "valid_draws": int(valid),
        "brier_lo": float(np.quantile(taken_b, K.BOOT_LO)),
        "brier_hi": float(np.quantile(taken_b, K.BOOT_HI)),
        "logloss_lo": float(np.quantile(taken_l, K.BOOT_LO)),
        "logloss_hi": float(np.quantile(taken_l, K.BOOT_HI)),
    }


def calibration_coefficients(y: np.ndarray, prob: np.ndarray) -> tuple[float, float]:
    """Unpenalized logistic of Y on logit(clip(p)). Slope is not a recalibration."""
    p = np.clip(np.asarray(prob, dtype=np.float64), K.CALIBRATION_LOGIT_CLIP, 1.0 - K.CALIBRATION_LOGIT_CLIP)
    logit = np.log(p / (1.0 - p)).reshape(-1, 1)
    if not np.all(np.isfinite(logit)):
        raise ImplementationInvalid("NON_FINITE_LOGIT")
    beta = fit_logistic(logit, np.asarray(y, dtype=np.float64))
    return float(beta[1]), float(beta[0])


def _loss_block(y: np.ndarray, p_clim: np.ndarray, p_base: np.ndarray, p_cand: np.ndarray) -> dict:
    brier_c = brier(y, p_clim)
    brier_b = brier(y, p_base)
    brier_k = brier(y, p_cand)
    log_c = log_loss(y, p_clim)
    log_b = log_loss(y, p_base)
    log_k = log_loss(y, p_cand)
    return {
        "n": int(y.shape[0]),
        "brier_climatology": brier_c,
        "brier_baseline": brier_b,
        "brier_candidate": brier_k,
        "logloss_climatology": log_c,
        "logloss_baseline": log_b,
        "logloss_candidate": log_k,
        "delta_brier": brier_k - brier_b,
        "delta_logloss": log_k - log_b,
    }


def _illustrative(mu_rp: np.ndarray, sd_rp: np.ndarray, beta: np.ndarray) -> dict:
    raw = np.array([0.1, 0.5, 0.9], dtype=np.float64)
    scaled = np.zeros((3, N_FEATURES), dtype=np.float64)
    scaled[:, 4] = (raw - float(mu_rp[0])) / float(sd_rp[0])
    prob = predict(scaled, beta)
    return {"p_at_0_1": float(prob[0]), "p_at_0_5": float(prob[1]), "p_at_0_9": float(prob[2])}


def _invalid(reason: str) -> dict:
    return {
        "route": K.ROUTE_INVALID,
        "implementation_ok": False,
        "reason": reason,
        "regularization_added": False,
        "fallback_fit": False,
        "market_series_loaded": False,
        "probabilities_computed_on_market": False,
        "refit_inside_bootstrap": False,
    }


def _evaluate_frame_checked(segments: list[dict], draws: int, seed: int, min_rows: int, min_weeks: int) -> dict:
    if int(draws) < 1:
        raise ImplementationInvalid("BOOTSTRAP_DRAWS_INVALID")
    pooled_y = []
    pooled_clim = []
    pooled_base = []
    pooled_cand = []
    pooled_block = []
    pooled_close = []
    pooled_segment = []
    fold_rows = []
    coefficients = []
    illustrative = []
    per_segment = []
    block_code = 0
    for segment in segments:
        name = str(segment["name"])
        allowed = tuple(segment.get("allowed_train_segments") or TRAIN_SOURCES[name])
        train_close = np.asarray(segment["train_close_ms"], dtype=np.int64)
        train_y = np.asarray(segment["train_y"], dtype=np.float64)
        train_x = np.asarray(segment["train_x"], dtype=np.float64)
        train_segment = np.asarray(segment["train_segment"])
        test_close = np.asarray(segment["test_close_ms"], dtype=np.int64)
        test_y = np.asarray(segment["test_y"], dtype=np.float64)
        test_x = np.asarray(segment["test_x"], dtype=np.float64)
        if train_x.ndim != 2 or train_x.shape[1] != N_FEATURES or test_x.shape[1] != N_FEATURES:
            raise ImplementationInvalid("FEATURE_WIDTH")
        source_ok = np.isin(train_segment, np.asarray(list(allowed)))
        schedule = assign_folds(test_close, train_close[source_ok], min_rows=min_rows, min_weeks=min_weeks)
        _year, _week, test_monday = iso_parts(test_close)
        seg_y = []
        seg_clim = []
        seg_base = []
        seg_cand = []
        last = None
        for fold in schedule["test_folds"]:
            start = int(fold["block_start_ms"])
            x_tr, y_tr, _t_tr, available, seg_tr = build_training_matrix(
                train_close, train_x, train_y, train_segment, start, allowed,
            )
            if int(y_tr.shape[0]) != int(fold["n_train"]):
                raise ImplementationInvalid("TRAIN_COUNT_DIVERGED")
            if y_tr.size and int(available.max()) > start:
                raise ImplementationInvalid("LABEL_AVAILABILITY_VIOLATION")
            test_mask = test_monday == start
            if int(test_mask.sum()) != int(fold["n_test"]):
                raise ImplementationInvalid("TEST_COUNT_DIVERGED")
            x_te = test_x[test_mask]
            y_te = test_y[test_mask]
            t_te = test_close[test_mask]
            if not np.all(np.isfinite(x_te)) or not np.all(np.isfinite(y_te)):
                raise ImplementationInvalid("NON_FINITE_TEST_VALUE")
            if np.any((y_te != 0.0) & (y_te != 1.0)) or np.any((y_tr != 0.0) & (y_tr != 1.0)):
                raise ImplementationInvalid("LABEL_NOT_BINARY")
            mu4, sd4 = fit_scaler(x_tr[:, :4])
            mu_rp, sd_rp = fit_scaler(x_tr[:, 4:5])
            base_tr = apply_scaler(x_tr[:, :4], mu4, sd4)
            cand_tr = np.column_stack([base_tr, apply_scaler(x_tr[:, 4:5], mu_rp, sd_rp).ravel()])
            beta_b = fit_logistic(base_tr, y_tr)
            beta_c = fit_logistic(cand_tr, y_tr)
            base_te = apply_scaler(x_te[:, :4], mu4, sd4)
            cand_te = np.column_stack([base_te, apply_scaler(x_te[:, 4:5], mu_rp, sd_rp).ravel()])
            p_b = predict(base_te, beta_b)
            p_c = predict(cand_te, beta_c)
            rate = float(np.mean(y_tr))
            p_clim = np.full(y_te.shape[0], rate, dtype=np.float64)
            if not np.all(np.isfinite(p_b)) or not np.all(np.isfinite(p_c)) or not np.isfinite(rate):
                raise ImplementationInvalid("NON_FINITE_PROBABILITY")
            block_code += 1
            codes = np.full(y_te.shape[0], block_code, dtype=np.int64)
            pooled_y.append(y_te)
            pooled_clim.append(p_clim)
            pooled_base.append(p_b)
            pooled_cand.append(p_c)
            pooled_block.append(codes)
            pooled_close.append(t_te)
            pooled_segment.append(np.full(y_te.shape[0], name))
            seg_y.append(y_te)
            seg_clim.append(p_clim)
            seg_base.append(p_b)
            seg_cand.append(p_c)
            fold_rows.append({
                "segment": name,
                "iso_year": fold["iso_year"],
                "iso_week": fold["iso_week"],
                "block_start": fold["block_start"],
                "n_train": int(y_tr.shape[0]),
                "n_train_weeks": fold["n_train_weeks"],
                "n_test": int(y_te.shape[0]),
                "max_train_label_available_at": int(available.max()),
                "block_start_ms": start,
                "train_segments": sorted(set(seg_tr.tolist())),
                "climatology_rate": rate,
            })
            coefficients.append({
                "segment": name,
                "iso_year": fold["iso_year"],
                "iso_week": fold["iso_week"],
                "baseline": [float(v) for v in beta_b],
                "candidate": [float(v) for v in beta_c],
            })
            last = (fold, mu_rp, sd_rp, beta_c)
        if seg_y:
            per_segment.append({
                "segment": name,
                **_loss_block(np.concatenate(seg_y), np.concatenate(seg_clim), np.concatenate(seg_base), np.concatenate(seg_cand)),
            })
        if last is not None:
            fold, mu_rp, sd_rp, beta_c = last
            illustrative.append({
                "segment": name,
                "block_start": fold["block_start"],
                **_illustrative(mu_rp, sd_rp, beta_c),
            })
    if not pooled_y:
        raise ImplementationInvalid("NO_TEST_ROWS")
    y = np.concatenate(pooled_y)
    p_clim = np.concatenate(pooled_clim)
    p_base = np.concatenate(pooled_base)
    p_cand = np.concatenate(pooled_cand)
    block_id = np.concatenate(pooled_block)
    close = np.concatenate(pooled_close)
    names = np.concatenate(pooled_segment)
    for row in fold_rows:
        if int(row["max_train_label_available_at"]) > int(row["block_start_ms"]):
            raise ImplementationInvalid("LABEL_AVAILABILITY_VIOLATION")
    pooled = _loss_block(y, p_clim, p_base, p_cand)
    boot = _bootstrap_losses(y, p_clim, p_base, p_cand, block_id, draws, seed)
    slope, intercept = calibration_coefficients(y, p_cand)
    route = assign_route(
        pooled["delta_brier"], pooled["delta_logloss"], boot["brier_hi"], slope,
        int(boot["valid_draws"]), True,
    )
    years = calendar_year(close)
    eras = []
    for year in range(2016, 2027):
        mask = years == year
        if not np.any(mask):
            continue
        block = _loss_block(y[mask], p_clim[mask], p_base[mask], p_cand[mask])
        eras.append({
            "year": int(year),
            "n": block["n"],
            "brier_baseline": block["brier_baseline"],
            "brier_candidate": block["brier_candidate"],
            "delta_brier": block["delta_brier"],
            "logloss_baseline": block["logloss_baseline"],
            "logloss_candidate": block["logloss_candidate"],
            "mean_predicted_up": float(p_cand[mask].mean()),
            "observed_up": float(y[mask].mean()),
        })
    up = y == 1.0
    down = y == 0.0
    separation = None
    if np.any(up) and np.any(down):
        separation = float(p_cand[up].mean() - p_cand[down].mean())
    segment_deltas = [row["delta_brier"] for row in per_segment]
    return {
        "route": route,
        "implementation_ok": True,
        "reason": None,
        "regularization_added": False,
        "fallback_fit": False,
        "market_series_loaded": False,
        "probabilities_computed_on_market": False,
        "refit_inside_bootstrap": False,
        "protocol_draws": int(draws),
        "protocol_seed": int(seed),
        "frozen_draws": int(draws) == K.BOOT_DRAWS,
        "pooled": pooled,
        "bootstrap": boot,
        "calibration_slope": slope,
        "calibration_intercept": intercept,
        "segment_losses": per_segment,
        "unweighted_mean_delta_brier": float(np.mean(segment_deltas)),
        "reliability": reliability_table(y, p_cand),
        "amplitude": amplitude(p_cand - p_base),
        "auroc_candidate": auroc(y, p_cand),
        "auroc_baseline": auroc(y, p_base),
        "predicted_separation": separation,
        "era": eras,
        "folds": [{key: row[key] for key in _FOLD_PUBLIC} | {
            "max_train_label_available_at_ms": row["max_train_label_available_at"],
            "block_start_ms": row["block_start_ms"],
        } for row in fold_rows],
        "coefficients": coefficients,
        "illustrative": illustrative,
        "stored_probabilities": {
            "segment": names.tolist(),
            "close_ms": close.astype(np.int64),
            "y": y,
            "p_climatology": p_clim,
            "p_baseline": p_base,
            "p_candidate": p_cand,
            "block_id": block_id,
        },
    }


def evaluate_frame(segments: list[dict], *, draws: int = K.BOOT_DRAWS, seed: int = K.BOOT_SEED,
                   min_rows: int = K.MIN_TRAIN_ROWS, min_weeks: int = K.MIN_TRAIN_WEEKS) -> dict:
    """Score one in-memory walk-forward. A failure returns `FORECAST_IMPLEMENTATION_INVALID`.

    The defaults are the frozen market protocol. A synthetic call may pass a smaller floor
    or a different seed. It may not change those defaults.
    """
    try:
        return _evaluate_frame_checked(segments, draws, seed, min_rows, min_weeks)
    except ImplementationInvalid as exc:
        return _invalid(str(exc))


def run_market() -> None:
    """Market prices stay unread until a later owner go wires this entry."""
    if not K.OWNER_GO:
        raise SystemExit("AWAITING_OWNER_GO")
    raise SystemExit("FORECAST_IMPLEMENTATION_INVALID")


def main() -> None:
    if not K.OWNER_GO:
        raise SystemExit("AWAITING_OWNER_GO")
    run_market()


if __name__ == "__main__":
    main()
