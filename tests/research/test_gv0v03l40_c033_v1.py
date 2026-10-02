"""C033 primary-state count and V1 planning. No market outcome is computed."""

import numpy as np

from scripts.research.gv0v03l40_c033_v1 import (
    COMPONENTS,
    aggregate_15m,
    build_planning,
    card_components_unchanged,
    label_primary_state,
    legal_months,
    pinned_sources,
    seal_and_compile,
    thin_first_in_6h,
    _rolling_sample_std,
)
from scripts.research.generator_v0.feasibility_contract_v1 import validate_planning_v1

BUCKET = 15 * 60 * 1000


def _bars(n, *, open_px=100.0, step=0.0, taker=0.5, trades=10.0, quote=100.0, wick="none"):
    open_ms = np.arange(n, dtype=np.int64) * BUCKET
    open_ = np.full(n, open_px)
    close = open_ + step
    high = np.maximum(open_, close)
    low = np.minimum(open_, close)
    if wick == "up":
        high = close + 0.5 * np.maximum(close - low, 1.0)
    elif wick == "down":
        low = close - 0.5 * np.maximum(high - close, 1.0)
    return {
        "open_ms": open_ms,
        "end_ms": open_ms + BUCKET,
        "open": open_.astype(float),
        "high": high.astype(float),
        "low": low.astype(float),
        "close": close.astype(float),
        "quote": np.full(n, quote),
        "trades": np.full(n, trades),
        "taker_buy_quote": np.full(n, taker * quote),
    }


def test_legal_months_stop_before_2025():
    months = legal_months()
    assert months[0] == "2020-01" and months[-1] == "2024-12"
    assert all(m < "2025-01" for m in months)
    specs = pinned_sources()
    assert {row["SYMBOL"] for row in specs} == {"BTCUSDT", "ETHUSDT"}
    assert all("2025" not in row["URL"] and "2026" not in row["URL"] for row in specs)
    assert len(specs) == 120


def test_incomplete_15m_bucket_is_dropped():
    minutes = np.array([[i * 60_000, 1, 2, 0.5, 1.5, 10, 3, 4] for i in range(14)], dtype=float)
    out = aggregate_15m(minutes)
    assert len(out["open_ms"]) == 0


def test_rolling_std_matches_numpy_and_excludes_the_current_bar():
    values = np.linspace(0.01, 0.2, 12)
    got = _rolling_sample_std(values, 5)
    for i in range(5, len(values)):
        assert np.isclose(got[i], np.std(values[i - 5:i], ddof=1))


def test_future_price_does_not_change_the_label_at_t():
    n = 40
    btc = _bars(n, step=0.01)
    eth = _bars(n, step=0.01)
    # A quiet history, then one large up bar with every footprint.
    noise = np.linspace(-0.2, 0.2, n - 1)
    btc["close"][:-1] = btc["open"][:-1] + noise
    btc["high"][:-1] = np.maximum(btc["open"][:-1], btc["close"][:-1])
    btc["low"][:-1] = np.minimum(btc["open"][:-1], btc["close"][:-1])
    eth["close"][:-1] = eth["open"][:-1] + noise
    eth["high"][:-1] = np.maximum(eth["open"][:-1], eth["close"][:-1])
    eth["low"][:-1] = np.minimum(eth["open"][:-1], eth["close"][:-1])
    btc["close"][-1] = 130
    btc["high"][-1] = 160
    btc["low"][-1] = 100
    btc["taker_buy_quote"][-1] = 99
    btc["trades"][-1] = 1000
    eth["close"][-1] = 130
    eth["high"][-1] = 130
    eth["low"][-1] = 100
    kwargs = dict(taker_bars=20, sigma_bars=10, taker_span_ms=20 * BUCKET, sigma_span_ms=10 * BUCKET)
    before = label_primary_state(btc, eth, **kwargs)
    later = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in btc.items()}
    # A bar after T cannot exist inside this series; perturbing an earlier future
    # relative to a middle index is the lookahead check.
    mid = 30
    later["close"][mid + 1:] *= 10
    later["high"][mid + 1:] *= 10
    later["low"][mid + 1:] *= 10
    after = label_primary_state(later, eth, **kwargs)
    assert before["shock"][mid] == after["shock"][mid]
    assert before["all4"][mid] == after["all4"][mid]
    assert before["all4"][-1]


def test_six_hour_thinning_keeps_the_first_event():
    end = np.array([0, 60_000, 6 * 60 * 60 * 1000], dtype=np.int64)
    mask = np.array([True, True, True])
    kept = thin_first_in_6h(end, mask)
    assert kept.tolist() == [True, False, True]


def test_planning_validates_and_compiles_without_outcomes():
    assert card_components_unchanged()
    counts = {
        "TOTAL_ELIGIBLE_SHOCKS": 8000,
        "TOTAL_ALL4_EVENTS": 400,
        "KEPT_ELIGIBLE_SHOCKS": 5000,
        "COUNT_BY_YEAR": {"2020": 800, "2021": 1000, "2022": 1100, "2023": 1000, "2024": 1100},
        "DISTINCT_DAYS": 900,
        "DEPENDENCE_CLUSTER_COUNT": 5000,
    }
    planning = build_planning(counts)
    validate_planning_v1(planning)
    assert planning["COMPONENTS"] == COMPONENTS
    assert planning["PRIMARY_CELLS"][0]["REGIME"] == "ALL_ELIGIBLE_BTC_15M_SHOCKS"
    assert planning["PRIMARY_FREEZE"]["PRIMARY_CELLS"] == 1
    proposal, result = seal_and_compile(planning)
    assert proposal["COMPILER_SCHEMA_VERSION"] == "GV0R02_SCHEMA_V1"
    assert result["MARKET_OUTCOMES_OPENED"] is False
    assert result["PROTECTED_2025_VALUES_OPENED"] is False
    assert result["PROTECTED_2026_VALUES_OPENED"] is False
    assert "FORCED_FLOW_ALL4_JOINT" not in planning["VARIABLE_ROLES"]["NUISANCE_BASELINE_VARIABLES"]
