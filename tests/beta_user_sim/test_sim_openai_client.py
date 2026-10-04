"""Offline OpenAI client contract: omitted temperature, exact model id, usage, sanitized errors.

No test opens a socket. urlopen is replaced before the client is constructed.
"""
import io
import json
import socket
from email.message import Message

import pytest

from tools.beta_user_sim.llm import (ROLE_AUDITOR, ROLE_JUDGE, ROLE_USER, TEMPERATURE_DEFAULT,
                                     FakeUserModel, OpenAIRequestError, aggregate_api_usage,
                                     build_models, openai_chat_body)


SECRET = "sk-test-not-used"


class _Calls:
    def __init__(self, rows):
        self.api_calls = rows


def _block_network(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("network attempted")
    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


def _authorize(monkeypatch):
    monkeypatch.setenv("SIGNALBOT_SIM_ALLOW_NETWORK", "1")
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)


def _response(payload: dict):
    class Resp:
        def read(self):
            return json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False
    return Resp()


def _http_error(status, body: dict):
    import urllib.error
    return urllib.error.HTTPError(
        "https://api.openai.com/v1/chat/completions", status, "Bad Request", Message(),
        io.BytesIO(json.dumps(body).encode("utf-8")))


def test_unset_temperature_is_omitted_from_the_request_body():
    body = openai_chat_body("chat-latest", [{"role": "user", "content": "{}"}])
    assert body["model"] == "chat-latest"
    assert "temperature" not in body
    explicit = openai_chat_body("chat-latest", [{"role": "user", "content": "{}"}], temperature=0.0)
    assert explicit["temperature"] == 0.0


