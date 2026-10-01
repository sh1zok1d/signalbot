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

from .access import invite_link
from .config import BetaConfig, BetaSwitches, effective_push_enabled
from .formatter import ForbiddenWordingError, assert_descriptive
from .health import health_alerts, ingestion_heartbeat, product_status

ADMIN_COMMANDS = ("admin_status", "admin_users", "admin_add", "admin_remove", "admin_pause_push",
                  "admin_resume_push", "admin_broadcast", "admin_health", "admin_invite_new",
                  "admin_invites", "admin_invite_revoke", "admin_waitlist", "admin_waitlist_admit",
                  "admin_stats")
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
    d7_at = None
    if cfg.section("regime_d7")["enabled"]:
        d7_at = await conn.newest_d7_available_at()
    alerts = health_alerts(cfg, now=now, heartbeat=st["heartbeat"], detector_watermark=wm,
                           latest_live=st["latest"], runtime=runtime, delivery_problems=problems,
                           switches=switches, d7_newest_available_at=d7_at)
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


def parse_invite_new(args: str):
    """`<max_uses> [days] <label…>`. A second all-digit token is the lifetime in days."""
    parts = (args or "").split()
    if len(parts) < 2 or not parts[0].isdigit() or int(parts[0]) <= 0:
        return None
    max_uses = int(parts[0])
    days = None
    rest = parts[1:]
    if rest[0].isdigit():
        days = int(rest[0])
        if days <= 0:
            return None
        rest = rest[1:]
    label = " ".join(rest).strip()
    if not label:
        return None
    return max_uses, days, label


async def handle_admin(conn, cfg: BetaConfig, switches: BetaSwitches, *, owner_user_id: Optional[int],
                       actor_user_id: int, command: str, args: str, now: datetime,
                       bot_username: Optional[str] = None) -> dict:
    """Returns reply, optional broadcast, optional direct notices, authorized.
    Refused attempts are audited without the actor's identity. Audit detail never
    stores a raw Telegram id; the waitlist reply is the owner-only exception."""
    if not is_owner(owner_user_id, actor_user_id):
        await conn.insert_audit(action=command if command in ADMIN_COMMANDS else "admin_status",
                                authorized=False, actor_fingerprint=UNAUTHORIZED_ACTOR,
                                target_fingerprint=None, result="REFUSED")
        return {"reply": None, "broadcast": None, "direct": None, "authorized": False}
    actor = fingerprint(actor_user_id)
    target, result, detail, reply, broadcast, direct = None, "OK", {}, "", None, None
    cap = int(cfg["access"]["max_active_users"])
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
                added = await conn.allowlist_with_cap(
                    uid, max_active_users=cap, owner_user_id=owner_user_id)
                if added == "OK":
                    reply = "added to allowlist"
                elif added == "ALREADY":
                    reply = "already allowlisted"
                else:
                    result, reply = "CAP", "cap reached; not added"
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
    elif command == "admin_invite_new":
        parsed = parse_invite_new(args)
        if parsed is None:
            result, reply = "INVALID_ARGUMENT", "usage: /admin_invite_new <max_uses> [days] <label>"
        else:
            max_uses, days, label = parsed
            expires = None if days is None else now + timedelta(days=days)
            code = await conn.create_invite(label=label, max_uses=max_uses, now=now, expires_at=expires)
            if bot_username:
                reply = invite_link(bot_username, code)
            else:
                reply = f"{code}\nbot username unavailable"
            detail = {"max_uses": max_uses, "days": days, "label": label, "code": code}
    elif command == "admin_invites":
        rows = await conn.list_invites()
        lines = []
        for r in rows:
            exp = r["expires_at"].isoformat() if r["expires_at"] else "none"
            state = "revoked" if r["revoked_at"] else "active"
            lines.append(f"{r['code']} {r['label']} {r['used_count']}/{r['max_uses']} expires {exp} {state}")
        reply = "\n".join(lines) or "no invites"
        detail = {"count": len(rows)}
    elif command == "admin_invite_revoke":
        outcome = await conn.revoke_invite(args.strip(), now)
        result = outcome if outcome != "OK" else "OK"
        reply = {"OK": "revoked", "ALREADY": "already revoked", "MISSING": "no such code",
                 "INVALID": "invalid code"}.get(outcome, outcome)
        detail = {"result": outcome}
    elif command == "admin_waitlist":
        listed = await conn.waitlist_list()
        lines = [f"waitlist {listed['count']}"]
        for entry in listed["entries"]:
            lines.append(f"{entry['telegram_user_id']} {entry['requested_at'].isoformat()}")
        reply = "\n".join(lines)
        detail = {"count": listed["count"]}
    elif command == "admin_waitlist_admit":
        if not args.isdigit() or int(args) <= 0:
            result, reply = "INVALID_ARGUMENT", "usage: /admin_waitlist_admit <telegram_user_id>"
        else:
            uid = int(args)
            target = fingerprint(uid)
            added = await conn.allowlist_with_cap(
                uid, max_active_users=cap, owner_user_id=owner_user_id)
            if added == "CAP":
                result, reply = "CAP", "cap reached; not added"
            else:
                await conn.waitlist_remove(uid)
                from .i18n import t
                direct = [(uid, t("ru", "access_granted"))]
                reply = "already allowlisted" if added == "ALREADY" else f"admitted {target}"
            detail = {"result": added}
    elif command == "admin_stats":
        from .usage import build_usage_report, format_usage_report
        report = build_usage_report(await conn.usage_facts(), now=now, owner_user_id=owner_user_id)
        reply = format_usage_report(report)
        detail = {"waitlist": report["waitlist_size"],
                  "weeks_3_and_4_active": report["since_first_external"]["weeks_3_and_4_active"]}
    else:
        result, reply = "UNKNOWN", "unknown admin command"
    await conn.insert_audit(action=command if command in ADMIN_COMMANDS else "admin_status",
                            authorized=True, actor_fingerprint=actor, target_fingerprint=target,
                            result=result, detail=detail)
    return {"reply": reply, "broadcast": broadcast, "direct": direct, "authorized": True}
