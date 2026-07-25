# Telegram forecast notifier systemd timer — deployment

This document covers the **deployment artifacts** for the isolated Telegram
forecast notifier: a bounded `oneshot` systemd service and a calendar-aligned
timer that fires every five minutes (UTC) at second `:35` — 30 seconds after
the shadow forecast timer's `:05` firing, so the notifier scans predictions
the shadow pass has already had time to persist.

The notifier is a completely separate subsystem from the shadow forecast pass:
separate PostgreSQL advisory lock, separate tables
(`telegram_notifier_state`, `telegram_notification_deliveries`), separate
systemd unit and timer. It never recomputes a forecast, never blocks or
changes the shadow prediction/outcome timer, and never flips the Stage 2
master switch — `config/stage2.yaml` stays `stage2.enabled: false`, exactly as
before.

**Scope: notifications only.** This is not a trading system. It never places
an order, never polls Telegram for inbound commands/messages, and never sends
anything for a `NEUTRAL` prediction.

---

## A. PR authoring (no server access required)

Creating, testing, reviewing, and merging these deployment artifacts needs **no
VPS access** and touches **no production system**:

- create the units (`deploy/signalbot-telegram.service`, `deploy/signalbot-telegram.timer`);
- run the repository tests (`pytest tests/deploy/test_telegram_systemd.py -q`);
- review the PR;
- merge the deployment artifacts.

**No production deployment was performed during PR authoring.** No unit was
installed, no timer was enabled, no production `--telegram-once` was run, and
no real Telegram message was sent.

---

## B. Required environment variables

Set these in `/opt/signalbot/.env` (never commit real values — see
`.env.example`):

- `TELEGRAM_BOT_TOKEN` — the bot token from @BotFather;
- `TELEGRAM_CHAT_ID` — the destination chat/channel id the bot has been added to.

Both are **required** for `--telegram-once` and `--telegram-test`. Missing or
blank values are rejected **before** any schema, lock, or outbox work —
`--telegram-status` also requires `TELEGRAM_CHAT_ID` (it derives the recipient
fingerprint from it) but performs no writes regardless.

Keep the existing `/opt/signalbot/.env` ownership/permissions:

```
sudo chown root:signalbot /opt/signalbot/.env && sudo chmod 640 /opt/signalbot/.env
```

Nothing about the notifier changes this — the bot token stays inside `.env`,
is never logged, never printed in a status/execution report, and never enters
the recipient fingerprint (the fingerprint is a SHA-256 digest of the chat id
only).

---

## C. Real VPS installation checkpoint (operator, later)

The operator performs these steps **on the server**, in order, when server
access is available. All commands are safe and explicit.

### 1. Update the checked-out working tree to merged `main` (fail-closed)

Same fail-closed update procedure as the shadow timer (see
`docs/SHADOW_TIMER_DEPLOY.md` section B.1) — require a clean tree, fetch,
fast-forward, and verify `HEAD` matches `origin/main` before continuing. Never
`git reset --hard`; never discard local changes.

```
cd /opt/signalbot
sudo -u signalbot git status --short          # MUST be empty before continuing
sudo -u signalbot git fetch origin
sudo -u signalbot git switch main
sudo -u signalbot git pull --ff-only origin main
sudo -u signalbot git status --short          # MUST still be empty
sudo -u signalbot git rev-parse HEAD          # record the deployed revision
sudo -u signalbot git rev-parse origin/main
```

If the tree is dirty, or `git pull --ff-only` cannot fast-forward, **stop and
investigate** — never force the update.

### 2. Activate the project virtualenv and run tests

```
sudo -u signalbot /opt/signalbot/.venv/bin/python -m pytest tests/deploy/test_telegram_systemd.py -q
# (optionally the full suite)
sudo -u signalbot /opt/signalbot/.venv/bin/python -m pytest -q
```

### 3. Manual read-only status BEFORE activation

