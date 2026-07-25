"""Unit tests for common/logging_setup.py's Telegram-token leak prevention:
(1) httpx/httpcore/telegram loggers quieted to WARNING by default, and (2) a
`TelegramTokenRedactionFilter` attached to every root StreamHandler that
redacts a Telegram Bot API URL's token segment regardless of logger/severity.
Only syntactically fake tokens are used — never a real secret.
"""
from __future__ import annotations

import io
import json
import logging
import sys

import pytest

from common.logging_setup import TelegramTokenRedactionFilter, setup_logging

FAKE_TOKEN = "123456789:AAExampleFakeToken"
FAKE_URL = f"https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage"


class _isolate_root_logging:
    """Clears root logging handlers so setup_logging() attaches a fresh
    handler bound to our capture stream, then restores the original handlers
    afterwards (matches the pattern used in tests/test_main_shadow_cli.py and
    tests/test_main_telegram_cli.py)."""

    def __enter__(self):
        self._root = logging.getLogger()
        self._saved_handlers = self._root.handlers[:]
        self._saved_levels = {
            name: logging.getLogger(name).level
            for name in ("httpx", "httpcore", "telegram", "websockets", "asyncpg")
        }
        self._root.handlers.clear()
        return self

    def __exit__(self, *exc):
        self._root.handlers[:] = self._saved_handlers
        for name, level in self._saved_levels.items():
            logging.getLogger(name).setLevel(level)
        return False


def _setup_capturing(level="INFO"):
    """setup_logging() + redirect the resulting handler(s) to an in-memory
    buffer; returns the buffer."""
    buf = io.StringIO()
    setup_logging(level)
    for handler in logging.getLogger().handlers:
        handler.setStream(buf)
    return buf


# ============================================================================
# A. httpx/httpcore/telegram loggers quieted to WARNING (level suppression)
# ============================================================================
def test_httpx_logger_quieted_to_warning():
    with _isolate_root_logging():
        setup_logging("INFO")
        assert logging.getLogger("httpx").getEffectiveLevel() == logging.WARNING


def test_httpcore_logger_quieted_to_warning():
    with _isolate_root_logging():
        setup_logging("INFO")
        assert logging.getLogger("httpcore").getEffectiveLevel() == logging.WARNING


def test_httpcore_child_loggers_inherit_warning():
    with _isolate_root_logging():
        setup_logging("INFO")
        # httpcore's real submodules log under child names like this
        assert logging.getLogger("httpcore.http11").getEffectiveLevel() == logging.WARNING
        assert logging.getLogger("httpcore.connection").getEffectiveLevel() == logging.WARNING


def test_telegram_logger_quieted_to_warning():
    with _isolate_root_logging():
        setup_logging("INFO")
        assert logging.getLogger("telegram").getEffectiveLevel() == logging.WARNING


def test_httpx_info_request_log_is_suppressed():
    with _isolate_root_logging():
        buf = _setup_capturing("INFO")
        logging.getLogger("httpx").info(
            'HTTP Request: %s %s "%s %d %s"', "POST", FAKE_URL, "HTTP/1.1", 200, "OK")
        out = buf.getvalue()
        assert out == ""                 # suppressed entirely: never reached a handler
        assert FAKE_TOKEN not in out


def test_our_own_runtime_telegram_logger_name_is_unaffected():
    # our own code logs under "runtime.telegram_cli" etc, NOT under the bare
    # "telegram" namespace — must stay at the configured level (INFO), never
    # accidentally silenced by the third-party "telegram" suppression.
    with _isolate_root_logging():
        setup_logging("INFO")
        assert logging.getLogger("runtime.telegram_cli").getEffectiveLevel() == logging.INFO


# ============================================================================
# B. TelegramTokenRedactionFilter: redaction regardless of logger/severity
# ============================================================================
def test_warning_record_with_url_in_msg_is_redacted():
    with _isolate_root_logging():
        buf = _setup_capturing("INFO")
        logging.getLogger("httpx").warning(f"HTTP Request: POST {FAKE_URL} failed")
        out = buf.getvalue()
        assert FAKE_TOKEN not in out
        assert "https://api.telegram.org/bot***/sendMessage" in out


def test_warning_record_from_arbitrary_logger_name_is_redacted():
    # the filter is attached to the HANDLER, so it applies to every logger,
    # not just httpx/httpcore/telegram.
    with _isolate_root_logging():
        buf = _setup_capturing("INFO")
        logging.getLogger("some.other.module").warning(f"failed calling {FAKE_URL}")
        out = buf.getvalue()
        assert FAKE_TOKEN not in out
        assert "bot***" in out


def test_string_formatting_args_containing_url_are_redacted():
    with _isolate_root_logging():
        buf = _setup_capturing("INFO")
        logging.getLogger("httpcore.http11").warning("request url: %s", FAKE_URL)
        out = buf.getvalue()
        assert FAKE_TOKEN not in out
        assert "bot***" in out


def test_url_object_arg_is_redacted():
    httpx = pytest.importorskip("httpx")
    with _isolate_root_logging():
        buf = _setup_capturing("INFO")
        url = httpx.URL(FAKE_URL)
        logging.getLogger("httpx").warning(
            'HTTP Request: %s %s "%s %d %s"', "POST", url, "HTTP/1.1", 200, "OK")
        out = buf.getvalue()
        assert FAKE_TOKEN not in out
        assert "bot***" in out


