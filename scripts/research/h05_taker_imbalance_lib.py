"""H05 taker-imbalance -> subsequent-return-distribution helpers.

Development-only. Refuses 2025/2026 1m canonical partitions and any outcome
window that reaches 2025-01-01. Does not reuse H01/H02/H03/H04 detectors or
definitions, and does not import any H01-H04 outcome-derived market
conclusion -- only implementation lessons (membership-safe pool exclusion,
real-timestamp calendar keys, candidate-weighted structural standardization,
1w/2w/4w dependence sensitivity wired in from the first commit) are carried
forward, per `docs/research/H05_TAKER_IMBALANCE_DESIGN.md` and
`docs/research/H05_TAKER_IMBALANCE_PREREG.md`.

This module intentionally does NOT execute against real accepted parquet as
part of preregistration/implementation freeze -- see
`docs/research/H05_TAKER_IMBALANCE_PREREG.md` and
`tests/research/test_h05_taker_imbalance.py`, which exercise every function
here with local synthetic fixtures only.

Design authority: this module encodes
`docs/research/H05_TAKER_IMBALANCE_DESIGN.md` @
`deaf6503896920685f25a03230174d360a07ab9a` (PR #82). It does not redesign
H05; any implementation ambiguity encountered while writing this module is
resolved and documented in
`docs/reviews/H05_PREREG_IMPLEMENTATION_AUDIT.md`, not silently chosen.
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
PREREG_JSON = REPO_ROOT / "docs" / "research" / "H05_TAKER_IMBALANCE_PREREG.json"
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
Q_THRESHOLDS = (0.80, 0.90, 0.95)
HORIZONS = (15, 30, 60, 120, 240)
YEAR_BLOCKS = (2020, 2021, 2022, 2023, 2024)
REFRACTORY_MS = 60 * BAR_MS
SHIFT_MS = 6 * 60 * BAR_MS
SEED_MATCHED = 20260904
SEED_BOOT = 20260905
N_MATCHED = 100
N_BOOT = 2000
DIR_BUY = 1
DIR_SELL = -1
ORDINARY_BAND = (0.60, 0.80)
MPIE = 0.10
CONTROL_DELTA_MIN = 0.05
DEP_LAGS_DAYS = (1, 2, 4, 8, 16, 32, 64)
DEP_ACF_THRESHOLD = 0.20
S_CONTINUATION = 1
S_REVERSAL = -1
SIGNS = {"continuation": S_CONTINUATION, "reversal": S_REVERSAL}


class H05Error(RuntimeError):
    pass


class ValidationWindowForbidden(H05Error):
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
        raise H05Error(f"unexpected dataset_id {data.get('dataset_id')}")
    snap = data.get("snapshot_id")
    if snap != REQUIRED_SNAPSHOT:
        raise H05Error(f"snapshot mismatch: {snap} != {REQUIRED_SNAPSHOT}")
    if data.get("status") != "ACCEPTED_FOR_DISCOVERY":
        raise H05Error(f"dataset not ACCEPTED_FOR_DISCOVERY: {data.get('status')}")
    if data.get("research_authorized") is not True:
        raise H05Error("research_authorized is not true")
    if data.get("confirmatory_authorized") is True:
        raise H05Error("confirmatory_authorized must remain false for H05")
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


def shift_plus_6h_same_utc_day(t_ms: int) -> int:
    day = t_ms - (t_ms % DAY_MS)
    return day + ((t_ms - day + SHIFT_MS) % DAY_MS)


def _forbid_partition_name(name: str) -> None:
    if name.startswith("2025-") or name.startswith("2026-"):
        raise ValidationWindowForbidden(
            f"refusing canonical partition {name} (2025/2026 forbidden in H05 development)"
        )


def list_development_parquet_paths(dataset_root: Path) -> list[Path]:
    """Enumerate ONLY 2020-2024 canonical 1m monthly partitions.

    Structurally rejects any partition whose filename year is >= 2025 --
    never opens the directory listing for 2025/2026 files and never relies
    on a later row filter to make forbidden-window access "safe"."""
    monthly = dataset_root / "canonical" / "1m" / "monthly"
    if not monthly.is_dir():
        raise H05Error(f"missing canonical 1m monthly dir: {monthly}")
    paths = []
    for p in sorted(monthly.glob("*.parquet")):
        year_prefix = p.name[:5]
        if year_prefix in ("2025-", "2026-"):
            continue
        year = int(p.name.split("-", 1)[0])
        if 2020 <= year <= 2024:
            paths.append(p)
    if not paths:
        raise H05Error("no 2020-2024 canonical monthly parquet found")
    return paths


def require_pyarrow() -> None:
    try:
        import pyarrow  # noqa: F401
    except ImportError as exc:
        raise H05Error("pyarrow is required; install requirements-research.txt") from exc


def load_development_1m(dataset_root: Path) -> dict:
    """Load 2020-2024 1m OHLC + base/taker-buy-base volume only. Never
    opens 2025/2026 parquet.

    Dedicated H05 development loader: it does not reuse any generic loader
    that scans all available dataset partitions and filters rows after the
    fact -- `list_development_parquet_paths` makes forbidden-window access
    structurally difficult by construction, not by a later row filter.

    Not exercised against real data in the preregistration/implementation
    -freeze task -- see module docstring."""
    require_pyarrow()
    import pyarrow.parquet as pq

    runtime_snap = dataset_root / "reports" / "snapshot_manifest.json"
    if runtime_snap.exists():
        snap = json.loads(runtime_snap.read_text(encoding="utf-8"))
        sid = snap.get("snapshot_id")
        if sid != REQUIRED_SNAPSHOT:
            raise H05Error(f"runtime snapshot_id {sid} != {REQUIRED_SNAPSHOT}")

    cols = ["open_time_ms", "available_at_ms", "close", "base_volume", "taker_buy_base_volume"]
    buckets = {c: [] for c in cols}
    for path in list_development_parquet_paths(dataset_root):
        _forbid_partition_name(path.name)
        table = pq.read_table(path, columns=cols)
        if "close_time_ms" in table.column_names:
            raise H05Error("close_time_ms must not be loaded")
        buckets["open_time_ms"].append(np.asarray(table.column("open_time_ms").to_pylist(), dtype=np.int64))
        buckets["available_at_ms"].append(np.asarray(table.column("available_at_ms").to_pylist(), dtype=np.int64))
        buckets["close"].append(np.array([parse_px(x) for x in table.column("close").to_pylist()], dtype=np.float64))
        buckets["base_volume"].append(np.array(table.column("base_volume").to_pylist(), dtype=np.float64))
        buckets["taker_buy_base_volume"].append(
            np.array(table.column("taker_buy_base_volume").to_pylist(), dtype=np.float64)
        )
    open_ms = np.concatenate(buckets["open_time_ms"])
    order = np.argsort(open_ms, kind="mergesort")
    frame = {
        "open_time_ms": open_ms[order],
        "available_at_ms": np.concatenate(buckets["available_at_ms"])[order],
        "close": np.concatenate(buckets["close"])[order],
        "base_volume": np.concatenate(buckets["base_volume"])[order],
        "taker_buy_base_volume": np.concatenate(buckets["taker_buy_base_volume"])[order],
    }
    if frame["open_time_ms"][0] < WARMUP_START_MS:
        raise H05Error("unexpected bars before warmup start")
    if int(frame["open_time_ms"][-1]) >= DEV_END_MS:
        raise ValidationWindowForbidden("loaded 1m bars reach 2025+")
    if np.any(frame["available_at_ms"] != frame["open_time_ms"] + BAR_MS):
        raise H05Error("available_at_ms is not open_time_ms + 60s")
    return frame


def aggregate_1m_to_15m(frame_1m: dict) -> dict:
    """T = bar_end_exclusive of the 15m bar [T-15m, T). close(T) is the
    close of the final canonical 1m bar whose own bar_end_exclusive == T.
    base_volume/taker_buy_base_volume are SUMMED over the 15 constituent
    1m bars (arithmetic aggregation, per
    `docs/manifests/CORE_BTC_BINANCE_V0.yaml` aggregation rules)."""
    o = frame_1m["open_time_ms"]
    n = len(o)
    if n == 0 or n % HTF_MIN != 0:
        raise H05Error(f"1m length {n} is not a multiple of {HTF_MIN}")
    if int(o[0]) % HTF_MS != 0:
        raise H05Error("1m series does not start on a 15m UTC boundary")
    expected = o[0] + np.arange(n, dtype=np.int64) * BAR_MS
    if np.any(o != expected):
        raise H05Error("1m open_time_ms is not a contiguous 1m grid")
    n15 = n // HTF_MIN
    open_ms = o[::HTF_MIN]
    avail = open_ms + HTF_MS
    last_1m_avail = frame_1m["available_at_ms"][HTF_MIN - 1::HTF_MIN]
    if np.any(last_1m_avail != avail):
        raise H05Error("15m available_at is not last 1m available_at in the bucket")
    base_volume = frame_1m["base_volume"].reshape(n15, HTF_MIN).sum(axis=1)
    taker_buy_base_volume = frame_1m["taker_buy_base_volume"].reshape(n15, HTF_MIN).sum(axis=1)
    frame = {
        "open_time_ms": open_ms,
        "available_at_ms": avail,
        "t_ms": avail,  # decision T = bar_end_exclusive
        "close": frame_1m["close"][HTF_MIN - 1::HTF_MIN],
        "base_volume": base_volume,
        "taker_buy_base_volume": taker_buy_base_volume,
        "taker_sell_base_volume": base_volume - taker_buy_base_volume,
    }
    if np.any(frame["available_at_ms"] != frame["open_time_ms"] + HTF_MS):
        raise H05Error("15m available_at_ms is not open_time_ms + 900s")
    return frame


# ---------------------------------------------------------------------------
# percentile machinery (shared, H01/H03/H04-compatible midrank convention)
# ---------------------------------------------------------------------------
def rolling_midrank_percentile(values: np.ndarray, window: int) -> np.ndarray:
    """For index i, returns the midrank percentile of values[i] within the
    strictly-prior window values[i-window:i] (current i excluded, no future
    observations).

        P(T) = (count(ref < x) + 0.5 * count(ref == x)) / N_ref

    Correct-but-not-optimized for this preregistration/implementation
    -freeze task's synthetic fixtures; no real-data run is performed here."""
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


