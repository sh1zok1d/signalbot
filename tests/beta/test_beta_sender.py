"""BetaTelegramSender maps outcomes to at-most-once delivery semantics (fake bot; no network)."""
import pytest

from beta_fakes import run
from beta.delivery import DeliveryAmbiguous, DeliveryRejected
from runtime.beta_bot import BetaTelegramSender

TOKEN = "123456:SECRET-TOKEN"


class FakeBot:
    def __init__(self, exc=None):
        self.exc, self.calls = exc, []

    async def send_message(self, **kw):
        self.calls.append(kw)
        if self.exc:
            raise self.exc

        class M:
            message_id = 77
        return M()


def _sender(exc=None):
    s = BetaTelegramSender(TOKEN)
    s._bot = FakeBot(exc)
    return s


def test_success_returns_message_id_with_buttons():
    s = _sender()
    assert run(s.send(chat_id=5, html="<b>x</b>", buttons=[[("Details", "d:EV-1")]])) == 77
    kw = s._bot.calls[0]
    assert kw["parse_mode"] == "HTML" and kw["reply_markup"].inline_keyboard[0][0].callback_data == "d:EV-1"


def test_timeout_and_network_errors_are_ambiguous():
    from telegram.error import NetworkError, TimedOut
    for exc in (TimedOut(), NetworkError("reset")):
        with pytest.raises(DeliveryAmbiguous):
            run(_sender(exc).send(chat_id=5, html="x"))


def test_explicit_rejection_is_sanitized():
    from telegram.error import BadRequest, Forbidden
    for exc in (Forbidden(f"blocked {TOKEN} chat 5"), BadRequest("chat not found")):
        with pytest.raises(DeliveryRejected) as ei:
            run(_sender(exc).send(chat_id=5, html="x"))
        assert TOKEN not in str(ei.value)
