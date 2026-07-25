"""
Pure, deterministic Telegram HTML message formatter for a shadow forecast
notification. No DB, environment, network, clock, logging, or filesystem — the
same `NotificationCandidate` always renders to the exact same string.

The message is explicitly labeled a SHADOW FORECAST, never an executed trade —
no "order opened" / "buy now" / "sell now" wording anywhere. The exact stored
`direction` is preserved verbatim; every dynamic value is HTML-escaped; the
`consensus_snapshot` and no secret/config value is ever included.

Telegram's hard sendMessage text limit is measured in UTF-16 code units (an
astral character, e.g. many emoji, costs 2 units — not 1 Python `str`
character), so every length check and truncation in this module operates on
UTF-16 units via `_utf16_len`, never Python's `len()`. Truncation always cuts
on a whole Unicode code-point boundary (never splitting a surrogate pair) and
never leaves a dangling partial HTML entity (e.g. "&amp" with no ";").
"""
from __future__ import annotations

import re
from html import escape

from .telegram_models import NotificationCandidate, TelegramModelError

# Telegram's hard sendMessage text limit is 4096 UTF-16 code units; stay well
# under it for a compact private-chat message and to leave margin for escaping.
MAX_MESSAGE_LENGTH = 3500
MAX_REASONS = 8

# Per-field bounds (UTF-16 code units) applied to escaped dynamic content
# BEFORE final assembly, so a single oversized symbol/horizon/reason can never
# blow out the whole message or force an unsafe final-stage cut.
MAX_SYMBOL_UNITS = 64
MAX_HORIZON_UNITS = 32
MAX_REASON_UNITS = 200

_FIELD_TRUNCATION_MARKER = "…"                    # "…" — 1 UTF-16 unit
_MESSAGE_TRUNCATION_MARKER = "\n… (message truncated)"

_DIRECTION_EMOJI = {"LONG": "\U0001F7E2", "SHORT": "\U0001F534"}   # green / red circle

_DANGLING_ENTITY_RE = re.compile(r"&[a-zA-Z0-9#]*$")


def _utf16_len(s: str) -> int:
    """Exact Telegram-relevant length: UTF-16 code units, never Python code
    points. An astral character (many emoji, e.g. U+1F600) costs 2 units."""
    return len(s.encode("utf-16-le")) // 2


def _esc(value) -> str:
    return escape(str(value), quote=False)


def _truncate_escaped(escaped: str, max_units: int) -> str:
    """Truncate an ALREADY-ESCAPED string to at most `max_units` UTF-16 code
    units. Iterates by Python code point (never by UTF-16 unit or byte), so a
    surrogate pair / astral character is always kept or dropped whole, never
    split. If the cut lands mid-entity (e.g. "&amp" or "&#12" with no
    terminating ";"), the partial entity is stripped so no dangling reference
    is ever emitted. Appends no marker — callers add their own with a
    pre-reserved budget via `_truncate_with_marker`."""
    if _utf16_len(escaped) <= max_units:
        return escaped
    out = []
    used = 0
    for ch in escaped:
        cost = 2 if ord(ch) > 0xFFFF else 1
        if used + cost > max_units:
            break
        out.append(ch)
        used += cost
    result = "".join(out)
    match = _DANGLING_ENTITY_RE.search(result)
    if match:
        result = result[:match.start()]
    return result


def _truncate_with_marker(escaped: str, max_units: int, marker: str) -> str:
    """`_truncate_escaped`, but only when truncation is actually needed, and
    with the marker's own UTF-16 cost reserved from the budget so the result
    (body + marker) never exceeds `max_units`."""
    if _utf16_len(escaped) <= max_units:
        return escaped
    budget = max(0, max_units - _utf16_len(marker))
    return _truncate_escaped(escaped, budget) + marker


def _fmt_price(value: float) -> str:
    # Deterministic thousands-separated 2dp formatting, e.g. 64126.301 -> "64 126.30".
    return f"{value:,.2f}".replace(",", " ")


def _fmt_pct(value: float) -> str:
    return f"{round(value * 100):d}%"


def _fmt_signed_score(value: float) -> str:
    return f"{value:+.3f}"


def _fmt_bucket(candidate: NotificationCandidate) -> str:
    return candidate.bucket_ts.strftime("%Y-%m-%d %H:%M UTC")


def _fmt_symbol(symbol: str) -> str:
    return _truncate_with_marker(_esc(symbol), MAX_SYMBOL_UNITS, _FIELD_TRUNCATION_MARKER)


def _fmt_horizons(horizon_set) -> str:
    parts = [_truncate_with_marker(_esc(h), MAX_HORIZON_UNITS, _FIELD_TRUNCATION_MARKER)
             for h in horizon_set]
    return " / ".join(parts)


def _fmt_reason(reason: str) -> str:
    return _truncate_with_marker(_esc(reason), MAX_REASON_UNITS, _FIELD_TRUNCATION_MARKER)


def _truncate_reasons(reasons: tuple) -> tuple:
    """Deterministic truncation: keep at most MAX_REASONS entries; if any were
    dropped, make the truncation VISIBLE with a trailing marker (never silently
    cut mid-entry)."""
    if len(reasons) <= MAX_REASONS:
        return reasons
    kept = reasons[:MAX_REASONS]
    return kept + (f"... (+{len(reasons) - MAX_REASONS} more)",)


def _final_truncate(text: str, max_units: int) -> str:
    """Last-resort safety net over the fully assembled message (per-field
    bounding above should already keep messages compact). UTF-16-unit-safe and
    entity-safe like `_truncate_escaped`; additionally prefers cutting on a
    whole-line boundary for readability when one is available within budget."""
    if _utf16_len(text) <= max_units:
        return text
    budget = max(0, max_units - _utf16_len(_MESSAGE_TRUNCATION_MARKER))
    cut = _truncate_escaped(text, budget)
    newline_idx = cut.rfind("\n")
    if newline_idx > 0:
        cut = cut[:newline_idx]
    return cut + _MESSAGE_TRUNCATION_MARKER


def render_telegram_forecast_message(candidate: NotificationCandidate) -> str:
    """Pure HTML render. Raises TelegramModelError if `candidate` is not exactly
    a NotificationCandidate (never duck-typed)."""
    if type(candidate) is not NotificationCandidate:
        raise TelegramModelError(
            f"candidate must be exactly NotificationCandidate, got {type(candidate).__name__}")

    emoji = _DIRECTION_EMOJI[candidate.direction]
    reasons = _truncate_reasons(candidate.reasons)
    reason_lines = "\n".join(f"• {_fmt_reason(r)}" for r in reasons) if reasons else "• (none)"
    partial = "yes" if candidate.is_partial_consensus else "no"

    lines = [
        f"{emoji} {_fmt_symbol(candidate.symbol)} — <b>{_esc(candidate.direction)}</b>",
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
    return _final_truncate(text, MAX_MESSAGE_LENGTH)
