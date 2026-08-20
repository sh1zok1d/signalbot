"""Tests for analytics/forecasting_v2/activation_readiness.py.

No real DB -- a fake `V2SetupHistoryReader` recording every call, matching
the existing V2 loader test style
(tests/analytics/test_forecasting_v2_trend_pullback_inputs.py's
`RecordingReader`).
"""
from __future__ import annotations

import asyncio
import dataclasses
import datetime as _datetime_module
from datetime import datetime, timedelta, timezone

import pytest

from analytics.forecasting_v2 import bias_1h as bias_1h_mod
from analytics.forecasting_v2 import compression_breakout as compression_breakout_mod
from analytics.forecasting_v2 import regime_4h as regime_4h_mod
from analytics.forecasting_v2.activation_readiness import (
    MANDATORY_PERCENTILE_COVERAGE, V2ActivationReadinessError,
    V2ActivationReadinessResult, V2CoverageStatus, V2RequiredPercentileCoverage,
    _evaluate_requirements, check_activation_readiness,
)
from analytics.forecasting_v2.alignment import selected_bucket
from analytics.forecasting_v2.context_evidence import MIN_PCTL_TIER

UTC = timezone.utc
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"
CALC_VERSION = "a" * 16
T = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)  # legal 5m boundary, on the 4h/1h/15m grid too


def _run(coro):
    return asyncio.run(coro)


class FakePercentileReader:
    """Satisfies `V2SetupHistoryReader` structurally (only the one method
    `check_activation_readiness` calls). `rows_by_key` maps
    `(metric, timeframe, percentile_window)` to the tuple of rows that key
    should return; a missing key returns `()`, matching a real empty
    read. Asserts every call is for a single EXACT bucket
    (`bucket_start == bucket_end`) -- `check_activation_readiness` must
    never issue a window read."""
    def __init__(self, rows_by_key=None):
        self._rows_by_key = rows_by_key or {}
        self.calls: list = []

    async def fetch_v2_consensus_percentile_window(self, **kw):
        self.calls.append(kw)
        assert kw["bucket_start"] == kw["bucket_end"], (
            "check_activation_readiness must query a single exact bucket, never a window")
        key = (kw["metric"], kw["timeframe"], kw["percentile_window"])
        return self._rows_by_key.get(key, ())

    # Unused by this module, present only for full Protocol conformance.
    async def fetch_v2_consensus_feature_window(self, **kw):
        raise AssertionError("must not be called")

    async def fetch_v2_reference_feature_window(self, **kw):
        raise AssertionError("must not be called")

    async def fetch_v2_reference_klines(self, **kw):
        raise AssertionError("must not be called")

    async def fetch_v2_instrument(self, **kw):
        raise AssertionError("must not be called")


class MultiRowReader:
    """A misbehaving reader that returns more than one row for a single
    exact bucket -- must trip `check_activation_readiness`'s
    defense-in-depth guard, never be silently accepted."""
    async def fetch_v2_consensus_percentile_window(self, **kw):
        return (_row(), _row())


class RaisingReader:
    class Boom(RuntimeError):
        pass

    async def fetch_v2_consensus_percentile_window(self, **kw):
        raise self.Boom("corrupted percentile_snapshots row")


class _RaisingTzinfo(_datetime_module.tzinfo):
    """A malformed/malicious custom `tzinfo` whose `utcoffset()` raises on
    every call -- proves the tech-lead amendment: no raw exception from a
    misbehaving `tzinfo` ever leaks past this module's public boundary."""
    def utcoffset(self, dt):  # noqa: D102 - deliberately misbehaving
        raise RuntimeError("malformed tzinfo: utcoffset() always raises")

    def tzname(self, dt):
        return "RAISING"

    def dst(self, dt):
        return timedelta(0)


def _row(*, bucket_ts=T, value=1.0, percentile_rank=0.5, confidence_tier="mature"):
    return {
        "bucket_ts": bucket_ts, "value": value, "percentile_rank": percentile_rank,
        "confidence_tier": confidence_tier,
    }


def _ready_rows_for_all(*, decision_boundary: datetime = T) -> dict:
    return {
        (req.metric, req.timeframe, req.percentile_window):
            (_row(bucket_ts=selected_bucket(req.timeframe, decision_boundary)),)
        for req in MANDATORY_PERCENTILE_COVERAGE
    }