# ---------------------------------------------------------------------------
# primary flow feature (TAKER_IMBALANCE_W) and price/activity confounds
# ---------------------------------------------------------------------------
def _rolling_sum_w_bars(values: np.ndarray, w_bars: int) -> np.ndarray:
    """Trailing sum over the w_bars bars ending at (and including) index i --
    i.e. sum over [T-W, T) where bar i itself is [T-15m, T). NaN until
    w_bars bars are available."""
    s = pd.Series(values, copy=False).rolling(w_bars, min_periods=w_bars).sum()
    return s.to_numpy(dtype=np.float64)


def compute_taker_imbalance(frame15: dict, w_minutes: int) -> dict:
    """BUY_W = sum(taker_buy_base_volume), SELL_W = sum(base_volume -
    taker_buy_base_volume), TOTAL_W = BUY_W + SELL_W == sum(base_volume),
    over the trailing w_bars bars [T-W, T).

    TAKER_IMBALANCE_W = (BUY_W - SELL_W) / TOTAL_W = 2*BUY_W/TOTAL_W - 1.

    TOTAL_W == 0 or non-finite is explicit ineligibility (imbalance -> NaN,
    D -> 0), never coerced to 0 and never silently dropped without being
    counted (see `ineligible_total_w_n` in the returned dict)."""
    if w_minutes % HTF_MIN != 0:
        raise H05Error(f"W={w_minutes} is not a multiple of the {HTF_MIN}m grid")
    w_bars = w_minutes // HTF_MIN
    buy_w = _rolling_sum_w_bars(frame15["taker_buy_base_volume"], w_bars)
    sell_w = _rolling_sum_w_bars(frame15["taker_sell_base_volume"], w_bars)
    total_w = buy_w + sell_w
    total_ok = np.isfinite(total_w) & (total_w != 0.0)
    ineligible_total_w_n = int(np.sum(np.isfinite(buy_w) & ~total_ok))
    with np.errstate(divide="ignore", invalid="ignore"):
        imbalance = np.where(total_ok, (buy_w - sell_w) / np.where(total_ok, total_w, 1.0), np.nan)
    d = np.zeros(len(imbalance), dtype=np.int8)
    finite = np.isfinite(imbalance)
    d[finite & (imbalance > 0)] = DIR_BUY
    d[finite & (imbalance < 0)] = DIR_SELL
    # imbalance == 0 exactly (a tie) leaves d == 0, excluded from candidacy.
    abs_imbalance = np.abs(imbalance)
    return {
        "buy_w": buy_w, "sell_w": sell_w, "total_w": total_w,
        "imbalance": imbalance, "abs_imbalance": abs_imbalance, "D": d,
        "ineligible_total_w_n": ineligible_total_w_n,
    }


def compute_price_ret(close: np.ndarray, w_minutes: int) -> np.ndarray:
    """PRICE_RET_W(T) = ln(close(T) / close(T-W))."""
    w_bars = w_minutes // HTF_MIN
    n = len(close)
    out = np.full(n, np.nan, dtype=np.float64)
    if n <= w_bars:
        return out
    c0 = close[w_bars:]
    c1 = close[:-w_bars]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.log(c0 / c1)
    out[w_bars:] = r
    return out


