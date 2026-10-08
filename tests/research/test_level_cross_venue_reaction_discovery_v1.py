"""LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1. Outcome-blind guards and feature identity."""

from __future__ import annotations

import gzip
import math
from pathlib import Path

import numpy as np
import pytest

from scripts.research.level_cross_venue_reaction_discovery_v1 import constants as K
from scripts.research.level_cross_venue_reaction_discovery_v1.claim import (
    conjunction, family_stability, route, side_stability, year_stability,
)
from scripts.research.level_cross_venue_reaction_discovery_v1.evaluate import refuse_if_recorded
from scripts.research.level_cross_venue_reaction_discovery_v1.features import (
    cross_venue_features, log_return, orient,
)
from scripts.research.level_cross_venue_reaction_discovery_v1.inference import (
    bh_adjust, columns_for, drop_redundant, fit_rows, freeze_scales,
)
from scripts.research.level_cross_venue_reaction_discovery_v1.series import VenueSeries


def test_instruments_are_same_class_perpetuals():
    assert K.REFERENCE_VENUE == "BINANCE_USD_M_BTCUSDT_PERP"
    assert K.OTHER_VENUES == ("BYBIT_LINEAR_BTCUSDT_PERP", "OKX_BTC_USDT_SWAP_PERP")
    assert K.TIER == "TIER_A"
    blob = Path("scripts/research/level_cross_venue_reaction_discovery_v1").read_text() if False else ""
    package = Path("scripts/research/level_cross_venue_reaction_discovery_v1")
    text = "\n".join(path.read_text() for path in package.glob("*.py"))
    assert "BTC-USDT\"" not in text
    assert "instId=BTC-USDT&" not in text
    assert "mark-price-candles?" not in text
    assert "category=spot" not in text
    assert "2026-01" not in text and "2025-01-02" not in text
    assert K.SURFACE_END_MS == 1735689600000
    assert K.ALIGNMENT_TOLERANCE_MS == 0
    assert K.REACTION_MS == 15 * 60_000
    assert K.LATE_START_OFFSET == 3 and K.LATE_STOP_OFFSET == 49


def test_preflight_does_not_import_the_late_label():
    text = Path("scripts/research/level_cross_venue_reaction_discovery_v1/preflight.py").read_text()
    assert "late_label" not in text
    assert "LATE_BREAK" not in text


def test_series_is_exact_and_refuses_2025(tmp_path: Path):
    path = tmp_path / "s.csv.gz"
    rows = [
        "open_ms,open,high,low,close",
        "1585699200000,1,1,1,10",
        "1585699500000,1,1,1,11",
    ]
    path.write_bytes(gzip.compress("\n".join(rows).encode(), mtime=0))
    from scripts.research.level_cross_venue_reaction_discovery_v1.series import _load_csv
    series = _load_csv(path, "BYBIT_LINEAR_BTCUSDT_PERP")
    assert series.close_at(1585699200000) == 10.0
    assert series.close_at(1585699200000 + 60_000) is None
    assert series.close_at(1585699500000 + 300_000) is None
    with pytest.raises(RuntimeError):
        VenueSeries("X", np.asarray([K.SURFACE_END_MS]), np.asarray([1.0]))


def test_no_forward_fill_when_the_middle_bar_is_absent():
    series = VenueSeries(
        "OKX_BTC_USDT_SWAP_PERP",
        np.asarray([1585699200000, 1585699200000 + 600_000]),
        np.asarray([10.0, 12.0]),
    )
    assert series.close_at(1585699200000 + 300_000) is None
    assert log_return(series.close_at(1585699200000), series.close_at(1585699200000 + 300_000)) is None


def test_feature_formulas_orientation_and_exact_zero():
    # side +1: break up. Bybit and OKX move up, Binance moves up more.
    got = cross_venue_features(0.30, 0.10, 0.20, side=1)
    assert got["OTHER_VENUE_MEDIAN_MOVE"] == pytest.approx(0.15)
    assert got["CROSS_VENUE_CONFIRMATION_GAP"] == pytest.approx(0.15)
    assert got["CROSS_VENUE_DISPERSION"] == pytest.approx(float(np.std([0.30, 0.10, 0.20], ddof=0)))
    assert got["DIRECTION_AGREEMENT"] == pytest.approx(1.0)
    # support: side -1 flips the oriented signs. Raw dispersion does not flip.
    flipped = cross_venue_features(0.30, 0.10, 0.20, side=-1)
    assert flipped["OTHER_VENUE_MEDIAN_MOVE"] == pytest.approx(-0.15)
    assert flipped["CROSS_VENUE_DISPERSION"] == pytest.approx(got["CROSS_VENUE_DISPERSION"])
    assert flipped["DIRECTION_AGREEMENT"] == pytest.approx(0.0)
    # exact zero is neutral.
    zero = cross_venue_features(0.0, 0.0, 0.2, side=1)
    assert zero["DIRECTION_AGREEMENT"] == pytest.approx(1.0 / 3.0)
    assert orient(0.0, 1) == 0.0
    assert orient(0.0, -1) == 0.0
    # one missing venue drops the whole family. Missing is not a flat return.
    missing = cross_venue_features(0.1, None, 0.1, side=1)
    assert all(value is None for value in missing.values())


