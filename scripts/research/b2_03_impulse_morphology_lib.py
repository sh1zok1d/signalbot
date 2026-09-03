"""Outcome-blind B2-03 impulse-morphology numerical implementation.

Implements the frozen B2-03 preregistration using only in-memory arrays.
This module never opens files, enumerates datasets, talks to Git/network,
creates evidence reservations, or persists results.

This module deliberately does not use `from __future__ import annotations`:
the merged Batch02 static source policy default-denies every non-repository
import that is not on its explicit transform allowlist, and B2-03 source is
adapted to that bounded policy rather than the policy being widened. Python
3.11 evaluates the annotations used here natively.
"""

import hashlib
import math
from collections import defaultdict, deque
from decimal import Decimal
from typing import Mapping, Sequence

import numpy as np

from scripts.research.lib.batch02_contracts import rolling_midrank_percentile


HYPOTHESIS_ID = "B2-03_IMPULSE_MORPHOLOGY"
DATASET_ID = "CORE_BTC_BINANCE_V0"
REQUIRED_SNAPSHOT = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
PREREG_MERGE_SHA = "61bc9cfde80c6a142ac147ebee6487a1ae710324"

BAR_MS = 60_000
FIVE_MIN = 5
FIVE_MS = FIVE_MIN * BAR_MS
HOUR_MS = 60 * BAR_MS
DAY_MS = 24 * 60 * BAR_MS
SCALE_GRID_MIN = 15
SCALE_GRID_MS = SCALE_GRID_MIN * BAR_MS
VOL_WINDOW_MIN = 60
VOL_RETURNS = 60

W_VALUES = (15, 30, 60)
H_VALUES = (15, 30, 60, 120, 240)
PATH_BARS_BY_W = {15: 3, 30: 6, 60: 12}
ADJACENT_H_PAIRS = ((15, 30), (30, 60), (60, 120), (120, 240))
YEAR_BLOCKS = (2020, 2021, 2022, 2023, 2024)
PRIMARY_CELLS = 15

REF_DAYS = 30
REF_MS = REF_DAYS * DAY_MS
TRAIN_DAYS = 90
TRAIN_MS = TRAIN_DAYS * DAY_MS
BASELINE_MIN_COUNT = 80
CANDIDATE_MIN_COUNT = 40
RELATIVE_MAE_MIN = 0.02
PLACEBO_Q = 0.95
N_PLACEBO = 100
N_BOOT = 2000
SEED_PLACEBO = 20260904
SEED_BOOT = 20260905

WARMUP_START_MS = 1_577_836_800_000
DEV_START_MS = 1_580_515_200_000
DEV_END_MS = 1_735_689_600_000
VALIDATION_2025_START_MS = DEV_END_MS
OOS_2026_START_MS = 1_767_225_600_000
FIRST_FORBIDDEN_YEAR = 2025

LAST_LEGAL_T_MS = {
    15: 1_735_686_000_000,
    30: 1_735_686_000_000,
    60: 1_735_682_400_000,
    120: 1_735_678_800_000,
    240: 1_735_671_600_000,
}

STATE_LOW = 0
STATE_MID = 1
STATE_HIGH = 2
STATE_MISSING = -1
STATE_LABELS = ("LOW", "MID", "HIGH")
DIR_UP = 1
DIR_DOWN = -1
DIR_LABELS = {DIR_UP: "UP", DIR_DOWN: "DOWN"}

GATE_NAMES = (
    "primary_positive",
    "material_relative_mae",
    "bootstrap_positive",
    "placebo_separation",
    "morphology_ordering",
    "horizon_robustness",
    "parameter_robustness",
    "year_stability",
)
PER_CELL_GATE_NAMES = GATE_NAMES[:5]
COMPONENT_NAMES = (
    "distributedness",
    "path_efficiency",
    "directional_bar_share",
    "countermove_shallowness",
)


class B203Error(RuntimeError):
    """B2-03 implementation input/invariant error."""


def _finite_price(value: object, label: str) -> float:
    try:
        out = float(Decimal(str(value)))
    except Exception as exc:
        raise B203Error(f"{label} is not a valid decimal price") from exc
    if not math.isfinite(out) or out <= 0.0:
        raise B203Error(f"{label} must be finite and > 0")
    return out


def table_to_1m_frame(table: object) -> dict[str, np.ndarray]:
    """Convert an authorized Arrow table without any direct file access."""
    columns = ("open_time_ms", "available_at_ms", "close")
    values: dict[str, np.ndarray] = {}
    for name in columns:
        try:
            column = table.column(name)
        except Exception as exc:
            raise B203Error(f"authorized table missing canonical column {name}") from exc
        try:
            raw = column.to_numpy(zero_copy_only=False)
        except Exception as exc:
            raise B203Error(
                f"authorized column {name} is not convertible in memory"
            ) from exc
        if name in {"open_time_ms", "available_at_ms"}:
            try:
                values[name] = np.asarray(raw, dtype=np.int64)
            except (TypeError, ValueError) as exc:
                raise B203Error(
                    f"authorized column {name} is not integer milliseconds"
                ) from exc
        else:
            values[name] = np.asarray(
                [_finite_price(v, name) for v in raw],
                dtype=np.float64,
            )
    validate_1m_frame(values)
    return values


def validate_1m_frame(frame: Mapping[str, np.ndarray]) -> None:
    columns = ("open_time_ms", "available_at_ms", "close")
    if any(name not in frame for name in columns):
        raise B203Error("1m frame missing canonical time/close columns")
    arrays = {name: np.asarray(frame[name]) for name in columns}
    n = len(arrays["open_time_ms"])
    if n == 0 or any(a.ndim != 1 or len(a) != n for a in arrays.values()):
        raise B203Error("1m columns must be equal non-empty one-dimensional arrays")
    open_ms = arrays["open_time_ms"].astype(np.int64, copy=False)
    avail = arrays["available_at_ms"].astype(np.int64, copy=False)
    close = arrays["close"].astype(np.float64, copy=False)
    if not np.all(np.isfinite(close)) or np.any(close <= 0.0):
        raise B203Error("close must be finite and strictly positive")
    if (
        int(np.max(open_ms)) >= DEV_END_MS
        or int(np.max(avail)) > VALIDATION_2025_START_MS
        or int(np.min(open_ms)) >= DEV_END_MS
        or int(np.min(avail)) > VALIDATION_2025_START_MS
    ):
        raise B203Error("1m frame reaches reserved 2025+ source data")
    if int(open_ms[0]) != WARMUP_START_MS:
        raise B203Error("1m frame must begin at frozen warmup start")
    if int(open_ms[0]) % FIVE_MS != 0:
        raise B203Error("1m frame must start on a UTC 5m boundary")
    expected = int(open_ms[0]) + np.arange(n, dtype=np.int64) * BAR_MS
    if np.any(open_ms != expected):
        raise B203Error("1m open_time_ms must be a contiguous minute grid")
    if np.any(avail != open_ms + BAR_MS):
        raise B203Error("available_at_ms must equal open_time_ms + 60000")
    if len(np.unique(open_ms)) != n:
        raise B203Error("1m open_time_ms contains duplicates")


