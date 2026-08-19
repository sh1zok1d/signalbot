"""
V2 4h regime engine (Stage 4 — Context Engines, PR 2 of ~3,
docs/FORECASTING_ROADMAP.md §I stage 4).

PR 1 (`context_evidence.py`, merged) built the shared mathematical
vocabulary: `normalized_evidence`, `compression_score`, and
`oi_confirmation`. This PR answers exactly ONE question with that
vocabulary — `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §4.2's own
framing — "what is the established 4h market regime?":

    `classify_4h_regime(inputs: V2TimeframeInputs) -> V2RegimeResult`

Exactly four regime identities (§4.2):

    BULLISH_TRENDING, BEARISH_TRENDING, NON_DIRECTIONAL, INSUFFICIENT_DATA

`NON_DIRECTIONAL` additionally carries an `is_compressed: bool` flag —
deliberately one state with a flag, not a fifth identity, since "how
tight is the non-trend" is a magnitude question, not a new regime
identity. This engine does **not** choose a trade — no `LONG`/`SHORT`,
setup, confidence, entry, or episode state exists anywhere in this
module. No 1h bias, no combined context snapshot, no setup detector, no
`directional_context_gate`, no state machine, no runtime wiring — those
are Stage 4 PR 3/~3 and Stage 5.

**Frozen §4.2 decision tree (evaluated in order):**

    1. if price_evi or comp is UNAVAILABLE due to missing DATA (not
       merely tier), or consensus is missing, or the price_structure
       FAMILY's own confidence/coverage (§6.3a — never the global
       consensus_confidence/min_coverage_ratio rollup) are missing or
       below their floors:
           regime = INSUFFICIENT_DATA
       (oi_confirmation UNAVAILABLE does NOT by itself force this — OI is
       a modulating veto input, not a required directional one.)

    2. elif |price_evi| >= REGIME_TREND_THRESHOLD
         and agreement >= REGIME_MIN_AGREEMENT
         and not (oi_confirmation is available
                  and the oi FAMILY's own confidence/coverage (§6.3a) pass
                  and oi_confirmation <= REGIME_OI_VETO):
           regime = BULLISH_TRENDING if price_evi > 0 else BEARISH_TRENDING
       (§6.3a: if OI itself is unavailable or fails its OWN family
       quality gate, the veto simply cannot apply — this never forces the
       whole regime to INSUFFICIENT_DATA solely because OI's family
       quality is insufficient.)

    3. else:
           regime = NON_DIRECTIONAL, is_compressed = (comp is not None
                                                        and comp >= REGIME_COMPRESSION)

**Per-family quality gating (§6.3a, `family_quality.py`).** STEP 1's
confidence/coverage floor and STEP 2's OI-veto quality precondition are
each scoped to exactly the ONE metric family the decision actually
consumes (`price_structure` for STEP 1, `oi` for the veto) — sourced from
the already-persisted `coverage_by_metric`/`data_confidence_by_metric`
per-family maps, never the global `consensus_confidence`/
`min_coverage_ratio` rollup a family this decision does not consume
(`volume`/`taker_flow`/`funding`/`liquidations`) could otherwise silently
drag down. A malformed PRESENT per-family map raises `V2RegimeError`
(chained from `V2FamilyQualityError`), never silently downgraded to
ordinary unavailability.

Direction is **always** decided by `price_evi`'s own sign alone —
`agreement` is a gate only (it can never itself create direction), and
`oi_confirmation` is an optional, symmetric VETO only (it can never
itself create direction, and rising OI can never veto — only
`oi_confirmation <= REGIME_OI_VETO`, i.e. sufficiently strong OPPOSING
OI, vetoes). `oi_confirmation` is deliberately evaluated ONLY once a
price+agreement candidate already exists (§4.2's own "elif" structure) —
a malformed/missing OI input is never even consulted when there is no
candidate to modulate in the first place.

**Missing DATA vs. tier-only UNAVAILABLE — load-bearing, easy to get
wrong.** `normalized_evidence`/`compression_score` (PR 1) both collapse
two different causes into the same `None`: (a) the exact percentile row
genuinely does not exist, or its `value`/`percentile_rank` is `None`
("missing data"), and (b) the row is fully PRESENT but its
`confidence_tier` is below `MIN_PCTL_TIER` ("tier-only unavailable" — a
real, PRESENT distribution that is simply too immature to score from).
§4.2 step 1 explicitly requires the FIRST cause, "not merely tier", to
force `INSUFFICIENT_DATA`. This module therefore independently re-derives
"missing data" via `find_consensus_percentile()` (PR 1's own exact
lookup primitive) for the two MANDATORY families (price, compression),
checking only row-existence/`value`/`percentile_rank` — never
`confidence_tier` — and never conflates a tier-only-unavailable
`normalized_evidence()`/`compression_score()` result with a truly-missing
one. A tier-only-unavailable price (evidence `None`, but NOT missing
data) simply cannot satisfy the step-2 trend condition (`price_evi is
not None and ...`), so it falls through to `NON_DIRECTIONAL` — never
`INSUFFICIENT_DATA` merely because a percentile hasn't matured yet.

**Corruption is not missingness (§21).** Wherever this module reads a
PRESENT field it depends on (`consensus_confidence`, `min_coverage_ratio`,
`price_direction_agreement`, or a PR 1 primitive's own malformed-input
signal), that field is validated for corruption BEFORE any
missingness/threshold short-circuit can hide it — mirroring PR 1's own
corruption-precedence hardening. A `V2ContextEvidenceError` raised by a
PR 1 primitive is never silently downgraded to `INSUFFICIENT_DATA`; it is
re-raised as `V2RegimeError` (exception-chained, cause preserved).

**Numeric-representation hardening at the two derived-arithmetic
boundaries (load-bearing).** §4.2's decision boundaries are inclusive
(`>=`/`<=`) at exact V2-v0 literals (`REGIME_TREND_THRESHOLD = 0.40`,
`REGIME_OI_VETO = -0.40`). `0.40` is not a dyadic rational, so it has no
exact IEEE-754 double representation, and — more importantly — the
VALUES being compared against it are not read directly; they are the
OUTPUT of PR 1's affine `normalized_evidence` transform
(`2p-1`/`1-2p`) or the `oi_confirmation` product (`strength *
agreement`). §23.1 states the frozen mathematical equivalence
`price_evi >= 0.40 iff percentile_rank >= 0.70` (and the negative-branch
mirror at `p <= 0.30`) — but evaluating `2.0*0.70 - 1.0` in Python
produces `0.3999999999999999`, one to a few ULPs below the literal
`0.40`, purely from double-rounding in that arithmetic chain (verified:
the negative-branch mirror at `p=0.30` happens to round-trip to exactly
`-0.4`, which is why this class of bug is easy to miss — it does not
reproduce symmetrically). Comparing the literal `>= REGIME_TREND_THRESHOLD`
therefore incorrectly rejects the mathematically-exact contract boundary
for the positive branch, while accepting it for the negative branch —
an unintended sign asymmetry. The same class of rounding affects the OI
veto product (e.g. `oi_rank=0.20`, `agreement=2/3` is mathematically
exactly `-0.40`, but the float product lands one ULP above it).

The fix (`_ge_inclusive`/`_le_inclusive` below) is NOT a model/product
tolerance — it is numeric-representation hardening, derived SOLELY from
the threshold literal's own IEEE-754 ULP spacing via `math.nextafter`,
applied ONLY at these two comparisons (`abs(price_evi) >=
REGIME_TREND_THRESHOLD`, `oi <= REGIME_OI_VETO`) where a derived
floating-point computation is compared against a non-dyadic literal. It
is not exposed as configuration, does not change
`REGIME_TREND_THRESHOLD`/`REGIME_OI_VETO`'s own values, and a value that
is genuinely — in real, non-representational terms — below the frozen
threshold remains classified as below it (the tolerance is a few ULPs
wide, many orders of magnitude narrower than any realistic "just below
threshold" test vector). The other four thresholds
(`REGIME_MIN_CONFIDENCE`, `REGIME_MIN_COVERAGE`, `REGIME_MIN_AGREEMENT`,
`REGIME_COMPRESSION`) are NOT widened this way: `consensus_confidence`/
`min_coverage_ratio`/`price_direction_agreement` are read directly off
`inputs.consensus` with no derived arithmetic applied by this module (a
caller-supplied `2.0/3.0` compares bit-identically against this module's
own `2.0/3.0` literal), and `compression_score`'s `1.0 - percentile_rank`
happens to be exactly reachable at `REGIME_COMPRESSION = 0.75` (both
`0.25` and `0.75` are exact dyadic rationals, so no rounding occurs) — so
none of the other four have the representational gap the trend/OI-veto
boundaries do, and none needed adjustment.

**Pure module.** No DB, no `asyncpg`, no network, no filesystem, no
clock, no config loading, no `random`/`uuid`/`subprocess`. Consumes only
the already-immutable Stage 3 `V2TimeframeInputs` and PR 1's public
evidence primitives — no `T` parameter, no reader, no wall clock:
`inputs` already carries the exact selected 4h bucket. Every public
function is synchronous.
"""
from __future__ import annotations

