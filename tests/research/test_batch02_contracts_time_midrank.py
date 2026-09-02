from __future__ import annotations

import numpy as np
import pytest

from scripts.research.lib.batch02_contracts import (
    Batch02ContractError,
    rolling_midrank_percentile,
)


def test_time_window_midrank_uses_only_prior_records_inside_clock_window():
    day = 86_400_000
    values = np.array([1.0, 3.0, 2.0, 4.0])
    times = np.array([0, day, 2 * day, 40 * day], dtype=np.int64)
    out = rolling_midrank_percentile(
        values,
        timestamps_ms=times,
        lookback_ms=30 * day,
    )
    assert np.isnan(out[0])
    assert out[1] == 1.0
    assert out[2] == 0.5
    assert np.isnan(out[3])


def test_time_window_midrank_ties_use_midrank():
    values = np.array([2.0, 2.0, 2.0])
    times = np.array([1, 2, 3], dtype=np.int64)
    out = rolling_midrank_percentile(values, timestamps_ms=times, lookback_ms=10)
    assert np.isnan(out[0])
    assert out[1] == 0.5
    assert out[2] == 0.5


def test_time_window_midrank_rejects_non_increasing_clock():
    with pytest.raises(Batch02ContractError, match="strictly increasing"):
        rolling_midrank_percentile(
            np.array([1.0, 2.0]),
            timestamps_ms=np.array([2, 2], dtype=np.int64),
            lookback_ms=10,
        )


def test_fixed_count_midrank_contract_is_unchanged():
    out = rolling_midrank_percentile(np.array([1.0, 2.0, 3.0]), window=2)
    assert np.isnan(out[0])
    assert np.isnan(out[1])
    assert out[2] == 1.0


def test_midrank_requires_exactly_one_mode():
    with pytest.raises(Batch02ContractError, match="exactly one"):
        rolling_midrank_percentile(np.array([1.0]), window=1, lookback_ms=10)


# ---------------------------------------------------------------------------
# Frozen causal semantics of the time-window mode. These pin the behaviour the
# current implementation documents; they are not a redefinition of it.
# ---------------------------------------------------------------------------


def test_reference_exactly_lookback_old_is_inside_the_window():
    """The trailing window boundary is inclusive.

    The purge drops a reference only when its timestamp is strictly older than
    `current_time - lookback_ms`, so a reference at exactly `lookback_ms` old
    is still an active reference. Pinning this prevents the boundary from
    silently flipping to exclusive.
    """
    day = 86_400_000
    lookback = 30 * day
    values = np.array([1.0, 5.0])
    times = np.array([0, lookback], dtype=np.int64)
    out = rolling_midrank_percentile(
        values,
        timestamps_ms=times,
        lookback_ms=lookback,
    )
    assert out[1] == 1.0  # the exactly-lookback-old reference is still counted


def test_reference_one_millisecond_older_than_lookback_leaves_the_window():
    day = 86_400_000
    lookback = 30 * day
    values = np.array([1.0, 5.0])
    times = np.array([0, lookback + 1], dtype=np.int64)
    out = rolling_midrank_percentile(
        values,
        timestamps_ms=times,
        lookback_ms=lookback,
    )
    # The only reference has aged out, so the window is empty -> unavailable.
    assert np.isnan(out[1])


def test_non_finite_reference_inside_the_window_makes_the_score_unavailable():
    values = np.array([1.0, np.nan, 3.0, 4.0])
    times = np.array([1, 2, 3, 4], dtype=np.int64)
    out = rolling_midrank_percentile(values, timestamps_ms=times, lookback_ms=10)
    # index 2 and 3 both carry the NaN reference inside their active window.
    assert np.isnan(out[2])
    assert np.isnan(out[3])


def test_non_finite_reference_stops_poisoning_once_it_ages_out():
    """Unavailability from a NaN reference is scoped to the active window.

    A non-finite reference blocks scoring only while it is inside the trailing
    window; once it ages out the score becomes available again from the
    remaining finite references.
    """
    values = np.array([np.nan, 1.0, 2.0, 3.0])
    times = np.array([0, 10, 20, 30], dtype=np.int64)
    out = rolling_midrank_percentile(values, timestamps_ms=times, lookback_ms=15)
    assert np.isnan(out[0])  # no reference at all
    assert np.isnan(out[1])  # NaN at t=0 is inside [10-15, 10]
    # At t=20 the cutoff is 5, so the NaN at t=0 has aged out and the only
    # remaining reference is the finite 1.0 at t=10.
    assert out[2] == 1.0
    assert out[3] == 1.0


def test_non_finite_current_value_is_unavailable_but_not_a_reference():
    values = np.array([1.0, 2.0, np.nan])
    times = np.array([1, 2, 3], dtype=np.int64)
    out = rolling_midrank_percentile(values, timestamps_ms=times, lookback_ms=10)
    assert out[1] == 1.0
    assert np.isnan(out[2])


def test_current_record_is_excluded_from_its_own_reference_set():
    values = np.array([5.0, 5.0])
    times = np.array([1, 2], dtype=np.int64)
    out = rolling_midrank_percentile(values, timestamps_ms=times, lookback_ms=10)
    # If the current record were included, a lone equal reference would give a
    # different denominator; with exclusion the single prior tie gives 0.5.
    assert np.isnan(out[0])
    assert out[1] == 0.5


def test_no_future_record_can_change_an_earlier_score():
    values = np.array([1.0, 2.0, 3.0])
    times = np.array([1, 2, 3], dtype=np.int64)
    base = rolling_midrank_percentile(
        values, timestamps_ms=times, lookback_ms=10
    )
    changed = values.copy()
    changed[2] = -999.0
    after = rolling_midrank_percentile(
        changed, timestamps_ms=times, lookback_ms=10
    )
    assert np.array_equal(base[:2], after[:2], equal_nan=True)


def test_empty_reference_window_is_unavailable():
    values = np.array([1.0, 2.0])
    times = np.array([0, 1_000_000], dtype=np.int64)
    out = rolling_midrank_percentile(values, timestamps_ms=times, lookback_ms=5)
    assert np.isnan(out[0])
    assert np.isnan(out[1])