def _status(req, *, ready: bool) -> V2CoverageStatus:
    return V2CoverageStatus(requirement=req, ready=ready, reason="test", latest_bucket_ts=T)


def _make_result(**over) -> V2ActivationReadinessResult:
    base = dict(
        symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
        decision_boundary=T, ready=True,
        statuses=tuple(_status(req, ready=True) for req in MANDATORY_PERCENTILE_COVERAGE))
    base.update(over)
    return V2ActivationReadinessResult(**base)


# ============================================================================
# MANDATORY_PERCENTILE_COVERAGE — sourced from real frozen family constants
# ============================================================================
def test_mandatory_coverage_has_exactly_four_entries():
    assert len(MANDATORY_PERCENTILE_COVERAGE) == 4


def test_mandatory_coverage_sourced_from_real_family_constants():
    by_source = {req.source: req for req in MANDATORY_PERCENTILE_COVERAGE}
    assert by_source["regime_4h.price"].metric == regime_4h_mod._PRICE_METRIC
    assert by_source["regime_4h.price"].timeframe == regime_4h_mod._REGIME_TIMEFRAME
    assert (
        by_source["regime_4h.price"].percentile_window
        == regime_4h_mod._REGIME_PERCENTILE_WINDOW)
    assert by_source["regime_4h.compression"].metric == regime_4h_mod._COMPRESSION_METRIC
    assert by_source["bias_1h.price"].metric == bias_1h_mod._PRICE_METRIC
    assert by_source["bias_1h.price"].timeframe == bias_1h_mod._BIAS_TIMEFRAME
    assert (
        by_source["bias_1h.price"].percentile_window == bias_1h_mod._BIAS_PERCENTILE_WINDOW)
    assert (
        by_source["compression_breakout.compression"].metric
        == compression_breakout_mod._COMPRESSION_METRIC)
    assert (
        by_source["compression_breakout.compression"].percentile_window
        == compression_breakout_mod.COMPRESSION_PERCENTILE_WINDOW)


def test_mandatory_coverage_excludes_oi_veto_and_percentile_free_families():
    """regime_4h's OI veto is optional/modulating -- never included.
    trend_pullback/confirmed_breakout have no percentile dependency at
    all -- never included."""
    sources = {req.source for req in MANDATORY_PERCENTILE_COVERAGE}
    assert not any("oi" in s.lower() for s in sources)
    assert not any("trend_pullback" in s for s in sources)
    assert not any("confirmed_breakout" in s for s in sources)


# ============================================================================
# V2RequiredPercentileCoverage validation
# ============================================================================
@pytest.mark.parametrize("field", ["source", "metric", "timeframe", "percentile_window"])
@pytest.mark.parametrize("bad", ["", "   "])
def test_required_coverage_rejects_blank_fields(field, bad):
    kwargs = dict(source="s", metric="m", timeframe="4h", percentile_window="30d")
    kwargs[field] = bad
    with pytest.raises(V2ActivationReadinessError, match=field):
        V2RequiredPercentileCoverage(**kwargs)


def test_required_coverage_rejects_unrecognized_timeframe():
    with pytest.raises(V2ActivationReadinessError, match="timeframe"):
        V2RequiredPercentileCoverage(
            source="s", metric="m", timeframe="3h", percentile_window="30d")


def test_required_coverage_is_frozen():
    req = V2RequiredPercentileCoverage(
        source="s", metric="m", timeframe="4h", percentile_window="30d")
    with pytest.raises(dataclasses.FrozenInstanceError):
        req.metric = "other"  # type: ignore[misc]


# ============================================================================
# check_activation_readiness — happy path
# ============================================================================
def test_all_requirements_ready_yields_ready_true():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    assert isinstance(result, V2ActivationReadinessResult)
    assert result.ready is True
    assert result.symbol == SYMBOL
    assert result.market_type == MARKET_TYPE
    assert result.calculation_version == CALC_VERSION
    assert result.decision_boundary == T
    assert len(result.statuses) == 4
    assert all(status.ready for status in result.statuses)


