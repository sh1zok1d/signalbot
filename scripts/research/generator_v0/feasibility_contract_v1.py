"""GV0R03 generator feasibility contract, V1 mapping.

The outcome-blind planning object for a shortlisted candidate, mapped to
HYPOTHESIS_EVALUATION_CONTRACT_V1. It extends the V0 planning object with the
V1 declarations and copies them into a GV0R02_SCHEMA_V1 compiler proposal.

Like V0, this layer checks shape only. The V1 compiler
(gv0r02_feasibility_compiler_v1) stays the single adjudicator of the V1
definition rules (claim type versus endpoint, nuisance baseline, practical
bar, regime consistency, time-disjoint replication, stopping rule, protected
window). Nothing here scores feasibility or reads market outcomes.

Unchanged by this module:
- the V0 planning contract (feasibility_contract.py), which keeps emitting
  GV0R02_SCHEMA_V0 proposals;
- the GENERATOR_CONTRACT_V02 card and the frozen CANDIDATE_SCHEMA. The V1
  fields are design-freeze decisions taken when a shortlisted card becomes a
  planning object; the generator card does not emit them.

The planning object also carries its rung on the complexity ladder
(COMPLEXITY_CLASS, COMPONENTS; see complexity.py). Interaction and composite
claims must keep every component's main effect in the nuisance baseline.
"""
from __future__ import annotations

import datetime as dt

from . import complexity
from . import feasibility_contract as v0
from .context import ContractError

CONTRACT_VERSION = "GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V1"
EVALUATION_CONTRACT = "HYPOTHESIS_EVALUATION_CONTRACT_V1"
COMPILER_SCHEMA_VERSION = "GV0R02_SCHEMA_V1"
COMPILER_POLICY_VERSION = "GV0R02_POLICY_V1"

CLAIM_TYPES = {"CONTEXT_DESCRIPTIVE", "INCREMENTAL"}
TARGET_CLASSES = {"UNCONDITIONAL", "CONDITIONAL"}
PRACTICAL_BAR_BASES = {"COSTS", "PRODUCT_RELEVANCE"}
REPLICATION_KINDS = {"HISTORICAL", "PROSPECTIVE"}
ROLE_KEYS = ("REGIME_VARIABLES", "MECHANISM_VARIABLES", "NUISANCE_BASELINE_VARIABLES")
MAX_PRIMARY_CELLS = 3

# Historical surfaces must lie inside an era whose frozen V0 role allows that use.
ERA_BOUNDS = {
    "BINANCE_2020_2024": (dt.date(2020, 1, 1), dt.date(2025, 1, 1)),
    "BITMEX_2016_2019": (dt.date(2016, 1, 1), dt.date(2020, 1, 1)),
}
DISCOVERY_ERAS = {e for e, r in v0.ERA_ROLES.items() if r == "DISCOVERY"}
REPLICATION_ERAS = {e for e, r in v0.ERA_ROLES.items() if r == "HISTORICAL_REPLICATION_CANDIDATE"}

V1_FIELDS = (
    "CLAIM_TYPE",
    "TARGET_CLASS",
    "VARIABLE_ROLES",
    "INTRADAY",
    "PRIMARY_CELLS",
    "PRACTICAL_BAR_BASIS",
    "DISCOVERY_SURFACE",
    "REPLICATION_SURFACE",
    "EPOCHS",
)
OPTIONAL_V1_FIELDS = ("NUISANCE_EXCLUSIONS", "NUISANCE_DIAGNOSTIC_PLANNED")
# Complexity ladder (complexity.py). Not compiler fields; carried for provenance.
LADDER_FIELDS = ("COMPLEXITY_CLASS", "COMPONENTS")
REQUIRED_FIELDS = v0.REQUIRED_FIELDS + V1_FIELDS + LADDER_FIELDS

# Downstream code may not rewrite these either: they are the twin preregistration's design.
SEALED_FIELDS = v0.SEALED_FIELDS + V1_FIELDS + OPTIONAL_V1_FIELDS + LADDER_FIELDS


def _reject(field: str, reason: str) -> None:
    raise ContractError(f"{field}: {reason}")


def _text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _pos_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _month_date(field: str, value) -> dt.date:
    try:
        d = dt.date.fromisoformat(str(value))
    except ValueError:
        _reject(field, "dates are ISO YYYY-MM-DD")
    if d.day != 1:
        _reject(field, "surfaces start and end on a month boundary (day 01, end exclusive)")
    return d


def _surface_interval(field: str, surface) -> tuple[dt.date, dt.date]:
    if not isinstance(surface, dict) or not _text(surface.get("ID")):
        _reject(field, "needs ID, START and END")
    start = _month_date(field, surface.get("START"))
    end = _month_date(field, surface.get("END"))
    if start >= end:
        _reject(field, "START must be before END")
    return start, end


