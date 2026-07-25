# Shadow forecast systemd timer — deployment

This document covers the **deployment artifacts** for the automatic 5-minute
shadow forecast one-shot: a bounded `oneshot` systemd service and a
calendar-aligned timer that fires every five minutes (UTC) at second `:05`.

The timer is an explicit **operational invocation** of `main.py --shadow-once`.
It does **not** flip the Stage 2 master switch — `config/stage2.yaml` stays
`stage2.enabled: false`, exactly as before.

---

## A. PR authoring (no server access required)

Creating, testing, reviewing, and merging these deployment artifacts needs **no
VPS access** and touches **no production system**:

- create the units (`deploy/signalbot-shadow.service`, `deploy/signalbot-shadow.timer`);
- run the repository tests (`pytest tests/deploy/test_shadow_systemd.py -q`);
- review the PR;
- merge the deployment artifacts.

**No production deployment was performed during PR authoring.** No unit was
installed, no timer was enabled, and no production `--shadow-once` was run.

---

## B. Real VPS installation checkpoint (operator, later)

The operator performs these steps **on the server**, in order, when server
access is available. All commands are safe and explicit.

### 1. Update the checked-out working tree to merged `main` (fail-closed)

`git fetch` alone does **not** update the checked-out working tree, so the later
tests and installation could run against an old revision. Update the working tree
with a fast-forward-only pull, and stop if anything is unexpected.

First require a clean tree before touching anything:

```
cd /opt/signalbot
sudo -u signalbot git status --short          # MUST be empty before continuing
```

If that output is not empty, **stop and investigate** — do not proceed, do not
`git reset --hard`, and do not discard local changes.

Then fetch and fast-forward the working tree onto `main`:

```
sudo -u signalbot git fetch origin
sudo -u signalbot git switch main
sudo -u signalbot git pull --ff-only origin main
```

Then verify the update landed exactly on the merged revision:

```
sudo -u signalbot git status --short          # MUST still be empty
sudo -u signalbot git rev-parse HEAD          # record the deployed revision
sudo -u signalbot git rev-parse origin/main
```

Requirements:

- the two SHAs (`HEAD` and `origin/main`) **must match**;
- the working tree **must remain clean** (empty `git status --short`) both before
  and after the pull;
- **do not** use `git reset --hard`;
- **do not** discard local changes or force the checkout;
- if the tree is dirty, or `git pull --ff-only` cannot fast-forward, **stop and
  investigate** — never force the update.

### 2. Activate the project virtualenv and run tests

```
sudo -u signalbot /opt/signalbot/.venv/bin/python -m pytest tests/deploy/test_shadow_systemd.py -q
# (optionally the full suite)
sudo -u signalbot /opt/signalbot/.venv/bin/python -m pytest -q
```

### 3. Manual read-only status BEFORE activation

```
sudo -u signalbot /opt/signalbot/.venv/bin/python \
  /opt/signalbot/main.py --shadow-status --shadow-json
```

Expect a single JSON object on stdout (schema state, per-exchange prerequisites,
latest prediction, recorded outcomes). This performs **no writes**.

### 4. Manual dry-run BEFORE activation

```
sudo -u signalbot /opt/signalbot/.venv/bin/python \
  /opt/signalbot/main.py --shadow-dry-run --shadow-json
```

The dry-run performs the real raw-read → features → consensus → forecast path but
**persists nothing** (`writes_enabled=false`, `persistence_effect=WOULD_INSERT`).
Confirm it succeeds before installing the timer.

### 5. Install the units WITHOUT activation

```
sudo /opt/signalbot/deploy/install_shadow_timer.sh
```

This validates the deployment layout, runs `systemd-analyze verify`, installs
both units `root:root 0644`, and runs `systemctl daemon-reload`. It does **not**
enable or start anything and prints the exact command to activate later.

### 6. Inspect unit verification

```
sudo systemd-analyze verify \
  /etc/systemd/system/signalbot-shadow.service \
  /etc/systemd/system/signalbot-shadow.timer
```

### 7. Explicitly enable the timer

```
sudo /opt/signalbot/deploy/install_shadow_timer.sh --enable-now
```

This enables and starts **the timer** (never the service directly). The service
runs only when the timer fires it.

### 8. Inspect the first real run

```
sudo /opt/signalbot/deploy/check_shadow_timer.sh
sudo systemctl list-timers --all signalbot-shadow.timer --no-pager
sudo journalctl -u signalbot-shadow.service -f
```

### 9. Verify a `forecast_predictions` row was written

After a timer firing (or the manual smoke below) has completed, confirm the
prediction landed using the existing **read-only** CLI — no raw SQL, no DSN
exposure:

```
sudo -u signalbot /opt/signalbot/.venv/bin/python \
  /opt/signalbot/main.py --shadow-status --shadow-json \
  | python3 -m json.tool
```

Check the pretty-printed JSON:

- `state` == `"READY"`;
- `latest_prediction` is **not** null;
- `latest_prediction.bucket_ts` corresponds to the newly processed closed bucket
  (the `bucket_ts` the timer just ran, i.e. the previous closed 5-minute bucket);
- `latest_prediction.reference_price_source` == `"binance_close_5m"`;
- **no secret** is printed (the status report never emits the DSN, `.env`
  values, Redis URL, or any token).

This reads the just-written `forecast_predictions` row through the same status
path used everywhere else — it performs no writes.

---

## First isolated manual smoke (optional)