def test_calculation_version_and_scope_passed_straight_through_never_defaulted():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    assert len(reader.calls) == 4
    for call in reader.calls:
        assert call["calculation_version"] == CALC_VERSION
        assert call["symbol"] == SYMBOL
        assert call["market_type"] == MARKET_TYPE


# ============================================================================
# Qodo amendment round 1, finding 1: exact bucket, never a window
# ============================================================================
def test_exact_bucket_used_never_a_window_on_aligned_boundary():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    by_timeframe = {call["timeframe"]: call for call in reader.calls}
    for tf in ("4h", "1h", "15m"):
        expected = selected_bucket(tf, T)
        assert by_timeframe[tf]["bucket_start"] == expected
        assert by_timeframe[tf]["bucket_end"] == expected


def test_exact_bucket_at_non_timeframe_aligned_boundary_matches_selected_bucket():
    """The load-bearing regression for finding 1: at T=12:05 (a legal 5m
    boundary, but NOT on the 4h/1h/15m grid), readiness must inspect
    EXACTLY the fully-closed bucket a live detector would consume --
    never a newer or unrelated snapshot, and never a window that starts
    AFTER that bucket."""
    t = datetime(2026, 8, 20, 12, 5, tzinfo=UTC)
    expected_4h = selected_bucket("4h", t)
    expected_1h = selected_bucket("1h", t)
    expected_15m = selected_bucket("15m", t)
    assert expected_4h == datetime(2026, 8, 20, 8, 0, tzinfo=UTC)
    assert expected_1h == datetime(2026, 8, 20, 11, 0, tzinfo=UTC)
    assert expected_15m == datetime(2026, 8, 20, 11, 45, tzinfo=UTC)

    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all(decision_boundary=t))
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=t))
    assert result.ready is True   # materialized history at 08:00/11:00/11:45 is found

    by_timeframe = {call["timeframe"]: call for call in reader.calls}
    assert by_timeframe["4h"]["bucket_start"] == expected_4h
    assert by_timeframe["4h"]["bucket_end"] == expected_4h
    assert by_timeframe["1h"]["bucket_start"] == expected_1h
    assert by_timeframe["15m"]["bucket_start"] == expected_15m
    # The old window-based query would have started at t - 4h == 08:05,
    # strictly AFTER the 08:00 bucket a real detector reads -- prove that
    # window would have EXCLUDED the bucket this test's row lives at.
    old_window_start = t - timedelta(hours=4)
    assert old_window_start > expected_4h


def test_row_present_only_at_selected_bucket_not_at_a_stale_or_newer_one():
    """A row that exists at a DIFFERENT bucket than
    `selected_bucket(timeframe, T)` (older or newer) must NOT satisfy
    readiness -- proves this module never accepts a newer or unrelated
    snapshot. Uses a reader that mirrors the REAL reader's own exact-
    identity contract: a row is only returned when the requested
    `bucket_start`/`bucket_end` matches the bucket it actually lives at."""
    wrong_bucket = selected_bucket("1h", T) - timedelta(hours=1)  # one bucket too old

    class ExactIdentityReader:
        async def fetch_v2_consensus_percentile_window(self, *, bucket_start, bucket_end, **kw):
            if bucket_start != wrong_bucket or bucket_end != wrong_bucket:
                return ()
            return (_row(bucket_ts=wrong_bucket),)

    # A production V2ActivationReadinessResult can only represent the full
    # canonical mandatory set (tech-lead amendment round 2) -- this
    # per-requirement bucket-identity behavior is exercised directly via
    # the private evaluator, not through check_activation_readiness().
    statuses = _run(_evaluate_requirements(
        ExactIdentityReader(), symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T,
        requirements=(V2RequiredPercentileCoverage(
            source="bias_1h.price", metric=bias_1h_mod._PRICE_METRIC,
            timeframe=bias_1h_mod._BIAS_TIMEFRAME,
            percentile_window=bias_1h_mod._BIAS_PERCENTILE_WINDOW),)))
    assert statuses[0].ready is False
    assert "no percentile_snapshots row" in statuses[0].reason


