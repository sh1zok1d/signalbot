"""H04 trend-pullback continuation helpers.

Development-only. Refuses 2025/2026 1m canonical partitions and any outcome
window that reaches 2025-01-01. Does not reuse H01/H02/H03 detectors or
definitions. No volume/taker/trend-indicator gates.

This module intentionally does NOT execute against real accepted parquet as
part of preregistration/implementation freeze -- see
`docs/research/H04_TREND_PULLBACK_PREREG.md` section 22 and
`tests/research/test_h04_trend_pullback_continuation.py`, which exercise
every function here with local synthetic fixtures only.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yaml

UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[2]
PREREG_JSON = REPO_ROOT / "docs" / "research" / "H04_TREND_PULLBACK_PREREG.json"
REPO_MANIFEST = REPO_ROOT / "docs" / "manifests" / "CORE_BTC_BINANCE_V0.yaml"
REQUIRED_SNAPSHOT = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
DATASET_ID = "CORE_BTC_BINANCE_V0"

BAR_MS = 60_000
HTF_MIN = 15
HTF_MS = HTF_MIN * BAR_MS
DAY_MS = 24 * 60 * BAR_MS
DEV_END_MS = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
DEV_START_MS = int(datetime(2020, 2, 1, tzinfo=UTC).timestamp() * 1000)
WARMUP_START_MS = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
MAX_H_MIN = 240
REF_DAYS = 30
REF_STEPS = REF_DAYS * 24 * 60 // HTF_MIN  # 2880

P_MIN = 60
P_STEPS = P_MIN // HTF_MIN  # 4
L_WINDOWS = (240, 480, 960)
TREND_Q = 0.80
HORIZONS = (15, 30, 60, 120, 240)
YEAR_BLOCKS = (2020, 2021, 2022, 2023, 2024)
REFRACTORY_MS = 60 * BAR_MS
SHIFT_MS = 6 * 60 * BAR_MS
SEED_MATCHED = 20260902
SEED_BOOT = 20260903
N_MATCHED = 100
N_BOOT = 2000
DIR_UP = 1
DIR_DOWN = -1
STRUCTURAL_RATIO_THRESHOLD = 0.10
DEPTH_BAND_ORDER = ("shallow", "moderate", "deep")
DEPTH_BANDS = {"shallow": (0.10, 0.25), "moderate": (0.25, 0.40), "deep": (0.40, 1.00)}
TREND_STRENGTH_BINS = ((0.80, 0.90), (0.90, 1.0000001))  # second bin closed at 1.0 inclusive
MPIE = 0.10
CONTROL_DELTA_MIN = 0.05
DEP_LAGS_DAYS = (1, 2, 4, 8, 16, 32, 64)
DEP_ACF_THRESHOLD = 0.20


class H04Error(RuntimeError):
    pass


class ValidationWindowForbidden(H04Error):
    pass


# ---------------------------------------------------------------------------
# identity / snapshot / prereg
# ---------------------------------------------------------------------------
def load_prereg(path: Path = PREREG_JSON) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_px(value) -> float:
    if value is None:
        return float("nan")
    return float(Decimal(str(value)))


def utc_ms(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.astimezone(UTC).timestamp() * 1000)


def iso_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_snapshot(manifest_path: Path = REPO_MANIFEST) -> str:
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if data.get("dataset_id") != DATASET_ID:
        raise H04Error(f"unexpected dataset_id {data.get('dataset_id')}")
    snap = data.get("snapshot_id")
    if snap != REQUIRED_SNAPSHOT:
        raise H04Error(f"snapshot mismatch: {snap} != {REQUIRED_SNAPSHOT}")
    if data.get("status") != "ACCEPTED_FOR_DISCOVERY":
        raise H04Error(f"dataset not ACCEPTED_FOR_DISCOVERY: {data.get('status')}")
    if data.get("research_authorized") is not True:
        raise H04Error("research_authorized is not true")
    if data.get("confirmatory_authorized") is True:
        raise H04Error("confirmatory_authorized must remain false for H04")
    return snap


# ---------------------------------------------------------------------------
# UTC grid / windowing helpers
# ---------------------------------------------------------------------------
def is_grid_ms(t_ms: int) -> bool:
    return t_ms % HTF_MS == 0


def development_t_max_ms() -> int:
    """Last legal 15m-aligned decision T such that T + 240m < 2025-01-01."""
    return DEV_END_MS - MAX_H_MIN * BAR_MS - HTF_MS


def assert_development_outcome_window(t_ms: int, h_min: int) -> None:
    end_ms = t_ms + h_min * BAR_MS
    if end_ms >= DEV_END_MS:
        raise ValidationWindowForbidden(
            f"outcome window [{iso_ms(t_ms)}, {iso_ms(end_ms)}] reaches 2025+"
        )


def utc_year(ms: int) -> int:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).year


def utc_month_key(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m")


def utc_week_key(ms: int) -> str:
    dt = datetime.fromtimestamp(ms / 1000, tz=UTC)
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def utc_day_key(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%d")


def utc_dow_key(ms: int) -> str:
    """UTC day-of-week, Monday=0 .. Sunday=6, as a fixed string key."""
    return str(datetime.fromtimestamp(ms / 1000, tz=UTC).weekday())


def utc_dom_key(ms: int) -> str:
    """UTC day-of-month, '01'..'31'."""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%d")


def shift_plus_6h_same_utc_day(t_ms: int) -> int:
    day = t_ms - (t_ms % DAY_MS)
    return day + ((t_ms - day + SHIFT_MS) % DAY_MS)


def _forbid_partition_name(name: str) -> None:
    if name.startswith("2025-") or name.startswith("2026-"):
        raise ValidationWindowForbidden(
            f"refusing canonical partition {name} (2025/2026 forbidden in H04 development)"
        )


def list_development_parquet_paths(dataset_root: Path) -> list[Path]:
    monthly = dataset_root / "canonical" / "1m" / "monthly"
    if not monthly.is_dir():
        raise H04Error(f"missing canonical 1m monthly dir: {monthly}")
    paths = []
    for p in sorted(monthly.glob("*.parquet")):
        year_prefix = p.name[:5]
        if year_prefix in ("2025-", "2026-"):
            continue
        year = int(p.name.split("-", 1)[0])
        if 2020 <= year <= 2024:
            paths.append(p)
    if not paths:
        raise H04Error("no 2020-2024 canonical monthly parquet found")
    return paths


def require_pyarrow() -> None:
    try:
        import pyarrow  # noqa: F401
    except ImportError as exc:
        raise H04Error("pyarrow is required; install requirements-research.txt") from exc


def load_development_1m(dataset_root: Path) -> dict:
    """Load 2020-2024 1m OHLC only. Never opens 2025/2026 parquet.

    Not exercised against real data in the preregistration/implementation
    -freeze task -- see module docstring.
    """
    require_pyarrow()
    import pyarrow.parquet as pq

    runtime_snap = dataset_root / "reports" / "snapshot_manifest.json"
    if runtime_snap.exists():
        snap = json.loads(runtime_snap.read_text(encoding="utf-8"))
        sid = snap.get("snapshot_id")
        if sid != REQUIRED_SNAPSHOT:
            raise H04Error(f"runtime snapshot_id {sid} != {REQUIRED_SNAPSHOT}")

    cols = ["open_time_ms", "available_at_ms", "open", "high", "low", "close"]
    buckets = {c: [] for c in ("open_time_ms", "available_at_ms", "open", "high", "low", "close")}
    for path in list_development_parquet_paths(dataset_root):
        _forbid_partition_name(path.name)
        table = pq.read_table(path, columns=cols)
        if "close_time_ms" in table.column_names:
            raise H04Error("close_time_ms must not be loaded")
        buckets["open_time_ms"].append(np.asarray(table.column("open_time_ms").to_pylist(), dtype=np.int64))
        buckets["available_at_ms"].append(np.asarray(table.column("available_at_ms").to_pylist(), dtype=np.int64))
        for px in ("open", "high", "low", "close"):
            buckets[px].append(np.array([parse_px(x) for x in table.column(px).to_pylist()], dtype=np.float64))
    open_ms = np.concatenate(buckets["open_time_ms"])
    order = np.argsort(open_ms, kind="mergesort")
    frame = {
        "open_time_ms": open_ms[order],
        "available_at_ms": np.concatenate(buckets["available_at_ms"])[order],
        "open": np.concatenate(buckets["open"])[order],
        "high": np.concatenate(buckets["high"])[order],
        "low": np.concatenate(buckets["low"])[order],
        "close": np.concatenate(buckets["close"])[order],
    }
    if frame["open_time_ms"][0] < WARMUP_START_MS:
        raise H04Error("unexpected bars before warmup start")
    if int(frame["open_time_ms"][-1]) >= DEV_END_MS:
        raise ValidationWindowForbidden("loaded 1m bars reach 2025+")
    if np.any(frame["available_at_ms"] != frame["open_time_ms"] + BAR_MS):
        raise H04Error("available_at_ms is not open_time_ms + 60s")
    return frame


def aggregate_1m_to_15m(frame_1m: dict) -> dict:
    """T = bar_end_exclusive of the 15m bar [T-15m, T). close(T) is that
    bar's close -- the close of the final canonical 1m bar whose own
    bar_end_exclusive == T. No off-by-one discretion: this is the only place
    the 1m->15m close is chosen."""
    o = frame_1m["open_time_ms"]
    n = len(o)
    if n == 0 or n % HTF_MIN != 0:
        raise H04Error(f"1m length {n} is not a multiple of {HTF_MIN}")
    if int(o[0]) % HTF_MS != 0:
        raise H04Error("1m series does not start on a 15m UTC boundary")
    expected = o[0] + np.arange(n, dtype=np.int64) * BAR_MS
    if np.any(o != expected):
        raise H04Error("1m open_time_ms is not a contiguous 1m grid")
    n15 = n // HTF_MIN
    high = frame_1m["high"].reshape(n15, HTF_MIN).max(axis=1)
    low = frame_1m["low"].reshape(n15, HTF_MIN).min(axis=1)
    open_ms = o[::HTF_MIN]
    avail = open_ms + HTF_MS
    last_1m_avail = frame_1m["available_at_ms"][HTF_MIN - 1::HTF_MIN]
    if np.any(last_1m_avail != avail):
        raise H04Error("15m available_at is not last 1m available_at in the bucket")
    frame = {
        "open_time_ms": open_ms,
        "available_at_ms": avail,
        "t_ms": avail,  # decision T = bar_end_exclusive
        "open": frame_1m["open"][::HTF_MIN],
        "high": high,
        "low": low,
        "close": frame_1m["close"][HTF_MIN - 1::HTF_MIN],
    }
    if np.any(frame["available_at_ms"] != frame["open_time_ms"] + HTF_MS):
        raise H04Error("15m available_at_ms is not open_time_ms + 900s")
    return frame


# ---------------------------------------------------------------------------
# trend / pullback / depth
# ---------------------------------------------------------------------------
def compute_trend_returns(close: np.ndarray, l_minutes: int) -> np.ndarray:
    """TREND_RET_L(T) = ln(close(T-P) / close(T-P-L)). Uses only the two
    fully-available closes bounding the trend leg [T-P-L, T-P) -- no
    off-by-one discretion (step counts are exact grid multiples)."""
    if l_minutes % HTF_MIN != 0:
        raise H04Error(f"L={l_minutes} is not a multiple of the {HTF_MIN}m grid")
    l_step = l_minutes // HTF_MIN
    lag_near = P_STEPS
    lag_far = P_STEPS + l_step
    n = len(close)
    out = np.full(n, np.nan, dtype=np.float64)
    if n <= lag_far:
        return out
    c_near = close[lag_far - lag_near: n - lag_near]  # close(T-P) aligned to i in [lag_far, n)
    c_far = close[: n - lag_far]  # close(T-P-L)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.log(c_near / c_far)
    out[lag_far:] = r
    return out


def compute_raw_pullback_return(close: np.ndarray) -> np.ndarray:
    """RAW_PB_RET(T) = ln(close(T) / close(T-P)) -- direction-agnostic,
    identical for every L (P does not depend on L)."""
    n = len(close)
    out = np.full(n, np.nan, dtype=np.float64)
    if n <= P_STEPS:
        return out
    c0 = close[P_STEPS:]
    c1 = close[:-P_STEPS]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.log(c0 / c1)
    out[P_STEPS:] = r
    return out


def rolling_midrank_percentile(values: np.ndarray, window: int) -> np.ndarray:
    """For index i, returns the midrank percentile of values[i] within the
    strictly-prior window values[i-window:i] (current i excluded, no future
    observations). NaNs in the reference are excluded from N_ref for that
    step. Returns NaN wherever values[i] is NaN or fewer than one valid
    reference observation is available.

    Formula (frozen, H01/H03-compatible):
        P(T) = (count(ref < x) + 0.5 * count(ref == x)) / N_ref

    Implemented with an incrementally maintained sorted reference list
    (bisect insert/remove) rather than a materialized (n, window) boolean
    matrix. Correct-but-not-optimized for this preregistration/
    implementation-freeze task's synthetic fixtures; no real-data run is
    performed here."""
    import bisect
    from collections import deque

    n = len(values)
    out = np.full(n, np.nan, dtype=np.float64)
    if window <= 0 or n == 0:
        return out

    sorted_ref: list[float] = []
    raw_window: deque = deque()

    def _push(v: float) -> None:
        raw_window.append(v)
        if np.isfinite(v):
            bisect.insort(sorted_ref, v)

    def _pop_oldest() -> None:
        old = raw_window.popleft()
        if np.isfinite(old):
            pos = bisect.bisect_left(sorted_ref, old)
            del sorted_ref[pos]

    for i in range(n):
        x = values[i]
        n_ref = len(sorted_ref)
        if np.isfinite(x) and n_ref > 0:
            lo = bisect.bisect_left(sorted_ref, x)
            hi = bisect.bisect_right(sorted_ref, x)
            out[i] = (lo + 0.5 * (hi - lo)) / n_ref
        if len(raw_window) >= window:
            _pop_oldest()
        _push(x)
    return out


def n_eff_l(l_minutes: int, ref_days: int = REF_DAYS) -> int:
    return int(ref_days * 24 * 60 // l_minutes)


def n_eff_h(h_minutes: int, ref_days: int = REF_DAYS) -> int:
    return int(ref_days * 24 * 60 // h_minutes)


def reference_overlap_disclosure(l_minutes: int, q: float = TREND_Q) -> dict:
    neff = n_eff_l(l_minutes)
    return {
        "l_minutes": l_minutes,
        "q": q,
        "n_eff_l": neff,
        "q80_tail_proxy": 0.20 * neff,
    }


def direction_of(trend_ret: np.ndarray) -> np.ndarray:
    out = np.zeros(len(trend_ret), dtype=np.int8)
    out[trend_ret > 0] = DIR_UP
    out[trend_ret < 0] = DIR_DOWN
    return out


def established_trend_mask(trend_pctl: np.ndarray, trend_ret: np.ndarray, q: float = TREND_Q) -> np.ndarray:
    return np.isfinite(trend_pctl) & (trend_pctl >= q) & np.isfinite(trend_ret) & (trend_ret != 0.0)


def compute_pullback_depth(signed_pb_ret: np.ndarray, trend_ret: np.ndarray) -> np.ndarray:
    """PULLBACK_DEPTH = -SIGNED_PB_RET / abs(TREND_RET_L). Defined
    (finite) only where SIGNED_PB_RET<0 and abs(TREND_RET_L) is finite and
    >0; NaN elsewhere -- no floor, no repair."""
    denom = np.abs(trend_ret)
    denom_ok = np.isfinite(denom) & (denom > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        depth = -signed_pb_ret / denom
    ok = denom_ok & np.isfinite(signed_pb_ret) & (signed_pb_ret < 0)
    return np.where(ok, depth, np.nan)


def compute_recent_ratio(signed_pb_ret: np.ndarray, trend_ret: np.ndarray) -> np.ndarray:
    """RECENT_RATIO = SIGNED_PB_RET / abs(TREND_RET_L) -- signed, used only
    by the structural control (no depth<0 restriction)."""
    denom = np.abs(trend_ret)
    denom_ok = np.isfinite(denom) & (denom > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = signed_pb_ret / denom
    ok = denom_ok & np.isfinite(signed_pb_ret)
    return np.where(ok, ratio, np.nan)


def depth_band_index(depth: np.ndarray) -> np.ndarray:
    """-1 = not a primary H04 candidate (depth<0.10, depth>=1.0, or NaN).
    0=shallow [0.10,0.25), 1=moderate [0.25,0.40), 2=deep [0.40,1.00)."""
    out = np.full(len(depth), -1, dtype=np.int8)
    valid = np.isfinite(depth) & (depth >= 0.10) & (depth < 1.00)
    d = depth[valid]
    band = np.full(d.shape, -1, dtype=np.int8)
    band[(d >= 0.10) & (d < 0.25)] = 0
    band[(d >= 0.25) & (d < 0.40)] = 1
    band[(d >= 0.40) & (d < 1.00)] = 2
    out[valid] = band
    return out


def fixed_depth_bin_index(depth: np.ndarray) -> np.ndarray:
    """Diagnostic-only 5-bin decomposition: [0,.10),[.10,.25),[.25,.40),
    [.40,.60),[.60,1.00). -1 outside [0,1.0) or NaN."""
    out = np.full(len(depth), -1, dtype=np.int8)
    valid = np.isfinite(depth) & (depth >= 0.0) & (depth < 1.00)
    d = depth[valid]
    bin_idx = np.full(d.shape, -1, dtype=np.int8)
    edges = (0.0, 0.10, 0.25, 0.40, 0.60, 1.00)
    for k in range(5):
        sel = (d >= edges[k]) & (d < edges[k + 1])
        bin_idx[sel] = k
    out[valid] = bin_idx
    return out


def trend_strength_bin_index(trend_pctl: np.ndarray) -> np.ndarray:
    """0 = [0.80,0.90), 1 = [0.90,1.00]. -1 if trend_pctl < 0.80 or NaN
    (should not occur once gated by established_trend_mask)."""
    out = np.full(len(trend_pctl), -1, dtype=np.int8)
    valid = np.isfinite(trend_pctl) & (trend_pctl >= 0.80)
    p = trend_pctl[valid]
    idx = np.where(p < 0.90, 0, 1)
    out[valid] = idx
    return out


def pullback_candidate_mask(trend_pctl: np.ndarray, trend_ret: np.ndarray, signed_pb_ret: np.ndarray,
                             band_idx: np.ndarray, band: int, q: float = TREND_Q) -> np.ndarray:
    return (
        established_trend_mask(trend_pctl, trend_ret, q)
        & np.isfinite(signed_pb_ret) & (signed_pb_ret < 0.0)
        & (band_idx == band)
    )


def structural_control_mask(trend_pctl: np.ndarray, trend_ret: np.ndarray, recent_ratio: np.ndarray,
                             q: float = TREND_Q, ratio_threshold: float = STRUCTURAL_RATIO_THRESHOLD) -> np.ndarray:
    return (
        established_trend_mask(trend_pctl, trend_ret, q)
        & np.isfinite(recent_ratio) & (np.abs(recent_ratio) < ratio_threshold)
    )


# ---------------------------------------------------------------------------
# refractory
# ---------------------------------------------------------------------------
def apply_refractory(t_ms: np.ndarray, mask: np.ndarray, refractory_ms: int = REFRACTORY_MS) -> np.ndarray:
    out = np.zeros(len(mask), dtype=bool)
    last = -10 ** 18
    for i in np.flatnonzero(mask):
        t = int(t_ms[i])
        if t >= last + refractory_ms:
            out[i] = True
            last = t
    return out


# ---------------------------------------------------------------------------
# horizons / normalization
# ---------------------------------------------------------------------------
def compute_horizon_return(close: np.ndarray, t_ms: np.ndarray, h_minutes: int,
                            dev_end_ms: int = DEV_END_MS) -> np.ndarray:
    """RET_H(T) = ln(close(T+H)/close(T)). Eligible only if T+H resolves
    strictly before dev_end_ms -- no truncation, ineligible rows are NaN."""
    h_bars = h_minutes // HTF_MIN
    n = len(close)
    out = np.full(n, np.nan, dtype=np.float64)
    dst = np.arange(n) + h_bars
    ok = dst < n
    ok &= (t_ms + h_minutes * BAR_MS) < dev_end_ms
    c0 = close
    c1 = np.full(n, np.nan, dtype=np.float64)
    c1[ok] = close[dst[ok]]
    with np.errstate(divide="ignore", invalid="ignore"):
        out[ok] = np.log(c1[ok] / c0[ok])
    out[~np.isfinite(c0) | (c0 <= 0)] = np.nan
    return out


def trailing_median_known(values: np.ndarray, window: int, known_lag_steps: int) -> np.ndarray:
    """Median of values[i-window : i-known_lag_steps+1] -- i.e. only
    reference observations whose own H-horizon outcome is fully resolved
    strictly before T (t' + H <= T). Current/future observations excluded."""
    w = window - known_lag_steps + 1
    n = len(values)
    out = np.full(n, np.nan, dtype=np.float64)
    if w <= 0 or n == 0:
        return out
    rm = pd.Series(values, copy=False).rolling(w, min_periods=w).median().to_numpy()
    src = np.arange(n) - known_lag_steps
    ok = src >= w - 1
    out[ok] = rm[src[ok]]
    return out


def normalize(cont_ret: np.ndarray, scale: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """NORM_TREND_CONT_RET_H = TREND_CONT_RET_H / PAST_MEDIAN_ABS_RET_H(T).
    No floor: a zero/non-finite/unavailable denominator makes the outcome
    ineligible (returned as NaN), never repaired, never floored. Returns
    (normalized, eligible_mask)."""
    denom_ok = np.isfinite(scale) & (scale > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        norm = cont_ret / scale
    eligible = denom_ok & np.isfinite(cont_ret) & np.isfinite(norm)
    norm = np.where(eligible, norm, np.nan)
    return norm, eligible


def denominator_diagnostics(scale: np.ndarray, norm: np.ndarray) -> dict:
    valid_scale = scale[np.isfinite(scale) & (scale > 0)]
    out = {
        "min": None, "p01": None, "p05": None, "p25": None, "p50": None,
        "top1pct_normalized_influence_share": None,
    }
    if valid_scale.size:
        out["min"] = float(np.min(valid_scale))
        out["p01"] = float(np.percentile(valid_scale, 1))
        out["p05"] = float(np.percentile(valid_scale, 5))
        out["p25"] = float(np.percentile(valid_scale, 25))
        out["p50"] = float(np.percentile(valid_scale, 50))
    abs_norm = np.abs(norm[np.isfinite(norm)])
    if abs_norm.size:
        total = float(np.sum(abs_norm))
        if total > 0:
            k = max(1, int(np.ceil(0.01 * abs_norm.size)))
            top_k = np.sort(abs_norm)[-k:]
            out["top1pct_normalized_influence_share"] = float(np.sum(top_k) / total)
    return out


def path_mfe_mae(high: np.ndarray, low: np.ndarray, close: np.ndarray, i: int,
                  h_bars: int, direction: int) -> tuple[float, float]:
    a = i + 1
    b = i + h_bars + 1
    mx = float(np.max(high[a:b]))
    mn = float(np.min(low[a:b]))
    c0 = float(close[i])
    if c0 <= 0 or mx <= 0 or mn <= 0:
        return float("nan"), float("nan")
    if direction == DIR_UP:
        mfe = float(np.log(mx / c0))
        mae = float(np.log(c0 / mn))
    else:
        mfe = float(np.log(c0 / mn))
        mae = float(np.log(mx / c0))
    return mfe, mae


# ---------------------------------------------------------------------------
# matched-random baseline
# ---------------------------------------------------------------------------
def build_matched_random_pool(all_grid_idx: np.ndarray, raw_extreme_idx: np.ndarray) -> np.ndarray:
    """The random pool excludes every RAW qualifying H04 candidate
    timestamp for this (L, depth-band) (before refractory dedup) but does
    NOT exclude surrounding hours/whole volatile regimes -- only the exact
    treated indices. Membership exclusion (np.isin): `all_grid_idx` and
    `raw_extreme_idx` are values in the same panel-index space, not
    necessarily a contiguous 0..n-1 range, so fancy-indexing raw ids into
    len(all_grid_idx) would be wrong -- this is the exact bug class H03's
    post-freeze audit found and it must not recur here."""
    excluded = np.isin(all_grid_idx, raw_extreme_idx)
    return all_grid_idx[~excluded]


def sample_matched_random_once(
    rng: np.random.Generator, pool_by_month: dict, need_up_by_month: dict, need_down_by_month: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Draw ONE replicate WITHOUT REPLACEMENT from the already-excluded
    pool; assign each drawn observation the paired real candidate's trend
    direction. `rng` is shared across all replicates of a cell so the
    frozen seed is consumed exactly once per cell, not re-seeded per
    replicate."""
    idx_out = []
    dir_out = []
    for month, pool in pool_by_month.items():
        n_up = need_up_by_month.get(month, 0)
        n_down = need_down_by_month.get(month, 0)
        need = n_up + n_down
        if need == 0:
            continue
        if need > len(pool):
            raise H04Error(f"matched-random need={need} exceeds eligible pool {len(pool)} in {month}")
        picked = rng.choice(pool, size=need, replace=False)
        labels = np.empty(need, dtype=np.int8)
        labels[:n_up] = DIR_UP
        labels[n_up:] = DIR_DOWN
        rng.shuffle(labels)
        idx_out.append(picked)
        dir_out.append(labels)
    if not idx_out:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int8)
    return np.concatenate(idx_out), np.concatenate(dir_out)


def total_variation_distance(dist_a: dict, dist_b: dict) -> float:
    """TVD = 0.5 * sum_i |p_i - q_i| over the union of categorical keys."""
    keys = set(dist_a) | set(dist_b)
    n_a = sum(dist_a.values()) or 1
    n_b = sum(dist_b.values()) or 1
    total = 0.0
    for k in keys:
        p = dist_a.get(k, 0) / n_a
        q = dist_b.get(k, 0) / n_b
        total += abs(p - q)
    return 0.5 * total


def categorical_counts(keys: list[str]) -> dict:
    out: dict = {}
    for k in keys:
        out[k] = out.get(k, 0) + 1
    return out


# ---------------------------------------------------------------------------
# negative control
# ---------------------------------------------------------------------------
def collision_fraction(shifted_t_ms: np.ndarray, raw_extreme_t_ms: np.ndarray) -> float:
    """Fraction of shifted timestamps that land exactly on a raw true H04
    candidate timestamp for the same (L, depth-band). Never removed --
    reported only."""
    if shifted_t_ms.size == 0:
        return 0.0
    raw_set = set(int(x) for x in raw_extreme_t_ms)
    hits = sum(1 for t in shifted_t_ms if int(t) in raw_set)
    return float(hits) / float(shifted_t_ms.size)


# ---------------------------------------------------------------------------
# control materiality / MPIE gates
# ---------------------------------------------------------------------------
def control_gate(mean_a: Optional[float], mean_b: Optional[float], sign: int,
                  delta_min: float = CONTROL_DELTA_MIN) -> Optional[bool]:
    """S * (mean_a - mean_b) >= delta_min. None if either mean is missing."""
    if mean_a is None or mean_b is None:
        return None
    return (sign * (mean_a - mean_b)) >= delta_min


def mpie_gate(mean_candidate: Optional[float], mean_matched: Optional[float], sign: int,
              mpie: float = MPIE) -> Optional[bool]:
    if mean_candidate is None or mean_matched is None:
        return None
    return (sign * (mean_candidate - mean_matched)) >= mpie


# ---------------------------------------------------------------------------
# dependence diagnostic
# ---------------------------------------------------------------------------
def daily_total_abs_return_series(t_ms: np.ndarray, close: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Daily series of total absolute 15m log-returns -- candidate/outcome
    -independent. Returns (day_keys_sorted, daily_totals)."""
    ret = np.full(len(close), np.nan, dtype=np.float64)
    ret[1:] = np.log(close[1:] / close[:-1])
    days = np.array([utc_day_key(int(x)) for x in t_ms])
    df = pd.DataFrame({"day": days, "abs_ret": np.abs(ret)})
    daily = df.groupby("day", sort=True)["abs_ret"].sum(min_count=1)
    return daily.index.to_numpy(), daily.to_numpy(dtype=np.float64)


def autocorrelation_at_lag(series: np.ndarray, lag: int) -> float:
    x = series[np.isfinite(series)]
    if lag <= 0 or lag >= len(series) or len(x) < 3:
        return float("nan")
    s = pd.Series(series)
    return float(s.autocorr(lag=lag))


def long_dependence_diagnostic(daily_series: np.ndarray,
                                lags_days: tuple[int, ...] = DEP_LAGS_DAYS,
                                threshold: float = DEP_ACF_THRESHOLD) -> dict:
    """L_dep = max{L in lags_days : |ACF(L)| >= threshold}. Uses the LARGEST
    qualifying lag, not the first crossing -- a non-monotone ACF that dips
    below threshold early and rises again later must not be reported as
    short dependence."""
    acf_by_lag = {lag: autocorrelation_at_lag(daily_series, lag) for lag in lags_days}
    qualifying = [lag for lag, v in acf_by_lag.items() if np.isfinite(v) and abs(v) >= threshold]
    if not qualifying:
        label = "<1 day"
        l_dep = None
    else:
        l_dep = max(qualifying)
        label = f">={l_dep} days" if l_dep == max(lags_days) else f"{l_dep} days"
    return {"acf_by_lag_days": acf_by_lag, "l_dep_days": l_dep, "l_dep_label": label}


# ---------------------------------------------------------------------------
# direction-symmetry verdict
# ---------------------------------------------------------------------------
def symmetric_claim_verdict(up_supports_continuation: Optional[bool], down_supports_continuation: Optional[bool]) -> dict:
    """H04 is symmetric: a continuation claim is only promotable if BOTH
    UPTREND and DOWNTREND support continuation overall. One side alone
    rejects the symmetric claim and records the asymmetric observation as
    POSTHOC_UNTESTED; it can never promote H04 or enter Batch 01
    validation. H04 has no exhaustion alternative sign."""
    if up_supports_continuation is True and down_supports_continuation is True:
        return {"symmetric_claim": "SUPPORTED", "posthoc_untested": False}
    if up_supports_continuation is True and down_supports_continuation is False:
        return {"symmetric_claim": "REJECTED_SPECIFIC_CLAIM", "posthoc_untested": True,
                "asymmetric_side": "UPTREND"}
    if down_supports_continuation is True and up_supports_continuation is False:
        return {"symmetric_claim": "REJECTED_SPECIFIC_CLAIM", "posthoc_untested": True,
                "asymmetric_side": "DOWNTREND"}
    return {"symmetric_claim": "REJECTED_SPECIFIC_CLAIM", "posthoc_untested": False}


# ---------------------------------------------------------------------------
# adjacency helpers (parameter-robustness promotion logic)
# ---------------------------------------------------------------------------
def has_adjacent_pair_support(ordered_keys: tuple, support: dict) -> bool:
    """True iff at least one pair of ADJACENT keys (in ordered_keys) both
    map to True in `support`. Used for both the two-adjacent-depth-band and
    the two-adjacent-horizon promotion requirements -- a single isolated
    supporting key is not sufficient."""
    for a, b in zip(ordered_keys[:-1], ordered_keys[1:]):
        if support.get(a) is True and support.get(b) is True:
            return True
    return False


# ---------------------------------------------------------------------------
# summary stats
# ---------------------------------------------------------------------------
def _mean(x: np.ndarray) -> Optional[float]:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    return float(np.mean(x)) if x.size else None


def _median(x: np.ndarray) -> Optional[float]:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    return float(np.median(x)) if x.size else None


def _pct(x: np.ndarray, q: float) -> Optional[float]:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    return float(np.percentile(x, q)) if x.size else None


def _share_pos(x: np.ndarray) -> Optional[float]:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    return float(np.mean(x > 0)) if x.size else None


def _share_neg(x: np.ndarray) -> Optional[float]:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    return float(np.mean(x < 0)) if x.size else None


def metric_block(cont_ret: np.ndarray, norm: np.ndarray) -> dict:
    n = int(np.sum(np.isfinite(norm)))
    mean_bps = _mean(cont_ret)
    return {
        "N": n,
        "mean_norm_trend_cont_ret": _mean(norm),
        "median_norm_trend_cont_ret": _median(norm),
        "mean_trend_cont_ret_bps": None if mean_bps is None else float(mean_bps * 10_000.0),
        "p_trend_cont_ret_pos": _share_pos(cont_ret),
        "p_trend_cont_ret_neg": _share_neg(cont_ret),
        "p05_norm_trend_cont_ret": _pct(norm, 5),
        "p25_norm_trend_cont_ret": _pct(norm, 25),
        "p75_norm_trend_cont_ret": _pct(norm, 75),
        "p95_norm_trend_cont_ret": _pct(norm, 95),
    }


def concentration_from_times(t_ms: np.ndarray, direction: Optional[np.ndarray] = None) -> dict:
    if t_ms.size == 0:
        return {
            "raw_n": 0, "unique_utc_days": 0, "unique_utc_weeks": 0, "unique_utc_months": 0,
            "by_year": {}, "by_month": {}, "largest_month_share": None, "top5_month_share": None,
            "uptrend_share": None, "downtrend_share": None, "median_spacing_minutes": None,
        }
    days = {utc_day_key(int(x)) for x in t_ms}
    weeks = {utc_week_key(int(x)) for x in t_ms}
    months = [utc_month_key(int(x)) for x in t_ms]
    years = [utc_year(int(x)) for x in t_ms]
    month_counts = categorical_counts(months)
    year_counts = categorical_counts([str(y) for y in years])
    n = int(t_ms.size)
    ordered = sorted(month_counts.items(), key=lambda kv: kv[1], reverse=True)
    spacing = None
    if n >= 2:
        diffs = np.diff(np.sort(t_ms.astype(np.int64))) / BAR_MS
        spacing = float(np.median(diffs))
    up_share = down_share = None
    if direction is not None and direction.size:
        up_share = float(np.mean(direction == DIR_UP))
        down_share = float(np.mean(direction == DIR_DOWN))
    return {
        "raw_n": n,
        "unique_utc_days": len(days),
        "unique_utc_weeks": len(weeks),
        "unique_utc_months": len(month_counts),
        "by_year": year_counts,
        "by_month": dict(ordered),
        "largest_month_share": float(ordered[0][1] / n),
        "top5_month_share": float(sum(c for _, c in ordered[:5]) / n),
        "uptrend_share": up_share,
        "downtrend_share": down_share,
        "median_spacing_minutes": spacing,
    }


def dumps_json(obj: dict) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n"


# ---------------------------------------------------------------------------
# panel / per-cell evaluation (frozen pipeline; exercised only against
# synthetic fixtures in this preregistration/implementation-freeze task)
# ---------------------------------------------------------------------------
def build_panel(frame15: dict) -> dict:
    t = frame15["t_ms"]
    close = frame15["close"]
    high = frame15["high"]
    low = frame15["low"]
    t_max = development_t_max_ms()
    in_dev = (t >= DEV_START_MS) & (t <= t_max)

    raw_pb_ret = compute_raw_pullback_return(close)

    trend_ret: dict = {}
    trend_pctl: dict = {}
    direction: dict = {}
    signed_pb_ret: dict = {}
    depth: dict = {}
    recent_ratio: dict = {}
    band_idx: dict = {}
    fixed_bin_idx: dict = {}
    strength_bin: dict = {}
    for L in L_WINDOWS:
        tr = compute_trend_returns(close, L)
        pctl = rolling_midrank_percentile(np.abs(tr), REF_STEPS)
        d = direction_of(tr)
        spb = d.astype(np.float64) * raw_pb_ret
        depth_l = compute_pullback_depth(spb, tr)
        ratio_l = compute_recent_ratio(spb, tr)
        trend_ret[L] = tr
        trend_pctl[L] = pctl
        direction[L] = d
        signed_pb_ret[L] = spb
        depth[L] = depth_l
        recent_ratio[L] = ratio_l
        band_idx[L] = depth_band_index(depth_l)
        fixed_bin_idx[L] = fixed_depth_bin_index(depth_l)
        strength_bin[L] = trend_strength_bin_index(pctl)

    ret: dict = {}
    scale: dict = {}
    for H in HORIZONS:
        h_bars = H // HTF_MIN
        r = compute_horizon_return(close, t, H)
        ret[H] = r
        sc = trailing_median_known(np.abs(r), REF_STEPS, h_bars)
        scale[H] = np.where(sc > 0, sc, np.nan)

    month = np.array([utc_month_key(int(x)) for x in t])
    week = np.array([utc_week_key(int(x)) for x in t])
    year = np.array([utc_year(int(x)) for x in t], dtype=np.int16)
    dow = np.array([utc_dow_key(int(x)) for x in t])
    dom = np.array([utc_dom_key(int(x)) for x in t])

    day_keys, daily_abs = daily_total_abs_return_series(t, close)
    long_dependence = long_dependence_diagnostic(daily_abs)

    return {
        "t_ms": t, "close": close, "high": high, "low": low,
        "in_development": in_dev,
        "trend_ret": trend_ret, "trend_pctl": trend_pctl, "direction": direction,
        "signed_pb_ret": signed_pb_ret, "depth": depth, "recent_ratio": recent_ratio,
        "band_idx": band_idx, "fixed_bin_idx": fixed_bin_idx, "strength_bin": strength_bin,
        "ret": ret, "scale": scale,
        "month_key": month, "week_key": week, "year": year, "dow_key": dow, "dom_key": dom,
        "t_max_inclusive": t_max,
        "long_dependence": long_dependence,
    }


def eligible_index(panel: dict, l_minutes: int, h_minutes: int) -> np.ndarray:
    return np.flatnonzero(
        panel["in_development"]
        & np.isfinite(panel["trend_ret"][l_minutes])
        & np.isfinite(panel["trend_pctl"][l_minutes])
        & np.isfinite(panel["ret"][h_minutes])
        & np.isfinite(panel["scale"][h_minutes])
    )


def outcome_bundle(panel: dict, idx: np.ndarray, l_minutes: int, h_minutes: int) -> dict:
    direction = panel["direction"][l_minutes][idx].astype(np.int64)
    ret = panel["ret"][h_minutes][idx]
    scale = panel["scale"][h_minutes][idx]
    cont_ret = direction.astype(np.float64) * ret
    norm, elig = normalize(cont_ret, scale)
    idx = idx[elig]
    direction = direction[elig]
    cont_ret = cont_ret[elig]
    norm = norm[elig]
    scale = scale[elig]
    t = panel["t_ms"][idx]
    h_bars = h_minutes // HTF_MIN
    mfe = np.full(idx.size, np.nan, dtype=np.float64)
    mae = np.full(idx.size, np.nan, dtype=np.float64)
    for k, i in enumerate(idx):
        mfe[k], mae[k] = path_mfe_mae(panel["high"], panel["low"], panel["close"], int(i), h_bars, int(direction[k]))
    with np.errstate(divide="ignore", invalid="ignore"):
        norm_mfe = mfe / scale
        norm_mae = mae / scale
    return {
        "idx": idx, "t_ms": t, "direction": direction, "cont_ret": cont_ret, "norm": norm,
        "scale": scale, "mfe": mfe, "mae": mae, "norm_mfe": norm_mfe, "norm_mae": norm_mae,
        "month": panel["month_key"][idx], "week": panel["week_key"][idx], "year": panel["year"][idx],
        "dow": panel["dow_key"][idx], "dom": panel["dom_key"][idx],
        "strength_bin": panel["strength_bin"][l_minutes][idx],
    }


def structural_control_bundle(panel: dict, cand: dict, l_minutes: int, h_minutes: int, elig_set: np.ndarray) -> dict:
    """Established trend + near-neutral recent move (abs(RECENT_RATIO)<0.10).
    Independent 60m refractory.

    Frozen deterministic stratified standardization (pre-outcome
    correction -- see docs/reviews/H04_PREREG_PREOUTCOME_CORRECTION.md):
    the primary structural comparison is standardized to the exact
    calendar-month x trend-direction x trend-strength-bin strata shared by
    both the candidate and the near-neutral control population (the
    "overlap" strata), weighted by the candidate's own stratum frequency.
    This isolates the incremental value of the pullback shape from generic
    trend-strength/month/direction composition differences between the two
    populations -- comparing the unstandardized full control population
    (as an earlier version of this function did) can reflect population
    MIX rather than the pullback ingredient itself, in either direction
    (false positive or false negative).

    Strata where the control has observations but the candidate has none
    receive zero candidate weight and do not influence the standardized
    means (H04 asks what the candidate population looks like relative to
    the near-neutral control state, not the unconditional composition of
    all near-neutral trend moments). Candidate observations whose exact
    stratum has no eligible control observation are outside the identified
    overlap population; they are excluded from the standardized comparison
    and reported explicitly (matched/unmatched candidate N and share,
    strata counts) -- never silently dropped from reporting, and no
    post-outcome fallback matching hierarchy is used."""
    t_arr = panel["t_ms"]
    ctrl_mask = structural_control_mask(
        panel["trend_pctl"][l_minutes], panel["trend_ret"][l_minutes], panel["recent_ratio"][l_minutes],
    ) & panel["in_development"]
    ctrl_kept = apply_refractory(t_arr, ctrl_mask)
    ctrl_idx = np.flatnonzero(ctrl_kept & elig_set)
    ctrl = outcome_bundle(panel, ctrl_idx, l_minutes, h_minutes)

    cand_keys = list(zip(cand["month"].tolist(), cand["direction"].tolist(), cand["strength_bin"].tolist()))
    ctrl_keys = list(zip(ctrl["month"].tolist(), ctrl["direction"].tolist(), ctrl["strength_bin"].tolist()))

    cand_by_stratum: dict = {}
    for k, v in zip(cand_keys, cand["norm"]):
        cand_by_stratum.setdefault(k, []).append(v)
    ctrl_by_stratum: dict = {}
    for k, v in zip(ctrl_keys, ctrl["norm"]):
        ctrl_by_stratum.setdefault(k, []).append(v)

    cand_strata = set(cand_by_stratum)
    ctrl_strata = set(ctrl_by_stratum)
    overlap_strata = cand_strata & ctrl_strata

    candidate_total_n = len(cand_keys)
    matched_candidate_mask = np.array([k in ctrl_strata for k in cand_keys], dtype=bool)
    matched_candidate_n = int(np.sum(matched_candidate_mask))
    unmatched_candidate_n = candidate_total_n - matched_candidate_n
    unmatched_candidate_share = float(unmatched_candidate_n / candidate_total_n) if candidate_total_n else None

    cand_stratum_mean: dict = {}
    ctrl_stratum_mean: dict = {}
    cand_stratum_n: dict = {}
    for k in overlap_strata:
        cv = np.asarray(cand_by_stratum[k], dtype=np.float64)
        cv = cv[np.isfinite(cv)]
        kv = np.asarray(ctrl_by_stratum[k], dtype=np.float64)
        kv = kv[np.isfinite(kv)]
        if cv.size == 0 or kv.size == 0:
            continue
        cand_stratum_mean[k] = float(np.mean(cv))
        ctrl_stratum_mean[k] = float(np.mean(kv))
        cand_stratum_n[k] = cv.size

    total_overlap_cand_n = sum(cand_stratum_n.values())
    if total_overlap_cand_n > 0:
        weight = {k: n / total_overlap_cand_n for k, n in cand_stratum_n.items()}
        candidate_standardized_mean = sum(weight[k] * cand_stratum_mean[k] for k in weight)
        control_standardized_mean = sum(weight[k] * ctrl_stratum_mean[k] for k in weight)
        standardized_delta = candidate_standardized_mean - control_standardized_mean
    else:
        candidate_standardized_mean = None
        control_standardized_mean = None
        standardized_delta = None

    return {
        "candidate_standardized_mean": candidate_standardized_mean,
        "control_standardized_mean": control_standardized_mean,
        "standardized_delta": standardized_delta,
        "structural_gate": control_gate(candidate_standardized_mean, control_standardized_mean, DIR_UP),
        "candidate_total_N": candidate_total_n,
        "matched_candidate_N": matched_candidate_n,
        "unmatched_candidate_N": unmatched_candidate_n,
        "unmatched_candidate_share": unmatched_candidate_share,
        "control_total_N": int(len(ctrl_keys)),
        "number_of_candidate_strata": len(cand_strata),
        "number_of_matched_strata": len(overlap_strata),
        "number_of_unmatched_candidate_strata": len(cand_strata - ctrl_strata),
        # Descriptive only -- MUST NOT feed the structural gate.
        "full_control_unstandardized_mean": _mean(ctrl["norm"]),
    }


def matched_random_bundle(
    panel: dict, cand: dict, pool_idx: np.ndarray, h_minutes: int,
    seed: int = SEED_MATCHED, replicates: int = N_MATCHED,
) -> dict:
    """One frozen seed consumed exactly once across all `replicates` draws.
    Reports the across-replicate mean of the per-replicate mean
    NORM_TREND_CONT_RET_H and positive-share -- the matched-random control
    distribution, never treated as independent market evidence."""
    empty = {
        "N_replicates": replicates, "seed": seed,
        "candidate_mean": None, "matched_mean": None, "candidate_minus_matched": None,
        "candidate_positive_share": None, "matched_positive_share": None, "positive_share_difference": None,
        "matched_mean_distribution": {"p025": None, "p50": None, "p975": None},
        "matched_positive_share_distribution": {"p025": None, "p50": None, "p975": None},
        "residual_diagnostic": None,
    }
    cand_mean = _mean(cand["norm"])
    cand_pos = _share_pos(cand["cont_ret"])
    if cand["idx"].size == 0 or pool_idx.size == 0:
        empty["candidate_mean"] = cand_mean
        empty["candidate_positive_share"] = cand_pos
        return empty

    months = panel["month_key"]
    ret = panel["ret"][h_minutes]
    scale = panel["scale"][h_minutes]

    need_up: dict = {}
    need_down: dict = {}
    pool_by_month: dict = {}
    for m in np.unique(cand["month"]):
        m = str(m)
        sel = cand["month"] == m
        need_up[m] = int(np.sum(sel & (cand["direction"] == DIR_UP)))
        need_down[m] = int(np.sum(sel & (cand["direction"] == DIR_DOWN)))
        pool_by_month[m] = pool_idx[months[pool_idx] == m]
        need = need_up[m] + need_down[m]
        if need > pool_by_month[m].size:
            raise H04Error(f"matched-random n={need} exceeds eligible {pool_by_month[m].size} in {m}")

    rng = np.random.default_rng(seed)
    replicate_means = []
    replicate_pos = []
    last_dow_dist: dict = {}
    last_dom_dist: dict = {}
    for _ in range(replicates):
        picked, labels = sample_matched_random_once(rng, pool_by_month, need_up, need_down)
        if picked.size == 0:
            replicate_means.append(np.nan)
            replicate_pos.append(np.nan)
            continue
        r = labels.astype(np.float64) * ret[picked]
        sc = scale[picked]
        ok = np.isfinite(r) & np.isfinite(sc) & (sc > 0)
        norm = r[ok] / sc[ok]
        replicate_means.append(float(np.mean(norm)) if norm.size else np.nan)
        replicate_pos.append(float(np.mean(r[ok] > 0)) if np.any(ok) else np.nan)
        # CRITICAL: calendar keys must come from real timestamps (t_ms of the
        # picked panel positions), never the panel indices themselves --
        # this is a direct, required response to H03's post-freeze TVD
        # erratum (docs/reviews/H03_POSTFREEZE_RESULT_AUDIT.md section 4).
        picked_t_ms = panel["t_ms"][picked]
        last_dow_dist = categorical_counts([utc_dow_key(int(x)) for x in picked_t_ms])
        last_dom_dist = categorical_counts([utc_dom_key(int(x)) for x in picked_t_ms])

    arr = np.asarray(replicate_means, dtype=np.float64)
    parr = np.asarray(replicate_pos, dtype=np.float64)
    real_dow = categorical_counts(list(cand["dow"]))
    real_dom = categorical_counts(list(cand["dom"]))
    matched_mean = float(np.nanmean(arr)) if np.any(np.isfinite(arr)) else None
    matched_pos = float(np.nanmean(parr)) if np.any(np.isfinite(parr)) else None

    def _distribution(values: np.ndarray) -> dict:
        v = values[np.isfinite(values)]
        if v.size == 0:
            return {"p025": None, "p50": None, "p975": None}
        return {
            "p025": float(np.percentile(v, 2.5)),
            "p50": float(np.percentile(v, 50)),
            "p975": float(np.percentile(v, 97.5)),
        }

    return {
        "N_replicates": replicates,
        "seed": seed,
        "candidate_mean": cand_mean,
        "matched_mean": matched_mean,
        "candidate_minus_matched": None if (cand_mean is None or matched_mean is None) else cand_mean - matched_mean,
        "candidate_positive_share": cand_pos,
        "matched_positive_share": matched_pos,
        "positive_share_difference": None if (cand_pos is None or matched_pos is None) else cand_pos - matched_pos,
        # Descriptive control uncertainty -- the spread of the 100
        # matched-random replicate means/positive-shares, NOT 100
        # independent market samples and NOT a confidence interval for the
        # MPIE candidate-minus-matched contrast (see
        # docs/reviews/H04_PREREG_PREOUTCOME_CORRECTION.md, bootstrap-scope
        # clarification).
        "matched_mean_distribution": _distribution(arr),
        "matched_positive_share_distribution": _distribution(parr),
        "residual_diagnostic": {
            "dow_tvd": total_variation_distance(real_dow, last_dow_dist),
            "dom_tvd": total_variation_distance(real_dom, last_dom_dist),
        },
    }


def negative_control_bundle(panel: dict, cand: dict, raw_mask: np.ndarray, h_minutes: int) -> dict:
    t_arr = panel["t_ms"]
    t0 = int(t_arr[0])
    shifted_idx = []
    shifted_dir = []
    for i, d in zip(cand["idx"], cand["direction"]):
        ts = shift_plus_6h_same_utc_day(int(t_arr[i]))
        j = (ts - t0) // HTF_MS
        if j < 0 or j >= len(t_arr):
            continue
        if int(t_arr[j]) != ts:
            continue
        if not panel["in_development"][j]:
            continue
        if not np.isfinite(panel["ret"][h_minutes][j]):
            continue
        if not (np.isfinite(panel["scale"][h_minutes][j]) and panel["scale"][h_minutes][j] > 0):
            continue
        shifted_idx.append(j)
        shifted_dir.append(int(d))

    raw_extreme_t = t_arr[np.flatnonzero(raw_mask)]
    shifted_t = t_arr[np.asarray(shifted_idx, dtype=np.int64)] if shifted_idx else np.array([], dtype=np.int64)
    coll = collision_fraction(shifted_t, raw_extreme_t)

    if not shifted_idx:
        return {"N": 0, "mean_norm_trend_cont_ret": None, "p_trend_cont_ret_pos": None, "collision_fraction": coll}

    idx = np.asarray(shifted_idx, dtype=np.int64)
    direction = np.asarray(shifted_dir, dtype=np.int64)
    ret = panel["ret"][h_minutes][idx]
    scale = panel["scale"][h_minutes][idx]
    cont_ret = direction.astype(np.float64) * ret
    norm, elig = normalize(cont_ret, scale)
    return {
        "N": int(np.sum(elig)),
        "mean_norm_trend_cont_ret": _mean(norm[elig]),
        "p_trend_cont_ret_pos": _share_pos(cont_ret[elig]),
        "collision_fraction": coll,
    }


def week_block_bootstrap(week_keys: np.ndarray, norm: np.ndarray, cont_ret: np.ndarray,
                          seed: int = SEED_BOOT, replicates: int = N_BOOT) -> dict:
    """UTC-week block bootstrap, wired into per-cell output (unlike H03's
    implementation, which left this library-only and never emitted it per
    cell -- see docs/reviews/H03_POSTFREEZE_RESULT_AUDIT.md). Resamples
    whole UTC-week blocks of candidate rows with replacement, `replicates`
    times, one deterministic seed consumed once. Reports the bootstrap
    mean and a 95% percentile interval for both the normalized mean and the
    continuation-positive share."""
    empty = {
        "seed": seed, "replicates": replicates,
        "norm_mean": None, "norm_p025": None, "norm_p975": None,
        "pos_share_mean": None, "pos_share_p025": None, "pos_share_p975": None,
    }
    unique_weeks = np.unique(week_keys) if week_keys.size else np.array([])
    if unique_weeks.size == 0:
        return empty
    idx_by_week = {w: np.flatnonzero(week_keys == w) for w in unique_weeks}
    n_weeks = unique_weeks.size
    rng = np.random.default_rng(seed)
    rep_norm = np.full(replicates, np.nan, dtype=np.float64)
    rep_pos = np.full(replicates, np.nan, dtype=np.float64)
    for r in range(replicates):
        chosen = rng.choice(unique_weeks, size=n_weeks, replace=True)
        rows = np.concatenate([idx_by_week[w] for w in chosen])
        nv = norm[rows]
        nv = nv[np.isfinite(nv)]
        if nv.size:
            rep_norm[r] = float(np.mean(nv))
        cv = cont_ret[rows]
        cv = cv[np.isfinite(cv)]
        if cv.size:
            rep_pos[r] = float(np.mean(cv > 0))
    vn = rep_norm[np.isfinite(rep_norm)]
    vp = rep_pos[np.isfinite(rep_pos)]
    return {
        "seed": seed, "replicates": replicates,
        "norm_mean": float(np.mean(vn)) if vn.size else None,
        "norm_p025": float(np.percentile(vn, 2.5)) if vn.size else None,
        "norm_p975": float(np.percentile(vn, 97.5)) if vn.size else None,
        "pos_share_mean": float(np.mean(vp)) if vp.size else None,
        "pos_share_p025": float(np.percentile(vp, 2.5)) if vp.size else None,
        "pos_share_p975": float(np.percentile(vp, 97.5)) if vp.size else None,
    }


def year_breakdown(cand: dict) -> dict:
    out = {}
    for y in YEAR_BLOCKS:
        sl = cand["year"] == y
        n = int(np.sum(sl))
        out[str(y)] = {
            "N": n,
            "mean_norm_trend_cont_ret": _mean(cand["norm"][sl]) if n else None,
            "p_trend_cont_ret_pos": _share_pos(cand["cont_ret"][sl]) if n else None,
        }
    return out


def direction_breakdown(cand: dict) -> dict:
    out = {}
    for name, d in (("UPTREND", DIR_UP), ("DOWNTREND", DIR_DOWN)):
        sl = cand["direction"] == d
        out[name] = {
            "N": int(np.sum(sl)),
            "mean_norm_trend_cont_ret": _mean(cand["norm"][sl]),
            "p_trend_cont_ret_pos": _share_pos(cand["cont_ret"][sl]),
        }
    return out


def fixed_depth_band_diagnostic(panel: dict, l_minutes: int, h_minutes: int, elig_set: np.ndarray) -> list:
    """Diagnostic only -- 5 fixed bins on the same PULLBACK_DEPTH scale,
    independent of the primary exclusive 3-band construction. Never
    introduces a new threshold; cannot rescue or promote a cell."""
    fixed_bins = panel["fixed_bin_idx"][l_minutes]
    ret_h = panel["ret"][h_minutes]
    scale_h = panel["scale"][h_minutes]
    direction = panel["direction"][l_minutes]
    labels = ["[0.00,0.10)", "[0.10,0.25)", "[0.25,0.40)", "[0.40,0.60)", "[0.60,1.00)"]
    out = []
    for b in range(5):
        sel = elig_set & (fixed_bins == b) & panel["in_development"]
        idx = np.flatnonzero(sel)
        if idx.size == 0:
            out.append({"bin": labels[b], "N": 0, "mean_norm_trend_cont_ret": None, "p_trend_cont_ret_pos": None})
            continue
        cont_ret = direction[idx].astype(np.float64) * ret_h[idx]
        norm, elig = normalize(cont_ret, scale_h[idx])
        out.append({
            "bin": labels[b],
            "N": int(np.sum(elig)),
            "mean_norm_trend_cont_ret": _mean(norm[elig]),
            "p_trend_cont_ret_pos": _share_pos(cont_ret[elig]),
        })
    return out


def evaluate_cell(panel: dict, l_minutes: int, band: int, h_minutes: int) -> dict:
    t_arr = panel["t_ms"]
    band_idx = panel["band_idx"][l_minutes]
    raw_mask = (band_idx == band) & established_trend_mask(
        panel["trend_pctl"][l_minutes], panel["trend_ret"][l_minutes]
    ) & np.isfinite(panel["signed_pb_ret"][l_minutes]) & (panel["signed_pb_ret"][l_minutes] < 0) & panel["in_development"]
    raw_n = int(np.sum(raw_mask))
    kept = apply_refractory(t_arr, raw_mask)
    elig = eligible_index(panel, l_minutes, h_minutes)
    elig_set = np.zeros(len(t_arr), dtype=bool)
    elig_set[elig] = True

    cand_idx = np.flatnonzero(kept & elig_set)
    cand = outcome_bundle(panel, cand_idx, l_minutes, h_minutes)

    structural = structural_control_bundle(panel, cand, l_minutes, h_minutes, elig_set)

    raw_in_elig = np.flatnonzero(raw_mask & elig_set)
    pool_idx = build_matched_random_pool(elig, raw_in_elig)
    matched = matched_random_bundle(panel, cand, pool_idx, h_minutes)

    shift = negative_control_bundle(panel, cand, raw_mask, h_minutes)

    metrics = metric_block(cand["cont_ret"], cand["norm"])

    mean_cand = metrics["mean_norm_trend_cont_ret"]
    mean_matched = matched["matched_mean"]
    mean_shifted = shift["mean_norm_trend_cont_ret"]

    return {
        "L": l_minutes, "band": DEPTH_BAND_ORDER[band], "H": h_minutes,
        **metrics,
        "raw_pre_refractory_N": raw_n,
        "post_refractory_N": int(np.sum(kept)),
        "reference_overlap": reference_overlap_disclosure(l_minutes),
        "n_eff_h": n_eff_h(h_minutes),
        "denominator_diagnostics": denominator_diagnostics(cand["scale"], cand["norm"]),
        "matched_random": matched,
        "structural_control": structural,
        "negative_control": shift,
        "mpie_gate": mpie_gate(mean_cand, mean_matched, DIR_UP),
        # Uses the structural bundle's own standardized gate -- NOT a
        # recomputation from unstandardized full-population means. See
        # docs/reviews/H04_PREREG_PREOUTCOME_CORRECTION.md.
        "structural_gate": structural["structural_gate"],
        "negative_control_gate": control_gate(mean_cand, mean_shifted, DIR_UP),
        "year_breakdown": year_breakdown(cand),
        "direction_breakdown": direction_breakdown(cand),
        "concentration": concentration_from_times(cand["t_ms"], cand["direction"]),
        "week_block_bootstrap": week_block_bootstrap(cand["week"], cand["norm"], cand["cont_ret"]),
    }


def evaluate_h04(panel: dict) -> dict:
    cells = []
    fixed_diag: dict = {}
    for L in L_WINDOWS:
        for H in HORIZONS:
            elig = eligible_index(panel, L, H)
            elig_set = np.zeros(len(panel["t_ms"]), dtype=bool)
            elig_set[elig] = True
            fixed_diag[f"L{L}_H{H}"] = fixed_depth_band_diagnostic(panel, L, H, elig_set)
        for band in range(3):
            for H in HORIZONS:
                cells.append(evaluate_cell(panel, L, band, H))

    forbidden_months = []
    for c in cells:
        for m in c["concentration"]["by_month"].keys():
            if m.startswith("2025") or m.startswith("2026"):
                forbidden_months.append(m)
    if forbidden_months:
        raise ValidationWindowForbidden(f"result months include forbidden windows: {forbidden_months}")

    return {
        "hypothesis_id": "H04_TREND_PULLBACK_CONTINUATION",
        "dataset_id": DATASET_ID,
        "snapshot_id": REQUIRED_SNAPSHOT,
        "search_surface": {
            "trend_lookbacks": list(L_WINDOWS),
            "depth_bands": list(DEPTH_BAND_ORDER),
            "horizons": list(HORIZONS),
            "primary_threshold_cells": 45,
        },
        "long_dependence": panel["long_dependence"],
        "fixed_depth_band_diagnostic": fixed_diag,
        "windows": {
            "warmup_start_inclusive": "2020-01-01T00:00:00Z",
            "development_start_inclusive": "2020-02-01T00:00:00Z",
            "development_end_exclusive": "2025-01-01T00:00:00Z",
            "t_max_inclusive": iso_ms(panel["t_max_inclusive"]),
            "validation_untouched": True,
            "oos_untouched": True,
        },
        "cells": cells,
    }
