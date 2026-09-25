"""Beta V0.2 state tape: forecast-free Stage-2 materialization + by-value snapshot.

Reuse (unchanged, never re-implemented):
  * analytics.feature_engine.bucket_coordinator.process_stage2_bucket — the
    explicit one-bucket Stage-2 exchange-feature + consensus materialization the
    shadow path uses, WITHOUT the frozen V1 forecast that
    analytics.forecasting.shadow_cycle.process_shadow_cycle adds on top;
  * analytics.percentile_engine.compute.compute_percentile_snapshot — the frozen
    Percentile Contract 0.2.4 core (mid-rank, strictly-earlier window, span tier).

Beta never writes the Stage-2 / frozen forecast tables: vectors are collected in
memory and persisted BY VALUE into beta_state_tape. Percentile history comes from
earlier beta tape rows only (window [B-30d, B)), so the current bucket can never
be part of its own sample window (the percentile core re-validates this and
fails loudly on any lookahead sample).
"""
from __future__ import annotations

import hashlib
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from analytics.feature_engine.bucket_coordinator import Stage2BucketResult, process_stage2_bucket
from analytics.feature_engine.consensus_models import FAMILIES
from analytics.percentile_engine.compute import compute_percentile_snapshot
from analytics.percentile_engine.models import (
    ConfidenceTierThresholds, PercentileRequest, PercentileSample, WINDOW_TIMEDELTAS)
from common.stage2_config import Stage2Config
from common.versioning import canonical_json

from .config import BetaConfig
from .models import ORIGIN_LIVE, TapeRecord

BUCKET = timedelta(minutes=5)

# Consensus metrics the V0.2 rules (and user context) need percentiles for.
CONSENSUS_METRICS = ("price_move_pct_median", "oi_change_pct_median", "range_width_pct_median",
                     "volume_notional_usd_sum", "taker_delta_notional_usd_sum")
# Context-only consensus values stored by value (no percentile).
CONTEXT_METRICS = ("funding_rate_median", "price_direction_agreement", "oi_direction_agreement")
LIQ_SIDES = (("long", "long_liquidation_notional"), ("short", "short_liquidation_notional"))
# Per-venue raw evidence stored by value (no percentile). Additive: existing
# consensus metrics and their percentiles are unchanged. The Stage-2 per-venue
# values live in the snapshot (`venue_raw`, current-bucket venue agreement); only
# the kline OHLC needed by rolling-1h HISTORY lives in `metrics`.
VENUE_RAW_FIELDS = ("price_move_pct", "oi_change_pct", "range_width_pct", "volume_notional_usd",
                    "taker_delta_notional_usd")
VENUE_OHLC_FIELDS = ("open", "high", "low", "close")
# First state-tape schema version carrying the temporal-context inputs above.
TEMPORAL_CONTEXT_SCHEMA_VERSION = 2
# Schema versions whose rows are valid PERCENTILE history for a given current
# version: V2 only ADDS keys, every consensus / liquidation metric (and hence
# every 30d detector percentile) is identical in V1 and V2 rows.
PERCENTILE_HISTORY_SCHEMA_VERSIONS = {1: (1,), 2: (1, 2)}


def carries_temporal_context(state_schema_version: int) -> bool:
    return state_schema_version >= TEMPORAL_CONTEXT_SCHEMA_VERSION
UNMATERIALIZED = "UNMATERIALIZED"


class BetaTapeError(ValueError):
    """Invalid tape construction input (fail loudly)."""


def _utc(dt: datetime, name: str) -> datetime:
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise BetaTapeError(f"{name} must be a UTC-aware datetime")
    return dt


def select_latest_closed_bucket(now: datetime, *, grace_s: int) -> datetime:
    """Latest 5m bucket whose close (+grace) is <= now."""
    effective = _utc(now, "now") - timedelta(seconds=grace_s)
    floored = effective.replace(second=0, microsecond=0,
                                minute=effective.minute - effective.minute % 5)
    return floored - BUCKET


def validate_bucket(bucket_ts: datetime) -> datetime:
    _utc(bucket_ts, "bucket_ts")
    if bucket_ts.second or bucket_ts.microsecond or bucket_ts.minute % 5:
        raise BetaTapeError("bucket_ts must be aligned to the 5m grid")
    return bucket_ts


def metric_key(scope_exchange: Optional[str], metric: str) -> str:
    return f"c:{metric}" if scope_exchange is None else f"x:{scope_exchange}:{metric}"


