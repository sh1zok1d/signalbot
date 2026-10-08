"""One official outcome join. Scales and retained features come from the preflight."""

from __future__ import annotations

import json

from scripts.research.level_post_touch_reaction_discovery_v1.late import late_label

from . import constants as K
from .claim import conjunction, route, specificity_pass
from .inference import bh_adjust, fit_rows, freeze_scales, scale_hex
from . import preflight as preflight_mod


def _attach_late(row: dict, bars) -> dict:
    out = dict(row)
    label = late_label(
        bars.high, bars.low, int(row["j"]), int(row["side"]),
        float(row["zone_low"]), float(row["zone_high"]), float(row["x_primary"]),
    )
    out["late"] = label
    return out


def _resolved(rows: list[dict]) -> list[dict]:
    kept = []
    for row in rows:
        if row.get("early_status") != "UNRESOLVED" or not row.get("nuisance_ok"):
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


def _late_census(rows: list[dict]) -> dict:
    unresolved = [row for row in rows if row.get("early_status") == "UNRESOLVED" and row.get("nuisance_ok")]
    counts = {"BREAK": 0, "REJECT": 0, "NEITHER": 0, "AMBIGUOUS": 0, "NONE": 0}
    for row in unresolved:
        label = row.get("late")
        counts[label if label in counts else "NONE"] += 1
    resolved = counts["BREAK"] + counts["REJECT"]
    return {**counts, "n_unresolved": len(unresolved), "n_resolved": resolved}


def _pp(cell: dict) -> dict:
    return {
        "feature": cell.get("feature"),
        "n": cell.get("n"),
        "clusters": cell.get("clusters"),
        "coef": cell.get("coef"),
        "ci95": cell.get("ci95"),
        "se": cell.get("se"),
        "p": cell.get("p"),
        "q": cell.get("q"),
        "endpos_coef": cell.get("endpos_coef"),
        "endpos_ci95": cell.get("endpos_ci95"),
        "brier": cell.get("brier"),
        "bootstrap_valid": cell.get("bootstrap_valid"),
        "includes_end_position": cell.get("includes_end_position"),
        "columns": cell.get("columns"),
    }


def _fit_named(rows, feature, scales, seed, **kwargs):
    cell = fit_rows(rows, feature, scales, draws=K.BOOT_DRAWS, seed=seed, **kwargs)
    return cell


def _shape(rows: list[dict], feature: str, cuts: dict) -> list[dict]:
    q33, q67 = cuts.get("q33"), cuts.get("q67")
    bins = {"T1": [], "T2": [], "T3": []}
    if q33 is None or q67 is None:
        return []
    for row in rows:
        value = row.get(feature)
        if value is None:
            continue
        if float(value) <= float(q33):
            bins["T1"].append(row["y"])
        elif float(value) <= float(q67):
            bins["T2"].append(row["y"])
        else:
            bins["T3"].append(row["y"])
    out = []
    for name, values in bins.items():
        out.append({
            "bin": name,
            "n": len(values),
            "late_break_rate": None if not values else float(sum(values) / len(values)),
        })
    return out


