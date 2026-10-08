"""Join resolution labels only after the frozen state model has been checked."""

from __future__ import annotations

from collections import Counter

import numpy as np

from scripts.research.level_touch_degradation_v1.outcomes import classify

from . import cluster, constants as K
from .claim import conjunction, route, specificity_label, statistical_hit, successor_list
from .cohort import outcome_ready, predictors_ok
from .inference import bh_adjust, fit_rows


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


def assign_states(rows: list[dict], scaler: dict, centroids: list[list[float]]) -> list[dict]:
    centers = np.asarray(centroids, dtype=float)
    out = []
    for row in rows:
        if not predictors_ok(row):
            out.append({**row, "state": None})
            continue
        raw = cluster.matrix_of([row])
        z, _outside = cluster.transform(raw, scaler)
        index = int(cluster.assign_nearest(z, centers)[0])
        out.append({**row, "state": cluster.state_name(index)})
    return out


def label_assembled(bars, assembled: dict, scaler: dict, centroids: list) -> tuple[list[dict], list[dict]]:
    real = assign_states(attach_outcomes(bars, assembled["real_rows"]), scaler, centroids)
    by_id = {row["episode_id"]: row for row in real}
    pairs = []
    for pair in assembled["pairs"]:
        pseudo = assign_states(attach_outcomes(bars, [pair["pseudo"]]), scaler, centroids)[0]
        pairs.append({**pair, "real": by_id[pair["episode_id"]], "pseudo": pseudo})
    return real, pairs


def _ready(row: dict, outcome_name: str) -> dict | None:
    if not outcome_ready(row):
        return None
    y = y_of(row.get("outcome"), outcome_name)
    if y is None:
        return None
    return {**row, "y": y}


def _fit(rows, state_name, activity, *, stacked, family, side, year, draws, seed, outcome, spec, slice_name):
    cell = fit_rows(
        rows, state_name, activity, stacked=stacked, family=family, side=side, year=year,
        draws=draws, seed=seed,
    )
    cell["outcome"] = outcome
    cell["spec"] = spec
    cell["slice"] = slice_name
    return cell


def three_way(rows: list[dict], names: list[str]) -> list[dict]:
    tables = []
    for name in names:
        members = [row for row in rows if row.get("state") == name and row.get("outcome") != "AMBIGUOUS"]
        counts = Counter(row.get("outcome") for row in members)
        labeled = sum(int(counts[key]) for key in ("BREAK", "REJECT", "NEITHER"))
        resolved = int(counts["BREAK"] + counts["REJECT"])

        def rate(key: str):
            return None if labeled == 0 else counts[key] / labeled

        tables.append({
            "state": name,
            "n": labeled,
            "n_ambiguous": int(counts["AMBIGUOUS"]),
            "p_break": rate("BREAK"),
            "p_reject": rate("REJECT"),
            "p_neither": rate("NEITHER"),
            "p_resolve": None if labeled == 0 else resolved / labeled,
            "p_break_given_resolved": None if resolved == 0 else counts["BREAK"] / resolved,
        })
    return tables


