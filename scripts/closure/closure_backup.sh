#!/usr/bin/env bash
# closure_backup.sh — stage, ENCRYPT and verify the Pulsy closure backup, without writing plaintext to disk.
#
# Part of docs/closure/BACKUP_AND_RESTORE_PLAN_V1.md. Run as root on the VPS, in a tmux session:
#   CLOSURE_PASSPHRASE_FILE=/root/closure.pass ./scripts/closure/closure_backup.sh            # dry run: preflight + plan, touches nothing
#   CLOSURE_PASSPHRASE_FILE=/root/closure.pass ./scripts/closure/closure_backup.sh --apply    # performs the backup
#
# Modes (CLOSURE_PG_MODE): `docker` (default; PostgreSQL runs in the container $BTCBOT_PG_CONTAINER, as on the VPS) or
# `local` (pg_dump/psql on this host against PGHOST/PGPORT; used by scripts/closure/test_backup_restore.sh).
#
# Design (after the owner's audit of 2026-10-15):
#   - STREAMING ENCRYPTION: every artifact is produced as a stream (pg_dump | gzip, tar czf -, \copy TO STDOUT | gzip,
#     journalctl | gzip, docker ... tar czf -) and piped straight into gpg (symmetric AES-256, passphrase from a root-only
#     file). No dump, CSV, journal, volume or secret archive ever exists in plaintext on disk. The only plaintext the run
#     creates is the small state snapshot (systemctl/docker status text), written into a private tmpfs directory in RAM
#     (/dev/shm), tar-streamed into gpg and removed; it never touches the disk.
#   - every ciphertext is written as <name>.gpg.partial and renamed only after it was decrypted and structurally verified
#     (gzip -t / tar -t / pg_restore --list / CSV line count = row count + 1); gpg's own MDC catches ciphertext damage;
#   - exit status of every pipeline stage is checked (pipefail + PIPESTATUS): pg_dump, gzip, tar, gpg, tee;
#   - traps on EXIT/INT/TERM remove the RAM directory and every *.partial of THIS run, write an INCOMPLETE marker on failure
#     and never touch earlier staging directories; on start, stale RAM directories and *.partial files of earlier runs are
#     removed; completed *.gpg files of this run are kept (ciphertext only);
#   - a free-space preflight compares the free disk with the database size; ENOSPC surfaces as a gpg/gzip write error;
#   - no secret value is ever printed: the passphrase is read by gpg from its file, .env is sourced but never echoed,
#     `set -x` is never enabled.
#   What a trap cannot cover: SIGKILL and power loss. After those, at most ciphertext *.partial files remain on disk and the
#   RAM snapshot directory survives until reboot (SIGKILL) or vanishes (power loss); the next run removes both.
# It stops nothing and deletes nothing outside its own staging directory and its RAM directory.
set -euo pipefail
umask 077

APPLY=0
VOLUMES=1
for a in "$@"; do
  case "$a" in
    --apply) APPLY=1 ;;
    --no-volumes) VOLUMES=0 ;;
    *) echo "usage: $0 [--apply] [--no-volumes]" >&2; exit 64 ;;
  esac
done

MODE="${CLOSURE_PG_MODE:-docker}"
SIGNALBOT_DIR="${SIGNALBOT_DIR:-/opt/signalbot}"
ENV_FILE="${SIGNALBOT_ENV_FILE:-$SIGNALBOT_DIR/.env}"
CONTAINER="${BTCBOT_PG_CONTAINER:-btcbot_timescaledb}"
PG_VOLUME="${PG_VOLUME:-timescale_data}"
REDIS_VOLUME="${REDIS_VOLUME:-redis_data}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CB="${CLOSURE_BACKUP_DIR:-$SIGNALBOT_DIR/closure_backup_$STAMP}"
PASSFILE="${CLOSURE_PASSPHRASE_FILE:-}"
MIN_DUMP_BYTES="${CLOSURE_MIN_DUMP_BYTES:-1048576}"
MIN_FREE_RATIO="${CLOSURE_MIN_FREE_RATIO:-0.6}"      # free disk must be >= ratio x database size (compressed dumps are far smaller)
SHM_BASE="${CLOSURE_SHM_BASE:-/dev/shm}"
TEST_FAULT="${CLOSURE_TEST_FAULT:-}"                  # fault injection for scripts/closure/test_backup_restore.sh only (requires CLOSURE_TEST_MODE=1)
[ -n "$TEST_FAULT" ] && [ "${CLOSURE_TEST_MODE:-0}" != 1 ] && { echo "CLOSURE_TEST_FAULT is a test-only variable" >&2; exit 64; }

