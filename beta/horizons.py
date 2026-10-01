"""Presentation-only 1h time-of-day baseline.

This is not detection. It does not enter the rules digest, the state-tape schema,
or BETA_CONTEXT_1H_V0. The result is stored on the /btc view payload under
`horizons`, with its own version label and digest.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional, Sequence

from common.versioning import canonical_json

from .state_tape import BUCKET, iso, metric_key

HORIZON_VERSION = "BETA_HORIZON_1H_TOD_V0"
# Pinned to the canonical definition below. A change of parameters needs a new label.
HORIZON_DIGEST = "e0d73c6969eade562fdfe7896bae27747ec923a12ce1c4091173973f4b33c3de"

_METRICS = ("range_width_pct_median", "price_move_pct_median", "volume_notional_usd_sum")
_PRIOR_DAYS = 30
_TOLERANCE_MIN = 30
_MATURE_DAYS = 20


def horizon_definition() -> dict:
    return {
        "version": HORIZON_VERSION,
        "presentation_only": True,
        "window_buckets": 12,
        "baseline_prior_utc_days": _PRIOR_DAYS,
        "baseline_tolerance_min": _TOLERANCE_MIN,
        "baseline_mature_days": _MATURE_DAYS,
        "daily_value": "median of rolling-1h samples whose window end is within "
                       "±tolerance of the same UTC time of day",
        "baseline": "median of those daily values",
        "price": "median over venues of (last close - first open) / first open",
        "range": "median over venues of (max high - min low) / first open",
        "volume": "sum of the 5m cross-venue volume sums",
        "taker": "sum of 5m taker_delta_notional_usd_sum",
        "funding": "funding_rate_median at the view bucket",
        "liquidations": "per venue, never summed across venues; a missing per-venue "
                        "value is not zero; missing buckets mark every venue as a lower "
                        "bound; Binance is always a lower bound",
    }


def horizon_digest() -> str:
    return hashlib.sha256(canonical_json(horizon_definition()).encode("utf-8")).hexdigest()


def verify_horizon_digest() -> str:
    digest = horizon_digest()
    if digest != HORIZON_DIGEST:
        raise ValueError(
            f"horizon {HORIZON_VERSION!r} is not pinned to digest {digest}")
    return digest


def _median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2.0


def _window_buckets(end_bucket: datetime, n: int) -> list:
    return [end_bucket - i * BUCKET for i in range(n - 1, -1, -1)]


def _liq_side(cfg, buckets: Sequence[datetime], metrics_by_bucket: Mapping[datetime, Mapping],
              *, buckets_missing: bool) -> dict:
    """Per venue. A None inside a present bucket is missing (never $0). Absent buckets
    do not invent a zero; they mark a numeric sum as a lower bound."""
    out = {}
    for ex in cfg.exchanges:
        out[ex] = {}
        for side, field in (("long", "long_liquidation_notional"), ("short", "short_liquidation_notional")):
            key = metric_key(ex, field)
            vals: list[float] = []
            missing_value = False
            for b in buckets:
                row = metrics_by_bucket.get(b)
                if row is None:
                    continue
                v = row.get(key)
                if v is None:
                    missing_value = True
                else:
                    vals.append(float(v))
            if missing_value or not vals:
                out[ex][side] = {"amount": None, "missing": True, "lower_bound": False}
                continue
            out[ex][side] = {
                "amount": float(sum(vals)),
                "missing": False,
                "lower_bound": bool(buckets_missing or ex == "binance"),
            }
    return out


def _baseline(cfg, metrics_by_bucket: Mapping[datetime, Mapping], end_bucket: datetime) -> dict:
    from .context import rolling_1h_values
    window_end = end_bucket + BUCKET
    if window_end.tzinfo is None or window_end.utcoffset() != timedelta(0):
        window_end = window_end.astimezone(timezone.utc)
    target = window_end.hour * 60 + window_end.minute
    daily = {m: [] for m in _METRICS}
    for d in range(1, _PRIOR_DAYS + 1):
        day = (window_end - timedelta(days=d)).date()
        midnight = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        samples = {m: [] for m in _METRICS}
        for delta in range(-_TOLERANCE_MIN, _TOLERANCE_MIN + 1, 5):
            wend = midnight + timedelta(minutes=target + delta)
            sample = rolling_1h_values(cfg, metrics_by_bucket, wend - BUCKET)
            if sample is None:
                continue
            for m in _METRICS:
                if sample.get(m) is not None:
                    samples[m].append(float(sample[m]))
        for m in _METRICS:
            if samples[m]:
                daily[m].append(_median(samples[m]))
    medians = {}
    days = {}
    for m in _METRICS:
        days[m] = len(daily[m])
        medians[m] = _median(daily[m]) if days[m] >= _MATURE_DAYS else None
    return {"days": days, "median": medians}


def _ratio(current: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if current is None or baseline is None or baseline == 0:
        return None
    return float(current) / float(baseline)


def build_horizons(cfg, *, as_of_bucket: datetime, metrics_by_bucket: Mapping[datetime, Mapping]) -> dict:
    """Language-neutral 1h block for the view payload. `as_of_bucket` is the last closed 5m open time."""
    from .context import rolling_1h_values
    n = int(cfg.section("context")["rolling_buckets"])
    buckets = _window_buckets(as_of_bucket, n)
    buckets_missing = any(metrics_by_bucket.get(b) is None for b in buckets)
    cur = None if buckets_missing else rolling_1h_values(cfg, metrics_by_bucket, as_of_bucket)
    complete = cur is not None
    base = _baseline(cfg, metrics_by_bucket, as_of_bucket) if complete else {
        "days": {m: 0 for m in _METRICS}, "median": {m: None for m in _METRICS}}
    price = None if not complete else cur.get("price_move_pct_median")
    rng = None if not complete else cur.get("range_width_pct_median")
    vol = None if not complete else cur.get("volume_notional_usd_sum")
    taker = _sum_metric(buckets, metrics_by_bucket, "c:taker_delta_notional_usd_sum")
    end_row = metrics_by_bucket.get(as_of_bucket) or {}
    funding = end_row.get("c:funding_rate_median")
    return {
        "version": HORIZON_VERSION,
        "digest": verify_horizon_digest(),
        "1h": {
            "complete": complete,
            "window_start": None if not buckets else iso(buckets[0]),
            "window_end": iso(as_of_bucket + BUCKET),
            "price_move_pct": price,
            "range_width_pct": rng,
            "volume_notional_usd": vol,
            "baseline_days": base["days"],
            "baseline_median": base["median"],
            "range_ratio": _ratio(rng, base["median"]["range_width_pct_median"]),
            "volume_ratio": _ratio(vol, base["median"]["volume_notional_usd_sum"]),
            "taker_delta_notional_usd_sum": taker,
            "funding_rate": None if funding is None else float(funding),
            "liquidations": {
                "buckets_missing": buckets_missing,
                "venues": _liq_side(cfg, buckets, metrics_by_bucket, buckets_missing=buckets_missing),
            },
        },
    }


def empty_horizons() -> dict:
    return {"version": HORIZON_VERSION, "digest": verify_horizon_digest(), "1h": None}


def _sum_metric(buckets, metrics_by_bucket, key: str) -> Optional[float]:
    total = 0.0
    for b in buckets:
        row = metrics_by_bucket.get(b)
        if row is None or row.get(key) is None:
            return None
        total += float(row[key])
    return total
