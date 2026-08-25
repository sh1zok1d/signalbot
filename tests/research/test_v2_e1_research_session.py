from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from scripts.research.v2_e1_research_session import (
    E1ResearchReadSession,
    E1ResearchSessionError,
)

UTC = timezone.utc
CALC = "9bed1b4cf99f1644"


class _FakeConn:
    def __init__(self, row=None):
        self.row = row
        self.calls = []

    async def fetchrow(self, sql, *args):
        self.calls.append((sql, args))
        return self.row


def _session(conn, T):
    return E1ResearchReadSession(
        conn,
        symbol="BTCUSDT",
        market_type="perp",
        calculation_version=CALC,
        decision_boundary=T,
    )


def test_health_adapter_is_explicit_none_cross_product_and_refuses_future_cutoff():
    T = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    session = _session(_FakeConn(), T)

    result = asyncio.run(session.fetch_v2_data_health_at_cutoff(
        symbol="BTCUSDT",
        market_type="perp",
        exchanges=("binance", "bybit"),
        metrics=("ohlcv", "open_interest"),
        cutoff_ts=T,
        calculation_version=CALC,
    ))
    assert set(result) == {
        ("binance", "ohlcv"),
        ("binance", "open_interest"),
        ("bybit", "ohlcv"),
        ("bybit", "open_interest"),
    }
    assert all(value is None for value in result.values())

    with pytest.raises(E1ResearchSessionError, match="lookahead refused"):
        asyncio.run(session.fetch_v2_data_health_at_cutoff(
            symbol="BTCUSDT",
            market_type="perp",
            exchanges=("binance",),
            metrics=("ohlcv",),
            cutoff_ts=T + timedelta(minutes=1),
            calculation_version=CALC,
        ))


def test_instrument_lkg_is_unavailable_when_fetched_after_decision_T():
    T = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    conn = _FakeConn({
        "exchange": "binance",
        "symbol": "BTCUSDT",
        "market_type": "perp",
        "exchange_instrument_id": "BTCUSDT",
        "quantity_unit": "base",
        "contract_multiplier": 1.0,
        "tick_size": 0.1,
        "price_precision": 1,
        "quantity_precision": 3,
        "metadata_source": "exchange_api",
        "fetched_at": T + timedelta(minutes=1),
        "is_stale": False,
        "note": None,
    })
    session = _session(conn, T)
    row = asyncio.run(session.fetch_v2_instrument(
        exchange="binance", symbol="BTCUSDT", market_type="perp", as_of=T))
    assert row is None


def test_instrument_lkg_before_T_is_projected_without_mutating_db():
    T = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    fetched_at = T - timedelta(days=1)
    conn = _FakeConn({
        "exchange": "binance",
        "symbol": "BTCUSDT",
        "market_type": "perp",
        "exchange_instrument_id": "BTCUSDT",
        "quantity_unit": "base",
        "contract_multiplier": 1.0,
        "tick_size": 0.1,
        "price_precision": 1,
        "quantity_precision": 3,
        "metadata_source": "exchange_api",
        "fetched_at": fetched_at,
        "is_stale": False,
        "note": "original",
    })
    session = _session(conn, T)
    row = asyncio.run(session.fetch_v2_instrument(
        exchange="binance", symbol="BTCUSDT", market_type="perp", as_of=T))
    assert row is not None
    assert row["tick_size"] == 0.1
    assert row["observed_at"] == fetched_at
    assert row["effective_from"] == fetched_at
    assert row["effective_until"] is None
    assert len(conn.calls) == 1