import math
from collections.abc import Mapping as _AbcMapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from analytics.forecasting_v2.aligned_inputs import V2TimeframeInputs
from analytics.forecasting_v2.context_evidence import (
    V2ContextEvidenceError,
    compression_score,
    find_consensus_percentile,
    normalized_evidence,
    oi_confirmation,
)
from analytics.forecasting_v2.family_quality import (
    V2FamilyQualityError,
    family_quality,
    family_quality_ok,
)

__all__ = [
    "V2RegimeError",
    "BULLISH_TRENDING",
    "BEARISH_TRENDING",
    "NON_DIRECTIONAL",
    "INSUFFICIENT_DATA",
    "REGIMES",
    "REGIME_MIN_CONFIDENCE",
    "REGIME_MIN_COVERAGE",
    "REGIME_TREND_THRESHOLD",
    "REGIME_MIN_AGREEMENT",
    "REGIME_OI_VETO",
    "REGIME_COMPRESSION",
    "V2RegimeResult",
    "classify_4h_regime",
]


class V2RegimeError(ValueError):
    """Malformed/inconsistent input: a non-`V2TimeframeInputs` argument, a
    wrong `timeframe`, a present-but-non-`Mapping`/mismatched-identity
    `consensus`, a malformed PRESENT `consensus_confidence`/
    `min_coverage_ratio`/`price_direction_agreement`, an invalid
    `V2RegimeResult`, or a `V2ContextEvidenceError` raised by a PR 1
    evidence primitive for genuinely corrupted (not missing) data —
    always re-raised as this type, exception-chained, never swallowed.
    Never raised for legitimately MISSING data — that yields
    `INSUFFICIENT_DATA` or `NON_DIRECTIONAL` per the frozen decision
    tree, never an exception."""