def run(bars, built: dict, frozen: dict) -> dict:
    retained = list(frozen["redundancy"]["retained"])
    scales = scales_from_hex(frozen)
    recomputed = freeze_scales([
        row for row in built["real_rows"]
        if row.get("early_status") == "UNRESOLVED" and row.get("nuisance_ok")
    ])
    for name, expected in frozen["scale_hex"].items():
        got = scale_hex(recomputed[name])
        if got != expected:
            raise RuntimeError(f"scale drift for {name}")
    real = [_attach_late(row, bars) for row in built["real_rows"]]
    pairs = []
    for pair in built["pairs"]:
        pairs.append({
            "real": _attach_late(pair["real"], bars),
            "pseudo": _attach_late(pair["pseudo"], bars),
            "episode_id": pair["episode_id"],
        })
    resolved = _resolved(real)
    pseudo_resolved = []
    for pair in pairs:
        real_row, pseudo_row = pair["real"], pair["pseudo"]
        if real_row.get("late") not in ("BREAK", "REJECT"):
            continue
        if pseudo_row.get("early_status") != "UNRESOLVED" or not pseudo_row.get("nuisance_ok"):
            continue
        if pseudo_row.get("late") not in ("BREAK", "REJECT"):
            continue
        left = dict(real_row)
        right = dict(pseudo_row)
        left["y"] = 1.0 if real_row["late"] == "BREAK" else 0.0
        right["y"] = 1.0 if pseudo_row["late"] == "BREAK" else 0.0
        left["real"] = 1.0
        right["real"] = 0.0
        right["cluster"] = left["cluster"]
        pseudo_resolved.append(right)
        pair["stacked_real"] = left
        pair["stacked_pseudo"] = right
    baseline = _fit_named(resolved, None, scales, K.stream_seed(0, 0))
    feature_rows = []
    index = {name: i for i, name in enumerate(K.FEATURES)}
    for name in retained:
        cell = _fit_named(resolved, name, scales, K.stream_seed(index[name], 1))
        base_brier = baseline.get("brier")
        cand_brier = cell.get("brier")
        cell["brier_delta"] = None if base_brier is None or cand_brier is None else base_brier - cand_brier
        epochs = []
        for year_i, year in enumerate(K.EPOCHS):
            subset = [row for row in resolved if row["epoch"] == year]
            fit = _fit_named(subset, name, scales, K.stream_seed(index[name], 10 + year_i))
            epochs.append({"name": year, "n": fit["n"], "coef": fit["coef"], "ci95": fit["ci95"]})
        loyo = []
        for year_i, year in enumerate(K.EPOCHS):
            subset = [row for row in resolved if row["epoch"] != year]
            fit = _fit_named(subset, name, scales, K.stream_seed(index[name], 20 + year_i))
            loyo.append({"name": f"omit_{year}", "n": fit["n"], "coef": fit["coef"], "ci95": fit["ci95"]})
        families = []
        for fam_i, family in enumerate(K.FAMILIES):
            subset = [row for row in resolved if row["family"] == family]
            fit = _fit_named(subset, name, scales, K.stream_seed(index[name], 30 + fam_i))
            families.append({"name": family, "n": fit["n"], "coef": fit["coef"], "ci95": fit["ci95"]})
        sides = []
        for side_i, (label, sign) in enumerate((("resistance", 1), ("support", -1))):
            subset = [row for row in resolved if row["side"] == sign]
            fit = _fit_named(subset, name, scales, K.stream_seed(index[name], 40 + side_i))
            sides.append({"name": label, "n": fit["n"], "coef": fit["coef"], "ci95": fit["ci95"]})
        pseudo_cell = {"n": len(pseudo_resolved), "coef": None, "ci95": None, "status": "NOT_ESTIMATED"}
        stacked = {"n": 0, "delta": None, "delta_ci95": None, "beta_real": None, "beta_pseudo": None,
                   "status": "NOT_ESTIMATED"}
        if len(pseudo_resolved) >= K.SPECIFICITY_MIN_N:
            pseudo_fit = _fit_named(pseudo_resolved, name, scales, K.stream_seed(index[name], 50))
            pseudo_cell = {
                "n": pseudo_fit["n"], "coef": pseudo_fit["coef"], "ci95": pseudo_fit["ci95"],
                "bootstrap_valid": pseudo_fit["bootstrap_valid"], "status": "ESTIMATED",
            }
            stacked_rows = []
            for pair in pairs:
                if "stacked_real" in pair:
                    stacked_rows.append(pair["stacked_real"])
                    stacked_rows.append(pair["stacked_pseudo"])
            stacked_fit = _fit_named(
                stacked_rows, name, scales, K.stream_seed(index[name], 60), stacked=True,
            )
            stacked = {
                "n": stacked_fit["n"],
                "delta": stacked_fit["delta"],
                "delta_ci95": stacked_fit["delta_ci95"],
                "beta_real": stacked_fit["beta_real"],
                "beta_pseudo": stacked_fit["beta_pseudo"],
                "bootstrap_valid": stacked_fit["bootstrap_valid"],
                "status": "ESTIMATED",
            }
        feature_rows.append({
            "cell": cell,
            "epochs": epochs,
            "loyo": loyo,
            "families": families,
            "sides": sides,
            "pseudo": pseudo_cell,
            "stacked": stacked,
            "shape": _shape(resolved, name, cuts_from_hex(frozen, name)),
        })
    pvalues = [item["cell"].get("p") for item in feature_rows]
    qvalues = bh_adjust(pvalues)
    summaries = []
    for item, q in zip(feature_rows, qvalues):
        cell = item["cell"]
        cell["q"] = q
        decision = conjunction(
            cell, item["epochs"], item["loyo"], item["families"], item["sides"],
            venue_artifact=bool(frozen.get("venue_artifact")),
        )
        specific = specificity_pass(item["stacked"]) if decision["pass"] else False
        if not decision["pass"]:
            klass = "NONE"
        elif specific:
            klass = "LEVEL_CROSS_VENUE_INTERACTION_CANDIDATE"
        else:
            klass = "GENERIC_CROSS_VENUE_REACTION_CANDIDATE"
        summaries.append({
            "feature": cell["feature"],
            "coef": cell.get("coef"),
            "ci95": cell.get("ci95"),
            "p": cell.get("p"),
            "q": q,
            "n": cell.get("n"),
            "statistical": decision["statistical"],
            "conjunction_pass": decision["pass"],
            "failed": decision["failed"],
            "candidate_class": klass,
            "includes_end_position": True,
        })
    routing = route(
        summaries,
        n_resolved=len(resolved),
        history_ok=bool(frozen.get("history_ok")),
        novelty_ok=bool(frozen.get("novelty_ok")),
    )
    return {
        "late": _late_census(real),
        "primary_n": len(resolved),
        "pseudo_primary_n": len(pseudo_resolved),
        "baseline": _pp(baseline),
        "features": [
            {
                "summary": summaries[i],
                "cell": _pp(item["cell"]),
                "brier_delta": item["cell"].get("brier_delta"),
                "epochs": item["epochs"],
                "loyo": item["loyo"],
                "families": item["families"],
                "sides": item["sides"],
                "shape": item["shape"],
                "pseudo": item["pseudo"],
                "stacked": item["stacked"],
                "conjunction": {
                    "pass": summaries[i]["conjunction_pass"],
                    "failed": summaries[i]["failed"],
                },
            }
            for i, item in enumerate(feature_rows)
        ],
        "routing": routing,
        "candidate_class": next(
            (item["candidate_class"] for item in summaries if item["candidate_class"] != "NONE"),
            "NONE",
        ),
        "outcomes_read": True,
    }


def load_frozen() -> dict:
    return json.loads(preflight_mod.OUT.read_text())
