"""
Stage 6 Unit 1/5 — episode identity + persisted-history read foundation
(`docs/FORECASTING_ROADMAP.md` §I stage 6 unit 1;
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §12.1/§12.2/§12.2a/§12.5/
§12.5a/§12.10/§13.4).

**What this module is.** The pure, immutable DOMAIN half of Stage 6's
persisted-history foundation: it turns already-read `v2_episode_events`
rows into one validated, deeply-frozen `V2EpisodeHistory` — an existing
episode's ordered event history, its immutable creation identity, and its
persisted lifecycle position as of one logical decision boundary `T`. The
concrete PostgreSQL reads live in `storage/v2_episode_history_readers.py`;
the structural port future Stage 6 units depend on is
`ports.py::V2EpisodeHistoryReader`.

**The invariant this module exists to enforce.** For an episode that
ALREADY EXISTS, Stage 6 must never reconstruct creation identity from a
current Stage 5 detector candidate:

    persisted EARLY_SIGNAL creation event
        -> immutable creation identity
        -> all later Stage 6 decisions

never:

    current Stage 5 candidate -> recompute existing episode identity

`V2EpisodeCreationIdentity` is that authoritative reconstruction. Every
field on it comes from persisted history; nothing on it is derived from
"now", from current instrument metadata, or from a fresh candidate.

**What this module is NOT.** It takes no lifecycle decision. It does not
classify candidates, arbitrate family precedence, decide `EARLY_SIGNAL`
creation, evaluate same-slot suppression, compute cooldown eligibility for
a new candidate, confirm, expire, weaken, invalidate, or complete anything
(Stage 6 units 2-5). `current_state` below is a READ of what was already
persisted, never a decision about what happens next. It also never
CONSTRUCTS a `V2EpisodeEvent`: `event_factory.py::build_v2_episode_event()`
remains the one canonical construction path, and this module is on the
read side of it.

**Deterministic identity is REUSED, never re-implemented.**
`episode_identity.py`'s `compute_episode_id()`/`compute_event_id()` are the
only hashing in play; this module imports and calls them to REVALIDATE
persisted rows (see "Integrity revalidation" below) and never contains a
second hash, canonical JSON, UUID, clock, sequence, `hash()`, or `repr()`
based identity path.

**`t_create` is recovered, not stored separately.** `V2EpisodeEvent` has no
`t_create` column — deliberately, since `event_factory.py` requires
`t_create` as an INPUT and folds it into `episode_id`. It is recovered from
history exactly as the contract defines it: `t_create` IS the
`decision_boundary` of the episode's own creation event
(`event_factory.py`: "For the episode's own creation event, `t_create ==
decision_boundary`").

**The creation event is identified by POSITION, never by counting states**
(red-team finding RT-63-01). It is the OLDEST persisted event of the
episode, and it must be `EARLY_SIGNAL` — an episode cannot have history
before its own creation, so an older non-`EARLY_SIGNAL` event means
`t_create` is unrecoverable and the history is corrupt. It is emphatically
NOT "the unique event whose state is `EARLY_SIGNAL`": §12.2a explicitly
allows a `TREND_PULLBACK` episode, WHILE STILL `EARLY_SIGNAL`, to record
each further material pre-confirmation update as "a **new**, immutable
history event", so a perfectly legal history can contain SEVERAL
`EARLY_SIGNAL` events. The episode is still created exactly once; "created
once" is a statement about position, not about how many events share a
state.

**Persisted state SEQUENCES are validated against §13.2** (RT-63-02).
Unit 1 takes no transition decision — it never asks whether the market
evidence justified a transition (Stage 6 units 3-5) — but it does reject a
recorded sequence that could not have happened: nothing may be persisted
after a terminal event (§13.2 gives `INVALIDATED`/`EXPIRED`/`COMPLETED` no
outgoing edges), and every state CHANGE must be one of §13.2's allowed
edges. A same-state event is not a change and is always allowed.

**Integrity revalidation, and why it lives HERE (not in the SQL reader).**
A persisted row existing is not proof it is coherent. Because every event of
one episode carries that episode's FROZEN creation facts (`direction`,
`setup_family`, `structural_anchor` — §12.2/§12.2a, enforced by
`event_factory.py`'s own required-parameter shape), the whole history is
self-checking: recomputing `compute_episode_id(...)` from the creation
facts plus the recovered `t_create` MUST reproduce the persisted
`episode_id`, and recomputing `compute_event_id(episode_id, boundary)` MUST
reproduce each persisted `event_id`. This defense is placed in this pure
analytics layer rather than in the storage reader on purpose: it is a
SEMANTIC invariant over a whole reconstructed history (it needs
`t_create`, which is only knowable after the creation event has been
identified across the full row set), it is fully testable with no database,
and keeping it here leaves the SQL layer a dumb, auditable projection.
`storage/v2_episode_history_readers.py` therefore validates only row SHAPE
and physical scope; everything semantic is validated exactly once, here.

**Missing history and corrupt history are different states.** An episode
with no rows in the requested `execution_stream`/`as_of` window yields
`None` from `reconstruct_episode_history()` — a legitimate "this stream has
not seen this episode (yet)" answer. A history that exists but cannot
possibly be true (creation identity drifting mid-episode, an
`episode_id`/`event_id` that does not match its own contents, two events at
one decision boundary, an event after the requested `as_of`, a foreign
execution stream) raises `V2EpisodeHistoryCorruptionError`. Corruption is
never silently repaired, never downgraded to `None`, and never returned as
a partially-usable history.

**`decision_code_version` deliberately MAY vary across one episode's
events.** §3.2 captures it BY VALUE per event, and `episode_identity.py`
excludes it from `episode_id` precisely so "a Stage 6 bug-fix release
changing `decision_code_version` alone must not fork the semantic identity
of an episode whose underlying market facts are unchanged." Rejecting a
history whose events carry different `decision_code_version` values would
therefore contradict a frozen contract decision, so this module explicitly
does NOT do that — while still requiring the SEMANTIC identity fields that
`episode_id` IS built from (`model_family`, `rules_version`,
`calculation_version`, `symbol`, `market_type`, `direction`,
`setup_family`, `structural_anchor`) to be byte-identical across every
event of one episode.

**Two same-`T` visibility modes, both frozen by §13.4, neither defaulted.**
§13.4's step 1 reconstructs "the episodes ACTIVE immediately before `T`
(the outcome of the previous decision boundary)" — a STRICTLY-BEFORE-`T`
view — while its step 3b's cooldown lookup explicitly INCLUDES an episode
that became terminal "at this very `T`" (`T_terminal = T` is "a valid,
immediately-effective value"). Those are genuinely different windows over
the same table, and picking one silently for every caller would guarantee
a wrong answer for the other. `HISTORY_BEFORE_T` and `HISTORY_THROUGH_T`
name them explicitly and `boundary_mode` is a REQUIRED argument everywhere
— this module invents no third convention and no default.

Pure only: no DB, network, filesystem, clock, `uuid`, or `random` access.
"""
from __future__ import annotations

