"""MARKET-03 implementation tests. Synthetic / fixture / handcrafted only.

Does not load bound MARKET-03 spot or funding scientific snapshots into
strategy logic, construct real MARKET-03 trades, or inspect real MDD.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.research.market_03_public_strategy_authority import (
    ALLOWED_TEST_ORIGINS,
    B2_06_SNAPSHOT_ID,
    EVALUATION_END_EXCLUSIVE,
    EVALUATION_START_INCLUSIVE,
    EXTERNAL_COMMIT,
    EXTERNAL_TREE,
    FROZEN_PREREG_JSON_SHA256,
    FROZEN_PREREG_MD_SHA256,
    FUNDING_DATA_SHA256,
    FUNDING_DATASET_ID,
    FUNDING_ROWS,
    FUNDING_SNAPSHOT_ID,
    MARKET_03_ARMED,
    MARKET_03_BOUND_EXECUTION_AUTHORIZED,
    PROTECTED_OOS_START,
    SPOT_DATA_SHA256,
    SPOT_SNAPSHOT_ID,
    STRICT_HISTORICAL_PUBLICATION_LATENCY,
    Market03AuthorityError,
    Market03BoundDataRefused,
    Market03ExecutionNotAuthorized,
    authenticate_frozen_prereg_bytes,
    inspect_market_03_authorization_state,
    refuse_bound_execution,
    refuse_bound_scientific_inputs,
    refuse_b2_06_as_authority,
)
from scripts.research.market_03_public_strategy_execute import (
    execute_bound_market_03,
    main as execute_main,
)
from scripts.research.market_03_public_strategy_lib import (
    AUTHOR_MDD_BASELINE,
    AUTHOR_MDD_FILTERED,
    CLASS_EXECUTION_INCOMPLETE,
    CLASS_EXECUTION_INVALID,
    CLASS_NOT_REPRODUCED_DIRECTION,
    CLASS_REPRODUCED_DIRECTION,
    EMA_PERIOD,
    FEE_PER_SIDE,
    FUNDING_MAX_PCT,
    STOPLOSS,
    advise_signals,
    classify_primary,
    crossed_above,
    crossed_below,
    descriptive_magnitude,
    ema_exit_level,
    evaluate_market_03_reproduction,
    funding_allows_entry,
    funding_series_from_observations,
    mdd_from_daily_equity,
    pinned_external_funding_features,
    populate_entry_trend,
    populate_indicators,
    risk_report,
    same_candle_exit_order,
    simulate_strategy,
    talib_ema,
    wallet_to_daily_equity,
)


REPO = Path(__file__).resolve().parents[2]
PREREG_MD = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.md"
PREREG_JS = REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json"
PINNED_METRICS = (
    REPO
    / "docs/research_data/MARKET_03_BTC_STRATEGY_LAB_B68A5518/source/research/metrics.py"
)
PINNED_FUNDING_STRAT = (
    REPO
    / "docs/research_data/MARKET_03_BTC_STRATEGY_LAB_B68A5518/source/user_data/strategies/EmaCrossFunding.py"
)
LIB = REPO / "scripts/research/market_03_public_strategy_lib.py"
AUTHORITY = REPO / "scripts/research/market_03_public_strategy_authority.py"
EXECUTE = REPO / "scripts/research/market_03_public_strategy_execute.py"

QTPYLIB_CROSS_VECTOR = [56, 97, 19, 76, 65, 25, 87, 91, 79, 79]
QTPYLIB_CROSS_LEVEL = 60
QTPYLIB_CROSSED_ABOVE = [False, True, False, True, False, False, True, False, False, False]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hourly(start: str, n: int, close: np.ndarray | None = None, volume: float = 1.0) -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="h", tz="UTC")
    if close is None:
        close = np.full(n, 100.0, dtype=np.float64)
    close = np.asarray(close, dtype=np.float64)
    return pd.DataFrame(
        {
            "date": idx,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.full(n, volume, dtype=np.float64),
        }
    )


def _load_pinned_metrics():
    spec = importlib.util.spec_from_file_location("market_03_pinned_metrics", PINNED_METRICS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _pinned_funding_snippet(candle_dates, funding: pd.Series) -> pd.DataFrame:
    """Exact EmaCrossFunding.py pandas body, inlined for EXACT_DIFFERENTIAL."""
    idx = pd.to_datetime(pd.Index(candle_dates), utc=True)
    fr = funding.sort_index()
    f = fr.reindex(idx, method="ffill")
    funding_3d = f.rolling(72, min_periods=24).mean()
    funding_pct = (
        pd.Series(funding_3d.to_numpy()).rolling(24 * 180, min_periods=24 * 30).rank(pct=True) * 100
    )
    return pd.DataFrame(
        {
            "funding": f.to_numpy(),
            "funding_3d": funding_3d.to_numpy(),
            "funding_pct": funding_pct.to_numpy(),
        }
    )


# ---------------------------------------------------------------------------
# Identity / fail-closed
# ---------------------------------------------------------------------------


def test_prereg_bytes_unchanged():
    authenticate_frozen_prereg_bytes()
    assert _sha256(PREREG_MD) == FROZEN_PREREG_MD_SHA256
    assert _sha256(PREREG_JS) == FROZEN_PREREG_JSON_SHA256


def test_authorization_remains_unarmed():
    state = inspect_market_03_authorization_state()
    assert state["MARKET_03_ARMED"] is False
    assert state["MARKET_03_BOUND_EXECUTION_AUTHORIZED"] is False
    assert state["IMPLEMENTATION_FROZEN"] is False
    assert state["CANONICAL_EXECUTIONS_AUTHORIZED"] == 0
    assert state["CANONICAL_EXECUTIONS_CONSUMED"] == 0
    assert state["PROTECTED_OOS_AUTHORIZED"] is False
    assert state["B2_06_EXECUTION_AUTHORIZED"] is False
    assert state["STRICT_HISTORICAL_PUBLICATION_LATENCY"] == "UNPROVEN"
    assert MARKET_03_ARMED is False
    assert MARKET_03_BOUND_EXECUTION_AUTHORIZED is False


def test_bound_execution_stub_raises():
    with pytest.raises(Market03ExecutionNotAuthorized):
        refuse_bound_execution()
    with pytest.raises(Market03ExecutionNotAuthorized):
        execute_bound_market_03()
    assert execute_main([]) == 2


def test_refuse_bound_snapshot_ids_and_b2_06():
    with pytest.raises(Market03BoundDataRefused):
        refuse_bound_scientific_inputs(
            origin="synthetic",
            spot_snapshot_id=SPOT_SNAPSHOT_ID,
        )
    with pytest.raises(Market03BoundDataRefused):
        refuse_bound_scientific_inputs(
            origin="synthetic",
            funding_snapshot_id=FUNDING_SNAPSHOT_ID,
        )
    with pytest.raises(Market03AuthorityError):
        refuse_b2_06_as_authority()
    with pytest.raises(Market03AuthorityError):
        refuse_bound_scientific_inputs(
            origin="synthetic",
            funding_snapshot_id=B2_06_SNAPSHOT_ID,
        )
    with pytest.raises(Market03BoundDataRefused):
        refuse_bound_scientific_inputs(origin="production")
    with pytest.raises(Market03BoundDataRefused):
        refuse_bound_scientific_inputs(
            origin="synthetic",
            source_path="docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/klines.jsonl",
        )


def test_evaluate_bound_snapshot_is_execution_invalid_not_not_reproduced():
    candles = _hourly("2019-10-01T00:00:00Z", 8)
    funding = funding_series_from_observations([1569888000000], [0.0001])
    out = evaluate_market_03_reproduction(
        candles,
        origin="synthetic",
        funding=funding,
        spot_snapshot_id=SPOT_SNAPSHOT_ID,
        evaluation_start="2019-10-01T00:00:00Z",
        evaluation_end="2019-10-02T00:00:00Z",
    )
    assert out["primary_classification"] == CLASS_EXECUTION_INVALID
    assert out["primary_classification"] != CLASS_NOT_REPRODUCED_DIRECTION
    assert out["mdd_baseline"] is None
    assert out["mdd_filtered"] is None


def test_protected_oos_is_execution_invalid():
    candles = _hourly("2025-01-01T00:00:00Z", 4)
    funding = funding_series_from_observations([1735689600000], [0.0])
    out = evaluate_market_03_reproduction(
        candles,
        origin="synthetic",
        funding=funding,
        evaluation_start="2025-01-01T00:00:00Z",
        evaluation_end="2025-01-02T00:00:00Z",
        require_prereg_bytes=True,
    )
    assert out["primary_classification"] == CLASS_EXECUTION_INVALID
    assert "PROTECTED_OOS" in (out["invalid_reason"] or "")


def test_wrong_external_source_is_execution_invalid():
    candles = _hourly("2019-10-01T00:00:00Z", 8)
    funding = funding_series_from_observations([1569888000000], [0.0001])
    out = evaluate_market_03_reproduction(
        candles,
        origin="synthetic",
        funding=funding,
        external_commit="deadbeef",
        evaluation_start="2019-10-01T00:00:00Z",
        evaluation_end="2019-10-02T00:00:00Z",
    )
    assert out["primary_classification"] == CLASS_EXECUTION_INVALID


def test_allowed_test_origins_only():
    assert ALLOWED_TEST_ORIGINS == {"synthetic", "pinned_external_fixture", "handcrafted"}


# ---------------------------------------------------------------------------
# EXACT_DIFFERENTIAL: qtpylib crossed_*
# ---------------------------------------------------------------------------


def test_qtpylib_crossed_above_freqtrade_vector_exact_differential():
    s1 = pd.Series(QTPYLIB_CROSS_VECTOR, dtype=float)
    got = crossed_above(s1, QTPYLIB_CROSS_LEVEL).fillna(False).tolist()
    assert got == QTPYLIB_CROSSED_ABOVE


def test_qtpylib_crossed_below_formula_exact_differential():
    s1 = pd.Series(QTPYLIB_CROSS_VECTOR, dtype=float)
    s2 = pd.Series([QTPYLIB_CROSS_LEVEL] * len(s1), dtype=float)
    expected = ((s1 < s2) & (s1.shift(1) >= s2.shift(1))).tolist()
    got = crossed_below(s1, s2).tolist()
    assert got == expected


def test_price_exactly_at_ema_is_not_a_cross():
    close = pd.Series([10.0, 10.0, 10.0])
    ema = pd.Series([9.0, 10.0, 10.0])
    assert bool(crossed_above(close, ema).iloc[1]) is False
    assert bool(crossed_above(close, ema).iloc[2]) is False


def test_price_infinitesimally_above_and_below_ema():
    eps = 1e-12
    close = pd.Series([10.0 - eps, 10.0 + eps])
    ema = pd.Series([10.0, 10.0])
    assert bool(crossed_above(close, ema).iloc[1]) is True
    close_down = pd.Series([10.0 + eps, 10.0 - eps])
    assert bool(crossed_below(close_down, ema).iloc[1]) is True


def test_crossed_uses_previous_present_row_not_calendar_gap():
    idx = pd.to_datetime(
        ["2019-10-01T00:00:00Z", "2019-10-01T02:00:00Z"], utc=True
    )  # missing 01:00
    close = pd.Series([10.0, 12.0], index=idx)
    ema = pd.Series([11.0, 11.0], index=idx)
    # Previous *present* row is 00:00 (close 10 <= ema 11), not a synthesized 01:00.
    assert bool(crossed_above(close, ema).iloc[1]) is True


# ---------------------------------------------------------------------------
# SEMANTIC_FIXTURE: TA-Lib EMA SMA-seed
# ---------------------------------------------------------------------------


def test_talib_ema_sma_seed_and_k_semantic_fixture():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    got = talib_ema(x, 3)
    assert math.isnan(got[0]) and math.isnan(got[1])
    seed = (1.0 + 2.0 + 3.0) / 3.0
    assert got[2] == pytest.approx(seed)
    k = 2.0 / 4.0
    expect3 = k * 4.0 + (1.0 - k) * seed
    assert got[3] == pytest.approx(expect3)


def test_ema_warmup_insufficient_bars_are_nan():
    x = np.arange(10, dtype=float)
    got = talib_ema(x, 600)
    assert np.all(np.isnan(got))


def test_ema_exit_is_two_percent_below():
    ema = np.array([100.0, 50.0])
    got = ema_exit_level(ema, 2.0)
    assert got[0] == pytest.approx(98.0)
    assert got[1] == pytest.approx(49.0)


# ---------------------------------------------------------------------------
# EXACT_DIFFERENTIAL: funding pandas snippet vs reimplementation
# ---------------------------------------------------------------------------


def _funding_fixture(n_candles: int = 900) -> tuple[pd.DatetimeIndex, pd.Series]:
    dates = pd.date_range("2019-09-10T00:00:00Z", periods=n_candles, freq="h", tz="UTC")
    # 8h funding with millisecond residuals; do not round.
    times = []
    rates = []
    t0 = int(pd.Timestamp("2019-09-10T00:00:00Z").timestamp() * 1000)
    for i in range(0, n_candles, 8):
        residual = (i // 8) % 47
        times.append(t0 + i * 3600_000 + residual)
        rates.append(0.0001 + 0.00001 * ((i // 8) % 17))
    fr = funding_series_from_observations(times, rates)
    return dates, fr


def test_funding_features_match_pinned_pandas_snippet_exact_differential():
    dates, fr = _funding_fixture(900)
    ours = pinned_external_funding_features(dates, fr)
    pinned = _pinned_funding_snippet(dates, fr)
    np.testing.assert_allclose(ours["funding"].to_numpy(), pinned["funding"], equal_nan=True)
    np.testing.assert_allclose(ours["funding_3d"].to_numpy(), pinned["funding_3d"], equal_nan=True)
    np.testing.assert_allclose(ours["funding_pct"].to_numpy(), pinned["funding_pct"], equal_nan=True)


def test_funding_ffill_is_last_fundingtime_at_or_before_candle():
    candles = pd.DatetimeIndex(
        [
            pd.Timestamp("2019-09-10T08:00:00.000Z"),
            pd.Timestamp("2019-09-10T08:00:00.015Z"),
            pd.Timestamp("2019-09-10T16:00:00Z"),
        ]
    )
    # Observation at 08:00:00.010 — after first candle, at/before second.
    fr = funding_series_from_observations(
        [1568102400010, 1568131200000],
        [0.01, 0.02],
    )
    got = pinned_external_funding_features(candles, fr)
    assert math.isnan(got["funding"].iloc[0])
    assert got["funding"].iloc[1] == pytest.approx(0.01)
    assert got["funding"].iloc[2] == pytest.approx(0.02)


def test_fundingtime_millisecond_before_at_after_boundary():
    boundary = pd.Timestamp("2019-10-01T00:00:00Z")
    candle = pd.DatetimeIndex([boundary])
    before = int(boundary.timestamp() * 1000) - 1
    at = int(boundary.timestamp() * 1000)
    after = int(boundary.timestamp() * 1000) + 1
    b = pinned_external_funding_features(candle, funding_series_from_observations([before], [1.0]))
    a = pinned_external_funding_features(candle, funding_series_from_observations([at], [2.0]))
    z = pinned_external_funding_features(candle, funding_series_from_observations([after], [3.0]))
    assert b["funding"].iloc[0] == pytest.approx(1.0)
    assert a["funding"].iloc[0] == pytest.approx(2.0)
    assert math.isnan(z["funding"].iloc[0])


def test_funding_3d_mean_window_and_min_periods():
    dates = pd.date_range("2019-09-10T00:00:00Z", periods=80, freq="h", tz="UTC")
    # One observation at start so ffill is constant after first.
    fr = funding_series_from_observations(
        [int(dates[0].timestamp() * 1000)],
        [0.003],
    )
    got = pinned_external_funding_features(dates, fr)
    # min_periods=24: first 23 aligned rows NaN, then mean of the constant.
    assert np.all(np.isnan(got["funding_3d"].iloc[:23]))
    assert got["funding_3d"].iloc[23] == pytest.approx(0.003)
    assert got["funding_3d"].iloc[71] == pytest.approx(0.003)


def test_funding_percentile_includes_current_and_missing_allows_entry():
    # pandas rolling.rank(pct=True) includes the current observation.
    s = pd.Series([1.0, 2.0, 3.0, 2.0, 5.0, 0.0, 4.0])
    got = s.rolling(3, min_periods=3).rank(pct=True)
    # Frozen probe: NaN, NaN, 1.0, 0.5, 1.0, 1/3, 2/3
    assert math.isnan(got.iloc[0]) and math.isnan(got.iloc[1])
    assert got.iloc[2] == pytest.approx(1.0)
    assert got.iloc[3] == pytest.approx(0.5)
    assert got.iloc[4] == pytest.approx(1.0)
    assert got.iloc[5] == pytest.approx(1.0 / 3.0)
    assert got.iloc[6] == pytest.approx(2.0 / 3.0)
    assert funding_allows_entry(float("nan")) is True
    assert funding_allows_entry(None) is True


def test_funding_threshold_54_999_55_and_above():
    assert funding_allows_entry(54.999) is True
    assert funding_allows_entry(55.0) is False
    assert funding_allows_entry(55.0001) is False
    assert funding_allows_entry(90.0) is False


def test_populate_entry_skips_iff_funding_pct_ge_55():
    n = 650
    close = np.full(n, 100.0)
    close[-2] = 90.0
    close[-1] = 110.0
    df = _hourly("2019-10-01T00:00:00Z", n, close)
    df = populate_indicators(df)
    # Force a valid cross on last bar regardless of EMA numerics: inject ema.
    df.loc[df.index[-2], "ema"] = 100.0
    df.loc[df.index[-1], "ema"] = 100.0
    df.loc[df.index[-2], "close"] = 90.0
    df.loc[df.index[-1], "close"] = 110.0
    df["funding_pct"] = np.nan
    df.loc[df.index[-1], "funding_pct"] = 54.999
    ok = populate_entry_trend(df, "filtered")
    assert int(ok["enter_long"].iloc[-1]) == 1
    df.loc[df.index[-1], "funding_pct"] = 55.0
    blocked = populate_entry_trend(df, "filtered")
    assert int(blocked["enter_long"].iloc[-1]) == 0
    df.loc[df.index[-1], "funding_pct"] = np.nan
    missing = populate_entry_trend(df, "filtered")
    assert int(missing["enter_long"].iloc[-1]) == 1


def test_funding_filter_does_not_change_exits():
    n = 650
    close = np.linspace(50.0, 150.0, n)
    df = _hourly("2019-10-01T00:00:00Z", n, close)
    dates, fr = _funding_fixture(n)
    df["date"] = dates[:n]
    base = advise_signals(df, "baseline")
    filt = advise_signals(df, "filtered", funding=fr)
    np.testing.assert_array_equal(base["exit_long"].to_numpy(), filt["exit_long"].to_numpy())


def test_exit_exactly_two_percent_below_ema_is_the_exit_level():
    ema = pd.Series([100.0, 100.0, 100.0])
    ema_exit = pd.Series(ema_exit_level(ema, 2.0))
    assert ema_exit.iloc[0] == pytest.approx(98.0)
    close = pd.Series([99.0, 98.0, 97.0])
    # Equal to ema_exit is not crossed_below; must go strictly below.
    below = crossed_below(close, ema_exit)
    assert bool(below.iloc[1]) is False
    assert bool(below.iloc[2]) is True


def test_no_short_signals():
    df = advise_signals(_hourly("2019-10-01T00:00:00Z", 20), "baseline")
    assert int(df["enter_short"].sum()) == 0
    assert int(df["exit_short"].sum()) == 0


def test_missing_funding_is_execution_invalid_not_not_reproduced():
    candles = _hourly("2019-10-01T00:00:00Z", 8)
    out = evaluate_market_03_reproduction(
        candles,
        origin="synthetic",
        funding=None,
        evaluation_start="2019-10-01T00:00:00Z",
        evaluation_end="2019-10-02T00:00:00Z",
    )
    assert out["primary_classification"] == CLASS_EXECUTION_INVALID
    assert out["primary_classification"] != CLASS_NOT_REPRODUCED_DIRECTION


def test_volume_zero_blocks_entry_but_close_may_enter_ema():
    n = 650
    close = np.full(n, 100.0)
    close[-2] = 90.0
    close[-1] = 110.0
    df = _hourly("2019-10-01T00:00:00Z", n, close, volume=0.0)
    df = populate_indicators(df)
    df.loc[df.index[-2], "ema"] = 100.0
    df.loc[df.index[-1], "ema"] = 100.0
    df.loc[df.index[-2], "close"] = 90.0
    df.loc[df.index[-1], "close"] = 110.0
    got = populate_entry_trend(df, "baseline")
    assert int(got["enter_long"].iloc[-1]) == 0
    # Degenerate volume=0 row is retained; EMA still consumed the close.
    assert not math.isnan(df["ema"].iloc[-1])


# ---------------------------------------------------------------------------
# SEMANTIC_FIXTURE: trade engine
# ---------------------------------------------------------------------------


def _flat_signal_frame(n: int = 16) -> pd.DataFrame:
    df = _hourly("2019-10-01T00:00:00Z", n, np.full(n, 100.0))
    df["high"] = df["open"]
    df["low"] = df["open"]
    df["ema"] = 90.0
    df["ema_exit"] = 88.2
    df["enter_long"] = 0
    df["exit_long"] = 0
    df["enter_tag"] = None
    df["exit_tag"] = None
    return df


def test_injected_entry_fills_at_next_open_not_signal_close():
    n = 30
    df = _hourly("2019-10-01T00:00:00Z", n, np.full(n, 100.0))
    df["ema"] = 90.0
    df["ema_exit"] = 88.2
    df["enter_long"] = 0
    df["exit_long"] = 0
    df["enter_tag"] = None
    df["exit_tag"] = None
    df.loc[10, "enter_long"] = 1
    df.loc[10, "enter_tag"] = "ema_cross_up"
    df.loc[20, "exit_long"] = 1
    df.loc[20, "exit_tag"] = "ema_cross_down"
    sim = simulate_strategy(
        df,
        variant="baseline",
        origin="handcrafted",
        evaluation_start="2019-10-01T00:00:00Z",
        evaluation_end="2019-10-03T00:00:00Z",
    )
    assert len(sim.trades) == 1
    trade = sim.trades[0]
    assert trade.open_date == pd.Timestamp(df.loc[11, "date"])
    assert trade.open_rate == pytest.approx(float(df.loc[11, "open"]))
    assert trade.close_date == pd.Timestamp(df.loc[21, "date"])
    assert trade.close_rate == pytest.approx(float(df.loc[21, "open"]))
    assert trade.exit_reason == "exit_signal"
    assert trade.enter_tag == "ema_cross_up"


def test_duplicate_prevention_max_open_trades_one():
    n = 20
    df = _hourly("2019-10-01T00:00:00Z", n, np.full(n, 100.0))
    df["ema"] = 90.0
    df["ema_exit"] = 88.2
    df["enter_long"] = 0
    df["exit_long"] = 0
    df["enter_tag"] = None
    df["exit_tag"] = None
    df.loc[2, "enter_long"] = 1
    df.loc[5, "enter_long"] = 1
    df.loc[10, "exit_long"] = 1
    sim = simulate_strategy(
        df,
        variant="baseline",
        origin="handcrafted",
        evaluation_start="2019-10-01T00:00:00Z",
        evaluation_end="2019-10-02T00:00:00Z",
    )
    assert len(sim.trades) == 1


def test_stoploss_fills_exactly_at_stop_even_if_low_lower():
    df = _flat_signal_frame()
    df.loc[2, "enter_long"] = 1
    # Fill at row 3 open=100. Stop = 85. Next candle low far below.
    df.loc[4, "low"] = 50.0
    df.loc[4, "high"] = 100.0
    df.loc[4, "open"] = 100.0
    df.loc[4, "close"] = 60.0
    sim = simulate_strategy(
        df,
        variant="baseline",
        origin="handcrafted",
        evaluation_start="2019-10-01T00:00:00Z",
        evaluation_end="2019-10-02T00:00:00Z",
    )
    assert len(sim.trades) == 1
    trade = sim.trades[0]
    assert trade.exit_reason == "stop_loss"
    assert trade.close_rate == pytest.approx(100.0 * (1.0 + STOPLOSS))
    assert trade.close_rate > 50.0


def test_trailing_stop_high_first_then_low_uses_adjusted():
    df = _flat_signal_frame()
    df.loc[2, "enter_long"] = 1
    # After fill at 3, candle 5: high 200, low 160. Old stop 85 < 160, trail to 170, 170>=160 hit.
    df.loc[5, "open"] = 150.0
    df.loc[5, "high"] = 200.0
    df.loc[5, "low"] = 160.0
    df.loc[5, "close"] = 170.0
    sim = simulate_strategy(
        df,
        variant="baseline",
        origin="handcrafted",
        evaluation_start="2019-10-01T00:00:00Z",
        evaluation_end="2019-10-02T00:00:00Z",
    )
    assert len(sim.trades) == 1
    trade = sim.trades[0]
    assert trade.exit_reason == "trailing_stop_loss"
    assert trade.close_rate == pytest.approx(200.0 * 0.85)


def test_same_candle_exit_signal_favored_over_stoploss():
    assert same_candle_exit_order() == ("exit_signal", "stoploss", "roi", "trailing_stoploss")
    df = _flat_signal_frame()
    df.loc[2, "enter_long"] = 1
    # Exit signal generated on candle 4 close → fill candle 5 open, and candle 5 also hits stop.
    df.loc[4, "exit_long"] = 1
    df.loc[5, "low"] = 50.0
    df.loc[5, "open"] = 100.0
    df.loc[5, "high"] = 101.0
    sim = simulate_strategy(
        df,
        variant="baseline",
        origin="handcrafted",
        evaluation_start="2019-10-01T00:00:00Z",
        evaluation_end="2019-10-02T00:00:00Z",
    )
    assert len(sim.trades) == 1
    assert sim.trades[0].exit_reason == "exit_signal"
    assert sim.trades[0].close_rate == pytest.approx(100.0)


def test_fee_applied_twice_and_wallet_compounds():
    n = 16
    df = _hourly("2019-10-01T00:00:00Z", n, np.full(n, 100.0))
    df["ema"] = 90.0
    df["ema_exit"] = 88.2
    df["enter_long"] = 0
    df["exit_long"] = 0
    df["enter_tag"] = None
    df["exit_tag"] = None
    df.loc[2, "enter_long"] = 1
    df.loc[8, "exit_long"] = 1
    sim = simulate_strategy(
        df,
        variant="baseline",
        origin="handcrafted",
        evaluation_start="2019-10-01T00:00:00Z",
        evaluation_end="2019-10-02T00:00:00Z",
        initial_capital=10000.0,
    )
    trade = sim.trades[0]
    assert trade.fee_open == pytest.approx(trade.amount * trade.open_rate * FEE_PER_SIDE)
    assert trade.fee_close == pytest.approx(trade.amount * trade.close_rate * FEE_PER_SIDE)
    expected_ratio = (trade.close_rate * (1 - FEE_PER_SIDE)) / (
        trade.open_rate * (1 + FEE_PER_SIDE)
    ) - 1.0
    assert trade.profit_ratio == pytest.approx(expected_ratio)
    # Remaining cash after round-trip at unchanged price is reduced by both fees.
    usdt_final = [w.total for w in sim.wallet if w.currency == "USDT"][-1]
    assert usdt_final < 10000.0


def test_force_exit_last_in_interval_candle_without_2025_prices():
    n = 12
    df = _hourly("2019-12-31T12:00:00Z", n, np.full(n, 100.0))
    df["ema"] = 90.0
    df["ema_exit"] = 88.2
    df["enter_long"] = 0
    df["exit_long"] = 0
    df["enter_tag"] = None
    df["exit_tag"] = None
    df.loc[2, "enter_long"] = 1
    sim = simulate_strategy(
        df,
        variant="baseline",
        origin="handcrafted",
        evaluation_start="2019-12-31T12:00:00Z",
        evaluation_end="2020-01-01T00:00:00Z",
    )
    assert sim.force_exited is True
    assert sim.trades[0].exit_reason == "force_exit"
    assert sim.trades[0].close_date < pd.Timestamp(PROTECTED_OOS_START)
    assert sim.trades[0].close_rate == pytest.approx(float(df.iloc[-1]["open"]))


def test_warmup_fills_not_before_evaluation_start():
    n = 48
    df = _hourly("2019-09-30T00:00:00Z", n, np.full(n, 100.0))
    df["ema"] = 90.0
    df["ema_exit"] = 88.2
    df["enter_long"] = 0
    df["exit_long"] = 0
    df["enter_tag"] = None
    df["exit_tag"] = None
    # Signal during warmup; fill would be next hour still in warmup.
    df.loc[2, "enter_long"] = 1
    sim = simulate_strategy(
        df,
        variant="baseline",
        origin="handcrafted",
        evaluation_start="2019-10-01T00:00:00Z",
        evaluation_end="2019-10-02T00:00:00Z",
    )
    assert sim.trades == []


def test_last_warmup_signal_may_fill_first_eval_open():
    n = 48
    df = _hourly("2019-09-30T00:00:00Z", n, np.full(n, 100.0))
    df["ema"] = 90.0
    df["ema_exit"] = 88.2
    df["enter_long"] = 0
    df["exit_long"] = 0
    df["enter_tag"] = None
    df["exit_tag"] = None
    # 2019-09-30T23:00:00Z is last warmup hour (index 23). Fill at 2019-10-01T00:00.
    warmup_last = df.index[df["date"] == pd.Timestamp("2019-09-30T23:00:00Z")][0]
    df.loc[warmup_last, "enter_long"] = 1
    sim = simulate_strategy(
        df,
        variant="baseline",
        origin="handcrafted",
        evaluation_start="2019-10-01T00:00:00Z",
        evaluation_end="2019-10-02T00:00:00Z",
    )
    assert len(sim.trades) >= 1
    assert sim.trades[0].open_date == pd.Timestamp("2019-10-01T00:00:00Z")


def test_classification_signed_mdd_not_abs():
    assert classify_primary(-0.338, -0.494) == CLASS_REPRODUCED_DIRECTION
    assert classify_primary(-0.494, -0.338) == CLASS_NOT_REPRODUCED_DIRECTION
    assert classify_primary(-0.494, -0.494) == CLASS_NOT_REPRODUCED_DIRECTION
    assert classify_primary(None, -0.1) == CLASS_EXECUTION_INCOMPLETE
    assert classify_primary(-0.1, None) == CLASS_EXECUTION_INCOMPLETE
    assert classify_primary(float("nan"), -0.1) == CLASS_EXECUTION_INCOMPLETE
    assert classify_primary(-0.9, -0.1, invalid_reason="x") == CLASS_EXECUTION_INVALID
    mag = descriptive_magnitude(-0.338, -0.494)
    assert mag["OBS_ABS_REDUCTION_PP"] == pytest.approx(15.6)
    # Magnitude must not flip a failed direction.
    assert classify_primary(-0.50, -0.10) == CLASS_NOT_REPRODUCED_DIRECTION


def test_author_headline_constants_are_descriptive_only():
    assert AUTHOR_MDD_BASELINE == pytest.approx(-0.494)
    assert AUTHOR_MDD_FILTERED == pytest.approx(-0.338)


# ---------------------------------------------------------------------------
# EXACT_DIFFERENTIAL: pinned metrics.py vs reimplementation
# ---------------------------------------------------------------------------


def test_risk_report_matches_pinned_metrics_py_exact_differential():
    idx = pd.date_range("2019-10-01", periods=40, freq="D", tz="UTC")
    rng = np.random.default_rng(0)
    r = pd.Series(rng.normal(0.001, 0.02, size=len(idx)), index=idx)
    pinned = _load_pinned_metrics().risk_report(r)
    ours = risk_report(r)
    assert ours["Max drawdown"] == pytest.approx(pinned["Max drawdown"])
    assert ours["Total return"] == pytest.approx(pinned["Total return"])
    assert ours["CAGR"] == pytest.approx(pinned["CAGR"])
    assert ours["Sharpe"] == pytest.approx(pinned["Sharpe"])
    assert ours["Sortino"] == pytest.approx(pinned["Sortino"])
    assert ours["Max drawdown"] <= 0.0


def test_mdd_undefined_when_returns_degenerate():
    s = pd.Series([100.0, 100.0], index=pd.date_range("2019-10-01", periods=2, freq="D", tz="UTC"))
    assert mdd_from_daily_equity(s) is None
    assert classify_primary(mdd_from_daily_equity(s), -0.1) == CLASS_EXECUTION_INCOMPLETE


def test_wallet_daily_equity_groupby_resample_ffill():
    from scripts.research.market_03_public_strategy_lib import WalletPoint

    wallet = [
        WalletPoint(date=pd.Timestamp("2019-10-01T01:00:00Z"), currency="USDT", price=1.0, total=4000.0),
        WalletPoint(date=pd.Timestamp("2019-10-01T01:00:00Z"), currency="BTC", price=100.0, total=60.0),
        WalletPoint(date=pd.Timestamp("2019-10-01T23:00:00Z"), currency="USDT", price=1.0, total=11000.0),
        WalletPoint(date=pd.Timestamp("2019-10-03T00:00:00Z"), currency="USDT", price=1.0, total=12000.0),
    ]
    eq = wallet_to_daily_equity(wallet)
    assert eq.loc["2019-10-01"].item() == pytest.approx(11000.0)
    assert eq.loc["2019-10-02"].item() == pytest.approx(11000.0)  # ffill
    assert eq.loc["2019-10-03"].item() == pytest.approx(12000.0)


def test_evaluate_synthetic_pair_runs_both_variants_without_bound_data():
    n = 800
    close = np.concatenate([np.full(600, 80.0), np.linspace(80.0, 140.0, 200)])
    candles = _hourly("2019-09-01T00:00:00Z", n, close)
    dates, fr = _funding_fixture(n)
    candles["date"] = dates[:n]
    out = evaluate_market_03_reproduction(
        candles,
        origin="synthetic",
        funding=fr,
        evaluation_start="2019-09-20T00:00:00Z",
        evaluation_end="2019-10-05T00:00:00Z",
        external_commit=EXTERNAL_COMMIT,
        external_tree=EXTERNAL_TREE,
    )
    assert out["invalid_reason"] is None
    assert out["primary_classification"] in {
        CLASS_REPRODUCED_DIRECTION,
        CLASS_NOT_REPRODUCED_DIRECTION,
        CLASS_EXECUTION_INCOMPLETE,
    }
    assert out["primary_classification"] != CLASS_EXECUTION_INVALID
    # Isolation: funding cannot invent shorts.
    assert all(t.enter_tag in {"ema_cross_up"} for t in out["baseline_trades"])
    assert all(
        t.enter_tag in {"ema_cross_funding_ok"} for t in out["filtered_trades"]
    )


def test_pinned_emacrossfunding_source_still_has_frozen_pandas_body():
    text = PINNED_FUNDING_STRAT.read_text(encoding="utf-8")
    assert 'reindex(idx, method="ffill")' in text
    assert "rolling(72, min_periods=24).mean()" in text
    assert "rolling(24 * 180, min_periods=24 * 30)" in text
    assert "rank(pct=True) * 100" in text
    assert "funding_pct" in text


def test_no_statistical_machinery_in_scientific_lib():
    text = LIB.read_text(encoding="utf-8")
    for token in ("bootstrap", "p_value", "pvalue", "optimize", "parameter_sweep"):
        assert token not in text


def test_tests_do_not_load_bound_scientific_snapshots(tmp_path):
    """Outcome-blind: this test file never points strategy logic at bound bytes."""
    lib_src = LIB.read_text(encoding="utf-8")
    auth_src = AUTHORITY.read_text(encoding="utf-8")
    exec_src = EXECUTE.read_text(encoding="utf-8")
    # Scientific core must not open bound snapshot bytes.
    for blob in (lib_src, exec_src):
        assert "read_parquet(" not in blob
        assert "read_feather(" not in blob
        assert "jsonl" not in blob
    assert "evaluate_bound" not in lib_src
    assert MARKET_03_BOUND_EXECUTION_AUTHORIZED is False
    assert "SPOT_SNAPSHOT_ID" in auth_src
    # Guard refuses the bound path tokens; it must not load them.
    with pytest.raises(Market03BoundDataRefused):
        refuse_bound_scientific_inputs(
            origin="synthetic",
            source_path="docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/klines",
        )


def test_implementation_record_locks_scientific_file_hashes():
    payload = json.loads(
        (REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION.json").read_text(
            encoding="utf-8"
        )
    )
    files = payload["implementation_files"]
    for rel, meta in files.items():
        assert _sha256(REPO / rel) == meta["sha256"], rel
    assert payload["prereg"]["md_sha256"] == FROZEN_PREREG_MD_SHA256
    assert payload["prereg"]["json_sha256"] == FROZEN_PREREG_JSON_SHA256
    assert payload["explicit_state"]["IMPLEMENTATION_FROZEN"] is False
    assert payload["explicit_state"]["MARKET_03_ARMED"] is False
    assert payload["explicit_state"]["CANONICAL_EXECUTIONS_AUTHORIZED"] == 0
    assert payload["fidelity"]["EXACT_DIFFERENTIAL_TESTS"] is True
    assert payload["fidelity"]["SEMANTIC_FIXTURE_TESTS"] is True
    md = (REPO / "docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION.md").read_text(
        encoding="utf-8"
    )
    assert "IMPLEMENTATION_FROZEN                = NO" in md
    assert FROZEN_PREREG_MD_SHA256 in md
    for path in (LIB, AUTHORITY, EXECUTE):
        assert path.is_file()
        assert path.stat().st_size > 100


def test_frozen_interval_constants():
    assert EVALUATION_START_INCLUSIVE == "2019-10-01T00:00:00Z"
    assert EVALUATION_END_EXCLUSIVE == "2025-01-01T00:00:00Z"
    assert PROTECTED_OOS_START == "2025-01-01T00:00:00Z"
    assert FUNDING_DATASET_ID == "MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0"
    assert FUNDING_ROWS == 5819
    assert SPOT_DATA_SHA256.startswith("e560bebb")
    assert FUNDING_DATA_SHA256.startswith("e7885cd5")
    assert EMA_PERIOD == 600
    assert FUNDING_MAX_PCT == 55.0
    assert STRICT_HISTORICAL_PUBLICATION_LATENCY == "UNPROVEN"
