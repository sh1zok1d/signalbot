"""The one official BitMEX transition read. Do not import this module from preflight."""

from __future__ import annotations

import math

import numpy as np

from scripts.research.level_volatility_transition_discovery_v1.inference import bootstrap_mean
from scripts.research.level_volatility_transition_discovery_v1.rv import event_transition

from . import constants as K
from .claim import decide
from .cohort import assemble


def _pct(delta):
    if delta is None or not math.isfinite(float(delta)):
        return None
    return 100.0 * (math.exp(float(delta)) - 1.0)


def _dist(values: np.ndarray) -> dict:
    if values.size == 0:
        return {"mean": None, "median": None, "p25": None, "p75": None}
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p25": float(np.quantile(values, 0.25)),
        "p75": float(np.quantile(values, 0.75)),
    }


def _arm_summary(rows: list[dict], prefix: str) -> dict:
    pre = np.array([row[f"{prefix}_rv_pre"] for row in rows], dtype=float)
    post = np.array([row[f"{prefix}_rv_post"] for row in rows], dtype=float)
    trans = np.array([row[f"{prefix}_transition"] for row in rows], dtype=float)
    summary = _dist(trans)
    summary.update({
        "n": len(rows),
        "rv_pre_mean": None if pre.size == 0 else float(np.mean(pre)),
        "rv_pre_median": None if pre.size == 0 else float(np.median(pre)),
        "rv_post_mean": None if post.size == 0 else float(np.mean(post)),
        "rv_post_median": None if post.size == 0 else float(np.median(post)),
        "expansion_fraction": None if trans.size == 0 else float(np.mean(trans > 0.0)),
    })
    return summary


def _slice(name: str, rows: list[dict]) -> dict:
    if not rows:
        return {"name": name, "n": 0, "delta": None, "multiplicative_pct": None}
    delta = float(np.mean([row["pair_delta"] for row in rows]))
    return {"name": name, "n": len(rows), "delta": delta, "multiplicative_pct": _pct(delta)}


