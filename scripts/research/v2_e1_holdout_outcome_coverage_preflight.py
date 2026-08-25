#!/usr/bin/env python3
"""Outcome-free raw-timestamp coverage preflight before opening E1 holdout prices.

Reads ONLY Binance 1m timestamps (no OHLC values) and the frozen holdout inventory
artifact. It verifies that the required +4h observation horizon has actually
arrived before the single holdout outcome evaluation is allowed to run.

Important: the original E1 preregistration explicitly allows genuine historical
1m gaps to remain as incomplete outcome paths with visible denominators.  Such a
gap must therefore NOT permanently block the whole holdout.  This preflight
separates already-observed historical gaps from an unobserved/future tail.  The
holdout may open only after the final required bar timestamp has been observed;
any earlier missing timestamps remain evidence-quality/path-completeness facts
for the frozen evaluator to report rather than being silently repaired.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg

UTC = timezone.utc
STUDY = "E1-RUN-001"
HOLDOUT_START = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
HOLDOUT_END = datetime(2026, 8, 25, 17, 20, tzinfo=UTC)
MAX_HORIZON = timedelta(minutes=240)
PRE_LOOKBACK = timedelta(minutes=61)


def _parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"expected UTC datetime, got {value!r}")
    return dt.astimezone(UTC)


def _load_inventory(path: Path) -> tuple[dict, list[dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("study") != STUDY:
        raise RuntimeError("unexpected study")
    if payload.get("kind") != "HOLDOUT_ABLATION_INVENTORY_NO_OUTCOMES":
        raise RuntimeError("unexpected holdout inventory kind")
    if payload.get("full_population_reproduced") is not True:
        raise RuntimeError("FULL holdout population was not reproduced")
    if payload.get("outcomes_included") is not False:
        raise RuntimeError("source inventory already includes outcomes")
    if payload.get("holdout_outcomes_opened") is not False:
        raise RuntimeError("source inventory says holdout outcomes were opened")
    if payload.get("holdout_market_rows_read") is not False:
        raise RuntimeError("source inventory says holdout market rows were read")
    window = payload.get("holdout_window") or {}
    if window.get("start_inclusive") != HOLDOUT_START.isoformat():
        raise RuntimeError("unexpected holdout start")
    if window.get("end_exclusive") != HOLDOUT_END.isoformat():
        raise RuntimeError("unexpected holdout end")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("holdout inventory rows missing")
    return payload, rows


async def _run(args: argparse.Namespace) -> dict:
    _, rows = _load_inventory(args.input)
    times = [_parse_utc(str(row["T"])) for row in rows]
    if any(not (HOLDOUT_START <= T < HOLDOUT_END) for T in times):
        raise RuntimeError("inventory contains T outside frozen holdout")

    min_t = min(times)
    max_t = max(times)
    required_start = min_t - PRE_LOOKBACK
    required_end_exclusive = max_t + MAX_HORIZON
    required_last_bar_start = required_end_exclusive - timedelta(minutes=1)
    expected_minutes = int((required_end_exclusive - required_start).total_seconds() // 60)

    conn = await asyncpg.connect(args.dsn)
    try:
        records = await conn.fetch(
            """
            SELECT ts
            FROM klines_1m
            WHERE exchange = 'binance' AND symbol = $1
              AND ts >= $2 AND ts < $3
            ORDER BY ts ASC
            """,
            args.symbol,
            required_start,
            required_end_exclusive,
        )
    finally:
        await conn.close()

    observed = {rec["ts"] for rec in records}
    latest_observed = max(observed) if observed else None

    missing_all: list[datetime] = []
    cursor = required_start
    while cursor < required_end_exclusive:
        if cursor not in observed:
            missing_all.append(cursor)
        cursor += timedelta(minutes=1)

    if latest_observed is None:
        historical_gaps: list[datetime] = []
        unobserved_tail = list(missing_all)
    else:
        # Missing timestamps at/before the latest observed bar are genuine
        # historical gaps. Missing timestamps after it are an unavailable tail.
        historical_gaps = [ts for ts in missing_all if ts <= latest_observed]
        unobserved_tail = [ts for ts in missing_all if ts > latest_observed]

    horizon_observed = (
        latest_observed is not None and latest_observed >= required_last_bar_start
    )

    payload = {
        "study": STUDY,
        "kind": "HOLDOUT_OUTCOME_COVERAGE_PREFLIGHT_TIMESTAMPS_ONLY",
        "source_inventory": str(args.input),
        "prices_read": False,
        "outcomes_opened": False,
        "holdout_market_price_rows_read": False,
        "inventory_min_T": min_t.isoformat(),
        "inventory_max_T": max_t.isoformat(),
        "required_raw_window": {
            "start_inclusive": required_start.isoformat(),
            "end_exclusive": required_end_exclusive.isoformat(),
            "required_last_bar_start": required_last_bar_start.isoformat(),
        },
        "expected_minutes": expected_minutes,
        "observed_minutes": len(observed),
        "latest_observed_bar_start": (
            latest_observed.isoformat() if latest_observed is not None else None
        ),
        "missing_minutes": len(missing_all),
        "historical_gap_minutes": len(historical_gaps),
        "historical_gap_sample": [ts.isoformat() for ts in historical_gaps[:20]],
        "unobserved_tail_minutes": len(unobserved_tail),
        "unobserved_tail_sample": [ts.isoformat() for ts in unobserved_tail[:20]],
        "horizon_observed_through_required_last_bar": horizon_observed,
        "readiness_rule": (
            "READY iff the final required 1m bar timestamp has been observed. "
            "Earlier historical gaps remain incomplete-path evidence and do not "
            "block the whole holdout."
        ),
        "ready_for_single_holdout_outcome_open": horizon_observed,
    }
    return payload


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Timestamp-only E1 holdout outcome coverage preflight")
    p.add_argument("--dsn", required=True)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--symbol", default="BTCUSDT")
    return p


def main() -> int:
    args = _parser().parse_args()
    payload = asyncio.run(_run(args))
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if payload["ready_for_single_holdout_outcome_open"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
