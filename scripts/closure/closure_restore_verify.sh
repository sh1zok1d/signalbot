#!/usr/bin/env bash
# closure_restore_verify.sh — prove the ENCRYPTED closure backup restores completely, on a clean machine.
#
# Part of docs/closure/BACKUP_AND_RESTORE_PLAN_V1.md §5. Usage:
#   CLOSURE_PASSPHRASE_FILE=~/closure.pass ./closure_restore_verify.sh /path/to/closure_backup_<stamp>
# Modes (CLOSURE_VERIFY_MODE): `docker` (default: a throwaway TimescaleDB container, the image of docker-compose.yml) or
# `local` (an existing PostgreSQL reached through PGHOST/PGPORT/PGUSER; a throwaway database is created and dropped;
# used by scripts/closure/test_backup_restore.sh).
#
# Strictness (owner audit 2026-10-15): the restore runs psql with ON_ERROR_STOP=1 inside ONE transaction
# (--single-transaction), so the first SQL error aborts and rolls back everything; the exit status of every pipeline stage
# (gpg, gunzip, psql) is checked; a dump without PostgreSQL's completion marker is rejected before anything is restored;
# every table created by the dump must exist afterwards and every row count in COUNTS.txt must match. Any deviation is a
# FAIL with a non-zero exit, the throwaway database/container is destroyed and the decrypted plaintext (kept only in a private
# mode-700 work dir, by default under /dev/shm) is removed, on success and on failure alike.
# TimescaleDB: when the target has the extension, timescaledb_pre_restore()/post_restore() wrap the load; pg_dump output of a
# TimescaleDB database restores only into a server with the same extension major version (use the image above); a version
# mismatch therefore fails, as it should.
set -euo pipefail
umask 077
SRC="${1:?backup directory}"
PASSFILE="${CLOSURE_PASSPHRASE_FILE:?set CLOSURE_PASSPHRASE_FILE}"
MODE="${CLOSURE_VERIFY_MODE:-docker}"
IMAGE="${TIMESCALE_IMAGE:-timescale/timescaledb:2.17.2-pg16}"
REPO="${SIGNALBOT_REPO:-}"                       # optional checkout, for storage/beta_v0_schema.sql re-apply
WORK_BASE="${CLOSURE_VERIFY_WORK_BASE:-}"        # default: /dev/shm when it is tmpfs, else $TMPDIR with a warning
TS="$(date -u +%H%M%S)_$$"
NAME="closure_restore_$TS"
DB="verify_$TS"
PGUSER="${PGUSER:-postgres}"
GPG=(gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$PASSFILE")
log() { printf '[restore-verify %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
q()  { if [ "$MODE" = docker ]; then docker exec "$NAME" psql -U postgres "$@"; else psql -U "$PGUSER" "$@"; fi; }
qi() { if [ "$MODE" = docker ]; then docker exec -i "$NAME" psql -U postgres "$@"; else psql -U "$PGUSER" "$@"; fi; }
WORK=""; DBCREATED=0; VERIFIED=0
cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  if [ "$MODE" = docker ]; then docker rm -f "$NAME" >/dev/null 2>&1 || true
  elif [ "$DBCREATED" = 1 ]; then psql -U "$PGUSER" -d postgres -q -c "DROP DATABASE IF EXISTS $DB" >/dev/null 2>&1 || true; fi
  if [ -n "$WORK" ] && [ -d "$WORK" ]; then rm -rf "$WORK"; fi
  if [ "$VERIFIED" != 1 ]; then echo "RESTORE NOT VERIFIED (exit $rc): throwaway database and plaintext removed" >&2; [ "$rc" = 0 ] && rc=1; fi
  exit "$rc"
}
on_signal() { echo "FAIL: interrupted" >&2; exit 130; }
trap cleanup EXIT
trap on_signal INT TERM

for t in gpg sha256sum gzip; do have "$t" || fail "missing tool: $t"; done
case "$MODE" in docker) have docker || fail "missing tool: docker" ;; local) have psql || fail "missing tool: psql" ;; *) fail "CLOSURE_VERIFY_MODE must be docker or local" ;; esac
[ -r "$PASSFILE" ] || fail "cannot read passphrase file"
[ -f "$SRC/MANIFEST.sha256" ] || fail "no MANIFEST.sha256 in $SRC"
[ -f "$SRC/COUNTS.txt" ] || fail "no COUNTS.txt in $SRC"
[ -f "$SRC/db_plain.sql.gz.gpg" ] || fail "no db_plain.sql.gz.gpg in $SRC"
[ ! -e "$SRC/INCOMPLETE" ] || fail "$SRC is marked INCOMPLETE by the backup run"
if [ -z "$WORK_BASE" ]; then
  if [ "$(df -PT /dev/shm 2>/dev/null | awk 'NR==2{print $2}')" = tmpfs ]; then WORK_BASE=/dev/shm; else WORK_BASE="${TMPDIR:-/tmp}"; log "WARNING: /dev/shm is not tmpfs; the decrypted dump will be written under $WORK_BASE (disk)"; fi
fi
WORK="$(mktemp -d "$WORK_BASE/closure_verify.XXXXXX")"; chmod 700 "$WORK"

log "1. manifest"
( cd "$SRC" && sha256sum -c --quiet MANIFEST.sha256 ) || fail "manifest check failed"

