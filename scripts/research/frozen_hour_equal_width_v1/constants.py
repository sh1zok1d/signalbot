"""Frozen FROZEN_HOUR_EQUAL_WIDTH_V1 constants.

Taken from docs/research/FROZEN_HOUR_EQUAL_WIDTH_V1_DESIGN.md at the design
commit. The census does not retune them and does not apply the barrier fraction.
"""

from __future__ import annotations

import datetime as dt

from scripts.research.opening_range_object_v1 import constants as PARENT

UNIT = "FROZEN_HOUR_EQUAL_WIDTH_V1"
FAMILY = "OPENING_RANGE_V1"
MODE = "CONFIRMATION"
TRACKS = ("STRUCTURE",)
CLAIM_CEILING = "L2"
DESIGN_COMMIT = "5c3f6e6bdc4df8ef3ce7266b318253c42dada4a3"
DESIGN_PATH_REL = "docs/research/FROZEN_HOUR_EQUAL_WIDTH_V1_DESIGN.md"

SURFACE_ID = "DH1_BINANCE_SPOT_BTCUSDT_5M_V0"
VENUE = "Binance spot BTCUSDT"
INTERVAL = "5m"
EVENT_START = "2017-09-01"
SURFACE_END = "2020-01-01"  # exclusive
FIRST_MONTH = "2017-09"
LAST_MONTH = "2019-12"
ROW = "PRICE_STRUCTURE.levels"
COLUMN = "CANDLES"
SURFACE_EVIDENCE_CLASS = "TIME_DISJOINT_OUTCOME_UNREAD"

FORMATION_BARS = PARENT.FORMATION_BARS
BAR_MS = PARENT.BAR_MS
DAY_MS = PARENT.DAY_MS
BARS_PER_DAY = PARENT.BARS_PER_DAY
ACTIVE_LIFE_BARS = PARENT.ACTIVE_LIFE_BARS
HORIZON_BARS = PARENT.HORIZON_BARS
REL_COLLIDE = PARENT.REL_COLLIDE

# Primary and the one diagnostic. Not four candidates.
ANCHORS = {
    "UTC_00": PARENT.ANCHORS["UTC_00"],
    "UTC_12": PARENT.ANCHORS["UTC_12"],
}
PRIMARY_CELL = "UTC_00"
DIAGNOSTIC_CELL = "UTC_12"
CELLS = ("UTC_00", "UTC_12")

EXTENSION_FRACTION = PARENT.EXTENSION_FRACTION  # frozen; the census does not apply it
PRACTICAL_SCALE = PARENT.PRACTICAL_SCALE
MIN_PAIRED = 614
MIN_ISO_WEEKS = 100
WIDTH_REL_TOL = 1e-9
MAX_DOUBLES = 60
BISECTIONS = 80
BOOT_DRAWS = PARENT.BOOT_DRAWS
BOOT_SEED_UTC_00 = 20261031
BOOT_SEED_UTC_12 = 20261102

ADEQUATE = "INFORMATION_ADEQUATE_FOR_LATER_OUTCOME"
LIMITED = "INFORMATION_LIMITED_STOP_BEFORE_OUTCOME"
REFUSAL_OUTCOME = "REFUSING_OUTCOME_BEFORE_OWNER_GO"
REFUSAL_RERUN = "REFUSING_RERUN"

UTC = dt.timezone.utc


def _ms(iso_date: str) -> int:
    return int(dt.datetime.fromisoformat(iso_date + "T00:00:00+00:00").timestamp() * 1000)


EVENT_START_MS = _ms(EVENT_START)
SURFACE_END_MS = _ms(SURFACE_END)
CALENDAR_DAYS = (SURFACE_END_MS - EVENT_START_MS) // DAY_MS


def information_status(n_pairs: int, n_weeks: int) -> str:
    if n_pairs >= MIN_PAIRED and n_weeks >= MIN_ISO_WEEKS:
        return ADEQUATE
    return LIMITED


def joint_information(primary: str, diagnostic: str) -> str:
    """Either cell below the floor stops both. Passing the floor does not authorize Y."""
    if primary == ADEQUATE and diagnostic == ADEQUATE:
        return ADEQUATE
    return LIMITED


assert FORMATION_BARS == 12
assert BARS_PER_DAY == 288
assert ACTIVE_LIFE_BARS == 276
assert HORIZON_BARS == 48
assert ANCHORS == {"UTC_00": 0, "UTC_12": 144}
assert EXTENSION_FRACTION == 0.5
assert PRACTICAL_SCALE == 0.03
assert MIN_PAIRED == 614
assert MIN_ISO_WEEKS == 100
assert PARENT.MIN_PAIRED == 614
assert REL_COLLIDE == 1e-9
assert WIDTH_REL_TOL == 1e-9
assert MAX_DOUBLES == 60
assert BISECTIONS == 80
assert BOOT_DRAWS == 2000
assert BOOT_SEED_UTC_00 == 20261031
assert BOOT_SEED_UTC_12 == 20261102
assert CALENDAR_DAYS == 852
assert EVENT_START_MS == 1504224000000
assert SURFACE_END_MS == 1577836800000
assert MODE == "CONFIRMATION"
assert CLAIM_CEILING == "L2"
