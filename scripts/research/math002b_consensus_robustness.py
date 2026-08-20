#!/usr/bin/env python3
"""MATH-002B / issue #52 -- historical 3/3 vs 2/3 Stage 2 consensus
robustness study.

READ-ONLY. This script never INSERTs/UPDATEs/DELETEs, runs no DDL, and
opens every database transaction as `READ ONLY` explicitly (defense in
depth on top of only ever issuing SELECTs). It never touches production
Stage 2 tables' contents -- it only reads `exchange_feature_vectors` and
recomputes controlled consensus variants IN MEMORY via the real, unmodified
`analytics.feature_engine.consensus.compute_consensus_features`.

Usage:
    python -m scripts.research.math002b_consensus_robustness --check-access
    python -m scripts.research.math002b_consensus_robustness --symbol BTCUSDT \\
        --market-type perp --timeframe 4h --family price_structure \\
        --out /tmp/math002b_4h_price_structure.json

`--check-access` only verifies read-only connectivity to the configured
Postgres instance and exits -- it makes no other query and writes nothing.
If the database is unreachable, it prints `DATA_ACCESS_BLOCKED` and exits
non-zero; this is the honest, expected outcome in an environment with no
provisioned historical Postgres instance (this is NOT a failure of the
harness itself).

Frozen posture (MATH-002B task, sections 6/8/18/23):
* `minimum_exchange_coverage` for the real FULL3/BB/BO/BYO consensus
  requests is ALWAYS 2 (the current production value) -- never silently
  lowered.
* The `BINANCE_ONLY_RESEARCH_BASELINE` diagnostic uses a SEPARATE request
  construction path with `minimum_exchange_coverage=1`, labeled explicitly
  as research-only, and is never presented as production `2/3` behavior.
* No percentile/regime/bias/setup replay is implemented here -- see
  `docs/V2_CONSENSUS_ROBUSTNESS_HISTORICAL_AUDIT.md` for why (no real
  historical database was reachable to validate that additional layer
  against, and building it unvalidated would be "fake infrastructure
  merely to produce a number", which the task explicitly forbids).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime
from typing import Any, Optional

from analytics.feature_engine.consensus import compute_consensus_features
from analytics.feature_engine.consensus_models import FAMILIES, ConsensusFeatureRequest
from analytics.feature_engine.models import ExchangeFeatureVector
from analytics.forecasting_v2.regime_4h import REGIME_MIN_CONFIDENCE, REGIME_MIN_COVERAGE
from scripts.research.math002b_lib import (
    BB,
    BINANCE_ONLY,
    BO,
    BYO,
    FULL3,
    PairComparison,
    outlier_report_flip_rate,
    quality_gate_flip_rate,
    sign_flip_rate,
    summarize,
)

EXCHANGES = ("binance", "bybit", "okx")
PAIRS = {BB: ("binance", "bybit"), BO: ("binance", "okx"), BYO: ("bybit", "okx")}
TIMEFRAMES = ("4h", "1h", "15m", "5m")
_STUDY_FAMILIES = ("price_structure", "oi")
_WEIGHTS = {"coverage": 0.50, "agreement": 0.30, "dispersion": 0.20}
_ROBUST_Z_THRESHOLD = 3.5


def _omitted(pair_name: str) -> str:
    contributing = set(PAIRS[pair_name])
    (omitted,) = (ex for ex in EXCHANGES if ex not in contributing)
    return omitted


# ---- exact-3/3 bucket discovery (read-only SQL) ----------------------------
_EXACT_3OF3_PRICE_SQL = """
    SELECT bucket_ts
    FROM exchange_feature_vectors
    WHERE symbol = $1 AND market_type = $2 AND timeframe = $3
      AND calculation_version = $4
      AND price_move_pct IS NOT NULL
      AND range_width_pct IS NOT NULL
      AND close_price IS NOT NULL
      AND is_usable = TRUE
    GROUP BY bucket_ts
    HAVING COUNT(DISTINCT exchange) = 3
    ORDER BY bucket_ts
"""

_EXACT_3OF3_OI_SQL = """
    SELECT bucket_ts
    FROM exchange_feature_vectors
    WHERE symbol = $1 AND market_type = $2 AND timeframe = $3
      AND calculation_version = $4
      AND oi_change_pct IS NOT NULL
    GROUP BY bucket_ts
    HAVING COUNT(DISTINCT exchange) = 3
    ORDER BY bucket_ts
"""

_ROWS_FOR_BUCKET_SQL = """
    SELECT * FROM exchange_feature_vectors
    WHERE symbol = $1 AND market_type = $2 AND timeframe = $3
      AND calculation_version = $4 AND bucket_ts = $5
