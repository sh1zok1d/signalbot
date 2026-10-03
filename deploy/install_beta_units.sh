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
       signalbot-beta-history.service signalbot-beta-history.timer)

for u in "${UNITS[@]}"; do
  install -m 0644 "${SRC_DIR}/${u}" "/etc/systemd/system/${u}"
done
systemctl daemon-reload
for u in "${UNITS[@]}"; do
  systemd-analyze verify "/etc/systemd/system/${u}" || true
done
echo "Beta units installed but NOT enabled. Activation requires owner authorization;"
echo "see docs/PRIVATE_BETA_V0_DEPLOY.md (soak: push disabled)."
