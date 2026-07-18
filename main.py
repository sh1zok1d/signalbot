"""
Stage 1 entrypoint: data_ingestion + backfill + storage.

Run:
    python main.py                 # backfill (if needed) then start live ingestion
    python main.py --backfill-only # run backfill and exit, don't start live WS
    python main.py --skip-backfill # skip backfill, go straight to live ingestion
    python main.py --validate      # read-only data validation report, then exit

Telegram / signal_engine / percentile_engine are NOT part of this stage per
the spec's staged rollout - this process only ingests, backfills, and
persists. Confirm this stage looks right before we move to stage 2
(percentile_engine + signal_engine).
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal

from common.config import Config, load_secrets
from common.logging_setup import setup_logging
from storage.db import Database
from storage.redis_client import RedisState
from backfill.backfill import run_backfill, run_gap_fill
from data_ingestion.manager import IngestionManager
from storage.validate import validate_ingestion

logger = logging.getLogger("main")


async def run(args: argparse.Namespace) -> None:
    cfg = Config.load()
    secrets = load_secrets(cfg)

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


def main() -> None:
    parser = argparse.ArgumentParser(description="BTC signal bot - stage 1 (ingestion/backfill/storage)")
    parser.add_argument("--backfill-only", action="store_true")
    parser.add_argument("--skip-backfill", action="store_true")
    parser.add_argument("--validate", action="store_true",
                        help="Print a read-only data validation report and exit "
                             "(no backfill, no live ingestion).")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    setup_logging(args.log_level)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
