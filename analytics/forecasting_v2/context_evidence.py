"""
V2 shared context-evidence primitives (Stage 4 — Context Engines, PR 1 of
~3, docs/FORECASTING_ROADMAP.md §I stage 4).

Stage 3 (complete) answers "which data belongs to logical decision
boundary T?" and hands back one immutable `V2AlignedInputs` snapshot
(`analytics/forecasting_v2/aligned_inputs.py`). Stage 4 begins answering
"what does that already-aligned data mean?" — but this PR owns ONLY the
small, reusable mathematical vocabulary the future 4h regime engine (PR
2/~3) and 1h bias engine (PR 3/~3) both need, taken directly from the
frozen `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §4.1/§4.2:

  - `find_consensus_percentile` — exact `(metric, percentile_window)`
    lookup over one `V2TimeframeInputs`' already-aligned percentile rows.
  - `normalized_evidence` — the corrected signed-evidence primitive
    (§4.1): the raw metric's own sign chooses the evidence's sign;
    percentile rank chooses magnitude/extremity within that sign ONLY. A
    positive raw value can never produce negative evidence; a negative
    raw value can never produce positive evidence.
  - `compression_score` — the unsigned companion primitive (§4.1),
    `1.0 - percentile_rank` of `range_width_pct_median`; no signed math.
  - `oi_confirmation` — the corrected OI confirmation/opposition
    primitive (§4.2): OI never independently selects a direction, it only
    confirms (rising OI) or opposes (falling OI) whichever anchor
    direction is established elsewhere, one-sided relative to its own
    raw sign — never `abs(oi_rank - 0.5)`.

This PR does **not** classify a 4h regime or a 1h bias — no
`BULLISH_TRENDING`/`BEARISH_TRENDING`/`NON_DIRECTIONAL`/
`INSUFFICIENT_DATA`, no `BULLISH`/`BEARISH`/`NEUTRAL_NOT_ESTABLISHED`, no
`REGIME_*`/`BIAS_*` threshold, no `directional_context_gate`, and no
setup-detector (`TREND_PULLBACK`/`COMPRESSION_BREAKOUT`/
`CONFIRMED_BREAKOUT`) logic exists anywhere in this module. Those are
Stage 4 PR 2/~3, PR 3/~3, and Stage 5 respectively.

**UNAVAILABLE representation.** Every public function returns
`Optional[float]`: `None` means UNAVAILABLE (legitimately absent or
too-immature data), a real `float` (including `0.0`) means an actually
computed value. `0.0` is NEVER used as a missing-data sentinel — see
`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §5.2, "never `None == 0`".

**Missing vs. malformed.** Legitimate missingness (`None` snapshot,
`None` value/rank, a `consensus is None` timeframe, a below-floor
confidence tier) returns `None` — never an exception. Malformed/impossible
data (an unknown confidence tier, a non-finite or out-of-range numeric
value, a duplicate exact percentile row, a percentile row whose identity
does not match what was requested, a lookahead-violating
`sample_window_end`) raises `V2ContextEvidenceError` — never silently
downgraded to `None`. This mirrors `aligned_inputs.py`'s own
missingness-vs-corruption posture at the Stage 3 boundary; the deep
re-check here exists because a Stage 4 caller may hand-construct a
`V2TimeframeInputs` directly (in tests, or a future replay harness) and
this module never blindly trusts a percentile row's semantic fields.

**`MIN_PCTL_TIER = "building"` (frozen V2-v0 parameter, §4.1).** Reuses
the canonical Stage 2 tier ordering (`analytics.percentile_engine.models
.CONFIDENCE_TIERS = ("none", "low", "building", "mature")`) rather than
inventing a second one — `"building"`/`"mature"` are usable, `"none"`/
`"low"` are legitimately-immature UNAVAILABLE, and an unknown tier string
is corrupted input (`V2ContextEvidenceError`), never silently treated as
unavailable. Per `STAGE2_SPEC.md` §12.6 this tier is a **calendar-span
maturity signal, not a row-count/statistical-density guarantee**. A valid
`building` or `mature` row can therefore have a very small `sample_size`;
this module deliberately does not invent an independent density threshold.
Issue #51 / MATH-001 tracks the requirement to resolve empirical-density
eligibility before a real percentile orchestrator makes such evidence part
of a research claim.

**Layering.** `analytics.forecasting_v2 -> analytics.percentile_engine`
is the correct direction here (this module reuses percentile_engine's own
frozen constants rather than re-declaring a second, driftable copy) — the
reverse (`percentile_engine` depending on `forecasting_v2`) would be
wrong and does not happen. This module consumes only the already-aligned,
already-immutable `V2TimeframeInputs` Stage 3 hands back — it performs NO
I/O of its own: no DB, no `asyncpg`, no network, no filesystem, no clock,
no config loading, no `random`/`uuid`/`subprocess`. Every public function
is synchronous and pure.

**OI raw-value / percentile-value cross-check — deliberately NOT
enforced.** `oi_confirmation`'s raw signed OI value comes from
`V2TimeframeInputs.consensus["oi_change_pct_median"]` (§4.2's own frozen
source), while its rank/extremity comes from the separate consensus-scope
percentile row for the same metric. `analytics/percentile_engine/
compute.py::compute_percentile_snapshot` does copy `PercentileRequest
.value` into `PercentileSnapshot.value` byte-for-byte, with no rounding —
so IF a `PercentileRequest` for `oi_change_pct_median` were always built
from the exact same stored consensus row, the two values would be
guaranteed identical. But no such request-construction pipeline exists
anywhere in this codebase today (`PercentileRequest(...)` is only ever
constructed in `analytics/percentile_engine`'s own tests) — there is no
Stage 2 orchestrator to inspect that actually makes this guarantee for a
live bucket. Asserting exact equality here would therefore be inventing a
cross-family guarantee this codebase does not yet establish, and this
module does not guess at tolerances. A future PR that adds the real
consensus-scope percentile-computation pipeline should revisit this and
decide, from that pipeline's actual code, whether the check becomes safe
to add.
"""
from __future__ import annotations

