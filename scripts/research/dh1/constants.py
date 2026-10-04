"""Frozen design constants for DH1 (directional hypotheses for the bot).

Fixed before any data byte was read and before any outcome. This table is the single source
for the candidate record, the feasibility pass, the preregistration and the one-shot evaluator.
"""

from __future__ import annotations

PROGRAM_ID = "DIRECTIONAL_HYPOTHESES_DH1"
SEARCH_FAMILY_ID = "SF-DH1"
DECISION_RECORD = "docs/research/DIRECTIONAL_HYPOTHESES_DECISION_V1.md"
EVALUATION_CONTRACT = "HYPOTHESIS_EVALUATION_CONTRACT_V1"
DESIGN_DATE = "2026-10-04"

MINUTE_MS = 60_000
BAR_MS = 300_000
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
WEEK_MS = 7 * DAY_MS


def _ms(iso: str) -> int:
    import datetime as dt
    return int(dt.datetime.fromisoformat(iso + "T00:00:00+00:00").timestamp() * 1000)


# ---- surfaces ---------------------------------------------------------------------------------
# DATA_START: first bar read (warm-up for month levels and the 24h scale). EVENT_START: first
# decision time that may form an event. END: exclusive; every outcome window ends before it.
SURFACES = {
    "DISCOVERY": {
        "ID": "BINANCE_2020_2024",
        "PERP": "CORE_BTC_BINANCE_V0 (Binance USD-M BTCUSDT 1m klines, aggregated to 5m)",
        "SPOT": "DH1_BINANCE_SPOT_BTCUSDT_5M_V0 (Binance spot BTCUSDT 5m klines)",
        "DATA_START": "2020-01-01", "EVENT_START": "2020-02-01", "END": "2025-01-01",
        "EPOCHS": [("2020", "2020-02-01", "2021-01-01"), ("2021", "2021-01-01", "2022-01-01"),
                   ("2022", "2022-01-01", "2023-01-01"), ("2023", "2023-01-01", "2024-01-01"),
                   ("2024", "2024-01-01", "2025-01-01")],
    },
    "REPLICATION": {
        "ID": "BITMEX_BINANCE_SPOT_2017_2019",
        "PERP": "DH1_BITMEX_XBTUSD_TRADES_5M_V0 (BitMEX XBTUSD public trades, aggregated to 5m)",
        "SPOT": "DH1_BINANCE_SPOT_BTCUSDT_5M_V0 (Binance spot BTCUSDT 5m klines)",
        "DATA_START": "2017-08-01", "EVENT_START": "2017-09-01", "END": "2020-01-01",
        "EPOCHS": [("2017H2", "2017-09-01", "2018-01-01"), ("2018", "2018-01-01", "2019-01-01"),
                   ("2019", "2019-01-01", "2020-01-01")],
    },
}
SPOT_FIRST_MONTH = "2017-08"     # Binance spot BTCUSDT 5m archive starts 2017-08-17
SPOT_LAST_MONTH = "2024-12"
BITMEX_FIRST_DAY = "2017-08-01"
BITMEX_LAST_DAY = "2019-12-31"
PROTECTED_FROM = "2025-01-01"    # no object at or after this date is requested by DH1

# ---- grid and windows (5m bars) -------------------------------------------------------------
HOLD_BARS = 48          # 4h outcome horizon
APPROACH_BARS = 12      # 1h approach window into a level, touch bar included
MOVE_BARS = 3           # 15-minute sharp move
SCALE_BARS = 288        # 24h of 5m returns for the volatility scale
LAG_BARS = 48           # prior 4h aligned return (lagged target)
STALE_BARS = 288        # a level not traded during the 24h before its touch is stale
MIN_PRESENT = 0.9       # share of bars that must be present in a window

# ---- level events (card L) ------------------------------------------------------------------
# Level types and first-touch rules are the product's (beta/levels.py, bound by digest at freeze).
LEVEL_TYPES = ("PMH", "PML", "PWH", "PWL", "PDH", "PDL", "POC_UP", "POC_DOWN", "ROUND_UP", "ROUND_DOWN")
TYPE_PRIORITY = {t: k for k, t in enumerate(LEVEL_TYPES)}   # same bar and side: keep the first
TYPE_GROUP = {"PMH": "MONTH", "PML": "MONTH", "PWH": "WEEK", "PWL": "WEEK", "PDH": "DAY", "PDL": "DAY",
              "POC_UP": "POC", "POC_DOWN": "POC", "ROUND_UP": "ROUND", "ROUND_DOWN": "ROUND"}
