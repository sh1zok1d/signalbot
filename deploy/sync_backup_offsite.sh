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

# ---- canonical backup-filename validator -----------------------------
# ONE rule, reused everywhere a name is asked to participate in backup
# semantics (the local upload candidate, weekly/monthly representative
# discovery, retention candidate selection): a name is a recognized
# backup object only if it is EXACTLY "btcbot_YYYYMMDDTHHMMSSZ.sql.gz"
# (all-numeric fields, no more/fewer characters) AND its embedded
# timestamp is a REAL UTC calendar date/time. Both are required -- digit
# SHAPE alone (e.g. "btcbot_20260819T999999Z.sql.gz", a nonexistent time)
# or date shape alone (e.g. "btcbot_20260230T030000Z.sql.gz", a
# nonexistent date) is not enough. Never prints anything -- callers that
# want a loud, fatal error (the local dump gate) construct their own
# message; callers that use this purely to recognize/filter remote
# objects (weekly/monthly dedup, retention) silently skip on failure.
#
# Verification is a strict, self-checking round-trip: parse the extracted
# Y-M-D H:M:S as UTC, format back to the exact same "%Y%m%dT%H%M%SZ"
# shape, and require byte-for-byte equality with the original timestamp.
# Returns 0 (valid) or 1 (invalid, for any reason) -- never aborts the
# script itself (no `set -e` interaction to worry about at call sites).
_valid_backup_filename() {
  local name="$1"
  [[ "$name" =~ ^btcbot_([0-9]{4})([0-9]{2})([0-9]{2})T([0-9]{2})([0-9]{2})([0-9]{2})Z\.sql\.gz$ ]] || return 1
  local ts y mo d h mi s formatted
  ts="${name#btcbot_}"; ts="${ts%.sql.gz}"   # e.g. "20260819T031500Z"
  y="${BASH_REMATCH[1]}"; mo="${BASH_REMATCH[2]}"; d="${BASH_REMATCH[3]}"
  h="${BASH_REMATCH[4]}"; mi="${BASH_REMATCH[5]}"; s="${BASH_REMATCH[6]}"
  formatted="$(date -u -d "${y}-${mo}-${d} ${h}:${mi}:${s}" +%Y%m%dT%H%M%SZ 2>/dev/null)" || return 1
  [ "$formatted" = "$ts" ]
}

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
# Reject every root-equivalent spelling, not just a literally empty path:
# "gdrive:", "gdrive:/", "gdrive://", "gdrive:///" all denote the remote's
# root once slashes are disregarded. Stripping EVERY '/' from the path
# component and checking what's left catches all of them in one test,
# while still allowing a real (even slash-prefixed) path like
# "gdrive:/signalbot-backups" or "gdrive:a/b" to pass, since those retain
# a non-slash character. This check runs BEFORE any trailing-slash
# normalization below, so normalization can never turn a path that passed
# validation into a root-equivalent form afterward.
_remote_path_no_slashes="${_remote_path//\//}"
if [ -z "$_remote_path_no_slashes" ]; then
  echo "[offsite] ERROR: SIGNALBOT_BACKUP_REMOTE must include a real, non-root path" \
       "after the colon (got '${REMOTE}') — refusing to operate against a remote root" >&2
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
# Newest completed dump = highest filesystem mtime among
# BACKUP_DIR/btcbot_*.sql.gz (primary; same criterion `ls -1t` used). On an
# exact mtime tie, break deterministically by filename descending: the
# fixed-width btcbot_YYYYMMDDTHHMMSSZ.sql.gz form is lexicographically
# chronological (same rule remote retention uses below). Never rely on
# `ls -1t` filesystem-dependent tie order among equal mtimes.
dump="${1:-}"
if [ -z "$dump" ]; then
  dump="$(
    find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'btcbot_*.sql.gz' \
      -printf '%T@\t%f\t%p\n' 2>/dev/null \
      | LC_ALL=C sort -t $'\t' -k1,1nr -k2,2r \
      | head -n 1 \
      | cut -f3-
  )"
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

# ---- 2b. canonical filename + calendar/time validation, BEFORE ANY
#          rclone invocation (not even `rclone mkdir`) -- a malformed
#          local dump must never create so much as an empty tier
#          directory on the remote. deploy/backup.sh always emits
#          `date -u +%Y%m%dT%H%M%SZ`, so this is the exact producer
#          format, not merely field WIDTH: a `?`-wildcard shape check (the
#          original approach) accepts non-numeric junk like
#          "btcbot_abcdefghTijklmnZ.sql.gz" as long as the widths line up
#          -- that junk would then reach `rclone copyto` for daily/ before
#          a LATER `date` call ever caught it. Uses the same
#          `_valid_backup_filename` helper the remote-side checks below
#          reuse, so there is exactly one definition of "valid" -- this is
#          the only call site that turns a failure into a loud, fatal
#          error (before any rclone invocation); the remote-side call
#          sites below use it purely to recognize/skip foreign objects. ----
if ! _valid_backup_filename "$fname"; then
  echo "[offsite] ERROR: dump filename is not a valid" \
       "btcbot_YYYYMMDDTHHMMSSZ.sql.gz timestamp: ${fname}" >&2
  exit 1
