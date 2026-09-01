"""Outcome-blind B2-02 boundary-interaction implementation.

Implements the frozen B2-02 preregistration using only synthetic fixtures during
the implementation-review stage. Real CORE outcomes are reachable only through
the canonical Batch02 runner after exact-SHA authorization.

This module deliberately does not use `from __future__ import annotations`:
the merged Batch02 static source policy default-denies every non-repository
import that is not on its explicit transform allowlist, and B2-02 source is
adapted to that bounded policy rather than the policy being widened. Python
3.11 evaluates the annotations used here natively.
"""

import hashlib
import math
from collections import defaultdict, deque
from decimal import Decimal
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from scripts.research.lib.batch02_contracts import rolling_midrank_percentile


HYPOTHESIS_ID = "B2-02_BOUNDARY_INTERACTION_PATH"
DATASET_ID = "CORE_BTC_BINANCE_V0"
REQUIRED_SNAPSHOT = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"

BAR_MS = 60_000
FIVE_MIN = 5
FIVE_MS = FIVE_MIN * BAR_MS
DAY_MS = 24 * 60 * BAR_MS
PATH_MIN = 30
PATH_BARS = PATH_MIN // FIVE_MIN
PATH_MS = PATH_MIN * BAR_MS
REF_DAYS = 30
REF_MS = REF_DAYS * DAY_MS
TRAIN_DAYS = 90
TRAIN_MS = TRAIN_DAYS * DAY_MS

LOOKBACKS = (60, 120, 240)
HORIZONS = (30, 60, 120, 240)
ADJACENT_H_PAIRS = ((30, 60), (60, 120), (120, 240))
YEAR_BLOCKS = (2020, 2021, 2022, 2023, 2024)

BASELINE_MIN_COUNT = 80
CANDIDATE_MIN_COUNT = 40
RELATIVE_MAE_MIN = 0.02
PLACEBO_Q = 0.95
N_PLACEBO = 100
N_BOOT = 2000
SEED_PLACEBO = 20260902
SEED_BOOT = 20260903

WARMUP_START_MS = 1_577_836_800_000
DEV_START_MS = 1_580_515_200_000
DEV_END_MS = 1_735_689_600_000
LAST_T0_MS = 1_735_673_100_000
LAST_T_MS = LAST_T0_MS + PATH_MS

# Reserved-validation and untouched-OOS boundaries (prereg section 3). These are
# used only to PROVE, from the authorized view and the already-loaded
# development bytes, that neither window was reached. Nothing in this module
# ever enumerates, opens, or reads a partition in those windows.
VALIDATION_2025_START_MS = DEV_END_MS
OOS_2026_START_MS = 1_767_225_600_000
FIRST_FORBIDDEN_YEAR = 2025

DIR_UPPER = 1
DIR_LOWER = -1
STATE_LOW = 0
STATE_MID = 1
STATE_HIGH = 2
STATE_MISSING = -1

GATE_NAMES = (
    "primary_positive",
    "material_relative_mae",
    "bootstrap_positive",
    "placebo_separation",
    "path_ordering",
    "horizon_robustness",
    "parameter_robustness",
    "year_stability",
)
PER_CELL_GATE_NAMES = GATE_NAMES[:5]


class B202Error(RuntimeError):
    """B2-02 implementation input/invariant error."""


def _finite_price(value: object, label: str) -> float:
    try:
        out = float(Decimal(str(value)))
    except Exception as exc:
        raise B202Error(f"{label} is not a valid decimal price") from exc
    if not math.isfinite(out) or out <= 0.0:
        raise B202Error(f"{label} must be finite and > 0")
    return out


def table_to_1m_frame(table: object) -> dict[str, np.ndarray]:
    """Convert an authorized Arrow table without any direct file access."""
    columns = ("open_time_ms", "available_at_ms", "open", "high", "low", "close")
    values: dict[str, np.ndarray] = {}
    for name in columns:
        try:
            column = table.column(name)
        except Exception as exc:
            raise B202Error(f"authorized table missing canonical column {name}") from exc
        # In-memory Arrow -> NumPy conversion only. `to_numpy` is on the merged
        # Batch02 source policy's explicit in-memory conversion allowlist; the
        # previously used `to_pylist` is not, and B2-02 source is adapted to the
        # bounded policy rather than the policy being widened for B2-02.
        try:
            raw = column.to_numpy(zero_copy_only=False)
        except Exception as exc:
            raise B202Error(
                f"authorized column {name} is not convertible in memory"
            ) from exc
        if name in {"open_time_ms", "available_at_ms"}:
            try:
                values[name] = np.asarray(raw, dtype=np.int64)
            except (TypeError, ValueError) as exc:
                raise B202Error(
                    f"authorized column {name} is not integer milliseconds"
                ) from exc
        else:
            values[name] = np.asarray(
                [_finite_price(v, name) for v in raw],
                dtype=np.float64,
            )
    validate_1m_frame(values)
    return values


