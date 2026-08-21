"""
Immutable V2 episode-event persistence model (Multi-model Framework PR 2,
docs/FORECASTING_ROADMAP.md §I stage 2).

`V2EpisodeEvent` is a PERSISTENCE EVENT MODEL, not a state machine. It
represents one already-decided, immutable historical event a future Episode
State Machine (a later PR) will construct and hand to the storage layer. This
module validates and freezes that event; it never decides whether the event
should exist, what state it should transition to, or how a
setup detector's `structural_anchor` is computed.

This is the durable-persistence boundary
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §2.1 requires: "V2 episode
events MUST follow the [V1 `ForecastPrediction`] pattern — every persisted
episode event embeds the exact feature values (by value, not by
reference/foreign key alone) it decided from." `decision_snapshot` and
`event_payload` are that by-value embedding; both are deeply frozen so a
caller cannot mutate what has already been "decided" out from under a
constructed event, and a later upstream feature-layer correction can never
reach back and rewrite an already-persisted event's own recorded values.

Pure only: no DB, network, filesystem access — and, deliberately, **no
clock, no `uuid`, no `random`**. `run_id`, `event_id`, `episode_id`, and
`decision_boundary` are all caller-supplied; the future Episode State
Machine owns their deterministic generation. This module only validates and
freezes what it is given.
"""
from __future__ import annotations

import math
from collections.abc import Mapping as _AbcMapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, Mapping

from analytics.forecasting_v2._validation import (
    SUPPORTED_MARKET_TYPE, SUPPORTED_SYMBOL, nonblank, one_of,
    validate_calculation_version, validate_config_hash,
    validate_feature_schema_version, validate_market_type, validate_symbol,
)
from common.v2_config import MODEL_FAMILY, validate_rules_version

__all__ = [
    "V2EventInputError",
    "RUN_KINDS", "LIVE", "REPLAY",
    "DIRECTIONS", "LONG", "SHORT",
    "SETUP_FAMILIES", "TREND_PULLBACK", "COMPRESSION_BREAKOUT", "CONFIRMED_BREAKOUT",
    "EPISODE_STATES",
    "SUPPORTED_SYMBOL", "SUPPORTED_MARKET_TYPE",
    "V2EpisodeEvent",
]


class V2EventInputError(ValueError):
    """Malformed V2EpisodeEvent input: bad identity, unsupported scope, an
    invalid enum value, a non-Mapping snapshot/payload, or an unsupported
    nested value inside one. Never silently coerced."""


# ---- run provenance (§2.1: live decision truth vs. replay research truth) --
LIVE = "LIVE"
REPLAY = "REPLAY"
RUN_KINDS = (LIVE, REPLAY)

# ---- episode logical dimensions (§12) ---------------------------------------
LONG = "LONG"
SHORT = "SHORT"
DIRECTIONS = (LONG, SHORT)   # V2 episodes are never NEUTRAL — unlike V1 predictions

TREND_PULLBACK = "TREND_PULLBACK"
COMPRESSION_BREAKOUT = "COMPRESSION_BREAKOUT"
CONFIRMED_BREAKOUT = "CONFIRMED_BREAKOUT"
SETUP_FAMILIES = (TREND_PULLBACK, COMPRESSION_BREAKOUT, CONFIRMED_BREAKOUT)

# ---- episode lifecycle states (§13.2) ---------------------------------------
# REVERSAL_CANDIDATE is deliberately absent: per §13.3 it is a cross-cutting
# event attached to an existing episode's history, never the episode's own
# `episode_state` — V2_PRODUCT_CONTRACT.md §5.1 states this explicitly
# ("not a primary persisted state that replaces or supersedes the original
# episode's own state"). A future event representing it belongs in
# `event_payload`, not in this CHECK-constrained column.
EARLY_SIGNAL = "EARLY_SIGNAL"
CONFIRMED = "CONFIRMED"
WEAKENING = "WEAKENING"
INVALIDATED = "INVALIDATED"
EXPIRED = "EXPIRED"
COMPLETED = "COMPLETED"
EPISODE_STATES = (EARLY_SIGNAL, CONFIRMED, WEAKENING, INVALIDATED, EXPIRED, COMPLETED)

