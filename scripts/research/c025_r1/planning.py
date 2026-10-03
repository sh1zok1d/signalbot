"""Sealed GV0R03 V1 planning object for C025-R1, compiled with GV0R02 V2.

The builder copies counts into the proposal. It does not open a post-T target
and it does not change the practical bar.
"""

from __future__ import annotations

from scripts.research import gv0r02_feasibility_compiler_v2 as v2
from scripts.research.generator_v0.feasibility_contract_v1 import to_compiler_proposal_v1

from .constants import (
    ALLOWED_INTERPRETATION,
    CLAIM_TYPE,
    COMPLEXITY_CLASS,
    DATASET_ID,
    DESIGN_VERSION,
    DISCOVERY_END_EXCLUSIVE,
    DISCOVERY_START,
    EFFECT_UNITS,
    ENDPOINT_MOMENT,
    EXPECTED_DIRECTION,
    FORBIDDEN_INTERPRETATION,
    HISTORICAL_WINDOW,
    MECHANISM_VARIABLE,
    MIN_MEANINGFUL_EFFECT,
    MONTE_CARLO_P_FLOOR,
    NAMED_INFERENCE_CLASS,
    NUISANCE_VARIABLES,
    ORIGINAL_CARD_CHANGED,
    ORIGINAL_FEASIBILITY_FAILED_CHECKS,
    ORIGINAL_FEASIBILITY_VERDICT,
    ORIGINAL_NOVELTY_VERDICT,
    ORIGINAL_RED_TEAM_FAILED_CHECKS,
    ORIGINAL_RED_TEAM_VERDICT,
    OVERRIDE_REASON,
    PERMUTATION_DRAWS,
    PERMUTATION_SEED,
    PLACEBO_DRAWS,
    PLACEBO_P_FLOOR,
    PLACEBO_SEED,
    PRACTICAL_BAR_BASIS,
    PRIMARY_ALPHA,
    PRIMARY_CLAIM,
    PRIMARY_QUANTILE,
    PRIMARY_THETA,
    PRIMARY_W_MINUTES,
    PRODUCT_EXPOSURE_HANDLING,
    PROPOSAL_ID,
    PROSPECTIVE_ARM_FLOOR,
    PROSPECTIVE_END_DATE,
    PROSPECTIVE_ID,
    PROSPECTIVE_MAX_EPISODES,
    PROSPECTIVE_MIN_N,
    PROSPECTIVE_START,
    R1_REASON,
    SELECTION_PIPELINE_OVERRIDDEN,
    SOURCE_CAMPAIGN,
    SOURCE_CARD,
    SOURCE_RUN_ID,
    TARGET_CLASS,
    TWO_SIDED_MAX,
)


def _operational_min_p(orbit: int, one: int, two: int) -> float:
    if one <= 0 or two <= 0 or orbit <= 1:
        return 1.0
    if orbit > PERMUTATION_DRAWS:
        return MONTE_CARLO_P_FLOOR
    return 1.0 / float(orbit)


