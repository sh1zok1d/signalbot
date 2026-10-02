"""V0.3 market briefing read model (docs/BETA_V0_3_MARKET_BRIEFING.md §1.0-§1.4).

Pure functions, no I/O. This is not detection: it never enters the rules digest,
never writes the state tape, never reads forward outcomes and never changes a
detector episode or push decision.

* Horizons (§1.0): rolling windows ending at the last closed 5m bucket - 5m (1
  bucket), 1h (12), 4h (48), 24h (288). Calendar candles are never used.
* Baselines: windows of the same length ending at the same 5m slot of day on prior
  days (30 days for 5m and 1h, 90 days for 4h and 24h). Mid-rank percentiles.
* State labels ``BETA_MARKET_STATE_LABELS_V1`` (§1.3): deterministic, first match
  wins, every condition against the horizon's own baseline percentile. Inferred
  positioning reads "похоже на ..." (the PRICE_OI pilot is BALANCE_FAILED).
* Significance (§1.4): decomposed per dimension on the rolling 1h window, plus
  cross-venue agreement on the price-and-flow direction. No composite score.
* Briefing episodes ``BETA_BRIEFING_EPISODES_V1``: a causal scan over 5m buckets.
  The legacy 5m detector is not an input.

Inputs:
  metrics_by_bucket   {bucket_open_utc: tape metrics} (``c:`` consensus values,
                      ``x:<venue>:kline_*`` OHLC and per-venue liquidations)
  venue_raw_by_bucket {bucket_open_utc: {venue: {"taker_delta_notional_usd": ...}}}
                      (the tape snapshot ``venue_raw``)
  oi_rows_by_venue    {venue: Stage-1 open_interest rows (ts, oi_raw, oi_unit,
                      contract_value)}; read as-of with beta.oi_asof.pick_oi_asof
"""
from __future__ import annotations

import bisect
import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from common.versioning import canonical_json

from .oi_asof import OI_ASOF_TOLERANCE, pick_oi_asof, venue_oi_change_pct
from .state_tape import BUCKET, iso, metric_key

BRIEFING_PROJECTIONS_VERSION = "BETA_BRIEFING_PROJECTIONS_V1"

HORIZON_BUCKETS = {"5m": 1, "1h": 12, "4h": 48, "24h": 288}
HORIZONS = tuple(HORIZON_BUCKETS)
BASELINE_DAYS = {"5m": 30, "1h": 30, "4h": 90, "24h": 90}
MATURE_DAYS = {"5m": 20, "1h": 20, "4h": 60, "24h": 60}
# Present buckets required for a window; the first and the last bucket are always required.
MIN_PRESENT = {"5m": 1, "1h": 12, "4h": 47, "24h": 282}

# ---- frozen vocabulary (§1.3) ---------------------------------------------------
LONG_FLUSH = "LONG_FLUSH"
SHORT_FLUSH = "SHORT_FLUSH"
ABSORBED_BUYING = "ABSORBED_BUYING"
ABSORBED_SELLING = "ABSORBED_SELLING"
SHORT_COVERING = "SHORT_COVERING"
LONG_CLOSING = "LONG_CLOSING"
LONG_BUILDUP = "LONG_BUILDUP"
SHORT_BUILDUP = "SHORT_BUILDUP"
COMPRESSION = "COMPRESSION"
POSITION_BUILDUP_FLAT = "POSITION_BUILDUP_FLAT"
DELEVERAGING = "DELEVERAGING"
NORMAL = "NORMAL"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
DATA_INCOMPLETE = "DATA_INCOMPLETE"

# Evaluation order (first match wins). Part of the labels identity.
LABEL_ORDER = (LONG_FLUSH, SHORT_FLUSH, ABSORBED_BUYING, ABSORBED_SELLING, SHORT_COVERING,
               LONG_CLOSING, LONG_BUILDUP, SHORT_BUILDUP, COMPRESSION, POSITION_BUILDUP_FLAT,
               DELEVERAGING, NORMAL)