from collections.abc import Mapping as _AbcMapping
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

from analytics.forecasting_v2.aligned_inputs import V2TimeframeInputs
from analytics.percentile_engine.models import (
    CONFIDENCE_TIERS, CONSENSUS_SCOPE_METRICS, VALID_WINDOWS,
)

__all__ = [
    "V2ContextEvidenceError",
    "MIN_PCTL_TIER",
    "find_consensus_percentile",
    "normalized_evidence",
    "compression_score",
    "oi_confirmation",
]


class V2ContextEvidenceError(ValueError):
    """Malformed input, or a percentile row that is internally
    INCONSISTENT with what was requested (wrong scope/exchange/timeframe/
    bucket, a duplicate exact `(metric, percentile_window)` row, a
    lookahead-violating `sample_window_end`, an unknown confidence tier,
    a non-finite/out-of-range numeric value). Never raised for
    legitimately MISSING data — that returns `None` (UNAVAILABLE), never
    an error."""


# Frozen V2-v0 parameter (§4.1): the loosest frozen calendar-maturity tier
# floor usable by both 7d and 30d windows. Per Stage 2 §12.6 it is span-based,
# NOT a row-count/statistical-density guarantee; issue #51/MATH-001 tracks the
# future empirical-density eligibility decision before percentile orchestration.
MIN_PCTL_TIER = "building"
_MIN_TIER_INDEX = CONFIDENCE_TIERS.index(MIN_PCTL_TIER)

# §4.1's unsigned companion metric — `compression_score` fixes this
# internally; `normalized_evidence` explicitly refuses it (§23 below).
_COMPRESSION_METRIC = "range_width_pct_median"
# §4.2's frozen raw-OI source, read from `V2TimeframeInputs.consensus`
# (never from the percentile row's own `value` — see module docstring).
_OI_METRIC = "oi_change_pct_median"


