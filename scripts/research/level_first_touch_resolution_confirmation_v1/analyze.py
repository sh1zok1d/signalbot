"""Attach the frozen 4h barrier to matched first touches and estimate the predeclared contrast.

Imported by the evaluator and by tests. The preflight path does not import this module.
"""

from __future__ import annotations

import numpy as np

from scripts.research.level_touch_degradation_v1.outcomes import attach

from . import claim, constants as K, inference
from .endpoint import indicator, resolved


def _cell_rng(cell: int, seed: int) -> np.random.Generator:
    return np.random.default_rng(int(seed) + int(cell))


def label_matched(high, low, pairs: list[dict]) -> tuple[list[dict], list[dict]]:
    real = attach(high, low, [p["real_touch"] for p in pairs],
                  horizon=K.HOLD_BARS, barrier_fraction=K.BARRIER_FRACTION)
    pseudo = attach(high, low, [p["pseudo_touch"] for p in pairs],
                    horizon=K.HOLD_BARS, barrier_fraction=K.BARRIER_FRACTION)
    return real, pseudo


def _as_object(values) -> np.ndarray:
    return np.asarray(list(values), dtype=object)


def estimate(pairs: list[dict], real_labels: list[str], pseudo_labels: list[str], *,
             edges: tuple[float, float], columns: list[str], draws: int, seed: int) -> dict:
    """`pairs` are availability-matched. Ambiguous and unclassified pairs leave here."""
    if len(pairs) != len(real_labels) or len(pairs) != len(pseudo_labels):
        raise RuntimeError("label alignment failed")
    n_amb_real = sum(1 for lab in real_labels if lab == "AMBIGUOUS")
    n_amb_pseudo = sum(1 for lab in pseudo_labels if lab == "AMBIGUOUS")
    kept = []
    n_unclassified = 0
    n_ambiguous_pairs = 0
    for pair, lab_r, lab_p in zip(pairs, real_labels, pseudo_labels):
        yr = resolved(lab_r)
        yp = resolved(lab_p)
        if yr is None or yp is None:
            if lab_r == "AMBIGUOUS" or lab_p == "AMBIGUOUS":
                n_ambiguous_pairs += 1
            else:
                n_unclassified += 1
            continue
        kept.append((pair, lab_r, lab_p, yr, yp))
    y_real = np.asarray([row[3] for row in kept], dtype=float)
    y_pseudo = np.asarray([row[4] for row in kept], dtype=float)
    weeks = np.asarray([row[0]["week"] for row in kept], dtype=np.int64)
    epochs = _as_object([row[0]["epoch"] for row in kept])
    families = _as_object([row[0]["family"] for row in kept])
    real_side = np.asarray([row[0]["real_side"] for row in kept], dtype=int)
    pseudo_side = np.asarray([row[0]["pseudo_side"] for row in kept], dtype=int)
    real_sigma = np.asarray([row[0]["real_sigma"] for row in kept], dtype=float)
    pseudo_sigma = np.asarray([row[0]["pseudo_sigma"] for row in kept], dtype=float)
    real_epoch = _as_object([row[0]["epoch"] for row in kept])
    pseudo_epoch = _as_object([row[0]["pseudo_epoch"] for row in kept])
    labels_r = [row[1] for row in kept]
    labels_p = [row[2] for row in kept]

    primary = inference.contrast_block(y_real, y_pseudo, weeks, _cell_rng(0, seed), draws)
    decomposition = {}
    for offset, name in enumerate(("BREAK", "REJECT", "NEITHER"), start=1):
        ir = np.asarray([indicator(lab, name) for lab in labels_r], dtype=float)
        ip = np.asarray([indicator(lab, name) for lab in labels_p], dtype=float)
        decomposition[name] = inference.contrast_block(ir, ip, weeks, _cell_rng(offset, seed), draws)
    _assert_identities(primary, decomposition)

    epoch_rows = []
    for offset, name in enumerate(K.EPOCHS, start=4):
        mask = epochs == name
        epoch_rows.append(_named(name, y_real[mask], y_pseudo[mask], weeks[mask], _cell_rng(offset, seed), draws))
    family_rows = []
    for offset, name in enumerate(K.FAMILIES, start=7):
        mask = families == name
        family_rows.append(_named(name, y_real[mask], y_pseudo[mask], weeks[mask], _cell_rng(offset, seed), draws))
    side_rows = []
    for offset, (side, name) in enumerate(((1, "resistance"), (-1, "support")), start=10):
        mask = real_side == side
        side_rows.append(_named(name, y_real[mask], y_pseudo[mask], weeks[mask], _cell_rng(offset, seed), draws))
    loeo_rows = []
    for offset, name in enumerate(K.EPOCHS, start=12):
        mask = epochs != name
        loeo_rows.append(_named("omit_" + name, y_real[mask], y_pseudo[mask], weeks[mask],
                                _cell_rng(offset, seed), draws))

    adjusted = _adjusted(
        y_real, y_pseudo, families, real_side, pseudo_side, real_sigma, pseudo_sigma,
        real_epoch, pseudo_epoch, weeks, edges, columns, _cell_rng(15, seed), draws,
    )
    discordant = _discordant(y_real, y_pseudo)
    clauses = claim.supporting_clauses(primary, epoch_rows, loeo_rows)
    label = claim.evidence_label(primary, clauses)
    decision = claim.claim_decision(int(y_real.size), label)
    return {
        "n_matched_available": len(pairs),
        "n_analysis": int(y_real.size),
        "n_ambiguous_real": n_amb_real,
        "n_ambiguous_pseudo": n_amb_pseudo,
        "n_excluded_ambiguous": n_ambiguous_pairs,
        "n_excluded_unclassified": n_unclassified,
        "weeks": int(np.unique(weeks).size) if weeks.size else 0,
        "primary": primary,
        "discordant": discordant,
        "decomposition": decomposition,
        "adjusted": adjusted,
        "epochs": epoch_rows,
        "families": family_rows,
        "sides": side_rows,
        "leave_one_epoch_out": loeo_rows,
        "evidence_label": label,
        "supporting_clauses": clauses,
        **decision,
    }


