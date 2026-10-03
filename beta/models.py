"""Beta V0.2 immutable models and closed vocabularies.

Pure data only. Personal identifiers (Telegram ids) NEVER appear in any model
used by the tape / rules / detector / outcomes layers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional

# ---- episode lifecycle -------------------------------------------------------
EARLY, ARMED, TRIGGERED, ENDED, EXPIRED = "EARLY", "ARMED", "TRIGGERED", "ENDED", "EXPIRED"
OPEN_STATES = (EARLY, ARMED, TRIGGERED)
TERMINAL_STATES = (ENDED, EXPIRED)
EPISODE_STATES = OPEN_STATES + TERMINAL_STATES
STATE_ORDER = {EARLY: 0, ARMED: 1, TRIGGERED: 2}

# ---- per-bucket rule evaluation (NOT a lifecycle state) ----------------------
QUALIFIES = "QUALIFIES"
NOT_QUALIFIES = "NOT_QUALIFIES"
NOT_EVALUABLE = "NOT_EVALUABLE"
EVALUATION_STATUSES = (QUALIFIES, NOT_QUALIFIES, NOT_EVALUABLE)

# ---- transition / terminal reasons -------------------------------------------
REASON_CONDITION_MET = "CONDITION_MET"
REASON_CONDITION_FAILED = "CONDITION_FAILED"
REASON_NOT_EVALUABLE = "NOT_EVALUABLE"
REASON_MAX_DURATION = "MAX_DURATION"
REASON_DETECTOR_VERSION_CHANGED = "DETECTOR_VERSION_CHANGED"
REASON_DETECTION_GAP = "DETECTION_GAP"
TERMINAL_REASONS = (REASON_CONDITION_FAILED, REASON_NOT_EVALUABLE, REASON_MAX_DURATION,
                    REASON_DETECTOR_VERSION_CHANGED, REASON_DETECTION_GAP)

# ---- push policy -------------------------------------------------------------
PUSH = "PUSH"
SUPPRESSED = "SUPPRESSED"
DAILY_CAP = "DAILY_CAP"
SAME_EVENT_COOLDOWN = "SAME_EVENT_COOLDOWN"
PUSH_DISABLED = "PUSH_DISABLED"
DELIVERY_TOO_OLD = "DELIVERY_TOO_OLD"
DATA_DEGRADED_REASON = "DATA_DEGRADED"
USER_INACTIVE = "USER_INACTIVE"
# Delivery-only: a briefing withheld on a U1a withdrawal day (BETA_MEASUREMENT_CONTRACT_V1 §6).
BRIEF_WITHDRAWAL = "BRIEF_WITHDRAWAL"
# PRODUCT_FIRST_DECISION_V1 §3 rows 7-8: the product-level unusual-hour gate and the
# delivery-side policy. Evaluated in a fixed order (see beta.detector.push_policy), so
# a reason that comes after the gate implies the hour qualified.
HOUR_NOT_UNUSUAL = "HOUR_NOT_UNUSUAL"
QUIET_HOURS = "QUIET_HOURS"
GLOBAL_COOLDOWN = "GLOBAL_COOLDOWN"
SUPPRESSION_REASONS = (DAILY_CAP, SAME_EVENT_COOLDOWN, PUSH_DISABLED, DELIVERY_TOO_OLD,
                       DATA_DEGRADED_REASON, USER_INACTIVE, HOUR_NOT_UNUSUAL, QUIET_HOURS,
                       GLOBAL_COOLDOWN)
# Reasons recorded AFTER the hour gate passed: the hour stays eligible for /catchup and
# the morning briefing (decision §3.1b.3); only delivery was withheld.
QUALIFIED_SUPPRESSIONS = (SAME_EVENT_COOLDOWN, GLOBAL_COOLDOWN, QUIET_HOURS, DAILY_CAP, PUSH_DISABLED)

# ---- delivery state machine (at most ONE send attempt per user/notification) --
D_PENDING, D_SENDING, D_SENT, D_FAILED = "PENDING", "SENDING", "SENT", "FAILED"
D_UNKNOWN, D_EXPIRED, D_SUPPRESSED = "DELIVERY_UNKNOWN", "EXPIRED_UNDELIVERED", "SUPPRESSED"
DELIVERY_STATES = (D_PENDING, D_SENDING, D_SENT, D_FAILED, D_UNKNOWN, D_EXPIRED, D_SUPPRESSED)

# ---- user-facing product statuses ---------------------------------------------
S_NO_ACTIVE = "NO ACTIVE EVENTS"
S_WATCH = "WATCH"
S_EVENT_ACTIVE = "EVENT ACTIVE"
S_DEGRADED = "DATA DEGRADED"
S_STALE = "DATA STALE"
PRODUCT_STATUSES = (S_NO_ACTIVE, S_WATCH, S_EVENT_ACTIVE, S_DEGRADED, S_STALE)

# ---- tape origins ---------------------------------------------------------------
ORIGIN_LIVE = "LIVE"
ORIGIN_BOOTSTRAP = "BOOTSTRAP"
ORIGIN_CORRECTION_CHECK = "CORRECTION_CHECK"
TAPE_ORIGINS = (ORIGIN_LIVE, ORIGIN_BOOTSTRAP, ORIGIN_CORRECTION_CHECK)

# ---- outcomes -------------------------------------------------------------------
OUTCOME_COMPLETE = "COMPLETE"
OUTCOME_INCOMPLETE_DATA = "INCOMPLETE_DATA"
OUTCOME_REFERENCE_UNAVAILABLE = "REFERENCE_UNAVAILABLE"
OUTCOME_STATUSES = (OUTCOME_COMPLETE, OUTCOME_INCOMPLETE_DATA, OUTCOME_REFERENCE_UNAVAILABLE)

# Families the core events and NO ACTIVE EVENTS depend on.
CORE_FAMILIES = ("price_structure", "oi", "volume")


@dataclass(frozen=True)
class TapeRecord:
    """One immutable by-value state-tape snapshot (one evaluated/bootstrapped bucket).
    `snapshot` is plain JSON-safe data; digests are sha256 of canonical JSON."""
    symbol: str
    market_type: str
    timeframe: str
    bucket_ts: datetime
    calculation_version: str
    state_schema_version: int
    rules_version: str
    rules_digest: str
    origin: str
    materialized: bool
    evaluation_fresh: bool
    code_version: str
    config_digest: str
    raw_revision: Optional[int]
    evaluated_at: datetime
    metrics: Mapping[str, Optional[float]]
    snapshot: Mapping[str, Any]
    feature_digest: str
    snapshot_digest: str


@dataclass(frozen=True)
class RuleEvaluation:
    event_type: str
    status: str                 # QUALIFIES | NOT_QUALIFIES | NOT_EVALUABLE
    streak: int                 # consecutive qualifying buckets ending at this bucket
    reason: str
    detail: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Episode:
    episode_pk: Optional[int]
    public_id: str
    symbol: str
    event_type: str
    state: str
    opened_bucket: datetime
    opened_at: datetime
    armed_at: Optional[datetime]
    triggered_at: Optional[datetime]
    terminal_at: Optional[datetime]
    terminal_reason: Optional[str]
    rules_version: str
    rules_digest: str
    code_version: str
    calculation_version: str
    opening_tape_digest: str
    trigger_tape_digest: Optional[str]
    last_bucket: datetime
    last_streak: int
    reference_price: Optional[float] = None
    reference_exchanges: tuple = ()
    reference_dispersion_pct: Optional[float] = None
    reference_bucket: Optional[datetime] = None
    correction_flag: bool = False
    correction_note: Optional[str] = None
