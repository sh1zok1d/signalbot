# Private Beta V0.2 — deploy, soak and privacy runbook

Authority: `docs/PRIVATE_BETA_V0_RESTART_DECISION.md`. The systemd artifacts are **prepared but not activated**. Activation is a separate, owner-authorized step.

## Units (`deploy/`)

| Unit | Schedule | Command |
|---|---|---|
| `signalbot-beta-detector.service` + `.timer` | every 5m at :25 s | `main.py --beta-once --beta-json` |
| `signalbot-beta-outcomes.service` + `.timer` | every 5m at :50 s (offset 2m) | `main.py --beta-outcomes-once --beta-json` |
| `signalbot-beta-notify.service` + `.timer` | every minute at :40 s | `main.py --beta-notify-once --beta-json` |
| `signalbot-beta-bot.service` | long-running (Restart=on-failure) | `python -m runtime.beta_bot` |

- `deploy/install_beta_units.sh` copies the units and runs `daemon-reload`. It **never enables or starts** anything.
- `deploy/check_beta_units.sh` is read-only.
- The detector and outcomes units wait for PostgreSQL first (`ExecStartPre=deploy/wait_for_infra.py --postgres-only --timeout 60`, the same readiness gate `signalbot.service` uses, minus Redis).
- The bounded history bootstrap is run manually with `python -m runtime.beta_bootstrap_runner [--max-iterations N]` (default 40, cap 100; 30 days need 31 batches of `bootstrap.max_buckets_per_run` = 288). Each iteration runs the unchanged `main.py --beta-bootstrap --beta-json` and prints progress. The runner stops on the first error, and fails if the bootstrap is still incomplete at the bound. After completion it runs one extra bootstrap as an idempotency check, which may only write buckets that closed in the meantime. Exit codes: `0` verified, `2` bootstrap error, `3` iteration limit, `4` verification failed.

## Temporal context (`/btc`)

`--beta-once` also advances the context projection (`beta_context_snapshots`) inside each bucket's transaction, and `/btc` records what it showed (`beta_btc_views`). See `docs/BETA_BTC_TEMPORAL_CONTEXT_V0.md`. There is no new unit and no new command.

## Warm-up and detector readiness

A fresh deployment has a **warm-up period**. Readiness follows the accumulated **valid history** recorded on the state tape, not the calendar. A family becomes ready when every percentile it needs has a valid sample exactly one maturity span (30 days, the Stage-2 confidence-tier setting) before the latest bucket, and its venue and eligibility gates pass. Gaps delay readiness; a fixed date is never promised.

**What is available when:**
- **Right after the bootstrap:** the kline-derived context, meaning NOW (price, range, volume) and the rolling 1h context.
- **Not yet:**
  - **Price/OI families** (price+OI contraction, build-up/compression) need live OI history. The historical 5m OI sources cannot reproduce the within-bucket OI change, so the bootstrap adds no OI history.
  - **Taker flow** needs live multi-venue taker history.
  - **Liquidations** need live liquidation feeds plus live eligibility (healthy live bars, no outage) on at least two venues.

**How `/btc` shows it:**
- A **Detector readiness** block appears unless every family is ready. Each family is one of:
  - `ready`;
  - `history building · <input> <span> / 30d`, where the span is the earliest valid sample to the latest bucket, floored to 0.1 day;
  - `data unavailable · <reason>`;
  - `degraded · <reason>`;
  - `disabled`.
- The **Readiness** button shows the per-rule tier, sample count, span and venue eligibility.
- **Headline precedence:** DATA STALE, then DATA DEGRADED, then WATCH / EVENT ACTIVE, then HISTORY BUILDING (or DETECTOR NOT READY), then NO ACTIVE EVENTS. NO ACTIVE EVENTS is shown only when the Price/OI families are actually evaluable.
- **Absence of an event is not a negative detector decision** until the relevant family is `ready`. A valid event from a ready family is always shown, even while other families are still building.
- **No pushes:** readiness changes never send notifications.

**Soak planning:** until the Price/OI families are ready, the soak cannot observe core events. Start judging event behaviour from the first bucket in which the relevant family reports `ready`.

## POST-DEPLOY V2 SMOKE CHECK

Run this after the detector is active. The SQL file is read-only (`BEGIN TRANSACTION READ ONLY`). It does not read outcomes and does not compute forward returns, PnL, MAE, MFE, or hit rate. Any `FAIL` row is an operational stop.

1. `systemctl status signalbot signalbot-beta-bot`
2. `systemctl list-timers 'signalbot-beta-*'`
3. `python main.py --beta-health --beta-json`
4. Wait for 2–3 closed 5m buckets.
5. Run:

```bash
psql "$DSN" \
  -v deploy_ts='<UTC deployment timestamp>' \
  -f deploy/signalbot-beta-smoke.sql
```

`deploy_ts` is UTC, for example `2026-09-25 18:00:00+00`. The script scores 5m buckets that start at or after that time and have already closed.

6. Manual Telegram `/btc` check.

On a fresh deployment, `HISTORY BUILDING` is normal. `DETECTOR NOT READY` is also valid when live quorum or a required input is missing. `NO ACTIVE EVENTS` is not valid while the mandatory Price/OI scope is immature. The readiness Details button should work. Temporal-context Details exists only when an ACTIVE EVENT or a retained LAST EVENT exists. No temporal Details button immediately after a quiet fresh deployment is normal.

### Live OI sampling is the Day-0 gate

The current Stage-2 OI-change definition requires at least two OI observations inside a closed 5m bucket. With the unchanged ~15s Stage-1 poll, a healthy venue produces about 20 live observations per bucket. The hard correctness requirement is `>=2` usable observations on Binance, Bybit, and OKX.

