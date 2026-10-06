"""Sending discipline (backlog A5, with the external review of A5), pure: the pacer's interval, per-chat
interval, budget counted from the process start, stop and flood-control states; every `send_one`
outcome; Telegram's RetryAfter as a later retry of that chat only; the owner's direct sends under the
same pacer; the budget bound against the notifier unit's timeout. Synthetic inputs only."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from beta.config import NOTIFY_BUDGET_MAX_S, SEND_TIMEOUTS_S, BetaConfig, BetaConfigError
from beta.delivery import (DEFERRED, FAILED, RACED, SENT, THROTTLED, UNKNOWN, DeliveryAmbiguous, DeliveryRejected,
                           DeliveryThrottled, SendPacer, process_age_s, send_direct, send_one)

T = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


class _Mono:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _pacer(**kw):
    mono, waits = _Mono(), []

    async def sleep(s):
        waits.append(round(s, 3))
        mono.t += s
    return SendPacer(monotonic=mono, sleep=sleep, **kw), mono, waits


def test_the_pacer_spaces_sends_globally_and_per_chat():
    p, mono, waits = _pacer(interval_s=0.05, per_chat_s=1.0)
    asyncio.run(p.pace(1))
    mono.t += 0.02
    asyncio.run(p.pace(2))                      # another chat 20 ms later: waits the remaining 30 ms
    asyncio.run(p.pace(1))                      # chat 1 again: waits for its own second
    assert waits == [0.03, 0.95]


def test_the_budget_counts_from_the_process_start():
    """A5 review 5: the unit's timeout runs from the process start, not from the pacer."""
    p, mono, _ = _pacer(budget_s=20, elapsed_s=19.5)
    assert p.is_open()
    mono.t += 0.6
    assert not p.is_open() and p.closed == "BUDGET"
    assert 0 < process_age_s() < 3600 * 24 * 365
    assert SendPacer.from_config(BetaConfig.load(), elapsed_s=25.0).is_open() is False     # budget 20 s


def test_flood_control_waits_for_that_chat_only_until_it_repeats():
    """A5 review 7: one chat's 429 never closes the run for the others; three in one run do."""
    p, _, _ = _pacer()
    p.throttle(5, chat_id=1)
    assert not p.may_send(1) and p.may_send(2) and p.closed is None
    p.throttle(7, chat_id=2)
    p.throttle(3, chat_id=3)
    assert p.closed == "THROTTLED" and not p.may_send(4) and p.retry_after_s == 7.0
    assert p.report()["throttled_chats"] == 3


def test_a_stop_is_seen_in_the_report_and_through_a_given_pacer():
    """A5 review 10 and 11: a stop after the last send still shows; a given pacer still sees the stop."""
    stop = asyncio.Event()
    p, _, _ = _pacer(stop=stop)
    stop.set()
    assert p.report()["send_stop"] == "STOPPING"                 # no send was tried after the stop
    from beta.delivery import run_notify_once
    from beta.config import BetaSwitches
    given, _, _ = _pacer()
    sw = BetaSwitches(enabled=False, detection=False, push_hard=False, outcome_tracking=False)
    asyncio.run(run_notify_once(None, BetaConfig.load(), sw, sender=None, clock=lambda: T, stop=stop, pacer=given))
    assert given.stop is stop and not given.is_open()


class _Conn:
    def __init__(self, transition_ok=True):
        self.calls, self.ok = [], transition_ok

    async def transition_delivery(self, did, *, from_state, to_state, now, **kw):
        self.calls.append((from_state, to_state, kw.get("error_summary")))
        return self.ok if to_state == "SENDING" else True

    async def requeue_delivery(self, did, *, error_summary, next_attempt_at):
        self.calls.append(("SENDING", "PENDING", error_summary, next_attempt_at))
        return True


class _Sender:
    def __init__(self, exc=None, on_send=None):
        self.exc, self.n, self.on_send = exc, 0, on_send

    async def send(self, *, chat_id, html, buttons=None):
        self.n += 1
        if self.on_send:
            self.on_send()
        if self.exc is not None:
            raise self.exc
        return 77


def _one(conn, sender, pacer=None, chat_id=5):
    return asyncio.run(send_one(conn, sender, pacer or SendPacer(), 1, chat_id=chat_id, html="x", clock=lambda: T))


def test_every_send_outcome():
    c = _Conn()
    assert _one(c, _Sender()) == (SENT, 77, T) and c.calls[-1][:2] == ("SENDING", "SENT")
    c = _Conn()
    assert _one(c, _Sender(DeliveryRejected("Forbidden: bot was blocked")))[0] == FAILED
    assert c.calls[-1] == ("SENDING", "FAILED", "Forbidden: bot was blocked")
    c = _Conn()
    assert _one(c, _Sender(DeliveryAmbiguous("TimedOut")))[0] == UNKNOWN and c.calls[-1][1] == "DELIVERY_UNKNOWN"
    s = _Sender()
    assert _one(_Conn(transition_ok=False), s)[0] == RACED and s.n == 0            # another run took the row