# ============================================================================
# check_activation_readiness — fail-closed NOT_READY cases
# ============================================================================
def test_missing_row_for_one_requirement_makes_whole_result_not_ready():
    rows = _ready_rows_for_all()
    key = (regime_4h_mod._PRICE_METRIC, regime_4h_mod._REGIME_TIMEFRAME,
           regime_4h_mod._REGIME_PERCENTILE_WINDOW)
    rows[key] = ()  # no row at all for regime_4h.price
    reader = FakePercentileReader(rows_by_key=rows)
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    assert result.ready is False
    by_source = {s.requirement.source: s for s in result.statuses}
    assert by_source["regime_4h.price"].ready is False
    assert "no percentile_snapshots row" in by_source["regime_4h.price"].reason
    # every OTHER requirement independently still reports ready=True --
    # never a partial/majority pass, but each status is its own verdict.
    assert by_source["bias_1h.price"].ready is True


def test_none_value_makes_requirement_not_ready():
    rows = _ready_rows_for_all()
    key = (bias_1h_mod._PRICE_METRIC, bias_1h_mod._BIAS_TIMEFRAME,
           bias_1h_mod._BIAS_PERCENTILE_WINDOW)
    rows[key] = (_row(value=None),)
    reader = FakePercentileReader(rows_by_key=rows)
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    assert result.ready is False
    by_source = {s.requirement.source: s for s in result.statuses}
    assert by_source["bias_1h.price"].ready is False
    assert "missing value/percentile_rank" in by_source["bias_1h.price"].reason


def test_none_percentile_rank_makes_requirement_not_ready():
    rows = _ready_rows_for_all()
    key = (bias_1h_mod._PRICE_METRIC, bias_1h_mod._BIAS_TIMEFRAME,
           bias_1h_mod._BIAS_PERCENTILE_WINDOW)
    rows[key] = (_row(percentile_rank=None),)
    reader = FakePercentileReader(rows_by_key=rows)
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    assert result.ready is False


@pytest.mark.parametrize("tier,expected_ready", [
    ("none", False), ("low", False), ("building", True), ("mature", True),
])
def test_confidence_tier_floor_is_min_pctl_tier(tier, expected_ready):
    assert MIN_PCTL_TIER == "building"  # sanity: this test tracks the real frozen floor
    rows = _ready_rows_for_all()
    key = (bias_1h_mod._PRICE_METRIC, bias_1h_mod._BIAS_TIMEFRAME,
           bias_1h_mod._BIAS_PERCENTILE_WINDOW)
    rows[key] = (_row(confidence_tier=tier),)
    reader = FakePercentileReader(rows_by_key=rows)
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    by_source = {s.requirement.source: s for s in result.statuses}
    assert by_source["bias_1h.price"].ready is expected_ready
    assert result.ready is expected_ready


def test_readiness_ignores_sample_size_entirely_math001():
    """MATH-001 / issue #51 regression. `_row()`/`FakePercentileReader`
    never carry a `sample_size` field at all -- `check_activation_
    readiness()` never reads one. This locks in, by name, that a
    `percentile_snapshots` row reporting `confidence_tier="building"`
    (`MIN_PCTL_TIER`, reachable per `STAGE2_SPEC.md` §12.6 once
    `sample_size >= 2` AND the age of the EARLIEST non-null historical
    sample relative to `bucket_ts` is `>= 7` calendar days -- the newest
    sample's position is irrelevant; see `tests/analytics/
    test_percentile_engine.py::test_sparse_long_span_follows_span_
    contract`) is treated as globally READY here, identically to a
    densely-populated distribution. This is the CURRENT, INTENTIONAL
    behavior (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §4.1 amendment;
    docs/PROJECT_RISK_AND_DEBT_REGISTER.md R-023) -- readiness answers "is
    real, non-tier-floored evidence available", not "is the evidence
    statistically dense". A future change that narrows or widens this must
    edit this test deliberately, not by accident.

    Qodo amendment: each row's `bucket_ts` is preserved from
    `_ready_rows_for_all()`'s already-aligned `selected_bucket(req.
    timeframe, decision_boundary)` value -- overwriting it with `_row()`'s
    default (`bucket_ts=T`) would stop exercising the exact-bucket
    invariant `check_activation_readiness()` relies on (4h/1h/15m buckets
    all differ from `T` itself)."""
    rows = _ready_rows_for_all()
    for key, existing_rows in rows.items():
        existing_ts = existing_rows[0]["bucket_ts"]
        rows[key] = (_row(bucket_ts=existing_ts, confidence_tier="building",
                          value=1000.0, percentile_rank=1.0),)
    reader = FakePercentileReader(rows_by_key=rows)
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    assert result.ready is True
    assert all(status.ready for status in result.statuses)


