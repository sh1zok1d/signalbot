# Beta audit de-identification V1 (OUT-8) — prepared, not run

**Status:** `PREPARED / NOT_RUN / OWNER_GO_REQUIRED` (2026-10-08). Nothing here has been run on production. The owner runs it after a go, following the steps in §4.

**Why.** Before #418, three deletion audit rows kept per-person data in `beta_admin_audit`:
- `admin_remove` and `retention_purge` stored `target_fingerprint`;
- all three (`user_delete_me`, `admin_remove`, `retention_purge`) stored per-person row counts (`users`, `allowlist`, `waitlist`, `activity`).

Since #418 the code writes only `detail.cohort`. The owner's rule (2026-10-08): after `/delete_me`, keep only a permitted de-identified aggregate, never a personal record. This file prepares the same change for the rows written before #418.

## 1. What remains per row after redaction, and what can still link it

**What remains, per deletion row:**

| Field | Value | Why it is kept |
|---|---|---|
| `audit_id` | sequence number | the primary key; the table is append-only |
| `action` | `user_delete_me` / `retention_purge` / `admin_remove` | which deletion path ran |
| `authorized`, `result` | `true`, `OK` | that the deletion was legitimate |
| `actor_fingerprint` | `participant`, `system`, or the **owner's** fingerprint for `admin_remove` | who acted (never the deleted person) |
| `target_fingerprint` | `NULL` | — |
| `detail` | `{"cohort": {joined_kyiv_date, known_contact, joined_after_test_open}}`, or `{"cohort": null}` for someone who never joined | the frozen denominator (contract §1.3, §1.5) |
| `recorded_at` | the deletion instant | not changed (see below) |

**Alone, no field names a person:**
- No Telegram id, chat id or fingerprint of the deleted person is left.
- The counts are gone.

**The fingerprints that were removed were linkable.** `fingerprint()` is `sha256("signalbot-beta-v0:<telegram id>")[:12]`, unsalted. Anyone who has a Telegram id can compute it. Removing it is the substance of this change.

**In combination, there is a residual risk, stated plainly.** In a cohort of about 10, these can single out a row:
- `joined_kyiv_date` + `known_contact` + `recorded_at` (to the second);
- `audit_id` ordering next to other audit rows.

Who can single it out:
- Someone who already knows when a given person joined and left: the owner, from the chat or the private U3 ledger. That person can match the row.
- A reader with only the database cannot name the person from these fields.

The audit row's own instant next to `joined_kyiv_date` is the strongest combination: it gives the exact days in and out.

**The owner's options, built as switches (§3).** Until the owner answers, each switch defaults to the most protective setting.
- **Coarsen the time (`coarsen`, default on).** `recorded_at` of the deletion rows is cut to the Kyiv date, so only the date of deletion is kept. Off means the rows are accepted as they are, as the permitted de-identified aggregate.
- **The other audit rows (`other_actions`, default on).** `admin_known`, `admin_reply` and `admin_add` rows still carry the `target_fingerprint` of a participant who later deleted themselves, and that fingerprint is recomputable from a Telegram id. With this switch on, those fingerprints are removed when they belong to nobody still present.
- **Salting the fingerprint.** This is a separate code PR, not this script.

## 2. Read-only count (VPS)

```bash
OWNER_FP=$(python -c "from beta.admin import fingerprint; print(fingerprint(<owner telegram id>))")
psql "$DSN" -X -v owner_fp="$OWNER_FP" -f deploy/signalbot-beta-audit-deidentify-count.sql
```

The file runs inside `BEGIN TRANSACTION READ ONLY … ROLLBACK`. For each deletion action it prints:
- the rows;
- rows with a target fingerprint;
- rows whose target is the owner;
- rows whose actor is the owner;
- rows with extra detail keys;
- rows without a cohort record;
- the first and last `recorded_at`.

It then prints the number of rows the redaction would change. It assumes nothing about test accounts: the owner-target column shows which rows are the owner's own.

## 3. The redaction, its switches, and how it gets past append-only

`deploy/signalbot-beta-audit-deidentify.sql`, in one transaction:
1. `LOCK TABLE beta_admin_audit IN ACCESS EXCLUSIVE MODE`.
2. Print the before counts.
3. `DISABLE TRIGGER trg_beta_audit_append_only`.
4. Run the updates below.
5. `ENABLE TRIGGER`.
6. Print the after counts and the trigger state (`O` = enabled).
7. `COMMIT`.

- **Always, on the deletion rows** (`user_delete_me`, `retention_purge`, `admin_remove`):
  - `target_fingerprint = NULL`;
  - `detail = {"cohort": …}` with `joined_after_test_open = false`. Every pre-#418 deletion predates any `/admin_test_open`, so false is the true value.
- **The owner's three pending decisions.** Until the owner answers, the defaults are the most protective:

| Switch (`psql -v`) | Default | Effect |
|---|---|---|
| `coarsen` | `on` | `recorded_at` of the deletion rows is cut to 00:00 of its Kyiv date, so the exact deletion time is gone. |
| `other_actions` | `on` | `admin_known` / `admin_reply` / `admin_add` rows lose their `target_fingerprint` when it belongs to nobody still in `beta_users`, `beta_allowlist` or `beta_waitlist`. Matching uses the same formula as `beta.admin.fingerprint`, computed in SQL. The owner's own fingerprint is never touched. |
| salted fingerprints | — | **Not this script:** a separate code PR. |

**Why disabling the trigger this way is safe:**
- Only the named append-only trigger is disabled, never `session_replication_role`, which would switch off every trigger and foreign key.
- `ALTER TABLE` holds an ACCESS EXCLUSIVE lock to the end of the transaction, so no other session can read or write the table while the trigger is off.
- `ON_ERROR_STOP` plus the single transaction mean any error rolls everything back, the `DISABLE` included.
- It needs the table owner. In the docker setup that is `POSTGRES_USER`, which created the schema.
- It is idempotent: every update reports `UPDATE 0` on a second run.

**Tested.**
- `tests/beta/test_beta_audit_deidentify_pg.py` runs both files with `psql` on PostgreSQL 16 against representative pre-#418 rows. It covers:
  - the count changes nothing;
  - only the intended rows change;
  - the cohort fields are exactly three;
  - coarsening to the Kyiv date;
  - only the deleted person's `admin_known` fingerprint goes;
  - append-only again afterwards;
  - both switches off;
  - idempotence.
- Blocks A and B below were run verbatim on 2026-10-08:
  - against a `postgres:16` container named `btcbot_timescaledb` (`POSTGRES_USER` / `POSTGRES_DB` = `btcbot`);
  - with the beta schema and representative rows;
  - with `/opt/signalbot` as a clone with its own `.env`;
  - with the scripts fetched from `pull/418/head`.

  Results:
  - Block A left every production row unchanged, redacted the scratch copy (count afterwards: 0 to redact), dropped `deid_scratch`, and left the working tree and `HEAD` of `/opt/signalbot` untouched.
  - Block B, with `systemctl` stubbed, redacted production and its count afterwards was 0.

## 4. Owner command blocks (VPS, as the user that runs `deploy/backup.sh`)

**What the owner types:** nothing but pasting the block.
- Everything comes from `/opt/signalbot/.env`, read in a subshell, with the same defaults as `deploy/backup.sh` and `docker-compose.yml`:
  - container `btcbot_timescaledb`;
  - `POSTGRES_DB` / `POSTGRES_USER` = `btcbot`;
  - `BETA_OWNER_TELEGRAM_USER_ID`.
- The owner's fingerprint is computed inline with the bot's formula, without importing the repo.
- The scripts are not on `main` yet. `git fetch origin pull/418/head` only updates refs, never the working tree. `git archive FETCH_HEAD` extracts the two files into `/tmp/deid`. There is no pull and no checkout in `/opt/signalbot`.
- The block prints the commit the scripts came from. Check it against the PR head; GitHub can lag a few seconds after a push.

**Block A — now, read-only on production.** The only database it writes is the scratch `deid_scratch` inside the same container, dropped at the end.

