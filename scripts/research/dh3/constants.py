"""Frozen design constants for DH3 (five cards of three hypotheses, direction and range).

Fixed before any DH3 data byte was read. Rules not restated here (grid, barrier X, sharp-move
rule, bootstrap, Holm) are DH1's, imported unchanged.
"""

from __future__ import annotations

import math

from scripts.research.dh1 import constants as K1

PROGRAM_ID = "DIRECTIONAL_AND_RANGE_DH3"
SEARCH_FAMILY_ID = "SF-DH3"
DESIGN_RECORD = "docs/research/DH3_DESIGN.md"
DESIGN_DATE = "2026-10-04"
_ms = K1._ms

RANGE_BAR = math.log(1.15)          # the product's range materiality (beta/analogues MATERIAL_RANGE_LOG)
DIR_BAR = K1.PRACTICAL_BAR          # 3 pp
EXECUTE_MDE_FACTOR = 2.0            # a cell runs only if it can detect twice its bar
HOUR_BARS = 12
EPOCHS_ALL = [("2017H2", "2017-09-01", "2018-01-01"), ("2018", "2018-01-01", "2019-01-01"),
              ("2019", "2019-01-01", "2020-01-01"), ("2020", "2020-01-01", "2021-01-01"),
              ("2021", "2021-01-01", "2022-01-01"), ("2022", "2022-01-01", "2023-01-01"),
              ("2023", "2023-01-01", "2024-01-01"), ("2024", "2024-01-01", "2025-01-01")]

# Card DH3-L spans two calendar years (bookDepth starts 2023-01), so calendar-year epochs could never give
# the three epochs the gates need. PRE_FREEZE_DEFINITIONAL_CORRECTION (outcome-blind, before any outcome):
# card L declares half-year epochs (contract V1 §4 allows epochs other than calendar years when declared).
EPOCHS_L = [("2023H1", "2023-01-01", "2023-07-01"), ("2023H2", "2023-07-01", "2024-01-01"),
            ("2024H1", "2024-01-01", "2024-07-01"), ("2024H2", "2024-07-01", "2025-01-01")]
EPOCH_ORDER = [e[0] for e in EPOCHS_ALL] + [e[0] for e in EPOCHS_L]


def epoch_rank(name: str) -> int:
    return EPOCH_ORDER.index(name)


# surfaces per card: symbols, event start, end (exclusive)
SURFACES = {
    "DH3-P": {"SYMBOLS": ("BTC",), "START": "2020-10-01", "END": "2025-01-01"},
    "DH3-L": {"SYMBOLS": ("BTC", "ETH", "BNB", "XRP", "DOGE", "SOL"), "START": "2023-01-08", "END": "2025-01-01"},
    "DH3-O": {"SYMBOLS": ("BTC", "ETH"), "START": "2021-04-08", "END": "2025-01-01"},
    "DH3-V": {"SYMBOLS": ("BTC", "ETH", "BNB", "XRP", "DOGE", "SOL"), "START": None, "END": "2025-01-01"},   # DH2 starts
    "DH3-S": {"SYMBOLS": ("BTC",), "START": "2020-01-08", "END": "2025-01-01"},
}
REPLICATION = {"DH3-V": "SPOT_4_COINS_2017_2019 (DH2 surface)"}

# data windows
METRICS_FIRST_DAY = "2020-09-01"
METRICS_LAST_DAY = "2024-12-31"
BOOKDEPTH_FIRST_DAY = "2023-01-01"
BOOKDEPTH_LAST_DAY = "2024-12-31"
DVOL_START = "2021-03-25"
DVOL_END = "2025-01-01"
AGG_FIRST_MONTH = "2020-01"
AGG_LAST_MONTH = "2024-12"

# card P
OI_LOOKBACK_4H = 48
OI_LOOKBACK_1H = 12
CROWD_METRIC = "count_long_short_ratio"
CROWD_Z_DAYS = 30
DELEVERAGE_DECILE = 0.10
# card L
DEPTH_BAND = 1                       # percent
THIN_LOOKBACK_DAYS = 7
THIN_QUINTILE = 0.20
RECOVERY_LAG_BARS = 6                # 30 minutes after the move
# card O
DVOL_JUMP_DECILE = 0.90
UPVOL_WINDOW_H = 24
# card V
SESSIONS = {"ASIA": (0, 0, 8, 0), "EU": (8, 0, 13, 30), "US": (13, 30, 20, 0)}   # the product's sessions (UTC)
SESSION_WINDOW_BARS = 288
CONTROLS_PER_EVENT = 2
CONTROL_SEED = 20261008
RETEST_RETREAT_X = 1.0               # retreat beyond the level by at least X (the DH1 barrier unit) before the retest
# card S
STRESS_DECILE = 0.90
LEAD_LAGS_S = (1, 2, 3)
LARGE_PRINT_USD = 1_000_000.0

BOOT_SEED = 20261009

CARDS = {
    "DH3-P": {"TITLE": "Positioning (OI metrics)", "TEST_FAMILY_ID": "TF-DH3-P-POSITIONING"},
    "DH3-L": {"TITLE": "Liquidity (book depth)", "TEST_FAMILY_ID": "TF-DH3-L-LIQUIDITY"},
    "DH3-O": {"TITLE": "Options (DVOL)", "TEST_FAMILY_ID": "TF-DH3-O-OPTIONS"},
    "DH3-V": {"TITLE": "Levels extended", "TEST_FAMILY_ID": "TF-DH3-V-LEVELS"},
    "DH3-S": {"TITLE": "Spot<->perp at one second", "TEST_FAMILY_ID": "TF-DH3-S-SPOT-PERP"},
}