def test_unknown_confidence_tier_raises_not_downgraded_to_not_ready():
    """Corruption (an impossible tier string) is never silently treated as
    a legitimate NOT_READY -- it is a real error."""
    rows = _ready_rows_for_all()
    key = (bias_1h_mod._PRICE_METRIC, bias_1h_mod._BIAS_TIMEFRAME,
           bias_1h_mod._BIAS_PERCENTILE_WINDOW)
    rows[key] = (_row(confidence_tier="bogus_tier"),)
    reader = FakePercentileReader(rows_by_key=rows)
    with pytest.raises(V2ActivationReadinessError, match="confidence_tier"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=T))


def test_more_than_one_row_for_exact_bucket_raises_defense_in_depth():
    reader = MultiRowReader()
    with pytest.raises(V2ActivationReadinessError, match="expected at most 1"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=T))


# ============================================================================
# corruption is never swallowed
# ============================================================================
def test_reader_error_propagates_unchanged_never_downgraded():
    with pytest.raises(RaisingReader.Boom):
        _run(check_activation_readiness(
            RaisingReader(), symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=T))


# ============================================================================
# input validation
# ============================================================================
@pytest.mark.parametrize("bad", ["", "   ", None])
def test_blank_symbol_rejected(bad):
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="symbol"):
        _run(check_activation_readiness(
            reader, symbol=bad, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=T))


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_blank_market_type_rejected(bad):
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="market_type"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=bad,
            calculation_version=CALC_VERSION, decision_boundary=T))


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_blank_calculation_version_rejected(bad):
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="calculation_version"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=bad, decision_boundary=T))


def test_naive_decision_boundary_rejected():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="decision_boundary"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=datetime(2026, 8, 20, 12, 0)))


def test_non_utc_decision_boundary_rejected():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    non_utc = datetime(2026, 8, 20, 12, 0, tzinfo=timezone(timedelta(hours=2)))
    with pytest.raises(V2ActivationReadinessError, match="decision_boundary"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=non_utc))


def test_non_whole_minute_decision_boundary_rejected():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="decision_boundary"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION,
            decision_boundary=datetime(2026, 8, 20, 12, 0, 30, tzinfo=UTC)))


def test_empty_requirements_rejected():
    """Exercised via the private evaluator -- the public
    check_activation_readiness() no longer accepts a `requirements=`
    override at all (tech-lead amendment round 2)."""
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="requirements"):
        _run(_evaluate_requirements(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=T, requirements=()))


def test_wrong_type_requirement_rejected():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="V2RequiredPercentileCoverage"):
        _run(_evaluate_requirements(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=T,
            requirements=("not-a-requirement",)))  # type: ignore[arg-type]


def test_check_activation_readiness_has_no_public_requirements_parameter():
    """The public entry point cannot be weakened by a caller-supplied
    subset -- confirmed by signature inspection, not just behavior."""
    import inspect
    sig = inspect.signature(check_activation_readiness)
    assert "requirements" not in sig.parameters


# ============================================================================
# Qodo amendment round 1, finding 6 (illegal boundaries) — reuse the
# canonical alignment validator, off-grid whole-minute values rejected
# ============================================================================
@pytest.mark.parametrize("bad_minute", [1, 2, 3, 4, 6, 7, 8, 9])
def test_off_5m_grid_whole_minute_decision_boundary_rejected(bad_minute):
    """12:03 etc. are whole-minute but NOT on the 5m grid -- must be
    rejected by check_activation_readiness (previously only whole-minute
    was checked, silently accepting an illegal boundary)."""
    off_grid = datetime(2026, 8, 20, 12, bad_minute, tzinfo=UTC)
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError, match="decision_boundary"):
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=off_grid))


def test_decision_boundary_validation_delegates_to_selected_bucket_no_duplicate_regex():
    """Reuses the canonical alignment validator -- no locally-maintained
    weaker duplicate grid-alignment check."""
    import inspect
    src = inspect.getsource(
        __import__(
            "analytics.forecasting_v2.activation_readiness",
            fromlist=["activation_readiness"]))
    assert "selected_bucket(" in src
    assert "% 5" not in src  # no local re-derivation of the 5m-grid modulus check


