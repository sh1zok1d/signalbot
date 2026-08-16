"""
V2 1h bias engine (Stage 4 — Context Engines, PR 3 of ~3, FINAL planned
Stage 4 PR, docs/FORECASTING_ROADMAP.md §I stage 4).

PR 1 (`context_evidence.py`, merged) built the shared mathematical
vocabulary. PR 2 (`regime_4h.py`, merged) answered "what is the
established 4h market regime?" This module answers a deliberately
**different**, lighter question — `docs/V2_CORRECTNESS_ACCEPTANCE_
CONTRACT.md` §4.3's own framing — "which way does the nearer-term tape
lean, if at all?":

    classify_1h_bias(inputs: V2TimeframeInputs) -> V2BiasResult

Exactly four bias states (§4.3):

    BULLISH, BEARISH, NEUTRAL_NOT_ESTABLISHED, "UNAVAILABLE"

**Frozen §4.3 decision tree (evaluated in order):**

    1. if bias_evi is UNAVAILABLE, or confidence < BIAS_MIN_CONFIDENCE,
       or coverage < BIAS_MIN_COVERAGE:
           bias = UNAVAILABLE

    2. elif bias_evi >= BIAS_THRESHOLD and agreement >= BIAS_MIN_AGREEMENT:
           bias = BULLISH

    3. elif bias_evi <= -BIAS_THRESHOLD and agreement >= BIAS_MIN_AGREEMENT:
           bias = BEARISH

    4. else:
           bias = NEUTRAL_NOT_ESTABLISHED

Direction is decided by `bias_evi`'s own sign alone; `agreement` is a gate
only (it can never itself create direction). Unlike the 4h regime engine,
there is deliberately **no OI-confirmation step here at all** — §4.4
assigns OI modulation to the 4h regime exclusively, so this module never
reads `oi_confirmation`/`oi_change_pct_median`/`oi_direction_agreement`,
and never reads `compression_score`/`range_width_pct_median` either
(compression awareness also belongs to regime only). This is the
independence/anti-double-counting boundary §4.4 freezes — the same 1h
impulsive move is never summed as a second vote on top of the 4h regime's
own OI-modulated read.

**`NEUTRAL_NOT_ESTABLISHED` is a real, successfully-computed result — not
missingness (§21).** It means the computation SUCCEEDED but a directional
lean could not be firmly established: usable evidence below `BIAS_
THRESHOLD`, a raw price value of exactly zero (`bias_evi == 0.0`,
genuinely neutral, per §4.1), or `agreement` below `BIAS_MIN_AGREEMENT`
(including `agreement` itself being legitimately absent — a missing
*gate*, not a missing *availability* input). This is fundamentally
different from `"UNAVAILABLE"`, which means the computation could not run
at all (missing/too-immature price evidence, or a missing/below-floor
`consensus_confidence`/`min_coverage_ratio`). Stage 5 relies on this exact
distinction (`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §7.0b: an
`UNAVAILABLE` bias fails closed for new episode formation as a
data-availability reason, distinct from a genuinely-measured
`NEUTRAL_NOT_ESTABLISHED`, which is not by itself disqualifying) — this
module never collapses either state into the other, and never returns
`None`/`False`/a third spelling for either.

**Deliberately NOT the 4h regime's "missing DATA vs. tier-only
UNAVAILABLE" distinction.** §4.2 step 1 requires re-deriving "missing
data, not merely tier" for the 4h regime specifically (see
`regime_4h.py`'s own docstring) — §4.3 does not: "if bias_evi is
UNAVAILABLE" is unconditional, so EVERY cause `normalized_evidence()`
collapses into `None` (a genuinely-missing exact percentile row, a
`None` `value`/`percentile_rank`, or a fully-PRESENT row whose
`confidence_tier` merely sits below `MIN_PCTL_TIER`) yields
`bias = "UNAVAILABLE"` here, with no exception. Generalizing regime's
missing-data re-derivation into this module would be wrong — a
tier-only-unavailable 1h price row is `"UNAVAILABLE"`, not
`NEUTRAL_NOT_ESTABLISHED`.

**Corruption is not missingness (§21).** Every PRESENT field this module
reads (`consensus_confidence`, `min_coverage_ratio`,
`price_direction_agreement`) is validated for corruption BEFORE any
unavailable/threshold short-circuit can hide it — mirroring PR 1/PR 2's
own corruption-precedence posture. A `V2ContextEvidenceError` raised by
`normalized_evidence()` for genuinely malformed PRESENT evidence is never
silently downgraded to `"UNAVAILABLE"`; it is re-raised as `V2BiasError`,
exception-chained.

**No ULP tolerance needed here.** Unlike `regime_4h.py`'s `0.40`/`-0.40`
boundaries, `BIAS_THRESHOLD = 0.25` and its corresponding exact percentile
boundaries (`p = 0.625` for `+0.25`, `p = 0.375` for `-0.25`) are dyadic
and land bit-exact through `normalized_evidence`'s own arithmetic in both
signed branches — verified directly: `2.0*0.625 - 1.0 == 0.25` and
`-(1.0 - 2.0*0.375) == -0.25`, both exactly, no rounding gap. A plain
inclusive `>=`/`<=` comparison against the literal `BIAS_THRESHOLD` is
therefore sufficient; this module does not import `regime_4h.py`'s
private ULP-comparison helpers, and does not invent a new tolerance
policy for a boundary that does not need one.

**Pure module.** No DB, no `asyncpg`, no network, no filesystem, no
clock, no config loading, no `random`/`uuid`/`subprocess`. Consumes only
the already-immutable Stage 3 `V2TimeframeInputs` and PR 1's
`normalized_evidence()` — no `T` parameter, no reader, no wall clock:
`inputs` already carries the exact selected 1h bucket. Every public
function is synchronous.
"""
from __future__ import annotations

