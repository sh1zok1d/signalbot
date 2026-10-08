"""One historical outcome read of the frozen FROZEN_HOUR_RANGE map.

The owner go is the only authority for the market run. A second official write
refuses. Synthetic callers use `analyze_scored` and do not touch the result files.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from . import census, constants as K, multiplicity, outcomes, routing, specificity

ROOT = Path(__file__).resolve().parents[3]
PKG = Path(__file__).resolve().parent
RESULT_JSON = ROOT / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_RESULT.json"
RESULT_MD = ROOT / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_RESULT.md"
MANIFEST_PATH = ROOT / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_EVALUATOR_MANIFEST.json"
CENSUS_PATH = ROOT / "docs" / "research" / "OPENING_RANGE_OBJECT_V1_AMENDMENT_A1_CENSUS.json"
REFUSAL_RERUN = "REFUSING_RERUN"
# Original design §6. Descriptive only. Not a candidate rule.
STABILITY_YEAR_MIN = 30
STABILITY_SIDE_MIN = 100
BOOT_VALID_FRACTION_MIN = 0.9
MAP_FIELDS = {
    "DIRECTION_EXTENSION_FIRST": "extension_first",
    "OUTSIDE_OCCUPANCY": "outside_share",
    "OUTWARD_EXCURSION": "outward_excursion",
}
ROUTE_SENTENCE = {
    "INFORMATION_LIMITED": "The frozen information rule was not met, or a required bootstrap stream was not interpretable. No candidate is declared.",
    "CLOCK_SPECIFICITY_INFORMATION_LIMITED": "The primary foundation cell cleared its simultaneous rule and a diagnostic cell did not meet the information floor. Clock specificity is not interpreted.",
    "UTC_DAY_BOUNDARY_RANGE_CANDIDATE": "UTC_00 cleared the foundation family rule and the three direct contrasts cleared the specificity family rule.",
    "GENERIC_FROZEN_HOUR_RANGE_STRUCTURE": "The four foundation cells cleared and none of the three direct contrasts separated them.",
    "FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE": "UTC_00, UTC_08, and UTC_16 cleared and the funding-hour contrasts did not separate them. This is a shared clock, not a funding-causality claim.",
    "INCONCLUSIVE": "The frozen pattern of cells and contrasts does not match a named structure route.",
    "NONFOUNDATION_MAP_CANDIDATE_ON_UTC_00": "The primary foundation cell did not clear, no diagnostic hour cleared, and at least one predeclared map row cleared Holm and its scale.",
    "NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE": "No foundation cell and no map row cleared its family rule on this surface.",
}


def code_digest() -> dict:
    digest = hashlib.sha256()
    files = {}
    for path in sorted(PKG.glob("*.py")):
        rel = str(path.relative_to(ROOT))
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        files[rel] = file_hash
        digest.update(rel.encode())
        digest.update(file_hash.encode())
    return {"files": files, "code_digest": digest.hexdigest()}


def atlas_state_for_route(route: str) -> str:
    if route == "NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE":
        return "NO_STRUCTURE"
    if route in ("INFORMATION_LIMITED", "CLOCK_SPECIFICITY_INFORMATION_LIMITED"):
        return "INFORMATIONALLY_WEAK"
    if route in (
        "INCONCLUSIVE",
        "UTC_DAY_BOUNDARY_RANGE_CANDIDATE",
        "GENERIC_FROZEN_HOUR_RANGE_STRUCTURE",
        "FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE",
        "NONFOUNDATION_MAP_CANDIDATE_ON_UTC_00",
    ):
        return "CLOSED_ON_SURFACE"
    raise ValueError(route)


def claim_for_route(route: str) -> str:
    if route in (
        "UTC_DAY_BOUNDARY_RANGE_CANDIDATE",
        "GENERIC_FROZEN_HOUR_RANGE_STRUCTURE",
        "FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE",
        "NONFOUNDATION_MAP_CANDIDATE_ON_UTC_00",
    ):
        return "L2_HISTORICAL_DIFFERENCE_ON_DISCOVERY_SURFACE"
    if route == "INCONCLUSIVE":
        return "L0_INCONCLUSIVE"
    if route == "NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE":
        return "L0_NO_CANDIDATE_ON_THIS_MAP"
    return "L0_INFORMATION_LIMITED"


def collect_pairs(high, low, close, t0: int) -> dict:
    found = {}
    for name, offset in K.ANCHORS.items():
        sink: list = []
        counts = census._cell(high, low, close, t0, offset, pair_sink=sink)
        if len(sink) != counts["paired_outcome_eligible"]:
            raise RuntimeError("pair sink does not match paired support")
        found[name] = {"counts": counts, "pairs": sink}
    return found


def _window(series, index: int):
    start = index + 1
    return np.asarray(series[start:start + K.HORIZON_BARS], dtype=np.float64)


def score_pairs(high, low, pairs: list) -> list:
    scored = []
    for pair in pairs:
        real = outcomes.score_window(
            _window(high, pair["real_index"]),
            _window(low, pair["real_index"]),
            pair["real_high"],
            pair["real_low"],
            pair["real_side"],
        )
        pseudo = outcomes.score_window(
            _window(high, pair["pseudo_index"]),
            _window(low, pair["pseudo_index"]),
            pair["pseudo_high"],
            pair["pseudo_low"],
            pair["pseudo_side"],
        )
        scored.append({
            "year": pair["year"],
            "iso_year": pair["iso_year"],
            "iso_week": pair["iso_week"],
            "real_side": pair["real_side"],
            "resolution_real": real["resolution"],
            "resolution_pseudo": pseudo["resolution"],
            "extension_first_real": real["extension_first"],
            "extension_first_pseudo": pseudo["extension_first"],
            "outside_share_real": real["outside_share"],
            "outside_share_pseudo": pseudo["outside_share"],
            "outward_excursion_real": real["outward_excursion"],
            "outward_excursion_pseudo": pseudo["outward_excursion"],
            "both_barriers_real": real["both_barriers_on_first_hit"],
            "both_barriers_pseudo": pseudo["both_barriers_on_first_hit"],
        })
    return scored


def _mean(values: list) -> float:
    if not values:
        raise ValueError("empty mean")
    return float(sum(values) / len(values))


def _week_sums(scored: list, field: str) -> dict:
    sums: dict = {}
    for row in scored:
        key = (row["iso_year"], row["iso_week"])
        delta = row[field + "_real"] - row[field + "_pseudo"]
        total, n = sums.get(key, (0.0, 0))
        sums[key] = (total + delta, n + 1)
    return sums


def _arm_summary(scored: list, field: str) -> dict:
    real = [row[field + "_real"] for row in scored]
    pseudo = [row[field + "_pseudo"] for row in scored]
    delta = [a - b for a, b in zip(real, pseudo)]
    return {
        "real": _mean(real),
        "pseudo": _mean(pseudo),
        "paired_effect": _mean(delta),
        "n_pairs": len(scored),
    }


def _stability(scored: list) -> dict:
    """Year and real-interaction side. Eligible slices only carry a mean. Not a search."""
    by_year: dict = {}
    by_side: dict = {}
    for row in scored:
        by_year.setdefault(str(row["year"]), []).append(row)
        by_side.setdefault(row["real_side"], []).append(row)
    years = {}
    for year in ("2020", "2021", "2022", "2023", "2024"):
        rows = by_year.get(year, [])
        eligible = len(rows) >= STABILITY_YEAR_MIN
        item = {"n_pairs": len(rows), "eligible": eligible, "role": "DESCRIPTIVE_NOT_A_SEARCH"}
        if eligible:
            item["paired_effect"] = _arm_summary(rows, "resolution")["paired_effect"]
        years[year] = item
    sides = {}
    for side in ("high", "low"):
        rows = by_side.get(side, [])
        eligible = len(rows) >= STABILITY_SIDE_MIN
        item = {"n_pairs": len(rows), "eligible": eligible, "role": "DESCRIPTIVE_NOT_A_SEARCH"}
        if eligible:
            item["paired_effect"] = _arm_summary(rows, "resolution")["paired_effect"]
        sides[side] = item
    return {"calendar_year": years, "real_side": sides}


def _family_intervals(summaries: dict) -> tuple[dict, dict]:
    """Joint week bootstrap for the four foundation means and the three contrasts."""
    sums = {name: _week_sums(rows, "resolution") for name, rows in summaries.items()}
    full = specificity.one_draw(sums, {week: 1 for week in sorted({w for cell in sums.values() for w in cell})})
    if full is None:
        raise RuntimeError("full-sample foundation draw is empty")
    for name, rows in summaries.items():
        direct = _arm_summary(rows, "resolution")["paired_effect"]
        if abs(direct - full["means"][name]) > 1e-9:
            raise RuntimeError("week-weighted mean does not match the pair mean")
    drawn = specificity.bootstrap(sums, draws=K.BOOT_DRAWS, seed=K.BOOT_SEED_JOINT)
    valid = drawn["valid"]
    fraction = len(valid) / drawn["draws"]
    mean_reps = [item["means"] for item in valid]
    contrast_reps = [item["contrasts"] for item in valid]
    points = {name: full["means"][name] for name in K.CLOCK_CELLS}
    contrast_points = {name: full["contrasts"][name] for name in ("UTC_08", "UTC_12", "UTC_16")}
    return points, {
        "valid_draws": len(valid),
        "draws": drawn["draws"],
        "invalid_draws": drawn["invalid"],
        "valid_fraction": fraction,
        "seed": K.BOOT_SEED_JOINT,
        "mean_reps": mean_reps,
        "contrast_reps": contrast_reps,
        "contrast_points": contrast_points,
    }


def _map_stream(scored: list, field: str, seed: int) -> dict:
    sums = {"UTC_00": _week_sums(scored, field)}
    weeks = sorted(sums["UTC_00"])
    full = specificity.one_draw(sums, {week: 1 for week in weeks})
    if full is None:
        raise RuntimeError("map stream has no pairs")
    point = full["means"]["UTC_00"]
    direct = _arm_summary(scored, field)["paired_effect"]
    if abs(direct - point) > 1e-9:
        raise RuntimeError("map week-weighted mean does not match the pair mean")
    drawn = specificity.bootstrap(sums, draws=K.BOOT_DRAWS, seed=seed)
    reps = [item["means"]["UTC_00"] for item in drawn["valid"]]
    fraction = len(reps) / drawn["draws"]
    lo, hi = multiplicity.marginal_percentile(reps) if reps else (None, None)
    p_value = multiplicity.bootstrap_p_value(point, reps) if reps else None
    return {
        "point": point,
        "marginal_lo": lo,
        "marginal_hi": hi,
        "bootstrap_p": p_value,
        "valid_draws": len(reps),
        "draws": drawn["draws"],
        "valid_fraction": fraction,
        "seed": seed,
        "interpretable": fraction >= BOOT_VALID_FRACTION_MIN and p_value is not None,
    }


def analyze_scored(scored_by_cell: dict, *, counts_by_cell: dict) -> dict:
    """`scored_by_cell` values are lists of scored pair rows. No bar loader."""
    if set(scored_by_cell) != set(K.CLOCK_CELLS):
        raise ValueError("the four clock cells are required")
    points, boot = _family_intervals(scored_by_cell)
    clock_ok = boot["valid_fraction"] >= BOOT_VALID_FRACTION_MIN
    sim = multiplicity.simultaneous_max_t(points, boot["mean_reps"]) if clock_ok else {}
    foundation = {}
    for name in K.CLOCK_CELLS:
        arm = _arm_summary(scored_by_cell[name], "resolution")
        if clock_ok:
            marginal_lo, marginal_hi = multiplicity.marginal_percentile(
                [draw[name] for draw in boot["mean_reps"]]
            )
            sim_lo = sim[name]["sim_lo"]
            sim_hi = sim[name]["sim_hi"]
            se = sim[name]["se"]
            critical = sim[name]["critical"]
        else:
            marginal_lo = marginal_hi = sim_lo = sim_hi = se = critical = None
        passed = bool(
            clock_ok and routing.clears_simultaneous(
                {"point": points[name], "sim_lo": sim_lo, "sim_hi": sim_hi},
                K.PRACTICAL_SCALE,
            )
        )
        counts = counts_by_cell[name]
        foundation[name] = {
            "real_resolution_rate": arm["real"],
            "pseudo_resolution_rate": arm["pseudo"],
            "paired_delta": arm["paired_effect"],
            "n_pairs": arm["n_pairs"],
            "iso_weeks": counts["paired_iso_weeks"],
            "information_status": counts["information_status"],
            "marginal_lo": marginal_lo,
            "marginal_hi": marginal_hi,
            "simultaneous_lo": sim_lo,
            "simultaneous_hi": sim_hi,
            "bootstrap_sd": se,
            "max_stat_critical": critical,
            "practical_scale": K.PRACTICAL_SCALE,
            "passes_family_rule": passed,
            "both_barriers_on_first_hit_real": sum(row["both_barriers_real"] for row in scored_by_cell[name]),
            "both_barriers_on_first_hit_pseudo": sum(row["both_barriers_pseudo"] for row in scored_by_cell[name]),
        }
    contrasts = {}
    if clock_ok:
        sim_c = multiplicity.simultaneous_max_t(boot["contrast_points"], boot["contrast_reps"])
    else:
        sim_c = {}
    for name in ("UTC_08", "UTC_12", "UTC_16"):
        if clock_ok:
            reps = [draw[name] for draw in boot["contrast_reps"]]
            lo, hi = multiplicity.marginal_percentile(reps)
            item = {
                "point": boot["contrast_points"][name],
                "marginal_lo": lo,
                "marginal_hi": hi,
                "simultaneous_lo": sim_c[name]["sim_lo"],
                "simultaneous_hi": sim_c[name]["sim_hi"],
                "bootstrap_sd": sim_c[name]["se"],
                "max_stat_critical": sim_c[name]["critical"],
                "practical_scale": K.SPECIFICITY_SCALE,
            }
            item["passes_family_rule"] = routing.clears_simultaneous(
                {"point": item["point"], "sim_lo": item["simultaneous_lo"], "sim_hi": item["simultaneous_hi"]},
                K.SPECIFICITY_SCALE,
            )
        else:
            item = {
                "point": boot["contrast_points"][name],
                "marginal_lo": None,
                "marginal_hi": None,
                "simultaneous_lo": None,
                "simultaneous_hi": None,
                "practical_scale": K.SPECIFICITY_SCALE,
                "passes_family_rule": False,
            }
        contrasts[name] = item
    seeds = {
        "DIRECTION_EXTENSION_FIRST": K.BOOT_SEED_DIRECTION,
        "OUTSIDE_OCCUPANCY": K.BOOT_SEED_OUTSIDE,
        "OUTWARD_EXCURSION": K.BOOT_SEED_EXCURSION,
    }
    primary = scored_by_cell[K.PRIMARY_CELL]
    streams = {
        name: _map_stream(primary, MAP_FIELDS[name], seeds[name])
        for name in K.NONFOUNDATION_ORDER
    }
    interpretable = {name: stream for name, stream in streams.items() if stream["interpretable"]}
    if len(interpretable) == len(K.NONFOUNDATION_ORDER):
        adjusted = multiplicity.holm_adjusted({name: stream["bootstrap_p"] for name, stream in interpretable.items()})
    else:
        adjusted = {}
    map_rows = {}
    route_rows = {}
    for name in K.NONFOUNDATION_ORDER:
        arm = _arm_summary(primary, MAP_FIELDS[name])
        stream = streams[name]
        holm_p = adjusted.get(name)
        passes = bool(
            holm_p is not None
            and holm_p < K.FAMILY_ALPHA
            and abs(stream["point"]) >= K.NONFOUNDATION_SCALE[name]
        )
        map_rows[name] = {
            "role": K.NONFOUNDATION_ROLE[name],
            "real": arm["real"],
            "pseudo": arm["pseudo"],
            "paired_effect": arm["paired_effect"],
            "n_pairs": arm["n_pairs"],
            "marginal_lo": stream["marginal_lo"],
            "marginal_hi": stream["marginal_hi"],
            "bootstrap_p": stream["bootstrap_p"],
            "holm_p": holm_p,
            "practical_scale": K.NONFOUNDATION_SCALE[name],
            "seed": stream["seed"],
            "valid_fraction": stream["valid_fraction"],
            "passes_family_rule": passes,
        }
        if holm_p is not None:
            route_rows[name] = {"point": stream["point"], "holm_p": holm_p}
    route_foundation = {}
    route_contrasts = {}
    if clock_ok:
        for name in K.CLOCK_CELLS:
            cell = foundation[name]
            route_foundation[name] = {
                "point": cell["paired_delta"],
                "sim_lo": cell["simultaneous_lo"],
                "sim_hi": cell["simultaneous_hi"],
            }
        for name in ("UTC_08", "UTC_12", "UTC_16"):
            cell = contrasts[name]
            route_contrasts[name] = {
                "point": cell["point"],
                "sim_lo": cell["simultaneous_lo"],
                "sim_hi": cell["simultaneous_hi"],
            }
        decided = routing.decide(
            {name: foundation[name]["information_status"] for name in K.CLOCK_CELLS},
            route_foundation,
            route_contrasts,
            route_rows,
        )
    else:
        decided = {
            "route": "INFORMATION_LIMITED",
            "opening_wording_allowed": False,
            "hour_adopted": None,
            "nonfoundation_candidates": [],
            "object_name": K.OBJECT_NAME,
            "clock_inference": "VALID_FRACTION_BELOW_0.9",
        }
    if clock_ok and len(route_rows) != len(K.NONFOUNDATION_ORDER) and decided["route"] in (
        "NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE",
        "NONFOUNDATION_MAP_CANDIDATE_ON_UTC_00",
    ):
        decided = {
            **decided,
            "route": "INFORMATION_LIMITED",
            "nonfoundation_candidates": [],
            "clock_inference": "MAP_STREAM_NOT_INTERPRETABLE",
        }
    route = decided["route"]
    return {
        "foundation": foundation,
        "contrasts": contrasts,
        "foundation_bootstrap": {
            "seed": boot["seed"],
            "draws": boot["draws"],
            "valid_draws": boot["valid_draws"],
            "invalid_draws": boot["invalid_draws"],
            "valid_fraction": boot["valid_fraction"],
            "procedure": "SINGLE_STEP_STANDARDIZED_MAX_STAT",
            "a2_family_name": K.FOUNDATION_CELL_FAMILY,
            "standardization": "one bootstrap SD per statistic; not replicate-specific bootstrap-t",
            "clock_inference_used": clock_ok,
        },
        "contrast_procedure": {
            "procedure": "SINGLE_STEP_STANDARDIZED_MAX_STAT",
            "a2_family_name": K.CLOCK_CONTRAST_FAMILY,
            "standardization": "one bootstrap SD per statistic; not replicate-specific bootstrap-t",
            "family_is_separate_from_cell_effects": True,
        },
        "nonfoundation_map": map_rows,
        "stability": {name: _stability(rows) for name, rows in scored_by_cell.items()},
        "route": route,
        "opening_wording_allowed": False,
        "hour_adopted": None,
        "nonfoundation_candidates": decided.get("nonfoundation_candidates", []),
        "route_sentence": ROUTE_SENTENCE[route],
        "atlas_state": atlas_state_for_route(route),
        "claim": claim_for_route(route),
        "claim_ceiling": K.CLAIM_CEILING,
    }


def analyze_bars(bars) -> dict:
    high = np.asarray(bars.high, dtype=np.float64)
    low = np.asarray(bars.low, dtype=np.float64)
    close = np.asarray(bars.close, dtype=np.float64)
    collected = collect_pairs(high, low, close, int(bars.t0))
    scored = {name: score_pairs(high, low, collected[name]["pairs"]) for name in K.CLOCK_CELLS}
    inferred = analyze_scored(
        scored,
        counts_by_cell={name: collected[name]["counts"] for name in K.CLOCK_CELLS},
    )
    return inferred


def render_markdown(payload: dict) -> str:
    lines = [
        "# OPENING_RANGE_OBJECT_V1 — one historical outcome read",
        "",
        payload["route_sentence"],
        "",
        f"- Route: `{payload['route']}`",
        f"- opening_wording_allowed: `{str(payload['opening_wording_allowed']).lower()}`",
        f"- hour_adopted: `{payload['hour_adopted']}`",
        f"- Claim: `{payload['claim']}`",
        f"- Claim ceiling: `{payload['claim_ceiling']}`",
        f"- Atlas state name for this read: `{payload['atlas_state']}`",
        f"- outcome_read: `{str(payload['outcome_read']).lower()}`",
        f"- Read at: `{payload['outcome_read_at']}`",
        f"- Surface: `{payload['surface']}` `{payload['event_start']}` inclusive to `{payload['surface_end_exclusive']}` exclusive",
        f"- Evaluator commit: `{payload['pre_outcome_evaluator_commit']}`",
        f"- Code digest: `{payload['code_digest']}`",
        f"- Touch-time handling: `{payload['touch_time']['handling']}`",
        "",
        "Touch time was not used to rematch, stratify, or add a sensitivity.",
        "",
        "## Foundation",
        "",
        "Family `FOUNDATION_CELL_EFFECTS`. Simultaneous intervals are single-step standardized max-stat intervals from the joint week bootstrap. Marginal intervals are percentile intervals.",
        "",
    ]
    for name in K.CLOCK_CELLS:
        cell = payload["foundation"][name]
        lines.append(
            f"- {name}: real {cell['real_resolution_rate']}, pseudo {cell['pseudo_resolution_rate']}, "
            f"delta {cell['paired_delta']}, N {cell['n_pairs']}, weeks {cell['iso_weeks']}, "
            f"marginal [{cell['marginal_lo']}, {cell['marginal_hi']}], "
            f"simultaneous [{cell['simultaneous_lo']}, {cell['simultaneous_hi']}], "
            f"passes `{str(cell['passes_family_rule']).lower()}`"
        )
    lines.extend(["", "## Clock contrasts", ""])
    for name in ("UTC_08", "UTC_12", "UTC_16"):
        cell = payload["contrasts"][name]
        lines.append(
            f"- delta UTC_00 minus {name}: {cell['point']}, "
            f"marginal [{cell['marginal_lo']}, {cell['marginal_hi']}], "
            f"simultaneous [{cell['simultaneous_lo']}, {cell['simultaneous_hi']}], "
            f"passes `{str(cell['passes_family_rule']).lower()}`"
        )
    lines.extend(["", "## Non-foundation map on UTC_00", ""])
    for name in K.NONFOUNDATION_ORDER:
        cell = payload["nonfoundation_map"][name]
        lines.append(
            f"- {name} ({cell['role']}): real {cell['real']}, pseudo {cell['pseudo']}, "
            f"delta {cell['paired_effect']}, N {cell['n_pairs']}, "
            f"marginal [{cell['marginal_lo']}, {cell['marginal_hi']}], "
            f"bootstrap p {cell['bootstrap_p']}, Holm p {cell['holm_p']}, "
            f"scale {cell['practical_scale']}, passes `{str(cell['passes_family_rule']).lower()}`"
        )
    listed = payload["nonfoundation_candidates"]
    lines.append(f"- candidates, declaration order: `{json.dumps(listed)}`")
    lines.extend(["", "## Stability", "", "Calendar year needs 30 paired days. Real-interaction side needs 100. A slice is not a winner.", ""])
    for name in K.CLOCK_CELLS:
        lines.append(f"- {name}: `{json.dumps(payload['stability'][name], sort_keys=True)}`")
    lines.extend([
        "",
        "No resolution clock, realized-volatility transition, traverse endpoint, extra hour, extra horizon, or extra barrier fraction was computed.",
        "No 2025/2026 object, no E1 window, no product sample, no prospective sample.",
        "",
    ])
    return "\n".join(lines)


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _assert_frozen_counts(counts: dict) -> None:
    census_payload = json.loads(CENSUS_PATH.read_text())
    for name in K.CLOCK_CELLS:
        got = counts[name]
        expected = census_payload["cells"][name]["support"]["paired_outcome_eligible"]
        if got != expected:
            raise SystemExit(f"PAIR_COUNT_DRIFT_STOP_BEFORE_Y {name} {got} {expected}")
    if census_payload["timing_handling"] != "PUBLISH_AUDIT_NO_CORRECTION":
        raise SystemExit("TOUCH_HANDLING_NOT_THE_FROZEN_BRANCH")
    if census_payload["outcome_read"] is not False:
        raise SystemExit("CENSUS_ALREADY_READ_AN_OUTCOME")


def _touch_block(census_payload: dict) -> dict:
    primary = census_payload["cells"][K.PRIMARY_CELL]["touch_time"]
    return {
        "handling": census_payload["timing_handling"],
        "source": "docs/research/OPENING_RANGE_OBJECT_V1_AMENDMENT_A1_CENSUS.json",
        "rematch": False,
        "stratified": False,
        "nearby_sensitivity": False,
        "primary_abs_delta_p50": primary["abs_paired_delta_min"]["p50"],
        "primary_far_240m_share": primary["far_240m_share"],
        "primary_timing_imbalance_material": census_payload["primary_timing_imbalance_material"],
    }


def write_result(payload: dict) -> None:
    if RESULT_JSON.exists() or RESULT_MD.exists():
        raise SystemExit(REFUSAL_RERUN)
    RESULT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RESULT_MD.write_text(render_markdown(payload), encoding="utf-8")


def main() -> int:
    if RESULT_JSON.exists() or RESULT_MD.exists():
        raise SystemExit(REFUSAL_RERUN)
    manifest = json.loads(MANIFEST_PATH.read_text())
    digest = code_digest()
    if digest["code_digest"] != manifest["code_digest"]:
        raise SystemExit("CODE_DIGEST_DOES_NOT_MATCH_PRE_OUTCOME_MANIFEST")
    from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

    bars = load_discovery_bars()
    if int(bars.times[0]) < census.EVENT_START_MS or int(bars.times[-1]) >= census.SURFACE_END_MS:
        raise SystemExit("PANEL_LEAVES_THE_FROZEN_SURFACE")
    high = np.asarray(bars.high, dtype=np.float64)
    low = np.asarray(bars.low, dtype=np.float64)
    close = np.asarray(bars.close, dtype=np.float64)
    collected = collect_pairs(high, low, close, int(bars.t0))
    _assert_frozen_counts({name: collected[name]["counts"]["paired_outcome_eligible"] for name in K.CLOCK_CELLS})
    census_payload = json.loads(CENSUS_PATH.read_text())
    scored = {name: score_pairs(high, low, collected[name]["pairs"]) for name in K.CLOCK_CELLS}
    inferred = analyze_scored(
        scored,
        counts_by_cell={name: collected[name]["counts"] for name in K.CLOCK_CELLS},
    )
    payload = {
        "unit": K.UNIT,
        "object_name": K.OBJECT_NAME,
        "outcome_read": True,
        "y_known": True,
        "outcome_read_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "surface": K.SURFACE_ID,
        "event_start": K.EVENT_START,
        "surface_end_exclusive": K.SURFACE_END,
        "panel_t0_ms": int(bars.t0),
        "panel_bars": int(bars.n),
        "original_design_commit": K.ORIGINAL_DESIGN_COMMIT,
        "original_design_sha256": K.ORIGINAL_DESIGN_SHA256,
        "amendment_a1_commit": "fb57fc8df8960e336b6dd779a339ec390b74e76b",
        "amendment_a1_sha256": "230b8818f154ad3b26450e25baab0fe368360c723c6ccabc86005cab6903803a",
        "amendment_a2_commit": "e4963fe8e8e7b6ba5ce677ec2fb16d9d3ba6b5c0",
        "amendment_a2_sha256": "64ae661cd2dd8815085817d1cc7c8062cb822328a74b3caf3e5f9c80c0aa7d40",
        "pre_outcome_evaluator_commit": _git_head(),
        "code_digest": digest["code_digest"],
        "seeds": {
            "joint": K.BOOT_SEED_JOINT,
            "direction": K.BOOT_SEED_DIRECTION,
            "outside_occupancy": K.BOOT_SEED_OUTSIDE,
            "outward_excursion": K.BOOT_SEED_EXCURSION,
            "draws": K.BOOT_DRAWS,
        },
        "touch_time": _touch_block(census_payload),
        **inferred,
    }
    write_result(payload)
    print(json.dumps({
        "route": payload["route"],
        "claim": payload["claim"],
        "opening_wording_allowed": payload["opening_wording_allowed"],
        "code_digest": payload["code_digest"],
        "pre_outcome_evaluator_commit": payload["pre_outcome_evaluator_commit"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