RESULT_TABLES="forecast_predictions forecast_outcomes beta_claims beta_claim_outcomes beta_claim_displays beta_forecasts
  beta_episodes beta_episode_outcomes beta_push_decisions beta_market_alerts beta_hist_stats beta_weekly_reports
  beta_shadow_anchors beta_shadow_issues beta_shadow_outcomes beta_shadow_hour_status beta_shadow_spec_identity
  beta_deleted_cohort_counts beta_rejected_start_counts"
PII_TABLES="beta_users beta_allowlist beta_waitlist beta_invites beta_user_activity beta_feedback beta_feedback_messages
  beta_message_votes beta_reasons beta_price_alerts beta_owner_forwards beta_notification_deliveries beta_admin_audit
  beta_rejected_start_hashes telegram_notification_deliveries telegram_notifier_state"

log() { printf '[closure-backup %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
need() { have "$1" || fail "required tool missing: $1"; }
pg()  { if [ "$MODE" = docker ]; then docker exec "$CONTAINER" "$@"; else "$@"; fi; }       # no stdin
pgi() { if [ "$MODE" = docker ]; then docker exec -i "$CONTAINER" "$@"; else "$@"; fi; }    # with stdin

# ---------- cleanup: the only state this run owns is $RAM and the *.partial files of this run ----------
RAM=""; STARTED=0; DONE=0
cleanup() {
  local rc=$?
  trap - EXIT INT TERM
  if [ -n "$RAM" ] && [ -d "$RAM" ]; then rm -rf "$RAM"; fi
  if [ "$STARTED" = 1 ]; then
    find "$CB" -maxdepth 2 -name '*.partial' -type f -delete 2>/dev/null || true
    if [ "$DONE" != 1 ]; then
      printf 'INCOMPLETE run %s: exit %s at %s. Completed *.gpg files are ciphertext only; no plaintext was written to disk.\n' "$STAMP" "$rc" "$(date -u +%FT%TZ)" > "$CB/INCOMPLETE" 2>/dev/null || true
      echo "ERROR: run did not complete (exit $rc); partial ciphertext removed; $CB marked INCOMPLETE" >&2
    fi
  fi
  exit "$rc"
}
on_signal() { echo "ERROR: interrupted" >&2; exit 130; }
trap cleanup EXIT
trap on_signal INT TERM

# ---------- preflight (both modes) ----------
[ "$(id -u)" = "0" ] || fail "run as root"
for t in gpg sha256sum tar gzip; do need "$t"; done
case "$MODE" in
  docker) need docker ;;
  local) need pg_dump; need psql; need pg_isready ;;
  *) fail "CLOSURE_PG_MODE must be docker or local" ;;
