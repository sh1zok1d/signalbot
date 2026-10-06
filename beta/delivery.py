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
from .config import BetaConfig, BetaSwitches, effective_push_enabled, research_main_surfaces_enabled
from .formatter import format_owner_alert, format_push
from .i18n import render_tz
from .latency import class_summary, latency_field
from .detector import in_quiet_hours
from .models import (BRIEF_WITHDRAWAL, D_EXPIRED, D_FAILED, D_PENDING, D_SENDING, D_SENT, D_SUPPRESSED,
                     D_UNKNOWN, DELIVERY_TOO_OLD, PUSH_DISABLED, QUIET_HOURS, USER_INACTIVE)


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
    """One notifier run's sending discipline (backlog A5; external review of A5).

    - At most one send per `interval_s` (Telegram allows about 30 messages a second per bot) and
      one per `per_chat_s` to the same chat (about one a second).
    - No new send once `budget_s` has passed since the process started (`elapsed_s` is the time
      already spent before the pacer was made; systemd stops the unit at 50 s, and a send cut off
      there could only become DELIVERY_UNKNOWN), and none once `stop` is set (SIGTERM).
    - Telegram's flood control (RetryAfter) defers that chat only; `max_throttles` refusals in one
      run close the pacer for every chat (the limit is then the bot's, not one chat's).
    A row it holds back stays PENDING for the next run, under the same TTL."""

    def __init__(self, *, interval_s: float = 0.0, budget_s: Optional[float] = None,
                 stop: Optional[asyncio.Event] = None, elapsed_s: float = 0.0, per_chat_s: float = 0.0,
                 max_throttles: int = 3, monotonic=time.monotonic, sleep=asyncio.sleep):
        self.interval_s, self.budget_s, self.stop = float(interval_s), budget_s, stop
        self.per_chat_s, self.max_throttles = float(per_chat_s), int(max_throttles)
        self._mono, self._sleep = monotonic, sleep
        self._t0, self._last = monotonic() - float(elapsed_s), None
        self._last_chat: dict = {}
        self.blocked_chats: set = set()
        self.throttles = 0
        self.closed: Optional[str] = None          # THROTTLED | STOPPING | BUDGET
        self.retry_after_s: Optional[float] = None
        self.deferred = 0

    @classmethod
    def from_config(cls, cfg: BetaConfig, *, stop: Optional[asyncio.Event] = None,
                    elapsed_s: float = 0.0) -> "SendPacer":
        n = cfg["notifications"]
        return cls(interval_s=int(n["send_interval_ms"]) / 1000.0, budget_s=float(n["send_budget_s"]), stop=stop,
                   elapsed_s=elapsed_s, per_chat_s=PER_CHAT_INTERVAL_S)

    def is_open(self) -> bool:
        if self.closed is None:
            if self.stop is not None and self.stop.is_set():
                self.closed = "STOPPING"
            elif self.budget_s is not None and self._mono() - self._t0 >= self.budget_s:
                self.closed = "BUDGET"
        return self.closed is None

    def may_send(self, chat_id) -> bool:
        return self.is_open() and chat_id not in self.blocked_chats

    async def pace(self, chat_id=None) -> None:
        now = self._mono()
        wait = 0.0
        if self._last is not None and self.interval_s > 0:
            wait = self.interval_s - (now - self._last)
        last_chat = self._last_chat.get(chat_id)
        if last_chat is not None and self.per_chat_s > 0:
            wait = max(wait, self.per_chat_s - (now - last_chat))
        if wait > 0:
            await self._sleep(wait)
        self._last = self._mono()
        self._last_chat[chat_id] = self._last

    def throttle(self, retry_after_s: float, chat_id=None) -> None:
        """Flood control for `chat_id`: that chat waits; `max_throttles` in one run stop every chat."""
        self.throttles += 1
        self.retry_after_s = max(self.retry_after_s or 0.0, float(retry_after_s))
        if chat_id is not None:
            self.blocked_chats.add(chat_id)
        if chat_id is None or self.throttles >= self.max_throttles:
            self.closed = "THROTTLED"

    def report(self) -> dict:
        stop = self.closed
        if stop is None and self.stop is not None and self.stop.is_set():
            stop = "STOPPING"                    # the stop came after the last send
        return {"send_stop": stop, "deferred": self.deferred, "retry_after_s": self.retry_after_s,
                "throttled_chats": len(self.blocked_chats)}


