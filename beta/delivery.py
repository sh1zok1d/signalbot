"""Beta V0.2 notification outbox — at most ONE send attempt per user per notification.

Per PENDING delivery: (1) verify decision age <= delivery TTL, (2) atomically
PENDING -> SENDING and COMMIT, (3) exactly one Telegram call -> SENT / FAILED
(explicit rejection) / DELIVERY_UNKNOWN (ambiguous). On startup any row still in
SENDING (a crashed run) becomes DELIVERY_UNKNOWN and is NEVER resent. Old events
past the TTL become EXPIRED_UNDELIVERED; they stay visible in history.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional, Protocol, Sequence

from .admin import collect_health, fingerprint
from .config import BetaConfig, BetaSwitches, effective_push_enabled
from .formatter import format_owner_alert, format_push
from .models import (D_EXPIRED, D_FAILED, D_PENDING, D_SENDING, D_SENT, D_SUPPRESSED, D_UNKNOWN,
                     DELIVERY_TOO_OLD, PUSH_DISABLED, USER_INACTIVE)


class DeliveryRejected(RuntimeError):
    """Telegram explicitly rejected the send (safe to record FAILED)."""


class DeliveryAmbiguous(RuntimeError):
    """The send outcome is unknown (timeout / network) — never resend."""


class BetaSender(Protocol):
    async def send(self, *, chat_id: int, html: str,
                   buttons: Optional[Sequence[Sequence[tuple]]] = None) -> int: ...


def feedback_buttons(public_id: str, lang: str = "ru") -> list:
    from .formatter import feedback_buttons as _buttons
    return _buttons(public_id, lang)


async def run_notify_once(store, cfg: BetaConfig, switches: BetaSwitches, *, sender: Optional[BetaSender],
                          clock, owner_user_id: Optional[int] = None, logger=None) -> dict:
    from storage.beta_v0_store import NOTIFIER_LOCK_KEY
    report = {"recovered_unknown": 0, "materialized": 0, "sent": 0, "failed": 0, "unknown": 0,
              "expired": 0, "suppressed": 0, "purged_users": 0, "purged_activity": 0,
              "purged_feedback_messages": 0, "purged_rejected_starts": 0, "owner_alerts": []}
    if not switches.enabled:
        return {"status": "DISABLED", "switches": switches.as_dict()}
    if not switches.telegram:
        return {"status": "TELEGRAM_DISABLED", "switches": switches.as_dict()}
    ttl = cfg.delivery_ttl
    async with store.advisory_lock(NOTIFIER_LOCK_KEY) as acquired:
        if not acquired:
            return {"status": "LOCKED"}
        async with store.connect() as conn:
            now = clock()
            report["recovered_unknown"] = await conn.recover_sending(now)
            for d in await conn.fetch_undispatched_push_decisions(cfg["notifications"]["max_deliveries_per_run"]):
                report["materialized"] += await conn.materialize_deliveries(
                    decision_id=d["decision_id"], episode_pk=d["episode_pk"],
                    decision_ts=d["decision_ts"], expired=(now - d["decision_ts"] > ttl))
            # retention purge of long-stopped participants (personal data)
            cutoff = now - timedelta(days=cfg["privacy"]["stopped_user_retention_days"])
            for uid in await conn.stopped_users_before(cutoff):
                async with conn.transaction():
                    await conn.delete_participant(uid)
                    await conn.insert_audit(action="retention_purge", authorized=True,
                                            actor_fingerprint="system", target_fingerprint=fingerprint(uid),
                                            result="OK")
                report["purged_users"] += 1
            activity_cutoff = now - timedelta(days=cfg["telemetry"]["retention_days"])
            report["purged_activity"] = await conn.purge_activity_before(activity_cutoff)
            report["purged_feedback_messages"] = await conn.purge_feedback_messages_before(activity_cutoff)
            rejected_cutoff = now - timedelta(days=cfg["telemetry"]["rejected_start_retention_days"])
            report["purged_rejected_starts"] = await conn.purge_rejected_starts_before(rejected_cutoff)
            push_on = effective_push_enabled(switches, await conn.get_admin_push_enabled())
            episodes: dict = {}
            for row in await conn.fetch_pending_deliveries(cfg["notifications"]["max_deliveries_per_run"]):
                now = clock()
                did = row["delivery_id"]
                if now - row["decision_ts"] > ttl:
                    await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_EXPIRED, now=now,
                                                   suppression_reason=DELIVERY_TOO_OLD)
                    report["expired"] += 1
                    continue
                if not push_on:
                    await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SUPPRESSED, now=now,
                                                   suppression_reason=PUSH_DISABLED)
                    report["suppressed"] += 1
                    continue
                if row["user_status"] != "ACTIVE":
                    await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SUPPRESSED, now=now,
                                                   suppression_reason=USER_INACTIVE)
                    report["suppressed"] += 1
                    continue
                if sender is None:
                    await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_FAILED, now=now,
                                                   error_summary="sender unavailable (no bot token)")
                    report["failed"] += 1
                    continue
                ep = episodes.get(row["episode_pk"])
                if ep is None:
                    ep = episodes[row["episode_pk"]] = await conn.fetch_episode_by_pk(row["episode_pk"])
                lang = row.get("user_lang") or "ru"
                text = format_push(ep, lang=lang)
                # (2) commit PENDING -> SENDING before the single API call
                if not await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SENDING, now=now):
                    continue
                try:
                    message_id = await sender.send(chat_id=row["chat_id"], html=text,
                                                   buttons=feedback_buttons(ep.public_id, lang))
                except DeliveryRejected as exc:
                    await conn.transition_delivery(did, from_state=D_SENDING, to_state=D_FAILED,
                                                   now=clock(), error_summary=str(exc)[:300])
                    report["failed"] += 1
                    continue
                except Exception as exc:  # noqa: BLE001 - ambiguous: never resend
                    await conn.transition_delivery(did, from_state=D_SENDING, to_state=D_UNKNOWN, now=clock(),
                                                   error_summary=type(exc).__name__)
                    report["unknown"] += 1
                    continue
                sent_at = clock()
                await conn.transition_delivery(did, from_state=D_SENDING, to_state=D_SENT, now=sent_at,
                                               message_id=int(message_id))
                if row.get("user_pk") is not None:
                    await conn.record_activity(user_pk=row["user_pk"], action="push_delivered",
                                               lang=lang, at=sent_at)
                report["sent"] += 1
            # this run is itself the notifier heartbeat (recorded before evaluating alerts)
            await conn.record_health("notifier", now=clock(), success=True)
            # owner health alerts (operational; owner only; rate-limited per key)
            if sender is not None and owner_user_id is not None:
                h = await collect_health(conn, cfg, switches, clock())
                runtime = await conn.fetch_health()
                due = []
                for a in h["alerts"]:
                    last = (runtime.get(f"owner_alert:{a['key']}") or {}).get("last_success_at")
                    if last is None or (clock() - last).total_seconds() >= cfg["health"]["owner_alert_repeat_s"]:
                        due.append(a)
                if due:
                    try:
                        await sender.send(chat_id=owner_user_id, html=format_owner_alert(due))
                        for a in due:
                            await conn.record_health(f"owner_alert:{a['key']}", now=clock(), success=True)
                        report["owner_alerts"] = [a["key"] for a in due]
                    except Exception as exc:  # noqa: BLE001
                        report["owner_alert_error"] = type(exc).__name__
            await conn.record_health("notifier", now=clock(), success=True,
                                     detail={k: v for k, v in report.items() if isinstance(v, int)})
    return {"status": "OK", **report}