def build_planning(support: dict) -> dict:
    """Outcome-blind planning object. `support` carries counts, not targets."""
    match = support["MATCHING"]
    one = int(match["MATCHABLE_ONE_SIDED_N"])
    two = int(match["MATCHABLE_TWO_SIDED_N"])
    by_year_arm = support["COUNT_BY_YEAR_ARM"]
    declared_year = {}
    for year, row in by_year_arm.items():
        total = int(row["ONE_SIDED"]) + int(row["TWO_SIDED"])
        if total > 0:
            declared_year[str(year)] = total
    nominal = one + two
    construction = {
        "COUNTING_UNIT": "DECLUSTERED_MATCHED_BURST",
        "WINDOW": HISTORICAL_WINDOW,
        "INCLUSION_RULE": (
            "BTCUSDT perpetual 1m bar in 2020-01..2024-12 whose quote volume is at or above "
            "the linear quantile 0.999 of the preceding 43200 quote volumes, whose one-sidedness "
            "is either >= 0.70 or <= 0.30, with a positive pre-impact over the preceding 60 minutes, "
            "and with no previously accepted event in the preceding 60 minutes."
        ),
        "EXCLUSION_RULE": (
            "Bars before the 30-day trailing window, neither-arm bursts, events inside the "
            "past-only 60-minute refractory, and events whose pre-impact is not positive. "
            "No post-T filter is applied in this count."
        ),
        "OUTCOME_FILTER": "NONE",
    }
    if nominal > 0:
        construction["DECLARED_NOMINAL_COUNT"] = nominal
    if declared_year:
        construction["DECLARED_COUNT_BY_YEAR"] = declared_year
    orbit = int(match["PRIMARY_LABEL_ORBIT_SIZE"])
    min_p = _operational_min_p(orbit, one, two)
    planning = {
        "CONTRACT_VERSION": "GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V1",
        "PROPOSAL_ID": PROPOSAL_ID,
        "CANDIDATE_ID": SOURCE_CARD,
        "DESIGN_VERSION": DESIGN_VERSION,
        "MEMORY_CAMPAIGN_ID": SOURCE_CAMPAIGN,
        "SOURCE_RUN_ID": SOURCE_RUN_ID,
        "SELECTION_PIPELINE_OVERRIDDEN": SELECTION_PIPELINE_OVERRIDDEN,
        "OVERRIDE_REASON": OVERRIDE_REASON,
        "ORIGINAL_CARD_CHANGED": ORIGINAL_CARD_CHANGED,
        "R1_REASON": R1_REASON,
        "ORIGINAL_CRITIC_VERDICTS": {
            "NOVELTY_VERDICT": ORIGINAL_NOVELTY_VERDICT,
            "FEASIBILITY_VERDICT": ORIGINAL_FEASIBILITY_VERDICT,
            "FEASIBILITY_FAILED_CHECKS": list(ORIGINAL_FEASIBILITY_FAILED_CHECKS),
            "RED_TEAM_VERDICT": ORIGINAL_RED_TEAM_VERDICT,
            "RED_TEAM_FAILED_CHECKS": list(ORIGINAL_RED_TEAM_FAILED_CHECKS),
        },
        "MECHANISM": (
            "At a high-volume minute, taker flow that is strongly one-sided is associated "
            "with a larger subsequent impact-per-volume than a two-sided burst of similar "
            "pre-T conditions. The association is the claim. It is consistent with makers "
            "carrying inventory after the burst. It does not prove that inventory constraints "
            "caused the path."
        ),
        "FALSIFIABLE_CLAIM": (
            "The preregistered claim fails unless the matched one-sided minus two-sided "
            "IMPACT_RATIO at 30 minutes is positive, the stratum-permutation p-value is at "
            "most 0.05, the standardized contrast is at least 0.30 SD, the contrast exceeds "
            "the mechanical-reversion placebo at the same alpha, and at least 3 of 5 calendar "
            "years have a positive point estimate."
        ),
        "EVENT_OR_STATE_DEFINITION": (
            f"Primary cell only. BURST when quote volume >= linear quantile {PRIMARY_QUANTILE} "
            f"of the preceding {43200} minutes. ONE_SIDE = 2*|taker_buy_quote/quote - 0.5|. "
            f"One-sided if ONE_SIDE >= {PRIMARY_THETA}. Two-sided if ONE_SIDE <= {TWO_SIDED_MAX}. "
            "Admit only if the preceding 60 minutes contain no already accepted event. "
            "Do not drop an admitted event because a later burst falls inside its outcome window."
        ),
        "PRIMARY_OBSERVABLE": MECHANISM_VARIABLE,
        "ENDPOINT_MOMENT": ENDPOINT_MOMENT,
        "COUNTERFACTUAL_CLASS": (
            "Permute ONE_SIDED versus TWO_SIDED labels within the frozen matched strata. "
            f"{PERMUTATION_DRAWS} draws, seed {PERMUTATION_SEED}, "
            "p = (1 + count(T_perm >= T_obs)) / (1 + permutations)."
        ),
        "NAMED_INFERENCE_CLASS": NAMED_INFERENCE_CLASS,
        "HISTORICAL_WINDOW": HISTORICAL_WINDOW,
        "POINT_IN_TIME_REQUIREMENTS": [{"DATASET_ID": DATASET_ID, "PIT_STATUS": "VERIFIED"}],
        "NOMINAL_OBSERVATION_COUNT_CONSTRUCTION": construction,
        "DEPENDENCE_CLUSTERING_UNIT": "60M_PAST_ONLY_REFRACTORY",
        "ERA_ROLES": {
            "BINANCE_2020_2024": "DISCOVERY",
            "BITMEX_2016_2019": "HISTORICAL_REPLICATION_CANDIDATE",
            "Y2025_2026": "PROTECTED_HOLDOUT",
        },
        "EXPECTED_EFFECT": {
            "DIRECTION": EXPECTED_DIRECTION,
            "MIN_MEANINGFUL_EFFECT": MIN_MEANINGFUL_EFFECT,
            "UNITS": EFFECT_UNITS,
            "RATIONALE": (
                "A one-sided-versus-two-sided difference smaller than 0.30 SD of the "
                "impact-ratio contrast is below the planning bar for a product-relevant "
                "liquidity-state description. The bar was set before C025 outcomes."
            ),
        },
        "REQUIRED_STRESS_SCREENS": ["STRESS_SD_MULTIPLIER", "HOMOGENEOUS_EFFECT", "ZERO_EFFECT_IN_ONE_ERA"],
        "FEATURE_REQUIREMENTS": [DATASET_ID],
        "DATA_SOURCE_REFS": {
            "FEATURE_REGISTRY_VERSION": "GV0R02_FEATURE_REGISTRY_V0",
            "FEATURE_IDS": [DATASET_ID],
        },
        "BLOCKING_ASSUMPTIONS": [
            "Arm labels are exchangeable inside a frozen stratum under the null.",
            "The 60-minute refractory removes admitted-event overlap but residual dependence can remain.",
            "A later burst inside the outcome window is contamination, not a reason to drop the event.",
            "The contrast is associative. It does not identify maker inventory as the cause.",
            PRIMARY_CLAIM,
        ],
        "ERA_INVARIANCE_PRIOR": "NOT_EXPECTED",
        "ERA_INVARIANCE_RATIONALE": (
            "The frozen stability rule allows up to two of the five calendar years to miss "
            "the pooled positive sign. Cross-year invariance is not assumed."
        ),
        "QUALITATIVE_DEPENDENCE_SOURCES": [
            "volatility clustering",
            "overlapping pre-windows",
            "residual clustering beyond the 60-minute refractory",
            "shared UTC-hour liquidity",
        ],
        "CLAIM_TYPE": CLAIM_TYPE,
        "TARGET_CLASS": TARGET_CLASS,
        "COMPLEXITY_CLASS": COMPLEXITY_CLASS,
        "COMPONENTS": [],
        "INTRADAY": True,
        "VARIABLE_ROLES": {
            "REGIME_VARIABLES": [],
            "MECHANISM_VARIABLES": [MECHANISM_VARIABLE],
            "NUISANCE_BASELINE_VARIABLES": list(NUISANCE_VARIABLES),
        },
        "PRIMARY_CELLS": [
            {
                "REGIME": "ELIGIBLE_HIGH_VOLUME_BTC_PERP_BURSTS",
                "ESTIMAND": "standardized matched one-sided minus two-sided DELTA_IMPACT",
                "HORIZON": "30m",
            }
        ],
        "PRACTICAL_BAR_BASIS": PRACTICAL_BAR_BASIS,
        "DISCOVERY_SURFACE": {
            "ID": "BINANCE_2020_2024",
            "START": DISCOVERY_START,
            "END": DISCOVERY_END_EXCLUSIVE,
        },
        "REPLICATION_SURFACE": {
            "KIND": "PROSPECTIVE",
            "ID": PROSPECTIVE_ID,
            "START": PROSPECTIVE_START,
            "STARTS_AFTER_FREEZE": True,
            "STOPPING_RULE": {
                "MIN_MECHANISM_ACTIVE_N": PROSPECTIVE_ARM_FLOOR,
                "MIN_MECHANISM_INACTIVE_N": PROSPECTIVE_ARM_FLOOR,
                "MIN_N": PROSPECTIVE_MIN_N,
                "MAX_EPISODES": PROSPECTIVE_MAX_EPISODES,
                "END_DATE": PROSPECTIVE_END_DATE,
                "COUNTS_ONLY_MONITORING": True,
                "PRODUCT_EXPOSURE_HANDLING": PRODUCT_EXPOSURE_HANDLING,
            },
        },
        "EPOCHS": "CALENDAR_YEAR",
        "PRIMARY_FREEZE": {
            "ONE_SIDE_THETA": PRIMARY_THETA,
            "VOLUME_QUANTILE": PRIMARY_QUANTILE,
            "W_MINUTES": PRIMARY_W_MINUTES,
            "TWO_SIDED_MAX": TWO_SIDED_MAX,
            "PERMUTATION_SEED": PERMUTATION_SEED,
            "PERMUTATION_DRAWS": PERMUTATION_DRAWS,
            "PLACEBO_SEED": PLACEBO_SEED,
            "PLACEBO_DRAWS": PLACEBO_DRAWS,
            "MIN_MEANINGFUL_EFFECT": MIN_MEANINGFUL_EFFECT,
        },
        "MATCHING_LEVEL": match.get("LEVEL"),
        "MATCHING_STATUS": match.get("STATUS"),
        "ALLOWED_INTERPRETATION": ALLOWED_INTERPRETATION,
        "FORBIDDEN_INTERPRETATION": FORBIDDEN_INTERPRETATION,
        "FROZEN_OUTCOME_BLIND_SCREEN": {
            "PRIMARY_LABEL_ORBIT_SIZE": str(orbit),
            "MIN_ATTAINABLE_P": min_p,
            "MONTE_CARLO_DRAWS": PERMUTATION_DRAWS,
            "MONTE_CARLO_P_FLOOR": MONTE_CARLO_P_FLOOR,
            "EXACT_ENUMERATION": False,
        },
        "PRIMARY_MECHANISM_SUPPORT": [
            {
                "KIND": "BINARY",
                "MECHANISM_VARIABLE": MECHANISM_VARIABLE,
                "MECHANISM_ACTIVE_N": one,
                "MECHANISM_INACTIVE_N": two,
            }
        ],
        "ALPHA_REFERENCE": PRIMARY_ALPHA,
        "PLACEBO_P_FLOOR": PLACEBO_P_FLOOR,
    }
    return planning


def compile_planning(planning: dict) -> dict:
    proposal = to_compiler_proposal_v1(planning)
    proposal["COMPILER_SCHEMA_VERSION"] = v2.COMPILER_SCHEMA_VERSION
    proposal["COMPILER_POLICY_VERSION"] = v2.COMPILER_POLICY_VERSION
    proposal["PRIMARY_MECHANISM_SUPPORT"] = [dict(row) for row in planning["PRIMARY_MECHANISM_SUPPORT"]]
    proposal["FROZEN_OUTCOME_BLIND_SCREEN"] = dict(planning["FROZEN_OUTCOME_BLIND_SCREEN"])
    # Orbit may be a decimal string. The compiler stores it; min p is already set.
    screen = proposal["FROZEN_OUTCOME_BLIND_SCREEN"]
    screen["PRIMARY_LABEL_ORBIT_SIZE"] = int(screen["PRIMARY_LABEL_ORBIT_SIZE"]) if len(screen["PRIMARY_LABEL_ORBIT_SIZE"]) < 18 else screen["PRIMARY_LABEL_ORBIT_SIZE"]
    return v2.compile_proposal_v2(proposal)
