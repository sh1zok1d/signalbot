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

### 1. Pull merged `main` and verify the revision

```
cd /opt/signalbot
sudo -u signalbot git fetch origin
sudo -u signalbot git status --short          # expect a clean tree
sudo -u signalbot git rev-parse HEAD          # record the deployed revision
```

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

After a timer firing has completed, confirm a prediction row exists for the
processed bucket (read-only inspection; use the operator's normal DB access).

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

## Current limitations (predictions only)

This timer is deliberately minimal:

- it produces **automatic predictions only**;
- `due_outcome_jobs` remains **empty** on every invocation;
- there is **no automatic 15m / 1h / 4h outcome processing** yet;
- there is **no replay of every missed 5-minute bucket** (`Persistent=true` may
  trigger at most one current invocation after downtime — not full catch-up);
- there is **no pending-prediction discovery**;
- there are **no watermarks**;
- there are **no cross-process locks**;
- there is **no Telegram**;
- there is **no trading**.

The next **recovery / catch-up PR** will address missed predictions and the
maturation of 15m / 1h / 4h outcomes.