LABEL_TEXT_RU = {
    LONG_FLUSH: "вынос лонгов",
    SHORT_FLUSH: "вынос шортов",
    ABSORBED_BUYING: "похоже на поглощение агрессивных покупок",
    ABSORBED_SELLING: "похоже на поглощение агрессивных продаж",
    SHORT_COVERING: "похоже на закрытие шортов",
    LONG_CLOSING: "похоже на закрытие лонгов",
    LONG_BUILDUP: "похоже на рост с набором новых лонгов",
    SHORT_BUILDUP: "похоже на снижение с набором новых шортов",
    COMPRESSION: "сжатие",
    POSITION_BUILDUP_FLAT: "похоже на набор позиций без движения цены",
    DELEVERAGING: "похоже на разгрузку рынка",
    NORMAL: "обычное состояние",
    INSUFFICIENT_HISTORY: "мало истории",
    DATA_INCOMPLETE: "данные неполные",
}

_LABEL_KEYS = ("price_moved_pct", "price_flat_pct", "oi_moved_pct", "taker_tail_pct",
               "liq_tail_pct", "liq_min_venues", "compression_range_pct")
_EPISODE_KEYS = ("significance_tail_pct", "significance_min_dims",
                 "significance_min_agreeing_venues", "close_delay_buckets", "merge_gap_min")

# Version label -> parameter digest. A parameter change without a NEW label fails loudly.
KNOWN_LABELS_DIGESTS = {
    "BETA_MARKET_STATE_LABELS_V1": "6686be844ca7f2e4918fcfdf42ecf7ce1782895c0201b9adbc652cc26470c9fe",
}
KNOWN_EPISODES_DIGESTS = {
    "BETA_BRIEFING_EPISODES_V1": "8832a20b81b0ca34d120b23d7780f11ce5223b9eff8f795e8a2e4060b47e7670",
}


class BriefingVersionError(ValueError):
    """Briefing parameters do not match their pinned version label."""


def _digest(obj) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def projections_payload() -> dict:
    """Code-defined part of the read model (windows, baselines, completeness, order)."""
    return {
        "version": BRIEFING_PROJECTIONS_VERSION,
        "horizon_buckets": HORIZON_BUCKETS,
        "baseline_days": BASELINE_DAYS,
        "mature_days": MATURE_DAYS,
        "min_present_buckets": MIN_PRESENT,
        "window": "rolling, ending at the last closed 5m bucket; never calendar candles",
        "baseline": "one window of the same length per prior UTC day, ending at the same 5m slot",
        "percentile": "mid-rank: (count below + 0.5 * count equal) / n",
        "price": "median over venues (>= min_venue_coverage) of (last close - first open) / first open",
        "range": "median over venues of (max high - min low) / first open",
        "volume_taker": "sums require every bucket; a partial sum is not a value",
        "buy_share": "(volume + taker delta) / (2 * volume) from consensus sums",
        "oi": "stage-1 as-of at window start and end per venue; median over >= min_venue_coverage venues",
        "liquidations": "per venue and side; every bucket required; never summed across venues",
        "label_order": LABEL_ORDER,
        "label_text_ru": LABEL_TEXT_RU,
    }


def labels_payload(cfg) -> dict:
    b = cfg.section("briefing")
    return {"version": b["labels_version"], "projections": _digest(projections_payload()),
            **{k: b[k] for k in _LABEL_KEYS}}


def episodes_payload(cfg) -> dict:
    b = cfg.section("briefing")
    return {"version": b["episodes_version"], "labels": _digest(labels_payload(cfg)),
            "significance_horizon": "1h",
            "dimensions": ("price_abs", "oi_abs", "volume", "taker_abs", "liq_total"),
            "venue_agreement": "venue price sign and venue taker-delta sign both equal the consensus signs",
            "closing": "after close_delay_buckets consecutive non-significant buckets; an unevaluable bucket "
                       "counts as non-significant",
            "merge": "causal: an opening with the same label within merge_gap_min of the last close "
                     "resumes that episode",
            **{k: b[k] for k in _EPISODE_KEYS}}


