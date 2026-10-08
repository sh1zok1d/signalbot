"""Join late labels only after the outcome-blind freeze has been checked by the caller."""

from __future__ import annotations

from collections import Counter

from scripts.research.level_post_touch_reaction_discovery_v1.late import late_label

from . import constants as K
from .claim import conjunction, route, specificity_label, statistical_hit
from .inference import bh_adjust, fit_rows


def y_of(label) -> float | None:
    if label == "BREAK":
        return 1.0
    if label == "REJECT":
        return 0.0
    return None


def attach_late(bars, rows: list[dict]) -> list[dict]:
    """Late labels only for events still unresolved at D. Early events stay unlabeled."""
    out = []
    for row in rows:
        label = None
        if row.get("early_status") == "UNRESOLVED":
            label = late_label(
                bars.high, bars.low, int(row["j"]), int(row["side"]),
                float(row["zone_low"]), float(row["zone_high"]), float(row["x_primary"]),
            )
        out.append({**row, "outcome": label})
    return out


def label_assembled(bars, assembled: dict) -> tuple[list[dict], list[dict]]:
    real = attach_late(bars, assembled["real_rows"])
    by_id = {row["episode_id"]: row for row in real}
    pairs = []
    for pair in assembled["pairs"]:
        pseudo = attach_late(bars, [pair["pseudo"]])[0]
        pairs.append({**pair, "real": by_id[pair["episode_id"]], "pseudo": pseudo})
    return real, pairs


def _ready(row: dict, contrast: str) -> dict | None:
    if row.get("early_status") != "UNRESOLVED" or row.get("contrast") != contrast:
        return None
    if not row.get("nuisance_ok"):
        return None
    y = y_of(row.get("outcome"))
    if y is None:
        return None
    return {**row, "y": y, "state": int(row["state_indicator"])}


def _fit(rows, scales, *, stacked, family, side, epoch, draws, seed, contrast, spec, slice_name, overlap_pass):
    cell = fit_rows(
        rows, scales, stacked=stacked, family=family, side=side, epoch=epoch, draws=draws, seed=seed,
    )
    cell["contrast"] = contrast
    cell["spec"] = spec
    cell["slice"] = slice_name
    cell["overlap_pass"] = bool(overlap_pass)
    cell["outcome"] = "LATE_BREAK_GIVEN_RESOLVED"
    return cell


def _share(count: int, n: int):
    if n == 0:
        return None
    return count / n


def sequence_table(rows: list[dict]) -> list[dict]:
    pool = [row for row in rows if row.get("early_status") == "UNRESOLVED"]
    out = []
    for name in K.SEQUENCES:
        bag = [row for row in pool if row.get("sequence") == name]
        counts = Counter(row.get("outcome") for row in bag)
        n = len(bag)
        out.append({
            "sequence": name,
            "n": n,
            "n_break": int(counts["BREAK"]),
            "n_reject": int(counts["REJECT"]),
            "n_neither": int(counts["NEITHER"]),
            "n_ambiguous": int(counts["AMBIGUOUS"]),
            "p_break": _share(int(counts["BREAK"]), n),
            "p_reject": _share(int(counts["REJECT"]), n),
            "p_neither": _share(int(counts["NEITHER"]), n),
        })
    return out


def state_table(rows: list[dict]) -> list[dict]:
    pool = [row for row in rows if row.get("early_status") == "UNRESOLVED"]
    out = []
    for name in K.STATES:
        bag = [row for row in pool if row.get("state") == name]
        counts = Counter(row.get("outcome") for row in bag)
        n = len(bag)
        labeled = int(counts["BREAK"]) + int(counts["REJECT"]) + int(counts["NEITHER"])
        resolved = int(counts["BREAK"]) + int(counts["REJECT"])
        out.append({
            "state": name,
            "n": n,
            "n_break": int(counts["BREAK"]),
            "n_reject": int(counts["REJECT"]),
            "n_neither": int(counts["NEITHER"]),
            "n_ambiguous": int(counts["AMBIGUOUS"]),
            "p_break": _share(int(counts["BREAK"]), n),
            "p_reject": _share(int(counts["REJECT"]), n),
            "p_neither": _share(int(counts["NEITHER"]), n),
            "p_resolve_among_labeled": None if labeled == 0 else resolved / labeled,
        })
    return out


