"""Pulsy UX V2, P0 owner tools: `/admin_export_views [n]` (market data only, scrubbed, capped, read-only),
`/admin_preview v2 <screen>` (live data, owner only, level buttons resolve only for the owner while the flag is on,
nothing written) and the gallery (`tools/ux_gallery/build.py`)."""
import json
from datetime import timedelta

import pytest

from beta_fakes import ON_PUSH, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_preview_pg import OWNER, _cfg
from test_beta_v2_pg import A, CFG, DAY, NOW, Sender, _join, _rows, _seed, plain

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_keys(v)


def _owner(text, k):
    return {"update_id": k, "message": {"from": {"id": OWNER}, "chat": {"id": OWNER, "type": "private"}, "text": text}}


def _cb(uid, data, k):
    return {"update_id": k, "callback_query": {"id": f"c{k}", "from": {"id": uid}, "data": data,
                                                "message": {"chat": {"id": uid}, "message_id": 77}}}


async def _world(flag=True):
    from beta.decision import reset_cache
    from beta.delivery import run_notify_once
    from beta.history_stats import run_history_build
    from runtime.beta_bot import BetaBotHandler
    reset_cache()
    pool = await fresh_pool()
    store = BetaStore(pool)
    await _seed(pool)
    assert (await run_history_build(store, CFG, now=DAY + timedelta(hours=2)))["status"] == "OK"
    cfg = _cfg(True).with_overrides(access={**dict(_cfg(True)["access"]), "ux_v2_preview": flag})
    h = BetaBotHandler(store, cfg, switches=lambda: ON_PUSH, owner_user_id=OWNER, clock=Clock(NOW))
    async with store.connect() as conn:
        await conn.allowlist_add(A)
    msg = await _join(h, A, 10)
    await h.handle(msg("/btc", 15))
    await run_notify_once(store, cfg, ON_PUSH, sender=Sender(), clock=Clock(NOW), owner_user_id=OWNER)
    return pool, h, msg


async def _counts(pool):
    tables = [r["t"] for r in await _rows(pool, """SELECT tablename AS t FROM pg_tables WHERE schemaname = 'public'
                                                  AND tablename LIKE 'beta%' AND tablename <> 'beta_admin_audit'""")]
    return {t: (await _rows(pool, f"SELECT count(*) AS n FROM {t}"))[0]["n"] for t in tables}


def test_export_views_is_market_data_only_capped_and_read_only():
    async def body():
        from beta.ux_export import DENYLIST, MAX_N
        pool, h, msg = await _world()
        before = await _counts(pool)
        out = await h.handle(_owner("/admin_export_views 5", 50))
        docs = [o for o in out if o.kind == "document"]
        assert len(docs) == 1 and docs[0].chat_id == OWNER and docs[0].document[0].endswith(".json")
        doc = json.loads(docs[0].document[1].decode("utf-8"))
        assert doc["version"] == "PULSY_UX_EXPORT_V1" and doc["provenance"] == "REAL"
        assert doc["views"] and doc["alerts"] and len(doc["views"]) <= 5
        keys = set(_walk_keys(doc))
        assert not keys & DENYLIST and not any(k.endswith("fingerprint") for k in keys)
        raw = docs[0].document[1].decode("utf-8")
        assert str(A) not in raw and str(OWNER) not in raw                   # no Telegram id anywhere
        assert await _counts(pool) == before                                 # read-only
        out = await h.handle(_owner(f"/admin_export_views {MAX_N + 1}", 51))
        assert not [o for o in out if o.kind == "document"] and "usage" in plain(out[0].html)
        out = await h.handle(msg("/admin_export_views", 52))                 # anyone else: unknown command
        assert not [o for o in out if o.kind == "document"]
        audit = await _rows(pool, "SELECT result FROM beta_admin_audit WHERE action = 'admin_export_views' "
                                  "ORDER BY audit_id")
        assert [a["result"] for a in audit] == ["OK", "INVALID_ARGUMENT", "REFUSED"]
        await pool.close()
    run(body())


