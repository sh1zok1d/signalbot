"""Role A: context isolation, strict actions, journal isolation, attention (§4–§9, §20.1/3/8/9)."""
import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from beta.i18n import _CATALOG
from sim_helpers import ScriptedUser, run
from tools.beta_user_sim.attention import AttentionConfig, AttentionSchedule
from tools.beta_user_sim.llm import FakeUserModel
from tools.beta_user_sim.prompts import ROLE_A_SYSTEM
from tools.beta_user_sim.role_a import (SIM_COMMANDS, UNSUPPORTED_SYNTHETIC_OPINION, RoleAUser, classify_journal,
                                        real_commands)
from tools.beta_user_sim.surface import (BUSY, SLEEPING, LeakError, UserTurn, VisibleButton, VisibleMessage,
                                         assert_role_a_safe)

TURN_KEYS = {"now", "new_messages", "notices", "popups"}
MSG_KEYS = {"message_id", "received_at", "arrived_while", "text", "buttons", "edit_of"}


def _turns(user):
    return [json.loads(p[-1]["content"]) for p in user.prompts]


# ---- context isolation ------------------------------------------------------------------------
def test_role_a_receives_only_the_visible_dto():
    user = ScriptedUser(lambda t: {"action": "SEND_COMMAND", "command": "/btc"} if t["new_messages"]
                        else {"action": "NO_ACTION"})
    run(user)
    turns = _turns(user)
    assert turns
    for turn in turns:
        assert set(turn) == TURN_KEYS
        for m in turn["new_messages"]:
            assert set(m) == MSG_KEYS
            assert m["arrived_while"] in ("AVAILABLE", "BUSY", "SLEEPING")
            for b in m["buttons"]:
                assert set(b) == {"button_id", "label"}
                assert b["button_id"].startswith(m["message_id"] + ".b")
    blob = json.dumps(user.prompts[-1], ensure_ascii=False)       # the persistent conversation holds every turn
    assert not re.search(r"\b[oe]:\d+:|\b[dun]:EV-|\bpick:|\bjoin:", blob)
    for leak in ("view_pk", "episode_pk", "payload", "digest", "outcome", "max_up",
                 "realized_range", "claim", "baseline", "SYNTHETIC", "DESCRIPTIVE_MONITORING", "rules_version",
                 "rules_digest", "/workspace", ".py", "RESEARCH", "MARKET-0", "Option A", "preferred"):
        assert leak not in blob, leak


def test_role_a_conversation_never_contains_role_b_output_or_outcomes():
    user = ScriptedUser(lambda t: {"action": "NO_ACTION"})
    e, r = run(user)
    assert r["role_b"]["audits"]
    blob = json.dumps(user.prompts[-1], ensure_ascii=False)
    for a in r["role_b"]["audits"]:
        for note in a["notes"].values():
            if note:
                assert note not in blob
    assert ROLE_A_SYSTEM.count("You are a user, not a QA engineer.") == 1


def test_leak_guard_blocks_internal_material_and_passes_every_user_visible_string():
    for bad in ({"text": "see docs/BETA_V0_3_MARKET_BRIEFING.md"}, {"text": "view_pk=4"},
                {"text": "o:12:1h"}, {"text": "a" * 40}, {"text": "f" * 64}, {"text": "RESEARCH_LEDGER"},
                {"x": "max_up_pct"}, {"text": "/workspace/beta/x"}, {"text": "MARKET-06"}):
        with pytest.raises(LeakError):
            assert_role_a_safe(bad)
    for key, by_lang in _CATALOG.items():
        for lang, text in by_lang.items():
            assert_role_a_safe({"text": text})


def test_persona_prompt_has_the_required_wording():
    assert "You are a user, not a QA engineer. Do not try to exercise every feature. If a\nmessage does not " \
           "deserve your attention, ignore it." in ROLE_A_SYSTEM
    assert "Do not flatter the product. Do not guess what the developers intended." in ROLE_A_SYSTEM
    for word in ("Signalbot", "detector", "percentile", "research", "rules_version"):
        assert word not in ROLE_A_SYSTEM


# ---- actions ---------------------------------------------------------------------------------
def _user(raw):
    class M:
        model_id = "m"

        def settings(self):
            return {}

        def complete(self, messages, *, role):
            return raw
    return RoleAUser(M())


_TURN = UserTurn(now="2024-03-04 12:00 Kyiv", new_messages=(VisibleMessage(
    "m3", "2024-03-04 12:00 Kyiv", "AVAILABLE", "BTC 64 000", (VisibleButton("m3.b1", "1h"),)),))
