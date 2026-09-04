"""Outcome-blind B2-04 moderate-pullback-structure numerical implementation.

Implements the frozen B2-04 preregistration
(`docs/research/B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.md` / `.json`)
using only in-memory arrays. This module never opens files, enumerates
datasets, talks to Git/network, creates evidence reservations, or persists
results.

Frozen contract summary implemented here (prereg section in brackets):

- source 1m, derived/decision grid 15m, P=60m, L in {240,480,960},
  H in {15,30,60,120,240}, moderate depth [0.25,0.40) [MD 4, 7; JSON
  event_construction];
- event lifecycle CONSTRUCT -> REFRACTORY -> IMMUTABLE POPULATION ->
  CAUSAL FEATURES -> H-SPECIFIC SCORE RECORD -> SAME-SUPPORT COMPARISON
  [MD 5; JSON event_lifecycle];
- exactly one structural property `RECOVERY_FRACTION` over the four 15m
  path steps {T-45m, T-30m, T-15m, T} anchored at close(T-60m), with
  event-level (not step-level) `d` and `TREND_RET_L` [MD 3, 4];
- baseline `Y = a + b*FINAL_DEPTH`, candidate adds only
  `c*RECOVERY_FRACTION`, unweighted OLS inside each (L, DIRECTION)
  365-day causal training pool, shared minimum N=30, no pseudoinverse,
  joint fail-closed [MD 10, 11, 12];
- placebo permutes historical training `RECOVERY_FRACTION` only
  (N=100, seed 20260906); UTC ISO-week block bootstrap (N=2000, seed
  20260907) [MD 14, 15];
- five per-cell conditions and eight promotion gates [MD 16].

This module deliberately does not use `from __future__ import annotations`:
the merged Batch02 static source policy default-denies every non-repository
import that is not on its explicit transform allowlist, and B2-04 source is
adapted to that bounded policy rather than the policy being widened. Python
3.11 evaluates the annotations used here natively.
"""

import hashlib
import math
from collections import defaultdict
from decimal import Decimal
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from scripts.research.lib.batch02_contracts import rolling_midrank_percentile


HYPOTHESIS_ID = "B2-04_MODERATE_PULLBACK_STRUCTURE"
DATASET_ID = "CORE_BTC_BINANCE_V0"
REQUIRED_SNAPSHOT = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
PREREG_MERGE_SHA = "bcc00d4a6180105991fd4828b7cfc7983c9c9ccf"
PRIMARY_FAMILY = "F1"
POSTHOC_PROVENANCE = "explicit_POSTHOC_UNTESTED_child"
H04_VERDICT = "H04_REJECTED_SPECIFIC_CLAIM"
STRUCTURAL_PROPERTY_FAMILY = "INTRA_PULLBACK_RECOVERY"
STRUCTURAL_PROPERTY_NAME = "RECOVERY_FRACTION"

BAR_MS = 60_000
HTF_MIN = 15
HTF_MS = HTF_MIN * BAR_MS
DAY_MS = 24 * 60 * BAR_MS

P_MIN = 60
P_STEPS = P_MIN // HTF_MIN
PATH_OFFSETS_MIN = (-45, -30, -15, 0)

L_VALUES = (240, 480, 960)
H_VALUES = (15, 30, 60, 120, 240)
ADJACENT_H_PAIRS = ((15, 30), (30, 60), (60, 120), (120, 240))
PRIMARY_CELLS = 15

TREND_Q = 0.80
MODERATE_LO = 0.25
MODERATE_HI = 0.40
REFRACTORY_MS = 60 * BAR_MS

REF_DAYS = 30
REF_STEPS = REF_DAYS * 24 * 60 // HTF_MIN
TRAIN_DAYS = 365
TRAIN_MS = TRAIN_DAYS * DAY_MS
MIN_TRAIN_COUNT = 30

RELATIVE_MAE_MIN = 0.02
PLACEBO_Q = 0.95
N_PLACEBO = 100
SEED_PLACEBO = 20260906
N_BOOT = 2000
SEED_BOOT = 20260907
BOOT_LOW_Q = 0.025
BOOT_HIGH_Q = 0.975

WARMUP_START_MS = 1_577_836_800_000
DEV_START_MS = 1_580_515_200_000
DEV_END_MS = 1_735_689_600_000
VALIDATION_2025_START_MS = DEV_END_MS
OOS_2026_START_MS = 1_767_225_600_000
FIRST_FORBIDDEN_YEAR = 2025
YEAR_BLOCKS = (2020, 2021, 2022, 2023, 2024)
MIN_POSITIVE_YEARS = 4

DIR_UP = 1
DIR_DOWN = -1
DIR_LABELS = {DIR_UP: "UP", DIR_DOWN: "DOWN"}
STATE_LOW = "LOW"
STATE_HIGH = "HIGH"
STATE_CUTPOINT = 0.5

GATE_NAMES = (
    "primary_positive",
    "material_relative_mae",
    "bootstrap_positive",
    "placebo_separation",
    "structure_ordering",
    "horizon_robustness",
    "parameter_robustness",
    "year_stability",
)
PER_CELL_GATE_NAMES = GATE_NAMES[:5]

VERDICT_PROMOTED = "B2_04_PROMOTED_CANDIDATE"
VERDICT_CLOSED = "B2_04_CLOSED_NO_PROMOTION"


class B204Error(RuntimeError):
    """B2-04 implementation input/invariant error."""


