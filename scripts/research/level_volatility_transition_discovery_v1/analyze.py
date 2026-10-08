"""The one official transition read. Do not import this module from preflight."""

from __future__ import annotations

import math

import numpy as np

from . import constants as K
from .claim import decide, excludes_zero, statistical_pass, support_gate
from .cohort import assemble
from .inference import bootstrap_mean
from .rv import event_transition


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


def _by(rows: list[dict], key: str, names) -> list[dict]:
    return [_slice(str(name), [row for row in rows if row[key] == name]) for name in names]


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
        if int(pair["year"]) not in K.YEARS:
            raise RuntimeError("a matched touch is outside 2020-2024")
        if int(pair["real"]["open_ms"]) >= K.EVENT_END_MS or int(pair["pseudo"]["open_ms"]) >= K.EVENT_END_MS:
            raise RuntimeError("a matched touch is at or after 2025-01-01")
        if not pair["path_complete"]:
            continue
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
            "year": int(pair["year"]),
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
    fitted = bootstrap_mean(weeks, deltas)
    year_counts = {str(year): sum(row["year"] == year for row in rows) for year in K.YEARS}
    usable_gate = support_gate(len(rows), int(len(set(weeks.tolist()))), year_counts)
    stat = statistical_pass(fitted["delta"], fitted["ci95"]) and not fitted["ci_withheld"]
    loyo = []
    loyo_ran = False
    if stat and usable_gate["pass"]:
        loyo_ran = True
        for year in K.YEARS:
            kept = [row for row in rows if row["year"] != year]
            item = _slice(f"omit_{year}", kept)
            item["omitted_year"] = int(year)
            loyo.append(item)
    epochs = _by(rows, "year", K.YEARS)
    families = _by(rows, "family", K.FAMILIES)
    sides = _by(rows, "side_name", ("resistance", "support"))
    decision = decide(
        blocked_key_level=bool(frozen.get("blocked_reopening_key_level_range")),
        blocked_vol_cell=bool(frozen.get("blocked_reopening_volatility_transition_cell")),
        pre_gate=bool(frozen.get("pre_outcome_gate_pass")),
        usable_gate=bool(usable_gate["pass"]),
        delta=fitted["delta"],
        ci=fitted["ci95"],
        ci_withheld=bool(fitted["ci_withheld"]),
        epochs=epochs,
        families=families,
        sides=sides,
        loyo=loyo,
        loyo_ran=loyo_ran,
        artifact=False,
    )
    real_pre = np.array([row["real_rv_pre"] for row in rows], dtype=float)
    pseudo_pre = np.array([row["pseudo_rv_pre"] for row in rows], dtype=float)
    if rows:
        paired_log_pre = float(np.mean(np.log(real_pre / pseudo_pre)))
    else:
        paired_log_pre = None
    real_summary = _arm_summary(rows, "real")
    pseudo_summary = _arm_summary(rows, "pseudo")
    expansion_diff = None
    if real_summary["expansion_fraction"] is not None and pseudo_summary["expansion_fraction"] is not None:
        expansion_diff = real_summary["expansion_fraction"] - pseudo_summary["expansion_fraction"]
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "claim_ceiling": K.CLAIM_CEILING,
        "exposure_status": K.EXPOSURE_STATUS,
        "outcomes_read": True,
        "routing": decision["routing"],
        "candidate_class": decision["candidate_class"],
        "product_integration_candidate": False,
        "successor_candidate": "NONE",
        "confirmation_started": False,
        "level_engine_discovery_8_of_8_complete": True,
        "adjusted_sensitivity": False,
        "novelty_ok": True,
        "real_legitimate": assembled["real_legitimate"],
        "pseudo_legitimate": assembled["pseudo_legitimate"],
        "matched_pairs": assembled["matched_pairs"],
        "path_complete_pairs": assembled["path_complete_pairs"],
        "usable_pairs": len(rows),
        "weeks": usable_gate["n_weeks"],
        "zero_rv": dropped,
        "usable_gate": usable_gate,
        "pre_outcome_gate": frozen.get("pre_outcome_gate"),
        "primary": {
            "delta_log": fitted["delta"],
            "multiplicative_pct": _pct(fitted["delta"]),
            "ci95": fitted["ci95"],
            "ci95_multiplicative_pct": None if fitted["ci95"] is None else [_pct(fitted["ci95"][0]), _pct(fitted["ci95"][1])],
            "se": fitted["se"],
            "p": fitted["p"],
            "bootstrap_valid": fitted["bootstrap_valid"],
            "bootstrap_draws": K.BOOT_DRAWS,
            "bootstrap_seed": K.BOOT_SEED,
            "ci_withheld": fitted["ci_withheld"],
            "practical_log": K.PRACTICAL_LOG,
            "practical_pass": fitted["delta"] is not None and abs(float(fitted["delta"])) >= K.PRACTICAL_LOG,
            "ci_excludes_zero": (not fitted["ci_withheld"]) and excludes_zero(fitted["ci95"]),
        },
        "real": real_summary,
        "pseudo": pseudo_summary,
        "expansion_fraction_difference": expansion_diff,
        "pre_rv_balance": {
            "real_mean": real_summary["rv_pre_mean"],
            "real_median": real_summary["rv_pre_median"],
            "pseudo_mean": pseudo_summary["rv_pre_mean"],
            "pseudo_median": pseudo_summary["rv_pre_median"],
            "paired_log_diff_mean": paired_log_pre,
            "paired_log_diff_multiplicative_pct": _pct(paired_log_pre),
            "imbalance_at_practical_scale": paired_log_pre is not None and abs(paired_log_pre) >= K.PRACTICAL_LOG,
        },
        "years": epochs,
        "families": families,
        "sides": sides,
        "loyo_ran": loyo_ran,
        "loyo": loyo,
        "stability": {
            "years": decision["years"],
            "family": decision["family"],
            "side": decision["side"],
            "loyo": decision["loyo"],
            "failed": decision["failed"],
        },
        "formulas": {
            "return": "r_k = log(close_k / close_{k-1})",
            "rv_pre60": "sqrt(mean(r_k^2)) for k = j-12..j-1",
            "rv_post60": "sqrt(mean(r_k^2)) for k = j+1..j+12",
            "touch_bar_excluded": True,
            "vol_transition_60": "log(RV_POST60 / RV_PRE60)",
            "pair_delta": "VOL_TRANSITION_REAL - VOL_TRANSITION_PSEUDO",
            "delta_transition": "mean(PAIR_DELTA)",
            "multiplicative": "100 * (exp(DELTA_TRANSITION) - 1) percent",
        },
        "note": (
            "One discovery run. No compression subgroup, no other horizon, no 4h range, "
            "no adjusted sensitivity, no product change, no confirmation, no successor."
        ),
    }
