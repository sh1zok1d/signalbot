"""Beta V0.2 notification outbox — at most ONE send attempt per user per notification.

Per PENDING delivery: (1) verify decision age <= delivery TTL, (2) atomically
PENDING -> SENDING and COMMIT, (3) exactly one Telegram call -> SENT / FAILED
(explicit rejection) / DELIVERY_UNKNOWN (ambiguous). On startup any row still in
SENDING (a crashed run) becomes DELIVERY_UNKNOWN and is NEVER resent. Old events
past the TTL become EXPIRED_UNDELIVERED; they stay visible in history.

Sending discipline (backlog A5, `SendPacer` / `send_one`): Telegram's flood control
(RetryAfter) is not a final FAILED — the row goes back to PENDING and the run stops
sending; sends are spaced by `notifications.send_interval_ms`; no send starts after
`notifications.send_budget_s` of the run or after a stop request (SIGTERM), so a stopped
notifier leaves PENDING rows for the next run instead of SENDING rows that would become
DELIVERY_UNKNOWN. One failed recipient never blocks the others.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Protocol, Sequence

from .admin import collect_health, fingerprint
from .config import BetaConfig, BetaSwitches, effective_push_enabled
from .formatter import format_owner_alert, format_push
from .latency import class_summary, latency_field
from .models import (BRIEF_WITHDRAWAL, D_EXPIRED, D_FAILED, D_PENDING, D_SENDING, D_SENT, D_SUPPRESSED,
                     D_UNKNOWN, DELIVERY_TOO_OLD, PUSH_DISABLED, USER_INACTIVE)


# A PUSH decision nobody could receive never gets a delivery row; the scan stops looking
# for rows that old so such decisions cannot crowd out new ones (at most two pushes a day).
UNDISPATCHED_LOOKBACK = timedelta(days=7)


class DeliveryRejected(RuntimeError):
    """Telegram explicitly rejected the send (safe to record FAILED)."""


class DeliveryAmbiguous(RuntimeError):
    """The send outcome is unknown (timeout / network) — never resend."""


class DeliveryThrottled(DeliveryRejected):
    """Telegram's flood control (RetryAfter): the message was not delivered and may be sent
    again after `retry_after_s`. A caller without `send_one` records it as FAILED (never sent)."""

    def __init__(self, retry_after_s: float, message: str = ""):
        super().__init__(message or f"RetryAfter {retry_after_s:.0f}s")
        self.retry_after_s = float(retry_after_s)


# send_one outcomes
SENT, FAILED, UNKNOWN, THROTTLED, DEFERRED, RACED = "SENT", "FAILED", "UNKNOWN", "THROTTLED", "DEFERRED", "RACED"


class SendPacer:
    """One notifier run's sending discipline (backlog A5). At most one send per `interval_s`
    (Telegram allows about 30 messages a second per bot); no new send once `budget_s` of the
    run has passed (systemd stops the unit at 50 s: a send cut off there could only become
    DELIVERY_UNKNOWN), once `stop` is set (SIGTERM), or once Telegram answered RetryAfter.
    A row it holds back stays PENDING for the next run, under the same TTL."""

    def __init__(self, *, interval_s: float = 0.0, budget_s: Optional[float] = None,
                 stop: Optional[asyncio.Event] = None, monotonic=time.monotonic, sleep=asyncio.sleep):
        self.interval_s, self.budget_s, self.stop = float(interval_s), budget_s, stop
        self._mono, self._sleep = monotonic, sleep
        self._t0, self._last = monotonic(), None
        self.closed: Optional[str] = None          # THROTTLED | STOPPING | BUDGET
        self.retry_after_s: Optional[float] = None
        self.deferred = 0

    @classmethod
    def from_config(cls, cfg: BetaConfig, *, stop: Optional[asyncio.Event] = None) -> "SendPacer":
        n = cfg["notifications"]
        return cls(interval_s=int(n["send_interval_ms"]) / 1000.0, budget_s=float(n["send_budget_s"]), stop=stop)

    def is_open(self) -> bool:
        if self.closed is None:
            if self.stop is not None and self.stop.is_set():
                self.closed = "STOPPING"
            elif self.budget_s is not None and self._mono() - self._t0 >= self.budget_s:
                self.closed = "BUDGET"
        return self.closed is None

    async def pace(self) -> None:
        if self._last is not None and self.interval_s > 0:
            wait = self.interval_s - (self._mono() - self._last)
            if wait > 0:
                await self._sleep(wait)
        self._last = self._mono()

    def throttle(self, retry_after_s: float) -> None:
        self.closed, self.retry_after_s = "THROTTLED", retry_after_s

    def report(self) -> dict:
        return {"send_stop": self.closed, "deferred": self.deferred, "retry_after_s": self.retry_after_s}


async def send_one(conn, sender, pacer: SendPacer, delivery_id: int, *, chat_id: int, html: str,
                   buttons=None, clock) -> tuple:
    """One outbox send: PENDING -> SENDING (committed) -> one API call -> SENT / FAILED /
    DELIVERY_UNKNOWN; flood control puts the row back to PENDING and closes the pacer; a closed
    pacer leaves the row untouched. Returns (outcome, message_id, sent_at)."""
    if not pacer.is_open():
        pacer.deferred += 1
        return DEFERRED, None, None
    await pacer.pace()
    if not await conn.transition_delivery(delivery_id, from_state=D_PENDING, to_state=D_SENDING, now=clock()):
        return RACED, None, None
    try:
        message_id = await sender.send(chat_id=chat_id, html=html, buttons=buttons)
    except DeliveryThrottled as exc:
        await conn.requeue_delivery(delivery_id, error_summary=str(exc)[:300])
        pacer.throttle(exc.retry_after_s)
        return THROTTLED, None, None
    except DeliveryRejected as exc:
        await conn.transition_delivery(delivery_id, from_state=D_SENDING, to_state=D_FAILED, now=clock(),
                                       error_summary=str(exc)[:300])
        return FAILED, None, None
    except Exception as exc:  # noqa: BLE001 - ambiguous: never resend
        await conn.transition_delivery(delivery_id, from_state=D_SENDING, to_state=D_UNKNOWN, now=clock(),
                                       error_summary=type(exc).__name__)
        return UNKNOWN, None, None
    sent_at = clock()
    await conn.transition_delivery(delivery_id, from_state=D_SENDING, to_state=D_SENT, now=sent_at,
                                   message_id=int(message_id))
    return SENT, int(message_id), sent_at


def count_outcome(report: dict, outcome: str) -> None:
    """The run report's counters for a non-SENT outcome (SENT is counted by the caller)."""
    key = {FAILED: "failed", UNKNOWN: "unknown", THROTTLED: "throttled"}.get(outcome)
    if key:
        report[key] = report.get(key, 0) + 1


