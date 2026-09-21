"""Row ineligibility vs source-integrity failure (red-team F-03).

Preregistered eligibility conditions drop a row. Source corruption must
abort canonical execution as MARKET_06_INCOMPLETE_EXECUTION and must never
become a silent row drop, because dropping corrupt observations would
silently improve support.

Synthetic fixtures only.
"""

from __future__ import annotations

import io
import json
import math
import zipfile
from datetime import datetime, timezone

import pytest

from scripts.research import market_06_cross_venue_dislocation_evaluator as ev
from scripts.research import market_06_cross_venue_dislocation_parsers as parsers
from scripts.research.market_06_cross_venue_dislocation_authority import (
    Market06IncompleteExecution,
    Market06RowIneligible,
)
from scripts.research.market_06_cross_venue_dislocation_parsers import BAR_MS, PerpBar

T = datetime(2024, 6, 15, 0, 5, tzinfo=timezone.utc)
T_MS = int(T.timestamp() * 1000)
E_MS = T_MS - BAR_MS


def _grid():
    perp: dict[int, PerpBar] = {}
    spot: dict[int, float] = {}
    ts = E_MS - 9000 * BAR_MS
    idx = 0
    while ts <= T_MS + 400 * BAR_MS:
        idx += 1
        px = 100.0 + (idx % 97) * 0.01
        perp[ts] = PerpBar(ts, px, px + 0.5, px - 0.5, px + 0.1)
        spot[ts] = px
        ts += BAR_MS
    return perp, spot


def test_baseline_grid_is_eligible():
    perp, spot = _grid()
    assert ev.construct_row_or_none(T_MS, "HOLDOUT_2024", perp, spot) is not None


# --------------------------------------------------------------------------
# Legitimate, preregistered row ineligibility -> row dropped.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,boundary_offset_bars",
    [
        ("D_E bar", 1),
        ("newest reference", 2),
        ("oldest reference", 8641),
        ("E-24h bar", 289),
        ("mid RV bar", 100),
    ],
)
def test_missing_required_feature_bar_is_row_ineligible(label, boundary_offset_bars):
    perp, spot = _grid()
    missing = E_MS - boundary_offset_bars * BAR_MS
    perp.pop(missing, None)
    spot.pop(missing, None)
    assert ev.construct_row_or_none(T_MS, "HOLDOUT_2024", perp, spot) is None


@pytest.mark.parametrize("offset", [0, 144, 287])
def test_missing_entry_or_outcome_bar_is_row_ineligible(offset):
    perp, spot = _grid()
    perp.pop(T_MS + offset * BAR_MS, None)
    assert ev.construct_row_or_none(T_MS, "HOLDOUT_2024", perp, spot) is None


def test_btc_ret_exactly_zero_is_row_ineligible():
    with pytest.raises(Market06RowIneligible) as exc:
        ev.btc_ret_24h(100.0, 100.0)
    assert exc.value.reason == "BTC_RET_24H_EQ_0"
    with pytest.raises(Market06RowIneligible):
        ev.btc_side_from_ret(0.0)


def test_mad_le_zero_is_row_ineligible():
    with pytest.raises(Market06RowIneligible) as exc:
        ev.robust_dislocation_z(0.5, [0.25] * ev.REFERENCE_COUNT)
    assert exc.value.reason == "MAD_LE_0"


def test_rv_le_zero_is_row_ineligible():
    with pytest.raises(Market06RowIneligible) as exc:
        ev.rv_btc_24h([100.0] * (ev.RV_RETURN_COUNT + 1))
    assert exc.value.reason == "RV_LE_0_OR_NONFINITE"


def test_forbidden_decision_time_is_row_ineligible():
    dec31 = int(datetime(2024, 12, 31, 0, 5, tzinfo=timezone.utc).timestamp() * 1000)
    perp, spot = _grid()
    assert ev.construct_row_or_none(dec31, "HOLDOUT_2024", perp, spot) is None


# --------------------------------------------------------------------------
# Source corruption -> INCOMPLETE_EXECUTION, never a silent row drop.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("boundary_offset_bars", [1, 2, 100, 289])
def test_nonpositive_close_in_feature_window_aborts_execution(boundary_offset_bars):
    perp, spot = _grid()
    corrupt_open = E_MS - boundary_offset_bars * BAR_MS
    good = perp[corrupt_open]
    perp[corrupt_open] = PerpBar(corrupt_open, good.open, good.high, good.low, -5.0)
    with pytest.raises(Market06IncompleteExecution):
        ev.construct_row_or_none(T_MS, "HOLDOUT_2024", perp, spot)


