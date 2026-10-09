"""`/admin_export_views [n]` (Pulsy UX V2, P0): the owner's JSON of the last n persisted views and stored
alert / push payloads, the input of the UX gallery (`tools/ux_gallery/build.py`).

Market data only. No user id, fingerprint, chat id, feedback, audit or claim row is read, and `scrub` drops any
denylisted key at any depth as a second guard. Read-only.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime
from typing import Any

EXPORT_VERSION = "PULSY_UX_EXPORT_V1"
MAX_N = 50
DEFAULT_N = 20
# Keys that may identify a person or link to one; dropped at any depth (`scrub`) and refused by the test.
DENYLIST = frozenset({"user_pk", "user_id", "telegram_user_id", "target_user_pk", "chat_id", "fingerprint",
                      "actor_fingerprint", "target_fingerprint", "username", "first_name", "last_name",
                      "invite_code", "feedback", "text", "message_id", "audit_id", "claim_pk"})


def scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if k not in DENYLIST and not k.endswith("_fingerprint")}
    if isinstance(obj, (list, tuple)):
        return [scrub(v) for v in obj]
    return obj


def _plain(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v) if v[:1] in "{[" else v
        except ValueError:
            return v
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if dataclasses.is_dataclass(v):
        return {k: _plain(x) for k, x in dataclasses.asdict(v).items()}
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v


def parse_n(args: str) -> int | None:
    raw = (args or "").strip()
    if not raw:
        return DEFAULT_N
    return int(raw) if raw.isdigit() and 1 <= int(raw) <= MAX_N else None


async def export_views(conn, n: int, *, now: datetime) -> dict:
    """The last `n` views, market alerts and pushed decisions (with their episode), newest first."""
    c = conn.conn
    views = await c.fetch("""SELECT view_pk, kind, requested_at, as_of_bucket, payload FROM beta_btc_views
                             ORDER BY view_pk DESC LIMIT $1""", n)
    alerts = await c.fetch("""SELECT alert_pk, kind, decision_ts, decision, suppression_reason, payload
                              FROM beta_market_alerts ORDER BY alert_pk DESC LIMIT $1""", n)
    pushes = await c.fetch("""SELECT decision_id, episode_pk, event_type, decision_ts, gate FROM beta_push_decisions
                              WHERE decision = 'PUSH' ORDER BY decision_id DESC LIMIT $1""", n)
    push_rows = []
    for p in pushes:
        ep = await conn.fetch_episode_by_pk(p["episode_pk"])
        push_rows.append({**{k: p[k] for k in ("decision_id", "event_type", "decision_ts", "gate")}, "episode": ep})
    out = {"version": EXPORT_VERSION, "exported_at": now, "n": n, "provenance": "REAL",
           "views": [dict(r) for r in views], "alerts": [dict(r) for r in alerts], "pushes": push_rows}
    return scrub(_plain(out))


def export_bytes(doc: dict) -> bytes:
    return json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8")
