"""Frozen design constants for LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1.

Chosen before any cross-venue feature was joined to a late BREAK label.
Do not change venues, alignment, features, nuisance, FDR, or the stability
rule after an outcome is read.
"""

from __future__ import annotations

from scripts.research.level_post_touch_reaction_discovery_v1 import constants as RX
from scripts.research.level_touch_degradation_v1 import constants as PARENT

UNIT = "LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1"
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
DEPENDENCY_PATH_SHA = "b005eaac895d3a4c644d16101d2e5eb7d2ff8d5f"

CORE_DATASET_ID = "CORE_BTC_BINANCE_V0"
CORE_ZIP_LIST_SHA256 = "936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b"
DATASET_ID = "LEVEL_CROSS_VENUE_PERP_5M_V0"
PARENT_SIGMA_LO = 0.0012364306616934476
PARENT_SIGMA_HI = 0.001790567553180052

# Common same-class overlap. Bybit public 5m klines begin 2020-04-01.
# The first legal touch is one bar later, so the pre-touch close exists.
EVENT_START = "2020-04-01T00:05:00+00:00"
EVENT_END = "2025-01-01T00:00:00+00:00"
EVENT_START_MS = 1585699200000 + 300_000
EVENT_END_MS = PARENT.SURFACE_END_MS
SURFACE_END_MS = PARENT.SURFACE_END_MS

MINUTE_MS = 60_000
BAR_MS = 300_000
HOUR_MS = 3_600_000
# Bybit's public MT4 file labels a fixed UTC+3 clock. Canonical opens are UTC.
# Frozen from the trade-tape identity on 2020-04-01 and 2020-07-15, before outcomes.
BYBIT_LABEL_OFFSET_HOURS = -3
BYBIT_LABEL_OFFSET_MS = BYBIT_LABEL_OFFSET_HOURS * HOUR_MS
PRE_BARS = 12
REACTION_BARS = 3
REACTION_MS = 15 * MINUTE_MS
HORIZON = 48
EARLY_START_OFFSET = 1
EARLY_STOP_OFFSET = 3
LATE_START_OFFSET = 3
LATE_STOP_OFFSET = 49

TIER = "TIER_A"
VENUE_TIER = "THREE_VENUE"
REFERENCE_VENUE = "BINANCE_USD_M_BTCUSDT_PERP"
OTHER_VENUES = ("BYBIT_LINEAR_BTCUSDT_PERP", "OKX_BTC_USDT_SWAP_PERP")
# Exact open-time match. No nearest bar, no forward fill.
ALIGNMENT_TOLERANCE_MS = 0

FEATURES = (
    "OTHER_VENUE_MEDIAN_MOVE",
    "CROSS_VENUE_CONFIRMATION_GAP",
    "CROSS_VENUE_DISPERSION",
    "DIRECTION_AGREEMENT",
)
# Later features are the ones dropped when |rho| >= 0.90.
REDUNDANCY_ORDER = FEATURES
REDUNDANCY_ABS_RHO = 0.90

EPOCHS = ("2020", "2021", "2022", "2023", "2024")
FAMILIES = ("DAY", "WEEK", "MONTH")
FAMILY_DUMMIES = ("fam_week", "fam_month")
VOL_DUMMIES = ("vol_mid", "vol_high")
TIME_DUMMIES = ("tb1", "tb2", "tb3")

YEAR_MIN_N = 30
YEAR_SIGN_MIN_OF_FIVE = 4
FAMILY_MIN_N = 30
SIDE_MIN_N = 30
LOYO_MIN_N = 30
PRE_OUTCOME_MIN_UNRESOLVED = 400
INFORMATION_MIN_RESOLVED = 200
INFORMATION_CI_WIDTH = 0.20
MATERIAL_OPPOSITE = 0.03

BOOT_DRAWS = 2000
BOOT_SEED = 20261019
BOOT_MIN_VALID_FRAC = 0.9
CI_ALPHA = 0.05
FDR_Q = 0.10
PRACTICAL_SCALE = 0.03
SPECIFICITY_SCALE = 0.03
SPECIFICITY_MIN_N = 100
PLANNING_RESOLVE_FRACTION = 0.50
INFO_DEFF = 1.25
PLANNING_Z = 1.959963984540054 + 0.8416212335729143

ROUTES = (
    "LEVEL_CROSS_VENUE_STRUCTURE_PRESENT",
    "GENERIC_CROSS_VENUE_REACTION_ONLY",
    "NO_INCREMENTAL_CROSS_VENUE_REACTION_STRUCTURE",
    "STRUCTURE_PRESENT_BUT_UNSTABLE",
    "INFORMATION_LIMITED",
    "CROSS_VENUE_HISTORY_INSUFFICIENT",
    "BLOCKED_REOPENING_CROSS_VENUE_CELL",
)

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
if ALIGNMENT_TOLERANCE_MS != 0:
    raise RuntimeError("alignment tolerance is no longer exact")
if TIER != "TIER_A" or len(OTHER_VENUES) != 2:
    raise RuntimeError("tier drifted from the frozen three-venue design")


def stream_seed(feature_index: int, kind: int) -> int:
    return int(BOOT_SEED + int(feature_index) * 100 + int(kind))