esac
have journalctl || log "journalctl not found: journal export will be skipped"
have systemctl || log "systemctl not found: unit snapshot will be partial"
[ -r "$ENV_FILE" ] || fail "cannot read $ENV_FILE"
[ -n "$PASSFILE" ] || fail "set CLOSURE_PASSPHRASE_FILE to a root-only file (mode 600) holding the archive passphrase"
[ -r "$PASSFILE" ] || fail "cannot read passphrase file"
[ "$(stat -c %a "$PASSFILE")" = "600" ] || fail "passphrase file must be mode 600"
[ "$(stat -c %U "$PASSFILE")" = "root" ] || fail "passphrase file must be owned by root"
[ "$(wc -c < "$PASSFILE")" -ge 20 ] || fail "passphrase shorter than 20 bytes"
[ -d "$SHM_BASE" ] || fail "no RAM-backed directory at $SHM_BASE (set CLOSURE_SHM_BASE to a tmpfs mount)"
shm_fs="$(df -PT "$SHM_BASE" | awk 'NR==2{print $2}')"
[ "$shm_fs" = tmpfs ] || [ "$shm_fs" = ramfs ] || fail "$SHM_BASE is $shm_fs, not tmpfs/ramfs: the state snapshot would touch the disk"
set -a; . "$ENV_FILE"; set +a
: "${POSTGRES_DB:?POSTGRES_DB missing in $ENV_FILE}" "${POSTGRES_USER:?POSTGRES_USER missing in $ENV_FILE}"
if [ "$MODE" = docker ]; then
  docker inspect "$CONTAINER" >/dev/null 2>&1 || fail "container $CONTAINER not found"
  [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" = "true" ] || fail "container $CONTAINER is not running (dumps need a live PostgreSQL)"
else
  VOLUMES=0
  [ -n "${POSTGRES_PASSWORD:-}" ] && export PGPASSWORD="$POSTGRES_PASSWORD"
fi
pg pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null || fail "pg_isready failed"
psqlq() { pg psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -v ON_ERROR_STOP=1 -c "$1"; }
table_exists() { [ "$(psqlq "SELECT to_regclass('public.$1') IS NOT NULL")" = "t" ]; }
db_bytes="$(psqlq "SELECT pg_database_size(current_database())" 2>/dev/null || echo 0)"
install -d -m 700 "$(dirname "$CB")"
free_kb=$(df -Pk "$(dirname "$CB")" | awk 'NR==2{print $4}')
need_kb=$(awk -v b="$db_bytes" -v r="$MIN_FREE_RATIO" 'BEGIN{printf "%d", b/1024*r}')
log "mode: $MODE; staging dir: $CB; db: $POSTGRES_DB (user name withheld); db size: $((db_bytes/1048576)) MB; free: $((free_kb/1024)) MB; required free: $((need_kb/1024)) MB"
[ "$free_kb" -ge "$need_kb" ] || fail "not enough free disk for the staging dir (need >= $MIN_FREE_RATIO x database size)"
log "plan: state snapshot (RAM) -> pg_dump plain+custom+globals -> CSV per table -> volumes($VOLUMES) -> secrets -> journals -> artifacts; each streamed into gpg; verify; manifest"
[ "$APPLY" = 1 ] || { log "dry run only; re-run with --apply"; DONE=1; exit 0; }

# ---------- staging and RAM dir; remove leftovers of earlier interrupted runs ----------
rm -rf "$SHM_BASE"/closure_backup_* 2>/dev/null || true
RAM="$(mktemp -d "$SHM_BASE/closure_backup_XXXXXX")"; chmod 700 "$RAM"
install -d -m 700 "$CB" "$CB/csv_results" "$CB/csv_participants"
find "$CB" -maxdepth 2 -name '*.partial' -type f -delete 2>/dev/null || true
rm -f "$CB/INCOMPLETE"
STARTED=1
GPG=(gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$PASSFILE")
if [ "$TEST_FAULT" = gpg_fail ]; then GPG=(sh -c 'cat > /dev/null; exit 9'); fi   # consumes the stream, then "fails" like a full disk

# enc_stream <relative name without .gpg> <verify kind> <producer command...>
#   producer stdout -> gpg -> $CB/<name>.gpg.partial; then decrypt and verify structurally; then rename.
#   verify kinds: gzip (gzip -t), tar (tar -tzf -), pgcustom (pg_restore --list), csv:<rows> (gunzip | wc -l == rows+1), none
enc_stream() {
  local name="$1" kind="$2"; shift 2
  local out="$CB/$name.gpg" st
  set +e   # errexit would abort before the per-stage statuses are read
  "$@" | "${GPG[@]}" --symmetric --cipher-algo AES256 -o "$out.partial"
  st=("${PIPESTATUS[@]}")
  set -e
  [ "${st[0]}" = 0 ] || fail "producer failed for $name (exit ${st[0]})"
  [ "${st[1]}" = 0 ] || fail "gpg failed for $name (exit ${st[1]}; disk full?)"
  [ -s "$out.partial" ] || fail "empty ciphertext for $name"
  case "$kind" in
    gzip)     "${GPG[@]}" --decrypt "$out.partial" | gzip -t || fail "verification failed for $name (gzip)" ;;
    tar)      "${GPG[@]}" --decrypt "$out.partial" | tar -tzf - > /dev/null || fail "verification failed for $name (tar)" ;;
    pgcustom) "${GPG[@]}" --decrypt "$out.partial" | pgi pg_restore --list > /dev/null || fail "verification failed for $name (pg_restore --list)" ;;
    csv:*)    local rows="${kind#csv:}" lines
              lines=$("${GPG[@]}" --decrypt "$out.partial" | gunzip -c | wc -l) || fail "verification failed for $name (gunzip)"
              [ "$lines" = $((rows + 1)) ] || fail "verification failed for $name: $lines lines, expected $((rows + 1)) (rows + header)" ;;
    none)     "${GPG[@]}" --decrypt "$out.partial" > /dev/null || fail "verification failed for $name (decrypt)" ;;
    *) fail "unknown verify kind $kind" ;;
  esac
  mv "$out.partial" "$out"; chmod 600 "$out"
  log "encrypted+verified: $name.gpg ($(stat -c %s "$out") bytes)"
}
# producers used with enc_stream
prod_plain_dump()  { [ "$TEST_FAULT" = dump_fail ] && { echo "injected pg_dump failure" >&2; return 3; }
                     if [ "$TEST_FAULT" = slow_dump ]; then sleep 8; fi
                     pg pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges | gzip -c; }