# ---------------------------------------------------------------------------
# frozen chronology helpers
# ---------------------------------------------------------------------------
def last_legal_t_ms(H):
    """Latest 15m grid T with T + H < 2025-01-01T00:00:00Z (equality illegal).

    Derived, not transcribed: the frozen table in prereg MD section 8 is an
    assertion target for tests, never the source of this value.
    """
    h = int(H)
    if h not in H_VALUES:
        raise B204Error("horizon is not in the frozen H set")
    limit = DEV_END_MS - h * BAR_MS
    grid = ((limit - 1) // HTF_MS) * HTF_MS
    return int(grid)


LAST_LEGAL_T_MS = {int(h): last_legal_t_ms(h) for h in H_VALUES}


def scoring_eligible(T_ms, H):
    """Development scoring window for one (T, H) score record."""
    t = int(T_ms)
    h = int(H)
    if t % HTF_MS != 0:
        return False
    if t < DEV_START_MS or t >= DEV_END_MS:
        return False
    return t + h * BAR_MS < DEV_END_MS


def _civil_from_days(z):
    """Proleptic Gregorian (year, month, day) from days since 1970-01-01."""
    z = int(z) + 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return (int(y + (1 if m <= 2 else 0)), int(m), int(d))


def _days_from_civil(y, m, d):
    """Days since 1970-01-01 for a proleptic Gregorian date."""
    y = int(y)
    y -= 1 if int(m) <= 2 else 0
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    mp = (int(m) + 9) % 12
    doy = (153 * mp + 2) // 5 + int(d) - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return int(era * 146097 + doe - 719468)


def utc_year(ms):
    return _civil_from_days(int(ms) // DAY_MS)[0]


def iso_week_id(ms):
    """ISO week-numbering year * 100 + ISO week (UTC), matching
    `datetime.isocalendar()` semantics. The Gregorian calendar year is
    deliberately not used (prereg MD section 15 / JSON bootstrap_week_id)."""
    days = int(ms) // DAY_MS
    weekday = ((days + 3) % 7) + 1
    thursday = days - (weekday - 4)
    iso_year = _civil_from_days(thursday)[0]
    jan1 = _days_from_civil(iso_year, 1, 1)
    week = (thursday - jan1) // 7 + 1
    return int(iso_year) * 100 + int(week)


# ---------------------------------------------------------------------------
# authorized in-memory frame conversion
# ---------------------------------------------------------------------------
def _finite_price(value, label):
    try:
        out = float(Decimal(str(value)))
    except Exception as exc:
        raise B204Error(f"{label} is not a valid decimal price") from exc
    if not math.isfinite(out) or out <= 0.0:
        raise B204Error(f"{label} must be finite and > 0")
    return out


def table_to_1m_frame(table):
    """Convert an authorized Arrow table without any direct file access."""
    columns = ("open_time_ms", "available_at_ms", "close")
    values = {}
    for name in columns:
        try:
            column = table.column(name)
        except Exception as exc:
            raise B204Error(f"authorized table missing canonical column {name}") from exc
        try:
            raw = column.to_numpy(zero_copy_only=False)
        except Exception as exc:
            raise B204Error(
                f"authorized column {name} is not convertible in memory"
            ) from exc
        if name in {"open_time_ms", "available_at_ms"}:
            try:
                values[name] = np.asarray(raw, dtype=np.int64)
            except (TypeError, ValueError) as exc:
                raise B204Error(
                    f"authorized column {name} is not integer milliseconds"
                ) from exc
        else:
            values[name] = np.asarray(
                [_finite_price(v, name) for v in raw],
                dtype=np.float64,
            )
    validate_1m_frame(values)
    return values


def validate_1m_frame(frame):
    columns = ("open_time_ms", "available_at_ms", "close")
    if any(name not in frame for name in columns):
        raise B204Error("1m frame missing canonical time/close columns")
    arrays = {name: np.asarray(frame[name]) for name in columns}
    n = len(arrays["open_time_ms"])
    if n == 0 or any(a.ndim != 1 or len(a) != n for a in arrays.values()):
        raise B204Error("1m columns must be equal non-empty one-dimensional arrays")
    open_ms = arrays["open_time_ms"].astype(np.int64, copy=False)
    avail = arrays["available_at_ms"].astype(np.int64, copy=False)
    close = arrays["close"].astype(np.float64, copy=False)
    if not np.all(np.isfinite(close)) or np.any(close <= 0.0):
        raise B204Error("close must be finite and strictly positive")
    if (
        int(np.max(open_ms)) >= DEV_END_MS
        or int(np.max(avail)) > VALIDATION_2025_START_MS
        or int(np.min(open_ms)) >= DEV_END_MS
        or int(np.min(avail)) > VALIDATION_2025_START_MS
    ):
        raise B204Error("1m frame reaches reserved 2025+ source data")
    if int(open_ms[0]) % HTF_MS != 0:
        raise B204Error("1m frame must start on a UTC 15m boundary")
    if n % HTF_MIN != 0:
        raise B204Error("1m frame length must be a whole number of 15m buckets")
    expected = int(open_ms[0]) + np.arange(n, dtype=np.int64) * BAR_MS
    if np.any(open_ms != expected):
        raise B204Error("1m open_time_ms must be a contiguous minute grid")
    if np.any(avail != open_ms + BAR_MS):
        raise B204Error("available_at_ms must equal open_time_ms + 60000")


def aggregate_1m_to_15m(frame_1m):
    """T is the bar-end-exclusive of the 15m bucket [T-15m, T).

    close(T) is the close of the final canonical 1m bar whose own
    bar-end-exclusive equals T. There is no off-by-one discretion: this is
    the only place the 1m -> 15m close is chosen.
    """
    validate_1m_frame(frame_1m)
    open_ms = np.asarray(frame_1m["open_time_ms"], dtype=np.int64)
    avail = np.asarray(frame_1m["available_at_ms"], dtype=np.int64)
    close = np.asarray(frame_1m["close"], dtype=np.float64)
    n15 = len(open_ms) // HTF_MIN
    bucket_open = open_ms[::HTF_MIN]
    bucket_close = close[HTF_MIN - 1:: HTF_MIN]
    bucket_avail = avail[HTF_MIN - 1:: HTF_MIN]
    t_ms = bucket_open + HTF_MS
    if np.any(bucket_avail != t_ms):
        raise B204Error("15m available_at is not the last 1m available_at in the bucket")
    if len(t_ms) != n15 or len(bucket_close) != n15:
        raise B204Error("15m aggregation produced an inconsistent bucket count")
    return {"t_ms": t_ms, "close": bucket_close}


# ---------------------------------------------------------------------------
# canonical identity + seeds
# ---------------------------------------------------------------------------
def canonical_base_event_id(*, L, direction, T_ms, snapshot_id=REQUIRED_SNAPSHOT):
    """snapshot|1m|15m|15m|L|direction|pullback_start_ms|T_ms (prereg MD 6)."""
    if direction not in {"UP", "DOWN"}:
        raise B204Error("canonical event direction must be UP or DOWN")
    t = int(T_ms)
    return "|".join(
        (
            str(snapshot_id),
            "1m",
            "15m",
            "15m",
            str(int(L)),
            str(direction),
            str(t - P_MIN * BAR_MS),
            str(t),
        )
    )


def canonical_score_record_id(base_event_id, H):
    """CANONICAL_SCORE_RECORD_ID = CANONICAL_BASE_EVENT_ID|H_minutes."""
    if int(H) not in H_VALUES:
        raise B204Error("horizon is not in the frozen H set")
    return "|".join((str(base_event_id), str(int(H))))


def baseline_stratum_id(*, L, direction):
    if direction not in {"UP", "DOWN"}:
        raise B204Error("stratum direction must be UP or DOWN")
    return "|".join((str(int(L)), str(direction)))


def seed_int(parts):
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:16], 16)


