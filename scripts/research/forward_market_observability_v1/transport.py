"""Transport adapters that capture authoritative raw bytes BEFORE JSON parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

WEBSOCKET_AUTHORITATIVE_BYTES = (
    "exact application-message payload bytes delivered by the WebSocket "
    "client after transport framing/decompression but BEFORE JSON/text parsing"
)
REST_AUTHORITATIVE_BYTES = (
    "exact HTTP response body bytes returned by the client BEFORE JSON parsing"
)


@dataclass(frozen=True)
class TransportReceipt:
    raw_payload: bytes
    transport: dict[str, Any]


def websocket_application_payload_bytes(
    message: str | bytes,
    *,
    endpoint: str,
    stream: str,
    websocket_message_type: str | None = None,
) -> TransportReceipt:
    """Authoritative WS bytes: application payload after framing/decompression."""
    if isinstance(message, bytes):
        raw = message
        msg_type = websocket_message_type or "binary"
    elif isinstance(message, str):
        raw = message.encode("utf-8")
        msg_type = websocket_message_type or "text"
    else:
        raise TypeError("WEBSOCKET_MESSAGE_MUST_BE_STR_OR_BYTES")
    return TransportReceipt(
        raw_payload=raw,
        transport={
            "transport": "websocket",
            "endpoint": endpoint,
            "stream": stream,
            "http_status": None,
            "content_encoding": None,
            "websocket_message_type": msg_type,
            "authoritative_raw_bytes_definition": WEBSOCKET_AUTHORITATIVE_BYTES,
        },
    )


def rest_response_body_bytes(
    body: bytes,
    *,
    endpoint: str,
    stream: str,
    http_status: int,
    content_encoding: str | None = None,
) -> TransportReceipt:
    """Authoritative REST bytes: exact HTTP response body before JSON parsing."""
    if not isinstance(body, (bytes, bytearray)):
        raise TypeError("REST_BODY_MUST_BE_BYTES")
    return TransportReceipt(
        raw_payload=bytes(body),
        transport={
            "transport": "rest",
            "endpoint": endpoint,
            "stream": stream,
            "http_status": http_status,
            "content_encoding": content_encoding,
            "websocket_message_type": None,
            "authoritative_raw_bytes_definition": REST_AUTHORITATIVE_BYTES,
        },
    )


def fetch_rest_body(
    endpoint: str,
    *,
    stream: str,
    timeout: float = 10.0,
    opener: Callable[..., Any] | None = None,
) -> TransportReceipt:
    request = Request(endpoint, headers={"User-Agent": "signalbot-forward-observability-v1"})
    open_fn = opener or urlopen
    try:
        with open_fn(request, timeout=timeout) as response:
            status = int(getattr(response, "status", getattr(response, "code", 200)))
            encoding = None
            headers = getattr(response, "headers", None)
            if headers is not None:
                encoding = headers.get("Content-Encoding")
            body = response.read()
    except HTTPError as exc:
        body = exc.read() if hasattr(exc, "read") else b""
        return rest_response_body_bytes(
            body,
            endpoint=endpoint,
            stream=stream,
            http_status=int(exc.code),
            content_encoding=None,
        )
    except URLError:
        raise
    if not isinstance(body, (bytes, bytearray)):
        raise TypeError("REST_READ_DID_NOT_RETURN_BYTES")
    return rest_response_body_bytes(
        bytes(body),
        endpoint=endpoint,
        stream=stream,
        http_status=status,
        content_encoding=encoding,
    )
