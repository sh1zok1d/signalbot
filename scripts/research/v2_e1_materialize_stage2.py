#!/usr/bin/env python3
"""Research-only Stage-2 materialization for E1-RUN-001.

Writes ONLY derived Stage-2 rows under the calculation_version implied by the
frozen feature-computation code/config. It never mutates raw Stage-1 tables and
never overwrites another calculation_version namespace.

Why this exists: the VPS has raw/live history but only an older 5m Stage-2
namespace. E1 needs coherent 5m/15m/1h/4h features plus the exact percentile
rows consumed by frozen Stage 4/5. We recompute them with the real production
feature/consensus/percentile cores instead of copying old rows or duplicating
formulas in SQL.

The VPS predates exchange_instrument_history. This harness therefore permits the
current exchange_instruments LKG ONLY when its fetched_at is already <= the
materialization start. That is an explicit fail-closed no-lookahead condition;
if it is not true, the run aborts before any derived write.

Historical liquidation connection state is not reconstructible, so the harness
sets liquidation_feed_available=False. Current frozen V2 Stage 4/5 does not use
liquidations; this avoids turning historical absence into fabricated measured
zeroes.
"""
from __future__ import annotations

import argparse
import asyncio
import bisect
import os
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any

from analytics.feature_engine.bucket_coordinator import _derive_family_exclusions
from analytics.feature_engine.consensus import compute_consensus_features
from analytics.feature_engine.consensus_input_adapter import build_consensus_feature_request
from analytics.feature_engine.consensus_models import FAMILIES
from analytics.feature_engine.exchange_features import compute_exchange_features
from analytics.feature_engine.input_adapter import load_exchange_feature_request
from analytics.feature_engine.models import TIMEFRAME_MINUTES
from analytics.percentile_engine.compute import compute_percentile_snapshot
from analytics.percentile_engine.models import (
    ConfidenceTierThresholds,
    PercentileRequest,
    PercentileSample,
    WINDOW_TIMEDELTAS,
)
from common.stage2_config import Stage2Config
from common.versioning import compute_calculation_version, resolve_feature_code_version
from storage.db import Database
from storage.stage2_readers import ExchangeFeatureRawBundle

UTC = timezone.utc
EXCHANGES = ("binance", "bybit", "okx")
TIMEFRAMES = ("5m", "15m", "1h", "4h")
BATCH = 500

# Exactly the consensus-scope percentile rows frozen Stage 4/5 consumes.
PERCENTILE_SPECS = (
    ("4h", "price_move_pct_median", "30d"),
    ("4h", "range_width_pct_median", "30d"),
    ("4h", "oi_change_pct_median", "30d"),
    ("1h", "price_move_pct_median", "7d"),
    ("15m", "range_width_pct_median", "30d"),
)


def _parse_utc(text: str) -> datetime:
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO-8601 datetime: {text!r}") from exc
    if dt.tzinfo is None or dt.utcoffset() is None or dt.utcoffset() != timedelta(0):
        raise argparse.ArgumentTypeError("datetime must be timezone-aware UTC")
    if dt.second or dt.microsecond:
        raise argparse.ArgumentTypeError("datetime must be on a whole minute")
    return dt.astimezone(UTC)


def _freeze(record: Mapping | Any) -> Mapping:
    return MappingProxyType(dict(record))


def _aligned(dt: datetime, timeframe: str) -> bool:
    if timeframe == "5m":
        return dt.minute % 5 == 0
    if timeframe == "15m":
        return dt.minute % 15 == 0
    if timeframe == "1h":
        return dt.minute == 0
    if timeframe == "4h":
        return dt.minute == 0 and dt.hour % 4 == 0
    raise ValueError(timeframe)


def _first_aligned(start: datetime, timeframe: str) -> datetime:
    cur = start
    while not _aligned(cur, timeframe):
        cur += timedelta(minutes=1)
    return cur


def _bucket_starts(start: datetime, end: datetime, timeframe: str):
    width = timedelta(minutes=TIMEFRAME_MINUTES[timeframe])
    cur = _first_aligned(start, timeframe)
    while cur + width <= end:
        yield cur
        cur += width