> **WARNING — this performs a REAL Stage 2 write.**
> - Only run it **after** the dry-run in step 4 succeeds.
> - Run it **once**, then inspect the database afterward.
> - **Do NOT run it during PR authoring** or before the dry-run passes.

```
sudo systemctl start signalbot-shadow.service
```

This starts the bounded one-shot exactly once (outside the timer schedule). It is
the same command the timer issues. Inspect the DB and journald output afterward.

---

## Expected journald behavior

- the structured JSON report is written to **stdout**;
- diagnostic logs are written to **stderr** (routed there by `--shadow-json`);
- both streams are collected by journald under `SyslogIdentifier=signalbot-shadow`;
- **no secrets** (DSN, `.env` values, Redis URL, tokens) are printed.

Inspect with:

```
sudo journalctl -u signalbot-shadow.service -n 50 --no-pager
```

---

## Rollback

```
sudo systemctl disable --now signalbot-shadow.timer
sudo rm -f \
  /etc/systemd/system/signalbot-shadow.timer \
  /etc/systemd/system/signalbot-shadow.service
sudo systemctl daemon-reload
```

Rollback is safe and leaves the rest of the system intact:

- the Stage 1 `signalbot.service` keeps running (it is independent);
- the PostgreSQL/Redis containers keep running;
- all database rows are preserved;
- `/opt/signalbot/.env` is **not** deleted;
- `/opt/signalbot` is **not** deleted.

---

## Automatic recovery behavior (bounded)

An automatic `--shadow-once` (no `--shadow-bucket-ts`) now runs **one bounded
recovery pass**, then exits. There is no background worker, no sleep, and no loop
across invocations — the timer still fires one bounded process every five minutes.

- **Cross-process lock.** The pass first takes a non-blocking PostgreSQL advisory
  lock (deterministic id per runner/scope, held on one dedicated connection). If
  another runner (a manual run and the timer overlapping) holds it, this run exits
  cleanly with `lock_status=LOCK_HELD_SKIPPED` and **zero writes**. The lock is
  always released. No Redis or filesystem lock is used.
- **Prediction catch-up.** The pass plans the missing closed 5m buckets
  **oldest-first** and processes each with the existing one-bucket cycle. A durable
  **watermark** (`shadow_recovery_watermarks`, runner `shadow_forecast_v1`) is
  advanced **only after** a bucket returns successfully, and only ever moves
  forward (monotonic). `PREDICTION_INSERTED`, `PREDICTION_DUPLICATE`,
  `PREDICTION_SKIPPED_NO_CONSENSUS`, and `PREDICTION_SKIPPED_REFERENCE_UNAVAILABLE`
  are all completed attempts. If a bucket raises, the watermark does **not** move
  past it; the next run retries it (the insert-once prediction write makes this
  safe).
- **First deployment / bootstrap.** With **no** watermark but existing predictions,
  the start position is derived from the newest stored prediction. With **neither**
  watermark nor prediction, only the **current** latest closed bucket is processed
  — never a historical replay. A hard **lookback bound** (24h = 288 buckets) caps
  how far back a stale runner reaches; older missing buckets are intentionally
  truncated and reported (`catchup_truncated_by_lookback`).
- **Per-invocation cap.** At most `--shadow-max-catchup-buckets` (default **12**)
  prediction buckets are processed per run (oldest kept, so the watermark keeps
  advancing across runs); truncation is reported (`catchup_truncated_by_cap`).
- **Outcome maturation.** After catch-up, the pass discovers **due** outcomes
  (a horizon whose evaluation window has ended by the UTC clock + soft grace) that
  are **missing** from `forecast_outcomes` (a real anti-join), for recent
  predictions within the lookback, capped at `--shadow-max-outcome-jobs`
  (default **100**). Each is evaluated sequentially with the existing outcome
  pipeline. Only `COMPLETE` outcomes are persisted.
- **INCOMPLETE retry.** An `INCOMPLETE` window (future 1m bars not all present yet)
  is **not** persisted, so it stays discoverable and is retried on a later run once
  the bars exist. A `COMPLETE` outcome is never re-evaluated under the same
  identity.
- **No six-month replay.** The lookback + per-invocation caps make each run
  bounded; there is no long-term replay/backtesting framework.

An explicit `--shadow-bucket-ts` still runs deterministic **one-bucket** work: it
does not read or advance the watermark, performs no catch-up, and (this PR) does
no broad outcome discovery.

`stage2.enabled` remains **false** and is reported as `stage2_global_enabled:false`
in every report — a shadow command is an explicit operational invocation, never
the Stage 2 master switch.

## STAGE2_CODE_VERSION (required for the systemd service)

The service user cannot run `git describe` in the root-owned repository, so the
analytics **code version must be supplied via the environment**. Set
`STAGE2_CODE_VERSION` in `/opt/signalbot/.env`:

- it is **required/recommended** for the systemd service (otherwise the run fails
  closed rather than using a silent `"unknown"`);
- it **must equal** the deployed `git rev-parse HEAD`;
- **refresh it after each deployment** (update `.env`) **before** the shadow timer
  next fires or is restarted;
- never print the full `.env` (set the single variable in place).

## Remaining limitations

- **no Telegram**, no notifications;
- **no trading** or order execution;
- **no calibration UI / long-term replay / backtesting framework**;
- **no ML / adaptive thresholds** — forecast/consensus/outcome formulas are
  unchanged.
