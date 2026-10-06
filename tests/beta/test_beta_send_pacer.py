"""Sending discipline (backlog A5), pure: the pacer's interval, budget, stop and flood-control states,
every `send_one` outcome, Telegram's RetryAfter mapped to a retry instead of a final FAILED, and the
budget bound against the notifier unit's timeout. Synthetic inputs only."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from beta.config import BetaConfig, BetaConfigError
from beta.delivery import (DEFERRED, FAILED, RACED, SENT, THROTTLED, UNKNOWN, DeliveryAmbiguous, DeliveryRejected,
                           DeliveryThrottled, SendPacer, send_one)

T = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


class _Mono:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_the_pacer_spaces_sends_and_closes_on_budget_stop_or_flood_control():
    mono, waits = _Mono(), []

    async def sleep(s):
        waits.append(round(s, 3))
        mono.t += s

    p = SendPacer(interval_s=0.05, budget_s=10, monotonic=mono, sleep=sleep)
    asyncio.run(p.pace())
    mono.t += 0.02
    asyncio.run(p.pace())                       # 20 ms after the last send: waits the remaining 30 ms
    mono.t += 1.0
    asyncio.run(p.pace())                       # a slow send already spaced them: no wait
    assert waits == [0.03] and p.is_open()
    mono.t = 10.0
    assert not p.is_open() and p.closed == "BUDGET"

    stop = asyncio.Event()
    p = SendPacer(stop=stop)
    assert p.is_open()
    stop.set()
    assert not p.is_open() and p.report() == {"send_stop": "STOPPING", "deferred": 0, "retry_after_s": None}
    p = SendPacer()
    p.throttle(12)
    assert not p.is_open() and p.report()["retry_after_s"] == 12


class _Conn:
    def __init__(self, transition_ok=True):
        self.calls, self.ok = [], transition_ok

    async def transition_delivery(self, did, *, from_state, to_state, now, **kw):
        self.calls.append((from_state, to_state, kw.get("error_summary")))
        return self.ok if to_state == "SENDING" else True

    async def requeue_delivery(self, did, *, error_summary):
        self.calls.append(("SENDING", "PENDING", error_summary))
        return True


class _Sender:
    def __init__(self, exc=None):
        self.exc, self.n = exc, 0

    async def send(self, *, chat_id, html, buttons=None):
        self.n += 1
        if self.exc is not None:
            raise self.exc
        return 77


def _one(conn, sender, pacer=None):
    return asyncio.run(send_one(conn, sender, pacer or SendPacer(), 1, chat_id=5, html="x", clock=lambda: T))


def test_every_send_outcome():
    c = _Conn()
    assert _one(c, _Sender()) == (SENT, 77, T) and c.calls[-1][:2] == ("SENDING", "SENT")
    c = _Conn()
    assert _one(c, _Sender(DeliveryRejected("Forbidden: bot was blocked")))[0] == FAILED
    assert c.calls[-1] == ("SENDING", "FAILED", "Forbidden: bot was blocked")
    c = _Conn()
    assert _one(c, _Sender(DeliveryAmbiguous("TimedOut")))[0] == UNKNOWN and c.calls[-1][1] == "DELIVERY_UNKNOWN"
    # flood control: back to PENDING, never FAILED, and the run stops sending
    c, p = _Conn(), SendPacer()
    assert _one(c, _Sender(DeliveryThrottled(7)), p)[0] == THROTTLED
    assert c.calls[-1] == ("SENDING", "PENDING", "RetryAfter 7s") and p.closed == "THROTTLED"
    s = _Sender()
    assert _one(_Conn(), s, p)[0] == DEFERRED and s.n == 0 and p.deferred == 1     # untouched, not sent
    s = _Sender()
    assert _one(_Conn(transition_ok=False), s)[0] == RACED and s.n == 0            # another run took the row


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


def test_the_send_budget_leaves_room_before_the_unit_timeout():
    base = BetaConfig.load()
    assert base["notifications"]["send_interval_ms"] == 50 and base["notifications"]["send_budget_s"] == 35
    with pytest.raises(BetaConfigError, match="send_budget_s"):
        base.with_overrides(notifications={**dict(base["notifications"]), "send_budget_s": 41})


def test_the_budget_bound_matches_the_notifier_unit():
    import re
    from pathlib import Path

    from beta.config import NOTIFY_UNIT_TIMEOUT_S
    unit = (Path(__file__).resolve().parents[2] / "deploy" / "signalbot-beta-notify.service").read_text()
    assert int(re.search(r"^TimeoutStartSec=(\d+)$", unit, re.M).group(1)) == NOTIFY_UNIT_TIMEOUT_S
