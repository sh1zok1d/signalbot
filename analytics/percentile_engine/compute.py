"""
Stage 2.1 Percentile Engine core — a pure, deterministic computation.

`compute_percentile_snapshot(request) -> PercentileSnapshot` ranks one current
value against its strictly-earlier historical distribution, exactly per
Percentile Contract Revision 0.2.4 (docs/STAGE2_SPEC.md §12).

No DB, no network, no asyncio, no clock/env/subprocess, no global mutable state,
and NO internal rounding. Same logical input -> same output; sample input order
does not matter.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from typing import Optional

from symbols.registry import ACTIVE_EXCHANGES

from .models import (
    ConfidenceTierThresholds, METRICS_BY_SCOPE, PercentileError, PercentileRequest,
    PercentileSample, PercentileSnapshot, VALID_SCOPES, VALID_WINDOWS,
    WINDOW_TIMEDELTAS,
)

_HEX16 = re.compile(r"^[0-9a-f]{16}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ONE_DAY_SECONDS = 86400.0

# Identity fields every sample must match the request on (§12.3). `exchange` is
# checked separately (required to match in both scopes: real venue vs '').
_SAMPLE_IDENTITY_FIELDS = (
    "scope", "symbol", "market_type", "metric", "timeframe",
    "feature_schema_version", "calculation_version",
)


# ---- small validators ------------------------------------------------------
def _tz_utc(dt, name: str) -> datetime:
    if not isinstance(dt, datetime):
        raise PercentileError(f"{name} must be a datetime, got {type(dt).__name__}")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise PercentileError(f"{name} must be timezone-aware")
    if dt.utcoffset() != timedelta(0):
        raise PercentileError(f"{name} must be UTC (offset 0), got offset {dt.utcoffset()}")
    return dt


def _nonblank(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PercentileError(f"{name} must be a non-empty string")
    return value


def _finite_value(value, name: str) -> float:
    """A real, finite metric value: bool rejected, NaN/±Inf rejected. Callers
    handle None separately (None is valid absent data, never coerced)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise PercentileError(f"{name} must be a number, got {type(value).__name__}")
    v = float(value)
    if not math.isfinite(v):
        raise PercentileError(f"{name} must be finite, got {value!r}")
    return v


# ---- request identity (§12.1 / §12.3) --------------------------------------
def _validate_request(req: PercentileRequest) -> None:
    if req.scope not in VALID_SCOPES:
        raise PercentileError(f"invalid scope {req.scope!r} (expected {list(VALID_SCOPES)})")
    if req.scope == "exchange":
        if not isinstance(req.exchange, str) or req.exchange not in ACTIVE_EXCHANGES:
            raise PercentileError(
                f"exchange scope requires a real active venue, got {req.exchange!r} "
                f"(active: {list(ACTIVE_EXCHANGES)})")
    else:  # consensus
        if req.exchange != "":
            raise PercentileError("consensus scope requires exchange == '' (empty string)")
    if req.metric not in METRICS_BY_SCOPE[req.scope]:
        raise PercentileError(
            f"metric {req.metric!r} is not in the {req.scope} scope allow-list")
    if req.percentile_window not in VALID_WINDOWS:
        raise PercentileError(
            f"invalid percentile_window {req.percentile_window!r} (expected {list(VALID_WINDOWS)})")
    _nonblank(req.symbol, "symbol")
    _nonblank(req.market_type, "market_type")
    _nonblank(req.timeframe, "timeframe")
    if not isinstance(req.feature_schema_version, int) or isinstance(req.feature_schema_version, bool) \
            or req.feature_schema_version <= 0:
        raise PercentileError("feature_schema_version must be an int > 0")
    if not isinstance(req.calculation_version, str) or not _HEX16.match(req.calculation_version):
        raise PercentileError("calculation_version must be 16 lowercase hex chars")
    if not isinstance(req.config_hash, str) or not _HEX64.match(req.config_hash):
        raise PercentileError("config_hash must be 64 lowercase hex chars")
    _nonblank(req.config_version, "config_version")
    _nonblank(req.code_version, "code_version")
    if not isinstance(req.confidence_tier_thresholds, ConfidenceTierThresholds):
        raise PercentileError("confidence_tier_thresholds must be a ConfidenceTierThresholds")
    _tz_utc(req.bucket_ts, "bucket_ts")
    if req.value is not None:
        _finite_value(req.value, "value")


