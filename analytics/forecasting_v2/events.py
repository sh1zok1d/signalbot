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

import re
from collections.abc import Mapping as _AbcMapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, Mapping

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
# perpetual") — frozen locally, deliberately NOT imported from
# analytics/forecasting/models.py's SUPPORTED_SYMBOL/SUPPORTED_MARKET_TYPE:
# V1's shadow scope and V2's product scope are independently declared and
# must be able to diverge without coupling one module's constant to the
# other's.
SUPPORTED_SYMBOL = "BTCUSDT"
SUPPORTED_MARKET_TYPE = "perp"

# Shared Stage 2 identity formats (common/versioning.py): calculation_version
# is sha256(...)[:16] hex, config_hash is a full sha256 hex digest. Same
# convention analytics/forecasting/models.py already validates against for
# V1 — re-stated locally (not imported) so V2's own identity validation does
# not depend on a V1-owned module.
_HEX16 = re.compile(r"[0-9a-f]{16}")
_HEX64 = re.compile(r"[0-9a-f]{64}")

_JSON_LEAF_TYPES = (str, int, float, bool, type(None), datetime)


def _nonblank(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise V2EventInputError(f"{name} must be a non-empty string")
    return value


def _one_of(value: Any, name: str, allowed: tuple) -> str:
    if value not in allowed:
        raise V2EventInputError(f"{name} must be one of {allowed}, got {value!r}")
    return value


def _deep_freeze(value: Any, name: str) -> Any:
    """Recursively convert a JSON-compatible structure into a deeply
    immutable form (MappingProxyType / tuple), rejecting anything that is
    not a JSON-compatible shape. This is the "by value" enforcement §2.1
    requires: once frozen, no caller-held reference to a nested dict/list can
    mutate what this event recorded. Booleans/ints/floats/strings/None and
    tz-aware datetimes pass through unchanged as leaves (bool is checked via
    isinstance before int, matching storage/stage2_serialization.py's own
    `to_jsonable` ordering, though bool IS accepted here — only isinstance
    checks care about the ordering, not acceptance)."""
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
    if isinstance(value, _JSON_LEAF_TYPES):
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

    decision_snapshot: Mapping
    event_payload: Mapping

    def __post_init__(self):
        _one_of(self.run_kind, "run_kind", RUN_KINDS)
        _nonblank(self.run_id, "run_id")
        _nonblank(self.event_id, "event_id")
        _nonblank(self.episode_id, "episode_id")

        if self.model_family != MODEL_FAMILY:
            raise V2EventInputError(
                f"model_family must be exactly {MODEL_FAMILY!r}, got {self.model_family!r}")
        try:
            validate_rules_version(self.rules_version)
        except ValueError as exc:
            raise V2EventInputError(str(exc)) from exc

        if self.symbol != SUPPORTED_SYMBOL:
            raise V2EventInputError(
                f"unsupported symbol {self.symbol!r} (V2 initial scope is {SUPPORTED_SYMBOL!r})")
        if self.market_type != SUPPORTED_MARKET_TYPE:
            raise V2EventInputError(
                f"unsupported market_type {self.market_type!r} "
                f"(V2 initial scope is {SUPPORTED_MARKET_TYPE!r})")
        _one_of(self.direction, "direction", DIRECTIONS)
        _one_of(self.setup_family, "setup_family", SETUP_FAMILIES)
        object.__setattr__(
            self, "structural_anchor",
            _validate_json_object(self.structural_anchor, "structural_anchor"))

        _one_of(self.episode_state, "episode_state", EPISODE_STATES)
        object.__setattr__(
            self, "decision_boundary", _validate_decision_boundary(self.decision_boundary))

        if not isinstance(self.feature_schema_version, int) \
                or isinstance(self.feature_schema_version, bool) \
                or self.feature_schema_version <= 0:
            raise V2EventInputError("feature_schema_version must be an int > 0")
        if not isinstance(self.calculation_version, str) or not _HEX16.fullmatch(self.calculation_version):
            raise V2EventInputError("calculation_version must be exactly 16 lowercase hex chars")
        if not isinstance(self.config_hash, str) or not _HEX64.fullmatch(self.config_hash):
            raise V2EventInputError("config_hash must be exactly 64 lowercase hex chars")
        _nonblank(self.config_version, "config_version")
        _nonblank(self.code_version, "code_version")

        object.__setattr__(
            self, "decision_snapshot",
            _validate_json_object(self.decision_snapshot, "decision_snapshot"))
        object.__setattr__(
            self, "event_payload",
            _validate_json_object(self.event_payload, "event_payload"))