from collections.abc import Mapping as _AbcMapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from analytics.forecasting_v2.aligned_inputs import V2TimeframeInputs
from analytics.forecasting_v2.context_evidence import (
    V2ContextEvidenceError,
    normalized_evidence,
)

__all__ = [
    "V2BiasError",
    "BULLISH",
    "BEARISH",
    "NEUTRAL_NOT_ESTABLISHED",
    "BIAS_UNAVAILABLE",
    "BIASES",
    "BIAS_MIN_CONFIDENCE",
    "BIAS_MIN_COVERAGE",
    "BIAS_THRESHOLD",
    "BIAS_MIN_AGREEMENT",
    "V2BiasResult",
    "classify_1h_bias",
]


class V2BiasError(ValueError):
    """Malformed/inconsistent input: a non-`V2TimeframeInputs` argument, a
    wrong `timeframe`, a present-but-non-`Mapping`/mismatched-identity
    `consensus`, a malformed PRESENT `consensus_confidence`/
    `min_coverage_ratio`/`price_direction_agreement`, an invalid
    `V2BiasResult`, or a `V2ContextEvidenceError` raised by
    `normalized_evidence()` for genuinely corrupted (not missing) evidence
    — always re-raised as this type, exception-chained, never swallowed.
    Never raised for a legitimate inability to establish bias — that
    yields `bias = "UNAVAILABLE"` or `NEUTRAL_NOT_ESTABLISHED` per the
    frozen decision tree, never an exception."""


# ---- exact bias states (§4.3). `BIAS_UNAVAILABLE`'s Python constant name
# is deliberately NOT `UNAVAILABLE` -- so package users never confuse this
# bias-state STRING with PR 1's evidence-primitive representation of
# unavailability, which is the Python value `None`, not a string. The
# underlying output string this constant holds is exactly "UNAVAILABLE". -
BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL_NOT_ESTABLISHED = "NEUTRAL_NOT_ESTABLISHED"
BIAS_UNAVAILABLE = "UNAVAILABLE"

BIASES = (BULLISH, BEARISH, NEUTRAL_NOT_ESTABLISHED, BIAS_UNAVAILABLE)

