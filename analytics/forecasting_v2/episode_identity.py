"""
V2-H3: deterministic episode/event persistence identity
(`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §2.1a).

`events.py`'s `V2EpisodeEvent` has always accepted `episode_id`/`event_id`
as plain, caller-supplied, `nonblank`-only strings — "the future Episode
State Machine owns their deterministic generation," per that module's own
docstring. No such generator has existed anywhere in this repository until
this module: every existing test/fixture supplies an arbitrary opaque
placeholder (`"evt-1"`, `"ep-1"`). This module is that generator — the ONE
place `episode_id`/`event_id` are actually computed, deterministically, from
the exact semantic fields §2.1a freezes.

**Two identities, deliberately not one (§2.1a, §12.1, §12.2):**

  - `compute_episode_id()` answers "which semantic EPISODE NAMESPACE does
    this belong to" — the episode's permanent, immutable identity,
    established once at `EARLY_SIGNAL` creation (`T_create`) and never
    recomputed for the rest of that episode's life, no matter how many
    later decision boundaries observe/update it. It is deliberately built
    from `T_create` — the episode's own fixed CREATION boundary — never
    from a later, "current" decision boundary. Putting a per-call
    `decision_boundary` into this function would be wrong precisely
    because an episode spans many decision boundaries over its life
    (§12.2/§12.2a); its identity must not shift with them.
  - `compute_event_id()` answers "which semantic EVENT is this, AT this one
    decision boundary" — built from the episode it belongs to plus that
    one specific boundary. §2.1a's own frozen "at most one persisted
    `V2EpisodeEvent` per (execution_stream, episode_id, decision_boundary)"
    same-`T` singular-event model is exactly why `(episode_id,
    decision_boundary)` alone is sufficient here: no event kind/ordinal/
    sequence number is needed, because the contract already guarantees at
    most one row can legitimately exist for that pair (§2.1a's rejected
    "option (b)" would have needed one; the adopted "option (a)" does not).

**Fields excluded, and why (§2.1a's own text, restated precisely):**

`run_kind`/`run_id` (`execution_stream`, §12.10) are the PHYSICAL row
namespace, never semantic identity — deliberately excluded from both
`episode_id` and `event_id` so a `LIVE` run and a `REPLAY` run over
identical historical data and rules reproduce the exact same identities
(enabling direct semantic comparison across runs), while the physical
`(run_kind, run_id, episode_id, decision_boundary)`/`(run_kind, run_id,
event_id)` composites still keep their rows from ever colliding in
storage (`storage/stage2_schema.sql`'s existing PK plus this PR's new
`UNIQUE` index). Wall-clock time, random UUIDs, and process/host identity
are excluded because they are non-deterministic by construction — a
retried, restarted, or reconnected computation of the identical logical
fact would otherwise never reproduce the same identity, defeating the
entire point of `ON CONFLICT DO NOTHING`-based idempotent retry.
`decision_code_version` (§3.2's Stage 4/5/6 DECISION-code identity) is
likewise excluded from BOTH identities: §2.1a's "exactly" field list for
`episode_id` does not include it, and a Stage 6 bug-fix release changing
`decision_code_version` alone must not fork the semantic identity of an
episode whose underlying market facts are unchanged. It is still captured
BY VALUE on the persisted `V2EpisodeEvent` itself (`events.py`,
`provenance.py`) — excluded from the ID, never dropped from the record.

**Hash algorithm and representation (deliberately NOT truncated).** SHA-256,
full 64-character lowercase hex digest — no 16-character (or other
shortened) prefix. A prior exploratory audit suggested reusing
`calculation_version`'s 16-hex-char convention; that was this repository's
existing STAGE-2 FEATURE-IDENTITY convention (`common.versioning.
compute_calculation_version`), not a frozen requirement for V2 EPISODE
identity, and 16 hex chars (64 bits) is a meaningfully weaker collision
bound than 64 hex chars (256 bits) for a value that must remain a globally
unique, permanent, reused-forever-across-replay identity with an unbounded
future population (unlike `calculation_version`, which is deliberately
scoped to a small, humanly-reviewed set of feature-computation code/config
combinations). Absent a concrete, reviewed collision-risk analysis
justifying a shorter representation, this module defaults to the full
digest, matching `config_hash`'s own existing 64-hex-char convention
(`analytics/forecasting_v2/_validation.py`'s `HEX64`) rather than
`calculation_version`'s 16-hex-char one.

**Canonicalization (deterministic, tested, never `repr()`-based).** Every
hash input is built as an explicit Python `dict` with named keys, then
serialized via `common.versioning.canonical_json` — the SAME sorted-key,
compact-separator, `ensure_ascii=False`, `allow_nan=False` canonical JSON
primitive this repository already uses for `config_hash`/
`calculation_version` (`common/versioning.py`), never a bespoke second
canonicalization or a delimiter-joined string (which would risk exactly
the `["a|b","c"]` vs. `["a","b|c"]` ambiguity a naive `"|".join(...)`
scheme could introduce — JSON's own structural quoting/braces make this
class of ambiguity impossible by construction). `canonical_json` does not,
by itself, know how to serialize a `datetime` — `_stringify_datetimes()`
below performs the one additional, explicit step this module needs before
handing a payload to it: converting every UTC-aware `datetime` leaf to its
`.isoformat()` string, the exact convention
`storage/stage2_serialization.py::to_jsonable` already uses for JSONB
persistence (reused here, not reinvented, so a value that later gets
persisted and a value that gets hashed always agree on one canonical
textual form). A naive or non-UTC datetime is rejected outright, never
silently normalized — mirroring `events.py::_deep_freeze`'s identical rule.

Pure only: no DB, network, filesystem, clock, `uuid`, or `random` access.
"""
from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping as _AbcMapping
from datetime import datetime, timedelta
from typing import Any, Mapping