# ---------------------------------------------------------------------------
# STAGE A - construct events (H04-compatible; recovery/target/H forbidden)
# ---------------------------------------------------------------------------
def trend_returns(close, L):
    """TREND_RET_L(T) = ln(close(T-P) / close(T-P-L)) on the 15m grid."""
    l_minutes = int(L)
    if l_minutes % HTF_MIN != 0:
        raise B204Error("L is not a multiple of the 15m grid")
    l_step = l_minutes // HTF_MIN
    lag_near = P_STEPS
    lag_far = P_STEPS + l_step
    values = np.asarray(close, dtype=np.float64)
    n = len(values)
    out = np.full(n, np.nan, dtype=np.float64)
    if n <= lag_far:
        return out
    near = values[lag_far - lag_near: n - lag_near]
    far = values[: n - lag_far]
    with np.errstate(divide="ignore", invalid="ignore"):
        out[lag_far:] = np.log(near / far)
    return out


def raw_pullback_returns(close):
    """RAW_PB_RET(T) = ln(close(T) / close(T-P)); identical for every L."""
    values = np.asarray(close, dtype=np.float64)
    n = len(values)
    out = np.full(n, np.nan, dtype=np.float64)
    if n <= P_STEPS:
        return out
    with np.errstate(divide="ignore", invalid="ignore"):
        out[P_STEPS:] = np.log(values[P_STEPS:] / values[:-P_STEPS])
    return out


def trend_standing(abs_trend):
    """Causal 30-calendar-day midrank standing of ABS_TREND_L.

    On the contiguous 15m grid the frozen "preceding 30 calendar days" is
    exactly `REF_STEPS` grid steps, so the canonical Batch02 primitive is
    called in its fixed-count mode with the same window H04 froze. Tests
    assert this equals the canonical time-window mode at 30 days and an
    independent from-scratch midrank oracle.
    """
    return rolling_midrank_percentile(
        np.asarray(abs_trend, dtype=np.float64),
        window=REF_STEPS,
    )


def construct_events(frame15):
    """STAGE A + STAGE B: constructed moderate events after refractory.

    Returns the immutable base-event population (STAGE C). Recovery, target
    availability and H are not inputs here and cannot change membership.
    """
    t_ms = np.asarray(frame15["t_ms"], dtype=np.int64)
    close = np.asarray(frame15["close"], dtype=np.float64)
    if len(t_ms) != len(close):
        raise B204Error("15m frame columns must be equal length")
    raw_pb = raw_pullback_returns(close)
    constructed = []
    for L in L_VALUES:
        trend = trend_returns(close, L)
        standing = trend_standing(np.abs(trend))
        stream = []
        for i in range(len(t_ms)):
            tr = float(trend[i])
            st = float(standing[i])
            if not math.isfinite(tr) or tr == 0.0:
                continue
            if not math.isfinite(st) or st < TREND_Q:
                continue
            pb = float(raw_pb[i])
            if not math.isfinite(pb):
                continue
            d = DIR_UP if tr > 0.0 else DIR_DOWN
            signed_pb = float(d) * pb
            if not (signed_pb < 0.0):
                continue
            denom = abs(tr)
            if not math.isfinite(denom) or denom <= 0.0:
                continue
            final_depth = -signed_pb / denom
            if not math.isfinite(final_depth):
                continue
            if final_depth < MODERATE_LO or final_depth >= MODERATE_HI:
                continue
            t = int(t_ms[i])
            stream.append(
                {
                    "L": int(L),
                    "T": t,
                    "index": int(i),
                    "d": int(d),
                    "direction": DIR_LABELS[d],
                    "trend_ret": tr,
                    "abs_trend": denom,
                    "trend_standing": st,
                    "signed_pb_ret": signed_pb,
                    "final_depth": float(final_depth),
                    "base_event_id": canonical_base_event_id(
                        L=int(L),
                        direction=DIR_LABELS[d],
                        T_ms=t,
                    ),
                    "warmup_only": bool(t < DEV_START_MS),
                }
            )
        constructed.extend(apply_refractory(stream))
    constructed.sort(key=lambda event: (int(event["T"]), int(event["L"])))
    return constructed


