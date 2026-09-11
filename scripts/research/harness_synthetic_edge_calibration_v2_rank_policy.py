#!/usr/bin/env python3
"""Fixture-only V2 rank-degeneracy policy implementation.

Frozen contract (read together; Amendment_001 controls where it clarifies):

- original prereg HEAD ``ada237edc330b44bc412332e263f124757919e93``
- Amendment_001 HEAD ``d8f0a996bc4341d0cbe01a1a061130b889ed5e75``

This module makes those frozen V2 semantics executable and testable. It does
not execute the 3200-world production grid, mint RESULT/WORLD_RECORDS, create
ARM, or consume V1 authority.

Scientific primitives (DGP, RNG, OLS, rank, bootstrap, placebo, visibility,
candidate definitions, world seeds) are imported unchanged from the V1 lib.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.harness_synthetic_edge_calibration_v1_lib import (
    ERA_NAMES,
    FEATURE_IDS,
    IncompleteWorld,
    SCORED_ERAS,
    WILSON_Z,
    _design_matrix,
    ae_metrics,
    candidate_features,
    compose_gates,
    era_mean_improvements,
    era_slices,
    expanding_era_predictions,
    fit_lstsq,
    placebo_q95,
    predict,
    prediction_bootstrap,
    scored_mask,
    select_blind,
    simulate_dgp,
    taxonomy_of,
    visibility_from_residuals,
    wilson_interval,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
AMENDMENT_JSON = (
    REPO_ROOT
    / "docs"
    / "research"
    / "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG_AMENDMENT_001.json"
)
ORIGINAL_PREREG_JSON = (
    REPO_ROOT
    / "docs"
    / "research"
    / "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG.json"
)

CONTRACT_ORIGINAL_HEAD = "ada237edc330b44bc412332e263f124757919e93"
CONTRACT_ORIGINAL_TREE = "ba1c0873879b7ea8556c3e238f8b962b91da6dc2"
CONTRACT_AMENDMENT_HEAD = "d8f0a996bc4341d0cbe01a1a061130b889ed5e75"
CONTRACT_AMENDMENT_TREE = "09dca9b1240a43d5de9de0dadf32d27e00e7eaea"

WORLD_VALID = "WORLD_VALID"
WORLD_INVALID = "WORLD_INVALID"
CANDIDATE_IDENTIFIABLE = "CANDIDATE_IDENTIFIABLE"
CANDIDATE_NOT_IDENTIFIABLE = "CANDIDATE_NOT_IDENTIFIABLE"
CANDIDATE_UNDEFINED_ON_INVALID_WORLD = "CANDIDATE_UNDEFINED_ON_INVALID_WORLD"

REASON_RANK_DEFICIENT = "RANK_DEFICIENT"
REASON_NONFINITE_FIT_OR_PREDICTION = "NONFINITE_FIT_OR_PREDICTION"
REASON_DESIGN_SHAPE_INVALID = "DESIGN_SHAPE_INVALID"
REASON_NONFINITE_AE_OR_RELATIVE_MAE = "NONFINITE_AE_OR_RELATIVE_MAE"
REASON_NONFINITE_BOOTSTRAP = "NONFINITE_BOOTSTRAP"
REASON_NONFINITE_PLACEBO = "NONFINITE_PLACEBO"
REASON_NONFINITE_VISIBILITY = "NONFINITE_VISIBILITY"

CLOSED_REASON_TAXONOMY = (
    REASON_RANK_DEFICIENT,
    REASON_NONFINITE_FIT_OR_PREDICTION,
    REASON_DESIGN_SHAPE_INVALID,
    REASON_NONFINITE_AE_OR_RELATIVE_MAE,
    REASON_NONFINITE_BOOTSTRAP,
    REASON_NONFINITE_PLACEBO,
    REASON_NONFINITE_VISIBILITY,
)

# Frozen execution-order precedence (Amendment_001 §4).
# Visibility-only does not recode identifiability; NONFINITE_VISIBILITY is reserved.
REASON_PRECEDENCE = (
    REASON_DESIGN_SHAPE_INVALID,
    REASON_RANK_DEFICIENT,
    REASON_NONFINITE_FIT_OR_PREDICTION,
    REASON_NONFINITE_AE_OR_RELATIVE_MAE,
    REASON_NONFINITE_BOOTSTRAP,
    REASON_NONFINITE_PLACEBO,
)

NOT_ERA_SCOPED = "NOT_ERA_SCOPED"
FIRST_FAILING_ERA_VALUES = ("E2", "E3", "E4", "E5", NOT_ERA_SCOPED)

COVERAGE_ADEQUATE = "ADEQUATE"
COVERAGE_INSUFFICIENT = "INSUFFICIENT_IDENTIFIABILITY"
HARD_FLOOR_IDENTIFIABLE = 200
WORLD_VALID_RATE_MIN_WILSON_LOWER = 0.95

SELECTION_NO_CANDIDATE = "NO_CANDIDATE"
SELECTION_SELECTED = "SELECTED"

MECHANICAL_STRUCTURAL_INCOMPLETE = "INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM"
MECHANICAL_INSUFFICIENT_IDENTIFIABILITY = "INSUFFICIENT_IDENTIFIABILITY_NO_METHODOLOGY_CLAIM"

L_VALUES = tuple(range(11))

BLIND_TAXONOMY_COUNT_FIELDS = (
    "BLIND_WORLD_COUNT",
    "TRUE_DISCOVERY",
    "PROXY_DISCOVERY",
    "FALSE_DISCOVERY",
    "NO_DISCOVERY",
    "ANY_EDGE_DECLARED",
    "USEFUL_DISCOVERY",
)

INHERITED_SELECTED_FEATURE_FIELDS = tuple(
    f"selected_{fid}_{gate}"
    for gate in ("STRICT_PASS", "STRICT_PASS_EX_MATERIALITY")
    for fid in FEATURE_IDS
)

AMENDED_F01_THRESHOLDS = {
    ("SMALL|2500", "F01"): 0.75,
    ("TINY_NOISY|5000", "F01"): 0.70,
}

PRODUCTION_N = frozenset({2500, 5000, 10000})
PRODUCTION_PLANNED_WORLDS = 3200

_AMENDMENT_CACHE: dict[str, Any] | None = None
_ORIGINAL_CACHE: dict[str, Any] | None = None


class ProductionGridForbidden(RuntimeError):
    """V2 fixture implementation must not execute the 3200-world production grid."""


class SelectiveCellCombineForbidden(RuntimeError):
    """Amendment_001 forbids combining a selective cell re-execution with a prior attempt."""


class UndefinedCoverageDenominator(RuntimeError):
    """Identifiability coverage with undefined/non-positive denominator fails closed."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_amendment() -> dict[str, Any]:
    global _AMENDMENT_CACHE
    if _AMENDMENT_CACHE is None:
        _AMENDMENT_CACHE = json.loads(AMENDMENT_JSON.read_text(encoding="utf-8"))
    return _AMENDMENT_CACHE


