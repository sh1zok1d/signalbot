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

**Options for the owner (the prepared script does neither by default):**
- **(a)** Accept these as the permitted de-identified aggregate. They are needed to keep a deleted enrolled participant in the denominator.
- **(b)** Additionally coarsen `recorded_at` of these rows to the Kyiv date (one extra `SET` in the same transaction). This keeps the date of deletion and drops the time.

**Outside this redaction, other personal traces remain:**
- `admin_known`, `admin_reply` and `admin_add` audit rows keep the `target_fingerprint` of a participant who later deleted themselves. That fingerprint is recomputable from a Telegram id.
- Telling which fingerprints belong to deleted people needs the live users' fingerprints, computed with `beta.admin.fingerprint`.
- This is **not** in the prepared script. It needs the owner's decision (OUT-8b).

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

## 3. The redaction and how it gets past append-only

`deploy/signalbot-beta-audit-deidentify.sql`, in one transaction:
1. `LOCK TABLE beta_admin_audit IN ACCESS EXCLUSIVE MODE`.
2. Print the before counts.
3. `ALTER TABLE … DISABLE TRIGGER trg_beta_audit_append_only`.
4. `UPDATE` the three deletion actions only:
   - set `target_fingerprint = NULL`;
   - set `detail = {"cohort": …}` with `joined_after_test_open = false`. Every pre-#418 deletion predates any `/admin_test_open`, so false is the true value.
5. `ENABLE TRIGGER`.
6. Print the after counts and the trigger state (`O` = enabled).
7. `COMMIT`.

**Why disabling the trigger this way is safe:**
- Only the named append-only trigger is disabled, never `session_replication_role`, which would switch off every trigger and foreign key.
- `ALTER TABLE` holds an ACCESS EXCLUSIVE lock to the end of the transaction, so no other session can read or write the table while the trigger is off.
- `ON_ERROR_STOP` plus the single transaction mean any error rolls everything back, the `DISABLE` included. The trigger is never left off.
- It needs the table owner: the role the schema was applied with, not the bot's runtime role.
- It is idempotent: a second run updates 0 rows.

**Tested locally.** `tests/beta/test_beta_audit_deidentify_pg.py` runs both files with `psql` on PostgreSQL 16, on the real schema with representative pre-#418 rows:
- `user_delete_me` with counts;
- `retention_purge` with a fingerprint;
- `admin_remove` of the owner's own account and of an invited non-joiner;
- an unrelated `admin_stats` row.

It checks:
- the count changes nothing;
- only the three actions change, with `recorded_at` and the actor unchanged;
- the cohort fields are exactly the three;
- the table is append-only again afterwards;
- a second run is a no-op.

## 4. Owner command block (VPS; scratch copy first)

```bash
# 0) read-only count on production (§2)
psql "$DSN" -X -v owner_fp="$OWNER_FP" -f deploy/signalbot-beta-audit-deidentify-count.sql

# 1) scratch copy: the function, the table and its rows, nothing else
createdb -h <host> -U <owner role> audit_scratch
psql "$DSN" -X -At -c "SELECT pg_get_functiondef('beta_v0_reject_mutation'::regproc) || ';'" \
  | psql -h <host> -U <owner role> -d audit_scratch -X -v ON_ERROR_STOP=1
pg_dump "$DSN" -t beta_admin_audit --no-owner --no-privileges \
  | psql -h <host> -U <owner role> -d audit_scratch -X -v ON_ERROR_STOP=1

# 2) redaction on the scratch copy; read the before / after tables it prints
psql -h <host> -U <owner role> -d audit_scratch -X -f deploy/signalbot-beta-audit-deidentify.sql
psql -h <host> -U <owner role> -d audit_scratch -X -v owner_fp="$OWNER_FP" \
  -f deploy/signalbot-beta-audit-deidentify-count.sql          # rows_to_redact must now be 0

# 3) only after the owner's go: production, as the table owner, right after a fresh backup
deploy/backup.sh
psql "$DSN" -X -f deploy/signalbot-beta-audit-deidentify.sql
dropdb -h <host> -U <owner role> audit_scratch
```

(Inside the docker setup, prefix the commands with `docker exec -i <container>` as `deploy/backup.sh` does.)

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
