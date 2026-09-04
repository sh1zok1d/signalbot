"""Outcome-blind B2-05 flow-absorption numerical implementation.

Implements the frozen B2-05 preregistration
(`docs/research/B2_05_FLOW_ABSORPTION_PREREG.md` / `.json`) using only
in-memory arrays. This module never opens files, enumerates datasets, talks
to Git/network, creates evidence reservations, or persists results.

Frozen contract summary implemented here (prereg section in brackets):

- source 1m, decision grid UTC-aligned 15m; W in {15,30,60}; H in
  {30,60,120,240}; every 15m grid point is a candidate record for every W
  -- no threshold event selection, no refractory stage [prereg S2-5];
- TOTAL_W/TAKER_BUY_W/IMB/ABS_IMB with row-level fail-closed integrity;
  IMB==0 makes the record unavailable [prereg S5];
- baseline causal controls FLOW_RET/RV_W/LOG_ACTIVITY [prereg S6];
- exactly one structural object IMPACT_INTERACTION = ABS_IMB * FLOW_RET
  [prereg S7];
- causal 180-day same-(W,side) impact state (midrank tertiles, min N=120)
  [prereg S8];
- target Y_H = FLOW_CONT_RET_H / PAST_MEDIAN_ABS_RET_H over the canonical
  aligned 15m grid (30-day scale reference, not B2-05 records) [prereg S9];
- weekly (UTC ISO week start) walk-forward causal OLS: baseline 6 features
  (intercept, ABS_IMB, FLOW_RET, RV_W, LOG_ACTIVITY, SIDE_BUY), candidate
  adds IMPACT_LOW/IMPACT_HIGH (MID reference); numpy.linalg.lstsq(rcond=None)
  exactly, no normal-equation substitution [prereg S10, S13];
- causal 180-day same-(W,side) nuisance quintile bins for ABS_IMB and
  FLOW_RET, used only to match placebo permutation strata [prereg S16];
- placebo (N=100, seed 20260907) permutes real candidate training IMPACT_STATE
  labels within (month, side, ABS_IMB quintile, FLOW_RET quintile) strata;
  fail-closed all-100-finite-or-unavailable rule [prereg S17-18];
- UTC ISO-week block bootstrap (N=2000, seed 20260908) [prereg S19];
- six per-cell conditions and nine promotion gates over a 3W x 4H = 12 cell
  surface [prereg S20-26].

This module deliberately does not use `from __future__ import annotations`:
the merged Batch02 static source policy default-denies every non-repository
import that is not on its explicit transform allowlist, and B2-0x source is
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


HYPOTHESIS_ID = "B2-05_FLOW_ABSORPTION"
DATASET_ID = "CORE_BTC_BINANCE_V0"
REQUIRED_SNAPSHOT = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
PREREG_MERGE_SHA = "4f1cb72473425dd7fcace0987be99d0950a2920d"
PRIMARY_FAMILY = "F4"
CANONICAL_PREREG_JSON_SHA256 = (
    "34e8412684ecf14fa802b5a412b4d26bb6894d835ff0b6f8ae99b1d725e759ea"
)

BAR_MS = 60_000
HTF_MIN = 15
HTF_MS = HTF_MIN * BAR_MS
DAY_MS = 24 * 60 * BAR_MS

W_VALUES = (15, 30, 60)
H_VALUES = (30, 60, 120, 240)
ADJACENT_H_PAIRS = ((30, 60), (60, 120), (120, 240))
PRIMARY_CELLS = 12

IMPACT_REF_DAYS = 180
IMPACT_REF_MS = IMPACT_REF_DAYS * DAY_MS
MIN_IMPACT_REF_N = 120

NUISANCE_REF_DAYS = 180
NUISANCE_REF_MS = NUISANCE_REF_DAYS * DAY_MS
MIN_NUISANCE_REF_N = 120

SCALE_REF_DAYS = 30
SCALE_REF_STEPS = SCALE_REF_DAYS * 24 * 60 // HTF_MIN

TRAIN_DAYS = 365
TRAIN_MS = TRAIN_DAYS * DAY_MS
MIN_BASELINE_N = 500
MIN_CANDIDATE_N = 500
MIN_CANDIDATE_N_PER_STATE = 100

RELATIVE_MAE_MIN = 0.02
PLACEBO_Q = 0.95
N_PLACEBO = 100
SEED_PLACEBO = 20260907
N_BOOT = 2000
SEED_BOOT = 20260908
BOOT_LOW_Q = 0.025
BOOT_HIGH_Q = 0.975

WARMUP_START_MS = 1_577_836_800_000  # 2020-01-01T00:00:00Z
DEV_START_MS = 1_580_515_200_000  # 2020-02-01T00:00:00Z
DEV_END_MS = 1_735_689_600_000  # 2025-01-01T00:00:00Z
VALIDATION_2025_START_MS = DEV_END_MS
OOS_2026_START_MS = 1_767_225_600_000  # 2026-01-01T00:00:00Z
FIRST_FORBIDDEN_YEAR = 2025
YEAR_BLOCKS = (2020, 2021, 2022, 2023, 2024)
MIN_POSITIVE_YEARS = 4

SIDE_BUY = "BUY"
SIDE_SELL = "SELL"
SIDE_LABELS = {1: SIDE_BUY, -1: SIDE_SELL}
STATE_LOW = "LOW"
STATE_MID = "MID"
STATE_HIGH = "HIGH"
STATE_LOW_CUT = 1.0 / 3.0
STATE_HIGH_CUT = 2.0 / 3.0
STATE_LABEL_CODE = {STATE_LOW: 0, STATE_MID: 1, STATE_HIGH: 2}
STATE_CODE_LABEL = {0: STATE_LOW, 1: STATE_MID, 2: STATE_HIGH}

QUINTILE_LABELS = ("Q1", "Q2", "Q3", "Q4", "Q5")
QUINTILE_CUTS = (0.2, 0.4, 0.6, 0.8)

GATE_NAMES = (
    "primary_positive",
    "material_relative_mae",
    "bootstrap_positive",
    "placebo_separation",
    "impact_ordering",
    "side_stability",
    "horizon_robustness",
    "parameter_robustness",
    "year_stability",
)
PER_CELL_GATE_NAMES = GATE_NAMES[:6]

VERDICT_PROMOTED = "B2_05_PROMOTED_CANDIDATE"
VERDICT_CLOSED = "B2_05_CLOSED_NO_PROMOTION"

REQUIRED_SOURCE_COLUMNS = (
    "open_time_ms",
    "available_at_ms",
    "close",
    "base_volume",
    "taker_buy_base_volume",
)


class B205Error(RuntimeError):
    """B2-05 implementation input/invariant error."""


# ---------------------------------------------------------------------------
# frozen chronology helpers
# ---------------------------------------------------------------------------
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


def utc_year_month(ms):
    y, m, _d = _civil_from_days(int(ms) // DAY_MS)
    return int(y), int(m)


def iso_week_id(ms):
    """ISO week-numbering year * 100 + ISO week (UTC), matching
    `datetime.isocalendar()` semantics. The Gregorian calendar year is
    deliberately not used (prereg controls.bootstrap_week_id)."""
    days = int(ms) // DAY_MS
    weekday = ((days + 3) % 7) + 1
    thursday = days - (weekday - 4)
    iso_year = _civil_from_days(thursday)[0]
    jan1 = _days_from_civil(iso_year, 1, 1)
    week = (thursday - jan1) // 7 + 1
    return int(iso_year) * 100 + int(week)


def iso_week_start_ms(ms):
    """UTC epoch ms of the Monday 00:00:00Z that begins T's ISO week."""
    days = int(ms) // DAY_MS
    weekday = ((days + 3) % 7) + 1  # Monday=1 .. Sunday=7
    monday_days = days - (weekday - 1)
    return int(monday_days) * DAY_MS