def load_original_prereg() -> dict[str, Any]:
    global _ORIGINAL_CACHE
    if _ORIGINAL_CACHE is None:
        _ORIGINAL_CACHE = json.loads(ORIGINAL_PREREG_JSON.read_text(encoding="utf-8"))
    return _ORIGINAL_CACHE


def frozen_coverage_table() -> dict[str, dict[str, float]]:
    """Exact 8×10 coverage table from Amendment_001. Do not derive from output."""
    return load_amendment()["amended_min_wilson_lower_by_cell_candidate"]


def original_coverage_table() -> dict[str, dict[str, float]]:
    return load_original_prereg()["coverage_gate"]["min_wilson_lower_by_cell_candidate"]


def frozen_coverage_thresholds_flat() -> dict[tuple[str, str], float]:
    table = frozen_coverage_table()
    out: dict[tuple[str, str], float] = {}
    for cell, by_fid in table.items():
        for fid, threshold in by_fid.items():
            out[(cell, fid)] = float(threshold)
    return out


def frozen_required_coverage_map() -> dict[str, Any]:
    """Exact 33-entry required-coverage dependency map from Amendment_001."""
    return load_amendment()["required_coverage_map"]["conclusions"]


def coverage_table_entry_count() -> int:
    return sum(len(by_fid) for by_fid in frozen_coverage_table().values())


def required_coverage_map_count() -> int:
    return len(frozen_required_coverage_map())


def amended_threshold_changes() -> dict[tuple[str, str], tuple[float, float]]:
    original = original_coverage_table()
    amended = frozen_coverage_table()
    changes: dict[tuple[str, str], tuple[float, float]] = {}
    for cell, by_fid in original.items():
        for fid, before in by_fid.items():
            after = float(amended[cell][fid])
            if float(before) != after:
                changes[(cell, fid)] = (float(before), after)
    return changes


def assert_not_production_grid(*, n_rows: int | None = None, planned_worlds: int | None = None) -> None:
    if n_rows is not None and int(n_rows) in PRODUCTION_N:
        raise ProductionGridForbidden(
            "V2 fixture implementation must not use production N values"
        )
    if planned_worlds is not None and int(planned_worlds) >= PRODUCTION_PLANNED_WORLDS:
        raise ProductionGridForbidden(
            "V2 fixture implementation must not execute the canonical 3200-world production grid"
        )


def run_frozen_production_grid(*_args: Any, **_kwargs: Any) -> None:
    raise ProductionGridForbidden(
        "V2 fixture implementation must not execute the canonical 3200-world production grid"
    )


def _reason_rank(reason: str) -> int:
    try:
        return REASON_PRECEDENCE.index(reason)
    except ValueError:
        return len(REASON_PRECEDENCE) + CLOSED_REASON_TAXONOMY.index(reason)


def choose_reason_by_precedence(reasons: Sequence[str]) -> str:
    if not reasons:
        raise ValueError("no reasons to choose")
    unknown = [r for r in reasons if r not in CLOSED_REASON_TAXONOMY]
    if unknown:
        raise ValueError(f"reason outside closed taxonomy: {unknown}")
    return min(reasons, key=_reason_rank)


def _era_index(era: str) -> int:
    return ERA_NAMES.index(era)


def choose_first_failing_era(eras: Sequence[str]) -> str:
    scoped = [e for e in eras if e in SCORED_ERAS]
    if not scoped:
        return NOT_ERA_SCOPED
    return min(scoped, key=_era_index)


def _map_incomplete_reason(message: str) -> str:
    text = str(message)
    if "shape" in text.lower():
        return REASON_DESIGN_SHAPE_INVALID
    if "not full rank" in text:
        return REASON_RANK_DEFICIENT
    if "relative MAE" in text or "non-finite AE" in text:
        return REASON_NONFINITE_AE_OR_RELATIVE_MAE
    if "non-finite" in text:
        return REASON_NONFINITE_FIT_OR_PREDICTION
    raise ValueError(f"unmapped IncompleteWorld message: {text}")


@dataclass(frozen=True)
class RankDiagnostics:
    design_nrows: int
    design_ncols: int
    design_rank: int
    required_rank: int


@dataclass(frozen=True)
class FitInspection:
    ok: bool
    reason: str | None = None
    first_failing_era: str | None = None
    rank_diagnostics: RankDiagnostics | None = None


