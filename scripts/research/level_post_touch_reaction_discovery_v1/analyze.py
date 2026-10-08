"""Join late labels only after the outcome-blind freeze has been checked by the caller."""

from __future__ import annotations

from collections import Counter

from . import constants as K
from .claim import conjunction, route, specificity_label, statistical_hit
from .cohort import early_census, feature_complete
from .inference import bh_adjust, fit_rows, shape_label, shape_table
from .late import late_label


def y_of(label, outcome_name: str):
    if outcome_name == "LATE_RESOLVE_BY_4H":
        if label in ("BREAK", "REJECT"):
            return 1.0
        if label == "NEITHER":
            return 0.0
        return None
    if outcome_name == "LATE_BREAK_GIVEN_RESOLVED":
        if label == "BREAK":
            return 1.0
        if label == "REJECT":
            return 0.0
        return None
    raise ValueError(outcome_name)


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


def _ready(row: dict, feature: str, outcome_name: str, *, require_end: bool) -> dict | None:
    if row.get("early_status") != "UNRESOLVED":
        return None
    names = [feature]
    if require_end and feature != K.PRICE_FEATURE:
        names.append(K.PRICE_FEATURE)
    if not feature_complete(row, names):
        return None
    y = y_of(row.get("outcome"), outcome_name)
    if y is None:
        return None
    return {**row, "y": y}


def label_assembled(bars, assembled: dict) -> tuple[list[dict], list[dict]]:
    real = attach_late(bars, assembled["real_rows"])
    by_id = {row["episode_id"]: row for row in real}
    pairs = []
    for pair in assembled["pairs"]:
        pseudo = attach_late(bars, [pair["pseudo"]])[0]
        pairs.append({**pair, "real": by_id[pair["episode_id"]], "pseudo": pseudo})
    return real, pairs


def late_decomposition(rows: list[dict]) -> dict:
    """Frequencies on unresolved events only. Early events are not in this denominator."""
    pool = [row for row in rows if row.get("early_status") == "UNRESOLVED"]
    counts = Counter(row.get("outcome") for row in pool)
    labeled = sum(counts[name] for name in ("BREAK", "REJECT", "NEITHER"))

    def rate(name: str):
        if labeled == 0:
            return None
        return counts[name] / labeled

    return {
        "n_unresolved": len(pool),
        "n_break": int(counts["BREAK"]),
        "n_reject": int(counts["REJECT"]),
        "n_neither": int(counts["NEITHER"]),
        "n_ambiguous": int(counts["AMBIGUOUS"]),
        "n_unlabeled": int(counts[None]),
        "n_labeled": labeled,
        "p_break": rate("BREAK"),
        "p_reject": rate("REJECT"),
        "p_neither": rate("NEITHER"),
        "p_resolve": None if labeled == 0 else (counts["BREAK"] + counts["REJECT"]) / labeled,
    }


def _fit(rows, feature, scales, *, stacked, family, side, epoch, draws, seed, outcome, spec, slice_name):
    cell = fit_rows(
        rows, feature, scales, stacked=stacked, family=family, side=side, epoch=epoch,
        end_position=True, draws=draws, seed=seed,
    )
    cell["outcome"] = outcome
    cell["spec"] = spec
    cell["slice"] = slice_name
    return cell


