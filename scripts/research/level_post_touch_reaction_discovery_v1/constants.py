"""Frozen design constants for LEVEL_POST_TOUCH_REACTION_DISCOVERY_V1.

Chosen before any post-touch feature was joined to a late resolution label.
Do not change these after an outcome is read. Parent level geometry is imported.
"""

from __future__ import annotations

import datetime as dt

from scripts.research.level_positioning_flow_discovery_v1 import constants as PF

UNIT = "LEVEL_POST_TOUCH_REACTION_DISCOVERY_V1"
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

OI_DATASET_ID = PF.OI_DATASET_ID
OI_SNAPSHOT_ID = PF.OI_SNAPSHOT_ID
OI_JSONL_SHA256 = PF.OI_JSONL_SHA256
OI_JSONL_ROWS = PF.OI_JSONL_ROWS
OI_FIRST_AVAILABLE_MS = PF.OI_FIRST_AVAILABLE_MS
OI_PERIOD_MS = PF.OI_PERIOD_MS

CORE_DATASET_ID = PF.CORE_DATASET_ID
CORE_ZIP_LIST_SHA256 = PF.CORE_ZIP_LIST_SHA256
PARENT_SIGMA_LO = PF.PARENT_SIGMA_LO
PARENT_SIGMA_HI = PF.PARENT_SIGMA_HI

SURFACE_END = "2025-01-01T00:00:00+00:00"
# First touch whose OI print is legally available. No 60m OI path is required.
# Price lookback of 24h is inside the CORE panel, which starts 2020-01-01.
EVENT_START = "2020-09-01T00:05:00+00:00"
EVENT_END = SURFACE_END

MINUTE_MS = 60_000
BAR_MS = 300_000
HOUR_MS = 3_600_000
REACTION_BARS = 3           # j, j+1, j+2 = [T, T+15m)
REACTION_MS = 15 * MINUTE_MS
PRE_BARS = 12               # [T-60m, T)
PRE_MS = 60 * MINUTE_MS
REL_VOL_BARS = 288
HORIZON = 48                # parent window j+1 .. j+48; late window is the tail
EARLY_START_OFFSET = 1      # first bar after the touch bar
EARLY_STOP_OFFSET = 3       # exclusive: bars j+1, j+2
LATE_START_OFFSET = 3       # bar j+3 opens at D
LATE_STOP_OFFSET = 49       # exclusive: through j+48, the parent end
# One native OI period. A missing print may use the previous one. A longer gap is missing.
MAX_OI_STALENESS_MS = OI_PERIOD_MS

RAW_FEATURES = (
    "END_POSITION_X",
    "RELATIVE_ACTIVITY_15M",
    "ORIENTED_TAKER_REACTION_15M",
    "TAKER_CHANGE_VS_PRE",
    "OI_REACTION_15M",
)
PRICE_FEATURE = "END_POSITION_X"
REDUNDANCY_RHO = 0.90

OUTCOMES = ("LATE_RESOLVE_BY_4H", "LATE_BREAK_GIVEN_RESOLVED")
EPOCHS = ("2020Q4", "2021", "2022", "2023", "2024")
FAMILIES = ("DAY", "WEEK", "MONTH")
EARLY_STATUSES = (
    "EARLY_BREAK",
    "EARLY_REJECT",
    "EARLY_AMBIGUOUS",
    "UNRESOLVED",
    "UNAVAILABLE",
)

BOOT_DRAWS = 2000
BOOT_SEED = 20261017
BOOT_MIN_VALID_FRAC = 0.9
CI_ALPHA = 0.05
FDR_Q = 0.10
PRACTICAL_SCALE = 0.03
SPECIFICITY_SCALE = 0.03
SIMILARITY_RATIO = 0.5
YEAR_MIN_N = 30
YEAR_SIGN_MIN = 4
FAMILY_COMPLEMENT_MIN_N = 30
SIDE_MIN_N = 30
MIN_CELL_N = 100
INFO_MIN_N = 100
INFO_MIN_CLUSTERS = 20
INFO_DEFF = 1.25
MIN_RETAINED = 3

FAMILY_DUMMIES = ("fam_week", "fam_month")
VOL_DUMMIES = ("vol_mid", "vol_high")
TIME_DUMMIES = ("tb1", "tb2", "tb3")


def _ms(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso).timestamp() * 1000)


EVENT_START_MS = _ms(EVENT_START)
EVENT_END_MS = _ms(EVENT_END)
SURFACE_END_MS = _ms(SURFACE_END)

if EVENT_START_MS != OI_FIRST_AVAILABLE_MS:
    raise RuntimeError("event start is not the first legally available OI print")
if EVENT_END_MS != SURFACE_END_MS:
    raise RuntimeError("event end drifted from the 2025-01-01 bound")
if REACTION_MS != REACTION_BARS * BAR_MS:
    raise RuntimeError("reaction window is not 15 minutes")
if LATE_STOP_OFFSET != 1 + HORIZON:
    raise RuntimeError("late window does not end on the parent 4h bar")
if MAX_OI_STALENESS_MS != OI_PERIOD_MS:
    raise RuntimeError("OI staleness is not one native period")


def stream_seed(feature_index: int, outcome_index: int, kind: int) -> int:
    return int(BOOT_SEED + feature_index * 1000 + outcome_index * 100 + kind)


def exposure(n_retained: int) -> dict:
    primary = int(n_retained) * len(OUTCOMES)
    return {
        "raw_features": len(RAW_FEATURES),
        "retained_features": int(n_retained),
        "reaction_bars": REACTION_BARS,
        "outcomes": len(OUTCOMES),
        "primary_cells": primary,
        "shape_cells": primary,
        "pseudo_cells": primary,
        "specificity_cells": primary,
        "stability_cells": primary * (len(EPOCHS) + len(FAMILIES) + 2),
        "loyo_cells": primary * len(EPOCHS),
        "lofo_cells": primary * len(FAMILIES),
        "interactions": 0,
        "acceptance_flags": 0,
        "horizon_extensions": 0,
        "extra_window_sensitivities": 0,
    }