# ---- sample identity / window / numeric / dedup (§12.2 / §12.3 / §12.5) -----
def _collect_samples(req: PercentileRequest) -> dict[datetime, Optional[float]]:
    """Validate every sample against the request identity, window, and numeric
    rules, then deterministically dedup by timestamp. Returns {bucket_ts: value},
    value possibly None. Order-independent."""
    bucket = req.bucket_ts
    window = WINDOW_TIMEDELTAS[req.percentile_window]
    lower = bucket - window
    by_ts: dict[datetime, Optional[float]] = {}
    for s in req.samples:
        if not isinstance(s, PercentileSample):
            raise PercentileError(f"samples must be PercentileSample, got {type(s).__name__}")
        # identity isolation — never silently filter a mismatched row
        for f in _SAMPLE_IDENTITY_FIELDS:
            if getattr(s, f) != getattr(req, f):
                raise PercentileError(
                    f"sample {f} mismatch: {getattr(s, f)!r} != request {getattr(req, f)!r}")
        if s.exchange != req.exchange:
            raise PercentileError(
                f"sample exchange mismatch: {s.exchange!r} != request {req.exchange!r}")
        _tz_utc(s.bucket_ts, "sample.bucket_ts")
        # window membership: [B - W, B)
        if not (lower <= s.bucket_ts < bucket):
            raise PercentileError(
                f"sample bucket_ts {s.bucket_ts.isoformat()} outside window "
                f"[{lower.isoformat()}, {bucket.isoformat()})")
        value = None if s.value is None else _finite_value(s.value, "sample.value")
        if s.bucket_ts in by_ts:
            prev = by_ts[s.bucket_ts]
            # identical (incl. None==None) collapses; anything else conflicts
            if prev is None or value is None:
                if not (prev is None and value is None):
                    raise PercentileError(
                        f"conflicting duplicate at {s.bucket_ts.isoformat()}: "
                        f"{prev!r} vs {value!r}")
            elif prev != value:
                raise PercentileError(
                    f"conflicting duplicate at {s.bucket_ts.isoformat()}: {prev!r} vs {value!r}")
            # else identical numeric -> collapse (keep existing)
        else:
            by_ts[s.bucket_ts] = value
    return by_ts


# ---- entry point -----------------------------------------------------------
def compute_percentile_snapshot(req: PercentileRequest) -> PercentileSnapshot:
    _validate_request(req)
    by_ts = _collect_samples(req)

    # Distribution: drop absent (None) observations; NULL is never a zero.
    non_null_ts = sorted(ts for ts, v in by_ts.items() if v is not None)
    values = [by_ts[ts] for ts in non_null_ts]
    sample_size = len(values)
    sample_window_start = non_null_ts[0] if sample_size else None
    sample_window_end = non_null_ts[-1] if sample_size else None

    # Percentile rank (mid-rank empirical, §12.1). Current value is NOT a sample.
    if req.value is None or sample_size == 0:
        percentile_rank: Optional[float] = None
    else:
        cur = float(req.value)
        less = sum(1 for v in values if v < cur)
        equal = sum(1 for v in values if v == cur)
        percentile_rank = (less + 0.5 * equal) / sample_size

    # Confidence tier (span measured against bucket_ts, §12.6).
    if sample_size < 2:
        span_days = 0.0
    else:
        span_days = (req.bucket_ts - sample_window_start).total_seconds() / _ONE_DAY_SECONDS
    thr = req.confidence_tier_thresholds
    if span_days < thr.none_below_days:
        confidence_tier = "none"
    elif span_days < thr.low_below_days:
        confidence_tier = "low"
    elif span_days < thr.building_below_days:
        confidence_tier = "building"
    else:
        confidence_tier = "mature"

    return PercentileSnapshot(
        scope=req.scope, exchange=req.exchange, symbol=req.symbol,
        market_type=req.market_type, metric=req.metric, timeframe=req.timeframe,
        percentile_window=req.percentile_window, bucket_ts=req.bucket_ts,
        value=req.value, percentile_rank=percentile_rank, sample_size=sample_size,
        sample_window_start=sample_window_start, sample_window_end=sample_window_end,
        confidence_tier=confidence_tier,
        config_hash=req.config_hash, config_version=req.config_version,
        code_version=req.code_version,
        feature_schema_version=req.feature_schema_version,
        calculation_version=req.calculation_version,
    )
