"""Frozen design constants for LEVEL_FLOW_RESPONSE_STATE_DISCOVERY_V1.

The five observables, the robust scaler, the K grid and the candidate rule
are fixed before any state is joined to a resolution label.
"""

from __future__ import annotations

import datetime as dt

UNIT = "LEVEL_FLOW_RESPONSE_STATE_DISCOVERY_V1"
FAMILY = "LEVEL_BEHAVIOR_V1"
MODE = "DISCOVERY"
TRACKS = ("STRUCTURE", "PRODUCT_EVIDENCE")
CLAIM_CEILING = "L2"
PRODUCT_INTEGRATION_CANDIDATE = False
SOURCE_MAIN_HEAD = "1a2e425303fb29e1044ca57452b8ad9b6f0a831b"

DEPENDENCY_TOUCH_SHA = "dfc9e0f04358de15606382472badeb5aee787039"
DEPENDENCY_MEMORY_SHA = "c3d39bffda861b535605a98205d7578c0c84c782"
DEPENDENCY_METHOD_SHA = "8effe9acc3b88b925a79b33f04ac0ee9e6f93e26"
DEPENDENCY_APPROACH_SHA = "aa85e5b43c405ee225336ff385e3a3383fa59d09"
DEPENDENCY_STRUCTURE_SHA = "f8623d3281424c165ebd7ee7fbcb0af994cc1e8d"
DEPENDENCY_CONFIRM_SHA = "c1cd4e0102e700f7860d21a9af0d243c3bc367be"
DEPENDENCY_POSITION_SHA = "e6e5f307cfa098db607544a556bae01a2310eb6a"

# Same admissible surfaces as #358. Not a new data contract.
OI_DATASET_ID = "B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0"
OI_SNAPSHOT_ID = "5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33"
OI_JSONL_SHA256 = "c4744a9369844f453476589111c2436372e729e7afdbe5fb34b6e9938a905b94"
OI_JSONL_ROWS = 455273
CORE_DATASET_ID = "CORE_BTC_BINANCE_V0"
CORE_ZIP_LIST_SHA256 = "936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b"

SURFACE_END = "2025-01-01T00:00:00+00:00"
EVENT_START = "2020-09-01T01:05:00+00:00"
EVENT_END = SURFACE_END
HORIZON = 48

FEATURES = (
    "OI_CHANGE_60M",
    "OI_RECENT_ACCELERATION",
    "ORIENTED_TAKER_IMBALANCE_60M",
    "TAKER_RECENT_SHIFT",
    "ORIENTED_PRICE_PROGRESS_60M",
)
# Robust normal quantile width of the interquartile range. Frozen.
ROBUST_IQR_SCALE = 1.349
CLIP = 5.0
K_GRID = (3, 4, 5, 6)
KMEANS_SEED = 20261014
KMEANS_N_INIT = 16
KMEANS_MAX_ITER = 50
KMEANS_TOL = 1e-7
MIN_CLUSTER_N = 100
MIN_CLUSTER_SHARE = 0.05
STABILITY_DRAWS = 40
STABILITY_ARI_MIN = 0.75
# Predictor-only membership. A state below this median Jaccard cannot be a candidate.
MEMBERSHIP_JACCARD_MIN = 0.50
# Words for a centroid coordinate. Not a split and not a new state.
WORD_Z = 0.50

OUTCOMES = ("RESOLVE_4H", "BREAK_GIVEN_RESOLVED")
EPOCHS = ("2020Q4", "2021", "2022", "2023", "2024")
FAMILIES = ("DAY", "WEEK", "MONTH")

BOOT_DRAWS = 2000
BOOT_SEED = 20261015
BOOT_MIN_VALID_FRAC = 0.9
CI_ALPHA = 0.05
FDR_Q = 0.10
# Probability points on the state-versus-rest contrast. Not a per-SD slope
# and not the DH1 3 pp plus Brier bar.
PRACTICAL_SCALE = 0.03
SPECIFICITY_SCALE = 0.03
SIMILARITY_RATIO = 0.5
YEAR_MIN_N = 30
YEAR_SIGN_MIN = 4
TINY_FAMILY_SHARE = 0.15
MIN_CELL_N = 100
INFO_MIN_N = 100
INFO_MIN_CLUSTERS = 20

YEAR_DUMMIES = ("y2021", "y2022", "y2023", "y2024")
FAMILY_DUMMIES = ("fam_week", "fam_month")
VOL_DUMMIES = ("vol_mid", "vol_high")
TIME_DUMMIES = ("tb1", "tb2", "tb3")


def _ms(iso: str) -> int:
    return int(dt.datetime.fromisoformat(iso).timestamp() * 1000)


EVENT_START_MS = _ms(EVENT_START)
EVENT_END_MS = _ms(EVENT_END)
SURFACE_END_MS = _ms(SURFACE_END)


def stream_seed(state_index: int, outcome_index: int, kind: int) -> int:
    return int(BOOT_SEED + state_index * 1000 + outcome_index * 100 + kind)


def exposure(k: int) -> dict:
    primary = int(k) * len(OUTCOMES)
    return {
        "raw_variables": len(FEATURES),
        "windows": 1,
        "k_candidates": list(K_GRID),
        "selected_k": int(k),
        "clustering_quality_cells": len(K_GRID),
        "primary_cells": primary,
        "pseudo_cells": primary,
        "specificity_cells": primary,
        "stability_cells": primary * (len(EPOCHS) + len(FAMILIES) + 2),
        "loyo_cells": primary * len(EPOCHS),
        "three_way_maps": int(k),
        "individual_slope_models": 0,
        "interactions": 0,
        "extra_window_sensitivities": 0,
    }
