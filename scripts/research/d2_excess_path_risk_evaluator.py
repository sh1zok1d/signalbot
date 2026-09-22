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


class ExecutionNotAuthorized(RuntimeError):
    """Real CORE BTC decomposition execution is not authorized."""


class SelectorIdentityError(RuntimeError):
    """Reconstructed RULE_1 mask is not the frozen 1791 / year breakdown."""


class FuturePathReconstructionError(RuntimeError):
    """The exact frozen 288x5m PerpBar future path could not be re-walked."""


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


def selector_identity(
    rows: Sequence[C.DiscoveryRow],
    mask: np.ndarray,
) -> dict[str, Any]:
    """RULE_1 mask census. Reports only; does not modify the selector."""
    mask_arr = np.asarray(mask, dtype=bool)
    if mask_arr.shape[0] != len(rows):
        raise SelectorIdentityError("MASK_ROW_SHAPE")
    year_counts = {year: 0 for year in CONTROL_YEARS}
    for row, flag in zip(rows, mask_arr.tolist(), strict=True):
        if not flag:
            continue
        key = str(int(row.year))
        if key not in year_counts:
            raise SelectorIdentityError(f"UNEXPECTED_YEAR:{key}")
        year_counts[key] += 1
    return {
        "RULE_1_ROW_COUNT": int(mask_arr.sum()),
        "RULE_1_YEAR_BREAKDOWN": year_counts,
    }


def verify_selector_identity(
    rows: Sequence[C.DiscoveryRow],
    mask: np.ndarray,
) -> dict[str, Any]:
    """Fail closed unless the reconstructed mask is exactly 1791 / frozen years."""
    census = selector_identity(rows, mask)
    if int(census["RULE_1_ROW_COUNT"]) != int(FROZEN_RULE1_N):
        raise SelectorIdentityError(
            f"RULE_1_N:{census['RULE_1_ROW_COUNT']}!={FROZEN_RULE1_N}"
        )
    if census["RULE_1_YEAR_BREAKDOWN"] != dict(FROZEN_RULE1_YEAR_N):
        raise SelectorIdentityError(f"RULE_1_YEAR_N:{census['RULE_1_YEAR_BREAKDOWN']}")
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
        float(np.percentile(control_share_means, 95.0))
        if bool(np.all(np.isfinite(control_share_means)))
        else None
    )
    control_scale_p95 = (
        float(np.percentile(control_scale_means, 95.0))
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


def _require_execution_permit(
    execution_authority: Mapping[str, Any] | ExecutionPermit | None,
    *,
    repo: Path,
) -> None:
    """No permit, no real decomposition. Fails closed on every path."""
    permit_path = repo / EXECUTION_PERMIT_REL
    if not permit_path.is_file():
        raise ExecutionNotAuthorized("NO_EXECUTION_PERMIT")
    if execution_authority is None:
        raise ExecutionNotAuthorized("EXECUTION_AUTHORITY_REQUIRED")
    if EXECUTION_AUTHORIZED is not True:
        raise ExecutionNotAuthorized("EXECUTION_AUTHORIZED_FALSE")
    if isinstance(execution_authority, ExecutionPermit):
        authority = {
            "design_sha256": execution_authority.design_sha256,
            "review_sha256": execution_authority.review_sha256,
            "implementation_sha256": execution_authority.implementation_sha256,
            "core_btc_snapshot": execution_authority.core_btc_snapshot,
            "run_identity": execution_authority.run_identity,
        }
    else:
        authority = dict(execution_authority)
    hashes = current_artifact_sha256(repo)
    expected = {
        "design_sha256": hashes["DESIGN_JSON_SHA256"],
        "review_sha256": file_sha256(repo / REVIEW_JSON_REL),
        "implementation_sha256": hashes["IMPLEMENTATION_FILE_SHA256"][
            "scripts/research/d2_excess_path_risk_evaluator.py"
        ],
        "core_btc_snapshot": C.CORE_BTC_SNAPSHOT,
    }
    for key, value in expected.items():
        if str(authority.get(key)) != str(value):
            raise ExecutionNotAuthorized(f"PERMIT_MISMATCH:{key}")
    stored = json.loads(permit_path.read_text(encoding="utf-8"))
    if str(authority.get("run_identity") or "") != str(stored.get("run_identity") or ""):
        raise ExecutionNotAuthorized("PERMIT_RUN_IDENTITY_MISMATCH")
    raise RealDecompositionForbidden("PERMIT_PRESENT_BUT_UNIT_REFUSES")


def load_canonical_core_btc_bars(
    repo: Path,
    *,
    execution_authority: Mapping[str, Any] | ExecutionPermit | None,
) -> dict[int, PerpBar]:
    """Load frozen CORE BTC 5m bars. Hard-gated: no permit, no bars."""
    _require_execution_permit(execution_authority, repo=repo)
    log = C.OpenedFileLog()
    return C.load_core_btc_5m(log, repo=repo)


def execute_decomposition(**kwargs: Any) -> dict[str, Any]:
    """Real canonical 2020-2024 decomposition. Refused in this unit.

    A future one-shot execution unit must supply an immutable permit. This
    unit creates none, so every call fails closed before any CORE BTC byte
    is read and before any ADVERSE_SHARE is computed.
    """
    repo = kwargs.get("repo")
    base = repo if isinstance(repo, Path) else C.repo_root()
    _require_execution_permit(kwargs.get("execution_authority"), repo=base)
    raise RealDecompositionForbidden("REAL_DECOMPOSITION_OUTCOME_FORBIDDEN")


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
    "CLASS_INVALID",
    "CLASS_NO_STRUCTURE",
    "CLASS_PROMISING",
    "CLASS_SCALE_COMPATIBLE",
    "EXECUTION_AUTHORIZED",
    "EXECUTION_PERMIT_REL",
    "IMPLEMENTATION_FILES",
    "REVIEW_JSON_REL",
    "REVIEW_MD_REL",
    "UNIT",
    "ExecutionNotAuthorized",
    "ExecutionPermit",
    "FuturePathReconstructionError",
    "SelectorIdentityError",
    "TargetRow",
    "build_target_rows",
    "compute_run_identity",
    "current_artifact_sha256",
    "current_implementation_file_sha256",
    "evaluate_decomposition",
    "execute_decomposition",
    "frozen_contract_summary",
    "future_bars_for_row",
    "load_canonical_core_btc_bars",
    "refuse_real_decomposition_outcome",
    "selector_identity",
    "target_row_from_discovery_row",
    "verify_selector_identity",
]
