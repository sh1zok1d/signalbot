"""The beta bot's systemd entry point must configure logging through the shared
`common.logging_setup.setup_logging`, so a Telegram Bot API token can never reach
stdout/journald: httpx (python-telegram-bot's transport) logs every request URL,
which embeds the full bot token, at INFO. Only syntactically fake tokens are used.
"""
from __future__ import annotations

import ast
import logging
import sys
from contextlib import contextmanager
from pathlib import Path

import httpx

from common.logging_setup import TelegramTokenRedactionFilter

REPO = Path(__file__).resolve().parents[2]
FAKE_TOKEN = "123456789:AAFakeBetaBotTokenForLogTests_x"
FAKE_URL = f"https://api.telegram.org/bot{FAKE_TOKEN}/getUpdates"
QUIETED = ("httpx", "httpcore", "telegram", "websockets", "asyncpg")


@contextmanager
def fresh_root_logging():
    """Start from an unconfigured root logger (as under systemd) and restore
    pytest's handlers and every touched logger level afterwards. Used inside the
    test body: pytest attaches its capture handlers to root after fixture setup."""
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    saved_levels = {n: logging.getLogger(n).level for n in QUIETED}
    root.handlers.clear()
    try:
        yield root
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
        for n, lvl in saved_levels.items():
            logging.getLogger(n).setLevel(lvl)


def _run_bot_main(monkeypatch):
    """Run the real entry point down its no-Telegram early return (no DB, no polling)."""
    from runtime import beta_bot
    for k, v in {"BETA_ENABLED": "1", "BETA_TELEGRAM_ENABLED": "0", "BETA_TELEGRAM_BOT_TOKEN": "",
                 "BETA_PUSH_ENABLED": ""}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(beta_bot.asyncio, "run",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("bot started")))
    beta_bot.main()


def _emitted(capsys) -> str:
    """Everything written to stdout AND stderr (journald captures both)."""
    cap = capsys.readouterr()
    return cap.out + cap.err


def _httpx_telegram_request():
    """A real httpx request to a Bot API URL; httpx itself emits its INFO request line."""
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True, "result": []}))
    with httpx.Client(transport=transport) as client:
        assert client.post(FAKE_URL).status_code == 200


def test_entry_point_uses_shared_setup_logging_not_basicconfig():
    tree = ast.parse((REPO / "runtime/beta_bot.py").read_text())
    assert not any(isinstance(n, ast.Attribute) and n.attr == "basicConfig" for n in ast.walk(tree))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    first = main.body[0].value
    assert isinstance(first, ast.Call) and getattr(first.func, "id", None) == "setup_logging"
    assert [a.value for a in first.args] == ["INFO"]


def test_main_installs_redaction_filter_and_quiets_transport_loggers(monkeypatch, capsys):
    with fresh_root_logging() as root:
        _run_bot_main(monkeypatch)
        handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
        assert handlers
        for h in handlers:
            assert h.stream is sys.stdout                   # journald under systemd
            assert any(isinstance(f, TelegramTokenRedactionFilter) for f in h.filters)
        for name in ("httpx", "httpcore", "httpcore.http11", "telegram", "telegram.ext"):
            assert logging.getLogger(name).getEffectiveLevel() == logging.WARNING, name
    # the bot's own records go through this handler
    assert "no-Telegram shadow mode" in capsys.readouterr().out   # stdout, not stderr


def test_real_httpx_request_line_never_reaches_output(monkeypatch, capsys):
    with fresh_root_logging():
        _run_bot_main(monkeypatch)
        capsys.readouterr()
        _httpx_telegram_request()
        out = _emitted(capsys)
    assert FAKE_TOKEN not in out
    assert "HTTP Request" not in out                        # INFO request line is suppressed


def test_token_is_redacted_even_at_warning_error_and_in_tracebacks(monkeypatch, capsys):
    with fresh_root_logging():
        _run_bot_main(monkeypatch)
        capsys.readouterr()
        logging.getLogger("httpx").warning("HTTP Request: %s %s", "POST", httpx.URL(FAKE_URL))
        logging.getLogger("beta.bot").error("unexpected reply from " + FAKE_URL)
        try:
            raise RuntimeError(f"transport failed for {FAKE_URL}")
        except RuntimeError:
            logging.getLogger("telegram.ext.Updater").exception("Exception happened while polling for updates.")
        out = _emitted(capsys)
    assert FAKE_TOKEN not in out
    assert out.count("https://api.telegram.org/bot***/getUpdates") == 3   # %-arg, message, traceback


def test_control_previous_basicconfig_leaked_the_token(capsys):
    """Power check: the replaced direct basicConfig lets httpx's INFO line carry the token."""
    with fresh_root_logging():
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s",
                            stream=sys.stdout)
        _httpx_telegram_request()
        out = _emitted(capsys)
    assert "HTTP Request: POST" in out and FAKE_TOKEN in out
