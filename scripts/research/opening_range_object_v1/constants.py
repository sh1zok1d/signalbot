"""Frozen design constants for OPENING_RANGE_OBJECT_V1.

The original freeze is commit 3be350eb. Amendment A1 adds clock cells, the
touch-time rule, and the observable map. It does not retune the foundation
estimand and it does not authorize an outcome read.
"""

from __future__ import annotations

import math

UNIT = "OPENING_RANGE_OBJECT_V1"
FAMILY = "OPENING_RANGE_V1"
MODE = "DISCOVERY"
TRACKS = ("STRUCTURE", "PRODUCT_EVIDENCE")
CLAIM_CEILING = "L2"
SOURCE_MAIN_HEAD = "03ad8ef3a3434b4426154aab2af6b651c9807de8"

SURFACE_ID = "CORE_BTC_BINANCE_V0"
VENUE = "Binance USD-M BTCUSDT"
EVENT_START = "2020-01-01"
SURFACE_END = "2025-01-01"  # exclusive
ROW = "PRICE_STRUCTURE.levels"
COLUMN = "CANDLES"

# One clock hour on the 5m grid. Not a searched duration.
FORMATION_BARS = 12
BAR_MS = 300_000
DAY_MS = 86_400_000
BARS_PER_DAY = 288
ACTIVE_LIFE_BARS = BARS_PER_DAY - FORMATION_BARS  # 23h, dies when the next object of the same cell starts
HORIZON_BARS = 48  # 4h after the touch bar; availability only in the census

# Original design had UTC_00 and UTC_12 only. Amendment A1 adds the funding-cadence
# hours. Offsets are exact hour starts on the 5m grid. Not a 24-hour search.
ANCHORS = {
    "UTC_00": 0,
    "UTC_08": 96,
    "UTC_12": 144,
    "UTC_16": 192,
}
PRIMARY_CELL = "UTC_00"
VETO_CELL = "UTC_12"  # off the 00/08/16 funding cadence; not a second candidate
FUNDING_CYCLE_CELLS = ("UTC_00", "UTC_08", "UTC_16")
CLOCK_CELLS = ("UTC_00", "UTC_08", "UTC_12", "UTC_16")
ORIGINAL_DESIGN_COMMIT = "3be350eb0f71011928b1c99cc92f37059d631252"
ORIGINAL_DESIGN_SHA256 = "7e46d9f5081a4b1c6e3246ff7e2172e96a0c14eba900eefd84731147630250c8"
AMENDMENT = "A1"
# Working name. OPENING remains a hypothesis label, not a route and not a finding.
OBJECT_NAME = "FROZEN_HOUR_RANGE"

# Later outcome, not applied by the census.
EXTENSION_FRACTION = 0.5
PRACTICAL_SCALE = 0.03
SPECIFICITY_SCALE = 0.03  # |δ_00 − δ_hour|, same rate scale, not a searched bar
EXCURSION_SCALE = 0.25  # mean paired max outward excursion, in units of width W
# Amendment A2. Interpretation only. Scales are unchanged.
FAMILY_ALPHA = 0.05
FOUNDATION_CELL_FAMILY = "FOUNDATION_CELL_EFFECTS"
CLOCK_CONTRAST_FAMILY = "CLOCK_SPECIFICITY"
NONFOUNDATION_FAMILY = "NONFOUNDATION_MAP"
NONFOUNDATION_ORDER = (
    "DIRECTION_EXTENSION_FIRST",
    "OUTSIDE_OCCUPANCY",
    "OUTWARD_EXCURSION",
)
NONFOUNDATION_ROLE = {
    "DIRECTION_EXTENSION_FIRST": "BARRIER_FAMILY_DECOMPOSITION",
    "OUTSIDE_OCCUPANCY": "INDEPENDENT_OBSERVABLE",
    "OUTWARD_EXCURSION": "INDEPENDENT_OBSERVABLE",
}
NONFOUNDATION_SCALE = {
    "DIRECTION_EXTENSION_FIRST": PRACTICAL_SCALE,
    "OUTSIDE_OCCUPANCY": PRACTICAL_SCALE,
    "OUTWARD_EXCURSION": EXCURSION_SCALE,
}
# Touch-time audit. Cuts are the first hour and the 4h outcome horizon.
TIMING_NEARBY_MIN = 60
TIMING_FAR_MIN = 240
TIMING_FAR_SHARE = 0.25
TIMING_MEDIAN_ABS_MIN = 120
ELAPSED_BIN_EDGES_MIN = (60, 240, 720)
# One stream order for a later outcome run. Not used by the census.
BOOT_SEED_JOINT = 20261027
BOOT_SEED_DIRECTION = 20261028
BOOT_SEED_OUTSIDE = 20261029
BOOT_SEED_EXCURSION = 20261030
# Planning benchmark only: the level-foundation resolution gap was about 8pp.
# It is not an expected opening-range effect and not a target to hit.
FOUNDATION_BENCHMARK = 0.08
PLANNING_VARIANCE = 0.5  # conservative paired Bernoulli / discordant-pair bound
Z_95 = 1.959963984540054
Z_80 = 0.8416212335729143
MIN_ISO_WEEKS = 100

