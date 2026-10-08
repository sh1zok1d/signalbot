#!/usr/bin/env bash
set -euo pipefail

# PREPARE (copy + daemon-reload) the Signalbot private beta V0.2 systemd units.
# It deliberately does NOT enable or start anything: activation is a separate,
# owner-authorized step (docs/PRIVATE_BETA_V0_DEPLOY.md). Never prints .env.

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNITS=(signalbot-beta-detector.service signalbot-beta-detector.timer
       signalbot-beta-outcomes.service signalbot-beta-outcomes.timer
       signalbot-beta-notify.service signalbot-beta-notify.timer
       signalbot-beta-bot.service
       signalbot-beta-d7.service signalbot-beta-d7.timer
       signalbot-beta-history.service signalbot-beta-history.timer
       signalbot-beta-feeds.service signalbot-beta-feeds.timer
       signalbot-beta-stress.service signalbot-beta-stress.timer)

for u in "${UNITS[@]}"; do
  install -m 0644 "${SRC_DIR}/${u}" "/etc/systemd/system/${u}"
done
# The build's git SHA for processes that cannot run git (beta/build.py). Written at every deploy;
# the script runs as root on a checkout owned by the service user, so git is told this directory is
# safe (otherwise it refuses with "dubious ownership" and the file would always be removed);
# when git cannot say, the file is removed rather than left stale, and the runtime says "unknown".
REPO_DIR="$(cd "${SRC_DIR}/.." && pwd)"
if sha="$(git -c safe.directory="${REPO_DIR}" -C "${REPO_DIR}" rev-parse HEAD 2>/dev/null)"; then
  if [ -n "$(git -c safe.directory="${REPO_DIR}" -C "${REPO_DIR}" status --porcelain --untracked-files=no 2>/dev/null)" ]; then
    sha="${sha}-dirty"
  fi
  printf '%s\n' "${sha}" > "${REPO_DIR}/BUILD_SHA"
  chmod 0644 "${REPO_DIR}/BUILD_SHA"
  echo "Build SHA recorded: ${sha}"
else
  rm -f "${REPO_DIR}/BUILD_SHA"
  echo "Build SHA unknown (git unavailable); BUILD_SHA removed."
fi
systemctl daemon-reload
for u in "${UNITS[@]}"; do
  systemd-analyze verify "/etc/systemd/system/${u}" || true
done
echo "Beta units installed but NOT enabled. Activation requires owner authorization;"
echo "see docs/PRIVATE_BETA_V0_DEPLOY.md (soak: push disabled)."
