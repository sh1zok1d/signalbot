#!/usr/bin/env bash
# test_backup_restore.sh — end-to-end and negative tests of closure_backup.sh and closure_restore_verify.sh on synthetic data:
#   1. throwaway PostgreSQL with the beta schema + fixture (same as the de-identification test);
#   2. closure_backup.sh in local mode: streaming encryption, manifest; only *.gpg + manifest + counts + README exist;
#   3. "transfer" to a test store and back (filesystem copy standing in for rclone; sha256 verified at each hop);
#   4. closure_restore_verify.sh in local mode from the downloaded copy: decrypt, strict restore, table set, counts;
#   5. restore negatives: tampered ciphertext, wrong passphrase, corrupted gzip inside valid ciphertext, SQL error inside the
#      stream, truncated SQL stream, INCOMPLETE marker -> every one FAILs, leaves no verify database and no work dir;
#   6. backup negatives (fault injection, CLOSURE_TEST_MODE=1): pg_dump failure, gpg failure, SIGTERM during the dump,
#      SIGKILL during the dump (+ the next run cleans the leftovers), disk full (ulimit -f) -> no plaintext and no .partial
#      left, INCOMPLETE marker written, the earlier good backup untouched, RAM dir gone;
#   7. de-identify the source (deidentify_closure.sql) and back up again: participant counts 0, result counts unchanged.
# Usage: ./scripts/closure/test_backup_restore.sh [workdir]   (root; PostgreSQL 16 server binaries; gpg; tmpfs at /dev/shm)
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
psql -X -q -v ON_ERROR_STOP=1 -d "$DB" -f "$REPO/storage/beta_v0_schema.sql" >/dev/null 2>&1
psql -X -q -v ON_ERROR_STOP=1 -d "$DB" -f "$HERE/test_fixture_closure.sql" >/dev/null
log "database ready"

FAKE="$WORK/opt_signalbot"; install -d -m 700 "$FAKE" "$FAKE/artifacts"
printf 'POSTGRES_DB=%s\nPOSTGRES_USER=postgres\nBETA_FINGERPRINT_KEY=testkey-not-real\n' "$DB" > "$FAKE/.env"; chmod 600 "$FAKE/.env"
echo "synthetic artifact" > "$FAKE/artifacts/note.txt"
PASS="$WORK/closure.pass"; printf 'test-passphrase-%s-%s\n' "$RANDOM" "$RANDOM" > "$PASS"; chmod 600 "$PASS"
BAD="$WORK/wrong.pass"; printf 'wrong-passphrase-wrong-passphrase\n' > "$BAD"; chmod 600 "$BAD"
export CLOSURE_PG_MODE=local SIGNALBOT_DIR="$FAKE" CLOSURE_PASSPHRASE_FILE="$PASS" CLOSURE_MIN_DUMP_BYTES=1024
GPGD=(gpg --batch --quiet --pinentry-mode loopback --passphrase-file "$PASS")
no_plaintext() {  # no_plaintext <dir>: only ciphertext and the three plaintext metadata files may exist; never .partial
  local bad; bad=$(find "$1" -type f ! -name '*.gpg' ! -name MANIFEST.sha256 ! -name COUNTS.txt ! -name README.txt ! -name INCOMPLETE 2>/dev/null | wc -l)
  [ "$bad" = 0 ] || { find "$1" -type f ! -name '*.gpg' >&2; fail "plaintext or partial files in $1"; }
}
no_ram_dirs() { [ "$(ls -d /dev/shm/closure_backup_* 2>/dev/null | wc -l)" = 0 ] || fail "RAM directory left behind"; }
no_verify_db() { [ "$(psql -X -At -d postgres -c "SELECT count(*) FROM pg_database WHERE datname LIKE 'verify_%'")" = 0 ] || fail "throwaway verify database left behind"; [ "$(ls -d /dev/shm/closure_verify.* 2>/dev/null | wc -l)" = 0 ] || fail "verify work dir left behind"; }

log "2. dry run then apply"
CLOSURE_BACKUP_DIR="$WORK/cb1" "$HERE/closure_backup.sh" > "$WORK/dry.log" 2>&1 || { cat "$WORK/dry.log"; fail "dry run"; }
grep -q "dry run only" "$WORK/dry.log" || fail "dry run message missing"
[ ! -e "$WORK/cb1" ] || fail "dry run created the staging dir"
CLOSURE_BACKUP_DIR="$WORK/cb1" "$HERE/closure_backup.sh" --apply > "$WORK/apply.log" 2>&1 || { cat "$WORK/apply.log"; fail "apply"; }
for f in db_plain.sql.gz.gpg db_custom.dump.gpg secrets.tar.gz.gpg artifacts.tar.gz.gpg state_snapshot.tar.gz.gpg csv_results/beta_claims.csv.gz.gpg csv_participants/beta_users.csv.gz.gpg MANIFEST.sha256 COUNTS.txt README.txt; do
  [ -s "$WORK/cb1/$f" ] || fail "missing artifact $f"
