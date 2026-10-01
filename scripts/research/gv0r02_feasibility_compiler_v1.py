"""Outcome-blind feasibility compiler mapped to HYPOTHESIS_EVALUATION_CONTRACT_V1.

GV0R02_SCHEMA_V1 / GV0R02_POLICY_V1. The V0 compiler is unchanged and keeps
scoring V0 proposals; old results are never rescored. This layer adds the
V1 definition checks (claim type, target class, variable roles, nuisance
baseline, primary cells, practical-bar basis, time-disjoint or prospective
replication with a fixed stopping rule, protected-window overlap), Holm-adjusted
power for the declared primary cells, a replication power screen and an
epoch-heterogeneity assessability record. It does not decide that a
hypothesis is true and does not open market outcomes.
"""

from __future__ import annotations

import datetime as dt
import math
from statistics import NormalDist

from scripts.research import gv0r02_feasibility_compiler as v0

COMPILER_SCHEMA_VERSION = "GV0R02_SCHEMA_V1"
COMPILER_POLICY_VERSION = "GV0R02_POLICY_V1"
EVALUATION_CONTRACT = "HYPOTHESIS_EVALUATION_CONTRACT_V1"
POWER_PROFILE = v0.POWER_PROFILE          # unchanged frozen profile
STATUS_PRIORITY = list(v0.STATUS_PRIORITY)

CLAIM_TYPES = {"CONTEXT_DESCRIPTIVE", "INCREMENTAL"}
TARGET_CLASSES = {"UNCONDITIONAL", "CONDITIONAL"}
PRACTICAL_BAR_BASES = {"COSTS", "PRODUCT_RELEVANCE"}
REPLICATION_KINDS = {"HISTORICAL", "PROSPECTIVE"}
DIRECTIONAL_MOMENTS = {"FIRST_MOMENT", "RELATIVE_VALUE"}
STANDARD_NUISANCE = ("PRIOR_REALIZED_VOLATILITY", "LAGGED_TARGET")
INTRADAY_NUISANCE = "TIME_OF_DAY"
MAX_PRIMARY_CELLS = 3
ALPHA_HET = 0.05
HET_ASSESSABLE_POWER = 0.50
PROTECTED_START = dt.date(2025, 1, 1)
PROTECTED_END_EXCLUSIVE = dt.date(2027, 1, 1)

V1_REQUIRED_FIELDS = [
    "CLAIM_TYPE",
    "TARGET_CLASS",
    "VARIABLE_ROLES",
    "INTRADAY",
    "PRIMARY_CELLS",
    "PRACTICAL_BAR_BASIS",
    "DISCOVERY_SURFACE",
    "REPLICATION_SURFACE",
    "EPOCHS",
]
HARDER_THAN_WEAK = STATUS_PRIORITY[: STATUS_PRIORITY.index("INFORMATIONALLY_WEAK")]


def _date(value) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _interval(surface) -> tuple[dt.date, dt.date] | None:
    if not isinstance(surface, dict):
        return None
    start, end = _date(surface.get("START")), _date(surface.get("END"))
    if start is None or end is None or start >= end:
        return None
    return start, end


