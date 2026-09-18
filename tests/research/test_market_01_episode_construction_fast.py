"""Equivalence tests: frozen construct_episodes vs construct_episodes_fast.

Synthetic/unit fixtures only. Does not load CORE/OI snapshots, enumerate
real MARKET-01 outcomes, consume the reservation, or rerun confirmatory
classification.
"""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest

from scripts.research.market_01_episode_construction_fast import (
    construct_episodes_fast,
    episode_field_pairs,
)
from scripts.research.market_01_episode_construction_perf_bench import make_synthetic_views
from scripts.research.market_01_oi_expansion_weak_continuation_authority import (
    Market01ExecutionNotAuthorized,
)
from scripts.research.market_01_oi_expansion_weak_continuation_lib import (
    BAR_MS,
    CALENDAR_DAY_MS,
    COMMON_START_MS,
    FIVE_MS,
    OI_STALE_MS,
    THIRTY_M_MS,
    OiView,
    PriceView,
    SYNTHETIC_SNAPSHOT,
    close_at,
    construct_episodes,
    legal_oi_at,
    pre_vol_60,
)


def _price(n: int, start_open_ms: int, closes: np.ndarray) -> PriceView:
    open_ms = start_open_ms + np.arange(n, dtype=np.int64) * BAR_MS
    return PriceView(
        open_time_ms=open_ms,
        available_at_ms=open_ms + BAR_MS,
        close=np.asarray(closes, dtype=np.float64),
        snapshot_id=SYNTHETIC_SNAPSHOT,
    )


def _oi(n: int, start_create_ms: int, values: np.ndarray) -> OiView:
    create = start_create_ms + np.arange(n, dtype=np.int64) * FIVE_MS
    return OiView(
        create_time_ms=create,
        available_at_ms=create + FIVE_MS,
        sum_open_interest=np.asarray(values, dtype=np.float64),
        snapshot_id=SYNTHETIC_SNAPSHOT,
    )


def _assert_same(price: PriceView, oi: OiView) -> tuple[list, list]:
    frozen = construct_episodes(price, oi)
    fast = construct_episodes_fast(price, oi)
    episode_field_pairs(frozen, fast)
    return frozen, fast


def test_missing_oi_after_occupancy_matches_frozen():
    hist_start = COMMON_START_MS - 31 * CALENDAR_DAY_MS
    t = COMMON_START_MS + THIRTY_M_MS
    n = int((t + 90 * BAR_MS - hist_start) / BAR_MS) + 10
    closes = np.full(n, 100.0, dtype=np.float64)
    idx_end = (t - BAR_MS - hist_start) // BAR_MS
    closes[idx_end] = 100.0 * math.exp(0.08)
    price = _price(n, hist_start, closes)
    oi = _oi(1, hist_start, np.array([1.0]))
    frozen, fast = _assert_same(price, oi)
    occupying = [e for e in fast if e.occupies_slot]
    assert occupying
    assert occupying[0].qualifying_impulse is True
    assert occupying[0].confirmatory_eligible is False
    assert occupying[0].exclusion_reason == "missing_or_invalid_oi"
    assert frozen[0].impulse_end_t_ms == fast[0].impulse_end_t_ms


def test_overlap_suppression_matches_frozen():
    hist_start = COMMON_START_MS - 31 * CALENDAR_DAY_MS
    t0 = COMMON_START_MS + THIRTY_M_MS
    t1 = t0 + FIVE_MS
    n = int((t1 + 90 * BAR_MS - hist_start) / BAR_MS) + 10
    closes = np.full(n, 100.0, dtype=np.float64)
    for t in (t0, t1):
        idx_end = (t - BAR_MS - hist_start) // BAR_MS
        closes[idx_end] = 100.0 * math.exp(0.07)
    price = _price(n, hist_start, closes)
    oi_n = int((n * BAR_MS) / FIVE_MS)
    oi = _oi(oi_n, hist_start, np.full(oi_n, 10.0))
    frozen, fast = _assert_same(price, oi)
    occupying = [e for e in fast if e.occupies_slot]
    assert occupying
    first = occupying[0]
    skipped = [
        e
        for e in fast
        if e.exclusion_reason == "overlap_skip"
        and first.impulse_start_ms < e.impulse_start_ms < first.impulse_start_ms + 120 * BAR_MS
    ]
    assert skipped
    assert [e.exclusion_reason for e in frozen] == [e.exclusion_reason for e in fast]


def test_stale_and_missing_oi_clocks_match_frozen():
    hist_start = COMMON_START_MS - 31 * CALENDAR_DAY_MS
    t = COMMON_START_MS + THIRTY_M_MS
    n = int((t + 90 * BAR_MS - hist_start) / BAR_MS) + 10
    closes = np.full(n, 100.0, dtype=np.float64)
    idx_end = (t - BAR_MS - hist_start) // BAR_MS
    closes[idx_end] = 100.0 * math.exp(0.09)
    price = _price(n, hist_start, closes)
    # One native OI print, then a 6-minute gap so later clocks are stale.
    create = np.array([hist_start, t + 6 * BAR_MS], dtype=np.int64)
    oi = OiView(
        create_time_ms=create,
        available_at_ms=create + FIVE_MS,
        sum_open_interest=np.array([10.0, 12.0], dtype=np.float64),
        snapshot_id=SYNTHETIC_SNAPSHOT,
    )
    available0 = int(create[0] + FIVE_MS)
    assert legal_oi_at(oi, available0) == 10.0
    assert legal_oi_at(oi, available0 + OI_STALE_MS + 1) is None
    _assert_same(price, oi)


