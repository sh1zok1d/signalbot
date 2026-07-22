"""Adversarial unit tests for the Stage 2.1 Data Quality & Gap Detection core
(analytics/data_quality/, Data Quality Contract Revision 0.2.5,
docs/STAGE2_SPEC.md §13).

Every frozen §13 worked example (§13.15) is represented here. Tests exercise the
real public implementation — the algorithm is never re-implemented inside a test
helper.
"""
from __future__ import annotations

import ast
import dataclasses
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from analytics.data_quality import (
    CONTINUOUS_METRICS, DataHealthSnapshot, DataQualityError, DataQualityObservation,
    DataQualityRequest, DataQualityThresholds, EVENT_DRIVEN_METRICS, GapSummary,
    LIVE_EXPECTED_INTERVAL_S, VALID_BACKFILL_STATUSES, VALID_COVERAGE_TYPES,
    VALID_METRICS, compute_data_health_snapshot, compute_gap_summary,
    derive_data_health_status,
)

UTC = timezone.utc
H64 = "a" * 64                       # 64 lowercase hex -> valid config_hash
H16 = "b" * 16                       # 16 lowercase hex -> valid calculation_version
# snapshot_ts aligned to cadence 60 with zero microseconds
S = datetime(2026, 7, 22, 0, 0, 0, tzinfo=UTC)


def _thr(cadence_s=60, coverage_window_s=86_400, gap_tolerance_factor=1.5,
         max_usable_gap_s=300):
    return DataQualityThresholds(cadence_s, coverage_window_s,
                                 gap_tolerance_factor, max_usable_gap_s)


def _obs(ts, *, exchange="binance", symbol="BTCUSDT", market_type="perp",
         metric="ohlcv", raw_source="live"):
    return DataQualityObservation(exchange, symbol, market_type, metric, ts, raw_source)


def _req(**over):
    """Build a valid healthy-OHLCV request; override any field via kwargs.
    `observations` defaults to two 60s-spaced live bars."""
    base = dict(
        symbol="BTCUSDT", exchange="binance", market_type="perp", metric="ohlcv",
        snapshot_ts=S,
        observations=[_obs(S - timedelta(seconds=60)), _obs(S - timedelta(seconds=120))],
        live_supported=True, historical_supported=True, coverage_type="full",
        expected_freshness_s=120, expected_interval_s=60, connection_up=None,
        backfill_status="complete", thresholds=_thr(),
        config_hash=H64, config_version="2.1.0", code_version="deadbeef",
        feature_schema_version=1, calculation_version=H16,
    )
    base.update(over)
    return DataQualityRequest(**base)


def _liq_req(**over):
    """Build a valid quiet-connected liquidations request."""
    base = dict(
        metric="liquidations", expected_interval_s=None, expected_freshness_s=None,
        connection_up=True, observations=[], historical_supported=False,
        backfill_status="not_applicable",
    )
    base.update(over)
    return _req(**base)


# ============================================================================
# A. Purity and models
# ============================================================================
def test_models_are_frozen():
    thr = _thr()
    obs = _obs(S - timedelta(seconds=60))
    snap = compute_data_health_snapshot(_req())
    for inst, field in [(thr, "cadence_s"), (obs, "raw_source"),
                        (snap, "is_usable")]:
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(inst, field, "x")


def test_request_observations_frozen_to_tuple():
    live = [_obs(S - timedelta(seconds=60))]
    req = _req(observations=live)
    assert isinstance(req.observations, tuple)
    live.append(_obs(S - timedelta(seconds=120)))  # mutate original
    assert len(req.observations) == 1               # request unaffected


_FORBIDDEN_MODULES = {
    "asyncio", "socket", "requests", "redis", "os", "subprocess",
    "psycopg", "asyncpg", "aiohttp", "time", "pathlib", "sqlite3",
}


def _module_asts():
    for py in Path("analytics/data_quality").glob("*.py"):
        yield py, ast.parse(py.read_text(encoding="utf-8"))


def test_no_forbidden_side_effect_imports():
    """AST scan (not text) so explanatory docstrings can name forbidden APIs."""
    for py, tree in _module_asts():
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        bad = imported & _FORBIDDEN_MODULES
        assert not bad, f"{py} imports forbidden module(s): {bad}"


