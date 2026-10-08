"""Frozen design constants for LEVEL_STRUCTURE_DISCOVERY_V1.

Chosen before any feature-conditioned break, reject or neither rate was read.
Do not change these to improve a result. This unit does not inherit the 70% DAY cap
from LEVEL_APPROACH_STATE_DISCOVERY_V1.
"""

from __future__ import annotations

UNIT = "LEVEL_STRUCTURE_DISCOVERY_V1"
FAMILY = "LEVEL_BEHAVIOR_V1"
MODE = "DISCOVERY"
TRACKS = ("STRUCTURE", "PRODUCT_EVIDENCE")
CLAIM_CEILING = "L2"
SOURCE_MAIN_HEAD = "1a2e425303fb29e1044ca57452b8ad9b6f0a831b"

DEPENDENCY_TOUCH_SHA = "dfc9e0f04358de15606382472badeb5aee787039"
DEPENDENCY_MEMORY_SHA = "c3d39bffda861b535605a98205d7578c0c84c782"
DEPENDENCY_METHOD_SHA = "8effe9acc3b88b925a79b33f04ac0ee9e6f93e26"
DEPENDENCY_APPROACH_SHA = "aa85e5b43c405ee225336ff385e3a3383fa59d09"

# Parent volatility terciles. Same scale as LEVEL_TOUCH_DEGRADATION_V1. Not refit here.
PARENT_SIGMA_LO = 0.0012364306616934476
PARENT_SIGMA_HI = 0.001790567553180052

# A bar trades "at" the source extreme when it reaches within this fraction of the final print.
# Frozen before outcomes. Not the confluence tolerance 0.0015.
EXTREME_TOL = 0.0005
# Prior completed periods of the same family. The source period itself is not in the baseline.
FORMATION_BASE = 20
FORMATION_MIN = 4
MIN_PRESENT = 0.9

# Outcome-blind redundancy and missingness.
REDUNDANCY_RHO = 0.90
MISSING_MAX = 0.01
# A count that never exceeds 2, or whose non-singleton share is below this, is a binary
# multi-vs-singleton contrast. At or above this share of count>=3, the integer count is
# the continuous predictor. Decided from the predictor distribution only.
COUNT_GE3_SHARE = 0.05

RAW_FEATURES = (
    "age",
    "confluence",
    "diversity",
    "zone_span",
    "formation_range",
    "formation_volume",
    "close_off_extreme",
    "extreme_timing",
    "extreme_density",
)
# Earlier features win a redundancy tie. Age is the duration nuisance for the others.
KEEP_ORDER = RAW_FEATURES
AGE_NUISANCE = "age"

OUTCOMES = ("BREAK", "REJECT", "NEITHER")
HORIZON = 48

BOOT_DRAWS = 2000
BOOT_SEED = 20261011
BOOT_MIN_VALID_FRAC = 0.9
CI_ALPHA = 0.05
FDR_Q = 0.10
# Per 1 SD, or per the binary contrast. Parent level-reaction reading scale. Not a 0.5 SD bar.
PRACTICAL_SCALE = 0.03
YEAR_MIN_N = 30
YEAR_SIGN_MIN = 4
FAMILY_SIGN_MIN = 2
LOFO_MIN_N = 30
L2_MIN_N = 30

YEARS = (2020, 2021, 2022, 2023, 2024)
FAMILIES = ("DAY", "WEEK", "MONTH")

# Approach-path sensitivity. Scales are frozen in the preflight. The fit runs only for a
# relation that already passed the successor rule. It cannot name a new candidate.
APPROACH_FEATURES = (
    "velocity",
    "efficiency",
    "persistence",
    "acceleration",
    "range_state",
    "rel_volume",
    "dwell",
)


def cells_per_feature_outcome() -> int:
    """Primary stacked Δ, no-touch companion, shape contrast, 5 years, 3 families, 2 sides,
    3 touch ordinals, 5 leave-one-year-out, 3 leave-one-family-out.
    """
    return 1 + 1 + 1 + 5 + 3 + 2 + 3 + 5 + 3


def material_cells(n_retained: int) -> int:
    return int(n_retained) * len(OUTCOMES) * cells_per_feature_outcome()


def fdr_family_size(n_retained: int) -> int:
    return int(n_retained) * len(OUTCOMES)