prod_custom_dump() { pg pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges -Fc; }
prod_globals()     { pg pg_dumpall -U "$POSTGRES_USER" --globals-only; }
prod_csv()         { pg psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "\\copy (SELECT * FROM public.$1) TO STDOUT CSV HEADER" | gzip -c; }
prod_volume()      { docker run --rm -v "$1:/src:ro" alpine:3.20 tar czf - -C /src .; }
prod_tar()         { tar czf - --ignore-failed-read "$@" 2>/dev/null; }
prod_journal()     { local st; set +e; journalctl -u 'signalbot*' "$@" 2>/dev/null | gzip -c; st=("${PIPESTATUS[@]}"); set -e
                     [ "${st[0]}" = 0 ] || echo "WARNING: journalctl exited ${st[0]} (no journal files here?); the export may be empty" >&2
                     return "${st[1]}"; }

# ---------- 0. state snapshot (plaintext only in RAM) ----------
log "0. state snapshot"
install -d -m 700 "$RAM/snap" "$RAM/snap/units"
{
  echo "stamp=$STAMP"; echo "mode=$MODE"; echo "git_head=$(git -C "$SIGNALBOT_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "build_sha=$(cat "$SIGNALBOT_DIR/BUILD_SHA" 2>/dev/null || echo none)"
} > "$RAM/snap/state.txt"
if have systemctl; then
  systemctl list-timers --all --no-pager > "$RAM/snap/systemd_timers.txt" 2>&1 || true
  systemctl list-units --all --no-pager 'signalbot*' > "$RAM/snap/systemd_units.txt" 2>&1 || true
  for u in $(systemctl list-units --all --no-legend --plain 'signalbot*' 2>/dev/null | awk '{print $1}'); do
    systemctl status "$u" --no-pager -l > "$RAM/snap/units/status_$u.txt" 2>&1 || true
  done
fi
cp /etc/systemd/system/signalbot*.service /etc/systemd/system/signalbot*.timer "$RAM/snap/units/" 2>/dev/null || true
if have docker; then docker ps -a > "$RAM/snap/docker_ps.txt" 2>&1 || true; docker system df -v > "$RAM/snap/docker_df.txt" 2>&1 || true; fi
crontab -l > "$RAM/snap/crontab_root.txt" 2>&1 || true
enc_stream state_snapshot.tar.gz tar prod_tar -C "$RAM" snap
rm -rf "$RAM/snap"

# ---------- 1. row counts (aggregate, plaintext; used by the restore verification and the CSV checks) ----------
log "1. row counts"
: > "$CB/COUNTS.txt"
declare -A ROWS
for t in $RESULT_TABLES $PII_TABLES klines_1m open_interest funding_rate beta_state_tape; do
  if table_exists "$t"; then ROWS[$t]="$(psqlq "SELECT count(*) FROM public.$t")"; echo "$t ${ROWS[$t]}" >> "$CB/COUNTS.txt"; else echo "$t ABSENT" >> "$CB/COUNTS.txt"; fi
done
if table_exists klines_1m; then
  echo "klines_1m_min_max $(psqlq "SELECT coalesce(min(open_time)::text,'') || ' ' || coalesce(max(open_time)::text,'') FROM klines_1m")" >> "$CB/COUNTS.txt"
fi

