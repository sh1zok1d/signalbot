#!/usr/bin/env bash
set -euo pipefail

# STRICTLY READ-ONLY inspection of the private beta V0.2 units. No mutating
# systemctl verb, no --beta-* write command, no SQL, no Telegram message, and
# never prints .env or any secret. Read-only health: main.py --beta-health.

for u in signalbot-beta-detector.timer signalbot-beta-outcomes.timer \
         signalbot-beta-notify.timer signalbot-beta-bot.service \
         signalbot-beta-d7.timer signalbot-beta-history.timer \
         signalbot-beta-feeds.timer signalbot-beta-stress.timer; do
  echo "== ${u} =="
  systemctl is-enabled "${u}" || true
  systemctl is-active "${u}" || true
done
systemctl list-timers --all 'signalbot-beta-*' --no-pager || true
for s in signalbot-beta-detector signalbot-beta-outcomes signalbot-beta-notify signalbot-beta-bot \
         signalbot-beta-d7 signalbot-beta-history signalbot-beta-feeds signalbot-beta-stress; do
  echo "== recent journal: ${s} =="
  journalctl -u "${s}.service" -n 20 --no-pager || true
done
# research feed credentials (PREREQ-3): owner and mode only, never the content
echo "== research feed env file =="
stat -c '%U:%G %a %n' /opt/signalbot/.env.beta-feeds 2>/dev/null || echo "/opt/signalbot/.env.beta-feeds: missing"
