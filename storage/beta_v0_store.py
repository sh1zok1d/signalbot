"""Beta V0.2 storage: static/trusted SQL over asyncpg for the beta_* tables only.

Never writes Stage-1, Stage-2 or frozen forecast tables. Reads Stage-1 raw
tables (klines_1m / connectivity_events) and the Stage-2 capability registry
read-only. Every method runs on ONE explicit connection (`BetaConn`), so callers
can group a bucket's writes into ONE transaction.

PRIVACY: Telegram identifiers are only ever written to beta_allowlist /
beta_users; no method logs them.
"""
from __future__ import annotations

import contextlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from beta.models import Episode, TapeRecord

BETA_SCHEMA_PATH = Path(__file__).resolve().parent / "beta_v0_schema.sql"
SCHEMA_LOCK_KEY = "beta_v0_schema_init"

# Session advisory-lock keys: a dedicated namespace, distinct from the shadow
# recovery / legacy telegram notifier keys.
DETECTOR_LOCK_KEY = 7_311_000_001
OUTCOMES_LOCK_KEY = 7_311_000_002
NOTIFIER_LOCK_KEY = 7_311_000_003
BOT_LOCK_KEY = 7_311_000_004

_EPISODE_COLS = """episode_pk, public_id, symbol, event_type, state, opened_bucket, opened_at,
    armed_at, triggered_at, terminal_at, terminal_reason, rules_version, rules_digest,
    code_version, calculation_version, opening_tape_digest, trigger_tape_digest,
    last_bucket, last_streak, reference_price, reference_exchanges,
    reference_dispersion_pct, reference_bucket, correction_flag, correction_note"""


_E_EPISODE_COLS = ", ".join("e." + c.strip() for c in _EPISODE_COLS.split(","))