def _partition_year(relative_path: str) -> int:
    leaf = str(relative_path).rsplit("/", 1)[-1]
    head = leaf.split("-", 1)[0]
    if len(head) != 4 or not head.isdigit():
        raise B203Error(
            f"authorized partition path is not a canonical monthly leaf: {relative_path}"
        )
    return int(head)


def derive_forbidden_window_evidence(
    run_identity: Mapping[str, object],
    frame: Mapping[str, np.ndarray],
) -> dict[str, object]:
    """Prove 2025/2026 were not reached from the authorized view only."""
    window = run_identity.get("window")
    if not isinstance(window, Mapping):
        raise B203Error("run identity is missing its authorized window evidence")
    try:
        end_exclusive_ms = int(window["end_exclusive_ms"])
        start_inclusive_ms = int(window["start_inclusive_ms"])
        allowed_years = tuple(int(year) for year in window["allowed_years"])
    except (KeyError, TypeError, ValueError) as exc:
        raise B203Error("authorized window evidence is malformed") from exc

    partitions = run_identity.get("partitions")
    if not isinstance(partitions, Sequence) or isinstance(partitions, (str, bytes)):
        raise B203Error("run identity is missing its authorized partition evidence")
    partition_years: list[int] = []
    for partition in partitions:
        if not isinstance(partition, Mapping) or "relative_path" not in partition:
            raise B203Error("authorized partition evidence is malformed")
        partition_years.append(_partition_year(str(partition["relative_path"])))
    if not partition_years:
        raise B203Error("authorized partition evidence is empty")

    open_ms = np.asarray(frame["open_time_ms"], dtype=np.int64)
    avail_ms = np.asarray(frame["available_at_ms"], dtype=np.int64)
    if len(open_ms) == 0:
        raise B203Error("loaded development frame is empty")
    observed_min_open_ms = int(np.min(open_ms))
    observed_max_open_ms = int(np.max(open_ms))
    observed_max_available_ms = int(np.max(avail_ms))

    if end_exclusive_ms > VALIDATION_2025_START_MS:
        raise B203Error("authorized window reaches the reserved 2025 validation pool")
    if max(allowed_years) >= FIRST_FORBIDDEN_YEAR:
        raise B203Error("authorized years reach a forbidden window")
    if max(partition_years) >= FIRST_FORBIDDEN_YEAR:
        raise B203Error("authorized partitions reach a forbidden window")
    if observed_max_available_ms > VALIDATION_2025_START_MS:
        raise B203Error("loaded development bytes reach the reserved 2025 pool")

    return {
        "2025_validation": False,
        "2026_oos": False,
        "derivation": "authorized-view-and-loaded-bytes",
        "authorized_window_start_inclusive_ms": start_inclusive_ms,
        "authorized_window_end_exclusive_ms": end_exclusive_ms,
        "authorized_allowed_years": list(allowed_years),
        "authorized_partition_count": len(partition_years),
        "authorized_max_partition_year": max(partition_years),
        "observed_min_open_time_ms": observed_min_open_ms,
        "observed_max_open_time_ms": observed_max_open_ms,
        "observed_max_available_at_ms": observed_max_available_ms,
        "validation_2025_start_ms": VALIDATION_2025_START_MS,
        "oos_2026_start_ms": OOS_2026_START_MS,
    }


def last_legal_t_ms(H: int) -> int:
    if int(H) not in LAST_LEGAL_T_MS:
        raise B203Error("horizon is not in the frozen H set")
    return LAST_LEGAL_T_MS[int(H)]


def scoring_eligible(T_ms: int, H: int) -> bool:
    """Development scoring requires T+H strictly before 2025-01-01."""
    t = int(T_ms)
    h = int(H)
    if t % HOUR_MS != 0:
        return False
    if t < DEV_START_MS or t >= DEV_END_MS:
        return False
    return t + h * BAR_MS < DEV_END_MS


def _close_ending_at(
    open_ms: np.ndarray,
    avail: np.ndarray,
    close: np.ndarray,
    t_end: int,
) -> float | None:
    start = int(open_ms[0])
    open_t = int(t_end) - BAR_MS
    delta = open_t - start
    if delta < 0 or delta % BAR_MS != 0:
        return None
    idx = delta // BAR_MS
    if idx < 0 or idx >= len(close):
        return None
    if int(open_ms[idx]) != open_t or int(avail[idx]) != int(t_end):
        raise B203Error("1m chronology mismatch at requested bar-end")
    value = float(close[idx])
    if not math.isfinite(value) or value <= 0.0:
        raise B203Error("close at requested bar-end is not a valid price")
    return value


def _complete_5m_close(
    open_ms: np.ndarray,
    avail: np.ndarray,
    close: np.ndarray,
    t_end: int,
) -> float | None:
    if int(t_end) % FIVE_MS != 0:
        return None
    start = int(open_ms[0])
    last_open = int(t_end) - BAR_MS
    delta = last_open - start
    if delta < 0 or delta % BAR_MS != 0:
        return None
    last_idx = delta // BAR_MS
    first_idx = last_idx - (FIVE_MIN - 1)
    if first_idx < 0 or last_idx >= len(close):
        return None
    if int(open_ms[first_idx]) % FIVE_MS != 0:
        return None
    if int(avail[last_idx]) != int(t_end):
        raise B203Error("derived 5m availability is not exact bucket end")
    return float(close[last_idx])


def pre_vol_60(
    open_ms: np.ndarray,
    avail: np.ndarray,
    close: np.ndarray,
    T_ms: int,
) -> float | None:
    """Exactly 60 consecutive 1m log-return energy on [T-60m, T)."""
    t = int(T_ms)
    closes: list[float] = []
    for k in range(VOL_RETURNS + 1):
        end = t - (VOL_RETURNS - k) * BAR_MS
        value = _close_ending_at(open_ms, avail, close, end)
        if value is None:
            return None
        if int(end) > t:
            raise B203Error("PRE_VOL window used a bar after T")
        closes.append(value)
    if len(closes) != VOL_RETURNS + 1:
        raise B203Error("PRE_VOL_60 did not collect exactly 61 closes")
    energy = 0.0
    for i in range(1, VOL_RETURNS + 1):
        left = closes[i - 1]
        right = closes[i]
        if left <= 0.0 or right <= 0.0:
            return None
        ret = math.log(right / left)
        if not math.isfinite(ret):
            return None
        energy += ret * ret
    value = math.sqrt(energy)
    if not math.isfinite(value):
        return None
    return value


