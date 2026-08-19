#!/usr/bin/env bash
# Off-site sync of a completed local backup (produced by deploy/backup.sh) to a
# generic rclone remote, with daily/weekly/monthly remote retention.
#
# This protects against total VPS/provider loss: deploy/backup.sh's local
# backups/ directory lives on the SAME disk as the live database, so losing
# the VPS loses both. At least one copy must live outside that failure
# domain.
#
# Depends ONLY on `rclone` and an operator-configured remote — never a
# specific provider. Google Drive is the documented example
# (docs/DATA_DURABILITY_RUNBOOK.md), but any rclone-compatible remote
# (Backblaze B2, S3, ...) works without touching this script.
#
# Intended to run right after deploy/backup.sh, by the same ADMIN (docker/DB
# access is NOT required here — this script only reads a local file and talks
# to rclone), e.g. as one systemd oneshot (deploy/signalbot-backup.service).
#
# Usage:
#   deploy/sync_backup_offsite.sh [dump.sql.gz]
#     # default: newest completed (non-.partial) local dump in BACKUP_DIR
#
# Configuration (env):
#   SIGNALBOT_BACKUP_REMOTE            rclone remote + path, e.g.
#                                       "gdrive:signalbot-backups". REQUIRED.
#                                       Must be "name:non-empty/path" — never
#                                       a bare remote name — so retention
#                                       pruning can never touch a remote root.
#   SIGNALBOT_BACKUP_DAILY_RETENTION   keep newest N in <remote>/daily/   (30)
#   SIGNALBOT_BACKUP_WEEKLY_RETENTION  keep newest N in <remote>/weekly/  (12)
#   SIGNALBOT_BACKUP_MONTHLY_RETENTION keep newest N in <remote>/monthly/ (12)
#   BACKUP_DIR                         same var deploy/backup.sh uses.
#
# The rclone remote/credentials themselves live in an operator-managed rclone
# config OUTSIDE this repository (see docs/DATA_DURABILITY_RUNBOOK.md) — this
# script never reads, writes, or logs a token/secret.
set -euo pipefail
umask 077

BACKUP_DIR="${BACKUP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backups}"
REMOTE="${SIGNALBOT_BACKUP_REMOTE:-}"
DAILY_RETENTION="${SIGNALBOT_BACKUP_DAILY_RETENTION:-30}"
WEEKLY_RETENTION="${SIGNALBOT_BACKUP_WEEKLY_RETENTION:-12}"
MONTHLY_RETENTION="${SIGNALBOT_BACKUP_MONTHLY_RETENTION:-12}"

require_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "[offsite] ERROR: missing required command: $1" >&2; exit 1; }; }
require_cmd rclone
require_cmd date

# ---- 1. remote configuration: required, and must not be an ambiguous root ----
# A bare "name:" or "name" (no path component) would make retention pruning
# operate on the remote's root — refuse that outright, fail closed.
if [ -z "$REMOTE" ]; then
  echo "[offsite] ERROR: SIGNALBOT_BACKUP_REMOTE is not set; refusing to sync" >&2
  exit 1
fi
case "$REMOTE" in
  *:*) : ;;
  *) echo "[offsite] ERROR: SIGNALBOT_BACKUP_REMOTE must be 'remote:path' (got '${REMOTE}')" >&2; exit 1 ;;
esac
_remote_path="${REMOTE#*:}"
if [ -z "$_remote_path" ]; then
  echo "[offsite] ERROR: SIGNALBOT_BACKUP_REMOTE must include a non-empty path" \
       "after the colon — refusing to operate against a remote root" >&2
  exit 1
fi
# Strip a trailing slash so "${REMOTE}/daily" never becomes "...//daily".
REMOTE="${REMOTE%/}"

for retention_var_name in DAILY_RETENTION WEEKLY_RETENTION MONTHLY_RETENTION; do
  val="${!retention_var_name}"
  case "$val" in
    ''|*[!0-9]*|0)
      echo "[offsite] ERROR: SIGNALBOT_BACKUP_${retention_var_name} must be a positive integer (got '${val}')" >&2
      exit 1
      ;;
  esac
done

# ---- 2. select + validate the local dump (never a .partial, never empty/corrupt) ----
dump="${1:-}"
if [ -z "$dump" ]; then
  dump="$(ls -1t "${BACKUP_DIR}"/btcbot_*.sql.gz 2>/dev/null | head -1 || true)"
fi
[ -n "$dump" ] || { echo "[offsite] ERROR: no completed local backup found in ${BACKUP_DIR}" >&2; exit 1; }
[ -f "$dump" ] || { echo "[offsite] ERROR: dump not found: ${dump}" >&2; exit 1; }
case "$dump" in
  *.partial) echo "[offsite] ERROR: refusing to sync a .partial (incomplete) dump: ${dump}" >&2; exit 1 ;;
esac
[ -s "$dump" ] || { echo "[offsite] ERROR: dump is empty: ${dump}" >&2; exit 1; }
gzip -t "$dump" 2>/dev/null || { echo "[offsite] ERROR: not a valid gzip: ${dump}" >&2; exit 1; }