BOOT_DRAWS = 2000
BOOT_SEED = 20261027  # 20261007 and 20261009–20261026 already used
REL_COLLIDE = 1e-9

EXACT_CLAIM_PREVIOUSLY_READ = False
NEIGHBORING_PATH_PREVIOUSLY_READ = True
SURFACE_EVIDENCE_CLASS = "DISCOVERY_ON_EXPOSED_SURFACE"


def min_paired_for_benchmark() -> int:
    """Smallest N at which a paired difference of FOUNDATION_BENCHMARK has 80% power under PLANNING_VARIANCE."""
    se = FOUNDATION_BENCHMARK / (Z_95 + Z_80)
    return math.floor(PLANNING_VARIANCE / (se * se)) + 1


def planning_half_width(n_pairs: int) -> float:
    if n_pairs <= 0:
        return float("inf")
    return Z_95 * math.sqrt(PLANNING_VARIANCE / n_pairs)


def information_status(n_pairs: int, n_weeks: int) -> str:
    if n_pairs >= min_paired_for_benchmark() and n_weeks >= MIN_ISO_WEEKS:
        return "INFORMATION_ADEQUATE_FOR_LATER_OUTCOME"
    return "INFORMATION_LIMITED_STOP_BEFORE_OUTCOME"


def timing_imbalance_material(share_abs_ge_far: float, median_abs_min: float) -> bool:
    """Predeclared on the primary paired sample. Not a subgroup search."""
    return share_abs_ge_far >= TIMING_FAR_SHARE or median_abs_min >= TIMING_MEDIAN_ABS_MIN


def timing_handling(material: bool, nearby_pairs: int, nearby_weeks: int) -> str:
    """One handling, chosen by the audit rule. No rematch on touch time."""
    if not material:
        return "PUBLISH_AUDIT_NO_CORRECTION"
    if nearby_pairs >= MIN_PAIRED and nearby_weeks >= MIN_ISO_WEEKS:
        return "PUBLISH_AUDIT_PLUS_NEARBY_SENSITIVITY"
    return "PUBLISH_AUDIT_NEARBY_SENSITIVITY_INFORMATION_LIMITED"


MIN_PAIRED = min_paired_for_benchmark()

assert MODE == "DISCOVERY"
assert FORMATION_BARS == 12
assert set(ANCHORS) == {"UTC_00", "UTC_08", "UTC_12", "UTC_16"}
assert ANCHORS["UTC_00"] == 0 and ANCHORS["UTC_08"] == 96
assert ANCHORS["UTC_12"] == 144 and ANCHORS["UTC_16"] == 192
assert SPECIFICITY_SCALE == 0.03 and EXCURSION_SCALE == 0.25
assert FAMILY_ALPHA == 0.05
assert NONFOUNDATION_ORDER == (
    "DIRECTION_EXTENSION_FIRST",
    "OUTSIDE_OCCUPANCY",
    "OUTWARD_EXCURSION",
)
assert NONFOUNDATION_ROLE["DIRECTION_EXTENSION_FIRST"] == "BARRIER_FAMILY_DECOMPOSITION"
assert NONFOUNDATION_SCALE["OUTWARD_EXCURSION"] == 0.25
assert TIMING_FAR_MIN == 240 and TIMING_FAR_SHARE == 0.25 and TIMING_MEDIAN_ABS_MIN == 120
assert TIMING_NEARBY_MIN == 60
assert OBJECT_NAME == "FROZEN_HOUR_RANGE"
assert AMENDMENT == "A1"
assert ACTIVE_LIFE_BARS == 276
assert HORIZON_BARS == 48
assert EXTENSION_FRACTION == 0.5
assert PRACTICAL_SCALE == 0.03
assert FOUNDATION_BENCHMARK == 0.08
assert PLANNING_VARIANCE == 0.5
assert MIN_ISO_WEEKS == 100
assert BOOT_SEED == 20261027
assert MIN_PAIRED == 614
assert EXACT_CLAIM_PREVIOUSLY_READ is False
assert NEIGHBORING_PATH_PREVIOUSLY_READ is True
assert CLAIM_CEILING == "L2"
