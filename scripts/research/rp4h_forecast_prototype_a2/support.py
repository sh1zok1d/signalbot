"""Coverage census. Counts rows and weeks. Does not fit a model or score a probability."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.research.dh1.data import load_binance_perp_5m, to_bars
from scripts.research.level_touch_degradation_v1.data import assert_panel_legal
from scripts.research.rp4h_binance_2025_2026_temporal_v1 import constants as modern_constants
from scripts.research.rp4h_binance_2025_2026_temporal_v1 import data as modern_data
from scripts.research.rp4h_binance_2025_2026_temporal_v1 import evaluate as modern_evaluate

from . import constants as K
from . import vendored_bitmex_sample as bitmex_sample
from .runtime_guard import assert_fold_clock
from .vendored_grid import features
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


def _assert_unit_b_surface() -> None:
    """A2: the 2025–2026 source is the canonical RP4H Unit B surface, with the same clock."""
    excluded = tuple((int(a), int(z)) for _name, a, z in modern_constants.EXCLUDED_PERIODS)
    if (
        modern_constants.MANIFEST != K.BINANCE_MANIFEST
        or modern_constants.OBJECT_LIST_SHA256 != K.BINANCE_OBJECT_LIST_SHA256
        or modern_constants.SURFACE_START_MS != K.BINANCE_START_MS
        or modern_constants.SURFACE_END_MS != K.BINANCE_END_MS
        or modern_constants.PHASE_ORIGIN_MS != K.PARENT_EPOCH_MS
        or modern_constants.BAR_MS != K.BAR_MS
        or not excluded
        or excluded[0][0] != K.E1_EXCLUDED_START_MS
        or not modern_constants.CENSUS_PINNED
    ):
        raise SystemExit("UNIT_B_SURFACE_MISMATCH")


def _assert_no_excluded_bars(open_ms: np.ndarray, close: np.ndarray | None = None) -> None:
    """No bar inside [2026-08-02, 2026-08-26) is present; on a grid, those slots stay NaN."""
    open_ms = np.asarray(open_ms, dtype=np.int64)
    inside = (open_ms >= K.E1_EXCLUDED_START_MS) & (open_ms < K.E1_EXCLUDED_END_MS)
    if close is not None:
        inside = inside & np.isfinite(np.asarray(close, dtype=np.float64))
    if np.any(inside):
        raise SystemExit("E1_EXCLUDED_BAR_PRESENT")


def _unit_b_sample_mask(series: dict, grid: dict) -> np.ndarray:
    """Unit B's sample rows (`evaluate.build_sample`) as a mask on the A2 grid."""
    sample = modern_evaluate.build_sample(series)
    opened = np.asarray(sample["close_ms"], dtype=np.int64) - np.int64(K.BAR_MS)
    origin = int(grid["grid_open"][0])
    idx = (opened - origin) // K.BAR_MS
    n = int(np.asarray(grid["grid_open"]).shape[0])
    if idx.size and (int(idx.min()) < 0 or int(idx.max()) >= n or np.any((opened - origin) % K.BAR_MS != 0)):
        raise SystemExit("BINANCE_ELIGIBILITY_DIVERGED")
    mask = np.zeros(n, dtype=bool)
    mask[idx] = True
    if int(mask.sum()) != int(idx.size):
        raise SystemExit("BINANCE_ELIGIBILITY_DIVERGED")
    return mask


def _modern_grid() -> dict:
    """A2 source: Unit B `load_series` -> `census` + `assert_census` -> `place`. No fill.

    The E1 window and the E1-development slice are never requested by the Unit B loader.
    The prototype mask must equal Unit B's sample mask on this grid.
    """
    _assert_unit_b_surface()
    series = modern_data.load_series()
    _assert_no_excluded_bars(series["open_ms"])
    census = modern_data.census(series)
    modern_evaluate.assert_census(census)
    grid = modern_data.place(series)
    if int(grid["grid_open"][0]) != K.BINANCE_START_MS or int(grid["grid_open"][-1]) + K.BAR_MS != K.BINANCE_END_MS:
        raise SystemExit("BINANCE_GRID_CLOCK_MISMATCH")
    _assert_no_excluded_bars(grid["grid_open"], grid["close"])
    official = _unit_b_sample_mask(series, grid)
    proto = replication_eligible(grid["grid_open"], grid["high"], grid["low"], grid["close"], K.BINANCE_END_MS)
    if not np.array_equal(official, proto):
        raise SystemExit("BINANCE_ELIGIBILITY_DIVERGED")
    grid["unit_b_census"] = census
    grid["unit_b_sample_rows"] = int(official.sum())
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


_PARENT_COUNT_KEYS = (
    "n_feature_eligible", "n_exact_zero_excluded", "n_labeled", "first_labeled_t", "last_labeled_t",
    "labeled_by_calendar_year", "primary_test_weeks", "primary_test_rows", "primary_warmup_weeks",
    "primary_warmup_rows", "hourly_labeled", "hourly_test_weeks", "hourly_test_rows",
)
UNCHANGED_SEGMENTS = ("BITMEX_2016_2019", "BINANCE_2020_2024")