class BetaSender(Protocol):
    async def send(self, *, chat_id: int, html: str,
                   buttons: Optional[Sequence[Sequence[tuple]]] = None) -> int: ...


def feedback_buttons(public_id: str, lang: str = "ru") -> list:
    from .formatter import feedback_buttons as _buttons
    return _buttons(public_id, lang)


async def run_notify_once(store, cfg: BetaConfig, switches: BetaSwitches, *, sender: Optional[BetaSender],
                          clock, owner_user_id: Optional[int] = None, logger=None,
                          stop: Optional[asyncio.Event] = None, pacer: Optional[SendPacer] = None) -> dict:
    from storage.beta_v0_store import NOTIFIER_LOCK_KEY
    report = {"recovered_unknown": 0, "materialized": 0, "sent": 0, "failed": 0, "unknown": 0,
              "throttled": 0, "expired": 0, "suppressed": 0, "purged_users": 0, "purged_activity": 0,
              "purged_feedback_messages": 0, "purged_rejected_starts": 0, "owner_alerts": []}
    pacer = pacer if pacer is not None else SendPacer.from_config(cfg, stop=stop)
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
            for d in await conn.fetch_undispatched_push_decisions(cfg["notifications"]["max_deliveries_per_run"],
                                                                  since=now - UNDISPATCHED_LOOKBACK):
                report["materialized"] += await conn.materialize_deliveries(
                    decision_id=d["decision_id"], episode_pk=d["episode_pk"],
                    decision_ts=d["decision_ts"], expired=(now - d["decision_ts"] > ttl))
            # retention purge of long-stopped participants (personal data)
            cutoff = now - timedelta(days=cfg["privacy"]["stopped_user_retention_days"])
            for uid in await conn.stopped_users_before(cutoff):
                async with conn.transaction():
                    removed = await conn.delete_participant(uid)
                    await conn.insert_audit(action="retention_purge", authorized=True,
                                            actor_fingerprint="system", target_fingerprint=fingerprint(uid),
                                            result="OK", detail=removed)
                report["purged_users"] += 1
            activity_cutoff = now - timedelta(days=cfg["telemetry"]["retention_days"])
            report["purged_activity"] = await conn.purge_activity_before(activity_cutoff)
            report["purged_feedback_messages"] = await conn.purge_feedback_messages_before(activity_cutoff)
            rejected_cutoff = now - timedelta(days=cfg["telemetry"]["rejected_start_retention_days"])
            report["purged_rejected_starts"] = await conn.purge_rejected_starts_before(rejected_cutoff)
            push_on = effective_push_enabled(switches, await conn.get_admin_push_enabled())
            episodes: dict = {}
            analogues, since_year = await _analogue_source(conn, now)
            lat_summary = None
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
                if lat_summary is None:
                    lat_summary = await class_summary(conn, now)
                text = format_push(ep, lang=lang, gate=row.get("gate"),
                                   analog=_push_analogue(analogues, row.get("gate")), since_year=since_year,
                                   latency=latency_field("push", row["decision_ts"], now, lat_summary))
                # (2) commit PENDING -> SENDING before the single API call
                outcome, _mid, sent_at = await send_one(conn, sender, pacer, did, chat_id=row["chat_id"], html=text,
                                                        buttons=feedback_buttons(ep.public_id, lang), clock=clock)
                if outcome != SENT:
                    count_outcome(report, outcome)
                    continue
                if row.get("user_pk") is not None:
                    await conn.record_activity(user_pk=row["user_pk"], action="push_delivered",
                                               lang=lang, at=sent_at)
                report["sent"] += 1
            try:
                from .market_alerts import run_market_alerts
                report["market"] = await run_market_alerts(conn, cfg, sender=sender, clock=clock, push_on=push_on,
                                                           pacer=pacer)
            except Exception as exc:  # noqa: BLE001 - decision support never stops the outbox
                report["market_error"] = type(exc).__name__
            report["briefs"] = await run_due_briefs(conn, cfg, sender=sender, clock=clock, push_on=push_on,
                                                    pacer=pacer)
            try:
                from .weekly import run_due_weekly
                report["weekly"] = await run_due_weekly(conn, cfg, sender=sender, clock=clock, push_on=push_on,
                                                        owner_user_id=owner_user_id, pacer=pacer)
            except Exception as exc:  # noqa: BLE001 - the weekly report never stops the outbox
                report["weekly_error"] = type(exc).__name__
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
            report.update(pacer.report())
            await conn.record_health("notifier", now=clock(), success=True,
                                     detail={k: v for k, v in report.items() if isinstance(v, int)})
    report["deadman_ping"] = await deadman_ping()
    return {"status": "OK", **report}