fname="$(basename "$dump")"
echo "[offsite] using local backup: ${fname}"

# Only filenames of the expected shape carry a chronologically-sortable,
# unambiguous timestamp; anything else is never something this script
# uploads, lists as a tier representative, or deletes.
case "$fname" in
  btcbot_????????T??????Z.sql.gz) : ;;
  *) echo "[offsite] ERROR: unexpected dump filename shape: ${fname}" >&2; exit 1 ;;
esac

# ---- helpers -----------------------------------------------------------
# btcbot_YYYYMMDDTHHMMSSZ.sql.gz -> YYYYMMDD (fixed-width, so lexicographic
# order over the full filename IS chronological order — no date parsing
# needed for sorting/retention).
_ymd_of() { local n="$1"; n="${n#btcbot_}"; echo "${n:0:8}"; }

_iso_week_of() {  # -> "GGGG-VV" ISO week-based year+week, from YYYYMMDD
  local ymd="$1"
  date -u -d "${ymd:0:4}-${ymd:4:2}-${ymd:6:2}" +%G-%V
}

_month_of() {  # -> "YYYY-MM", from YYYYMMDD
  local ymd="$1"
  echo "${ymd:0:4}-${ymd:4:2}"
}

# List filenames present under "${REMOTE}/<tier>/" — tolerate a not-yet-
# existing prefix (empty listing) without treating that as an error.
_list_tier() {
  local tier="$1"
  rclone lsf "${REMOTE}/${tier}/" 2>/dev/null || true
}

# ---- 3. DAILY: every successful backup may participate ----
echo "[offsite] uploading -> ${REMOTE}/daily/${fname}"
if ! rclone copyto "$dump" "${REMOTE}/daily/${fname}"; then
  echo "[offsite] ERROR: rclone upload to daily/ failed; local backup is untouched, job failed" >&2
  exit 1
fi
echo "[offsite] OK: daily/${fname}"

# ---- 4. WEEKLY / MONTHLY: at most one representative per UTC period ----
this_ymd="$(_ymd_of "$fname")"
this_week="$(_iso_week_of "$this_ymd")"
this_month="$(_month_of "$this_ymd")"

_sync_period_tier() {
  local tier="$1" this_key="$2" keyfn="$3"
  local existing name candidate_ymd candidate_key found=0
  existing="$(_list_tier "$tier")"
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    case "$name" in btcbot_????????T??????Z.sql.gz) : ;; *) continue ;; esac
    candidate_ymd="$(_ymd_of "$name")"
    candidate_key="$("$keyfn" "$candidate_ymd")"
    if [ "$candidate_key" = "$this_key" ]; then
      found=1
      break
    fi
  done <<< "$existing"
  if [ "$found" -eq 1 ]; then
    echo "[offsite] ${tier}/: representative for ${this_key} already present; skipping"
    return 0
  fi
  echo "[offsite] uploading -> ${REMOTE}/${tier}/${fname} (new ${this_key} representative)"
  if ! rclone copyto "$dump" "${REMOTE}/${tier}/${fname}"; then
    echo "[offsite] ERROR: rclone upload to ${tier}/ failed" >&2
    exit 1
  fi
  echo "[offsite] OK: ${tier}/${fname}"
}

_sync_period_tier weekly "$this_week" _iso_week_of
_sync_period_tier monthly "$this_month" _month_of

# ---- 5. retention: keep newest N per tier, delete only excess, only inside
#         the configured tier path (never a bulk/root delete). A pruning
#         failure aborts (set -e) WITHOUT having deleted the object this run
#         just uploaded (it is always among the newest, so it is never a
#         pruning candidate) -- "best effort success" is never masked. ----
_prune_tier() {
  local tier="$1" keep="$2"
  local names sorted_desc i=0 name
  names="$(_list_tier "$tier")"
  [ -n "$names" ] || return 0
  # Filter to expected-shape names only, then sort descending (lexicographic
  # == chronological for this fixed-width timestamp format).
  sorted_desc="$(printf '%s\n' "$names" | grep -E '^btcbot_[0-9]{8}T[0-9]{6}Z\.sql\.gz$' | sort -r)"
  [ -n "$sorted_desc" ] || return 0
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    i=$((i + 1))
    if [ "$i" -gt "$keep" ]; then
      echo "[offsite] pruning ${tier}/${name} (beyond retention=${keep})"
      if ! rclone deletefile "${REMOTE}/${tier}/${name}"; then
        echo "[offsite] ERROR: failed to prune ${tier}/${name}; job failed (nothing already" \
             "uploaded was deleted to mask this)" >&2
        exit 1
      fi
    fi
  done <<< "$sorted_desc"
}

_prune_tier daily "$DAILY_RETENTION"
_prune_tier weekly "$WEEKLY_RETENTION"
_prune_tier monthly "$MONTHLY_RETENTION"

echo "[offsite] done."
