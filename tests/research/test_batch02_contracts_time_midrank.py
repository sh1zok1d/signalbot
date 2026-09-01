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