LIVE_KIND = {"PMH": "PMH", "PML": "PML", "PWH": "PWH", "PWL": "PWL", "PDH": "PDH", "PDL": "PDL",
             "POC_UP": "POC_PD", "POC_DOWN": "POC_PD", "ROUND_UP": "ROUND", "ROUND_DOWN": "ROUND"}
CONFLUENCE_TOL = 0.0015          # the product's zone tolerance (ZONE_TOL_PCT = 0.15 %)
CONFLUENCE_LOOKBACK_BARS = 62 * 288

# ---- sharp-move events (card B) -------------------------------------------------------------
MOVE_RATIO_MIN = 2.0             # |15m log move| >= 2 x the 1h scale known before the move began
MOVE_REFRACTORY_BARS = 12        # one event per hour at most
CORRIDOR_Z = 1.2816              # the product's 80 % corridor, as a normal half-width
BARRIER_FRACTION = 0.5           # X = half of the 4h corridor half-width ("половина коридора")

# ---- inference ------------------------------------------------------------------------------
PRACTICAL_BAR = 0.03             # owner: 3 pp against "обычно"
FAMILY_ALPHA = 0.05
BOOT_DRAWS = 2000
BOOT_SEED = 20261004
EPOCH_BOOT_DRAWS = 500
HET_PERM_DRAWS = 1000
HET_SEED = 20261005
HET_ALPHA = 0.05
OPPOSITE_ALPHA = 0.05
MIN_EPOCH_ARM = 30
PRED_CLIP = (0.01, 0.99)
DEFF_PLANNING = 1.25             # outcome-blind design effect allowance for week clustering
PLANNING_EFFECT = 0.06
EXECUTE_MDE_MAX = 0.06           # a cell runs only if it can detect twice the practical bar
EXECUTE_MIN_ARM = 300
HET_POWER_SIMS = 200
HET_POWER_PERMS = 300
HET_POWER_EFFECTS = (0.03, 0.06)  # half of the epochs at each: a 2x difference

NUISANCE_COMMON = ("HOUR_BLOCK", "RV_TERCILE", "LAG_TERCILE")

CARDS = {
    "DH1-L": {
        "TITLE": "First touch of a key level: what changes how often price holds beyond it",
        "TEST_FAMILY_ID": "TF-DH1-L-LEVEL-HOLD",
        "EVENT": "LEVEL_FIRST_TOUCH",
        "ENDPOINT": "LEVEL_HOLD_4H",
        "ENDPOINT_TEXT": "the close 4h after the touch bar is beyond the level, on the side of the approach",
        "NUISANCE_EXTRA": ("TYPE_GROUP",),
    },
    "DH1-B": {
        "TITLE": "Sharp 15-minute move: which edge is reached first in the next 4h",
        "TEST_FAMILY_ID": "TF-DH1-B-BARRIER",
        "EVENT": "SHARP_MOVE",
        "ENDPOINT": "BARRIER_FIRST_PASSAGE_4H",
        "ENDPOINT_TEXT": ("1 if price reaches close*(1 + d*X) before close*(1 - d*X) within 4h, 0 if the reverse, "
                          "0.5 if neither or both in the same bar; d = move direction, X = half of the 4h "
                          "corridor half-width"),
        "NUISANCE_EXTRA": ("MOVE_TERCILE",),
    },
}

