"""Outcome-blind count pass, planning objects and GV0R02 V2 compile for all twelve
R03 hypotheses. Never imports outcomes.py. Never reads a BTC target.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import NormalDist

import numpy as np

from scripts.research import gv0r02_feasibility_compiler as v0
from scripts.research import gv0r02_feasibility_compiler_v2 as v2
from scripts.research.generator_v0.feasibility_contract_v1 import to_compiler_proposal_v1

from . import constants as K
from . import data as D
from . import states as S

REPO = Path(__file__).resolve().parents[3]
PLANNING_OUT = REPO / "docs/research/OWNER_CARDS_R03_PLANNING.json"
FEASIBILITY_OUT = REPO / "docs/research/OWNER_CARDS_R03_FEASIBILITY.json"
STRESS_SD = v2.POWER_PROFILE["BASE_SD"] * v2.POWER_PROFILE["STRESS_SD_MULTIPLIER"]
Z_POWER = NormalDist().inv_cdf(v2.POWER_PROFILE["TARGET_POWER"])
def _jsonable(v):
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if not math.isfinite(float(v)) else float(v)
    if isinstance(v, np.ndarray):
        return _jsonable(v.tolist())
    return v


def unit_screen(units: list[dict], holm_m: int) -> dict:
    """Paired-unit power screen at the Holm first-step alpha, alpha / m, where m is the
    number of hypotheses of the card that pass the compiler gate (fixed outcome-blind).

    Under the frozen stress profile each window has SD 2 (comparator-SD units). A unit's
    difference of means then has variance 4 * (1/n_s + 1/n_c); the estimate is the mean
    over independent units. MDE = (z_alpha + z_power) * SE.
    """
    alpha = K.FAMILY_ALPHA / max(1, holm_m)
    if not units:
        return {"N_UNITS": 0, "MDE_STRESS": None, "WEAK": True, "ALPHA": alpha, "HOLM_M": holm_m}
    var = [STRESS_SD ** 2 * (1.0 / len(u["STATE"]) + 1.0 / len(u["COMPARATOR"])) for u in units]
    se = math.sqrt(float(np.mean(var)) / len(units))
    z_alpha = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    mde = (z_alpha + Z_POWER) * se
    return {"N_UNITS": len(units), "SE_STRESS": se, "MDE_STRESS": mde,
            "WEAK": bool(mde > K.MIN_MEANINGFUL_EFFECT), "ALPHA": alpha, "HOLM_M": holm_m,
            "MIN_MEANINGFUL_EFFECT": K.MIN_MEANINGFUL_EFFECT}


def planning_object(h: dict, disc_units: list[dict], rep_units: list[dict]) -> dict:
    card = K.CARDS[h["CARD"]]
    counts = S.unit_counts(disc_units)
    datasets = list(card["DATASETS"])
    pit = {
        K.DATASET_BTC: "VERIFIED",
        K.DATASET_BITMEX: "VERIFIED",
        K.DATASET_PANEL: "VERIFIED",
        K.DATASET_NYSE: "VERIFIED_PREANNOUNCED",
    }
    if card["REPLICATION"] == "BITMEX_HISTORICAL":
        if h["REPLICATION"]:
            replication = {"KIND": "HISTORICAL", **K.REPLICATION_BITMEX,
                           "NOMINAL_OBSERVATION_COUNT": max(1, len(rep_units))}
        else:
            replication = {"KIND": "PROSPECTIVE", "ID": f"BINANCE_PROSPECTIVE_{h['ID']}", "START": "2027-01-01",
                           "STARTS_AFTER_FREEZE": True,
                           "STOPPING_RULE": {"MIN_MECHANISM_ACTIVE_N": 10, "MIN_MECHANISM_INACTIVE_N": 40,
                                             "MIN_N": 50, "MAX_EPISODES": 60, "END_DATE": "2032-12-31",
                                             "COUNTS_ONLY_MONITORING": True,
                                             "PRODUCT_EXPOSURE_HANDLING": K.PROSPECTIVE_PANEL["STOPPING_RULE"]["PRODUCT_EXPOSURE_HANDLING"]}}
            datasets = [d for d in datasets if d != K.DATASET_BITMEX]
    else:
        replication = json.loads(json.dumps(K.PROSPECTIVE_PANEL))
    construction = {
        "COUNTING_UNIT": f"{h['UNIT']}_WITH_STATE_AND_COMPARATOR_WINDOWS",
        "WINDOW": K.HISTORICAL_WINDOW,
        "INCLUSION_RULE": f"STATE: {h['STATE']}. COMPARATOR: {h['COMPARATOR']}. A unit needs at least one state window and one comparator window.",
        "EXCLUSION_RULE": "Units without a state or without a comparator window; windows with any missing bar are dropped at outcome time from timestamps only. No outcome filter.",
        "OUTCOME_FILTER": "NONE",
    }
    if counts["UNITS"] > 0:
        construction["DECLARED_NOMINAL_COUNT"] = counts["ACTIVE_WINDOWS"] + counts["INACTIVE_WINDOWS"]
        construction["DECLARED_COUNT_BY_YEAR"] = {y: n for y, n in counts["UNITS_BY_YEAR"].items() if n > 0}
    nuisance = ["PRIOR_REALIZED_VOLATILITY", "LAGGED_TARGET"] + (["TIME_OF_DAY"] if h["WINDOW"] != "UTC_DAY_1440" else [])
    intraday = h["WINDOW"] != "UTC_DAY_1440"
    return {
        "CONTRACT_VERSION": K.CONTRACT_VERSION,
        "PROPOSAL_ID": h["ID"],
        "CANDIDATE_ID": f"{h['ID']}-{h['NAME']}",
        "CARD_ID": h["CARD"],
        "TEST_FAMILY_ID": card["TEST_FAMILY_ID"],
        "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID,
        "MECHANISM": h["MECHANISM"],
        "FALSIFIABLE_CLAIM": (
            f"The standardized log range of the state window ({h['STATE']}) minus the mean standardized "
            f"log range of the comparator windows ({h['COMPARATOR']}), averaged over {h['UNIT']} units, "
            f"has the expected sign ({h['DIRECTION']}), magnitude at least {K.MIN_MEANINGFUL_EFFECT} SD, and a "
            f"Holm-adjusted two-sided sign-flip p at or below {K.FAMILY_ALPHA} within {card['TEST_FAMILY_ID']}."
        ),
        "EVENT_OR_STATE_DEFINITION": h["STATE"],
        "PRIMARY_OBSERVABLE": f"STATE_{h['NAME']}",
        "ENDPOINT_MOMENT": "SECOND_MOMENT",
        "COUNTERFACTUAL_CLASS": (
            f"Sign-flip randomization of the per-unit state-minus-comparator difference over {h['UNIT']} units, "
            f"{K.SIGNFLIP_DRAWS} draws, seed {K.SIGNFLIP_SEED} plus the hypothesis index, two-sided "
            "p = (1 + count(|T_perm| >= |T_obs|)) / (1 + draws). Units are time-separated and each difference is "
            "computed inside its own unit, so slow volatility regimes cancel within the unit; a moving-block "
            "standard error over units is reported as a dependence diagnostic."
        ),
        "NAMED_INFERENCE_CLASS": "PERMUTATION_GROUP_INVARIANCE",
        "HISTORICAL_WINDOW": K.HISTORICAL_WINDOW,
        "POINT_IN_TIME_REQUIREMENTS": [{"DATASET_ID": d, "PIT_STATUS": pit[d]} for d in datasets],
        "NOMINAL_OBSERVATION_COUNT_CONSTRUCTION": construction,
        "DEPENDENCE_CLUSTERING_UNIT": h["UNIT"],
        "ERA_ROLES": {"BINANCE_2020_2024": "DISCOVERY", "BITMEX_2016_2019": "HISTORICAL_REPLICATION_CANDIDATE",
                      "Y2025_2026": "PROTECTED_HOLDOUT"},
        "EXPECTED_EFFECT": {"DIRECTION": h["DIRECTION"], "MIN_MEANINGFUL_EFFECT": K.MIN_MEANINGFUL_EFFECT,
                            "UNITS": K.EFFECT_UNITS, "RATIONALE": K.PRACTICAL_BAR_RATIONALE},
        "REQUIRED_STRESS_SCREENS": ["STRESS_SD_MULTIPLIER", "HOMOGENEOUS_EFFECT", "ZERO_EFFECT_IN_ONE_ERA"],
        "FEATURE_REQUIREMENTS": datasets,
        "DATA_SOURCE_REFS": {"FEATURE_REGISTRY_VERSION": "GV0R02_FEATURE_REGISTRY_V0", "FEATURE_IDS": datasets},
        "BLOCKING_ASSUMPTIONS": [
            "Within a unit the state and comparator windows share the slow volatility regime, so the within-unit difference removes it; what remains can still be serially dependent across units.",
            "The standardization scale (per year and per window definition) is label-blind and symmetric.",
            "The claim is descriptive. It does not identify which participants act.",
        ],
        "ERA_INVARIANCE_PRIOR": "UNKNOWN",
        "ERA_INVARIANCE_RATIONALE": "Calendar and venue structure changed between 2017-2019 and 2020-2024; the epoch-heterogeneity gate is assessed, never assumed.",
        "QUALITATIVE_DEPENDENCE_SOURCES": ["volatility clustering across units", "shared macro weeks", "exchange outages"],
        "CLAIM_TYPE": "CONTEXT_DESCRIPTIVE",
        "TARGET_CLASS": "UNCONDITIONAL",
        "COMPLEXITY_CLASS": "ATOMIC",
        "COMPONENTS": [],
        "INTRADAY": intraday,
        "VARIABLE_ROLES": {"REGIME_VARIABLES": [], "MECHANISM_VARIABLES": [f"STATE_{h['NAME']}"],
                           "NUISANCE_BASELINE_VARIABLES": nuisance},
        "NUISANCE_DIAGNOSTIC_PLANNED": True,
        "PRIMARY_CELLS": [{"REGIME": None,
                           "ESTIMAND": f"mean over {h['UNIT']} units of standardized log-range difference, state minus comparator",
                           "HORIZON": f"{K.WINDOW_DEFS[h['WINDOW']][2]}m window"}],
        "PRACTICAL_BAR_BASIS": "PRODUCT_RELEVANCE",
        "DISCOVERY_SURFACE": dict(K.DISCOVERY_SURFACE),
        "REPLICATION_SURFACE": replication,
        "EPOCHS": "CALENDAR_YEAR",
        "PRIMARY_MECHANISM_SUPPORT": [{"KIND": "BINARY", "MECHANISM_VARIABLE": f"STATE_{h['NAME']}",
                                       "MECHANISM_ACTIVE_N": counts["ACTIVE_WINDOWS"],
                                       "MECHANISM_INACTIVE_N": counts["INACTIVE_WINDOWS"]}],
        "FROZEN_OUTCOME_BLIND_SCREEN": {"PRIMARY_LABEL_ORBIT_SIZE": str(2 ** min(counts["UNITS"], 60)),
                                        "MIN_ATTAINABLE_P": 1.0 / (1 + K.SIGNFLIP_DRAWS) if counts["UNITS"] > 0 else 1.0,
                                        "MONTE_CARLO_DRAWS": K.SIGNFLIP_DRAWS, "EXACT_ENUMERATION": False},
        "UNIT_COUNTS": counts,
        "REPLICATION_UNIT_COUNT": len(rep_units),
        "ALLOWED_INTERPRETATION": K.ALLOWED_INTERPRETATION,
        "FORBIDDEN_INTERPRETATION": K.FORBIDDEN_INTERPRETATION,
    }


def extended_registry() -> dict:
    """The frozen derived registry plus two rows for datasets that have committed
    ledgers but no MANIFEST.json. The frozen registry itself is not touched, so earlier
    compiler results and their golden digests stay reproducible. Values are not opened."""
    base = v0.derive_feature_registry()
    extra = [
        {
            "feature_id": K.DATASET_PANEL,
            "definition_ref": "docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/object_ledger.json",
            "definition_digest": D.panel_ledger_digest(),
            "input_dataset_ids": [K.DATASET_PANEL], "unit": "dataset",
            "normalization_rule": "identity of the frozen object ledger (18296 SHA256-pinned monthly 1d zips)",
            "lookback_requirement": None,
            "available_at_rule": "daily bar closed at the next 00:00 UTC; values are not read here",
            "coverage_by_venue": {"SPOT": {"START": "2019-12", "VALUES_OPENED": False}},
            "coverage_by_instrument": {"USDT_QUOTED_PANEL": [2019, 2020, 2021, 2022, 2023, 2024]},
            "completeness": "LEDGER_ONLY", "known_breaks": [],
            "cross_venue_notes": "No cross-venue portability grade is assigned.",
            "quality_status": "PINNED_LEDGER",
        },
        {
            "feature_id": K.DATASET_BITMEX,
            "definition_ref": "docs/research_data/D2_BITMEX_PRE2020_SOURCE_AUTHORITY.json",
            "definition_digest": D.sha256_file(D.BITMEX_GZ),
            "input_dataset_ids": [K.DATASET_BITMEX], "unit": "dataset",
            "normalization_rule": "identity of canonical_5m.jsonl.gz (digest in the D2 source authority)",
            "lookback_requirement": None,
            "available_at_rule": "as-of the 5m bar open time; values are not read here",
            "coverage_by_venue": {"BITMEX_XBTUSD_PERPETUAL": {"START": "2016-05", "VALUES_OPENED": False}},
            "coverage_by_instrument": {"XBTUSD": [2016, 2017, 2018, 2019]},
            "completeness": "CANONICAL_FILE", "known_breaks": [],
            "cross_venue_notes": "No cross-venue portability grade is assigned.",
            "quality_status": "PINNED_CANONICAL_FILE",
        },
    ]
    features = sorted(base["FEATURES"] + extra, key=lambda r: r["feature_id"])
    body = {"FEATURE_REGISTRY_VERSION": base["FEATURE_REGISTRY_VERSION"], "FEATURES": features}
    return {**body, "FEATURE_REGISTRY_DIGEST": v0.sha256_hex(v0.canonical_json(body)),
            "EXTENDED_FROM_FROZEN_DIGEST": base["FEATURE_REGISTRY_DIGEST"],
            "EXTENSION_ROWS": [r["feature_id"] for r in extra]}


def compile_planning(planning: dict, registry: dict | None = None) -> dict:
    registry = registry or extended_registry()
    proposal = to_compiler_proposal_v1(planning)
    proposal["COMPILER_SCHEMA_VERSION"] = v2.COMPILER_SCHEMA_VERSION
    proposal["COMPILER_POLICY_VERSION"] = v2.COMPILER_POLICY_VERSION
    proposal["PRIMARY_MECHANISM_SUPPORT"] = [dict(r) for r in planning["PRIMARY_MECHANISM_SUPPORT"]]
    screen = dict(planning["FROZEN_OUTCOME_BLIND_SCREEN"])
    orbit = screen["PRIMARY_LABEL_ORBIT_SIZE"]
    screen["PRIMARY_LABEL_ORBIT_SIZE"] = int(orbit) if len(orbit) < 18 else orbit
    proposal["FROZEN_OUTCOME_BLIND_SCREEN"] = screen
    return v2.compile_proposal_v2(proposal, registry=registry)


def panel_metrics() -> dict:
    panel = D.load_panel_daily()
    return S.panel_day_metrics(panel, D.excluded_symbols(), K.DISCOVERY_START_MS, K.DISCOVERY_END_MS)


def run_support(*, with_panel: bool = True) -> tuple[dict, dict]:
    K.assert_locked()
    nyse = D.nyse_events()
    metrics = panel_metrics() if with_panel else None
    plans, feas, stage = {}, {}, {}
    registry = extended_registry()
    for h in K.HYPOTHESES:
        if h["CARD"] == "R03-B" and metrics is None:
            continue
        disc = S.build_units(h["ID"], "DISCOVERY", nyse=nyse, metrics=metrics)
        rep = S.build_units(h["ID"], "REPLICATION", nyse=nyse) if h["REPLICATION"] else []
        plan = planning_object(h, disc, rep)
        stage[h["ID"]] = (h, disc, rep, plan, compile_planning(plan, registry))
    for h in K.HYPOTHESES:
        if h["ID"] not in stage:
            continue
        h, disc, rep, plan, compiled = stage[h["ID"]]
        holm_m = sum(1 for x in stage.values()
                     if x[0]["CARD"] == h["CARD"] and x[4]["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION")
        own = unit_screen(disc, holm_m)
        executable = compiled["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION" and not own["WEAK"]
        plans[h["ID"]] = plan
        feas[h["ID"]] = {
            "COMPILER": compiled,
            "OWN_UNIT_SCREEN": own,
            "REPLICATION_UNITS": len(rep),
            "EXECUTABLE": executable,
            "STATUS": "FEASIBLE_FOR_PREREGISTRATION" if executable else (
                compiled["FEASIBILITY_STATUS"] if compiled["FEASIBILITY_STATUS"] != "FEASIBLE_FOR_PREREGISTRATION"
                else "INFORMATIONALLY_WEAK_AT_UNIT_LEVEL"),
        }
        if h["CARD"] == "R03-B":
            feas[h["ID"]]["PANEL_STATE_DIAGNOSTIC"] = S.units_panel(h["ID"], metrics, K.DISCOVERY_START_MS, K.DISCOVERY_END_MS)[1]
    return plans, feas


def main() -> None:
    plans, feas = run_support()
    identity = D.dataset_identity()
    PLANNING_OUT.write_text(json.dumps(_jsonable({"PROGRAM_ID": K.PROGRAM_ID, "DATASETS": identity,
                                                  "PLANNING": plans}), indent=2, sort_keys=True) + "\n")
    summary = {hid: {"STATUS": f["STATUS"], "EXECUTABLE": f["EXECUTABLE"],
                     "COMPILER_STATUS": f["COMPILER"]["FEASIBILITY_STATUS"],
                     "BLOCKERS": [b["BLOCKER_CODE"] for b in f["COMPILER"]["BLOCKERS"]],
                     "EFFECTIVE_N": f["COMPILER"]["DISCOVERY_SCREEN"].get("EFFECTIVE_N"),
                     "MDE_STRESS_COMPILER": f["COMPILER"]["DISCOVERY_SCREEN"].get("MDE_STRESS"),
                     "MDE_STRESS_UNITS": f["OWN_UNIT_SCREEN"]["MDE_STRESS"],
                     "N_UNITS": f["OWN_UNIT_SCREEN"]["N_UNITS"],
                     "REPLICATION_UNITS": f["REPLICATION_UNITS"]} for hid, f in feas.items()}
    reg = extended_registry()
    FEASIBILITY_OUT.write_text(json.dumps(_jsonable({"PROGRAM_ID": K.PROGRAM_ID, "SUMMARY": summary,
                                                     "FEATURE_REGISTRY": {k: reg[k] for k in ("FEATURE_REGISTRY_DIGEST", "EXTENDED_FROM_FROZEN_DIGEST", "EXTENSION_ROWS")},
                                                     "DETAIL": feas, "MARKET_OUTCOMES_OPENED": False,
                                                     "POST_T_TARGET_COMPUTED": False}),
                                          indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