DEADMAN_PING_ENV = "BETA_DEADMAN_PING_URL"


async def deadman_ping(url: Optional[str] = None, *, timeout_s: float = 5.0) -> str:
    """A3: after every complete notifier run, ping an external check (for example a healthchecks.io
    URL in `.env`). When the VPS, the database or this timer stops, the pings stop and the external
    service alerts the owner, which nothing on the box can do. Optional; the URL is never logged."""
    import os
    url = url if url is not None else os.environ.get(DEADMAN_PING_ENV, "").strip()
    if not url:
        return "OFF"
    if not url.startswith("https://"):
        return "REFUSED_NOT_HTTPS"

    def _get() -> int:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout_s) as r:     # noqa: S310 - https only, owner-set
            return int(r.status)
    try:
        import asyncio
        status = await asyncio.to_thread(_get)
    except Exception as exc:  # noqa: BLE001 - a failed ping is the external check's signal, not ours
        import logging
        logging.getLogger("beta.delivery").warning("dead-man ping failed: %s", type(exc).__name__)
        return "FAILED"
    return "OK" if 200 <= status < 300 else "FAILED"


async def _analogue_source(conn, now: datetime) -> tuple:
    """(analogue statistics, first year of the history) for the push's «после похожих» line."""
    try:
        from .decision import latest_stats
        stats = await latest_stats(conn, now=now)
    except Exception:  # noqa: BLE001 - the line is optional; the push is not
        return None, None
    if not stats:
        return None, None
    ms = (stats.get("data") or {}).get("from_ms")
    year = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).year if ms else None
    return stats.get("analogues"), year


