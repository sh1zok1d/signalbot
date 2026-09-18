"""MARKET-03 LEVEL_2 scientific core.

Pure deterministic functions for EmaCross / EmaCrossFunding reproduction.
Does not ARM, persist results, or load bound MARKET-03 snapshots.

JSON sidecar parameters are frozen here. Class defaults (ema 800 / exit 1.0
/ funding 90) are not the published contrast.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Literal, Mapping, Sequence

import numpy as np
import pandas as pd

from scripts.research.market_03_public_strategy_authority import (
    B2_06_DATASET_ID,
    B2_06_SNAPSHOT_ID,
    EVALUATION_END_EXCLUSIVE,
    EVALUATION_START_INCLUSIVE,
    PROTECTED_OOS_START,
    STRICT_HISTORICAL_PUBLICATION_LATENCY,
    Market03AuthorityError,
    Market03BoundDataRefused,
    Market03ExecutionNotAuthorized,
    authenticate_frozen_prereg_bytes,
    refuse_bound_scientific_inputs,
    require_external_source_identity,
)

Variant = Literal["baseline", "filtered"]

# Frozen JSON-sidecar trading rules (not class defaults).
EMA_PERIOD = 600
EXIT_THRESHOLD_PCT = 2.0
FUNDING_MAX_PCT = 55.0
STOPLOSS = -0.15
TRAILING_STOP = True
TRAILING_STOP_POSITIVE: float | None = None
TRAILING_STOP_POSITIVE_OFFSET = 0.0
TRAILING_ONLY_OFFSET_IS_REACHED = False
MINIMAL_ROI = {"0": 10.0}
ROI_EFFECTIVELY_INACTIVE = True
STARTUP_CANDLE_COUNT = 1300
MAX_OPEN_TRADES = 1
CAN_SHORT = False
FEE_PER_SIDE = 0.001
TRADABLE_BALANCE_RATIO = 0.99
INITIAL_CAPITAL_USDT = 10000.0
PPY = 365
FUNDING_3D_WINDOW = 72
FUNDING_3D_MIN_PERIODS = 24
FUNDING_PCT_WINDOW = 24 * 180
FUNDING_PCT_MIN_PERIODS = 24 * 30
ENTRY_TAG_BASELINE = "ema_cross_up"
ENTRY_TAG_FILTERED = "ema_cross_funding_ok"
EXIT_TAG = "ema_cross_down"

CLASS_REPRODUCED_DIRECTION = "REPRODUCED_DIRECTION"
CLASS_NOT_REPRODUCED_DIRECTION = "NOT_REPRODUCED_DIRECTION"
CLASS_EXECUTION_INCOMPLETE = "EXECUTION_INCOMPLETE"
CLASS_EXECUTION_INVALID = "EXECUTION_INVALID"

AUTHOR_MDD_BASELINE = -0.494
AUTHOR_MDD_FILTERED = -0.338


# ---------------------------------------------------------------------------
# Indicators (TA-Lib EMA SMA-seed; qtpylib crossed_* present-row shift)
# ---------------------------------------------------------------------------


def talib_ema(close: np.ndarray, period: int = EMA_PERIOD) -> np.ndarray:
    """TA-Lib EMA: SMA seed of first `period` bars, then k=2/(period+1).

    First `period-1` outputs are NaN. This is a faithful reimplementation of
    the published TA-Lib SMA-seed algorithm, not a live `talib` C call.
    """
    x = np.asarray(close, dtype=np.float64)
    n = int(period)
    out = np.full(x.shape[0], np.nan, dtype=np.float64)
    if n < 1:
        raise ValueError("ema period must be >= 1")
    if x.size < n:
        return out
    if n == 1:
        return x.copy()
    seed = np.mean(x[:n])
    out[n - 1] = seed
    k = 2.0 / (n + 1.0)
    one_k = 1.0 - k
    prev = seed
    for i in range(n, x.size):
        prev = k * x[i] + one_k * prev
        out[i] = prev
    return out


def crossed_above(series1: pd.Series, series2: pd.Series | float) -> pd.Series:
    """qtpylib crossed_above: (s1 > s2) & (s1.shift(1) <= s2.shift(1)).

    Prior observation is the previous *present* dataframe row, not a
    calendar hour if that hour is missing.
    """
    s1 = pd.Series(series1)
    if isinstance(series2, (float, int, np.floating, np.integer)):
        s2 = pd.Series(index=s1.index, data=float(series2))
    else:
        s2 = pd.Series(series2)
    return (s1 > s2) & (s1.shift(1) <= s2.shift(1))


def crossed_below(series1: pd.Series, series2: pd.Series | float) -> pd.Series:
    """qtpylib crossed_below: (s1 < s2) & (s1.shift(1) >= s2.shift(1))."""
    s1 = pd.Series(series1)
    if isinstance(series2, (float, int, np.floating, np.integer)):
        s2 = pd.Series(index=s1.index, data=float(series2))
    else:
        s2 = pd.Series(series2)
    return (s1 < s2) & (s1.shift(1) >= s2.shift(1))


def ema_exit_level(ema: pd.Series | np.ndarray, threshold_pct: float = EXIT_THRESHOLD_PCT) -> np.ndarray:
    ema_arr = np.asarray(ema, dtype=np.float64)
    return ema_arr * (100.0 - float(threshold_pct)) / 100.0


# ---------------------------------------------------------------------------
# Funding: exact pinned EmaCrossFunding.py pandas operations
# ---------------------------------------------------------------------------


def funding_series_from_observations(
    funding_time_ms: Sequence[int] | np.ndarray,
    funding_rate: Sequence[float] | np.ndarray,
) -> pd.Series:
    """Index by raw fundingTime milliseconds. Do not round."""
    times = np.asarray(funding_time_ms, dtype=np.int64)
    rates = np.asarray(funding_rate, dtype=np.float64)
    idx = pd.to_datetime(times, unit="ms", utc=True)
    series = pd.Series(rates, index=idx, name="funding")
    return series.sort_index()


def pinned_external_funding_features(
    candle_dates: pd.Series | np.ndarray | Sequence,
    funding: pd.Series,
) -> pd.DataFrame:
    """Literal pinned EmaCrossFunding.py alignment / 3d mean / 180d percentile.

    External code:
        idx = pd.to_datetime(dataframe["date"], utc=True)
        f = fr.reindex(idx, method="ffill")
        funding_3d = f.rolling(72, min_periods=24).mean()
        funding_pct = (
            pd.Series(funding_3d.to_numpy())
            .rolling(24 * 180, min_periods=24 * 30)
            .rank(pct=True) * 100
        )
    """
    idx = pd.to_datetime(pd.Index(candle_dates), utc=True)
    fr = funding.sort_index()
    if not isinstance(fr.index, pd.DatetimeIndex):
        raise Market03AuthorityError("MARKET_03_FUNDING_INDEX_NOT_DATETIME")
    if fr.index.tz is None:
        fr.index = fr.index.tz_localize("UTC")
    else:
        fr.index = fr.index.tz_convert("UTC")
    if fr.index.has_duplicates:
        fr = fr[~fr.index.duplicated(keep="last")]
    f = fr.reindex(idx, method="ffill")
    funding_3d = f.rolling(FUNDING_3D_WINDOW, min_periods=FUNDING_3D_MIN_PERIODS).mean()
    funding_pct = (
        pd.Series(np.asarray(funding_3d.to_numpy(), dtype=np.float64))
        .rolling(FUNDING_PCT_WINDOW, min_periods=FUNDING_PCT_MIN_PERIODS)
        .rank(pct=True)
        * 100.0
    )
    return pd.DataFrame(
        {
            "date": idx,
            "funding": np.asarray(f.to_numpy(), dtype=np.float64),
            "funding_3d": np.asarray(funding_3d.to_numpy(), dtype=np.float64),
            "funding_pct": np.asarray(funding_pct.to_numpy(), dtype=np.float64),
        }
    )


def align_funding_to_candles(
    candle_dates: pd.Series | np.ndarray | Sequence,
    funding_time_ms: Sequence[int] | np.ndarray,
    funding_rate: Sequence[float] | np.ndarray,
) -> pd.DataFrame:
    return pinned_external_funding_features(
        candle_dates,
        funding_series_from_observations(funding_time_ms, funding_rate),
    )


def funding_allows_entry(funding_pct: float | np.floating | None, threshold: float = FUNDING_MAX_PCT) -> bool:
    """Skip entry iff funding_pct >= threshold. Missing percentile allows entry."""
    if funding_pct is None:
        return True
    if isinstance(funding_pct, (float, np.floating)) and (math.isnan(float(funding_pct))):
        return True
    return float(funding_pct) < float(threshold)


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------


def populate_indicators(
    candles: pd.DataFrame,
    *,
    ema_period: int = EMA_PERIOD,
    exit_threshold_pct: float = EXIT_THRESHOLD_PCT,
    funding: pd.Series | None = None,
    include_funding: bool = False,
) -> pd.DataFrame:
    """Populate ema / ema_exit and optionally funding features.

    `candles` must contain date, open, high, low, close, volume. Missing
    native hours must already be omitted. Degenerate volume=0 rows are
    retained unrepaired.
    """
    out = candles.copy()
    out["date"] = pd.to_datetime(out["date"], utc=True)
    out["ema"] = talib_ema(np.asarray(out["close"], dtype=np.float64), ema_period)
    out["ema_exit"] = ema_exit_level(out["ema"], exit_threshold_pct)
    if include_funding:
        if funding is None:
            raise Market03AuthorityError("MARKET_03_FUNDING_REQUIRED_FOR_FILTERED")
        feats = pinned_external_funding_features(out["date"], funding)
        out["funding"] = feats["funding"].to_numpy()
        out["funding_3d"] = feats["funding_3d"].to_numpy()
        out["funding_pct"] = feats["funding_pct"].to_numpy()
    else:
        out["funding"] = np.nan
        out["funding_3d"] = np.nan
        out["funding_pct"] = np.nan
    return out


def populate_entry_trend(dataframe: pd.DataFrame, variant: Variant) -> pd.DataFrame:
    out = dataframe.copy()
    cross = crossed_above(out["close"], out["ema"])
    vol_ok = out["volume"] > 0
    if variant == "filtered":
        pct = out["funding_pct"]
        fund_ok = (pct < FUNDING_MAX_PCT) | pct.isna()
        mask = cross & vol_ok & fund_ok
        tag = ENTRY_TAG_FILTERED
    elif variant == "baseline":
        mask = cross & vol_ok
        tag = ENTRY_TAG_BASELINE
    else:
        raise Market03AuthorityError("MARKET_03_UNKNOWN_VARIANT")
    out["enter_long"] = np.where(mask.fillna(False), 1, 0).astype(np.int64)
    out["enter_tag"] = np.where(mask.fillna(False), tag, None)
    return out


def populate_exit_trend(dataframe: pd.DataFrame) -> pd.DataFrame:
    out = dataframe.copy()
    mask = crossed_below(out["close"], out["ema_exit"])
    out["exit_long"] = np.where(mask.fillna(False), 1, 0).astype(np.int64)
    out["exit_tag"] = np.where(mask.fillna(False), EXIT_TAG, None)
    return out


def advise_signals(
    candles: pd.DataFrame,
    variant: Variant,
    *,
    funding: pd.Series | None = None,
) -> pd.DataFrame:
    include_funding = variant == "filtered"
    df = populate_indicators(
        candles,
        funding=funding,
        include_funding=include_funding,
    )
    df = populate_entry_trend(df, variant)
    df = populate_exit_trend(df)
    if not CAN_SHORT:
        df["enter_short"] = 0
        df["exit_short"] = 0
    return df


# ---------------------------------------------------------------------------
# Trade / wallet simulation (Freqtrade 2026.7 LEVEL_2)
# ---------------------------------------------------------------------------


@dataclass
class Trade:
    id: int
    open_date: pd.Timestamp
    open_rate: float
    amount: float
    stake_amount: float
    fee_open: float
    enter_tag: str
    stop_loss: float
    initial_stop_loss: float
    stop_loss_pct: float = STOPLOSS
    is_stop_loss_trailing: bool = False
    close_date: pd.Timestamp | None = None
    close_rate: float | None = None
    fee_close: float = 0.0
    exit_reason: str | None = None
    is_open: bool = True

    @property
    def profit_abs(self) -> float | None:
        if self.close_rate is None:
            return None
        open_val = self.amount * self.open_rate * (1.0 + FEE_PER_SIDE)
        close_val = self.amount * self.close_rate * (1.0 - FEE_PER_SIDE)
        return close_val - open_val

    @property
    def profit_ratio(self) -> float | None:
        if self.close_rate is None:
            return None
        return (self.close_rate * (1.0 - FEE_PER_SIDE)) / (
            self.open_rate * (1.0 + FEE_PER_SIDE)
        ) - 1.0


@dataclass
class WalletPoint:
    date: pd.Timestamp
    currency: str
    price: float
    total: float

    @property
    def total_quote(self) -> float:
        return float(self.total) * float(self.price)


@dataclass
class SimulationResult:
    variant: Variant
    trades: list[Trade]
    wallet: list[WalletPoint]
    daily_equity: pd.Series
    metrics: dict[str, Any]
    n_candles: int
    n_signals_entry: int
    n_signals_exit: int
    force_exited: bool
    origin: str


def _shift_signals_like_freqtrade(df: pd.DataFrame) -> pd.DataFrame:
    """Entry/exit flags used on candle T are those generated on T-1 close."""
    out = df.copy()
    for col, is_tag in (("enter_long", False), ("exit_long", False), ("enter_tag", True), ("exit_tag", True)):
        if col not in out.columns:
            out[col] = None if is_tag else 0
        if is_tag:
            out[col] = out[col].shift(1)
        else:
            out[col] = out[col].replace([np.nan], [0]).shift(1).fillna(0).astype(np.int64)
    return out.iloc[1:].reset_index(drop=True)


def _dir_correct_long(stop_loss: float, low: float) -> bool:
    return stop_loss < low


def _adjust_stop_loss(
    trade: Trade,
    current_price: float,
    stoploss: float,
    *,
    initial: bool = False,
) -> None:
    if initial and trade.stop_loss not in (None, 0.0):
        return
    new_loss = float(current_price) * (1.0 - abs(float(stoploss)))
    if trade.initial_stop_loss == 0.0 or initial:
        trade.stop_loss = new_loss
        trade.initial_stop_loss = new_loss
        trade.stop_loss_pct = -abs(float(stoploss))
        return
    if new_loss > trade.stop_loss:
        trade.is_stop_loss_trailing = True
        trade.stop_loss = new_loss
        trade.stop_loss_pct = -abs(float(stoploss))


def _maybe_trail(trade: Trade, high: float, low: float) -> None:
    if not TRAILING_STOP:
        return
    if not _dir_correct_long(trade.stop_loss, low):
        return
    sl_offset = TRAILING_STOP_POSITIVE_OFFSET
    bound_profit = (high / trade.open_rate) - 1.0
    if TRAILING_ONLY_OFFSET_IS_REACHED and bound_profit < sl_offset:
        return
    stop_loss_value = STOPLOSS
    if TRAILING_STOP_POSITIVE is not None and bound_profit > sl_offset:
        stop_loss_value = float(TRAILING_STOP_POSITIVE)
    _adjust_stop_loss(trade, high, stop_loss_value, initial=False)


def _stoploss_hit(trade: Trade, low: float) -> str | None:
    if trade.stop_loss >= low:
        if trade.is_stop_loss_trailing:
            return "trailing_stop_loss"
        return "stop_loss"
    return None


def _close_rate_for_stop(trade: Trade, row: Mapping[str, Any], reason: str, trade_dur_candles: int) -> float:
    stoploss_value = trade.stop_loss
    high = float(row["high"])
    low = float(row["low"])
    open_ = float(row["open"])
    if stoploss_value > high:
        return open_
    if reason == "trailing_stop_loss" and trade_dur_candles == 0:
        # Freqtrade 2026.7 entry-candle trailing fill (positive trail unset):
        # worst case: tick above open then dive; stop_rate = open * (1 - |sl|).
        stop_rate = open_ * (1.0 - abs(trade.stop_loss_pct))
        return max(low, stop_rate)
    return stoploss_value


def _open_trade(
    trade_id: int,
    row: Mapping[str, Any],
    cash: float,
    enter_tag: str,
) -> tuple[Trade, float]:
    rate = float(row["open"])
    stake = cash * TRADABLE_BALANCE_RATIO
    amount = stake / rate
    fee_open = amount * rate * FEE_PER_SIDE
    cash_after = cash - stake - fee_open
    stop = rate * (1.0 - abs(STOPLOSS))
    trade = Trade(
        id=trade_id,
        open_date=pd.Timestamp(row["date"]),
        open_rate=rate,
        amount=amount,
        stake_amount=stake,
        fee_open=fee_open,
        enter_tag=enter_tag,
        stop_loss=stop,
        initial_stop_loss=stop,
        stop_loss_pct=STOPLOSS,
    )
    return trade, cash_after


def _close_trade(trade: Trade, close_date: pd.Timestamp, close_rate: float, reason: str, cash: float) -> float:
    fee_close = trade.amount * close_rate * FEE_PER_SIDE
    proceeds = trade.amount * close_rate - fee_close
    trade.close_date = close_date
    trade.close_rate = float(close_rate)
    trade.fee_close = fee_close
    trade.exit_reason = reason
    trade.is_open = False
    return cash + proceeds


def _capture(wallet: list[WalletPoint], ts: pd.Timestamp, cash: float, trade: Trade | None, price: float) -> None:
    wallet.append(WalletPoint(date=ts, currency="USDT", price=1.0, total=cash))
    if trade is not None and trade.is_open and trade.amount > 0:
        wallet.append(WalletPoint(date=ts, currency="BTC", price=price, total=trade.amount))


def wallet_to_daily_equity(wallet: Sequence[WalletPoint]) -> pd.Series:
    """Author results.py: groupby date sum(total_quote).resample('D').last().ffill()."""
    if not wallet:
        return pd.Series(dtype=np.float64, name="BOT")
    frame = pd.DataFrame(
        {
            "date": [pd.Timestamp(w.date) for w in wallet],
            "total_quote": [w.total_quote for w in wallet],
        }
    )
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    equity = (
        frame.groupby("date")["total_quote"]
        .sum()
        .resample("D")
        .last()
        .ffill()
        .rename("BOT")
    )
    return equity


def risk_report(returns: pd.Series, ppy: int = PPY) -> dict[str, Any]:
    """Author metrics.py risk_report for the frozen secondary + primary MDD."""
    r = returns.dropna()
    if len(r) < 2 or float(r.std()) == 0.0:
        return {}
    cum = (1.0 + r).cumprod()
    dd = cum / cum.cummax() - 1.0
    downside = r[r < 0]
    n = len(r)
    cagr = float(cum.iloc[-1] ** (ppy / n) - 1.0)
    max_dd = float(dd.min())
    out: dict[str, Any] = {
        "Total return": float(cum.iloc[-1] - 1.0),
        "CAGR": cagr,
        "Max drawdown": max_dd,
        "Sharpe": float(r.mean() / r.std() * np.sqrt(ppy)),
        "Sortino": (
            float(r.mean() / downside.std() * np.sqrt(ppy)) if len(downside) else float("nan")
        ),
    }
    return out


def mdd_from_daily_equity(daily_equity: pd.Series) -> float | None:
    r = daily_equity.pct_change().dropna()
    report = risk_report(r)
    if not report or "Max drawdown" not in report:
        return None
    value = report["Max drawdown"]
    if value is None or not math.isfinite(float(value)):
        return None
    return float(value)


def classify_primary(
    mdd_filtered: float | None,
    mdd_baseline: float | None,
    *,
    invalid_reason: str | None = None,
) -> str:
    """Frozen primary classification. Magnitude cannot override."""
    if invalid_reason:
        return CLASS_EXECUTION_INVALID
    if mdd_filtered is None or mdd_baseline is None:
        return CLASS_EXECUTION_INCOMPLETE
    if not math.isfinite(float(mdd_filtered)) or not math.isfinite(float(mdd_baseline)):
        return CLASS_EXECUTION_INCOMPLETE
    if float(mdd_filtered) > float(mdd_baseline):
        return CLASS_REPRODUCED_DIRECTION
    return CLASS_NOT_REPRODUCED_DIRECTION


def _ensure_no_protected_oos(dates: Iterable) -> None:
    bound = pd.Timestamp(PROTECTED_OOS_START)
    for value in dates:
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        if ts >= bound:
            raise Market03AuthorityError("MARKET_03_PROTECTED_OOS_ACCESS")


def simulate_strategy(
    advised: pd.DataFrame,
    *,
    variant: Variant,
    origin: str,
    evaluation_start: str = EVALUATION_START_INCLUSIVE,
    evaluation_end: str = EVALUATION_END_EXCLUSIVE,
    initial_capital: float = INITIAL_CAPITAL_USDT,
) -> SimulationResult:
    """Freqtrade-2026.7-faithful single-pair long-only backtest.

    Signals are on candle close; fills at next open (via shifted flags).
    Same-candle order: exit_signal → stoploss → ROI → trailing.
    No shorts. max_open_trades=1. Last-row entries are refused; leftover
    positions force_exit at last in-interval candle open.
    """
    if CAN_SHORT:
        raise Market03AuthorityError("MARKET_03_SHORTS_MUST_REMAIN_DISABLED")
    df = advised.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True)
    _ensure_no_protected_oos(df["date"])
    eval_start = pd.Timestamp(evaluation_start)
    eval_end = pd.Timestamp(evaluation_end)
    if eval_start.tzinfo is None:
        eval_start = eval_start.tz_localize("UTC")
    if eval_end.tzinfo is None:
        eval_end = eval_end.tz_localize("UTC")
    if eval_end > pd.Timestamp(PROTECTED_OOS_START):
        raise Market03AuthorityError("MARKET_03_EVALUATION_OVERLAPS_PROTECTED_OOS")

    shifted = _shift_signals_like_freqtrade(df)
    n_entry = int((advised.get("enter_long", 0) == 1).sum()) if "enter_long" in advised else 0
    n_exit = int((advised.get("exit_long", 0) == 1).sum()) if "exit_long" in advised else 0

    cash = float(initial_capital)
    open_trade: Trade | None = None
    trades: list[Trade] = []
    wallet: list[WalletPoint] = []
    trade_id = 0
    force_exited = False
    n_rows = len(shifted)
    for i, row in shifted.iterrows():
        ts = pd.Timestamp(row["date"])
        is_last = i == n_rows - 1
        in_eval = eval_start <= ts < eval_end
        # Wallet capture at candle open, before this candle's orders (Freqtrade).
        _capture(wallet, ts, cash, open_trade, float(row["open"]))

        enter_flag = int(row["enter_long"]) == 1
        exit_flag = int(row["exit_long"]) == 1
        # Colliding enter+exit on the shifted row: ignore entry.
        if enter_flag and exit_flag:
            enter_flag = False

        can_enter = (not is_last) and in_eval and open_trade is None
        if can_enter and enter_flag and MAX_OPEN_TRADES == 1:
            tag = row["enter_tag"] if isinstance(row["enter_tag"], str) else (
                ENTRY_TAG_FILTERED if variant == "filtered" else ENTRY_TAG_BASELINE
            )
            trade_id += 1
            open_trade, cash = _open_trade(trade_id, row, cash, tag)

        if open_trade is not None and open_trade.is_open and in_eval:
            trade_dur = 0 if ts == open_trade.open_date else 1
            exits: list[tuple[str, float]] = []
            if exit_flag:
                exits.append(("exit_signal", float(row["open"])))
            _maybe_trail(open_trade, float(row["high"]), float(row["low"]))
            sl_reason = _stoploss_hit(open_trade, float(row["low"]))
            # Sequence: exit_signal, stoploss, ROI, trailing.
            # Trailing vs static is distinguished after trail adjustment.
            if sl_reason == "stop_loss":
                exits.append(("stop_loss", _close_rate_for_stop(open_trade, row, "stop_loss", trade_dur)))
            # ROI {"0": 10} is 1000% and does not fire on spot BTC.
            if sl_reason == "trailing_stop_loss":
                exits.append(
                    (
                        "trailing_stop_loss",
                        _close_rate_for_stop(open_trade, row, "trailing_stop_loss", trade_dur),
                    )
                )
            if exits:
                reason, rate = exits[0]
                cash = _close_trade(open_trade, ts, rate, reason, cash)
                trades.append(open_trade)
                open_trade = None

    if open_trade is not None and open_trade.is_open:
        last = shifted.iloc[-1]
        last_ts = pd.Timestamp(last["date"])
        if last_ts >= eval_end:
            raise Market03AuthorityError("MARKET_03_FORCE_EXIT_WOULD_READ_PROTECTED_OOS")
        cash = _close_trade(open_trade, last_ts, float(last["open"]), "force_exit", cash)
        trades.append(open_trade)
        open_trade = None
        force_exited = True
        _capture(wallet, last_ts, cash, None, 1.0)

    equity_all = wallet_to_daily_equity(wallet)
    if equity_all.empty:
        daily = equity_all
    else:
        # Warmup must not contribute to performance metrics.
        daily = equity_all.loc[equity_all.index >= eval_start]
        daily = daily.loc[daily.index < eval_end]
    r = daily.pct_change().dropna() if not daily.empty else pd.Series(dtype=np.float64)
    metrics = risk_report(r)
    metrics["trade_count"] = len(trades)
    return SimulationResult(
        variant=variant,
        trades=trades,
        wallet=wallet,
        daily_equity=daily,
        metrics=metrics,
        n_candles=len(advised),
        n_signals_entry=n_entry,
        n_signals_exit=n_exit,
        force_exited=force_exited,
        origin=origin,
    )


def descriptive_magnitude(mdd_filtered: float, mdd_baseline: float) -> dict[str, float]:
    """Descriptive only. Cannot change primary classification."""
    abs_pp = 100.0 * (mdd_filtered - mdd_baseline)
    rel = (mdd_filtered - mdd_baseline) / abs(mdd_baseline) if mdd_baseline != 0 else float("nan")
    return {
        "OBS_ABS_REDUCTION_PP": float(abs_pp),
        "OBS_REL_REDUCTION": float(rel),
        "baseline_vs_author_pp": 100.0 * (mdd_baseline - AUTHOR_MDD_BASELINE),
        "filtered_vs_author_pp": 100.0 * (mdd_filtered - AUTHOR_MDD_FILTERED),
    }


def evaluate_market_03_reproduction(
    candles: pd.DataFrame,
    *,
    origin: str,
    funding: pd.Series | None = None,
    funding_time_ms: Sequence[int] | np.ndarray | None = None,
    funding_rate: Sequence[float] | np.ndarray | None = None,
    spot_snapshot_id: str | None = None,
    funding_snapshot_id: str | None = None,
    dataset_id: str | None = None,
    source_path: str | None = None,
    external_commit: str | None = None,
    external_tree: str | None = None,
    evaluation_start: str = EVALUATION_START_INCLUSIVE,
    evaluation_end: str = EVALUATION_END_EXCLUSIVE,
    require_prereg_bytes: bool = True,
) -> dict[str, Any]:
    """Run baseline and filtered on the provided (non-bound) inputs.

    Fail-closed: bound snapshots, B2-06, protected OOS, and unknown origins
    become EXECUTION_INVALID rather than NOT_REPRODUCED_DIRECTION.
    """
    invalid: str | None = None
    try:
        if require_prereg_bytes:
            authenticate_frozen_prereg_bytes()
        require_external_source_identity(external_commit, external_tree)
        n_spot = int(len(candles)) if candles is not None else None
        n_fund = None
        if funding is not None:
            n_fund = int(len(funding))
        elif funding_time_ms is not None:
            n_fund = int(len(funding_time_ms))
        refuse_bound_scientific_inputs(
            origin=origin,
            spot_snapshot_id=spot_snapshot_id,
            funding_snapshot_id=funding_snapshot_id,
            dataset_id=dataset_id,
            source_path=source_path,
            n_spot_rows=n_spot,
            n_funding_rows=n_fund,
        )
        if dataset_id == B2_06_DATASET_ID or funding_snapshot_id == B2_06_SNAPSHOT_ID:
            raise Market03AuthorityError("MARKET_03_B2_06_IS_NOT_FUNDING_AUTHORITY")
        if funding is None and funding_time_ms is not None and funding_rate is not None:
            funding = funding_series_from_observations(funding_time_ms, funding_rate)
        if funding is None:
            raise Market03AuthorityError("MARKET_03_MISSING_FUNDING_AUTHORITY")
        _ensure_no_protected_oos(pd.to_datetime(candles["date"], utc=True))
        baseline_advised = advise_signals(candles, "baseline", funding=None)
        filtered_advised = advise_signals(candles, "filtered", funding=funding)
        # Isolation: exit columns must match; funding may change entries only.
        if not np.array_equal(
            np.asarray(baseline_advised["exit_long"]),
            np.asarray(filtered_advised["exit_long"]),
        ):
            raise Market03AuthorityError("MARKET_03_FUNDING_FILTER_MUTATED_EXITS")
        base_sim = simulate_strategy(
            baseline_advised,
            variant="baseline",
            origin=origin,
            evaluation_start=evaluation_start,
            evaluation_end=evaluation_end,
        )
        filt_sim = simulate_strategy(
            filtered_advised,
            variant="filtered",
            origin=origin,
            evaluation_start=evaluation_start,
            evaluation_end=evaluation_end,
        )
        mdd_b = mdd_from_daily_equity(base_sim.daily_equity)
        mdd_f = mdd_from_daily_equity(filt_sim.daily_equity)
        primary = classify_primary(mdd_f, mdd_b)
        magnitude = None
        if mdd_b is not None and mdd_f is not None:
            magnitude = descriptive_magnitude(mdd_f, mdd_b)
        return {
            "primary_classification": primary,
            "invalid_reason": None,
            "mdd_baseline": mdd_b,
            "mdd_filtered": mdd_f,
            "magnitude_descriptive": magnitude,
            "baseline": {
                "metrics": base_sim.metrics,
                "trade_count": len(base_sim.trades),
                "n_signals_entry": base_sim.n_signals_entry,
                "n_signals_exit": base_sim.n_signals_exit,
                "force_exited": base_sim.force_exited,
            },
            "filtered": {
                "metrics": filt_sim.metrics,
                "trade_count": len(filt_sim.trades),
                "n_signals_entry": filt_sim.n_signals_entry,
                "n_signals_exit": filt_sim.n_signals_exit,
                "force_exited": filt_sim.force_exited,
            },
            "replication_level": "LEVEL_2_FAITHFUL_REIMPLEMENTATION",
            "STRICT_HISTORICAL_PUBLICATION_LATENCY": STRICT_HISTORICAL_PUBLICATION_LATENCY,
            "origin": origin,
            "baseline_trades": base_sim.trades,
            "filtered_trades": filt_sim.trades,
            "baseline_sim": base_sim,
            "filtered_sim": filt_sim,
        }
    except (Market03AuthorityError, Market03BoundDataRefused, Market03ExecutionNotAuthorized) as exc:
        invalid = str(exc)
        return {
            "primary_classification": CLASS_EXECUTION_INVALID,
            "invalid_reason": invalid,
            "mdd_baseline": None,
            "mdd_filtered": None,
            "magnitude_descriptive": None,
            "replication_level": "LEVEL_2_FAITHFUL_REIMPLEMENTATION",
            "STRICT_HISTORICAL_PUBLICATION_LATENCY": STRICT_HISTORICAL_PUBLICATION_LATENCY,
            "origin": origin,
        }


def same_candle_exit_order() -> tuple[str, ...]:
    return ("exit_signal", "stoploss", "roi", "trailing_stoploss")
