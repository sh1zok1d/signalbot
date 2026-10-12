"""PostgreSQL ledger for the paired shadow.

The production bot does not import this module. A caller has to pass ``allow_write=True``,
which stays off until the owner allows the hourly writer.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Mapping, Optional, Sequence
from urllib.parse import unquote, urlsplit

from beta.paired_shadow import ShadowConflict

UTC = timezone.utc


class PgShadowLedger:
    """The same keep-first rules as ``ShadowLedger``, stored in PostgreSQL."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def record_issues(self, rows: Sequence[Mapping], *, allow_write: bool = False) -> dict:
        from beta.paired_shadow import _require_recording
        _require_recording(allow_write)
        if not rows:
            return {"inserted": 0, "kept": 0}
        before = int(self._scalar("SELECT count(*) FROM beta_shadow_issues"))
        self._sql(_issues_sql(rows))
        after = int(self._scalar("SELECT count(*) FROM beta_shadow_issues"))
        inserted = after - before
        return {"inserted": inserted, "kept": len(rows) - inserted}

    def record_hour_statuses(self, rows: Sequence[Mapping], *, allow_write: bool = False) -> dict:
        from beta.paired_shadow import _require_recording
        _require_recording(allow_write)
        if not rows:
            return {"inserted": 0, "kept": 0}
        before = int(self._scalar("SELECT count(*) FROM beta_shadow_hour_status"))
        self._sql(_status_sql(rows))
        after = int(self._scalar("SELECT count(*) FROM beta_shadow_hour_status"))
        inserted = after - before
        return {"inserted": inserted, "kept": len(rows) - inserted}

    def record_outcome(self, anchor_key: str, *, status: str, outcome: Optional[int],
                       coverage: Optional[float], eval_rule_digest: str, computed_at: datetime,
                       revision: Optional[int] = None, correction_note: Optional[str] = None,
                       allow_write: bool = False) -> dict:
        from beta.paired_shadow import _require_recording, _utc
        _require_recording(allow_write)
        latest = self.latest_outcome(anchor_key)
        number = (1 if latest is None else latest["revision"] + 1) if revision is None else int(revision)
        if latest is not None and number == latest["revision"]:
            return {"revision": number, "stored": False}
        note_sql = "NULL" if not correction_note else _dollar(correction_note)
        supersedes = "NULL" if number == 1 else (
            "(SELECT outcome_pk FROM beta_shadow_outcomes WHERE anchor_pk = a.anchor_pk "
            f"AND revision = {number - 1})"
        )
        outcome_sql = "NULL" if outcome is None else str(int(outcome))
        coverage_sql = "NULL" if coverage is None else _float(coverage)
        self._sql(f"""
            INSERT INTO beta_shadow_outcomes (
                anchor_pk, revision, supersedes_outcome_pk, status, outcome, coverage,
                eval_rule_digest, computed_at, correction_note)
            SELECT a.anchor_pk, {number}, {supersedes}, {_dollar(status)}, {outcome_sql},
                   {coverage_sql}, {_dollar(eval_rule_digest)}, {_time(_utc(computed_at))}, {note_sql}
            FROM beta_shadow_anchors a
            WHERE a.anchor_key = {_dollar(anchor_key)}
        """)
        return {"revision": number, "stored": True}

    def latest_outcome(self, anchor_key: str) -> Optional[dict]:
        raw = self._scalar(f"""
            SELECT row_to_json(x) FROM (
                SELECT o.revision, o.status, o.outcome, o.coverage
                FROM beta_shadow_outcomes o
                JOIN beta_shadow_anchors a USING (anchor_pk)
                WHERE a.anchor_key = {_dollar(anchor_key)}
                ORDER BY o.revision DESC
                LIMIT 1
            ) x
        """)
        if not raw:
            return None
        loaded = json.loads(raw)
        return {
            "revision": loaded["revision"],
            "status": loaded["status"],
            "outcome": loaded["outcome"],
            "coverage": loaded["coverage"],
        }

    def due_unscored(self, now: datetime, *, limit: int) -> list:
        """Elapsed anchors with no outcome. The query is limited; it does not read the issue journal."""
        if limit < 1:
            raise ValueError("limit must be positive")
        moment = now.astimezone(UTC)
        raw = self._scalar(f"""
            SELECT coalesce(json_agg(row_to_json(x)), '[]'::json)
            FROM (
                SELECT a.anchor_key, a.symbol, a.family, a.horizon,
                       to_char(a.issue_slot AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS issue_slot,
                       to_char(a.as_of AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS as_of,
                       to_char(a.horizon_end AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS horizon_end,
                       a.side, a.distance_pct, a.distance_up_pct, a.distance_down_pct,
                       a.level_up, a.level_down, a.eval_rule_id, a.eval_rule_digest
                FROM beta_shadow_anchors a
                WHERE a.horizon_end <= {_time(moment)}
                  AND NOT EXISTS (
                      SELECT 1 FROM beta_shadow_outcomes o WHERE o.anchor_pk = a.anchor_pk
                  )
                ORDER BY a.horizon_end, a.anchor_key
                LIMIT {int(limit)}
            ) x
        """)
        rows = json.loads(raw or "[]")
        for row in rows:
            for field in ("issue_slot", "as_of", "horizon_end"):
                row[field] = datetime.fromisoformat(row[field].replace("Z", "+00:00")).astimezone(UTC)
        return rows

    def joined_rows(self) -> list:
        raw = self._scalar("""
            SELECT coalesce(json_agg(row_to_json(x) ORDER BY x.anchor_key, x.procedure_id, x.spec_id), '[]'::json)
            FROM (
                SELECT a.anchor_key, a.symbol, a.family, a.horizon,
                       to_char(a.issue_slot AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS issue_slot,
                       to_char(a.as_of AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS as_of,
                       to_char(a.horizon_end AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS horizon_end,
                       a.side, a.distance_pct, a.distance_up_pct, a.distance_down_pct,
                       a.level_up, a.level_down, a.eval_rule_id, a.eval_rule_digest,
                       i.procedure_id, i.spec_id, i.spec_digest, i.snapshot_id, i.probability,
                       o.status, o.outcome, o.coverage, o.revision AS outcome_revision
                FROM beta_shadow_issues i
                JOIN beta_shadow_anchors a USING (anchor_pk)
                LEFT JOIN LATERAL (
                    SELECT status, outcome, coverage, revision
                    FROM beta_shadow_outcomes x
                    WHERE x.anchor_pk = a.anchor_pk
                    ORDER BY x.revision DESC
                    LIMIT 1
                ) o ON TRUE
            ) x
        """)
        rows = json.loads(raw or "[]")
        for row in rows:
            for field in ("issue_slot", "as_of", "horizon_end"):
                row[field] = datetime.fromisoformat(row[field].replace("Z", "+00:00")).astimezone(UTC)
        return rows

    def _scalar(self, sql: str) -> str:
        completed = self._run(sql)
        return completed.stdout.strip()

    def _sql(self, sql: str) -> None:
        self._run(sql)

    def _run(self, sql: str) -> subprocess.CompletedProcess:
        argv, env = psql_invocation(self.dsn)
        completed = subprocess.run(
            argv, input=sql, capture_output=True, text=True, check=False, env=env,
        )
        if completed.returncode != 0:
            message = redact_connection(completed.stderr or completed.stdout, self.dsn)
            if "spec_digest" in message or "already frozen" in message or "already has status" in message:
                raise ShadowConflict(message.strip())
            raise RuntimeError(message.strip())
        return completed


