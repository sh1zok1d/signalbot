"""Frozen design constants for AUTOGEN_G01 (autonomous research generation 1).

Fixed before any count and before any outcome. The hypothesis table is the single
source for planning, preregistration and the one-shot evaluator. No market value is
read here.
"""

from __future__ import annotations

PROGRAM_ID = "AUTOGEN_G01"
SEARCH_FAMILY_ID = "SF-AUTOGEN-G01"
CONTRACT_VERSION = "GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V1"
EVALUATION_CONTRACT = "HYPOTHESIS_EVALUATION_CONTRACT_V1"
DESIGN_DATE = "2026-10-03"

# Surfaces (identical bounds to the R03 discovery and replication surfaces)
DISCOVERY_SURFACE = {"ID": "BINANCE_2020_2024", "START": "2020-01-01", "END": "2025-01-01"}
HISTORICAL_WINDOW = "2020-01..2024-12"
DISCOVERY_START_MS = 1577836800000  # 2020-01-01T00:00Z
DISCOVERY_END_MS = 1735689600000  # 2025-01-01T00:00Z (exclusive)
REPLICATION_BITMEX = {"ID": "BITMEX_2016_2019", "START": "2017-01-01", "END": "2020-01-01"}
BITMEX_START_MS = 1483228800000  # 2017-01-01T00:00Z
BITMEX_END_MS = DISCOVERY_START_MS

# Datasets
DATASET_BTC = "CORE_BTC_BINANCE_V0"
DATASET_BITMEX = "D2_BITMEX_PRE2020_XBTUSD"
DATASET_NYSE = "NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0"

# Effect bar and inference (the bar and the heterogeneity/nuisance rules equal R03's,
# whose frozen evaluate module is imported and bound by digest)
MIN_MEANINGFUL_EFFECT = 0.5
EFFECT_UNITS = "COMPARATOR_SD_OF_STANDARDIZED_TARGET"
PRACTICAL_BAR_RATIONALE = (
    "The beta briefing ranks activity and range against recent same-window baselines and flags "
    "the extremes. A calendar state that shifts the target distribution by half a comparator SD "
    "roughly doubles the flag rate; a smaller shift is not worth a baseline correction or a "
    "user-facing sentence. Same bar as OWNER_CARDS_R03, set before any count or outcome."
)
FAMILY_ALPHA = 0.05
MULTIPLICITY = "HOLM_WITHIN_CARD_OVER_EXECUTED_HYPOTHESES"
SIGNFLIP_DRAWS = 20000
SIGNFLIP_SEED = 20261010
BLOCKPERM_DRAWS = 20000
BLOCKPERM_SEED = 20261011
BLOCK_WEEKS = 4
HET_SEED = 20261012
MOVING_BLOCK_UNITS = 4
MOVING_BLOCK_DRAWS = 2000
PRODUCT_FREQUENCY_MIN_PER_YEAR = 12
PRIOR_RV_MINUTES = 1440

MINUTE_MS = 60_000
HOUR_MS = 3_600_000
DAY_MS = 86_400_000

# Card A calendar rules
TOM_LAST_DAY_OFFSET = 1  # the last calendar day of the previous month
TOM_FIRST_DAYS = (1, 2, 3)
COMPARATOR_DAYS = tuple(range(8, 22))  # days 8..21
HOLIDAY_WINDOWS = (((12, 24), (1, 2)), ((10, 1), (10, 7)))  # inclusive, fixed dates, both surfaces
MONTH_END_HOUR_UTC = 23

# Card B calendar rules
ETF_LAUNCH_DATE = "2024-01-11"
PRE_LAST_DATE = "2024-01-07"  # end of ISO 2024-W01
POST_FIRST_DATE = "2024-01-15"  # start of ISO 2024-W03; the launch week 2024-W02 is dropped
NY_FIX_HOUR = "15:00"
NY_ADJACENT_HOURS = ("13:00", "14:00")
NY_ZONE = "America/New_York"

CARDS = {
    "G01-A": {
        "TITLE": "Turn-of-month cash-flow clock",
        "FAMILY": "J-adjacent",
        "FAMILY_NAME": "CALENDAR_CASH_FLOW_CLOCK (day-of-month; not sessions, not expiry, not tax-year)",
        "TEST_FAMILY_ID": "TF-G01-A-TURN-OF-MONTH",
        "DATASETS": [DATASET_BTC, DATASET_BITMEX],
        "REPLICATION": "BITMEX_HISTORICAL",
    },
    "G01-B": {
        "TITLE": "ETF NAV fixing window (natural experiment at the 2024-01-11 launch)",
        "FAMILY": "G-adjacent",
        "FAMILY_NAME": "SCHEDULED_REFERENCE_FIXING (ETF era; not FOMC/CPI/NFP; not CME monthly settlement)",
        "TEST_FAMILY_ID": "TF-G01-B-ETF-FIXING-WINDOW",
        "DATASETS": [DATASET_BTC, DATASET_NYSE],
        "REPLICATION": "PROSPECTIVE",
    },
}

