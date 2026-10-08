"""Presentation-only 1h, 4h and 24h horizons.

This is not detection. It does not enter the rules digest, the state-tape schema,
or BETA_CONTEXT_1H_V0. The result is stored on the /btc view payload under
`horizons`, with its own version label and digest.
"""
from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional, Sequence

from common.versioning import canonical_json

from .oi_asof import venue_oi_change_pct
from .state_tape import BUCKET, iso, metric_key

HORIZON_VERSION = "BETA_HORIZON_TOD_V6"
# Pinned to the canonical definition below. A change of parameters needs a new label.
# V1 (4b84b794…) had no 4h block; V2 (f64700b7…) adds it with the same time-of-day baseline rule;
# V3 (C1, docs/BETA_C1_DAY_TYPE_BASELINE_V1.md) uses same-UTC-day-type days for the 1h range and
# volume baselines only. V4 (D3, docs/BETA_DATA_RELIABILITY_FIX_PLAN_V1.md R4): the OI change of every
# horizon needs at least `min_venues` venues, as the 1h context does. V5 (D3 R6, R7): the 24h volume is
# complete only when every bucket has every venue's kline; the change lines record which checks ran. V6 (D3 R3):
# «Funding сейчас» from each venue's newest live row no older than FUNDING_MAX_AGE, median of >= min_venues;
# the 24h mean needs the price rule's bucket coverage; the sign change needs both rates of a printable size.
HORIZON_DIGEST = "9222de8688979e48f264ed141f1608c0446194a85d2230e1e0511acd4e168411"
# the versions whose 1h range / volume baselines follow the C1 same-day-type rule
DAY_TYPE_VERSIONS = ("BETA_HORIZON_TOD_V3", "BETA_HORIZON_TOD_V4", "BETA_HORIZON_TOD_V5", "BETA_HORIZON_TOD_V6")
# a venue's live funding is polled about every minute; one older than this is stale and leaves the median
FUNDING_MAX_AGE = timedelta(minutes=15)
# the sign-change rule needs both rates at least this large (0,001 % per 8 h prints; 0,000 % does not)
FUNDING_SIGN_MIN = 0.00001

_H1_BUCKETS = 12
_H4_BUCKETS = 48
_H24_BUCKETS = 288
_H24_PRICE_MIN = 282
_METRICS = ("range_width_pct_median", "price_move_pct_median", "volume_notional_usd_sum")
_PRIOR_DAYS = 30
_DAY_TYPE_TOD_METRICS = ("range_width_pct_median", "volume_notional_usd_sum")
_DAY_TYPE_MIN_DAYS = 8
_TOLERANCE_MIN = 30
_MATURE_DAYS = 20
_H24_BASELINE = ("range_width_pct", "volume_notional_usd")