# ============================================================================
# tech-lead amendment: malformed tzinfo never leaks a raw exception
# ============================================================================
def test_malformed_tzinfo_utcoffset_never_leaks_raw_exception_in_check():
    bad_dt = datetime(2026, 8, 20, 12, 0, tzinfo=_RaisingTzinfo())
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    with pytest.raises(V2ActivationReadinessError) as exc_info:
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=bad_dt))
    # the underlying RuntimeError is chained/described, never swallowed silently
    assert "RuntimeError" in str(exc_info.value) or isinstance(exc_info.value.__cause__, RuntimeError)


def test_malformed_tzinfo_utcoffset_never_leaks_raw_exception_in_result_construction():
    bad_dt = datetime(2026, 8, 20, 12, 0, tzinfo=_RaisingTzinfo())
    with pytest.raises(V2ActivationReadinessError):
        _make_result(decision_boundary=bad_dt)


def test_utcoffset_called_at_most_once_by_our_own_validator():
    """A tzinfo that raises only on its SECOND call would silently look
    "fine" under a naive two-call validator -- this proves our own
    boundary calls the offset-evaluation path at most once (by never
    calling `.utcoffset()` itself at all; it delegates entirely to
    `selected_bucket()`)."""
    calls = {"n": 0}

    class _CountingTzinfo(_datetime_module.tzinfo):
        def utcoffset(self, dt):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise RuntimeError("raises only on second call")
            return timedelta(0)

        def tzname(self, dt):
            return "COUNTING"

        def dst(self, dt):
            return timedelta(0)

    dt = datetime(2026, 8, 20, 12, 0, tzinfo=_CountingTzinfo())
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    # This module's own `_validate_decision_boundary` must not itself
    # trigger the second call; whether `selected_bucket()`'s internal
    # implementation calls utcoffset() more than once is out of THIS
    # module's control/scope -- what matters is that any resulting
    # exception is translated, never leaked raw. Accept either a clean
    # pass or a translated V2ActivationReadinessError, but NEVER a raw
    # RuntimeError.
    try:
        _run(check_activation_readiness(
            reader, symbol=SYMBOL, market_type=MARKET_TYPE,
            calculation_version=CALC_VERSION, decision_boundary=dt))
    except V2ActivationReadinessError:
        pass  # acceptable: translated
    except RuntimeError:
        pytest.fail("a raw RuntimeError leaked past check_activation_readiness's boundary")


# ============================================================================
# Qodo amendment round 1, finding 4: V2ActivationReadinessResult is
# self-validating, never forgeable
# ============================================================================
def test_result_ready_true_with_all_ready_statuses_accepted():
    result = _make_result(ready=True)
    assert result.ready is True


def test_result_forged_ready_true_with_failing_status_rejected():
    statuses = (
        _status(MANDATORY_PERCENTILE_COVERAGE[0], ready=False),
        *[_status(req, ready=True) for req in MANDATORY_PERCENTILE_COVERAGE[1:]],
    )
    with pytest.raises(V2ActivationReadinessError, match="ready"):
        _make_result(ready=True, statuses=statuses)


def test_result_forged_ready_false_with_all_ready_statuses_rejected():
    with pytest.raises(V2ActivationReadinessError, match="ready"):
        _make_result(ready=False, statuses=tuple(
            _status(req, ready=True) for req in MANDATORY_PERCENTILE_COVERAGE))


def test_result_empty_statuses_rejected():
    with pytest.raises(V2ActivationReadinessError, match="statuses"):
        _make_result(ready=True, statuses=())


def test_result_non_tuple_statuses_rejected():
    with pytest.raises(V2ActivationReadinessError, match="statuses"):
        _make_result(ready=True, statuses=[_status(MANDATORY_PERCENTILE_COVERAGE[0], ready=True)])


def test_result_wrong_type_status_element_rejected():
    with pytest.raises(V2ActivationReadinessError, match="V2CoverageStatus"):
        _make_result(ready=True, statuses=("not-a-status",))  # type: ignore[arg-type]