import math
from collections.abc import Mapping as _AbcMapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from analytics.forecasting_v2._validation import (
    HEX64, nonblank, one_of, validate_calculation_version, validate_market_type,
    validate_symbol,
)
from analytics.forecasting_v2.alignment import V2AlignmentError, selected_bucket
from analytics.forecasting_v2.episode_identity import compute_episode_id, compute_event_id
from analytics.forecasting_v2.events import (
    COMPLETED, COMPRESSION_BREAKOUT, CONFIRMED_BREAKOUT, DIRECTIONS,
    EARLY_SIGNAL, EPISODE_STATES, EXPIRED, INVALIDATED, RUN_KINDS,
    SETUP_FAMILIES, TREND_PULLBACK,
)
from common.v2_config import MODEL_FAMILY, validate_rules_version

__all__ = [
    "V2EpisodeHistoryError", "V2EpisodeHistoryCorruptionError",
    "HISTORY_BEFORE_T", "HISTORY_THROUGH_T", "HISTORY_BOUNDARY_MODES",
    "TERMINAL_EPISODE_STATES", "NON_TERMINAL_EPISODE_STATES",
    "ANCHOR_BUCKET_TS", "ANCHOR_LEVEL_TICK_INDEX", "ANCHOR_LEVEL_NORMALIZED_PRICE",
    "CREATION_IDENTITY_TICK_SIZE",
    "normalize_price_to_tick", "canonical_decimal_text",
    "build_trend_pullback_anchor", "build_compression_breakout_anchor",
    "build_confirmed_breakout_anchor",
    "V2PersistedEpisodeEvent", "V2EpisodeCreationIdentity", "V2EpisodeHistory",
    "reconstruct_episode_history",
]


class V2EpisodeHistoryError(ValueError):
    """Malformed input to episode-history reconstruction: a bad
    execution-stream/episode scope, an unsupported `boundary_mode`, a
    non-Mapping row, or a malformed tick-normalization input. Never
    silently coerced."""


class V2EpisodeHistoryCorruptionError(V2EpisodeHistoryError):
    """Persisted history that exists but cannot possibly be true — creation
    identity drifting mid-episode, an `episode_id`/`event_id` inconsistent
    with its own contents, two events at one decision boundary, an event
    past the requested `as_of`, or a foreign execution stream leaking into
    the result.

    Deliberately a SUBCLASS of `V2EpisodeHistoryError` (so a caller may
    fail closed on either with one `except`) but a DISTINCT type, so
    "this episode has no history here" (`None`), "you asked me something
    malformed" (`V2EpisodeHistoryError`), and "the database contains an
    impossible history" (this) are three separable outcomes and never one
    ambiguous `None`."""


# ---- §13.4 same-boundary visibility modes ----------------------------------
# Named, frozen, and never defaulted -- see module docstring. HISTORY_BEFORE_T
# is §13.4 step 1's "ACTIVE immediately before T"; HISTORY_THROUGH_T is the
# window step 3b's cooldown lookup needs, where an episode that became
# terminal at this very T is explicitly still in scope.
HISTORY_BEFORE_T = "BEFORE_T"
HISTORY_THROUGH_T = "THROUGH_T"
HISTORY_BOUNDARY_MODES = (HISTORY_BEFORE_T, HISTORY_THROUGH_T)

# ---- §13.2 terminal vs non-terminal lifecycle position ----------------------
# A READ-side classification of an ALREADY-PERSISTED state, not a transition
# rule: Stage 6 units 3-5 own which transitions may occur. INVALIDATED/
# EXPIRED/COMPLETED are §12.8's three terminal states verbatim.
# Bound to `events.py`'s own constants (never re-spelled as string
# literals) so a rename there breaks at import here, not silently at
# runtime; the assertion below pins them to the real state enum.
TERMINAL_EPISODE_STATES = (INVALIDATED, EXPIRED, COMPLETED)
NON_TERMINAL_EPISODE_STATES = tuple(
    s for s in EPISODE_STATES if s not in TERMINAL_EPISODE_STATES)
assert set(TERMINAL_EPISODE_STATES) <= set(EPISODE_STATES)

# ---- canonical persisted `structural_anchor` JSON keys ----------------------
# §12.5a freezes the required logical FACTS but explicitly "does not
# prescribe a physical JSON key/schema for it (that remains implementation
# work, per §0.1)". Stage 6 Unit 1 is that implementation work: these are the
# canonical keys, defined ONCE here so units 2-5 never hand-read raw JSON
# with ad-hoc string literals and never disagree about spelling.
ANCHOR_BUCKET_TS = "bucket_ts"
ANCHOR_LEVEL_TICK_INDEX = "level_tick_index"
ANCHOR_LEVEL_NORMALIZED_PRICE = "level_normalized_price"
CREATION_IDENTITY_TICK_SIZE = "creation_identity_tick_size"