def seed_int(parts):
    """SHA-256(pipe-joined str(part)) -> first 8 raw digest bytes -> unsigned
    big-endian uint64. Frozen primitive (prereg controls.seed_derivation_primitive):
    no alternate hash, no alternate byte order, no alternate digest slice."""
    raw = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(raw).digest()[:8]
    return int.from_bytes(digest, "big", signed=False)


# ---------------------------------------------------------------------------
# canonical identity
# ---------------------------------------------------------------------------
def canonical_base_event_id(*, W, side, T_ms, snapshot_id=REQUIRED_SNAPSHOT):
    """snapshot_id|1m|15m|W_minutes|side|interval_start_ms|interval_end_ms|T_ms."""
    if side not in (SIDE_BUY, SIDE_SELL):
        raise B205Error("canonical event side must be BUY or SELL")
    t = int(T_ms)
    w = int(W)
    interval_start = t - w * BAR_MS
    return "|".join(
        (
            str(snapshot_id),
            "1m",
            "15m",
            str(w),
            str(side),
            str(interval_start),
            str(t),
            str(t),
        )
    )


def canonical_score_record_id(base_event_id, H):
    """CANONICAL_SCORE_RECORD_ID = CANONICAL_BASE_EVENT_ID|H_minutes."""
    if int(H) not in H_VALUES:
        raise B205Error("horizon is not in the frozen H set")
    return "|".join((str(base_event_id), str(int(H))))


def permutation_stratum_id(*, T_e_ms, side, abs_imb_quintile, flow_ret_quintile):
    if side not in (SIDE_BUY, SIDE_SELL):
        raise B205Error("stratum side must be BUY or SELL")
    if abs_imb_quintile not in QUINTILE_LABELS or flow_ret_quintile not in QUINTILE_LABELS:
        raise B205Error("stratum requires a valid quintile label for both nuisance bins")
    year, month = utc_year_month(T_e_ms)
    return "{:04d}-{:02d}|SIDE={}|IMB_Q={}|FLOW_Q={}".format(
        int(year), int(month), side, abs_imb_quintile, flow_ret_quintile
    )


# ---------------------------------------------------------------------------
# authorized in-memory frame conversion
# ---------------------------------------------------------------------------
def _finite_price(value, label):
    try:
        out = float(Decimal(str(value)))
    except Exception as exc:
        raise B205Error(f"{label} is not a valid decimal price") from exc
    if not math.isfinite(out) or out <= 0.0:
        raise B205Error(f"{label} must be finite and > 0")
    return out


def _coerce_volume(value):
    """Volume columns tolerate non-finite/negative values: they fail closed
    per-row (prereg flow.malformed_row_policy), they never hard-fail frame
    conversion."""
    try:
        return float(Decimal(str(value)))
    except Exception:
        return float("nan")


def table_to_1m_frame(table):
    """Convert an authorized Arrow table without any direct file access."""
    values = {}
    for name in ("open_time_ms", "available_at_ms"):
        try:
            column = table.column(name)
        except Exception as exc:
            raise B205Error(f"authorized table missing canonical column {name}") from exc
        try:
            raw = column.to_numpy(zero_copy_only=False)
        except Exception as exc:
            raise B205Error(
                f"authorized column {name} is not convertible in memory"
            ) from exc
        try:
            values[name] = np.asarray(raw, dtype=np.int64)
        except (TypeError, ValueError) as exc:
            raise B205Error(
                f"authorized column {name} is not integer milliseconds"
            ) from exc

    try:
        close_column = table.column("close")
    except Exception as exc:
        raise B205Error("authorized table missing canonical column close") from exc
    close_raw = close_column.to_numpy(zero_copy_only=False)
    values["close"] = np.asarray(
        [_finite_price(v, "close") for v in close_raw], dtype=np.float64
    )

    for name in ("base_volume", "taker_buy_base_volume"):
        try:
            column = table.column(name)
        except Exception as exc:
            raise B205Error(f"authorized table missing canonical column {name}") from exc
        raw = column.to_numpy(zero_copy_only=False)
        values[name] = np.asarray([_coerce_volume(v) for v in raw], dtype=np.float64)

    validate_1m_frame(values)
    return values


def validate_1m_frame(frame):
    columns = ("open_time_ms", "available_at_ms", "close", "base_volume", "taker_buy_base_volume")
    if any(name not in frame for name in columns):
        raise B205Error("1m frame missing a required canonical column")
    arrays = {name: np.asarray(frame[name]) for name in columns}
    n = len(arrays["open_time_ms"])
    if n == 0 or any(a.ndim != 1 or len(a) != n for a in arrays.values()):
        raise B205Error("1m columns must be equal non-empty one-dimensional arrays")
    open_ms = arrays["open_time_ms"].astype(np.int64, copy=False)
    avail = arrays["available_at_ms"].astype(np.int64, copy=False)
    close = arrays["close"].astype(np.float64, copy=False)
    if not np.all(np.isfinite(close)) or np.any(close <= 0.0):
        raise B205Error("close must be finite and strictly positive")
    if (
        int(np.max(open_ms)) >= DEV_END_MS
        or int(np.max(avail)) > VALIDATION_2025_START_MS
        or int(np.min(open_ms)) >= DEV_END_MS
        or int(np.min(avail)) > VALIDATION_2025_START_MS
    ):
        raise B205Error("1m frame reaches reserved 2025+ source data")
    if int(open_ms[0]) % HTF_MS != 0:
        raise B205Error("1m frame must start on a UTC 15m boundary")
    if n % HTF_MIN != 0:
        raise B205Error("1m frame length must be a whole number of 15m buckets")
    expected = int(open_ms[0]) + np.arange(n, dtype=np.int64) * BAR_MS
    if np.any(open_ms != expected):
        raise B205Error("1m open_time_ms must be a contiguous minute grid")
    if np.any(avail != open_ms + BAR_MS):
        raise B205Error("available_at_ms must equal open_time_ms + 60000")


