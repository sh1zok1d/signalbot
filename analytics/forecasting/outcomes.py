"""
Deterministic Stage 2 shadow forecast OUTCOME evaluator (15m / 1h / 4h).

Given one immutable `ForecastPrediction`, an explicit evaluation exchange, and the
complete future 1-minute price window, this computes deterministic horizon outcome
metrics (raw market return, peak/trough, direction-aware directional return /
MFE / MAE). Pure only: no DB, network, clock, env, filesystem, or ML — same inputs
always produce an equal result.

Window semantics (BTCUSDT / perp / 5m; horizons 15m/1h/4h): `bucket_ts` is the
OPEN of the closed 5m bucket that produced the prediction, so
`evaluation_start_ts = bucket_ts + 5m`, `evaluation_end_ts = start + horizon`, and
future 1m bars are `ts in [start, end)`. `klines_1m.ts` is a candle OPEN, so the
horizon target price is the CLOSE of the bar at `target_bar_ts = end - 1m`.

Missing future bars are NOT malformed input: they yield an INCOMPLETE evaluation
(no persisted row), never an error.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from collections.abc import Sequence as _AbcSequence

from symbols.registry import ACTIVE_EXCHANGES

from .models import LONG, NEUTRAL, SHORT
from .persistence import ForecastPrediction

# ---- constants -------------------------------------------------------------
OUTCOME_COMPLETE = "COMPLETE"
OUTCOME_INCOMPLETE = "INCOMPLETE"
OUTCOME_STATUSES = (OUTCOME_COMPLETE, OUTCOME_INCOMPLETE)

OUTCOME_HORIZONS = ("15m", "1h", "4h")
OUTCOME_HORIZON_MINUTES = MappingProxyType({"15m": 15, "1h": 60, "4h": 240})

DEFAULT_OUTCOME_VERSION = "forecast-outcome-v0.1.0"
EVALUATION_PRICE_SOURCE = "klines_1m"

_SUPPORTED_SYMBOL = "BTCUSDT"
_SUPPORTED_MARKET_TYPE = "perp"
_SUPPORTED_TIMEFRAME = "5m"
_PREDICTION_TIMEFRAME_MINUTES = 5
_METRIC_TOL = dict(rel_tol=1e-12, abs_tol=1e-12)

_HEX16 = re.compile(r"[0-9a-f]{16}")
_HEX64 = re.compile(r"[0-9a-f]{64}")


class ForecastOutcomeInputError(ValueError):
    """Malformed outcome model / argument / bar, an identity-version mismatch, or
    an unsupported evaluation request. Missing future bars are NOT this error —
    they produce an INCOMPLETE result."""


# ---- small validators (all raise ForecastOutcomeInputError) ----------------
def _finite(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ForecastOutcomeInputError(f"{name} must be a real number, got {type(value).__name__}")
    v = float(value)
    if not math.isfinite(v):
        raise ForecastOutcomeInputError(f"{name} must be finite, got {value!r}")
    return v


def _positive(value, name: str) -> float:
    v = _finite(value, name)
    if not v > 0:
        raise ForecastOutcomeInputError(f"{name} must be > 0, got {v!r}")
    return v


def _in_range(value, name: str, low: float, high: float) -> float:
    v = _finite(value, name)
    if not (low <= v <= high):
        raise ForecastOutcomeInputError(f"{name} must be in [{low}, {high}], got {v!r}")
    return v


def _nonblank(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ForecastOutcomeInputError(f"{name} must be a non-empty string")
    return value


def _utc(dt, name: str) -> datetime:
    if not isinstance(dt, datetime):
        raise ForecastOutcomeInputError(f"{name} must be a datetime, got {type(dt).__name__}")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ForecastOutcomeInputError(f"{name} must be timezone-aware")
    if dt.utcoffset() != timedelta(0):
        raise ForecastOutcomeInputError(f"{name} must be UTC (offset 0), got {dt.utcoffset()}")
    return dt


def _whole_minute(dt, name: str) -> datetime:
    _utc(dt, name)
    if dt.second != 0 or dt.microsecond != 0:
        raise ForecastOutcomeInputError(f"{name} must be on a whole minute")
    return dt


def _5m_aligned(dt, name: str) -> datetime:
    _whole_minute(dt, name)
    if dt.minute % _PREDICTION_TIMEFRAME_MINUTES != 0:
        raise ForecastOutcomeInputError(f"{name} must be aligned to the 5m grid")
    return dt


def _active_exchange(value, name: str) -> str:
    if not isinstance(value, str) or value not in ACTIVE_EXCHANGES:
        raise ForecastOutcomeInputError(
            f"{name} must be an active exchange {list(ACTIVE_EXCHANGES)}, got {value!r}")
    return value


def _validate_scope_identity(m) -> None:
    """BTCUSDT/perp/5m identity + version rules shared by ForecastOutcome."""
    if m.symbol != _SUPPORTED_SYMBOL:
        raise ForecastOutcomeInputError(f"unsupported symbol {m.symbol!r} (scope {_SUPPORTED_SYMBOL})")
    if m.market_type != _SUPPORTED_MARKET_TYPE:
        raise ForecastOutcomeInputError(
            f"unsupported market_type {m.market_type!r} (scope {_SUPPORTED_MARKET_TYPE})")
    if m.timeframe != _SUPPORTED_TIMEFRAME:
        raise ForecastOutcomeInputError(f"unsupported timeframe {m.timeframe!r} (scope {_SUPPORTED_TIMEFRAME})")
    _5m_aligned(m.bucket_ts, "bucket_ts")
    if not isinstance(m.feature_schema_version, int) or isinstance(m.feature_schema_version, bool) \
            or m.feature_schema_version <= 0:
        raise ForecastOutcomeInputError("feature_schema_version must be an int > 0")
    if not isinstance(m.calculation_version, str) or not _HEX16.fullmatch(m.calculation_version):
        raise ForecastOutcomeInputError("calculation_version must be exactly 16 lowercase hex chars")
    _nonblank(m.rule_version, "rule_version")
    _nonblank(m.outcome_version, "outcome_version")
    if not isinstance(m.config_hash, str) or not _HEX64.fullmatch(m.config_hash):
        raise ForecastOutcomeInputError("config_hash must be exactly 64 lowercase hex chars")
    _nonblank(m.config_version, "config_version")
    _nonblank(m.code_version, "code_version")


def _expected_reference_source(evaluation_exchange: str) -> str:
    return f"{evaluation_exchange}_close_5m"


# ---- price bar -------------------------------------------------------------
@dataclass(frozen=True)
class OutcomePriceBar:
    exchange: str
    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self):
        _active_exchange(self.exchange, "exchange")
        if self.symbol != _SUPPORTED_SYMBOL:
            raise ForecastOutcomeInputError(
                f"symbol must be {_SUPPORTED_SYMBOL}, got {self.symbol!r}")
        _whole_minute(self.ts, "ts")
        o = _positive(self.open, "open")
        h = _positive(self.high, "high")
        low = _positive(self.low, "low")
        c = _positive(self.close, "close")
        if not (h >= low):
            raise ForecastOutcomeInputError("high must be >= low")
        if not (low <= o <= h):
            raise ForecastOutcomeInputError("open must be within [low, high]")
        if not (low <= c <= h):
            raise ForecastOutcomeInputError("close must be within [low, high]")


# ---- window ----------------------------------------------------------------
@dataclass(frozen=True)
class ForecastOutcomeWindow:
    horizon: str
    outcome_version: str
    evaluation_exchange: str
    evaluation_price_source: str

    evaluation_start_ts: datetime
    evaluation_end_ts: datetime
    target_bar_ts: datetime
    bars_expected: int

    def __post_init__(self):
        if self.horizon not in OUTCOME_HORIZONS:
            raise ForecastOutcomeInputError(
                f"horizon must be one of {list(OUTCOME_HORIZONS)}, got {self.horizon!r}")
        _nonblank(self.outcome_version, "outcome_version")
        _active_exchange(self.evaluation_exchange, "evaluation_exchange")
        if self.evaluation_price_source != EVALUATION_PRICE_SOURCE:
            raise ForecastOutcomeInputError(
                f"evaluation_price_source must be {EVALUATION_PRICE_SOURCE!r}")
        _whole_minute(self.evaluation_start_ts, "evaluation_start_ts")
        _whole_minute(self.evaluation_end_ts, "evaluation_end_ts")
        _whole_minute(self.target_bar_ts, "target_bar_ts")
        expected = OUTCOME_HORIZON_MINUTES[self.horizon]
        if type(self.bars_expected) is not int:      # exact int: reject bool and 15.0
            raise ForecastOutcomeInputError(
                f"bars_expected must be an int, got {type(self.bars_expected).__name__}")
        if self.bars_expected != expected:
            raise ForecastOutcomeInputError(
                f"bars_expected must be {expected} for {self.horizon}, got {self.bars_expected!r}")
        if self.evaluation_end_ts != self.evaluation_start_ts + timedelta(minutes=self.bars_expected):
            raise ForecastOutcomeInputError("evaluation_end_ts must be start + bars_expected minutes")
        if self.target_bar_ts != self.evaluation_end_ts - timedelta(minutes=1):
            raise ForecastOutcomeInputError("target_bar_ts must be evaluation_end_ts - 1 minute")


def build_forecast_outcome_window(
    prediction: ForecastPrediction,
    *,
    horizon: str,
    evaluation_exchange: str,
    outcome_version: str = DEFAULT_OUTCOME_VERSION,
) -> ForecastOutcomeWindow:
    """Pure builder for one horizon's evaluation window. See module docstring for
    the exact 5m-bucket -> [start, end) semantics."""
    if type(prediction) is not ForecastPrediction:
        raise ForecastOutcomeInputError(
            f"prediction must be a ForecastPrediction, got {type(prediction).__name__}")
    if horizon not in OUTCOME_HORIZONS:
        raise ForecastOutcomeInputError(
            f"horizon must be one of {list(OUTCOME_HORIZONS)}, got {horizon!r}")
    if horizon not in prediction.horizon_set:
        raise ForecastOutcomeInputError(
            f"horizon {horizon!r} is not in prediction.horizon_set {list(prediction.horizon_set)}")
    _active_exchange(evaluation_exchange, "evaluation_exchange")
    _nonblank(outcome_version, "outcome_version")
    # V0 source-alignment: the reference price must be that exchange's 5m close.
    expected_src = _expected_reference_source(evaluation_exchange)
    if prediction.reference_price_source != expected_src:
        raise ForecastOutcomeInputError(
            f"reference_price_source {prediction.reference_price_source!r} must equal "
            f"{expected_src!r} for evaluation_exchange {evaluation_exchange!r}")

    bars_expected = OUTCOME_HORIZON_MINUTES[horizon]
    start = prediction.bucket_ts + timedelta(minutes=_PREDICTION_TIMEFRAME_MINUTES)
    end = start + timedelta(minutes=bars_expected)
    target_bar_ts = end - timedelta(minutes=1)
    return ForecastOutcomeWindow(
        horizon=horizon, outcome_version=outcome_version,
        evaluation_exchange=evaluation_exchange,
        evaluation_price_source=EVALUATION_PRICE_SOURCE,
        evaluation_start_ts=start, evaluation_end_ts=end,
        target_bar_ts=target_bar_ts, bars_expected=bars_expected)


# ---- persisted outcome -----------------------------------------------------
@dataclass(frozen=True)
class ForecastOutcome:
    symbol: str
    market_type: str
    timeframe: str
    bucket_ts: datetime

    feature_schema_version: int
    calculation_version: str
    rule_version: str

    horizon: str
    outcome_version: str

    direction: str
    prediction_confidence: float
    prediction_final_score: float

    reference_price: float
    reference_price_source: str

    evaluation_exchange: str
    evaluation_price_source: str

    evaluation_start_ts: datetime
    evaluation_end_ts: datetime
    target_bar_ts: datetime

    bars_expected: int
    bars_present: int

    target_close_price: float
    window_high_price: float
    window_low_price: float

    market_return_pct: float
    peak_return_pct: float
    trough_return_pct: float

    directional_return_pct: Optional[float]
    mfe_pct: Optional[float]
    mae_pct: Optional[float]

    config_hash: str
    config_version: str
    code_version: str

    def __post_init__(self):
        _validate_scope_identity(self)

        if self.direction not in (LONG, SHORT, NEUTRAL):
            raise ForecastOutcomeInputError(f"invalid direction {self.direction!r}")
        _in_range(self.prediction_confidence, "prediction_confidence", 0.0, 1.0)
        _in_range(self.prediction_final_score, "prediction_final_score", -1.0, 1.0)

        ref = _positive(self.reference_price, "reference_price")
        _nonblank(self.reference_price_source, "reference_price_source")
        _active_exchange(self.evaluation_exchange, "evaluation_exchange")
        if self.evaluation_price_source != EVALUATION_PRICE_SOURCE:
            raise ForecastOutcomeInputError(f"evaluation_price_source must be {EVALUATION_PRICE_SOURCE!r}")
        if self.reference_price_source != _expected_reference_source(self.evaluation_exchange):
            raise ForecastOutcomeInputError(
                "reference_price_source must equal "
                f"{_expected_reference_source(self.evaluation_exchange)!r}")

        # window timing + bars_expected reuse ForecastOutcomeWindow validation
        ForecastOutcomeWindow(
            horizon=self.horizon, outcome_version=self.outcome_version,
            evaluation_exchange=self.evaluation_exchange,
            evaluation_price_source=self.evaluation_price_source,
            evaluation_start_ts=self.evaluation_start_ts,
            evaluation_end_ts=self.evaluation_end_ts, target_bar_ts=self.target_bar_ts,
            bars_expected=self.bars_expected)
        # bind the (already self-consistent) window to this prediction's bucket, so a
        # directly constructed/persisted outcome cannot carry a valid window that
        # belongs to a different point in time than bucket_ts.
        if self.evaluation_start_ts != self.bucket_ts + timedelta(minutes=_PREDICTION_TIMEFRAME_MINUTES):
            raise ForecastOutcomeInputError(
                "evaluation_start_ts must equal bucket_ts + 5 minutes")
        if not isinstance(self.bars_present, int) or isinstance(self.bars_present, bool):
            raise ForecastOutcomeInputError("bars_present must be an int")
        if self.bars_present <= 0:
            raise ForecastOutcomeInputError("bars_present must be > 0")
        if self.bars_present != self.bars_expected:
            raise ForecastOutcomeInputError("bars_present must equal bars_expected for a stored outcome")

        target = _positive(self.target_close_price, "target_close_price")
        high = _positive(self.window_high_price, "window_high_price")
        low = _positive(self.window_low_price, "window_low_price")
        if not (low <= target <= high):
            raise ForecastOutcomeInputError("window_low <= target_close <= window_high required")

        mret = _finite(self.market_return_pct, "market_return_pct")
        peak = _finite(self.peak_return_pct, "peak_return_pct")
        trough = _finite(self.trough_return_pct, "trough_return_pct")
        exp_mret = ((target / ref) - 1.0) * 100.0
        exp_peak = ((high / ref) - 1.0) * 100.0
        exp_trough = ((low / ref) - 1.0) * 100.0
        if not math.isclose(mret, exp_mret, **_METRIC_TOL):
            raise ForecastOutcomeInputError("market_return_pct inconsistent with prices")
        if not math.isclose(peak, exp_peak, **_METRIC_TOL):
            raise ForecastOutcomeInputError("peak_return_pct inconsistent with prices")
        if not math.isclose(trough, exp_trough, **_METRIC_TOL):
            raise ForecastOutcomeInputError("trough_return_pct inconsistent with prices")
        if not (peak >= trough):
            raise ForecastOutcomeInputError("peak_return_pct must be >= trough_return_pct")

        self._validate_directional(mret, peak, trough)

    def _validate_directional(self, mret: float, peak: float, trough: float) -> None:
        dr, mfe, mae = self.directional_return_pct, self.mfe_pct, self.mae_pct
        if self.direction == NEUTRAL:
            if dr is not None or mfe is not None or mae is not None:
                raise ForecastOutcomeInputError(
                    "NEUTRAL outcome must have NULL directional_return_pct/mfe_pct/mae_pct")
            return
        # LONG / SHORT
        if dr is None or mfe is None or mae is None:
            raise ForecastOutcomeInputError(
                "LONG/SHORT outcome requires directional_return_pct/mfe_pct/mae_pct")
        dr = _finite(dr, "directional_return_pct")
        mfe = _finite(mfe, "mfe_pct")
        mae = _finite(mae, "mae_pct")
        if self.direction == LONG:
            exp_dr, exp_mfe, exp_mae = mret, max(0.0, peak), min(0.0, trough)
        else:  # SHORT
            exp_dr, exp_mfe, exp_mae = -mret, max(0.0, -trough), min(0.0, -peak)
        if not math.isclose(dr, exp_dr, **_METRIC_TOL):
            raise ForecastOutcomeInputError("directional_return_pct inconsistent with direction")
        if not math.isclose(mfe, exp_mfe, **_METRIC_TOL):
            raise ForecastOutcomeInputError("mfe_pct inconsistent with direction")
        if not math.isclose(mae, exp_mae, **_METRIC_TOL):
            raise ForecastOutcomeInputError("mae_pct inconsistent with direction")
        if not (mfe >= 0.0):
            raise ForecastOutcomeInputError("mfe_pct must be >= 0")
        if not (mae <= 0.0):
            raise ForecastOutcomeInputError("mae_pct must be <= 0")


# ---- evaluation result -----------------------------------------------------
@dataclass(frozen=True)
class ForecastOutcomeEvaluation:
    horizon: str
    outcome_version: str
    evaluation_exchange: str
    evaluation_price_source: str

    evaluation_start_ts: datetime
    evaluation_end_ts: datetime

    status: str
    bars_expected: int
    bars_present: int
    missing_bar_ts: Sequence[datetime]

    outcome: Optional[ForecastOutcome]

    def __post_init__(self):
        # 1. missing_bar_ts must be a real Sequence — reject str/bytes/bytearray,
        # mapping, set/frozenset, generator/iterator, and any non-Sequence — then
        # detach to an immutable tuple.
        raw = self.missing_bar_ts
        if isinstance(raw, (str, bytes, bytearray)) or not isinstance(raw, _AbcSequence):
            raise ForecastOutcomeInputError(
                f"missing_bar_ts must be a Sequence (list/tuple), got {type(raw).__name__}")
        missing = tuple(raw)
        object.__setattr__(self, "missing_bar_ts", missing)

        if self.status not in OUTCOME_STATUSES:
            raise ForecastOutcomeInputError(f"invalid status {self.status!r}")

        # 2. validate the evaluation window for BOTH COMPLETE and INCOMPLETE via a
        # temporary real ForecastOutcomeWindow (supported horizon, non-blank outcome
        # version, active exchange, exact price source, UTC whole-minute timestamps,
        # exact horizon duration, exact int bars_expected). Pre-check the two window
        # timestamps so the target-bar arithmetic below cannot raise a raw TypeError.
        _whole_minute(self.evaluation_start_ts, "evaluation_start_ts")
        _whole_minute(self.evaluation_end_ts, "evaluation_end_ts")
        ForecastOutcomeWindow(
            horizon=self.horizon, outcome_version=self.outcome_version,
            evaluation_exchange=self.evaluation_exchange,
            evaluation_price_source=self.evaluation_price_source,
            evaluation_start_ts=self.evaluation_start_ts,
            evaluation_end_ts=self.evaluation_end_ts,
            target_bar_ts=self.evaluation_end_ts - timedelta(minutes=1),
            bars_expected=self.bars_expected)

        # 3. bars_present must be an actual int in [0, bars_expected] (bool rejected).
        if type(self.bars_present) is not int:
            raise ForecastOutcomeInputError("bars_present must be an int (bool rejected)")
        if not (0 <= self.bars_present <= self.bars_expected):
            raise ForecastOutcomeInputError("bars_present must be in [0, bars_expected]")

        # 4. every missing timestamp is UTC whole-minute, on the exact start..end-1m
        # grid, unique, and chronological.
        grid = [self.evaluation_start_ts + timedelta(minutes=i)
                for i in range(self.bars_expected)]
        grid_set = set(grid)
        for ts in missing:
            _whole_minute(ts, "missing_bar_ts")
            if ts not in grid_set:
                raise ForecastOutcomeInputError(
                    f"missing_bar_ts {ts.isoformat()} not on the evaluation grid")
        if len(set(missing)) != len(missing):
            raise ForecastOutcomeInputError("missing_bar_ts must be unique")
        if list(missing) != sorted(missing):
            raise ForecastOutcomeInputError("missing_bar_ts must be chronological")

        # 5. status-specific invariants
        if self.status == OUTCOME_COMPLETE:
            if type(self.outcome) is not ForecastOutcome:
                raise ForecastOutcomeInputError("COMPLETE requires a ForecastOutcome")
            if self.bars_present != self.bars_expected:
                raise ForecastOutcomeInputError("COMPLETE requires bars_present == bars_expected")
            if missing != ():
                raise ForecastOutcomeInputError("COMPLETE requires no missing bars")
            o = self.outcome
            for f in ("horizon", "outcome_version", "evaluation_exchange",
                      "evaluation_price_source", "evaluation_start_ts",
                      "evaluation_end_ts", "bars_expected", "bars_present"):
                if getattr(o, f) != getattr(self, f):
                    raise ForecastOutcomeInputError(
                        f"COMPLETE outcome {f} does not match evaluation")
        else:  # INCOMPLETE
            if self.outcome is not None:
                raise ForecastOutcomeInputError("INCOMPLETE must have outcome=None")
            if not (self.bars_present < self.bars_expected):
                raise ForecastOutcomeInputError("INCOMPLETE requires bars_present < bars_expected")
            if len(missing) == 0:
                raise ForecastOutcomeInputError("INCOMPLETE requires non-empty missing_bar_ts")
            if len(missing) != self.bars_expected - self.bars_present:
                raise ForecastOutcomeInputError(
                    "len(missing_bar_ts) must equal bars_expected - bars_present")


# ---- pure evaluator --------------------------------------------------------
def evaluate_forecast_outcome(
    prediction: ForecastPrediction,
    window: ForecastOutcomeWindow,
    *,
    price_bars: Sequence[OutcomePriceBar],
) -> ForecastOutcomeEvaluation:
    """Pure: measure one horizon outcome from the complete future 1m window. See
    module docstring. Missing bars -> INCOMPLETE (no error, no partial metrics)."""
    if type(prediction) is not ForecastPrediction:
        raise ForecastOutcomeInputError(
            f"prediction must be a ForecastPrediction, got {type(prediction).__name__}")
    if type(window) is not ForecastOutcomeWindow:
        raise ForecastOutcomeInputError(
            f"window must be a ForecastOutcomeWindow, got {type(window).__name__}")
    if isinstance(price_bars, (str, bytes, bytearray)) or not isinstance(price_bars, _AbcSequence):
        raise ForecastOutcomeInputError(
            f"price_bars must be a Sequence (list/tuple), got {type(price_bars).__name__}")

    # window must be consistent with the prediction
    if window.horizon not in prediction.horizon_set:
        raise ForecastOutcomeInputError(
            f"window horizon {window.horizon!r} not in prediction.horizon_set")
    if window.evaluation_start_ts != prediction.bucket_ts + timedelta(minutes=_PREDICTION_TIMEFRAME_MINUTES):
        raise ForecastOutcomeInputError("window evaluation_start_ts must be bucket_ts + 5m")
    if prediction.reference_price_source != _expected_reference_source(window.evaluation_exchange):
        raise ForecastOutcomeInputError(
            "reference_price_source must equal "
            f"{_expected_reference_source(window.evaluation_exchange)!r}")

    # expected 1m grid: start .. end-1m (bars_expected timestamps)
    grid = [window.evaluation_start_ts + timedelta(minutes=i)
            for i in range(window.bars_expected)]
    grid_set = set(grid)

    by_ts: dict[datetime, OutcomePriceBar] = {}
    for bar in price_bars:
        if type(bar) is not OutcomePriceBar:
            raise ForecastOutcomeInputError(
                f"price_bars items must be OutcomePriceBar, got {type(bar).__name__}")
        if bar.exchange != window.evaluation_exchange:
            raise ForecastOutcomeInputError(
                f"bar exchange {bar.exchange!r} != evaluation_exchange {window.evaluation_exchange!r}")
        if bar.symbol != prediction.symbol:
            raise ForecastOutcomeInputError(
                f"bar symbol {bar.symbol!r} != prediction symbol {prediction.symbol!r}")
        if not (window.evaluation_start_ts <= bar.ts < window.evaluation_end_ts):
            raise ForecastOutcomeInputError(
                f"bar ts {bar.ts.isoformat()} outside [start, end)")
        if bar.ts not in grid_set:
            raise ForecastOutcomeInputError(f"bar ts {bar.ts.isoformat()} not on the 1m grid")
        if bar.ts in by_ts:
            raise ForecastOutcomeInputError(f"duplicate bar ts {bar.ts.isoformat()}")
        by_ts[bar.ts] = bar

    bars_present = len(by_ts)
    missing = tuple(ts for ts in grid if ts not in by_ts)

    if missing:
        return ForecastOutcomeEvaluation(
            horizon=window.horizon, outcome_version=window.outcome_version,
            evaluation_exchange=window.evaluation_exchange,
            evaluation_price_source=window.evaluation_price_source,
            evaluation_start_ts=window.evaluation_start_ts,
            evaluation_end_ts=window.evaluation_end_ts,
            status=OUTCOME_INCOMPLETE, bars_expected=window.bars_expected,
            bars_present=bars_present, missing_bar_ts=missing, outcome=None)

    # complete: compute exact metrics
    ref = prediction.reference_price
    target_close = by_ts[window.target_bar_ts].close
    window_high = max(bar.high for bar in by_ts.values())
    window_low = min(bar.low for bar in by_ts.values())

    market_return = ((target_close / ref) - 1.0) * 100.0
    peak_return = ((window_high / ref) - 1.0) * 100.0
    trough_return = ((window_low / ref) - 1.0) * 100.0

    if prediction.direction == LONG:
        directional = market_return
        mfe = max(0.0, peak_return)
        mae = min(0.0, trough_return)
    elif prediction.direction == SHORT:
        directional = -market_return
        mfe = max(0.0, -trough_return)
        mae = min(0.0, -peak_return)
    else:  # NEUTRAL
        directional = mfe = mae = None

    outcome = ForecastOutcome(
        symbol=prediction.symbol, market_type=prediction.market_type,
        timeframe=prediction.timeframe, bucket_ts=prediction.bucket_ts,
        feature_schema_version=prediction.feature_schema_version,
        calculation_version=prediction.calculation_version,
        rule_version=prediction.rule_version,
        horizon=window.horizon, outcome_version=window.outcome_version,
        direction=prediction.direction,
        prediction_confidence=prediction.confidence,
        prediction_final_score=prediction.final_score,
        reference_price=prediction.reference_price,
        reference_price_source=prediction.reference_price_source,
        evaluation_exchange=window.evaluation_exchange,
        evaluation_price_source=window.evaluation_price_source,
        evaluation_start_ts=window.evaluation_start_ts,
        evaluation_end_ts=window.evaluation_end_ts, target_bar_ts=window.target_bar_ts,
        bars_expected=window.bars_expected, bars_present=bars_present,
        target_close_price=target_close, window_high_price=window_high,
        window_low_price=window_low, market_return_pct=market_return,
        peak_return_pct=peak_return, trough_return_pct=trough_return,
        directional_return_pct=directional, mfe_pct=mfe, mae_pct=mae,
        config_hash=prediction.config_hash, config_version=prediction.config_version,
        code_version=prediction.code_version)

    return ForecastOutcomeEvaluation(
        horizon=window.horizon, outcome_version=window.outcome_version,
        evaluation_exchange=window.evaluation_exchange,
        evaluation_price_source=window.evaluation_price_source,
        evaluation_start_ts=window.evaluation_start_ts,
        evaluation_end_ts=window.evaluation_end_ts,
        status=OUTCOME_COMPLETE, bars_expected=window.bars_expected,
        bars_present=bars_present, missing_bar_ts=(), outcome=outcome)