def test_preview_v2_renders_live_data_to_the_owner_only_and_writes_nothing():
    async def body():
        pool, h, msg = await _world()
        before = await _counts(pool)
        out = await h.handle(_owner("/admin_preview v2 btc", 60))
        assert len(out) == 1 and out[0].chat_id == OWNER and "ПРЕВЬЮ V2" in plain(out[0].html)
        datas = [d for row in out[0].buttons for _l, d in row]
        assert "ux:btc:2" in datas and all(d.startswith("ux:") for d in datas)   # track A's callbacks, unchanged
        nav = await h.handle(_cb(OWNER, "ux:btc:2", 61))
        assert [o.kind for o in nav] == ["answer", "edit"] and "ПРЕВЬЮ V2" in plain(nav[1].html)
        assert plain(nav[1].html) != plain(out[0].html)
        stranger = await h.handle(_cb(A, "ux:btc:2", 62))                    # a participant's tap: nothing
        assert not [o for o in stranger if o.kind == "edit" or "ПРЕВЬЮ" in (o.html or "")]
        out = await h.handle(_owner("/admin_preview v2 hour", 63))           # no push decision yet
        assert "ещё не было" in plain(out[0].html)
        assert await _counts(pool) == before                                 # no view, display, activity, row
        await pool.close()
    run(body())


def test_preview_v2_is_refused_while_its_flag_is_off():
    async def body():
        pool, h, _msg = await _world(flag=False)
        out = await h.handle(_owner("/admin_preview v2 btc", 60))
        assert "ux_v2_preview is off" in plain(out[0].html) and not out[0].buttons
        assert [o.kind for o in await h.handle(_cb(OWNER, "ux:btc:2", 61))] == ["answer"]
        await pool.close()
    run(body())


def test_gallery_is_one_self_contained_page_of_real_and_synthetic_states():
    from tools.ux_gallery.build import build, real_states, synthetic_states
    doc = {"views": [{"kind": "btc", "requested_at": "2026-10-09T10:00:00+00:00", "payload": {"x": 1}}],
           "alerts": [{"kind": "level", "decision_ts": "2026-10-09T10:05:00+00:00",
                       "payload": {"at": "2026-10-09T10:05:00+00:00", "price": 62000.0, "level": 62010.0,
                                   "level_kind": "PDH", "member": {"kind": "PDH"}}}],
           "pushes": []}
    states = real_states(doc) + synthetic_states()
    page = build(states)
    assert page.startswith("<!doctype html>") and "<script src" not in page and "<link" not in page
    assert "R01 · REAL · view btc · 2026-10-09T10:00:00+00:00" in page and "R02 · REAL · alert level" in page
    assert page.count("<section class='state'") == 20 and "render failed" not in page
    assert "<ul class='toc'>" in page and "href='#S07-btc-L2-ru'" in page          # contents: state × screen
    assert "id='S07-btc-L2-ru'" in page and "id='S07-btc-L2-ru-wide'" in page      # stable ids, both widths
    for screen in ("btc", "levels", "level_card", "hour", "level", "move", "brief"):  # coverage
        assert f"-{screen}-L1-ru'" in page, screen
    assert ">RU · narrow<" in page and ">EN · wide<" in page and "col narrow" in page and "col wide" in page
    assert "onclick=\"show(" in page


def test_the_18_named_states_have_levels_and_visibly_different_l1():
    import re
    from beta.ux import render
    from tools.ux_gallery.states import named_states
    states = named_states()
    assert [sid for sid, _n, _s in states] == [f"S{i:02d}" for i in range(1, 19)]
    l1 = set()
    for sid, name, screens in states:
        if name != "stale data":                                              # stale: no levels by design
            assert screens["btc"]["levels"]["above"] and screens["btc"]["levels"]["below"], sid
            assert "level_card" in screens, sid
        html_text, buttons = render("btc", 1, "ru", screens["btc"])
        assert all(d.startswith("ux:") for row in buttons for _l, d in row)
        lines = re.sub(r"<[^>]+>", "", html_text).split("\n")[2:]       # the body: no header, no as-of line
        l1.add(re.sub(r"[0-9][0-9 \u202f\u00a0.,:%+−-]*", "#", "\n".join(lines)))   # numbers stripped
    assert len(l1) >= 15


def test_the_preview_uses_track_as_renderer_and_no_stub():
    """Production code never stubs the V2 render: without `beta.ux` the preview does not import."""
    import beta.ux
    import beta.ux_preview as V2
    assert V2.render is beta.ux.render and V2.from_view is beta.ux.from_view
    assert not hasattr(V2, "stub_render") and V2.SCREENS is beta.ux.SCREENS