def inspect_design_window(
    y_train: np.ndarray,
    x1_train: np.ndarray,
    x2_train: np.ndarray,
    feature_train: np.ndarray | None,
    *,
    scored_era: str,
) -> FitInspection:
    y_train = np.asarray(y_train, dtype=np.float64)
    cols = [np.asarray(x1_train, dtype=np.float64), np.asarray(x2_train, dtype=np.float64)]
    if feature_train is not None:
        cols.append(np.asarray(feature_train, dtype=np.float64))
    try:
        X = _design_matrix(*cols)
    except (ValueError, IndexError):
        return FitInspection(
            ok=False,
            reason=REASON_DESIGN_SHAPE_INVALID,
            first_failing_era=scored_era,
            rank_diagnostics=RankDiagnostics(0, 0, 0, 3 if feature_train is None else 4),
        )
    required = int(X.shape[1]) if X.ndim == 2 else (3 if feature_train is None else 4)
    nrows = int(X.shape[0]) if X.ndim == 2 else 0
    ncols = int(X.shape[1]) if X.ndim == 2 else 0
    if X.ndim != 2 or y_train.ndim != 1 or nrows != int(y_train.shape[0]) or nrows < 1 or ncols < 1:
        return FitInspection(
            ok=False,
            reason=REASON_DESIGN_SHAPE_INVALID,
            first_failing_era=scored_era,
            rank_diagnostics=RankDiagnostics(nrows, ncols, 0, required),
        )
    rank = int(np.linalg.matrix_rank(X))
    if rank < ncols:
        return FitInspection(
            ok=False,
            reason=REASON_RANK_DEFICIENT,
            first_failing_era=scored_era,
            rank_diagnostics=RankDiagnostics(nrows, ncols, rank, required),
        )
    try:
        coef = fit_lstsq(X, y_train)
    except IncompleteWorld as exc:
        return FitInspection(
            ok=False,
            reason=_map_incomplete_reason(exc),
            first_failing_era=scored_era,
            rank_diagnostics=RankDiagnostics(nrows, ncols, rank, required),
        )
    if not np.all(np.isfinite(coef)):
        return FitInspection(
            ok=False,
            reason=REASON_NONFINITE_FIT_OR_PREDICTION,
            first_failing_era=scored_era,
            rank_diagnostics=RankDiagnostics(nrows, ncols, rank, required),
        )
    return FitInspection(
        ok=True,
        rank_diagnostics=RankDiagnostics(nrows, ncols, rank, required),
    )


def inspect_expanding_fit(
    y: np.ndarray,
    x1: np.ndarray,
    x2: np.ndarray,
    feature: np.ndarray | None,
    n_rows: int,
    *,
    score_feature: np.ndarray | None = None,
) -> FitInspection:
    """Walk expanding scored eras in frozen order; first era failure wins."""
    slices = era_slices(n_rows)
    y = np.asarray(y, dtype=np.float64)
    x1 = np.asarray(x1, dtype=np.float64)
    x2 = np.asarray(x2, dtype=np.float64)
    feat = None if feature is None else np.asarray(feature, dtype=np.float64)
    score_feat = feat if score_feature is None else np.asarray(score_feature, dtype=np.float64)
    for era_i, era_name in enumerate(ERA_NAMES):
        if era_i == 0:
            continue
        train = slice(0, slices[era_name].start)
        score = slices[era_name]
        if train.stop > score.start:
            return FitInspection(
                ok=False,
                reason=REASON_DESIGN_SHAPE_INVALID,
                first_failing_era=era_name,
            )
        feature_train = None if feat is None else feat[train]
        insp = inspect_design_window(y[train], x1[train], x2[train], feature_train, scored_era=era_name)
        if not insp.ok:
            return insp
        cols_score = [x1[score], x2[score]]
        if score_feat is not None:
            cols_score.append(score_feat[score])
        X_score = _design_matrix(*cols_score)
        X_train = _design_matrix(
            x1[train],
            x2[train],
            *([] if feat is None else [feat[train]]),
        )
        try:
            coef = fit_lstsq(X_train, y[train])
            pred = predict(X_score, coef)
        except IncompleteWorld as exc:
            return FitInspection(
                ok=False,
                reason=_map_incomplete_reason(exc),
                first_failing_era=era_name,
                rank_diagnostics=insp.rank_diagnostics,
            )
        if not np.all(np.isfinite(pred)):
            return FitInspection(
                ok=False,
                reason=REASON_NONFINITE_FIT_OR_PREDICTION,
                first_failing_era=era_name,
                rank_diagnostics=insp.rank_diagnostics,
            )
    return FitInspection(ok=True)


def inspect_ae(
    y: np.ndarray,
    base_pred: np.ndarray,
    cand_pred: np.ndarray,
    n_rows: int,
) -> FitInspection:
    mask = scored_mask(n_rows)
    slices = era_slices(n_rows)
    first_era = None
    for era in SCORED_ERAS:
        slc = slices[era]
        era_mask = np.zeros(n_rows, dtype=bool)
        era_mask[slc] = True
        try:
            ae_metrics(y, base_pred, cand_pred, era_mask)
        except IncompleteWorld:
            first_era = era
            break
    try:
        ae_metrics(y, base_pred, cand_pred, mask)
    except IncompleteWorld:
        return FitInspection(
            ok=False,
            reason=REASON_NONFINITE_AE_OR_RELATIVE_MAE,
            first_failing_era=first_era or NOT_ERA_SCOPED,
        )
    return FitInspection(ok=True)


@dataclass(frozen=True)
class NonidentifiabilityRecord:
    candidate_id: str
    scenario: str
    N: int
    world_id: str
    reason: str
    first_failing_era: str
    design_nrows: int | None = None
    design_ncols: int | None = None
    design_rank: int | None = None
    required_rank: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "candidate_id": self.candidate_id,
            "scenario": self.scenario,
            "N": self.N,
            "world_id": self.world_id,
            "reason": self.reason,
            "first_failing_era": self.first_failing_era,
        }
        if self.reason == REASON_RANK_DEFICIENT:
            payload["design_nrows"] = self.design_nrows
            payload["design_ncols"] = self.design_ncols
            payload["design_rank"] = self.design_rank
            payload["required_rank"] = self.required_rank
        return payload