PER_CHAT_INTERVAL_S = 1.0


def process_age_s() -> float:
    """Seconds since this process started (Linux /proc; 0 elsewhere): the notifier unit's timeout
    runs from the start, not from the moment the pacer is made."""
    import os
    try:
        with open("/proc/self/stat", encoding="ascii") as f:
            start_ticks = int(f.read().rsplit(")", 1)[1].split()[19])
        with open("/proc/uptime", encoding="ascii") as f:
            uptime = float(f.read().split()[0])
        return max(0.0, uptime - start_ticks / os.sysconf("SC_CLK_TCK"))
    except (OSError, ValueError, IndexError):
        return 0.0


def retry_at(now: datetime, retry_after_s: float) -> datetime:
    """When a row refused by flood control may be tried again: Telegram's own wait, at least 1 s."""
    import math
    return now + timedelta(seconds=max(1, math.ceil(float(retry_after_s))))


async def send_one(conn, sender, pacer: SendPacer, delivery_id: int, *, chat_id: int, html: str,
                   buttons=None, clock) -> tuple:
    """One outbox send: PENDING -> SENDING (committed) -> one API call -> SENT / FAILED /
    DELIVERY_UNKNOWN. Flood control puts the row back to PENDING until `next_attempt_at` and
    defers that chat; a closed pacer (checked again after the pause) leaves the row untouched.
    Returns (outcome, message_id, sent_at)."""
    if not pacer.may_send(chat_id):
        pacer.deferred += 1
        return DEFERRED, None, None
    await pacer.pace(chat_id)
    if not pacer.may_send(chat_id):              # a stop or the budget during the pause
        pacer.deferred += 1
        return DEFERRED, None, None
    if not await conn.transition_delivery(delivery_id, from_state=D_PENDING, to_state=D_SENDING, now=clock()):
        return RACED, None, None
    try:
        message_id = await sender.send(chat_id=chat_id, html=html, buttons=buttons)
    except DeliveryThrottled as exc:
        await conn.requeue_delivery(delivery_id, error_summary=str(exc)[:300],
                                    next_attempt_at=retry_at(clock(), exc.retry_after_s))
        pacer.throttle(exc.retry_after_s, chat_id)
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