def path_log_returns(
    open_ms: np.ndarray,
    avail: np.ndarray,
    close: np.ndarray,
    T_ms: int,
    W: int,
) -> tuple[np.ndarray, float] | None:
    n_bars = PATH_BARS_BY_W[int(W)]
    t = int(T_ms)
    w_ms = int(W) * BAR_MS
    closes: list[float] = []
    for i in range(n_bars + 1):
        end = t - w_ms + i * FIVE_MS
        value = _complete_5m_close(open_ms, avail, close, end)
        if value is None:
            return None
        if end > t:
            raise B203Error("morphology path used a 5m bucket after T")
        closes.append(value)
    returns = np.empty(n_bars, dtype=np.float64)
    for i in range(n_bars):
        left = closes[i]
        right = closes[i + 1]
        if left <= 0.0 or right <= 0.0:
            return None
        ret = math.log(right / left)
        if not math.isfinite(ret):
            return None
        returns[i] = ret
    d_w = math.log(closes[-1] / closes[0])
    if not math.isfinite(d_w):
        return None
    telescoped = float(np.sum(returns))
    if abs(telescoped - d_w) > 1e-12:
        raise B203Error("5m path returns do not telescope to D_W(T)")
    return returns, d_w


def morphology_components(
    returns: np.ndarray,
    d: int,
    d_w: float,
) -> dict[str, float] | None:
    """Four frozen path components. Invalid construction invariants raise."""
    if int(d) not in (DIR_UP, DIR_DOWN):
        raise B203Error("direction sign must be +1 or -1")
    r = np.asarray(returns, dtype=np.float64)
    if r.ndim != 1 or len(r) == 0:
        raise B203Error("morphology returns must be a non-empty 1D path")
    if not np.all(np.isfinite(r)):
        return None
    tv = float(np.sum(np.abs(r)))
    if not math.isfinite(tv) or tv <= 0.0:
        return None
    max_share = float(np.max(np.abs(r)) / tv)
    distributedness = 1.0 - max_share
    signed = float(np.sum(r))
    if not math.isfinite(signed) or abs(signed - float(d_w)) > 1e-12:
        raise B203Error("PATH_EFFICIENCY violated the [0,1] construction invariant")
    path_efficiency = abs(signed) / tv
    if not math.isfinite(path_efficiency) or path_efficiency < 0.0 or path_efficiency > 1.0:
        raise B203Error("PATH_EFFICIENCY violated the [0,1] construction invariant")
    n = len(r)
    directional = 0
    for value in r:
        if float(d) * float(value) > 0.0:
            directional += 1
    directional_bar_share = directional / float(n)
    z = 0.0
    peak = 0.0
    max_countermove = 0.0
    for value in r:
        z += float(d) * float(value)
        if z > peak:
            peak = z
        draw = peak - z
        if draw > max_countermove:
            max_countermove = draw
    ratio = max_countermove / tv
    if not math.isfinite(ratio) or ratio < 0.0 or ratio > 1.0:
        raise B203Error("COUNTERMOVE_RATIO violated the [0,1] construction invariant")
    shallowness = 1.0 - ratio
    out = {
        "tv": tv,
        "distributedness": distributedness,
        "path_efficiency": path_efficiency,
        "directional_bar_share": directional_bar_share,
        "countermove_shallowness": shallowness,
        "max_countermove": max_countermove,
    }
    for name in COMPONENT_NAMES:
        value = float(out[name])
        if not math.isfinite(value):
            return None
        if name != "directional_bar_share" and (value < 0.0 or value > 1.0):
            raise B203Error(f"{name} is outside the construction interval")
        if name == "directional_bar_share" and (value < 0.0 or value > 1.0):
            raise B203Error("DIRECTIONAL_BAR_SHARE is outside [0,1]")
    return out


def _tertile(score: float) -> int:
    if not math.isfinite(score):
        return STATE_MISSING
    if score < 0.0 or score > 1.0:
        raise B203Error("causal score outside [0,1]")
    if score < 1.0 / 3.0:
        return STATE_LOW
    if score < 2.0 / 3.0:
        return STATE_MID
    return STATE_HIGH


def state_label(state: int) -> str:
    if int(state) not in (STATE_LOW, STATE_MID, STATE_HIGH):
        raise B203Error("state is not a frozen tertile")
    return STATE_LABELS[int(state)]


def canonical_event_id(
    *,
    W: int,
    direction: str,
    T_ms: int,
    H: int,
    snapshot_id: str = REQUIRED_SNAPSHOT,
) -> str:
    if direction not in {"UP", "DOWN"}:
        raise B203Error("canonical event direction must be UP or DOWN")
    w = int(W)
    h = int(H)
    t = int(T_ms)
    window_start = t - w * BAR_MS
    window_end = t
    return "|".join(
        (
            str(snapshot_id),
            "1m",
            "5m",
            "1h",
            str(w),
            str(direction),
            str(window_start),
            str(window_end),
            str(t),
            str(h),
        )
    )


def baseline_stratum_id(
    *,
    W: int,
    direction: str,
    displacement_mag_state: str,
    vol_state: str,
) -> str:
    if direction not in {"UP", "DOWN"}:
        raise B203Error("stratum direction must be UP or DOWN")
    for label in (displacement_mag_state, vol_state):
        if label not in STATE_LABELS:
            raise B203Error("stratum state must be LOW, MID, or HIGH")
    return "|".join(
        (
            str(int(W)),
            str(direction),
            str(displacement_mag_state),
            str(vol_state),
        )
    )


def seed_int(parts: Sequence[object]) -> int:
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:16], 16)


def _year_from_ms(value: int) -> int:
    return int(
        np.datetime64(int(value), "ms")
        .astype("datetime64[Y]")
        .astype(int)
    ) + 1970


def _month_key(value: int) -> int:
    return int(
        np.datetime64(int(value), "ms")
        .astype("datetime64[M]")
        .astype(int)
    )


def _week_key(value: int) -> int:
    day = int(value) // DAY_MS
    return (day + 3) // 7