def run(bars, frozen: dict) -> dict:
    assembled = assemble(bars)
    if int(assembled["path_complete_pairs"]) != int(frozen["path_complete_pairs"]):
        raise RuntimeError("path census drifted after the design freeze")
    if int(assembled["real_legitimate"]) != int(frozen["real_legitimate"]):
        raise RuntimeError("real first-touch census drifted after the design freeze")
    close = bars.close
    rows = []
    dropped = {
        "real_nonpositive_rv": 0,
        "pseudo_nonpositive_rv": 0,
        "pairs_dropped": 0,
        "path_complete_pairs": int(assembled["path_complete_pairs"]),
    }
    for pair in assembled["pairs"]:
        if not pair["path_complete"]:
            continue
        if "outcome" in pair or "label" in pair:
            raise RuntimeError("a resolution label entered the pair")
        real = event_transition(close, pair["real"]["j"])
        pseudo = event_transition(close, pair["pseudo"]["j"])
        if real is None:
            dropped["real_nonpositive_rv"] += 1
        if pseudo is None:
            dropped["pseudo_nonpositive_rv"] += 1
        if real is None or pseudo is None:
            dropped["pairs_dropped"] += 1
            continue
        rows.append({
            "epoch": pair["epoch"],
            "week": int(pair["week"]),
            "family": pair["family"],
            "side_name": pair["side_name"],
            "real_rv_pre": real["rv_pre"],
            "real_rv_post": real["rv_post"],
            "real_transition": real["transition"],
            "pseudo_rv_pre": pseudo["rv_pre"],
            "pseudo_rv_post": pseudo["rv_post"],
            "pseudo_transition": pseudo["transition"],
            "pair_delta": real["transition"] - pseudo["transition"],
        })
    weeks = np.array([row["week"] for row in rows], dtype=int)
    deltas = np.array([row["pair_delta"] for row in rows], dtype=float)
    fitted = bootstrap_mean(weeks, deltas, draws=K.BOOT_DRAWS, seed=K.BOOT_SEED)
    stat_ready = (
        fitted["delta"] is not None
        and fitted["delta"] > 0.0
        and not fitted["ci_withheld"]
        and fitted["ci95"] is not None
        and float(fitted["ci95"][0]) > 0.0
        and float(fitted["delta"]) >= K.PRACTICAL_LOG
    )
    loeo = []
    loeo_ran = False
    if stat_ready:
        loeo_ran = True
        for epoch in K.EPOCHS:
            kept = [row for row in rows if row["epoch"] != epoch]
            item = _slice(f"omit_{epoch}", kept)
            item["omitted_epoch"] = epoch
            loeo.append(item)
    epochs = [_slice(name, [row for row in rows if row["epoch"] == name]) for name in K.EPOCHS]
    families = [_slice(name, [row for row in rows if row["family"] == name]) for name in K.FAMILIES]
    sides = [_slice(name, [row for row in rows if row["side_name"] == name]) for name in ("resistance", "support")]
    decision = decide(
        pre_gate=bool(frozen.get("pre_outcome_gate_pass")),
        delta=fitted["delta"],
        ci=fitted["ci95"],
        ci_withheld=bool(fitted["ci_withheld"]),
        epochs=epochs,
        families=families,
        sides=sides,
        loeo=loeo,
        loeo_ran=loeo_ran,
        artifact=False,
    )
    real_pre = np.array([row["real_rv_pre"] for row in rows], dtype=float)
    pseudo_pre = np.array([row["pseudo_rv_pre"] for row in rows], dtype=float)
    paired_log_pre = float(np.mean(np.log(real_pre / pseudo_pre))) if rows else None
    real_summary = _arm_summary(rows, "real")
    pseudo_summary = _arm_summary(rows, "pseudo")
    expansion_diff = None
    if real_summary["expansion_fraction"] is not None and pseudo_summary["expansion_fraction"] is not None:
        expansion_diff = real_summary["expansion_fraction"] - pseudo_summary["expansion_fraction"]
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "surface_evidence_class": K.SURFACE_EVIDENCE_CLASS,
        "surface_pristine": False,
        "claim_ceiling": K.CLAIM_CEILING,
        "independence_from_resolution_clock": K.INDEPENDENCE_FROM_RESOLUTION_CLOCK,
        "outcomes_read": True,
        "resolution_labels_used": False,
        "routing": decision["routing"],
        "evidence_label": decision["evidence_label"],
        "product_integration_candidate": False,
        "prospective_started": False,
        "cross_venue_started": False,
        "real_legitimate": assembled["real_legitimate"],
        "pseudo_legitimate": assembled["pseudo_legitimate"],
        "matched_pairs": assembled["matched_pairs"],
        "path_complete_pairs": assembled["path_complete_pairs"],
        "usable_pairs": len(rows),
        "weeks": int(len(set(weeks.tolist()))) if rows else 0,
        "zero_rv": dropped,
        "primary": {
            "delta_log": fitted["delta"],
            "multiplicative_pct": _pct(fitted["delta"]),
            "ci95": fitted["ci95"],
            "ci95_multiplicative_pct": None if fitted["ci95"] is None else [
                _pct(fitted["ci95"][0]), _pct(fitted["ci95"][1]),
            ],
            "se": fitted["se"],
            "p": fitted["p"],
            "bootstrap_valid": fitted["bootstrap_valid"],
            "bootstrap_draws": K.BOOT_DRAWS,
            "bootstrap_seed": K.BOOT_SEED,
            "ci_withheld": fitted["ci_withheld"],
            "practical_log": K.PRACTICAL_LOG,
            "practical_pass": fitted["delta"] is not None and float(fitted["delta"]) >= K.PRACTICAL_LOG,
            "ci_excludes_zero": (not fitted["ci_withheld"]) and fitted["ci95"] is not None and (
                float(fitted["ci95"][0]) > 0.0 or float(fitted["ci95"][1]) < 0.0
            ),
            "ci_contains_practical_bar": decision["ci_contains_practical_bar"],
            "ci_contains_discovery_point": decision["ci_contains_discovery_point"],
        },
        "real": real_summary,
        "pseudo": pseudo_summary,
        "expansion_fraction_difference": expansion_diff,
        "pre_rv_balance": {
            "paired_log_diff_mean": paired_log_pre,
            "paired_log_diff_median": None if not rows else float(np.median(np.log(real_pre / pseudo_pre))),
            "paired_log_diff_multiplicative_pct": _pct(paired_log_pre),
            "real_mean": real_summary["rv_pre_mean"],
            "real_median": real_summary["rv_pre_median"],
            "pseudo_mean": pseudo_summary["rv_pre_mean"],
            "pseudo_median": pseudo_summary["rv_pre_median"],
        },
        "epochs": epochs,
        "families": families,
        "sides": sides,
        "loeo_ran": loeo_ran,
        "loeo": loeo,
        "decision": decision,
        "discovery_comparison_not_pooled": {
            "discovery_delta_log": K.DISCOVERY_POINT,
            "discovery_multiplicative_pct": _pct(K.DISCOVERY_POINT),
            "pooled": False,
        },
    }
