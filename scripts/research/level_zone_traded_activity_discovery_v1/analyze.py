"""One official outcome join. Scales and retained features come from the preflight.

This is the only module in the package that reads a late label.
"""

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


def _point(rows: list[dict], feature: str, scales: dict) -> dict:
    fit = fit_rows(rows, feature, scales, draws=0, seed=K.BOOT_SEED)
    return {"n": fit["n"], "coef": fit["coef"]}


def load_frozen() -> dict:
    return json.loads(preflight_mod.OUT.read_text())


def run(bars, frozen: dict) -> dict:
    records, _inventory = preflight_mod.load_aggregates()
    from scripts.research.level_cross_venue_reaction_discovery_v1.cohort import assemble
    from scripts.research.level_cross_venue_reaction_discovery_v1.series import load_reaction_series

    venues = load_reaction_series()
    built = assemble(bars, venues)
    retained = list(frozen["retained"])
    scales = scales_from_hex(frozen)
    real = [preflight_mod.attach(row, records, "real") for row in built["real_rows"]]
    pairs = []
    for pair in built["pairs"]:
        pairs.append({
            "real": preflight_mod.attach(pair["real"], records, "real"),
            "pseudo": preflight_mod.attach(pair["pseudo"], records, "pseudo"),
            "episode_id": pair["episode_id"],
        })
    real = [_attach_late(row, bars) for row in real]
    for pair in pairs:
        pair["real"] = _attach_late(pair["real"], bars)
        pair["pseudo"] = _attach_late(pair["pseudo"], bars)
    support_rows = [
        row for row in real
        if row.get("early_status") == "UNRESOLVED" and row.get("baseline_ok")
        and all(row.get(name) is not None for name in retained)
    ]
    recomputed = freeze_scales(support_rows, tuple(retained))
    for name, expected in frozen["scale_hex"].items():
        got = scale_hex(recomputed[name])
        if got != expected:
            raise RuntimeError(f"scale drift for {name}")
    late_counts = Counter(row.get("late") for row in support_rows)
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
        cell = fit_rows(
            common_resolved, name, scales, draws=K.BOOT_DRAWS, seed=K.stream_seed(index[name], 1),
        )
        epochs = [{"name": year, **_point([row for row in common_resolved if row["epoch"] == year], name, scales)}
                  for year in K.EPOCHS]
        loyo = [{"name": f"omit_{year}", **_point([row for row in common_resolved if row["epoch"] != year], name, scales)}
                for year in K.EPOCHS]
        families = [{"name": family, **_point([row for row in common_resolved if row["family"] == family], name, scales)}
                    for family in K.FAMILIES]
        sides = []
        for label, sign in (("resistance", 1), ("support", -1)):
            sides.append({
                "name": label,
                **_point([row for row in common_resolved if row["side"] == sign], name, scales),
            })
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
            "p": cell.get("p"),
            "n": cell.get("n"),
            "includes_end_position": True,
            "includes_cv1": True,
            "includes_offset": True,
        })
        feature_rows.append({
            "cell": cell, "epochs": epochs, "loyo": loyo, "families": families, "sides": sides,
            "shape": _shape(common_resolved, name, cuts_from_hex(frozen, name)),
            "matched": {
                "n_pairs": 0, "status": "NOT_APPLIED", "beta_real": None, "beta_pseudo": None,
                "delta": None, "delta_ci95": None, "columns": [],
            },
            "decision": decision,
        })
    qs = bh_adjust([item["cell"].get("p") for item in feature_rows])
    for item, q, summary in zip(feature_rows, qs, summaries):
        item["cell"]["q"] = q
        summary["q"] = q
        decision = conjunction(
            item["cell"], item["epochs"], item["loyo"], item["families"], item["sides"],
            identity_artifact=bool(frozen.get("identity_artifact")),
        )
        item["decision"] = decision
        summary["conjunction_pass"] = decision["pass"]
        summary["failed"] = decision["failed"]
        summary["statistical"] = decision["statistical"]
    pseudo_ok = bool(frozen.get("pseudo_identity_ok"))
    for item, summary in zip(feature_rows, summaries):
        if not summary["conjunction_pass"]:
            continue
        name = summary["feature"]
        if not pseudo_ok:
            item["matched"] = {
                "n_pairs": 0, "status": "NOT_ESTIMATED", "beta_real": None, "beta_pseudo": None,
                "delta": None, "delta_ci95": None, "columns": [],
                "reason": "pseudo touch identity below 0.95",
            }
            summary["specificity_status"] = "NOT_ESTIMATED"
            summary["candidate_class"] = "GENERIC_TRADED_ACTIVITY_CANDIDATE"
            continue
        eligible = {row["episode_id"] for row in common_resolved}
        matched_pairs = []
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
                matched_pairs, name, scales, draws=K.BOOT_DRAWS, seed=K.stream_seed(index[name], 100),
            )
        else:
            matched = {
                "n_pairs": len(matched_pairs), "status": "NOT_ESTIMATED",
                "beta_real": None, "beta_pseudo": None, "delta": None, "delta_ci95": None, "columns": [],
            }
        item["matched"] = matched
        if support_sensitive(item["cell"].get("coef"), matched.get("beta_real")):
            summary["specificity_status"] = "SUPPORT_SENSITIVE"
            summary["candidate_class"] = "GENERIC_TRADED_ACTIVITY_CANDIDATE"
        elif specificity_pass(matched, item["cell"].get("coef")):
            summary["specificity_status"] = "LEVEL_SPECIFIC"
            summary["candidate_class"] = "LEVEL_ZONE_TRADED_ACTIVITY_INTERACTION_CANDIDATE"
        else:
            summary["specificity_status"] = "GENERIC" if matched.get("status") == "ESTIMATED" else "NOT_ESTIMATED"
            summary["candidate_class"] = "GENERIC_TRADED_ACTIVITY_CANDIDATE"
    classes = [item["candidate_class"] for item in summaries]
    top = "NONE"
    for label in (
        "LEVEL_ZONE_TRADED_ACTIVITY_INTERACTION_CANDIDATE",
        "GENERIC_TRADED_ACTIVITY_CANDIDATE",
    ):
        if label in classes:
            top = label
            break
    routing = route(
        summaries,
        n_resolved=len(common_resolved),
        novelty_ok=bool(frozen.get("novelty_ok", True)),
        touch_identity_ok=bool(frozen.get("touch_identity_pass")),
        pre_outcome_ok=bool(frozen.get("pre_outcome_gate_pass")),
    )
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "family": K.FAMILY,
        "tracks": list(K.TRACKS),
        "claim_ceiling": K.CLAIM_CEILING,
        "exposure_status": K.EXPOSURE_STATUS,
        "product_integration_candidate": False,
        "successor_candidate": "NONE",
        "outcomes_read": True,
        "novelty_ok": bool(frozen.get("novelty_ok", True)),
        "touch_identity_pass": bool(frozen.get("touch_identity_pass")),
        "pre_outcome_gate_pass": bool(frozen.get("pre_outcome_gate_pass")),
        "pseudo_identity_ok": pseudo_ok,
        "raw_touch_match_rate": frozen.get("raw_touch_match_rate"),
        "dependencies": {
            "touch": K.DEP_TOUCH,
            "reaction": K.DEP_REACTION,
            "cross_venue": K.DEP_CROSS,
            "sequence": K.DEP_SEQUENCE,
            "source_main": K.SOURCE_MAIN_HEAD,
        },
        "retained": retained,
        "late_counts_unresolved_complete": dict(late_counts),
        "n_unresolved_complete": len(support_rows),
        "n_resolved": len(common_resolved),
        "baseline": baseline,
        "features": [
            {
                "summary": summary,
                "cell": item["cell"],
                "epochs": item["epochs"],
                "loyo": item["loyo"],
                "families": item["families"],
                "sides": item["sides"],
                "shape": item["shape"],
                "matched": item["matched"],
                "decision": item["decision"],
            }
            for summary, item in zip(summaries, feature_rows)
        ],
        "overall_candidate_class": top,
        "routing": routing,
    }
