#!/usr/bin/env bash
set -euo pipefail

# STRICTLY READ-ONLY inspection of the Signalbot backup + restore-verify
# timers/services (see check_shadow_timer.sh/check_telegram_timer.sh for the
# same pattern).
#
# This script only ever INSPECTS. It runs no mutating systemctl verb (no
# start, stop, restart, enable, disable, daemon-reload, reset-failed, kill,
# edit, mask, or unmask), never runs a backup/restore/`docker` command,
# executes no SQL, and never prints .env, backup.env, or any secret.
#
# Both services are `oneshot` and are normally INACTIVE between timer
# firings — a non-active status is expected and must not abort the report,
# so each inspection tolerates a non-zero exit.

UNITS=(
  signalbot-backup.timer
  signalbot-backup.service
  signalbot-backup-verify.timer
  signalbot-backup-verify.service
)

for u in "${UNITS[@]}"; do
  echo "== ${u}: is-enabled =="
  systemctl is-enabled "${u}" || true
  echo "== ${u}: is-active =="
  systemctl is-active "${u}" || true
done

echo "== scheduled timers =="
systemctl list-timers --all signalbot-backup.timer signalbot-backup-verify.timer --no-pager || true

echo "== signalbot-backup.timer status =="
systemctl status signalbot-backup.timer --no-pager || true
echo "== signalbot-backup.service status (oneshot; normally inactive between runs) =="
systemctl status signalbot-backup.service --no-pager || true

echo "== signalbot-backup-verify.timer status =="
systemctl status signalbot-backup-verify.timer --no-pager || true
echo "== signalbot-backup-verify.service status (oneshot; normally inactive between runs) =="
systemctl status signalbot-backup-verify.service --no-pager || true

echo "== recent backup journal (last 50 lines) =="
journalctl -u signalbot-backup.service -n 50 --no-pager || true

echo "== recent restore-verify journal (last 50 lines) =="
journalctl -u signalbot-backup-verify.service -n 50 --no-pager || true
