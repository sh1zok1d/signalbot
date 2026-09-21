"""Focused Discovery Sprint 01 tests. Synthetic fixtures only.

Does not import MARKET confirmatory lifecycle machinery, does not create
MARKET-07, and does not require local CORE parquet.
"""

from __future__ import annotations

import inspect
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from scripts.research.discovery_sprint_01 import common as C
from scripts.research.discovery_sprint_01.d2_abstention_tail_risk import (
    classify_d2,
    evaluate_rule_1,
    evaluate_rule_2,
    run_d2,
)
from scripts.research.discovery_sprint_01.d3_path_morphology import (
    SEARCH_SURFACE as D3_SURFACE,
    classify_d3,
    evaluate_functionals,
    run_d3,
)
from scripts.research.discovery_sprint_01.d4_btc_eth_relative_structure import (
    SEARCH_SURFACE as D4_SURFACE,
    evaluate_rolling_correlation,
    refuse_lead_lag,
    run_d4,
)
from scripts.research.discovery_sprint_01.d5_composed_decision import (
    composed_or_mask,
    evaluate_d5_same_window,
    run_d5,
)
from scripts.research.market_06_cross_venue_dislocation_parsers import PerpBar


UTC = timezone.utc
REPO = Path(__file__).resolve().parents[2]


def _bar(open_ms: int, price: float, *, high: float | None = None, low: float | None = None) -> PerpBar:
    return PerpBar(
        open_time_ms=int(open_ms),
        open=float(price),
        high=float(price if high is None else high),
        low=float(price if low is None else low),
        close=float(price),
    )


def _fill_perp(start: datetime, n_bars: int, *, price0: float = 100.0, drift: float = 0.0001) -> dict[int, PerpBar]:
    t = C.ms_from_utc(start)
    px = price0
    out: dict[int, PerpBar] = {}
    for i in range(n_bars):
        px = max(1.0, px * (1.0 + drift * math.sin(i / 11.0)))
        hi = px * 1.002
        lo = px * 0.998
        out[t] = PerpBar(open_time_ms=t, open=px, high=hi, low=lo, close=px)
        t += C.BAR_MS
    return out


def _row(
    t: datetime,
    *,
    rv: float,
    severity: float,
    year: int | None = None,
    z: float | None = None,
    entry: float = 100.0,
    closes: tuple[float, ...] | None = None,
    ret: float = 0.01,
    side: float = 1.0,
) -> C.DiscoveryRow:
    if closes is None:
        closes = tuple(entry * (1.0 + 0.001 * k) for k in range(C.FUTURE_BARS))
    return C.DiscoveryRow(
        t_ms=C.ms_from_utc(t),
        year=int(year if year is not None else t.year),
        rv=float(rv),
        ret=float(ret),
        side=float(side),
        severity=float(severity),
        entry_open=float(entry),
        future_closes=closes,
        z=z,
    )


def test_preflight_flags_absent_core_and_present_m06() -> None:
    report = C.preflight_local_data(REPO)
    assert report["CORE_BTC_SNAPSHOT"] == C.CORE_BTC_SNAPSHOT
    assert report["CORE_ETH_SNAPSHOT"] == C.CORE_ETH_SNAPSHOT
    assert report["M06_SNAPSHOT"] == C.M06_SNAPSHOT
    assert report["BTC_DATA_PRESENT"] is False
    assert report["ETH_DATA_PRESENT"] is False
    assert report["M06_CROSS_VENUE_DATA_PRESENT"] is True


def test_protected_partition_refusal(tmp_path: Path) -> None:
    bad = tmp_path / "canonical" / "1m" / "monthly" / "2025-01.parquet"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"nope")
    with pytest.raises(C.ProtectedYearRefused):
        C.assert_openable(bad)
    also_bad = tmp_path / "BTCUSDT-5m-2026-02.zip"
    also_bad.write_bytes(b"nope")
    with pytest.raises(C.ProtectedYearRefused):
        C.open_bytes(also_bad, C.OpenedFileLog(), repo_root_path=tmp_path)
    spanning = tmp_path / "canonical" / "5m" / "bars.parquet"
    spanning.parent.mkdir(parents=True)
    spanning.write_bytes(b"nope")
    with pytest.raises(C.ProtectedYearRefused):
        C.assert_openable(spanning)


