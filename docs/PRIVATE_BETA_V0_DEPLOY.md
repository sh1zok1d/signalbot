# Private Beta V0.2 — deploy, soak and privacy runbook

Authority: `docs/PRIVATE_BETA_V0_RESTART_DECISION.md`. The systemd artifacts are **prepared but not activated**. Activation is a separate, owner-authorized step.

## Units (`deploy/`)

| Unit | Schedule | Command |
|---|---|---|
| `signalbot-beta-detector.service` + `.timer` | every 5m at :25 s | `main.py --beta-once --beta-json` |
| `signalbot-beta-outcomes.service` + `.timer` | every 5m at :50 s (offset 2m) | `main.py --beta-outcomes-once --beta-json` |
| `signalbot-beta-notify.service` + `.timer` | every minute at :40 s | `main.py --beta-notify-once --beta-json` |
| `signalbot-beta-bot.service` | long-running (Restart=on-failure) | `python -m runtime.beta_bot` |
| `signalbot-beta-d7.service` + `.timer` | every hour at HH:01 UTC | `main.py --beta-d7-once --beta-json` |

- `deploy/install_beta_units.sh` copies the units and runs `daemon-reload`. It **never enables or starts** anything.
- `deploy/check_beta_units.sh` is read-only.
- The detector and outcomes units wait for PostgreSQL first (`ExecStartPre=deploy/wait_for_infra.py --postgres-only --timeout 60`, the same readiness gate `signalbot.service` uses, minus Redis).
- The bounded history bootstrap is run manually with `python -m runtime.beta_bootstrap_runner [--max-iterations N]` (default 40, cap 100; 30 days need 31 batches of `bootstrap.max_buckets_per_run` = 288). Each iteration runs the unchanged `main.py --beta-bootstrap --beta-json` and prints progress. The runner stops on the first error, and fails if the bootstrap is still incomplete at the bound. After completion it runs one extra bootstrap as an idempotency check, which may only write buckets that closed in the meantime. Exit codes: `0` verified, `2` bootstrap error, `3` iteration limit, `4` verification failed.

## D7 hour state

The D7 feed is display-only. It does not enter the rules digest, does not open an episode, and does not change a push.

The line is shown only when both switches are on, the same shape as push:

- **Hard allow:** committed `regime_d7.enabled: true` in `config/beta_v0.yaml`. Turning this false in a future config hides the line even if the owner state is on. Activation does not edit this file on the VPS.
- **Owner state:** `/admin_d7_on` and `/admin_d7_off`. Both are audited in `beta_admin_audit`. The durable key is `beta_runtime_state.state_key = 'admin_d7_enabled'`. A missing row is off. `/admin_d7_on` cannot exceed the hard allow.

- **Timer:** `signalbot-beta-d7.timer` runs `main.py --beta-d7-once` at HH:01 UTC. Each run fetches closed Binance USD-M BTCUSDT 1m bars (`closeTime < now`) from the last stored bar, and at least the last 120 bars, paging at 1500. It then inserts hour states that do not exist yet. A missed run catches up on the next start.
- **Backfill:** `python main.py --beta-d7-backfill --days 90 --beta-json`. Paged at 1500 bars with a short pause between pages. Resumable and idempotent. 90 days covers the 1440-hour warm-up with room for gaps.
- **Health:** while `regime_d7.enabled` is true, `--beta-health` raises `D7_HOUR_STATE_STALE` when there is no hour state or the newest state's `available_at` (the end of that clock hour) is older than 70 minutes. With the hard allow false the alert is absent. The alert follows the hard allow, so it can fire before `/admin_d7_on`. It does not show the line.

**Enable, without editing files on the VPS:**

1. Deploy the commit that already has `regime_d7.enabled: true`. Schema init widens `beta_runtime_state` so `admin_d7_enabled` is allowed. No owner row is inserted.
2. Install and start `signalbot-beta-d7.timer`.
3. Run `python main.py --beta-d7-backfill --days 90 --beta-json`.
4. Run the sanity SQL below. Leave the line off until every check is sane.
5. From the owner account, send `/admin_d7_on`. The next `/btc` can show the line when the display rules also hold (complete last hour, state true, warm-up, computed on time, view not stale or degraded).
6. `/admin_d7_off` hides the line again. No restart and no config edit.