done
no_plaintext "$WORK/cb1"; no_ram_dirs
[ ! -e "$WORK/cb1/INCOMPLETE" ] || fail "INCOMPLETE marker on a good run"
grep -q "^beta_users 5$" "$WORK/cb1/COUNTS.txt" || fail "COUNTS.txt wrong"
grep -q --binary-files=text "friend from the chat" "$WORK/cb1/db_plain.sql.gz.gpg" && fail "plaintext leaked into ciphertext" || true
"${GPGD[@]}" --decrypt "$WORK/cb1/db_plain.sql.gz.gpg" | gunzip -c | grep -c "friend from the chat" > /dev/null || fail "decrypted dump lacks fixture content"   # grep -c reads the whole stream (no SIGPIPE under pipefail)
[ "$("${GPGD[@]}" --decrypt "$WORK/cb1/csv_participants/beta_users.csv.gz.gpg" | gunzip -c | wc -l)" = 6 ] || fail "CSV line count"
( cd "$WORK/cb1" && sha256sum -c --quiet MANIFEST.sha256 ) || fail "manifest at source"
grep -qi "passphrase-" "$WORK/apply.log" && fail "passphrase text appeared in the log" || true
log "staging ok: $(find "$WORK/cb1" -type f | wc -l) files, all encrypted, no plaintext on disk"

log "3. transfer to the test store and back"
STORE="$WORK/store/closure_test"; DL="$WORK/download/closure_test"
if command -v rclone >/dev/null 2>&1; then
  rclone copy --checksum "$WORK/cb1" "$STORE" && rclone check "$WORK/cb1" "$STORE" && rclone copy --checksum "$STORE" "$DL"
else
  install -d -m 700 "$STORE" "$DL"; cp -rp "$WORK/cb1"/. "$STORE/"; cp -rp "$STORE"/. "$DL/"
  log "rclone not installed: filesystem copies stand in for the remote (checksums verified below)"
fi
( cd "$STORE" && sha256sum -c --quiet MANIFEST.sha256 ) || fail "manifest in store"
( cd "$DL" && sha256sum -c --quiet MANIFEST.sha256 ) || fail "manifest after download"

log "4. restore verification from the downloaded copy"
CLOSURE_VERIFY_MODE=local SIGNALBOT_REPO="$REPO" "$HERE/closure_restore_verify.sh" "$DL" > "$WORK/verify.log" 2>&1 || { cat "$WORK/verify.log"; fail "restore verify"; }
grep -q "RESTORE VERIFIED" "$WORK/verify.log" || fail "no RESTORE VERIFIED"
grep -q "ok beta_users = 5" "$WORK/verify.log" || fail "restored count check missing"
grep -qE "[0-9]+ tables present" "$WORK/verify.log" || fail "table-set check missing"
no_verify_db