def test_iter_decision_times_skips_dec31_and_stops_before_2025() -> None:
    times = C.iter_discovery_decision_times(
        datetime(2024, 12, 29, 0, 5, tzinfo=UTC),
        datetime(2025, 1, 1, tzinfo=UTC),
    )
    assert [t.day for t in times] == [29, 30]
    assert all(t.year == 2024 for t in times)
    with pytest.raises(C.ProtectedYearRefused):
        C.iter_discovery_decision_times(
            datetime(2025, 1, 1, 0, 5, tzinfo=UTC),
            datetime(2025, 1, 3, tzinfo=UTC),
        )


def test_d2_rate_matched_control_matches_count_and_year() -> None:
    years = [2020] * 10 + [2021] * 10 + [2022] * 10
    abstain = np.zeros(30, dtype=bool)
    abstain[0] = True
    abstain[5] = True
    abstain[12] = True
    abstain[25] = True
    abstain[26] = True
    reps = C.rate_matched_random_abstention(years, abstain, seed=C.D2_RANDOM_CONTROL_SEED, n_replicates=32)
    assert len(reps) == 32
    year_arr = np.asarray(years)
    for rep in reps:
        assert int(rep.sum()) == int(abstain.sum())
        for year in (2020, 2021, 2022):
            assert int(rep[year_arr == year].sum()) == int(abstain[year_arr == year].sum())
    other = C.rate_matched_random_abstention(years, abstain, seed=C.D2_RANDOM_CONTROL_SEED, n_replicates=32)
    assert [r.tolist() for r in reps] == [r.tolist() for r in other]


def test_d2_per_rule_interval_enforcement() -> None:
    early = _row(datetime(2021, 6, 1, 0, 5, tzinfo=UTC), rv=0.1, severity=0.02, z=3.0)
    legal = _row(datetime(2022, 3, 1, 0, 5, tzinfo=UTC), rv=0.1, severity=0.02, z=3.0)
    with pytest.raises(ValueError, match="RULE_2_INTERVAL_VIOLATION"):
        evaluate_rule_2([early], n_replicates=4)
    evaluate_rule_2([legal], n_replicates=4)
    evaluate_rule_1(
        [_row(datetime(2020, 3, 1, 0, 5, tzinfo=UTC), rv=0.2, severity=0.01)],
        n_replicates=4,
    )


def test_d2_rv_rule_uses_trailing_p90_and_classifies_without_core() -> None:
    start = datetime(2020, 2, 1, 0, 5, tzinfo=UTC)
    rows = []
    for i in range(260):
        t = start + timedelta(days=i)
        if t.month == 12 and t.day == 31:
            continue
        rv = 0.01 if i < 250 else 1.0
        rows.append(_row(t, rv=rv, severity=0.05 if i >= 250 else 0.01, year=t.year))
    result = evaluate_rule_1(rows, n_replicates=16)
    assert result["RULE"] == "RV_ABSTENTION"
    assert result["ABSTAIN_COUNT"] > 0
    blocked = classify_d2({}, missing=["CORE_BTC_BINANCE_V0_MONTHLY_PARQUET"])
    assert blocked == "BLOCKED_MISSING_LOCAL_DATA"


def test_d3_exactly_three_functionals_and_no_high_low() -> None:
    assert D3_SURFACE == [
        "MAX_UPSIDE_CLOSE_24H",
        "MAX_DOWNSIDE_CLOSE_24H",
        "TIME_TO_MAX_ABS_CLOSE_EXCURSION",
    ]
    source = inspect.getsource(C.close_path_functionals) + inspect.getsource(run_d3)
    assert "bar.high" not in source
    assert "bar.low" not in source
    assert "btc_side_from_ret" not in inspect.getsource(run_d3)
    assert "PATH_ASYMMETRY" not in D3_SURFACE
    entry = 100.0
    closes = [100.0] * C.FUTURE_BARS
    closes[10] = 110.0
    closes[20] = 90.0
    computed = C.close_path_functionals(entry, closes)
    assert computed["MAX_UPSIDE_CLOSE_24H"] == pytest.approx(0.10)
    assert computed["MAX_DOWNSIDE_CLOSE_24H"] == pytest.approx(0.10)
    assert computed["TIME_TO_MAX_ABS_CLOSE_EXCURSION"] == 10.0
    never_up = C.close_path_functionals(100.0, [99.0] * C.FUTURE_BARS)
    assert never_up["MAX_UPSIDE_CLOSE_24H"] == 0.0
    assert never_up["MAX_DOWNSIDE_CLOSE_24H"] > 0.0


