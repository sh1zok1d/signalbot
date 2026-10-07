"""One official LEVEL_STRUCTURE_DISCOVERY_V1 evaluation.

Reads the outcome-blind preflight for the retained family, the coding and the frozen
scales. Does not add a feature, a tolerance, a horizon or a control, and refuses to
overwrite an existing result.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.research.level_approach_state_discovery_v1.approach import compute_features, price_features_ok, volume_ok
from scripts.research.level_approach_state_discovery_v1.constants import BAND_MULT_PRIMARY
from scripts.research.level_touch_degradation_v1.build import build_population
from scripts.research.level_touch_degradation_v1.constants import (
    BARRIER_FRACTION_PRIMARY,
    HOLD_BARS_PRIMARY,
    ZONE_HALF_PRIMARY,
)
from scripts.research.level_touch_degradation_v1.data import load_discovery_bars
from scripts.research.level_touch_degradation_v1.outcomes import attach

from . import claim, constants as K
from .inference import bh_adjust, lpm, shape_contrast, shape_label
from .rows import complete, control_rows, prepare, real_rows, restrict_matched

ROOT = Path(__file__).resolve().parents[3]
PRE = ROOT / "docs" / "research" / "LEVEL_STRUCTURE_DISCOVERY_V1_PREFLIGHT.json"
RESULT_JSON = ROOT / "docs" / "research" / "LEVEL_STRUCTURE_DISCOVERY_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "LEVEL_STRUCTURE_DISCOVERY_V1_RESULT.md"


def _design_sha() -> str:
    import subprocess
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", "docs/research/LEVEL_STRUCTURE_DISCOVERY_V1_DESIGN.md"],
            cwd=ROOT, text=True,
        ).strip()
    except subprocess.CalledProcessError:
        return ""
    return out


def _outcome_index(bars, touches) -> dict:
    scored = attach(bars.high, bars.low, touches, horizon=HOLD_BARS_PRIMARY,
                    barrier_fraction=BARRIER_FRACTION_PRIMARY)
    return {(touch["episode_id"], int(touch["j"])): touch.get("outcome") for touch in scored}


def _apply_coding(rows: list[dict], coding: dict) -> None:
    for name, decision in coding.items():
        if decision.get("coding") != "binary":
            continue
        for row in rows:
            value = row.get(name)
            if value is None:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                row[name] = None
                continue
            if number != number:
                row[name] = None
            else:
                row[name] = 1.0 if number >= 2.0 else 0.0


def _keep(rows: list[dict], outcomes: dict) -> tuple[list[dict], dict]:
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
    return kept, {"rows": len(rows), "ambiguous": ambiguous, "missing_outcome": missing}


def _slice(rows, **pred):
    return [row for row in rows if all(row[key] == value for key, value in pred.items())]


def _pp(value) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * value:+.1f} pp"


def _ci(ci) -> str:
    if not ci:
        return "n/a"
    return f"{_pp(ci[0])}..{_pp(ci[1])}"


def _approach_attach(rows: list[dict], bars) -> list[dict]:
    out = []
    for row in rows:
        feat = compute_features(
            bars.close, bars.high, bars.low, bars.quote,
            j=int(row["j"]), i0=int(row["i0"]), side=int(row["side"]),
            zlo=float(row["zone_low"]), zhi=float(row["zone_high"]),
            x=float(row["x_primary"]), sigma=float(row["sigma"]), band_mult=BAND_MULT_PRIMARY,
        )
        if feat is None or not price_features_ok(feat) or not volume_ok(feat):
            continue
        copied = dict(row)
        for name in K.APPROACH_FEATURES:
            copied[name] = float(feat[name])
        out.append(copied)
    return out


def run() -> dict:
    if RESULT_JSON.exists():
        raise SystemExit(f"refusing to overwrite {RESULT_JSON.name}")
    pre = json.loads(PRE.read_text(encoding="utf-8"))
    retained = list(pre["retained"])
    if not retained:
        raise SystemExit("preflight retained no feature; do not invent one after the fact")
    scales = pre["scales"]
    coding = pre["coding"]
    bars = load_discovery_bars()
    built = build_population(bars, ZONE_HALF_PRIMARY)
    prepared = prepare(bars, built)
    real = real_rows(built["touches"], prepared)
    pseudo = control_rows(
        built["control_touches"], built["controls"], prepared, {row["episode_id"] for row in real})
    _apply_coding(real, coding)
    _apply_coding(pseudo, coding)
    real = complete(real, retained)
    pseudo = complete(pseudo, retained)
    real, pseudo = restrict_matched(real, pseudo)
    real_y = _outcome_index(bars, built["touches"])
    pseudo_y = _outcome_index(bars, built["control_touches"])
    real_fit, real_drop = _keep(real, real_y)
    pseudo_fit, pseudo_drop = _keep(pseudo, pseudo_y)
    rows = real_fit + pseudo_fit
    cells = {}
    shapes = {}
    for feature in retained:
        for endpoint in K.OUTCOMES:
            key = f"{feature}__{endpoint}"
            cells[key] = lpm(
                rows, scales, feature, endpoint, coding, retained,
                spec="full", draws=K.BOOT_DRAWS, seed=K.BOOT_SEED)
            cells[f"no_touch__{key}"] = lpm(
                rows, scales, feature, endpoint, coding, retained,
                spec="no_touch", draws=K.BOOT_DRAWS, seed=K.BOOT_SEED)
            shapes[key] = shape_contrast(
                rows, scales, feature, endpoint, draws=K.BOOT_DRAWS, seed=K.BOOT_SEED)
            shapes[key]["label"] = shape_label(shapes[key]["bands"], shapes[key])
            for year in K.YEARS:
                cells[f"year__{year}__{key}"] = lpm(
                    _slice(rows, year=year), scales, feature, endpoint, coding, retained,
                    spec="year", draws=0)
            for family in K.FAMILIES:
                cells[f"family__{family}__{key}"] = lpm(
                    _slice(rows, family=family), scales, feature, endpoint, coding, retained,
                    spec="family", draws=0)
            cells[f"side__resistance__{key}"] = lpm(
                _slice(rows, support=0.0), scales, feature, endpoint, coding, retained, spec="side", draws=0)
            cells[f"side__support__{key}"] = lpm(
                _slice(rows, support=1.0), scales, feature, endpoint, coding, retained, spec="side", draws=0)
            for bucket in ("1", "2", "3+"):
                cells[f"touch__{bucket}__{key}"] = lpm(
                    _slice(rows, bucket=bucket), scales, feature, endpoint, coding, retained, spec="touch", draws=0)
            for year in K.YEARS:
                cells[f"loyo__{year}__{key}"] = lpm(
                    [row for row in rows if row["year"] != year], scales, feature, endpoint, coding, retained,
                    spec="loyo", drop_year=year, draws=0)
            for family in K.FAMILIES:
                cells[f"lofo__{family}__{key}"] = lpm(
                    [row for row in rows if row["family"] != family], scales, feature, endpoint, coding, retained,
                    spec="lofo", drop_family=family, draws=0)
    order = [f"{feature}__{endpoint}" for feature in retained for endpoint in K.OUTCOMES]
    adjusted = bh_adjust([cells[key].get("p") for key in order])
    for key, q in zip(order, adjusted):
        cells[key]["q"] = q
    candidates = []
    for feature in retained:
        for endpoint in K.OUTCOMES:
            key = f"{feature}__{endpoint}"
            years = [cells[f"year__{year}__{key}"] for year in K.YEARS]
            loyo = [cells[f"loyo__{year}__{key}"] for year in K.YEARS]
            families = [cells[f"family__{family}__{key}"] for family in K.FAMILIES]
            lofo = [cells[f"lofo__{family}__{key}"] for family in K.FAMILIES]
            ok = claim.successor_ok(
                primary=cells[key], years=years, loyo=loyo, families=families, lofo=lofo,
                no_touch=cells[f"no_touch__{key}"], q=cells[key].get("q"))
            if ok:
                candidates.append({"feature": feature, "endpoint": endpoint, "delta": cells[key]["delta"]})
    approach_sensitivity = []
    if candidates:
        approach_rows = _approach_attach(rows, bars)
        for item in candidates:
            feature, endpoint = item["feature"], item["endpoint"]
            fit = lpm(
                approach_rows, scales, feature, endpoint, coding, retained,
                spec="full", draws=K.BOOT_DRAWS, seed=K.BOOT_SEED, approach=True,
                extra_scales=pre["approach_scales"])
            approach_sensitivity.append({
                "feature": feature,
                "endpoint": endpoint,
                "n": fit["n"],
                "n_real": fit["n_real"],
                "n_pseudo": fit["n_pseudo"],
                "delta": fit["delta"],
                "delta_ci95": fit["delta_ci95"],
                "beta_real": fit["beta_real"],
                "beta_pseudo": fit["beta_pseudo"],
                "primary_n": cells[f"{feature}__{endpoint}"]["n"],
            })
    primary_cells = [cells[key] for key in order]
    no_touch_cells = [cells[f"no_touch__{key}"] for key in order]
    sparse = any(
        (coding.get(name) or {}).get("coding") == "binary" and (coding.get(name) or {}).get("share_ge3", 1) < K.COUNT_GE3_SHARE
        for name in retained
    )
    status = claim.routing_status(len(candidates), primary_cells, no_touch_cells, sparse_note=False)
    result = {
        "unit": K.UNIT,
        "mode": K.MODE,
        "tracks": list(K.TRACKS),
        "method_before_outcome": _design_sha(),
        "dependency": {
            "touch": K.DEPENDENCY_TOUCH_SHA,
            "memory": K.DEPENDENCY_MEMORY_SHA,
            "method": K.DEPENDENCY_METHOD_SHA,
            "approach": K.DEPENDENCY_APPROACH_SHA,
        },
        "retained": retained,
        "coding": coding,
        "routing_status": status,
        "atlas_state": claim.atlas_state(status),
        "claim_level": claim.claim_level(status, len(real_fit)),
        "successor_candidates": candidates,
        "product_integration_candidate": "NO",
        "interactions_estimated": 0,
        "exploratory_successor_ideas": [],
        "sparse_binary_present": sparse,
        "n_real": len(real_fit),
        "n_pseudo": len(pseudo_fit),
        "clusters": len({row["cluster"] for row in rows}),
        "real_drops": real_drop,
        "pseudo_drops": pseudo_drop,
        "material_cells": K.material_cells(len(retained)),
        "fdr_family_size": K.fdr_family_size(len(retained)),
        "fdr_q": K.FDR_Q,
        "practical_scale": K.PRACTICAL_SCALE,
        "cells": cells,
        "shapes": shapes,
        "approach_sensitivity": approach_sensitivity,
        "day_share_cap_applied": False,
    }
    RESULT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD.write_text(_markdown(result), encoding="utf-8")
    return {
        "routing": status,
        "claim": result["claim_level"],
        "candidates": [f"{c['feature']}->{c['endpoint']}" for c in candidates],
        "n_real": len(real_fit),
        "n_pseudo": len(pseudo_fit),
    }


def _markdown(result: dict) -> str:
    lines = [
        "# LEVEL_STRUCTURE_DISCOVERY_V1 — result",
        "",
        "MODE = `DISCOVERY`. Tracks: STRUCTURE, PRODUCT_EVIDENCE.",
        f"Design note commit `{result['method_before_outcome']}`.",
        f"Dependencies: `{result['dependency']['touch']}` (#352), `{result['dependency']['memory']}` (#353), "
        f"`{result['dependency']['method']}` (#354), `{result['dependency']['approach']}` (#355).",
        "",
        "## routing",
        "",
        f"`{result['routing_status']}`. Atlas state `{result['atlas_state']}`. Claim `{result['claim_level']}`.",
        "SUCCESSOR_CANDIDATE = "
        + ("NONE" if not result["successor_candidates"] else ", ".join(
            f"{c['feature']}->{c['endpoint']}" for c in result["successor_candidates"])) + ".",
        "PRODUCT_INTEGRATION_CANDIDATE = NO.",
        "The screened object is Δ = β_real − β_pseudo. The 70% DAY cap from #355 is not applied.",
        "",
        "## level-specific increments",
        "",
        "Adjusted Δ per +1 SD, or per the binary multi-minus-singleton contrast. "
        f"95% cluster-bootstrap interval. q is Benjamini–Hochberg within the {result['fdr_family_size']} "
        f"primary increments, q cut {result['fdr_q']}.",
        "",
        "| feature | outcome | Δ | 95% | q | β_real | β_pseudo | N real | N pseudo |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for feature in result["retained"]:
        for endpoint in K.OUTCOMES:
            cell = result["cells"][f"{feature}__{endpoint}"]
            lines.append(
                f"| {feature} | {endpoint} | {_pp(cell.get('delta'))} | {_ci(cell.get('delta_ci95'))} | "
                f"{cell.get('q'):.3f} | {_pp(cell.get('beta_real'))} | {_pp(cell.get('beta_pseudo'))} | "
                f"{cell.get('n_real')} | {cell.get('n_pseudo')} |"
            )
    lines.extend(["", "## shapes", "", "Real rate, pseudo rate, and real−pseudo inside each frozen band.", ""])
    for feature in result["retained"]:
        for endpoint in K.OUTCOMES:
            shape = result["shapes"][f"{feature}__{endpoint}"]
            bits = []
            for band, info in shape["bands"].items():
                bits.append(
                    f"{band}: real {_fmt_rate(info['real_p'])} (N={info['real_n']}), "
                    f"pseudo {_fmt_rate(info['pseudo_p'])} (N={info['pseudo_n']}), "
                    f"diff {_pp(info['diff'])}"
                )
            lines.append(
                f"- {feature} → {endpoint} ({shape['label']}; high−low or binary contrast "
                f"{_pp(shape.get('coef'))} ({_ci(shape.get('ci95'))}): " + "; ".join(bits)
            )
    lines.extend(["", "## year Δ", ""])
    lines.extend(_block(result, "year", [str(year) for year in K.YEARS]))
    lines.extend(["", "## family Δ", ""])
    lines.extend(_block(result, "family", list(K.FAMILIES)))
    lines.extend(["", "## side Δ", ""])
    lines.extend(_block(result, "side", ["resistance", "support"]))
    lines.extend(["", "## touch ordinal Δ", ""])
    lines.extend(_block(result, "touch", ["1", "2", "3+"]))
    lines.extend(["", "## leave-one-year-out Δ", ""])
    lines.extend(_block(result, "loyo", [str(year) for year in K.YEARS]))
    lines.extend(["", "## leave-one-family-out Δ", ""])
    lines.extend(_block(result, "lofo", list(K.FAMILIES)))
    lines.extend(["", "## without touch ordinal", ""])
    lines.append("| feature | outcome | Δ | 95% |")
    lines.append("|---|---|---:|---|")
    for feature in result["retained"]:
        for endpoint in K.OUTCOMES:
            cell = result["cells"][f"no_touch__{feature}__{endpoint}"]
            lines.append(f"| {feature} | {endpoint} | {_pp(cell.get('delta'))} | {_ci(cell.get('delta_ci95'))} |")
    lines.extend(["", "## approach-path sensitivity", ""])
    if not result["approach_sensitivity"]:
        lines.append("No successor candidate. The approach adjustment was not used to search for one.")
    else:
        for item in result["approach_sensitivity"]:
            lines.append(
                f"- {item['feature']} → {item['endpoint']}: Δ {_pp(item['delta'])} ({_ci(item['delta_ci95'])}), "
                f"N={item['n']} (primary N={item['primary_n']})."
            )
    lines.extend([
        "",
        "## information",
        "",
        f"Real analysis touches N={result['n_real']}. Pseudo touches N={result['n_pseudo']}. "
        f"Matched-episode clusters={result['clusters']}. "
        f"Ambiguous real bars dropped: {result['real_drops']['ambiguous']}. "
        f"Ambiguous pseudo bars dropped: {result['pseudo_drops']['ambiguous']}.",
        "",
        "## search exposure",
        "",
        f"{result['material_cells']} material cells. FDR family size {result['fdr_family_size']}. "
        "No cell was added after the outcomes were read. Interactions estimated: 0.",
        "",
        "## limitations",
        "",
        "The cohort is the #352 feature-eligible structural touches, not the approach-eligible subset. "
        "Features use the anchor source period, which is closed before the level is active, and constituents "
        "known at the open of the touch bar. The control keeps that metadata and moves the price by the "
        "parent half-rotation. Separate outcome models are not constrained to sum to one. "
        "A historical frequency here is not a current probability. "
        "A cell that passes the successor rule is DISCOVERY_ONLY on this selection surface.",
        "",
        "## product",
        "",
        "Not integrated. No `/levels` change, no findings-registry edit, no deploy. Confirmation was not started.",
        "",
    ])
    return "\n".join(lines)


def _fmt_rate(value) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * value:.1f}%"


def _block(result: dict, prefix: str, labels: list[str]) -> list[str]:
    lines = []
    for endpoint in K.OUTCOMES:
        lines.append(f"### {endpoint}")
        lines.append("")
        lines.append("| feature | " + " | ".join(labels) + " |")
        lines.append("|---|" + "|".join("---:" for _ in labels) + "|")
        for feature in result["retained"]:
            bits = []
            for label in labels:
                cell = result["cells"][f"{prefix}__{label}__{feature}__{endpoint}"]
                bits.append(f"{_pp(cell.get('delta'))} (Nr={cell.get('n_real')})")
            lines.append(f"| {feature} | " + " | ".join(bits) + " |")
        lines.append("")
    return lines


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