def _purge(queue: deque, cutoff: int) -> None:
    while queue and int(queue[0][0]) < cutoff:
        queue.popleft()


def _iter_hourly_grid(
    frame: Mapping[str, np.ndarray],
) -> list[tuple[int, float | None]]:
    """Every hourly decision-grid T within bounds, with its own PRE_VOL_60(T).

    This is the single source of truth for the hourly grid iteration bounds,
    shared by `construct_events` (which additionally requires a qualifying
    D_W(T)!=0 per W to admit a (T,W) event) and `construct_hourly_vol_grid`
    (which requires only grid membership, matching the frozen §7.3 VOL_STATE
    reference population). Neither caller may derive the grid from the other's
    output: event admission and the hourly volatility reference population are
    two different frozen populations that must not be conflated.
    """
    open_ms = np.asarray(frame["open_time_ms"], dtype=np.int64)
    avail = np.asarray(frame["available_at_ms"], dtype=np.int64)
    close = np.asarray(frame["close"], dtype=np.float64)
    first_avail = int(avail[0])
    last_avail = int(avail[-1])
    t = ((first_avail + HOUR_MS - 1) // HOUR_MS) * HOUR_MS
    if t < first_avail:
        t += HOUR_MS
    grid: list[tuple[int, float | None]] = []
    while t <= last_avail and t < DEV_END_MS:
        if t < WARMUP_START_MS:
            t += HOUR_MS
            continue
        vol = pre_vol_60(open_ms, avail, close, t)
        grid.append((int(t), vol))
        t += HOUR_MS
    return grid


def construct_hourly_vol_grid(
    frame: Mapping[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    """The frozen §7.3 VOL_STATE reference population: every hourly grid T
    whose own PRE_VOL_60(T) is available, independent of whether any (T,W)
    event exists at that T. A T with no qualifying (T,W) event still occupies
    a reference slot here as long as its PRE_VOL_60 is itself computable --
    that is the population/decision-reference separation this function
    exists to fix.

    A T whose PRE_VOL_60 is itself unavailable (e.g. inside the first 60
    minutes of the frame, where no bar's `available_at` equals T-60m) is
    excluded outright rather than included as a NaN-poisoning slot: PRE_VOL
    availability is a mechanical function of frame coverage, not a qualifying
    event whose later unavailability must poison every subsequent 30-day
    lookback window. Poisoning every reference for 30 days after one
    structurally-unavailable leading grid point would be a materially larger
    and unintended behavior change, not a minimal fix of the population
    mismatch this function targets.
    """
    validate_1m_frame(frame)
    grid = [(t, vol) for t, vol in _iter_hourly_grid(frame) if vol is not None]
    times = np.asarray([t for t, _ in grid], dtype=np.int64)
    values = np.asarray([vol for _, vol in grid], dtype=np.float64)
    return times, values


def construct_events(frame: Mapping[str, np.ndarray]) -> list[dict[str, object]]:
    """Hourly (T,W) events. Morphology state is not an admission gate."""
    validate_1m_frame(frame)
    open_ms = np.asarray(frame["open_time_ms"], dtype=np.int64)
    avail = np.asarray(frame["available_at_ms"], dtype=np.int64)
    close = np.asarray(frame["close"], dtype=np.float64)
    events: list[dict[str, object]] = []
    for t, vol in _iter_hourly_grid(frame):
        for W in W_VALUES:
            path = path_log_returns(open_ms, avail, close, t, W)
            if path is None or vol is None:
                continue
            returns, d_w = path
            if d_w == 0.0 or not math.isfinite(d_w):
                continue
            d = 1 if d_w > 0.0 else -1
            events.append(
                {
                    "T": int(t),
                    "W": int(W),
                    "d": int(d),
                    "direction": DIR_LABELS[d],
                    "D_W": float(d_w),
                    "abs_disp": abs(float(d_w)),
                    "pre_vol": float(vol),
                    "returns": np.asarray(returns, dtype=np.float64),
                    "warmup_only": bool(t < DEV_START_MS),
                }
            )
    return events


def _causal_tertile_states(
    values: np.ndarray,
    times: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    scores = rolling_midrank_percentile(
        np.asarray(values, dtype=np.float64),
        timestamps_ms=np.asarray(times, dtype=np.int64),
        lookback_ms=REF_MS,
    )
    out = np.full(len(scores), STATE_MISSING, dtype=np.int8)
    for i, score in enumerate(scores):
        out[i] = _tertile(float(score))
    return out, scores


def attach_states(
    events: Sequence[Mapping[str, object]],
    frame: Mapping[str, np.ndarray],
) -> list[dict[str, object]]:
    """Attach causal MAG/VOL/morphology states.

    `frame` is required so the VOL_STATE causal reference population can be
    built from the full hourly decision grid (frozen §7.3), independent of
    which hourly points happened to produce a (T,W) event. Deriving the VOL
    reference from `events` alone would silently drop any hourly T whose
    PRE_VOL_60 is valid but every W's D_W(T) is exactly zero -- conflating
    event-admission population with decision-reference population.
    """
    out = [dict(event) for event in events]
    if not out:
        return out

    vol_times, vol_values = construct_hourly_vol_grid(frame)
    vol_states, vol_scores = _causal_tertile_states(vol_values, vol_times)
    vol_state_by_t = {
        int(t): int(state) for t, state in zip(vol_times, vol_states)
    }
    vol_score_by_t = {
        int(t): float(score) for t, score in zip(vol_times, vol_scores)
    }

    for event in out:
        t = int(event["T"])
        if t not in vol_state_by_t:
            raise B203Error(
                "constructed event T is not a member of the hourly VOL grid"
            )
        event["vol_state"] = vol_state_by_t[t]
        event["vol_score"] = vol_score_by_t[t]

    for W in W_VALUES:
        positions = [i for i, event in enumerate(out) if int(event["W"]) == W]
        if not positions:
            continue
        times = np.asarray([int(out[i]["T"]) for i in positions], dtype=np.int64)
        mag = np.asarray([float(out[i]["abs_disp"]) for i in positions], dtype=np.float64)
        mag_states, mag_scores = _causal_tertile_states(mag, times)
        for pos, state, score in zip(positions, mag_states, mag_scores):
            out[pos]["mag_state"] = int(state)
            out[pos]["mag_score"] = float(score)

        component_raw: dict[str, list[float]] = {name: [] for name in COMPONENT_NAMES}
        valid_positions: list[int] = []
        for pos in positions:
            event = out[pos]
            computed = morphology_components(
                event["returns"],
                int(event["d"]),
                float(event["D_W"]),
            )
            if computed is None:
                event["morphology_unavailable"] = True
                continue
            event["morphology_unavailable"] = False
            event.update(computed)
            valid_positions.append(pos)
            for name in COMPONENT_NAMES:
                component_raw[name].append(float(computed[name]))

        if valid_positions:
            path_times = np.asarray(
                [int(out[i]["T"]) for i in valid_positions],
                dtype=np.int64,
            )
            component_scores: list[np.ndarray] = []
            for name in COMPONENT_NAMES:
                raw = np.asarray(component_raw[name], dtype=np.float64)
                scores = rolling_midrank_percentile(
                    raw,
                    timestamps_ms=path_times,
                    lookback_ms=REF_MS,
                )
                component_scores.append(scores)
                for pos, score in zip(valid_positions, scores):
                    out[pos][f"pctl_{name}"] = float(score)
            matrix = np.vstack(component_scores)
            mean_scores = np.mean(matrix, axis=0)
            for column, pos in enumerate(valid_positions):
                if np.all(np.isfinite(matrix[:, column])):
                    out[pos]["morphology_score"] = float(mean_scores[column])
                    out[pos]["morphology_state"] = _tertile(float(mean_scores[column]))
                else:
                    out[pos]["morphology_score"] = float("nan")
                    out[pos]["morphology_state"] = STATE_MISSING
        for pos in positions:
            out[pos].setdefault("morphology_unavailable", True)
            out[pos].setdefault("morphology_score", float("nan"))
            out[pos].setdefault("morphology_state", STATE_MISSING)
            out[pos].setdefault("mag_state", STATE_MISSING)
            out[pos].setdefault("vol_state", STATE_MISSING)
    return out


def _past_median_abs_ret(
    open_ms: np.ndarray,
    avail: np.ndarray,
    close: np.ndarray,
    T_ms: int,
    H: int,
    cache: dict[tuple[int, int], float | None] | None = None,
) -> float | None:
    """Median abs H-return on the UTC 15m grid over the prior 30d, known by T.

    Scale depends only on `(T, H)`, not on W. Callers may pass a shared cache
    so the 15 cells reuse the same `(T, H)` denominator on one frame. The cache
    is not a frame fingerprint and must not be reused across different frames.
    Missing bars stay unavailable; a present but invalid close fails closed.
    """
    key = (int(T_ms), int(H))
    if cache is not None and key in cache:
        return cache[key]
    t = key[0]
    h_ms = key[1] * BAR_MS
    window_start = t - REF_MS
    last_ref = t - h_ms
    if last_ref < window_start:
        if cache is not None:
            cache[key] = None
        return None
    first_grid = ((window_start + SCALE_GRID_MS - 1) // SCALE_GRID_MS) * SCALE_GRID_MS
    if first_grid > last_ref:
        if cache is not None:
            cache[key] = None
        return None
    n_refs = ((last_ref - first_grid) // SCALE_GRID_MS) + 1
    refs = first_grid + np.arange(n_refs, dtype=np.int64) * SCALE_GRID_MS
    frame_start = int(open_ms[0])
    n_bars = int(len(close))
    left_idx = (refs - BAR_MS - frame_start) // BAR_MS
    right_idx = (refs + h_ms - BAR_MS - frame_start) // BAR_MS
    valid = (
        (left_idx >= 0)
        & (left_idx < n_bars)
        & (right_idx >= 0)
        & (right_idx < n_bars)
    )
    if not np.any(valid):
        if cache is not None:
            cache[key] = None
        return None
    chosen_refs = refs[valid]
    chosen_left = left_idx[valid]
    chosen_right = right_idx[valid]
    if np.any(open_ms[chosen_left] != chosen_refs - BAR_MS) or np.any(
        avail[chosen_left] != chosen_refs
    ):
        raise B203Error("1m chronology mismatch at requested bar-end")
    if np.any(open_ms[chosen_right] != chosen_refs + h_ms - BAR_MS) or np.any(
        avail[chosen_right] != chosen_refs + h_ms
    ):
        raise B203Error("1m chronology mismatch at requested bar-end")
    left = close[chosen_left]
    right = close[chosen_right]
    if not (
        np.all(np.isfinite(left))
        and np.all(np.isfinite(right))
        and np.all(left > 0.0)
        and np.all(right > 0.0)
    ):
        raise B203Error("close at requested bar-end is not a valid price")
    values = np.abs(np.log(right / left))
    if len(values) == 0 or not np.all(np.isfinite(values)):
        raise B203Error("close at requested bar-end is not a valid price")
    median = float(np.median(values))
    out = median if math.isfinite(median) and median > 0.0 else None
    if cache is not None:
        cache[key] = out
    return out


def _dir_ret_h(
    open_ms: np.ndarray,
    avail: np.ndarray,
    close: np.ndarray,
    T_ms: int,
    H: int,
    d: int,
) -> float | None:
    t = int(T_ms)
    h_ms = int(H) * BAR_MS
    left = _close_ending_at(open_ms, avail, close, t)
    right = _close_ending_at(open_ms, avail, close, t + h_ms)
    if left is None or right is None:
        return None
    ret = float(d) * math.log(right / left)
    if not math.isfinite(ret):
        return None
    return ret


def _attach_targets(
    events: Sequence[Mapping[str, object]],
    frame: Mapping[str, np.ndarray],
    H: int,
    scale_cache: dict[tuple[int, int], float | None] | None = None,
) -> list[dict[str, object]]:
    open_ms = np.asarray(frame["open_time_ms"], dtype=np.int64)
    avail = np.asarray(frame["available_at_ms"], dtype=np.int64)
    close = np.asarray(frame["close"], dtype=np.float64)
    cache = scale_cache if scale_cache is not None else {}
    out: list[dict[str, object]] = []
    for event in events:
        record = dict(event)
        t = int(record["T"])
        d = int(record["d"])
        dir_ret = _dir_ret_h(open_ms, avail, close, t, H, d)
        scale = _past_median_abs_ret(open_ms, avail, close, t, H, cache=cache)
        if (
            dir_ret is None
            or scale is None
            or not math.isfinite(dir_ret)
            or not math.isfinite(scale)
            or scale <= 0.0
        ):
            record["Y"] = float("nan")
            record["target_available"] = False
        else:
            record["Y"] = float(dir_ret / scale)
            record["target_available"] = True
        record["H"] = int(H)
        out.append(record)
    return out


def _decision_ready(event: Mapping[str, object]) -> bool:
    return (
        int(event.get("mag_state", STATE_MISSING)) >= 0
        and int(event.get("vol_state", STATE_MISSING)) >= 0
        and int(event.get("morphology_state", STATE_MISSING)) >= 0
        and bool(event.get("target_available"))
        and math.isfinite(float(event.get("Y", float("nan"))))
    )


def _week_bootstrap_interval(
    improvements: np.ndarray,
    times: np.ndarray,
    W: int,
    H: int,
) -> tuple[float, float]:
    if len(improvements) == 0:
        return float("nan"), float("nan")
    groups: dict[int, list[float]] = defaultdict(list)
    for value, t in zip(improvements, times):
        groups[_week_key(int(t))].append(float(value))
    keys = sorted(groups)
    sums = np.asarray([sum(groups[key]) for key in keys], dtype=np.float64)
    counts = np.asarray([len(groups[key]) for key in keys], dtype=np.int64)
    if len(keys) == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed_int((SEED_BOOT, int(W), int(H))))
    draws = np.empty(N_BOOT, dtype=np.float64)
    for rep in range(N_BOOT):
        sampled = rng.integers(0, len(keys), size=len(keys))
        denom = int(np.sum(counts[sampled]))
        draws[rep] = (
            float(np.sum(sums[sampled]) / denom)
            if denom > 0
            else float("nan")
        )
    finite = draws[np.isfinite(draws)]
    if len(finite) == 0:
        return float("nan"), float("nan")
    return (
        float(np.quantile(finite, 0.025)),
        float(np.quantile(finite, 0.975)),
    )


def _side_mean(records: Sequence[Mapping[str, object]], direction: str) -> float:
    values = [
        float(record["ae_improvement"])
        for record in records
        if str(record["direction"]) == direction
    ]
    if not values:
        return float("nan")
    return float(np.mean(np.asarray(values, dtype=np.float64)))


def _morphology_separation(
    records: Sequence[Mapping[str, object]],
    direction: str | None = None,
) -> float:
    subset = records
    if direction is not None:
        subset = [record for record in records if str(record["direction"]) == direction]
    high = [
        float(record["base_residual"])
        for record in subset
        if int(record["morphology_state"]) == STATE_HIGH
    ]
    low = [
        float(record["base_residual"])
        for record in subset
        if int(record["morphology_state"]) == STATE_LOW
    ]
    if not high or not low:
        return float("nan")
    return float(np.median(np.asarray(high, dtype=np.float64)) - np.median(np.asarray(low, dtype=np.float64)))


def per_cell_gates(
    *,
    mean_improvement: float,
    up_mean: float,
    down_mean: float,
    relative: float,
    bootstrap_lower: float,
    placebo_q95: float,
    sep_pooled: float,
    sep_up: float,
    sep_down: float,
) -> dict[str, bool]:
    """Frozen five per-cell operators. Zero is not positive. NaN is not pass."""
    return {
        "primary_positive": bool(
            math.isfinite(mean_improvement)
            and math.isfinite(up_mean)
            and math.isfinite(down_mean)
            and mean_improvement > 0.0
            and up_mean > 0.0
            and down_mean > 0.0
        ),
        "material_relative_mae": bool(
            math.isfinite(relative) and relative >= RELATIVE_MAE_MIN
        ),
        "bootstrap_positive": bool(
            math.isfinite(bootstrap_lower) and bootstrap_lower > 0.0
        ),
        "placebo_separation": bool(
            math.isfinite(mean_improvement)
            and math.isfinite(placebo_q95)
            and mean_improvement > placebo_q95
        ),
        "morphology_ordering": bool(
            math.isfinite(sep_pooled)
            and math.isfinite(sep_up)
            and math.isfinite(sep_down)
            and sep_pooled > 0.0
            and sep_up > 0.0
            and sep_down > 0.0
        ),
    }


def _support_diagnostics(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    times = [int(record["T"]) for record in records]
    months: dict[int, int] = defaultdict(int)
    mag_counts: dict[str, int] = defaultdict(int)
    vol_counts: dict[str, int] = defaultdict(int)
    morph_counts: dict[str, int] = defaultdict(int)
    for record in records:
        months[_month_key(int(record["T"]))] += 1
        mag_counts[state_label(int(record["mag_state"]))] += 1
        vol_counts[state_label(int(record["vol_state"]))] += 1
        morph_counts[state_label(int(record["morphology_state"]))] += 1
    counts = sorted(months.values(), reverse=True)
    n = len(records)
    return {
        "unique_utc_days": len({t // DAY_MS for t in times}),
        "unique_utc_weeks": len({_week_key(t) for t in times}),
        "unique_utc_months": len(months),
        "largest_month_support_share": (
            counts[0] / n if n and counts else None
        ),
        "top5_month_support_share": (
            sum(counts[:5]) / n if n and counts else None
        ),
        "baseline_state_counts": {
            "displacement_mag": dict(mag_counts),
            "vol": dict(vol_counts),
        },
        "morphology_state_counts": dict(morph_counts),
    }


def evaluate_cell(
    events: Sequence[Mapping[str, object]],
    frame: Mapping[str, np.ndarray],
    W: int,
    H: int,
    scale_cache: dict[tuple[int, int], float | None] | None = None,
) -> dict[str, object]:
    """Score one frozen (W, H) cell.

    `scale_cache` is keyed only by `(T, H)` and is valid for one in-memory
    frame. `evaluate_b2_03` creates a fresh cache per authorized frame.
    Do not reuse a cache across different frames.
    """
    targeted = _attach_targets(
        [event for event in events if int(event["W"]) == int(W)],
        frame,
        int(H),
        scale_cache=scale_cache,
    )
    constructed = len(targeted)
    ready = [
        event
        for event in targeted
        if _decision_ready(event) and math.isfinite(float(event["Y"]))
    ]
    ready.sort(key=lambda item: (int(item["T"]), str(item["direction"])))
    baseline_queues: dict[tuple[object, ...], deque] = defaultdict(deque)
    candidate_queues: dict[tuple[object, ...], deque] = defaultdict(deque)
    scored: list[dict[str, object]] = []
    placebo_sums = np.zeros(N_PLACEBO, dtype=np.float64)
    mature = 0
    h_ms = int(H) * BAR_MS

    for event in ready:
        current_t = int(event["T"])
        while mature < len(ready) and int(ready[mature]["T"]) + h_ms <= current_t:
            previous = ready[mature]
            item = (
                int(previous["T"]),
                float(previous["Y"]),
                state_label(int(previous["morphology_state"])),
                str(previous["direction"]),
                int(previous["W"]),
                canonical_event_id(
                    W=int(previous["W"]),
                    direction=str(previous["direction"]),
                    T_ms=int(previous["T"]),
                    H=int(H),
                ),
            )
            base_key = (
                int(previous["W"]),
                str(previous["direction"]),
                state_label(int(previous["mag_state"])),
                state_label(int(previous["vol_state"])),
            )
            candidate_key = (*base_key, state_label(int(previous["morphology_state"])))
            baseline_queues[base_key].append(item)
            candidate_queues[candidate_key].append(item)
            mature += 1

        if not scoring_eligible(current_t, H):
            continue
        base_key = (
            int(event["W"]),
            str(event["direction"]),
            state_label(int(event["mag_state"])),
            state_label(int(event["vol_state"])),
        )
        candidate_key = (*base_key, state_label(int(event["morphology_state"])))
        base_queue = baseline_queues[base_key]
        candidate_queue = candidate_queues[candidate_key]
        cutoff = current_t - TRAIN_MS
        _purge(base_queue, cutoff)
        _purge(candidate_queue, cutoff)
        if (
            len(base_queue) < BASELINE_MIN_COUNT
            or len(candidate_queue) < CANDIDATE_MIN_COUNT
        ):
            continue
        base_y = np.asarray([float(item[1]) for item in base_queue], dtype=np.float64)
        cand_y = np.asarray([float(item[1]) for item in candidate_queue], dtype=np.float64)
        base_pred = float(np.median(base_y))
        cand_pred = float(np.median(cand_y))
        y = float(event["Y"])
        if not (math.isfinite(base_pred) and math.isfinite(cand_pred) and math.isfinite(y)):
            continue
        base_ae = abs(y - base_pred)
        cand_ae = abs(y - cand_pred)
        record = dict(event)
        event_id = canonical_event_id(
            W=int(W),
            direction=str(event["direction"]),
            T_ms=current_t,
            H=int(H),
        )
        record.update(
            {
                "event_id": event_id,
                "base_pred": base_pred,
                "candidate_pred": cand_pred,
                "base_ae": base_ae,
                "candidate_ae": cand_ae,
                "ae_improvement": base_ae - cand_ae,
                "base_residual": y - base_pred,
                "baseline_count": len(base_queue),
                "candidate_count": len(candidate_queue),
            }
        )
        scored.append(record)
        sorted_base_items = sorted(base_queue, key=lambda item: str(item[5]))
        sorted_base_y = np.asarray(
            [float(item[1]) for item in sorted_base_items],
            dtype=np.float64,
        )
        sorted_base_labels = np.asarray([str(item[2]) for item in sorted_base_items])
        evaluation_state = state_label(int(event["morphology_state"]))
        stratum = baseline_stratum_id(
            W=int(W),
            direction=str(event["direction"]),
            displacement_mag_state=state_label(int(event["mag_state"])),
            vol_state=state_label(int(event["vol_state"])),
        )
        for rep in range(N_PLACEBO):
            rng = np.random.default_rng(
                seed_int((SEED_PLACEBO, rep, int(W), int(H), current_t, stratum))
            )
            permuted_labels = rng.permutation(sorted_base_labels)
            chosen_y = sorted_base_y[permuted_labels == evaluation_state]
            if len(chosen_y) == 0:
                placebo_sums[rep] = float("nan")
                continue
            placebo_pred = float(np.median(chosen_y))
            placebo_sums[rep] += base_ae - abs(y - placebo_pred)

    improvements = np.asarray(
        [float(record["ae_improvement"]) for record in scored],
        dtype=np.float64,
    )
    base_ae = np.asarray([float(record["base_ae"]) for record in scored], dtype=np.float64)
    cand_ae = np.asarray(
        [float(record["candidate_ae"]) for record in scored],
        dtype=np.float64,
    )
    times = np.asarray([int(record["T"]) for record in scored], dtype=np.int64)
    mean_improvement = float(np.mean(improvements)) if len(improvements) else float("nan")
    median_improvement = (
        float(np.median(improvements)) if len(improvements) else float("nan")
    )
    mean_base = float(np.mean(base_ae)) if len(base_ae) else float("nan")
    mean_cand = float(np.mean(cand_ae)) if len(cand_ae) else float("nan")
    relative = (
        1.0 - mean_cand / mean_base
        if math.isfinite(mean_base) and mean_base > 0.0 and math.isfinite(mean_cand)
        else float("nan")
    )
    ci_low, ci_high = _week_bootstrap_interval(improvements, times, W, H)
    up_mean = _side_mean(scored, "UP")
    down_mean = _side_mean(scored, "DOWN")
    sep_pooled = _morphology_separation(scored)
    sep_up = _morphology_separation(scored, "UP")
    sep_down = _morphology_separation(scored, "DOWN")
    placebo_means = (
        placebo_sums / len(scored)
        if len(scored)
        else np.full(N_PLACEBO, np.nan, dtype=np.float64)
    )
    placebo_finite = placebo_means[np.isfinite(placebo_means)]
    placebo_q95 = (
        float(np.quantile(placebo_finite, PLACEBO_Q))
        if len(placebo_finite)
        else float("nan")
    )
    yearly: dict[str, float | None] = {}
    positive_years = 0
    for year in YEAR_BLOCKS:
        values = np.asarray(
            [
                float(record["ae_improvement"])
                for record in scored
                if _year_from_ms(int(record["T"])) == year
            ],
            dtype=np.float64,
        )
        mean_year = float(np.mean(values)) if len(values) else float("nan")
        yearly[str(year)] = mean_year if math.isfinite(mean_year) else None
        if math.isfinite(mean_year) and mean_year > 0.0:
            positive_years += 1

    up_n = sum(1 for record in scored if str(record["direction"]) == "UP")
    down_n = sum(1 for record in scored if str(record["direction"]) == "DOWN")
    gates = per_cell_gates(
        mean_improvement=mean_improvement,
        up_mean=up_mean,
        down_mean=down_mean,
        relative=relative,
        bootstrap_lower=ci_low,
        placebo_q95=placebo_q95,
        sep_pooled=sep_pooled,
        sep_up=sep_up,
        sep_down=sep_down,
    )
    event_ids = [str(record["event_id"]) for record in scored]
    support = _support_diagnostics(scored)
    return {
        "W": int(W),
        "H": int(H),
        "N": len(scored),
        "constructed_events": constructed,
        "UP_count": up_n,
        "DOWN_count": down_n,
        "unique_utc_days": support["unique_utc_days"],
        "unique_utc_weeks": support["unique_utc_weeks"],
        "unique_utc_months": support["unique_utc_months"],
        "largest_month_support_share": support["largest_month_support_share"],
        "top5_month_support_share": support["top5_month_support_share"],
        "baseline_state_counts": support["baseline_state_counts"],
        "morphology_state_counts": support["morphology_state_counts"],
        "mean_ae_improvement": mean_improvement if math.isfinite(mean_improvement) else None,
        "median_ae_improvement": (
            median_improvement if math.isfinite(median_improvement) else None
        ),
        "relative_mae_improvement": relative if math.isfinite(relative) else None,
        "bootstrap_lower_95": ci_low if math.isfinite(ci_low) else None,
        "bootstrap_upper_95": ci_high if math.isfinite(ci_high) else None,
        "morphology_separation_pooled": sep_pooled if math.isfinite(sep_pooled) else None,
        "morphology_separation_up": sep_up if math.isfinite(sep_up) else None,
        "morphology_separation_down": sep_down if math.isfinite(sep_down) else None,
        "placebo_q95": placebo_q95 if math.isfinite(placebo_q95) else None,
        "placebo_replicate_count_nominal": int(N_PLACEBO),
        "placebo_replicate_count_finite": int(len(placebo_finite)),
        "up": {
            "N": up_n,
            "mean_ae_improvement": up_mean if math.isfinite(up_mean) else None,
            "morphology_separation_up": sep_up if math.isfinite(sep_up) else None,
        },
        "down": {
            "N": down_n,
            "mean_ae_improvement": down_mean if math.isfinite(down_mean) else None,
            "morphology_separation_down": sep_down if math.isfinite(sep_down) else None,
        },
        "anti_rescue": {
            "primary_positive_requires_pooled_up_down": True,
            "morphology_ordering_requires_pooled_up_down": True,
            "up_mean_ae_improvement": up_mean if math.isfinite(up_mean) else None,
            "down_mean_ae_improvement": down_mean if math.isfinite(down_mean) else None,
            "morphology_separation_up": sep_up if math.isfinite(sep_up) else None,
            "morphology_separation_down": sep_down if math.isfinite(sep_down) else None,
        },
        "yearly_2020_2024_mean_ae_improvement": yearly,
        "positive_years": positive_years,
        "year_stability_pass": bool(positive_years >= 4),
        "per_cell_gates": gates,
        "support": support,
        "event_ids": event_ids,
        "scored": scored,
    }


def _cell_five_pass(cell: Mapping[str, object]) -> bool:
    gates = cell.get("per_cell_gates")
    if not isinstance(gates, Mapping):
        return False
    return all(gates.get(name) is True for name in PER_CELL_GATE_NAMES)


def determine_promotion_gates(
    cells: Sequence[Mapping[str, object]],
) -> tuple[dict[str, bool], list[dict[str, object]]]:
    by_key = {
        (int(cell["W"]), int(cell["H"])): cell
        for cell in cells
        if "W" in cell and "H" in cell
    }
    per_gate_evidence = {name: False for name in PER_CELL_GATE_NAMES}
    horizon_robustness = False
    parameter_robustness = False
    year_stability = False
    neighborhoods: list[dict[str, object]] = []

    for h1, h2 in ADJACENT_H_PAIRS:
        per_gate_W: dict[str, list[int]] = {name: [] for name in PER_CELL_GATE_NAMES}
        core_W: list[int] = []
        stable_W: list[int] = []
        for W in W_VALUES:
            c1 = by_key.get((W, h1))
            c2 = by_key.get((W, h2))
            if c1 is None or c2 is None:
                continue
            for name in PER_CELL_GATE_NAMES:
                g1 = c1.get("per_cell_gates")
                g2 = c2.get("per_cell_gates")
                if (
                    isinstance(g1, Mapping)
                    and isinstance(g2, Mapping)
                    and g1.get(name) is True
                    and g2.get(name) is True
                ):
                    per_gate_W[name].append(int(W))
            if _cell_five_pass(c1) and _cell_five_pass(c2):
                horizon_robustness = True
                core_W.append(int(W))
                if (
                    c1.get("year_stability_pass") is True
                    and c2.get("year_stability_pass") is True
                ):
                    stable_W.append(int(W))
        for name, passing in per_gate_W.items():
            if len(passing) >= 2:
                per_gate_evidence[name] = True
        if len(core_W) >= 2:
            parameter_robustness = True
        if len(stable_W) >= 2:
            year_stability = True
            neighborhoods.append(
                {
                    "H_pair": [h1, h2],
                    "W": list(stable_W),
                    "cells": [
                        {"W": W, "H": h}
                        for W in stable_W
                        for h in (h1, h2)
                    ],
                }
            )

    neighborhoods.sort(key=lambda item: (item["H_pair"], item["W"]))
    gates = {
        **per_gate_evidence,
        "horizon_robustness": horizon_robustness,
        "parameter_robustness": parameter_robustness,
        "year_stability": year_stability,
    }
    return gates, neighborhoods


def evaluate_b2_03(frame_1m: Mapping[str, np.ndarray]) -> dict[str, object]:
    validate_1m_frame(frame_1m)
    raw_events = construct_events(frame_1m)
    events = attach_states(raw_events, frame_1m)
    scale_cache: dict[tuple[int, int], float | None] = {}
    cells = [
        evaluate_cell(events, frame_1m, W, H, scale_cache=scale_cache)
        for W in W_VALUES
        for H in H_VALUES
    ]
    for cell in cells:
        cell.pop("scored", None)
    gates, neighborhoods = determine_promotion_gates(cells)
    passed = bool(neighborhoods) and all(gates.get(name) is True for name in GATE_NAMES)
    return {
        "hypothesis_id": HYPOTHESIS_ID,
        "dataset_id": DATASET_ID,
        "snapshot_id": REQUIRED_SNAPSHOT,
        "search_surface": {
            "impulse_windows_minutes": list(W_VALUES),
            "horizons_minutes": list(H_VALUES),
            "primary_cells": PRIMARY_CELLS,
        },
        "windows": {
            "warmup_start_inclusive_ms": WARMUP_START_MS,
            "development_start_inclusive_ms": DEV_START_MS,
            "development_end_exclusive_ms": DEV_END_MS,
            "last_legal_T_by_horizon_minutes": dict(LAST_LEGAL_T_MS),
            "validation_2025_untouched": True,
            "oos_2026_untouched": True,
        },
        "constructed_events": len(raw_events),
        "cells": cells,
        "promotion": {
            "gates": gates,
            "qualifying_neighborhoods": neighborhoods,
            "passed": passed,
            "verdict": (
                "B2_03_PROMOTED_CANDIDATE"
                if passed
                else "B2_03_CLOSED_NO_PROMOTION"
            ),
        },
    }