@dataclass
class CandidateWorldRecord:
    candidate_id: str
    state: str
    detected: bool | None
    nonidentifiability: NonidentifiabilityRecord | None = None
    gates: dict[str, Any] | None = None
    mean_ae_improvement: float | None = None


@dataclass
class WorldRecordV2:
    world_id: str
    scenario: str
    N: int
    world_index: int
    world_state: str
    L: int | None
    selection_state: str | None
    selected_candidate: str | None
    taxonomy: str | None
    candidates: dict[str, CandidateWorldRecord] = field(default_factory=dict)
    baseline_failure: FitInspection | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "scenario": self.scenario,
            "N": self.N,
            "world_index": self.world_index,
            "world_state": self.world_state,
            "L": self.L,
            "selection_state": self.selection_state,
            "selected_candidate": self.selected_candidate,
            "taxonomy": self.taxonomy,
            "candidates": {
                cid: {
                    "state": rec.state,
                    "detected": rec.detected,
                    "nonidentifiability": rec.nonidentifiability.to_dict()
                    if rec.nonidentifiability
                    else None,
                }
                for cid, rec in self.candidates.items()
            },
        }


def _nonident_record(
    *,
    cid: str,
    scenario: str,
    n_rows: int,
    world_id: str,
    inspection: FitInspection,
) -> NonidentifiabilityRecord:
    diag = inspection.rank_diagnostics
    return NonidentifiabilityRecord(
        candidate_id=cid,
        scenario=scenario,
        N=n_rows,
        world_id=world_id,
        reason=inspection.reason or REASON_RANK_DEFICIENT,
        first_failing_era=inspection.first_failing_era or NOT_ERA_SCOPED,
        design_nrows=diag.design_nrows if diag else None,
        design_ncols=diag.design_ncols if diag else None,
        design_rank=diag.design_rank if diag else None,
        required_rank=diag.required_rank if diag else None,
    )


def apply_e1_zero_features(
    features: dict[str, np.ndarray],
    zero_ids: frozenset[str],
    n_rows: int,
) -> dict[str, np.ndarray]:
    if not zero_ids:
        return features
    slc = era_slices(n_rows)["E1"]
    out = {cid: np.asarray(arr, dtype=np.float64).copy() for cid, arr in features.items()}
    for cid in zero_ids:
        out[cid][slc] = 0.0
    return out


def zero_e1_baseline_regressors(world: Mapping[str, np.ndarray]) -> dict[str, Any]:
    """Fixture-only injection: zero X1/X2 on E1 after the unchanged DGP."""
    n_rows = int(np.asarray(world["Y"]).shape[0])
    slc = era_slices(n_rows)["E1"]
    out: dict[str, Any] = {}
    for key, value in world.items():
        if isinstance(value, np.ndarray) and key in {"X1", "X2"}:
            copied = value.copy()
            copied[slc] = 0.0
            out[key] = copied
        else:
            out[key] = value
    return out