def aggregate_1m_to_15m(frame_1m):
    """T is the bar-end-exclusive of the 15m bucket [T-15m, T).

    close(T) is the close of the final canonical 1m bar whose own
    bar-end-exclusive equals T. There is no off-by-one discretion: this is
    the only place the 1m -> 15m close is chosen (matching the B2-04
    precedent for the same underlying dataset/grid convention).
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
        raise B205Error("15m available_at is not the last 1m available_at in the bucket")
    if len(t_ms) != n15 or len(bucket_close) != n15:
        raise B205Error("15m aggregation produced an inconsistent bucket count")
    return {"t_ms": t_ms, "close": bucket_close}


# ---------------------------------------------------------------------------
# causal reference counting (time-window mode companion to
# rolling_midrank_percentile, which does not itself expose a minimum-N gate)
# ---------------------------------------------------------------------------
def causal_reference_count(times_ms, lookback_ms):
    """Count of strictly-earlier references within `lookback_ms`, inclusive
    lower bound, current index excluded. `times_ms` must be strictly
    increasing (same contract as `rolling_midrank_percentile`'s time-window
    mode). O(n) two-pointer sweep -- no bisect/searchsorted/rank primitive."""
    times = np.asarray(times_ms, dtype=np.int64)
    n = len(times)
    if n > 1 and np.any(times[1:] <= times[:-1]):
        raise B205Error("causal_reference_count requires strictly increasing timestamps")
    counts = np.zeros(n, dtype=np.int64)
    left = 0
    duration = int(lookback_ms)
    for i in range(n):
        cutoff = int(times[i]) - duration
        while left < i and int(times[left]) < cutoff:
            left += 1
        counts[i] = i - left
    return counts


# ---------------------------------------------------------------------------
# STAGE A - per-W flow construction (no refractory, no threshold selection)
# ---------------------------------------------------------------------------
def build_flow_frame(frame_1m, W, close15, t_ms15):
    """Every 15m grid point is a candidate flow record for this W.

    Vectorized rolling-sum construction: TOTAL_W/TAKER_BUY_W/RV_W use
    prefix-sum arrays over the full 1m bar array, indexed once per 15m grid
    point -- O(n) precompute, O(1) per point, equivalent to (and verified
    against) a brute-force per-window re-sum oracle in the test suite.
    """
    validate_1m_frame(frame_1m)
    w_minutes = int(W)
    if w_minutes not in W_VALUES:
        raise B205Error("W is not in the frozen flow-window set")

    open_ms = np.asarray(frame_1m["open_time_ms"], dtype=np.int64)
    close = np.asarray(frame_1m["close"], dtype=np.float64)
    base_volume = np.asarray(frame_1m["base_volume"], dtype=np.float64)
    taker_buy = np.asarray(frame_1m["taker_buy_base_volume"], dtype=np.float64)
    n = len(open_ms)
    n15 = n // HTF_MIN
    if len(close15) != n15 or len(t_ms15) != n15:
        raise B205Error("close15/t_ms15 do not match the 1m frame's 15m aggregation")

    row_ok = (
        np.isfinite(base_volume)
        & np.isfinite(taker_buy)
        & (base_volume >= 0.0)
        & (taker_buy >= 0.0)
        & (taker_buy <= base_volume)
    )
    safe_base = np.where(row_ok, base_volume, 0.0)
    safe_taker = np.where(row_ok, taker_buy, 0.0)
    cumsum_base = np.concatenate(([0.0], np.cumsum(safe_base)))
    cumsum_taker = np.concatenate(([0.0], np.cumsum(safe_taker)))
    cumsum_invalid = np.concatenate(([0], np.cumsum((~row_ok).astype(np.int64))))

    sq_ret_full = np.zeros(n, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        sq_ret_full[1:] = np.square(np.log(close[1:] / close[:-1]))
    cumsum_sqret = np.concatenate(([0.0], np.cumsum(sq_ret_full)))

    i_end = np.arange(n15, dtype=np.int64) * HTF_MIN + (HTF_MIN - 1)
    start_idx = i_end - w_minutes + 1
    prior_idx = i_end - w_minutes
    window_ok_shape = (prior_idx >= 0) & (start_idx >= 0)

    total_w = np.full(n15, np.nan, dtype=np.float64)
    taker_buy_w = np.full(n15, np.nan, dtype=np.float64)
    rv_w = np.full(n15, np.nan, dtype=np.float64)
    flow_ret_raw = np.full(n15, np.nan, dtype=np.float64)

    ok_idx = np.flatnonzero(window_ok_shape)
    if ok_idx.size:
        se = start_idx[ok_idx]
        ee = i_end[ok_idx]
        pe = prior_idx[ok_idx]
        invalid_in_window = cumsum_invalid[ee + 1] - cumsum_invalid[se]
        window_clean = invalid_in_window == 0
        clean_idx = ok_idx[window_clean]
        se_c = start_idx[clean_idx]
        ee_c = i_end[clean_idx]
        total_w[clean_idx] = cumsum_base[ee_c + 1] - cumsum_base[se_c]
        taker_buy_w[clean_idx] = cumsum_taker[ee_c + 1] - cumsum_taker[se_c]
        rv_sq = cumsum_sqret[ee + 1] - cumsum_sqret[se + 1]
        with np.errstate(invalid="ignore"):
            rv_w[ok_idx] = np.sqrt(rv_sq)
        with np.errstate(divide="ignore", invalid="ignore"):
            flow_ret_raw[ok_idx] = np.log(close[ee] / close[pe])

    total_w_valid = np.isfinite(total_w) & (total_w > 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        imb = np.where(total_w_valid, (2.0 * taker_buy_w - total_w) / total_w, np.nan)
        log_activity = np.where(total_w_valid, np.log(total_w), np.nan)
    side_code = np.zeros(n15, dtype=np.int8)
    side_code[np.isfinite(imb) & (imb > 0.0)] = 1
    side_code[np.isfinite(imb) & (imb < 0.0)] = -1
    abs_imb = np.where(side_code != 0, np.abs(imb), np.nan)
    d = side_code.astype(np.float64)
    flow_ret = np.where(
        (side_code != 0) & np.isfinite(flow_ret_raw), d * flow_ret_raw, np.nan
    )
    rv_valid = np.isfinite(rv_w) & (rv_w > 0.0)
    impact_interaction = np.where(
        (side_code != 0) & np.isfinite(abs_imb) & np.isfinite(flow_ret),
        abs_imb * flow_ret,
        np.nan,
    )

    valid_features = (
        total_w_valid
        & (side_code != 0)
        & rv_valid
        & np.isfinite(log_activity)
        & np.isfinite(flow_ret)
        & np.isfinite(impact_interaction)
    )

    interval_start_ms = t_ms15 - w_minutes * BAR_MS

    return {
        "W": w_minutes,
        "t_ms": np.asarray(t_ms15, dtype=np.int64),
        "close": np.asarray(close15, dtype=np.float64),
        "interval_start_ms": interval_start_ms,
        "total_w": total_w,
        "taker_buy_w": taker_buy_w,
        "imb": imb,
        "side_code": side_code,
        "abs_imb": abs_imb,
        "flow_ret": flow_ret,
        "rv_w": rv_w,
        "log_activity": log_activity,
        "impact_interaction": impact_interaction,
        "valid_features": valid_features,
        # attached below by attach_impact_state / attach_nuisance_bins
        "impact_percentile": np.full(n15, np.nan, dtype=np.float64),
        "impact_state": np.array([None] * n15, dtype=object),
        "abs_imb_quintile": np.array([None] * n15, dtype=object),
        "flow_ret_quintile": np.array([None] * n15, dtype=object),
    }


def _causal_standing_by_side(t_ms, side_code, values, *, lookback_ms, min_ref_n):
    """Per-(side) causal midrank percentile of `values`, NaN where the
    finite-value reference count is below `min_ref_n` (prereg S8/S16 min N).
    """
    n = len(t_ms)
    out = np.full(n, np.nan, dtype=np.float64)
    for side_value in (1, -1):
        side_idx = np.flatnonzero(side_code == side_value)
        if side_idx.size == 0:
            continue
        finite_mask = np.isfinite(values[side_idx])
        f_idx = side_idx[finite_mask]
        if f_idx.size == 0:
            continue
        f_times = t_ms[f_idx]
        f_values = values[f_idx]
        pct = rolling_midrank_percentile(
            f_values, timestamps_ms=f_times, lookback_ms=int(lookback_ms)
        )
        counts = causal_reference_count(f_times, int(lookback_ms))
        pct = np.where(counts >= int(min_ref_n), pct, np.nan)
        out[f_idx] = pct
    return out


def _tertile_state(pct):
    if not math.isfinite(pct):
        return None
    if pct < STATE_LOW_CUT:
        return STATE_LOW
    if pct < STATE_HIGH_CUT:
        return STATE_MID
    return STATE_HIGH


def _quintile_label(pct):
    if not math.isfinite(pct):
        return None
    for cut, label in zip(QUINTILE_CUTS, QUINTILE_LABELS):
        if pct < cut:
            return label
    return QUINTILE_LABELS[-1]


def attach_impact_state(flow):
    """Causal 180-day same-(W,side) IMPACT_STATE tertiles (prereg S8)."""
    pct = _causal_standing_by_side(
        flow["t_ms"],
        flow["side_code"],
        flow["impact_interaction"],
        lookback_ms=IMPACT_REF_MS,
        min_ref_n=MIN_IMPACT_REF_N,
    )
    flow["impact_percentile"] = pct
    flow["impact_state"] = np.array(
        [_tertile_state(float(p)) for p in pct], dtype=object
    )
    return flow


def attach_nuisance_bins(flow):
    """Causal 180-day same-(W,side) ABS_IMB/FLOW_RET quintile bins used only
    to build placebo permutation strata (prereg S16); never enter the
    candidate design matrix."""
    abs_pct = _causal_standing_by_side(
        flow["t_ms"],
        flow["side_code"],
        flow["abs_imb"],
        lookback_ms=NUISANCE_REF_MS,
        min_ref_n=MIN_NUISANCE_REF_N,
    )
    flow_pct = _causal_standing_by_side(
        flow["t_ms"],
        flow["side_code"],
        flow["flow_ret"],
        lookback_ms=NUISANCE_REF_MS,
        min_ref_n=MIN_NUISANCE_REF_N,
    )
    flow["abs_imb_quintile"] = np.array(
        [_quintile_label(float(p)) for p in abs_pct], dtype=object
    )
    flow["flow_ret_quintile"] = np.array(
        [_quintile_label(float(p)) for p in flow_pct], dtype=object
    )
    return flow


# ---------------------------------------------------------------------------
# STAGE B - target (W-independent price-grid scale reference)
# ---------------------------------------------------------------------------
def scoring_eligible(T_ms, H):
    t = int(T_ms)
    h = int(H)
    if t % HTF_MS != 0:
        return False
    if t < DEV_START_MS or t >= DEV_END_MS:
        return False
    return t + h * BAR_MS < DEV_END_MS


def horizon_returns(close15, t_ms15, H):
    """RET_H(T) = ln(close(T+H)/close(T)); NaN unless T+H is legal and on grid."""
    values = np.asarray(close15, dtype=np.float64)
    times = np.asarray(t_ms15, dtype=np.int64)
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
    """PAST_MEDIAN_ABS_RET_H(T): median |ln(close(t+H)/close(t))| over the
    preceding 30 calendar days on the 15m grid, restricted to references
    with ref_t + H <= T. Observation population is the full canonical
    aligned 15m grid, never B2-05 flow/trigger records (prereg
    target.scale_reference)."""
    values = np.asarray(abs_returns, dtype=np.float64)
    h_steps = int(H) // HTF_MIN
    span = SCALE_REF_STEPS - h_steps + 1
    n = len(values)
    out = np.full(n, np.nan, dtype=np.float64)
    if span <= 0 or n == 0:
        return out
    # Vectorized rolling median (pandas `min_periods=span` requires every
    # value in the window to be non-NaN, so a window touching even one
    # illegal/immature reference correctly yields NaN -- fail-closed,
    # matching the brute-force per-window oracle proven equivalent in the
    # test suite). O(n log span) instead of the O(n * span log span)
    # brute-force per-window re-sort this replaces.
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


# ---------------------------------------------------------------------------
# STAGE C - OLS: exact frozen historical primitive
# ---------------------------------------------------------------------------
def ols_fit(design, target):
    """numpy.linalg.lstsq(X, y, rcond=None), exactly as frozen by the old
    outcome-blind design (prereg ols_solver_contract). Full column rank and
    all-finite coefficients required; no pseudoinverse, no normal-equation
    substitution, no fallback."""
    matrix = np.asarray(design, dtype=np.float64)
    y = np.asarray(target, dtype=np.float64)
    if matrix.ndim != 2 or y.ndim != 1 or matrix.shape[0] != y.shape[0]:
        return None
    if matrix.shape[0] < matrix.shape[1]:
        return None
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(y)):
        return None
    try:
        lstsq_result = np.linalg.lstsq(matrix, y, rcond=None)
    except np.linalg.LinAlgError:
        return None
    coef = lstsq_result[0]
    if int(lstsq_result[2]) != matrix.shape[1]:
        return None
    coef = np.asarray(coef, dtype=np.float64)
    if coef.shape != (matrix.shape[1],) or not np.all(np.isfinite(coef)):
        return None
    return coef


BASELINE_COLUMNS = ("ABS_IMB", "FLOW_RET", "RV_W", "LOG_ACTIVITY")


def _standardize(pool_matrix):
    """mean/std per continuous column over the pool; requires finite std>0."""
    mean = np.mean(pool_matrix, axis=0)
    std = np.std(pool_matrix, axis=0, ddof=0)
    if not np.all(np.isfinite(mean)) or not np.all(np.isfinite(std)) or np.any(std <= 0.0):
        return None, None
    return mean, std


def _baseline_design(z_cols, side_buy):
    n = z_cols.shape[0]
    return np.column_stack(
        (np.ones(n, dtype=np.float64), z_cols, side_buy.astype(np.float64))
    )


def _candidate_design(z_cols, side_buy, impact_low, impact_high):
    n = z_cols.shape[0]
    return np.column_stack(
        (
            np.ones(n, dtype=np.float64),
            z_cols,
            side_buy.astype(np.float64),
            impact_low.astype(np.float64),
            impact_high.astype(np.float64),
        )
    )


# ---------------------------------------------------------------------------
# STAGE D - weekly walk-forward per-cell evaluation
# ---------------------------------------------------------------------------
def _week_bootstrap_interval(improvements, times, W, H):
    """UTC ISO-week block bootstrap of the pooled mean AE improvement.
    One RNG stream per (W,H) cell for all N_BOOT replicates in order."""
    values = np.asarray(improvements, dtype=np.float64)
    stamps = np.asarray(times, dtype=np.int64)
    if len(values) == 0:
        return float("nan"), float("nan")
    groups = defaultdict(list)
    for value, t in zip(values, stamps):
        groups[iso_week_id(int(t))].append(float(value))
    keys = sorted(groups)
    if not keys:
        return float("nan"), float("nan")
    sums = np.asarray([sum(groups[key]) for key in keys], dtype=np.float64)
    counts = np.asarray([len(groups[key]) for key in keys], dtype=np.int64)
    rng = np.random.default_rng(seed_int((SEED_BOOT, int(W), int(H))))
    draws = np.empty(N_BOOT, dtype=np.float64)
    n_blocks = len(keys)
    for replicate in range(N_BOOT):
        sampled = rng.integers(0, n_blocks, size=n_blocks, dtype=np.int64)
        denominator = int(np.sum(counts[sampled]))
        draws[replicate] = (
            float(np.sum(sums[sampled]) / denominator) if denominator > 0 else float("nan")
        )
    finite = draws[np.isfinite(draws)]
    if len(finite) == 0:
        return float("nan"), float("nan")
    return (
        float(np.quantile(finite, BOOT_LOW_Q, method="linear")),
        float(np.quantile(finite, BOOT_HIGH_Q, method="linear")),
    )


def per_cell_conditions(
    *,
    mean_improvement,
    relative,
    bootstrap_lower,
    placebo_q95,
    residual_low,
    residual_mid,
    residual_high,
    buy_mean_improvement,
    buy_ordering_gap,
    sell_mean_improvement,
    sell_ordering_gap,
):
    """The six frozen per-cell conditions (prereg promotion_gate_contract).
    Zero is not positive; NaN fails."""
    primary_positive = bool(math.isfinite(mean_improvement) and mean_improvement > 0.0)
    material_relative_mae = bool(math.isfinite(relative) and relative >= RELATIVE_MAE_MIN)
    bootstrap_positive = bool(math.isfinite(bootstrap_lower) and bootstrap_lower > 0.0)
    placebo_separation = bool(
        math.isfinite(mean_improvement)
        and math.isfinite(placebo_q95)
        and mean_improvement > placebo_q95
    )
    impact_ordering = bool(
        math.isfinite(residual_low)
        and math.isfinite(residual_mid)
        and math.isfinite(residual_high)
        and residual_low < residual_mid < residual_high
    )
    side_stability = bool(
        math.isfinite(buy_mean_improvement)
        and buy_mean_improvement > 0.0
        and math.isfinite(buy_ordering_gap)
        and buy_ordering_gap > 0.0
        and math.isfinite(sell_mean_improvement)
        and sell_mean_improvement > 0.0
        and math.isfinite(sell_ordering_gap)
        and sell_ordering_gap > 0.0
    )
    return {
        "primary_positive": primary_positive,
        "material_relative_mae": material_relative_mae,
        "bootstrap_positive": bootstrap_positive,
        "placebo_separation": placebo_separation,
        "impact_ordering": impact_ordering,
        "side_stability": side_stability,
    }


def evaluate_cell(flow, H, snapshot_id=REQUIRED_SNAPSHOT):
    """Score one frozen (W,H) cell under the weekly walk-forward same-support
    contract. `flow` must already carry impact_state / nuisance quintiles
    (attach_impact_state / attach_nuisance_bins)."""
    h_minutes = int(H)
    w_minutes = int(flow["W"])
    t_ms = flow["t_ms"]
    n = len(t_ms)

    raw_ret = horizon_returns(flow["close"], t_ms, h_minutes)
    scale = past_median_abs_return(np.abs(raw_ret), h_minutes)
    side_code = flow["side_code"]
    d = side_code.astype(np.float64)
    flow_cont_ret = d * raw_ret
    y = np.where(
        (side_code != 0) & np.isfinite(raw_ret) & np.isfinite(scale) & (scale > 0.0),
        flow_cont_ret / scale,
        np.nan,
    )
    target_available = np.isfinite(y)

    legal = (
        (t_ms % HTF_MS == 0)
        & (t_ms >= DEV_START_MS)
        & (t_ms < DEV_END_MS)
        & ((t_ms + h_minutes * BAR_MS) < DEV_END_MS)
    )

    valid_features = flow["valid_features"]
    impact_state = flow["impact_state"]
    abs_q = flow["abs_imb_quintile"]
    flow_q = flow["flow_ret_quintile"]

    baseline_eligible = valid_features & target_available
    candidate_eligible = (
        baseline_eligible
        & np.array([s is not None for s in impact_state], dtype=bool)
        & np.array([s is not None for s in abs_q], dtype=bool)
        & np.array([s is not None for s in flow_q], dtype=bool)
    )
    current_scoreable = valid_features & target_available & legal & np.array(
        [s is not None for s in impact_state], dtype=bool
    )

    baseline_idx_all = np.flatnonzero(baseline_eligible)
    candidate_idx_all = np.flatnonzero(candidate_eligible)
    current_idx_all = np.flatnonzero(current_scoreable)

    abs_imb = flow["abs_imb"]
    flow_ret = flow["flow_ret"]
    rv_w = flow["rv_w"]
    log_activity = flow["log_activity"]
    side_buy = (side_code == 1).astype(np.float64)

    week_of = np.array([iso_week_start_ms(int(t)) for t in t_ms], dtype=np.int64)

    # group current-scoreable indices by week (t_ms ascending => week_of
    # ascending within each week's contiguous run)
    weeks_with_current = []
    current_by_week = defaultdict(list)
    for i in current_idx_all:
        s_ms = int(week_of[i])
        if s_ms not in current_by_week:
            weeks_with_current.append(s_ms)
        current_by_week[s_ms].append(int(i))

    scored = []
    placebo_sums = np.zeros(N_PLACEBO, dtype=np.float64)

    b_left = b_right = 0
    c_left = c_right = 0

    for S in weeks_with_current:
        upper_bound = S - h_minutes * BAR_MS
        cutoff_low = S - TRAIN_MS

        while b_right < len(baseline_idx_all) and t_ms[baseline_idx_all[b_right]] <= upper_bound:
            b_right += 1
        while b_left < b_right and t_ms[baseline_idx_all[b_left]] < cutoff_low:
            b_left += 1
        baseline_pool = baseline_idx_all[b_left:b_right]

        while c_right < len(candidate_idx_all) and t_ms[candidate_idx_all[c_right]] <= upper_bound:
            c_right += 1
        while c_left < c_right and t_ms[candidate_idx_all[c_left]] < cutoff_low:
            c_left += 1
        candidate_pool = candidate_idx_all[c_left:c_right]

        if len(baseline_pool) < MIN_BASELINE_N or len(candidate_pool) < MIN_CANDIDATE_N:
            continue

        state_counts = defaultdict(int)
        for j in candidate_pool:
            state_counts[impact_state[j]] += 1
        if any(
            state_counts.get(state, 0) < MIN_CANDIDATE_N_PER_STATE
            for state in (STATE_LOW, STATE_MID, STATE_HIGH)
        ):
            continue

        # canonical row order: T_ms sort is provably equivalent to sorting
        # by CANONICAL_SCORE_RECORD_ID within one (W,H) pool -- side is a
        # deterministic function of T_ms here, so no two pooled rows share a
        # T_ms, and the id's only varying field is T_ms itself (see the
        # dedicated equivalence test).
        baseline_pool = np.sort(baseline_pool)
        candidate_pool = np.sort(candidate_pool)

        base_cols = np.column_stack(
            (abs_imb[baseline_pool], flow_ret[baseline_pool], rv_w[baseline_pool], log_activity[baseline_pool])
        )
        base_mean, base_std = _standardize(base_cols)
        if base_mean is None:
            continue
        base_z = (base_cols - base_mean) / base_std
        base_design = _baseline_design(base_z, side_buy[baseline_pool])
        base_beta = ols_fit(base_design, y[baseline_pool])
        if base_beta is None:
            continue

        cand_cols = np.column_stack(
            (abs_imb[candidate_pool], flow_ret[candidate_pool], rv_w[candidate_pool], log_activity[candidate_pool])
        )
        cand_mean, cand_std = _standardize(cand_cols)
        if cand_mean is None:
            continue
        cand_z = (cand_cols - cand_mean) / cand_std
        cand_states = [impact_state[j] for j in candidate_pool]
        cand_low = np.asarray([1.0 if s == STATE_LOW else 0.0 for s in cand_states])
        cand_high = np.asarray([1.0 if s == STATE_HIGH else 0.0 for s in cand_states])
        cand_design = _candidate_design(cand_z, side_buy[candidate_pool], cand_low, cand_high)
        cand_beta = ols_fit(cand_design, y[candidate_pool])
        if cand_beta is None:
            continue

        current_week_idx = current_by_week[S]
        base_ae_by_i = {}
        for i in current_week_idx:
            zi = (np.asarray([abs_imb[i], flow_ret[i], rv_w[i], log_activity[i]]) - base_mean) / base_std
            base_pred = float(base_beta[0] + np.dot(base_beta[1:5], zi) + base_beta[5] * side_buy[i])
            zci = (np.asarray([abs_imb[i], flow_ret[i], rv_w[i], log_activity[i]]) - cand_mean) / cand_std
            low_i = 1.0 if impact_state[i] == STATE_LOW else 0.0
            high_i = 1.0 if impact_state[i] == STATE_HIGH else 0.0
            cand_pred = float(
                cand_beta[0]
                + np.dot(cand_beta[1:5], zci)
                + cand_beta[5] * side_buy[i]
                + cand_beta[6] * low_i
                + cand_beta[7] * high_i
            )
            if not (math.isfinite(base_pred) and math.isfinite(cand_pred)):
                continue
            base_ae = abs(float(y[i]) - base_pred)
            cand_ae = abs(float(y[i]) - cand_pred)
            base_ae_by_i[int(i)] = base_ae
            side_label = SIDE_LABELS[int(side_code[i])]
            base_event_id = canonical_base_event_id(
                W=w_minutes, side=side_label, T_ms=int(t_ms[i]), snapshot_id=snapshot_id
            )
            scored.append(
                {
                    "index": int(i),
                    "T": int(t_ms[i]),
                    "side": side_label,
                    "week_start_ms": int(S),
                    "score_record_id": canonical_score_record_id(base_event_id, h_minutes),
                    "base_pred": base_pred,
                    "candidate_pred": cand_pred,
                    "base_ae": base_ae,
                    "candidate_ae": cand_ae,
                    "ae_improvement": base_ae - cand_ae,
                    "base_residual": float(y[i]) - base_pred,
                    "impact_state": impact_state[i],
                }
            )

        if not current_week_idx:
            continue

        strata = defaultdict(list)
        for j in candidate_pool:
            key = permutation_stratum_id(
                T_e_ms=int(t_ms[j]),
                side=SIDE_LABELS[int(side_code[j])],
                abs_imb_quintile=abs_q[j],
                flow_ret_quintile=flow_q[j],
            )
            strata[key].append(int(j))
        for key in strata:
            strata[key] = sorted(strata[key], key=lambda j: int(t_ms[j]))

        pool_position = {int(j): pos for pos, j in enumerate(candidate_pool)}
        real_state_codes = np.asarray(
            [STATE_LABEL_CODE[s] for s in cand_states], dtype=np.int64
        )

        # Precompute each scored current-week event's own (unpermuted, fixed)
        # candidate-standardized features once -- these are identical across
        # all N_PLACEBO replicates (only the training-side IMPACT_STATE
        # labels are permuted, never the evaluation event's own state), so
        # recomputing them per replicate would be pure repeated work. This is
        # a performance optimization only: the per-replicate poison-on-any-
        # nonfinite-prediction semantics are unchanged (see the dedicated
        # equivalence test against a from-scratch per-event/per-replicate
        # oracle).
        cur_idx_arr = np.asarray(current_week_idx, dtype=np.int64)
        cur_cols = np.column_stack(
            (
                abs_imb[cur_idx_arr],
                flow_ret[cur_idx_arr],
                rv_w[cur_idx_arr],
                log_activity[cur_idx_arr],
            )
        )
        cur_z = (cur_cols - cand_mean) / cand_std
        cur_side_buy = side_buy[cur_idx_arr]
        cur_low = np.asarray(
            [1.0 if impact_state[i] == STATE_LOW else 0.0 for i in cur_idx_arr]
        )
        cur_high = np.asarray(
            [1.0 if impact_state[i] == STATE_HIGH else 0.0 for i in cur_idx_arr]
        )
        cur_base_ae = np.asarray([base_ae_by_i[int(i)] for i in cur_idx_arr])
        cur_y = y[cur_idx_arr]

        for replicate in range(N_PLACEBO):
            permuted_codes = real_state_codes.copy()
            for key, ordered_js in strata.items():
                seed = seed_int((SEED_PLACEBO, replicate, w_minutes, h_minutes, S, key))
                rng = np.random.default_rng(seed)
                label_vec = np.asarray(
                    [STATE_LABEL_CODE[impact_state[j]] for j in ordered_js], dtype=np.int64
                )
                permuted = rng.permutation(label_vec)
                for pos, j in enumerate(ordered_js):
                    permuted_codes[pool_position[j]] = permuted[pos]

            p_low = (permuted_codes == STATE_LABEL_CODE[STATE_LOW]).astype(np.float64)
            p_high = (permuted_codes == STATE_LABEL_CODE[STATE_HIGH]).astype(np.float64)
            p_design = _candidate_design(cand_z, side_buy[candidate_pool], p_low, p_high)
            p_beta = ols_fit(p_design, y[candidate_pool])
            if p_beta is None:
                placebo_sums[replicate] = float("nan")
                continue
            preds = (
                p_beta[0]
                + cur_z @ p_beta[1:5]
                + p_beta[5] * cur_side_buy
                + p_beta[6] * cur_low
                + p_beta[7] * cur_high
            )
            if not np.all(np.isfinite(preds)):
                placebo_sums[replicate] = float("nan")
                continue
            placebo_sums[replicate] += float(np.sum(cur_base_ae - np.abs(cur_y - preds)))

    return _summarize_cell(W=w_minutes, H=h_minutes, scored=scored, placebo_sums=placebo_sums)


def _summarize_cell(*, W, H, scored, placebo_sums):
    improvements = np.asarray([r["ae_improvement"] for r in scored], dtype=np.float64)
    base_ae = np.asarray([r["base_ae"] for r in scored], dtype=np.float64)
    cand_ae = np.asarray([r["candidate_ae"] for r in scored], dtype=np.float64)
    times = np.asarray([r["T"] for r in scored], dtype=np.int64)

    mean_improvement = float(np.mean(improvements)) if len(improvements) else float("nan")
    median_improvement = float(np.median(improvements)) if len(improvements) else float("nan")
    mean_base = float(np.mean(base_ae)) if len(base_ae) else float("nan")
    mean_cand = float(np.mean(cand_ae)) if len(cand_ae) else float("nan")
    relative = (
        1.0 - mean_cand / mean_base
        if math.isfinite(mean_base) and mean_base > 0.0 and math.isfinite(mean_cand)
        else float("nan")
    )
    ci_low, ci_high = _week_bootstrap_interval(improvements, times, W, H)

    def _residual_median(state):
        values = [r["base_residual"] for r in scored if r["impact_state"] == state]
        return float(np.median(np.asarray(values, dtype=np.float64))) if values else float("nan")

    residual_low = _residual_median(STATE_LOW)
    residual_mid = _residual_median(STATE_MID)
    residual_high = _residual_median(STATE_HIGH)

    def _side_mean(side):
        values = [r["ae_improvement"] for r in scored if r["side"] == side]
        return float(np.mean(np.asarray(values, dtype=np.float64))) if values else float("nan")

    def _side_gap(side):
        high = [
            r["base_residual"] for r in scored if r["side"] == side and r["impact_state"] == STATE_HIGH
        ]
        low = [
            r["base_residual"] for r in scored if r["side"] == side and r["impact_state"] == STATE_LOW
        ]
        if not high or not low:
            return float("nan")
        return float(np.median(np.asarray(high)) - np.median(np.asarray(low)))

    buy_mean = _side_mean(SIDE_BUY)
    sell_mean = _side_mean(SIDE_SELL)
    buy_gap = _side_gap(SIDE_BUY)
    sell_gap = _side_gap(SIDE_SELL)

    placebo_means = (
        placebo_sums / len(scored) if len(scored) else np.full(N_PLACEBO, np.nan, dtype=np.float64)
    )
    placebo_finite = placebo_means[np.isfinite(placebo_means)]
    placebo_q95 = (
        float(np.quantile(placebo_finite, PLACEBO_Q, method="linear"))
        if len(placebo_finite) == N_PLACEBO
        else float("nan")
    )

    yearly = {}
    positive_years = 0
    for year in YEAR_BLOCKS:
        values = np.asarray(
            [r["ae_improvement"] for r in scored if utc_year(r["T"]) == year], dtype=np.float64
        )
        mean_year = float(np.mean(values)) if len(values) else float("nan")
        yearly[str(year)] = mean_year if math.isfinite(mean_year) else None
        if math.isfinite(mean_year) and mean_year > 0.0:
            positive_years += 1

    conditions = per_cell_conditions(
        mean_improvement=mean_improvement,
        relative=relative,
        bootstrap_lower=ci_low,
        placebo_q95=placebo_q95,
        residual_low=residual_low,
        residual_mid=residual_mid,
        residual_high=residual_high,
        buy_mean_improvement=buy_mean,
        buy_ordering_gap=buy_gap,
        sell_mean_improvement=sell_mean,
        sell_ordering_gap=sell_gap,
    )

    score_record_ids = sorted(str(r["score_record_id"]) for r in scored)
    support_digest = hashlib.sha256("\n".join(score_record_ids).encode("utf-8")).hexdigest()

    return {
        "W": int(W),
        "H": int(H),
        "N": len(scored),
        "BUY_N": sum(1 for r in scored if r["side"] == SIDE_BUY),
        "SELL_N": sum(1 for r in scored if r["side"] == SIDE_SELL),
        "mean_ae_improvement": mean_improvement if math.isfinite(mean_improvement) else None,
        "median_ae_improvement": median_improvement if math.isfinite(median_improvement) else None,
        "relative_mae_improvement": relative if math.isfinite(relative) else None,
        "bootstrap_lower_95": ci_low if math.isfinite(ci_low) else None,
        "bootstrap_upper_95": ci_high if math.isfinite(ci_high) else None,
        "placebo_q95": placebo_q95 if math.isfinite(placebo_q95) else None,
        "placebo_replicate_count_nominal": int(N_PLACEBO),
        "placebo_replicate_count_finite": int(len(placebo_finite)),
        "impact_residual_median": {
            "LOW": residual_low if math.isfinite(residual_low) else None,
            "MID": residual_mid if math.isfinite(residual_mid) else None,
            "HIGH": residual_high if math.isfinite(residual_high) else None,
        },
        "buy": {
            "N": sum(1 for r in scored if r["side"] == SIDE_BUY),
            "mean_ae_improvement": buy_mean if math.isfinite(buy_mean) else None,
            "residual_gap_high_minus_low": buy_gap if math.isfinite(buy_gap) else None,
        },
        "sell": {
            "N": sum(1 for r in scored if r["side"] == SIDE_SELL),
            "mean_ae_improvement": sell_mean if math.isfinite(sell_mean) else None,
            "residual_gap_high_minus_low": sell_gap if math.isfinite(sell_gap) else None,
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


def _cell_six_pass(cell):
    conditions = cell.get("per_cell_conditions")
    if not isinstance(conditions, Mapping):
        return False
    return all(conditions.get(name) is True for name in PER_CELL_GATE_NAMES)


def determine_promotion_gates(cells):
    """Nine frozen gates; a neighborhood is one adjacent-H pair at two W."""
    by_key = {(int(c["W"]), int(c["H"])): c for c in cells if "W" in c and "H" in c}
    per_gate_evidence = {name: False for name in PER_CELL_GATE_NAMES}
    horizon_robustness = False
    parameter_robustness = False
    year_stability = False
    neighborhoods = []

    for h1, h2 in ADJACENT_H_PAIRS:
        per_gate_w = {name: [] for name in PER_CELL_GATE_NAMES}
        core_w = []
        stable_w = []
        for w in W_VALUES:
            c1 = by_key.get((w, h1))
            c2 = by_key.get((w, h2))
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
                    per_gate_w[name].append(int(w))
            if _cell_six_pass(c1) and _cell_six_pass(c2):
                horizon_robustness = True
                core_w.append(int(w))
                if c1.get("year_stability_pass") is True and c2.get("year_stability_pass") is True:
                    stable_w.append(int(w))
        for name, passing in per_gate_w.items():
            if len(passing) >= 2:
                per_gate_evidence[name] = True
        if len(core_w) >= 2:
            parameter_robustness = True
        if len(stable_w) >= 2:
            year_stability = True
            neighborhoods.append(
                {
                    "H_pair": [h1, h2],
                    "W": list(stable_w),
                    "cells": [{"W": w, "H": h} for w in stable_w for h in (h1, h2)],
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


# ---------------------------------------------------------------------------
# forbidden-window evidence + top-level evaluation
# ---------------------------------------------------------------------------
def _partition_year(relative_path):
    leaf = str(relative_path).rsplit("/", 1)[-1]
    head = leaf.split("-", 1)[0]
    if len(head) != 4 or not head.isdigit():
        raise B205Error(
            f"authorized partition path is not a canonical monthly leaf: {relative_path}"
        )
    return int(head)


def derive_forbidden_window_evidence(run_identity, frame):
    """Prove 2025/2026 were not reached from the authorized view only."""
    window = run_identity.get("window")
    if not isinstance(window, Mapping):
        raise B205Error("run identity is missing its authorized window evidence")
    try:
        end_exclusive_ms = int(window["end_exclusive_ms"])
        start_inclusive_ms = int(window["start_inclusive_ms"])
        allowed_years = tuple(int(year) for year in window["allowed_years"])
    except (KeyError, TypeError, ValueError) as exc:
        raise B205Error("authorized window evidence is malformed") from exc
    if not allowed_years:
        raise B205Error("authorized window evidence has an empty allowed_years")

    partitions = run_identity.get("partitions")
    if not isinstance(partitions, Sequence) or isinstance(partitions, (str, bytes)):
        raise B205Error("run identity is missing its authorized partition evidence")
    partition_years = []
    for partition in partitions:
        if not isinstance(partition, Mapping) or "relative_path" not in partition:
            raise B205Error("authorized partition evidence is malformed")
        partition_years.append(_partition_year(str(partition["relative_path"])))
    if not partition_years:
        raise B205Error("authorized partition evidence is empty")

    open_ms = np.asarray(frame["open_time_ms"], dtype=np.int64)
    avail_ms = np.asarray(frame["available_at_ms"], dtype=np.int64)
    if len(open_ms) == 0:
        raise B205Error("loaded development frame is empty")

    if end_exclusive_ms > VALIDATION_2025_START_MS:
        raise B205Error("authorized window reaches the reserved 2025 validation pool")
    if max(allowed_years) >= FIRST_FORBIDDEN_YEAR:
        raise B205Error("authorized years reach a forbidden window")
    if max(partition_years) >= FIRST_FORBIDDEN_YEAR:
        raise B205Error("authorized partitions reach a forbidden window")
    if int(np.max(avail_ms)) > VALIDATION_2025_START_MS:
        raise B205Error("loaded development bytes reach the reserved 2025 pool")

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


def evaluate_b2_05(frame_1m, snapshot_id=REQUIRED_SNAPSHOT):
    """Full frozen 3W x 4H = 12-cell B2-05 surface from one authorized 1m frame."""
    validate_1m_frame(frame_1m)
    frame15 = aggregate_1m_to_15m(frame_1m)
    close15 = frame15["close"]
    t_ms15 = frame15["t_ms"]

    cells = []
    flow_summary = {}
    for w in W_VALUES:
        flow = build_flow_frame(frame_1m, w, close15, t_ms15)
        flow = attach_impact_state(flow)
        flow = attach_nuisance_bins(flow)
        flow_summary[str(w)] = {
            "valid_feature_records": int(np.sum(flow["valid_features"])),
            "impact_state_available_records": int(
                np.sum(np.array([s is not None for s in flow["impact_state"]]))
            ),
        }
        for h in H_VALUES:
            cell = evaluate_cell(flow, h, snapshot_id=snapshot_id)
            cell.pop("scored", None)
            cells.append(cell)

    gates, neighborhoods = determine_promotion_gates(cells)
    passed = bool(neighborhoods) and all(gates.get(name) is True for name in GATE_NAMES)

    return {
        "hypothesis_id": HYPOTHESIS_ID,
        "primary_family": PRIMARY_FAMILY,
        "prereg_merge_sha": PREREG_MERGE_SHA,
        "canonical_prereg_json_sha256": CANONICAL_PREREG_JSON_SHA256,
        "structural_property": {
            "family": "PRICE_IMPACT_ABSORPTION",
            "name": "IMPACT_INTERACTION",
            "count": 1,
        },
        "dataset_id": DATASET_ID,
        "snapshot_id": snapshot_id,
        "stage": "development",
        "search_surface": {
            "W_minutes": list(W_VALUES),
            "H_minutes": list(H_VALUES),
            "primary_cells": PRIMARY_CELLS,
        },
        "windows": {
            "warmup_start_inclusive_ms": WARMUP_START_MS,
            "development_start_inclusive_ms": DEV_START_MS,
            "development_end_exclusive_ms": DEV_END_MS,
            "validation_2025_untouched": True,
            "oos_2026_untouched": True,
        },
        "flow_summary_by_W": flow_summary,
        "cells": cells,
        "promotion": {
            "gates": gates,
            "required_gate_names": list(GATE_NAMES),
            "qualifying_neighborhoods": neighborhoods,
            "passed": passed,
            "verdict": VERDICT_PROMOTED if passed else VERDICT_CLOSED,
        },
    }
