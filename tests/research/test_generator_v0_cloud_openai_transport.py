from __future__ import annotations

import pytest

from scripts.research.generator_v0.cloud_openai_transport import (
    CloudProxyOpenAITransport,
    _proxy_endpoint,
)
from scripts.research.generator_v0.context import ContractError


class _Response:
    status = 200

    def read(self, _limit):
        return b'{"ok":true}'


class _Conn:
    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.tunnel = None
        self.sock = object()
        self.sent = None
        self.closed = False

    def set_tunnel(self, host, port):
        self.tunnel = (host, port)

    def connect(self):
        return None

    def request(self, method, path, body, headers):
        self.sent = (method, path, body, headers)

    def getresponse(self):
        return _Response()

    def close(self):
        self.closed = True


class _TLS:
    def wrap_socket(self, sock, *, server_hostname):
        assert server_hostname == "api.openai.com"
        return sock


def test_cloud_transport_preserves_request_except_authorization(monkeypatch):
    holder = {}

    def factory(host, port, timeout):
        holder["conn"] = _Conn(host, port, timeout)
        return holder["conn"]

    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:40465")
    monkeypatch.setattr(
        "scripts.research.generator_v0.cloud_openai_transport.http.client.HTTPConnection",
        factory,
    )
    monkeypatch.setattr(
        "scripts.research.generator_v0.cloud_openai_transport.ssl.create_default_context",
        lambda: _TLS(),
    )

    transport = CloudProxyOpenAITransport()
    body = b'{"model":"gpt-6-sol","background":true}'
    status, wire = transport(
        "POST",
        "/v1/responses",
        body,
        {
            "Authorization": "Bearer placeholder",
            "Content-Type": "application/json",
            "X-Signalbot-Test": "kept",
        },
        60,
    )

    conn = holder["conn"]
    assert status == 200
    assert wire == b'{"ok":true}'
    assert conn.host == "127.0.0.1"
    assert conn.port == 40465
    assert conn.tunnel == ("api.openai.com", 443)
    assert conn.sent[0] == "POST"
    assert conn.sent[1] == "/v1/responses"
    assert conn.sent[2] is body
    assert conn.sent[3] == {
        "Content-Type": "application/json",
        "X-Signalbot-Test": "kept",
    }
    assert conn.closed is True


def test_proxy_port_is_read_from_current_environment(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:34583")
    assert _proxy_endpoint() == ("127.0.0.1", 34583)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:40465")
    assert _proxy_endpoint() == ("127.0.0.1", 40465)


def test_proxy_userinfo_is_refused(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://user:pass@127.0.0.1:40465")
    with pytest.raises(ContractError, match="userinfo"):
        _proxy_endpoint()


def test_missing_proxy_is_refused(monkeypatch):
    monkeypatch.delenv("HTTPS_PROXY", raising=False)
    monkeypatch.delenv("https_proxy", raising=False)
    with pytest.raises(ContractError, match="HTTPS_PROXY"):
        _proxy_endpoint()