def psql_invocation(dsn: str, *, extra: Sequence[str] = ()) -> tuple:
    """``psql`` argv and environment. The URL and the password are not arguments."""
    parts = urlsplit(dsn)
    database = unquote(parts.path.lstrip("/"))
    if not database or "/" in database:
        raise RuntimeError("paired shadow database name is missing")
    env = os.environ.copy()
    for key in ("PGHOST", "PGPORT", "PGUSER", "PGPASSWORD", "PGDATABASE"):
        env.pop(key, None)
    env["PGDATABASE"] = database
    if parts.hostname:
        env["PGHOST"] = parts.hostname
    if parts.port:
        env["PGPORT"] = str(parts.port)
    if parts.username:
        env["PGUSER"] = unquote(parts.username)
    if parts.password:
        env["PGPASSWORD"] = unquote(parts.password)
    argv = ["psql", "-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-1", *extra]
    return argv, env


def redact_connection(text: str, dsn: str) -> str:
    """Drop the URL and the password from a client error before it is printed."""
    if not text:
        return ""
    parts = urlsplit(dsn)
    secret = unquote(parts.password) if parts.password else ""
    cleaned = text.replace(dsn, "[dsn]")
    if secret:
        cleaned = cleaned.replace(secret, "[redacted]")
    return cleaned


