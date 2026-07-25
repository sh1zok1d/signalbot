"""
Storage-layer SQL + validation for the Telegram forecast notifier.

Pure storage: static/trusted SQL and immutable detached results only. Imports NO
analytics, runtime, or main module and NO Telegram/network client. Every query
uses explicit columns (never `SELECT *`); NEUTRAL predictions never enter this
module's writes; `consensus_snapshot` is never selected.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")


class TelegramNotificationReaderError(ValueError):
    """Invalid telegram-notifier reader/writer argument (validated before any
    DB access) or a malformed row that must fail closed."""


# ---- static, trusted SQL ----------------------------------------------------
NOTIFIER_STATE_SELECT_SQL = """
SELECT started_at
FROM telegram_notifier_state
WHERE runner_name = $1 AND channel = $2 AND recipient_fingerprint = $3
"""

NOTIFIER_STATE_INSERT_SQL = """
INSERT INTO telegram_notifier_state
    (runner_name, channel, recipient_fingerprint, started_at)
VALUES ($1, $2, $3, $4)
ON CONFLICT (runner_name, channel, recipient_fingerprint) DO NOTHING
"""

# Materialize missing delivery rows for LONG/SHORT predictions with
# created_at >= started_at, oldest created_at first, capped, real NOT EXISTS
# anti-join, ON CONFLICT DO NOTHING as an additional idempotency guard.
MATERIALIZE_DELIVERIES_SQL = """
INSERT INTO telegram_notification_deliveries
    (channel, recipient_fingerprint, symbol, market_type, timeframe, bucket_ts,
     calculation_version, rule_version, next_attempt_at)
SELECT
    $1, $2, fp.symbol, fp.market_type, fp.timeframe, fp.bucket_ts,
    fp.calculation_version, fp.rule_version, now()
FROM forecast_predictions fp
WHERE fp.symbol = $3
  AND fp.market_type = $4
  AND fp.timeframe = $5
  AND fp.direction IN ('LONG', 'SHORT')
  AND fp.created_at >= $6
  AND NOT EXISTS (
      SELECT 1 FROM telegram_notification_deliveries d
      WHERE d.channel = $1 AND d.recipient_fingerprint = $2
        AND d.symbol = fp.symbol AND d.market_type = fp.market_type
        AND d.timeframe = fp.timeframe AND d.bucket_ts = fp.bucket_ts
        AND d.calculation_version = fp.calculation_version
        AND d.rule_version = fp.rule_version
  )
ORDER BY fp.created_at ASC
LIMIT $7
ON CONFLICT (channel, recipient_fingerprint, symbol, market_type, timeframe,
             bucket_ts, calculation_version, rule_version) DO NOTHING
"""

# Due unsent deliveries joined to their prediction, explicit columns only, no
# consensus_snapshot, deterministic oldest-next_attempt_at-first order, capped.
PENDING_DELIVERIES_SQL = """
SELECT
    d.symbol, d.market_type, d.timeframe, d.bucket_ts,
    d.calculation_version, d.rule_version, d.attempt_count,
    fp.direction, fp.confidence, fp.final_score, fp.reference_price,
    fp.reference_price_source, fp.horizon_set, fp.reasons,
    fp.exchanges_expected_max, fp.min_coverage_ratio, fp.data_confidence_overall,
    fp.consensus_confidence, fp.is_partial_consensus, fp.created_at AS prediction_created_at
FROM telegram_notification_deliveries d
JOIN forecast_predictions fp
    ON  fp.symbol = d.symbol AND fp.market_type = d.market_type
    AND fp.timeframe = d.timeframe AND fp.bucket_ts = d.bucket_ts
    AND fp.calculation_version = d.calculation_version
    AND fp.rule_version = d.rule_version
WHERE d.channel = $1 AND d.recipient_fingerprint = $2
  AND d.sent_at IS NULL AND d.next_attempt_at <= $3
ORDER BY d.next_attempt_at ASC, d.bucket_ts ASC
LIMIT $4
"""

RECORD_ATTEMPT_START_SQL = """
UPDATE telegram_notification_deliveries
SET attempt_count = attempt_count + 1, last_attempt_at = now(), updated_at = now()
WHERE channel = $1 AND recipient_fingerprint = $2 AND symbol = $3 AND market_type = $4
  AND timeframe = $5 AND bucket_ts = $6 AND calculation_version = $7 AND rule_version = $8
RETURNING attempt_count
"""

RECORD_SENT_SQL = """
UPDATE telegram_notification_deliveries
SET sent_at = now(), telegram_message_id = $9,
    last_error_class = NULL, last_error_summary = NULL, updated_at = now()
WHERE channel = $1 AND recipient_fingerprint = $2 AND symbol = $3 AND market_type = $4
  AND timeframe = $5 AND bucket_ts = $6 AND calculation_version = $7 AND rule_version = $8
