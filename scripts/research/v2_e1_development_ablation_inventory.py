#!/usr/bin/env python3
"""Outcome-free E1 development ablation/simple-baseline candidate census.

Exact variant semantics are frozen in
`docs/e1/E1_RUN_001_ABLATION_PROTOCOL_FREEZE.md` before this script's
outputs are inspected.  This script reads only information available at each
historical decision T and never reads post-T outcome paths.  The chronological
holdout starts at 2026-08-16T00:00:00Z and is never evaluated here.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import sys
from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from analytics.forecasting_v2.aligned_inputs import (
    V2AlignedInputRequest,
    derive_reference_extrema,
    load_v2_aligned_inputs,
)
from analytics.forecasting_v2.alignment import selected_bucket
from analytics.forecasting_v2.bias_1h import (
    BEARISH as BIAS_BEARISH,
    BULLISH as BIAS_BULLISH,
    NEUTRAL_NOT_ESTABLISHED,
    V2BiasResult,
)
from analytics.forecasting_v2.compression_breakout import (
    V2CompressionBreakoutInputs,
    detect_compression_breakout,
)
from analytics.forecasting_v2.compression_breakout_inputs import load_compression_breakout_inputs
from analytics.forecasting_v2.confirmed_breakout import detect_confirmed_breakout
from analytics.forecasting_v2.confirmed_breakout_inputs import load_confirmed_breakout_inputs
from analytics.forecasting_v2.context_snapshot import V2ContextSnapshot, build_v2_context_snapshot
from analytics.forecasting_v2.regime_4h import (
    BEARISH_TRENDING,
    BULLISH_TRENDING,
    NON_DIRECTIONAL,
    REGIME_TREND_THRESHOLD,
    V2RegimeResult,
)
from analytics.forecasting_v2.trend_pullback import detect_trend_pullback
from analytics.forecasting_v2.trend_pullback_inputs import load_trend_pullback_inputs
from scripts.research.v2_e1_candidate_inventory import (
    FROZEN_PRODUCTION_BASE_SHA,
    _assert_frozen_production_tree,
    _jsonable,
)
from scripts.research.v2_e1_research_session import E1ResearchReadSession
from storage.db import Database

UTC = timezone.utc
DEV_START = datetime(2026, 8, 2, 0, 0, tzinfo=UTC)
HOLDOUT_START = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
STEP = timedelta(minutes=5)
FIVE_MIN = timedelta(minutes=5)
FIFTEEN_MIN = timedelta(minutes=15)

TP_FULL = "TP_FULL"
TP_NO_4H = "TP_NO_4H"
TP_NO_1H = "TP_NO_1H"
TP_NO_CONTEXT = "TP_NO_CONTEXT"
CB_FULL = "CB_FULL"
CB_NO_TAKER = "CB_NO_TAKER"
CB_SIMPLE = "CB_SIMPLE_COMPRESSION_BREAKOUT"
CB_ORDINARY = "CB_ORDINARY_RANGE_BREAKOUT"
FB_FULL = "FB_FULL"
FB_NO_CONTEXT = "FB_NO_CONTEXT"
FB_DUMB = "FB_DUMB_48H_LEVEL_BREAKOUT"

VARIANTS = (
    TP_FULL, TP_NO_4H, TP_NO_1H, TP_NO_CONTEXT,
    CB_FULL, CB_NO_TAKER, CB_SIMPLE, CB_ORDINARY,
    FB_FULL, FB_NO_CONTEXT, FB_DUMB,
)


def _iter_boundaries():
    T = DEV_START
    while T < HOLDOUT_START:
        yield T
        T += STEP


def _synthetic_context(
    context: V2ContextSnapshot, *, regime: str, bias: str,
) -> V2ContextSnapshot:
    if regime == BULLISH_TRENDING:
        regime_result = V2RegimeResult(
            bucket_ts=context.regime_4h.bucket_ts,
            regime=BULLISH_TRENDING,
            is_compressed=None,
            price_evi=REGIME_TREND_THRESHOLD,
            compression_score=None,
        )
    elif regime == BEARISH_TRENDING:
        regime_result = V2RegimeResult(
            bucket_ts=context.regime_4h.bucket_ts,
            regime=BEARISH_TRENDING,
            is_compressed=None,
            price_evi=-REGIME_TREND_THRESHOLD,
            compression_score=None,
        )
    elif regime == NON_DIRECTIONAL:
        regime_result = V2RegimeResult(
            bucket_ts=context.regime_4h.bucket_ts,
            regime=NON_DIRECTIONAL,
            is_compressed=False,
            price_evi=0.0,
            compression_score=0.0,
        )
    else:
        raise ValueError(f"unsupported synthetic regime {regime!r}")

    if bias == BIAS_BULLISH:
        bias_result = V2BiasResult(
            bucket_ts=context.bias_1h.bucket_ts, bias=BIAS_BULLISH, bias_evi=0.25)
    elif bias == BIAS_BEARISH:
        bias_result = V2BiasResult(
            bucket_ts=context.bias_1h.bucket_ts, bias=BIAS_BEARISH, bias_evi=-0.25)
    elif bias == NEUTRAL_NOT_ESTABLISHED:
        bias_result = V2BiasResult(
            bucket_ts=context.bias_1h.bucket_ts,
            bias=NEUTRAL_NOT_ESTABLISHED,
            bias_evi=0.0,
        )
    else:
        raise ValueError(f"unsupported synthetic bias {bias!r}")

    return V2ContextSnapshot(
        T=context.T,
        symbol=context.symbol,
        market_type=context.market_type,
        calculation_version=context.calculation_version,
        feature_schema_version=context.feature_schema_version,
        regime_4h=regime_result,
        bias_1h=bias_result,
    )


def _neutral_context(context: V2ContextSnapshot) -> V2ContextSnapshot:
    return _synthetic_context(
        context, regime=NON_DIRECTIONAL, bias=NEUTRAL_NOT_ESTABLISHED)


def _row(*, variant: str, T: datetime, direction: str, candidate: Any = None,
         note: str | None = None) -> dict[str, Any]:
    return {
        "T": T.astimezone(UTC).isoformat(),
        "variant": variant,
        "direction": direction,
        "candidate": _jsonable(candidate) if candidate is not None else None,
        "note": note,
    }


def _dedup(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (row["variant"], row["T"], row["direction"])
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def _neutralize_taker_and_optional_agreement(
    inputs: V2CompressionBreakoutInputs, *, sign: int, force_agreement: bool,
    neutralize_context: bool,
) -> V2CompressionBreakoutInputs:
    if sign not in (-1, 1):
        raise ValueError(sign)
    changed_rows: list[Mapping] = []
    for source in inputs.consensus_5m_rows:
        row = copy.deepcopy(dict(source))
        coverage = copy.deepcopy(dict(row["coverage_by_metric"]))
        taker_cov = copy.deepcopy(dict(coverage["taker_flow"]))
        taker_cov["ratio"] = 1.0
        coverage["taker_flow"] = taker_cov
        confidence = copy.deepcopy(dict(row["data_confidence_by_metric"]))
        confidence["taker_flow"] = 100.0
        row["coverage_by_metric"] = coverage
        row["data_confidence_by_metric"] = confidence
        row["taker_delta_notional_usd_sum"] = float(sign)
        if force_agreement:
            row["price_direction_agreement"] = 1.0
        changed_rows.append(row)
    context = _neutral_context(inputs.context) if neutralize_context else inputs.context
    return replace(
        inputs,
        context=context,
        consensus_5m_rows=tuple(changed_rows),
    )


def _usable_reference_close(row: Mapping, *, expected_bars: int) -> float | None:
    if (
        row.get("is_usable") is True
        and row.get("has_gap") is False
        and row.get("bars_expected") == expected_bars
        and row.get("bars_present") == expected_bars
        and row.get("close_price") is not None
    ):
        value = row["close_price"]
        if isinstance(value, bool):
            raise RuntimeError("reference close_price cannot be bool")
        value = float(value)
        if value > 0.0:
            return value
    return None


def _ordinary_range_breakout(
    inputs: V2CompressionBreakoutInputs,
) -> str | None:
    """Frozen simple baseline: 16x15m full range + fresh 5m cross only."""
    context = inputs.context
    T = context.T
    B15 = selected_bucket("15m", T)
    B5 = selected_bucket("5m", T)
    grid = tuple(B15 - (15 - i) * FIFTEEN_MIN for i in range(16))

    ref15: dict[datetime, Mapping] = {}
    for row in inputs.reference_15m_rows:
        ts = row.get("bucket_ts")
        if ts in ref15:
            raise RuntimeError(f"duplicate 15m reference row at {ts}")
        if ts not in grid:
            raise RuntimeError(f"unexpected 15m reference row at {ts}")
        if (
            row.get("exchange") != "binance"
            or row.get("symbol") != context.symbol
            or row.get("market_type") != context.market_type
            or row.get("timeframe") != "15m"
            or row.get("calculation_version") != context.calculation_version
            or row.get("feature_schema_version") != context.feature_schema_version
        ):
            raise RuntimeError(f"15m reference identity mismatch at {ts}")
        ref15[ts] = row
    if len(ref15) != 16:
        return None

    raw_by_bucket: dict[datetime, list[Mapping]] = {b: [] for b in grid}
    grid_set = set(grid)
    for row in inputs.reference_1m_rows:
        ts = row.get("ts")
        if not isinstance(ts, datetime):
            raise RuntimeError("raw 1m ts must be datetime")
        owning = ts.replace(minute=(ts.minute // 15) * 15, second=0, microsecond=0)
        if owning in grid_set:
            raw_by_bucket[owning].append(row)

    highs: list[float] = []
    lows: list[float] = []
    for b in grid:
        try:
            extrema = derive_reference_extrema(
                timeframe="15m",
                bucket_ts=b,
                reference_feature=ref15[b],
                reference_klines=raw_by_bucket[b],
            )
        except Exception as exc:
            raise RuntimeError(f"ordinary-range extrema failed at {b.isoformat()}: {exc}") from exc
        if extrema is None:
            return None
        highs.append(extrema.high)
        lows.append(extrema.low)
    range_high = max(highs)
    range_low = min(lows)

    ref5: dict[datetime, float] = {}
    expected5 = {B5 - FIVE_MIN, B5}
    for row in inputs.reference_5m_rows:
        ts = row.get("bucket_ts")
        if ts not in expected5:
            raise RuntimeError(f"unexpected 5m reference row at {ts}")
        if (
            row.get("exchange") != "binance"
            or row.get("symbol") != context.symbol
            or row.get("market_type") != context.market_type
            or row.get("timeframe") != "5m"
            or row.get("calculation_version") != context.calculation_version
            or row.get("feature_schema_version") != context.feature_schema_version
        ):
            raise RuntimeError(f"5m reference identity mismatch at {ts}")
        close = _usable_reference_close(row, expected_bars=5)
        if close is not None:
            ref5[ts] = close
    if set(ref5) != expected5:
        return None

    previous = ref5[B5 - FIVE_MIN]
    current = ref5[B5]
    long_fresh = previous <= range_high and current > range_high
    short_fresh = previous >= range_low and current < range_low
    if long_fresh and short_fresh:
        raise RuntimeError("ordinary range breakout cannot be simultaneously LONG and SHORT")
    if long_fresh:
        return "LONG"
    if short_fresh:
        return "SHORT"
    return None


async def _evaluate_boundary(conn, args: argparse.Namespace, T: datetime) -> list[dict[str, Any]]:
    if not (DEV_START <= T < HOLDOUT_START):
        raise RuntimeError("ablation inventory attempted to leave development window")
    session = E1ResearchReadSession(
        conn,
        symbol=args.symbol,
        market_type=args.market_type,
        calculation_version=args.calculation_version,
        decision_boundary=T,
    )
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
    rows: list[dict[str, Any]] = []

    # TREND_PULLBACK -----------------------------------------------------
    tp_inputs = await load_trend_pullback_inputs(session, context=context)
    if tp_inputs is not None:
        full = detect_trend_pullback(tp_inputs)
        if full is not None:
            rows.append(_row(variant=TP_FULL, T=T, direction=full.direction, candidate=full))

        if context.bias_1h.bias == BIAS_BULLISH:
            c = _synthetic_context(context, regime=BULLISH_TRENDING, bias=BIAS_BULLISH)
            x = detect_trend_pullback(replace(tp_inputs, context=c))
            if x is not None:
                rows.append(_row(variant=TP_NO_4H, T=T, direction=x.direction, candidate=x))
        elif context.bias_1h.bias == BIAS_BEARISH:
            c = _synthetic_context(context, regime=BEARISH_TRENDING, bias=BIAS_BEARISH)
            x = detect_trend_pullback(replace(tp_inputs, context=c))
            if x is not None:
                rows.append(_row(variant=TP_NO_4H, T=T, direction=x.direction, candidate=x))

        if context.regime_4h.regime == BULLISH_TRENDING:
            c = _synthetic_context(context, regime=BULLISH_TRENDING, bias=BIAS_BULLISH)
            x = detect_trend_pullback(replace(tp_inputs, context=c))
            if x is not None:
                rows.append(_row(variant=TP_NO_1H, T=T, direction=x.direction, candidate=x))
        elif context.regime_4h.regime == BEARISH_TRENDING:
            c = _synthetic_context(context, regime=BEARISH_TRENDING, bias=BIAS_BEARISH)
            x = detect_trend_pullback(replace(tp_inputs, context=c))
            if x is not None:
                rows.append(_row(variant=TP_NO_1H, T=T, direction=x.direction, candidate=x))

        for regime, bias in (
            (BULLISH_TRENDING, BIAS_BULLISH),
            (BEARISH_TRENDING, BIAS_BEARISH),
        ):
            c = _synthetic_context(context, regime=regime, bias=bias)
            x = detect_trend_pullback(replace(tp_inputs, context=c))
            if x is not None:
                rows.append(_row(variant=TP_NO_CONTEXT, T=T, direction=x.direction, candidate=x))

    # COMPRESSION_BREAKOUT ---------------------------------------------
    cb_inputs = await load_compression_breakout_inputs(session, context=context)
    full_cb = detect_compression_breakout(cb_inputs)
    if full_cb is not None:
        rows.append(_row(variant=CB_FULL, T=T, direction=full_cb.direction, candidate=full_cb))

    for sign in (1, -1):
        x = detect_compression_breakout(_neutralize_taker_and_optional_agreement(
            cb_inputs, sign=sign, force_agreement=False, neutralize_context=False))
        if x is not None:
            rows.append(_row(variant=CB_NO_TAKER, T=T, direction=x.direction, candidate=x))

        y = detect_compression_breakout(_neutralize_taker_and_optional_agreement(
            cb_inputs, sign=sign, force_agreement=True, neutralize_context=True))
        if y is not None:
            rows.append(_row(variant=CB_SIMPLE, T=T, direction=y.direction, candidate=y))

    ordinary_direction = _ordinary_range_breakout(cb_inputs)
    if ordinary_direction is not None:
        rows.append(_row(
            variant=CB_ORDINARY,
            T=T,
            direction=ordinary_direction,
            note="16x15m full-range fresh-cross price-only baseline",
        ))

    # CONFIRMED_BREAKOUT -----------------------------------------------
    fb_inputs = await load_confirmed_breakout_inputs(session, context=context)
    full_fb = detect_confirmed_breakout(fb_inputs)
    if full_fb is not None:
        rows.append(_row(variant=FB_FULL, T=T, direction=full_fb.direction, candidate=full_fb))

    neutral = _neutral_context(context)
    noctx = detect_confirmed_breakout(replace(fb_inputs, context=neutral))
    if noctx is not None:
        rows.append(_row(variant=FB_NO_CONTEXT, T=T, direction=noctx.direction, candidate=noctx))
        rows.append(_row(
            variant=FB_DUMB,
            T=T,
            direction=noctx.direction,
            candidate=noctx,
            note="exact Stage-5 population alias of FB_NO_CONTEXT",
        ))

    return _dedup(rows)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    research_head = _assert_frozen_production_tree()
    boundaries = tuple(_iter_boundaries())
    db = Database(args.dsn)
    await db.connect()
    try:
        assert db.pool is not None
        rows: list[dict[str, Any]] = []
        async with db.pool.acquire() as conn:
            async with conn.transaction(isolation="repeatable_read", readonly=True):
                for i, T in enumerate(boundaries, 1):
                    rows.extend(await _evaluate_boundary(conn, args, T))
                    if args.progress_every and i % args.progress_every == 0:
                        print(
                            f"ablation inventory: {i}/{len(boundaries)} boundaries; "
                            f"{len(rows)} variant qualifications",
                            file=sys.stderr,
                            flush=True,
                        )
    finally:
        await db.close()

    by_variant = Counter(r["variant"] for r in rows)
    by_variant_direction = Counter((r["variant"], r["direction"]) for r in rows)
    return {
        "study": "E1-RUN-001",
        "kind": "DEVELOPMENT_ABLATION_INVENTORY_NO_OUTCOMES",
        "frozen_production_base_sha": FROZEN_PRODUCTION_BASE_SHA,
        "research_head_sha": research_head,
        "protocol": "docs/e1/E1_RUN_001_ABLATION_PROTOCOL_FREEZE.md",
        "symbol": args.symbol,
        "market_type": args.market_type,
        "calculation_version": args.calculation_version,
        "feature_schema_version": args.feature_schema_version,
        "development_window": {
            "start_inclusive": DEV_START.isoformat(),
            "end_exclusive": HOLDOUT_START.isoformat(),
            "boundaries": len(boundaries),
        },
        "holdout_outcomes_opened": False,
        "holdout_market_rows_read": False,
        "outcomes_included": False,
        "summary": {
            "total_variant_qualifications": len(rows),
            "by_variant": {v: by_variant.get(v, 0) for v in VARIANTS},
            "by_variant_direction": {
                f"{v}:{d}": by_variant_direction.get((v, d), 0)
                for v in VARIANTS for d in ("LONG", "SHORT")
            },
        },
        "rows": rows,
    }


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Inventory frozen E1 development ablations without outcomes")
    p.add_argument("--dsn", required=True)
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--market-type", default="perp")
    p.add_argument("--calculation-version", required=True)
    p.add_argument("--feature-schema-version", type=int, default=1)
    p.add_argument("--health-exchanges", nargs="+", required=True)
    p.add_argument("--health-metrics", nargs="+", required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--progress-every", type=int, default=500)
    return p


def main() -> int:
    args = _parser().parse_args()
    payload = asyncio.run(_run(args))
    _write_json_atomic(args.output, payload)
    print(json.dumps(payload["summary"], sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