async def send_direct(sender, pacer: SendPacer, *, chat_id: int, html: str) -> str:
    """A message outside the outbox (the owner's alert, the owner's weekly copy) under the same
    pacer: DEFERRED when it is closed for that chat, THROTTLED after flood control, else SENT or
    FAILED. Never raises."""
    if not pacer.may_send(chat_id):
        return DEFERRED
    await pacer.pace(chat_id)
    if not pacer.may_send(chat_id):
        return DEFERRED
    try:
        await sender.send(chat_id=chat_id, html=html)
    except DeliveryThrottled as exc:
        pacer.throttle(exc.retry_after_s, chat_id)
        return THROTTLED
    except Exception as exc:  # noqa: BLE001 - reported by the caller
        logging.getLogger("beta.delivery").warning("direct send failed: %s", type(exc).__name__)
        return FAILED
    return SENT


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
                          stop: Optional[asyncio.Event] = None, pacer: Optional[SendPacer] = None,
                          ping: bool = False) -> dict:
    """One notifier run. `stop` (SIGTERM) ends the run at the next step: nothing more is sent or
    built, and neither the success heartbeat nor the dead-man ping is written. `ping` (the unit's
    `--beta-deadman-ping`) pings the external check after a complete run."""
    from storage.beta_v0_store import NOTIFIER_LOCK_KEY
    report = {"recovered_unknown": 0, "materialized": 0, "sent": 0, "failed": 0, "unknown": 0,
              "throttled": 0, "expired": 0, "suppressed": 0, "purged_users": 0, "purged_activity": 0,
              "purged_feedback_messages": 0, "purged_rejected_starts": 0, "owner_alerts": []}
    if pacer is None:
        pacer = SendPacer.from_config(cfg, stop=stop)
    elif stop is not None and pacer.stop is None:
        pacer.stop = stop                        # a given pacer still sees the stop

    def stopped() -> bool:
        return stop is not None and stop.is_set()

    def stop_report() -> dict:
        report.update(pacer.report())
        return {"status": "STOPPED", **report}

    if not switches.enabled:
        return {"status": "DISABLED", "switches": switches.as_dict(),
                **({"deadman_ping": await deadman_ping()} if ping else {})}
    if not switches.telegram:
        return {"status": "TELEGRAM_DISABLED", "switches": switches.as_dict(),
                **({"deadman_ping": await deadman_ping()} if ping else {})}
    ttl = cfg.delivery_ttl
    max_rows = cfg["notifications"]["max_deliveries_per_run"]
    async with store.advisory_lock(NOTIFIER_LOCK_KEY) as acquired:
        if not acquired:
            return {"status": "LOCKED"}
        async with store.connect() as conn:
            now = clock()
            report["recovered_unknown"] = await conn.recover_sending(now)
            for d in await conn.fetch_undispatched_push_decisions(max_rows, since=now - UNDISPATCHED_LOOKBACK):
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
            if stopped():
                return stop_report()
            push_on = effective_push_enabled(switches, await conn.get_admin_push_enabled())
            episodes: dict = {}
            analogues, since_year = await _analogue_source(conn, now)
            lat_summary = None
            for row in await conn.fetch_pending_deliveries(max_rows, now=now):
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
                if in_quiet_hours(cfg, row["decision_ts"], row.get("user_tz")):
                    # the decision went out because someone was awake; it is this participant's night (C5)
                    await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_SUPPRESSED, now=now,
                                                   suppression_reason=QUIET_HOURS)
                    report["suppressed"] += 1
                    continue
                if sender is None:
                    await conn.transition_delivery(did, from_state=D_PENDING, to_state=D_FAILED, now=now,
                                                   error_summary="sender unavailable (no bot token)")
                    report["failed"] += 1
                    continue
                if not pacer.may_send(row["chat_id"]):      # nothing is rendered for a row that waits
                    pacer.deferred += 1
                    continue
                ep = episodes.get(row["episode_pk"])
                if ep is None:
                    ep = episodes[row["episode_pk"]] = await conn.fetch_episode_by_pk(row["episode_pk"])
                lang = row.get("user_lang") or "ru"
                if lat_summary is None:
                    lat_summary = await class_summary(conn, now)
                with render_tz(row.get("user_tz")):          # the recipient's clock (C5)
                    text = format_push(ep, lang=lang, gate=row.get("gate"),
                                       analog=_push_analogue(analogues, row.get("gate")), since_year=since_year,
                                       latency=latency_field("push", row["decision_ts"], now, lat_summary),
                                       research=research_main_surfaces_enabled(cfg))
                # (2) commit PENDING -> SENDING before the single API call
                outcome, _mid, sent_at = await send_one(conn, sender, pacer, did, chat_id=row["chat_id"],
                                                        html=text, buttons=feedback_buttons(ep.public_id, lang),
                                                        clock=clock)
                if outcome != SENT:
                    count_outcome(report, outcome)
                    continue
                if row.get("user_pk") is not None:
                    await conn.record_activity(user_pk=row["user_pk"], action="push_delivered",
                                               lang=lang, at=sent_at)
                report["sent"] += 1
            if stopped():
                return stop_report()
            report["market"] = await _step(conn, "notify_market", "market_error", report, clock,
                                           _market(conn, cfg, sender, clock, push_on, pacer))
            if stopped():
                return stop_report()
            report["briefs"] = await run_due_briefs(conn, cfg, sender=sender, clock=clock, push_on=push_on,
                                                    pacer=pacer)
            if stopped():
                return stop_report()
            report["weekly"] = await _step(conn, "notify_weekly", "weekly_error", report, clock,
                                           _weekly(conn, cfg, sender, clock, push_on, owner_user_id, pacer))
            if stopped():
                return stop_report()
            # this run is itself the notifier heartbeat (recorded before evaluating alerts)
            await conn.record_health("notifier", now=clock(), success=True)
            # owner health alerts (operational; owner only; rate-limited per key), under the same pacer:
            # not sent once it is closed (they are due again on the next run)
            if sender is not None and owner_user_id is not None:
                h = await collect_health(conn, cfg, switches, clock())
                runtime = await conn.fetch_health()
                due = []
                for a in h["alerts"]:
                    last = (runtime.get(f"owner_alert:{a['key']}") or {}).get("last_success_at")
                    if last is None or (clock() - last).total_seconds() >= cfg["health"]["owner_alert_repeat_s"]:
                        due.append(a)
                if due:
                    res = await send_direct(sender, pacer, chat_id=owner_user_id, html=format_owner_alert(due))
                    if res == SENT:
                        for a in due:
                            await conn.record_health(f"owner_alert:{a['key']}", now=clock(), success=True)
                        report["owner_alerts"] = [a["key"] for a in due]
                    else:
                        report["owner_alert_error"] = res
            if stopped():
                return stop_report()
            report.update(pacer.report())
            await conn.record_health("notifier", now=clock(), success=True,
                                     detail={k: v for k, v in report.items() if isinstance(v, int)})
    if ping:
        report["deadman_ping"] = await deadman_ping()
    return {"status": "OK", **report}


