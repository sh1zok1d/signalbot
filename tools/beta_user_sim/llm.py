"""Model interface. CI and the default CLI use deterministic fakes; there is no network.

`OpenAIChatModel` exists only so a later, explicitly authorized smoke run does not
need new code. It refuses to construct unless `allow_network=True` is passed AND
SIGNALBOT_SIM_ALLOW_NETWORK=1 AND OPENAI_API_KEY are set. No test constructs it
with network allowed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Mapping, Optional, Protocol, Sequence

ROLE_USER, ROLE_AUDITOR, ROLE_JUDGE = "ROLE_A_USER", "ROLE_B_AUDITOR", "ROLE_B_JUDGE"


class ChatModel(Protocol):
    model_id: str

    def complete(self, messages: Sequence[Mapping[str, str]], *, role: str) -> str: ...

    def settings(self) -> dict: ...


def _h(*parts: str) -> int:
    return int(hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:8], 16)


def _last_user_json(messages: Sequence[Mapping[str, str]]) -> dict:
    for m in reversed(messages):
        if m["role"] == "user":
            return json.loads(m["content"])
    return {}


class FakeUserModel:
    """Deterministic stand-in for Role A. It reads only the conversation it is given."""

    model_id = "fake-user-v0"

    def settings(self) -> dict:
        return {"deterministic": True, "network": False}

    def complete(self, messages: Sequence[Mapping[str, str]], *, role: str) -> str:
        assert role == ROLE_USER
        turn = _last_user_json(messages)
        new = turn.get("new_messages") or []
        if turn.get("notices"):
            return json.dumps({"action": "NO_ACTION", "journal": {
                "attention": "Nothing came back after my last tap, so I left it."}})
        pushes = [m for m in new if m["text"].startswith("BTCUSDT perp")]
        screens = [m for m in new if m["text"].startswith("BTC ") and m["buttons"]]
        if len(pushes) >= 3:
            return json.dumps({"action": "NO_ACTION", "journal": {
                "attention": f"{len(pushes)} event messages piled up while I was away; I skimmed and ignored them.",
                "notification_fatigue": "Several alerts in a row, each with the same layout.",
                "repetition": "The alerts repeat the same template."}})
        if screens:
            m = screens[-1]
            pick = _h(m["message_id"], m["text"]) % 3
            if pick == 0:
                labels = [b for b in m["buttons"] if b["label"] in ("1ч", "1h")]
                if labels:
                    return json.dumps({"action": "CLICK_BUTTON", "message_id": m["message_id"],
                                       "button_id": labels[0]["button_id"], "journal": {
                                           "missing_context": "I wanted the last hour before deciding if this matters."}})
            return json.dumps({"action": "NO_ACTION", "journal": {
                "understood": "Screen read; nothing I need to act on.",
                "wording_vs_evidence": "The labels read as descriptions, not calls."}})
        if pushes and any(m["arrived_while"] != "AVAILABLE" for m in pushes):
            return json.dumps({"action": "SEND_COMMAND", "command": "/history", "journal": {
                "attention": "An alert came in while I was away; I checked what happened since."}})
        if pushes:
            p = pushes[-1]
            pick = _h(p["message_id"]) % 3
            if pick == 0:
                return json.dumps({"action": "SEND_COMMAND", "command": "/btc", "journal": {
                    "attention": "An event alert arrived; I checked the market screen.",
                    "needed_other_screen": "The alert alone does not show the hour context."}})
            if pick == 1 and p["buttons"]:
                return json.dumps({"action": "CLICK_BUTTON", "message_id": p["message_id"],
                                   "button_id": p["buttons"][0]["button_id"], "journal": {
                                       "missing_context": "I opened the first button to see what is behind the alert."}})
            return json.dumps({"action": "NO_ACTION", "journal": {
                "attention": "Alert seen. A 5-minute event is not enough for me to look closer.",
                "ambiguous": "The decision time and the composite price are clear; why it matters is not."}})
        if not new and _h(turn.get("now", "")) % 4 == 0:
            return json.dumps({"action": "SEND_COMMAND", "command": "/btc", "journal": {
                "attention": "Quick unprompted look at the market."}})
        return json.dumps({"action": "NO_ACTION"})


class FakeAuditorModel:
    """Deterministic stand-in for Role B subjective questions."""

    model_id = "fake-auditor-v0"
    _STRONG = re.compile(r"(экстрем|extreme|резк|sharp|стресс|stress|aggressive|агрессивн)", re.IGNORECASE)

    def settings(self) -> dict:
        return {"deterministic": True, "network": False}

    def complete(self, messages: Sequence[Mapping[str, str]], *, role: str) -> str:
        assert role == ROLE_AUDITOR
        data = _last_user_json(messages)
        text = data["original_message"]
        strong = bool(self._STRONG.search(text))
        return json.dumps({
            "wording_stronger_than_evidence": "UNCLEAR" if strong else "NO",
            "wording_note": ("Intensity words appear; the visible numbers are one 5m bucket." if strong
                             else "Plain descriptive wording."),
            "adds_explanatory_value_over_baseline": "YES" if len(text) > len(data["baseline_message"]) else "NO",
            "understandable_without_hidden_knowledge": "PARTLY" if "OI" in text else "YES",
            "retrospective_usefulness": "SOMEWHAT",
            "retrospective_note": "Describes the state at the time; makes no claim about what followed.",
        })


class FakeJudgeModel:
    """Deterministic blind judge. Sees only 'Option A' / 'Option B' text."""

    model_id = "fake-judge-v0"

    def settings(self) -> dict:
        return {"deterministic": True, "network": False}

    def complete(self, messages: Sequence[Mapping[str, str]], *, role: str) -> str:
        assert role == ROLE_JUDGE
        data = _last_user_json(messages)
        a, b = data["option_a"], data["option_b"]
        v = _h(a, b) % 5
        choice = "TIE" if v == 0 else ("A" if v in (1, 2, 3) else "B")
        return json.dumps({"preferred": choice, "reason": "Deterministic fake judge."})


class NetworkNotAuthorized(RuntimeError):
    pass


class OpenAIChatModel:
    """Chat Completions client (stdlib only). Never used in tests or by default."""

    def __init__(self, model_id: str, *, allow_network: bool = False, temperature: float = 0.0,
                 seed: Optional[int] = None, timeout_s: float = 60.0):
        if not allow_network or os.environ.get("SIGNALBOT_SIM_ALLOW_NETWORK") != "1":
            raise NetworkNotAuthorized("real model calls need --allow-network and SIGNALBOT_SIM_ALLOW_NETWORK=1")
        self._key = os.environ.get("OPENAI_API_KEY")
        if not self._key:
            raise NetworkNotAuthorized("OPENAI_API_KEY is not set")
        self.model_id, self.temperature, self.seed, self.timeout_s = model_id, temperature, seed, timeout_s

    def settings(self) -> dict:
        return {"temperature": self.temperature, "seed": self.seed, "response_format": "json_object",
                "network": True, "bit_identical_reproducibility": "NOT_GUARANTEED"}

    def complete(self, messages: Sequence[Mapping[str, str]], *, role: str) -> str:
        import urllib.request
        body = {"model": self.model_id, "messages": list(messages), "temperature": self.temperature,
                "response_format": {"type": "json_object"}}
        if self.seed is not None:
            body["seed"] = self.seed
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions",
                                     data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Authorization": f"Bearer {self._key}",
                                              "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310 - fixed https host
            out = json.loads(resp.read().decode("utf-8"))
        return out["choices"][0]["message"]["content"]


def build_models(kind: str, *, model_id: Optional[str] = None, allow_network: bool = False,
                 seed: Optional[int] = None) -> dict:
    if kind == "fake":
        return {ROLE_USER: FakeUserModel(), ROLE_AUDITOR: FakeAuditorModel(), ROLE_JUDGE: FakeJudgeModel()}
    if kind == "openai":
        if not model_id:
            raise ValueError("--model-id is required for --model openai")
        m = OpenAIChatModel(model_id, allow_network=allow_network, seed=seed)
        return {ROLE_USER: m, ROLE_AUDITOR: m, ROLE_JUDGE: m}
    raise ValueError(f"unknown model kind {kind!r}")
