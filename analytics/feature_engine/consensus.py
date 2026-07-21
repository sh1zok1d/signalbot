"""
Stage 2.1 Level B consensus computation — a pure, deterministic core.

`compute_consensus_features(request) -> ConsensusFeatureVector` aggregates the
already-computed per-exchange `ExchangeFeatureVector`s of one bucket into one
cross-exchange consensus vector, exactly per Consensus Contract Revision 0.2.3
(docs/STAGE2_SPEC.md §11).

No DB, no network, no asyncio, no clock/env/subprocess, no global mutable state,
and NO internal rounding. Same input -> same output; input order does not matter
(the explicit per-family expected sets drive everything; nothing is recomputed
from the live registry except structural liquidation feed quality, which §11.6
makes the registry the authority for).
"""
from __future__ import annotations

import math
import re
from datetime import datetime
from types import MappingProxyType
from typing import Optional, Sequence

from symbols.registry import ACTIVE_EXCHANGES, active_symbols, family_capability

from .models import ExchangeFeatureVector, TIMEFRAME_MINUTES
from .consensus_models import (
    APPLICABLE_COMPONENTS, CONFIDENCE_WEIGHT_KEYS, ConsensusError,
    ConsensusFeatureRequest, ConsensusFeatureVector, CoverageEntry, FAMILIES,
    OUTLIER_REASON_MAD_ZERO, OUTLIER_REASON_THRESHOLD, OutlierEntry,
    ProvenanceEntry, ROBUST_Z_SCALE,
)

_HEX16 = re.compile(r"^[0-9a-f]{16}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_WEIGHT_SUM_TOL = 1e-9

# Required non-NULL EFV fields for a venue to contribute to each family (§11.
# contribution rules). All are validated (finite; counts as ints) when a venue
# contributes. Structurally immutable — shared read-only lookup, never mutable
# module state.
_REQUIRED_FIELDS: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "price_structure": ("price_move_pct", "range_width_pct", "close_price"),
    "volume":          ("volume_notional_usd",),
    "taker_flow":      ("taker_buy_notional_usd", "taker_sell_notional_usd",
                        "taker_delta_notional_usd", "cvd_delta_notional_usd"),
    "oi":              ("oi_change_pct",),
    "funding":         ("funding_rate",),
    "liquidations":    ("long_liquidation_notional", "short_liquidation_notional",
                        "liquidation_event_count"),
})
# EFV fields that are integer counts (validated as ints, never coerced).
_COUNT_FIELDS = frozenset({"liquidation_event_count"})
# is_usable gates contribution ONLY for the bar-derived families (§11.7).
_USABLE_GATED = frozenset({"price_structure", "volume", "taker_flow"})

# Outlier metrics -> (family that owns them, EFV field) (§11.5). Immutable.
_OUTLIER_METRICS: Mapping[str, tuple[str, str]] = MappingProxyType({
    "price_move_pct": ("price_structure", "price_move_pct"),
    "oi_change_pct":  ("oi", "oi_change_pct"),
    "funding_rate":   ("funding", "funding_rate"),
})


# ---- small validators ------------------------------------------------------
def _tz_aware(dt, name: str) -> datetime:
    if not isinstance(dt, datetime):
        raise ConsensusError(f"{name} must be a datetime, got {type(dt).__name__}")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ConsensusError(f"{name} must be timezone-aware")
    return dt


