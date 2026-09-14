"""V2 inherited detection-ladder: pure mechanical derivation of all 33 ids.

Binds the approved, independently-reviewed methodology authority
(``AMENDMENT_003`` + ``AMENDMENT_004``, GO_FOR_33_33_IMPLEMENTATION_BINDING,
BLOCKERS=0/MAJORS=0) into executable production code.

This module derives all 33 required-coverage-map conclusion ids, plus the
composite ``FINAL_OVERALL_MECHANICAL_CONCLUSION`` state machine, purely from
authenticated ``WorldRecordV2`` evidence. It accepts NO caller-supplied
scientific conclusion, mapping, override, callback, or strategy object of any
kind. The only inputs are: (a) authenticated evidence records, and (b) frozen,
hash-pinned repository authority (Amendment_003, Amendment_004, the frozen V2
policy fixture, and the frozen V1 TCB). Same evidence + same authority always
yields the same 33 values and the same final conclusion -- there is no branch
in this module that reads a caller-supplied value to decide a scientific
question.

Per-id, per-family logic (statistic, denominator, conditioning population,
threshold, operator) is transcribed directly from the approved Amendment_003
JSON table (31 ids) and the approved Amendment_004 JSON overlay (2 superseded
ids: ``FINAL_OVERALL_MECHANICAL_CONCLUSION``, ``NULL_PER_CANDIDATE_FPR``).
Every frozen numeric threshold and every frozen executable function used here
(``wilson_interval``, ``specificity_verdict``, ``power_verdict``,
``small_band``, ``mechanical_conclusion``) is imported from the pinned V1 TCB,
never re-derived. STAGE 1 (structural completeness) and STAGE 2 (coverage
adequacy) for each of the 33 individual ids remain exactly the frozen V2
policy's own ``mechanical_conclusion_v2`` wrapper -- this module supplies only
the pre-gating "inherited raw value" that wrapper already expected from a
caller, and now computes internally instead.

KNOWN, DISCLOSED, UNRESOLVED GAP (do not paper over -- see
``V2VisibilityStatisticUnavailable``): the frozen V2 policy fixture
(``harness_synthetic_edge_calibration_v2_rank_policy.py``) does not compute a
``GROUND_TRUTH_VISIBLE``-equivalent statistic anywhere. ``evaluate_v2_world``'s
own docstring states plainly: "This fixture stage does not execute bootstrap,
placebo, or visibility." ``WorldRecordV2`` and ``CandidateWorldRecord`` carry
no visibility field. Six conclusion ids/inputs that Amendment_003/004 approved
as machine-executable in fact have no computable input under the CURRENT
frozen V2 fixture: ``VISIBILITY_FLOOR``, ``MODEL_FLOOR`` (its own rule reads
"given VISIBILITY_FLOOR not already binding"), ``TINY_NOISY_ORACLE_DIAGNOSTIC``,
its two aliases ``TINY_NOISY_CONCLUSION`` / ``ORACLE_F03_TINY_NOISY``, and the
``visibility_wilson_upper`` input to ``FINAL_OVERALL_MECHANICAL_CONCLUSION``
itself. This module refuses (raises ``V2VisibilityStatisticUnavailable``)
rather than default the missing statistic to ``None`` -- doing the latter
would silently make the calibration MORE permissive (it would make
``VISIBILITY_FLOOR`` structurally unreachable), which is exactly the kind of
undisclosed choice Amendment_003/004 exist to eliminate. This is a genuine
structural gap in already-frozen V2 authority, not a defect introduced here,
and closing it (e.g. wiring frozen V1's own ``visibility_from_residuals`` into
V2's per-world evaluation) is new science this unit is not authorized to
invent. See the accompanying implementation report:
``IMPLEMENTATION_REQUIRES_NEW_SCIENTIFIC_CHOICE = YES``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    FEATURE_IDS,
    SyntheticExecutionNotAuthorized,
    mechanical_conclusion,
    power_verdict,
    small_band,
    specificity_verdict,
    wilson_interval,
)
from scripts.research.harness_synthetic_edge_calibration_v1_production import (
    _commit_blob,
    _repo_root,
    _sha256_bytes,
)
from scripts.research.harness_synthetic_edge_calibration_v2_rank_policy import (
    CandidateWorldRecord,
    CellAggregateV2,
    WorldRecordV2,
    aggregate_v2_records,
    frozen_required_coverage_map,
)

# --- frozen authority artifact identity (independently reviewed, unmodified) -

AMENDMENT_003_MD_REL = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_AMENDMENT_003.md"
)
AMENDMENT_003_JSON_REL = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_AMENDMENT_003.json"
)
AMENDMENT_004_MD_REL = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_AMENDMENT_004.md"
)
AMENDMENT_004_JSON_REL = (
    "docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_AMENDMENT_004.json"
)

FROZEN_AMENDMENT_003_SHA256 = {
    AMENDMENT_003_MD_REL: "10f26bbaeca30d47051026878ca8afd6622efdb8cc30562e44a7860abe896300",
    AMENDMENT_003_JSON_REL: "f9856e8ed957bf9ed800121ef17c9c73223eee3bc4af2711130f19bf1a59b7db",
}
FROZEN_AMENDMENT_004_SHA256 = {
    AMENDMENT_004_MD_REL: "9002838f4dc14a27a5f83870abb7cad4bd83a5c84abc75723263562045f646ca",
    AMENDMENT_004_JSON_REL: "8c3f9d2d662e5ce807baf4b65f94c145ed84c7337c41653493867d25e6a4ea55",
}
APPROVED_METHODOLOGY_HEAD = "df5dcde63581198d4766fa662de89eae3e7c461e"
APPROVED_METHODOLOGY_TREE = "95814ae17922c399350200a4f2b55b1021113442"

PASS, FAIL, IND = "PASS", "FAIL", "INDETERMINATE"


class V2InheritedLadderAuthorityError(SyntheticExecutionNotAuthorized):
    """Amendment_003/004 methodology authority is missing, mutated, or
    inconsistent with the independently-reviewed identity it was approved
    under."""


class V2VisibilityStatisticUnavailable(SyntheticExecutionNotAuthorized):
    """A conclusion id's approved rule requires a GROUND_TRUTH_VISIBLE-type
    statistic that the frozen V2 policy fixture does not compute anywhere.

    This is a disclosed, pre-existing gap in already-frozen V2 authority
    (see module docstring), not a defect in this derivation. Inventing a
    substitute value here would be an unauthorized new scientific choice;
    this module refuses instead.
    """


def _refuse_authority(detail: str) -> None:
    raise V2InheritedLadderAuthorityError(f"SYNTHETIC_EXECUTION_NOT_AUTHORIZED: {detail}")


def assert_v2_inherited_ladder_authority_intact(
    repo_root: Path | None = None, commit: str = "HEAD"
) -> None:
    """Fail closed unless the exact approved Amendment_003+004 text is present.

    Hash-pinned exactly like ``assert_v1_tcb_intact``: any drift in either
    amendment's tracked bytes -- at any commit this is asked to check, not
    only HEAD -- refuses rather than silently reading a mutated/substituted
    methodology document.
    """
    repo_root = repo_root or _repo_root()
    pins = {**FROZEN_AMENDMENT_003_SHA256, **FROZEN_AMENDMENT_004_SHA256}
    for rel, expected in pins.items():
        blob = _commit_blob(repo_root, commit, rel)
        if blob is None:
            _refuse_authority(f"Amendment_003/004 artifact missing from {commit}: {rel}")
        digest = _sha256_bytes(blob)
        if digest != expected:
            _refuse_authority(f"Amendment_003/004 artifact hash drifted for {rel}")


def _load_amendment_json(repo_root: Path, commit: str, rel: str) -> dict[str, Any]:
    blob = _commit_blob(repo_root, commit, rel)
    if blob is None:
        _refuse_authority(f"amendment JSON missing from {commit}: {rel}")
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise V2InheritedLadderAuthorityError(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: amendment JSON is malformed"
        ) from exc
    if not isinstance(payload, dict):
        _refuse_authority(f"amendment JSON is not an object: {rel}")
    return payload


def load_v2_inherited_ladder_authority(
    repo_root: Path | None = None, commit: str = "HEAD"
) -> dict[str, Any]:
    """Load the merged, hash-verified 33-id authority table.

    31 ids come from Amendment_003 unchanged; exactly 2 (``NULL_PER_CANDIDATE_FPR``
    and ``FINAL_OVERALL_MECHANICAL_CONCLUSION``) are superseded by
    Amendment_004's precedence-only overlay. This function does not trust a
    caller-supplied path or a pre-parsed object: it always re-reads tracked
    git blob content at ``commit`` and re-verifies its hash first.
    """
    repo_root = repo_root or _repo_root()
    assert_v2_inherited_ladder_authority_intact(repo_root, commit)
    a003 = _load_amendment_json(repo_root, commit, AMENDMENT_003_JSON_REL)
    a004 = _load_amendment_json(repo_root, commit, AMENDMENT_004_JSON_REL)
    conclusions = dict(a003.get("conclusions") or {})
    overlay = dict(a004.get("conclusions") or {})
    if a004.get("amends") != "AMENDMENT_003":
        _refuse_authority("Amendment_004 does not declare amends=AMENDMENT_003")
    for cid, entry in overlay.items():
        if cid not in conclusions:
            _refuse_authority(f"Amendment_004 overlay id not present in Amendment_003: {cid}")
        conclusions[cid] = entry
    frozen_map = frozen_required_coverage_map()
    if set(conclusions) != set(frozen_map):
        _refuse_authority("merged 33-id authority does not match frozen_required_coverage_map()")
    return {"conclusions": conclusions, "amendment_003": a003, "amendment_004": a004}


# --- comb(): the one composition operator Amendment_003/004 use everywhere --
# for combining two or more PASS/FAIL/INDETERMINATE verdicts into one:
# NOT_CLAIMABLE > FAIL > INDETERMINATE > PASS. Not invented here -- this is
# the exact rule Amendment_003 states, verbatim, for NULL_FALSE_POSITIVE_CONCLUSION,
# EASY_CONCLUSION, MODERATE_CONCLUSION and BLIND_DISCOVERY_CONCLUSION, and
# Amendment_004 states, verbatim, for integrating the NULL aggregate gate.


def _comb(*verdicts: str) -> str:
    if "NOT_CLAIMABLE" in verdicts:
        return "NOT_CLAIMABLE"
    if FAIL in verdicts:
        return FAIL
    if IND in verdicts:
        return IND
    return PASS


# --- per-statistic-family raw-value derivation (pre STAGE-1/2 gating) -------
# Each function below returns a raw PASS/FAIL/INDETERMINATE (or band/floor)
# value using ONLY frozen executable operators (specificity_verdict,
# power_verdict, small_band -- all imported from the pinned V1 TCB) applied
# to counts read from already-frozen, already-computed WorldRecordV2/
# CellAggregateV2 fields. No classification logic is reimplemented: a world's
# CANDIDATE_IDENTIFIABLE state and its `detected` (== frozen gates["STRICT_PASS"])
# / gates["STRICT_PASS_EX_MATERIALITY"] values are read verbatim from records
# the frozen V2 fixture already produced.
#
# Undefined-denominator fallback: mirrors the exact convention already frozen
# in the pinned V1 TCB production module (`_spec`/`_pow`: "return verdict(...)
# if arm['n'] else 'INDETERMINATE'") -- not invented here. This raw value is
# only ever consulted by mechanical_conclusion_v2 AFTER it has already
# confirmed COVERAGE_ADEQUATE for the relevant cell/candidate (which requires
# candidate_identifiable_count >= HARD_FLOOR_IDENTIFIABLE = 200), so an
# INDETERMINATE fallback on a truly zero denominator is never actually
# selected as the emitted conclusion; it exists only so this function does
# not raise before the coverage gate has a chance to run.


def _cell(cells: Mapping[tuple[str, int], CellAggregateV2], scenario: str, n_rows: int) -> CellAggregateV2 | None:
    return cells.get((scenario, n_rows))


def _cand_detection_verdict(
    cells: Mapping[tuple[str, int], CellAggregateV2],
    scenario: str,
    n_rows: int,
    cid: str,
    *,
    op,
    threshold: float,
) -> str:
    cell = _cell(cells, scenario, n_rows)
    if cell is None:
        return IND
    ident = cell.candidate_identifiable_count.get(cid, 0)
    det = cell.candidate_detection_count.get(cid, 0)
    if ident <= 0:
        return IND
    return op(wilson_interval(det, ident), threshold)


def _cand_detection_band(
    cells: Mapping[tuple[str, int], CellAggregateV2], scenario: str, n_rows: int, cid: str
) -> str:
    cell = _cell(cells, scenario, n_rows)
    if cell is None:
        return IND
    ident = cell.candidate_identifiable_count.get(cid, 0)
    det = cell.candidate_detection_count.get(cid, 0)
    if ident <= 0:
        return IND
    return small_band(wilson_interval(det, ident))


def _strict_pass_ex_materiality_count(cell: CellAggregateV2, cid: str) -> int:
    """New tally only: counts an already-frozen, already-computed gate value
    (`gates["STRICT_PASS_EX_MATERIALITY"]`) that CellAggregateV2 itself does
    not separately tally. No classification logic; a pure count over records
    the frozen fixture already produced."""
    count = 0
    for rec in cell.worlds:
        cand = rec.candidates.get(cid)
        if cand is None or cand.state != "CANDIDATE_IDENTIFIABLE":
            continue
        gates = cand.gates or {}
        if gates.get("STRICT_PASS_EX_MATERIALITY") is True:
            count += 1
    return count


def _trap_specificity_verdict(cells: Mapping[tuple[str, int], CellAggregateV2]) -> str:
    """NONSTATIONARY_TRAP_ORACLE_SPECIFICITY: statistic is STRICT_PASS_EX_MATERIALITY
    detection (NOT plain `detected`/STRICT_PASS), per Amendment_003."""
    cell = _cell(cells, "NONSTATIONARY_TRAP", 5000)
    if cell is None:
        return IND
    ident = cell.candidate_identifiable_count.get("F03", 0)
    if ident <= 0:
        return IND
    ex_count = _strict_pass_ex_materiality_count(cell, "F03")
    return specificity_verdict(wilson_interval(ex_count, ident), 0.20)


def _pooled_blind_verdict(
    cells: Mapping[tuple[str, int], CellAggregateV2], scenario: str, n_rows: int, *, field: str, op, threshold: float
) -> str:
    cell = _cell(cells, scenario, n_rows)
    if cell is None:
        return IND
    pooled = cell.pooled_blind()
    n = int(pooled["BLIND_WORLD_COUNT"])
    if n <= 0:
        return IND
    return op(wilson_interval(int(pooled[field]), n), threshold)


def _materiality_only_diagnostic(cells: Mapping[tuple[str, int], CellAggregateV2]) -> tuple[str, bool | None]:
    """Returns (state, failure_bool). state in {'NOT_CLAIMABLE' is handled by
    the caller's coverage gate; here we only ever return the two governing
    states DIAGNOSTIC / no-suppression, expressed as (label, bool)."""
    cell = _cell(cells, "EASY", 5000)
    if cell is None:
        return "MATERIALITY_ONLY_DIAGNOSTIC", None
    successes_strict = cell.candidate_detection_count.get("F03", 0)  # == STRICT_PASS count
    successes_ex = _strict_pass_ex_materiality_count(cell, "F03")
    failure = successes_ex > successes_strict
    label = "MATERIALITY_ONLY_DIAGNOSTIC" if failure else "NO_MATERIALITY_ONLY_SUPPRESSION"
    return label, failure


def _null_per_candidate_aggregate(cells: Mapping[tuple[str, int], CellAggregateV2]) -> str:
    verdicts = [
        _cand_detection_verdict(cells, "NULL", 5000, cid, op=specificity_verdict, threshold=0.10)
        for cid in FEATURE_IDS
    ]
    return _comb(*verdicts)


# --- the 33-id raw-value table (transcribed from Amendment_003 + 004) -------


def _derive_raw_values(
    cells: Mapping[tuple[str, int], CellAggregateV2]
) -> dict[str, Any]:
    """All 33 ids' pre-STAGE-1/2 raw values. Six visibility-dependent entries
    raise V2VisibilityStatisticUnavailable lazily (only if actually read) via
    the sentinel below, so every OTHER id can still be derived and reported."""

    def _blocked_by_visibility():
        raise V2VisibilityStatisticUnavailable(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: the frozen V2 policy fixture "
            "computes no GROUND_TRUTH_VISIBLE-equivalent statistic anywhere "
            "(evaluate_v2_world: 'does not execute bootstrap, placebo, or "
            "visibility'); this conclusion id's approved rule cannot be "
            "mechanically derived from current frozen V2 authority without "
            "inventing a new, unreviewed scientific procedure"
        )

    raw: dict[str, Any] = {}

    raw["NULL_ORACLE_FPR"] = _cand_detection_verdict(
        cells, "NULL", 5000, "F03", op=specificity_verdict, threshold=0.05
    )
    raw["NULL_BLIND_FPR"] = _pooled_blind_verdict(
        cells, "NULL", 5000, field="ANY_EDGE_DECLARED", op=specificity_verdict, threshold=0.10
    )
    raw["NONSTATIONARY_TRAP_ORACLE_SPECIFICITY"] = _trap_specificity_verdict(cells)
    raw["EASY_ORACLE_POWER"] = _cand_detection_verdict(
        cells, "EASY", 5000, "F03", op=power_verdict, threshold=0.90
    )
    raw["MODERATE_ORACLE_POWER"] = _cand_detection_verdict(
        cells, "MODERATE", 5000, "F03", op=power_verdict, threshold=0.70
    )
    raw["EASY_BLIND_USEFUL_DISCOVERY"] = _pooled_blind_verdict(
        cells, "EASY", 5000, field="USEFUL_DISCOVERY", op=power_verdict, threshold=0.80
    )
    raw["MODERATE_BLIND_USEFUL_DISCOVERY"] = _pooled_blind_verdict(
        cells, "MODERATE", 5000, field="USEFUL_DISCOVERY", op=power_verdict, threshold=0.50
    )
    raw["SMALL_ORACLE_BAND"] = _cand_detection_band(cells, "SMALL", 5000, "F03")
    raw["SMALL_2500_SENSITIVITY"] = _cand_detection_band(cells, "SMALL", 2500, "F03")
    raw["SMALL_10000_SENSITIVITY"] = _cand_detection_band(cells, "SMALL", 10000, "F03")

    mat_label, mat_failure = _materiality_only_diagnostic(cells)
    raw["MATERIALITY_ONLY_DIAGNOSTIC"] = mat_label
    raw["_materiality_only_failure_bool"] = mat_failure

    raw["NULL_PER_CANDIDATE_FPR"] = _null_per_candidate_aggregate(cells)
    raw["NULL_FALSE_POSITIVE_CONCLUSION"] = _comb(
        raw["NULL_ORACLE_FPR"], raw["NULL_BLIND_FPR"], raw["NULL_PER_CANDIDATE_FPR"]
    )

    raw["EASY_CONCLUSION"] = _comb(raw["EASY_ORACLE_POWER"], raw["EASY_BLIND_USEFUL_DISCOVERY"])
    raw["MODERATE_CONCLUSION"] = _comb(
        raw["MODERATE_ORACLE_POWER"], raw["MODERATE_BLIND_USEFUL_DISCOVERY"]
    )

    raw["SMALL_CONCLUSION"] = raw["SMALL_ORACLE_BAND"]
    raw["NONSTATIONARY_TRAP_CONCLUSION"] = raw["NONSTATIONARY_TRAP_ORACLE_SPECIFICITY"]

    raw["ORACLE_F03_NULL"] = raw["NULL_ORACLE_FPR"]
    raw["ORACLE_F03_EASY"] = raw["EASY_ORACLE_POWER"]
    raw["ORACLE_F03_MODERATE"] = raw["MODERATE_ORACLE_POWER"]
    raw["ORACLE_F03_SMALL_5000"] = raw["SMALL_ORACLE_BAND"]
    raw["ORACLE_F03_TRAP"] = raw["NONSTATIONARY_TRAP_ORACLE_SPECIFICITY"]
    raw["ORACLE_F03_SMALL_2500"] = raw["SMALL_2500_SENSITIVITY"]
    raw["ORACLE_F03_SMALL_10000"] = raw["SMALL_10000_SENSITIVITY"]

    raw["BLIND_DISCOVERY_EASY"] = raw["EASY_BLIND_USEFUL_DISCOVERY"]
    raw["BLIND_DISCOVERY_MODERATE"] = raw["MODERATE_BLIND_USEFUL_DISCOVERY"]
    raw["BLIND_DISCOVERY_CONCLUSION"] = _comb(
        raw["BLIND_DISCOVERY_EASY"], raw["BLIND_DISCOVERY_MODERATE"]
    )

    # -- visibility-dependent (blocked): evaluated lazily via a callable so
    # callers that do not need them (e.g. tests exercising only the
    # derivable subset) are never forced to pay for the refusal.
    raw["VISIBILITY_FLOOR"] = _blocked_by_visibility
    raw["MODEL_FLOOR"] = _blocked_by_visibility
    raw["TINY_NOISY_ORACLE_DIAGNOSTIC"] = _blocked_by_visibility
    raw["TINY_NOISY_CONCLUSION"] = _blocked_by_visibility
    raw["ORACLE_F03_TINY_NOISY"] = _blocked_by_visibility

    raw["FINAL_OVERALL_MECHANICAL_CONCLUSION"] = None  # computed separately
    return raw


VISIBILITY_BLOCKED_IDS = frozenset(
    {
        "VISIBILITY_FLOOR",
        "MODEL_FLOOR",
        "TINY_NOISY_ORACLE_DIAGNOSTIC",
        "TINY_NOISY_CONCLUSION",
        "ORACLE_F03_TINY_NOISY",
    }
)


def derive_v2_inherited_conclusion(
    conclusion_id: str, records: Sequence[WorldRecordV2]
) -> str:
    """The single per-id entrypoint that replaces the removed
    ``inherited_detection_conclusions`` caller mapping. Deterministic pure
    function of authenticated evidence only. Raises
    ``V2VisibilityStatisticUnavailable`` if -- and only if -- this specific
    id's rule requires the unavailable GROUND_TRUTH_VISIBLE statistic."""
    if conclusion_id not in frozen_required_coverage_map():
        _refuse_authority(f"unknown conclusion id: {conclusion_id}")
    cells = aggregate_v2_records(records)
    raw = _derive_raw_values(cells)
    value = raw[conclusion_id]
    if callable(value):
        return value()
    return value


def derive_v2_inherited_conclusions_needed(
    records: Sequence[WorldRecordV2], needed_ids: Sequence[str]
) -> dict[str, str]:
    """Raw (pre STAGE-1/2) values for exactly ``needed_ids``.

    Callers that already know a given id's coverage is INSUFFICIENT (and will
    therefore never actually read its inherited raw value -- see the frozen
    ``mechanical_conclusion_v2``, which returns before touching that argument
    in that case) should exclude it from ``needed_ids``. This means the
    visibility-dependent ids only ever raise ``V2VisibilityStatisticUnavailable``
    when a real derivation is actually required for one of them -- exactly
    mirroring how ``derive_v2_final_overall_conclusion`` only raises when
    frozen step 3.5 is actually reached, and never merely because visibility
    data theoretically doesn't exist for an id that STAGE 2 already refused
    on coverage grounds.
    """
    cells = aggregate_v2_records(records)
    raw = _derive_raw_values(cells)
    out: dict[str, str] = {}
    for cid in needed_ids:
        if cid not in frozen_required_coverage_map():
            _refuse_authority(f"unknown conclusion id: {cid}")
        value = raw[cid]
        out[cid] = value() if callable(value) else value
    return out


def derive_all_v2_inherited_conclusions(
    records: Sequence[WorldRecordV2],
) -> dict[str, str]:
    """All 33 raw (pre STAGE-1/2) values, unconditionally. Raises
    ``V2VisibilityStatisticUnavailable`` listing the blocked ids -- use this
    only when every id's raw value is genuinely needed regardless of
    coverage (e.g. a research/audit tool). Production code (see
    ``harness_synthetic_edge_calibration_v2_production.derive_v2_mechanical_conclusions``)
    uses ``derive_v2_inherited_conclusions_needed`` instead, so that a
    coverage-inadequate run is correctly reported as
    INSUFFICIENT_IDENTIFIABILITY_NO_METHODOLOGY_CLAIM rather than masked by
    an unrelated visibility refusal.
    """
    cells = aggregate_v2_records(records)
    raw = _derive_raw_values(cells)
    blocked = sorted(cid for cid in VISIBILITY_BLOCKED_IDS if cid in frozen_required_coverage_map())
    if blocked:
        raise V2VisibilityStatisticUnavailable(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: cannot derive the complete "
            f"33-id ladder -- {len(blocked)} ids have no computable input "
            f"under the frozen V2 policy fixture: {blocked}. "
            "IMPLEMENTATION_REQUIRES_NEW_SCIENTIFIC_CHOICE = YES "
            "(see V2VisibilityStatisticUnavailable docstring)."
        )
    out: dict[str, str] = {}
    for cid in frozen_required_coverage_map():
        if cid == "FINAL_OVERALL_MECHANICAL_CONCLUSION":
            continue
        value = raw[cid]
        out[cid] = value() if callable(value) else value
    return out


# --- FINAL_OVERALL_MECHANICAL_CONCLUSION: the composite state machine ------
# STAGE 1 / STAGE 2 are the caller's responsibility (already-frozen V2
# structural/coverage semantics, unchanged); this function implements ONLY
# Amendment_004's repaired STAGE 2b+3 composition, and does so by calling the
# frozen, SHA256-pinned mechanical_conclusion() UNMODIFIED -- the V2
# NULL-aggregate gate is folded into the `trap_specificity` argument slot via
# `_comb()`, which is mathematically equivalent to adding it as a fourth
# member of the frozen specificity tuple and a further member of the frozen
# required-verdict tuple (folding preserves "does FAIL/INDETERMINATE appear
# anywhere in the set", which is the only thing `mechanical_conclusion` ever
# tests for those tuples). This calls the frozen function verbatim; it does
# not reimplement its logic.


class _VisibilityBlockedSentinel:
    """Passed as ``visibility_wilson_upper`` to the frozen, unmodified
    ``mechanical_conclusion()``. It is not ``None``, so the frozen function's
    own ``if visibility_wilson_upper is not None and visibility_wilson_upper
    < 0.50`` guard proceeds to the comparison -- which this sentinel raises
    on. This means the block fires ONLY when frozen step 3.5 is actually
    reached (i.e. no stronger frozen consequence -- specificity failure,
    power failure, or INDETERMINATE -- already applied at steps 3.1-3.3), not
    unconditionally. A case fully resolved by an earlier, non-visibility step
    is therefore never wrongly blocked."""

    def _raise(self, *_args: Any, **_kwargs: Any) -> "bool":
        raise V2VisibilityStatisticUnavailable(
            "SYNTHETIC_EXECUTION_NOT_AUTHORIZED: FINAL_OVERALL_MECHANICAL_CONCLUSION "
            "reached frozen step 3.5 (VISIBILITY_FLOOR), which requires a "
            "GROUND_TRUTH_VISIBLE-equivalent statistic the frozen V2 policy "
            "fixture does not compute anywhere. "
            "IMPLEMENTATION_REQUIRES_NEW_SCIENTIFIC_CHOICE = YES "
            "(see V2VisibilityStatisticUnavailable docstring)."
        )

    __lt__ = __le__ = __gt__ = __ge__ = __eq__ = _raise
    __hash__ = None  # type: ignore[assignment]


def derive_v2_final_overall_conclusion(
    records: Sequence[WorldRecordV2], *, structurally_complete: bool
) -> str:
    if not structurally_complete:
        return mechanical_conclusion(
            incomplete_execution=True,
            oracle_null_specificity=PASS,
            blind_null_specificity=PASS,
            trap_specificity=PASS,
            easy_oracle_power=PASS,
            moderate_oracle_power=PASS,
            easy_blind_useful=PASS,
            moderate_blind_useful=PASS,
        )
    cells = aggregate_v2_records(records)
    raw = _derive_raw_values(cells)
    null_gate = raw["NULL_PER_CANDIDATE_FPR"]
    trap_folded = _comb(raw["NONSTATIONARY_TRAP_ORACLE_SPECIFICITY"], null_gate)
    model_upper = None
    model_cell = _cell(cells, "EASY", 5000)
    if model_cell is not None:
        ident = model_cell.candidate_identifiable_count.get("F03", 0)
        if ident > 0:
            model_upper = wilson_interval(model_cell.candidate_detection_count.get("F03", 0), ident)["upper"]
    return mechanical_conclusion(
        incomplete_execution=False,
        oracle_null_specificity=raw["NULL_ORACLE_FPR"],
        blind_null_specificity=raw["NULL_BLIND_FPR"],
        trap_specificity=trap_folded,
        easy_oracle_power=raw["EASY_ORACLE_POWER"],
        moderate_oracle_power=raw["MODERATE_ORACLE_POWER"],
        easy_blind_useful=raw["EASY_BLIND_USEFUL_DISCOVERY"],
        moderate_blind_useful=raw["MODERATE_BLIND_USEFUL_DISCOVERY"],
        visibility_wilson_upper=_VisibilityBlockedSentinel(),
        model_detection_wilson_upper=model_upper,
        materiality_only_failure=bool(raw["_materiality_only_failure_bool"]),
    )