def test_flood_control_requeues_with_its_wait_and_defers_that_chat():
    """A5 review 1: the wait is stored on the row (next_attempt_at), not only in the run."""
    c, p = _Conn(), SendPacer()
    assert _one(c, _Sender(DeliveryThrottled(7)), p, chat_id=5)[0] == THROTTLED
    assert c.calls[-1] == ("SENDING", "PENDING", "RetryAfter 7s", T + timedelta(seconds=7))
    s = _Sender()
    assert _one(_Conn(), s, p, chat_id=5)[0] == DEFERRED and s.n == 0 and p.deferred == 1
    assert _one(_Conn(), _Sender(), p, chat_id=6)[0] == SENT                         # another chat goes on


def test_a_stop_during_the_pause_starts_no_send():
    """A5 review 6: the pacer is checked again after its pause."""
    stop = asyncio.Event()
    mono = _Mono()

    async def sleep(s):
        stop.set()                                # SIGTERM arrives while the pacer waits
        mono.t += s
    p = SendPacer(interval_s=0.05, stop=stop, monotonic=mono, sleep=sleep)
    c, s = _Conn(), _Sender()
    assert _one(c, s, p)[0] == SENT
    assert _one(c, s, p)[0] == DEFERRED and s.n == 1 and c.calls[-1][1] == "SENT"     # no second SENDING


def test_the_owner_direct_send_follows_the_same_pacer():
    """A5 review 4: the owner's alert and weekly copy go through the pacer and its flood control."""
    p = SendPacer()
    assert asyncio.run(send_direct(_Sender(), p, chat_id=9, html="x")) == SENT
    assert asyncio.run(send_direct(_Sender(DeliveryThrottled(4)), p, chat_id=9, html="x")) == THROTTLED
    s = _Sender()
    assert asyncio.run(send_direct(s, p, chat_id=9, html="x")) == DEFERRED and s.n == 0
    closed = SendPacer()
    closed.closed = "BUDGET"
    assert asyncio.run(send_direct(_Sender(), closed, chat_id=9, html="x")) == DEFERRED
    assert asyncio.run(send_direct(_Sender(RuntimeError("x")), SendPacer(), chat_id=9, html="x")) == FAILED


def test_retry_after_is_a_retry_not_a_final_failure(monkeypatch):
    from telegram.error import RetryAfter

    from runtime.beta_bot import BetaTelegramSender, retry_after_seconds

    class _Bot:
        async def send_message(self, **kw):
            raise RetryAfter(5)
    sender = BetaTelegramSender("123:abc")
    monkeypatch.setattr(sender, "_ensure_bot", lambda: _Bot())
    with pytest.raises(DeliveryThrottled) as err:
        asyncio.run(sender.send(chat_id=1, html="x"))
    assert err.value.retry_after_s == 5.0 and isinstance(err.value, DeliveryRejected)   # a non-outbox caller: not sent

    class _Later:
        retry_after = timedelta(seconds=9)
    assert retry_after_seconds(_Later()) == 9.0


def test_the_send_budget_leaves_one_send_and_the_tail_before_the_unit_timeout():
    """A5 review 5: one send can take the sum of the sender's timeouts; the budget leaves it and the tail."""
    assert sum(SEND_TIMEOUTS_S) == 17 and NOTIFY_BUDGET_MAX_S == 25
    base = BetaConfig.load()
    assert base["notifications"]["send_interval_ms"] == 50 and base["notifications"]["send_budget_s"] == 20
    with pytest.raises(BetaConfigError, match="send_budget_s"):
        base.with_overrides(notifications={**dict(base["notifications"]), "send_budget_s": 26})
    from runtime.beta_bot import BetaTelegramSender
    req = BetaTelegramSender("123:abc")._ensure_bot().request
    assert req._client_kwargs["timeout"].read == SEND_TIMEOUTS_S[2]


def test_the_budget_bound_matches_the_notifier_unit():
    import re
    from pathlib import Path

    from beta.config import NOTIFY_UNIT_TIMEOUT_S
    unit = (Path(__file__).resolve().parents[2] / "deploy" / "signalbot-beta-notify.service").read_text()
    assert int(re.search(r"^TimeoutStartSec=(\d+)$", unit, re.M).group(1)) == NOTIFY_UNIT_TIMEOUT_S
    # A3 review 6: only the unit pings the external dead-man check
    assert "--beta-notify-once --beta-deadman-ping" in unit