# ---- exact regime identities (§4.2) -----------------------------------------
BULLISH_TRENDING = "BULLISH_TRENDING"
BEARISH_TRENDING = "BEARISH_TRENDING"
NON_DIRECTIONAL = "NON_DIRECTIONAL"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

REGIMES = (BULLISH_TRENDING, BEARISH_TRENDING, NON_DIRECTIONAL, INSUFFICIENT_DATA)

# ---- frozen V2-v0 parameters (§4.2 table) — exact fractions, never rounded --
REGIME_MIN_CONFIDENCE = 50.0
REGIME_MIN_COVERAGE = 2.0 / 3.0
REGIME_TREND_THRESHOLD = 0.40
REGIME_MIN_AGREEMENT = 2.0 / 3.0
REGIME_OI_VETO = -0.40
REGIME_COMPRESSION = 0.75

# Fixed by §4.2's own "Inputs" preamble — not configurable, not a parameter.
_REGIME_TIMEFRAME = "4h"
_REGIME_PERCENTILE_WINDOW = "30d"
_PRICE_METRIC = "price_move_pct_median"
_COMPRESSION_METRIC = "range_width_pct_median"


# ---- UTC-whole-minute datetime validation (mirrors the same posture
# storage/v2_alignment_readers.py, aligned_inputs.py, and
# context_evidence.py already use elsewhere in V2 — a small local,
# private copy, not a cross-module import) ----------------------------------
def _validate_utc_datetime(value: Any, name: str) -> datetime:
    if type(value) is not datetime:
        raise V2RegimeError(f"{name} must be a datetime, got {type(value).__name__}: {value!r}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2RegimeError(f"{name} must be timezone-aware, got {value!r}")
    if value.utcoffset() != timedelta(0):
        raise V2RegimeError(f"{name} must be UTC (offset 0), got offset {value.utcoffset()}")
    if value.second != 0 or value.microsecond != 0:
        raise V2RegimeError(
            f"{name} must be a whole minute (no seconds/microseconds), got {value!r}")
    return value


@dataclass(frozen=True)
class V2RegimeResult:
    """One immutable 4h regime classification, for exactly one aligned 4h
    bucket. `is_compressed` is `bool` if and only if `regime ==
    NON_DIRECTIONAL` — §4.2 attaches the compression flag specifically to
    the non-directional case; every other regime carries `is_compressed
    = None` (compression is never itself a regime identity, and is never
    computed/attached for a trending or insufficient-data result).

    `price_evi`/`compression_score` (§4.1a) preserve BY VALUE the exact
    `normalized_evidence`/`compression_score` PR 1 evidence this engine
    itself computed while deciding `regime`/`is_compressed` — never
    recomputed downstream (Stage 5/6 read these fields instead of
    re-deriving them from Stage 3 percentile history). Either may
    legitimately be `None` (the same UNAVAILABLE semantics PR 1's own
    primitives already return — missing data, tier-only-unavailable, or
    simply not computed for a branch that never needed it); a `None` here
    is never itself an error, only a value inconsistent with `regime`/
    `is_compressed` is."""
    bucket_ts: datetime
    regime: str
    is_compressed: Optional[bool]
    price_evi: Optional[float]
    compression_score: Optional[float]

    def __post_init__(self) -> None:
        _validate_utc_datetime(self.bucket_ts, "bucket_ts")
        if self.regime not in REGIMES:
            raise V2RegimeError(f"regime must be one of {REGIMES}, got {self.regime!r}")
        if self.regime == NON_DIRECTIONAL:
            if not isinstance(self.is_compressed, bool):
                raise V2RegimeError(
                    "is_compressed must be a bool when regime is NON_DIRECTIONAL, "
                    f"got {self.is_compressed!r}")
        elif self.is_compressed is not None:
            raise V2RegimeError(
                f"is_compressed must be None for regime {self.regime!r}, "
                f"got {self.is_compressed!r}")

        price_evi: Optional[float] = None
        if self.price_evi is not None:
            price_evi = _validate_finite_numeric(self.price_evi, "price_evi")
            if not (-1.0 <= price_evi <= 1.0):
                raise V2RegimeError(f"price_evi must be within [-1.0, 1.0], got {price_evi!r}")

        comp: Optional[float] = None
        if self.compression_score is not None:
            comp = _validate_finite_numeric(self.compression_score, "compression_score")
            if not (0.0 <= comp <= 1.0):
                raise V2RegimeError(
                    f"compression_score must be within [0.0, 1.0], got {comp!r}")

        # §4.1a: label and numerical evidence must be internally consistent
        # -- a directly-constructed impossible/malformed result fails closed.
        if self.regime == BULLISH_TRENDING:
            if price_evi is None or not (price_evi > 0):
                raise V2RegimeError(
                    f"price_evi must be a positive float for regime {BULLISH_TRENDING!r}, "
                    f"got {self.price_evi!r}")
            # Tech-lead amendment round 1, item 4: classify_4h_regime()
            # requires abs(price_evi) >= REGIME_TREND_THRESHOLD (via the
            # SAME representation-safe _ge_inclusive() the real classifier
            # uses, never an invented epsilon) to ever produce a trending
            # label -- a directly-constructed result claiming
            # BULLISH_TRENDING with evidence below that threshold is
            # impossible under the owning classifier and must fail closed.
            # Only this NECESSARY condition (provable from price_evi alone)
            # is enforced -- never agreement/OI veto, which this result
            # does not carry by value.
            if not _ge_inclusive(abs(price_evi), REGIME_TREND_THRESHOLD):
                raise V2RegimeError(
                    f"price_evi ({price_evi!r}) must satisfy abs(price_evi) >= "
                    f"REGIME_TREND_THRESHOLD ({REGIME_TREND_THRESHOLD!r}) for regime "
                    f"{BULLISH_TRENDING!r}")
        elif self.regime == BEARISH_TRENDING:
            if price_evi is None or not (price_evi < 0):
                raise V2RegimeError(
                    f"price_evi must be a negative float for regime {BEARISH_TRENDING!r}, "
                    f"got {self.price_evi!r}")
            if not _ge_inclusive(abs(price_evi), REGIME_TREND_THRESHOLD):
                raise V2RegimeError(
                    f"price_evi ({price_evi!r}) must satisfy abs(price_evi) >= "
                    f"REGIME_TREND_THRESHOLD ({REGIME_TREND_THRESHOLD!r}) for regime "
                    f"{BEARISH_TRENDING!r}")
        elif self.regime == NON_DIRECTIONAL:
            expected_compressed = comp is not None and comp >= REGIME_COMPRESSION
            if self.is_compressed != expected_compressed:
                raise V2RegimeError(
                    "is_compressed is inconsistent with compression_score -- expected "
                    f"{expected_compressed!r} (compression_score={self.compression_score!r}), "
                    f"got {self.is_compressed!r}")


# ---- numeric validation (mirrors context_evidence.py's own posture; a
# small local, private copy — not a cross-module import of its private
# helpers, consistent with this codebase's established small-duplication-
# over-cross-module-private-import precedent) -------------------------------
def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))  # NaN != NaN


