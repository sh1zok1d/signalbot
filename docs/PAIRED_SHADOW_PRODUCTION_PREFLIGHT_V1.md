# Paired shadow production preflight

**Status:** prepared, not enabled (2026-10-12). `main` at the merge of #458, #459 and #460 is `0fc72db9ea6fdeb867f420725c3f40dbfd970f0d`. Production was not updated by that merge. Scenarios A and B below are not authorized by this document.

Nothing here changes user forecasts, `touch_live_cal`, sticky flags, the sharp-move detector, or user text. `SHADOW_RECORDING_ENABLED` stays false. The shadow SQL is not part of `apply_beta_schema`.

## What production already does

| Piece | Where | What it uses |
|---|---|---|
| Hourly market anchor | `beta.decision.load_live_bars` | Closed 5m history in `beta_hist_bars_5m`, then the Stage-1 Binance 1m tail (`klines_1m`) aggregated to closed 5m bars. The price is the last closed 1m close. The same function feeds the user decision block. |
| V1 nightly fit | `signalbot-beta-history.timer` at 02:20 UTC → `main.py --beta-history-build` → `beta.history_stats.run_history_build` | One grid from `load_history_grid`, then `rangecast.fit_range_model`. The result is one new `beta_hist_stats` row. A failed build leaves the previous row. Readers drop a row older than 72 hours (`decision.STATS_MAX_AGE`). |
| Outcome bars | `signalbot-beta-outcomes.timer` every 5 minutes → `beta.outcomes.run_outcomes_once` | Stage-1 `klines` for the user episode window. The paired shadow does not use that writer. Its settler scores 5m bars through `paired_shadow.score_anchor`. |
| Process control | systemd oneshots and timers under `/etc/systemd/system`, user `signalbot`, `EnvironmentFile=/opt/signalbot/.env` | History, outcomes, feeds, notify, detector, backup. Installing a unit does not enable it. `install_beta_units.sh` does not install the paired-shadow units. |

The W_L1 fit (`rangecast_shadow.fit_nightly_snapshot`, `SnapshotStore`) was not on a timer. The units in `deploy/signalbot-paired-shadow-*.timer` are the prepared connection. They are separate from the V1 history unit and do not insert `beta_hist_stats`.

## Live record

`scripts/beta/build_paired_shadow_record.py` and `run_paired_shadow_hour.py --from-live` load one snapshot and call `issue_live_record`.

- V1 comes from the newest `beta_hist_stats` row only when that row is inside 72 hours. A missing or stale row returns `NO_V1_MODEL` or `V1_STATS_STALE` and writes no file.
- W_L1 comes from `SnapshotStore.select`. `NO_SNAPSHOT`, `STALE_SNAPSHOT` and `MODEL_INVALID` write no file.
- Both binders run on that same bar. The stored digests must equal the Amendment 1 pins or the hour is `MODEL_INVALID`.
- A refusal has no price and no probability. `plan_shadow_record` stores nothing from it.
- A second `--from-live` in the same hour may see a later price and `as_of`. The anchor key does not include them. The first `as_of`, barriers and probabilities stay. The repeat does not raise, and settlement still runs on the frozen pair. A different distance, side or evaluation rule under that same key is still a conflict.

## W_L1 snapshots

`scripts/beta/fit_paired_shadow_snapshot.py` reads the same grid window as `run_history_build` and writes one JSON file under `PAIRED_SHADOW_SNAPSHOT_DIR`.

The snapshot unit sets `StateDirectory=signalbot/paired-shadow`, which systemd creates as `/var/lib/signalbot/paired-shadow` and makes writable under `ProtectSystem=strict`. `ReadWritePaths` names that same directory. The files go in its `snapshots` subdirectory. The hour unit bind-mounts that directory read-only and does not get `StateDirectory` or `ReadWritePaths` for it. If `STATE_DIRECTORY` is set and the snapshot path is outside it, the fit and the hour exit without writing.

| Condition | Behaviour |
|---|---|
| No file yet | `select` returns `NO_SNAPSHOT`. The hour refuses. The fit creates the directory and the first file. |
| `data_through` older than 72 hours | `select` returns `STALE_SNAPSHOT`. The hour refuses. |
| Process killed during the write | The temporary file is not `*_*.json`, so the next `select` ignores it. The next fit writes again. |
| File bytes no longer verify | `select` returns `MODEL_INVALID` and the hour refuses. The next fit of the same coefficients replaces that file. An older valid file is not served in its place. |
| Fit already running | `pg_try_advisory_lock(7311000457)` returns `BUSY`. This is not the V1 history lock `7311000007`. |
| Same coefficients, valid file | `put` stores nothing. The snapshot id does not change. |

The fit exits 2 unless `PAIRED_SHADOW_SNAPSHOT_APPROVED=1`. The shipped unit does not set that variable.