fi

# ---- helpers -----------------------------------------------------------
# btcbot_YYYYMMDDTHHMMSSZ.sql.gz -> YYYYMMDD (fixed-width, so lexicographic
# order over the full filename IS chronological order — no date parsing
# needed for sorting/retention). Only ever called on a name that has
# already passed `_valid_backup_filename`.
_ymd_of() { local n="$1"; n="${n#btcbot_}"; echo "${n:0:8}"; }

_iso_week_of() {  # -> "GGGG-VV" ISO week-based year+week, from YYYYMMDD
  local ymd="$1"
  date -u -d "${ymd:0:4}-${ymd:4:2}-${ymd:6:2}" +%G-%V
}

_month_of() {  # -> "YYYY-MM", from YYYYMMDD
  local ymd="$1"
  echo "${ymd:0:4}-${ymd:4:2}"
}

# List filenames present under "${REMOTE}/<tier>/". Does NOT swallow
# failures: an auth/network/permission/backend error from `rclone lsf` must
# never be silently reinterpreted as "tier has no objects" -- that would let
# a real listing failure masquerade as an empty remote and let the job
# report success. `_ensure_tier_dirs` (below) creates all three tier
# directories up front specifically so "the directory doesn't exist yet" is
# never a reason `lsf` needs to fail here -- by the time this is called, a
# non-zero exit from `rclone lsf` is a REAL failure, and it is left to
# propagate (via `set -e`) to whichever caller invoked this in a plain
# assignment, aborting the whole run non-zero. No caller may treat a failed
# call as an empty list.
_list_tier() {
  local tier="$1"
  rclone lsf "${REMOTE}/${tier}/"
}

# Create the three tier directories if they don't already exist yet (e.g.
# the very first run against a fresh remote). Idempotent -- a no-op against
# an already-existing directory on every provider rclone supports. This
# exists so a later `_list_tier` failure can be trusted to mean a REAL
# error (auth/network/permission/backend), never "directory not found yet".
_ensure_tier_dirs() {
  local tier
  for tier in daily weekly monthly; do
    if ! rclone mkdir "${REMOTE}/${tier}"; then
      echo "[offsite] ERROR: failed to ensure remote directory ${REMOTE}/${tier} exists; job failed" >&2
      exit 1
    fi
  done
}
_ensure_tier_dirs

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
    # Full canonical validity (shape AND real calendar/time), via the
    # SAME helper the local dump gate above uses -- not merely a digit-
    # width shape check. That distinction is exactly what closes the
    # "invalid remotes suppress tier uploads" gap: `_iso_week_of` only
    # ever examined the DATE portion (never HHMMSS), so a remote object
    # with an impossible TIME (e.g. "...T999999Z...") previously computed
    # a normal-looking ISO week and could silently masquerade as an
    # already-present representative, suppressing a genuinely valid
    # upload; `_month_of` performed no date/time validation at all. A
    # remote object failing this check is simply skipped -- it is never
    # treated as a same-period representative, and it is never deleted.
    _valid_backup_filename "$name" || continue
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
  local names valid_names="" sorted_desc i=0 name
  names="$(_list_tier "$tier")"
  [ -n "$names" ] || return 0
  # Filter to fully valid backup objects only (shape AND real calendar/
  # time -- the same `_valid_backup_filename` helper used everywhere
  # else), THEN sort descending (lexicographic == chronological for this
  # fixed-width timestamp format). A shape-only filter (the previous
  # `grep -E '^btcbot_[0-9]{8}T[0-9]{6}Z\.sql\.gz$'`) would let a digit-
  # shaped-but-impossible timestamp (e.g. a malformed future-looking
  # object) participate in this ordering and consume one of the `keep`
  # retention slots, displacing a genuinely valid backup. An excluded
  # object is simply never counted -- it is NOT deleted by this pass.
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    _valid_backup_filename "$name" || continue
    valid_names+="${name}"$'\n'
  done <<< "$names"
  [ -n "$valid_names" ] || return 0
  sorted_desc="$(printf '%s' "$valid_names" | sort -r)"
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