```
sudo -u signalbot /opt/signalbot/.venv/bin/python \
  /opt/signalbot/main.py --telegram-status --telegram-json
```

Expect a single JSON object on stdout: `state` (`NOT_INITIALIZED` or `READY`),
`notifier_initialized`, pending/sent counters, and the earliest next retry
time if any deliveries are pending. This performs **no writes** — it never
acquires the notifier lock, never creates the notifier tables, and never
inserts a bootstrap row.

### 4. Optional connectivity test BEFORE activation

```
sudo -u signalbot /opt/signalbot/.venv/bin/python \
  /opt/signalbot/main.py --telegram-test --telegram-json
```

Sends one fixed connectivity message to the configured chat and reports
`{"command":"TELEGRAM_TEST","sent":true,"telegram_message_id":...}`. This
performs **no outbox mutation** and **no forecast lookup** — it only proves
the bot token and chat id are wired correctly. Skip this step if you would
rather not send any message before the timer is installed.

### 5. Install the units WITHOUT activation

```
sudo /opt/signalbot/deploy/install_telegram_timer.sh
```

This validates the deployment layout, runs `systemd-analyze verify`, installs
both units `root:root 0644`, and runs `systemctl daemon-reload`. It does **not**
enable or start anything and prints the exact command to activate later.

### 6. Inspect unit verification

```
sudo systemd-analyze verify \
  /etc/systemd/system/signalbot-telegram.service \
  /etc/systemd/system/signalbot-telegram.timer
```

### 7. Explicitly enable the timer

```
sudo /opt/signalbot/deploy/install_telegram_timer.sh --enable-now
```

This enables and starts **the timer** (never the service directly). The
service runs only when the timer fires it.

### 8. Inspect the first real run

```
sudo /opt/signalbot/deploy/check_telegram_timer.sh
sudo systemctl list-timers --all signalbot-telegram.timer --no-pager
sudo journalctl -u signalbot-telegram.service -f
```

### 9. Verify the first run's behavior

```
sudo -u signalbot /opt/signalbot/.venv/bin/python \
  /opt/signalbot/main.py --telegram-status --telegram-json \
  | python3 -m json.tool
```

On the **very first** invocation against an existing (already-populated)
deployment, expect `bootstrap_status: "BOOTSTRAPPED_NO_HISTORY"` in the
execution report from that run's journald output, and `sent_count: 0` /
`materialized_count: 0` — see "First-deployment bootstrap" below for why. On
subsequent runs, newly persisted `LONG`/`SHORT` predictions are materialized
into the outbox and delivered.

---

## First-deployment bootstrap (no historical-message spam)

The very first time the notifier runs for a given `(runner_name="telegram_forecast_v1",
channel="telegram", recipient_fingerprint=sha256(chat_id))` combination, it
records a `telegram_notifier_state` row with `started_at = now` — the wall-clock
time of that first run — and reports `bootstrap_status: "BOOTSTRAPPED_NO_HISTORY"`.

The outbox materialization query only enqueues predictions with
`forecast_predictions.created_at >= started_at`. This means:

- **no backlog of old predictions is ever sent** on first deployment, even if
  the shadow forecast pass has been running for days and has accumulated many
  `LONG`/`SHORT` rows;
- the bootstrap row is written **once**, using `ON CONFLICT DO NOTHING` on the
  `(runner_name, channel, recipient_fingerprint)` primary key, so a restart or
  a second `--telegram-once` invocation never resets `started_at` and never
  causes historical predictions to be (re)enqueued;
- subsequent runs report `bootstrap_status: "ALREADY_INITIALIZED"`.

---

## Durable outbox and delivery guarantee

Every actionable (`LONG`/`SHORT`) prediction is materialized **once** into
`telegram_notification_deliveries`, keyed by the full identity
`(channel, recipient_fingerprint, symbol, market_type, timeframe, bucket_ts,
calculation_version, rule_version)`. Materialization is an anti-join
(`NOT EXISTS`) against that identity plus `ON CONFLICT DO NOTHING` as an extra
guard, so re-running `--telegram-once` never double-enqueues a row.

