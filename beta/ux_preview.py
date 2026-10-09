"""`/admin_preview v2 <screen>` (Pulsy UX V2, P0): track A's V2 render (`beta.ux`) on live data, to the owner only,
behind `access.ux_v2_preview`. The user-facing flag `ux.v2_enabled` is untouched.

The render's buttons call `ux:<screen>:<level>`. The preview rewrites them to `x2:<screen>:<level>`, a namespace of its
own, and those taps resolve only for the owner while the flag is on. Nothing is written: no view, no claim display,
no activity, no outbox row.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from .config import BetaConfig
from .ux import SCREENS, from_alert, from_hour_gate, from_view, render

CALLBACK = "x2:"
VIEW_SCREENS = ("btc", "levels", "level_card", "brief")


def enabled(cfg: BetaConfig) -> bool:
    return bool(((getattr(cfg, "raw", None) or {}).get("access") or {}).get("ux_v2_preview", False))


def _plain(v: Any) -> Any:
    from .ux_export import _plain as plain
    return plain(v)


async def live_facts(conn, cfg: BetaConfig, screen: str, *, now: datetime) -> Optional[dict]:
    """The facts of `screen` from live data: the current view (built, never persisted) or the latest stored
    decision of that kind; None when there is none yet."""
    if screen in VIEW_SCREENS:
        from .config import effective_d7_enabled
        from .market_view import BRIEF_WINDOW_HOURS, build_view, maturity_days
        kind = "brief" if screen == "brief" else "btc"
        view = await build_view(conn, cfg, now=now, kind=kind,
                                window_hours=BRIEF_WINDOW_HOURS if kind == "brief" else None,
                                maturity_days=maturity_days(cfg),
                                d7_enabled=effective_d7_enabled(cfg, await conn.get_admin_d7_enabled()))
        f = from_view(_plain(view))
        return card_facts(f) if screen == "level_card" else f
    if screen in ("level", "move"):
        row = await conn.conn.fetchrow("SELECT payload FROM beta_market_alerts WHERE kind = $1 "
                                       "ORDER BY alert_pk DESC LIMIT 1", screen)
        return None if row is None else from_alert(screen, _plain(row["payload"]))
    if screen == "hour":
        row = await conn.conn.fetchrow("""SELECT episode_pk, gate FROM beta_push_decisions
                                          WHERE decision = 'PUSH' AND gate IS NOT NULL
                                          ORDER BY decision_id DESC LIMIT 1""")
        if row is None:
            return None
        ep = await conn.fetch_episode_by_pk(row["episode_pk"])
        at = getattr(ep, "triggered_at", None)
        return from_hour_gate(at.isoformat() if at else None, _plain(row["gate"]))
    raise ValueError(screen)


def card_facts(f: dict) -> Optional[dict]:
    """`level_card` shows one level: the one price is at, else the nearest above, else the nearest below."""
    lv = f.get("levels") or {}
    z = lv.get("at") or next((x for x in (lv.get("above") or []) + (lv.get("below") or []) if x), None)
    return None if z is None else {**f, "zone": z}


def owner_buttons(buttons) -> list:
    """The render's `ux:` callbacks in the preview's own `x2:` namespace; anything else is dropped."""
    rows = [[(label, CALLBACK + data[3:]) for label, data in row if str(data).startswith("ux:")]
            for row in (buttons or [])]
    return [r for r in rows if r]


async def render_v2(conn, cfg: BetaConfig, screen: str, level: int, *, now: datetime,
                    lang: str = "ru") -> Optional[tuple]:
    """(html, buttons) for the owner, or None when the screen has no data yet."""
    facts = await live_facts(conn, cfg, screen, now=now)
    if facts is None:
        return None
    text, buttons = render(screen, level, lang, facts)
    return f"🔍 <b>ПРЕВЬЮ V2</b>\n\n{text}", owner_buttons(buttons)


def parse_callback(data: str) -> Optional[tuple]:
    parts = data[len(CALLBACK):].split(":") if data.startswith(CALLBACK) else []
    if len(parts) != 2 or parts[0] not in SCREENS or not parts[1].isdigit():
        return None
    level = int(parts[1])
    return (parts[0], level) if level in SCREENS[parts[0]] else None
