"""Coverage census. Counts rows and weeks. Does not fit a model or score a probability."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.research.dh1.data import load_binance_perp_5m, to_bars
from scripts.research.level_touch_degradation_v1.data import assert_panel_legal
from scripts.research.range_position_4h_binance_2025_2026_temporal_replication_v1 import sample as modern_sample
from scripts.research.range_position_4h_bitmex_temporal_replication_v1 import sample as bitmex_sample
from scripts.research.range_position_4h_incremental_replication_v1.grid import features

from . import constants as K
from .eligibility import local_returns, replication_eligible
from .folds import assign_folds, calendar_year, iso_z

ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN_KEYS = {
    "p_up", "mean_return", "brier", "logloss", "log_loss", "auroc", "coefficient",
    "probability", "delta_brier", "delta_logloss",
}
PRE_A1_SUPPORT_SHA256 = "8400e2f20abb79ea074ce2ea93614c1675987c7ef55282060b43c9c0e576abc4"
PRE_A1_FOLDS_SHA256 = "ec7a94e1f5c24928c756eda5ead050beb4c67da5f233784bb3fe1b98550e1bb5"
_PUBLIC_FOLD_KEYS = (
    "iso_year", "iso_week", "block_start", "n_train", "n_train_weeks", "n_test",
    "n_excluded_by_label_lag", "max_train_label_available_at",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value)
    return value


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _guard(payload: dict) -> None:
    keys = set()

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                keys.add(str(key).lower())
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    hit = [key for key in keys if key in FORBIDDEN_KEYS]
    if hit:
        raise SystemExit("CENSUS_CONTAINS_A_MODEL_METRIC " + ",".join(sorted(hit)))


def _labeled(grid: dict, surface_end_ms: int) -> dict[str, np.ndarray]:
    eligible = replication_eligible(grid["grid_open"], grid["high"], grid["low"], grid["close"], surface_end_ms)
    feat = features(grid["high"], grid["low"], grid["close"])
    ret_1h, ret_15m = local_returns(grid["close"])
    finite = (
        np.isfinite(feat["rp"]) & np.isfinite(feat["ret4"]) & np.isfinite(feat["rv4"])
        & np.isfinite(feat["r1"]) & np.isfinite(ret_1h) & np.isfinite(ret_15m)
    )
    if np.any(eligible & ~finite):
        raise SystemExit("ELIGIBLE_ROW_MISSING_A_FEATURE")
    feature_ok = eligible & finite
    zero = feature_ok & (feat["r1"] == 0.0)
    labeled = feature_ok & ~zero
    close_ms = grid["grid_open"] + K.BAR_MS
    return {
        "eligible": feature_ok,
        "labeled": labeled,
        "close_ms": close_ms,
        "n_feature": int(feature_ok.sum()),
        "n_zero": int(zero.sum()),
        "n_labeled": int(labeled.sum()),
    }


def _bitmex_grid() -> dict:
    path = ROOT / K.BITMEX_SERIES
    if sha256(path) != K.BITMEX_SHA256:
        raise SystemExit("BITMEX_HASH_MISMATCH")
    rows = bitmex_sample.load_rows(path)
    grid = bitmex_sample.build_grid(*bitmex_sample.rows_to_arrays(rows))
    official = bitmex_sample.classify(grid)["eligible"]
    proto = replication_eligible(grid["grid_open"], grid["high"], grid["low"], grid["close"], K.BITMEX_END_MS)
    if not np.array_equal(official, proto):
        raise SystemExit("BITMEX_ELIGIBILITY_DIVERGED")
    return grid


def _core_grid() -> dict:
    panel = load_binance_perp_5m()
    assert_panel_legal(panel["open_ms"])
    bars = to_bars(panel, K.CORE_START_MS, K.CORE_END_MS)
    assert_panel_legal(bars.times)
    if int(bars.end_ms) != K.CORE_END_MS:
        raise SystemExit("CORE_GRID_END_MISMATCH")
    return {
        "grid_open": bars.times,
        "high": np.asarray(bars.high, dtype=np.float64),
        "low": np.asarray(bars.low, dtype=np.float64),
        "close": np.asarray(bars.close, dtype=np.float64),
        "occupied": int(np.isfinite(bars.close).sum()),
        "slots": int(bars.n),
    }


def _modern_grid() -> dict:
    path = ROOT / K.BINANCE_SERIES
    if sha256(path) != K.BINANCE_SHA256:
        raise SystemExit("BINANCE_HASH_MISMATCH")
    rows = modern_sample.load_rows(path)
    grid = modern_sample.build_grid(*modern_sample.rows_to_arrays(rows))
    official = modern_sample.classify(grid)["eligible"]
    proto = replication_eligible(grid["grid_open"], grid["high"], grid["low"], grid["close"], K.BINANCE_END_MS)
    if not np.array_equal(official, proto):
        raise SystemExit("BINANCE_ELIGIBILITY_DIVERGED")
    return grid


def _year_counts(close_ms: np.ndarray) -> dict[str, int]:
    years = calendar_year(close_ms)
    return {str(int(year)): int(np.sum(years == year)) for year in range(2016, 2027) if np.any(years == year)}


def _segment(name: str, close_ms: np.ndarray, train_close_ms: np.ndarray | None, counts: dict) -> dict:
    primary = assign_folds(close_ms, train_close_ms)
    hourly = close_ms[close_ms % K.HOUR_MS == 0]
    train_hourly = None if train_close_ms is None else train_close_ms[train_close_ms % K.HOUR_MS == 0]
    secondary = assign_folds(hourly, train_hourly)
    return {
        "segment": name,
        "n_feature_eligible": counts["n_feature"],
        "n_exact_zero_excluded": counts["n_zero"],
        "n_labeled": counts["n_labeled"],
        "first_labeled_t": iso_z(int(close_ms.min())) if close_ms.size else None,
        "last_labeled_t": iso_z(int(close_ms.max())) if close_ms.size else None,
        "labeled_by_calendar_year": _year_counts(close_ms),
        "primary_15m": primary,
        "secondary_hourly": secondary,
    }


def _public_row(row: dict) -> dict:
    return {key: row[key] for key in _PUBLIC_FOLD_KEYS}


def _public_folds(block: dict) -> dict:
    """Drop the internal millisecond field from the committed schedule."""
    folds = [_public_row(row) for row in block["test_folds"]]
    warmup = [_public_row(row) for row in block["warmup_weeks"]]
    return {
        "warmup_weeks": warmup,
        "test_folds": folds,
        "n_warmup_weeks": block["n_warmup_weeks"],
        "n_test_weeks": block["n_test_weeks"],
        "n_test_rows": block["n_test_rows"],
        "n_warmup_rows": block["n_warmup_rows"],
        "first_test": block["first_test"],
        "last_test": block["last_test"],
    }


def _label_proof(folds: dict) -> dict:
    checked = 0
    max_excluded = 0
    for segment in folds["segments"].values():
        for cadence in ("primary_15m", "secondary_hourly"):
            block = segment[cadence]
            for row in block["test_folds"] + block["warmup_weeks"]:
                if not row["n_train"]:
                    continue
                checked += 1
                if row["max_train_label_available_at"] > row["block_start"]:
                    raise SystemExit("LABEL_AVAILABILITY_VIOLATION")
                max_excluded = max(max_excluded, int(row["n_excluded_by_label_lag"]))
    return {
        "rule": "T + HORIZON * BAR_MS <= block_start",
        "horizon": K.HORIZON,
        "bar_ms": K.BAR_MS,
        "label_lag_ms": int(K.HORIZON) * int(K.BAR_MS),
        "blocks_checked": checked,
        "violations": 0,
        "max_train_label_available_at_le_block_start": True,
        "max_n_excluded_by_label_lag": max_excluded,
    }


def _compare_block(old_block: dict, new_block: dict) -> dict:
    old_rows = old_block["test_folds"]
    new_rows = new_block["test_folds"]
    old_keys = [(row["iso_year"], row["iso_week"]) for row in old_rows]
    new_keys = [(row["iso_year"], row["iso_week"]) for row in new_rows]
    aligned = old_keys == new_keys
    deltas = []
    weeks_same = True
    tests_same = True
    lag_matches = True
    if aligned:
        for old, new in zip(old_rows, new_rows):
            delta = int(old["n_train"]) - int(new["n_train"])
            deltas.append(delta)
            weeks_same = weeks_same and int(old["n_train_weeks"]) == int(new["n_train_weeks"])
            tests_same = tests_same and int(old["n_test"]) == int(new["n_test"])
            lag_matches = lag_matches and delta == int(new["n_excluded_by_label_lag"])
    return {
        "aligned": aligned,
        "n_test_weeks_before": len(old_rows),
        "n_test_weeks_after": len(new_rows),
        "n_test_rows_before": int(old_block["n_test_rows"]),
        "n_test_rows_after": int(new_block["n_test_rows"]),
        "train_weeks_unchanged": weeks_same,
        "test_rows_unchanged": tests_same,
        "train_row_delta_equals_label_lag_exclusion": lag_matches,
        "min_train_row_delta": None if not deltas else int(min(deltas)),
        "max_train_row_delta": None if not deltas else int(max(deltas)),
        "first_n_train_before": None if not old_rows else int(old_rows[0]["n_train"]),
        "first_n_train_after": None if not new_rows else int(new_rows[0]["n_train"]),
        "first_n_train_weeks_before": None if not old_rows else int(old_rows[0]["n_train_weeks"]),
        "first_n_train_weeks_after": None if not new_rows else int(new_rows[0]["n_train_weeks"]),
    }


def _compare_schedules(old_folds: dict, new_folds: dict) -> dict:
    compared = {}
    for name, new_segment in new_folds["segments"].items():
        old_segment = old_folds["segments"][name]
        compared[name] = {
            "primary_15m": _compare_block(old_segment["primary_15m"], new_segment["primary_15m"]),
            "secondary_hourly": _compare_block(old_segment["secondary_hourly"], new_segment["secondary_hourly"]),
        }
    return compared


def build_census() -> tuple[dict, dict]:
    bitmex = _labeled(_bitmex_grid(), K.BITMEX_END_MS)
    core = _labeled(_core_grid(), K.CORE_END_MS)
    modern = _labeled(_modern_grid(), K.BINANCE_END_MS)
    bitmex_t = bitmex["close_ms"][bitmex["labeled"]]
    core_t = core["close_ms"][core["labeled"]]
    modern_t = modern["close_ms"][modern["labeled"]]
    segments = {
        "BITMEX_2016_2019": _segment("BITMEX_2016_2019", bitmex_t, None, bitmex),
        "BINANCE_2020_2024": _segment("BINANCE_2020_2024", core_t, None, core),
        "BINANCE_2025_2026": _segment(
            "BINANCE_2025_2026", modern_t, np.concatenate([core_t, modern_t]), modern),
    }
    support = {
        "unit": K.UNIT,
        "model_metrics_computed": False,
        "probabilities_computed": False,
        "coefficients_computed": False,
        "p_up_computed": False,
        "brier_computed": False,
        "logloss_computed": False,
        "zero_return_rule": "ZERO_RETURN_EXCLUDED",
        "e1_objects_requested": False,
        "grids_stitched": False,
        "venue_dummy": False,
        "bybit_included": False,
        "core_snapshot": K.CORE_SNAPSHOT,
        "bitmex_sha256": K.BITMEX_SHA256,
        "binance_2025_2026_sha256": K.BINANCE_SHA256,
        "segments": {
            name: {
                "n_feature_eligible": row["n_feature_eligible"],
                "n_exact_zero_excluded": row["n_exact_zero_excluded"],
                "n_labeled": row["n_labeled"],
                "first_labeled_t": row["first_labeled_t"],
                "last_labeled_t": row["last_labeled_t"],
                "labeled_by_calendar_year": row["labeled_by_calendar_year"],
                "primary_test_weeks": row["primary_15m"]["n_test_weeks"],
                "primary_test_rows": row["primary_15m"]["n_test_rows"],
                "primary_warmup_weeks": row["primary_15m"]["n_warmup_weeks"],
                "primary_warmup_rows": row["primary_15m"]["n_warmup_rows"],
                "first_test": row["primary_15m"]["first_test"],
                "last_test": row["primary_15m"]["last_test"],
                "hourly_labeled": int(
                    row["secondary_hourly"]["n_test_rows"] + row["secondary_hourly"]["n_warmup_rows"]),
                "hourly_test_weeks": row["secondary_hourly"]["n_test_weeks"],
                "hourly_test_rows": row["secondary_hourly"]["n_test_rows"],
                "hourly_first_test": row["secondary_hourly"]["first_test"],
            }
            for name, row in segments.items()
        },
    }
    folds = {
        "unit": K.UNIT,
        "model_metrics_computed": False,
        "label_availability_rule": "T + HORIZON * BAR_MS <= block_start",
        "horizon": K.HORIZON,
        "bar_ms": K.BAR_MS,
        "cadence_primary": "15m",
        "cadence_secondary": "hourly_close",
        "min_train_rows": K.MIN_TRAIN_ROWS,
        "min_train_weeks": K.MIN_TRAIN_WEEKS,
        "segments": {
            name: {
                "primary_15m": _public_folds(row["primary_15m"]),
                "secondary_hourly": _public_folds(row["secondary_hourly"]),
            }
            for name, row in segments.items()
        },
    }
    proof = _label_proof(folds)
    support["label_availability"] = proof
    folds["label_availability"] = proof
    _guard(support)
    _guard(folds)
    return support, folds


def _markdown(support: dict) -> str:
    lines = [
        "# RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1 — support census",
        "",
        "Row and week counts only. No probability was fit. No Brier score, log loss, AUROC, or coefficient was computed.",
        "",
        "Training admission after amendment A1: `T + 12 * 300000 <= block_start`.",
        "",
        f"Zero-return rule: `{support['zero_return_rule']}`.",
        "",
        "| segment | feature rows | exact zeros dropped | labeled | 15m test rows | 15m test weeks | hourly test rows |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in support["segments"].items():
        lines.append(
            f"| {name} | {row['n_feature_eligible']} | {row['n_exact_zero_excluded']} | {row['n_labeled']} | "
            f"{row['primary_test_rows']} | {row['primary_test_weeks']} | {row['hourly_test_rows']} |"
        )
    lines.append("")
    effect = support.get("label_lag_effect")
    if effect:
        lines.append("Train-row change versus the pre-A1 rule `T < block_start`. Week identity is the ISO week of each test block.")
        lines.append("")
        lines.append("| segment | cadence | test weeks | test rows changed | first n_train before | first n_train after | max train-row delta |")
        lines.append("|---|---|---:|---|---:|---:|---:|")
        for name, cadences in effect.items():
            for cadence, row in cadences.items():
                rows_changed = "no" if row["test_rows_unchanged"] else "yes"
                lines.append(
                    f"| {name} | {cadence} | {row['n_test_weeks_before']} -> {row['n_test_weeks_after']} | {rows_changed} | "
                    f"{row['first_n_train_before']} | {row['first_n_train_after']} | {row['max_train_row_delta']} |"
                )
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    import sys

    support_path = ROOT / K.SUPPORT
    folds_path = ROOT / K.FOLDS
    rewrite = "--rewrite-a1" in sys.argv
    if (support_path.exists() or folds_path.exists()) and not rewrite:
        raise SystemExit("CENSUS_EXISTS")
    old_folds = None
    if rewrite:
        if sha256(support_path) != PRE_A1_SUPPORT_SHA256 or sha256(folds_path) != PRE_A1_FOLDS_SHA256:
            raise SystemExit("CENSUS_REWRITE_REFUSED")
        old_folds = json.loads(folds_path.read_text(encoding="utf-8"))
    support, folds = build_census()
    if old_folds is not None:
        support["label_lag_effect"] = _compare_schedules(old_folds, folds)
        folds["label_lag_effect"] = support["label_lag_effect"]
        _guard(support)
        _guard(folds)
    _write(support_path, support)
    _write(folds_path, folds)
    (ROOT / K.SUPPORT_MD).write_text(_markdown(support), encoding="utf-8")
    total_test = sum(row["primary_test_rows"] for row in support["segments"].values())
    print(f"labeled census written; primary test rows {total_test}; model metrics false")
    proof = support["label_availability"]
    print(
        f"label proof blocks {proof['blocks_checked']}; "
        f"max excluded {proof['max_n_excluded_by_label_lag']}; violations {proof['violations']}"
    )
    if "label_lag_effect" in support:
        print(json.dumps(support["label_lag_effect"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
