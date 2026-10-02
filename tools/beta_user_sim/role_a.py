"""Role A: one persistent conversation, a strict action contract and a private journal."""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

from .llm import ROLE_USER, ChatModel
from .prompts import ROLE_A_SYSTEM
from .surface import UserTurn, assert_role_a_safe

NO_ACTION, SEND_COMMAND, CLICK_BUTTON = "NO_ACTION", "SEND_COMMAND", "CLICK_BUTTON"
ACTIONS = (NO_ACTION, SEND_COMMAND, CLICK_BUTTON)

# Real commands Role A may send. /lang is excluded (persisted /btc views keep the
# language they were rendered in), /delete_me is excluded (it erases the sandbox
# identity mid-run), admin_* are owner-only.
SIM_COMMANDS = ("btc", "history", "terms", "help", "feedback", "stop", "start")
COMMANDS_WITH_ARGS = ("feedback",)

JOURNAL_TOPICS = ("understood", "not_understood", "attention", "ignored_because", "repetition",
                  "notification_fatigue", "temporal_inconsistency", "ambiguous", "wording_vs_evidence",
                  "missing_context", "needed_other_screen")
UNSUPPORTED_SYNTHETIC_OPINION = "UNSUPPORTED_SYNTHETIC_OPINION"
_UNSUPPORTED = re.compile(
    r"(product[- ]market|\bpmf\b|willing(ness)? to pay|\bpay(ing)? for\b|subscription|\bprice tier|"
    r"would (keep|stop) using|retention|\bchurn\b|replace (my|another|coinglass)|would miss|"
    r"worth (the )?money|\bbuy (it|this)\b|заплатил|подписк|платить)", re.IGNORECASE)


def real_commands() -> frozenset:
    """Commands the production handler dispatches, read from its source (`cmd == "..."`)."""
    import runtime.beta_bot as bot
    tree = ast.parse(Path(bot.__file__).read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "cmd":
            for c in node.comparators:
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    found.add(c.value)
    return frozenset(found)


@dataclass(frozen=True)
class Action:
    kind: str
    command: Optional[str] = None
    args: str = ""
    message_id: Optional[str] = None
    button_id: Optional[str] = None


@dataclass(frozen=True)
class Decision:
    action: Action
    accepted: bool
    rejection: Optional[str]
    journal: Mapping[str, str]
    excluded_journal: Mapping[str, str]
    raw: str


def classify_journal(raw: Mapping) -> tuple:
    kept, excluded = {}, {}
    for k, v in (raw or {}).items():
        text = str(v)
        if _UNSUPPORTED.search(text) or _UNSUPPORTED.search(str(k)):
            excluded[str(k)] = UNSUPPORTED_SYNTHETIC_OPINION
        elif k not in JOURNAL_TOPICS:
            excluded[str(k)] = "UNKNOWN_TOPIC"
        else:
            kept[k] = text
    return kept, excluded


def parse_command(text: str, allowed: Sequence[str]) -> tuple:
    """('btc', '') for an allowed command; raises ValueError otherwise."""
    if not isinstance(text, str) or not text.startswith("/"):
        raise ValueError("NOT_A_COMMAND")
    head, _, rest = text.strip().partition(" ")
    name = head[1:]
    if not re.fullmatch(r"[a-z_]+", name or ""):
        raise ValueError("MALFORMED_COMMAND")
    if name not in allowed:
        raise ValueError("COMMAND_NOT_ALLOWED")
    rest = rest.strip()
    if rest and name not in COMMANDS_WITH_ARGS:
        raise ValueError("ARGS_NOT_ALLOWED")
    return name, rest


class RoleAUser:
    """Persistent Role A conversation. It holds only Role A's own turns and replies."""

    def __init__(self, model: ChatModel, *, allowed_commands: Optional[Sequence[str]] = None):
        real = real_commands()
        allowed = tuple(c for c in (allowed_commands or SIM_COMMANDS) if c in real)
        if set(allowed_commands or SIM_COMMANDS) - set(allowed):
            raise ValueError("Role A allowlist contains a command the production handler does not dispatch")
        self.model = model
        self.allowed = allowed
        self.messages: list = [{"role": "system", "content": ROLE_A_SYSTEM}]
        self.decisions: list = []

    def decide(self, turn: UserTurn, visible_buttons: Mapping[str, Sequence[str]]) -> Decision:
        """`visible_buttons`: message_id -> button ids currently clickable."""
        content = turn.to_json()
        assert_role_a_safe(json.loads(content))
        self.messages.append({"role": "user", "content": content})
        raw = self.model.complete(list(self.messages), role=ROLE_USER)
        self.messages.append({"role": "assistant", "content": raw})
        decision = self._validate(raw, visible_buttons)
        self.decisions.append(decision)
        return decision

    def _validate(self, raw: str, visible: Mapping[str, Sequence[str]]) -> Decision:
        def reject(reason: str, journal=None) -> Decision:
            kept, excluded = classify_journal(journal or {})
            return Decision(Action(NO_ACTION), False, reason, kept, excluded, raw)
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return reject("NOT_JSON")
        if not isinstance(data, dict):
            return reject("NOT_AN_OBJECT")
        journal = data.get("journal") if isinstance(data.get("journal"), dict) else {}
        kind = data.get("action")
        extra = set(data) - {"action", "command", "message_id", "button_id", "journal"}
        if kind not in ACTIONS:
            return reject("UNKNOWN_ACTION", journal)
        if extra:
            return reject("UNKNOWN_FIELDS:" + ",".join(sorted(extra)), journal)
        kept, excluded = classify_journal(journal)
        if kind == NO_ACTION:
            return Decision(Action(NO_ACTION), True, None, kept, excluded, raw)
        if kind == SEND_COMMAND:
            try:
                name, args = parse_command(data.get("command"), self.allowed)
            except ValueError as exc:
                return reject(str(exc), journal)
            return Decision(Action(SEND_COMMAND, command=name, args=args), True, None, kept, excluded, raw)
        mid, bid = data.get("message_id"), data.get("button_id")
        if not isinstance(mid, str) or not isinstance(bid, str):
            return reject("MISSING_BUTTON_REFERENCE", journal)
        if mid not in visible:
            return reject("MESSAGE_NOT_VISIBLE", journal)
        if bid not in visible[mid]:
            return reject("BUTTON_NOT_ON_MESSAGE", journal)
        return Decision(Action(CLICK_BUTTON, message_id=mid, button_id=bid), True, None, kept, excluded, raw)
