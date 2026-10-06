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
#
# Private beta (backlog A6): the self-test also checks that every beta_* table the current code
# defines came back, that the current beta schema applies to the restored copy, and that the
# research feed role's grants apply to it. A --force-live restore re-grants that role, because the
# dump carries no privileges (deploy/backup.sh uses --no-owner --no-privileges).
set -euo pipefail

CONTAINER="${BTCBOT_PG_CONTAINER:-btcbot_timescaledb}"
DB_USER="${POSTGRES_USER:-btcbot}"
LIVE_DB="${POSTGRES_DB:-btcbot}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${ROOT}/backups}"
BETA_SCHEMA="${ROOT}/storage/beta_v0_schema.sql"
FEEDS_ROLE_SQL="${ROOT}/deploy/beta_feeds_role.sql"
FEEDS_ROLE=signalbot_beta_feeds
# the tables deploy/beta_feeds_role.sql grants on (the same list as deploy/install_beta_feeds_role.sh)
FEED_TABLES=(beta_feed_metrics_5m beta_feed_dvol_1h beta_feed_depth beta_feed_spot_5m beta_feed_stress_hours
             beta_runtime_health beta_hist_oi_5m)

psql_admin() { docker exec -i "$CONTAINER" psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 "$@"; }
psql_db()    { docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$1" -v ON_ERROR_STOP=1 "${@:2}"; }

db_exists() { [ "$(psql_admin -tAc "SELECT 1 FROM pg_database WHERE datname='$1'")" = "1" ]; }

# the beta tables the current code defines, one per line
beta_expected_tables() {
  grep -oE '^CREATE TABLE IF NOT EXISTS beta_[a-z0-9_]+' "${1:-$BETA_SCHEMA}" | awk '{print $6}' | sort -u
}

# SQL that lists those of the given tables that do not exist (no row: all present)
missing_tables_sql() {
  local list
  list=$(printf "'%s'," "$@")
  echo "SELECT t FROM unnest(ARRAY[${list%,}]::text[]) AS t WHERE to_regclass('public.' || t) IS NULL ORDER BY t"
}

# re-apply the research feed role's grants in <db>; the role is cluster-level and survives a restore,
# its grants do not. Never creates the role: a host without the feed units has nothing to re-grant.
regrant_feeds_role() {
  local db=$1 missing
  if [ "$(psql_admin -tAc "SELECT 1 FROM pg_roles WHERE rolname='${FEEDS_ROLE}'")" != "1" ]; then
    echo "[restore] research feed role ${FEEDS_ROLE} not installed: nothing to re-grant"
    return 0
  fi
  missing=$(psql_db "$db" -tA -c "$(missing_tables_sql "${FEED_TABLES[@]}")")
  if [ -n "$missing" ]; then
    echo "[restore] feed tables missing in ${db}: $(echo $missing). Apply the beta schema with the core role" \
         "(start signalbot-beta-bot.service), then run deploy/install_beta_feeds_role.sh" >&2
    return 1
  fi
  psql_db "$db" -q < "$FEEDS_ROLE_SQL" >/dev/null
  echo "[restore] research feed role ${FEEDS_ROLE}: grants re-applied in ${db}"
}

# the beta part of the self-test: every beta table back, the current schema applies, the feed grants apply
beta_self_test() {
  local db=$1 missing t
  local expected
  mapfile -t expected < <(beta_expected_tables)
  missing=$(psql_db "$db" -tA -c "$(missing_tables_sql "${expected[@]}")")
  if [ -n "$missing" ]; then
    echo "[self-test] beta tables missing from the restored copy: $(echo $missing)" \
         "(a dump older than the deployed code fails here too: re-run after the next backup)"
    return 1
  fi
  echo "[self-test] all ${#expected[@]} beta tables present"
  psql_db "$db" -q -1 < "$BETA_SCHEMA" >/dev/null       # one transaction, as the code applies it
  echo "[self-test] the current beta schema applies to the restored copy"
  for t in beta_users beta_allowlist beta_notification_deliveries beta_user_activity beta_market_alerts \
           beta_claims; do
    echo "[self-test] ${t} rows: $(psql_db "$db" -tAc "SELECT count(*) FROM ${t}")"
  done
  regrant_feeds_role "$db"
}

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
  if [ "${n:-0}" -le 0 ]; then
    echo "SELF_TEST_RESULT: FAIL (no rows restored)"; exit 1
  fi
  if ! beta_self_test "$test_db"; then
    echo "SELF_TEST_RESULT: FAIL (beta tables or grants)"; exit 1
  fi
  echo "SELF_TEST_RESULT: PASS"
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
  regrant_feeds_role "$LIVE_DB" || echo "[restore] WARNING: feed role grants NOT re-applied (see above)" >&2
  echo "[restore] next: sudo deploy/install_beta_feeds_role.sh (verifies the feed login), then start services"
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