# ============================================================================
# §12.5 tick normalization (exact Decimal, never binary float)
# ============================================================================
def _to_decimal(value: Any, name: str) -> Decimal:
    """`Decimal(str(x))` per §12.5's explicit requirement -- "String
    construction (`Decimal(str(x))`) is required specifically to avoid
    binary float artifacts that `Decimal(x)` on a `float` would otherwise
    introduce." A `bool` is rejected outright (it is an `int` subclass in
    Python and is never a legitimate price/tick)."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise V2EpisodeHistoryError(
            f"{name} must be a real number (int/float/str/Decimal), got {type(value).__name__}")
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise V2EpisodeHistoryError(f"{name}: not a valid decimal: {value!r}") from exc
    if not dec.is_finite():
        raise V2EpisodeHistoryError(f"{name} must be finite, got {value!r}")
    if dec <= 0:
        raise V2EpisodeHistoryError(f"{name} must be strictly positive, got {value!r}")
    return dec


def normalize_price_to_tick(raw_price: Any, tick_size: Any) -> "tuple[int, Decimal]":
    """§12.5's frozen normalization, verbatim:

        price_decimal = Decimal(str(raw_level_price))
        tick_decimal  = Decimal(str(tick_size))
        tick_index    = (price_decimal / tick_decimal) rounded ROUND_HALF_UP
        normalized_level_price = tick_index * tick_decimal

    Returns `(tick_index, normalized_level_price)`. `tick_index` is "the
    canonical equality identity for the normalized price (two prices are
    the 'same' tick iff their `tick_index` values are equal)";
    `normalized_level_price` is "its human-readable decimal equivalent."

    Never `round()` (binary-float, round-half-to-even) and never a
    `price % tick` float trick -- both are explicitly excluded by §12.5.
    Both inputs are always positive (§12.5) and are validated as such."""
    price_decimal = _to_decimal(raw_price, "raw_price")
    tick_decimal = _to_decimal(tick_size, "tick_size")
    try:
        tick_index = int(
            (price_decimal / tick_decimal).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        normalized = tick_index * tick_decimal
    except (ArithmeticError, ValueError) as exc:
        # An extreme but syntactically valid ratio can exceed the active
        # decimal context's precision/exponent range. `ArithmeticError` is
        # the common base of BOTH `decimal.DecimalException` (InvalidOperation,
        # Overflow, Underflow, ...) and the builtin `OverflowError`, so this
        # catches the whole family rather than an enumerated subset that a
        # different extreme input could slip past. That is an
        # out-of-supported-domain input, not a contract change: surface it
        # inside this module's own error hierarchy (chained), never as a raw
        # decimal exception.
        raise V2EpisodeHistoryError(
            f"tick normalization of raw_price={raw_price!r} against tick_size={tick_size!r} "
            f"exceeds exact decimal evaluation: {type(exc).__name__}: {exc}") from exc
    if tick_index < 1:
        # §12.5's inputs "are always positive", so the normalized result is a
        # positive PRICE too. A ratio small enough to round down to the zero
        # tick (raw_price < tick_size/2, or an extreme underflowing pair)
        # would mint a degenerate zero-priced identity; reject it at the
        # source rather than let it reach structural_anchor/episode_id.
        raise V2EpisodeHistoryError(
            f"tick normalization of raw_price={raw_price!r} against tick_size={tick_size!r} "
            f"yields tick_index={tick_index}, i.e. a normalized price of zero -- a structural "
            "level price is always strictly positive (§12.5)")
    return tick_index, normalized


# ============================================================================
# canonical per-family `structural_anchor` construction (§12.1)
# ============================================================================
def _validate_utc(value: Any, name: str) -> datetime:
    """UTC-awareness only. Never sufficient on its own for a decision
    boundary or a family anchor — see the two grid validators below."""
    if not isinstance(value, datetime):
        raise V2EpisodeHistoryError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2EpisodeHistoryError(f"{name} must be timezone-aware, got naive {value!r}")
    if value.utcoffset() != timedelta(0):
        raise V2EpisodeHistoryError(
            f"{name} must be UTC (offset 0), got {value!r} (offset {value.utcoffset()})")
    return value


def _validate_decision_boundary_T(
    value: Any, name: str, *, error_cls: type = V2EpisodeHistoryError,
) -> datetime:
    """A legal V2 5m DECISION BOUNDARY `T`, not merely a UTC instant.

    `as_of` and every persisted event's `decision_boundary` are logical
    Stage 6 decision boundaries, so an arbitrary wall-clock UTC value
    (`12:03:00`, `12:10:01`, `12:10:00.5`) is malformed input, never a
    usable window edge. Delegated to `alignment.selected_bucket("5m", ...)`
    — the same canonical source of truth `episode_identity.py`/
    `decision_provenance.py`/`version_switch.py` already use — never a
    locally-duplicated minute arithmetic reimplementation.

    `error_cls` lets one call site raise the corruption subclass instead:
    an off-grid boundary supplied BY A CALLER is malformed input, while an
    off-grid boundary read back OUT OF STORAGE is impossible history."""
    v = _validate_utc(value, name) if error_cls is V2EpisodeHistoryError else value
    if error_cls is not V2EpisodeHistoryError:
        if not isinstance(v, datetime):
            raise error_cls(f"{name} must be a datetime, got {type(v).__name__}")
        if v.tzinfo is None or v.utcoffset() is None or v.utcoffset() != timedelta(0):
            raise error_cls(f"{name} must be a UTC-aware datetime, got {v!r}")
    try:
        selected_bucket("5m", v)
    except V2AlignmentError as exc:
        raise error_cls(f"{name} is not a legal V2 5m decision boundary: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - malformed/adversarial tzinfo, never leaked raw
        raise error_cls(
            f"{name} failed decision-boundary validation: {type(exc).__name__}: {exc}") from exc
    return v


_TIMEFRAME_DELTAS = MappingProxyType({
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
})

# §12.1's per-family anchor grid, in ONE place: the canonical builders below
# and the persisted-history validator both resolve the timeframe from here,
# so construction and reconstruction can never disagree about which grid a
# family's `structural_anchor.bucket_ts` lives on.
_FAMILY_ANCHOR_TIMEFRAME = MappingProxyType({
    TREND_PULLBACK: "15m",          # the 15m bucket establishing trend_leg_extreme
    COMPRESSION_BREAKOUT: "15m",    # the first 15m bucket of the compression window
    CONFIRMED_BREAKOUT: "1h",       # the 1h extreme defining the broken level
})
assert set(_FAMILY_ANCHOR_TIMEFRAME) == set(SETUP_FAMILIES)


def _validate_bucket_start(value: Any, name: str, *, timeframe: str) -> datetime:
    """A legal EXACT bucket START on the canonical V2 `timeframe` grid.

    Reuses `alignment.selected_bucket()`'s own round-trip technique
    verbatim — `value` is a legal `<tf>` bucket start iff selecting the
    `<tf>` bucket for `T = value + <tf>` round-trips back to `value` —
    exactly as `compression_breakout.py::_validate_15m_bucket_start` and
    `confirmed_breakout.py::_validate_1h_bucket_start` already do for the
    identical question. No second grid convention, no local minute
    arithmetic."""
    v = _validate_utc(value, name)
    if v.second or v.microsecond:
        raise V2EpisodeHistoryError(
            f"{name} must be a whole minute, got {v!r}")
    try:
        canonical = selected_bucket(timeframe, v + _TIMEFRAME_DELTAS[timeframe])
    except V2AlignmentError as exc:
        raise V2EpisodeHistoryError(
            f"{name} is not a legal {timeframe} bucket start: {exc}") from exc
    if canonical != v:
        raise V2EpisodeHistoryError(
            f"{name}={v.isoformat()!r} is not aligned to the canonical {timeframe} bucket grid "
            f"(the containing {timeframe} bucket starts at {canonical.isoformat()!r})")
    return v


def canonical_decimal_text(value: Decimal, name: str = "value") -> str:
    """The ONE canonical plain-decimal textual form of an exact `Decimal`.

    `structural_anchor` participates directly in `compute_episode_id()`, so
    two economically IDENTICAL creation facts must produce byte-identical
    text or they would fork the episode's permanent semantic identity for
    no reason but formatting. `str(Decimal(...))` does not satisfy that:
    `Decimal("0.1")`, `Decimal("0.10")` and `Decimal("1E-1")` are all
    numerically equal yet stringify as `'0.1'`, `'0.10'` and `'0.1'`, and
    `Decimal("1E+2")` stringifies in scientific notation as `'1E+2'`.

    Canonical form: `normalize()` collapses equal values to one exponent,
    then trailing-zero/scientific artifacts are removed — plain decimal
    notation, no exponent, no insignificant trailing fractional zeros,
    deterministic and lossless (no float ever involved). `Decimal("0.1")`,
    `Decimal("0.10")`, `Decimal("1E-1")` -> `'0.1'`; `Decimal("100")`,
    `Decimal("100.0")`, `Decimal("1E2")` -> `'100'`."""
    if not isinstance(value, Decimal):
        raise V2EpisodeHistoryError(
            f"{name} must be a Decimal, got {type(value).__name__}")
    if not value.is_finite():
        raise V2EpisodeHistoryError(f"{name} must be finite, got {value!r}")
    normalized = value.normalize()
    sign, digits, exponent = normalized.as_tuple()
    if exponent > 0:
        # normalize() pushes trailing integer zeros into a positive
        # exponent (Decimal("100") -> 1E+2); re-expand so the canonical
        # text is always plain notation.
        normalized = normalized.quantize(Decimal(1))
    text = format(normalized, "f")
    return "-0" if text == "-0" and not any(digits) else text


def build_trend_pullback_anchor(*, bucket_ts: datetime) -> Mapping:
    """§12.1's `TREND_PULLBACK` anchor: "the `bucket_ts` of the 15m bucket
    establishing `trend_leg_extreme`". The Stage 5 detector exposes that
    fact as a bare `datetime`
    (`trend_pullback.py::V2TrendPullbackCandidate.structural_anchor`);
    `compute_episode_id()` requires a JSON object. This is the canonical
    wrapping of one into the other -- defined once, here, so no Stage 6
    unit invents a second spelling of the same anchor."""
    return MappingProxyType({ANCHOR_BUCKET_TS: _validate_bucket_start(
        bucket_ts, "bucket_ts",
        timeframe=_FAMILY_ANCHOR_TIMEFRAME[TREND_PULLBACK]).isoformat()})


def build_compression_breakout_anchor(*, bucket_ts: datetime) -> Mapping:
    """§12.1's `COMPRESSION_BREAKOUT` anchor: "the `bucket_ts` of the first
    15m bucket in the qualifying compression window"
    (`compression_breakout.py`'s `compression_start_bucket`). Structurally
    identical shape to `TREND_PULLBACK`'s -- deliberately a SEPARATE named
    function rather than one shared "bucket anchor" helper, so a future
    per-family divergence changes one family's builder without silently
    changing the other's."""
    return MappingProxyType({ANCHOR_BUCKET_TS: _validate_bucket_start(
        bucket_ts, "bucket_ts",
        timeframe=_FAMILY_ANCHOR_TIMEFRAME[COMPRESSION_BREAKOUT]).isoformat()})


def build_confirmed_breakout_anchor(
    *, level_anchor_bucket: datetime, raw_level_price: Any,
    creation_identity_tick_size: Any,
) -> Mapping:
    """§12.1's `CONFIRMED_BREAKOUT` anchor -- "the `(bucket_ts, price)` of
    the 1h extreme defining the broken level, price **tick-normalized** per
    ... §12.5" -- plus §12.5a's `creation_identity_tick_size`, recorded BY
    VALUE in the same object.

    §12.5a requires exactly this: "`creation_identity_tick_size` (and the
    `tick_index`/`normalized_level_price` it produces) MUST be recorded BY
    VALUE in the episode's creation event/history, so that state
    reconstruction after a process restart never needs to re-read TODAY's
    instrument metadata to know what grid an existing active episode's
    identity was built on."

    `creation_identity_tick_size` is the validated reference-exchange
    `tick_size` KNOWN AT `T_create` — in practice the Stage 5 candidate's
    own `decision_tick_size`, which `confirmed_breakout.py` already carries
    by value for precisely this purpose. It is frozen here once and never
    re-derived.

    Persisted representation: `level_tick_index` is an exact JSON integer
    (§12.5's canonical equality identity, lossless), and both
    `level_normalized_price` and `creation_identity_tick_size` are stored
    as canonical DECIMAL STRINGS, never JSON floats — a float round-trip
    through JSONB would be exactly the binary-float artifact §12.5 forbids.
    `normalize_price_to_tick()` can therefore reproduce the identical
    `Decimal` grid from the persisted row alone, with no precision loss and
    no access to current instrument metadata."""
    bucket = _validate_bucket_start(
        level_anchor_bucket, "level_anchor_bucket",
        timeframe=_FAMILY_ANCHOR_TIMEFRAME[CONFIRMED_BREAKOUT])
    tick_decimal = _to_decimal(creation_identity_tick_size, "creation_identity_tick_size")
    tick_index, normalized = normalize_price_to_tick(raw_level_price, tick_decimal)
    return MappingProxyType({
        ANCHOR_BUCKET_TS: bucket.isoformat(),
        ANCHOR_LEVEL_TICK_INDEX: tick_index,
        ANCHOR_LEVEL_NORMALIZED_PRICE: canonical_decimal_text(
            normalized, ANCHOR_LEVEL_NORMALIZED_PRICE),
        CREATION_IDENTITY_TICK_SIZE: canonical_decimal_text(
            tick_decimal, CREATION_IDENTITY_TICK_SIZE),
    })


# ============================================================================
# immutable read-side value objects
# ============================================================================
def _deep_freeze_json(value: Any, name: str) -> Any:
    """Freeze one already-JSON-shaped value read back from storage.

    This is deliberately NOT a fourth competing freeze implementation: the
    storage reader (`storage/v2_episode_history_readers.py`) reuses the
    JSONB-detachment posture `storage/v2_setup_readers.py` already
    established, and this function is the ANALYTICS-side idempotent
    re-freeze applied to whatever a caller hands
    `reconstruct_episode_history()` (which may be a plain test dict, not a
    reader's already-frozen mapping). Same narrow leaf rules
    `events.py::_deep_freeze` uses, restated at this module's own boundary
    for values arriving from the read direction."""
    if isinstance(value, _AbcMapping):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise V2EpisodeHistoryError(
                    f"{name}: JSON object keys must be str, got {type(k).__name__}: {k!r}")
            out[k] = _deep_freeze_json(v, f"{name}.{k}")
        return MappingProxyType(out)
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze_json(v, f"{name}[]") for v in value)
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        # Mirrors events.py::_deep_freeze's identical write-side rule: a
        # non-finite float is not a legal JSON leaf and canonical persistence
        # can never have written one, so encountering one on the read path is
        # corrupt storage, never a value to pass through.
        if not math.isfinite(value):
            raise V2EpisodeHistoryError(
                f"{name}: non-finite float is not allowed in persisted JSON "
                f"(NaN/+Inf/-Inf), got {value!r}")
        return value
    if isinstance(value, datetime):
        return _validate_utc(value, name)
    raise V2EpisodeHistoryError(
        f"{name}: unsupported persisted JSON value of type {type(value).__name__}")