def test_rolling_thresholds_strata_pre_vol_outcomes_on_seeded_synthetic():
    price, oi = make_synthetic_views(
        n_days_hist=31, n_days_eval=0, seed=7, spike_every_5m=24, spike_log=0.02
    )
    # Trim eval to 8h after common start so frozen stays cheap while still
    # exercising occupancy, OI, strata, candidate/baseline, and outcomes.
    last_open = COMMON_START_MS + 8 * 60 * BAR_MS
    keep = price.open_time_ms <= last_open
    price = PriceView(
        open_time_ms=price.open_time_ms[keep],
        available_at_ms=price.available_at_ms[keep],
        close=price.close[keep],
        snapshot_id=SYNTHETIC_SNAPSHOT,
    )
    oi_keep = oi.available_at_ms <= last_open + FIVE_MS
    oi = OiView(
        create_time_ms=oi.create_time_ms[oi_keep],
        available_at_ms=oi.available_at_ms[oi_keep],
        sum_open_interest=oi.sum_open_interest[oi_keep],
        snapshot_id=SYNTHETIC_SNAPSHOT,
    )
    frozen, fast = _assert_same(price, oi)
    assert [e.impulse_end_t_ms for e in frozen] == [e.impulse_end_t_ms for e in fast]
    occupying = [e for e in fast if e.occupies_slot]
    assert occupying
    reasons = {e.exclusion_reason for e in fast}
    assert "overlap_skip" in reasons
    eligible = [e for e in fast if e.confirmatory_eligible]
    if eligible:
        assert any(e.candidate for e in eligible) or any(not e.candidate for e in eligible)
        assert all(e.pre_vol_60 is not None for e in eligible)
        assert all(e.stratum_id is not None for e in eligible)
        assert all(e.reversal_return is not None for e in eligible)
        t0 = eligible[0].impulse_end_t_ms
        assert eligible[0].pre_vol_60 == pre_vol_60(price, t0)
        assert eligible[0].impulse_return == pytest.approx(
            math.log(
                close_at(price, t0) / close_at(price, t0 - THIRTY_M_MS)
            )
        )


def test_gappy_1m_falls_back_and_still_matches():
    hist_start = COMMON_START_MS - 31 * CALENDAR_DAY_MS
    t = COMMON_START_MS + THIRTY_M_MS
    n = int((t + 90 * BAR_MS - hist_start) / BAR_MS) + 10
    closes = np.full(n, 100.0, dtype=np.float64)
    idx_end = (t - BAR_MS - hist_start) // BAR_MS
    closes[idx_end] = 100.0 * math.exp(0.08)
    price = _price(n, hist_start, closes)
    # Drop one interior bar so the 1m grid is not contiguous.
    mask = np.ones(n, dtype=bool)
    mask[n // 2] = False
    gappy = PriceView(
        open_time_ms=price.open_time_ms[mask],
        available_at_ms=price.available_at_ms[mask],
        close=price.close[mask],
        snapshot_id=SYNTHETIC_SNAPSHOT,
    )
    oi_n = int((n * BAR_MS) / FIVE_MS)
    oi = _oi(oi_n, hist_start, np.full(oi_n, 10.0))
    _assert_same(gappy, oi)


def test_bound_snapshot_still_refused_on_fast_path():
    price = _price(3, COMMON_START_MS, np.array([1.0, 1.0, 1.0]))
    oi = _oi(1, COMMON_START_MS, np.array([1.0]))
    bound = replace(
        price,
        snapshot_id="717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415",
    )
    with pytest.raises(Market01ExecutionNotAuthorized):
        construct_episodes_fast(bound, oi)


def test_32_day_profile_workload_field_equality():
    """Same generator as the throughput bench; 2 eval days, seed=1."""
    price, oi = make_synthetic_views(n_days_hist=30, n_days_eval=2, seed=1)
    frozen, fast = _assert_same(price, oi)
    assert len(frozen) == len(fast)
    assert any(e.occupies_slot for e in fast)
    assert any(e.exclusion_reason == "overlap_skip" for e in fast)
    eligible = [e for e in fast if e.confirmatory_eligible]
    assert eligible
    assert any(e.candidate for e in eligible)
    assert any(not e.candidate for e in eligible)
    assert all(e.stratum_id is not None for e in eligible)
    assert all(e.pre_vol_60 is not None for e in eligible)
    assert [e.impulse_end_t_ms for e in frozen] == [e.impulse_end_t_ms for e in fast]