def test_no_clock_or_filesystem_calls():
    banned_attrs = {"now", "utcnow", "time", "today"}
    for py, tree in _module_asts():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Attribute):
                    assert f.attr not in banned_attrs, f"{py} calls .{f.attr}()"
                if isinstance(f, ast.Name):
                    assert f.id != "open", f"{py} calls open()"


def test_lateness_uses_integer_math_not_total_seconds():
    """No `.total_seconds()` call in the computation modules (AST, so the
    docstring that *names* the forbidden pattern does not trip the check)."""
    for py, tree in _module_asts():
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr != "total_seconds", f"{py} uses total_seconds()"


def test_live_interval_mapping_is_read_only():
    with pytest.raises(TypeError):
        LIVE_EXPECTED_INTERVAL_S["ohlcv"] = 1  # MappingProxyType


def test_no_source_mode_field_anywhere():
    for model in (DataQualityObservation, DataQualityRequest, DataHealthSnapshot):
        names = {f.name for f in dataclasses.fields(model)}
        assert "source_mode" not in names
    assert "raw_source" not in {f.name for f in dataclasses.fields(DataHealthSnapshot)}


def test_observation_has_no_calculation_version():
    names = {f.name for f in dataclasses.fields(DataQualityObservation)}
    assert "calculation_version" not in names
    assert "source_mode" not in names


def _schema_columns(table: str) -> list[str]:
    sql = Path("storage/stage2_schema.sql").read_text(encoding="utf-8")
    m = re.search(r"CREATE TABLE IF NOT EXISTS " + table + r"\s*\((.*?)\n\);", sql, re.S)
    assert m, f"{table} not found"
    cols = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("--") or line.upper().startswith("PRIMARY KEY"):
            continue
        cols.append(line.split()[0])
    return cols


def test_output_schema_parity_minus_computed_at():
    schema_cols = set(_schema_columns("data_health_snapshots"))
    model_cols = {f.name for f in dataclasses.fields(DataHealthSnapshot)}
    assert "computed_at" in schema_cols
    assert "computed_at" not in model_cols
    assert model_cols == schema_cols - {"computed_at"}


# ============================================================================
# B. Identity
# ============================================================================
@pytest.mark.parametrize("exchange", ["binance", "bybit", "okx"])
def test_all_active_exchanges_accepted(exchange):
    snap = compute_data_health_snapshot(
        _req(exchange=exchange,
             observations=[_obs(S - timedelta(seconds=60), exchange=exchange)]))
    assert snap.exchange == exchange


@pytest.mark.parametrize("exchange", ["bitget", "kraken", "", "BINANCE"])
def test_inactive_or_unknown_exchange_rejected(exchange):
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(exchange=exchange, observations=[]))


def test_btcusdt_perp_accepted():
    assert compute_data_health_snapshot(_req()).symbol == "BTCUSDT"


@pytest.mark.parametrize("symbol", ["ETHUSDT", "SOLUSDT", "UNKNOWN"])
def test_unknown_symbol_rejected(symbol):
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(
            _req(symbol=symbol,
                 observations=[_obs(S - timedelta(seconds=60), symbol=symbol)]))


@pytest.mark.parametrize("market_type", ["spot", "future", "PERP", ""])
def test_bad_market_type_rejected(market_type):
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(
            _req(market_type=market_type,
                 observations=[_obs(S - timedelta(seconds=60), market_type=market_type)]))


@pytest.mark.parametrize("metric", list(VALID_METRICS))
def test_five_health_metrics_accepted(metric):
    if metric in EVENT_DRIVEN_METRICS:
        req = _liq_req()
    else:
        req = _req(metric=metric, expected_interval_s=LIVE_EXPECTED_INTERVAL_S[metric],
                   observations=[_obs(S - timedelta(seconds=60), metric=metric)])
    assert compute_data_health_snapshot(req).metric == metric


def test_mark_price_rejected():
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(
            _req(metric="mark_price", expected_interval_s=60,
                 observations=[_obs(S - timedelta(seconds=60), metric="mark_price")]))


@pytest.mark.parametrize("over", [
    {"config_hash": "a" * 63},
    {"config_hash": "A" * 64},
    {"config_hash": "g" * 64},
    {"calculation_version": "b" * 15},
    {"calculation_version": "B" * 16},
    {"config_version": ""},
    {"code_version": "   "},
    {"feature_schema_version": 0},
    {"feature_schema_version": True},
    {"feature_schema_version": 1.0},
])
def test_malformed_version_fields_rejected(over):
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(**over))