class CachedRawReader:
    """In-memory implementation of the production RawBundleReader protocol.

    It preserves the production reader's exact half-open bucket semantics and
    latest-funding-strictly-before-end rule while avoiding tens of thousands of
    round-trips during the historical replay.
    """

    def __init__(self, *, rows: dict, instruments: dict, capabilities: dict,
                 required_metadata_revision: int):
        self.rows = rows
        self.instruments = instruments
        self.capabilities = capabilities
        self.required_metadata_revision = required_metadata_revision

    @staticmethod
    def _slice(items: tuple[Mapping, ...], timestamps: tuple[datetime, ...],
               start: datetime, end: datetime) -> tuple[Mapping, ...]:
        lo = bisect.bisect_left(timestamps, start)
        hi = bisect.bisect_left(timestamps, end)
        return items[lo:hi]

    async def fetch_exchange_feature_raw_bundle(
        self, *, exchange: str, symbol: str, market_type: str,
        bucket_start: datetime, bucket_end: datetime,
    ) -> ExchangeFeatureRawBundle:
        key = (exchange, symbol)
        data = self.rows[key]
        klines = self._slice(data["klines"], data["klines_ts"], bucket_start, bucket_end)
        oi = self._slice(data["oi"], data["oi_ts"], bucket_start, bucket_end)

        funding_items = data["funding"]
        funding_ts = data["funding_ts"]
        idx = bisect.bisect_left(funding_ts, bucket_end) - 1
        latest_funding = funding_items[idx] if idx >= 0 else None

        return ExchangeFeatureRawBundle(
            klines=klines,
            open_interest=oi,
            latest_funding=latest_funding,
            liquidations=(),
            instrument=self.instruments.get((exchange, symbol, market_type)),
            liquidation_capability=self.capabilities.get((exchange, symbol, market_type)),
            required_metadata_revision=self.required_metadata_revision,
        )


async def _load_raw_cache(db: Database, *, symbol: str, market_type: str,
                          start: datetime, end: datetime,
                          required_metadata_revision: int) -> CachedRawReader:
    rows: dict = {}
    instruments: dict = {}
    capabilities: dict = {}

    for exchange in EXCHANGES:
        klines = tuple(_freeze(r) for r in await db.fetch(
            """
            SELECT exchange, symbol, ts, open, high, low, close, volume,
                   taker_buy_volume, taker_sell_volume
            FROM klines_1m
            WHERE exchange=$1 AND symbol=$2 AND ts >= $3 AND ts < $4
            ORDER BY ts ASC
            """,
            exchange, symbol, start, end,
        ))
        oi = tuple(_freeze(r) for r in await db.fetch(
            """
            SELECT exchange, symbol, ts, oi_raw, oi_unit
            FROM open_interest
            WHERE exchange=$1 AND symbol=$2 AND ts >= $3 AND ts < $4
            ORDER BY ts ASC
            """,
            exchange, symbol, start, end,
        ))
        # Latest-before semantics need observations that may predate materialize start.
        funding = tuple(_freeze(r) for r in await db.fetch(
            """
            SELECT exchange, symbol, ts, funding_rate
            FROM funding_rate
            WHERE exchange=$1 AND symbol=$2 AND ts < $3
            ORDER BY ts ASC
            """,
            exchange, symbol, end,
        ))
        instrument_rows = await db.fetch(
            """
            SELECT exchange, symbol, market_type, exchange_instrument_id,
                   quantity_unit, contract_multiplier, tick_size,
                   price_precision, quantity_precision, metadata_source,
                   fetched_at, is_stale, note
            FROM exchange_instruments
            WHERE exchange=$1 AND symbol=$2 AND market_type=$3
            """,
            exchange, symbol, market_type,
        )
        if len(instrument_rows) != 1:
            raise RuntimeError(
                f"expected exactly one current instrument row for {exchange}/{symbol}/{market_type}, "
                f"got {len(instrument_rows)}")
        instrument = _freeze(instrument_rows[0])
        fetched_at = instrument.get("fetched_at")
        if fetched_at is None or fetched_at > start:
            raise RuntimeError(
                f"NO_LOOKAHEAD_REFUSAL: current instrument LKG for {exchange} has "
                f"fetched_at={fetched_at!r}, which is not proven available by materialization "
                f"start={start!r}; exchange_instrument_history is absent, so refusing to "
                "back-project this metadata")

        capability_rows = await db.fetch(
            """
            SELECT exchange, symbol, market_type, metric, live_supported,
                   historical_supported, coverage_type, expected_freshness_s, enabled
            FROM symbol_exchange_capabilities
            WHERE exchange=$1 AND symbol=$2 AND market_type=$3 AND metric='liquidations'
            """,
            exchange, symbol, market_type,
        )
        capability = _freeze(capability_rows[0]) if len(capability_rows) == 1 else None

        rows[(exchange, symbol)] = {
            "klines": klines,
            "klines_ts": tuple(r["ts"] for r in klines),
            "oi": oi,
            "oi_ts": tuple(r["ts"] for r in oi),
            "funding": funding,
            "funding_ts": tuple(r["ts"] for r in funding),
        }
        instruments[(exchange, symbol, market_type)] = instrument
        capabilities[(exchange, symbol, market_type)] = capability
        print(
            f"raw-cache {exchange}: klines={len(klines)} oi={len(oi)} "
            f"funding={len(funding)} instrument_fetched_at={fetched_at.isoformat()}",
            flush=True,
        )

    return CachedRawReader(
        rows=rows,
        instruments=instruments,
        capabilities=capabilities,
        required_metadata_revision=required_metadata_revision,
    )


