#!/usr/bin/env bash
# closure_restore_verify.sh — prove the ENCRYPTED closure backup restores, on a clean machine (owner's laptop with Docker).
#
# Part of docs/closure/BACKUP_AND_RESTORE_PLAN_V1.md §3. Usage:
#   CLOSURE_PASSPHRASE_FILE=~/closure.pass ./closure_restore_verify.sh /path/to/closure_backup_<stamp>
# Steps: verify MANIFEST.sha256 -> decrypt db_plain.sql.gz.gpg into a private temp dir -> start a throwaway TimescaleDB
# container (same image as docker-compose.yml) -> restore with timescaledb_pre/post_restore -> compare row counts with
# COUNTS.txt -> re-apply the beta schema if the repository is available -> destroy the container and the plaintext.
# The decrypted dump exists only inside WORK (default: a fresh mode-700 dir under $TMPDIR, prefer tmpfs or an encrypted disk).
set -euo pipefail
umask 077
SRC="${1:?backup directory}"
PASSFILE="${CLOSURE_PASSPHRASE_FILE:?set CLOSURE_PASSPHRASE_FILE}"
IMAGE="${TIMESCALE_IMAGE:-timescale/timescaledb:2.17.2-pg16}"
REPO="${SIGNALBOT_REPO:-}"                       # optional checkout, for storage/beta_v0_schema.sql re-apply
WORK="${CLOSURE_VERIFY_WORK:-$(mktemp -d "${TMPDIR:-/tmp}/closure_verify.XXXXXX")}"
NAME="closure_restore_$(date -u +%H%M%S)"
GPG=(gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$PASSFILE")
log() { printf '[restore-verify %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }
cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  if command -v shred >/dev/null 2>&1; then find "$WORK" -type f -exec shred -u {} + 2>/dev/null || true; fi
  rm -rf "$WORK"
}
trap cleanup EXIT
for t in docker gpg sha256sum gzip; do command -v "$t" >/dev/null || fail "missing tool: $t"; done
[ -r "$PASSFILE" ] || fail "cannot read passphrase file"
[ -f "$SRC/MANIFEST.sha256" ] || fail "no MANIFEST.sha256 in $SRC"
chmod 700 "$WORK"

log "1. manifest"
( cd "$SRC" && sha256sum -c --quiet MANIFEST.sha256 ) || fail "manifest check failed"

log "2. decrypt dump into $WORK"
"${GPG[@]}" --decrypt "$SRC/db_plain.sql.gz.gpg" > "$WORK/db_plain.sql.gz"
gzip -t "$WORK/db_plain.sql.gz" || fail "decrypted dump is not a valid gzip"

log "3. throwaway database ($IMAGE)"
docker run -d --name "$NAME" -e POSTGRES_PASSWORD=verify -e POSTGRES_USER=postgres -e POSTGRES_DB=postgres "$IMAGE" >/dev/null
for i in $(seq 1 60); do docker exec "$NAME" pg_isready -U postgres >/dev/null 2>&1 && break; sleep 1; [ "$i" = 60 ] && fail "database did not start"; done
docker exec "$NAME" psql -U postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE verify;" >/dev/null
docker exec "$NAME" psql -U postgres -d verify -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS timescaledb; SELECT timescaledb_pre_restore();" >/dev/null

log "4. restore (errors from missing roles are tolerated: the dump is --no-owner --no-privileges)"
gunzip -c "$WORK/db_plain.sql.gz" | docker exec -i "$NAME" psql -U postgres -d verify -q -v ON_ERROR_STOP=0 > "$WORK/restore.log" 2>&1 || true
docker exec "$NAME" psql -U postgres -d verify -v ON_ERROR_STOP=1 -c "SELECT timescaledb_post_restore();" >/dev/null
errs=$(grep -c '^ERROR' "$WORK/restore.log" || true); log "restore log: $errs ERROR lines (expected 0; review $WORK/restore.log before cleanup if not 0)"

log "5. row counts vs COUNTS.txt"
mismatch=0
while read -r t n; do
  case "$t" in klines_1m_min_max|"") continue ;; esac
  if [ "$n" = "ABSENT" ]; then continue; fi
  got=$(docker exec "$NAME" psql -U postgres -d verify -At -c "SELECT count(*) FROM public.$t" 2>/dev/null || echo ERR)
  if [ "$got" != "$n" ]; then echo "  MISMATCH $t: backup $n, restored $got"; mismatch=$((mismatch+1)); else echo "  ok $t = $n"; fi
done < "$SRC/COUNTS.txt"
[ "$mismatch" = 0 ] || fail "$mismatch table(s) differ"

if [ -n "$REPO" ] && [ -f "$REPO/storage/beta_v0_schema.sql" ]; then
  log "6. re-apply beta schema (idempotent)"
  docker exec -i "$NAME" psql -U postgres -d verify -v ON_ERROR_STOP=1 -q < "$REPO/storage/beta_v0_schema.sql" >/dev/null || fail "beta schema re-apply failed"
fi
log "7. spot checks"
docker exec "$NAME" psql -U postgres -d verify -At -c "SELECT 'klines_1m', min(open_time), max(open_time) FROM klines_1m" || true
docker exec "$NAME" psql -U postgres -d verify -At -c "SELECT 'beta_claims', count(*) FROM beta_claims" || true
log "RESTORE VERIFIED from the encrypted copy. Record the output above in docs/closure/BACKUP_MANIFEST_<date>.md (counts only). Cleanup follows."