`systemd-analyze verify` accepts both units and both timers. Where systemd is not PID 1, the writable-path constraint was also checked in a private mount namespace: a root remounted read-only with a tmpfs only on `/var/lib/paired-shadow` refuses to create `/var/lib/signalbot/paired-shadow/snapshots` (`EROFS`). The same namespace with the tmpfs on `/var/lib/signalbot/paired-shadow` lets `SnapshotStore.put` create a verified file, mode `0600`, and a write outside that directory is refused.

## Connection file

`PAIRED_SHADOW_DSN` is the only URL the shadow scripts read. A `postgresql://` argument is refused and is not echoed. `psql` receives host, port, user, database and password through its environment, not through its argument list. Errors are redacted before they are printed.

The file is `/opt/signalbot/.env.paired-shadow`, mode `0600`, owner `signalbot`. The shadow units load that file and cannot read `/opt/signalbot/.env`. Their `ExecStartPre` is `deploy/wait_for_paired_shadow.py --timeout 60`: it connects with `PAIRED_SHADOW_DSN` and runs `SELECT 1`, with the same 5s connect timeout and 2s retry as `wait_for_infra.py`. It does not load the core config or `POSTGRES_PASSWORD`. The production units keep `wait_for_infra.py`. Create the connection file on the host, after a later go, with the URL already in the environment:

```bash
sudo -u signalbot /opt/signalbot/.venv/bin/python /opt/signalbot/scripts/beta/write_paired_shadow_env.py
```

The command prints the path and the mode. It does not print the URL. It does not overwrite an existing file unless `--replace` is passed.

## Read-only preflight

On the VPS, after the code deploy and the connection file exist, and before scenarios A and B:

```bash
sudo systemd-run --pipe --wait --collect \
  -p User=signalbot -p Group=signalbot \
  -p WorkingDirectory=/opt/signalbot \
  -p EnvironmentFile=/opt/signalbot/.env.paired-shadow \
  -p InaccessiblePaths=/opt/signalbot/.env \
  /opt/signalbot/.venv/bin/python /opt/signalbot/scripts/beta/paired_shadow_preflight.py
```

Optional: `Environment=PAIRED_SHADOW_EXPECTED_SHA=0fc72db9ea6fdeb867f420725c3f40dbfd970f0d` after that commit is what the host is running.

The JSON report has `status` `PASS`, `NOT_READY` or `FAIL`. It includes the deployed SHA, PostgreSQL `server_version`, history and live-bar ages, free disk, backup timer state and dump age, the listed systemd units, the snapshot state, and the two spec digests. It does not include the URL, a password, a price, or a user row.

| Check | PASS | Not ready / fail |
|---|---|---|
| SHA | `BUILD_SHA` when the installer wrote it, otherwise git HEAD. `git status --porcelain` reports no tracked change, `BUILD_SHA` equals HEAD when both exist, and the value matches `PAIRED_SHADOW_EXPECTED_SHA` when that is set. The report does not list paths | missing, a tracked change (`DIRTY_TREE`), `BUILD_SHA` disagreeing with HEAD, expected SHA disagreeing with the deployed identity, or git status unavailable (`TREE_UNKNOWN`) |
| Digests | `v1_spec_digest()` and `shadow_spec_digest()` equal the pins in `beta/paired_shadow.py` | any other value, or the identity check raises |
| Recording | `SHADOW_RECORDING_ENABLED` is false | true |
| Sources | history present, statistics younger than 72 hours, last Binance 1m bar younger than 15 minutes | no history, stale history, stale live bars, or `DSN_UNSET` |
| Disk | at least 2 GiB free on the snapshot filesystem | less than 2 GiB |
| Backup | `signalbot-backup.timer` enabled and the newest `backups/btcbot_*.sql.gz` younger than 36 hours | timer off, no dump, or dump older than 36 hours |
| Schedulers | production units are visible and neither paired-shadow timer is `enabled` | `systemctl` returns no unit state (`SYSTEMCTL_UNAVAILABLE`), or either paired-shadow timer is `enabled` |
| Snapshot | a verifiable W_L1 file is in force | `NO_SNAPSHOT`, `STALE_SNAPSHOT`, or `MODEL_INVALID` |

Exit 0 is `PASS`, exit 3 is `NOT_READY`, exit 1 is `FAIL`. A `NOT_READY` snapshot is expected until the first approved fit. Do not start scenario B while the report is `FAIL`.

## Scenario A — schema, not started

Run only after a backup `PASS` and an owner go. One transaction (`psql -1`): a failed script leaves no shadow tables.

```bash
sudo systemd-run --pipe --wait --collect \
  -p User=signalbot -p Group=signalbot \
  -p WorkingDirectory=/opt/signalbot \
  -p EnvironmentFile=/opt/signalbot/.env.paired-shadow \
  -p Environment=PAIRED_SHADOW_SCHEMA_APPROVED=1 \
  -p InaccessiblePaths=/opt/signalbot/.env \
  /opt/signalbot/.venv/bin/python /opt/signalbot/scripts/beta/apply_paired_shadow_schema.py
echo "apply_exit=$?"
```

PASS: the apply exits 0. Run the preflight command again. `checks.sources.shadow_tables` is true and `checks.recording.status` is `PASS`. `beta_claims` is not queried and is not altered. The product units are not restarted.

