"""
V2 per-family metric-scoped quality gate primitive (§6.3a).

Reads ONLY already-persisted Stage 2 per-family coverage/confidence maps
(`ConsensusFeatureVector.coverage_by_metric`/`.data_confidence_by_metric`,
surfaced on every V2 consensus row this package reads -- via `V2TimeframeInputs
.consensus` (storage/v2_alignment_readers.py) or the equivalent Stage 5 setup
history rows (storage/v2_setup_readers.py) -- as plain JSON-decoded Mappings)
-- never the global `min_coverage_ratio`/`consensus_confidence` rollup, which
§6.3a forbids as a V2 decision gate: a metric family a decision does not
consume must never be able to suppress it.

Pure, synchronous, no I/O, no DB/clock/network.
"""
from __future__ import annotations

from collections.abc import Mapping as _AbcMapping
from typing import Any, Mapping, NamedTuple, Optional

__all__ = [
    "V2FamilyQualityError",
    "FAMILIES",
    "FAMILY_MIN_COVERAGE",
    "FAMILY_MIN_CONFIDENCE",
    "V2FamilyQuality",
    "family_quality",
    "family_quality_ok",
]


class V2FamilyQualityError(ValueError):
    """Malformed PRESENT per-family coverage/confidence data -- a
    structurally-impossible shape for a `consensus` row that genuinely
    exists (Stage 2's own writer, `analytics/feature_engine/consensus.py`,
    always populates every one of the six metric families' entries when a
    consensus row is written at all -- an unconditional loop over `FAMILIES`,
    never a partial write). Never raised for legitimate unavailability -- a
    `None`/absent consensus row is not this error's job; call sites treat
    whole-row absence as ordinary unavailability, per each decision's own
    §6.3a rule."""


# Canonical metric family order (mirrors
# analytics/feature_engine/consensus_models.py::FAMILIES -- not imported
# directly to avoid pulling analytics.feature_engine into this pure,
# dependency-light module; the six names are frozen product vocabulary,
# not a value this module infers or duplicates ownership of).
FAMILIES = ("price_structure", "volume", "taker_flow", "oi", "funding", "liquidations")
_KNOWN_FAMILIES = frozenset(FAMILIES)

# Frozen V2-v0 thresholds (§6.3a: "a required family passes only when its
# own coverage >= 2/3 and confidence >= 50.0") -- the SAME numeric values
# already frozen for the global rollup (§4.2/§4.3's
# REGIME_MIN_COVERAGE/REGIME_MIN_CONFIDENCE, setup_common.py's
# SETUP_MIN_COVERAGE/SETUP_MIN_CONFIDENCE), now applied per family instead
# of globally. Not re-tuned by this hardening pass -- only which
# family/families each decision's gate is scoped to changes, never these
# threshold values themselves.
FAMILY_MIN_COVERAGE = 2.0 / 3.0
FAMILY_MIN_CONFIDENCE = 50.0


class V2FamilyQuality(NamedTuple):
    """One family's own coverage ratio (`[0,1]`) and confidence (`[0,100]`),
    read BY VALUE from an already-persisted consensus row. `None` for either
    field means UNAVAILABLE for that fact specifically (never a sentinel
    `0.0`) -- either the whole consensus row is legitimately absent, or (not
    currently reachable given Stage 2's unconditional per-family write, but
    defensively distinguished here rather than assumed) some future writer
    genuinely omits a family's entry without that being corruption."""
    coverage_ratio: Optional[float]
    confidence: Optional[float]


def _is_finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))  # NaN != NaN