**Delivery guarantee: durable at-least-once.** There is exactly one Telegram
send attempt per pending delivery per invocation (no in-process retry loop,
no `sleep`). A delivery that fails is recorded with a bounded exponential
backoff (`next_attempt_at`) and retried on a **later** invocation — meaning the
notifier survives process restarts, Telegram API downtime, and VPS reboots
without losing a pending notification. A **rare** duplicate delivery is
possible only in the narrow crash window after Telegram has accepted a message
but before PostgreSQL records `sent_at` — this design deliberately favors
retrying (never silently dropping a notification) over claiming a
mathematically perfect exactly-once guarantee, which is impossible without a
distributed transaction across Telegram and PostgreSQL.

## Retry / backoff behavior

A failed delivery's `next_attempt_at` is computed with a deterministic
exponential backoff: base 60 seconds, doubling with each attempt, capped at 6
hours. If Telegram itself supplies a `RetryAfter` (HTTP 429), that wait is
respected (the delivery is not retried before that regardless of the computed
backoff). Backoff is purely a function of `attempt_count` and the optional
`retry_after` — no randomness, no jitter, overflow-safe at high attempt counts.

## Failure isolation

A Telegram send failure (network error, API error, invalid chat, revoked
token) is persisted per-delivery (`last_error_class`, `last_error_summary`,
`next_attempt_at`) and reported in the execution report's `failures` list. It
**never**:

- fails the whole `--telegram-once` invocation (other pending deliveries in
  the same run are still attempted);
- rolls back or modifies any `forecast_predictions` / `forecast_outcomes` row;
- blocks, delays, or otherwise affects the shadow forecast/outcome timer.

An **internal** correctness failure (a malformed pending-delivery row, an
identity mismatch, a database error, missing secrets) is different: it fails
the invocation closed with a non-zero exit, exactly like the equivalent
shadow-CLI failures — this is deliberate, since silently ignoring a hydration
or database failure could produce silent data loss.

## Advisory lock

Before any write, `--telegram-once` takes a dedicated, non-blocking PostgreSQL
advisory lock (deterministic SHA-256-derived key, held on one dedicated
connection, always released in `finally`). This lock is in a **completely
separate namespace** from the shadow-recovery lock — a Telegram run can never
block on, or be blocked by, a concurrent shadow forecast/outcome run, and vice
versa. If another Telegram invocation already holds the lock (e.g. the timer
firing while a manual `--telegram-once` is still running), the later
invocation exits cleanly with `lock_status: "LOCK_HELD_SKIPPED"` and
**zero writes**. `--telegram-status` never acquires this lock (it is strictly
read-only).

## Message format

Each notification is a single HTML-formatted Telegram message (🟢 for `LONG`,
🔴 for `SHORT`) labeled **"Режим: shadow forecast"** — it never uses
trade-execution wording ("buy", "sell", "enter", "exit"). It includes the
reference price, confidence, score, bucket timestamp (UTC), horizon set, a
data-quality section (data confidence, consensus confidence, partial-consensus
flag), and a bounded, HTML-escaped list of reasons (visibly truncated if long,
never cut through an HTML tag or entity). It never includes the raw
`consensus_snapshot`, the bot token, the chat id, or any Telegram API URL.

## CLI

- `--telegram-once` — one bounded pass: materialize + attempt pending
  deliveries. Optional `--telegram-max-scan` (default 200, ceiling 2000) and
  `--telegram-max-send` (default 20, ceiling 100) bound the scan/send work per
  invocation. An explicit `0`, a negative value, a bool, or a value over the
  ceiling is rejected before any work begins.
- `--telegram-status` — strictly read-only status (never writes, never
  acquires the lock).
- `--telegram-test` (optional) — sends one fixed connectivity message with no
  outbox mutation and no forecast lookup.
