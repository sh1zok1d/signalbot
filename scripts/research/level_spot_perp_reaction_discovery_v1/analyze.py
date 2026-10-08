"""One official outcome join. Scales and retained features come from the preflight."""

from __future__ import annotations

import json
from collections import Counter

from scripts.research.level_post_touch_reaction_discovery_v1.late import late_label

from . import constants as K
from . import preflight as preflight_mod
from .claim import conjunction, route, specificity_pass, support_sensitive
from .inference import bh_adjust, fit_matched, fit_rows, freeze_scales, scale_hex


def _attach_late(row: dict, bars) -> dict:
    out = dict(row)
    out["late"] = late_label(
        bars.high, bars.low, int(row["j"]), int(row["side"]),
        float(row["zone_low"]), float(row["zone_high"]), float(row["x_primary"]),
    )
    return out


def _resolved(rows: list[dict], feature: str) -> list[dict]:
    kept = []
    for row in rows:
        if row.get("early_status") != "UNRESOLVED" or not row.get("baseline_ok"):
            continue
        value = row.get(feature)
        if value is None:
            continue
        if row.get("late") not in ("BREAK", "REJECT"):
            continue
        copied = dict(row)
        copied["y"] = 1.0 if row["late"] == "BREAK" else 0.0
        kept.append(copied)
    return kept


def scales_from_hex(frozen: dict) -> dict:
    scales = {}
    for name, payload in frozen["scale_hex"].items():
        if payload.get("mean") is None or payload.get("sd") is None:
            raise RuntimeError(f"missing frozen scale for {name}")
        scales[name] = {"mean": float.fromhex(payload["mean"]), "sd": float.fromhex(payload["sd"])}
    return scales


def cuts_from_hex(frozen: dict, name: str) -> dict:
    payload = (frozen.get("tertile_cuts_hex") or {}).get(name) or {}
    return {
        "q33": None if payload.get("q33") is None else float.fromhex(payload["q33"]),
        "q67": None if payload.get("q67") is None else float.fromhex(payload["q67"]),
    }


def _shape(rows: list[dict], name: str, cuts: dict) -> list[dict]:
    q33, q67 = cuts.get("q33"), cuts.get("q67")
    bins = {"T1": [], "T2": [], "T3": []}
    for row in rows:
        value = row.get(name)
        if value is None or q33 is None or q67 is None:
            continue
        if float(value) <= float(q33):
            key = "T1"
        elif float(value) <= float(q67):
            key = "T2"
        else:
            key = "T3"
        bins[key].append(row)
    out = []
    for key in ("T1", "T2", "T3"):
        group = bins[key]
        breaks = sum(1 for row in group if row["late"] == "BREAK")
        rate = None if not group else breaks / len(group)
        out.append({"bin": key, "n": len(group), "late_break_rate": rate})
    return out


def _pp(cell: dict) -> dict:
    keep = (
        "feature", "n", "clusters", "coef", "ci95", "se", "p", "q", "bootstrap_valid",
        "endpos_coef", "endpos_ci95", "cv1_coef", "cv1_ci95", "brier", "columns",
        "includes_end_position", "includes_cv1",
    )
    return {key: cell.get(key) for key in keep}


def load_frozen() -> dict:
    return json.loads(preflight_mod.OUT.read_text())


