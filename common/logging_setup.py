import logging
import re
import sys

# A Telegram Bot API URL embeds the COMPLETE bot token as a path segment,
# e.g. "https://api.telegram.org/bot123456:ABCDEF/sendMessage". Any log record
# containing one — from httpx/httpcore's own request logging, from
# python-telegram-bot's internal loggers, or from anywhere else — must never
# reach stdout/journald with the token intact.
_TELEGRAM_BOT_URL_RE = re.compile(r"(https://api\.telegram\.org/bot)([^/\s]+)")


def _redact_telegram_urls(text: str) -> str:
    return _TELEGRAM_BOT_URL_RE.sub(r"\1***", text)


class TelegramTokenRedactionFilter(logging.Filter):
    """Defense in depth, independent of
    `notifications.telegram_client.sanitize_telegram_error`: that function
    sanitizes an application-level error summary BEFORE it is logged/stored,
    while this filter is the LAST line of defense against a raw token
    reaching a stream through a third-party logger (httpx, httpcore,
    python-telegram-bot's own request/transport loggers) whose message format
    this codebase does not control. Attached to every root StreamHandler, it
    redacts a Telegram Bot API URL's token segment from a record's message,
    its %-formatting arguments, and any exception text — regardless of the
    record's logger name or severity."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact_telegram_urls(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _redact_arg(v) for k, v in record.args.items()}
            else:
                record.args = tuple(_redact_arg(a) for a in record.args)
        if record.exc_info:
            formatted = logging.Formatter().formatException(record.exc_info)
            record.exc_text = _redact_telegram_urls(formatted)
        return True


def _redact_arg(value):
    # Redact based on the object's string form (covers plain strings as well
    # as e.g. an `httpx.URL` object, which stringifies to the full URL), but
    # only replace the arg with a plain string when something was actually
    # redacted — an untouched non-string arg (e.g. an int status code) is
    # left as-is so %-style formatting (%d, etc.) still behaves correctly.
    text = str(value)
    redacted = _redact_telegram_urls(text)
    return redacted if redacted != text else value


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    # Quiet down noisy third-party loggers by default.
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    # httpx/httpcore (the transport used by python-telegram-bot's
    # HTTPXRequest) log the full request URL at INFO, and python-telegram-bot
    # itself namespaces all its internal loggers under "telegram"/"telegram.
    # ext" — a Telegram Bot API URL embeds the complete bot token, so all
    # three are quieted to WARNING to prevent a token from ever reaching
    # stdout/journald at the default --log-level INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    # Defense in depth: even a WARNING/ERROR record (from a third-party
    # logger or our own) has any Telegram Bot API URL's token segment
    # redacted before it reaches a stream, independent of logger name/level.
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and not any(
                isinstance(f, TelegramTokenRedactionFilter) for f in handler.filters):
            handler.addFilter(TelegramTokenRedactionFilter())
