#!/usr/bin/env bash
set -euo pipefail

# STRICTLY READ-ONLY inspection of the Signalbot shadow timer + one-shot service.
#
# This script only ever INSPECTS. It runs no mutating systemctl verb (no start,
# stop, restart, enable, disable, daemon-reload, reset-failed, kill, edit, mask,
# or unmask), never runs --shadow-once, executes no SQL and no Docker command,
# and never prints .env or any secret.
#
# The shadow service is a `oneshot` and is normally INACTIVE between timer
# firings — a non-active status is expected and must not abort the report, so
# each inspection tolerates a non-zero exit.

TIMER_NAME=signalbot-shadow.timer
SERVICE_NAME=signalbot-shadow.service

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
