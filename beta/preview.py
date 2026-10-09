"""The owner's UX preview (2026-10-09): `/admin_preview [type]` renders one automated notification type for the
owner only, prefixed «ПРЕВЬЮ».

- The unusual-hour push and the market alerts are rendered again from the latest stored real decision of that kind.
- The briefing and the weekly report are rendered from the current state (the /catchup path, `build_weekly`).
- Nothing is written: no outbox row, no claim-journal link, no view, no activity. No fuse or limit is used.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from .config import BetaConfig

PREVIEW_TYPES = ("hour", "level", "move", "event", "price", "approach", "brief", "weekly")
PREFIX = "🔍 <b>ПРЕВЬЮ</b>"
NEVER = "ещё не было"


def _json(v: Any) -> Any:
    return json.loads(v) if isinstance(v, str) else v


def preview_help() -> str:
    return ("/admin_preview <type> — the latest notification of that type, to you only, prefixed «ПРЕВЬЮ».\n"
            "types: hour (unusual-hour push), level, move, event (CPI/FOMC), price, approach (personal /alert), "
            "brief, weekly (current state)")


async def render_preview(conn, cfg: BetaConfig, kind: str, *, now: datetime) -> Optional[str]:
    """The owner's preview text of `kind`, or None when that type never occurred."""
    if kind == "hour":
        row = await conn.conn.fetchrow(
            """SELECT episode_pk, gate FROM beta_push_decisions WHERE decision = 'PUSH'
               ORDER BY decision_ts DESC, decision_id DESC LIMIT 1""")
        if row is None:
            return None
        from .config import research_main_surfaces_enabled
        from .delivery import _analogue_source, _push_analogue, _push_levels
        from .formatter import format_push
        ep = await conn.fetch_episode_by_pk(row["episode_pk"])
        gate = _json(row["gate"])
        analogues, since_year = await _analogue_source(conn, now)
        text = format_push(ep, lang="ru", gate=gate, analog=_push_analogue(analogues, gate), since_year=since_year,
                           research=research_main_surfaces_enabled(cfg), levels=await _push_levels(conn, cfg, now) or None)
    elif kind in ("level", "move", "event", "price", "approach"):
        row = await conn.conn.fetchrow(
            "SELECT payload FROM beta_market_alerts WHERE kind = $1 ORDER BY alert_pk DESC LIMIT 1", kind)
        if row is None:
            return None
        from .decision_format import format_alert
        text = format_alert(kind, _json(row["payload"]), "ru")
    elif kind == "brief":
        from .config import effective_d7_enabled
        from .formatter import format_catchup
        from .market_view import BRIEF_WINDOW_HOURS, build_view, maturity_days
        view = await build_view(conn, cfg, now=now, kind="brief", window_hours=BRIEF_WINDOW_HOURS,
                                maturity_days=maturity_days(cfg),
                                d7_enabled=effective_d7_enabled(cfg, await conn.get_admin_d7_enabled()))
        text = format_catchup(cfg, view, "ru")
    elif kind == "weekly":
        from .weekly import build_weekly, format_weekly
        text = format_weekly(await build_weekly(conn, now=now), "ru")
    else:
        raise ValueError(kind)
    return f"{PREFIX}\n\n{text}"