HYPOTHESES = [
    {"ID": "DH1-L1", "CARD": "DH1-L", "STATE": "SPOT_CONFIRMED_APPROACH",
     "STATE_TEXT": "spot taker net flow over the hour into the touch (touch bar included) points in the approach direction",
     "COMPARATOR": "spot taker net flow zero or against the approach",
     "MECHANISM": "A push into a level carried by unlevered spot buying (or selling) is less likely to be unwound than one carried by perpetual flow alone.",
     "NUISANCE_EXTRA": ("PERP_IMB_TERCILE",), "ATLAS_CELL": "SPOT_PERP.spot_confirmation x SPOT"},
    {"ID": "DH1-L2", "CARD": "DH1-L", "STATE": "CONFLUENT_LEVEL",
     "STATE_TEXT": "another objective level of a different kind lies within 0.15 % of the touched level at the touch",
     "COMPARATOR": "no other level within 0.15 %",
     "MECHANISM": "A level that coincides with other watched levels concentrates resting orders and stops, so the reaction there differs from an isolated level.",
     "NUISANCE_EXTRA": (), "ATLAS_CELL": "PRICE_STRUCTURE.levels x CANDLES"},
    {"ID": "DH1-L3", "CARD": "DH1-L", "STATE": "STALE_LEVEL",
     "STATE_TEXT": "the level price was not traded during the 24h before the touch bar",
     "COMPARATOR": "the level price was traded during those 24h",
     "MECHANISM": "Orders and stops accumulate at a level the market has not visited for a while; a recently traded level carries less of them.",
     "NUISANCE_EXTRA": (), "ATLAS_CELL": "PRICE_STRUCTURE.levels x CANDLES"},
    {"ID": "DH1-B1", "CARD": "DH1-B", "STATE": "SPOT_CONFIRMED_MOVE",
     "STATE_TEXT": "spot taker net flow over the three 5m bars of the move points in the move direction",
     "COMPARATOR": "spot taker net flow zero or against the move",
     "MECHANISM": "A sharp move carried by spot flow reflects unlevered demand; a move carried by perpetual flow alone is more often leverage that unwinds.",
     "NUISANCE_EXTRA": ("PERP_IMB_TERCILE",), "ATLAS_CELL": "SPOT_PERP.spot_confirmation x SPOT"},
    {"ID": "DH1-B2", "CARD": "DH1-B", "STATE": "SPOT_SHARE_HIGH_MOVE",
     "STATE_TEXT": "spot share of spot+perp quote volume during the move exceeds its share over the 24h before the move",
     "COMPARATOR": "spot share at or below its 24h share",
     "MECHANISM": "Moves with unusually high spot participation are less leverage-driven, so they are less often reversed.",
     "NUISANCE_EXTRA": ("PERP_IMB_TERCILE",), "ATLAS_CELL": "SPOT_PERP.volume_share x SPOT"},
]
HYPOTHESIS_BY_ID = {h["ID"]: h for h in HYPOTHESES}

PROSPECTIVE = {
    "KIND": "PROSPECTIVE_LIVE_TRACKING",
    "SOURCE": "Binance Vision daily 5m klines (USD-M BTCUSDT and spot BTCUSDT), read after each day closes",
    "STARTS_AFTER_FREEZE": True,
    "START": "2026-10-05",
    "STOPPING_RULE": {"MIN_N": 300, "MAX_EVENTS": 1000, "END_DATE": "2027-12-31", "COUNTS_ONLY_MONITORING": True},
    "EXPOSURE_HANDLING": ("The bot may show the frozen discovery estimate («Гипотеза») during the window. The "
                          "prospective analysis uses only events after the freeze and the frozen discovery model; "
                          "showing a frozen number cannot change BTC outcomes, and no interim statistic is computed."),
}

ALLOWED_INTERPRETATION = ("A historical conditional probability on one venue: how often the stated event followed the "
                          "state, beside the same probability without the state after the nuisance adjustment, with N "
                          "and an interval and its status («Проверено» or «Гипотеза»).")
FORBIDDEN_INTERPRETATION = ("No trade call (buy/sell, long/short now, entry, target, take-profit), no edge claim, no "
                            "causal claim about participants, no wording stronger than the status.")


def assert_locked() -> None:
    if PRACTICAL_BAR != 0.03 or FAMILY_ALPHA != 0.05 or len(HYPOTHESES) != 5:
        raise RuntimeError("DH1 design constants drifted")
    for card in CARDS:
        cells = [h for h in HYPOTHESES if h["CARD"] == card]
        if not 1 <= len(cells) <= 3:
            raise RuntimeError("DH1: a card must hold 1..3 primary cells")