"""

RECORD_FAILURE_SQL = """
UPDATE telegram_notification_deliveries
SET next_attempt_at = $9, last_error_class = $10, last_error_summary = $11, updated_at = now()
WHERE channel = $1 AND recipient_fingerprint = $2 AND symbol = $3 AND market_type = $4
  AND timeframe = $5 AND bucket_ts = $6 AND calculation_version = $7 AND rule_version = $8
"""

NOTIFIER_STATUS_AGGREGATE_SQL = """
SELECT
    count(*) FILTER (WHERE sent_at IS NULL) AS total_pending,
    count(*) FILTER (WHERE sent_at IS NULL AND next_attempt_at <= $3) AS due_pending,
    count(*) FILTER (WHERE sent_at IS NOT NULL) AS total_sent,
    max(sent_at) AS last_sent_at,
    min(next_attempt_at) FILTER (WHERE sent_at IS NULL) AS earliest_next_attempt_at
FROM telegram_notification_deliveries
WHERE channel = $1 AND recipient_fingerprint = $2
"""

TELEGRAM_SCHEMA_STATE_SQL = """
SELECT
    to_regclass('public.telegram_notifier_state')::text          AS telegram_notifier_state,
    to_regclass('public.telegram_notification_deliveries')::text  AS telegram_notification_deliveries
