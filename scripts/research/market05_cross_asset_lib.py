"""MARKET-05 exact scientific primitives.

Literal executable rendering of
``docs/research/MARKET_05_CROSS_ASSET_PREREG.json``. Fixture-safe: callers
pass arrays. This module never loads CORE parquet or computes real
development outcomes on import.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Optional, Sequence

import numpy as np

UTC = timezone.utc

RESEARCH_ID = "MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK"
BAR_MS = 60_000
DAY_MS = 86_400_000
LOOKBACK_MS = 24 * 60 * 60 * 1000
HORIZON_MS = 24 * 60 * 60 * 1000
N_FEATURE_BARS = 1440
N_OUTCOME_BARS = 1440
MATERIALITY_THRESHOLD = 0.02
BLOCK_LENGTH = 14
BOOTSTRAP_REPLICATES = 5000
RANDOM_SEED = 2026091905
BOOTSTRAP_KIND = "CIRCULAR_MOVING_BLOCK"
ETH_CONFIRMATION_FORMULA = "BTC_SIDE * Z_ETH"
PRIMARY_OUTCOME = "BTC_DIRECTION_ALIGNED_MAE_24H"
BASELINE_MODEL = "Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H"
CANDIDATE_MODEL = "Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H + ETH_CONFIRMATION"
MODEL_CLASS = "ORDINARY_LEAST_SQUARES_LINEAR_REGRESSION"
DECISION_TIME = "00:00:00 UTC"
DECISION_FREQUENCY = "DAILY"
STD_DDOF = 0

FIRST_USABLE_MS = int(datetime(2020, 1, 3, tzinfo=UTC).timestamp() * 1000)
LAST_USABLE_MS = int(datetime(2024, 12, 31, tzinfo=UTC).timestamp() * 1000)
PROTECTED_OOS_START_MS = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)

FOLD_1_TRAIN = (
    FIRST_USABLE_MS,
    int(datetime(2022, 1, 1, tzinfo=UTC).timestamp() * 1000),
)
FOLD_1_TEST = (
    int(datetime(2022, 1, 1, tzinfo=UTC).timestamp() * 1000),
    int(datetime(2023, 1, 1, tzinfo=UTC).timestamp() * 1000),
)
FOLD_2_TRAIN = (
    FIRST_USABLE_MS,
    int(datetime(2023, 1, 1, tzinfo=UTC).timestamp() * 1000),
)
FOLD_2_TEST = (
    int(datetime(2023, 1, 1, tzinfo=UTC).timestamp() * 1000),
    int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * 1000),
)
FOLD_3_TRAIN = (
    FIRST_USABLE_MS,
    int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * 1000),
)
FOLD_3_TEST = (
    int(datetime(2024, 1, 1, tzinfo=UTC).timestamp() * 1000),
    PROTECTED_OOS_START_MS,
)
FOLDS = {
    "FOLD_1": {"train": FOLD_1_TRAIN, "test": FOLD_1_TEST, "test_year": 2022},
    "FOLD_2": {"train": FOLD_2_TRAIN, "test": FOLD_2_TEST, "test_year": 2023},
    "FOLD_3": {"train": FOLD_3_TRAIN, "test": FOLD_3_TEST, "test_year": 2024},
}

CANDIDATE_COLUMN_NAMES = (
    "INTERCEPT",
    "BTC_SIDE",
    "ABS_Z_BTC",
    "RV_BTC_24H",
    "ETH_CONFIRMATION",
)
BASELINE_COLUMN_NAMES = CANDIDATE_COLUMN_NAMES[:-1]
ETH_CONFIRMATION_COL = 4

CLASS_PROMOTED = "MARKET_05_PROMOTED_HISTORICAL_CANDIDATE"
CLASS_NO_EVIDENCE = "MARKET_05_NO_EVIDENCE"
CLASS_INCOMPLETE = "MARKET_05_INCOMPLETE_EXECUTION"

SPLITMIX64_GOLDEN_INC = 0x9E3779B97F4A7C15
SPLITMIX64_GOLDEN_M1 = 0xBF58476D1CE4E5B9
SPLITMIX64_GOLDEN_M2 = 0x94D049BB133111EB
MASK64 = 0xFFFFFFFFFFFFFFFF


class Market05IntegrityError(RuntimeError):
    """Fail-closed scientific integrity / identifiability error."""


class Market05ProtectedOOSError(RuntimeError):
    """Protected 2025/2026 scientific parse/evaluation attempted."""


class Market05DecisionBoundError(RuntimeError):
    """Decision timestamp outside frozen development execution bounds."""


@dataclass(frozen=True)
class Bar:
    open_time_ms: int
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class EligibleRow:
    t_ms: int
    btc_side: float
    abs_z_btc: float
    rv_btc_24h: float
    eth_confirmation: float
    y: float


class SplitMix64:
    """Version-stable splitmix64. Does not use numpy/global RNG."""

    def __init__(self, seed: int) -> None:
        self.state = int(seed) & MASK64

    def next_u64(self) -> int:
        self.state = (self.state + SPLITMIX64_GOLDEN_INC) & MASK64
        z = self.state
        z = (z ^ (z >> 30)) * SPLITMIX64_GOLDEN_M1 & MASK64
        z = (z ^ (z >> 27)) * SPLITMIX64_GOLDEN_M2 & MASK64
        return z ^ (z >> 31)

    def next_index(self, n: int) -> int:
        if n <= 0:
            raise Market05IntegrityError("RNG index modulus must be positive")
        return self.next_u64() % n


def scientific_rng() -> SplitMix64:
    return SplitMix64(RANDOM_SEED)


def is_utc_midnight(t_ms: int) -> bool:
    return int(t_ms) % DAY_MS == 0


def assert_development_decision_time(t_ms: int) -> None:
    t = int(t_ms)
    if t < FIRST_USABLE_MS or t > LAST_USABLE_MS:
        raise Market05DecisionBoundError(
            f"MARKET_05_DECISION_OUT_OF_BOUNDS:{t}"
        )
    if not is_utc_midnight(t):
        raise Market05DecisionBoundError(
            f"MARKET_05_DECISION_NOT_MIDNIGHT_UTC:{t}"
        )


def assert_no_protected_open_times(open_times_ms: Sequence[int]) -> None:
    for ts in open_times_ms:
        if int(ts) >= PROTECTED_OOS_START_MS:
            raise Market05ProtectedOOSError(
                "MARKET_05_PROTECTED_OOS_SCIENTIFIC_PARSE_FORBIDDEN"
            )


def assert_outcome_window_inside_development(t_ms: int) -> None:
    t = int(t_ms)
    if t + HORIZON_MS > PROTECTED_OOS_START_MS:
        raise Market05DecisionBoundError(
            "MARKET_05_OUTCOME_CROSSES_PROTECTED_OOS"
        )


def bar_end_exclusive_ms(open_time_ms: int) -> int:
    return int(open_time_ms) + BAR_MS


def feature_open_times(t_ms: int) -> list[int]:
    start = int(t_ms) - LOOKBACK_MS
    return [start + i * BAR_MS for i in range(N_FEATURE_BARS)]


def prefix_open_time(t_ms: int) -> int:
    return int(t_ms) - LOOKBACK_MS - BAR_MS


def outcome_open_times(t_ms: int) -> list[int]:
    start = int(t_ms)
    return [start + i * BAR_MS for i in range(N_OUTCOME_BARS)]


def _index_unique_bars(bars: Sequence[Bar]) -> Optional[dict[int, Bar]]:
    out: dict[int, Bar] = {}
    for bar in bars:
        if bar.open_time_ms in out:
            return None
        out[bar.open_time_ms] = bar
    return out


def extract_ordered_bars(
    bars_by_open: Mapping[int, Bar], open_times: Sequence[int]
) -> Optional[list[Bar]]:
    ordered: list[Bar] = []
    for ts in open_times:
        bar = bars_by_open.get(int(ts))
        if bar is None:
            return None
        ordered.append(bar)
    return ordered


def one_minute_log_returns(prefix_close: float, feature_closes: Sequence[float]) -> Optional[np.ndarray]:
    if len(feature_closes) != N_FEATURE_BARS:
        return None
    prev = float(prefix_close)
    out = np.empty(N_FEATURE_BARS, dtype=np.float64)
    for i, close in enumerate(feature_closes):
        cur = float(close)
        if prev <= 0.0 or cur <= 0.0 or not math.isfinite(prev) or not math.isfinite(cur):
            return None
        out[i] = math.log(cur / prev)
        prev = cur
    if not np.isfinite(out).all():
        return None
    return out


def realized_vol(log_returns: Sequence[float]) -> float:
    arr = np.asarray(log_returns, dtype=np.float64)
    return float(np.sqrt(np.sum(np.square(arr))))


def signed_side(value: float) -> float:
    if value > 0.0:
        return 1.0
    if value < 0.0:
        return -1.0
    return 0.0


def direction_aligned_mae(
    btc_side: float, p_btc_t: float, outcome_lows: Sequence[float], outcome_highs: Sequence[float]
) -> Optional[float]:
    if p_btc_t <= 0.0 or not math.isfinite(p_btc_t):
        return None
    if len(outcome_lows) != N_OUTCOME_BARS or len(outcome_highs) != N_OUTCOME_BARS:
        return None
    lows = np.asarray(outcome_lows, dtype=np.float64)
    highs = np.asarray(outcome_highs, dtype=np.float64)
    if not np.isfinite(lows).all() or not np.isfinite(highs).all():
        return None
    if np.any(lows <= 0.0) or np.any(highs <= 0.0):
        return None
    if btc_side > 0.0:
        adverse = float(np.min(lows))
        y = math.log(p_btc_t / adverse)
    elif btc_side < 0.0:
        adverse = float(np.max(highs))
        y = math.log(adverse / p_btc_t)
    else:
        return None
    if not math.isfinite(y):
        return None
    return float(max(0.0, y))


def window_complete(
    bars: Sequence[Bar],
    prefix: Optional[Bar],
    t_ms: int,
    *,
    require_outcome: bool,
) -> bool:
    indexed = _index_unique_bars(bars)
    if indexed is None or prefix is None:
        return False
    if prefix.open_time_ms != prefix_open_time(t_ms):
        return False
    if bar_end_exclusive_ms(prefix.open_time_ms) != int(t_ms) - LOOKBACK_MS:
        return False
    feat = extract_ordered_bars(indexed, feature_open_times(t_ms))
    if feat is None or len(feat) != N_FEATURE_BARS:
        return False
    last_feat = feat[-1]
    if bar_end_exclusive_ms(last_feat.open_time_ms) != int(t_ms):
        return False
    if feat[0].open_time_ms != int(t_ms) - LOOKBACK_MS:
        return False
    if require_outcome:
        out = extract_ordered_bars(indexed, outcome_open_times(t_ms))
        if out is None or len(out) != N_OUTCOME_BARS:
            return False
        if out[0].open_time_ms != int(t_ms):
            return False
    return True


def build_eligible_row(
    t_ms: int,
    btc_bars: Sequence[Bar],
    btc_prefix: Bar,
    eth_bars: Sequence[Bar],
    eth_prefix: Bar,
) -> Optional[EligibleRow]:
    """Shared eligible-row constructor. Missing/duplicate/zero-RV/zero-R
    invalidates the row for BOTH models."""
    assert_development_decision_time(t_ms)
    assert_outcome_window_inside_development(t_ms)
    all_opens = (
        [btc_prefix.open_time_ms, eth_prefix.open_time_ms]
        + [b.open_time_ms for b in btc_bars]
        + [b.open_time_ms for b in eth_bars]
    )
    assert_no_protected_open_times(all_opens)
    if not window_complete(btc_bars, btc_prefix, t_ms, require_outcome=True):
        return None
    if not window_complete(eth_bars, eth_prefix, t_ms, require_outcome=False):
        return None
    btc_index = _index_unique_bars(btc_bars)
    eth_index = _index_unique_bars(eth_bars)
    if btc_index is None or eth_index is None:
        return None
    btc_feat = extract_ordered_bars(btc_index, feature_open_times(t_ms))
    eth_feat = extract_ordered_bars(eth_index, feature_open_times(t_ms))
    btc_out = extract_ordered_bars(btc_index, outcome_open_times(t_ms))
    if btc_feat is None or eth_feat is None or btc_out is None:
        return None
    p_btc_t = float(btc_feat[-1].close)
    p_btc_tm = float(btc_prefix.close)
    p_eth_t = float(eth_feat[-1].close)
    p_eth_tm = float(eth_prefix.close)
    if min(p_btc_t, p_btc_tm, p_eth_t, p_eth_tm) <= 0.0:
        return None
    r_btc = math.log(p_btc_t / p_btc_tm)
    r_eth = math.log(p_eth_t / p_eth_tm)
    if not math.isfinite(r_btc) or not math.isfinite(r_eth):
        return None
    if r_btc == 0.0:
        return None
    btc_rets = one_minute_log_returns(p_btc_tm, [b.close for b in btc_feat])
    eth_rets = one_minute_log_returns(p_eth_tm, [b.close for b in eth_feat])
    if btc_rets is None or eth_rets is None:
        return None
    rv_btc = realized_vol(btc_rets)
    rv_eth = realized_vol(eth_rets)
    if rv_btc <= 0.0 or rv_eth <= 0.0 or not math.isfinite(rv_btc) or not math.isfinite(rv_eth):
        return None
    z_btc = r_btc / rv_btc
    z_eth = r_eth / rv_eth
    if not math.isfinite(z_btc) or not math.isfinite(z_eth):
        return None
    btc_side = signed_side(r_btc)
    y = direction_aligned_mae(
        btc_side,
        p_btc_t,
        [b.low for b in btc_out],
        [b.high for b in btc_out],
    )
    if y is None:
        return None
    return EligibleRow(
        t_ms=int(t_ms),
        btc_side=float(btc_side),
        abs_z_btc=float(abs(z_btc)),
        rv_btc_24h=float(rv_btc),
        eth_confirmation=float(btc_side * z_eth),
        y=float(y),
    )


def in_half_open(t_ms: int, bounds: tuple[int, int]) -> bool:
    lo, hi = bounds
    return lo <= int(t_ms) < hi


def heldout_fold_name(t_ms: int) -> Optional[str]:
    for name, spec in FOLDS.items():
        if in_half_open(t_ms, spec["test"]):
            return name
    return None


def train_fold_names(t_ms: int) -> list[str]:
    return [name for name, spec in FOLDS.items() if in_half_open(t_ms, spec["train"])]


def utc_year(t_ms: int) -> int:
    return datetime.fromtimestamp(int(t_ms) / 1000.0, tz=UTC).year


def training_mean_sd(values: Sequence[float]) -> tuple[float, float]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        raise Market05IntegrityError("empty training standardizer")
    mean = float(arr.mean())
    sd = float(arr.std(ddof=STD_DDOF))
    if not math.isfinite(mean) or not math.isfinite(sd) or sd == 0.0:
        raise Market05IntegrityError("zero training sd")
    return mean, sd


def apply_standardization(values: Sequence[float], mean: float, sd: float) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    return (arr - mean) / sd


def design_baseline(rows: Sequence[EligibleRow], stats: Mapping[str, tuple[float, float]]) -> np.ndarray:
    n = len(rows)
    x = np.ones((n, 4), dtype=np.float64)
    x[:, 1] = np.fromiter((r.btc_side for r in rows), dtype=np.float64, count=n)
    x[:, 2] = apply_standardization([r.abs_z_btc for r in rows], *stats["ABS_Z_BTC"])
    x[:, 3] = apply_standardization([r.rv_btc_24h for r in rows], *stats["RV_BTC_24H"])
    return x


def design_candidate(rows: Sequence[EligibleRow], stats: Mapping[str, tuple[float, float]]) -> np.ndarray:
    base = design_baseline(rows, stats)
    eth = apply_standardization(
        [r.eth_confirmation for r in rows], *stats["ETH_CONFIRMATION"]
    )
    return np.column_stack([base, eth])


def fit_standardizer(rows: Sequence[EligibleRow], *, include_eth: bool) -> dict[str, tuple[float, float]]:
    stats = {
        "ABS_Z_BTC": training_mean_sd([r.abs_z_btc for r in rows]),
        "RV_BTC_24H": training_mean_sd([r.rv_btc_24h for r in rows]),
    }
    if include_eth:
        stats["ETH_CONFIRMATION"] = training_mean_sd([r.eth_confirmation for r in rows])
    return stats


def _assert_finite_rank(x: np.ndarray, y: np.ndarray, expected_cols: int) -> None:
    if x.shape[1] != expected_cols:
        raise Market05IntegrityError("unexpected design width")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise Market05IntegrityError("non-finite design values")
    rank = int(np.linalg.matrix_rank(x))
    if rank < expected_cols:
        raise Market05IntegrityError("rank deficiency")


def eth_collinear_with_baseline(x_candidate: np.ndarray) -> bool:
    base = x_candidate[:, :4]
    eth = x_candidate[:, 4]
    try:
        coef, *_ = np.linalg.lstsq(base, eth, rcond=None)
        fitted = base @ coef
        resid = eth - fitted
        scale = float(np.linalg.norm(eth))
        if scale == 0.0:
            return True
        return float(np.linalg.norm(resid) / scale) <= 1e-12
    except np.linalg.LinAlgError:
        return True


def fit_ols(x: np.ndarray, y: np.ndarray, expected_cols: int) -> np.ndarray:
    _assert_finite_rank(x, y, expected_cols)
    if expected_cols == 5 and eth_collinear_with_baseline(x):
        raise Market05IntegrityError("ETH_CONFIRMATION collinear with baseline")
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    if not np.isfinite(beta).all():
        raise Market05IntegrityError("non-finite OLS coefficients")
    return np.asarray(beta, dtype=np.float64)


def predict_ols(x: np.ndarray, beta: np.ndarray) -> np.ndarray:
    pred = x @ beta
    return np.asarray(pred, dtype=np.float64)


def mean_absolute_error(y: Sequence[float], pred: Sequence[float]) -> float:
    y_arr = np.asarray(y, dtype=np.float64)
    p_arr = np.asarray(pred, dtype=np.float64)
    if y_arr.size == 0 or y_arr.size != p_arr.size:
        raise Market05IntegrityError("MAE support mismatch")
    return float(np.mean(np.abs(y_arr - p_arr)))


def relative_mae_improvement(mae_baseline: float, mae_candidate: float) -> float:
    if not math.isfinite(mae_baseline) or mae_baseline == 0.0:
        raise Market05IntegrityError("invalid MAE baseline denominator")
    if not math.isfinite(mae_candidate):
        raise Market05IntegrityError("non-finite MAE candidate")
    return float(1.0 - (mae_candidate / mae_baseline))


def circular_moving_block_indices(
    n: int, block_length: int, rng: SplitMix64
) -> np.ndarray:
    if n <= 0:
        raise Market05IntegrityError("empty bootstrap sample")
    if block_length <= 0:
        raise Market05IntegrityError("block length must be positive")
    out = np.empty(n, dtype=np.int64)
    filled = 0
    while filled < n:
        start = rng.next_index(n)
        take = min(block_length, n - filled)
        for i in range(take):
            out[filled + i] = (start + i) % n
        filled += take
    return out


def percentile_2p5_97p5(values: Sequence[float]) -> tuple[float, float]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        raise Market05IntegrityError("empty percentile sample")
    lo = float(np.percentile(arr, 2.5, method="linear"))
    hi = float(np.percentile(arr, 97.5, method="linear"))
    return lo, hi


def predictive_relative_mae_bootstrap(
    abs_err_baseline: Sequence[float],
    abs_err_candidate: Sequence[float],
    *,
    block_length: int,
    replicates: int,
    rng: SplitMix64,
    refit: bool = False,
) -> np.ndarray:
    if refit:
        raise Market05IntegrityError("predictive bootstrap must not refit")
    b = np.asarray(abs_err_baseline, dtype=np.float64)
    c = np.asarray(abs_err_candidate, dtype=np.float64)
    if b.size == 0 or b.size != c.size:
        raise Market05IntegrityError("predictive bootstrap support mismatch")
    out = np.empty(int(replicates), dtype=np.float64)
    n = int(b.size)
    for i in range(int(replicates)):
        idx = circular_moving_block_indices(n, block_length, rng)
        mae_b = float(np.mean(b[idx]))
        mae_c = float(np.mean(c[idx]))
        out[i] = relative_mae_improvement(mae_b, mae_c)
    return out


def coefficient_bootstrap(
    rows: Sequence[EligibleRow],
    *,
    block_length: int,
    replicates: int,
    rng: SplitMix64,
    refit: bool = True,
) -> np.ndarray:
    if not refit:
        raise Market05IntegrityError("coefficient bootstrap must refit")
    n = len(rows)
    if n == 0:
        raise Market05IntegrityError("empty coefficient bootstrap sample")
    out = np.empty(int(replicates), dtype=np.float64)
    y_all = np.fromiter((r.y for r in rows), dtype=np.float64, count=n)
    for i in range(int(replicates)):
        idx = circular_moving_block_indices(n, block_length, rng)
        sample = [rows[int(j)] for j in idx]
        try:
            stats = fit_standardizer(sample, include_eth=True)
            x = design_candidate(sample, stats)
            y = y_all[idx]
            beta = fit_ols(x, y, expected_cols=5)
        except Market05IntegrityError as exc:
            raise Market05IntegrityError(
                "MARKET_05_INCOMPLETE_EXECUTION:invalid_coefficient_bootstrap_replicate"
            ) from exc
        out[i] = float(beta[ETH_CONFIRMATION_COL])
    return out


def classify(
    *,
    beta_eth_confirmation: float,
    beta_ci_upper: float,
    relative_mae_improvement_value: float,
    relative_mae_ci_lower: float,
    year_relative_mae: Mapping[int, float],
    integrity_ok: bool,
) -> tuple[str, dict[str, bool]]:
    if not integrity_ok:
        return CLASS_INCOMPLETE, {
            "GATE_1_DIRECTION": False,
            "GATE_2_DIRECTION_UNCERTAINTY": False,
            "GATE_3_PREDICTIVE_SIGN": False,
            "GATE_4_PREDICTIVE_UNCERTAINTY": False,
            "GATE_5_MATERIALITY": False,
            "GATE_6_TEMPORAL_STABILITY": False,
        }
    required_years = (2022, 2023, 2024)
    if any(year not in year_relative_mae for year in required_years):
        return CLASS_INCOMPLETE, {
            "GATE_1_DIRECTION": False,
            "GATE_2_DIRECTION_UNCERTAINTY": False,
            "GATE_3_PREDICTIVE_SIGN": False,
            "GATE_4_PREDICTIVE_UNCERTAINTY": False,
            "GATE_5_MATERIALITY": False,
            "GATE_6_TEMPORAL_STABILITY": False,
        }
    g1 = bool(beta_eth_confirmation < 0.0)
    g2 = bool(beta_ci_upper < 0.0)
    g3 = bool(relative_mae_improvement_value > 0.0)
    g4 = bool(relative_mae_ci_lower > 0.0)
    g5 = bool(relative_mae_improvement_value >= MATERIALITY_THRESHOLD)
    year_vals = [float(year_relative_mae[year]) for year in required_years]
    positive_years = sum(1 for value in year_vals if value > 0.0)
    materially_bad = any(value <= -MATERIALITY_THRESHOLD for value in year_vals)
    g6 = bool(positive_years >= 2 and not materially_bad)
    gates = {
        "GATE_1_DIRECTION": g1,
        "GATE_2_DIRECTION_UNCERTAINTY": g2,
        "GATE_3_PREDICTIVE_SIGN": g3,
        "GATE_4_PREDICTIVE_UNCERTAINTY": g4,
        "GATE_5_MATERIALITY": g5,
        "GATE_6_TEMPORAL_STABILITY": g6,
    }
    if all(gates.values()):
        return CLASS_PROMOTED, gates
    return CLASS_NO_EVIDENCE, gates


def evaluate_prepared_rows(
    rows: Sequence[EligibleRow],
    *,
    predictive_replicates: int = BOOTSTRAP_REPLICATES,
    coefficient_replicates: int = BOOTSTRAP_REPLICATES,
    block_length: int = BLOCK_LENGTH,
    rng: Optional[SplitMix64] = None,
) -> dict:
    """Chronological MARKET-05 evaluation on already-eligible rows.

    Does not load real datasets. Used by synthetic tests and, after ARM,
    by the authorized execution path with rows constructed elsewhere.
    """
    for row in rows:
        assert_development_decision_time(row.t_ms)
        assert_outcome_window_inside_development(row.t_ms)
    rng = rng or scientific_rng()
    fold_payload = []
    held_y: list[float] = []
    held_pred_b: list[float] = []
    held_pred_c: list[float] = []
    held_err_b: list[float] = []
    held_err_c: list[float] = []
    held_years: list[int] = []
    for name, spec in FOLDS.items():
        train = [r for r in rows if in_half_open(r.t_ms, spec["train"])]
        test = [r for r in rows if in_half_open(r.t_ms, spec["test"])]
        if not train or not test:
            raise Market05IntegrityError(f"empty fold support:{name}")
        stats = fit_standardizer(train, include_eth=True)
        x_b_train = design_baseline(train, stats)
        x_c_train = design_candidate(train, stats)
        y_train = np.fromiter((r.y for r in train), dtype=np.float64, count=len(train))
        beta_b = fit_ols(x_b_train, y_train, expected_cols=4)
        beta_c = fit_ols(x_c_train, y_train, expected_cols=5)
        x_b_test = design_baseline(test, stats)
        x_c_test = design_candidate(test, stats)
        y_test = np.fromiter((r.y for r in test), dtype=np.float64, count=len(test))
        pred_b = predict_ols(x_b_test, beta_b)
        pred_c = predict_ols(x_c_test, beta_c)
        mae_b = mean_absolute_error(y_test, pred_b)
        mae_c = mean_absolute_error(y_test, pred_c)
        fold_payload.append(
            {
                "name": name,
                "test_year": spec["test_year"],
                "train_n": len(train),
                "test_n": len(test),
                "MAE_BASELINE": mae_b,
                "MAE_CANDIDATE": mae_c,
            }
        )
        held_y.extend(y_test.tolist())
        held_pred_b.extend(pred_b.tolist())
        held_pred_c.extend(pred_c.tolist())
        held_err_b.extend(np.abs(y_test - pred_b).tolist())
        held_err_c.extend(np.abs(y_test - pred_c).tolist())
        held_years.extend(utc_year(r.t_ms) for r in test)
    pooled_mae_b = mean_absolute_error(held_y, held_pred_b)
    pooled_mae_c = mean_absolute_error(held_y, held_pred_c)
    rel = relative_mae_improvement(pooled_mae_b, pooled_mae_c)
    year_rel = {}
    for year in (2022, 2023, 2024):
        mask = [i for i, value in enumerate(held_years) if value == year]
        if not mask:
            raise Market05IntegrityError(f"missing held-out year:{year}")
        y_year = [held_y[i] for i in mask]
        pb = [held_pred_b[i] for i in mask]
        pc = [held_pred_c[i] for i in mask]
        year_rel[year] = relative_mae_improvement(
            mean_absolute_error(y_year, pb),
            mean_absolute_error(y_year, pc),
        )
    pred_reps = predictive_relative_mae_bootstrap(
        held_err_b,
        held_err_c,
        block_length=block_length,
        replicates=predictive_replicates,
        rng=rng,
        refit=False,
    )
    rel_lo, rel_hi = percentile_2p5_97p5(pred_reps)
    dev_rows = [r for r in rows if FIRST_USABLE_MS <= r.t_ms < PROTECTED_OOS_START_MS]
    if not dev_rows:
        raise Market05IntegrityError("empty full-development sample")
    dev_stats = fit_standardizer(dev_rows, include_eth=True)
    x_dev = design_candidate(dev_rows, dev_stats)
    y_dev = np.fromiter((r.y for r in dev_rows), dtype=np.float64, count=len(dev_rows))
    beta_dev = fit_ols(x_dev, y_dev, expected_cols=5)
    beta_eth = float(beta_dev[ETH_CONFIRMATION_COL])
    coef_reps = coefficient_bootstrap(
        dev_rows,
        block_length=block_length,
        replicates=coefficient_replicates,
        rng=rng,
        refit=True,
    )
    beta_lo, beta_hi = percentile_2p5_97p5(coef_reps)
    classification, gates = classify(
        beta_eth_confirmation=beta_eth,
        beta_ci_upper=beta_hi,
        relative_mae_improvement_value=rel,
        relative_mae_ci_lower=rel_lo,
        year_relative_mae=year_rel,
        integrity_ok=True,
    )
    return {
        "research_id": RESEARCH_ID,
        "folds": fold_payload,
        "POOLED_MAE_BASELINE": pooled_mae_b,
        "POOLED_MAE_CANDIDATE": pooled_mae_c,
        "RELATIVE_MAE_IMPROVEMENT": rel,
        "YEAR_RELATIVE_MAE_IMPROVEMENT": year_rel,
        "BETA_ETH_CONFIRMATION": beta_eth,
        "BETA_ETH_CONFIRMATION_CI": [beta_lo, beta_hi],
        "RELATIVE_MAE_IMPROVEMENT_CI": [rel_lo, rel_hi],
        "gates": gates,
        "classification": classification,
        "candidate_column_names": list(CANDIDATE_COLUMN_NAMES),
        "predictive_bootstrap_refit": False,
        "coefficient_bootstrap_refit": True,
        "bootstrap_kind": BOOTSTRAP_KIND,
        "bootstrap_block_length": block_length,
        "bootstrap_replicates_predictive": predictive_replicates,
        "bootstrap_replicates_coefficient": coefficient_replicates,
        "random_seed": RANDOM_SEED,
    }


RESULT_SCHEMA_KEYS = (
    "research_id",
    "prereg_md_sha256",
    "prereg_json_sha256",
    # Commit provenance and per-file identity are SEPARATE fields; the
    # commit fields carry exact git SHAs and are never overloaded with a
    # hash map (schema 1.1.0).
    "implementation_head",
    "implementation_tree",
    "scientific_implementation_hashes",
    "btc_dataset_id",
    "btc_snapshot_id",
    "eth_dataset_id",
    "eth_snapshot_id",
    "run_identity",
    "row_counts",
    "exclusion_counts",
    "fold_counts",
    "coefficients",
    "bootstrap",
    "bootstrap_cis",
    "maes",
    "year_metrics",
    "gates",
    "classification",
    "protected_oos_touched",
    "scientific_consumed",
)


def result_schema() -> dict:
    return {key: None for key in RESULT_SCHEMA_KEYS}


def instantiate_scientific_result(payload: Mapping) -> dict:
    """Build a RESULT payload under an authenticated canonical execution.

    Lifecycle-gated, not permanently forbidden: refuses while unarmed and
    permits once an authenticated ARM + RESERVATION authorizes exactly one
    unconsumed canonical execution. The authority decision is delegated so
    this module holds no lifecycle state of its own.

    Every RESULT_SCHEMA_KEYS field must be supplied by the caller and no
    extra field is accepted, so a RESULT cannot self-attest authority
    fields that the authority layer did not verify.
    """
    from scripts.research.market05_cross_asset_authority import (
        Market05AuthorityError,
        Market05ExecutionNotAuthorized,
        refuse_scientific_result_instantiation,
    )

    try:
        refuse_scientific_result_instantiation()
    except (Market05ExecutionNotAuthorized, Market05AuthorityError) as exc:
        raise Market05IntegrityError(str(exc)) from exc

    provided = set(payload)
    expected = set(RESULT_SCHEMA_KEYS)
    if provided != expected:
        missing = sorted(expected - provided)
        extra = sorted(provided - expected)
        raise Market05IntegrityError(
            f"MARKET_05_RESULT_SCHEMA_MISMATCH:missing={missing}:extra={extra}"
        )
    return {key: payload[key] for key in RESULT_SCHEMA_KEYS}