```bash
# ---- Block A: now, read-only on production. Writes only a scratch database deid_scratch inside the same container.
set -euo pipefail
cd /opt/signalbot
# 1) settings, read from /opt/signalbot/.env in a subshell, defaults as in deploy/backup.sh and docker-compose.yml
eval "$( (set -a; . /opt/signalbot/.env; set +a
          printf 'C=%q\nDB=%q\nU=%q\nOWNER_ID=%q\n' "${BTCBOT_PG_CONTAINER:-btcbot_timescaledb}" \
                 "${POSTGRES_DB:-btcbot}" "${POSTGRES_USER:-btcbot}" "${BETA_OWNER_TELEGRAM_USER_ID:-}") )"
[ -n "$OWNER_ID" ] || { echo "BETA_OWNER_TELEGRAM_USER_ID is empty in /opt/signalbot/.env"; exit 1; }
OWNER_FP=$(python3 -c 'import hashlib,sys; print("u_" + hashlib.sha256(("signalbot-beta-v0:%d" % int(sys.argv[1])).encode()).hexdigest()[:12])' "$OWNER_ID")
echo "container=$C db=$DB user=$U owner_fp=$OWNER_FP"
# 2) the two scripts from the #418 head into /tmp/deid (fetch updates refs only; the working tree is untouched)
rm -rf /tmp/deid && mkdir -p /tmp/deid
git -C /opt/signalbot fetch -q origin pull/418/head
echo "scripts from commit $(git -C /opt/signalbot rev-parse FETCH_HEAD)"
git -C /opt/signalbot archive FETCH_HEAD deploy/signalbot-beta-audit-deidentify.sql \
    deploy/signalbot-beta-audit-deidentify-count.sql | tar -x -C /tmp/deid
PSQL() { docker exec -i "$C" psql -X -U "$U" -v ON_ERROR_STOP=1 "$@"; }
# 3) the read-only count on production
PSQL -d "$DB" -v owner_fp="$OWNER_FP" < /tmp/deid/deploy/signalbot-beta-audit-deidentify-count.sql
# 4) scratch copy: the trigger function, the audit table with its rows, and only the ids the redaction compares
trap 'docker exec "$C" dropdb -U "$U" --if-exists deid_scratch' EXIT
docker exec "$C" dropdb -U "$U" --if-exists deid_scratch
docker exec "$C" createdb -U "$U" deid_scratch
PSQL -d "$DB" -At -c "SELECT pg_get_functiondef('beta_v0_reject_mutation'::regproc) || ';'" | PSQL -q -d deid_scratch
docker exec "$C" pg_dump -U "$U" -d "$DB" -t beta_admin_audit --no-owner --no-privileges | PSQL -q -d deid_scratch
PSQL -q -d deid_scratch -c "CREATE TABLE beta_users (telegram_user_id BIGINT);
                            CREATE TABLE beta_allowlist (telegram_user_id BIGINT);
                            CREATE TABLE beta_waitlist (telegram_user_id BIGINT);"
for t in beta_users beta_allowlist beta_waitlist; do
  PSQL -d "$DB" -c "\copy (SELECT telegram_user_id FROM $t) TO STDOUT" | PSQL -q -d deid_scratch -c "\copy $t FROM STDIN"
done
# 5) the redaction on the scratch copy (default switches: coarsen=on, other_actions=on); before / after
PSQL -d deid_scratch < /tmp/deid/deploy/signalbot-beta-audit-deidentify.sql
PSQL -d deid_scratch -v owner_fp="$OWNER_FP" < /tmp/deid/deploy/signalbot-beta-audit-deidentify-count.sql
# 6) the scratch database is dropped on exit (trap)
```

**Block B — later, only after the owner's go.** It writes production. It needs Block A's `/tmp/deid`. Set `-v coarsen=` and `-v other_actions=` to the owner's answers; both stay `on` until he answers.

```bash
# ---- Block B: later, only after the owner's go. Writes beta_admin_audit on production.
set -euo pipefail
cd /opt/signalbot
eval "$( (set -a; . /opt/signalbot/.env; set +a
          printf 'C=%q\nDB=%q\nU=%q\nOWNER_ID=%q\n' "${BTCBOT_PG_CONTAINER:-btcbot_timescaledb}" \
                 "${POSTGRES_DB:-btcbot}" "${POSTGRES_USER:-btcbot}" "${BETA_OWNER_TELEGRAM_USER_ID:-}") )"
[ -n "$OWNER_ID" ] || { echo "BETA_OWNER_TELEGRAM_USER_ID is empty in /opt/signalbot/.env"; exit 1; }
OWNER_FP=$(python3 -c 'import hashlib,sys; print("u_" + hashlib.sha256(("signalbot-beta-v0:%d" % int(sys.argv[1])).encode()).hexdigest()[:12])' "$OWNER_ID")
[ -f /tmp/deid/deploy/signalbot-beta-audit-deidentify.sql ] || { echo "run block A first (it fetches the scripts)"; exit 1; }
PSQL() { docker exec -i "$C" psql -X -U "$U" -v ON_ERROR_STOP=1 "$@"; }
# 1) a fresh backup first (the same unit the timer runs: local dump, then off-site if configured)
sudo systemctl start signalbot-backup.service
systemctl --no-pager --lines=5 status signalbot-backup.service || true
# 2) the redaction on production; the switches follow the owner's answers (both on unless he says otherwise)
PSQL -d "$DB" -v coarsen=on -v other_actions=on < /tmp/deid/deploy/signalbot-beta-audit-deidentify.sql
# 3) the count again: rows_to_redact and other_rows_to_redact must be 0
PSQL -d "$DB" -v owner_fp="$OWNER_FP" < /tmp/deid/deploy/signalbot-beta-audit-deidentify-count.sql
```

## 5. When the old traces leave the backups

Let R be the redaction day. Backups run daily (`signalbot-backup.timer`). Every dump taken before R still holds the old rows.

| Copy | Retention | Last pre-R dump gone |
|---|---|---|
| Local `deploy/backup.sh` | 7 newest dumps (`BACKUP_RETENTION=7`) | about R + 7 days |
| Off-site daily (if configured) | 30 newest | about R + 30 days |
| Off-site weekly (first dump of each ISO week) | 12 newest | about R + 12 weeks: the week containing R keeps its pre-R representative unless R is that week's first backup |
| Off-site monthly (first dump of each month) | 12 newest | up to R + 12 months: the month containing R keeps its pre-R representative |

- **Off-site.** The 2026-10-08 VPS check skipped it. If off-site is not configured, only the local row applies.
- **Restores.** Restoring any pre-R dump (`deploy/restore.sh`) brings the old rows back. After such a restore, run the redaction again; it is idempotent.