def _push_analogue(analogues, gate) -> Optional[dict]:
    from .analogues import lookup
    from .interpretation import COMPRESSION, FACTUAL, INTERPRETED
    res = (gate or {}).get("interpretation") or {}
    if res.get("kind") not in (INTERPRETED, FACTUAL, COMPRESSION):
        return None
    return lookup(analogues, "1h", res.get("key"))


def brief_slot(now: datetime, time_kyiv: str):
    """(Kyiv date, UTC instant) of today's briefing slot, or None before it."""
    from datetime import time as dtime
    from .i18n import KYIV
    local = now.astimezone(KYIV)
    hh, mm = int(time_kyiv[:2]), int(time_kyiv[3:])
    slot = datetime.combine(local.date(), dtime(hh, mm), tzinfo=KYIV)
    if local < slot:
        return None
    return local.date(), slot.astimezone(now.tzinfo)


def brief_withdrawal_dates(briefing: Mapping[str, Any]) -> frozenset:
    """The U1a withdrawal days (Kyiv dates), the same for every participant.

    Frozen before Day 0 (BETA_MEASUREMENT_CONTRACT_V1 §6): `count` weekdays drawn with
    `seed` from cohort days first..last (Day 0 = cohort day 0). Only `day0_kyiv` is filled
    in when Day 0 happens; nothing here may change after it. Empty while day0 is unset."""
    import random
    from datetime import date
    w = briefing.get("withdrawal") or {}
    if not w.get("day0_kyiv"):
        return frozenset()
    day0 = date.fromisoformat(w["day0_kyiv"])
    weekdays = [day0 + timedelta(days=n) for n in range(int(w["first_cohort_day"]), int(w["last_cohort_day"]) + 1)
                if (day0 + timedelta(days=n)).weekday() < 5]
    return frozenset(random.Random(int(w["seed"])).sample(weekdays, int(w["count"])))