def _inside_era(field: str, surface: dict, allowed: set[str], interval) -> None:
    era = surface["ID"]
    if era not in allowed:
        _reject(field, "ID must be one of " + ", ".join(sorted(allowed)) + " (frozen era roles)")
    lo, hi = ERA_BOUNDS[era]
    if interval[0] < lo or interval[1] > hi:
        _reject(field, "interval must lie inside the " + era + " era")


def window_of(interval: tuple[dt.date, dt.date]) -> str:
    """[2020-01-01, 2025-01-01) -> '2020-01..2024-12' (the V0 HISTORICAL_WINDOW form)."""
    start, end = interval
    last = dt.date(end.year - (end.month == 1), 12 if end.month == 1 else end.month - 1, 1)
    return f"{start.year:04d}-{start.month:02d}..{last.year:04d}-{last.month:02d}"


def validate_planning_v1(proposal: dict) -> None:
    if not isinstance(proposal, dict):
        _reject("PROPOSAL", "planning object must be an object")
    if proposal.get("CONTRACT_VERSION") != CONTRACT_VERSION:
        _reject("CONTRACT_VERSION", "must be " + CONTRACT_VERSION)
    v0.validate_planning({k: v for k, v in proposal.items() if k != "CONTRACT_VERSION"})

    missing = [f for f in V1_FIELDS if f not in proposal or proposal[f] in (None, "", [])]
    if "INTRADAY" in missing and isinstance(proposal.get("INTRADAY"), bool):
        missing.remove("INTRADAY")
    if missing:
        _reject(missing[0], "required V1 field omitted")
    if proposal["CLAIM_TYPE"] not in CLAIM_TYPES:
        _reject("CLAIM_TYPE", "not a V1 claim type")
    if proposal["TARGET_CLASS"] not in TARGET_CLASSES:
        _reject("TARGET_CLASS", "not a V1 target class")
    if not isinstance(proposal["INTRADAY"], bool):
        _reject("INTRADAY", "must be true or false")
    if proposal["PRACTICAL_BAR_BASIS"] not in PRACTICAL_BAR_BASES:
        _reject("PRACTICAL_BAR_BASIS", "not a V1 practical-bar basis")

    roles = proposal["VARIABLE_ROLES"]
    if not isinstance(roles, dict) or set(roles) != set(ROLE_KEYS):
        _reject("VARIABLE_ROLES", "needs exactly " + ", ".join(ROLE_KEYS))
    for key in ROLE_KEYS:
        if not isinstance(roles[key], list) or not all(_text(x) for x in roles[key]):
            _reject("VARIABLE_ROLES", key + " is a list of variable names")

    cells = proposal["PRIMARY_CELLS"]
    if not isinstance(cells, list) or not 1 <= len(cells) <= MAX_PRIMARY_CELLS:
        _reject("PRIMARY_CELLS", "1 to 3 primary cells")
    for cell in cells:
        if not isinstance(cell, dict) or set(cell) != {"REGIME", "ESTIMAND", "HORIZON"}:
            _reject("PRIMARY_CELLS", "each cell has exactly REGIME, ESTIMAND and HORIZON")
        if not _text(cell["ESTIMAND"]) or not _text(cell["HORIZON"]):
            _reject("PRIMARY_CELLS", "ESTIMAND and HORIZON are required")
        if cell["REGIME"] is not None and not _text(cell["REGIME"]):
            _reject("PRIMARY_CELLS", "REGIME is a name or null")

    disc = _surface_interval("DISCOVERY_SURFACE", proposal["DISCOVERY_SURFACE"])
    _inside_era("DISCOVERY_SURFACE", proposal["DISCOVERY_SURFACE"], DISCOVERY_ERAS, disc)
    if window_of(disc) != proposal["HISTORICAL_WINDOW"]:
        _reject("DISCOVERY_SURFACE", "must equal HISTORICAL_WINDOW " + str(proposal["HISTORICAL_WINDOW"]))

    rep = proposal["REPLICATION_SURFACE"]
    if not isinstance(rep, dict) or rep.get("KIND") not in REPLICATION_KINDS:
        _reject("REPLICATION_SURFACE", "KIND is HISTORICAL or PROSPECTIVE")
    if rep["KIND"] == "HISTORICAL":
        if set(rep) != {"KIND", "ID", "START", "END", "NOMINAL_OBSERVATION_COUNT"}:
            _reject("REPLICATION_SURFACE", "historical: exactly KIND, ID, START, END, NOMINAL_OBSERVATION_COUNT")
        interval = _surface_interval("REPLICATION_SURFACE", rep)
        _inside_era("REPLICATION_SURFACE", rep, REPLICATION_ERAS, interval)
        if not _pos_int(rep["NOMINAL_OBSERVATION_COUNT"]):
            _reject("REPLICATION_SURFACE", "outcome-blind nominal count must be a positive integer")
    else:
        if set(rep) != {"KIND", "ID", "START", "STARTS_AFTER_FREEZE", "STOPPING_RULE"}:
            _reject("REPLICATION_SURFACE", "prospective: exactly KIND, ID, START, STARTS_AFTER_FREEZE, STOPPING_RULE")
        if not _text(rep["ID"]):
            _reject("REPLICATION_SURFACE", "ID is required")
        _month_date("REPLICATION_SURFACE", rep["START"])
        if not isinstance(rep["STOPPING_RULE"], dict):
            _reject("REPLICATION_SURFACE", "STOPPING_RULE must be an object")
        # Content of the rule, and a start inside the protected window, are the compiler's to judge.

    epochs = proposal["EPOCHS"]
    if epochs != "CALENDAR_YEAR" and not (isinstance(epochs, list) and len(epochs) >= 3
                                          and all(isinstance(e, dict) and _text(e.get("ID")) for e in epochs)):
        _reject("EPOCHS", "CALENDAR_YEAR or a declared list of at least 3 epochs with IDs")

    exclusions = proposal.get("NUISANCE_EXCLUSIONS", [])
    if not isinstance(exclusions, list) or not all(isinstance(r, dict) and set(r) == {"VARIABLE", "MECHANISM_ARGUMENT"}
                                                   for r in exclusions):
        _reject("NUISANCE_EXCLUSIONS", "a list of {VARIABLE, MECHANISM_ARGUMENT}")
    if "NUISANCE_DIAGNOSTIC_PLANNED" in proposal and not isinstance(proposal["NUISANCE_DIAGNOSTIC_PLANNED"], bool):
        _reject("NUISANCE_DIAGNOSTIC_PLANNED", "must be true or false")

    for field in LADDER_FIELDS:
        if field not in proposal:
            _reject(field, "required ladder field omitted")
    complexity.check_planning_ladder(proposal)

    by_year = proposal["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"].get("DECLARED_COUNT_BY_YEAR")
    if by_year is not None:
        if not isinstance(by_year, dict) or not all(str(y).isdigit() and _pos_int(n) for y, n in by_year.items()):
            _reject("NOMINAL_OBSERVATION_COUNT_CONSTRUCTION", "DECLARED_COUNT_BY_YEAR maps years to positive counts")
        if any(not disc[0].year <= int(y) < disc[1].year + (disc[1].month > 1) for y in by_year):
            _reject("NOMINAL_OBSERVATION_COUNT_CONSTRUCTION", "DECLARED_COUNT_BY_YEAR years must lie in the discovery surface")
    v0._reject_outcome_keys(proposal)