def horizon_definition() -> dict:
    return {
        "version": HORIZON_VERSION,
        "presentation_only": True,
        "window_buckets_1h": _H1_BUCKETS,
        "window_buckets_4h": _H4_BUCKETS,
        "window_buckets_24h": _H24_BUCKETS,
        "h24_price_range_min_buckets": _H24_PRICE_MIN,
        "h24_price_range_requires_first_and_last": True,
        "h24_volume_ratio_requires_every_bucket": True,
        "h24_volume_complete_requires_every_venue": "no bucket where some configured venues carry a 5m kline "
                                                    "close and others none; otherwise the volume is partial "
                                                    "and no 24h baseline day (a venue without any 1m bar did "
                                                    "not contribute; one with 1-4 bars, or a bucket with no "
                                                    "venue's OHLC, is not detected)",
        "baseline_prior_utc_days": _PRIOR_DAYS,
        "baseline_1h_tolerance_min": _TOLERANCE_MIN,
        "baseline_1h": "median of rolling-1h samples whose window end is within "
                       "±tolerance of the same UTC time of day, then the median of those daily values",
        "baseline_1h_day_type": {
            "metrics": list(_DAY_TYPE_TOD_METRICS),
            "rule": "only prior days whose type (UTC date of W - d days - 1h) equals the evaluated "
                    "window's type (UTC date of its start); Saturday/Sunday = WEEKEND",
            "min_days": _DAY_TYPE_MIN_DAYS,
            "fallback": "NONE (no median below min_days)",
            "other_metrics": "price move keeps all days and baseline_mature_days; 4h and 24h unchanged",
            "source": "WEEKDAY_WEEKEND_BASELINE_UNIT_V2 candidate C1 (evaluator 86b2c09)",
        },
        "baseline_4h": "the baseline_1h rule over rolling-4h samples (48 buckets), all days",
        "h4_window_requires_every_bucket": True,
        "baseline_24h": "one rolling-24h value per prior UTC day ending at the same "
                        "UTC time of day, then the median; mature at baseline_mature_days",
        "baseline_mature_days": _MATURE_DAYS,
        "price": "median over venues of (last close - first open) / first open",
        "range": "median over venues of (max high - min low) / first open",
        "volume": "sum of the 5m cross-venue volume sums",
        "taker": "sum of 5m taker_delta_notional_usd_sum; a missing bucket is not a partial sum",
        "funding_now": {"source": "each venue's newest live funding_rate row before data-through",
                        "max_age_min": int(FUNDING_MAX_AGE.total_seconds() // 60),
                        "aggregate": "median of the fresh venues; fewer than min_venues: none",
                        "unit": "rate per 8h settlement (all three venues settle every 8h, VPS 2026-10-08)"},
        "funding_24h_avg": "mean of funding_rate_median over the 24h buckets; needs h24_price_range_min_buckets "
                           "present (the historical tape median carries no age bound)",
        "funding_sign_change_min_abs_rate": FUNDING_SIGN_MIN,
        "oi": {
            "source": "stage-1 open_interest as-of, not compounded tape oi_change_pct",
            "tolerance_min": 2,
            "same_oi_unit_and_contract_value": True,
            "change": "(end - start) / start",
            "aggregate": "median of venue percents",
            "min_venues": "config min_venues; fewer venues: no change (never one venue's figure)",
            "never_usd_sum": True,
        },
        "liquidations": "per venue, never summed across venues; a missing per-venue "
                        "value is not zero; missing buckets mark every venue as a lower "
                        "bound; Binance is always a lower bound",
        "changes_vs_previous_24h": "ordered presentation rules from horizon_changes; at most 3 lines",
        "changes_checked": "the rules whose inputs were present on both windows; 'none' is said only "
                           "over these",
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


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        return dt.astimezone(timezone.utc)
    return dt


def data_through(as_of_bucket: datetime) -> datetime:
    return _utc(as_of_bucket) + BUCKET


def oi_boundaries(as_of_bucket: datetime) -> tuple:
    """Window ends and starts that the OI as-of read must cover: t, t−1h, t−4h, t−24h."""
    end = data_through(as_of_bucket)
    return (end - timedelta(hours=1), end - timedelta(hours=4), end - timedelta(hours=24), end)


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


def _baseline_1h(cfg, metrics_by_bucket: Mapping[datetime, Mapping], end_bucket: datetime) -> dict:
    return _baseline_tod(cfg, metrics_by_bucket, end_bucket, _H1_BUCKETS, day_type=True)


def _baseline_tod(cfg, metrics_by_bucket: Mapping[datetime, Mapping], end_bucket: datetime,
                  n: int, *, day_type: bool = False) -> dict:
    """Time-of-day baseline of an n-bucket rolling window (12 = 1h, 48 = 4h). With
    `day_type` (C1, 1h only), the range and volume baselines use only prior days of the
    evaluated window's UTC day type and need _DAY_TYPE_MIN_DAYS of them; no fallback."""
    from .context import rolling_window_values
    from .day_type import tod_day_type, window_day_type
    window_end = data_through(end_bucket)
    target = window_end.hour * 60 + window_end.minute
    daily = {m: [] for m in _METRICS}
    own_type = window_day_type(end_bucket, n) if day_type else None
    for d in range(1, _PRIOR_DAYS + 1):
        same_type = (not day_type) or tod_day_type(window_end, d) == own_type
        day = (window_end - timedelta(days=d)).date()
        midnight = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        samples = {m: [] for m in _METRICS}
        for delta in range(-_TOLERANCE_MIN, _TOLERANCE_MIN + 1, 5):
            wend = midnight + timedelta(minutes=target + delta)
            sample = rolling_window_values(cfg, metrics_by_bucket, wend - BUCKET, n)
            if sample is None:
                continue
            for m in _METRICS:
                if sample.get(m) is not None:
                    samples[m].append(float(sample[m]))
        for m in _METRICS:
            if samples[m] and (same_type or m not in _DAY_TYPE_TOD_METRICS):
                daily[m].append(_median(samples[m]))
    medians = {}
    days = {}
    for m in _METRICS:
        days[m] = len(daily[m])
        need = _DAY_TYPE_MIN_DAYS if day_type and m in _DAY_TYPE_TOD_METRICS else _MATURE_DAYS
        medians[m] = _median(daily[m]) if days[m] >= need else None
    out = {"days": days, "median": medians}
    if day_type:
        out["day_type"] = own_type
    return out


def _ratio(current: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if current is None or baseline is None or baseline == 0:
        return None
    return float(current) / float(baseline)


def _sum_metric(buckets, metrics_by_bucket, key: str) -> Optional[float]:
    total = 0.0
    for b in buckets:
        row = metrics_by_bucket.get(b)
        if row is None or row.get(key) is None:
            return None
        total += float(row[key])
    return total


def funding_now(cfg, latest: Optional[Mapping], end: datetime) -> dict:
    """«Funding сейчас»: the median of the venues whose newest live rate is at most FUNDING_MAX_AGE old at
    `end`, from at least min_venues venues; a stale venue leaves the median (D3, R3). No rows: none."""
    by = {}
    for ex in cfg.exchanges:
        row = (latest or {}).get(ex)
        fresh = row is not None and row.get("funding_rate") is not None and end - row["ts"] <= FUNDING_MAX_AGE
        by[ex] = float(row["funding_rate"]) if fresh else None
    vals = [v for v in by.values() if v is not None]
    ok = len(vals) >= max(1, int(cfg.min_venues))
    return {"rate": _median(vals) if ok else None, "by_venue": by, "venues": len(vals)}


def _funding_mean(buckets, metrics_by_bucket, min_present: int) -> Optional[float]:
    """The mean of the tape funding median over a window, only with `min_present` buckets present."""
    vals = [float(r["c:funding_rate_median"]) for b in buckets
            for r in [metrics_by_bucket.get(b)] if r is not None and r.get("c:funding_rate_median") is not None]
    return float(sum(vals) / len(vals)) if len(vals) >= min_present else None


def _oi_for(cfg, start: datetime, end: datetime, oi_by_boundary: Optional[Mapping]) -> dict:
    by = {}
    start_map = (oi_by_boundary or {}).get(start) or {}
    end_map = (oi_by_boundary or {}).get(end) or {}
    for ex in cfg.exchanges:
        by[ex] = venue_oi_change_pct(start_map.get(ex), end_map.get(ex))
    vals = [v for v in by.values() if v is not None]
    return {"oi_change_pct": _median(vals) if len(vals) >= max(1, int(cfg.min_venues)) else None, "oi_by_venue": by}


def span_min_present(n: int) -> int:
    """The 24h completeness rule (282 of 288) scaled to an n-bucket span."""
    return n - (n * (_H24_BUCKETS - _H24_PRICE_MIN)) // _H24_BUCKETS


def rolling_24h_values(cfg, metrics_by_bucket: Mapping[datetime, Mapping], end_bucket: datetime,
                       n: int = _H24_BUCKETS, min_present: int = _H24_PRICE_MIN) -> dict:
    """Rolling 24h over the last 288 closed buckets ending at ``end_bucket``.

    Price and range need at least 282 buckets with the first and last present.
    The rule is applied PER VENUE: a venue is usable when its open (first bucket),
    close (last bucket) and high/low at both ends are present and it has at least
    `min_present` buckets with a valid high/low. A missing row and a present row
    whose kline OHLC is NULL for that venue are both one missing observation;
    neither drops the venue while it stays within the allowance. `price_complete`
    needs `min_venue_coverage` usable venues.
    The volume ratio needs every bucket. A partial sum is kept and marked partial.
    `n` / `min_present` reuse the same rule for another span (the /catchup window).
    The 1h / 4h windows (`beta.context.rolling_window_values`) are stricter and do
    not use this function: there every bucket must be complete.
    """
    buckets = _window_buckets(_utc(end_bucket), n)
    rows = [metrics_by_bucket.get(b) for b in buckets]
    present = sum(row is not None for row in rows)
    first_ok = rows[0] is not None
    last_ok = rows[-1] is not None
    ends_ok = first_ok and last_ok
    price_window = present >= min_present and ends_ok
    vols = []
    volume_gap = False
    venue_gap = False                      # a bucket summed from fewer than every venue (D3, R7)
    for row in rows:
        if row is None or row.get("c:volume_notional_usd_sum") is None:
            volume_gap = True
            continue
        vols.append(float(row["c:volume_notional_usd_sum"]))
        k = sum(row.get(metric_key(ex, "kline_close")) is not None for ex in cfg.exchanges)
        if 0 < k < len(cfg.exchanges):     # some venues there, others not; all-NULL OHLC says nothing of volume
            venue_gap = True
    volume = float(math.fsum(vols)) if vols else None
    volume_complete = (not volume_gap) and (not venue_gap) and present == n and len(vols) == n
    ranges, moves, highs, lows, opens, closes = [], [], [], [], [], []
    if price_window:
        last = len(rows) - 1
        for ex in cfg.exchanges:
            o = rows[0].get(metric_key(ex, "kline_open"))
            c = rows[-1].get(metric_key(ex, "kline_close"))
            if o is None or c is None or o <= 0:
                continue
            hs, ls, ends_ok_ex = [], [], True
            for idx, row in enumerate(rows):
                if row is None:
                    continue                                   # missing row: one missing observation
                h = row.get(metric_key(ex, "kline_high"))
                low = row.get(metric_key(ex, "kline_low"))
                if h is None or low is None:
                    if idx in (0, last):                       # the ends stay mandatory
                        ends_ok_ex = False
                        break
                    continue                                   # internal OHLC gap: one missing observation
                hs.append(float(h))
                ls.append(float(low))
            if not ends_ok_ex or len(hs) < min_present:        # per-venue allowance
                continue
            ranges.append((max(hs) - min(ls)) / float(o) * 100.0)
            moves.append((float(c) - float(o)) / float(o) * 100.0)
            highs.append(max(hs))
            lows.append(min(ls))
            opens.append(float(o))
            closes.append(float(c))
    enough = len(moves) >= cfg.min_venues
    return {
        "buckets": buckets,
        "buckets_present": present,
        "buckets_expected": n,
        "price_complete": bool(price_window and enough),
        "volume_complete": bool(volume_complete),
        "volume_partial": bool(volume is not None and not volume_complete),
        "volume_venue_gap": bool(venue_gap),
        "price_move_pct": _median(moves) if enough else None,
        "range_width_pct": _median(ranges) if enough else None,
        "high": _median(highs) if enough else None,
        "low": _median(lows) if enough else None,
        "open": _median(opens) if enough else None,
        "close": _median(closes) if enough else None,
        "volume_notional_usd": volume,
        "buckets_missing": present < n,
    }


def _baseline_24h(cfg, metrics_by_bucket, end_bucket: datetime) -> dict:
    daily = {m: [] for m in _H24_BASELINE}
    end_bucket = _utc(end_bucket)
    for d in range(1, _PRIOR_DAYS + 1):
        sample = rolling_24h_values(cfg, metrics_by_bucket, end_bucket - timedelta(days=d))
        if sample["price_complete"] and sample["range_width_pct"] is not None:
            daily["range_width_pct"].append(float(sample["range_width_pct"]))
        if sample["volume_complete"] and sample["volume_notional_usd"] is not None:
            daily["volume_notional_usd"].append(float(sample["volume_notional_usd"]))
    days = {m: len(daily[m]) for m in _H24_BASELINE}
    median = {m: _median(daily[m]) if days[m] >= _MATURE_DAYS else None for m in _H24_BASELINE}
    return {"days": days, "median": median}


def select_changes(cfg, *, range_w, range_p, volume_w, volume_p, volume_w_complete: bool,
                   volume_p_complete: bool, price_w, oi_w, funding_now, funding_p) -> list:
    """The four §8 rules, in order, capped at 3. Thresholds come from ``horizon_changes``."""
    th = cfg.section("horizon_changes")
    lines = []
    if range_w is not None and range_p not in (None, 0):
        ratio = float(range_w) / float(range_p)
        if ratio >= float(th["range_wider_ratio"]):
            lines.append({"rule": "range", "direction": "wider", "w": float(range_w), "p": float(range_p)})
        elif ratio <= float(th["range_narrower_ratio"]):
            lines.append({"rule": "range", "direction": "narrower", "w": float(range_w), "p": float(range_p)})
    if volume_w_complete and volume_p_complete and volume_w is not None and volume_p not in (None, 0):
        ratio = float(volume_w) / float(volume_p)
        if ratio >= float(th["volume_higher_ratio"]):
            lines.append({"rule": "volume", "direction": "higher", "w": float(volume_w), "p": float(volume_p)})
        elif ratio <= float(th["volume_lower_ratio"]):
            lines.append({"rule": "volume", "direction": "lower", "w": float(volume_w), "p": float(volume_p)})
    if (oi_w is not None and price_w is not None
            and abs(float(oi_w)) >= float(th["oi_abs_pct_min"])
            and abs(float(price_w)) >= float(th["price_abs_pct_min"])
            and float(oi_w) != 0 and float(price_w) != 0):
        lines.append({"rule": "oi_price", "oi_up": float(oi_w) > 0, "price_up": float(price_w) > 0})
    if (funding_now is not None and funding_p is not None
            and abs(float(funding_now)) >= FUNDING_SIGN_MIN and abs(float(funding_p)) >= FUNDING_SIGN_MIN
            and (float(funding_now) > 0) != (float(funding_p) > 0)):
        lines.append({"rule": "funding", "positive": float(funding_now) > 0})
    return lines[:3]


def changes_checked(*, range_w, range_p, volume_w, volume_p, volume_w_complete: bool, volume_p_complete: bool,
                    price_w, oi_w, funding_now, funding_p) -> list:
    """The `select_changes` rules whose inputs exist on both windows: «no large change» is said only over
    these, and never when none could be computed (D3, R6)."""
    out = []
    if range_w is not None and range_p not in (None, 0):
        out.append("range")
    if volume_w_complete and volume_p_complete and volume_w is not None and volume_p not in (None, 0):
        out.append("volume")
    if oi_w is not None and price_w is not None:
        out.append("oi_price")
    if funding_now is not None and funding_p is not None:
        out.append("funding")
    return out


def _empty_metric_baseline() -> dict:
    return {"days": {m: 0 for m in _METRICS}, "median": {m: None for m in _METRICS}}


def build_horizons(cfg, *, as_of_bucket: datetime, metrics_by_bucket: Mapping[datetime, Mapping],
                   oi_by_boundary: Optional[Mapping] = None, funding_latest: Optional[Mapping] = None) -> dict:
    """Language-neutral 1h and 24h blocks. ``as_of_bucket`` is the last closed 5m open time."""
    from .context import rolling_1h_values
    as_of_bucket = _utc(as_of_bucket)
    end = data_through(as_of_bucket)
    h1_buckets = _window_buckets(as_of_bucket, int(cfg.section("context")["rolling_buckets"]))
    h1_missing = any(metrics_by_bucket.get(b) is None for b in h1_buckets)
    cur = None if h1_missing else rolling_1h_values(cfg, metrics_by_bucket, as_of_bucket)
    h1_complete = cur is not None
    base = _baseline_1h(cfg, metrics_by_bucket, as_of_bucket) if h1_complete else _empty_metric_baseline()
    price = None if not h1_complete else cur.get("price_move_pct_median")
    rng = None if not h1_complete else cur.get("range_width_pct_median")
    vol = None if not h1_complete else cur.get("volume_notional_usd_sum")
    fnow = funding_now(cfg, funding_latest, end)
    funding = fnow["rate"]
    oi_1h = _oi_for(cfg, end - timedelta(hours=1), end, oi_by_boundary)
    h4 = _window_block(cfg, metrics_by_bucket, as_of_bucket, _H4_BUCKETS,
                       _oi_for(cfg, end - timedelta(hours=4), end, oi_by_boundary))
    h24 = rolling_24h_values(cfg, metrics_by_bucket, as_of_bucket)
    h24_buckets = h24["buckets"]
    base24 = _baseline_24h(cfg, metrics_by_bucket, as_of_bucket)
    oi_24 = _oi_for(cfg, end - timedelta(hours=24), end, oi_by_boundary)
    prev_end = as_of_bucket - timedelta(hours=24)
    prev = rolling_24h_values(cfg, metrics_by_bucket, prev_end)
    prev_buckets = prev["buckets"]
    change_inputs = dict(
        range_w=h24["range_width_pct"] if h24["price_complete"] else None,
        range_p=prev["range_width_pct"] if prev["price_complete"] else None,
        volume_w=h24["volume_notional_usd"],
        volume_p=prev["volume_notional_usd"],
        volume_w_complete=h24["volume_complete"],
        volume_p_complete=prev["volume_complete"],
        price_w=h24["price_move_pct"] if h24["price_complete"] else None,
        oi_w=oi_24["oi_change_pct"],
        funding_now=None if funding is None else float(funding),
        funding_p=_funding_mean(prev_buckets, metrics_by_bucket, _H24_PRICE_MIN),
    )
    changes = select_changes(cfg, **change_inputs)
    checked = changes_checked(**change_inputs)
    return {
        "version": HORIZON_VERSION,
        "digest": verify_horizon_digest(),
        "1h": {
            "complete": h1_complete,
            "window_start": None if not h1_buckets else iso(h1_buckets[0]),
            "window_end": iso(end),
            "price_move_pct": price,
            "range_width_pct": rng,
            "volume_notional_usd": vol,
            "baseline_days": base["days"],
            "baseline_median": base["median"],
            "range_ratio": _ratio(rng, base["median"]["range_width_pct_median"]),
            "volume_ratio": _ratio(vol, base["median"]["volume_notional_usd_sum"]),
            "taker_delta_notional_usd_sum": _sum_metric(h1_buckets, metrics_by_bucket,
                                                       "c:taker_delta_notional_usd_sum"),
            "funding_rate": None if funding is None else float(funding),
            "funding_venues": fnow["venues"],
            "funding_venues_of": len(cfg.exchanges),
            "oi_change_pct": oi_1h["oi_change_pct"],
            "oi_by_venue": oi_1h["oi_by_venue"],
            "liquidations": {
                "buckets_missing": h1_missing,
                "venues": _liq_side(cfg, h1_buckets, metrics_by_bucket, buckets_missing=h1_missing),
            },
        },
        "4h": h4,
        "24h": {
            "price_complete": h24["price_complete"],
            "volume_complete": h24["volume_complete"],
            "volume_partial": h24["volume_partial"],
            "buckets_present": h24["buckets_present"],
            "buckets_expected": h24["buckets_expected"],
            "window_start": iso(h24_buckets[0]),
            "window_end": iso(end),
            "price_move_pct": h24["price_move_pct"] if h24["price_complete"] else None,
            "range_width_pct": h24["range_width_pct"] if h24["price_complete"] else None,
            "high": h24["high"] if h24["price_complete"] else None,
            "low": h24["low"] if h24["price_complete"] else None,
            "volume_notional_usd": h24["volume_notional_usd"],
            "baseline_days": base24["days"],
            "baseline_median": base24["median"],
            "range_ratio": _ratio(h24["range_width_pct"] if h24["price_complete"] else None,
                                  base24["median"]["range_width_pct"]),
            "volume_ratio": _ratio(h24["volume_notional_usd"] if h24["volume_complete"] else None,
                                   base24["median"]["volume_notional_usd"]),
            "taker_delta_notional_usd_sum": _sum_metric(h24_buckets, metrics_by_bucket,
                                                       "c:taker_delta_notional_usd_sum"),
            "funding_rate": None if funding is None else float(funding),
            "funding_venues": fnow["venues"],
            "funding_venues_of": len(cfg.exchanges),
            "funding_rate_avg": _funding_mean(h24_buckets, metrics_by_bucket, _H24_PRICE_MIN),
            "oi_change_pct": oi_24["oi_change_pct"],
            "oi_by_venue": oi_24["oi_by_venue"],
            "liquidations": {
                "buckets_missing": h24["buckets_missing"],
                "venues": _liq_side(cfg, h24_buckets, metrics_by_bucket,
                                    buckets_missing=h24["buckets_missing"]),
            },
            "changes": changes,
            "changes_checked": checked,
        },
    }


def _window_block(cfg, metrics_by_bucket: Mapping[datetime, Mapping], as_of_bucket: datetime, n: int,
                  oi: Mapping) -> dict:
    """The 1h block's fields for an n-bucket window. Every bucket is required."""
    from .context import rolling_window_values
    buckets = _window_buckets(as_of_bucket, n)
    missing = any(metrics_by_bucket.get(b) is None for b in buckets)
    cur = None if missing else rolling_window_values(cfg, metrics_by_bucket, as_of_bucket, n)
    complete = cur is not None
    base = _baseline_tod(cfg, metrics_by_bucket, as_of_bucket, n) if complete else _empty_metric_baseline()
    price = cur.get("price_move_pct_median") if complete else None
    rng = cur.get("range_width_pct_median") if complete else None
    vol = cur.get("volume_notional_usd_sum") if complete else None
    return {
        "complete": complete,
        "window_start": iso(buckets[0]),
        "window_end": iso(data_through(as_of_bucket)),
        "price_move_pct": price,
        "range_width_pct": rng,
        "volume_notional_usd": vol,
        "baseline_days": base["days"],
        "baseline_median": base["median"],
        "range_ratio": _ratio(rng, base["median"]["range_width_pct_median"]),
        "volume_ratio": _ratio(vol, base["median"]["volume_notional_usd_sum"]),
        "taker_delta_notional_usd_sum": _sum_metric(buckets, metrics_by_bucket, "c:taker_delta_notional_usd_sum"),
        "oi_change_pct": oi["oi_change_pct"],
        "oi_by_venue": oi["oi_by_venue"],
        "liquidations": {
            "buckets_missing": missing,
            "venues": _liq_side(cfg, buckets, metrics_by_bucket, buckets_missing=missing),
        },
    }


def empty_horizons() -> dict:
    return {"version": HORIZON_VERSION, "digest": verify_horizon_digest(), "1h": None, "4h": None,
            "24h": None}