def estimate(real_rows: list[dict], pairs: list[dict], contrasts: dict, eligible: list[str], *,
             draws: int = K.BOOT_DRAWS) -> dict:
    primary = []
    pseudo = []
    specificity = []
    stability = []
    loyo = []
    for name in eligible:
        index = K.CONTRAST_INDEX[name]
        scales = contrasts[name]["scales"]
        overlap_pass = bool(contrasts[name]["audit"]["overlap_pass"])
        real = [row for row in (_ready(r, name) for r in real_rows) if row]
        cell = _fit(
            real, scales, stacked=False, family=True, side=True, epoch=True,
            draws=draws, seed=K.stream_seed(index, 0), contrast=name, spec="primary",
            slice_name="all", overlap_pass=overlap_pass,
        )
        primary.append(cell)
        matched = []
        pseudo_only = []
        for pair in pairs:
            left = _ready(pair["real"], name)
            right = _ready(pair["pseudo"], name)
            if left is None or right is None:
                continue
            matched.append({**left, "real": 1.0, "cluster": int(pair["real"]["week"])})
            matched.append({**right, "real": 0.0, "cluster": int(pair["real"]["week"])})
            pseudo_only.append({**right, "cluster": int(pair["pseudo"]["week"])})
        pseudo.append(_fit(
            pseudo_only, scales, stacked=False, family=True, side=True, epoch=True,
            draws=draws, seed=K.stream_seed(index, 1), contrast=name, spec="pseudo",
            slice_name="pseudo", overlap_pass=overlap_pass,
        ))
        specificity.append(_fit(
            matched, scales, stacked=True, family=True, side=True, epoch=True,
            draws=draws, seed=K.stream_seed(index, 2), contrast=name, spec="specificity",
            slice_name="matched", overlap_pass=overlap_pass,
        ))
        for epoch_name in K.EPOCHS:
            stability.append(_fit(
                [row for row in real if row["epoch"] == epoch_name], scales,
                stacked=False, family=True, side=True, epoch=False, draws=0, seed=0,
                contrast=name, spec="epoch", slice_name=epoch_name, overlap_pass=overlap_pass,
            ))
        for family in K.FAMILIES:
            stability.append(_fit(
                [row for row in real if row["family"] == family], scales,
                stacked=False, family=False, side=True, epoch=True, draws=0, seed=0,
                contrast=name, spec="family", slice_name=family, overlap_pass=overlap_pass,
            ))
        for side_name, side_value in (("resistance", 1), ("support", -1)):
            stability.append(_fit(
                [row for row in real if int(row["side"]) == side_value], scales,
                stacked=False, family=True, side=False, epoch=True, draws=0, seed=0,
                contrast=name, spec="side", slice_name=side_name, overlap_pass=overlap_pass,
            ))
        for epoch_name in K.EPOCHS:
            loyo.append(_fit(
                [row for row in real if row["epoch"] != epoch_name], scales,
                stacked=False, family=True, side=True, epoch=True, draws=0, seed=0,
                contrast=name, spec="loyo", slice_name=f"omit_{epoch_name}", overlap_pass=overlap_pass,
            ))
    qs = bh_adjust([cell["p"] for cell in primary])
    for cell, q in zip(primary, qs):
        cell["q"] = q
    decisions = []
    for cell, stacked in zip(primary, specificity):
        epochs = [
            item for item in stability
            if item["contrast"] == cell["contrast"] and item["spec"] == "epoch"
        ]
        held = [item for item in loyo if item["contrast"] == cell["contrast"]]
        families = [
            item for item in stability
            if item["contrast"] == cell["contrast"] and item["spec"] == "family"
        ]
        sides = [
            item for item in stability
            if item["contrast"] == cell["contrast"] and item["spec"] == "side"
        ]
        rule = conjunction(cell, epochs, held, families, sides)
        label = specificity_label(cell, stacked) if rule["pass"] else "NONE"
        decisions.append({
            "contrast": cell["contrast"],
            "conjunction_pass": rule["pass"],
            "path_memory_candidate": rule["pass"],
            "failed": rule["failed"],
            "statistical_hit": statistical_hit(cell),
            "label": label,
            "primary_coef": cell["coef"],
            "primary_ci95": cell["ci95"],
            "q": cell["q"],
            "n": cell["n"],
            "n_treated": cell["n_treated"],
            "n_reference": cell["n_reference"],
            "delta": stacked.get("delta"),
            "delta_ci95": stacked.get("ci95"),
            "beta_real": stacked.get("beta_real"),
            "beta_pseudo": stacked.get("beta_pseudo"),
            "pseudo_coef": next(item["coef"] for item in pseudo if item["contrast"] == cell["contrast"]),
            "pseudo_ci95": next(item["ci95"] for item in pseudo if item["contrast"] == cell["contrast"]),
        })
    routing = route(decisions, n_estimated=len(primary))
    named = [item for item in decisions if item["label"] in (
        "LEVEL_ACCEPTANCE_PATH_CANDIDATE", "GENERIC_PRICE_PATH_MEMORY_CANDIDATE")]
    return {
        "outcomes_read": True,
        "primary": primary,
        "pseudo": pseudo,
        "specificity": specificity,
        "stability": stability,
        "loyo": loyo,
        "sequence_table": sequence_table(real_rows),
        "state_table": state_table(real_rows),
        "decisions": decisions,
        "path_memory_candidate": [item for item in decisions if item["path_memory_candidate"]],
        "level_acceptance_path_candidate": [
            item for item in named if item["label"] == "LEVEL_ACCEPTANCE_PATH_CANDIDATE"
        ],
        "generic_price_path_memory_candidate": [
            item for item in named if item["label"] == "GENERIC_PRICE_PATH_MEMORY_CANDIDATE"
        ],
        "routing": routing,
        "successor_candidate": "NONE",
    }
