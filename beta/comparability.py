"""EVENT_COMPARABILITY_V0 — narrow semantic identity for historical follow-up.

Question it answers: would two detector episode observations have the same
market-state definition AND the same outcome semantics?

It is deliberately NOT `rules_digest`. `rules_digest` covers
`state_schema_version`, so the V1 -> V2 state-tape transition (which only ADDED
keys; see `state_tape.PERCENTILE_HISTORY_SCHEMA_VERSIONS`) changed it although
no event threshold changed. It is also not a bare threshold hash: gating,
streak/duration semantics, Stage-2 feature identity and the outcome version all
change what an episode or its outcome means.

Included (see docs/BETA_HISTORICAL_FOLLOW_UP_V0.md for the per-field reason):
  symbol / market_type / timeframe, event_type, rules_version,
  ONLY the rule-family keys this event type reads, the gates every rule and the
  reference price depend on (active exchanges, min_venue_coverage,
  percentile_window, max_state_age_s), the Stage-2 calculation_version of the
  episode, the detector-feature semantics class of its state-tape schema, and
  outcome_version.
Excluded: rules_digest / config_digest, raw state_schema_version, episodization
and context (presentation projection), push / cooldown / TTL / cap policy,
forward_horizons (a statistic is per horizon), feature_schema_version and the
Stage-2 config hash as separate fields (both are inside calculation_version).

The database stores an episode's rules_digest, not its rule values, so an
episode can only be keyed with the configuration that produced it:
`episode_comparability` verifies that configuration reproduces the stored
rules_digest and fails closed otherwise. Pure; no I/O. Changes no detector,
rule, digest or tape behavior.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from common.versioning import canonical_json

from .config import _PERCENTILE_KEYS
from .config import (BetaConfig, EVENT_TYPES, LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT,
                     POSITION_BUILDUP_COMPRESSION, PRICE_OI_CONTRACTION_DOWN,
                     PRICE_OI_CONTRACTION_UP, TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL)

COMPARABILITY_VERSION = "EVENT_COMPARABILITY_V0"

# Detector-feature semantics per state-tape schema. V2 = V1 plus per-venue raw
# values and kline OHLC; every consensus / liquidation metric and percentile the
# rules read is identical (the tape uses V1 and V2 rows as the same percentile
# history). A schema that changed those semantics must map to a NEW class here;
# an unknown schema fails closed.
DETECTOR_FEATURE_SEMANTICS = MappingProxyType({
    1: "BETA_TAPE_DETECTOR_FEATURES_V1",
    2: "BETA_TAPE_DETECTOR_FEATURES_V1",
})

# event type -> (config rule family, the family keys this event type actually reads)
EVENT_RULE_KEYS = MappingProxyType({
    PRICE_OI_CONTRACTION_DOWN: ("PRICE_OI_CONTRACTION_DOWN", (
        "price_move_pct_median_max", "oi_change_pct_median_max", "armed_at_streak",
        "triggered_at_streak")),
    PRICE_OI_CONTRACTION_UP: ("PRICE_OI_CONTRACTION_UP", (
        "price_move_pct_median_min", "oi_change_pct_median_max", "armed_at_streak",
        "triggered_at_streak")),
    POSITION_BUILDUP_COMPRESSION: ("POSITION_BUILDUP_COMPRESSION", (
        "range_width_pct_median_max", "oi_change_pct_median_min", "volume_notional_usd_sum_min",
        "early_at_streak", "armed_at_streak", "triggered_at_streak", "max_duration_min")),
    TAKER_FLOW_EXTREME_BUY: ("TAKER_FLOW_EXTREME", (
        "enabled", "buy_percentile_min", "armed_at_streak", "triggered_at_streak")),
    TAKER_FLOW_EXTREME_SELL: ("TAKER_FLOW_EXTREME", (
        "enabled", "sell_percentile_max", "armed_at_streak", "triggered_at_streak")),
    LIQUIDATION_STRESS_LONG: ("LIQUIDATION_STRESS", (
        "enabled", "venue_percentile_min", "min_eligible_venues", "triggered_at_streak")),
    LIQUIDATION_STRESS_SHORT: ("LIQUIDATION_STRESS", (
        "enabled", "venue_percentile_min", "min_eligible_venues", "triggered_at_streak")),
})

_CALCULATION_VERSION = re.compile(r"^[0-9a-f]{16}$")


class ComparabilityError(ValueError):
    """Comparability cannot be established (fail closed; never assume it)."""


def _plain(key: str, v: Any) -> Any:
    """Canonical rule value: percentile thresholds are real numbers (1 == 1.0),
    streaks / durations / venue counts are ints, `enabled` is a bool."""
    if key in _PERCENTILE_KEYS:
        return float(v)
    if isinstance(v, (bool, int, str)):
        return v
    raise ComparabilityError(f"unsupported rule value {key}={v!r}")


def comparability_payload(cfg: BetaConfig, *, event_type: str, calculation_version: str,
                          state_schema_version: int) -> dict:
    """Human-readable canonical payload (audit/debug)."""
    if event_type not in EVENT_TYPES or event_type not in EVENT_RULE_KEYS:
        raise ComparabilityError(f"unknown event type {event_type!r}")
    if not isinstance(calculation_version, str) or not _CALCULATION_VERSION.match(calculation_version):
        raise ComparabilityError("calculation_version must be a materialized 16-hex Stage-2 identity")
    if type(state_schema_version) is not int or state_schema_version not in DETECTOR_FEATURE_SEMANTICS:
        raise ComparabilityError(f"unknown detector-feature semantics for state schema {state_schema_version!r}")
    family, keys = EVENT_RULE_KEYS[event_type]
    rule = cfg.rule(family)
    return {
        "comparability_version": COMPARABILITY_VERSION,
        "symbol": cfg.symbol, "market_type": cfg.market_type, "timeframe": cfg.timeframe,
        "event_type": event_type,
        "rules_version": cfg.rules_version,
        "rule_family": family,
        "rule": {k: _plain(k, rule[k]) for k in keys},
        "gates": {"active_exchanges": sorted(cfg.exchanges),
                  "min_venue_coverage": cfg.min_venues,
                  "percentile_window": cfg["percentile_window"],
                  "max_state_age_s": cfg["max_state_age_s"]},
        "features": {"stage2_calculation_version": calculation_version,
                     "detector_feature_semantics": DETECTOR_FEATURE_SEMANTICS[state_schema_version]},
        "outcome_version": cfg.outcome_version,
    }


def payload_digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EventComparability:
    payload: Mapping[str, Any]
    digest: str

    @property
    def event_type(self) -> str:
        return self.payload["event_type"]

    @property
    def outcome_version(self) -> str:
        return self.payload["outcome_version"]

    @property
    def market(self) -> tuple:
        return (self.payload["symbol"], self.payload["market_type"], self.payload["timeframe"])


def event_comparability(cfg: BetaConfig, *, event_type: str, calculation_version: str,
                        state_schema_version: int | None = None) -> EventComparability:
    """Identity under `cfg` (defaults to the configuration's own state schema)."""
    schema = cfg.state_schema_version if state_schema_version is None else state_schema_version
    payload = comparability_payload(cfg, event_type=event_type, calculation_version=calculation_version,
                                    state_schema_version=schema)
    return EventComparability(payload=MappingProxyType(payload), digest=payload_digest(payload))


def episode_comparability(cfg: BetaConfig, *, event_type: str, rules_digest: str,
                          calculation_version: str) -> EventComparability:
    """Identity of a STORED episode. `cfg` must be the configuration that produced
    it: its rules_digest must equal the episode's (fail closed otherwise)."""
    if cfg.rules_digest != rules_digest:
        raise ComparabilityError("the supplied configuration does not reproduce the episode's rules_digest")
    return event_comparability(cfg, event_type=event_type, calculation_version=calculation_version)
