"""H03 extreme-impulse continuation/exhaustion helpers.

Development-only. Refuses 2025/2026 1m canonical partitions and any outcome
window that reaches 2025-01-01. Does not reuse V1/V2 detectors, or H01/H02
compression/breakout definitions. No volume/taker/trend gates.

This module intentionally does NOT execute against real accepted parquet as
part of preregistration/implementation freeze -- see
`docs/research/H03_EXTREME_IMPULSE_PREREG.md` section 22 and
`tests/research/test_h03_extreme_impulse.py`, which exercise every function
here with local synthetic fixtures only.
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
PREREG_JSON = REPO_ROOT / "docs" / "research" / "H03_EXTREME_IMPULSE_PREREG.json"
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

W_WINDOWS = (15, 30, 60)
Q_THRESHOLDS = (0.90, 0.95, 0.98)
HORIZONS = (15, 30, 60, 120, 240)
YEAR_BLOCKS = (2020, 2021, 2022, 2023, 2024)
REFRACTORY_MS = 60 * BAR_MS
SHIFT_MS = 6 * 60 * BAR_MS
SEED_MATCHED = 20260831
SEED_BOOT = 20260901
N_MATCHED = 100
N_BOOT = 2000
DIR_UP = 1
DIR_DOWN = -1
MODERATE_BAND = (0.60, 0.80)
MPIE = 0.10
CONTROL_DELTA_MIN = 0.05
DEP_LAGS_DAYS = (1, 2, 4, 8, 16, 32, 64)
DEP_ACF_THRESHOLD = 0.20


class H03Error(RuntimeError):
    pass


class ValidationWindowForbidden(H03Error):
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
        raise H03Error(f"unexpected dataset_id {data.get('dataset_id')}")
    snap = data.get("snapshot_id")
    if snap != REQUIRED_SNAPSHOT:
        raise H03Error(f"snapshot mismatch: {snap} != {REQUIRED_SNAPSHOT}")
    if data.get("status") != "ACCEPTED_FOR_DISCOVERY":
        raise H03Error(f"dataset not ACCEPTED_FOR_DISCOVERY: {data.get('status')}")
    if data.get("research_authorized") is not True:
        raise H03Error("research_authorized is not true")
    if data.get("confirmatory_authorized") is True:
        raise H03Error("confirmatory_authorized must remain false for H03")
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
            f"refusing canonical partition {name} (2025/2026 forbidden in H03 development)"
        )


def list_development_parquet_paths(dataset_root: Path) -> list[Path]:
    monthly = dataset_root / "canonical" / "1m" / "monthly"
    if not monthly.is_dir():
        raise H03Error(f"missing canonical 1m monthly dir: {monthly}")
    paths = []
    for p in sorted(monthly.glob("*.parquet")):
        year_prefix = p.name[:5]
        if year_prefix in ("2025-", "2026-"):
            continue
        year = int(p.name.split("-", 1)[0])
        if 2020 <= year <= 2024:
            paths.append(p)
    if not paths:
        raise H03Error("no 2020-2024 canonical monthly parquet found")
    return paths


def require_pyarrow() -> None:
    try:
        import pyarrow  # noqa: F401
    except ImportError as exc:
        raise H03Error("pyarrow is required; install requirements-research.txt") from exc


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
            raise H03Error(f"runtime snapshot_id {sid} != {REQUIRED_SNAPSHOT}")

    cols = ["open_time_ms", "available_at_ms", "open", "high", "low", "close"]
    buckets = {c: [] for c in ("open_time_ms", "available_at_ms", "open", "high", "low", "close")}
    for path in list_development_parquet_paths(dataset_root):
        _forbid_partition_name(path.name)
        table = pq.read_table(path, columns=cols)
        if "close_time_ms" in table.column_names:
            raise H03Error("close_time_ms must not be loaded")
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
        raise H03Error("unexpected bars before warmup start")
    if int(frame["open_time_ms"][-1]) >= DEV_END_MS:
        raise ValidationWindowForbidden("loaded 1m bars reach 2025+")
    if np.any(frame["available_at_ms"] != frame["open_time_ms"] + BAR_MS):
        raise H03Error("available_at_ms is not open_time_ms + 60s")
    return frame


def aggregate_1m_to_15m(frame_1m: dict) -> dict:
    """T = bar_end_exclusive of the 15m bar [T-15m, T). close(T) is that
    bar's close -- the close of the final canonical 1m bar whose own
    bar_end_exclusive == T. No off-by-one discretion: this is the only place
    the 1m->15m close is chosen."""
    o = frame_1m["open_time_ms"]
    n = len(o)
    if n == 0 or n % HTF_MIN != 0:
        raise H03Error(f"1m length {n} is not a multiple of {HTF_MIN}")
    if int(o[0]) % HTF_MS != 0:
        raise H03Error("1m series does not start on a 15m UTC boundary")
    expected = o[0] + np.arange(n, dtype=np.int64) * BAR_MS
    if np.any(o != expected):
        raise H03Error("1m open_time_ms is not a contiguous 1m grid")
    n15 = n // HTF_MIN
    high = frame_1m["high"].reshape(n15, HTF_MIN).max(axis=1)
    low = frame_1m["low"].reshape(n15, HTF_MIN).min(axis=1)
    open_ms = o[::HTF_MIN]
    avail = open_ms + HTF_MS
    last_1m_avail = frame_1m["available_at_ms"][HTF_MIN - 1::HTF_MIN]
    if np.any(last_1m_avail != avail):
        raise H03Error("15m available_at is not last 1m available_at in the bucket")
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
        raise H03Error("15m available_at_ms is not open_time_ms + 900s")
    return frame


# ---------------------------------------------------------------------------
# impulse / extremeness
# ---------------------------------------------------------------------------
def compute_impulse_returns(close: np.ndarray, w_minutes: int) -> np.ndarray:
    """IMPULSE_RET_W(T) = ln(close(T) / close(T-W)). close(T-W) uses the
    corresponding fully available close W minutes earlier on the same grid --
    no off-by-one discretion (step = W // HTF_MIN grid steps back)."""
    if w_minutes % HTF_MIN != 0:
        raise H03Error(f"W={w_minutes} is not a multiple of the {HTF_MIN}m grid")
    step = w_minutes // HTF_MIN
    n = len(close)
    out = np.full(n, np.nan, dtype=np.float64)
    if n <= step:
        return out
    c0 = close[step:]
    c1 = close[:-step] if step else close
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.log(c0 / c1)
    out[step:] = r
    return out


def rolling_midrank_percentile(values: np.ndarray, window: int) -> np.ndarray:
    """For index i, returns the midrank percentile of values[i] within the
    strictly-prior window values[i-window:i] (current i excluded, no future
    observations). NaNs in the reference are excluded from N_ref for that
    step. Returns NaN wherever values[i] is NaN or fewer than one valid
    reference observation is available.

    Formula (frozen, H01-compatible):
        P(T) = (count(ref < x) + 0.5 * count(ref == x)) / N_ref

    Implemented with an incrementally maintained sorted reference list
    (bisect insert/remove) rather than a materialized (n, window) boolean
    matrix, since window is O(2880) and this must stay correct (not
    necessarily fast) for the synthetic fixtures this preregistration/
    implementation-freeze task tests against. A full 2020-2024 development
    run would benefit from a more optimized rolling rank/order-statistic
    structure; that optimization is out of scope here (no real-data run is
    performed in this task)."""
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
        # slide the window forward: value i now becomes part of future
        # references; if the window has reached its capacity, drop the
        # oldest entry before adding this one.
        if len(raw_window) >= window:
            _pop_oldest()
        _push(x)
    return out


def n_eff_w(w_minutes: int, ref_days: int = REF_DAYS) -> int:
    return int(ref_days * 24 * 60 // w_minutes)


def n_eff_h(h_minutes: int, ref_days: int = REF_DAYS) -> int:
    return int(ref_days * 24 * 60 // h_minutes)


def reference_overlap_disclosure(w_minutes: int, q: float) -> dict:
    neff = n_eff_w(w_minutes)
    return {
        "w_minutes": w_minutes,
        "q": q,
        "n_eff_w": neff,
        "tail_proxy": neff * (1.0 - q),
        "moderate_band_proxy": 0.20 * neff,
        "decile_proxy": 0.10 * neff,
    }


def extreme_candidate_mask(p_w: np.ndarray, impulse_ret: np.ndarray, q: float) -> np.ndarray:
    """P_W(T) >= q, excluding exact-zero impulse (no direction) and NaN."""
    return np.isfinite(p_w) & (p_w >= q) & np.isfinite(impulse_ret) & (impulse_ret != 0.0)


def moderate_band_mask(p_w: np.ndarray, impulse_ret: np.ndarray,
                        band: tuple[float, float] = MODERATE_BAND) -> np.ndarray:
    lo, hi = band
    return np.isfinite(p_w) & (p_w >= lo) & (p_w < hi) & np.isfinite(impulse_ret) & (impulse_ret != 0.0)


def direction_of(impulse_ret: np.ndarray) -> np.ndarray:
    out = np.zeros(len(impulse_ret), dtype=np.int8)
    out[impulse_ret > 0] = DIR_UP
    out[impulse_ret < 0] = DIR_DOWN
    return out


def decile_bin(p_w: np.ndarray) -> np.ndarray:
    """Fixed bins [0,10),...,[90,100] on a 0-100 midrank percentile scale.
    Returns bin index 0..9, or -1 where undefined."""
    out = np.full(len(p_w), -1, dtype=np.int8)
    valid = np.isfinite(p_w)
    pct = np.clip(p_w[valid] * 100.0, 0.0, 100.0)
    bin_idx = np.minimum((pct // 10).astype(np.int64), 9)
    out[valid] = bin_idx.astype(np.int8)
    return out


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
    """NORM_CONT_RET_H = CONT_RET_H / PAST_MEDIAN_ABS_RET_H(T). No floor: a
    zero/non-finite/unavailable denominator makes the outcome ineligible
    (returned as NaN), never repaired, never floored. Returns
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
    """The random pool excludes every RAW qualifying extreme timestamp for
    this (W,q) (before refractory dedup) but does NOT exclude surrounding
    hours/whole volatile regimes -- only the exact treated indices."""
    excluded = np.zeros(len(all_grid_idx), dtype=bool)
    excluded[raw_extreme_idx] = True
    return all_grid_idx[~excluded]


def sample_matched_random_once(
    rng: np.random.Generator, pool_by_month: dict, need_up_by_month: dict, need_down_by_month: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Draw ONE replicate WITHOUT REPLACEMENT from the already-excluded
    pool; assign each drawn observation the paired real candidate's
    direction label. `rng` is shared across all replicates of a cell so the
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
            raise H03Error(f"matched-random need={need} exceeds eligible pool {len(pool)} in {month}")
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
    """Fraction of shifted timestamps that land exactly on a raw true
    extreme-impulse timestamp for the same (W,q). Never removed -- reported
    only."""
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


def mpie_gate(mean_extreme: Optional[float], mean_matched: Optional[float], sign: int,
              mpie: float = MPIE) -> Optional[bool]:
    if mean_extreme is None or mean_matched is None:
        return None
    return (sign * (mean_extreme - mean_matched)) >= mpie


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
def symmetric_claim_verdict(up_supports_sign: Optional[bool], down_supports_sign: Optional[bool]) -> dict:
    """H03 is symmetric: a claim is only promotable if BOTH UP and DOWN
    support the same preregistered sign overall. One side alone rejects the
    symmetric claim and records the asymmetric observation as
    POSTHOC_UNTESTED; it can never promote H03 or enter Batch 01
    validation."""
    if up_supports_sign is True and down_supports_sign is True:
        return {"symmetric_claim": "SUPPORTED", "posthoc_untested": False}
    if up_supports_sign is True and down_supports_sign is False:
        return {"symmetric_claim": "REJECTED_SPECIFIC_CLAIM", "posthoc_untested": True,
                "asymmetric_side": "UP"}
    if down_supports_sign is True and up_supports_sign is False:
        return {"symmetric_claim": "REJECTED_SPECIFIC_CLAIM", "posthoc_untested": True,
                "asymmetric_side": "DOWN"}
    return {"symmetric_claim": "REJECTED_SPECIFIC_CLAIM", "posthoc_untested": False}


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
        "mean_norm_cont_ret": _mean(norm),
        "median_norm_cont_ret": _median(norm),
        "mean_cont_ret_bps": None if mean_bps is None else float(mean_bps * 10_000.0),
        "p_cont_ret_pos": _share_pos(cont_ret),
        "p_cont_ret_neg": _share_neg(cont_ret),
        "p05_norm_cont_ret": _pct(norm, 5),
        "p25_norm_cont_ret": _pct(norm, 25),
        "p75_norm_cont_ret": _pct(norm, 75),
        "p95_norm_cont_ret": _pct(norm, 95),
    }


def concentration_from_times(t_ms: np.ndarray, direction: Optional[np.ndarray] = None) -> dict:
    if t_ms.size == 0:
        return {
            "raw_n": 0, "unique_utc_days": 0, "unique_utc_weeks": 0, "unique_utc_months": 0,
            "by_year": {}, "by_month": {}, "largest_month_share": None, "top5_month_share": None,
            "up_share": None, "down_share": None, "median_spacing_minutes": None,
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
        "up_share": up_share,
        "down_share": down_share,
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

    impulse: dict = {}
    p_w: dict = {}
    direction: dict = {}
    decile: dict = {}
    for W in W_WINDOWS:
        imp = compute_impulse_returns(close, W)
        p = rolling_midrank_percentile(np.abs(imp), REF_STEPS)
        impulse[W] = imp
        p_w[W] = p
        direction[W] = direction_of(imp)
        decile[W] = decile_bin(p)

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
        "impulse": impulse, "p_w": p_w, "direction": direction, "decile": decile,
        "ret": ret, "scale": scale,
        "month_key": month, "week_key": week, "year": year, "dow_key": dow, "dom_key": dom,
        "t_max_inclusive": t_max,
        "long_dependence": long_dependence,
    }


def eligible_index(panel: dict, w_minutes: int, h_minutes: int) -> np.ndarray:
    return np.flatnonzero(
        panel["in_development"]
        & np.isfinite(panel["impulse"][w_minutes])
        & np.isfinite(panel["p_w"][w_minutes])
        & np.isfinite(panel["ret"][h_minutes])
        & np.isfinite(panel["scale"][h_minutes])
    )


def outcome_bundle(panel: dict, idx: np.ndarray, w_minutes: int, h_minutes: int) -> dict:
    direction = panel["direction"][w_minutes][idx].astype(np.int64)
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
    }


def matched_random_bundle(
    panel: dict, cand: dict, pool_idx: np.ndarray, h_minutes: int,
    seed: int = SEED_MATCHED, replicates: int = N_MATCHED,
) -> dict:
    """One frozen seed consumed exactly once across all `replicates` draws.
    Reports the across-replicate mean of the per-replicate mean
    NORM_CONT_RET_H and positive-share -- the matched-random control
    distribution, never treated as independent market evidence."""
    empty = {
        "N_replicates": replicates, "seed": seed,
        "mean_norm_cont_ret": None, "mean_p_cont_ret_pos": None,
        "residual_diagnostic": None,
    }
    if cand["idx"].size == 0 or pool_idx.size == 0:
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
            raise H03Error(f"matched-random n={need} exceeds eligible {pool_by_month[m].size} in {m}")

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
        last_dow_dist = categorical_counts([utc_dow_key(int(x)) for x in picked])
        last_dom_dist = categorical_counts([utc_dom_key(int(x)) for x in picked])

    arr = np.asarray(replicate_means, dtype=np.float64)
    parr = np.asarray(replicate_pos, dtype=np.float64)
    real_dow = categorical_counts(list(cand["dow"]))
    real_dom = categorical_counts(list(cand["dom"]))
    return {
        "N_replicates": replicates,
        "seed": seed,
        "mean_norm_cont_ret": float(np.nanmean(arr)) if np.any(np.isfinite(arr)) else None,
        "mean_p_cont_ret_pos": float(np.nanmean(parr)) if np.any(np.isfinite(parr)) else None,
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
        return {"N": 0, "mean_norm_cont_ret": None, "p_cont_ret_pos": None, "collision_fraction": coll}

    idx = np.asarray(shifted_idx, dtype=np.int64)
    direction = np.asarray(shifted_dir, dtype=np.int64)
    ret = panel["ret"][h_minutes][idx]
    scale = panel["scale"][h_minutes][idx]
    cont_ret = direction.astype(np.float64) * ret
    norm, elig = normalize(cont_ret, scale)
    return {
        "N": int(np.sum(elig)),
        "mean_norm_cont_ret": _mean(norm[elig]),
        "p_cont_ret_pos": _share_pos(cont_ret[elig]),
        "collision_fraction": coll,
    }


def year_breakdown(cand: dict) -> dict:
    out = {}
    for y in YEAR_BLOCKS:
        sl = cand["year"] == y
        n = int(np.sum(sl))
        out[str(y)] = {
            "N": n,
            "mean_norm_cont_ret": _mean(cand["norm"][sl]) if n else None,
            "p_cont_ret_pos": _share_pos(cand["cont_ret"][sl]) if n else None,
        }
    return out


def direction_breakdown(cand: dict) -> dict:
    out = {}
    for name, d in (("UP", DIR_UP), ("DOWN", DIR_DOWN)):
        sl = cand["direction"] == d
        out[name] = {
            "N": int(np.sum(sl)),
            "mean_norm_cont_ret": _mean(cand["norm"][sl]),
            "p_cont_ret_pos": _share_pos(cand["cont_ret"][sl]),
        }
    return out


def evaluate_cell(panel: dict, w_minutes: int, q: float, h_minutes: int) -> dict:
    t_arr = panel["t_ms"]
    raw_mask = extreme_candidate_mask(panel["p_w"][w_minutes], panel["impulse"][w_minutes], q) & panel["in_development"]
    raw_n = int(np.sum(raw_mask))
    kept = apply_refractory(t_arr, raw_mask)
    elig = eligible_index(panel, w_minutes, h_minutes)
    elig_set = np.zeros(len(t_arr), dtype=bool)
    elig_set[elig] = True

    cand_idx = np.flatnonzero(kept & elig_set)
    cand = outcome_bundle(panel, cand_idx, w_minutes, h_minutes)

    moderate_mask = moderate_band_mask(panel["p_w"][w_minutes], panel["impulse"][w_minutes]) & panel["in_development"]
    moderate_kept = apply_refractory(t_arr, moderate_mask)
    moderate_idx = np.flatnonzero(moderate_kept & elig_set)
    moderate = outcome_bundle(panel, moderate_idx, w_minutes, h_minutes)

    raw_extreme_in_elig = np.flatnonzero(raw_mask & elig_set)
    pool_idx = build_matched_random_pool(elig, raw_extreme_in_elig)
    matched = matched_random_bundle(panel, cand, pool_idx, h_minutes)

    shift = negative_control_bundle(panel, cand, raw_mask, h_minutes)

    metrics = metric_block(cand["cont_ret"], cand["norm"])
    moderate_metrics = metric_block(moderate["cont_ret"], moderate["norm"])

    mean_extreme = metrics["mean_norm_cont_ret"]
    mean_matched = matched["mean_norm_cont_ret"]
    mean_moderate = moderate_metrics["mean_norm_cont_ret"]
    mean_shifted = shift["mean_norm_cont_ret"]

    return {
        "W": w_minutes, "q": q, "H": h_minutes,
        **metrics,
        "raw_pre_refractory_N": raw_n,
        "post_refractory_N": int(np.sum(kept)),
        "reference_overlap": reference_overlap_disclosure(w_minutes, q),
        "n_eff_h": n_eff_h(h_minutes),
        "denominator_diagnostics": denominator_diagnostics(cand["scale"], cand["norm"]),
        "matched_random": matched,
        "moderate_structural_control": moderate_metrics,
        "negative_control": shift,
        "mpie_gate_continuation": mpie_gate(mean_extreme, mean_matched, DIR_UP),
        "mpie_gate_exhaustion": mpie_gate(mean_extreme, mean_matched, DIR_DOWN),
        "structural_gate_continuation": control_gate(mean_extreme, mean_moderate, DIR_UP),
        "structural_gate_exhaustion": control_gate(mean_extreme, mean_moderate, DIR_DOWN),
        "negative_control_gate_continuation": control_gate(mean_extreme, mean_shifted, DIR_UP),
        "negative_control_gate_exhaustion": control_gate(mean_extreme, mean_shifted, DIR_DOWN),
        "year_breakdown": year_breakdown(cand),
        "direction_breakdown": direction_breakdown(cand),
        "decile_diagnostic": decile_diagnostic_for_cell(panel, w_minutes, h_minutes, elig_set),
        "concentration": concentration_from_times(cand["t_ms"], cand["direction"]),
    }


def decile_diagnostic_for_cell(panel: dict, w_minutes: int, h_minutes: int, elig_set: np.ndarray) -> list:
    """Diagnostic only -- fixed 0-100 midrank-percentile decile bins for this
    (W, H) pair, using the SAME percentile convention as the primary
    extremeness classification. Never introduces a new threshold; cannot
    rescue or promote a cell."""
    bins = panel["decile"][w_minutes]
    ret_h = panel["ret"][h_minutes]
    scale_h = panel["scale"][h_minutes]
    out = []
    for b in range(10):
        sel = elig_set & (bins == b) & panel["in_development"]
        idx = np.flatnonzero(sel)
        label = f"[{b*10},{b*10+10})" if b < 9 else "[90,100]"
        if idx.size == 0:
            out.append({"bin": label, "N": 0, "mean_norm_cont_ret": None, "p_cont_ret_pos": None})
            continue
        direction = panel["direction"][w_minutes][idx]
        cont_ret = direction.astype(np.float64) * ret_h[idx]
        norm, elig = normalize(cont_ret, scale_h[idx])
        out.append({
            "bin": label,
            "N": int(np.sum(elig)),
            "mean_norm_cont_ret": _mean(norm[elig]),
            "p_cont_ret_pos": _share_pos(cont_ret[elig]),
        })
    return out


def evaluate_h03(panel: dict) -> dict:
    cells = []
    for W in W_WINDOWS:
        for q in Q_THRESHOLDS:
            for H in HORIZONS:
                cells.append(evaluate_cell(panel, W, q, H))
    forbidden_months = []
    for c in cells:
        for m in c["concentration"]["by_month"].keys():
            if m.startswith("2025") or m.startswith("2026"):
                forbidden_months.append(m)
    if forbidden_months:
        raise ValidationWindowForbidden(f"result months include forbidden windows: {forbidden_months}")
    return {
        "hypothesis_id": "H03_EXTREME_IMPULSE_CONTINUATION_EXHAUSTION",
        "dataset_id": DATASET_ID,
        "snapshot_id": REQUIRED_SNAPSHOT,
        "search_surface": {
            "impulse_windows": list(W_WINDOWS),
            "thresholds": list(Q_THRESHOLDS),
            "horizons": list(HORIZONS),
            "primary_threshold_cells": 45,
        },
        "long_dependence": panel["long_dependence"],
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
