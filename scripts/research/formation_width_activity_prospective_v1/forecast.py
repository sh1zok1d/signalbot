"""Outcome-blind information compiler for the prospective formation-width claim.

Uses the published discovery dependence number and the confirmation forecast
function. Does not load a market tape and does not score a forward endpoint.
Historical point estimates are stored as context and are not inputs.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist

from scripts.research.formation_width_activity_confirmation_v1.support import information_forecast

from . import constants as K

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_DESIGN.md"
SPEC_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_SPEC.json"
SUPPORT_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_SUPPORT.md"
UTC = dt.timezone.utc
NORMAL = NormalDist()
START = dt.datetime(2026, 10, 10, tzinfo=UTC)


def balanced_week_sizes(n: int) -> list[int]:
    """Equal ISO-week sizes summing to n, using the discovery week ratio."""
    if n < 1:
        raise RuntimeError("forecast sample is empty")
    n_weeks = max(1, round(n * K.DISCOVERY_ISO_WEEKS / K.DISCOVERY_ANALYSIS_N))
    base, extra = divmod(n, n_weeks)
    if base < 1:
        raise RuntimeError("week size fell below one day")
    sizes = [base + 1] * extra + [base] * (n_weeks - extra)
    if sum(sizes) != n:
        raise RuntimeError("week sizes do not sum to the forecast N")
    return sizes


def forecast_row(n: int) -> dict:
    sizes = balanced_week_sizes(n)
    info = information_forecast(sizes, K.PHI)
    calendar_days = n * K.DISCOVERY_CALENDAR_DAYS / K.DISCOVERY_ANALYSIS_N
    expected = START + dt.timedelta(days=calendar_days)
    return {
        "raw_n": int(n),
        "iso_weeks": len(sizes),
        "week_size_min": min(sizes),
        "week_size_max": max(sizes),
        "effective_n": info["effective_n"],
        "fisher_se": info["fisher_se"],
        "mde80": info["minimum_detectable_association_80"],
        "single_look_power_at_reference": info["power_lower_bound_excludes_zero_at_practical_bar"],
        "expected_calendar_days": calendar_days,
        "expected_formation_date": expected.date().isoformat(),
    }


def cumulative_alpha(information_time: float) -> float:
    if information_time < 0.0 or information_time > 1.0:
        raise RuntimeError("information time is outside [0, 1]")
    return K.ALPHA * (information_time ** K.SPENDING_RHO)


def sequential_power(se: float, incremental_alpha: float) -> float:
    """Normal power that the lower bound clears 0 when the truth is the reference.

    The critical value is the normal quantile of the spent increment. This is a
    forecast of the bootstrap percentile test. It is not the test.
    """
    if not math.isfinite(se) or se <= 0.0 or not 0.0 < incremental_alpha < 1.0:
        return 0.0
    z = NORMAL.inv_cdf(1.0 - incremental_alpha)
    return float(1.0 - NORMAL.cdf(z - K.PRACTICAL_REFERENCE / se))


def _maturity_n(rows: dict[int, dict]) -> int:
    eligible = [n for n in K.ANNUAL_CANDIDATES if rows[n]["mde80"] <= K.PRACTICAL_REFERENCE]
    if not eligible:
        raise RuntimeError("no annual candidate reaches the reference MDE")
    return min(eligible)


def _terminal_n(rows: dict[int, dict], maturity: int) -> int:
    later = [n for n in K.ANNUAL_CANDIDATES if n > maturity]
    if not later:
        raise RuntimeError("no annual candidate sits after maturity")
    return min(later)


def _first_look(rows: dict[int, dict], terminal: int) -> int:
    ne_terminal = rows[terminal]["effective_n"]
    for n in K.ANNUAL_CANDIDATES:
        if n >= terminal:
            break
        information_time = rows[n]["effective_n"] / ne_terminal
        power = sequential_power(rows[n]["fisher_se"], cumulative_alpha(information_time))
        if power >= K.MIN_SEQUENTIAL_POWER:
            return n
    raise RuntimeError("no annual candidate is a meaningful first look")


def _admit_between(rows: dict[int, dict], first: int, terminal: int) -> list[int]:
    """Add an annual point only when its spent increment can still decide."""
    admitted = [first]
    ne_terminal = rows[terminal]["effective_n"]
    previous = cumulative_alpha(rows[first]["effective_n"] / ne_terminal)
    for n in K.ANNUAL_CANDIDATES:
        if n <= first or n >= terminal:
            continue
        information_time = rows[n]["effective_n"] / ne_terminal
        increment = cumulative_alpha(information_time) - previous
        power = sequential_power(rows[n]["fisher_se"], increment)
        if power < K.MIN_SEQUENTIAL_POWER:
            continue
        admitted.append(n)
        previous = cumulative_alpha(information_time)
    admitted.append(terminal)
    return admitted


def select_schedule(rows: dict[int, dict]) -> dict:
    """Choose checkpoints from the forecast only.

    The discovery point and the cross-venue point are not arguments.
    """
    maturity = _maturity_n(rows)
    terminal = _terminal_n(rows, maturity)
    first = _first_look(rows, terminal)
    admitted = _admit_between(rows, first, terminal)
    if maturity not in admitted:
        raise RuntimeError("maturity checkpoint was not admitted")
    return {
        "first_look_n": first,
        "maturity_n": maturity,
        "terminal_n": terminal,
        "admitted_n": admitted,
    }


def _annotate(rows: dict[int, dict], schedule: dict) -> list[dict]:
    terminal = schedule["terminal_n"]
    ne_terminal = rows[terminal]["effective_n"]
    previous = 0.0
    out = []
    for n in schedule["admitted_n"]:
        row = dict(rows[n])
        information_time = row["effective_n"] / ne_terminal
        cumulative = cumulative_alpha(information_time)
        increment = cumulative - previous
        if increment <= 0.0:
            raise RuntimeError("alpha increment is not positive")
        row.update({
            "information_time": information_time,
            "cumulative_alpha": cumulative,
            "incremental_alpha": increment,
            "quantile_lo": increment,
            "quantile_hi": 1.0 - increment,
            "sequential_power_lower_clears_zero": sequential_power(row["fisher_se"], increment),
            "role": _role(n, schedule),
            "magnitude_stop_allowed": n >= schedule["maturity_n"],
            "terminal": n == terminal,
        })
        previous = cumulative
        out.append(row)
    if abs(previous - K.ALPHA) > 1e-12:
        raise RuntimeError("spent alpha does not sum to the family alpha")
    return out


def _role(n: int, schedule: dict) -> str:
    if n == schedule["first_look_n"] and n == schedule["maturity_n"]:
        return "FIRST_LOOK_AND_MATURITY"
    if n == schedule["first_look_n"]:
        return "FIRST_LOOK"
    if n == schedule["terminal_n"]:
        return "TERMINAL"
    if n == schedule["maturity_n"]:
        return "MATURITY"
    return "INTERMEDIATE"


def decide(is_terminal: bool, magnitude_stop_allowed: bool, interpretable: bool,
           point: float, lower: float, upper: float) -> str:
    """Frozen route on one checkpoint. Inputs are numbers, not a market path."""
    if interpretable and lower > upper:
        interpretable = False
    if not interpretable:
        return K.ROUTE_INCONCLUSIVE if is_terminal else K.ACTION_CONTINUE
    reference = K.PRACTICAL_REFERENCE
    magnitude = point > 0.0 and lower >= reference
    positive = point > 0.0 and lower > 0.0
    below = upper < reference
    if magnitude:
        return K.ROUTE_MAGNITUDE
    if magnitude_stop_allowed and below:
        return K.ROUTE_NOT
    if is_terminal:
        return K.ROUTE_POSITIVE if positive else K.ROUTE_INCONCLUSIVE
    return K.ACTION_CONTINUE


def interim_label(interpretable: bool, point: float, lower: float, upper: float) -> str | None:
    """Description while accrual continues. Not a stop and not a route change."""
    if interpretable and lower <= upper and point > 0.0 and 0.0 < lower < K.PRACTICAL_REFERENCE and upper >= K.PRACTICAL_REFERENCE:
        return K.ROUTE_POSITIVE
    return None


def build_spec(design_sha256: str | None = None) -> dict:
    needed = set(K.ANNUAL_CANDIDATES) | set(K.REJECTED_FOR_REPORT)
    rows = {n: forecast_row(n) for n in sorted(needed)}
    schedule = select_schedule(rows)
    checkpoints = _annotate(rows, schedule)
    rejected = []
    for n in K.REJECTED_FOR_REPORT:
        row = dict(rows[n])
        row["admitted"] = n in schedule["admitted_n"]
        row["reason"] = _rejection_reason(row, schedule)
        rejected.append(row)
    return {
        "unit": K.UNIT,
        "mode": K.MODE,
        "outcome_read": False,
        "future_association_read": False,
        "accrued_analysis_n": 0,
        "status": "AWAITING_START",
        "prospective_start": K.PROSPECTIVE_START,
        "first_decision_time": K.FIRST_DECISION_TIME,
        "endpoint_window_not_read": K.ENDPOINT_WINDOW,
        "dataset_id": K.DATASET_ID,
        "venue": K.VENUE,
        "instrument": K.INSTRUMENT,
        "column": K.COLUMN,
        "exposure_class": K.EXPOSURE_CLASS,
        "practical_reference": K.PRACTICAL_REFERENCE,
        "design_sha256": design_sha256,
        "forecast_assumption": {
            "role": "FORECAST_ASSUMPTION",
            "not_the_inferential_engine": True,
            "model": "AR1_WITHIN_ISO_WEEK_USING_WIDTH_LAG_THEN_KISH",
            "phi": K.PHI,
            "phi_source": K.PHI_SOURCE,
            "discovery_analysis_n": K.DISCOVERY_ANALYSIS_N,
            "discovery_iso_weeks": K.DISCOVERY_ISO_WEEKS,
            "discovery_calendar_days": K.DISCOVERY_CALENDAR_DAYS,
            "phi_refit_on_forward_state": False,
        },
        "inference": {
            "method": "ISO_WEEK_BLOCK_BOOTSTRAP_AT_SPARSE_CHECKPOINTS",
            "spending_family": "KIM_DEMETS_POWER",
            "spending_exponent": K.SPENDING_RHO,
            "alpha_per_onesided_family": K.ALPHA,
            "families": ["LOWER_BOUND_ABOVE_ZERO", "UPPER_BOUND_BELOW_REFERENCE"],
            "validity": "UNION_BOUND_ON_POSITIVE_DEPENDENCE_OF_LOOKS",
            "always_valid_sequence": False,
            "draws": K.BOOT_DRAWS,
            "seed": K.BOOT_SEED,
            "seed_restarted_each_checkpoint": True,
            "min_finite_draw_fraction": K.MIN_VALID_FRACTION,
            "ranks_recomputed_inside_draw": True,
            "between_checkpoint_looks": False,
        },
        "schedule": schedule,
        "checkpoints": checkpoints,
        "rejected_candidates": rejected,
        "context_not_a_prior": {
            "discovery_point": K.DISCOVERY_POINT,
            "cross_venue_point": K.CROSS_VENUE_POINT,
            "cross_venue_route": K.CROSS_VENUE_ROUTE,
            "used_as_prior": False,
            "used_to_choose_checkpoints": False,
            "used_to_choose_alpha": False,
            "rounded_to_reference": False,
        },
        "lag_placebo": {
            "option": "A",
            "when": "ONCE_ON_THE_STOPPING_SAMPLE",
            "route_input": False,
            "min_pairs": K.LAG_MIN_PAIRS,
            "wording_constraint": "If the absolute lag point is at least the absolute primary point, the wording does not claim current-state specificity. The route name does not change.",
        },
        "stability": {
            "route_input": False,
            "min_n": K.STABILITY_MIN_N,
            "split": "FLOOR_N_OVER_2_IN_CALENDAR_ORDER",
            "opposite_signs_are_a_veto": False,
            "calendar_year_search": False,
        },
        "product_integration_candidate": False,
        "l3_authorized": False,
        "owner_go_required_for_first_checkpoint": True,
        "this_unit_scores_the_forward_endpoint": False,
    }


def _rejection_reason(row: dict, schedule: dict) -> str:
    if row["admitted"]:
        return "ADMITTED"
    if row["raw_n"] > schedule["terminal_n"]:
        return "AFTER_TERMINAL"
    if row["single_look_power_at_reference"] < K.MIN_SEQUENTIAL_POWER:
        return "SINGLE_LOOK_POWER_BELOW_MINIMUM"
    return "SEQUENTIAL_INCREMENT_POWER_BELOW_MINIMUM"


def render_support(spec: dict) -> str:
    lines = [
        "# FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1 support forecast",
        "",
        "`outcome_read = false`",
        "`future_association_read = false`",
        "`accrued_analysis_n = 0`",
        "`status = AWAITING_START`",
        "",
        "This file is the outcome-blind compiler output. It counts no forward bar and scores no forward association. The dependence model below is a forecast assumption. The inferential engine is the ISO-week block bootstrap at the frozen checkpoints.",
        "",
        f"Prospective start: `{spec['prospective_start']}`.",
        f"Dataset: `{spec['dataset_id']}`, {spec['venue']} {spec['instrument']}, column `{spec['column']}`.",
        f"Practical reference: `{spec['practical_reference']}`.",
        "",
        "## Forecast assumption",
        "",
        f"Phi `{spec['forecast_assumption']['phi']}` from `{spec['forecast_assumption']['phi_source']}`.",
        f"Discovery counts used only as rates: analysis N `{spec['forecast_assumption']['discovery_analysis_n']}`, ISO weeks `{spec['forecast_assumption']['discovery_iso_weeks']}`, calendar days `{spec['forecast_assumption']['discovery_calendar_days']}`.",
        "Model: AR(1) inside an ISO week, then Kish effective N, then the Fisher standard error. This is not refit on a forward state, and it is not the test.",
        "",
        "## Checkpoints",
        "",
        "| N | role | ISO weeks | effective N | SE | MDE80 | single-look power | information time | incremental alpha | sequential power | expected formation date |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in spec["checkpoints"]:
        lines.append(
            "| {raw_n} | {role} | {iso_weeks} | {effective_n:.4f} | {fisher_se:.6f} | {mde80:.6f} | "
            "{single_look_power_at_reference:.6f} | {information_time:.6f} | {incremental_alpha:.6f} | "
            "{sequential_power_lower_clears_zero:.6f} | {expected_formation_date} |".format(**row)
        )
    lines.extend([
        "",
        "## Rejected candidates",
        "",
        "| N | single-look power | MDE80 | reason |",
        "| --- | --- | --- | --- |",
    ])
    for row in spec["rejected_candidates"]:
        lines.append(
            "| {raw_n} | {single_look_power_at_reference:.6f} | {mde80:.6f} | {reason} |".format(**row)
        )
    lines.extend([
        "",
        "## Context, not a prior",
        "",
        f"Discovery point `{spec['context_not_a_prior']['discovery_point']}`.",
        f"Cross-venue point `{spec['context_not_a_prior']['cross_venue_point']}`.",
        f"Cross-venue route `{spec['context_not_a_prior']['cross_venue_route']}`.",
        "These numbers do not choose N, alpha, or the spending exponent.",
        "",
        f"Design SHA256: `{spec['design_sha256']}`.",
        "",
    ])
    return "\n".join(lines)


def design_sha256() -> str:
    return hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest()


def emit() -> dict:
    spec = build_spec(design_sha256())
    SPEC_PATH.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUPPORT_PATH.write_text(render_support(spec), encoding="utf-8")
    return spec


if __name__ == "__main__":
    emit()
