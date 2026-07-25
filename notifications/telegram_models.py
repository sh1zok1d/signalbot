"""
Pure, deterministic models for the Telegram forecast notifier.

No DB, environment, network, clock, logging, or filesystem access anywhere in
this module — every function/dataclass here is a pure function of its inputs.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Sequence

# LONG/SHORT are actionable; NEUTRAL must never reach this module at all (the
# storage-layer materialization query itself excludes NEUTRAL predictions).
ACTIONABLE_DIRECTIONS = ("LONG", "SHORT")

CHANNEL_TELEGRAM = "telegram"
NOTIFIER_RUNNER_NAME = "telegram_forecast_v1"

# Retry/backoff policy (base 60s, exponential by attempt count, capped at 6h).
# Deterministic; no randomness/jitter.
RETRY_BASE_SECONDS = 60
RETRY_MAX_SECONDS = 6 * 60 * 60
_MAX_EXPONENT = 32   # overflow-safe ceiling on the doubling exponent


class TelegramModelError(ValueError):
    """A malformed notification candidate, fingerprint input, or retry input."""


# ---- small validators -------------------------------------------------------
def _nonblank(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TelegramModelError(f"{name} must be a non-empty string")
    return value


def _require_utc(dt, name: str) -> datetime:
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise TelegramModelError(f"{name} must be a timezone-aware UTC datetime")
    return dt


def _finite(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TelegramModelError(f"{name} must be a real number, got {type(value).__name__}")
    v = float(value)
    if not math.isfinite(v):
        raise TelegramModelError(f"{name} must be finite, got {value!r}")
    return v


def _finite_in_range(value, name: str, low: float, high: float) -> float:
    v = _finite(value, name)
    if not (low <= v <= high):
        raise TelegramModelError(f"{name} must be in [{low}, {high}], got {v!r}")
    return v


def _finite_in_range_or_none(value, name: str, low: float, high: float):
    if value is None:
        return None
    return _finite_in_range(value, name, low, high)


def _validate_str_sequence(value, name: str) -> tuple:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise TelegramModelError(f"{name} must be a Sequence of strings, got {type(value).__name__}")
    out = tuple(value)
    for i, item in enumerate(out):
        if not isinstance(item, str):
            raise TelegramModelError(f"{name}[{i}] must be a string, got {type(item).__name__}")
    return out


# ---- recipient fingerprint ---------------------------------------------------
def compute_recipient_fingerprint(chat_id: str) -> str:
    """Deterministic sha256 hex digest of the chat id (64 lowercase hex chars).
    Never Python's randomized `hash()`. The bot token never enters the
    fingerprint, and the raw chat id is never returned/stored anywhere — only
    this fingerprint is persisted."""
    _nonblank(chat_id, "chat_id")
    return hashlib.sha256(chat_id.strip().encode("utf-8")).hexdigest()


# ---- retry / backoff ---------------------------------------------------------
def compute_retry_delay(attempt_count: int, *, retry_after: Optional[float] = None) -> int:
    """Pure, deterministic, overflow-safe retry delay in whole seconds.

    - base 60s, doubled per attempt (attempt_count=1 -> 60s, 2 -> 120s, ...),
      capped at 6 hours (21600s);
    - a Telegram RetryAfter / HTTP 429 `retry_after` (seconds) is respected: the
      delay is never shorter than it (still capped at 6h);
    - no randomness/jitter — fully deterministic and testable;
    - `attempt_count` must be an exact int >= 1 (bool rejected).
    """
    if type(attempt_count) is not int or attempt_count < 1:
        raise TelegramModelError("attempt_count must be an int >= 1")
    exponent = min(attempt_count - 1, _MAX_EXPONENT)   # overflow-safe: never shifts unbounded
    delay = min(RETRY_BASE_SECONDS * (2 ** exponent), RETRY_MAX_SECONDS)
    if retry_after is not None:
        if isinstance(retry_after, bool) or not isinstance(retry_after, (int, float)) \
                or not math.isfinite(retry_after) or retry_after < 0:
            raise TelegramModelError("retry_after must be a finite number >= 0")
        delay = max(delay, min(int(math.ceil(retry_after)), RETRY_MAX_SECONDS))
    return delay


# ---- notification candidate --------------------------------------------------
@dataclass(frozen=True)
class NotificationCandidate:
    """Strict, immutable notification candidate: everything needed to render
    and identify ONE due delivery. Deliberately excludes consensus_snapshot,
    config_hash/config_version, and code_version — unnecessary for rendering."""
    symbol: str
    market_type: str
    timeframe: str
    bucket_ts: datetime
    calculation_version: str
    rule_version: str

    direction: str
    confidence: float
    final_score: float
    reference_price: float
    reference_price_source: str
    horizon_set: Sequence[str]
    reasons: Sequence[str]
    exchanges_expected_max: int
    min_coverage_ratio: Optional[float]
    data_confidence_overall: Optional[float]
    consensus_confidence: Optional[float]
    is_partial_consensus: bool

    prediction_created_at: datetime

    def __post_init__(self) -> None:
        _nonblank(self.symbol, "symbol")
        _nonblank(self.market_type, "market_type")
        _nonblank(self.timeframe, "timeframe")
        _nonblank(self.calculation_version, "calculation_version")
        _nonblank(self.rule_version, "rule_version")
        _nonblank(self.reference_price_source, "reference_price_source")

        if self.direction not in ACTIONABLE_DIRECTIONS:
            raise TelegramModelError(
                f"direction must be one of {ACTIONABLE_DIRECTIONS}, got {self.direction!r}")

        _finite_in_range(self.confidence, "confidence", 0.0, 1.0)
        _finite_in_range(self.final_score, "final_score", -1.0, 1.0)

        price = _finite(self.reference_price, "reference_price")
        if not price > 0:
            raise TelegramModelError(f"reference_price must be > 0, got {price!r}")

        object.__setattr__(self, "horizon_set", _validate_str_sequence(self.horizon_set, "horizon_set"))
        if not self.horizon_set:
            raise TelegramModelError("horizon_set must be non-empty")
        object.__setattr__(self, "reasons", _validate_str_sequence(self.reasons, "reasons"))

        if not isinstance(self.exchanges_expected_max, int) or isinstance(self.exchanges_expected_max, bool) \
                or self.exchanges_expected_max < 1:
            raise TelegramModelError("exchanges_expected_max must be an int >= 1")
        _finite_in_range_or_none(self.min_coverage_ratio, "min_coverage_ratio", 0.0, 1.0)
        _finite_in_range_or_none(self.data_confidence_overall, "data_confidence_overall", 0.0, 100.0)
        _finite_in_range_or_none(self.consensus_confidence, "consensus_confidence", 0.0, 100.0)
        if not isinstance(self.is_partial_consensus, bool):
            raise TelegramModelError("is_partial_consensus must be a bool")

        _require_utc(self.bucket_ts, "bucket_ts")
        _require_utc(self.prediction_created_at, "prediction_created_at")
