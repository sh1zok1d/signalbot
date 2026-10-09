"""Frozen PRE_IMPULSE_STATE_ATLAS_V1 search bounds.

The feature list, grid, horizons, and ranking rule are the search. They are not
admission thresholds and they are not chosen from a market result.
"""

from __future__ import annotations

UNIT = "PRE_IMPULSE_STATE_ATLAS_V1"
EVIDENCE_CLASS = "HISTORICAL_DIRECTIONAL_DISCOVERY / ADAPTIVE_SEARCH"
CLAIM_CEILING = "DISCOVERY_ONLY"
DESIGN_SHA256 = "01b7eafb7d2231388503a0c523e1443eceba7666b774ec8d0c1dc5fb055c3a5b"

SURFACE = "CORE_BTC_BINANCE_V0"
DATA_START_MS = 1_577_836_800_000  # 2020-01-01T00:00:00Z
SURFACE_END_MS = 1_735_689_600_000  # 2025-01-01T00:00:00Z exclusive on bar opens and on T
BAR_MS = 300_000
ANCHOR_MS = 900_000  # 15 minutes
MIN_INDEX = 96  # prior 4h window ends 48 bars before T; recent window is 48 bars
WEEK_MIN_ANCHORS = 30
YEAR_MIN_N = 200
SUPPORT_WEEK_SCALE = 100
NEAR_BAND = 0.15
DIST_MULT = 1.0
FLOW_INELIGIBLE = True
PRIMARY_HORIZONS = ("1h", "4h", "8h")
CLOCK_COLLISION = "ADJACENT_D12_DIFFERENT_ENDPOINT"

BYBIT_PRICE = "docs/research_data/LEVEL_CROSS_VENUE_PERP_5M_V0/bybit_btcusdt_linear_5m.csv.gz"
BYBIT_SHA256 = "f7ef739f7d359056cbbf78a77993995f54e3303e50775b5aadf36b4ba68f507c"
OKX_PRICE = "docs/research_data/LEVEL_CROSS_VENUE_PERP_5M_V0/okx_btc_usdt_swap_5m.csv.gz"
OKX_SHA256 = "b435fdec219df96e88e2ae4b65c04e16217af16f327aae36dca148d9203172a8"

BOOT_DRAWS = 1000
BOOT_SEED = 20261116
BOOT_LO = 0.025
BOOT_HI = 0.975

# (name, bars of 5m, used in the shortlist)
HORIZONS = (
    ("1h", 12, True),
    ("4h", 48, True),
    ("8h", 96, True),
    ("24h", 288, False),
)

# UTC hour half-open blocks. Conventional session labels, not a searched clock.
SESSIONS = (
    ("asia", 0, 7),
    ("europe", 7, 13),
    ("us", 13, 21),
    ("late", 21, 24),
)
CLOCK_BASES = ("range_ratio_60_240", "frac_near_upper_4h", "frac_near_lower_4h")