# ---- frozen V2-v0 parameters (§4.3) — exact fractions, never rounded ------
BIAS_MIN_CONFIDENCE = 50.0
BIAS_MIN_COVERAGE = 2.0 / 3.0
BIAS_THRESHOLD = 0.25
BIAS_MIN_AGREEMENT = 2.0 / 3.0

# Fixed by §4.3's own "Inputs" preamble — not configurable, not a
# parameter. Deliberately lighter/faster-adapting than regime's 4h/30d:
# a 7d window can only ever reach "building" tier (Percentile Contract
# window-reachability), which is exactly MIN_PCTL_TIER's own floor.
_BIAS_TIMEFRAME = "1h"
_BIAS_PERCENTILE_WINDOW = "7d"
_PRICE_METRIC = "price_move_pct_median"


# ---- UTC-whole-minute datetime validation (mirrors the same posture
# storage/v2_alignment_readers.py, aligned_inputs.py, context_evidence.py,
# and regime_4h.py already use elsewhere in V2 — a small local, private
# copy, not a cross-module import) -------------------------------------------
def _validate_utc_datetime(value: Any, name: str) -> datetime:
    if type(value) is not datetime:
        raise V2BiasError(f"{name} must be a datetime, got {type(value).__name__}: {value!r}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise V2BiasError(f"{name} must be timezone-aware, got {value!r}")
    if value.utcoffset() != timedelta(0):
        raise V2BiasError(f"{name} must be UTC (offset 0), got offset {value.utcoffset()}")
    if value.second != 0 or value.microsecond != 0:
        raise V2BiasError(
            f"{name} must be a whole minute (no seconds/microseconds), got {value!r}")
    return value


@dataclass(frozen=True)
class V2BiasResult:
    """One immutable 1h bias classification, for exactly one aligned 1h
    bucket."""
    bucket_ts: datetime
    bias: str

    def __post_init__(self) -> None:
        _validate_utc_datetime(self.bucket_ts, "bucket_ts")
        if self.bias not in BIASES:
            raise V2BiasError(f"bias must be one of {BIASES}, got {self.bias!r}")


# ---- numeric validation (mirrors context_evidence.py/regime_4h.py's own
# posture; a small local, private copy — not a cross-module import of
# their private helpers, consistent with this codebase's established
# small-duplication-over-cross-module-private-import precedent) -------------
def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))  # NaN != NaN


