#!/usr/bin/env bash
# closure_backup.sh — stage, ENCRYPT and verify the Pulsy closure backup on the VPS.
#
# Part of docs/closure/BACKUP_AND_RESTORE_PLAN_V1.md. Run as root on the VPS, in a tmux session:
#   CLOSURE_PASSPHRASE_FILE=/root/closure.pass ./scripts/closure/closure_backup.sh            # dry run: prints the plan, touches nothing
#   CLOSURE_PASSPHRASE_FILE=/root/closure.pass ./scripts/closure/closure_backup.sh --apply    # performs the backup
#
# Rules this script enforces:
#   - every produced file that can hold personal data (dumps, CSV, journals, volumes, secrets, unit snapshots) is encrypted with
#     gpg AES-256 (symmetric, passphrase from a root-only file) BEFORE anything leaves the staging directory; the plaintext is
#     verified against the ciphertext and then shredded; only *.gpg, MANIFEST.sha256, COUNTS.txt and README.txt remain;
#   - `set -euo pipefail`, umask 077, a .partial suffix until each artifact is verified, explicit tool checks;
#   - nothing is copied off the VPS here: the off-site copy is a separate step (`rclone copy --checksum` of *.gpg + manifest).
# It stops nothing, deletes nothing outside its own staging directory and never prints secret values.
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

SIGNALBOT_DIR="${SIGNALBOT_DIR:-/opt/signalbot}"
ENV_FILE="${SIGNALBOT_ENV_FILE:-$SIGNALBOT_DIR/.env}"
CONTAINER="${BTCBOT_PG_CONTAINER:-btcbot_timescaledb}"
PG_VOLUME="${PG_VOLUME:-timescale_data}"
REDIS_VOLUME="${REDIS_VOLUME:-redis_data}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CB="${CLOSURE_BACKUP_DIR:-$SIGNALBOT_DIR/closure_backup_$STAMP}"
PASSFILE="${CLOSURE_PASSPHRASE_FILE:-}"

# Result tables (no user identifiers) and participant tables (personal data). Both are exported; both are encrypted.
RESULT_TABLES="forecast_predictions forecast_outcomes beta_claims beta_claim_outcomes beta_claim_displays beta_forecasts
  beta_episodes beta_episode_outcomes beta_push_decisions beta_market_alerts beta_hist_stats beta_weekly_reports
  beta_shadow_anchors beta_shadow_issues beta_shadow_outcomes beta_shadow_hour_status beta_shadow_spec_identity
  beta_deleted_cohort_counts beta_rejected_start_counts"
PII_TABLES="beta_users beta_allowlist beta_waitlist beta_invites beta_user_activity beta_feedback beta_feedback_messages
  beta_message_votes beta_reasons beta_price_alerts beta_owner_forwards beta_notification_deliveries beta_admin_audit
  beta_rejected_start_hashes telegram_notification_deliveries telegram_notifier_state"

