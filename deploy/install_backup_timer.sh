#!/usr/bin/env bash
set -euo pipefail

# Install the Signalbot database backup (local + off-site) daily oneshot +
# timer, and the monthly restore self-test oneshot + timer, following the
# existing VPS deployment contract (see install_shadow_timer.sh/
# install_telegram_timer.sh). DEFAULT behavior is install + validate ONLY (no
# enable, no start). Pass --enable-now to explicitly activate BOTH timers.
#
# Usage:
#   sudo ./deploy/install_backup_timer.sh                # install + validate only
#   sudo ./deploy/install_backup_timer.sh --enable-now   # install + enable both timers
#
# This script installs deployment artifacts. It never runs a backup, a
# restore, or `docker`, never touches Docker itself, never modifies the
# signalbot user/group or .env, and never stops or restarts any other
# Signalbot service. It does NOT create /etc/signalbot/backup.env or install
# rclone/an rclone remote — those are separate, explicit operator actions
# documented in docs/DATA_DURABILITY_RUNBOOK.md (this installer only checks
# that /etc/signalbot/backup.env already exists before installing, since the
# backup service's EnvironmentFile= requires it to be present at start time).

APP_DIR=/opt/signalbot
UNIT_DIR=/etc/systemd/system
BACKUP_ENV_FILE=/etc/signalbot/backup.env
# Must match signalbot-backup.service's Environment=RCLONE_CONFIG=... exactly
# -- deliberately NOT rclone's interactive default (~/.config/rclone/
# rclone.conf under /root), which ProtectHome=true makes unreachable to that
# service. See docs/DATA_DURABILITY_RUNBOOK.md.
RCLONE_CONFIG_FILE=/etc/signalbot/rclone.conf

UNITS=(
  signalbot-backup.service
  signalbot-backup.timer
  signalbot-backup-verify.service
  signalbot-backup-verify.timer
)
TIMERS=(signalbot-backup.timer signalbot-backup-verify.timer)

ENABLE_NOW=0
case "${1:-}" in
  "")            ENABLE_NOW=0 ;;
  --enable-now)  ENABLE_NOW=1 ;;
  *)             echo "usage: $0 [--enable-now]" >&2; exit 2 ;;
esac

if [[ "${EUID}" -ne 0 ]]; then
  echo "error: this installer must run as root (use sudo)" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "error: missing required command: $1" >&2; exit 1; }
}

require_cmd systemctl
require_cmd systemd-analyze

[[ -d "${APP_DIR}" ]]                            || { echo "error: ${APP_DIR} does not exist" >&2; exit 1; }
[[ -r "${APP_DIR}/.env" ]]                       || { echo "error: ${APP_DIR}/.env is not readable" >&2; exit 1; }
[[ -x "${APP_DIR}/deploy/backup.sh" ]]           || { echo "error: ${APP_DIR}/deploy/backup.sh is not executable" >&2; exit 1; }
[[ -x "${APP_DIR}/deploy/sync_backup_offsite.sh" ]] || { echo "error: ${APP_DIR}/deploy/sync_backup_offsite.sh is not executable" >&2; exit 1; }
[[ -x "${APP_DIR}/deploy/restore.sh" ]]          || { echo "error: ${APP_DIR}/deploy/restore.sh is not executable" >&2; exit 1; }
[[ -r "${BACKUP_ENV_FILE}" ]]                    || {
  echo "error: ${BACKUP_ENV_FILE} is missing or unreadable." >&2
  echo "       Create it (root-owned, mode 600) with at least SIGNALBOT_BACKUP_REMOTE" >&2
  echo "       set BEFORE installing. See docs/DATA_DURABILITY_RUNBOOK.md." >&2
  exit 1
}

src_paths=()
for u in "${UNITS[@]}"; do
  p="${SCRIPT_DIR}/${u}"
  [[ -f "$p" ]] || { echo "error: source unit ${p} is missing" >&2; exit 1; }
  src_paths+=("$p")
done

echo "Validating source units with systemd-analyze verify..."
systemd-analyze verify "${src_paths[@]}"

echo "Installing units into ${UNIT_DIR} (root:root 0644)..."
for u in "${UNITS[@]}"; do
  install -o root -g root -m 0644 "${SCRIPT_DIR}/${u}" "${UNIT_DIR}/${u}"
done

systemctl daemon-reload

if [[ "${ENABLE_NOW}" -eq 1 ]]; then
  # Fail closed BEFORE activating anything: a config that works when an
  # admin runs rclone interactively must not silently fail only once the
  # timer fires unattended. Prints no credential -- only existence/
  # readability of the config PATH is checked, never its contents.
  command -v rclone >/dev/null 2>&1 || {
    echo "error: rclone is not installed/on PATH -- required before enabling the backup timer" >&2
    echo "       See docs/DATA_DURABILITY_RUNBOOK.md." >&2
    exit 1
  }
  [[ -r "${RCLONE_CONFIG_FILE}" ]] || {
    echo "error: rclone config not found/readable at ${RCLONE_CONFIG_FILE}" >&2
    echo "       -- required before enabling the backup timer. Create it (root-owned," >&2
    echo "       mode 600) per docs/DATA_DURABILITY_RUNBOOK.md before retrying." >&2
    exit 1
  }
  echo "Enabling and starting ${TIMERS[*]} (explicit --enable-now)..."
  systemctl enable --now "${TIMERS[@]}"
  echo "Backup + restore-verify timers activated."
else
  echo "Units installed and validated. NOT enabled (install-only default)."
  echo "To activate the daily backup + monthly restore-verify timers later, run:"
  echo "  sudo ${SCRIPT_DIR}/install_backup_timer.sh --enable-now"
fi

echo "Verify with:"
echo "  ${SCRIPT_DIR}/check_backup_timer.sh"
echo "  journalctl -u signalbot-backup.service -n 50 --no-pager"
echo "  journalctl -u signalbot-backup-verify.service -n 50 --no-pager"
