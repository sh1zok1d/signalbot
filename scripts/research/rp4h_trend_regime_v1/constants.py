"""Frozen RP4H_TREND_REGIME_MODULATION_V1 constants (design SHA below). Not tuned on an outcome."""
from __future__ import annotations

UNIT = "RP4H_TREND_REGIME_MODULATION_V1"
MODE = "DISCOVERY"
EVIDENCE_CLASS = "ADAPTIVE_HISTORICAL_DISCOVERY (question unread on CORE; RP4H outcome vector known)"
CLAIM_CEILING = "DISCOVERY_ONLY"
PRODUCT_INTEGRATION_CANDIDATE = False

BAR_MS = 300_000
SURFACE_START_MS = 1_577_836_800_000   # 2020-01-01
SURFACE_END_MS = 1_735_689_600_000     # 2025-01-01 (exclusive)
LOOKBACK_24H = 288
N_TERCILES = 3

B0 = ("ret4", "rv4")                       # controls of the RP4H partial (its canonical estimand)
B1 = ("ret4", "rv4", "ret1h", "ret15")     # secondary: plus the local path

BOOT_DRAWS = 2000
BOOT_SEED = 20261122
BOOT_LO = 0.025
BOOT_HI = 0.975
MIN_VALID_DRAWS = 1900

# rules §4 search-exposure bar: m = CORE x DIRECTION before (~840, after DIRECTIONAL_STATE_SEARCH_V2) + this unit's cells
M_ST_BEFORE = 840
FAMILYWISE_ALPHA = 0.10
UNIT_CELLS = ("delta_b0", "rho_t1_b0", "rho_t2_b0", "rho_t3_b0", "delta_b1", "interaction_b0")

ROUTE_INVALID = "TREND_REGIME_IMPLEMENTATION_INVALID"
ROUTE_DISCOVERED = "TREND_REGIME_MODULATION_DISCOVERED"          # delta > 0, CI > 0: reversal weaker in trending regime
ROUTE_OPPOSITE = "TREND_REGIME_MODULATION_OPPOSITE"              # delta < 0, CI < 0: reversal stronger in trending regime
ROUTE_NONE = "TREND_REGIME_MODULATION_NOT_DETECTED"

# ---- pins
DESIGN_SHA256 = "c1343df4a7399e9c5cb7bab475605c7b2b8feaa289bbbee953df47c8cc2d94d1"
DESIGN_COMMIT = "PENDING"
EXPECTED_N = None
EXPECTED_WEEKS = None
TS_TERCILE_EDGES = None    # frozen from the outcome-blind preflight (state quantiles only)