def verify_versions(cfg) -> dict:
    b = cfg.section("briefing")
    ld, ed = _digest(labels_payload(cfg)), _digest(episodes_payload(cfg))
    if KNOWN_LABELS_DIGESTS.get(b["labels_version"]) != ld:
        raise BriefingVersionError(f"labels {b['labels_version']!r} is not pinned to digest {ld}")
    if KNOWN_EPISODES_DIGESTS.get(b["episodes_version"]) != ed:
        raise BriefingVersionError(f"episodes {b['episodes_version']!r} is not pinned to digest {ed}")
    return {"labels_version": b["labels_version"], "labels_digest": ld,
            "episodes_version": b["episodes_version"], "episodes_digest": ed}


# ---- helpers -------------------------------------------------------------------------
def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("datetimes must be timezone-aware UTC")
    return dt.astimezone(timezone.utc)


def _median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2.0


def percentile_rank(value: Optional[float], samples: Sequence[float]) -> Optional[float]:
    """Mid-rank percentile of ``value`` among ``samples``; None without a value or samples."""
    if value is None or not samples:
        return None
    below = sum(1 for s in samples if s < value)
    equal = sum(1 for s in samples if s == value)
    return (below + 0.5 * equal) / len(samples)


def _sign(x: Optional[float]) -> int:
    if x is None or x == 0:
        return 0
    return 1 if x > 0 else -1


@dataclass(frozen=True)
class BriefingInputs:
    metrics_by_bucket: Mapping[datetime, Mapping[str, Any]]
    venue_raw_by_bucket: Mapping[datetime, Mapping[str, Mapping[str, Any]]] = field(default_factory=dict)
    oi_rows_by_venue: Mapping[str, Sequence[Mapping[str, Any]]] = field(default_factory=dict)

    def oi_index(self) -> dict:
        out = {}
        for ex, rows in self.oi_rows_by_venue.items():
            ordered = sorted((r for r in rows if r.get("ts") is not None), key=lambda r: r["ts"])
            out[ex] = ([r["ts"] for r in ordered], ordered)
        return out


def _oi_asof(index, venue: str, boundary: datetime) -> Optional[dict]:
    entry = index.get(venue)
    if entry is None:
        return None
    ts, rows = entry
    lo = bisect.bisect_left(ts, boundary - OI_ASOF_TOLERANCE)
    hi = bisect.bisect_right(ts, boundary)
    return pick_oi_asof(rows[lo:hi], boundary) if hi > lo else None


# ---- windows ---------------------------------------------------------------------------
def window_buckets(horizon: str, end_bucket: datetime) -> list:
    n = HORIZON_BUCKETS[horizon]
    end_bucket = _utc(end_bucket)
    return [end_bucket - i * BUCKET for i in range(n - 1, -1, -1)]


