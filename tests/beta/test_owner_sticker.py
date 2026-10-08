"""Owner sticker replies, the delivery path without PostgreSQL: a sticker goes out through sendSticker on the
same sender, an owner copy is mapped by the message_id the send returned, and a failed mapping write never
breaks the delivery."""
import asyncio

from runtime.beta_bot import Outgoing, deliver_outgoing


class Sender:
    def __init__(self, mid=42):
        self.calls, self.mid = [], mid

    async def send(self, *, chat_id, html, buttons=None):
        self.calls.append(("send", chat_id))
        return self.mid

    async def send_sticker(self, *, chat_id, sticker):
        self.calls.append(("sticker", chat_id, sticker))
        return 1


class Store:
    def __init__(self, fail=False):
        self.rows, self.fail = [], fail

    def connect(self):
        store = self

        class Conn:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def insert_owner_forward(self, **kw):
                if store.fail:
                    raise RuntimeError("db down")
                store.rows.append(kw)
        return Conn()


def test_sticker_goes_through_send_sticker_and_is_counted():
    s = Sender()
    mass = ("admin_sticker", "Sticker to u_x")
    counts = asyncio.run(deliver_outgoing(s, [Outgoing(kind="mass_open", mass=mass),
                                             Outgoing(kind="sticker", chat_id=5, sticker="F", mass=mass)]))
    assert s.calls == [("sticker", 5, "F")]
    assert counts[mass] == {"recipients": 1, "delivered": 1, "failed": 0, "unknown": 0}


def test_an_owner_copy_is_mapped_by_the_returned_message_id_only():
    st = Store()
    out = [Outgoing(kind="message", chat_id=1, html="thanks"),
           Outgoing(kind="message", chat_id=9, html="copy", forward_of=(7, "idea"))]
    asyncio.run(deliver_outgoing(Sender(mid=777), out, store=st))
    assert [(r["owner_message_id"], r["user_pk"], r["kind"]) for r in st.rows] == [(777, 7, "idea")]
    asyncio.run(deliver_outgoing(Sender(mid=None), out, store=st))     # no id returned: nothing inferred
    asyncio.run(deliver_outgoing(Sender(mid=778), out))                 # no store: nothing written
    assert len(st.rows) == 1


def test_a_failed_mapping_write_never_breaks_delivery():
    s = Sender(mid=780)
    out = [Outgoing(kind="message", chat_id=9, html="copy", forward_of=(7, "feedback")),
           Outgoing(kind="message", chat_id=1, html="next")]
    asyncio.run(deliver_outgoing(s, out, store=Store(fail=True)))
    assert s.calls == [("send", 9), ("send", 1)]
