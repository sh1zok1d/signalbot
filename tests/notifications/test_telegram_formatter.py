"""Unit tests for the pure Telegram HTML formatter. No DB/network/clock access."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest

from notifications.telegram_formatter import (
    MAX_HORIZON_UNITS, MAX_MESSAGE_LENGTH, MAX_REASON_UNITS, MAX_REASONS,
    MAX_SYMBOL_UNITS, _utf16_len, render_telegram_forecast_message,
)
from notifications.telegram_models import NotificationCandidate, TelegramModelError

UTC = timezone.utc
B = datetime(2026, 3, 1, 12, 5, tzinfo=UTC)


def _candidate(**overrides):
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=B,
        calculation_version="c" * 16, rule_version="r1", direction="LONG",
        confidence=0.75, final_score=0.4, reference_price=64126.301,
        reference_price_source="binance_close_5m", horizon_set=("15m", "1h"),
        reasons=("strong momentum", "breakout confirmed"), exchanges_expected_max=3,
        min_coverage_ratio=1.0, data_confidence_overall=80.0,
        consensus_confidence=90.0, is_partial_consensus=False,
        prediction_created_at=B + timedelta(seconds=1))
    base.update(overrides)
    return NotificationCandidate(**base)


# ============================================================================
# basic template shape
# ============================================================================
def test_long_message_contains_green_emoji_and_symbol():
    msg = render_telegram_forecast_message(_candidate(direction="LONG"))
    assert "\U0001F7E2" in msg
    assert "BTCUSDT" in msg
    assert "LONG" in msg


def test_short_message_contains_red_emoji():
    msg = render_telegram_forecast_message(_candidate(direction="SHORT"))
    assert "\U0001F534" in msg
    assert "SHORT" in msg


def test_message_labels_shadow_forecast_not_trade():
    msg = render_telegram_forecast_message(_candidate())
    assert "shadow forecast" in msg
    low = msg.lower()
    for banned in ("buy now", "sell now", "order opened", "order placed",
                   "execute trade", "position opened"):
        assert banned not in low


def test_message_deterministic_for_same_candidate():
    c = _candidate()
    assert render_telegram_forecast_message(c) == render_telegram_forecast_message(c)


def test_message_contains_bucket_utc_timestamp():
    msg = render_telegram_forecast_message(_candidate())
    assert "2026-03-01 12:05 UTC" in msg


def test_message_contains_horizons():
    msg = render_telegram_forecast_message(_candidate(horizon_set=("15m", "1h", "4h")))
    assert "15m" in msg and "1h" in msg and "4h" in msg


def test_message_contains_data_quality_section():
    msg = render_telegram_forecast_message(_candidate())
    assert "Качество данных" in msg
    assert "Data confidence" in msg
    assert "Consensus confidence" in msg
    assert "Partial consensus" in msg


def test_message_omits_optional_confidence_lines_when_none():
    msg = render_telegram_forecast_message(
        _candidate(data_confidence_overall=None, consensus_confidence=None))
    assert "Data confidence" not in msg
    assert "Consensus confidence" not in msg
    assert "Partial consensus" in msg   # always present (bool, never None)


def test_message_reflects_partial_consensus_flag():
    msg_yes = render_telegram_forecast_message(_candidate(is_partial_consensus=True))
    msg_no = render_telegram_forecast_message(_candidate(is_partial_consensus=False))
    assert "Partial consensus: yes" in msg_yes
    assert "Partial consensus: no" in msg_no


def test_message_never_includes_consensus_snapshot_or_secrets():
    msg = render_telegram_forecast_message(_candidate())
    low = msg.lower()
    for banned in ("consensus_snapshot", "token", "bot_token", "dsn", "postgresql://"):
        assert banned not in low


def test_message_rejects_non_candidate_type():
    with pytest.raises(TelegramModelError):
        render_telegram_forecast_message({"direction": "LONG"})


def test_message_rejects_subclass_duck_typing():
    class Fake:
        direction = "LONG"
    with pytest.raises(TelegramModelError):
        render_telegram_forecast_message(Fake())


# ============================================================================
# HTML escaping / injection resistance
# ============================================================================
def test_html_special_chars_in_symbol_are_escaped():
    msg = render_telegram_forecast_message(_candidate(symbol="BTC<script>USDT"))
    assert "<script>" not in msg
    assert "&lt;script&gt;" in msg


def test_html_injection_in_reasons_is_escaped():
    msg = render_telegram_forecast_message(
        _candidate(reasons=("<b>bold injection</b>", "safe reason")))
    assert "<b>bold injection</b>" not in msg
    assert "&lt;b&gt;bold injection&lt;/b&gt;" in msg


def test_ampersand_in_reason_is_escaped():
    msg = render_telegram_forecast_message(_candidate(reasons=("A & B",)))
    assert "A &amp; B" in msg


def test_only_intentional_bold_tag_survives():
    msg = render_telegram_forecast_message(_candidate())
    # the direction is intentionally wrapped in <b>...</b> by the formatter itself
    assert "<b>LONG</b>" in msg
    # no OTHER raw angle bracket should appear outside that one intentional tag
    without_intentional = msg.replace("<b>LONG</b>", "")
    assert "<" not in without_intentional and ">" not in without_intentional


# ============================================================================
# reason truncation (count-based, MAX_REASONS)
# ============================================================================
def test_reasons_under_limit_all_kept():
    reasons = tuple(f"reason {i}" for i in range(MAX_REASONS))
    msg = render_telegram_forecast_message(_candidate(reasons=reasons))
    for r in reasons:
        assert r in msg
    assert "more)" not in msg


def test_reasons_over_limit_truncated_visibly():
    reasons = tuple(f"reason {i}" for i in range(MAX_REASONS + 12))
    msg = render_telegram_forecast_message(_candidate(reasons=reasons))
    for r in reasons[:MAX_REASONS]:
        assert r in msg
    for r in reasons[MAX_REASONS:]:
        assert r not in msg
    assert "(+12 more)" in msg


def test_no_reasons_shows_placeholder():
    msg = render_telegram_forecast_message(_candidate(reasons=()))
    assert "(none)" in msg


# ============================================================================
# UTF-16 code-unit measurement (not Python len / code points)
# ============================================================================
def test_utf16_len_matches_python_len_for_bmp_text():
    assert _utf16_len("hello") == 5
    assert _utf16_len("привет") == 6   # Cyrillic is BMP: 1 unit per char


def test_utf16_len_counts_astral_emoji_as_two_units():
    # U+1F600 GRINNING FACE is astral (outside the BMP): 2 UTF-16 units, 1 Python char
    emoji = "\U0001F600"
    assert len(emoji) == 1
    assert _utf16_len(emoji) == 2


def test_utf16_len_mixed_bmp_and_astral():
    text = "A" + "\U0001F600" + "B"
    assert len(text) == 3
    assert _utf16_len(text) == 4


# ============================================================================
# per-field bounding: oversized symbol / horizon / reason
# ============================================================================
def test_oversized_symbol_is_bounded_and_still_valid_html():
    huge_symbol = "X" * 5000
    msg = render_telegram_forecast_message(_candidate(symbol=huge_symbol))
    assert huge_symbol not in msg
    assert "…" in msg
    assert _utf16_len(msg) <= MAX_MESSAGE_LENGTH
    _assert_no_dangling_entity(msg)


def test_oversized_symbol_with_html_injection_stays_escaped_after_truncation():
    huge_symbol = "<script>" * 2000
    msg = render_telegram_forecast_message(_candidate(symbol=huge_symbol))
    assert "<script>" not in msg
    _assert_no_dangling_entity(msg)


def test_oversized_horizon_is_bounded_and_still_valid_html():
    huge_horizon = "h" * 5000
    msg = render_telegram_forecast_message(_candidate(horizon_set=(huge_horizon, "1h")))
    assert huge_horizon not in msg
    assert "1h" in msg
    assert _utf16_len(msg) <= MAX_MESSAGE_LENGTH
    _assert_no_dangling_entity(msg)


def test_oversized_single_reason_is_bounded_and_still_valid_html():
    huge_reason = "reason text " * 2000
    msg = render_telegram_forecast_message(_candidate(reasons=(huge_reason,)))
    assert huge_reason not in msg
    assert "…" in msg
    assert _utf16_len(msg) <= MAX_MESSAGE_LENGTH
    _assert_no_dangling_entity(msg)


def test_field_truncation_visible_marker_present():
    msg = render_telegram_forecast_message(_candidate(symbol="X" * 5000))
    assert "…" in msg   # per-field ellipsis marker


# ============================================================================
# repeated &, <, > and combinations with emoji
# ============================================================================
def test_repeated_ampersand_lt_gt_in_reason_stays_valid_after_truncation():
    huge_reason = "<tag> & <another> & " * 500
    msg = render_telegram_forecast_message(_candidate(reasons=(huge_reason,)))
    assert "<tag>" not in msg
    assert "<another>" not in msg
    _assert_no_dangling_entity(msg)
    assert _utf16_len(msg) <= MAX_MESSAGE_LENGTH


def test_thousands_of_astral_emoji_in_reason_bounded_correctly():
    huge_reason = "\U0001F600" * 5000   # thousands of 2-unit astral chars
    msg = render_telegram_forecast_message(_candidate(reasons=(huge_reason,)))
    assert _utf16_len(msg) <= MAX_MESSAGE_LENGTH
    # every kept emoji must be a complete code point (no lone surrogate),
    # otherwise re-encoding to utf-16 would raise
    msg.encode("utf-16-le")


def test_emoji_combined_with_escaped_entities_in_reason():
    huge_reason = ("\U0001F600<b>&amp;</b>" * 500)
    msg = render_telegram_forecast_message(_candidate(reasons=(huge_reason,)))
    assert "<b>" not in msg.replace("<b>LONG</b>", "")   # only the intentional tag survives
    _assert_no_dangling_entity(msg)
    assert _utf16_len(msg) <= MAX_MESSAGE_LENGTH
    msg.encode("utf-16-le")   # no lone surrogate


# ============================================================================
# overall length safety net + truncation never splits a tag/entity/surrogate
# ============================================================================
def _assert_no_dangling_entity(msg: str) -> None:
    # no dangling partial entity like "&am" or "&l" anywhere a cut could have
    # landed; every "&" must begin a COMPLETE, terminated entity reference.
    for m in re.finditer(r"&[a-zA-Z0-9#]*(;?)", msg):
        assert m.group(1) == ";", f"dangling entity fragment: {m.group(0)!r}"


def test_message_never_exceeds_configured_utf16_bound():
    reasons = tuple(f"a very long reason describing the signal in detail number {i} " * 3
                     for i in range(200))
    msg = render_telegram_forecast_message(_candidate(reasons=reasons))
    assert _utf16_len(msg) <= MAX_MESSAGE_LENGTH


def test_truncation_never_splits_html_entity_or_tag():
    huge_reason = ("<tag> & entities " * 500)
    msg = render_telegram_forecast_message(_candidate(reasons=(huge_reason,)))
    assert _utf16_len(msg) <= MAX_MESSAGE_LENGTH
    _assert_no_dangling_entity(msg)


def test_truncation_never_splits_surrogate_pair():
    # an oversized reason made ENTIRELY of astral characters: if truncation
    # cut by raw index/byte instead of code point, this would produce a lone
    # surrogate that fails to re-encode.
    huge_reason = "\U0001F602" * 4000
    msg = render_telegram_forecast_message(_candidate(reasons=(huge_reason,)))
    msg.encode("utf-16-le")   # raises if a lone surrogate is present


def test_truncation_visible_marker_present_when_triggered_via_field_bound():
    huge_reason = "x" * 10000
    msg = render_telegram_forecast_message(_candidate(reasons=(huge_reason,)))
    assert "…" in msg


def test_final_safety_net_truncation_marker_when_many_oversized_fields_combine():
    # push well past the per-field bounds on every dynamic field at once so the
    # final message-level safety net itself must engage.
    reasons = tuple("r" * MAX_REASON_UNITS * 2 for _ in range(MAX_REASONS))
    msg = render_telegram_forecast_message(_candidate(
        symbol="S" * 500, horizon_set=tuple(f"h{i}" * 100 for i in range(20)),
        reasons=reasons))
    assert _utf16_len(msg) <= MAX_MESSAGE_LENGTH
    _assert_no_dangling_entity(msg)


def test_balanced_intentional_bold_tag_survives_heavy_truncation():
    huge_reason = "z" * 100000
    msg = render_telegram_forecast_message(_candidate(reasons=(huge_reason,)))
    assert msg.count("<b>") == msg.count("</b>") == 1
    assert "<b>LONG</b>" in msg


def test_deterministic_output_for_oversized_fields():
    c = _candidate(symbol="X" * 5000, reasons=("y" * 5000,))
    assert render_telegram_forecast_message(c) == render_telegram_forecast_message(c)


def test_normal_message_unchanged_by_utf16_rework():
    msg = render_telegram_forecast_message(_candidate())
    assert msg == (
        "\U0001F7E2 BTCUSDT — <b>LONG</b>\n"
        "\n"
        "Режим: shadow forecast\n"
        "\n"
        "Цена: 64 126.30\n"
        "Уверенность: 75%\n"
        "Score: +0.400\n"
        "Bucket: 2026-03-01 12:05 UTC\n"
        "Горизонты: 15m / 1h\n"
        "\n"
        "Качество данных:\n"
        "Data confidence: 80%\n"
        "Consensus confidence: 90%\n"
        "Partial consensus: no\n"
        "\n"
        "Причины:\n"
        "• strong momentum\n"
        "• breakout confirmed"
    )
