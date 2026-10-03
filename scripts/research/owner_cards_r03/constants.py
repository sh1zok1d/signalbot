"""Frozen design constants for the owner cards R03 program.

Everything here is fixed before any count and before any outcome. The
hypothesis table is the single source for the planning objects, the
preregistration twin and the one-shot evaluator. No market value is read here.
"""

from __future__ import annotations

PROGRAM_ID = "OWNER_CARDS_R03"
SEARCH_FAMILY_ID = "SF-OWNER-CARDS-R03"
CONTRACT_VERSION = "GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V1"
EVALUATION_CONTRACT = "HYPOTHESIS_EVALUATION_CONTRACT_V1"
DESIGN_DATE = "2026-10-03"

# Surfaces
DISCOVERY_SURFACE = {"ID": "BINANCE_2020_2024", "START": "2020-01-01", "END": "2025-01-01"}
HISTORICAL_WINDOW = "2020-01..2024-12"
DISCOVERY_START_MS = 1577836800000  # 2020-01-01T00:00Z
DISCOVERY_END_MS = 1735689600000  # 2025-01-01T00:00Z (exclusive)
REPLICATION_BITMEX = {"ID": "BITMEX_2016_2019", "START": "2017-01-01", "END": "2020-01-01"}
BITMEX_START_MS = 1483228800000  # 2017-01-01T00:00Z
BITMEX_END_MS = DISCOVERY_START_MS
PROSPECTIVE_PANEL = {
    "KIND": "PROSPECTIVE",
    "ID": "BINANCE_SPOT_PANEL_PROSPECTIVE_R03B",
    "START": "2027-01-01",
    "STARTS_AFTER_FREEZE": True,
    "STOPPING_RULE": {
        "MIN_MECHANISM_ACTIVE_N": 60,
        "MIN_MECHANISM_INACTIVE_N": 240,
        "MIN_N": 365,
        "MAX_EPISODES": 730,
        "END_DATE": "2028-12-31",
        "COUNTS_ONLY_MONITORING": True,
        "PRODUCT_EXPOSURE_HANDLING": (
            "The beta product shows no panel breadth, dispersion, volume-shock or BTC-share "
            "statistic. No product exposure of these states exists; if one is added before the "
            "stop, the prospective leg is void and needs a new preregistration."
        ),
    },
}

# Datasets (feature registry ids = docs/research_data/<ID>/MANIFEST.json)
DATASET_BTC = "CORE_BTC_BINANCE_V0"
DATASET_BITMEX = "D2_BITMEX_PRE2020_XBTUSD"
DATASET_PANEL = "SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0"
DATASET_NYSE = "NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0"

# Effect bar and inference
MIN_MEANINGFUL_EFFECT = 0.5  # comparator-SD units of standardized log range
EFFECT_UNITS = "SD_OF_STANDARDIZED_LOG_RANGE"
PRACTICAL_BAR_RATIONALE = (
    "The beta briefing flags an hour whose range sits in the extreme of its same-hour "
    "baseline. A scheduled state that shifts the range distribution by half a comparator "
    "SD roughly doubles that flag rate; a smaller shift is not worth a user-facing sentence. "
    "The bar was set before any count or outcome and is the same for all twelve hypotheses."
)
FAMILY_ALPHA = 0.05
MULTIPLICITY = "HOLM_WITHIN_CARD_OVER_EXECUTED_HYPOTHESES"
SIGNFLIP_DRAWS = 20000
SIGNFLIP_SEED = 20261003
HET_DRAWS = 2000
HET_SEED = 20261004
HET_BLOCK_UNITS = 4
ALPHA_HET = 0.05
NUISANCE_RETENTION_FOR_STATE_SPECIFIC_WORDING = 0.5
PRODUCT_FREQUENCY_MIN_PER_YEAR = 12

# Windows and warm-ups
MINUTE_MS = 60_000
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
PANEL_TRAILING_DAYS = 180
PANEL_STATE_QUANTILE = 0.80
PANEL_UNIVERSE_TOP_N = 100
PANEL_UNIVERSE_HISTORY_DAYS = 30
PANEL_MIN_SYMBOLS = 20
VOLUME_SHOCK_MULTIPLE = 2.0
PRIOR_RV_MINUTES = 1440

