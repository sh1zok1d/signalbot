"""
Stage 2.1 Exchange Feature input adapter: bridge Stage 1 raw rows to ONE valid,
deterministic `ExchangeFeatureRequest` for the pure feature core.

Two layers:
  * `build_assembly_context` (+ `assemble_exchange_feature_request`) — PURE: no
    DB, network, clock, env, subprocess, Redis, filesystem, logging side effects,
    or mutable module state. Deterministic; input order does not matter.
  * `load_exchange_feature_request` — async orchestration facing: validates and
    resolves a deterministic context, then calls the supplied raw reader exactly
    once and assembles the request. It writes nothing, initializes no schema,
    sleeps/retries/loops never, and reads no wall clock.

The caller supplies an already-resolved `code_version` (no environment/subprocess
dependence) and the runtime `liquidation_feed_available` fact.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_CEILING
from typing import Mapping, Optional, Protocol

from common.instrument_metadata import InstrumentMetadata
from common.stage2_config import Stage2Config
from common.versioning import compute_calculation_version
from symbols.registry import ACTIVE_EXCHANGES, active_symbols

from .models import (
    ExchangeFeatureRequest, FundingObservation, KlineBar, LiquidationEvent,
    LiquidationFeedState, LIQUIDATION_SIDES,
    OpenInterestObservation, SUPPORTED_MARKET_TYPES, TIMEFRAME_MINUTES,
)

_INSTRUMENT_SOURCES = ("exchange_api", "declared_fallback", "manual")
_QUANTITY_UNITS = ("base", "contracts")
# Authoritative liquidations LIVE coverage types for the active Stage 2 venues —
# 'unavailable' is drift (live liquidation feeds exist on all three venues).
_LIQ_LIVE_COVERAGE_TYPES = ("snapshot", "full", "aggregated")
_MISSING = object()


class FeatureInputError(ValueError):
    """Invalid context / raw row that must fail loudly during assembly (never
    silently coerced, dropped, defaulted, or synthesized)."""


# ---- narrow reader protocol (no concrete Database import here) --------------
class RawBundleReader(Protocol):
    async def fetch_exchange_feature_raw_bundle(
        self, *, exchange: str, symbol: str, market_type: str,
        bucket_start: datetime, bucket_end: datetime,
    ): ...


# ---- deterministic assembly context (pure; DB-independent) ------------------
@dataclass(frozen=True)
class AssemblyContext:
    exchange: str
    symbol: str
    market_type: str
    timeframe: str
    bucket_ts: datetime
    bucket_end: datetime
    feature_schema_version: int
    calculation_version: str
    config_hash: str
    config_version: str
    code_version: str
    allowed_missing_bars: int
    liquidation_feed_available: bool


# ---- small validators -------------------------------------------------------
def _utc_whole_minute(dt, name: str) -> datetime:
    if not isinstance(dt, datetime):
        raise FeatureInputError(f"{name} must be a datetime, got {type(dt).__name__}")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise FeatureInputError(f"{name} must be timezone-aware")
    if dt.utcoffset() != timedelta(0):
        raise FeatureInputError(f"{name} must be UTC (offset 0), got {dt.utcoffset()}")
    if dt.second != 0 or dt.microsecond != 0:
        raise FeatureInputError(f"{name} must be on a whole minute")
    return dt


def _validate_bucket_alignment(bucket_ts: datetime, timeframe: str) -> None:
    minute, hour = bucket_ts.minute, bucket_ts.hour
    if timeframe == "1m":
        return
    if timeframe == "5m":
        aligned = minute % 5 == 0
    elif timeframe == "15m":
        aligned = minute % 15 == 0
    elif timeframe == "1h":
        aligned = minute == 0
    elif timeframe == "4h":
        aligned = minute == 0 and hour % 4 == 0
    else:  # pragma: no cover - guarded upstream
        raise FeatureInputError(f"unsupported timeframe {timeframe!r}")
    if not aligned:
        raise FeatureInputError(
            f"bucket_ts {bucket_ts.isoformat()} not aligned to the {timeframe} grid")


def _allowed_missing_bars(timeframe: str, minimum_metric_coverage) -> int:
    """ceil(expected * coverage) present required; allowed_missing = expected -
    that, computed with exact Decimal arithmetic (no float rounding surprises)."""
    # Overflow-safe finite validation (bool/non-number/NaN/±Inf/huge-int rejected)
    # before the range check, so 10**400 can never leak a raw OverflowError.
    cov_f = _number(minimum_metric_coverage, "minimum_metric_coverage")
    if not (0 < cov_f <= 1):
        raise FeatureInputError(
            f"minimum_metric_coverage must be in (0, 1], got {minimum_metric_coverage!r}")
    expected = TIMEFRAME_MINUTES[timeframe]
    cov = Decimal(str(minimum_metric_coverage))
    required_present = int((Decimal(expected) * cov).to_integral_value(rounding=ROUND_CEILING))
    allowed = expected - required_present
    if not (0 <= allowed <= expected):
        raise FeatureInputError(
            f"allowed_missing_bars {allowed} out of range for {timeframe}")
    return allowed


# ---- context build (pure; validates BEFORE any reader call) -----------------
def build_assembly_context(
    stage2_config: Stage2Config, *, exchange: str, symbol: str, market_type: str,
    timeframe: str, bucket_ts: datetime, code_version: str,
    liquidation_feed_available: bool,
) -> AssemblyContext:
    if not isinstance(stage2_config, Stage2Config):
        raise FeatureInputError("stage2_config must be a Stage2Config")
    if not isinstance(exchange, str) or exchange not in ACTIVE_EXCHANGES:
        raise FeatureInputError(
            f"unknown/inactive exchange {exchange!r} (active: {list(ACTIVE_EXCHANGES)})")
    active = {s.symbol: s for s in active_symbols()}
    sym_def = active.get(symbol) if isinstance(symbol, str) else None
    if sym_def is None:
        raise FeatureInputError(f"unknown/inactive symbol {symbol!r} (active: {sorted(active)})")
    if market_type not in sym_def.market_types or market_type not in SUPPORTED_MARKET_TYPES:
        raise FeatureInputError(
            f"unsupported market_type {market_type!r} for {symbol}")
    if timeframe not in TIMEFRAME_MINUTES:
        raise FeatureInputError(f"unsupported timeframe {timeframe!r}")
    if not isinstance(code_version, str) or not code_version.strip():
        raise FeatureInputError("code_version must be a non-empty string")
    if not isinstance(liquidation_feed_available, bool):
        raise FeatureInputError("liquidation_feed_available must be a bool")

    resolved = stage2_config.resolve(symbol)
    # Honour resolved per-symbol enablement (distinct from the registry check
    # above and from the global stage2.enabled master switch, which stays NOT
    # required). Registry/config drift must fail loudly here — before any reader.
    if resolved.enabled is not True:
        raise FeatureInputError(f"symbol {symbol!r} is disabled in the resolved config")
    if market_type not in resolved.market_types:
        raise FeatureInputError(
            f"market_type {market_type!r} not in resolved market_types "
            f"{list(resolved.market_types)} for {symbol}")
    enabled_timeframes = resolved["timeframes"]
    if timeframe not in enabled_timeframes:
        raise FeatureInputError(
            f"timeframe {timeframe!r} is not enabled for {symbol} "
            f"(enabled: {list(enabled_timeframes)})")

    _utc_whole_minute(bucket_ts, "bucket_ts")
    _validate_bucket_alignment(bucket_ts, timeframe)

    config_hash = resolved.config_hash()
    config_version = stage2_config.config_version
    feature_schema_version = stage2_config.feature_schema_version
    calculation_version = compute_calculation_version(
        feature_schema_version, config_hash, code_version)
    allowed_missing_bars = _allowed_missing_bars(
        timeframe, resolved["data_confidence"]["minimum_metric_coverage"])
    bucket_end = bucket_ts + timedelta(minutes=TIMEFRAME_MINUTES[timeframe])

    return AssemblyContext(
        exchange=exchange, symbol=symbol, market_type=market_type, timeframe=timeframe,
        bucket_ts=bucket_ts, bucket_end=bucket_end,
        feature_schema_version=feature_schema_version,
        calculation_version=calculation_version, config_hash=config_hash,
        config_version=config_version, code_version=code_version,
        allowed_missing_bars=allowed_missing_bars,
        liquidation_feed_available=liquidation_feed_available)


# ---- row field helpers ------------------------------------------------------
def _require_mapping(row, name: str) -> Mapping:
    if not isinstance(row, Mapping):
        raise FeatureInputError(f"{name} row must be a mapping, got {type(row).__name__}")
    return row


def _required(row: Mapping, key: str, name: str):
    v = row.get(key, _MISSING)
    if v is _MISSING or v is None:
        raise FeatureInputError(f"{name}: required field {key!r} is missing/NULL")
    return v


def _number(value, name: str) -> float:
    """A finite real number as float. bool rejected; NaN/±Inf rejected; a huge
    int that cannot be represented as a float raises FeatureInputError (never a
    raw OverflowError). The adapter must never build a request holding a
    non-finite number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FeatureInputError(f"{name} must be a number, got {type(value).__name__}")
    try:
        f = float(value)
    except OverflowError:
        raise FeatureInputError(
            f"{name} is too large to represent as a float: {value!r}") from None
    if not math.isfinite(f):
        raise FeatureInputError(f"{name} must be finite, got {value!r}")
    return f


