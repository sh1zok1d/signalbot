"""Tests for analytics/forecasting_v2/context_evidence.py (Stage 4 —
Context Engines, PR 1 of ~3). No DB, no async — pure math over
hand-constructed `V2TimeframeInputs` fixtures, following the existing V2
analytics test style (tests/analytics/test_forecasting_v2_aligned_inputs.py).

Exercises the shared evidence vocabulary's central contract: exact
`(metric, percentile_window)` lookup with no cross-window fallback; the
corrected signed `normalized_evidence` primitive (raw-value sign chooses
sign, percentile rank chooses magnitude only — a positive raw value can
never produce bearish evidence and vice versa); the unsigned
`compression_score` companion (`1.0 - percentile_rank`, no signed math);
the corrected one-sided `oi_confirmation` primitive (never
`abs(rank-0.5)`, never a direction parameter); `MIN_PCTL_TIER="building"`
tier-floor semantics; and the missing-vs-malformed distinction (`None`
for legitimate absence, `V2ContextEvidenceError` for corrupted input).
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2 import context_evidence as ce_module
from analytics.forecasting_v2.aligned_inputs import V2TimeframeInputs
from analytics.forecasting_v2.context_evidence import (
    MIN_PCTL_TIER,
    V2ContextEvidenceError,
    compression_score,
    find_consensus_percentile,
    normalized_evidence,
    oi_confirmation,
)

UTC = timezone.utc
B = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
H16 = "a" * 16


# ============================================================================
# fixtures
# ============================================================================
def make_percentile_row(**over):
    base = dict(
        scope="consensus", exchange="", symbol="BTCUSDT", market_type="perp",
        metric="price_move_pct_median", timeframe="4h", percentile_window="30d",
        bucket_ts=B, value=0.1, percentile_rank=0.9, sample_size=100,
        sample_window_start=B - timedelta(days=30), sample_window_end=B - timedelta(minutes=5),
        confidence_tier="mature", feature_schema_version=1, calculation_version=H16,
    )
    base.update(over)
    return base


def make_consensus(**over):
    base = dict(
        symbol="BTCUSDT", market_type="perp", timeframe="4h", bucket_ts=B,
        price_move_pct_median=0.1, oi_change_pct_median=0.1,
        oi_direction_agreement=0.75, price_direction_agreement=0.8,
        consensus_confidence=87.5, min_coverage_ratio=1.0,
    )
    base.update(over)
    return base


def make_inputs(*, percentiles=(), consensus=None, timeframe="4h", bucket_ts=B):
    return V2TimeframeInputs(
        timeframe=timeframe, bucket_ts=bucket_ts, bucket_end=bucket_ts + timedelta(hours=4),
        consensus=consensus, percentiles=tuple(percentiles), health={},
        reference_feature=None, reference_klines=None, reference_extrema=None,
    )


# ============================================================================
# 1. EXACT LOOKUP
# ============================================================================
def test_lookup_returns_exact_matching_row():
    row = make_percentile_row(metric="price_move_pct_median", percentile_window="30d")
    inputs = make_inputs(percentiles=[row])
    result = find_consensus_percentile(inputs, metric="price_move_pct_median", percentile_window="30d")
    assert result is row


def test_lookup_no_cross_window_fallback_30d_missing():
    row_7d = make_percentile_row(metric="price_move_pct_median", percentile_window="7d")
    inputs = make_inputs(percentiles=[row_7d])
    result = find_consensus_percentile(inputs, metric="price_move_pct_median", percentile_window="30d")
    assert result is None


def test_lookup_no_cross_window_fallback_7d_missing():
    row_30d = make_percentile_row(metric="price_move_pct_median", percentile_window="30d")
    inputs = make_inputs(percentiles=[row_30d])
    result = find_consensus_percentile(inputs, metric="price_move_pct_median", percentile_window="7d")
    assert result is None


def test_lookup_missing_pair_returns_none():
    inputs = make_inputs(percentiles=[])
    assert find_consensus_percentile(inputs, metric="oi_change_pct_median", percentile_window="30d") is None


def test_lookup_disambiguates_multiple_metrics_and_windows():
    rows = [
        make_percentile_row(metric="price_move_pct_median", percentile_window="7d", value=1.0),
        make_percentile_row(metric="price_move_pct_median", percentile_window="30d", value=2.0),
        make_percentile_row(metric="oi_change_pct_median", percentile_window="30d", value=3.0),
        make_percentile_row(metric="range_width_pct_median", percentile_window="30d", value=4.0),
    ]
    inputs = make_inputs(percentiles=rows)
    assert find_consensus_percentile(
        inputs, metric="price_move_pct_median", percentile_window="7d")["value"] == 1.0
    assert find_consensus_percentile(
        inputs, metric="price_move_pct_median", percentile_window="30d")["value"] == 2.0
    assert find_consensus_percentile(
        inputs, metric="oi_change_pct_median", percentile_window="30d")["value"] == 3.0
    assert find_consensus_percentile(
        inputs, metric="range_width_pct_median", percentile_window="30d")["value"] == 4.0


def test_lookup_duplicate_exact_pair_raises():
    row = make_percentile_row(metric="price_move_pct_median", percentile_window="30d")
    inputs = make_inputs(percentiles=[row, dict(row)])
    with pytest.raises(V2ContextEvidenceError, match="expected at most one"):
        find_consensus_percentile(inputs, metric="price_move_pct_median", percentile_window="30d")


def test_lookup_wrong_scope_raises():
    row = make_percentile_row(scope="exchange")
    inputs = make_inputs(percentiles=[row])
    with pytest.raises(V2ContextEvidenceError, match="scope"):
        find_consensus_percentile(inputs, metric="price_move_pct_median", percentile_window="30d")


def test_lookup_nonblank_exchange_raises():
    row = make_percentile_row(exchange="binance")
    inputs = make_inputs(percentiles=[row])
    with pytest.raises(V2ContextEvidenceError, match="exchange"):
        find_consensus_percentile(inputs, metric="price_move_pct_median", percentile_window="30d")


def test_lookup_wrong_timeframe_raises():
    row = make_percentile_row(timeframe="1h")  # inputs.timeframe defaults to "4h"
    inputs = make_inputs(percentiles=[row])
    with pytest.raises(V2ContextEvidenceError, match="timeframe"):
        find_consensus_percentile(inputs, metric="price_move_pct_median", percentile_window="30d")


def test_lookup_wrong_bucket_ts_raises():
    row = make_percentile_row(bucket_ts=B - timedelta(hours=4))
    inputs = make_inputs(percentiles=[row])
    with pytest.raises(V2ContextEvidenceError, match="bucket_ts"):
        find_consensus_percentile(inputs, metric="price_move_pct_median", percentile_window="30d")


def test_lookup_lookahead_equal_sample_window_end_raises():
    row = make_percentile_row(sample_window_end=B)  # == bucket_ts, forbidden
    inputs = make_inputs(percentiles=[row])
    with pytest.raises(V2ContextEvidenceError, match="no-lookahead"):
        find_consensus_percentile(inputs, metric="price_move_pct_median", percentile_window="30d")


def test_lookup_lookahead_after_sample_window_end_raises():
    row = make_percentile_row(sample_window_end=B + timedelta(minutes=1))
    inputs = make_inputs(percentiles=[row])
    with pytest.raises(V2ContextEvidenceError, match="no-lookahead"):
        find_consensus_percentile(inputs, metric="price_move_pct_median", percentile_window="30d")


def test_lookup_none_sample_window_end_is_fine():
    row = make_percentile_row(sample_window_end=None)
    inputs = make_inputs(percentiles=[row])
    assert find_consensus_percentile(
        inputs, metric="price_move_pct_median", percentile_window="30d") is row


def test_lookup_malformed_sample_window_end_type_raises_domain_error():
    row = make_percentile_row(sample_window_end="not-a-datetime")
    inputs = make_inputs(percentiles=[row])
    with pytest.raises(V2ContextEvidenceError, match="cannot be compared"):
        find_consensus_percentile(inputs, metric="price_move_pct_median", percentile_window="30d")


@pytest.mark.parametrize("bad_metric", ["", "not_a_metric", None, 5, "price_move_pct"])
def test_lookup_rejects_invalid_metric(bad_metric):
    inputs = make_inputs(percentiles=[])
    with pytest.raises(V2ContextEvidenceError, match="metric"):
        find_consensus_percentile(inputs, metric=bad_metric, percentile_window="30d")


@pytest.mark.parametrize("bad_window", ["", "1d", "90d", None, 5, "7D", "30D"])
def test_lookup_rejects_invalid_window(bad_window):
    inputs = make_inputs(percentiles=[])
    with pytest.raises(V2ContextEvidenceError, match="percentile_window"):
        find_consensus_percentile(inputs, metric="price_move_pct_median", percentile_window=bad_window)


# ============================================================================
# 2. NORMALIZED EVIDENCE — frozen vectors (§4.1)
# ============================================================================
@pytest.mark.parametrize("v,p,expected", [
    (1.0, 1.0, 1.0),
    (1.0, 0.90, 0.80),
    (1.0, 0.50, 0.0),
    (1.0, 0.10, 0.0),        # NOT -0.80
    (-1.0, 0.0, -1.0),
    (-1.0, 0.10, -0.80),
    (-1.0, 0.50, 0.0),
    (-1.0, 0.90, 0.0),       # NOT +0.80
    (0.0, 0.10, 0.0),
    (0.0, 0.50, 0.0),
    (0.0, 0.90, 0.0),
])
def test_normalized_evidence_frozen_vectors(v, p, expected):
    row = make_percentile_row(value=v, percentile_rank=p)
    inputs = make_inputs(percentiles=[row])
    result = normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d")
    assert result == pytest.approx(expected)


@pytest.mark.parametrize("p", [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])
def test_normalized_evidence_sign_invariant_positive_raw_never_negative(p):
    row = make_percentile_row(value=1.0, percentile_rank=p)
    inputs = make_inputs(percentiles=[row])
    result = normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d")
    assert result >= 0.0


@pytest.mark.parametrize("p", [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])
def test_normalized_evidence_sign_invariant_negative_raw_never_positive(p):
    row = make_percentile_row(value=-1.0, percentile_rank=p)
    inputs = make_inputs(percentiles=[row])
    result = normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d")
    assert result <= 0.0


@pytest.mark.parametrize("p", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_normalized_evidence_zero_raw_is_always_exactly_zero(p):
    row = make_percentile_row(value=0.0, percentile_rank=p)
    inputs = make_inputs(percentiles=[row])
    result = normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d")
    assert result == 0.0


def test_normalized_evidence_regression_never_unconditional_2p_minus_1():
    # The explicit forbidden-form regression: a positive raw value with a
    # LOW percentile rank must be 0.0, never negative (which unconditional
    # 2*p-1 would produce: 2*0.10-1 = -0.80).
    row = make_percentile_row(value=0.10, percentile_rank=0.10)
    inputs = make_inputs(percentiles=[row])
    result = normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d")
    assert result == 0.0


def test_normalized_evidence_rejects_compression_metric():
    inputs = make_inputs(percentiles=[])
    with pytest.raises(V2ContextEvidenceError, match="compression_score"):
        normalized_evidence(inputs, metric="range_width_pct_median", percentile_window="30d")


# ---- unavailable/tier ----
def test_normalized_evidence_missing_snapshot_is_none():
    inputs = make_inputs(percentiles=[])
    assert normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d") is None


def test_normalized_evidence_none_value_is_none():
    row = make_percentile_row(value=None)
    inputs = make_inputs(percentiles=[row])
    assert normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d") is None


def test_normalized_evidence_none_rank_is_none():
    row = make_percentile_row(percentile_rank=None)
    inputs = make_inputs(percentiles=[row])
    assert normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d") is None


@pytest.mark.parametrize("tier", ["none", "low"])
def test_normalized_evidence_low_tier_is_none(tier):
    row = make_percentile_row(confidence_tier=tier)
    inputs = make_inputs(percentiles=[row])
    assert normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d") is None


@pytest.mark.parametrize("tier", ["building", "mature"])
def test_normalized_evidence_usable_tier_computes(tier):
    row = make_percentile_row(confidence_tier=tier, value=1.0, percentile_rank=0.9)
    inputs = make_inputs(percentiles=[row])
    assert normalized_evidence(
        inputs, metric="price_move_pct_median", percentile_window="30d") == pytest.approx(0.8)


def test_normalized_evidence_unknown_tier_raises():
    row = make_percentile_row(confidence_tier="legendary")
    inputs = make_inputs(percentiles=[row])
    with pytest.raises(V2ContextEvidenceError, match="unknown confidence_tier"):
        normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d")


# ---- numeric corruption ----
@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf"), True, "1"])
def test_normalized_evidence_malformed_value_raises(bad_value):
    row = make_percentile_row(value=bad_value)
    inputs = make_inputs(percentiles=[row])
    with pytest.raises(V2ContextEvidenceError):
        normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d")


@pytest.mark.parametrize("bad_rank", [-0.01, 1.01, float("nan"), float("inf"), True, "0.9"])
def test_normalized_evidence_malformed_rank_raises(bad_rank):
    row = make_percentile_row(percentile_rank=bad_rank)
    inputs = make_inputs(percentiles=[row])
    with pytest.raises(V2ContextEvidenceError):
        normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d")


def test_normalized_evidence_rank_not_clamped():
    row = make_percentile_row(percentile_rank=1.01)
    inputs = make_inputs(percentiles=[row])
    with pytest.raises(V2ContextEvidenceError, match=r"\[0\.0, 1\.0\]"):
        normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d")


# ============================================================================
# 3. COMPRESSION SCORE — §4.1 unsigned companion
# ============================================================================
@pytest.mark.parametrize("p,expected", [
    (0.00, 1.00), (0.10, 0.90), (0.50, 0.50), (0.90, 0.10), (1.00, 0.00),
])
def test_compression_score_frozen_vectors(p, expected):
    row = make_percentile_row(metric="range_width_pct_median", value=2.0, percentile_rank=p)
    inputs = make_inputs(percentiles=[row])
    result = compression_score(inputs, percentile_window="30d")
    assert result == pytest.approx(expected)


def test_compression_score_uses_range_width_pct_median_exactly():
    wrong_metric_row = make_percentile_row(metric="price_move_pct_median", percentile_rank=0.1)
    inputs = make_inputs(percentiles=[wrong_metric_row])
    assert compression_score(inputs, percentile_window="30d") is None


def test_compression_score_missing_snapshot_is_none():
    inputs = make_inputs(percentiles=[])
    assert compression_score(inputs, percentile_window="30d") is None


def test_compression_score_none_value_is_none():
    row = make_percentile_row(metric="range_width_pct_median", value=None)
    inputs = make_inputs(percentiles=[row])
    assert compression_score(inputs, percentile_window="30d") is None


def test_compression_score_none_rank_is_none():
    row = make_percentile_row(metric="range_width_pct_median", percentile_rank=None)
    inputs = make_inputs(percentiles=[row])
    assert compression_score(inputs, percentile_window="30d") is None


@pytest.mark.parametrize("tier", ["none", "low"])
def test_compression_score_low_tier_is_none(tier):
    row = make_percentile_row(metric="range_width_pct_median", confidence_tier=tier)
    inputs = make_inputs(percentiles=[row])
    assert compression_score(inputs, percentile_window="30d") is None


def test_compression_score_negative_range_width_raises():
    row = make_percentile_row(metric="range_width_pct_median", value=-1.0, percentile_rank=0.5)
    inputs = make_inputs(percentiles=[row])
    with pytest.raises(V2ContextEvidenceError, match=">= 0"):
        compression_score(inputs, percentile_window="30d")


def test_compression_score_never_negative_and_never_above_one():
    for p in (0.0, 0.25, 0.5, 0.75, 1.0):
        row = make_percentile_row(metric="range_width_pct_median", value=1.0, percentile_rank=p)
        inputs = make_inputs(percentiles=[row])
        result = compression_score(inputs, percentile_window="30d")
        assert 0.0 <= result <= 1.0


# ============================================================================
# 4. OI CONFIRMATION — §4.2, one-sided tail distance
# ============================================================================
@pytest.mark.parametrize("oi_raw,rank,agreement,expected", [
    (0.10, 0.90, 0.75, 0.60),
    (0.10, 0.10, 0.75, 0.0),
    (-0.10, 0.10, 0.75, -0.60),
    (-0.10, 0.90, 0.75, 0.0),
])
def test_oi_confirmation_frozen_vectors(oi_raw, rank, agreement, expected):
    consensus = make_consensus(oi_change_pct_median=oi_raw, oi_direction_agreement=agreement)
    row = make_percentile_row(metric="oi_change_pct_median", value=oi_raw, percentile_rank=rank)
    inputs = make_inputs(percentiles=[row], consensus=consensus)
    result = oi_confirmation(inputs, percentile_window="30d")
    assert result == pytest.approx(expected)


def test_oi_confirmation_zero_raw_is_zero():
    consensus = make_consensus(oi_change_pct_median=0.0, oi_direction_agreement=0.75)
    row = make_percentile_row(metric="oi_change_pct_median", value=0.0, percentile_rank=0.5)
    inputs = make_inputs(percentiles=[row], consensus=consensus)
    assert oi_confirmation(inputs, percentile_window="30d") == 0.0


def test_oi_confirmation_zero_agreement_zeroes_out_nonzero_oi():
    consensus = make_consensus(oi_change_pct_median=0.10, oi_direction_agreement=0.0)
    row = make_percentile_row(metric="oi_change_pct_median", value=0.10, percentile_rank=0.9)
    inputs = make_inputs(percentiles=[row], consensus=consensus)
    assert oi_confirmation(inputs, percentile_window="30d") == 0.0


def test_oi_confirmation_full_agreement_full_strength():
    consensus = make_consensus(oi_change_pct_median=0.10, oi_direction_agreement=1.0)
    row = make_percentile_row(metric="oi_change_pct_median", value=0.10, percentile_rank=1.0)
    inputs = make_inputs(percentiles=[row], consensus=consensus)
    assert oi_confirmation(inputs, percentile_window="30d") == pytest.approx(1.0)


def test_oi_confirmation_regression_not_absolute_rank_distance():
    # The explicit forbidden-form regression: a weak rising-OI reading
    # that ranks BELOW its own median (rank=0.10) must be ZERO
    # confirmation, never 2*|0.10-0.5|=0.80 * agreement.
    consensus = make_consensus(oi_change_pct_median=0.10, oi_direction_agreement=0.75)
    row = make_percentile_row(metric="oi_change_pct_median", value=0.10, percentile_rank=0.10)
    inputs = make_inputs(percentiles=[row], consensus=consensus)
    assert oi_confirmation(inputs, percentile_window="30d") == 0.0


@pytest.mark.parametrize("rank", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_oi_confirmation_rising_oi_never_negative(rank):
    consensus = make_consensus(oi_change_pct_median=0.10, oi_direction_agreement=0.75)
    row = make_percentile_row(metric="oi_change_pct_median", value=0.10, percentile_rank=rank)
    inputs = make_inputs(percentiles=[row], consensus=consensus)
    assert oi_confirmation(inputs, percentile_window="30d") >= 0.0


@pytest.mark.parametrize("rank", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_oi_confirmation_falling_oi_never_positive(rank):
    consensus = make_consensus(oi_change_pct_median=-0.10, oi_direction_agreement=0.75)
    row = make_percentile_row(metric="oi_change_pct_median", value=-0.10, percentile_rank=rank)
    inputs = make_inputs(percentiles=[row], consensus=consensus)
    assert oi_confirmation(inputs, percentile_window="30d") <= 0.0


def test_oi_confirmation_signature_has_no_direction_parameter():
    sig = inspect.signature(oi_confirmation)
    params = set(sig.parameters)
    assert not (params & {"direction", "price_evidence", "regime", "bias", "long", "short"})


# ---- unavailable ----
def test_oi_confirmation_missing_consensus_is_none():
    inputs = make_inputs(percentiles=[], consensus=None)
    assert oi_confirmation(inputs, percentile_window="30d") is None


def test_oi_confirmation_missing_raw_is_none():
    consensus = make_consensus(oi_change_pct_median=None)
    inputs = make_inputs(percentiles=[], consensus=consensus)
    assert oi_confirmation(inputs, percentile_window="30d") is None


def test_oi_confirmation_missing_agreement_is_none():
    consensus = make_consensus(oi_direction_agreement=None)
    inputs = make_inputs(percentiles=[], consensus=consensus)
    assert oi_confirmation(inputs, percentile_window="30d") is None


def test_oi_confirmation_missing_percentile_row_is_none():
    consensus = make_consensus()
    inputs = make_inputs(percentiles=[], consensus=consensus)
    assert oi_confirmation(inputs, percentile_window="30d") is None


def test_oi_confirmation_missing_rank_is_none():
    consensus = make_consensus()
    row = make_percentile_row(metric="oi_change_pct_median", percentile_rank=None)
    inputs = make_inputs(percentiles=[row], consensus=consensus)
    assert oi_confirmation(inputs, percentile_window="30d") is None


@pytest.mark.parametrize("tier", ["none", "low"])
def test_oi_confirmation_low_tier_is_none(tier):
    consensus = make_consensus()
    row = make_percentile_row(metric="oi_change_pct_median", confidence_tier=tier)
    inputs = make_inputs(percentiles=[row], consensus=consensus)
    assert oi_confirmation(inputs, percentile_window="30d") is None


# ---- malformed ----
@pytest.mark.parametrize("bad_agreement", [-0.01, 1.01, float("nan"), float("inf"), True, "0.8"])
def test_oi_confirmation_malformed_agreement_raises(bad_agreement):
    consensus = make_consensus(oi_direction_agreement=bad_agreement)
    row = make_percentile_row(metric="oi_change_pct_median", percentile_rank=0.5)
    inputs = make_inputs(percentiles=[row], consensus=consensus)
    with pytest.raises(V2ContextEvidenceError):
        oi_confirmation(inputs, percentile_window="30d")


@pytest.mark.parametrize("bad_raw", [float("nan"), float("inf"), float("-inf"), True, "0.1"])
def test_oi_confirmation_malformed_raw_raises(bad_raw):
    consensus = make_consensus(oi_change_pct_median=bad_raw)
    row = make_percentile_row(metric="oi_change_pct_median", percentile_rank=0.5)
    inputs = make_inputs(percentiles=[row], consensus=consensus)
    with pytest.raises(V2ContextEvidenceError):
        oi_confirmation(inputs, percentile_window="30d")


# ============================================================================
# 5. IMMUTABILITY / NO MUTATION
# ============================================================================
def test_functions_never_mutate_inputs_or_percentile_rows():
    row = make_percentile_row(metric="oi_change_pct_median", value=0.1, percentile_rank=0.9)
    consensus = make_consensus()
    inputs = make_inputs(percentiles=[row], consensus=consensus)

    row_before = dict(row)
    consensus_before = dict(consensus)

    normalized_evidence(inputs, metric="price_move_pct_median", percentile_window="30d")
    compression_score(inputs, percentile_window="30d")
    oi_confirmation(inputs, percentile_window="30d")
    find_consensus_percentile(inputs, metric="oi_change_pct_median", percentile_window="30d")

    assert row == row_before
    assert consensus == consensus_before
    assert inputs.percentiles == (row,)
    assert inputs.consensus is consensus


# ============================================================================
# 6. PURITY — module-source checks
# ============================================================================
def _executable_body_source(module) -> str:
    """Source with every docstring stripped so a prose mention inside
    documentation cannot false-positive a forbidden-token scan (mirrors
    tests/analytics/test_forecasting_v2_aligned_inputs.py's own helper)."""
    import ast
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_module_has_no_clock_random_uuid_network_filesystem_access():
    body_src = _executable_body_source(ce_module)
    forbidden = (
        "datetime.now(", "datetime.utcnow(", "time.time(", "time.monotonic(",
        "import random", "import uuid", "import yaml", "os.environ", "os.getenv",
        "requests.", "httpx.", "open(", "asyncpg", "subprocess",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden token found: {token!r}"


def test_module_imports_nothing_from_storage_runtime_main_notifications():
    import ast
    tree = ast.parse(inspect.getsource(ce_module))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            for banned in ("storage", "runtime", "main", "notifications"):
                assert not name.startswith(banned), f"forbidden import: {name}"


def test_all_public_functions_are_synchronous():
    for name in ("find_consensus_percentile", "normalized_evidence",
                 "compression_score", "oi_confirmation"):
        fn = getattr(ce_module, name)
        assert not inspect.iscoroutinefunction(fn), f"{name} must be synchronous"


# ============================================================================
# 7. NO FUTURE ENGINE/DETECTOR LOGIC — source-level guarantee this PR does
# ZERO regime/bias classification or Stage 5 detector work.
# ============================================================================
def test_no_regime_bias_or_detector_logic_implemented_yet():
    body_src = _executable_body_source(ce_module)
    forbidden = (
        "REGIME_MIN_", "REGIME_TREND_THRESHOLD", "REGIME_OI_VETO",
        "BULLISH_TRENDING", "BEARISH_TRENDING", "NON_DIRECTIONAL", "INSUFFICIENT_DATA",
        "BIAS_MIN_", "BIAS_THRESHOLD", "NEUTRAL_NOT_ESTABLISHED",
        "directional_context_gate",
        "TREND_PULLBACK", "COMPRESSION_BREAKOUT", "CONFIRMED_BREAKOUT",
    )
    for token in forbidden:
        assert token not in body_src, f"forbidden Stage 4 PR2/PR3/Stage 5 token found: {token!r}"


def test_min_pctl_tier_is_building():
    assert MIN_PCTL_TIER == "building"


def test_confidence_tiers_reused_from_percentile_engine_not_redeclared():
    from analytics.percentile_engine.models import CONFIDENCE_TIERS
    # context_evidence.py must not carry its own independent tier ordering
    # literal — it imports and reuses percentile_engine's canonical one.
    assert "CONFIDENCE_TIERS" in inspect.getsource(ce_module)
    assert CONFIDENCE_TIERS == ("none", "low", "building", "mature")
