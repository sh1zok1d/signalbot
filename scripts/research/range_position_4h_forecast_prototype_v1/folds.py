"""ISO-week expanding windows. The function does not read a label rate."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import constants as K


def iso_parts(close_ms: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ISO year, ISO week, and Monday 00:00 UTC in milliseconds, for each close time."""
    close_ms = np.asarray(close_ms, dtype=np.int64)
    ts = pd.to_datetime(close_ms, unit="ms", utc=True)
    iso = ts.isocalendar()
    year = iso["year"].to_numpy(dtype=np.int64)
    week = iso["week"].to_numpy(dtype=np.int64)
    shifted = ts - pd.to_timedelta(ts.dayofweek, unit="D")
    monday = shifted.normalize() if hasattr(shifted, "normalize") else shifted.dt.normalize()
    monday_ms = (pd.Series(monday).astype("int64") // 1_000_000).to_numpy(dtype=np.int64)
    return year, week, monday_ms


def calendar_year(close_ms: np.ndarray) -> np.ndarray:
    ts = pd.to_datetime(np.asarray(close_ms, dtype=np.int64), unit="ms", utc=True)
    return ts.year.to_numpy(dtype=np.int64)


def iso_z(ms: int) -> str:
    return datetime.fromtimestamp(int(ms) / 1000.0, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def assign_folds(close_ms: np.ndarray, train_close_ms: np.ndarray | None = None,
                 min_rows: int = K.MIN_TRAIN_ROWS, min_weeks: int = K.MIN_TRAIN_WEEKS) -> dict:
    """Expanding ISO-week schedule.

    `close_ms` are the candidate test timestamps. Training timestamps default to those
    same rows. A separate training clock is used when earlier Binance rows may train a
    later Binance block. Every test row must satisfy T < block start.
    """
    close_ms = np.asarray(close_ms, dtype=np.int64)
    if train_close_ms is None:
        train_close_ms = close_ms
    else:
        train_close_ms = np.asarray(train_close_ms, dtype=np.int64)
    year, week, monday = iso_parts(close_ms)
    train_year, train_week, train_monday = iso_parts(train_close_ms)
    if close_ms.size and np.any(close_ms < monday):
        raise RuntimeError("a timestamp precedes its own ISO Monday")
    order = np.lexsort((week, year))
    # Unique weeks in Monday order.
    keys = year.astype(np.int64) * 100 + week.astype(np.int64)
    train_keys = train_year.astype(np.int64) * 100 + train_week.astype(np.int64)
    uniq_idx = np.unique(keys, return_index=True)[1]
    uniq_idx = uniq_idx[np.argsort(monday[uniq_idx], kind="mergesort")]
    test_folds = []
    warmup = []
    for idx in uniq_idx:
        start = int(monday[idx])
        train_mask = train_close_ms < start
        n_train = int(train_mask.sum())
        n_train_weeks = int(np.unique(train_keys[train_mask]).size) if n_train else 0
        n_test = int(np.sum(keys == int(keys[idx])))
        row = {
            "iso_year": int(year[idx]),
            "iso_week": int(week[idx]),
            "block_start": iso_z(start),
            "block_start_ms": start,
            "n_train": n_train,
            "n_train_weeks": n_train_weeks,
            "n_test": n_test,
        }
        if n_train >= min_rows and n_train_weeks >= min_weeks:
            if n_test and int(close_ms[keys == int(keys[idx])].max()) >= start + 7 * 24 * 60 * 60 * 1000:
                raise RuntimeError("a test timestamp is outside its ISO week")
            test_folds.append(row)
        else:
            warmup.append({k: row[k] for k in ("iso_year", "iso_week", "block_start", "n_train", "n_train_weeks", "n_test")})
    test_rows = int(sum(row["n_test"] for row in test_folds))
    return {
        "warmup_weeks": warmup,
        "test_folds": test_folds,
        "n_warmup_weeks": len(warmup),
        "n_test_weeks": len(test_folds),
        "n_test_rows": test_rows,
        "n_warmup_rows": int(close_ms.size - test_rows),
        "first_test": None if not test_folds else {
            "iso_year": test_folds[0]["iso_year"],
            "iso_week": test_folds[0]["iso_week"],
            "block_start": test_folds[0]["block_start"],
            "n_train": test_folds[0]["n_train"],
            "n_train_weeks": test_folds[0]["n_train_weeks"],
        },
        "last_test": None if not test_folds else {
            "iso_year": test_folds[-1]["iso_year"],
            "iso_week": test_folds[-1]["iso_week"],
            "block_start": test_folds[-1]["block_start"],
            "n_test": test_folds[-1]["n_test"],
        },
    }