def _validate_finite_numeric(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2RegimeError(
            f"{name} must be a real number, got {type(value).__name__}: {value!r}")
    v = float(value)
    if not _is_finite(v):
        raise V2RegimeError(f"{name} must be finite, got {value!r}")
    return v


def _validate_unit_ratio(value: Any, name: str) -> float:
    v = _validate_finite_numeric(value, name)
    if not (0.0 <= v <= 1.0):
        raise V2RegimeError(f"{name} must be within [0.0, 1.0], got {v!r}")
    return v


# ---- IEEE-754 representation hardening for the two derived-arithmetic
# inclusive boundaries only (see module docstring's numeric-hardening
# section for the full rationale and the concrete counter-example) ---------
# A handful of ULPs comfortably covers the observed 1-2 ULP rounding gaps
# from the affine normalized_evidence transform and the OI strength*
# agreement product, while remaining many orders of magnitude narrower
# than any realistic "genuinely below threshold" percentile-rank vector.
_BOUNDARY_ULP_TOLERANCE = 4


def _floor_by_ulps(threshold: float, ulps: int) -> float:
    """`threshold`, walked `ulps` IEEE-754 steps toward -infinity."""
    value = threshold
    for _ in range(ulps):
        value = math.nextafter(value, -math.inf)
    return value


def _ceil_by_ulps(threshold: float, ulps: int) -> float:
    """`threshold`, walked `ulps` IEEE-754 steps toward +infinity."""
    value = threshold
    for _ in range(ulps):
        value = math.nextafter(value, math.inf)
    return value


def _ge_inclusive(value: float, threshold: float) -> bool:
    """`value >= threshold`, tolerant of up to `_BOUNDARY_ULP_TOLERANCE`
    ULPs of floating-point representation error AT `threshold`'s own
    magnitude — never a decimal/model epsilon. Used only for
    `abs(price_evi) >= REGIME_TREND_THRESHOLD`."""
    return value >= _floor_by_ulps(threshold, _BOUNDARY_ULP_TOLERANCE)


def _le_inclusive(value: float, threshold: float) -> bool:
    """`value <= threshold`, tolerant of up to `_BOUNDARY_ULP_TOLERANCE`
    ULPs of floating-point representation error AT `threshold`'s own
    magnitude — never a decimal/model epsilon. Used only for
    `oi_confirmation <= REGIME_OI_VETO`."""
    return value <= _ceil_by_ulps(threshold, _BOUNDARY_ULP_TOLERANCE)


def _is_missing_data(inputs: V2TimeframeInputs, *, metric: str) -> bool:
    """§4.2 step 1's "missing DATA (not merely tier)" test for one
    mandatory evidence family, re-derived directly from PR 1's own exact
    lookup primitive (never from `normalized_evidence()`/
    `compression_score()`'s collapsed `None`, which cannot distinguish
    this from tier-only unavailability): `True` iff the exact percentile
    row does not exist, or its `value` is `None`, or its
    `percentile_rank` is `None`. `confidence_tier` is deliberately never
    consulted here — a fully-present, low-tier row is NOT missing data."""
    try:
        row = find_consensus_percentile(
            inputs, metric=metric, percentile_window=_REGIME_PERCENTILE_WINDOW)
    except V2ContextEvidenceError as exc:
        raise V2RegimeError(f"malformed percentile lookup for {metric!r}: {exc}") from exc
    if row is None:
        return True
    if row.get("value") is None:
        return True
    if row.get("percentile_rank") is None:
        return True
    return False


def classify_4h_regime(inputs: V2TimeframeInputs) -> V2RegimeResult:
    """Deterministically classify the 4h regime for `inputs`' already-
    selected bucket, per §4.2's frozen decision tree (see module
    docstring for the exact tree and the missing-data-vs-tier-only
    distinction this function is careful to preserve). Pure — no I/O, no
    clock; the same `inputs` always yields the same `V2RegimeResult`.

    Raises `V2RegimeError` for: `inputs.timeframe != "4h"`; a PRESENT
    `inputs.consensus` that is not a `Mapping`, or whose `timeframe`/
    `bucket_ts` do not match `inputs`; a malformed PRESENT
    `consensus_confidence`/`min_coverage_ratio`/`price_direction_agreement`;
    or a `V2ContextEvidenceError` from a PR 1 primitive for genuinely
    corrupted (not missing) evidence — re-raised here, exception-chained.
    Every such validation runs BEFORE the field it guards can be used in
    a missingness/threshold short-circuit, so malformed PRESENT data is
    never masked by an unrelated gate."""
    if not isinstance(inputs, V2TimeframeInputs):
        raise V2RegimeError(f"inputs must be a V2TimeframeInputs, got {type(inputs).__name__}")
    if inputs.timeframe != _REGIME_TIMEFRAME:
        raise V2RegimeError(
            f"classify_4h_regime requires inputs.timeframe == {_REGIME_TIMEFRAME!r}, "
            f"got {inputs.timeframe!r}")

    # ---- §4.2 "Inputs": price_evi, comp, and the missing-data-vs-tier-only
    # distinction for both mandatory families. A V2ContextEvidenceError from
    # either primitive means genuinely corrupted PRESENT data -- re-raised,
    # never downgraded to INSUFFICIENT_DATA.
    price_missing_data = _is_missing_data(inputs, metric=_PRICE_METRIC)
    comp_missing_data = _is_missing_data(inputs, metric=_COMPRESSION_METRIC)
    try:
        price_evi = normalized_evidence(
            inputs, metric=_PRICE_METRIC, percentile_window=_REGIME_PERCENTILE_WINDOW)
        comp = compression_score(inputs, percentile_window=_REGIME_PERCENTILE_WINDOW)
    except V2ContextEvidenceError as exc:
        raise V2RegimeError(f"malformed price/compression evidence input: {exc}") from exc

    # ---- consensus identity + PRESENT-field validation (corruption
    # precedence: every present field is validated here, unconditionally,
    # BEFORE step 1's threshold comparisons ever run). ----------------------
    consensus = inputs.consensus
    agreement: Optional[float] = None
    if consensus is not None:
        if not isinstance(consensus, _AbcMapping):
            raise V2RegimeError(
                f"inputs.consensus must be a Mapping, got {type(consensus).__name__}")
        if consensus.get("timeframe") != _REGIME_TIMEFRAME:
            raise V2RegimeError(
                "inputs.consensus.timeframe does not match the 4h regime timeframe")
        if consensus.get("bucket_ts") != inputs.bucket_ts:
            raise V2RegimeError("inputs.consensus.bucket_ts does not match inputs.bucket_ts")

        raw_agreement = consensus.get("price_direction_agreement")
        if raw_agreement is not None:
            agreement = _validate_unit_ratio(raw_agreement, "price_direction_agreement")

    # ---- §6.3a: STEP 1's confidence/coverage gate is scoped to the
    # price_structure family alone -- never the global consensus_confidence/
    # min_coverage_ratio rollup, which a family this decision does not
    # consume (volume/taker_flow/oi/funding/liquidations) could otherwise
    # drag down. `consensus is None` collapses into `confidence is None or
    # coverage is None` below, since family_quality(None, ...) returns
    # (None, None) -- the same "no row at all" unavailability.
    try:
        price_family = family_quality(consensus, family="price_structure")
    except V2FamilyQualityError as exc:
        raise V2RegimeError(f"malformed price_structure family quality: {exc}") from exc
    confidence = price_family.confidence
    coverage = price_family.coverage_ratio

    def _result(regime: str, *, is_compressed: Optional[bool]) -> V2RegimeResult:
        return V2RegimeResult(
            bucket_ts=inputs.bucket_ts, regime=regime, is_compressed=is_compressed,
            price_evi=price_evi, compression_score=comp)

    # ---- STEP 1: mandatory-data hard gate ----------------------------------
    if (
        price_missing_data
        or comp_missing_data
        or confidence is None
        or coverage is None
        or confidence < REGIME_MIN_CONFIDENCE
        or coverage < REGIME_MIN_COVERAGE
    ):
        return _result(INSUFFICIENT_DATA, is_compressed=None)

    # ---- STEP 2: price+agreement candidate, OI evaluated ONLY here as an
    # optional symmetric veto (never a directional vote, never consulted
    # when there is no candidate to modulate). §6.3a: the veto itself also
    # requires OI's OWN family quality to pass -- if OI family quality is
    # insufficient, the veto is UNAVAILABLE/cannot apply, and this MUST NOT
    # force the whole regime to INSUFFICIENT_DATA (OI is a modulating veto
    # input, not a required directional one; that already-frozen §4.2
    # posture is unchanged, only OI's own quality SOURCE is now
    # family-scoped rather than implicitly trusted). ------------------------
    if (
        price_evi is not None
        and _ge_inclusive(abs(price_evi), REGIME_TREND_THRESHOLD)
        and agreement is not None
        and agreement >= REGIME_MIN_AGREEMENT
    ):
        try:
            oi = oi_confirmation(inputs, percentile_window=_REGIME_PERCENTILE_WINDOW)
        except V2ContextEvidenceError as exc:
            raise V2RegimeError(f"malformed OI evidence input: {exc}") from exc
        try:
            oi_quality_ok = family_quality_ok(consensus, family="oi")
        except V2FamilyQualityError as exc:
            raise V2RegimeError(f"malformed oi family quality: {exc}") from exc

        vetoed = oi is not None and oi_quality_ok and _le_inclusive(oi, REGIME_OI_VETO)
        if not vetoed:
            if price_evi > 0:
                return _result(BULLISH_TRENDING, is_compressed=None)
            elif price_evi < 0:
                return _result(BEARISH_TRENDING, is_compressed=None)
            # price_evi == 0.0 cannot satisfy abs(price_evi) >= REGIME_TREND_THRESHOLD
            # (a strictly positive threshold) -- unreachable, but falls through to
            # STEP 3 rather than asserting, matching this module's fail-safe posture.

    # ---- STEP 3: NON_DIRECTIONAL, with the compression flag -----------------
    is_compressed = comp is not None and comp >= REGIME_COMPRESSION
    return _result(NON_DIRECTIONAL, is_compressed=is_compressed)
