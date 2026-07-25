"""Unit tests for the pure Telegram HTML formatter. No DB/network/clock access."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from notifications.telegram_formatter import (
    MAX_MESSAGE_LENGTH, MAX_REASONS, render_telegram_forecast_message,
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
# reason truncation
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
# overall length safety net + truncation never splits a tag/entity
# ============================================================================
def test_message_never_exceeds_max_length_plus_truncation_marker():
    reasons = tuple(f"a very long reason describing the signal in detail number {i} " * 3
                     for i in range(200))
    msg = render_telegram_forecast_message(_candidate(reasons=reasons))
    # bounded: either under the reasons cap (8) or under the hard safety net
    assert len(msg) <= MAX_MESSAGE_LENGTH + len("\n… (message truncated)") + 1


def test_truncation_never_splits_html_entity_or_tag():
    # force the hard safety-net truncation with an oversized single reason that
    # itself contains many escaped entities, so a naive char-cut would slice
    # straight through an "&amp;" or "&lt;...&gt;" sequence.
    huge_reason = ("<tag> & entities " * 500)
    msg = render_telegram_forecast_message(_candidate(reasons=(huge_reason,)))
    assert len(msg) <= MAX_MESSAGE_LENGTH + len("\n… (message truncated)") + 1
    # no dangling partial entity like "&am" or "&l" at the very end before the marker
    if "message truncated" in msg:
        body = msg.rsplit("\n… (message truncated)", 1)[0]
        assert not body.endswith("&")
        # never ends mid-entity (a truncated named/numeric reference)
        import re
        assert re.search(r"&[a-zA-Z#0-9]*$", body) is None or body.rstrip().endswith(";")


def test_truncation_visible_marker_present_when_triggered():
    huge_reason = "x" * 10000
    msg = render_telegram_forecast_message(_candidate(reasons=(huge_reason,)))
    assert "message truncated" in msg