def test_d3_utc_slot_bootstrap_preserves_slots() -> None:
    block = 12
    n_slots = C.FUTURE_BARS // block
    marker = np.full(block, 0.5)
    other = np.zeros(block)
    pools = []
    for slot in range(n_slots):
        if slot == 3:
            pools.append(np.stack([marker, marker], axis=0))
        else:
            pools.append(np.stack([other, other], axis=0))
    paths = C.stratified_block_bootstrap_paths(pools, n_paths=5, seed=C.D3_NULL_SURROGATE_SEED)
    for path in paths:
        rets = C.path_log_returns(1.0, path)
        assert np.allclose(rets[3 * block : 4 * block], marker)
        assert np.allclose(rets[0:block], other)


def test_d3_functional_evaluation_deterministic() -> None:
    start = datetime(2020, 3, 1, 0, 5, tzinfo=UTC)
    rows = []
    for i in range(40):
        t = start + timedelta(days=i)
        closes = tuple(100.0 + 0.2 * math.sin((i + k) / 7.0) for k in range(C.FUTURE_BARS))
        rows.append(_row(t, rv=0.1, severity=0.01, closes=closes, year=t.year))
    a = evaluate_functionals(rows, n_replicates=6)
    b = evaluate_functionals(rows, n_replicates=6)
    assert a["FUNCTIONALS"] == list(C.D3_FUNCTIONALS)
    assert a["FUNCTIONAL_COUNT"] == 3
    for name in C.D3_FUNCTIONALS:
        assert a[name]["EMPIRICAL_MEAN"] == b[name]["EMPIRICAL_MEAN"]
        assert a[name]["SURROGATE_MEAN_MEDIAN"] == b[name]["SURROGATE_MEAN_MEDIAN"]


def test_d4_only_rolling_path_executable_and_practical_formula() -> None:
    assert D4_SURFACE == ["ROLLING_CORRELATION_90D"]
    with pytest.raises(C.DeferredFunctionalError):
        refuse_lead_lag()
    with pytest.raises(C.DeferredFunctionalError):
        run_d4(implementation_commit="TEST", execute_lead_lag=True)
    observed_range = 0.40
    null_median = 0.10
    assert C.practical_excess_range(observed_range, null_median) == pytest.approx(0.30)
    rng = np.random.default_rng(C.D4_NULL_SEED)
    x = rng.normal(size=120)
    y = 0.2 * x + rng.normal(size=120)
    years = np.array([2020] * 40 + [2021] * 40 + [2022] * 40)
    report = evaluate_rolling_correlation(x, y, years, n_replicates=12)
    assert report["LEAD_LAG_1DAY_EXECUTED"] is False
    assert report["LEAD_LAG_1DAY_STATUS"] == "DEFERRED_FROM_SPRINT_01"
    assert report["PRACTICAL_EXCESS_RANGE"] == pytest.approx(
        report["OBSERVED_CORRELATION_RANGE"] - report["NULL_RANGE_MEDIAN"]
    )