WINDOW_DEFS = {
    # id: (anchor, local_start, length_minutes)
    "UTC_0800_60": ("UTC", "08:00", 60),
    "UTC_0400_240": ("UTC", "04:00", 240),
    "LONDON_1600_60": ("Europe/London", "16:00", 60),
    "NY_0930_60": ("America/New_York", "09:30", 60),
    "NY_1500_60": ("America/New_York", "15:00", 60),
    "UTC_DAY_1440": ("UTC", "00:00", 1440),
    "UTC_HOUR_60": ("UTC", "HOURLY", 60),
}

CARDS = {
    "R03-A": {
        "TITLE": "Scheduled derivatives-expiry clock",
        "FAMILY": "G",
        "FAMILY_NAME": "EVENT_RESPONSE / scheduled derivative settlement (not FOMC, CPI or NFP)",
        "TEST_FAMILY_ID": "TF-R03-A-EXPIRY-CLOCK",
        "DATASETS": [DATASET_BTC, DATASET_BITMEX],
        "REPLICATION": "BITMEX_HISTORICAL",
    },
    "R03-B": {
        "TITLE": "Cross-sectional panel breadth and dispersion states",
        "FAMILY": "H",
        "FAMILY_NAME": "CROSS_SECTIONAL / true panel (not D9 share, not D13 relative momentum)",
        "TEST_FAMILY_ID": "TF-R03-B-PANEL-STATES",
        "DATASETS": [DATASET_BTC, DATASET_PANEL],
        "REPLICATION": "PROSPECTIVE_PANEL",
    },
    "R03-C": {
        "TITLE": "Session and participant-clock structure",
        "FAMILY": "J",
        "FAMILY_NAME": "PARTICIPANT_CLOCK_ANCHORING / session structure (not the D12 DST profile shift)",
        "TEST_FAMILY_ID": "TF-R03-C-SESSION-CLOCK",
        "DATASETS": [DATASET_BTC, DATASET_NYSE, DATASET_BITMEX],
        "REPLICATION": "BITMEX_HISTORICAL",
    },
}