def _overlaps(a: tuple[dt.date, dt.date], b: tuple[dt.date, dt.date]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _pos_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def z_two_sided(alpha: float) -> float:
    return NormalDist().inv_cdf(1.0 - alpha / 2.0)


def _power(effect, sd: float, n_eff, z_alpha: float) -> float | None:
    if effect is None or n_eff is None or n_eff <= 0 or sd <= 0:
        return None
    z = abs(effect) / (sd / math.sqrt(n_eff)) - z_alpha
    return NormalDist().cdf(z)


def _mde(sd: float, n_eff, z_alpha: float) -> float | None:
    if n_eff is None or n_eff <= 0:
        return None
    return (z_alpha + POWER_PROFILE["Z_TARGET"]) * sd / math.sqrt(n_eff)


def _definition_checks(p: dict) -> list[dict]:
    """V1 definition checks. Every failure is a DEFINITION_INCOMPLETE blocker."""
    out = []

    def block(code, **obj):
        out.append({"BLOCKER_CODE": code, "BLOCKER_OBJECT": obj})

    missing = [f for f in V1_REQUIRED_FIELDS if f not in p or p[f] in (None, "", [])]
    if "INTRADAY" in p and isinstance(p["INTRADAY"], bool):
        missing = [f for f in missing if f != "INTRADAY"]
    if missing:
        block("V1_FIELDS_MISSING", FIELDS=sorted(missing))
        return out

    claim, target = p["CLAIM_TYPE"], p["TARGET_CLASS"]
    if claim not in CLAIM_TYPES:
        block("CLAIM_TYPE_INVALID", CLAIM_TYPE=claim)
    if target not in TARGET_CLASSES:
        block("TARGET_CLASS_INVALID", TARGET_CLASS=target)
    if not isinstance(p["INTRADAY"], bool):
        block("INTRADAY_INVALID", INTRADAY=p["INTRADAY"])

    roles = p["VARIABLE_ROLES"] if isinstance(p["VARIABLE_ROLES"], dict) else {}
    regime = list(roles.get("REGIME_VARIABLES") or [])
    mechanism = list(roles.get("MECHANISM_VARIABLES") or [])
    nuisance = list(roles.get("NUISANCE_BASELINE_VARIABLES") or [])
    if not mechanism:
        block("MECHANISM_VARIABLES_MISSING")
    if set(mechanism) & set(nuisance):
        block("MECHANISM_CONDITIONED_AWAY", VARIABLES=sorted(set(mechanism) & set(nuisance)))
    if target == "CONDITIONAL" and not regime:
        block("REGIME_MISSING_FOR_CONDITIONAL_CLAIM")
    if target == "UNCONDITIONAL" and regime:
        block("REGIME_DECLARED_FOR_UNCONDITIONAL_CLAIM", REGIME_VARIABLES=regime)

    moment = p.get("ENDPOINT_MOMENT")
    if claim == "CONTEXT_DESCRIPTIVE":
        if moment in DIRECTIONAL_MOMENTS:
            block("CONTEXT_CLAIM_DIRECTIONAL", ENDPOINT_MOMENT=moment)
        if p.get("NUISANCE_DIAGNOSTIC_PLANNED") is not True or not nuisance:
            block("CONTEXT_NUISANCE_DIAGNOSTIC_MISSING")
        if p["PRACTICAL_BAR_BASIS"] != "PRODUCT_RELEVANCE":
            block("PRACTICAL_BAR_BASIS_INVALID", CLAIM_TYPE=claim, BASIS=p["PRACTICAL_BAR_BASIS"])
    if claim == "INCREMENTAL":
        required = list(STANDARD_NUISANCE) + ([INTRADAY_NUISANCE] if p["INTRADAY"] is True else [])
        excluded = {}
        for row in p.get("NUISANCE_EXCLUSIONS") or []:
            if isinstance(row, dict) and str(row.get("MECHANISM_ARGUMENT") or "").strip():
                excluded[row.get("VARIABLE")] = row["MECHANISM_ARGUMENT"]
        absent = [v for v in required if v not in nuisance and v not in excluded]
        if absent:
            block("STANDARD_NUISANCE_MISSING", VARIABLES=absent)
        if moment in DIRECTIONAL_MOMENTS and p["PRACTICAL_BAR_BASIS"] != "COSTS":
            block("PRACTICAL_BAR_BASIS_INVALID", CLAIM_TYPE=claim, BASIS=p["PRACTICAL_BAR_BASIS"])
    if p["PRACTICAL_BAR_BASIS"] not in PRACTICAL_BAR_BASES:
        block("PRACTICAL_BAR_BASIS_INVALID", BASIS=p["PRACTICAL_BAR_BASIS"])

    cells = p["PRIMARY_CELLS"]
    if not isinstance(cells, list) or not cells or len(cells) > MAX_PRIMARY_CELLS:
        block("PRIMARY_CELLS_INVALID", COUNT=len(cells) if isinstance(cells, list) else None, MAX=MAX_PRIMARY_CELLS)
    elif not all(isinstance(c, dict) and c.get("ESTIMAND") and c.get("HORIZON") for c in cells):
        block("PRIMARY_CELLS_INVALID", REASON="each cell needs ESTIMAND and HORIZON")
    elif target == "CONDITIONAL" and not all(c.get("REGIME") for c in cells):
        block("PRIMARY_CELLS_INVALID", REASON="conditional cells need a declared REGIME")

    disc = _interval(p["DISCOVERY_SURFACE"])
    rep_decl = p["REPLICATION_SURFACE"] if isinstance(p["REPLICATION_SURFACE"], dict) else {}
    kind = rep_decl.get("KIND")
    if disc is None:
        block("DISCOVERY_SURFACE_INVALID")
    if kind not in REPLICATION_KINDS:
        block("REPLICATION_SURFACE_INVALID", KIND=kind)
    elif kind == "HISTORICAL":
        rep = _interval(rep_decl)
        if rep is None:
            block("REPLICATION_SURFACE_INVALID", KIND=kind)
        elif disc is not None and _overlaps(disc, rep):
            block("REPLICATION_NOT_TIME_DISJOINT")
        if not _pos_int(rep_decl.get("NOMINAL_OBSERVATION_COUNT")):
            block("REPLICATION_COUNT_MISSING")
    else:  # PROSPECTIVE
        start = _date(rep_decl.get("START"))
        if start is None:
            block("REPLICATION_SURFACE_INVALID", KIND=kind)
        elif disc is not None and start < disc[1]:
            block("REPLICATION_NOT_TIME_DISJOINT")
        if rep_decl.get("STARTS_AFTER_FREEZE") is not True:
            block("PROSPECTIVE_NOT_AFTER_FREEZE")
        rule = rep_decl.get("STOPPING_RULE") if isinstance(rep_decl.get("STOPPING_RULE"), dict) else None
        if rule is None:
            block("STOPPING_RULE_MISSING")
        else:
            has_count = _pos_int(rule.get("MAX_EPISODES"))
            end = _date(rule.get("END_DATE"))
            if not (has_count or end is not None):
                block("STOPPING_RULE_MISSING", REASON="needs MAX_EPISODES or END_DATE")
            if not _pos_int(rule.get("MIN_N")):
                block("STOPPING_RULE_MISSING", REASON="needs MIN_N")
            elif has_count and rule["MIN_N"] > rule["MAX_EPISODES"]:
                block("STOPPING_RULE_INVALID", REASON="MIN_N above MAX_EPISODES")
            if end is not None and start is not None and end <= start:
                block("STOPPING_RULE_INVALID", REASON="END_DATE not after START")
            if rule.get("COUNTS_ONLY_MONITORING") is not True:
                block("STOPPING_RULE_MISSING", REASON="counts-only monitoring must be declared")
            if not str(rule.get("PRODUCT_EXPOSURE_HANDLING") or "").strip():
                block("STOPPING_RULE_MISSING", REASON="product exposure handling must be stated")
    return out


def _protected_overlap(p: dict) -> list[str]:
    hits = []
    window = (PROTECTED_START, PROTECTED_END_EXCLUSIVE)
    disc = _interval(p.get("DISCOVERY_SURFACE"))
    if disc is not None and _overlaps(disc, window):
        hits.append("DISCOVERY_SURFACE")
    rep = p.get("REPLICATION_SURFACE") or {}
    if rep.get("KIND") == "HISTORICAL":
        iv = _interval(rep)
        if iv is not None and _overlaps(iv, window):
            hits.append("REPLICATION_SURFACE")
    elif rep.get("KIND") == "PROSPECTIVE":
        start = _date(rep.get("START"))
        if start is not None and start < PROTECTED_END_EXCLUSIVE:
            hits.append("REPLICATION_SURFACE")
    return hits


def _heterogeneity_assessability(p: dict) -> dict:
    counts = (p.get("OUTCOME_BLIND_SAMPLE") or {}).get("COUNT_BY_YEAR") or {}
    sizes = sorted(v for v in counts.values() if _pos_int(v))
    if len(sizes) < 3:
        return {"STATUS": "NOT_ASSESSABLE", "REASON": "FEWER_THAN_3_EPOCHS_WITH_COUNTS", "POWER": None}
    n1, n2 = sizes[0], sizes[1]
    sd = POWER_PROFILE["BASE_SD"] * POWER_PROFILE["STRESS_SD_MULTIPLIER"]
    effect = p.get("MIN_MEANINGFUL_EFFECT")
    n_eff = 1.0 / (1.0 / n1 + 1.0 / n2)
    power = _power(effect, sd, n_eff, z_two_sided(ALPHA_HET))
    status = "ASSESSABLE" if power is not None and power >= HET_ASSESSABLE_POWER else "NOT_ASSESSABLE"
    return {
        "STATUS": status,
        "REASON": "POWER_TO_DETECT_A_DIFFERENCE_OF_THE_MIN_EFFECT_BETWEEN_THE_TWO_SMALLEST_EPOCHS",
        "POWER": power,
        "THRESHOLD": HET_ASSESSABLE_POWER,
        "NOT_EVIDENCE_OF_STABILITY": True,
    }


def compile_proposal_v1(proposal: dict, *, registry: dict | None = None) -> dict:
    registry = registry or v0.derive_feature_registry()
    if proposal.get("COMPILER_SCHEMA_VERSION") not in (None, COMPILER_SCHEMA_VERSION):
        version_block = [{"BLOCKER_CODE": "DEFINITION_INCOMPLETE",
                          "BLOCKER_OBJECT": {"FIELDS": ["COMPILER_SCHEMA_VERSION"]}}]
    else:
        version_block = []
    base_input = {k: v for k, v in proposal.items() if k not in ("COMPILER_SCHEMA_VERSION", "COMPILER_POLICY_VERSION")}
    base = v0.compile_proposal(base_input, registry=registry)

    flags = {s: False for s in STATUS_PRIORITY}
    blockers = list(version_block)
    reasons = []
    if version_block:
        flags["DEFINITION_INCOMPLETE"] = True
        reasons.append("schema version is not GV0R02_SCHEMA_V1")
    if base["FEASIBILITY_STATUS"] in HARDER_THAN_WEAK:
        flags[base["FEASIBILITY_STATUS"]] = True
        reasons.append(f"V0 passes: {base['FEASIBILITY_STATUS']}")
    blockers += [b for b in base["BLOCKERS"] if b["BLOCKER_CODE"] != "MDE_TOO_LARGE"]

    definition = _definition_checks(proposal)
    if definition:
        flags["DEFINITION_INCOMPLETE"] = True
        reasons.append("V1 definition checks failed")
        blockers += definition

    protected = _protected_overlap(proposal)
    if protected:
        flags["DATA_BLOCKED"] = True
        reasons.append("a surface overlaps the protected 2025/2026 window")
        blockers.append({"BLOCKER_CODE": "PROTECTED_SURFACE_DECISION_REQUIRED",
                         "BLOCKER_OBJECT": {"SURFACES": protected}})

    cells = proposal.get("PRIMARY_CELLS") if isinstance(proposal.get("PRIMARY_CELLS"), list) else []
    k = max(1, min(len(cells), MAX_PRIMARY_CELLS)) if cells else 1
    alpha_cell = POWER_PROFILE["ALPHA"] / k
    z_cell = z_two_sided(alpha_cell)
    effect = proposal.get("MIN_MEANINGFUL_EFFECT")
    stress_sd = POWER_PROFILE["BASE_SD"] * POWER_PROFILE["STRESS_SD_MULTIPLIER"]

    screen = (proposal.get("FROZEN_OUTCOME_BLIND_SCREEN") or {}).get("POWER")
    if screen:
        if k > 1 and screen.get("MULTIPLICITY_ADJUSTED") is not True:
            flags["DEFINITION_INCOMPLETE"] = True
            blockers.append({"BLOCKER_CODE": "MULTIPLICITY_NOT_ADJUSTED", "BLOCKER_OBJECT": {"PRIMARY_CELLS": k}})
        discovery = {
            "MDE_BASE": screen.get("MDE_BASE"), "MDE_STRESS": screen.get("MDE_STRESS"),
            "POWER_BASE": screen.get("POWER_BASE"), "POWER_STRESS": screen.get("POWER_STRESS"),
        }
    else:
        n = (proposal.get("OUTCOME_BLIND_SAMPLE") or {}).get("NOMINAL_OBSERVATION_COUNT")
        n = float(n) if _pos_int(n) else None
        discovery = {
            "MDE_BASE": _mde(POWER_PROFILE["BASE_SD"], n, z_cell),
            "MDE_STRESS": _mde(stress_sd, n, z_cell),
            "POWER_BASE": _power(effect, POWER_PROFILE["BASE_SD"], n, z_cell),
            "POWER_STRESS": _power(effect, stress_sd, n, z_cell),
        }

    def weak_by(numbers) -> bool:
        p_s, m_s = numbers.get("POWER_STRESS"), numbers.get("MDE_STRESS")
        if p_s is not None and p_s < POWER_PROFILE["TARGET_POWER"]:
            return True
        return (m_s is not None and effect is not None and abs(m_s) > abs(effect)
                and proposal.get("NAMED_INFERENCE_CLASS") != "PLACEBO_REFERENCE_DISTRIBUTION")

    if weak_by(discovery):
        flags["INFORMATIONALLY_WEAK"] = True
        reasons.append("discovery stress screen misses the target at the Holm-adjusted alpha")
        blockers.append({"BLOCKER_CODE": "MDE_TOO_LARGE",
                         "BLOCKER_OBJECT": {"SURFACE": "DISCOVERY", "MIN_MEANINGFUL_EFFECT": effect,
                                            "MDE_STRESS": discovery["MDE_STRESS"],
                                            "POWER_STRESS": discovery["POWER_STRESS"],
                                            "ALPHA_PER_CELL": alpha_cell}})

    rep_decl = proposal.get("REPLICATION_SURFACE") if isinstance(proposal.get("REPLICATION_SURFACE"), dict) else {}
    rep_screen = rep_decl.get("POWER")
    if rep_screen:
        replication = {"POWER_STRESS": rep_screen.get("POWER_STRESS"), "MDE_STRESS": rep_screen.get("MDE_STRESS")}
        rep_n = None
    else:
        if rep_decl.get("KIND") == "PROSPECTIVE":
            rep_n = (rep_decl.get("STOPPING_RULE") or {}).get("MIN_N")
        else:
            rep_n = rep_decl.get("NOMINAL_OBSERVATION_COUNT")
        rep_n = float(rep_n) if _pos_int(rep_n) else None
        replication = {"POWER_STRESS": _power(effect, stress_sd, rep_n, z_cell),
                       "MDE_STRESS": _mde(stress_sd, rep_n, z_cell)}
    if not flags["DEFINITION_INCOMPLETE"] and weak_by(replication):
        flags["INFORMATIONALLY_WEAK"] = True
        reasons.append("replication stress screen misses the target")
        blockers.append({"BLOCKER_CODE": "REPLICATION_MDE_TOO_LARGE",
                         "BLOCKER_OBJECT": {"SURFACE": "REPLICATION", "N": rep_n, **replication}})

    heterogeneity = _heterogeneity_assessability(proposal)

    if not any(flags[s] for s in STATUS_PRIORITY if s != "FEASIBLE_FOR_PREREGISTRATION"):
        flags["FEASIBLE_FOR_PREREGISTRATION"] = True
        reasons.append("no harder status matched")
    status = next(s for s in STATUS_PRIORITY if flags[s])

    digest_fields = v0.REQUIRED_FIELDS + V1_REQUIRED_FIELDS + ["NUISANCE_EXCLUSIONS", "NUISANCE_DIAGNOSTIC_PLANNED"]
    proposal_digest = v0.sha256_hex(v0.canonical_json({f: proposal[f] for f in digest_fields if f in proposal}))
    identity = {
        "PROPOSAL_DIGEST": proposal_digest,
        "COMPILER_SCHEMA_VERSION": COMPILER_SCHEMA_VERSION,
        "COMPILER_POLICY_VERSION": COMPILER_POLICY_VERSION,
        "EVALUATION_CONTRACT": EVALUATION_CONTRACT,
        "POWER_ASSUMPTION_PROFILE_VERSION": v0.POWER_ASSUMPTION_PROFILE_VERSION,
        "FEATURE_REGISTRY_DIGEST": registry["FEATURE_REGISTRY_DIGEST"],
    }
    return {
        "RESULT_ID": v0.sha256_hex(v0.canonical_json(identity)),
        "PROPOSAL_ID": proposal.get("PROPOSAL_ID"),
        "PROPOSAL_DIGEST": proposal_digest,
        "COMPILER_SCHEMA_VERSION": COMPILER_SCHEMA_VERSION,
        "COMPILER_POLICY_VERSION": COMPILER_POLICY_VERSION,
        "EVALUATION_CONTRACT": EVALUATION_CONTRACT,
        "POWER_ASSUMPTION_PROFILE_VERSION": v0.POWER_ASSUMPTION_PROFILE_VERSION,
        "FEATURE_REGISTRY_DIGEST": registry["FEATURE_REGISTRY_DIGEST"],
        "V0_PASSES": {k: base[k] for k in ("FEASIBILITY_STATUS", "DATA_STATUS", "PIT_STATUS", "NAMED_INFERENCE_CLASS",
                                            "PRIMARY_SUPPORT_SIZE", "MIN_ATTAINABLE_P", "ALPHA_ATTAINABLE",
                                            "REFERENCE_SUPPORT_SIZE", "REFERENCE_SUPPORT_RESOLUTION",
                                            "MONTE_CARLO_P_FLOOR", "STRUCTURAL_DEPENDENCE_SUMMARY")},
        "CLAIM_TYPE": proposal.get("CLAIM_TYPE"),
        "TARGET_CLASS": proposal.get("TARGET_CLASS"),
        "PRIMARY_CELL_COUNT": len(cells),
        "ALPHA_PER_CELL_HOLM_FIRST_STEP": alpha_cell,
        "DISCOVERY_SCREEN": discovery,
        "REPLICATION_KIND": rep_decl.get("KIND"),
        "REPLICATION_SCREEN": replication,
        "HETEROGENEITY_ASSESSABILITY": heterogeneity,
        "PROTECTED_OVERLAP": protected,
        "MIN_MEANINGFUL_EFFECT": effect,
        "TARGET_POWER": POWER_PROFILE["TARGET_POWER"],
        "BLOCKERS": blockers,
        "FEASIBILITY_STATUS": status,
        "STATUS_REASONS": reasons,
        "MARKET_OUTCOMES_OPENED": False,
        "PROTECTED_2025_VALUES_OPENED": False,
        "PROTECTED_2026_VALUES_OPENED": False,
    }


def v1_fields(**overrides) -> dict:
    """Neutral V1 declaration for structural fixtures. Not a market hypothesis."""
    fields = {
        "COMPILER_SCHEMA_VERSION": COMPILER_SCHEMA_VERSION,
        "CLAIM_TYPE": "INCREMENTAL",
        "TARGET_CLASS": "UNCONDITIONAL",
        "INTRADAY": False,
        "VARIABLE_ROLES": {
            "REGIME_VARIABLES": [],
            "MECHANISM_VARIABLES": ["FIXTURE_MECHANISM"],
            "NUISANCE_BASELINE_VARIABLES": ["PRIOR_REALIZED_VOLATILITY", "LAGGED_TARGET"],
        },
        "PRIMARY_CELLS": [{"REGIME": None, "ESTIMAND": "FIXTURE_ESTIMAND", "HORIZON": "FIXTURE_HORIZON"}],
        "PRACTICAL_BAR_BASIS": "COSTS",
        "DISCOVERY_SURFACE": {"ID": "BINANCE_2020_2024", "START": "2020-01-01", "END": "2025-01-01"},
        "REPLICATION_SURFACE": {"KIND": "HISTORICAL", "ID": "BITMEX_2016_2019", "START": "2016-01-01",
                                "END": "2020-01-01", "NOMINAL_OBSERVATION_COUNT": 100000},
        "EPOCHS": "CALENDAR_YEAR",
    }
    fields.update(overrides)
    return fields


def golden_proposals_v1() -> dict[str, dict]:
    """The three V0 golden cases with a neutral V1 declaration (one primary cell).

    V1 must not change their binding constraint: C012 and C020 stay
    INFORMATIONALLY_WEAK and C004 stays INFERENCE_SUPPORT_INSUFFICIENT.
    """
    return {name: {**proposal, **v1_fields()} for name, proposal in v0.golden_proposals().items()}
