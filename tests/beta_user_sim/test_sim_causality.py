"""Causal replay: nothing later than the clock is visible to Role A, outcomes unlock at T+h (§3, §20.2)."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from beta.formatter import format_details
from beta.formatter import format_push_v02 as format_push
from beta.outcomes import LAST_BAR_GRACE
from sim_helpers import CFG, ScriptedUser, bundle, raw_bundle, run
from tools.beta_user_sim.bundle import BundleError, bundle_from_dict
from tools.beta_user_sim.outcomes import NOT_AVAILABLE, NotMatured, OutcomeLedger
from tools.beta_user_sim.sandbox import (SandboxStore, Unreplayable, callback_update, message_update,
                                        sandbox_handler)
from tools.beta_user_sim.timeline import KIND_PUSH, build_timeline, push_episode_at_trigger


def _dt(s):
    return datetime.fromisoformat(s)


def test_every_turn_sees_only_messages_that_already_arrived():
    e, r = run()
    shown = {s["message_id"]: s for s in r["shown"]}
    last = None
    for t in r["transcript"]:
        if t["event"] != "ROLE_A_TURN":
            continue
        now = _dt(t["t"])
        assert last is None or now >= last
        last = now
        for m in t["shown"]:
            assert _dt(shown[m]["at"]) <= now


def test_pushes_arrive_at_first_sent_time_and_never_before_the_trigger():
    b = bundle()
    tl = build_timeline(b, CFG, lang="ru")
    assert tl.pushes
    for p in tl.pushes:
        ep = b.episode(p.source["episode_pk"])
        sent = [d["finished_at"] for d in b.deliveries if d["episode_pk"] == ep["episode_pk"] and d["state"] == "SENT"]
        assert p.at == min(sent) and p.at >= ep["triggered_at"]
    suppressed = {d["episode_pk"] for d in b.push_decisions if d["decision"] != "PUSH"}
    assert suppressed and not {p.source["episode_pk"] for p in tl.pushes} & suppressed


def test_push_text_uses_only_set_once_trigger_fields():
    b = bundle()
    for row in b.episodes:
        if row["triggered_at"] is None:
            continue
        ep = push_episode_at_trigger(row)
        base = format_push(ep, lang="ru")
        from dataclasses import replace
        for variant in (replace(ep, state="ENDED", terminal_at=row["triggered_at"] + timedelta(hours=1),
                                terminal_reason="CONDITION_FAILED", last_streak=9,
                                last_bucket=row["opened_bucket"] + timedelta(hours=2)),
                        replace(ep, armed_at=row["opened_at"], reference_dispersion_pct=0.5)):
            assert format_push(variant, lang="ru") == base


def test_details_template_ignores_the_placeholder_lifecycle_fields():
    b = bundle()
    store = SandboxStore(b, CFG, start=datetime(2024, 3, 5, tzinfo=timezone.utc))
    from dataclasses import replace
    for row in b.episodes:
        ep = store.episode_as_of(row)
        tr, oc = store.transitions_as_of(row["episode_pk"]), store.outcomes_as_of(row["episode_pk"])
        base = format_details(ep, tr, oc, "ru")
        assert format_details(replace(ep, last_streak=7, last_bucket=ep.opened_bucket + timedelta(hours=3)),
                              tr, oc, "ru") == base


def test_btc_is_served_only_from_a_persisted_view_at_or_after_the_request():
    e, r = run(ScriptedUser(lambda t: {"action": "SEND_COMMAND", "command": "/btc"} if not t["new_messages"]
                            else {"action": "NO_ACTION"}))
    served = [x for x in r["transcript"] if x["event"] == "SERVED_PERSISTED_VIEW"]
    assert served
    for s in served:
        assert 0 <= s["wait_s"] <= 600
        assert s["template_check"] == "TEMPLATE_MATCH"
    assert len({s["item_id"] for s in served}) == len(served)           # a persisted view is shown once


def _btc_after_push(t):
    if any(m["text"].startswith("BTCUSDT perp") for m in t["new_messages"]):
        return {"action": "SEND_COMMAND", "command": "/btc"}
    return {"action": "NO_ACTION"}


def test_btc_without_a_persisted_view_in_the_wait_window_is_unreplayable_and_neutral():
    e, r = run(ScriptedUser(_btc_after_push), btc_max_wait_min=0)
    assert r["unreplayable"]
    assert {u["reason"] for u in r["unreplayable"]} == {"NO_PERSISTED_BTC_VIEW_IN_WAIT_WINDOW"}
    assert not [x for x in r["transcript"] if x["event"] == "SERVED_PERSISTED_VIEW"]
    notices = [t for t in r["transcript"] if t["event"] == "ROLE_A_TURN" and t["notices"]]
    assert notices and all(t["notices"] == ["Your last action produced no visible reply."] for t in notices)


def test_btc_after_a_push_moves_the_clock_to_the_persisted_view_and_never_back():
    e, r = run(ScriptedUser(_btc_after_push))
    served = [x for x in r["transcript"] if x["event"] == "SERVED_PERSISTED_VIEW"]
    assert served and any(s["wait_s"] > 0 for s in served)
    ts = [_dt(x["t"]) for x in r["transcript"] if x["event"] != "PUSH_ARRIVED"]
    assert ts == sorted(ts)


def _store_and_handler(at):
    store = SandboxStore(bundle(), CFG, start=at)
    return store, sandbox_handler(store, CFG)


async def _join(store, h):
    await h.handle(message_update(1, "/start"))
    await h.handle(callback_update(2, "pick:ru", 1))
    await h.handle(callback_update(3, "join:ru", 2))


def test_live_btc_and_readiness_paths_fail_closed_in_the_sandbox():
    store, h = _store_and_handler(datetime(2024, 3, 4, 10, tzinfo=timezone.utc))

    async def go():
        await _join(store, h)
        with pytest.raises(Unreplayable):
            await h.handle(message_update(4, "/btc"))
        out = await h.handle(callback_update(5, "r:latest", 3))       # owner-only: never reaches live state
        assert [o.kind for o in out] == ["answer"]
    asyncio.run(go())
    assert store.activity[-1]["action"] == "cmd_start"   # the failed transactions rolled back


def test_tabs_open_only_views_the_participant_was_shown():
    b = bundle()
    v = b.btc_views[0]
    store, h = _store_and_handler(v["requested_at"] + timedelta(minutes=1))

    async def go():
        await _join(store, h)
        out = await h.handle(callback_update(4, f"o:{v['view_pk']}:1h", 3))
        assert [o.html for o in out if o.kind == "answer"] == ["Недоступно"] or len(out) == 1
        store.expose_view(v)
        out = await h.handle(callback_update(5, f"o:{v['view_pk']}:1h", 3))
        assert any(o.kind == "message" and "ПОСЛЕДНИЙ ЧАС" in o.html for o in out)
    asyncio.run(go())


def test_as_of_episode_history_and_details_hide_later_state():
    b = bundle()
    first = min((e for e in b.episodes if e["triggered_at"]), key=lambda e: e["triggered_at"])
    at = first["triggered_at"] + timedelta(seconds=5)
    store = SandboxStore(b, CFG, start=at)
    ep = store.episode_as_of(first)
    assert ep.state == "TRIGGERED" and ep.terminal_at is None and first["state"] == "ENDED"
    assert store.outcomes_as_of(first["episode_pk"]) == []
    hist = store.history_as_of(10)
    assert [r["public_id"] for r in hist] == [first["public_id"]]
    assert hist[0]["decision"] is None and hist[0]["delivery_states"] is None
    store.clock = first["triggered_at"] + timedelta(minutes=20)
    assert [o["horizon"] for o in store.outcomes_as_of(first["episode_pk"])] == ["15m"]
    assert store.history_as_of(10)[0]["delivery_states"] == ["SENT"]


def test_correction_flag_makes_the_episode_unreplayable():
    raw = raw_bundle()
    raw["episodes"][0]["correction_flag"] = True
    store = SandboxStore(bundle_from_dict(raw), CFG, start=datetime(2024, 3, 5, tzinfo=timezone.utc))
    with pytest.raises(Unreplayable):
        store.episode_as_of(store.bundle.episodes[0])


def test_history_outside_the_exported_episode_window_is_unreplayable():
    raw = raw_bundle()
    raw["episodes_since"] = "2024-03-04T00:00:00+00:00"
    store = SandboxStore(bundle_from_dict(raw), CFG, start=datetime(2024, 3, 4, 12, tzinfo=timezone.utc))
    with pytest.raises(Unreplayable):
        store.history_as_of(10)


def test_unknown_store_methods_are_unreplayable_not_answered():
    store, _h = _store_and_handler(datetime(2024, 3, 4, tzinfo=timezone.utc))

    async def go():
        async with store.connect() as c:
            for name in ("fetch_latest_live_tape", "fetch_latest_context_state", "insert_btc_view",
                         "active_user_chats", "delete_participant", "redeem_invite"):
                with pytest.raises(Unreplayable):
                    getattr(c, name)
    asyncio.run(go())


# ---- outcomes -----------------------------------------------------------------------------------
def _push_item(b):
    return build_timeline(b, CFG, lang="ru").pushes[0]


def test_role_b_cannot_run_before_the_longest_horizon_matures():
    b = bundle()
    item = _push_item(b)
    led = OutcomeLedger(b, CFG)
    due = item.at + timedelta(hours=24) + LAST_BAR_GRACE
    assert led.audit_at(item) == due
    with pytest.raises(NotMatured):
        led.require_matured(item, due - timedelta(seconds=1))
    led.require_matured(item, due)


def test_episode_outcomes_unlock_only_when_written_and_use_the_configured_version():
    raw = raw_bundle()
    pk = raw["episodes"][0]["episode_pk"]
    rows = [o for o in raw["outcomes"] if o["episode_pk"] == pk and o["horizon"] == "1h"]
    later = dict(rows[0], revision=2, close_return_pct=9.99,
                 computed_at=(_dt(rows[0]["computed_at"]) + timedelta(hours=5)).isoformat())
    other = dict(rows[0], outcome_version="OTHER_VERSION", close_return_pct=-9.99)
    raw["outcomes"] += [later, other]
    b = bundle_from_dict(raw)
    item = _push_item(b)
    led = OutcomeLedger(b, CFG)
    trig = b.episode(pk)["triggered_at"]
    obs = {o.horizon: o for o in led.available(item, trig + timedelta(minutes=10))}
    assert all(o.status == NOT_AVAILABLE for o in obs.values())
    obs = {o.horizon: o for o in led.available(item, trig + timedelta(hours=1, minutes=4))}
    assert obs["1h"].fields["close_return_pct"] == rows[0]["close_return_pct"]
    assert obs["4h"].status == NOT_AVAILABLE
    obs = {o.horizon: o for o in led.available(item, trig + timedelta(hours=7))}
    assert obs["1h"].fields["close_return_pct"] == 9.99 and obs["1h"].note == "revision 2"


def test_view_outcomes_use_the_frozen_outcome_function_and_unlock_at_t_plus_h():
    b = bundle()
    tl = build_timeline(b, CFG, lang="ru")
    item = tl.views[0]
    payload = next(v["payload"] for v in b.btc_views if v["view_pk"] == item.source["view_pk"])
    anchor = _dt(payload["data_through"])
    led = OutcomeLedger(b, CFG)
    before = {o.horizon: o for o in led.available(item, anchor + timedelta(minutes=17, seconds=-1), payload=payload)}
    assert before["15m"].status == NOT_AVAILABLE
    early = {o.horizon: o for o in led.available(item, anchor + timedelta(minutes=17), payload=payload)}
    assert early["15m"].status == "COMPLETE" and early["30m"].status == NOT_AVAILABLE
    assert set(early["15m"].fields) == {"max_up_pct", "max_down_pct", "close_return_pct", "realized_range_pct",
                                        "time_to_max_up_s", "time_to_max_down_s"}
    from beta.outcomes import compute_outcome
    bars = [k for k in b.klines if anchor <= k["ts"] < anchor + timedelta(minutes=15)]
    want = compute_outcome(anchor=anchor, horizon="15m", reference_price=payload["now"]["reference_price"],
                           exchanges=list(CFG.exchanges), klines=bars)
    assert early["15m"].fields["realized_range_pct"] == want["realized_range_pct"]


def test_horizons_after_the_export_time_are_deferred_not_guessed():
    raw = raw_bundle()
    last_push = max(d["finished_at"] for d in raw["deliveries"])
    raw["exported_at"] = (_dt(last_push) + timedelta(hours=2)).isoformat()
    from sim_helpers import CFG as cfg, models
    from tools.beta_user_sim.replay import ReplayConfig, ReplayEngine
    r = ReplayEngine(bundle_from_dict(raw), cfg, models(), ReplayConfig()).run()
    assert r["role_b"]["deferred"]
    assert {d["reason"] for d in r["role_b"]["deferred"]} == {"HORIZON_NOT_MATURE_AT_BUNDLE_EXPORT"}


def test_bundle_rejects_personal_identifiers_and_naive_times():
    raw = raw_bundle()
    raw["deliveries"][0]["user_pk"] = 4
    with pytest.raises(BundleError):
        bundle_from_dict(raw)
    raw = raw_bundle()
    raw["btc_views"][0]["requested_at"] = "2024-03-04T10:00:00"
    with pytest.raises(BundleError):
        bundle_from_dict(raw)


def test_tampered_rendered_text_is_skipped_as_unreplayable():
    raw = raw_bundle()
    raw["btc_views"][0]["rendered_html"] += "x"
    tl = build_timeline(bundle_from_dict(raw), CFG, lang="ru")
    assert ("view:%d" % raw["btc_views"][0]["view_pk"], "RENDERED_DIGEST_MISMATCH") in \
        [(s.source_id, s.reason) for s in tl.skipped]


def test_replay_input_ids_are_ordered_and_recorded():
    e, r = run()
    ids = r["replay_input_ids"]
    items = {i.item_id: i for i in [*e.timeline.views, *e.timeline.pushes]}
    ats = [items[i].at for i in ids]
    assert ats == sorted(ats) and len(ids) == len(set(ids))
    assert any(i.startswith("push:") for i in ids) and any(i.startswith("view:") for i in ids)
    assert all(items[i].kind != KIND_PUSH or i.startswith("push:EV-") for i in ids)