def apply_refractory(stream, refractory_ms=REFRACTORY_MS):
    """STAGE B: 60m within one L on the constructed moderate stream.

    Earliest T wins. The caller supplies one L's chronological stream; there
    is no cross-L suppression and no T-only global dedup. Recovery, target
    availability and H are structurally absent from this function.
    """
    kept = []
    last = None
    for event in sorted(stream, key=lambda item: int(item["T"])):
        t = int(event["T"])
        if last is None or t >= last + int(refractory_ms):
            kept.append(event)
            last = t
    return kept


# ---------------------------------------------------------------------------
# STAGE D - causal features at T
# ---------------------------------------------------------------------------
def recovery_descriptor(close, index, d, abs_trend):
    """RECOVERY_FRACTION over the four frozen 15m path steps.

    ADVERSE_j = -d * ln(close(t_j) / close(T-60m)) / abs(TREND_RET_L(T))
    for t_j in {T-45m, T-30m, T-15m, T}; close(T-60m) is the path origin and
    is not itself a path step. Returns None when the descriptor is malformed;
    the caller must keep the constructed event and mark only the H-specific
    score record unavailable.
    """
    values = np.asarray(close, dtype=np.float64)
    i = int(index)
    origin_index = i - P_STEPS
    if origin_index < 0:
        return None
    denom = float(abs_trend)
    if not math.isfinite(denom) or denom <= 0.0:
        return None
    origin = float(values[origin_index])
    if not math.isfinite(origin) or origin <= 0.0:
        return None
    adverse = []
    for offset in PATH_OFFSETS_MIN:
        step_index = i + offset // HTF_MIN
        if step_index < 0 or step_index >= len(values):
            return None
        price = float(values[step_index])
        if not math.isfinite(price) or price <= 0.0:
            return None
        ratio = math.log(price / origin)
        if not math.isfinite(ratio):
            return None
        adverse.append(-float(d) * ratio / denom)
    if len(adverse) != len(PATH_OFFSETS_MIN):
        return None
    if not all(math.isfinite(value) for value in adverse):
        return None
    final_depth = float(adverse[-1])
    max_adverse = float(max(adverse))
    if not math.isfinite(max_adverse) or max_adverse <= 0.0:
        return None
    if final_depth > max_adverse:
        return None
    fraction = (max_adverse - final_depth) / max_adverse
    if not math.isfinite(fraction) or fraction < 0.0 or fraction > 1.0:
        return None
    return {
        "adverse_path": [float(value) for value in adverse],
        "path_final_depth": final_depth,
        "max_adverse": max_adverse,
        "recovery_fraction": float(fraction),
    }


def attach_recovery(events, frame15, depth_tolerance=1e-9):
    """Attach RECOVERY_FRACTION without changing the event population."""
    close = np.asarray(frame15["close"], dtype=np.float64)
    out = []
    for event in events:
        record = dict(event)
        descriptor = recovery_descriptor(
            close,
            int(record["index"]),
            int(record["d"]),
            float(record["abs_trend"]),
        )
        if descriptor is None:
            record["recovery_available"] = False
            record["recovery_fraction"] = float("nan")
            record["max_adverse"] = float("nan")
        else:
            drift = abs(descriptor["path_final_depth"] - float(record["final_depth"]))
            if drift > float(depth_tolerance):
                raise B204Error(
                    "path final adverse step does not equal H04 PULLBACK_DEPTH"
                )
            record["recovery_available"] = True
            record["recovery_fraction"] = float(descriptor["recovery_fraction"])
            record["max_adverse"] = float(descriptor["max_adverse"])
        out.append(record)
    return out


def attach_structure_state(events):
    """Gate-only RECOVERY_STATE (causal 365d same-L midrank, pooled sides).

    This never enters the candidate design matrix and never changes event
    existence or support (prereg MD section 9).
    """
    out = [dict(event) for event in events]
    for event in out:
        event["structure_state"] = None
        event["structure_standing"] = float("nan")
    for L in L_VALUES:
        positions = [
            i
            for i, event in enumerate(out)
            if int(event["L"]) == int(L) and bool(event.get("recovery_available"))
        ]
        if not positions:
            continue
        times = np.asarray([int(out[i]["T"]) for i in positions], dtype=np.int64)
        values = np.asarray(
            [float(out[i]["recovery_fraction"]) for i in positions],
            dtype=np.float64,
        )
        scores = rolling_midrank_percentile(
            values,
            timestamps_ms=times,
            lookback_ms=TRAIN_MS,
        )
        for pos, score in zip(positions, scores):
            value = float(score)
            out[pos]["structure_standing"] = value
            if math.isfinite(value):
                out[pos]["structure_state"] = (
                    STATE_HIGH if value >= STATE_CUTPOINT else STATE_LOW
                )
    return out


# ---------------------------------------------------------------------------
# STAGE E - target and H-specific score record
# ---------------------------------------------------------------------------
def horizon_returns(close, t_ms, H):
    """RET_H(T) = ln(close(T+H)/close(T)); NaN unless T+H is legal and on grid."""
    values = np.asarray(close, dtype=np.float64)
    times = np.asarray(t_ms, dtype=np.int64)
    h_steps = int(H) // HTF_MIN
    n = len(values)
    out = np.full(n, np.nan, dtype=np.float64)
    destination = np.arange(n) + h_steps
    ok = destination < n
    ok &= (times + int(H) * BAR_MS) < DEV_END_MS
    if not np.any(ok):
        return out
    idx = np.flatnonzero(ok)
    with np.errstate(divide="ignore", invalid="ignore"):
        out[idx] = np.log(values[destination[idx]] / values[idx])
    return out


def past_median_abs_return(abs_returns, H):
    """PAST_MEDIAN_ABS_RET_H(T): median |RET_H| over the preceding 30 calendar
    days on the 15m grid, restricted to references with ref_t + H <= T.

    On the contiguous grid that is exactly indices [i-REF_STEPS, i-h_steps]
    inclusive; the current record and every unresolved reference are excluded.
    """
    values = np.asarray(abs_returns, dtype=np.float64)
    h_steps = int(H) // HTF_MIN
    span = REF_STEPS - h_steps + 1
    n = len(values)
    out = np.full(n, np.nan, dtype=np.float64)
    if span <= 0 or n == 0:
        return out
    rolled = (
        pd.Series(values, copy=False)
        .rolling(span, min_periods=span)
        .median()
        .to_numpy()
    )
    source = np.arange(n) - h_steps
    ok = source >= span - 1
    out[ok] = rolled[source[ok]]
    return np.where(np.isfinite(out) & (out > 0.0), out, np.nan)