HYPOTHESES = [
    {
        "ID": "G01-A1", "CARD": "G01-A", "NAME": "TOM_PARTICIPATION", "DESIGN": "PAIRED_UNIT",
        "UNIT": "CALENDAR_MONTH", "TARGET": "LOG_TRADE_COUNT", "WINDOW": "UTC_DAY", "DIRECTION": "POSITIVE",
        "STATE": "turn-of-month UTC days: the last day of the previous month and days 1-3, minus the last-Friday expiry day and the fixed holiday windows",
        "COMPARATOR": "UTC days 8-21 of the same month, outside the fixed holiday windows",
        "MECHANISM": "Recurring fiat-rail cash flows (salary-linked purchases, monthly DCA, fund subscriptions, month-end marks) concentrate at the turn of the month, so participation is higher on those days.",
        "REPLICATION": True,
        "REPLICATION_NOTE": "BitMEX XBTUSD 5m trade counts, 2017-01..2019-12, same calendar rule.",
    },
    {
        "ID": "G01-A2", "CARD": "G01-A", "NAME": "TOM_RANGE", "DESIGN": "PAIRED_UNIT",
        "UNIT": "CALENDAR_MONTH", "TARGET": "LOG_RANGE", "WINDOW": "UTC_DAY", "DIRECTION": "POSITIVE",
        "STATE": "as G01-A1", "COMPARATOR": "as G01-A1",
        "MECHANISM": "If turn-of-month flows are lumpy and directional, the daily range is wider on those days than mid-month.",
        "REPLICATION": True,
        "REPLICATION_NOTE": "BitMEX XBTUSD 5m highs and lows, 2017-01..2019-12, same rule.",
    },
    {
        "ID": "G01-A3", "CARD": "G01-A", "NAME": "MONTH_END_MARK_HOUR", "DESIGN": "PAIRED_UNIT",
        "UNIT": "CALENDAR_MONTH", "TARGET": "LOG_RANGE", "WINDOW": "UTC_HOUR_23", "DIRECTION": "POSITIVE",
        "STATE": "23:00-24:00 UTC on the last day of the month (outside the fixed holiday windows)",
        "COMPARATOR": "23:00-24:00 UTC on days 8-21 of the same month",
        "MECHANISM": "Funds and treasuries mark month-end NAV at 00:00 UTC; marking and rebalancing trades concentrate in the last UTC hour of the month.",
        "REPLICATION": True,
        "REPLICATION_NOTE": "BitMEX XBTUSD 5m, same rule.",
    },
    {
        "ID": "G01-B1", "CARD": "G01-B", "NAME": "ETF_FIXING_HOUR_PARTICIPATION", "DESIGN": "TWO_ERA_DID",
        "UNIT": "ISO_WEEK", "TARGET": "LOG_QUOTE_VOLUME", "WINDOW": "NY_HOURS_13_14_15", "DIRECTION": "POSITIVE",
        "STATE": "post-launch NYSE full trading days (2024-01-15..2024-12-31): z(15:00-16:00 NY) minus the mean z of 13:00-14:00 and 14:00-15:00 NY",
        "COMPARATOR": "the same quantity on pre-launch NYSE full trading days (2020-01-01..2024-01-07)",
        "MECHANISM": "US spot bitcoin ETFs strike NAV on reference rates computed over 15:00-16:00 New York; authorized-participant and market-maker execution and the related CME basis activity concentrate there on NYSE trading days.",
        "REPLICATION": True,
        "REPLICATION_NOTE": "No historical ETF era exists. Prospective Binance perp from 2027-01-01 against the frozen pre-launch mean, with a fixed stopping rule.",
    },
]
HYPOTHESIS_BY_ID = {h["ID"]: h for h in HYPOTHESES}

PROSPECTIVE_B = {
    "KIND": "PROSPECTIVE",
    "ID": "BINANCE_PERP_PROSPECTIVE_G01B",
    "START": "2027-01-01",
    "STARTS_AFTER_FREEZE": True,
    "STOPPING_RULE": {
        "MIN_MECHANISM_ACTIVE_N": 52,
        "MIN_MECHANISM_INACTIVE_N": 200,
        "MIN_N": 52,  # prospective weeks only; corrected before freeze from 252, which double-counted the frozen pre arm
        "MAX_EPISODES": 104,
        "END_DATE": "2029-12-31",
        "COUNTS_ONLY_MONITORING": True,
        "PRODUCT_EXPOSURE_HANDLING": (
            "The beta product shows no fixing-hour participation statistic. If one is added before the "
            "stop, the prospective leg is void and needs a new preregistration. The inactive arm is the "
            "frozen pre-launch weeks; the active arm is new weeks only."
        ),
    },
}

ALLOWED_INTERPRETATION = (
    "A non-directional description of participation or range in a calendar-defined window relative to a "
    "named ordinary-conditions comparator; the nuisance diagnostic decides whether it is more than the "
    "general volatility regime."
)
FORBIDDEN_INTERPRETATION = (
    "No direction, no trade, no target, no probability of direction, no causal claim about ETFs, funds, "
    "payrolls or any participant group, no generalization beyond the venue and years tested."
)


def assert_locked() -> None:
    if MIN_MEANINGFUL_EFFECT != 0.5 or FAMILY_ALPHA != 0.05 or len(HYPOTHESES) != 4:
        raise RuntimeError("AUTOGEN_G01 design constants drifted")
    if {h["CARD"] for h in HYPOTHESES} != set(CARDS) or len({h["ID"] for h in HYPOTHESES}) != 4:
        raise RuntimeError("AUTOGEN_G01 hypothesis table drifted")
