"""Design-only D2 excess direction-aligned path-risk decomposition.

Changes the TARGET QUESTION, not the D2 / RULE_1 / RV_ABSTENTION selector.

Does not load CORE BTC / BitMEX OHLC.
Does not compute real ADVERSE_SHARE / DELTA_SHARE / classification.
Does not open Binance 2025/2026.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_cross_venue_dislocation_evaluator import (
    FUTURE_BARS,
    arithmetic_mae,
)
from scripts.research.market_06_cross_venue_dislocation_parsers import PerpBar

UNIT = "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN"
EVIDENCE_CLASS = "POST_REPLICATION_MECHANISM_DECOMPOSITION_DISCOVERY"
JSON_REL = (
    "docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN.json"
)
MD_REL = (
    "docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN.md"
)

PRIMARY_SELECTOR = "D2_RULE_1_RV_ABSTENTION"
PRIMARY_TARGET = "ADVERSE_SHARE"
PRIMARY_COMPARATOR = "YEAR_SIDE_MATCHED_RATE_MATCHED_RANDOM_ABSTENTION"
CONTROL_STRATA = "calendar_year × frozen_SIDE"
CONTROL_YEARS = ("2020", "2021", "2022", "2023", "2024")
SIDE_LABELS = ("LONG", "SHORT")
RANDOM_SEED = 20260922131
N_RANDOM_CONTROLS = 10000
PRACTICAL_DELTA_SHARE = 0.05
PATH_SCALE_PRACTICAL_RELATIVE_BAR = 0.20
TEMPORAL_YEARS_REQUIRED = 3
TEMPORAL_YEARS_TOTAL = 5
RV_TRAILING_WINDOW = C.RV_TRAILING_WINDOW
RV_PCTL = C.RV_PCTL
FUTURE_BAR_COUNT = FUTURE_BARS
D2_DISCOVERY_RESULT_REL = "docs/research/discovery_results/D2_DISCOVERY_RESULT.json"
PROGRAM_DECISION_REL = (
    "docs/research/PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED.json"
)
FROZEN_D2_DISCOVERY_SHA256 = (
    "42ee5d7db19a17e62d861513759192ec78898ee9ec901902b3db58e7386966c2"
)
FROZEN_PROGRAM_DECISION_SHA256 = (
    "d9b6000273d93ea86b0d02282dfa9f12f3b1aad9bb25322dbbbcc689f008448d"
)
FROZEN_COMMON_SHA256 = (
    "ab152da63fa8c923fba3fd0255b7cd4d6457389b6a45be9959abc7235fa912ef"
)
FROZEN_D2_CARD_SHA256 = (
    "2c00d7510e497cee48b169c1e6296982600567fffe0cb94e08fb9bcef2931991"
)
FROZEN_ARITHMETIC_MAE_MODULE_SHA256 = (
    "ff87062edf583af1a67affcc18cda5e184379d9e63f7ff8b0e18383978890ead"
)
FROZEN_RULE1_N = 1791
FROZEN_RULE1_YEAR_N = {
    "2020": 334,
    "2021": 364,
    "2022": 364,
    "2023": 364,
    "2024": 365,
}
TARGET_INELIGIBLE_REASON = "TARGET_ROW_INELIGIBLE_PATH_SCALE_NONPOSITIVE"

CLASS_PROMISING = "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PROMISING"
CLASS_SCALE_COMPATIBLE = "D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT"
CLASS_NO_STRUCTURE = "D2_DECOMPOSITION_NO_USEFUL_STRUCTURE"
CLASS_INVALID = "D2_DECOMPOSITION_INVALID"
CLASSIFICATION_ORDER = (
    CLASS_INVALID,
    CLASS_PROMISING,
    CLASS_SCALE_COMPATIBLE,
    CLASS_NO_STRUCTURE,
)
CLASS_SCALE_COMPATIBLE_INTERPRETATION = (
    "no ROBUST excess alignment under the frozen all-gates rule; "
    "not proof that excess alignment is absent"
)


class RealDecompositionForbidden(RuntimeError):
    """Real-data decomposition outcomes are forbidden in this design unit."""


class InsufficientStratumSupport(RuntimeError):
    """K_{y,s} exceeds available target-eligible control population."""


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mae_pair(
    side: float,
    entry: float,
    future_bars: Sequence[PerpBar],
) -> tuple[float, float]:
    """MAE_SIDE and MAE_OPPOSITE on the exact same future path."""
    mae_side = float(arithmetic_mae(float(side), float(entry), future_bars))
    mae_opposite = float(arithmetic_mae(float(-side), float(entry), future_bars))
    return mae_side, mae_opposite


def path_scale(mae_side: float, mae_opposite: float) -> float:
    return float(mae_side) + float(mae_opposite)


def adverse_share(mae_side: float, mae_opposite: float) -> float | None:
    scale = path_scale(mae_side, mae_opposite)
    if not math.isfinite(scale) or scale <= 0.0:
        return None
    share = float(mae_side) / scale
    if not math.isfinite(share) or share < 0.0 or share > 1.0:
        return None
    return float(share)


def path_asymmetry(share: float) -> float:
    """Secondary signed representation. Not the primary target."""
    return float(2.0 * float(share) - 1.0)


def target_ineligible_reason(mae_side: float, mae_opposite: float) -> str | None:
    scale = path_scale(mae_side, mae_opposite)
    if (not math.isfinite(scale)) or scale <= 0.0:
        return TARGET_INELIGIBLE_REASON
    if adverse_share(mae_side, mae_opposite) is None:
        return TARGET_INELIGIBLE_REASON
    return None


def mc_p_share(mu_share_rule: float, control_share_means: Sequence[float]) -> float:
    """(1 + count(control_mean >= MU_SHARE_RULE)) / (N_CONTROLS + 1)."""
    n = int(len(control_share_means))
    count = sum(1 for mean in control_share_means if float(mean) >= float(mu_share_rule))
    return float(1 + count) / float(n + 1)


def statistical_gate(mu_share_rule: float, control_share_p95: float) -> bool:
    return bool(float(mu_share_rule) > float(control_share_p95))


def practical_gate(delta_share: float) -> bool:
    return bool(float(delta_share) >= PRACTICAL_DELTA_SHARE)


def temporal_gate(year_delta_share: Mapping[str, float | None]) -> bool:
    positive = 0
    for year in ("2020", "2021", "2022", "2023", "2024"):
        delta = year_delta_share.get(year)
        if delta is not None and float(delta) > 0.0:
            positive += 1
    return bool(positive >= TEMPORAL_YEARS_REQUIRED)


def path_scale_materially_elevated(
    *,
    mu_path_scale_rule: float,
    mu_path_scale_control: float,
    control_path_scale_p95: float,
) -> bool:
    """Diagnostic only. Cannot rescue ADVERSE_SHARE gates."""
    if not math.isfinite(mu_path_scale_control) or mu_path_scale_control <= 0.0:
        return False
    statistical = bool(float(mu_path_scale_rule) > float(control_path_scale_p95))
    practical = bool(
        float(mu_path_scale_rule) - float(mu_path_scale_control)
        >= PATH_SCALE_PRACTICAL_RELATIVE_BAR * float(mu_path_scale_control)
    )
    return bool(statistical and practical)


def classify_decomposition(
    *,
    integrity_invalid: bool,
    statistical: bool,
    practical: bool,
    temporal: bool,
    path_scale_elevated: bool,
) -> str:
    """Exhaustive pre-outcome classification. Exactly one class per execution."""
    if integrity_invalid:
        return CLASS_INVALID
    if statistical and practical and temporal:
        return CLASS_PROMISING
    if path_scale_elevated:
        return CLASS_SCALE_COMPATIBLE
    return CLASS_NO_STRUCTURE


def random_generator(seed: int = RANDOM_SEED) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(int(seed)))


def encode_side(side: float | str) -> str:
    if isinstance(side, str):
        label = side.upper()
        if label not in SIDE_LABELS:
            raise ValueError("INVALID_SIDE_LABEL")
        return label
    value = float(side)
    if value == 1.0:
        return "LONG"
    if value == -1.0:
        return "SHORT"
    raise ValueError("INVALID_SIDE")


def candidate_stratum_counts(
    years: Sequence[int],
    sides: Sequence[float | str],
    candidate: Sequence[bool],
) -> dict[tuple[str, str], int]:
    counts = {(year, side): 0 for year in CONTROL_YEARS for side in SIDE_LABELS}
    for year, side, flag in zip(years, sides, candidate, strict=True):
        if not bool(flag):
            continue
        key = (str(int(year)), encode_side(side))
        if key not in counts:
            raise InsufficientStratumSupport(f"UNKNOWN_STRATUM:{key}")
        counts[key] += 1
    return counts


def year_side_matched_control_masks(
    years: Sequence[int],
    sides: Sequence[float | str],
    target_eligible: Sequence[bool],
    candidate: Sequence[bool],
    *,
    seed: int = RANDOM_SEED,
    n_replicates: int = N_RANDOM_CONTROLS,
) -> np.ndarray:
    """Boolean masks of shape (n_replicates, n). Same mask for share and scale.

    Within each (calendar year, frozen SIDE) stratum independently, each
    replicate draws exactly K_{y,s} target-eligible rows without replacement.
    K=0 draws zero rows. K exceeding stratum population fails closed.
    No pooled K. No year-only fallback.
    """
    n = len(years)
    if not (n == len(sides) == len(target_eligible) == len(candidate)):
        raise InsufficientStratumSupport("SHAPE_MISMATCH")
    years_arr = np.asarray([int(year) for year in years], dtype=np.int64)
    side_labels = np.asarray([encode_side(side) for side in sides])
    eligible = np.asarray(list(target_eligible), dtype=bool)
    cand = np.asarray(list(candidate), dtype=bool)
    if np.any(cand & ~eligible):
        raise InsufficientStratumSupport("CANDIDATE_NOT_TARGET_ELIGIBLE")
    k_counts = candidate_stratum_counts(years, sides, candidate)
    stratum_idx: dict[tuple[str, str], np.ndarray] = {}
    for year in CONTROL_YEARS:
        for side in SIDE_LABELS:
            idx = np.flatnonzero(
                eligible & (years_arr == int(year)) & (side_labels == side)
            )
            need = int(k_counts[(year, side)])
            if need > int(idx.size):
                raise InsufficientStratumSupport(
                    f"K_EXCEEDS_POPULATION:{year}:{side}:{need}>{int(idx.size)}"
                )
            stratum_idx[(year, side)] = idx
    rng = random_generator(seed)
    masks = np.zeros((int(n_replicates), n), dtype=bool)
    for replicate in range(int(n_replicates)):
        for year in CONTROL_YEARS:
            for side in SIDE_LABELS:
                need = int(k_counts[(year, side)])
                if need == 0:
                    continue
                chosen = rng.choice(stratum_idx[(year, side)], size=need, replace=False)
                masks[replicate, chosen] = True
    return masks


def means_from_shared_masks(
    values: Sequence[float],
    masks: np.ndarray,
) -> np.ndarray:
    """Apply already-drawn year×SIDE masks to a row-level series."""
    arr = np.asarray(list(values), dtype=np.float64)
    if arr.shape[0] != masks.shape[1]:
        raise InsufficientStratumSupport("VALUE_MASK_SHAPE")
    out = np.empty(masks.shape[0], dtype=np.float64)
    for i, row in enumerate(masks):
        if not bool(row.any()):
            out[i] = float("nan")
        else:
            out[i] = float(arr[row].mean())
    return out


def year_means_from_shared_masks(
    years: Sequence[int],
    values: Sequence[float],
    masks: np.ndarray,
) -> dict[str, np.ndarray]:
    """Yearly diagnostics from the SAME year×SIDE matched replicate system."""
    years_arr = np.asarray([int(year) for year in years], dtype=np.int64)
    arr = np.asarray(list(values), dtype=np.float64)
    out: dict[str, np.ndarray] = {}
    for year in CONTROL_YEARS:
        in_year = years_arr == int(year)
        year_means = np.empty(masks.shape[0], dtype=np.float64)
        for i, row in enumerate(masks):
            selected = row & in_year
            if not bool(selected.any()):
                year_means[i] = float("nan")
            else:
                year_means[i] = float(arr[selected].mean())
        out[year] = year_means
    return out


def refuse_real_decomposition_outcome() -> None:
    raise RealDecompositionForbidden("REAL_DECOMPOSITION_OUTCOME_FORBIDDEN")


def frozen_d2_selector_contract() -> dict[str, Any]:
    return {
        "PRIMARY_SELECTOR": PRIMARY_SELECTOR,
        "ABSTAIN_RULE": (
            "ABSTAIN(t)=1 iff RV_BTC_24H(t) > P90 of previous 250 valid "
            "constructed-row RV observations; t excluded; strict >"
        ),
        "RV_TRAILING_WINDOW": int(RV_TRAILING_WINDOW),
        "RV_PCTL": float(RV_PCTL),
        "DECISION_CLOCK": "00:05Z daily discovery decisions",
        "INTERVAL_START": "2020-02-01T00:05:00Z",
        "INTERVAL_END_EXCLUSIVE": "2025-01-01T00:00:00Z",
        "ENTRY": "5m OPEN at T",
        "HORIZON_BARS": int(FUTURE_BAR_COUNT),
        "BTC_RET_24H": "frozen btc_ret_24h at feature cutoff E=T-5m",
        "BTC_SIDE": "sign(BTC_RET_24H) via frozen btc_side_from_ret",
        "TRAILING_HISTORY_AUTHORITY": "VALID_CONSTRUCTED_ROWS",
        "MASK_FUNCTION": "scripts.research.discovery_sprint_01.common.rv_abstention_mask",
        "ROW_CONSTRUCTOR": "scripts.research.discovery_sprint_01.common.construct_discovery_row",
        "NO_P85_P95": True,
        "NO_ALTERNATE_RV": True,
        "NO_ALTERNATE_HORIZON": True,
        "NO_ALTERNATE_ENTRY": True,
        "D2_SELECTOR_CHANGED": False,
    }


def identity_metadata_from_frozen_discovery(repo: Path) -> dict[str, Any]:
    """Read frozen D2 discovery metadata only. Does not rebuild rows."""
    path = repo / D2_DISCOVERY_RESULT_REL
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "TERMINAL_CLASSIFICATION": payload.get("TERMINAL_CLASSIFICATION"),
        "RULE_1_ROW_COUNT": payload.get("RULE_1_ROW_COUNT"),
        "RULE_1_YEAR_BREAKDOWN": payload.get("RULE_1_YEAR_BREAKDOWN"),
        "CORE_BTC_SNAPSHOT": (payload.get("DATASET_IDENTITIES") or {})
        .get("RULE_1", {})
        .get("CORE_BTC_BINANCE_V0"),
        "RULE_1_INTERVAL": (payload.get("INTERVAL_USED") or {}).get("RULE_1"),
        "D2_DISCOVERY_CONTROL_SEED_NOT_REUSED": C.D2_RANDOM_CONTROL_SEED,
    }


def verify_design_authorities(repo: Path) -> list[str]:
    blockers: list[str] = []
    if file_sha256(repo / D2_DISCOVERY_RESULT_REL) != FROZEN_D2_DISCOVERY_SHA256:
        blockers.append("D2_DISCOVERY_RESULT_SHA")
    if file_sha256(repo / PROGRAM_DECISION_REL) != FROZEN_PROGRAM_DECISION_SHA256:
        blockers.append("PROGRAM_DECISION_SHA")
    if (
        file_sha256(repo / "scripts/research/discovery_sprint_01/common.py")
        != FROZEN_COMMON_SHA256
    ):
        blockers.append("COMMON_SHA")
    if (
        file_sha256(repo / "scripts/research/discovery_sprint_01/d2_abstention_tail_risk.py")
        != FROZEN_D2_CARD_SHA256
    ):
        blockers.append("D2_CARD_SHA")
    if (
        file_sha256(
            repo / "scripts/research/market_06_cross_venue_dislocation_evaluator.py"
        )
        != FROZEN_ARITHMETIC_MAE_MODULE_SHA256
    ):
        blockers.append("ARITHMETIC_MAE_MODULE_SHA")
    meta = identity_metadata_from_frozen_discovery(repo)
    if int(meta["RULE_1_ROW_COUNT"] or 0) != FROZEN_RULE1_N:
        blockers.append("RULE_1_N")
    if meta["RULE_1_YEAR_BREAKDOWN"] != FROZEN_RULE1_YEAR_N:
        blockers.append("RULE_1_YEAR_N")
    if int(RV_TRAILING_WINDOW) != 250:
        blockers.append("RV_TRAILING_WINDOW")
    if float(RV_PCTL) != 90.0:
        blockers.append("RV_PCTL")
    if int(FUTURE_BAR_COUNT) != 288:
        blockers.append("FUTURE_BARS")
    if RANDOM_SEED == C.D2_RANDOM_CONTROL_SEED:
        blockers.append("SEED_COLLISION_WITH_D2_DISCOVERY")
    if RANDOM_SEED == 20260921125:
        blockers.append("SEED_COLLISION_WITH_D2_BITMEX")
    return blockers