@pytest.mark.parametrize("over", [
    {"config_hash": "a" * 64 + "\n"},
    {"config_hash": "a" * 64 + " "},
    {"config_hash": "\n" + "a" * 63},
    {"calculation_version": "b" * 16 + "\n"},
    {"calculation_version": "b" * 16 + " "},
    {"calculation_version": " " + "b" * 15},
])
def test_hex_trailing_whitespace_or_newline_rejected(over):
    # `$` can match before a trailing newline; fullmatch on an unanchored pattern
    # must reject any non-hex trailing/leading character.
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(**over))


def test_exact_length_hex_still_accepted():
    snap = compute_data_health_snapshot(_req(config_hash="a" * 64, calculation_version="b" * 16))
    assert snap.config_hash == "a" * 64 and snap.calculation_version == "b" * 16


# ============================================================================
# C. Snapshot time
# ============================================================================
def test_utc_snapshot_accepted():
    assert compute_data_health_snapshot(_req()).snapshot_ts == S


def test_naive_snapshot_rejected():
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(snapshot_ts=datetime(2026, 7, 22, 0, 0, 0),
                                          observations=[]))


def test_nonzero_offset_snapshot_rejected():
    ts = datetime(2026, 7, 22, 0, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(snapshot_ts=ts, observations=[]))


def test_microsecond_snapshot_rejected():
    ts = datetime(2026, 7, 22, 0, 0, 0, 1, tzinfo=UTC)
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(snapshot_ts=ts, observations=[]))


def test_off_cadence_snapshot_rejected():
    ts = datetime(2026, 7, 22, 0, 0, 30, tzinfo=UTC)  # not a multiple of 60
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(snapshot_ts=ts, observations=[]))


def test_exact_cadence_snapshot_accepted():
    ts = datetime(2026, 7, 22, 0, 5, 0, tzinfo=UTC)
    snap = compute_data_health_snapshot(
        _req(snapshot_ts=ts, observations=[_obs(ts - timedelta(seconds=60))]))
    assert snap.snapshot_ts == ts


def test_cadence_alignment_uses_custom_cadence():
    # cadence 15: snapshot at :45 is aligned, at :50 is not
    ts_ok = datetime(2026, 7, 22, 0, 0, 45, tzinfo=UTC)
    compute_data_health_snapshot(
        _req(snapshot_ts=ts_ok, thresholds=_thr(cadence_s=15),
             metric="open_interest", expected_interval_s=15, expected_freshness_s=30,
             observations=[_obs(ts_ok - timedelta(seconds=15), metric="open_interest")]))
    ts_bad = datetime(2026, 7, 22, 0, 0, 50, tzinfo=UTC)
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(
            _req(snapshot_ts=ts_bad, thresholds=_thr(cadence_s=15),
                 metric="open_interest", expected_interval_s=15, expected_freshness_s=30,
                 observations=[]))


# ============================================================================
# D. Thresholds and numeric validation
# ============================================================================
@pytest.mark.parametrize("field,bad", [
    ("cadence_s", 0), ("cadence_s", -1), ("cadence_s", 1.0), ("cadence_s", "60"),
    ("cadence_s", True),
    ("coverage_window_s", 0), ("coverage_window_s", -5), ("coverage_window_s", 3.0),
    ("coverage_window_s", False),
    ("max_usable_gap_s", 0), ("max_usable_gap_s", -1), ("max_usable_gap_s", 2.5),
    ("max_usable_gap_s", True),
])
def test_int_threshold_fields_reject_bad(field, bad):
    kw = dict(cadence_s=60, coverage_window_s=86_400, gap_tolerance_factor=1.5,
              max_usable_gap_s=300)
    kw[field] = bad
    with pytest.raises(DataQualityError):
        DataQualityThresholds(**kw)


@pytest.mark.parametrize("bad", [1.0, 1, 0.5, 0, -3, True, False, float("nan"),
                                 float("inf"), float("-inf"), "1.5"])
def test_gap_tolerance_factor_rejects_bad(bad):
    with pytest.raises(DataQualityError):
        DataQualityThresholds(60, 86_400, bad, 300)


@pytest.mark.parametrize("good", [1.0001, 1.5, 2, 3.0])
def test_gap_tolerance_factor_accepts_gt_one(good):
    assert DataQualityThresholds(60, 86_400, good, 300).gap_tolerance_factor == good


