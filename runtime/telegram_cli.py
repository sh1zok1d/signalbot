"""
Operational Telegram forecast-notification CLI: --telegram-once /
--telegram-status / --telegram-test.

This is the deliberate MANUAL/timer operational boundary over the isolated
Telegram notification subsystem (notifications/*, storage/telegram_notification_
readers.py). It is the layer allowed to read the wall clock, load secrets,
acquire the dedicated (independent) Telegram advisory lock, perform Database
I/O, construct the real Telegram sender, and render human/JSON output.

Isolation from the shadow forecast timer is architectural, not incidental:
- this module never imports runtime.shadow_recovery / runtime.shadow_cli's
  process_shadow_cycle path, and is never imported BY those modules;
- the advisory lock used here is a completely separate PostgreSQL lock
  namespace from the shadow recovery lock (different deterministic key);
- Telegram network failures are persisted per-delivery and reported in
  aggregate — they never fail the whole invocation, never roll back a
  forecast_predictions/forecast_outcomes row, and never touch the shadow
  timer's state in any way.

Delivery guarantee (documented honestly): durable AT-LEAST-ONCE delivery. The
unique outbox identity prevents a normal duplicate enqueue, and there is
exactly one Telegram send attempt per delivery per invocation (no in-process
retry), so under normal operation a message is sent at most once. A RARE
duplicate is possible only if the process crashes in the narrow window after
Telegram has accepted a message but before PostgreSQL records `sent_at` — an
ambiguous outcome that this design deliberately resolves by retrying (favoring
delivery over risking silent message loss) rather than claiming a
mathematically perfect exactly-once guarantee.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping, Optional, Sequence

from common.config import Config, Secrets
from storage.db import Database

from notifications.telegram_client import (
    TelegramSendError, TelegramSender, sanitize_telegram_error,
)
from notifications.telegram_formatter import render_telegram_forecast_message
from notifications.telegram_models import (
    ACTIONABLE_DIRECTIONS, CHANNEL_TELEGRAM, NOTIFIER_RUNNER_NAME,
    NotificationCandidate, TelegramModelError, compute_recipient_fingerprint,
    compute_retry_delay,
)

# ---- stable command / lock / bootstrap / status constants ------------------
TELEGRAM_ONCE = "TELEGRAM_ONCE"
TELEGRAM_STATUS = "TELEGRAM_STATUS"
TELEGRAM_TEST = "TELEGRAM_TEST"

LOCK_ACQUIRED = "ACQUIRED"
LOCK_HELD_SKIPPED = "LOCK_HELD_SKIPPED"

BOOTSTRAPPED_NO_HISTORY = "BOOTSTRAPPED_NO_HISTORY"
ALREADY_INITIALIZED = "ALREADY_INITIALIZED"

STATUS_NOT_INITIALIZED = "NOT_INITIALIZED"
STATUS_READY = "READY"

_MARKET_TYPE = "perp"
_TIMEFRAME = "5m"

# Bounded scan/send defaults + hard validation ceilings. Operational only —
# these never enter any forecast identity/config_hash/calculation_version.
DEFAULT_MAX_SCAN = 200
DEFAULT_MAX_SEND = 20
MAX_SCAN_LIMIT = 2000
MAX_SEND_LIMIT = 100


class TelegramCliError(RuntimeError):
    """A Telegram-notifier-layer failure: invalid operational input, missing
    secrets, a hydration/identity failure that must fail closed, or an
    impossible orchestration state. Telegram send failures are NOT this error
    (they are persisted per-delivery and never raised)."""


def is_telegram_command(args) -> bool:
    return bool(getattr(args, "telegram_once", False)
                or getattr(args, "telegram_status", False)
                or getattr(args, "telegram_test", False))


# ============================================================================
# Pure helpers
# ============================================================================
def validate_operational_cap(value, name: str, upper: int) -> int:
    """A validated operational cap: an exact int in [1, upper]; bool/zero/
    negative/non-int/too-large rejected. Operational only."""
    if type(value) is not int:
        raise TelegramCliError(f"{name} must be an int (bool rejected)")
    if not (1 <= value <= upper):
        raise TelegramCliError(f"{name} must be in [1, {upper}], got {value}")
    return value


def telegram_notifier_lock_key(runner_name: str, channel: str, recipient_fingerprint: str) -> int:
    """Deterministic signed 64-bit advisory-lock key, derived the same way as
    the shadow recovery lock (sha256, never Python's randomized hash()) but in
    a completely SEPARATE lock namespace: this key is computed from the
    Telegram runner/channel/recipient identity only, so it can never collide
    with — or block on — the shadow recovery lock."""
    import hashlib
    for name_, value in (("runner_name", runner_name), ("channel", channel),
                         ("recipient_fingerprint", recipient_fingerprint)):
        if not isinstance(value, str) or not value.strip():
            raise TelegramCliError(f"{name_} must be a non-empty string")
    payload = "\x1e".join((runner_name, channel, recipient_fingerprint)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=True)


def hydrate_notification_candidate(row: Mapping) -> NotificationCandidate:
    """Strictly reconstruct a NotificationCandidate from a pending-delivery row.
    Any malformed row (missing key, wrong type, invalid identity/version, out-of
    -range value) fails closed — never silently skipped."""
    if not isinstance(row, Mapping):
        raise TelegramCliError("pending delivery row must be a mapping")
    try:
        return NotificationCandidate(
            symbol=row["symbol"], market_type=row["market_type"], timeframe=row["timeframe"],
            bucket_ts=row["bucket_ts"], calculation_version=row["calculation_version"],
            rule_version=row["rule_version"], direction=row["direction"],
            confidence=row["confidence"], final_score=row["final_score"],
            reference_price=row["reference_price"],
            reference_price_source=row["reference_price_source"],
            horizon_set=tuple(row["horizon_set"]), reasons=tuple(row["reasons"]),
            exchanges_expected_max=row["exchanges_expected_max"],
            min_coverage_ratio=row["min_coverage_ratio"],
            data_confidence_overall=row["data_confidence_overall"],
            consensus_confidence=row["consensus_confidence"],
            is_partial_consensus=row["is_partial_consensus"],
            prediction_created_at=row["prediction_created_at"])
    except KeyError as exc:
        raise TelegramCliError(f"malformed pending delivery row: missing {exc}") from exc
    except TelegramModelError as exc:
        raise TelegramCliError(f"malformed pending delivery row: {exc}") from exc


# ============================================================================
# Typed reports
# ============================================================================
@dataclass(frozen=True)
class TelegramExecutionReport:
    command: str
    lock_status: str
    bootstrap_status: Optional[str]
    channel: str
    recipient_fingerprint: str
    scan_limit: int
    send_limit: int
    materialized_count: int
    pending_count: int
    attempted_count: int
    sent_count: int
    failed_count: int
    retryable_remaining: int
    earliest_next_attempt_at: Optional[datetime]
    directions_represented: Sequence[str]
    prediction_buckets_represented: Sequence[datetime]
    writes_enabled: bool
    telegram_calls_attempted: int
    code_version: Optional[str]
    failures: Sequence[Mapping]

    def __post_init__(self) -> None:
        if self.command not in (TELEGRAM_ONCE,):
            raise TelegramCliError(f"invalid execution command {self.command!r}")
        if self.lock_status not in (LOCK_ACQUIRED, LOCK_HELD_SKIPPED):
            raise TelegramCliError(f"invalid lock_status {self.lock_status!r}")
        if type(self.writes_enabled) is not bool:
            raise TelegramCliError("writes_enabled must be a bool")
        object.__setattr__(self, "directions_represented", tuple(self.directions_represented))
        object.__setattr__(self, "prediction_buckets_represented",
                           tuple(self.prediction_buckets_represented))
        object.__setattr__(self, "failures", tuple(dict(f) for f in self.failures))
        for d in self.directions_represented:
            if d not in ACTIONABLE_DIRECTIONS:
                raise TelegramCliError(f"directions_represented contains {d!r}")


@dataclass(frozen=True)
class TelegramStatusReport:
    state: str
    notifier_initialized: bool
    started_at: Optional[datetime]
    channel: str
    recipient_fingerprint: str
    total_pending: int
    due_pending: int
    total_sent: int
    last_sent_at: Optional[datetime]
    earliest_next_attempt_at: Optional[datetime]

    def __post_init__(self) -> None:
        if self.state not in (STATUS_NOT_INITIALIZED, STATUS_READY):
            raise TelegramCliError(f"invalid status state {self.state!r}")
        if type(self.notifier_initialized) is not bool:
            raise TelegramCliError("notifier_initialized must be a bool")


# ============================================================================
# Execution APIs
# ============================================================================
def _resolve_secrets(secrets: Secrets) -> tuple:
    token = secrets.telegram_token
    chat_id = secrets.telegram_chat_id
    if not isinstance(token, str) or not token.strip():
        raise TelegramCliError(
            "TELEGRAM_BOT_TOKEN is not configured (set it in .env before running "
            "--telegram-once)")
    if not isinstance(chat_id, str) or not chat_id.strip():
        raise TelegramCliError(
            "TELEGRAM_CHAT_ID is not configured (set it in .env before running "
            "--telegram-once)")
    return token, chat_id


def _best_effort_code_version() -> Optional[str]:
    from common.versioning import VersioningError, resolve_code_version
    try:
        return resolve_code_version()
    except VersioningError:
        return None


async def execute_telegram_once(
    db,
    stage1_config: Config,
    secrets: Secrets,
    *,
    now: datetime,
    max_scan: Optional[int] = None,
    max_send: Optional[int] = None,
    telegram_sender=None,
) -> TelegramExecutionReport:
    """One bounded Telegram notification pass. All secret/cap validation happens
    BEFORE any schema/outbox/lock work. See module docstring for the isolation
    and delivery guarantees."""
    token, chat_id = _resolve_secrets(secrets)

    scan_limit = DEFAULT_MAX_SCAN if max_scan is None else max_scan
    send_limit = DEFAULT_MAX_SEND if max_send is None else max_send
    validate_operational_cap(scan_limit, "max_scan", MAX_SCAN_LIMIT)
    validate_operational_cap(send_limit, "max_send", MAX_SEND_LIMIT)

    channel = CHANNEL_TELEGRAM
    recipient_fingerprint = compute_recipient_fingerprint(chat_id)
    code_version = _best_effort_code_version()
    lock_key = telegram_notifier_lock_key(NOTIFIER_RUNNER_NAME, channel, recipient_fingerprint)

    async with db.telegram_notifier_lock(lock_key) as acquired:
        if not acquired:
            return TelegramExecutionReport(
                command=TELEGRAM_ONCE, lock_status=LOCK_HELD_SKIPPED, bootstrap_status=None,
                channel=channel, recipient_fingerprint=recipient_fingerprint,
                scan_limit=scan_limit, send_limit=send_limit, materialized_count=0,
                pending_count=0, attempted_count=0, sent_count=0, failed_count=0,
                retryable_remaining=0, earliest_next_attempt_at=None,
                directions_represented=(), prediction_buckets_represented=(),
                writes_enabled=False, telegram_calls_attempted=0,
                code_version=code_version, failures=())

        await db.init_stage2_schema()   # idempotent; also creates the telegram tables

        symbol = stage1_config.symbol
        started_at, bootstrapped = await db.ensure_telegram_notifier_state(
            runner_name=NOTIFIER_RUNNER_NAME, channel=channel,
            recipient_fingerprint=recipient_fingerprint, now=now)
        bootstrap_status = BOOTSTRAPPED_NO_HISTORY if bootstrapped else ALREADY_INITIALIZED

        materialized = await db.materialize_telegram_deliveries(
            channel=channel, recipient_fingerprint=recipient_fingerprint, symbol=symbol,
            market_type=_MARKET_TYPE, timeframe=_TIMEFRAME, started_at=started_at,
            limit=scan_limit)

        pending_rows = await db.fetch_pending_telegram_deliveries(
            channel=channel, recipient_fingerprint=recipient_fingerprint, now=now,
            limit=send_limit)
        # Hydrate EVERY row up front: a single malformed row fails the WHOLE
        # invocation closed before any send attempt — never silently skipped.
        candidates = [hydrate_notification_candidate(row) for row in pending_rows]

        client = telegram_sender if telegram_sender is not None else TelegramSender(token)

        attempted = sent = failed = 0
        directions: set = set()
        buckets: list = []
        failures: list = []

        for candidate in candidates:
            attempted += 1
            attempt_count = await db.record_telegram_attempt_start(
                channel=channel, recipient_fingerprint=recipient_fingerprint,
                symbol=candidate.symbol, market_type=candidate.market_type,
                timeframe=candidate.timeframe, bucket_ts=candidate.bucket_ts,
                calculation_version=candidate.calculation_version,
                rule_version=candidate.rule_version)
            html = render_telegram_forecast_message(candidate)
            try:
                # Exactly ONE Telegram send attempt per delivery this invocation.
                result = await client.send_message(chat_id=chat_id, html=html)
            except TelegramSendError as exc:
                delay_s = compute_retry_delay(attempt_count, retry_after=exc.retry_after)
                next_attempt_at = now + timedelta(seconds=delay_s)
                error_class = type(exc).__name__
                # Defensive re-sanitization: even though TelegramSender already
                # sanitizes before raising, an injected TelegramSenderProtocol
                # implementation could raise with an unsanitized message, so the
                # runtime boundary sanitizes again with BOTH secrets before any
                # persistence/reporting — the raw token and raw chat id must
                # never reach storage or a report.
                error_summary = sanitize_telegram_error(exc, token=token, chat_id=chat_id)
                await db.record_telegram_failure(
                    channel=channel, recipient_fingerprint=recipient_fingerprint,
                    symbol=candidate.symbol, market_type=candidate.market_type,
                    timeframe=candidate.timeframe, bucket_ts=candidate.bucket_ts,
                    calculation_version=candidate.calculation_version,
                    rule_version=candidate.rule_version, next_attempt_at=next_attempt_at,
                    error_class=error_class, error_summary=error_summary)
                failed += 1
                failures.append({
                    "bucket_ts": candidate.bucket_ts, "error_class": error_class,
                    "error_summary": error_summary})
                continue   # bounded: move on to the next delivery, never crash
            await db.record_telegram_sent(
                channel=channel, recipient_fingerprint=recipient_fingerprint,
                symbol=candidate.symbol, market_type=candidate.market_type,
                timeframe=candidate.timeframe, bucket_ts=candidate.bucket_ts,
                calculation_version=candidate.calculation_version,
                rule_version=candidate.rule_version,
                telegram_message_id=result.message_id)
            sent += 1
            directions.add(candidate.direction)
            buckets.append(candidate.bucket_ts)

        aggregate = await db.fetch_telegram_notifier_status(
            channel=channel, recipient_fingerprint=recipient_fingerprint, now=now)

        return TelegramExecutionReport(
            command=TELEGRAM_ONCE, lock_status=LOCK_ACQUIRED, bootstrap_status=bootstrap_status,
            channel=channel, recipient_fingerprint=recipient_fingerprint,
            scan_limit=scan_limit, send_limit=send_limit, materialized_count=materialized,
            pending_count=len(candidates), attempted_count=attempted, sent_count=sent,
            failed_count=failed, retryable_remaining=aggregate["total_pending"],
            earliest_next_attempt_at=aggregate["earliest_next_attempt_at"],
            directions_represented=tuple(sorted(directions)),
            prediction_buckets_represented=tuple(buckets), writes_enabled=True,
            telegram_calls_attempted=attempted, code_version=code_version,
            failures=tuple(failures))


async def execute_telegram_status(
    db, secrets: Secrets, *, now: datetime,
) -> TelegramStatusReport:
    """Strictly read-only status: no lock, no schema creation, no writes."""
    chat_id = secrets.telegram_chat_id
    if not isinstance(chat_id, str) or not chat_id.strip():
        raise TelegramCliError("TELEGRAM_CHAT_ID is not configured")
    channel = CHANNEL_TELEGRAM
    recipient_fingerprint = compute_recipient_fingerprint(chat_id)

    schema_state = await db.fetch_telegram_schema_state()
    if not all(schema_state.values()):
        return TelegramStatusReport(
            state=STATUS_NOT_INITIALIZED, notifier_initialized=False, started_at=None,
            channel=channel, recipient_fingerprint=recipient_fingerprint,
            total_pending=0, due_pending=0, total_sent=0, last_sent_at=None,
            earliest_next_attempt_at=None)

    started_at = await db.fetch_telegram_notifier_started_at(
        runner_name=NOTIFIER_RUNNER_NAME, channel=channel,
        recipient_fingerprint=recipient_fingerprint)
    aggregate = await db.fetch_telegram_notifier_status(
        channel=channel, recipient_fingerprint=recipient_fingerprint, now=now)
    return TelegramStatusReport(
        state=STATUS_READY, notifier_initialized=(started_at is not None),
        started_at=started_at, channel=channel, recipient_fingerprint=recipient_fingerprint,
        total_pending=aggregate["total_pending"], due_pending=aggregate["due_pending"],
        total_sent=aggregate["total_sent"], last_sent_at=aggregate["last_sent_at"],
        earliest_next_attempt_at=aggregate["earliest_next_attempt_at"])


# ============================================================================
# JSON views (no secrets, no consensus snapshot)
# ============================================================================
def _iso_utc(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if not isinstance(dt, datetime) or dt.tzinfo is None:
        raise TelegramCliError("expected a timezone-aware datetime in a report")
    return dt.astimezone(timezone.utc).isoformat()


def execution_report_to_jsonable(report: TelegramExecutionReport) -> dict:
    return {
        "command": report.command,
        "lock_status": report.lock_status,
        "bootstrap_status": report.bootstrap_status,
        "channel": report.channel,
        "recipient_fingerprint": report.recipient_fingerprint,
        "scan_limit": report.scan_limit,
        "send_limit": report.send_limit,
        "outbox_rows_materialized": report.materialized_count,
        "pending_rows_discovered": report.pending_count,
        "deliveries_attempted": report.attempted_count,
        "deliveries_sent": report.sent_count,
        "deliveries_failed": report.failed_count,
        "retryable_remaining": report.retryable_remaining,
        "earliest_next_attempt_at": _iso_utc(report.earliest_next_attempt_at),
        "directions_represented": list(report.directions_represented),
        "prediction_buckets_represented": [_iso_utc(b) for b in report.prediction_buckets_represented],
        "writes_enabled": report.writes_enabled,
        "telegram_calls_attempted": report.telegram_calls_attempted,
        "code_version": report.code_version,
        "failures": [
            {"bucket_ts": _iso_utc(f["bucket_ts"]), "error_class": f["error_class"],
             "error_summary": f["error_summary"]}
            for f in report.failures],
    }


def status_report_to_jsonable(report: TelegramStatusReport) -> dict:
    return {
        "state": report.state,
        "notifier_initialized": report.notifier_initialized,
        "started_at": _iso_utc(report.started_at),
        "channel": report.channel,
        "recipient_fingerprint": report.recipient_fingerprint,
        "total_pending": report.total_pending,
        "due_pending": report.due_pending,
        "total_sent": report.total_sent,
        "last_sent_at": _iso_utc(report.last_sent_at),
        "earliest_next_attempt_at": _iso_utc(report.earliest_next_attempt_at),
    }


def render_execution_report_json(report: TelegramExecutionReport) -> str:
    return json.dumps(execution_report_to_jsonable(report), sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def render_status_report_json(report: TelegramStatusReport) -> str:
    return json.dumps(status_report_to_jsonable(report), sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


# ============================================================================
# Human views
# ============================================================================
def _fmt(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, datetime):
        return _iso_utc(value)
    return str(value)


def render_execution_report(report: TelegramExecutionReport) -> str:
    lines = [
        "=== TELEGRAM ONCE ===",
        f"lock:             {report.lock_status}",
        f"bootstrap:        {_fmt(report.bootstrap_status)}",
        f"channel:          {report.channel} (recipient={report.recipient_fingerprint[:12]}...)",
        f"writes_enabled:   {_fmt(report.writes_enabled)}",
        f"scan/send limit:  {report.scan_limit}/{report.send_limit}",
        f"materialized:     {report.materialized_count}",
        f"pending:          {report.pending_count}",
        f"attempted/sent/failed: {report.attempted_count}/{report.sent_count}/{report.failed_count}",
        f"retryable remaining: {report.retryable_remaining}",
        f"earliest next attempt: {_fmt(report.earliest_next_attempt_at)}",
        f"directions:       {', '.join(report.directions_represented) or '(none)'}",
        f"code_version:     {_fmt(report.code_version)}",
    ]
    if report.failures:
        lines.append("failures:")
        for f in report.failures:
            lines.append(f"  {_fmt(f['bucket_ts'])} {f['error_class']}: {f['error_summary']}")
    return "\n".join(lines)


def render_status_report(report: TelegramStatusReport) -> str:
    return "\n".join([
        "=== TELEGRAM STATUS ===",
        f"state:            {report.state}",
        f"notifier_initialized: {_fmt(report.notifier_initialized)}",
        f"started_at:       {_fmt(report.started_at)}",
        f"channel:          {report.channel} (recipient={report.recipient_fingerprint[:12]}...)",
        f"total_pending:    {report.total_pending}",
        f"due_pending:      {report.due_pending}",
        f"total_sent:       {report.total_sent}",
        f"last_sent_at:     {_fmt(report.last_sent_at)}",
        f"earliest_next_attempt_at: {_fmt(report.earliest_next_attempt_at)}",
    ])


# ============================================================================
# CLI command dispatch (connection lifecycle)
# ============================================================================
async def run_telegram_cli_command(args, stage1_config: Config, secrets: Secrets) -> None:
    """Connect a Database (PostgreSQL only — never Redis), run exactly one
    selected Telegram command, render+print, and always close the pool.
    Command failures propagate; no success report is printed after an
    exception."""
    db = Database(secrets.postgres_dsn)
    await db.connect()
    try:
        use_json = bool(getattr(args, "telegram_json", False))
        if args.telegram_status:
            status = await execute_telegram_status(db, secrets, now=datetime.now(timezone.utc))
            output = render_status_report_json(status) if use_json else render_status_report(status)
        elif args.telegram_once:
            max_scan = getattr(args, "telegram_max_scan", None)
            max_send = getattr(args, "telegram_max_send", None)
            report = await execute_telegram_once(
                db, stage1_config, secrets, now=datetime.now(timezone.utc),
                max_scan=max_scan, max_send=max_send)
            output = render_execution_report_json(report) if use_json else render_execution_report(report)
        elif getattr(args, "telegram_test", False):
            from notifications.telegram_client import TelegramSender
            token, chat_id = _resolve_secrets(secrets)
            sender = TelegramSender(token)
            html = ("\U0001F7E2 Signalbot Telegram notifier — connectivity test.\n"
                    "This message performs NO outbox mutation and no forecast lookup.")
            result = await sender.send_message(chat_id=chat_id, html=html)
            payload = {"command": TELEGRAM_TEST, "sent": True, "telegram_message_id": result.message_id}
            output = (json.dumps(payload, sort_keys=True, separators=(",", ":")) if use_json
                      else f"=== TELEGRAM TEST ===\nsent: yes\nmessage_id: {result.message_id}")
        else:
            raise TelegramCliError("no telegram command selected")
        print(output)
    finally:
        await db.close()
