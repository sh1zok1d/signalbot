"""Cloud-agent OpenAI network adapter.

Environment-only transport boundary. OpenAIProvider remains authoritative for
request construction, schemas, model parameters, parsing and accounting.
"""
from __future__ import annotations

import http.client
import os
import ssl
from urllib.parse import urlsplit

from .context import ContractError
from .provider import ProviderFailure

TARGET_HOST = "api.openai.com"
TARGET_PORT = 443
MAX_WIRE_BYTES = 4_000_000


def _proxy_endpoint(environ=None):
    env = os.environ if environ is None else environ
    raw = env.get("HTTPS_PROXY") or env.get("https_proxy")
    if not isinstance(raw, str) or not raw.strip():
        raise ContractError("HTTPS_PROXY is required for cloud OpenAI transport")
    parsed = urlsplit(raw.strip())
    if parsed.scheme.lower() != "http":
        raise ContractError("cloud OpenAI proxy must use http CONNECT")
    if parsed.username is not None or parsed.password is not None:
        raise ContractError("proxy userinfo is not allowed")
    if not parsed.hostname:
        raise ContractError("invalid HTTPS_PROXY host")
    try:
        port = parsed.port or 80
    except ValueError as exc:
        raise ContractError("invalid HTTPS_PROXY port") from exc
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ContractError("HTTPS_PROXY must be an origin URL")
    return parsed.hostname, port


def _without_authorization(headers):
    if not isinstance(headers, dict):
        raise ContractError("provider headers must be a dict")
    return {k: v for k, v in headers.items() if k.lower() != "authorization"}


class CloudProxyOpenAITransport:
    """Route provider-generated OpenAI HTTP through the sandbox HTTPS proxy.

    The sandbox proxy supplies provider authentication. This adapter removes
    only Authorization at that boundary; method, path, body bytes and every
    other provider-generated header are forwarded unchanged.
    """

    def __call__(self, method, path, body, headers, timeout):
        proxy_host, proxy_port = _proxy_endpoint()
        forwarded_headers = _without_authorization(headers)

        conn = http.client.HTTPConnection(proxy_host, proxy_port, timeout=timeout)
        try:
            conn.set_tunnel(TARGET_HOST, TARGET_PORT)
            conn.connect()
            context = ssl.create_default_context()
            conn.sock = context.wrap_socket(conn.sock, server_hostname=TARGET_HOST)
            conn.request(method, path, body=body or b"", headers=forwarded_headers)
            response = conn.getresponse()
            wire = response.read(MAX_WIRE_BYTES + 1)
            if len(wire) > MAX_WIRE_BYTES:
                raise ProviderFailure(
                    "oversized provider response", wire, billing="UNCERTAIN"
                )
            return response.status, wire
        finally:
            conn.close()
