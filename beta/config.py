"""Beta V0.2 configuration: strict loading, validation, digests and hard switches.

Every threshold / persistence duration / TTL / cooldown / cap comes from
config/beta_v0.yaml. Validation is strict (exact key sets, typed values) so a
typo can never silently fall back to a default. Secrets are never read from the
YAML; `BetaSecrets` reads them from the environment.
"""
from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Optional

import yaml

from common.versioning import canonical_json

ROOT_DIR = Path(__file__).resolve().parent.parent
BETA_CONFIG_PATH = ROOT_DIR / "config" / "beta_v0.yaml"

RULES_VERSION = "BETA_EVENT_RULES_V1"
# State-tape payload schema. V1: the original beta tape. V2 (temporal context,
# docs/BETA_BTC_TEMPORAL_CONTEXT_V0.md) additionally records per-venue raw Stage-2
# values (snapshot `venue_raw`) and per-venue 5m kline OHLC (`metrics`
# x:<venue>:kline_*, venue `ohlc`). The payload shape is a function of the version,
# so a V1 configuration still reproduces V1 rows byte-for-byte.
SUPPORTED_STATE_SCHEMA_VERSIONS = (1, 2)
CANONICAL_EXCHANGES = ("binance", "bybit", "okx")

# Internal event-type codes (never shown verbatim to users; see beta/formatter.py).
PRICE_OI_CONTRACTION_DOWN = "PRICE_OI_CONTRACTION_DOWN"
PRICE_OI_CONTRACTION_UP = "PRICE_OI_CONTRACTION_UP"
POSITION_BUILDUP_COMPRESSION = "POSITION_BUILDUP_COMPRESSION"
TAKER_FLOW_EXTREME_BUY = "TAKER_FLOW_EXTREME_BUY"
TAKER_FLOW_EXTREME_SELL = "TAKER_FLOW_EXTREME_SELL"
LIQUIDATION_STRESS_LONG = "LIQUIDATION_STRESS_LONG"
LIQUIDATION_STRESS_SHORT = "LIQUIDATION_STRESS_SHORT"

CORE_EVENT_TYPES = (PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP,
                    POSITION_BUILDUP_COMPRESSION)
GATED_EVENT_TYPES = (TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL,
                     LIQUIDATION_STRESS_LONG, LIQUIDATION_STRESS_SHORT)
EVENT_TYPES = CORE_EVENT_TYPES + GATED_EVENT_TYPES

HORIZON_MINUTES = MappingProxyType({"15m": 15, "30m": 30, "1h": 60, "4h": 240, "24h": 1440})

_TOP_KEYS = frozenset({
    "enabled", "detection_enabled", "push_enabled", "outcome_tracking_enabled",
    "rules_version", "state_schema_version", "outcome_version", "symbol",
    "market_type", "timeframe", "active_exchanges", "percentile_window",
    "min_venue_coverage", "max_state_age_s", "bucket_close_grace_s",
    "same_event_cooldown_min", "delivery_ttl_s", "max_new_pushes_per_utc_day",
    "forward_horizons", "detector", "bootstrap", "ingestion", "outcomes",
    "notifications", "privacy", "health", "rules", "episodization", "context",
    "horizon_changes", "access", "telemetry", "feedback", "regime_d7", "briefing",
    "push_policy", "decision", "level_race",
})
# deploy/signalbot-beta-notify.service TimeoutStartSec: no send may start after the budget (A5)
NOTIFY_UNIT_TIMEOUT_S = 50
# The beta sender's Telegram timeouts (connect, write, read, pool; runtime.beta_bot.BetaTelegramSender):
# one send takes at most their sum. The budget leaves that plus the run's tail (health, owner alert
# rows, the dead-man ping of at most 5 s) before the unit's timeout (A5 review).
SEND_TIMEOUTS_S = (5.0, 5.0, 5.0, 2.0)
NOTIFY_TAIL_S = 8
NOTIFY_BUDGET_MAX_S = int(NOTIFY_UNIT_TIMEOUT_S - sum(SEND_TIMEOUTS_S) - NOTIFY_TAIL_S)
_SECTION_KEYS = {
    "detector": {"max_catchup_buckets_per_run"},
    "bootstrap": {"lookback_days", "max_buckets_per_run"},
    "ingestion": {"heartbeat_max_age_s", "min_healthy_venues"},
    "outcomes": {"max_jobs_per_run", "incomplete_after_h", "recheck_window_h"},
    "notifications": {"max_deliveries_per_run", "send_interval_ms", "send_budget_s"},
    "privacy": {"stopped_user_retention_days"},
    "health": {"detector_stall_s", "outcome_stall_s", "bot_stall_s", "notifier_stall_s",
               "delivery_problem_window_s", "delivery_problem_threshold",
               "owner_alert_repeat_s"},
}
_RULE_KEYS = {
    "PRICE_OI_CONTRACTION_DOWN": {"price_move_pct_median_max", "oi_change_pct_median_max",
                                  "armed_at_streak", "triggered_at_streak"},
    "PRICE_OI_CONTRACTION_UP": {"price_move_pct_median_min", "oi_change_pct_median_max",
                                "armed_at_streak", "triggered_at_streak"},
    "POSITION_BUILDUP_COMPRESSION": {"range_width_pct_median_max", "oi_change_pct_median_min",
                                     "volume_notional_usd_sum_min", "early_at_streak",
                                     "armed_at_streak", "triggered_at_streak",
                                     "max_duration_min"},
    "TAKER_FLOW_EXTREME": {"enabled", "buy_percentile_min", "sell_percentile_max",
                           "armed_at_streak", "triggered_at_streak"},
    "LIQUIDATION_STRESS": {"enabled", "venue_percentile_min", "min_eligible_venues",
                           "triggered_at_streak"},
}
_PERCENTILE_KEYS = {
    "price_move_pct_median_max", "price_move_pct_median_min", "oi_change_pct_median_max",
    "range_width_pct_median_max", "oi_change_pct_median_min", "volume_notional_usd_sum_min",
    "buy_percentile_min", "sell_percentile_max", "venue_percentile_min",
}

