# Beta audit de-identification (OUT-8 v4) — prepared, not run

**Status:** `PREPARED / NOT_RUN / OWNER_GO_REQUIRED` (v2, 2026-10-08; block A hardened in v3: unique scratch name, marker-checked drop, read-only production sessions; v4: the actor side, each block in its own shell). Nothing here has been run on production; the owner runs block B after a go.

**v2 supersedes v1** (#418's draft) and follows the owner's OUT-8 decisions of 2026-10-08:
- Keep only what the measurements need; a counter replaces any per-row record (#420).
- Pseudonyms are keyed (#423).
- Every audit row about a participant who was deleted is de-identified: target, nested detail, any free text, and the exact time.

## 1. What remains, per row type

| Row | Before | After the redaction |
|---|---|---|
| Deletion (`user_delete_me`, `retention_purge`, `admin_remove`) | `admin_remove` / `retention_purge` held the person's fingerprint; all three held per-person row counts and a cohort record (`joined_kyiv_date`, `known_contact`, since #418 `joined_after_test_open`); the exact time | The #420 minimal form: action, `result`, the kind of actor (`participant` / `system` / `owner`), the Kyiv date. `target_fingerprint` NULL, `detail` `{}`. A row that was unknown **and** joined after the test opening adds one to `beta_deleted_cohort_counts` for its join date. **Rows written before any `/admin_test_open` never qualify**, so before the test none move. |
| About a deleted person (`admin_known`, `admin_reply`, `admin_add`, `admin_waitlist_admit`, any other action with a target) | Their fingerprint, nested detail (`known_contact`, `result`), the exact time | Action, actor, `result`, the Kyiv date. `target_fingerprint` NULL, `detail` `{}`. **The fact that the action happened stays.** |
| A deleted person as the **actor** (any row but a deletion, whatever the target: none, themselves, someone else) | Their fingerprint as `actor_fingerprint` | `actor_fingerprint` = `participant`. A row they only acted in keeps everything else; when target = actor = them, both go (the row above). Counted separately (`actor_deleted`). |
| About someone still present, a live person's or the owner's own row, rows without a target by a live actor | — | Untouched |

- **Free text.** The audit holds none to strip: `/admin_reply` stores the fingerprint, not the reply body (`docs/PRIVATE_BETA_V0_DEPLOY.md`), and `/admin_broadcast` stores only the length. Participants' own texts live in `beta_feedback_messages`, which `/delete_me` already removes.
- **Residual risk, stated.** In a small cohort, a deleted person's rows still show *that* an action happened on a given Kyiv date (for example «an `admin_known` on 2026-10-02»). The counter shows *that* someone who joined on a date left. Neither names anyone without outside knowledge, such as the owner's own memory or ledger. These are the minimum the measurements need.
- **Not a guarantee.** Removing exact times and fingerprints lowers the risk of matching a row in a small cohort but does not by itself guarantee anonymity.

## 2. How rows about a deleted participant are found
- **The rule.** Every row before #423 holds the old, unkeyed fingerprint `"u_" + sha256("signalbot-beta-v0:" + id)[:12]`.
  - The script computes that fingerprint, in SQL, for every id still present in `beta_users`, `beta_allowlist` and `beta_waitlist`.
  - A row whose target is none of these, and is not a live person's or the owner's own, is a row about someone who was deleted.
  - **The actor side.** An actor that is a person's fingerprint (`u_` + 12 hex), none of these and not the owner's (`-v owner_fp`, required) is a deleted person acting; it becomes `participant`.
- **`/delete_me` rows** have no target and are matched by action, not by person. The deleted person's *other* rows are found by the rule above.
- **What cannot be matched safely is counted, never guessed.** Rows recorded after #423 hold **keyed** fingerprints, which SQL cannot recompute without the key.
  - Pass `-v keyed_since=<the #423 deploy instant>`: those rows are left untouched and reported as `keyed_unmatched`.
  - **The intended order is to run block B after #420 and before #423**; then there are none.
- **A target the owner typed for nobody** (an `/admin_reply` to an unknown fingerprint) also matches the rule. Removing it loses nothing.

## 3. Read-only count
`deploy/signalbot-beta-audit-deidentify-count.sql` runs inside `BEGIN TRANSACTION READ ONLY … ROLLBACK`.
- **Per kind, actor side and action.** The kinds are `deletion`, `deleted_person`, `keyed_unmatched`, `live` and `actor_own` (only a live person's or the owner's own row); `actor_deleted` marks the rows whose actor is a deleted person, and those rows are listed whatever their kind. For each it gives the rows, the rows with a target, the rows whose target is the owner, the rows whose actor is the owner, the rows with detail, and the first and last time.
- **The counter.** It also gives the number of old deletion rows that would move into the counter.
- **No assumption about test accounts.** The owner columns show which rows are the owner's own.

## 4. The redaction, and how it gets past append-only
`deploy/signalbot-beta-audit-deidentify.sql`, in one transaction:
1. Lock `beta_admin_audit` and `beta_deleted_cohort_counts` (ACCESS EXCLUSIVE).
2. Classify the rows (§2) and print the before table.
3. Add the qualifying old deletion rows to the counter.
4. `DISABLE TRIGGER trg_beta_audit_append_only`.
5. Reduce the deletion rows; strip the rows about deleted people.
6. `ENABLE TRIGGER`.
7. Print the after table, the counter and the trigger state (`O` = enabled).
8. `COMMIT`.

**Why it is safe:**
- Only the named append-only trigger is disabled, never `session_replication_role`, which would disable every trigger and foreign key.
- The ACCESS EXCLUSIVE lock holds to the end of the transaction, so no other session touches the table while the trigger is off.
- `ON_ERROR_STOP` plus the single transaction mean any error rolls everything back, the `DISABLE` included.
- It needs the table owner: `POSTGRES_USER` in the docker setup.
- It is idempotent: a second run gives `UPDATE 0` twice and `INSERT 0 0`.

**Tests.** `tests/beta/test_beta_audit_deidentify_pg.py` runs both files with `psql` on PostgreSQL 16 against representative rows from main and #418. It checks:
- the count changes nothing;
- each row type ends as in §1;
- only the post-opening unknown deletion enters the counter;
- live, own and no-target rows are untouched;
- the table is append-only again;
- a second run is a no-op;
- keyed rows are left alone and counted.

## 5. Owner command blocks (VPS, as the user that runs `deploy/backup.sh`)

**What the owner types:** nothing but pasting the block.
- **Each block runs in its own shell.** It is wrapped as `bash -c "$(cat <<'BLOCK_A' … BLOCK_A
)"` (quoted delimiter: nothing is expanded at paste time). `set -euo pipefail` and the exit trap live inside that child shell, so an error ends the block, not the owner's SSH session, and the trap runs when the block ends. The script text is an argument, not stdin, so no `docker exec -i` inside can swallow the rest of it.
- Everything comes from `/opt/signalbot/.env`, read in a subshell, with the defaults of `deploy/backup.sh` and `docker-compose.yml`:
  - container `btcbot_timescaledb`;
  - `POSTGRES_DB` / `POSTGRES_USER` = `btcbot`;
  - `BETA_OWNER_TELEGRAM_USER_ID`.
- The owner's old fingerprint is computed inline in python3, without importing the repo.
- **Fetching the scripts.** `git fetch origin pull/422/head` updates refs only, never the working tree. `git archive` extracts the two scripts into a fresh `mktemp -d /tmp/deid.XXXXXXXX` directory, removed on exit. There is no pull and no checkout in `/opt/signalbot`. The block prints the commit the scripts came from, because GitHub can lag a few seconds after a push.

**Block A — now, read-only on production.**
- **Production is read-only twice.** Every production `psql` / `pg_dump` session runs with `PGOPTIONS='-c default_transaction_read_only=on'` (passed by `docker exec -e`), on top of `BEGIN READ ONLY` in the count file; a write under it fails (`tests/beta/test_beta_audit_deidentify_pg.py`).
- **The only database it writes** is a scratch database inside the same container, named `deid_scratch_<UTC yyyymmddThhmmss>_<8 random hex>`.
  - Never an existing database: if the name exists, the block stops before creating anything and drops nothing.
  - Right after `createdb` it is marked (`COMMENT ON DATABASE … 'signalbot OUT-8 scratch <name>'`).
  - The exit trap drops only the database this run created, and only if its marker still matches.
- It copies only what the matching needs: the trigger function, the audit table, the counter if production has it, and the bare `telegram_user_id`s of users, allowlist and waitlist.

```bash
bash -c "$(cat <<'BLOCK_A'
# ---- Block A: now, read-only on production. Writes only a scratch database created by this run inside the same
# container, under a unique name, and drops only that database.
set -euo pipefail
cd /opt/signalbot
# 1) settings, read from /opt/signalbot/.env in a subshell, defaults as in deploy/backup.sh and docker-compose.yml
eval "$( (set -a; . /opt/signalbot/.env; set +a
          printf 'C=%q\nDB=%q\nU=%q\nOWNER_ID=%q\n' "${BTCBOT_PG_CONTAINER:-btcbot_timescaledb}" \
                 "${POSTGRES_DB:-btcbot}" "${POSTGRES_USER:-btcbot}" "${BETA_OWNER_TELEGRAM_USER_ID:-}") )"
[ -n "$OWNER_ID" ] || { echo "BETA_OWNER_TELEGRAM_USER_ID is empty in /opt/signalbot/.env"; exit 1; }
# the owner's fingerprint as the existing (pre-#423, unkeyed) rows hold it
OWNER_FP=$(python3 -c 'import hashlib,sys; print("u_" + hashlib.sha256(("signalbot-beta-v0:%d" % int(sys.argv[1])).encode()).hexdigest()[:12])' "$OWNER_ID")
echo "container=$C db=$DB user=$U owner_fp(old)=$OWNER_FP"
# 2) the two scripts from the PR head into a fresh /tmp directory (fetch updates refs only; the working tree is untouched)
WORK=$(mktemp -d /tmp/deid.XXXXXXXX)
git -C /opt/signalbot fetch -q origin pull/422/head
echo "scripts from commit $(git -C /opt/signalbot rev-parse FETCH_HEAD)"
git -C /opt/signalbot archive FETCH_HEAD deploy/signalbot-beta-audit-deidentify.sql \
    deploy/signalbot-beta-audit-deidentify-count.sql | tar -x -C "$WORK"
# production: every session read-only (PGOPTIONS), on top of BEGIN READ ONLY in the count file
PROD() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' "$C" psql -X -U "$U" -v ON_ERROR_STOP=1 -d "$DB" "$@"; }
PROD_DUMP() { docker exec -e PGOPTIONS='-c default_transaction_read_only=on' "$C" pg_dump -U "$U" -d "$DB" "$@"; }
# the scratch database: a unique name, refused if it already exists, marked at creation, dropped only by this run
SCRATCH="deid_scratch_$(date -u +%Y%m%dT%H%M%S)_$(python3 -c 'import secrets; print(secrets.token_hex(4))')"
MARK="signalbot OUT-8 scratch $SCRATCH"
SCR() { docker exec -i "$C" psql -X -U "$U" -v ON_ERROR_STOP=1 -d "$SCRATCH" "$@"; }
# 3) the read-only count on production
PROD -v owner_fp="$OWNER_FP" < "$WORK/deploy/signalbot-beta-audit-deidentify-count.sql"
# 4) scratch copy: the trigger function, the audit table, the #420 counter, and only the ids the matching needs
[ -z "$(PROD -At -c "SELECT 1 FROM pg_database WHERE datname = '$SCRATCH'")" ] \
  || { echo "database $SCRATCH already exists; nothing created, nothing dropped"; exit 1; }
CREATED=""
cleanup() {
  if [ -n "$CREATED" ] && [ "$(PROD -At \
        -c "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = '$CREATED'")" = "$MARK" ]; then
    docker exec "$C" dropdb -U "$U" "$CREATED" && echo "dropped $CREATED"
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT
docker exec "$C" createdb -U "$U" "$SCRATCH"
CREATED="$SCRATCH"
SCR -q -c "COMMENT ON DATABASE \"$SCRATCH\" IS '$MARK'"
PROD -At -c "SELECT pg_get_functiondef(oid) || ';' FROM pg_proc WHERE proname IN ('beta_v0_reject_mutation', 'beta_audit_guard')" | SCR -q
PROD_DUMP -t beta_admin_audit --no-owner --no-privileges | SCR -q
SCR -q -c "CREATE TABLE beta_users (telegram_user_id BIGINT);
           CREATE TABLE beta_allowlist (telegram_user_id BIGINT);
           CREATE TABLE beta_waitlist (telegram_user_id BIGINT);
           CREATE TABLE beta_deleted_cohort_counts (joined_kyiv_date DATE PRIMARY KEY, n INTEGER NOT NULL CHECK (n > 0));"
for t in beta_users beta_allowlist beta_waitlist; do
  PROD -c "\copy (SELECT telegram_user_id FROM $t) TO STDOUT" | SCR -q -c "\copy $t FROM STDIN"
done
if [ "$(PROD -At -c "SELECT to_regclass('beta_deleted_cohort_counts') IS NOT NULL")" = "t" ]; then
  PROD -c "\copy beta_deleted_cohort_counts TO STDOUT" | SCR -q -c "\copy beta_deleted_cohort_counts FROM STDIN"
fi
# 5) the redaction on the scratch copy; before / after; then the count on the scratch copy
SCR -v owner_fp="$OWNER_FP" < "$WORK/deploy/signalbot-beta-audit-deidentify.sql"
SCR -v owner_fp="$OWNER_FP" < "$WORK/deploy/signalbot-beta-audit-deidentify-count.sql"
# 6) on exit: only the database this run created (name and marker checked) is dropped
BLOCK_A
)"
```

**Block B — later, only after the owner's go.**
- Run it after #420 is deployed (the counter exists; the block checks) and before #423 switches the fingerprints to keyed.
- It writes production, right after a fresh backup.

```bash
bash -c "$(cat <<'BLOCK_B'
# ---- Block B: later, only after the owner's go, after #420 is deployed and before #423 (keyed fingerprints).
set -euo pipefail
cd /opt/signalbot
eval "$( (set -a; . /opt/signalbot/.env; set +a
          printf 'C=%q\nDB=%q\nU=%q\nOWNER_ID=%q\n' "${BTCBOT_PG_CONTAINER:-btcbot_timescaledb}" \
                 "${POSTGRES_DB:-btcbot}" "${POSTGRES_USER:-btcbot}" "${BETA_OWNER_TELEGRAM_USER_ID:-}") )"
[ -n "$OWNER_ID" ] || { echo "BETA_OWNER_TELEGRAM_USER_ID is empty in /opt/signalbot/.env"; exit 1; }
OWNER_FP=$(python3 -c 'import hashlib,sys; print("u_" + hashlib.sha256(("signalbot-beta-v0:%d" % int(sys.argv[1])).encode()).hexdigest()[:12])' "$OWNER_ID")
WORK=$(mktemp -d /tmp/deid.XXXXXXXX); trap 'rm -rf "$WORK"' EXIT
git -C /opt/signalbot fetch -q origin pull/422/head
echo "scripts from commit $(git -C /opt/signalbot rev-parse FETCH_HEAD)"
git -C /opt/signalbot archive FETCH_HEAD deploy/signalbot-beta-audit-deidentify.sql \
    deploy/signalbot-beta-audit-deidentify-count.sql | tar -x -C "$WORK"
PSQL() { docker exec -i "$C" psql -X -U "$U" -v ON_ERROR_STOP=1 "$@"; }
[ "$(PSQL -d "$DB" -At -c "SELECT to_regclass('beta_deleted_cohort_counts') IS NOT NULL")" = "t" ] \
  || { echo "beta_deleted_cohort_counts is missing: deploy #420 first"; exit 1; }
# 1) a fresh backup first (the same unit the timer runs: local dump, then off-site if configured)
sudo systemctl start signalbot-backup.service
systemctl --no-pager --lines=5 status signalbot-backup.service || true
# 2) the redaction on production
PSQL -d "$DB" -v owner_fp="$OWNER_FP" < "$WORK"/deploy/signalbot-beta-audit-deidentify.sql
# 3) the count again: no deletion row with detail, no deleted_person row with a target
PSQL -d "$DB" -v owner_fp="$OWNER_FP" < "$WORK"/deploy/signalbot-beta-audit-deidentify-count.sql
BLOCK_B
)"
```

## 6. Scratch-copy result (local, 2026-10-08)
See the PR description: blocks A and B were run verbatim against a `postgres:16` container named `btcbot_timescaledb`, with the beta schema of #420 and representative rows.

## 7. When the old traces leave the backups
Let R be the redaction day. Backups run daily (`signalbot-backup.timer`). Every dump taken before R still holds the old rows.

| Copy | Retention | Last pre-R dump gone |
|---|---|---|
| Local `deploy/backup.sh` | 7 newest dumps (`BACKUP_RETENTION=7`) | about R + 7 days |
| Off-site daily (if configured) | 30 newest | about R + 30 days |
| Off-site weekly (first dump of each ISO week) | 12 newest | about R + 12 weeks |
| Off-site monthly (first dump of each month) | 12 newest | up to R + 12 months |

- **Off-site.** The 2026-10-08 VPS check skipped it. If off-site is not configured, only the local row applies.
- **Restores.** Restoring a pre-R dump (`deploy/restore.sh`) brings the old rows back. Run block B again afterwards; it is idempotent.
