"""
Stage 2.1 per-exchange feature computation — a pure, deterministic core.

`compute_exchange_features(request) -> ExchangeFeatureVector` computes ONE
exchange_feature_vector for one (exchange, bucket). No DB, no network, no
asyncio, no clock/env/subprocess, no global mutable state. Same input → same
output; input order does not matter (everything is deterministically sorted).

NO cross-exchange logic (consensus / percentiles / data-confidence / medians /
direction agreement) — that is a separate later PR.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from typing import Optional, Sequence

from .models import (
    ExchangeFeatureRequest, ExchangeFeatureVector, KlineBar,
    LIQUIDATION_COVERAGE_TYPES, LIQUIDATION_SIDES, TIMEFRAME_MINUTES,
)
from .units import (
    bar_notional_from_metadata, metadata_notional_eligible,
)
from symbols.registry import ACTIVE_EXCHANGES, active_symbols

# Identity fields cross-checked against instrument_metadata before any notional
# is derived (mismatched metadata must never feed a USD conversion).
_METADATA_IDENTITY_FIELDS = ("exchange", "symbol", "market_type")

_HEX16 = re.compile(r"^[0-9a-f]{16}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class FeatureError(ValueError):
    """Invalid feature request / input that must fail loudly (never silently
    coerced, dropped, or defaulted)."""


# ---- small validators ------------------------------------------------------
def _tz_aware(dt, name: str) -> datetime:
    if not isinstance(dt, datetime):
        raise FeatureError(f"{name} must be a datetime, got {type(dt).__name__}")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise FeatureError(f"{name} must be timezone-aware")
    return dt


def _utc_minute(dt, name: str) -> datetime:
    """A timezone-aware UTC timestamp pinned to a whole minute: offset 0,
    second 0, microsecond 0. No silent rounding — anything else fails loudly."""
    _tz_aware(dt, name)
    if dt.utcoffset() != timedelta(0):
        raise FeatureError(f"{name} must be UTC (offset 0), got offset {dt.utcoffset()}")
    if dt.second != 0 or dt.microsecond != 0:
        raise FeatureError(
            f"{name} must be on a whole minute (second=0, microsecond=0), "
            f"got second={dt.second} microsecond={dt.microsecond}")
    return dt


def _validate_bucket_alignment(bucket_ts: datetime, timeframe: str) -> None:
    """The bucket start must fall on the timeframe grid (all UTC)."""
    minute, hour = bucket_ts.minute, bucket_ts.hour
    if timeframe == "1m":
        return                                   # any whole UTC minute
    if timeframe == "5m":
        aligned = minute % 5 == 0
    elif timeframe == "15m":
        aligned = minute % 15 == 0
    elif timeframe == "1h":
        aligned = minute == 0
    elif timeframe == "4h":
        aligned = minute == 0 and hour % 4 == 0
    else:                                        # pragma: no cover - guarded upstream
        raise FeatureError(f"unsupported timeframe {timeframe!r}")
    if not aligned:
        raise FeatureError(
            f"bucket_ts {bucket_ts.isoformat()} is not aligned to the {timeframe} grid")


def _finite(value, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise FeatureError(f"{name} must be a number, got {type(value).__name__}")
    v = float(value)
    if not math.isfinite(v):
        raise FeatureError(f"{name} must be finite, got {value!r}")
    return v


def _positive(value, name: str) -> float:
    v = _finite(value, name)
    if v <= 0:
        raise FeatureError(f"{name} must be > 0, got {value!r}")
    return v


def _nonblank(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FeatureError(f"{name} must be a non-empty string")
    return value


# ---- identity / request validation -----------------------------------------
def _validate_identity(req: ExchangeFeatureRequest) -> None:
    # Canonical identity is authoritative from symbols/registry.py — NO arbitrary
    # non-blank strings, NO silent case normalization, NO fallback to BTCUSDT.
    if not isinstance(req.exchange, str) or req.exchange not in ACTIVE_EXCHANGES:
        raise FeatureError(f"unknown/inactive exchange {req.exchange!r} "
                           f"(active: {list(ACTIVE_EXCHANGES)})")
    active = {s.symbol: s for s in active_symbols()}
    sym_def = active.get(req.symbol) if isinstance(req.symbol, str) else None
    if sym_def is None:
        raise FeatureError(f"unknown/inactive symbol {req.symbol!r} "
                           f"(active: {sorted(active)})")
    if req.market_type not in sym_def.market_types:
        raise FeatureError(f"unsupported market_type {req.market_type!r} for "
                           f"{req.symbol} (supported: {list(sym_def.market_types)})")
    if req.timeframe not in TIMEFRAME_MINUTES:
        raise FeatureError(f"unsupported timeframe {req.timeframe!r} "
                           f"(supported: {sorted(TIMEFRAME_MINUTES)})")
    _utc_minute(req.bucket_ts, "bucket_ts")
    _validate_bucket_alignment(req.bucket_ts, req.timeframe)
    if not isinstance(req.feature_schema_version, int) or isinstance(req.feature_schema_version, bool) \
            or req.feature_schema_version <= 0:
        raise FeatureError("feature_schema_version must be an int > 0")
    if not isinstance(req.calculation_version, str) or not _HEX16.match(req.calculation_version):
        raise FeatureError("calculation_version must be 16 lowercase hex chars")
    if not isinstance(req.config_hash, str) or not _HEX64.match(req.config_hash):
        raise FeatureError("config_hash must be 64 lowercase hex chars")
    _nonblank(req.config_version, "config_version")
    _nonblank(req.code_version, "code_version")
    if not isinstance(req.allowed_missing_bars, int) or isinstance(req.allowed_missing_bars, bool) \
            or req.allowed_missing_bars < 0:
        raise FeatureError("allowed_missing_bars must be an int >= 0")
    _validate_metadata_identity(req)


def _validate_metadata_identity(req: ExchangeFeatureRequest) -> None:
    """When instrument_metadata is supplied it MUST describe the same instrument
    as the request. A mismatch fails BEFORE any notional is derived, so metadata
    for another exchange / symbol / market_type can never feed a USD conversion.
    (We only cross-check the identity; the shared common.symbol_mapper stays the
    single source of venue instrument ids — no second mapper here.)"""
    meta = req.instrument_metadata
    if meta is None:
        return
    mismatched = [f for f in _METADATA_IDENTITY_FIELDS
                  if getattr(meta, f) != getattr(req, f)]
    if mismatched:
        raise FeatureError(
            f"instrument_metadata identity mismatch on {mismatched}: request "
            f"{req.exchange}/{req.symbol}/{req.market_type} vs metadata "
            f"{meta.exchange}/{meta.symbol}/{meta.market_type}")


# ---- bars / completeness ----------------------------------------------------
def _validate_ohlc(bar: KlineBar) -> None:
    o = _positive(bar.open, "open")
    h = _positive(bar.high, "high")
    lo = _positive(bar.low, "low")
    c = _positive(bar.close, "close")
    _finite(bar.volume, "volume")
    if bar.volume < 0:
        raise FeatureError(f"negative volume not allowed: {bar.volume!r}")
    if h < max(o, c, lo):
        raise FeatureError(f"OHLC invariant violated: high {h} < max(open,close,low)")
    if lo > min(o, c, h):
        raise FeatureError(f"OHLC invariant violated: low {lo} > min(open,close,high)")


def _prepare_bars(req: ExchangeFeatureRequest, bucket_end: datetime):
    expected = TIMEFRAME_MINUTES[req.timeframe]
    if req.allowed_missing_bars > expected:
        raise FeatureError(
            f"allowed_missing_bars ({req.allowed_missing_bars}) exceeds "
            f"bars_expected ({expected})")
    # The exact set of legal 1m slots: bucket_ts + N minutes for N in [0, expected).
    expected_slots = {req.bucket_ts + timedelta(minutes=n) for n in range(expected)}
    seen_ts = set()
    for bar in req.bars:
        _utc_minute(bar.ts, "bar.ts")
        if not (req.bucket_ts <= bar.ts < bucket_end):
            raise FeatureError(
                f"bar ts {bar.ts.isoformat()} outside bucket "
                f"[{req.bucket_ts.isoformat()}, {bucket_end.isoformat()})")
        if bar.ts not in expected_slots:
            raise FeatureError(
                f"bar ts {bar.ts.isoformat()} is not an expected 1m slot of the "
                f"{req.timeframe} bucket at {req.bucket_ts.isoformat()}")
        if bar.ts in seen_ts:
            raise FeatureError(f"duplicate bar timestamp {bar.ts.isoformat()}")
        seen_ts.add(bar.ts)
        _validate_ohlc(bar)
    bars = sorted(req.bars, key=lambda b: b.ts)
    # bars_present counts distinct expected slots actually filled, never raw rows.
    present = len(seen_ts)
    if present > expected:                       # unreachable given slot membership
        raise FeatureError(f"bars_present ({present}) exceeds bars_expected ({expected})")
    missing = expected - present
    has_gap = present < expected
    is_usable = present > 0 and missing <= req.allowed_missing_bars
    return bars, expected, present, has_gap, is_usable


# ---- price ------------------------------------------------------------------
def _price_features(bars: Sequence[KlineBar]):
    if not bars:
        return None, None, None
    open_first = bars[0].open
    close_last = bars[-1].close
    high_max = max(b.high for b in bars)
    low_min = min(b.low for b in bars)
    close_price = close_last
    if open_first == 0:
        return None, None, close_price
    price_move_pct = (close_last - open_first) / open_first * 100.0
    range_width_pct = (high_max - low_min) / open_first * 100.0
    return price_move_pct, range_width_pct, close_price


# ---- volume / taker / cvd ---------------------------------------------------
def _volume_taker_features(bars, metadata, is_usable):
    unit = metadata.quantity_unit if metadata is not None else None
    if not bars:
        return {"volume_raw": None, "volume_raw_unit": unit,
                "volume_notional_usd": None, "taker_buy_notional_usd": None,
                "taker_sell_notional_usd": None, "taker_delta_notional_usd": None,
                "cvd_delta_notional_usd": None}

    volume_raw = sum(b.volume for b in bars)
    eligible = metadata_notional_eligible(metadata)
    volume_notional = (sum(bar_notional_from_metadata(b.volume, b.close, metadata) for b in bars)
                       if eligible else None)

    # A split exists only when BOTH taker columns are present on EVERY bar.
    split_available = all(b.taker_buy_volume is not None and b.taker_sell_volume is not None
                          for b in bars)
    if split_available and eligible:
        taker_buy = sum(bar_notional_from_metadata(b.taker_buy_volume, b.close, metadata) for b in bars)
        taker_sell = sum(bar_notional_from_metadata(b.taker_sell_volume, b.close, metadata) for b in bars)
        taker_delta = taker_buy - taker_sell
    else:
        taker_buy = taker_sell = taker_delta = None

    # CVD is the windowed sum of per-1m taker delta; only when the bucket is
    # usable (gaps within tolerance). No carry-forward, no stored state.
    cvd_delta = taker_delta if (taker_delta is not None and is_usable) else None

    return {"volume_raw": volume_raw, "volume_raw_unit": unit,
            "volume_notional_usd": volume_notional,
            "taker_buy_notional_usd": taker_buy,
            "taker_sell_notional_usd": taker_sell,
            "taker_delta_notional_usd": taker_delta,
            "cvd_delta_notional_usd": cvd_delta}


# ---- open interest ----------------------------------------------------------
def _oi_feature(req: ExchangeFeatureRequest, bucket_end: datetime):
    # One canonical observation per timestamp. Identical (oi_raw, oi_unit)
    # duplicates collapse deterministically; a conflicting value OR unit at the
    # same timestamp is a hard error. first/last are chosen by timestamp only, so
    # input order never affects the result. Raw OI is never summed.
    by_ts: dict[datetime, tuple[float, str]] = {}
    for o in req.open_interest:
        _tz_aware(o.ts, "open_interest.ts")
        if not (req.bucket_ts <= o.ts < bucket_end):
            continue
        raw = _finite(o.oi_raw, "oi_raw")
        unit = _nonblank(o.oi_unit, "oi_unit")
        if o.ts in by_ts:
            if by_ts[o.ts] != (raw, unit):
                prev = by_ts[o.ts]
                raise FeatureError(
                    f"conflicting open interest at {o.ts.isoformat()}: "
                    f"{prev} vs {(raw, unit)}")
            continue                       # identical duplicate -> deduplicated
        by_ts[o.ts] = (raw, unit)
    if len(by_ts) < 2:
        return None, None
    units = {u for _, u in by_ts.values()}
    if len(units) != 1:                    # unit change inside bucket
        return None, None
    unit = next(iter(units))
    ordered_ts = sorted(by_ts)
    oi_first = by_ts[ordered_ts[0]][0]
    oi_last = by_ts[ordered_ts[-1]][0]
    if oi_first == 0:
        return None, unit                  # consistent series, but no % base
    return (oi_last - oi_first) / oi_first * 100.0, unit


# ---- funding ----------------------------------------------------------------
def _funding_feature(req: ExchangeFeatureRequest, bucket_end: datetime):
    candidates = []
    for f in req.funding:
        _tz_aware(f.ts, "funding.ts")
        if f.ts < bucket_end:              # observations at/after bucket_end forbidden
            _finite(f.funding_rate, "funding_rate")
            candidates.append(f)
    if not candidates:
        return None
    by_ts: dict[datetime, float] = {}
    for f in candidates:
        if f.ts in by_ts and by_ts[f.ts] != f.funding_rate:
            raise FeatureError(
                f"conflicting funding values at {f.ts.isoformat()}: "
                f"{by_ts[f.ts]} vs {f.funding_rate}")
        by_ts[f.ts] = f.funding_rate
    latest_ts = max(by_ts)                 # deterministic: last observation before bucket_end
    return by_ts[latest_ts]


# ---- liquidations -----------------------------------------------------------
def _liquidation_features(req: ExchangeFeatureRequest, bucket_end: datetime):
    fs = req.liquidation_feed_state
    if fs.coverage_type not in LIQUIDATION_COVERAGE_TYPES:
        raise FeatureError(f"invalid liquidation coverage_type {fs.coverage_type!r}")
    if fs.coverage_type == "unavailable" and fs.is_available:
        raise FeatureError("liquidation feed 'unavailable' cannot be is_available=True")
    # is_snapshot_feed is true iff (and only iff) the coverage_type is 'snapshot'.
    if fs.is_snapshot_feed != (fs.coverage_type == "snapshot"):
        raise FeatureError(
            f"is_snapshot_feed={fs.is_snapshot_feed} inconsistent with "
            f"coverage_type={fs.coverage_type!r} (snapshot feed iff coverage 'snapshot')")
    # An unavailable feed for this bucket must not carry events; NULL != zero.
    if not fs.is_available and req.liquidations:
        raise FeatureError(
            "liquidation feed is_available=False but liquidation events were provided")

    long_sum = 0.0
    short_sum = 0.0
    count = 0
    for e in req.liquidations:
        _tz_aware(e.ts, "liquidation.ts")
        if not (req.bucket_ts <= e.ts < bucket_end):
            raise FeatureError(
                f"liquidation ts {e.ts.isoformat()} outside bucket")
        if e.side not in LIQUIDATION_SIDES:
            raise FeatureError(f"unknown liquidation side {e.side!r}")
        n = _finite(e.notional, "liquidation.notional")
        if n < 0:
            raise FeatureError(f"negative liquidation notional: {e.notional!r}")
        count += 1
        if e.side == "long":
            long_sum += n
        else:
            short_sum += n

    if not fs.is_available:
        # Absence of a live feed is NOT a measured zero.
        return None, None, None, fs.coverage_type, fs.is_snapshot_feed
    return long_sum, short_sum, count, fs.coverage_type, fs.is_snapshot_feed


# ---- entry point ------------------------------------------------------------
def compute_exchange_features(req: ExchangeFeatureRequest) -> ExchangeFeatureVector:
    _validate_identity(req)
    bucket_end = req.bucket_ts + timedelta(minutes=TIMEFRAME_MINUTES[req.timeframe])

    bars, bars_expected, bars_present, has_gap, is_usable = _prepare_bars(req, bucket_end)
    price_move_pct, range_width_pct, close_price = _price_features(bars)
    vt = _volume_taker_features(bars, req.instrument_metadata, is_usable)
    oi_change_pct, oi_unit = _oi_feature(req, bucket_end)
    funding_rate = _funding_feature(req, bucket_end)
    long_liq, short_liq, liq_count, liq_quality, is_snapshot = \
        _liquidation_features(req, bucket_end)

    return ExchangeFeatureVector(
        exchange=req.exchange, symbol=req.symbol, market_type=req.market_type,
        timeframe=req.timeframe, bucket_ts=req.bucket_ts,
        feature_schema_version=req.feature_schema_version,
        calculation_version=req.calculation_version,
        price_move_pct=price_move_pct, range_width_pct=range_width_pct,
        close_price=close_price,
        volume_raw=vt["volume_raw"], volume_raw_unit=vt["volume_raw_unit"],
        volume_notional_usd=vt["volume_notional_usd"],
        taker_buy_notional_usd=vt["taker_buy_notional_usd"],
        taker_sell_notional_usd=vt["taker_sell_notional_usd"],
        taker_delta_notional_usd=vt["taker_delta_notional_usd"],
        cvd_delta_notional_usd=vt["cvd_delta_notional_usd"],
        oi_change_pct=oi_change_pct, oi_unit=oi_unit, funding_rate=funding_rate,
        long_liquidation_notional=long_liq, short_liquidation_notional=short_liq,
        liquidation_event_count=liq_count, liquidation_feed_quality=liq_quality,
        is_snapshot_feed=is_snapshot,
        bars_expected=bars_expected, bars_present=bars_present,
        has_gap=has_gap, is_usable=is_usable,
        config_hash=req.config_hash, config_version=req.config_version,
        code_version=req.code_version,
    )
