#!/usr/bin/env python3
"""Single frozen E1-RUN-001 holdout outcome evaluation.

This script is intentionally one-shot.  It may run only from the already-frozen
outcome-free holdout ablation inventory and only after the strengthened
TIMESTAMPS-ONLY coverage preflight says that BOTH primary +4h paths and the
frozen FULL-family +6h same-day circular time-shift +4h paths have arrived.

The evaluator opens holdout OHLC once and computes, in the same process before
anything outcome-derived is printed:
- every preregistered FULL / ablation / simple-baseline population;
- nested FULL / ABLATION_ALL / ADDED_ONLY objects;
- per-population deterministic matched-random controls;
- same-T direction inversion for FULL families;
- fixed +6h same-UTC-day circular time-shift for FULL families;
- delay stress 0/+60/+120 seconds (computed for every variant prospectively so
  no outcome-driven second read is needed);
- total friction stress 0/5/10/20 bps;
- 30m/60m clustering, per-UTC-day concentration and fixed-seed UTC-day block
  bootstrap intervals.

No detector thresholds, candidate definitions, directions, horizons, control
offsets, delays, costs, matching rules or verdict criteria are selected here.
The script does NOT auto-assign qualitative final verdicts because the frozen
SURVIVES/SIMPLIFY/DEMOTE/KILL/INCONCLUSIVE rules are intentionally qualitative.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import asyncpg

from analytics.forecasting_v2.alignment import selected_bucket
from scripts.research.v2_e1_development_ablation_inventory import (
    CB_FULL,
    CB_NO_TAKER,
    CB_ORDINARY,
    CB_SIMPLE,
    FB_DUMB,
    FB_FULL,
    FB_NO_CONTEXT,
    TP_FULL,
    TP_NO_1H,
    TP_NO_4H,
    TP_NO_CONTEXT,
    VARIANTS,
)
from scripts.research.v2_e1_development_outcomes import (
    HORIZONS,
    RAW_BARS_SQL,
    REFERENCE_5M_SQL,
    REFERENCE_EXCHANGE,
    STUDY,
    _finite_float,
    _first_extreme,
    _future_metric,
    _mean,
    _median,
    _parse_utc,
)

UTC = timezone.utc
HOLDOUT_START = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
HOLDOUT_END = datetime(2026, 8, 25, 17, 20, tzinfo=UTC)
MAX_HORIZON_MINUTES = 240
TIME_SHIFT_MINUTES = 360
MATCH_SEED = 20260825
BOOTSTRAP_SEED = 20260825
BOOTSTRAP_RESAMPLES = 10_000
FRICTION_BPS = (0, 5, 10, 20)
DELAYS_SECONDS = (0, 60, 120)
FULL_VARIANTS = (TP_FULL, CB_FULL, FB_FULL)
EXPECTED_FULL_COUNTS = {TP_FULL: 105, CB_FULL: 17, FB_FULL: 19}

VARIANT_FAMILY = {
    TP_FULL: "TREND_PULLBACK",
    TP_NO_4H: "TREND_PULLBACK",
    TP_NO_1H: "TREND_PULLBACK",
    TP_NO_CONTEXT: "TREND_PULLBACK",
    CB_FULL: "COMPRESSION_BREAKOUT",
    CB_NO_TAKER: "COMPRESSION_BREAKOUT",
    CB_SIMPLE: "COMPRESSION_BREAKOUT",
    CB_ORDINARY: "COMPRESSION_BREAKOUT",
    FB_FULL: "CONFIRMED_BREAKOUT",
    FB_NO_CONTEXT: "CONFIRMED_BREAKOUT",
    FB_DUMB: "CONFIRMED_BREAKOUT",
}
FULL_BY_FAMILY = {
    "TREND_PULLBACK": TP_FULL,
    "COMPRESSION_BREAKOUT": CB_FULL,
    "CONFIRMED_BREAKOUT": FB_FULL,
}
NESTED = {
    TP_NO_4H: TP_FULL,
    TP_NO_1H: TP_FULL,
    TP_NO_CONTEXT: TP_FULL,
    CB_NO_TAKER: CB_FULL,
    CB_SIMPLE: CB_FULL,
    FB_NO_CONTEXT: FB_FULL,
}
MATCH_EVIDENCE_VARIANTS = tuple(v for v in VARIANTS if v != FB_DUMB)


def _key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row["T"]), str(row["direction"])


def _opposite(direction: str) -> str:
    if direction == "LONG":
        return "SHORT"
    if direction == "SHORT":
        return "LONG"
    raise RuntimeError(f"unknown direction {direction!r}")


def _directional_return(direction: str, p0: float, p1: float) -> float:
    if direction == "LONG":
        return p1 / p0 - 1.0
    if direction == "SHORT":
        return (p0 - p1) / p0
    raise RuntimeError(f"unknown direction {direction!r}")


def _same_day_circular_shift(T: datetime) -> datetime:
    day_start = T.replace(hour=0, minute=0, second=0, microsecond=0)
    shifted_offset = ((T - day_start) + timedelta(minutes=TIME_SHIFT_MINUTES)) % timedelta(days=1)
    shifted = day_start + shifted_offset
    if shifted.date() != T.date() or shifted.minute % 5 or shifted.second or shifted.microsecond:
        raise RuntimeError(f"invalid frozen time shift for {T.isoformat()}")
    return shifted


def _percentile(sorted_values: list[float], q: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[lo]
    weight = pos - lo
    return sorted_values[lo] * (1.0 - weight) + sorted_values[hi] * weight


def _cluster_count(rows: Iterable[Mapping[str, Any]], gap_minutes: int) -> int:
    times = sorted({_parse_utc(str(r["T"])) for r in rows})
    if not times:
        return 0
    clusters = 1
    max_gap = timedelta(minutes=gap_minutes)
    for prev, cur in zip(times, times[1:]):
        if cur - prev > max_gap:
            clusters += 1
    return clusters


def _metric_values(rows: list[dict[str, Any]], minutes: int) -> tuple[list[dict[str, Any]], list[float]]:
    complete = []
    returns = []
    for row in rows:
        metric = row["future"][str(minutes)]
        value = metric.get("terminal_directional_return")
        if metric.get("path_complete") is True and value is not None:
            complete.append(metric)
            returns.append(float(value))
    return complete, returns


def _day_bootstrap(rows: list[dict[str, Any]], minutes: int) -> dict[str, Any]:
    by_day: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        metric = row["future"][str(minutes)]
        value = metric.get("terminal_directional_return")
        if metric.get("path_complete") is True and value is not None:
            day = _parse_utc(str(row["T"])).date().isoformat()
            by_day[day].append(float(value))
    days = sorted(by_day)
    if not days:
        return {
            "seed": BOOTSTRAP_SEED,
            "resamples": BOOTSTRAP_RESAMPLES,
            "block": "UTC_DAY",
            "n_days": 0,
            "mean": None,
            "ci_95_percentile": [None, None],
        }
    observed = [v for day in days for v in by_day[day]]
    rng = random.Random(BOOTSTRAP_SEED)
    boot: list[float] = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sampled_days = [rng.choice(days) for _ in days]
        sample = [v for day in sampled_days for v in by_day[day]]
        boot.append(statistics.fmean(sample))
    boot.sort()
    return {
        "seed": BOOTSTRAP_SEED,
        "resamples": BOOTSTRAP_RESAMPLES,
        "block": "UTC_DAY",
        "n_days": len(days),
        "mean": statistics.fmean(observed),
        "ci_95_percentile": [_percentile(boot, 0.025), _percentile(boot, 0.975)],
    }


def _day_table(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_day[_parse_utc(str(row["T"])).date().isoformat()].append(row)
    total = len(rows)
    table: dict[str, Any] = {}
    for day in sorted(by_day):
        dr = by_day[day]
        entry: dict[str, Any] = {
            "n": len(dr),
            "LONG": sum(1 for r in dr if r["direction"] == "LONG"),
            "SHORT": sum(1 for r in dr if r["direction"] == "SHORT"),
            "share_of_population": len(dr) / total if total else None,
            "future": {},
        }
        for minutes in HORIZONS:
            _, values = _metric_values(dr, minutes)
            entry["future"][str(minutes)] = {
                "n_complete": len(values),
                "mean_directional_return": _mean(values),
                "median_directional_return": _median(values),
                "positive_share": (sum(v > 0.0 for v in values) / len(values) if values else None),
            }
        table[day] = entry
    return table


def _summarize_population(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "raw_n": len(rows),
        "direction_n": {
            "LONG": sum(1 for r in rows if r["direction"] == "LONG"),
            "SHORT": sum(1 for r in rows if r["direction"] == "SHORT"),
        },
        "reference_usable_n": sum(1 for r in rows if r.get("reference_usable") is True),
        "cluster_n": {
            "30m_gap": _cluster_count(rows, 30),
            "60m_gap": _cluster_count(rows, 60),
        },
        "utc_day_count": len({_parse_utc(str(r["T"])).date() for r in rows}),
        "utc_day_table": _day_table(rows),
        "future": {},
        "friction_stress": {},
        "utc_day_block_bootstrap": {},
    }
    if rows:
        counts = Counter(_parse_utc(str(r["T"])).date().isoformat() for r in rows)
        largest_day, largest_n = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
        summary["largest_utc_day"] = {
            "day": largest_day,
            "n": largest_n,
            "share": largest_n / len(rows),
        }
    else:
        summary["largest_utc_day"] = {"day": None, "n": 0, "share": None}

    for minutes in HORIZONS:
        complete, returns = _metric_values(rows, minutes)
        mfes = [float(m["mfe"]) for m in complete if m.get("mfe") is not None]
        maes = [float(m["mae"]) for m in complete if m.get("mae") is not None]
        summary["future"][str(minutes)] = {
            "n_complete": len(complete),
            "n_incomplete": len(rows) - len(complete),
            "path_complete_share": len(complete) / len(rows) if rows else None,
            "mean_directional_return": _mean(returns),
            "median_directional_return": _median(returns),
            "positive_share": (sum(v > 0.0 for v in returns) / len(returns) if returns else None),
            "median_mfe": _median(mfes),
            "median_mae": _median(maes),
        }
        summary["friction_stress"][str(minutes)] = {}
        for bps in FRICTION_BPS:
            net = [v - bps / 10_000.0 for v in returns]
            summary["friction_stress"][str(minutes)][str(bps)] = {
                "total_round_trip_bps": bps,
                "n": len(net),
                "mean_net_directional_return": _mean(net),
                "median_net_directional_return": _median(net),
                "positive_share_net": (sum(v > 0.0 for v in net) / len(net) if net else None),
            }
        summary["utc_day_block_bootstrap"][str(minutes)] = _day_bootstrap(rows, minutes)
    return summary


def _load_inventory(path: Path, calculation_version: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("study") != STUDY:
        raise RuntimeError("unexpected inventory study")
    if payload.get("kind") != "HOLDOUT_ABLATION_INVENTORY_NO_OUTCOMES":
        raise RuntimeError("unexpected inventory kind")
    if payload.get("full_population_reproduced") is not True:
        raise RuntimeError("FULL holdout population not reproduced")
    if payload.get("outcomes_included") is not False:
        raise RuntimeError("source inventory already contains outcomes")
    if payload.get("holdout_outcomes_opened") is not False:
        raise RuntimeError("source inventory says holdout opened")
    if payload.get("holdout_market_rows_read") is not False:
        raise RuntimeError("source inventory says holdout market rows read")
    if payload.get("calculation_version") != calculation_version:
        raise RuntimeError("inventory calculation_version mismatch")
    window = payload.get("holdout_window") or {}
    if window.get("start_inclusive") != HOLDOUT_START.isoformat():
        raise RuntimeError("unexpected holdout start")
    if window.get("end_exclusive") != HOLDOUT_END.isoformat():
        raise RuntimeError("unexpected holdout end")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("inventory rows missing")
    return payload, rows


def _validate_inventory(rows: list[dict[str, Any]]) -> dict[str, set[tuple[str, str]]]:
    keys_by_variant: dict[str, set[tuple[str, str]]] = {v: set() for v in VARIANTS}
    counts: Counter[str] = Counter()
    for row in rows:
        variant = row.get("variant")
        direction = row.get("direction")
        if variant not in VARIANTS:
            raise RuntimeError(f"unknown variant {variant!r}")
        if direction not in ("LONG", "SHORT"):
            raise RuntimeError(f"unknown direction {direction!r}")
        T = _parse_utc(str(row["T"]))
        if not (HOLDOUT_START <= T < HOLDOUT_END):
            raise RuntimeError(f"row outside frozen holdout: {T.isoformat()}")
        k = _key(row)
        if k in keys_by_variant[variant]:
            raise RuntimeError(f"duplicate variant identity: {variant} {k}")
        keys_by_variant[variant].add(k)
        counts[variant] += 1
    for variant, expected in EXPECTED_FULL_COUNTS.items():
        if counts[variant] != expected:
            raise RuntimeError(
                f"FULL reproducibility failure: {variant} expected {expected}, got {counts[variant]}")
    if keys_by_variant[FB_NO_CONTEXT] != keys_by_variant[FB_DUMB]:
        raise RuntimeError("FB_NO_CONTEXT and FB_DUMB alias populations diverged")
    for ablation, full in NESTED.items():
        if not keys_by_variant[full].issubset(keys_by_variant[ablation]):
            raise RuntimeError(f"nested invariant failed: {full} not subset of {ablation}")
    return keys_by_variant


def _load_preflight(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("study") != STUDY:
        raise RuntimeError("unexpected preflight study")
    if payload.get("kind") != "HOLDOUT_OUTCOME_COVERAGE_PREFLIGHT_TIMESTAMPS_ONLY":
        raise RuntimeError("unexpected preflight kind")
    if payload.get("prices_read") is not False or payload.get("outcomes_opened") is not False:
        raise RuntimeError("preflight is not outcome-free")
    if payload.get("holdout_market_price_rows_read") is not False:
        raise RuntimeError("preflight says market price rows were read")
    if payload.get("ready_for_single_holdout_outcome_open") is not True:
        raise RuntimeError("coverage preflight is not READY")
    shift = payload.get("full_time_shift_control") or {}
    if shift.get("offset_minutes") != TIME_SHIFT_MINUTES:
        raise RuntimeError("preflight does not cover frozen +6h time shift")
    if shift.get("circular_within_same_utc_day") is not True:
        raise RuntimeError("preflight time-shift semantics mismatch")
    if shift.get("observed_through_required_last_bar") is not True:
        raise RuntimeError("time-shift outcome horizon not fully observed")
    primary = payload.get("primary_outcome_coverage") or {}
    if primary.get("observed_through_required_last_bar") is not True:
        raise RuntimeError("primary outcome horizon not fully observed")
    return payload


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _reserve_open_marker(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, b"E1-RUN-001 holdout OHLC read authorized and started\n")
        os.fsync(fd)
    finally:
        os.close(fd)


def _grid_rows(
    bar_map: Mapping[datetime, Mapping[str, Any]], start: datetime, minutes: int
) -> tuple[list[Mapping[str, Any]], list[datetime]]:
    rows: list[Mapping[str, Any]] = []
    missing: list[datetime] = []
    for i in range(minutes):
        ts = start + timedelta(minutes=i)
        row = bar_map.get(ts)
        if row is None:
            missing.append(ts)
        else:
            rows.append(row)
    return rows, missing


def _delay_metric(
    *, direction: str, T: datetime, delay_seconds: int, horizon_minutes: int,
    p_t: float, bar_map: Mapping[datetime, Mapping[str, Any]],
) -> dict[str, Any]:
    if delay_seconds not in DELAYS_SECONDS:
        raise RuntimeError("unregistered delay")
    delay_minutes = delay_seconds // 60
    if delay_seconds == 0:
        return _future_metric(
            direction=direction, T=T, minutes=horizon_minutes, p_t=p_t, bar_map=bar_map)

    entry_bar_ts = T + timedelta(minutes=delay_minutes - 1)
    entry_bar = bar_map.get(entry_bar_ts)
    path_start = T + timedelta(minutes=delay_minutes)
    path_minutes = horizon_minutes - delay_minutes
    rows, missing = _grid_rows(bar_map, path_start, path_minutes)
    complete = entry_bar is not None and not missing and len(rows) == path_minutes and path_minutes > 0
    if not complete:
        return {
            "minutes": horizon_minutes,
            "delay_seconds": delay_seconds,
            "path_complete": False,
            "bars_expected_after_entry": max(path_minutes, 0),
            "bars_present_after_entry": len(rows),
            "missing_minutes": len(missing) + (1 if entry_bar is None else 0),
            "terminal_directional_return": None,
            "mfe": None,
            "mae": None,
        }

    entry = _finite_float(entry_bar["close"], "delayed entry close")
    if entry <= 0.0:
        raise RuntimeError("delayed entry must be positive")
    terminal = _finite_float(rows[-1]["close"], "delayed terminal close")
    if direction == "LONG":
        mfe_row = _first_extreme(rows, "high", "max")
        mae_row = _first_extreme(rows, "low", "min")
        mfe = _finite_float(mfe_row["high"], "high") / entry - 1.0
        mae = _finite_float(mae_row["low"], "low") / entry - 1.0
    else:
        mfe_row = _first_extreme(rows, "low", "min")
        mae_row = _first_extreme(rows, "high", "max")
        mfe = (entry - _finite_float(mfe_row["low"], "low")) / entry
        mae = (entry - _finite_float(mae_row["high"], "high")) / entry
    return {
        "minutes": horizon_minutes,
        "delay_seconds": delay_seconds,
        "path_complete": True,
        "bars_expected_after_entry": path_minutes,
        "bars_present_after_entry": path_minutes,
        "missing_minutes": 0,
        "entry_bar_start": entry_bar_ts.isoformat(),
        "entry_price": entry,
        "terminal_directional_return": _directional_return(direction, entry, terminal),
        "mfe": mfe,
        "mae": mae,
    }


def _delay_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for delay in DELAYS_SECONDS:
        result[str(delay)] = {}
        for minutes in HORIZONS:
            metrics = [r["delay"][str(delay)][str(minutes)] for r in rows]
            complete = [m for m in metrics if m.get("path_complete") is True and m.get("terminal_directional_return") is not None]
            returns = [float(m["terminal_directional_return"]) for m in complete]
            result[str(delay)][str(minutes)] = {
                "n_complete": len(complete),
                "n_incomplete": len(rows) - len(complete),
                "mean_directional_return": _mean(returns),
                "median_directional_return": _median(returns),
                "positive_share": (sum(v > 0.0 for v in returns) / len(returns) if returns else None),
                "median_mfe": _median([float(m["mfe"]) for m in complete if m.get("mfe") is not None]),
                "median_mae": _median([float(m["mae"]) for m in complete if m.get("mae") is not None]),
            }
    return result


def _comparison_delta(actual: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for minutes in HORIZONS:
        a = actual["future"][str(minutes)].get("mean_directional_return")
        c = control["future"][str(minutes)].get("mean_directional_return")
        result[str(minutes)] = {
            "actual_mean": a,
            "control_mean": c,
            "actual_minus_control_mean": (a - c if a is not None and c is not None else None),
        }
    return result


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    if args.output.exists():
        raise RuntimeError(f"final output already exists: {args.output}; refusing overwrite")
    marker = args.open_marker or args.output.with_name(args.output.name + ".OPENED")
    if marker.exists():
        raise RuntimeError(f"holdout open marker already exists: {marker}; refusing second run")

    source, inventory_rows = _load_inventory(args.input, args.calculation_version)
    keys_by_variant = _validate_inventory(inventory_rows)
    preflight = _load_preflight(args.preflight)

    raw_window = preflight.get("required_raw_window") or {}
    raw_start = _parse_utc(str(raw_window["start_inclusive"]))
    raw_end = _parse_utc(str(raw_window["end_exclusive"]))
    required_last = _parse_utc(str(raw_window["required_last_bar_start"]))
    if raw_end - timedelta(minutes=1) != required_last:
        raise RuntimeError("preflight raw-window endpoint mismatch")

    full_rows = [r for r in inventory_rows if r["variant"] in FULL_VARIANTS]
    shifted_times = [_same_day_circular_shift(_parse_utc(str(r["T"]))) for r in full_rows]
    max_original = max(_parse_utc(str(r["T"])) for r in inventory_rows)
    max_shifted = max(shifted_times)
    independently_required_end = max(max_original, max_shifted) + timedelta(minutes=MAX_HORIZON_MINUTES)
    if raw_end < independently_required_end:
        raise RuntimeError("preflight window does not cover frozen primary/time-shift horizons")

    # DB authentication/connectivity failure must not consume the one-shot marker.
    conn = await asyncpg.connect(args.dsn)
    try:
        _reserve_open_marker(marker)
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            raw_records = await conn.fetch(
                RAW_BARS_SQL, REFERENCE_EXCHANGE, args.symbol, raw_start, raw_end)

            bar_map: dict[datetime, dict[str, Any]] = {
                rec["ts"]: {
                    "ts": rec["ts"], "open": rec["open"], "high": rec["high"],
                    "low": rec["low"], "close": rec["close"],
                }
                for rec in raw_records
            }
            if not bar_map:
                raise RuntimeError("no raw bars returned")
            if max(bar_map) < required_last:
                raise RuntimeError("raw DB snapshot ends before preflight-required last bar")

            # Reference vectors are required for candidate/control entry validity.
            # Random controls stay on the frozen holdout decision grid; shifted
            # FULL controls may land later on the same UTC day.
            min_eval_t = min(HOLDOUT_START, min(shifted_times))
            max_eval_t = max(HOLDOUT_END - timedelta(minutes=5), max(shifted_times))
            first_ref_bucket = selected_bucket("5m", min_eval_t)
            last_ref_bucket = selected_bucket("5m", max_eval_t)
            ref_records = await conn.fetch(
                REFERENCE_5M_SQL,
                REFERENCE_EXCHANGE, args.symbol, args.market_type,
                args.calculation_version, first_ref_bucket, last_ref_bucket,
            )
            ref_map = {rec["bucket_ts"]: dict(rec) for rec in ref_records}

            ref_cache: dict[datetime, tuple[bool, str | None, float | None]] = {}

            def reference_at(T: datetime) -> tuple[bool, str | None, float | None]:
                cached = ref_cache.get(T)
                if cached is not None:
                    return cached
                b5 = selected_bucket("5m", T)
                ref = ref_map.get(b5)
                usable = False
                reason: str | None = None
                p_t: float | None = None
                if ref is None:
                    reason = "MISSING_REFERENCE_VECTOR"
                else:
                    if (
                        ref.get("exchange") != REFERENCE_EXCHANGE
                        or ref.get("symbol") != args.symbol
                        or ref.get("market_type") != args.market_type
                        or ref.get("timeframe") != "5m"
                        or ref.get("bucket_ts") != b5
                        or ref.get("calculation_version") != args.calculation_version
                        or ref.get("feature_schema_version") != args.feature_schema_version
                    ):
                        raise RuntimeError(f"reference identity mismatch at T={T.isoformat()}")
                    gate = (
                        ref.get("is_usable") is True
                        and ref.get("has_gap") is False
                        and ref.get("bars_present") == ref.get("bars_expected")
                        and ref.get("close_price") is not None
                    )
                    if not gate:
                        reason = "REFERENCE_GATE_FAILED"
                    else:
                        p_t = _finite_float(ref["close_price"], "reference close_price")
                        raw_endpoint = bar_map.get(T - timedelta(minutes=1))
                        if raw_endpoint is None:
                            reason = "MISSING_RAW_REFERENCE_ENDPOINT"
                            p_t = None
                        else:
                            raw_close = _finite_float(raw_endpoint["close"], "raw P_T close")
                            if raw_close != p_t:
                                raise RuntimeError(
                                    f"reference/raw close mismatch at T={T.isoformat()}: vector={p_t!r} raw={raw_close!r}")
                            usable = True
                result = (usable, reason, p_t)
                ref_cache[T] = result
                return result

            def evaluate_point(T: datetime, direction: str, **identity: Any) -> dict[str, Any]:
                usable, reason, p_t = reference_at(T)
                out: dict[str, Any] = {
                    "T": T.isoformat(),
                    "direction": direction,
                    **identity,
                    "reference_usable": usable,
                    "reference_unavailable_reason": reason,
                    "P_T": p_t,
                    "future": {},
                }
                if usable and p_t is not None:
                    for minutes in HORIZONS:
                        out["future"][str(minutes)] = _future_metric(
                            direction=direction, T=T, minutes=minutes, p_t=p_t, bar_map=bar_map)
                else:
                    for minutes in HORIZONS:
                        out["future"][str(minutes)] = {
                            "minutes": minutes,
                            "path_complete": False,
                            "bars_expected": minutes,
                            "bars_present": None,
                            "missing_minutes": None,
                            "terminal_directional_return": None,
                            "mfe": None,
                            "mae": None,
                            "time_to_mfe_bar_start_minutes": None,
                            "time_to_mae_bar_start_minutes": None,
                        }
                return out

            # Primary candidate/ablation/simple-baseline outcomes.
            primary_rows: list[dict[str, Any]] = []
            for source_row in sorted(inventory_rows, key=lambda r: (r["variant"], r["T"], r["direction"])):
                T = _parse_utc(str(source_row["T"]))
                variant = str(source_row["variant"])
                direction = str(source_row["direction"])
                out = evaluate_point(
                    T, direction, variant=variant, family=VARIANT_FAMILY[variant], source="PRIMARY")
                out["delay"] = {}
                if out["reference_usable"] and out["P_T"] is not None:
                    p_t = float(out["P_T"])
                    for delay in DELAYS_SECONDS:
                        out["delay"][str(delay)] = {}
                        for minutes in HORIZONS:
                            out["delay"][str(delay)][str(minutes)] = _delay_metric(
                                direction=direction, T=T, delay_seconds=delay,
                                horizon_minutes=minutes, p_t=p_t, bar_map=bar_map)
                else:
                    for delay in DELAYS_SECONDS:
                        out["delay"][str(delay)] = {}
                        for minutes in HORIZONS:
                            out["delay"][str(delay)][str(minutes)] = {
                                "minutes": minutes, "delay_seconds": delay,
                                "path_complete": False,
                                "terminal_directional_return": None,
                                "mfe": None, "mae": None,
                            }
                primary_rows.append(out)

            by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in primary_rows:
                by_variant[row["variant"]].append(row)
            primary_summary = {v: _summarize_population(by_variant[v]) for v in VARIANTS}
            delay_summary = {v: _delay_summary(by_variant[v]) for v in VARIANTS}

            nested: dict[str, Any] = {}
            for ablation, full in NESTED.items():
                full_keys = keys_by_variant[full]
                added_rows = [r for r in by_variant[ablation] if _key(r) not in full_keys]
                nested[ablation] = {
                    "full_variant": full,
                    "FULL": primary_summary[full],
                    "ABLATION_ALL": primary_summary[ablation],
                    "ADDED_ONLY": _summarize_population(added_rows),
                    "identity_counts": {
                        "full": len(full_keys),
                        "ablation_all": len(keys_by_variant[ablation]),
                        "added_only": len(keys_by_variant[ablation] - full_keys),
                    },
                }

            # Same-T inversion: negative control for FULL only.
            inversion_rows_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for family, full_variant in FULL_BY_FAMILY.items():
                for row in by_variant[full_variant]:
                    T = _parse_utc(row["T"])
                    inversion_rows_by_family[family].append(
                        evaluate_point(
                            T, _opposite(row["direction"]), family=family,
                            full_variant=full_variant, source="SAME_T_DIRECTION_INVERSION",
                            original_direction=row["direction"],
                        )
                    )
            inversion_summary = {
                family: {
                    "summary": _summarize_population(rows_),
                    "FULL_minus_inversion": _comparison_delta(
                        primary_summary[FULL_BY_FAMILY[family]], _summarize_population(rows_)),
                }
                for family, rows_ in inversion_rows_by_family.items()
            }

            # Fixed +6h same-day circular time shift: negative timing control.
            shift_rows_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
            shift_overlap: dict[str, Any] = {}
            for family, full_variant in FULL_BY_FAMILY.items():
                original_times = {_parse_utc(r["T"]) for r in by_variant[full_variant]}
                collisions = 0
                for row in by_variant[full_variant]:
                    original_T = _parse_utc(row["T"])
                    shifted_T = _same_day_circular_shift(original_T)
                    if shifted_T in original_times:
                        collisions += 1
                    shift_rows_by_family[family].append(
                        evaluate_point(
                            shifted_T, row["direction"], family=family,
                            full_variant=full_variant, source="PLUS_6H_SAME_DAY_CIRCULAR_SHIFT",
                            original_T=original_T.isoformat(),
                        )
                    )
                n = len(by_variant[full_variant])
                shift_overlap[family] = {
                    "candidate_time_collisions": collisions,
                    "collision_share": collisions / n if n else None,
                    "offset_minutes": TIME_SHIFT_MINUTES,
                }
            shift_summary = {
                family: {
                    "summary": _summarize_population(rows_),
                    "overlap": shift_overlap[family],
                    "FULL_minus_time_shift": _comparison_delta(
                        primary_summary[FULL_BY_FAMILY[family]], _summarize_population(rows_)),
                }
                for family, rows_ in shift_rows_by_family.items()
            }

            # Precompute legal matched-random boundaries: frozen holdout 5m grid,
            # reference usable and complete through the longest +4h path.
            legal_by_day: dict[str, list[datetime]] = defaultdict(list)
            T = HOLDOUT_START
            while T < HOLDOUT_END:
                usable, _, p_t = reference_at(T)
                legal = False
                if usable and p_t is not None:
                    m = _future_metric(
                        direction="LONG", T=T, minutes=MAX_HORIZON_MINUTES,
                        p_t=p_t, bar_map=bar_map)
                    legal = m.get("path_complete") is True
                if legal:
                    legal_by_day[T.date().isoformat()].append(T)
                T += timedelta(minutes=5)

            rng = random.Random(MATCH_SEED)
            matched_random: dict[str, Any] = {}
            for variant in sorted(MATCH_EVIDENCE_VARIANTS):
                candidates = sorted(by_variant[variant], key=lambda r: (r["T"], r["direction"]))
                own_times = {_parse_utc(r["T"]) for r in candidates}
                by_day_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
                for row in candidates:
                    by_day_candidates[_parse_utc(row["T"]).date().isoformat()].append(row)
                control_rows: list[dict[str, Any]] = []
                unmatched: list[dict[str, Any]] = []
                strata: dict[str, Any] = {}
                for day in sorted(by_day_candidates):
                    cr = sorted(by_day_candidates[day], key=lambda r: (r["T"], r["direction"]))
                    pool = [t for t in legal_by_day.get(day, []) if t not in own_times]
                    pool = sorted(pool)
                    rng.shuffle(pool)
                    take = min(len(cr), len(pool))
                    chosen = pool[:take]
                    for source_row, random_T in zip(cr[:take], chosen):
                        control_rows.append(
                            evaluate_point(
                                random_T, source_row["direction"], variant=variant,
                                family=VARIANT_FAMILY[variant], source="MATCHED_RANDOM",
                                matched_from_T=source_row["T"],
                            )
                        )
                    for source_row in cr[take:]:
                        unmatched.append({
                            "T": source_row["T"],
                            "direction": source_row["direction"],
                            "day": day,
                            "reason": "INSUFFICIENT_LEGAL_UNUSED_BOUNDARIES",
                        })
                    strata[day] = {
                        "candidate_n": len(cr),
                        "legal_pool_after_own_time_exclusion": len(pool),
                        "matched_n": take,
                        "unmatched_n": len(cr) - take,
                    }
                control_summary = _summarize_population(control_rows)
                matched_random[variant] = {
                    "seed": MATCH_SEED,
                    "sampling": "without_replacement_where_feasible",
                    "match_strata": "variant/family + UTC day; preserve candidate direction",
                    "own_candidate_times_excluded": True,
                    "rows": control_rows,
                    "unmatched": unmatched,
                    "strata": strata,
                    "summary": control_summary,
                    "ACTUAL_minus_matched_random": _comparison_delta(primary_summary[variant], control_summary),
                }
            matched_random[FB_DUMB] = {
                "alias_of": FB_NO_CONTEXT,
                "independent_evidence": False,
                "note": "FB_DUMB_48H_LEVEL_BREAKOUT is the exact Stage-5 alias of FB_NO_CONTEXT.",
            }

    finally:
        await conn.close()

    return {
        "study": STUDY,
        "kind": "FINAL_HOLDOUT_EVALUATION_SINGLE_OPEN",
        "protocol": "docs/e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md",
        "coverage_clarification": "docs/e1/E1_RUN_001_COVERAGE_PREFLIGHT_CLARIFICATION.md",
        "source_holdout_inventory": str(args.input),
        "source_preflight": str(args.preflight),
        "source_research_head_sha": source.get("research_head_sha"),
        "symbol": args.symbol,
        "market_type": args.market_type,
        "calculation_version": args.calculation_version,
        "feature_schema_version": args.feature_schema_version,
        "holdout_window": {
            "start_inclusive": HOLDOUT_START.isoformat(),
            "end_exclusive": HOLDOUT_END.isoformat(),
        },
        "db_market_read_window": {
            "start_inclusive": raw_start.isoformat(),
            "end_exclusive": raw_end.isoformat(),
        },
        "holdout_outcomes_opened": True,
        "holdout_market_rows_read": True,
        "prices_read": True,
        "historical_gap_minutes_preflight": preflight.get("historical_gap_minutes"),
        "historical_gap_sample_preflight": preflight.get("historical_gap_sample"),
        "registered_horizons_minutes": list(HORIZONS),
        "registered_delays_seconds": list(DELAYS_SECONDS),
        "registered_total_round_trip_friction_bps": list(FRICTION_BPS),
        "registered_time_shift_minutes": TIME_SHIFT_MINUTES,
        "matched_random_seed": MATCH_SEED,
        "bootstrap": {
            "seed": BOOTSTRAP_SEED,
            "resamples": BOOTSTRAP_RESAMPLES,
            "block": "UTC_DAY",
            "interval": "95% percentile",
        },
        "denominator": {
            "inventory_rows": len(inventory_rows),
            "full_counts": {v: len(by_variant[v]) for v in FULL_VARIANTS},
            "variant_counts": {v: len(by_variant[v]) for v in VARIANTS},
        },
        "primary": {
            "rows": primary_rows,
            "summary_by_variant": primary_summary,
            "nested_ablation_comparisons": nested,
            "fb_alias": {
                "alias": FB_DUMB,
                "canonical_evidence_item": FB_NO_CONTEXT,
                "exact_population_identity": True,
                "independent_evidence": False,
            },
        },
        "matched_random_controls": matched_random,
        "full_direction_inversion_controls": {
            "rows_by_family": inversion_rows_by_family,
            "summary_by_family": inversion_summary,
        },
        "full_plus_6h_time_shift_controls": {
            "rows_by_family": shift_rows_by_family,
            "summary_by_family": shift_summary,
        },
        "delay_stress_by_variant": delay_summary,
        "verdicts": {
            "auto_assigned": False,
            "allowed_vocabulary": [
                "SURVIVES", "SIMPLIFY", "DEMOTE_TO_BASELINE", "KILL", "INCONCLUSIVE_SAMPLE"
            ],
            "note": "Apply frozen qualitative verdict logic only after this complete artifact is written.",
        },
    }


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Single frozen E1 final holdout evaluator")
    p.add_argument("--dsn", required=True)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--preflight", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--open-marker", type=Path, default=None)
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--market-type", default="perp")
    p.add_argument("--calculation-version", required=True)
    p.add_argument("--feature-schema-version", type=int, default=1)
    return p


def main() -> int:
    args = _parser().parse_args()
    payload = asyncio.run(_run(args))
    _write_json_atomic(args.output, payload)
    # Do not print outcome metrics before the entire frozen evaluation and every
    # control has completed and the immutable artifact has been written.
    print(json.dumps({
        "study": payload["study"],
        "kind": payload["kind"],
        "artifact": str(args.output),
        "holdout_outcomes_opened": payload["holdout_outcomes_opened"],
        "holdout_market_rows_read": payload["holdout_market_rows_read"],
        "metrics_printed_to_stdout": False,
        "inventory_rows": payload["denominator"]["inventory_rows"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