def _number_or_none(value, name: str) -> Optional[float]:
    return None if value is None else _number(value, name)


def _positive_number_or_none(value, name: str) -> Optional[float]:
    """A finite number strictly > 0, or None. Used for instrument
    contract_multiplier / tick_size: a present value must be positive, but
    absence stays allowed so notional degrades fail-closed in the core — never a
    default here."""
    if value is None:
        return None
    f = _number(value, name)
    if not (f > 0):
        raise FeatureInputError(f"{name} must be > 0 when present, got {value!r}")
    return f


def _int_or_none(value, name: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise FeatureInputError(f"{name} must be an int, got {type(value).__name__}")
    return value


def _req_datetime(row: Mapping, key: str, name: str) -> datetime:
    v = _required(row, key, name)
    if not isinstance(v, datetime):
        raise FeatureInputError(f"{name}: {key} must be a datetime")
    return v


def _match_identity(row: Mapping, ctx: AssemblyContext, name: str, *, market: bool = False) -> None:
    if row.get("exchange") != ctx.exchange:
        raise FeatureInputError(
            f"{name} exchange {row.get('exchange')!r} != request {ctx.exchange!r}")
    if row.get("symbol") != ctx.symbol:
        raise FeatureInputError(
            f"{name} symbol {row.get('symbol')!r} != request {ctx.symbol!r}")
    if market and row.get("market_type") != ctx.market_type:
        raise FeatureInputError(
            f"{name} market_type {row.get('market_type')!r} != request {ctx.market_type!r}")


# ---- per-source conversions -------------------------------------------------
def _bars(ctx: AssemblyContext, rows) -> list[KlineBar]:
    bars = []
    for row in rows:
        _require_mapping(row, "kline")
        _match_identity(row, ctx, "kline")
        bar = KlineBar(
            ts=_req_datetime(row, "ts", "kline"),
            open=_number(_required(row, "open", "kline"), "kline.open"),
            high=_number(_required(row, "high", "kline"), "kline.high"),
            low=_number(_required(row, "low", "kline"), "kline.low"),
            close=_number(_required(row, "close", "kline"), "kline.close"),
            volume=_number(_required(row, "volume", "kline"), "kline.volume"),
            # Nullable split — passed through unchanged; never synthesized.
            taker_buy_volume=_number_or_none(row.get("taker_buy_volume"), "kline.taker_buy_volume"),
            taker_sell_volume=_number_or_none(row.get("taker_sell_volume"), "kline.taker_sell_volume"),
        )
        bars.append(bar)
    bars.sort(key=lambda b: b.ts)
    return bars


def _open_interest(ctx: AssemblyContext, rows) -> list[OpenInterestObservation]:
    obs = []
    for row in rows:
        _require_mapping(row, "open_interest")
        _match_identity(row, ctx, "open_interest")
        ts = _req_datetime(row, "ts", "open_interest")
        oi_raw = _number(_required(row, "oi_raw", "open_interest"), "oi_raw")
        oi_unit = _required(row, "oi_unit", "open_interest")
        if not isinstance(oi_unit, str) or not oi_unit.strip():
            raise FeatureInputError("open_interest.oi_unit must be a non-empty string")
        obs.append(OpenInterestObservation(ts=ts, oi_raw=oi_raw, oi_unit=oi_unit))
    obs.sort(key=lambda o: o.ts)
    return obs


def _funding(ctx: AssemblyContext, row: Optional[Mapping]) -> list[FundingObservation]:
    if row is None:
        return []
    _require_mapping(row, "funding")
    _match_identity(row, ctx, "funding")
    ts = _req_datetime(row, "ts", "funding")
    if not (ts < ctx.bucket_end):
        raise FeatureInputError(
            f"funding ts {ts.isoformat()} must be strictly before bucket_end "
            f"{ctx.bucket_end.isoformat()}")
    rate = _number(_required(row, "funding_rate", "funding"), "funding_rate")
    return [FundingObservation(ts=ts, funding_rate=rate)]


def _liquidation_events(ctx: AssemblyContext, rows) -> list[tuple]:
    """Return sorted (ts, id, LiquidationEvent, is_snapshot_feed) tuples."""
    out = []
    for row in rows:
        _require_mapping(row, "liquidation")
        _match_identity(row, ctx, "liquidation")
        # BIGSERIAL id drives deterministic same-ts ordering — validate BEFORE
        # sorting so a malformed id fails loudly instead of leaking a sort
        # TypeError. type(id) is int excludes bool; must be strictly positive.
        event_id = _required(row, "id", "liquidation")
        if type(event_id) is not int or event_id <= 0:
            raise FeatureInputError(
                f"liquidation.id must be a positive int, got {event_id!r}")
        ts = _req_datetime(row, "ts", "liquidation")
        side = _required(row, "side", "liquidation")
        if side not in LIQUIDATION_SIDES:
            raise FeatureInputError(
                f"liquidation.side {side!r} must be one of {list(LIQUIDATION_SIDES)}")
        notional = row.get("notional")
        if notional is None:
            raise FeatureInputError(
                "liquidation.notional is NULL — refusing to derive it from price*qty "
                "(unsafe for contract-denominated venues)")
        notional = _number(notional, "liquidation.notional")   # finite, measured zero preserved
        if notional < 0:
            raise FeatureInputError(
                f"liquidation.notional must be >= 0, got {notional!r}")
        is_snapshot = row.get("is_snapshot_feed")
        if not isinstance(is_snapshot, bool):
            raise FeatureInputError("liquidation.is_snapshot_feed must be a bool")
        if not (ctx.bucket_ts <= ts < ctx.bucket_end):
            raise FeatureInputError(
                f"liquidation ts {ts.isoformat()} outside bucket "
                f"[{ctx.bucket_ts.isoformat()}, {ctx.bucket_end.isoformat()})")
        out.append((ts, event_id, LiquidationEvent(ts=ts, side=side, notional=notional),
                    is_snapshot))
    out.sort(key=lambda e: (e[0], e[1]))
    return out


def _liquidation_capability(ctx: AssemblyContext, cap: Optional[Mapping]) -> str:
    """Validate the capability row and return its coverage_type."""
    if cap is None:
        raise FeatureInputError("missing liquidations capability row")
    _require_mapping(cap, "capability")
    _match_identity(cap, ctx, "capability", market=True)
    if cap.get("metric") != "liquidations":
        raise FeatureInputError(f"capability metric {cap.get('metric')!r} != 'liquidations'")
    live = cap.get("live_supported")
    hist = cap.get("historical_supported")
    enabled = cap.get("enabled")
    for flag, fname in ((live, "live_supported"), (hist, "historical_supported"),
                        (enabled, "enabled")):
        if not isinstance(flag, bool):
            raise FeatureInputError(f"capability.{fname} must be a bool")
    # A runtime feed cannot claim availability with no structural live support.
    if ctx.liquidation_feed_available and not live:
        raise FeatureInputError(
            "liquidation_feed_available=True but structural live support is unavailable")
    # Drift detection against the authoritative capability table: for the active
    # Stage 2 venues liquidations are exactly enabled + live + never-backfilled +
    # event-driven (no freshness budget), with a live coverage_type.
    if enabled is not True:
        raise FeatureInputError("liquidations capability must be enabled=True")
    if live is not True:
        raise FeatureInputError("liquidations capability must have live_supported=True")
    if hist is not False:
        raise FeatureInputError(
            "liquidations capability must have historical_supported=False (never backfilled)")
    freshness = cap.get("expected_freshness_s")
    if freshness is not None:
        raise FeatureInputError(
            "liquidations capability expected_freshness_s must be None (event-driven)")
    coverage_type = cap.get("coverage_type")
    if coverage_type not in _LIQ_LIVE_COVERAGE_TYPES:
        raise FeatureInputError(
            f"liquidations coverage_type {coverage_type!r} must be one of "
            f"{list(_LIQ_LIVE_COVERAGE_TYPES)} (got drift/'unavailable'?)")
    return coverage_type


def _instrument_metadata(ctx: AssemblyContext, inst: Optional[Mapping]) -> Optional[InstrumentMetadata]:
    if inst is None:
        return None
    _require_mapping(inst, "instrument")
    _match_identity(inst, ctx, "instrument", market=True)
    quantity_unit = inst.get("quantity_unit")
    if quantity_unit is not None and quantity_unit not in _QUANTITY_UNITS:
        raise FeatureInputError(f"instrument.quantity_unit {quantity_unit!r} invalid")
    metadata_source = inst.get("metadata_source")
    if metadata_source not in _INSTRUMENT_SOURCES:
        raise FeatureInputError(f"instrument.metadata_source {metadata_source!r} invalid")
    is_stale = inst.get("is_stale")
    if not isinstance(is_stale, bool):
        raise FeatureInputError("instrument.is_stale must be a bool")
    fetched_at = inst.get("fetched_at")
    if fetched_at is not None and not isinstance(fetched_at, datetime):
        raise FeatureInputError("instrument.fetched_at must be a datetime or NULL")
    note = inst.get("note")
    if note is None:
        note = ""                                  # DB NULL -> model empty-string default
    elif not isinstance(note, str):
        raise FeatureInputError("instrument.note must be a string or NULL")
    exchange_instrument_id = _required(inst, "exchange_instrument_id", "instrument")
    if not isinstance(exchange_instrument_id, str) or not exchange_instrument_id.strip():
        raise FeatureInputError("instrument.exchange_instrument_id must be a non-empty string")
    return InstrumentMetadata(
        exchange=ctx.exchange, symbol=ctx.symbol, market_type=ctx.market_type,
        exchange_instrument_id=exchange_instrument_id,
        quantity_unit=quantity_unit,
        contract_multiplier=_positive_number_or_none(
            inst.get("contract_multiplier"), "instrument.contract_multiplier"),
        tick_size=_positive_number_or_none(inst.get("tick_size"), "instrument.tick_size"),
        price_precision=_int_or_none(inst.get("price_precision"), "instrument.price_precision"),
        quantity_precision=_int_or_none(inst.get("quantity_precision"), "instrument.quantity_precision"),
        metadata_source=metadata_source, fetched_at=fetched_at, is_stale=is_stale, note=note)


# ---- pure assembly ----------------------------------------------------------
def assemble_exchange_feature_request(
    context: AssemblyContext, raw_bundle,
) -> ExchangeFeatureRequest:
    """PURE: convert the raw bundle into one ExchangeFeatureRequest. No I/O."""
    bars = _bars(context, raw_bundle.klines)
    open_interest = _open_interest(context, raw_bundle.open_interest)
    funding = _funding(context, raw_bundle.latest_funding)
    events = _liquidation_events(context, raw_bundle.liquidations)
    coverage_type = _liquidation_capability(context, raw_bundle.liquidation_capability)
    is_snapshot_feed = coverage_type == "snapshot"

    # Every raw event's snapshot flag must agree with the structural coverage type.
    for _ts, _id, _event, event_is_snapshot in events:
        if is_snapshot_feed and not event_is_snapshot:
            raise FeatureInputError(
                "snapshot capability but a liquidation row has is_snapshot_feed=False")
        if (not is_snapshot_feed) and event_is_snapshot:
            raise FeatureInputError(
                f"{coverage_type} capability but a liquidation row has is_snapshot_feed=True")

    # Availability is a supplied runtime fact; presence of rows never flips it.
    if not context.liquidation_feed_available and events:
        raise FeatureInputError(
            "liquidation_feed_available=False but liquidation events were supplied")

    feed_state = LiquidationFeedState(
        is_available=context.liquidation_feed_available,
        coverage_type=coverage_type, is_snapshot_feed=is_snapshot_feed)
    instrument_metadata = _instrument_metadata(context, raw_bundle.instrument)

    return ExchangeFeatureRequest(
        exchange=context.exchange, symbol=context.symbol, market_type=context.market_type,
        timeframe=context.timeframe, bucket_ts=context.bucket_ts,
        feature_schema_version=context.feature_schema_version,
        calculation_version=context.calculation_version,
        config_hash=context.config_hash, config_version=context.config_version,
        code_version=context.code_version,
        bars=bars, open_interest=open_interest, funding=funding,
        liquidations=[e[2] for e in events],
        liquidation_feed_state=feed_state, instrument_metadata=instrument_metadata,
        allowed_missing_bars=context.allowed_missing_bars)


# ---- async orchestration entry point ---------------------------------------
async def load_exchange_feature_request(
    reader: RawBundleReader, stage2_config: Stage2Config, *,
    exchange: str, symbol: str, market_type: str, timeframe: str,
    bucket_ts: datetime, code_version: str, liquidation_feed_available: bool,
) -> ExchangeFeatureRequest:
    """Validate + resolve a deterministic context, call the reader exactly once,
    and assemble the request. No writes, no schema init, no loop, no clock."""
    context = build_assembly_context(
        stage2_config, exchange=exchange, symbol=symbol, market_type=market_type,
        timeframe=timeframe, bucket_ts=bucket_ts, code_version=code_version,
        liquidation_feed_available=liquidation_feed_available)
    raw_bundle = await reader.fetch_exchange_feature_raw_bundle(
        exchange=context.exchange, symbol=context.symbol,
        market_type=context.market_type, bucket_start=context.bucket_ts,
        bucket_end=context.bucket_end)
    return assemble_exchange_feature_request(context, raw_bundle)