def test_d5_same_window_component_comparison() -> None:
    start = datetime(2022, 2, 1, 0, 5, tzinfo=UTC)
    all_rows = []
    for i in range(280):
        t = start + timedelta(days=i)
        if t.month == 12 and t.day == 31:
            continue
        if t.year >= 2025:
            break
        rv = 1.0 if i in {260, 261, 262} else 0.01
        z = 3.0 if i in {270, 271} else 0.1
        severity = 0.20 if i in {260, 261, 262, 270, 271} else 0.01
        all_rows.append(_row(t, rv=rv, severity=severity, z=z, year=t.year))
    report = evaluate_d5_same_window(all_rows, n_replicates=8)
    composed = report["COMPOSED"]
    assert composed["COMPONENT_A_DELTA_FOR_D5"] is not None
    assert composed["COMPONENT_B_DELTA_FOR_D5"] is not None
    assert composed["D5_DELTA"] is not None
    expected_beats = composed["D5_DELTA"] > max(
        composed["COMPONENT_A_DELTA_FOR_D5"],
        composed["COMPONENT_B_DELTA_FOR_D5"],
    )
    assert composed["COMPOSED_BEATS_COMPONENTS"] is expected_beats
    mask_a = C.rv_abstention_mask(all_rows)
    mask_b = C.dislocation_abstention_mask(all_rows)
    assert int(composed_or_mask(mask_a, mask_b).sum()) >= int(mask_a.sum())
    assert int(composed_or_mask(mask_a, mask_b).sum()) >= int(mask_b.sum())


def test_seeds_are_frozen() -> None:
    assert C.D2_RANDOM_CONTROL_SEED == 20260921102
    assert C.D3_NULL_SURROGATE_SEED == 20260921103
    assert C.D4_NULL_SEED == 20260921104
    assert C.D5_RANDOM_CONTROL_SEED == 20260921105


def test_no_market07_or_confirmatory_lifecycle_dependency() -> None:
    folder = REPO / "scripts" / "research" / "discovery_sprint_01"
    for path in folder.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "market_06_execution_lifecycle" not in text
        assert "ONE_SHOT_EXECUTION_AUTHORITY" not in text
        assert "reconstruct_canonical_dataset" not in text
        assert "create_market_07" not in text.lower()
        if "MARKET_07_CREATED" in text:
            assert "MARKET_07_CREATED\": False" in text or "MARKET_07_CREATED = False" in text
        assert "claim_or_reservation" not in text.lower()


def test_batch_blocked_without_core(tmp_path: Path) -> None:
    payload = run_d2(
        implementation_commit="TEST",
        output_dir=tmp_path,
        repo=REPO,
        n_replicates=4,
        m06_perp={},
        m06_spot={},
    )
    assert payload["TERMINAL_CLASSIFICATION"] == "BLOCKED_MISSING_LOCAL_DATA"
    assert payload["PROTECTED_2025_OPENED"] is False
    d3 = run_d3(implementation_commit="TEST", output_dir=tmp_path, repo=REPO, n_replicates=2, run_companions=False)
    assert d3["TERMINAL_CLASSIFICATION"] == "BLOCKED_MISSING_LOCAL_DATA"
    d4 = run_d4(implementation_commit="TEST", output_dir=tmp_path, repo=REPO, n_replicates=2)
    assert d4["TERMINAL_CLASSIFICATION"] == "BLOCKED_MISSING_LOCAL_DATA"
    d5 = run_d5(implementation_commit="TEST", output_dir=tmp_path, repo=REPO, n_replicates=2)
    assert d5["TERMINAL_CLASSIFICATION"] == "BLOCKED_MISSING_LOCAL_DATA"


def test_d2_rule2_executes_on_injected_m06_like_bars() -> None:
    start = datetime(2022, 1, 1, tzinfo=UTC)
    n_bars = 80 * 288
    perp = _fill_perp(start, n_bars, price0=40000.0, drift=0.0002)
    spot = {}
    for i, (ts, bar) in enumerate(sorted(perp.items())):
        spot[ts] = bar.close * (0.998 + 0.004 * math.sin(i / 50.0))
    for ts, bar in list(perp.items())[50 * 288 : 52 * 288]:
        perp[ts] = PerpBar(bar.open_time_ms, bar.open, bar.high * 1.08, bar.low, bar.close * 1.06)
    payload = run_d2(
        implementation_commit="TEST",
        core_perp=None,
        m06_perp=perp,
        m06_spot=spot,
        n_replicates=8,
        repo=REPO,
    )
    assert payload["TERMINAL_CLASSIFICATION"] == "BLOCKED_MISSING_LOCAL_DATA"
    assert "DISLOCATION_ABSTENTION" in payload["PRIMARY_METRICS"]
    assert payload["SEARCH_SURFACE_ATTEMPTED"] == ["RV_ABSTENTION", "DISLOCATION_ABSTENTION"]
