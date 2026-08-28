#!/usr/bin/env python3
"""Evaluate frozen E1 ablation/simple-baseline variants on development only.

This script is allowed to read post-T prices only for the already-consumed
DEVELOPMENT window.  It reuses the exact market/outcome definitions from
`v2_e1_development_outcomes.py`, enforces the same +4h purge, and hard-caps all
DB market reads strictly before the sealed holdout at 2026-08-16T00:00:00Z.

Nested gate-removal ablations are reported as FULL / ABLATION_ALL / ADDED_ONLY
per `docs/e1/E1_RUN_001_ABLATION_OUTCOME_REPORTING_FREEZE.md`.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

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
    DEV_LAST_FULL_HORIZON_T,
    DEV_START,
    FINAL_HOLDOUT_START,
    HORIZONS,
    MAX_HORIZON_MINUTES,
    PRE_HORIZONS,
    RAW_BARS_SQL,
    REFERENCE_5M_SQL,
    REFERENCE_EXCHANGE,
    STUDY,
    _finite_float,
    _future_metric,
    _mean,
    _median,
    _parse_utc,
    _pre_metric,
)

EXPECTED_FULL_COUNTS = {
    TP_FULL: 93,
    CB_FULL: 30,
    FB_FULL: 26,
}

NESTED = {
    TP_NO_4H: TP_FULL,
    TP_NO_1H: TP_FULL,
    TP_NO_CONTEXT: TP_FULL,
    CB_NO_TAKER: CB_FULL,
    CB_SIMPLE: CB_FULL,
    FB_NO_CONTEXT: FB_FULL,
}


def _key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row["T"]), str(row["direction"])


def _load_inventory(path: Path, calculation_version: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("study") != STUDY:
        raise RuntimeError(f"inventory study must be {STUDY!r}")
    if payload.get("kind") != "DEVELOPMENT_ABLATION_INVENTORY_NO_OUTCOMES":
        raise RuntimeError("unexpected ablation inventory kind")
    if payload.get("outcomes_included") is not False:
        raise RuntimeError("ablation inventory must have outcomes_included=false")
    if payload.get("holdout_outcomes_opened") is not False:
        raise RuntimeError("source artifact says holdout outcomes were opened")
    if payload.get("holdout_market_rows_read") is not False:
        raise RuntimeError("source artifact says holdout market rows were read")
    if payload.get("calculation_version") != calculation_version:
        raise RuntimeError("ablation inventory calculation_version does not match CLI")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise RuntimeError("ablation inventory rows must be a list")
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
        if not (DEV_START <= T < FINAL_HOLDOUT_START):
            raise RuntimeError(f"variant row outside frozen development window: {T.isoformat()}")
        key = _key(row)
        if key in keys_by_variant[variant]:
            raise RuntimeError(f"duplicate variant key {variant} {key}")
        keys_by_variant[variant].add(key)
        counts[variant] += 1

    for variant, expected in EXPECTED_FULL_COUNTS.items():
        if counts[variant] != expected:
            raise RuntimeError(
                f"reproducibility failure: {variant} count={counts[variant]} expected={expected}")

    if keys_by_variant[FB_NO_CONTEXT] != keys_by_variant[FB_DUMB]:
        raise RuntimeError("FB_NO_CONTEXT must exactly equal FB_DUMB population")

    for ablation, full in NESTED.items():
        if not keys_by_variant[full].issubset(keys_by_variant[ablation]):
            missing = sorted(keys_by_variant[full] - keys_by_variant[ablation])[:5]
            raise RuntimeError(
                f"nested-population invariant failed: {full} not subset of {ablation}; "
                f"sample missing={missing}")
    return keys_by_variant


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    variants = sorted({r["variant"] for r in rows})
    for variant in variants:
        vr = [r for r in rows if r["variant"] == variant]
        summary: dict[str, Any] = {
            "rows": len(vr),
            "reference_usable": sum(1 for r in vr if r["reference_usable"]),
            "pre": {},
            "future": {},
        }
        for minutes in PRE_HORIZONS:
            metrics = [r["pre"][str(minutes)] for r in vr]
            complete = [m for m in metrics if m["path_complete"] and m["directional_return"] is not None]
            values = [m["directional_return"] for m in complete]
            summary["pre"][str(minutes)] = {
                "n_complete": len(complete),
                "median_directional_return": _median(values),
                "mean_directional_return": _mean(values),
            }
        for minutes in HORIZONS:
            metrics = [r["future"][str(minutes)] for r in vr]
            complete = [m for m in metrics if m["path_complete"] and m["terminal_directional_return"] is not None]
            returns = [m["terminal_directional_return"] for m in complete]
            mfes = [m["mfe"] for m in complete]
            maes = [m["mae"] for m in complete]
            summary["future"][str(minutes)] = {
                "n_complete": len(complete),
                "positive_share": (sum(1 for v in returns if v > 0.0) / len(returns) if returns else None),
                "median_directional_return": _median(returns),
                "mean_directional_return": _mean(returns),
                "median_mfe": _median(mfes),
                "median_mae": _median(maes),
            }
        result[variant] = summary
    return result


def _comparison_populations(
    outcome_rows: list[dict[str, Any]],
    keys_by_variant: Mapping[str, set[tuple[str, str]]],
) -> dict[str, Any]:
    by_variant_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in outcome_rows:
        by_variant_rows[row["variant"]].append(row)

    comparisons: dict[str, Any] = {}
    for ablation, full in NESTED.items():
        if ablation == FB_NO_CONTEXT:
            # FB_DUMB is an exact alias and is not independent evidence.
            pass
        full_keys = keys_by_variant[full]
        added_keys = keys_by_variant[ablation] - full_keys
        added_rows = [r for r in by_variant_rows[ablation] if _key(r) in added_keys]
        comparisons[ablation] = {
            "full_variant": full,
            "full_count_pre_purge": len(full_keys),
            "ablation_count_pre_purge": len(keys_by_variant[ablation]),
            "added_only_count_pre_purge": len(added_keys),
            "FULL": _summarize(by_variant_rows[full]).get(full, {}),
            "ABLATION_ALL": _summarize(by_variant_rows[ablation]).get(ablation, {}),
            "ADDED_ONLY": _summarize(added_rows).get(ablation, {
                "rows": 0, "reference_usable": 0, "pre": {}, "future": {}
            }),
        }
    return comparisons


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    source, rows = _load_inventory(args.input, args.calculation_version)
    keys_by_variant = _validate_inventory(rows)

    partition_counts: Counter[str] = Counter()
    partition_by_variant: dict[str, Counter[str]] = defaultdict(Counter)
    eligible: list[dict[str, Any]] = []
    for row in rows:
        T = _parse_utc(row["T"])
        if T > DEV_LAST_FULL_HORIZON_T:
            partition = "DEV_PURGE"
        else:
            partition = "DEV_OUTCOME_ELIGIBLE"
            eligible.append(row)
        partition_counts[partition] += 1
        partition_by_variant[partition][row["variant"]] += 1

    for row in eligible:
        T = _parse_utc(row["T"])
        if T + timedelta(minutes=MAX_HORIZON_MINUTES) > FINAL_HOLDOUT_START:
            raise RuntimeError("holdout seal violation: eligible variant crosses split")

    conn = await asyncpg.connect(args.dsn)
    try:
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            raw_start = DEV_START - timedelta(minutes=61)
            raw_end = FINAL_HOLDOUT_START
            raw_records = await conn.fetch(
                RAW_BARS_SQL, REFERENCE_EXCHANGE, args.symbol, raw_start, raw_end)
            for rec in raw_records:
                if rec["ts"] >= FINAL_HOLDOUT_START:
                    raise RuntimeError("DB returned raw row inside sealed holdout")
            bar_map = {
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
            for source_row in eligible:
                T = _parse_utc(source_row["T"])
                variant = source_row["variant"]
                direction = source_row["direction"]
                b5 = selected_bucket("5m", T)
                ref = ref_map.get(b5)
                reference_usable = False
                reference_reason: str | None = None
                p_t: float | None = None

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

                out: dict[str, Any] = {
                    "T": T.isoformat(),
                    "variant": variant,
                    "direction": direction,
                    "reference_usable": reference_usable,
                    "reference_unavailable_reason": reference_reason,
                    "P_T": p_t,
                    "pre": {},
                    "future": {},
                }
                if reference_usable and p_t is not None:
                    for minutes in PRE_HORIZONS:
                        out["pre"][str(minutes)] = _pre_metric(
                            direction=direction, T=T, minutes=minutes, p_t=p_t,
                            bar_map=bar_map)
                    for minutes in HORIZONS:
                        out["future"][str(minutes)] = _future_metric(
                            direction=direction, T=T, minutes=minutes, p_t=p_t,
                            bar_map=bar_map)
                else:
                    for minutes in PRE_HORIZONS:
                        out["pre"][str(minutes)] = {
                            "minutes": minutes, "path_complete": False,
                            "missing_minutes": None, "directional_return": None,
                        }
                    for minutes in HORIZONS:
                        out["future"][str(minutes)] = {
                            "minutes": minutes, "path_complete": False,
                            "bars_expected": minutes, "bars_present": None,
                            "missing_minutes": None, "terminal_directional_return": None,
                            "mfe": None, "mae": None,
                            "time_to_mfe_bar_start_minutes": None,
                            "time_to_mae_bar_start_minutes": None,
                        }
                outcome_rows.append(out)
    finally:
        await conn.close()

    variant_summary = _summarize(outcome_rows)
    comparisons = _comparison_populations(outcome_rows, keys_by_variant)

    return {
        "study": STUDY,
        "kind": "DEVELOPMENT_ABLATION_OUTCOMES_ONLY",
        "source_ablation_inventory": str(args.input),
        "source_research_head_sha": source.get("research_head_sha"),
        "reporting_protocol": "docs/e1/E1_RUN_001_ABLATION_OUTCOME_REPORTING_FREEZE.md",
        "symbol": args.symbol,
        "market_type": args.market_type,
        "calculation_version": args.calculation_version,
        "feature_schema_version": args.feature_schema_version,
        "sealed_holdout_start": FINAL_HOLDOUT_START.isoformat(),
        "db_market_read_window": {
            "raw_start_inclusive": (DEV_START - timedelta(minutes=61)).isoformat(),
            "upper_bound_exclusive": FINAL_HOLDOUT_START.isoformat(),
        },
        "holdout_outcomes_opened": False,
        "holdout_market_rows_read": False,
        "max_forward_horizon_minutes": MAX_HORIZON_MINUTES,
        "denominator": {
            "source_variant_rows_total": len(rows),
            "partitions": dict(sorted(partition_counts.items())),
            "partitions_by_variant": {
                p: dict(sorted(c.items())) for p, c in sorted(partition_by_variant.items())
            },
            "full_horizon_eligible_rows": len(eligible),
            "reference_usable_rows": sum(1 for r in outcome_rows if r["reference_usable"]),
        },
        "variant_summary": variant_summary,
        "nested_ablation_comparisons": comparisons,
        "alias_note": "FB_DUMB_48H_LEVEL_BREAKOUT is an exact population alias of FB_NO_CONTEXT and is not independent evidence",
        "rows": outcome_rows,
    }


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Evaluate frozen E1 ablation variants on development only")
    p.add_argument("--dsn", required=True)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--market-type", default="perp")
    p.add_argument("--calculation-version", required=True)
    p.add_argument("--feature-schema-version", type=int, default=1)
    return p


def main() -> int:
    args = _parser().parse_args()
    payload = asyncio.run(_run(args))
    _write_json_atomic(args.output, payload)
    print(json.dumps({
        "denominator": payload["denominator"],
        "holdout_outcomes_opened": payload["holdout_outcomes_opened"],
        "holdout_market_rows_read": payload["holdout_market_rows_read"],
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
