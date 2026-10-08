"""Frozen design constants for LEVEL_ACCEPTANCE_PATH_DISCOVERY_V1.

Chosen before any path state was joined to a late BREAK label.
Do not change these after an outcome is read. Parent level geometry is imported.
"""

from __future__ import annotations

from scripts.research.level_post_touch_reaction_discovery_v1 import constants as RX
from scripts.research.level_touch_degradation_v1 import constants as PARENT

UNIT = "LEVEL_ACCEPTANCE_PATH_DISCOVERY_V1"
FAMILY = "LEVEL_BEHAVIOR_V1"
MODE = "DISCOVERY"
TRACKS = ("STRUCTURE", "PRODUCT_EVIDENCE")
CLAIM_CEILING = "L2"
EXPOSURE_STATUS = "DISCOVERY_ONLY"
PRODUCT_INTEGRATION_CANDIDATE = False
SOURCE_MAIN_HEAD = "1a2e425303fb29e1044ca57452b8ad9b6f0a831b"

DEPENDENCY_TOUCH_SHA = "dfc9e0f04358de15606382472badeb5aee787039"
DEPENDENCY_MEMORY_SHA = "c3d39bffda861b535605a98205d7578c0c84c782"
DEPENDENCY_METHOD_SHA = "8effe9acc3b88b925a79b33f04ac0ee9e6f93e26"
DEPENDENCY_APPROACH_SHA = "aa85e5b43c405ee225336ff385e3a3383fa59d09"
DEPENDENCY_STRUCTURE_SHA = "f8623d3281424c165ebd7ee7fbcb0af994cc1e8d"
DEPENDENCY_CONFIRM_SHA = "c1cd4e0102e700f7860d21a9af0d243c3bc367be"
DEPENDENCY_POSITION_SHA = "e6e5f307cfa098db607544a556bae01a2310eb6a"
DEPENDENCY_JOINT_SHA = "bcc0a9e8a5c2af221b23b72768d7b7ba1d6a4aa2"
DEPENDENCY_LIQUIDITY_SHA = "181debc4aa626637f2cd560103447d2d4adc96b1"
DEPENDENCY_REACTION_SHA = "44726ded55c75fefecc6848ab8b76971ead83721"

CORE_DATASET_ID = "CORE_BTC_BINANCE_V0"
CORE_ZIP_LIST_SHA256 = "936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b"
# Parent #352 volatility terciles. Copied as numbers. Not refit on this cohort.
PARENT_SIGMA_LO = 0.0012364306616934476
PARENT_SIGMA_HI = 0.001790567553180052

EVENT_START = "2020-02-01T00:00:00+00:00"
EVENT_END = "2025-01-01T00:00:00+00:00"
EVENT_START_MS = PARENT.EVENT_START_MS
EVENT_END_MS = PARENT.SURFACE_END_MS

MINUTE_MS = 60_000
BAR_MS = 300_000
HOUR_MS = 3_600_000
PRE_BARS = 12
REACTION_BARS = 3
REACTION_MS = 15 * MINUTE_MS
HORIZON = 48
EARLY_START_OFFSET = 1
EARLY_STOP_OFFSET = 3
LATE_START_OFFSET = 3
LATE_STOP_OFFSET = 49

SEQUENCES = ("000", "001", "010", "011", "100", "101", "110", "111")
STATES = (
    "NEVER_OUTSIDE",
    "REENTERED",
    "LATE_OR_RECROSS_OUTSIDE",
    "PERSISTENT_OUTSIDE",
)
CONTRASTS = ("REENTRY_MEMORY", "PERSISTENCE_MEMORY")
CONTRAST_INDEX = {"REENTRY_MEMORY": 0, "PERSISTENCE_MEMORY": 1}
TREATED_STATE = {
    "REENTRY_MEMORY": "REENTERED",
    "PERSISTENCE_MEMORY": "PERSISTENT_OUTSIDE",
}
REFERENCE_STATE = {
    "REENTRY_MEMORY": "NEVER_OUTSIDE",
    "PERSISTENCE_MEMORY": "LATE_OR_RECROSS_OUTSIDE",
}

EPOCHS = ("2020", "2021", "2022", "2023", "2024")
FAMILIES = ("DAY", "WEEK", "MONTH")
FAMILY_DUMMIES = ("fam_week", "fam_month")
VOL_DUMMIES = ("vol_mid", "vol_high")
TIME_DUMMIES = ("tb1", "tb2", "tb3")

ARM_MIN_N = 100
RESOLVED_ARM_MIN_N = 100
OVERLAP_SHARE_MIN = 0.50
YEAR_MIN_N = 30
YEAR_ARM_MIN = 15
YEAR_SIGN_MIN = 4
FAMILY_MIN_N = 30
FAMILY_ARM_MIN = 15
SIDE_MIN_N = 30
SIDE_ARM_MIN = 15
LOYO_MIN_N = 30

BOOT_DRAWS = 2000
BOOT_SEED = 20261018
BOOT_MIN_VALID_FRAC = 0.9
CI_ALPHA = 0.05
FDR_Q = 0.10
PRACTICAL_SCALE = 0.03
SPECIFICITY_SCALE = 0.03
SIMILARITY_RATIO = 0.5
INFO_DEFF = 1.25
PLANNING_Z = 1.959963984540054 + 0.8416212335729143

if EVENT_START_MS != PARENT.EVENT_START_MS:
    raise RuntimeError("event start drifted from the parent February 2020 boundary")
if EVENT_END_MS != PARENT.SURFACE_END_MS:
    raise RuntimeError("event end drifted from the 2025-01-01 bound")
if REACTION_MS != REACTION_BARS * BAR_MS:
    raise RuntimeError("reaction window is not 15 minutes")
if LATE_STOP_OFFSET != 1 + HORIZON:
    raise RuntimeError("late window does not end on the parent 4h bar")
if EARLY_START_OFFSET != RX.EARLY_START_OFFSET or EARLY_STOP_OFFSET != RX.EARLY_STOP_OFFSET:
    raise RuntimeError("early window drifted from the #361 rule")
if LATE_START_OFFSET != RX.LATE_START_OFFSET or LATE_STOP_OFFSET != RX.LATE_STOP_OFFSET:
    raise RuntimeError("late window drifted from the #361 rule")
if HORIZON != PARENT.HOLD_BARS_PRIMARY:
    raise RuntimeError("horizon drifted from the parent 4h window")


def stream_seed(contrast_index: int, kind: int) -> int:
    return int(BOOT_SEED + int(contrast_index) * 100 + int(kind))


def exposure(n_estimated: int) -> dict:
    n = int(n_estimated)
    return {
        "states": len(STATES),
        "sequences_descriptive": len(SEQUENCES),
        "primary_contrasts_frozen": len(CONTRASTS),
        "primary_contrasts_estimated": n,
        "outcomes_primary": 1,
        "outcomes_secondary_descriptive": 1,
        "pseudo_contrasts": n,
        "specificity_contrasts": n,
        "stability_slices": n * (len(EPOCHS) + len(FAMILIES) + 2),
        "loyo_cells": n * len(EPOCHS),
        "lofo_cells": 0,
        "taxonomy_variants": 0,
        "horizon_extensions": 0,
    }