FAIL: non-zero apply exit. The transaction is rolled back. Do not retry until the stderr class (not a URL) is understood. Do not enable the hour timer.

Stop, before any hour has been written: leave the empty tables in place. They are not read by the bot. Do not `DROP` them after scenario B has stored rows unless the owner asks for that separately. Disable remains:

```bash
sudo systemctl disable --now signalbot-paired-shadow-hour.timer signalbot-paired-shadow-snapshot.timer
sudo rm -f /etc/systemd/system/signalbot-paired-shadow-hour.service.d/write.conf \
           /etc/systemd/system/signalbot-paired-shadow-snapshot.service.d/fit.conf
sudo systemctl daemon-reload
```

## Scenario B — hour, nightly fit, settlement, not started

Requires scenario A `PASS`, a preflight that is `PASS` except the snapshot may still be `NOT_READY`, and a separate owner go.

1. Install the units. This does not enable them.

```bash
sudo /opt/signalbot/deploy/install_paired_shadow_units.sh
systemctl is-enabled signalbot-paired-shadow-hour.timer signalbot-paired-shadow-snapshot.timer
```

PASS: both print `disabled`. FAIL: either prints `enabled`. Stop with the disable command above.

2. One manual fit. The drop-in is the approval. Remove it to turn the fit off.

```bash
sudo mkdir -p /etc/systemd/system/signalbot-paired-shadow-snapshot.service.d
sudo tee /etc/systemd/system/signalbot-paired-shadow-snapshot.service.d/fit.conf >/dev/null <<'EOF'
[Service]
Environment=PAIRED_SHADOW_SNAPSHOT_APPROVED=1
EOF
sudo systemctl daemon-reload
sudo systemctl start signalbot-paired-shadow-snapshot.service
systemctl show signalbot-paired-shadow-snapshot.service -p Result -p ExecMainStatus
```

PASS: `Result=success`, `ExecMainStatus=0`, and the journal line has `"status": "OK"`, `"stored": true` on the first fit, and a `snapshot_id`. The V1 timer is not restarted and no new `beta_hist_stats` row is required for this command. FAIL: any other result. Leave the drop-in removed (the stop command) and do not enable the timer. A `BUSY` result means the fit was already running; wait and read the first run, do not start a second one.

3. One dry hour. The shipped unit has no `--write`.

```bash
sudo systemctl start signalbot-paired-shadow-hour.service
journalctl -u signalbot-paired-shadow-hour.service -n 20 --no-pager
```

PASS: exit 0, `"written": false`, `"status": "OK"`, `n_issues` greater than 0, horizons that are not in an event zone are `OK`. FAIL: exit 3 (`NO_SNAPSHOT`, `STALE_SNAPSHOT`, `MODEL_INVALID`, `NO_V1_MODEL`, `V1_STATS_STALE`) or exit 1. Do not add the write drop-in.

4. One real hour, then a restart of the same hour.

```bash
sudo mkdir -p /etc/systemd/system/signalbot-paired-shadow-hour.service.d
sudo tee /etc/systemd/system/signalbot-paired-shadow-hour.service.d/write.conf >/dev/null <<'EOF'
[Service]
Environment=PAIRED_SHADOW_HOUR_APPROVED=1
ExecStart=
ExecStart=/opt/signalbot/.venv/bin/python /opt/signalbot/scripts/beta/run_paired_shadow_hour.py --from-live --bars-from-db --write
EOF
sudo systemctl daemon-reload
sudo systemctl start signalbot-paired-shadow-hour.service
sudo systemctl start signalbot-paired-shadow-hour.service
```

PASS, first start: `"written": true`, `"inserted"` greater than 0, settlement `"launched": true`, settlement `"status"` is `OK`, `"stored"` greater than 0 for horizons that have already elapsed. PASS, second start: `"inserted": 0`, settlement `"selected": 0` for anchors that already have an outcome. The journal text contains no `postgresql://`. FAIL: settlement `NO_BARS`, a non-zero exit, or a second start that inserts again. Stop with the disable command and remove `write.conf`. Rows already stored stay; they are not user claims.

5. Enable the two timers only after steps 2 and 4 passed once.

```bash
sudo systemctl enable --now signalbot-paired-shadow-snapshot.timer signalbot-paired-shadow-hour.timer
```

Stop at any time:

```bash
sudo systemctl disable --now signalbot-paired-shadow-hour.timer signalbot-paired-shadow-snapshot.timer
sudo rm -f /etc/systemd/system/signalbot-paired-shadow-hour.service.d/write.conf \
           /etc/systemd/system/signalbot-paired-shadow-snapshot.service.d/fit.conf
sudo systemctl daemon-reload
```

A disable stops the next hour and the next fit. It does not restart the bot, the history unit, or the outcomes unit.

## First real shadow hour

The first real hour is scenario B step 4, one manual start, after A and after one successful fit. Do not enable the timers in that same step. Read the two journal lines, confirm the second start stored nothing new, and only then decide whether the timers should be enabled.