def _issues_sql(rows: Sequence[Mapping]) -> str:
    parts = []
    for row in rows:
        key = _dollar(row["anchor_key"])
        parts.append(f"""
            INSERT INTO beta_shadow_anchors (
                anchor_key, symbol, family, horizon, issue_slot, as_of, horizon_end, side,
                distance_pct, distance_up_pct, distance_down_pct, level_up, level_down,
                eval_rule_id, eval_rule_digest)
            VALUES (
                {key}, {_dollar(row['symbol'])}, {_dollar(row['family'])}, {_dollar(row['horizon'])},
                {_time(row['issue_slot'])}, {_time(row['as_of'])}, {_time(row['horizon_end'])},
                {_int(row.get('side'))}, {_float(row.get('distance_pct'))}, {_float(row.get('distance_up_pct'))},
                {_float(row.get('distance_down_pct'))}, {_float(row.get('level_up'))}, {_float(row.get('level_down'))},
                {_dollar(row['eval_rule_id'])}, {_dollar(row['eval_rule_digest'])})
            ON CONFLICT (anchor_key) DO NOTHING;
            DO $check$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM beta_shadow_anchors
                    WHERE anchor_key = {key}
                      AND family = {_dollar(row['family'])}
                      AND horizon = {_dollar(row['horizon'])}
                      AND issue_slot = {_time(row['issue_slot'])}
                      AND as_of = {_time(row['as_of'])}
                      AND horizon_end = {_time(row['horizon_end'])}
                      AND side IS NOT DISTINCT FROM {_int(row.get('side'))}
                      AND distance_pct IS NOT DISTINCT FROM {_float(row.get('distance_pct'))}
                      AND distance_up_pct IS NOT DISTINCT FROM {_float(row.get('distance_up_pct'))}
                      AND distance_down_pct IS NOT DISTINCT FROM {_float(row.get('distance_down_pct'))}
                      AND level_up IS NOT DISTINCT FROM {_float(row.get('level_up'))}
                      AND level_down IS NOT DISTINCT FROM {_float(row.get('level_down'))}
                      AND eval_rule_id = {_dollar(row['eval_rule_id'])}
                      AND eval_rule_digest = {_dollar(row['eval_rule_digest'])}
                ) THEN
                    RAISE EXCEPTION 'anchor % was already frozen', {key}
                        USING ERRCODE = 'check_violation';
                END IF;
            END
            $check$;
            INSERT INTO beta_shadow_issues (
                anchor_pk, procedure_id, spec_id, spec_digest, snapshot_id, probability, issued_at)
            SELECT anchor_pk, {_dollar(row['procedure_id'])}, {_dollar(row['spec_id'])},
                   {_dollar(row['spec_digest'])}, {_dollar(row['snapshot_id'])},
                   {_float(row['probability'])}, {_time(row['issued_at'])}
            FROM beta_shadow_anchors WHERE anchor_key = {key}
            ON CONFLICT (anchor_pk, procedure_id, spec_id) DO NOTHING;
        """)
    return "\n".join(parts)


def _status_sql(rows: Sequence[Mapping]) -> str:
    parts = []
    for row in rows:
        reason = "NULL" if row.get("reason") is None else _dollar(str(row["reason"]))
        parts.append(f"""
            INSERT INTO beta_shadow_hour_status (issue_slot, horizon, status, reason)
            VALUES ({_time(row['issue_slot'])}, {_dollar(row['horizon'])}, {_dollar(row['status'])}, {reason})
            ON CONFLICT (issue_slot, horizon) DO NOTHING;
        """)
    return "\n".join(parts)


def _dollar(text: str) -> str:
    tag = "pg"
    raw = str(text)
    while f"${tag}$" in raw:
        tag += "x"
    return f"${tag}${raw}${tag}$"


def _time(value: datetime) -> str:
    stamp = value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S+00")
    return "timestamptz " + _dollar(stamp)


def _float(value) -> str:
    if value is None:
        return "NULL"
    return format(float(value), ".17g")


def _int(value) -> str:
    if value is None:
        return "NULL"
    return str(int(value))