def window(cfg, inp: BriefingInputs, horizon: str, end_bucket: datetime, *, oi_index=None) -> dict:
    """Aggregates of one rolling window ending at ``end_bucket`` (inclusive). Only buckets
    at or before ``end_bucket`` are read."""
    buckets = window_buckets(horizon, end_bucket)
    mb = inp.metrics_by_bucket
    rows = [mb.get(b) for b in buckets]
    present = sum(r is not None for r in rows)
    price_ok = rows[0] is not None and rows[-1] is not None and present >= MIN_PRESENT[horizon]
    every = present == len(buckets)

    moves, ranges, venue_move = [], [], {}
    for ex in cfg.exchanges:
        venue_move[ex] = None
        if not price_ok:
            continue
        o = rows[0].get(metric_key(ex, "kline_open"))
        c = rows[-1].get(metric_key(ex, "kline_close"))
        hs, ls, bad = [], [], o is None or c is None or o <= 0
        for r in rows:
            if r is None or bad:
                continue
            h, low = r.get(metric_key(ex, "kline_high")), r.get(metric_key(ex, "kline_low"))
            if h is None or low is None:
                bad = True
                continue
            hs.append(float(h))
            ls.append(float(low))
        if bad or not hs:
            continue
        mv = (float(c) - float(o)) / float(o) * 100.0
        venue_move[ex] = mv
        moves.append(mv)
        ranges.append((max(hs) - min(ls)) / float(o) * 100.0)
    enough = len(moves) >= cfg.min_venues

    def _sum(key):
        if not every:
            return None
        vals = [r.get(key) for r in rows]
        return None if any(v is None for v in vals) else float(math.fsum(float(v) for v in vals))

    volume = _sum("c:volume_notional_usd_sum")
    delta = _sum("c:taker_delta_notional_usd_sum")
    buy_share = None
    if volume is not None and delta is not None and volume > 0:
        buy_share = (volume + delta) / (2.0 * volume)

    venue_delta = {}
    for ex in cfg.exchanges:
        vals = [((inp.venue_raw_by_bucket.get(b) or {}).get(ex) or {}).get("taker_delta_notional_usd")
                for b in buckets]
        venue_delta[ex] = (None if any(v is None for v in vals)
                           else float(math.fsum(float(v) for v in vals)))

    liq = {}
    for ex in cfg.exchanges:
        liq[ex] = {}
        for side, fld in (("long", "long_liquidation_notional"), ("short", "short_liquidation_notional")):
            vals = None if not every else [r.get(metric_key(ex, fld)) for r in rows]
            liq[ex][side] = (None if vals is None or any(v is None for v in vals)
                             else float(math.fsum(float(v) for v in vals)))

    idx = oi_index if oi_index is not None else inp.oi_index()
    start, end = buckets[0], buckets[-1] + BUCKET
    venue_oi = {ex: venue_oi_change_pct(_oi_asof(idx, ex, start), _oi_asof(idx, ex, end))
                for ex in cfg.exchanges}
    oi_vals = [v for v in venue_oi.values() if v is not None]
    return {
        "horizon": horizon,
        "window_start": iso(start),
        "window_end": iso(end),
        "buckets_present": present,
        "buckets_expected": len(buckets),
        "price_complete": bool(price_ok and enough),
        "price_move_pct": _median(moves) if enough else None,
        "range_width_pct": _median(ranges) if enough else None,
        "venue_price_move_pct": venue_move,
        "volume_notional_usd": volume,
        "taker_delta_notional_usd": delta,
        "buy_share": buy_share,
        "venue_taker_delta_usd": venue_delta,
        "oi_change_pct": _median(oi_vals) if len(oi_vals) >= cfg.min_venues else None,
        "venue_oi_change_pct": venue_oi,
        "liquidations": liq,
    }


def dimensions(cfg, w: Mapping[str, Any]) -> dict:
    """The comparable values of one window (the baseline compares like with like)."""
    out = {
        "price_abs": None if w["price_move_pct"] is None else abs(w["price_move_pct"]),
        "oi_abs": None if w["oi_change_pct"] is None else abs(w["oi_change_pct"]),
        "range": w["range_width_pct"],
        "volume": w["volume_notional_usd"],
        "taker_abs": None if w["buy_share"] is None else abs(w["buy_share"] - 0.5),
    }
    for ex in cfg.exchanges:
        lq = w["liquidations"][ex]
        out[f"liq_long:{ex}"] = lq["long"]
        out[f"liq_short:{ex}"] = lq["short"]
        out[f"liq_total:{ex}"] = (None if lq["long"] is None or lq["short"] is None
                                  else lq["long"] + lq["short"])
    return out


def baseline_samples(cfg, inp: BriefingInputs, horizon: str, end_bucket: datetime, *,
                     oi_index=None) -> dict:
    """Per dimension, one value per prior UTC day: the window of the same length ending
    at the same 5m slot. Days whose window is incomplete for a dimension are skipped."""
    idx = oi_index if oi_index is not None else inp.oi_index()
    samples: dict = {}
    for d in range(1, BASELINE_DAYS[horizon] + 1):
        w = window(cfg, inp, horizon, _utc(end_bucket) - timedelta(days=d), oi_index=idx)
        for k, v in dimensions(cfg, w).items():
            if v is not None:
                samples.setdefault(k, []).append(float(v))
    return samples


def percentiles(cfg, horizon: str, current: Mapping[str, Any], samples: Mapping[str, Sequence[float]]) -> dict:
    """Mid-rank percentile per dimension; None when the baseline is immature."""
    out = {}
    for k, v in dimensions(cfg, current).items():
        s = samples.get(k) or []
        out[k] = percentile_rank(v, s) if len(s) >= MATURE_DAYS[horizon] else None
    return out


