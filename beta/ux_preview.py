"""`/admin_preview v2 <screen>` (Pulsy UX V2, P0): the V2 templates on live data, to the owner only, behind
`access.ux_v2_preview`. Its level buttons (L1 summary / L2 «Почему так?» / L3 «Данные») resolve only for the owner
while the flag is on. Nothing is written: no view, no claim display, no activity, no outbox row.

The renderer is track A's `beta.ux.render(screen, level, lang, facts) -> (html, buttons)`. Each button is
(label, target), and a target that names a level ("l1" / "l2" / "l3") becomes the callback `x2:<screen>:<level>`.
Until `beta.ux` lands, `stub_render` stands in with the same signature.
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Any, Optional

from .config import BetaConfig

SCREENS = ("btc", "levels", "brief", "alert", "push")
LEVELS = ("l1", "l2", "l3")
CALLBACK = "x2:"
_LEVEL_LABELS = {"ru": {"l1": "Кратко", "l2": "Почему так?", "l3": "Данные"},
                 "en": {"l1": "Summary", "l2": "Why?", "l3": "Data"}}


def enabled(cfg: BetaConfig) -> bool:
    return bool(((getattr(cfg, "raw", None) or {}).get("access") or {}).get("ux_v2_preview", False))


def stub_render(screen: str, level: str, lang: str, facts: Any) -> tuple:
    """A stand-in for `beta.ux.render` until track A's module lands: the facts as they are, and level buttons."""
    body = json.dumps(facts, ensure_ascii=False, sort_keys=True, default=str)
    limit = {"l1": 300, "l2": 1200, "l3": 3000}[level]
    text = f"<b>{html.escape(screen)} · {level.upper()}</b> (stub)\n<pre>{html.escape(body[:limit])}</pre>"
    labels = _LEVEL_LABELS.get(lang, _LEVEL_LABELS["en"])
    return text, [[(labels[x], x) for x in LEVELS if x != level]]


def renderer():
    try:
        from .ux import render          # track A (Pulsy UX V2)
        return render
    except ImportError:
        return stub_render


async def live_facts(conn, cfg: BetaConfig, screen: str, *, now: datetime) -> Optional[Any]:
    """The live input of `screen`: the current view (read only, never persisted) or the latest stored decision."""
    from .ux_export import _plain
    if screen in ("btc", "levels", "brief"):
        from .config import effective_d7_enabled
        from .market_view import BRIEF_WINDOW_HOURS, build_view, maturity_days
        kind = "brief" if screen == "brief" else "btc"
        return _plain(await build_view(conn, cfg, now=now, kind=kind,
                                       window_hours=BRIEF_WINDOW_HOURS if kind == "brief" else None,
                                       maturity_days=maturity_days(cfg),
                                       d7_enabled=effective_d7_enabled(cfg, await conn.get_admin_d7_enabled())))
    if screen == "alert":
        row = await conn.conn.fetchrow("SELECT kind, payload FROM beta_market_alerts ORDER BY alert_pk DESC LIMIT 1")
        return None if row is None else _plain({"kind": row["kind"], "payload": row["payload"]})
    row = await conn.conn.fetchrow("""SELECT episode_pk, gate FROM beta_push_decisions WHERE decision = 'PUSH'
                                      ORDER BY decision_id DESC LIMIT 1""")
    if row is None:
        return None
    return _plain({"gate": row["gate"], "episode": await conn.fetch_episode_by_pk(row["episode_pk"])})


async def render_v2(conn, cfg: BetaConfig, screen: str, level: str, *, now: datetime,
                    lang: str = "ru") -> Optional[tuple]:
    """(html, buttons) for the owner, or None when the screen has no data yet."""
    facts = await live_facts(conn, cfg, screen, now=now)
    if facts is None:
        return None
    text, buttons = renderer()(screen, level, lang, facts)
    rows = [[(label, f"{CALLBACK}{screen}:{target}") for label, target in row if target in LEVELS]
            for row in (buttons or [])]
    return f"🔍 <b>ПРЕВЬЮ V2</b>\n\n{text}", [r for r in rows if r]


def parse_callback(data: str) -> Optional[tuple]:
    parts = data[len(CALLBACK):].split(":") if data.startswith(CALLBACK) else []
    return (parts[0], parts[1]) if len(parts) == 2 and parts[0] in SCREENS and parts[1] in LEVELS else None
