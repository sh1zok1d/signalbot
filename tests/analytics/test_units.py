"""Unit tests for analytics/feature_engine/units.py (pure, no DB/network)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from common.instrument_metadata import FailClosedError, InstrumentMetadata
from analytics.feature_engine.units import (
    UnitError, bar_notional_from_metadata, metadata_notional_eligible,
    notional_usd_per_bar,
)

FIXED = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _meta(unit, mult):
    return InstrumentMetadata(
        exchange="x", symbol="BTCUSDT", market_type="perp",
        exchange_instrument_id="ID", quantity_unit=unit, contract_multiplier=mult,
        tick_size=0.1, price_precision=None, quantity_precision=None,
        metadata_source="exchange_api", fetched_at=FIXED, is_stale=False)


# -- base / contracts formulas -----------------------------------------------
def test_base_quantity_times_close():
    assert notional_usd_per_bar(2.0, 100.0, "base") == 200.0


def test_contracts_quantity_times_multiplier_times_close():
    assert notional_usd_per_bar(3.0, 100.0, "contracts", 0.01) == pytest.approx(3.0)


def test_per_bar_aggregation_differs_from_sum_qty_times_final_close():
    # two bars, different closes: per-bar sum != sum(qty) * last close
    qtys_closes = [(1.0, 100.0), (1.0, 200.0)]
    per_bar = sum(notional_usd_per_bar(q, c, "base") for q, c in qtys_closes)
    naive = sum(q for q, _ in qtys_closes) * qtys_closes[-1][1]
    assert per_bar == 300.0
    assert naive == 400.0
    assert per_bar != naive


# -- fail-closed / validation ------------------------------------------------
def test_contracts_missing_multiplier_fails_closed():
    with pytest.raises(FailClosedError):
        notional_usd_per_bar(1.0, 100.0, "contracts", None)


def test_multiplier_not_defaulted_to_one():
    # if it silently defaulted to 1.0 this would return 100.0; it must raise
    with pytest.raises(FailClosedError):
        notional_usd_per_bar(1.0, 100.0, "contracts")


def test_unknown_unit_fails():
    with pytest.raises(UnitError):
        notional_usd_per_bar(1.0, 100.0, "lots")


def test_negative_quantity_fails():
    with pytest.raises(UnitError):
        notional_usd_per_bar(-1.0, 100.0, "base")


def test_zero_quantity_allowed():
    assert notional_usd_per_bar(0.0, 100.0, "base") == 0.0
    assert notional_usd_per_bar(0.0, 100.0, "contracts", 0.01) == 0.0


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_bad_close_rejected(bad):
    with pytest.raises(UnitError):
        notional_usd_per_bar(1.0, bad, "base")


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_bad_multiplier_rejected(bad):
    with pytest.raises(UnitError):
        notional_usd_per_bar(1.0, 100.0, "contracts", bad)


def test_non_finite_quantity_rejected():
    with pytest.raises(UnitError):
        notional_usd_per_bar(float("nan"), 100.0, "base")


# -- metadata-driven paths ---------------------------------------------------
def test_okx_contracts_metadata_path():
    m = _meta("contracts", 0.01)
    assert metadata_notional_eligible(m) is True
    assert bar_notional_from_metadata(5.0, 100.0, m) == pytest.approx(5.0)


def test_binance_bybit_base_metadata_path():
    m = _meta("base", None)
    assert metadata_notional_eligible(m) is True
    assert bar_notional_from_metadata(5.0, 100.0, m) == 500.0


def test_contracts_metadata_without_multiplier_not_eligible():
    m = _meta("contracts", None)
    assert metadata_notional_eligible(m) is False
    with pytest.raises(FailClosedError):
        bar_notional_from_metadata(1.0, 100.0, m)


def test_none_metadata_not_eligible():
    assert metadata_notional_eligible(None) is False


def test_inputs_not_mutated():
    m = _meta("contracts", 0.01)
    before = (m.quantity_unit, m.contract_multiplier, m.tick_size)
    notional_usd_per_bar(2.0, 100.0, "contracts", 0.01)
    bar_notional_from_metadata(2.0, 100.0, m)
    assert (m.quantity_unit, m.contract_multiplier, m.tick_size) == before