def sha256_json(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def iso(dt: Optional[datetime]) -> Optional[str]:
    return None if dt is None else dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ---- in-memory Stage-2 writers (beta never writes Stage-2 tables) ------------
class CollectingWriter:
    def __init__(self):
        self.exchange_vectors: list = []
        self.consensus_vectors: list = []

    async def upsert_exchange_feature_vectors(self, rows):
        self.exchange_vectors.extend(rows)
        return len(rows)

    async def upsert_consensus_feature_vectors(self, rows):
        self.consensus_vectors.extend(rows)
        return len(rows)


async def materialize_bucket(reader, stage2_config: Stage2Config, cfg: BetaConfig, *,
                             bucket_ts: datetime, code_version: str,
                             liquidation_feed_available_by_exchange: Mapping[str, bool],
                             ) -> Stage2BucketResult:
    """ONE explicit Stage-2 bucket materialization (no forecast, no DB write)."""
    writer = CollectingWriter()
    return await process_stage2_bucket(
        reader, writer, writer, stage2_config,
        exchanges=cfg.exchanges, symbol=cfg.symbol, market_type=cfg.market_type,
        timeframe=cfg.timeframe, bucket_ts=validate_bucket(bucket_ts),
        code_version=code_version,
        liquidation_feed_available_by_exchange=liquidation_feed_available_by_exchange)


# ---- venue heartbeat (DB-derived; see beta/health.py for the rows) -----------
def venue_heartbeat_healthy(live_bars: int, outage_overlap: bool) -> bool:
    """A venue's live stream is healthy for a bucket iff all five 1m bars in it
    were written by the LIVE websocket path and no logged outage overlaps it."""
    return live_bars == 5 and outage_overlap is False


# ---- reference price ------------------------------------------------------------
def reference_price(result: Optional[Stage2BucketResult], cfg: BetaConfig) -> dict:
    """Median close across usable active EFVs. Never a single-venue fallback."""
    closes = {}
    if result is not None:
        for v in result.exchange_features:
            if v.is_usable and not v.has_gap and v.close_price is not None:
                closes[v.exchange] = float(v.close_price)
    exchanges = sorted(closes)
    if len(exchanges) < cfg.min_venues:
        return {"status": "INSUFFICIENT_VENUES", "price": None, "exchanges": exchanges,
                "dispersion_pct": None}
    values = [closes[e] for e in exchanges]
    med = statistics.median(values)
    return {"status": "OK", "price": med, "exchanges": exchanges,
            "dispersion_pct": (max(values) - min(values)) / med * 100.0}


# ---- metrics ------------------------------------------------------------------
def extract_metrics(result: Optional[Stage2BucketResult], cfg: BetaConfig,
                    venue_liq_ok: Mapping[str, bool],
                    venues: Optional[Mapping[str, Mapping[str, Any]]] = None) -> dict:
    """Flat by-value metric map used both as this bucket's values and, later, as
    percentile history. A per-venue liquidation value is recorded ONLY when that
    venue's feed was declared available AND its heartbeat was healthy — otherwise
    None (absence is never a measured zero). The venue's raw 5m kline OHLC is
    recorded by value as ``x:<venue>:kline_<ohlc>``."""
    out: dict[str, Optional[float]] = {}
    c = result.consensus_feature if result is not None else None
    for m in CONSENSUS_METRICS + CONTEXT_METRICS:
        v = None if c is None else getattr(c, m)
        out[metric_key(None, m)] = None if v is None else float(v)
    by_ex = {v.exchange: v for v in (result.exchange_features if result is not None else ())}
    for ex in cfg.exchanges:
        efv = by_ex.get(ex)
        for _side, field in LIQ_SIDES:
            v = None if efv is None else getattr(efv, field)
            if not venue_liq_ok.get(ex, False):
                v = None
            out[metric_key(ex, field)] = None if v is None else float(v)
        if not carries_temporal_context(cfg.state_schema_version):
            continue                               # V1 payload: no kline OHLC
        ohlc = ((venues or {}).get(ex) or {}).get("ohlc") or {}
        for field in VENUE_OHLC_FIELDS:
            v = ohlc.get(field)
            out[metric_key(ex, f"kline_{field}")] = None if v is None else float(v)
    return out


def _venue_payload(cfg: BetaConfig, v: Mapping[str, Any]) -> dict:
    """Per-venue state by value, in the configured schema's shape (V1 has no OHLC)."""
    out = dict(v)
    if not carries_temporal_context(cfg.state_schema_version):
        out.pop("ohlc", None)
    return out


def venue_raw(result: Optional[Stage2BucketResult], cfg: BetaConfig) -> dict:
    """Per-venue raw Stage-2 values of this bucket, by value (None when absent)."""
    by_ex = {v.exchange: v for v in (result.exchange_features if result is not None else ())}
    out = {}
    for ex in cfg.exchanges:
        efv = by_ex.get(ex)
        out[ex] = {f: (None if efv is None or getattr(efv, f) is None else float(getattr(efv, f)))
                   for f in VENUE_RAW_FIELDS}
    return out


def percentile_inputs(result: Optional[Stage2BucketResult]):
    c = result.consensus_feature if result is not None else None
    if c is None:
        return None
    return {"calculation_version": c.calculation_version, "config_hash": c.config_hash,
            "config_version": c.config_version, "feature_schema_version": c.feature_schema_version}


def compute_percentiles(stage2_config: Stage2Config, cfg: BetaConfig, *, bucket_ts: datetime,
                        metrics: Mapping[str, Optional[float]], ident: Mapping[str, Any],
                        code_version: str,
                        history: Sequence[tuple[datetime, Mapping[str, Any]]]) -> dict:
    """Frozen percentile core per metric. `history` = [(bucket_ts, metrics)] of
    EARLIER tape rows of the same calculation_version; the core rejects any sample
    outside [B-30d, B)."""
    tiers = stage2_config.resolve(cfg.symbol)["percentiles"]["confidence_tiers"]
    thresholds = ConfidenceTierThresholds(
        none_below_days=tiers["none_below_days"], low_below_days=tiers["low_below_days"],
        building_below_days=tiers["building_below_days"])
    window = cfg["percentile_window"]
    specs = [("consensus", "", m) for m in CONSENSUS_METRICS]
    specs += [("exchange", ex, f) for ex in cfg.exchanges for _s, f in LIQ_SIDES]
    out = {}
    for scope, ex, metric in specs:
        key = metric_key(ex or None, metric)
        samples = [PercentileSample(
            scope=scope, exchange=ex, symbol=cfg.symbol, market_type=cfg.market_type,
            metric=metric, timeframe=cfg.timeframe, bucket_ts=ts, value=hm.get(key),
            feature_schema_version=ident["feature_schema_version"],
            calculation_version=ident["calculation_version"]) for ts, hm in history]
        snap = compute_percentile_snapshot(PercentileRequest(
            scope=scope, exchange=ex, symbol=cfg.symbol, market_type=cfg.market_type,
            metric=metric, timeframe=cfg.timeframe, percentile_window=window,
            bucket_ts=bucket_ts, value=metrics.get(key), samples=samples,
            confidence_tier_thresholds=thresholds, config_hash=ident["config_hash"],
            config_version=ident["config_version"], code_version=code_version,
            feature_schema_version=ident["feature_schema_version"],
            calculation_version=ident["calculation_version"]))
        out[key] = {"value": snap.value, "rank": snap.percentile_rank, "tier": snap.confidence_tier,
                    "sample_size": snap.sample_size,
                    "window_start": iso(snap.sample_window_start),
                    "window_end": iso(snap.sample_window_end)}
    return out


def history_window(bucket_ts: datetime, cfg: BetaConfig) -> tuple[datetime, datetime]:
    """[start, end) for percentile history — end is the CURRENT bucket (excluded)."""
    return bucket_ts - WINDOW_TIMEDELTAS[cfg["percentile_window"]], bucket_ts


def family_state(result: Optional[Stage2BucketResult], cfg: BetaConfig) -> dict:
    c = result.consensus_feature if result is not None else None
    out = {}
    for fam in FAMILIES:
        if c is None:
            out[fam] = {"available": 0, "expected": len(cfg.exchanges), "contributing": [],
                        "excluded": sorted([ex, "NOT_MATERIALIZED"] for ex in cfg.exchanges),
                        "data_confidence": None, "usable": False}
            continue
        cov, prov = c.coverage_by_metric[fam], c.provenance_by_metric[fam]
        out[fam] = {"available": cov.available, "expected": cov.expected,
                    "contributing": list(prov.contributing),
                    "excluded": [list(p) for p in prov.excluded],
                    "data_confidence": c.data_confidence_by_metric.get(fam),
                    "usable": cov.available >= cfg.min_venues}
    return out


def build_tape_record(cfg: BetaConfig, *, bucket_ts: datetime, origin: str,
                      result: Optional[Stage2BucketResult], materialization_error: Optional[str],
                      venues: Mapping[str, Mapping[str, Any]], percentiles: Optional[Mapping],
                      code_version: str, feature_code_version: str,
                      raw_revision_before: Optional[int], raw_revision_after: Optional[int],
                      evaluated_at: datetime, rule_evaluations: Optional[Mapping] = None,
                      ) -> TapeRecord:
    """Assemble one immutable by-value snapshot. `venues[ex]` carries
    declared_available / live_bars / outage_overlap / heartbeat_healthy."""
    validate_bucket(bucket_ts)
    _utc(evaluated_at, "evaluated_at")
    ident = percentile_inputs(result)
    materialized = ident is not None
    venue_liq_ok = {ex: bool(v["declared_available"] and v["heartbeat_healthy"])
                    for ex, v in venues.items()}
    metrics = extract_metrics(result, cfg, venue_liq_ok, venues)
    barrier_stale = (raw_revision_before != raw_revision_after)
    lag_s = (evaluated_at - (bucket_ts + BUCKET)).total_seconds()
    fresh = bool(materialized and not barrier_stale and lag_s <= cfg["max_state_age_s"])
    failures = [] if result is None else [[f.exchange, f.reason, f.error_type] for f in result.failures]
    features = {
        "identity": {"symbol": cfg.symbol, "market_type": cfg.market_type,
                     "timeframe": cfg.timeframe, "bucket_ts": iso(bucket_ts),
                     "calculation_version": ident["calculation_version"] if ident else UNMATERIALIZED,
                     "feature_schema_version": ident["feature_schema_version"] if ident else None,
                     "stage2_config_hash": ident["config_hash"] if ident else None,
                     "stage2_config_version": ident["config_version"] if ident else None},
        "materialized": materialized,
        "materialization_error": materialization_error,
        "feature_code_version": feature_code_version,
        "metrics": metrics,
        "percentiles": percentiles,
        "families": family_state(result, cfg),
        "venues": {ex: _venue_payload(cfg, venues[ex]) for ex in cfg.exchanges},
        "reference": reference_price(result, cfg),
        "exchange_failures": failures,
        "raw_revision": raw_revision_before,
    }
    if carries_temporal_context(cfg.state_schema_version):
        features["venue_raw"] = venue_raw(result, cfg)
    feature_digest = sha256_json(features)
    snapshot = dict(features)
    snapshot.update({
        "state_schema_version": cfg.state_schema_version, "rules_version": cfg.rules_version,
        "rules_digest": cfg.rules_digest, "config_digest": cfg.config_digest,
        "code_version": code_version, "origin": origin, "evaluated_at": iso(evaluated_at),
        "evaluation_lag_s": lag_s, "raw_revision_after": raw_revision_after,
        "stale_barrier": barrier_stale, "evaluation_fresh": fresh,
        "rule_evaluations": dict(rule_evaluations) if rule_evaluations is not None else None,
        "feature_digest": feature_digest,
    })
    return TapeRecord(
        symbol=cfg.symbol, market_type=cfg.market_type, timeframe=cfg.timeframe,
        bucket_ts=bucket_ts,
        calculation_version=features["identity"]["calculation_version"],
        state_schema_version=cfg.state_schema_version, rules_version=cfg.rules_version,
        rules_digest=cfg.rules_digest, origin=origin, materialized=materialized,
        evaluation_fresh=fresh if origin == ORIGIN_LIVE else False,
        code_version=code_version, config_digest=cfg.config_digest,
        raw_revision=raw_revision_before, evaluated_at=evaluated_at, metrics=metrics,
        snapshot=snapshot, feature_digest=feature_digest, snapshot_digest=sha256_json(snapshot))


def with_rule_evaluations(cfg: BetaConfig, rec: TapeRecord, evaluations: Mapping) -> TapeRecord:
    """Return the same snapshot with rule evaluations attached (digest recomputed).
    Features (and feature_digest) are unchanged."""
    snap = dict(rec.snapshot)
    snap["rule_evaluations"] = dict(evaluations)
    return TapeRecord(**{**rec.__dict__, "snapshot": snap, "snapshot_digest": sha256_json(snap)})