def to_compiler_proposal_v1(proposal: dict) -> dict:
    """Copy a V1 planning object into a GV0R02_SCHEMA_V1 proposal. No feasibility judgment."""
    validate_planning_v1(proposal)
    base = v0.to_compiler_proposal({k: v for k, v in proposal.items() if k != "CONTRACT_VERSION"})
    base["COMPILER_SCHEMA_VERSION"] = COMPILER_SCHEMA_VERSION
    base["COMPILER_POLICY_VERSION"] = COMPILER_POLICY_VERSION
    by_year = proposal["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"].get("DECLARED_COUNT_BY_YEAR")
    if by_year:
        base["OUTCOME_BLIND_SAMPLE"]["COUNT_BY_YEAR"] = {str(y): n for y, n in by_year.items()}
    for field in V1_FIELDS:
        value = proposal[field]
        base[field] = [dict(c) for c in value] if field == "PRIMARY_CELLS" else (
            {k: (list(v) if isinstance(v, list) else v) for k, v in value.items()} if isinstance(value, dict) else value)
    base["NUISANCE_EXCLUSIONS"] = [dict(r) for r in proposal.get("NUISANCE_EXCLUSIONS", [])]
    if "NUISANCE_DIAGNOSTIC_PLANNED" in proposal:
        base["NUISANCE_DIAGNOSTIC_PLANNED"] = proposal["NUISANCE_DIAGNOSTIC_PLANNED"]
    base["COMPLEXITY_CLASS"] = proposal["COMPLEXITY_CLASS"]
    base["COMPONENTS"] = list(proposal["COMPONENTS"])
    return base


def seal_v1(proposal: dict) -> dict:
    validate_planning_v1(proposal)
    return {field: proposal.get(field) for field in SEALED_FIELDS}


def reject_downstream_edit_v1(proposal: dict, edited: dict) -> None:
    """Refuse a silent rewrite of the V0 sealed fields or of any V1 design declaration."""
    original = seal_v1(proposal)
    if not isinstance(edited, dict):
        _reject("DOWNSTREAM", "edited proposal must be an object")
    for field, value in original.items():
        if edited.get(field) != value:
            _reject(field, "downstream change is forbidden")