def estimate(real_rows: list[dict], pairs: list[dict], activity: dict, names: list[str],
             jaccard: list[float], *, draws: int = K.BOOT_DRAWS) -> dict:
    primary, pseudo, specificity, stability, loyo, lofo = [], [], [], [], [], []
    for si, name in enumerate(names):
        for oi, outcome in enumerate(K.OUTCOMES):
            real = [row for row in (_ready(r, outcome) for r in real_rows) if row]
            cell = _fit(
                real, name, activity, stacked=False, family=True, side=True, year=True,
                draws=draws, seed=K.stream_seed(si, oi, 0), outcome=outcome, spec="primary",
                slice_name="all",
            )
            primary.append(cell)
            matched, pseudo_only = [], []
            for pair in pairs:
                left = _ready(pair["real"], outcome)
                right = _ready(pair["pseudo"], outcome)
                if left is None or right is None:
                    continue
                matched.append({**left, "real": 1.0, "cluster": int(pair["real"]["week"])})
                matched.append({**right, "real": 0.0, "cluster": int(pair["real"]["week"])})
                pseudo_only.append({**right, "cluster": int(pair["pseudo"]["week"])})
            pseudo.append(_fit(
                pseudo_only, name, activity, stacked=False, family=True, side=True, year=True,
                draws=draws, seed=K.stream_seed(si, oi, 1), outcome=outcome, spec="pseudo",
                slice_name="matched",
            ))
            specificity.append(_fit(
                matched, name, activity, stacked=True, family=True, side=True, year=True,
                draws=draws, seed=K.stream_seed(si, oi, 2), outcome=outcome, spec="specificity",
                slice_name="matched",
            ))
            for epoch in K.EPOCHS:
                stability.append(_fit(
                    [row for row in real if row["epoch"] == epoch], name, activity,
                    stacked=False, family=True, side=True, year=False, draws=0, seed=0,
                    outcome=outcome, spec="epoch", slice_name=epoch,
                ))
            for family in K.FAMILIES:
                stability.append(_fit(
                    [row for row in real if row["family"] == family], name, activity,
                    stacked=False, family=False, side=True, year=True, draws=0, seed=0,
                    outcome=outcome, spec="family", slice_name=family,
                ))
            for side_name, side_value in (("resistance", 1), ("support", -1)):
                stability.append(_fit(
                    [row for row in real if int(row["side"]) == side_value], name, activity,
                    stacked=False, family=True, side=False, year=True, draws=0, seed=0,
                    outcome=outcome, spec="side", slice_name=side_name,
                ))
            for epoch in K.EPOCHS:
                year = 2020 if epoch == "2020Q4" else int(epoch)
                loyo.append(_fit(
                    [row for row in real if int(row["year"]) != year], name, activity,
                    stacked=False, family=True, side=True, year=True, draws=0, seed=0,
                    outcome=outcome, spec="loyo", slice_name=f"omit_{epoch}",
                ))
            n_real = len(real)
            for family in K.FAMILIES:
                kept = [row for row in real if row["family"] != family]
                item = _fit(
                    kept, name, activity, stacked=False, family=True, side=True, year=True,
                    draws=0, seed=0, outcome=outcome, spec="lofo", slice_name=f"omit_{family}",
                )
                item["dropped_share"] = None if n_real == 0 else (n_real - len(kept)) / n_real
                item["dropped_family"] = family
                lofo.append(item)
    qs = bh_adjust([cell["p"] for cell in primary])
    for cell, q in zip(primary, qs):
        cell["q"] = q
    decisions = []
    for cell, stacked in zip(primary, specificity):
        epochs = [
            item for item in stability
            if item["state"] == cell["state"] and item["outcome"] == cell["outcome"] and item["spec"] == "epoch"
        ]
        held = [
            item for item in loyo
            if item["state"] == cell["state"] and item["outcome"] == cell["outcome"]
        ]
        dropped = [
            item for item in lofo
            if item["state"] == cell["state"] and item["outcome"] == cell["outcome"]
        ]
        index = names.index(cell["state"])
        rule = conjunction(cell, epochs, held, dropped, jaccard[index] if index < len(jaccard) else None)
        label = "NONE"
        if rule["pass"]:
            label = specificity_label(cell, stacked)
        decisions.append({
            "state": cell["state"],
            "outcome": cell["outcome"],
            "label": label,
            "conjunction": rule,
            "statistical_hit": statistical_hit(cell),
            "specificity_delta": stacked.get("delta"),
        })
    resolve_rows = [row for row in (_ready(r, "RESOLVE_4H") for r in real_rows) if row]
    weeks = {int(row["cluster"]) for row in resolve_rows}
    names_out = successor_list(decisions)
    return {
        "primary": primary,
        "pseudo": pseudo,
        "specificity": specificity,
        "stability": stability,
        "loyo": loyo,
        "lofo": lofo,
        "decisions": decisions,
        "three_way": three_way(real_rows, names),
        "n_resolve": len(resolve_rows),
        "clusters_resolve": len(weeks),
        "routing": route(decisions, n_resolve=len(resolve_rows), clusters=len(weeks)),
        "successor_candidate": names_out if names_out else "NONE",
        "ideas": [
            "EXPLORATORY_SUCCESSOR_IDEA: do not split a state, add a ratio, or fit an OI-by-flow product on this matrix.",
        ],
    }
