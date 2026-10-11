"""Walk-forward comparison. Stored probabilities are not refit inside the bootstrap."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import constants as K
from .frame import label_available_at
from .model import (
    ImplementationInvalid,
    apply_scaler,
    auroc,
    brier,
    calibration_coefficients,
    fit_logistic,
    fit_scaler,
    log_loss,
    predict,
)
from .states import evaluate_cells


def calendar_fields(close_ms: np.ndarray) -> dict:
    ts = pd.to_datetime(np.asarray(close_ms, dtype=np.int64), unit="ms", utc=True)
    iso = ts.isocalendar()
    monday = (ts - pd.to_timedelta(ts.dayofweek, unit="D")).normalize()
    return {
        "year": ts.year.to_numpy(dtype=np.int64),
        "iso_year": iso["year"].to_numpy(dtype=np.int64),
        "iso_week": iso["week"].to_numpy(dtype=np.int64),
        "monday_ms": (monday.asi8 // 1_000_000).astype(np.int64),
    }


def loss_block(y: np.ndarray, p_b0: np.ndarray, p_b1: np.ndarray, p_c: np.ndarray, p_geom: np.ndarray) -> dict:
    return {
        "n": int(y.shape[0]),
        "brier_b0": brier(y, p_b0),
        "brier_geom": brier(y, p_geom),
        "brier_b1": brier(y, p_b1),
        "brier_candidate": brier(y, p_c),
        "logloss_b0": log_loss(y, p_b0),
        "logloss_geom": log_loss(y, p_geom),
        "logloss_b1": log_loss(y, p_b1),
        "logloss_candidate": log_loss(y, p_c),
        "delta_brier": brier(y, p_c) - brier(y, p_b1),
        "delta_logloss": log_loss(y, p_c) - log_loss(y, p_b1),
        "auroc_b1": auroc(y, p_b1),
        "auroc_candidate": auroc(y, p_c),
    }


def bootstrap_model_deltas(y, p_b1, p_c, week, draws: int, seed: int) -> dict:
    codes, inverse = np.unique(week, return_inverse=True)
    counts = np.bincount(inverse).astype(np.float64)
    brier_b1 = np.bincount(inverse, weights=(p_b1 - y) ** 2)
    brier_c = np.bincount(inverse, weights=(p_c - y) ** 2)
    clip_b1 = np.clip(p_b1, K.LOGLOSS_CLIP, 1.0 - K.LOGLOSS_CLIP)
    clip_c = np.clip(p_c, K.LOGLOSS_CLIP, 1.0 - K.LOGLOSS_CLIP)
    log_b1 = np.bincount(inverse, weights=-(y * np.log(clip_b1) + (1.0 - y) * np.log(1.0 - clip_b1)))
    log_c = np.bincount(inverse, weights=-(y * np.log(clip_c) + (1.0 - y) * np.log(1.0 - clip_c)))
    rng = np.random.default_rng(int(seed))
    brier_delta = np.empty(int(draws), dtype=np.float64)
    log_delta = np.empty(int(draws), dtype=np.float64)
    valid = 0
    for _ in range(int(draws)):
        picked = rng.integers(0, codes.size, size=codes.size)
        mult = np.bincount(picked, minlength=codes.size).astype(np.float64)
        denom = float(mult @ counts)
        if denom <= 0.0:
            continue
        db = float(mult @ brier_c) / denom - float(mult @ brier_b1) / denom
        dl = float(mult @ log_c) / denom - float(mult @ log_b1) / denom
        if np.isfinite(db) and np.isfinite(dl):
            brier_delta[valid] = db
            log_delta[valid] = dl
            valid += 1
    if valid == 0:
        return {"valid_draws": 0, "brier_lo": None, "brier_hi": None, "logloss_lo": None, "logloss_hi": None}
    return {
        "valid_draws": int(valid),
        "brier_lo": float(np.quantile(brier_delta[:valid], K.BOOT_LO)),
        "brier_hi": float(np.quantile(brier_delta[:valid], K.BOOT_HI)),
        "logloss_lo": float(np.quantile(log_delta[:valid], K.BOOT_LO)),
        "logloss_hi": float(np.quantile(log_delta[:valid], K.BOOT_HI)),
    }


def reliability(y: np.ndarray, prob: np.ndarray) -> list[dict]:
    bins = np.digitize(prob, np.asarray(K.RELIABILITY_EDGES, dtype=np.float64), right=False)
    edges = (float("-inf"),) + tuple(K.RELIABILITY_EDGES) + (float("inf"),)
    rows = []
    for code in range(len(edges) - 1):
        mask = bins == code
        n = int(mask.sum())
        rows.append({
            "bin_left": None if edges[code] == float("-inf") else edges[code],
            "bin_right": None if edges[code + 1] == float("inf") else edges[code + 1],
            "n": n,
            "mean_predicted": None if n == 0 else float(np.mean(prob[mask])),
            "observed": None if n == 0 else float(np.mean(y[mask])),
        })
    return rows


def _catalog(frame: dict, scored: np.ndarray, alert: np.ndarray) -> dict:
    close_ms = frame["close_ms"]
    touch_ms = frame["touch_ms"]
    y = frame["y"]
    ratio = frame["map_values"]["rv_ratio_4h_24h"]
    regime = np.digitize(ratio, np.asarray(K.RATIO_EDGES, dtype=np.float64), right=False)
    regime_name = np.asarray(["lt_0.7", "0.7_to_1", "1_to_1.4", "ge_1.4"], dtype=object)
    episodes = []
    nested = 0
    next_free = -1
    for j in np.flatnonzero(y == 1.0):
        if int(close_ms[j]) < next_free:
            nested += 1
            continue
        touch = int(touch_ms[j])
        if touch < 0:
            continue
        next_free = touch
        warned = bool(scored[j] and alert[j])
        episodes.append({
            "t_ms": int(close_ms[j]),
            "touch_ms": touch,
            "duration_min": (touch - int(close_ms[j])) / 60_000.0,
            "direction": int(frame["direction"][j]),
            "barrier_z": float(K.PRIMARY_K if frame["direction"][j] > 0 else -K.PRIMARY_K),
            "wick_z": None if not np.isfinite(frame["wick_z"][j]) else float(frame["wick_z"][j]),
            "regime": str(regime_name[int(regime[j])]),
            "warned": warned,
            "scored": bool(scored[j]),
        })
    durations = np.array([row["duration_min"] for row in episodes if row["warned"]], dtype=np.float64)
    raw = int(np.sum(y == 1.0))
    return {
        "raw_impulse_rows": raw,
        "episodes": int(len(episodes)),
        "nested_rows": int(nested),
        "nested_share_of_raw": None if raw == 0 else float(nested / raw),
        "up_episodes": int(sum(row["direction"] > 0 for row in episodes)),
        "down_episodes": int(sum(row["direction"] < 0 for row in episodes)),
        "warned_episodes": int(sum(row["warned"] for row in episodes)),
        "median_warned_lead_min": None if durations.size == 0 else float(np.median(durations)),
        "p90_warned_lead_min": None if durations.size == 0 else float(np.quantile(durations, 0.90)),
        "mean_duration_min": None if not episodes else float(np.mean([row["duration_min"] for row in episodes])),
        "episodes_head": episodes[:20],
        "episode_rows": episodes,
    }


def practical_metrics(y, p_b1, p_c, close_ms, alert) -> dict:
    y = np.asarray(y, dtype=np.float64)
    dates = np.asarray(close_ms, dtype=np.int64) // 86_400_000
    n_days = int(np.unique(dates).size)
    n_alert = int(np.sum(alert))
    hits = int(np.sum(alert & (y == 1.0)))
    false = int(np.sum(alert & (y == 0.0)))
    positives = int(np.sum(y == 1.0))
    return {
        "alert_margin": K.ALERT_MARGIN,
        "alerts": n_alert,
        "alerts_per_day": None if n_days == 0 else n_alert / n_days,
        "precision": None if n_alert == 0 else hits / n_alert,
        "recall": None if positives == 0 else hits / positives,
        "missed_share": None if positives == 0 else 1.0 - hits / positives,
        "false_alarms_per_day": None if n_days == 0 else false / n_days,
        "mean_probability_lift": float(np.mean(p_c - p_b1)),
        "mean_alert_lift": None if n_alert == 0 else float(np.mean((p_c - p_b1)[alert])),
        "scored_days": n_days,
    }


def walk_forward(frame: dict, min_rows: int = K.MIN_TRAIN_ROWS, min_weeks: int = K.MIN_TRAIN_WEEKS) -> dict:
    y = np.asarray(frame["y"], dtype=np.float64)
    x = np.asarray(frame["features"], dtype=np.float64)
    close_ms = np.asarray(frame["close_ms"], dtype=np.int64)
    cal = calendar_fields(close_ms)
    available = label_available_at(close_ms)
    week = cal["iso_year"] * 100 + cal["iso_week"]
    p_b0 = np.full(y.shape[0], np.nan)
    p_b1 = np.full(y.shape[0], np.nan)
    p_c = np.full(y.shape[0], np.nan)
    b1_index = K.CANDIDATE_FEATURES.index("log_rv_24h")
    folds = []
    for monday in np.unique(cal["monday_ms"]):
        test = cal["monday_ms"] == monday
        train = available <= int(monday)
        n_train = int(train.sum())
        n_weeks = int(np.unique(week[train]).size) if n_train else 0
        if n_train < int(min_rows) or n_weeks < int(min_weeks):
            continue
        if int(available[train].max()) > int(monday):
            raise ImplementationInvalid("LABEL_AVAILABILITY_VIOLATION")
        if np.any(train & test):
            raise ImplementationInvalid("TRAIN_TEST_OVERLAP")
        try:
            mu_b1, sd_b1 = fit_scaler(x[train][:, [b1_index]])
            beta_b1 = fit_logistic(apply_scaler(x[train][:, [b1_index]], mu_b1, sd_b1), y[train])
            mu_c, sd_c = fit_scaler(x[train])
            beta_c = fit_logistic(apply_scaler(x[train], mu_c, sd_c), y[train])
        except ImplementationInvalid:
            raise
        rate = float(np.mean(y[train]))
        p_b0[test] = rate
        p_b1[test] = predict(apply_scaler(x[test][:, [b1_index]], mu_b1, sd_b1), beta_b1)
        p_c[test] = predict(apply_scaler(x[test], mu_c, sd_c), beta_c)
        folds.append({
            "block_start_ms": int(monday),
            "n_train": n_train,
            "n_train_weeks": n_weeks,
            "n_test": int(test.sum()),
            "train_rate": rate,
        })
    scored = np.isfinite(p_c) & np.isfinite(p_b1) & np.isfinite(p_b0)
    if int(scored.sum()) == 0 or not folds:
        raise ImplementationInvalid("NO_TEST_ROWS")
    return {
        "p_b0": p_b0,
        "p_b1": p_b1,
        "p_candidate": p_c,
        "scored": scored,
        "week": week,
        "year": cal["year"],
        "folds": folds,
        "monday_ms": cal["monday_ms"],
    }


def precursor_means(frame: dict, scored: np.ndarray) -> list[dict]:
    y = frame["y"]
    rows = []
    for name, values in frame["map_values"].items():
        pos = scored & (y == 1.0)
        neg = scored & (y == 0.0)
        rows.append({
            "feature": name,
            "mean_impulse": None if not np.any(pos) else float(np.mean(values[pos])),
            "mean_quiet": None if not np.any(neg) else float(np.mean(values[neg])),
            "n_impulse": int(np.sum(pos)),
            "n_quiet": int(np.sum(neg)),
        })
    return rows


def summarize(frame: dict, fitted: dict) -> dict:
    scored = fitted["scored"]
    y = frame["y"][scored]
    p_b0 = fitted["p_b0"][scored]
    p_b1 = fitted["p_b1"][scored]
    p_c = fitted["p_candidate"][scored]
    p_geom = frame["p_geom"][scored]
    year = fitted["year"][scored]
    week = fitted["week"][scored]
    pooled = loss_block(y, p_b0, p_b1, p_c, p_geom)
    boot = bootstrap_model_deltas(y, p_b1, p_c, week, K.BOOT_DRAWS, K.BOOT_SEED)
    slope, intercept = calibration_coefficients(y, p_c)
    by_year = []
    for one in sorted(set(int(v) for v in year)):
        mask = year == one
        block = loss_block(y[mask], p_b0[mask], p_b1[mask], p_c[mask], p_geom[mask])
        block["year"] = int(one)
        by_year.append(block)
    dev = np.isin(year, K.DEV_YEARS)
    diag = np.isin(year, K.DIAG_YEARS)
    dev_loss = loss_block(y[dev], p_b0[dev], p_b1[dev], p_c[dev], p_geom[dev]) if np.any(dev) else None
    diag_loss = loss_block(y[diag], p_b0[diag], p_b1[diag], p_c[diag], p_geom[diag]) if np.any(diag) else None
    alert = p_c >= (p_b1 + K.ALERT_MARGIN)
    full_alert = np.zeros(frame["y"].shape[0], dtype=bool)
    full_alert[np.flatnonzero(scored)] = alert
    cells = evaluate_cells(frame, scored, fitted["p_b1"], fitted["week"], fitted["year"])
    catalog = _catalog(frame, scored, full_alert)
    return {
        "pooled": pooled,
        "bootstrap": boot,
        "calibration_slope": slope,
        "calibration_intercept": intercept,
        "by_year": by_year,
        "development_block": dev_loss,
        "diagnostic_block": diag_loss,
        "practical": practical_metrics(y, p_b1, p_c, frame["close_ms"][scored], alert),
        "reliability": reliability(y, p_c),
        "cells": [{key: value for key, value in row.items()} for row in cells],
        "precursors": precursor_means(frame, scored),
        "catalog_summary": {key: value for key, value in catalog.items() if key != "episode_rows"},
        "catalog_episodes": catalog["episode_rows"],
        "folds": fitted["folds"],
        "scored_n": int(scored.sum()),
        "predictions": {
            "close_ms": frame["close_ms"][scored],
            "y": y,
            "p_b0": p_b0,
            "p_b1": p_b1,
            "p_candidate": p_c,
            "p_geom": p_geom,
            "week": week,
            "year": year,
        },
    }