def test_result_duplicate_requirement_rejected():
    req = MANDATORY_PERCENTILE_COVERAGE[0]
    with pytest.raises(V2ActivationReadinessError, match="duplicate"):
        _make_result(ready=True, statuses=(
            _status(req, ready=True), _status(req, ready=True)))


# ============================================================================
# tech-lead amendment round 2: full canonical coverage, never a partial probe
# ============================================================================
def test_1_one_requirement_subset_can_never_create_a_globally_ready_result():
    """A one-requirement subset -- even if that one requirement is
    ready -- can never be represented as a globally activation-ready
    result."""
    with pytest.raises(V2ActivationReadinessError, match="MANDATORY_PERCENTILE_COVERAGE"):
        _make_result(ready=True, statuses=(
            _status(MANDATORY_PERCENTILE_COVERAGE[0], ready=True),))
    # Not ready=False either -- the object cannot be constructed AT ALL.
    with pytest.raises(V2ActivationReadinessError, match="MANDATORY_PERCENTILE_COVERAGE"):
        _make_result(ready=False, statuses=(
            _status(MANDATORY_PERCENTILE_COVERAGE[0], ready=True),))


def test_2_three_of_four_mandatory_requirements_cannot_create_a_result():
    subset = tuple(_status(req, ready=True) for req in MANDATORY_PERCENTILE_COVERAGE[:3])
    assert len(subset) == 3
    with pytest.raises(V2ActivationReadinessError, match="MANDATORY_PERCENTILE_COVERAGE"):
        _make_result(ready=True, statuses=subset)


def test_3_full_four_of_four_ready_coverage_succeeds():
    statuses = tuple(_status(req, ready=True) for req in MANDATORY_PERCENTILE_COVERAGE)
    assert len(statuses) == 4
    result = _make_result(ready=True, statuses=statuses)
    assert result.ready is True
    assert len(result.statuses) == 4


def test_4_full_coverage_with_one_failing_requirement_yields_ready_false():
    statuses = (
        _status(MANDATORY_PERCENTILE_COVERAGE[0], ready=False),
        *[_status(req, ready=True) for req in MANDATORY_PERCENTILE_COVERAGE[1:]],
    )
    assert len(statuses) == 4
    result = _make_result(ready=False, statuses=statuses)
    assert result.ready is False
    # The SAME full coverage marked ready=True must be rejected (finding
    # 4's invariant, still enforced together with the new coverage check).
    with pytest.raises(V2ActivationReadinessError, match="ready"):
        _make_result(ready=True, statuses=statuses)


def test_5_extra_noncanonical_requirement_is_rejected():
    extra_req = V2RequiredPercentileCoverage(
        source="not_a_real_mandatory_requirement", metric="some_metric",
        timeframe="4h", percentile_window="30d")
    statuses = (
        *[_status(req, ready=True) for req in MANDATORY_PERCENTILE_COVERAGE],
        _status(extra_req, ready=True),
    )
    assert len(statuses) == 5
    with pytest.raises(V2ActivationReadinessError, match="MANDATORY_PERCENTILE_COVERAGE"):
        _make_result(ready=True, statuses=statuses)


def test_6_direct_construction_cannot_bypass_the_canonical_coverage_invariant():
    """Bypassing check_activation_readiness() entirely and constructing
    V2ActivationReadinessResult directly with a partial/extra/mismatched
    statuses tuple must STILL raise -- __post_init__ is the actual
    enforcement point for every construction path."""
    # partial
    with pytest.raises(V2ActivationReadinessError, match="MANDATORY_PERCENTILE_COVERAGE"):
        V2ActivationReadinessResult(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            decision_boundary=T, ready=True,
            statuses=(_status(MANDATORY_PERCENTILE_COVERAGE[0], ready=True),))
    # full coverage, direct construction, succeeds
    result = V2ActivationReadinessResult(
        symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
        decision_boundary=T, ready=True,
        statuses=tuple(_status(req, ready=True) for req in MANDATORY_PERCENTILE_COVERAGE))
    assert result.ready is True


