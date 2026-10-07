"""Frozen design constants for LEVEL_LIQUIDITY_STATE_DISCOVERY_V1.

Chosen after the outcome-blind book schema audit and before any book feature
was joined to a resolution label. Do not change these after an outcome is read.
Parent level geometry is imported, not copied into a second definition.
"""

from __future__ import annotations

import datetime as dt

UNIT = "LEVEL_LIQUIDITY_STATE_DISCOVERY_V1"
FAMILY = "LEVEL_BEHAVIOR_V1"
MODE = "DISCOVERY"
TRACKS = ("STRUCTURE", "PRODUCT_EVIDENCE")
CLAIM_CEILING = "L2"
PRODUCT_INTEGRATION_CANDIDATE = False
EXPOSURE_STATUS = "DISCOVERY_ONLY"
STATE_TERM = "LOCAL_BOOK_STATE_AROUND_LEVEL_TOUCH"
SOURCE_MAIN_HEAD = "1a2e425303fb29e1044ca57452b8ad9b6f0a831b"

DEPENDENCY_TOUCH_SHA = "dfc9e0f04358de15606382472badeb5aee787039"
DEPENDENCY_MEMORY_SHA = "c3d39bffda861b535605a98205d7578c0c84c782"
DEPENDENCY_METHOD_SHA = "8effe9acc3b88b925a79b33f04ac0ee9e6f93e26"
DEPENDENCY_APPROACH_SHA = "aa85e5b43c405ee225336ff385e3a3383fa59d09"
DEPENDENCY_STRUCTURE_SHA = "f8623d3281424c165ebd7ee7fbcb0af994cc1e8d"
DEPENDENCY_CONFIRM_SHA = "c1cd4e0102e700f7860d21a9af0d243c3bc367be"
DEPENDENCY_POSITION_SHA = "e6e5f307cfa098db607544a556bae01a2310eb6a"
DEPENDENCY_JOINT_SHA = "bcc0a9e8a5c2af221b23b72768d7b7ba1d6a4aa2"

BOOK_DATASET_ID = "DH3_BINANCE_UM_BOOKDEPTH_V0"
BOOK_INVENTORY = "docs/research_data/DH3_BINANCE_UM_BOOKDEPTH_V0/SOURCE_INVENTORY.json"
BOOK_OBJECT_LIST_SHA256 = "c53fc179d922f83b572703d52e80f847fb54531961ac776929f2e3e95feeddce"
BOOK_SYMBOL = "BTC"
BOOK_PAIR = "BTCUSDT"
BOOK_FIRST_DAY = "2023-01-01"
BOOK_LAST_DAY = "2024-12-31"
# Native Binance percentage bands. The narrowest is ±1. No sub-1% band exists.
DEPTH_BAND_PCT = 1
NATIVE_BANDS = (-5, -4, -3, -2, -1, 1, 2, 3, 4, 5)
# Complete-day inter-arrival on 2023-01-01 and 2024-12-31 was at most 47s (median ~30s).
# 90s is three nominal 30s intervals. It is not DH3's 10-minute grid rule, and it is not
# refit after the full-archive gap list or after any outcome.
MAX_STALENESS_MS = 90_000
PRIMARY_MS = 3_600_000

CORE_DATASET_ID = "CORE_BTC_BINANCE_V0"
CORE_ZIP_LIST_SHA256 = "936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b"

# Parent #352 volatility terciles. Not refit on this cohort.
PARENT_SIGMA_LO = 0.0012364306616934476
PARENT_SIGMA_HI = 0.001790567553180052

SURFACE_END = "2025-01-01T00:00:00+00:00"
# First snapshot on 2023-01-01 is 00:06:05Z. A round hour after that, plus the 60m
# comparison, keeps the lookback inside the archive without using the touch sample.
EVENT_START = "2023-01-01T02:00:00+00:00"
EVENT_END = SURFACE_END

MINUTE_MS = 60_000
BAR_MS = 300_000
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
TAKER_BARS = 12         # opens [T-60m, T); quote volume only, not a tested feature
REL_VOL_BARS = 288
REL_VOL_MIN_PRESENT = 0.9
HORIZON = 48

