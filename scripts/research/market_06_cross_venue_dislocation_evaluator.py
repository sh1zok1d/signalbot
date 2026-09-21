"""MARKET-06 frozen scientific evaluator (synthetic-capable).

Implements the live amendment-002 preregistration. Canonical evaluation
of the retained 2022-2024 dataset is refused in this unit.

TRAIN_SD_CONVENTION = numpy.std(x, ddof=0)  # population SD.
Positive rescaling of a regressor leaves OLS predictions and the sign of
its coefficient invariant, so this convention cannot change eligibility,
gates, or final classification under the frozen predicates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

import numpy as np

from scripts.research.market_06_cross_venue_dislocation_authority import (
    CLASS_INCOMPLETE,
    CLASS_NO_EVIDENCE,
    CLASS_PROMOTED,
    FORBIDDEN_PROMOTION_STATES,
    Market06IncompleteExecution,
    refuse_canonical_execution,
)
from scripts.research.market_06_cross_venue_dislocation_bootstrap import (
    coefficient_moving_block_bootstrap,
    make_rng,
    ols_solve,
    percentile_ci,
    relative_mae_improvement,
    year_stratified_predictive_bootstrap,
)
from scripts.research.market_06_cross_venue_dislocation_parsers import (
    BAR_MS,
    PerpBar,
)
from scripts.research.market_06_year_stratified_circular_mbb import (
    BLOCK_LENGTH_DAYS,
    BOOTSTRAP_REPLICATES,
    RANDOM_SEED,
)


MAD_CONSISTENCY_CONSTANT = 1.4826
REFERENCE_COUNT = 8640
RV_RETURN_COUNT = 288
FUTURE_BARS = 288
MATERIALITY_THRESHOLD = 0.02
G6_ADVERSE_YEAR_THRESHOLD = -0.02
TRAIN_SD_CONVENTION = "numpy.std(x, ddof=0)"
TRAIN_SD_DDOF = 0
CONTINUOUS_COLUMNS = ("abs_btc_ret_24h", "rv_btc_24h", "abs_dislocation_z")
BASELINE_COLUMNS = (
    "INTERCEPT",
    "BTC_SIDE",
    "ABS_BTC_RET_24H_STD",
    "RV_BTC_24H_STD",
)
CANDIDATE_COLUMNS = BASELINE_COLUMNS + ("ABS_DISLOCATION_Z_STD",)

TRAIN_START = datetime(2022, 2, 1, 0, 5, tzinfo=timezone.utc)
TRAIN_END = datetime(2022, 12, 30, 0, 5, tzinfo=timezone.utc)
HOLDOUT_2023_START = datetime(2023, 1, 1, 0, 5, tzinfo=timezone.utc)
HOLDOUT_2023_END = datetime(2023, 12, 30, 0, 5, tzinfo=timezone.utc)
HOLDOUT_2024_START = datetime(2024, 1, 1, 0, 5, tzinfo=timezone.utc)
HOLDOUT_2024_END = datetime(2024, 12, 30, 0, 5, tzinfo=timezone.utc)

SPLIT_BOUNDS = {
    "TRAIN": (TRAIN_START, TRAIN_END),
    "HOLDOUT_2023": (HOLDOUT_2023_START, HOLDOUT_2023_END),
    "HOLDOUT_2024": (HOLDOUT_2024_START, HOLDOUT_2024_END),
}


@dataclass(frozen=True)
class EligibleRow:
    t_ms: int
    split: str
    year: int
    btc_side: float
    abs_btc_ret_24h: float
    rv_btc_24h: float
    abs_dislocation_z: float
    y: float


def _ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def feature_cutoff_ms(t_ms: int) -> int:
    return int(t_ms - BAR_MS)


def is_forbidden_decision(moment: datetime) -> str | None:
    if moment.year >= 2025:
        return "PROTECTED_2025_PLUS"
    if moment.year >= 2026:
        return "PROTECTED_2026"
    if moment.month == 12 and moment.day == 31:
        return "DECEMBER_31_FORBIDDEN"
    if moment.hour != 0 or moment.minute != 5 or moment.second != 0 or moment.microsecond != 0:
        return "NOT_DAILY_0005"
    return None


def iter_decision_times(start: datetime, end: datetime) -> list[datetime]:
    if start.tzinfo is None or end.tzinfo is None:
        raise Market06IncompleteExecution("NAIVE_DATETIME")
    out: list[datetime] = []
    cursor = start
    while cursor <= end:
        reason = is_forbidden_decision(cursor)
        if reason:
            raise Market06IncompleteExecution(f"ILLEGAL_DECISION:{reason}:{cursor.isoformat()}")
        out.append(cursor)
        cursor = cursor + timedelta(days=1)
    return out


def decision_times_for_split(split: str) -> list[datetime]:
    start, end = SPLIT_BOUNDS[split]
    return iter_decision_times(start, end)


def dislocation_d(perp_close: float, spot_close: float) -> float:
    if perp_close <= 0.0 or spot_close <= 0.0:
        raise Market06IncompleteExecution("NONPOSITIVE_CLOSE_FOR_D")
    value = math.log(perp_close / spot_close)
    if not math.isfinite(value):
        raise Market06IncompleteExecution("NONFINITE_D")
    return float(value)


def robust_dislocation_z(d_e: float, ref: Sequence[float]) -> tuple[float, float, float, float]:
    if len(ref) != REFERENCE_COUNT:
        raise Market06IncompleteExecution(f"REFERENCE_COUNT:{len(ref)}")
    ref_arr = np.asarray(ref, dtype=np.float64)
    if not np.all(np.isfinite(ref_arr)):
        raise Market06IncompleteExecution("NONFINITE_REF")
    center = float(np.median(ref_arr))
    mad = float(np.median(np.abs(ref_arr - center)))
    if not math.isfinite(mad) or mad <= 0.0:
        raise Market06IncompleteExecution("MAD_LE_0")
    scale = MAD_CONSISTENCY_CONSTANT * mad
    z = (float(d_e) - center) / scale
    if not math.isfinite(z):
        raise Market06IncompleteExecution("NONFINITE_Z")
    return center, mad, scale, float(z)


def btc_ret_24h(close_e: float, close_e_minus_24h: float) -> float:
    if close_e <= 0.0 or close_e_minus_24h <= 0.0:
        raise Market06IncompleteExecution("NONPOSITIVE_BTC_RET_CLOSE")
    value = math.log(close_e / close_e_minus_24h)
    if not math.isfinite(value) or value == 0.0:
        raise Market06IncompleteExecution("BTC_RET_24H_ZERO_OR_NONFINITE")
    return float(value)


def btc_side_from_ret(ret: float) -> float:
    if ret > 0.0:
        return 1.0
    if ret < 0.0:
        return -1.0
    raise Market06IncompleteExecution("BTC_RET_24H_ZERO_OR_NONFINITE")


def rv_btc_24h(closes_inclusive: Sequence[float]) -> float:
    if len(closes_inclusive) != RV_RETURN_COUNT + 1:
        raise Market06IncompleteExecution(f"RV_CLOSE_COUNT:{len(closes_inclusive)}")
    total = 0.0
    prev = float(closes_inclusive[0])
    for price in closes_inclusive[1:]:
        current = float(price)
        if prev <= 0.0 or current <= 0.0:
            raise Market06IncompleteExecution("NONPOSITIVE_RV_CLOSE")
        ret = math.log(current / prev)
        if not math.isfinite(ret):
            raise Market06IncompleteExecution("NONFINITE_RV_RETURN")
        total += ret * ret
        prev = current
    value = math.sqrt(total)
    if not math.isfinite(value) or value <= 0.0:
        raise Market06IncompleteExecution("RV_LE_0_OR_NONFINITE")
    return float(value)


def arithmetic_mae(btc_side: float, entry: float, future_bars: Sequence[PerpBar]) -> float:
    if len(future_bars) != FUTURE_BARS:
        raise Market06IncompleteExecution(f"FUTURE_BAR_COUNT:{len(future_bars)}")
    if not math.isfinite(entry) or entry <= 0.0:
        raise Market06IncompleteExecution("NONPOSITIVE_ENTRY")
    lows = [bar.low for bar in future_bars]
    highs = [bar.high for bar in future_bars]
    if btc_side == 1.0:
        y = max(0.0, (entry - min(lows)) / entry)
    elif btc_side == -1.0:
        y = max(0.0, (max(highs) - entry) / entry)
    else:
        raise Market06IncompleteExecution("INVALID_BTC_SIDE")
    if not math.isfinite(y) or y < 0.0:
        raise Market06IncompleteExecution("NONFINITE_Y")
    return float(y)


def _lookup_perp(perp: Mapping[int, PerpBar], ts: int) -> PerpBar | None:
    return perp.get(ts)


def _lookup_spot(spot: Mapping[int, float], ts: int) -> float | None:
    return spot.get(ts)


def _d_at(
    perp: Mapping[int, PerpBar],
    spot: Mapping[int, float],
    ts: int,
) -> float | None:
    bar = _lookup_perp(perp, ts)
    close_spot = _lookup_spot(spot, ts)
    if bar is None or close_spot is None:
        return None
    try:
        return dislocation_d(bar.close, close_spot)
    except Market06IncompleteExecution:
        return None


def construct_row_or_none(
    t_ms: int,
    split: str,
    perp: Mapping[int, PerpBar],
    spot: Mapping[int, float],
) -> EligibleRow | None:
    moment = datetime.fromtimestamp(t_ms / 1000, tz=timezone.utc)
    reason = is_forbidden_decision(moment)
    if reason:
        return None
    e_ms = feature_cutoff_ms(t_ms)
    d_e = _d_at(perp, spot, e_ms)
    if d_e is None:
        return None
    ref: list[float] = []
    for k in range(1, REFERENCE_COUNT + 1):
        value = _d_at(perp, spot, e_ms - k * BAR_MS)
        if value is None:
            return None
        ref.append(value)
    try:
        _center, _mad, _scale, z = robust_dislocation_z(d_e, ref)
    except Market06IncompleteExecution:
        return None
    e_bar = _lookup_perp(perp, e_ms)
    e_24h = _lookup_perp(perp, e_ms - FUTURE_BARS * BAR_MS)
    if e_bar is None or e_24h is None:
        return None
    try:
        ret = btc_ret_24h(e_bar.close, e_24h.close)
        side = btc_side_from_ret(ret)
    except Market06IncompleteExecution:
        return None
    rv_closes: list[float] = []
    for k in range(RV_RETURN_COUNT, -1, -1):
        bar = _lookup_perp(perp, e_ms - k * BAR_MS)
        if bar is None:
            return None
        rv_closes.append(bar.close)
    try:
        rv = rv_btc_24h(rv_closes)
    except Market06IncompleteExecution:
        return None
    entry_bar = _lookup_perp(perp, t_ms)
    if entry_bar is None:
        return None
    future: list[PerpBar] = []
    for k in range(FUTURE_BARS):
        bar = _lookup_perp(perp, t_ms + k * BAR_MS)
        if bar is None:
            return None
        future.append(bar)
    try:
        y = arithmetic_mae(side, entry_bar.open, future)
    except Market06IncompleteExecution:
        return None
    return EligibleRow(
        t_ms=t_ms,
        split=split,
        year=moment.year,
        btc_side=side,
        abs_btc_ret_24h=abs(ret),
        rv_btc_24h=rv,
        abs_dislocation_z=abs(z),
        y=y,
    )


def build_eligible_rows(
    perp: Mapping[int, PerpBar],
    spot: Mapping[int, float],
    *,
    splits: Sequence[str] = ("TRAIN", "HOLDOUT_2023", "HOLDOUT_2024"),
) -> list[EligibleRow]:
    rows: list[EligibleRow] = []
    for split in splits:
        for moment in decision_times_for_split(split):
            row = construct_row_or_none(_ms(moment), split, perp, spot)
            if row is not None:
                rows.append(row)
    return rows


def fit_train_standardization(train: Sequence[EligibleRow]) -> tuple[np.ndarray, np.ndarray]:
    if not train:
        raise Market06IncompleteExecution("EMPTY_TRAIN")
    matrix = np.column_stack(
        [
            np.asarray([getattr(row, name) for row in train], dtype=np.float64)
            for name in CONTINUOUS_COLUMNS
        ]
    )
    mean = np.mean(matrix, axis=0)
    sd = np.std(matrix, axis=0, ddof=TRAIN_SD_DDOF)
    if (not np.all(np.isfinite(mean))) or (not np.all(np.isfinite(sd))) or np.any(sd <= 0.0):
        raise Market06IncompleteExecution("ZERO_OR_NONFINITE_TRAIN_SD")
    return mean, sd


def standardize_row(row: EligibleRow, mean: np.ndarray, sd: np.ndarray) -> np.ndarray:
    raw = np.asarray(
        [row.abs_btc_ret_24h, row.rv_btc_24h, row.abs_dislocation_z],
        dtype=np.float64,
    )
    std = (raw - mean) / sd
    return np.asarray(
        [1.0, row.btc_side, std[0], std[1], std[2]],
        dtype=np.float64,
    )


def design_matrices(
    rows: Sequence[EligibleRow],
    mean: np.ndarray,
    sd: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    candidate = np.vstack([standardize_row(row, mean, sd) for row in rows])
    baseline = candidate[:, :4]
    y = np.asarray([row.y for row in rows], dtype=np.float64)
    return baseline, candidate, y


def year_mae(y: np.ndarray, pred: np.ndarray) -> float:
    if y.size == 0:
        raise Market06IncompleteExecution("EMPTY_YEAR_MAE")
    return float(np.mean(np.abs(y - pred)))


def apply_six_gates(
    *,
    beta_abs_dislocation_z: float,
    beta_ci_low: float,
    pooled_improvement: float,
    pooled_improvement_ci_low: float,
    year_2023_improvement: float,
    year_2024_improvement: float,
) -> dict[str, bool]:
    g1 = bool(beta_abs_dislocation_z > 0.0)
    g2 = bool(beta_ci_low > 0.0)
    g3 = bool(pooled_improvement > 0.0)
    g4 = bool(pooled_improvement_ci_low > 0.0)
    g5 = bool(pooled_improvement >= MATERIALITY_THRESHOLD)
    g6_pos = bool(year_2023_improvement > 0.0 and year_2024_improvement > 0.0)
    g6_no_adverse = bool(
        year_2023_improvement > G6_ADVERSE_YEAR_THRESHOLD
        and year_2024_improvement > G6_ADVERSE_YEAR_THRESHOLD
        and not (year_2023_improvement <= G6_ADVERSE_YEAR_THRESHOLD)
        and not (year_2024_improvement <= G6_ADVERSE_YEAR_THRESHOLD)
    )
    g6 = bool(g6_pos and g6_no_adverse)
    return {
        "G1": g1,
        "G2": g2,
        "G3": g3,
        "G4": g4,
        "G5": g5,
        "G6": g6,
        "G6_BOTH_YEARS_POSITIVE": g6_pos,
        "G6_NO_YEAR_LE_MINUS_0_02": g6_no_adverse,
    }


def classify(gates: Mapping[str, bool]) -> str:
    if all(gates[name] for name in ("G1", "G2", "G3", "G4", "G5", "G6")):
        return CLASS_PROMOTED
    return CLASS_NO_EVIDENCE


def evaluate_from_eligible_rows(rows: Sequence[EligibleRow]) -> dict[str, Any]:
    train = [row for row in rows if row.split == "TRAIN"]
    hold_2023 = [row for row in rows if row.split == "HOLDOUT_2023"]
    hold_2024 = [row for row in rows if row.split == "HOLDOUT_2024"]
    if not train or not hold_2023 or not hold_2024:
        raise Market06IncompleteExecution("EMPTY_SPLIT_SUPPORT")
    mean, sd = fit_train_standardization(train)
    x_base_train, x_cand_train, y_train = design_matrices(train, mean, sd)
    beta_base = ols_solve(x_base_train, y_train)
    beta_cand = ols_solve(x_cand_train, y_train)
    beta_z = float(beta_cand[-1])
    if not math.isfinite(beta_z):
        raise Market06IncompleteExecution("NONFINITE_BETA")

    def _predict(split_rows: Sequence[EligibleRow]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        x_base, x_cand, y = design_matrices(split_rows, mean, sd)
        pred_base = x_base @ beta_base
        pred_cand = x_cand @ beta_cand
        return y, pred_base, pred_cand

    y23, p23b, p23c = _predict(hold_2023)
    y24, p24b, p24c = _predict(hold_2024)
    mae23b, mae23c = year_mae(y23, p23b), year_mae(y23, p23c)
    mae24b, mae24c = year_mae(y24, p24b), year_mae(y24, p24c)
    imp23 = relative_mae_improvement(mae23c, mae23b)
    imp24 = relative_mae_improvement(mae24c, mae24b)
    y_pool = np.concatenate([y23, y24])
    p_base_pool = np.concatenate([p23b, p24b])
    p_cand_pool = np.concatenate([p23c, p24c])
    mae_base = year_mae(y_pool, p_base_pool)
    mae_cand = year_mae(y_pool, p_cand_pool)
    pooled_imp = relative_mae_improvement(mae_cand, mae_base)

    loss_2023 = list(
        zip(np.abs(y23 - p23b).tolist(), np.abs(y23 - p23c).tolist())
    )
    loss_2024 = list(
        zip(np.abs(y24 - p24b).tolist(), np.abs(y24 - p24c).tolist())
    )

    rng = make_rng(RANDOM_SEED)
    beta_reps = coefficient_moving_block_bootstrap(x_cand_train, y_train, rng)
    beta_low, beta_high = percentile_ci(beta_reps)
    pred_reps = year_stratified_predictive_bootstrap(loss_2023, loss_2024, rng)
    pred_low, pred_high = percentile_ci(pred_reps)

    gates = apply_six_gates(
        beta_abs_dislocation_z=beta_z,
        beta_ci_low=beta_low,
        pooled_improvement=pooled_imp,
        pooled_improvement_ci_low=pred_low,
        year_2023_improvement=imp23,
        year_2024_improvement=imp24,
    )
    classification = classify(gates)
    if classification in FORBIDDEN_PROMOTION_STATES:
        raise Market06IncompleteExecution("FORBIDDEN_PROMOTION_STATE")
    return {
        "classification": classification,
        "gates": gates,
        "BETA_ABS_DISLOCATION_Z": beta_z,
        "BETA_ABS_DISLOCATION_Z_CI95_LOW": beta_low,
        "BETA_ABS_DISLOCATION_Z_CI95_HIGH": beta_high,
        "POOLED_MAE_BASELINE": mae_base,
        "POOLED_MAE_CANDIDATE": mae_cand,
        "RELATIVE_MAE_IMPROVEMENT": pooled_imp,
        "RELATIVE_MAE_IMPROVEMENT_CI95_LOW": pred_low,
        "RELATIVE_MAE_IMPROVEMENT_CI95_HIGH": pred_high,
        "YEAR_2023_RELATIVE_MAE_IMPROVEMENT": imp23,
        "YEAR_2024_RELATIVE_MAE_IMPROVEMENT": imp24,
        "YEAR_2023_BASELINE_MAE": mae23b,
        "YEAR_2023_CANDIDATE_MAE": mae23c,
        "YEAR_2024_BASELINE_MAE": mae24b,
        "YEAR_2024_CANDIDATE_MAE": mae24c,
        "N_TRAIN": len(train),
        "N_2023": len(hold_2023),
        "N_2024": len(hold_2024),
        "BASELINE_COLUMNS": list(BASELINE_COLUMNS),
        "CANDIDATE_COLUMNS": list(CANDIDATE_COLUMNS),
        "TRAIN_SD_CONVENTION": TRAIN_SD_CONVENTION,
        "BLOCK_LENGTH_DAYS": BLOCK_LENGTH_DAYS,
        "BOOTSTRAP_REPLICATES": BOOTSTRAP_REPLICATES,
        "RANDOM_SEED": RANDOM_SEED,
        "PREDICTIVE_MODEL_REFIT_IN_BOOTSTRAP": False,
        "PREDICTIVE_BOOTSTRAP_STRATIFIED_BY_YEAR": True,
        "CROSS_YEAR_BOOTSTRAP_BLOCKS_ALLOWED": False,
        "YEAR_SAMPLE_SIZE_PRESERVED_PER_REPLICATE": True,
        "prediction_clipped": False,
        "holdout_refit": False,
    }


def evaluate_from_bars(
    perp: Mapping[int, PerpBar],
    spot: Mapping[int, float],
) -> dict[str, Any]:
    rows = build_eligible_rows(perp, spot)
    return evaluate_from_eligible_rows(rows)


def evaluate_canonical_market_06(*args: Any, **kwargs: Any) -> None:
    refuse_canonical_execution(*args, **kwargs)


def incomplete_report(reason: str) -> dict[str, Any]:
    return {
        "classification": CLASS_INCOMPLETE,
        "reason": reason,
        "scientific_outcomes_inspected": False,
    }


def safe_evaluate_from_eligible_rows(rows: Sequence[EligibleRow]) -> dict[str, Any]:
    try:
        return evaluate_from_eligible_rows(rows)
    except Market06IncompleteExecution as exc:
        return incomplete_report(exc.reason)
