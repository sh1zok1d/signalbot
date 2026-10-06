"""Beta V0.2 operational CLI (wired into main.py; PostgreSQL only, never Redis).

  --beta-bootstrap      bounded, resumable, oldest-first 30d tape history (no rules/forecast/Telegram)
  --beta-once           detector pass: newest closed bucket(s) -> tape + episodes + push decisions
                        (--beta-bucket-ts X: one explicit bucket; an already-decided bucket runs a
                        correction check that can only APPEND a tape revision)
  --beta-status         READ-ONLY status + 7-day soak metrics
  --beta-outcomes-once  forward outcome tracker pass
  --beta-notify-once    outbox pass (at most one send attempt per user per notification)
  --beta-health         READ-ONLY health / owner-alert evaluation
  --beta-history-sync   fetch / verify / upsert Binance Vision history (5m klines 2020→, OI 2020-09→)
  --beta-history-build  nightly statistics build (range model, levels, analogues, events)
  --beta-bootstrap-rewind  rewind the bootstrap watermark 30 days (then run the bootstrap runner)
  --beta-feeds-once     research-evidence read-only public feeds (OI / long-short ratio, DVOL, depth, spot)
  --beta-stress-once    research-evidence stress hours (public aggTrades of both venues, stress hours only)

No beta command imports or invokes the frozen V1/V2 forecast engines. Stage-2
schema/revision/instrument bootstrap reuses the shadow CLI helpers unchanged.
"""
from __future__ import annotations

import json
import math
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from beta.config import BetaConfig, BetaSecrets, BetaSwitches, resolve_switches

BETA_CODE_PATHS = ("beta", "runtime/beta_cli.py", "runtime/beta_bot.py", "storage/beta_v0_store.py",
                   "storage/beta_v0_schema.sql", "config/beta_v0.yaml", "config/beta_calendar.yaml")
BETA_COMMAND_FLAGS = ("beta_bootstrap", "beta_once", "beta_status", "beta_outcomes_once",
                      "beta_notify_once", "beta_health", "beta_usage_report",
                      "beta_d7_once", "beta_d7_backfill", "beta_context_dry_run", "beta_c1_replay",
                      "beta_history_sync", "beta_history_build", "beta_bootstrap_rewind",
                      "beta_feeds_once", "beta_stress_once", "beta_claims_report")
READ_ONLY_COMMANDS = ("beta_status", "beta_health", "beta_usage_report", "beta_context_dry_run", "beta_c1_replay",
                      "beta_claims_report")


# A feed job refused to run: its schema, columns, checks or grants are missing, or it is connected
# as another DB role than the unit expects (deploy plan PREREQ-1 / PREREQ-3). Exit code 3.
FAIL_CLOSED_STATUSES = ("SCHEMA_NOT_READY", "WRONG_DB_ROLE")
# Set by the feed units (deploy/signalbot-beta-{feeds,stress}.service): the DB role they must run as.
FEEDS_ROLE_ENV = "BETA_FEEDS_EXPECTED_DB_ROLE"


class BetaCliError(RuntimeError):
    pass