def evaluate_v2_world(
    world: Mapping[str, Any],
    *,
    scenario: str,
    n_rows: int,
    world_index: int = 0,
    zero_e1_features: frozenset[str] | set[str] = frozenset(),
    zero_e1_baseline: bool = False,
    force_candidate_reason: dict[str, str] | None = None,
    skip_bootstrap_placebo: bool = True,
    feature_overrides: Mapping[str, np.ndarray] | None = None,
) -> WorldRecordV2:
    """Evaluate one world under frozen V2 rank-degeneracy semantics.

    ``zero_e1_features`` / ``zero_e1_baseline`` are fixture-only injections
    applied after the unchanged DGP. They do not change DGP, RNG, seeds, or
    candidate definitions.
    """
    assert_not_production_grid(n_rows=n_rows)
    if zero_e1_baseline:
        world = zero_e1_baseline_regressors(world)
    y = np.asarray(world["Y"], dtype=np.float64)
    x1 = np.asarray(world["X1"], dtype=np.float64)
    x2 = np.asarray(world["X2"], dtype=np.float64)
    world_id = str(world.get("world_identity", f"{scenario}|{n_rows}|{world_index}"))
    feats = apply_e1_zero_features(candidate_features(world), frozenset(zero_e1_features), n_rows)
    if feature_overrides:
        for cid, arr in feature_overrides.items():
            feats[cid] = np.asarray(arr, dtype=np.float64)
    forced = force_candidate_reason or {}

    baseline_insp = inspect_expanding_fit(y, x1, x2, None, n_rows)
    if not baseline_insp.ok:
        return WorldRecordV2(
            world_id=world_id,
            scenario=scenario,
            N=n_rows,
            world_index=world_index,
            world_state=WORLD_INVALID,
            L=None,
            selection_state=None,
            selected_candidate=None,
            taxonomy=None,
            baseline_failure=baseline_insp,
            candidates={
                cid: CandidateWorldRecord(
                    candidate_id=cid,
                    state=CANDIDATE_UNDEFINED_ON_INVALID_WORLD,
                    detected=None,
                )
                for cid in FEATURE_IDS
            },
        )

    candidate_recs: dict[str, CandidateWorldRecord] = {}
    identifiable_rows: list[dict[str, Any]] = []
    for cid in FEATURE_IDS:
        if cid in forced:
            reason = forced[cid]
            if reason not in CLOSED_REASON_TAXONOMY:
                raise ValueError(f"forced reason outside taxonomy: {reason}")
            era = "E2" if reason == REASON_RANK_DEFICIENT else NOT_ERA_SCOPED
            candidate_recs[cid] = CandidateWorldRecord(
                candidate_id=cid,
                state=CANDIDATE_NOT_IDENTIFIABLE,
                detected=None,
                nonidentifiability=NonidentifiabilityRecord(
                    candidate_id=cid,
                    scenario=scenario,
                    N=n_rows,
                    world_id=world_id,
                    reason=reason,
                    first_failing_era=era,
                    design_nrows=n_rows // 5 if reason == REASON_RANK_DEFICIENT else None,
                    design_ncols=4 if reason == REASON_RANK_DEFICIENT else None,
                    design_rank=3 if reason == REASON_RANK_DEFICIENT else None,
                    required_rank=4 if reason == REASON_RANK_DEFICIENT else None,
                ),
            )
            continue

        insp = inspect_expanding_fit(y, x1, x2, feats[cid], n_rows)
        if not insp.ok:
            candidate_recs[cid] = CandidateWorldRecord(
                candidate_id=cid,
                state=CANDIDATE_NOT_IDENTIFIABLE,
                detected=None,
                nonidentifiability=_nonident_record(
                    cid=cid,
                    scenario=scenario,
                    n_rows=n_rows,
                    world_id=world_id,
                    inspection=insp,
                ),
            )
            continue
        try:
            preds = expanding_era_predictions(y, x1, x2, feats[cid], n_rows)
        except IncompleteWorld as exc:
            mapped = _map_incomplete_reason(exc)
            candidate_recs[cid] = CandidateWorldRecord(
                candidate_id=cid,
                state=CANDIDATE_NOT_IDENTIFIABLE,
                detected=None,
                nonidentifiability=NonidentifiabilityRecord(
                    candidate_id=cid,
                    scenario=scenario,
                    N=n_rows,
                    world_id=world_id,
                    reason=mapped,
                    first_failing_era=NOT_ERA_SCOPED,
                ),
            )
            continue
        ae_insp = inspect_ae(y, preds["BASE_PRED"], preds["CAND_PRED"], n_rows)
        if not ae_insp.ok:
            candidate_recs[cid] = CandidateWorldRecord(
                candidate_id=cid,
                state=CANDIDATE_NOT_IDENTIFIABLE,
                detected=None,
                nonidentifiability=_nonident_record(
                    cid=cid,
                    scenario=scenario,
                    n_rows=n_rows,
                    world_id=world_id,
                    inspection=ae_insp,
                ),
            )
            continue
        if not skip_bootstrap_placebo:
            mask = scored_mask(n_rows)
            ae_imp_full = np.full(n_rows, np.nan, dtype=np.float64)
            ae_imp_full[mask] = (
                np.abs(y[mask] - preds["BASE_PRED"][mask])
                - np.abs(y[mask] - preds["CAND_PRED"][mask])
            )
            rng = np.random.default_rng(0)
            boot = prediction_bootstrap(
                ae_imp_full,
                n_rows,
                replicates=3,
                block_rows=2,
                rng=rng,
            )
            if boot.get("bootstrap_invalid") or boot.get("world_invalid"):
                candidate_recs[cid] = CandidateWorldRecord(
                    candidate_id=cid,
                    state=CANDIDATE_NOT_IDENTIFIABLE,
                    detected=None,
                    nonidentifiability=NonidentifiabilityRecord(
                        candidate_id=cid,
                        scenario=scenario,
                        N=n_rows,
                        world_id=world_id,
                        reason=REASON_NONFINITE_BOOTSTRAP,
                        first_failing_era=NOT_ERA_SCOPED,
                    ),
                )
                continue
            plac = placebo_q95(
                world=world,
                feature=feats[cid],
                n_rows=n_rows,
                replicates=3,
                rng=rng,
            )
            if plac.get("placebo_invalid") or plac.get("world_invalid"):
                candidate_recs[cid] = CandidateWorldRecord(
                    candidate_id=cid,
                    state=CANDIDATE_NOT_IDENTIFIABLE,
                    detected=None,
                    nonidentifiability=NonidentifiabilityRecord(
                        candidate_id=cid,
                        scenario=scenario,
                        N=n_rows,
                        world_id=world_id,
                        reason=REASON_NONFINITE_PLACEBO,
                        first_failing_era=NOT_ERA_SCOPED,
                    ),
                )
                continue
            # Visibility-only invalidity does not recode identifiability.
            visibility_from_residuals(
                y - preds["BASE_PRED"],
                np.asarray(world["S"], dtype=np.float64),
                n_rows,
                replicates=3,
                block_rows=2,
                rng=np.random.default_rng(1),
            )
        metrics = ae_metrics(y, preds["BASE_PRED"], preds["CAND_PRED"], scored_mask(n_rows))
        era_imp = era_mean_improvements(y, preds["BASE_PRED"], preds["CAND_PRED"], n_rows)
        cand_pos = int(np.sum(feats[cid][scored_mask(n_rows)] == 1.0))
        gates = compose_gates(
            mean_ae_improvement=metrics["MEAN_AE_IMPROVEMENT"],
            relative_mae_improvement=metrics["RELATIVE_MAE_IMPROVEMENT"],
            bootstrap_positive=False if skip_bootstrap_placebo else bool(boot["bootstrap_positive"]),
            placebo_separation=False if skip_bootstrap_placebo else (
                (not plac["placebo_invalid"])
                and np.isfinite(plac["placebo_q95"])
                and metrics["MEAN_AE_IMPROVEMENT"] > plac["placebo_q95"]
            ),
            era_improvements=era_imp,
            candidate_positive_count=cand_pos,
        )
        detected = bool(gates["STRICT_PASS"])
        candidate_recs[cid] = CandidateWorldRecord(
            candidate_id=cid,
            state=CANDIDATE_IDENTIFIABLE,
            detected=detected,
            gates=gates,
            mean_ae_improvement=float(metrics["MEAN_AE_IMPROVEMENT"]),
        )
        identifiable_rows.append(
            {
                "feature_id": cid,
                "MEAN_AE_IMPROVEMENT": float(metrics["MEAN_AE_IMPROVEMENT"]),
                "gates": gates,
            }
        )

    L = len(identifiable_rows)
    if L < 0 or L > 10:
        raise ValueError(f"L out of bounds: {L}")
    if L == 0:
        return WorldRecordV2(
            world_id=world_id,
            scenario=scenario,
            N=n_rows,
            world_index=world_index,
            world_state=WORLD_VALID,
            L=0,
            selection_state=SELECTION_NO_CANDIDATE,
            selected_candidate=None,
            taxonomy=None,
            candidates=candidate_recs,
        )

    selected = select_blind(identifiable_rows, gate="STRICT_PASS_EX_MATERIALITY")
    if selected == "NO_CANDIDATE":
        taxonomy = "NO_DISCOVERY"
        selection_state = SELECTION_SELECTED
        selected_out: str | None = None
    else:
        taxonomy = taxonomy_of(selected)
        if scenario == "NULL" and taxonomy != "NO_DISCOVERY":
            taxonomy = "FALSE_DISCOVERY"
        selection_state = SELECTION_SELECTED
        selected_out = selected
    return WorldRecordV2(
        world_id=world_id,
        scenario=scenario,
        N=n_rows,
        world_index=world_index,
        world_state=WORLD_VALID,
        L=L,
        selection_state=selection_state,
        selected_candidate=selected_out,
        taxonomy=taxonomy,
        candidates=candidate_recs,
    )