def _parent_comparison(support: dict, folds: dict) -> dict:
    """Counts against Cursor's A1 census. BitMEX and CORE must be identical; only 2025–2026 may move."""
    parent_support_path = ROOT / K.PARENT_SUPPORT
    parent_folds_path = ROOT / K.PARENT_FOLDS
    if sha256(parent_support_path) != K.PARENT_SUPPORT_SHA256 or sha256(parent_folds_path) != K.PARENT_FOLDS_SHA256:
        raise SystemExit("PARENT_CENSUS_HASH_MISMATCH")
    parent_support = json.loads(parent_support_path.read_text(encoding="utf-8"))
    parent_folds = json.loads(parent_folds_path.read_text(encoding="utf-8"))
    out = {}
    for name, segment in support["segments"].items():
        before = parent_support["segments"][name]
        counts = {key: {"a1": before[key], "a2": segment[key]} for key in _PARENT_COUNT_KEYS}
        changed = sorted(key for key, pair in counts.items() if pair["a1"] != pair["a2"])
        row = {"counts": counts, "changed_count_keys": changed}
        for cadence in ("primary_15m", "secondary_hourly"):
            old_block = parent_folds["segments"][name][cadence]
            new_block = _jsonable(folds["segments"][name][cadence])
            old_weeks = {(r["iso_year"], r["iso_week"]): r for r in old_block["test_folds"]}
            new_weeks = {(r["iso_year"], r["iso_week"]): r for r in new_block["test_folds"]}
            row[cadence] = {
                "fold_schedule_identical": old_block == new_block,
                "test_weeks_only_in_a1": [f"{y}-W{w:02d}" for (y, w) in sorted(set(old_weeks) - set(new_weeks))],
                "test_weeks_only_in_a2": [f"{y}-W{w:02d}" for (y, w) in sorted(set(new_weeks) - set(old_weeks))],
                "test_weeks_with_changed_n_test": [
                    f"{y}-W{w:02d}" for (y, w) in sorted(set(old_weeks) & set(new_weeks))
                    if old_weeks[(y, w)]["n_test"] != new_weeks[(y, w)]["n_test"]
                ],
                "test_weeks_with_changed_n_train": int(sum(
                    1 for key in set(old_weeks) & set(new_weeks)
                    if old_weeks[key]["n_train"] != new_weeks[key]["n_train"]
                )),
            }
        out[name] = row
    for name in UNCHANGED_SEGMENTS:
        row = out[name]
        if row["changed_count_keys"] or not all(row[c]["fold_schedule_identical"] for c in ("primary_15m", "secondary_hourly")):
            raise SystemExit("PARENT_SEGMENT_DIVERGED " + name)
    return out


def _runtime() -> dict:
    import platform

    import pandas

    return {"python": platform.python_version(), "numpy": np.__version__, "pandas": pandas.__version__}


def build_census() -> tuple[dict, dict]:
    assert_fold_clock()
    bitmex = _labeled(_bitmex_grid(), K.BITMEX_END_MS)
    core = _labeled(_core_grid(), K.CORE_END_MS)
    modern_grid = _modern_grid()
    modern = _labeled(modern_grid, K.BINANCE_END_MS)
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
        "parent_unit": K.PARENT_UNIT,
        "amendment": "A2",
        "amendment_a2_scope": "BINANCE_2025_2026 data source only",
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
        "binance_2025_2026_manifest": K.BINANCE_MANIFEST,
        "binance_2025_2026_object_list_sha256": K.BINANCE_OBJECT_LIST_SHA256,
        "binance_2025_2026_source": "scripts.research.rp4h_binance_2025_2026_temporal_v1 (Unit B canonical surface)",
        "binance_2025_2026_unit_b_census": {
            key: modern_grid["unit_b_census"][key]
            for key in ("rows", "holes", "holes_sha256", "holes_in_e1_window",
                        "holes_in_e1_development_slice", "holes_e1_refused_day_tail", "holes_other")
        },
        "binance_2025_2026_unit_b_sample_rows": modern_grid["unit_b_sample_rows"],
        "binance_2025_2026_mask_equals_unit_b_sample": True,
        "binance_2025_2026_excluded_open_interval": [iso_z(K.E1_EXCLUDED_START_MS), iso_z(K.E1_EXCLUDED_END_MS)],
        "e1_development_slice_requested": False,
        "parent_binance_2025_2026_file_read": False,
        "census_runtime": _runtime(),
        "fold_clock_runtime_check": "PASSED",
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
        "parent_unit": K.PARENT_UNIT,
        "amendment": "A2",
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
    support["parent_a1_comparison"] = _parent_comparison(support, folds)
    _guard(support)
    _guard(folds)
    return support, folds


def _markdown(support: dict) -> str:
    lines = [
        "# RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_A2 — support census",
        "",
        "Amendment A2: only the 2025–2026 source changes (RP4H Unit B canonical surface; "
        "`[2026-08-02, 2026-08-26)` never requested).",
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
    comparison = support.get("parent_a1_comparison")
    if comparison:
        lines.append("Against Cursor's A1 census, whose 2025–2026 file includes `[2026-08-02, 2026-08-16)`. Counts only.")
        lines.append("")
        lines.append("| segment | labeled A1 -> A2 | 15m test rows A1 -> A2 | 15m test weeks A1 -> A2 | 15m schedule identical | hourly schedule identical |")
        lines.append("|---|---:|---:|---:|---|---|")
        for name, row in comparison.items():
            counts = row["counts"]
            lines.append(
                f"| {name} | {counts['n_labeled']['a1']} -> {counts['n_labeled']['a2']} | "
                f"{counts['primary_test_rows']['a1']} -> {counts['primary_test_rows']['a2']} | "
                f"{counts['primary_test_weeks']['a1']} -> {counts['primary_test_weeks']['a2']} | "
                f"{'yes' if row['primary_15m']['fold_schedule_identical'] else 'no'} | "
                f"{'yes' if row['secondary_hourly']['fold_schedule_identical'] else 'no'} |"
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