# Temporal-context sections (episodization + 1h context). They never enter the
# rules digest: they change presentation / episode projection, not detection.
_EPISODIZATION_KEYS = {"version", "live_hysteresis_enabled"}
_CONTEXT_KEYS = {"version", "rolling_buckets", "rolling_buckets_4h", "label_elevated", "label_high",
                 "label_extreme", "tail_display_max", "last_event_retention_min"}

# Presentation thresholds for "Changes vs previous 24h". They never enter the
# rules digest: they do not change detection.
_HORIZON_CHANGES_KEYS = {"version", "range_wider_ratio", "range_narrower_ratio",
                         "volume_higher_ratio", "volume_lower_ratio",
                         "oi_abs_pct_min", "price_abs_pct_min"}

# Join cap and activity retention. They never enter the rules digest.
_ACCESS_KEYS = {"max_active_users"}
_TELEMETRY_KEYS = {"retention_days", "rejected_start_retention_days"}

# /feedback limits. Presentation only. They never enter the rules digest.
_FEEDBACK_KEYS = {"max_chars", "max_per_utc_day"}
# Morning briefing (PRODUCT_FIRST_DECISION_V1 §3 row 3). Not detection, not the rules
# digest. `enabled` is a committed allow; sending also needs the global push switches.
_BRIEFING_KEYS = {"enabled", "time_kyiv", "max_delay_min", "withdrawal"}
# U1a withdrawal test (BETA_MEASUREMENT_CONTRACT_V1 §6): the rule is frozen before Day 0;
# only `day0_kyiv` is filled in when Day 0 happens. Null = no briefing is ever withheld.
_BRIEF_WITHDRAWAL_KEYS = {"day0_kyiv", "seed", "count", "first_cohort_day", "last_cohort_day"}

# D7 regime line. Display only. It never enters the rules digest.
_REGIME_D7_KEYS = {"enabled"}
# Delivery-side push policy (PRODUCT_FIRST_DECISION_V1 §3 row 8): quiet hours in Kyiv
# time and one cooldown across event types. Policy only; never the rules digest.
_PUSH_POLICY_KEYS = {"quiet_hours_kyiv", "global_cooldown_min"}
# PRODUCT_DECISION_V2: decision support. Presentation and market-alert policy only.
_DECISION_KEYS = {"max_price_alerts", "forecast_tracking", "claim_journal", "market_alerts", "research_evidence",
                  "weekly_report", "signature_index"}
# Weekly report (backlog B4). Presentation and delivery only.
_WEEKLY_REPORT_KEYS = {"enabled", "weekday_kyiv", "time_kyiv", "max_delay_min"}
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_MARKET_ALERT_KEYS = {"enabled", "max_per_utc_day", "move_cooldown_min", "event_lead_min",
                      "touch_max_age_min"}
