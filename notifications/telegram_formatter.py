"""
Pure, deterministic Telegram HTML message formatter for a shadow forecast
notification. No DB, environment, network, clock, logging, or filesystem — the
same `NotificationCandidate` always renders to the exact same string.

The message is explicitly labeled a SHADOW FORECAST, never an executed trade —
no "order opened" / "buy now" / "sell now" wording anywhere. The exact stored
`direction` is preserved verbatim; every dynamic value is HTML-escaped; the
`consensus_snapshot` and no secret/config value is ever included.
"""
from __future__ import annotations

from html import escape

from .telegram_models import NotificationCandidate, TelegramModelError

# Telegram's hard sendMessage text limit is 4096 UTF-16 code units; stay well
# under it for a compact private-chat message and to leave margin for escaping.
MAX_MESSAGE_LENGTH = 3500
MAX_REASONS = 8

_DIRECTION_EMOJI = {"LONG": "\U0001F7E2", "SHORT": "\U0001F534"}   # green / red circle


def _esc(value: str) -> str:
    return escape(str(value), quote=False)


def _fmt_price(value: float) -> str:
    # Deterministic thousands-separated 2dp formatting, e.g. 64126.301 -> "64 126.30".
    return f"{value:,.2f}".replace(",", " ")


def _fmt_pct(value: float) -> str:
    return f"{round(value * 100):d}%"


def _fmt_signed_score(value: float) -> str:
    return f"{value:+.3f}"


def _fmt_bucket(candidate: NotificationCandidate) -> str:
    return candidate.bucket_ts.strftime("%Y-%m-%d %H:%M UTC")


def _fmt_horizons(horizon_set) -> str:
    return " / ".join(_esc(h) for h in horizon_set)


def _truncate_reasons(reasons: tuple) -> tuple:
    """Deterministic truncation: keep at most MAX_REASONS entries; if any were
    dropped, make the truncation VISIBLE with a trailing marker (never silently
    cut mid-entry, so no HTML tag/entity is ever split)."""
    if len(reasons) <= MAX_REASONS:
        return reasons
    kept = reasons[:MAX_REASONS]
    return kept + (f"... (+{len(reasons) - MAX_REASONS} more)",)


def render_telegram_forecast_message(candidate: NotificationCandidate) -> str:
    """Pure HTML render. Raises TelegramModelError if `candidate` is not exactly
    a NotificationCandidate (never duck-typed)."""
    if type(candidate) is not NotificationCandidate:
        raise TelegramModelError(
            f"candidate must be exactly NotificationCandidate, got {type(candidate).__name__}")

    emoji = _DIRECTION_EMOJI[candidate.direction]
    reasons = _truncate_reasons(candidate.reasons)
    reason_lines = "\n".join(f"• {_esc(r)}" for r in reasons) if reasons else "• (none)"
    partial = "yes" if candidate.is_partial_consensus else "no"

    lines = [
        f"{emoji} {_esc(candidate.symbol)} — <b>{_esc(candidate.direction)}</b>",
        "",
        "Режим: shadow forecast",
        "",
        f"Цена: {_esc(_fmt_price(candidate.reference_price))}",
        f"Уверенность: {_fmt_pct(candidate.confidence)}",
        f"Score: {_fmt_signed_score(candidate.final_score)}",
        f"Bucket: {_fmt_bucket(candidate)}",
        f"Горизонты: {_fmt_horizons(candidate.horizon_set)}",
        "",
        "Качество данных:",
    ]
    if candidate.data_confidence_overall is not None:
        lines.append(f"Data confidence: {_fmt_pct(candidate.data_confidence_overall / 100.0)}")
    if candidate.consensus_confidence is not None:
        lines.append(f"Consensus confidence: {_fmt_pct(candidate.consensus_confidence / 100.0)}")
    lines.append(f"Partial consensus: {partial}")
    lines.append("")
    lines.append("Причины:")
    lines.append(reason_lines)

    text = "\n".join(lines)
    if len(text) > MAX_MESSAGE_LENGTH:
        # Deterministic bounded truncation as a last-resort safety net (reason
        # truncation above should already keep messages compact): cut on a
        # whole-line boundary so no HTML tag/entity is ever split mid-token.
        cut = text[:MAX_MESSAGE_LENGTH]
        newline_idx = cut.rfind("\n")
        if newline_idx > 0:
            cut = cut[:newline_idx]
        text = cut + "\n… (message truncated)"
    return text
