"""Frozen ADAPTIVE_B1_FORECAST_V1 constants (design SHA below). Not tuned on an outcome."""
from __future__ import annotations

UNIT = "ADAPTIVE_B1_FORECAST_V1"
EVIDENCE_CLASS = "RETROSPECTIVE_ADAPTIVE_FORECAST_PROTOTYPE / HISTORICAL_ONLY"
CLAIM_CEILING = "HISTORICAL_ONLY"
PRODUCT_INTEGRATION_CANDIDATE = False

ERAS = ("BITMEX_XBTUSD_2016_2019", "BINANCE_UM_2020_2024", "BINANCE_UM_2025_2026")
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
WEEK_MS = 7 * DAY_MS
BLOCK_DAYS = 28                       # outer and inner block length (4 ISO weeks, Monday 00:00 UTC)
MEMORIES_WEEKS = (26, 52, 104)        # trailing training memories (ADAPTIVE candidates)
INNER_BLOCKS = 6                      # inner validation = the 6 blocks (24 weeks) before the outer block
TIE_TOL = 1e-9                        # inner Brier tie -> prefer the longer memory (less adaptive)
RIDGE = 1.0                           # L2 on standardized slopes (not the intercept), frozen
CLIP_Z = 5.0
P_CLIP = 1e-6
IRLS_MAX_ITER = 50
IRLS_TOL = 1e-10
RELIABILITY_BINS = 10                 # equal-count bins of predicted probability

BOOT_DRAWS = 2000
BOOT_SEED = 20261123
BOOT_LO = 0.025
BOOT_HI = 0.975
MIN_VALID_DRAWS = 1900

DIAG_ERAS = (("2018-2019", 2018, 2019), ("2020-2022", 2020, 2022), ("2023-2024", 2023, 2024), ("2025-2026", 2025, 2026))

ROUTE_INVALID = "ADAPTIVE_B1_IMPLEMENTATION_INVALID"
P1 = {"SUPPORTED": "B1_OOS_SKILL_SUPPORTED", "UNCERTAIN": "B1_OOS_SKILL_UNCERTAIN",
      "NONE": "B1_NO_OOS_SKILL", "WORSE": "B1_WORSE_THAN_CLIMATOLOGY"}
P2 = {"SUPPORTED": "ADAPTATION_IMPROVES_FORECAST", "UNCERTAIN": "ADAPTATION_UNCERTAIN",
      "NONE": "ADAPTATION_NO_GAIN", "WORSE": "ADAPTATION_WORSE"}

# synthetic power check (outcome-free): real features, synthetic overlapping 1h outcomes
SYN_SEED = 777
SYN_SCENARIOS = (("NULL", 0.0, 0.0), ("CONSTANT_0.03", 0.03, 0.03), ("SWITCHING_0.06_0_52W", 0.06, 0.0))
SYN_SWITCH_WEEKS = 52

# ---- pins
DESIGN_SHA256 = "PENDING"
DESIGN_COMMIT = "PENDING"
EXPECTED_ROWS = None
EXPECTED_OUTER_BLOCKS = None
EXPECTED_FIRST_OUTER_MS = None
