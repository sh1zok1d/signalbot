#!/usr/bin/env bash
# Restore a gzip'd pg_dump produced by deploy/backup.sh.
#
# SAFETY: this never silently overwrites the live database. By default it
# restores into a NEW database (default name derived from the dump), refusing if
# that database already exists. Restoring OVER the live DB requires both
# --force-live AND typing an explicit confirmation phrase.
#
# TimescaleDB requires wrapping a plain-SQL restore in
# timescaledb_pre_restore()/post_restore(); this script does that.
#
# Run by an ADMIN (docker access), NOT the signalbot service user.
#
# Usage:
#   deploy/restore.sh <dump.sql.gz> [target_db]         # restore into new DB
#   deploy/restore.sh --force-live <dump.sql.gz>        # restore OVER live DB (guarded)
#   deploy/restore.sh --self-test [dump.sql.gz]         # restore into throwaway DB, verify, drop
set -euo pipefail

CONTAINER="${BTCBOT_PG_CONTAINER:-btcbot_timescaledb}"
DB_USER="${POSTGRES_USER:-btcbot}"
LIVE_DB="${POSTGRES_DB:-btcbot}"
BACKUP_DIR="${BACKUP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backups}"

psql_admin() { docker exec -i "$CONTAINER" psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 "$@"; }
psql_db()    { docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$1" -v ON_ERROR_STOP=1 "${@:2}"; }

db_exists() { [ "$(psql_admin -tAc "SELECT 1 FROM pg_database WHERE datname='$1'")" = "1" ]; }

do_restore() {
  local dump=$1 target=$2
  [ -f "$dump" ] || { echo "restore: dump not found: $dump" >&2; exit 1; }
  gzip -t "$dump" 2>/dev/null || { echo "restore: not a valid gzip: $dump" >&2; exit 1; }

  echo "[restore] target DB: ${target}"
  psql_admin -c "CREATE DATABASE \"${target}\";"
  psql_db "$target" -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
  psql_db "$target" -c "SELECT timescaledb_pre_restore();"
  echo "[restore] loading ${dump} ..."
  gunzip -c "$dump" | docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$target" -v ON_ERROR_STOP=1 >/dev/null
  psql_db "$target" -c "SELECT timescaledb_post_restore();"
  echo "[restore] restored into ${target}"
}

# ---- self-test: restore latest (or given) dump into a throwaway DB, verify, drop ----
if [ "${1:-}" = "--self-test" ]; then
  dump="${2:-$(ls -1t "${BACKUP_DIR}"/btcbot_*.sql.gz 2>/dev/null | head -1 || true)}"
  [ -n "$dump" ] || { echo "self-test: no dump found in ${BACKUP_DIR}" >&2; exit 1; }
  test_db="btcbot_restore_selftest_$(date -u +%Y%m%d%H%M%S)"
  echo "[self-test] using dump: ${dump}"
  cleanup() { psql_admin -c "DROP DATABASE IF EXISTS \"${test_db}\";" >/dev/null 2>&1 || true; }
  trap cleanup EXIT
  do_restore "$dump" "$test_db"
  n=$(psql_db "$test_db" -tAc "SELECT count(*) FROM klines_1m" || echo 0)
  echo "[self-test] klines_1m rows in restored copy: ${n}"
  if [ "${n:-0}" -gt 0 ]; then
    echo "SELF_TEST_RESULT: PASS"
  else
    echo "SELF_TEST_RESULT: FAIL (no rows restored)"; exit 1
  fi
  exit 0
fi

# ---- force-live: restore OVER the working DB (double-guarded) ----
if [ "${1:-}" = "--force-live" ]; then
  dump="${2:?usage: restore.sh --force-live <dump.sql.gz>}"
  echo "!! WARNING: you are about to DROP and REPLACE the LIVE database '${LIVE_DB}'."
  echo "!! All current data in '${LIVE_DB}' will be lost and replaced by ${dump}."
  echo "!! Stop the signalbot service first (sudo systemctl stop signalbot)."
  read -r -p "Type exactly 'RESTORE-OVER-LIVE' to proceed: " confirm
  [ "$confirm" = "RESTORE-OVER-LIVE" ] || { echo "aborted."; exit 1; }
  psql_admin -c "DROP DATABASE IF EXISTS \"${LIVE_DB}\";"
  do_restore "$dump" "$LIVE_DB"
  exit 0
fi

# ---- default: restore into a NEW database (never the live one) ----
dump="${1:?usage: restore.sh <dump.sql.gz> [target_db]}"
target="${2:-btcbot_restore_$(basename "$dump" .sql.gz | sed 's/^btcbot_//')}"
if [ "$target" = "$LIVE_DB" ]; then
  echo "refusing to restore into the live DB '${LIVE_DB}' without --force-live" >&2
  exit 1
fi
if db_exists "$target"; then
  echo "target DB '${target}' already exists — choose another name or drop it first" >&2
  exit 1
fi
do_restore "$dump" "$target"
echo "[restore] done. Inspect with: docker exec -it ${CONTAINER} psql -U ${DB_USER} -d ${target}"
