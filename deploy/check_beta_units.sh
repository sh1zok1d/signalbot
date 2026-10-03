#!/usr/bin/env bash
set -euo pipefail

# STRICTLY READ-ONLY inspection of the private beta V0.2 units. No mutating
# systemctl verb, no --beta-* write command, no SQL, no Telegram message, and
# never prints .env or any secret. Read-only health: main.py --beta-health.

for u in signalbot-beta-detector.timer signalbot-beta-outcomes.timer \
         signalbot-beta-notify.timer signalbot-beta-bot.service \
         signalbot-beta-d7.timer signalbot-beta-history.timer; do
  echo "== ${u} =="
  systemctl is-enabled "${u}" || true
  systemctl is-active "${u}" || true
done
systemctl list-timers --all 'signalbot-beta-*' --no-pager || true
for s in signalbot-beta-detector signalbot-beta-outcomes signalbot-beta-notify signalbot-beta-bot \
         signalbot-beta-d7 signalbot-beta-history; do
  echo "== recent journal: ${s} =="
  journalctl -u "${s}.service" -n 20 --no-pager || true
done