_VISIBLE = {"m3": ("m3.b1",)}


@pytest.mark.parametrize("raw,reason", [
    ('{"action": "SEND_COMMAND", "command": "/admin_status"}', "COMMAND_NOT_ALLOWED"),
    ('{"action": "SEND_COMMAND", "command": "/delete_me"}', "COMMAND_NOT_ALLOWED"),
    ('{"action": "SEND_COMMAND", "command": "/lang"}', "COMMAND_NOT_ALLOWED"),
    ('{"action": "SEND_COMMAND", "command": "/catchup"}', "COMMAND_NOT_ALLOWED"),
    ('{"action": "SEND_COMMAND", "command": "/btc now"}', "ARGS_NOT_ALLOWED"),
    ('{"action": "SEND_COMMAND", "command": "btc"}', "NOT_A_COMMAND"),
    ('{"action": "SEND_COMMAND", "command": "/BTC;rm"}', "MALFORMED_COMMAND"),
    ('{"action": "CLICK_BUTTON", "message_id": "m3", "button_id": "m3.b9"}', "BUTTON_NOT_ON_MESSAGE"),
    ('{"action": "CLICK_BUTTON", "message_id": "m9", "button_id": "m9.b1"}', "MESSAGE_NOT_VISIBLE"),
    ('{"action": "CLICK_BUTTON", "message_id": "m3", "button_id": "o:4:1h"}', "BUTTON_NOT_ON_MESSAGE"),
    ('{"action": "CLICK_BUTTON", "message_id": "m3"}', "MISSING_BUTTON_REFERENCE"),
    ('{"action": "CALL_API", "url": "http://x"}', "UNKNOWN_ACTION"),
    ('{"action": "NO_ACTION", "tool": "shell"}', "UNKNOWN_FIELDS:tool"),
    ('{"action": "SEND_COMMAND", "command": "/btc", "callback_data": "d:EV-1"}', "UNKNOWN_FIELDS:callback_data"),
    ("not json", "NOT_JSON"),
    ("[1, 2]", "NOT_AN_OBJECT"),
])
def test_invalid_actions_are_rejected_and_become_no_action(raw, reason):
    d = _user(raw).decide(_TURN, _VISIBLE)
    assert not d.accepted and d.rejection == reason and d.action.kind == "NO_ACTION"


def test_valid_actions_are_accepted():
    d = _user('{"action": "CLICK_BUTTON", "message_id": "m3", "button_id": "m3.b1"}').decide(_TURN, _VISIBLE)
    assert d.accepted and d.action.button_id == "m3.b1"
    d = _user('{"action": "SEND_COMMAND", "command": "/feedback the 1h line is clear"}').decide(_TURN, _VISIBLE)
    assert d.accepted and d.action.command == "feedback" and d.action.args == "the 1h line is clear"


def test_command_allowlist_is_derived_from_the_real_handler():
    real = real_commands()
    assert {"start", "btc", "history", "terms", "help", "feedback", "stop", "lang", "delete_me"} <= real
    assert set(SIM_COMMANDS) <= real and "lang" not in SIM_COMMANDS and "delete_me" not in SIM_COMMANDS
    with pytest.raises(ValueError):
        RoleAUser(FakeUserModel(), allowed_commands=("btc", "analogues"))


def test_rejected_and_fabricated_actions_never_reach_the_handler():
    user = ScriptedUser(lambda t: {"action": "CLICK_BUTTON", "message_id": "m1", "button_id": "d:EV-0000000000"})
    e, r = run(user)
    turns = [t for t in r["transcript"] if t["event"] == "ROLE_A_TURN"]
    assert turns and all(not t["accepted"] for t in turns)
    assert not [t for t in r["transcript"] if t["event"] == "REPLY" and t["kind"] != "ONBOARDING"]
    assert e.store.votes == {} and e.store.details_opens == []


def test_accepted_click_runs_the_real_handler_with_the_hidden_callback():
    def decide(t):
        for m in t["new_messages"]:
            if m["text"].startswith("BTCUSDT perp"):
                return {"action": "CLICK_BUTTON", "message_id": m["message_id"],
                        "button_id": m["buttons"][2]["button_id"]}            # Noise vote
        return {"action": "NO_ACTION"}
    e, r = run(ScriptedUser(decide))
    clicks = [t for t in r["transcript"] if t["event"] == "ROLE_A_TURN" and t["action"] == "CLICK_BUTTON"]
    assert clicks and all(c["callback"].startswith("n:EV-") for c in clicks)
    assert set(e.store.votes.values()) == {"NOISE"}


