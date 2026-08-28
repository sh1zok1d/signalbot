"""B2-01 volatility-transition implementation helpers.

Outcome-blind implementation of the frozen preregistration in
`docs/research/B2_01_VOLATILITY_TRANSITION_PREREG.{md,json}`.

This module is wired for a later authorized development run, but the
implementation-freeze PR must exercise it only on synthetic fixtures. It must
not open real accepted parquet outcomes as part of implementation review.
"""
from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_left, bisect_right, insort_right
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Hashable, Mapping, Sequence

import numpy as np

from scripts.research.lib.research_harness import (
    AuthorizedDataset,
    PromotionGateContract,
    assert_no_lookahead,
    fail_closed_gate_conjunction,
    paired_same_support_delta,
)

UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[2]
PREREG_JSON = REPO_ROOT / "docs" / "research" / "B2_01_VOLATILITY_TRANSITION_PREREG.json"

HYPOTHESIS_ID = "B2-01_VOLATILITY_TRANSITION"
DATASET_ID = "CORE_BTC_BINANCE_V0"
REQUIRED_SNAPSHOT = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"

BAR_MS = 60_000
GRID_MIN = 15
GRID_MS = GRID_MIN * BAR_MS
DAY_MS = 24 * 60 * BAR_MS
REF_DAYS = 30
REF_STEPS = REF_DAYS * 24 * 60 // GRID_MIN

W_WINDOWS = (60, 120)
D_LAGS = (60, 120)
HORIZONS = (30, 60, 120, 240)
YEAR_BLOCKS = (2020, 2021, 2022, 2023, 2024)
ADJACENT_H_PAIRS = ((30, 60), (60, 120), (120, 240))

BASELINE_MIN_COUNT = 80
CANDIDATE_MIN_COUNT = 40
RELATIVE_MAE_MIN = 0.02
PLACEBO_Q = 0.95
N_PLACEBO = 100
N_BOOT = 2000
SEED_PLACEBO = 20260830
SEED_BOOT = 20260831

WARMUP_START_MS = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
DEV_START_MS = int(datetime(2020, 2, 1, tzinfo=UTC).timestamp() * 1000)
DEV_END_MS = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
MAX_H_MIN = max(HORIZONS)
T_MAX_MS = DEV_END_MS - MAX_H_MIN * BAR_MS - GRID_MS

LEVEL_NAMES = ("L1", "L2", "L3", "L4", "L5")
TRANSITION_NAMES = ("DOWN", "FLAT", "UP")
UP_STATE = 2
DOWN_STATE = 0
MISSING_STATE = -1

GATE_NAMES = (
    "primary_positive",
    "material_relative_mae",
    "bootstrap_positive",
    "placebo_separation",
    "transition_ordering",
    "horizon_robustness",
    "parameter_robustness",
    "year_stability",
)
PER_CELL_GATE_NAMES = GATE_NAMES[:5]


class B201Error(RuntimeError):
    """Base B2-01 implementation error."""


class B201InputError(B201Error):
    """Malformed or internally inconsistent input."""


def load_prereg(path: Path = PREREG_JSON) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise B201InputError("B2-01 prereg must be a JSON object")
    return data


def validate_prereg(data: Mapping[str, object]) -> None:
    """Fail closed if implementation constants drift from the frozen prereg."""
    expected_scalars = {
        "formulation_id": HYPOTHESIS_ID,
        "primary_family": "F3",
        "search_surface_primary_cells": 16,
        "outcome_access_authorized": False,
        "validation_2025_authorized": False,
        "oos_2026_authorized": False,
    }
    for key, expected in expected_scalars.items():
        if data.get(key) != expected:
            raise B201InputError(f"prereg {key} mismatch: {data.get(key)!r} != {expected!r}")

    dataset = data.get("dataset")
    if not isinstance(dataset, Mapping):
        raise B201InputError("prereg dataset must be a mapping")
    if dataset.get("dataset_id") != DATASET_ID:
        raise B201InputError("prereg dataset_id mismatch")
    if dataset.get("snapshot_id") != REQUIRED_SNAPSHOT:
        raise B201InputError("prereg snapshot_id mismatch")
    if dataset.get("timeframe") != "1m":
        raise B201InputError("prereg timeframe must remain 1m")
    if dataset.get("decision_grid_minutes") != GRID_MIN:
        raise B201InputError("prereg decision grid mismatch")

    if tuple(data.get("feature_windows_minutes", ())) != W_WINDOWS:
        raise B201InputError("prereg feature windows drifted")
    if tuple(data.get("transition_lags_minutes", ())) != D_LAGS:
        raise B201InputError("prereg transition lags drifted")
    if tuple(data.get("horizons_minutes", ())) != HORIZONS:
        raise B201InputError("prereg horizons drifted")
    if data.get("reference_days") != REF_DAYS:
        raise B201InputError("prereg reference_days drifted")

    forecast = data.get("forecast")
    if not isinstance(forecast, Mapping):
        raise B201InputError("prereg forecast must be a mapping")
    if forecast.get("baseline_min_count") != BASELINE_MIN_COUNT:
        raise B201InputError("baseline_min_count drifted")
    if forecast.get("candidate_min_count") != CANDIDATE_MIN_COUNT:
        raise B201InputError("candidate_min_count drifted")
    if forecast.get("estimator") != "median":
        raise B201InputError("estimator drifted")
    eligibility = str(forecast.get("eligibility_rule", ""))
    for token in (
        "baseline_count >= 80",
        "candidate_joint_count >= 40",
        "UNAVAILABLE_FOR_DECISION",
        "exact same canonical event IDs",
        "no fallback",
    ):
        if token not in eligibility:
            raise B201InputError(f"prereg eligibility_rule missing {token!r}")

    controls = data.get("controls")
    if not isinstance(controls, Mapping):
        raise B201InputError("prereg controls must be a mapping")
    expected_controls = {
        "permutation_seed": SEED_PLACEBO,
        "permutation_replicates": N_PLACEBO,
        "bootstrap_seed": SEED_BOOT,
        "bootstrap_replicates": N_BOOT,
        "bootstrap_block": "UTC_week",
    }
    for key, expected in expected_controls.items():
        if controls.get(key) != expected:
            raise B201InputError(f"prereg control {key} drifted")

    thresholds = data.get("per_cell_thresholds")
    if not isinstance(thresholds, Mapping):
        raise B201InputError("per_cell_thresholds must be a mapping")
    if thresholds.get("relative_mae_improvement_min") != RELATIVE_MAE_MIN:
        raise B201InputError("relative MAE threshold drifted")
    if thresholds.get("placebo_percentile") != PLACEBO_Q:
        raise B201InputError("placebo percentile drifted")

    gate_contract = data.get("promotion_gate_contract")
    if not isinstance(gate_contract, Mapping):
        raise B201InputError("promotion_gate_contract must be a mapping")
    if tuple(gate_contract.get("required_gate_names", ())) != GATE_NAMES:
        raise B201InputError("promotion gate names drifted")