def _exclusions(efvs: list) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {family: {} for family in FAMILIES}
    for efv in efvs:
        for family, reason in _derive_family_exclusions(efv).items():
            result[family][efv.exchange] = reason
    return result


async def _materialize_features(db: Database, reader: CachedRawReader, cfg: Stage2Config,
                                *, symbol: str, market_type: str, start: datetime,
                                end: datetime, code_version: str) -> dict[str, list]:
    consensus_by_tf: dict[str, list] = defaultdict(list)

    for timeframe in TIMEFRAMES:
        buckets = list(_bucket_starts(start, end, timeframe))
        efv_batch = []
        cfv_batch = []
        for index, bucket_ts in enumerate(buckets, start=1):
            efvs = []
            for exchange in EXCHANGES:
                request = await load_exchange_feature_request(
                    reader,
                    cfg,
                    exchange=exchange,
                    symbol=symbol,
                    market_type=market_type,
                    timeframe=timeframe,
                    bucket_ts=bucket_ts,
                    code_version=code_version,
                    # We cannot reconstruct historical liquidation-connection state.
                    # Unavailable is safer than fabricating measured zeroes.
                    liquidation_feed_available=False,
                )
                efv = compute_exchange_features(request)
                efvs.append(efv)
                efv_batch.append(efv)

            cf_req = build_consensus_feature_request(
                cfg,
                exchange_features=efvs,
                expected_exchanges_by_family={family: EXCHANGES for family in FAMILIES},
                exclusion_reasons_by_family=_exclusions(efvs),
            )
            cfv = compute_consensus_features(cf_req)
            consensus_by_tf[timeframe].append(cfv)
            cfv_batch.append(cfv)

            if len(efv_batch) >= BATCH:
                await db.upsert_exchange_feature_vectors(tuple(efv_batch))
                efv_batch.clear()
            if len(cfv_batch) >= BATCH:
                await db.upsert_consensus_feature_vectors(tuple(cfv_batch))
                cfv_batch.clear()
            if index % 500 == 0:
                print(f"materialize {timeframe}: {index}/{len(buckets)} buckets", flush=True)

        if efv_batch:
            await db.upsert_exchange_feature_vectors(tuple(efv_batch))
        if cfv_batch:
            await db.upsert_consensus_feature_vectors(tuple(cfv_batch))
        print(f"materialize {timeframe}: COMPLETE buckets={len(buckets)}", flush=True)

    return consensus_by_tf


async def _materialize_percentiles(db: Database, cfg: Stage2Config, *, symbol: str,
                                   market_type: str, code_version: str,
                                   calculation_version: str,
                                   consensus_by_tf: dict[str, list]) -> int:
    resolved = cfg.resolve(symbol)
    tier_cfg = resolved["percentiles"]["confidence_tiers"]
    thresholds = ConfidenceTierThresholds(
        none_below_days=tier_cfg["none_below_days"],
        low_below_days=tier_cfg["low_below_days"],
        building_below_days=tier_cfg["building_below_days"],
    )
    total = 0
    batch = []

    for timeframe, metric, window in PERCENTILE_SPECS:
        series = consensus_by_tf[timeframe]
        timestamps = [row.bucket_ts for row in series]
        delta = WINDOW_TIMEDELTAS[window]

        for idx, row in enumerate(series):
            lower = row.bucket_ts - delta
            lo = bisect.bisect_left(timestamps, lower, 0, idx)
            samples = tuple(
                PercentileSample(
                    scope="consensus",
                    exchange="",
                    symbol=symbol,
                    market_type=market_type,
                    metric=metric,
                    timeframe=timeframe,
                    bucket_ts=prior.bucket_ts,
                    value=getattr(prior, metric),
                    feature_schema_version=cfg.feature_schema_version,
                    calculation_version=calculation_version,
                )
                for prior in series[lo:idx]
            )
            req = PercentileRequest(
                scope="consensus",
                exchange="",
                symbol=symbol,
                market_type=market_type,
                metric=metric,
                timeframe=timeframe,
                percentile_window=window,
                bucket_ts=row.bucket_ts,
                value=getattr(row, metric),
                samples=samples,
                confidence_tier_thresholds=thresholds,
                config_hash=resolved.config_hash(),
                config_version=cfg.config_version,
                code_version=code_version,
                feature_schema_version=cfg.feature_schema_version,
                calculation_version=calculation_version,
            )
            batch.append(compute_percentile_snapshot(req))
            total += 1
            if len(batch) >= BATCH:
                await db.upsert_percentile_snapshots(tuple(batch))
                batch.clear()

        print(f"percentiles {timeframe}/{metric}/{window}: rows={len(series)}", flush=True)

    if batch:
        await db.upsert_percentile_snapshots(tuple(batch))
    return total


