#!/usr/bin/env bash
# test_backup_restore.sh — end-to-end test of closure_backup.sh and closure_restore_verify.sh on synthetic data:
#   1. throwaway PostgreSQL with the beta schema + fixture (same as the de-identification test);
#   2. closure_backup.sh in local mode: staging, encryption, manifest; only *.gpg + manifest + counts + README remain;
#   3. "transfer" to a test store and back (filesystem copy standing in for rclone; sha256 verified at each hop);
#   4. closure_restore_verify.sh in local mode from the downloaded copy: decrypt, restore into a throwaway DB, counts;
#   5. tamper test: one flipped byte in a downloaded .gpg -> the manifest check fails and nothing is restored;
#   6. wrong passphrase -> decryption fails, nothing restored;
#   7. de-identify the source (deidentify_closure.sql) and back up again: participant counts 0, result counts unchanged.
# Usage: ./scripts/closure/test_backup_restore.sh [workdir]   (root; PostgreSQL 16 server binaries; gpg)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; REPO="$(cd "$HERE/../.." && pwd)"
. "$HERE/testlib_pg.sh"
WORK="${1:-$(mktemp -d "${TMPDIR:-/tmp}/closure_backup_test.XXXXXX")}"; PORT="${PGTEST_PORT:-54392}"
DB=btcbot_test
log() { printf '[test-backup] %s\n' "$*"; }
fail() { echo "FAIL: $*" >&2; exit 1; }
mkdir -p "$WORK"; chmod 700 "$WORK"
trap 'pg_test_stop "$PORT"' EXIT
umask 077
pg_test_start "$PORT"
psql -X -q -d postgres -c "CREATE DATABASE $DB" >/dev/null
psql -X -q -v ON_ERROR_STOP=1 -d "$DB" -f "$REPO/storage/beta_v0_schema.sql" >/dev/null
psql -X -q -v ON_ERROR_STOP=1 -d "$DB" -f "$HERE/test_fixture_closure.sql" >/dev/null
log "database ready"

# fake install dir with a fake .env (test values only) and a passphrase file
FAKE="$WORK/opt_signalbot"; install -d -m 700 "$FAKE" "$FAKE/artifacts"
printf 'POSTGRES_DB=%s\nPOSTGRES_USER=postgres\nBETA_FINGERPRINT_KEY=testkey-not-real\n' "$DB" > "$FAKE/.env"; chmod 600 "$FAKE/.env"
echo "synthetic artifact" > "$FAKE/artifacts/note.txt"
PASS="$WORK/closure.pass"; printf 'test-passphrase-%s-%s\n' "$RANDOM" "$RANDOM" > "$PASS"; chmod 600 "$PASS"
BAD="$WORK/wrong.pass"; printf 'wrong-passphrase-wrong-passphrase\n' > "$BAD"; chmod 600 "$BAD"
export CLOSURE_PG_MODE=local SIGNALBOT_DIR="$FAKE" CLOSURE_PASSPHRASE_FILE="$PASS" CLOSURE_MIN_DUMP_BYTES=1024

log "2. dry run then apply"
CLOSURE_BACKUP_DIR="$WORK/cb1" "$HERE/closure_backup.sh" > "$WORK/dry.log" 2>&1 || { cat "$WORK/dry.log"; fail "dry run"; }
grep -q "dry run only" "$WORK/dry.log" || fail "dry run message missing"
[ ! -e "$WORK/cb1" ] || fail "dry run created the staging dir"
CLOSURE_BACKUP_DIR="$WORK/cb1" "$HERE/closure_backup.sh" --apply > "$WORK/apply.log" 2>&1 || { cat "$WORK/apply.log"; fail "apply"; }
ls "$WORK/cb1" | sort | tr '\n' ' '; echo
for f in db_plain.sql.gz.gpg db_custom.dump.gpg csv_results.tar.gz.gpg csv_participants.tar.gz.gpg secrets.tar.gz.gpg artifacts.tar.gz.gpg state_snapshot.tar.gz.gpg MANIFEST.sha256 COUNTS.txt README.txt; do
  [ -s "$WORK/cb1/$f" ] || fail "missing artifact $f"
done
[ "$(find "$WORK/cb1" -type f ! -name '*.gpg' ! -name MANIFEST.sha256 ! -name COUNTS.txt ! -name README.txt | wc -l)" = 0 ] || fail "plaintext left in staging"
grep -q "^beta_users 5$" "$WORK/cb1/COUNTS.txt" || fail "COUNTS.txt wrong"
# the ciphertext must not contain fixture strings; the decrypted dump must
grep -q --binary-files=text "friend from the chat" "$WORK/cb1/db_plain.sql.gz.gpg" && fail "plaintext leaked into ciphertext" || true
gpg --batch --quiet --pinentry-mode loopback --passphrase-file "$PASS" --decrypt "$WORK/cb1/db_plain.sql.gz.gpg" | gunzip -c | grep -q "friend from the chat" || fail "decrypted dump lacks fixture content"
( cd "$WORK/cb1" && sha256sum -c --quiet MANIFEST.sha256 ) || fail "manifest at source"
log "staging ok: $(ls "$WORK/cb1" | wc -l) files, all encrypted"