def _finite(value, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConsensusError(f"{name} must be a number, got {type(value).__name__}")
    v = float(value)
    if not math.isfinite(v):
        raise ConsensusError(f"{name} must be finite, got {value!r}")
    return v


def _nonblank(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConsensusError(f"{name} must be a non-empty string")
    return value


def _require_count(value, name: str) -> int:
    """A real non-negative integer event count — never a bool, float, or coerced
    value (no silent int(...))."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConsensusError(f"{name} must be an int, got {type(value).__name__}")
    if value < 0:
        raise ConsensusError(f"{name} must be >= 0, got {value!r}")
    return value


# ---- pure math (no rounding) -----------------------------------------------
def _median(values: Sequence[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


def _mad(values: Sequence[float], med: float) -> float:
    return _median([abs(v - med) for v in values])


def _dispersion_score(values: Sequence[float]) -> float:
    med = _median(values)
    mad = _mad(values, med)
    if mad == 0:
        return 1.0
    if med == 0:
        return 0.0
    return 1.0 / (1.0 + mad / abs(med))


def _direction_agreement(values: Sequence[float]) -> float:
    neg = sum(1 for v in values if v < 0)
    pos = sum(1 for v in values if v > 0)
    flat = sum(1 for v in values if v == 0)
    return max(neg, flat, pos) / len(values)


# ---- request validation ----------------------------------------------------
def _validate_weights(req: ConsensusFeatureRequest) -> None:
    w = req.confidence_weights
    if set(w) != set(CONFIDENCE_WEIGHT_KEYS):
        raise ConsensusError(
            f"confidence_weights must have exactly {list(CONFIDENCE_WEIGHT_KEYS)}, "
            f"got {sorted(w)}")
    vals = {k: _finite(w[k], f"confidence_weights.{k}") for k in CONFIDENCE_WEIGHT_KEYS}
    for k, v in vals.items():
        if v < 0:
            raise ConsensusError(f"confidence_weights.{k} must be >= 0, got {v!r}")
    if vals["coverage"] <= 0:
        raise ConsensusError("confidence_weights.coverage must be > 0")
    total = math.fsum(vals.values())
    if abs(total - 1.0) > _WEIGHT_SUM_TOL:
        raise ConsensusError(f"confidence_weights must sum to 1.0, got {total!r}")


def _validate_identity(req: ConsensusFeatureRequest) -> None:
    active = {s.symbol: s for s in active_symbols()}
    sym_def = active.get(req.symbol) if isinstance(req.symbol, str) else None
    if sym_def is None:
        raise ConsensusError(f"unknown/inactive symbol {req.symbol!r} "
                             f"(active: {sorted(active)})")
    if req.market_type not in sym_def.market_types:
        raise ConsensusError(f"unsupported market_type {req.market_type!r} for "
                             f"{req.symbol} (supported: {list(sym_def.market_types)})")
    if req.timeframe not in TIMEFRAME_MINUTES:
        raise ConsensusError(f"unsupported timeframe {req.timeframe!r}")
    _tz_aware(req.bucket_ts, "bucket_ts")
    if not isinstance(req.feature_schema_version, int) or isinstance(req.feature_schema_version, bool) \
            or req.feature_schema_version <= 0:
        raise ConsensusError("feature_schema_version must be an int > 0")
    if not isinstance(req.calculation_version, str) or not _HEX16.match(req.calculation_version):
        raise ConsensusError("calculation_version must be 16 lowercase hex chars")
    if not isinstance(req.config_hash, str) or not _HEX64.match(req.config_hash):
        raise ConsensusError("config_hash must be 64 lowercase hex chars")
    _nonblank(req.config_version, "config_version")
    _nonblank(req.code_version, "code_version")
    if not isinstance(req.minimum_exchange_coverage, int) or isinstance(req.minimum_exchange_coverage, bool) \
            or req.minimum_exchange_coverage < 1:
        raise ConsensusError("minimum_exchange_coverage must be an int >= 1")
    if isinstance(req.robust_z_threshold, bool) or not isinstance(req.robust_z_threshold, (int, float)):
        raise ConsensusError("robust_z_threshold must be a number")
    if not math.isfinite(float(req.robust_z_threshold)) or req.robust_z_threshold <= 0:
        raise ConsensusError("robust_z_threshold must be finite and > 0")
    _validate_weights(req)


def _validate_expected_and_exclusions(req: ConsensusFeatureRequest) -> None:
    exp = req.expected_exchanges_by_family
    if set(exp) != set(FAMILIES):
        raise ConsensusError(
            f"expected_exchanges_by_family must have exactly the six families "
            f"{list(FAMILIES)}, got {sorted(exp)}")
    for family in FAMILIES:
        members = exp[family]
        if len(members) == 0:
            raise ConsensusError(f"expected set for {family!r} is empty")
        if len(set(members)) != len(members):
            raise ConsensusError(f"expected set for {family!r} has duplicates: {list(members)}")
        for ex in members:
            if ex not in ACTIVE_EXCHANGES:
                raise ConsensusError(
                    f"{family}: expected exchange {ex!r} is not an active canonical "
                    f"exchange {list(ACTIVE_EXCHANGES)}")
    # exclusion reasons: known families only; each excluded exchange must be
    # expected for that family; each reason a non-empty string (never guessed).
    for family, reasons in req.exclusion_reasons_by_family.items():
        if family not in FAMILIES:
            raise ConsensusError(f"exclusion_reasons_by_family has unknown family {family!r}")
        expected_set = set(exp[family])
        for ex, reason in reasons.items():
            if ex not in expected_set:
                raise ConsensusError(
                    f"{family}: excluded exchange {ex!r} is not in that family's expected set")
            _nonblank(reason, f"exclusion_reasons_by_family[{family}][{ex}]")


def _validate_exchange_features(req: ConsensusFeatureRequest) -> dict[str, ExchangeFeatureVector]:
    efv_by_ex: dict[str, ExchangeFeatureVector] = {}
    expected_union: set[str] = set()
    for members in req.expected_exchanges_by_family.values():
        expected_union.update(members)
    ident_fields = ("symbol", "market_type", "timeframe", "bucket_ts",
                    "feature_schema_version", "calculation_version",
                    "config_hash", "config_version", "code_version")
    for efv in req.exchange_features:
        ex = efv.exchange
        if ex not in ACTIVE_EXCHANGES:
            raise ConsensusError(f"EFV exchange {ex!r} is not active/canonical")
        if ex in efv_by_ex:
            raise ConsensusError(f"duplicate EFV for exchange {ex!r}")
        if ex not in expected_union:
            raise ConsensusError(f"unexpected EFV exchange {ex!r} (not in any family's expected set)")
        mism = [f for f in ident_fields if getattr(efv, f) != getattr(req, f)]
        if mism:
            raise ConsensusError(
                f"EFV for {ex!r} identity mismatch on {mism} vs request")
        efv_by_ex[ex] = efv
    return efv_by_ex


# ---- contribution ----------------------------------------------------------
def _contributes(family: str, efv: ExchangeFeatureVector) -> bool:
    if family in _USABLE_GATED and not efv.is_usable:
        return False
    return all(getattr(efv, f) is not None for f in _REQUIRED_FIELDS[family])


def _validate_contributor_values(family: str, efv: ExchangeFeatureVector) -> None:
    """Every required field of a contributor is a real value: numeric fields
    finite, count fields non-negative ints. Runs for all contributors (even below
    minimum), so a bad value always fails loudly."""
    for f in _REQUIRED_FIELDS[family]:
        if f in _COUNT_FIELDS:
            _require_count(getattr(efv, f), f"{efv.exchange}.{f}")
        else:
            _finite(getattr(efv, f), f"{efv.exchange}.{f}")


# ---- entry point -----------------------------------------------------------
def compute_consensus_features(req: ConsensusFeatureRequest) -> ConsensusFeatureVector:
    _validate_identity(req)
    _validate_expected_and_exclusions(req)
    efv_by_ex = _validate_exchange_features(req)

    minimum = req.minimum_exchange_coverage
    coverage: dict[str, CoverageEntry] = {}
    provenance: dict[str, ProvenanceEntry] = {}
    contributors: dict[str, list[ExchangeFeatureVector]] = {}

    # 1) Resolve contributing vs excluded per family; build coverage/provenance.
    for family in FAMILIES:
        expected = req.expected_exchanges_by_family[family]
        excl = dict(req.exclusion_reasons_by_family.get(family, {}))
        contributing: list[ExchangeFeatureVector] = []
        for ex in expected:
            if ex in excl:
                continue  # excluded wins even if an EFV with numbers exists (§ item 10)
            efv = efv_by_ex.get(ex)
            if efv is None:
                raise ConsensusError(
                    f"{family}: expected exchange {ex!r} has neither an EFV nor an "
                    f"exclusion reason")
            if not _contributes(family, efv):
                raise ConsensusError(
                    f"{family}: expected exchange {ex!r} is neither excluded nor a valid "
                    f"contributor (missing required value or is_usable gate)")
            _validate_contributor_values(family, efv)
            contributing.append(efv)
        contributors[family] = contributing
        available = len(contributing)
        expected_n = len(expected)
        coverage[family] = CoverageEntry(available, expected_n, available / expected_n)
        provenance[family] = ProvenanceEntry(
            contributing=tuple(sorted(e.exchange for e in contributing)),
            excluded=tuple(sorted((ex, excl[ex]) for ex in excl)),
        )

    def _vals(family: str, field: str) -> list[float]:
        return [_finite(getattr(e, field), f"{e.exchange}.{field}")
                for e in contributors[family]]

    def _ok(family: str) -> bool:
        return coverage[family].available >= minimum

    # 2) Per-family aggregates (NULL below minimum). Also cache med/mad/dispersion
    #    and direction agreement for confidence + outliers.
    agg: dict[str, Optional[float]] = {}
    agreement: dict[str, Optional[float]] = {}
    dispersion: dict[str, Optional[float]] = {}

    # price_structure
    if _ok("price_structure"):
        pm = _vals("price_structure", "price_move_pct")
        rw = _vals("price_structure", "range_width_pct")
        pm_med = _median(pm)
        agg["price_move_pct_median"] = pm_med
        agg["range_width_pct_median"] = _median(rw)
        agg["price_move_pct_mad"] = _mad(pm, pm_med)
        agreement["price_structure"] = _direction_agreement(pm)
        dispersion["price_structure"] = _dispersion_score(pm)
    # volume
    if _ok("volume"):
        agg["volume_notional_usd_sum"] = math.fsum(_vals("volume", "volume_notional_usd"))
    # taker_flow
    if _ok("taker_flow"):
        td = _vals("taker_flow", "taker_delta_notional_usd")
        agg["taker_buy_notional_usd_sum"] = math.fsum(_vals("taker_flow", "taker_buy_notional_usd"))
        agg["taker_sell_notional_usd_sum"] = math.fsum(_vals("taker_flow", "taker_sell_notional_usd"))
        agg["taker_delta_notional_usd_sum"] = math.fsum(td)
        agg["cvd_delta_notional_usd_sum"] = math.fsum(_vals("taker_flow", "cvd_delta_notional_usd"))
        agreement["taker_flow"] = _direction_agreement(td)
        dispersion["taker_flow"] = _dispersion_score(td)
    # oi
    if _ok("oi"):
        oi = _vals("oi", "oi_change_pct")
        oi_med = _median(oi)
        agg["oi_change_pct_median"] = oi_med
        agg["oi_change_pct_mad"] = _mad(oi, oi_med)
        agreement["oi"] = _direction_agreement(oi)
        dispersion["oi"] = _dispersion_score(oi)
    # funding
    if _ok("funding"):
        fr = _vals("funding", "funding_rate")
        fr_med = _median(fr)
        agg["funding_rate_median"] = fr_med
        agg["funding_rate_mad"] = _mad(fr, fr_med)
        dispersion["funding"] = _dispersion_score(fr)
    # liquidations (event count kept as int)
    if _ok("liquidations"):
        agg["observed_long_liquidation_notional_sum"] = math.fsum(
            _vals("liquidations", "long_liquidation_notional"))
        agg["observed_short_liquidation_notional_sum"] = math.fsum(
            _vals("liquidations", "short_liquidation_notional"))
        # Values are already validated as non-negative ints — sum directly, no
        # coercion. sum() of ints stays an int.
        agg["observed_liquidation_event_count_sum"] = sum(
            e.liquidation_event_count for e in contributors["liquidations"])

    # 3) Data Confidence per family.
    def _family_confidence(family: str) -> float:
        ratio = coverage[family].ratio
        if coverage[family].available < minimum:
            return ratio * 100.0
        applicable = APPLICABLE_COMPONENTS[family]
        comp = {"coverage": ratio}
        if "agreement" in applicable:
            comp["agreement"] = agreement[family]
        if "dispersion" in applicable:
            comp["dispersion"] = dispersion[family]
        wsum = math.fsum(req.confidence_weights[c] for c in applicable)
        num = math.fsum(req.confidence_weights[c] * comp[c] for c in applicable)
        return 100.0 * num / wsum

    confidence = {family: _family_confidence(family) for family in FAMILIES}
    family_scores = [confidence[family] for family in FAMILIES]
    data_confidence_overall = math.fsum(family_scores) / len(FAMILIES)
    consensus_confidence = min(family_scores)
    min_coverage_ratio = min(coverage[family].ratio for family in FAMILIES)
    exchanges_expected_max = max(coverage[family].expected for family in FAMILIES)
    is_partial = any(coverage[family].available < coverage[family].expected
                     for family in FAMILIES)

    # 4) Outliers (only for families that reached the minimum). Metric-first.
    outliers: dict[str, MappingProxyType] = {}
    for metric, (family, field) in _OUTLIER_METRICS.items():
        if not _ok(family):
            continue
        by_ex = {e.exchange: _finite(getattr(e, field), f"{e.exchange}.{field}")
                 for e in contributors[family]}
        med = _median(list(by_ex.values()))
        mad = _mad(list(by_ex.values()), med)
        entries: dict[str, OutlierEntry] = {}
        for ex in sorted(by_ex):
            v = by_ex[ex]
            if mad > 0:
                rz = ROBUST_Z_SCALE * (v - med) / mad
                if abs(rz) > req.robust_z_threshold:
                    entries[ex] = OutlierEntry(rz, OUTLIER_REASON_THRESHOLD)
            elif v != med:  # mad == 0
                entries[ex] = OutlierEntry(None, OUTLIER_REASON_MAD_ZERO)
        if entries:
            outliers[metric] = MappingProxyType(entries)
    outlier_exchanges = MappingProxyType({m: outliers[m] for m in sorted(outliers)})

    # 5) Liquidation feed quality — ALL expected liquidation exchanges, from the
    #    registry (§11.6); contributing venues must match their EFV or fail.
    liq_expected = req.expected_exchanges_by_family["liquidations"]
    liq_contrib = {e.exchange: e for e in contributors["liquidations"]}
    quality: dict[str, str] = {}
    for ex in sorted(liq_expected):
        cap = family_capability(req.symbol, "liquidations", ex).coverage_type
        efv = liq_contrib.get(ex)
        if efv is not None and efv.liquidation_feed_quality != cap:
            raise ConsensusError(
                f"liquidation feed quality mismatch for {ex!r}: EFV "
                f"{efv.liquidation_feed_quality!r} vs registry {cap!r}")
        quality[ex] = cap
    liquidation_feed_quality_by_exchange = MappingProxyType(quality)

    # 6) Assemble (family-ordered maps; deeply immutable).
    coverage_map = MappingProxyType({f: coverage[f] for f in FAMILIES})
    provenance_map = MappingProxyType({f: provenance[f] for f in FAMILIES})
    confidence_map = MappingProxyType({f: confidence[f] for f in FAMILIES})

    return ConsensusFeatureVector(
        symbol=req.symbol, market_type=req.market_type, timeframe=req.timeframe,
        bucket_ts=req.bucket_ts, feature_schema_version=req.feature_schema_version,
        calculation_version=req.calculation_version,
        coverage_by_metric=coverage_map,
        provenance_by_metric=provenance_map,
        data_confidence_by_metric=confidence_map,
        exchanges_expected_max=exchanges_expected_max,
        min_coverage_ratio=min_coverage_ratio,
        data_confidence_overall=data_confidence_overall,
        price_direction_agreement=agreement.get("price_structure"),
        flow_direction_agreement=agreement.get("taker_flow"),
        oi_direction_agreement=agreement.get("oi"),
        price_move_pct_median=agg.get("price_move_pct_median"),
        range_width_pct_median=agg.get("range_width_pct_median"),
        oi_change_pct_median=agg.get("oi_change_pct_median"),
        funding_rate_median=agg.get("funding_rate_median"),
        funding_rate_mad=agg.get("funding_rate_mad"),
        volume_notional_usd_sum=agg.get("volume_notional_usd_sum"),
        taker_buy_notional_usd_sum=agg.get("taker_buy_notional_usd_sum"),
        taker_sell_notional_usd_sum=agg.get("taker_sell_notional_usd_sum"),
        taker_delta_notional_usd_sum=agg.get("taker_delta_notional_usd_sum"),
        cvd_delta_notional_usd_sum=agg.get("cvd_delta_notional_usd_sum"),
        observed_long_liquidation_notional_sum=agg.get("observed_long_liquidation_notional_sum"),
        observed_short_liquidation_notional_sum=agg.get("observed_short_liquidation_notional_sum"),
        observed_liquidation_event_count_sum=agg.get("observed_liquidation_event_count_sum"),
        liquidation_feed_quality_by_exchange=liquidation_feed_quality_by_exchange,
        price_move_pct_mad=agg.get("price_move_pct_mad"),
        oi_change_pct_mad=agg.get("oi_change_pct_mad"),
        outlier_exchanges=outlier_exchanges,
        consensus_confidence=consensus_confidence,
        is_partial_consensus=is_partial,
        config_hash=req.config_hash, config_version=req.config_version,
        code_version=req.code_version,
    )