@dataclass(frozen=True)
class V2PersistedEpisodeEvent:
    """One already-persisted `v2_episode_events` row, deeply frozen.

    A READ-side mirror of `events.py::V2EpisodeEvent`, deliberately a
    distinct type rather than a reuse of it: `V2EpisodeEvent` is the WRITE
    model whose construction path is `build_v2_episode_event()` (which
    recomputes `episode_id`/`event_id` from inputs). Materializing rows read
    back from the database as `V2EpisodeEvent` would either bypass that
    canonical factory or silently recompute identity while pretending to
    report what storage actually holds — this type reports the persisted
    truth verbatim, and `reconstruct_episode_history()` separately proves
    that truth is self-consistent."""
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

    def __post_init__(self) -> None:
        # RT-63-07: the deep-immutability guarantee belongs to the TYPE, not
        # to one particular construction path. `frozen=True` only stops
        # rebinding the fields themselves; without this, a caller
        # constructing the dataclass directly could retain a live reference
        # to the nested dicts it passed in and mutate recorded history
        # afterwards. Freezing here means EVERY valid instance upholds the
        # contract its docstring states, however it was built.
        for field in ("structural_anchor", "decision_snapshot", "event_payload"):
            object.__setattr__(
                self, field, _deep_freeze_json(getattr(self, field), field))

    @property
    def is_terminal(self) -> bool:
        """Whether the state this event RECORDED is one of §12.8's three
        terminal states. A read of persisted fact, never a transition
        decision."""
        return self.episode_state in TERMINAL_EPISODE_STATES