async def _market(conn, cfg, sender, clock, push_on, pacer):
    from .market_alerts import run_market_alerts
    return await run_market_alerts(conn, cfg, sender=sender, clock=clock, push_on=push_on, pacer=pacer)


async def _weekly(conn, cfg, sender, clock, push_on, owner_user_id, pacer):
    from .weekly import run_due_weekly
    return await run_due_weekly(conn, cfg, sender=sender, clock=clock, push_on=push_on,
                                owner_user_id=owner_user_id, pacer=pacer)


async def _step(conn, component: str, error_key: str, report: dict, clock, work) -> Optional[dict]:
    """A notifier step that never stops the outbox: its failure goes to the report and to the
    step's own health row, so the owner hears of it (NOTIFIER_STEP_FAILED; A3 review)."""
    try:
        out = await work
    except Exception as exc:  # noqa: BLE001 - decision support and the weekly report never stop the outbox
        report[error_key] = type(exc).__name__
        try:
            await conn.record_health(component, now=clock(), success=False, error_type=type(exc).__name__)
        except Exception:  # noqa: BLE001 - the original failure is already in the report
            pass
        return None
    await conn.record_health(component, now=clock(), success=True)
    return out


DEADMAN_PING_ENV = "BETA_DEADMAN_PING_URL"