# ---- restore negatives: each must FAIL (non-zero), print a reason, leave no database and no work dir
mutate() {  # mutate <dst> <mode>: copy of $DL whose plain dump is modified then re-encrypted with the same passphrase; manifest regenerated
  local dst="$1" mode="$2" tmp="$WORK/mut.sql"
  rm -rf "$dst"; install -d -m 700 "$dst"; cp -rp "$DL"/. "$dst/"
  "${GPGD[@]}" --decrypt "$DL/db_plain.sql.gz.gpg" | gunzip -c > "$tmp"
  case "$mode" in
    sql_error)   awk 'BEGIN{done=0} /^CREATE TABLE public\.beta_hist_stats/ && !done {print "INSERT INTO public.table_that_does_not_exist VALUES (1);"; done=1} {print}' "$tmp" > "$tmp.2"; mv "$tmp.2" "$tmp"; gzip -c "$tmp" > "$tmp.gz" ;;
    truncate)    head -c $(( $(stat -c %s "$tmp") * 6 / 10 )) "$tmp" > "$tmp.2"; mv "$tmp.2" "$tmp"; gzip -c "$tmp" > "$tmp.gz" ;;
    corrupt_gz)  gzip -c "$tmp" > "$tmp.gz"; head -c $(( $(stat -c %s "$tmp.gz") * 7 / 10 )) "$tmp.gz" > "$tmp.gz.2"; mv "$tmp.gz.2" "$tmp.gz" ;;
  esac
  rm -f "$dst/db_plain.sql.gz.gpg"
  "${GPGD[@]}" --yes --symmetric --cipher-algo AES256 -o "$dst/db_plain.sql.gz.gpg" "$tmp.gz"
  rm -f "$tmp" "$tmp.gz"
  ( cd "$dst" && find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256 )
}
expect_verify_fail() {  # expect_verify_fail <dir> <label> <grep pattern>
  local dir="$1" label="$2" pat="$3"; local logf="$WORK/neg_$label.log"
  if CLOSURE_VERIFY_MODE=local "$HERE/closure_restore_verify.sh" "$dir" > "$logf" 2>&1; then cat "$logf"; fail "$label: tampered/broken backup was accepted"; fi
  grep -qE "$pat" "$logf" || { cat "$logf"; fail "$label: expected failure reason not reported"; }
  grep -q "RESTORE NOT VERIFIED" "$logf" || fail "$label: no NOT VERIFIED line"
  no_verify_db
  log "  negative ok: $label"
}
log "5. restore negatives"
TAMP="$WORK/neg_tamper"; install -d -m 700 "$TAMP"; cp -rp "$DL"/. "$TAMP/"
printf '\x00' | dd of="$TAMP/db_plain.sql.gz.gpg" bs=1 seek=100 conv=notrunc status=none
expect_verify_fail "$TAMP" tampered_ciphertext "manifest check failed"
CLOSURE_VERIFY_MODE=local CLOSURE_PASSPHRASE_FILE="$BAD" "$HERE/closure_restore_verify.sh" "$DL" > "$WORK/neg_badpass.log" 2>&1 && fail "wrong passphrase accepted" || true
grep -q "decryption failed" "$WORK/neg_badpass.log" || fail "wrong passphrase: reason missing"; no_verify_db; log "  negative ok: wrong_passphrase"
mutate "$WORK/neg_corrupt" corrupt_gz;  expect_verify_fail "$WORK/neg_corrupt" corrupted_gzip "not a valid gzip"
mutate "$WORK/neg_sqlerr" sql_error;    expect_verify_fail "$WORK/neg_sqlerr" sql_error_in_stream "restore aborted"
mutate "$WORK/neg_trunc" truncate;      expect_verify_fail "$WORK/neg_trunc" truncated_stream "truncated: no completion marker"
INC="$WORK/neg_incomplete"; install -d -m 700 "$INC"; cp -rp "$DL"/. "$INC/"; echo x > "$INC/INCOMPLETE"
expect_verify_fail "$INC" incomplete_marker "marked INCOMPLETE"