# Hypothesis table. UNIT is the inference unit; the sign-flip null acts on it.
HYPOTHESES = [
    {
        "ID": "R03-A1", "CARD": "R03-A", "NAME": "WEEKLY_EXPIRY_HOUR",
        "WINDOW": "UTC_0800_60", "UNIT": "ISO_WEEK", "DIRECTION": "POSITIVE",
        "STATE": "Friday 08:00-09:00 UTC, the Deribit weekly, monthly and quarterly expiry hour",
        "COMPARATOR": "08:00-09:00 UTC on Monday-Thursday of the same ISO week",
        "MECHANISM": (
            "Deribit settles every listed option and future at 08:00 UTC on Fridays. Dealers "
            "and basis traders unwind hedges and roll positions into and out of that hour, so "
            "the hour carries more price discovery than the same hour on other weekdays."
        ),
        "REPLICATION": True,
        "REPLICATION_NOTE": "Deribit expiries ran at 08:00 UTC through 2017-2019; BitMEX XBTUSD 5m bars.",
    },
    {
        "ID": "R03-A2", "CARD": "R03-A", "NAME": "LARGE_EXPIRY_INCREMENT",
        "WINDOW": "UTC_0800_60", "UNIT": "CALENDAR_MONTH", "DIRECTION": "POSITIVE",
        "STATE": "08:00-09:00 UTC on the last Friday of the calendar month (monthly and quarterly expiry)",
        "COMPARATOR": "08:00-09:00 UTC on the other Fridays of the same calendar month",
        "MECHANISM": (
            "Monthly and quarterly expiries carry much larger open interest than weeklies. If "
            "the expiry-hour effect scales with settled notional, the last-Friday hour should "
            "exceed the ordinary weekly expiry hour."
        ),
        "REPLICATION": True,
        "REPLICATION_NOTE": "Same calendar rule on BitMEX 2017-2019.",
    },
    {
        "ID": "R03-A3", "CARD": "R03-A", "NAME": "CME_EXPIRY_HOUR",
        "WINDOW": "LONDON_1600_60", "UNIT": "CALENDAR_MONTH", "DIRECTION": "POSITIVE",
        "STATE": "The hour starting 16:00 London time on the last Friday of the month (CME Bitcoin futures final settlement on the BRR)",
        "COMPARATOR": "The hour starting 16:00 London time on the other Fridays of the same month",
        "MECHANISM": (
            "CME Bitcoin futures settle to the CME CF Bitcoin Reference Rate computed over "
            "15:00-16:00 London on the last Friday. Basis and cash-and-carry positions close "
            "around that fixing, and the hour after it absorbs the unwinds."
        ),
        "REPLICATION": True,
        "REPLICATION_NOTE": "CME BTC futures listed 2017-12-18; replication covers 2018-01..2019-12 only.",
    },
    {
        "ID": "R03-A4", "CARD": "R03-A", "NAME": "PRE_EXPIRY_PINNING",
        "WINDOW": "UTC_0400_240", "UNIT": "ISO_WEEK", "DIRECTION": "NEGATIVE",
        "STATE": "Friday 04:00-08:00 UTC, the four hours before the Deribit expiry",
        "COMPARATOR": "04:00-08:00 UTC on Monday-Thursday of the same ISO week",
        "MECHANISM": (
            "Into a large options expiry, dealer gamma hedging near popular strikes pins the "
            "spot price, so the pre-expiry window should show a narrower range than the same "
            "window on other weekdays."
        ),
        "REPLICATION": True,
        "REPLICATION_NOTE": "Same rule on BitMEX 2017-2019.",
    },
    {
        "ID": "R03-B1", "CARD": "R03-B", "NAME": "RETURN_DISPERSION_HIGH",
        "WINDOW": "UTC_DAY_1440", "UNIT": "CALENDAR_MONTH", "DIRECTION": "POSITIVE",
        "STATE": "UTC day whose cross-sectional SD of daily log returns across the eligible panel is at or above its trailing-180-day 0.80 quantile",
        "COMPARATOR": "Other eligible UTC days of the same calendar month",
        "MECHANISM": (
            "High dispersion means idiosyncratic repricing dominates the common factor. That "
            "ends when the common factor moves; the next BTC day should carry a wider range."
        ),
        "REPLICATION": False,
    },
    {
        "ID": "R03-B2", "CARD": "R03-B", "NAME": "BREADTH_SYNCHRONY",
        "WINDOW": "UTC_DAY_1440", "UNIT": "CALENDAR_MONTH", "DIRECTION": "POSITIVE",
        "STATE": "UTC day whose |fraction of eligible symbols with a positive daily return - 0.5| is at or above its trailing-180-day 0.80 quantile",
        "COMPARATOR": "Other eligible UTC days of the same calendar month",
        "MECHANISM": (
            "When nearly every symbol moves the same way, the move is a common-factor shock. "
            "Common shocks cluster, so the next BTC day should carry a wider range."
        ),
        "REPLICATION": False,
    },
    {
        "ID": "R03-B3", "CARD": "R03-B", "NAME": "VOLUME_SHOCK_FRACTION",
        "WINDOW": "UTC_DAY_1440", "UNIT": "CALENDAR_MONTH", "DIRECTION": "POSITIVE",
        "STATE": "UTC day whose fraction of eligible symbols with quote volume at or above 2x their own trailing-30-day median is at or above its trailing-180-day 0.80 quantile",
        "COMPARATOR": "Other eligible UTC days of the same calendar month",
        "MECHANISM": (
            "A broad volume shock across the panel signals a change in participation that "
            "is not specific to one coin; it should carry into the next BTC day."
        ),
        "REPLICATION": False,
    },
    {
        "ID": "R03-B4", "CARD": "R03-B", "NAME": "BTC_SHARE_LOW",
        "WINDOW": "UTC_DAY_1440", "UNIT": "CALENDAR_MONTH", "DIRECTION": "TWO_SIDED",
        "STATE": "UTC day whose BTC share of eligible-panel quote volume (BTC included) is at or below its trailing-180-day 0.20 quantile",
        "COMPARATOR": "Other eligible UTC days of the same calendar month",
        "MECHANISM": (
            "Days when activity concentrates in altcoins describe a different participant "
            "mix. Whether BTC's next-day range is wider or narrower on such days is not "
            "known, so the claim is two-sided."
        ),
        "REPLICATION": False,
    },
    {
        "ID": "R03-C1", "CARD": "R03-C", "NAME": "WEEKEND_HOURS",
        "WINDOW": "UTC_HOUR_60", "UNIT": "ISO_WEEK", "DIRECTION": "NEGATIVE",
        "STATE": "Every UTC hour of Saturday and Sunday",
        "COMPARATOR": "The same UTC hour of Tuesday, Wednesday and Thursday of the same ISO week",
        "MECHANISM": (
            "Traditional-finance participants and their funding rails are closed at the "
            "weekend, so the hourly range should be narrower hour for hour."
        ),
        "REPLICATION": True,
        "REPLICATION_NOTE": "Same rule on BitMEX 2017-2019.",
    },
    {
        "ID": "R03-C2", "CARD": "R03-C", "NAME": "MONDAY_US_OPEN",
        "WINDOW": "NY_0930_60", "UNIT": "ISO_WEEK", "DIRECTION": "POSITIVE",
        "STATE": "Monday 09:30-10:30 America/New_York, excluding Mondays that are NYSE full-day closures",
        "COMPARATOR": "09:30-10:30 America/New_York on Tuesday-Thursday of the same ISO week",
        "MECHANISM": (
            "Information that accumulates over the weekend is priced by US-session "
            "participants when they return; the first US-open hour of the week should carry "
            "a wider range than the same hour later in the week."
        ),
        "REPLICATION": True,
        "REPLICATION_NOTE": "BitMEX 2017-2019; NYSE closures are not pinned for those years, so Monday closures are not excluded there.",
    },
    {
        "ID": "R03-C3", "CARD": "R03-C", "NAME": "NYSE_CLOSURE_US_OPEN",
        "WINDOW": "NY_0930_60", "UNIT": "CLOSURE_DAY", "DIRECTION": "NEGATIVE",
        "STATE": "09:30-10:30 America/New_York on a weekday that is a NYSE full-day closure",
        "COMPARATOR": "09:30-10:30 America/New_York on the other non-closure weekdays of the same ISO week",
        "MECHANISM": (
            "On a US holiday the US equity session does not open, so the hour that usually "
            "carries the US open should show a narrower range."
        ),
        "REPLICATION": False,
        "REPLICATION_NOTE": "No pinned NYSE calendar for 2017-2019; replication NOT_AVAILABLE.",
    },
    {
        "ID": "R03-C4", "CARD": "R03-C", "NAME": "FRIDAY_US_CLOSE",
        "WINDOW": "NY_1500_60", "UNIT": "ISO_WEEK", "DIRECTION": "POSITIVE",
        "STATE": "Friday 15:00-16:00 America/New_York, excluding Fridays that are NYSE closures or early-close days",
        "COMPARATOR": "15:00-16:00 America/New_York on Tuesday-Thursday of the same ISO week",
        "MECHANISM": (
            "Before the weekend, participants who cannot manage risk over two closed days "
            "square positions in the last regular US hour of the week."
        ),
        "REPLICATION": True,
        "REPLICATION_NOTE": "BitMEX 2017-2019; NYSE early closes are not pinned there, so no exclusion is applied.",
    },
]

HYPOTHESIS_BY_ID = {h["ID"]: h for h in HYPOTHESES}

ALLOWED_INTERPRETATION = (
    "A non-directional description of the range of a scheduled or calendar-defined hour or "
    "day relative to a named ordinary-conditions comparator, with the nuisance diagnostic "
    "deciding whether the state is more than the general volatility regime."
)
FORBIDDEN_INTERPRETATION = (
    "No direction, no trade, no target, no probability of direction, no causal claim about "
    "dealers, hedgers or any participant group, no generalization beyond the venue and years tested."
)


def assert_locked() -> None:
    if MIN_MEANINGFUL_EFFECT != 0.5 or FAMILY_ALPHA != 0.05 or len(HYPOTHESES) != 12:
        raise RuntimeError("R03 design constants drifted")
    ids = [h["ID"] for h in HYPOTHESES]
    if len(set(ids)) != 12 or any(h["CARD"] not in CARDS for h in HYPOTHESES):
        raise RuntimeError("R03 hypothesis table drifted")
    if any(h["WINDOW"] not in WINDOW_DEFS for h in HYPOTHESES):
        raise RuntimeError("R03 window table drifted")