def _validate_finite_numeric(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2BiasError(
            f"{name} must be a real number, got {type(value).__name__}: {value!r}")
    v = float(value)
    if not _is_finite(v):
        raise V2BiasError(f"{name} must be finite, got {value!r}")
    return v


def _validate_confidence(value: Any) -> float:
    v = _validate_finite_numeric(value, "consensus_confidence")
    if not (0.0 <= v <= 100.0):
        raise V2BiasError(f"consensus_confidence must be within [0.0, 100.0], got {v!r}")
    return v


def _validate_unit_ratio(value: Any, name: str) -> float:
    v = _validate_finite_numeric(value, name)
    if not (0.0 <= v <= 1.0):
        raise V2BiasError(f"{name} must be within [0.0, 1.0], got {v!r}")
    return v


def classify_1h_bias(inputs: V2TimeframeInputs) -> V2BiasResult:
    """Deterministically classify the 1h bias for `inputs`' already-
    selected bucket, per §4.3's frozen decision tree (see module docstring
    for the exact tree and why this is deliberately lighter than the 4h
    regime engine). Pure — no I/O, no clock; the same `inputs` always
    yields the same `V2BiasResult`.

    Raises `V2BiasError` for: `inputs.timeframe != "1h"`; a PRESENT
    `inputs.consensus` that is not a `Mapping`, or whose `timeframe`/
    `bucket_ts` do not match `inputs`; a malformed PRESENT
    `consensus_confidence`/`min_coverage_ratio`/`price_direction_agreement`;
    or a `V2ContextEvidenceError` from `normalized_evidence()` for
    genuinely corrupted (not missing) evidence — re-raised here,
    exception-chained. Every such validation runs BEFORE the field it
    guards can be used in an unavailable/threshold short-circuit, so
    malformed PRESENT data is never masked by an unrelated gate."""
    if not isinstance(inputs, V2TimeframeInputs):
        raise V2BiasError(f"inputs must be a V2TimeframeInputs, got {type(inputs).__name__}")
    if inputs.timeframe != _BIAS_TIMEFRAME:
        raise V2BiasError(
            f"classify_1h_bias requires inputs.timeframe == {_BIAS_TIMEFRAME!r}, "
            f"got {inputs.timeframe!r}")

    # ---- §4.3 "Inputs": bias_evi. Deliberately no missing-data-vs-tier-only
    # re-derivation here (see module docstring) -- every None cause from
    # normalized_evidence() means bias = UNAVAILABLE. A V2ContextEvidenceError
    # means genuinely corrupted PRESENT data -- re-raised, never downgraded.
    try:
        bias_evi = normalized_evidence(
            inputs, metric=_PRICE_METRIC, percentile_window=_BIAS_PERCENTILE_WINDOW)
    except V2ContextEvidenceError as exc:
        raise V2BiasError(f"malformed price evidence input: {exc}") from exc

    # ---- consensus identity + PRESENT-field validation (corruption
    # precedence: every present field is validated here, unconditionally,
    # BEFORE step 1's threshold comparisons ever run). ----------------------
    consensus = inputs.consensus
    confidence: Optional[float] = None
    coverage: Optional[float] = None
    agreement: Optional[float] = None
    if consensus is not None:
        if not isinstance(consensus, _AbcMapping):
            raise V2BiasError(
                f"inputs.consensus must be a Mapping, got {type(consensus).__name__}")
        if consensus.get("timeframe") != _BIAS_TIMEFRAME:
            raise V2BiasError(
                "inputs.consensus.timeframe does not match the 1h bias timeframe")
        if consensus.get("bucket_ts") != inputs.bucket_ts:
            raise V2BiasError("inputs.consensus.bucket_ts does not match inputs.bucket_ts")

        raw_confidence = consensus.get("consensus_confidence")
        raw_coverage = consensus.get("min_coverage_ratio")
        raw_agreement = consensus.get("price_direction_agreement")

        if raw_confidence is not None:
            confidence = _validate_confidence(raw_confidence)
        if raw_coverage is not None:
            coverage = _validate_unit_ratio(raw_coverage, "min_coverage_ratio")
        if raw_agreement is not None:
            agreement = _validate_unit_ratio(raw_agreement, "price_direction_agreement")

    # ---- STEP 1: UNAVAILABLE hard gate -------------------------------------
    if (
        bias_evi is None
        or consensus is None
        or confidence is None
        or coverage is None
        or confidence < BIAS_MIN_CONFIDENCE
        or coverage < BIAS_MIN_COVERAGE
    ):
        return V2BiasResult(bucket_ts=inputs.bucket_ts, bias=BIAS_UNAVAILABLE)

    # ---- STEP 2/3: directional candidate, agreement as a gate only (never
    # itself a direction source); 0.25/-0.25 need no ULP tolerance (see
    # module docstring). -----------------------------------------------------
    if bias_evi >= BIAS_THRESHOLD and agreement is not None and agreement >= BIAS_MIN_AGREEMENT:
        return V2BiasResult(bucket_ts=inputs.bucket_ts, bias=BULLISH)
    if bias_evi <= -BIAS_THRESHOLD and agreement is not None and agreement >= BIAS_MIN_AGREEMENT:
        return V2BiasResult(bucket_ts=inputs.bucket_ts, bias=BEARISH)

    # ---- STEP 4: NEUTRAL_NOT_ESTABLISHED -- a real, successfully-computed
    # result, never confused with BIAS_UNAVAILABLE (see module docstring). --
    return V2BiasResult(bucket_ts=inputs.bucket_ts, bias=NEUTRAL_NOT_ESTABLISHED)
