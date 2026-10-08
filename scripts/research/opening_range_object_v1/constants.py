"""Frozen design constants for OPENING_RANGE_OBJECT_V1.

Chosen before any post-interaction resolution label. The support census may count
formations and first-interaction existence. It must not apply the extension
fraction or score a barrier.
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

# Primary anchor is the UTC day. The noon cell is a veto, not a second candidate.
ANCHORS = {
    "UTC_00": 0,
    "UTC_12": 144,
}
PRIMARY_CELL = "UTC_00"
VETO_CELL = "UTC_12"

# Later outcome, not applied by the census.
EXTENSION_FRACTION = 0.5
PRACTICAL_SCALE = 0.03
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


MIN_PAIRED = min_paired_for_benchmark()

assert MODE == "DISCOVERY"
assert FORMATION_BARS == 12
assert set(ANCHORS) == {"UTC_00", "UTC_12"}
assert ANCHORS["UTC_00"] == 0 and ANCHORS["UTC_12"] == 144
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
