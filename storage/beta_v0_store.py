"""Beta V0.2 storage: static/trusted SQL over asyncpg for the beta_* tables only.

Never writes Stage-1, Stage-2 or frozen forecast tables. Reads Stage-1 raw
tables (klines_1m / connectivity_events) and the Stage-2 capability registry
read-only. Every method runs on ONE explicit connection (`BetaConn`), so callers
can group a bucket's writes into ONE transaction.

PRIVACY: Telegram identifiers are written to beta_allowlist, beta_users, and
beta_waitlist (only after the request button). Activity rows store user_pk, not
a Telegram id. A rejected /start stores an HMAC or a daily count. No method logs
an identifier.
"""
from __future__ import annotations

import contextlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from beta.access import PRIVACY_NOTICE_VERSION, generate_invite_code, rejected_hmac
from beta.models import Episode, TapeRecord

logger = logging.getLogger("beta.store")

BETA_SCHEMA_PATH = Path(__file__).resolve().parent / "beta_v0_schema.sql"
SCHEMA_LOCK_KEY = "beta_v0_schema_init"

# Session advisory-lock keys: a dedicated namespace, distinct from the shadow
# recovery / legacy telegram notifier keys.
DETECTOR_LOCK_KEY = 7_311_000_001
OUTCOMES_LOCK_KEY = 7_311_000_002
NOTIFIER_LOCK_KEY = 7_311_000_003
BOT_LOCK_KEY = 7_311_000_004
ACCESS_LOCK_KEY = 7_311_000_005
D7_LOCK_KEY = 7_311_000_006
HISTORY_LOCK_KEY = 7_311_000_007
FEEDS_LOCK_KEY = 7_311_000_008
STRESS_LOCK_KEY = 7_311_000_009

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
                                 calculation_version: str, state_schema_versions: Sequence[int],
                                 start: datetime, end: datetime,
                                 before_tape_id: Optional[int] = None) -> list:
        """Latest-recorded row per bucket in [start, end) among the given state-tape
        schema versions — `end` (the current bucket) is EXCLUDED by the predicate
        itself. `before_tape_id` restricts to rows recorded before that tape row (an
        exact as-of view: tape ids are assigned in recording order under the
        detector lock)."""
        rows = await self.conn.fetch(
            """SELECT DISTINCT ON (bucket_ts) bucket_ts, metrics
               FROM beta_state_tape
               WHERE symbol=$1 AND market_type=$2 AND timeframe=$3
                 AND calculation_version=$4 AND state_schema_version = ANY($5::int[])
                 AND materialized AND bucket_ts >= $6 AND bucket_ts < $7
                 AND ($8::bigint IS NULL OR tape_id < $8::bigint)
               ORDER BY bucket_ts, tape_id DESC""",
            symbol, market_type, timeframe, calculation_version, list(state_schema_versions), start, end,
            before_tape_id)
        # liquidation keys of rows written before the collector fix, read honestly (D2); OKX only
        # where its liquidation channel was alive (liveness marker)
        from beta.liq_mapping import LIVENESS_LEAD_S, apply_liveness, correct_metrics
        cutover = await self.fetch_liquidation_cutover(symbol=symbol)
        exchanges = ("binance", "bybit", "okx")
        beats = await self.fetch_liquidation_feed_heartbeats(
            symbol=symbol, start=start - timedelta(seconds=LIVENESS_LEAD_S), end=end)
        return [(r["bucket_ts"], apply_liveness(correct_metrics(_load(r["metrics"]), r["bucket_ts"], cutover,
                                                                exchanges), r["bucket_ts"], beats))
                for r in rows]

    async def fetch_liquidation_feed_heartbeats(self, *, symbol: str, start: datetime, end: datetime) -> dict:
        """{venue: [ts]} of the collector's liquidation-channel heartbeats in [start, end]; {} before the
        collector created the table (then no venue with a separate channel is measured)."""
        from beta.liq_mapping import LIVENESS_EXCHANGES
        has_table = getattr(self, "_has_heartbeats", None)
        if has_table is None:                              # one catalog probe per connection
            has_table = bool(await self.conn.fetchval(
                "SELECT to_regclass('liquidation_feed_heartbeats') IS NOT NULL"))
            self._has_heartbeats = has_table
        if not has_table:
            return {}
        # exchange first: the primary key (exchange, symbol, ts) serves the range read
        rows = await self.conn.fetch(
            """SELECT exchange, ts FROM liquidation_feed_heartbeats
               WHERE exchange = ANY($4::text[]) AND symbol=$1 AND ts >= $2 AND ts <= $3 ORDER BY ts""",
            symbol, start, end, list(LIVENESS_EXCHANGES))
        out: dict = {}
        for r in rows:
            out.setdefault(r["exchange"], []).append(r["ts"])
        return out

    async def fetch_live_tape_range(self, *, symbol: str, start: datetime, end: datetime,
                                    rules_digest: str) -> dict:
        """The detector's LIVE decision row per bucket in [start, end] (replay input)."""
        rows = await self.conn.fetch(
            """SELECT DISTINCT ON (bucket_ts) tape_id, bucket_ts, revision, snapshot_digest, snapshot
               FROM beta_state_tape WHERE symbol=$1 AND origin='LIVE' AND rules_digest=$2
                 AND bucket_ts >= $3 AND bucket_ts <= $4
               ORDER BY bucket_ts, tape_id DESC""", symbol, rules_digest, start, end)
        return {r["bucket_ts"]: {"tape_id": r["tape_id"], "revision": r["revision"],
                                 "snapshot_digest": r["snapshot_digest"], "snapshot": _load(r["snapshot"])}
                for r in rows}

    # ------------------------------------------------------------- temporal context
    async def fetch_latest_context_snapshot(self, *, symbol: str, before: datetime,
                                            episodization_digest: str, context_digest: str,
                                            rules_digest: str):
        r = await self.conn.fetchrow(
            """SELECT bucket_ts, state, state_digest FROM beta_context_snapshots
               WHERE symbol=$1 AND bucket_ts < $2 AND episodization_digest=$3
                 AND context_digest=$4 AND rules_digest=$5
               ORDER BY bucket_ts DESC LIMIT 1""",
            symbol, before, episodization_digest, context_digest, rules_digest)
        return None if r is None else {"bucket_ts": r["bucket_ts"], "state": _load(r["state"]),
                                       "state_digest": r["state_digest"]}

    async def fetch_context_snapshots(self, *, symbol: str, start: datetime, end: datetime,
                                      episodization_digest: str) -> list:
        rows = await self.conn.fetch(
            """SELECT bucket_ts, tape_id, prev_state_digest, state, state_digest FROM beta_context_snapshots
               WHERE symbol=$1 AND bucket_ts >= $2 AND bucket_ts <= $3 AND episodization_digest=$4
               ORDER BY bucket_ts""", symbol, start, end, episodization_digest)
        return [{**dict(r), "state": _load(r["state"])} for r in rows]

    async def insert_context_snapshot(self, state: Mapping[str, Any], *, bucket_ts: datetime,
                                      tape_id: Optional[int], tape_revision: Optional[int],
                                      prev_state_digest: Optional[str], state_digest: str) -> None:
        await self.conn.execute(
            """INSERT INTO beta_context_snapshots (symbol, bucket_ts, episodization_version,
                   episodization_digest, context_version, context_digest, rules_digest, tape_id,
                   tape_revision, prev_state_digest, state, state_digest)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12)""",
            state["symbol"], bucket_ts, state["episodization_version"], state["episodization_digest"],
            state["context_version"], state["context_digest"], state["rules_digest"], tape_id,
            tape_revision, prev_state_digest, _j(state), state_digest)

    async def fetch_latest_context_state(self, *, symbol: str, episodization_digest: str):
        r = await self.conn.fetchrow(
            """SELECT context_pk, bucket_ts, state, state_digest FROM beta_context_snapshots
               WHERE symbol=$1 AND episodization_digest=$2 ORDER BY bucket_ts DESC LIMIT 1""",
            symbol, episodization_digest)
        return None if r is None else {"bucket_ts": r["bucket_ts"], "state": _load(r["state"]),
                                       "state_digest": r["state_digest"], "context_pk": r["context_pk"]}

    async def insert_btc_view(self, *, requested_at: datetime, as_of_bucket: Optional[datetime],
                              context_state_digest: Optional[str], episodization_version: Optional[str],
                              episodization_digest: Optional[str], payload: Mapping[str, Any],
                              payload_digest: str, rendered_sha256: str, rendered_html: str,
                              lang: str = "ru", kind: str = "btc") -> int:
        return await self.conn.fetchval(
            """INSERT INTO beta_btc_views (requested_at, as_of_bucket, context_state_digest,
                   episodization_version, episodization_digest, payload, payload_digest,
                   rendered_sha256, rendered_html, lang, kind)
               VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10,$11)
               RETURNING view_pk""",
            requested_at, as_of_bucket, context_state_digest, episodization_version,
            episodization_digest, _j(payload), payload_digest, rendered_sha256, rendered_html, lang, kind)

    async def fetch_btc_view(self, view_pk: int):
        r = await self.conn.fetchrow(
            """SELECT view_pk, payload, payload_digest, lang, rendered_html, kind
               FROM beta_btc_views WHERE view_pk=$1""", view_pk)
        return None if r is None else {**dict(r), "payload": _load(r["payload"])}

    async def fetch_open_interest_asof(self, *, symbol: str, exchanges: Sequence[str],
                                       boundaries: Sequence[datetime]) -> dict:
        """Last ``open_interest`` row at or before each boundary, at most 2 minutes old.

        Mirrors the Stage-1 column set (exchange, symbol, ts, oi_raw, oi_unit) and
        adds ``contract_value``. One row per (exchange, symbol, ts) in Stage-1.
        Returns ``{boundary: {exchange: observation or None}}``.
        """
        from beta.oi_asof import OI_ASOF_TOLERANCE, pick_oi_asof
        out = {}
        for boundary in boundaries:
            rows = await self.conn.fetch(
                """SELECT exchange, ts, oi_raw, oi_unit, contract_value
                   FROM open_interest
                   WHERE symbol=$1 AND exchange = ANY($2::text[])
                     AND ts <= $3 AND ts >= $4
                   ORDER BY exchange, ts DESC""",
                symbol, list(exchanges), boundary, boundary - OI_ASOF_TOLERANCE)
            grouped: dict = {}
            for r in rows:
                grouped.setdefault(r["exchange"], []).append(dict(r))
            out[boundary] = {ex: pick_oi_asof(grouped.get(ex, []), boundary) for ex in exchanges}
        return out

    async def fetch_open_interest_range(self, *, symbol: str, exchanges: Sequence[str],
                                        start: datetime, end: datetime) -> list:
        """Every ``open_interest`` row in ``[start, end]`` for the venues, oldest first.
        Read-only; the as-of selection is ``beta.oi_asof.OiAsofIndex``."""
        rows = await self.conn.fetch(
            """SELECT exchange, ts, oi_raw, oi_unit, contract_value
               FROM open_interest
               WHERE symbol=$1 AND exchange = ANY($2::text[]) AND ts >= $3 AND ts <= $4
               ORDER BY exchange, ts""",
            symbol, list(exchanges), start, end)
        return [dict(r) for r in rows]

    async def insert_details_open(self, *, view_pk: int, tab: str, lang: str, opened_at: datetime) -> None:
        await self.conn.execute(
            """INSERT INTO beta_details_opens (view_pk, tab, lang, opened_at) VALUES ($1,$2,$3,$4)""",
            view_pk, tab, lang, opened_at)

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

    async def fetch_bucket_chain(self, *, symbol: str, bucket_ts: datetime,
                                 rules_digest: Optional[str]):
        """Every row for a bucket under one rules digest (None: under any), oldest first."""
        rows = await self.conn.fetch(
            "SELECT tape_id, origin, revision, feature_digest, snapshot_digest, calculation_version, "
            "rules_digest, state_schema_version "
            "FROM beta_state_tape WHERE symbol=$1 AND bucket_ts=$2 "
            "AND ($3::text IS NULL OR rules_digest=$3::text) "
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
        """Per venue: live-sourced 1m bar count in the bucket, the bucket's raw
        1m-kline OHLC (first open, max high, min low, last close) and the
        connectivity events needed to decide whether a logged outage overlaps it."""
        bars = await self.conn.fetch(
            "SELECT exchange, count(*) FILTER (WHERE source='live') AS live_bars, count(*) AS bars, "
            "(array_agg(open ORDER BY ts))[1] AS open, max(high) AS high, min(low) AS low, "
            "(array_agg(close ORDER BY ts DESC))[1] AS close "
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
            out[r["exchange"]].update(live_bars=int(r["live_bars"]), bars=int(r["bars"]),
                                      ohlc={k: (None if r[k] is None else float(r[k]))
                                            for k in ("open", "high", "low", "close")})
        for r in events:
            out[r["exchange"]]["events"].append(
                {"event_type": r["event_type"], "ts": r["ts"], "detail": _load(r["detail"]) or {}})
        return out

    async def fetch_stage1_startup_recovery(self, *, symbol: str) -> Optional[dict]:
        """The newest Stage-1 startup-recovery readiness row (common.startup_recovery)."""
        from common.startup_recovery import EXCHANGE, SOURCE
        row = await self.conn.fetchrow(
            "SELECT id, status, started_at, finished_at, rows_written, note FROM backfill_runs "
            "WHERE source=$1 AND exchange=$2 AND symbol=$3 ORDER BY id DESC LIMIT 1",
            SOURCE, EXCHANGE, symbol)
        return dict(row) if row else None

    async def fetch_decided_venue_bars(self, *, symbol: str, rules_digest: str,
                                       state_schema_version: int, start: datetime,
                                       end: datetime) -> dict:
        """bucket -> {venue: stored 1m-bar count} of each bucket's newest decided row
        (LIVE / CORRECTION_CHECK of this rules digest and schema) in [start, end]."""
        rows = await self.conn.fetch(
            """SELECT DISTINCT ON (bucket_ts) bucket_ts, snapshot->'venues' AS venues
               FROM beta_state_tape
               WHERE symbol=$1 AND origin IN ('LIVE','CORRECTION_CHECK') AND rules_digest=$2
                 AND state_schema_version=$3 AND bucket_ts >= $4 AND bucket_ts <= $5
               ORDER BY bucket_ts, tape_id DESC""",
            symbol, rules_digest, state_schema_version, start, end)
        return {r["bucket_ts"]: {ex: int((v or {}).get("bars") or 0)
                                 for ex, v in (_load(r["venues"]) or {}).items()} for r in rows}

    async def fetch_kline_bucket_counts(self, *, exchanges: Sequence[str], symbol: str,
                                        start: datetime, end: datetime) -> dict:
        """(5m bucket, venue) -> raw 1m-bar count (any source) for buckets in [start, end]."""
        rows = await self.conn.fetch(
            "SELECT to_timestamp(floor(extract(epoch FROM ts) / 300) * 300) AS bucket_ts, exchange, "
            "count(*) AS n FROM klines_1m WHERE exchange = ANY($1::text[]) AND symbol=$2 "
            "AND ts >= $3 AND ts < $4 GROUP BY 1, 2",
            list(exchanges), symbol, start, end + timedelta(minutes=5))
        return {(r["bucket_ts"], r["exchange"]): int(r["n"]) for r in rows}

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

    async def latest_any_would_push(self, *, exclude_pk: Optional[int]) -> Optional[datetime]:
        """Newest would-push decision of ANY event type (the global cooldown)."""
        return await self.conn.fetchval(
            "SELECT max(decision_ts) FROM beta_push_decisions WHERE would_push "
            "AND episode_pk IS DISTINCT FROM $1", exclude_pk)

    async def count_would_push(self, utc_day: date) -> int:
        return int(await self.conn.fetchval(
            "SELECT count(*) FROM beta_push_decisions WHERE utc_day=$1 AND would_push", utc_day))

    async def insert_push_decision(self, *, episode_pk: int, event_type: str,
                                   decision_ts: datetime, would_push: bool, decision: str,
                                   suppression_reason: Optional[str],
                                   push_enabled_effective: bool,
                                   gate: Optional[Mapping[str, Any]] = None) -> int:
        return await self.conn.fetchval(
            """INSERT INTO beta_push_decisions (episode_pk, event_type, decision_ts, utc_day,
                   would_push, decision, suppression_reason, push_enabled_effective, gate)
               VALUES ($1,$2,$3,($3 AT TIME ZONE 'UTC')::date,$4,$5,$6,$7,$8::jsonb) RETURNING decision_id""",
            episode_pk, event_type, decision_ts, would_push, decision, suppression_reason,
            push_enabled_effective, None if gate is None else _j(gate))

    async def fetch_qualified_hours(self, *, symbol: str, start: datetime, end: datetime) -> list:
        """Push decisions whose unusual-hour gate PASSED, decided in [start, end], oldest
        first. Delivery-side suppression is reported, never filtered (decision §3.1b.3)."""
        rows = await self.conn.fetch(
            """SELECT d.decision_id, d.decision_ts, d.decision, d.suppression_reason, d.gate, e.public_id, e.event_type
               FROM beta_push_decisions d JOIN beta_episodes e USING (episode_pk)
               WHERE e.symbol=$1 AND d.decision_ts >= $2 AND d.decision_ts <= $3
                 AND d.gate IS NOT NULL AND (d.gate->>'qualified')::boolean
               ORDER BY d.decision_ts, d.decision_id""", symbol, start, end)
        return [{**dict(r), "gate": _load(r["gate"])} for r in rows]

    async def own_push_reasons(self, user_pk: int, decision_ids: Sequence[int]) -> dict:
        """{decision_id: this participant's own outcome}: None when it was sent to them, else their
        delivery's suppression reason (review of #373: a note about an unsent hour is the reader's own)."""
        if not decision_ids:
            return {}
        rows = await self.conn.fetch(
            """SELECT decision_id, state, suppression_reason FROM beta_notification_deliveries
               WHERE kind='push' AND user_pk=$1 AND decision_id = ANY($2::bigint[])""",
            user_pk, [int(x) for x in decision_ids])
        return {r["decision_id"]: (None if r["state"] == "SENT" else r["suppression_reason"]) for r in rows}

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

    async def fetch_triggered_episodes(self, *, symbol: str, start: datetime, end: datetime) -> list:
        """Every TRIGGERED episode whose buckets reach into [start, end). Read-only (the
        gate coverage diagnostic)."""
        rows = await self.conn.fetch(
            """SELECT public_id, event_type, opened_bucket, last_bucket, triggered_at FROM beta_episodes
               WHERE symbol=$1 AND triggered_at IS NOT NULL AND opened_bucket < $3 AND last_bucket >= $2
               ORDER BY opened_bucket""", symbol, start, end)
        from beta.state_tape import iso
        return [{"episode_id": r["public_id"], "event_type": r["event_type"], "opened_bucket": iso(r["opened_bucket"]),
                 "last_bucket": iso(r["last_bucket"]), "triggered_at": iso(r["triggered_at"])} for r in rows]

    async def fetch_liquidation_episodes(self, *, symbol: str, start: datetime, end: datetime) -> list:
        """Triggered LIQUIDATION_STRESS episodes whose buckets reach into [start, end). Read-only."""
        rows = await self.conn.fetch(
            """SELECT public_id, event_type, opened_bucket, last_bucket, triggered_at FROM beta_episodes
               WHERE symbol=$1 AND event_type IN ('LIQUIDATION_STRESS_LONG', 'LIQUIDATION_STRESS_SHORT')
                 AND triggered_at IS NOT NULL AND opened_bucket < $3 AND last_bucket >= $2
               ORDER BY opened_bucket""", symbol, start, end)
        from beta.state_tape import iso
        return [{"episode_id": r["public_id"], "event_type": r["event_type"], "opened_bucket": iso(r["opened_bucket"]),
                 "last_bucket": iso(r["last_bucket"]), "triggered_at": iso(r["triggered_at"])} for r in rows]

    async def fetch_push_decisions_range(self, *, start: datetime, end: datetime) -> list:
        """Recorded push decisions with decision_ts in [start, end), oldest first. Read-only (C1 replay)."""
        rows = await self.conn.fetch(
            """SELECT decision_id, event_type, decision_ts, decision, suppression_reason, would_push
               FROM beta_push_decisions WHERE decision_ts >= $1 AND decision_ts < $2
               ORDER BY decision_ts, decision_id""", start, end)
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

    async def fetch_undispatched_push_decisions(self, limit: int, *, since: Optional[datetime] = None) -> list:
        """PUSH decisions without delivery rows. `since` bounds the scan: a decision nobody could
        receive (every participant had pushes off) never gets a row and must not stay at the head
        of every batch."""
        rows = await self.conn.fetch(
            """SELECT d.decision_id, d.episode_pk, d.decision_ts FROM beta_push_decisions d
               WHERE d.decision='PUSH' AND ($2::timestamptz IS NULL OR d.decision_ts >= $2::timestamptz)
                 AND NOT EXISTS (
                   SELECT 1 FROM beta_notification_deliveries x WHERE x.decision_id=d.decision_id)
               ORDER BY d.decision_ts, d.decision_id LIMIT $1""", limit, since)
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
               FROM beta_users u WHERE u.push_enabled AND u.push_hours
               ON CONFLICT (decision_id, user_pk) DO NOTHING""",
            decision_id, episode_pk, decision_ts, expired)
        return int(status.split()[-1])

    async def fetch_pending_deliveries(self, limit: int, *, now: Optional[datetime] = None) -> list:
        # `now`: while any row of a participant waits after flood control (next_attempt_at), every row of
        # that chat waits: the limit is the chat's, not one message's (review of #345)
        rows = await self.conn.fetch(
            """SELECT x.delivery_id, x.decision_id, x.episode_pk, x.user_pk, x.decision_ts,
                      u.chat_id, u.status AS user_status, u.lang AS user_lang, u.tz AS user_tz, d.gate
               FROM beta_notification_deliveries x JOIN beta_users u USING (user_pk)
               LEFT JOIN beta_push_decisions d ON d.decision_id = x.decision_id
               WHERE x.state='PENDING' AND x.kind='push'
                 AND ($2::timestamptz IS NULL OR NOT EXISTS (
                     SELECT 1 FROM beta_notification_deliveries wt WHERE wt.user_pk = x.user_pk
                       AND wt.state = 'PENDING' AND wt.next_attempt_at > $2))
               ORDER BY x.decision_ts, x.delivery_id LIMIT $1""", limit, now)
        return [{**dict(r), "gate": _load(r["gate"]) if r["gate"] is not None else None} for r in rows]

    # ---- morning briefing rows in the same outbox (kind = 'brief') ----------
    async def brief_scheduled(self, brief_date) -> bool:
        return bool(await self.conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM beta_notification_deliveries WHERE kind='brief' AND brief_date=$1)",
            brief_date))

    async def materialize_brief_deliveries(self, *, brief_date, view_pk: int, decision_ts: datetime) -> int:
        """One PENDING row per ACTIVE participant with the briefing on. The partial
        unique index (brief_date, user_pk) makes this idempotent."""
        status = await self.conn.execute(
            """INSERT INTO beta_notification_deliveries (kind, brief_date, view_pk, user_pk, state,
                   decision_ts)
               SELECT 'brief', $1, $2, u.user_pk, 'PENDING', $3
               FROM beta_users u WHERE u.status='ACTIVE' AND u.brief_enabled
               ON CONFLICT (brief_date, user_pk) WHERE kind='brief' DO NOTHING""",
            brief_date, view_pk, decision_ts)
        return int(status.split()[-1])

    async def fetch_pending_brief_deliveries(self, limit: int, *, now: Optional[datetime] = None) -> list:
        # `now`: while any row of a participant waits after flood control (next_attempt_at), every row of
        # that chat waits: the limit is the chat's, not one message's (review of #345)
        rows = await self.conn.fetch(
            """SELECT x.delivery_id, x.view_pk, x.brief_date, x.user_pk, x.decision_ts,
                      u.chat_id, u.status AS user_status, u.lang AS user_lang, u.tz AS user_tz, u.brief_enabled,
                      u.push_enabled, u.push_hours,
                      NOT EXISTS (SELECT 1 FROM beta_notification_deliveries y
                                  WHERE y.kind='brief' AND y.user_pk=x.user_pk AND y.state='SENT'
                                    AND y.brief_date < x.brief_date) AS first_brief
               FROM beta_notification_deliveries x JOIN beta_users u USING (user_pk)
               WHERE x.state='PENDING' AND x.kind='brief'
                 AND ($2::timestamptz IS NULL OR NOT EXISTS (
                     SELECT 1 FROM beta_notification_deliveries wt WHERE wt.user_pk = x.user_pk
                       AND wt.state = 'PENDING' AND wt.next_attempt_at > $2))
               ORDER BY x.decision_ts, x.delivery_id LIMIT $1""", limit, now)
        return [dict(r) for r in rows]

    # ---- weekly report rows in the same outbox (kind = 'weekly'; backlog B4) ----------
    async def weekly_report_payload(self, week_end) -> Optional[dict]:
        raw = await self.conn.fetchval("SELECT payload FROM beta_weekly_reports WHERE week_end=$1", week_end)
        return None if raw is None else _load(raw)

    async def weekly_report_pk(self, week_end) -> Optional[int]:
        return await self.conn.fetchval("SELECT weekly_pk FROM beta_weekly_reports WHERE week_end=$1", week_end)

    async def insert_weekly_report(self, *, week_end, built_at: datetime, payload: Mapping[str, Any],
                                   payload_digest: str) -> Optional[int]:
        """None when the week already has its report (append-only, one per week)."""
        return await self.conn.fetchval(
            """INSERT INTO beta_weekly_reports (week_end, built_at, payload, payload_digest)
               VALUES ($1,$2,$3::jsonb,$4) ON CONFLICT (week_end) DO NOTHING RETURNING weekly_pk""",
            week_end, built_at, _j(payload), payload_digest)

    async def materialize_weekly_deliveries(self, *, weekly_pk: int, decision_ts: datetime,
                                            tz: Optional[str] = None) -> int:
        """One PENDING row per ACTIVE participant with messages on and the weekly type on, in zone `tz`
        (None: Kyiv; review of #379: each zone at its own slot)."""
        status = await self.conn.execute(
            """INSERT INTO beta_notification_deliveries (kind, weekly_pk, user_pk, state, decision_ts)
               SELECT 'weekly', $1, u.user_pk, 'PENDING', $2
               FROM beta_users u WHERE u.status='ACTIVE' AND u.push_enabled AND u.push_weekly
                 AND u.tz IS NOT DISTINCT FROM $3
               ON CONFLICT (weekly_pk, user_pk) WHERE kind='weekly' DO NOTHING""",
            weekly_pk, decision_ts, tz)
        return int(status.split()[-1])

    async def fetch_pending_weekly_deliveries(self, limit: int, *, now: Optional[datetime] = None) -> list:
        # `now`: while any row of a participant waits after flood control (next_attempt_at), every row of
        # that chat waits: the limit is the chat's, not one message's (review of #345)
        rows = await self.conn.fetch(
            """SELECT x.delivery_id, x.weekly_pk, x.user_pk, x.decision_ts, w.payload,
                      u.chat_id, u.status AS user_status, u.lang AS user_lang, u.tz AS user_tz, u.push_enabled, u.push_weekly
               FROM beta_notification_deliveries x JOIN beta_users u USING (user_pk)
               JOIN beta_weekly_reports w ON w.weekly_pk = x.weekly_pk
               WHERE x.state='PENDING' AND x.kind='weekly'
                 -- a row before its recipient's own slot takes no place in the run's limit (review of #379)
                 AND ($2::timestamptz IS NULL OR x.decision_ts <= $2)
                 AND ($2::timestamptz IS NULL OR NOT EXISTS (
                     SELECT 1 FROM beta_notification_deliveries wt WHERE wt.user_pk = x.user_pk
                       AND wt.state = 'PENDING' AND wt.next_attempt_at > $2))
               ORDER BY x.decision_ts, x.delivery_id LIMIT $1""", limit, now)
        return [{**dict(r), "payload": _load(r["payload"])} for r in rows]

    async def long_short_summary(self, *, as_of: datetime) -> Optional[dict]:
        """Binance's long/short account ratio from the research feed (backlog G2): the latest value at most
        15 minutes before `as_of`, and the median of the means of the 30 prior 24h windows before the
        current one (a window counts with at least 144 of its 288 values). None without a recent value."""
        now_row = await self.conn.fetchrow(
            """SELECT ts, ls_account_ratio FROM beta_feed_metrics_5m
               WHERE ts <= $1::timestamptz AND ts > $1::timestamptz - interval '15 minutes'
                 AND ls_account_ratio IS NOT NULL
               ORDER BY ts DESC LIMIT 1""", as_of)
        if now_row is None:
            return None
        days = await self.conn.fetch(
            """SELECT avg(ls_account_ratio) AS m FROM beta_feed_metrics_5m
               WHERE ts > $1::timestamptz - interval '31 days' AND ts <= $1::timestamptz - interval '1 day'
                 AND ls_account_ratio IS NOT NULL
               GROUP BY floor(extract(epoch FROM $1::timestamptz - ts) / 86400) HAVING count(*) >= 144""", as_of)
        means = sorted(float(r["m"]) for r in days)
        n = len(means)
        med = None if n < 20 else (means[n // 2] if n % 2 else (means[n // 2 - 1] + means[n // 2]) / 2)
        return {"ratio": float(now_row["ls_account_ratio"]), "at": now_row["ts"].isoformat(),
                "typical": med, "n_days": n}

    # ---- owner-only signature index (/hypotheses; beta/signatures.py) ----------------------------
    async def last_signature_bucket(self, *, version: str) -> Optional[dict]:
        r = await self.conn.fetchrow(
            """SELECT bucket_ts, signature_key, sig_id FROM beta_signature_buckets WHERE version=$1
               ORDER BY bucket_ts DESC LIMIT 1""", version)
        return None if r is None else dict(r)

    async def context_buckets_after(self, *, symbol: str, episodization_digest: str, after: datetime,
                                    limit: int) -> list:
        """Closed buckets after `after`, oldest first: the newest context snapshot of each and its own
        tape row's rule evaluations (the liquidation votes)."""
        rows = await self.conn.fetch(
            """SELECT DISTINCT ON (c.bucket_ts) c.context_pk, c.bucket_ts, c.state,
                      t.snapshot->'rule_evaluations' AS rules
               FROM beta_context_snapshots c LEFT JOIN beta_state_tape t ON t.tape_id = c.tape_id
               WHERE c.symbol=$1 AND c.episodization_digest=$2 AND c.bucket_ts > $3
               ORDER BY c.bucket_ts, c.recorded_at DESC, c.context_pk DESC LIMIT $4""",
            symbol, episodization_digest, after, limit)
        return [{**dict(r), "state": _load(r["state"]),
                 "rules": _load(r["rules"]) if r["rules"] is not None else None} for r in rows]

    async def d7_states_asof(self, hours: Sequence[datetime]) -> dict:
        rows = await self.conn.fetch(
            """SELECT hour_start, state, available_at FROM beta_d7_hour_states
               WHERE hour_start = ANY($1::timestamptz[])""", list(hours))
        return {r["hour_start"]: dict(r) for r in rows}

    async def insert_signature_bucket(self, *, bucket_ts: datetime, version: str, key: str, sig_id: str,
                                      components: Mapping[str, Any], tail_count: int, episode_start: bool,
                                      context_pk: Optional[int], recorded_at: datetime) -> bool:
        status = await self.conn.execute(
            """INSERT INTO beta_signature_buckets (version, bucket_ts, signature_key, sig_id, components,
                   tail_count, episode_start, context_pk, recorded_at)
               VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,$8,$9) ON CONFLICT (version, bucket_ts) DO NOTHING""",
            version, bucket_ts, key, sig_id, _j(components), tail_count, episode_start, context_pk, recorded_at)
        return status == "INSERT 0 1"

    async def signature_summary(self, *, version: str) -> dict:
        r = await self.conn.fetchrow(
            """SELECT count(*) AS total, count(DISTINCT signature_key) AS signatures, min(bucket_ts) AS first_bucket
               FROM beta_signature_buckets WHERE version=$1""", version)
        return dict(r)

    _SIG_STATS = """SELECT signature_key AS key, min(sig_id) AS sig_id, (array_agg(components))[1] AS components,
                           max(tail_count) AS tail_count, count(*) AS n_buckets,
                           count(*) FILTER (WHERE episode_start) AS n_episodes,
                           count(DISTINCT (bucket_ts AT TIME ZONE 'UTC')::date) AS n_days,
                           min(bucket_ts) AS first_bucket, max(bucket_ts) AS last_bucket
                    FROM beta_signature_buckets WHERE version=$1 {where} GROUP BY signature_key"""

    async def signature_stats_all(self, *, version: str) -> list:
        rows = await self.conn.fetch(self._SIG_STATS.format(where=""), version)
        return [{**dict(r), "components": _load(r["components"])} for r in rows]

    async def signature_stats(self, *, version: str, sig_id: str) -> Optional[dict]:
        r = await self.conn.fetchrow(self._SIG_STATS.format(where="AND sig_id=$2"), version, sig_id)
        if r is None:
            return None
        total = int(await self.conn.fetchval("SELECT count(*) FROM beta_signature_buckets WHERE version=$1", version))
        return {**dict(r), "components": _load(r["components"]), "total": total}

    async def insert_hypothesis_review(self, *, version: str, key: str, sig_id: str, components: Mapping[str, Any],
                                       decision: str, hypothesis: Optional[str], window_from: datetime,
                                       window_to: datetime, seen: Mapping[str, Any], decided_at: datetime) -> Optional[int]:
        """None when the signature already has its decision (the first one is frozen)."""
        return await self.conn.fetchval(
            """INSERT INTO beta_hypothesis_reviews (version, signature_key, sig_id, components, decision, hypothesis,
                   window_from, window_to, seen, decided_at)
               VALUES ($1,$2,$3,$4::jsonb,$5,$6,$7,$8,$9::jsonb,$10)
               ON CONFLICT (version, signature_key) DO NOTHING RETURNING review_pk""",
            version, key, sig_id, _j(components), decision, hypothesis, window_from, window_to, _j(seen), decided_at)

    async def hypothesis_reviews(self, *, version: Optional[str] = None) -> list:
        rows = await self.conn.fetch(
            """SELECT review_pk, version, signature_key AS key, sig_id, components, decision, hypothesis,
                      window_from, window_to, seen, decided_at
               FROM beta_hypothesis_reviews WHERE $1::text IS NULL OR version=$1 ORDER BY review_pk""", version)
        return [{**dict(r), "components": _load(r["components"]), "seen": _load(r["seen"])} for r in rows]

    async def insert_hypothesis_pin(self, *, bucket_ts: datetime, version: str, key: str, sig_id: str,
                                    note: Optional[str], pinned_at: datetime) -> int:
        return await self.conn.fetchval(
            """INSERT INTO beta_hypothesis_pins (version, bucket_ts, signature_key, sig_id, note, pinned_at)
               VALUES ($1,$2,$3,$4,$5,$6) RETURNING pin_pk""", version, bucket_ts, key, sig_id, note, pinned_at)

    async def hypothesis_pins(self, *, version: str) -> list:
        rows = await self.conn.fetch(
            """SELECT bucket_ts, sig_id, note, pinned_at FROM beta_hypothesis_pins WHERE version=$1
               ORDER BY pin_pk""", version)
        return [dict(r) for r in rows]

    async def market_alert_counts(self, *, since: datetime, until: datetime) -> dict:
        """Market alerts the policy let through (decision PUSH) by kind; personal alerts excluded."""
        rows = await self.conn.fetch(
            """SELECT kind, count(*) AS n FROM beta_market_alerts
               WHERE decision='PUSH' AND kind <> 'price' AND decision_ts >= $1 AND decision_ts < $2
               GROUP BY kind""", since, until)
        return {r["kind"]: int(r["n"]) for r in rows}

    async def set_push_enabled(self, telegram_user_id: int, enabled: bool) -> bool:
        status = await self.conn.execute(
            "UPDATE beta_users SET push_enabled=$2, updated_at=now() WHERE telegram_user_id=$1",
            telegram_user_id, enabled)
        return status == "UPDATE 1"

    async def set_known_contact(self, telegram_user_id: int, known: bool) -> bool:
        status = await self.conn.execute(
            "UPDATE beta_users SET known_contact=$2, updated_at=now() WHERE telegram_user_id=$1",
            telegram_user_id, known)
        return status == "UPDATE 1"

    async def recipient_tzs(self, pref: str) -> list:
        """The time zones (None = Kyiv) of ACTIVE participants with pushes on and `pref` on (backlog C5)."""
        if pref not in ("push_hours", "push_levels", "push_events", "push_moves", "push_weekly"):
            raise ValueError(f"unknown push preference {pref!r}")
        rows = await self.conn.fetch(
            f"SELECT DISTINCT tz FROM beta_users WHERE status='ACTIVE' AND push_enabled AND {pref}")
        return [r["tz"] for r in rows]

    async def recipient_loads(self, pref: str, *, since: datetime, outbox_kind: str,
                              alert_kinds: Sequence[str] = ()) -> list:
        """{tz, times} for every ACTIVE participant with pushes and `pref` on: their zone and the decision
        times of their messages of this budget since `since` that are sent or still on the way (review of
        #373: each participant's own daily budget). `alert_kinds` narrows the market alerts to a budget."""
        if pref not in ("push_hours", "push_levels", "push_events", "push_moves", "push_weekly"):
            raise ValueError(f"unknown push preference {pref!r}")
        rows = await self.conn.fetch(
            f"""SELECT u.user_pk, u.tz,
                       array_remove(array_agg(x.decision_ts ORDER BY x.decision_ts), NULL) AS times
                FROM beta_users u
                LEFT JOIN beta_notification_deliveries x ON x.user_pk = u.user_pk AND x.kind = $2
                     AND x.decision_ts >= $1 AND x.state IN ('PENDING', 'SENDING', 'SENT', 'DELIVERY_UNKNOWN')
                     AND ($2 <> 'alert' OR EXISTS (SELECT 1 FROM beta_market_alerts a
                            WHERE a.alert_pk = x.alert_pk AND a.kind = ANY($3::text[])))
                WHERE u.status='ACTIVE' AND u.push_enabled AND u.{pref}
                GROUP BY u.user_pk, u.tz""", since, outbox_kind, list(alert_kinds))
        return [{"user_pk": r["user_pk"], "tz": r["tz"], "times": list(r["times"] or [])} for r in rows]

    async def count_sent_on_own_day(self, *, user_pk: int, ts: datetime, tz: Optional[str], outbox_kind: str,
                                    alert_kinds: Sequence[str] = (), before: Optional[datetime] = None) -> int:
        """How many messages of this budget the participant was sent, or may have been (SENDING, an
        ambiguous DELIVERY_UNKNOWN; review of #379), on their own calendar date of `ts` (their clock;
        review of #373), decided before `before` when given."""
        from beta.detector import own_day_bounds
        start, end = own_day_bounds(ts, tz)
        if before is not None:
            end = min(end, before)
        return int(await self.conn.fetchval(
            """SELECT count(*) FROM beta_notification_deliveries x
               WHERE x.user_pk = $1 AND x.kind = $2 AND x.state IN ('SENDING', 'SENT', 'DELIVERY_UNKNOWN')
                 AND x.decision_ts >= $3 AND x.decision_ts < $4
                 AND ($2 <> 'alert' OR EXISTS (SELECT 1 FROM beta_market_alerts a
                        WHERE a.alert_pk = x.alert_pk AND a.kind = ANY($5::text[])))""",
            user_pk, outbox_kind, start, end, list(alert_kinds)))

    async def set_user_tz(self, telegram_user_id: int, tz: Optional[str]) -> bool:
        """The participant's time zone (backlog C5); None = Kyiv. The caller validated it (i18n.parse_tz)."""
        status = await self.conn.execute(
            "UPDATE beta_users SET tz=$2, updated_at=now() WHERE telegram_user_id=$1", telegram_user_id, tz)
        return status == "UPDATE 1"

    async def set_trader_type(self, telegram_user_id: int, kind: Optional[str]) -> bool:
        """The participant's onboarding answer (backlog E5): scalp / intraday / swing / invest."""
        status = await self.conn.execute(
            "UPDATE beta_users SET trader_type=$2, updated_at=now() WHERE telegram_user_id=$1", telegram_user_id, kind)
        return status == "UPDATE 1"

    async def set_brief_time(self, telegram_user_id: int, hhmm: Optional[str]) -> bool:
        """The participant's briefing time on their own clock (backlog E3); None = the default."""
        status = await self.conn.execute(
            "UPDATE beta_users SET brief_time=$2, updated_at=now() WHERE telegram_user_id=$1", telegram_user_id, hhmm)
        return status == "UPDATE 1"

    async def brief_candidates(self) -> list:
        """ACTIVE participants with the briefing on: their zone, time and the date of their newest briefing row."""
        rows = await self.conn.fetch(
            """SELECT u.user_pk, u.tz, u.brief_time,
                      (SELECT max(x.brief_date) FROM beta_notification_deliveries x
                       WHERE x.kind='brief' AND x.user_pk=u.user_pk) AS last_brief_date
               FROM beta_users u WHERE u.status='ACTIVE' AND u.brief_enabled ORDER BY u.user_pk""")
        return [dict(r) for r in rows]

    async def materialize_brief_delivery(self, *, user_pk: int, brief_date, view_pk: int,
                                         decision_ts: datetime) -> int:
        """One participant's PENDING briefing row for their local date (idempotent on (brief_date, user_pk))."""
        status = await self.conn.execute(
            """INSERT INTO beta_notification_deliveries (kind, brief_date, view_pk, user_pk, state, decision_ts)
               VALUES ('brief', $1, $2, $3, 'PENDING', $4)
               ON CONFLICT (brief_date, user_pk) WHERE kind='brief' DO NOTHING""",
            brief_date, view_pk, user_pk, decision_ts)
        return int(status.split()[-1])

    async def set_brief_enabled(self, telegram_user_id: int, enabled: bool) -> bool:
        status = await self.conn.execute(
            "UPDATE beta_users SET brief_enabled=$2, updated_at=now() WHERE telegram_user_id=$1",
            telegram_user_id, enabled)
        return status == "UPDATE 1"

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

    async def requeue_delivery(self, delivery_id: int, *, error_summary: str, next_attempt_at: datetime) -> bool:
        """SENDING -> PENDING after Telegram's flood control (RetryAfter): the message was not
        delivered, so a later run may send it, not before `next_attempt_at` and under the same TTL
        (backlog A5). A PENDING row carries no `sending_at`; `error_summary` says why it waits."""
        status = await self.conn.execute(
            """UPDATE beta_notification_deliveries SET state='PENDING', sending_at=NULL, finished_at=NULL,
                   error_summary=$2, next_attempt_at=$3
               WHERE delivery_id=$1 AND state='SENDING'""", delivery_id, error_summary, next_attempt_at)
        return status == "UPDATE 1"

    async def delivery_state_counts(self, *, since: Optional[datetime] = None) -> dict:
        rows = await self.conn.fetch(
            "SELECT state, count(*) AS n FROM beta_notification_deliveries "
            "WHERE kind='push' AND ($1::timestamptz IS NULL OR created_at >= $1) GROUP BY state", since)
        return {r["state"]: int(r["n"]) for r in rows}

    async def delivery_problems(self, *, since: datetime) -> dict:
        """The owner's failure spike (every outbox kind): {"by_kind", "by_reason", "blocked"}.
        A problem is a FAILED row other than a participant who blocked the bot (`Forbidden:` is
        their choice, counted apart as `blocked`), a DELIVERY_UNKNOWN row, a row that expired
        undelivered, or a row waiting after Telegram's flood control."""
        rows = await self.conn.fetch(
            """SELECT kind,
                      CASE WHEN state = 'FAILED' AND error_summary LIKE 'Forbidden:%' THEN 'blocked'
                           WHEN state = 'FAILED' THEN 'failed'
                           WHEN state = 'DELIVERY_UNKNOWN' THEN 'unknown'
                           WHEN state = 'EXPIRED_UNDELIVERED' THEN 'expired'
                           ELSE 'throttled' END AS reason,
                      count(*) AS n
               FROM beta_notification_deliveries
               WHERE COALESCE(finished_at, created_at) >= $1
                 AND (state IN ('FAILED', 'DELIVERY_UNKNOWN')
                      OR (state = 'EXPIRED_UNDELIVERED' AND suppression_reason = 'DELIVERY_TOO_OLD')
                      OR (state = 'PENDING' AND next_attempt_at IS NOT NULL))
               GROUP BY 1, 2""", since)
        out: dict = {"by_kind": {}, "by_reason": {}, "blocked": 0}
        for r in rows:
            if r["reason"] == "blocked":
                out["blocked"] += int(r["n"])
                continue
            out["by_kind"][r["kind"]] = out["by_kind"].get(r["kind"], 0) + int(r["n"])
            out["by_reason"][r["reason"]] = out["by_reason"].get(r["reason"], 0) + int(r["n"])
        return out

    async def delivery_latency_rows(self, *, since: datetime) -> list:
        """Delivered and expired-undelivered rows finished since `since`, with the alert kind and
        the alert's source time (backlog A4; `beta.latency`). No user column."""
        rows = await self.conn.fetch(
            """SELECT d.kind, a.kind AS alert_kind, d.state, d.decision_ts, d.finished_at,
                      a.payload->>'source_at' AS source_at, d.decision_id, d.alert_pk, d.view_pk, d.weekly_pk
               FROM beta_notification_deliveries d
               LEFT JOIN beta_market_alerts a ON a.alert_pk = d.alert_pk
               WHERE d.state IN ('SENT', 'EXPIRED_UNDELIVERED')
                 AND COALESCE(d.finished_at, d.created_at) >= $1""", since)
        return [dict(r) for r in rows]

    async def push_decision_counts(self, *, since: datetime) -> list:
        rows = await self.conn.fetch(
            "SELECT decision, suppression_reason, count(*) AS n FROM beta_push_decisions "
            "WHERE decision_ts >= $1 GROUP BY decision, suppression_reason ORDER BY 1, 2", since)
        return [dict(r) for r in rows]

    async def cap_activation_days(self, *, since: datetime) -> int:
        return int(await self.conn.fetchval(
            "SELECT count(DISTINCT utc_day) FROM beta_push_decisions WHERE decision_ts >= $1 "
            "AND suppression_reason IN ('DAILY_CAP', 'DAILY_FUSE')", since))

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
            """SELECT user_pk, telegram_user_id, chat_id, status, joined_at, stopped_at, lang,
                      invite_code, privacy_notice_version, brief_enabled, push_enabled, known_contact,
                      push_levels, push_events, push_moves, push_hours, push_weekly, tz, brief_time, trader_type,
                      awaiting, awaiting_until, tier, onboarded_at
               FROM beta_users WHERE telegram_user_id=$1""", telegram_user_id)
        return None if r is None else dict(r)

    async def join_user(self, *, telegram_user_id: int, chat_id: int, now: datetime,
                        lang: str = "ru") -> int:
        return await self.conn.fetchval(
            """INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at,
                   joined_at, lang, invite_code, privacy_notice_version)
               VALUES ($1,$2,'ACTIVE',$3,$3,$4,
                   (SELECT invite_code FROM beta_allowlist WHERE telegram_user_id=$1), $5)
               ON CONFLICT (telegram_user_id) DO UPDATE SET status='ACTIVE', stopped_at=NULL,
                   chat_id=EXCLUDED.chat_id, privacy_accepted_at=EXCLUDED.privacy_accepted_at,
                   lang=EXCLUDED.lang, updated_at=now(),
                   privacy_notice_version=EXCLUDED.privacy_notice_version,
                   invite_code=COALESCE(beta_users.invite_code, EXCLUDED.invite_code)
               RETURNING user_pk""",
            telegram_user_id, chat_id, now, lang, PRIVACY_NOTICE_VERSION)

    async def set_user_lang(self, telegram_user_id: int, lang: str) -> bool:
        status = await self.conn.execute(
            "UPDATE beta_users SET lang=$2, updated_at=now() WHERE telegram_user_id=$1",
            telegram_user_id, lang)
        return status == "UPDATE 1"

    async def stop_user(self, *, telegram_user_id: int, now: datetime) -> bool:
        status = await self.conn.execute(
            "UPDATE beta_users SET status='STOPPED', stopped_at=$2, updated_at=now() "
            "WHERE telegram_user_id=$1 AND status='ACTIVE'", telegram_user_id, now)
        return status == "UPDATE 1"

    async def delete_participant(self, telegram_user_id: int) -> dict:
        """Delete the participant's personal beta records: user row (feedback and
        activity cascade; delivery rows keep only an anonymous NULL user_pk), the
        allowlist entry, and the waitlist row. Market/event records contain no
        identity and remain.

        `cohort` keeps the participant countable without identity
        (BETA_MEASUREMENT_CONTRACT_V1 §1.3, §1.5): the Kyiv join date, the known-contact
        flag and whether the join came at or after the test opening (`admin_test_open`),
        so the frozen enrollment rule can still count them. Nothing else per person."""
        from beta.i18n import KYIV
        row = await self.conn.fetchrow(
            "SELECT joined_at, known_contact FROM beta_users WHERE telegram_user_id=$1", telegram_user_id)
        cohort = None
        if row is not None and row["joined_at"] is not None:
            opened = await self.test_open_at()
            cohort = {"joined_kyiv_date": row["joined_at"].astimezone(KYIV).date().isoformat(),
                      "known_contact": bool(row["known_contact"]),
                      "joined_after_test_open": opened is not None and row["joined_at"] >= opened}
        activity = int(await self.conn.fetchval(
            """SELECT count(*) FROM beta_user_activity a
               JOIN beta_users u USING (user_pk) WHERE u.telegram_user_id=$1""",
            telegram_user_id))
        users = await self.conn.execute("DELETE FROM beta_users WHERE telegram_user_id=$1",
                                        telegram_user_id)
        allow = await self.conn.execute("DELETE FROM beta_allowlist WHERE telegram_user_id=$1",
                                        telegram_user_id)
        wait = await self.conn.execute("DELETE FROM beta_waitlist WHERE telegram_user_id=$1",
                                       telegram_user_id)
        return {"users": int(users.split()[-1]), "allowlist": int(allow.split()[-1]),
                "waitlist": int(wait.split()[-1]), "activity": activity, "cohort": cohort}

    async def mark_privacy_notice_seen(self, telegram_user_id: int, version: int) -> None:
        await self.conn.execute(
            "UPDATE beta_users SET privacy_notice_version=$2, updated_at=now() "
            "WHERE telegram_user_id=$1", telegram_user_id, version)

    # ------------------------------------------------- invites / access cap
    async def _lock_access(self) -> None:
        await self.conn.execute("SELECT pg_advisory_xact_lock($1)", ACCESS_LOCK_KEY)

    async def _allowlist_count_excluding_owner(self, owner_user_id: Optional[int]) -> int:
        if owner_user_id is None:
            return int(await self.conn.fetchval("SELECT count(*) FROM beta_allowlist"))
        return int(await self.conn.fetchval(
            "SELECT count(*) FROM beta_allowlist WHERE telegram_user_id <> $1", int(owner_user_id)))

    async def _allowlist_locked(self, telegram_user_id: int, max_active_users: int,
                                owner_user_id: Optional[int], invite_code: Optional[str]) -> str:
        """Caller holds the access lock. Returns OK, ALREADY, or CAP."""
        if await self.allowlist_contains(telegram_user_id):
            return "ALREADY"
        exempt = owner_user_id is not None and int(telegram_user_id) == int(owner_user_id)
        if not exempt:
            n = await self._allowlist_count_excluding_owner(owner_user_id)
            if n >= int(max_active_users):
                return "CAP"
        status = await self.conn.execute(
            "INSERT INTO beta_allowlist (telegram_user_id, invite_code) VALUES ($1,$2) "
            "ON CONFLICT DO NOTHING", int(telegram_user_id), invite_code)
        return "OK" if status.endswith(" 1") else "ALREADY"

    async def allowlist_with_cap(self, telegram_user_id: int, *, max_active_users: int,
                                 owner_user_id: Optional[int],
                                 invite_code: Optional[str] = None) -> str:
        """Allowlist one user under the active-user cap. The owner is exempt."""
        async with self.transaction():
            await self._lock_access()
            return await self._allowlist_locked(telegram_user_id, max_active_users,
                                                owner_user_id, invite_code)

    async def redeem_invite(self, code: str, telegram_user_id: int, now: datetime,
                            max_active_users: int, owner_user_id: Optional[int]) -> str:
        """One transaction: lock, validate the code, allowlist, increment used_count.

        Returns OK, ALREADY, CAP, MISSING, REVOKED, EXPIRED, or EXHAUSTED.
        ALREADY does not increment used_count. The owner skips only the cap.
        """
        async with self.transaction():
            await self._lock_access()
            row = await self.conn.fetchrow(
                """SELECT max_uses, used_count, expires_at, revoked_at
                   FROM beta_invites WHERE code=$1 FOR UPDATE""", code)
            if row is None:
                return "MISSING"
            if row["revoked_at"] is not None:
                return "REVOKED"
            if row["expires_at"] is not None and row["expires_at"] <= now:
                return "EXPIRED"
            if int(row["used_count"]) >= int(row["max_uses"]):
                return "EXHAUSTED"
            outcome = await self._allowlist_locked(
                telegram_user_id, max_active_users, owner_user_id, code)
            if outcome != "OK":
                return outcome
            await self.conn.execute(
                "UPDATE beta_invites SET used_count = used_count + 1 WHERE code=$1", code)
            return "OK"

    async def create_invite(self, *, label: str, max_uses: int, now: datetime,
                            expires_at: Optional[datetime] = None) -> str:
        label = (label or "").strip()
        if not label or int(max_uses) <= 0:
            raise ValueError("invalid invite")
        import asyncpg
        for _ in range(8):
            code = generate_invite_code()
            try:
                async with self.transaction():
                    await self.conn.execute(
                        """INSERT INTO beta_invites (code, label, max_uses, created_at, expires_at)
                           VALUES ($1,$2,$3,$4,$5)""",
                        code, label, int(max_uses), now, expires_at)
                return code
            except asyncpg.UniqueViolationError:
                continue
        raise RuntimeError("invite code collision")

    async def revoke_invite(self, code: str, now: datetime) -> str:
        from beta.access import INVITE_CODE_RE
        if not INVITE_CODE_RE.fullmatch(code or ""):
            return "INVALID"
        async with self.transaction():
            row = await self.conn.fetchrow(
                "SELECT revoked_at FROM beta_invites WHERE code=$1 FOR UPDATE", code)
            if row is None:
                return "MISSING"
            if row["revoked_at"] is not None:
                return "ALREADY"
            await self.conn.execute(
                "UPDATE beta_invites SET revoked_at=$2 WHERE code=$1", code, now)
            return "OK"

    async def list_invites(self) -> list:
        rows = await self.conn.fetch(
            """SELECT code, label, max_uses, used_count, created_at, expires_at, revoked_at
               FROM beta_invites ORDER BY created_at, code""")
        return [dict(r) for r in rows]

    # ------------------------------------------------------------- waitlist
    async def waitlist_add(self, telegram_user_id: int, now: datetime) -> bool:
        status = await self.conn.execute(
            """INSERT INTO beta_waitlist (telegram_user_id, requested_at) VALUES ($1,$2)
               ON CONFLICT DO NOTHING""", int(telegram_user_id), now)
        return status.endswith(" 1")

    async def waitlist_contains(self, telegram_user_id: int) -> bool:
        return bool(await self.conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM beta_waitlist WHERE telegram_user_id=$1)",
            telegram_user_id))

    async def waitlist_list(self, limit: int = 20) -> dict:
        count = int(await self.conn.fetchval("SELECT count(*) FROM beta_waitlist"))
        rows = await self.conn.fetch(
            """SELECT telegram_user_id, requested_at FROM beta_waitlist
               ORDER BY requested_at, telegram_user_id LIMIT $1""", limit)
        return {"count": count, "entries": [dict(r) for r in rows]}

    async def waitlist_remove(self, telegram_user_id: int) -> bool:
        status = await self.conn.execute(
            "DELETE FROM beta_waitlist WHERE telegram_user_id=$1", telegram_user_id)
        return status.endswith(" 1")

    # ---------------------------------------------------- activity telemetry
    async def record_activity(self, *, user_pk: int, action: str, lang: Optional[str],
                              at: datetime, detail: Optional[str] = None) -> bool:
        """Insert one activity row in its own savepoint. A failure never aborts
        the caller's transaction. The log line carries the exception type only."""
        try:
            async with self.transaction():
                await self.conn.execute(
                    """INSERT INTO beta_user_activity (user_pk, action, detail, lang, at)
                       VALUES ($1,$2,$3,$4,$5)""",
                    user_pk, action, detail, lang, at)
            return True
        except Exception as exc:  # noqa: BLE001 - telemetry must not fail the reply
            logger.warning("beta activity write failed: %s", type(exc).__name__)
            try:
                async with self.transaction():
                    await self._bump_telemetry_failure(at)
            except Exception as bump_exc:  # noqa: BLE001
                logger.warning("beta activity counter failed: %s", type(bump_exc).__name__)
            return False

    async def _bump_telemetry_failure(self, now: datetime) -> None:
        await self.conn.execute(
            """INSERT INTO beta_runtime_health (component, last_run_at, last_success_at,
                   last_error_type, detail)
               VALUES ('telemetry', $1::timestamptz, NULL, 'activity_write_failure',
                       '{"activity_write_failures": 1}'::jsonb)
               ON CONFLICT (component) DO UPDATE SET
                   last_run_at=EXCLUDED.last_run_at,
                   last_error_type=EXCLUDED.last_error_type,
                   detail=jsonb_set(
                       COALESCE(beta_runtime_health.detail, '{}'::jsonb),
                       '{activity_write_failures}',
                       to_jsonb(COALESCE((beta_runtime_health.detail->>'activity_write_failures')::int, 0) + 1))""",
            now)

    async def record_rejected_start(self, telegram_user_id: int, now: datetime,
                                    salt: Optional[str]) -> bool:
        """Store a daily HMAC, or a daily count when salt is unset. Never the raw id."""
        day = now.astimezone(timezone.utc).date() if now.tzinfo else now.date()
        try:
            async with self.transaction():
                if salt:
                    digest = rejected_hmac(salt, telegram_user_id)
                    await self.conn.execute(
                        """INSERT INTO beta_rejected_start_hashes (utc_day, user_hmac)
                           VALUES ($1,$2) ON CONFLICT DO NOTHING""", day, digest)
                else:
                    await self.conn.execute(
                        """INSERT INTO beta_rejected_start_counts (utc_day, attempt_count)
                           VALUES ($1, 1)
                           ON CONFLICT (utc_day) DO UPDATE
                           SET attempt_count = beta_rejected_start_counts.attempt_count + 1""",
                        day)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("beta rejected-start write failed: %s", type(exc).__name__)
            return False

    async def purge_activity_before(self, cutoff: datetime) -> int:
        status = await self.conn.execute(
            "DELETE FROM beta_user_activity WHERE at < $1", cutoff)
        return int(status.split()[-1])

    async def count_feedback_messages_on_utc_day(self, user_pk: int, day) -> int:
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        return int(await self.conn.fetchval(
            """SELECT count(*) FROM beta_feedback_messages
               WHERE user_pk=$1 AND created_at >= $2 AND created_at < $3""",
            user_pk, start, start + timedelta(days=1)))

    async def insert_feedback_message(self, *, user_pk: int, text: str, lang: str,
                                      created_at: datetime, kind: str = "feedback") -> int:
        """Free text: /feedback, an idea (H1) or an interview request (H4)."""
        return int(await self.conn.fetchval(
            """INSERT INTO beta_feedback_messages (user_pk, text, lang, created_at, kind)
               VALUES ($1,$2,$3,$4,$5) RETURNING message_pk""",
            user_pk, text, lang, created_at, kind))

    async def set_awaiting(self, telegram_user_id: int, what: Optional[str], until: Optional[datetime]) -> None:
        """The next plain message is `what` (H1: 'idea') until `until`; None clears it."""
        await self.conn.execute(
            "UPDATE beta_users SET awaiting=$2, awaiting_until=$3, updated_at=now() WHERE telegram_user_id=$1",
            telegram_user_id, what, until)

    async def upsert_reason(self, *, user_pk: int, topic: str, subject: str, reason: str, at: datetime) -> None:
        """H2 / H3: one answer per participant and subject; a second tap replaces it."""
        await self.conn.execute(
            """INSERT INTO beta_reasons (user_pk, topic, subject, reason, at) VALUES ($1,$2,$3,$4,$5)
               ON CONFLICT (user_pk, topic, subject) DO UPDATE SET reason=EXCLUDED.reason, at=EXCLUDED.at""",
            user_pk, topic, subject, reason, at)

    async def purge_feedback_messages_before(self, cutoff: datetime) -> int:
        status = await self.conn.execute(
            "DELETE FROM beta_feedback_messages WHERE created_at < $1", cutoff)
        return int(status.split()[-1])

    async def enrolled_user_rows(self) -> list:
        """ACTIVE and STOPPED participants (not deleted): /admin_reply and the U3 offer reach churned ones (J4, I2)."""
        rows = await self.conn.fetch(
            """SELECT user_pk, telegram_user_id, chat_id, lang, status
               FROM beta_users WHERE status IN ('ACTIVE', 'STOPPED') ORDER BY user_pk""")
        return [dict(r) for r in rows]

    async def set_onboarded(self, telegram_user_id: int, at: datetime) -> bool:
        status = await self.conn.execute(
            "UPDATE beta_users SET onboarded_at=$2, updated_at=now() WHERE telegram_user_id=$1 AND onboarded_at IS NULL",
            telegram_user_id, at)
        return status == "UPDATE 1"

    async def active_user_rows(self) -> list:
        rows = await self.conn.fetch(
            """SELECT user_pk, telegram_user_id, chat_id, lang
               FROM beta_users WHERE status='ACTIVE' ORDER BY user_pk""")
        return [dict(r) for r in rows]

    async def purge_rejected_starts_before(self, cutoff: datetime) -> int:
        day = cutoff.astimezone(timezone.utc).date() if cutoff.tzinfo else cutoff.date()
        hashes = await self.conn.execute(
            "DELETE FROM beta_rejected_start_hashes WHERE utc_day < $1", day)
        counts = await self.conn.execute(
            "DELETE FROM beta_rejected_start_counts WHERE utc_day < $1", day)
        return int(hashes.split()[-1]) + int(counts.split()[-1])

    async def usage_facts(self) -> dict:
        """Rows the usage report aggregates. The return value still has ids;
        only build_usage_report's result is shown to the owner."""
        # trader_type: the onboarding answer (backlog E5); NULL when not given
        users = await self.conn.fetch(
            """SELECT user_pk, telegram_user_id, status, lang, joined_at, invite_code, known_contact, trader_type
               FROM beta_users u""")
        activity = await self.conn.fetch(
            "SELECT user_pk, action, detail, at FROM beta_user_activity")
        # votes: the unusual-hour push (episodes) and every other message type (backlog F6)
        votes = await self.conn.fetch(
            """SELECT user_pk, 'hour' AS kind, vote, updated_at AS at FROM beta_feedback
               UNION ALL SELECT user_pk, kind, vote, updated_at AS at FROM beta_message_votes""")
        invites = await self.conn.fetch("SELECT code, label FROM beta_invites")
        deletions = await self.conn.fetch(
            """SELECT recorded_at FROM beta_admin_audit
               WHERE action='user_delete_me' AND authorized""")
        hashes = await self.conn.fetch(
            "SELECT utc_day, count(*) AS n FROM beta_rejected_start_hashes GROUP BY utc_day")
        counts = await self.conn.fetch(
            "SELECT utc_day, attempt_count FROM beta_rejected_start_counts")
        wait = int(await self.conn.fetchval("SELECT count(*) FROM beta_waitlist"))
        # backlog F5: which message each delivery was (the activity row knows only the type)
        deliveries = await self.conn.fetch(
            """SELECT d.kind, a.kind AS alert_kind, d.decision_id, d.alert_pk, d.brief_date, d.weekly_pk,
                      d.decision_ts, d.user_pk, d.finished_at AS at
               FROM beta_notification_deliveries d LEFT JOIN beta_market_alerts a ON a.alert_pk = d.alert_pk
               WHERE d.state = 'SENT' AND d.user_pk IS NOT NULL""")
        return {"users": [dict(r) for r in users],
                "deliveries": [dict(r) for r in deliveries],
                "activity": [dict(r) for r in activity],
                "votes": [dict(r) for r in votes],
                "invites": [dict(r) for r in invites],
                "deletions": [r["recorded_at"] for r in deletions],
                "rejected_hashes": [dict(r) for r in hashes],
                "rejected_counts": [dict(r) for r in counts],
                "waitlist_size": wait}

    async def stopped_users_before(self, cutoff: datetime) -> list:
        rows = await self.conn.fetch(
            "SELECT telegram_user_id FROM beta_users WHERE status='STOPPED' AND stopped_at < $1",
            cutoff)
        return [r["telegram_user_id"] for r in rows]

    async def list_users(self) -> list:
        rows = await self.conn.fetch(
            """SELECT a.telegram_user_id, u.status, u.joined_at, u.stopped_at, u.known_contact
               FROM beta_allowlist a LEFT JOIN beta_users u USING (telegram_user_id)
               UNION ALL
               SELECT u.telegram_user_id, u.status, u.joined_at, u.stopped_at, u.known_contact
               FROM beta_users u
               WHERE NOT EXISTS (SELECT 1 FROM beta_allowlist a WHERE a.telegram_user_id=u.telegram_user_id)
               ORDER BY 3 NULLS LAST""")
        return [dict(r) for r in rows]

    async def active_user_chats(self) -> list:
        rows = await self.conn.fetch("SELECT chat_id FROM beta_users WHERE status='ACTIVE' ORDER BY user_pk")
        return [r["chat_id"] for r in rows]

    async def user_counts(self) -> dict:
        rows = await self.conn.fetch("SELECT status, count(*) AS n FROM beta_users GROUP BY status")
        return {r["status"]: int(r["n"]) for r in rows}

    async def upsert_feedback(self, *, user_pk: int, episode_pk: int, vote: str) -> bool:
        """True when the vote is new or changed (a repeated tap changes nothing and is not an action)."""
        return await self.conn.fetchval(
            """INSERT INTO beta_feedback (user_pk, episode_pk, vote) VALUES ($1,$2,$3)
               ON CONFLICT (user_pk, episode_pk) DO UPDATE SET vote=EXCLUDED.vote, updated_at=now()
               WHERE beta_feedback.vote IS DISTINCT FROM EXCLUDED.vote
               RETURNING TRUE""", user_pk, episode_pk, vote) is not None

    async def upsert_message_vote(self, *, user_pk: int, kind: str, ref: int, vote: str) -> bool:
        """«Полезно / Шум» on an alert, the briefing or the weekly report (backlog F6). True when new or changed."""
        return await self.conn.fetchval(
            """INSERT INTO beta_message_votes (user_pk, kind, ref, vote) VALUES ($1,$2,$3,$4)
               ON CONFLICT (user_pk, kind, ref) DO UPDATE SET vote=EXCLUDED.vote, updated_at=now()
               WHERE beta_message_votes.vote IS DISTINCT FROM EXCLUDED.vote
               RETURNING TRUE""", user_pk, kind, ref, vote) is not None

    async def received_message(self, *, user_pk: int, kind: str, ref: int) -> bool:
        """Whether this participant was sent this message (review of #375: a vote counts only on a message
        its voter received): an alert of this kind by its alert_pk, the briefing by its view, the weekly
        report by its row. An ambiguous send (DELIVERY_UNKNOWN) counts: a tap on it shows it arrived."""
        if kind == "brief":
            where, ref_col = "d.kind='brief'", "d.view_pk"
        elif kind == "weekly":
            where, ref_col = "d.kind='weekly'", "d.weekly_pk"
        else:
            where, ref_col = "d.kind='alert' AND a.kind=$3", "d.alert_pk"
        return bool(await self.conn.fetchval(
            f"""SELECT EXISTS (SELECT 1 FROM beta_notification_deliveries d
                               LEFT JOIN beta_market_alerts a ON a.alert_pk = d.alert_pk
                               WHERE d.user_pk=$1 AND {ref_col}=$2 AND {where}
                                 AND d.state IN ('SENT', 'DELIVERY_UNKNOWN'))""",
            *((user_pk, ref, kind) if kind not in ("brief", "weekly") else (user_pk, ref))))

    async def feedback_counts(self) -> dict:
        rows = await self.conn.fetch(
            """SELECT vote, count(*) AS n FROM (SELECT vote FROM beta_feedback
                                              UNION ALL SELECT vote FROM beta_message_votes) v GROUP BY vote""")
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

    async def test_open_at(self) -> Optional[datetime]:
        """The test opening (`/admin_test_open`; the latest one if the owner forced a re-open), or None."""
        v = await self.conn.fetchval(
            """SELECT detail->>'test_open_at' FROM beta_admin_audit
               WHERE action='admin_test_open' AND authorized AND result='OK' AND detail ? 'test_open_at'
               ORDER BY audit_id DESC LIMIT 1""")
        return datetime.fromisoformat(v) if v else None

    async def derived_day0_kyiv(self, owner_user_id: Optional[int]):
        """Day 0 (contract §1.4, owner 2026-10-08): the Kyiv date of the first unknown participant who joined at
        or after the test opening, live rows and the de-identified cohort records of deleted ones together.
        None before the opening or before that join; a join before the opening never counts."""
        return (await self.derived_day0(owner_user_id))["day0_kyiv"]

    async def derived_day0(self, owner_user_id: Optional[int]) -> dict:
        """{"day0_kyiv", "provisional_until"}: Day 0 stays provisional until the first unknown joiner's 24-hour
        known-classification window closes (contract §1.2); a participant marked known in it moves Day 0 to the
        next unknown join. A deleted first joiner can no longer be reclassified, so their date is final."""
        from beta.i18n import KYIV
        opened = await self.test_open_at()
        if opened is None:
            return {"day0_kyiv": None, "provisional_until": None}
        first = await self.conn.fetchval(
            """SELECT min(joined_at) FROM beta_users
               WHERE joined_at >= $1 AND NOT known_contact AND telegram_user_id IS DISTINCT FROM $2""",
            opened, owner_user_id)
        days = [first.astimezone(KYIV).date()] if first is not None else []
        live_day = days[0] if days else None
        gone = await self.conn.fetchval(
            """SELECT min(detail->'cohort'->>'joined_kyiv_date') FROM beta_admin_audit
               WHERE action IN ('user_delete_me', 'retention_purge', 'admin_remove') AND detail ? 'cohort'
                 AND detail->>'cohort' <> 'null'
                 AND (detail->'cohort'->>'joined_after_test_open')::boolean
                 AND NOT (detail->'cohort'->>'known_contact')::boolean""")
        if gone:
            days.append(date.fromisoformat(gone))
        if not days:
            return {"day0_kyiv": None, "provisional_until": None}
        day0 = min(days)
        provisional = first + timedelta(hours=24) if live_day == day0 else None
        return {"day0_kyiv": day0, "provisional_until": provisional}

    async def u3_offer_sent(self) -> bool:
        """I2: whether /admin_offer send already went out (U3 is one offer)."""
        return bool(await self.conn.fetchval(
            """SELECT EXISTS (SELECT 1 FROM beta_admin_audit WHERE action='admin_offer' AND authorized
                   AND result='OK' AND detail ? 'recipients')"""))

    async def get_admin_push_enabled(self) -> bool:
        v = await self.conn.fetchval(
            "SELECT bool_value FROM beta_runtime_state WHERE state_key='admin_push_enabled'")
        return bool(v) if v is not None else True

    async def set_admin_push_enabled(self, value: bool) -> None:
        await self.conn.execute(
            """INSERT INTO beta_runtime_state (state_key, bool_value) VALUES ('admin_push_enabled',$1)
               ON CONFLICT (state_key) DO UPDATE SET bool_value=EXCLUDED.bool_value, updated_at=now()""",
            value)

    async def get_admin_d7_enabled(self) -> bool:
        """Missing row is off. Unlike push, the owner must turn the line on."""
        v = await self.conn.fetchval(
            "SELECT bool_value FROM beta_runtime_state WHERE state_key='admin_d7_enabled'")
        return bool(v) if v is not None else False

    async def set_admin_d7_enabled(self, value: bool) -> None:
        await self.conn.execute(
            """INSERT INTO beta_runtime_state (state_key, bool_value) VALUES ('admin_d7_enabled',$1)
               ON CONFLICT (state_key) DO UPDATE SET bool_value=EXCLUDED.bool_value, updated_at=now()""",
            value)

    async def record_health(self, component: str, *, now: datetime, success: bool,
                            error_type: Optional[str] = None,
                            detail: Optional[Mapping] = None) -> None:
        await self.conn.execute(
            """INSERT INTO beta_runtime_health (component, last_run_at, last_success_at,
                   last_error_type, detail, first_run_at)
               VALUES ($1,$2::timestamptz,CASE WHEN $3::boolean THEN $2::timestamptz END,$4,$5::jsonb,
                       $2::timestamptz)
               ON CONFLICT (component) DO UPDATE SET last_run_at=EXCLUDED.last_run_at,
                   first_run_at=COALESCE(beta_runtime_health.first_run_at, EXCLUDED.first_run_at),
                   last_success_at=CASE WHEN $3::boolean THEN EXCLUDED.last_run_at
                                        ELSE beta_runtime_health.last_success_at END,
                   last_error_type=EXCLUDED.last_error_type, detail=EXCLUDED.detail""",
            component, now, success, error_type, _j(dict(detail or {})))

    async def fetch_health(self, components: Optional[Sequence[str]] = None) -> dict:
        """Every component's row, or only `components` (the bot's dead-man reads two rows each poll)."""
        rows = await self.conn.fetch(
            "SELECT component, last_run_at, last_success_at, last_error_type, detail, first_run_at "
            "FROM beta_runtime_health WHERE $1::text[] IS NULL OR component = ANY($1::text[])",
            None if components is None else list(components))
        return {r["component"]: {**dict(r), "detail": _load(r["detail"])} for r in rows}

    # ------------------------------------------------------------------ D7 display feed
    async def upsert_d7_klines(self, rows: Sequence[Mapping]) -> None:
        if not rows:
            return
        await self.conn.executemany(
            """INSERT INTO beta_d7_klines_1m (open_time, open, high, low, close,
                   quote_asset_volume, close_time, fetched_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
               ON CONFLICT (open_time) DO UPDATE SET
                   open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                   close=EXCLUDED.close, quote_asset_volume=EXCLUDED.quote_asset_volume,
                   close_time=EXCLUDED.close_time, fetched_at=EXCLUDED.fetched_at""",
            [(r["open_time"], r["open"], r["high"], r["low"], r["close"],
              r["quote_asset_volume"], r["close_time"], r["fetched_at"]) for r in rows])

    async def d7_kline_bounds(self):
        r = await self.conn.fetchrow(
            "SELECT min(open_time) AS lo, max(open_time) AS hi FROM beta_d7_klines_1m")
        return r["lo"], r["hi"]

    async def fetch_d7_klines(self) -> list:
        rows = await self.conn.fetch(
            """SELECT open_time, open, high, low, close, quote_asset_volume, close_time
               FROM beta_d7_klines_1m ORDER BY open_time""")
        return [dict(r) for r in rows]

    async def insert_d7_hour_if_absent(self, *, hour_start: datetime, complete: bool,
                                       ret: Optional[float], quote_volume_1h: Optional[float],
                                       qrel: Optional[float], impact: Optional[float],
                                       p90: Optional[float], state: Optional[bool],
                                       available_at: datetime, computed_at: datetime,
                                       definition_digest: str) -> bool:
        wrote = await self.conn.fetchval(
            """INSERT INTO beta_d7_hour_states (hour_start, complete, ret, quote_volume_1h,
                   qrel, impact, p90, state, available_at, computed_at, definition_digest)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
               ON CONFLICT (hour_start) DO NOTHING
               RETURNING hour_start""",
            hour_start, complete, ret, quote_volume_1h, qrel, impact, p90, state,
            available_at, computed_at, definition_digest)
        return wrote is not None

    async def fetch_d7_hour_state(self, hour_start: datetime):
        r = await self.conn.fetchrow(
            """SELECT hour_start, complete, ret, quote_volume_1h, qrel, impact, p90, state,
                      available_at, computed_at, definition_digest
               FROM beta_d7_hour_states WHERE hour_start=$1""", hour_start)
        return None if r is None else dict(r)

    async def count_d7_valid_hours_before(self, hour_start: datetime) -> int:
        return int(await self.conn.fetchval(
            """SELECT count(*) FROM beta_d7_hour_states
               WHERE complete AND ret IS NOT NULL AND hour_start < $1""", hour_start))

    async def newest_d7_available_at(self) -> Optional[datetime]:
        return await self.conn.fetchval(
            "SELECT available_at FROM beta_d7_hour_states ORDER BY hour_start DESC LIMIT 1")

    # ------------------------------------------- decision support V2: history (Vision)
    async def hist_object_ledger(self) -> dict:
        rows = await self.conn.fetch("SELECT object_key, status, attempts FROM beta_hist_objects")
        return {r["object_key"]: {"status": r["status"], "attempts": r["attempts"]} for r in rows}

    async def record_hist_object(self, key: str, kind: str, *, status: str, now: datetime,
                                 sha256: Optional[str] = None, rows: Optional[int] = None) -> None:
        await self.conn.execute(
            """INSERT INTO beta_hist_objects (object_key, kind, status, sha256, row_count, attempts,
                   first_attempt_at, last_attempt_at)
               VALUES ($1,$2,$3,$4,$5,1,$6,$6)
               ON CONFLICT (object_key) DO UPDATE SET status=EXCLUDED.status, sha256=EXCLUDED.sha256,
                   row_count=EXCLUDED.row_count, attempts=beta_hist_objects.attempts + 1,
                   last_attempt_at=EXCLUDED.last_attempt_at""",
            key, kind, status, sha256, rows, now)

    async def upsert_hist_bars(self, rows: Sequence[Mapping], *, fetched_at: datetime) -> int:
        if not rows:
            return 0
        await self.conn.executemany(
            """INSERT INTO beta_hist_bars_5m (open_time, open, high, low, close, volume, quote_volume,
                   taker_buy_quote, trades, source, fetched_at)
               VALUES (to_timestamp($1::bigint / 1000.0), $2,$3,$4,$5,$6,$7,$8,$9,'vision',$10)
               ON CONFLICT (open_time) DO UPDATE SET open=EXCLUDED.open, high=EXCLUDED.high,
                   low=EXCLUDED.low, close=EXCLUDED.close, volume=EXCLUDED.volume,
                   quote_volume=EXCLUDED.quote_volume, taker_buy_quote=EXCLUDED.taker_buy_quote,
                   trades=EXCLUDED.trades, fetched_at=EXCLUDED.fetched_at""",
            [(int(r["open_time_ms"]), r["open"], r["high"], r["low"], r["close"], r.get("volume"),
              r.get("quote_volume"), r.get("taker_buy_quote"), r.get("trades"), fetched_at) for r in rows])
        return len(rows)

    async def upsert_hist_oi(self, rows: Sequence[Mapping], *, fetched_at: datetime) -> int:
        if not rows:
            return 0
        await self.conn.executemany(
            """INSERT INTO beta_hist_oi_5m (ts, oi_base, oi_usd, ls_account_ratio, source, fetched_at)
               VALUES (to_timestamp($1::bigint / 1000.0), $2, $3, $4, 'vision', $5)
               ON CONFLICT (ts) DO UPDATE SET oi_base=EXCLUDED.oi_base, oi_usd=EXCLUDED.oi_usd,
                   ls_account_ratio=EXCLUDED.ls_account_ratio, fetched_at=EXCLUDED.fetched_at""",
            [(int(r["ts_ms"]), r["oi_base"], r.get("oi_usd"), r.get("ls_account_ratio"), fetched_at)
             for r in rows])
        return len(rows)

    async def hist_bounds(self) -> dict:
        b = await self.conn.fetchrow(
            "SELECT min(open_time) AS lo, max(open_time) AS hi, count(*) AS n FROM beta_hist_bars_5m")
        o = await self.conn.fetchrow("SELECT min(ts) AS lo, max(ts) AS hi, count(*) AS n FROM beta_hist_oi_5m")
        return {"bars_from": b["lo"], "bars_through": b["hi"], "bars_count": int(b["n"]),
                "oi_from": o["lo"], "oi_through": o["hi"], "oi_count": int(o["n"])}

    async def fetch_hist_bars(self, *, start: datetime, end: datetime) -> list:
        rows = await self.conn.fetch(
            """SELECT (extract(epoch FROM open_time) * 1000)::bigint AS open_time_ms, open, high, low,
                      close, volume, quote_volume, taker_buy_quote
               FROM beta_hist_bars_5m WHERE open_time >= $1 AND open_time < $2 ORDER BY open_time""",
            start, end)
        return [dict(r) for r in rows]

    async def fetch_hist_oi(self, *, start: datetime, end: datetime) -> list:
        rows = await self.conn.fetch(
            """SELECT (extract(epoch FROM ts) * 1000)::bigint AS ts_ms, oi_base AS oi
               FROM beta_hist_oi_5m WHERE ts >= $1 AND ts < $2 ORDER BY ts""", start, end)
        return [dict(r) for r in rows]

    async def insert_hist_stats(self, *, version: str, built_at: datetime, data_from: Optional[datetime],
                                data_through: Optional[datetime], payload: Mapping[str, Any]) -> int:
        import hashlib
        body = _j(payload)
        return await self.conn.fetchval(
            """INSERT INTO beta_hist_stats (version, built_at, data_from, data_through, payload, payload_digest)
               VALUES ($1,$2,$3,$4,$5::jsonb,$6) RETURNING stats_pk""",
            version, built_at, data_from, data_through, body, hashlib.sha256(body.encode("utf-8")).hexdigest())

    async def fetch_latest_hist_stats(self) -> Optional[dict]:
        r = await self.conn.fetchrow(
            """SELECT stats_pk, version, built_at, data_from, data_through, payload, payload_digest
               FROM beta_hist_stats ORDER BY built_at DESC, stats_pk DESC LIMIT 1""")
        return None if r is None else {**dict(r), "payload": _load(r["payload"])}

    async def fetch_latest_hist_stats_meta(self) -> Optional[dict]:
        r = await self.conn.fetchrow(
            """SELECT stats_pk, version, built_at, data_through, payload_digest
               FROM beta_hist_stats ORDER BY built_at DESC, stats_pk DESC LIMIT 1""")
        return None if r is None else dict(r)

    # ------------------------------------------------ Stage-1 read-only (decision support)
    async def fetch_live_klines_1m(self, *, exchange: str, symbol: str, start: datetime,
                                   end: datetime) -> list:
        rows = await self.conn.fetch(
            """SELECT ts, open, high, low, close, volume, taker_buy_volume FROM klines_1m
               WHERE exchange=$1 AND symbol=$2 AND ts >= $3 AND ts < $4 ORDER BY ts""",
            exchange, symbol, start, end)
        return [dict(r) for r in rows]

    async def fetch_live_flow_15m(self, *, exchange: str, symbol: str, start: datetime, end: datetime) -> list:
        """Stage-1 1m klines summed into UTC 15-minute buckets (read-only): base volume, taker-buy
        base volume and how many of the 15 minutes are present (H05 needs complete buckets)."""
        rows = await self.conn.fetch(
            """SELECT (floor(extract(epoch FROM ts) / 900) * 900000)::bigint AS bucket_ms,
                      sum(volume) AS volume, sum(taker_buy_volume) AS taker_buy_volume,
                      count(*) AS minutes, count(taker_buy_volume) AS taker_minutes
               FROM klines_1m WHERE exchange=$1 AND symbol=$2 AND ts >= $3 AND ts < $4
               GROUP BY 1 ORDER BY 1""",
            exchange, symbol, start, end)
        return [dict(r) for r in rows]

    # ------------------------------------------------ research evidence feeds (read-only public data)
    async def db_role(self) -> dict:
        """The connected role and whether it is a superuser (catalog read only)."""
        row = await self.conn.fetchrow(
            "SELECT current_user::text AS name, r.rolsuper AS superuser FROM pg_roles r WHERE r.rolname = current_user")
        return {"name": row["name"], "superuser": bool(row["superuser"])}

    async def catalog_tables(self, names: Sequence[str]) -> dict:
        """{table: {present, columns, constraints, has_pk}} from the system catalog (read only; it
        needs no privilege on the tables themselves). Names resolve through the search path."""
        rows = await self.conn.fetch(
            """SELECT r.t AS name, c.oid IS NOT NULL AS present,
                      COALESCE((SELECT array_agg(a.attname::text) FROM pg_attribute a
                                WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped), '{}') AS columns,
                      COALESCE((SELECT array_agg(k.conname::text) FROM pg_constraint k
                                WHERE k.conrelid = c.oid), '{}') AS constraints,
                      EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conrelid = c.oid AND k.contype = 'p') AS has_pk
               FROM unnest($1::text[]) AS r(t)
               LEFT JOIN pg_class c ON c.oid = to_regclass(r.t) AND c.relkind IN ('r', 'p')""",
            list(names))
        return {r["name"]: {"present": bool(r["present"]), "columns": set(r["columns"]),
                            "constraints": set(r["constraints"]), "has_pk": bool(r["has_pk"])} for r in rows}

    async def table_privileges(self, wanted: Sequence[tuple]) -> dict:
        """{(table, privilege): bool} for the connected role; `wanted` holds existing tables only."""
        if not wanted:
            return {}
        rows = await self.conn.fetch(
            """SELECT w.t, w.p, has_table_privilege(to_regclass(w.t), w.p) AS ok
               FROM unnest($1::text[], $2::text[]) AS w(t, p)""",
            [t for t, _ in wanted], [p for _, p in wanted])
        return {(r["t"], r["p"]): bool(r["ok"]) for r in rows}

    async def column_privileges(self, wanted: Sequence[tuple]) -> dict:
        """{(table, column, privilege): bool}; `wanted` holds existing columns only."""
        if not wanted:
            return {}
        rows = await self.conn.fetch(
            """SELECT w.t, w.c, w.p, has_column_privilege(to_regclass(w.t), w.c, w.p) AS ok
               FROM unnest($1::text[], $2::text[], $3::text[]) AS w(t, c, p)""",
            [t for t, _, _ in wanted], [c for _, c, _ in wanted], [p for _, _, p in wanted])
        return {(r["t"], r["c"], r["p"]): bool(r["ok"]) for r in rows}

    async def fetch_hist_daily_rv(self, *, start: datetime, end: datetime) -> list:
        """Per UTC day of `beta_hist_bars_5m`: the number of 5m log returns whose previous bar is
        present, the sum of their squares (D2's RV_BTC_24H is sqrt of a full day's 288) and their
        sum (the day's log return; a zero return is ineligible in D2)."""
        rows = await self.conn.fetch(
            """WITH b AS (
                   SELECT open_time, close,
                          lag(close) OVER (ORDER BY open_time) AS prev_close,
                          lag(open_time) OVER (ORDER BY open_time) AS prev_time
                   FROM beta_hist_bars_5m WHERE open_time >= $1::timestamptz - interval '5 minutes'
                     AND open_time < $2::timestamptz)
               SELECT (extract(epoch FROM date_trunc('day', open_time)) * 1000)::bigint AS day_ms,
                      count(*) AS n, sum(ln(close / prev_close) ^ 2) AS sum_r2, sum(ln(close / prev_close)) AS sum_r
               FROM b WHERE open_time >= $1::timestamptz AND prev_time = open_time - interval '5 minutes'
                        AND prev_close > 0 AND close > 0
               GROUP BY 1 ORDER BY 1""",
            start, end)
        return [{"day_ms": int(r["day_ms"]), "n": int(r["n"]), "sum_r2": float(r["sum_r2"]), "sum_r": float(r["sum_r"])}
                for r in rows]

    async def fetch_hist_metrics(self, *, start: datetime, end: datetime) -> list:
        rows = await self.conn.fetch(
            """SELECT (extract(epoch FROM ts) * 1000)::bigint AS ts_ms, oi_base, ls_account_ratio
               FROM beta_hist_oi_5m WHERE ts >= $1 AND ts < $2 ORDER BY ts""", start, end)
        return [dict(r) for r in rows]

    async def upsert_feed_metrics(self, rows: Sequence[Mapping], *, fetched_at: datetime) -> int:
        if not rows:
            return 0
        await self.conn.executemany(
            """INSERT INTO beta_feed_metrics_5m (ts, oi_base, oi_usd, ls_account_ratio, source, fetched_at)
               VALUES (to_timestamp($1::bigint / 1000.0), $2, $3, $4, 'binance_futures_data', $5)
               ON CONFLICT (ts) DO UPDATE SET
                   oi_base=COALESCE(EXCLUDED.oi_base, beta_feed_metrics_5m.oi_base),
                   oi_usd=COALESCE(EXCLUDED.oi_usd, beta_feed_metrics_5m.oi_usd),
                   ls_account_ratio=COALESCE(EXCLUDED.ls_account_ratio, beta_feed_metrics_5m.ls_account_ratio),
                   fetched_at=EXCLUDED.fetched_at""",
            [(int(r["ts_ms"]), r.get("oi_base"), r.get("oi_usd"), r.get("ls_account_ratio"), fetched_at)
             for r in rows])
        return len(rows)

    async def fetch_feed_metrics(self, *, start: datetime, end: datetime) -> list:
        rows = await self.conn.fetch(
            """SELECT (extract(epoch FROM ts) * 1000)::bigint AS ts_ms, oi_base, ls_account_ratio
               FROM beta_feed_metrics_5m WHERE ts >= $1 AND ts < $2 ORDER BY ts""", start, end)
        return [dict(r) for r in rows]

    async def latest_feed_ts(self, table: str, column: str, *, where: str = "") -> Optional[datetime]:
        allowed = {("beta_feed_metrics_5m", "ts"), ("beta_feed_dvol_1h", "hour_start"),
                   ("beta_feed_spot_5m", "open_time"), ("beta_feed_depth", "ts"),
                   ("beta_feed_stress_hours", "hour_start")}
        if (table, column) not in allowed or where not in ("", "oi_base IS NOT NULL",
                                                           "ls_account_ratio IS NOT NULL"):
            raise ValueError(f"not a feed column: {table}.{column} {where}")
        return await self.conn.fetchval(
            f"SELECT max({column}) FROM {table}" + (f" WHERE {where}" if where else ""))

    async def upsert_feed_dvol(self, rows: Sequence[Mapping], *, fetched_at: datetime) -> int:
        if not rows:
            return 0
        await self.conn.executemany(
            """INSERT INTO beta_feed_dvol_1h (hour_start, open, high, low, close, source, fetched_at)
               VALUES (to_timestamp($1::bigint / 1000.0), $2, $3, $4, $5, 'deribit_dvol', $6)
               ON CONFLICT (hour_start) DO UPDATE SET open=EXCLUDED.open, high=EXCLUDED.high,
                   low=EXCLUDED.low, close=EXCLUDED.close, fetched_at=EXCLUDED.fetched_at""",
            [(int(r["t_ms"]), r["open"], r["high"], r["low"], r["close"], fetched_at) for r in rows])
        return len(rows)

    async def fetch_feed_dvol(self, *, start: datetime, end: datetime) -> list:
        rows = await self.conn.fetch(
            """SELECT (extract(epoch FROM hour_start) * 1000)::bigint AS t_ms, close
               FROM beta_feed_dvol_1h WHERE hour_start >= $1 AND hour_start < $2 ORDER BY hour_start""",
            start, end)
        return [dict(r) for r in rows]

    async def insert_feed_depth(self, row: Mapping, *, fetched_at: datetime) -> bool:
        wrote = await self.conn.fetchval(
            """INSERT INTO beta_feed_depth (ts, mid, bid1_usd, ask1_usd, bid_reach_pct, ask_reach_pct, levels,
                   source, fetched_at)
               VALUES (to_timestamp($1::bigint / 1000.0), $2, $3, $4, $5, $6, $7, 'binance_futures_depth', $8)
               ON CONFLICT (ts) DO NOTHING RETURNING 1""",
            int(row["ts_ms"]), row["mid"], row.get("bid1_usd"), row.get("ask1_usd"), row["bid_reach_pct"],
            row["ask_reach_pct"], int(row["levels"]), fetched_at)
        return wrote is not None

    async def fetch_feed_depth(self, *, start: datetime, end: datetime) -> list:
        rows = await self.conn.fetch(
            """SELECT (extract(epoch FROM ts) * 1000)::bigint AS ts_ms, bid1_usd, ask1_usd
               FROM beta_feed_depth WHERE ts >= $1 AND ts < $2 ORDER BY ts""", start, end)
        return [dict(r) for r in rows]

    async def upsert_feed_spot(self, rows: Sequence[Mapping], *, fetched_at: datetime) -> int:
        if not rows:
            return 0
        await self.conn.executemany(
            """INSERT INTO beta_feed_spot_5m (open_time, open, high, low, close, volume, quote_volume,
                   taker_buy_quote, trades, source, fetched_at)
               VALUES (to_timestamp($1::bigint / 1000.0), $2,$3,$4,$5,$6,$7,$8,$9,'binance_spot',$10)
               ON CONFLICT (open_time) DO UPDATE SET open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                   close=EXCLUDED.close, volume=EXCLUDED.volume, quote_volume=EXCLUDED.quote_volume,
                   taker_buy_quote=EXCLUDED.taker_buy_quote, trades=EXCLUDED.trades,
                   fetched_at=EXCLUDED.fetched_at""",
            [(int(r["open_time_ms"]), r["open"], r["high"], r["low"], r["close"], r["volume"], r["quote_volume"],
              r["taker_buy_quote"], r.get("trades"), fetched_at) for r in rows])
        return len(rows)

    async def fetch_feed_spot(self, *, start: datetime, end: datetime) -> list:
        rows = await self.conn.fetch(
            """SELECT (extract(epoch FROM open_time) * 1000)::bigint AS open_time_ms, close, quote_volume,
                      taker_buy_quote
               FROM beta_feed_spot_5m WHERE open_time >= $1 AND open_time < $2 ORDER BY open_time""",
            start, end)
        return [dict(r) for r in rows]

    async def upsert_feed_stress_hour(self, row: Mapping, *, now: datetime) -> bool:
        """One checked hour. A final row (anything but INCOMPLETE) is never replaced."""
        wrote = await self.conn.fetchval(
            """INSERT INTO beta_feed_stress_hours (hour_start, perp_log_range, status, lead_score, n_large_perp,
                   n_perp_trades, n_spot_trades, computed_at)
               VALUES (to_timestamp($1::bigint / 1000.0), $2, $3, $4, $5, $6, $7, $8)
               ON CONFLICT (hour_start) DO UPDATE SET perp_log_range=EXCLUDED.perp_log_range,
                   status=EXCLUDED.status, lead_score=EXCLUDED.lead_score, n_large_perp=EXCLUDED.n_large_perp,
                   n_perp_trades=EXCLUDED.n_perp_trades, n_spot_trades=EXCLUDED.n_spot_trades,
                   computed_at=EXCLUDED.computed_at
               WHERE beta_feed_stress_hours.status = 'INCOMPLETE'
               RETURNING 1""",
            int(row["hour_ms"]), float(row["perp_log_range"]), row["status"], row.get("lead_score"),
            row.get("n_large_perp"), row.get("n_perp_trades"), row.get("n_spot_trades"), now)
        return wrote is not None

    async def fetch_feed_stress_hours(self, *, start: datetime, end: datetime) -> list:
        rows = await self.conn.fetch(
            """SELECT (extract(epoch FROM hour_start) * 1000)::bigint AS hour_ms, perp_log_range, status,
                      lead_score, n_large_perp
               FROM beta_feed_stress_hours WHERE hour_start >= $1 AND hour_start < $2 ORDER BY hour_start""",
            start, end)
        return [dict(r) for r in rows]

    async def fetch_liquidations(self, *, symbol: str, exchanges: Sequence[str], start: datetime,
                                 end: datetime) -> list:
        """Raw rows, read honestly (beta.liq_mapping.correct_raw_rows): an old-mapping Bybit row
        with its side swapped; an old OKX row dropped. Raw bytes are never rewritten."""
        from beta.liq_mapping import correct_raw_rows
        version = "mapping_version" if await self._has_mapping_version() else "NULL::smallint AS mapping_version"
        rows = await self.conn.fetch(
            f"""SELECT exchange, ts, side, price, qty, notional, is_snapshot_feed, {version}
                FROM liquidations
                WHERE symbol=$1 AND exchange = ANY($2::text[]) AND ts >= $3 AND ts < $4""",
            symbol, list(exchanges), start, end)
        return correct_raw_rows(dict(r) for r in rows)

    async def _has_mapping_version(self) -> bool:
        """`liquidations.mapping_version` exists once the fixed collector applied storage/schema.sql
        (the beta never adds it: it must not lock the collector's table)."""
        return bool(await self.conn.fetchval(
            """SELECT EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid = to_regclass('liquidations')
                              AND attname = 'mapping_version' AND NOT attisdropped)"""))

    async def fetch_liquidation_cutover(self, *, symbol: str) -> dict:
        """{venue: {"first_new", "last_old"}} for Bybit and OKX: the first row written by the fixed
        collector and the last one written before it (docs/BETA_DATA_RELIABILITY_FIX_PLAN_V1.md D2).
        Immutable once both exist; memoized on this connection."""
        cache = getattr(self, "_liq_cutover", None)
        if cache is not None and symbol in cache:
            return cache[symbol]
        out: dict = {}
        has_column = await self._has_mapping_version()
        for ex in ("bybit", "okx"):
            first_new = last_old = None
            if has_column:
                first_new = await self.conn.fetchval(
                    """SELECT min(ts) FROM liquidations
                       WHERE exchange=$1 AND symbol=$2 AND mapping_version IS NOT NULL""", ex, symbol)
                last_old = await self.conn.fetchval(
                    """SELECT max(ts) FROM liquidations
                       WHERE exchange=$1 AND symbol=$2 AND mapping_version IS NULL""", ex, symbol)
            out[ex] = {"first_new": first_new, "last_old": last_old}
        self._liq_cutover = {**(cache or {}), symbol: out}
        return out

    # ------------------------------------------------------------- forecast tracking
    async def insert_forecast(self, *, horizon: str, issued_at: datetime, horizon_end: datetime,
                              anchor_price: float, lower: float, upper: float, coverage: float,
                              model_version: str, stats_pk: Optional[int]) -> bool:
        wrote = await self.conn.fetchval(
            """INSERT INTO beta_forecasts (horizon, issued_at, horizon_end, anchor_price, lower, upper,
                   coverage, model_version, stats_pk)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
               ON CONFLICT (horizon, issued_at) DO NOTHING RETURNING forecast_pk""",
            horizon, issued_at, horizon_end, anchor_price, lower, upper, coverage, model_version, stats_pk)
        return wrote is not None

    async def forecast_issued_since(self, *, horizon: str, since: datetime) -> bool:
        return bool(await self.conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM beta_forecasts WHERE horizon=$1 AND issued_at >= $2)",
            horizon, since))

    async def fetch_matured_forecasts(self, *, now: datetime, limit: int = 200) -> list:
        rows = await self.conn.fetch(
            """SELECT forecast_pk, horizon, issued_at, horizon_end, anchor_price, lower, upper
               FROM beta_forecasts WHERE outcome IS NULL AND horizon_end <= $1
               ORDER BY horizon_end LIMIT $2""", now, limit)
        return [dict(r) for r in rows]

    async def set_forecast_outcome(self, forecast_pk: int, *, outcome: str, high: Optional[float],
                                   low: Optional[float], now: datetime) -> None:
        await self.conn.execute(
            """UPDATE beta_forecasts SET outcome=$2, realized_high=$3, realized_low=$4, evaluated_at=$5
               WHERE forecast_pk=$1 AND outcome IS NULL""", forecast_pk, outcome, high, low, now)

    async def forecast_accuracy(self, *, since: datetime) -> dict:
        """{horizon: {outcome: count, 'N_EFF': non-overlapping windows}}. Forecasts are issued
        hourly, so 4h and 24h windows overlap; `N_EFF` counts the distinct UTC-aligned slots of
        one horizon length that hold a scored (INSIDE / OUTSIDE) forecast."""
        rows = await self.conn.fetch(
            """SELECT horizon, outcome, count(*) AS n
               FROM beta_forecasts WHERE issued_at >= $1 AND outcome IS NOT NULL
               GROUP BY horizon, outcome""", since)
        out: dict = {}
        for r in rows:
            out.setdefault(r["horizon"], {})[r["outcome"]] = int(r["n"])
        eff = await self.conn.fetch(
            """SELECT horizon, count(DISTINCT floor(extract(epoch FROM issued_at) /
                         CASE horizon WHEN '1h' THEN 3600 WHEN '4h' THEN 14400 ELSE 86400 END)) AS n_eff
               FROM beta_forecasts WHERE issued_at >= $1 AND outcome IN ('INSIDE', 'OUTSIDE')
               GROUP BY horizon""", since)
        for r in eff:
            out.setdefault(r["horizon"], {})["N_EFF"] = int(r["n_eff"])
        return out

    # ------------------------------------------------------- claim journal (append-only)
    async def insert_claim(self, row: Mapping[str, Any]) -> Optional[int]:
        """One claim; None when (class, subject, slot) is already journaled (idempotent writer)."""
        return await self.conn.fetchval(
            """INSERT INTO beta_claims (claim_class, level, issued_at, issue_slot, as_of, context_pk, stats_pk,
                   stats_digest, subject, subject_key, numbers, rule_version, template_id, template_digest,
                   eval_rule_id, eval_rule, eval_rule_digest, horizon_end, eligible_reason, claim_digest)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11::jsonb,$12,$13,$14,$15,$16::jsonb,$17,$18,$19,$20)
               ON CONFLICT (claim_class, subject_key, issue_slot) DO NOTHING RETURNING claim_pk""",
            row["claim_class"], row["level"], row["issued_at"], row["issue_slot"], row["as_of"],
            row.get("context_pk"), row.get("stats_pk"), row.get("stats_digest"), _j(row["subject"]),
            row["subject_key"], _j(row["numbers"]), row["rule_version"], row["template_id"],
            row["template_digest"], row["eval_rule_id"], _j(row["eval_rule"]), row["eval_rule_digest"],
            row["horizon_end"], row["eligible_reason"], row["claim_digest"])

    async def fetch_due_claims(self, *, now: datetime, limit: int = 500) -> list:
        """Claims whose horizon has passed and that have no outcome yet, oldest first."""
        rows = await self.conn.fetch(
            """SELECT c.claim_pk, c.claim_class, c.as_of, c.issue_slot, c.horizon_end, c.subject, c.numbers,
                      c.eval_rule, c.eval_rule_digest
               FROM beta_claims c
               WHERE c.horizon_end <= $1
                 AND NOT EXISTS (SELECT 1 FROM beta_claim_outcomes o WHERE o.claim_pk = c.claim_pk)
               ORDER BY c.horizon_end, c.claim_pk LIMIT $2""", now, limit)
        return [{**dict(r), "subject": _load(r["subject"]), "numbers": _load(r["numbers"]),
                 "eval_rule": _load(r["eval_rule"])} for r in rows]

    async def insert_claim_outcome(self, *, claim_pk: int, eval_rule_digest: str, status: str,
                                   realized: Mapping[str, Any], computed_at: datetime, outcome_digest: str,
                                   revision: int = 1, supersedes_outcome_pk: Optional[int] = None,
                                   correction_note: Optional[str] = None) -> Optional[int]:
        return await self.conn.fetchval(
            """INSERT INTO beta_claim_outcomes (claim_pk, eval_rule_digest, revision, supersedes_outcome_pk,
                   status, realized, computed_at, outcome_digest, correction_note)
               VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9)
               ON CONFLICT (claim_pk, revision) DO NOTHING RETURNING outcome_pk""",
            claim_pk, eval_rule_digest, revision, supersedes_outcome_pk, status, _j(realized), computed_at,
            outcome_digest, correction_note)

    async def fetch_slot_claims(self, *, issue_slot: datetime, classes: Sequence[str]) -> list:
        rows = await self.conn.fetch(
            """SELECT claim_pk, claim_class, subject_key FROM beta_claims
               WHERE issue_slot = $1 AND claim_class = ANY($2::text[])""", issue_slot, list(classes))
        return [dict(r) for r in rows]

    async def view_has_claim_displays(self, view_pk: int) -> bool:
        return bool(await self.conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM beta_claim_displays WHERE view_pk=$1)", view_pk))

    async def insert_claim_displays(self, rows: Sequence[Mapping[str, Any]]) -> int:
        n = 0
        for r in rows:
            await self.conn.execute(
                """INSERT INTO beta_claim_displays (claim_pk, surface, view_pk, alert_pk, shown_at)
                   VALUES ($1,$2,$3,$4,$5)""",
                r["claim_pk"], r["surface"], r.get("view_pk"), r.get("alert_pk"), r["shown_at"])
            n += 1
        return n

    async def touch_claim_cells(self, *, since: datetime, classes: Sequence[str]) -> list:
        """Scored L3 touch claims aggregated by (class, probability bin, UTC day, horizon slot):
        count, touches and the sum of stated chances (the live calibration of the «B» wording)."""
        rows = await self.conn.fetch(
            """SELECT c.claim_class,
                      width_bucket((c.numbers->>'probability')::float8,
                                   ARRAY[0.05, 0.15, 0.3, 0.5, 0.7, 0.85]::float8[]) AS bin,
                      floor(extract(epoch FROM c.as_of) / 86400)::bigint AS day,
                      -- the class suffix is the horizon: _1H, _4H or _24H (a 2-character suffix would
                      -- read _24H as 4H and split 24h claims into 4h slots)
                      floor(extract(epoch FROM c.as_of) /
                            ((regexp_match(c.claim_class, '_(1|4|24)H$'))[1]::int * 3600))::bigint AS slot,
                      count(*) AS n,
                      sum((COALESCE(o.realized->>'touched', o.realized->>'neither')::boolean)::int) AS hits,
                      sum((c.numbers->>'probability')::float8) AS psum
               FROM beta_claims c
               JOIN LATERAL (SELECT status, realized FROM beta_claim_outcomes x WHERE x.claim_pk = c.claim_pk
                             ORDER BY x.revision DESC LIMIT 1) o ON o.status = 'COMPLETE'
               WHERE c.as_of >= $1 AND c.claim_class = ANY($2::text[])
               GROUP BY 1, 2, 3, 4""", since, list(classes))
        return [dict(r) for r in rows]

    async def market_alert_pk(self, alert_key: str) -> Optional[int]:
        return await self.conn.fetchval("SELECT alert_pk FROM beta_market_alerts WHERE alert_key=$1", alert_key)

    async def fetch_claim_cohort(self, *, since: Optional[datetime] = None,
                                 classes: Optional[Sequence[str]] = None) -> list:
        """Claims with their newest outcome revision (if any) and whether any surface showed them."""
        rows = await self.conn.fetch(
            """SELECT c.claim_pk, c.claim_class, c.level, c.issue_slot, c.as_of, c.horizon_end, c.subject,
                      c.subject_key, c.numbers, c.rule_version, c.template_digest, c.eval_rule_digest,
                      c.eligible_reason, o.status, o.realized,
                      EXISTS (SELECT 1 FROM beta_claim_displays d WHERE d.claim_pk = c.claim_pk) AS shown
               FROM beta_claims c
               LEFT JOIN LATERAL (SELECT status, realized FROM beta_claim_outcomes x
                                  WHERE x.claim_pk = c.claim_pk ORDER BY x.revision DESC LIMIT 1) o ON TRUE
               WHERE ($1::timestamptz IS NULL OR c.issue_slot >= $1)
                 AND ($2::text[] IS NULL OR c.claim_class = ANY($2::text[]))
               ORDER BY c.claim_class, c.issue_slot, c.claim_pk""",
            since, list(classes) if classes is not None else None)
        return [{**dict(r), "subject": _load(r["subject"]), "numbers": _load(r["numbers"]),
                 "realized": _load(r["realized"]) if r["realized"] is not None else None} for r in rows]

    async def forecast_rows(self, *, since: datetime) -> list:
        """Scored corridor forecasts (INSIDE / OUTSIDE) since `since`, for the /accuracy breakdown."""
        rows = await self.conn.fetch(
            """SELECT horizon, issued_at, anchor_price, lower, upper, outcome, realized_high, realized_low
               FROM beta_forecasts WHERE issued_at >= $1 AND outcome IN ('INSIDE', 'OUTSIDE')
               ORDER BY issued_at""", since)
        return [dict(r) for r in rows]

    # ---------------------------------------------------------------- market alerts
    async def insert_market_alert(self, *, kind: str, alert_key: str, decision_ts: datetime,
                                  decision: str, suppression_reason: Optional[str],
                                  payload: Mapping[str, Any], target_user_pk: Optional[int] = None
                                  ) -> Optional[int]:
        return await self.conn.fetchval(
            """INSERT INTO beta_market_alerts (kind, alert_key, decision_ts, utc_day, decision,
                   suppression_reason, target_user_pk, payload)
               VALUES ($1,$2,$3,($3 AT TIME ZONE 'UTC')::date,$4,$5,$6,$7::jsonb)
               ON CONFLICT (alert_key) DO NOTHING RETURNING alert_pk""",
            kind, alert_key, decision_ts, decision, suppression_reason, target_user_pk, _j(payload))

    async def market_alert_keys(self, keys: Sequence[str]) -> set:
        rows = await self.conn.fetch(
            "SELECT alert_key FROM beta_market_alerts WHERE alert_key = ANY($1::text[])", list(keys))
        return {r["alert_key"] for r in rows}

    async def count_market_pushes(self, *, utc_day, kinds: Sequence[str]) -> int:
        return int(await self.conn.fetchval(
            """SELECT count(*) FROM beta_market_alerts
               WHERE utc_day=$1 AND kind = ANY($2::text[]) AND decision='PUSH'""", utc_day, list(kinds)))

    async def last_market_push_ts(self, *, kind: str) -> Optional[datetime]:
        return await self.conn.fetchval(
            "SELECT max(decision_ts) FROM beta_market_alerts WHERE kind=$1 AND decision='PUSH'", kind)

    async def fetch_market_alerts(self, *, start: datetime, end: datetime,
                                  kinds: Sequence[str] = ("level", "move")) -> list:
        rows = await self.conn.fetch(
            """SELECT alert_pk, kind, alert_key, decision_ts, decision, suppression_reason, payload
               FROM beta_market_alerts WHERE decision_ts >= $1 AND decision_ts < $2
                 AND kind = ANY($3::text[]) ORDER BY decision_ts""", start, end, list(kinds))
        return [{**dict(r), "payload": _load(r["payload"])} for r in rows]

    async def fetch_undispatched_market_alerts(self, limit: int) -> list:
        rows = await self.conn.fetch(
            """SELECT a.alert_pk, a.kind, a.decision_ts, a.target_user_pk FROM beta_market_alerts a
               WHERE a.decision='PUSH' AND a.dispatched_at IS NULL
               ORDER BY a.decision_ts, a.alert_pk LIMIT $1""", limit)
        return [dict(r) for r in rows]

    async def materialize_alert_deliveries(self, *, alert_pk: int, kind: str, decision_ts: datetime,
                                           target_user_pk: Optional[int], expired: bool,
                                           now: Optional[datetime] = None) -> int:
        """One row per recipient. Market kinds go to participants with push on and the kind's
        preference on; a personal price alert goes to its participant only. STOPPED
        participants get a SUPPRESSED row (as for the existing pushes). The alert is then marked
        dispatched, also when nobody qualified, so it never blocks later alerts."""
        pref = {"level": "push_levels", "event": "push_events", "move": "push_moves"}.get(kind)
        if kind in ("price", "approach"):
            where = "u.user_pk = $4::bigint"
        elif pref is not None:
            where = f"$4::bigint IS NULL AND u.push_enabled AND u.{pref}"
        else:
            raise ValueError(f"unknown alert kind {kind!r}")
        status = await self.conn.execute(
            f"""INSERT INTO beta_notification_deliveries (kind, alert_pk, user_pk, state,
                    suppression_reason, decision_ts)
                SELECT 'alert', $1, u.user_pk,
                       CASE WHEN $3::boolean THEN 'EXPIRED_UNDELIVERED'
                            WHEN u.status='ACTIVE' THEN 'PENDING' ELSE 'SUPPRESSED' END,
                       CASE WHEN $3::boolean THEN 'DELIVERY_TOO_OLD'
                            WHEN u.status='ACTIVE' THEN NULL ELSE 'USER_INACTIVE' END,
                       $2
                FROM beta_users u WHERE {where}
                ON CONFLICT (alert_pk, user_pk) WHERE kind='alert' DO NOTHING""",
            alert_pk, decision_ts, expired, target_user_pk if kind in ("price", "approach") else None)
        await self.conn.execute("UPDATE beta_market_alerts SET dispatched_at=$2 WHERE alert_pk=$1",
                                alert_pk, now or decision_ts)
        return int(status.split()[-1])

    async def fetch_pending_alert_deliveries(self, limit: int, *, now: Optional[datetime] = None) -> list:
        # `now`: while any row of a participant waits after flood control (next_attempt_at), every row of
        # that chat waits: the limit is the chat's, not one message's (review of #345)
        rows = await self.conn.fetch(
            """SELECT x.delivery_id, x.alert_pk, x.user_pk, x.decision_ts, a.kind, a.payload,
                      u.chat_id, u.status AS user_status, u.lang AS user_lang, u.tz AS user_tz
               FROM beta_notification_deliveries x JOIN beta_users u USING (user_pk)
               JOIN beta_market_alerts a ON a.alert_pk = x.alert_pk
               WHERE x.state='PENDING' AND x.kind='alert'
                 AND ($2::timestamptz IS NULL OR NOT EXISTS (
                     SELECT 1 FROM beta_notification_deliveries wt WHERE wt.user_pk = x.user_pk
                       AND wt.state = 'PENDING' AND wt.next_attempt_at > $2))
               ORDER BY x.decision_ts, x.delivery_id LIMIT $1""", limit, now)
        return [{**dict(r), "payload": _load(r["payload"])} for r in rows]

    # ------------------------------------------------------------ personal price alerts
    async def add_price_alert(self, *, user_pk: int, price: float, created_price: float, now: datetime,
                              max_active: int) -> Optional[int]:
        """None when the participant already has `max_active` active alerts."""
        n = int(await self.conn.fetchval(
            """SELECT count(*) FROM beta_price_alerts
               WHERE user_pk=$1 AND triggered_at IS NULL AND cancelled_at IS NULL""", user_pk))
        if n >= max_active:
            return None
        direction = "above" if price > created_price else "below"
        return await self.conn.fetchval(
            """INSERT INTO beta_price_alerts (user_pk, price, direction, created_at, created_price)
               VALUES ($1,$2,$3,$4,$5) RETURNING price_alert_pk""",
            user_pk, price, direction, now, created_price)

    async def list_price_alerts(self, user_pk: int) -> list:
        rows = await self.conn.fetch(
            """SELECT price_alert_pk, price, direction, created_at, created_price FROM beta_price_alerts
               WHERE user_pk=$1 AND triggered_at IS NULL AND cancelled_at IS NULL
               ORDER BY price""", user_pk)
        return [dict(r) for r in rows]

    async def cancel_price_alerts(self, user_pk: int, *, now: datetime,
                                  price_alert_pk: Optional[int] = None) -> int:
        status = await self.conn.execute(
            """UPDATE beta_price_alerts SET cancelled_at=$2
               WHERE user_pk=$1 AND triggered_at IS NULL AND cancelled_at IS NULL
                 AND ($3::bigint IS NULL OR price_alert_pk=$3::bigint)""", user_pk, now, price_alert_pk)
        return int(status.split()[-1])

    async def fetch_active_price_alerts(self) -> list:
        rows = await self.conn.fetch(
            """SELECT p.price_alert_pk, p.user_pk, p.price, p.direction, p.created_at, p.created_price,
                      p.approached_at
               FROM beta_price_alerts p JOIN beta_users u USING (user_pk)
               WHERE p.triggered_at IS NULL AND p.cancelled_at IS NULL AND u.status='ACTIVE'""")
        return [dict(r) for r in rows]

    async def mark_price_alert_approached(self, price_alert_pk: int, *, at: datetime) -> bool:
        status = await self.conn.execute(
            """UPDATE beta_price_alerts SET approached_at=$2
               WHERE price_alert_pk=$1 AND approached_at IS NULL AND triggered_at IS NULL AND cancelled_at IS NULL""",
            price_alert_pk, at)
        return status == "UPDATE 1"

    async def mark_price_alert_triggered(self, price_alert_pk: int, *, at: datetime) -> bool:
        status = await self.conn.execute(
            """UPDATE beta_price_alerts SET triggered_at=$2
               WHERE price_alert_pk=$1 AND triggered_at IS NULL AND cancelled_at IS NULL""",
            price_alert_pk, at)
        return status == "UPDATE 1"

    _PUSH_PREFS = ("push_enabled", "push_levels", "push_events", "push_moves", "push_hours", "push_weekly")

    async def set_push_pref(self, telegram_user_id: int, field: str, enabled: bool) -> bool:
        if field not in self._PUSH_PREFS:
            raise ValueError(f"unknown push preference {field!r}")
        status = await self.conn.execute(
            f"UPDATE beta_users SET {field}=$2, updated_at=now() WHERE telegram_user_id=$1",
            telegram_user_id, enabled)
        return status == "UPDATE 1"

    # ------------------------------------------------------ bootstrap rewind (operator)
    async def rewind_bootstrap_watermark(self, *, symbol: str, market_type: str, timeframe: str,
                                         bucket_ts: datetime) -> Optional[datetime]:
        """Set the bootstrap watermark back to `bucket_ts` (only ever earlier). The existing
        bounded bootstrap then refills missing current-schema tape rows from there; rows that
        exist are skipped, so nothing already recorded is rewritten."""
        prev = await self.get_watermark("bootstrap", symbol=symbol, market_type=market_type,
                                        timeframe=timeframe)
        await self.conn.execute(
            """INSERT INTO beta_detector_watermark (runner_name, symbol, market_type, timeframe, bucket_ts)
               VALUES ('bootstrap',$1,$2,$3,$4)
               ON CONFLICT (runner_name, symbol, market_type, timeframe) DO UPDATE
               SET bucket_ts = LEAST(beta_detector_watermark.bucket_ts, EXCLUDED.bucket_ts),
                   updated_at = now()""", symbol, market_type, timeframe, bucket_ts)
        return prev