def _partition_year(relative_path: str) -> int:
    """Year encoded in an authorized monthly partition's relative path."""
    leaf = str(relative_path).rsplit("/", 1)[-1]
    head = leaf.split("-", 1)[0]
    if len(head) != 4 or not head.isdigit():
        raise B202Error(
            f"authorized partition path is not a canonical monthly leaf: {relative_path}"
        )
    return int(head)


def derive_forbidden_window_evidence(
    run_identity: Mapping[str, object],
    frame: Mapping[str, np.ndarray],
) -> dict[str, object]:
    """Derive 2025/2026 non-inspection evidence from the authorized view.

    The proof is built from what the authorized run actually carried and
    actually loaded -- the authorized outcome window, the authorized partition
    identities, and the observed timestamp extremes of the already-loaded
    development bytes -- never by enumerating, opening, or reading anything in
    the reserved-validation or untouched-OOS windows.

    Fail-closed: if the authorized view or the loaded bytes reach 2025 or 2026
    at all, this raises instead of recording a forbidden window as inspected.
    """
    window = run_identity.get("window")
    if not isinstance(window, Mapping):
        raise B202Error("run identity is missing its authorized window evidence")
    try:
        end_exclusive_ms = int(window["end_exclusive_ms"])
        start_inclusive_ms = int(window["start_inclusive_ms"])
        allowed_years = tuple(int(year) for year in window["allowed_years"])
    except (KeyError, TypeError, ValueError) as exc:
        raise B202Error("authorized window evidence is malformed") from exc

    partitions = run_identity.get("partitions")
    if not isinstance(partitions, Sequence) or isinstance(partitions, (str, bytes)):
        raise B202Error("run identity is missing its authorized partition evidence")
    partition_years: list[int] = []
    for partition in partitions:
        if not isinstance(partition, Mapping) or "relative_path" not in partition:
            raise B202Error("authorized partition evidence is malformed")
        partition_years.append(_partition_year(str(partition["relative_path"])))
    if not partition_years:
        raise B202Error("authorized partition evidence is empty")

    open_ms = np.asarray(frame["open_time_ms"], dtype=np.int64)
    avail_ms = np.asarray(frame["available_at_ms"], dtype=np.int64)
    if len(open_ms) == 0:
        raise B202Error("loaded development frame is empty")
    observed_min_open_ms = int(np.min(open_ms))
    observed_max_open_ms = int(np.max(open_ms))
    observed_max_available_ms = int(np.max(avail_ms))

    if end_exclusive_ms > VALIDATION_2025_START_MS:
        raise B202Error("authorized window reaches the reserved 2025 validation pool")
    if max(allowed_years) >= FIRST_FORBIDDEN_YEAR:
        raise B202Error("authorized years reach a forbidden window")
    if max(partition_years) >= FIRST_FORBIDDEN_YEAR:
        raise B202Error("authorized partitions reach a forbidden window")
    if observed_max_available_ms > VALIDATION_2025_START_MS:
        raise B202Error("loaded development bytes reach the reserved 2025 pool")

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


def validate_1m_frame(frame: Mapping[str, np.ndarray]) -> None:
    columns = ("open_time_ms", "available_at_ms", "open", "high", "low", "close")
    if any(name not in frame for name in columns):
        raise B202Error("1m frame missing canonical OHLC/time columns")
    arrays = {name: np.asarray(frame[name]) for name in columns}
    n = len(arrays["open_time_ms"])
    if n == 0 or any(a.ndim != 1 or len(a) != n for a in arrays.values()):
        raise B202Error("1m columns must be equal non-empty one-dimensional arrays")
    if n % FIVE_MIN != 0:
        raise B202Error("1m frame length must be divisible by 5")
    open_ms = arrays["open_time_ms"].astype(np.int64)
    avail = arrays["available_at_ms"].astype(np.int64)
    if int(open_ms[0]) != WARMUP_START_MS:
        raise B202Error("1m frame must begin at frozen warmup start")
    if int(open_ms[0]) % FIVE_MS != 0:
        raise B202Error("1m frame must start on a UTC 5m boundary")
    expected = int(open_ms[0]) + np.arange(n, dtype=np.int64) * BAR_MS
    if np.any(open_ms != expected):
        raise B202Error("1m open_time_ms must be a contiguous minute grid")
    if np.any(avail != open_ms + BAR_MS):
        raise B202Error("1m available_at_ms must equal bar end")
    if int(open_ms[-1]) >= DEV_END_MS:
        raise B202Error("1m frame reaches reserved 2025+ source data")

    opn = arrays["open"].astype(np.float64)
    high = arrays["high"].astype(np.float64)
    low = arrays["low"].astype(np.float64)
    close = arrays["close"].astype(np.float64)
    for name, arr in (("open", opn), ("high", high), ("low", low), ("close", close)):
        if not np.all(np.isfinite(arr)) or np.any(arr <= 0.0):
            raise B202Error(f"{name} must be finite and positive")
    if np.any(low > high):
        raise B202Error("1m low exceeds high")
    if np.any(high < np.maximum(opn, close)) or np.any(low > np.minimum(opn, close)):
        raise B202Error("1m OHLC geometry is inconsistent")