# Simpler quantity first. A later feature with |rho| >= 0.90 against an earlier one is dropped.
RAW_FEATURES = (
    "TOTAL_LOCAL_DEPTH",
    "ORIENTED_DEPTH_IMBALANCE",
    "AHEAD_DEPTH_CHANGE_60M",
    "BEHIND_DEPTH_CHANGE_60M",
    "TOTAL_DEPTH_CHANGE_60M",
)
REDUNDANCY_RHO = 0.90
MIN_RETAINED = 3

OUTCOMES = ("RESOLVE_4H", "BREAK_GIVEN_RESOLVED")
EPOCHS = ("2023H1", "2023H2", "2024H1", "2024H2")
EPOCH_BOUNDS = (
    ("2023H1", "2023-01-01T00:00:00+00:00", "2023-07-01T00:00:00+00:00"),
    ("2023H2", "2023-07-01T00:00:00+00:00", "2024-01-01T00:00:00+00:00"),
    ("2024H1", "2024-01-01T00:00:00+00:00", "2024-07-01T00:00:00+00:00"),
    ("2024H2", "2024-07-01T00:00:00+00:00", "2025-01-01T00:00:00+00:00"),
)
FAMILIES = ("DAY", "WEEK", "MONTH")

BOOT_DRAWS = 2000
BOOT_SEED = 20261016
BOOT_MIN_VALID_FRAC = 0.9
CI_ALPHA = 0.05
FDR_Q = 0.10
# Product level-reaction floor. Same reading scale as #352 and #358.
# Not the DH1 3pp-plus-Brier bar. Not lowered after the result.
PRACTICAL_SCALE = 0.03
SPECIFICITY_SCALE = 0.03
SIMILARITY_RATIO = 0.5
EPOCH_MIN_N = 30
EPOCH_SIGN_MIN = 3          # of the epochs that clear EPOCH_MIN_N; there are only four
SIDE_MIN_N = 30
FAMILY_COMPLEMENT_MIN_N = 30
MIN_CELL_N = 100
INFO_MIN_N = 100
INFO_MIN_CLUSTERS = 20
# Parent planning deff. Used only as an outcome-blind information context, not a gate.
INFO_DEFF = 1.25

# Reference levels: DAY, resistance (side +1), 2023H1, low vol, 00-06 UTC.
FAMILY_DUMMIES = ("fam_week", "fam_month")
VOL_DUMMIES = ("vol_mid", "vol_high")
TIME_DUMMIES = ("tb1", "tb2", "tb3")


def _ms(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso).timestamp() * 1000)


EVENT_START_MS = _ms(EVENT_START)
EVENT_END_MS = _ms(EVENT_END)
SURFACE_END_MS = _ms(SURFACE_END)
EPOCH_BOUND_MS = tuple((name, _ms(a), _ms(b)) for name, a, b in EPOCH_BOUNDS)

if EVENT_END_MS != SURFACE_END_MS:
    raise RuntimeError("event end drifted from the 2025-01-01 bound")
if EVENT_START_MS >= EVENT_END_MS:
    raise RuntimeError("event window is empty")
if MAX_STALENESS_MS != 90_000:
    raise RuntimeError("staleness drifted")


def stream_seed(feature_index: int, outcome_index: int, kind: int) -> int:
    """Disjoint bootstrap streams. kind is a small integer fixed in inference.py."""
    return int(BOOT_SEED + feature_index * 1000 + outcome_index * 100 + kind)


def exposure(n_retained: int) -> dict:
    """Predeclared cell counts. Slices are computed for every primary cell.
    They are not a second FDR family.
    """
    primary = int(n_retained) * len(OUTCOMES)
    return {
        "raw_features": len(RAW_FEATURES),
        "retained_features": int(n_retained),
        "windows": 2,
        "outcomes": len(OUTCOMES),
        "primary_cells": primary,
        "shape_cells": primary,
        "pseudo_cells": primary,
        "specificity_cells": primary,
        "stability_cells": primary * (len(EPOCHS) + len(FAMILIES) + 2),
        "loeo_cells": primary * len(EPOCHS),
        "lofo_cells": primary * len(FAMILIES),
        "interactions": 0,
        "clusters": 0,
        "extra_window_sensitivities": 0,
        "dh3_quintiles": 0,
    }
