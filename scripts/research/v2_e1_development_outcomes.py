#!/usr/bin/env python3
"""Development-only E1 outcome evaluator with a physically sealed holdout.

This script is the first E1 tool allowed to read future prices. It may evaluate
ONLY candidates in the final frozen development window and enforces a +4h purge
at the split boundary. It never queries a raw/reference market row at or after
FINAL_HOLDOUT_START, so the chronological holdout remains unopened by
construction.

It does not import Stage-6 lifecycle code, does not tune detector parameters,
and does not generate baselines/ablations yet. Its job is to establish the raw
post-T candidate distributions and the pre-T reactivity diagnostic on the
DEVELOPMENT sample only.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import asyncpg

from analytics.forecasting_v2.alignment import selected_bucket

UTC = timezone.utc
STUDY = "E1-RUN-001"
REFERENCE_EXCHANGE = "binance"
DEV_START = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
FINAL_HOLDOUT_START = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
MAX_HORIZON_MINUTES = 240
DEV_LAST_FULL_HORIZON_T = FINAL_HOLDOUT_START - timedelta(minutes=MAX_HORIZON_MINUTES)
PRE_LOOKBACK_MAX_MINUTES = 60
HORIZONS = (15, 30, 60, 120, 240)
PRE_HORIZONS = (15, 30, 60)
FAMILIES = ("TREND_PULLBACK", "COMPRESSION_BREAKOUT", "CONFIRMED_BREAKOUT")
DIRECTIONS = ("LONG", "SHORT")

RAW_BARS_SQL = """
SELECT ts, open, high, low, close
FROM klines_1m
WHERE exchange = $1 AND symbol = $2
  AND ts >= $3 AND ts < $4
ORDER BY ts ASC
"""

REFERENCE_5M_SQL = """
SELECT exchange, symbol, market_type, timeframe, bucket_ts,
       feature_schema_version, calculation_version,
       close_price, bars_expected, bars_present, has_gap, is_usable
FROM exchange_feature_vectors
WHERE exchange = $1 AND symbol = $2 AND market_type = $3
  AND timeframe = '5m' AND calculation_version = $4
  AND bucket_ts >= $5 AND bucket_ts <= $6