def test_nonpositive_spot_close_aborts_execution():
    perp, spot = _grid()
    spot[ev.bar_open_for_close_at(E_MS)] = 0.0
    with pytest.raises(Market06IncompleteExecution):
        ev.construct_row_or_none(T_MS, "HOLDOUT_2024", perp, spot)


def test_nonpositive_entry_price_aborts_execution():
    perp, spot = _grid()
    good = perp[T_MS]
    perp[T_MS] = PerpBar(T_MS, -1.0, good.high, good.low, good.close)
    with pytest.raises(Market06IncompleteExecution):
        ev.construct_row_or_none(T_MS, "HOLDOUT_2024", perp, spot)


def test_corruption_is_not_reachable_as_row_ineligible():
    """Market06RowIneligible must not be raised for corrupt data."""

    assert not issubclass(Market06IncompleteExecution, Market06RowIneligible)
    assert not issubclass(Market06RowIneligible, Market06IncompleteExecution)


def test_build_eligible_rows_propagates_integrity_failure():
    perp, spot = _grid()
    corrupt = ev.bar_open_for_close_at(E_MS)
    good = perp[corrupt]
    perp[corrupt] = PerpBar(corrupt, good.open, good.high, good.low, float("nan"))
    with pytest.raises(Market06IncompleteExecution):
        ev.construct_row_or_none(T_MS, "HOLDOUT_2024", perp, spot)


# --------------------------------------------------------------------------
# Parser-level integrity failures.
# --------------------------------------------------------------------------


def _zip(rows: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("BTCUSDT-5m.csv", rows)
    return buf.getvalue()


def test_parser_nonpositive_close_is_integrity_failure():
    with pytest.raises(Market06IncompleteExecution):
        parsers.parse_binance_klines_csv(
            "open_time,open,high,low,close\n1640995200000,100,101,99,-1", source="x"
        )


def test_parser_duplicate_timestamp_is_integrity_failure():
    rows = "open_time,open,high,low,close\n1640995200000,100,101,99,100\n1640995200000,100,101,99,100"
    with pytest.raises(Market06IncompleteExecution) as exc:
        parsers.parse_binance_klines_csv(rows, source="x")
    assert "BINANCE_DUPLICATE" in exc.value.reason


def test_parser_inconsistent_ohlc_is_integrity_failure():
    with pytest.raises(Market06IncompleteExecution) as exc:
        parsers.parse_binance_klines_csv(
            "open_time,open,high,low,close\n1640995200000,500,101,99,100", source="x"
        )
    assert "OHLC_INCONSISTENT" in exc.value.reason


def test_corrupt_zip_is_integrity_failure():
    with pytest.raises(Market06IncompleteExecution) as exc:
        parsers.parse_binance_zip_bytes(b"not-a-zip", zip_name="BTCUSDT-5m-2022-01.zip")
    assert "BAD_ZIP" in exc.value.reason


def test_wrong_zip_identity_is_integrity_failure():
    payload = _zip("open_time,open,high,low,close\n1640995200000,100,101,99,100")
    with pytest.raises(Market06IncompleteExecution) as exc:
        parsers.parse_binance_zip_bytes(payload, zip_name="ETHUSDT-1h-2022-01.zip")
    assert "BINANCE_IDENTITY" in exc.value.reason


def test_okx_invalid_confirm_is_integrity_failure():
    body = json.dumps(
        {"code": "0", "data": [["1640995200000", "1", "2", "0.5", "1", "1", "1", "1", "0"]]}
    ).encode()
    with pytest.raises(Market06IncompleteExecution) as exc:
        parsers.parse_okx_history_body(body, source="page")
    assert "OKX_CONFIRM" in exc.value.reason


def test_okx_bad_code_is_integrity_failure():
    body = json.dumps({"code": "50011", "data": []}).encode()
    with pytest.raises(Market06IncompleteExecution) as exc:
        parsers.parse_okx_history_body(body, source="page")
    assert "OKX_CODE" in exc.value.reason


def test_misaligned_timestamp_is_integrity_failure():
    with pytest.raises(Market06IncompleteExecution) as exc:
        parsers.parse_binance_klines_csv(
            "open_time,open,high,low,close\n1640995200001,100,101,99,100", source="x"
        )
    assert "NOT_5M_ALIGNED" in exc.value.reason
