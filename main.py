"""
Stage 1 entrypoint: data_ingestion + backfill + storage.

Run:
    python main.py                 # backfill (if needed) then start live ingestion
    python main.py --backfill-only # run backfill and exit, don't start live WS
    python main.py --skip-backfill # skip backfill, go straight to live ingestion
    python main.py --validate      # read-only data validation report, then exit
    python main.py --shadow-once   # run ONE explicit shadow forecast cycle (writes)
    python main.py --shadow-dry-run # run ONE shadow cycle, write nothing
    python main.py --shadow-status # read-only shadow status report, then exit
    python main.py --telegram-once   # send bounded pending forecast notifications
    python main.py --telegram-status # read-only Telegram notifier status, then exit

signal_engine / percentile_engine are NOT part of this stage per the spec's
staged rollout - this process only ingests, backfills, and persists. The three
--shadow-* commands are deliberate MANUAL operations that delegate to
runtime.shadow_cli; they do not activate any automatic Stage 2 runtime (Stage 2
stays globally disabled). The --telegram-* commands are a SEPARATE, isolated
notification worker (runtime.telegram_cli) with its own systemd timer and its
own PostgreSQL advisory lock — it never blocks or changes shadow prediction/
outcome processing, and NEUTRAL predictions never produce a notification.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
import sys

from common.config import Config, load_secrets
from common.logging_setup import setup_logging
from runtime.shadow_cli import is_shadow_command, run_shadow_cli_command
from runtime.telegram_cli import is_telegram_command, run_telegram_cli_command
from storage.db import Database
from storage.redis_client import RedisState
from backfill.backfill import run_backfill, run_gap_fill
from data_ingestion.manager import IngestionManager
from storage.validate import validate_ingestion

logger = logging.getLogger("main")


async def run(args: argparse.Namespace) -> None:
    cfg = Config.load()
    secrets = load_secrets(cfg)

    # A shadow command is a deliberate manual operation that branches BEFORE any
    # Stage 1 startup (schema init, capability seeding, stale-backfill sweep,
    # Redis, backfill, gap-fill, IngestionManager). Shadow commands use
    # PostgreSQL only and never connect Redis.
    if is_shadow_command(args):
        await run_shadow_cli_command(args, cfg, secrets)
        return

    # A Telegram command is the same kind of deliberate manual/timer operation,
    # fully isolated from the shadow forecast pass (separate lock, separate
    # tables, separate systemd timer). PostgreSQL only, never Redis.
    if is_telegram_command(args):
        await run_telegram_cli_command(args, cfg, secrets)
        return

    db = Database(secrets.postgres_dsn)
    await db.connect()
    await db.init_schema()
    # Seed the structural capability registry so downstream (validate,
    # signal_engine) reads it from the DB, not from the WS client classes.
    from common.capabilities import capabilities_rows
    await db.seed_capabilities(capabilities_rows(), enabled_exchanges=cfg.enabled_exchanges)
    # Sweep any 'running' backfill rows left by a prior interrupted process so
    # bookkeeping is honest and those sources get re-run.
    swept = await db.cancel_stale_backfill_runs()
    if swept and swept != "UPDATE 0":
        logger.info("Cleared stale 'running' backfill runs: %s", swept)

    redis_state = RedisState(secrets.redis_url)
    await redis_state.connect()

    # Install the stop signal handlers UP FRONT so a SIGINT during backfill or
    # gap-fill (not just live) triggers a graceful, cancelling shutdown — the
    # in-flight query unwinds through `async with pool.acquire()` (rollback)
    # and db.close() force-closes the pool, leaving no idle-in-transaction
    # backends or ungranted locks behind.
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:  # e.g. non-main-thread / Windows
            pass

    manager = None
    try:
        if args.validate:
            await validate_ingestion(db, cfg, redis=redis_state)
            return

        if not args.skip_backfill:
            await _run_cancellable(
                run_backfill(db=db, symbol=cfg.symbol, exchanges=cfg.enabled_exchanges,
                             window_days=cfg["backfill"]["window_days"]),
                stop_event)
        else:
            logger.info("Skipping backfill (--skip-backfill)")

        if stop_event.is_set():
            logger.info("Stop requested during backfill; shutting down.")
            return

        if args.backfill_only:
            logger.info("Backfill-only run requested, exiting without starting live ingestion")
            return

        # Close the residual klines gap between the newest stored bar and the
        # current closed minute right before going live, so the series is
        # continuous across the backfill/skip-backfill -> live handoff.
        await _run_cancellable(
            run_gap_fill(db, symbol=cfg.symbol, exchanges=cfg.enabled_exchanges), stop_event)
        if stop_event.is_set():
            logger.info("Stop requested during gap-fill; shutting down.")
            return

        manager = IngestionManager(cfg, db, redis_state)
        await manager.start()

        logger.info("Live ingestion running. Ctrl+C to stop.")
        await stop_event.wait()
        logger.info("Shutting down...")
    finally:
        if manager is not None:
            await manager.stop()
        await redis_state.close()
        await db.close()


async def _run_cancellable(coro, stop_event: asyncio.Event) -> None:
    """Run `coro`, but if `stop_event` fires first, cancel it and let it unwind
    cleanly (rolling back any open DB transaction). Used so SIGINT interrupts a
    long backfill/gap-fill promptly instead of waiting for it to finish."""
    task = asyncio.ensure_future(coro)
    stopper = asyncio.ensure_future(stop_event.wait())
    try:
        await asyncio.wait({task, stopper}, return_when=asyncio.FIRST_COMPLETED)
        if task.done():
            await task  # propagate result/exception
            return
        # Stop requested first: cancel the workload and await its unwind.
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    finally:
        stopper.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await stopper


def build_parser() -> argparse.ArgumentParser:
    """Construct the flag-based CLI parser (no argparse subcommands). Extracted so
    parser behavior is unit-testable; main() adds nothing beyond this + the
    cross-flag validation below."""
    parser = argparse.ArgumentParser(description="BTC signal bot - stage 1 (ingestion/backfill/storage)")
    parser.add_argument("--backfill-only", action="store_true")
    parser.add_argument("--skip-backfill", action="store_true")
    parser.add_argument("--validate", action="store_true",
                        help="Print a read-only data validation report and exit "
                             "(no backfill, no live ingestion).")
    parser.add_argument("--log-level", default="INFO")

    # Three mutually-exclusive deliberate manual shadow commands (delegated to
    # runtime.shadow_cli). argparse enforces one-of; cross-flag rules below.
    shadow = parser.add_mutually_exclusive_group()
    shadow.add_argument("--shadow-once", action="store_true",
                        help="Run ONE explicit shadow forecast cycle (writes Stage 2 rows).")
    shadow.add_argument("--shadow-dry-run", action="store_true",
                        help="Run ONE shadow forecast cycle but persist nothing.")
    shadow.add_argument("--shadow-status", action="store_true",
                        help="Print a read-only shadow status report and exit.")

    # Shadow-only options. Default None so we can tell whether they were supplied;
    # reference exchange defaults to binance at execution time when omitted.
    parser.add_argument("--shadow-bucket-ts", default=None,
                        help="Explicit ISO-8601 UTC 5m bucket open (shadow-once/dry-run only).")
    parser.add_argument("--shadow-reference-exchange", default=None,
                        help="Reference exchange for the prediction (default: binance; "
                             "shadow-once/dry-run only).")
    parser.add_argument("--shadow-code-version", default=None,
                        help="Explicit analytics code version (shadow-once/dry-run only).")
    parser.add_argument("--shadow-json", action="store_true",
                        help="Emit the shadow report as one JSON object (all shadow commands).")
    # Automatic-recovery caps (--shadow-once WITHOUT --shadow-bucket-ts only).
    parser.add_argument("--shadow-max-catchup-buckets", type=int, default=None,
                        help="Max missed 5m prediction buckets to recover this run "
                             "(automatic --shadow-once only; default 12).")
    parser.add_argument("--shadow-max-outcome-jobs", type=int, default=None,
                        help="Max due outcome evaluations this run "
                             "(automatic --shadow-once only; default 100).")

    # Three mutually-exclusive deliberate Telegram notifier commands (delegated
    # to runtime.telegram_cli). Fully isolated from the shadow group above —
    # cross-group exclusivity is enforced manually below.
    telegram = parser.add_mutually_exclusive_group()
    telegram.add_argument("--telegram-once", action="store_true",
                          help="Send bounded pending Telegram forecast notifications.")
    telegram.add_argument("--telegram-status", action="store_true",
                          help="Print a read-only Telegram notifier status report and exit.")
    telegram.add_argument("--telegram-test", action="store_true",
                          help="Send ONE fixed connectivity-test message (no outbox mutation).")

    parser.add_argument("--telegram-json", action="store_true",
                        help="Emit the Telegram report as one JSON object (all telegram commands).")
    parser.add_argument("--telegram-max-scan", type=int, default=None,
                        help="Max forecast_predictions rows to scan for materialization "
                             "(--telegram-once only; default 200).")
    parser.add_argument("--telegram-max-send", type=int, default=None,
                        help="Max pending deliveries to attempt this run "
                             "(--telegram-once only; default 20).")
    return parser


def _validate_shadow_arg_combos(parser: argparse.ArgumentParser,
                                args: argparse.Namespace) -> None:
    """Enforce the flag-compatibility rules argparse cannot express directly."""
    shadow_selected = is_shadow_command(args)
    execution_shadow = bool(args.shadow_once or args.shadow_dry_run)
    telegram_selected = is_telegram_command(args)

    if shadow_selected:
        for flag, value in (("--validate", args.validate),
                            ("--backfill-only", args.backfill_only),
                            ("--skip-backfill", args.skip_backfill)):
            if value:
                parser.error(f"{flag} cannot be combined with a --shadow-* command")

    # bucket-ts / reference-exchange / code-version are only valid for
    # shadow-once / shadow-dry-run.
    for flag, value in (("--shadow-bucket-ts", args.shadow_bucket_ts),
                        ("--shadow-reference-exchange", args.shadow_reference_exchange),
                        ("--shadow-code-version", args.shadow_code_version)):
        if value is not None and not execution_shadow:
            parser.error(f"{flag} is only valid with --shadow-once or --shadow-dry-run")

    if args.shadow_json and not shadow_selected:
        parser.error("--shadow-json is only valid with a --shadow-* command")

    # Automatic-recovery caps apply only to automatic --shadow-once (no explicit
    # bucket, which does deterministic one-bucket work with no catch-up).
    for flag, value in (("--shadow-max-catchup-buckets", args.shadow_max_catchup_buckets),
                        ("--shadow-max-outcome-jobs", args.shadow_max_outcome_jobs)):
        if value is not None:
            if not args.shadow_once:
                parser.error(f"{flag} is only valid with --shadow-once")
            if args.shadow_bucket_ts is not None:
                parser.error(f"{flag} is not valid with --shadow-bucket-ts "
                             "(an explicit bucket performs no catch-up)")

    # Telegram commands are fully isolated: never combined with a shadow
    # command, --validate, --backfill-only, or --skip-backfill.
    if telegram_selected:
        for flag, value in (("--validate", args.validate),
                            ("--backfill-only", args.backfill_only),
                            ("--skip-backfill", args.skip_backfill)):
            if value:
                parser.error(f"{flag} cannot be combined with a --telegram-* command")
        if shadow_selected:
            parser.error("a --telegram-* command cannot be combined with a --shadow-* command")

    if args.telegram_json and not telegram_selected:
        parser.error("--telegram-json is only valid with a --telegram-* command")

    # Scan/send caps apply only to --telegram-once.
    for flag, value in (("--telegram-max-scan", args.telegram_max_scan),
                        ("--telegram-max-send", args.telegram_max_send)):
        if value is not None and not args.telegram_once:
            parser.error(f"{flag} is only valid with --telegram-once")


def parse_args(argv=None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    _validate_shadow_arg_combos(parser, args)
    return args


def configure_cli_logging(args: argparse.Namespace) -> None:
    """Configure logging for a CLI invocation.

    Normally identical to `setup_logging(args.log_level)` — Stage 1 commands and
    human shadow/telegram commands keep their existing stdout logging behavior
    untouched.

    For a `--shadow-json` or `--telegram-json` command, stdout must carry
    exactly one machine-readable JSON object, so logging stays fully ENABLED
    but the root StreamHandler(s) currently targeting stdout are redirected to
    stderr (logs are never disabled or discarded; the format is not
    duplicated; normal Stage 1 logs are not moved).
    """
    setup_logging(args.log_level)
    if getattr(args, "shadow_json", False) or getattr(args, "telegram_json", False):
        root = logging.getLogger()
        for handler in root.handlers:
            if isinstance(handler, logging.StreamHandler) \
                    and getattr(handler, "stream", None) is sys.stdout:
                handler.setStream(sys.stderr)


def main() -> None:
    args = parse_args()

    configure_cli_logging(args)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