def build_score_records(events, frame15, H):
    """STAGE E: attach H to the immutable population; never re-rank it."""
    t_ms = np.asarray(frame15["t_ms"], dtype=np.int64)
    close = np.asarray(frame15["close"], dtype=np.float64)
    ret = horizon_returns(close, t_ms, H)
    scale = past_median_abs_return(np.abs(ret), H)
    out = []
    for event in events:
        record = dict(event)
        i = int(record["index"])
        raw = float(ret[i])
        denominator = float(scale[i])
        record["H"] = int(H)
        record["score_record_id"] = canonical_score_record_id(
            str(record["base_event_id"]),
            int(H),
        )
        record["raw_future_ret"] = raw
        record["target_scale"] = denominator
        if (
            math.isfinite(raw)
            and math.isfinite(denominator)
            and denominator > 0.0
            and bool(record.get("recovery_available"))
            and math.isfinite(float(record["final_depth"]))
        ):
            record["Y"] = float(record["d"]) * raw / denominator
        else:
            record["Y"] = float("nan")
        record["target_available"] = bool(math.isfinite(float(record["Y"])))
        record["scoreable"] = bool(
            record["target_available"] and scoring_eligible(int(record["T"]), int(H))
        )
        out.append(record)
    return out


# ---------------------------------------------------------------------------
# STAGE F - same-support OLS comparison
# ---------------------------------------------------------------------------
def ols_fit(design, target):
    """Deterministic full-rank unweighted OLS. No pseudoinverse, no fallback.

    Rank test: Cholesky of the Gram matrix `X'X`. Cholesky succeeds exactly
    when `X'X` is numerically positive definite, i.e. `X` has full column
    rank; it fails closed otherwise. The solve itself is `np.linalg.solve`
    on the same Gram matrix (LU, deterministic for fixed inputs). Columns
    are never dropped, never standardized, never regularized.
    """
    matrix = np.asarray(design, dtype=np.float64)
    y = np.asarray(target, dtype=np.float64)
    if matrix.ndim != 2 or y.ndim != 1 or matrix.shape[0] != y.shape[0]:
        return None
    if matrix.shape[0] < matrix.shape[1]:
        return None
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(y)):
        return None
    gram = matrix.T @ matrix
    moment = matrix.T @ y
    if not np.all(np.isfinite(gram)) or not np.all(np.isfinite(moment)):
        return None
    try:
        np.linalg.cholesky(gram)
    except np.linalg.LinAlgError:
        return None
    try:
        beta = np.linalg.solve(gram, moment)
    except np.linalg.LinAlgError:
        return None
    beta = np.asarray(beta, dtype=np.float64)
    if beta.shape != (matrix.shape[1],) or not np.all(np.isfinite(beta)):
        return None
    return beta


def _baseline_design(depth):
    values = np.asarray(depth, dtype=np.float64)
    return np.column_stack((np.ones(len(values), dtype=np.float64), values))


def _candidate_design(depth, recovery):
    depth_values = np.asarray(depth, dtype=np.float64)
    recovery_values = np.asarray(recovery, dtype=np.float64)
    return np.column_stack(
        (
            np.ones(len(depth_values), dtype=np.float64),
            depth_values,
            recovery_values,
        )
    )


def _side_mean(records, direction):
    values = [
        float(record["ae_improvement"])
        for record in records
        if str(record["direction"]) == direction
    ]
    if not values:
        return float("nan")
    return float(np.mean(np.asarray(values, dtype=np.float64)))


def structure_separation(records, direction=None):
    """median(BASE_RESIDUAL | HIGH) - median(BASE_RESIDUAL | LOW) on the exact
    same scored support (prereg MD section 16)."""
    subset = records
    if direction is not None:
        subset = [
            record for record in records if str(record["direction"]) == direction
        ]
    high = [
        float(record["base_residual"])
        for record in subset
        if record.get("structure_state") == STATE_HIGH
    ]
    low = [
        float(record["base_residual"])
        for record in subset
        if record.get("structure_state") == STATE_LOW
    ]
    if not high or not low:
        return float("nan")
    return float(
        np.median(np.asarray(high, dtype=np.float64))
        - np.median(np.asarray(low, dtype=np.float64))
    )


def week_bootstrap_interval(improvements, times, L, H):
    """UTC ISO-week block bootstrap of the pooled mean AE improvement."""
    values = np.asarray(improvements, dtype=np.float64)
    stamps = np.asarray(times, dtype=np.int64)
    if len(values) == 0:
        return float("nan"), float("nan")
    groups = defaultdict(list)
    for value, t in zip(values, stamps):
        groups[iso_week_id(int(t))].append(float(value))
    keys = sorted(groups)
    sums = np.asarray([sum(groups[key]) for key in keys], dtype=np.float64)
    counts = np.asarray([len(groups[key]) for key in keys], dtype=np.int64)
    if len(keys) == 0:
        return float("nan"), float("nan")
    draws = np.empty(N_BOOT, dtype=np.float64)
    for replicate in range(N_BOOT):
        rng = np.random.default_rng(
            seed_int((SEED_BOOT, replicate, int(L), int(H)))
        )
        sampled = rng.integers(0, len(keys), size=len(keys))
        denominator = int(np.sum(counts[sampled]))
        draws[replicate] = (
            float(np.sum(sums[sampled]) / denominator)
            if denominator > 0
            else float("nan")
        )
    finite = draws[np.isfinite(draws)]
    if len(finite) == 0:
        return float("nan"), float("nan")
    return (
        float(np.quantile(finite, BOOT_LOW_Q)),
        float(np.quantile(finite, BOOT_HIGH_Q)),
    )


