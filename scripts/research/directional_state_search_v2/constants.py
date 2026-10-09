"""DIRECTIONAL_STATE_SEARCH_V2 frozen constants (bounded discovery cycle; see the design note)."""
from __future__ import annotations

PROGRAM = "DIRECTIONAL_STATE_SEARCH_V2"
MODE = "DISCOVERY"
EXPOSURE_CLASS = "ADAPTIVE_HISTORICAL_DISCOVERY"
CLAIM_CEILING = "DISCOVERY_ONLY"
PRODUCT_INTEGRATION_CANDIDATE = False

CORE_DATASET_ID = "CORE_BTC_BINANCE_V0"
CORE_ZIP_LIST_SHA256 = "936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b"
SURFACE_START_MS = 1_577_836_800_000   # 2020-01-01T00:00Z
SURFACE_END_MS = 1_735_689_600_000     # 2025-01-01T00:00Z (exclusive)
MINUTE_MS = 60_000
BAR_MS = 300_000

# ---- method (fixed by design)
LOOKBACK_4H = 48
LOOKBACK_24H = 288
HORIZON_1H = 12
PHASE_ORIGIN_MS = 1_577_836_800_000    # anchor bar: ((open - origin)/5m) mod 3 == 2 -> T at :00/:15/:30/:45
BOOT_DRAWS = 2000
BOOT_SEED = 20261120
BOOT_LO = 0.025
BOOT_HI = 0.975

# ---- search-exposure bar (RESEARCH_RULES_DECISION_V1 §4; EXPOSURE_COUNTERS_V1 §3): family-wise alpha 0.10 Bonferroni
# over m_ST (CORE x DIRECTION, lower bound before this cycle) plus this cycle's own read cells. Not a ranking rule.
M_ST_CORE_DIRECTION_BEFORE = 813
PROMOTION_FAMILYWISE_ALPHA = 0.10

# ---- frozen candidate inventory (design note §3). Controls are added to the baseline B0 = (RP4H, RET_4H, RV_4H).
# (id, family, state, source, extra controls)
CANDIDATES = (
    ("F1a", "SIGNED_PATH_ASYMMETRY", "SPA_24H", "core", ("RET_24H", "RV_24H")),
    ("F1b", "SIGNED_PATH_ASYMMETRY", "UPFRAC_24H", "core", ("RET_24H", "RV_24H")),
    ("F2a", "PATH_OCCUPANCY_RESIDUAL", "OCC_MEAN_4H", "core", ()),
    ("F3a", "REJECTION_DECAY", "REJ_DECAY_24H", "core", ("RP_24H",)),
    ("F4a", "COUNTERMOVE_DECAY", "CMD_UP_24H", "core", ("RET_24H",)),
    ("F6a", "US_OPEN_DRIVE", "US_OPEN_DRIVE", "session", ()),
    ("F6b", "SESSION_HANDOFF", "SESSION_HANDOFF", "session", ()),
    ("F7a", "EFFORT_TO_RESULT", "FLOW_RESPONSE_CHANGE_4H", "core", ("IMB_4H",)),
    ("F7b", "EFFORT_TO_RESULT", "SIDE_ASYM_CHANGE_4H", "core", ("IMB_4H",)),
)
# declared robustness variant of an object (same object, another formula; not a new hypothesis)
VARIANTS = (("F2a-v", "F2a", "OCC_THIRDS_4H", ()),)
# declared sensitivity (extra control); never a route, never a replacement
SENSITIVITIES = (("F7a-s", "F7a", "FLOW_RESPONSE_CHANGE_4H", ("IMB_4H", "LOG_LAMBDA_4H")),)
BLOCKED_FAMILIES = {
    "FAILED_PROGRESS": "inside the owner-closed divergence / selling-exhaustion line (catalog §6 price-only momentum divergence; E2 price leg)",
    "OI_RESPONSE": "inside the owner-closed DH3 line (catalog E3/E4) or exact-consumed MARKET-01; OI-only read needs its own owner permit",
}
# parity: the recorded discovery cell close_pos_4h -> R_1H on CORE (Cursor PRE_IMPULSE_STATE_ATLAS_V1), anchors i >= 96
PARITY_RP4H_SPEARMAN = -0.057773446228651215
PARITY_N = 175_356
PARITY_TOL = 1e-9

# ---- pre-assigned before any outcome (design §6): qualitative grades (A best) and question-fresh replication surfaces
GRADES = {
    "F1a": {"simplicity": "A", "novelty": "A", "distance_from_consumed": "A"},
    "F1b": {"simplicity": "A", "novelty": "B", "distance_from_consumed": "A"},
    "F2a": {"simplicity": "A", "novelty": "B", "distance_from_consumed": "B"},
    "F3a": {"simplicity": "C", "novelty": "B", "distance_from_consumed": "B"},
    "F4a": {"simplicity": "B", "novelty": "B", "distance_from_consumed": "B"},
    "F6a": {"simplicity": "A", "novelty": "A", "distance_from_consumed": "A"},
    "F6b": {"simplicity": "A", "novelty": "A", "distance_from_consumed": "B"},
    "F7a": {"simplicity": "B", "novelty": "A", "distance_from_consumed": "B"},
    "F7b": {"simplicity": "B", "novelty": "B", "distance_from_consumed": "C"},
}
_PRICE_SURFACES = ("BitMEX XBTUSD 5m 2016-05..2019-12 (D2 canonical)", "Binance spot BTCUSDT 5m 2017-08..2019-12",
                   "Binance USD-M BTCUSDT 5m 2025-01..2026-10 minus the E1 window (needs its own per-question exposure audit)")
_FLOW_SURFACES = ("Binance spot BTCUSDT 5m klines with taker-buy quote 2017-08..2019-12",
                  "BitMEX XBTUSD trades 2017-08..2019-12 (taker side; DH1_BITMEX_XBTUSD_TRADES_5M_V0 provenance to check)",
                  "Binance USD-M BTCUSDT 5m klines 2025-01..2026-10 minus the E1 window (per-question exposure audit)")
_SESSION_SURFACES = ("Binance USD-M BTCUSDT 2025-01..2026-10 minus the E1 window (needs a 2025-26 NYSE calendar pin incl. 2025-01-09)",
                     "BitMEX XBTUSD 5m 2016-05..2019-12 (needs 2016-19 NYSE calendar pins)")
REPLICATION = {"F1a": _PRICE_SURFACES, "F1b": _PRICE_SURFACES, "F2a": _PRICE_SURFACES, "F3a": _PRICE_SURFACES,
               "F4a": _PRICE_SURFACES, "F6a": _SESSION_SURFACES, "F6b": _SESSION_SURFACES,
               "F7a": _FLOW_SURFACES, "F7b": _FLOW_SURFACES}

# ---- freeze pins (set in the freeze commit; the run refuses on any mismatch)
DESIGN_SHA256 = "a361ff35fdb30cd051d7c6f6de1d4b9c70a5329f3250933963396a3d31b52c52"
DESIGN_COMMIT = "PENDING"
LEDGER_PRE_SHA256 = "5ae1a8048666f339da62b9a07703a5858a0ca76bef367d6481f6dc55de2698e6"