def _j(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _load(value):
    if value is None:
        return None
    return json.loads(value) if isinstance(value, str) else value


def row_to_episode(r) -> Episode:
    return Episode(
        episode_pk=r["episode_pk"], public_id=r["public_id"], symbol=r["symbol"],
        event_type=r["event_type"], state=r["state"], opened_bucket=r["opened_bucket"],
        opened_at=r["opened_at"], armed_at=r["armed_at"], triggered_at=r["triggered_at"],
        terminal_at=r["terminal_at"], terminal_reason=r["terminal_reason"],
        rules_version=r["rules_version"], rules_digest=r["rules_digest"],
        code_version=r["code_version"], calculation_version=r["calculation_version"],
        opening_tape_digest=r["opening_tape_digest"],
        trigger_tape_digest=r["trigger_tape_digest"], last_bucket=r["last_bucket"],
        last_streak=r["last_streak"], reference_price=r["reference_price"],
        reference_exchanges=tuple(r["reference_exchanges"] or ()),
        reference_dispersion_pct=r["reference_dispersion_pct"],
        reference_bucket=r["reference_bucket"], correction_flag=r["correction_flag"],
        correction_note=r["correction_note"])


async def apply_beta_schema(conn) -> None:
    """Apply storage/beta_v0_schema.sql as ONE script in ONE transaction,
    serialized by a transaction-scoped advisory lock (idempotent)."""
    sql = BETA_SCHEMA_PATH.read_text(encoding="utf-8")
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", SCHEMA_LOCK_KEY)
        await conn.execute(sql)


class BetaStore:
    """Pool-level entry point. `async with store.connect() as c:` yields a BetaConn."""

    def __init__(self, pool):
        self._pool = pool

    @contextlib.asynccontextmanager
    async def connect(self):
        async with self._pool.acquire() as conn:
            yield BetaConn(conn)

    @contextlib.asynccontextmanager
    async def advisory_lock(self, key: int):
        """Session-scoped advisory lock on a dedicated connection; yields bool."""
        if type(key) is not int:
            raise ValueError("advisory lock key must be an int")
        conn = await self._pool.acquire()
        acquired = False
        try:
            acquired = bool(await conn.fetchval("SELECT pg_try_advisory_lock($1)", key))
            yield acquired
        finally:
            try:
                if acquired:
                    await conn.fetchval("SELECT pg_advisory_unlock($1)", key)
            finally:
                await self._pool.release(conn)


class BetaConn:
    def __init__(self, conn):
        self.conn = conn

    def transaction(self):
        return self.conn.transaction()

    async def init_schema(self) -> None:
        await apply_beta_schema(self.conn)

    async def schema_present(self) -> bool:
        return bool(await self.conn.fetchval(
            "SELECT to_regclass('public.beta_state_tape') IS NOT NULL "
            "AND to_regclass('public.beta_admin_audit') IS NOT NULL"))

    # ------------------------------------------------------------------ tape
    async def insert_tape(self, rec: TapeRecord, *, revision: int = 1,
                          supersedes_tape_id: Optional[int] = None) -> int:
        return await self.conn.fetchval(
            """INSERT INTO beta_state_tape (symbol, market_type, timeframe, bucket_ts,
                   calculation_version, state_schema_version, rules_version, rules_digest,
                   revision, supersedes_tape_id, origin, materialized, evaluation_fresh,
                   code_version, config_digest, raw_revision, evaluated_at, metrics, snapshot,
                   feature_digest, snapshot_digest)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,
                       $18::jsonb,$19::jsonb,$20,$21)
               RETURNING tape_id""",
            rec.symbol, rec.market_type, rec.timeframe, rec.bucket_ts, rec.calculation_version,
            rec.state_schema_version, rec.rules_version, rec.rules_digest, revision,
            supersedes_tape_id, rec.origin, rec.materialized, rec.evaluation_fresh,
            rec.code_version, rec.config_digest, rec.raw_revision, rec.evaluated_at,
            _j(dict(rec.metrics)), _j(dict(rec.snapshot)), rec.feature_digest, rec.snapshot_digest)

    async def fetch_tape_history(self, *, symbol: str, market_type: str, timeframe: str,
                                 calculation_version: str, state_schema_version: int,
                                 start: datetime, end: datetime) -> list:
        """Latest-recorded row per bucket in [start, end) — `end` (the current
        bucket) is EXCLUDED by the predicate itself."""
        rows = await self.conn.fetch(
            """SELECT DISTINCT ON (bucket_ts) bucket_ts, metrics
               FROM beta_state_tape
               WHERE symbol=$1 AND market_type=$2 AND timeframe=$3
                 AND calculation_version=$4 AND state_schema_version=$5
                 AND materialized AND bucket_ts >= $6 AND bucket_ts < $7
               ORDER BY bucket_ts, tape_id DESC""",
            symbol, market_type, timeframe, calculation_version, state_schema_version, start, end)
        return [(r["bucket_ts"], _load(r["metrics"])) for r in rows]

    async def fetch_live_tape(self, *, symbol: str, bucket_ts: datetime,
                              rules_digest: Optional[str] = None):
        q = ("SELECT tape_id, bucket_ts, rules_digest, calculation_version, feature_digest, "
             "snapshot_digest, snapshot, evaluated_at, revision FROM beta_state_tape "
             "WHERE symbol=$1 AND bucket_ts=$2 AND origin='LIVE'")
        args: list = [symbol, bucket_ts]
        if rules_digest is not None:
            q += " AND rules_digest=$3"
            args.append(rules_digest)
        r = await self.conn.fetchrow(q + " ORDER BY tape_id DESC LIMIT 1", *args)
        return None if r is None else {**dict(r), "snapshot": _load(r["snapshot"])}

    async def fetch_latest_live_tape(self, *, symbol: str):
        r = await self.conn.fetchrow(
            "SELECT tape_id, bucket_ts, rules_digest, snapshot, evaluated_at FROM beta_state_tape "
            "WHERE symbol=$1 AND origin='LIVE' ORDER BY bucket_ts DESC, tape_id DESC LIMIT 1", symbol)
        return None if r is None else {**dict(r), "snapshot": _load(r["snapshot"])}

    async def fetch_bucket_chain(self, *, symbol: str, bucket_ts: datetime, rules_digest: str):
        """Every row for a bucket under one rules digest (oldest first)."""
        rows = await self.conn.fetch(
            "SELECT tape_id, origin, revision, feature_digest, snapshot_digest, calculation_version "
            "FROM beta_state_tape WHERE symbol=$1 AND bucket_ts=$2 AND rules_digest=$3 "
            "ORDER BY tape_id", symbol, bucket_ts, rules_digest)
        return [dict(r) for r in rows]

    async def tape_bucket_exists(self, *, symbol: str, bucket_ts: datetime,
                                 state_schema_version: int) -> bool:
        return bool(await self.conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM beta_state_tape WHERE symbol=$1 AND bucket_ts=$2 "
            "AND state_schema_version=$3)", symbol, bucket_ts, state_schema_version))

    async def count_tape(self, *, symbol: str, since: datetime, origin: str = "LIVE") -> Mapping:
        r = await self.conn.fetchrow(
            "SELECT count(*) AS n, count(*) FILTER (WHERE materialized) AS materialized, "
            "count(*) FILTER (WHERE evaluation_fresh) AS fresh FROM beta_state_tape "
            "WHERE symbol=$1 AND origin=$2 AND bucket_ts >= $3", symbol, origin, since)
        return dict(r)

    # ------------------------------------------------------------- watermark
    async def get_watermark(self, runner: str, *, symbol: str, market_type: str,
                            timeframe: str) -> Optional[datetime]:
        return await self.conn.fetchval(
            "SELECT bucket_ts FROM beta_detector_watermark WHERE runner_name=$1 AND symbol=$2 "
            "AND market_type=$3 AND timeframe=$4", runner, symbol, market_type, timeframe)

    async def advance_watermark(self, runner: str, *, symbol: str, market_type: str,
                                timeframe: str, bucket_ts: datetime) -> None:
        await self.conn.execute(
            """INSERT INTO beta_detector_watermark (runner_name, symbol, market_type, timeframe, bucket_ts)
               VALUES ($1,$2,$3,$4,$5)
               ON CONFLICT (runner_name, symbol, market_type, timeframe) DO UPDATE
               SET bucket_ts = GREATEST(beta_detector_watermark.bucket_ts, EXCLUDED.bucket_ts),
                   updated_at = now()""", runner, symbol, market_type, timeframe, bucket_ts)

    # ------------------------------------------------ Stage-1 read-only views
    async def fetch_venue_bucket_rows(self, *, exchanges: Sequence[str], symbol: str,
                                      bucket_start: datetime, bucket_end: datetime,
                                      event_lookaround: timedelta = timedelta(hours=6)) -> Mapping:
        """Per venue: live-sourced 1m bar count in the bucket + the connectivity
        events needed to decide whether a logged outage overlaps it."""
        bars = await self.conn.fetch(
            "SELECT exchange, count(*) FILTER (WHERE source='live') AS live_bars, count(*) AS bars "
            "FROM klines_1m WHERE exchange = ANY($1::text[]) AND symbol=$2 AND ts >= $3 AND ts < $4 "
            "GROUP BY exchange", list(exchanges), symbol, bucket_start, bucket_end)
        events = await self.conn.fetch(
            """(SELECT DISTINCT ON (exchange) exchange, event_type, ts, detail FROM connectivity_events
                WHERE exchange = ANY($1::text[]) AND event_type IN ('disconnect','restore') AND ts < $2
                ORDER BY exchange, ts DESC, id DESC)
               UNION ALL
               (SELECT exchange, event_type, ts, detail FROM connectivity_events
                WHERE exchange = ANY($1::text[]) AND event_type IN ('disconnect','restore')
                  AND ts >= $2 AND ts < $3)""",
            list(exchanges), bucket_start - event_lookaround, bucket_end + event_lookaround)
        out = {ex: {"live_bars": 0, "bars": 0, "events": []} for ex in exchanges}
        for r in bars:
            out[r["exchange"]].update(live_bars=int(r["live_bars"]), bars=int(r["bars"]))
        for r in events:
            out[r["exchange"]]["events"].append(
                {"event_type": r["event_type"], "ts": r["ts"], "detail": _load(r["detail"]) or {}})
        return out

    async def fetch_newest_live_kline(self, *, exchanges: Sequence[str], symbol: str,
                                      since: datetime) -> Mapping:
        rows = await self.conn.fetch(
            "SELECT exchange, max(ts) AS ts FROM klines_1m WHERE exchange = ANY($1::text[]) "
            "AND symbol=$2 AND source='live' AND ts >= $3 GROUP BY exchange",
            list(exchanges), symbol, since)
        return {r["exchange"]: r["ts"] for r in rows}

    async def fetch_klines(self, *, exchanges: Sequence[str], symbol: str, start: datetime,
                           end: datetime) -> list:
        rows = await self.conn.fetch(
            "SELECT exchange, ts, high, low, close FROM klines_1m WHERE exchange = ANY($1::text[]) "
            "AND symbol=$2 AND ts >= $3 AND ts < $4 ORDER BY ts, exchange",
            list(exchanges), symbol, start, end)
        return [dict(r) for r in rows]

    # -------------------------------------------------------------- episodes
    async def fetch_open_episodes(self, *, symbol: str, for_update: bool = True) -> dict:
        rows = await self.conn.fetch(
            f"SELECT {_EPISODE_COLS} FROM beta_episodes WHERE symbol=$1 "
            "AND state IN ('EARLY','ARMED','TRIGGERED') ORDER BY opened_at"
            + (" FOR UPDATE" if for_update else ""), symbol)
        return {r["event_type"]: row_to_episode(r) for r in rows}

    async def insert_episode(self, ep: Episode) -> int:
        return await self.conn.fetchval(
            """INSERT INTO beta_episodes (public_id, symbol, event_type, state, opened_bucket,
                   opened_at, armed_at, triggered_at, rules_version, rules_digest, code_version,
                   calculation_version, opening_tape_digest, trigger_tape_digest, last_bucket,
                   last_streak, reference_price, reference_exchanges, reference_dispersion_pct,
                   reference_bucket)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
               RETURNING episode_pk""",
            ep.public_id, ep.symbol, ep.event_type, ep.state, ep.opened_bucket, ep.opened_at,
            ep.armed_at, ep.triggered_at, ep.rules_version, ep.rules_digest, ep.code_version,
            ep.calculation_version, ep.opening_tape_digest, ep.trigger_tape_digest,
            ep.last_bucket, ep.last_streak, ep.reference_price, list(ep.reference_exchanges),
            ep.reference_dispersion_pct, ep.reference_bucket)

    async def update_episode(self, ep: Episode, *, expected_state: str) -> None:
        """Guarded update of lifecycle fields (compare-and-set on the old state)."""
        status = await self.conn.execute(
            """UPDATE beta_episodes SET state=$2, armed_at=$3, triggered_at=$4, terminal_at=$5,
                   terminal_reason=$6, trigger_tape_digest=$7, last_bucket=$8, last_streak=$9,
                   reference_price=$10, reference_exchanges=$11, reference_dispersion_pct=$12,
                   reference_bucket=$13, updated_at=now()
               WHERE episode_pk=$1 AND state=$14""",
            ep.episode_pk, ep.state, ep.armed_at, ep.triggered_at, ep.terminal_at,
            ep.terminal_reason, ep.trigger_tape_digest, ep.last_bucket, ep.last_streak,
            ep.reference_price, list(ep.reference_exchanges), ep.reference_dispersion_pct,
            ep.reference_bucket, expected_state)
        if status != "UPDATE 1":
            raise RuntimeError("episode compare-and-set failed (concurrent modification)")

    async def next_transition_seq(self, episode_pk: int) -> int:
        return int(await self.conn.fetchval(
            "SELECT coalesce(max(seq), 0) + 1 FROM beta_episode_transitions WHERE episode_pk=$1",
            episode_pk))

    async def insert_transition(self, *, episode_pk: int, seq: int, from_state: Optional[str],
                                to_state: str, decision_bucket: datetime, decision_ts: datetime,
                                snapshot_digest: str, reason: str) -> None:
        await self.conn.execute(
            """INSERT INTO beta_episode_transitions (episode_pk, seq, from_state, to_state,
                   decision_bucket, decision_ts, snapshot_digest, reason)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
            episode_pk, seq, from_state, to_state, decision_bucket, decision_ts,
            snapshot_digest, reason)

    async def fetch_transitions(self, episode_pk: int) -> list:
        rows = await self.conn.fetch(
            "SELECT seq, from_state, to_state, decision_bucket, decision_ts, snapshot_digest, reason "
            "FROM beta_episode_transitions WHERE episode_pk=$1 ORDER BY seq", episode_pk)
        return [dict(r) for r in rows]

    async def latest_same_type_terminal(self, *, symbol: str, event_type: str,
                                        exclude_pk: Optional[int]) -> Optional[datetime]:
        return await self.conn.fetchval(
            "SELECT max(terminal_at) FROM beta_episodes WHERE symbol=$1 AND event_type=$2 "
            "AND terminal_at IS NOT NULL AND episode_pk IS DISTINCT FROM $3",
            symbol, event_type, exclude_pk)

    async def latest_same_type_would_push(self, *, event_type: str,
                                          exclude_pk: Optional[int]) -> Optional[datetime]:
        return await self.conn.fetchval(
            "SELECT max(decision_ts) FROM beta_push_decisions WHERE event_type=$1 AND would_push "
            "AND episode_pk IS DISTINCT FROM $2", event_type, exclude_pk)

    async def count_would_push(self, utc_day: date) -> int:
        return int(await self.conn.fetchval(
            "SELECT count(*) FROM beta_push_decisions WHERE utc_day=$1 AND would_push", utc_day))

    async def insert_push_decision(self, *, episode_pk: int, event_type: str,
                                   decision_ts: datetime, would_push: bool, decision: str,
                                   suppression_reason: Optional[str],
                                   push_enabled_effective: bool) -> int:
        return await self.conn.fetchval(
            """INSERT INTO beta_push_decisions (episode_pk, event_type, decision_ts, utc_day,
                   would_push, decision, suppression_reason, push_enabled_effective)
               VALUES ($1,$2,$3,($3 AT TIME ZONE 'UTC')::date,$4,$5,$6,$7) RETURNING decision_id""",
            episode_pk, event_type, decision_ts, would_push, decision, suppression_reason,
            push_enabled_effective)

    async def flag_correction(self, *, snapshot_digests: Sequence[str], note: str) -> int:
        """Annotate (never rewrite) episodes decided from a later-corrected snapshot."""
        status = await self.conn.execute(
            """UPDATE beta_episodes SET correction_flag=TRUE,
                   correction_note = CASE WHEN correction_note IS NULL THEN $2
                                          ELSE correction_note || ' | ' || $2 END,
                   updated_at=now()
               WHERE opening_tape_digest = ANY($1::text[]) OR trigger_tape_digest = ANY($1::text[])
                  OR episode_pk IN (SELECT episode_pk FROM beta_episode_transitions
                                    WHERE snapshot_digest = ANY($1::text[]))""",
            list(snapshot_digests), note)
        return int(status.split()[-1])

    async def fetch_episode_history(self, *, symbol: str, limit: int) -> list:
        rows = await self.conn.fetch(
            f"""SELECT {_E_EPISODE_COLS},
                   d.decision, d.suppression_reason, d.decision_ts AS push_decision_ts,
                   (SELECT array_agg(DISTINCT x.state) FROM beta_notification_deliveries x
                     WHERE x.episode_pk = e.episode_pk) AS delivery_states
                FROM beta_episodes e LEFT JOIN beta_push_decisions d USING (episode_pk)
                WHERE e.symbol=$1 ORDER BY e.opened_at DESC, e.episode_pk DESC LIMIT $2""",
            symbol, limit)
        return [dict(r) for r in rows]

    async def fetch_episode_by_pk(self, episode_pk: int):
        r = await self.conn.fetchrow(
            f"SELECT {_EPISODE_COLS} FROM beta_episodes WHERE episode_pk=$1", episode_pk)
        return None if r is None else row_to_episode(r)

    async def fetch_episode_by_public_id(self, public_id: str):
        r = await self.conn.fetchrow(
            f"SELECT {_EPISODE_COLS} FROM beta_episodes WHERE public_id=$1", public_id)
        return None if r is None else row_to_episode(r)

    async def episode_counts(self, *, symbol: str, since: datetime) -> list:
        rows = await self.conn.fetch(
            """SELECT event_type, count(*) AS opened,
                   count(*) FILTER (WHERE armed_at IS NOT NULL) AS armed,
                   count(*) FILTER (WHERE triggered_at IS NOT NULL) AS triggered,
                   count(*) FILTER (WHERE state IN ('EARLY','ARMED','TRIGGERED')) AS open_now
               FROM beta_episodes WHERE symbol=$1 AND opened_at >= $2
               GROUP BY event_type ORDER BY event_type""", symbol, since)
        return [dict(r) for r in rows]

    # -------------------------------------------------------------- outcomes
    async def fetch_outcome_candidates(self, *, symbol: str, outcome_version: str,
                                       horizons: Sequence[str], limit: int) -> list:
        """TRIGGERED episodes (pushed or not) lacking a row for some horizon."""
        rows = await self.conn.fetch(
            """SELECT e.episode_pk, e.public_id, e.event_type, e.triggered_at, e.reference_price,
                      e.reference_exchanges, h.horizon
               FROM beta_episodes e CROSS JOIN unnest($3::text[]) AS h(horizon)
               WHERE e.symbol=$1 AND e.triggered_at IS NOT NULL
                 AND NOT EXISTS (SELECT 1 FROM beta_episode_outcomes o WHERE o.episode_pk=e.episode_pk
                                 AND o.horizon=h.horizon AND o.outcome_version=$2)
               ORDER BY e.triggered_at, e.episode_pk, h.horizon LIMIT $4""",
            symbol, outcome_version, list(horizons), limit)
        return [dict(r) for r in rows]

    async def fetch_recheck_candidates(self, *, outcome_version: str, since: datetime,
                                       limit: int) -> list:
        rows = await self.conn.fetch(
            """SELECT DISTINCT ON (o.episode_pk, o.horizon) o.outcome_id, o.episode_pk, o.horizon,
                      o.revision, o.status, o.outcome_digest, e.triggered_at, e.reference_price,
                      e.reference_exchanges, e.public_id, e.event_type
               FROM beta_episode_outcomes o JOIN beta_episodes e USING (episode_pk)
               WHERE o.outcome_version=$1 AND o.status='COMPLETE' AND o.window_end >= $2
               ORDER BY o.episode_pk, o.horizon, o.revision DESC LIMIT $3""",
            outcome_version, since, limit)
        return [dict(r) for r in rows]

    async def insert_outcome(self, o: Mapping[str, Any]) -> int:
        return await self.conn.fetchval(
            """INSERT INTO beta_episode_outcomes (episode_pk, horizon, outcome_version, revision,
                   supersedes_outcome_id, status, anchor_ts, window_end, reference_price,
                   max_up_pct, max_down_pct, close_return_pct, realized_range_pct,
                   time_to_max_up_s, time_to_max_down_s, bars_expected, bars_complete,
                   source_exchanges, source_raw_revision, outcome_digest, correction_note, computed_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22)
               RETURNING outcome_id""",
            o["episode_pk"], o["horizon"], o["outcome_version"], o["revision"],
            o.get("supersedes_outcome_id"), o["status"], o["anchor_ts"], o["window_end"],
            o["reference_price"], o["max_up_pct"], o["max_down_pct"], o["close_return_pct"],
            o["realized_range_pct"], o["time_to_max_up_s"], o["time_to_max_down_s"],
            o["bars_expected"], o["bars_complete"], list(o["source_exchanges"]),
            o.get("source_raw_revision"), o["outcome_digest"], o.get("correction_note"),
            o["computed_at"])

    async def fetch_outcomes(self, episode_pk: int) -> list:
        rows = await self.conn.fetch(
            """SELECT DISTINCT ON (horizon) horizon, status, max_up_pct, max_down_pct,
                   close_return_pct, realized_range_pct, time_to_max_up_s, time_to_max_down_s,
                   revision, correction_note
               FROM beta_episode_outcomes WHERE episode_pk=$1
               ORDER BY horizon, revision DESC""", episode_pk)
        return [dict(r) for r in rows]

    # ------------------------------------------------------------ deliveries
    async def recover_sending(self, now: datetime) -> int:
        status = await self.conn.execute(
            "UPDATE beta_notification_deliveries SET state='DELIVERY_UNKNOWN', finished_at=$1 "
            "WHERE state='SENDING'", now)
        return int(status.split()[-1])

    async def fetch_undispatched_push_decisions(self, limit: int) -> list:
        rows = await self.conn.fetch(
            """SELECT d.decision_id, d.episode_pk, d.decision_ts FROM beta_push_decisions d
               WHERE d.decision='PUSH' AND NOT EXISTS (
                   SELECT 1 FROM beta_notification_deliveries x WHERE x.decision_id=d.decision_id)
               ORDER BY d.decision_ts, d.decision_id LIMIT $1""", limit)
        return [dict(r) for r in rows]

    async def materialize_deliveries(self, *, decision_id: int, episode_pk: int,
                                     decision_ts: datetime, expired: bool) -> int:
        """One row per current participant: PENDING for ACTIVE, SUPPRESSED /
        USER_INACTIVE for STOPPED; EXPIRED_UNDELIVERED if the decision already
        exceeded the TTL. Unique (decision_id, user_pk) makes this idempotent."""
        status = await self.conn.execute(
            """INSERT INTO beta_notification_deliveries (decision_id, episode_pk, user_pk, state,
                   suppression_reason, decision_ts)
               SELECT $1, $2, u.user_pk,
                      CASE WHEN $4::boolean THEN 'EXPIRED_UNDELIVERED'
                           WHEN u.status='ACTIVE' THEN 'PENDING' ELSE 'SUPPRESSED' END,
                      CASE WHEN $4::boolean THEN 'DELIVERY_TOO_OLD'
                           WHEN u.status='ACTIVE' THEN NULL ELSE 'USER_INACTIVE' END,
                      $3
               FROM beta_users u
               ON CONFLICT (decision_id, user_pk) DO NOTHING""",
            decision_id, episode_pk, decision_ts, expired)
        return int(status.split()[-1])

    async def fetch_pending_deliveries(self, limit: int) -> list:
        rows = await self.conn.fetch(
            """SELECT x.delivery_id, x.decision_id, x.episode_pk, x.user_pk, x.decision_ts,
                      u.chat_id, u.status AS user_status
               FROM beta_notification_deliveries x JOIN beta_users u USING (user_pk)
               WHERE x.state='PENDING' ORDER BY x.decision_ts, x.delivery_id LIMIT $1""", limit)
        return [dict(r) for r in rows]

    async def transition_delivery(self, delivery_id: int, *, from_state: str, to_state: str,
                                  now: datetime, suppression_reason: Optional[str] = None,
                                  message_id: Optional[int] = None,
                                  error_summary: Optional[str] = None) -> bool:
        status = await self.conn.execute(
            """UPDATE beta_notification_deliveries SET state=$3, suppression_reason=$4,
                   telegram_message_id=$5, error_summary=$6,
                   sending_at = CASE WHEN $3::text='SENDING' THEN $7::timestamptz ELSE sending_at END,
                   finished_at = CASE WHEN $3::text='SENDING' THEN finished_at ELSE $7::timestamptz END
               WHERE delivery_id=$1 AND state=$2""",
            delivery_id, from_state, to_state, suppression_reason, message_id, error_summary, now)
        return status == "UPDATE 1"

    async def delivery_state_counts(self, *, since: Optional[datetime] = None) -> dict:
        rows = await self.conn.fetch(
            "SELECT state, count(*) AS n FROM beta_notification_deliveries "
            "WHERE $1::timestamptz IS NULL OR created_at >= $1 GROUP BY state", since)
        return {r["state"]: int(r["n"]) for r in rows}

    async def push_decision_counts(self, *, since: datetime) -> list:
        rows = await self.conn.fetch(
            "SELECT decision, suppression_reason, count(*) AS n FROM beta_push_decisions "
            "WHERE decision_ts >= $1 GROUP BY decision, suppression_reason ORDER BY 1, 2", since)
        return [dict(r) for r in rows]

    async def cap_activation_days(self, *, since: datetime) -> int:
        return int(await self.conn.fetchval(
            "SELECT count(DISTINCT utc_day) FROM beta_push_decisions WHERE decision_ts >= $1 "
            "AND suppression_reason='DAILY_CAP'", since))

    # ----------------------------------------------------- participants (PII)
    async def allowlist_contains(self, telegram_user_id: int) -> bool:
        return bool(await self.conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM beta_allowlist WHERE telegram_user_id=$1)",
            telegram_user_id))

    async def allowlist_add(self, telegram_user_id: int) -> bool:
        status = await self.conn.execute(
            "INSERT INTO beta_allowlist (telegram_user_id) VALUES ($1) ON CONFLICT DO NOTHING",
            telegram_user_id)
        return status.endswith(" 1")

    async def allowlist_count(self) -> int:
        return int(await self.conn.fetchval("SELECT count(*) FROM beta_allowlist"))

    async def get_user(self, telegram_user_id: int):
        r = await self.conn.fetchrow(
            "SELECT user_pk, telegram_user_id, chat_id, status, joined_at, stopped_at "
            "FROM beta_users WHERE telegram_user_id=$1", telegram_user_id)
        return None if r is None else dict(r)

    async def join_user(self, *, telegram_user_id: int, chat_id: int, now: datetime) -> int:
        return await self.conn.fetchval(
            """INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at)
               VALUES ($1,$2,'ACTIVE',$3,$3)
               ON CONFLICT (telegram_user_id) DO UPDATE SET status='ACTIVE', stopped_at=NULL,
                   chat_id=EXCLUDED.chat_id, privacy_accepted_at=EXCLUDED.privacy_accepted_at,
                   updated_at=now()
               RETURNING user_pk""", telegram_user_id, chat_id, now)

    async def stop_user(self, *, telegram_user_id: int, now: datetime) -> bool:
        status = await self.conn.execute(
            "UPDATE beta_users SET status='STOPPED', stopped_at=$2, updated_at=now() "
            "WHERE telegram_user_id=$1 AND status='ACTIVE'", telegram_user_id, now)
        return status == "UPDATE 1"

    async def delete_participant(self, telegram_user_id: int) -> dict:
        """Delete the participant's personal beta records: user row (feedback
        cascades; delivery rows keep only an anonymous NULL user_pk) and the
        allowlist entry. Market/event records contain no identity and remain."""
        users = await self.conn.execute("DELETE FROM beta_users WHERE telegram_user_id=$1",
                                        telegram_user_id)
        allow = await self.conn.execute("DELETE FROM beta_allowlist WHERE telegram_user_id=$1",
                                        telegram_user_id)
        return {"users": int(users.split()[-1]), "allowlist": int(allow.split()[-1])}

    async def stopped_users_before(self, cutoff: datetime) -> list:
        rows = await self.conn.fetch(
            "SELECT telegram_user_id FROM beta_users WHERE status='STOPPED' AND stopped_at < $1",
            cutoff)
        return [r["telegram_user_id"] for r in rows]

    async def list_users(self) -> list:
        rows = await self.conn.fetch(
            """SELECT a.telegram_user_id, u.status, u.joined_at, u.stopped_at
               FROM beta_allowlist a LEFT JOIN beta_users u USING (telegram_user_id)
               UNION ALL
               SELECT u.telegram_user_id, u.status, u.joined_at, u.stopped_at FROM beta_users u
               WHERE NOT EXISTS (SELECT 1 FROM beta_allowlist a WHERE a.telegram_user_id=u.telegram_user_id)
               ORDER BY 3 NULLS LAST""")
        return [dict(r) for r in rows]

    async def active_user_chats(self) -> list:
        rows = await self.conn.fetch("SELECT chat_id FROM beta_users WHERE status='ACTIVE' ORDER BY user_pk")
        return [r["chat_id"] for r in rows]

    async def user_counts(self) -> dict:
        rows = await self.conn.fetch("SELECT status, count(*) AS n FROM beta_users GROUP BY status")
        return {r["status"]: int(r["n"]) for r in rows}

    async def upsert_feedback(self, *, user_pk: int, episode_pk: int, vote: str) -> None:
        await self.conn.execute(
            """INSERT INTO beta_feedback (user_pk, episode_pk, vote) VALUES ($1,$2,$3)
               ON CONFLICT (user_pk, episode_pk) DO UPDATE SET vote=EXCLUDED.vote, updated_at=now()""",
            user_pk, episode_pk, vote)

    async def feedback_counts(self) -> dict:
        rows = await self.conn.fetch("SELECT vote, count(*) AS n FROM beta_feedback GROUP BY vote")
        return {r["vote"]: int(r["n"]) for r in rows}

    # ---------------------------------------------------- bot / admin / state
    async def get_last_update_id(self, bot_name: str) -> Optional[int]:
        return await self.conn.fetchval(
            "SELECT last_update_id FROM beta_bot_update_state WHERE bot_name=$1", bot_name)

    async def set_last_update_id(self, bot_name: str, update_id: int) -> None:
        await self.conn.execute(
            """INSERT INTO beta_bot_update_state (bot_name, last_update_id) VALUES ($1,$2)
               ON CONFLICT (bot_name) DO UPDATE SET
                   last_update_id=GREATEST(beta_bot_update_state.last_update_id, EXCLUDED.last_update_id),
                   updated_at=now()""", bot_name, update_id)

    async def insert_audit(self, *, action: str, authorized: bool, actor_fingerprint: str,
                           target_fingerprint: Optional[str], result: str,
                           detail: Optional[Mapping] = None) -> None:
        await self.conn.execute(
            """INSERT INTO beta_admin_audit (action, authorized, actor_fingerprint, target_fingerprint,
                   result, detail) VALUES ($1,$2,$3,$4,$5,$6::jsonb)""",
            action, authorized, actor_fingerprint, target_fingerprint, result, _j(dict(detail or {})))

    async def get_admin_push_enabled(self) -> bool:
        v = await self.conn.fetchval(
            "SELECT bool_value FROM beta_runtime_state WHERE state_key='admin_push_enabled'")
        return bool(v) if v is not None else True

    async def set_admin_push_enabled(self, value: bool) -> None:
        await self.conn.execute(
            """INSERT INTO beta_runtime_state (state_key, bool_value) VALUES ('admin_push_enabled',$1)
               ON CONFLICT (state_key) DO UPDATE SET bool_value=EXCLUDED.bool_value, updated_at=now()""",
            value)

    async def record_health(self, component: str, *, now: datetime, success: bool,
                            error_type: Optional[str] = None,
                            detail: Optional[Mapping] = None) -> None:
        await self.conn.execute(
            """INSERT INTO beta_runtime_health (component, last_run_at, last_success_at,
                   last_error_type, detail)
               VALUES ($1,$2::timestamptz,CASE WHEN $3::boolean THEN $2::timestamptz END,$4,$5::jsonb)
               ON CONFLICT (component) DO UPDATE SET last_run_at=EXCLUDED.last_run_at,
                   last_success_at=CASE WHEN $3::boolean THEN EXCLUDED.last_run_at
                                        ELSE beta_runtime_health.last_success_at END,
                   last_error_type=EXCLUDED.last_error_type, detail=EXCLUDED.detail""",
            component, now, success, error_type, _j(dict(detail or {})))

    async def fetch_health(self) -> dict:
        rows = await self.conn.fetch(
            "SELECT component, last_run_at, last_success_at, last_error_type, detail "
            "FROM beta_runtime_health")
        return {r["component"]: {**dict(r), "detail": _load(r["detail"])} for r in rows}
