#!/usr/bin/env python3
"""E1 development-only direction-inversion and matched-random controls.

This is the first control evaluator after candidate development outcomes were
opened. The high-level controls and seed were pre-registered before outcomes:

- direction inversion (LONG <-> SHORT) at the same candidate T;
- deterministic time-matched random control, seed 20260825.

The exact random matching protocol is frozen here BEFORE any control outcome is
viewed: for every full-horizon development candidate, choose one non-candidate
T without replacement within the SAME (family, UTC day), preserve the original
candidate direction, and preserve the family's legal decision clock
(TREND_PULLBACK: 15m formation boundaries; breakout families: every 5m boundary).
All actual V2 candidate times from any family are excluded from random pools.
Only controls with complete pre-60m / post-240m raw paths and a usable canonical
Binance 5m reference vector are eligible. Selection depends on timestamps/data
availability only, never on future price values.

The DB market read is hard-capped strictly before the final sealed holdout start
2026-08-16T00:00:00Z. No Stage-6 lifecycle code is imported.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import asyncpg

from analytics.forecasting_v2.alignment import selected_bucket
from scripts.research.v2_e1_development_outcomes import (
    DEV_LAST_FULL_HORIZON_T,
    DEV_START,
    FINAL_HOLDOUT_START,
    FAMILIES,
    HORIZONS,
    PRE_HORIZONS,
    REFERENCE_EXCHANGE,
    _finite_float,
    _future_metric,
    _parse_utc,
    _pre_metric,
)

UTC = timezone.utc
STUDY = "E1-RUN-001"
DEFAULT_SEED = 20260825
MARKET_TYPE = "perp"

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


def _opposite(direction: str) -> str:
    if direction == "LONG":
        return "SHORT"
    if direction == "SHORT":
        return "LONG"
    raise ValueError(f"unknown direction {direction!r}")


def _family_clock_ok(family: str, T: datetime) -> bool:
    if T.second or T.microsecond or T.tzinfo is None or T.utcoffset() != timedelta(0):
        return False
    if T.minute % 5 != 0:
        return False
    if family == "TREND_PULLBACK":
        return T.minute % 15 == 0
    if family in ("COMPRESSION_BREAKOUT", "CONFIRMED_BREAKOUT"):
        return True
    raise ValueError(f"unknown family {family!r}")


def _reference_price_at(
    *, T: datetime, symbol: str, calculation_version: str, feature_schema_version: int,
    ref_map: Mapping[datetime, Mapping[str, Any]],
    bar_map: Mapping[datetime, Mapping[str, Any]],
) -> float | None:
    b5 = selected_bucket("5m", T)
    ref = ref_map.get(b5)
    if ref is None:
        return None
    if (
        ref.get("exchange") != REFERENCE_EXCHANGE
        or ref.get("symbol") != symbol
        or ref.get("market_type") != MARKET_TYPE
        or ref.get("timeframe") != "5m"
        or ref.get("bucket_ts") != b5
        or ref.get("calculation_version") != calculation_version
        or ref.get("feature_schema_version") != feature_schema_version
    ):
        raise RuntimeError(f"reference identity mismatch at T={T.isoformat()}")
    if not (
        ref.get("is_usable") is True
        and ref.get("has_gap") is False
        and ref.get("bars_present") == ref.get("bars_expected")
        and ref.get("close_price") is not None
    ):
        return None
    p_t = _finite_float(ref["close_price"], "reference close_price")
    raw_endpoint = bar_map.get(T - timedelta(minutes=1))
    if raw_endpoint is None:
        return None
    raw_close = _finite_float(raw_endpoint["close"], "raw P_T close")
    if raw_close != p_t:
        raise RuntimeError(
            f"reference/raw close mismatch at T={T.isoformat()}: vector={p_t!r} raw={raw_close!r}")
    return p_t


def _timestamps_complete(T: datetime, bar_map: Mapping[datetime, Mapping[str, Any]]) -> bool:
    # Pre-T metric at -60m needs the endpoint bar ending at T-60m plus all
    # bars from T-60m through T-1. Future +240m needs T through T+239m.
    required_start = T - timedelta(minutes=61)
    required_end_exclusive = T + timedelta(minutes=240)
    cursor = required_start
    while cursor < required_end_exclusive:
        if cursor not in bar_map:
            return False
        cursor += timedelta(minutes=1)
    return True


def _iter_day_grid(day: date, family: str) -> Iterable[datetime]:
    T = datetime(day.year, day.month, day.day, tzinfo=UTC)
    day_end = T + timedelta(days=1)
    while T < day_end:
        if _family_clock_ok(family, T):
            yield T
        T += timedelta(minutes=5)


def _stable_group_seed(base_seed: int, family: str, day: date) -> int:
    digest = hashlib.sha256(f"{base_seed}|{family}|{day.isoformat()}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _metrics_row(
    *, T: datetime, family: str, direction: str, p_t: float,
    bar_map: Mapping[datetime, Mapping[str, Any]], control_kind: str,
    matched_from_T: datetime | None,
) -> dict[str, Any]:
    return {
        "T": T.isoformat(),
        "matched_from_T": matched_from_T.isoformat() if matched_from_T is not None else None,
        "family": family,
        "direction": direction,
        "control_kind": control_kind,
        "P_T": p_t,
        "pre": {
            str(minutes): _pre_metric(
                direction=direction, T=T, minutes=minutes, p_t=p_t, bar_map=bar_map)
            for minutes in PRE_HORIZONS
        },
        "future": {
            str(minutes): _future_metric(
                direction=direction, T=T, minutes=minutes, p_t=p_t, bar_map=bar_map)
            for minutes in HORIZONS
        },
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
        item: dict[str, Any] = {"rows": len(family_rows), "future": {}}
        for minutes in HORIZONS:
            metrics = [r["future"][str(minutes)] for r in family_rows]
            complete = [m for m in metrics if m["path_complete"]]
            returns = [m["terminal_directional_return"] for m in complete]
            item["future"][str(minutes)] = {
                "n_complete": len(complete),
                "positive_share": (
                    sum(1 for value in returns if value > 0.0) / len(returns) if returns else None
                ),
                "mean_directional_return": _mean(returns),
                "median_directional_return": _median(returns),
                "median_mfe": _median(m["mfe"] for m in complete),
                "median_mae": _median(m["mae"] for m in complete),
            }
        result[family] = item
    return result


def _paired_candidate_vs_random(
    actual_rows: list[dict[str, Any]], random_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    random_by_key = {
        (row["matched_from_T"], row["family"], row["direction"]): row
        for row in random_rows
    }
    output: dict[str, Any] = {}
    for family in FAMILIES:
        family_actual = [r for r in actual_rows if r["family"] == family]
        family_out: dict[str, Any] = {}
        for minutes in HORIZONS:
            deltas: list[float] = []
            wins = 0
            for actual in family_actual:
                key = (actual["T"], actual["family"], actual["direction"])
                random_row = random_by_key.get(key)
                if random_row is None:
                    raise RuntimeError(f"missing matched random row for {key}")
                a = actual["future"][str(minutes)]
                r = random_row["future"][str(minutes)]
                if not a["path_complete"] or not r["path_complete"]:
                    continue
                delta = a["terminal_directional_return"] - r["terminal_directional_return"]
                deltas.append(delta)
                if delta > 0.0:
                    wins += 1
            family_out[str(minutes)] = {
                "n_paired": len(deltas),
                "mean_candidate_minus_random": _mean(deltas),
                "median_candidate_minus_random": _median(deltas),
                "candidate_better_share": wins / len(deltas) if deltas else None,
            }
        output[family] = family_out
    return output


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    candidates_payload = _load_json(args.candidates)
    outcomes_payload = _load_json(args.outcomes)
    if candidates_payload.get("study") != STUDY or candidates_payload.get("outcomes_included") is not False:
        raise RuntimeError("candidate artifact identity/outcomes flag invalid")
    if outcomes_payload.get("study") != STUDY:
        raise RuntimeError("development outcome artifact study invalid")
    if outcomes_payload.get("holdout_outcomes_opened") is not False:
        raise RuntimeError("refusing source with opened holdout outcomes")
    if outcomes_payload.get("holdout_market_rows_read") is not False:
        raise RuntimeError("refusing source that read holdout market rows")
    if outcomes_payload.get("sealed_holdout_start") != FINAL_HOLDOUT_START.isoformat():
        raise RuntimeError("development outcome artifact has unexpected holdout split")
    if candidates_payload.get("calculation_version") != args.calculation_version:
        raise RuntimeError("candidate calculation_version mismatch")

    actual_rows = list(outcomes_payload.get("rows", []))
    if len(actual_rows) != outcomes_payload["denominator"]["development_full_horizon_eligible"]:
        raise RuntimeError("development outcome row count/denominator mismatch")
    actual_rows.sort(key=lambda r: (_parse_utc(r["T"]), r["family"], r["direction"]))

    all_dev_candidate_times = {
        _parse_utc(row["T"])
        for row in candidates_payload.get("candidates", [])
        if DEV_START <= _parse_utc(row["T"]) < FINAL_HOLDOUT_START
    }

    conn = await asyncpg.connect(args.dsn)
    try:
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            raw_start = DEV_START - timedelta(minutes=61)
            raw_records = await conn.fetch(
                RAW_BARS_SQL, REFERENCE_EXCHANGE, args.symbol, raw_start, FINAL_HOLDOUT_START)
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

            ref_records = await conn.fetch(
                REFERENCE_5M_SQL,
                REFERENCE_EXCHANGE, args.symbol, MARKET_TYPE, args.calculation_version,
                selected_bucket("5m", DEV_START), selected_bucket("5m", DEV_LAST_FULL_HORIZON_T),
            )
            ref_map = {rec["bucket_ts"]: dict(rec) for rec in ref_records}

            groups: dict[tuple[str, date], list[dict[str, Any]]] = defaultdict(list)
            for row in actual_rows:
                T = _parse_utc(row["T"])
                if not (DEV_START <= T <= DEV_LAST_FULL_HORIZON_T):
                    raise RuntimeError(f"actual development row outside full-horizon window: {T}")
                if not _family_clock_ok(row["family"], T):
                    raise RuntimeError(f"actual row violates family clock: {row}")
                groups[(row["family"], T.date())].append(row)

            matched_random_rows: list[dict[str, Any]] = []
            match_manifest: list[dict[str, Any]] = []
            for (family, day), group_rows in sorted(groups.items(), key=lambda x: (x[0][1], x[0][0])):
                pool: list[datetime] = []
                for T in _iter_day_grid(day, family):
                    if T < DEV_START or T > DEV_LAST_FULL_HORIZON_T:
                        continue
                    if T in all_dev_candidate_times:
                        continue
                    if not _timestamps_complete(T, bar_map):
                        continue
                    p_t = _reference_price_at(
                        T=T, symbol=args.symbol,
                        calculation_version=args.calculation_version,
                        feature_schema_version=args.feature_schema_version,
                        ref_map=ref_map, bar_map=bar_map)
                    if p_t is None:
                        continue
                    pool.append(T)

                group_rows = sorted(group_rows, key=lambda r: (_parse_utc(r["T"]), r["direction"]))
                if len(pool) < len(group_rows):
                    raise RuntimeError(
                        f"insufficient matched-random pool for {(family, day)}: "
                        f"need {len(group_rows)}, have {len(pool)}")
                rng = random.Random(_stable_group_seed(args.seed, family, day))
                rng.shuffle(pool)
                chosen = pool[:len(group_rows)]
                for actual, random_T in zip(group_rows, chosen):
                    p_t = _reference_price_at(
                        T=random_T, symbol=args.symbol,
                        calculation_version=args.calculation_version,
                        feature_schema_version=args.feature_schema_version,
                        ref_map=ref_map, bar_map=bar_map)
                    if p_t is None:
                        raise RuntimeError("matched random T lost reference usability after pool construction")
                    matched_random_rows.append(_metrics_row(
                        T=random_T,
                        family=family,
                        direction=actual["direction"],
                        p_t=p_t,
                        bar_map=bar_map,
                        control_kind="MATCHED_RANDOM_NONCANDIDATE_SAME_UTC_DAY",
                        matched_from_T=_parse_utc(actual["T"]),
                    ))
                    match_manifest.append({
                        "family": family,
                        "direction": actual["direction"],
                        "candidate_T": actual["T"],
                        "random_T": random_T.isoformat(),
                        "utc_day": day.isoformat(),
                    })

            inverted_rows: list[dict[str, Any]] = []
            for actual in actual_rows:
                T = _parse_utc(actual["T"])
                p_t = _reference_price_at(
                    T=T, symbol=args.symbol,
                    calculation_version=args.calculation_version,
                    feature_schema_version=args.feature_schema_version,
                    ref_map=ref_map, bar_map=bar_map)
                if p_t is None:
                    raise RuntimeError(f"actual candidate lost reference usability at {T}")
                inverted_rows.append(_metrics_row(
                    T=T,
                    family=actual["family"],
                    direction=_opposite(actual["direction"]),
                    p_t=p_t,
                    bar_map=bar_map,
                    control_kind="DIRECTION_INVERSION_SAME_T",
                    matched_from_T=T,
                ))
    finally:
        await conn.close()

    return {
        "study": STUDY,
        "kind": "DEVELOPMENT_NEGATIVE_AND_MATCHED_CONTROLS",
        "seed": args.seed,
        "exact_matching_protocol_frozen_before_control_outcome_view": True,
        "matching_protocol": {
            "random_scope": "same family + same UTC day",
            "direction": "preserve original candidate LONG/SHORT",
            "family_clock": {
                "TREND_PULLBACK": "15m formation boundaries only",
                "COMPRESSION_BREAKOUT": "every legal 5m boundary",
                "CONFIRMED_BREAKOUT": "every legal 5m boundary",
            },
            "exclude": "all actual V2 candidate T from any family in development",
            "replacement": False,
            "data_gate": "usable canonical Binance 5m reference + complete pre60/post240 raw path",
            "selection_uses_future_price_values": False,
        },
        "sealed_holdout_start": FINAL_HOLDOUT_START.isoformat(),
        "holdout_outcomes_opened": False,
        "holdout_market_rows_read": False,
        "rows": {
            "actual_candidate": actual_rows,
            "direction_inversion": inverted_rows,
            "matched_random": matched_random_rows,
        },
        "match_manifest": match_manifest,
        "summary": {
            "actual_candidate": _summarize(actual_rows),
            "direction_inversion": _summarize(inverted_rows),
            "matched_random": _summarize(matched_random_rows),
        },
        "paired_candidate_vs_matched_random": _paired_candidate_vs_random(
            actual_rows, matched_random_rows),
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
        description="Run sealed E1 development direction-inversion and matched-random controls")
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--calculation-version", required=True)
    parser.add_argument("--feature-schema-version", type=int, default=1)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser


def main() -> int:
    args = _parser().parse_args()
    payload = asyncio.run(_run(args))
    _write_json_atomic(args.output, payload)
    print(json.dumps({
        "seed": payload["seed"],
        "holdout_outcomes_opened": payload["holdout_outcomes_opened"],
        "holdout_market_rows_read": payload["holdout_market_rows_read"],
        "summary": payload["summary"],
        "paired_candidate_vs_matched_random": payload["paired_candidate_vs_matched_random"],
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
