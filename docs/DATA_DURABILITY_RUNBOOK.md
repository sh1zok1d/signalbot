# Data durability & off-site backup runbook (INFRA-D1)

This document covers the **off-site data durability layer**: extending the
existing local `deploy/backup.sh` / `deploy/restore.sh` foundation with an
off-site copy (via `rclone`, to a generic operator-configured remote — Google
Drive is the documented initial example, never hardcoded), daily/weekly/
monthly remote retention, systemd automation, and periodic restore
verification.

**This is infrastructure, not a trading feature.** It changes no V1/V2 rule,
no `rules_version`/`calculation_version`, and no schema. It protects data
that is already persisted; it computes nothing.

**No production deployment was performed while authoring this PR.** No unit
was installed, no timer was enabled, no rclone remote was configured, and no
restore was run against any real server. Everything below the artifacts
themselves (deploy/signalbot-backup*.service/.timer,
deploy/signalbot-backup-verify*.service/.timer, deploy/sync_backup_offsite.sh,
deploy/install_backup_timer.sh, deploy/check_backup_timer.sh) is an operator
runbook for a **separate, explicit, later action** — see §19 of the INFRA-D1
task and `docs/FORECASTING_ROADMAP.md`.

---

## A. What is protected

The PostgreSQL/TimescaleDB contents of the `btcbot` database, i.e. everything
`deploy/backup.sh`'s `pg_dump` captures:

- raw historical market data (`klines_1m` and related raw tables);
- Stage 2 feature/consensus/percentile history;
- V1 forecast history (`forecast_predictions`, `forecast_outcomes`);
- future V2 persistence (`v2_episode_events` and anything added later) —
  this runbook covers the database as a whole, not a fixed table list, so it
  automatically covers new tables without a runbook change.

This dataset is becoming a durable research/replay asset: once ingested,
**our own retention governs it, not the exchange API's retention** — Binance
does not promise to keep historical klines/OI/liquidations available
indefinitely, so a gap here cannot be re-backfilled from the exchange later.

## B. What is NOT automatically protected

- **Plaintext application secrets** (`/opt/signalbot/.env`,
  `/etc/signalbot/backup.env`, the rclone config/token) are **not** included
  in the database backup or the off-site sync. `deploy/backup.sh` dumps only
  the database; `deploy/sync_backup_offsite.sh` uploads only that dump.
  Secret recovery is a **separate, deliberately out-of-scope** hardening item
  — see §M.
- Anything outside the `btcbot` database (application code, systemd units,
  OS configuration) — that is what `git`/the deployment runbooks already
  cover, not this one.
- Redis (`btcbot_redis`) — hot/derived state only, intentionally not
  persisted; not in scope here.

## C. Local backup (existing foundation — unchanged by this PR)

`deploy/backup.sh` (already merged, not modified by INFRA-D1):

- runs `pg_dump` inside the running `btcbot_timescaledb` container;
- writes a gzip-compressed, plain-SQL dump to `backups/btcbot_<UTC
  timestamp>.sql.gz` (`BACKUP_DIR`, default `<repo>/backups`);
- uses a `.partial` file until the dump is verified non-empty and
  `gzip -t`-valid, so a failed/partial dump never replaces a good one;
- keeps a configurable number of local backups (`BACKUP_RETENTION`, default
  7), pruning older ones.

This alone protects against **DB corruption**, not against **losing the
VPS** — the local `backups/` directory lives on the same disk as the live
database. That is exactly the gap INFRA-D1 closes.

## D. Off-site backup

`deploy/sync_backup_offsite.sh` (new in INFRA-D1) uploads ONE completed local
backup to an `rclone`-compatible remote, then applies remote retention:

```
TimescaleDB -> deploy/backup.sh -> LOCAL (newest 7) -> deploy/sync_backup_offsite.sh -> <REMOTE>/{daily,weekly,monthly}/
```

- selects the newest **completed** local dump by default (`btcbot_*.sql.gz`,
  never a `.partial`), or accepts an explicit path as `$1`;
- re-validates the dump locally before upload (non-empty, `gzip -t` valid);
- requires `rclone` and an explicitly configured remote — refuses to run
  otherwise (fail closed, never assumes a default provider);
