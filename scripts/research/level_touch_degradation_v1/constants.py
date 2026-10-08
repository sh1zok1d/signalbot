"""Frozen design constants for LEVEL_TOUCH_DEGRADATION_V1.

Chosen before any break/reject rate was read. `outcomes.py` and `evaluate.py` must not
change these to improve a result. A post-hoc variant is a new unit.
"""

from __future__ import annotations

import datetime as dt

UNIT = "LEVEL_TOUCH_DEGRADATION_V1"
FAMILY = "LEVEL_BEHAVIOR_V1"
TRACKS = ("STRUCTURE", "PRODUCT_EVIDENCE")
CLAIM_CEILING = "L2"
SOURCE_MAIN_HEAD = "1a2e425303fb29e1044ca57452b8ad9b6f0a831b"

SURFACE_ID = "CORE_BTC_BINANCE_V0"
VENUE = "Binance USD-M BTCUSDT"
# Price only. The 5m grid is the DH1 aggregation of the pinned 1m klines (complete bins only).
DATA_START = "2020-01-01"     # warm-up: January builds the first month level and the 24h scale
EVENT_START = "2020-02-01"    # first touch timestamp that may enter the estimand
SURFACE_END = "2025-01-01"    # exclusive. Nothing at or after this instant is read.
PROTECTED_FROM = "2025-01-01"
# E1-RUN-001 final holdout. Outside this surface; the loader still refuses it.
E1_HOLDOUT_START = "2026-08-16T00:00:00+00:00"
E1_HOLDOUT_END = "2026-08-25T17:20:00+00:00"

MINUTE_MS = 60_000
BAR_MS = 300_000
DAY_MS = 86_400_000

# ---- level set --------------------------------------------------------------------------------
# The product's structural previous-period extremes (beta/levels.py PUSH_LEVELS). Round numbers,
# POC, session extremes, opens and liquidation levels are out of this unit.
LEVEL_KINDS = ("PMH", "PML", "PWH", "PWL", "PDH", "PDL")
PRIORITY = {k: i for i, k in enumerate(LEVEL_KINDS)}  # lower = more important; product LEVEL_ORDER
FAMILY_OF = {"PMH": "MONTH", "PML": "MONTH", "PWH": "WEEK", "PWL": "WEEK", "PDH": "DAY", "PDL": "DAY"}
STRUCT_SIDE = {"PMH": 1, "PWH": 1, "PDH": 1, "PML": -1, "PWL": -1, "PDL": -1}

# ---- zone --------------------------------------------------------------------------------------
# Primary half-width is the product's frozen confluence tolerance (ZONE_TOL_PCT = 0.15).
# The single sensitivity width is the product's "at the level" band (AT_LEVEL_PCT = 0.03).
ZONE_HALF_PRIMARY = 0.0015
ZONE_HALF_SENSITIVITY = 0.0003
# Two prices belong to one birth cluster when (higher - lower) / lower <= this.
MERGE_TOL = ZONE_HALF_PRIMARY

# ---- touch / refractory / outcome --------------------------------------------------------------
SCALE_BARS = 288                 # 24h of 5m log returns, ending at the bar BEFORE the touch
MIN_PRESENT = 0.9
CORRIDOR_Z = 1.2816              # product 80% corridor half-width, in sigma units (DH1)
HOLD_BARS_PRIMARY = 48           # 4h
HOLD_BARS_SENSITIVITY = 12       # 1h
BARRIER_FRACTION_PRIMARY = 0.5   # X = half of the 4h corridor half-width (DH1)
BARRIER_FRACTION_SENSITIVITY = 1.0
REFRACTORY_MULT = 1.0            # clearance distance = this × primary X; not sensitized
X_MIN = 1e-8
X_MAX = 0.5                      # a larger X makes the lower barrier non-positive or useless

TOUCH_BUCKETS = ("1", "2", "3+")

# ---- inference ---------------------------------------------------------------------------------
# Direct standardization strata: family × approach side × vol tercile. Year is a stability cut,
# not a standardization axis (90 cells would be mostly empty).
MIN_ARM = 15
BOOT_DRAWS = 2000
BOOT_SEED = 20261007
BOOT_MIN_VALID_FRAC = 0.9
CI_ALPHA = 0.05
# Practical scale for the predeclared reading rule, not a verdict function.
# Product level-reaction materiality floor (beta/levels.py MATERIAL_DIFF; PRODUCT_DECISION_V2 §3).
PRACTICAL_SCALE = 0.03
PLANNING_Z = 1.959963984540054 + 0.8416212335729143  # 95% two-sided, 80% power
PLANNING_DEFF_DH1 = 1.25
YEAR_MIN_ARM = 30
YEAR_SIGN_MIN = 4                 # of 5 years, for the integration reading
MAX_YEAR_SHARE = 0.40
MAX_FAMILY_SHARE_TOUCH3 = 0.70
MIN_WEEKS_READING = 100
CONTROL_HALF = 0.5                # control |Δ| below half the real |Δ| counts as "not the same pattern"

# Search exposure: every contrast the evaluator computes. See the design note §12.
N_PRIMARY_CONTRASTS = 2
N_CONTRASTS_TOTAL = 42

YEARS = (2020, 2021, 2022, 2023, 2024)
FAMILIES = ("DAY", "WEEK", "MONTH")
SIDES = (1, -1)  # +1 resistance (approach from below, break upward); -1 support


def _ms_date(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso + "T00:00:00+00:00").timestamp() * 1000)


def _ms_stamp(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso).timestamp() * 1000)


DATA_START_MS = _ms_date(DATA_START)
EVENT_START_MS = _ms_date(EVENT_START)
SURFACE_END_MS = _ms_date(SURFACE_END)
E1_START_MS = _ms_stamp(E1_HOLDOUT_START)
E1_END_MS = _ms_stamp(E1_HOLDOUT_END)


def x_from_sigma(sigma: float, *, barrier_fraction: float = BARRIER_FRACTION_PRIMARY,
                 horizon: int = HOLD_BARS_PRIMARY) -> float:
    """Volatility-scaled barrier distance. sigma is the 5m log-return std known before the touch."""
    return float(barrier_fraction) * CORRIDOR_Z * float(sigma) * (float(horizon) ** 0.5)


def bucket_of(touch_number: int) -> str:
    if touch_number <= 1:
        return "1"
    if touch_number == 2:
        return "2"
    return "3+"