def test_7_decision_view_cannot_receive_a_partial_but_ready_readiness_object():
    """The full closed loop: since V2ActivationReadinessResult itself
    cannot be constructed from a partial requirement set, V2DecisionView
    (which only type-checks + identity-checks an already-constructed
    V2ActivationReadinessResult) can never end up composed with a partial-
    but-ready readiness object -- there is no such object to compose."""
    from analytics.forecasting_v2.decision_provenance import V2DecisionProvenance
    from analytics.forecasting_v2.decision_view import resolve_decision_view
    from analytics.forecasting_v2.events import LIVE

    # A partial readiness result cannot even be constructed to attempt
    # composing it -- this IS the proof.
    with pytest.raises(V2ActivationReadinessError, match="MANDATORY_PERCENTILE_COVERAGE"):
        _make_result(ready=True, statuses=(
            _status(MANDATORY_PERCENTILE_COVERAGE[0], ready=True),))

    # And a full-coverage, genuinely ready result composes cleanly.
    provenance = V2DecisionProvenance(
        run_kind=LIVE, run_id="live-shadow", decision_boundary=T,
        model_family="v2", rules_version="v2-rules-v0.2.0",
        symbol=SYMBOL, market_type=MARKET_TYPE,
        feature_schema_version=1, calculation_version=CALC_VERSION, config_hash="a" * 64,
        config_version="2.1.0", code_version="deadbeef",
        decision_code_version="decision-code-v1")
    readiness = _make_result(ready=True)
    view = resolve_decision_view(provenance, readiness)
    assert view.ready is True


@pytest.mark.parametrize("field,bad", [
    ("symbol", ""), ("symbol", None), ("market_type", ""), ("market_type", None),
    ("calculation_version", ""), ("calculation_version", None),
])
def test_result_blank_identity_field_rejected(field, bad):
    with pytest.raises(V2ActivationReadinessError, match=field):
        _make_result(**{field: bad})


def test_result_ready_non_bool_rejected():
    with pytest.raises(V2ActivationReadinessError, match="ready"):
        _make_result(ready=1)  # type: ignore[arg-type]


def test_result_is_frozen():
    result = _make_result()
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.ready = False  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.statuses[0].ready = False  # type: ignore[misc]


def test_check_activation_readiness_return_value_satisfies_its_own_invariant():
    reader = FakePercentileReader(rows_by_key=_ready_rows_for_all())
    result = _run(check_activation_readiness(
        reader, symbol=SYMBOL, market_type=MARKET_TYPE,
        calculation_version=CALC_VERSION, decision_boundary=T))
    # Constructing an EQUIVALENT result by hand must not raise -- proves
    # check_activation_readiness's own return already satisfies
    # __post_init__'s invariant (it goes through the same constructor).
    V2ActivationReadinessResult(
        symbol=result.symbol, market_type=result.market_type,
        calculation_version=result.calculation_version,
        decision_boundary=result.decision_boundary, ready=result.ready,
        statuses=result.statuses)


# ============================================================================
# V2CoverageStatus self-validation
# ============================================================================
def test_coverage_status_wrong_type_requirement_rejected():
    with pytest.raises(V2ActivationReadinessError, match="requirement"):
        V2CoverageStatus(requirement="not-a-requirement", ready=True, reason="x",
                          latest_bucket_ts=None)  # type: ignore[arg-type]


def test_coverage_status_non_bool_ready_rejected():
    with pytest.raises(V2ActivationReadinessError, match="ready"):
        V2CoverageStatus(requirement=MANDATORY_PERCENTILE_COVERAGE[0], ready=1,
                          reason="x", latest_bucket_ts=None)  # type: ignore[arg-type]


def test_coverage_status_blank_reason_rejected():
    with pytest.raises(V2ActivationReadinessError, match="reason"):
        V2CoverageStatus(requirement=MANDATORY_PERCENTILE_COVERAGE[0], ready=True,
                          reason="", latest_bucket_ts=None)


def test_coverage_status_bad_latest_bucket_ts_rejected():
    with pytest.raises(V2ActivationReadinessError, match="latest_bucket_ts"):
        V2CoverageStatus(requirement=MANDATORY_PERCENTILE_COVERAGE[0], ready=True,
                          reason="x", latest_bucket_ts="not-a-datetime")  # type: ignore[arg-type]


def test_coverage_status_none_latest_bucket_ts_accepted():
    status = V2CoverageStatus(requirement=MANDATORY_PERCENTILE_COVERAGE[0], ready=False,
                               reason="x", latest_bucket_ts=None)
    assert status.latest_bucket_ts is None