async def run_due_briefs(conn, cfg: BetaConfig, *, sender: Optional[BetaSender], clock, push_on: bool,
                         pacer: Optional[SendPacer] = None) -> dict:
    """The morning briefing inside the existing notifier cycle and outbox.

    Once per Kyiv day after `briefing.time_kyiv`: build ONE shared view (kind
    'brief', the /catchup render path), persist it, and materialize one PENDING
    outbox row per ACTIVE participant with the briefing on. Each row then follows
    the outbox rules: at most one send attempt, never late (expired after
    `max_delay_min`), suppressed while pushes are switched off. Push rows, push
    decisions and push policy are not read or changed here."""
    from .formatter import btc_buttons, format_catchup
    from .market_view import BRIEF_WINDOW_HOURS, build_view, maturity_days, persist_view
    from .config import effective_d7_enabled
    b = cfg.section("briefing")
    out = {"scheduled": 0, "sent": 0, "failed": 0, "unknown": 0, "throttled": 0, "expired": 0, "suppressed": 0,
           "withheld": 0}
    pacer = pacer if pacer is not None else SendPacer()
    max_delay = timedelta(minutes=int(b["max_delay_min"]))
    withdrawn = brief_withdrawal_dates(b)
    now = clock()
    slot = brief_slot(now, b["time_kyiv"])
    if b["enabled"] and push_on and slot is not None and now - slot[1] <= max_delay \
            and not await conn.brief_scheduled(slot[0]):
        view = await build_view(conn, cfg, now=now, kind="brief", window_hours=BRIEF_WINDOW_HOURS,
                                maturity_days=maturity_days(cfg),
                                d7_enabled=effective_d7_enabled(cfg, await conn.get_admin_d7_enabled()))
        view_pk = await persist_view(conn, view, now=now, text=format_catchup(cfg, view, "ru"), lang="ru",
                                     kind="brief")
        out["scheduled"] = await conn.materialize_brief_deliveries(brief_date=slot[0], view_pk=view_pk,
                                                                   decision_ts=slot[1])
    views: dict = {}
    for row in await conn.fetch_pending_brief_deliveries(cfg["notifications"]["max_deliveries_per_run"]):
        now = clock()
        did = row["delivery_id"]
        if now - row["decision_ts"] > max_delay:
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_EXPIRED, now=now,
                                           suppression_reason=DELIVERY_TOO_OLD)
            out["expired"] += 1
            continue
        if not (b["enabled"] and push_on):
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SUPPRESSED, now=now,
                                           suppression_reason=PUSH_DISABLED)
            out["suppressed"] += 1
            continue
        if row["user_status"] != "ACTIVE" or not row.get("brief_enabled", True):
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SUPPRESSED, now=now,
                                           suppression_reason=USER_INACTIVE)
            out["suppressed"] += 1
            continue
        if row["brief_date"] in withdrawn:
            # U1a: withheld for everyone who would have received it; observable per participant
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SUPPRESSED, now=now,
                                           suppression_reason=BRIEF_WITHDRAWAL)
            if row.get("user_pk") is not None:
                await conn.record_activity(user_pk=row["user_pk"], action="brief_withheld",
                                           lang=row.get("user_lang") or "ru", at=now,
                                           detail=row["brief_date"].isoformat())
            out["withheld"] += 1
            continue
        if sender is None:
            await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_FAILED, now=now,
                                           error_summary="sender unavailable (no bot token)")
            out["failed"] += 1
            continue
        payload = views.get(row["view_pk"])
        if payload is None:
            payload = views[row["view_pk"]] = (await conn.fetch_btc_view(row["view_pk"]))["payload"]
        lang = row.get("user_lang") or "ru"
        text = format_catchup(cfg, payload, lang, push_enabled=bool(row.get("push_enabled", True)),
                              first_brief=bool(row.get("first_brief", False)))
        outcome, _mid, sent_at = await send_one(conn, sender, pacer, did, chat_id=row["chat_id"], html=text,
                                                buttons=btc_buttons(payload, lang, row["view_pk"]), clock=clock)
        if outcome != SENT:
            count_outcome(out, outcome)
            continue
        if row.get("user_pk") is not None:
            await conn.record_activity(user_pk=row["user_pk"], action="brief_delivered", lang=lang, at=sent_at)
        out["sent"] += 1
        await _link_brief_claims(conn, cfg, row["view_pk"], payload, sent_at=sent_at)
    return out


async def _link_brief_claims(conn, cfg: BetaConfig, view_pk: int, payload: Mapping[str, Any], *,
                             sent_at: datetime) -> None:
    """The brief's claims count as shown once a participant actually received it: after the first SENT
    row of the view, never at scheduling (a withdrawal day or a paused bot shows nothing). Best-effort:
    the journal never stops the remaining sends."""
    if not cfg.section("decision").get("claim_journal") or not payload.get("requested_at"):
        return
    try:
        if await conn.view_has_claim_displays(view_pk):
            return
        from .claims import record_displays, shown_keys
        built = datetime.fromisoformat(payload["requested_at"]).astimezone(timezone.utc)
        await record_displays(conn, surface="brief", now=sent_at, view_pk=view_pk,
                              slot=built.replace(minute=0, second=0, microsecond=0),
                              shown=shown_keys("brief", payload.get("decision"), market=payload.get("market")))
    except Exception as exc:  # noqa: BLE001 - the journal never breaks a delivery run
        logging.getLogger("beta.delivery").warning("brief display link failed: %s", type(exc).__name__)