def useful_discovery(taxonomy: str | None) -> bool:
    return taxonomy in {"TRUE_DISCOVERY", "PROXY_DISCOVERY"}


def any_edge_declared(taxonomy: str | None) -> bool:
    return taxonomy in {"TRUE_DISCOVERY", "PROXY_DISCOVERY", "FALSE_DISCOVERY"}


def _empty_selected_counts() -> dict[str, int]:
    return {name: 0 for name in INHERITED_SELECTED_FEATURE_FIELDS}


def _wilson_or_none(successes: int, n: int) -> dict[str, float] | None:
    if n <= 0:
        return None
    return wilson_interval(successes, n)


@dataclass
class BlindStratum:
    L: int
    BLIND_WORLD_COUNT: int = 0
    TRUE_DISCOVERY: int = 0
    PROXY_DISCOVERY: int = 0
    FALSE_DISCOVERY: int = 0
    NO_DISCOVERY: int = 0
    ANY_EDGE_DECLARED: int = 0
    USEFUL_DISCOVERY: int = 0
    selected_counts: dict[str, int] = field(default_factory=_empty_selected_counts)

    def add(self, rec: WorldRecordV2) -> None:
        if rec.world_state != WORLD_VALID or rec.L in (None, 0):
            return
        self.BLIND_WORLD_COUNT += 1
        tax = rec.taxonomy or "NO_DISCOVERY"
        if tax == "TRUE_DISCOVERY":
            self.TRUE_DISCOVERY += 1
        elif tax == "PROXY_DISCOVERY":
            self.PROXY_DISCOVERY += 1
        elif tax == "FALSE_DISCOVERY":
            self.FALSE_DISCOVERY += 1
        elif tax == "NO_DISCOVERY":
            self.NO_DISCOVERY += 1
        if any_edge_declared(tax):
            self.ANY_EDGE_DECLARED += 1
        if useful_discovery(tax):
            self.USEFUL_DISCOVERY += 1
        if rec.selected_candidate:
            gates = rec.candidates[rec.selected_candidate].gates or {}
            cid = rec.selected_candidate
            if gates.get("STRICT_PASS") is True:
                self.selected_counts[f"selected_{cid}_STRICT_PASS"] += 1
            if gates.get("STRICT_PASS_EX_MATERIALITY") is True:
                self.selected_counts[f"selected_{cid}_STRICT_PASS_EX_MATERIALITY"] += 1

    def to_dict(self) -> dict[str, Any]:
        n = self.BLIND_WORLD_COUNT
        payload: dict[str, Any] = {k: getattr(self, k) for k in ("L",) + BLIND_TAXONOMY_COUNT_FIELDS}
        payload["TRUE_DISCOVERY_RATE"] = (self.TRUE_DISCOVERY / n) if n else None
        payload["USEFUL_DISCOVERY_RATE"] = (self.USEFUL_DISCOVERY / n) if n else None
        payload["TRUE_DISCOVERY_RATE_wilson"] = _wilson_or_none(self.TRUE_DISCOVERY, n)
        payload["USEFUL_DISCOVERY_RATE_wilson"] = _wilson_or_none(self.USEFUL_DISCOVERY, n)
        payload.update(self.selected_counts)
        return payload


def empty_l_distribution() -> dict[str, int]:
    return {f"L={k}": 0 for k in L_VALUES}


def add_l(dist: dict[str, int], L: int | None) -> None:
    if L is None:
        raise ValueError("WORLD_INVALID L is undefined and must not enter an L bucket")
    if L < 0 or L > 10:
        raise ValueError(f"L out of bounds: {L}")
    dist[f"L={L}"] += 1


def reconcile_l_distribution(dist: Mapping[str, int], world_valid_count: int) -> bool:
    return sum(int(dist[f"L={k}"]) for k in L_VALUES) == world_valid_count


def worlds_with_zero_identifiable(dist: Mapping[str, int]) -> int:
    return int(dist["L=0"])


