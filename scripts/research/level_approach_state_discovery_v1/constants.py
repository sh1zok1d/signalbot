"""Frozen design constants for LEVEL_APPROACH_STATE_DISCOVERY_V1.

Chosen before any touch outcome rate was read. Do not change these to improve a result.
A relation selected after the outcomes is DISCOVERY_ONLY and needs its own confirmation unit.
"""

from __future__ import annotations

UNIT = "LEVEL_APPROACH_STATE_DISCOVERY_V1"
FAMILY = "LEVEL_BEHAVIOR_V1"
MODE = "DISCOVERY"
TRACKS = ("STRUCTURE", "PRODUCT_EVIDENCE")
CLAIM_CEILING = "L2"  # family-level statement only; a selected cell is DISCOVERY_ONLY
SOURCE_MAIN_HEAD = "1a2e425303fb29e1044ca57452b8ad9b6f0a831b"

DEPENDENCY_TOUCH_UNIT = "LEVEL_TOUCH_DEGRADATION_V1"
DEPENDENCY_TOUCH_PR = 352
DEPENDENCY_TOUCH_SHA = "dfc9e0f04358de15606382472badeb5aee787039"
DEPENDENCY_MEMORY_UNIT = "LEVEL_REJECTION_MEMORY_V1"
DEPENDENCY_MEMORY_PR = 353
DEPENDENCY_MEMORY_SHA = "c3d39bffda861b535605a98205d7578c0c84c782"
DEPENDENCY_METHOD_PR = 354
DEPENDENCY_METHOD_SHA = "8effe9acc3b88b925a79b33f04ac0ee9e6f93e26"

# Parent volatility terciles. Same scale as LEVEL_TOUCH_DEGRADATION_V1. Not refit here.
PARENT_SIGMA_LO = 0.0012364306616934476
PARENT_SIGMA_HI = 0.001790567553180052

# Approach geometry. D = BAND_MULT * primary X. One sensitivity widens the band only.
BAND_MULT_PRIMARY = 1.0
BAND_MULT_SENSITIVITY = 2.0
MIN_APPROACH_BARS = 4          # in-band bars; also the close-to-close steps, so each half has >= 2
DWELL_FRAC = 0.5               # inner band is this fraction of primary X, not of the sensitivity band
RANGE_RECENT = 6               # last 30 minutes before the touch bar
RANGE_BASE = 288               # 24h ending at the same pre-touch bar; recent sits inside it
MIN_PRESENT = 0.9
VOLUME_MISSING_MAX = 0.01      # above this, rel_volume leaves the family before any outcome

# Redundancy is outcome-blind. |rho| at or above this drops the later feature.
REDUNDANCY_RHO = 0.90
# pullback is the algebraic complement of efficiency and is never a model feature.
RAW_FEATURES = (
    "velocity",       # F1
    "efficiency",     # F2
    "pullback",       # F3, dropped analytically
    "persistence",    # F4
    "acceleration",   # F5
    "range_state",    # F6
    "rel_volume",     # F7, subject to the volume audit
    "dwell",          # F8
)
# Greedy keep order after pullback is removed. Earlier features win a redundancy tie.
KEEP_ORDER = (
    "velocity",
    "efficiency",
    "persistence",
    "acceleration",
    "range_state",
    "rel_volume",
    "dwell",
)
DURATION_NUISANCE = "log_steps"

OUTCOMES = ("BREAK", "REJECT", "NEITHER")
HORIZON = 48  # 4h only. No second horizon.

BOOT_DRAWS = 2000
BOOT_SEED = 20261009
BOOT_MIN_VALID_FRAC = 0.9
CI_ALPHA = 0.05
FDR_Q = 0.10
PRACTICAL_SCALE = 0.03  # per 1 SD; the level-reaction reading scale used by the parent units
YEAR_MIN_N = 30
YEAR_SIGN_MIN = 4
FAMILY_SIGN_MIN = 2
MAX_FAMILY_SHARE = 0.70
CONTROL_HALF = 0.5
L2_MIN_N = 30

YEARS = (2020, 2021, 2022, 2023, 2024)
FAMILIES = ("DAY", "WEEK", "MONTH")

# feature_z stays in column 1 so the reported coefficient is always that slot.
PRIMARY_COLUMNS = (
    "intercept",
    "feature_z",
    "touch2",
    "touch3",
    "fam_week",
    "fam_month",
    "support",
    "vol_mid",
    "vol_high",
    "log_steps_z",
    "y2021",
    "y2022",
    "y2023",
    "y2024",
)


def cells_per_feature_outcome() -> int:
    """primary, no-touch, no-duration, tertile, sensitivity, control, 5 years, 3 families, 2 sides, 5 LOYO."""
    return 6 + 5 + 3 + 2 + 5


def material_cells(n_retained: int) -> int:
    return int(n_retained) * len(OUTCOMES) * cells_per_feature_outcome()


def fdr_family_size(n_retained: int) -> int:
    return int(n_retained) * len(OUTCOMES)
