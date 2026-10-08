"""Frozen design constants for LEVEL_REJECTION_MEMORY_V1.

Chosen before any next-touch break rate was read. Do not change these to improve a result.
"""

from __future__ import annotations

UNIT = "LEVEL_REJECTION_MEMORY_V1"
FAMILY = "LEVEL_BEHAVIOR_V1"
TRACKS = ("STRUCTURE", "PRODUCT_EVIDENCE")
CLAIM_CEILING = "L2"
DEPENDENCY_UNIT = "LEVEL_TOUCH_DEGRADATION_V1"
DEPENDENCY_PR = 352
DEPENDENCY_SHA = "dfc9e0f04358de15606382472badeb5aee787039"
SOURCE_MAIN_HEAD = "1a2e425303fb29e1044ca57452b8ad9b6f0a831b"

# Parent volatility terciles, frozen in that unit's outcome-blind preflight.
# Reused so "vol state" is the same scale. Not refit on this unit's outcomes.
PARENT_SIGMA_LO = 0.0012364306616934476
PARENT_SIGMA_HI = 0.001790567553180052

BOOT_DRAWS = 2000
BOOT_SEED = 20261008
BOOT_MIN_VALID_FRAC = 0.9
CI_ALPHA = 0.05
PRACTICAL_SCALE = 0.03  # per 1 SD; parent reading scale, not a Holm switch
PLANNING_Z = 1.959963984540054 + 0.8416212335729143
PLANNING_RATE = 0.5
PLANNING_DEFF = 1.25
YEAR_MIN_N = 30
YEAR_SIGN_MIN = 4
MAX_YEAR_SHARE = 0.40
MAX_FAMILY_SHARE = 0.70
MIN_CLUSTERS = 100
CONTROL_HALF = 0.5
L2_MIN_N = 30

N_PRIMARY = 1
N_CONTRASTS = 28

YEARS = (2020, 2021, 2022, 2023, 2024)
FAMILIES = ("DAY", "WEEK", "MONTH")

# Primary LPM columns. speed_z is the only claim coefficient.
PRIMARY_COLUMNS = (
    "intercept",
    "speed_z",
    "touch3",
    "fam_week",
    "fam_month",
    "support",
    "vol_mid",
    "vol_high",
    "gap_z",
    "y2021",
    "y2022",
    "y2023",
    "y2024",
)
SPEED_COLUMN = "speed_z"