def _named(name, y_real, y_pseudo, weeks, rng, draws) -> dict:
    body = inference.contrast_block(y_real, y_pseudo, weeks, rng, draws)
    body["name"] = name
    return body


def _assert_identities(primary: dict, decomposition: dict) -> None:
    d_res = primary["estimate"]
    d_break = decomposition["BREAK"]["estimate"]
    d_reject = decomposition["REJECT"]["estimate"]
    d_neither = decomposition["NEITHER"]["estimate"]
    if d_res is None:
        return
    if abs((d_break + d_reject) - d_res) > 1e-9:
        raise RuntimeError("decomposition identity failed")
    if abs(d_res + d_neither) > 1e-9:
        raise RuntimeError("endpoint identity failed")


def _discordant(y_real: np.ndarray, y_pseudo: np.ndarray) -> dict:
    if y_real.size == 0:
        return {"both_resolved": 0, "both_neither": 0, "real_only": 0, "pseudo_only": 0}
    yr = y_real == 1
    yp = y_pseudo == 1
    return {
        "both_resolved": int((yr & yp).sum()),
        "both_neither": int((~yr & ~yp).sum()),
        "real_only": int((yr & ~yp).sum()),
        "pseudo_only": int((~yr & yp).sum()),
    }


def _adjusted(y_real, y_pseudo, families, real_side, pseudo_side, real_sigma, pseudo_sigma,
              real_epoch, pseudo_epoch, weeks, edges, columns, rng, draws) -> dict:
    if y_real.size == 0:
        return {"estimate": None, "ci_low": None, "ci_high": None, "columns": list(columns),
                "valid_frac": None, "status": "empty"}
    z_real = inference.control_matrix(families, real_side, real_sigma, real_epoch, edges, columns)
    z_pseudo = inference.control_matrix(families, pseudo_side, pseudo_sigma, pseudo_epoch, edges, columns)
    index = np.arange(y_real.size)
    point = inference.adjusted_from_z(y_real, y_pseudo, z_real, z_pseudo, index)
    if point is None:
        return {"estimate": None, "ci_low": None, "ci_high": None, "columns": list(columns),
                "valid_frac": 0.0, "status": "rank_deficient_on_analysis_sample"}
    draws_a = inference.bootstrap_adjusted(y_real, y_pseudo, z_real, z_pseudo, weeks, rng, draws)
    ci = inference.percentile_ci(draws_a, expected=draws)
    valid = float(np.isfinite(draws_a).mean()) if draws else None
    return {
        "estimate": point,
        "ci_low": None if ci is None else ci[0],
        "ci_high": None if ci is None else ci[1],
        "columns": list(columns),
        "valid_frac": valid,
        "status": "ok" if ci is not None else "interval_not_valid",
    }
