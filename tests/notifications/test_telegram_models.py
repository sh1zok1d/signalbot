"""Unit tests for the pure Telegram notification models: fingerprint, retry
backoff, and NotificationCandidate validation. No DB/network/clock/filesystem
access anywhere in this test file."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from notifications.telegram_models import (
    ACTIONABLE_DIRECTIONS, RETRY_BASE_SECONDS, RETRY_MAX_SECONDS,
    NotificationCandidate, TelegramModelError, compute_recipient_fingerprint,
    compute_retry_delay,
)

UTC = timezone.utc
B = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _kwargs(**overrides):
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="5m", bucket_ts=B,
        calculation_version="c" * 16, rule_version="r1", direction="LONG",
        confidence=0.75, final_score=0.4, reference_price=65000.0,
        reference_price_source="binance_close_5m", horizon_set=("15m", "1h"),
        reasons=("strong momentum",), exchanges_expected_max=3,
        min_coverage_ratio=1.0, data_confidence_overall=80.0,
        consensus_confidence=80.0, is_partial_consensus=False,
        prediction_created_at=B + timedelta(seconds=1))
    base.update(overrides)
    return base


# ============================================================================
# recipient fingerprint
# ============================================================================
def test_fingerprint_deterministic():
    a = compute_recipient_fingerprint("12345")
    b = compute_recipient_fingerprint("12345")
    assert a == b


def test_fingerprint_is_sha256_hex_of_chat_id():
    import hashlib
    expected = hashlib.sha256("12345".encode("utf-8")).hexdigest()
    assert compute_recipient_fingerprint("12345") == expected


def test_fingerprint_differs_for_different_chat_ids():
    assert compute_recipient_fingerprint("12345") != compute_recipient_fingerprint("54321")


def test_fingerprint_is_64_lowercase_hex_chars():
    fp = compute_recipient_fingerprint("999999999")
    assert len(fp) == 64
    assert fp == fp.lower()
    int(fp, 16)   # must parse as hex


def test_fingerprint_never_equals_raw_chat_id():
    assert compute_recipient_fingerprint("12345") != "12345"


@pytest.mark.parametrize("bad", ["", "   ", None, 12345, b"12345"])
def test_fingerprint_rejects_blank_or_non_string(bad):
    with pytest.raises(TelegramModelError):
        compute_recipient_fingerprint(bad)


def test_fingerprint_strips_whitespace_deterministically():
    assert compute_recipient_fingerprint("12345") == compute_recipient_fingerprint("12345 ".strip())


# ============================================================================
# retry / backoff
# ============================================================================
def test_retry_delay_attempt_one_is_base():
    assert compute_retry_delay(1) == RETRY_BASE_SECONDS


def test_retry_delay_doubles_per_attempt():
    assert compute_retry_delay(2) == RETRY_BASE_SECONDS * 2
    assert compute_retry_delay(3) == RETRY_BASE_SECONDS * 4
    assert compute_retry_delay(4) == RETRY_BASE_SECONDS * 8


def test_retry_delay_caps_at_max():
    assert compute_retry_delay(20) == RETRY_MAX_SECONDS
    assert compute_retry_delay(1000) == RETRY_MAX_SECONDS


def test_retry_delay_overflow_safe_no_exception():
    # a huge attempt_count must not raise OverflowError / hang
    assert compute_retry_delay(10 ** 9) == RETRY_MAX_SECONDS


def test_retry_delay_monotonic_nondecreasing():
    prev = 0
    for attempt in range(1, 40):
        d = compute_retry_delay(attempt)
        assert d >= prev
        prev = d


@pytest.mark.parametrize("bad", [0, -1, 1.5, True, "1", None])
def test_retry_delay_rejects_invalid_attempt_count(bad):
    with pytest.raises(TelegramModelError):
        compute_retry_delay(bad)


def test_retry_delay_respects_retry_after_when_larger():
    # attempt 1 base delay is 60s; a RetryAfter of 90s must win
    assert compute_retry_delay(1, retry_after=90) == 90


def test_retry_delay_retry_after_smaller_than_base_is_ignored():
    # attempt 1 base delay 60s already exceeds a tiny retry_after
    assert compute_retry_delay(1, retry_after=5) == RETRY_BASE_SECONDS


def test_retry_delay_retry_after_capped_at_max():
    assert compute_retry_delay(1, retry_after=999999) == RETRY_MAX_SECONDS


def test_retry_delay_retry_after_fractional_rounds_up():
    assert compute_retry_delay(1, retry_after=60.1) == 61


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), "30", True])
def test_retry_delay_rejects_invalid_retry_after(bad):
    with pytest.raises(TelegramModelError):
        compute_retry_delay(1, retry_after=bad)


def test_retry_delay_no_randomness_same_input_same_output():
    results = {compute_retry_delay(5, retry_after=10) for _ in range(20)}
    assert len(results) == 1


# ============================================================================
# NotificationCandidate
# ============================================================================
def test_candidate_constructs_with_valid_long():
    c = NotificationCandidate(**_kwargs(direction="LONG"))
    assert c.direction == "LONG"


def test_candidate_constructs_with_valid_short():
    c = NotificationCandidate(**_kwargs(direction="SHORT"))
    assert c.direction == "SHORT"


def test_candidate_rejects_neutral():
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(direction="NEUTRAL"))


def test_candidate_rejects_unknown_direction():
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(direction="SIDEWAYS"))


def test_candidate_is_frozen():
    c = NotificationCandidate(**_kwargs())
    with pytest.raises(Exception):
        c.direction = "SHORT"


@pytest.mark.parametrize("field", ["symbol", "market_type", "timeframe",
                                   "calculation_version", "rule_version",
                                   "reference_price_source"])
def test_candidate_rejects_blank_strings(field):
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(**{field: ""}))


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf"), "0.5", True])
def test_candidate_rejects_bad_confidence(value):
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(confidence=value))


@pytest.mark.parametrize("value", [-1.1, 1.1, float("nan")])
def test_candidate_rejects_bad_final_score(value):
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(final_score=value))


@pytest.mark.parametrize("value", [0, -1.0, float("nan"), float("inf")])
def test_candidate_rejects_bad_reference_price(value):
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(reference_price=value))


def test_candidate_rejects_empty_horizon_set():
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(horizon_set=()))


def test_candidate_rejects_non_string_horizon_items():
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(horizon_set=(15, "1h")))


def test_candidate_accepts_empty_reasons():
    c = NotificationCandidate(**_kwargs(reasons=()))
    assert c.reasons == ()


def test_candidate_rejects_non_string_reason_items():
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(reasons=(1, 2)))


def test_candidate_reasons_and_horizons_detached_to_tuple():
    c = NotificationCandidate(**_kwargs(horizon_set=["15m", "1h"], reasons=["a", "b"]))
    assert isinstance(c.horizon_set, tuple)
    assert isinstance(c.reasons, tuple)


@pytest.mark.parametrize("value", [0, -1, 1.5, True, "3"])
def test_candidate_rejects_bad_exchanges_expected_max(value):
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(exchanges_expected_max=value))


def test_candidate_accepts_none_optional_fields():
    c = NotificationCandidate(**_kwargs(
        min_coverage_ratio=None, data_confidence_overall=None, consensus_confidence=None))
    assert c.min_coverage_ratio is None
    assert c.data_confidence_overall is None
    assert c.consensus_confidence is None


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_candidate_rejects_bad_min_coverage_ratio(value):
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(min_coverage_ratio=value))


@pytest.mark.parametrize("value", [-1, 101])
def test_candidate_rejects_bad_data_confidence_overall(value):
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(data_confidence_overall=value))


def test_candidate_rejects_non_bool_is_partial_consensus():
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(is_partial_consensus=1))


def test_candidate_rejects_naive_bucket_ts():
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(bucket_ts=datetime(2026, 3, 1, 12, 0)))


def test_candidate_rejects_non_utc_bucket_ts():
    tz = timezone(timedelta(hours=3))
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(bucket_ts=datetime(2026, 3, 1, 12, 0, tzinfo=tz)))


def test_candidate_rejects_naive_prediction_created_at():
    with pytest.raises(TelegramModelError):
        NotificationCandidate(**_kwargs(prediction_created_at=datetime(2026, 3, 1, 12, 0)))


def test_candidate_has_no_consensus_snapshot_field():
    c = NotificationCandidate(**_kwargs())
    assert not hasattr(c, "consensus_snapshot")


def test_candidate_has_no_config_hash_or_code_version_field():
    c = NotificationCandidate(**_kwargs())
    assert not hasattr(c, "config_hash")
    assert not hasattr(c, "code_version")


def test_actionable_directions_excludes_neutral():
    assert "NEUTRAL" not in ACTIONABLE_DIRECTIONS
    assert set(ACTIONABLE_DIRECTIONS) == {"LONG", "SHORT"}