log "2. decrypt dump into $WORK (RAM when tmpfs)"
"${GPG[@]}" --decrypt "$SRC/db_plain.sql.gz.gpg" > "$WORK/db_plain.sql.gz" || fail "decryption failed (wrong passphrase or damaged ciphertext)"
gzip -t "$WORK/db_plain.sql.gz" || fail "decrypted dump is not a valid gzip"
gunzip -c "$WORK/db_plain.sql.gz" | tail -c 200 | grep -c "PostgreSQL database dump complete" > /dev/null || fail "dump is truncated: no completion marker"
mapfile -t DUMP_TABLES < <(gunzip -c "$WORK/db_plain.sql.gz" | sed -n -E 's/^CREATE TABLE (IF NOT EXISTS )?(public\.)?([A-Za-z0-9_]+) \(.*/\3/p' | sort -u)
[ "${#DUMP_TABLES[@]}" -gt 0 ] || fail "dump declares no tables"

log "3. throwaway database ($MODE)"
if [ "$MODE" = docker ]; then
  docker run -d --name "$NAME" -e POSTGRES_PASSWORD=verify -e POSTGRES_USER=postgres -e POSTGRES_DB=postgres "$IMAGE" >/dev/null
  for i in $(seq 1 60); do docker exec "$NAME" pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; [ "$i" = 60 ] && fail "database did not start"; done
else
  pg_isready -U "$PGUSER" >/dev/null || fail "local PostgreSQL not reachable (PGHOST/PGPORT)"
fi
q -d postgres -v ON_ERROR_STOP=1 -q -c "CREATE DATABASE $DB;" || fail "cannot create the throwaway database"
DBCREATED=1
TIMESCALE=0
if q -d "$DB" -v ON_ERROR_STOP=1 -q -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" >/dev/null 2>&1; then
  TIMESCALE=1; q -d "$DB" -v ON_ERROR_STOP=1 -q -c "SELECT timescaledb_pre_restore();" >/dev/null || fail "timescaledb_pre_restore failed"
else
  log "timescaledb extension not available here: restoring without pre/post_restore (fine for a non-hypertable dump)"
fi

log "4. restore: ON_ERROR_STOP=1, single transaction; any error aborts and rolls back"
set +e
gunzip -c "$WORK/db_plain.sql.gz" | qi -d "$DB" -q -v ON_ERROR_STOP=1 --single-transaction > "$WORK/restore.log" 2>&1
st=("${PIPESTATUS[@]}")
set -e
if [ "${st[0]}" != 0 ] || [ "${st[1]}" != 0 ]; then
  echo "  gunzip exit ${st[0]}, psql exit ${st[1]}; first error line (data values may follow it in the log, which is destroyed):" >&2
  grep -m1 -E '^(psql:|ERROR|FATAL)' "$WORK/restore.log" | cut -c1-200 >&2 || true
  fail "restore aborted"
fi
if grep -qE '^(ERROR|FATAL)' "$WORK/restore.log"; then fail "restore log contains errors despite exit 0"; fi
[ "$TIMESCALE" = 1 ] && { q -d "$DB" -v ON_ERROR_STOP=1 -q -c "SELECT timescaledb_post_restore();" >/dev/null || fail "timescaledb_post_restore failed"; }

log "5. every table declared by the dump exists"
missing=0
for t in "${DUMP_TABLES[@]}"; do
  if [ "$(q -d "$DB" -At -c "SELECT to_regclass('public.$t') IS NOT NULL")" != "t" ]; then echo "  MISSING table $t"; missing=$((missing+1)); fi
done
[ "$missing" = 0 ] || fail "$missing table(s) declared by the dump are missing after restore"
log "  ${#DUMP_TABLES[@]} tables present"

log "6. row counts vs COUNTS.txt"
mismatch=0; checked=0
while read -r t n; do
  case "$t" in klines_1m_min_max|"") continue ;; esac
  [ "$n" = "ABSENT" ] && continue
  got=$(q -d "$DB" -At -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM public.$t" 2>/dev/null || echo ERR)
  checked=$((checked+1))
  if [ "$got" != "$n" ]; then echo "  MISMATCH $t: backup $n, restored $got"; mismatch=$((mismatch+1)); else echo "  ok $t = $n"; fi
done < "$SRC/COUNTS.txt"
[ "$checked" -gt 0 ] || fail "no table was checked"
[ "$mismatch" = 0 ] || fail "$mismatch table(s) differ"
if grep -q '^klines_1m_min_max ' "$SRC/COUNTS.txt"; then
  want="$(sed -n 's/^klines_1m_min_max //p' "$SRC/COUNTS.txt")"
  got="$(q -d "$DB" -At -c "SELECT coalesce(min(open_time)::text,'') || ' ' || coalesce(max(open_time)::text,'') FROM klines_1m" 2>/dev/null || echo ERR)"
  [ "$want" = "$got" ] || fail "klines_1m min/max differ"
fi

if [ -n "$REPO" ] && [ -f "$REPO/storage/beta_v0_schema.sql" ]; then
  log "7. re-apply beta schema (idempotent)"
  qi -d "$DB" -v ON_ERROR_STOP=1 -q --single-transaction < "$REPO/storage/beta_v0_schema.sql" >/dev/null 2>&1 || fail "beta schema re-apply failed"
fi
VERIFIED=1
log "RESTORE VERIFIED from the encrypted copy: ${#DUMP_TABLES[@]} tables present, $checked row counts matched. Record this in docs/closure/BACKUP_MANIFEST_<date>.md (counts only). Cleanup follows."