def test_chat_latest_path_omits_temperature_and_keeps_the_model_id(monkeypatch):
    _block_network(monkeypatch)
    _authorize(monkeypatch)
    sent = []

    def urlopen(req, timeout=None):
        sent.append(json.loads(req.data.decode("utf-8")))
        assert SECRET not in req.data.decode("utf-8")
        return _response({
            "model": "chat-latest-2026-snapshot",
            "choices": [{"message": {"content": "{\"action\":\"NO_ACTION\"}"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 4, "total_tokens": 15,
                      "prompt_tokens_details": {"cached_tokens": 3}},
        })

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    models = build_models("openai", model_id="chat-latest", allow_network=True)
    assert models[ROLE_USER] is models[ROLE_AUDITOR] is models[ROLE_JUDGE]
    assert models[ROLE_USER].model_id == "chat-latest"
    assert models[ROLE_USER].settings()["temperature"] == TEMPERATURE_DEFAULT
    assert models[ROLE_USER].settings()["bit_identical_reproducibility"] == "NOT_GUARANTEED"
    text = models[ROLE_USER].complete([{"role": "user", "content": "{}"}], role=ROLE_USER)
    assert json.loads(text)["action"] == "NO_ACTION"
    assert sent[0]["model"] == "chat-latest" and "temperature" not in sent[0]
    # A returned snapshot id does not replace the next request's model.
    models[ROLE_AUDITOR].complete([{"role": "user", "content": "{}"}], role=ROLE_AUDITOR)
    assert sent[1]["model"] == "chat-latest"
    assert "temperature" not in sent[1]
    assert models[ROLE_USER].model_id == "chat-latest"


def test_api_error_does_not_retry_or_change_the_model(monkeypatch):
    _block_network(monkeypatch)
    _authorize(monkeypatch)
    calls = {"n": 0}

    def urlopen(req, timeout=None):
        calls["n"] += 1
        body = json.loads(req.data.decode("utf-8"))
        assert body["model"] == "chat-latest"
        assert "temperature" not in body
        raise _http_error(400, {"error": {
            "message": f"Unsupported value. key {SECRET} Bearer {SECRET}",
            "type": "invalid_request_error",
            "param": "temperature",
            "code": "unsupported_value",
        }})

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    model = build_models("openai", model_id="chat-latest", allow_network=True)[ROLE_USER]
    with pytest.raises(OpenAIRequestError) as caught:
        model.complete([{"role": "user", "content": "{}"}], role=ROLE_USER)
    err = caught.value
    assert calls["n"] == 1
    assert model.model_id == "chat-latest"
    assert model.api_calls == []
    assert err.status == 400
    assert err.error_type == "invalid_request_error"
    assert err.code == "unsupported_value"
    assert err.param == "temperature"
    assert "Unsupported value" in err.message
    rendered = str(err)
    assert SECRET not in rendered and "Bearer sk-" not in rendered
    assert "Authorization" not in rendered


def test_usage_is_copied_when_present_and_null_when_absent(monkeypatch):
    _block_network(monkeypatch)
    _authorize(monkeypatch)
    payloads = [
        {"model": "chat-latest", "choices": [{"message": {"content": "{}"}}],
         "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12,
                   "prompt_tokens_details": {"cached_tokens": 4}}},
        {"model": "chat-latest", "choices": [{"message": {"content": "{}"}}],
         "usage": {"input_tokens": 7, "output_tokens": 1}},
        {"model": "chat-latest", "choices": [{"message": {"content": "{}"}}]},
    ]

    def urlopen(req, timeout=None):
        return _response(payloads.pop(0))

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    model = build_models("openai", model_id="chat-latest", allow_network=True)[ROLE_USER]
    model.complete([{"role": "user", "content": "{}"}], role=ROLE_USER)
    model.complete([{"role": "user", "content": "{}"}], role=ROLE_AUDITOR)
    model.complete([{"role": "user", "content": "{}"}], role=ROLE_JUDGE)
    first, second, third = model.api_calls
    assert first == {"role": ROLE_USER, "model": "chat-latest", "input_tokens": 10,
                     "cached_input_tokens": 4, "output_tokens": 2, "total_tokens": 12}
    assert second["input_tokens"] == 7 and second["output_tokens"] == 1
    assert second["cached_input_tokens"] is None and second["total_tokens"] is None
    assert third["model"] == "chat-latest"
    assert third["input_tokens"] is None and third["output_tokens"] is None
    assert third["cached_input_tokens"] is None and third["total_tokens"] is None
    usage = aggregate_api_usage({"a": model, "b": model})
    assert usage["by_role"][ROLE_USER]["calls"] == 1
    assert usage["by_role"][ROLE_USER]["input_tokens"] == 10
    assert usage["by_role"][ROLE_AUDITOR]["calls"] == 1
    assert usage["by_role"][ROLE_AUDITOR]["total_tokens"] is None
    assert usage["by_role"][ROLE_JUDGE]["calls"] == 1
    assert usage["by_role"][ROLE_JUDGE]["input_tokens"] is None
    # A missing field on any call makes that total unknown rather than a partial sum.
    assert usage["total"]["calls"] == 3
    assert usage["total"]["input_tokens"] is None
    assert usage["total"]["model"] == "chat-latest"
    assert len(usage["calls"]) == 3
    # A call that omits the returned model makes that rollup unknown.
    partial = {"role": ROLE_USER, "model": None, "input_tokens": 1, "cached_input_tokens": None,
               "output_tokens": 1, "total_tokens": 2}
    mixed = aggregate_api_usage({"a": _Calls([first, partial])})
    assert mixed["by_role"][ROLE_USER]["model"] is None
    assert mixed["by_role"][ROLE_USER]["input_tokens"] == 11
    assert mixed["total"]["model"] is None


def test_fake_models_stay_deterministic_and_record_no_api_usage():
    models = build_models("fake")
    assert isinstance(models[ROLE_USER], FakeUserModel)
    assert models[ROLE_USER].settings() == {"deterministic": True, "network": False}
    now = "fixed-now"
    from tools.beta_user_sim.llm import _h
    while _h(now) % 4 == 0:
        now += "x"
    raw = models[ROLE_USER].complete(
        [{"role": "user", "content": json.dumps({"now": now, "new_messages": []})}], role=ROLE_USER)
    assert json.loads(raw) == {"action": "NO_ACTION"}
    usage = aggregate_api_usage(models)
    assert usage["calls"] == []
    assert usage["total"]["calls"] is None
    assert usage["by_role"][ROLE_USER]["input_tokens"] is None