def test_thresholds_huge_finite_int_factor_no_overflow():
    # a huge finite int must NOT leak OverflowError from a blind float() conversion
    huge = 10 ** 400
    assert DataQualityThresholds(60, 86_400, huge, 300).gap_tolerance_factor == huge


# ----- direct public-helper validation for compute_gap_summary (§13.8) -------
_GAP_TS = [S - timedelta(seconds=1000), S - timedelta(seconds=100)]  # would-be huge gap


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"),
                                 True, False, "1.5", 1, 0.5, 0, -3, None])
def test_compute_gap_summary_rejects_bad_factor_directly(bad):
    # tested through the exported helper, NOT via DataQualityThresholds
    with pytest.raises(DataQualityError):
        compute_gap_summary(_GAP_TS, 60, bad)


def test_positive_infinity_cannot_disable_gap_detection():
    # +inf previously passed `float(x) > 1` and made every delta "not a gap"
    with pytest.raises(DataQualityError):
        compute_gap_summary(_GAP_TS, 60, float("inf"))


def test_compute_gap_summary_huge_finite_int_factor_no_overflow():
    # huge finite int is a legitimate factor: no OverflowError, deterministic result
    g = compute_gap_summary(_GAP_TS, 60, 10 ** 400)
    assert g == GapSummary(0, None)   # threshold astronomically large -> no gap


@pytest.mark.parametrize("bad", [0, -1, 60.0, "60", True, None])
def test_compute_gap_summary_rejects_bad_interval_directly(bad):
    with pytest.raises(DataQualityError):
        compute_gap_summary(_GAP_TS, bad, 1.5)


# ============================================================================
# E. Capability / backfill
# ============================================================================
@pytest.mark.parametrize("field,bad", [
    ("live_supported", "yes"), ("live_supported", 1), ("live_supported", None),
    ("historical_supported", "no"), ("historical_supported", 0),
])
def test_capability_bools_strict(field, bad):
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(**{field: bad}))


@pytest.mark.parametrize("cov", list(VALID_COVERAGE_TYPES))
def test_coverage_type_allow_list_accepts(cov):
    # 'unavailable' is accepted as an input but yields not_available (§13.5 rule 1)
    snap = compute_data_health_snapshot(_req(coverage_type=cov))
    if cov == "unavailable":
        assert snap.is_usable is False
    else:
        assert snap.is_usable is True


@pytest.mark.parametrize("cov", ["partial", "none", "", "FULL"])
def test_coverage_type_unknown_rejected(cov):
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(coverage_type=cov))


def test_historically_unsupported_requires_not_applicable():
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(
            _req(historical_supported=False, backfill_status="complete"))


def test_historically_supported_rejects_not_applicable():
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(
            _req(historical_supported=True, backfill_status="not_applicable"))


@pytest.mark.parametrize("status", [s for s in VALID_BACKFILL_STATUSES if s != "not_applicable"])
def test_all_supported_backfill_states_accepted(status):
    snap = compute_data_health_snapshot(
        _req(historical_supported=True, backfill_status=status))
    assert snap.backfill_status == status


@pytest.mark.parametrize("status", ["done", "queued", "", "NOT_STARTED"])
def test_unknown_backfill_status_rejected(status):
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(historical_supported=True, backfill_status=status))


def test_historical_support_never_changes_live_usability():
    # identical healthy live feed, only backfill readiness differs
    a = compute_data_health_snapshot(
        _req(historical_supported=True, backfill_status="complete"))
    b = compute_data_health_snapshot(
        _req(historical_supported=False, backfill_status="not_applicable"))
    assert a.is_usable == b.is_usable == True
    assert a.backfill_status != b.backfill_status


# ============================================================================
# F. Intervals
# ============================================================================
@pytest.mark.parametrize("metric,interval", list(LIVE_EXPECTED_INTERVAL_S.items()))
def test_exact_live_interval_mapping_accepted(metric, interval):
    if metric in EVENT_DRIVEN_METRICS:
        snap = compute_data_health_snapshot(_liq_req())
        assert snap.expected_interval_s is None
    else:
        snap = compute_data_health_snapshot(
            _req(metric=metric, expected_interval_s=interval,
                 expected_freshness_s=120,
                 observations=[_obs(S - timedelta(seconds=interval), metric=metric)]))
        assert snap.expected_interval_s == interval