def price_alignment_index(d: np.ndarray, price_ret_w: np.ndarray) -> np.ndarray:
    """price_alignment: 1 = ALIGNED (SIGNED_PRICE_RET_W > 0), 0 = OPPOSED
    (SIGNED_PRICE_RET_W <= 0, including exact zero -- frozen, deterministic,
    decided pre-outcome; see design doc section 9). -1 where d==0 or
    price_ret_w is non-finite (not a candidate anyway)."""
    n = len(d)
    out = np.full(n, -1, dtype=np.int8)
    valid = (d != 0) & np.isfinite(price_ret_w)
    signed = d[valid].astype(np.float64) * price_ret_w[valid]
    out[valid] = np.where(signed > 0.0, 1, 0)
    return out


def bin_index_at_median(pctl: np.ndarray) -> np.ndarray:
    """0 = LOWER (pctl < 0.50), 1 = UPPER (pctl >= 0.50). -1 if pctl is
    non-finite. Used identically for price_strength_bin and activity_bin --
    same causal trailing-30d midrank percentile machinery, applied to a
    different underlying series."""
    out = np.full(len(pctl), -1, dtype=np.int8)
    valid = np.isfinite(pctl)
    out[valid] = np.where(pctl[valid] < 0.50, 0, 1)
    return out


# ---------------------------------------------------------------------------
# candidate / ordinary-control masks
# ---------------------------------------------------------------------------
def candidate_mask(d: np.ndarray, abs_imbalance_pctl: np.ndarray, q: float, in_development: np.ndarray) -> np.ndarray:
    """ABS_IMBALANCE_PCTL_W(T) >= q AND D != 0 AND in development. Nested:
    membership at q also satisfies membership at every looser q' < q."""
    return (d != 0) & np.isfinite(abs_imbalance_pctl) & (abs_imbalance_pctl >= q) & in_development


def ordinary_control_mask(d: np.ndarray, abs_imbalance_pctl: np.ndarray, in_development: np.ndarray) -> np.ndarray:
    """Fixed band 0.60 <= ABS_IMBALANCE_PCTL_W < 0.80, decoupled from
    whichever q is under evaluation -- reused verbatim across all three q
    cells for a given W (design doc section 9)."""
    lo, hi = ORDINARY_BAND
    return (
        (d != 0) & np.isfinite(abs_imbalance_pctl)
        & (abs_imbalance_pctl >= lo) & (abs_imbalance_pctl < hi) & in_development
    )


# ---------------------------------------------------------------------------
# refractory
# ---------------------------------------------------------------------------
def apply_refractory(t_ms: np.ndarray, mask: np.ndarray, refractory_ms: int = REFRACTORY_MS) -> np.ndarray:
    """Either-direction, 60-minute refractory: keep the earliest qualifying
    timestamp, suppress subsequent qualifiers of either direction inside
    the window. No direction-aware exception."""
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
    """RAW_FUTURE_RETURN(T,H) = ln(close(T+H)/close(T)). Eligible only if
    T+H resolves strictly before dev_end_ms -- no truncation, ineligible
    rows are NaN."""
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
    """Median of values[i-window : i-known_lag_steps+1] -- only reference
    observations whose own H-horizon outcome is fully resolved strictly
    before T. Current/future observations excluded."""
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


