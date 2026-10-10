"""Frozen ADAPTIVE_OCCUPANCY_TIMESCALE_V1 constants (design SHA below). Not tuned on an outcome."""
from __future__ import annotations

UNIT = "ADAPTIVE_OCCUPANCY_TIMESCALE_V1"
EVIDENCE_CLASS = "RETROSPECTIVE_ADAPTIVE_FORECAST_PROTOTYPE / HISTORICAL_ONLY"
CLAIM_CEILING = "HISTORICAL_ONLY"
PRODUCT_INTEGRATION_CANDIDATE = False
# Owner decision 2026-10-10: DO NOT RUN (design failed outcome-free synthetic power). run --go refuses.
OWNER_STATUS = "DESIGN_INFORMATIONALLY_INSUFFICIENT / OUTCOME_NOT_READ"

BAR_MS = 300_000
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
WEEK_MS = 7 * DAY_MS

# ---- the algorithm's frozen candidate set
LOOKBACK_HOURS = (1, 2, 3, 4, 6, 8, 12)            # OCC_L; nothing is added after the outcome
NO_OCC = "NO_OCC"
CONFIGS = (NO_OCC,) + tuple(f"OCC_{h}H" for h in LOOKBACK_HOURS)
MEMORIES_WEEKS = (26, 52, 104)
STATIC_OCC = "OCC_4H"                               # the fixed comparator

# ---- walk-forward
BLOCK_DAYS = 28                                     # outer and inner blocks: 4 ISO weeks from Monday 00:00 UTC
INNER_BLOCKS = 6                                    # inner validation = the 24 weeks before the outer block
TIE_TOL = 1e-9                                      # Brier tie -> log loss -> order below
# deterministic order after ties: NO_OCC first, then the longer memory, then the shorter lookback
VENUES = {0: "BITMEX_XBTUSD", 1: "BINANCE_USDM_BTCUSDT"}     # era 0 -> venue 0; eras 1, 2 -> venue 1
ERAS = ("BITMEX_XBTUSD_2016_2019", "BINANCE_UM_2020_2024", "BINANCE_UM_2025_2026")
ERA_VENUE = (0, 1, 1)

# ---- imported model machinery (adaptive_b1_forecast_v1.model / .metrics): values asserted equal at run time
RIDGE = 1.0                                         # L2 on standardized slopes, not the intercept
CLIP_Z = 5.0
IRLS_MAX_ITER = 50
IRLS_TOL = 1e-10

# ---- metrics and uncertainty
P_CLIP = 1e-6
BOOT_DRAWS = 2000
BOOT_SEED = 20261124
BOOT_LO = 0.025
BOOT_HI = 0.975
MIN_VALID_DRAWS = 1900
RELIABILITY_BINS = 10
DIAG_ERAS = (("2016-2019", 2016, 2019), ("2020-2022", 2020, 2022), ("2023-2024", 2023, 2024), ("2025-2026", 2025, 2026))

ROUTE_INVALID = "ADAPTIVE_OCC_IMPLEMENTATION_INVALID"
ROUTE_SUPPORTED = "ADAPTIVE_OCC_FORECAST_SKILL_SUPPORTED"
ROUTE_UNCERTAIN = "ADAPTIVE_OCC_FORECAST_SKILL_UNCERTAIN"
ROUTE_NONE = "ADAPTIVE_OCC_NO_INCREMENTAL_SKILL"
ROUTE_WORSE = "ADAPTIVE_OCC_WORSE_THAN_BASELINE"

# ---- synthetic power check (outcome-free): real features and schedule, synthetic overlapping 1h outcomes
SYN_SEED = 4242
SYN_BETA = 0.03
SYN_SWITCH_WEEKS = 52
SYN_SCENARIOS = (("NULL", None, None), ("CONSTANT_OCC_4H", "OCC_4H", "OCC_4H"), ("SWITCHING_OCC_2H_8H", "OCC_2H", "OCC_8H"))

# ---- pins (set after the design freeze commit; checked by run --go before any outcome)
DESIGN_SHA256 = "d33f32b7ec4eaa9b970f444600b9c512dc7b608523008215f710b3ef0703ee0d"
DESIGN_COMMIT = "bb5c35ef"
EXPECTED_ROWS = 361949
EXPECTED_OUTER_BLOCKS = 111
FOLD_MANIFEST_SHA256 = "8427c09eb1de60e033bb5ad4eb752ae2f14ca326e32ad9ba846af8f670d9ef10"
SELECTOR_MANIFEST_SHA256 = "4dfc58e5b12fd16993164f483dff517f2cd690c673b0ef5c66f2089e963c346a"
DESIGN_JSON_SHA256 = "0ca29fc6b70071ab0c785d94416358a9a59397a09356e4042d1ac71d7f7e00ec"
EXPECTED_FEATURE_SHA256 = "7afa8e8d1c7e22e02d33c560f0739122bb76e67083747835b827acfba0d5eeef"
EVALUATOR_DIGEST = "61c7fe401fb6da83255ba278465e9ce1448e56fa25ddb8e143dc479391dbdf80"
