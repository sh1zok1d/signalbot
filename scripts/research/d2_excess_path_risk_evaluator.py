"""Frozen D2 excess direction-aligned path-risk decomposition evaluator.

Implements the frozen design
``D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN``
without redesigning it. Every scientific formula, comparator, gate, and
classification rule is imported from the frozen design module rather than
reimplemented here.

The only genuinely new mechanical work is reconstruction of the exact 288
5m ``PerpBar`` future path. ``DiscoveryRow`` stores ``future_closes`` only,
so ``MAE_OPPOSITE`` cannot be read off a stored row; the same bars must be
re-walked from the same perp map. ``MAE_SIDE`` recomputed from those
re-walked bars is cross-checked bit-for-bit against the frozen
``DiscoveryRow.severity``, which fails closed if the wrong window, the
close path, or a different path is ever substituted.

Real canonical CORE BTC evaluation is gated behind an immutable execution
permit that does not exist in this unit. Synthetic / constructed-row
evaluation is allowed.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.d2_excess_path_risk_beyond_vol_clustering_design import (
    CLASS_INVALID,
    CLASS_NO_STRUCTURE,
    CLASS_PROMISING,
    CLASS_SCALE_COMPATIBLE,
    CLASSIFICATION_ORDER,
    CONTROL_STRATA,
    CONTROL_YEARS,
    D2_DISCOVERY_RESULT_REL,
    FROZEN_D2_DISCOVERY_SHA256,
    FROZEN_RULE1_N,
    FROZEN_RULE1_YEAR_N,
    JSON_REL as DESIGN_JSON_REL,
    MD_REL as DESIGN_MD_REL,
    N_RANDOM_CONTROLS,
    PATH_SCALE_PRACTICAL_RELATIVE_BAR,
    PRACTICAL_DELTA_SHARE,
    PRIMARY_COMPARATOR,
    PRIMARY_SELECTOR,
    PRIMARY_TARGET,
    RANDOM_SEED,
    RV_PCTL,
    RV_TRAILING_WINDOW,
    SIDE_LABELS,
    TARGET_INELIGIBLE_REASON,
    TEMPORAL_YEARS_REQUIRED,
    TEMPORAL_YEARS_TOTAL,
    InsufficientStratumSupport,
    RealDecompositionForbidden,
    adverse_share,
    candidate_stratum_counts,
    classify_decomposition,
    encode_side,
    file_sha256,
    frozen_d2_selector_contract,
    mae_pair,
    mc_p_share,
    means_from_shared_masks,
    path_scale,
    path_scale_materially_elevated,
    practical_gate,
    statistical_gate,
    target_ineligible_reason,
    temporal_gate,
    verify_design_authorities,
    year_means_from_shared_masks,
    year_side_matched_control_masks,
)
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_cross_venue_dislocation_evaluator import (
    FUTURE_BARS,
    arithmetic_mae,
    get_perp_bar_opening_at,
)
from scripts.research.market_06_cross_venue_dislocation_parsers import BAR_MS, PerpBar

UNIT = "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW"
EVIDENCE_CLASS = "POST_REPLICATION_MECHANISM_DECOMPOSITION_DISCOVERY"

EXECUTION_AUTHORIZED = False
EXECUTION_PERMIT_REL = "docs/research/D2_EXCESS_PATH_RISK_EXECUTION_PERMIT.json"
REVIEW_JSON_REL = (
    "docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_REVIEW.json"
)
REVIEW_MD_REL = (
    "docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_REVIEW.md"
)
SELECTOR_IDENTITY_AUTHORITY_REL = (
    "docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_SELECTOR_IDENTITY.json"
)
SELECTOR_IDENTITY_AUTHORITY_UNIT = (
    "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PRE_OUTCOME_SELECTOR_DIGEST_FREEZE"
)
SELECTOR_IDENTITY_AUTHORITY_KIND = "PRE_OUTCOME_SELECTOR_IDENTITY_AUTHORITY"
SELECTOR_DIGEST_ALGORITHM = "SHA256_ORDERED_T_MS_AND_SELECTOR_FLAGS_V1"
SELECTOR_DIGEST_VERSION = 1
# Historical identity facts bound to frozen D2 discovery result SHA
# FROZEN_D2_DISCOVERY_SHA256. FROZEN_RULE1_N is the CONSTRUCTED RULE_1
# population (len(rows) / RULE_1_ROW_COUNT / YEAR_BREAKDOWN.RULE_1).
# It is NEVER the selector mask sum. SELECTOR_ABSTAIN_* is
# PRIMARY_METRICS.RV_ABSTENTION.ABSTAIN_COUNT / YEAR_ABSTAIN_COUNTS.
# See frozen_d2_selector_identity_facts().
FROZEN_SELECTOR_ABSTAIN_N = 163
FROZEN_SELECTOR_ABSTAIN_YEAR_N = {
    "2020": 10,
    "2021": 48,
    "2022": 32,
    "2023": 23,
    "2024": 50,
}
FROZEN_SELECTOR_ABSTAIN_PROVENANCE = (
    "PRIMARY_METRICS.RV_ABSTENTION.ABSTAIN_COUNT/YEAR_ABSTAIN_COUNTS"
)

IMPLEMENTATION_FILES = (
    "scripts/research/d2_excess_path_risk_evaluator.py",
    "scripts/research/d2_excess_path_risk_beyond_vol_clustering_design.py",
    "scripts/research/discovery_sprint_01/common.py",
    "scripts/research/discovery_sprint_01/d2_abstention_tail_risk.py",
    "scripts/research/market_06_cross_venue_dislocation_evaluator.py",
)

SCIENTIFIC_MAE = arithmetic_mae
SCIENTIFIC_RV_MASK = C.rv_abstention_mask
SCIENTIFIC_CONSTRUCT_ROW = C.construct_discovery_row
SCIENTIFIC_BUILD_ROWS = C.build_rows

MAE_SIDE_CROSS_CHECK_TOLERANCE = 0.0
CONTROL_P95_METHOD = "NUMPY_LINEAR_INHERITED_FROM_D2"
EXACT_SELECTOR_IDENTITY_IMPLEMENTED = True
CANONICAL_SELECTOR_DIGEST_FROZEN = False
SCIENTIFIC_KERNEL_READY = True
CANONICAL_ORCHESTRATION_READY = True
PERMIT_VERIFIER_READY = True
EXECUTION_READY = False
CALLER_FORBIDDEN_AUTHORITY_KEYS = frozenset(
    {
        "execution_authority",
        "design_sha256",
        "DESIGN_JSON_SHA256",
        "review_sha256",
        "IMPLEMENTATION_REVIEW_JSON_SHA256",
        "implementation_sha256",
        "REVIEWED_EVALUATOR_SHA256",
        "core_btc_snapshot",
        "CORE_BTC_SNAPSHOT_ID",
        "run_identity",
        "RUN_IDENTITY",
        "seed",
        "RANDOM_SEED",
        "n_replicates",
        "N_RANDOM_CONTROLS",
        "UNIT",
        "EXECUTION_AUTHORIZED",
        "ONE_SHOT",
        "RERUN_AUTHORIZED",
        "SELECTOR_IDENTITY_AUTHORITY_SHA256",
        "CANONICAL_SELECTOR_DIGEST",
        "SELECTOR_DIGEST",
    }
)
PERMIT_REQUIRED_KEYS = (
    "UNIT",
    "DESIGN_JSON_SHA256",
    "IMPLEMENTATION_REVIEW_JSON_SHA256",
    "REVIEWED_EVALUATOR_SHA256",
    "CORE_BTC_SNAPSHOT_ID",
    "RUN_IDENTITY",
    "RANDOM_SEED",
    "N_RANDOM_CONTROLS",
    "EXECUTION_AUTHORIZED",
    "ONE_SHOT",
    "RERUN_AUTHORIZED",
    "SELECTOR_IDENTITY_AUTHORITY_SHA256",
)
SELECTOR_IDENTITY_AUTHORITY_REQUIRED_KEYS = (
    "UNIT",
    "KIND",
    "CORE_BTC_SNAPSHOT_ID",
    "SELECTOR_DIGEST_ALGORITHM",
    "SELECTOR_DIGEST_VERSION",
    "CANONICAL_SELECTOR_DIGEST",
    "RULE_1_CONSTRUCTED_N",
    "RULE_1_CONSTRUCTED_YEAR_N",
    "RULE_1_N",
    "RULE_1_YEAR_N",
    "RULE_1_N_MEANS_CONSTRUCTED_POPULATION",
    "SELECTOR_ABSTAIN_N",
    "SELECTOR_ABSTAIN_YEAR_N",
    "FROZEN_D2_DISCOVERY_SHA256",
    "SELECTOR_ABSTAIN_PROVENANCE",
    "DESIGN_JSON_SHA256",
    "IMPLEMENTATION_REVIEW_JSON_SHA256",
    "RUN_IDENTITY",
    "CANONICAL_SELECTOR_DIGEST_FROZEN",
)


class ExecutionNotAuthorized(RuntimeError):
    """Real CORE BTC decomposition execution is not authorized."""


class SelectorIdentityError(RuntimeError):
    """Reconstructed RULE_1 constructed/abstain census and/or digest failed."""


class FuturePathReconstructionError(RuntimeError):
    """The exact frozen 288x5m PerpBar future path could not be re-walked."""


class PermitAuthorityError(ExecutionNotAuthorized):
    """Tracked execution-permit authority failed closed."""


def control_p95(values: Sequence[float] | np.ndarray) -> float:
    """P95 of control means. Inherited D2 NumPy linear percentile, made explicit."""
    arr = np.asarray(list(values) if not isinstance(values, np.ndarray) else values, dtype=np.float64)
    return float(np.percentile(arr, 95.0, method="linear"))


@dataclass(frozen=True)
class ExecutionPermit:
    """Future immutable permit. None exists in this unit."""

    design_sha256: str
    review_sha256: str
    implementation_sha256: str
    core_btc_snapshot: str
    run_identity: str


@dataclass(frozen=True)
class TargetRow:
    """Per-row decomposition components on the exact frozen future path."""

    t_ms: int
    year: int
    side: float
    entry_open: float
    mae_side: float
    mae_opposite: float
    path_scale: float
    adverse_share: float | None
    ineligible_reason: str | None

    @property
    def target_eligible(self) -> bool:
        return self.ineligible_reason is None


def future_bars_for_row(
    row: C.DiscoveryRow,
    perp: Mapping[int, PerpBar],
) -> list[PerpBar]:
    """Re-walk the exact 288 5m PerpBars construct_discovery_row consumed.

    Bars open at T, T+5m, ... T+287*5m. Any missing bar, any off-grid
    open_time, or any protected-era bar fails closed. Close-path extrema
    are never substituted for high/low.
    """
    bars: list[PerpBar] = []
    for k in range(FUTURE_BARS):
        want_ms = int(row.t_ms) + k * BAR_MS
        bar = get_perp_bar_opening_at(perp, want_ms)
        if bar is None:
            raise FuturePathReconstructionError(f"MISSING_FUTURE_BAR:{row.t_ms}:{k}")
        if int(bar.open_time_ms) != want_ms:
            raise FuturePathReconstructionError(
                f"FUTURE_BAR_OFF_GRID:{row.t_ms}:{k}:{bar.open_time_ms}!={want_ms}"
            )
        if int(bar.open_time_ms) >= C.PROTECTED_START_MS:
            raise C.ProtectedYearRefused(f"PROTECTED_FUTURE_BAR:{bar.open_time_ms}")
        bars.append(bar)
    if len(bars) != FUTURE_BARS:
        raise FuturePathReconstructionError(f"FUTURE_BAR_COUNT:{len(bars)}")
    return bars


def target_row_from_discovery_row(
    row: C.DiscoveryRow,
    perp: Mapping[int, PerpBar],
    *,
    cross_check_severity: bool = True,
) -> TargetRow:
    """MAE_SIDE / MAE_OPPOSITE from ONE shared re-walked future path.

    ``mae_pair`` calls frozen ``arithmetic_mae`` twice on the identical
    ``future_bars`` sequence, so SIDE and -SIDE cannot diverge onto
    different paths. ``cross_check_severity`` re-proves that the re-walked
    path is the same path the frozen row was built from.
    """
    bars = future_bars_for_row(row, perp)
    mae_side, mae_opposite = mae_pair(float(row.side), float(row.entry_open), bars)
    if cross_check_severity:
        if abs(float(mae_side) - float(row.severity)) > MAE_SIDE_CROSS_CHECK_TOLERANCE:
            raise FuturePathReconstructionError(
                f"MAE_SIDE_NOT_FROZEN_SEVERITY:{row.t_ms}:{mae_side}!={row.severity}"
            )
    scale = path_scale(mae_side, mae_opposite)
    reason = target_ineligible_reason(mae_side, mae_opposite)
    share = None if reason is not None else adverse_share(mae_side, mae_opposite)
    return TargetRow(
        t_ms=int(row.t_ms),
        year=int(row.year),
        side=float(row.side),
        entry_open=float(row.entry_open),
        mae_side=float(mae_side),
        mae_opposite=float(mae_opposite),
        path_scale=float(scale),
        adverse_share=None if share is None else float(share),
        ineligible_reason=reason,
    )


def build_target_rows(
    rows: Sequence[C.DiscoveryRow],
    perp: Mapping[int, PerpBar],
    *,
    cross_check_severity: bool = True,
) -> list[TargetRow]:
    return [
        target_row_from_discovery_row(
            row, perp, cross_check_severity=cross_check_severity
        )
        for row in rows
    ]


def selector_digest(
    rows: Sequence[C.DiscoveryRow],
    mask: np.ndarray,
) -> str:
    """SHA256 of the ordered constructed-row clock and selector flags.

    Count-only identity is not exact identity: two selections with the same
    total N and year counts but different timestamps must hash differently.
    The digest is computed here; it is NOT compared to a frozen canonical
    value in this unit (CANONICAL_SELECTOR_DIGEST_FROZEN = false).
    """
    mask_arr = np.asarray(mask, dtype=bool)
    if mask_arr.shape[0] != len(rows):
        raise SelectorIdentityError("MASK_ROW_SHAPE")
    payload = {
        "t_ms": [int(row.t_ms) for row in rows],
        "selector": [1 if bool(flag) else 0 for flag in mask_arr.tolist()],
    }
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return C.sha256_bytes(encoded)


def _year_breakdown(
    rows: Sequence[C.DiscoveryRow],
    include: Sequence[bool],
) -> dict[str, int]:
    year_counts = {year: 0 for year in CONTROL_YEARS}
    for row, flag in zip(rows, include, strict=True):
        if not flag:
            continue
        key = str(int(row.year))
        if key not in year_counts:
            raise SelectorIdentityError(f"UNEXPECTED_YEAR:{key}")
        year_counts[key] += 1
    return year_counts


def frozen_d2_selector_identity_facts(repo: Path) -> dict[str, Any]:
    """Read constructed and abstain censuses from the frozen D2 result.

    Does not rebuild rows, open CORE OHLC, or compute a new outcome.
    Fails closed if the discovery-result bytes have drifted from
    FROZEN_D2_DISCOVERY_SHA256.
    """
    path = repo / D2_DISCOVERY_RESULT_REL
    digest = file_sha256(path)
    if digest != FROZEN_D2_DISCOVERY_SHA256:
        raise SelectorIdentityError("D2_DISCOVERY_RESULT_SHA")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rv = (payload.get("PRIMARY_METRICS") or {}).get("RV_ABSTENTION") or {}
    constructed_year = {
        str(year): int((payload.get("RULE_1_YEAR_BREAKDOWN") or {}).get(year, -1))
        for year in CONTROL_YEARS
    }
    abstain_year = {
        str(year): int((rv.get("YEAR_ABSTAIN_COUNTS") or {}).get(year, -1))
        for year in CONTROL_YEARS
    }
    return {
        "FROZEN_D2_DISCOVERY_SHA256": digest,
        "RULE_1_CONSTRUCTED_N": int(payload.get("RULE_1_ROW_COUNT") or -1),
        "RULE_1_CONSTRUCTED_YEAR_N": constructed_year,
        "SELECTOR_ABSTAIN_N": int(rv.get("ABSTAIN_COUNT") or -1),
        "SELECTOR_ABSTAIN_YEAR_N": abstain_year,
        "SELECTOR_ABSTAIN_PROVENANCE": FROZEN_SELECTOR_ABSTAIN_PROVENANCE,
        "D2_DISCOVERY_RESULT_REL": D2_DISCOVERY_RESULT_REL,
    }


def verify_frozen_selector_identity_facts(repo: Path) -> dict[str, Any]:
    """Fail closed unless evaluator constants match SHA-bound D2 facts."""
    facts = frozen_d2_selector_identity_facts(repo)
    if int(facts["RULE_1_CONSTRUCTED_N"]) != int(FROZEN_RULE1_N):
        raise SelectorIdentityError(
            f"FROZEN_RULE1_N:{facts['RULE_1_CONSTRUCTED_N']}!={FROZEN_RULE1_N}"
        )
    if dict(facts["RULE_1_CONSTRUCTED_YEAR_N"]) != dict(FROZEN_RULE1_YEAR_N):
        raise SelectorIdentityError(
            f"FROZEN_RULE1_YEAR_N:{facts['RULE_1_CONSTRUCTED_YEAR_N']}"
        )
    if int(facts["SELECTOR_ABSTAIN_N"]) != int(FROZEN_SELECTOR_ABSTAIN_N):
        raise SelectorIdentityError(
            f"FROZEN_SELECTOR_ABSTAIN_N:{facts['SELECTOR_ABSTAIN_N']}"
            f"!={FROZEN_SELECTOR_ABSTAIN_N}"
        )
    if dict(facts["SELECTOR_ABSTAIN_YEAR_N"]) != dict(FROZEN_SELECTOR_ABSTAIN_YEAR_N):
        raise SelectorIdentityError(
            f"FROZEN_SELECTOR_ABSTAIN_YEAR_N:{facts['SELECTOR_ABSTAIN_YEAR_N']}"
        )
    return facts


def selector_identity(
    rows: Sequence[C.DiscoveryRow],
    mask: np.ndarray,
) -> dict[str, Any]:
    """Two-census RULE_1 identity plus exact ordered digest.

    Constructed census is len(rows) / all-row year counts.
    Selector/abstain census is mask.sum() / selected-row year counts.
    RULE_1_ROW_COUNT is a backwards-compatible alias for the constructed
    population and is never mask.sum(). Does not modify the selector.
    """
    mask_arr = np.asarray(mask, dtype=bool)
    if mask_arr.shape[0] != len(rows):
        raise SelectorIdentityError("MASK_ROW_SHAPE")
    flags = [bool(flag) for flag in mask_arr.tolist()]
    constructed_years = _year_breakdown(rows, [True] * len(rows))
    abstain_years = _year_breakdown(rows, flags)
    constructed_n = int(len(rows))
    abstain_n = int(mask_arr.sum())
    return {
        "RULE_1_CONSTRUCTED_ROW_COUNT": constructed_n,
        "RULE_1_CONSTRUCTED_YEAR_BREAKDOWN": constructed_years,
        "RULE_1_ROW_COUNT": constructed_n,
        "RULE_1_YEAR_BREAKDOWN": constructed_years,
        "RULE_1_N_MEANS_CONSTRUCTED_POPULATION": True,
        "SELECTOR_ABSTAIN_COUNT": abstain_n,
        "SELECTOR_ABSTAIN_YEAR_BREAKDOWN": abstain_years,
        "SELECTOR_DIGEST": selector_digest(rows, mask_arr),
        "CANONICAL_SELECTOR_DIGEST_FROZEN": CANONICAL_SELECTOR_DIGEST_FROZEN,
        "CENSUS_IS_NOT_EXACT_IDENTITY": True,
    }


def verify_selector_identity(
    rows: Sequence[C.DiscoveryRow],
    mask: np.ndarray,
) -> dict[str, Any]:
    """Fail closed on frozen constructed AND historical abstain censuses.

    Constructed N/years are FROZEN_RULE1_N / FROZEN_RULE1_YEAR_N (1791 /
    334,364,364,364,365). Selector abstain N/years are
    FROZEN_SELECTOR_ABSTAIN_N / FROZEN_SELECTOR_ABSTAIN_YEAR_N (163 /
    10,48,32,23,50), bound to frozen D2 PRIMARY_METRICS.RV_ABSTENTION.
    The ordered digest is computed but not compared to a guessed canonical
    value in this unit.
    """
    census = selector_identity(rows, mask)
    if int(census["RULE_1_CONSTRUCTED_ROW_COUNT"]) != int(FROZEN_RULE1_N):
        raise SelectorIdentityError(
            f"RULE_1_CONSTRUCTED_N:{census['RULE_1_CONSTRUCTED_ROW_COUNT']}"
            f"!={FROZEN_RULE1_N}"
        )
    if census["RULE_1_CONSTRUCTED_YEAR_BREAKDOWN"] != dict(FROZEN_RULE1_YEAR_N):
        raise SelectorIdentityError(
            f"RULE_1_CONSTRUCTED_YEAR_N:{census['RULE_1_CONSTRUCTED_YEAR_BREAKDOWN']}"
        )
    if int(census["RULE_1_ROW_COUNT"]) != int(FROZEN_RULE1_N):
        raise SelectorIdentityError(
            f"RULE_1_N:{census['RULE_1_ROW_COUNT']}!={FROZEN_RULE1_N}"
        )
    if int(census["SELECTOR_ABSTAIN_COUNT"]) != int(FROZEN_SELECTOR_ABSTAIN_N):
        raise SelectorIdentityError(
            f"SELECTOR_ABSTAIN_N:{census['SELECTOR_ABSTAIN_COUNT']}"
            f"!={FROZEN_SELECTOR_ABSTAIN_N}"
        )
    if census["SELECTOR_ABSTAIN_YEAR_BREAKDOWN"] != dict(FROZEN_SELECTOR_ABSTAIN_YEAR_N):
        raise SelectorIdentityError(
            f"SELECTOR_ABSTAIN_YEAR_N:{census['SELECTOR_ABSTAIN_YEAR_BREAKDOWN']}"
        )
    return census


def _finite_mean(values: Sequence[float]) -> float | None:
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.size == 0:
        return None
    if not bool(np.all(np.isfinite(arr))):
        return None
    return float(arr.mean())


def _control_series_mean(series: np.ndarray) -> float | None:
    if series.size == 0:
        return None
    finite = np.isfinite(series)
    if not bool(finite.any()):
        return None
    if not bool(finite.all()):
        raise InsufficientStratumSupport("PARTIAL_NAN_CONTROL_SERIES")
    return float(series.mean())


def evaluate_decomposition(
    rows: Sequence[C.DiscoveryRow],
    perp: Mapping[int, PerpBar],
    *,
    seed: int = RANDOM_SEED,
    n_replicates: int = N_RANDOM_CONTROLS,
    enforce_selector_identity: bool = False,
    cross_check_severity: bool = True,
) -> dict[str, Any]:
    """Full frozen decomposition on already-constructed rows.

    Pure with respect to data provenance: it evaluates whatever rows and
    perp map it is handed, so synthetic fixtures are legal. Real canonical
    CORE BTC bars can only reach it through ``execute_decomposition``,
    which requires an execution permit that does not exist in this unit.
    """
    mask = SCIENTIFIC_RV_MASK(rows)
    census = (
        verify_selector_identity(rows, mask)
        if enforce_selector_identity
        else selector_identity(rows, mask)
    )
    targets = build_target_rows(rows, perp, cross_check_severity=cross_check_severity)

    years = [int(t.year) for t in targets]
    sides = [encode_side(float(t.side)) for t in targets]
    eligible = [bool(t.target_eligible) for t in targets]
    mask_list = [bool(flag) for flag in np.asarray(mask, dtype=bool).tolist()]

    # Target ineligibility never rebuilds or edits the D2 selector; the
    # candidate set is the INTERSECTION and the drop is reported.
    candidate = [bool(m and e) for m, e in zip(mask_list, eligible, strict=True)]
    selector_ineligible = [
        bool(m and not e) for m, e in zip(mask_list, eligible, strict=True)
    ]
    selector_target_ineligible_n = int(sum(selector_ineligible))
    selector_target_ineligible_by_year = {year: 0 for year in CONTROL_YEARS}
    for year, flag in zip(years, selector_ineligible, strict=True):
        if flag:
            selector_target_ineligible_by_year[str(int(year))] += 1

    share_values = [
        float(t.adverse_share) if t.adverse_share is not None else float("nan")
        for t in targets
    ]
    scale_values = [float(t.path_scale) for t in targets]

    k_counts = candidate_stratum_counts(years, sides, candidate)
    stratum_population = {
        f"{year}|{side}": int(
            sum(
                1
                for y, s, e in zip(years, sides, eligible, strict=True)
                if e and str(int(y)) == year and s == side
            )
        )
        for year in CONTROL_YEARS
        for side in SIDE_LABELS
    }

    integrity_reasons: list[str] = []
    candidate_n = int(sum(candidate))
    if candidate_n == 0:
        integrity_reasons.append("NO_TARGET_ELIGIBLE_CANDIDATE_ROWS")

    masks: np.ndarray | None = None
    try:
        masks = year_side_matched_control_masks(
            years,
            sides,
            eligible,
            candidate,
            seed=seed,
            n_replicates=n_replicates,
        )
    except InsufficientStratumSupport as exc:
        integrity_reasons.append(f"STRATUM_SUPPORT:{exc}")

    payload: dict[str, Any] = {
        "UNIT": UNIT,
        "EVIDENCE_CLASS": EVIDENCE_CLASS,
        "PRIMARY_SELECTOR": PRIMARY_SELECTOR,
        "PRIMARY_TARGET": PRIMARY_TARGET,
        "PRIMARY_COMPARATOR": PRIMARY_COMPARATOR,
        "CONTROL_STRATA": CONTROL_STRATA,
        "RANDOM_SEED": int(seed),
        "N_RANDOM_CONTROLS": int(n_replicates),
        "CONTROL_P95_METHOD": CONTROL_P95_METHOD,
        "SELECTOR_CENSUS": census,
        "N_CONSTRUCTED_ROWS": int(len(rows)),
        "N_SELECTOR_ROWS": int(sum(mask_list)),
        "N_TARGET_ELIGIBLE_ROWS": int(sum(eligible)),
        "N_CANDIDATE_ROWS": candidate_n,
        "SELECTOR_ROWS_TARGET_INELIGIBLE_N": selector_target_ineligible_n,
        "SELECTOR_ROWS_TARGET_INELIGIBLE_BY_YEAR": selector_target_ineligible_by_year,
        "TARGET_INELIGIBLE_REASON": TARGET_INELIGIBLE_REASON,
        "TARGET_INELIGIBILITY_DOES_NOT_CHANGE_D2_SELECTOR": True,
        "K_BY_STRATUM": {f"{y}|{s}": int(v) for (y, s), v in k_counts.items()},
        "TARGET_ELIGIBLE_POPULATION_BY_STRATUM": stratum_population,
        "SAME_CONTROL_MASK_FOR_SHARE_AND_PATH_SCALE": True,
        "REAL_DECOMPOSITION_OUTCOME_COMPUTED": False,
    }

    if integrity_reasons or masks is None:
        payload.update(
            {
                "INTEGRITY_INVALID": True,
                "INTEGRITY_REASONS": integrity_reasons,
                "MU_SHARE_RULE": None,
                "MU_SHARE_CONTROL": None,
                "DELTA_SHARE": None,
                "CONTROL_SHARE_P95": None,
                "MC_P_SHARE": None,
                "MU_PATH_SCALE_RULE": None,
                "MU_PATH_SCALE_CONTROL": None,
                "DELTA_PATH_SCALE": None,
                "CONTROL_PATH_SCALE_P95": None,
                "YEAR_DELTA_SHARE": {year: None for year in CONTROL_YEARS},
                "STATISTICAL_GATE": False,
                "PRACTICAL_GATE": False,
                "TEMPORAL_GATE": False,
                "PATH_SCALE_MATERIALLY_ELEVATED": False,
                "CLASSIFICATION": CLASS_INVALID,
                "CLASSIFICATION_ORDER": list(CLASSIFICATION_ORDER),
            }
        )
        return payload

    candidate_arr = np.asarray(candidate, dtype=bool)
    share_arr = np.asarray(share_values, dtype=np.float64)
    scale_arr = np.asarray(scale_values, dtype=np.float64)

    mu_share_rule = _finite_mean(share_arr[candidate_arr])
    mu_scale_rule = _finite_mean(scale_arr[candidate_arr])

    # ONE mask system, reused for ADVERSE_SHARE and PATH_SCALE.
    control_share_means = means_from_shared_masks(share_arr, masks)
    control_scale_means = means_from_shared_masks(scale_arr, masks)

    mu_share_control = _control_series_mean(control_share_means)
    mu_scale_control = _control_series_mean(control_scale_means)
    control_share_p95 = (
        control_p95(control_share_means)
        if bool(np.all(np.isfinite(control_share_means)))
        else None
    )
    control_scale_p95 = (
        control_p95(control_scale_means)
        if bool(np.all(np.isfinite(control_scale_means)))
        else None
    )

    delta_share = (
        None
        if (mu_share_rule is None or mu_share_control is None)
        else float(mu_share_rule - mu_share_control)
    )
    delta_scale = (
        None
        if (mu_scale_rule is None or mu_scale_control is None)
        else float(mu_scale_rule - mu_scale_control)
    )
    p_share = (
        None
        if (mu_share_rule is None or not bool(np.all(np.isfinite(control_share_means))))
        else float(mc_p_share(mu_share_rule, control_share_means.tolist()))
    )

    # Yearly diagnostics come from the SAME year x SIDE matched replicates,
    # subset to each year. No separate yearly comparator is generated.
    year_control_share = year_means_from_shared_masks(years, share_arr, masks)
    years_arr = np.asarray(years, dtype=np.int64)
    year_delta_share: dict[str, float | None] = {}
    year_mu_rule: dict[str, float | None] = {}
    year_mu_control: dict[str, float | None] = {}
    for year in CONTROL_YEARS:
        in_year = years_arr == int(year)
        rule_year = _finite_mean(share_arr[candidate_arr & in_year])
        control_year = _control_series_mean(year_control_share[year])
        year_mu_rule[year] = rule_year
        year_mu_control[year] = control_year
        year_delta_share[year] = (
            None
            if (rule_year is None or control_year is None)
            else float(rule_year - control_year)
        )

    gate_statistical = bool(
        mu_share_rule is not None
        and control_share_p95 is not None
        and statistical_gate(mu_share_rule, control_share_p95)
    )
    gate_practical = bool(delta_share is not None and practical_gate(delta_share))
    gate_temporal = bool(temporal_gate(year_delta_share))
    scale_elevated = bool(
        mu_scale_rule is not None
        and mu_scale_control is not None
        and control_scale_p95 is not None
        and path_scale_materially_elevated(
            mu_path_scale_rule=mu_scale_rule,
            mu_path_scale_control=mu_scale_control,
            control_path_scale_p95=control_scale_p95,
        )
    )

    integrity_invalid = bool(
        mu_share_rule is None or mu_share_control is None or delta_share is None
    )
    classification = classify_decomposition(
        integrity_invalid=integrity_invalid,
        statistical=gate_statistical,
        practical=gate_practical,
        temporal=gate_temporal,
        path_scale_elevated=scale_elevated,
    )

    payload.update(
        {
            "INTEGRITY_INVALID": integrity_invalid,
            "INTEGRITY_REASONS": integrity_reasons,
            "MU_SHARE_RULE": mu_share_rule,
            "MU_SHARE_CONTROL": mu_share_control,
            "DELTA_SHARE": delta_share,
            "CONTROL_SHARE_P95": control_share_p95,
            "MC_P_SHARE": p_share,
            "MU_PATH_SCALE_RULE": mu_scale_rule,
            "MU_PATH_SCALE_CONTROL": mu_scale_control,
            "DELTA_PATH_SCALE": delta_scale,
            "CONTROL_PATH_SCALE_P95": control_scale_p95,
            "YEAR_MU_SHARE_RULE": year_mu_rule,
            "YEAR_MU_SHARE_CONTROL": year_mu_control,
            "YEAR_DELTA_SHARE": year_delta_share,
            "YEARLY_DIAGNOSTICS_USE_SAME_YEAR_SIDE_MATCHED_REPLICATES": True,
            "STATISTICAL_GATE": gate_statistical,
            "PRACTICAL_GATE": gate_practical,
            "TEMPORAL_GATE": gate_temporal,
            "PATH_SCALE_MATERIALLY_ELEVATED": scale_elevated,
            "PATH_SCALE_CANNOT_RESCUE_PRIMARY": True,
            "NO_SUBGROUP_RESCUE": True,
            "CLASSIFICATION": classification,
            "CLASSIFICATION_ORDER": list(CLASSIFICATION_ORDER),
        }
    )
    return payload


def current_implementation_file_sha256(repo: Path) -> dict[str, str]:
    return {rel: file_sha256(repo / rel) for rel in IMPLEMENTATION_FILES}


def current_artifact_sha256(repo: Path) -> dict[str, str]:
    return {
        "DESIGN_JSON_SHA256": file_sha256(repo / DESIGN_JSON_REL),
        "DESIGN_MD_SHA256": file_sha256(repo / DESIGN_MD_REL),
        "IMPLEMENTATION_FILE_SHA256": current_implementation_file_sha256(repo),
    }


def compute_run_identity(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return C.sha256_bytes(encoded)


def _reject_caller_scientific_authority(kwargs: Mapping[str, Any]) -> None:
    forbidden = sorted(k for k in kwargs if k in CALLER_FORBIDDEN_AUTHORITY_KEYS)
    if forbidden:
        raise PermitAuthorityError(f"CALLER_SUPPLIED_AUTHORITY_FORBIDDEN:{','.join(forbidden)}")


def verify_core_btc_snapshot_identity(repo: Path) -> str:
    """Fail closed unless the tracked CORE BTC snapshot document matches frozen ID.

    Reads only the snapshot identity document, never 1m parquet / OHLC.
    """
    path = repo / C.CORE_BTC_SNAPSHOT_DOC_REL
    if not path.is_file():
        raise C.SnapshotIdentityError("CORE_BTC_SNAPSHOT_DOC_MISSING")
    identity = json.loads(path.read_text(encoding="utf-8"))
    payload = identity.get("identity_payload") or identity
    bound = payload.get("snapshot_id") or identity.get("snapshot_id")
    if bound != C.CORE_BTC_SNAPSHOT:
        raise C.SnapshotIdentityError(f"CORE_BTC:snapshot_mismatch:{bound}")
    dataset = payload.get("dataset_id")
    if dataset not in (None, "CORE_BTC_BINANCE_V0", getattr(C, "CORE_BTC_DATASET_ID", None)):
        raise C.SnapshotIdentityError(f"CORE_BTC:dataset_mismatch:{dataset}")
    return str(bound)


def verify_constructed_rule1_interval(rows: Sequence[C.DiscoveryRow]) -> None:
    if not rows:
        raise SelectorIdentityError("NO_CONSTRUCTED_ROWS")
    start_ms = C.ms_from_utc(C.RULE1_INTERVAL_START)
    end_ms = C.ms_from_utc(C.DISCOVERY_END)
    for row in rows:
        t_ms = int(row.t_ms)
        if t_ms >= C.PROTECTED_START_MS:
            raise C.ProtectedYearRefused(f"PROTECTED_CONSTRUCTED_ROW:{t_ms}")
        if t_ms < start_ms or t_ms >= end_ms:
            raise SelectorIdentityError(f"ROW_OUTSIDE_RULE1_INTERVAL:{t_ms}")


def selector_identity_authority_payload(
    *,
    canonical_selector_digest: str,
    design_json_sha256: str,
    implementation_review_json_sha256: str,
    run_identity: str,
    core_btc_snapshot_id: str = C.CORE_BTC_SNAPSHOT,
) -> dict[str, Any]:
    """Schema the future digest-freeze unit must write. Does not write the file.

    RULE_1_N / RULE_1_YEAR_N are backwards-compatible aliases for the
    CONSTRUCTED RULE_1 population. They are never the selector mask sum.
    SELECTOR_ABSTAIN_* is the historical RV_ABSTENTION census from the
    frozen D2 discovery result.
    """
    return {
        "UNIT": SELECTOR_IDENTITY_AUTHORITY_UNIT,
        "KIND": SELECTOR_IDENTITY_AUTHORITY_KIND,
        "CORE_BTC_SNAPSHOT_ID": str(core_btc_snapshot_id),
        "SELECTOR_DIGEST_ALGORITHM": SELECTOR_DIGEST_ALGORITHM,
        "SELECTOR_DIGEST_VERSION": int(SELECTOR_DIGEST_VERSION),
        "CANONICAL_SELECTOR_DIGEST": str(canonical_selector_digest),
        "RULE_1_CONSTRUCTED_N": int(FROZEN_RULE1_N),
        "RULE_1_CONSTRUCTED_YEAR_N": dict(FROZEN_RULE1_YEAR_N),
        "RULE_1_N": int(FROZEN_RULE1_N),
        "RULE_1_YEAR_N": dict(FROZEN_RULE1_YEAR_N),
        "RULE_1_N_MEANS_CONSTRUCTED_POPULATION": True,
        "SELECTOR_ABSTAIN_N": int(FROZEN_SELECTOR_ABSTAIN_N),
        "SELECTOR_ABSTAIN_YEAR_N": dict(FROZEN_SELECTOR_ABSTAIN_YEAR_N),
        "FROZEN_D2_DISCOVERY_SHA256": FROZEN_D2_DISCOVERY_SHA256,
        "SELECTOR_ABSTAIN_PROVENANCE": FROZEN_SELECTOR_ABSTAIN_PROVENANCE,
        "DESIGN_JSON_SHA256": str(design_json_sha256),
        "IMPLEMENTATION_REVIEW_JSON_SHA256": str(implementation_review_json_sha256),
        "RUN_IDENTITY": str(run_identity),
        "CANONICAL_SELECTOR_DIGEST_FROZEN": True,
    }


def _authority_year_map(
    value: Any, expected: Mapping[str, int], label: str
) -> dict[str, int]:
    try:
        got = {str(k): int(v) for k, v in dict(value or {}).items()}
    except (TypeError, ValueError) as exc:
        raise SelectorIdentityError(f"SELECTOR_AUTHORITY_MISMATCH:{label}") from exc
    if got != {str(k): int(v) for k, v in dict(expected).items()}:
        raise SelectorIdentityError(f"SELECTOR_AUTHORITY_MISMATCH:{label}")
    return got


def bind_selector_identity_authority_census(stored: Mapping[str, Any]) -> None:
    """Fail closed on constructed vs abstain census fields in the authority."""
    try:
        constructed_n = int(stored.get("RULE_1_CONSTRUCTED_N"))
        alias_n = int(stored.get("RULE_1_N"))
        abstain_n = int(stored.get("SELECTOR_ABSTAIN_N"))
    except (TypeError, ValueError) as exc:
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:CENSUS_N") from exc
    if constructed_n != int(FROZEN_RULE1_N):
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:RULE_1_CONSTRUCTED_N")
    if alias_n != int(FROZEN_RULE1_N):
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:RULE_1_N")
    if constructed_n != alias_n:
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:RULE_1_N_NE_CONSTRUCTED")
    if abstain_n != int(FROZEN_SELECTOR_ABSTAIN_N):
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:SELECTOR_ABSTAIN_N")
    if stored.get("RULE_1_N_MEANS_CONSTRUCTED_POPULATION") is not True:
        raise SelectorIdentityError(
            "SELECTOR_AUTHORITY_MISMATCH:RULE_1_N_MEANS_CONSTRUCTED_POPULATION"
        )
    _authority_year_map(
        stored.get("RULE_1_CONSTRUCTED_YEAR_N"),
        FROZEN_RULE1_YEAR_N,
        "RULE_1_CONSTRUCTED_YEAR_N",
    )
    _authority_year_map(stored.get("RULE_1_YEAR_N"), FROZEN_RULE1_YEAR_N, "RULE_1_YEAR_N")
    _authority_year_map(
        stored.get("SELECTOR_ABSTAIN_YEAR_N"),
        FROZEN_SELECTOR_ABSTAIN_YEAR_N,
        "SELECTOR_ABSTAIN_YEAR_N",
    )
    if str(stored.get("FROZEN_D2_DISCOVERY_SHA256")) != FROZEN_D2_DISCOVERY_SHA256:
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:FROZEN_D2_DISCOVERY_SHA256")
    if str(stored.get("SELECTOR_ABSTAIN_PROVENANCE")) != FROZEN_SELECTOR_ABSTAIN_PROVENANCE:
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:SELECTOR_ABSTAIN_PROVENANCE")


def _canonical_digest_hex(value: Any) -> str:
    digest = str(value or "")
    if len(digest) != 64 or any(
        ch not in "0123456789abcdef" for ch in digest.lower()
    ):
        raise SelectorIdentityError("SELECTOR_AUTHORITY_CANONICAL_DIGEST_MISSING")
    return digest.lower()


def verify_selector_identity_authority_payload(
    stored: Mapping[str, Any],
    *,
    design_json_sha256: str,
    implementation_review_json_sha256: str,
    run_identity: str,
    core_btc_snapshot_id: str,
) -> dict[str, Any]:
    """Fail closed on schema and bound identities. Does not open CORE OHLC."""
    if not isinstance(stored, dict):
        raise SelectorIdentityError("SELECTOR_AUTHORITY_NOT_OBJECT")
    missing = [key for key in SELECTOR_IDENTITY_AUTHORITY_REQUIRED_KEYS if key not in stored]
    if missing:
        raise SelectorIdentityError(f"SELECTOR_AUTHORITY_MISSING_KEYS:{','.join(missing)}")
    if str(stored.get("UNIT")) != SELECTOR_IDENTITY_AUTHORITY_UNIT:
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:UNIT")
    if str(stored.get("KIND")) != SELECTOR_IDENTITY_AUTHORITY_KIND:
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:KIND")
    if str(stored.get("CORE_BTC_SNAPSHOT_ID")) != str(core_btc_snapshot_id):
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:CORE_BTC_SNAPSHOT_ID")
    if str(stored.get("SELECTOR_DIGEST_ALGORITHM")) != SELECTOR_DIGEST_ALGORITHM:
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:SELECTOR_DIGEST_ALGORITHM")
    try:
        version = int(stored.get("SELECTOR_DIGEST_VERSION"))
    except (TypeError, ValueError) as exc:
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:SELECTOR_DIGEST_VERSION") from exc
    if version != int(SELECTOR_DIGEST_VERSION):
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:SELECTOR_DIGEST_VERSION")
    _canonical_digest_hex(stored.get("CANONICAL_SELECTOR_DIGEST"))
    bind_selector_identity_authority_census(stored)
    if str(stored.get("DESIGN_JSON_SHA256")) != str(design_json_sha256):
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:DESIGN_JSON_SHA256")
    if str(stored.get("IMPLEMENTATION_REVIEW_JSON_SHA256")) != str(
        implementation_review_json_sha256
    ):
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:IMPLEMENTATION_REVIEW_JSON_SHA256")
    if str(stored.get("RUN_IDENTITY") or "") != str(run_identity):
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:RUN_IDENTITY")
    if stored.get("CANONICAL_SELECTOR_DIGEST_FROZEN") is not True:
        raise SelectorIdentityError("SELECTOR_AUTHORITY_NOT_FROZEN")
    return dict(stored)


def load_selector_identity_authority(repo: Path) -> dict[str, Any]:
    path = repo / SELECTOR_IDENTITY_AUTHORITY_REL
    if not path.is_file():
        raise PermitAuthorityError("SELECTOR_IDENTITY_AUTHORITY_MISSING")
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PermitAuthorityError("SELECTOR_IDENTITY_AUTHORITY_UNPARSEABLE") from exc
    return stored


def verify_selector_identity_authority(repo: Path) -> dict[str, Any]:
    """Read and bind the tracked selector-identity authority. No CORE OHLC."""
    stored = load_selector_identity_authority(repo)
    review_path = repo / REVIEW_JSON_REL
    if not review_path.is_file():
        raise PermitAuthorityError("REVIEW_ARTIFACT_MISSING")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    hashes = current_artifact_sha256(repo)
    try:
        return verify_selector_identity_authority_payload(
            stored,
            design_json_sha256=hashes["DESIGN_JSON_SHA256"],
            implementation_review_json_sha256=file_sha256(review_path),
            run_identity=str(review.get("RUN_IDENTITY") or ""),
            core_btc_snapshot_id=C.CORE_BTC_SNAPSHOT,
        )
    except SelectorIdentityError as exc:
        raise PermitAuthorityError(str(exc)) from exc


def tracked_permit_expected_authority(repo: Path) -> dict[str, Any]:
    review_path = repo / REVIEW_JSON_REL
    if not review_path.is_file():
        raise PermitAuthorityError("REVIEW_ARTIFACT_MISSING")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    hashes = current_artifact_sha256(repo)
    identity_path = repo / SELECTOR_IDENTITY_AUTHORITY_REL
    selector_authority_sha256 = (
        file_sha256(identity_path) if identity_path.is_file() else ""
    )
    return {
        "UNIT": UNIT,
        "DESIGN_JSON_SHA256": hashes["DESIGN_JSON_SHA256"],
        "IMPLEMENTATION_REVIEW_JSON_SHA256": file_sha256(review_path),
        "REVIEWED_EVALUATOR_SHA256": hashes["IMPLEMENTATION_FILE_SHA256"][
            "scripts/research/d2_excess_path_risk_evaluator.py"
        ],
        "CORE_BTC_SNAPSHOT_ID": C.CORE_BTC_SNAPSHOT,
        "RUN_IDENTITY": str(review.get("RUN_IDENTITY") or ""),
        "RANDOM_SEED": int(RANDOM_SEED),
        "N_RANDOM_CONTROLS": int(N_RANDOM_CONTROLS),
        "EXECUTION_AUTHORIZED": True,
        "ONE_SHOT": True,
        "RERUN_AUTHORIZED": False,
        "SELECTOR_IDENTITY_AUTHORITY_SHA256": selector_authority_sha256,
    }


def verify_tracked_permit(repo: Path) -> dict[str, Any]:
    """Read the tracked permit artifact. Caller kwargs cannot replace it.

    All comparisons happen before CORE BTC OHLC is opened.
    """
    permit_path = repo / EXECUTION_PERMIT_REL
    if not permit_path.is_file():
        raise PermitAuthorityError("NO_EXECUTION_PERMIT")
    try:
        stored = json.loads(permit_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PermitAuthorityError("PERMIT_BYTES_UNPARSEABLE") from exc
    if not isinstance(stored, dict):
        raise PermitAuthorityError("PERMIT_NOT_OBJECT")
    expected = tracked_permit_expected_authority(repo)
    missing = [key for key in PERMIT_REQUIRED_KEYS if key not in stored]
    if missing:
        raise PermitAuthorityError(f"PERMIT_MISSING_KEYS:{','.join(missing)}")
    review_path = repo / REVIEW_JSON_REL
    review_hash = file_sha256(review_path)
    if str(stored.get("IMPLEMENTATION_REVIEW_JSON_SHA256")) != review_hash:
        raise PermitAuthorityError("PERMIT_MISMATCH:IMPLEMENTATION_REVIEW_JSON_SHA256")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    if str(stored.get("RUN_IDENTITY") or "") != str(review.get("RUN_IDENTITY") or ""):
        raise PermitAuthorityError("PERMIT_RUN_IDENTITY_NE_REVIEW_RUN_IDENTITY")
    if str(stored.get("RUN_IDENTITY") or "") != str(expected["RUN_IDENTITY"]):
        raise PermitAuthorityError("PERMIT_MISMATCH:RUN_IDENTITY")
    if str(stored.get("UNIT")) != str(expected["UNIT"]):
        raise PermitAuthorityError("PERMIT_MISMATCH:UNIT")
    if str(stored.get("DESIGN_JSON_SHA256")) != str(expected["DESIGN_JSON_SHA256"]):
        raise PermitAuthorityError("PERMIT_MISMATCH:DESIGN_JSON_SHA256")
    if str(stored.get("REVIEWED_EVALUATOR_SHA256")) != str(
        expected["REVIEWED_EVALUATOR_SHA256"]
    ):
        raise PermitAuthorityError("PERMIT_MISMATCH:REVIEWED_EVALUATOR_SHA256")
    if str(stored.get("CORE_BTC_SNAPSHOT_ID")) != str(expected["CORE_BTC_SNAPSHOT_ID"]):
        raise PermitAuthorityError("PERMIT_MISMATCH:CORE_BTC_SNAPSHOT_ID")
    try:
        stored_seed = int(stored.get("RANDOM_SEED"))
        stored_n = int(stored.get("N_RANDOM_CONTROLS"))
    except (TypeError, ValueError) as exc:
        raise PermitAuthorityError("PERMIT_NONINTEGER_SEED_OR_N") from exc
    if stored_seed != int(expected["RANDOM_SEED"]):
        raise PermitAuthorityError("PERMIT_MISMATCH:RANDOM_SEED")
    if stored_n != int(expected["N_RANDOM_CONTROLS"]):
        raise PermitAuthorityError("PERMIT_MISMATCH:N_RANDOM_CONTROLS")
    if stored.get("EXECUTION_AUTHORIZED") is not True:
        raise PermitAuthorityError("PERMIT_MISMATCH:EXECUTION_AUTHORIZED")
    if stored.get("ONE_SHOT") is not True:
        raise PermitAuthorityError("PERMIT_MISMATCH:ONE_SHOT")
    if stored.get("RERUN_AUTHORIZED") is not False:
        raise PermitAuthorityError("PERMIT_MISMATCH:RERUN_AUTHORIZED")
    identity_path = repo / SELECTOR_IDENTITY_AUTHORITY_REL
    if not identity_path.is_file():
        raise PermitAuthorityError("SELECTOR_IDENTITY_AUTHORITY_MISSING")
    identity_hash = file_sha256(identity_path)
    if str(stored.get("SELECTOR_IDENTITY_AUTHORITY_SHA256")) != identity_hash:
        raise PermitAuthorityError("PERMIT_MISMATCH:SELECTOR_IDENTITY_AUTHORITY_SHA256")
    authority = verify_selector_identity_authority(repo)
    if str(authority.get("RUN_IDENTITY") or "") != str(stored.get("RUN_IDENTITY") or ""):
        raise PermitAuthorityError("PERMIT_SELECTOR_AUTHORITY_RUN_IDENTITY_MISMATCH")
    if str(authority.get("DESIGN_JSON_SHA256")) != str(stored.get("DESIGN_JSON_SHA256")):
        raise PermitAuthorityError("PERMIT_SELECTOR_AUTHORITY_DESIGN_MISMATCH")
    if str(authority.get("CORE_BTC_SNAPSHOT_ID")) != str(
        stored.get("CORE_BTC_SNAPSHOT_ID")
    ):
        raise PermitAuthorityError("PERMIT_SELECTOR_AUTHORITY_SNAPSHOT_MISMATCH")
    if str(authority.get("IMPLEMENTATION_REVIEW_JSON_SHA256")) != str(
        stored.get("IMPLEMENTATION_REVIEW_JSON_SHA256")
    ):
        raise PermitAuthorityError("PERMIT_SELECTOR_AUTHORITY_REVIEW_MISMATCH")
    return stored


def canonical_orchestration(
    *,
    load_core_bars: Callable[[], Mapping[int, PerpBar]],
    verify_core_snapshot: Callable[[], str],
    load_selector_identity_authority: Callable[[], Mapping[str, Any]],
    build_rows_fn: Callable[..., list[C.DiscoveryRow]] = C.build_rows,
) -> dict[str, Any]:
    """Full dormant scientific route. Injected loaders may be synthetic.

    Hard-wires seed 20260922131, N=10000, selector identity ON, severity
    cross-check ON. Reconstructs the exact selector digest and compares it
    to the frozen selector-identity authority BEFORE any target-path or
    ADVERSE_SHARE / PATH_SCALE evaluation. Does not itself open CORE BTC.
    """
    snapshot_id = verify_core_snapshot()
    if snapshot_id != C.CORE_BTC_SNAPSHOT:
        raise C.SnapshotIdentityError(f"CORE_BTC:snapshot_mismatch:{snapshot_id}")
    authority = dict(load_selector_identity_authority())
    frozen_digest = _canonical_digest_hex(authority.get("CANONICAL_SELECTOR_DIGEST"))
    if str(authority.get("CORE_BTC_SNAPSHOT_ID")) != snapshot_id:
        raise SelectorIdentityError("SELECTOR_AUTHORITY_MISMATCH:CORE_BTC_SNAPSHOT_ID")
    bind_selector_identity_authority_census(authority)
    if authority.get("CANONICAL_SELECTOR_DIGEST_FROZEN") is not True:
        raise SelectorIdentityError("SELECTOR_AUTHORITY_NOT_FROZEN")
    perp = load_core_bars()
    rows = build_rows_fn(perp, C.RULE1_INTERVAL_START, C.DISCOVERY_END)
    verify_constructed_rule1_interval(rows)
    mask = SCIENTIFIC_RV_MASK(rows)
    census = verify_selector_identity(rows, mask)
    if str(census["SELECTOR_DIGEST"]) != frozen_digest:
        raise SelectorIdentityError(
            f"SELECTOR_DIGEST_NE_CANONICAL:{census['SELECTOR_DIGEST']}"
        )
    result = evaluate_decomposition(
        rows,
        perp,
        seed=RANDOM_SEED,
        n_replicates=N_RANDOM_CONTROLS,
        enforce_selector_identity=True,
        cross_check_severity=True,
    )
    result["SELECTOR_DIGEST"] = census["SELECTOR_DIGEST"]
    result["CANONICAL_SELECTOR_DIGEST"] = frozen_digest
    result["CANONICAL_SELECTOR_DIGEST_FROZEN"] = bool(
        authority.get("CANONICAL_SELECTOR_DIGEST_FROZEN") is True
    )
    result["SELECTOR_DIGEST_ALGORITHM"] = SELECTOR_DIGEST_ALGORITHM
    result["CORE_BTC_SNAPSHOT_ID"] = snapshot_id
    result["BUILD_ROWS_INTERVAL_START"] = C.RULE1_INTERVAL_START.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    result["BUILD_ROWS_INTERVAL_END_EXCLUSIVE"] = C.DISCOVERY_END.strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    result["CANONICAL_ORCHESTRATION"] = True
    result["ENFORCE_SELECTOR_IDENTITY"] = True
    result["CROSS_CHECK_SEVERITY"] = True
    result["RANDOM_SEED"] = int(RANDOM_SEED)
    result["N_RANDOM_CONTROLS"] = int(N_RANDOM_CONTROLS)
    result["CONTROL_P95_METHOD"] = CONTROL_P95_METHOD
    return result


def load_canonical_core_btc_bars(repo: Path) -> dict[int, PerpBar]:
    """Load frozen CORE BTC 5m bars. Hard-gated: tracked permit first, then snapshot."""
    verify_tracked_permit(repo)
    verify_core_btc_snapshot_identity(repo)
    log = C.OpenedFileLog()
    return C.load_core_btc_5m(log, repo=repo)


def execute_decomposition(*, repo: Path | None = None, **kwargs: Any) -> dict[str, Any]:
    """Real canonical 2020-2024 decomposition.

    Scientific authority is read only from the tracked permit artifact.
    Caller kwargs may identify the checkout (``repo``) and nothing else.
    No permit exists in this unit, so this always fails closed before CORE
    BTC OHLC is opened.
    """
    _reject_caller_scientific_authority(kwargs)
    base = repo if isinstance(repo, Path) else C.repo_root()
    verify_tracked_permit(base)

    def _load() -> dict[int, PerpBar]:
        return load_canonical_core_btc_bars(base)

    def _snapshot() -> str:
        return verify_core_btc_snapshot_identity(base)

    def _authority() -> dict[str, Any]:
        return verify_selector_identity_authority(base)

    return canonical_orchestration(
        load_core_bars=_load,
        verify_core_snapshot=_snapshot,
        load_selector_identity_authority=_authority,
        build_rows_fn=C.build_rows,
    )


def refuse_real_decomposition_outcome() -> None:
    raise RealDecompositionForbidden("REAL_DECOMPOSITION_OUTCOME_FORBIDDEN")


def frozen_contract_summary(repo: Path) -> dict[str, Any]:
    """Outcome-blind contract echo. No prices, no outcomes."""
    return {
        "UNIT": UNIT,
        "SELECTOR_CONTRACT": frozen_d2_selector_contract(),
        "PRIMARY_TARGET": PRIMARY_TARGET,
        "ADVERSE_SHARE_FORMULA": "MAE_SIDE / (MAE_SIDE + MAE_OPPOSITE)",
        "PATH_SCALE_FORMULA": "MAE_SIDE + MAE_OPPOSITE",
        "MAE_SIDE": "arithmetic_mae(SIDE, entry, future_288x5m_path)",
        "MAE_OPPOSITE": "arithmetic_mae(-SIDE, entry, SAME future_288x5m_path)",
        "PRIMARY_COMPARATOR": PRIMARY_COMPARATOR,
        "CONTROL_STRATA": CONTROL_STRATA,
        "RANDOM_SEED": int(RANDOM_SEED),
        "N_RANDOM_CONTROLS": int(N_RANDOM_CONTROLS),
        "CONTROL_P95_METHOD": CONTROL_P95_METHOD,
        "EXACT_SELECTOR_IDENTITY_IMPLEMENTED": EXACT_SELECTOR_IDENTITY_IMPLEMENTED,
        "CANONICAL_SELECTOR_DIGEST_FROZEN": CANONICAL_SELECTOR_DIGEST_FROZEN,
        "SELECTOR_IDENTITY_AUTHORITY_REL": SELECTOR_IDENTITY_AUTHORITY_REL,
        "SELECTOR_IDENTITY_AUTHORITY_PRESENT": (
            repo / SELECTOR_IDENTITY_AUTHORITY_REL
        ).is_file(),
        "SELECTOR_DIGEST_ALGORITHM": SELECTOR_DIGEST_ALGORITHM,
        "SCIENTIFIC_KERNEL_READY": SCIENTIFIC_KERNEL_READY,
        "CANONICAL_ORCHESTRATION_READY": CANONICAL_ORCHESTRATION_READY,
        "PERMIT_VERIFIER_READY": PERMIT_VERIFIER_READY,
        "EXECUTION_READY": EXECUTION_READY,
        "STATISTICAL_GATE": "MU_SHARE_RULE > CONTROL_SHARE_P95",
        "PRACTICAL_GATE": f"DELTA_SHARE >= {PRACTICAL_DELTA_SHARE}",
        "TEMPORAL_GATE": (
            f"DELTA_SHARE > 0 in at least {TEMPORAL_YEARS_REQUIRED} "
            f"of {TEMPORAL_YEARS_TOTAL} years"
        ),
        "PATH_SCALE_RELATIVE_BAR": float(PATH_SCALE_PRACTICAL_RELATIVE_BAR),
        "CLASSIFICATION_ORDER": list(CLASSIFICATION_ORDER),
        "FROZEN_RULE1_N": int(FROZEN_RULE1_N),
        "FROZEN_RULE1_YEAR_N": dict(FROZEN_RULE1_YEAR_N),
        "FROZEN_RULE1_N_MEANS_CONSTRUCTED_POPULATION": True,
        "FROZEN_SELECTOR_ABSTAIN_N": int(FROZEN_SELECTOR_ABSTAIN_N),
        "FROZEN_SELECTOR_ABSTAIN_YEAR_N": dict(FROZEN_SELECTOR_ABSTAIN_YEAR_N),
        "FROZEN_SELECTOR_ABSTAIN_PROVENANCE": FROZEN_SELECTOR_ABSTAIN_PROVENANCE,
        "FROZEN_D2_DISCOVERY_SHA256": FROZEN_D2_DISCOVERY_SHA256,
        "SELECTOR_IDENTITY_FACTS": verify_frozen_selector_identity_facts(repo),
        "RV_TRAILING_WINDOW": int(RV_TRAILING_WINDOW),
        "RV_PCTL": float(RV_PCTL),
        "FUTURE_BARS": int(FUTURE_BARS),
        "DESIGN_AUTHORITY_BLOCKERS": verify_design_authorities(repo),
        "EXECUTION_AUTHORIZED": EXECUTION_AUTHORIZED,
        "EXECUTION_PERMIT_PRESENT": (repo / EXECUTION_PERMIT_REL).is_file(),
        "REAL_DECOMPOSITION_OUTCOME_COMPUTED": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "BITMEX_2017_2019_REUSED_FOR_NEW_TARGET": False,
        "MARKET_07_CREATED": False,
    }


__all__ = [
    "CANONICAL_ORCHESTRATION_READY",
    "CANONICAL_SELECTOR_DIGEST_FROZEN",
    "CLASS_INVALID",
    "CLASS_NO_STRUCTURE",
    "CLASS_PROMISING",
    "CLASS_SCALE_COMPATIBLE",
    "CONTROL_P95_METHOD",
    "EXACT_SELECTOR_IDENTITY_IMPLEMENTED",
    "EXECUTION_AUTHORIZED",
    "EXECUTION_PERMIT_REL",
    "EXECUTION_READY",
    "FROZEN_SELECTOR_ABSTAIN_N",
    "FROZEN_SELECTOR_ABSTAIN_YEAR_N",
    "IMPLEMENTATION_FILES",
    "PERMIT_VERIFIER_READY",
    "REVIEW_JSON_REL",
    "REVIEW_MD_REL",
    "SCIENTIFIC_KERNEL_READY",
    "SELECTOR_DIGEST_ALGORITHM",
    "SELECTOR_IDENTITY_AUTHORITY_KIND",
    "SELECTOR_IDENTITY_AUTHORITY_REL",
    "SELECTOR_IDENTITY_AUTHORITY_UNIT",
    "UNIT",
    "ExecutionNotAuthorized",
    "ExecutionPermit",
    "FuturePathReconstructionError",
    "PermitAuthorityError",
    "SelectorIdentityError",
    "TargetRow",
    "bind_selector_identity_authority_census",
    "build_target_rows",
    "canonical_orchestration",
    "compute_run_identity",
    "control_p95",
    "current_artifact_sha256",
    "current_implementation_file_sha256",
    "evaluate_decomposition",
    "execute_decomposition",
    "frozen_contract_summary",
    "frozen_d2_selector_identity_facts",
    "future_bars_for_row",
    "load_canonical_core_btc_bars",
    "load_selector_identity_authority",
    "refuse_real_decomposition_outcome",
    "selector_digest",
    "selector_identity",
    "selector_identity_authority_payload",
    "target_row_from_discovery_row",
    "tracked_permit_expected_authority",
    "verify_core_btc_snapshot_identity",
    "verify_frozen_selector_identity_facts",
    "verify_selector_identity",
    "verify_selector_identity_authority",
    "verify_selector_identity_authority_payload",
    "verify_tracked_permit",
]
