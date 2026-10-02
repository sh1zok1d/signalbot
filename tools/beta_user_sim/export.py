"""Read-only exporter: beta_* rows (and the live 1m klines the outcome tracker reads)
into a replay bundle. Never run by tests against production; never run by the replay.

* one connection, one `READ ONLY` transaction, `SELECT` statements only;
* no participant table is read (beta_users, beta_allowlist, beta_feedback, activity,
  invites, waitlist): delivery rows are exported without `user_pk`,
  `telegram_message_id` or `error_summary`;
* no research archive or protected dataset is read; klines are the live
  `klines_1m` rows the existing outcome tracker already uses for these horizons.

The DSN comes from an environment variable named on the command line (never an
argument value), so it does not land in shell history or in the bundle.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from beta.config import HORIZON_MINUTES, BetaConfig

from .bundle import BUNDLE_VERSION, PROVENANCE_EXPORTED, canonical

EXPORT_QUERIES = {
    "btc_views": (
        "SELECT view_pk, requested_at, as_of_bucket, context_state_digest, episodization_version, "
        "episodization_digest, payload, payload_digest, rendered_sha256, rendered_html, lang, recorded_at "
        "FROM beta_btc_views WHERE requested_at >= $1 AND requested_at < $2 ORDER BY requested_at, view_pk"),
    "episodes": (
        "SELECT episode_pk, public_id, symbol, event_type, state, opened_bucket, opened_at, armed_at, "
        "triggered_at, terminal_at, terminal_reason, rules_version, rules_digest, code_version, "
        "calculation_version, opening_tape_digest, trigger_tape_digest, last_bucket, last_streak, "
        "reference_price, reference_exchanges, reference_dispersion_pct, reference_bucket, correction_flag, "
        "correction_note FROM beta_episodes WHERE symbol = $3 AND opened_at >= $1 AND opened_at < $2 "
        "ORDER BY opened_at, episode_pk"),
    "transitions": (
        "SELECT t.episode_pk, t.seq, t.from_state, t.to_state, t.decision_bucket, t.decision_ts, "
        "t.snapshot_digest, t.reason, t.recorded_at FROM beta_episode_transitions t "
        "JOIN beta_episodes e USING (episode_pk) WHERE e.symbol = $3 AND e.opened_at >= $1 "
        "AND e.opened_at < $2 ORDER BY t.episode_pk, t.seq"),
    "push_decisions": (
        "SELECT d.episode_pk, d.event_type, d.decision_ts, d.utc_day, d.would_push, d.decision, "
        "d.suppression_reason, d.push_enabled_effective, d.recorded_at FROM beta_push_decisions d "
        "JOIN beta_episodes e USING (episode_pk) WHERE e.symbol = $3 AND e.opened_at >= $1 "
        "AND e.opened_at < $2 ORDER BY d.episode_pk"),
    "deliveries": (
        "SELECT n.episode_pk, n.state, n.suppression_reason, n.decision_ts, n.created_at, n.sending_at, "
        "n.finished_at FROM beta_notification_deliveries n JOIN beta_episodes e USING (episode_pk) "
        "WHERE e.symbol = $3 AND e.opened_at >= $1 AND e.opened_at < $2 ORDER BY n.episode_pk, n.created_at"),
    "outcomes": (
        "SELECT o.episode_pk, o.horizon, o.outcome_version, o.revision, o.status, o.anchor_ts, o.window_end, "
        "o.reference_price, o.max_up_pct, o.max_down_pct, o.close_return_pct, o.realized_range_pct, "
        "o.time_to_max_up_s, o.time_to_max_down_s, o.bars_expected, o.bars_complete, o.source_exchanges, "
        "o.correction_note, o.computed_at FROM beta_episode_outcomes o JOIN beta_episodes e USING (episode_pk) "
        "WHERE e.symbol = $3 AND e.opened_at >= $1 AND e.opened_at < $2 ORDER BY o.episode_pk, o.horizon, "
        "o.revision"),
    "klines": (
        "SELECT exchange, ts, open, high, low, close FROM klines_1m WHERE exchange = ANY($4::text[]) "
        "AND symbol = $3 AND ts >= $1 AND ts < $2 ORDER BY ts, exchange"),
}

PROTECTED_FROM = datetime(2025, 1, 1, tzinfo=timezone.utc)


class ExportRefused(RuntimeError):
    pass


def check_query(sql: str) -> None:
    head = sql.lstrip().split(None, 1)[0].upper()
    if head != "SELECT" or ";" in sql:
        raise ExportRefused("exporter runs single SELECT statements only")
    for word in ("INSERT", "UPDATE", "DELETE", "ALTER", "DROP", "TRUNCATE", "GRANT", "CREATE", "COPY"):
        if f" {word} " in f" {sql.upper()} ":
            raise ExportRefused(f"exporter query contains {word}")
    for table in ("beta_users", "beta_allowlist", "beta_feedback", "beta_user_activity", "beta_invites",
                  "beta_waitlist", "beta_rejected_start", "beta_admin_audit"):
        if table in sql:
            raise ExportRefused(f"exporter must not read {table}")


def _plain(row) -> dict:
    d = dict(row)
    if isinstance(d.get("payload"), str):
        d["payload"] = json.loads(d["payload"])
    if d.get("utc_day") is not None and not isinstance(d["utc_day"], str):
        d["utc_day"] = d["utc_day"].isoformat()
    for k in ("reference_exchanges", "source_exchanges"):
        if k in d and d[k] is not None:
            d[k] = list(d[k])
    for k, v in list(d.items()):
        if hasattr(v, "is_finite") and not isinstance(v, (int, float)):
            d[k] = float(v)
    return d


def window_check(start: datetime, end: datetime, *, allow_protected_window: bool = False) -> None:
    """A 24h forward horizon must stay out of the sealed 2025/2026 research period
    unless the owner explicitly says this beta-only export may cover live beta time."""
    longest = timedelta(minutes=max(HORIZON_MINUTES.values()))
    if end <= start:
        raise ExportRefused("export window needs end > start")
    if end + longest > PROTECTED_FROM and not allow_protected_window:
        raise ExportRefused("window reaches 2025+; pass --beta-live-window to confirm this export reads only "
                            "live beta tables and not any sealed research dataset")


async def export_bundle(conn, cfg: BetaConfig, *, start: datetime, end: datetime,
                        history_lookback: timedelta = timedelta(days=14)) -> dict:
    """`conn` is an asyncpg connection. All reads happen in one READ ONLY transaction."""
    for sql in EXPORT_QUERIES.values():
        check_query(sql)
    longest = timedelta(minutes=max(HORIZON_MINUTES.values()))
    ep_from = start - history_lookback
    out: dict = {}
    async with conn.transaction(readonly=True, isolation="repeatable_read"):
        exported_at = await conn.fetchval("SELECT now()")
        args = {
            "btc_views": (start, end),
            "klines": (start, end + longest + timedelta(minutes=5), cfg.symbol, list(cfg.exchanges)),
        }
        for name, sql in EXPORT_QUERIES.items():
            rows = await conn.fetch(sql, *args.get(name, (ep_from, end, cfg.symbol)))
            out[name] = [_plain(r) for r in rows]
    raw = {"bundle_version": BUNDLE_VERSION, "provenance": PROVENANCE_EXPORTED, "symbol": cfg.symbol,
           "exported_at": exported_at, "episodes_since": ep_from, **out}
    return json.loads(canonical(raw))


def connect_kwargs(dsn: Optional[str]) -> dict:
    if not dsn:
        raise ExportRefused("set the DSN in the environment variable named by --dsn-env")
    return {"dsn": dsn, "server_settings": {"default_transaction_read_only": "on",
                                            "application_name": "signalbot-beta-sim-export"}}
