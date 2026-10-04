"""Frozen design constants for DH2 (pooled directional hypotheses on six coins).

Fixed before any DH2 data byte was read. Inference constants not restated here are DH1's
(`scripts/research/dh1/constants.py`), imported unchanged.
"""

from __future__ import annotations

from scripts.research.dh1 import constants as K1

PROGRAM_ID = "DIRECTIONAL_HYPOTHESES_DH2"
SEARCH_FAMILY_ID = "SF-DH2"
DESIGN_RECORD = "docs/research/DH2_POOLED_DESIGN.md"
DESIGN_DATE = "2026-10-04"

_ms = K1._ms
SYMBOLS = ("BTC", "ETH", "BNB", "XRP", "DOGE", "SOL")
PAIR = {s: f"{s}USDT" for s in SYMBOLS}

# discovery: (data start = first full UM month, event start = one month later); BTC uses CORE_BTC
DISCOVERY = {
    "BTC": ("2020-01-01", "2020-02-01"), "ETH": ("2020-01-01", "2020-02-01"), "XRP": ("2020-02-01", "2020-03-01"),
    "BNB": ("2020-03-01", "2020-04-01"), "DOGE": ("2020-08-01", "2020-09-01"), "SOL": ("2020-10-01", "2020-11-01"),
}
DISCOVERY_END = "2025-01-01"
DISCOVERY_EPOCHS = [("2020", "2020-01-01", "2021-01-01"), ("2021", "2021-01-01", "2022-01-01"),
                    ("2022", "2022-01-01", "2023-01-01"), ("2023", "2023-01-01", "2024-01-01"),
                    ("2024", "2024-01-01", "2025-01-01")]
UM_FIRST_MONTH = {"ETH": "2020-01", "XRP": "2020-02", "BNB": "2020-03", "DOGE": "2020-08", "SOL": "2020-10"}  # first full month
SPOT_DISCOVERY_FIRST_MONTH = "2020-01"
LAST_MONTH = "2024-12"

# replication: spot-only price surface for DH2-L3; the DH1 BTC surface for DH2-L1 and DH2-B2
REPLICATION_SPOT = {"BTC": ("2017-08-01", "2017-09-01"), "ETH": ("2017-08-01", "2017-09-01"),
                    "BNB": ("2017-12-01", "2018-01-01"), "XRP": ("2018-06-01", "2018-07-01")}
SPOT_EARLY_FIRST_MONTH = {"ETH": "2017-08", "BNB": "2017-12", "XRP": "2018-06"}  # first full month after listing
SPOT_EARLY_LAST_MONTH = "2019-12"
REPLICATION_END = "2020-01-01"
REPLICATION_EPOCHS = [("2017H2", "2017-09-01", "2018-01-01"), ("2018", "2018-01-01", "2019-01-01"),
                      ("2019", "2019-01-01", "2020-01-01")]

LEVEL_TYPES = ("PMH", "PML", "PWH", "PWL", "PDH", "PDL", "POC_UP", "POC_DOWN")   # no round numbers
TYPE_GROUP = {"PMH": "MONTH", "PML": "MONTH", "PWH": "WEEK", "PWL": "WEEK", "PDH": "DAY", "PDL": "DAY",
              "POC_UP": "POC", "POC_DOWN": "POC"}

CARDS = {
    "DH2-L": {"TITLE": "First touch of a key level on six coins", "TEST_FAMILY_ID": "TF-DH2-L-LEVEL-HOLD",
              "ENDPOINT": "LEVEL_HOLD_4H", "NUISANCE_EXTRA": ("TYPE_GROUP",)},
    "DH2-B": {"TITLE": "Sharp 15-minute move on six coins", "TEST_FAMILY_ID": "TF-DH2-B-BARRIER",
              "ENDPOINT": "BARRIER_FIRST_PASSAGE_4H", "NUISANCE_EXTRA": ("MOVE_TERCILE",)},
}
HYPOTHESES = [
    {"ID": "DH2-L1", "CARD": "DH2-L", "STATE": "SPOT_CONFIRMED_APPROACH", "SOURCE": "DH1-L1",
     "NUISANCE_EXTRA": ("PERP_IMB_TERCILE",), "REPLICATION": "BTC_BITMEX", "ATLAS_CELL": "SPOT_PERP.spot_confirmation x SPOT"},
    {"ID": "DH2-L3", "CARD": "DH2-L", "STATE": "STALE_LEVEL", "SOURCE": "DH1-L3",
     "NUISANCE_EXTRA": (), "REPLICATION": "SPOT_4_COINS", "ATLAS_CELL": "PRICE_STRUCTURE.levels x CANDLES"},
    {"ID": "DH2-B2", "CARD": "DH2-B", "STATE": "SPOT_SHARE_HIGH_MOVE", "SOURCE": "DH1-B2",
     "NUISANCE_EXTRA": ("PERP_IMB_TERCILE",), "REPLICATION": "BTC_BITMEX", "ATLAS_CELL": "SPOT_PERP.volume_share x SPOT"},
]
HYPOTHESIS_BY_ID = {h["ID"]: h for h in HYPOTHESES}
NUISANCE_COMMON = ("HOUR_BLOCK", "RV_TERCILE", "LAG_TERCILE", "SYMBOL")
WITHIN_SYMBOL_TERCILES = ("RV", "LAG", "PERP_IMB", "RATIO")

SYMBOL_HET_MIN_SYMBOLS = 3
SYMBOL_HET_SEED = 20261006
BOOT_SEED = 20261007


def assert_locked() -> None:
    if K1.PRACTICAL_BAR != 0.03 or len(HYPOTHESES) != 3 or len(SYMBOLS) != 6:
        raise RuntimeError("DH2 design constants drifted")