log() { printf '[closure-backup %s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "required tool missing: $1"; }

# ---------- preflight (both modes) ----------
[ "$(id -u)" = "0" ] || fail "run as root"
for t in docker gpg sha256sum tar gzip cmp journalctl systemctl; do need "$t"; done
command -v shred >/dev/null 2>&1 || log "shred not found: plaintext will be removed with rm (less secure on SSD anyway; the disk is destroyed with the VPS)"
[ -r "$ENV_FILE" ] || fail "cannot read $ENV_FILE"
[ -n "$PASSFILE" ] || fail "set CLOSURE_PASSPHRASE_FILE to a root-only file (mode 600) holding the archive passphrase"
[ -r "$PASSFILE" ] || fail "cannot read passphrase file"
[ "$(stat -c %a "$PASSFILE")" = "600" ] || fail "passphrase file must be mode 600"
[ "$(stat -c %U "$PASSFILE")" = "root" ] || fail "passphrase file must be owned by root"
[ "$(wc -c < "$PASSFILE")" -ge 20 ] || fail "passphrase shorter than 20 bytes"
docker inspect "$CONTAINER" >/dev/null 2>&1 || fail "container $CONTAINER not found"
[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" = "true" ] || fail "container $CONTAINER is not running (dumps need a live PostgreSQL)"
set -a; . "$ENV_FILE"; set +a
: "${POSTGRES_DB:?POSTGRES_DB missing in $ENV_FILE}" "${POSTGRES_USER:?POSTGRES_USER missing in $ENV_FILE}"
docker exec "$CONTAINER" pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null || fail "pg_isready failed"
free_kb=$(df -Pk "$(dirname "$CB")" | awk 'NR==2{print $4}')
vol_bytes=$(docker system df -v --format '{{json .}}' 2>/dev/null | tr -d '\n' | grep -o "\"Name\":\"$PG_VOLUME\"[^}]*" | grep -o '"Size":"[^"]*"' | head -1 || true)
log "staging dir: $CB"; log "db: $POSTGRES_DB (user name withheld); container: $CONTAINER"; log "free space: $((free_kb/1024)) MB; pg volume size: ${vol_bytes:-unknown}"
log "plan: state snapshot -> pg_dump plain+custom+globals -> CSV (results, participants) -> volumes($VOLUMES) -> secrets -> journals -> artifacts -> units -> encrypt each -> manifest"
[ "$APPLY" = 1 ] || { log "dry run only; re-run with --apply"; exit 0; }

# ---------- helpers ----------
install -d -m 700 "$CB" "$CB/csv_results" "$CB/csv_participants" "$CB/units"
GPG=(gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$PASSFILE")
enc() {  # enc <plaintext path>: writes <path>.gpg, verifies round-trip, destroys plaintext
  local p="$1"
  [ -s "$p" ] || { log "skip empty: $p"; rm -f "$p"; return 0; }
  "${GPG[@]}" --symmetric --cipher-algo AES256 -o "$p.gpg.partial" "$p"
  "${GPG[@]}" --decrypt "$p.gpg.partial" | cmp -s - "$p" || fail "round-trip verification failed for $p"
  mv "$p.gpg.partial" "$p.gpg"
  if command -v shred >/dev/null 2>&1; then shred -u "$p"; else rm -f "$p"; fi
  log "encrypted: $(basename "$p").gpg ($(stat -c %s "$p.gpg") bytes)"
}
pg() { docker exec "$CONTAINER" "$@"; }
psqlq() { pg psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -v ON_ERROR_STOP=1 -c "$1"; }
table_exists() { [ "$(psqlq "SELECT to_regclass('public.$1') IS NOT NULL")" = "t" ]; }

# ---------- 0. state snapshot ----------
log "0. state snapshot"
{
  echo "stamp=$STAMP"; echo "git_head=$(git -C "$SIGNALBOT_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
  echo "build_sha=$(cat "$SIGNALBOT_DIR/BUILD_SHA" 2>/dev/null || echo none)"
} > "$CB/state.txt"
systemctl list-timers --all --no-pager > "$CB/systemd_timers.txt" 2>&1 || true
systemctl list-units --all --no-pager 'signalbot*' > "$CB/systemd_units.txt" 2>&1 || true
for u in $(systemctl list-units --all --no-legend --plain 'signalbot*' 2>/dev/null | awk '{print $1}'); do
  systemctl status "$u" --no-pager -l > "$CB/units/status_$u.txt" 2>&1 || true
done
cp /etc/systemd/system/signalbot*.service /etc/systemd/system/signalbot*.timer "$CB/units/" 2>/dev/null || true
docker ps -a > "$CB/docker_ps.txt" 2>&1 || true
docker system df -v > "$CB/docker_df.txt" 2>&1 || true
crontab -l > "$CB/crontab_root.txt" 2>&1 || true
tar czf "$CB/state_snapshot.tar.gz" -C "$CB" state.txt systemd_timers.txt systemd_units.txt units docker_ps.txt docker_df.txt crontab_root.txt
rm -rf "$CB/units" "$CB"/state.txt "$CB"/systemd_*.txt "$CB"/docker_*.txt "$CB"/crontab_root.txt
enc "$CB/state_snapshot.tar.gz"   # status output can carry journal lines; encrypted like everything else

# ---------- 1. row counts (aggregate, plaintext; used by the restore verification) ----------
log "1. row counts"
: > "$CB/COUNTS.txt"
for t in $RESULT_TABLES $PII_TABLES klines_1m open_interest funding_rate beta_state_tape; do
  if table_exists "$t"; then echo "$t $(psqlq "SELECT count(*) FROM public.$t")" >> "$CB/COUNTS.txt"; else echo "$t ABSENT" >> "$CB/COUNTS.txt"; fi
done
echo "klines_1m_min_max $(psqlq "SELECT coalesce(min(open_time)::text,'') || ' ' || coalesce(max(open_time)::text,'') FROM klines_1m" 2>/dev/null || echo unknown)" >> "$CB/COUNTS.txt"

# ---------- 2. logical dumps ----------
log "2a. pg_dump plain"
pg pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges | gzip -c > "$CB/db_plain.sql.gz.partial"
gzip -t "$CB/db_plain.sql.gz.partial" || fail "plain dump gzip test failed"
[ "$(stat -c %s "$CB/db_plain.sql.gz.partial")" -gt 1048576 ] || fail "plain dump suspiciously small"
mv "$CB/db_plain.sql.gz.partial" "$CB/db_plain.sql.gz"; enc "$CB/db_plain.sql.gz"
log "2b. pg_dump custom"
pg pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges -Fc > "$CB/db_custom.dump.partial"
docker exec -i "$CONTAINER" pg_restore --list < "$CB/db_custom.dump.partial" > /dev/null || fail "custom dump TOC unreadable"
mv "$CB/db_custom.dump.partial" "$CB/db_custom.dump"; enc "$CB/db_custom.dump"
log "2c. globals"
pg pg_dumpall -U "$POSTGRES_USER" --globals-only > "$CB/db_globals.sql" || log "globals dump failed (non-superuser?); continuing without it"
[ -s "$CB/db_globals.sql" ] && enc "$CB/db_globals.sql" || rm -f "$CB/db_globals.sql"

# ---------- 3. CSV exports ----------
log "3. CSV exports"
for t in $RESULT_TABLES; do
  table_exists "$t" || continue
  pg psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "\\copy (SELECT * FROM public.$t) TO STDOUT CSV HEADER" > "$CB/csv_results/$t.csv" || fail "csv export failed: $t"
done
for t in $PII_TABLES; do
  table_exists "$t" || continue
  pg psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "\\copy (SELECT * FROM public.$t) TO STDOUT CSV HEADER" > "$CB/csv_participants/$t.csv" || fail "csv export failed: $t"
done
tar czf "$CB/csv_results.tar.gz" -C "$CB" csv_results && rm -rf "$CB/csv_results"; enc "$CB/csv_results.tar.gz"
tar czf "$CB/csv_participants.tar.gz" -C "$CB" csv_participants && rm -rf "$CB/csv_participants"; enc "$CB/csv_participants.tar.gz"

# ---------- 4. volumes (physical copies; inconsistent while PostgreSQL runs — complements the dumps) ----------
if [ "$VOLUMES" = 1 ]; then
  log "4. volumes"
  for v in "$PG_VOLUME" "$REDIS_VOLUME"; do
    docker volume inspect "$v" >/dev/null 2>&1 || { log "volume $v absent, skipped"; continue; }
    docker run --rm -v "$v:/src:ro" -v "$CB:/dst" alpine:3.20 tar czf "/dst/volume_$v.tar.gz.partial" -C /src . || fail "volume copy failed: $v"
    gzip -t "$CB/volume_$v.tar.gz.partial" || fail "volume archive corrupt: $v"
    mv "$CB/volume_$v.tar.gz.partial" "$CB/volume_$v.tar.gz"; enc "$CB/volume_$v.tar.gz"
  done
fi

# ---------- 5. secrets and configuration ----------
log "5. secrets"
tar czf "$CB/secrets.tar.gz" --ignore-failed-read "$ENV_FILE" "$SIGNALBOT_DIR/.env.beta-feeds" /etc/signalbot 2>/dev/null || true
enc "$CB/secrets.tar.gz"

# ---------- 6. journals ----------
log "6. journals"
journalctl -u 'signalbot*' -o export 2>/dev/null | gzip -c > "$CB/journal_signalbot.export.gz" || true
journalctl -u 'signalbot*' --no-pager 2>/dev/null | gzip -c > "$CB/journal_signalbot.txt.gz" || true
enc "$CB/journal_signalbot.export.gz"; enc "$CB/journal_signalbot.txt.gz"

# ---------- 7. artifacts outside git ----------
log "7. artifacts"
tar czf "$CB/artifacts.tar.gz" --ignore-failed-read -C "$SIGNALBOT_DIR" artifacts exports data logs backups 2>/dev/null || true
enc "$CB/artifacts.tar.gz"

# ---------- 8. manifest and closing checks ----------
log "8. manifest"
cat > "$CB/README.txt" <<EOF
Pulsy closure backup, staged $STAMP on the VPS by scripts/closure/closure_backup.sh.
Every *.gpg file is gpg symmetric AES-256; the passphrase is held by the owner only.
Contents: state snapshot, pg_dump plain and custom, globals, CSV exports (results; participants), volumes (if present),
secrets, journald export, artifacts. COUNTS.txt holds aggregate row counts for the restore verification.
Decrypt: gpg --batch --pinentry-mode loopback --passphrase-file <file> --decrypt <name>.gpg > <name>
Verify: sha256sum -c MANIFEST.sha256
EOF
( cd "$CB" && find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256 )
leftover=$(find "$CB" -type f ! -name '*.gpg' ! -name MANIFEST.sha256 ! -name COUNTS.txt ! -name README.txt | wc -l)
[ "$leftover" = 0 ] || fail "unencrypted files remain in $CB"
find "$CB" -name '*.partial' | grep -q . && fail "partial files remain" || true
chmod 700 "$CB"; chmod 600 "$CB"/*
log "done: $CB"; ls -la "$CB"
log "next: sha256sum -c MANIFEST.sha256; rclone copy --checksum \"$CB\" <remote>:closure_$STAMP/ ; rclone check \"$CB\" <remote>:closure_$STAMP/ ; copy to owner's disk; then scripts/closure/closure_restore_verify.sh on a clean machine"
