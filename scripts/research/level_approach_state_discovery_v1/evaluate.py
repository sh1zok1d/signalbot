"""One official LEVEL_APPROACH_STATE_DISCOVERY_V1 evaluation.

Reads the outcome-blind preflight for the retained family and the frozen scales.
Does not add a feature, a window, a horizon or a subgroup, and refuses to overwrite
an existing result.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.research.level_touch_degradation_v1.build import build_population
from scripts.research.level_touch_degradation_v1.constants import (
    BARRIER_FRACTION_PRIMARY,
    HOLD_BARS_PRIMARY,
    ZONE_HALF_PRIMARY,
)
from scripts.research.level_touch_degradation_v1.data import load_discovery_bars
from scripts.research.level_touch_degradation_v1.outcomes import attach

from . import claim, constants as K
from .inference import (
    bucket_rates_for,
    bh_adjust,
    lpm,
    shape_label,
    tertile_diff,
)
from .rows import collect, require_volume

ROOT = Path(__file__).resolve().parents[3]
PRE = ROOT / "docs" / "research" / "LEVEL_APPROACH_STATE_DISCOVERY_V1_PREFLIGHT.json"
RESULT_JSON = ROOT / "docs" / "research" / "LEVEL_APPROACH_STATE_DISCOVERY_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "LEVEL_APPROACH_STATE_DISCOVERY_V1_RESULT.md"


def _design_sha() -> str:
    # The design note is committed before this module is executed. The caller records
    # the sha separately when the note exists; tests do not need git.
    import subprocess
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", "docs/research/LEVEL_APPROACH_STATE_DISCOVERY_V1_DESIGN.md"],
            cwd=ROOT, text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return ""
    return out


def _prepare(touches, close, high, low, quote, outcomes: dict, band_mult: float, volume_status: str):
    rows = collect(touches, close, high, low, quote, band_mult=band_mult)
    if volume_status == "available":
        rows = require_volume(rows, ["rel_volume"])
    ambiguous = 0
    missing = 0
    kept = []
    for row in rows:
        outcome = outcomes.get((row["episode_id"], row["j"]))
        if outcome == "AMBIGUOUS":
            ambiguous += 1
            continue
        if outcome not in K.OUTCOMES:
            missing += 1
            continue
        row["outcome"] = outcome
        kept.append(row)
    return kept, {"approach_rows": len(rows), "ambiguous": ambiguous, "missing_outcome": missing}


def _outcome_index(bars, touches) -> dict:
    scored = attach(bars.high, bars.low, touches, horizon=HOLD_BARS_PRIMARY,
                    barrier_fraction=BARRIER_FRACTION_PRIMARY)
    return {(touch["episode_id"], int(touch["j"])): touch.get("outcome") for touch in scored}


def _slice(rows, **pred):
    out = []
    for row in rows:
        if all(row[key] == value for key, value in pred.items()):
            out.append(row)
    return out


def _pp(value) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * value:+.1f} pp"


def _ci(ci) -> str:
    if not ci:
        return "n/a"
    return f"{_pp(ci[0])}..{_pp(ci[1])}"


def _cell_line(cell: dict) -> str:
    return f"{_pp(cell.get('coef'))} ({_ci(cell.get('ci95'))}), N={cell.get('n')}"


def run() -> dict:
    if RESULT_JSON.exists():
        raise SystemExit(f"refusing to overwrite {RESULT_JSON.name}")
    pre = json.loads(PRE.read_text(encoding="utf-8"))
    retained = list(pre["retained"])
    if not retained:
        raise SystemExit("preflight retained no feature; do not invent one after the fact")
    scales = pre["scales"]
    sens_scales = pre["sensitivity_scales"]
    volume_status = pre["volume_status"]
    bars = load_discovery_bars()
    built = build_population(bars, ZONE_HALF_PRIMARY)
    real_y = _outcome_index(bars, built["touches"])
    control_y = _outcome_index(bars, built["control_touches"])
    rows, drops = _prepare(built["touches"], bars.close, bars.high, bars.low, bars.quote,
                           real_y, K.BAND_MULT_PRIMARY, volume_status)
    sens_rows, sens_drops = _prepare(built["touches"], bars.close, bars.high, bars.low, bars.quote,
                                     real_y, K.BAND_MULT_SENSITIVITY, volume_status)
    control_rows, control_drops = _prepare(
        built["control_touches"], bars.close, bars.high, bars.low, bars.quote,
        control_y, K.BAND_MULT_PRIMARY, volume_status)
    family_n = {}
    for row in rows:
        family_n[row["family"]] = family_n.get(row["family"], 0) + 1
    family_share = max(family_n.values()) / len(rows) if rows else 1.0

    cells = {}
    primary_order = []
    for feature in retained:
        for endpoint in K.OUTCOMES:
            key = f"primary__{feature}__{endpoint}"
            cells[key] = lpm(rows, scales, feature, endpoint, spec="full", draws=K.BOOT_DRAWS, seed=K.BOOT_SEED)
            primary_order.append(key)
            cells[f"no_touch__{feature}__{endpoint}"] = lpm(
                rows, scales, feature, endpoint, spec="no_touch", draws=K.BOOT_DRAWS, seed=K.BOOT_SEED)
            cells[f"no_duration__{feature}__{endpoint}"] = lpm(
                rows, scales, feature, endpoint, spec="no_duration", draws=K.BOOT_DRAWS, seed=K.BOOT_SEED)
            cells[f"tertile__{feature}__{endpoint}"] = tertile_diff(
                rows, scales, feature, endpoint, draws=K.BOOT_DRAWS, seed=K.BOOT_SEED)
            cells[f"sensitivity__{feature}__{endpoint}"] = lpm(
                sens_rows, sens_scales, feature, endpoint, spec="full", draws=K.BOOT_DRAWS, seed=K.BOOT_SEED)
            cells[f"control__{feature}__{endpoint}"] = lpm(
                control_rows, scales, feature, endpoint, spec="full", draws=K.BOOT_DRAWS, seed=K.BOOT_SEED)
            for year in K.YEARS:
                cells[f"year__{year}__{feature}__{endpoint}"] = lpm(
                    _slice(rows, year=year), scales, feature, endpoint, spec="year", draws=0)
            for family in K.FAMILIES:
                cells[f"family__{family}__{feature}__{endpoint}"] = lpm(
                    _slice(rows, family=family), scales, feature, endpoint, spec="family", draws=0)
            cells[f"side__resistance__{feature}__{endpoint}"] = lpm(
                _slice(rows, support=0.0), scales, feature, endpoint, spec="side", draws=0)
            cells[f"side__support__{feature}__{endpoint}"] = lpm(
                _slice(rows, support=1.0), scales, feature, endpoint, spec="side", draws=0)
            for year in K.YEARS:
                cells[f"loyo__{year}__{feature}__{endpoint}"] = lpm(
                    [row for row in rows if row["year"] != year], scales, feature, endpoint,
                    spec="loyo", drop_year=year, draws=0)

    qvalues = bh_adjust([cells[key].get("p") for key in primary_order])
    for key, q in zip(primary_order, qvalues):
        cells[key]["q"] = q

    shapes = {}
    rates = {}
    candidates = []
    for feature in retained:
        for endpoint in K.OUTCOMES:
            rate = bucket_rates_for(rows, scales, feature, endpoint)
            diff = cells[f"tertile__{feature}__{endpoint}"]
            rates[f"{feature}__{endpoint}"] = rate
            shapes[f"{feature}__{endpoint}"] = shape_label(rate, diff)
            years = [cells[f"year__{year}__{feature}__{endpoint}"] for year in K.YEARS]
            loyo = [cells[f"loyo__{year}__{feature}__{endpoint}"] for year in K.YEARS]
            families = [cells[f"family__{family}__{feature}__{endpoint}"] for family in K.FAMILIES]
            ok = claim.successor_ok(
                primary=cells[f"primary__{feature}__{endpoint}"],
                years=years, loyo=loyo, families=families,
                control=cells[f"control__{feature}__{endpoint}"],
                q=cells[f"primary__{feature}__{endpoint}"].get("q"),
                family_share=family_share,
            )
            if ok:
                candidates.append({"feature": feature, "endpoint": endpoint,
                                   "coef": cells[f"primary__{feature}__{endpoint}"]["coef"]})

    primary_cells = [cells[key] for key in primary_order]
    no_touch_cells = [cells[f"no_touch__{feature}__{endpoint}"] for feature in retained for endpoint in K.OUTCOMES]
    status = claim.routing_status(len(candidates), primary_cells, no_touch_cells)
    level = claim.claim_level(status, len(rows))
    result = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "tracks": list(K.TRACKS),
        "dependency": {
            "touch": {"unit": K.DEPENDENCY_TOUCH_UNIT, "pr": K.DEPENDENCY_TOUCH_PR, "sha": K.DEPENDENCY_TOUCH_SHA},
            "memory": {"unit": K.DEPENDENCY_MEMORY_UNIT, "pr": K.DEPENDENCY_MEMORY_PR, "sha": K.DEPENDENCY_MEMORY_SHA},
            "method": {"pr": K.DEPENDENCY_METHOD_PR, "sha": K.DEPENDENCY_METHOD_SHA},
        },
        "method_before_outcome": _design_sha(),
        "retained": retained,
        "dropped": pre["dropped"],
        "n_analysis": len(rows),
        "clusters": len({row["cluster"] for row in rows}),
        "drops": drops,
        "sensitivity_drops": sens_drops,
        "control_drops": control_drops,
        "control_n": len(control_rows),
        "sensitivity_n": len(sens_rows),
        "family_share_max": family_share,
        "family_n": family_n,
        "material_cells": K.material_cells(len(retained)),
        "fdr_family_size": K.fdr_family_size(len(retained)),
        "fdr_q": K.FDR_Q,
        "practical_scale": K.PRACTICAL_SCALE,
        "cells": cells,
        "bucket_rates": rates,
        "shapes": shapes,
        "successor_candidates": candidates,
        "routing_status": status,
        "atlas_state": claim.atlas_state(status),
        "claim_level": level,
        "product_integration_candidate": "NO",
        "exploratory_successor_ideas": [],
        "interactions_estimated": 0,
    }
    RESULT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD.write_text(_markdown(result), encoding="utf-8")
    return result


def _markdown(result: dict) -> str:
    lines = [
        f"# {K.UNIT} — result",
        "",
        f"MODE = `{K.MODE}`. Tracks: STRUCTURE, PRODUCT_EVIDENCE.",
        f"Dependencies: `{K.DEPENDENCY_TOUCH_SHA}` (PR #{K.DEPENDENCY_TOUCH_PR}), "
        f"`{K.DEPENDENCY_MEMORY_SHA}` (PR #{K.DEPENDENCY_MEMORY_PR}), "
        f"`{K.DEPENDENCY_METHOD_SHA}` (PR #{K.DEPENDENCY_METHOD_PR} methodology).",
        f"Design note commit `{result['method_before_outcome']}`.",
        "",
        "## routing",
        "",
        f"`{result['routing_status']}`. Atlas state `{result['atlas_state']}`. "
        f"Claim ceiling for a selected cell is DISCOVERY_ONLY; the family statement is `{result['claim_level']}`.",
        f"SUCCESSOR_CANDIDATE = {result['successor_candidates'] or 'NONE'}.",
        "PRODUCT_INTEGRATION_CANDIDATE = NO.",
        "",
        "## primary matrix",
        "",
        "Adjusted Δ frequency per +1 SD. 95% cluster-bootstrap interval. q is Benjamini-Hochberg "
        f"within the {result['fdr_family_size']} primary slopes, q cut {K.FDR_Q}.",
        "",
        "| feature | outcome | coef | 95% | q | N |",
        "|---|---|---:|---|---:|---:|",
    ]
    cells = result["cells"]
    for feature in result["retained"]:
        for endpoint in K.OUTCOMES:
            cell = cells[f"primary__{feature}__{endpoint}"]
            q = cell.get("q")
            q_txt = "n/a" if q is None else f"{q:.3f}"
            lines.append(
                f"| {feature} | {endpoint} | {_pp(cell.get('coef'))} | {_ci(cell.get('ci95'))} | {q_txt} | {cell.get('n')} |"
            )
    lines += ["", "## shapes", "", "| feature | outcome | shape | low | mid | high | high−low |",
              "|---|---|---|---:|---:|---:|---|"]
    for feature in result["retained"]:
        for endpoint in K.OUTCOMES:
            rate = result["bucket_rates"][f"{feature}__{endpoint}"]
            diff = cells[f"tertile__{feature}__{endpoint}"]
            def _share(band):
                p = rate[band]["p"]
                n = rate[band]["n"]
                if p is None:
                    return "n/a"
                return f"{100 * p:.1f}% (N={n})"
            lines.append(
                f"| {feature} | {endpoint} | {result['shapes'][f'{feature}__{endpoint}']} | "
                f"{_share('low')} | {_share('mid')} | {_share('high')} | {_cell_line(diff)} |"
            )
    lines += ["", "## companions", ""]
    for label, prefix in (("without touch ordinal", "no_touch"), ("without log duration", "no_duration"),
                          ("band mult 2", "sensitivity"), ("pseudo-level", "control")):
        lines.append(f"### {label}")
        lines.append("")
        lines.append("| feature | outcome | coef | 95% | N |")
        lines.append("|---|---|---:|---|---:|")
        for feature in result["retained"]:
            for endpoint in K.OUTCOMES:
                cell = cells[f"{prefix}__{feature}__{endpoint}"]
                lines.append(
                    f"| {feature} | {endpoint} | {_pp(cell.get('coef'))} | {_ci(cell.get('ci95'))} | {cell.get('n')} |"
                )
        lines.append("")
    for title, prefix, keys in (
        ("year", "year", [str(year) for year in K.YEARS]),
        ("family", "family", list(K.FAMILIES)),
        ("side", "side", ["resistance", "support"]),
        ("leave-one-year-out", "loyo", [str(year) for year in K.YEARS]),
    ):
        lines.append(f"## {title}")
        lines.append("")
        for endpoint in K.OUTCOMES:
            lines.append(f"### {endpoint}")
            lines.append("")
            header = " | ".join(keys)
            lines.append(f"| feature | {header} |")
            lines.append("|---|" + "|".join(["---:" for _ in keys]) + "|")
            for feature in result["retained"]:
                bits = []
                for key in keys:
                    cell = cells[f"{prefix}__{key}__{feature}__{endpoint}"]
                    bits.append(f"{_pp(cell.get('coef'))} (N={cell.get('n')})")
                lines.append(f"| {feature} | " + " | ".join(bits) + " |")
            lines.append("")
    lines += [
        "## information",
        "",
        f"Analysis touches N={result['n_analysis']}. Episode clusters={result['clusters']}. "
        f"Ambiguous next bars dropped: {result['drops']['ambiguous']}. "
        f"Control N={result['control_n']}. Sensitivity N={result['sensitivity_n']}. "
        f"Busiest family share {100 * result['family_share_max']:.1f}%.",
        "",
        "## search exposure",
        "",
        f"{result['material_cells']} material cells. FDR family size {result['fdr_family_size']}. "
        "No cell was added after the outcomes were read. Interactions estimated: 0.",
        "",
        "## limitations",
        "",
        "The sample is touches of ex-ante structural zones that had an observed entry into the "
        "predeclared outer band and a later 4h window. Features use only bars before the touch. "
        "Separate linear probability models are not constrained to sum to one across BREAK, REJECT "
        "and NEITHER. Episode clustering does not model every shared path across zones. A 5m bar "
        "that hits both barriers is dropped. One venue, 2020–2024, on a surface already used for "
        "level research. A historical frequency here is not a current probability. A cell that "
        "passes the successor rule is DISCOVERY_ONLY on this selection surface.",
        "",
        "## product",
        "",
        "Not integrated. No `/levels` change, no findings-registry edit, no deploy. "
        "Confirmation was not started.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    result = run()
    print(json.dumps({
        "routing": result["routing_status"],
        "claim": result["claim_level"],
        "candidates": result["successor_candidates"],
        "n": result["n_analysis"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