async def deadman_ping(url: Optional[str] = None, *, timeout_s: float = 5.0) -> str:
    """A3: after every complete notifier run started with `--beta-deadman-ping` (the unit only, so
    tests and manual runs never ping), ping an external check (for example a healthchecks.io URL in
    `.env`). When the VPS, the database or this timer stops, the pings stop and the external service
    alerts the owner, which nothing on the box can do. The URL is never logged.

    The whole ping, name resolution included, is bounded by `timeout_s`: it runs in a daemon thread
    that is abandoned at the deadline (urlopen's own timeout does not cover DNS)."""
    import os
    import threading
    url = url if url is not None else os.environ.get(DEADMAN_PING_ENV, "").strip()
    if not url:
        return "OFF"
    if not url.startswith("https://"):
        return "REFUSED_NOT_HTTPS"
    loop = asyncio.get_running_loop()
    done: asyncio.Future = loop.create_future()

    def _get() -> None:
        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=timeout_s) as r:     # noqa: S310 - https only, owner-set
                result = "OK" if 200 <= int(r.status) < 300 else "FAILED"
        except Exception as exc:  # noqa: BLE001 - a failed ping is the external check's signal, not ours
            logging.getLogger("beta.delivery").warning("dead-man ping failed: %s", type(exc).__name__)
            result = "FAILED"
        try:
            loop.call_soon_threadsafe(lambda: done.done() or done.set_result(result))
        except RuntimeError:                       # the loop is gone: the run already ended
            pass

    threading.Thread(target=_get, name="deadman-ping", daemon=True).start()
    try:
        return await asyncio.wait_for(asyncio.shield(done), timeout=timeout_s)
    except asyncio.TimeoutError:
        logging.getLogger("beta.delivery").warning("dead-man ping timed out")
        return "TIMEOUT"


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


def brief_slot(now: datetime, time_kyiv: str, tz: Optional[str] = None):
    """(local date, UTC instant) of today's briefing slot on the participant's clock (Kyiv when `tz` is
    None; backlog C5 / E3), or None before it."""
    from datetime import time as dtime
    from .i18n import tz_of
    zone = tz_of(tz)
    local = now.astimezone(zone)
    hh, mm = int(time_kyiv[:2]), int(time_kyiv[3:])
    slot = datetime.combine(local.date(), dtime(hh, mm), tzinfo=zone)
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

    Each participant has a slot on their own clock: their `brief_time` (default
    `briefing.time_kyiv`) in their time zone (backlog C5 / E3). In a run where some
    participants' slots have come and they have no briefing row for their local date,
    build ONE shared view (kind 'brief', the /catchup render path), persist it, and
    materialize one PENDING outbox row per such participant. Each row then follows
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
    due = []
    if b["enabled"] and push_on:
        for u in await conn.brief_candidates():
            slot = brief_slot(now, u.get("brief_time") or b["time_kyiv"], u.get("tz"))
            if slot is None or now - slot[1] > max_delay:
                continue
            if u.get("last_brief_date") is not None and u["last_brief_date"] >= slot[0]:
                continue                                    # this local day already has its row
            due.append((u["user_pk"], slot))
    if due:
        view = await build_view(conn, cfg, now=now, kind="brief", window_hours=BRIEF_WINDOW_HOURS,
                                maturity_days=maturity_days(cfg),
                                d7_enabled=effective_d7_enabled(cfg, await conn.get_admin_d7_enabled()))
        view_pk = await persist_view(conn, view, now=now, text=format_catchup(cfg, view, "ru"), lang="ru",
                                     kind="brief")
        for user_pk, (brief_date, at) in due:
            out["scheduled"] += await conn.materialize_brief_delivery(user_pk=user_pk, brief_date=brief_date,
                                                                      view_pk=view_pk, decision_ts=at)
    views: dict = {}
    for row in await conn.fetch_pending_brief_deliveries(cfg["notifications"]["max_deliveries_per_run"],
                                                         now=clock()):
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
        if not pacer.may_send(row["chat_id"]):          # nothing is rendered for a row that waits
            pacer.deferred += 1
            continue
        payload = views.get(row["view_pk"])
        if payload is None:
            payload = views[row["view_pk"]] = (await conn.fetch_btc_view(row["view_pk"]))["payload"]
        lang = row.get("user_lang") or "ru"
        with render_tz(row.get("user_tz")):              # the recipient's clock (C5)
            text = format_catchup(cfg, payload, lang, push_enabled=bool(row.get("push_enabled", True)),
                                  first_brief=bool(row.get("first_brief", False)))
            buttons = btc_buttons(payload, lang, row["view_pk"])
        outcome, _mid, sent_at = await send_one(conn, sender, pacer, did, chat_id=row["chat_id"], html=text,
                                                buttons=buttons, clock=clock)
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