def reconcile_blind_pooled_vs_strata(
    pooled: Mapping[str, Any],
    strata: Mapping[int, Mapping[str, Any]],
) -> dict[str, bool]:
    status: dict[str, bool] = {}
    fields = list(BLIND_TAXONOMY_COUNT_FIELDS) + list(INHERITED_SELECTED_FEATURE_FIELDS)
    for field_name in fields:
        total = sum(int(strata[L][field_name]) for L in range(1, 11) if L in strata)
        status[field_name] = total == int(pooled[field_name])
    status["all_fields_reconcile"] = all(status[f] for f in fields)
    return status


@dataclass
class CellAggregateV2:
    scenario: str
    N: int
    planned_worlds: int = 0
    world_valid_count: int = 0
    world_invalid_count: int = 0
    L_distribution: dict[str, int] = field(default_factory=empty_l_distribution)
    candidate_identifiable_count: dict[str, int] = field(
        default_factory=lambda: {c: 0 for c in FEATURE_IDS}
    )
    candidate_non_identifiable_count: dict[str, int] = field(
        default_factory=lambda: {c: 0 for c in FEATURE_IDS}
    )
    candidate_detection_count: dict[str, int] = field(
        default_factory=lambda: {c: 0 for c in FEATURE_IDS}
    )
    nonidentifiability_records: list[dict[str, Any]] = field(default_factory=list)
    blind_by_L: dict[int, BlindStratum] = field(
        default_factory=lambda: {L: BlindStratum(L=L) for L in range(1, 11)}
    )
    worlds: list[WorldRecordV2] = field(default_factory=list)

    def add(self, rec: WorldRecordV2) -> None:
        self.worlds.append(rec)
        self.planned_worlds += 1
        if rec.world_state == WORLD_INVALID:
            self.world_invalid_count += 1
            return
        self.world_valid_count += 1
        add_l(self.L_distribution, rec.L)
        for cid in FEATURE_IDS:
            cr = rec.candidates[cid]
            if cr.state == CANDIDATE_IDENTIFIABLE:
                self.candidate_identifiable_count[cid] += 1
                if cr.detected is True:
                    self.candidate_detection_count[cid] += 1
            elif cr.state == CANDIDATE_NOT_IDENTIFIABLE:
                self.candidate_non_identifiable_count[cid] += 1
                if cr.nonidentifiability:
                    self.nonidentifiability_records.append(cr.nonidentifiability.to_dict())
        if rec.L and rec.L > 0:
            self.blind_by_L[rec.L].add(rec)

    def pooled_blind(self) -> dict[str, Any]:
        pooled = BlindStratum(L=-1)
        for stratum in self.blind_by_L.values():
            pooled.BLIND_WORLD_COUNT += stratum.BLIND_WORLD_COUNT
            pooled.TRUE_DISCOVERY += stratum.TRUE_DISCOVERY
            pooled.PROXY_DISCOVERY += stratum.PROXY_DISCOVERY
            pooled.FALSE_DISCOVERY += stratum.FALSE_DISCOVERY
            pooled.NO_DISCOVERY += stratum.NO_DISCOVERY
            pooled.ANY_EDGE_DECLARED += stratum.ANY_EDGE_DECLARED
            pooled.USEFUL_DISCOVERY += stratum.USEFUL_DISCOVERY
            for key, value in stratum.selected_counts.items():
                pooled.selected_counts[key] += value
        return pooled.to_dict()

    def result_schema(self) -> dict[str, Any]:
        if not reconcile_l_distribution(self.L_distribution, self.world_valid_count):
            raise ValueError("L distribution does not reconcile to world_valid_count")
        zero_id = worlds_with_zero_identifiable(self.L_distribution)
        if zero_id != self.L_distribution["L=0"]:
            raise ValueError("worlds_with_zero_identifiable_candidates != count(L=0)")
        pooled = self.pooled_blind()
        strata = {L: self.blind_by_L[L].to_dict() for L in range(1, 11)}
        recon = reconcile_blind_pooled_vs_strata(pooled, strata)
        if not recon["all_fields_reconcile"]:
            raise ValueError(f"pooled BLIND counts disagree with L strata: {recon}")
        if pooled["BLIND_WORLD_COUNT"] != self.world_valid_count - zero_id:
            raise ValueError("sum L=1..10 BLIND_WORLD_COUNT != world_valid_count - count(L=0)")
        candidate_block = {}
        for cid in FEATURE_IDS:
            ident = self.candidate_identifiable_count[cid]
            nident = self.candidate_non_identifiable_count[cid]
            det = self.candidate_detection_count[cid]
            if ident + nident != self.world_valid_count:
                raise ValueError(
                    f"{cid} identifiable+non_identifiable != world_valid_count"
                )
            candidate_block[cid] = {
                "candidate_identifiable_count": ident,
                "candidate_non_identifiable_count": nident,
                "candidate_detection_count": det,
                "identifiability_rate": (ident / self.world_valid_count)
                if self.world_valid_count
                else None,
                "conditional_detection_rate": (det / ident) if ident else None,
            }
        return {
            "scenario": self.scenario,
            "N": self.N,
            "planned_worlds": self.planned_worlds,
            "world_valid_count": self.world_valid_count,
            "world_invalid_count": self.world_invalid_count,
            "candidates": candidate_block,
            "L_distribution": dict(self.L_distribution),
            "worlds_with_zero_identifiable_candidates": zero_id,
            "BLIND": {
                "by_L": strata,
                "pooled": pooled,
                "reconciliation_status": recon,
                "blind_not_claimed_invariant_to_L": True,
            },
            "selective_cell_reexecution_and_combine_forbidden": True,
        }


def aggregate_v2_records(records: Sequence[WorldRecordV2]) -> dict[tuple[str, int], CellAggregateV2]:
    cells: dict[tuple[str, int], CellAggregateV2] = {}
    for rec in records:
        key = (rec.scenario, rec.N)
        if key not in cells:
            cells[key] = CellAggregateV2(scenario=rec.scenario, N=rec.N)
        cells[key].add(rec)
    return cells


