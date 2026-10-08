"""Frozen confirmation constants. Chosen before any BitMEX break/reject rate is read.

Parent level geometry, touch numbering and the 4h barrier are imported from
LEVEL_TOUCH_DEGRADATION_V1. This module does not retune them.
"""

from __future__ import annotations

import datetime as dt

from scripts.research.level_touch_degradation_v1 import constants as PARENT

UNIT = "LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1"
FAMILY = "LEVEL_BEHAVIOR_V1"
MODE = "CONFIRMATION"
TRACKS = ("STRUCTURE", "PRODUCT_EVIDENCE")
CLAIM_CEILING = "L2"

SOURCE_MAIN_HEAD = "1a2e425303fb29e1044ca57452b8ad9b6f0a831b"
DEP_TOUCH = "dfc9e0f04358de15606382472badeb5aee787039"
DEP_REJECTION = "c3d39bffda861b535605a98205d7578c0c84c782"
DEP_METHOD = "8effe9acc3b88b925a79b33f04ac0ee9e6f93e26"
DEP_APPROACH = "aa85e5b43c405ee225336ff385e3a3383fa59d09"
DEP_STRUCTURE = "f8623d3281424c165ebd7ee7fbcb0af994cc1e8d"

SURFACE_ID = "DH1_BITMEX_XBTUSD_TRADES_5M_V0"
EXPOSURE_STATUS = "TIME_DISJOINT / OUTCOME_UNREAD_FOR_THIS_CLAIM / FEASIBILITY_EXPOSED"
VENUE = "BitMEX XBTUSD inverse perpetual"

# Warm-up includes August so September can have a previous month. Events start in September.
DATA_START = "2017-08-01"
EVENT_START = "2017-09-01"
EVENT_END = "2020-01-01"  # exclusive
PROTECTED_FROM = "2025-01-01"
E1_HOLDOUT_START = "2026-08-16T00:00:00+00:00"
E1_HOLDOUT_END = "2026-08-25T17:20:00+00:00"

EPOCHS = ("2017H2", "2018", "2019")
FAMILIES = ("DAY", "WEEK", "MONTH")
# Approach side on the touch: +1 resistance (from below), -1 support (from above).
SIDE_NAME = {1: "resistance", -1: "support"}

# Reused, not copied as a new choice.
ZONE_HALF = PARENT.ZONE_HALF_PRIMARY
LEVEL_KINDS = PARENT.LEVEL_KINDS
HOLD_BARS = PARENT.HOLD_BARS_PRIMARY
BARRIER_FRACTION = PARENT.BARRIER_FRACTION_PRIMARY
PRACTICAL_SCALE = PARENT.PRACTICAL_SCALE  # 3 pp. Reading scale, not a required copy of the discovery gap.

BOOT_DRAWS = 2000
BOOT_SEED = 20261012
BOOT_MIN_VALID_FRAC = 0.9
MIN_PAIRS_CLAIM = 30
MIN_EPOCH_PAIRS = 30
MIN_DUMMY_SHARE = 0.02
MAX_DUMMY_SHARE = 0.98
# Availability-matched pairs below this are not a meaningful confirmation reading.
RUN_FLOOR = 30

# One primary contrast. The other cells are decomposition, one adjusted sensitivity, and diagnostics.
N_PRIMARY = 1
N_DECOMPOSITION = 3
N_ADJUSTED = 1
N_EPOCH = 3
N_FAMILY = 3
N_SIDE = 2
N_LOEO = 3
N_CELLS = N_PRIMARY + N_DECOMPOSITION + N_ADJUSTED + N_EPOCH + N_FAMILY + N_SIDE + N_LOEO

ADJUSTED_COLUMN_ORDER = (
    "family_week",
    "family_month",
    "support",
    "vol_mid",
    "vol_high",
    "epoch_2018",
    "epoch_2019",
)

LABEL_REPLICATED = "REPLICATED_POSITIVE_RESOLUTION_DIFFERENCE"
LABEL_NO_MATERIAL = "NO_MATERIAL_POSITIVE_RESOLUTION_DIFFERENCE"
LABEL_UNSTABLE = "POSITIVE_RESOLUTION_DIFFERENCE_UNSTABLE"
LABEL_LIMITED = "INFORMATION_LIMITED"
EVIDENCE_LABELS = (LABEL_REPLICATED, LABEL_NO_MATERIAL, LABEL_UNSTABLE, LABEL_LIMITED)


def _ms_date(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso + "T00:00:00+00:00").timestamp() * 1000)


def _ms_stamp(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso).timestamp() * 1000)


DATA_START_MS = _ms_date(DATA_START)
EVENT_START_MS = _ms_date(EVENT_START)
EVENT_END_MS = _ms_date(EVENT_END)
PROTECTED_FROM_MS = _ms_date(PROTECTED_FROM)
E1_START_MS = _ms_stamp(E1_HOLDOUT_START)
E1_END_MS = _ms_stamp(E1_HOLDOUT_END)


def epoch_of_ms(open_ms: int) -> str:
    """Epoch of a touch open. 2017 inside the event window is the partial second half."""
    year = int(dt.datetime.fromtimestamp(open_ms / 1000.0, dt.timezone.utc).year)
    if year == 2017:
        return "2017H2"
    if year == 2018:
        return "2018"
    if year == 2019:
        return "2019"
    return "OUT"
