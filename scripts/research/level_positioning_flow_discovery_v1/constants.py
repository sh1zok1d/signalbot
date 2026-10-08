"""Frozen design constants for LEVEL_POSITIONING_FLOW_DISCOVERY_V1.

Chosen before any positioning or flow feature was joined to a resolution label.
Do not change these after an outcome is read. Parent level geometry is imported,
not copied into a second definition.
"""

from __future__ import annotations

import datetime as dt

UNIT = "LEVEL_POSITIONING_FLOW_DISCOVERY_V1"
FAMILY = "LEVEL_BEHAVIOR_V1"
MODE = "DISCOVERY"
TRACKS = ("STRUCTURE", "PRODUCT_EVIDENCE")
CLAIM_CEILING = "L2"
PRODUCT_INTEGRATION_CANDIDATE = False
SOURCE_MAIN_HEAD = "1a2e425303fb29e1044ca57452b8ad9b6f0a831b"

DEPENDENCY_TOUCH_SHA = "dfc9e0f04358de15606382472badeb5aee787039"
DEPENDENCY_MEMORY_SHA = "c3d39bffda861b535605a98205d7578c0c84c782"
DEPENDENCY_METHOD_SHA = "8effe9acc3b88b925a79b33f04ac0ee9e6f93e26"
DEPENDENCY_APPROACH_SHA = "aa85e5b43c405ee225336ff385e3a3383fa59d09"
DEPENDENCY_STRUCTURE_SHA = "f8623d3281424c165ebd7ee7fbcb0af994cc1e8d"
DEPENDENCY_CONFIRM_SHA = "c1cd4e0102e700f7860d21a9af0d243c3bc367be"

# Git-tracked B2-06 OI object. The unit binds to these bytes, not to a new wrapper id.
OI_DATASET_ID = "B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0"
OI_SNAPSHOT_ID = "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33"
OI_MATERIALIZER_COMMIT = "78d5bdf9d5686b740ebc48e46227bbf0f990cbbe"
OI_MATERIALIZER_TREE = "2b3e48ba36dd19f40a00fabe5c1a548b0b94d72f"
OI_JSONL_SHA256 = "c4744a9369844f453476589111c2436372e729e7afdbe5fb34b6e9938a905b94"
OI_JSONL_ROWS = 455273
OI_JSONL_BYTES = 254313318
OI_FIRST_PERIOD_START_MS = 1_598_918_400_000  # 2020-09-01 00:00:00Z
OI_FIRST_AVAILABLE_MS = 1_598_918_700_000    # create_time + 5m
OI_PERIOD_MS = 300_000

CORE_DATASET_ID = "CORE_BTC_BINANCE_V0"
CORE_ZIP_LIST_SHA256 = "936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b"

# Parent #352 volatility terciles. Not refit on this cohort.
PARENT_SIGMA_LO = 0.0012364306616934476
PARENT_SIGMA_HI = 0.001790567553180052

SURFACE_END = "2025-01-01T00:00:00+00:00"
# First decision time that can see a full 60m of legal OI prints.
# First available_at is 2020-09-01 00:05Z, so T - 60m lands on that print at 01:05Z.
EVENT_START = "2020-09-01T01:05:00+00:00"
EVENT_END = SURFACE_END

MINUTE_MS = 60_000
BAR_MS = 300_000
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
PRIMARY_MS = 60 * MINUTE_MS
RECENT_MS = 15 * MINUTE_MS
PRIOR_MS = 45 * MINUTE_MS
OI_PRINTS = 13          # available_at = T-60m, T-55m, ..., T
TAKER_BARS = 12         # opens [T-60m, T)
RECENT_BARS = 3         # opens [T-15m, T)
PRIOR_BARS = 9          # opens [T-60m, T-15m)
REL_VOL_BARS = 288      # prior 24h of 5m bars, end-exclusive at T
REL_VOL_MIN_PRESENT = 0.9
HORIZON = 48

# Keep the simpler feature when |rho| >= 0.90. Order is the simplicity order.
RAW_FEATURES = (
    "OI_CHANGE_60M",
    "OI_RECENT_ACCELERATION",
    "ORIENTED_TAKER_IMBALANCE_60M",
    "TAKER_RECENT_SHIFT",
)
REDUNDANCY_RHO = 0.90

OUTCOMES = ("RESOLVE_4H", "BREAK_GIVEN_RESOLVED")
EPOCHS = ("2020Q4", "2021", "2022", "2023", "2024")
FAMILIES = ("DAY", "WEEK", "MONTH")

BOOT_DRAWS = 2000
BOOT_SEED = 20261013
BOOT_MIN_VALID_FRAC = 0.9
CI_ALPHA = 0.05
FDR_Q = 0.10
# Product level-reaction floor (beta/levels.py MATERIAL_DIFF). Same reading scale as
# #352/#355/#356/#357. Not the DH1 3pp-plus-Brier bar, which applies to a directional
# probability claim this unit does not make.
PRACTICAL_SCALE = 0.03
SPECIFICITY_SCALE = 0.03
# A pseudo slope at least half the real primary slope, and the same sign, is "similar".
# Half-magnitude is the #352 control rule. It is not refit after outcomes.
SIMILARITY_RATIO = 0.5
YEAR_MIN_N = 30
YEAR_SIGN_MIN = 4
TINY_FAMILY_SHARE = 0.15
MIN_CELL_N = 100
INFO_MIN_N = 100
INFO_MIN_CLUSTERS = 20

# Full-sample nuisance. Reference levels: DAY, resistance (side +1), 2020, low vol, 00-06 UTC.
YEAR_DUMMIES = ("y2021", "y2022", "y2023", "y2024")
FAMILY_DUMMIES = ("fam_week", "fam_month")
VOL_DUMMIES = ("vol_mid", "vol_high")
TIME_DUMMIES = ("tb1", "tb2", "tb3")


def _ms(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso).timestamp() * 1000)


EVENT_START_MS = _ms(EVENT_START)
EVENT_END_MS = _ms(EVENT_END)
SURFACE_END_MS = _ms(SURFACE_END)

if EVENT_START_MS != OI_FIRST_AVAILABLE_MS + PRIMARY_MS:
    raise RuntimeError("event start is not the first T with a 60m OI lookback")
if EVENT_END_MS != SURFACE_END_MS:
    raise RuntimeError("event end drifted from the 2025-01-01 bound")


def stream_seed(feature_index: int, outcome_index: int, kind: int) -> int:
    """Disjoint bootstrap streams. kind is a small integer fixed in inference.py."""
    return int(BOOT_SEED + feature_index * 1000 + outcome_index * 100 + kind)


def exposure(n_retained: int) -> dict:
    """Predeclared cell counts. LOYO and LOFO are computed for every primary cell
    so the conjunction does not choose the slice after a look at Y. They are not
    a second FDR family.
    """
    primary = int(n_retained) * len(OUTCOMES)
    return {
        "raw_features": len(RAW_FEATURES),
        "retained_features": int(n_retained),
        "windows": 2,
        "outcomes": len(OUTCOMES),
        "primary_cells": primary,
        "shape_cells": primary,
        "pseudo_cells": primary,
        "specificity_cells": primary,
        "stability_cells": primary * (len(EPOCHS) + len(FAMILIES) + 2),
        "loyo_cells": primary * len(EPOCHS),
        "lofo_cells": primary * len(FAMILIES),
        "interactions": 0,
        "extra_window_sensitivities": 0,
    }