def _percentile_tier_usable(tier: Any) -> bool:
    """`True` for `"building"`/`"mature"`, `False` for `"none"`/`"low"`.
    An unknown tier string is corrupted input, not a legitimately
    low-maturity one — raises rather than silently treating it as
    unavailable (§21: Unavailable vs. Rejected are different categories).
    Compares by canonical CONFIDENCE_TIERS index, never alphabetically."""
    if tier not in CONFIDENCE_TIERS:
        raise V2ContextEvidenceError(
            f"unknown confidence_tier {tier!r} (expected one of {CONFIDENCE_TIERS})")
    return CONFIDENCE_TIERS.index(tier) >= _MIN_TIER_INDEX


def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))  # NaN != NaN


def _validate_finite_numeric(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2ContextEvidenceError(
            f"{name} must be a real number, got {type(value).__name__}: {value!r}")
    v = float(value)
    if not _is_finite(v):
        raise V2ContextEvidenceError(f"{name} must be finite, got {value!r}")
    return v


def _validate_unit_interval(value: Any, name: str) -> float:
    v = _validate_finite_numeric(value, name)
    if not (0.0 <= v <= 1.0):
        raise V2ContextEvidenceError(f"{name} must be within [0.0, 1.0], got {v!r}")
    return v


def _validate_utc_datetime(value: Any, name: str) -> datetime:
    """Exact-type, timezone-aware, UTC, whole-minute `datetime` check —
    mirrors the same posture `storage/v2_alignment_readers.py::
    _validate_whole_minute_utc` and `aligned_inputs.py::_validate_bar_ts`
    already use elsewhere in V2, restated locally (never imported — this
    module raises its own `V2ContextEvidenceError`, not a foreign
    exception type). Stage 3 already guarantees this for a real
    `V2AlignedInputs`, but `find_consensus_percentile` explicitly supports
    a hand-constructed `V2TimeframeInputs` too (tests, a future replay
    harness); a malformed timestamp there must raise this domain error,
    never a bare `TypeError` leaking out of a `<`/`!=` comparison. Never
    normalizes/floors/converts — a value that fails is rejected outright."""
    if type(value) is not datetime:
        raise V2ContextEvidenceError(f"{name} must be a datetime, got {type(value).__name__}: {value!r}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2ContextEvidenceError(f"{name} must be timezone-aware, got {value!r}")
    if value.utcoffset() != timedelta(0):
        raise V2ContextEvidenceError(f"{name} must be UTC (offset 0), got offset {value.utcoffset()}")
    if value.second != 0 or value.microsecond != 0:
        raise V2ContextEvidenceError(
            f"{name} must be a whole minute (no seconds/microseconds), got {value!r}")
    return value


def find_consensus_percentile(
    inputs: V2TimeframeInputs, *, metric: str, percentile_window: str,
) -> Optional[Mapping]:
    """The ONE consensus-scope percentile row in `inputs.percentiles`
    matching EXACTLY `(metric, percentile_window)` — no cross-window
    fallback (a `30d` request never returns a `7d` row or vice versa).

    0 matching rows -> `None` (legitimately absent, never an error).
    1 matching row -> the row, after defensively re-validating the
    semantic fields this module depends on (`scope == "consensus"`,
    `exchange == ""`, `timeframe`/`bucket_ts` match `inputs`, and the
    no-lookahead invariant `sample_window_end < inputs.bucket_ts` when
    `sample_window_end` is present — equality is forbidden).
    >1 matching rows -> `V2ContextEvidenceError` (the Stage 3 boundary
    already rejects duplicate logical percentile rows for a real
    `V2AlignedInputs`; this stays fail-closed for a hand-constructed
    `V2TimeframeInputs` too, e.g. in a test or a future replay harness).

    `metric` must be one of `CONSENSUS_SCOPE_METRICS`
    (`analytics.percentile_engine.models`) and `percentile_window` must be
    one of `VALID_WINDOWS` (`"7d"`/`"30d"`) — no string coercion, no
    aliasing, no fuzzy matching.

    Every item in `inputs.percentiles` must be a `Mapping` — checked for
    ALL rows, not only a matching one, so a malformed non-matching row
    (a broken/fake caller's corrupted collection) is treated as
    corruption rather than silently ignored. `inputs.bucket_ts`, the
    matching row's `bucket_ts`, and its `sample_window_end` (when present)
    are each validated as proper aware-UTC whole-minute `datetime`s before
    any comparison — a malformed value raises `V2ContextEvidenceError`,
    never a bare `TypeError`/`AttributeError`."""
    if not isinstance(metric, str) or metric not in CONSENSUS_SCOPE_METRICS:
        raise V2ContextEvidenceError(
            f"metric must be one of {CONSENSUS_SCOPE_METRICS}, got {metric!r}")
    if not isinstance(percentile_window, str) or percentile_window not in VALID_WINDOWS:
        raise V2ContextEvidenceError(
            f"percentile_window must be one of {VALID_WINDOWS}, got {percentile_window!r}")

    bucket_ts = _validate_utc_datetime(inputs.bucket_ts, "inputs.bucket_ts")

    matches = []
    for row in inputs.percentiles:
        if not isinstance(row, _AbcMapping):
            raise V2ContextEvidenceError(
                f"inputs.percentiles must contain only Mapping rows, got "
                f"{type(row).__name__}: {row!r}")
        if row.get("metric") == metric and row.get("percentile_window") == percentile_window:
            matches.append(row)

    if not matches:
        return None
    if len(matches) > 1:
        raise V2ContextEvidenceError(
            f"expected at most one percentile row for (metric={metric!r}, "
            f"percentile_window={percentile_window!r}), got {len(matches)}")
    row = matches[0]

    if row.get("scope") != "consensus":
        raise V2ContextEvidenceError(
            f"percentile row scope must be 'consensus', got {row.get('scope')!r}")
    if row.get("exchange") != "":
        raise V2ContextEvidenceError(
            f"percentile row exchange must be '' for consensus scope, got "
            f"{row.get('exchange')!r}")
    if row.get("timeframe") != inputs.timeframe:
        raise V2ContextEvidenceError(
            "percentile row timeframe does not match the aligned timeframe")

    row_bucket_ts = _validate_utc_datetime(row.get("bucket_ts"), "percentile row bucket_ts")
    if row_bucket_ts != bucket_ts:
        raise V2ContextEvidenceError(
            "percentile row bucket_ts does not match the aligned bucket")

    sample_window_end = row.get("sample_window_end")
    if sample_window_end is not None:
        sample_window_end = _validate_utc_datetime(
            sample_window_end, "percentile row sample_window_end")
        if not (sample_window_end < bucket_ts):
            raise V2ContextEvidenceError(
                "percentile row sample_window_end must be strictly before bucket_ts "
                "(no-lookahead defense) — equality is not allowed")

    return row


def normalized_evidence(
    inputs: V2TimeframeInputs, *, metric: str, percentile_window: str,
) -> Optional[float]:
    """§4.1's corrected signed-normalization primitive. The raw metric's
    OWN sign chooses the evidence's sign; `percentile_rank` chooses
    magnitude/extremity within that sign ONLY — it can never flip it.

        v > 0  -> max(0.0, 2.0 * p - 1.0)   (>= 0 always)
        v < 0  -> -max(0.0, 1.0 - 2.0 * p)  (<= 0 always)
        v == 0 -> 0.0                        (genuine neutral)

    `None` (UNAVAILABLE, never `0.0`) if: no exact percentile row exists;
    its `value` is `None`; its `percentile_rank` is `None`; or its
    `confidence_tier` is below `MIN_PCTL_TIER`. `V2ContextEvidenceError`
    for a malformed PRESENT `value`/`percentile_rank` (non-finite,
    non-numeric, `percentile_rank` outside `[0.0, 1.0]`) or an unknown
    confidence tier — never silently coerced or clamped.

    **Validation order (load-bearing).** Every PRESENT field this
    function reads (`confidence_tier`, `value`, `percentile_rank`) is
    validated for corruption BEFORE any missingness/tier-floor
    short-circuit runs — an unknown tier, a non-finite `value`, or an
    out-of-range `percentile_rank` is never masked just because a
    DIFFERENT field on the same row happens to be legitimately missing or
    the tier happens to be below the usable floor. Only once every
    PRESENT field is known valid do the `None`/tier-floor rules apply.

    Rejects `metric == "range_width_pct_median"` outright: that is an
    UNSIGNED range metric with no sign to preserve — use
    `compression_score()` instead (§23: this primitive must not silently
    become the general-purpose API for an unsigned metric)."""
    if metric == _COMPRESSION_METRIC:
        raise V2ContextEvidenceError(
            f"{_COMPRESSION_METRIC!r} is an unsigned range metric with no sign to "
            "preserve — use compression_score(), not normalized_evidence()")

    snapshot = find_consensus_percentile(inputs, metric=metric, percentile_window=percentile_window)
    if snapshot is None:
        return None

    value = snapshot.get("value")
    rank = snapshot.get("percentile_rank")
    tier = snapshot.get("confidence_tier")

    # Validate every PRESENT field first — an unknown tier, or a
    # malformed present value/rank, must never be hidden behind a
    # coincidentally-missing peer field.
    tier_usable = _percentile_tier_usable(tier)
    v = _validate_finite_numeric(value, "value") if value is not None else None
    p = _validate_unit_interval(rank, "percentile_rank") if rank is not None else None

    # Only now: legitimate-missingness / tier-floor short-circuits.
    if v is None:
        return None
    if p is None:
        return None
    if not tier_usable:
        return None

    if v > 0:
        return max(0.0, 2.0 * p - 1.0)
    elif v < 0:
        return -max(0.0, 1.0 - 2.0 * p)
    else:
        return 0.0


def compression_score(inputs: V2TimeframeInputs, *, percentile_window: str) -> Optional[float]:
    """§4.1's unsigned companion primitive: `1.0 - percentile_rank` of the
    FIXED metric `range_width_pct_median` (the caller does not, and
    cannot, supply a different metric). A narrow range relative to its
    own history scores near `1.0` (tight/compressed); a wide range scores
    near `0.0`. No signed evidence math is applied — this is an unsigned
    magnitude, never `> 1.0` or `< 0.0`.

    Same `None`/tier-floor rules as `normalized_evidence` (missing
    snapshot/value/rank, or a below-floor tier, -> `None`). A PRESENT
    `value` must be finite and `>= 0.0` — a negative range width is
    corrupted data (`V2ContextEvidenceError`), never silently accepted.

    **Validation order (load-bearing)**, same posture as
    `normalized_evidence`: every PRESENT field (`confidence_tier`,
    `value`, `percentile_rank`) is validated for corruption BEFORE any
    missingness/tier-floor short-circuit — a negative/non-finite PRESENT
    `value`, an out-of-range `percentile_rank`, or an unknown tier is
    never masked by a coincidentally-missing peer field or a below-floor
    tier on the same row."""
    snapshot = find_consensus_percentile(
        inputs, metric=_COMPRESSION_METRIC, percentile_window=percentile_window)
    if snapshot is None:
        return None

    value = snapshot.get("value")
    rank = snapshot.get("percentile_rank")
    tier = snapshot.get("confidence_tier")

    tier_usable = _percentile_tier_usable(tier)
    if value is not None:
        v = _validate_finite_numeric(value, f"{_COMPRESSION_METRIC} value")
        if v < 0:
            raise V2ContextEvidenceError(
                f"{_COMPRESSION_METRIC} must be >= 0 (unsigned range metric), got {v!r}")
    else:
        v = None
    p = _validate_unit_interval(rank, "percentile_rank") if rank is not None else None

    if v is None:
        return None
    if p is None:
        return None
    if not tier_usable:
        return None

    return 1.0 - p


def oi_confirmation(inputs: V2TimeframeInputs, *, percentile_window: str) -> Optional[float]:
    """§4.2's corrected OI confirmation/opposition primitive. OI does
    **not** independently select LONG/SHORT — this function intentionally
    accepts no `direction`/`price_evidence`/`regime`/`bias` parameter. Its
    output only ever means:

        positive -> CONFIRMS whatever anchor direction is established
                    elsewhere (rising OI can confirm either a bullish or
                    a bearish anchor — it is symmetric by construction)
        negative -> OPPOSES that anchor (falling OI)
        zero     -> neither

    Raw OI comes from `inputs.consensus["oi_change_pct_median"]` (§4.2's
    own frozen source — never re-derived from the percentile row's
    `value`); extremity comes from the separate consensus-scope
    percentile row for the same metric:

        oi_raw > 0  -> +max(0.0, 2.0 * oi_rank - 1.0) * oi_agreement
        oi_raw < 0  -> -max(0.0, 1.0 - 2.0 * oi_rank) * oi_agreement
        oi_raw == 0 -> 0.0

    This is a ONE-SIDED tail distance relative to `oi_raw`'s own sign —
    deliberately NOT `2 * abs(oi_rank - 0.5)` (§17: that undirected form
    would wrongly report a weak rising-OI reading that merely ranks below
    its own median as "strong confirmation").

    `None` (UNAVAILABLE) if: `inputs.consensus` is `None`;
    `oi_change_pct_median` is `None`; `oi_direction_agreement` is `None`;
    no exact percentile row exists for `(oi_change_pct_median,
    percentile_window)`; that row's `percentile_rank` is `None`; or its
    confidence tier is below `MIN_PCTL_TIER`. `V2ContextEvidenceError` for
    a malformed PRESENT `oi_change_pct_median`/`percentile_rank`/
    `oi_direction_agreement` (non-finite, non-numeric, an agreement/rank
    outside `[0.0, 1.0]`) — never clamped.

    **Validation order (load-bearing).** Every PRESENT consensus value
    (`oi_change_pct_median`, `oi_direction_agreement`) is validated for
    corruption BEFORE checking whether the OTHER one is missing or
    looking up the percentile row at all — a malformed present raw OI or
    agreement is never masked by a coincidentally-missing peer field or a
    missing percentile row. Symmetrically, once a percentile row is
    found, its `confidence_tier` and any PRESENT `percentile_rank` are
    validated before the `None`/tier-floor short-circuits run."""
    consensus = inputs.consensus
    if consensus is None:
        return None

    oi_raw = consensus.get("oi_change_pct_median")
    oi_agreement = consensus.get("oi_direction_agreement")

    # Validate every PRESENT consensus value before checking whether the
    # OTHER one is missing or looking up the percentile row.
    oi_raw_v = (_validate_finite_numeric(oi_raw, "consensus.oi_change_pct_median")
                if oi_raw is not None else None)
    oi_agreement_v = (_validate_unit_interval(oi_agreement, "consensus.oi_direction_agreement")
                       if oi_agreement is not None else None)

    if oi_raw_v is None or oi_agreement_v is None:
        return None

    snapshot = find_consensus_percentile(
        inputs, metric=_OI_METRIC, percentile_window=percentile_window)
    if snapshot is None:
        return None

    rank = snapshot.get("percentile_rank")
    tier = snapshot.get("confidence_tier")
    tier_usable = _percentile_tier_usable(tier)
    oi_rank = _validate_unit_interval(rank, "percentile_rank") if rank is not None else None

    if oi_rank is None:
        return None
    if not tier_usable:
        return None

    if oi_raw_v > 0:
        strength = max(0.0, 2.0 * oi_rank - 1.0)
        return +strength * oi_agreement_v
    elif oi_raw_v < 0:
        strength = max(0.0, 1.0 - 2.0 * oi_rank)
        return -strength * oi_agreement_v
    else:
        return 0.0