- uploads to `<remote>/daily/`, then conditionally to `<remote>/weekly/` and
  `<remote>/monthly/` (see §F);
- fails loudly (non-zero exit) on any upload failure, and **never deletes
  the local dump** — a failed off-site run leaves the next scheduled run free
  to retry from the same local file;
- is idempotent: re-running against the same dump does not duplicate or
  corrupt the remote copy (same destination filename, same content).

It depends **only** on the `rclone` binary and the remote you configure — see
§E for Google Drive as the documented example, and §I for how the remote is
actually set on the VPS. Swapping to Backblaze B2, S3, or any other
`rclone`-supported backend requires **no code change**, only a different
`SIGNALBOT_BACKUP_REMOTE` value and a different `rclone` remote definition.

## E. Google Drive example setup

Google Drive is the **initial recommended** setup for this personal
deployment, purely because it needs no separate account/billing setup beyond
an existing Google account. It is documentation, not a code dependency —
nothing in `deploy/sync_backup_offsite.sh` references Google or Drive.

On the VPS, as the admin/root user (see §F for why root):

```bash
# Create the config directory and point THIS invocation at the same
# explicit path signalbot-backup.service uses (RCLONE_CONFIG=
# /etc/signalbot/rclone.conf) -- NOT rclone's interactive default of
# ~/.config/rclone/rclone.conf (/root/.config/rclone/rclone.conf for root).
# Using the same explicit path here means this manual setup exercises the
# EXACT credential surface the systemd timer will read later -- a config
# that only works when run interactively as root, but not from the timer,
# is exactly the failure mode this avoids. See §1 rationale below.
sudo install -d -m 0700 -o root -g root /etc/signalbot
sudo RCLONE_CONFIG=/etc/signalbot/rclone.conf rclone config
# n) New remote
# name>            gdrive
# Storage>         (select "Google Drive" / "drive" from the list)
# client_id>       <leave blank to use rclone's default, or supply your own>
# client_secret>   <leave blank to use rclone's default, or supply your own>
# scope>           1  (Full access, or "drive.file" for a narrower app-only scope)
# root_folder_id>  <leave blank>
# service_account_file> <leave blank>
# Edit advanced config? n
# Use auto config?  y   (opens a browser OAuth flow; use `rclone authorize`
#                        from a machine with a browser if the VPS is headless)

# rclone writes the config file itself as 0600; confirm/enforce ownership+mode:
sudo chown root:root /etc/signalbot/rclone.conf
sudo chmod 600 /etc/signalbot/rclone.conf
```

This writes the remote definition (including the OAuth token) into
`/etc/signalbot/rclone.conf` — the explicit, non-default path
`signalbot-backup.service` itself is configured with
(`Environment=RCLONE_CONFIG=/etc/signalbot/rclone.conf`), never rclone's
interactive default under `/root`. Then set, in `/etc/signalbot/backup.env`
(see §I):

```
SIGNALBOT_BACKUP_REMOTE=gdrive:signalbot-backups
```

`rclone` creates the `signalbot-backups` folder (and `daily/`, `weekly/`,
`monthly/` under it) on first upload — no manual folder creation needed.

## F. Installing/configuring rclone without committing its auth tokens