def test_wrong_interval_rejected():
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(metric="open_interest", expected_interval_s=60,
                                          expected_freshness_s=30, observations=[]))


def test_bool_interval_rejected():
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(expected_interval_s=True, observations=[]))


def test_liquidation_interval_must_be_none():
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_liq_req(expected_interval_s=15))


def test_continuous_interval_must_not_be_none():
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(expected_interval_s=None, observations=[]))


@pytest.mark.parametrize("bad", [0, -1, 1.5, "120", True])
def test_continuous_freshness_budget_validated(bad):
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(expected_freshness_s=bad, observations=[]))


def test_liquidation_freshness_must_be_none():
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_liq_req(expected_freshness_s=120))


# ============================================================================
# G. Observation isolation
# ============================================================================
@pytest.mark.parametrize("field,val", [
    ("exchange", "bybit"), ("symbol", "ETHUSDT"), ("market_type", "spot"),
    ("metric", "funding"),
])
def test_observation_identity_mismatch_rejected(field, val):
    bad = _obs(S - timedelta(seconds=60), **{field: val})
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(observations=[bad]))


def test_non_observation_object_rejected():
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(observations=[("binance", S)]))


def test_backfill_raw_source_rejected():
    bad = _obs(S - timedelta(seconds=60), raw_source="backfill")
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(observations=[bad]))


@pytest.mark.parametrize("rs", ["replay", "LIVE", "", "historical"])
def test_unknown_raw_source_rejected(rs):
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(observations=[_obs(S - timedelta(seconds=60), raw_source=rs)]))


def test_lower_coverage_boundary_inclusive():
    lo = S - timedelta(seconds=86_400)  # coverage_window_start, inclusive
    snap = compute_data_health_snapshot(_req(observations=[_obs(lo)]))
    assert snap.last_event_at == lo


def test_before_lower_boundary_rejected():
    before = S - timedelta(seconds=86_400, microseconds=1)
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(observations=[_obs(before)]))


def test_exactly_snapshot_ts_rejected():
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(observations=[_obs(S)]))


def test_after_snapshot_ts_rejected():
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(observations=[_obs(S + timedelta(seconds=1))]))


def test_naive_observation_ts_rejected():
    bad = DataQualityObservation("binance", "BTCUSDT", "perp", "ohlcv",
                                 datetime(2026, 7, 21, 23, 59, 0), "live")
    with pytest.raises(DataQualityError):
        compute_data_health_snapshot(_req(observations=[bad]))


def test_duplicate_timestamps_collapse():
    ts = S - timedelta(seconds=60)
    snap = compute_data_health_snapshot(_req(observations=[_obs(ts), _obs(ts), _obs(ts)]))
    assert snap.last_event_at == ts
    assert snap.gap_count == 0


def test_observation_order_invariance():
    tss = [S - timedelta(seconds=60 * i) for i in range(1, 6)]
    a = compute_data_health_snapshot(_req(observations=[_obs(t) for t in tss]))
    b = compute_data_health_snapshot(_req(observations=[_obs(t) for t in reversed(tss)]))
    assert a == b


# ============================================================================
# H. Freshness
# ============================================================================
def test_healthy_ohlcv():
    snap = compute_data_health_snapshot(_req())
    assert snap.last_event_at == S - timedelta(seconds=60)
    assert snap.lateness_ms == 60_000
    assert snap.is_stale is False and snap.is_usable is True


@pytest.mark.parametrize("micros,expected_ms,stale", [
    (120_000_000, 120_000, False),   # exact budget boundary -> fresh
    (120_000_999, 120_000, False),   # floors to 120000 -> fresh
    (120_001_000, 120_001, True),    # 120001 -> stale
])
def test_freshness_sub_millisecond_boundaries(micros, expected_ms, stale):
    obs = [_obs(S - timedelta(microseconds=micros))]
    snap = compute_data_health_snapshot(_req(observations=obs))
    assert snap.lateness_ms == expected_ms
    assert snap.is_stale is stale