def aggregate_1m_to_5m(frame: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    validate_1m_frame(frame)
    n = len(frame["open_time_ms"])
    n5 = n // FIVE_MIN
    open_ms = np.asarray(frame["open_time_ms"], dtype=np.int64)
    avail = np.asarray(frame["available_at_ms"], dtype=np.int64)
    opn = np.asarray(frame["open"], dtype=np.float64)
    high = np.asarray(frame["high"], dtype=np.float64)
    low = np.asarray(frame["low"], dtype=np.float64)
    close = np.asarray(frame["close"], dtype=np.float64)

    result = {
        "open_time_ms": open_ms[::FIVE_MIN],
        "available_at_ms": avail[FIVE_MIN - 1 :: FIVE_MIN],
        "open": opn[::FIVE_MIN],
        "high": high.reshape(n5, FIVE_MIN).max(axis=1),
        "low": low.reshape(n5, FIVE_MIN).min(axis=1),
        "close": close[FIVE_MIN - 1 :: FIVE_MIN],
    }
    if np.any(result["available_at_ms"] != result["open_time_ms"] + FIVE_MS):
        raise B202Error("derived 5m availability is not exact bar end")
    return result


def _prior_range(high: np.ndarray, low: np.ndarray, bars: int) -> tuple[np.ndarray, np.ndarray]:
    n = len(high)
    rh = np.full(n, np.nan, dtype=np.float64)
    rl = np.full(n, np.nan, dtype=np.float64)
    if bars <= 0 or n <= bars:
        return rh, rl
    wh = np.lib.stride_tricks.sliding_window_view(high, bars)
    wl = np.lib.stride_tricks.sliding_window_view(low, bars)
    rh[bars:] = wh.max(axis=1)[: n - bars]
    rl[bars:] = wl.min(axis=1)[: n - bars]
    return rh, rl


def _pre_vol_at_5m(frame_1m: Mapping[str, np.ndarray]) -> np.ndarray:
    close = np.asarray(frame_1m["close"], dtype=np.float64)
    logs = np.log(close)
    returns = np.full(len(close), np.nan, dtype=np.float64)
    returns[1:] = np.diff(logs)
    squares = returns * returns
    finite = np.isfinite(squares)
    sums = np.concatenate(([0.0], np.cumsum(np.where(finite, squares, 0.0))))
    bad = np.concatenate(([0], np.cumsum((~finite).astype(np.int64))))
    ends = np.arange(FIVE_MIN - 1, len(close), FIVE_MIN)
    out = np.full(len(ends), np.nan, dtype=np.float64)
    for pos, end in enumerate(ends):
        first_return = int(end) - 59
        last_exclusive = int(end) + 1
        if first_return < 1:
            continue
        if bad[last_exclusive] - bad[first_return] != 0:
            continue
        total = sums[last_exclusive] - sums[first_return]
        if total >= 0.0 and math.isfinite(float(total)):
            out[pos] = math.sqrt(float(total))
    return out


def _event_raw(
    frame_1m: Mapping[str, np.ndarray],
    frame5: Mapping[str, np.ndarray],
    L: int,
) -> list[dict[str, object]]:
    bars = L // FIVE_MIN
    high = np.asarray(frame5["high"], dtype=np.float64)
    low = np.asarray(frame5["low"], dtype=np.float64)
    opn = np.asarray(frame5["open"], dtype=np.float64)
    close = np.asarray(frame5["close"], dtype=np.float64)
    t0_all = np.asarray(frame5["available_at_ms"], dtype=np.int64)
    rh, rl = _prior_range(high, low, bars)
    with np.errstate(divide="ignore", invalid="ignore"):
        width = np.log(rh / rl)
    width = np.where((rh > rl) & (rl > 0.0), width, np.nan)
    pre_vol = _pre_vol_at_5m(frame_1m)

    open_inside = (opn >= rl) & (opn <= rh)
    upper = open_inside & (high > rh) & (low >= rl)
    lower = open_inside & (low < rl) & (high <= rh)
    double = open_inside & (high > rh) & (low < rl)
    upper &= ~double
    lower &= ~double
    qualifying = (upper | lower) & np.isfinite(width) & (width > 0.0)

    # Prereg section 4 defines the qualifying breach population: open inside the
    # prior range, exactly one boundary breached, a valid positive prior range,
    # and BREACH_MAG > 0. Section 5 then applies the 30m refractory ONCE to that
    # qualifying population, before candidate/baseline construction.
    #
    # BREACH_MAG is therefore evaluated here, before the refractory decision: a
    # bar that is not a qualifying breach must never consume a refractory slot
    # and thereby suppress a later genuinely qualifying breach.
    #
    # Everything after this loop (PRE_VOL/PRE_DRIFT availability, path state,
    # causal reference availability, history minima) is section 6/7 decision
    # availability, NOT qualification. Those events remain qualifying breaches,
    # keep their refractory slot, and are simply UNAVAILABLE_FOR_DECISION for
    # candidate and baseline alike. They must not be hoisted ahead of the
    # refractory or the frozen event population would silently change.
    accepted: list[tuple[int, float]] = []
    last_t0 = -10**30
    for idx in np.flatnonzero(qualifying):
        t0 = int(t0_all[idx])
        if t0 < DEV_START_MS or t0 > LAST_T0_MS:
            continue
        if int(idx) + PATH_BARS >= len(close):
            continue
        direction = DIR_UPPER if bool(upper[idx]) else DIR_LOWER
        boundary = float(rh[idx]) if direction == DIR_UPPER else float(rl[idx])
        if direction == DIR_UPPER:
            breach_mag = math.log(float(high[idx]) / boundary) / float(width[idx])
        else:
            breach_mag = math.log(boundary / float(low[idx])) / float(width[idx])
        if not math.isfinite(breach_mag) or breach_mag <= 0.0:
            continue
        if t0 < last_t0 + PATH_MS:
            continue
        accepted.append((int(idx), float(breach_mag)))
        last_t0 = t0

    events: list[dict[str, object]] = []
    for idx, breach_mag in accepted:
        direction = DIR_UPPER if bool(upper[idx]) else DIR_LOWER
        side = "UPPER" if direction == DIR_UPPER else "LOWER"
        boundary = float(rh[idx]) if direction == DIR_UPPER else float(rl[idx])
        drift_idx = idx - (60 // FIVE_MIN)
        if drift_idx < 0 or not math.isfinite(float(pre_vol[idx])):
            continue
        pre_drift = direction * math.log(float(close[idx]) / float(close[drift_idx]))

        path_slice = slice(idx + 1, idx + PATH_BARS + 1)
        path_close = close[path_slice]
        path_high = high[path_slice]
        path_low = low[path_slice]
        if len(path_close) != PATH_BARS:
            continue
        if direction == DIR_UPPER:
            residence = float(np.mean(path_close > boundary))
            terminal = math.log(float(path_close[-1]) / boundary) / float(width[idx])
            maximum = float(np.max(np.log(path_high / boundary))) / float(width[idx])
        else:
            residence = float(np.mean(path_close < boundary))
            terminal = math.log(boundary / float(path_close[-1])) / float(width[idx])
            maximum = float(np.max(np.log(boundary / path_low))) / float(width[idx])

        path_chain = np.concatenate(([float(close[idx])], path_close.astype(np.float64)))
        path_moves = np.diff(np.log(path_chain))
        denom = float(np.sum(np.abs(path_moves)))
        efficiency = (
            float(direction * math.log(float(path_close[-1]) / float(close[idx])) / denom)
            if denom > 0.0 and math.isfinite(denom)
            else float("nan")
        )

        t0 = int(t0_all[idx])
        t_index = idx + PATH_BARS
        t = int(t0_all[t_index])
        if t != t0 + PATH_MS:
            raise B202Error("path clock is not exactly six complete 5m bars")
        events.append(
            {
                "L": L,
                "side": side,
                "direction": direction,
                "breach_index": idx,
                "T0": t0,
                "T": t,
                "T_index": t_index,
                "boundary": boundary,
                "prior_log_range": float(width[idx]),
                "breach_mag": float(breach_mag),
                "pre_vol": float(pre_vol[idx]),
                "pre_drift": float(pre_drift),
                "residence": residence,
                "terminal_extension": float(terminal),
                "max_extension": float(maximum),
                "path_efficiency": float(efficiency),
            }
        )
    return events


def detect_breaches(
    frame_1m: Mapping[str, np.ndarray],
) -> tuple[dict[str, np.ndarray], list[dict[str, object]]]:
    frame5 = aggregate_1m_to_5m(frame_1m)
    events: list[dict[str, object]] = []
    for L in LOOKBACKS:
        events.extend(_event_raw(frame_1m, frame5, L))
    events.sort(key=lambda event: (int(event["T0"]), int(event["L"])))
    return frame5, events


def _tertile(score: float) -> int:
    if not math.isfinite(score):
        return STATE_MISSING
    if score < 0.0 or score > 1.0:
        raise B202Error("causal score outside [0,1]")
    if score < 1.0 / 3.0:
        return STATE_LOW
    if score < 2.0 / 3.0:
        return STATE_MID
    return STATE_HIGH


def _causal_tertile_states(values: np.ndarray, times: np.ndarray) -> np.ndarray:
    scores = rolling_midrank_percentile(
        np.asarray(values, dtype=np.float64),
        timestamps_ms=np.asarray(times, dtype=np.int64),
        lookback_ms=REF_MS,
    )
    out = np.full(len(scores), STATE_MISSING, dtype=np.int8)
    for i, score in enumerate(scores):
        out[i] = _tertile(float(score))
    return out


def attach_states(events: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    out = [dict(event) for event in events]
    for L in LOOKBACKS:
        positions = [i for i, event in enumerate(out) if int(event["L"]) == L]
        if not positions:
            continue
        t0 = np.asarray([int(out[i]["T0"]) for i in positions], dtype=np.int64)
        for source, target in (
            ("breach_mag", "breach_state"),
            ("pre_vol", "pre_vol_state"),
            ("pre_drift", "pre_drift_state"),
        ):
            raw = np.asarray([float(out[i][source]) for i in positions], dtype=np.float64)
            states = _causal_tertile_states(raw, t0)
            for pos, state in zip(positions, states):
                out[pos][target] = int(state)

        valid_positions = [
            i
            for i in positions
            if all(
                math.isfinite(float(out[i][name]))
                for name in (
                    "residence",
                    "terminal_extension",
                    "max_extension",
                    "path_efficiency",
                )
            )
        ]
        if valid_positions:
            path_times = np.asarray(
                [int(out[i]["T"]) for i in valid_positions],
                dtype=np.int64,
            )
            component_scores: list[np.ndarray] = []
            for name in (
                "residence",
                "terminal_extension",
                "max_extension",
                "path_efficiency",
            ):
                raw = np.asarray(
                    [float(out[i][name]) for i in valid_positions],
                    dtype=np.float64,
                )
                component_scores.append(
                    rolling_midrank_percentile(
                        raw,
                        timestamps_ms=path_times,
                        lookback_ms=REF_MS,
                    )
                )
            matrix = np.vstack(component_scores)
            mean_scores = np.mean(matrix, axis=0)
            for column, pos in enumerate(valid_positions):
                if np.all(np.isfinite(matrix[:, column])):
                    out[pos]["path_score"] = float(mean_scores[column])
                    out[pos]["path_state"] = _tertile(float(mean_scores[column]))
                else:
                    out[pos]["path_score"] = float("nan")
                    out[pos]["path_state"] = STATE_MISSING
        for pos in positions:
            out[pos].setdefault("path_score", float("nan"))
            out[pos].setdefault("path_state", STATE_MISSING)
    return out


def _target_scale(close5: np.ndarray, H: int) -> np.ndarray:
    h_bars = H // FIVE_MIN
    ref_steps = REF_DAYS * 24 * 60 // FIVE_MIN
    known = np.full(len(close5), np.nan, dtype=np.float64)
    if h_bars <= 0 or h_bars >= len(close5):
        return known
    source = np.arange(len(close5) - h_bars, dtype=np.int64)
    with np.errstate(divide="ignore", invalid="ignore"):
        absolute = np.abs(np.log(close5[source + h_bars] / close5[source]))
    known[source + h_bars] = absolute
    count = ref_steps - h_bars + 1
    if count <= 0:
        return np.full(len(close5), np.nan, dtype=np.float64)
    med = (
        pd.Series(known, copy=False)
        .rolling(count, min_periods=count)
        .median()
        .to_numpy()
    )
    return np.where(np.isfinite(med) & (med > 0.0), med, np.nan)


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


def _seed_int(parts: Sequence[object]) -> int:
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:16], 16)


def _event_id(event: Mapping[str, object], H: int) -> str:
    return "|".join(
        (
            REQUIRED_SNAPSHOT,
            "1m",
            "5m",
            str(int(event["L"])),
            str(event["side"]),
            str(int(event["T0"])),
            str(int(event["T"])),
            str(int(H)),
        )
    )


def _purge(queue: deque, cutoff: int) -> None:
    while queue and int(queue[0][0]) < cutoff:
        queue.popleft()


def _week_bootstrap_interval(
    improvements: np.ndarray,
    times: np.ndarray,
    L: int,
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
    rng = np.random.default_rng(_seed_int((SEED_BOOT, L, H)))
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


def _support_diagnostics(
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    times = [int(record["T"]) for record in records]
    months: dict[int, int] = defaultdict(int)
    sides: dict[str, int] = defaultdict(int)
    paths: dict[int, int] = defaultdict(int)
    baseline: dict[str, int] = defaultdict(int)
    for record in records:
        months[_month_key(int(record["T"]))] += 1
        sides[str(record["side"])] += 1
        paths[int(record["path_state"])] += 1
        key = (
            f'{int(record["breach_state"])}|'
            f'{int(record["pre_vol_state"])}|'
            f'{int(record["pre_drift_state"])}'
        )
        baseline[key] += 1
    counts = sorted(months.values(), reverse=True)
    n = len(records)
    return {
        "unique_utc_days": len({t // DAY_MS for t in times}),
        "unique_utc_weeks": len({_week_key(t) for t in times}),
        "unique_utc_months": len(months),
        "largest_month_share": float(counts[0] / n) if n and counts else None,
        "top5_month_share": float(sum(counts[:5]) / n) if n else None,
        "side_counts": dict(sorted(sides.items())),
        "path_state_counts": {str(k): v for k, v in sorted(paths.items())},
        "baseline_state_counts": dict(sorted(baseline.items())),
    }


def evaluate_cell(
    frame5: Mapping[str, np.ndarray],
    events: Sequence[Mapping[str, object]],
    L: int,
    H: int,
) -> dict[str, object]:
    close5 = np.asarray(frame5["close"], dtype=np.float64)
    scale = _target_scale(close5, H)
    h_bars = H // FIVE_MIN

    eligible: list[dict[str, object]] = []
    for raw in events:
        if int(raw["L"]) != L:
            continue
        event = dict(raw)
        t_index = int(event["T_index"])
        future_index = t_index + h_bars
        if future_index >= len(close5):
            continue
        if int(event["T"]) + H * BAR_MS >= DEV_END_MS:
            continue
        state_values = (
            int(event.get("breach_state", STATE_MISSING)),
            int(event.get("pre_vol_state", STATE_MISSING)),
            int(event.get("pre_drift_state", STATE_MISSING)),
            int(event.get("path_state", STATE_MISSING)),
        )
        if any(state < 0 for state in state_values):
            continue
        denom = float(scale[t_index])
        if not math.isfinite(denom) or denom <= 0.0:
            continue
        direction = int(event["direction"])
        y = (
            direction
            * math.log(float(close5[future_index]) / float(close5[t_index]))
            / denom
        )
        if not math.isfinite(y):
            continue
        event["Y"] = float(y)
        event["H"] = H
        eligible.append(event)

    eligible.sort(key=lambda event: int(event["T"]))
    baseline_queues: dict[tuple[int, int, int], deque] = defaultdict(deque)
    candidate_queues: dict[tuple[int, int, int, int], deque] = defaultdict(deque)
    mature = 0
    scored: list[dict[str, object]] = []
    placebo_sums = np.zeros(N_PLACEBO, dtype=np.float64)

    for current_index, event in enumerate(eligible):
        current_t = int(event["T"])
        while (
            mature < current_index
            and int(eligible[mature]["T"]) + H * BAR_MS <= current_t
        ):
            previous = eligible[mature]
            base_key = (
                int(previous["breach_state"]),
                int(previous["pre_vol_state"]),
                int(previous["pre_drift_state"]),
            )
            candidate_key = (*base_key, int(previous["path_state"]))
            item = (
                int(previous["T"]),
                float(previous["Y"]),
                int(previous["path_state"]),
            )
            baseline_queues[base_key].append(item)
            candidate_queues[candidate_key].append(item)
            mature += 1

        base_key = (
            int(event["breach_state"]),
            int(event["pre_vol_state"]),
            int(event["pre_drift_state"]),
        )
        candidate_key = (*base_key, int(event["path_state"]))
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
        base_y = np.asarray(
            [float(item[1]) for item in base_queue],
            dtype=np.float64,
        )
        candidate_y = np.asarray(
            [float(item[1]) for item in candidate_queue],
            dtype=np.float64,
        )
        base_pred = float(np.median(base_y))
        candidate_pred = float(np.median(candidate_y))
        y = float(event["Y"])
        base_ae = abs(y - base_pred)
        candidate_ae = abs(y - candidate_pred)
        improvement = base_ae - candidate_ae

        record = dict(event)
        record.update(
            {
                "event_id": _event_id(event, H),
                "base_pred": base_pred,
                "candidate_pred": candidate_pred,
                "base_ae": base_ae,
                "candidate_ae": candidate_ae,
                "ae_improvement": improvement,
                "base_residual": y - base_pred,
                "baseline_count": len(base_queue),
                "candidate_count": len(candidate_queue),
            }
        )
        scored.append(record)

        # Internal consistency invariant, not ordinary unavailability.
        #
        # Every matured event is appended to baseline_queues[base_key] and to
        # candidate_queues[base_key + path_state] in the same iteration, and
        # both queues are purged immediately above with the same monotonically
        # non-decreasing cutoff. The subset of base_queue carrying this event's
        # path_state is therefore exactly candidate_queue, so path_count ==
        # len(candidate_queue) >= CANDIDATE_MIN_COUNT always holds here.
        #
        # The check is consequently redundant by construction and must never
        # fire. If it ever does, the queue bookkeeping -- and therefore the
        # placebo stratum the negative control draws from -- is inconsistent
        # with the scored candidate support. That is an integrity failure, not
        # a per-cell unavailability the frozen contract defines, so it stays
        # fail-closed: the run aborts rather than emitting a partial or
        # silently mis-strata'd research result.
        path_count = sum(
            1
            for item in base_queue
            if int(item[2]) == int(event["path_state"])
        )
        if path_count != len(candidate_queue) or path_count < CANDIDATE_MIN_COUNT:
            raise B202Error("placebo stratum count diverged from candidate count")
        stratum = "|".join(str(value) for value in base_key)
        for rep in range(N_PLACEBO):
            rng = np.random.default_rng(
                _seed_int((SEED_PLACEBO, rep, L, H, current_t, stratum))
            )
            chosen = rng.choice(
                len(base_y),
                size=path_count,
                replace=False,
            )
            placebo_pred = float(np.median(base_y[chosen]))
            placebo_sums[rep] += base_ae - abs(y - placebo_pred)

    improvements = np.asarray(
        [float(record["ae_improvement"]) for record in scored],
        dtype=np.float64,
    )
    base_ae = np.asarray(
        [float(record["base_ae"]) for record in scored],
        dtype=np.float64,
    )
    candidate_ae = np.asarray(
        [float(record["candidate_ae"]) for record in scored],
        dtype=np.float64,
    )
    times = np.asarray(
        [int(record["T"]) for record in scored],
        dtype=np.int64,
    )
    base_residual = np.asarray(
        [float(record["base_residual"]) for record in scored],
        dtype=np.float64,
    )
    path_states = np.asarray(
        [int(record["path_state"]) for record in scored],
        dtype=np.int8,
    )

    mean_improvement = (
        float(np.mean(improvements))
        if len(improvements)
        else float("nan")
    )
    median_improvement = (
        float(np.median(improvements))
        if len(improvements)
        else float("nan")
    )
    mean_base = float(np.mean(base_ae)) if len(base_ae) else float("nan")
    mean_candidate = (
        float(np.mean(candidate_ae))
        if len(candidate_ae)
        else float("nan")
    )
    relative = (
        1.0 - mean_candidate / mean_base
        if math.isfinite(mean_base) and mean_base > 0.0
        else float("nan")
    )
    ci_low, ci_high = _week_bootstrap_interval(
        improvements,
        times,
        L,
        H,
    )

    high_values = base_residual[path_states == STATE_HIGH]
    low_values = base_residual[path_states == STATE_LOW]
    separation = (
        float(np.median(high_values) - np.median(low_values))
        if len(high_values) and len(low_values)
        else float("nan")
    )
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
        mean_year = (
            float(np.mean(values))
            if len(values)
            else float("nan")
        )
        yearly[str(year)] = mean_year if math.isfinite(mean_year) else None
        if math.isfinite(mean_year) and mean_year > 0.0:
            positive_years += 1

    gates = {
        "primary_positive": bool(
            math.isfinite(mean_improvement)
            and mean_improvement > 0.0
        ),
        "material_relative_mae": bool(
            math.isfinite(relative)
            and relative >= RELATIVE_MAE_MIN
        ),
        "bootstrap_positive": bool(
            math.isfinite(ci_low)
            and ci_low > 0.0
        ),
        "placebo_separation": bool(
            math.isfinite(mean_improvement)
            and math.isfinite(placebo_q95)
            and mean_improvement > placebo_q95
        ),
        "path_ordering": bool(
            math.isfinite(separation)
            and separation > 0.0
        ),
    }

    return {
        "L": L,
        "H": H,
        "N": len(scored),
        "mean_ae_improvement": (
            mean_improvement
            if math.isfinite(mean_improvement)
            else None
        ),
        "median_ae_improvement": (
            median_improvement
            if math.isfinite(median_improvement)
            else None
        ),
        "relative_mae_improvement": (
            relative
            if math.isfinite(relative)
            else None
        ),
        "bootstrap_ci95": [
            ci_low if math.isfinite(ci_low) else None,
            ci_high if math.isfinite(ci_high) else None,
        ],
        "path_separation": (
            separation
            if math.isfinite(separation)
            else None
        ),
        "placebo_q95": (
            placebo_q95
            if math.isfinite(placebo_q95)
            else None
        ),
        "yearly_mean_ae_improvement": yearly,
        "positive_years": positive_years,
        "year_stability_pass": bool(positive_years >= 4),
        "per_cell_gates": gates,
        "support": _support_diagnostics(scored),
        "event_ids": [str(record["event_id"]) for record in scored],
    }


def _cell_five_pass(cell: Mapping[str, object]) -> bool:
    gates = cell.get("per_cell_gates")
    if not isinstance(gates, Mapping):
        return False
    return all(
        gates.get(name) is True
        for name in PER_CELL_GATE_NAMES
    )


def determine_promotion_gates(
    cells: Sequence[Mapping[str, object]],
) -> tuple[dict[str, bool], list[dict[str, int]]]:
    by_key = {
        (int(cell["L"]), int(cell["H"])): cell
        for cell in cells
        if "L" in cell and "H" in cell
    }
    per_gate_evidence = {
        name: False
        for name in PER_CELL_GATE_NAMES
    }
    horizon_robustness = False
    parameter_robustness = False
    year_stability = False
    selected: list[dict[str, int]] = []

    for h1, h2 in ADJACENT_H_PAIRS:
        per_gate_L: dict[str, list[int]] = {
            name: []
            for name in PER_CELL_GATE_NAMES
        }
        core_L: list[int] = []
        stable_L: list[int] = []
        for L in LOOKBACKS:
            c1 = by_key.get((L, h1))
            c2 = by_key.get((L, h2))
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
                    per_gate_L[name].append(L)
            if _cell_five_pass(c1) and _cell_five_pass(c2):
                horizon_robustness = True
                core_L.append(L)
                if (
                    c1.get("year_stability_pass") is True
                    and c2.get("year_stability_pass") is True
                ):
                    stable_L.append(L)

        for name, passing in per_gate_L.items():
            if len(passing) >= 2:
                per_gate_evidence[name] = True
        if len(core_L) >= 2:
            parameter_robustness = True
        if len(stable_L) >= 2:
            year_stability = True
            if not selected:
                for L in sorted(stable_L)[:2]:
                    selected.extend(
                        (
                            {"L": L, "H": h1},
                            {"L": L, "H": h2},
                        )
                    )

    gates = {
        **per_gate_evidence,
        "horizon_robustness": horizon_robustness,
        "parameter_robustness": parameter_robustness,
        "year_stability": year_stability,
    }
    return gates, selected


def evaluate_b2_02(
    frame_1m: Mapping[str, np.ndarray],
) -> dict[str, object]:
    frame5, raw_events = detect_breaches(frame_1m)
    events = attach_states(raw_events)
    cells = [
        evaluate_cell(frame5, events, L, H)
        for L in LOOKBACKS
        for H in HORIZONS
    ]
    gates, selected = determine_promotion_gates(cells)
    passed = all(gates.get(name) is True for name in GATE_NAMES)
    return {
        "hypothesis_id": HYPOTHESIS_ID,
        "dataset_id": DATASET_ID,
        "snapshot_id": REQUIRED_SNAPSHOT,
        "search_surface": {
            "lookbacks_minutes": list(LOOKBACKS),
            "path_observation_minutes": PATH_MIN,
            "horizons_minutes": list(HORIZONS),
            "primary_cells": 12,
        },
        "windows": {
            "warmup_start_inclusive_ms": WARMUP_START_MS,
            "development_start_inclusive_ms": DEV_START_MS,
            "development_end_exclusive_ms": DEV_END_MS,
            "last_legal_T0_ms": LAST_T0_MS,
            "last_legal_T_ms": LAST_T_MS,
            "validation_2025_untouched": True,
            "oos_2026_untouched": True,
        },
        "qualifying_breaches": len(raw_events),
        "cells": cells,
        "promotion": {
            "gates": gates,
            "selected_neighborhood": selected,
            "passed": passed,
            "verdict": (
                "B2_02_PROMOTED_CANDIDATE"
                if passed
                else "B2_02_CLOSED_NO_PROMOTION"
            ),
        },
    }
