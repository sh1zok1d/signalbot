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

# ---- model development (§2–§4) -------------------------------------------------------------
LAMBDA_GRID = (0.0005, 0.002, 0.008, 0.032)   # per event (objective -loglik/n + lambda/2 ||beta||^2)
LAMBDA_TIE_NATS = 0.0005
CHAMPION_TIE_NATS = 0.002
CHAMPION_TIE_ORDER = ("M1B", "M1", "M1A")
OFFSET_CLIP = 1e-4
FOLDS = (((2020,), 2021), ((2020, 2021), 2022), ((2020, 2021, 2022), 2023), ((2020, 2021, 2022, 2023), 2024))
YEARS = (2020, 2021, 2022, 2023, 2024)
SPECS = {
    "M1": ("1", "T15", "FAM_WM", "SIDE", "SIGMA_T"),
    "M1A": ("1", "T15", "WEEK", "MONTH", "SIDE"),
    "M1B": ("1", "T15"),
}
C1_TERM = "OVMM"
C1_START_MS = 1585699500000   # 2020-04-01T00:05:00Z (#363 event start)
RELIABILITY_EDGES = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0000001)
SHARP_BAND = (0.4, 0.6)

# ---- generic race stream (§8a) ---------------------------------------------------------------
GENERIC_PAIRS = ((1, 1), (1, 2), (2, 1), (2, 2))
GENERIC_SPEC = ("1", "SIGMA_T")
HOUR_MS = 3_600_000