- `--telegram-json` — JSON output for any of the above (structured journald
  records). Rejected if no `--telegram-*` command is selected.

`--telegram-*` commands cannot be combined with each other, with a
`--shadow-*` command, or with `--validate` / `--backfill-only` /
`--skip-backfill`.

## Schema

Two additive tables (`CREATE TABLE IF NOT EXISTS`, no `ALTER`/`DROP` of
existing Stage 1/2 tables, no foreign key to `forecast_predictions`):

- `telegram_notifier_state` — one row per `(runner_name, channel,
  recipient_fingerprint)`, recording `started_at` for the bootstrap contract
  above. Never stores the raw chat id (only its SHA-256 fingerprint).
- `telegram_notification_deliveries` — the durable outbox, one row per
  `(channel, recipient_fingerprint, symbol, market_type, timeframe, bucket_ts,
  calculation_version, rule_version)`, tracking `attempt_count`,
  `next_attempt_at`, `last_attempt_at`, `sent_at`, `telegram_message_id`,
  `last_error_class`, `last_error_summary`.

Plus one additive partial index on `forecast_predictions` (`ix_fp_actionable_
created_at`, `WHERE direction IN ('LONG','SHORT')`, ordered by `created_at`) —
supports the notifier's discovery scan without affecting any existing query.

---

## Expected journald behavior

- the structured JSON report is written to **stdout**;
- diagnostic logs are written to **stderr** (routed there by `--telegram-json`);
- both streams are collected by journald under `SyslogIdentifier=signalbot-telegram`;
- **no secrets** (bot token, chat id, DSN, `.env` values) are printed — the
  reported `recipient_fingerprint` is a SHA-256 digest, never the raw chat id.

Inspect with:

```
sudo journalctl -u signalbot-telegram.service -n 50 --no-pager
```

---

## Rollback

```
sudo systemctl disable --now signalbot-telegram.timer
sudo rm -f \
  /etc/systemd/system/signalbot-telegram.timer \
  /etc/systemd/system/signalbot-telegram.service
sudo systemctl daemon-reload
```

Rollback is safe and leaves the rest of the system intact:

- the Stage 1 `signalbot.service` and the shadow `signalbot-shadow.service`/
  `.timer` keep running (both are independent);
- the PostgreSQL/Redis containers keep running;
- **all database rows are preserved** — `telegram_notifier_state` and
  `telegram_notification_deliveries` are not dropped, so a later reinstall
  resumes from the same outbox state rather than re-bootstrapping;
- `/opt/signalbot/.env` is **not** deleted;
- `/opt/signalbot` is **not** deleted.

---

## Notifier independence

The Telegram notifier is fully isolated from Stage 1 ingestion and the shadow
forecast/outcome pass:

- it reads `forecast_predictions` rows but never writes to it, and never
  recomputes a forecast or a consensus snapshot;
- it never touches `shadow_recovery_watermarks` or the shadow-recovery
  advisory lock;
- its own advisory lock is in a separate namespace, so it can never block, or
  be blocked by, a concurrent shadow run;
- disabling, uninstalling, or rolling back this timer has **no effect** on
  Stage 1 ingestion or the shadow forecast/outcome timer;
- `stage2.enabled` remains **false** in `config/stage2.yaml` — the notifier is
  an explicit operational invocation, never the Stage 2 master switch.

## Remaining limitations (explicit scope exclusions)

- **no trading** or order execution of any kind;
- **no inbound Telegram commands, polling, or webhooks** — this is
  send-only;
- **no multiple subscribers / recipient list** — one configured chat id;
- **no interactive buttons or replies**;
- **no outcome notifications** — only `LONG`/`SHORT` predictions are sent,
  never `NEUTRAL`, never a maturation/outcome result;
- **no daily/periodic summary reports**;
- **no calibration UI / ML / adaptive thresholds** — forecast, consensus, and
  outcome formulas are unchanged;
- **no change to the shadow timer's cadence or logic** — the shadow pass and
  its timer are untouched by this PR.