log "3. transfer to the test store and back"
STORE="$WORK/store/closure_test"; DL="$WORK/download/closure_test"
if command -v rclone >/dev/null 2>&1; then
  rclone copy --checksum "$WORK/cb1" "$STORE" && rclone check "$WORK/cb1" "$STORE" && rclone copy --checksum "$STORE" "$DL"
else
  install -d -m 700 "$STORE" "$DL"; cp -p "$WORK/cb1"/* "$STORE/"; cp -p "$STORE"/* "$DL/"
  log "rclone not installed: filesystem copies stand in for the remote (checksums verified below)"
fi
( cd "$STORE" && sha256sum -c --quiet MANIFEST.sha256 ) || fail "manifest in store"
( cd "$DL" && sha256sum -c --quiet MANIFEST.sha256 ) || fail "manifest after download"

log "4. restore verification from the downloaded copy"
CLOSURE_VERIFY_MODE=local SIGNALBOT_REPO="$REPO" CLOSURE_VERIFY_WORK="$WORK/verify_work" "$HERE/closure_restore_verify.sh" "$DL" > "$WORK/verify.log" 2>&1 || { cat "$WORK/verify.log"; fail "restore verify"; }
grep -q "RESTORE VERIFIED" "$WORK/verify.log" || fail "no RESTORE VERIFIED"
grep -q "ok beta_users = 5" "$WORK/verify.log" || fail "restored count check missing"
[ ! -e "$WORK/verify_work" ] || fail "verify work dir not cleaned"
[ "$(psql -X -At -d postgres -c "SELECT count(*) FROM pg_database WHERE datname LIKE 'verify_%'")" = 0 ] || fail "throwaway verify database not dropped"

log "5. tamper test"
TAMP="$WORK/download_tampered"; install -d -m 700 "$TAMP"; cp -p "$DL"/* "$TAMP/"
printf '\x00' | dd of="$TAMP/db_plain.sql.gz.gpg" bs=1 seek=100 conv=notrunc status=none
if CLOSURE_VERIFY_MODE=local "$HERE/closure_restore_verify.sh" "$TAMP" > "$WORK/tamper.log" 2>&1; then fail "tampered copy was accepted"; fi
grep -q "manifest check failed" "$WORK/tamper.log" || { cat "$WORK/tamper.log"; fail "tamper not caught by the manifest"; }

log "6. wrong passphrase"
if CLOSURE_VERIFY_MODE=local CLOSURE_PASSPHRASE_FILE="$BAD" "$HERE/closure_restore_verify.sh" "$DL" > "$WORK/badpass.log" 2>&1; then fail "wrong passphrase was accepted"; fi
[ "$(psql -X -At -d postgres -c "SELECT count(*) FROM pg_database WHERE datname LIKE 'verify_%'")" = 0 ] || fail "verify database left after failed decryption"

log "7. de-identify, then the de-identified export"
psql -X -q -v ON_ERROR_STOP=1 -d "$DB" -v owner_fps=u_0123456789ab -v owner_id=1001 -v apply=1 -f "$HERE/deidentify_closure.sql" > "$WORK/deid.log" 2>&1 || { cat "$WORK/deid.log"; fail "deidentify"; }
CLOSURE_BACKUP_DIR="$WORK/cb2" "$HERE/closure_backup.sh" --apply > "$WORK/apply2.log" 2>&1 || { cat "$WORK/apply2.log"; fail "second apply"; }
for t in beta_users beta_allowlist beta_waitlist beta_feedback_messages beta_user_activity; do grep -q "^$t 0$" "$WORK/cb2/COUNTS.txt" || fail "$t not 0 in de-identified export"; done
for t in beta_claims beta_claim_outcomes beta_forecasts beta_hist_stats beta_episodes beta_push_decisions beta_market_alerts beta_notification_deliveries; do
  a=$(grep "^$t " "$WORK/cb1/COUNTS.txt"); b=$(grep "^$t " "$WORK/cb2/COUNTS.txt"); [ "$a" = "$b" ] || fail "result count changed for $t: '$a' vs '$b'"
done
gpg --batch --quiet --pinentry-mode loopback --passphrase-file "$PASS" --decrypt "$WORK/cb2/db_plain.sql.gz.gpg" | gunzip -c > "$WORK/deid_dump.sql"
for s in "Rex" "friend from the chat" "blocked by the user" "u_aaaaaaaaaaaa" "u_0123456789ab"; do grep -q -- "$s" "$WORK/deid_dump.sql" && fail "identifying string in de-identified dump: $s"; done
shred -u "$WORK/deid_dump.sql" 2>/dev/null || rm -f "$WORK/deid_dump.sql"
CLOSURE_VERIFY_MODE=local CLOSURE_VERIFY_WORK="$WORK/verify_work2" "$HERE/closure_restore_verify.sh" "$WORK/cb2" > "$WORK/verify2.log" 2>&1 || { cat "$WORK/verify2.log"; fail "restore verify of the de-identified export"; }
grep -q "ok beta_users = 0" "$WORK/verify2.log" || fail "de-identified restore count"
log "sizes: $(du -sh "$WORK/cb1" | cut -f1) full, $(du -sh "$WORK/cb2" | cut -f1) de-identified"
log "PASS"