# ---- argparse wiring --------------------------------------------------------------
def add_beta_arguments(parser) -> None:
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--beta-bootstrap", action="store_true",
                   help="Beta V0.2: bounded resumable 30d state-tape history bootstrap.")
    g.add_argument("--beta-once", action="store_true",
                   help="Beta V0.2: one detector pass (tape + episodes + push decisions).")
    g.add_argument("--beta-status", action="store_true",
                   help="Beta V0.2: READ-ONLY status and soak metrics.")
    g.add_argument("--beta-outcomes-once", action="store_true",
                   help="Beta V0.2: one forward-outcome tracker pass.")
    g.add_argument("--beta-notify-once", action="store_true",
                   help="Beta V0.2: one notification outbox pass.")
    g.add_argument("--beta-health", action="store_true",
                   help="Beta V0.2: READ-ONLY health report.")
    g.add_argument("--beta-usage-report", action="store_true",
                   help="Beta V0.2: READ-ONLY usage report (fingerprints only).")
    g.add_argument("--beta-d7-once", action="store_true",
                   help="Beta V0.2: one D7 hour pass (closed 1m bars + missing hour states).")
    g.add_argument("--beta-d7-backfill", action="store_true",
                   help="Beta V0.2: resumable D7 1m backfill (default 90 days) and hour states.")
    g.add_argument("--beta-context-dry-run", action="store_true",
                   help="Beta: READ-ONLY recorded-tape dry run of the 1h/4h interpretation labels.")
    g.add_argument("--beta-c1-replay", action="store_true",
                   help="Beta: READ-ONLY replay of recorded tape under C0 (context V2) and C1 (V3) side by side.")
    g.add_argument("--beta-history-sync", action="store_true",
                   help="Beta V2: fetch, verify and upsert the Binance Vision history (resumable).")
    g.add_argument("--beta-history-build", action="store_true",
                   help="Beta V2: build the decision-support statistics from the stored history.")
    g.add_argument("--beta-bootstrap-rewind", action="store_true",
                   help="Beta V2: rewind the bootstrap watermark so the bootstrap refills 30 days of V2 tape.")
    g.add_argument("--beta-feeds-once", action="store_true",
                   help="Beta: one pass of the research-evidence read-only public feeds.")
    g.add_argument("--beta-stress-once", action="store_true",
                   help="Beta: check the last completed hours for DH3-S stress hours (public aggTrades).")
    g.add_argument("--beta-claims-report", action="store_true",
                   help="Beta: READ-ONLY claim journal report per cohort (docs/BETA_CLAIM_JOURNAL_DESIGN_V1.md).")
    parser.add_argument("--history-max-objects", type=int, default=None,
                        help="Bound one --beta-history-sync run to N archive objects (default: all).")
    parser.add_argument("--beta-bucket-ts", default=None,
                        help="Explicit ISO-8601 UTC 5m bucket open (--beta-once only).")
    parser.add_argument("--days", type=int, default=None,
                        help="D7 backfill length in days (--beta-d7-backfill only; default 90).")
    parser.add_argument("--dry-run-days", type=int, default=7,
                        help="Days of recorded tape to sample (--beta-context-dry-run only).")
    parser.add_argument("--dry-run-stride", type=int, default=12,
                        help="Sample every N 5m buckets (--beta-context-dry-run only; 12 = hourly).")
    parser.add_argument("--dry-run-provisional", action="store_true",
                        help="Rank against existing history, ignoring the maturity tiers (PROVISIONAL).")
    parser.add_argument("--claims-days", type=int, default=30,
                        help="Days of journaled claims to report (--beta-claims-report only; default 30).")
    parser.add_argument("--beta-json", action="store_true",
                        help="Emit the beta report as one JSON object (all --beta-* commands).")


def is_beta_command(args) -> bool:
    return any(getattr(args, f, False) for f in BETA_COMMAND_FLAGS)


def validate_beta_args(parser, args, *, other_command_selected: bool) -> None:
    selected = is_beta_command(args)
    if selected:
        for flag, value in (("--validate", getattr(args, "validate", False)),
                            ("--backfill-only", getattr(args, "backfill_only", False)),
                            ("--skip-backfill", getattr(args, "skip_backfill", False))):
            if value:
                parser.error(f"{flag} cannot be combined with a --beta-* command")
        if other_command_selected:
            parser.error("a --beta-* command cannot be combined with a --shadow-*/--telegram-* command")
    if getattr(args, "beta_bucket_ts", None) is not None and not getattr(args, "beta_once", False):
        parser.error("--beta-bucket-ts is only valid with --beta-once")
    if getattr(args, "days", None) is not None and not getattr(args, "beta_d7_backfill", False):
        parser.error("--days is only valid with --beta-d7-backfill")
    if getattr(args, "beta_d7_backfill", False) and args.days is not None and args.days < 1:
        parser.error("--days must be an int >= 1")
    dry = getattr(args, "beta_context_dry_run", False) or getattr(args, "beta_c1_replay", False)
    if getattr(args, "dry_run_provisional", False) and not getattr(args, "beta_context_dry_run", False):
        parser.error("--dry-run-provisional is only valid with --beta-context-dry-run")
    if dry and (args.dry_run_days < 1 or args.dry_run_days > 30 or args.dry_run_stride < 1):
        parser.error("--dry-run-days must be 1..30 and --dry-run-stride >= 1")
    if getattr(args, "history_max_objects", None) is not None and not getattr(args, "beta_history_sync", False):
        parser.error("--history-max-objects is only valid with --beta-history-sync")
    if getattr(args, "history_max_objects", None) is not None and args.history_max_objects < 1:
        parser.error("--history-max-objects must be an int >= 1")
    if getattr(args, "beta_json", False) and not selected:
        parser.error("--beta-json is only valid with a --beta-* command")


