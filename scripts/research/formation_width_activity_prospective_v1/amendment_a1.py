"""Pre-outcome Amendment A1 for the prospective formation-width claim.

Repairs the sequential error budget before any forward score. The estimand,
the venue, and the prospective start stay as in the parent design. This module
does not load a market tape.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from statistics import NormalDist

from scripts.research.formation_width_activity_confirmation_v1.support import Z_POWER

from . import constants as K
from . import forecast

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_DESIGN.md"
PARENT_SPEC_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_SPEC.json"
AMENDMENT_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_AMENDMENT_A1.md"
SPEC_PATH = ROOT / "docs" / "research" / "FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_AMENDMENT_A1.json"

PARENT_HEAD = "6b178352e464fac7cc3c847448cb3bc9018ae6a4"
OVERALL_DECISIVE_ERROR_BUDGET = 0.05
LOWER_TAIL_BUDGET = 0.025
UPPER_TAIL_BUDGET = 0.025
SPENDING_EXPONENT = 1.0
MIN_SEQUENTIAL_POWER = 0.50
MIN_TAIL_DRAWS = 20
SEARCH_HORIZON_YEARS = 12
CANDIDATE_GRID = tuple(365 * year for year in range(1, SEARCH_HORIZON_YEARS + 1))
NORMAL = NormalDist()

PARENT_PER_SIDE_BUDGET = 0.05

assert LOWER_TAIL_BUDGET + UPPER_TAIL_BUDGET == OVERALL_DECISIVE_ERROR_BUDGET
assert LOWER_TAIL_BUDGET == UPPER_TAIL_BUDGET
assert SPENDING_EXPONENT == 1.0
assert MIN_SEQUENTIAL_POWER == 0.50
assert K.BOOT_DRAWS == 2000
assert MIN_TAIL_DRAWS / K.BOOT_DRAWS == 0.01
assert K.PROSPECTIVE_START == "2026-10-10T00:00:00Z"
assert K.PRACTICAL_REFERENCE == 0.10
assert PARENT_PER_SIDE_BUDGET != LOWER_TAIL_BUDGET


def min_increment() -> float:
    """Smallest tail probability the frozen bootstrap can resolve."""
    return MIN_TAIL_DRAWS / K.BOOT_DRAWS


def cumulative_side_alpha(information_time: float) -> float:
    """Kim–DeMets spend inside one tail. Exponent 1, budget 0.025."""
    if information_time < 0.0 or information_time > 1.0:
        raise RuntimeError("information time is outside [0, 1]")
    return LOWER_TAIL_BUDGET * (information_time ** SPENDING_EXPONENT)


def mde80_at_increment(se: float, incremental_alpha: float) -> float:
    """80% MDE of the normal test whose critical value is this look's increment.

    The parent MDE used the normal quantile of 0.05. This one uses the quantile
    of the alpha actually spent at the look.
    """
    if not 0.0 < incremental_alpha < 1.0:
        return float("inf")
    z = NORMAL.inv_cdf(1.0 - incremental_alpha)
    return (z + Z_POWER) * se


def _rows() -> dict[int, dict]:
    return {n: forecast.forecast_row(n) for n in CANDIDATE_GRID}


def _try_schedule(rows: dict[int, dict], terminal: int) -> list[int] | None:
    ne_terminal = rows[terminal]["effective_n"]
    floor = min_increment()
    first = None
    for n in CANDIDATE_GRID:
        if n >= terminal:
            break
        information_time = rows[n]["effective_n"] / ne_terminal
        increment = cumulative_side_alpha(information_time)
        power = forecast.sequential_power(rows[n]["fisher_se"], increment)
        if increment >= floor and power >= MIN_SEQUENTIAL_POWER:
            first = n
            break
    if first is None:
        return None
    admitted = [first]
    previous = cumulative_side_alpha(rows[first]["effective_n"] / ne_terminal)
    for n in CANDIDATE_GRID:
        if n <= first or n >= terminal:
            continue
        information_time = rows[n]["effective_n"] / ne_terminal
        increment = cumulative_side_alpha(information_time) - previous
        power = forecast.sequential_power(rows[n]["fisher_se"], increment)
        if increment < floor or power < MIN_SEQUENTIAL_POWER:
            continue
        admitted.append(n)
        previous = cumulative_side_alpha(information_time)
    if LOWER_TAIL_BUDGET - previous < floor:
        return None
    admitted.append(terminal)
    return admitted


def _annotate_attempt(rows: dict[int, dict], admitted: list[int]) -> list[dict]:
    terminal = admitted[-1]
    ne_terminal = rows[terminal]["effective_n"]
    previous = 0.0
    out = []
    for n in admitted:
        information_time = rows[n]["effective_n"] / ne_terminal
        cumulative = cumulative_side_alpha(information_time)
        increment = cumulative - previous
        se = rows[n]["fisher_se"]
        out.append({
            "raw_n": n,
            "increment": increment,
            "mde80": mde80_at_increment(se, increment),
            "row": rows[n],
            "information_time": information_time,
            "cumulative": cumulative,
        })
        previous = cumulative
    return out


def select_schedule(rows: dict[int, dict]) -> dict:
    """Earliest legal terminal inside the frozen annual grid.

    Historical point estimates are not arguments.
    """
    for terminal in CANDIDATE_GRID:
        admitted = _try_schedule(rows, terminal)
        if admitted is None:
            continue
        detail = _annotate_attempt(rows, admitted)
        mature = [item["raw_n"] for item in detail if item["mde80"] <= K.PRACTICAL_REFERENCE]
        if not mature:
            continue
        return {
            "first_look_n": admitted[0],
            "maturity_n": mature[0],
            "terminal_n": terminal,
            "admitted_n": admitted,
        }
    raise RuntimeError("no finite terminal inside the frozen search horizon")


def _role(n: int, schedule: dict) -> str:
    roles = []
    if n == schedule["first_look_n"]:
        roles.append("FIRST_LOOK")
    if n == schedule["maturity_n"]:
        roles.append("MATURITY")
    if n == schedule["terminal_n"]:
        roles.append("TERMINAL")
    return "_AND_".join(roles)


def _checkpoints(rows: dict[int, dict], schedule: dict) -> list[dict]:
    terminal = schedule["terminal_n"]
    ne_terminal = rows[terminal]["effective_n"]
    previous = 0.0
    out = []
    for n in schedule["admitted_n"]:
        row = rows[n]
        information_time = row["effective_n"] / ne_terminal
        cumulative = cumulative_side_alpha(information_time)
        increment = cumulative - previous
        if increment <= 0.0:
            raise RuntimeError("alpha increment is not positive")
        se = row["fisher_se"]
        out.append({
            "raw_n": n,
            "role": _role(n, schedule),
            "iso_weeks": row["iso_weeks"],
            "effective_n": row["effective_n"],
            "fisher_se": se,
            "expected_calendar_days": row["expected_calendar_days"],
            "expected_formation_date": row["expected_formation_date"],
            "information_time": information_time,
            "lower_tail_spend": {"cumulative": cumulative, "incremental": increment},
            "upper_tail_spend": {"cumulative": cumulative, "incremental": increment},
            "lower_quantile": increment,
            "upper_quantile": 1.0 - increment,
            "mde80": mde80_at_increment(se, increment),
            "sequential_power_at_reference": forecast.sequential_power(se, increment),
            "magnitude_stop_allowed": n >= schedule["maturity_n"],
            "terminal": n == terminal,
        })
        previous = cumulative
    if abs(previous - LOWER_TAIL_BUDGET) > 1e-12:
        raise RuntimeError("lower-tail spend does not sum to 0.025")
    upper = sum(item["upper_tail_spend"]["incremental"] for item in out)
    if abs(upper - UPPER_TAIL_BUDGET) > 1e-12:
        raise RuntimeError("upper-tail spend does not sum to 0.025")
    return out


def _would_be_increment(rows: dict[int, dict], schedule: dict, n: int) -> float:
    """Alpha this candidate would spend given the looks already admitted before it."""
    terminal = schedule["terminal_n"]
    ne_terminal = rows[terminal]["effective_n"]
    previous = 0.0
    for admitted in schedule["admitted_n"]:
        if admitted >= n:
            break
        previous = cumulative_side_alpha(rows[admitted]["effective_n"] / ne_terminal)
    information_time = rows[n]["effective_n"] / ne_terminal
    return cumulative_side_alpha(information_time) - previous


def _candidate_table(rows: dict[int, dict], schedule: dict) -> list[dict]:
    terminal = schedule["terminal_n"]
    admitted = set(schedule["admitted_n"])
    table = []
    for n in CANDIDATE_GRID:
        if n > terminal:
            reason = "AFTER_TERMINAL"
        elif n in admitted:
            reason = "ADMITTED"
        else:
            increment = _would_be_increment(rows, schedule, n)
            power = forecast.sequential_power(rows[n]["fisher_se"], increment)
            if increment < min_increment():
                reason = "INCREMENT_BELOW_BOOTSTRAP_FLOOR"
            elif power < MIN_SEQUENTIAL_POWER:
                reason = "SEQUENTIAL_POWER_BELOW_MINIMUM"
            else:
                reason = "NOT_THE_EARLIEST_LEGAL_TERMINAL"
        table.append({
            "raw_n": n,
            "reason": reason,
            "effective_n": rows[n]["effective_n"],
            "fisher_se": rows[n]["fisher_se"],
            "expected_formation_date": rows[n]["expected_formation_date"],
        })
    return table


def build_spec(amendment_sha256: str | None = None) -> dict:
    rows = _rows()
    schedule = select_schedule(rows)
    checkpoints = _checkpoints(rows, schedule)
    return {
        "unit": K.UNIT,
        "amendment": "A1",
        "active_contract": True,
        "parent_design_sha256": hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest(),
        "parent_head": PARENT_HEAD,
        "parent_spec": "docs/research/FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1_SPEC.json",
        "parent_spec_role": "SUPERSEDED_ERROR_BUDGET",
        "amendment_sha256": amendment_sha256,
        "outcome_read": False,
        "future_association_read": False,
        "accrued_analysis_n": 0,
        "status": "AWAITING_START",
        "prospective_start": K.PROSPECTIVE_START,
        "dataset_id": K.DATASET_ID,
        "venue": K.VENUE,
        "instrument": K.INSTRUMENT,
        "column": K.COLUMN,
        "practical_reference": K.PRACTICAL_REFERENCE,
        "overall_decisive_error_budget": OVERALL_DECISIVE_ERROR_BUDGET,
        "lower_tail_budget": LOWER_TAIL_BUDGET,
        "upper_tail_budget": UPPER_TAIL_BUDGET,
        "spending_family": "KIM_DEMETS_POWER",
        "spending_exponent": SPENDING_EXPONENT,
        "spending_formula": "A(t)=0.025*t",
        "positive_relation_option": "A",
        "positive_relation_uses_extra_family": False,
        "positive_relation_object": "SAME_LOWER_TAIL_BOUND",
        "min_sequential_power": MIN_SEQUENTIAL_POWER,
        "min_sequential_power_role": "MINIMUM_INFORMATION_THRESHOLD",
        "min_tail_draws": MIN_TAIL_DRAWS,
        "min_incremental_alpha": min_increment(),
        "search_horizon_years": SEARCH_HORIZON_YEARS,
        "candidate_grid": list(CANDIDATE_GRID),
        "bootstrap_draws": K.BOOT_DRAWS,
        "bootstrap_seed": K.BOOT_SEED,
        "seed_restarted_each_checkpoint": True,
        "forecast_assumption": {
            "role": "FORECAST_ASSUMPTION",
            "model": "AR1_WITHIN_ISO_WEEK_USING_WIDTH_LAG_THEN_KISH",
            "phi": K.PHI,
            "phi_source": K.PHI_SOURCE,
            "discovery_analysis_n": K.DISCOVERY_ANALYSIS_N,
            "discovery_iso_weeks": K.DISCOVERY_ISO_WEEKS,
            "discovery_calendar_days": K.DISCOVERY_CALENDAR_DAYS,
        },
        "schedule": schedule,
        "checkpoints": checkpoints,
        "candidate_table": _candidate_table(rows, schedule),
        "context_not_a_prior": {
            "discovery_point": K.DISCOVERY_POINT,
            "cross_venue_point": K.CROSS_VENUE_POINT,
            "cross_venue_route": K.CROSS_VENUE_ROUTE,
            "used_as_prior": False,
            "used_to_choose_checkpoints": False,
            "used_to_choose_alpha": False,
        },
        "lag_placebo_route_input": False,
        "stability_route_input": False,
        "product_integration_candidate": False,
        "l3_authorized": False,
        "owner_go_required_for_first_checkpoint": True,
        "this_unit_scores_the_forward_endpoint": False,
    }


def require_active_contract(spec: dict) -> None:
    """Reject the parent per-side budget of 0.05 as a current contract."""
    if spec.get("active_contract") is not True:
        raise RuntimeError("parent per-side budget is not the active contract")
    if spec.get("inference", {}).get("alpha_per_onesided_family") == PARENT_PER_SIDE_BUDGET:
        raise RuntimeError("parent per-side budget is not the active contract")
    if spec.get("lower_tail_budget") != LOWER_TAIL_BUDGET:
        raise RuntimeError("parent per-side budget is not the active contract")
    if spec.get("upper_tail_budget") != UPPER_TAIL_BUDGET:
        raise RuntimeError("parent per-side budget is not the active contract")
    if spec.get("overall_decisive_error_budget") != OVERALL_DECISIVE_ERROR_BUDGET:
        raise RuntimeError("parent per-side budget is not the active contract")
    lower = sum(item["lower_tail_spend"]["incremental"] for item in spec["checkpoints"])
    upper = sum(item["upper_tail_spend"]["incremental"] for item in spec["checkpoints"])
    if abs(lower - LOWER_TAIL_BUDGET) > 1e-12 or abs(upper - UPPER_TAIL_BUDGET) > 1e-12:
        raise RuntimeError("parent per-side budget is not the active contract")


def load_active_spec() -> dict:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    require_active_contract(spec)
    return spec


def state_before_first_look(analysis_n: int, first_look_n: int) -> str:
    if analysis_n < first_look_n:
        return K.ROUTE_IMMATURE
    raise RuntimeError("analysis N has reached a formal checkpoint")


def decide(is_terminal: bool, magnitude_stop_allowed: bool, interpretable: bool,
           point: float, lower: float, upper: float) -> str:
    """Same route order as the parent. L and U come from the A1 tails.

    The lower bound is one object. Comparing it with 0 and with +0.10 does
    not open a third alpha family.
    """
    return forecast.decide(is_terminal, magnitude_stop_allowed, interpretable, point, lower, upper)


def amendment_sha256() -> str:
    return hashlib.sha256(AMENDMENT_PATH.read_bytes()).hexdigest()


def emit() -> dict:
    spec = build_spec(amendment_sha256())
    SPEC_PATH.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return spec


if __name__ == "__main__":
    emit()