"""


def _row_to_efv(row: Any) -> ExchangeFeatureVector:
    """Build a real `ExchangeFeatureVector` from one `exchange_feature_vectors`
    row -- field-for-field, no coercion, no defaulting of a NULL to a
    synthetic value."""
    d = dict(row)
    return ExchangeFeatureVector(**{
        f: d[f] for f in (
            "exchange", "symbol", "market_type", "timeframe", "bucket_ts",
            "feature_schema_version", "calculation_version", "price_move_pct",
            "range_width_pct", "close_price", "volume_raw", "volume_raw_unit",
            "volume_notional_usd", "taker_buy_notional_usd",
            "taker_sell_notional_usd", "taker_delta_notional_usd",
            "cvd_delta_notional_usd", "oi_change_pct", "oi_unit",
            "funding_rate", "long_liquidation_notional",
            "short_liquidation_notional", "liquidation_event_count",
            "liquidation_feed_quality", "is_snapshot_feed", "bars_expected",
            "bars_present", "has_gap", "is_usable", "config_hash",
            "config_version", "code_version",
        )
    })


def _build_request(
    efvs: list[ExchangeFeatureVector], *, minimum_exchange_coverage: int,
) -> ConsensusFeatureRequest:
    present = {e.exchange for e in efvs}
    missing = tuple(ex for ex in EXCHANGES if ex not in present)
    exclusions = {
        family: {ex: "MATH002B_HISTORICAL_VARIANT_OMISSION" for ex in missing}
        for family in FAMILIES if missing
    }
    any_efv = efvs[0]
    return ConsensusFeatureRequest(
        symbol=any_efv.symbol, market_type=any_efv.market_type,
        timeframe=any_efv.timeframe, bucket_ts=any_efv.bucket_ts,
        feature_schema_version=any_efv.feature_schema_version,
        calculation_version=any_efv.calculation_version,
        config_hash=any_efv.config_hash, config_version=any_efv.config_version,
        code_version=any_efv.code_version,
        exchange_features=efvs,
        expected_exchanges_by_family={family: EXCHANGES for family in FAMILIES},
        exclusion_reasons_by_family=exclusions,
        minimum_exchange_coverage=minimum_exchange_coverage,
        confidence_weights=_WEIGHTS,
        robust_z_threshold=_ROBUST_Z_THRESHOLD,
    )


def _outlier_metric_for_family(family: str) -> Optional[str]:
    return {"price_structure": "price_move_pct", "oi": "oi_change_pct"}.get(family)


def compare_bucket(
    efv_by_exchange: dict[str, ExchangeFeatureVector], *, family: str, timeframe: str,
) -> list[PairComparison]:
    """Recompute FULL3 and every BB/BO/BYO variant for ONE exact-3/3 bucket
    and return the three `PairComparison`s. Pure with respect to I/O -- the
    caller already fetched `efv_by_exchange` read-only."""
    all_three = [efv_by_exchange[ex] for ex in EXCHANGES]
    full3 = compute_consensus_features(
        _build_request(all_three, minimum_exchange_coverage=2))

    metric = _outlier_metric_for_family(family)
    full3_has_outlier = metric is not None and metric in full3.outlier_exchanges
    median_field = {"price_structure": "price_move_pct_median", "oi": "oi_change_pct_median"}[family]
    agreement_field = {"price_structure": "price_direction_agreement", "oi": "oi_direction_agreement"}[family]
    mad_field = {"price_structure": "price_move_pct_mad", "oi": "oi_change_pct_mad"}[family]

    full3_quality_pass = (
        full3.coverage_by_metric[family].ratio >= REGIME_MIN_COVERAGE
        and full3.data_confidence_by_metric[family] >= REGIME_MIN_CONFIDENCE
    )

    comparisons: list[PairComparison] = []
    for pair_name, pair_exchanges in PAIRS.items():
        pair_efvs = [efv_by_exchange[ex] for ex in pair_exchanges]
        pair = compute_consensus_features(
            _build_request(pair_efvs, minimum_exchange_coverage=2))
        pair_has_outlier = metric is not None and metric in pair.outlier_exchanges
        pair_quality_pass = (
            pair.coverage_by_metric[family].ratio >= REGIME_MIN_COVERAGE
            and pair.data_confidence_by_metric[family] >= REGIME_MIN_CONFIDENCE
        )
        comparisons.append(PairComparison(
            bucket_ts=all_three[0].bucket_ts, timeframe=timeframe, family=family,
            pair_name=pair_name, omitted_venue=_omitted(pair_name),
            full3_median=getattr(full3, median_field), pair_median=getattr(pair, median_field),
            full3_mad=getattr(full3, mad_field), pair_mad=getattr(pair, mad_field),
            full3_agreement=getattr(full3, agreement_field),
            pair_agreement=getattr(pair, agreement_field),
            full3_confidence=full3.data_confidence_by_metric[family],
            pair_confidence=pair.data_confidence_by_metric[family],
            full3_has_outlier=full3_has_outlier, pair_has_outlier=pair_has_outlier,
            full3_quality_gate_pass=full3_quality_pass,
            pair_quality_gate_pass=pair_quality_pass,
        ))
    return comparisons


async def _check_access(dsn: str) -> bool:
    try:
        import asyncpg
    except ImportError:
        print("DATA_ACCESS_BLOCKED: asyncpg not installed", file=sys.stderr)
        return False
    try:
        conn = await asyncpg.connect(dsn, timeout=5)
    except Exception as exc:  # noqa: BLE001 -- any connection failure is DATA_ACCESS_BLOCKED
        print(f"DATA_ACCESS_BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return False
    try:
        async with conn.transaction(readonly=True):
            await conn.fetchval("SELECT 1")
    finally:
        await conn.close()
    return True


async def run_study(
    dsn: str, *, symbol: str, market_type: str, timeframe: str, family: str,
    calculation_version: str,
) -> dict:
    import asyncpg  # local import: never required unless actually running the DB study

    if family not in _STUDY_FAMILIES:
        raise ValueError(f"family must be one of {_STUDY_FAMILIES}, got {family!r}")

    sql = _EXACT_3OF3_PRICE_SQL if family == "price_structure" else _EXACT_3OF3_OI_SQL

    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        async with conn.transaction(readonly=True):
            bucket_rows = await conn.fetch(sql, symbol, market_type, timeframe, calculation_version)
            all_comparisons: list[PairComparison] = []
            for brow in bucket_rows:
                rows = await conn.fetch(
                    _ROWS_FOR_BUCKET_SQL, symbol, market_type, timeframe,
                    calculation_version, brow["bucket_ts"])
                efv_by_exchange = {r["exchange"]: _row_to_efv(r) for r in rows}
                if set(efv_by_exchange) != set(EXCHANGES):
                    continue  # defensive -- HAVING COUNT(DISTINCT exchange)=3 already guarantees this
                all_comparisons.extend(
                    compare_bucket(efv_by_exchange, family=family, timeframe=timeframe))
    finally:
        await conn.close()

    return _summarize_study(
        symbol=symbol, market_type=market_type, timeframe=timeframe, family=family,
        complete_3of3_bucket_count=len(bucket_rows), comparisons=all_comparisons,
    )


def _summarize_study(
    *, symbol: str, market_type: str, timeframe: str, family: str,
    complete_3of3_bucket_count: int, comparisons: list[PairComparison],
) -> dict:
    by_pair: dict[str, list[PairComparison]] = {p: [] for p in PAIRS}
    for c in comparisons:
        by_pair[c.pair_name].append(c)

    out: dict[str, Any] = {
        "symbol": symbol, "market_type": market_type, "timeframe": timeframe,
        "family": family, "complete_3of3_bucket_count": complete_3of3_bucket_count,
        "pairs": {},
    }
    for pair_name, pair_comparisons in by_pair.items():
        abs_deltas = [c.absolute_median_delta for c in pair_comparisons
                      if c.absolute_median_delta is not None]
        out["pairs"][pair_name] = {
            "n": len(pair_comparisons),
            "absolute_median_delta": asdict(summarize(abs_deltas)),
            "sign_flip_rate": sign_flip_rate(pair_comparisons),
            "outlier_report_flip_rate": outlier_report_flip_rate(pair_comparisons),
            "quality_gate_flip_rate": quality_gate_flip_rate(pair_comparisons),
        }
    return out


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-access", action="store_true",
                        help="only verify read-only DB connectivity, then exit")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--market-type", default="perp")
    parser.add_argument("--timeframe", choices=TIMEFRAMES, default="4h")
    parser.add_argument("--family", choices=_STUDY_FAMILIES, default="price_structure")
    parser.add_argument("--calculation-version", required=False,
                        help="exact Stage2 calculation_version to study (required unless --check-access)")
    parser.add_argument("--out", default=None, help="write JSON summary here (default: stdout only)")
    args = parser.parse_args()

    from common.config import Config, load_secrets
    cfg = Config.load()
    secrets = load_secrets(cfg)
    dsn = secrets.postgres_dsn

    if args.check_access:
        ok = asyncio.run(_check_access(dsn))
        if not ok:
            return 1
        print("DB read-only connectivity OK.")
        return 0

    if not args.calculation_version:
        parser.error("--calculation-version is required unless --check-access is passed")

    result = asyncio.run(run_study(
        dsn, symbol=args.symbol, market_type=args.market_type, timeframe=args.timeframe,
        family=args.family, calculation_version=args.calculation_version))
    text = json.dumps(result, indent=2, default=str)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
