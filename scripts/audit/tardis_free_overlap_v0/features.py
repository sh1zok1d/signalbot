"""Build per-venue and consensus features by calling the production cores.

analytics.feature_engine.exchange_features.compute_exchange_features and
analytics.feature_engine.consensus.compute_consensus_features own the formulas.
This module only shapes rows and records diagnostics those functions do not
return (observation counts, endpoint timestamps). The OI percentage attached
to a diagnostic is the value returned by the production function.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

from analytics.feature_engine.bucket_coordinator import _derive_family_exclusions
from analytics.feature_engine.consensus import compute_consensus_features
from analytics.feature_engine.consensus_models import (
    ConsensusFeatureRequest,
    FAMILIES,
)
from analytics.feature_engine.exchange_features import (
    FeatureError,
    _oi_feature,
    compute_exchange_features,
)
from analytics.feature_engine.input_adapter import _allowed_missing_bars
from analytics.feature_engine.models import (
    ExchangeFeatureRequest,
    ExchangeFeatureVector,
    KlineBar,
    LiquidationFeedState,
    OpenInterestObservation,
)
from common.instrument_metadata import InstrumentMetadata
from common.stage2_config import Stage2Config
from common.versioning import compute_calculation_version
from symbols.registry import family_capability

from .constants import (
    CANONICAL_SYMBOL,
    MARKET_TYPE,
    TIMEFRAME,
    VENUE_BY_SIGNALBOT,
    VenueMap,
)
from .parsing import MinuteBar, OpenInterestRow, bucket_bounds, exchange_us_to_datetime

# Liquidations and funding are out of scope for this overlap. The feed is
# marked unavailable so production returns NULL rather than a measured zero.
_LIQUIDATION_UNAVAILABLE = LiquidationFeedState(
    is_available=False,
    coverage_type="unavailable",
    is_snapshot_feed=False,
)


def production_identity(stage2: Stage2Config | None = None) -> dict:
    cfg = stage2 or Stage2Config.load()
    resolved = cfg.resolve(CANONICAL_SYMBOL)
    data = resolved.as_dict()
    confidence = data["data_confidence"]
    return {
        "config_version": cfg["stage2"]["config_version"],
        "feature_schema_version": cfg["stage2"]["feature_schema_version"],
        "config_hash": resolved.config_hash(),
        "calculation_version": compute_calculation_version(
            cfg["stage2"]["feature_schema_version"],
            resolved.config_hash(),
            code_version="tardis-free-overlap-v0",
        ),
        "code_version": "tardis-free-overlap-v0",
        "minimum_metric_coverage": confidence["minimum_metric_coverage"],
        "minimum_exchange_coverage": confidence["minimum_exchange_coverage"],
        "confidence_weights": dict(confidence["weights"]),
        "robust_z_threshold": data["outliers"]["robust_z_threshold"],
        "allowed_missing_bars_5m": _allowed_missing_bars(
            TIMEFRAME, confidence["minimum_metric_coverage"]
        ),
        "instrument_metadata_revision": data["instrument_metadata_revision"],
    }


def structural_metadata(venue: VenueMap, *, contract_multiplier: float | None,
                        metadata_source: str, note: str) -> InstrumentMetadata:
    return InstrumentMetadata(
        exchange=venue.signalbot_exchange,
        symbol=CANONICAL_SYMBOL,
        market_type=MARKET_TYPE,
        exchange_instrument_id=venue.tardis_symbol,
        quantity_unit=venue.quantity_unit,
        contract_multiplier=contract_multiplier,
        tick_size=None,
        price_precision=None,
        quantity_precision=None,
        metadata_source=metadata_source,
        fetched_at=None,
        is_stale=False,
        note=note,
    )


def minute_bar_to_kline(bar: MinuteBar) -> KlineBar:
    if bar.taker_split_complete:
        buy: float | None = bar.taker_buy_volume
        sell: float | None = bar.taker_sell_volume
    else:
        buy = sell = None
    return KlineBar(
        ts=bar.minute_start,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
        taker_buy_volume=buy,
        taker_sell_volume=sell,
    )


def oi_rows_to_observations(rows: Sequence[OpenInterestRow], venue: VenueMap,
                            ) -> list[OpenInterestObservation]:
    """Keep rows that actually carry an open-interest value.

    Empty Tardis open_interest cells are omitted. They are not zeros.
    The unit is the production unit for that venue (base for Binance and
    Bybit, contracts for OKX). Tardis does not publish a unit column; the
    manifest records this as an assumption, and a gold unit disagreement
    fails the bucket closed.
    """
    out: list[OpenInterestObservation] = []
    for row in rows:
        if row.open_interest is None:
            continue
        out.append(OpenInterestObservation(
            ts=exchange_us_to_datetime(row.exchange_timestamp_us),
            oi_raw=row.open_interest,
            oi_unit=venue.oi_unit,
        ))
    return out


def _request(identity: dict, exchange: str, bucket_ts: datetime,
             bars: Sequence[KlineBar],
             oi: Sequence[OpenInterestObservation],
             metadata: InstrumentMetadata | None) -> ExchangeFeatureRequest:
    return ExchangeFeatureRequest(
        exchange=exchange,
        symbol=CANONICAL_SYMBOL,
        market_type=MARKET_TYPE,
        timeframe=TIMEFRAME,
        bucket_ts=bucket_ts,
        feature_schema_version=identity["feature_schema_version"],
        calculation_version=identity["calculation_version"],
        config_hash=identity["config_hash"],
        config_version=identity["config_version"],
        code_version=identity["code_version"],
        bars=bars,
        open_interest=oi,
        funding=(),
        liquidations=(),
        liquidation_feed_state=_LIQUIDATION_UNAVAILABLE,
        instrument_metadata=metadata,
        allowed_missing_bars=identity["allowed_missing_bars_5m"],
    )


def _oi_probe(bucket_ts: datetime,
              observations: Sequence[OpenInterestObservation]) -> ExchangeFeatureRequest:
    """A request whose only job is to let _oi_feature see the window."""
    return _request(
        {
            "feature_schema_version": 1,
            "calculation_version": "0123456789abcdef",
            "config_hash": "a" * 64,
            "config_version": "probe",
            "code_version": "probe",
            "allowed_missing_bars_5m": 5,
        },
        "binance",
        bucket_ts,
        bars=(),
        oi=observations,
        metadata=None,
    )


def oi_endpoint_facts(observations: Sequence[OpenInterestObservation],
                      bucket_ts: datetime) -> dict:
    """Window membership and endpoints. The percentage comes from _oi_feature.

    Identical (oi_raw, oi_unit) rows at one timestamp collapse the same way
    the production function collapses them. A conflicting value raises
    FeatureError (the production error) and the caller records the bucket
    as not evaluable.
    """
    _, bucket_end = bucket_bounds(bucket_ts)
    in_window = [o for o in observations if bucket_ts <= o.ts < bucket_end]
    by_ts: dict[datetime, tuple[float, str]] = {}
    for obs in in_window:
        key = (float(obs.oi_raw), obs.oi_unit)
        prev = by_ts.get(obs.ts)
        if prev is None:
            by_ts[obs.ts] = key
        elif prev != key:
            _oi_feature(_oi_probe(bucket_ts, observations), bucket_end)
            raise FeatureError(
                f"conflicting open interest at {obs.ts.isoformat()}"
            )
    pct, unit = _oi_feature(_oi_probe(bucket_ts, observations), bucket_end)
    ordered = sorted(by_ts)
    return {
        "observation_count": len(by_ts),
        "raw_row_count_in_window": len(in_window),
        "first_timestamp": ordered[0].isoformat() if ordered else None,
        "last_timestamp": ordered[-1].isoformat() if ordered else None,
        "first_oi": by_ts[ordered[0]][0] if ordered else None,
        "last_oi": by_ts[ordered[-1]][0] if ordered else None,
        "unit": unit,
        "units_seen": sorted({u for _, u in by_ts.values()}),
        "oi_change_pct": pct,
        "conflict": False,
        "right_edge_excluded": bucket_end.isoformat(),
    }


def compute_bucket_features(
    *,
    identity: dict,
    exchange: str,
    bucket_ts: datetime,
    bars: Sequence[KlineBar],
    oi: Sequence[OpenInterestObservation],
    metadata: InstrumentMetadata | None,
) -> tuple[ExchangeFeatureVector, dict]:
    """One production feature vector plus OI diagnostics.

    A conflicting OI timestamp fails that OI series closed (no percentage)
    and is omitted from the feature request so the price and taker vectors
    still compute. The conflict is recorded on the diagnostic.
    """
    _, bucket_end = bucket_bounds(bucket_ts)
    future_bars = [b.ts for b in bars if b.ts >= bucket_end]
    if future_bars:
        raise FeatureError(
            f"future bar {future_bars[0].isoformat()} in bucket {bucket_ts.isoformat()}"
        )
    diagnostic: dict = {
        "oi_status": "not_evaluable",
        "oi_reason": None,
    }
    oi_for_request: Sequence[OpenInterestObservation] = oi
    try:
        facts = oi_endpoint_facts(oi, bucket_ts)
    except FeatureError as exc:
        facts = {
            "observation_count": None,
            "oi_change_pct": None,
            "conflict": True,
            "error": str(exc),
        }
        oi_for_request = ()
        diagnostic["oi_reason"] = (
            "CONFLICTING_OI" if "conflicting" in str(exc) else "OI_FEATURE_ERROR"
        )
    else:
        if facts["conflict"]:
            oi_for_request = ()
            diagnostic["oi_reason"] = "CONFLICTING_OI"
        elif facts["observation_count"] < 2:
            diagnostic["oi_reason"] = "FEWER_THAN_TWO_DISTINCT_TIMESTAMPS"
        elif len(facts["units_seen"]) != 1:
            diagnostic["oi_reason"] = "UNIT_MISMATCH_WITHIN_BUCKET"
        elif facts["oi_change_pct"] is None:
            diagnostic["oi_reason"] = "OI_CHANGE_UNDEFINED"
        else:
            diagnostic["oi_status"] = "evaluable"
            diagnostic["oi_reason"] = None
    diagnostic["oi"] = facts
    vector = compute_exchange_features(_request(
        identity, exchange, bucket_ts, bars, oi_for_request, metadata,
    ))
    if diagnostic["oi_reason"] == "CONFLICTING_OI":
        # Production would have raised if the conflicting rows were passed in.
        # The omitted series must stay NULL.
        if vector.oi_change_pct is not None:
            raise RuntimeError("conflicting OI produced a percentage")
    return vector, diagnostic


def consensus_for_vectors(identity: dict, bucket_ts: datetime,
                          vectors: Sequence[ExchangeFeatureVector]):
    """Same exclusion rules as bucket_coordinator._derive_family_exclusions.

    Funding and liquidations are expected to be excluded: this experiment
    does not feed those families, and NULL is not rewritten to zero.
    """
    expected = {family: tuple(v.exchange for v in vectors) for family in FAMILIES}
    # Stable venue order: binance, bybit, okx as in the registry tuple,
    # restricted to vectors we actually have.
    order = [ex for ex in ("binance", "bybit", "okx") if any(v.exchange == ex for v in vectors)]
    expected = {family: tuple(order) for family in FAMILIES}
    exclusions: dict[str, dict[str, str]] = {family: {} for family in FAMILIES}
    for vector in vectors:
        for family, reason in _derive_family_exclusions(vector).items():
            exclusions[family][vector.exchange] = reason
    request = ConsensusFeatureRequest(
        symbol=CANONICAL_SYMBOL,
        market_type=MARKET_TYPE,
        timeframe=TIMEFRAME,
        bucket_ts=bucket_ts,
        feature_schema_version=identity["feature_schema_version"],
        calculation_version=identity["calculation_version"],
        config_hash=identity["config_hash"],
        config_version=identity["config_version"],
        code_version=identity["code_version"],
        exchange_features=tuple(vectors),
        expected_exchanges_by_family=expected,
        exclusion_reasons_by_family=exclusions,
        minimum_exchange_coverage=identity["minimum_exchange_coverage"],
        confidence_weights=identity["confidence_weights"],
        robust_z_threshold=identity["robust_z_threshold"],
    )
    # Touch the registry the same way consensus does, so a quality mismatch
    # on a contributing liquidation venue still fails closed. With the
    # unavailable feed, liquidations are excluded and this is a no-op check
    # that the import stays live.
    for ex in order:
        family_capability(CANONICAL_SYMBOL, "liquidations", ex)
    return compute_consensus_features(request), exclusions


def vector_public_dict(vector: ExchangeFeatureVector, *, source: str,
                       instrument: str, sample_date: str,
                       source_file_sha256: str | None,
                       exchange_timestamp_role: str) -> dict:
    return {
        "source": source,
        "exchange": vector.exchange,
        "instrument": instrument,
        "sample_date": sample_date,
        "source_file_sha256": source_file_sha256,
        "bucket_ts": vector.bucket_ts.isoformat(),
        "price_move_pct": vector.price_move_pct,
        "range_width_pct": vector.range_width_pct,
        "volume_raw": vector.volume_raw,
        "volume_raw_unit": vector.volume_raw_unit,
        "volume_notional_usd": vector.volume_notional_usd,
        "taker_buy_notional_usd": vector.taker_buy_notional_usd,
        "taker_sell_notional_usd": vector.taker_sell_notional_usd,
        "taker_delta_notional_usd": vector.taker_delta_notional_usd,
        "oi_change_pct": vector.oi_change_pct,
        "oi_unit": vector.oi_unit,
        "bars_expected": vector.bars_expected,
        "bars_present": vector.bars_present,
        "has_gap": vector.has_gap,
        "is_usable": vector.is_usable,
        "exchange_timestamp_role": exchange_timestamp_role,
        "called_live_observed": False,
    }


def day_start(sample_date: str) -> datetime:
    year, month, day = (int(p) for p in sample_date.split("-"))
    return datetime(year, month, day, tzinfo=timezone.utc)


def iter_day_buckets(sample_date: str):
    start = day_start(sample_date)
    end = start + timedelta(days=1)
    cursor = start
    while cursor < end:
        yield cursor
        cursor += timedelta(minutes=5)