If closed buckets repeatedly contain fewer than 2 live observations, do not wait for the 30-day warm-up. Treat that as an operational blocker immediately. Historical backfill cannot supply this within-bucket OI change.

A measured liquidation zero on an eligible venue is not a failure. `NULL` on an ineligible venue is UNKNOWN, not zero.

### First ~24 hours

Re-run the same script with the original `deploy_ts`. Read:

- expected vs written V2 buckets, missing buckets, revisions
- materialized rate and `evaluation_fresh` rate
- per venue: live OHLC coverage, OI observations per bucket (min / median / max), percent of buckets with `>=2` OI samples, taker coverage, liquidation-source rows, heartbeat healthy rate
- per readiness group, from recorded `/btc` payloads: `READY`, `HISTORY_BUILDING`, `DATA_UNAVAILABLE`, `DEGRADED`

Do not query `beta_episode_outcomes`. Do not compute forward returns, PnL, MAE, MFE, or hit rate.

## Environment (`/opt/signalbot/.env`, never committed, never printed)

| Variable | Meaning |
|---|---|
| `BETA_TELEGRAM_BOT_TOKEN` | Beta bot token. It is separate from the legacy notifier token. |
| `BETA_OWNER_TELEGRAM_USER_ID` | The single owner/admin Telegram user id. |
| `BETA_ENABLED` | Runtime enable. An explicit `1`/`true` enables and `0`/`false` disables, overriding the committed `beta.enabled: false`. If unset or empty, the config decides. |
| `BETA_DETECTION_ENABLED` | Kill switch for the tape and detector (restrict-only). |
| `BETA_PUSH_ENABLED` | Must be set explicitly to `1`/`true` **and** `beta.push_enabled: true` must be committed. If unset, push is forbidden. |
| `BETA_OUTCOME_TRACKING_ENABLED` | Kill switch for the outcome tracker (restrict-only). |
| `BETA_TELEGRAM_ENABLED` | `0` selects the no-Telegram shadow-soak mode (below). Default: Telegram is part of the deployment. |
| `BETA_CODE_VERSION` | Optional explicit beta code version. The default is resolved from the path-scoped git history. |

- **Switch precedence:**
  - `BETA_ENABLED`: explicit env value, else committed config.
  - Detection and outcome tracking: config AND env; the env can only restrict.
  - Push: committed `push_enabled` AND explicit env true. The env alone can never enable push.
- **Required even for beta-only runs:** the database variables and `REDIS_URL`. The shared secrets loader validates `REDIS_URL` for every `main.py` command, although the beta never connects to Redis.
- **Admin push state:** `/admin_pause_push` and `/admin_resume_push` change a durable admin push state. Effective push = hard push switch AND admin state, so an admin command can never exceed the hard switch.
- **Push OFF scope:** turning push off does not stop the tape, the detector or outcome tracking.

## Soak (7 days, push disabled)

1. Set `BETA_ENABLED=1` in `.env`. The committed config stays `beta.enabled: false`, `push_enabled: false`.
2. Run `python -m runtime.beta_bootstrap_runner` until it exits `0`.
3. Enable the detector and outcomes timers. Then either:
   - **With Telegram:** also enable the notify timer and the bot, with only the owner allowlisted; or
   - **No-Telegram shadow soak:** set `BETA_TELEGRAM_ENABLED=0`, leave `BETA_TELEGRAM_BOT_TOKEN` empty, and do not enable the notify timer or the bot.
4. Check `--beta-status` (soak metrics) and `--beta-health` (alerts) daily.

### No-Telegram shadow-soak mode

`BETA_TELEGRAM_ENABLED=0` is accepted only while push is off and no beta bot token is set; otherwise every beta command fails with a configuration error. In this mode:
- `--beta-health` does not report `BOT_RECEIVER_DOWN` or `NOTIFIER_NOT_RUNNING`, because Telegram is deliberately absent.
- `--beta-notify-once` returns `TELEGRAM_DISABLED` without doing anything.
- `runtime.beta_bot` exits without starting.

All other health alerts (ingestion, detector, materialization, outcomes, delivery) are unchanged. With Telegram enabled (the default), the bot and notifier liveness checks apply exactly as before.

The gate criteria are listed in the restart decision.

## Owner health alerts

`--beta-notify-once` evaluates `--beta-health`. When a bot token and owner id are configured, it sends one owner alert per alert key, rate-limited by `health.owner_alert_repeat_s`. The alert keys are:
- `INGESTION_STALE`
- `DETECTOR_NOT_ADVANCING`
- `MATERIALIZATION_FAILURE`
- `OUTCOME_TRACKER_NOT_ADVANCING`
- `BOT_RECEIVER_DOWN`
- `NOTIFIER_NOT_RUNNING`
- `DELIVERY_FAILURE_SPIKE`

A DB outage makes every beta command exit with status 2 and report `DB_UNAVAILABLE`. systemd records that as a failed unit.

## Privacy (personal data)

- **Where personal data lives:** Telegram user and chat ids exist only in `beta_allowlist` and `beta_users`. `beta_notification_deliveries` and `beta_feedback` reference them through `user_pk` only.
- **What never holds ids:** the tape, episode, transition, outcome, push-decision and audit tables hold no Telegram identifiers. Audit rows store pseudonymous fingerprints only.
- **Database backups contain personal data.** Treat backup files and offsite copies accordingly (`deploy/backup.sh`).
- **`/stop`** pauses messages.
- **`/delete_me`** deletes the user row. Feedback rows cascade. Delivery rows keep only an anonymous `NULL` user. The allowlist entry is also removed.
- **Retention:** stopped users are purged automatically after `privacy.stopped_user_retention_days` (30).
- **Logs:** never contain a raw Telegram id, chat id or token.
