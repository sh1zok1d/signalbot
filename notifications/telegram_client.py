"""
Thin adapter around python-telegram-bot's `telegram.Bot`.

The `telegram` package is imported LAZILY (only inside `TelegramSender`'s
methods, never at module import time), mirroring the existing deferred-`aiohttp`
pattern used for instrument-metadata bootstrap. This keeps importing this module
— and everything that transitively imports it (runtime/telegram_cli.py, main.py,
every test) — free of any real network-client import cost, and lets unit tests
inject a fake sender that never triggers a `telegram` import at all, so tests
make NO network request.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

# Explicit, bounded timeouts (seconds) for the one send attempt per delivery.
CONNECT_TIMEOUT_S = 10.0
READ_TIMEOUT_S = 10.0
WRITE_TIMEOUT_S = 10.0
POOL_TIMEOUT_S = 10.0


class TelegramSendError(RuntimeError):
    """One Telegram send attempt failed. `retry_after` carries Telegram's own
    requested wait (seconds) when the API supplied one (HTTP 429 / RetryAfter);
    otherwise None. The message is already sanitized (no token/chat id/URL)."""

    def __init__(self, message: str, *, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class TelegramSendResult:
    message_id: int


class TelegramSenderProtocol(Protocol):
    async def send_message(self, *, chat_id: str, html: str) -> TelegramSendResult:
        ...


def sanitize_telegram_error(exc: BaseException, *, token: str = "") -> str:
    """A short, deterministic, secret-free summary of a send failure. Strips the
    bot token (if present in the message) and any bot-API URL, so a sanitized
    summary can be safely stored/reported without ever leaking credentials."""
    text = str(exc)
    if token:
        text = text.replace(token, "***")
    # Telegram Bot API URLs embed the token as a path segment: redact defensively
    # even if the token string itself doesn't literally match (e.g. re-encoded).
    text = _redact_bot_api_urls(text)
    return text[:300]


def _redact_bot_api_urls(text: str) -> str:
    import re
    return re.sub(r"https://api\.telegram\.org/bot[^/\s]+", "https://api.telegram.org/bot***", text)


class TelegramSender:
    """The REAL sender: one thin wrapper around `telegram.Bot.send_message`,
    parse_mode=HTML, explicit bounded timeouts. Constructed only when no fake
    sender is injected (i.e. real `--telegram-once` / `--telegram-test`
    execution) — never during tests."""

    def __init__(self, token: str):
        if not isinstance(token, str) or not token.strip():
            raise ValueError("token must be a non-empty string")
        self._token = token
        self._bot = None   # lazily constructed on first send

    def _ensure_bot(self):
        if self._bot is None:
            import telegram          # lazy: see module docstring
            from telegram.request import HTTPXRequest
            request = HTTPXRequest(
                connect_timeout=CONNECT_TIMEOUT_S, read_timeout=READ_TIMEOUT_S,
                write_timeout=WRITE_TIMEOUT_S, pool_timeout=POOL_TIMEOUT_S)
            self._bot = telegram.Bot(token=self._token, request=request)
        return self._bot

    async def send_message(self, *, chat_id: str, html: str) -> TelegramSendResult:
        from telegram.error import RetryAfter, TelegramError   # lazy
        bot = self._ensure_bot()
        try:
            message = await bot.send_message(chat_id=chat_id, text=html, parse_mode="HTML")
        except RetryAfter as exc:
            raise TelegramSendError(
                sanitize_telegram_error(exc, token=self._token),
                retry_after=float(exc.retry_after)) from exc
        except TelegramError as exc:
            raise TelegramSendError(sanitize_telegram_error(exc, token=self._token)) from exc
        return TelegramSendResult(message_id=message.message_id)