# ---- labels (§1.3) -------------------------------------------------------------------
def _liq_tail_venues(cfg, pct: Mapping[str, Optional[float]], side: str, cut: float) -> int:
    return sum(1 for ex in cfg.exchanges
               if pct.get(f"liq_{side}:{ex}") is not None and pct[f"liq_{side}:{ex}"] >= cut)


def state_label(cfg, w: Mapping[str, Any], pct: Mapping[str, Optional[float]]) -> str:
    """BETA_MARKET_STATE_LABELS_V1. Describes what happened in the window; never what follows."""
    cuts = cfg.section("briefing")
    if not w["price_complete"]:
        return DATA_INCOMPLETE
    pp, pr = pct.get("price_abs"), pct.get("range")
    if pp is None or pr is None:
        return INSUFFICIENT_HISTORY
    move = w["price_move_pct"]
    moved = pp >= cuts["price_moved_pct"]
    flat = pp <= cuts["price_flat_pct"]
    up, down = move > 0, move < 0
    pt = pct.get("taker_abs")
    oi, po = w["oi_change_pct"], pct.get("oi_abs")
    oi_known = oi is not None and po is not None
    oi_up = oi_known and oi > 0 and po >= cuts["oi_moved_pct"]
    oi_down = oi_known and oi < 0 and po >= cuts["oi_moved_pct"]

    if moved and oi_down:
        if down and _liq_tail_venues(cfg, pct, "long", cuts["liq_tail_pct"]) >= cuts["liq_min_venues"]:
            return LONG_FLUSH
        if up and _liq_tail_venues(cfg, pct, "short", cuts["liq_tail_pct"]) >= cuts["liq_min_venues"]:
            return SHORT_FLUSH
    if flat and pt is not None and pt >= cuts["taker_tail_pct"] and w["buy_share"] is not None:
        if w["buy_share"] > 0.5:
            return ABSORBED_BUYING
        if w["buy_share"] < 0.5:
            return ABSORBED_SELLING
    if not oi_known:
        return DATA_INCOMPLETE
    if moved and oi_down:
        return SHORT_COVERING if up else LONG_CLOSING
    if moved and oi_up:
        return LONG_BUILDUP if up else SHORT_BUILDUP
    if pr <= cuts["compression_range_pct"] and not oi_down:
        return COMPRESSION
    if flat and oi_up:
        return POSITION_BUILDUP_FLAT
    if flat and oi_down:
        return DELEVERAGING
    return NORMAL


def horizon_view(cfg, inp: BriefingInputs, horizon: str, end_bucket: datetime, *, oi_index=None) -> dict:
    idx = oi_index if oi_index is not None else inp.oi_index()
    w = window(cfg, inp, horizon, end_bucket, oi_index=idx)
    samples = baseline_samples(cfg, inp, horizon, end_bucket, oi_index=idx)
    pct = percentiles(cfg, horizon, w, samples)
    label = state_label(cfg, w, pct)
    return {"window": w, "percentiles": pct,
            "baseline_days": {k: len(v) for k, v in samples.items()},
            "label": label, "label_text_ru": LABEL_TEXT_RU[label]}


def market_state(cfg, inp: BriefingInputs, end_bucket: datetime) -> dict:
    """The Market State block (§1.2): one row per horizon, each against its own baseline."""
    idx = inp.oi_index()
    return {"versions": verify_versions(cfg), "as_of_bucket": iso(_utc(end_bucket)),
            "rows": {h: horizon_view(cfg, inp, h, end_bucket, oi_index=idx) for h in HORIZONS}}