- Install `rclone` on the VPS via the OS package manager or the official
  install script (https://rclone.org/install/) — an operator action, not
  part of this repository.
- Run `rclone config` **as root** (the same user `signalbot-backup.service`
  runs as), with `RCLONE_CONFIG=/etc/signalbot/rclone.conf` explicitly set
  (§E) — **not** rclone's interactive default of
  `~/.config/rclone/rclone.conf` (`/root/.config/rclone/rclone.conf` for
  root). `signalbot-backup.service` runs with `ProtectHome=true`, which
  makes `/root` (and every other home directory) inaccessible to it — a
  config file placed there would work when an admin runs `rclone`
  interactively, then silently fail to be found only once the *timer* fires
  unattended. Using the same explicit, non-`/root` path both interactively
  and in the unit avoids that trap entirely, and lets `ProtectHome=true`
  stay fully enabled rather than being weakened just to reach a credential
  file.
- The resulting `/etc/signalbot/rclone.conf` must be mode `0600`, owned by
  `root:root` — readable by root only, never by the unprivileged
  `signalbot` application user, never checked into git (it is outside the
  repository entirely), and never referenced by *value* in any script or
  unit file in this repository. Its *path* is referenced explicitly (by
  `signalbot-backup.service`'s `RCLONE_CONFIG=` and by
  `install_backup_timer.sh`'s pre-activation check) — the path itself is
  not a secret; only the file's contents are.
- The remote **name and path** (`SIGNALBOT_BACKUP_REMOTE=gdrive:signalbot-backups`)
  is not itself a secret and lives in `/etc/signalbot/backup.env` (§I) — the
  token/credential stays exclusively in `rclone.conf`.
- **Never** put a token, client secret, or `rclone.conf` contents into: git,
  `.env.example`, a systemd unit source, or a shell script source. This
  repository's tests
  (`tests/deploy/test_backup_systemd.py::test_backup_service_no_secret_literal_in_unit_source`)
  statically check the unit sources contain no such literal.
- `install_backup_timer.sh --enable-now` fails closed, before activating
  either timer, if `rclone` is not on `PATH` or
  `/etc/signalbot/rclone.conf` is missing/unreadable — printing only that
  fact, never the file's contents.

## G. Enabling the systemd backup timer

Two independent oneshot+timer pairs, both root-run (see rationale below),
following the same install/check pattern as the existing shadow/telegram
timers:

```bash
# 1. Create /etc/signalbot/backup.env FIRST (required — the installer
#    refuses to install signalbot-backup.service without it):
sudo install -d -m 0755 /etc/signalbot
sudo tee /etc/signalbot/backup.env > /dev/null <<'EOF'
SIGNALBOT_BACKUP_REMOTE=gdrive:signalbot-backups
# Optional — these are the script's own defaults if omitted:
# SIGNALBOT_BACKUP_DAILY_RETENTION=30
# SIGNALBOT_BACKUP_WEEKLY_RETENTION=12
# SIGNALBOT_BACKUP_MONTHLY_RETENTION=12
EOF
sudo chown root:root /etc/signalbot/backup.env
sudo chmod 600 /etc/signalbot/backup.env

# 2. Install + validate (install-only by default, matches the existing
#    shadow/telegram installer contract):
sudo /opt/signalbot/deploy/install_backup_timer.sh

# 3. Explicitly activate both timers. This step fails closed (before
#    enabling anything) unless `rclone` is on PATH AND
#    /etc/signalbot/rclone.conf is present/readable -- complete §E/§F
#    (rclone install + `rclone config` at that exact path) BEFORE this step:
sudo /opt/signalbot/deploy/install_backup_timer.sh --enable-now
```

**Why root, not the `signalbot` application user:** `deploy/backup.sh` needs
`docker exec` into the TimescaleDB container to run `pg_dump`, and the
project's existing posture is explicit — "Do NOT add signalbot to the docker
group" (`deploy/signalbot.service`). INFRA-D1 does not weaken that; it keeps
the privileged backup/restore path on the pre-existing admin/root trust
boundary that `deploy/backup.sh`/`deploy/restore.sh` already assumed (their
own header comments say "run by an ADMIN").

## H. Inspecting the timers (read-only)

```bash
/opt/signalbot/deploy/check_backup_timer.sh
```

This is **strictly read-only** — no mutating `systemctl` verb, no secret
printed (see `tests/deploy/test_backup_systemd.py`). It reports, for both
`signalbot-backup.{service,timer}` and
`signalbot-backup-verify.{service,timer}`: enabled/active state, the
scheduled next/last run (`systemctl list-timers`), full `systemctl status`,
and the last 50 journal lines.

Individual commands, if preferred:

```bash
systemctl list-timers --all signalbot-backup.timer signalbot-backup-verify.timer
journalctl -u signalbot-backup.service -n 50 --no-pager
journalctl -u signalbot-backup-verify.service -n 50 --no-pager
```

**Local files:** `ls -lht /opt/signalbot/backups/`
**Remote files:** `sudo RCLONE_CONFIG=/etc/signalbot/rclone.conf rclone lsf
gdrive:signalbot-backups/daily/` (substitute `weekly`/`monthly`, and your
actual remote name/path). The explicit `RCLONE_CONFIG=` here exercises the
same credential file the timer itself reads (§F) — omitting it falls back
to rclone's interactive default, which may not even exist for the `root`
user if the config was only ever created at the explicit path.

## I. Manually running one backup

```bash
# local dump only:
sudo /opt/signalbot/deploy/backup.sh

# off-site sync of the newest local dump (reads SIGNALBOT_BACKUP_* from the
# environment -- source /etc/signalbot/backup.env first, or export them):
sudo bash -c 'set -a; source /etc/signalbot/backup.env; set +a; /opt/signalbot/deploy/sync_backup_offsite.sh'

# or trigger the full systemd job (local dump, then off-site sync, in order):
sudo systemctl start signalbot-backup.service
journalctl -u signalbot-backup.service -n 50 --no-pager
```

## J. Disaster recovery: total VPS loss

Designed procedure (see §K for the distinction between "designed" and
"drilled"):

```
NEW VPS
  -> install Docker + project OS-level dependencies (git, python3-venv, ...)
  -> git clone <signalbot repo> /opt/signalbot
  -> restore/reconfigure rclone credentials:
       install rclone; `sudo RCLONE_CONFIG=/etc/signalbot/rclone.conf rclone
       config` (or copy a securely-transferred rclone.conf back to
       /etc/signalbot/rclone.conf, mode 0600 owned root:root -- the SAME
       explicit path signalbot-backup.service uses, never
       /root/.config/rclone/rclone.conf)
  -> download the selected remote backup:
       sudo RCLONE_CONFIG=/etc/signalbot/rclone.conf rclone copyto \
           gdrive:signalbot-backups/daily/btcbot_<TS>.sql.gz \
           /opt/signalbot/backups/btcbot_<TS>.sql.gz
       # or pick a weekly/monthly representative instead of daily/, depending
       # on how far back you need to go
  -> docker compose up -d            # bring up TimescaleDB (+ Redis)
  -> deploy/restore.sh --force-live /opt/signalbot/backups/btcbot_<TS>.sql.gz
       # explicit confirmation phrase required; see deploy/restore.sh
  -> validate the DB:
       docker exec -it btcbot_timescaledb psql -U btcbot -d btcbot \
           -c "SELECT count(*) FROM klines_1m;"
       # or: deploy/restore.sh --self-test  (restores into a THROWAWAY DB
       # from the SAME dump, verifies, drops it -- an extra check that does
       # not touch the just-restored live DB)
  -> only THEN resume ingestion/services:
       sudo systemctl start signalbot.service
       # shadow/telegram/backup timers as applicable
```

Recreate `/opt/signalbot/.env` and `/etc/signalbot/backup.env` on the new VPS
before this — they are not part of the database backup (see §B/§M).

## K. Restore self-test (safe, no live-DB risk)

```bash
sudo /opt/signalbot/deploy/restore.sh --self-test
```

Reused verbatim (INFRA-D1 adds **no** second restore implementation) —
restores the latest local dump into a throwaway
`btcbot_restore_selftest_<timestamp>` database, runs
`SELECT count(*) FROM klines_1m`, reports `SELF_TEST_RESULT: PASS`/`FAIL`,
and always drops the throwaway DB (even on failure, via a `trap`). It never
accepts `--force-live` and never touches the live `POSTGRES_DB`.

INFRA-D1 additionally wires this into `signalbot-backup-verify.service` +
`.timer`, firing approximately monthly (`OnCalendar=*-*-01 04:00:00 UTC`,
`Persistent=true`) so restorability is checked periodically, not only
assumed from "a backup file exists." A failure here returns non-zero and is
visible via `systemctl status signalbot-backup-verify.service` /
`journalctl -u signalbot-backup-verify.service`.

**Distinction that matters:** the disaster-recovery procedure in §J is a
**designed** procedure, reviewed against the actual scripts it invokes. It
has **not** been executed end-to-end against a brand-new VPS as part of this
PR — no VPS access was used (see the top of this document and INFRA-D1 §19).
Treat §J as "this is how it should work," not "this has been drilled."
Running an actual disaster-recovery drill on a throwaway VPS is a reasonable
follow-up **outside** this PR.

## L. Retention policy

**Local** (`deploy/backup.sh`, unchanged): newest `BACKUP_RETENTION` dumps
(default 7).

**Remote** (`deploy/sync_backup_offsite.sh`, new): three independent tiers
under `<remote>/{daily,weekly,monthly}/`, UTC-keyed:

| Tier | Participation | Kept |
|---|---|---|
| `daily/` | every successful backup | newest 30 (`SIGNALBOT_BACKUP_DAILY_RETENTION`) |
| `weekly/` | at most one representative per **ISO/UTC week** | newest 12 (`SIGNALBOT_BACKUP_WEEKLY_RETENTION`) |
| `monthly/` | at most one representative per **UTC calendar month** | newest 12 (`SIGNALBOT_BACKUP_MONTHLY_RETENTION`) |

Representative selection is deterministic: for `weekly`/`monthly`, the
script derives each candidate's period key (`date -u +%G-%V` / `+%Y-%m`)
directly from the dump's own embedded UTC timestamp
(`btcbot_YYYYMMDDTHHMMSSZ.sql.gz`) — never from "did the timer happen to
fire on a particular day," which would silently skip a period entirely if
the VPS was offline at exactly the wrong moment. If a representative for the
current period is already present remotely, no duplicate is uploaded.

Pruning deletes only objects **beyond** the configured count, one at a time
(`rclone deletefile`, never a directory-wide `rclone delete`), confined to
the exact configured `<remote>/<tier>/` path — `SIGNALBOT_BACKUP_REMOTE`
itself is refused at startup unless it has a non-empty path component after
the colon, so pruning can never reach a remote root.

## M. Failure modes

Frozen operational semantics (also enforced by
`tests/deploy/test_sync_backup_offsite.py`):

- **Local dump fails** (`deploy/backup.sh` exits non-zero): the off-site
  sync never runs — `signalbot-backup.service` has two ordered
  `ExecStart=` lines under `Type=oneshot`; systemd skips the second if the
  first fails.
- **Local dump succeeds, remote upload fails**: the local dump is left
  intact (nothing in `sync_backup_offsite.sh` ever deletes it), the job
  reports failure (non-zero exit, visible in `journalctl`), and the next
  scheduled run retries from the same local file.
- **Remote retention pruning fails**: the just-uploaded backup is **not**
  deleted to force a false "success" — pruning only ever targets objects
  strictly beyond the retention count (never the newest upload), and any
  `rclone deletefile` failure aborts the script non-zero immediately.
- **Restore self-test fails**: the live database is never touched (the
  self-test path only ever creates/drops a throwaway DB); the job reports
  failure.
- **No "best effort success" is ever masked** — every failure path above
  exits non-zero and is visible in `systemctl status`/`journalctl`.

**Known, deliberately out-of-scope follow-ups** (not implemented in
INFRA-D1 — see the roadmap for sequencing):

- **Secret recovery**: `/opt/signalbot/.env`, `/etc/signalbot/backup.env`,
  and the rclone config/token are not backed up by this mechanism at all —
  a total VPS loss requires recreating them by hand (§J). An encrypted
  off-site copy of these (with separate key management) is a real future
  hardening item, deliberately **not** invented inside this PR (INFRA-D1
  §12 explicitly avoids adding new encryption/key-management
  infrastructure here).
- **Provider VPS snapshots**: a provider-level VPS snapshot MAY be used as a
  *secondary* operational convenience (faster full-VPS recovery than
  reinstalling from scratch), but **a provider snapshot is not an off-site
  backup** — provider account loss or provider-side incident can affect both
  the VPS and its provider-local snapshot simultaneously. This PR does not
  implement any provider-API snapshot automation.
- **PITR / WAL archiving**: `pgBackRest`/WAL archiving/point-in-time
  recovery are documented here as a future scalability upgrade *if* DB size
  growth makes daily full `pg_dump`s expensive or a lower RPO becomes
  important. The current target is intentionally simpler: daily `pg_dump` +
  off-site retention + periodic restore verification. Not implemented here.