def per_cell_conditions(
    *,
    mean_improvement,
    up_mean,
    down_mean,
    relative,
    bootstrap_lower,
    placebo_q95,
    separation_pooled,
    separation_up,
    separation_down,
):
    """The five frozen per-cell conditions. Zero is not positive; NaN fails."""
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
        "structure_ordering": bool(
            math.isfinite(separation_pooled)
            and math.isfinite(separation_up)
            and math.isfinite(separation_down)
            and separation_pooled > 0.0
            and separation_up > 0.0
            and separation_down > 0.0
        ),
    }


def evaluate_cell(events, frame15, L, H):
    """Score one frozen (L, H) cell under the same-support contract."""
    records = [
        record
        for record in build_score_records(events, frame15, H)
        if int(record["L"]) == int(L)
    ]
    constructed = len(records)
    usable = [record for record in records if bool(record["target_available"])]
    usable.sort(key=lambda item: (int(item["T"]), str(item["score_record_id"])))
    h_ms = int(H) * BAR_MS

    pools = defaultdict(list)
    mature = 0
    scored = []
    placebo_sums = np.zeros(N_PLACEBO, dtype=np.float64)

    for record in usable:
        current_t = int(record["T"])
        while mature < len(usable) and int(usable[mature]["T"]) + h_ms <= current_t:
            previous = usable[mature]
            pools[
                (int(previous["L"]), str(previous["direction"]))
            ].append(previous)
            mature += 1

        if not bool(record["scoreable"]):
            continue
        key = (int(record["L"]), str(record["direction"]))
        pool = pools[key]
        cutoff = current_t - TRAIN_MS
        while pool and int(pool[0]["T"]) < cutoff:
            pool.pop(0)
        if len(pool) < MIN_TRAIN_COUNT:
            continue

        pool_depth = np.asarray(
            [float(item["final_depth"]) for item in pool],
            dtype=np.float64,
        )
        pool_recovery = np.asarray(
            [float(item["recovery_fraction"]) for item in pool],
            dtype=np.float64,
        )
        pool_y = np.asarray([float(item["Y"]) for item in pool], dtype=np.float64)

        base_beta = ols_fit(_baseline_design(pool_depth), pool_y)
        cand_beta = ols_fit(
            _candidate_design(pool_depth, pool_recovery),
            pool_y,
        )
        if base_beta is None or cand_beta is None:
            continue

        depth = float(record["final_depth"])
        recovery = float(record["recovery_fraction"])
        y = float(record["Y"])
        base_pred = float(base_beta[0] + base_beta[1] * depth)
        cand_pred = float(
            cand_beta[0] + cand_beta[1] * depth + cand_beta[2] * recovery
        )
        if not (math.isfinite(base_pred) and math.isfinite(cand_pred)):
            continue

        base_ae = abs(y - base_pred)
        cand_ae = abs(y - cand_pred)
        entry = dict(record)
        entry.update(
            {
                "base_pred": base_pred,
                "candidate_pred": cand_pred,
                "base_ae": base_ae,
                "candidate_ae": cand_ae,
                "ae_improvement": base_ae - cand_ae,
                "base_residual": y - base_pred,
                "training_count": len(pool),
            }
        )
        scored.append(entry)

        ordered = sorted(pool, key=lambda item: str(item["score_record_id"]))
        ordered_depth = np.asarray(
            [float(item["final_depth"]) for item in ordered],
            dtype=np.float64,
        )
        ordered_recovery = np.asarray(
            [float(item["recovery_fraction"]) for item in ordered],
            dtype=np.float64,
        )
        ordered_y = np.asarray(
            [float(item["Y"]) for item in ordered],
            dtype=np.float64,
        )
        stratum = baseline_stratum_id(
            L=int(record["L"]),
            direction=str(record["direction"]),
        )
        for replicate in range(N_PLACEBO):
            rng = np.random.default_rng(
                seed_int(
                    (
                        SEED_PLACEBO,
                        replicate,
                        int(L),
                        int(H),
                        current_t,
                        stratum,
                    )
                )
            )
            permuted = rng.permutation(ordered_recovery)
            placebo_beta = ols_fit(
                _candidate_design(ordered_depth, permuted),
                ordered_y,
            )
            if placebo_beta is None:
                placebo_sums[replicate] = float("nan")
                continue
            placebo_pred = float(
                placebo_beta[0]
                + placebo_beta[1] * depth
                + placebo_beta[2] * recovery
            )
            if not math.isfinite(placebo_pred):
                placebo_sums[replicate] = float("nan")
                continue
            placebo_sums[replicate] += base_ae - abs(y - placebo_pred)

    return _summarize_cell(
        L=L,
        H=H,
        constructed=constructed,
        scored=scored,
        placebo_sums=placebo_sums,
    )