HYPOTHESES = [
    {"ID": "DH3-P1", "CARD": "DH3-P", "STATE": "LEVERAGE_LOADING", "ENDPOINT": "RANGE_4H", "EXTRA": (),
     "ATLAS_CELL": "VOLATILITY_STATE.compression x POSITIONING"},
    {"ID": "DH3-P2", "CARD": "DH3-P", "STATE": "DELEVERAGING", "ENDPOINT": "RANGE_4H", "EXTRA": ("ABS_RET1_TERCILE",),
     "ATLAS_CELL": "VOLATILITY_STATE.shock_recovery x POSITIONING"},
    {"ID": "DH3-P3", "CARD": "DH3-P", "STATE": "CROWD_LONG", "ENDPOINT": "UP_FIRST_4H", "EXTRA": ("TREND24_TERCILE",),
     "ATLAS_CELL": "DERIVATIVES.leverage_crowding x POSITIONING"},
    {"ID": "DH3-L1", "CARD": "DH3-L", "STATE": "THIN_BOOK", "ENDPOINT": "RANGE_4H", "EXTRA": ("SYMBOL",),
     "ATLAS_CELL": "MICROSTRUCTURE.liquidity_withdrawal x ORDER_BOOK"},
    {"ID": "DH3-L2", "CARD": "DH3-L", "STATE": "BID_HEAVY_BOOK", "ENDPOINT": "UP_FIRST_4H", "EXTRA": ("SYMBOL",),
     "ATLAS_CELL": "MICROSTRUCTURE.book_imbalance x ORDER_BOOK"},
    {"ID": "DH3-L3", "CARD": "DH3-L", "STATE": "BOOK_NOT_RECOVERED", "ENDPOINT": "RANGE_4H", "EXTRA": ("MOVE_TERCILE", "SYMBOL"),
     "ATLAS_CELL": "MICROSTRUCTURE.book_recovery x ORDER_BOOK"},
    {"ID": "DH3-O1", "CARD": "DH3-O", "STATE": "IMPLIED_ABOVE_REALIZED", "ENDPOINT": "RANGE_4H", "EXTRA": ("SYMBOL",),
     "ATLAS_CELL": "OPTIONS_REGION.implied_vs_realized x OPTIONS"},
    {"ID": "DH3-O2", "CARD": "DH3-O", "STATE": "DVOL_JUMP", "ENDPOINT": "RANGE_4H", "EXTRA": ("ABS_RET1_TERCILE", "SYMBOL"),
     "ATLAS_CELL": "OPTIONS_REGION.implied_vs_realized x OPTIONS"},
    {"ID": "DH3-O3", "CARD": "DH3-O", "STATE": "UP_VOL_REGIME", "ENDPOINT": "UP_FIRST_4H", "EXTRA": ("TREND24_TERCILE", "SYMBOL"),
     "ATLAS_CELL": "OPTIONS_REGION.implied_vs_realized x OPTIONS"},
    {"ID": "DH3-V1", "CARD": "DH3-V", "STATE": "SESSION_EXTREME", "ENDPOINT": "LEVEL_HOLD_4H", "EXTRA": ("SYMBOL", "SESSION"),
     "ATLAS_CELL": "PRICE_STRUCTURE.levels x CANDLES"},
    {"ID": "DH3-V2", "CARD": "DH3-V", "STATE": "KEY_LEVEL", "ENDPOINT": "RANGE_4H", "EXTRA": ("SYMBOL", "TYPE_GROUP"),
     "ATLAS_CELL": "PRICE_STRUCTURE.levels x CANDLES"},
    {"ID": "DH3-V3", "CARD": "DH3-V", "STATE": "RETEST", "ENDPOINT": "LEVEL_HOLD_4H", "EXTRA": ("SYMBOL", "TYPE"),
     "ATLAS_CELL": "PRICE_STRUCTURE.levels x CANDLES"},
    {"ID": "DH3-S1", "CARD": "DH3-S", "STATE": "SPOT_LED_STRESS", "ENDPOINT": "RANGE_4H", "EXTRA": (),
     "ATLAS_CELL": "SPOT_PERP.stress_lead_lag x SPOT"},
    {"ID": "DH3-S2", "CARD": "DH3-S", "STATE": "SPOT_LED_STRESS", "ENDPOINT": "CONT_FIRST_4H", "EXTRA": ("ABS_RET1_TERCILE",),
     "ATLAS_CELL": "SPOT_PERP.stress_lead_lag x PERP_FLOW"},
    {"ID": "DH3-S3", "CARD": "DH3-S", "STATE": "LARGE_PERP_PRINTS", "ENDPOINT": "RANGE_4H", "EXTRA": (),
     "ATLAS_CELL": "FLOW.participant_composition x PERP_FLOW"},
]
HYPOTHESIS_BY_ID = {h["ID"]: h for h in HYPOTHESES}
NUISANCE_COMMON = ("HOUR_BLOCK", "RV_TERCILE", "LAG_TERCILE")


def bar_of(h: dict) -> float:
    return RANGE_BAR if h["ENDPOINT"] == "RANGE_4H" else DIR_BAR


def assert_locked() -> None:
    if len(HYPOTHESES) != 15 or len(CARDS) != 5:
        raise RuntimeError("DH3 design drifted")
    for card in CARDS:
        if sum(1 for h in HYPOTHESES if h["CARD"] == card) != 3:
            raise RuntimeError("DH3: every card holds exactly 3 primary cells")
    if abs(RANGE_BAR - math.log(1.15)) > 1e-12 or DIR_BAR != 0.03:
        raise RuntimeError("DH3 bars drifted")