def test_every_candidate_model_contains_end_position_on_the_same_rows():
    rows = []
    for i in range(40):
        rows.append({
            "y": float(i % 2),
            "END_POSITION_X": float((i * 3) % 11) - 5.0,
            "disp": float((i * 2) % 5),
            "OTHER_VENUE_MEDIAN_MOVE": float((i * 5) % 7) - 3.0,
            "family": "DAY" if i < 30 else "WEEK",
            "support": float(i % 2),
            "vol_tercile": i % 3,
            "epoch": "2022" if i < 20 else "2023",
            "time_block": (i // 2) % 4,
            "cluster": i // 4,
            "side": 1 if i % 2 == 0 else -1,
        })
    scales = freeze_scales(rows)
    assert scales["OTHER_VENUE_MEDIAN_MOVE"]["sd"] > 0
    columns = columns_for(rows, feature=True)
    assert columns[1] == "endpos_z"
    assert "feature_z" in columns
    baseline_columns = columns_for(rows, feature=False)
    assert "feature_z" not in baseline_columns
    assert "endpos_z" in baseline_columns
    fitted = fit_rows(rows, "OTHER_VENUE_MEDIAN_MOVE", scales, draws=0)
    baseline = fit_rows(rows, None, scales, draws=0)
    assert fitted["includes_end_position"] is True
    assert "endpos_z" in fitted["columns"]
    assert fitted["n"] == baseline["n"] == 40
    assert fitted["coef"] is not None and baseline["coef"] is not None


def test_redundancy_drops_the_later_feature_before_any_outcome():
    rows = []
    for i in range(10):
        rows.append({
            "OTHER_VENUE_MEDIAN_MOVE": float(i),
            "CROSS_VENUE_CONFIRMATION_GAP": float(i) * 2.0,
            "CROSS_VENUE_DISPERSION": float(i % 3),
            "DIRECTION_AGREEMENT": float(i) / 9.0,
        })
    decision = drop_redundant(rows)
    assert "CROSS_VENUE_CONFIRMATION_GAP" in {item["feature"] for item in decision["dropped"]}
    assert "OTHER_VENUE_MEDIAN_MOVE" in decision["retained"]
    assert abs(decision["rho"]["OTHER_VENUE_MEDIAN_MOVE__CROSS_VENUE_CONFIRMATION_GAP"]) >= 0.90


def test_bh_year_family_side_and_routing():
    q = bh_adjust([0.01, 0.04, None])
    assert q[0] <= q[1] <= 1.0
    epochs = [{"n": 40, "coef": 0.05}, {"n": 40, "coef": 0.04}, {"n": 40, "coef": 0.03},
              {"n": 40, "coef": 0.02}, {"n": 40, "coef": -0.01}]
    assert year_stability(0.04, epochs)["pass"] is True
    assert year_stability(0.04, epochs[:3] + [{"n": 40, "coef": -0.05}])["pass"] is False
    assert family_stability([
        {"name": "DAY", "n": 40, "coef": 0.04},
        {"name": "WEEK", "n": 40, "coef": -0.04},
    ])["pass"] is False
    assert family_stability([
        {"name": "DAY", "n": 40, "coef": 0.04},
        {"name": "WEEK", "n": 10, "coef": -0.04},
    ])["pass"] is True
    assert side_stability([
        {"name": "resistance", "n": 40, "coef": 0.04},
        {"name": "support", "n": 40, "coef": 0.02},
    ])["pass"] is True
    cell = {"coef": 0.05, "ci95": [0.02, 0.08], "q": 0.04, "includes_end_position": True}
    decision = conjunction(
        cell,
        epochs,
        [{"name": f"omit_{i}", "n": 80, "coef": 0.04} for i in range(5)],
        [{"name": "DAY", "n": 40, "coef": 0.04}, {"name": "WEEK", "n": 40, "coef": 0.03}],
        [{"name": "resistance", "n": 40, "coef": 0.04}, {"name": "support", "n": 40, "coef": 0.02}],
        venue_artifact=False,
    )
    assert decision["pass"] is True
    blocked = route([], n_resolved=0, history_ok=True, novelty_ok=False)
    assert blocked == "BLOCKED_REOPENING_CROSS_VENUE_CELL"
    insufficient = route([], n_resolved=0, history_ok=False, novelty_ok=True)
    assert insufficient == "CROSS_VENUE_HISTORY_INSUFFICIENT"


def test_rerun_refusal(tmp_path: Path):
    recorded = tmp_path / "RESULT.json"
    recorded.write_text("{}")
    with pytest.raises(SystemExit, match="REFUSING_RERUN"):
        refuse_if_recorded(recorded, tmp_path / "missing.md")


def test_log_return_uses_prices_not_levels():
    assert log_return(100.0, 110.0) == pytest.approx(math.log(1.1))
    assert log_return(0.0, 110.0) is None
    assert log_return(100.0, None) is None
