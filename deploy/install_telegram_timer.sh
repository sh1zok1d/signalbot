#!/usr/bin/env bash
set -euo pipefail

# Install the Signalbot Telegram forecast notifier one-shot service + 5-minute
# timer, following the existing VPS deployment contract. DEFAULT behavior is
# install + validate ONLY (no enable, no start). Pass --enable-now to explicitly
# activate the timer.
#
# Usage:
#   sudo ./deploy/install_telegram_timer.sh                # install + validate only
#   sudo ./deploy/install_telegram_timer.sh --enable-now   # install + enable the timer
#
# This script installs deployment artifacts. It never runs --telegram-once,
# never touches Docker, never modifies the signalbot user/group or .env, and
# never stops or restarts the Stage 1 signalbot.service or the shadow
# signalbot-shadow.service/.timer.

# Fixed deployment paths (existing VPS contract).
APP_DIR=/opt/signalbot
UNIT_DIR=/etc/systemd/system
SERVICE_NAME=signalbot-telegram.service
TIMER_NAME=signalbot-telegram.timer

# Parse the single optional argument.
ENABLE_NOW=0
case "${1:-}" in
  "")            ENABLE_NOW=0 ;;
  --enable-now)  ENABLE_NOW=1 ;;
  *)             echo "usage: $0 [--enable-now]" >&2; exit 2 ;;
esac

# 1. Require root.
if [[ "${EUID}" -ne 0 ]]; then
  echo "error: this installer must run as root (use sudo)" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_SERVICE="${SCRIPT_DIR}/${SERVICE_NAME}"
SRC_TIMER="${SCRIPT_DIR}/${TIMER_NAME}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "error: missing required command: $1" >&2; exit 1; }
}

# 3. Validate everything BEFORE changing anything on the system.
require_cmd systemctl
require_cmd systemd-analyze

[[ -d "${APP_DIR}" ]]                      || { echo "error: ${APP_DIR} does not exist" >&2; exit 1; }
[[ -f "${APP_DIR}/main.py" ]]              || { echo "error: ${APP_DIR}/main.py is missing" >&2; exit 1; }
[[ -x "${APP_DIR}/.venv/bin/python" ]]     || { echo "error: ${APP_DIR}/.venv/bin/python is not executable" >&2; exit 1; }
[[ -r "${APP_DIR}/.env" ]]                 || { echo "error: ${APP_DIR}/.env is not readable" >&2; exit 1; }
getent passwd signalbot >/dev/null         || { echo "error: system user 'signalbot' does not exist" >&2; exit 1; }
getent group  signalbot >/dev/null         || { echo "error: system group 'signalbot' does not exist" >&2; exit 1; }
[[ -f "${SRC_SERVICE}" ]]                  || { echo "error: source unit ${SRC_SERVICE} is missing" >&2; exit 1; }
[[ -f "${SRC_TIMER}" ]]                    || { echo "error: source unit ${SRC_TIMER} is missing" >&2; exit 1; }

# 5. Validate the SOURCE units before installing or enabling them.
echo "Validating source units with systemd-analyze verify..."
systemd-analyze verify "${SRC_SERVICE}" "${SRC_TIMER}"

# 6. Install the units root:root 0644.
echo "Installing units into ${UNIT_DIR} (root:root 0644)..."
install -o root -g root -m 0644 "${SRC_SERVICE}" "${UNIT_DIR}/${SERVICE_NAME}"
install -o root -g root -m 0644 "${SRC_TIMER}"   "${UNIT_DIR}/${TIMER_NAME}"

# 7. Reload systemd so it sees the new units.
systemctl daemon-reload

if [[ "${ENABLE_NOW}" -eq 1 ]]; then
  # 9. Explicit activation: enable+start the TIMER only (never the service).
  echo "Enabling and starting ${TIMER_NAME} (explicit --enable-now)..."
  systemctl enable --now "${TIMER_NAME}"
  echo "Telegram notifier timer activated."
else
  # 8. Default: install + validate only. Do NOT enable or start anything.
  echo "Units installed and validated. NOT enabled (install-only default)."
  echo "To activate the 5-minute Telegram notifier timer later, run:"
  echo "  sudo ${SCRIPT_DIR}/install_telegram_timer.sh --enable-now"
fi

# 10. Bounded verification hints (no secrets, no mutation).
echo "Verify with:"
echo "  systemctl status ${TIMER_NAME} --no-pager"
echo "  systemctl list-timers --all ${TIMER_NAME} --no-pager"
echo "  journalctl -u ${SERVICE_NAME} -n 50 --no-pager"