# ---- backup negatives: fault injection; cb1 (the earlier good backup) must stay byte-identical
log "6. backup negatives (fault injection)"
cb1_before="$(cd "$WORK/cb1" && find . -type f -exec sha256sum {} + | sort)"
expect_backup_fail() {  # expect_backup_fail <label> <dir> <pattern> -- <command...>
  local label="$1" dir="$2" pat="$3"; shift 3; [ "$1" = -- ] && shift
  local logf="$WORK/bneg_$label.log"
  if "$@" > "$logf" 2>&1; then cat "$logf"; fail "$label: backup reported success"; fi
  grep -qE "$pat" "$logf" || { cat "$logf"; fail "$label: expected reason missing"; }
  [ -e "$dir/INCOMPLETE" ] || fail "$label: no INCOMPLETE marker"
  [ "$(find "$dir" -name '*.partial' | wc -l)" = 0 ] || fail "$label: .partial left"
  no_plaintext "$dir"; no_ram_dirs
  [ "$(cd "$WORK/cb1" && find . -type f -exec sha256sum {} + | sort)" = "$cb1_before" ] || fail "$label: earlier good backup changed"
  grep -qi "passphrase-" "$logf" && fail "$label: passphrase in log" || true
  log "  negative ok: $label"
}
export CLOSURE_TEST_MODE=1
expect_backup_fail dump_failure "$WORK/bneg1" "producer failed" -- env CLOSURE_TEST_FAULT=dump_fail CLOSURE_BACKUP_DIR="$WORK/bneg1" "$HERE/closure_backup.sh" --apply
expect_backup_fail gpg_failure  "$WORK/bneg2" "gpg failed"      -- env CLOSURE_TEST_FAULT=gpg_fail  CLOSURE_BACKUP_DIR="$WORK/bneg2" "$HERE/closure_backup.sh" --apply
# disk full: a file-size limit makes the first large ciphertext write fail (EFBIG stands in for ENOSPC)
expect_backup_fail disk_full "$WORK/bneg3" "gpg failed|producer failed" -- bash -c "ulimit -f 4; CLOSURE_BACKUP_DIR='$WORK/bneg3' '$HERE/closure_backup.sh' --apply"
# SIGTERM during the (slowed) dump
CLOSURE_TEST_FAULT=slow_dump CLOSURE_BACKUP_DIR="$WORK/bneg4" setsid "$HERE/closure_backup.sh" --apply > "$WORK/bneg_sigterm.log" 2>&1 &
bpid=$!; sleep 3; kill -TERM "$bpid"; wait "$bpid" && fail "SIGTERM: backup reported success" || true
sleep 10   # orphaned pipeline children of the interrupted run (psql, gpg waiting on a closed pipe) end on their own
pg_isready >/dev/null || fail "SIGTERM scenario: the test server itself died"
grep -q "interrupted" "$WORK/bneg_sigterm.log" || { cat "$WORK/bneg_sigterm.log"; fail "SIGTERM: not reported"; }
[ -e "$WORK/bneg4/INCOMPLETE" ] || fail "SIGTERM: no INCOMPLETE marker"
[ "$(find "$WORK/bneg4" -name '*.partial' | wc -l)" = 0 ] || fail "SIGTERM: .partial left"; no_plaintext "$WORK/bneg4"; no_ram_dirs
log "  negative ok: sigterm_during_dump"
# SIGKILL during the dump: no trap runs; only ciphertext .partial and the RAM dir may remain; the next run removes both
CLOSURE_TEST_FAULT=slow_dump CLOSURE_BACKUP_DIR="$WORK/bneg5" setsid "$HERE/closure_backup.sh" --apply > "$WORK/bneg_sigkill.log" 2>&1 &
bpid=$!; sleep 3; kill -KILL "$bpid"; wait "$bpid" 2>/dev/null || true
sleep 10   # orphaned pipeline children of the killed shell end on their own; nothing else is killed by name or group
pg_isready >/dev/null || fail "SIGKILL scenario: the test server itself died"
[ "$(find "$WORK/bneg5" -type f ! -name '*.gpg' ! -name '*.partial' ! -name COUNTS.txt | wc -l)" = 0 ] || { find "$WORK/bneg5" -type f; fail "SIGKILL: plaintext on disk"; }
ramleft=$(ls -d /dev/shm/closure_backup_* 2>/dev/null | wc -l); partleft=$(find "$WORK/bneg5" -name '*.partial' | wc -l)
log "  after SIGKILL: RAM dirs left $ramleft, ciphertext .partial left $partleft (both expected possible; cleaned by the next run)"
CLOSURE_BACKUP_DIR="$WORK/bneg5" "$HERE/closure_backup.sh" --apply > "$WORK/bneg_rerun.log" 2>&1 || { cat "$WORK/bneg_rerun.log"; fail "rerun after SIGKILL"; }
no_ram_dirs; [ "$(find "$WORK/bneg5" -name '*.partial' | wc -l)" = 0 ] || fail "rerun left .partial"; [ ! -e "$WORK/bneg5/INCOMPLETE" ] || fail "rerun left INCOMPLETE"
no_plaintext "$WORK/bneg5"; log "  negative ok: sigkill_then_rerun_cleans"
unset CLOSURE_TEST_MODE

log "7. de-identify, then the de-identified export"
psql -X -q -v ON_ERROR_STOP=1 -d "$DB" -v owner_fps=u_0123456789ab -v owner_id=1001 -v apply=1 -f "$HERE/deidentify_closure.sql" > "$WORK/deid.log" 2>&1 || { cat "$WORK/deid.log"; fail "deidentify"; }
CLOSURE_BACKUP_DIR="$WORK/cb2" "$HERE/closure_backup.sh" --apply > "$WORK/apply2.log" 2>&1 || { cat "$WORK/apply2.log"; fail "second apply"; }
for t in beta_users beta_allowlist beta_waitlist beta_feedback_messages beta_user_activity; do grep -q "^$t 0$" "$WORK/cb2/COUNTS.txt" || fail "$t not 0 in de-identified export"; done
for t in beta_claims beta_claim_outcomes beta_forecasts beta_hist_stats beta_episodes beta_push_decisions beta_market_alerts beta_notification_deliveries; do
  a=$(grep "^$t " "$WORK/cb1/COUNTS.txt"); b=$(grep "^$t " "$WORK/cb2/COUNTS.txt"); [ "$a" = "$b" ] || fail "result count changed for $t: '$a' vs '$b'"
done
for s in "Rex" "friend from the chat" "blocked by the user" "u_aaaaaaaaaaaa" "u_0123456789ab"; do
  if "${GPGD[@]}" --decrypt "$WORK/cb2/db_plain.sql.gz.gpg" | gunzip -c | grep -c -- "$s" > /dev/null; then fail "identifying string in de-identified dump: $s"; fi
done
CLOSURE_VERIFY_MODE=local "$HERE/closure_restore_verify.sh" "$WORK/cb2" > "$WORK/verify2.log" 2>&1 || { cat "$WORK/verify2.log"; fail "restore verify of the de-identified export"; }
grep -q "ok beta_users = 0" "$WORK/verify2.log" || fail "de-identified restore count"; no_verify_db
log "sizes: $(du -sh "$WORK/cb1" | cut -f1) full, $(du -sh "$WORK/cb2" | cut -f1) de-identified"
log "PASS"