# ---------- 2. logical dumps ----------
log "2a. pg_dump plain (streamed)"
enc_stream db_plain.sql.gz gzip prod_plain_dump
[ "$(stat -c %s "$CB/db_plain.sql.gz.gpg")" -gt "$MIN_DUMP_BYTES" ] || fail "plain dump smaller than $MIN_DUMP_BYTES bytes"
"${GPG[@]}" --decrypt "$CB/db_plain.sql.gz.gpg" | gunzip -c | tail -c 200 | grep -c "PostgreSQL database dump complete" > /dev/null || fail "plain dump lacks the completion marker"
log "2b. pg_dump custom (streamed)"
enc_stream db_custom.dump pgcustom prod_custom_dump
log "2c. globals"
if pg pg_dumpall -U "$POSTGRES_USER" --globals-only > /dev/null 2>&1; then enc_stream db_globals.sql none prod_globals
else log "globals dump unavailable (non-superuser?); continuing without it"; fi

# ---------- 3. CSV exports, one encrypted file per table, line count checked against the row count ----------
log "3. CSV exports"
for t in $RESULT_TABLES; do table_exists "$t" || continue; enc_stream "csv_results/$t.csv.gz" "csv:${ROWS[$t]}" prod_csv "$t"; done
for t in $PII_TABLES;    do table_exists "$t" || continue; enc_stream "csv_participants/$t.csv.gz" "csv:${ROWS[$t]}" prod_csv "$t"; done

# ---------- 4. volumes (docker mode only; inconsistent while PostgreSQL runs — complements the dumps) ----------
if [ "$VOLUMES" = 1 ]; then
  log "4. volumes (streamed)"
  for v in "$PG_VOLUME" "$REDIS_VOLUME"; do
    docker volume inspect "$v" >/dev/null 2>&1 || { log "volume $v absent, skipped"; continue; }
    enc_stream "volume_$v.tar.gz" tar prod_volume "$v"
  done
fi

# ---------- 5. secrets and configuration ----------
log "5. secrets (streamed)"
enc_stream secrets.tar.gz tar prod_tar "$ENV_FILE" "$SIGNALBOT_DIR/.env.beta-feeds" /etc/signalbot

# ---------- 6. journals ----------
if have journalctl; then
  log "6. journals (streamed)"
  enc_stream journal_signalbot.export.gz gzip prod_journal -o export
  enc_stream journal_signalbot.txt.gz gzip prod_journal --no-pager
fi

# ---------- 7. artifacts outside git ----------
log "7. artifacts (streamed)"
art_dirs=()
for d in artifacts exports data logs backups; do [ -d "$SIGNALBOT_DIR/$d" ] && art_dirs+=("$d"); done
if [ "${#art_dirs[@]}" -gt 0 ]; then
  enc_stream artifacts.tar.gz tar prod_tar -C "$SIGNALBOT_DIR" "${art_dirs[@]}"
else log "no artifact directories under $SIGNALBOT_DIR; skipped"; fi

# ---------- 8. manifest and closing checks ----------
log "8. manifest"
cat > "$CB/README.txt" <<EOF
Pulsy closure backup, staged $STAMP ($MODE mode) by scripts/closure/closure_backup.sh (streaming encryption: no plaintext on disk).
Every *.gpg file is gpg symmetric AES-256; the passphrase is held by the owner only.
Contents: state snapshot, pg_dump plain and custom, globals (if available), CSV per table (csv_results/, csv_participants/),
volumes (docker mode), secrets, journald export (if available), artifacts. COUNTS.txt holds aggregate row counts.
Decrypt: gpg --batch --pinentry-mode loopback --passphrase-file <file> --decrypt <name>.gpg > <name>
Verify: sha256sum -c MANIFEST.sha256
EOF
( cd "$CB" && find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256 )
leftover=$(find "$CB" -type f ! -name '*.gpg' ! -name MANIFEST.sha256 ! -name COUNTS.txt ! -name README.txt | wc -l)
[ "$leftover" = 0 ] || fail "unexpected plaintext files in $CB"
[ "$(find "$CB" -name '*.partial' | wc -l)" = 0 ] || fail "partial files remain"
rm -rf "$RAM"; RAM=""
chmod 700 "$CB" "$CB/csv_results" "$CB/csv_participants"; find "$CB" -type f -exec chmod 600 {} +
DONE=1
log "done: $CB ($(find "$CB" -type f | wc -l) files)"
log "next: sha256sum -c MANIFEST.sha256; rclone copy --checksum \"$CB\" <remote>:closure_$STAMP/ ; rclone check \"$CB\" <remote>:closure_$STAMP/ ; copy to owner's disk; then scripts/closure/closure_restore_verify.sh on a clean machine"