def normalize(signed_ret: np.ndarray, scale: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """X = NORM_TAKER_RET_H = signed_ret / trailing_30d_median_abs_H_return.
    No floor: a zero/non-finite/unavailable denominator makes the outcome
    ineligible (NaN), never repaired, never floored."""
    denom_ok = np.isfinite(scale) & (scale > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        norm = signed_ret / scale
    eligible = denom_ok & np.isfinite(signed_ret) & np.isfinite(norm)
    norm = np.where(eligible, norm, np.nan)
    return norm, eligible


# ---------------------------------------------------------------------------
# matched-random baseline
# ---------------------------------------------------------------------------
def build_matched_random_pool(all_grid_idx: np.ndarray, raw_extreme_idx: np.ndarray) -> np.ndarray:
    """Membership-based (np.isin) exclusion of every RAW qualifying H05
    candidate timestamp for this (W, q) from the matched-random pool --
    NOT positional/fancy-indexing exclusion. Direct carry-forward of the
    H03 post-freeze audit lesson; this bug class must not recur."""
    excluded = np.isin(all_grid_idx, raw_extreme_idx)
    return all_grid_idx[~excluded]


def sample_matched_random_once(
    rng: np.random.Generator, pool_by_month: dict, need_buy_by_month: dict, need_sell_by_month: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Draw ONE replicate WITHOUT REPLACEMENT from the already-excluded
    pool; assign each drawn observation the paired real candidate's flow
    direction D. `rng` is shared across all replicates of a cell so the
    frozen seed is consumed exactly once per cell, not re-seeded per
    replicate."""
    idx_out = []
    dir_out = []
    for month, pool in pool_by_month.items():
        n_buy = need_buy_by_month.get(month, 0)
        n_sell = need_sell_by_month.get(month, 0)
        need = n_buy + n_sell
        if need == 0:
            continue
        if need > len(pool):
            raise H05Error(f"matched-random need={need} exceeds eligible pool {len(pool)} in {month}")
        picked = rng.choice(pool, size=need, replace=False)
        labels = np.empty(need, dtype=np.int8)
        labels[:n_buy] = DIR_BUY
        labels[n_buy:] = DIR_SELL
        rng.shuffle(labels)
        idx_out.append(picked)
        dir_out.append(labels)
    if not idx_out:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int8)
    return np.concatenate(idx_out), np.concatenate(dir_out)


# ---------------------------------------------------------------------------
# negative control
# ---------------------------------------------------------------------------
def collision_fraction(shifted_t_ms: np.ndarray, raw_extreme_t_ms: np.ndarray) -> float:
    """Fraction of shifted timestamps that land exactly on a raw true H05
    candidate timestamp for the same (W, q). Never removed -- reported
    only."""
    if shifted_t_ms.size == 0:
        return 0.0
    raw_set = set(int(x) for x in raw_extreme_t_ms)
    hits = sum(1 for t in shifted_t_ms if int(t) in raw_set)
    return float(hits) / float(shifted_t_ms.size)


# ---------------------------------------------------------------------------
# claim-orientation formalism (S) -- design doc section 2
# ---------------------------------------------------------------------------
def oriented_primary(candidate_mean: Optional[float], sign: int) -> Optional[float]:
    if candidate_mean is None:
        return None
    return sign * candidate_mean


def oriented_delta(candidate_mean: Optional[float], reference_mean: Optional[float], sign: int) -> Optional[float]:
    if candidate_mean is None or reference_mean is None:
        return None
    return sign * (candidate_mean - reference_mean)


def gate_primary(candidate_mean: Optional[float], sign: int) -> Optional[bool]:
    v = oriented_primary(candidate_mean, sign)
    return None if v is None else v > 0


def gate_matched_mpie(candidate_mean: Optional[float], matched_mean: Optional[float], sign: int,
                       mpie: float = MPIE) -> Optional[bool]:
    v = oriented_delta(candidate_mean, matched_mean, sign)
    return None if v is None else v >= mpie


def gate_control_delta(candidate_mean: Optional[float], reference_mean: Optional[float], sign: int,
                        delta_min: float = CONTROL_DELTA_MIN) -> Optional[bool]:
    v = oriented_delta(candidate_mean, reference_mean, sign)
    return None if v is None else v >= delta_min


def oriented_from_delta(delta: Optional[float], sign: int) -> Optional[float]:
    """S * delta, for a delta that is already computed on matched support
    (e.g. the structural comparison's own like-with-like
    `candidate_overlap_standardized_mean - structural_control_standardized
    _mean`) -- distinct from `oriented_delta`, which computes `candidate -
    reference` from two independent means that may not share support."""
    return None if delta is None else sign * delta


def gate_from_delta(delta: Optional[float], sign: int, threshold: float = CONTROL_DELTA_MIN) -> Optional[bool]:
    v = oriented_from_delta(delta, sign)
    return None if v is None else v >= threshold


def claim_evaluation(candidate_mean: Optional[float], matched_mean: Optional[float],
                      structural_delta: Optional[float], shifted_mean: Optional[float], sign: int) -> dict:
    """All four mandatory gates for one claim orientation.

    `candidate_mean` is the SAME quantity (the FULL, unrestricted
    candidate-population mean of X) used for the primary, matched, and
    shift gates -- it is never restricted/re-standardized for those.

    `structural_delta`, by contrast, is NOT a mean to be differenced here:
    it is the already-computed, like-with-like structural comparison
    (`candidate_overlap_standardized_mean -
    structural_control_standardized_mean`, both sides restricted to, and
    weighted over, exactly the same overlap strata -- see
    `structural_control_bundle`). This is the pre-outcome structural
    -support correction: comparing the FULL candidate mean against a
    control mean standardized only over overlap strata would compare
    quantities on different support, letting unmatched-candidate-stratum
    outcomes move the gate without any corresponding control observation.
    See design doc section 9 and section 17."""
    return {
        "S": sign,
        "ORIENTED_PRIMARY": oriented_primary(candidate_mean, sign),
        "ORIENTED_MATCHED_DELTA": oriented_delta(candidate_mean, matched_mean, sign),
        "ORIENTED_STRUCTURAL_DELTA": oriented_from_delta(structural_delta, sign),
        "ORIENTED_SHIFT_DELTA": oriented_delta(candidate_mean, shifted_mean, sign),
        "primary_gate": gate_primary(candidate_mean, sign),
        "mpie_gate": gate_matched_mpie(candidate_mean, matched_mean, sign),
        "structural_gate": gate_from_delta(structural_delta, sign),
        "shift_gate": gate_control_delta(candidate_mean, shifted_mean, sign),
    }


# ---------------------------------------------------------------------------
# dependence diagnostics
# ---------------------------------------------------------------------------
def daily_indicator_series(t_ms: np.ndarray, indicator_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Daily count of a boolean indicator (e.g. kept candidates) over the
    full `t_ms` domain -- candidate-count series, NOT outcome returns.
    Days with zero qualifying candidates are included with count 0 (a
    proper zero-filled daily series, not a sparse one)."""
    days = np.array([utc_day_key(int(x)) for x in t_ms])
    df = pd.DataFrame({"day": days, "hit": indicator_mask.astype(np.float64)})
    daily = df.groupby("day", sort=True)["hit"].sum()
    return daily.index.to_numpy(), daily.to_numpy(dtype=np.float64)


def autocorrelation_at_lag(series: np.ndarray, lag: int) -> float:
    if lag <= 0 or lag >= len(series) or len(series) < 3:
        return float("nan")
    s = pd.Series(series)
    return float(s.autocorr(lag=lag))


def candidate_clustering_diagnostic(t_ms: np.ndarray, kept_mask: np.ndarray,
                                     lags_days: tuple[int, ...] = DEP_LAGS_DAYS,
                                     threshold: float = DEP_ACF_THRESHOLD) -> dict:
    """OUTCOME-INDEPENDENT, CELL-SPECIFIC CANDIDATE-CLUSTERING DIAGNOSTIC.

    Input: the post-refractory candidate indicator series for this (W, q)
    cell (never outcome/return values). L_dep = the LARGEST lag in
    `lags_days` at which |ACF| >= threshold -- not the first crossing, so
    a non-monotone ACF that dips below threshold early and rises again
    later is not misreported as short dependence. Diagnostic only; never
    gates promotion."""
    _, daily = daily_indicator_series(t_ms, kept_mask)
    acf_by_lag = {lag: autocorrelation_at_lag(daily, lag) for lag in lags_days}
    qualifying = [lag for lag, v in acf_by_lag.items() if np.isfinite(v) and abs(v) >= threshold]
    l_dep = max(qualifying) if qualifying else None
    return {"acf_by_lag_days": acf_by_lag, "l_dep_days": l_dep}


def week_block_bootstrap(week_keys: np.ndarray, norm: np.ndarray,
                          seed: int = SEED_BOOT, replicates: int = N_BOOT) -> dict:
    """UTC-week block bootstrap applied to the candidate primary mean X
    (NORM_TAKER_RET_H) -- never the matched/structural/shift deltas, which
    remain distinct estimands (design doc section 21/22 item 12)."""
    empty = {"seed": seed, "replicates": replicates, "norm_mean": None, "norm_p025": None, "norm_p975": None}
    unique_weeks = np.unique(week_keys) if week_keys.size else np.array([])
    if unique_weeks.size == 0:
        return empty
    idx_by_week = {w: np.flatnonzero(week_keys == w) for w in unique_weeks}
    n_weeks = unique_weeks.size
    rng = np.random.default_rng(seed)
    rep_norm = np.full(replicates, np.nan, dtype=np.float64)
    for r in range(replicates):
        chosen = rng.choice(unique_weeks, size=n_weeks, replace=True)
        rows = np.concatenate([idx_by_week[w] for w in chosen])
        nv = norm[rows]
        nv = nv[np.isfinite(nv)]
        if nv.size:
            rep_norm[r] = float(np.mean(nv))
    vn = rep_norm[np.isfinite(rep_norm)]
    return {
        "seed": seed, "replicates": replicates,
        "norm_mean": float(np.mean(vn)) if vn.size else None,
        "norm_p025": float(np.percentile(vn, 2.5)) if vn.size else None,
        "norm_p975": float(np.percentile(vn, 97.5)) if vn.size else None,
    }


DEPENDENCE_SENSITIVITY_BLOCK_SIZES_WEEKS = (1, 2, 4)


def _block_groups_for_size(sorted_unique_weeks: list, block_size_weeks: int) -> list:
    """Deterministically partition chronologically ordered UTC-week keys
    into consecutive, non-overlapping groups of `block_size_weeks` weeks
    each, starting from the earliest week present (never chosen from
    outcomes). A final incomplete group is retained as one shorter
    terminal block rather than discarded."""
    return [
        sorted_unique_weeks[i:i + block_size_weeks]
        for i in range(0, len(sorted_unique_weeks), block_size_weeks)
    ]


def block_bootstrap_sensitivity(week_keys: np.ndarray, norm: np.ndarray, block_size_weeks: int,
                                 seed: int = SEED_BOOT, replicates: int = N_BOOT) -> dict:
    """Deterministic fixed block-size bootstrap on the candidate primary
    outcome mean X -- never a different metric, never MPIE/control values.

    Seed derivation (deterministic, never outcome-dependent, never
    re-rolled): `block_size_weeks == 1` uses the frozen master seed
    directly (`np.random.default_rng(seed)`) -- required so the 1-week
    sensitivity numerically agrees with `week_block_bootstrap` under the
    same seed and single-week block construction. `block_size_weeks in
    {2, 4}` derives an independent, deterministic child stream via
    `np.random.SeedSequence([seed, block_size_weeks])`."""
    empty = {
        "block_size_weeks": block_size_weeks, "observed_blocks_N": 0, "replicates": replicates,
        "seed": seed if block_size_weeks == 1 else f"SeedSequence([{seed}, {block_size_weeks}])",
        "norm_mean": None, "norm_p025": None, "norm_p50": None, "norm_p975": None,
    }
    if week_keys.size == 0:
        return empty
    unique_weeks = sorted(np.unique(week_keys).tolist())
    idx_by_week = {w: np.flatnonzero(week_keys == w) for w in unique_weeks}
    groups = _block_groups_for_size(unique_weeks, block_size_weeks)
    n_blocks = len(groups)
    if n_blocks == 0:
        return empty
    group_indices = [np.concatenate([idx_by_week[w] for w in g]) for g in groups]

    if block_size_weeks == 1:
        rng = np.random.default_rng(seed)
    else:
        rng = np.random.default_rng(np.random.SeedSequence([seed, block_size_weeks]))

    rep_norm = np.full(replicates, np.nan, dtype=np.float64)
    for r in range(replicates):
        chosen = rng.integers(0, n_blocks, size=n_blocks)
        rows = np.concatenate([group_indices[c] for c in chosen])
        nv = norm[rows]
        nv = nv[np.isfinite(nv)]
        if nv.size:
            rep_norm[r] = float(np.mean(nv))

    vn = rep_norm[np.isfinite(rep_norm)]
    if vn.size == 0:
        norm_mean = norm_p025 = norm_p50 = norm_p975 = None
    else:
        norm_mean = float(np.mean(vn))
        norm_p025 = float(np.percentile(vn, 2.5))
        norm_p50 = float(np.percentile(vn, 50))
        norm_p975 = float(np.percentile(vn, 97.5))
    return {
        "block_size_weeks": block_size_weeks, "observed_blocks_N": n_blocks, "replicates": replicates,
        "seed": seed if block_size_weeks == 1 else f"SeedSequence([{seed}, {block_size_weeks}])",
        "norm_mean": norm_mean, "norm_p025": norm_p025, "norm_p50": norm_p50, "norm_p975": norm_p975,
    }


def dependence_sensitivity_bundle(week_keys: np.ndarray, norm: np.ndarray,
                                   seed: int = SEED_BOOT, replicates: int = N_BOOT) -> dict:
    """Fixed, predeclared, non-selectable 1w/2w/4w block-sensitivity,
    computed unconditionally for every cell from the first implementation
    commit (design doc section 21)."""
    return {
        f"{size}w": block_bootstrap_sensitivity(week_keys, norm, size, seed=seed, replicates=replicates)
        for size in DEPENDENCE_SENSITIVITY_BLOCK_SIZES_WEEKS
    }


def bootstrap_sign_gate(dep_sensitivity: dict, sign: int) -> dict:
    """`p025 > 0` at 1w/2w/4w for CONTINUATION (sign=+1); `p975 < 0` at
    1w/2w/4w for REVERSAL (sign=-1). Kept as the pre-existing sign-specific
    rule (design doc section 22 item 12) -- not re-expressed via oriented
    quantities, since it is already sign-specific by construction."""
    out = {}
    all_pass = True
    for size in DEPENDENCE_SENSITIVITY_BLOCK_SIZES_WEEKS:
        block = dep_sensitivity[f"{size}w"]
        if sign == S_CONTINUATION:
            p025 = block["norm_p025"]
            passed = None if p025 is None else p025 > 0
        else:
            p975 = block["norm_p975"]
            passed = None if p975 is None else p975 < 0
        out[f"{size}w"] = passed
        if passed is not True:
            all_pass = False
    out["all_block_sizes_pass"] = all_pass
    return out


# ---------------------------------------------------------------------------
# adjacency / robustness helpers
# ---------------------------------------------------------------------------
def has_adjacent_pair_support(ordered_keys: tuple, support: dict) -> bool:
    """True iff at least one pair of ADJACENT keys (in ordered_keys) both
    map to True in `support`. Used for the two-adjacent-q and two-adjacent
    -horizon promotion requirements."""
    for a, b in zip(ordered_keys[:-1], ordered_keys[1:]):
        if support.get(a) is True and support.get(b) is True:
            return True
    return False


def has_adjacent_w_directional_support(ordered_w: tuple, w_index: int, directional_ok: dict) -> bool:
    """True iff at least one W ADJACENT to `ordered_w[w_index]` has
    directional_ok[True] (ORIENTED_PRIMARY>0 AND ORIENTED_MATCHED_DELTA>0
    AND ORIENTED_STRUCTURAL_DELTA>0), without requiring the full numeric
    MPIE/CONTROL_DELTA_MIN gates. A fully isolated W (no adjacent support
    either side) returns False."""
    neighbors = []
    if w_index > 0:
        neighbors.append(ordered_w[w_index - 1])
    if w_index < len(ordered_w) - 1:
        neighbors.append(ordered_w[w_index + 1])
    return any(directional_ok.get(w) is True for w in neighbors)


def directional_support(candidate_mean: Optional[float], matched_mean: Optional[float],
                         structural_delta: Optional[float], sign: int) -> Optional[bool]:
    """ORIENTED_PRIMARY>0 AND ORIENTED_MATCHED_DELTA>0 AND
    ORIENTED_STRUCTURAL_DELTA>0 (direction only, not full gate magnitude).
    `structural_delta` is the already like-with-like overlap comparison
    (`candidate_overlap_standardized_mean -
    structural_control_standardized_mean`), consistent with the
    pre-outcome structural-support correction -- not `candidate_mean`
    differenced against a control mean of different support."""
    p = oriented_primary(candidate_mean, sign)
    m = oriented_delta(candidate_mean, matched_mean, sign)
    s = oriented_from_delta(structural_delta, sign)
    if p is None or m is None or s is None:
        return None
    return (p > 0) and (m > 0) and (s > 0)


def year_stability_gate(yearly_means: dict, sign: int, min_years: int = 4, of_years: int = 5) -> Optional[bool]:
    """S * yearly_candidate_primary_mean(y) > 0 in at least min_years of
    of_years. No shock-year exclusion path exists in this function -- every
    year in `yearly_means` is used, unconditionally."""
    if len(yearly_means) < of_years:
        return None
    n_support = 0
    for y, m in yearly_means.items():
        if m is None:
            continue
        if sign * m > 0:
            n_support += 1
    return n_support >= min_years


def direction_symmetry_gate(buy_mean: Optional[float], sell_mean: Optional[float], sign: int) -> Optional[bool]:
    """Both D=+1 and D=-1 must independently satisfy ORIENTED_PRIMARY > 0
    for the same sign."""
    buy_ok = gate_primary(buy_mean, sign)
    sell_ok = gate_primary(sell_mean, sign)
    if buy_ok is None or sell_ok is None:
        return None
    return buy_ok and sell_ok


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


def categorical_counts(keys: list[str]) -> dict:
    out: dict = {}
    for k in keys:
        out[k] = out.get(k, 0) + 1
    return out


def metric_block(raw_ret: np.ndarray, norm: np.ndarray) -> dict:
    n = int(np.sum(np.isfinite(norm)))
    mean_bps = _mean(raw_ret)
    median_bps = _median(raw_ret)
    return {
        "N": n,
        "candidate_mean": _mean(norm),
        "candidate_median": _median(norm),
        "raw_mean_bps": None if mean_bps is None else float(mean_bps * 10_000.0),
        "raw_median_bps": None if median_bps is None else float(median_bps * 10_000.0),
        "P_X_pos": _share_pos(norm),
        "p05": _pct(norm, 5), "p25": _pct(norm, 25), "p75": _pct(norm, 75), "p95": _pct(norm, 95),
    }


def concentration_from_times(t_ms: np.ndarray, direction: Optional[np.ndarray], norm: Optional[np.ndarray]) -> dict:
    if t_ms.size == 0:
        return {
            "raw_n": 0, "unique_utc_days": 0, "unique_utc_weeks": 0, "unique_utc_months": 0,
            "by_year": {}, "by_month": {}, "largest_month_share": None, "top5_month_share": None,
            "buy_share": None, "sell_share": None, "median_spacing_minutes": None,
            "largest_candidate_contribution_share": None, "top_decile_contribution_share": None,
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
    buy_share = sell_share = None
    if direction is not None and direction.size:
        buy_share = float(np.mean(direction == DIR_BUY))
        sell_share = float(np.mean(direction == DIR_SELL))
    largest_contrib = top_decile_contrib = None
    if norm is not None:
        abs_norm = np.abs(norm[np.isfinite(norm)])
        total = float(np.sum(abs_norm))
        if total > 0:
            largest_contrib = float(np.max(abs_norm) / total)
            k = max(1, int(np.ceil(0.10 * abs_norm.size)))
            top_k = np.sort(abs_norm)[-k:]
            top_decile_contrib = float(np.sum(top_k) / total)
    return {
        "raw_n": n,
        "unique_utc_days": len(days), "unique_utc_weeks": len(weeks), "unique_utc_months": len(month_counts),
        "by_year": year_counts, "by_month": dict(ordered),
        "largest_month_share": float(ordered[0][1] / n), "top5_month_share": float(sum(c for _, c in ordered[:5]) / n),
        "buy_share": buy_share, "sell_share": sell_share, "median_spacing_minutes": spacing,
        "largest_candidate_contribution_share": largest_contrib,
        "top_decile_contribution_share": top_decile_contrib,
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
    t_max = development_t_max_ms()
    in_dev = (t >= DEV_START_MS) & (t <= t_max)

    feat: dict = {}
    price_ret: dict = {}
    price_alignment: dict = {}
    price_strength_bin: dict = {}
    activity_bin: dict = {}
    for w in W_WINDOWS:
        f = compute_taker_imbalance(frame15, w)
        f["abs_imbalance_pctl"] = rolling_midrank_percentile(f["abs_imbalance"], REF_STEPS)
        feat[w] = f
        pr = compute_price_ret(close, w)
        price_ret[w] = pr
        pr_pctl = rolling_midrank_percentile(np.abs(pr), REF_STEPS)
        price_strength_bin[w] = bin_index_at_median(pr_pctl)
        price_alignment[w] = price_alignment_index(f["D"], pr)
        act_pctl = rolling_midrank_percentile(f["total_w"], REF_STEPS)
        activity_bin[w] = bin_index_at_median(act_pctl)

    ret: dict = {}
    scale: dict = {}
    for h in HORIZONS:
        h_bars = h // HTF_MIN
        r = compute_horizon_return(close, t, h)
        ret[h] = r
        sc = trailing_median_known(np.abs(r), REF_STEPS, h_bars)
        scale[h] = np.where(sc > 0, sc, np.nan)

    month = np.array([utc_month_key(int(x)) for x in t])
    week = np.array([utc_week_key(int(x)) for x in t])
    year = np.array([utc_year(int(x)) for x in t], dtype=np.int16)

    return {
        "t_ms": t, "close": close, "in_development": in_dev,
        "feat": feat, "price_ret": price_ret,
        "price_alignment": price_alignment, "price_strength_bin": price_strength_bin, "activity_bin": activity_bin,
        "ret": ret, "scale": scale,
        "month_key": month, "week_key": week, "year": year,
        "t_max_inclusive": t_max,
    }


def eligible_index(panel: dict, w_minutes: int, h_minutes: int) -> np.ndarray:
    f = panel["feat"][w_minutes]
    return np.flatnonzero(
        panel["in_development"]
        & (f["D"] != 0)
        & np.isfinite(f["abs_imbalance_pctl"])
        & np.isfinite(panel["ret"][h_minutes])
        & np.isfinite(panel["scale"][h_minutes])
    )


def outcome_bundle(panel: dict, idx: np.ndarray, w_minutes: int, h_minutes: int) -> dict:
    f = panel["feat"][w_minutes]
    direction = f["D"][idx].astype(np.int64)
    ret = panel["ret"][h_minutes][idx]
    scale = panel["scale"][h_minutes][idx]
    raw_ret = direction.astype(np.float64) * ret
    norm, elig = normalize(raw_ret, scale)
    idx = idx[elig]
    direction = direction[elig]
    raw_ret = raw_ret[elig]
    norm = norm[elig]
    t = panel["t_ms"][idx]
    return {
        "idx": idx, "t_ms": t, "direction": direction, "raw_ret": raw_ret, "norm": norm,
        "month": panel["month_key"][idx], "week": panel["week_key"][idx], "year": panel["year"][idx],
        "price_alignment": panel["price_alignment"][w_minutes][idx],
        "price_strength_bin": panel["price_strength_bin"][w_minutes][idx],
        "activity_bin": panel["activity_bin"][w_minutes][idx],
    }


def structural_control_bundle(panel: dict, cand: dict, cand_mean: Optional[float],
                               w_minutes: int, h_minutes: int, elig_set: np.ndarray) -> dict:
    """Fixed ordinary-flow band [0.60, 0.80), decoupled from the q under
    test. Candidate-weighted deterministic standardization over the FULL
    five-dimensional stratification (calendar_month, D, price_alignment,
    price_strength_bin, activity_bin) -- design doc section 9.

    PRE-OUTCOME STRUCTURAL-SUPPORT CORRECTION (this revision, supersedes
    `H05_PREREG_SHA_V1` = `9502006eb4797a9947c61d8d04acd1345ed41e5e`): an
    independent pre-outcome audit found that comparing the FULL candidate
    -population mean (`cand_mean`, unrestricted) against a control mean
    standardized only over overlap strata compares quantities on
    different support -- if unmatched candidate strata have
    systematically different outcomes, they could move the full candidate
    mean while having no corresponding structural-control observation at
    all, letting a structural gate pass or fail on composition the
    control never actually saw. The structural comparison must be
    LIKE-WITH-LIKE: both `candidate_overlap_standardized_mean` and
    `structural_control_standardized_mean` are now computed over exactly
    the same overlap strata, with exactly the same candidate-frequency
    weights `w_s`. `structural_delta =
    candidate_overlap_standardized_mean - structural_control_standardized
    _mean` is the quantity every `ORIENTED_STRUCTURAL_DELTA` gate now
    uses -- **not** the full unrestricted candidate mean. The full
    candidate-population mean (`cand_mean`, passed in) is reported here
    only as `full_candidate_mean`, for transparency/contrast; it is not
    used in this bundle's own delta. It continues to be used, unchanged,
    for every OTHER oriented quantity (primary, matched, shift, bootstrap,
    year stability, BUY/SELL symmetry) -- only the structural-control
    estimand is restricted to overlap support, because matched-random and
    +6h have their own candidate/reference semantics and are not
    restricted by structural-control overlap."""
    t_arr = panel["t_ms"]
    f = panel["feat"][w_minutes]
    ctrl_mask = ordinary_control_mask(f["D"], f["abs_imbalance_pctl"], panel["in_development"])
    ctrl_kept = apply_refractory(t_arr, ctrl_mask)
    ctrl_idx = np.flatnonzero(ctrl_kept & elig_set)
    ctrl = outcome_bundle(panel, ctrl_idx, w_minutes, h_minutes)

    def _key(bundle: dict, i: int) -> tuple:
        return (
            str(bundle["month"][i]), int(bundle["direction"][i]),
            int(bundle["price_alignment"][i]), int(bundle["price_strength_bin"][i]), int(bundle["activity_bin"][i]),
        )

    cand_keys = [_key(cand, i) for i in range(len(cand["idx"]))]
    ctrl_keys = [_key(ctrl, i) for i in range(len(ctrl["idx"]))]

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
        candidate_overlap_standardized_mean = sum(weight[k] * cand_stratum_mean[k] for k in weight)
        structural_control_standardized_mean = sum(weight[k] * ctrl_stratum_mean[k] for k in weight)
        structural_delta = candidate_overlap_standardized_mean - structural_control_standardized_mean
    else:
        candidate_overlap_standardized_mean = None
        structural_control_standardized_mean = None
        structural_delta = None

    return {
        "ordinary_band": list(ORDINARY_BAND),
        "strata_definition": ["calendar_month", "D", "price_alignment", "price_strength_bin", "activity_bin"],
        # LIKE-WITH-LIKE structural comparison (both sides restricted to,
        # and weighted over, exactly the same overlap strata):
        "candidate_overlap_standardized_mean": candidate_overlap_standardized_mean,
        "structural_control_standardized_mean": structural_control_standardized_mean,
        "structural_delta": structural_delta,
        # Reported for transparency/contrast ONLY -- the full, unrestricted
        # candidate-population mean is never itself part of the structural
        # delta above; it remains the estimand for every OTHER gate
        # (primary/matched/shift/bootstrap/year/symmetry), computed
        # upstream in metric_block and passed in here only for reporting.
        "full_candidate_mean": cand_mean,
        "candidate_overlap_N": total_overlap_cand_n,
        "candidate_total_N": candidate_total_n,
        "matched_candidate_N": matched_candidate_n,
        "unmatched_candidate_N": unmatched_candidate_n,
        "unmatched_candidate_share": unmatched_candidate_share,
        "control_total_N": int(len(ctrl_keys)),
        "number_of_candidate_strata": len(cand_strata),
        "number_of_matched_strata": len(overlap_strata),
        "number_of_unmatched_candidate_strata": len(cand_strata - ctrl_strata),
        # Descriptive only -- MUST NOT feed any gate.
        "full_control_unstandardized_mean": _mean(ctrl["norm"]),
    }


def matched_random_bundle(
    panel: dict, cand: dict, pool_idx: np.ndarray, w_minutes: int, h_minutes: int,
    seed: int = SEED_MATCHED, replicates: int = N_MATCHED,
) -> dict:
    """Match on calendar_month + D only. One frozen seed consumed exactly
    once across all `replicates` draws."""
    empty = {
        "N_replicates": replicates, "seed": seed,
        "matched_mean": None, "candidate_minus_matched": None,
        "matched_mean_distribution": {"p025": None, "p50": None, "p975": None},
    }
    if cand["idx"].size == 0 or pool_idx.size == 0:
        return empty

    months = panel["month_key"]
    ret = panel["ret"][h_minutes]
    scale = panel["scale"][h_minutes]

    need_buy: dict = {}
    need_sell: dict = {}
    pool_by_month: dict = {}
    for m in np.unique(cand["month"]):
        m = str(m)
        sel = cand["month"] == m
        need_buy[m] = int(np.sum(sel & (cand["direction"] == DIR_BUY)))
        need_sell[m] = int(np.sum(sel & (cand["direction"] == DIR_SELL)))
        pool_by_month[m] = pool_idx[months[pool_idx] == m]
        need = need_buy[m] + need_sell[m]
        if need > pool_by_month[m].size:
            raise H05Error(f"matched-random n={need} exceeds eligible {pool_by_month[m].size} in {m}")

    rng = np.random.default_rng(seed)
    replicate_means = []
    for _ in range(replicates):
        picked, labels = sample_matched_random_once(rng, pool_by_month, need_buy, need_sell)
        if picked.size == 0:
            replicate_means.append(np.nan)
            continue
        r = labels.astype(np.float64) * ret[picked]
        sc = scale[picked]
        ok = np.isfinite(r) & np.isfinite(sc) & (sc > 0)
        norm = r[ok] / sc[ok]
        replicate_means.append(float(np.mean(norm)) if norm.size else np.nan)

    arr = np.asarray(replicate_means, dtype=np.float64)
    cand_mean = _mean(cand["norm"])
    matched_mean = float(np.nanmean(arr)) if np.any(np.isfinite(arr)) else None

    def _distribution(values: np.ndarray) -> dict:
        v = values[np.isfinite(values)]
        if v.size == 0:
            return {"p025": None, "p50": None, "p975": None}
        return {"p025": float(np.percentile(v, 2.5)), "p50": float(np.percentile(v, 50)),
                "p975": float(np.percentile(v, 97.5))}

    return {
        "N_replicates": replicates, "seed": seed,
        "matched_mean": matched_mean,
        "candidate_minus_matched": None if (cand_mean is None or matched_mean is None) else cand_mean - matched_mean,
        "matched_mean_distribution": _distribution(arr),
    }


def negative_control_bundle(panel: dict, cand: dict, raw_mask: np.ndarray, w_minutes: int, h_minutes: int) -> dict:
    """+6h same-UTC-day circular shift, preserving each candidate's own D.
    Never redetects the candidate at the shifted timestamp (no filter on
    the shifted position's own candidacy is required or applied -- the
    shifted timestamp's OWN feature state is irrelevant; only its return/
    scale eligibility matters)."""
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
        return {"shifted_mean": None, "candidate_minus_shifted": None, "collision_fraction": coll}

    idx = np.asarray(shifted_idx, dtype=np.int64)
    direction = np.asarray(shifted_dir, dtype=np.int64)
    ret = panel["ret"][h_minutes][idx]
    scale = panel["scale"][h_minutes][idx]
    raw_ret = direction.astype(np.float64) * ret
    norm, elig = normalize(raw_ret, scale)
    shifted_mean = _mean(norm[elig])
    cand_mean = _mean(cand["norm"])
    return {
        "shifted_mean": shifted_mean,
        "candidate_minus_shifted": None if (cand_mean is None or shifted_mean is None) else cand_mean - shifted_mean,
        "collision_fraction": coll,
    }


def year_breakdown(cand: dict) -> dict:
    out = {}
    for y in YEAR_BLOCKS:
        sl = cand["year"] == y
        n = int(np.sum(sl))
        out[str(y)] = {"N": n, "candidate_mean": _mean(cand["norm"][sl]) if n else None}
    return out


def direction_breakdown(cand: dict) -> dict:
    out = {}
    for name, d in (("BUY", DIR_BUY), ("SELL", DIR_SELL)):
        sl = cand["direction"] == d
        n = int(np.sum(sl))
        out[name] = {
            "N": n,
            "mean": _mean(cand["norm"][sl]) if n else None,
            "median": _median(cand["norm"][sl]) if n else None,
            "P_pos": _share_pos(cand["norm"][sl]) if n else None,
            "raw_mean_bps": (lambda m: None if m is None else float(m * 10_000.0))(_mean(cand["raw_ret"][sl]) if n else None),
        }
    return out


def evaluate_cell(panel: dict, w_minutes: int, q: float, h_minutes: int) -> dict:
    t_arr = panel["t_ms"]
    f = panel["feat"][w_minutes]
    raw_mask = candidate_mask(f["D"], f["abs_imbalance_pctl"], q, panel["in_development"])
    raw_n = int(np.sum(raw_mask))
    kept = apply_refractory(t_arr, raw_mask)
    elig = eligible_index(panel, w_minutes, h_minutes)
    elig_set = np.zeros(len(t_arr), dtype=bool)
    elig_set[elig] = True

    cand_idx = np.flatnonzero(kept & elig_set)
    cand = outcome_bundle(panel, cand_idx, w_minutes, h_minutes)
    metrics = metric_block(cand["raw_ret"], cand["norm"])
    cand_mean = metrics["candidate_mean"]

    structural = structural_control_bundle(panel, cand, cand_mean, w_minutes, h_minutes, elig_set)

    raw_in_elig = np.flatnonzero(raw_mask & elig_set)
    pool_idx = build_matched_random_pool(elig, raw_in_elig)
    matched = matched_random_bundle(panel, cand, pool_idx, w_minutes, h_minutes)

    shift = negative_control_bundle(panel, cand, raw_mask, w_minutes, h_minutes)

    dep_sensitivity = dependence_sensitivity_bundle(cand["week"], cand["norm"])
    legacy_week_boot = week_block_bootstrap(cand["week"], cand["norm"])
    clustering = candidate_clustering_diagnostic(t_arr, kept)

    yearly = year_breakdown(cand)
    yearly_means = {y: yearly[str(y)]["candidate_mean"] for y in YEAR_BLOCKS}
    dirs = direction_breakdown(cand)

    claim_eval = {}
    for name, sign in SIGNS.items():
        # structural["structural_delta"] is the already like-with-like
        # overlap comparison (pre-outcome structural-support correction) --
        # NOT structural["full_candidate_mean"] differenced against a
        # control mean of different support.
        ev = claim_evaluation(cand_mean, matched["matched_mean"], structural["structural_delta"],
                               shift["shifted_mean"], sign)
        ev["bootstrap_gate"] = bootstrap_sign_gate(dep_sensitivity, sign)
        ev["year_stability_gate"] = year_stability_gate(yearly_means, sign)
        ev["direction_symmetry_gate"] = direction_symmetry_gate(dirs["BUY"]["mean"], dirs["SELL"]["mean"], sign)
        ev["directional_support"] = directional_support(
            cand_mean, matched["matched_mean"], structural["structural_delta"], sign
        )
        claim_eval[name] = ev

    return {
        "W": w_minutes, "q": q, "H": h_minutes,
        **metrics,
        "raw_pre_refractory_N": raw_n,
        "post_refractory_N": int(np.sum(kept)),
        "ineligible_total_w_n": int(f["ineligible_total_w_n"]),
        "matched_random": matched,
        "structural_control": structural,
        "negative_control": shift,
        "year_breakdown": yearly,
        "direction_breakdown": dirs,
        "concentration": concentration_from_times(cand["t_ms"], cand["direction"], cand["norm"]),
        "week_block_bootstrap": legacy_week_boot,
        "dependence_sensitivity": dep_sensitivity,
        "candidate_clustering": clustering,
        "claim_evaluation": claim_eval,
    }


def evaluate_h05(panel: dict) -> dict:
    cells = []
    for w in W_WINDOWS:
        for q in Q_THRESHOLDS:
            for h in HORIZONS:
                cells.append(evaluate_cell(panel, w, q, h))

    forbidden_months = []
    for c in cells:
        for m in c["concentration"]["by_month"].keys():
            if m.startswith("2025") or m.startswith("2026"):
                forbidden_months.append(m)
    if forbidden_months:
        raise ValidationWindowForbidden(f"result months include forbidden windows: {forbidden_months}")

    return {
        "hypothesis_id": "H05_TAKER_IMBALANCE_SUBSEQUENT_RETURN",
        "dataset_id": DATASET_ID,
        "snapshot_id": REQUIRED_SNAPSHOT,
        "search_surface": {
            "W": list(W_WINDOWS), "q": list(Q_THRESHOLDS), "H": list(HORIZONS),
            "primary_threshold_cells": 45,
            "batch01_cumulative_cells": 225,
            "sign_multiplicity": ["continuation", "reversal"],
        },
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