def test_non_string_non_matching_arg_is_left_unchanged():
    with _isolate_root_logging():
        buf = _setup_capturing("INFO")
        logging.getLogger("httpx").warning("status=%d", 200)
        out = buf.getvalue()
        assert "status=200" in out   # %d formatting still works normally


def test_exception_logging_containing_url_is_redacted():
    with _isolate_root_logging():
        buf = _setup_capturing("INFO")
        try:
            raise RuntimeError(f"failed hitting {FAKE_URL}")
        except RuntimeError:
            logging.getLogger("main").error("send failed", exc_info=True)
        out = buf.getvalue()
        assert FAKE_TOKEN not in out
        assert "bot***" in out
        assert "RuntimeError" in out   # the rest of the traceback is preserved


def test_dict_style_args_are_redacted():
    with _isolate_root_logging():
        buf = _setup_capturing("INFO")
        logging.getLogger("httpx").warning("url=%(url)s", {"url": FAKE_URL})
        out = buf.getvalue()
        assert FAKE_TOKEN not in out


def test_filter_added_exactly_once_across_repeated_setup_calls():
    with _isolate_root_logging():
        setup_logging("INFO")
        setup_logging("INFO")
        setup_logging("DEBUG")
        for handler in logging.getLogger().handlers:
            count = sum(1 for f in handler.filters if isinstance(f, TelegramTokenRedactionFilter))
            assert count == 1


# ============================================================================
# C. fake token never appears anywhere in captured output; ordinary INFO stays visible
# ============================================================================
def test_fake_token_never_appears_across_combined_scenarios():
    with _isolate_root_logging():
        buf = _setup_capturing("INFO")
        logging.getLogger("httpx").info("suppressed info %s", FAKE_URL)   # suppressed
        logging.getLogger("httpx").warning("warn %s", FAKE_URL)
        logging.getLogger("httpcore.http11").warning("warn2 %s", FAKE_URL)
        try:
            raise RuntimeError(FAKE_URL)
        except RuntimeError:
            logging.getLogger("telegram.Bot").error("err", exc_info=True)
        out = buf.getvalue()
        assert FAKE_TOKEN not in out


def test_ordinary_application_info_messages_remain_visible():
    with _isolate_root_logging():
        buf = _setup_capturing("INFO")
        logging.getLogger("main").info("Connected to TimescaleDB")
        logging.getLogger("runtime.telegram_cli").info("dispatching telegram command")
        out = buf.getvalue()
        assert "Connected to TimescaleDB" in out
        assert "dispatching telegram command" in out


def test_root_level_stays_info_not_globally_raised_to_warning():
    with _isolate_root_logging():
        setup_logging("INFO")
        assert logging.getLogger().getEffectiveLevel() == logging.INFO


# ============================================================================
# D. exact regression URL shapes
# ============================================================================
@pytest.mark.parametrize("url,leaked_fragment", [
    ("https://api.telegram.org/botecho/sendMessage", "echo"),
    ("https://api.telegram.org/bot123456789:AAExampleFakeToken/sendMessage",
     "123456789:AAExampleFakeToken"),
])
def test_exact_observed_url_shapes_are_redacted(url, leaked_fragment):
    with _isolate_root_logging():
        buf = _setup_capturing("INFO")
        logging.getLogger("httpx").warning(f"HTTP Request: POST {url} failed")
        out = buf.getvalue()
        assert leaked_fragment not in out
        assert "https://api.telegram.org/bot***/sendMessage" in out


# ============================================================================
# E. --telegram-json still emits exactly one clean JSON object on stdout
# ============================================================================
def test_telegram_json_stdout_still_single_clean_json_object(monkeypatch, capsys):
    import main

    class _FakeCfg:
        symbol = "BTCUSDT"

    monkeypatch.setattr(main.Config, "load", staticmethod(lambda: _FakeCfg()))
    monkeypatch.setattr(main, "load_secrets",
                        lambda cfg: type("S", (), {
                            "postgres_dsn": "postgresql://x", "redis_url": "redis://x",
                            "telegram_token": FAKE_TOKEN, "telegram_chat_id": "12345"})())

    async def fake_telegram(args, cfg, secrets):
        logging.getLogger("httpx").warning(f"HTTP Request: POST {FAKE_URL} failed")
        logging.getLogger("main").info("Connected to TimescaleDB")
        print(json.dumps({"command": "TELEGRAM_ONCE", "state": "READY"}))

    monkeypatch.setattr(main, "run_telegram_cli_command", fake_telegram)
    monkeypatch.setattr(sys, "argv", ["main.py", "--telegram-once", "--telegram-json"])

    with _isolate_root_logging():
        main.main()
    out, err = capsys.readouterr()

    parsed = json.loads(out)              # stdout is exactly one JSON object
    assert parsed == {"command": "TELEGRAM_ONCE", "state": "READY"}
    assert out.strip().count("\n") == 0
    assert FAKE_TOKEN not in out
    assert FAKE_TOKEN not in err          # redacted even on the (redirected) stderr stream
    assert "Connected to TimescaleDB" in err


# ============================================================================
# F. existing application-level Telegram error sanitization is unchanged
# ============================================================================
def test_sanitize_telegram_error_contract_unchanged():
    from notifications.telegram_client import sanitize_telegram_error
    exc = RuntimeError(f"failed: {FAKE_URL}")
    summary = sanitize_telegram_error(exc, token=FAKE_TOKEN, chat_id="12345")
    assert FAKE_TOKEN not in summary
    assert "bot***" in summary
