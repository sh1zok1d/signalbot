"""Model interface. CI and the default CLI use deterministic fakes; there is no network.

`OpenAIChatModel` exists only so a later, explicitly authorized smoke run does not
need new code. It refuses to construct unless `allow_network=True` is passed AND
SIGNALBOT_SIM_ALLOW_NETWORK=1 AND OPENAI_API_KEY are set. Tests may construct it
only against a mocked HTTP response; they do not open a socket.

Temperature is optional. When it is unset the request omits the field and the
manifest records DEFAULT. The client sends the requested model id unchanged,
does not retry, and does not replace a rejected parameter with another value.
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


class OpenAIRequestError(RuntimeError):
    """A sanitized Chat Completions failure. No key, header, or request body."""

    def __init__(self, status: Optional[int], error_type: Optional[str], code: Optional[str],
                 param: Optional[str], message: str):
        self.status, self.error_type, self.code, self.param = status, error_type, code, param
        self.message = message
        super().__init__(
            f"OpenAI HTTP {status} type={error_type} code={code} param={param}: {message}")


_BEARER = re.compile(r"Bearer\s+\S+", re.IGNORECASE)
_SK = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
_USAGE_FIELDS = ("model", "input_tokens", "cached_input_tokens", "output_tokens", "total_tokens")
TEMPERATURE_DEFAULT = "DEFAULT"


def _sanitize(text: Optional[str], secret: Optional[str]) -> str:
    out = "" if text is None else str(text)
    if secret:
        out = out.replace(secret, "[REDACTED]")
    out = _BEARER.sub("Bearer [REDACTED]", out)
    out = _SK.sub("[REDACTED]", out)
    return out[:1000]


def openai_chat_body(model_id: str, messages: Sequence[Mapping[str, str]], *,
                     temperature: Optional[float] = None, seed: Optional[int] = None) -> dict:
    """Chat Completions body. An unset temperature is omitted, not sent as 0."""
    body = {"model": model_id, "messages": [dict(m) for m in messages],
            "response_format": {"type": "json_object"}}
    if temperature is not None:
        body["temperature"] = temperature
    if seed is not None:
        body["seed"] = seed
    return body


def _present(mapping: Mapping, *keys: str):
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def usage_from_payload(payload: Mapping) -> dict:
    """Copy usage the response actually exposes. Missing fields stay None."""
    model = payload.get("model") if isinstance(payload, Mapping) else None
    usage = payload.get("usage") if isinstance(payload, Mapping) else None
    if not isinstance(usage, Mapping):
        return {"model": model, "input_tokens": None, "cached_input_tokens": None,
                "output_tokens": None, "total_tokens": None}
    cached = None
    for details_key in ("prompt_tokens_details", "input_tokens_details"):
        details = usage.get(details_key)
        if isinstance(details, Mapping) and "cached_tokens" in details:
            cached = details["cached_tokens"]
            break
    if cached is None and "cached_tokens" in usage:
        cached = usage["cached_tokens"]
    return {"model": model,
            "input_tokens": _present(usage, "prompt_tokens", "input_tokens"),
            "cached_input_tokens": cached,
            "output_tokens": _present(usage, "completion_tokens", "output_tokens"),
            "total_tokens": usage["total_tokens"] if "total_tokens" in usage else None}


def _blank_usage() -> dict:
    return {"calls": None, "model": None, "input_tokens": None, "cached_input_tokens": None,
            "output_tokens": None, "total_tokens": None}


def _rollup(rows: Sequence[Mapping]) -> dict:
    out = _blank_usage()
    out["calls"] = len(rows)
    models = [row.get("model") for row in rows]
    if rows and all(isinstance(m, str) and m for m in models) and len(set(models)) == 1:
        out["model"] = models[0]
    for field in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"):
        vals = [row.get(field) for row in rows]
        if rows and all(isinstance(v, int) and not isinstance(v, bool) for v in vals):
            out[field] = sum(vals)
    return out


def aggregate_api_usage(models: Mapping) -> dict:
    """Per-call usage plus role and total rollups. Fake models stay unknown, not zero."""
    roles = (ROLE_USER, ROLE_AUDITOR, ROLE_JUDGE)
    seen = set()
    recorded = False
    calls: list = []
    for model in models.values():
        if id(model) in seen:
            continue
        seen.add(id(model))
        got = getattr(model, "api_calls", None)
        if got is not None:
            recorded = True
            calls.extend(got)
    if not recorded:
        return {"calls": [], "by_role": {role: _blank_usage() for role in roles}, "total": _blank_usage()}
    return {"calls": list(calls),
            "by_role": {role: _rollup([c for c in calls if c.get("role") == role]) for role in roles},
            "total": _rollup(calls)}


def openai_http_error(exc, *, secret: Optional[str]) -> OpenAIRequestError:
    raw = ""
    try:
        raw = exc.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - a closed error body still needs a status
        raw = ""
    error_type = code = param = None
    message = _sanitize(getattr(exc, "reason", None) or getattr(exc, "msg", None), secret)
    try:
        parsed = json.loads(raw) if raw else None
    except (TypeError, ValueError):
        parsed = None
    if isinstance(parsed, Mapping):
        err = parsed.get("error")
        if isinstance(err, Mapping):
            error_type = err.get("type")
            code = err.get("code")
            param = err.get("param")
            if err.get("message") is not None:
                message = _sanitize(err.get("message"), secret)
        elif raw:
            message = _sanitize(raw, secret)
    elif raw:
        message = _sanitize(raw, secret)
    return OpenAIRequestError(getattr(exc, "code", None), error_type, code, param, message)


class OpenAIChatModel:
    """Chat Completions client (stdlib only). Offline unless explicitly authorized."""

    def __init__(self, model_id: str, *, allow_network: bool = False, temperature: Optional[float] = None,
                 seed: Optional[int] = None, timeout_s: float = 60.0):
        if not allow_network or os.environ.get("SIGNALBOT_SIM_ALLOW_NETWORK") != "1":
            raise NetworkNotAuthorized("real model calls need --allow-network and SIGNALBOT_SIM_ALLOW_NETWORK=1")
        self._key = os.environ.get("OPENAI_API_KEY")
        if not self._key:
            raise NetworkNotAuthorized("OPENAI_API_KEY is not set")
        self.model_id = model_id
        self.temperature = temperature
        self.seed = seed
        self.timeout_s = timeout_s
        self.api_calls: list = []

    def settings(self) -> dict:
        return {"temperature": TEMPERATURE_DEFAULT if self.temperature is None else self.temperature,
                "seed": self.seed, "response_format": "json_object", "network": True,
                "bit_identical_reproducibility": "NOT_GUARANTEED"}

    def complete(self, messages: Sequence[Mapping[str, str]], *, role: str) -> str:
        import urllib.error
        import urllib.request
        body = openai_chat_body(self.model_id, messages, temperature=self.temperature, seed=self.seed)
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions",
                                     data=json.dumps(body).encode("utf-8"), method="POST",
                                     headers={"Authorization": f"Bearer {self._key}",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310 - fixed https host
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise openai_http_error(exc, secret=self._key) from None
        if not isinstance(payload, Mapping):
            raise OpenAIRequestError(None, None, None, None, "response is not a JSON object")
        self.api_calls.append({"role": role, **usage_from_payload(payload)})
        try:
            return payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise OpenAIRequestError(None, None, None, None, "response has no message content") from None


def build_models(kind: str, *, model_id: Optional[str] = None, allow_network: bool = False,
                 seed: Optional[int] = None) -> dict:
    if kind == "fake":
        return {ROLE_USER: FakeUserModel(), ROLE_AUDITOR: FakeAuditorModel(), ROLE_JUDGE: FakeJudgeModel()}
    if kind == "openai":
        if not model_id:
            raise ValueError("--model-id is required for --model openai")
        # Temperature stays unset: the request uses the model default and never rewrites the id.
        m = OpenAIChatModel(model_id, allow_network=allow_network, temperature=None, seed=seed)
        return {ROLE_USER: m, ROLE_AUDITOR: m, ROLE_JUDGE: m}
    raise ValueError(f"unknown model kind {kind!r}")