@dataclass(frozen=True)
class V2EpisodeCreationIdentity:
    """An existing episode's IMMUTABLE creation identity, reconstructed
    exclusively from its persisted creation event.

    This is the type Stage 6 units 2-5 consume instead of re-deriving
    anything from a current detector candidate or from current instrument
    metadata. Everything here is fixed at `EARLY_SIGNAL` and never changes
    for the episode's life (§12.2); `structural_anchor` is the frozen
    §12.1 `episode_logical_key` anchor, and for `CONFIRMED_BREAKOUT` it
    additionally carries §12.5a's creation-time tick grid BY VALUE."""
    episode_id: str
    t_create: datetime

    model_family: str
    rules_version: str
    calculation_version: str

    symbol: str
    market_type: str
    direction: str
    setup_family: str
    structural_anchor: Mapping

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "structural_anchor",
            _deep_freeze_json(self.structural_anchor, "structural_anchor"))

    @property
    def slot(self) -> "tuple[str, str, str, str]":
        """§12.8's cooldown/occupancy `slot` — `(symbol, market_type,
        direction, setup_family)`, deliberately WITHOUT `structural_anchor`
        ("Cooldown scope remains the `slot` ... not the structural
        anchor"). Exposed as a plain comparable tuple; this module attaches
        no eligibility meaning to it (that is Stage 6 unit 2's job)."""
        return (self.symbol, self.market_type, self.direction, self.setup_family)

    @property
    def creation_identity_tick_size(self) -> Optional[Decimal]:
        """§12.5a's frozen creation-time tick grid, as an exact `Decimal`,
        for `CONFIRMED_BREAKOUT`; `None` for the two families that have no
        tick grid in their identity. Reconstructed from the persisted
        creation event only — never from today's instrument metadata."""
        raw = self.structural_anchor.get(CREATION_IDENTITY_TICK_SIZE)
        return None if raw is None else Decimal(str(raw))

    @property
    def creation_level_tick_index(self) -> Optional[int]:
        """§12.5's canonical equality identity for the creation-time
        normalized level price (`CONFIRMED_BREAKOUT` only), or `None`."""
        raw = self.structural_anchor.get(ANCHOR_LEVEL_TICK_INDEX)
        return None if raw is None else int(raw)

    @property
    def creation_normalized_level_price(self) -> Optional[Decimal]:
        """§12.5's human-readable normalized creation level as an exact
        `Decimal` (`CONFIRMED_BREAKOUT` only), or `None`."""
        raw = self.structural_anchor.get(ANCHOR_LEVEL_NORMALIZED_PRICE)
        return None if raw is None else Decimal(str(raw))


@dataclass(frozen=True)
class V2EpisodeHistory:
    """One existing episode's validated, deeply-immutable persisted history
    within exactly one `execution_stream` (§12.10), as of exactly one
    logical decision boundary under exactly one §13.4 visibility mode.

    `events` is the full ordered prefix visible under that window (oldest
    first, by `decision_boundary`); `creation_identity` is the immutable
    §12.2 creation identity; `current_state` is the persisted lifecycle
    position at the newest visible event. None of this decides what happens
    next."""
    run_kind: str
    run_id: str
    episode_id: str
    as_of: datetime
    boundary_mode: str
    events: "tuple[V2PersistedEpisodeEvent, ...]"
    creation_identity: V2EpisodeCreationIdentity

    def __post_init__(self) -> None:
        if isinstance(self.events, (str, bytes, bytearray)) or not isinstance(
                self.events, Sequence):
            raise V2EpisodeHistoryError(
                f"events must be a Sequence of V2PersistedEpisodeEvent, got "
                f"{type(self.events).__name__}")
        if not self.events:
            raise V2EpisodeHistoryError(
                "a V2EpisodeHistory always has at least its own creation event; an episode "
                "with no visible history is represented by None, never by an empty history")
        for index, event in enumerate(self.events):
            if not isinstance(event, V2PersistedEpisodeEvent):
                raise V2EpisodeHistoryError(
                    f"events[{index}] must be a V2PersistedEpisodeEvent, got "
                    f"{type(event).__name__}")
        object.__setattr__(self, "events", tuple(self.events))

    @property
    def creation_event(self) -> V2PersistedEpisodeEvent:
        """The episode's own `EARLY_SIGNAL` creation event. Always present
        and unambiguous — `reconstruct_episode_history()` refuses to build
        a history without exactly one, so no caller ever has to write
        `events[0]` and hope."""
        return self.events[0]

    @property
    def latest_event(self) -> V2PersistedEpisodeEvent:
        """The newest event visible under this history's own `as_of`/
        `boundary_mode` window."""
        return self.events[-1]

    @property
    def current_state(self) -> str:
        """The persisted `episode_state` as of this window — a PROJECTION
        of recorded history, never a decision about the next transition."""
        return self.latest_event.episode_state

    @property
    def is_terminal(self) -> bool:
        """Whether this episode is, as of this window, already in one of
        §12.8's three terminal states."""
        return self.latest_event.is_terminal

    @property
    def terminal_boundary(self) -> Optional[datetime]:
        """§12.8's `T_terminal` — "the decision boundary of the terminal
        event" — if this episode is terminal as of this window, else
        `None`. Exposed as the raw persisted FACT that §12.8's cooldown
        clock is computed FROM; this module deliberately does not compute
        the cooldown window or any eligibility from it (Stage 6 unit 2)."""
        return self.latest_event.decision_boundary if self.is_terminal else None


# ============================================================================
# validation + reconstruction
# ============================================================================
def _validate_boundary_mode(value: Any) -> str:
    return one_of(value, "boundary_mode", HISTORY_BOUNDARY_MODES, V2EpisodeHistoryError)


def _validate_episode_id(value: Any) -> str:
    nonblank(value, "episode_id", V2EpisodeHistoryError)
    if not HEX64.fullmatch(value):
        raise V2EpisodeHistoryError(
            "episode_id must be exactly 64 lowercase hex chars (a compute_episode_id() "
            f"output), got {value!r}")
    return value


def validate_episode_history_scope(
    *, run_kind: Any, run_id: Any, episode_id: Any, as_of: Any, boundary_mode: Any,
) -> None:
    """Validate one episode-history read's full scope BEFORE any I/O.

    Shared by this module and `storage/v2_episode_history_readers.py` (and
    through it `Database.fetch_v2_episode_history`) so the analytics and
    storage boundaries can never drift on what a legal scope is."""
    one_of(run_kind, "run_kind", RUN_KINDS, V2EpisodeHistoryError)
    nonblank(run_id, "run_id", V2EpisodeHistoryError)
    _validate_episode_id(episode_id)
    _validate_decision_boundary_T(as_of, "as_of")
    _validate_boundary_mode(boundary_mode)


_REQUIRED_ROW_FIELDS = (
    "run_kind", "run_id", "event_id", "episode_id",
    "model_family", "rules_version",
    "symbol", "market_type", "direction", "setup_family", "structural_anchor",
    "episode_state", "decision_boundary",
    "feature_schema_version", "calculation_version", "config_hash",
    "config_version", "code_version", "decision_code_version",
    "decision_snapshot", "event_payload",
)

# The frozen §12.2 creation-identity fields plus the semantic identity
# fields `compute_episode_id()` itself is built from -- every one of these
# MUST be byte-identical on every event of one episode.
# `decision_code_version` is deliberately ABSENT: see module docstring.
_EPISODE_INVARIANT_FIELDS = (
    "model_family", "rules_version", "calculation_version",
    "symbol", "market_type", "direction", "setup_family",
)


def _row_value(row: Mapping, field: str) -> Any:
    try:
        return row[field]
    except (KeyError, TypeError) as exc:
        raise V2EpisodeHistoryError(
            f"persisted episode-event row is missing required field {field!r}") from exc