from analytics.forecasting_v2._validation import (
    HEX64, nonblank, one_of, validate_calculation_version, validate_market_type,
    validate_symbol,
)
from analytics.forecasting_v2.alignment import V2AlignmentError, selected_bucket
from analytics.forecasting_v2.events import DIRECTIONS, SETUP_FAMILIES
from common.v2_config import MODEL_FAMILY, validate_rules_version
from common.versioning import canonical_json

__all__ = [
    "V2EpisodeIdentityError",
    "EPISODE_ID_HASH_ALGORITHM", "EVENT_ID_HASH_ALGORITHM", "ID_HEX_LENGTH",
    "compute_episode_id", "compute_event_id",
]


class V2EpisodeIdentityError(ValueError):
    """Malformed input to deterministic episode/event identity construction:
    an invalid model/version identity, an unsupported symbol/market_type/
    direction/setup_family, a non-Mapping `structural_anchor`, a naive/
    non-UTC/non-legal-5m-boundary timestamp, or a malformed
    already-computed `episode_id` handed to `compute_event_id()`. Never
    silently coerced."""


# SHA-256, full 64-lowercase-hex-char digest -- see module docstring "Hash
# algorithm and representation" for why this is NOT truncated to 16 chars
# the way calculation_version/config_hash's 16-char convention is.
EPISODE_ID_HASH_ALGORITHM = "sha256"
EVENT_ID_HASH_ALGORITHM = "sha256"
ID_HEX_LENGTH = 64