# Research evidence (owner task 2026-10-04; docs/research/RESEARCH_EVIDENCE_INTEGRATION_V1.md):
# live matching of closed research units and the read-only public feeds it needs. Presentation
# only: never detection, push gating, corridors or touch probabilities. `enabled` is the
# presentation switch of the «🔬 Исследования» tab (with BETA_RESEARCH_EVIDENCE_ENABLED,
# research_presentation_enabled); `main_surfaces_enabled` adds the lines on the main surfaces
# (research_main_surfaces_enabled; off by PRE_BETA_SCOPE_DECISION_V1 §6.1); `feeds_enabled` /
# `stress_hours_enabled` alone gate collection (deploy plan PREREQ-2).
_RESEARCH_EVIDENCE_KEYS = {"enabled", "main_surfaces_enabled", "feeds_enabled", "stress_hours_enabled",
                           "main_surface_max"}

# Rule-relevant fields that enter the rules digest (policy fields such as TTL /
# cooldown / cap only enter the config digest).
_RULE_DIGEST_FIELDS = ("rules_version", "state_schema_version", "symbol", "market_type",
                       "timeframe", "active_exchanges", "percentile_window",
                       "min_venue_coverage", "max_state_age_s", "rules")


class BetaConfigError(ValueError):
    """Invalid beta configuration (fail loudly; never default silently)."""


def _int(value, name: str, *, minimum: int = 1) -> int:
    if type(value) is not int or value < minimum:
        raise BetaConfigError(f"{name} must be an int >= {minimum}, got {value!r}")
    return value


def _bool(value, name: str) -> bool:
    if type(value) is not bool:
        raise BetaConfigError(f"{name} must be a bool, got {value!r}")
    return value


def _unit(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BetaConfigError(f"{name} must be a number in [0, 1], got {value!r}")
    v = float(value)
    if not math.isfinite(v) or not (0.0 <= v <= 1.0):
        raise BetaConfigError(f"{name} must be a number in [0, 1], got {value!r}")
    return v


def _freeze(obj):
    if isinstance(obj, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in obj.items()})
    if isinstance(obj, (list, tuple)):
        return tuple(_freeze(v) for v in obj)
    return obj


def _exact_keys(mapping, expected, name: str) -> None:
    if not isinstance(mapping, Mapping):
        raise BetaConfigError(f"{name} must be a mapping")
    keys = set(mapping)
    if keys != set(expected):
        raise BetaConfigError(
            f"{name} keys mismatch: missing={sorted(set(expected) - keys)} "
            f"extra={sorted(keys - set(expected))}")


