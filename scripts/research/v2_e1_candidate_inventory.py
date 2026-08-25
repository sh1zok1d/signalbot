#!/usr/bin/env python3
"""Candidate-only inventory for the pre-registered V2 E1 study.

This script deliberately stops at frozen Stage 5. It does NOT import or call
Stage-6 episode/lifecycle code and it never reads future outcome paths. Its
purpose is to learn the usable historical window and Stage-5 qualification
counts before the chronological development/holdout split is frozen.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from analytics.forecasting_v2.aligned_inputs import (
    V2AlignedInputRequest,
    load_v2_aligned_inputs,
)
from analytics.forecasting_v2.compression_breakout import detect_compression_breakout
from analytics.forecasting_v2.compression_breakout_inputs import load_compression_breakout_inputs
from analytics.forecasting_v2.confirmed_breakout import detect_confirmed_breakout
from analytics.forecasting_v2.confirmed_breakout_inputs import load_confirmed_breakout_inputs
from analytics.forecasting_v2.context_snapshot import build_v2_context_snapshot
from analytics.forecasting_v2.trend_pullback import detect_trend_pullback
from analytics.forecasting_v2.trend_pullback_inputs import load_trend_pullback_inputs
from storage.db import Database

UTC = timezone.utc
STEP = timedelta(minutes=5)
FROZEN_PRODUCTION_BASE_SHA = "8081eb31657f127141efb3a455f86690258164bc"
FAMILY_TREND_PULLBACK = "TREND_PULLBACK"
FAMILY_COMPRESSION_BREAKOUT = "COMPRESSION_BREAKOUT"
FAMILY_CONFIRMED_BREAKOUT = "CONFIRMED_BREAKOUT"


def _parse_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO-8601 datetime: {value!r}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise argparse.ArgumentTypeError("datetime must be timezone-aware UTC")
    if dt.utcoffset() != timedelta(0):
        raise argparse.ArgumentTypeError("datetime must have UTC offset +00:00")
    if dt.second or dt.microsecond or dt.minute % 5:
        raise argparse.ArgumentTypeError("datetime must be a whole 5-minute V2 decision boundary")
    return dt.astimezone(UTC)


def _iter_boundaries(start: datetime, end: datetime):
    """Yield [start, end) on the exact 5m grid; never floor/round caller input."""
    if end <= start:
        raise ValueError(f"end must be strictly after start, got {start!r} -> {end!r}")
    T = start
    while T < end:
        yield T
        T += STEP


def _jsonable(value: Any) -> Any:
    """Detach research output without Python-equality coercion tricks."""
    if is_dataclass(value):
        return {f.name: _jsonable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if value is None or type(value) in (bool, int, float, str):
        return value
    raise TypeError(f"unsupported research-output value {type(value).__name__}: {value!r}")


def _git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return completed.stdout.strip()


def _assert_frozen_production_tree() -> str:
    """Research tooling may change; frozen Stage3/4/5 + storage/config may not."""
    head = _git(["rev-parse", "HEAD"])
    completed = subprocess.run(
        [
            "git", "diff", "--quiet", FROZEN_PRODUCTION_BASE_SHA, "--",
            "analytics/forecasting_v2", "storage", "config/stage2.yaml",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode not in (0, 1):
        raise RuntimeError(f"git diff failed: {completed.stderr.strip()}")
    if completed.returncode == 1:
        raise RuntimeError(
            "research branch changes frozen production detector/data-path files relative to "
            f"{FROZEN_PRODUCTION_BASE_SHA}; E1-RUN-001 refuses to run"
        )
    return head


def _candidate_row(*, family: str, candidate: Any, context: Any) -> dict[str, Any]:
    return {
        "T": candidate.T.astimezone(UTC).isoformat(),
        "family": family,
        "direction": candidate.direction,
        "context": {
            "regime_4h": _jsonable(context.regime_4h),
            "bias_1h": _jsonable(context.bias_1h),
        },
        "candidate": _jsonable(candidate),
    }


async def _evaluate_boundary(db: Database, args: argparse.Namespace, T: datetime):
    """One coherent Stage3 -> Stage4 -> Stage5 evaluation at one T."""
    async with db.open_v2_coherent_read_session(
        symbol=args.symbol,
        market_type=args.market_type,
        calculation_version=args.calculation_version,
        decision_boundary=T,
    ) as session:
        request = V2AlignedInputRequest(
            T=T,
            symbol=args.symbol,
            market_type=args.market_type,
            calculation_version=args.calculation_version,
            feature_schema_version=args.feature_schema_version,
            health_exchanges=tuple(args.health_exchanges),
            health_metrics=tuple(args.health_metrics),
        )
        aligned = await load_v2_aligned_inputs(session, request)
        context = build_v2_context_snapshot(aligned)

        found: list[dict[str, Any]] = []

        tp_inputs = await load_trend_pullback_inputs(session, context=context)
        if tp_inputs is not None:
            tp = detect_trend_pullback(tp_inputs)
            if tp is not None:
                found.append(_candidate_row(
                    family=FAMILY_TREND_PULLBACK, candidate=tp, context=context))

        cb_inputs = await load_compression_breakout_inputs(session, context=context)
        cb = detect_compression_breakout(cb_inputs)
        if cb is not None:
            found.append(_candidate_row(
                family=FAMILY_COMPRESSION_BREAKOUT, candidate=cb, context=context))

        fb_inputs = await load_confirmed_breakout_inputs(session, context=context)
        fb = detect_confirmed_breakout(fb_inputs)
        if fb is not None:
            found.append(_candidate_row(
                family=FAMILY_CONFIRMED_BREAKOUT, candidate=fb, context=context))

        return found


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    research_head = _assert_frozen_production_tree()
    boundaries = list(_iter_boundaries(args.start, args.end))

    db = Database(args.dsn)
    await db.connect()
    try:
        candidates: list[dict[str, Any]] = []
        for index, T in enumerate(boundaries, start=1):
            rows = await _evaluate_boundary(db, args, T)
            candidates.extend(rows)
            if args.progress_every and index % args.progress_every == 0:
                print(
                    f"inventory progress: {index}/{len(boundaries)} boundaries; "
                    f"{len(candidates)} qualifications",
                    file=sys.stderr,
                    flush=True,
                )
    finally:
        await db.close()

    by_family = Counter(row["family"] for row in candidates)
    by_family_direction = Counter((row["family"], row["direction"]) for row in candidates)
    by_utc_day = Counter(row["T"][:10] for row in candidates)

    return {
        "study": "E1-RUN-001",
        "kind": "STAGE5_CANDIDATE_INVENTORY_NO_OUTCOMES",
        "frozen_production_base_sha": FROZEN_PRODUCTION_BASE_SHA,
        "research_head_sha": research_head,
        "symbol": args.symbol,
        "market_type": args.market_type,
        "calculation_version": args.calculation_version,
        "feature_schema_version": args.feature_schema_version,
        "health_exchanges": list(args.health_exchanges),
        "health_metrics": list(args.health_metrics),
        "window": {
            "start_inclusive": args.start.isoformat(),
            "end_exclusive": args.end.isoformat(),
            "decision_boundaries": len(boundaries),
        },
        "summary": {
            "total_qualifications": len(candidates),
            "by_family": dict(sorted(by_family.items())),
            "by_family_direction": {
                f"{family}:{direction}": count
                for (family, direction), count in sorted(by_family_direction.items())
            },
            "by_utc_day": dict(sorted(by_utc_day.items())),
        },
        "candidates": candidates,
        "outcomes_included": False,
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
        description="Inventory frozen V2 Stage-5 candidates without reading future outcomes")
    parser.add_argument("--dsn", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--market-type", default="perp")
    parser.add_argument("--start", required=True, type=_parse_utc)
    parser.add_argument("--end", required=True, type=_parse_utc)
    parser.add_argument("--calculation-version", required=True)
    parser.add_argument("--feature-schema-version", type=int, default=1)
    parser.add_argument("--health-exchanges", nargs="+", required=True)
    parser.add_argument("--health-metrics", nargs="+", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--progress-every", type=int, default=100)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.dsn:
        raise SystemExit("--dsn or DATABASE_URL is required")
    if args.feature_schema_version <= 0:
        raise SystemExit("--feature-schema-version must be > 0")
    if args.progress_every < 0:
        raise SystemExit("--progress-every must be >= 0")

    payload = asyncio.run(_run(args))
    _write_json_atomic(args.output, payload)
    print(json.dumps(payload["summary"], sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
