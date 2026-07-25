"""Unit tests for the Telegram sender adapter, focused on the lazy-import
discipline (the `telegram` package is broken in some environments and must
never be imported at module load time) and the pure error-sanitization helper.
No real network call is ever made in these tests.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from notifications.telegram_client import (
    TelegramSendError, TelegramSendResult, TelegramSender,
    sanitize_telegram_error,
)

ROOT = Path(__file__).resolve().parents[2]


# ============================================================================
# lazy-import discipline
# ============================================================================
def test_importing_module_does_not_import_telegram_package():
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; import notifications.telegram_client; "
         "assert 'telegram' not in sys.modules, sorted(m for m in sys.modules if 'telegram' in m)"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_constructing_sender_does_not_import_telegram_package():
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; from notifications.telegram_client import TelegramSender; "
         "s = TelegramSender('fake-token'); "
         "assert 'telegram' not in sys.modules, sorted(m for m in sys.modules if 'telegram' in m)"],
        cwd=str(ROOT), capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_source_has_no_top_level_telegram_import():
    text = (ROOT / "notifications" / "telegram_client.py").read_text()
    lines = [l for l in text.splitlines() if not l.strip().startswith("#")]
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import telegram") or stripped.startswith("from telegram"):
            # only acceptable indented inside a function/method body
            indent = len(line) - len(line.lstrip())
            assert indent > 0, f"top-level telegram import found: {line!r}"


# ============================================================================
# TelegramSender construction
# ============================================================================
def test_sender_rejects_blank_token():
    with pytest.raises(ValueError):
        TelegramSender("")


def test_sender_rejects_whitespace_only_token():
    with pytest.raises(ValueError):
        TelegramSender("   ")


def test_sender_rejects_non_string_token():
    with pytest.raises(ValueError):
        TelegramSender(12345)


def test_sender_constructs_with_valid_token():
    sender = TelegramSender("123456:ABC-token")
    assert sender is not None


def test_send_result_is_frozen():
    result = TelegramSendResult(message_id=42)
    assert result.message_id == 42
    with pytest.raises(Exception):
        result.message_id = 1


# ============================================================================
# TelegramSendError
# ============================================================================
def test_send_error_stores_retry_after():
    exc = TelegramSendError("boom", retry_after=30.0)
    assert exc.retry_after == 30.0
    assert str(exc) == "boom"


def test_send_error_retry_after_defaults_to_none():
    exc = TelegramSendError("boom")
    assert exc.retry_after is None


def test_send_error_is_runtime_error():
    assert isinstance(TelegramSendError("x"), RuntimeError)


# ============================================================================
# sanitize_telegram_error
# ============================================================================
def test_sanitize_strips_literal_token():
    exc = RuntimeError("failed using token 123456:ABC-token in request")
    summary = sanitize_telegram_error(exc, token="123456:ABC-token")
    assert "123456:ABC-token" not in summary
    assert "***" in summary


def test_sanitize_redacts_bot_api_url():
    exc = RuntimeError("POST https://api.telegram.org/bot123456:ABC-token/sendMessage failed")
    summary = sanitize_telegram_error(exc, token="123456:ABC-token")
    assert "123456:ABC-token" not in summary
    assert "https://api.telegram.org/bot***" in summary


def test_sanitize_redacts_url_even_without_matching_token_arg():
    exc = RuntimeError("POST https://api.telegram.org/botDIFFERENT-token/sendMessage failed")
    summary = sanitize_telegram_error(exc)
    assert "DIFFERENT-token" not in summary


def test_sanitize_truncates_to_300_chars():
    exc = RuntimeError("x" * 5000)
    summary = sanitize_telegram_error(exc)
    assert len(summary) <= 300


def test_sanitize_with_no_token_still_returns_message():
    exc = RuntimeError("generic network failure")
    summary = sanitize_telegram_error(exc)
    assert "generic network failure" in summary


def test_sanitize_deterministic():
    exc = RuntimeError("failure abc")
    assert sanitize_telegram_error(exc) == sanitize_telegram_error(exc)


# ============================================================================
# sanitize_telegram_error: raw chat id redaction
# ============================================================================
def test_sanitize_strips_literal_chat_id():
    exc = RuntimeError("failed to deliver to chat 123456789: forbidden")
    summary = sanitize_telegram_error(exc, chat_id="123456789")
    assert "123456789" not in summary
    assert "***" in summary


def test_sanitize_strips_negative_private_chat_id():
    # Telegram supergroup/channel chat ids are negative, e.g. -1001234567890
    exc = RuntimeError("failed to deliver to chat -1001234567890: forbidden")
    summary = sanitize_telegram_error(exc, chat_id="-1001234567890")
    assert "-1001234567890" not in summary
    assert "***" in summary


def test_sanitize_strips_token_chat_id_and_url_together():
    exc = RuntimeError(
        "POST https://api.telegram.org/bot123456:ABC-token/sendMessage?chat_id=987654321 failed")
    summary = sanitize_telegram_error(exc, token="123456:ABC-token", chat_id="987654321")
    assert "123456:ABC-token" not in summary
    assert "987654321" not in summary
    assert "https://api.telegram.org/bot***" in summary


def test_sanitize_blank_chat_id_is_a_noop_and_never_mangles_text():
    exc = RuntimeError("chat not found: generic failure")
    summary = sanitize_telegram_error(exc, chat_id="")
    assert summary == "chat not found: generic failure"


def test_sanitize_blank_chat_id_does_not_replace_harmless_short_substrings():
    # a blank chat_id must never accidentally strip an empty-string "match"
    # (str.replace("", x) would otherwise interleave into every position)
    exc = RuntimeError("normal message with numbers 12345 in it")
    summary = sanitize_telegram_error(exc, chat_id="")
    assert summary == "normal message with numbers 12345 in it"


def test_sanitize_chat_id_redaction_is_deterministic():
    exc = RuntimeError("chat 555555 failed")
    a = sanitize_telegram_error(exc, chat_id="555555")
    b = sanitize_telegram_error(exc, chat_id="555555")
    assert a == b


def test_sanitize_chat_id_redaction_stays_bounded_to_300_chars():
    exc = RuntimeError(("chat 555555 failed; " * 100))
    summary = sanitize_telegram_error(exc, chat_id="555555")
    assert "555555" not in summary
    assert len(summary) <= 300


# ============================================================================
# TelegramSender.send_message sanitizes with BOTH token and chat_id
# ============================================================================
def test_send_message_error_path_sanitizes_chat_id(monkeypatch):
    """A real TelegramError raised deep inside python-telegram-bot could embed
    the chat id in its message; TelegramSender.send_message must sanitize with
    BOTH the token and the chat_id before wrapping it in TelegramSendError."""
    import asyncio

    class _FakeTelegramError(Exception):
        pass

    class _FakeBot:
        async def send_message(self, *, chat_id, text, parse_mode):
            raise _FakeTelegramError(
                f"Forbidden: bot was blocked by chat {chat_id} (token 123456:ABC-token)")

    sender = TelegramSender("123456:ABC-token")
    sender._bot = _FakeBot()   # bypass the lazy `telegram.Bot` construction

    import notifications.telegram_client as client_mod
    fake_telegram_error_module = type(
        "M", (), {"RetryAfter": type("RetryAfter", (Exception,), {}),
                  "TelegramError": _FakeTelegramError})
    monkeypatch.setitem(sys.modules, "telegram.error", fake_telegram_error_module)

    with pytest.raises(TelegramSendError) as excinfo:
        asyncio.run(sender.send_message(chat_id="987654321", html="<b>hi</b>"))
    text = str(excinfo.value)
    assert "987654321" not in text
    assert "123456:ABC-token" not in text