def _validate_finite_numeric(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V2FamilyQualityError(
            f"{name} must be a real number, got {type(value).__name__}: {value!r}")
    v = float(value)
    if not _is_finite(v):
        raise V2FamilyQualityError(f"{name} must be finite, got {value!r}")
    return v


def family_quality(consensus: Optional[Mapping], *, family: str) -> V2FamilyQuality:
    """One metric family's own `coverage_ratio`/`confidence`, sourced
    exclusively from `consensus["coverage_by_metric"][family]["ratio"]` and
    `consensus["data_confidence_by_metric"][family]` -- never the global
    `min_coverage_ratio`/`consensus_confidence` rollup (§6.3a).

    `consensus is None` (the whole consensus row is legitimately absent) ->
    `V2FamilyQuality(None, None)`: not an error, the same "no row at all"
    unavailability every V2 quality gate already treats uniformly.

    A PRESENT `consensus` row's per-family maps are validated defensively:
    `coverage_by_metric`/`data_confidence_by_metric` must each be a Mapping
    containing `family`'s own entry (Stage 2's writer always populates all
    six families whenever it writes a row at all -- a genuinely-written row
    missing one is therefore a structural corruption, not legitimate
    absence: a MISSING family key or a non-Mapping/malformed-shaped entry
    raises `V2FamilyQualityError`). A PRESENT entry whose `ratio`/
    confidence value is itself SQL NULL (`None`) is legitimate unavailable
    quality for that specific fact -- mirrors the same present-key-but-
    null-value convention every other V2 quality gate in this codebase
    already uses -- returned as `None` on the corresponding
    `V2FamilyQuality` field, never an error; a PRESENT non-`None` value
    that is malformed (non-finite, wrong type, out of its `[0,1]`/`[0,100]`
    domain) still raises `V2FamilyQualityError`, never silently coerced."""
    if family not in _KNOWN_FAMILIES:
        raise V2FamilyQualityError(
            f"family must be one of {sorted(_KNOWN_FAMILIES)}, got {family!r}")
    if consensus is None:
        return V2FamilyQuality(None, None)
    if not isinstance(consensus, _AbcMapping):
        raise V2FamilyQualityError(
            f"consensus must be a Mapping, got {type(consensus).__name__}")

    coverage_map = consensus.get("coverage_by_metric")
    if not isinstance(coverage_map, _AbcMapping):
        raise V2FamilyQualityError(
            f"consensus.coverage_by_metric must be a Mapping, got "
            f"{type(coverage_map).__name__}")
    if family not in coverage_map:
        raise V2FamilyQualityError(
            f"consensus.coverage_by_metric is missing required family {family!r}")
    coverage_entry = coverage_map[family]
    if not isinstance(coverage_entry, _AbcMapping):
        raise V2FamilyQualityError(
            f"consensus.coverage_by_metric[{family!r}] must be a Mapping, got "
            f"{type(coverage_entry).__name__}")
    if "ratio" not in coverage_entry:
        raise V2FamilyQualityError(
            f"consensus.coverage_by_metric[{family!r}] is missing required field 'ratio'")
    raw_ratio = coverage_entry["ratio"]
    ratio: Optional[float] = None
    if raw_ratio is not None:
        ratio = _validate_finite_numeric(raw_ratio, f"coverage_by_metric[{family!r}].ratio")
        if not (0.0 <= ratio <= 1.0):
            raise V2FamilyQualityError(
                f"coverage_by_metric[{family!r}].ratio must be within [0.0, 1.0], got {ratio!r}")

    confidence_map = consensus.get("data_confidence_by_metric")
    if not isinstance(confidence_map, _AbcMapping):
        raise V2FamilyQualityError(
            f"consensus.data_confidence_by_metric must be a Mapping, got "
            f"{type(confidence_map).__name__}")
    if family not in confidence_map:
        raise V2FamilyQualityError(
            f"consensus.data_confidence_by_metric is missing required family {family!r}")
    raw_confidence = confidence_map[family]
    confidence: Optional[float] = None
    if raw_confidence is not None:
        confidence = _validate_finite_numeric(raw_confidence, f"data_confidence_by_metric[{family!r}]")
        if not (0.0 <= confidence <= 100.0):
            raise V2FamilyQualityError(
                f"data_confidence_by_metric[{family!r}] must be within [0.0, 100.0], got "
                f"{confidence!r}")

    return V2FamilyQuality(coverage_ratio=ratio, confidence=confidence)


def family_quality_ok(consensus: Optional[Mapping], *, family: str) -> bool:
    """`True` iff `family`'s own coverage/confidence BOTH satisfy the frozen
    V2-v0 family-scoped gate (`>= FAMILY_MIN_COVERAGE`, `>=
    FAMILY_MIN_CONFIDENCE`). `False` for a legitimately-absent consensus row
    or a present-but-below-floor family. Raises `V2FamilyQualityError` for
    malformed PRESENT data (never silently treated as failing the gate) --
    callers that need to distinguish "failed the gate" from "malformed"
    should call `family_quality()` directly instead."""
    q = family_quality(consensus, family=family)
    if q.coverage_ratio is None or q.confidence is None:
        return False
    return q.coverage_ratio >= FAMILY_MIN_COVERAGE and q.confidence >= FAMILY_MIN_CONFIDENCE