def _to_persisted_event(row: Any, *, index: int) -> V2PersistedEpisodeEvent:
    """Convert ONE already-read row mapping into a frozen
    `V2PersistedEpisodeEvent`, validating shape/enums only. Cross-row
    semantic invariants are checked by `reconstruct_episode_history()`."""
    if isinstance(row, (str, bytes, bytearray)) or not isinstance(row, _AbcMapping):
        raise V2EpisodeHistoryError(
            f"episode-event row[{index}] must be a Mapping, got {type(row).__name__}")
    for field in _REQUIRED_ROW_FIELDS:
        _row_value(row, field)

    run_kind = one_of(_row_value(row, "run_kind"), "run_kind", RUN_KINDS, V2EpisodeHistoryError)
    episode_state = one_of(
        _row_value(row, "episode_state"), "episode_state", EPISODE_STATES, V2EpisodeHistoryError)
    direction = one_of(
        _row_value(row, "direction"), "direction", DIRECTIONS, V2EpisodeHistoryError)
    setup_family = one_of(
        _row_value(row, "setup_family"), "setup_family", SETUP_FAMILIES, V2EpisodeHistoryError)

    model_family = _row_value(row, "model_family")
    if model_family != MODEL_FAMILY:
        raise V2EpisodeHistoryError(
            f"model_family must be exactly {MODEL_FAMILY!r}, got {model_family!r}")
    rules_version = _row_value(row, "rules_version")
    try:
        validate_rules_version(rules_version)
    except ValueError as exc:
        raise V2EpisodeHistoryError(str(exc)) from exc

    event_id = nonblank(_row_value(row, "event_id"), "event_id", V2EpisodeHistoryError)
    if not HEX64.fullmatch(event_id):
        raise V2EpisodeHistoryError(
            f"event_id must be exactly 64 lowercase hex chars, got {event_id!r}")

    feature_schema_version = _row_value(row, "feature_schema_version")
    if type(feature_schema_version) is not int or feature_schema_version <= 0:
        raise V2EpisodeHistoryError(
            f"feature_schema_version must be a positive int, got {feature_schema_version!r}")

    return V2PersistedEpisodeEvent(
        run_kind=run_kind,
        run_id=nonblank(_row_value(row, "run_id"), "run_id", V2EpisodeHistoryError),
        event_id=event_id,
        episode_id=_validate_episode_id(_row_value(row, "episode_id")),
        model_family=model_family,
        rules_version=rules_version,
        symbol=validate_symbol(_row_value(row, "symbol"), V2EpisodeHistoryError),
        market_type=validate_market_type(_row_value(row, "market_type"), V2EpisodeHistoryError),
        direction=direction,
        setup_family=setup_family,
        structural_anchor=_require_json_object(
            _row_value(row, "structural_anchor"), "structural_anchor"),
        episode_state=episode_state,
        decision_boundary=_validate_utc(
            _row_value(row, "decision_boundary"), "decision_boundary"),
        feature_schema_version=feature_schema_version,
        calculation_version=validate_calculation_version(
            _row_value(row, "calculation_version"), V2EpisodeHistoryError),
        config_hash=nonblank(_row_value(row, "config_hash"), "config_hash", V2EpisodeHistoryError),
        config_version=nonblank(
            _row_value(row, "config_version"), "config_version", V2EpisodeHistoryError),
        code_version=nonblank(
            _row_value(row, "code_version"), "code_version", V2EpisodeHistoryError),
        decision_code_version=nonblank(
            _row_value(row, "decision_code_version"), "decision_code_version",
            V2EpisodeHistoryError),
        decision_snapshot=_require_json_object(
            _row_value(row, "decision_snapshot"), "decision_snapshot"),
        event_payload=_require_json_object(
            _row_value(row, "event_payload"), "event_payload"),
    )


def _require_json_object(value: Any, name: str) -> Mapping:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, _AbcMapping):
        raise V2EpisodeHistoryError(
            f"{name} must be a Mapping (JSON object), got {type(value).__name__}")
    return _deep_freeze_json(value, name)


# §13.2's frozen transition graph, verbatim ("No other edges are allowed").
# Keys/values are STATE-CHANGING edges only: a same-state event (A -> A) is
# NOT a lifecycle transition at all, it is a new event that leaves the
# episode in the state it was already in (§12.2a's pre-confirmation
# TREND_PULLBACK updates are exactly that), so it is never looked up here.
# The three terminal states are deliberately ABSENT as keys: §13.2 gives
# them no outgoing edges, so nothing may be persisted for the episode after
# one -- the fail-closed reading, since no frozen text permits it.
_LEGAL_STATE_EDGES = MappingProxyType({
    EARLY_SIGNAL: frozenset({"CONFIRMED", INVALIDATED, EXPIRED}),
    "CONFIRMED": frozenset({"WEAKENING", INVALIDATED, COMPLETED, EXPIRED}),
    "WEAKENING": frozenset({"CONFIRMED", INVALIDATED, COMPLETED, EXPIRED}),
})
assert set(_LEGAL_STATE_EDGES) | set(TERMINAL_EPISODE_STATES) == set(EPISODE_STATES)


def _assert_legal_state_sequence(
    events: "tuple[V2PersistedEpisodeEvent, ...]", *, episode_id: str,
) -> None:
    """Validate the recorded state SEQUENCE against §13.2's frozen graph.

    This is integrity validation of already-persisted history, NOT a
    lifecycle decision: it never asks whether the market evidence justified
    a transition (that is Stage 6 units 3-5), only whether the sequence of
    states that was actually written down could possibly have happened.

    Two rules:
      - nothing may be persisted after a TERMINAL event (§13.2 gives
        `INVALIDATED`/`EXPIRED`/`COMPLETED` no outgoing edges);
      - every state CHANGE must be one of §13.2's allowed edges. A
        same-state event is not a change and is always allowed."""
    for previous, current in zip(events, events[1:]):
        if previous.is_terminal:
            raise V2EpisodeHistoryCorruptionError(
                f"episode {episode_id!r} has an event at "
                f"{current.decision_boundary.isoformat()!r} persisted AFTER it reached the "
                f"terminal state {previous.episode_state!r} at "
                f"{previous.decision_boundary.isoformat()!r} -- §13.2 gives terminal states no "
                "outgoing transitions, so an episode's history ends there")
        if current.episode_state == previous.episode_state:
            continue        # a same-state event is not a transition (§12.2a)
        allowed = _LEGAL_STATE_EDGES[previous.episode_state]
        if current.episode_state not in allowed:
            raise V2EpisodeHistoryCorruptionError(
                f"episode {episode_id!r} records the transition "
                f"{previous.episode_state!r} -> {current.episode_state!r} at "
                f"{current.decision_boundary.isoformat()!r}, which §13.2 does not allow "
                f"(legal from {previous.episode_state!r}: {sorted(allowed)!r})")


def _require_decimal_text(value: Any, *, key: str, episode_id: str) -> Decimal:
    """One persisted decimal identity field: it MUST be the exact canonical
    STRING this module's own builders write, never a JSON float (which
    would be precisely the binary-float artifact §12.5 forbids) and never
    a bool/int/other type. Parsed back to an exact `Decimal`."""
    if not isinstance(value, str):
        raise V2EpisodeHistoryCorruptionError(
            f"episode {episode_id!r}'s persisted structural_anchor.{key} must be an exact "
            f"decimal string, got {type(value).__name__}: {value!r} -- a JSON float would be "
            "the binary-float artifact §12.5 forbids")
    try:
        dec = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise V2EpisodeHistoryCorruptionError(
            f"episode {episode_id!r}'s persisted structural_anchor.{key}={value!r} is not a "
            f"valid decimal: {exc}") from exc
    if not dec.is_finite() or dec <= 0:
        raise V2EpisodeHistoryCorruptionError(
            f"episode {episode_id!r}'s persisted structural_anchor.{key}={value!r} must be a "
            "finite, strictly positive decimal")
    return dec