# ---- significance (§1.4) -----------------------------------------------------------
def significance(cfg, view_1h: Mapping[str, Any]) -> dict:
    """Decomposed significance of the rolling 1h window. ``significant`` is None when the
    window or its baseline cannot be evaluated."""
    cuts = cfg.section("briefing")
    w, pct = view_1h["window"], view_1h["percentiles"]
    liq_vals = [pct.get(f"liq_total:{ex}") for ex in cfg.exchanges]
    liq_vals = [v for v in liq_vals if v is not None]
    dims = {"price_abs": pct.get("price_abs"), "oi_abs": pct.get("oi_abs"),
            "volume": pct.get("volume"), "taker_abs": pct.get("taker_abs"),
            "liq_total": _median(liq_vals) if liq_vals else None}
    in_tail = sorted(k for k, v in dims.items() if v is not None and v >= cuts["significance_tail_pct"])
    p_sign, d_sign = _sign(w["price_move_pct"]), _sign(w["taker_delta_notional_usd"])
    agreeing, evaluable = [], []
    for ex in cfg.exchanges:
        vm, vd = w["venue_price_move_pct"].get(ex), w["venue_taker_delta_usd"].get(ex)
        if vm is None or vd is None:
            continue
        evaluable.append(ex)
        if p_sign != 0 and d_sign != 0 and _sign(vm) == p_sign and _sign(vd) == d_sign:
            agreeing.append(ex)
    evaluable_window = w["price_complete"] and dims["price_abs"] is not None
    significant = None
    if evaluable_window:
        significant = (len(in_tail) >= cuts["significance_min_dims"]
                       and len(agreeing) >= cuts["significance_min_agreeing_venues"])
    return {"significant": significant, "dimensions": dims, "dimensions_in_tail": in_tail,
            "venues_agreeing": agreeing, "venues_evaluable": evaluable,
            "label": view_1h["label"]}


# ---- briefing episodes -----------------------------------------------------------
OPEN, CLOSED = "OPEN", "CLOSED"


def scan_episodes(cfg, points: Sequence[tuple]) -> list:
    """BETA_BRIEFING_EPISODES_V1 over ``points`` = [(bucket, significant, label)] in time
    order (one per closed 5m bucket). Causal: each decision uses only earlier points.

    * opens at the first significant bucket;
    * closes after ``close_delay_buckets`` consecutive non-significant buckets
      (``None`` - not evaluable - counts as non-significant); ``end`` is the close of the
      last significant bucket;
    * an opening whose label equals the last closed episode's opening label, within
      ``merge_gap_min`` of that episode's end, resumes it (no new episode, no new push);
    * label changes while open are recorded as (bucket, label).
    """
    cuts = cfg.section("briefing")
    delay = cuts["close_delay_buckets"]
    gap = timedelta(minutes=cuts["merge_gap_min"])
    episodes: list = []
    cur = None
    quiet = 0
    prev_bucket = None
    for bucket, significant, label in points:
        bucket = _utc(bucket)
        if prev_bucket is not None and bucket <= prev_bucket:
            raise ValueError("points must be strictly increasing in time")
        prev_bucket = bucket
        if cur is not None and cur["status"] == OPEN:
            if significant:
                quiet = 0
                cur["last_significant_bucket"] = bucket
                cur["significant_buckets"] += 1
                if label != cur["label_now"]:
                    cur["label_changes"].append((bucket, label))
                    cur["label_now"] = label
            else:
                quiet += 1
                if quiet >= delay:
                    cur["status"] = CLOSED
                    cur["end"] = cur["last_significant_bucket"] + BUCKET
                    cur["closed_at_bucket"] = bucket
            continue
        if not significant:
            continue
        last = episodes[-1] if episodes else None
        if last is not None and last["label_at_open"] == label and bucket - last["end"] < gap:
            last["status"] = OPEN
            last["resumptions"].append(bucket)
            last["last_significant_bucket"] = bucket
            last["significant_buckets"] += 1
            if label != last["label_now"]:
                last["label_changes"].append((bucket, label))
                last["label_now"] = label
            last["end"] = None
            last["closed_at_bucket"] = None
            cur, quiet = last, 0
            continue
        cur = {"episode_id": "BR-" + iso(bucket), "start": bucket, "label_at_open": label,
               "label_now": label, "label_changes": [], "status": OPEN,
               "last_significant_bucket": bucket, "significant_buckets": 1,
               "end": None, "closed_at_bucket": None, "resumptions": []}
        episodes.append(cur)
        quiet = 0
    return episodes
