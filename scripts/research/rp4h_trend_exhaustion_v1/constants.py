"""RP4H_TREND_EXHAUSTION_INTERACTION_V1 — frozen constants of the information-adequacy gate (before any simulation
summary). No market interaction outcome is read by this package."""
from __future__ import annotations

UNIT = "RP4H_TREND_EXHAUSTION_INTERACTION_V1"
STAGE = "EXACT_PARITY + EXPOSURE_AUDIT + OUTCOME_FREE_ADEQUACY_GATE (no market interaction outcome)"
CANDIDATE_STATUS = "DISCOVERY_CANDIDATE_FROM_SIGN_REVERSED_PRIMARY_HYPOTHESIS"

BAR_MS = 300_000
LOOKBACK_24H = 288                    # TS_24H window (Unit 1)

# ---- discovery (RP4H_TREND_REGIME_MODULATION_V1, CORE 2020-24; recorded, not recomputed)
DISCOVERY_INTERACTION_B0 = -0.01186966202306912
DISCOVERY_INTERACTION_B0_CI = (-0.020208846061829724, -0.004027209754568008)
UNIT1_TS_TERCILE_EDGES = (0.36032530929162965, 0.8528621530723187)   # frozen in Unit 1 (descriptive strata only)
PRIMARY_CONTROLS = ("rp", "ts", "ret4", "rv4")                        # Unit 1 interaction_b0, exactly
SECONDARY_LOCAL_CONTROLS = ("rp", "ts", "ret4", "rv4", "ret1h", "ret15")   # predeclared now; no CORE value exists

# ---- canonical bootstrap of a real run (Unit 1 machinery; new seed for this unit)
BOOT_DRAWS = 2000
BOOT_SEED = 20261125
BOOT_LO, BOOT_HI = 0.025, 0.975
MIN_VALID_DRAWS = 1900

# ---- synthetic adequacy study
SURFACES = ("BITMEX_XBTUSD_2016_2019", "BINANCE_UM_BTCUSDT_2025_2026")
POOLED = "POOLED_BITMEX_PLUS_BINANCE_2025_2026"     # informational only; never selectable by the frozen rule
LADDER = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0)            # multiples of |DISCOVERY_INTERACTION_B0|; 3x only locates the MDE
MAIN_RP4H_PARTIAL = -0.030                          # planted main effect (CORE order), all levels incl. null
VOL_LAG_BARS = 13                                   # per-bar noise scale uses bars <= k-13 (past of every anchor)
VOL_WINDOW_BARS = 48
VOL_MIN_FINITE = 24
STUDY_SEED = 202610111
SENS_SEED = 202610112
REPS = 400                                          # per surface and level, primary (heteroskedastic) DGP
SENS_REPS = 200                                     # homoskedastic sensitivity, levels 0 and 1 only
SENS_LEVELS = (0.0, 1.0)
CALIB_DRAWS = 16
CALIB_BETA = 0.03
VALIDATE_REPS = 2                                   # canonical re-rank bootstrap vs the fast fixed-residual bootstrap
CI_WIDTH_RATIO_REDO = 1.10                          # if canonical/fast CI width > this, recompute the gate widened

# ---- frozen adequacy criterion (per surface) and surface rule
NULL_FALSE_SUPPORT_MAX = 0.05     # P(SUPPORTED | 0) and P(SIGN_OPPOSES | 0)
POWER_MIN_AT_1X = 0.80            # P(SUPPORTED | 1x discovery magnitude), primary DGP AND homoskedastic sensitivity
VERDICT_INSUFFICIENT = "TREND_EXHAUSTION_REPLICATION_INFORMATIONALLY_INSUFFICIENT"

# ---- routes of a real run (frozen; PRIMARY interaction_b0 only)
ROUTE_INVALID = "IMPLEMENTATION_INVALID"
ROUTE_SUPPORTED = "TREND_EXHAUSTION_INTERACTION_REPLICATION_SUPPORTED"
ROUTE_UNCERTAIN = "TREND_EXHAUSTION_INTERACTION_DIRECTION_COMPATIBLE_UNCERTAIN"
ROUTE_NOT = "TREND_EXHAUSTION_INTERACTION_NOT_REPLICATED"
ROUTE_OPPOSES = "TREND_EXHAUSTION_INTERACTION_SIGN_OPPOSES"