def _assert_valid_persisted_anchor(
    anchor: Mapping, *, setup_family: str, episode_id: str,
) -> None:
    """Validate the persisted creation `structural_anchor` against the
    canonical per-family shape THIS module defines (§12.5a leaves the
    physical JSON schema to implementation, so Unit 1 owns and therefore
    must enforce it).

    Validated at RECONSTRUCTION, not lazily on property access, so a
    malformed persisted grid can never escape as a raw `ValueError` from a
    property or, worse, be silently coerced into a plausible-looking
    identity. Every family requires its own `bucket_ts`;
    `CONFIRMED_BREAKOUT` additionally requires the exact
    §12.5/§12.5a creation tick grid, and its recorded values must be
    mutually coherent (`normalized == tick_index * tick`)."""
    bucket_ts = anchor.get(ANCHOR_BUCKET_TS)
    if not isinstance(bucket_ts, str):
        raise V2EpisodeHistoryCorruptionError(
            f"episode {episode_id!r}'s persisted structural_anchor.{ANCHOR_BUCKET_TS} must be an "
            f"ISO-8601 string, got {type(bucket_ts).__name__}: {bucket_ts!r}")

    # RT-63-R1: being a STRING is not proof of being a legal anchor. The
    # persisted timestamp is parsed and held to the SAME family grid the
    # canonical builders enforce (§12.1), resolved from the one shared
    # _FAMILY_ANCHOR_TIMEFRAME map. Identity revalidation cannot substitute
    # for this: a corrupt row whose episode_id was hashed FROM the malformed
    # anchor is perfectly self-consistent, so only an independent grid check
    # can catch it. "The builder would never write this" is exactly the
    # assumption this module exists to stop relying on after restart/replay.
    timeframe = _FAMILY_ANCHOR_TIMEFRAME[setup_family]
    try:
        parsed_bucket = datetime.fromisoformat(bucket_ts)
    except (TypeError, ValueError) as exc:
        raise V2EpisodeHistoryCorruptionError(
            f"episode {episode_id!r}'s persisted structural_anchor.{ANCHOR_BUCKET_TS}="
            f"{bucket_ts!r} is not a parseable ISO-8601 datetime: {exc}") from exc
    try:
        _validate_bucket_start(
            parsed_bucket, f"structural_anchor.{ANCHOR_BUCKET_TS}", timeframe=timeframe)
    except V2EpisodeHistoryError as exc:
        # Re-raised as CORRUPTION, not caller-input error: this value came
        # out of storage, not out of a caller's arguments.
        raise V2EpisodeHistoryCorruptionError(
            f"episode {episode_id!r} is {setup_family!r}, whose §12.1 identity anchor is a "
            f"{timeframe} bucket start, but its persisted "
            f"structural_anchor.{ANCHOR_BUCKET_TS}={bucket_ts!r} is not one: {exc}") from exc

    tick_fields = (ANCHOR_LEVEL_TICK_INDEX, ANCHOR_LEVEL_NORMALIZED_PRICE,
                   CREATION_IDENTITY_TICK_SIZE)
    if setup_family != CONFIRMED_BREAKOUT:
        present = [k for k in tick_fields if k in anchor]
        if present:
            raise V2EpisodeHistoryCorruptionError(
                f"episode {episode_id!r} is {setup_family!r} but its persisted "
                f"structural_anchor carries CONFIRMED_BREAKOUT tick-grid field(s) {present!r} -- "
                "§12.1 gives this family a bucket-only identity anchor")
        return

    missing = [k for k in tick_fields if k not in anchor]
    if missing:
        raise V2EpisodeHistoryCorruptionError(
            f"episode {episode_id!r} is CONFIRMED_BREAKOUT but its persisted structural_anchor "
            f"is missing required creation tick-grid field(s) {missing!r} -- §12.5a requires them "
            "recorded BY VALUE so restart never re-reads today's instrument metadata")

    tick_index = anchor[ANCHOR_LEVEL_TICK_INDEX]
    if type(tick_index) is not int:      # bool is an int subclass: reject it
        raise V2EpisodeHistoryCorruptionError(
            f"episode {episode_id!r}'s persisted structural_anchor."
            f"{ANCHOR_LEVEL_TICK_INDEX} must be an exact JSON integer, got "
            f"{type(tick_index).__name__}: {tick_index!r}")

    tick = _require_decimal_text(
        anchor[CREATION_IDENTITY_TICK_SIZE], key=CREATION_IDENTITY_TICK_SIZE,
        episode_id=episode_id)
    normalized = _require_decimal_text(
        anchor[ANCHOR_LEVEL_NORMALIZED_PRICE], key=ANCHOR_LEVEL_NORMALIZED_PRICE,
        episode_id=episode_id)
    if normalized != tick_index * tick:
        raise V2EpisodeHistoryCorruptionError(
            f"episode {episode_id!r}'s persisted creation tick grid is incoherent: "
            f"{ANCHOR_LEVEL_NORMALIZED_PRICE}={normalized} but "
            f"{ANCHOR_LEVEL_TICK_INDEX}({tick_index}) * "
            f"{CREATION_IDENTITY_TICK_SIZE}({tick}) = {tick_index * tick} (§12.5)")