def run(bars, built: dict, frozen: dict) -> dict:
    retained = list(frozen["retained"])
    scales = scales_from_hex(frozen)
    real = [_attach_late(row, bars) for row in built["real_rows"]]
    pairs = []
    for pair in built["pairs"]:
        pairs.append({
            "real": _attach_late(pair["real"], bars),
            "pseudo": _attach_late(pair["pseudo"], bars),
            "episode_id": pair["episode_id"],
        })
    recomputed = freeze_scales(
        [row for row in real if row.get("early_status") == "UNRESOLVED" and row.get("baseline_ok")
         and all(row.get(name) is not None for name in retained)],
        tuple(retained),
    )
    for name, expected in frozen["scale_hex"].items():
        got = scale_hex(recomputed[name])
        if got != expected:
            raise RuntimeError(f"scale drift for {name}")
    support_rows = [
        row for row in real
        if row.get("early_status") == "UNRESOLVED" and row.get("baseline_ok")
        and all(row.get(name) is not None for name in retained)
    ]
    late_counts = Counter(row.get("late") for row in support_rows)
    baseline_rows = _resolved(support_rows, retained[0]) if retained else []
    # Baseline uses the common retained support. Each candidate uses the same rows.
    common_resolved = []
    for row in support_rows:
        if row.get("late") not in ("BREAK", "REJECT"):
            continue
        copied = dict(row)
        copied["y"] = 1.0 if row["late"] == "BREAK" else 0.0
        common_resolved.append(copied)
    baseline = fit_rows(common_resolved, None, scales, draws=K.BOOT_DRAWS, seed=K.stream_seed(0, 0))
    index = {name: i for i, name in enumerate(K.FEATURES)}
    feature_rows = []
    summaries = []
    for name in retained:
        cell = fit_rows(common_resolved, name, scales, draws=K.BOOT_DRAWS, seed=K.stream_seed(index[name], 1))
        base_brier = baseline.get("brier")
        cand_brier = cell.get("brier")
        cell["brier_delta"] = None if base_brier is None or cand_brier is None else base_brier - cand_brier
        epochs, loyo, families, sides = [], [], [], []
        for year_i, year in enumerate(K.EPOCHS):
            subset = [row for row in common_resolved if row["epoch"] == year]
            fit = fit_rows(subset, name, scales, draws=K.BOOT_DRAWS, seed=K.stream_seed(index[name], 10 + year_i))
            epochs.append({"name": year, "n": fit["n"], "coef": fit["coef"], "ci95": fit["ci95"]})
        for year_i, year in enumerate(K.EPOCHS):
            subset = [row for row in common_resolved if row["epoch"] != year]
            fit = fit_rows(subset, name, scales, draws=K.BOOT_DRAWS, seed=K.stream_seed(index[name], 20 + year_i))
            loyo.append({"name": f"omit_{year}", "n": fit["n"], "coef": fit["coef"], "ci95": fit["ci95"]})
        for fam_i, family in enumerate(K.FAMILIES):
            subset = [row for row in common_resolved if row["family"] == family]
            fit = fit_rows(subset, name, scales, draws=K.BOOT_DRAWS, seed=K.stream_seed(index[name], 30 + fam_i))
            families.append({"name": family, "n": fit["n"], "coef": fit["coef"], "ci95": fit["ci95"]})
        for side_i, (label, sign) in enumerate((("resistance", 1), ("support", -1))):
            subset = [row for row in common_resolved if row["side"] == sign]
            fit = fit_rows(subset, name, scales, draws=K.BOOT_DRAWS, seed=K.stream_seed(index[name], 40 + side_i))
            sides.append({"name": label, "n": fit["n"], "coef": fit["coef"], "ci95": fit["ci95"]})
        decision = conjunction(
            cell, epochs, loyo, families, sides, identity_artifact=bool(frozen.get("identity_artifact")),
        )
        summaries.append({
            "feature": name,
            "candidate_class": "NONE",
            "specificity_status": "NOT_APPLIED",
            "conjunction_pass": decision["pass"],
            "failed": decision["failed"],
            "statistical": decision["statistical"],
            "coef": cell.get("coef"),
            "ci95": cell.get("ci95"),
            "q": None,
            "n": cell.get("n"),
            "includes_end_position": True,
            "includes_cv1": True,
        })
        feature_rows.append({
            "cell": cell, "epochs": epochs, "loyo": loyo, "families": families, "sides": sides,
            "shape": _shape(common_resolved, name, cuts_from_hex(frozen, name)),
            "matched": {
                "n_pairs": 0, "status": "NOT_APPLIED", "beta_real": None, "beta_pseudo": None,
                "delta": None, "delta_ci95": None,
            },
            "decision": decision,
        })
    qs = bh_adjust([item["cell"].get("p") for item in feature_rows])
    for item, q, summary in zip(feature_rows, qs, summaries):
        item["cell"]["q"] = q
        summary["q"] = q
        # q is part of the statistical gate. Recompute the class now that q exists.
        decision = conjunction(
            item["cell"], item["epochs"], item["loyo"], item["families"], item["sides"],
            identity_artifact=bool(frozen.get("identity_artifact")),
        )
        summary["conjunction_pass"] = decision["pass"]
        summary["failed"] = decision["failed"]
        summary["statistical"] = decision["statistical"]
    for item, summary in zip(feature_rows, summaries):
        summary["specificity_status"] = "NOT_APPLIED"
        summary["candidate_class"] = "NONE"
        item["matched"] = {
            "n_pairs": 0, "status": "NOT_APPLIED", "beta_real": None, "beta_pseudo": None,
            "delta": None, "delta_ci95": None,
        }
        if not summary["conjunction_pass"]:
            continue
        name = summary["feature"]
        matched_pairs = []
        eligible = {row["episode_id"] for row in common_resolved}
        for pair in pairs:
            real_row, pseudo_row = pair["real"], pair["pseudo"]
            if real_row.get("episode_id") not in eligible:
                continue
            if pseudo_row.get("early_status") != "UNRESOLVED" or not pseudo_row.get("baseline_ok"):
                continue
            if pseudo_row.get("late") not in ("BREAK", "REJECT"):
                continue
            if real_row.get(name) is None or pseudo_row.get(name) is None:
                continue
            left = dict(real_row)
            right = dict(pseudo_row)
            left["y"] = 1.0 if real_row["late"] == "BREAK" else 0.0
            right["y"] = 1.0 if pseudo_row["late"] == "BREAK" else 0.0
            right["cluster"] = left["cluster"]
            matched_pairs.append({"real": left, "pseudo": right})
        if len(matched_pairs) >= K.SPECIFICITY_MIN_N:
            matched = fit_matched(
                matched_pairs, name, scales, draws=K.BOOT_DRAWS, seed=K.stream_seed(index[name], 60),
            )
        else:
            matched = {
                "n_pairs": len(matched_pairs), "status": "NOT_ESTIMATED",
                "beta_real": None, "beta_pseudo": None, "delta": None, "delta_ci95": None,
            }
        item["matched"] = matched
        if support_sensitive(item["cell"].get("coef"), matched.get("beta_real")):
            summary["specificity_status"] = "SUPPORT_SENSITIVE"
            summary["candidate_class"] = "GENERIC_SPOT_PERP_REACTION_CANDIDATE"
        elif specificity_pass(matched, item["cell"].get("coef")):
            summary["specificity_status"] = "LEVEL_SPECIFIC"
            summary["candidate_class"] = "LEVEL_SPOT_PERP_INTERACTION_CANDIDATE"
        else:
            summary["specificity_status"] = "GENERIC" if matched.get("status") == "ESTIMATED" else "NOT_ESTIMATED"
            summary["candidate_class"] = "GENERIC_SPOT_PERP_REACTION_CANDIDATE"
    classes = [item["candidate_class"] for item in summaries]
    top = "NONE"
    for label in (
        "LEVEL_SPOT_PERP_INTERACTION_CANDIDATE",
        "GENERIC_SPOT_PERP_REACTION_CANDIDATE",
    ):
        if label in classes:
            top = label
            break
    routing = route(
        summaries, n_resolved=len(common_resolved),
        history_ok=bool(frozen.get("history_ok")), novelty_ok=bool(frozen.get("novelty_ok", True)),
    )
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "family": K.FAMILY,
        "tracks": list(K.TRACKS),
        "claim_ceiling": K.CLAIM_CEILING,
        "product_integration_candidate": False,
        "exposure_status": K.EXPOSURE_STATUS,
        "source_main": K.SOURCE_MAIN_HEAD,
        "outcomes_read": True,
        "novelty_ok": True,
        "history_ok": bool(frozen.get("history_ok")),
        "dependencies": {
            "touch": K.DEPENDENCY_TOUCH_SHA,
            "memory": K.DEPENDENCY_MEMORY_SHA,
            "method": K.DEPENDENCY_METHOD_SHA,
            "approach": K.DEPENDENCY_APPROACH_SHA,
            "structure": K.DEPENDENCY_STRUCTURE_SHA,
            "confirm": K.DEPENDENCY_CONFIRM_SHA,
            "position": K.DEPENDENCY_POSITION_SHA,
            "joint": K.DEPENDENCY_JOINT_SHA,
            "liquidity": K.DEPENDENCY_LIQUIDITY_SHA,
            "reaction": K.DEPENDENCY_REACTION_SHA,
            "path": K.DEPENDENCY_PATH_SHA,
            "cross_venue": K.DEPENDENCY_CROSS_VENUE_SHA,
        },
        "late": {
            "n_unresolved": len(support_rows),
            "n_resolved": len(common_resolved),
            "BREAK": int(late_counts["BREAK"]),
            "REJECT": int(late_counts["REJECT"]),
            "NEITHER": int(late_counts["NEITHER"]),
            "AMBIGUOUS": int(late_counts["AMBIGUOUS"]),
        },
        "primary_n": len(common_resolved),
        "baseline": _pp(baseline),
        "features": [
            {
                "summary": summary,
                "cell": _pp(item["cell"]),
                "brier_delta": item["cell"].get("brier_delta"),
                "epochs": item["epochs"],
                "loyo": item["loyo"],
                "families": item["families"],
                "sides": item["sides"],
                "shape": item["shape"],
                "matched": item["matched"],
            }
            for item, summary in zip(feature_rows, summaries)
        ],
        "candidate_class": top,
        "routing": routing,
        "note": (
            "Discovery only. CV1 is a baseline control, not a confirmation of the prior "
            "cross-venue unit. A historical association is not a current probability."
        ),
    }