ORDER BY bucket_ts ASC
"""


def _parse_utc(text: str) -> datetime:
    value = text.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None or dt.utcoffset() is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"expected aware UTC datetime, got {text!r}")
    if dt.second or dt.microsecond:
        raise ValueError(f"expected whole-minute datetime, got {text!r}")
    return dt.astimezone(UTC)


def _finite_float(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        # asyncpg frequently returns Decimal for NUMERIC columns.
        try:
            value = float(value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"{label} must be numeric, got {value!r}") from exc
    result = float(value)
    if not math.isfinite(result):
        raise RuntimeError(f"{label} must be finite, got {value!r}")
    return result


def _candidate_partition(T: datetime) -> str:
    if T >= FINAL_HOLDOUT_START:
        return "HOLDOUT_SEALED"
    if T > DEV_LAST_FULL_HORIZON_T:
        return "DEV_PURGE"
    if T < DEV_START:
        return "OUTSIDE_DEV"
    return "DEV_OUTCOME_ELIGIBLE"


def _directional_return(direction: str, p0: float, p1: float) -> float:
    if direction == "LONG":
        return p1 / p0 - 1.0
    if direction == "SHORT":
        return p0 / p1 - 1.0
    raise ValueError(f"unknown direction {direction!r}")


def _exact_grid(start: datetime, minutes: int) -> tuple[datetime, ...]:
    return tuple(start + timedelta(minutes=i) for i in range(minutes))


def _grid_rows(bar_map: Mapping[datetime, Mapping[str, Any]], start: datetime,
               minutes: int) -> tuple[tuple[Mapping[str, Any], ...], tuple[datetime, ...]]:
    expected = _exact_grid(start, minutes)
    missing = tuple(ts for ts in expected if ts not in bar_map)
    rows = tuple(bar_map[ts] for ts in expected if ts in bar_map)
    return rows, missing


def _first_extreme(rows: Iterable[Mapping[str, Any]], key: str, mode: str) -> Mapping[str, Any]:
    items = tuple(rows)
    if not items:
        raise RuntimeError("cannot select an extreme from an empty path")
    if mode == "max":
        target = max(_finite_float(r[key], key) for r in items)
    elif mode == "min":
        target = min(_finite_float(r[key], key) for r in items)
    else:
        raise ValueError(mode)
    for row in items:  # earliest bar wins an exact tie
        if _finite_float(row[key], key) == target:
            return row
    raise AssertionError("unreachable")


def _pre_metric(*, direction: str, T: datetime, minutes: int, p_t: float,
                bar_map: Mapping[datetime, Mapping[str, Any]]) -> dict[str, Any]:
    # Price at instant T-minutes is the close of the 1m bar ending at that instant.
    endpoint_ts = T - timedelta(minutes=minutes + 1)
    path_start = T - timedelta(minutes=minutes)
    path_rows, missing = _grid_rows(bar_map, path_start, minutes)
    endpoint = bar_map.get(endpoint_ts)
    complete = endpoint is not None and not missing and len(path_rows) == minutes
    if not complete:
        return {
            "minutes": minutes,
            "path_complete": False,
            "missing_minutes": len(missing) + (1 if endpoint is None else 0),
            "directional_return": None,
        }
    p_past = _finite_float(endpoint["close"], "pre endpoint close")
    return {
        "minutes": minutes,
        "path_complete": True,
        "missing_minutes": 0,
        "directional_return": _directional_return(direction, p_past, p_t),
    }


def _future_metric(*, direction: str, T: datetime, minutes: int, p_t: float,
                   bar_map: Mapping[datetime, Mapping[str, Any]]) -> dict[str, Any]:
    rows, missing = _grid_rows(bar_map, T, minutes)
    complete = not missing and len(rows) == minutes
    if not complete:
        return {
            "minutes": minutes,
            "path_complete": False,
            "bars_expected": minutes,
            "bars_present": len(rows),
            "missing_minutes": len(missing),
            "terminal_directional_return": None,
            "mfe": None,
            "mae": None,
            "time_to_mfe_bar_start_minutes": None,
            "time_to_mae_bar_start_minutes": None,
        }

    terminal = _finite_float(rows[-1]["close"], "terminal close")
    if direction == "LONG":
        mfe_row = _first_extreme(rows, "high", "max")
        mae_row = _first_extreme(rows, "low", "min")
        mfe = _finite_float(mfe_row["high"], "high") / p_t - 1.0
        mae = _finite_float(mae_row["low"], "low") / p_t - 1.0
    elif direction == "SHORT":
        mfe_row = _first_extreme(rows, "low", "min")
        mae_row = _first_extreme(rows, "high", "max")
        mfe = (p_t - _finite_float(mfe_row["low"], "low")) / p_t
        mae = (p_t - _finite_float(mae_row["high"], "high")) / p_t
    else:
        raise ValueError(direction)

    mfe_ts = mfe_row["ts"]
    mae_ts = mae_row["ts"]
    return {
        "minutes": minutes,
        "path_complete": True,
        "bars_expected": minutes,
        "bars_present": minutes,
        "missing_minutes": 0,
        "terminal_directional_return": _directional_return(direction, p_t, terminal),
        "mfe": mfe,
        "mae": mae,
        # Historical 1m data only identify the bar containing the extreme, not
        # the sub-minute instant. Report the bar-start offset explicitly.
        "time_to_mfe_bar_start_minutes": int((mfe_ts - T).total_seconds() // 60),
        "time_to_mae_bar_start_minutes": int((mae_ts - T).total_seconds() // 60),
    }


def _median(values: Iterable[float]) -> float | None:
    vals = list(values)
    return statistics.median(vals) if vals else None


def _mean(values: Iterable[float]) -> float | None:
    vals = list(values)
    return statistics.fmean(vals) if vals else None


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for family in FAMILIES:
        family_rows = [r for r in rows if r["family"] == family]
        family_summary: dict[str, Any] = {
            "rows": len(family_rows),
            "reference_usable": sum(1 for r in family_rows if r["reference_usable"]),
            "pre": {},
            "future": {},
        }
        for minutes in PRE_HORIZONS:
            metrics = [r["pre"][str(minutes)] for r in family_rows]
            complete = [m for m in metrics if m["path_complete"] and m["directional_return"] is not None]
            values = [m["directional_return"] for m in complete]
            family_summary["pre"][str(minutes)] = {
                "n_complete": len(complete),
                "median_directional_return": _median(values),
                "mean_directional_return": _mean(values),
            }
        for minutes in HORIZONS:
            metrics = [r["future"][str(minutes)] for r in family_rows]
            complete = [m for m in metrics if m["path_complete"] and m["terminal_directional_return"] is not None]
            returns = [m["terminal_directional_return"] for m in complete]
            mfes = [m["mfe"] for m in complete]
            maes = [m["mae"] for m in complete]
            family_summary["future"][str(minutes)] = {
                "n_complete": len(complete),
                "positive_share": (
                    sum(1 for v in returns if v > 0.0) / len(returns) if returns else None
                ),
                "median_directional_return": _median(returns),
                "mean_directional_return": _mean(returns),
                "median_mfe": _median(mfes),
                "median_mae": _median(maes),
            }
        result[family] = family_summary
    return result


def _load_candidates(path: Path, calculation_version: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("study") != STUDY:
        raise RuntimeError(f"candidate artifact study must be {STUDY!r}")
    if payload.get("outcomes_included") is not False:
        raise RuntimeError("candidate artifact must have outcomes_included=false")
    if payload.get("calculation_version") != calculation_version:
        raise RuntimeError("candidate artifact calculation_version does not match CLI")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        raise RuntimeError("candidate artifact candidates must be a list")
    return payload, candidates


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    source, candidates = _load_candidates(args.input, args.calculation_version)

    partition_counts: Counter[str] = Counter()
    family_partition_counts: dict[str, Counter[str]] = defaultdict(Counter)
    eligible: list[dict[str, Any]] = []
    for candidate in candidates:
        T = _parse_utc(candidate["T"])
        family = candidate.get("family")
        direction = candidate.get("direction")
        if family not in FAMILIES:
            raise RuntimeError(f"unknown candidate family {family!r}")
        if direction not in DIRECTIONS:
            raise RuntimeError(f"unknown candidate direction {direction!r}")
        partition = _candidate_partition(T)
        partition_counts[partition] += 1
        family_partition_counts[partition][family] += 1
        if partition == "DEV_OUTCOME_ELIGIBLE":
            eligible.append(candidate)

    # This is a hard safety assertion: the DB query upper bound is exactly the
    # sealed split and every per-candidate +4h path must end at/before it.
    for candidate in eligible:
        T = _parse_utc(candidate["T"])
        if T + timedelta(minutes=MAX_HORIZON_MINUTES) > FINAL_HOLDOUT_START:
            raise RuntimeError("holdout seal violation: eligible candidate future path crosses split")

    conn = await asyncpg.connect(args.dsn)
    try:
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            raw_start = DEV_START - timedelta(minutes=PRE_LOOKBACK_MAX_MINUTES + 1)
            raw_end = FINAL_HOLDOUT_START
            raw_records = await conn.fetch(
                RAW_BARS_SQL, REFERENCE_EXCHANGE, args.symbol, raw_start, raw_end)
            # Defensive assertion over returned data: never accept a row on/after split.
            for rec in raw_records:
                if rec["ts"] >= FINAL_HOLDOUT_START:
                    raise RuntimeError("DB returned raw row inside sealed holdout")
            bar_map: dict[datetime, dict[str, Any]] = {
                rec["ts"]: {
                    "ts": rec["ts"], "open": rec["open"], "high": rec["high"],
                    "low": rec["low"], "close": rec["close"],
                }
                for rec in raw_records
            }

            first_ref_bucket = selected_bucket("5m", DEV_START)
            last_ref_bucket = selected_bucket("5m", DEV_LAST_FULL_HORIZON_T)
            ref_records = await conn.fetch(
                REFERENCE_5M_SQL,
                REFERENCE_EXCHANGE, args.symbol, args.market_type,
                args.calculation_version, first_ref_bucket, last_ref_bucket,
            )
            ref_map = {rec["bucket_ts"]: dict(rec) for rec in ref_records}

            outcome_rows: list[dict[str, Any]] = []
            for candidate in eligible:
                T = _parse_utc(candidate["T"])
                family = candidate["family"]
                direction = candidate["direction"]
                b5 = selected_bucket("5m", T)
                ref = ref_map.get(b5)
                reference_usable = False
                p_t: float | None = None
                reference_reason: str | None = None

                if ref is None:
                    reference_reason = "MISSING_REFERENCE_VECTOR"
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
                        reference_reason = "REFERENCE_GATE_FAILED"
                    else:
                        p_t = _finite_float(ref["close_price"], "reference close_price")
                        if p_t <= 0.0:
                            raise RuntimeError("reference close_price must be > 0")
                        # Cross-check the materialized 5m close against the exact raw
                        # 1m close immediately preceding T.
                        raw_endpoint = bar_map.get(T - timedelta(minutes=1))
                        if raw_endpoint is None:
                            reference_reason = "MISSING_RAW_REFERENCE_ENDPOINT"
                            p_t = None
                        else:
                            raw_close = _finite_float(raw_endpoint["close"], "raw P_T close")
                            if raw_close != p_t:
                                raise RuntimeError(
                                    f"reference/raw close mismatch at T={T.isoformat()}: "
                                    f"vector={p_t!r} raw={raw_close!r}")
                            reference_usable = True

                row: dict[str, Any] = {
                    "T": T.isoformat(),
                    "family": family,
                    "direction": direction,
                    "reference_bucket_5m": b5.isoformat(),
                    "reference_usable": reference_usable,
                    "reference_unavailable_reason": reference_reason,
                    "P_T": p_t,
                    "pre": {},
                    "future": {},
                }
                if reference_usable and p_t is not None:
                    for minutes in PRE_HORIZONS:
                        row["pre"][str(minutes)] = _pre_metric(
                            direction=direction, T=T, minutes=minutes, p_t=p_t,
                            bar_map=bar_map)
                    for minutes in HORIZONS:
                        row["future"][str(minutes)] = _future_metric(
                            direction=direction, T=T, minutes=minutes, p_t=p_t,
                            bar_map=bar_map)
                else:
                    for minutes in PRE_HORIZONS:
                        row["pre"][str(minutes)] = {
                            "minutes": minutes, "path_complete": False,
                            "missing_minutes": None, "directional_return": None,
                        }
                    for minutes in HORIZONS:
                        row["future"][str(minutes)] = {
                            "minutes": minutes, "path_complete": False,
                            "bars_expected": minutes, "bars_present": None,
                            "missing_minutes": None,
                            "terminal_directional_return": None, "mfe": None, "mae": None,
                            "time_to_mfe_bar_start_minutes": None,
                            "time_to_mae_bar_start_minutes": None,
                        }
                outcome_rows.append(row)
    finally:
        await conn.close()

    denominator = {
        "source_candidates_total": len(candidates),
        "partitions": dict(sorted(partition_counts.items())),
        "partitions_by_family": {
            partition: dict(sorted(counts.items()))
            for partition, counts in sorted(family_partition_counts.items())
        },
        "development_candidate_window_total": sum(
            count for partition, count in partition_counts.items()
            if partition in ("DEV_OUTCOME_ELIGIBLE", "DEV_PURGE")
        ),
        "development_full_horizon_eligible": len(eligible),
        "development_full_horizon_reference_usable": sum(
            1 for row in outcome_rows if row["reference_usable"]),
        "holdout_candidates_sealed": partition_counts.get("HOLDOUT_SEALED", 0),
    }

    return {
        "study": STUDY,
        "kind": "DEVELOPMENT_CANDIDATE_OUTCOMES_ONLY",
        "source_candidate_artifact": str(args.input),
        "source_research_head_sha": source.get("research_head_sha"),
        "symbol": args.symbol,
        "market_type": args.market_type,
        "calculation_version": args.calculation_version,
        "feature_schema_version": args.feature_schema_version,
        "development_candidate_window": {
            "start_inclusive": DEV_START.isoformat(),
            "end_exclusive": FINAL_HOLDOUT_START.isoformat(),
        },
        "full_horizon_eligible_T_max_inclusive": DEV_LAST_FULL_HORIZON_T.isoformat(),
        "sealed_holdout_start": FINAL_HOLDOUT_START.isoformat(),
        "db_market_read_window": {
            "raw_start_inclusive": (
                DEV_START - timedelta(minutes=PRE_LOOKBACK_MAX_MINUTES + 1)
            ).isoformat(),
            "upper_bound_exclusive": FINAL_HOLDOUT_START.isoformat(),
        },
        "holdout_outcomes_opened": False,
        "holdout_market_rows_read": False,
        "max_forward_horizon_minutes": MAX_HORIZON_MINUTES,
        "time_to_extreme_resolution_note": (
            "1m history identifies the bar containing the extreme; time-to-extreme is the "
            "bar-start offset in whole minutes, not a sub-minute event time"
        ),
        "denominator": denominator,
        "family_summary": _summarize(outcome_rows),
        "rows": outcome_rows,
    }


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate E1 candidate outcomes on development only; holdout stays sealed")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--market-type", default="perp")
    parser.add_argument("--calculation-version", required=True)
    parser.add_argument("--feature-schema-version", type=int, default=1)
    return parser


def main() -> int:
    args = _parser().parse_args()
    payload = asyncio.run(_run(args))
    _write_json_atomic(args.output, payload)
    print(json.dumps({
        "denominator": payload["denominator"],
        "family_summary": payload["family_summary"],
        "holdout_outcomes_opened": payload["holdout_outcomes_opened"],
        "holdout_market_rows_read": payload["holdout_market_rows_read"],
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
