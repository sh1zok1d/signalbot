"""H01 compression → realized-volatility expansion helpers.

Development-only. Refuses 2025/2026 canonical partitions and any outcome
window that reaches 2025-01-01. Does not reuse V1/V2 detectors.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

import numpy as np
import yaml

UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[2]
PREREG_JSON = REPO_ROOT / "docs" / "research" / "H01_COMPRESSION_EXPANSION_PREREG.json"
REPO_MANIFEST = REPO_ROOT / "docs" / "manifests" / "CORE_BTC_BINANCE_V0.yaml"
REQUIRED_SNAPSHOT = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
DATASET_ID = "CORE_BTC_BINANCE_V0"

BAR_MS = 60_000
GRID_MS = 15 * BAR_MS
DEV_END_MS = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
DEV_START_MS = int(datetime(2020, 2, 1, tzinfo=UTC).timestamp() * 1000)
WARMUP_START_MS = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
MAX_H_MIN = 240
REF_DAYS = 30
REF_STEPS = REF_DAYS * 24 * 60 // 15  # 2880
LOOKBACKS = (30, 60, 120)
THRESHOLDS_Q = (0.10, 0.20, 0.30)
HORIZONS = (15, 30, 60, 120, 240)
YEAR_BLOCKS = (2020, 2021, 2022, 2023, 2024)
SEED_MATCHED = 20260826
SEED_PERM = 20260827
SEED_BOOT = 20260828
N_MATCHED = 100
N_BOOT = 2000
FORBIDDEN_YEAR_PREFIXES = ("2025-", "2026-")


class H01Error(RuntimeError):
    pass


class ValidationWindowForbidden(H01Error):
    pass


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
        raise H01Error(f"unexpected dataset_id {data.get('dataset_id')}")
    snap = data.get("snapshot_id")
    if snap != REQUIRED_SNAPSHOT:
        raise H01Error(f"snapshot mismatch: {snap} != {REQUIRED_SNAPSHOT}")
    if data.get("status") != "ACCEPTED_FOR_DISCOVERY":
        raise H01Error(f"dataset not ACCEPTED_FOR_DISCOVERY: {data.get('status')}")
    if data.get("research_authorized") is not True:
        raise H01Error("research_authorized is not true")
    if data.get("confirmatory_authorized") is True:
        raise H01Error("confirmatory_authorized must remain false for H01")
    return snap


def assert_development_outcome_window(t_ms: int, h_min: int) -> None:
    end_ms = t_ms + h_min * BAR_MS
    if end_ms >= DEV_END_MS:
        raise ValidationWindowForbidden(
            f"outcome window [{iso_ms(t_ms)}, {iso_ms(end_ms)}] reaches 2025+"
        )


def last_known_bar_open_ms(t_ms: int) -> int:
    """Last 1m bar known at T: available_at = open+60s <= T."""
    return t_ms - BAR_MS


def future_bar_open_times_ms(t_ms: int, h_min: int) -> tuple[int, int]:
    """Future 1m bars with available_at in (T, T+H]: open in [T, T+H)."""
    return t_ms, t_ms + h_min * BAR_MS


def development_t_max_ms() -> int:
    # T + 240m < 2025-01-01 → last 15m boundary at 2024-12-31T19:45:00Z
    raw = DEV_END_MS - MAX_H_MIN * BAR_MS
    return raw - GRID_MS


def is_grid_ms(t_ms: int) -> bool:
    return t_ms % GRID_MS == 0


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


def _forbid_partition_name(name: str) -> None:
    for prefix in FORBIDDEN_YEAR_PREFIXES:
        if name.startswith(prefix):
            raise ValidationWindowForbidden(
                f"refusing canonical partition {name} (2025/2026 forbidden in H01 development)"
            )


def list_development_parquet_paths(dataset_root: Path) -> list[Path]:
    monthly = dataset_root / "canonical" / "1m" / "monthly"
    if not monthly.is_dir():
        raise H01Error(f"missing canonical 1m monthly dir: {monthly}")
    paths = []
    for p in sorted(monthly.glob("*.parquet")):
        _forbid_partition_name(p.name)
        year = int(p.name.split("-", 1)[0])
        if 2020 <= year <= 2024:
            paths.append(p)
    if not paths:
        raise H01Error("no 2020-2024 canonical monthly parquet found")
    return paths


def load_development_arrays(dataset_root: Path) -> dict:
    """Load 2020-2024 1m arrays only. Never opens 2025/2026 parquet."""
    require_pyarrow()
    import pyarrow.parquet as pq

    runtime_snap = dataset_root / "reports" / "snapshot_manifest.json"
    if runtime_snap.exists():
        snap = json.loads(runtime_snap.read_text(encoding="utf-8"))
        sid = snap.get("snapshot_id")
        if sid != REQUIRED_SNAPSHOT:
            raise H01Error(f"runtime snapshot_id {sid} != {REQUIRED_SNAPSHOT}")

    cols = ["open_time_ms", "available_at_ms", "close", "high", "low"]
    opens, avails, closes, highs, lows = [], [], [], [], []
    for path in list_development_parquet_paths(dataset_root):
        table = pq.read_table(path, columns=cols)
        if "close_time_ms" in table.column_names:
            raise H01Error("close_time_ms must not be loaded")
        opens.append(np.asarray(table.column("open_time_ms").to_pylist(), dtype=np.int64))
        avails.append(np.asarray(table.column("available_at_ms").to_pylist(), dtype=np.int64))
        closes.append(np.array([parse_px(x) for x in table.column("close").to_pylist()], dtype=np.float64))
        highs.append(np.array([parse_px(x) for x in table.column("high").to_pylist()], dtype=np.float64))
        lows.append(np.array([parse_px(x) for x in table.column("low").to_pylist()], dtype=np.float64))
    open_ms = np.concatenate(opens)
    order = np.argsort(open_ms, kind="mergesort")
    frame = {
        "open_time_ms": open_ms[order],
        "available_at_ms": np.concatenate(avails)[order],
        "close": np.concatenate(closes)[order],
        "high": np.concatenate(highs)[order],
        "low": np.concatenate(lows)[order],
    }
    if frame["open_time_ms"][0] < WARMUP_START_MS:
        raise H01Error("unexpected bars before warmup start")
    if int(frame["open_time_ms"][-1]) >= DEV_END_MS:
        raise ValidationWindowForbidden("loaded bars reach 2025+")
    if np.any(frame["available_at_ms"] != frame["open_time_ms"] + BAR_MS):
        raise H01Error("available_at_ms is not open_time_ms + 60s")
    return frame


def require_pyarrow() -> None:
    try:
        import pyarrow  # noqa: F401
    except ImportError as exc:
        raise H01Error("pyarrow is required; install requirements-research.txt") from exc


def log_returns(close: np.ndarray) -> np.ndarray:
    r = np.full(close.shape, np.nan, dtype=np.float64)
    prev = close[:-1]
    cur = close[1:]
    ok = np.isfinite(prev) & np.isfinite(cur) & (prev > 0) & (cur > 0)
    r[1:][ok] = np.log(cur[ok] / prev[ok])
    return r


def rolling_sum_last(values: np.ndarray, length: int) -> np.ndarray:
    x = np.nan_to_num(values, nan=0.0)
    c = np.cumsum(x)
    out = np.full(values.shape, np.nan, dtype=np.float64)
    if length <= 0 or length > len(values):
        return out
    out[length - 1] = c[length - 1]
    out[length:] = c[length:] - c[:-length]
    finite = np.isfinite(values)
    # require the window itself to contain no NaN original returns
    cf = np.cumsum(finite.astype(np.int32))
    count = np.zeros(len(values), dtype=np.int32)
    count[length - 1] = cf[length - 1]
    count[length:] = cf[length:] - cf[:-length]
    out[count != length] = np.nan
    return out


def midrank_percentile_against_prior(series: np.ndarray, window: int) -> np.ndarray:
    """Percentile of series[i] among series[i-window:i] (current excluded)."""
    n = len(series)
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(window, n):
        x = series[i]
        if not np.isfinite(x):
            continue
        ref = series[i - window:i]
        if not np.all(np.isfinite(ref)):
            continue
        less = np.count_nonzero(ref < x)
        eq = np.count_nonzero(ref == x)
        out[i] = 100.0 * (less + 0.5 * eq) / window
    return out


def trailing_median_q75(known_values: np.ndarray, window: int, known_lag_steps: int) -> tuple[np.ndarray, np.ndarray]:
    """Median and q75 of values known by index i: values[i-window:i-known_lag_steps+1]? 

    values[j] is FUTURE_RV at decision j, known at j + known_lag_steps.
    At index i, use j in [i-window, i-known_lag_steps] inclusive? j < i and
    j <= i - known_lag_steps → j in [i-window, i-known_lag_steps].
    """
    n = len(known_values)
    med = np.full(n, np.nan, dtype=np.float64)
    q75 = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        end = i - known_lag_steps + 1  # exclusive
        start = i - window
        if start < 0 or end <= start:
            continue
        ref = known_values[start:end]
        if ref.size != (end - start) or not np.all(np.isfinite(ref)):
            continue
        med[i] = float(np.median(ref))
        q75[i] = float(np.quantile(ref, 0.75, method="linear"))
    return med, q75


def build_grid_ms(start_ms: int, last_inclusive_ms: int) -> np.ndarray:
    if start_ms % GRID_MS or last_inclusive_ms % GRID_MS:
        raise H01Error("grid bounds are not 15m UTC aligned")
    n = (last_inclusive_ms - start_ms) // GRID_MS + 1
    return start_ms + np.arange(n, dtype=np.int64) * GRID_MS


def minute_index(open_ms: np.ndarray, t_open_ms: np.ndarray) -> np.ndarray:
    base = int(open_ms[0])
    idx = (t_open_ms - base) // BAR_MS
    return idx.astype(np.int64)


def build_panel(frame: dict) -> dict:
    """Build 15m panel of RV, compression, future RV/range, and trailing scales."""
    open_ms = frame["open_time_ms"]
    avail = frame["available_at_ms"]
    close = frame["close"]
    high = frame["high"]
    low = frame["low"]
    n = len(open_ms)
    if n < 2:
        raise H01Error("not enough 1m bars")
    r = log_returns(close)
    r2 = r * r
    last_t = development_t_max_ms()
    grid = build_grid_ms(WARMUP_START_MS, last_t)
    # last known 1m open at each T
    last_open = grid - BAR_MS
    last_i = minute_index(open_ms, last_open)
    valid_i = (last_i >= 1) & (last_i < n)
    panel = {
        "t_ms": grid,
        "year": np.array([utc_year(int(x)) for x in grid], dtype=np.int16),
        "month_key": np.array([utc_month_key(int(x)) for x in grid]),
        "week_key": np.array([utc_week_key(int(x)) for x in grid]),
        "day_key": np.array([utc_day_key(int(x)) for x in grid]),
        "in_development": (grid >= DEV_START_MS) & (grid <= last_t),
    }
    for L in LOOKBACKS:
        rv = np.full(grid.shape, np.nan, dtype=np.float64)
        win_sum = rolling_sum_last(r2, L)
        ok = valid_i & (last_i >= L)
        rv[ok] = np.sqrt(win_sum[last_i[ok]])
        panel[f"rv_{L}"] = rv
        panel[f"C_{L}"] = midrank_percentile_against_prior(rv, REF_STEPS)

    # log-range helper on 1m: ln(high/low) not used directly; path high/low
    log_high = np.log(np.clip(high, 1e-12, None))
    log_low = np.log(np.clip(low, 1e-12, None))

    first_future_i = minute_index(open_ms, grid)  # bar opening at T
    for H in HORIZONS:
        fut = np.full(grid.shape, np.nan, dtype=np.float64)
        rng = np.full(grid.shape, np.nan, dtype=np.float64)
        start_i = first_future_i
        end_i = start_i + H  # exclusive
        ok = (
            valid_i
            & (start_i >= 1)
            & (end_i <= n)
            & (grid + H * BAR_MS < DEV_END_MS)
        )
        # available_at of last future bar = open + 60s = T+H
        for k in np.flatnonzero(ok):
            a = int(start_i[k])
            b = int(end_i[k])
            chunk = r2[a:b]
            if chunk.size != H or not np.all(np.isfinite(chunk)):
                continue
            fut[k] = float(np.sqrt(np.sum(chunk)))
            mx = float(np.max(high[a:b]))
            mn = float(np.min(low[a:b]))
            if mx > 0 and mn > 0:
                rng[k] = float(np.log(mx / mn))
        panel[f"fut_rv_{H}"] = fut
        panel[f"fut_range_{H}"] = rng
        lag = H // 15
        med, q75 = trailing_median_q75(fut, REF_STEPS, lag)
        rmed, _ = trailing_median_q75(rng, REF_STEPS, lag)
        panel[f"past_med_rv_{H}"] = med
        panel[f"past_q75_rv_{H}"] = q75
        panel[f"past_med_range_{H}"] = rmed
        with np.errstate(divide="ignore", invalid="ignore"):
            panel[f"norm_rv_{H}"] = fut / med
            panel[f"norm_range_{H}"] = rng / rmed
            panel[f"expansion_{H}"] = np.where(
                np.isfinite(fut) & np.isfinite(q75),
                (fut >= q75).astype(np.float64),
                np.nan,
            )
    panel["_last_i"] = last_i
    panel["_avail"] = avail
    panel["_open"] = open_ms
    return panel


def eligible_mask(panel: dict, L: int, H: int) -> np.ndarray:
    return (
        panel["in_development"]
        & np.isfinite(panel[f"C_{L}"])
        & np.isfinite(panel[f"fut_rv_{H}"])
        & np.isfinite(panel[f"past_med_rv_{H}"])
        & (panel[f"past_med_rv_{H}"] > 0)
        & np.isfinite(panel[f"past_q75_rv_{H}"])
        & np.isfinite(panel[f"norm_rv_{H}"])
    )


def candidate_mask(panel: dict, L: int, q: float, H: int) -> np.ndarray:
    return eligible_mask(panel, L, H) & (panel[f"C_{L}"] <= 100.0 * q)


def _mean(x: np.ndarray) -> Optional[float]:
    x = x[np.isfinite(x)]
    if x.size == 0:
        return None
    return float(np.mean(x))


def _median(x: np.ndarray) -> Optional[float]:
    x = x[np.isfinite(x)]
    if x.size == 0:
        return None
    return float(np.median(x))


def consecutive_run_stats(mask: np.ndarray) -> dict:
    runs = []
    run = 0
    for v in mask:
        if v:
            run += 1
        elif run:
            runs.append(run)
            run = 0
    if run:
        runs.append(run)
    arr = np.array(runs, dtype=np.int32) if runs else np.array([0], dtype=np.int32)
    n = int(np.sum(mask))
    adjacent = 0
    prev = False
    for v in mask:
        if v and prev:
            adjacent += 1
        prev = bool(v)
    return {
        "n_runs": int(len(runs)),
        "mean_run_length": float(np.mean(arr)) if runs else 0.0,
        "max_run_length": int(np.max(arr)) if runs else 0,
        "fraction_adjacent_to_previous": (adjacent / n) if n else None,
    }


def concentration_stats(panel: dict, mask: np.ndarray) -> dict:
    t = panel["t_ms"][mask]
    if t.size == 0:
        return {
            "raw_n": 0,
            "unique_utc_days": 0,
            "unique_utc_weeks": 0,
            "unique_utc_months": 0,
            "by_year": {},
            "by_month": {},
            "top5_month_share": None,
            "max_month_share": None,
            "clustering": consecutive_run_stats(mask),
        }
    days = {utc_day_key(int(x)) for x in t}
    weeks = {utc_week_key(int(x)) for x in t}
    months = [utc_month_key(int(x)) for x in t]
    years = [utc_year(int(x)) for x in t]
    month_counts: dict[str, int] = {}
    for m in months:
        month_counts[m] = month_counts.get(m, 0) + 1
    year_counts: dict[str, int] = {}
    for y in years:
        year_counts[str(y)] = year_counts.get(str(y), 0) + 1
    n = int(t.size)
    ordered = sorted(month_counts.items(), key=lambda kv: kv[1], reverse=True)
    top5 = sum(c for _, c in ordered[:5]) / n
    max_share = ordered[0][1] / n
    return {
        "raw_n": n,
        "unique_utc_days": len(days),
        "unique_utc_weeks": len(weeks),
        "unique_utc_months": len(month_counts),
        "by_year": year_counts,
        "by_month": dict(ordered),
        "top5_month_share": float(top5),
        "max_month_share": float(max_share),
        "clustering": consecutive_run_stats(mask),
    }


def matched_random_means(
    panel: dict, L: int, q: float, H: int, field: str, replicates: int = N_MATCHED, seed: int = SEED_MATCHED,
) -> dict:
    elig = eligible_mask(panel, L, H)
    cand = candidate_mask(panel, L, q, H)
    months = panel["month_key"]
    rng = np.random.default_rng(seed)
    month_to_elig: dict[str, np.ndarray] = {}
    month_n: dict[str, int] = {}
    for m in np.unique(months[elig]):
        month_to_elig[str(m)] = np.flatnonzero(elig & (months == m))
        month_n[str(m)] = int(np.sum(cand & (months == m)))
    values = panel[field]
    means = []
    for _ in range(replicates):
        picked = []
        for m, n in month_n.items():
            pool = month_to_elig[m]
            if n == 0:
                continue
            if n > pool.size:
                raise H01Error(f"matched-random n={n} exceeds eligible {pool.size} in {m}")
            picked.append(rng.choice(pool, size=n, replace=False))
        if not picked:
            means.append(float("nan"))
            continue
        idx = np.concatenate(picked)
        means.append(float(np.mean(values[idx])))
    arr = np.asarray(means, dtype=np.float64)
    return {
        "replicate_mean": float(np.nanmean(arr)),
        "replicate_p05": float(np.nanpercentile(arr, 5)),
        "replicate_p50": float(np.nanpercentile(arr, 50)),
        "replicate_p95": float(np.nanpercentile(arr, 95)),
        "replicates": replicates,
        "seed": seed,
    }


def permutation_candidate_mean(
    panel: dict, L: int, q: float, H: int, field: str, seed: int = SEED_PERM,
) -> dict:
    elig = eligible_mask(panel, L, H)
    scores = panel[f"C_{L}"].copy()
    rng = np.random.default_rng(seed)
    months = panel["month_key"]
    for m in np.unique(months[elig]):
        idx = np.flatnonzero(elig & (months == m))
        scores[idx] = rng.permutation(scores[idx])
    perm_cand = elig & (scores <= 100.0 * q)
    vals = panel[field][perm_cand]
    return {
        "N": int(np.sum(perm_cand)),
        "mean": _mean(vals),
        "seed": seed,
    }


def week_block_bootstrap(
    panel: dict, L: int, q: float, H: int, field: str, replicates: int = N_BOOT, seed: int = SEED_BOOT,
) -> dict:
    elig = eligible_mask(panel, L, H)
    cand = candidate_mask(panel, L, q, H)
    weeks = panel["week_key"]
    values = panel[field]
    uniq = np.unique(weeks[elig])
    n_w = uniq.size
    sum_all = np.zeros(n_w, dtype=np.float64)
    n_all = np.zeros(n_w, dtype=np.float64)
    sum_c = np.zeros(n_w, dtype=np.float64)
    n_c = np.zeros(n_w, dtype=np.float64)
    for i, w in enumerate(uniq):
        idx = np.flatnonzero(elig & (weeks == w))
        v = values[idx]
        sum_all[i] = float(np.sum(v))
        n_all[i] = float(idx.size)
        cidx = cand[idx]
        sum_c[i] = float(np.sum(v[cidx]))
        n_c[i] = float(np.sum(cidx))
    rng = np.random.default_rng(seed)
    diffs = np.full(replicates, np.nan, dtype=np.float64)
    for b in range(replicates):
        draw = rng.integers(0, n_w, size=n_w)
        sa = np.sum(sum_all[draw])
        na = np.sum(n_all[draw])
        sc = np.sum(sum_c[draw])
        nc = np.sum(n_c[draw])
        if na <= 0 or nc <= 0 or nc >= na:
            continue
        diffs[b] = (sc / nc) - (sa / na)
    obs_na = np.sum(n_all)
    obs_nc = np.sum(n_c)
    obs_diff = float((np.sum(sum_c) / obs_nc) - (np.sum(sum_all) / obs_na)) if obs_nc > 0 and obs_na > 0 else float("nan")
    return {
        "observed_diff": obs_diff,
        "ci95_low": float(np.nanpercentile(diffs, 2.5)),
        "ci95_high": float(np.nanpercentile(diffs, 97.5)),
        "replicates": replicates,
        "seed": seed,
        "block": "UTC_WEEK",
    }


def year_breakdown(panel: dict, L: int, q: float, H: int) -> dict:
    elig = eligible_mask(panel, L, H)
    cand = candidate_mask(panel, L, q, H)
    out = {}
    for y in YEAR_BLOCKS:
        ymask = panel["year"] == y
        c = cand & ymask
        e = elig & ymask
        n = int(np.sum(c))
        if n == 0 or not np.any(e):
            out[str(y)] = {"N": n, "mean_norm_rv": None, "p_expansion": None, "baseline_mean_norm_rv": None, "diff_norm_rv": None}
            continue
        mn = _mean(panel[f"norm_rv_{H}"][c])
        be = _mean(panel[f"norm_rv_{H}"][e])
        pe = _mean(panel[f"expansion_{H}"][c])
        out[str(y)] = {
            "N": n,
            "mean_norm_rv": mn,
            "p_expansion": pe,
            "baseline_mean_norm_rv": be,
            "diff_norm_rv": None if mn is None or be is None else mn - be,
            "baseline_p_expansion": _mean(panel[f"expansion_{H}"][e]),
        }
    return out


def decile_table(panel: dict, L: int, H: int) -> list[dict]:
    elig = eligible_mask(panel, L, H)
    c = panel[f"C_{L}"]
    rows = []
    edges = list(range(0, 100, 10))
    for i, lo in enumerate(edges):
        hi = lo + 10
        if i == len(edges) - 1:
            sel = elig & (c >= lo) & (c <= 100.0)
            label = "[90,100]"
        else:
            sel = elig & (c >= lo) & (c < hi)
            label = f"[{lo},{hi})"
        rows.append({
            "bin": label,
            "lo": lo,
            "hi": 100 if i == len(edges) - 1 else hi,
            "N": int(np.sum(sel)),
            "mean_norm_rv": _mean(panel[f"norm_rv_{H}"][sel]),
            "median_norm_rv": _median(panel[f"norm_rv_{H}"][sel]),
            "p_expansion": _mean(panel[f"expansion_{H}"][sel]),
        })
    finite_means = [r["mean_norm_rv"] for r in rows if r["mean_norm_rv"] is not None]
    spearman = None
    if len(finite_means) == 10:
        x = np.arange(10, dtype=np.float64)
        y = np.asarray(finite_means, dtype=np.float64)
        # Spearman via rank correlation
        rx = np.argsort(np.argsort(x)).astype(np.float64)
        ry = np.argsort(np.argsort(y)).astype(np.float64)
        spearman = float(np.corrcoef(rx, ry)[0, 1])
    return {"bins": rows, "spearman_bin_mean_norm_rv": spearman}


def evaluate_cell(panel: dict, L: int, q: float, H: int) -> dict:
    elig = eligible_mask(panel, L, H)
    cand = candidate_mask(panel, L, q, H)
    n = int(np.sum(cand))
    n_elig = int(np.sum(elig))
    norm = panel[f"norm_rv_{H}"]
    expn = panel[f"expansion_{H}"]
    rng = panel[f"norm_range_{H}"]
    matched_norm = matched_random_means(panel, L, q, H, f"norm_rv_{H}")
    matched_exp = matched_random_means(panel, L, q, H, f"expansion_{H}")
    perm_norm = permutation_candidate_mean(panel, L, q, H, f"norm_rv_{H}")
    perm_exp = permutation_candidate_mean(panel, L, q, H, f"expansion_{H}")
    boot_norm = week_block_bootstrap(panel, L, q, H, f"norm_rv_{H}")
    boot_exp = week_block_bootstrap(panel, L, q, H, f"expansion_{H}")
    mean_norm = _mean(norm[cand])
    base_norm = _mean(norm[elig])
    p_exp = _mean(expn[cand])
    base_p = _mean(expn[elig])
    return {
        "L": L,
        "q": q,
        "H": H,
        "N": n,
        "N_eligible": n_elig,
        "mean_norm_rv": mean_norm,
        "median_norm_rv": _median(norm[cand]),
        "p_expansion": p_exp,
        "baseline_A_mean_norm_rv": base_norm,
        "baseline_A_p_expansion": base_p,
        "true_minus_baseline_norm_rv": None if mean_norm is None or base_norm is None else mean_norm - base_norm,
        "true_minus_baseline_p_expansion": None if p_exp is None or base_p is None else p_exp - base_p,
        "matched_random_norm_rv": matched_norm,
        "true_minus_matched_norm_rv": None if mean_norm is None else mean_norm - matched_norm["replicate_mean"],
        "matched_random_p_expansion": matched_exp,
        "true_minus_matched_p_expansion": None if p_exp is None else p_exp - matched_exp["replicate_mean"],
        "permutation_norm_rv": perm_norm,
        "permutation_p_expansion": perm_exp,
        "bootstrap_norm_rv": boot_norm,
        "bootstrap_p_expansion": boot_exp,
        "mean_norm_range": _mean(rng[cand]),
        "baseline_A_mean_norm_range": _mean(rng[elig]),
        "year_breakdown": year_breakdown(panel, L, q, H),
        "concentration": concentration_stats(panel, cand),
    }


def evaluate_h01(panel: dict) -> dict:
    cells = []
    for L in LOOKBACKS:
        for q in THRESHOLDS_Q:
            for H in HORIZONS:
                cells.append(evaluate_cell(panel, L, q, H))
    deciles = {}
    for L in LOOKBACKS:
        deciles[str(L)] = {str(H): decile_table(panel, L, H) for H in HORIZONS}
    elig15 = eligible_mask(panel, 30, 15)
    return {
        "hypothesis_id": "H01_COMPRESSION_EXPANSION",
        "dataset_id": DATASET_ID,
        "snapshot_id": REQUIRED_SNAPSHOT,
        "eligible_development_boundaries": int(np.sum(elig15)),
        "search_surface": {
            "lookbacks": list(LOOKBACKS),
            "thresholds": list(THRESHOLDS_Q),
            "horizons": list(HORIZONS),
            "primary_threshold_cells": 45,
        },
        "windows": {
            "warmup_start_inclusive": "2020-01-01T00:00:00Z",
            "development_start_inclusive": "2020-02-01T00:00:00Z",
            "development_end_exclusive": "2025-01-01T00:00:00Z",
            "t_max_inclusive": iso_ms(development_t_max_ms()),
            "validation_untouched": True,
            "oos_untouched": True,
        },
        "cells": cells,
        "deciles": deciles,
    }


def dumps_json(obj: dict) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"
