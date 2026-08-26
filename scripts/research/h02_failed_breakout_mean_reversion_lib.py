"""H02 failed-breakout → mean-reversion helpers.

Development-only. Refuses 2025/2026 1m canonical partitions and any outcome
window that reaches 2025-01-01. Does not reuse V1/V2 detectors or H01
compression definitions. No volume/taker/trend gates.
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
from numpy.lib.stride_tricks import sliding_window_view

UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[2]
PREREG_JSON = REPO_ROOT / "docs" / "research" / "H02_FAILED_BREAKOUT_MEAN_REVERSION_PREREG.json"
REPO_MANIFEST = REPO_ROOT / "docs" / "manifests" / "CORE_BTC_BINANCE_V0.yaml"
REQUIRED_SNAPSHOT = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
DATASET_ID = "CORE_BTC_BINANCE_V0"

BAR_MS = 60_000
HTF_MIN = 5
HTF_MS = HTF_MIN * BAR_MS
DAY_MS = 24 * 60 * BAR_MS
DEV_END_MS = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
DEV_START_MS = int(datetime(2020, 2, 1, tzinfo=UTC).timestamp() * 1000)
WARMUP_START_MS = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
MAX_H_MIN = 240
REF_DAYS = 30
REF_STEPS = REF_DAYS * 24 * 60 // HTF_MIN  # 8640
LOOKBACKS = (60, 120, 240)
THRESHOLDS_S = (0.00, 0.05, 0.10)
HORIZONS = (15, 30, 60, 120, 240)
YEAR_BLOCKS = (2020, 2021, 2022, 2023, 2024)
REFRACTORY_MS = 30 * BAR_MS
SHIFT_MS = 6 * 60 * BAR_MS
SEED_MATCHED = 20260829
SEED_BOOT = 20260830
N_MATCHED = 100
N_BOOT = 2000
DIR_UPPER = -1
DIR_LOWER = 1


class H02Error(RuntimeError):
    pass


class ValidationWindowForbidden(H02Error):
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
        raise H02Error(f"unexpected dataset_id {data.get('dataset_id')}")
    snap = data.get("snapshot_id")
    if snap != REQUIRED_SNAPSHOT:
        raise H02Error(f"snapshot mismatch: {snap} != {REQUIRED_SNAPSHOT}")
    if data.get("status") != "ACCEPTED_FOR_DISCOVERY":
        raise H02Error(f"dataset not ACCEPTED_FOR_DISCOVERY: {data.get('status')}")
    if data.get("research_authorized") is not True:
        raise H02Error("research_authorized is not true")
    if data.get("confirmatory_authorized") is True:
        raise H02Error("confirmatory_authorized must remain false for H02")
    return snap


def assert_development_outcome_window(t_ms: int, h_min: int) -> None:
    end_ms = t_ms + h_min * BAR_MS
    if end_ms >= DEV_END_MS:
        raise ValidationWindowForbidden(
            f"outcome window [{iso_ms(t_ms)}, {iso_ms(end_ms)}] reaches 2025+"
        )


def development_t_max_ms() -> int:
    # T + 240m < 2025-01-01 and T 5m-aligned → 2024-12-31T19:55:00Z
    return DEV_END_MS - MAX_H_MIN * BAR_MS - HTF_MS


def is_grid_ms(t_ms: int) -> bool:
    return t_ms % HTF_MS == 0


def event_bar_open_ms(t_ms: int) -> int:
    """Event bar B=[T-5m, T) opens at T-5m; available_at = T."""
    return t_ms - HTF_MS


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
            f"refusing canonical partition {name} (2025/2026 forbidden in H02 development)"
        )


def list_development_parquet_paths(dataset_root: Path) -> list[Path]:
    monthly = dataset_root / "canonical" / "1m" / "monthly"
    if not monthly.is_dir():
        raise H02Error(f"missing canonical 1m monthly dir: {monthly}")
    paths = []
    for p in sorted(monthly.glob("*.parquet")):
        year_prefix = p.name[:5]
        if year_prefix in ("2025-", "2026-"):
            continue
        year = int(p.name.split("-", 1)[0])
        if 2020 <= year <= 2024:
            paths.append(p)
    if not paths:
        raise H02Error("no 2020-2024 canonical monthly parquet found")
    return paths


def require_pyarrow() -> None:
    try:
        import pyarrow  # noqa: F401
    except ImportError as exc:
        raise H02Error("pyarrow is required; install requirements-research.txt") from exc


def load_development_1m(dataset_root: Path) -> dict:
    """Load 2020-2024 1m OHLC only. Never opens 2025/2026 parquet."""
    require_pyarrow()
    import pyarrow.parquet as pq

    runtime_snap = dataset_root / "reports" / "snapshot_manifest.json"
    if runtime_snap.exists():
        snap = json.loads(runtime_snap.read_text(encoding="utf-8"))
        sid = snap.get("snapshot_id")
        if sid != REQUIRED_SNAPSHOT:
            raise H02Error(f"runtime snapshot_id {sid} != {REQUIRED_SNAPSHOT}")

    cols = ["open_time_ms", "available_at_ms", "open", "high", "low", "close"]
    buckets = {c: [] for c in ("open_time_ms", "available_at_ms", "open", "high", "low", "close")}
    for path in list_development_parquet_paths(dataset_root):
        table = pq.read_table(path, columns=cols)
        if "close_time_ms" in table.column_names:
            raise H02Error("close_time_ms must not be loaded")
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
        raise H02Error("unexpected bars before warmup start")
    if int(frame["open_time_ms"][-1]) >= DEV_END_MS:
        raise ValidationWindowForbidden("loaded 1m bars reach 2025+")
    if np.any(frame["available_at_ms"] != frame["open_time_ms"] + BAR_MS):
        raise H02Error("available_at_ms is not open_time_ms + 60s")
    return frame


def aggregate_1m_to_5m(frame_1m: dict) -> dict:
    o = frame_1m["open_time_ms"]
    n = len(o)
    if n == 0 or n % HTF_MIN != 0:
        raise H02Error(f"1m length {n} is not a multiple of 5")
    if int(o[0]) % HTF_MS != 0:
        raise H02Error("1m series does not start on a 5m UTC boundary")
    expected = o[0] + np.arange(n, dtype=np.int64) * BAR_MS
    if np.any(o != expected):
        raise H02Error("1m open_time_ms is not a contiguous 1m grid")
    n5 = n // HTF_MIN
    high = frame_1m["high"].reshape(n5, HTF_MIN).max(axis=1)
    low = frame_1m["low"].reshape(n5, HTF_MIN).min(axis=1)
    open_ms = o[::HTF_MIN]
    avail = open_ms + HTF_MS
    last_1m_avail = frame_1m["available_at_ms"][HTF_MIN - 1::HTF_MIN]
    if np.any(last_1m_avail != avail):
        raise H02Error("5m available_at is not last 1m available_at in the bucket")
    frame = {
        "open_time_ms": open_ms,
        "available_at_ms": avail,
        "t_ms": avail,  # decision T = event-bar available_at
        "open": frame_1m["open"][::HTF_MIN],
        "high": high,
        "low": low,
        "close": frame_1m["close"][HTF_MIN - 1::HTF_MIN],
    }
    if np.any(frame["available_at_ms"] != frame["open_time_ms"] + HTF_MS):
        raise H02Error("5m available_at_ms is not open_time_ms + 300s")
    if int(frame["open_time_ms"][-1]) + HTF_MS > DEV_END_MS:
        # last 5m bar of 2024-12-31 23:55 ends 2025-01-01 00:00; that bar's T is 2025
        # and must not be used as a development decision. Outcomes for T<=t_max still
        # only read closes with available_at <= T+240m < 2025, so the 23:55 bar is
        # kept as a future close source for earlier T but never as an event T.
        pass
    return frame


def prior_range(high: np.ndarray, low: np.ndarray, n_bars: int) -> tuple[np.ndarray, np.ndarray]:
    """R_high/R_low at event index i from bars [i-n_bars, i) — event excluded."""
    n = len(high)
    rh = np.full(n, np.nan, dtype=np.float64)
    rl = np.full(n, np.nan, dtype=np.float64)
    if n_bars <= 0 or n <= n_bars:
        return rh, rl
    w_h = sliding_window_view(high, n_bars)
    w_l = sliding_window_view(low, n_bars)
    rh[n_bars:] = w_h.max(axis=1)[: n - n_bars]
    rl[n_bars:] = w_l.min(axis=1)[: n - n_bars]
    return rh, rl


def classify_events(frame5: dict, L: int) -> dict:
    n_bars = L // HTF_MIN
    high = frame5["high"]
    low = frame5["low"]
    opn = frame5["open"]
    close = frame5["close"]
    rh, rl = prior_range(high, low, n_bars)
    with np.errstate(divide="ignore", invalid="ignore"):
        plr = np.log(rh / rl)
    plr = np.where((rh > 0) & (rl > 0) & (rh > rl), plr, np.nan)
    open_in = (opn >= rl) & (opn <= rh)
    close_in = (close >= rl) & (close <= rh)
    upper_touch = high > rh
    lower_touch = low < rl
    lower_ok = low >= rl
    upper_ok = high <= rh
    double = open_in & close_in & upper_touch & lower_touch
    failed_u = open_in & close_in & upper_touch & lower_ok & ~double
    failed_l = open_in & close_in & lower_touch & upper_ok & ~double
    succ_u = open_in & upper_touch & (close > rh) & lower_ok
    succ_l = open_in & lower_touch & (close < rl) & upper_ok
    with np.errstate(divide="ignore", invalid="ignore"):
        ov_u = np.log(high / rh) / plr
        ov_l = np.log(rl / low) / plr
    overshoot = np.full(len(high), np.nan, dtype=np.float64)
    overshoot[failed_u] = ov_u[failed_u]
    overshoot[failed_l] = ov_l[failed_l]
    ov_succ = np.full(len(high), np.nan, dtype=np.float64)
    ov_succ[succ_u] = ov_u[succ_u]
    ov_succ[succ_l] = ov_l[succ_l]
    side = np.zeros(len(high), dtype=np.int8)
    side[failed_u] = DIR_UPPER
    side[failed_l] = DIR_LOWER
    side_s = np.zeros(len(high), dtype=np.int8)
    side_s[succ_u] = DIR_UPPER
    side_s[succ_l] = DIR_LOWER
    return {
        "R_high": rh,
        "R_low": rl,
        "prior_log_range": plr,
        "failed_upper": failed_u,
        "failed_lower": failed_l,
        "failed": failed_u | failed_l,
        "double": double,
        "success_upper": succ_u,
        "success_lower": succ_l,
        "success": succ_u | succ_l,
        "overshoot": overshoot,
        "overshoot_success": ov_succ,
        "side": side,
        "side_success": side_s,
        "open_inside": open_in,
    }


def apply_refractory(t_ms: np.ndarray, mask: np.ndarray, refractory_ms: int = REFRACTORY_MS) -> np.ndarray:
    out = np.zeros(len(mask), dtype=bool)
    last = -10**18
    for i in np.flatnonzero(mask):
        t = int(t_ms[i])
        if t >= last + refractory_ms:
            out[i] = True
            last = t
    return out


def trailing_median_known(values: np.ndarray, window: int, known_lag_steps: int) -> np.ndarray:
    """Median of values[i-window : i-known_lag_steps+1] (outcome known by i)."""
    w = window - known_lag_steps + 1
    n = len(values)
    out = np.full(n, np.nan, dtype=np.float64)
    if w <= 0 or n == 0:
        return out
    rm = pd.Series(values, copy=False).rolling(w, min_periods=w).median().to_numpy()
    # rm[k] = median(values[k-w+1:k+1]); we want that at k = i - known_lag_steps
    src = np.arange(n) - known_lag_steps
    ok = src >= w - 1
    out[ok] = rm[src[ok]]
    return out


def path_mfe_mae(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, i: int, h_bars: int, direction: int,
) -> tuple[float, float]:
    a = i + 1
    b = i + h_bars + 1
    mx = float(np.max(high[a:b]))
    mn = float(np.min(low[a:b]))
    c0 = float(close[i])
    if c0 <= 0 or mx <= 0 or mn <= 0:
        return float("nan"), float("nan")
    if direction == DIR_LOWER:
        mfe = float(np.log(mx / c0))
        mae = float(np.log(c0 / mn))
    else:
        mfe = float(np.log(c0 / mn))
        mae = float(np.log(mx / c0))
    return mfe, mae


def _mean(x: np.ndarray) -> Optional[float]:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return None
    return float(np.mean(x))


def _median(x: np.ndarray) -> Optional[float]:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return None
    return float(np.median(x))


def _pct(x: np.ndarray, q: float) -> Optional[float]:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return None
    return float(np.percentile(x, q))


def _share_pos(x: np.ndarray) -> Optional[float]:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return None
    return float(np.mean(x > 0))


def dumps_json(obj: dict) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n"


def concentration_from_times(t_ms: np.ndarray, side: np.ndarray | None = None) -> dict:
    if t_ms.size == 0:
        return {
            "raw_n": 0,
            "unique_utc_days": 0,
            "unique_utc_weeks": 0,
            "unique_utc_months": 0,
            "by_year": {},
            "by_month": {},
            "top5_month_share": None,
            "max_month_share": None,
            "upper_share": None,
            "lower_share": None,
            "median_spacing_minutes": None,
        }
    days = {utc_day_key(int(x)) for x in t_ms}
    weeks = {utc_week_key(int(x)) for x in t_ms}
    months = [utc_month_key(int(x)) for x in t_ms]
    years = [utc_year(int(x)) for x in t_ms]
    month_counts: dict[str, int] = {}
    for m in months:
        month_counts[m] = month_counts.get(m, 0) + 1
    year_counts: dict[str, int] = {}
    for y in years:
        year_counts[str(y)] = year_counts.get(str(y), 0) + 1
    n = int(t_ms.size)
    ordered = sorted(month_counts.items(), key=lambda kv: kv[1], reverse=True)
    spacing = None
    if n >= 2:
        diffs = np.diff(np.sort(t_ms.astype(np.int64))) / BAR_MS
        spacing = float(np.median(diffs))
    upper_share = lower_share = None
    if side is not None and side.size:
        upper_share = float(np.mean(side == DIR_UPPER))
        lower_share = float(np.mean(side == DIR_LOWER))
    return {
        "raw_n": n,
        "unique_utc_days": len(days),
        "unique_utc_weeks": len(weeks),
        "unique_utc_months": len(month_counts),
        "by_year": year_counts,
        "by_month": dict(ordered),
        "top5_month_share": float(sum(c for _, c in ordered[:5]) / n),
        "max_month_share": float(ordered[0][1] / n),
        "upper_share": upper_share,
        "lower_share": lower_share,
        "median_spacing_minutes": spacing,
    }


def build_panel(frame5: dict) -> dict:
    t = frame5["t_ms"]
    close = frame5["close"]
    high = frame5["high"]
    low = frame5["low"]
    n = len(t)
    t_max = development_t_max_ms()
    in_dev = (t >= DEV_START_MS) & (t <= t_max)
    # future close at T+H is the bar whose available_at = T+H → index + H/5
    ret = {}
    abs_ret = {}
    scale = {}
    for H in HORIZONS:
        h_bars = H // HTF_MIN
        r = np.full(n, np.nan, dtype=np.float64)
        dst = np.arange(n) + h_bars
        ok = dst < n
        ok &= (t + H * BAR_MS) < DEV_END_MS
        c0 = close.copy()
        c1 = np.full(n, np.nan, dtype=np.float64)
        c1[ok] = close[dst[ok]]
        with np.errstate(divide="ignore", invalid="ignore"):
            r[ok] = np.log(c1[ok] / c0[ok])
        r[~np.isfinite(c0) | (c0 <= 0)] = np.nan
        ret[H] = r
        abs_ret[H] = np.abs(r)
        scale[H] = trailing_median_known(abs_ret[H], REF_STEPS, h_bars)
        scale[H] = np.where(scale[H] > 0, scale[H], np.nan)

    classified = {L: classify_events(frame5, L) for L in LOOKBACKS}
    month = np.array([utc_month_key(int(x)) for x in t])
    week = np.array([utc_week_key(int(x)) for x in t])
    year = np.array([utc_year(int(x)) for x in t], dtype=np.int16)
    return {
        "t_ms": t,
        "open_time_ms": frame5["open_time_ms"],
        "available_at_ms": frame5["available_at_ms"],
        "open": frame5["open"],
        "high": high,
        "low": low,
        "close": close,
        "in_development": in_dev,
        "month_key": month,
        "week_key": week,
        "year": year,
        "ret": ret,
        "scale": scale,
        "classified": classified,
        "t_max_inclusive": t_max,
    }


def eligible_index(panel: dict, L: int, H: int) -> np.ndarray:
    cl = panel["classified"][L]
    return np.flatnonzero(
        panel["in_development"]
        & np.isfinite(cl["prior_log_range"])
        & (cl["prior_log_range"] > 0)
        & np.isfinite(panel["ret"][H])
        & np.isfinite(panel["scale"][H])
        & (panel["scale"][H] > 0)
    )


def qualifying_mask(panel: dict, L: int, s: float, kind: str) -> np.ndarray:
    cl = panel["classified"][L]
    if kind == "failed":
        base = cl["failed"] & np.isfinite(cl["overshoot"]) & (cl["overshoot"] >= s)
    elif kind == "success":
        base = cl["success"] & np.isfinite(cl["overshoot_success"]) & (cl["overshoot_success"] >= s)
    else:
        raise H02Error(f"unknown kind {kind}")
    return panel["in_development"] & base


def select_population(panel: dict, L: int, s: float, kind: str) -> np.ndarray:
    mask = qualifying_mask(panel, L, s, kind)
    return apply_refractory(panel["t_ms"], mask)


def outcome_bundle(panel: dict, idx: np.ndarray, L: int, H: int, kind: str) -> dict:
    cl = panel["classified"][L]
    side_field = "side" if kind == "failed" else "side_success"
    side = cl[side_field][idx].astype(np.int8)
    ret = panel["ret"][H][idx]
    scale = panel["scale"][H][idx]
    rev = side.astype(np.float64) * ret
    with np.errstate(divide="ignore", invalid="ignore"):
        norm = rev / scale
    ok = np.isfinite(norm) & np.isfinite(rev) & (scale > 0)
    idx = idx[ok]
    side = side[ok]
    ret = ret[ok]
    scale = scale[ok]
    rev = rev[ok]
    norm = norm[ok]
    t = panel["t_ms"][idx]
    high = panel["high"]
    low = panel["low"]
    close = panel["close"]
    h_bars = H // HTF_MIN
    mfe = np.full(idx.size, np.nan, dtype=np.float64)
    mae = np.full(idx.size, np.nan, dtype=np.float64)
    for k, i in enumerate(idx):
        mfe[k], mae[k] = path_mfe_mae(high, low, close, int(i), h_bars, int(side[k]))
    n_mfe = mfe / scale
    n_mae = mae / scale
    return {
        "idx": idx,
        "t_ms": t,
        "side": side,
        "ret": ret,
        "rev": rev,
        "norm": norm,
        "scale": scale,
        "mfe": mfe,
        "mae": mae,
        "norm_mfe": n_mfe,
        "norm_mae": n_mae,
        "month": panel["month_key"][idx],
        "week": panel["week_key"][idx],
        "year": panel["year"][idx],
    }


def metric_block(b: dict) -> dict:
    n = int(b["norm"].size)
    return {
        "N": n,
        "mean_norm_rev": _mean(b["norm"]),
        "median_norm_rev": _median(b["norm"]),
        "mean_rev_bps": None if _mean(b["rev"]) is None else float(_mean(b["rev"]) * 10_000.0),
        "p_rev_pos": _share_pos(b["rev"]),
        "p25_norm_rev": _pct(b["norm"], 25),
        "p75_norm_rev": _pct(b["norm"], 75),
        "p05_norm_rev": _pct(b["norm"], 5),
        "p95_norm_rev": _pct(b["norm"], 95),
        "mean_norm_mfe": _mean(b["norm_mfe"]),
        "mean_norm_mae": _mean(b["norm_mae"]),
        "p_mfe_gt_mae": _mean((b["mfe"] > b["mae"]).astype(np.float64)) if n else None,
    }


def matched_random_replicates(panel: dict, cand: dict, L: int, H: int, seed: int = SEED_MATCHED, replicates: int = N_MATCHED) -> dict:
    elig = eligible_index(panel, L, H)
    if cand["idx"].size == 0 or elig.size == 0:
        return {
            "replicate_mean_norm": None,
            "replicate_p05_norm": None,
            "replicate_p50_norm": None,
            "replicate_p95_norm": None,
            "replicate_mean_p_pos": None,
            "replicate_p05_p_pos": None,
            "replicate_p95_p_pos": None,
            "replicates": replicates,
            "seed": seed,
        }
    months = panel["month_key"]
    ret = panel["ret"][H]
    scale = panel["scale"][H]
    month_n_u: dict[str, int] = {}
    month_n_d: dict[str, int] = {}
    month_pool: dict[str, np.ndarray] = {}
    for m in np.unique(cand["month"]):
        m = str(m)
        sel = cand["month"] == m
        month_n_u[m] = int(np.sum(sel & (cand["side"] == DIR_UPPER)))
        month_n_d[m] = int(np.sum(sel & (cand["side"] == DIR_LOWER)))
        pool = elig[months[elig] == m]
        month_pool[m] = pool
        need = month_n_u[m] + month_n_d[m]
        if need > pool.size:
            raise H02Error(f"matched-random n={need} exceeds eligible {pool.size} in {m}")
    rng = np.random.default_rng(seed)
    means = []
    pos = []
    for _ in range(replicates):
        norms = []
        revs = []
        for m, pool in month_pool.items():
            n_u = month_n_u[m]
            n_d = month_n_d[m]
            n = n_u + n_d
            if n == 0:
                continue
            picked = rng.choice(pool, size=n, replace=False)
            labels = np.empty(n, dtype=np.int8)
            labels[:n_u] = DIR_UPPER
            labels[n_u:] = DIR_LOWER
            rng.shuffle(labels)
            r = labels.astype(np.float64) * ret[picked]
            sc = scale[picked]
            ok = np.isfinite(r) & (sc > 0) & np.isfinite(sc)
            norms.append(r[ok] / sc[ok])
            revs.append(r[ok])
        if not norms:
            means.append(np.nan)
            pos.append(np.nan)
            continue
        nv = np.concatenate(norms)
        rv = np.concatenate(revs)
        means.append(float(np.mean(nv)) if nv.size else np.nan)
        pos.append(float(np.mean(rv > 0)) if rv.size else np.nan)
    arr = np.asarray(means, dtype=np.float64)
    parr = np.asarray(pos, dtype=np.float64)
    return {
        "replicate_mean_norm": float(np.nanmean(arr)) if np.any(np.isfinite(arr)) else None,
        "replicate_p05_norm": float(np.nanpercentile(arr, 5)) if np.any(np.isfinite(arr)) else None,
        "replicate_p50_norm": float(np.nanpercentile(arr, 50)) if np.any(np.isfinite(arr)) else None,
        "replicate_p95_norm": float(np.nanpercentile(arr, 95)) if np.any(np.isfinite(arr)) else None,
        "replicate_mean_p_pos": float(np.nanmean(parr)) if np.any(np.isfinite(parr)) else None,
        "replicate_p05_p_pos": float(np.nanpercentile(parr, 5)) if np.any(np.isfinite(parr)) else None,
        "replicate_p95_p_pos": float(np.nanpercentile(parr, 95)) if np.any(np.isfinite(parr)) else None,
        "replicates": replicates,
        "seed": seed,
    }


def week_block_bootstrap_minus_matched(
    cand: dict, matched_mean_norm: Optional[float], matched_p_pos: Optional[float],
    replicates: int = N_BOOT, seed: int = SEED_BOOT,
) -> dict:
    empty = {
        "observed_diff_norm": None,
        "ci95_low_norm": None,
        "ci95_high_norm": None,
        "observed_diff_p_pos": None,
        "ci95_low_p_pos": None,
        "ci95_high_p_pos": None,
        "replicates": replicates,
        "seed": seed,
        "block": "UTC_WEEK",
    }
    if cand["idx"].size == 0 or matched_mean_norm is None:
        return empty
    weeks = cand["week"]
    uniq, inv = np.unique(weeks, return_inverse=True)
    n_w = uniq.size
    sum_n = np.zeros(n_w, dtype=np.float64)
    cnt = np.zeros(n_w, dtype=np.float64)
    sum_pos = np.zeros(n_w, dtype=np.float64)
    for i in range(n_w):
        sl = inv == i
        v = cand["norm"][sl]
        sum_n[i] = float(np.sum(v))
        cnt[i] = float(np.sum(sl))
        sum_pos[i] = float(np.sum(cand["rev"][sl] > 0))
    rng = np.random.default_rng(seed)
    d_norm = np.full(replicates, np.nan)
    d_pos = np.full(replicates, np.nan)
    for b in range(replicates):
        draw = rng.integers(0, n_w, size=n_w)
        c = np.sum(cnt[draw])
        if c <= 0:
            continue
        d_norm[b] = (np.sum(sum_n[draw]) / c) - matched_mean_norm
        if matched_p_pos is not None:
            d_pos[b] = (np.sum(sum_pos[draw]) / c) - matched_p_pos
    obs_c = np.sum(cnt)
    obs_norm = float(np.sum(sum_n) / obs_c) - matched_mean_norm if obs_c else None
    obs_pos = (float(np.sum(sum_pos) / obs_c) - matched_p_pos) if (obs_c and matched_p_pos is not None) else None
    return {
        "observed_diff_norm": obs_norm,
        "ci95_low_norm": float(np.nanpercentile(d_norm, 2.5)) if np.any(np.isfinite(d_norm)) else None,
        "ci95_high_norm": float(np.nanpercentile(d_norm, 97.5)) if np.any(np.isfinite(d_norm)) else None,
        "observed_diff_p_pos": obs_pos,
        "ci95_low_p_pos": float(np.nanpercentile(d_pos, 2.5)) if np.any(np.isfinite(d_pos)) else None,
        "ci95_high_p_pos": float(np.nanpercentile(d_pos, 97.5)) if np.any(np.isfinite(d_pos)) else None,
        "replicates": replicates,
        "seed": seed,
        "block": "UTC_WEEK",
    }


def year_breakdown(panel: dict, cand: dict, L: int, H: int) -> dict:
    out = {}
    for y in YEAR_BLOCKS:
        sl = cand["year"] == y
        sub = {k: (v[sl] if isinstance(v, np.ndarray) else v) for k, v in cand.items()}
        n = int(np.sum(sl))
        if n == 0:
            out[str(y)] = {
                "N": 0,
                "mean_norm_rev": None,
                "p_rev_pos": None,
                "matched_mean_norm": None,
                "diff_norm": None,
            }
            continue
        matched = matched_random_replicates(
            panel, sub, L, H,
            seed=int(np.random.SeedSequence([SEED_MATCHED, y]).generate_state(1)[0]),
        )
        mn = _mean(sub["norm"])
        mm = matched["replicate_mean_norm"]
        out[str(y)] = {
            "N": n,
            "mean_norm_rev": mn,
            "p_rev_pos": _share_pos(sub["rev"]),
            "matched_mean_norm": mm,
            "diff_norm": None if (mn is None or mm is None) else float(mn - mm),
        }
    return out


def side_breakdown(cand: dict) -> dict:
    out = {}
    for name, d in (("UPPER", DIR_UPPER), ("LOWER", DIR_LOWER)):
        sl = cand["side"] == d
        out[name] = {
            "N": int(np.sum(sl)),
            "mean_norm_rev": _mean(cand["norm"][sl]),
            "p_rev_pos": _share_pos(cand["rev"][sl]),
            "mean_rev_bps": None if _mean(cand["rev"][sl]) is None else float(_mean(cand["rev"][sl]) * 10_000.0),
        }
    return out


def time_shift_bundle(panel: dict, cand: dict, L: int, H: int) -> dict:
    t0 = int(panel["t_ms"][0])
    shifted_idx = []
    shifted_side = []
    for i, side in zip(cand["idx"], cand["side"]):
        ts = shift_plus_6h_same_utc_day(int(panel["t_ms"][i]))
        j = (ts - t0) // HTF_MS
        if j < 0 or j >= len(panel["t_ms"]):
            continue
        if int(panel["t_ms"][j]) != ts:
            continue
        if ts + MAX_H_MIN * BAR_MS >= DEV_END_MS:
            continue
        if not panel["in_development"][j]:
            continue
        if not np.isfinite(panel["ret"][H][j]):
            continue
        if not (np.isfinite(panel["scale"][H][j]) and panel["scale"][H][j] > 0):
            continue
        cl = panel["classified"][L]
        if not (np.isfinite(cl["prior_log_range"][j]) and cl["prior_log_range"][j] > 0):
            continue
        shifted_idx.append(j)
        shifted_side.append(int(side))
    if not shifted_idx:
        return {"N": 0, "mean_norm_rev": None, "p_rev_pos": None}
    idx = np.asarray(shifted_idx, dtype=np.int64)
    side = np.asarray(shifted_side, dtype=np.int8)
    rev = side.astype(np.float64) * panel["ret"][H][idx]
    norm = rev / panel["scale"][H][idx]
    ok = np.isfinite(norm)
    return {
        "N": int(np.sum(ok)),
        "mean_norm_rev": _mean(norm[ok]),
        "p_rev_pos": _share_pos(rev[ok]),
    }


def evaluate_h02(panel: dict) -> dict:
    cells = []
    t_ms = panel["t_ms"]
    for L in LOOKBACKS:
        for s in THRESHOLDS_S:
            raw_mask = qualifying_mask(panel, L, s, "failed")
            raw_n = int(np.sum(raw_mask))
            kept = apply_refractory(t_ms, raw_mask)
            for H in HORIZONS:
                elig = eligible_index(panel, L, H)
                elig_set = np.zeros(len(t_ms), dtype=bool)
                elig_set[elig] = True
                cand_idx = np.flatnonzero(kept & elig_set)
                cand = outcome_bundle(panel, cand_idx, L, H, "failed")
                succ_kept = apply_refractory(t_ms, qualifying_mask(panel, L, s, "success"))
                succ_idx = np.flatnonzero(succ_kept & elig_set)
                succ = outcome_bundle(panel, succ_idx, L, H, "success")
                matched = matched_random_replicates(panel, cand, L, H)
                boot = week_block_bootstrap_minus_matched(
                    cand, matched["replicate_mean_norm"], matched["replicate_mean_p_pos"],
                )
                metrics = metric_block(cand)
                succ_m = metric_block(succ)
                shift = time_shift_bundle(panel, cand, L, H)
                mn = metrics["mean_norm_rev"]
                mm = matched["replicate_mean_norm"]
                mp = matched["replicate_mean_p_pos"]
                cell = {
                    "L": L,
                    "s": s,
                    "H": H,
                    **metrics,
                    "raw_pre_dedup_N": raw_n,
                    "post_refractory_before_H_filter_N": int(np.sum(kept)),
                    "matched_random": matched,
                    "true_minus_matched_norm": None if (mn is None or mm is None) else float(mn - mm),
                    "true_minus_matched_p_pos": None if (metrics["p_rev_pos"] is None or mp is None) else float(metrics["p_rev_pos"] - mp),
                    "successful_breakout": {
                        **succ_m,
                        "true_minus_success_norm": None if (mn is None or succ_m["mean_norm_rev"] is None) else float(mn - succ_m["mean_norm_rev"]),
                        "upper_share": concentration_from_times(succ["t_ms"], succ["side"]).get("upper_share"),
                        "lower_share": concentration_from_times(succ["t_ms"], succ["side"]).get("lower_share"),
                    },
                    "time_shift": shift,
                    "bootstrap": boot,
                    "year_breakdown": year_breakdown(panel, cand, L, H),
                    "side_breakdown": side_breakdown(cand),
                    "concentration": concentration_from_times(cand["t_ms"], cand["side"]),
                }
                cells.append(cell)
    forbidden_months = []
    for c in cells:
        for m in c["concentration"]["by_month"].keys():
            if m.startswith("2025") or m.startswith("2026"):
                forbidden_months.append(m)
    if forbidden_months:
        raise ValidationWindowForbidden(f"result months include forbidden windows: {forbidden_months}")
    return {
        "hypothesis_id": "H02_FAILED_BREAKOUT_MEAN_REVERSION",
        "dataset_id": DATASET_ID,
        "snapshot_id": REQUIRED_SNAPSHOT,
        "search_surface": {
            "lookbacks": list(LOOKBACKS),
            "overshoot_thresholds": list(THRESHOLDS_S),
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
    }
