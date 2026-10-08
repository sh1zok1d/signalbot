"""Beta V0.2 owner administration + shared read-only status/health collection.

Owner authorization is against BETA_OWNER_TELEGRAM_USER_ID (environment only).
Every admin action — authorized or refused — is audited with pseudonymous
fingerprints, never raw Telegram ids. Admin pause/resume changes only the durable
admin push state, which can never exceed the config/env hard switch. `/admin_d7_on`
and `/admin_d7_off` change only the durable D7 owner state, which defaults off
and can never exceed `regime_d7.enabled`.
"""
from __future__ import annotations

import hashlib
import html
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Sequence

from .access import invite_link
from .config import BetaConfig, BetaSwitches, effective_d7_enabled, effective_push_enabled
from .formatter import ForbiddenWordingError, assert_descriptive
from .health import health_alerts, ingestion_heartbeat, product_status

ADMIN_COMMANDS = ("admin_status", "admin_users", "admin_add", "admin_remove", "admin_pause_push",
                  "admin_resume_push", "admin_d7_on", "admin_d7_off", "admin_broadcast", "admin_outage",
                  "admin_health", "admin_invite_new", "admin_invites", "admin_invite_revoke",
                  "admin_waitlist", "admin_waitlist_admit", "admin_stats", "admin_reply", "admin_known",
                  "admin_latency", "admin_offer")
UNAUTHORIZED_ACTOR = "unauthorized"


def owner_parts(text: str, limit: int = 3500) -> list:
    """Owner text in whole lines, each part under `limit` characters once HTML-escaped (Telegram caps
    a message at 4096 characters; `/admin_stats` grows with the weeks)."""
    parts, cur = [], ""
    for line in text.split("\n"):
        if cur and len(html.escape(cur + "\n" + line, quote=False)) > limit:
            parts.append(cur)
            cur = line
        else:
            cur = line if not cur else cur + "\n" + line
    return parts + [cur]


def fingerprint(telegram_user_id: Optional[int]) -> str:
    """Pseudonymous (not anonymous) stable id for audit/log lines."""
    if telegram_user_id is None:
        return "none"
    return "u_" + hashlib.sha256(f"signalbot-beta-v0:{int(telegram_user_id)}".encode()).hexdigest()[:12]


def is_owner(owner_user_id: Optional[int], telegram_user_id: Optional[int]) -> bool:
    return owner_user_id is not None and telegram_user_id is not None \
        and int(owner_user_id) == int(telegram_user_id)


def classify_fingerprint(rows: Sequence[Mapping], fp: str):
    """ACTIVE rows whose fingerprint equals `fp`. Empty or more than one is not a send."""
    hits = [r for r in rows if fingerprint(r.get("telegram_user_id")) == fp]
    if not hits:
        return "UNKNOWN", []
    if len(hits) > 1:
        return "AMBIGUOUS", hits
    return "OK", hits