def promotion_gate_contract() -> PromotionGateContract:
    return PromotionGateContract(required_gate_names=GATE_NAMES)


def _require_pyarrow():
    try:
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - CI installs pyarrow.
        raise B201InputError(
            "B2-01 development parquet loading requires pyarrow; "
            "install requirements-research.txt or requirements-dev.txt"
        ) from exc
    return pq


def _to_finite_positive_float(value: object, label: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise B201InputError(f"{label} is not numeric") from exc
    if not math.isfinite(out) or out <= 0.0:
        raise B201InputError(f"{label} must be finite and > 0")
    return out


def validate_1m_frame(frame: Mapping[str, np.ndarray]) -> None:
    required = ("open_time_ms", "available_at_ms", "close")
    if any(name not in frame for name in required):
        raise B201InputError("1m frame missing required columns")
    open_ms = np.asarray(frame["open_time_ms"])
    avail = np.asarray(frame["available_at_ms"])
    close = np.asarray(frame["close"])
    if not (open_ms.ndim == avail.ndim == close.ndim == 1):
        raise B201InputError("1m columns must be one-dimensional")
    if not (len(open_ms) == len(avail) == len(close)) or len(open_ms) < 2:
        raise B201InputError("1m columns must have equal non-trivial length")
    if open_ms.dtype.kind not in "iu" or avail.dtype.kind not in "iu":
        raise B201InputError("timestamps must be integer milliseconds")
    if int(open_ms[0]) != WARMUP_START_MS:
        raise B201InputError("1m frame must begin at frozen warmup start")
    expected = int(open_ms[0]) + np.arange(len(open_ms), dtype=np.int64) * BAR_MS
    if np.any(open_ms.astype(np.int64) != expected):
        raise B201InputError("1m open_time_ms must be a contiguous 1m grid")
    if np.any(avail.astype(np.int64) != open_ms.astype(np.int64) + BAR_MS):
        raise B201InputError("1m available_at_ms must equal bar_end_exclusive")
    if int(open_ms[-1]) >= DEV_END_MS:
        raise B201InputError("1m frame reaches reserved 2025+ data")
    close_f = close.astype(np.float64)
    if not np.all(np.isfinite(close_f)) or np.any(close_f <= 0.0):
        raise B201InputError("close must be finite and positive")


def load_authorized_1m(authorized: AuthorizedDataset) -> dict[str, np.ndarray]:
    """Read only partitions already authorized and checksum-bound by Harness v1."""
    if not isinstance(authorized, AuthorizedDataset):
        raise B201InputError("authorized must be an AuthorizedDataset proof")
    pq = _require_pyarrow()
    chunks: dict[str, list[np.ndarray]] = {
        "open_time_ms": [],
        "available_at_ms": [],
        "close": [],
    }
    for path in authorized.list_monthly_partitions():
        table = pq.read_table(path, columns=list(chunks))
        for name in ("open_time_ms", "available_at_ms"):
            chunks[name].append(np.asarray(table.column(name).to_pylist(), dtype=np.int64))
        chunks["close"].append(
            np.asarray(
                [_to_finite_positive_float(v, "close") for v in table.column("close").to_pylist()],
                dtype=np.float64,
            )
        )
    frame = {name: np.concatenate(parts) for name, parts in chunks.items()}
    order = np.argsort(frame["open_time_ms"], kind="mergesort")
    frame = {name: values[order] for name, values in frame.items()}
    validate_1m_frame(frame)
    return frame


def _grid_ms() -> np.ndarray:
    # The dataset begins at 00:00; the first causal 15m decision boundary is
    # 00:15, after the first complete 15m source bucket exists.
    return np.arange(
        WARMUP_START_MS + GRID_MS,
        T_MAX_MS + GRID_MS,
        GRID_MS,
        dtype=np.int64,
    )


def _log_return_squares(close: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    log_close = np.log(close.astype(np.float64))
    r = np.full(len(close), np.nan, dtype=np.float64)
    r[1:] = np.diff(log_close)
    r2 = r * r
    finite = np.isfinite(r2)
    sums = np.concatenate(([0.0], np.cumsum(np.where(finite, r2, 0.0))))
    invalid = np.concatenate(([0], np.cumsum((~finite).astype(np.int64))))
    return sums, invalid


def _window_rv(
    prefix_sum: np.ndarray,
    prefix_invalid: np.ndarray,
    start_idx: np.ndarray,
    end_idx: np.ndarray,
) -> np.ndarray:
    out = np.full(len(start_idx), np.nan, dtype=np.float64)
    ok = (
        (start_idx >= 0)
        & (end_idx >= start_idx)
        & (end_idx < len(prefix_sum))
    )
    positions = np.flatnonzero(ok)
    for k in positions:
        a = int(start_idx[k])
        b = int(end_idx[k])
        if prefix_invalid[b] - prefix_invalid[a] != 0:
            continue
        value = prefix_sum[b] - prefix_sum[a]
        if value >= 0.0 and math.isfinite(float(value)):
            out[k] = math.sqrt(float(value))
    return out


def rolling_midrank_percentile(series: np.ndarray, window: int = REF_STEPS) -> np.ndarray:
    """Midrank of current value against exactly the preceding window records.

    The current record is excluded. No full-sample thresholds or future values
    are used. If the complete frozen reference window is not finite, output is
    unavailable.
    """
    values = np.asarray(series, dtype=np.float64)
    out = np.full(len(values), np.nan, dtype=np.float64)
    sorted_values: list[float] = []
    queue: deque[float | None] = deque()
    finite_count = 0

    for i, raw in enumerate(values):
        x = float(raw)
        if (
            len(queue) == window
            and finite_count == window
            and math.isfinite(x)
        ):
            lo = bisect_left(sorted_values, x)
            hi = bisect_right(sorted_values, x)
            out[i] = (lo + 0.5 * (hi - lo)) / window

        item: float | None = x if math.isfinite(x) else None
        queue.append(item)
        if item is not None:
            insort_right(sorted_values, item)
            finite_count += 1

        if len(queue) > window:
            old = queue.popleft()
            if old is not None:
                pos = bisect_left(sorted_values, old)
                if pos >= len(sorted_values) or sorted_values[pos] != old:
                    raise B201InputError("rolling midrank window lost deterministic state")
                sorted_values.pop(pos)
                finite_count -= 1

    return out


def _state_from_percentile(p: np.ndarray, cuts: Sequence[float]) -> np.ndarray:
    values = np.asarray(p, dtype=np.float64)
    out = np.full(len(values), MISSING_STATE, dtype=np.int8)
    for i, x in enumerate(values):
        if not math.isfinite(float(x)) or x < 0.0 or x > 1.0:
            continue
        assigned = False
        for state in range(len(cuts) - 1):
            lo, hi = cuts[state], cuts[state + 1]
            if lo <= x < hi or (state == len(cuts) - 2 and x == hi):
                out[i] = state
                assigned = True
                break
        if not assigned:
            raise B201InputError(f"finite percentile not assigned to state: {x}")
    return out


def canonical_event_id(t_ms: int, w_min: int, d_min: int, h_min: int) -> str:
    if w_min not in W_WINDOWS or d_min not in D_LAGS or h_min not in HORIZONS:
        raise B201InputError("event identity uses non-frozen W/D/H")
    return (
        f"{REQUIRED_SNAPSHOT}|1m|T={int(t_ms)}|"
        f"W={int(w_min)}|D={int(d_min)}|H={int(h_min)}"
    )


def _utc_year(t_ms: int) -> int:
    return datetime.fromtimestamp(t_ms / 1000, tz=UTC).year


def _utc_month_key(t_ms: int) -> str:
    return datetime.fromtimestamp(t_ms / 1000, tz=UTC).strftime("%Y-%m")


def _utc_week_key(t_ms: int) -> str:
    d = datetime.fromtimestamp(t_ms / 1000, tz=UTC)
    iso = d.isocalendar()
    return f"{iso.year:04d}-W{iso.week:02d}"


class _SortedValueWindow:
    """Small deterministic sorted multiset keyed by unique integer record id."""

    def __init__(self) -> None:
        self._sorted: list[tuple[float, int]] = []
        self._by_id: dict[int, float] = {}

    def __len__(self) -> int:
        return len(self._sorted)

    def add(self, record_id: int, value: float) -> None:
        if record_id in self._by_id:
            raise B201InputError(f"duplicate rolling record id {record_id}")
        if not math.isfinite(value):
            raise B201InputError("rolling window may only store finite values")
        pair = (float(value), int(record_id))
        insort_right(self._sorted, pair)
        self._by_id[int(record_id)] = float(value)

    def remove(self, record_id: int) -> None:
        value = self._by_id.pop(int(record_id), None)
        if value is None:
            return
        pair = (value, int(record_id))
        pos = bisect_left(self._sorted, pair)
        if pos >= len(self._sorted) or self._sorted[pos] != pair:
            raise B201InputError("rolling median window lost deterministic state")
        self._sorted.pop(pos)

    def median(self) -> float:
        n = len(self._sorted)
        if n == 0:
            return float("nan")
        mid = n // 2
        if n % 2:
            return float(self._sorted[mid][0])
        return 0.5 * (self._sorted[mid - 1][0] + self._sorted[mid][0])


def _causal_past_median(
    future_rv: np.ndarray,
    h_steps: int,
    ref_steps: int = REF_STEPS,
) -> np.ndarray:
    values = np.asarray(future_rv, dtype=np.float64)
    out = np.full(len(values), np.nan, dtype=np.float64)
    window = _SortedValueWindow()
    for i in range(len(values)):
        j_add = i - h_steps
        if j_add >= 0 and math.isfinite(float(values[j_add])):
            window.add(j_add, float(values[j_add]))
        j_remove = i - ref_steps - 1
        if j_remove >= 0:
            window.remove(j_remove)
        if len(window):
            out[i] = window.median()
    return out


def build_panel(frame_1m: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Build only frozen B2-01 features/targets on the causal 15m grid."""
    validate_1m_frame(frame_1m)
    open_ms = np.asarray(frame_1m["open_time_ms"], dtype=np.int64)
    avail = np.asarray(frame_1m["available_at_ms"], dtype=np.int64)
    close = np.asarray(frame_1m["close"], dtype=np.float64)

    grid = _grid_ms()
    offset = ((grid - int(open_ms[0])) // BAR_MS).astype(np.int64)
    if np.any(grid < open_ms[0]) or np.any(offset < 0):
        raise B201InputError("decision grid precedes authorized 1m frame")
    if np.any(offset >= len(open_ms)):
        raise B201InputError("decision grid exceeds authorized 1m frame")

    last_idx = offset - 1
    if np.any(last_idx < 0):
        raise B201InputError("decision grid lacks prior 1m bar")
    feature_available = avail[last_idx]
    assert_no_lookahead(grid.tolist(), feature_available.tolist())

    prefix_sum, prefix_invalid = _log_return_squares(close)
    panel: dict[str, np.ndarray] = {
        "t_ms": grid,
        "feature_available_at_ms": feature_available.astype(np.int64),
        "in_development": (grid >= DEV_START_MS) & (grid <= T_MAX_MS),
        "year": np.asarray([_utc_year(int(t)) for t in grid], dtype=np.int16),
        "month_key": np.asarray([_utc_month_key(int(t)) for t in grid]),
        "week_key": np.asarray([_utc_week_key(int(t)) for t in grid]),
    }

    for w in W_WINDOWS:
        starts = offset - w
        rv = _window_rv(prefix_sum, prefix_invalid, starts, offset)
        panel[f"rv_{w}"] = rv
        level_p = rolling_midrank_percentile(rv)
        panel[f"level_p_{w}"] = level_p
        panel[f"level_state_{w}"] = _state_from_percentile(
            level_p, (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        )

        for d in D_LAGS:
            d_steps = d // GRID_MIN
            raw = np.full(len(grid), np.nan, dtype=np.float64)
            for i in range(d_steps, len(grid)):
                now = float(rv[i])
                prev = float(rv[i - d_steps])
                if now > 0.0 and prev > 0.0 and math.isfinite(now) and math.isfinite(prev):
                    raw[i] = math.log(now / prev)
            panel[f"transition_raw_{w}_{d}"] = raw
            transition_p = rolling_midrank_percentile(raw)
            panel[f"transition_p_{w}_{d}"] = transition_p
            panel[f"transition_state_{w}_{d}"] = _state_from_percentile(
                transition_p, (0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0)
            )

    for h in HORIZONS:
        end = offset + h
        future_rv = _window_rv(prefix_sum, prefix_invalid, offset, end)
        legal = (grid + h * BAR_MS) < DEV_END_MS
        future_rv[~legal] = np.nan
        panel[f"future_rv_{h}"] = future_rv
        h_steps = h // GRID_MIN
        past_med = _causal_past_median(future_rv, h_steps)
        panel[f"past_median_future_rv_{h}"] = past_med
        target = np.full(len(grid), np.nan, dtype=np.float64)
        ok = (
            np.isfinite(future_rv)
            & np.isfinite(past_med)
            & (future_rv > 0.0)
            & (past_med > 0.0)
        )
        target[ok] = np.log(future_rv[ok] / past_med[ok])
        panel[f"y_{h}"] = target

    return panel


def _walk_forward_forecasts(
    target: np.ndarray,
    level_state: np.ndarray,
    transition_state: np.ndarray,
    h_steps: int,
    *,
    baseline_min_count: int,
    candidate_min_count: int,
    ref_steps: int = REF_STEPS,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Causal historical medians with joint fail-closed eligibility."""
    y = np.asarray(target, dtype=np.float64)
    level = np.asarray(level_state, dtype=np.int16)
    transition = np.asarray(transition_state, dtype=np.int16)
    if not (len(y) == len(level) == len(transition)):
        raise B201InputError("walk-forward arrays differ in length")

    base_windows: dict[int, _SortedValueWindow] = defaultdict(_SortedValueWindow)
    cand_windows: dict[tuple[int, int], _SortedValueWindow] = defaultdict(_SortedValueWindow)
    base_pred = np.full(len(y), np.nan, dtype=np.float64)
    cand_pred = np.full(len(y), np.nan, dtype=np.float64)
    eligible = np.zeros(len(y), dtype=bool)

    def add_record(j: int) -> None:
        if not (
            0 <= j < len(y)
            and math.isfinite(float(y[j]))
            and int(level[j]) >= 0
        ):
            return
        lvl = int(level[j])
        base_windows[lvl].add(j, float(y[j]))
        if int(transition[j]) >= 0:
            state = int(transition[j])
            cand_windows[(lvl, state)].add(j, float(y[j]))

    def remove_record(j: int) -> None:
        if not (
            0 <= j < len(y)
            and math.isfinite(float(y[j]))
            and int(level[j]) >= 0
        ):
            return
        lvl = int(level[j])
        base_windows[lvl].remove(j)
        if int(transition[j]) >= 0:
            state = int(transition[j])
            cand_windows[(lvl, state)].remove(j)

    for i in range(len(y)):
        add_record(i - h_steps)
        remove_record(i - ref_steps - 1)

        lvl = int(level[i])
        state = int(transition[i])
        if lvl < 0 or state < 0:
            continue
        b = base_windows[lvl]
        c = cand_windows[(lvl, state)]
        if len(b) < baseline_min_count or len(c) < candidate_min_count:
            continue
        base_pred[i] = b.median()
        cand_pred[i] = c.median()
        eligible[i] = True

    return base_pred, cand_pred, eligible


def walk_forward_forecasts(
    target: np.ndarray,
    level_state: np.ndarray,
    transition_state: np.ndarray,
    h_steps: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return _walk_forward_forecasts(
        target,
        level_state,
        transition_state,
        h_steps,
        baseline_min_count=BASELINE_MIN_COUNT,
        candidate_min_count=CANDIDATE_MIN_COUNT,
    )


def paired_loss_summary(
    candidate_ae_by_id: Mapping[Hashable, float],
    baseline_ae_by_id: Mapping[Hashable, float],
) -> dict:
    proof = paired_same_support_delta(candidate_ae_by_id, baseline_ae_by_id)
    candidate_mean = float(proof["candidate_support_mean"])
    baseline_mean = float(proof["reference_support_mean"])
    if baseline_mean <= 0.0:
        raise B201InputError("baseline MAE must be positive on scored support")
    return {
        "support_n": int(proof["support_n"]),
        "candidate_mae": candidate_mean,
        "baseline_mae": baseline_mean,
        "mean_ae_improvement": baseline_mean - candidate_mean,
        "relative_mae_improvement": 1.0 - candidate_mean / baseline_mean,
    }


def week_block_bootstrap_interval(
    improvement: np.ndarray,
    t_ms: np.ndarray,
    *,
    n_boot: int = N_BOOT,
    seed: int = SEED_BOOT,
) -> tuple[float, float]:
    values = np.asarray(improvement, dtype=np.float64)
    times = np.asarray(t_ms, dtype=np.int64)
    if len(values) != len(times) or len(values) == 0:
        raise B201InputError("bootstrap inputs must be equal non-empty arrays")
    if not np.all(np.isfinite(values)):
        raise B201InputError("bootstrap improvement must be finite")
    blocks: dict[str, list[float]] = defaultdict(list)
    for value, t in zip(values, times):
        blocks[_utc_week_key(int(t))].append(float(value))
    keys = sorted(blocks)
    if not keys:
        raise B201InputError("bootstrap has no UTC-week blocks")
    sums = np.asarray([sum(blocks[k]) for k in keys], dtype=np.float64)
    counts = np.asarray([len(blocks[k]) for k in keys], dtype=np.int64)
    rng = np.random.default_rng(seed)
    reps = np.empty(n_boot, dtype=np.float64)
    for r in range(n_boot):
        pick = rng.integers(0, len(keys), size=len(keys))
        denom = int(np.sum(counts[pick]))
        if denom <= 0:
            raise B201InputError("bootstrap sampled empty support")
        reps[r] = float(np.sum(sums[pick]) / denom)
    q = np.quantile(reps, [0.025, 0.975])
    return float(q[0]), float(q[1])


def _seed_from_parts(*parts: object) -> int:
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big", signed=False)


def _placebo_candidate_prediction(
    *,
    i: int,
    replicate: int,
    t_ms: np.ndarray,
    target: np.ndarray,
    level_state: np.ndarray,
    transition_state: np.ndarray,
    w_min: int,
    d_min: int,
    h_min: int,
    ref_steps: int,
    candidate_min_count: int,
) -> float:
    h_steps = h_min // GRID_MIN
    right = i - h_steps
    left = max(0, i - ref_steps)
    if right < left:
        return float("nan")
    current_level = int(level_state[i])
    current_transition = int(transition_state[i])
    if current_level < 0 or current_transition < 0:
        return float("nan")

    strata: dict[str, list[int]] = defaultdict(list)
    for j in range(left, right + 1):
        if (
            math.isfinite(float(target[j]))
            and int(level_state[j]) == current_level
            and int(transition_state[j]) >= 0
        ):
            strata[_utc_month_key(int(t_ms[j]))].append(j)

    selected_values: list[float] = []
    for month in sorted(strata):
        ordered = sorted(
            strata[month],
            key=lambda j: canonical_event_id(
                int(t_ms[j]), w_min, d_min, h_min
            ),
        )
        labels = np.asarray([int(transition_state[j]) for j in ordered], dtype=np.int8)
        stratum_id = f"{month}|L={current_level}"
        seed = _seed_from_parts(
            SEED_PLACEBO,
            replicate,
            w_min,
            d_min,
            h_min,
            int(t_ms[i]),
            stratum_id,
        )
        rng = np.random.default_rng(seed)
        shuffled = labels.copy()
        rng.shuffle(shuffled)
        for j, assigned in zip(ordered, shuffled, strict=True):
            if int(assigned) == current_transition:
                selected_values.append(float(target[j]))

    if len(selected_values) < candidate_min_count:
        return float("nan")
    return float(np.median(np.asarray(selected_values, dtype=np.float64)))


def causal_placebo_mean_improvements(
    *,
    scored_indices: np.ndarray,
    t_ms: np.ndarray,
    target: np.ndarray,
    level_state: np.ndarray,
    transition_state: np.ndarray,
    baseline_pred: np.ndarray,
    w_min: int,
    d_min: int,
    h_min: int,
    n_replicates: int = N_PLACEBO,
    ref_steps: int = REF_STEPS,
    candidate_min_count: int = CANDIDATE_MIN_COUNT,
) -> np.ndarray:
    """Exact causal placebo, with historical strata prepared once per event.

    This preserves the preregistered seed derivation and label-shuffle behavior
    exactly while avoiding the previous 100x repetition of the same 30-day
    historical scan and canonical ordering for every replicate.
    """
    indices = np.asarray(scored_indices, dtype=np.int64)
    if len(indices) == 0:
        raise B201InputError("placebo requires non-empty scored support")

    improvement_sums = np.zeros(n_replicates, dtype=np.float64)
    h_steps = h_min // GRID_MIN

    for i_raw in indices:
        i = int(i_raw)
        right = i - h_steps
        left = max(0, i - ref_steps)
        if right < left:
            raise B201InputError("placebo scored event has no mature causal history")

        current_level = int(level_state[i])
        current_transition = int(transition_state[i])
        if current_level < 0 or current_transition < 0:
            raise B201InputError("placebo scored event has unavailable decision state")

        strata: dict[str, list[int]] = defaultdict(list)
        for j in range(left, right + 1):
            if (
                math.isfinite(float(target[j]))
                and int(level_state[j]) == current_level
                and int(transition_state[j]) >= 0
            ):
                strata[_utc_month_key(int(t_ms[j]))].append(j)

        prepared: list[tuple[str, np.ndarray, np.ndarray]] = []
        selected_count = 0
        for month in sorted(strata):
            ordered = sorted(
                strata[month],
                key=lambda j: canonical_event_id(
                    int(t_ms[j]), w_min, d_min, h_min
                ),
            )
            labels = np.asarray(
                [int(transition_state[j]) for j in ordered],
                dtype=np.int8,
            )
            values = np.asarray([float(target[j]) for j in ordered], dtype=np.float64)
            selected_count += int(np.count_nonzero(labels == current_transition))
            prepared.append((f"{month}|L={current_level}", labels, values))

        if selected_count < candidate_min_count:
            raise B201InputError(
                "placebo lost scored support despite count-preserving stratum permutation"
            )

        event_target = float(target[i])
        base_ae = abs(event_target - float(baseline_pred[i]))

        for replicate in range(n_replicates):
            selected_parts: list[np.ndarray] = []
            for stratum_id, labels, values in prepared:
                seed = _seed_from_parts(
                    SEED_PLACEBO,
                    replicate,
                    w_min,
                    d_min,
                    h_min,
                    int(t_ms[i]),
                    stratum_id,
                )
                rng = np.random.default_rng(seed)
                shuffled = labels.copy()
                rng.shuffle(shuffled)
                selected_parts.append(values[shuffled == current_transition])

            selected_values = np.concatenate(selected_parts)
            if selected_values.size < candidate_min_count:
                raise B201InputError(
                    "placebo lost scored support despite count-preserving stratum permutation"
                )
            pred = float(np.median(selected_values))
            placebo_ae = abs(event_target - pred)
            improvement_sums[replicate] += base_ae - placebo_ae

    return improvement_sums / len(indices)

def _optional_float(value: float) -> float | None:
    return float(value) if math.isfinite(float(value)) else None


def evaluate_cell(
    panel: Mapping[str, np.ndarray],
    w_min: int,
    d_min: int,
    h_min: int,
    *,
    run_placebo: bool = True,
) -> dict:
    t_ms = np.asarray(panel["t_ms"], dtype=np.int64)
    target = np.asarray(panel[f"y_{h_min}"], dtype=np.float64)
    level = np.asarray(panel[f"level_state_{w_min}"], dtype=np.int16)
    transition = np.asarray(panel[f"transition_state_{w_min}_{d_min}"], dtype=np.int16)
    in_dev = np.asarray(panel["in_development"], dtype=bool)
    feature_avail = np.asarray(panel["feature_available_at_ms"], dtype=np.int64)
    assert_no_lookahead(t_ms.tolist(), feature_avail.tolist())

    base_pred, cand_pred, model_eligible = walk_forward_forecasts(
        target, level, transition, h_min // GRID_MIN
    )
    scored = (
        in_dev
        & model_eligible
        & np.isfinite(target)
        & np.isfinite(base_pred)
        & np.isfinite(cand_pred)
    )
    idx = np.flatnonzero(scored)
    if len(idx) == 0:
        return {
            "W": w_min,
            "D": d_min,
            "H": h_min,
            "support_n": 0,
            "metrics": {"placebo_evaluation": "SKIPPED_NO_SCORED_SUPPORT"},
            "year_mean_ae_improvement": {str(y): None for y in YEAR_BLOCKS},
            "per_cell_gates": {name: False for name in PER_CELL_GATE_NAMES},
            "year_stability_pass": False,
        }

    candidate_ae_by_id: dict[str, float] = {}
    baseline_ae_by_id: dict[str, float] = {}
    improvements = np.empty(len(idx), dtype=np.float64)
    for k, i_raw in enumerate(idx):
        i = int(i_raw)
        event_id = canonical_event_id(int(t_ms[i]), w_min, d_min, h_min)
        c_ae = abs(float(target[i]) - float(cand_pred[i]))
        b_ae = abs(float(target[i]) - float(base_pred[i]))
        candidate_ae_by_id[event_id] = c_ae
        baseline_ae_by_id[event_id] = b_ae
        improvements[k] = b_ae - c_ae

    loss = paired_loss_summary(candidate_ae_by_id, baseline_ae_by_id)
    boot_lo, boot_hi = week_block_bootstrap_interval(improvements, t_ms[idx])

    residual = target[idx] - base_pred[idx]
    up = residual[transition[idx] == UP_STATE]
    down = residual[transition[idx] == DOWN_STATE]
    if len(up) and len(down):
        separation = float(np.median(up) - np.median(down))
    else:
        separation = float("nan")

    year_means: dict[str, float | None] = {}
    positive_years = 0
    years = np.asarray(panel["year"], dtype=np.int16)
    for year in YEAR_BLOCKS:
        vals = improvements[years[idx] == year]
        value = float(np.mean(vals)) if len(vals) else float("nan")
        year_means[str(year)] = _optional_float(value)
        if math.isfinite(value) and value > 0.0:
            positive_years += 1

    mean_improvement = float(loss["mean_ae_improvement"])
    relative = float(loss["relative_mae_improvement"])
    year_stability_pass = positive_years >= 4
    cheap_gates = {
        "primary_positive": mean_improvement > 0.0,
        "material_relative_mae": relative >= RELATIVE_MAE_MIN,
        "bootstrap_positive": boot_lo > 0.0,
        "transition_ordering": math.isfinite(separation) and separation > 0.0,
    }

    placebo_q95 = float("nan")
    placebo_status = "DISABLED"
    placebo_gate = False
    if run_placebo:
        if all(cheap_gates.values()) and year_stability_pass:
            placebo = causal_placebo_mean_improvements(
                scored_indices=idx,
                t_ms=t_ms,
                target=target,
                level_state=level,
                transition_state=transition,
                baseline_pred=base_pred,
                w_min=w_min,
                d_min=d_min,
                h_min=h_min,
            )
            placebo_q95 = float(np.quantile(placebo, PLACEBO_Q))
            placebo_gate = (
                math.isfinite(placebo_q95) and mean_improvement > placebo_q95
            )
            placebo_status = "EVALUATED"
        else:
            # Exact promotion semantics are preserved: once another mandatory
            # cell prerequisite is false, placebo cannot rescue the cell.
            placebo_status = "SKIPPED_FAIL_CLOSED_PRECONDITION"

    per_cell_gates = {
        "primary_positive": cheap_gates["primary_positive"],
        "material_relative_mae": cheap_gates["material_relative_mae"],
        "bootstrap_positive": cheap_gates["bootstrap_positive"],
        "placebo_separation": placebo_gate,
        "transition_ordering": cheap_gates["transition_ordering"],
    }
    return {
        "W": w_min,
        "D": d_min,
        "H": h_min,
        "support_n": int(len(idx)),
        "metrics": {
            **loss,
            "median_ae_improvement": float(np.median(improvements)),
            "bootstrap_95": [boot_lo, boot_hi],
            "transition_separation": _optional_float(separation),
            "placebo_q95_mean_ae_improvement": _optional_float(placebo_q95),
            "placebo_evaluation": placebo_status,
            "largest_month_support_share": _largest_month_share(t_ms[idx]),
            "top5_month_support_share": _top_month_share(t_ms[idx], 5),
            "unique_days": len({_utc_day_key(int(t)) for t in t_ms[idx]}),
            "unique_weeks": len({_utc_week_key(int(t)) for t in t_ms[idx]}),
            "unique_months": len({_utc_month_key(int(t)) for t in t_ms[idx]}),
            "transition_state_counts": {
                TRANSITION_NAMES[state]: int(np.sum(transition[idx] == state))
                for state in range(3)
            },
            "level_state_counts": {
                LEVEL_NAMES[lvl]: int(np.sum(level[idx] == lvl))
                for lvl in range(5)
            },
        },
        "year_mean_ae_improvement": year_means,
        "per_cell_gates": per_cell_gates,
        "year_stability_pass": year_stability_pass,
    }

def _utc_day_key(t_ms: int) -> str:
    return datetime.fromtimestamp(t_ms / 1000, tz=UTC).strftime("%Y-%m-%d")


def _largest_month_share(t_ms: np.ndarray) -> float:
    if len(t_ms) == 0:
        return 0.0
    counts: dict[str, int] = defaultdict(int)
    for t in t_ms:
        counts[_utc_month_key(int(t))] += 1
    return max(counts.values()) / len(t_ms)


def _top_month_share(t_ms: np.ndarray, n: int) -> float:
    if len(t_ms) == 0:
        return 0.0
    counts: dict[str, int] = defaultdict(int)
    for t in t_ms:
        counts[_utc_month_key(int(t))] += 1
    return sum(sorted(counts.values(), reverse=True)[:n]) / len(t_ms)


def _cell_five_pass(cell: Mapping[str, object]) -> bool:
    gates = cell.get("per_cell_gates")
    if not isinstance(gates, Mapping):
        return False
    return all(gates.get(name) is True for name in PER_CELL_GATE_NAMES)


def determine_promotion_gates(cells: Sequence[Mapping[str, object]]) -> tuple[dict, list[dict]]:
    """Compute frozen promotion gates with separate evidence per condition."""
    by_key = {
        (int(cell["W"]), int(cell["D"]), int(cell["H"])): cell
        for cell in cells
        if all(key in cell for key in ("W", "D", "H"))
    }

    per_gate_parameter_evidence = {name: False for name in PER_CELL_GATE_NAMES}
    horizon_robustness = False
    parameter_robustness = False
    year_stability = False
    selected: list[dict] = []

    for h1, h2 in ADJACENT_H_PAIRS:
        per_gate_wd: dict[str, list[tuple[int, int]]] = {
            name: [] for name in PER_CELL_GATE_NAMES
        }
        core_passing_wd: list[tuple[int, int]] = []
        stable_passing_wd: list[tuple[int, int]] = []

        for w in W_WINDOWS:
            for d in D_LAGS:
                c1 = by_key.get((w, d, h1))
                c2 = by_key.get((w, d, h2))
                if c1 is None or c2 is None:
                    continue

                for gate_name in PER_CELL_GATE_NAMES:
                    g1 = c1.get("per_cell_gates")
                    g2 = c2.get("per_cell_gates")
                    if (
                        isinstance(g1, Mapping)
                        and isinstance(g2, Mapping)
                        and g1.get(gate_name) is True
                        and g2.get(gate_name) is True
                    ):
                        per_gate_wd[gate_name].append((w, d))

                if _cell_five_pass(c1) and _cell_five_pass(c2):
                    horizon_robustness = True
                    core_passing_wd.append((w, d))
                    if (
                        c1.get("year_stability_pass") is True
                        and c2.get("year_stability_pass") is True
                    ):
                        stable_passing_wd.append((w, d))

        for gate_name, passing_wd in per_gate_wd.items():
            if len(passing_wd) >= 2:
                per_gate_parameter_evidence[gate_name] = True

        if len(core_passing_wd) >= 2:
            parameter_robustness = True

        if len(stable_passing_wd) >= 2:
            year_stability = True
            if not selected:
                chosen = sorted(stable_passing_wd)[:2]
                selected = [
                    {"W": w, "D": d, "H": h}
                    for w, d in chosen
                    for h in (h1, h2)
                ]

    gates = {
        **per_gate_parameter_evidence,
        "horizon_robustness": horizon_robustness,
        "parameter_robustness": parameter_robustness,
        "year_stability": year_stability,
    }
    return gates, selected

def evaluate_b2_01(panel: Mapping[str, np.ndarray]) -> dict:
    cells = [
        evaluate_cell(panel, w, d, h)
        for w in W_WINDOWS
        for d in D_LAGS
        for h in HORIZONS
    ]
    gates, selected = determine_promotion_gates(cells)
    contract = promotion_gate_contract()
    promoted = fail_closed_gate_conjunction(gates, contract)
    verdict = (
        "B2_01_PROMOTED_CANDIDATE"
        if promoted
        else "B2_01_CLOSED_NO_PROMOTION"
    )
    return {
        "hypothesis_id": HYPOTHESIS_ID,
        "dataset_id": DATASET_ID,
        "snapshot_id": REQUIRED_SNAPSHOT,
        "search_surface": {
            "feature_windows_minutes": list(W_WINDOWS),
            "transition_lags_minutes": list(D_LAGS),
            "horizons_minutes": list(HORIZONS),
            "primary_cells": 16,
        },
        "windows": {
            "warmup_start_inclusive_ms": WARMUP_START_MS,
            "development_start_inclusive_ms": DEV_START_MS,
            "development_end_exclusive_ms": DEV_END_MS,
            "t_max_inclusive_ms": T_MAX_MS,
            "validation_2025_untouched": True,
            "oos_2026_untouched": True,
        },
        "cells": cells,
        "promotion": {
            "gates": gates,
            "selected_neighborhood": selected,
            "passed": promoted,
            "verdict": verdict,
        },
    }