def test_lateness_matches_integer_formula_not_float():
    micros = 120_000_999
    last = S - timedelta(microseconds=micros)
    delta = S - last
    integer_formula = (delta.days * 86_400_000 + delta.seconds * 1_000
                       + delta.microseconds // 1_000)
    snap = compute_data_health_snapshot(_req(observations=[_obs(last)]))
    assert snap.lateness_ms == integer_formula == 120_000


def test_empty_continuous_window_is_no_data_not_stale():
    snap = compute_data_health_snapshot(_req(observations=[]))
    assert snap.last_event_at is None
    assert snap.lateness_ms is None
    assert snap.is_stale is False
    assert snap.is_usable is False
    assert derive_data_health_status(
        snap, live_supported=True, coverage_type="full", connection_up=None,
        max_usable_gap_s=300) == "no_data"


def test_last_event_at_is_newest_in_window():
    obs = [_obs(S - timedelta(seconds=180)), _obs(S - timedelta(seconds=60)),
           _obs(S - timedelta(seconds=120))]
    snap = compute_data_health_snapshot(_req(observations=obs))
    assert snap.last_event_at == S - timedelta(seconds=60)


def test_liquidations_never_stale_even_with_old_event():
    old = _obs(S - timedelta(hours=10), metric="liquidations")
    snap = compute_data_health_snapshot(_liq_req(observations=[old]))
    assert snap.is_stale is False
    assert snap.lateness_ms == 10 * 3_600 * 1_000  # still computed


# ============================================================================
# I. Gaps
# ============================================================================
def test_gap_no_observations():
    assert compute_gap_summary([], 60, 1.5) == GapSummary(0, None)


def test_gap_one_observation():
    assert compute_gap_summary([S - timedelta(seconds=60)], 60, 1.5) == GapSummary(0, None)


def test_gap_regular_intervals_none():
    tss = [S - timedelta(seconds=60 * i) for i in range(1, 20)]
    assert compute_gap_summary(tss, 60, 1.5) == GapSummary(0, None)


def test_gap_exact_tolerance_boundary_no_gap():
    a = S - timedelta(seconds=300)
    assert compute_gap_summary([a, a + timedelta(seconds=90)], 60, 1.5) == GapSummary(0, None)


def test_gap_tolerance_plus_one_microsecond():
    a = S - timedelta(seconds=300)
    g = compute_gap_summary([a, a + timedelta(seconds=90, microseconds=1)], 60, 1.5)
    assert g.gap_count == 1 and g.largest_gap_s == 91


def test_gap_multiple_separate_oversized_deltas():
    base = S - timedelta(seconds=1000)
    tss = [base,
           base + timedelta(seconds=200),   # gap (>90)
           base + timedelta(seconds=260),   # ok (60)
           base + timedelta(seconds=460)]   # gap (>90)
    g = compute_gap_summary(tss, 60, 1.5)
    assert g.gap_count == 2 and g.largest_gap_s == 200


def test_gap_duplicates_do_not_create_gap():
    a = S - timedelta(seconds=120)
    assert compute_gap_summary([a, a, a], 60, 1.5) == GapSummary(0, None)


def test_gap_edges_not_counted():
    # single interior delta only; window edges never a gap
    a = S - timedelta(seconds=500)
    g = compute_gap_summary([a, a + timedelta(seconds=200)], 60, 1.5)
    assert g.gap_count == 1


def test_gap_exact_300_persists_300_and_usable():
    a = S - timedelta(seconds=400)
    # need delta strictly > 90 to be a gap; use interval 60,factor 1.5 -> boundary 90
    g = compute_gap_summary([a, a + timedelta(seconds=300)], 60, 1.5)
    assert g.largest_gap_s == 300           # ceil(300.000000) == 300
    assert not (g.largest_gap_s > 300)      # equal threshold -> usable


def test_gap_300_000001_persists_301():
    a = S - timedelta(seconds=400)
    g = compute_gap_summary([a, a + timedelta(seconds=300, microseconds=1)], 60, 1.5)
    assert g.largest_gap_s == 301
    assert g.largest_gap_s > 300            # exceeds


def test_largest_gap_equal_threshold_remains_usable():
    a = S - timedelta(seconds=400)
    snap = compute_data_health_snapshot(
        _req(observations=[_obs(a), _obs(a + timedelta(seconds=300))],
             thresholds=_thr(max_usable_gap_s=300)))
    assert snap.largest_gap_s == 300 and snap.is_usable is True


def test_largest_gap_over_threshold_unusable():
    a = S - timedelta(seconds=400)
    snap = compute_data_health_snapshot(
        _req(observations=[_obs(a), _obs(a + timedelta(seconds=300, microseconds=1))],
             thresholds=_thr(max_usable_gap_s=300)))
    assert snap.largest_gap_s == 301 and snap.is_usable is False
    assert derive_data_health_status(
        snap, live_supported=True, coverage_type="full", connection_up=None,
        max_usable_gap_s=300) == "gap_exceeded"


def test_liquidations_never_run_continuous_gap_logic():
    obs = [_obs(S - timedelta(seconds=3600 * i), metric="liquidations")
           for i in range(1, 5)]  # huge deltas that WOULD be gaps for continuous
    snap = compute_data_health_snapshot(_liq_req(observations=obs, connection_up=True))
    assert snap.gap_count == 0 and snap.largest_gap_s is None


# ============================================================================
# J. Status / usability precedence
# ============================================================================
def test_not_available_beats_everything():
    # stale + gap facts present, but not live_supported -> not_available
    snap = compute_data_health_snapshot(_req(live_supported=False, observations=[]))
    assert snap.is_usable is False
    assert derive_data_health_status(
        snap, live_supported=False, coverage_type="full", connection_up=None,
        max_usable_gap_s=300) == "not_available"


def test_coverage_unavailable_is_not_available():
    snap = compute_data_health_snapshot(_req(coverage_type="unavailable"))
    assert derive_data_health_status(
        snap, live_supported=True, coverage_type="unavailable", connection_up=None,
        max_usable_gap_s=300) == "not_available"


def test_disconnected_liquidations():
    snap = compute_data_health_snapshot(_liq_req(connection_up=False))
    assert snap.is_usable is False
    assert derive_data_health_status(
        snap, live_supported=True, coverage_type="full", connection_up=False,
        max_usable_gap_s=300) == "disconnected"


def test_connection_unknown_liquidations():
    snap = compute_data_health_snapshot(_liq_req(connection_up=None))
    assert snap.is_usable is False
    assert derive_data_health_status(
        snap, live_supported=True, coverage_type="full", connection_up=None,
        max_usable_gap_s=300) == "connection_unknown"


def test_quiet_connected_liquidations_ok():
    snap = compute_data_health_snapshot(_liq_req(connection_up=True, observations=[]))
    assert snap.is_usable is True
    assert snap.last_event_at is None and snap.is_stale is False
    assert derive_data_health_status(
        snap, live_supported=True, coverage_type="full", connection_up=True,
        max_usable_gap_s=300) == "ok"


def test_no_data_status():
    snap = compute_data_health_snapshot(_req(observations=[]))
    assert derive_data_health_status(
        snap, live_supported=True, coverage_type="full", connection_up=None,
        max_usable_gap_s=300) == "no_data"


def test_stale_beats_gap_exceeded_when_both_true():
    # newest event stale AND an interior gap exceeded; stale wins (higher precedence)
    a = S - timedelta(seconds=86_000)
    obs = [_obs(a), _obs(a + timedelta(seconds=300, microseconds=1)),
           _obs(S - timedelta(seconds=200))]  # newest is 200s old > 120 budget
    snap = compute_data_health_snapshot(
        _req(observations=obs, thresholds=_thr(max_usable_gap_s=300)))
    assert snap.is_stale is True
    assert snap.largest_gap_s is not None and snap.largest_gap_s > 300
    assert derive_data_health_status(
        snap, live_supported=True, coverage_type="full", connection_up=None,
        max_usable_gap_s=300) == "stale"


def test_ok_status():
    snap = compute_data_health_snapshot(_req())
    assert derive_data_health_status(
        snap, live_supported=True, coverage_type="full", connection_up=None,
        max_usable_gap_s=300) == "ok"
    assert snap.is_usable is True


# ----- derive_data_health_status public-helper input validation --------------
def _ok_snap():
    return compute_data_health_snapshot(_req())


def test_derive_status_rejects_non_snapshot():
    with pytest.raises(DataQualityError):
        derive_data_health_status(object(), live_supported=True, coverage_type="full",
                                  connection_up=None, max_usable_gap_s=300)


def test_derive_status_rejects_non_bool_live_supported():
    with pytest.raises(DataQualityError):
        derive_data_health_status(_ok_snap(), live_supported=1, coverage_type="full",
                                  connection_up=None, max_usable_gap_s=300)


@pytest.mark.parametrize("cov", ["garbage", "", "FULL", "partial"])
def test_derive_status_rejects_bad_coverage_type(cov):
    with pytest.raises(DataQualityError):
        derive_data_health_status(_ok_snap(), live_supported=True, coverage_type=cov,
                                  connection_up=None, max_usable_gap_s=300)


@pytest.mark.parametrize("conn", ["down", 1, 0, "True"])
def test_derive_status_rejects_bad_connection_up(conn):
    with pytest.raises(DataQualityError):
        derive_data_health_status(_ok_snap(), live_supported=True, coverage_type="full",
                                  connection_up=conn, max_usable_gap_s=300)


@pytest.mark.parametrize("bad", [0, -1, True, 300.0, "300", None])
def test_derive_status_rejects_bad_max_usable_gap_s(bad):
    with pytest.raises(DataQualityError):
        derive_data_health_status(_ok_snap(), live_supported=True, coverage_type="full",
                                  connection_up=None, max_usable_gap_s=bad)


def test_derive_status_rejects_metric_not_in_allow_list():
    # a hand-forged snapshot carrying a non-health metric must be rejected
    bad = dataclasses.replace(_ok_snap(), metric="mark_price")
    with pytest.raises(DataQualityError):
        derive_data_health_status(bad, live_supported=True, coverage_type="full",
                                  connection_up=None, max_usable_gap_s=300)


def test_healthy_live_okx_oi_unsupported_history_still_usable():
    # §13.15 ex.11: OKX open_interest, historical_supported=False, healthy 15s poll
    ts = datetime(2026, 7, 22, 0, 0, 45, tzinfo=UTC)
    obs = [_obs(ts - timedelta(seconds=15 * i), exchange="okx", metric="open_interest")
           for i in range(1, 20)]
    snap = compute_data_health_snapshot(_req(
        exchange="okx", metric="open_interest", snapshot_ts=ts,
        thresholds=_thr(cadence_s=15), expected_interval_s=15, expected_freshness_s=30,
        historical_supported=False, backfill_status="not_applicable",
        coverage_type="snapshot", observations=obs))
    assert snap.backfill_status == "not_applicable"
    assert snap.is_usable is True
    assert derive_data_health_status(
        snap, live_supported=True, coverage_type="snapshot", connection_up=None,
        max_usable_gap_s=300) == "ok"


# ============================================================================
# K. Determinism / versioning
# ============================================================================
def test_replay_identical_inputs_identical_output():
    req1 = _req()
    req2 = _req()
    assert compute_data_health_snapshot(req1) == compute_data_health_snapshot(req2)


def test_same_raw_data_two_calc_versions_only_expected_differences():
    # identical live history; config A usable, config B gap_exceeded (max_usable_gap_s 150).
    # One interior 200s gap; newest bar is fresh (60s old).
    obs = [_obs(S - timedelta(seconds=60)), _obs(S - timedelta(seconds=120)),
           _obs(S - timedelta(seconds=320)), _obs(S - timedelta(seconds=380))]
    common = dict(observations=obs)
    snap_a = compute_data_health_snapshot(_req(
        thresholds=_thr(max_usable_gap_s=300), config_hash="c" * 64,
        calculation_version="1" * 16, **common))
    snap_b = compute_data_health_snapshot(_req(
        thresholds=_thr(max_usable_gap_s=150), config_hash="d" * 64,
        calculation_version="2" * 16, **common))
    # same raw-derived facts
    assert snap_a.last_event_at == snap_b.last_event_at
    assert snap_a.largest_gap_s == snap_b.largest_gap_s == 200
    assert snap_a.lateness_ms == snap_b.lateness_ms
    # only config/version-dependent divergence
    assert snap_a.is_usable is True and snap_b.is_usable is False
    assert snap_a.calculation_version != snap_b.calculation_version


def test_no_source_mode_or_historical_mode_path():
    # There is no request/observation/output field enabling a second historical
    # snapshot under the same identity -> one live-health row per PK.
    for model in (DataQualityRequest, DataQualityObservation, DataHealthSnapshot):
        names = {f.name for f in dataclasses.fields(model)}
        assert "source_mode" not in names
        assert not any("historical_mode" in n for n in names)


def test_continuous_metric_set_is_exactly_four():
    assert CONTINUOUS_METRICS == {"ohlcv", "taker_flow", "open_interest", "funding"}
    assert EVENT_DRIVEN_METRICS == {"liquidations"}
