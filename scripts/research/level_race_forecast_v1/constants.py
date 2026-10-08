"""Frozen constants of LEVEL_RACE_FORECAST_V1 (design 997ba98615135b263684ad10f9c044335910a346).

Event, barriers and outcome are the #352 constants, imported unchanged.
"""

from __future__ import annotations

from scripts.research.level_touch_degradation_v1 import constants as K352

UNIT = "LEVEL_RACE_FORECAST_V1"
DESIGN_SHA = "997ba98615135b263684ad10f9c044335910a346"
RULE_ID = "LEVEL_RACE_4H_V1"

ZONE_HALF = K352.ZONE_HALF_PRIMARY
WINDOW_BARS = K352.HOLD_BARS_PRIMARY          # j+1 .. j+48
T15_OFFSET = 2                                # T15 = close of bar j+2
LANDMARKS = ("T0", "T15")
TAU = {"T0": WINDOW_BARS, "T15": WINDOW_BARS - T15_OFFSET}   # 48, 46

PROB_FLOOR = 0.001
B0_TERM_EPS = 1e-15
B0_MAX_TERMS = 20000

# ---- HIST (§0) -------------------------------------------------------------------------------
HIST_TABLE_VERSION = "LEVEL_RACE_HIST_TABLE_V1"
HIST_LABEL = "2020–2024"
BAND_EDGES = (0.35, 0.55)                     # on B0_beyond at T15; a priori numbers
BANDS = ("F1", "F2", "F3")
N_MIN = 30
BOOT_DRAWS = 2000
BOOT_SEED = 20261008
CI_ALPHA = 0.05
OUTCOMES = ("BEYOND", "BACK", "NEITHER")      # = #352 BREAK / REJECT / NEITHER
FAMILIES = K352.FAMILIES
STRUCT_SIDES = (1, -1)