def candidate_coverage_verdict(
    *,
    candidate_identifiable_count: int,
    world_valid_count: int,
    threshold: float,
    apply_hard_floor: bool = True,
) -> str:
    """Frozen Wilson coverage on identifiable / world_valid. Fail closed if n undefined."""
    if world_valid_count is None or world_valid_count <= 0:
        raise UndefinedCoverageDenominator("candidate identifiability denominator is undefined")
    if apply_hard_floor and candidate_identifiable_count < HARD_FLOOR_IDENTIFIABLE:
        return COVERAGE_INSUFFICIENT
    interval = wilson_interval(candidate_identifiable_count, world_valid_count)
    if interval["lower"] < threshold:
        return COVERAGE_INSUFFICIENT
    return COVERAGE_ADEQUATE


def world_baseline_coverage_verdict(*, world_valid_count: int, planned_worlds: int) -> str:
    if planned_worlds is None or planned_worlds <= 0:
        raise UndefinedCoverageDenominator("planned_worlds denominator is undefined")
    interval = wilson_interval(world_valid_count, planned_worlds)
    if interval["lower"] < WORLD_VALID_RATE_MIN_WILSON_LOWER:
        return COVERAGE_INSUFFICIENT
    return COVERAGE_ADEQUATE


def evaluate_cell_coverage(
    cell: CellAggregateV2,
    *,
    apply_hard_floor: bool = True,
) -> dict[str, str]:
    table = frozen_coverage_thresholds_flat()
    verdicts: dict[str, str] = {}
    cell_key = f"{cell.scenario}|{cell.N}"
    for cid in FEATURE_IDS:
        threshold = table[(cell_key, cid)]
        try:
            verdicts[cid] = candidate_coverage_verdict(
                candidate_identifiable_count=cell.candidate_identifiable_count[cid],
                world_valid_count=cell.world_valid_count,
                threshold=threshold,
                apply_hard_floor=apply_hard_floor,
            )
        except UndefinedCoverageDenominator:
            verdicts[cid] = COVERAGE_INSUFFICIENT
    return verdicts


def _required_cell_candidates(entry: Mapping[str, Any]) -> dict[str, list[str]]:
    if "union" in entry:
        return {cell: list(cids) for cell, cids in entry["union"].items()}
    if "cells" in entry:
        per_cell = list(entry.get("candidates_per_named_cell") or entry.get("candidates") or [])
        return {cell: list(per_cell) for cell in entry["cells"]}
    cell = str(entry["cell"])
    return {cell: list(entry.get("candidates") or [])}


def required_coverage_for_conclusion(
    conclusion_id: str,
    *,
    candidate_verdicts_by_cell: Mapping[str, Mapping[str, str]],
    baseline_verdicts_by_cell: Mapping[str, str],
) -> str:
    entry = frozen_required_coverage_map()[conclusion_id]
    required = _required_cell_candidates(entry)
    for cell, fids in required.items():
        if baseline_verdicts_by_cell.get(cell) != COVERAGE_ADEQUATE:
            return COVERAGE_INSUFFICIENT
        for fid in fids:
            if candidate_verdicts_by_cell.get(cell, {}).get(fid) != COVERAGE_ADEQUATE:
                return COVERAGE_INSUFFICIENT
    return COVERAGE_ADEQUATE


def mechanical_conclusion_v2(
    *,
    structurally_complete: bool,
    coverage_for_conclusion: str,
    inherited_detection_conclusion: str,
) -> str:
    """Exact precedence: structural incompleteness > identifiability > inherited ladder."""
    if not structurally_complete:
        return MECHANICAL_STRUCTURAL_INCOMPLETE
    if coverage_for_conclusion == COVERAGE_INSUFFICIENT:
        return MECHANICAL_INSUFFICIENT_IDENTIFIABILITY
    return inherited_detection_conclusion


def null_claim_blocked_by_coverage(cell_verdicts: Mapping[str, str]) -> bool:
    """Claim-bearing NULL requires adequate coverage for all F01–F10."""
    return any(cell_verdicts.get(cid) != COVERAGE_ADEQUATE for cid in FEATURE_IDS)


def refuse_selective_cell_combine(
    *,
    prior_attempt_id: str | None,
    selective_cells: Sequence[Any] | None,
) -> None:
    if prior_attempt_id and selective_cells:
        raise SelectiveCellCombineForbidden(
            "scientific combination of selectively rerun cells with a prior attempt is forbidden"
        )


def draw_fixture_world(
    *,
    scenario: str,
    n_rows: int,
    world_index: int = 0,
) -> dict[str, Any]:
    assert_not_production_grid(n_rows=n_rows)
    return simulate_dgp(scenario_id=scenario, n_rows=n_rows, world_index=world_index)


def implementation_identity() -> dict[str, Any]:
    return {
        "unit_id": "HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY",
        "stage": "fixture_implementation",
        "implementation_exists": True,
        "fixture_only": True,
        "synthetic_execution_authorized": False,
        "v2_production_arm_authorized": False,
        "production_calibration_executed": False,
        "result_mint_authorized": False,
        "authority_consumed": False,
        "contract_original_head": CONTRACT_ORIGINAL_HEAD,
        "contract_amendment_head": CONTRACT_AMENDMENT_HEAD,
        "coverage_table_entries": coverage_table_entry_count(),
        "required_coverage_map_count": required_coverage_map_count(),
        "blind_not_claimed_invariant_to_L": True,
        "selective_cell_reexecution_and_combine_forbidden": True,
        "next_required_step": "INDEPENDENT_IMPLEMENTATION_REVIEW",
    }


if __name__ == "__main__":
    raise ProductionGridForbidden(
        "V2 fixture module has no production entrypoint; next step is independent implementation review"
    )
