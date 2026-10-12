#!/usr/bin/env bash
set -euo pipefail

# Install the paired-shadow units. Does not enable them, does not start them,
# does not apply SQL, and does not write the connection file.

APP_DIR=/opt/signalbot
UNIT_DIR=/etc/systemd/system
UNITS=(
  signalbot-paired-shadow-snapshot.service
  signalbot-paired-shadow-snapshot.timer
  signalbot-paired-shadow-hour.service
  signalbot-paired-shadow-hour.timer
)

if [[ "${EUID}" -ne 0 ]]; then
  echo "error: this installer must run as root (use sudo)" >&2
  exit 1
fi
if [[ "${1:-}" != "" ]]; then
  echo "usage: $0" >&2
  echo "This installer has no enable switch. Scenario B in the preflight doc is the later step." >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v systemctl >/dev/null
command -v systemd-analyze >/dev/null
[[ -d "${APP_DIR}" ]] || { echo "error: ${APP_DIR} does not exist" >&2; exit 1; }
[[ -x "${APP_DIR}/.venv/bin/python" ]] || { echo "error: ${APP_DIR}/.venv/bin/python is not executable" >&2; exit 1; }

src=()
for unit in "${UNITS[@]}"; do
  [[ -f "${SCRIPT_DIR}/${unit}" ]] || { echo "error: missing ${unit}" >&2; exit 1; }
  src+=("${SCRIPT_DIR}/${unit}")
done
systemd-analyze verify "${src[@]}"
for unit in "${UNITS[@]}"; do
  install -o root -g root -m 0644 "${SCRIPT_DIR}/${unit}" "${UNIT_DIR}/${unit}"
done
systemctl daemon-reload
echo "Paired shadow units installed and not enabled."
