"""MULTISCALE_ADAPTIVE_OCCUPANCY_V2 — synthetic adequacy protocol constants (frozen before the Monte Carlo summary).

Design engineering on synthetic outcomes only. No market outcome is read by this package."""
from __future__ import annotations

UNIT = "MULTISCALE_ADAPTIVE_OCCUPANCY_V2"
STAGE = "DESIGN_AND_SYNTHETIC_ADEQUACY (no market outcome; not frozen for market evaluation)"

# ---- candidate architectures (design engineering grid)
STRUCTURES = ("JOINT", "OFFSET")
MEMORIES = (("TRAIL", 52), ("TRAIL", 104), ("EWMA", 26))          # eligible for selection (owner's A, B, C)
REFERENCE_MEMORIES = (("EXPANDING", 0),)                            # reported, never selectable (does not adapt)
LAMBDAS_OCC = (1.0, 1e3, 1e4)                                       # none / moderate / strong at these n
LAMBDA_B1 = 1.0                                                     # the frozen B1 ridge, unchanged
EWMA_HALF_LIFE_WEEKS = 26

# ---- synthetic worlds
SCENARIOS = ("NULL", "NULL_DRIFT", "CONSTANT_OCC_4H", "SWITCHING_OCC_2H_8H", "OCC_OFF_ON")
RHO_OBS = 0.011                      # observed order: OCC_4H partial Spearman | B1, BitMEX 2016-19 (PRIMARY)
LADDER = (0.5, 1.0, 1.5, 2.0, 3.0)   # multiples of RHO_OBS (weak, observed, 1.5x, 2x, 3x)
KAPPA = {2: 0.9193, 4: 0.8485, 8: 0.8733}   # partial Spearman per unit beta (paired calibration, 16 draws)
DRIFT_SD = 0.025                     # NULL_DRIFT: per-13-week level shift (about 1 pp of P(UP))

# ---- Monte Carlo
STAGE1_SEED = 202610101              # architecture selection
STAGE2_SEED = 202610102              # fresh seeds: adequacy of the selected architecture
STAGE1_R, STAGE1_R_NULL = 50, 100
STAGE2_R, STAGE2_R_NULL = 100, 200
BATCH = 50
BOOT_DRAWS = 2000
BOOT_SEED = 20261124                 # the frozen V1 bootstrap seed (same draws as a real run would use)

# ---- stage-1 selection rule (frozen)
SELECT_NULL_FALSE_SUPPORT_MAX = 0.05
SELECT_NULL_BEAT_MAX = 0.50
SELECT_SCORE = (("SWITCHING_OCC_2H_8H", 1.0), ("SWITCHING_OCC_2H_8H", 2.0))      # mean P(SUPPORT)
SELECT_TIE_BAND = 0.05
SELECT_SECONDARY = (("CONSTANT_OCC_4H", 1.0), ("CONSTANT_OCC_4H", 2.0), ("OCC_OFF_ON", 1.0), ("OCC_OFF_ON", 2.0))
# exact ties after the secondary score: larger lambda, then OFFSET, then TRAIL_104, TRAIL_52, EWMA_26

# ---- stage-2 adequacy criterion (frozen)
C1_FALSE_SUPPORT_MAX = 0.05          # NULL and NULL_DRIFT
C2_BEAT_MAX = 0.50                   # NULL and NULL_DRIFT
C3_SUPPORT_GAIN_OVER_V1_AT_2X = 0.20     # SWITCHING
C3_BEAT_GAIN_OVER_V1_AT_1X = 0.20        # SWITCHING
C4_POWER_MIN = 0.80                  # P(SUPPORT) at 2x in SWITCHING and CONSTANT_OCC_4H
C4_LEVEL = 2.0
C5_OFF_ON_LEVEL = 2.0                # mean dBrier(V2 - B1) < 0 in OCC_OFF_ON at 2x
VERDICT_PASS = "READY_FOR_PREFLIGHT"
VERDICT_FAIL = "DESIGN_STILL_INFORMATIONALLY_INSUFFICIENT"