**Sanity SQL** (read-only). `valid_hours` counts completed hours with a return. `share_true` is the share of decided hours whose stored state is true. That is the p90 threshold on hours already labeled. It is not a count of whether the next hour was also high impact.

```sql
SELECT count(*) FILTER (WHERE complete AND ret IS NOT NULL) AS valid_hours,
       count(*) FILTER (WHERE state IS NOT NULL) AS decided_hours,
       count(*) FILTER (WHERE state) AS state_true,
       count(*) FILTER (WHERE state)::float
           / NULLIF(count(*) FILTER (WHERE state IS NOT NULL), 0) AS share_true
FROM beta_d7_hour_states;
```

Expect `valid_hours >= 1440` and `share_true` near 0.10.

```sql
SELECT hour_start, available_at, now() - available_at AS age
FROM beta_d7_hour_states
ORDER BY hour_start DESC
LIMIT 1;
```

Expect `age` under 70 minutes.

Stage-1 `klines_1m.ts` is the Binance 1m open time, the same instant as `beta_d7_klines_1m.open_time`. The current open minute is excluded.

```sql
WITH bounds AS (
    SELECT now() - interval '24 hours' AS start_ts,
           date_bin('minute', now(), TIMESTAMPTZ '2000-01-01 00:00:00+00') AS open_minute
),
d7 AS (
    SELECT d.open_time, d.close
    FROM beta_d7_klines_1m d
    CROSS JOIN bounds b
    WHERE d.open_time >= b.start_ts AND d.open_time < b.open_minute
),
stage1 AS (
    SELECT k.ts, k.close
    FROM klines_1m k
    CROSS JOIN bounds b
    WHERE k.exchange = 'binance' AND k.symbol = 'BTCUSDT'
      AND k.ts >= b.start_ts AND k.ts < b.open_minute
)
SELECT (SELECT count(*) FROM d7) AS d7_bars,
       (SELECT count(*) FROM stage1) AS stage1_bars,
       (SELECT count(*) FROM d7 JOIN stage1 s ON s.ts = d7.open_time) AS compared,
       (SELECT count(*) FROM d7 JOIN stage1 s ON s.ts = d7.open_time
         WHERE d7.close IS DISTINCT FROM s.close) AS close_mismatches,
       (SELECT count(*) FROM d7 LEFT JOIN stage1 s ON s.ts = d7.open_time
         WHERE s.ts IS NULL) AS d7_only,
       (SELECT count(*) FROM stage1 s LEFT JOIN d7 ON d7.open_time = s.ts
         WHERE d7.open_time IS NULL) AS stage1_only;
```

Expect `close_mismatches = 0`, `d7_only = 0`, and `stage1_only = 0`.

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
- **Readiness on the main view:** `Detector ready` when every family is ready. Otherwise one line per family that is not ready (families in the identical condition share a line), then `Ready: <families>`. Each family is one of:
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
- **Admin D7 state:** `/admin_d7_on` and `/admin_d7_off` change a durable owner state that defaults off. The D7 line is shown only when that state is on and `regime_d7.enabled` is true. See the D7 section for the sanity SQL.
- **Push OFF scope:** turning push off does not stop the tape, the detector or outcome tracking.

## Soak (7 days, push disabled)

1. Set `BETA_ENABLED=1` in `.env`. The committed config stays `beta.enabled: false`. During the soak `push_enabled` was `false`; since 2026-10-01 it is `true` (see Live push), so keep `BETA_PUSH_ENABLED` unset for a soak.
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

## Live push (owner decision 2026-10-01)

The committed config now has `beta.push_enabled: true`. This is the hard allow only. Push is effective only when all three hold:
- `beta.push_enabled: true` (committed);
- `BETA_PUSH_ENABLED=true` in `/opt/signalbot/.env` (unset, empty or `0` forbids push);
- the durable admin state is not paused (`/admin_resume_push`; a missing row counts as resumed).

**Recipients:** every `ACTIVE` beta user. While only the owner has joined, this is the owner-only live push of the rollout. Do not hand out invite codes until the owner has seen real pushes.

**Limits (unchanged):** at most `max_new_pushes_per_utc_day` = 3 new pushes per UTC day, `same_event_cooldown_min` = 20, nothing older than `delivery_ttl_s` = 600 s. D7 and readiness changes never push.

