#!/usr/bin/env bash
set -euo pipefail

# STRICTLY READ-ONLY inspection of the Signalbot Telegram notifier timer +
# one-shot service.
#
# This script only ever INSPECTS. It runs no mutating systemctl verb (no start,
# stop, restart, enable, disable, daemon-reload, reset-failed, kill, edit, mask,
# or unmask), never runs --telegram-once or --telegram-test, executes no SQL,
# sends no Telegram message, and never prints .env, the bot token, or any
# other secret.
#
# The notifier service is a `oneshot` and is normally INACTIVE between timer
# firings — a non-active status is expected and must not abort the report, so
# each inspection tolerates a non-zero exit.

TIMER_NAME=signalbot-telegram.timer
SERVICE_NAME=signalbot-telegram.service

echo "== timer is-enabled =="
systemctl is-enabled "${TIMER_NAME}" || true

echo "== timer is-active =="
systemctl is-active "${TIMER_NAME}" || true

echo "== scheduled timers =="
systemctl list-timers --all "${TIMER_NAME}" --no-pager || true

echo "== timer status =="
systemctl status "${TIMER_NAME}" --no-pager || true

echo "== service status (oneshot; normally inactive between runs) =="
systemctl status "${SERVICE_NAME}" --no-pager || true

echo "== timer properties =="
systemctl show "${TIMER_NAME}" || true

echo "== recent service journal (last 50 lines) =="
journalctl -u "${SERVICE_NAME}" -n 50 --no-pager || true