# ---- initial V2 scope (V2_PRODUCT_CONTRACT.md §1: "Symbol: BTCUSDT... USDT
# perpetual") — SUPPORTED_SYMBOL/SUPPORTED_MARKET_TYPE are imported above
# from the shared _validation module (bound at module level by that import
# statement, and re-exported here via __all__) so both V2 value objects
# (this event model and provenance.py's V2EventProvenance) pin the
# identical constants without either importing from
# analytics/forecasting/models.py (V1-owned).


def _deep_freeze(value: Any, name: str) -> Any:
    """Recursively convert a JSON-compatible structure into a deeply
    immutable form (MappingProxyType / tuple), rejecting anything that is
    not a JSON-compatible shape. This is the "by value" enforcement §2.1
    requires: once frozen, no caller-held reference to a nested dict/list can
    mutate what this event recorded.

    Leaf validation is aligned with the canonical serializer
    (`storage/stage2_serialization.py`'s `to_jsonable`) so a malformed leaf
    fails HERE, at `V2EpisodeEvent` construction, rather than surviving
    construction and only failing later at `serialize_batch()` time:
      - `bool`/`str`/`int`/`None` pass through unchanged.
      - `float` must be finite — NaN/+Inf/-Inf are rejected.
      - `datetime` must be timezone-aware with a zero UTC offset — a naive
        or non-UTC datetime is rejected, never silently normalized.
    `bool` is checked before `float`/`int` only because it is a subclass of
    `int` in Python; the acceptance behavior itself does not depend on the
    check order."""
    if isinstance(value, _AbcMapping):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise V2EventInputError(
                    f"{name}: mapping keys must be str, got {type(k).__name__}: {k!r}")
            out[k] = _deep_freeze(v, f"{name}.{k}")
        return MappingProxyType(out)
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(v, f"{name}[]") for v in value)
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise V2EventInputError(
                f"{name}: non-finite float is not allowed in a JSON leaf "
                f"(NaN/+Inf/-Inf), got {value!r}")
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise V2EventInputError(
                f"{name}: datetime must be timezone-aware, got naive {value!r}")
        if value.utcoffset() != timedelta(0):
            raise V2EventInputError(
                f"{name}: datetime must be UTC (offset 0), got {value!r} "
                f"(offset {value.utcoffset()})")
        return value
    raise V2EventInputError(
        f"{name}: unsupported value of type {type(value).__name__} "
        "(only JSON-compatible mappings/lists/str/int/float/bool/None/datetime "
        "are allowed in a by-value snapshot/payload)")


def _validate_json_object(value: Any, name: str) -> Mapping:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, _AbcMapping):
        raise V2EventInputError(
            f"{name} must be a Mapping (JSON object), got {type(value).__name__}")
    return _deep_freeze(value, name)