"""


# ---- validation --------------------------------------------------------------
def _nonblank(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TelegramNotificationReaderError(f"{name} must be a non-empty string")
    return value


def _fingerprint(value, name: str) -> str:
    _nonblank(value, name)
    if not _FINGERPRINT_RE.match(value):
        raise TelegramNotificationReaderError(f"{name} must be a 64-char lowercase sha256 hex digest")
    return value


def _utc(dt, name: str) -> datetime:
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise TelegramNotificationReaderError(f"{name} must be a timezone-aware UTC datetime")
    return dt


def _pos_int(value, name: str, upper: int) -> int:
    if type(value) is not int:
        raise TelegramNotificationReaderError(f"{name} must be an int")
    if not (1 <= value <= upper):
        raise TelegramNotificationReaderError(f"{name} must be in [1, {upper}]")
    return value


def validate_notifier_scope(*, runner_name, channel, recipient_fingerprint) -> None:
    _nonblank(runner_name, "runner_name")
    _nonblank(channel, "channel")
    _fingerprint(recipient_fingerprint, "recipient_fingerprint")


def validate_recipient_scope(*, channel, recipient_fingerprint) -> None:
    _nonblank(channel, "channel")
    _fingerprint(recipient_fingerprint, "recipient_fingerprint")


# ---- bootstrap state ---------------------------------------------------------
async def read_notifier_started_at(conn, *, runner_name, channel, recipient_fingerprint
                                   ) -> Optional[datetime]:
    validate_notifier_scope(runner_name=runner_name, channel=channel,
                            recipient_fingerprint=recipient_fingerprint)
    return await conn.fetchval(NOTIFIER_STATE_SELECT_SQL, runner_name, channel, recipient_fingerprint)


async def ensure_notifier_started_at(conn, *, runner_name, channel, recipient_fingerprint,
                                     now: datetime) -> tuple:
    """Return (started_at, bootstrapped). If no state row exists yet, insert one
    with started_at=now (ON CONFLICT DO NOTHING guards a concurrent bootstrap),
    then re-read the authoritative value. Never overwrites an existing
    started_at."""
    validate_notifier_scope(runner_name=runner_name, channel=channel,
                            recipient_fingerprint=recipient_fingerprint)
    _utc(now, "now")
    existing = await conn.fetchval(
        NOTIFIER_STATE_SELECT_SQL, runner_name, channel, recipient_fingerprint)
    if existing is not None:
        return existing, False
    await conn.execute(
        NOTIFIER_STATE_INSERT_SQL, runner_name, channel, recipient_fingerprint, now)
    started_at = await conn.fetchval(
        NOTIFIER_STATE_SELECT_SQL, runner_name, channel, recipient_fingerprint)
    return started_at, True


# ---- materialization ----------------------------------------------------------
async def materialize_telegram_deliveries(conn, *, channel, recipient_fingerprint,
                                          symbol, market_type, timeframe,
                                          started_at, limit) -> int:
    validate_recipient_scope(channel=channel, recipient_fingerprint=recipient_fingerprint)
    _nonblank(symbol, "symbol")
    _nonblank(market_type, "market_type")
    _nonblank(timeframe, "timeframe")
    _utc(started_at, "started_at")
    _pos_int(limit, "limit", 100000)
    result = await conn.execute(
        MATERIALIZE_DELIVERIES_SQL, channel, recipient_fingerprint, symbol,
        market_type, timeframe, started_at, limit)
    # asyncpg execute() returns a command tag like "INSERT 0 3"
    try:
        return int(str(result).rsplit(" ", 1)[-1])
    except ValueError:
        return 0


# ---- pending discovery ---------------------------------------------------------
_JSONB_COLUMNS = ("horizon_set", "reasons")


def _parse_jsonb(value):
    if value is None or isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        return json.loads(value)
    raise TelegramNotificationReaderError(f"unexpected JSONB python type {type(value).__name__}")


def _detach_pending_row(rec) -> Mapping:
    out = {}
    for key in rec.keys():
        out[key] = _parse_jsonb(rec[key]) if key in _JSONB_COLUMNS else rec[key]
    return MappingProxyType(out)


async def read_pending_telegram_deliveries(conn, *, channel, recipient_fingerprint,
                                           now, limit) -> tuple:
    validate_recipient_scope(channel=channel, recipient_fingerprint=recipient_fingerprint)
    _utc(now, "now")
    _pos_int(limit, "limit", 100000)
    records = await conn.fetch(PENDING_DELIVERIES_SQL, channel, recipient_fingerprint, now, limit)
    return tuple(_detach_pending_row(r) for r in records)


def _delivery_identity_args(*, channel, recipient_fingerprint, symbol, market_type,
                            timeframe, bucket_ts, calculation_version, rule_version):
    validate_recipient_scope(channel=channel, recipient_fingerprint=recipient_fingerprint)
    _nonblank(symbol, "symbol")
    _nonblank(market_type, "market_type")
    _nonblank(timeframe, "timeframe")
    _utc(bucket_ts, "bucket_ts")
    _nonblank(calculation_version, "calculation_version")
    _nonblank(rule_version, "rule_version")
    return (channel, recipient_fingerprint, symbol, market_type, timeframe,
            bucket_ts, calculation_version, rule_version)


# ---- attempt bookkeeping ------------------------------------------------------
async def record_delivery_attempt_start(conn, *, channel, recipient_fingerprint, symbol,
                                        market_type, timeframe, bucket_ts,
                                        calculation_version, rule_version) -> int:
    args = _delivery_identity_args(
        channel=channel, recipient_fingerprint=recipient_fingerprint, symbol=symbol,
        market_type=market_type, timeframe=timeframe, bucket_ts=bucket_ts,
        calculation_version=calculation_version, rule_version=rule_version)
    return await conn.fetchval(RECORD_ATTEMPT_START_SQL, *args)


async def record_delivery_sent(conn, *, channel, recipient_fingerprint, symbol, market_type,
                               timeframe, bucket_ts, calculation_version, rule_version,
                               telegram_message_id: int) -> None:
    args = _delivery_identity_args(
        channel=channel, recipient_fingerprint=recipient_fingerprint, symbol=symbol,
        market_type=market_type, timeframe=timeframe, bucket_ts=bucket_ts,
        calculation_version=calculation_version, rule_version=rule_version)
    if type(telegram_message_id) is not int:
        raise TelegramNotificationReaderError("telegram_message_id must be an int")
    await conn.execute(RECORD_SENT_SQL, *args, telegram_message_id)


async def record_delivery_failure(conn, *, channel, recipient_fingerprint, symbol, market_type,
                                  timeframe, bucket_ts, calculation_version, rule_version,
                                  next_attempt_at: datetime, error_class: str,
                                  error_summary: str) -> None:
    args = _delivery_identity_args(
        channel=channel, recipient_fingerprint=recipient_fingerprint, symbol=symbol,
        market_type=market_type, timeframe=timeframe, bucket_ts=bucket_ts,
        calculation_version=calculation_version, rule_version=rule_version)
    _utc(next_attempt_at, "next_attempt_at")
    _nonblank(error_class, "error_class")
    if not isinstance(error_summary, str):
        raise TelegramNotificationReaderError("error_summary must be a string")
    await conn.execute(RECORD_FAILURE_SQL, *args, next_attempt_at, error_class, error_summary)


# ---- status (read-only) -------------------------------------------------------
async def read_telegram_schema_state(conn) -> Mapping[str, bool]:
    row = await conn.fetchrow(TELEGRAM_SCHEMA_STATE_SQL)
    return MappingProxyType({
        "telegram_notifier_state": row["telegram_notifier_state"] is not None,
        "telegram_notification_deliveries": row["telegram_notification_deliveries"] is not None,
    })


async def read_notifier_status_aggregate(conn, *, channel, recipient_fingerprint, now) -> Mapping:
    validate_recipient_scope(channel=channel, recipient_fingerprint=recipient_fingerprint)
    _utc(now, "now")
    row = await conn.fetchrow(NOTIFIER_STATUS_AGGREGATE_SQL, channel, recipient_fingerprint, now)
    return MappingProxyType({
        "total_pending": row["total_pending"],
        "due_pending": row["due_pending"],
        "total_sent": row["total_sent"],
        "last_sent_at": row["last_sent_at"],
        "earliest_next_attempt_at": row["earliest_next_attempt_at"],
    })