@dataclass(frozen=True)
class BetaConfig:
    raw: Mapping[str, Any]

    # ---- construction ----------------------------------------------------
    @classmethod
    def load(cls, path: Path = BETA_CONFIG_PATH) -> "BetaConfig":
        with open(path, "r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        if not isinstance(doc, Mapping) or set(doc) != {"beta"}:
            raise BetaConfigError("beta config must have exactly one top-level key 'beta'")
        return cls.from_mapping(doc["beta"])

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "BetaConfig":
        _validate(data)
        return cls(raw=_freeze(data))

    def with_overrides(self, **overrides) -> "BetaConfig":
        """Test/operator helper: a NEW validated config with top-level keys replaced."""
        from common.versioning import _to_plain  # plain copy
        data = _to_plain(self.raw)
        data.update(overrides)
        return BetaConfig.from_mapping(data)

    # ---- accessors ---------------------------------------------------------
    def __getitem__(self, key):
        return self.raw[key]

    def section(self, name: str) -> Mapping[str, Any]:
        return self.raw[name]

    def rule(self, family: str) -> Mapping[str, Any]:
        return self.raw["rules"][family]

    @property
    def symbol(self) -> str:
        return self.raw["symbol"]

    @property
    def market_type(self) -> str:
        return self.raw["market_type"]

    @property
    def timeframe(self) -> str:
        return self.raw["timeframe"]

    @property
    def exchanges(self) -> tuple:
        return tuple(self.raw["active_exchanges"])

    @property
    def rules_version(self) -> str:
        return self.raw["rules_version"]

    @property
    def state_schema_version(self) -> int:
        return self.raw["state_schema_version"]

    @property
    def outcome_version(self) -> str:
        return self.raw["outcome_version"]

    @property
    def min_venues(self) -> int:
        return self.raw["min_venue_coverage"]

    @property
    def bucket(self) -> timedelta:
        return timedelta(minutes=5)

    @property
    def cooldown(self) -> timedelta:
        return timedelta(minutes=self.raw["same_event_cooldown_min"])

    @property
    def global_cooldown(self) -> timedelta:
        return timedelta(minutes=self.raw["push_policy"]["global_cooldown_min"])

    @property
    def quiet_hours_kyiv(self) -> tuple:
        """(start, end) as HH:MM Kyiv wall-clock strings; the window wraps midnight."""
        q = self.raw["push_policy"]["quiet_hours_kyiv"]
        return (str(q[0]), str(q[1]))

    @property
    def delivery_ttl(self) -> timedelta:
        return timedelta(seconds=self.raw["delivery_ttl_s"])

    @property
    def horizons(self) -> tuple:
        return tuple(self.raw["forward_horizons"])

    # ---- digests -----------------------------------------------------------
    @property
    def rules_digest(self) -> str:
        payload = {k: self.raw[k] for k in _RULE_DIGEST_FIELDS}
        return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()

    @property
    def config_digest(self) -> str:
        return hashlib.sha256(canonical_json(self.raw).encode("utf-8")).hexdigest()


def _validate(d: Mapping[str, Any]) -> None:
    _exact_keys(d, _TOP_KEYS, "beta")
    for key in ("enabled", "detection_enabled", "push_enabled", "outcome_tracking_enabled"):
        _bool(d[key], key)
    if d["rules_version"] != RULES_VERSION:
        raise BetaConfigError(f"rules_version must be {RULES_VERSION!r}")
    if d["state_schema_version"] not in SUPPORTED_STATE_SCHEMA_VERSIONS \
            or type(d["state_schema_version"]) is not int:
        raise BetaConfigError("unsupported state_schema_version")
    if not isinstance(d["outcome_version"], str) or not d["outcome_version"].strip():
        raise BetaConfigError("outcome_version must be a non-empty string")
    if d["symbol"] != "BTCUSDT" or d["market_type"] != "perp" or d["timeframe"] != "5m":
        raise BetaConfigError("V0.2 scope is exactly BTCUSDT / perp / 5m")
    ex = d["active_exchanges"]
    if not isinstance(ex, (list, tuple)) or len(set(ex)) != len(ex) or not ex \
            or any(e not in CANONICAL_EXCHANGES for e in ex):
        raise BetaConfigError(f"active_exchanges must be distinct members of {CANONICAL_EXCHANGES}")
    if d["percentile_window"] != "30d":
        raise BetaConfigError("V0.2 rules use exactly the 30d percentile window")
    _int(d["min_venue_coverage"], "min_venue_coverage", minimum=2)
    if d["min_venue_coverage"] > len(ex):
        raise BetaConfigError("min_venue_coverage exceeds active venue count")
    for key in ("max_state_age_s", "same_event_cooldown_min", "delivery_ttl_s",
                "max_new_pushes_per_utc_day"):
        _int(d[key], key)
    _int(d["bucket_close_grace_s"], "bucket_close_grace_s", minimum=0)
    if d["bucket_close_grace_s"] >= 300:
        raise BetaConfigError("bucket_close_grace_s must be < 300")
    hz = d["forward_horizons"]
    if not isinstance(hz, (list, tuple)) or not hz or len(set(hz)) != len(hz) \
            or any(h not in HORIZON_MINUTES for h in hz):
        raise BetaConfigError(f"forward_horizons must be distinct members of {list(HORIZON_MINUTES)}")
    for section, keys in _SECTION_KEYS.items():
        _exact_keys(d[section], keys, section)
        for k in keys:
            _int(d[section][k], f"{section}.{k}")
    if d["notifications"]["send_budget_s"] > NOTIFY_BUDGET_MAX_S:
        raise BetaConfigError(f"notifications.send_budget_s must be <= {NOTIFY_BUDGET_MAX_S}: one send "
                              f"({sum(SEND_TIMEOUTS_S):.0f} s) and the run's tail ({NOTIFY_TAIL_S} s) must fit "
                              f"before the notifier unit's {NOTIFY_UNIT_TIMEOUT_S} s timeout")
    if d["bootstrap"]["lookback_days"] > 30:
        raise BetaConfigError("bootstrap.lookback_days must be <= 30 (maximum needed by rules)")
    if d["ingestion"]["min_healthy_venues"] > len(ex):
        raise BetaConfigError("ingestion.min_healthy_venues exceeds active venue count")
    rules = d["rules"]
    _exact_keys(rules, _RULE_KEYS, "rules")
    for family, keys in _RULE_KEYS.items():
        r = rules[family]
        _exact_keys(r, keys, f"rules.{family}")
        for k in keys:
            if k == "enabled":
                _bool(r[k], f"rules.{family}.enabled")
            elif k in _PERCENTILE_KEYS:
                _unit(r[k], f"rules.{family}.{k}")
            else:
                _int(r[k], f"rules.{family}.{k}")
    for family in ("PRICE_OI_CONTRACTION_DOWN", "PRICE_OI_CONTRACTION_UP", "TAKER_FLOW_EXTREME"):
        if not (rules[family]["armed_at_streak"] < rules[family]["triggered_at_streak"]):
            raise BetaConfigError(f"rules.{family}: armed_at_streak must be < triggered_at_streak")
    b = rules["POSITION_BUILDUP_COMPRESSION"]
    if not (b["early_at_streak"] < b["armed_at_streak"] < b["triggered_at_streak"]):
        raise BetaConfigError("POSITION_BUILDUP_COMPRESSION streaks must be strictly increasing")
    if b["max_duration_min"] <= b["triggered_at_streak"] * 5:
        raise BetaConfigError("POSITION_BUILDUP_COMPRESSION max_duration_min too short")
    if rules["LIQUIDATION_STRESS"]["min_eligible_venues"] < 2:
        raise BetaConfigError("LIQUIDATION_STRESS.min_eligible_venues must be >= 2")
    _validate_temporal_context(d)
    _validate_horizon_changes(d)
    _validate_access(d)
    _validate_telemetry(d)
    _validate_feedback(d)
    _validate_regime_d7(d)
    _validate_briefing(d)
    _validate_push_policy(d)
    _validate_decision(d)
    _validate_level_race(d)


# Level race at structural first touches (FORECAST_LAYER_DECISION_V1 §6a; beta/level_race_live.py).
_LEVEL_RACE_KEYS = {"journal_enabled", "display_enabled", "model_states_enabled", "push_trigger"}


def _validate_level_race(d: Mapping[str, Any]) -> None:
    x = d["level_race"]
    _exact_keys(x, _LEVEL_RACE_KEYS, "level_race")
    for key in ("journal_enabled", "display_enabled", "model_states_enabled"):
        _bool(x[key], f"level_race.{key}")
    if x["push_trigger"] not in ("legacy", "structural"):
        raise BetaConfigError("level_race.push_trigger must be legacy or structural")


def _validate_decision(d: Mapping[str, Any]) -> None:
    x = d["decision"]
    _exact_keys(x, _DECISION_KEYS, "decision")
    _int(x["max_price_alerts"], "decision.max_price_alerts", minimum=1)
    _bool(x["forecast_tracking"], "decision.forecast_tracking")
    _bool(x["claim_journal"], "decision.claim_journal")
    _bool(x["signature_index"], "decision.signature_index")
    m = x["market_alerts"]
    _exact_keys(m, _MARKET_ALERT_KEYS, "decision.market_alerts")
    _bool(m["enabled"], "decision.market_alerts.enabled")
    for key in ("max_per_utc_day", "move_cooldown_min", "event_lead_min", "touch_max_age_min"):
        _int(m[key], f"decision.market_alerts.{key}", minimum=1)
    w = x["weekly_report"]
    _exact_keys(w, _WEEKLY_REPORT_KEYS, "decision.weekly_report")
    _bool(w["enabled"], "decision.weekly_report.enabled")
    if w["weekday_kyiv"] not in WEEKDAYS:
        raise BetaConfigError(f"decision.weekly_report.weekday_kyiv must be one of {', '.join(WEEKDAYS)}")
    _hhmm(w["time_kyiv"], "decision.weekly_report.time_kyiv")
    _int(w["max_delay_min"], "decision.weekly_report.max_delay_min", minimum=1)
    r = x["research_evidence"]
    _exact_keys(r, _RESEARCH_EVIDENCE_KEYS, "decision.research_evidence")
    for key in ("enabled", "main_surfaces_enabled", "feeds_enabled", "stress_hours_enabled"):
        _bool(r[key], f"decision.research_evidence.{key}")
    if _int(r["main_surface_max"], "decision.research_evidence.main_surface_max", minimum=1) > 2:
        raise BetaConfigError("decision.research_evidence.main_surface_max must be 1 or 2 (owner task 2026-10-04)")


def _hhmm(value, name: str) -> None:
    if not isinstance(value, str) or len(value) != 5 or value[2] != ":" or not (value[:2] + value[3:]).isdigit() \
            or int(value[:2]) > 23 or int(value[3:]) > 59:
        raise BetaConfigError(f"{name} must be HH:MM")


def _validate_push_policy(d: Mapping[str, Any]) -> None:
    p = d["push_policy"]
    _exact_keys(p, _PUSH_POLICY_KEYS, "push_policy")
    q = p["quiet_hours_kyiv"]
    if not isinstance(q, (list, tuple)) or len(q) != 2:
        raise BetaConfigError("push_policy.quiet_hours_kyiv must be [start, end] in HH:MM")
    _hhmm(q[0], "push_policy.quiet_hours_kyiv[0]")
    _hhmm(q[1], "push_policy.quiet_hours_kyiv[1]")
    _int(p["global_cooldown_min"], "push_policy.global_cooldown_min", minimum=1)


def _validate_briefing(d: Mapping[str, Any]) -> None:
    b = d["briefing"]
    # `withdrawal` may be absent (off) in an override; the committed config carries it.
    _exact_keys(b, _BRIEFING_KEYS if "withdrawal" in b else _BRIEFING_KEYS - {"withdrawal"}, "briefing")
    _bool(b["enabled"], "briefing.enabled")
    t = b["time_kyiv"]
    if not isinstance(t, str) or len(t) != 5 or t[2] != ":" or not (t[:2] + t[3:]).isdigit() \
            or int(t[:2]) > 23 or int(t[3:]) > 59:
        raise BetaConfigError("briefing.time_kyiv must be HH:MM")
    _int(b["max_delay_min"], "briefing.max_delay_min", minimum=1)
    w = b.get("withdrawal")
    if w is None:
        return
    _exact_keys(w, _BRIEF_WITHDRAWAL_KEYS, "briefing.withdrawal")
    day0 = w["day0_kyiv"]
    if day0 is not None:
        try:
            date.fromisoformat(day0)
        except (TypeError, ValueError):
            raise BetaConfigError("briefing.withdrawal.day0_kyiv must be null or a quoted YYYY-MM-DD") from None
    _int(w["seed"], "briefing.withdrawal.seed", minimum=0)
    if w["count"] != 3:
        raise BetaConfigError("briefing.withdrawal.count must be 3 (PRODUCT_FIRST_DECISION_V1 §7 U1a)")
    first = _int(w["first_cohort_day"], "briefing.withdrawal.first_cohort_day", minimum=1)
    last = _int(w["last_cohort_day"], "briefing.withdrawal.last_cohort_day", minimum=1)
    if last - first < 6:
        raise BetaConfigError("briefing.withdrawal cohort-day range must hold at least one full week")


def _validate_temporal_context(d: Mapping[str, Any]) -> None:
    ep = d["episodization"]
    _exact_keys(ep, _EPISODIZATION_KEYS, "episodization")
    if not isinstance(ep["version"], str) or not ep["version"].strip():
        raise BetaConfigError("episodization.version must be a non-empty string")
    if _bool(ep["live_hysteresis_enabled"], "episodization.live_hysteresis_enabled"):
        raise BetaConfigError("episodization.live_hysteresis_enabled must be false: hysteresis "
                              "parameters are unfrozen and not approved for /btc, pushes or episodes")
    c = d["context"]
    _exact_keys(c, _CONTEXT_KEYS, "context")
    if not isinstance(c["version"], str) or not c["version"].strip():
        raise BetaConfigError("context.version must be a non-empty string")
    _int(c["rolling_buckets"], "context.rolling_buckets", minimum=2)
    _int(c["rolling_buckets_4h"], "context.rolling_buckets_4h", minimum=2)
    if c["rolling_buckets_4h"] <= c["rolling_buckets"]:
        raise BetaConfigError("context.rolling_buckets_4h must be longer than rolling_buckets")
    for k in ("label_elevated", "label_high", "label_extreme", "tail_display_max"):
        _unit(c[k], f"context.{k}")
    if not (0.5 <= c["label_elevated"] < c["label_high"] < c["label_extreme"] < 1.0):
        raise BetaConfigError("context labels must satisfy 0.5 <= elevated < high < extreme < 1")
    if not (0.0 < c["tail_display_max"] <= 0.5):
        raise BetaConfigError("context.tail_display_max must be in (0, 0.5]")
    _int(c["last_event_retention_min"], "context.last_event_retention_min", minimum=5)


def _positive(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BetaConfigError(f"{name} must be a positive number, got {value!r}")
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise BetaConfigError(f"{name} must be a positive number, got {value!r}")
    return v


def _validate_horizon_changes(d: Mapping[str, Any]) -> None:
    h = d["horizon_changes"]
    _exact_keys(h, _HORIZON_CHANGES_KEYS, "horizon_changes")
    if not isinstance(h["version"], str) or not h["version"].strip():
        raise BetaConfigError("horizon_changes.version must be a non-empty string")
    wider = _positive(h["range_wider_ratio"], "horizon_changes.range_wider_ratio")
    narrower = _positive(h["range_narrower_ratio"], "horizon_changes.range_narrower_ratio")
    if not (narrower < 1.0 < wider):
        raise BetaConfigError("horizon_changes range ratios must satisfy narrower < 1 < wider")
    vol_hi = _positive(h["volume_higher_ratio"], "horizon_changes.volume_higher_ratio")
    vol_lo = _positive(h["volume_lower_ratio"], "horizon_changes.volume_lower_ratio")
    if not (vol_lo < 1.0 < vol_hi):
        raise BetaConfigError("horizon_changes volume ratios must satisfy lower < 1 < higher")
    _positive(h["oi_abs_pct_min"], "horizon_changes.oi_abs_pct_min")
    _positive(h["price_abs_pct_min"], "horizon_changes.price_abs_pct_min")


def _validate_access(d: Mapping[str, Any]) -> None:
    a = d["access"]
    _exact_keys(a, _ACCESS_KEYS, "access")
    _int(a["max_active_users"], "access.max_active_users", minimum=1)


def _validate_telemetry(d: Mapping[str, Any]) -> None:
    tel = d["telemetry"]
    _exact_keys(tel, _TELEMETRY_KEYS, "telemetry")
    _int(tel["retention_days"], "telemetry.retention_days", minimum=1)
    _int(tel["rejected_start_retention_days"], "telemetry.rejected_start_retention_days", minimum=1)


def _validate_feedback(d: Mapping[str, Any]) -> None:
    f = d["feedback"]
    _exact_keys(f, _FEEDBACK_KEYS, "feedback")
    _int(f["max_chars"], "feedback.max_chars", minimum=1)
    _int(f["max_per_utc_day"], "feedback.max_per_utc_day", minimum=1)


def _validate_regime_d7(d: Mapping[str, Any]) -> None:
    r = d["regime_d7"]
    _exact_keys(r, _REGIME_D7_KEYS, "regime_d7")
    _bool(r["enabled"], "regime_d7.enabled")


# ---- hard switches ---------------------------------------------------------
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _env_flag(env: Mapping[str, str], name: str, *, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    v = raw.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    raise BetaConfigError(f"{name} must be a boolean flag (got an unrecognized value)")


@dataclass(frozen=True)
class BetaSwitches:
    enabled: bool
    detection: bool
    push_hard: bool
    outcome_tracking: bool
    # False only in the explicit no-Telegram shadow-soak mode
    # (BETA_TELEGRAM_ENABLED=0): no bot, no notifier, no Telegram health checks.
    telegram: bool = True

    def as_dict(self) -> dict:
        return {"BETA_ENABLED": self.enabled, "BETA_DETECTION_ENABLED": self.detection,
                "BETA_PUSH_ENABLED": self.push_hard,
                "BETA_OUTCOME_TRACKING_ENABLED": self.outcome_tracking,
                "BETA_TELEGRAM_ENABLED": self.telegram}


def resolve_switches(cfg: BetaConfig, env: Optional[Mapping[str, str]] = None) -> BetaSwitches:
    """Effective hard switches. Precedence (deterministic):

    * BETA_ENABLED: an explicit env value (true or false) wins; unset/empty
      falls back to the committed `beta.enabled` (false by default).
    * Detection / outcome tracking: config AND env (env can only restrict).
    * Push: committed `push_enabled` AND an EXPLICIT true BETA_PUSH_ENABLED
      (unset => push forbidden); the env can never enable push on its own.
    * BETA_TELEGRAM_ENABLED=0 selects the no-Telegram shadow-soak mode; it is
      refused (BetaConfigError) while push is enabled or a bot token is set.
    """
    env = os.environ if env is None else env
    enabled = _env_flag(env, "BETA_ENABLED", default=bool(cfg["enabled"]))
    push_hard = enabled and cfg["push_enabled"] and _env_flag(env, "BETA_PUSH_ENABLED", default=False)
    telegram = _env_flag(env, "BETA_TELEGRAM_ENABLED", default=True)
    if not telegram:
        if push_hard:
            raise BetaConfigError("BETA_TELEGRAM_ENABLED=0 (no-Telegram shadow mode) "
                                  "conflicts with enabled push")
        if (env.get("BETA_TELEGRAM_BOT_TOKEN") or "").strip():
            raise BetaConfigError("BETA_TELEGRAM_ENABLED=0 (no-Telegram shadow mode) "
                                  "requires BETA_TELEGRAM_BOT_TOKEN to be unset")
    return BetaSwitches(
        enabled=enabled,
        detection=enabled and cfg["detection_enabled"]
        and _env_flag(env, "BETA_DETECTION_ENABLED", default=True),
        push_hard=push_hard,
        outcome_tracking=enabled and cfg["outcome_tracking_enabled"]
        and _env_flag(env, "BETA_OUTCOME_TRACKING_ENABLED", default=True),
        telegram=telegram,
    )


def effective_push_enabled(switches: BetaSwitches, admin_push_enabled: bool) -> bool:
    """Admin durable state can only further restrict the hard switch."""
    return bool(switches.push_hard and admin_push_enabled is True)


def research_presentation_enabled(cfg: BetaConfig, env: Optional[Mapping[str, str]] = None) -> bool:
    """Research evidence on the bot's surfaces: `decision.research_evidence.enabled` AND
    BETA_RESEARCH_EVIDENCE_ENABLED. An unset env value leaves the config in charge; the env can
    only switch presentation off, and an unrecognised value is read as off (fail closed). It
    never gates collection: the feed jobs follow `feeds_enabled` / `stress_hours_enabled`."""
    env = os.environ if env is None else env
    rcfg = cfg.section("decision").get("research_evidence") or {}
    if not rcfg.get("enabled"):
        return False
    try:
        return _env_flag(env, "BETA_RESEARCH_EVIDENCE_ENABLED", default=True)
    except BetaConfigError:
        return False


def research_main_surfaces_enabled(cfg: BetaConfig, env: Optional[Mapping[str, str]] = None) -> bool:
    """Research lines on the main surfaces (/btc, /catchup, the briefing, /levels, /risk, alerts and
    pushes): the presentation switch AND `decision.research_evidence.main_surfaces_enabled`. Off, the
    evidence is still collected, matched and shown in the «🔬 Исследования» tab and /research
    (PRE_BETA_SCOPE_DECISION_V1 §6.1)."""
    rcfg = cfg.section("decision").get("research_evidence") or {}
    return bool(rcfg.get("main_surfaces_enabled")) and research_presentation_enabled(cfg, env)


def effective_d7_enabled(cfg: BetaConfig, admin_d7_enabled: bool) -> bool:
    """The D7 line needs the committed hard allow and the owner state.

    A missing owner row is off. `/admin_d7_on` cannot show the line when
    `regime_d7.enabled` is false.
    """
    return bool(cfg.section("regime_d7")["enabled"] and admin_d7_enabled is True)


# ---- secrets (environment only) --------------------------------------------
@dataclass(frozen=True)
class BetaSecrets:
    bot_token: Optional[str]
    owner_user_id: Optional[int]

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "BetaSecrets":
        env = os.environ if env is None else env
        token = (env.get("BETA_TELEGRAM_BOT_TOKEN") or "").strip() or None
        owner_raw = (env.get("BETA_OWNER_TELEGRAM_USER_ID") or "").strip()
        owner = None
        if owner_raw:
            if not owner_raw.isdigit():
                raise BetaConfigError("BETA_OWNER_TELEGRAM_USER_ID must be a positive integer")
            owner = int(owner_raw)
        return cls(bot_token=token, owner_user_id=owner)

    def __repr__(self) -> str:  # never leak secrets through repr/logging
        return (f"BetaSecrets(bot_token={'set' if self.bot_token else 'unset'}, "
                f"owner_user_id={'set' if self.owner_user_id else 'unset'})")