def _summarize_cell(*, L, H, constructed, scored, placebo_sums):
    improvements = np.asarray(
        [float(record["ae_improvement"]) for record in scored],
        dtype=np.float64,
    )
    base_ae = np.asarray(
        [float(record["base_ae"]) for record in scored],
        dtype=np.float64,
    )
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
    ci_low, ci_high = week_bootstrap_interval(improvements, times, L, H)
    up_mean = _side_mean(scored, "UP")
    down_mean = _side_mean(scored, "DOWN")
    separation_pooled = structure_separation(scored)
    separation_up = structure_separation(scored, "UP")
    separation_down = structure_separation(scored, "DOWN")

    placebo_means = (
        placebo_sums / len(scored)
        if len(scored)
        else np.full(N_PLACEBO, np.nan, dtype=np.float64)
    )
    placebo_finite = placebo_means[np.isfinite(placebo_means)]
    # Frozen procedure: placebo_q95 is the 95th percentile of the exact
    # frozen N_PLACEBO causal permutation replicates. A replicate that fails
    # to fit (singular/nonfinite candidate design) is not silently dropped
    # from the quantile population and not resampled with a replacement
    # replicate -- that would compute a percentile over a different,
    # implementation-dependent subset instead of the frozen 100. If fewer
    # than N_PLACEBO replicates are finite, the whole cell's placebo
    # comparison is unavailable and `placebo_separation` must fail, not pass
    # on a partial population.
    placebo_q95 = (
        float(np.quantile(placebo_finite, PLACEBO_Q))
        if len(placebo_finite) == N_PLACEBO
        else float("nan")
    )

    yearly = {}
    positive_years = 0
    for year in YEAR_BLOCKS:
        values = np.asarray(
            [
                float(record["ae_improvement"])
                for record in scored
                if utc_year(int(record["T"])) == year
            ],
            dtype=np.float64,
        )
        mean_year = float(np.mean(values)) if len(values) else float("nan")
        yearly[str(year)] = mean_year if math.isfinite(mean_year) else None
        if math.isfinite(mean_year) and mean_year > 0.0:
            positive_years += 1

    up_n = sum(1 for record in scored if str(record["direction"]) == "UP")
    down_n = sum(1 for record in scored if str(record["direction"]) == "DOWN")
    conditions = per_cell_conditions(
        mean_improvement=mean_improvement,
        up_mean=up_mean,
        down_mean=down_mean,
        relative=relative,
        bootstrap_lower=ci_low,
        placebo_q95=placebo_q95,
        separation_pooled=separation_pooled,
        separation_up=separation_up,
        separation_down=separation_down,
    )
    score_record_ids = [str(record["score_record_id"]) for record in scored]
    support_digest = hashlib.sha256(
        "\n".join(score_record_ids).encode("utf-8")
    ).hexdigest()

    return {
        "L": int(L),
        "H": int(H),
        "N": len(scored),
        "constructed_base_events": int(constructed),
        "UP_N": up_n,
        "DOWN_N": down_n,
        "mean_ae_improvement": mean_improvement if math.isfinite(mean_improvement) else None,
        "median_ae_improvement": (
            median_improvement if math.isfinite(median_improvement) else None
        ),
        "relative_mae_improvement": relative if math.isfinite(relative) else None,
        "bootstrap_lower_95": ci_low if math.isfinite(ci_low) else None,
        "bootstrap_upper_95": ci_high if math.isfinite(ci_high) else None,
        "placebo_q95": placebo_q95 if math.isfinite(placebo_q95) else None,
        "placebo_replicate_count_nominal": int(N_PLACEBO),
        "placebo_replicate_count_finite": int(len(placebo_finite)),
        "structure_separation_pooled": (
            separation_pooled if math.isfinite(separation_pooled) else None
        ),
        "structure_separation_up": (
            separation_up if math.isfinite(separation_up) else None
        ),
        "structure_separation_down": (
            separation_down if math.isfinite(separation_down) else None
        ),
        "up": {
            "N": up_n,
            "mean_ae_improvement": up_mean if math.isfinite(up_mean) else None,
            "structure_separation": (
                separation_up if math.isfinite(separation_up) else None
            ),
        },
        "down": {
            "N": down_n,
            "mean_ae_improvement": down_mean if math.isfinite(down_mean) else None,
            "structure_separation": (
                separation_down if math.isfinite(separation_down) else None
            ),
        },
        "yearly_mean_ae_improvement": yearly,
        "positive_years": int(positive_years),
        "year_stability_pass": bool(positive_years >= MIN_POSITIVE_YEARS),
        "per_cell_conditions": conditions,
        "same_support": {
            "baseline_score_record_ids_equal_candidate": True,
            "score_record_count": len(score_record_ids),
            "score_record_digest_sha256": support_digest,
        },
        "score_record_ids": score_record_ids,
        "scored": scored,
    }


def _cell_five_pass(cell):
    conditions = cell.get("per_cell_conditions")
    if not isinstance(conditions, Mapping):
        return False
    return all(conditions.get(name) is True for name in PER_CELL_GATE_NAMES)


def determine_promotion_gates(cells):
    """Eight frozen gates; a neighborhood is one adjacent-H pair at two L."""
    by_key = {
        (int(cell["L"]), int(cell["H"])): cell
        for cell in cells
        if "L" in cell and "H" in cell
    }
    per_gate_evidence = {name: False for name in PER_CELL_GATE_NAMES}
    horizon_robustness = False
    parameter_robustness = False
    year_stability = False
    neighborhoods = []

    for h1, h2 in ADJACENT_H_PAIRS:
        per_gate_L = {name: [] for name in PER_CELL_GATE_NAMES}
        core_L = []
        stable_L = []
        for L in L_VALUES:
            c1 = by_key.get((L, h1))
            c2 = by_key.get((L, h2))
            if c1 is None or c2 is None:
                continue
            g1 = c1.get("per_cell_conditions")
            g2 = c2.get("per_cell_conditions")
            for name in PER_CELL_GATE_NAMES:
                if (
                    isinstance(g1, Mapping)
                    and isinstance(g2, Mapping)
                    and g1.get(name) is True
                    and g2.get(name) is True
                ):
                    per_gate_L[name].append(int(L))
            if _cell_five_pass(c1) and _cell_five_pass(c2):
                horizon_robustness = True
                core_L.append(int(L))
                if (
                    c1.get("year_stability_pass") is True
                    and c2.get("year_stability_pass") is True
                ):
                    stable_L.append(int(L))
        for name, passing in per_gate_L.items():
            if len(passing) >= 2:
                per_gate_evidence[name] = True
        if len(core_L) >= 2:
            parameter_robustness = True
        if len(stable_L) >= 2:
            year_stability = True
            neighborhoods.append(
                {
                    "H_pair": [h1, h2],
                    "L": list(stable_L),
                    "cells": [
                        {"L": L, "H": h} for L in stable_L for h in (h1, h2)
                    ],
                }
            )

    neighborhoods.sort(key=lambda item: (item["H_pair"], item["L"]))
    gates = {
        **per_gate_evidence,
        "horizon_robustness": horizon_robustness,
        "parameter_robustness": parameter_robustness,
        "year_stability": year_stability,
    }
    return gates, neighborhoods


