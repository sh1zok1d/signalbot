#!/usr/bin/env bash
# closure_restore_verify.sh — prove the ENCRYPTED closure backup restores, on a clean machine.
#
# Part of docs/closure/BACKUP_AND_RESTORE_PLAN_V1.md §5. Usage:
#   CLOSURE_PASSPHRASE_FILE=~/closure.pass ./closure_restore_verify.sh /path/to/closure_backup_<stamp>
# Modes (CLOSURE_VERIFY_MODE): `docker` (default: a throwaway TimescaleDB container, the image of docker-compose.yml) or
# `local` (an existing PostgreSQL reached through PGHOST/PGPORT/PGUSER; a throwaway database is created and dropped;
# used by scripts/closure/test_backup_restore.sh).
# Steps: verify MANIFEST.sha256 -> decrypt db_plain.sql.gz.gpg into a private work dir -> throwaway database ->
# restore (timescaledb_pre/post_restore when the extension exists) -> compare row counts with COUNTS.txt -> re-apply the
# beta schema if the repository is given -> destroy the database/container and the plaintext.
# The decrypted dump exists only inside WORK (default: a fresh mode-700 dir under $TMPDIR; prefer tmpfs or an encrypted disk).
set -euo pipefail
umask 077
SRC="${1:?backup directory}"
PASSFILE="${CLOSURE_PASSPHRASE_FILE:?set CLOSURE_PASSPHRASE_FILE}"
MODE="${CLOSURE_VERIFY_MODE:-docker}"
IMAGE="${TIMESCALE_IMAGE:-timescale/timescaledb:2.17.2-pg16}"
REPO="${SIGNALBOT_REPO:-}"                       # optional checkout, for storage/beta_v0_schema.sql re-apply
WORK="${CLOSURE_VERIFY_WORK:-$(mktemp -d "${TMPDIR:-/tmp}/closure_verify.XXXXXX")}"
TS="$(date -u +%H%M%S)"
NAME="closure_restore_$TS"
DB="verify_$TS"
PGUSER="${PGUSER:-postgres}"
GPG=(gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$PASSFILE")
log() { printf '[restore-verify %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
# psql against the throwaway server; q = no stdin, qi = stdin
q()  { if [ "$MODE" = docker ]; then docker exec "$NAME" psql -U postgres "$@"; else psql -U "$PGUSER" "$@"; fi; }
qi() { if [ "$MODE" = docker ]; then docker exec -i "$NAME" psql -U postgres "$@"; else psql -U "$PGUSER" "$@"; fi; }
cleanup() {
  if [ "$MODE" = docker ]; then docker rm -f "$NAME" >/dev/null 2>&1 || true
  else psql -U "$PGUSER" -d postgres -q -c "DROP DATABASE IF EXISTS $DB" >/dev/null 2>&1 || true; fi
  if have shred; then find "$WORK" -type f -exec shred -u {} + 2>/dev/null || true; fi
  rm -rf "$WORK"
}
trap cleanup EXIT
for t in gpg sha256sum gzip; do have "$t" || fail "missing tool: $t"; done
case "$MODE" in docker) have docker || fail "missing tool: docker" ;; local) have psql || fail "missing tool: psql" ;; *) fail "CLOSURE_VERIFY_MODE must be docker or local" ;; esac
[ -r "$PASSFILE" ] || fail "cannot read passphrase file"
[ -f "$SRC/MANIFEST.sha256" ] || fail "no MANIFEST.sha256 in $SRC"
[ -f "$SRC/COUNTS.txt" ] || fail "no COUNTS.txt in $SRC"
install -d -m 700 "$WORK"

log "1. manifest"
( cd "$SRC" && sha256sum -c --quiet MANIFEST.sha256 ) || fail "manifest check failed"

log "2. decrypt dump into $WORK"
"${GPG[@]}" --decrypt "$SRC/db_plain.sql.gz.gpg" > "$WORK/db_plain.sql.gz"
gzip -t "$WORK/db_plain.sql.gz" || fail "decrypted dump is not a valid gzip"

log "3. throwaway database ($MODE)"
if [ "$MODE" = docker ]; then
  docker run -d --name "$NAME" -e POSTGRES_PASSWORD=verify -e POSTGRES_USER=postgres -e POSTGRES_DB=postgres "$IMAGE" >/dev/null
  for i in $(seq 1 60); do docker exec "$NAME" pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; [ "$i" = 60 ] && fail "database did not start"; done
else
  pg_isready -U "$PGUSER" >/dev/null || fail "local PostgreSQL not reachable (PGHOST/PGPORT)"
fi
q -d postgres -v ON_ERROR_STOP=1 -q -c "CREATE DATABASE $DB;"
TIMESCALE=0
if q -d "$DB" -v ON_ERROR_STOP=1 -q -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" >/dev/null 2>&1; then
  TIMESCALE=1; q -d "$DB" -v ON_ERROR_STOP=1 -q -c "SELECT timescaledb_pre_restore();" >/dev/null
else
  log "timescaledb extension not available here: restoring without pre/post_restore (fine for a non-hypertable dump)"
fi

log "4. restore (role/privilege errors are tolerated: the dump is --no-owner --no-privileges)"
gunzip -c "$WORK/db_plain.sql.gz" | qi -d "$DB" -q -v ON_ERROR_STOP=0 > "$WORK/restore.log" 2>&1 || true
[ "$TIMESCALE" = 1 ] && q -d "$DB" -v ON_ERROR_STOP=1 -q -c "SELECT timescaledb_post_restore();" >/dev/null
errs=$(grep -c '^ERROR' "$WORK/restore.log" || true); log "restore log: $errs ERROR lines (expected 0)"
[ "$errs" = 0 ] || { grep '^ERROR' "$WORK/restore.log" | head -20; fail "restore reported errors"; }

log "5. row counts vs COUNTS.txt"
mismatch=0; checked=0
while read -r t n; do
  case "$t" in klines_1m_min_max|"") continue ;; esac
  [ "$n" = "ABSENT" ] && continue
  got=$(q -d "$DB" -At -c "SELECT count(*) FROM public.$t" 2>/dev/null || echo ERR)
  checked=$((checked+1))
  if [ "$got" != "$n" ]; then echo "  MISMATCH $t: backup $n, restored $got"; mismatch=$((mismatch+1)); else echo "  ok $t = $n"; fi
done < "$SRC/COUNTS.txt"
[ "$checked" -gt 0 ] || fail "no table was checked"
[ "$mismatch" = 0 ] || fail "$mismatch table(s) differ"

if [ -n "$REPO" ] && [ -f "$REPO/storage/beta_v0_schema.sql" ]; then
  log "6. re-apply beta schema (idempotent)"
  qi -d "$DB" -v ON_ERROR_STOP=1 -q < "$REPO/storage/beta_v0_schema.sql" >/dev/null || fail "beta schema re-apply failed"
fi
log "7. spot checks"
q -d "$DB" -At -c "SELECT 'klines_1m', min(open_time), max(open_time) FROM klines_1m" 2>/dev/null || log "klines_1m absent in this dump"
q -d "$DB" -At -c "SELECT 'beta_claims', count(*) FROM beta_claims" 2>/dev/null || true
log "RESTORE VERIFIED from the encrypted copy ($checked tables compared). Record the output above in docs/closure/BACKUP_MANIFEST_<date>.md (counts only). Cleanup follows."