# collision is assigned from prior records before any ranking.
# eligible False never enters the shortlist.
FEATURES = (
    {"id": "rv_1h", "family": "geometry", "eligible": True, "mirror": None, "expect": None,
     "high_means": "larger 1h realized volatility", "collision": "ADJACENT_VOLATILITY_DIFFERENT_ENDPOINT"},
    {"id": "rv_4h", "family": "geometry", "eligible": True, "mirror": None, "expect": None,
     "high_means": "larger 4h realized volatility", "collision": "ADJACENT_VOLATILITY_DIFFERENT_ENDPOINT"},
    {"id": "log_range_1h", "family": "geometry", "eligible": True, "mirror": None, "expect": None,
     "high_means": "wider 1h log range", "collision": "ADJACENT_VOLATILITY_DIFFERENT_ENDPOINT"},
    {"id": "log_range_4h", "family": "geometry", "eligible": True, "mirror": None, "expect": None,
     "high_means": "wider 4h log range", "collision": "ADJACENT_VOLATILITY_DIFFERENT_ENDPOINT"},
    {"id": "range_ratio_30_240", "family": "compression", "eligible": True, "mirror": None, "expect": None,
     "high_means": "30m range large relative to 4h range", "collision": "ADJACENT_FORMATION_WIDTH_DIFFERENT_ENDPOINT"},
    {"id": "range_ratio_60_240", "family": "compression", "eligible": True, "mirror": None, "expect": None,
     "high_means": "1h range large relative to 4h range", "collision": "ADJACENT_FORMATION_WIDTH_DIFFERENT_ENDPOINT"},
    {"id": "range_ratio_120_240", "family": "compression", "eligible": True, "mirror": None, "expect": None,
     "high_means": "2h range large relative to 4h range", "collision": "ADJACENT_FORMATION_WIDTH_DIFFERENT_ENDPOINT"},
    {"id": "rv_ratio_60_240", "family": "compression", "eligible": True, "mirror": None, "expect": None,
     "high_means": "1h RV large relative to 4h RV", "collision": "ADJACENT_FORMATION_WIDTH_DIFFERENT_ENDPOINT"},
    {"id": "compression_slope_1h", "family": "compression", "eligible": True, "mirror": None, "expect": None,
     "high_means": "1h range wider than the prior 1h range", "collision": "ADJACENT_FORMATION_WIDTH_DIFFERENT_ENDPOINT"},
    {"id": "efficiency_1h", "family": "geometry", "eligible": True, "mirror": None, "expect": None,
     "high_means": "1h path closer to a straight line", "collision": "ADJACENT_H03_DIFFERENT_FORMULATION"},
    {"id": "efficiency_4h", "family": "geometry", "eligible": True, "mirror": None, "expect": None,
     "high_means": "4h path closer to a straight line", "collision": "ADJACENT_H03_DIFFERENT_FORMULATION"},
    {"id": "close_pos_4h", "family": "morphology", "eligible": True, "mirror": None, "expect": None,
     "high_means": "close near the 4h high", "collision": "NEW_LOCAL_GEOMETRY"},
    {"id": "dir_changes_1h", "family": "geometry", "eligible": True, "mirror": None, "expect": None,
     "high_means": "more 5m sign changes inside 1h", "collision": "NEW_LOCAL_GEOMETRY"},
    {"id": "midpoint_slope_4h", "family": "geometry", "eligible": True, "mirror": None, "expect": None,
     "high_means": "4h range midpoint migrating upward", "collision": "NEW_LOCAL_GEOMETRY"},
    {"id": "dist_upper_4h", "family": "boundary", "eligible": True, "mirror": "dist_lower_4h", "expect": "opposite",
     "high_means": "close far below the 4h high", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "dist_lower_4h", "family": "boundary", "eligible": True, "mirror": "dist_upper_4h", "expect": "opposite",
     "high_means": "close far above the 4h low", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "frac_near_upper_4h", "family": "boundary", "eligible": True, "mirror": "frac_near_lower_4h", "expect": "opposite",
     "high_means": "more closes in the upper band of the 4h range", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "frac_near_lower_4h", "family": "boundary", "eligible": True, "mirror": "frac_near_upper_4h", "expect": "opposite",
     "high_means": "more closes in the lower band of the 4h range", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "bars_since_upper_4h", "family": "boundary", "eligible": True, "mirror": "bars_since_lower_4h", "expect": "opposite",
     "high_means": "longer time since the last upper-band print", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "bars_since_lower_4h", "family": "boundary", "eligible": True, "mirror": "bars_since_upper_4h", "expect": "opposite",
     "high_means": "longer time since the last lower-band print", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "touch_count_upper_4h", "family": "boundary", "eligible": True, "mirror": "touch_count_lower_4h", "expect": "opposite",
     "high_means": "more entries into the upper band", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "touch_count_lower_4h", "family": "boundary", "eligible": True, "mirror": "touch_count_upper_4h", "expect": "opposite",
     "high_means": "more entries into the lower band", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "last_rejection_upper_4h", "family": "boundary", "eligible": True, "mirror": "last_rejection_lower_4h", "expect": "opposite",
     "high_means": "larger pullback after the latest upper-band print", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "last_rejection_lower_4h", "family": "boundary", "eligible": True, "mirror": "last_rejection_upper_4h", "expect": "opposite",
     "high_means": "larger pullback after the latest lower-band print", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "extension_up", "family": "acceptance", "eligible": True, "mirror": "extension_down", "expect": "opposite",
     "high_means": "recent 4h high extends farther beyond the prior 4h high", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "extension_down", "family": "acceptance", "eligible": True, "mirror": "extension_up", "expect": "opposite",
     "high_means": "recent 4h low extends farther beyond the prior 4h low", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "frac_above_prior_high", "family": "acceptance", "eligible": True, "mirror": "frac_below_prior_low", "expect": "opposite",
     "high_means": "more recent closes above the prior 4h high", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "frac_below_prior_low", "family": "acceptance", "eligible": True, "mirror": "frac_above_prior_high", "expect": "opposite",
     "high_means": "more recent closes below the prior 4h low", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "reentry_up", "family": "acceptance", "eligible": True, "mirror": "reentry_down", "expect": "opposite",
     "high_means": "more returns back inside after trading above the prior high", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "reentry_down", "family": "acceptance", "eligible": True, "mirror": "reentry_up", "expect": "opposite",
     "high_means": "more returns back inside after trading below the prior low", "collision": "ADJACENT_H02_B202_DIFFERENT_FORMULATION"},
    {"id": "adverse_share_4h", "family": "countertrend", "eligible": True, "mirror": None, "expect": None,
     "high_means": "more of the 4h path spent moving against its own net direction", "collision": "ADJACENT_H03_H04_DIFFERENT_FORMULATION"},
    {"id": "last_against_share_4h", "family": "countertrend", "eligible": True, "mirror": None, "expect": None,
     "high_means": "the path ends in a larger move against its 4h net direction", "collision": "ADJACENT_H03_H04_DIFFERENT_FORMULATION"},
    {"id": "countertrend_last_frac_4h", "family": "countertrend", "eligible": True, "mirror": None, "expect": None,
     "high_means": "the latest against-move is a larger share of all against-moves", "collision": "ADJACENT_H03_H04_DIFFERENT_FORMULATION"},
    {"id": "up_bars_per_vol", "family": "speed", "eligible": True, "mirror": "down_bars_per_vol", "expect": "opposite",
     "high_means": "slower recent travel of one 4h-vol unit upward", "collision": "NEW_LOCAL_GEOMETRY"},
    {"id": "down_bars_per_vol", "family": "speed", "eligible": True, "mirror": "up_bars_per_vol", "expect": "opposite",
     "high_means": "slower recent travel of one 4h-vol unit downward", "collision": "NEW_LOCAL_GEOMETRY"},
    {"id": "speed_ratio_up_down", "family": "speed", "eligible": True, "mirror": None, "expect": None,
     "high_means": "up-travel slower than down-travel over the same vol unit", "collision": "NEW_LOCAL_GEOMETRY"},
    {"id": "mean_clv_1h", "family": "morphology", "eligible": True, "mirror": None, "expect": None,
     "high_means": "1h closes sit higher inside each bar", "collision": "NEW_LOCAL_GEOMETRY"},
    {"id": "mean_upper_wick_1h", "family": "morphology", "eligible": True, "mirror": "mean_lower_wick_1h", "expect": "opposite",
     "high_means": "larger upper wicks over 1h", "collision": "NEW_LOCAL_GEOMETRY"},
    {"id": "mean_lower_wick_1h", "family": "morphology", "eligible": True, "mirror": "mean_upper_wick_1h", "expect": "opposite",
     "high_means": "larger lower wicks over 1h", "collision": "NEW_LOCAL_GEOMETRY"},
    {"id": "mean_body_1h", "family": "morphology", "eligible": True, "mirror": None, "expect": None,
     "high_means": "larger candle bodies relative to range", "collision": "NEW_LOCAL_GEOMETRY"},
    {"id": "frac_close_upper_1h", "family": "morphology", "eligible": True, "mirror": "frac_close_lower_1h", "expect": "opposite",
     "high_means": "more closes in the top quarter of the 1h range", "collision": "NEW_LOCAL_GEOMETRY"},
    {"id": "frac_close_lower_1h", "family": "morphology", "eligible": True, "mirror": "frac_close_upper_1h", "expect": "opposite",
     "high_means": "more closes in the bottom quarter of the 1h range", "collision": "NEW_LOCAL_GEOMETRY"},
    {"id": "wick_asym_slope_1h", "family": "morphology", "eligible": True, "mirror": None, "expect": None,
     "high_means": "lower wick minus upper wick rising through the hour", "collision": "NEW_LOCAL_GEOMETRY"},
    {"id": "xdisp_std_15m", "family": "cross_venue", "eligible": True, "mirror": None, "expect": None,
     "high_means": "Binance, Bybit and OKX 15m returns disagree more", "collision": "ADJACENT_D9_M06_DIFFERENT_OBJECT"},
    {"id": "n_confirm_15m", "family": "cross_venue", "eligible": True, "mirror": None, "expect": None,
     "high_means": "more venues share the sign of the Binance 15m return", "collision": "ADJACENT_D9_M06_DIFFERENT_OBJECT"},
    {"id": "binance_lag_15m", "family": "cross_venue", "eligible": True, "mirror": None, "expect": None,
     "high_means": "the other venues rose more than Binance over the last 15m", "collision": "ADJACENT_D9_M06_DIFFERENT_OBJECT"},
    {"id": "bybit_leader_signed", "family": "cross_venue", "eligible": True, "mirror": None, "expect": None,
     "high_means": "Bybit led the last 15m and its return was positive", "collision": "ADJACENT_D9_M06_DIFFERENT_OBJECT"},
    {"id": "okx_leader_signed", "family": "cross_venue", "eligible": True, "mirror": None, "expect": None,
     "high_means": "OKX led the last 15m and its return was positive", "collision": "ADJACENT_D9_M06_DIFFERENT_OBJECT"},
    {"id": "flow_beta_1h", "family": "flow", "eligible": False, "mirror": None, "expect": None,
     "high_means": "1h price responded more in the direction of taker imbalance", "collision": "COSMETIC_NEIGHBORHOOD_H05_B205"},
    {"id": "flow_corr_1h", "family": "flow", "eligible": False, "mirror": None, "expect": None,
     "high_means": "1h returns and taker imbalance moved together", "collision": "COSMETIC_NEIGHBORHOOD_H05_B205"},
)

FEATURE_BY_ID = {row["id"]: row for row in FEATURES}

REFUSAL_RERUN = "REFUSING_RERUN"
OI_OPENED = False
LEVEL_ENGINE_USED = False
OBJECTS_2025_2026_USED = False
PRODUCT_CODE_CHANGED = False