# ---------------------------------------------------------------------------
# forbidden-window evidence + top-level evaluation
# ---------------------------------------------------------------------------
def _partition_year(relative_path):
    leaf = str(relative_path).rsplit("/", 1)[-1]
    head = leaf.split("-", 1)[0]
    if len(head) != 4 or not head.isdigit():
        raise B204Error(
            f"authorized partition path is not a canonical monthly leaf: {relative_path}"
        )
    return int(head)


def derive_forbidden_window_evidence(run_identity, frame):
    """Prove 2025/2026 were not reached from the authorized view only."""
    window = run_identity.get("window")
    if not isinstance(window, Mapping):
        raise B204Error("run identity is missing its authorized window evidence")
    try:
        end_exclusive_ms = int(window["end_exclusive_ms"])
        start_inclusive_ms = int(window["start_inclusive_ms"])
        allowed_years = tuple(int(year) for year in window["allowed_years"])
    except (KeyError, TypeError, ValueError) as exc:
        raise B204Error("authorized window evidence is malformed") from exc
    if not allowed_years:
        raise B204Error("authorized window evidence has an empty allowed_years")

    partitions = run_identity.get("partitions")
    if not isinstance(partitions, Sequence) or isinstance(partitions, (str, bytes)):
        raise B204Error("run identity is missing its authorized partition evidence")
    partition_years = []
    for partition in partitions:
        if not isinstance(partition, Mapping) or "relative_path" not in partition:
            raise B204Error("authorized partition evidence is malformed")
        partition_years.append(_partition_year(str(partition["relative_path"])))
    if not partition_years:
        raise B204Error("authorized partition evidence is empty")

    open_ms = np.asarray(frame["open_time_ms"], dtype=np.int64)
    avail_ms = np.asarray(frame["available_at_ms"], dtype=np.int64)
    if len(open_ms) == 0:
        raise B204Error("loaded development frame is empty")

    if end_exclusive_ms > VALIDATION_2025_START_MS:
        raise B204Error("authorized window reaches the reserved 2025 validation pool")
    if max(allowed_years) >= FIRST_FORBIDDEN_YEAR:
        raise B204Error("authorized years reach a forbidden window")
    if max(partition_years) >= FIRST_FORBIDDEN_YEAR:
        raise B204Error("authorized partitions reach a forbidden window")
    if int(np.max(avail_ms)) > VALIDATION_2025_START_MS:
        raise B204Error("loaded development bytes reach the reserved 2025 pool")

    return {
        "2025_validation": False,
        "2026_oos": False,
        "derivation": "authorized-view-and-loaded-bytes",
        "authorized_window_start_inclusive_ms": start_inclusive_ms,
        "authorized_window_end_exclusive_ms": end_exclusive_ms,
        "authorized_allowed_years": list(allowed_years),
        "authorized_partition_count": len(partition_years),
        "authorized_max_partition_year": max(partition_years),
        "observed_min_open_time_ms": int(np.min(open_ms)),
        "observed_max_open_time_ms": int(np.max(open_ms)),
        "observed_max_available_at_ms": int(np.max(avail_ms)),
        "validation_2025_start_ms": VALIDATION_2025_START_MS,
        "oos_2026_start_ms": OOS_2026_START_MS,
    }


def evaluate_b2_04(frame_1m):
    """Full frozen 15-cell B2-04 surface from one authorized 1m frame."""
    validate_1m_frame(frame_1m)
    frame15 = aggregate_1m_to_15m(frame_1m)
    constructed = construct_events(frame15)
    with_recovery = attach_recovery(constructed, frame15)
    events = attach_structure_state(with_recovery)

    cells = [
        evaluate_cell(events, frame15, L, H)
        for L in L_VALUES
        for H in H_VALUES
    ]
    for cell in cells:
        cell.pop("scored", None)
    gates, neighborhoods = determine_promotion_gates(cells)
    passed = bool(neighborhoods) and all(
        gates.get(name) is True for name in GATE_NAMES
    )

    refractory_counts = {}
    for L in L_VALUES:
        refractory_counts[str(L)] = sum(
            1 for event in constructed if int(event["L"]) == int(L)
        )

    return {
        "hypothesis_id": HYPOTHESIS_ID,
        "primary_family": PRIMARY_FAMILY,
        "posthoc_provenance": POSTHOC_PROVENANCE,
        "prereg_merge_sha": PREREG_MERGE_SHA,
        "h04_verdict": H04_VERDICT,
        "structural_property": {
            "family": STRUCTURAL_PROPERTY_FAMILY,
            "name": STRUCTURAL_PROPERTY_NAME,
            "count": 1,
        },
        "dataset_id": DATASET_ID,
        "snapshot_id": REQUIRED_SNAPSHOT,
        "stage": "development",
        "search_surface": {
            "lookbacks_minutes": list(L_VALUES),
            "horizons_minutes": list(H_VALUES),
            "moderate_domain": [MODERATE_LO, MODERATE_HI],
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
        "constructed_base_events": len(constructed),
        "refractory_selected_by_L": refractory_counts,
        "recovery_available_events": sum(
            1 for event in events if bool(event.get("recovery_available"))
        ),
        "cells": cells,
        "promotion": {
            "gates": gates,
            "required_gate_names": list(GATE_NAMES),
            "qualifying_neighborhoods": neighborhoods,
            "passed": passed,
            "verdict": VERDICT_PROMOTED if passed else VERDICT_CLOSED,
        },
    }
