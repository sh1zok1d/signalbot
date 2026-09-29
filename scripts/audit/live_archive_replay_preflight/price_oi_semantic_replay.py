"""Semantic reconstruction of the current PRICE_OI_CONTRACTION rules.

This is not a replay of historical online runtime behavior. The live archive
supplies market observations. It does not preserve evaluation freshness, the
raw-revision coherence race, or actual alert delivery. Every output row is
labeled ``RECONSTRUCTED_FROM_SIGNALBOT_LIVE_ARCHIVE`` and
``CURRENT_RULE_SEMANTIC_RECONSTRUCTION``.

Feature formulas, consensus, percentile ranking, rule thresholds, and
``STRICT_QUALIFICATION_V1`` episode steps are the current implementations.
The rule adapter does not assert the historical operational gates those
implementations also check at runtime.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional, Sequence

from analytics.feature_engine.bucket_coordinator import (
    EXCHANGE_PROCESSING_FAILED,
    _derive_family_exclusions,
)
from analytics.feature_engine.consensus import compute_consensus_features
from analytics.feature_engine.consensus_input_adapter import build_consensus_feature_request
from analytics.feature_engine.consensus_models import FAMILIES
from analytics.feature_engine.exchange_features import compute_exchange_features
from analytics.feature_engine.input_adapter import build_assembly_context
from analytics.feature_engine.models import (
    ExchangeFeatureRequest,
    ExchangeFeatureVector,
    KlineBar,
    LiquidationFeedState,
    OpenInterestObservation,
)
from beta.config import (
    PRICE_OI_CONTRACTION_DOWN,
    PRICE_OI_CONTRACTION_UP,
    BetaConfig,
)
from beta.detector import BucketContext, lifecycle, step_episode
from beta.models import NOT_EVALUABLE, NOT_QUALIFIES, QUALIFIES, Episode
from beta.rules import _families_usable, _pct
from beta.state_tape import compute_percentiles, metric_key
from common.stage2_config import Stage2Config

UTC = timezone.utc
BUCKET = timedelta(minutes=5)
VENUES = ("binance", "bybit", "okx")
AUTHORIZED_FAMILIES = (PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP)
PROVENANCE = "RECONSTRUCTED_FROM_SIGNALBOT_LIVE_ARCHIVE"
REPLAY_CLASS = "CURRENT_RULE_SEMANTIC_RECONSTRUCTION"
HISTORICAL_FRESHNESS_STATE = "NOT_IN_ARCHIVE"
HISTORICAL_COHERENCE_STATE = "NOT_IN_ARCHIVE"
HISTORICAL_ALERT_DELIVERY = "NOT_PROVEN"
P4_EPISODE_MINIMUM = 10
P4_DATE_MINIMUM = 5
SEMANTIC_DISCLAIMER = (
    "This is a reconstructed semantic replay of the current PRICE_OI_CONTRACTION "
    "rules on market observations Signalbot collected live. It is not a record of "
    "alerts the production runtime certainly emitted. Historical evaluation freshness, "
    "raw-revision coherence, and alert delivery are not proven."
)

# Frozen Phase A intervals, inclusive. The interior gap is not a replay bucket.
INTERVALS = (
    (
        datetime(2026, 8, 16, 19, 30, tzinfo=UTC),
        datetime(2026, 9, 25, 12, 40, tzinfo=UTC),
    ),
    (
        datetime(2026, 9, 25, 13, 5, tzinfo=UTC),
        datetime(2026, 9, 28, 23, 55, tzinfo=UTC),
    ),
)
GAP_START = datetime(2026, 9, 25, 12, 45, tzinfo=UTC)
GAP_END = datetime(2026, 9, 25, 13, 0, tzinfo=UTC)
# Left edge of the first replay bucket's 30-day percentile window.
HISTORY_START = datetime(2026, 7, 17, 19, 30, tzinfo=UTC)
PHASE_A_AUTHORIZED_BUCKETS = 12434

UNAVAILABLE_FEED = LiquidationFeedState(
    is_available=False, coverage_type="unavailable", is_snapshot_feed=False,
)


@dataclass(frozen=True)
class BucketReconstruction:
    bucket_ts: datetime
    price_median: Optional[float]
    oi_median: Optional[float]
    price_available: int
    oi_available: int
    price_venues: tuple[str, ...]
    oi_venues: tuple[str, ...]
    calculation_version: Optional[str]
    venue_failures: tuple[str, ...]


@dataclass(frozen=True)
class PreparedBucket:
    reconstruction: BucketReconstruction
    price_rank: Optional[float]
    oi_rank: Optional[float]
    price_tier: Optional[str]
    oi_tier: Optional[str]


@dataclass(frozen=True)
class ReplayEpisode:
    episode: Episode
    qualifying_bucket_count: int
    source_interval: str


def authorized_buckets() -> list[datetime]:
    found = []
    for start, end in INTERVALS:
        cursor = start
        while cursor <= end:
            if GAP_START <= cursor <= GAP_END:
                raise RuntimeError(f"authorized grid entered the frozen gap at {iso(cursor)}")
            found.append(cursor)
            cursor += BUCKET
    return found


def history_buckets() -> list[datetime]:
    """Every 5-minute bucket from the percentile left edge through the last replay bucket.

    Gap buckets are included so their reconstructed values can be reported. They
    are not rule-evaluation buckets.
    """
    end = INTERVALS[-1][1]
    cursor = HISTORY_START
    found = []
    while cursor <= end:
        found.append(cursor)
        cursor += BUCKET
    return found


def source_interval(bucket: datetime) -> Optional[str]:
    for index, (start, end) in enumerate(INTERVALS, start=1):
        if start <= bucket <= end:
            return f"interval_{index}"
    return None


def in_frozen_gap(bucket: datetime) -> bool:
    return GAP_START <= bucket <= GAP_END


def floor_5m(value: datetime) -> datetime:
    value = value.astimezone(UTC).replace(second=0, microsecond=0)
    return value - timedelta(minutes=value.minute % 5)


def samples_before(history: Sequence[tuple[datetime, Mapping]], bucket: datetime, *, maturity_days: int):
    """Percentile samples in [B-window, B). The current bucket and the future are absent."""
    start = bucket - timedelta(days=maturity_days)
    return [(ts, metrics) for ts, metrics in history if start <= ts < bucket]


def reconstruct_bucket(
    stage2: Stage2Config,
    bucket: datetime,
    bars_by_venue: Mapping[str, Sequence[KlineBar]],
    oi_by_venue: Mapping[str, Sequence[OpenInterestObservation]],
    *,
    code_version: str,
) -> BucketReconstruction:
    """One bucket through the current exchange-feature and consensus implementations.

    Instrument metadata is not supplied, so volume and taker notionals stay
    unavailable. Liquidation events are not supplied. Funding is not supplied.
    """
    exclusions = {family: {} for family in FAMILIES}
    vectors: list[ExchangeFeatureVector] = []
    failures = []
    for venue in VENUES:
        try:
            vectors.append(_venue_feature(
                stage2, venue, bucket,
                bars_by_venue.get(venue, ()),
                oi_by_venue.get(venue, ()),
                code_version=code_version,
            ))
        except Exception as exc:  # noqa: BLE001 - one venue must not abort the bucket
            failures.append(venue)
            for family in FAMILIES:
                exclusions[family][venue] = EXCHANGE_PROCESSING_FAILED
            _ = type(exc).__name__
            continue
        for family, reason in _derive_family_exclusions(vectors[-1]).items():
            exclusions[family][venue] = reason
    if not vectors:
        return BucketReconstruction(
            bucket, None, None, 0, 0, (), (), None, tuple(failures),
        )
    consensus = compute_consensus_features(build_consensus_feature_request(
        stage2,
        exchange_features=vectors,
        expected_exchanges_by_family={family: VENUES for family in FAMILIES},
        exclusion_reasons_by_family=exclusions,
    ))
    price = consensus.provenance_by_metric["price_structure"]
    oi = consensus.provenance_by_metric["oi"]
    return BucketReconstruction(
        bucket_ts=bucket,
        price_median=consensus.price_move_pct_median,
        oi_median=consensus.oi_change_pct_median,
        price_available=consensus.coverage_by_metric["price_structure"].available,
        oi_available=consensus.coverage_by_metric["oi"].available,
        price_venues=tuple(price.contributing),
        oi_venues=tuple(oi.contributing),
        calculation_version=consensus.calculation_version,
        venue_failures=tuple(failures),
    )


def current_percentiles(
    stage2: Stage2Config,
    cfg: BetaConfig,
    reconstruction: BucketReconstruction,
    history: Sequence[tuple[datetime, Mapping]],
    *,
    code_version: str,
) -> dict:
    """Current percentile core for this reconstruction. History must already exclude B."""
    if reconstruction.calculation_version is None:
        return {}
    for ts, _metrics in history:
        if ts >= reconstruction.bucket_ts:
            raise ValueError("percentile history includes the current bucket or a later bucket")
    ident = {
        "calculation_version": reconstruction.calculation_version,
        "config_hash": stage2.resolve(cfg.symbol).config_hash(),
        "config_version": stage2.config_version,
        "feature_schema_version": stage2.feature_schema_version,
    }
    metrics = {
        metric_key(None, "price_move_pct_median"): reconstruction.price_median,
        metric_key(None, "oi_change_pct_median"): reconstruction.oi_median,
    }
    return compute_percentiles(
        stage2, cfg, bucket_ts=reconstruction.bucket_ts, metrics=metrics, ident=ident,
        code_version=code_version, history=history,
    )


def semantic_rule(cfg: BetaConfig, event_type: str, prepared: PreparedBucket):
    """Current threshold, family, and maturity semantics without runtime gates.

    ``_threshold_rule`` also requires materialized, fresh, and non-stale state.
    Those facts are not in the archive, so this adapter does not set them.
    Family usability and ``_pct`` are the current implementations.
    """
    if event_type not in AUTHORIZED_FAMILIES:
        raise ValueError(f"refusing to evaluate {event_type}")
    rule = cfg.rule(event_type)
    if event_type == PRICE_OI_CONTRACTION_DOWN:
        checks = (
            ("price_move_pct_median", "<=", rule["price_move_pct_median_max"]),
            ("oi_change_pct_median", "<=", rule["oi_change_pct_median_max"]),
        )
    else:
        checks = (
            ("price_move_pct_median", ">=", rule["price_move_pct_median_min"]),
            ("oi_change_pct_median", "<=", rule["oi_change_pct_median_max"]),
        )
    snapshot = _projection(cfg, prepared)
    reason = _families_usable(snapshot, ("price_structure", "oi"))
    if reason:
        return NOT_EVALUABLE, reason, {}
    ranks = {}
    for metric, _op, _threshold in checks:
        rank, why = _pct(snapshot, metric_key(None, metric))
        if why:
            return NOT_EVALUABLE, why, {}
        ranks[metric] = rank
    ok = all((ranks[metric] <= threshold) if op == "<=" else (ranks[metric] >= threshold)
             for metric, op, threshold in checks)
    return (QUALIFIES if ok else NOT_QUALIFIES), ("CONDITION_MET" if ok else "CONDITION_NOT_MET"), {"ranks": ranks}


def replay_series(cfg: BetaConfig, prepared: Sequence[PreparedBucket]) -> dict:
    """Rule rows, episodes, and the P4 sample-availability gate.

    A bucket that is not exactly five minutes after the previous authorized
    bucket resets the streak. ``step_episode`` then terminates an open episode
    with ``DETECTION_GAP``. The frozen 20-minute hole is that break.
    """
    if any(in_frozen_gap(item.reconstruction.bucket_ts) for item in prepared):
        raise ValueError("replay series contains a frozen gap bucket")
    evaluations = []
    episodes: list[ReplayEpisode] = []
    open_eps: dict[str, Optional[Episode]] = {name: None for name in AUTHORIZED_FAMILIES}
    previous_bucket = None
    previous_evals = None
    for item in prepared:
        contiguous = previous_bucket is not None and item.reconstruction.bucket_ts == previous_bucket + BUCKET
        carried = previous_evals if contiguous else None
        current = {}
        version = item.reconstruction.calculation_version or "UNMATERIALIZED"
        for event_type in AUTHORIZED_FAMILIES:
            status, reason, detail = semantic_rule(cfg, event_type, item)
            prev_streak = int(((carried or {}).get(event_type) or {}).get("streak", 0))
            streak = prev_streak + 1 if status == QUALIFIES else 0
            current[event_type] = {
                "status": status, "streak": streak, "reason": reason, "detail": detail,
            }
            ctx = BucketContext(
                bucket_ts=item.reconstruction.bucket_ts,
                decision_ts=item.reconstruction.bucket_ts + BUCKET,
                snapshot_digest=_digest(item, event_type, status, streak),
                calculation_version=version,
                reference={"status": "NOT_A_HISTORICAL_REFERENCE"},
                code_version="semantic-reconstruction",
            )
            step = step_episode(cfg, event_type, open_eps[event_type], current[event_type], ctx)
            if step.terminated is not None:
                episodes.append(_recorded(step.terminated))
                open_eps[event_type] = None
            if step.updated is not None:
                open_eps[event_type] = step.updated
            if step.opened is not None:
                open_eps[event_type] = step.opened
            evaluations.append(_evaluation_row(item, event_type, current[event_type]))
        previous_bucket = item.reconstruction.bucket_ts
        previous_evals = current
    for event_type, episode in open_eps.items():
        if episode is not None:
            episodes.append(_recorded(episode))
            _ = event_type
    _reject_cross_gap(episodes)
    return {
        "evaluations": evaluations,
        "episodes": episodes,
        "gates": {event_type: sample_gate([item for item in episodes if item.episode.event_type == event_type])
                  for event_type in AUTHORIZED_FAMILIES},
        "disclaimer": SEMANTIC_DISCLAIMER,
        "replay_class": REPLAY_CLASS,
        "provenance": PROVENANCE,
        "authorized_bucket_count": len(prepared),
        "non_evaluable_buckets": _non_evaluable_count(evaluations),
        "event_outcomes_computed": False,
        "p4_performance_computed": False,
    }


def sample_gate(episodes: Sequence[ReplayEpisode]) -> dict:
    counts = [item.qualifying_bucket_count for item in episodes]
    dates = sorted({item.episode.opened_bucket.astimezone(UTC).date().isoformat() for item in episodes})
    early = sum(1 for item in episodes if item.episode.armed_at is None and item.episode.triggered_at is None)
    armed = sum(1 for item in episodes if item.episode.armed_at is not None and item.episode.triggered_at is None)
    triggered = sum(1 for item in episodes if item.episode.triggered_at is not None)
    total = len(episodes)
    distinct = len(dates)
    return {
        "total_episodes": total,
        "distinct_episode_dates_utc": distinct,
        "episode_dates_utc": dates,
        "early_only_episodes": early,
        "armed_episodes": armed,
        "triggered_episodes": triggered,
        "median_qualifying_buckets_per_episode": statistics.median(counts) if counts else None,
        "max_qualifying_buckets_per_episode": max(counts) if counts else None,
        "p4_sample_gate": "PASS" if total >= P4_EPISODE_MINIMUM and distinct >= P4_DATE_MINIMUM else "FAIL",
        "gate_meaning": "sample availability only; not profitability, prediction, or a validated edge",
    }


def metrics_of(reconstruction: BucketReconstruction) -> dict:
    return {
        metric_key(None, "price_move_pct_median"): reconstruction.price_median,
        metric_key(None, "oi_change_pct_median"): reconstruction.oi_median,
    }


def iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _venue_feature(stage2, venue, bucket, bars, observations, *, code_version: str) -> ExchangeFeatureVector:
    context = build_assembly_context(
        stage2, exchange=venue, symbol="BTCUSDT", market_type="perp", timeframe="5m",
        bucket_ts=bucket, code_version=code_version, liquidation_feed_available=False,
    )
    return compute_exchange_features(ExchangeFeatureRequest(
        exchange=venue, symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=bucket,
        feature_schema_version=context.feature_schema_version,
        calculation_version=context.calculation_version,
        config_hash=context.config_hash, config_version=context.config_version,
        code_version=code_version,
        bars=tuple(bars), open_interest=tuple(observations), funding=(), liquidations=(),
        liquidation_feed_state=UNAVAILABLE_FEED, instrument_metadata=None,
        allowed_missing_bars=context.allowed_missing_bars,
    ))


def _projection(cfg: BetaConfig, prepared: PreparedBucket) -> dict:
    item = prepared.reconstruction
    def family(available: int) -> dict:
        return {"available": available, "usable": available >= cfg.min_venues}
    return {
        "families": {
            "price_structure": family(item.price_available),
            "oi": family(item.oi_available),
        },
        "percentiles": {
            metric_key(None, "price_move_pct_median"): {
                "value": item.price_median, "rank": prepared.price_rank, "tier": prepared.price_tier,
            },
            metric_key(None, "oi_change_pct_median"): {
                "value": item.oi_median, "rank": prepared.oi_rank, "tier": prepared.oi_tier,
            },
        },
    }


def _evaluation_row(item: PreparedBucket, event_type: str, evaluation: Mapping) -> dict:
    rec = item.reconstruction
    return {
        "bucket_ts": iso(rec.bucket_ts),
        "event_type": event_type,
        "rule_status": evaluation["status"],
        "reason": evaluation["reason"],
        "streak": evaluation["streak"],
        "price_move_pct_median": rec.price_median,
        "oi_change_pct_median": rec.oi_median,
        "price_percentile_rank": item.price_rank,
        "oi_percentile_rank": item.oi_rank,
        "price_maturity": item.price_tier,
        "oi_maturity": item.oi_tier,
        "price_contributing_venues": ",".join(rec.price_venues),
        "oi_contributing_venues": ",".join(rec.oi_venues),
        "source_interval": source_interval(rec.bucket_ts),
        "provenance": PROVENANCE,
        "replay_class": REPLAY_CLASS,
        "historical_freshness_state": HISTORICAL_FRESHNESS_STATE,
        "historical_coherence_race_state": HISTORICAL_COHERENCE_STATE,
        "historical_alert_delivery": HISTORICAL_ALERT_DELIVERY,
    }


def _recorded(episode: Episode) -> ReplayEpisode:
    interval = source_interval(episode.opened_bucket)
    if interval is None:
        raise ValueError("episode opened outside an authorized interval")
    return ReplayEpisode(episode, episode.last_streak, interval)


def _reject_cross_gap(episodes: Sequence[ReplayEpisode]) -> None:
    for item in episodes:
        opened = source_interval(item.episode.opened_bucket)
        last = source_interval(item.episode.last_bucket)
        if opened != last:
            raise ValueError(
                f"episode {item.episode.public_id} crosses the frozen coverage gap"
            )
        if in_frozen_gap(item.episode.opened_bucket) or in_frozen_gap(item.episode.last_bucket):
            raise ValueError(f"episode {item.episode.public_id} touches the frozen coverage gap")


def _non_evaluable_count(rows: Sequence[Mapping]) -> dict:
    counts = {name: 0 for name in AUTHORIZED_FAMILIES}
    for row in rows:
        if row["rule_status"] == NOT_EVALUABLE:
            counts[row["event_type"]] += 1
    return counts


def _digest(item: PreparedBucket, event_type: str, status: str, streak: int) -> str:
    payload = {
        "bucket_ts": iso(item.reconstruction.bucket_ts),
        "event_type": event_type,
        "status": status,
        "streak": streak,
        "replay_class": REPLAY_CLASS,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def entry_streak(cfg: BetaConfig, event_type: str) -> int:
    return lifecycle(cfg, event_type).entry_streak