def parse_admin_reply(args: str):
    """`<fingerprint> <text>`. The fingerprint is the first token."""
    fp, _, text = (args or "").strip().partition(" ")
    fp, text = fp.strip(), text.strip()
    if not fp or not text:
        return None
    return fp, text


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
    counts = await conn.delivery_state_counts(since=now - window)          # push states (soak report)
    # the spike counts every outbox kind (push, brief, alert, weekly), expired and flood-control rows
    # included; a participant who blocked the bot is counted apart, never as a failure (A3)
    problems = await conn.delivery_problems(since=now - window)
    d7_at = None
    if cfg.section("regime_d7")["enabled"]:
        d7_at = await conn.newest_d7_available_at()
    alerts = health_alerts(cfg, now=now, heartbeat=st["heartbeat"], detector_watermark=wm,
                           latest_live=st["latest"], runtime=runtime, delivery_problems=problems,
                           switches=switches, d7_newest_available_at=d7_at)
    admin_push = await conn.get_admin_push_enabled()
    admin_d7 = await conn.get_admin_d7_enabled()
    return {"product_status": st["status"]["status"], "status_reasons": st["status"]["reasons"],
            "last_good_bucket": st["status"].get("last_good_bucket"),
            "detector_watermark": wm, "heartbeat": st["heartbeat"],
            "runtime": {k: {"last_run_at": v["last_run_at"], "last_success_at": v["last_success_at"],
                            "last_error_type": v["last_error_type"]} for k, v in runtime.items()},
            "delivery_counts_window": counts, "delivery_problems": problems, "alerts": alerts,
            "switches": switches.as_dict(), "admin_push_enabled": admin_push,
            "effective_push_enabled": effective_push_enabled(switches, admin_push),
            "admin_d7_enabled": admin_d7,
            "effective_d7_enabled": effective_d7_enabled(cfg, admin_d7),
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
        return {"reply": None, "broadcast": None, "direct": None, "mass": None, "authorized": False}
    actor = fingerprint(actor_user_id)
    target, result, detail, reply, broadcast, direct, mass = None, "OK", {}, "", None, None, None
    cap = int(cfg["access"]["max_active_users"])
    if command == "admin_status":
        st = await collect_status(conn, cfg, now)
        users = await conn.user_counts()
        reply = (f"status {st['status']['status']} {st['status']['reasons']}\n"
                 f"users {users} allowlist {await conn.allowlist_count()}\n"
                 f"open {[(e.public_id, e.event_type, e.state) for e in st['open_episodes']]}\n"
                 f"push effective {effective_push_enabled(switches, await conn.get_admin_push_enabled())}\n"
                 f"d7 effective {effective_d7_enabled(cfg, await conn.get_admin_d7_enabled())}")
    elif command == "admin_health":
        h = await collect_health(conn, cfg, switches, now)
        reply = f"alerts {[a['key'] for a in h['alerts']]}\nswitches {h['switches']}\nstatus {h['product_status']}"
    elif command == "admin_users":
        rows = await conn.list_users()
        reply = "\n".join(f"{r['telegram_user_id']} {r['status'] or 'INVITED'} joined {r['joined_at']}"
                          f"{' known' if r.get('known_contact') else ''}"
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
    elif command == "admin_d7_off":
        await conn.set_admin_d7_enabled(False)
        reply = "D7 line off (durable admin state)."
        detail = {"effective": False}
    elif command == "admin_d7_on":
        await conn.set_admin_d7_enabled(True)
        eff = effective_d7_enabled(cfg, True)
        reply = "admin D7 state on; effective D7 line " + (
            "ON" if eff else "remains OFF (regime_d7.enabled hard switch forbids the line)")
        detail = {"effective": eff}
    elif command == "admin_broadcast":
        if not args:
            result, reply = "INVALID_ARGUMENT", "usage: /admin_broadcast <text>"
        else:
            try:
                import html as _html
                broadcast = assert_descriptive(_html.escape(args, quote=False))
                mass = {"action": "admin_broadcast", "label": "broadcast"}
                reply = "broadcast: sending to active users"
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
    elif command == "admin_known":
        parts = args.split()
        if len(parts) != 2 or not parts[0].isdigit() or int(parts[0]) <= 0 or parts[1] not in ("on", "off"):
            result, reply = "INVALID_ARGUMENT", "usage: /admin_known <telegram_user_id> on|off"
        else:
            uid, known = int(parts[0]), parts[1] == "on"
            target = fingerprint(uid)
            if await conn.set_known_contact(uid, known):
                reply = f"known_contact={'true' if known else 'false'}"
                detail = {"known_contact": known}
            else:
                result, reply = "NOT_FOUND", "no such participant"
    elif command == "admin_reply":
        parsed = parse_admin_reply(args)
        if parsed is None:
            result, reply = "INVALID_ARGUMENT", "usage: /admin_reply <fingerprint> <text>"
        else:
            fp, body = parsed
            target = fp
            # paused participants are answered too (J4): they are enrolled until deleted
            status, hits = classify_fingerprint(await conn.enrolled_user_rows(), fp)
            if status != "OK":
                result = status
                reply = "unknown fingerprint" if status == "UNKNOWN" else "ambiguous fingerprint"
            else:
                lang = hits[0].get("lang") or "ru"
                try:
                    assert_descriptive(body, lang)
                except ForbiddenWordingError as exc:
                    result, reply = "REFUSED_WORDING", f"refused: {exc}"
                else:
                    from .i18n import t
                    shown = t(lang, "team_reply") + html.escape(body, quote=False)
                    direct = [(int(hits[0]["chat_id"]), shown, lang)]
                    reply = f"delivered to {fp}"
    elif command == "admin_outage":
        # A3: the ready «у нас сбой» notice, each participant in their own language
        from .i18n import t
        phase = (args or "").strip().lower()
        if phase not in ("start", "end"):
            result = "INVALID_ARGUMENT"
            reply = ("usage: /admin_outage start|end\nstart (ru): " + t("ru", "outage_start")
                     + "\nend (ru): " + t("ru", "outage_end"))
        else:
            chats = await conn.active_user_rows()
            direct = [(int(c["chat_id"]), t(c.get("lang") or "ru", f"outage_{phase}"), c.get("lang") or "ru")
                      for c in chats]
            # the bot sends these paced after the commit and then reports how many were delivered
            # (runtime.beta_bot.report_mass_send), with a second audit row carrying the real count
            mass = {"action": "admin_outage", "label": f"outage {phase} notice", "phase": phase}
            reply = f"outage {phase} notice: sending to {len(direct)} active participants"
            detail = {"phase": phase, "recipients": len(direct)}
    elif command == "admin_offer":
        # I2 / U3, days 21–25: one offer to each ACTIVE participant, inactive ones included; STOPPED, deleted
        # and bot-blocked participants are skipped and counted (owner, 2026-10-08). The owner keeps the payment
        # ledger outside git; the fingerprints and the time go to the owner only.
        from .i18n import t
        offer = cfg.section("access").get("u3_offer") or {}
        if not (offer.get("price") and offer.get("method")):
            result = "REFUSED"
            reply = "refused: access.u3_offer.price and .method are fixed in a commit before Day 0"
        elif (args or "").strip().lower() not in ("send", "send again"):
            reply = ("preview (ru):\n" + t("ru", "u3_offer", price=offer["price"], method=offer["method"])
                     + "\n\nsend it to every active participant: /admin_offer send")
        elif (args or "").strip().lower() == "send" and await conn.u3_offer_sent():
            # U3 is one offer: a second «send» is refused; the owner types «send again» on purpose
            result = "REFUSED"
            reply = "refused: the U3 offer was already sent; to send it again: /admin_offer send again"
        else:
            offer_to = await conn.u3_offer_recipients()
            rows = offer_to["recipients"]
            direct = [(int(r["chat_id"]), t(r.get("lang") or "ru", "u3_offer", price=offer["price"],
                                            method=offer["method"]), r.get("lang") or "ru") for r in rows]
            mass = {"action": "admin_offer", "label": "U3 offer"}
            when = now.astimezone(timezone.utc).isoformat()
            skipped = {k: offer_to[k] for k in ("stopped", "blocked", "deleted")}
            reply = ("U3 offer: sending to %d active participants\nskipped: %d stopped, %d blocked the bot, "
                     "%d deleted\nfor the ledger (participant_fingerprint, offered_at):\n"
                     % (len(direct), skipped["stopped"], skipped["blocked"], skipped["deleted"])
                     + "\n".join(f"{fingerprint(int(r['telegram_user_id']))} {when}" for r in rows))
            detail = {"recipients": len(direct), "skipped": skipped}
    elif command == "admin_latency":
        # A4: candle close (or schedule) -> delivery, P50/P95 by class
        from .latency import format_report, summarize
        raw = (args or "").strip()
        if raw and not (raw.isdigit() and 1 <= int(raw) <= 90):
            result, reply = "INVALID_ARGUMENT", "usage: /admin_latency [days 1..90, default 7]"
        else:
            days = int(raw or 7)
            summary = summarize(await conn.delivery_latency_rows(since=now - timedelta(days=days)))
            reply = format_report(summary, days=days)
            detail = {"days": days, "n": {k: v["n"] for k, v in summary.items()}}
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
    return {"reply": reply, "broadcast": broadcast, "direct": direct, "mass": mass, "authorized": True}
