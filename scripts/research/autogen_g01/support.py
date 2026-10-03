"""Outcome-blind feasibility for AUTOGEN_G01: unit counts from calendars and timestamps,
planning objects under GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V1, the GV0R02 V2 compile
(R03 extended registry, imported unchanged) and the program's own unit-level power screens.
Never imports outcomes.py. Never reads a price, a volume or a trade count.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import NormalDist

import numpy as np

from scripts.research import gv0r02_feasibility_compiler_v2 as v2
from scripts.research.owner_cards_r03 import data as RD
from scripts.research.owner_cards_r03 import support as RS

from . import constants as K
from . import data as D
from . import states as S

REPO = Path(__file__).resolve().parents[3]
PLANNING_OUT = REPO / "docs/research/AUTOGEN_G01_PLANNING.json"
FEASIBILITY_OUT = REPO / "docs/research/AUTOGEN_G01_FEASIBILITY.json"
STRESS_SD = v2.POWER_PROFILE["BASE_SD"] * v2.POWER_PROFILE["STRESS_SD_MULTIPLIER"]
Z_POWER = NormalDist().inv_cdf(v2.POWER_PROFILE["TARGET_POWER"])
_jsonable = RS._jsonable


# ------------------------------------------------------------ availability
def window_complete(t_sorted: np.ndarray, t0: int, minutes: int, step_ms: int) -> bool:
    t1 = t0 + minutes * K.MINUTE_MS
    i0 = int(np.searchsorted(t_sorted, t0, side="left"))
    i1 = int(np.searchsorted(t_sorted, t1, side="left"))
    return i1 - i0 == (t1 - t0) // step_ms


def available_units(units: list[dict], t_sorted: np.ndarray, step_ms: int) -> list[dict]:
    """Units keeping only timestamp-complete windows; a unit needs one state and one comparator."""
    out = []
    for u in units:
        st = [w for w in u["STATE"] if window_complete(t_sorted, w[0], w[1], step_ms)]
        co = [w for w in u["COMPARATOR"] if window_complete(t_sorted, w[0], w[1], step_ms)]
        if st and co:
            out.append({**u, "STATE": st, "COMPARATOR": co})
    return out


# ------------------------------------------------------------ power screens
def did_screen(units: list[dict]) -> dict:
    """Two-era DiD on week units. Under the frozen stress profile each hour z has SD STRESS_SD;
    a day's fix-minus-adjacent difference has variance STRESS_SD^2 * (1 + 1/2); a week averages
    its trading days. SE = sqrt(mean var_pre / n_pre + mean var_post / n_post)."""
    pre = [u for u in units if u["ERA"] == "PRE"]
    post = [u for u in units if u["ERA"] == "POST"]
    if not pre or not post:
        return {"N_PRE": len(pre), "N_POST": len(post), "MDE_STRESS": None, "WEAK": True}
    var_day = STRESS_SD ** 2 * (1.0 + 1.0 / len(K.NY_ADJACENT_HOURS))
    v_pre = float(np.mean([var_day / len(u["DAYS"]) for u in pre]))
    v_post = float(np.mean([var_day / len(u["DAYS"]) for u in post]))
    se = math.sqrt(v_pre / len(pre) + v_post / len(post))
    z_alpha = NormalDist().inv_cdf(1.0 - K.FAMILY_ALPHA / 2.0)
    mde = (z_alpha + Z_POWER) * se
    return {"N_PRE": len(pre), "N_POST": len(post), "SE_STRESS": se, "MDE_STRESS": mde, "ALPHA": K.FAMILY_ALPHA,
            "HOLM_M": 1, "WEAK": bool(mde > K.MIN_MEANINGFUL_EFFECT), "MIN_MEANINGFUL_EFFECT": K.MIN_MEANINGFUL_EFFECT}


def paired_screen(units: list[dict], holm_m: int) -> dict:
    if RS.K.FAMILY_ALPHA != K.FAMILY_ALPHA or RS.K.MIN_MEANINGFUL_EFFECT != K.MIN_MEANINGFUL_EFFECT:
        raise RuntimeError("imported R03 screen constants differ from AUTOGEN_G01's")
    return RS.unit_screen(units, holm_m)


# ------------------------------------------------------------ planning objects
def planning_object(h: dict, disc_units: list[dict], rep_units: list[dict]) -> dict:
    card = K.CARDS[h["CARD"]]
    counts = S.unit_counts(disc_units)
    datasets = list(card["DATASETS"])
    pit = {K.DATASET_BTC: "VERIFIED", K.DATASET_BITMEX: "VERIFIED", K.DATASET_NYSE: "VERIFIED_PREANNOUNCED"}
    if card["REPLICATION"] == "BITMEX_HISTORICAL":
        replication = {"KIND": "HISTORICAL", **K.REPLICATION_BITMEX, "NOMINAL_OBSERVATION_COUNT": max(1, len(rep_units))}
    else:
        replication = json.loads(json.dumps(K.PROSPECTIVE_B))
    did = h["DESIGN"] == "TWO_ERA_DID"
    window_text = {"UTC_DAY": "1440m UTC day", "UTC_HOUR_23": "60m window 23:00-24:00 UTC",
                   "NY_HOURS_13_14_15": "60m New York hours 13:00, 14:00 and 15:00"}[h["WINDOW"]]
    if did:
        estimand = "mean d_week over POST weeks minus mean d_week over PRE weeks, d = z(fix hour) - mean z(adjacent hours)"
        counterfactual = (
            f"Block permutation of era labels over blocks of {K.BLOCK_WEEKS} consecutive ISO weeks, "
            f"{K.BLOCKPERM_DRAWS} draws, seed {K.BLOCKPERM_SEED}, two-sided p = (1 + count(|T_perm| >= |T_obs|)) / (1 + draws). "
            "The within-day difference removes day-level volatility; the 4-week blocks keep short-range serial dependence."
        )
        n_blocks = math.ceil(counts["UNITS"] / K.BLOCK_WEEKS)
        n_post_blocks = math.ceil(counts["POST_UNITS"] / K.BLOCK_WEEKS)
        orbit = str(math.comb(n_blocks, n_post_blocks)) if counts["UNITS"] else "1"
        draws = K.BLOCKPERM_DRAWS
    else:
        estimand = "mean over month units of mean z(state) - mean z(comparator)"
        counterfactual = (
            f"Sign-flip randomization of the per-month state-minus-comparator difference, {K.SIGNFLIP_DRAWS} draws, "
            f"seed {K.SIGNFLIP_SEED} plus the hypothesis index, two-sided p = (1 + count(|T_perm| >= |T_obs|)) / (1 + draws). "
            "Months are time-separated and each difference is formed inside its month; a moving-block SE is reported."
        )
        orbit = str(2 ** min(counts["UNITS"], 60))
        draws = K.SIGNFLIP_DRAWS
    construction = {
        "COUNTING_UNIT": f"{h['UNIT']}_WITH_STATE_AND_COMPARATOR_WINDOWS",
        "WINDOW": K.HISTORICAL_WINDOW,
        "INCLUSION_RULE": f"STATE: {h['STATE']}. COMPARATOR: {h['COMPARATOR']}.",
        "EXCLUSION_RULE": "Units without a state or a comparator window; windows with any missing bar dropped at outcome time from timestamps only. No outcome filter.",
        "OUTCOME_FILTER": "NONE",
    }
    if counts["UNITS"] > 0:
        construction["DECLARED_NOMINAL_COUNT"] = counts["ACTIVE_WINDOWS"] + counts["INACTIVE_WINDOWS"]
        construction["DECLARED_COUNT_BY_YEAR"] = {y: n for y, n in counts["UNITS_BY_YEAR"].items() if n > 0}
    nuisance = ["PRIOR_REALIZED_VOLATILITY", "LAGGED_TARGET"] + (["TIME_OF_DAY"] if h["WINDOW"] != "UTC_DAY" else [])
    return {
        "CONTRACT_VERSION": K.CONTRACT_VERSION,
        "PROPOSAL_ID": h["ID"],
        "CANDIDATE_ID": f"{h['ID']}-{h['NAME']}",
        "CARD_ID": h["CARD"],
        "TEST_FAMILY_ID": card["TEST_FAMILY_ID"],
        "SEARCH_FAMILY_ID": K.SEARCH_FAMILY_ID,
        "MECHANISM": h["MECHANISM"],
        "FALSIFIABLE_CLAIM": (
            f"{estimand}, with target {h['TARGET']}, has the expected sign ({h['DIRECTION']}), magnitude at least "
            f"{K.MIN_MEANINGFUL_EFFECT} comparator-SD and a Holm-adjusted two-sided p at or below {K.FAMILY_ALPHA} within {card['TEST_FAMILY_ID']}."
        ),
        "EVENT_OR_STATE_DEFINITION": h["STATE"],
        "PRIMARY_OBSERVABLE": f"STATE_{h['NAME']}",
        "ENDPOINT_MOMENT": "SECOND_MOMENT" if h["TARGET"] == "LOG_RANGE" else "PARTICIPATION",
        "COUNTERFACTUAL_CLASS": counterfactual,
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
        "BLOCKING_ASSUMPTIONS": (
            ["Hour-specific trends in the 15:00-16:00 New York hour that are unrelated to ETFs would be attributed to the ETF era; the DiD against adjacent hours removes only afternoon-wide changes.",
             "The standardization scale (per year, common across the three hours) is label-blind.",
             "The claim is descriptive; it does not identify which participants act."] if did else
            ["Inside a month the state and comparator days share the slow participation and volatility regime, so the within-month difference removes it.",
             "Weekday composition is removed by standardizing per year and weekday class (label-blind).",
             "The claim is descriptive; it does not identify which participants act."]
        ),
        "ERA_INVARIANCE_PRIOR": "UNKNOWN",
        "ERA_INVARIANCE_RATIONALE": ("A single post-launch year; epochs are 2024 quarters and the gate is assessed, never assumed."
                                     if did else "Venue and participant structure changed between 2017-2019 and 2020-2024; the epoch gate is assessed, never assumed."),
        "QUALITATIVE_DEPENDENCE_SOURCES": ["volatility clustering across units", "shared macro weeks", "exchange outages"],
        "CLAIM_TYPE": "CONTEXT_DESCRIPTIVE",
        "TARGET_CLASS": "UNCONDITIONAL",
        "COMPLEXITY_CLASS": "ATOMIC",
        "COMPONENTS": [],
        "INTRADAY": h["WINDOW"] != "UTC_DAY",
        "VARIABLE_ROLES": {"REGIME_VARIABLES": [], "MECHANISM_VARIABLES": [f"STATE_{h['NAME']}"],
                           "NUISANCE_BASELINE_VARIABLES": nuisance},
        "NUISANCE_DIAGNOSTIC_PLANNED": True,
        "PRIMARY_CELLS": [{"REGIME": None, "ESTIMAND": estimand, "HORIZON": window_text}],
        "PRACTICAL_BAR_BASIS": "PRODUCT_RELEVANCE",
        "DISCOVERY_SURFACE": dict(K.DISCOVERY_SURFACE),
        "REPLICATION_SURFACE": replication,
        "EPOCHS": [{"ID": "2024Q1", "START": "2024-01-15", "END": "2024-04-01"},
                   {"ID": "2024Q2", "START": "2024-04-01", "END": "2024-07-01"},
                   {"ID": "2024Q3", "START": "2024-07-01", "END": "2024-10-01"},
                   {"ID": "2024Q4", "START": "2024-10-01", "END": "2025-01-01"}] if did else "CALENDAR_YEAR",
        "PRIMARY_MECHANISM_SUPPORT": [{"KIND": "BINARY", "MECHANISM_VARIABLE": f"STATE_{h['NAME']}",
                                       "MECHANISM_ACTIVE_N": counts["ACTIVE_WINDOWS"],
                                       "MECHANISM_INACTIVE_N": counts["INACTIVE_WINDOWS"]}],
        "FROZEN_OUTCOME_BLIND_SCREEN": {"PRIMARY_LABEL_ORBIT_SIZE": orbit,
                                        "MIN_ATTAINABLE_P": 1.0 / (1 + draws) if counts["UNITS"] > 0 else 1.0,
                                        "MONTE_CARLO_DRAWS": draws, "EXACT_ENUMERATION": False},
        "UNIT_COUNTS": counts,
        "REPLICATION_UNIT_COUNT": len(rep_units),
        "ALLOWED_INTERPRETATION": K.ALLOWED_INTERPRETATION,
        "FORBIDDEN_INTERPRETATION": K.FORBIDDEN_INTERPRETATION,
    }


def run_support() -> tuple[dict, dict, dict]:
    K.assert_locked()
    nyse = RD.nyse_events()
    bitmex_t = D.bitmex_timestamps()
    registry = RS.extended_registry()
    stage = {}
    for h in K.HYPOTHESES:
        disc = S.build_units(h["ID"], "DISCOVERY", nyse=nyse)
        rep_nominal = S.build_units(h["ID"], "REPLICATION") if K.CARDS[h["CARD"]]["REPLICATION"] == "BITMEX_HISTORICAL" else []
        rep = available_units(rep_nominal, bitmex_t, 5 * K.MINUTE_MS) if rep_nominal else []
        plan = planning_object(h, disc, rep)
        stage[h["ID"]] = (h, disc, rep_nominal, rep, plan, RS.compile_planning(plan, registry))
    plans, feas = {}, {}
    for hid, (h, disc, rep_nominal, rep, plan, compiled) in stage.items():
        if h["DESIGN"] == "TWO_ERA_DID":
            own = did_screen(disc)
        else:
            holm_m = sum(1 for x in stage.values()
                         if x[0]["CARD"] == h["CARD"] and x[5]["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION")
            own = paired_screen(disc, holm_m)
        rep_screen = paired_screen(rep, 1) if rep else None
        executable = compiled["FEASIBILITY_STATUS"] == "FEASIBLE_FOR_PREREGISTRATION" and not own["WEAK"]
        plans[hid] = plan
        feas[hid] = {
            "COMPILER": compiled,
            "OWN_UNIT_SCREEN": own,
            "REPLICATION_NOMINAL_UNITS": len(rep_nominal),
            "REPLICATION_AVAILABLE_UNITS": len(rep),
            "REPLICATION_UNIT_SCREEN": rep_screen,
            "EXECUTABLE": executable,
            "STATUS": "FEASIBLE_FOR_PREREGISTRATION" if executable else (
                compiled["FEASIBILITY_STATUS"] if compiled["FEASIBILITY_STATUS"] != "FEASIBLE_FOR_PREREGISTRATION"
                else "INFORMATIONALLY_WEAK_AT_UNIT_LEVEL"),
        }
    return plans, feas, registry


FEASIBILITY_MD = REPO / "docs/research/AUTOGEN_G01_FEASIBILITY.md"
FIRST_COMPILE_NOTE = (
    "First compile (same day, before freeze): G01-B1 returned `DEFINITION_INCOMPLETE / STOPPING_RULE_INVALID` "
    "because the prospective rule declared `MIN_N = 252` above `MAX_EPISODES = 104`. The 252 double-counted the "
    "frozen pre-launch arm (52 prospective + 200 pre weeks) against the stated intent of at least 52 prospective "
    "weeks. It was corrected to `MIN_N = 52` before any freeze. This is a definitional fix; it changes neither the "
    "bar, nor the discovery screen, nor the unit-level screen, and every other number below is from the recompile."
)


def feasibility_markdown(plans: dict, feas: dict) -> str:
    lines = ["# AUTOGEN_G01 — outcome-blind feasibility", "",
             "**Status:** `FEASIBILITY_COMPLETE / OUTCOMES_NOT_OPENED / NO_SURVIVOR`", f"**Date:** {K.DESIGN_DATE}",
             "**Compiler:** `GV0R02_SCHEMA_V2 / GV0R02_POLICY_V2` via `to_compiler_proposal_v1` and the R03 extended "
             "registry (both imported unchanged), plus the program's unit-level screens (paired months at the card's "
             "Holm first-step alpha; two-era weeks for card B)",
             "**Machine records:** `AUTOGEN_G01_FEASIBILITY.json`, `AUTOGEN_G01_PLANNING.json`", "",
             "| ID | Units (discovery) | State / comparator windows | n_eff (compiler) | MDE stress (compiler) | "
             "MDE stress (units) | Replication units | Replication MDE (units) | Blockers | Status |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for h in K.HYPOTHESES:
        f, p = feas[h["ID"]], plans[h["ID"]]
        c = p["UNIT_COUNTS"]
        rep = f["REPLICATION_UNIT_SCREEN"] or {}
        own = f["OWN_UNIT_SCREEN"]
        units = (f"{c['UNITS']} ({c['PRE_UNITS']} pre / {c['POST_UNITS']} post weeks)" if "PRE_UNITS" in c else f"{c['UNITS']} months")
        rep_units = (f"{f['REPLICATION_AVAILABLE_UNITS']} of {f['REPLICATION_NOMINAL_UNITS']} months (BitMEX)"
                     if f["REPLICATION_NOMINAL_UNITS"] else "prospective from 2027-01-01 (min 52 weeks)")
        rep_mde = f"{rep['MDE_STRESS']:.3f}" if rep.get("MDE_STRESS") is not None else "compiler only"
        ds = f["COMPILER"]["DISCOVERY_SCREEN"]
        lines.append(
            f"| {h['ID']} `{h['NAME']}` | {units} | {c['ACTIVE_WINDOWS']} / {c['INACTIVE_WINDOWS']} | "
            f"{(ds.get('EFFECTIVE_N') or 0):.1f} | {(ds.get('MDE_STRESS') or 0):.3f} | {own['MDE_STRESS']:.4f} | {rep_units} | "
            f"{rep_mde} | {', '.join(b['BLOCKER_CODE'] for b in f['COMPILER']['BLOCKERS']) or 'none'} | `{f['STATUS']}` |")
    lines += ["", f"Effect bar {K.MIN_MEANINGFUL_EFFECT} comparator-SD for every hypothesis (not lowered). "
              "A hypothesis is executable only if the compiler returns `FEASIBLE_FOR_PREREGISTRATION` and the unit-level "
              "MDE is at or below the bar. **No hypothesis is executable; nothing is frozen or executed.**", "",
              "## Reading", "",
              "- **G01-A1 / A2 (turn of month).** The discovery surface alone would carry the bar (unit MDE 0.486 at "
              "the Holm first-step alpha). The declared time-disjoint replication surface, 36 BitMEX months, cannot (MDE about 0.63), "
              "and the compiler requires it to. A monthly calendar clock has too few independent units per era.",
              "- **G01-A3 (month-end mark hour).** One state hour per month: discovery MDE 0.78, as expected (the R03-A2/A3 precedent).",
              "- **G01-B1 (ETF fixing window).** One post-launch year: the unit-level MDE is 0.5005, above the bar by "
              "5e-4. The prospective replication declared at 52 weeks is also underpowered. A natural experiment with a "
              "single launch has no historical replication surface.", "",
              "## Definitional correction before freeze", "", FIRST_COMPILE_NOTE, "",
              "## What is not done", "",
              "- No price, volume or trade count was read. Only calendars and BitMEX 5m bar open times (for replication availability) were used.",
              "- No closed hypothesis is repaired: the replication surface, minimum N, pre-period, block length and bar stay as declared. "
              "A later variant is a new search object with its own test family.",
              "- No 2025/2026 object, no B2-06, no product change, no API spend."]
    return "\n".join(lines) + "\n"


def main() -> None:
    plans, feas, registry = run_support()
    FEASIBILITY_MD.write_text(feasibility_markdown(plans, feas))
    PLANNING_OUT.write_text(json.dumps(_jsonable({"PROGRAM_ID": K.PROGRAM_ID, "DATASETS": D.dataset_identity(),
                                                  "PLANNING": plans}), indent=2, sort_keys=True) + "\n")
    summary = {hid: {"STATUS": f["STATUS"], "EXECUTABLE": f["EXECUTABLE"],
                     "COMPILER_STATUS": f["COMPILER"]["FEASIBILITY_STATUS"],
                     "BLOCKERS": [b["BLOCKER_CODE"] for b in f["COMPILER"]["BLOCKERS"]],
                     "EFFECTIVE_N": f["COMPILER"]["DISCOVERY_SCREEN"].get("EFFECTIVE_N"),
                     "MDE_STRESS_COMPILER": f["COMPILER"]["DISCOVERY_SCREEN"].get("MDE_STRESS"),
                     "MDE_STRESS_UNITS": f["OWN_UNIT_SCREEN"]["MDE_STRESS"],
                     "N_UNITS": plans[hid]["UNIT_COUNTS"]["UNITS"],
                     "REPLICATION_AVAILABLE_UNITS": f["REPLICATION_AVAILABLE_UNITS"],
                     "REPLICATION_MDE_STRESS_UNITS": (f["REPLICATION_UNIT_SCREEN"] or {}).get("MDE_STRESS")}
               for hid, f in feas.items()}
    FEASIBILITY_OUT.write_text(json.dumps(_jsonable({
        "PROGRAM_ID": K.PROGRAM_ID, "SUMMARY": summary,
        "FEATURE_REGISTRY": {k: registry[k] for k in ("FEATURE_REGISTRY_DIGEST", "EXTENDED_FROM_FROZEN_DIGEST", "EXTENSION_ROWS")},
        "DETAIL": feas, "MARKET_OUTCOMES_OPENED": False, "MARKET_VALUES_READ": False,
        "TIMESTAMPS_READ": ["BitMEX 5m bar open times (replication availability)"]}), indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