def _validate_legal_decision_boundary(value: Any, name: str) -> datetime:
    """A legal V2 5m decision boundary -- delegated to
    `alignment.selected_bucket("5m", value)`, the same canonical source of
    truth `decision_provenance.py`/`version_switch.py` already use for
    this exact check (never a locally-duplicated, potentially-weaker
    reimplementation). Wraps every exception (the expected
    `V2AlignmentError`, or anything an adversarial/malformed `tzinfo`
    might raise) into this module's own `V2EpisodeIdentityError` at this
    module's public boundary, exactly like those two modules do."""
    if not isinstance(value, datetime):
        raise V2EpisodeIdentityError(f"{name} must be a datetime, got {type(value).__name__}")
    try:
        selected_bucket("5m", value)
    except V2AlignmentError as exc:
        raise V2EpisodeIdentityError(f"{name}: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - malformed/malicious tzinfo, never leaked raw
        raise V2EpisodeIdentityError(
            f"{name} failed alignment validation: {type(exc).__name__}: {exc}") from exc
    return value


def _stringify_datetimes(value: Any, *, name: str) -> Any:
    """Recursively canonicalize one JSON-safe structure for hashing:
    every UTC-aware `datetime` leaf becomes its canonical `.isoformat()`
    string (the one step `common.versioning.canonical_json` cannot do on
    its own -- its `_to_plain` helper has no `datetime` case at all), and
    every leaf's shape/finiteness is validated HERE, raising this module's
    own `V2EpisodeIdentityError` with the exact field path (`name`) that
    failed -- never a raw `ValueError`/`TypeError` leaking up from
    `canonical_json`'s own, differently-worded, path-less validation
    inside `compute_episode_id()`/`compute_event_id()`. This mirrors
    `events.py::_deep_freeze`'s identical leaf rules (naive/non-UTC
    datetime rejected, non-finite float rejected, non-str mapping key
    rejected, unsupported type rejected) — a THIRD, hashing-specific
    variant of the same narrow, stable rule set `_deep_freeze()` and
    `storage/stage2_serialization.py::to_jsonable()` already each
    implement for their own purposes (construction-time freezing;
    JSONB-persistence conversion, respectively) — never a second copy of
    either of those two, and never a behavioral fork from either: the same
    three leaf rules, restated once more at this module's own boundary."""
    if value is None or isinstance(value, (bool, str, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise V2EpisodeIdentityError(
                f"{name}: non-finite float is not allowed in a hash input "
                f"(NaN/+Inf/-Inf), got {value!r}")
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise V2EpisodeIdentityError(f"{name}: datetime must be timezone-aware, got naive {value!r}")
        if value.utcoffset() != timedelta(0):
            raise V2EpisodeIdentityError(
                f"{name}: datetime must be UTC (offset 0), got {value!r} "
                f"(offset {value.utcoffset()})")
        return value.isoformat()
    if isinstance(value, _AbcMapping):
        out = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise V2EpisodeIdentityError(
                    f"{name}: mapping keys must be str, got {type(k).__name__}: {k!r}")
            out[k] = _stringify_datetimes(v, name=f"{name}.{k}")
        return out
    if isinstance(value, (list, tuple)):
        return [_stringify_datetimes(v, name=f"{name}[]") for v in value]
    raise V2EpisodeIdentityError(
        f"{name}: unsupported value of type {type(value).__name__} "
        "(only JSON-compatible mappings/lists/str/int/float/bool/None/datetime "
        "are allowed in a hash input)")


def _validate_structural_anchor(value: Any) -> Mapping:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, _AbcMapping):
        raise V2EpisodeIdentityError(
            f"structural_anchor must be a Mapping (JSON object), got {type(value).__name__}")
    return value


def _validate_episode_id_shape(value: Any) -> str:
    nonblank(value, "episode_id", V2EpisodeIdentityError)
    if not HEX64.fullmatch(value):
        raise V2EpisodeIdentityError(
            "episode_id must be exactly 64 lowercase hex chars (a compute_episode_id() "
            f"output), got {value!r}")
    return value


def compute_episode_id(
    *,
    model_family: str,
    rules_version: str,
    calculation_version: str,
    symbol: str,
    market_type: str,
    direction: str,
    setup_family: str,
    structural_anchor: Mapping,
    t_create: datetime,
) -> str:
    """Deterministic `episode_id`: SHA-256 (full 64-hex-char lowercase
    digest) of the canonical JSON serialization of exactly the
    §2.1a-frozen tuple -- `model_family`, `rules_version`,
    `calculation_version`, `symbol`, `market_type`, `direction`,
    `setup_family`, `structural_anchor` (canonicalized), `t_create`
    (canonicalized) -- no more, no fewer fields. See module docstring for
    the full field-inclusion/exclusion rationale.

    `t_create` MUST be the episode's own fixed `EARLY_SIGNAL` creation
    decision boundary (a legal V2 5m-grid-aligned boundary) -- NEVER a
    later, "current" decision boundary; see module docstring for why.

    Every field is independently validated (reusing the same validators
    `events.py`/`provenance.py`/`decision_provenance.py` already use, never
    a second competing implementation) before hashing -- a malformed field
    raises `V2EpisodeIdentityError` before any hash is computed."""
    if model_family != MODEL_FAMILY:
        raise V2EpisodeIdentityError(
            f"model_family must be exactly {MODEL_FAMILY!r}, got {model_family!r}")
    try:
        validate_rules_version(rules_version)
    except ValueError as exc:
        raise V2EpisodeIdentityError(str(exc)) from exc
    validate_calculation_version(calculation_version, V2EpisodeIdentityError)
    validate_symbol(symbol, V2EpisodeIdentityError)
    validate_market_type(market_type, V2EpisodeIdentityError)
    one_of(direction, "direction", DIRECTIONS, V2EpisodeIdentityError)
    one_of(setup_family, "setup_family", SETUP_FAMILIES, V2EpisodeIdentityError)
    anchor = _validate_structural_anchor(structural_anchor)
    t = _validate_legal_decision_boundary(t_create, "t_create")

    payload = {
        "model_family": model_family,
        "rules_version": rules_version,
        "calculation_version": calculation_version,
        "symbol": symbol,
        "market_type": market_type,
        "direction": direction,
        "setup_family": setup_family,
        "structural_anchor": _stringify_datetimes(anchor, name="structural_anchor"),
        "t_create": t.isoformat(),
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def compute_event_id(*, episode_id: str, decision_boundary: datetime) -> str:
    """Deterministic `event_id`: SHA-256 (full 64-hex-char lowercase
    digest) of the canonical JSON serialization of exactly `episode_id`
    plus `decision_boundary` -- no event kind, ordinal, or sequence number,
    because §2.1a's own frozen "at most one persisted `V2EpisodeEvent` per
    (execution_stream, episode_id, decision_boundary)" invariant already
    guarantees this pair is unambiguous; inventing an ordinal here would
    contradict that same-`T` singular-event model rather than support it.

    `episode_id` MUST already be a valid `compute_episode_id()` output
    (validated against its own frozen 64-hex-char shape) -- this function
    never re-derives it from raw episode fields itself, keeping the two
    identities' construction boundaries separate per the module docstring.
    `decision_boundary` MUST be a legal V2 5m-grid-aligned boundary, exactly
    like `t_create` above."""
    episode = _validate_episode_id_shape(episode_id)
    t = _validate_legal_decision_boundary(decision_boundary, "decision_boundary")
    payload = {"episode_id": episode, "decision_boundary": t.isoformat()}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