def parse_bucket(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise BetaCliError("--beta-bucket-ts must be UTC (Z or +00:00)")
    if dt.second or dt.microsecond or dt.minute % 5:
        raise BetaCliError("--beta-bucket-ts must be aligned to the 5m grid")
    return dt


# ---- helpers ----------------------------------------------------------------------
def load_postgres_dsn() -> str:
    from common.config import _build_postgres_dsn
    return _build_postgres_dsn()


def resolve_beta_code_version() -> str:
    from common.versioning import resolve_feature_code_version
    return resolve_feature_code_version(env_var="BETA_CODE_VERSION", paths=BETA_CODE_PATHS)


def to_jsonable(v: Any):
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, dict):
        return {str(k): to_jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [to_jsonable(x) for x in v]
    if hasattr(v, "__dataclass_fields__"):
        return to_jsonable(v.__dict__)
    return v


def render(report: dict, *, as_json: bool) -> str:
    data = to_jsonable(report)
    if as_json:
        return json.dumps(data, sort_keys=True)
    return json.dumps(data, sort_keys=True, indent=2)


async def prepare_stage2(db, stage2_config, cfg: BetaConfig, *, metadata_fetch_json=None) -> None:
    """Explicit Stage-2 prerequisites for raw-bundle reads (same order as the
    shadow path), then the additive beta schema. Works with stage2.enabled=false."""
    from runtime.shadow_cli import _bootstrap_instrument_metadata, _bootstrap_stage2_schema_and_revision
    from symbols.registry import symbol_exchange_capability_seed_rows, symbol_seed_rows
    await _bootstrap_stage2_schema_and_revision(db, stage2_config, cfg.symbol)
    await db.seed_symbols(symbol_seed_rows())
    await db.seed_symbol_exchange_capabilities(symbol_exchange_capability_seed_rows())
    await _bootstrap_instrument_metadata(db, list(cfg.exchanges), cfg.symbol,
                                         metadata_fetch_json=metadata_fetch_json)
    await db.init_beta_v0_schema()


def build_detector_deps(db, stage2_config, cfg: BetaConfig, *, clock, code_version: str,
                        feature_code_version: str):
    from beta.detector import DetectorDeps

    async def declared(exchanges):
        return dict(await db.fetch_shadow_liquidation_availability(
            exchanges=list(exchanges), symbol=cfg.symbol, market_type=cfg.market_type))

    async def raw_revision():
        return await db.fetch_stage2_raw_revision(symbol=cfg.symbol, market_type=cfg.market_type)

    from beta.recovery import read_host_boot_time
    return DetectorDeps(reader=db, store=db.beta_store(), stage2_config=stage2_config,
                        declared_liquidation_available=declared, raw_revision=raw_revision,
                        clock=clock, code_version=code_version,
                        feature_code_version=feature_code_version,
                        host_boot_time=read_host_boot_time())


async def soak_metrics(conn, cfg: BetaConfig, now: datetime, days: int = 7) -> dict:
    since = now - timedelta(days=days)
    tape = await conn.count_tape(symbol=cfg.symbol, since=since)
    counts = await conn.episode_counts(symbol=cfg.symbol, since=since)
    for c in counts:
        c["armed_to_triggered_conversion"] = (c["triggered"] / c["armed"]) if c["armed"] else None
    latest = await conn.fetch_latest_live_tape(symbol=cfg.symbol)
    maturity = {}
    if latest and latest["snapshot"].get("rule_evaluations"):
        maturity = {k: (v["status"], v["reason"]) for k, v in latest["snapshot"]["rule_evaluations"].items()}
    n = tape["n"] or 0
    return {"window_days": days, "live_evaluations": n,
            "evaluations_per_day": n / days, "materialized": tape["materialized"],
            "fresh": tape["fresh"], "data_degraded_fraction": (1 - tape["fresh"] / n) if n else None,
            "episodes_by_event_type": counts,
            "push_decisions": await conn.push_decision_counts(since=since),
            "cap_activation_days": await conn.cap_activation_days(since=since),
            "deliveries": await conn.delivery_state_counts(since=since),
            "feedback": await conn.feedback_counts(), "latest_rule_maturity": maturity}


# ---- entry ------------------------------------------------------------------------
async def run_beta_cli_command(args, stage1_config=None, secrets=None, *, db=None, env=None,
                               clock=None, metadata_fetch_json=None, sender=None) -> dict:
    """Execute exactly one --beta-* command; prints and returns the report."""
    from common.stage2_config import Stage2Config
    from common.versioning import resolve_feature_code_version
    cfg = BetaConfig.load()
    switches = resolve_switches(cfg, env)
    clock = clock or (lambda: datetime.now(timezone.utc))
    own_db = db is None
    if own_db:
        from storage.db import Database
        dsn = getattr(secrets, "postgres_dsn", None) or load_postgres_dsn()
        db = Database(dsn)
        try:
            await db.connect()
        except Exception as exc:  # noqa: BLE001 - DB unavailable is a reportable state
            report = {"command": _command_name(args), "status": "DB_UNAVAILABLE",
                      "error_type": type(exc).__name__}
            print(render(report, as_json=bool(getattr(args, "beta_json", False))))
            raise SystemExit(2)
    try:
        report = await _dispatch(args, db, cfg, switches, clock, Stage2Config,
                                 resolve_feature_code_version, metadata_fetch_json, sender, env)
    finally:
        if own_db:
            await db.close()
    report = {"command": _command_name(args), "switches": switches.as_dict(),
              "rules_version": cfg.rules_version, "rules_digest": cfg.rules_digest, **report}
    print(render(report, as_json=bool(getattr(args, "beta_json", False))))
    if report.get("status") in FAIL_CLOSED_STATUSES:
        raise SystemExit(3)                                   # the unit fails visibly; nothing was written
    return report


def _command_name(args) -> str:
    return next(("--" + f.replace("_", "-") for f in BETA_COMMAND_FLAGS if getattr(args, f, False)), "")


async def _dispatch(args, db, cfg, switches: BetaSwitches, clock, Stage2Config,
                    resolve_feature_code_version, metadata_fetch_json, sender, env) -> dict:
    from beta.admin import collect_health, collect_status
    if getattr(args, "beta_c1_replay", False):
        from beta.c1_replay import run_c1_replay_from_db
        store = db.beta_store()
        async with store.connect() as conn:
            if not await conn.schema_present():
                return {"status": "NOT_INITIALIZED"}
            return {"status": "OK", "c1_replay": await run_c1_replay_from_db(
                conn, cfg, Stage2Config.load(), end=clock(), days=args.dry_run_days,
                stride_buckets=args.dry_run_stride)}
    if getattr(args, "beta_context_dry_run", False):
        from beta.dry_run import run_dry_run_from_db
        store = db.beta_store()
        async with store.connect() as conn:
            if not await conn.schema_present():
                return {"status": "NOT_INITIALIZED"}
            report = await run_dry_run_from_db(
                conn, cfg, Stage2Config.load(), end=clock(), days=args.dry_run_days,
                stride_buckets=args.dry_run_stride, ignore_maturity=args.dry_run_provisional)
            return {"status": "OK", "dry_run": report}
    if args.beta_claims_report:
        store = db.beta_store()
        async with store.connect() as conn:
            if not await conn.schema_present():
                return {"status": "NOT_INITIALIZED"}
            from beta.claims import claims_report
            since = clock() - timedelta(days=max(1, int(args.claims_days)))
            return {"status": "OK", "since": since.isoformat(),
                    "claims": claims_report(await conn.fetch_claim_cohort(since=since))}
    if args.beta_status or args.beta_health or args.beta_usage_report:
        store = db.beta_store()
        async with store.connect() as conn:
            if not await conn.schema_present():
                return {"status": "NOT_INITIALIZED"}
            now = clock()
            if args.beta_usage_report:
                from beta.usage import build_usage_report
                owner = BetaSecrets.from_env(env).owner_user_id
                usage = build_usage_report(await conn.usage_facts(), now=now, owner_user_id=owner)
                return {"status": "OK", "usage": usage}
            if args.beta_health:
                h = await collect_health(conn, cfg, switches, now)
                return {"status": "OK" if not h["alerts"] else "ALERTS", "health": h}
            st = await collect_status(conn, cfg, now)
            return {"status": "OK", "product_status": st["status"],
                    "open_episodes": [(e.public_id, e.event_type, e.state) for e in st["open_episodes"]],
                    "heartbeat": st["heartbeat"], "soak_metrics": await soak_metrics(conn, cfg, now)}

    if args.beta_bootstrap or args.beta_once:
        if not (switches.enabled if args.beta_bootstrap else switches.detection):
            return {"status": "DISABLED"}
        stage2_config = Stage2Config.load()
        explicit = parse_bucket(args.beta_bucket_ts) if getattr(args, "beta_bucket_ts", None) else None
        await prepare_stage2(db, stage2_config, cfg, metadata_fetch_json=metadata_fetch_json)
        deps = build_detector_deps(db, stage2_config, cfg, clock=clock,
                                   code_version=resolve_beta_code_version(),
                                   feature_code_version=resolve_feature_code_version())
        from beta.detector import run_bootstrap_once, run_detector_once
        if args.beta_bootstrap:
            return await run_bootstrap_once(deps, cfg, switches)
        return await run_detector_once(deps, cfg, switches, explicit_bucket=explicit)

    if args.beta_outcomes_once:
        if not switches.outcome_tracking:
            return {"status": "DISABLED"}
        await db.init_beta_v0_schema()
        from beta.outcomes import run_outcomes_once

        async def raw_revision():
            return await db.fetch_stage2_raw_revision(symbol=cfg.symbol, market_type=cfg.market_type)
        return await run_outcomes_once(db.beta_store(), cfg, switches, clock=clock, raw_revision=raw_revision)

    if args.beta_notify_once:
        if not switches.enabled:
            return {"status": "DISABLED"}
        if not switches.telegram:          # no-Telegram shadow soak: nothing to do, no DB access
            return {"status": "TELEGRAM_DISABLED"}
        await db.init_beta_v0_schema()
        secrets = BetaSecrets.from_env(env)
        if sender is None and secrets.bot_token:
            from runtime.beta_bot import BetaTelegramSender
            sender = BetaTelegramSender(secrets.bot_token)
        from beta.delivery import run_notify_once
        return await run_notify_once(db.beta_store(), cfg, switches, sender=sender, clock=clock,
                                     owner_user_id=secrets.owner_user_id)

    if getattr(args, "beta_history_sync", False) or getattr(args, "beta_history_build", False) \
            or getattr(args, "beta_bootstrap_rewind", False):
        if not switches.enabled:
            return {"status": "DISABLED"}
        await db.init_beta_v0_schema()
        store = db.beta_store()
        if args.beta_history_sync:
            from beta.history_data import sync_history
            return await sync_history(store, now=clock(), max_objects=getattr(args, "history_max_objects", None))
        if args.beta_history_build:
            from beta.history_stats import run_history_build
            return await run_history_build(store, cfg, now=clock())
        from beta.state_tape import BUCKET as _BUCKET, select_latest_closed_bucket
        target = select_latest_closed_bucket(clock(), grace_s=cfg["bucket_close_grace_s"])
        rewind_to = target - timedelta(days=cfg["bootstrap"]["lookback_days"]) - _BUCKET
        async with store.connect() as conn:
            prev = await conn.rewind_bootstrap_watermark(symbol=cfg.symbol, market_type=cfg.market_type,
                                                         timeframe=cfg.timeframe, bucket_ts=rewind_to)
        return {"status": "OK", "previous_watermark": prev, "rewound_to": rewind_to,
                "next": "python -m runtime.beta_bootstrap_runner"}

    if getattr(args, "beta_feeds_once", False) or getattr(args, "beta_stress_once", False):
        if not switches.enabled:
            return {"status": "DISABLED"}
        rcfg = cfg.section("decision")["research_evidence"]
        key = "feeds_enabled" if args.beta_feeds_once else "stress_hours_enabled"
        # collection never depends on presentation (decision.research_evidence.enabled /
        # BETA_RESEARCH_EVIDENCE_ENABLED): data matures before anything is shown (PREREQ-2)
        if not rcfg[key]:
            return {"status": "DISABLED", "reason": f"decision.research_evidence.{key}"}
        # no DDL here: the core role applies the schema; the feed role only verifies it (PREREQ-1)
        from beta.research_feeds import run_feeds_job, run_stress_job
        env_map = os.environ if env is None else env
        expected = (env_map.get(FEEDS_ROLE_ENV) or "").strip() or None
        if args.beta_feeds_once:
            return await run_feeds_job(db.beta_store(), now=clock(), expected_role=expected)
        return await run_stress_job(db.beta_store(), now=clock(), expected_role=expected)

    if args.beta_d7_once or args.beta_d7_backfill:
        if not switches.enabled:
            return {"status": "DISABLED"}
        await db.init_beta_v0_schema()
        from beta.regime_d7 import DEFAULT_BACKFILL_DAYS, run_d7_job
        days = DEFAULT_BACKFILL_DAYS if args.days is None else args.days
        return await run_d7_job(db.beta_store(), now=clock(),
                                mode="backfill" if args.beta_d7_backfill else "once", days=days)
    raise BetaCliError("no --beta-* command selected")
