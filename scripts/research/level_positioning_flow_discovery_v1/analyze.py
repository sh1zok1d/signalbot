"""Join labels only after the outcome-blind freeze has been checked by the caller."""

from __future__ import annotations

from collections import Counter

from scripts.research.level_touch_degradation_v1.outcomes import classify

from . import constants as K
from .claim import conjunction, route, specificity_label, statistical_hit
from .cohort import feature_complete
from .inference import bh_adjust, fit_rows, shape_label, shape_table


def y_of(label, outcome_name: str):
    if outcome_name == "RESOLVE_4H":
        if label in ("BREAK", "REJECT"):
            return 1.0
        if label == "NEITHER":
            return 0.0
        return None
    if outcome_name == "BREAK_GIVEN_RESOLVED":
        if label == "BREAK":
            return 1.0
        if label == "REJECT":
            return 0.0
        return None
    raise ValueError(outcome_name)


def attach_outcomes(bars, rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        label = classify(
            bars.high, bars.low, int(row["j"]), int(row["side"]),
            float(row["zone_low"]), float(row["zone_high"]), float(row["x_primary"]), K.HORIZON,
        )
        out.append({**row, "outcome": label})
    return out


def _ready(row: dict, feature: str, outcome_name: str) -> dict | None:
    if not feature_complete(row, (feature,)):
        return None
    y = y_of(row.get("outcome"), outcome_name)
    if y is None:
        return None
    return {**row, "y": y}


def label_assembled(bars, assembled: dict) -> tuple[list[dict], list[dict]]:
    real = attach_outcomes(bars, assembled["real_rows"])
    by_id = {row["episode_id"]: row for row in real}
    pairs = []
    for pair in assembled["pairs"]:
        pseudo = attach_outcomes(bars, [pair["pseudo"]])[0]
        pairs.append({**pair, "real": by_id[pair["episode_id"]], "pseudo": pseudo})
    return real, pairs


def decomposition(rows: list[dict]) -> dict:
    counts = Counter(row.get("outcome") for row in rows)
    labeled = sum(counts[name] for name in ("BREAK", "REJECT", "NEITHER"))
    ambiguous = int(counts["AMBIGUOUS"])

    def rate(name: str):
        if labeled == 0:
            return None
        return counts[name] / labeled

    return {
        "n_break": int(counts["BREAK"]),
        "n_reject": int(counts["REJECT"]),
        "n_neither": int(counts["NEITHER"]),
        "n_ambiguous": ambiguous,
        "n_resolved_support": labeled,
        "p_break": rate("BREAK"),
        "p_reject": rate("REJECT"),
        "p_neither": rate("NEITHER"),
        "p_resolve": None if labeled == 0 else (counts["BREAK"] + counts["REJECT"]) / labeled,
    }


def _fit(rows, feature, scales, *, stacked, family, side, year, draws, seed, outcome, spec, slice_name):
    cell = fit_rows(
        rows, feature, scales, stacked=stacked, family=family, side=side, year=year,
        draws=draws, seed=seed,
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
            real = [row for row in (_ready(r, feature, outcome) for r in real_rows) if row]
            cell = _fit(
                real, feature, scales, stacked=False, family=True, side=True, year=True,
                draws=draws, seed=K.stream_seed(fi, oi, 0), outcome=outcome, spec="primary",
                slice_name="all",
            )
            primary.append(cell)
            matched = []
            pseudo_only = []
            for pair in pairs:
                left = _ready(pair["real"], feature, outcome)
                right = _ready(pair["pseudo"], feature, outcome)
                if left is None or right is None:
                    continue
                matched.append({**left, "real": 1.0, "cluster": int(pair["real"]["week"])})
                matched.append({**right, "real": 0.0, "cluster": int(pair["real"]["week"])})
                pseudo_only.append({**right, "cluster": int(pair["pseudo"]["week"])})
            pseudo.append(_fit(
                pseudo_only, feature, scales, stacked=False, family=True, side=True, year=True,
                draws=draws, seed=K.stream_seed(fi, oi, 1), outcome=outcome, spec="pseudo",
                slice_name="matched",
            ))
            specificity.append(_fit(
                matched, feature, scales, stacked=True, family=True, side=True, year=True,
                draws=draws, seed=K.stream_seed(fi, oi, 2), outcome=outcome, spec="specificity",
                slice_name="matched",
            ))
            for epoch in K.EPOCHS:
                stability.append(_fit(
                    [row for row in real if row["epoch"] == epoch], feature, scales,
                    stacked=False, family=True, side=True, year=False, draws=0, seed=0,
                    outcome=outcome, spec="epoch", slice_name=epoch,
                ))
            for family in K.FAMILIES:
                stability.append(_fit(
                    [row for row in real if row["family"] == family], feature, scales,
                    stacked=False, family=False, side=True, year=True, draws=0, seed=0,
                    outcome=outcome, spec="family", slice_name=family,
                ))
            for side_name, side_value in (("resistance", 1), ("support", -1)):
                stability.append(_fit(
                    [row for row in real if int(row["side"]) == side_value], feature, scales,
                    stacked=False, family=True, side=False, year=True, draws=0, seed=0,
                    outcome=outcome, spec="side", slice_name=side_name,
                ))
            for epoch in K.EPOCHS:
                year = 2020 if epoch == "2020Q4" else int(epoch)
                loyo.append(_fit(
                    [row for row in real if int(row["year"]) != year], feature, scales,
                    stacked=False, family=True, side=True, year=True, draws=0, seed=0,
                    outcome=outcome, spec="loyo", slice_name=f"omit_{epoch}",
                ))
            n_real = len(real)
            for family in K.FAMILIES:
                kept = [row for row in real if row["family"] != family]
                dropped = n_real - len(kept)
                item = _fit(
                    kept, feature, scales, stacked=False, family=True, side=True, year=True,
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
        epochs = [item for item in stability if item["feature"] == cell["feature"] and item["outcome"] == cell["outcome"] and item["spec"] == "epoch"]
        held = [item for item in loyo if item["feature"] == cell["feature"] and item["outcome"] == cell["outcome"]]
        families = [item for item in lofo if item["feature"] == cell["feature"] and item["outcome"] == cell["outcome"]]
        rule = conjunction(cell, epochs, held, families)
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
    resolve_rows = [row for row in real_rows if row.get("outcome") in ("BREAK", "REJECT", "NEITHER")]
    clusters = len({int(row["week"]) for row in resolve_rows})
    resolve_cells = [cell for cell in primary if cell["outcome"] == "RESOLVE_4H"]
    n_info = max((int(cell["n"]) for cell in resolve_cells), default=0)
    c_info = max((int(cell["clusters"]) for cell in resolve_cells), default=0)
    routing = route(decisions, n_resolve=n_info, clusters=c_info)
    ideas = []
    for item in shapes:
        if item["label"] == "u_shape":
            ideas.append(
                f"EXPLORATORY_SUCCESSOR_IDEA: {item['feature']} vs {item['outcome']} is U-shaped "
                "across frozen tertiles. No threshold, saturation model, or interaction was fit."
            )
    candidates = [item for item in decisions if item["label"] in (
        "LEVEL_INTERACTION_CANDIDATE", "GENERIC_STATE_CANDIDATE")]
    return {
        "primary": primary,
        "pseudo": pseudo,
        "specificity": specificity,
        "stability": stability,
        "loyo": loyo,
        "lofo": lofo,
        "shape": shapes,
        "decisions": decisions,
        "candidates": candidates,
        "routing": routing,
        "successor_candidate": "NONE" if not candidates else [
            f"{item['label']}:{item['feature']}:{item['outcome']}" for item in candidates
        ],
        "exploratory_successor_ideas": ideas,
        "decomposition_geometry": decomposition(real_rows),
        "n_resolve_geometry": len(resolve_rows),
        "clusters_resolve_geometry": clusters,
        "n_resolve_primary_max": n_info,
        "clusters_resolve_primary_max": c_info,
    }
