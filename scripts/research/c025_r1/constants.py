"""Frozen C025-R1 design constants.

Confirmatory parameters are owner-locked. Nothing in this module reads a
market target. Non-primary search-surface cells are recorded so they can be
shown to be outside the verdict path; they are not estimated.
"""

from __future__ import annotations

DESIGN_VERSION = "C025-R1"
SOURCE_CARD = "C025"
SOURCE_CAMPAIGN = "GV0V03L40"
SOURCE_RUN_ID = "ladder-40-card-v03-r02-derived-critics-v2"
PROPOSAL_ID = "GV0V03L40-C025-R1"

SELECTION_PIPELINE_OVERRIDDEN = True
OVERRIDE_REASON = (
    "Owner-authorized scientific audit of C025 after questioning critic rejection; "
    "original critic judgments remain immutable."
)
ORIGINAL_CARD_CHANGED = False
R1_REASON = "PRE_OUTCOME_NO_LOOKAHEAD_REPAIR"

# Immutable critic record. Not a new judgment.
ORIGINAL_NOVELTY_VERDICT = "REJECT"
ORIGINAL_FEASIBILITY_VERDICT = "REJECT"
ORIGINAL_RED_TEAM_VERDICT = "REJECT"
ORIGINAL_RED_TEAM_FAILED_CHECKS = ("CAUSALITY", "CONFOUNDING_ADDRESSED", "NO_LOOKAHEAD")
ORIGINAL_FEASIBILITY_FAILED_CHECKS = ("BLOCKER_RESOLVED",)

CLAIM_TYPE = "INCREMENTAL"
TARGET_CLASS = "UNCONDITIONAL"
COMPLEXITY_CLASS = "ATOMIC"
ENDPOINT_MOMENT = "OTHER"
PRACTICAL_BAR_BASIS = "PRODUCT_RELEVANCE"
NAMED_INFERENCE_CLASS = "PERMUTATION_GROUP_INVARIANCE"

# Owner-locked confirmatory cell. First-listed theta, first-listed quantile,
# and the horizon the original falsifier names.
PRIMARY_THETA = 0.70
PRIMARY_QUANTILE = 0.999
PRIMARY_W_MINUTES = 30
TWO_SIDED_MAX = 0.30
REFRACTORY_MINUTES = 60
PRE_WINDOW_MINUTES = 60
TRAIL_DAYS = 30
TRAIL_BARS = TRAIL_DAYS * 24 * 60  # 43200 complete 1m bars

MIN_MEANINGFUL_EFFECT = 0.30
EFFECT_UNITS = "STANDARDIZED_DELTA_IMPACT_SD"
PRIMARY_ALPHA = 0.05
EXPECTED_DIRECTION = "POSITIVE"

PERMUTATION_DRAWS = 10_000
PERMUTATION_SEED = 250251
PLACEBO_DRAWS = 1_000
PLACEBO_SEED = 250252
PLACEBO_MAX_PER_STRATUM = 40
# +1 Monte Carlo correction. Operational resolution of the primary test.
MONTE_CARLO_P_FLOOR = 1.0 / (1.0 + PERMUTATION_DRAWS)
PLACEBO_P_FLOOR = 1.0 / (1.0 + PLACEBO_DRAWS)

# Matching acceptance, chosen before any post-T target. Counts and covariate
# balance only. A level is the first in LEVEL_ORDER that meets all three.
MATCH_MIN_ARM = 30
MATCH_MIN_RETENTION = 0.40
MATCH_MAX_ABS_SMD = 0.50

# Execution support floor relative to the frozen preflight effective N.
# Below this, the preregistered test is informationally weak.
EXECUTION_NEFF_RETAINED = 0.80

# Prospective replication. Arm floors are the smallest equal counts whose
# binary effective N meets GV0R02 stress power 0.80 at 0.30 SD. Derived from
# the frozen profile, not from 2025/2026 frequency.
PROSPECTIVE_ID = "BINANCE_PROSPECTIVE_C025_R1"
PROSPECTIVE_START = "2027-01-01"
PROSPECTIVE_END_DATE = "2032-12-31"
PROSPECTIVE_ARM_FLOOR = 698
PROSPECTIVE_MIN_N = PROSPECTIVE_ARM_FLOOR * 2  # 1396
PROSPECTIVE_MAX_EPISODES = 8000
PRODUCT_EXPOSURE_HANDLING = (
    "hidden from product users until replication stopping rule fires and the "
    "replication outcome is separately authorized"
)

DISCOVERY_START = "2020-01-01"
DISCOVERY_END_EXCLUSIVE = "2025-01-01"
HISTORICAL_WINDOW = "2020-01..2024-12"
DATASET_ID = "CORE_BTC_BINANCE_V0"
DATASET_MANIFEST_DIGEST = "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"

FUNDING_MINUTES = 15  # [settlement-15m, settlement+15m): distance < 15

# The other 11 generated cells. Not confirmatory and not estimated.
_SURFACE_THETA = (0.7, 0.8)
_SURFACE_Q = (0.999, 0.9995)
_SURFACE_W = (15, 30, 60)
PRIMARY_VARIANT = (PRIMARY_THETA, PRIMARY_QUANTILE, PRIMARY_W_MINUTES)
NON_PRIMARY_VARIANTS = tuple(
    (theta, q, w)
    for theta in _SURFACE_THETA
    for q in _SURFACE_Q
    for w in _SURFACE_W
    if (theta, q, w) != (0.7, 0.999, 30)
)

MECHANISM_VARIABLE = "ONE_SIDED_BURST"
NUISANCE_VARIABLES = (
    "PRIOR_REALIZED_VOLATILITY",
    "LAGGED_TARGET",
    "TIME_OF_DAY",
    "ABS_BURST_RETURN",
    "BURST_VOLUME_TAIL_RANK",
    "CALENDAR_YEAR",
    "FUNDING_SETTLEMENT_INDICATOR",
)

PRIMARY_CLAIM = (
    "At matched high-volume BTC perpetual bursts, strong taker one-sidedness is "
    "associated with greater subsequent impact-per-volume persistence than a two-sided burst."
)
ALLOWED_INTERPRETATION = "consistent with maker inventory loading"
FORBIDDEN_INTERPRETATION = "proves maker inventory constraints caused the effect"


def assert_locked_primary(**overrides) -> None:
    """Confirmatory entry points call this. Any override is a design breach."""
    if overrides:
        raise RuntimeError("C025-R1 primary variant is frozen and cannot be overridden: " + ",".join(overrides))
    if len(NON_PRIMARY_VARIANTS) != 11:
        raise RuntimeError("expected 11 non-primary variants")
    if PRIMARY_VARIANT in NON_PRIMARY_VARIANTS:
        raise RuntimeError("primary variant leaked into the non-primary list")
    if PROSPECTIVE_MIN_N > PROSPECTIVE_MAX_EPISODES:
        raise RuntimeError("prospective MIN_N exceeds MAX_EPISODES")
    if PROSPECTIVE_ARM_FLOOR != 698 or MIN_MEANINGFUL_EFFECT != 0.30:
        raise RuntimeError("practical bar or prospective floor drifted")
