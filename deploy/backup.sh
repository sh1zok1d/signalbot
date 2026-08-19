#!/usr/bin/env bash
# PostgreSQL/TimescaleDB backup for the BTC Signal Bot.
#
# Runs pg_dump inside the running container and writes a gzip'd plain-SQL dump.
# Intended to be run by an ADMIN (a user with docker access) — NOT by the
# unprivileged signalbot service user. Schedule via cron, e.g. daily:
#   15 3 * * *  /opt/signalbot/deploy/backup.sh >> /var/log/signalbot-backup.log 2>&1
#
# IMPORTANT: these local backups protect against DB corruption, not against
# losing the VPS. Periodically copy the backups/ directory OFF the VPS
# (scp/rsync/object storage).
set -euo pipefail
umask 077   # backups are private (contain all market data + schema)

CONTAINER="${BTCBOT_PG_CONTAINER:-btcbot_timescaledb}"
DB="${POSTGRES_DB:-btcbot}"
DB_USER="${POSTGRES_USER:-btcbot}"
BACKUP_DIR="${BACKUP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backups}"
RETENTION="${BACKUP_RETENTION:-7}"   # keep this many most-recent dumps

mkdir -p "$BACKUP_DIR"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="${BACKUP_DIR}/btcbot_${ts}.sql.gz"
tmp="${out}.partial"

echo "[backup] dumping ${DB} from container ${CONTAINER} -> ${out}"
# pg_dump exit status propagates through the pipe (pipefail); gzip to a temp file
# first so a failed/partial dump never replaces a good backup.
if docker exec "$CONTAINER" pg_dump -U "$DB_USER" -d "$DB" --no-owner --no-privileges \
     | gzip -c > "$tmp"; then
  # Sanity: non-empty and gzip-valid.
  if [ ! -s "$tmp" ] || ! gzip -t "$tmp" 2>/dev/null; then
    echo "[backup] ERROR: dump is empty or not a valid gzip; keeping .partial for inspection" >&2
    exit 1
  fi
  mv "$tmp" "$out"
  echo "[backup] OK: $(du -h "$out" | cut -f1) ${out}"
else
  echo "[backup] ERROR: pg_dump failed; removing partial" >&2
  rm -f "$tmp"
  exit 1
fi

# Retention: keep the newest $RETENTION dumps, delete older ones.
mapfile -t old < <(ls -1t "${BACKUP_DIR}"/btcbot_*.sql.gz 2>/dev/null | tail -n +"$((RETENTION + 1))")
if [ "${#old[@]}" -gt 0 ]; then
  echo "[backup] pruning ${#old[@]} old dump(s) beyond retention=${RETENTION}"
  rm -f "${old[@]}"
fi
echo "[backup] done."