**Enable:**
1. From the owner account, send `/admin_pause_push` before touching `.env`. A missing admin row counts as resumed, so without this step push starts at the first restart.
2. Add `BETA_PUSH_ENABLED=true` to `/opt/signalbot/.env`. The detector and notify timers read `.env` on every run, so the env change applies within a minute; the bot needs a restart.
3. Deploy and restart as usual (pull, schema init, restart the bot, timers keep running).
4. Check `/admin_health`: switches show `'BETA_PUSH_ENABLED': True`. Check `/admin_status`: `push effective False` (paused).
5. Send `/admin_resume_push`. The reply must say effective push is on.

**Stop:** `/admin_pause_push` stops new deliveries at once, without a restart. Pending deliveries are suppressed with `PUSH_DISABLED`. For a hard stop, set `BETA_PUSH_ENABLED=0` and restart the bot and the notify timer.

## Owner health alerts

`--beta-notify-once` evaluates `--beta-health`. When a bot token and owner id are configured, it sends one owner alert per alert key, rate-limited by `health.owner_alert_repeat_s`. The alert keys are:
- `INGESTION_STALE`
- `DETECTOR_NOT_ADVANCING`
- `MATERIALIZATION_FAILURE`
- `OUTCOME_TRACKER_NOT_ADVANCING`
- `BOT_RECEIVER_DOWN`
- `NOTIFIER_NOT_RUNNING`
- `DELIVERY_FAILURE_SPIKE`
- `D7_HOUR_STATE_STALE` (only while `regime_d7.enabled` is true, and only when the newest hour state's `available_at` is older than 70 minutes; independent of `/admin_d7_on`)

A DB outage makes every beta command exit with status 2 and report `DB_UNAVAILABLE`. systemd records that as a failed unit.

## Privacy (personal data)

- **Where personal data lives:** Telegram user and chat ids exist in `beta_allowlist` and `beta_users`. `beta_waitlist` stores a Telegram id and `requested_at` only after the person presses the request-access button. `beta_notification_deliveries`, `beta_feedback`, `beta_feedback_messages`, and `beta_user_activity` reference a person through `user_pk` only.
- **`beta_user_activity`:** one row per command, button, or delivered push (`action`, optional `detail`, `lang`, `at`). No Telegram id, no chat id, no message text. Kept for `telemetry.retention_days` (120), then purged. `/delete_me` deletes the user row and the activity rows cascade.
- **`beta_feedback_messages`:** free text from `/feedback` (`text`, `lang`, `created_at`) keyed by `user_pk`. This is not the Useful/Noise table `beta_feedback`. At most `feedback.max_chars` (1000) characters and `feedback.max_per_utc_day` (5) stored messages per user per UTC day. Rows older than `telemetry.retention_days` (120) are purged by the notifier retention job. `/delete_me` deletes them through `ON DELETE CASCADE`. A copy is forwarded to the owner's private chat as a fingerprint, language, Kyiv time, and the text. The forward does not contain the Telegram id. The audit row for `/admin_reply` stores the fingerprint only, not the reply text.
- **`beta_invites`:** invite codes and labels. Not user ids. `beta_allowlist.invite_code` and `beta_users.invite_code` remember which code admitted the person. Codes are revoked, not deleted.
- **Rejected `/start`:** when `BETA_TELEMETRY_SALT` is set, a row is `(utc_day, HMAC-SHA256(salt, telegram id))`. When the salt is unset, the day stores a count only. The raw id is never stored. Purged after `telemetry.rejected_start_retention_days` (30).
- **What never holds ids:** the tape, episode, transition, outcome, push-decision, `beta_btc_views`, `beta_details_opens`, and audit tables hold no Telegram identifiers. Audit rows store pseudonymous fingerprints only. The owner waitlist view is the exception that shows ids to the owner.
- **Database backups contain personal data.** Treat backup files and offsite copies accordingly (`deploy/backup.sh`).
- **`/stop`** pauses messages.
- **`/delete_me`** deletes the user row, the allowlist entry, and the waitlist row. Feedback and activity rows cascade. Delivery rows keep only an anonymous `NULL` user.
- **Retention:** stopped users are purged automatically after `privacy.stopped_user_retention_days` (30).
- **Logs:** never contain a raw Telegram id, chat id or token.