def estimate(real_rows: list[dict], pairs: list[dict], scales: dict, retained: list[str], *,
             draws: int = K.BOOT_DRAWS) -> dict:
    primary = []
    pseudo = []
    specificity = []
    stability = []
    loyo = []
    lofo = []
    shapes = []
    for fi, feature in enumerate(retained):
        for oi, outcome in enumerate(K.OUTCOMES):
            require_end = feature != K.PRICE_FEATURE
            real = [
                row for row in (_ready(r, feature, outcome, require_end=require_end) for r in real_rows)
                if row
            ]
            cell = _fit(
                real, feature, scales, stacked=False, family=True, side=True, epoch=True,
                draws=draws, seed=K.stream_seed(fi, oi, 0), outcome=outcome, spec="primary",
                slice_name="all",
            )
            primary.append(cell)
            matched = []
            pseudo_only = []
            for pair in pairs:
                left = _ready(pair["real"], feature, outcome, require_end=require_end)
                right = _ready(pair["pseudo"], feature, outcome, require_end=require_end)
                if left is None or right is None:
                    continue
                matched.append({**left, "real": 1.0, "cluster": int(pair["real"]["week"])})
                matched.append({**right, "real": 0.0, "cluster": int(pair["real"]["week"])})
                pseudo_only.append({**right, "cluster": int(pair["pseudo"]["week"])})
            pseudo.append(_fit(
                pseudo_only, feature, scales, stacked=False, family=True, side=True, epoch=True,
                draws=draws, seed=K.stream_seed(fi, oi, 1), outcome=outcome, spec="pseudo",
                slice_name="matched",
            ))
            specificity.append(_fit(
                matched, feature, scales, stacked=True, family=True, side=True, epoch=True,
                draws=draws, seed=K.stream_seed(fi, oi, 2), outcome=outcome, spec="specificity",
                slice_name="matched",
            ))
            for epoch_name in K.EPOCHS:
                stability.append(_fit(
                    [row for row in real if row["epoch"] == epoch_name], feature, scales,
                    stacked=False, family=True, side=True, epoch=False, draws=0, seed=0,
                    outcome=outcome, spec="epoch", slice_name=epoch_name,
                ))
            for family in K.FAMILIES:
                stability.append(_fit(
                    [row for row in real if row["family"] == family], feature, scales,
                    stacked=False, family=False, side=True, epoch=True, draws=0, seed=0,
                    outcome=outcome, spec="family", slice_name=family,
                ))
            for side_name, side_value in (("resistance", 1), ("support", -1)):
                stability.append(_fit(
                    [row for row in real if int(row["side"]) == side_value], feature, scales,
                    stacked=False, family=True, side=False, epoch=True, draws=0, seed=0,
                    outcome=outcome, spec="side", slice_name=side_name,
                ))
            for epoch_name in K.EPOCHS:
                loyo.append(_fit(
                    [row for row in real if row["epoch"] != epoch_name], feature, scales,
                    stacked=False, family=True, side=True, epoch=True, draws=0, seed=0,
                    outcome=outcome, spec="loyo", slice_name=f"omit_{epoch_name}",
                ))
            n_real = len(real)
            for family in K.FAMILIES:
                kept = [row for row in real if row["family"] != family]
                dropped = n_real - len(kept)
                item = _fit(
                    kept, feature, scales, stacked=False, family=True, side=True, epoch=True,
                    draws=0, seed=0, outcome=outcome, spec="lofo", slice_name=f"omit_{family}",
                )
                item["dropped_share"] = None if n_real == 0 else dropped / n_real
                item["dropped_family"] = family
                lofo.append(item)
            table = shape_table(real, feature, scales[feature])
            shapes.append({
                "feature": feature, "outcome": outcome, "spec": "shape",
                "bands": table, "label": shape_label(table),
            })
    qs = bh_adjust([cell["p"] for cell in primary])
    for cell, q in zip(primary, qs):
        cell["q"] = q
    decisions = []
    for cell, stacked in zip(primary, specificity):
        epochs = [
            item for item in stability
            if item["feature"] == cell["feature"] and item["outcome"] == cell["outcome"] and item["spec"] == "epoch"
        ]
        held = [item for item in loyo if item["feature"] == cell["feature"] and item["outcome"] == cell["outcome"]]
        families = [item for item in lofo if item["feature"] == cell["feature"] and item["outcome"] == cell["outcome"]]
        sides = [
            item for item in stability
            if item["feature"] == cell["feature"] and item["outcome"] == cell["outcome"] and item["spec"] == "side"
        ]
        rule = conjunction(cell, epochs, held, families, sides)
        label = specificity_label(cell, stacked) if rule["pass"] else "NONE"
        decisions.append({
            "feature": cell["feature"],
            "outcome": cell["outcome"],
            "conjunction_pass": rule["pass"],
            "failed": rule["failed"],
            "statistical_hit": statistical_hit(cell),
            "label": label,
            "primary_coef": cell["coef"],
            "primary_ci95": cell["ci95"],
            "q": cell["q"],
            "delta": stacked.get("delta"),
            "delta_ci95": stacked.get("ci95"),
            "beta_real": stacked.get("beta_real"),
            "beta_pseudo": stacked.get("beta_pseudo"),
        })
    labeled = [
        row for row in real_rows
        if row.get("early_status") == "UNRESOLVED" and row.get("outcome") in ("BREAK", "REJECT", "NEITHER")
    ]
    clusters = len({int(row["week"]) for row in labeled})
    resolve_cells = [cell for cell in primary if cell["outcome"] == "LATE_RESOLVE_BY_4H"]
    n_info = max((int(cell["n"]) for cell in resolve_cells), default=0)
    c_info = max((int(cell["clusters"]) for cell in resolve_cells), default=0)
    routing = route(decisions, n_resolve=n_info, clusters=c_info)
    ideas = []
    for item in shapes:
        if item["label"] in ("u_shape", "other"):
            ideas.append(
                f"EXPLORATORY_SUCCESSOR_IDEA: {item['feature']} vs {item['outcome']} is {item['label']} "
                "across frozen tertiles. No threshold, acceptance flag, or extra window was fit."
            )
    named = [item for item in decisions if item["label"] in (
        "LEVEL_POST_TOUCH_REACTION_CANDIDATE", "GENERIC_POST_TOUCH_STATE_CANDIDATE")]
    return {
        "primary": primary,
        "pseudo": pseudo,
        "specificity": specificity,
        "stability": stability,
        "loyo": loyo,
        "lofo": lofo,
        "shape": shapes,
        "decisions": decisions,
        "candidates": named,
        "level_post_touch_reaction_candidate": [
            item for item in named if item["label"] == "LEVEL_POST_TOUCH_REACTION_CANDIDATE"
        ],
        "generic_post_touch_state_candidate": [
            item for item in named if item["label"] == "GENERIC_POST_TOUCH_STATE_CANDIDATE"
        ],
        "routing": routing,
        "successor_candidate": "NONE",
        "exploratory_successor_ideas": ideas,
        "early_census_geometry": early_census(real_rows),
        "late_decomposition": late_decomposition(real_rows),
        "n_late_labeled": len(labeled),
        "clusters_late_labeled": clusters,
        "n_resolve_primary_max": n_info,
        "clusters_resolve_primary_max": c_info,
    }