def reconstruct_episode_history(
    rows: Sequence[Any],
    *,
    run_kind: str,
    run_id: str,
    episode_id: str,
    as_of: datetime,
    boundary_mode: str,
) -> Optional[V2EpisodeHistory]:
    """Validate and project already-read `v2_episode_events` rows into one
    immutable `V2EpisodeHistory`, or `None` if this episode has no history
    at all in this exact `execution_stream`/window.

    `rows` must already be scoped and ordered by the caller (the storage
    reader does both in SQL); this function independently RE-VERIFIES both
    rather than trusting them, so a hand-built or mis-scoped row set fails
    here exactly as a corrupted database read would.

    Fails closed with `V2EpisodeHistoryCorruptionError` on any history that
    exists but cannot be true:

      - a row from a different `execution_stream` or a different
        `episode_id` than the one requested;
      - a row whose `decision_boundary` is outside the requested `as_of`
        window under `boundary_mode` (a future event leaking backwards);
      - two rows sharing one `decision_boundary` (§2.1a's "at most one
        persisted `V2EpisodeEvent` per (execution_stream, episode_id,
        decision_boundary)");
      - rows not strictly ascending by `decision_boundary`;
      - any §12.2 creation-identity/semantic field differing between two
        events of the same episode (`decision_code_version` excepted by
        contract — see module docstring);
      - an oldest event whose `episode_state` is not `EARLY_SIGNAL` (an
        episode cannot have persisted history before its own creation);
      - a state SEQUENCE contradicting §13.2's frozen transition graph,
        including any event persisted after a terminal one;
      - any event whose `decision_boundary` is not a legal V2 5m boundary;
      - a malformed persisted `CONFIRMED_BREAKOUT` creation tick grid;
      - an `episode_id` that does not reproduce from its own creation facts
        via `compute_episode_id()`;
      - any `event_id` that does not reproduce from `(episode_id,
        decision_boundary)` via `compute_event_id()`.

    Never repairs, never partially returns, never downgrades corruption to
    `None`."""
    validate_episode_history_scope(
        run_kind=run_kind, run_id=run_id, episode_id=episode_id,
        as_of=as_of, boundary_mode=boundary_mode)
    if isinstance(rows, (str, bytes, bytearray)) or not isinstance(rows, Sequence):
        raise V2EpisodeHistoryError(
            f"rows must be a Sequence of row mappings, got {type(rows).__name__}")
    if not rows:
        return None

    events = tuple(_to_persisted_event(r, index=i) for i, r in enumerate(rows))

    # ---- physical scope: no foreign stream/episode may leak in ------------
    for event in events:
        if event.run_kind != run_kind or event.run_id != run_id:
            raise V2EpisodeHistoryCorruptionError(
                f"execution_stream leak: requested ({run_kind!r}, {run_id!r}) but a row carries "
                f"({event.run_kind!r}, {event.run_id!r}) -- §12.10 forbids mixing LIVE/REPLAY "
                "history or two REPLAY run_ids")
        if event.episode_id != episode_id:
            raise V2EpisodeHistoryCorruptionError(
                f"episode leak: requested episode_id {episode_id!r} but a row carries "
                f"{event.episode_id!r}")

    # ---- temporal window: no event may be visible past its own T ----------
    for event in events:
        boundary = event.decision_boundary
        if boundary > as_of or (boundary_mode == HISTORY_BEFORE_T and boundary == as_of):
            raise V2EpisodeHistoryCorruptionError(
                f"lookahead: event at decision_boundary {boundary.isoformat()!r} is outside the "
                f"requested window (as_of={as_of.isoformat()!r}, boundary_mode={boundary_mode!r})")

    # ---- deterministic ordering + §2.1a one-event-per-T -------------------
    for previous, current in zip(events, events[1:]):
        if current.decision_boundary == previous.decision_boundary:
            raise V2EpisodeHistoryCorruptionError(
                f"two persisted events share decision_boundary "
                f"{current.decision_boundary.isoformat()!r} for episode {episode_id!r} -- §2.1a "
                "allows at most one event per (execution_stream, episode_id, decision_boundary)")
        if current.decision_boundary < previous.decision_boundary:
            raise V2EpisodeHistoryCorruptionError(
                f"episode history is not ascending by decision_boundary: "
                f"{previous.decision_boundary.isoformat()!r} is followed by "
                f"{current.decision_boundary.isoformat()!r}")

    # ---- §12.2 creation identity is immutable across the whole episode ----
    first = events[0]
    for event in events[1:]:
        for field in _EPISODE_INVARIANT_FIELDS:
            if getattr(event, field) != getattr(first, field):
                raise V2EpisodeHistoryCorruptionError(
                    f"episode {episode_id!r} changes {field!r} mid-history "
                    f"({getattr(first, field)!r} -> {getattr(event, field)!r}) -- §12.2 freezes "
                    "creation identity for the episode's entire life")
        if event.structural_anchor != first.structural_anchor:
            raise V2EpisodeHistoryCorruptionError(
                f"episode {episode_id!r} changes structural_anchor mid-history "
                f"({dict(first.structural_anchor)!r} -> {dict(event.structural_anchor)!r}) -- "
                "§12.2 freezes the episode_logical_key anchor at creation; a later observed "
                "candidate anchor belongs in decision_snapshot/event_payload (§12.3), never here")

    # ---- the creation event is the OLDEST event, and it is EARLY_SIGNAL --
    # Deliberately NOT "the unique event whose state == EARLY_SIGNAL": §12.2a
    # explicitly allows a TREND_PULLBACK episode, WHILE STILL EARLY_SIGNAL,
    # to record further material pre-confirmation updates as "a **new**,
    # immutable history event". Such an episode legally has SEVERAL
    # EARLY_SIGNAL events. It is created exactly once all the same -- and
    # creation is identified by POSITION (oldest), not by counting states.
    if first.episode_state != EARLY_SIGNAL:
        raise V2EpisodeHistoryCorruptionError(
            f"episode {episode_id!r}'s oldest persisted event at "
            f"{first.decision_boundary.isoformat()!r} is {first.episode_state!r}, not "
            f"{EARLY_SIGNAL!r} -- an episode cannot have persisted history before its own "
            "creation, so t_create is unrecoverable (corrupt history, NOT an absent episode)")

    # ---- §13.2 persisted state SEQUENCE integrity ------------------------
    _assert_legal_state_sequence(events, episode_id=episode_id)

    # t_create IS the creation event's own decision boundary (event_factory.py:
    # "For the episode's own creation event, t_create == decision_boundary").
    t_create = first.decision_boundary

    # ---- every persisted boundary must be a legal V2 5m T -----------------
    # Checked for ALL events, not just creation: an off-grid later boundary
    # would otherwise reach compute_event_id() and surface as a foreign
    # V2EpisodeIdentityError, outside this module's documented hierarchy.
    for event in events:
        _validate_decision_boundary_T(
            event.decision_boundary, "persisted decision_boundary",
            error_cls=V2EpisodeHistoryCorruptionError)

    # ---- §12.5/§12.5a persisted creation tick grid ------------------------
    _assert_valid_persisted_anchor(
        first.structural_anchor, setup_family=first.setup_family, episode_id=episode_id)

    # ---- deterministic-identity revalidation (REUSES H3, never re-hashes) -
    recomputed_episode_id = compute_episode_id(
        model_family=first.model_family,
        rules_version=first.rules_version,
        calculation_version=first.calculation_version,
        symbol=first.symbol,
        market_type=first.market_type,
        direction=first.direction,
        setup_family=first.setup_family,
        structural_anchor=first.structural_anchor,
        t_create=t_create,
    )
    if recomputed_episode_id != episode_id:
        raise V2EpisodeHistoryCorruptionError(
            f"episode_id {episode_id!r} does not match its own persisted creation facts "
            f"(recomputing compute_episode_id() from them yields {recomputed_episode_id!r}) -- "
            "the row's identity and its contents disagree")
    for event in events:
        recomputed_event_id = compute_event_id(
            episode_id=episode_id, decision_boundary=event.decision_boundary)
        if recomputed_event_id != event.event_id:
            raise V2EpisodeHistoryCorruptionError(
                f"event_id {event.event_id!r} at decision_boundary "
                f"{event.decision_boundary.isoformat()!r} does not match compute_event_id("
                f"episode_id, decision_boundary) = {recomputed_event_id!r}")

    return V2EpisodeHistory(
        run_kind=run_kind,
        run_id=run_id,
        episode_id=episode_id,
        as_of=as_of,
        boundary_mode=boundary_mode,
        events=events,
        creation_identity=V2EpisodeCreationIdentity(
            episode_id=episode_id,
            t_create=t_create,
            model_family=first.model_family,
            rules_version=first.rules_version,
            calculation_version=first.calculation_version,
            symbol=first.symbol,
            market_type=first.market_type,
            direction=first.direction,
            setup_family=first.setup_family,
            structural_anchor=first.structural_anchor,
        ),
    )
