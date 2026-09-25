"""Beta V0.2 owner administration + shared read-only status/health collection.

Owner authorization is against BETA_OWNER_TELEGRAM_USER_ID (environment only).
Every admin action — authorized or refused — is audited with pseudonymous
fingerprints, never raw Telegram ids. Admin pause/resume changes only the durable
admin push state, which can never exceed the config/env hard switch.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

from .config import BetaConfig, BetaSwitches, effective_push_enabled
from .formatter import ForbiddenWordingError, assert_descriptive
from .health import health_alerts, ingestion_heartbeat, product_status

ADMIN_COMMANDS = ("admin_status", "admin_users", "admin_add", "admin_remove", "admin_pause_push",
                  "admin_resume_push", "admin_broadcast", "admin_health")
UNAUTHORIZED_ACTOR = "unauthorized"


def fingerprint(telegram_user_id: Optional[int]) -> str:
    """Pseudonymous (not anonymous) stable id for audit/log lines."""
    if telegram_user_id is None:
        return "none"
    return "u_" + hashlib.sha256(f"signalbot-beta-v0:{int(telegram_user_id)}".encode()).hexdigest()[:12]


def is_owner(owner_user_id: Optional[int], telegram_user_id: Optional[int]) -> bool:
    return owner_user_id is not None and telegram_user_id is not None \
        and int(owner_user_id) == int(telegram_user_id)


def parse_command(text: Optional[str]):
    """'/cmd@bot arg rest' -> ('cmd', 'arg rest'); non-commands -> (None, '')."""
    if not text or not text.startswith("/"):
        return None, ""
    head, _, rest = text.strip().partition(" ")
    return head[1:].split("@", 1)[0].lower(), rest.strip()


async def collect_status(conn, cfg: BetaConfig, now: datetime) -> dict:
    latest = await conn.fetch_latest_live_tape(symbol=cfg.symbol)
    open_eps = list((await conn.fetch_open_episodes(symbol=cfg.symbol, for_update=False)).values())
    newest = await conn.fetch_newest_live_kline(exchanges=cfg.exchanges, symbol=cfg.symbol,
                                                since=now - timedelta(hours=1))
    hb = ingestion_heartbeat(cfg, now, newest)
    status = product_status(cfg, now=now, latest_live=latest, open_episodes=open_eps, heartbeat=hb)
    return {"status": status, "open_episodes": open_eps, "latest": latest, "heartbeat": hb}


async def collect_health(conn, cfg: BetaConfig, switches: BetaSwitches, now: datetime) -> dict:
    st = await collect_status(conn, cfg, now)
    wm = await conn.get_watermark("detector", symbol=cfg.symbol, market_type=cfg.market_type,
                                  timeframe=cfg.timeframe)
    runtime = await conn.fetch_health()
    window = timedelta(seconds=cfg["health"]["delivery_problem_window_s"])
    counts = await conn.delivery_state_counts(since=now - window)
    problems = counts.get("FAILED", 0) + counts.get("DELIVERY_UNKNOWN", 0)
    alerts = health_alerts(cfg, now=now, heartbeat=st["heartbeat"], detector_watermark=wm,
                           latest_live=st["latest"], runtime=runtime, delivery_problems=problems,
                           switches=switches)
    admin_push = await conn.get_admin_push_enabled()
    return {"product_status": st["status"]["status"], "status_reasons": st["status"]["reasons"],
            "last_good_bucket": st["status"].get("last_good_bucket"),
            "detector_watermark": wm, "heartbeat": st["heartbeat"],
            "runtime": {k: {"last_run_at": v["last_run_at"], "last_success_at": v["last_success_at"],
                            "last_error_type": v["last_error_type"]} for k, v in runtime.items()},
            "delivery_counts_window": counts, "alerts": alerts,
            "switches": switches.as_dict(), "admin_push_enabled": admin_push,
            "effective_push_enabled": effective_push_enabled(switches, admin_push),
            "open_episodes": [(e.public_id, e.event_type, e.state) for e in st["open_episodes"]]}


async def handle_admin(conn, cfg: BetaConfig, switches: BetaSwitches, *, owner_user_id: Optional[int],
                       actor_user_id: int, command: str, args: str, now: datetime) -> dict:
    """Returns {'reply': html, 'broadcast': Optional[html], 'authorized': bool}.
    Refused attempts are audited without the actor's identity."""
    if not is_owner(owner_user_id, actor_user_id):
        await conn.insert_audit(action=command, authorized=False, actor_fingerprint=UNAUTHORIZED_ACTOR,
                                target_fingerprint=None, result="REFUSED")
        return {"reply": None, "broadcast": None, "authorized": False}
    actor = fingerprint(actor_user_id)
    target, result, detail, reply, broadcast = None, "OK", {}, "", None
    if command == "admin_status":
        st = await collect_status(conn, cfg, now)
        users = await conn.user_counts()
        reply = (f"status {st['status']['status']} {st['status']['reasons']}\n"
                 f"users {users} allowlist {await conn.allowlist_count()}\n"
                 f"open {[(e.public_id, e.event_type, e.state) for e in st['open_episodes']]}\n"
                 f"push effective {effective_push_enabled(switches, await conn.get_admin_push_enabled())}")
    elif command == "admin_health":
        h = await collect_health(conn, cfg, switches, now)
        reply = f"alerts {[a['key'] for a in h['alerts']]}\nswitches {h['switches']}\nstatus {h['product_status']}"
    elif command == "admin_users":
        rows = await conn.list_users()
        reply = "\n".join(f"{r['telegram_user_id']} {r['status'] or 'INVITED'} joined {r['joined_at']}"
                          for r in rows) or "no users"
        detail = {"count": len(rows)}
    elif command in ("admin_add", "admin_remove"):
        if not args.isdigit() or int(args) <= 0:
            result, reply = "INVALID_ARGUMENT", f"usage: /{command} <telegram_user_id>"
        else:
            uid = int(args)
            target = fingerprint(uid)
            if command == "admin_add":
                added = await conn.allowlist_add(uid)
                reply = "added to allowlist" if added else "already allowlisted"
            else:
                removed = await conn.delete_participant(uid)
                reply = f"removed ({removed})"
                detail = removed
    elif command == "admin_pause_push":
        await conn.set_admin_push_enabled(False)
        reply = "push paused (durable admin state)."
    elif command == "admin_resume_push":
        await conn.set_admin_push_enabled(True)
        eff = effective_push_enabled(switches, True)
        reply = "admin push state resumed; effective push " + (
            "ON" if eff else "remains OFF (config/env hard switch forbids push)")
        detail = {"effective": eff}
    elif command == "admin_broadcast":
        if not args:
            result, reply = "INVALID_ARGUMENT", "usage: /admin_broadcast <text>"
        else:
            try:
                import html as _html
                broadcast = assert_descriptive(_html.escape(args, quote=False))
                reply = "broadcast queued to active users"
                detail = {"length": len(args)}
            except ForbiddenWordingError:
                result, reply = "REFUSED_WORDING", "refused: broadcast contains forbidden wording"
    else:
        result, reply = "UNKNOWN", "unknown admin command"
    await conn.insert_audit(action=command if command in ADMIN_COMMANDS else "admin_status",
                            authorized=True, actor_fingerprint=actor, target_fingerprint=target,
                            result=result, detail=detail)
    return {"reply": reply, "broadcast": broadcast, "authorized": True}