async def _require_clean_target_namespace(db: Database, *, symbol: str, market_type: str,
                                          calculation_version: str, resume: bool) -> None:
    counts = {}
    for table in ("exchange_feature_vectors", "consensus_feature_vectors", "percentile_snapshots"):
        counts[table] = await db.fetchval(
            f"SELECT count(*) FROM {table} WHERE symbol=$1 AND market_type=$2 "
            "AND calculation_version=$3",
            symbol, market_type, calculation_version,
        )
    print("target namespace existing rows:", counts, flush=True)
    if not resume and any(counts.values()):
        raise RuntimeError(
            "target calculation_version already contains derived rows; rerun with --resume only "
            "after verifying they belong to this exact E1 materialization")


async def _run(args: argparse.Namespace) -> None:
    cfg = Stage2Config.load()
    resolved = cfg.resolve(args.symbol)
    code_version = resolve_feature_code_version(repo_root=Path(args.repo_root))
    calculation_version = compute_calculation_version(
        cfg.feature_schema_version, resolved.config_hash(), code_version)
    if calculation_version != args.expected_calculation_version:
        raise RuntimeError(
            f"calculation_version mismatch: derived {calculation_version}, expected "
            f"{args.expected_calculation_version}")
    if args.end <= args.start:
        raise RuntimeError("--end must be after --start")

    print(f"feature_code_version={code_version}", flush=True)
    print(f"config_hash={resolved.config_hash()}", flush=True)
    print(f"calculation_version={calculation_version}", flush=True)
    print(f"window=[{args.start.isoformat()}, {args.end.isoformat()})", flush=True)

    db = Database(args.dsn)
    await db.connect()
    try:
        await _require_clean_target_namespace(
            db,
            symbol=args.symbol,
            market_type=args.market_type,
            calculation_version=calculation_version,
            resume=args.resume,
        )
        reader = await _load_raw_cache(
            db,
            symbol=args.symbol,
            market_type=args.market_type,
            start=args.start,
            end=args.end,
            required_metadata_revision=cfg.instrument_metadata_revision,
        )
        consensus_by_tf = await _materialize_features(
            db,
            reader,
            cfg,
            symbol=args.symbol,
            market_type=args.market_type,
            start=args.start,
            end=args.end,
            code_version=code_version,
        )
        percentile_rows = await _materialize_percentiles(
            db,
            cfg,
            symbol=args.symbol,
            market_type=args.market_type,
            code_version=code_version,
            calculation_version=calculation_version,
            consensus_by_tf=consensus_by_tf,
        )

        print(f"MATERIALIZATION_COMPLETE percentile_rows={percentile_rows}", flush=True)
        for timeframe in TIMEFRAMES:
            efv = await db.fetchval(
                "SELECT count(*) FROM exchange_feature_vectors WHERE symbol=$1 AND market_type=$2 "
                "AND timeframe=$3 AND calculation_version=$4",
                args.symbol, args.market_type, timeframe, calculation_version,
            )
            cfv = await db.fetchval(
                "SELECT count(*) FROM consensus_feature_vectors WHERE symbol=$1 AND market_type=$2 "
                "AND timeframe=$3 AND calculation_version=$4",
                args.symbol, args.market_type, timeframe, calculation_version,
            )
            print(f"rows {timeframe}: exchange={efv} consensus={cfv}", flush=True)
    finally:
        await db.close()


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Materialize isolated Stage-2 history for E1-RUN-001")
    p.add_argument("--dsn", default=os.getenv("DATABASE_URL"))
    p.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--market-type", default="perp")
    p.add_argument("--start", required=True, type=_parse_utc)
    p.add_argument("--end", required=True, type=_parse_utc)
    p.add_argument("--expected-calculation-version", required=True)
    p.add_argument("--resume", action="store_true")
    return p


def main() -> int:
    args = _parser().parse_args()
    if not args.dsn:
        raise SystemExit("--dsn or DATABASE_URL is required")
    asyncio.run(_run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