def _validate_decision_boundary(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise V2EventInputError(
            f"decision_boundary must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2EventInputError("decision_boundary must be timezone-aware")
    if value.utcoffset() != timedelta(0):
        raise V2EventInputError(f"decision_boundary must be UTC (offset 0), got {value.utcoffset()}")
    # Deliberately NO grid-alignment check here (e.g. "must land on a 5m/15m
    # boundary") — selected_bucket()/decision_boundary() mechanics belong to
    # the later Multi-timeframe Alignment stage, not this persistence PR.
    return value


@dataclass(frozen=True)
class V2EpisodeEvent:
    """Deeply-immutable, self-validating V2 episode event — one already-decided
    historical fact, ready to persist. Its field set equals the
    `v2_episode_events` columns EXCEPT the DB-owned `created_at`.

    Field groups:
      - run provenance (§2.1): `run_kind`, `run_id`, `event_id`, `episode_id` —
        `(run_kind, run_id, event_id)` is the storage identity
        (`storage/v2_serialization.py`); LIVE and REPLAY runs, or two
        distinct REPLAY runs, can carry the same `event_id` without
        colliding, because `run_id` namespaces them apart.
      - model/version identity (§3): `model_family` (always exactly `"v2"`),
        `rules_version` (validated against the frozen
        `v2-rules-v<major>.<minor>.<patch>` namespace via
        `common.v2_config.validate_rules_version` — the same validator
        `common/v2_config.py` itself uses, never a second competing regex).
      - episode logical dimensions (§12): `symbol`, `market_type`,
        `direction`, `setup_family`, `structural_anchor` — together these
        (minus `structural_anchor`'s own internal identity role) form
        `episode_logical_key`. `structural_anchor` is stored **by value**,
        exactly as the (future) detector computed it — this model never
        computes or validates its internal shape beyond "is a JSON object."
      - lifecycle position (§13.2): `episode_state` — one of the six actual
        lifecycle states. `REVERSAL_CANDIDATE` is deliberately not a legal
        value here (see `EPISODE_STATES`'s comment).
      - `decision_boundary` — logical decision time, never wall-clock
        insertion time.
      - shared Stage 2 provenance (§3): `feature_schema_version`,
        `calculation_version`, `config_hash`, `config_version`,
        `code_version` — recorded as supplied, never recomputed here.
      - decision-code provenance (§3.2, V2-H3): `decision_code_version` —
        the Stage 4/5/6 DECISION-code identity §3.2 requires captured BY
        VALUE on every persisted V2 decision/event, kept deliberately
        distinct from `code_version` above (Stage 2's FEATURE-computation-
        code identity). Deliberately EXCLUDED from `episode_identity.py`'s
        `episode_id`/`event_id` derivation (docs/V2_CORRECTNESS_
        ACCEPTANCE_CONTRACT.md §2.1a's frozen field list omits it) — a
        Stage 6 code fix changing this value alone must not fork an
        episode's semantic identity; it is recorded here purely so
        historical truth can later prove which decision-code identity
        produced this event, never derived from current Git state at
        read time.
      - by-value historical truth (§2.1): `decision_snapshot` (what was
        decided FROM) and `event_payload` (what was decided/emitted) — both
        deeply frozen `Mapping`s. Neither is defined with a normative
        internal schema by this PR; later owning modules (context engines,
        detectors, the state machine) construct their exact contents
        according to their own already-frozen contracts.
    """
    run_kind: str
    run_id: str
    event_id: str
    episode_id: str

    model_family: str
    rules_version: str

    symbol: str
    market_type: str
    direction: str
    setup_family: str
    structural_anchor: Mapping

    episode_state: str
    decision_boundary: datetime

    feature_schema_version: int
    calculation_version: str
    config_hash: str
    config_version: str
    code_version: str
    decision_code_version: str

    decision_snapshot: Mapping
    event_payload: Mapping

    def __post_init__(self):
        one_of(self.run_kind, "run_kind", RUN_KINDS, V2EventInputError)
        nonblank(self.run_id, "run_id", V2EventInputError)
        nonblank(self.event_id, "event_id", V2EventInputError)
        nonblank(self.episode_id, "episode_id", V2EventInputError)

        if self.model_family != MODEL_FAMILY:
            raise V2EventInputError(
                f"model_family must be exactly {MODEL_FAMILY!r}, got {self.model_family!r}")
        try:
            validate_rules_version(self.rules_version)
        except ValueError as exc:
            raise V2EventInputError(str(exc)) from exc

        validate_symbol(self.symbol, V2EventInputError)
        validate_market_type(self.market_type, V2EventInputError)
        one_of(self.direction, "direction", DIRECTIONS, V2EventInputError)
        one_of(self.setup_family, "setup_family", SETUP_FAMILIES, V2EventInputError)
        object.__setattr__(
            self, "structural_anchor",
            _validate_json_object(self.structural_anchor, "structural_anchor"))

        one_of(self.episode_state, "episode_state", EPISODE_STATES, V2EventInputError)
        object.__setattr__(
            self, "decision_boundary", _validate_decision_boundary(self.decision_boundary))

        validate_feature_schema_version(self.feature_schema_version, V2EventInputError)
        validate_calculation_version(self.calculation_version, V2EventInputError)
        validate_config_hash(self.config_hash, V2EventInputError)
        nonblank(self.config_version, "config_version", V2EventInputError)
        nonblank(self.code_version, "code_version", V2EventInputError)
        nonblank(self.decision_code_version, "decision_code_version", V2EventInputError)

        object.__setattr__(
            self, "decision_snapshot",
            _validate_json_object(self.decision_snapshot, "decision_snapshot"))
        object.__setattr__(
            self, "event_payload",
            _validate_json_object(self.event_payload, "event_payload"))
