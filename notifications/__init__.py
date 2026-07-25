"""Isolated Telegram forecast-notification subsystem.

Pure formatting/model code lives here (no DB, network, clock, environment,
logging, or filesystem). The durable outbox storage lives in
storage/telegram_notification_readers.py; orchestration (secrets, clock, lock,
Telegram I/O, reporting) lives in runtime/telegram_cli.py. This package never
recomputes a forecast and is never imported by analytics or by
runtime/shadow_recovery.py — Telegram delivery is fully independent of the
shadow prediction/outcome timer.
"""