# ---- journal -----------------------------------------------------------------------------------
def test_unsupported_synthetic_opinions_are_excluded():
    kept, excluded = classify_journal({
        "attention": "Ignored the second alert.",
        "missing_context": "I would pay for this every month.",
        "understood": "This would replace my CoinGlass tab.",
        "verdict": "Great product-market fit.",
        "repetition": "Same layout twice."})
    assert kept == {"attention": "Ignored the second alert.", "repetition": "Same layout twice."}
    assert excluded == {"missing_context": UNSUPPORTED_SYNTHETIC_OPINION, "understood": UNSUPPORTED_SYNTHETIC_OPINION,
                        "verdict": UNSUPPORTED_SYNTHETIC_OPINION}


def test_journal_is_never_fed_into_signalbot():
    marker = "JOURNALMARKER private note"

    def decide(t):
        if t["new_messages"]:
            return {"action": "SEND_COMMAND", "command": "/btc", "journal": {"attention": marker}}
        return {"action": "NO_ACTION", "journal": {"understood": marker}}
    e, r = run(ScriptedUser(decide))
    assert any(marker in json.dumps(d["journal"]) for d in r["role_a_decisions"])
    state = json.dumps({"users": e.store.users, "activity": e.store.activity, "fb": e.store.feedback_messages,
                        "votes": list(e.store.votes.values())}, default=str)
    assert marker not in state
    replies = [x for x in r["transcript"] if x["event"] in ("REPLY", "SERVED_PERSISTED_VIEW")]
    assert all(marker not in x["text"] for x in replies)
    for a in r["role_b"]["audits"]:
        assert marker not in json.dumps(a)


# ---- attention ---------------------------------------------------------------------------------
T0 = datetime(2024, 3, 4, tzinfo=timezone.utc)


def test_attention_schedule_is_deterministic_and_seeded():
    a = AttentionSchedule(AttentionConfig(seed=3), T0, T0 + timedelta(days=2)).as_list()
    b = AttentionSchedule(AttentionConfig(seed=3), T0, T0 + timedelta(days=2)).as_list()
    c = AttentionSchedule(AttentionConfig(seed=4), T0, T0 + timedelta(days=2)).as_list()
    assert a == b and a != c


def test_sleep_window_is_kyiv_local_time():
    s = AttentionSchedule(AttentionConfig(seed=1, p_busy=0.0), T0, T0 + timedelta(days=1))
    assert s.state_at(datetime(2024, 3, 4, 0, 0, tzinfo=timezone.utc)) == SLEEPING      # 02:00 Kyiv
    assert s.state_at(datetime(2024, 3, 4, 6, 0, tzinfo=timezone.utc)) == "AVAILABLE"   # 08:00 Kyiv
    busy = AttentionSchedule(AttentionConfig(seed=1, p_busy=1.0), T0, T0 + timedelta(days=1))
    assert busy.state_at(datetime(2024, 3, 4, 10, 0, tzinfo=timezone.utc)) == BUSY
    assert busy.available_starts() == []


def test_backlog_is_presented_later_in_original_order_with_original_times():
    e, r = run(ScriptedUser(lambda t: {"action": "NO_ACTION"}))
    shown = {s["message_id"]: s for s in r["shown"]}
    backlog_turns = [t for t in r["transcript"] if t["event"] == "ROLE_A_TURN" and t["backlog"]]
    assert backlog_turns
    pushes_in_backlog = [m for t in backlog_turns for m in t["backlog"] if shown[m]["kind"] == "PUSH"]
    assert pushes_in_backlog
    for t in backlog_turns:
        ats = [shown[m]["at"] for m in t["shown"]]
        assert ats == sorted(ats)
        for m in t["backlog"]:
            assert shown[m]["arrived_while"] in (BUSY, SLEEPING)
            assert shown[m]["at"] <= t["t"]
    turns_at = [t["t"] for t in r["transcript"] if t["event"] == "ROLE_A_TURN"]
    for push in [s for s in r["shown"] if s["kind"] == "PUSH" and s["arrived_while"] != "AVAILABLE"]:
        assert not [x for x in turns_at if x == push["at"]]   # no turn while busy/asleep


def test_role_a_turns_happen_only_while_available():
    e, r = run(FakeUserModel())
    for t in r["transcript"]:
        if t["event"] == "ROLE_A_TURN":
            assert e.schedule.state_at(datetime.fromisoformat(t["t"])) == "AVAILABLE"
